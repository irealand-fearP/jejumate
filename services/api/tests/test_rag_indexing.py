"""게시판 글·모임 생성 시 RAG 문서로 자동 색인되는지 확인하는 테스트
(work-order-2026-07-10-badge-rag.md 작업 B).

기존 RAG 코퍼스는 카톡 수집(kakao_chat)과 소량 큐레이션 시드뿐이었다 — 서비스
내에서 직접 쓴 게시판 글·모임은 /api/rag/ask 답변 근거에 전혀 안 잡혔다. 생성
시점에 embed_text로 임베딩해 rag_documents에 넣도록 고친 뒤, 이 파일에서
다음을 검증한다:
  1) 게시판 글/모임 생성 시 rag_documents에 해당 source_type으로 색인되는가
  2) 임베딩 API가 실패해도 글/모임 작성 자체는 성공하는가(best-effort)
  3) 글/모임 삭제 시 색인이 비활성화(is_active=0)되어 더는 근거로 안 쓰이는가
  4) 실제로 answer_rag_question이 새로 만든 게시판 글을 근거로 answer_source
     'community'를 반환하는가(end-to-end)
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.repositories import local_store

FAKE_EMBEDDING = [1.0, 0.0, 0.0]


@pytest.fixture(autouse=True)
def isolated_sqlite_db(tmp_path, monkeypatch):
    """다른 테스트/실제 데이터와 섞이지 않게 테스트마다 독립된 sqlite 파일을 쓴다."""
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(local_store, "DB_PATH", db_path)
    monkeypatch.setattr(local_store, "USE_POSTGRES", False)
    local_store.ensure_database()
    yield


def _rag_document_row(source_type: str, source_id: str):
    with local_store._connect() as connection:
        return connection.execute(
            "SELECT * FROM rag_documents WHERE source_type = ? AND source_id = ?",
            (source_type, source_id),
        ).fetchone()


@patch("app.repositories.local_store.embed_text", return_value=FAKE_EMBEDDING)
def test_create_board_post_indexes_rag_document(mock_embed):
    post = local_store.create_board_post(
        category="꿀팁",
        title="세탁기 필터 청소 팁",
        body="한 달에 한 번 필터를 꺼내서 씻어주면 냄새가 안 나요.",
        author_nickname="바당이",
        anonymous_id="anon-board-1",
    )

    row = _rag_document_row("board", post.id)
    assert row is not None
    assert row["is_active"] == 1
    assert json.loads(row["embedding"]) == FAKE_EMBEDDING
    assert row["title"] == "세탁기 필터 청소 팁"
    mock_embed.assert_called_once()


@patch("app.repositories.local_store.embed_text", return_value=FAKE_EMBEDDING)
def test_create_meeting_indexes_rag_document(mock_embed):
    meeting = local_store.create_meeting(
        category="move",
        title="공항 택시팟",
        description="3시 비행기라 2시 반에 출발해요",
        place_label="제주공항 3번 게이트",
        capacity=3,
        starts_at="2026-07-10T14:00",
        ends_at="2026-07-10T15:00",
        nickname="호스트바당이",
        anonymous_id="anon-meeting-1",
    )

    row = _rag_document_row("meeting", meeting.meeting_id)
    assert row is not None
    assert row["is_active"] == 1
    assert "제주공항 3번 게이트" in row["body"]
    assert "3시 비행기" in row["body"]
    mock_embed.assert_called_once()


@patch("app.repositories.local_store.embed_text", side_effect=RuntimeError("OPENAI_API_KEY 없음"))
def test_board_post_creation_survives_embedding_failure(mock_embed, caplog):
    # 임베딩 API가 실패해도 게시판 글 작성 자체는 성공해야 한다(best-effort 색인).
    post = local_store.create_board_post(
        category="질문게시판",
        title="렌트카 추천",
        body="공항 근처에서 렌트카 빌리려는데 추천 있나요?",
        author_nickname="바당이",
        anonymous_id="anon-board-2",
    )
    assert post.id

    row = _rag_document_row("board", post.id)
    assert row is None  # 색인은 실패했으므로 문서가 생기지 않아야 한다.


@patch("app.repositories.local_store.embed_text", return_value=FAKE_EMBEDDING)
def test_deleting_board_post_deactivates_rag_document(mock_embed):
    post = local_store.create_board_post(
        category="기타",
        title="곧 지울 글",
        body="테스트용 게시글이라 곧 지울 예정입니다 잘부탁드립니다",
        author_nickname="바당이",
        anonymous_id="anon-board-3",
    )
    local_store.delete_board_post(post_id=post.id, anonymous_id="anon-board-3")

    row = _rag_document_row("board", post.id)
    assert row is not None
    assert row["is_active"] == 0


@patch("app.repositories.local_store.embed_text", return_value=FAKE_EMBEDDING)
def test_deleting_meeting_deactivates_rag_document(mock_embed):
    meeting = local_store.create_meeting(
        category="move",
        title="곧 해산할 모임",
        description=None,
        place_label="제주공항",
        capacity=2,
        starts_at="2026-07-10T14:00",
        ends_at="2026-07-10T15:00",
        nickname="호스트바당이",
        anonymous_id="anon-meeting-2",
    )
    local_store.delete_meeting(meeting_id=meeting.meeting_id, owner_secret=meeting.owner_secret)

    row = _rag_document_row("meeting", meeting.meeting_id)
    assert row is not None
    assert row["is_active"] == 0


def _fake_openai_chat_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=json.dumps(payload)))]
    return response


@patch("app.repositories.local_store.embed_text", return_value=FAKE_EMBEDDING)
@patch("app.services.rag_answer_service.settings")
def test_answer_rag_question_uses_newly_created_board_post_as_source(mock_rag_settings, mock_embed):
    # 게시판 글이 실제로 /api/rag/ask 답변 근거(sources)에 잡히는지 end-to-end로 확인한다.
    post = local_store.create_board_post(
        category="꿀팁",
        title="제주공항 짐보관 팁",
        body="공항 3층 짐보관소가 항상 여유 있어서 편해요.",
        author_nickname="바당이",
        anonymous_id="anon-board-4",
    )

    mock_rag_settings.openai_api_key = "test-key"
    fake_response = _fake_openai_chat_response(
        {
            "answer": "제주공항 3층 짐보관소를 이용해보세요.",
            "citations": [{"index": 0, "supports": True}],
        }
    )

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        result = local_store.answer_rag_question(question="짐 맡길 데 있나요?", anonymous_id=None)

    assert result.answer_source == "community"
    # rag_sources.title은 add_kakao_rag_document와 같은 컨벤션으로 카테고리 라벨을
    # 쓰므로(원문 제목이 아님), 실제 확인 대상은 출처 구분값(source_type)이다 —
    # 이게 work order 핵심 요구사항("카톡 문서와 섞여도 출처 구분 가능하게").
    assert any(source.source_type == "board" for source in result.sources)


@patch("app.repositories.local_store.embed_text", return_value=FAKE_EMBEDDING)
@patch("app.services.rag_answer_service.settings")
def test_unverified_candidates_are_not_exposed_as_sources(mock_rag_settings, mock_embed):
    local_store.create_board_post(
        category="꿀팁",
        title="제주공항 짐보관 팁",
        body="공항 3층 짐보관소를 이용했어요.",
        author_nickname="바당이",
        anonymous_id="anon-board-unsupported",
    )
    mock_rag_settings.openai_api_key = "test-key"
    general_response = MagicMock()
    general_response.choices = [MagicMock(message=MagicMock(content="일반 지식 답변입니다."))]

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            _fake_openai_chat_response(
                {
                    "answer": "근거로 답하기 어렵습니다.",
                    "citations": [{"index": 0, "supports": False}],
                }
            ),
            general_response,
        ]
        mock_openai_cls.return_value = mock_client

        result = local_store.answer_rag_question(question="화성에 물이 있어?", anonymous_id=None)

    assert result.answer == "일반 지식 답변입니다."
    assert result.answer_source == "general_knowledge"
    assert result.sources == []
    assert result.confidence_grade == "none"


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("제주대학교에 수의대가 있어?", True),
        ("수의대는 어디에 있어?", True),
        ("휴학 신청은 어떻게 해?", True),
        ("기숙사 입주 신청 알려줘", True),
        ("기숙사에서 공항 갈 택시팟 있어?", False),
        ("생활관 세탁기 몇 대야?", False),
        ("제주대 근처 맛집 추천해줘", False),
        ("주차등록은 어디서 해?", True),
        ("자동차 정기이용 해지는 어떻게 해?", True),
        ("골프연습장은 어디에 있어?", True),
        ("공대3호관 어디에있어?", True),
        ("생명과학대는 어디있어?", True),
        ("건축학과 어디있어?", True),
        ("수학 공부는 어떻게 해?", False),
        ("2026 제주대학교 하기 계절학기 학점교류방", False),
        ("모임 신청은 어디서 해?", False),
    ],
)
def test_routes_university_facts_to_official_documents(question, expected):
    assert local_store._should_search_jejunu_official(question) is expected


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("주차등록은 어디서 해?", True),
        ("휴학 신청 기간 알려줘", True),
        ("수의대는 어디에 있어?", False),
    ],
)
def test_refreshes_time_sensitive_official_search(question, expected):
    assert local_store._should_refresh_jejunu_official_search(question) is expected


def test_veterinary_location_question_prioritizes_exact_building_source():
    source_ids = local_store._official_source_ids_for_question("대학교 내 수의대 위치 알려줘")

    assert source_ids[0] == "campus-building-suuigwadaehak"


def test_engineering_location_question_prioritizes_exact_building_source():
    source_ids = local_store._official_source_ids_for_question("공대3호관 어디에있어?")

    assert source_ids == ("campus-building-gonggwadaehak3hogwan",)


def test_life_sciences_location_question_prioritizes_exact_building_source():
    source_ids = local_store._official_source_ids_for_question("생명과학대는 어디있어?")

    assert source_ids[0] == "campus-building-saengmyeongjawongwahakdaehak"


def test_department_location_question_prioritizes_department_building_source():
    source_ids = local_store._official_source_ids_for_question("건축학과 어디있어?")

    assert source_ids[0] == "campus-building-gonggwadaehak4hogwan"
