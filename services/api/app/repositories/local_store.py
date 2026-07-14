from __future__ import annotations

import json
import logging
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
    MeetingDeleteResponse,
    MeetingStatusResponse,
    NicknameResponse,
    RagAskResponse,
    RagMapLocation,
    RagSource,
)
from app.schemas.resources import BoardComment, BoardDeleteResponse, BoardPost, BoardReportResponse
from app.services.embedding_service import cosine_similarity, embed_text
from app.services.rag_answer_service import (
    confidence_grade,
    generate_general_answer,
    generate_verified_answer,
)

logger = logging.getLogger(__name__)

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


class SelfApplicationError(Exception):
    """호스트 본인이 자기 파티에 신청하는 것을 막는다(2026-07-10 사용자 리포트:
    셀프 신청이 호스트 승인 목록에도 그대로 떠서 발견)."""


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


_PG_CONNECTION: _PgConnectionWrapper | None = None


def _pg_connection_is_alive(connection: _PgConnectionWrapper) -> bool:
    try:
        return connection._raw.closed == 0
    except Exception:
        return False


def _get_pg_connection() -> _PgConnectionWrapper:
    # 배포 DB(Supabase)가 시드니 리전이라 연결 하나 맺을 때마다(TCP+TLS+인증 핸드셰이크)
    # 왕복 지연이 크다. Vercel 서버리스는 warm 인스턴스가 재사용되는 동안 모듈 전역
    # 상태가 유지되므로, 커넥션을 프로세스 생존 기간 동안 재사용해 요청마다 새로
    # 연결하지 않게 한다(콜드스타트 때만 새로 연결).
    global _PG_CONNECTION
    if _PG_CONNECTION is None or not _pg_connection_is_alive(_PG_CONNECTION):
        _PG_CONNECTION = _pg_raw_connect()
    return _PG_CONNECTION


def _time_order_expr(column: str) -> str:
    """오프셋이 섞인(+09:00/+00:00) ISO8601 문자열을 실제 시각으로 정규화해서
    정렬하기 위한 표현식. SQLite는 datetime(), Postgres는 timestamptz 캐스팅을 쓴다."""
    return f"({column})::timestamptz" if USE_POSTGRES else f"datetime({column})"


def _time_sort_key(value: str) -> datetime:
    """파이썬에서 타임스탬프 문자열을 정렬할 때 쓰는 키. _time_order_expr과 같은 이유로
    문자열 그대로 비교하면 안 된다(+09:00과 +00:00이 섞여 순서가 어긋난다).
    오프셋이 없는 값은 다른 컬럼들과 같은 규약대로 UTC로 본다."""
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


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
        connection = _get_pg_connection()
        try:
            yield connection
            connection.commit()
        except Exception:
            try:
                connection._raw.rollback()
            except Exception:
                pass
            raise
        # 연결을 닫지 않는다 — 다음 요청(같은 warm 인스턴스)에서 재사용한다.
        return
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
  source TEXT NOT NULL DEFAULT 'service',
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
  source TEXT NOT NULL DEFAULT 'service',
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

CREATE TABLE IF NOT EXISTS kakao_upload_messages (
  client_message_hash TEXT PRIMARY KEY,
  room TEXT NOT NULL,
  sender TEXT NOT NULL,
  sent_at_text TEXT NOT NULL,
  content TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  result TEXT,
  created_at TEXT NOT NULL,
  processed_at TEXT
);

CREATE TABLE IF NOT EXISTS ingest_cursors (
  source TEXT PRIMARY KEY,
  last_id INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  last_attempt_at TEXT
);

CREATE TABLE IF NOT EXISTS coldstart_daily_counts (
  day TEXT PRIMARY KEY,
  count INTEGER NOT NULL DEFAULT 0
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
            "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'service'",
            "ALTER TABLE board_posts ADD COLUMN IF NOT EXISTS author_anonymous_id TEXT",
            "ALTER TABLE board_posts ADD COLUMN IF NOT EXISTS deleted_at TEXT",
            "ALTER TABLE board_posts ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'service'",
            "ALTER TABLE ingest_cursors ADD COLUMN IF NOT EXISTS last_attempt_at TEXT",
        ):
            connection.execute(statement)
        connection.commit()
        # RAG 검색을 파이썬 전수 스캔(문서 전체를 매 질문마다 네트워크로 가져와 코사인
        # 유사도 계산)이 아니라 DB 안에서 pgvector로 처리하기 위한 컬럼. 문서가 늘어날수록
        # 전수 스캔은 요청마다 수 초씩 걸리게 된다(2026-07-08 실측: rag_documents 2천건
        # 근처에서 6초). 확장/컬럼 추가는 멱등이라 실패해도 무해하게 롤백한다.
        try:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            connection.execute("ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS embedding_vec vector(1536)")
            connection.commit()
        except Exception:
            connection._raw.rollback()
        try:
            connection.execute("SET maintenance_work_mem = '64MB'")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS rag_documents_embedding_vec_idx "
                "ON rag_documents USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 20)"
            )
            connection.commit()
        except Exception:
            # 인덱스 없이도 LIMIT 3 최근접 검색 자체는 동작한다(문서 수가 적어 브루트포스도
            # 빠름) — 인덱스는 성능 최적화일 뿐 필수 전제조건이 아니다.
            connection._raw.rollback()
        _seed(connection)
        _seed_board_posts(connection)
        _migrate_board_categories(connection)
        _migrate_legacy_kakao_meeting_times(connection)
        connection.commit()
    finally:
        connection.close()


def _migrate_board_categories(connection) -> None:
    """'중고거래'와 '나눔'을 '중고거래/나눔' 한 카테고리로 합친 뒤, 기존에 옛 값으로
    저장된 글들을 새 값으로 통일한다. 통일하지 않으면 옛 글이 새 필터에 하나도 안 잡힌다.

    멱등이라 매 기동마다 돌아도 안전하다(두 번째부터는 대상 행이 0건).
    resource_service.LEGACY_MERGED_CATEGORIES와 같은 값을 쓴다(순환 import를 피해 직접 적음)."""
    connection.execute(
        "UPDATE board_posts SET category = '중고거래/나눔' WHERE category IN ('중고거래', '나눔')"
    )


def _migrate_legacy_kakao_meeting_times(connection) -> None:
    """예전 오픈채팅 파티의 임시 +24시간 일정을 수집 시각 기준으로 한 번만 정리한다.

    예전 행은 원문 채팅 시각을 별도 컬럼에 보관하지 않았으므로 created_at(수집 시각)을
    안전한 대체값으로 쓴다. 새 형식은 starts_at과 created_at이 같은 원문 시각이라 이후
    기동에서는 건드리지 않는다.
    """
    rows = connection.execute(
        "SELECT id, starts_at, created_at FROM meetings WHERE source = 'kakao_chat'"
    ).fetchall()
    for row in rows:
        try:
            starts_at = datetime.fromisoformat(row["starts_at"])
            created_at = datetime.fromisoformat(row["created_at"])
        except (TypeError, ValueError):
            continue
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        starts_at = starts_at.astimezone(timezone.utc)
        created_at = created_at.astimezone(timezone.utc)
        if abs((starts_at - created_at).total_seconds()) < 1:
            continue
        ends_at = created_at + timedelta(hours=settings.kakao_party_delete_after_hours)
        connection.execute(
            "UPDATE meetings SET starts_at = ?, ends_at = ? WHERE id = ?",
            (created_at.isoformat(), ends_at.isoformat(), row["id"]),
        )


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
            "ALTER TABLE meetings ADD COLUMN source TEXT NOT NULL DEFAULT 'service'",
            "ALTER TABLE board_posts ADD COLUMN author_anonymous_id TEXT",
            "ALTER TABLE board_posts ADD COLUMN deleted_at TEXT",
            "ALTER TABLE board_posts ADD COLUMN source TEXT NOT NULL DEFAULT 'service'",
            "ALTER TABLE ingest_cursors ADD COLUMN last_attempt_at TEXT",
        ):
            try:
                connection.execute(statement)
            except sqlite3.OperationalError:
                pass
        _seed(connection)
        # 게시판 시드는 모임 시드(_seed)의 meeting_count 가드와 무관하게 항상 확인한다 —
        # 이미 모임이 있는 기존 개발 DB에서도 board_posts는 비어 있을 수 있기 때문.
        _seed_board_posts(connection)
        _migrate_board_categories(connection)
        _migrate_legacy_kakao_meeting_times(connection)
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
            "중고거래/나눔",
            "원룸용 접이식 책상 나눔 가격에 팝니다",
            "이호동 근처, 상태 좋아요. 직거래만 가능합니다.",
            "이호주민",
        ),
        (
            "board-market-bike",
            "중고거래/나눔",
            "자전거(생활용) 3개월 사용, 저렴하게 드려요",
            "타이어 최근 교체했습니다. 서귀포 인근에서 만나요.",
            "서귀포라이더",
        ),
        (
            "board-share-firstaid",
            "중고거래/나눔",
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
            "함덕 해변 근처에서 점심 먹고 산책까지 이어지는 소규모 밥친구 파티",
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
            "노트북 작업, 짧은 회고, 저녁 전 자유 해산으로 운영되는 워케이션 작업 파티",
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
            "함덕 해수욕장 근처 점심은 혼밥보다 2~4명 밥친구 파티로 예약하면 대기 시간이 짧고, 식사 후 해변 산책까지 이어가기 좋습니다.",
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
    source = row["source"] if "source" in row.keys() else "service"
    is_external = source == "kakao_chat"
    # 오픈채팅 수집 글은 호스트가 없는 외부 글이라 신청/승인 흐름을 붙이지 않는다.
    cta = (
        MeetingCta(label="오픈채팅에서 참여", enabled=False, requires_auth=False)
        if is_external
        else MeetingCta(label="신청", enabled=row["status"] == "open", requires_auth=True)
    )
    return HomeMeeting(
        id=row["id"],
        category=row["category"],
        title=row["title"],
        description=row["description"] if "description" in row.keys() else None,
        starts_at=row["starts_at"],
        ends_at=row["ends_at"],
        place_label=row["place_label"],
        host=MeetingHost(profile_id=row["host_profile_id"], nickname=row["host_nickname"], badge="host"),
        capacity=row["capacity"],
        approved_count=row["approved_count"],
        status=row["status"],
        cta=cta,
        is_popular=False if is_external else _is_popular_meeting(capacity=row["capacity"], approved_count=row["approved_count"]),
        # 카테고리 탭의 새 글 표시에는 오픈채팅 수집 글도 포함한다. 카드 자체는 이미
        # 출처 배지가 있으므로 프론트에서 외부 글의 NEW 문구만 중복 렌더링하지 않는다.
        is_new=_is_new_meeting(created_at=row["created_at"], now=now),
        source=source,
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
        source=row["source"] if "source" in row.keys() else "service",
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
    # 글 저장 트랜잭션이 끝난 뒤 별도 연결로 색인한다(best-effort — 실패해도 글 작성은
    # 이미 성공한 뒤라 영향 없음). RAG 답변이 게시판 글도 근거로 쓰게 하는 목적.
    index_content_as_rag_document(
        source_type="board",
        source_id=post_id,
        title=title.strip(),
        body=body.strip(),
        category=category.strip(),
        source_label="생활게시판 글",
    )
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
        # 삭제된 글이 RAG 근거로 계속 쓰이지 않게 색인도 같이 비활성화한다.
        connection.execute(
            "UPDATE rag_documents SET is_active = 0 WHERE source_type = 'board' AND source_id = ?",
            (post_id,),
        )

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
    """공개+열린 모임 조회. 최신 등록순(created_at DESC)으로 정렬한다 — 새로 올린
    파티가 목록 맨 위에 보여야 등록한 사람이 바로 확인할 수 있다.

    ORDER BY는 문자열이 아니라 datetime()으로 비교한다 — 시드 데이터는 +09:00,
    API로 만든 모임은 +00:00 오프셋을 쓰는데 TEXT 컬럼을 그대로 비교하면 실제
    시간 순서와 어긋나는 버그가 있었다(datetime()이 오프셋을 정규화해서 비교해준다).

    오픈채팅 수집(source='kakao_chat') 모임은 마감 시각이 지나면 즉시 숨긴다.
    호스트가 직접 관리하는 서비스 내 모임(source != 'kakao_chat')은 마감 직후
    바로 사라지면 매정하므로 grace period(설정값)만큼 여유를 두고 숨긴다."""
    limit_clause = "LIMIT ?" if limit else ""
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    grace_cutoff_iso = (now - timedelta(minutes=settings.service_meeting_hide_grace_minutes)).isoformat()
    params: tuple[object, ...] = (now_iso, grace_cutoff_iso, limit) if limit else (now_iso, grace_cutoff_iso)
    return connection.execute(
        f"""
        SELECT m.*, p.nickname AS host_nickname
        FROM meetings m
        JOIN profiles p ON p.id = m.host_profile_id
        WHERE m.visibility = 'public' AND m.status IN ('open', 'closing_soon')
          AND (
            m.ends_at IS NULL
            OR (m.source = 'kakao_chat' AND {_time_order_expr('m.ends_at')} >= {_time_order_expr('?')})
            OR (m.source != 'kakao_chat' AND {_time_order_expr('m.ends_at')} >= {_time_order_expr('?')})
          )
        ORDER BY {_time_order_expr('m.created_at')} DESC
        {limit_clause}
        """,
        params,
    ).fetchall()


def _home_meeting_rows(connection: sqlite3.Connection, *, limit: int, kakao_slots: int) -> list[sqlite3.Row]:
    """홈 미리보기(LIMIT 6)용. 콜드스타트(오픈채팅) 콘텐츠가 서비스 파티에 밀려
    홈에 한 건도 안 보이지 않도록 지정한 수만큼 자리를 예약한다."""
    kakao_slots = min(kakao_slots, limit)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    grace_cutoff_iso = (now - timedelta(minutes=settings.service_meeting_hide_grace_minutes)).isoformat()

    kakao_rows = connection.execute(
        f"""
        SELECT m.*, p.nickname AS host_nickname
        FROM meetings m
        JOIN profiles p ON p.id = m.host_profile_id
        WHERE m.visibility = 'public' AND m.status IN ('open', 'closing_soon') AND m.source = 'kakao_chat'
          AND (m.ends_at IS NULL OR {_time_order_expr('m.ends_at')} >= {_time_order_expr('?')})
        ORDER BY {_time_order_expr('m.created_at')} DESC
        LIMIT ?
        """,
        (now_iso, kakao_slots),
    ).fetchall()

    service_limit = limit - len(kakao_rows)
    # 서비스 파티도 마감+grace 지난 것은 홈 미리보기에서 숨긴다(_open_meeting_rows와 동일 규칙).
    service_rows = connection.execute(
        f"""
        SELECT m.*, p.nickname AS host_nickname
        FROM meetings m
        JOIN profiles p ON p.id = m.host_profile_id
        WHERE m.visibility = 'public' AND m.status IN ('open', 'closing_soon') AND m.source != 'kakao_chat'
          AND (m.ends_at IS NULL OR {_time_order_expr('m.ends_at')} >= {_time_order_expr('?')})
        ORDER BY {_time_order_expr('m.created_at')} DESC
        LIMIT ?
        """,
        (grace_cutoff_iso, service_limit),
    ).fetchall()

    # 합친 뒤에도 최신 등록순을 유지한다. 여기서 starts_at으로 다시 정렬하면 위 두
    # 쿼리의 created_at DESC가 무의미해진다(선택되는 행만 바뀌고 표시 순서는 그대로).
    combined = list(service_rows) + list(kakao_rows)
    combined.sort(key=lambda row: _time_sort_key(row["created_at"]), reverse=True)
    return combined[:limit]


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
        meeting_rows = _home_meeting_rows(connection, limit=6, kakao_slots=2)
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
        meeting_filters=["전체", "이동", "밥친구", "러닝", "기타", "퀵매치", "오픈채팅"],
        meetings=[_meeting_from_row(row, now=now) for row in meeting_rows],
        activity_summary=ActivitySummary(
            active_people_count=active_people_count,
            thumbnail_keys=["hamdeok_beach", "palm_road", "ocean_cafe", "jeju_street"],
        ),
        rag_strip=RagStrip(
            title="제주에서 바로 물어보기",
            subtitle="장소·파티를 근거와 함께",
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
        if user["id"] == meeting["host_user_id"]:
            raise SelfApplicationError("본인이 만든 파티에는 신청할 수 없어요")

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


_KST = timezone(timedelta(hours=9))


def _local_kst_to_utc_iso(value: str) -> str:
    """<input type="datetime-local">가 주는 오프셋 없는 문자열(예: "2026-07-10T14:30")을
    사용자가 실제로 보고 고른 한국 시간(Asia/Seoul)으로 해석해 UTC ISO로 변환한다.
    DB의 다른 타임스탬프들과 동일하게 UTC로 저장해야 _time_order_expr 정렬이 맞는다."""
    naive = datetime.fromisoformat(value)
    return naive.replace(tzinfo=_KST).astimezone(timezone.utc).isoformat()


def _kakao_source_time_to_utc(value: str) -> datetime:
    """카카오 원문 입력 시각을 UTC로 정규화한다.

    Windows 내보내기(sent_at_text)는 오프셋 없는 한국시간이고, 외부 채팅 API는
    오프셋이 포함된 ISO 문자열을 줄 수 있어 두 형식을 모두 처리한다.
    """
    try:
        source_dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if source_dt.tzinfo is None:
        source_dt = source_dt.replace(tzinfo=_KST)
    return source_dt.astimezone(timezone.utc)


def create_meeting(
    *,
    category: str,
    title: str,
    description: str | None,
    place_label: str,
    capacity: int,
    starts_at: str,
    ends_at: str,
    nickname: str,
    anonymous_id: str | None,
) -> MeetingCreateResponse:
    """모임 등록. jejumate/backend(POST /posts/party)와 동일하게 등록 즉시 4자리
    관리 코드를 발급하고, 별도 로그인 없이 이 코드로 승인/거절 권한을 증명한다.
    starts_at/ends_at은 사용자가 직접 고른 시작·마감 시각(로컬/KST)이다."""
    profile = create_or_update_profile(nickname=nickname, anonymous_id=anonymous_id)
    now_dt = datetime.now(timezone.utc)
    starts_at = _local_kst_to_utc_iso(starts_at)
    ends_at = _local_kst_to_utc_iso(ends_at)
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

    # 모임 저장 트랜잭션이 끝난 뒤 별도 연결로 색인한다(best-effort). 설명이 없으면
    # 제목만으로, 장소는 항상 같이 넣어서 "OO에서 하는 모임 있나요" 류 질문에도 걸리게 한다.
    meeting_body = "\n".join(part for part in (description, f"장소: {place_label}") if part) or title
    index_content_as_rag_document(
        source_type="meeting",
        source_id=meeting_id,
        title=title,
        body=meeting_body,
        category=category,
        source_label="모임 등록",
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


def delete_meeting(*, meeting_id: str, owner_secret: str) -> MeetingDeleteResponse:
    """호스트가 파티를 해산한다. 관리 코드 불일치는 OwnerMismatchError(라우트에서 403).

    cleanup_expired_parties와 동일한 cascade 순서로 채팅·신청까지 지워 고아 레코드를
    막는다. users/profiles는 건드리지 않는다 — 영구 보존 방침."""
    with _connect() as connection:
        meeting = _resolve_meeting(connection, meeting_id)
        if meeting["owner_secret"] is None or meeting["owner_secret"] != owner_secret:
            raise OwnerMismatchError("관리 코드가 일치하지 않아요")

        # source_key로 조회됐을 수도 있으므로 실제 행의 id로 지운다.
        resolved_id = meeting["id"]
        connection.execute("DELETE FROM meeting_chat_messages WHERE meeting_id = ?", (resolved_id,))
        connection.execute("DELETE FROM meeting_applications WHERE meeting_id = ?", (resolved_id,))
        connection.execute("DELETE FROM meetings WHERE id = ?", (resolved_id,))
        # 해산된 모임이 RAG 근거로 계속 쓰이지 않게 색인도 같이 비활성화한다.
        connection.execute(
            "UPDATE rag_documents SET is_active = 0 WHERE source_type = 'meeting' AND source_id = ?",
            (resolved_id,),
        )

    return MeetingDeleteResponse(meeting_id=resolved_id, status="deleted")


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
            title, body = "참여 신청이 승인됐어요", f"{row['meeting_title']} 파티에 참여할 수 있어요."
        elif status == "rejected":
            title, body = "참여 신청이 거절됐어요", f"{row['meeting_title']} 신청이 거절됐어요. 다른 파티를 둘러봐 주세요."
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
            # 0 밑으로 안 내려가게 클램프. Postgres에서 MAX는 집계함수라 두 인자를
            # 못 받는다(GREATEST를 써야 함) — SQLite는 MAX(a,b) 스칼라라 분기한다.
            clamp = "GREATEST" if USE_POSTGRES else "MAX"
            connection.execute(
                f"UPDATE meetings SET approved_count = {clamp}(approved_count - 1, 0), updated_at = ? WHERE id = ?",
                (now, meeting["id"]),
            )
        connection.execute("DELETE FROM meeting_applications WHERE id = ?", (application_id,))

    return ApplicationDeleteResponse(application_id=application_id, meeting_id=meeting["id"], status="deleted")


def _chat_message_from_row(row: sqlite3.Row) -> ChatMessage:
    return ChatMessage(
        id=row["id"],
        meeting_id=row["meeting_id"],
        sender_nickname=row["sender_nickname"],
        sender_anonymous_id=row["sender_anonymous_id"],
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
            SELECT m.*, u.anonymous_id AS sender_anonymous_id
            FROM meeting_chat_messages m
            JOIN users u ON u.id = m.sender_user_id
            WHERE m.meeting_id = ? AND m.deleted_at IS NULL
            ORDER BY m.created_at ASC
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
            SELECT m.*, u.anonymous_id AS sender_anonymous_id
            FROM meeting_chat_messages m
            JOIN users u ON u.id = m.sender_user_id
            WHERE m.meeting_id = ? AND m.deleted_at IS NULL
            ORDER BY m.created_at ASC
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


_OFFICIAL_INFORMATION_KEYWORDS = (
    "학과",
    "학부",
    "전공",
    "단과대",
    "수의대",
    "수의과",
    "수의학",
    "의대",
    "의과대",
    "약대",
    "약학대",
    "간호대",
    "장학",
    "등록금",
    "휴학",
    "복학",
    "전과",
    "재입학",
    "수강신청",
    "학사일정",
    "증명서",
    "교육과정",
    "복수전공",
    "기숙사",
    "생활관",
    "주차",
    "차량",
    "자동차",
    "정기이용",
    "교통상황실",
    "신청",
    "등록",
    "해지",
    "납부",
    "학적",
    "성적",
    "졸업",
    "교환학생",
)

_COMMUNITY_INFORMATION_KEYWORDS = (
    "택시",
    "택시팟",
    "구해",
    "같이",
    "맛집",
    "카페",
    "동행",
    "파티",
    "모임",
    "밥친구",
    "세탁기",
    "건조기",
    "게시글",
)

_DYNAMIC_OFFICIAL_SEARCH_KEYWORDS = (
    "신청",
    "등록",
    "해지",
    "납부",
    "기간",
    "마감",
    "언제",
    "서류",
    "절차",
    "모집",
    "공지",
    "주차",
    "차량",
)


_OFFICIAL_SOURCE_ALIASES = (
    (
        ("수의대", "수의과", "수의학"),
        ("campus-map-veterinary-college", "veterinary-college", "organization-2026"),
    ),
    (
        ("학과", "학부", "전공", "단과대", "의대", "의과대", "약대", "약학대", "간호대"),
        ("colleges-departments-2026", "organization-2026"),
    ),
    (("학사일정", "수강신청"), ("academic-calendar-2026",)),
    (("휴학",), ("leave-of-absence",)),
    (("복학",), ("return-to-school",)),
    (("전과", "재입학"), ("change-major-readmission",)),
    (("복수전공", "교육과정"), ("multiple-majors",)),
    (("장학",), ("scholarships-2026",)),
    (("등록금",), ("tuition-payment",)),
    (("증명서",), ("certificates",)),
    (("기숙사", "생활관"), ("student-dormitory",)),
)

_CAMPUS_MAP_LOCATIONS = {
    "campus-map-veterinary-college": RagMapLocation(
        title="제주대학교 수의과대학",
        lat=33.4520059,
        lng=126.5585883,
        description="부설 동물병원에서 북서쪽 약 76m",
        source_url="https://www.jejunu.ac.kr/schoolinfo/campinfo/campusmap.htm",
    ),
}

_LOCATION_QUESTION_KEYWORDS = ("어디", "위치", "찾아가", "가는길", "근처", "좌표", "지도")


def _official_source_ids_for_question(question: str) -> tuple[str, ...]:
    """명시적인 대학 주제는 관련 공식 문서에만 결정적으로 연결한다."""
    normalized = question.replace(" ", "").lower()
    source_ids: list[str] = []
    for keywords, mapped_source_ids in _OFFICIAL_SOURCE_ALIASES:
        if any(keyword in normalized for keyword in keywords):
            for source_id in mapped_source_ids:
                if source_id not in source_ids:
                    source_ids.append(source_id)
    return tuple(source_ids)


def _should_search_jejunu_official(question: str) -> bool:
    """대학이 정하는 사실은 공식 문서에서, 학생 활동은 커뮤니티에서 찾는다."""
    normalized = question.replace(" ", "").lower()
    if any(keyword in normalized for keyword in _COMMUNITY_INFORMATION_KEYWORDS):
        return False
    if any(keyword in normalized for keyword in _OFFICIAL_INFORMATION_KEYWORDS):
        return True
    return "제주대학교" in normalized or "제주대" in normalized


def _should_refresh_jejunu_official_search(question: str) -> bool:
    """변동 가능성이 높거나 정적 문서 별칭이 없는 공식 질문은 통합검색도 조회한다."""
    normalized = question.replace(" ", "").lower()
    return (
        any(keyword in normalized for keyword in _DYNAMIC_OFFICIAL_SEARCH_KEYWORDS)
        or not _official_source_ids_for_question(question)
    )


def answer_rag_question(*, question: str, anonymous_id: str | None) -> RagAskResponse:
    """
    RAG 근거 검색: jejumate/backend(app/search.py)와 동일하게 OpenAI 임베딩 +
    코사인 유사도 threshold 방식을 쓴다. 예전의 "키워드 LIKE 매칭 → 매칭 실패 시
    아무 문서나 반환" 폴백은 제거했다 — threshold 미만이면 근거 없음으로 응답한다.
    """
    normalized = question.strip()
    compact_question = normalized.replace(" ", "")
    asks_for_location = any(keyword in compact_question for keyword in _LOCATION_QUESTION_KEYWORDS)
    official_only = _should_search_jejunu_official(normalized)
    if official_only and _should_refresh_jejunu_official_search(normalized):
        try:
            from app.services.jejunu_portal_search import (
                build_official_search_query,
                search_and_ingest_jejunu_official,
            )

            official_search_query = build_official_search_query(normalized)
            if official_search_query:
                search_and_ingest_jejunu_official(official_search_query)
        except Exception:
            # 공식 사이트가 잠시 느리거나 점검 중이어도 기존 RAG 답변은 계속 제공한다.
            logger.warning("제주대학교 통합검색 증분 색인 실패", exc_info=True)

    query_vector = embed_text(normalized)
    source_filter = (
        " AND source_type = 'jejunu_official'"
        if official_only
        else " AND source_type != 'jejunu_official'"
    )

    with _connect() as connection:
        if USE_POSTGRES:
            # rag_documents 전체(임베딩 포함)를 매 질문마다 네트워크로 통째로 가져와
            # 파이썬에서 코사인 유사도를 계산하면, 문서가 늘어날수록(현재 2천건 근처)
            # 요청마다 수 초가 걸린다. pgvector로 DB 안에서 최근접 3건만 계산해서
            # 그 3건만 네트워크로 받는다(embedding_vec + ivfflat 인덱스, 백필 완료).
            vec_literal = "[" + ",".join(str(x) for x in query_vector) + "]"
            # 공식 문서는 소수라 ivfflat 근사 인덱스가 먼저 후보를 줄인 뒤 필터하면
            # 결과가 빠질 수 있다. + 0으로 인덱스 정렬을 피하고 공식 문서 안에서만
            # 정확 검색한다. 다수인 커뮤니티 문서는 기존 근사 인덱스를 계속 쓴다.
            order_expression = (
                "(embedding_vec <=> ?::vector) + 0"
                if official_only
                else "embedding_vec <=> ?::vector"
            )
            candidates = connection.execute(
                f"""
                SELECT *, 1 - (embedding_vec <=> ?::vector) AS similarity
                FROM rag_documents
                WHERE is_active = 1 AND embedding_vec IS NOT NULL{source_filter}
                ORDER BY {order_expression}
                LIMIT 3
                """,
                (vec_literal, vec_literal),
            ).fetchall()
            rows = [row for row in candidates if row["similarity"] >= settings.rag_similarity_threshold]
        else:
            candidates = connection.execute(
                f"""
                SELECT *
                FROM rag_documents
                WHERE is_active = 1 AND embedding IS NOT NULL{source_filter}
                """
            ).fetchall()

            scored = [
                (row, cosine_similarity(query_vector, json.loads(row["embedding"])))
                for row in candidates
            ]
            scored = [(row, sim) for row, sim in scored if sim >= settings.rag_similarity_threshold]
            scored.sort(key=lambda item: item[1], reverse=True)
            rows = [row for row, _sim in scored[:3]]

        # "수의대는 어디에 있어?"처럼 짧은 질문은 주제가 명확해도 임베딩
        # 유사도가 전역 threshold 아래로 내려갈 수 있다. 명시적인 공식 주제는
        # 미리 지정한 관련 문서만 우선 포함해 일반 지식 폴백의 오답을 막는다.
        if official_only:
            targeted_source_ids = _official_source_ids_for_question(normalized)
            if targeted_source_ids:
                placeholders = ", ".join("?" for _ in targeted_source_ids)
                targeted_rows = connection.execute(
                    f"""
                    SELECT *
                    FROM rag_documents
                    WHERE is_active = 1
                      AND source_type = 'jejunu_official'
                      AND source_id IN ({placeholders})
                    """,
                    targeted_source_ids,
                ).fetchall()
                targeted_by_source_id = {row["source_id"]: row for row in targeted_rows}
                prioritized_rows = [
                    targeted_by_source_id[source_id]
                    for source_id in targeted_source_ids
                    if source_id in targeted_by_source_id
                ]
                targeted_ids = {row["id"] for row in prioritized_rows}
                rows = (prioritized_rows + [row for row in rows if row["id"] not in targeted_ids])[:3]

        # 근거 문서와 출처를 같은 인덱스로 유지한다. 출처가 없는 문서가 하나 섞여도
        # 뒤 문서의 URL이 잘못 연결되지 않게 각 문서당 정확히 한 칸을 둔다.
        source_rows = []
        for row in rows:
            source_rows.append(
                connection.execute(
                    """
                    SELECT *
                    FROM rag_sources
                    WHERE rag_document_id = ?
                    LIMIT 1
                    """,
                    (row["id"],),
                ).fetchone()
            )

        user = None
        if anonymous_id:
            user = connection.execute("SELECT * FROM users WHERE anonymous_id = ?", (anonymous_id,)).fetchone()

        query_log_id = _new_id()
        confidence_for_log = "none" if not rows else "medium"
        connection.execute(
            """
            INSERT INTO rag_query_logs (
              id, user_id, anonymous_id, query, intent, used_source_count, confidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query_log_id,
                user["id"] if user else None,
                anonymous_id,
                normalized,
                _infer_intent(normalized),
                sum(1 for source in source_rows if source is not None),
                confidence_for_log,
                _now(),
            ),
        )

    map_location: RagMapLocation | None = None

    if not rows:
        # threshold 미달: 근거는 없지만, 정적 회피 문구 대신 LLM의 일반 지식으로 답한다.
        # confidence_grade는 여전히 "none"(근거 0개인 사실은 그대로).
        answer = generate_general_answer(question=normalized)
        sources: list[RagSource] = []
        confidence = "none"
        verified_count = 0
        total_count = 0
        answer_source = "general_knowledge"
    else:
        documents = [
            {
                "index": i,
                "title": row["title"],
                "body": row["body"],
                "source_label": (
                    "제주대학교 공식"
                    if row["source_type"] == "jejunu_official"
                    else "학생 커뮤니티"
                ),
                "url": source_rows[i]["url"] if source_rows[i] is not None else None,
            }
            for i, row in enumerate(rows)
        ]
        result = generate_verified_answer(question=normalized, documents=documents)
        supported_indexes = [i for i, supported in enumerate(result.supports) if supported]

        if not supported_indexes:
            # 유사도만 통과한 무관 문서를 출처처럼 보여주지 않는다. 검증을 하나도
            # 통과하지 못했으면 공식/커뮤니티 근거가 없는 질문과 동일하게 처리한다.
            answer = generate_general_answer(question=normalized)
            confidence = "none"
            verified_count = 0
            total_count = 0
            answer_source = "general_knowledge"
            sources = []
        else:
            answer = result.answer
            confidence = confidence_grade(result.supports)
            verified_count = len(supported_indexes)
            total_count = len(result.supports)
            supported_source_types = {
                rows[i]["source_type"] for i in supported_indexes
            }
            answer_source = (
                "official"
                if supported_source_types == {"jejunu_official"}
                else "community"
            )
            sources = [
                RagSource(
                    title=source_rows[i]["title"] or rows[i]["title"],
                    url=source_rows[i]["url"] or "https://jejumate.local",
                    source_type=source_rows[i]["source_type"],
                    supports_answer=True,
                )
                for i in supported_indexes
                if source_rows[i] is not None
            ]
            if asks_for_location:
                map_location = next(
                    (
                        _CAMPUS_MAP_LOCATIONS[rows[i]["source_id"]]
                        for i in supported_indexes
                        if rows[i]["source_id"] in _CAMPUS_MAP_LOCATIONS
                    ),
                    None,
                )
        # 실제 검증 결과로 로그의 confidence를 갱신(위 INSERT 시점엔 LLM 호출 전이라 알 수 없었음).
        with _connect() as connection:
            connection.execute(
                "UPDATE rag_query_logs SET confidence = ? WHERE id = ?",
                (confidence, query_log_id),
            )

    if answer_source == "official":
        safety_note = "제주대학교 공식 홈페이지 기준이며, 변경될 수 있는 일정·기준은 연결된 원문도 확인해주세요."
        suggestions = ["제주대 학과 목록 알려줘", "휴학 신청은 어떻게 해?", "교내 장학금 알려줘"]
    elif answer_source == "community":
        safety_note = "채팅에서 모은 정보라 최신 상황은 직접 한 번 더 확인해보세요."
        suggestions = ["제주공항 택시팟 있나요?", "함덕 점심 추천", "비 오는 날 코스"]
    else:
        safety_note = "공식 홈페이지나 커뮤니티 근거 없이 일반 지식으로 답했어요. 중요한 내용은 원문을 확인해주세요."
        suggestions = ["제주대 학과 목록 알려줘", "제주공항 택시팟 있나요?", "비 오는 날 코스"]

    return RagAskResponse(
        answer=answer,
        sources=sources,
        safety_note=safety_note,
        suggestions=suggestions,
        query_log_id=query_log_id,
        persisted=True,
        confidence_grade=confidence,
        verified_source_count=verified_count,
        total_source_count=total_count,
        answer_source=answer_source,
        map_location=map_location,
    )


def cleanup_expired_parties() -> int:
    """만료된 파티를 DB에서 실제로 삭제한다(목록 숨김과 달리 복구 불가). 규칙은 두 갈래다:

    - 사용자 파티(source != 'kakao_chat'): 마감(ends_at) 후 party_delete_after_days(기본 2일)
    - 카톡 수집 파티(source = 'kakao_chat'): 원문 채팅 입력 시각(created_at) 후
      kakao_party_delete_after_hours(기본 4시간). 콜드스타트용 임시 콘텐츠라 원문 시각을
      기준으로 짧게 정리한다.

    연관 신청·채팅도 함께 지워 고아 레코드를 막는다. users/profiles(닉네임·익명ID),
    생활게시판 글(board_posts), RAG 문서(rag_documents)는 건드리지 않는다 — 보존 방침.
    삭제한 파티 수를 반환한다."""
    now = datetime.now(timezone.utc)
    service_cutoff_iso = (now - timedelta(days=settings.party_delete_after_days)).isoformat()
    kakao_cutoff_iso = (now - timedelta(hours=settings.kakao_party_delete_after_hours)).isoformat()

    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id FROM meetings
            WHERE (
                source != 'kakao_chat'
                AND ends_at IS NOT NULL
                AND {_time_order_expr('ends_at')} < {_time_order_expr('?')}
              )
               OR (
                source = 'kakao_chat'
                AND {_time_order_expr('created_at')} < {_time_order_expr('?')}
              )
            """,
            (service_cutoff_iso, kakao_cutoff_iso),
        ).fetchall()
        meeting_ids = [row["id"] for row in rows]
        for meeting_id in meeting_ids:
            connection.execute("DELETE FROM meeting_chat_messages WHERE meeting_id = ?", (meeting_id,))
            connection.execute("DELETE FROM meeting_applications WHERE meeting_id = ?", (meeting_id,))
            connection.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    return len(meeting_ids)


def get_ingest_cursor(source: str) -> int:
    """카톡 실시간 수집 증분 커서(마지막으로 처리한 항목 id). 없으면 0(처음부터)."""
    with _connect() as connection:
        row = connection.execute(
            "SELECT last_id FROM ingest_cursors WHERE source = ?", (source,)
        ).fetchone()
    return row["last_id"] if row else 0


def set_ingest_cursor(source: str, last_id: int) -> None:
    """커서를 전진시킨다. 항상 MAX로 갱신해 단조 증가만 허용한다 — 피기백 호출이
    겹쳐서(동시 요청) ingest_new_messages()가 두 번 돌아도, 늦게 끝난 호출이 더 작은
    max_id로 커서를 되돌리는 회귀를 막는다."""
    now = _now()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO ingest_cursors (source, last_id, updated_at, last_attempt_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
              last_id = CASE
                WHEN excluded.last_id > ingest_cursors.last_id THEN excluded.last_id
                ELSE ingest_cursors.last_id
              END,
              updated_at = excluded.updated_at
            """,
            (source, last_id, now, now),
        )


def try_claim_kakao_ingest_attempt(source: str, min_interval_seconds: int) -> bool:
    """마지막 시도로부터 min_interval_seconds가 지났으면 '이번 시도는 내가 맡는다'고
    원자적으로 표시하고 True를 반환한다. 아직 간격이 안 지났거나 동시 요청 중 다른
    쪽이 먼저 선점했으면 False.

    별도 락 없이 안전한 이유: UPDATE ... WHERE ...는 행 단위로 원자적이다. 두 요청이
    동시에 들어와도 DB가 한쪽을 먼저 커밋시키고, 뒤따르는 요청은 WHERE 조건(마지막
    시도 시각)을 다시 평가하는 시점엔 이미 방금 갱신된 값을 보게 되어 조건을 만족하지
    못한다 — 즉 최대 하나의 호출만 True를 받는다."""
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    threshold_str = (now - timedelta(seconds=min_interval_seconds)).isoformat()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO ingest_cursors (source, last_id, updated_at, last_attempt_at)
            VALUES (?, 0, ?, NULL)
            ON CONFLICT(source) DO NOTHING
            """,
            (source, now_str),
        )
        cursor = connection.execute(
            """
            UPDATE ingest_cursors
            SET last_attempt_at = ?
            WHERE source = ? AND (last_attempt_at IS NULL OR last_attempt_at <= ?)
            """,
            (now_str, source, threshold_str),
        )
        claimed = cursor.rowcount > 0
    return claimed


def index_content_as_rag_document(
    *,
    source_type: str,
    source_id: str,
    title: str,
    body: str,
    category: str | None,
    source_label: str,
) -> bool:
    """게시판 글/모임 등 서비스 내 콘텐츠를 RAG 근거 문서로 색인한다.
    add_kakao_rag_document와 같은 컨벤션(카톡과는 source_type만 다름)을 따르되,
    여기서는 임베딩 API 실패를 이 함수 안에서 삼킨다 — 글/모임 작성 자체가 색인
    실패 때문에 같이 실패하면 안 되기 때문이다(best-effort). 성공 여부만 bool로
    돌려주고, 실패는 warning으로 남겨 조용히 묻히지 않게 한다."""
    try:
        embedding = embed_text(f"{title}\n{body}".strip())
    except Exception:
        logger.warning(
            "RAG 색인용 임베딩 실패(best-effort, 원본 작성은 계속 성공 처리) — "
            "source_type=%s source_id=%s",
            source_type,
            source_id,
            exc_info=True,
        )
        return False

    document_id = _stable_id("rag-document", f"{source_type}-{source_id}")
    now = _now()
    with _connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO rag_documents (
              id, source_type, source_id, title, body, region, category, visibility,
              is_active, embedding, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, '제주', ?, 'public', 1, ?, ?, ?)
            """,
            (document_id, source_type, source_id, title, body, category, json.dumps(embedding), now, now),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO rag_sources (
              id, rag_document_id, source_type, title, url, official, created_at
            )
            VALUES (?, ?, ?, ?, NULL, 0, ?)
            """,
            (_stable_id("rag-source", f"{source_type}-{source_id}"), document_id, source_type, source_label, now),
        )
        if USE_POSTGRES:
            # pgvector 컬럼도 같이 채운다 — answer_rag_question의 벡터 검색이 이걸 쓴다.
            vec_literal = "[" + ",".join(str(x) for x in embedding) + "]"
            connection.execute(
                "UPDATE rag_documents SET embedding_vec = ?::vector WHERE id = ?",
                (vec_literal, document_id),
            )
    return True


def add_kakao_rag_document(*, item_id: int, content: str, embedding: list[float]) -> None:
    """카톡 실시간 수집 메시지 1건을 RAG 근거 문서로 적재한다. 이미 있으면(재실행 등) 무시.
    기존 scripts/seed_rag_embeddings.py의 카톡 시드(source_type='kakao_chat')와 같은
    관례를 따른다."""
    document_id = _stable_id("rag-document", f"kakao-live-{item_id}")
    title = content if len(content) <= 40 else f"{content[:40]}…"
    now = _now()
    with _connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO rag_documents (
              id, source_type, source_id, title, body, region, category, visibility,
              is_active, embedding, created_at, updated_at
            )
            VALUES (?, 'kakao_chat', ?, ?, ?, '제주', '카톡', 'public', 1, ?, ?, ?)
            """,
            (document_id, str(item_id), title, content, json.dumps(embedding), now, now),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO rag_sources (
              id, rag_document_id, source_type, title, url, official, created_at
            )
            VALUES (?, ?, 'kakao_chat', '카카오톡 채팅 수집', NULL, 0, ?)
            """,
            (_stable_id("rag-source", f"kakao-live-{item_id}"), document_id, now),
        )
        if USE_POSTGRES:
            # pgvector 컬럼도 같이 채운다 — answer_rag_question의 벡터 검색이 이걸 쓴다.
            vec_literal = "[" + ",".join(str(x) for x in embedding) + "]"
            connection.execute(
                "UPDATE rag_documents SET embedding_vec = ?::vector WHERE id = ?",
                (vec_literal, document_id),
            )


def has_kakao_rag_document(item_id: int) -> bool:
    document_id = _stable_id("rag-document", f"kakao-live-{item_id}")
    with _connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM rag_documents WHERE id = ?", (document_id,)
        ).fetchone()
    return row is not None


def store_kakao_upload_messages(messages: list[dict[str, str]]) -> int:
    """Windows 수집기 메시지를 해시 기준으로 멱등 저장하고 신규 건수를 반환한다."""
    inserted = 0
    now = _now()
    with _connect() as connection:
        for message in messages:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO kakao_upload_messages (
                  client_message_hash, room, sender, sent_at_text, content,
                  status, result, created_at, processed_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', NULL, ?, NULL)
                """,
                (
                    message["client_message_hash"],
                    message["room"],
                    message["sender"],
                    message["sent_at_text"],
                    message["content"],
                    now,
                ),
            )
            inserted += max(cursor.rowcount, 0)
    return inserted


def get_pending_kakao_upload_messages(limit: int) -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT client_message_hash, room, sender, sent_at_text, content
            FROM kakao_upload_messages
            WHERE status = 'pending'
            ORDER BY created_at, client_message_hash
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def mark_kakao_upload_processed(client_message_hash: str, result: str) -> None:
    with _connect() as connection:
        connection.execute(
            """
            UPDATE kakao_upload_messages
            SET status = 'processed', result = ?, processed_at = ?
            WHERE client_message_hash = ?
            """,
            (result, _now(), client_message_hash),
        )


def count_pending_kakao_upload_messages() -> int:
    with _connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM kakao_upload_messages WHERE status = 'pending'"
        ).fetchone()
    return int(row["count"])


# --- 콜드스타트 자동 변환(카톡 메시지 → 모임/게시판 콘텐츠) ---

_KAKAO_HOST_USER_ID = _stable_id("kakao-host-user", "shared")
_KAKAO_HOST_PROFILE_ID = _stable_id("kakao-host-profile", "shared")


def get_coldstart_count_today() -> int:
    """하루 자동 생성 상한(30건) 체크용. UTC 날짜 기준으로 센다."""
    today = datetime.now(timezone.utc).date().isoformat()
    with _connect() as connection:
        row = connection.execute(
            "SELECT count FROM coldstart_daily_counts WHERE day = ?", (today,)
        ).fetchone()
    return row["count"] if row else 0


def _increment_coldstart_count_today(connection) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    row = connection.execute(
        "SELECT count FROM coldstart_daily_counts WHERE day = ?", (today,)
    ).fetchone()
    if row:
        connection.execute(
            "UPDATE coldstart_daily_counts SET count = ? WHERE day = ?", (row["count"] + 1, today)
        )
    else:
        connection.execute(
            "INSERT INTO coldstart_daily_counts (day, count) VALUES (?, 1)", (today,)
        )


def has_coldstart_content(item_id: int) -> bool:
    """이미 이 카톡 메시지를 모임/게시판 콘텐츠로 변환했는지(중복 변환 방지)."""
    meeting_id = _stable_id("meeting", f"kakao-live-{item_id}")
    post_id = _stable_id("board-post", f"kakao-live-{item_id}")
    with _connect() as connection:
        meeting_row = connection.execute("SELECT 1 FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if meeting_row:
            return True
        post_row = connection.execute("SELECT 1 FROM board_posts WHERE id = ?", (post_id,)).fetchone()
        return post_row is not None


def _ensure_kakao_host_profile(connection) -> None:
    now = _now()
    connection.execute(
        """
        INSERT OR IGNORE INTO users (id, role, status, anonymous_id, created_at, updated_at)
        VALUES (?, 'system', 'active', 'kakao_open_chat', ?, ?)
        """,
        (_KAKAO_HOST_USER_ID, now, now),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO profiles (id, user_id, nickname, avatar_key, created_at, updated_at)
        VALUES (?, ?, '오픈채팅', 'default_01', ?, ?)
        """,
        (_KAKAO_HOST_PROFILE_ID, _KAKAO_HOST_USER_ID, now, now),
    )


def create_coldstart_meeting(
    *, item_id: int, title: str, meeting_category: str, description: str, created_at: str
) -> None:
    """오픈채팅 동행/이동 구인 글을 모임 후보로 변환한다. 호스트가 없는 외부 글이라
    owner_secret 없이(NULL) 등록하고, 신청/승인은 프론트에서 cta.enabled=False로 막는다."""
    meeting_id = _stable_id("meeting", f"kakao-live-{item_id}")
    source_dt = _kakao_source_time_to_utc(created_at)
    # 원문에서 약속 시각을 안정적으로 추출하기 어려우므로 화면에는 채팅 작성 시각을
    # 보여준다. 노출·삭제도 같은 원문 시각부터 짧은 유효기간(기본 4시간)만 적용한다.
    starts_at = source_dt.isoformat()
    ends_at = (source_dt + timedelta(hours=settings.kakao_party_delete_after_hours)).isoformat()
    now = _now()

    with _connect() as connection:
        _ensure_kakao_host_profile(connection)
        connection.execute(
            """
            INSERT OR IGNORE INTO meetings (
              id, source_key, host_user_id, host_profile_id, category, title, description,
              place_label, starts_at, ends_at, capacity, approved_count, status, visibility,
              owner_secret, source, created_at, updated_at
            )
            VALUES (?, NULL, ?, ?, ?, ?, ?, '오픈채팅방 참고', ?, ?, 1, 0, 'open', 'public', NULL, 'kakao_chat', ?, ?)
            """,
            (
                meeting_id,
                _KAKAO_HOST_USER_ID,
                _KAKAO_HOST_PROFILE_ID,
                meeting_category,
                title,
                description,
                starts_at,
                ends_at,
                starts_at,
                now,
            ),
        )
        _increment_coldstart_count_today(connection)


def create_coldstart_board_post(*, item_id: int, category: str, title: str, body: str) -> None:
    """오픈채팅 중고·나눔·질문 글을 생활게시판에 같은 배지로 노출한다."""
    post_id = _stable_id("board-post", f"kakao-live-{item_id}")
    now = _now()
    with _connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO board_posts (
              id, category, title, body, author_nickname, author_anonymous_id, source, created_at
            )
            VALUES (?, ?, ?, ?, '오픈채팅', NULL, 'kakao_chat', ?)
            """,
            (post_id, category, title, body, now),
        )
        _increment_coldstart_count_today(connection)
