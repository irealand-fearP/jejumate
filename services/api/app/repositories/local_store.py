from __future__ import annotations

import json
import random
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.core.config import settings
from app.schemas.home import (
    ActivitySummary,
    HomeMeeting,
    HomePolicy,
    HomeResponse,
    MeetingCta,
    MeetingHost,
    MeetingSummary,
    PrivacyChip,
    ProfileChip,
    RagStrip,
)
from app.schemas.interactions import (
    ChatMessage,
    ChatMessagesResponse,
    MeetingApplicationDecisionResponse,
    MeetingApplicationListItem,
    MeetingApplicationListResponse,
    MeetingApplicationResponse,
    MeetingCreateResponse,
    MeetingStatusResponse,
    NicknameResponse,
    RagAskResponse,
    RagSource,
)
from app.services.embedding_service import cosine_similarity, embed_text

DB_PATH = Path(__file__).resolve().parents[2] / ".data" / "jejumate.sqlite3"


class MeetingNotFoundError(Exception):
    pass


class ApplicationNotFoundError(Exception):
    pass


class OwnerMismatchError(Exception):
    pass


class AlreadyProcessedError(Exception):
    pass


class CapacityExceededError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(kind: str, source: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"https://jejumate.local/{kind}/{source}"))


def _new_id() -> str:
    return str(uuid4())


def _new_anonymous_id() -> str:
    return f"anon_{uuid4().hex[:12]}"


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    ensure_database()
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def ensure_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              role TEXT NOT NULL DEFAULT 'user',
              status TEXT NOT NULL DEFAULT 'active',
              anonymous_id TEXT UNIQUE,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS profiles (
              id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL UNIQUE,
              nickname TEXT NOT NULL,
              avatar_key TEXT NOT NULL DEFAULT 'default_01',
              bio TEXT,
              region TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS meetings (
              id TEXT PRIMARY KEY,
              source_key TEXT UNIQUE,
              host_user_id TEXT NOT NULL,
              host_profile_id TEXT NOT NULL,
              category TEXT NOT NULL,
              title TEXT NOT NULL,
              description TEXT,
              place_label TEXT NOT NULL,
              starts_at TEXT NOT NULL,
              ends_at TEXT,
              capacity INTEGER NOT NULL,
              approved_count INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'open',
              visibility TEXT NOT NULL DEFAULT 'public',
              owner_secret TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS meeting_applications (
              id TEXT PRIMARY KEY,
              meeting_id TEXT NOT NULL,
              applicant_user_id TEXT NOT NULL,
              applicant_profile_id TEXT NOT NULL,
              message TEXT,
              status TEXT NOT NULL DEFAULT 'pending',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (meeting_id, applicant_user_id),
              FOREIGN KEY (meeting_id) REFERENCES meetings(id),
              FOREIGN KEY (applicant_user_id) REFERENCES users(id),
              FOREIGN KEY (applicant_profile_id) REFERENCES profiles(id)
            );

            CREATE TABLE IF NOT EXISTS meeting_chat_messages (
              id TEXT PRIMARY KEY,
              meeting_id TEXT NOT NULL,
              sender_user_id TEXT NOT NULL,
              sender_profile_id TEXT NOT NULL,
              sender_nickname TEXT NOT NULL,
              content TEXT NOT NULL,
              created_at TEXT NOT NULL,
              deleted_at TEXT,
              FOREIGN KEY (meeting_id) REFERENCES meetings(id),
              FOREIGN KEY (sender_user_id) REFERENCES users(id),
              FOREIGN KEY (sender_profile_id) REFERENCES profiles(id)
            );

            CREATE TABLE IF NOT EXISTS policies (
              id TEXT PRIMARY KEY,
              external_id TEXT UNIQUE,
              title TEXT NOT NULL,
              summary TEXT NOT NULL,
              target TEXT,
              region TEXT NOT NULL,
              field TEXT NOT NULL,
              application_start_date TEXT,
              application_end_date TEXT,
              status TEXT NOT NULL,
              official_url TEXT NOT NULL,
              last_synced_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rag_documents (
              id TEXT PRIMARY KEY,
              source_type TEXT NOT NULL,
              source_id TEXT NOT NULL,
              title TEXT NOT NULL,
              body TEXT NOT NULL,
              region TEXT,
              category TEXT,
              visibility TEXT NOT NULL DEFAULT 'public',
              is_active INTEGER NOT NULL DEFAULT 1,
              embedding TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rag_sources (
              id TEXT PRIMARY KEY,
              rag_document_id TEXT NOT NULL,
              source_type TEXT NOT NULL,
              title TEXT NOT NULL,
              url TEXT,
              official INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              FOREIGN KEY (rag_document_id) REFERENCES rag_documents(id)
            );

            CREATE TABLE IF NOT EXISTS rag_query_logs (
              id TEXT PRIMARY KEY,
              user_id TEXT,
              anonymous_id TEXT,
              query TEXT NOT NULL,
              intent TEXT,
              used_source_count INTEGER NOT NULL DEFAULT 0,
              confidence TEXT NOT NULL DEFAULT 'medium',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analytics_events (
              id TEXT PRIMARY KEY,
              user_id TEXT,
              anonymous_id TEXT,
              event_name TEXT NOT NULL,
              properties TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL
            );
            """
        )
        try:
            # 이미 생성돼 있던 기존 rag_documents 테이블에 embedding 컬럼을 안전하게 추가
            # (신규 생성 시엔 위 CREATE TABLE에 이미 포함돼 있어 여기서는 no-op).
            connection.execute("ALTER TABLE rag_documents ADD COLUMN embedding TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            # 이미 생성돼 있던 기존 meetings 테이블에 owner_secret 컬럼을 안전하게 추가.
            connection.execute("ALTER TABLE meetings ADD COLUMN owner_secret TEXT")
        except sqlite3.OperationalError:
            pass
        _seed(connection)
        connection.commit()
    finally:
        connection.close()


def _seed(connection: sqlite3.Connection) -> None:
    meeting_count = connection.execute("SELECT COUNT(*) FROM meetings").fetchone()[0]
    if meeting_count:
        return

    now = _now()
    hosts = [
        ("profile_badang", "바당이", "함덕"),
        ("profile_island", "아일랜드", "구좌"),
        ("profile_runner", "러너제주", "이호"),
        ("profile_dolhareubang", "돌하르방", "서귀포"),
        ("profile_oreum", "오름메이트", "애월"),
    ]
    for source, nickname, region in hosts:
        user_id = _stable_id("host-user", source)
        profile_id = _stable_id("host-profile", source)
        connection.execute(
            """
            INSERT OR IGNORE INTO users (id, role, status, anonymous_id, created_at, updated_at)
            VALUES (?, 'user', 'active', ?, ?, ?)
            """,
            (user_id, f"host_{source}", now, now),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO profiles (id, user_id, nickname, avatar_key, region, created_at, updated_at)
            VALUES (?, ?, ?, 'host_default', ?, ?, ?)
            """,
            (profile_id, user_id, nickname, region, now, now),
        )

    meetings = [
        (
            "meeting_lunch_hamdeok",
            "profile_badang",
            "meal",
            "함덕 점심 같이 먹자",
            "함덕 해변 근처에서 점심 먹고 산책까지 이어지는 소규모 밥친구 모임",
            "함덕해수욕장 근처",
            "2026-07-07T11:00:00+09:00",
            "2026-07-07T13:00:00+09:00",
            4,
            2,
            "open",
        ),
        (
            "meeting_work_ocean",
            "profile_island",
            "work",
            "오션뷰 카페 작업팟",
            "노트북 작업, 짧은 회고, 저녁 전 자유 해산으로 운영되는 워케이션 작업 모임",
            "구좌 오션뷰 카페",
            "2026-07-07T14:00:00+09:00",
            "2026-07-07T17:00:00+09:00",
            5,
            1,
            "open",
        ),
        (
            "meeting_run_coast",
            "profile_runner",
            "run",
            "해안도로 5km 러닝",
            "초보 페이스로 함께 달리고 바다 앞에서 쿨다운하는 저녁 러닝",
            "이호테우해변",
            "2026-07-07T17:30:00+09:00",
            "2026-07-07T19:00:00+09:00",
            6,
            3,
            "open",
        ),
        (
            "meeting_taxi_airport",
            "profile_dolhareubang",
            "move",
            "공항 → 서귀포 택시팟",
            "도착 시간이 맞는 참가자끼리 이동비를 나누는 안전 동행 이동팟",
            "제주공항 3번 게이트",
            "2026-07-07T20:00:00+09:00",
            "2026-07-07T21:30:00+09:00",
            4,
            1,
            "open",
        ),
        (
            "meeting_coffee_aewol",
            "profile_oreum",
            "coffee",
            "애월 노을 커피챗",
            "런케이션 기간에 일, 취향, 정책 정보를 편하게 나누는 커피챗",
            "애월 해안도로 카페",
            "2026-07-08T18:00:00+09:00",
            "2026-07-08T19:30:00+09:00",
            5,
            2,
            "open",
        ),
    ]
    for source_key, host_source, category, title, description, place, starts, ends, capacity, approved, status in meetings:
        connection.execute(
            """
            INSERT OR IGNORE INTO meetings (
              id, source_key, host_user_id, host_profile_id, category, title, description,
              place_label, starts_at, ends_at, capacity, approved_count, status, visibility,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'public', ?, ?)
            """,
            (
                _stable_id("meeting", source_key),
                source_key,
                _stable_id("host-user", host_source),
                _stable_id("host-profile", host_source),
                category,
                title,
                description,
                place,
                starts,
                ends,
                capacity,
                approved,
                status,
                now,
                now,
            ),
        )

    policies = [
        (
            "jeju-youth-trip-2026",
            "제주 청년 큐레이션 여행 지원",
            "런케이션 기간 중 체류형 여행 경비를 최대 30만원까지 지원",
            "제주 체류 청년 및 워케이션 참가자",
            "제주",
            "여행",
            "2026-07-01",
            "2026-08-15",
            "open",
            "https://www.jeju.go.kr",
        ),
        (
            "jeju-local-startup-2026",
            "청년 로컬창업 지원사업 참여자 모집",
            "로컬 문제를 해결하는 청년 창업팀에 사업화 자금과 멘토링 제공",
            "만 19~39세 청년 예비창업자",
            "제주",
            "창업",
            "2026-07-05",
            "2026-08-31",
            "open",
            "https://www.jeju.go.kr",
        ),
        (
            "jeju-workation-pass-2026",
            "제주 워케이션 오피스 패스",
            "공유오피스, 회의실, 네트워킹 프로그램을 묶어 할인 지원",
            "제주 체류 근로자 및 프리랜서",
            "제주",
            "일자리",
            "2026-07-10",
            "2026-09-10",
            "open",
            "https://www.jeju.go.kr",
        ),
    ]
    for external_id, title, summary, target, region, field, starts, ends, status, url in policies:
        connection.execute(
            """
            INSERT OR IGNORE INTO policies (
              id, external_id, title, summary, target, region, field,
              application_start_date, application_end_date, status, official_url,
              last_synced_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _stable_id("policy", external_id),
                external_id,
                title,
                summary,
                target,
                region,
                field,
                starts,
                ends,
                status,
                url,
                "2026-07-07T09:00:00+09:00",
                now,
                now,
            ),
        )

    documents = [
        (
            "doc-policy-trip",
            "policy",
            "jeju-youth-trip-2026",
            "제주 청년 큐레이션 여행 지원 핵심 조건",
            "제주 체류 청년은 체류 기간, 참여 프로그램, 증빙 자료 조건을 충족하면 여행 경비 일부를 지원받을 수 있습니다. 신청 마감은 2026년 8월 15일입니다.",
            "정책",
        ),
        (
            "doc-hamdeok-food",
            "curated",
            "hamdeok-food",
            "함덕 점심 추천 동선",
            "함덕 해수욕장 근처 점심은 혼밥보다 2~4명 밥친구 모임으로 예약하면 대기 시간이 짧고, 식사 후 해변 산책까지 이어가기 좋습니다.",
            "장소",
        ),
        (
            "doc-rain-course",
            "curated",
            "rain-course",
            "비 오는 날 제주 코스",
            "비가 오는 날은 오션뷰 카페 작업, 실내 전시, 공유오피스 네트워킹을 묶은 코스가 만족도가 높습니다. 이동팟을 함께 잡으면 비용 부담을 줄일 수 있습니다.",
            "코스",
        ),
    ]
    for doc_source, source_type, source_id, title, body, category in documents:
        document_id = _stable_id("rag-document", doc_source)
        connection.execute(
            """
            INSERT OR IGNORE INTO rag_documents (
              id, source_type, source_id, title, body, region, category, visibility,
              is_active, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, '제주', ?, 'public', 1, ?, ?)
            """,
            (document_id, source_type, source_id, title, body, category, now, now),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO rag_sources (
              id, rag_document_id, source_type, title, url, official, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _stable_id("rag-source", doc_source),
                document_id,
                source_type,
                "제주메이트 검증 데이터" if source_type == "curated" else "제주특별자치도 청년정책",
                "https://www.jeju.go.kr" if source_type == "policy" else "https://jejumate.local/curation",
                1 if source_type == "policy" else 0,
                now,
            ),
        )

    for index in range(1, 277):
        connection.execute(
            """
            INSERT OR IGNORE INTO analytics_events (id, anonymous_id, event_name, properties, created_at)
            VALUES (?, ?, 'app_opened', '{}', ?)
            """,
            (_stable_id("analytics", f"app-opened-{index}"), f"anon_seed_{index:03d}", now),
        )


def _meeting_from_row(row: sqlite3.Row) -> HomeMeeting:
    return HomeMeeting(
        id=row["id"],
        category=row["category"],
        title=row["title"],
        starts_at=row["starts_at"],
        ends_at=row["ends_at"],
        place_label=row["place_label"],
        host=MeetingHost(profile_id=row["host_profile_id"], nickname=row["host_nickname"], badge="host"),
        capacity=row["capacity"],
        approved_count=row["approved_count"],
        status=row["status"],
        cta=MeetingCta(label="신청", enabled=row["status"] == "open", requires_auth=True),
    )


def _policy_from_row(row: sqlite3.Row) -> HomePolicy:
    end_date = date.fromisoformat(row["application_end_date"])
    return HomePolicy(
        id=row["id"],
        title=row["title"],
        summary=row["summary"],
        region=row["region"],
        field=row["field"],
        status=row["status"],
        application_end_date=row["application_end_date"],
        d_day=max((end_date - date.today()).days, 0),
        official_url=row["official_url"],
    )


def get_home_data() -> HomeResponse:
    with _connect() as connection:
        meeting_rows = connection.execute(
            """
            SELECT m.*, p.nickname AS host_nickname
            FROM meetings m
            JOIN profiles p ON p.id = m.host_profile_id
            WHERE m.visibility = 'public' AND m.status IN ('open', 'closing_soon')
            ORDER BY m.starts_at ASC
            LIMIT 6
            """
        ).fetchall()
        policy_rows = connection.execute(
            """
            SELECT *
            FROM policies
            WHERE status IN ('open', 'closing_soon')
            ORDER BY application_end_date ASC
            LIMIT 4
            """
        ).fetchall()
        active_people_count = connection.execute(
            """
            SELECT COUNT(DISTINCT anonymous_id)
            FROM analytics_events
            WHERE event_name = 'app_opened'
            """
        ).fetchone()[0]

    return HomeResponse(
        profile_chip=ProfileChip(label="닉네임", is_set=False),
        privacy_chip=PrivacyChip(label="실명 비공개", is_verified=False),
        meeting_summary=MeetingSummary(open_count=len(meeting_rows)),
        meeting_filters=["전체", "밥친구", "작업", "이동", "커피챗", "러닝"],
        meetings=[_meeting_from_row(row) for row in meeting_rows],
        activity_summary=ActivitySummary(
            active_people_count=active_people_count,
            thumbnail_keys=["hamdeok_beach", "palm_road", "ocean_cafe", "jeju_street"],
        ),
        rag_strip=RagStrip(
            title="제주에서 바로 물어보기",
            subtitle="정책·장소·모임을 근거와 함께",
            suggestions=["오늘 신청 가능한 청년정책", "함덕 점심 추천", "비 오는 날 코스"],
        ),
        policies=[_policy_from_row(row) for row in policy_rows],
    )


def create_or_update_profile(*, nickname: str, anonymous_id: str | None) -> NicknameResponse:
    now = _now()
    next_anonymous_id = anonymous_id or _new_anonymous_id()
    with _connect() as connection:
        user = connection.execute("SELECT * FROM users WHERE anonymous_id = ?", (next_anonymous_id,)).fetchone()
        if user is None:
            user_id = _new_id()
            connection.execute(
                """
                INSERT INTO users (id, role, status, anonymous_id, created_at, updated_at)
                VALUES (?, 'user', 'active', ?, ?, ?)
                """,
                (user_id, next_anonymous_id, now, now),
            )
        else:
            user_id = user["id"]
            connection.execute("UPDATE users SET updated_at = ? WHERE id = ?", (now, user_id))

        profile = connection.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        if profile is None:
            profile_id = _new_id()
            connection.execute(
                """
                INSERT INTO profiles (id, user_id, nickname, avatar_key, created_at, updated_at)
                VALUES (?, ?, ?, 'default_01', ?, ?)
                """,
                (profile_id, user_id, nickname, now, now),
            )
        else:
            profile_id = profile["id"]
            connection.execute(
                "UPDATE profiles SET nickname = ?, updated_at = ? WHERE id = ?",
                (nickname, now, profile_id),
            )

    return NicknameResponse(
        profile_id=profile_id,
        nickname=nickname,
        anonymous_id=next_anonymous_id,
        public_note="다른 참가자에게는 닉네임과 공개 관심사만 표시됩니다.",
        persisted=True,
    )


def create_or_update_application(
    *,
    meeting_id: str,
    nickname: str,
    message: str | None,
    anonymous_id: str | None,
) -> MeetingApplicationResponse:
    profile = create_or_update_profile(nickname=nickname, anonymous_id=anonymous_id)
    now = _now()
    with _connect() as connection:
        meeting = connection.execute(
            "SELECT * FROM meetings WHERE id = ? OR source_key = ?",
            (meeting_id, meeting_id),
        ).fetchone()
        if meeting is None:
            raise ValueError(f"Unknown meeting id: {meeting_id}")

        user = connection.execute("SELECT * FROM users WHERE anonymous_id = ?", (profile.anonymous_id,)).fetchone()
        application = connection.execute(
            """
            SELECT *
            FROM meeting_applications
            WHERE meeting_id = ? AND applicant_user_id = ?
            """,
            (meeting["id"], user["id"]),
        ).fetchone()
        if application is None:
            application_id = _new_id()
            connection.execute(
                """
                INSERT INTO meeting_applications (
                  id, meeting_id, applicant_user_id, applicant_profile_id, message,
                  status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (application_id, meeting["id"], user["id"], profile.profile_id, message, now, now),
            )
        else:
            application_id = application["id"]
            connection.execute(
                """
                UPDATE meeting_applications
                SET applicant_profile_id = ?, message = ?, updated_at = ?
                WHERE id = ?
                """,
                (profile.profile_id, message, now, application_id),
            )

    return MeetingApplicationResponse(
        application_id=application_id,
        meeting_id=meeting["id"],
        status="pending",
        public_alias=profile.nickname,
        privacy_note="실명, 전화번호, 생년월일은 호스트와 참가자에게 공개되지 않습니다.",
        next_step="호스트가 승인하면 앱에서 바로 참여 확정을 안내합니다.",
        persisted=True,
    )


def _resolve_meeting(connection: sqlite3.Connection, meeting_id: str) -> sqlite3.Row:
    meeting = connection.execute(
        "SELECT * FROM meetings WHERE id = ? OR source_key = ?",
        (meeting_id, meeting_id),
    ).fetchone()
    if meeting is None:
        raise MeetingNotFoundError(f"Unknown meeting id: {meeting_id}")
    return meeting


def _generate_owner_secret() -> str:
    """로그인 없이 호스트 권한을 증명할 4자리 관리 코드(jejumate/backend와 동일 방식)."""
    return f"{random.randint(0, 9999):04d}"


def create_meeting(
    *,
    category: str,
    title: str,
    description: str | None,
    place_label: str,
    capacity: int,
    duration_minutes: int,
    nickname: str,
    anonymous_id: str | None,
) -> MeetingCreateResponse:
    """모임 등록. jejumate/backend(POST /posts/party)와 동일하게 등록 즉시 4자리
    관리 코드를 발급하고, 별도 로그인 없이 이 코드로 승인/거절 권한을 증명한다."""
    profile = create_or_update_profile(nickname=nickname, anonymous_id=anonymous_id)
    now_dt = datetime.now(timezone.utc)
    starts_at = now_dt.isoformat()
    ends_at = (now_dt + timedelta(minutes=duration_minutes)).isoformat()
    owner_secret = _generate_owner_secret()
    meeting_id = _new_id()

    with _connect() as connection:
        user = connection.execute("SELECT * FROM users WHERE anonymous_id = ?", (profile.anonymous_id,)).fetchone()
        connection.execute(
            """
            INSERT INTO meetings (
              id, source_key, host_user_id, host_profile_id, category, title, description,
              place_label, starts_at, ends_at, capacity, approved_count, status, visibility,
              owner_secret, created_at, updated_at
            )
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'open', 'public', ?, ?, ?)
            """,
            (
                meeting_id,
                user["id"],
                profile.profile_id,
                category,
                title,
                description,
                place_label,
                starts_at,
                ends_at,
                capacity,
                owner_secret,
                now_dt.isoformat(),
                now_dt.isoformat(),
            ),
        )

    return MeetingCreateResponse(
        meeting_id=meeting_id,
        owner_secret=owner_secret,
        starts_at=starts_at,
        ends_at=ends_at,
        persisted=True,
    )


def get_meeting_status(*, meeting_id: str) -> MeetingStatusResponse:
    """모집 현황 폴링용: 승인 count vs 정원, 마감 여부(jejumate/backend GET /posts/{id}/status와 동일)."""
    with _connect() as connection:
        meeting = _resolve_meeting(connection, meeting_id)
        return MeetingStatusResponse(
            capacity=meeting["capacity"],
            approved_count=meeting["approved_count"],
            is_closed=meeting["status"] not in ("open", "closing_soon"),
        )


def list_meeting_applications(*, meeting_id: str, owner_secret: str | None) -> MeetingApplicationListResponse:
    """관리 코드가 맞으면 전체 상세, 아니면 닉네임만(jejumate/backend GET /posts/{id}/applications와 동일).
    거절된 신청은 목록에서 제외한다."""
    with _connect() as connection:
        meeting = _resolve_meeting(connection, meeting_id)
        rows = connection.execute(
            """
            SELECT ma.*, p.nickname AS applicant_nickname
            FROM meeting_applications ma
            JOIN profiles p ON p.id = ma.applicant_profile_id
            WHERE ma.meeting_id = ? AND ma.status != 'rejected'
            ORDER BY ma.created_at ASC
            """,
            (meeting["id"],),
        ).fetchall()
        authorized = owner_secret is not None and meeting["owner_secret"] == owner_secret

    if authorized:
        items = [
            MeetingApplicationListItem(
                id=row["id"], nickname=row["applicant_nickname"], message=row["message"], status=row["status"]
            )
            for row in rows
        ]
    else:
        items = [MeetingApplicationListItem(nickname=row["applicant_nickname"]) for row in rows]

    return MeetingApplicationListResponse(authorized=authorized, applications=items)


def decide_meeting_application(
    *,
    meeting_id: str,
    application_id: str,
    owner_secret: str,
    decision: str,
) -> MeetingApplicationDecisionResponse:
    """승인/거절(jejumate/backend approve_application/reject_application과 동일 규칙):
    관리 코드 불일치는 OwnerMismatchError, 이미 처리된 신청 재처리는 AlreadyProcessedError,
    승인 시 정원 초과는 CapacityExceededError로 알린다(라우트에서 403/400/409로 매핑)."""
    with _connect() as connection:
        meeting = _resolve_meeting(connection, meeting_id)
        if meeting["owner_secret"] is None or meeting["owner_secret"] != owner_secret:
            raise OwnerMismatchError("관리 코드가 일치하지 않아요")

        application = connection.execute(
            "SELECT * FROM meeting_applications WHERE id = ? AND meeting_id = ?",
            (application_id, meeting["id"]),
        ).fetchone()
        if application is None:
            raise ApplicationNotFoundError(f"Unknown application id: {application_id}")

        if application["status"] != "pending":
            raise AlreadyProcessedError("이미 처리된 신청이에요")

        if decision == "approve":
            if meeting["approved_count"] >= meeting["capacity"]:
                raise CapacityExceededError("정원이 찼어요")
            new_status = "approved"
        else:
            new_status = "rejected"

        now = _now()
        connection.execute(
            "UPDATE meeting_applications SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, application_id),
        )
        if new_status == "approved":
            connection.execute(
                "UPDATE meetings SET approved_count = approved_count + 1, updated_at = ? WHERE id = ?",
                (now, meeting["id"]),
            )

    return MeetingApplicationDecisionResponse(application_id=application_id, meeting_id=meeting["id"], status=new_status)


def _chat_message_from_row(row: sqlite3.Row) -> ChatMessage:
    return ChatMessage(
        id=row["id"],
        meeting_id=row["meeting_id"],
        sender_nickname=row["sender_nickname"],
        content=row["content"],
        created_at=row["created_at"],
    )


def list_chat_messages(*, meeting_id: str) -> ChatMessagesResponse:
    with _connect() as connection:
        meeting = _resolve_meeting(connection, meeting_id)
        rows = connection.execute(
            """
            SELECT *
            FROM meeting_chat_messages
            WHERE meeting_id = ? AND deleted_at IS NULL
            ORDER BY created_at ASC
            LIMIT 80
            """,
            (meeting["id"],),
        ).fetchall()

    return ChatMessagesResponse(
        meeting_id=meeting["id"],
        messages=[_chat_message_from_row(row) for row in rows],
        notice="연락처 공유는 신중하게 해주세요. 불편한 요청은 신고할 수 있어요.",
        persisted=True,
    )


def create_chat_message(
    *,
    meeting_id: str,
    nickname: str,
    content: str,
    anonymous_id: str | None,
) -> ChatMessagesResponse:
    profile = create_or_update_profile(nickname=nickname, anonymous_id=anonymous_id)
    now = _now()
    with _connect() as connection:
        meeting = _resolve_meeting(connection, meeting_id)
        user = connection.execute("SELECT * FROM users WHERE anonymous_id = ?", (profile.anonymous_id,)).fetchone()
        connection.execute(
            """
            INSERT INTO meeting_chat_messages (
              id, meeting_id, sender_user_id, sender_profile_id, sender_nickname,
              content, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (_new_id(), meeting["id"], user["id"], profile.profile_id, profile.nickname, content.strip(), now),
        )
        rows = connection.execute(
            """
            SELECT *
            FROM meeting_chat_messages
            WHERE meeting_id = ? AND deleted_at IS NULL
            ORDER BY created_at ASC
            LIMIT 80
            """,
            (meeting["id"],),
        ).fetchall()

    return ChatMessagesResponse(
        meeting_id=meeting["id"],
        messages=[_chat_message_from_row(row) for row in rows],
        notice="연락처 공유는 신중하게 해주세요. 불편한 요청은 신고할 수 있어요.",
        persisted=True,
    )


def _infer_intent(question: str) -> str:
    if any(keyword in question for keyword in ["정책", "지원", "신청", "마감"]):
        return "policy"
    if any(keyword in question for keyword in ["맛집", "카페", "코스", "비"]):
        return "place"
    if any(keyword in question for keyword in ["모임", "밥", "친구", "동행"]):
        return "meeting"
    return "general"


def answer_rag_question(*, question: str, anonymous_id: str | None) -> RagAskResponse:
    """
    RAG 근거 검색: jejumate/backend(app/search.py)와 동일하게 OpenAI 임베딩 +
    코사인 유사도 threshold 방식을 쓴다. 예전의 "키워드 LIKE 매칭 → 매칭 실패 시
    아무 문서나 반환" 폴백은 제거했다 — threshold 미만이면 근거 없음으로 응답한다.
    """
    normalized = question.strip()
    query_vector = embed_text(normalized)

    with _connect() as connection:
        candidates = connection.execute(
            """
            SELECT *
            FROM rag_documents
            WHERE is_active = 1 AND embedding IS NOT NULL
            """
        ).fetchall()

        scored = [
            (row, cosine_similarity(query_vector, json.loads(row["embedding"])))
            for row in candidates
        ]
        scored = [(row, sim) for row, sim in scored if sim >= settings.rag_similarity_threshold]
        scored.sort(key=lambda item: item[1], reverse=True)
        rows = [row for row, _sim in scored[:3]]

        source_rows = []
        for row in rows:
            source_rows.extend(
                connection.execute(
                    """
                    SELECT *
                    FROM rag_sources
                    WHERE rag_document_id = ?
                    LIMIT 1
                    """,
                    (row["id"],),
                ).fetchall()
            )

        user = None
        if anonymous_id:
            user = connection.execute("SELECT * FROM users WHERE anonymous_id = ?", (anonymous_id,)).fetchone()

        query_log_id = _new_id()
        connection.execute(
            """
            INSERT INTO rag_query_logs (
              id, user_id, anonymous_id, query, intent, used_source_count, confidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'medium', ?)
            """,
            (
                query_log_id,
                user["id"] if user else None,
                anonymous_id,
                normalized,
                _infer_intent(normalized),
                len(source_rows),
                _now(),
            ),
        )

    if not rows:
        answer = "지금 조건에 맞는 유효한 정보를 찾지 못했어요. 다른 질문으로 다시 시도해주세요."
        sources: list[RagSource] = []
    else:
        evidence = " ".join(row["body"] for row in rows)
        answer = (
            f"{normalized} 기준으로는 {rows[0]['title']} 정보를 먼저 확인하는 것이 좋습니다. "
            f"{evidence[:180]}{'...' if len(evidence) > 180 else ''}"
        )
        sources = [
            RagSource(title=row["title"], url=row["url"] or "https://jejumate.local", source_type=row["source_type"])
            for row in source_rows
        ]

    return RagAskResponse(
        answer=answer,
        sources=sources,
        safety_note="정책 신청 조건과 마감일은 공식 링크에서 최종 확인하세요.",
        suggestions=["신청 가능한 청년정책", "함덕 점심 추천", "비 오는 날 코스"],
        query_log_id=query_log_id,
        persisted=True,
    )
