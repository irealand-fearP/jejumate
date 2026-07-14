"""선별한 제주대학교 공식 문서를 RAG에 멱등 색인한다."""
from __future__ import annotations

import json

from app.data.jejunu_official import JEJUNU_OFFICIAL_DOCUMENTS, JejunuOfficialDocument
from app.repositories import local_store
from app.services.embedding_service import embed_text


SOURCE_TYPE = "jejunu_official"


def seed_jejunu_official_documents(
    documents: tuple[JejunuOfficialDocument, ...] = JEJUNU_OFFICIAL_DOCUMENTS,
) -> int:
    """공식 문서와 원문 URL을 upsert하고 처리한 문서 수를 반환한다."""
    now = local_store._now()

    with local_store._connect() as connection:
        for document in documents:
            document_id = local_store._stable_id(
                "rag-document", f"{SOURCE_TYPE}-{document['source_id']}"
            )
            source_id = local_store._stable_id(
                "rag-source", f"{SOURCE_TYPE}-{document['source_id']}"
            )
            existing = connection.execute(
                "SELECT title, body, embedding FROM rag_documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            content_changed = (
                existing is None
                or existing["title"] != document["title"]
                or existing["body"] != document["body"]
                or not existing["embedding"]
            )
            if content_changed:
                embedding = embed_text(f"{document['title']}\n{document['body']}")
                embedding_json = json.dumps(embedding)
            else:
                embedding = None
                embedding_json = existing["embedding"]

            connection.execute(
                """
                INSERT INTO rag_documents (
                  id, source_type, source_id, title, body, region, category, visibility,
                  is_active, embedding, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, '제주', '제주대학교 공식', 'public', 1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  source_type = excluded.source_type,
                  source_id = excluded.source_id,
                  title = excluded.title,
                  body = excluded.body,
                  region = excluded.region,
                  category = excluded.category,
                  visibility = excluded.visibility,
                  is_active = 1,
                  embedding = excluded.embedding,
                  updated_at = excluded.updated_at
                """,
                (
                    document_id,
                    SOURCE_TYPE,
                    document["source_id"],
                    document["title"],
                    document["body"],
                    embedding_json,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO rag_sources (
                  id, rag_document_id, source_type, title, url, official, created_at
                )
                VALUES (?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(id) DO UPDATE SET
                  rag_document_id = excluded.rag_document_id,
                  source_type = excluded.source_type,
                  title = excluded.title,
                  url = excluded.url,
                  official = 1
                """,
                (
                    source_id,
                    document_id,
                    SOURCE_TYPE,
                    document["title"],
                    document["url"],
                    now,
                ),
            )

            if local_store.USE_POSTGRES and embedding is not None:
                vector = "[" + ",".join(str(value) for value in embedding) + "]"
                connection.execute(
                    "UPDATE rag_documents SET embedding_vec = ?::vector WHERE id = ?",
                    (vector, document_id),
                )

    return len(documents)
