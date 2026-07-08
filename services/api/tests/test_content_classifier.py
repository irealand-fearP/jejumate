"""content_classifier가 올바른 모델/파라미터로 OpenAI를 호출하는지 회귀 테스트.

gpt-5-mini는 temperature 커스텀 값을 지원하지 않으므로(400 에러), 이 테스트는
temperature 파라미터가 다시 섞여 들어가는 실수를 잡아내는 역할도 한다.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.services.content_classifier import CHAT_MODEL, classify_message


def _fake_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=json.dumps(payload)))]
    return response


@patch("app.services.content_classifier.settings")
def test_classify_message_uses_gpt5_mini_without_temperature(mock_settings):
    mock_settings.openai_api_key = "test-key"
    fake_response = _fake_response({"type": "meetup", "title": "애월 택시팟", "meeting_category": "move"})

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        result = classify_message("내일 1시 애월 가실 분")

    assert CHAT_MODEL == "gpt-5-mini"
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-5-mini"
    assert "temperature" not in call_kwargs
    assert call_kwargs["reasoning_effort"] == "minimal"
    assert result == {"type": "meetup", "title": "애월 택시팟", "meeting_category": "move"}


@patch("app.services.content_classifier.settings")
def test_classify_message_without_api_key_skips_call(mock_settings):
    mock_settings.openai_api_key = None
    with patch.dict("os.environ", {}, clear=True):
        result = classify_message("아무 메시지")
    assert result == {"type": "other", "title": "", "meeting_category": None}
