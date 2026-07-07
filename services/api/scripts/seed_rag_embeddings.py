"""
RAG 임베딩 백필 + 카톡 시드 적재 스크립트 (1회성).

1) 기존 코덱스 rag_documents(정책/코스 3건)에 임베딩이 없으면 채워 넣는다(코덱스 시드는
   그대로 유지, 임베딩만 추가).
2) jejumate/backend의 실제 Postgres(jejumate-pg, 55432)에서 카톡 파싱 결과(source='kakao')
   게시글을 읽어와 rag_documents에 새 문서로 적재한다. 이미 실제 OpenAI 임베딩이 계산돼
   있으므로 재계산하지 않고 그대로 복사한다(비용 절감).

실행 전 OPENAI_API_KEY가 필요하다(코덱스 기존 문서 3건 백필용):
    set -a; source ../.env; set +a
    python3 seed_rag_embeddings.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from app.repositories.local_store import _connect, _now, _stable_id, ensure_database  # noqa: E402
from app.services.embedding_service import embed_text  # noqa: E402

OUR_DATABASE_URL = "postgresql://postgres:postgres@localhost:55432/jejumate"


def backfill_existing_documents() -> int:
    """코덱스 기존 rag_documents 중 embedding이 비어 있는 문서를 채운다."""
    updated = 0
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, title, body FROM rag_documents WHERE embedding IS NULL"
        ).fetchall()
        for row in rows:
            vector = embed_text(f"{row['title']}\n{row['body']}")
            connection.execute(
                "UPDATE rag_documents SET embedding = ? WHERE id = ?",
                (json.dumps(vector), row["id"]),
            )
            updated += 1
    return updated


def seed_kakao_documents() -> int:
    """우리 Postgres의 카톡 파싱 결과(source='kakao')를 rag_documents에 적재한다."""
    inserted = 0
    now = _now()

    with psycopg.connect(OUR_DATABASE_URL, row_factory=dict_row) as pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT id, content, category, embedding::text AS embedding FROM posts "
                "WHERE source = 'kakao' AND embedding IS NOT NULL"
            )
            posts = cur.fetchall()

    with _connect() as connection:
        for post in posts:
            post_id = str(post["id"])
            document_id = _stable_id("rag-document", f"kakao-post-{post_id}")
            content = post["content"]
            title = content if len(content) <= 40 else f"{content[:40]}…"
            # psycopg가 pgvector 어댑터 없이 반환하는 텍스트 표현("[0.01,-0.02,...]")은
            # 이미 JSON 배열 문법과 동일하므로 그대로 파싱해서 float 리스트로 되돌린다.
            embedding_vector = json.loads(post["embedding"])

            connection.execute(
                """
                INSERT OR IGNORE INTO rag_documents (
                  id, source_type, source_id, title, body, region, category, visibility,
                  is_active, embedding, created_at, updated_at
                )
                VALUES (?, 'kakao_chat', ?, ?, ?, '제주', ?, 'public', 1, ?, ?, ?)
                """,
                (
                    document_id,
                    post_id,
                    title,
                    content,
                    post["category"],
                    json.dumps(embedding_vector),
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO rag_sources (
                  id, rag_document_id, source_type, title, url, official, created_at
                )
                VALUES (?, ?, 'kakao_chat', '카카오톡 채팅 수집', NULL, 0, ?)
                """,
                (_stable_id("rag-source", f"kakao-post-{post_id}"), document_id, now),
            )
            inserted += 1

    return inserted


if __name__ == "__main__":
    ensure_database()
    backfilled = backfill_existing_documents()
    print(f"코덱스 기존 문서 임베딩 백필: {backfilled}건")
    seeded = seed_kakao_documents()
    print(f"카톡 시드 적재(embedding 포함): {seeded}건")
