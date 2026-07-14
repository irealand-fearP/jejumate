"""제주대학교 공식 홈페이지 문서의 멱등 색인과 출처 노출을 검증한다."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.repositories import local_store
from app.data.jejunu_campus_map import campus_building_documents
from app.services.jejunu_official_ingest import seed_jejunu_official_documents

FAKE_EMBEDDING = [1.0, 0.0, 0.0]
OFFICIAL_URL = "https://www.jejunu.ac.kr/colleges/university.htm"
OFFICIAL_MAP_URL = "https://www.jejunu.ac.kr/schoolinfo/campinfo/campusmap.htm"


@pytest.fixture(autouse=True)
def isolated_sqlite_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(local_store, "DB_PATH", db_path)
    monkeypatch.setattr(local_store, "USE_POSTGRES", False)
    local_store.ensure_database()
    yield


def _document(body: str, source_id: str = "veterinary-test"):
    return (
        {
            "source_id": source_id,
            "title": "제주대학교 수의과대학 안내",
            "body": body,
            "url": OFFICIAL_URL,
        },
    )


def _location_document():
    return (
        {
            "source_id": "campus-map-veterinary-college",
            "title": "제주대학교 캠퍼스맵 수의과대학 위치",
            "body": "수의과대학 건물 핀은 위도 33.4520059, 경도 126.5585883에 있다.",
            "url": OFFICIAL_MAP_URL,
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


@patch("app.services.jejunu_official_ingest.embed_text", return_value=FAKE_EMBEDDING)
def test_unchanged_official_document_reuses_existing_embedding(mock_embed):
    document = _document("수의예과와 수의학과가 있습니다.")

    assert seed_jejunu_official_documents(document) == 1
    assert seed_jejunu_official_documents(document) == 1

    assert mock_embed.call_count == 1


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


@patch("app.repositories.local_store.embed_text", return_value=[0.0, 1.0, 0.0])
@patch("app.services.jejunu_official_ingest.embed_text", return_value=FAKE_EMBEDDING)
@patch("app.services.rag_answer_service.settings")
def test_short_official_question_uses_targeted_source_below_similarity_threshold(
    mock_rag_settings, mock_seed_embed, mock_query_embed
):
    seed_jejunu_official_documents(
        _document("제주대학교에는 수의과대학이 있습니다.", source_id="veterinary-college")
    )
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
            question="수의대는 어디에 있어?", anonymous_id=None
        )

    assert result.answer_source == "official"
    assert result.sources[0].source_type == "jejunu_official"
    assert result.sources[0].url == OFFICIAL_URL


@patch("app.repositories.local_store.embed_text", return_value=FAKE_EMBEDDING)
@patch("app.services.jejunu_official_ingest.embed_text", return_value=FAKE_EMBEDDING)
@patch("app.services.rag_answer_service.settings")
def test_location_answer_includes_structured_map_location(
    mock_rag_settings, mock_seed_embed, mock_query_embed
):
    seed_jejunu_official_documents(_location_document())
    mock_rag_settings.openai_api_key = "test-key"

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_response(
            {
                "answer": "수의과대학은 아라캠퍼스 남쪽에 있습니다.",
                "citations": [{"index": 0, "supports": True}],
            }
        )
        mock_openai_cls.return_value = mock_client

        result = local_store.answer_rag_question(
            question="대학교 내 수의대 위치 알려줘", anonymous_id=None
        )

    assert result.map_location is not None
    assert result.map_location.title == "제주대학교 수의과대학"
    assert result.map_location.lat == 33.4520059
    assert result.map_location.lng == 126.5585883
    assert result.map_location.source_url == OFFICIAL_MAP_URL


@patch("app.repositories.local_store.embed_text", return_value=FAKE_EMBEDDING)
@patch("app.services.jejunu_official_ingest.embed_text", return_value=FAKE_EMBEDDING)
@patch("app.services.rag_answer_service.settings")
def test_any_campus_building_location_includes_structured_map_location(
    mock_rag_settings, mock_seed_embed, mock_query_embed
):
    engineering_three = next(
        document
        for document in campus_building_documents()
        if document["source_id"] == "campus-building-gonggwadaehak3hogwan"
    )
    seed_jejunu_official_documents((engineering_three,))
    mock_rag_settings.openai_api_key = "test-key"

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_response(
            {
                "answer": "공과대학3호관은 공과대학1호관 남쪽에 있습니다.",
                "citations": [{"index": 0, "supports": True}],
            }
        )
        mock_openai_cls.return_value = mock_client

        result = local_store.answer_rag_question(
            question="공대3호관 어디에있어?", anonymous_id=None
        )

    assert result.answer_source == "official"
    assert result.map_location is not None
    assert result.map_location.title == "제주대학교 공과대학3호관"
    assert result.map_location.lat == 33.45651
    assert result.map_location.lng == 126.5655039
    assert result.map_location.source_url == OFFICIAL_MAP_URL


@patch("app.repositories.local_store.embed_text", return_value=FAKE_EMBEDDING)
@patch("app.services.jejunu_official_ingest.embed_text", return_value=FAKE_EMBEDDING)
@patch("app.services.rag_answer_service.settings")
def test_department_question_returns_office_building_and_map(
    mock_rag_settings, mock_seed_embed, mock_query_embed
):
    engineering_four = next(
        document
        for document in campus_building_documents()
        if document["source_id"] == "campus-building-gonggwadaehak4hogwan"
    )
    seed_jejunu_official_documents((engineering_four,))
    mock_rag_settings.openai_api_key = "test-key"

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_response(
            {
                "answer": "건축학전공 사무실은 공과대학4호관 지상 1층에 있습니다.",
                "citations": [{"index": 0, "supports": True}],
            }
        )
        mock_openai_cls.return_value = mock_client

        result = local_store.answer_rag_question(
            question="건축학과 어디있어?", anonymous_id=None
        )

    assert result.answer_source == "official"
    assert result.confidence_grade == "high"
    assert result.map_location is not None
    assert result.map_location.title == "제주대학교 공과대학4호관"
    assert result.map_location.lat == 33.4547286
    assert result.map_location.lng == 126.5651324
