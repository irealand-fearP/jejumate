from __future__ import annotations

from app.services.kakao_export import parse_kakao_export_text, post_chat_messages


SAMPLE = """제주 생활 정보방 님과 카카오톡 대화
저장한 날짜 : 2026-07-13 02:48:08

--------------- 2026년 7월 13일 월요일 ---------------
채팅방 안내 문구는 메시지가 아닙니다.
[여행자] [오전 2:16] 공항으로 같이 이동하실 분을 구해요.
[도우미] [오후 12:05] 첫째 줄
둘째 줄
"""


def test_parse_export_ignores_preamble_and_parses_messages():
    exported = parse_kakao_export_text(SAMPLE)

    assert exported.room == "제주 생활 정보방"
    assert len(exported.messages) == 2
    assert exported.messages[0].sender == "여행자"
    assert exported.messages[0].sent_at.isoformat() == "2026-07-13T02:16:00"
    assert exported.messages[1].sent_at.isoformat() == "2026-07-13T12:05:00"
    assert exported.messages[1].content == "첫째 줄\n둘째 줄"


def test_client_hash_is_stable_across_overlapping_exports():
    first = parse_kakao_export_text(SAMPLE).messages[0]
    second = parse_kakao_export_text(SAMPLE).messages[0]

    assert first.client_message_hash == second.client_message_hash
    assert len(first.client_message_hash) == 64


def test_client_hash_changes_when_message_changes():
    original = parse_kakao_export_text(SAMPLE).messages[0]
    changed = parse_kakao_export_text(SAMPLE.replace("같이 이동", "택시로 이동")).messages[0]

    assert original.client_message_hash != changed.client_message_hash


def test_upload_requires_secret_before_network_call():
    message = parse_kakao_export_text(SAMPLE).messages[0]

    try:
        post_chat_messages("https://example.invalid/chats", [message], upload_secret="")
    except ValueError as exc:
        assert "비밀키" in str(exc)
    else:
        raise AssertionError("API 키 없이 업로드가 허용됐습니다.")
