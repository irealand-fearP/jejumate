"""제주대학교 공식 홈페이지 문서의 멱등 색인과 출처 노출을 검증한다."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.repositories import local_store
from app.services.jejunu_official_ingest import seed_jejunu_official_documents

FAKE_EMBEDDING = [1.0, 0.0, 0.0]
OFFICIAL_URL = "https://www.jejunu.ac.kr/colleges/university.htm"


@pytest.fixture(autouse=True)
def isolated_sqlite_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(local_store, "DB_PATH", db_path)
    monkeypatch.setattr(local_store, "USE_POSTGRES", False)
    local_store.ensure_database()
    yield


def _document(body: str):
    return (
        {
            "source_id": "veterinary-test",
            "title": "제주대학교 수의과대학 안내",
            "body": body,
            "url": OFFICIAL_URL,
        },
    )


@patch("app.services.jejunu_official_ingest.embed_text", return_value=FAKE_EMBEDDING)
def test_seed_is_idempotent_and_keeps_original_url(mock_embed):
    assert seed_jejunu_official_documents(_document("수의예과와 수의학과가 있습니다.")) == 1
    assert seed_jejunu_official_documents(_document("수의과대학이 운영되고 있습니다.")) == 1

    with local_store._connect() as connection:
        rows = connection.execute(
            "SELECT * FROM rag_documents WHERE source_type = 'jejunu_official'"
        ).fetchall()
        source = connection.execute(
            "SELECT * FROM rag_sources WHERE source_type = 'jejunu_official'"
        ).fetchone()

    assert len(rows) == 1
    assert rows[0]["body"] == "수의과대학이 운영되고 있습니다."
    assert json.loads(rows[0]["embedding"]) == FAKE_EMBEDDING
    assert source["url"] == OFFICIAL_URL
    assert source["official"] == 1
    assert mock_embed.call_count == 2


def _fake_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=json.dumps(payload)))]
    return response


@patch("app.repositories.local_store.embed_text", return_value=FAKE_EMBEDDING)
@patch("app.services.jejunu_official_ingest.embed_text", return_value=FAKE_EMBEDDING)
@patch("app.services.rag_answer_service.settings")
def test_official_answer_returns_only_verified_original_sources(
    mock_rag_settings, mock_seed_embed, mock_query_embed
):
    seed_jejunu_official_documents(_document("제주대학교에는 수의과대학이 있습니다."))
    mock_rag_settings.openai_api_key = "test-key"

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_response(
            {
                "answer": "제주대학교에는 수의과대학이 있습니다.",
                "citations": [{"index": 0, "supports": True}],
            }
        )
        mock_openai_cls.return_value = mock_client

        result = local_store.answer_rag_question(
            question="제주대학교에 수의대가 있어?", anonymous_id=None
        )

    assert result.answer_source == "official"
    assert result.confidence_grade == "high"
    assert len(result.sources) == 1
    assert result.sources[0].source_type == "jejunu_official"
    assert result.sources[0].url == OFFICIAL_URL
    assert result.sources[0].supports_answer is True
