from __future__ import annotations

import json
import math
import os
import random
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.core.config import settings
from app.schemas.home import (
    ActivitySummary,
    HomeMeeting,
    HomeResponse,
    MeetingCta,
    MeetingHost,
    MeetingSummary,
    PrivacyChip,
    ProfileChip,
    RagStrip,
)
from app.schemas.interactions import (
    ApplicantNotification,
    ApplicantNotificationsResponse,
    ApplicationDeleteResponse,
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
from app.schemas.resources import BoardComment, BoardDeleteResponse, BoardPost, BoardReportResponse
from app.services.embedding_service import cosine_similarity, embed_text

DB_PATH = Path(os.environ.get("JEJUMATE_SQLITE_PATH", Path(__file__).resolve().parents[2] / ".data" / "jejumate.sqlite3"))

# DATABASE_URL이 있으면 Postgres(배포), 없으면 SQLite(로컬 개발)를 쓴다. 서버리스
# 배포는 인스턴스마다 /tmp가 독립돼 있어 SQLite로는 인스턴스 간 데이터가 유실됐다 —
# 이게 "신청했는데 처리가 안 된다" 버그의 근본 원인이라 공유 Postgres로 옮긴다.
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

# "NEW" 배지 노출 시간(모임 생성 후). 30분 지나면 자동으로 사라진다.
NEW_MEETING_WINDOW_MINUTES = 30


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


class BoardPostNotFoundError(Exception):
    pass


class BoardOwnerMismatchError(Exception):
    pass


class ApplicantMismatchError(Exception):
    """신청 삭제는 호스트가 아니라 신청자 본인 액션이라 owner_secret이 아니라
    anonymous_id로 본인 확인한다(OwnerMismatchError와 별개)."""


class ChatAccessDeniedError(Exception):
    """모임 채팅은 호스트(owner_secret)와 승인된 신청자(anonymous_id)만 볼 수 있다.
    대기/거절 상태이거나 아예 신청하지 않은 사람은 여기 걸린다."""

    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(kind: str, source: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"https://jejumate.local/{kind}/{source}"))


def _new_id() -> str:
    return str(uuid4())


def _new_anonymous_id() -> str:
    return f"anon_{uuid4().hex[:12]}"


class _PgConnectionWrapper:
    """psycopg2 커넥션을 sqlite3.Connection과 비슷한 인터페이스로 감싼다.
    connection.execute(sql, params)가 커서를 바로 반환하는 sqlite3 관례를 맞추고,
    SQLite 전용 문법(? 플레이스홀더, INSERT OR IGNORE)을 Postgres 문법으로 옮긴다."""

    def __init__(self, raw) -> None:
        self._raw = raw

    def execute(self, sql: str, params: tuple = ()):
        import psycopg2.extras

        translated = sql.replace("?", "%s")
        if "INSERT OR IGNORE INTO" in translated:
            translated = translated.replace("INSERT OR IGNORE INTO", "INSERT INTO").rstrip() + "\nON CONFLICT DO NOTHING"
        cursor = self._raw.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(translated, params)
        return cursor

    def commit(self) -> None:
        self._raw.commit()

    def close(self) -> None:
        self._raw.close()


def _pg_raw_connect() -> _PgConnectionWrapper:
    import psycopg2

    return _PgConnectionWrapper(psycopg2.connect(DATABASE_URL, connect_timeout=10))


def _time_order_expr(column: str) -> str:
    """오프셋이 섞인(+09:00/+00:00) ISO8601 문자열을 실제 시각으로 정규화해서
    정렬하기 위한 표현식. SQLite는 datetime(), Postgres는 timestamptz 캐스팅을 쓴다."""
    return f"({column})::timestamptz" if USE_POSTGRES else f"datetime({column})"


def _split_statements(script: str) -> list[str]:
    return [statement.strip() for statement in script.split(";") if statement.strip()]


_DATABASE_ENSURED = False


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    # ensure_database()는 DDL+시드 확인만으로도 Postgres에서 연결을 새로 열고 십수 번
    # 왕복한다. 매 _connect() 호출마다 반복하면(한 API 요청 안에서도 여러 번 열린다)
    # Supabase 트랜잭션 풀러의 커넥션을 순식간에 소진해 이후 연결이 멈춰버린다.
    # 프로세스(서버리스면 콜드스타트 1회)당 한 번만 실행하면 충분하다.
    global _DATABASE_ENSURED
    if not _DATABASE_ENSURED:
        ensure_database()
        _DATABASE_ENSURED = True
    if USE_POSTGRES:
        connection = _pg_raw_connect()
    else:
        connection = sqlite3.connect(DB_PATH)
        connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


_SCHEMA_SQL = """
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

CREATE TABLE IF NOT EXISTS board_posts (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  author_nickname TEXT NOT NULL,
  author_anonymous_id TEXT,
  deleted_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS board_comments (
  id TEXT PRIMARY KEY,
  post_id TEXT NOT NULL,
  body TEXT NOT NULL,
  author_nickname TEXT NOT NULL,
  author_anonymous_id TEXT,
  deleted_at TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (post_id) REFERENCES board_posts(id)
);

CREATE TABLE IF NOT EXISTS board_reports (
  id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  reporter_anonymous_id TEXT,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
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


def _ensure_database_postgres() -> None:
    """Postgres는 트랜잭션 하나가 에러 하나로 통째로 abort되므로(SQLite처럼
    try/except로 넘어갈 수 없다) ALTER는 전부 IF NOT EXISTS로만 처리한다."""
    connection = _pg_raw_connect()
    try:
        for statement in _split_statements(_SCHEMA_SQL):
            connection.execute(statement)
        for statement in (
            "ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS embedding TEXT",
            "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS owner_secret TEXT",
            "ALTER TABLE board_posts ADD COLUMN IF NOT EXISTS author_anonymous_id TEXT",
            "ALTER TABLE board_posts ADD COLUMN IF NOT EXISTS deleted_at TEXT",
        ):
            connection.execute(statement)
        connection.commit()
        _seed(connection)
        _seed_board_posts(connection)
        connection.commit()
    finally:
        connection.close()


def ensure_database() -> None:
    if USE_POSTGRES:
        _ensure_database_postgres()
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.executescript(_SCHEMA_SQL)
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
        for statement in (
            "ALTER TABLE board_posts ADD COLUMN author_anonymous_id TEXT",
            "ALTER TABLE board_posts ADD COLUMN deleted_at TEXT",
        ):
            try:
                connection.execute(statement)
            except sqlite3.OperationalError:
                pass
        _seed(connection)
        # 게시판 시드는 모임 시드(_seed)의 meeting_count 가드와 무관하게 항상 확인한다 —
        # 이미 모임이 있는 기존 개발 DB에서도 board_posts는 비어 있을 수 있기 때문.
        _seed_board_posts(connection)
        connection.commit()
    finally:
        connection.close()


def _seed_board_posts(connection: sqlite3.Connection) -> None:
    post_count = connection.execute("SELECT COUNT(*) FROM board_posts").fetchone()[0]
    if post_count:
        return

    now = _now()
    board_posts = [
        (
            "board-question-taxi",
            "질문게시판",
            "제주공항 심야 택시 잘 잡히나요?",
            "밤 11시 넘어서 도착하는데 공항에서 시내까지 택시 대기가 긴지 궁금해요.",
            "제주새내기",
        ),
        (
            "board-question-rain",
            "질문게시판",
            "비 오는 날 실내 데이트 코스 추천해주세요",
            "이번 주 내내 비 예보라 실내 위주로 다닐만한 곳 있을까요?",
            "우산요정",
        ),
        (
            "board-market-desk",
            "중고거래",
            "원룸용 접이식 책상 나눔 가격에 팝니다",
            "이호동 근처, 상태 좋아요. 직거래만 가능합니다.",
            "이호주민",
        ),
        (
            "board-market-bike",
            "중고거래",
            "자전거(생활용) 3개월 사용, 저렴하게 드려요",
            "타이어 최근 교체했습니다. 서귀포 인근에서 만나요.",
            "서귀포라이더",
        ),
        (
            "board-share-firstaid",
            "나눔",
            "버물리/연고 여유분 나눔합니다",
            "여행 오면서 넉넉히 챙겨왔는데 남아서 나눔해요.",
            "제주헬퍼",
        ),
    ]
    for post_id, category, title, body, author_nickname in board_posts:
        connection.execute(
            """
            INSERT OR IGNORE INTO board_posts (
              id, category, title, body, author_nickname, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (post_id, category, title, body, author_nickname, now),
        )


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

    documents = [
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
                "제주메이트 검증 데이터",
                "https://jejumate.local/curation",
                0,
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


def _is_popular_meeting(*, capacity: int, approved_count: int) -> bool:
    """인기 배지: 정원 4명 이상인 모임 중 승인 인원이 정원의 과반수 이상일 때만 표시.
    "과반수 이상"의 정확한 기준값은 ceil(capacity/2)로 확정한다(정원 4명이면 2명
    이상, 정원 5명이면 3명 이상 승인돼야 인기)."""
    if capacity < 4:
        return False
    return approved_count >= math.ceil(capacity / 2)


def _is_new_meeting(*, created_at: str, now: datetime) -> bool:
    """NEW 배지: 모임 생성 후 30분 동안만 표시(created_at 기준)."""
    created_dt = datetime.fromisoformat(created_at)
    if created_dt.tzinfo is None:
        created_dt = created_dt.replace(tzinfo=timezone.utc)
    return now - created_dt <= timedelta(minutes=NEW_MEETING_WINDOW_MINUTES)


def _meeting_from_row(row: sqlite3.Row, *, now: datetime | None = None) -> HomeMeeting:
    now = now or datetime.now(timezone.utc)
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
        is_popular=_is_popular_meeting(capacity=row["capacity"], approved_count=row["approved_count"]),
        is_new=_is_new_meeting(created_at=row["created_at"], now=now),
    )


def _board_comment_from_row(row: sqlite3.Row) -> BoardComment:
    return BoardComment(
        id=row["id"],
        post_id=row["post_id"],
        body=row["body"],
        author_nickname=row["author_nickname"],
        created_at=row["created_at"],
    )


def _board_post_from_row(
    row: sqlite3.Row,
    *,
    comments: list[BoardComment] | None = None,
    can_delete: bool = False,
) -> BoardPost:
    return BoardPost(
        id=row["id"],
        category=row["category"],
        title=row["title"],
        body=row["body"],
        author_nickname=row["author_nickname"],
        created_at=row["created_at"],
        comment_count=row["comment_count"] if "comment_count" in row.keys() else 0,
        can_delete=can_delete,
        comments=comments or [],
    )


def list_board_posts() -> list[BoardPost]:
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT p.*, COUNT(c.id) AS comment_count
            FROM board_posts p
            LEFT JOIN board_comments c ON c.post_id = p.id AND c.deleted_at IS NULL
            WHERE p.deleted_at IS NULL
            GROUP BY p.id
            ORDER BY {_time_order_expr('p.created_at')} DESC
            """
        ).fetchall()
    return [_board_post_from_row(row) for row in rows]


def get_board_post(post_id: str, anonymous_id: str | None = None) -> BoardPost:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT p.*, COUNT(c.id) AS comment_count
            FROM board_posts p
            LEFT JOIN board_comments c ON c.post_id = p.id AND c.deleted_at IS NULL
            WHERE p.id = ? AND p.deleted_at IS NULL
            GROUP BY p.id
            """,
            (post_id,),
        ).fetchone()
        comment_rows = connection.execute(
            f"""
            SELECT *
            FROM board_comments
            WHERE post_id = ? AND deleted_at IS NULL
            ORDER BY {_time_order_expr('created_at')} ASC
            """,
            (post_id,),
        ).fetchall()
    if not row:
        raise BoardPostNotFoundError(f"Unknown board post id: {post_id}")
    can_delete = bool(anonymous_id and row["author_anonymous_id"] == anonymous_id)
    return _board_post_from_row(
        row,
        comments=[_board_comment_from_row(comment_row) for comment_row in comment_rows],
        can_delete=can_delete,
    )


def create_board_post(
    *,
    category: str,
    title: str,
    body: str,
    author_nickname: str,
    anonymous_id: str | None,
) -> BoardPost:
    post_id = _new_id()
    created_at = _now()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO board_posts (
              id, category, title, body, author_nickname, author_anonymous_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post_id,
                category.strip(),
                title.strip(),
                body.strip(),
                author_nickname.strip(),
                anonymous_id,
                created_at,
            ),
        )
        connection.commit()
    return get_board_post(post_id, anonymous_id=anonymous_id)


def delete_board_post(*, post_id: str, anonymous_id: str) -> BoardDeleteResponse:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM board_posts WHERE id = ? AND deleted_at IS NULL",
            (post_id,),
        ).fetchone()
        if row is None:
            raise BoardPostNotFoundError(f"Unknown board post id: {post_id}")
        if not anonymous_id or row["author_anonymous_id"] != anonymous_id:
            raise BoardOwnerMismatchError("본인 글만 삭제할 수 있어요")

        now = _now()
        connection.execute("UPDATE board_posts SET deleted_at = ? WHERE id = ?", (now, post_id))
        connection.execute("UPDATE board_comments SET deleted_at = ? WHERE post_id = ?", (now, post_id))

    return BoardDeleteResponse(post_id=post_id, status="deleted")


def create_board_comment(
    *,
    post_id: str,
    body: str,
    author_nickname: str,
    anonymous_id: str | None,
) -> BoardPost:
    comment_id = _new_id()
    created_at = _now()
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM board_posts WHERE id = ? AND deleted_at IS NULL",
            (post_id,),
        ).fetchone()
        if row is None:
            raise BoardPostNotFoundError(f"Unknown board post id: {post_id}")
        connection.execute(
            """
            INSERT INTO board_comments (
              id, post_id, body, author_nickname, author_anonymous_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (comment_id, post_id, body.strip(), author_nickname.strip(), anonymous_id, created_at),
        )

    return get_board_post(post_id, anonymous_id=anonymous_id)


def report_board_target(
    *,
    target_type: str,
    target_id: str,
    reason: str,
    anonymous_id: str | None,
) -> BoardReportResponse:
    if target_type != "post":
        raise ValueError("Unsupported report target")

    with _connect() as connection:
        row = connection.execute(
            "SELECT id FROM board_posts WHERE id = ? AND deleted_at IS NULL",
            (target_id,),
        ).fetchone()
        if row is None:
            raise BoardPostNotFoundError(f"Unknown board post id: {target_id}")
        connection.execute(
            """
            INSERT INTO board_reports (
              id, target_type, target_id, reporter_anonymous_id, reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_new_id(), target_type, target_id, anonymous_id, reason.strip(), _now()),
        )

    return BoardReportResponse(target_type=target_type, target_id=target_id, status="reported")


def _open_meeting_rows(connection: sqlite3.Connection, limit: int | None = None) -> list[sqlite3.Row]:
    """공개+열린 모임 조회. ORDER BY는 문자열이 아니라 datetime()으로 비교한다 —
    시드 데이터는 +09:00, API로 만든 모임은 +00:00 오프셋을 쓰는데 TEXT 컬럼을
    그대로 비교하면 실제 시간 순서와 어긋나는 버그가 있었다(datetime()이 오프셋을
    정규화해서 비교해준다)."""
    limit_clause = "LIMIT ?" if limit else ""
    params: tuple[object, ...] = (limit,) if limit else ()
    return connection.execute(
        f"""
        SELECT m.*, p.nickname AS host_nickname
        FROM meetings m
        JOIN profiles p ON p.id = m.host_profile_id
        WHERE m.visibility = 'public' AND m.status IN ('open', 'closing_soon')
        ORDER BY {_time_order_expr('m.starts_at')} ASC
        {limit_clause}
        """,
        params,
    ).fetchall()


def list_open_meetings() -> list[HomeMeeting]:
    """모임 목록 페이지(GET /api/meetings) 전용. 홈 미리보기(get_home_data, LIMIT 6)와
    달리 열린 모임 전체를 반환한다 — 버그: 목록 페이지가 홈 미리보기 쿼리를 그대로
    재사용해서 열린 모임이 6개를 넘으면 새로 만든 모임이 목록에서 사라졌었다."""
    now = datetime.now(timezone.utc)
    with _connect() as connection:
        rows = _open_meeting_rows(connection)
    return [_meeting_from_row(row, now=now) for row in rows]


def get_home_data() -> HomeResponse:
    now = datetime.now(timezone.utc)
    with _connect() as connection:
        meeting_rows = _open_meeting_rows(connection, limit=6)
        # "지금 제주 어딘가에서 N명이 놀고 있어요": 마감 안 된(활성) 모임의 호스트
        # 1명씩 + 그 모임에 승인된 참가자 수를 전부 더한 실제 값(하드코딩 아님).
        active_people_count = connection.execute(
            """
            SELECT COALESCE(SUM(approved_count), 0) + COUNT(*)
            FROM meetings
            WHERE visibility = 'public' AND status IN ('open', 'closing_soon')
            """
        ).fetchone()[0]

    return HomeResponse(
        profile_chip=ProfileChip(label="닉네임", is_set=False),
        privacy_chip=PrivacyChip(label="실명 비공개", is_verified=False),
        meeting_summary=MeetingSummary(open_count=len(meeting_rows)),
        meeting_filters=["전체", "밥친구", "작업", "이동", "커피챗", "러닝"],
        meetings=[_meeting_from_row(row, now=now) for row in meeting_rows],
        activity_summary=ActivitySummary(
            active_people_count=active_people_count,
            thumbnail_keys=["hamdeok_beach", "palm_road", "ocean_cafe", "jeju_street"],
        ),
        rag_strip=RagStrip(
            title="제주에서 바로 물어보기",
            subtitle="장소·모임을 근거와 함께",
            suggestions=["제주공항 택시팟 있나요?", "함덕 점심 추천", "비 오는 날 코스"],
        ),
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


def get_meeting_by_id(*, meeting_id: str) -> HomeMeeting:
    """내정보 화면의 '내가 만든 모임' 목록 등, 상태(open/closed)와 무관하게 모임 한 건의
    전체 정보가 필요할 때 쓴다. list_open_meetings/get_home_data와 달리 공개+열린
    모임으로 제한하지 않는다."""
    now = datetime.now(timezone.utc)
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT m.*, p.nickname AS host_nickname
            FROM meetings m
            JOIN profiles p ON p.id = m.host_profile_id
            WHERE m.id = ? OR m.source_key = ?
            """,
            (meeting_id, meeting_id),
        ).fetchone()
        if row is None:
            raise MeetingNotFoundError(f"Unknown meeting id: {meeting_id}")
    return _meeting_from_row(row, now=now)


def _has_chat_access(
    connection: sqlite3.Connection,
    meeting: sqlite3.Row,
    *,
    anonymous_id: str | None,
    owner_secret: str | None,
) -> bool:
    if owner_secret and meeting["owner_secret"] == owner_secret:
        return True
    if not anonymous_id:
        return False
    approved = connection.execute(
        """
        SELECT 1
        FROM meeting_applications a
        JOIN users u ON u.id = a.applicant_user_id
        WHERE a.meeting_id = ? AND u.anonymous_id = ? AND a.status = 'approved'
        LIMIT 1
        """,
        (meeting["id"], anonymous_id),
    ).fetchone()
    return approved is not None


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
                application_id=row["id"],
                nickname=row["applicant_nickname"],
                message=row["message"],
                status=row["status"],
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


def list_notifications_for_applicant(*, anonymous_id: str) -> ApplicantNotificationsResponse:
    """내 신청들의 현재 상태를 알림 형태로 보여준다(코덱스 원본 신규 기능 이식).
    호스트 액션이 아니라 신청자 본인 조회라 anonymous_id로만 스코프한다."""
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT a.id AS application_id, a.meeting_id, m.title AS meeting_title,
                   m.starts_at, m.place_label, hp.nickname AS host_nickname,
                   a.status, a.created_at, a.updated_at
            FROM meeting_applications a
            JOIN meetings m ON m.id = a.meeting_id
            JOIN profiles hp ON hp.id = m.host_profile_id
            JOIN users u ON u.id = a.applicant_user_id
            WHERE u.anonymous_id = ?
            ORDER BY a.updated_at DESC
            LIMIT 20
            """,
            (anonymous_id,),
        ).fetchall()

    notifications: list[ApplicantNotification] = []
    for row in rows:
        status = row["status"]
        if status == "approved":
            title, body = "참여 신청이 승인됐어요", f"{row['meeting_title']} 모임에 참여할 수 있어요."
        elif status == "rejected":
            title, body = "참여 신청이 거절됐어요", f"{row['meeting_title']} 신청이 거절됐어요. 다른 모임을 둘러봐 주세요."
        else:
            title, body = "참여 신청이 접수됐어요", f"{row['meeting_title']} 신청을 호스트가 확인하고 있어요."

        notifications.append(
            ApplicantNotification(
                application_id=row["application_id"],
                meeting_id=row["meeting_id"],
                meeting_title=row["meeting_title"],
                starts_at=row["starts_at"],
                place_label=row["place_label"],
                host_nickname=row["host_nickname"],
                status=status,
                title=title,
                body=body,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )

    return ApplicantNotificationsResponse(notifications=notifications)


def delete_my_application(*, meeting_id: str, application_id: str, anonymous_id: str) -> ApplicationDeleteResponse:
    """신청자 본인이 자기 신청을 취소/삭제한다(코덱스 원본 신규 기능 이식, owner_secret이
    아니라 anonymous_id로 본인 확인 — 호스트 액션인 승인/거절과는 별개 권한 모델)."""
    with _connect() as connection:
        meeting = _resolve_meeting(connection, meeting_id)
        application = connection.execute(
            """
            SELECT a.*, u.anonymous_id AS applicant_anonymous_id
            FROM meeting_applications a
            JOIN users u ON u.id = a.applicant_user_id
            WHERE a.id = ? AND a.meeting_id = ?
            """,
            (application_id, meeting["id"]),
        ).fetchone()
        if application is None:
            raise ApplicationNotFoundError(f"Unknown application id: {application_id}")
        if application["applicant_anonymous_id"] != anonymous_id:
            raise ApplicantMismatchError("본인 신청만 삭제할 수 있어요")

        now = _now()
        if application["status"] == "approved":
            connection.execute(
                "UPDATE meetings SET approved_count = MAX(approved_count - 1, 0), updated_at = ? WHERE id = ?",
                (now, meeting["id"]),
            )
        connection.execute("DELETE FROM meeting_applications WHERE id = ?", (application_id,))

    return ApplicationDeleteResponse(application_id=application_id, meeting_id=meeting["id"], status="deleted")


def _chat_message_from_row(row: sqlite3.Row) -> ChatMessage:
    return ChatMessage(
        id=row["id"],
        meeting_id=row["meeting_id"],
        sender_nickname=row["sender_nickname"],
        content=row["content"],
        created_at=row["created_at"],
    )


def list_chat_messages(
    *, meeting_id: str, anonymous_id: str | None = None, owner_secret: str | None = None
) -> ChatMessagesResponse:
    with _connect() as connection:
        meeting = _resolve_meeting(connection, meeting_id)
        if not _has_chat_access(connection, meeting, anonymous_id=anonymous_id, owner_secret=owner_secret):
            raise ChatAccessDeniedError("승인된 참가자와 호스트만 볼 수 있어요")
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
    owner_secret: str | None = None,
) -> ChatMessagesResponse:
    with _connect() as connection:
        meeting = _resolve_meeting(connection, meeting_id)
        if not _has_chat_access(connection, meeting, anonymous_id=anonymous_id, owner_secret=owner_secret):
            raise ChatAccessDeniedError("승인된 참가자와 호스트만 보낼 수 있어요")

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
        safety_note="채팅에서 모은 정보라 최신 상황은 직접 한 번 더 확인해보세요.",
        suggestions=["제주공항 택시팟 있나요?", "함덕 점심 추천", "비 오는 날 코스"],
        query_log_id=query_log_id,
        persisted=True,
    )
