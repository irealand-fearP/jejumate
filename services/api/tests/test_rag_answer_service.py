"""rag_answer_service의 답변 생성 + 신뢰도 검증 로직 테스트.

실제 OpenAI 호출은 비용이 들고 비결정적이므로, OpenAI 클라이언트를 모킹해서
"근거만 프롬프트에 담아 보내는지", "citations 응답을 문서 순서에 맞게
supports 리스트로 변환하는지", "응답이 이상해도 안전하게 처리하는지"를 검증한다.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.rag_answer_service import (
    confidence_grade,
    generate_general_answer,
    generate_verified_answer,
)


def _fake_openai_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=json.dumps(payload)))]
    return response


@patch("app.services.rag_answer_service.settings")
def test_generate_verified_answer_maps_citations_to_documents(mock_settings):
    mock_settings.openai_api_key = "test-key"
    documents = [
        {
            "index": 0,
            "title": "제주대학교 수의과대학 안내",
            "body": "수의예과와 수의학과가 있습니다.",
            "source_label": "제주대학교 공식",
            "url": "https://www.jejunu.ac.kr/colleges/university.htm",
        },
        {"index": 1, "title": "함덕 맛집", "body": "오션뷰 카페가 많습니다."},
    ]
    fake_response = _fake_openai_response(
        {
            "answer": "제주대학교에는 수의과대학이 있습니다.",
            "citations": [{"index": 0, "supports": True}, {"index": 1, "supports": False}],
        }
    )

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        result = generate_verified_answer(question="제주대학교에 수의대가 있나요?", documents=documents)

    assert result.answer == "제주대학교에는 수의과대학이 있습니다."
    assert result.supports == [True, False]

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-5-mini"
    assert call_kwargs["reasoning_effort"] == "minimal"
    user_message = call_kwargs["messages"][1]["content"]
    assert "제주대학교 수의과대학 안내" in user_message
    assert "[출처 유형] 제주대학교 공식" in user_message
    assert "https://www.jejunu.ac.kr/colleges/university.htm" in user_message
    assert "함덕 맛집" in user_message
    assert "제주대학교에 수의대가 있나요?" in user_message


@patch("app.services.rag_answer_service.settings")
def test_generate_verified_answer_defaults_missing_citation_to_unsupported(mock_settings):
    mock_settings.openai_api_key = "test-key"
    documents = [{"index": 0, "title": "A", "body": "내용"}]
    fake_response = _fake_openai_response({"answer": "답변", "citations": []})

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        result = generate_verified_answer(question="질문", documents=documents)

    assert result.supports == [False]


@patch("app.services.rag_answer_service.settings")
def test_generate_verified_answer_falls_back_on_invalid_json(mock_settings):
    mock_settings.openai_api_key = "test-key"
    documents = [{"index": 0, "title": "A", "body": "내용"}]
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="이건 JSON이 아님"))]

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        result = generate_verified_answer(question="질문", documents=documents)

    assert result.answer == "제공된 정보로는 답변하기 어렵습니다."
    assert result.supports == [False]


@patch("app.services.rag_answer_service.settings")
def test_generate_verified_answer_requires_api_key(mock_settings):
    mock_settings.openai_api_key = None
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError):
            generate_verified_answer(question="질문", documents=[{"index": 0, "title": "A", "body": "b"}])


@patch("app.services.rag_answer_service.settings")
def test_generate_general_answer_calls_openai_with_question_only(mock_settings):
    """근거 문서 없이(rows=0) 일반 지식으로 답할 때도 gpt-5-mini를 같은 비용 설정으로 호출하는지 확인."""
    mock_settings.openai_api_key = "test-key"
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="화성 표면 아래 얼음 형태로 물이 있다고 알려져 있습니다."))]

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        answer = generate_general_answer(question="화성에 물이 있나요?")

    assert answer == "화성 표면 아래 얼음 형태로 물이 있다고 알려져 있습니다."

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-5-mini"
    assert call_kwargs["reasoning_effort"] == "minimal"
    assert call_kwargs["max_completion_tokens"] == 700
    user_message = call_kwargs["messages"][1]["content"]
    assert "화성에 물이 있나요?" in user_message


@patch("app.services.rag_answer_service.settings")
def test_generate_general_answer_falls_back_on_empty_content(mock_settings):
    mock_settings.openai_api_key = "test-key"
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content=""))]

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        answer = generate_general_answer(question="질문")

    assert answer.strip() != ""


@patch("app.services.rag_answer_service.settings")
def test_generate_general_answer_requires_api_key(mock_settings):
    mock_settings.openai_api_key = None
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError):
            generate_general_answer(question="질문")


@pytest.mark.parametrize(
    ("supports", "expected_grade"),
    [
        ([], "none"),
        ([True, True, True], "high"),
        ([True, False, True], "medium"),
        ([False, False], "low"),
    ],
)
def test_confidence_grade(supports, expected_grade):
    assert confidence_grade(supports) == expected_grade
