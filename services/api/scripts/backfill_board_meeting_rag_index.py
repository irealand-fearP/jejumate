"""게시판 글·모임 RAG 색인 백필 스크립트 (1회성).

work-order-2026-07-10-badge-rag.md 작업 B: create_board_post/create_meeting에
색인을 붙였지만, 그 전에 이미 만들어진 기존 글·모임은 자동으로 색인되지 않는다.
이 스크립트가 기존 데이터를 한 번 훑어서 index_content_as_rag_document로 채워 넣는다.
이미 색인된 건(INSERT OR IGNORE)은 중복 생성되지 않으므로 여러 번 실행해도 안전하다.

실행 전 .env 로드 필수(운영 저장소는 Postgres — 안 하면 SQLite로 잘못 붙는다):
    cd services/api
    set -a; . ./.env; set +a
    python3 scripts/backfill_board_meeting_rag_index.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.repositories.local_store import _connect, ensure_database, index_content_as_rag_document  # noqa: E402


def _count_rag_documents(connection, source_type: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS n FROM rag_documents WHERE source_type = ?", (source_type,)
    ).fetchone()
    return row["n"]


def backfill_board_posts() -> tuple[int, int]:
    """(성공, 실패) 건수를 돌려준다."""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, category, title, body FROM board_posts WHERE deleted_at IS NULL"
        ).fetchall()

    ok = 0
    failed = 0
    for row in rows:
        success = index_content_as_rag_document(
            source_type="board",
            source_id=row["id"],
            title=row["title"],
            body=row["body"],
            category=row["category"],
            source_label="생활게시판 글",
        )
        ok += int(success)
        failed += int(not success)
    return ok, failed


def backfill_meetings() -> tuple[int, int]:
    """(성공, 실패) 건수를 돌려준다. 오픈채팅 콜드스타트 변환 모임(source='kakao_chat')도
    같이 색인한다 — 이미 rag_documents(source_type='kakao_chat')에 원본 채팅이 들어가
    있지만, 모임으로 변환된 요약본을 'meeting'으로 한 번 더 색인해도 INSERT OR IGNORE라
    안전하고, 모임 검색 관점에서 근거가 하나 더 느는 것도 나쁘지 않다."""
    with _connect() as connection:
        rows = connection.execute("SELECT id, category, title, description, place_label FROM meetings").fetchall()

    ok = 0
    failed = 0
    for row in rows:
        body = "\n".join(part for part in (row["description"], f"장소: {row['place_label']}") if part) or row["title"]
        success = index_content_as_rag_document(
            source_type="meeting",
            source_id=row["id"],
            title=row["title"],
            body=body,
            category=row["category"],
            source_label="모임 등록",
        )
        ok += int(success)
        failed += int(not success)
    return ok, failed


if __name__ == "__main__":
    ensure_database()

    with _connect() as connection:
        before_board = _count_rag_documents(connection, "board")
        before_meeting = _count_rag_documents(connection, "meeting")

    board_ok, board_failed = backfill_board_posts()
    meeting_ok, meeting_failed = backfill_meetings()

    with _connect() as connection:
        after_board = _count_rag_documents(connection, "board")
        after_meeting = _count_rag_documents(connection, "meeting")

    print(f"게시판 글: 시도 {board_ok + board_failed}건 (성공 {board_ok} / 임베딩 실패 {board_failed})")
    print(f"모임: 시도 {meeting_ok + meeting_failed}건 (성공 {meeting_ok} / 임베딩 실패 {meeting_failed})")
    print(f"rag_documents(board) 순증가: {before_board} -> {after_board} ({after_board - before_board}건)")
    print(f"rag_documents(meeting) 순증가: {before_meeting} -> {after_meeting} ({after_meeting - before_meeting}건)")
