from __future__ import annotations

from unittest.mock import patch

from app.api.routes.ingest import upload_kakao_messages
from app.core.config import settings
from app.schemas.ingest import KakaoUploadMessage, KakaoUploadRequest
from app.services.kakao_ingest import _uploaded_item_id, ingest_uploaded_messages


def test_uploaded_item_id_is_stable_and_namespaced():
    message_hash = "a" * 64

    first = _uploaded_item_id(message_hash)
    second = _uploaded_item_id(message_hash)

    assert first == second
    assert first >= 1 << 60
    assert first < 1 << 61


@patch("app.services.kakao_ingest.count_pending_kakao_upload_messages", return_value=0)
@patch("app.services.kakao_ingest.mark_kakao_upload_processed")
@patch("app.services.kakao_ingest.convert_to_coldstart_content")
@patch("app.services.kakao_ingest.add_kakao_rag_document")
@patch("app.services.kakao_ingest.embed_text", return_value=[0.1, 0.2])
@patch("app.services.kakao_ingest.has_kakao_rag_document", return_value=False)
@patch("app.services.kakao_ingest.get_pending_kakao_upload_messages")
def test_ingest_uploaded_message_uses_existing_pipeline(
    mock_pending,
    _mock_has_document,
    _mock_embed,
    mock_add_document,
    mock_convert,
    mock_mark,
    _mock_count,
):
    mock_pending.return_value = [
        {
            "client_message_hash": "b" * 64,
            "room": "제주 생활 정보방",
            "sender": "여행자",
            "sent_at_text": "2026-07-13 02:16:00",
            "content": "공항으로 같이 이동하실 분을 구합니다.",
        }
    ]

    ingested, filtered, pending = ingest_uploaded_messages()

    assert (ingested, filtered, pending) == (1, 0, 0)
    mock_add_document.assert_called_once()
    mock_convert.assert_called_once()
    mock_mark.assert_called_once_with("b" * 64, "ingested")


@patch("app.api.routes.ingest.ingest_uploaded_messages", return_value=(1, 0, 0))
@patch("app.api.routes.ingest.enqueue_uploaded_messages", return_value=1)
@patch("app.api.routes.ingest.count_pending_kakao_upload_messages", return_value=1)
def test_upload_route_accepts_its_dedicated_bearer_secret(
    _mock_count, _mock_enqueue, _mock_ingest
):
    previous = settings.kakao_upload_secret
    settings.kakao_upload_secret = "test-upload-secret"
    try:
        response = upload_kakao_messages(
            KakaoUploadRequest(
                messages=[
                    KakaoUploadMessage(
                        room="제주 생활 정보방",
                        sender="여행자",
                        sent_at_text="2026-07-13 02:16:00",
                        content="공항으로 같이 이동하실 분을 구합니다.",
                        client_message_hash="c" * 64,
                    )
                ]
            ),
            authorization="Bearer test-upload-secret",
        )
    finally:
        settings.kakao_upload_secret = previous

    assert response.data.accepted == 1
    assert response.data.pending == 1
