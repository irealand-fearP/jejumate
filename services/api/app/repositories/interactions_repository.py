from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from psycopg import Connection
from psycopg.rows import DictRow

from app.core.db import get_connection
from app.schemas.home import HomeMeeting
from app.schemas.interactions import MeetingApplicationResponse, NicknameResponse
from app.services.home_service import get_home_data


@dataclass(frozen=True)
class ProfileRecord:
    user_id: UUID
    profile_id: UUID
    anonymous_id: str
    nickname: str


def _stable_uuid(kind: str, source_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"https://jejumate.local/{kind}/{source_id}")


def _new_anonymous_id() -> str:
    return f"anon_{uuid4().hex[:12]}"


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _find_home_meeting(source_id: str) -> HomeMeeting:
    for meeting in get_home_data().meetings:
        if meeting.id == source_id:
            return meeting
    raise ValueError(f"Unknown meeting id: {source_id}")


def _ensure_profile(
    connection: Connection[DictRow],
    *,
    nickname: str,
    anonymous_id: str | None,
) -> ProfileRecord:
    next_anonymous_id = _normalize_optional(anonymous_id) or _new_anonymous_id()

    user = connection.execute(
        """
        INSERT INTO users (anonymous_id)
        VALUES (%s)
        ON CONFLICT (anonymous_id)
        DO UPDATE SET updated_at = now()
        RETURNING id, anonymous_id
        """,
        (next_anonymous_id,),
    ).fetchone()
    if user is None:
        raise RuntimeError("Failed to upsert user")

    profile = connection.execute(
        """
        INSERT INTO profiles (user_id, nickname)
        VALUES (%s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET nickname = EXCLUDED.nickname, updated_at = now()
        RETURNING id, nickname
        """,
        (user["id"], nickname),
    ).fetchone()
    if profile is None:
        raise RuntimeError("Failed to upsert profile")

    return ProfileRecord(
        user_id=user["id"],
        profile_id=profile["id"],
        anonymous_id=user["anonymous_id"],
        nickname=profile["nickname"],
    )


def _ensure_host_profile(connection: Connection[DictRow], meeting: HomeMeeting) -> tuple[UUID, UUID]:
    host_user_id = _stable_uuid("host-user", meeting.host.profile_id)
    host_profile_id = _stable_uuid("host-profile", meeting.host.profile_id)
    host_anonymous_id = f"host_{meeting.host.profile_id}"[:80]

    connection.execute(
        """
        INSERT INTO users (id, anonymous_id)
        VALUES (%s, %s)
        ON CONFLICT (id)
        DO UPDATE SET anonymous_id = EXCLUDED.anonymous_id, updated_at = now()
        """,
        (host_user_id, host_anonymous_id),
    )
    connection.execute(
        """
        INSERT INTO profiles (id, user_id, nickname, avatar_key)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id)
        DO UPDATE SET nickname = EXCLUDED.nickname, updated_at = now()
        """,
        (host_profile_id, host_user_id, meeting.host.nickname, "host_default"),
    )

    return host_user_id, host_profile_id


def _ensure_meeting(connection: Connection[DictRow], source_id: str) -> UUID:
    meeting = _find_home_meeting(source_id)
    host_user_id, host_profile_id = _ensure_host_profile(connection, meeting)
    meeting_id = _stable_uuid("meeting", source_id)

    connection.execute(
        """
        INSERT INTO meetings (
            id,
            host_user_id,
            host_profile_id,
            category,
            title,
            place_label,
            starts_at,
            ends_at,
            capacity,
            approved_count,
            status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id)
        DO UPDATE SET
            category = EXCLUDED.category,
            title = EXCLUDED.title,
            place_label = EXCLUDED.place_label,
            starts_at = EXCLUDED.starts_at,
            ends_at = EXCLUDED.ends_at,
            capacity = EXCLUDED.capacity,
            approved_count = EXCLUDED.approved_count,
            status = EXCLUDED.status,
            updated_at = now()
        """,
        (
            meeting_id,
            host_user_id,
            host_profile_id,
            meeting.category,
            meeting.title,
            meeting.place_label,
            meeting.starts_at,
            meeting.ends_at,
            meeting.capacity,
            meeting.approved_count,
            meeting.status,
        ),
    )

    return meeting_id


def create_or_update_profile(*, nickname: str, anonymous_id: str | None) -> NicknameResponse:
    with get_connection() as connection:
        with connection.transaction():
            profile = _ensure_profile(connection, nickname=nickname, anonymous_id=anonymous_id)

    return NicknameResponse(
        profile_id=str(profile.profile_id),
        nickname=profile.nickname,
        anonymous_id=profile.anonymous_id,
        public_note="다른 참가자에게는 닉네임과 공개 관심사만 표시됩니다.",
        persisted=True,
    )


def create_or_update_application(
    *,
    meeting_source_id: str,
    nickname: str,
    message: str | None,
    anonymous_id: str | None,
) -> MeetingApplicationResponse:
    with get_connection() as connection:
        with connection.transaction():
            applicant = _ensure_profile(connection, nickname=nickname, anonymous_id=anonymous_id)
            meeting_id = _ensure_meeting(connection, meeting_source_id)
            application = connection.execute(
                """
                INSERT INTO meeting_applications (
                    meeting_id,
                    applicant_user_id,
                    applicant_profile_id,
                    message,
                    status
                )
                VALUES (%s, %s, %s, %s, 'pending')
                ON CONFLICT (meeting_id, applicant_user_id)
                DO UPDATE SET
                    applicant_profile_id = EXCLUDED.applicant_profile_id,
                    message = EXCLUDED.message,
                    updated_at = now()
                RETURNING id, status
                """,
                (meeting_id, applicant.user_id, applicant.profile_id, _normalize_optional(message)),
            ).fetchone()

    if application is None:
        raise RuntimeError("Failed to upsert meeting application")

    return MeetingApplicationResponse(
        application_id=str(application["id"]),
        meeting_id=meeting_source_id,
        status=application["status"],
        public_alias=applicant.nickname,
        privacy_note="실명, 전화번호, 생년월일은 호스트와 참가자에게 공개되지 않습니다.",
        next_step="호스트 승인 후 알림으로 참여 확정을 안내합니다.",
        persisted=True,
    )


def _infer_intent(question: str) -> str:
    normalized = question.lower()
    if "정책" in normalized or "지원" in normalized or "신청" in normalized:
        return "policy"
    if "맛집" in normalized or "카페" in normalized or "코스" in normalized:
        return "place"
    if "모임" in normalized or "밥" in normalized or "친구" in normalized:
        return "meeting"
    return "general"


def log_rag_query(*, question: str, anonymous_id: str | None, used_source_count: int) -> str:
    normalized_anonymous_id = _normalize_optional(anonymous_id)

    with get_connection() as connection:
        user_id = None
        if normalized_anonymous_id:
            user = connection.execute(
                "SELECT id FROM users WHERE anonymous_id = %s",
                (normalized_anonymous_id,),
            ).fetchone()
            user_id = user["id"] if user else None

        with connection.transaction():
            query_log = connection.execute(
                """
                INSERT INTO rag_query_logs (
                    user_id,
                    anonymous_id,
                    query,
                    intent,
                    used_source_count,
                    confidence
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    normalized_anonymous_id,
                    question,
                    _infer_intent(question),
                    used_source_count,
                    "low",
                ),
            ).fetchone()

    if query_log is None:
        raise RuntimeError("Failed to log RAG query")

    return str(query_log["id"])
