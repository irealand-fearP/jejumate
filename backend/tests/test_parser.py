"""
카카오톡 txt 파서 + 대화 단위 청킹 테스트 (태스크3).

형식: `[닉네임] [오후 2:11] 내용`. 입장/퇴장/삭제/공지봇 등 노이즈 제거와
멀티라인 메시지(줄바꿈으로 이어지는 긴 메시지) 처리, 같은 화자·5분 이내
연속 발화 병합(청킹)까지 검증한다.
"""
from datetime import datetime, timedelta

from app.parser import chunk_messages, parse_kakao_txt

SAMPLE_PATH = "/home/ai/agent-company/data/sample_kakao_chat.txt"


def test_parses_single_message_with_am_pm_time():
    text = (
        "--------------- 2026년 7월 6일 월요일 ---------------\n"
        "[배부른 춘식이] [오후 2:18] 2시반 함덕해수욕장 택시 같이 타실 분 있나용 !!!\n"
    )
    messages = parse_kakao_txt(text)
    assert len(messages) == 1
    assert messages[0].nickname == "배부른 춘식이"
    assert messages[0].content == "2시반 함덕해수욕장 택시 같이 타실 분 있나용 !!!"
    assert messages[0].timestamp == datetime(2026, 7, 6, 14, 18)


def test_am_pm_boundary_conversion():
    text = (
        "--------------- 2026년 7월 6일 월요일 ---------------\n"
        "[가] [오전 12:05] 자정 넘은 메시지\n"
        "[나] [오후 12:30] 정오 메시지\n"
        "[다] [오전 11:59] 오전 마지막\n"
    )
    messages = parse_kakao_txt(text)
    assert [m.timestamp.hour for m in messages] == [0, 12, 11]
    assert [m.timestamp.minute for m in messages] == [5, 30, 59]


def test_filters_enter_leave_deleted_and_bot_notice():
    text = (
        "2026 제주대학교 하기 계절학기 학점교류방 님과 카카오톡 대화\n"
        "저장한 날짜 : 2026-07-06 16:29:59\n"
        "\n"
        "--------------- 2026년 7월 6일 월요일 ---------------\n"
        "우는 춘식이님이 들어왔습니다.타인, 기관 등의 사칭에 유의해 주세요.\n"
        "[오픈채팅봇] [오후 2:11] 공지글을 반드시 확인하세요!!\n"
        "[축하하는 라이언] [오후 2:12] 구하셧나요?\n"
        "메시지가 삭제되었습니다.\n"
        "[하루] [오후 2:19] 택시팟인가요?\n"
        "나른한 니니즈님이 나갔습니다.\n"
    )
    messages = parse_kakao_txt(text)
    nicknames = [m.nickname for m in messages]
    assert nicknames == ["축하하는 라이언", "하루"]


def test_multiline_message_continuation_joins_into_previous_message():
    text = (
        "--------------- 2026년 7월 6일 월요일 ---------------\n"
        "[전알여] [오후 4:05] 톡게시판 '글 공유': 코코 컬처클럽\n"
        "(7/17, 7/18)\n"
        "\n"
        "https://jnuluncation.notion.site/abc\n"
        "[우는 라이언] [오후 4:05] 다음 메시지\n"
    )
    messages = parse_kakao_txt(text)
    assert len(messages) == 2
    assert messages[0].nickname == "전알여"
    assert "코코 컬처클럽" in messages[0].content
    assert "(7/17, 7/18)" in messages[0].content
    assert "https://jnuluncation.notion.site/abc" in messages[0].content
    assert messages[1].content == "다음 메시지"


def test_date_separator_advances_date_for_following_messages():
    text = (
        "--------------- 2026년 7월 6일 월요일 ---------------\n"
        "[가] [오후 11:50] 첫째날 밤\n"
        "--------------- 2026년 7월 7일 화요일 ---------------\n"
        "[가] [오전 12:10] 둘째날 새벽\n"
    )
    messages = parse_kakao_txt(text)
    assert messages[0].timestamp == datetime(2026, 7, 6, 23, 50)
    assert messages[1].timestamp == datetime(2026, 7, 7, 0, 10)


def test_parses_real_sample_file_without_error():
    with open(SAMPLE_PATH, encoding="utf-8") as f:
        text = f.read()
    messages = parse_kakao_txt(text)

    assert len(messages) > 50
    assert all(m.nickname != "오픈채팅봇" for m in messages)
    assert not any("삭제되었습니다" == m.content for m in messages)
    # 실제 대화 중 알려진 메시지 하나가 정확히 파싱되는지 확인
    assert any("함덕해수욕장 택시" in m.content for m in messages)


def test_chunk_merges_same_speaker_within_five_minutes():
    base = datetime(2026, 7, 6, 14, 0)
    text_messages = [
        ("긁적이는 춘식이", base, "그럼 지금 나갈게오"),
        ("긁적이는 춘식이", base + timedelta(minutes=1), "욥"),
    ]
    from app.parser import ParsedMessage

    messages = [ParsedMessage(n, t, c) for n, t, c in text_messages]
    chunks = chunk_messages(messages)

    assert len(chunks) == 1
    assert chunks[0].nickname == "긁적이는 춘식이"
    assert chunks[0].message_count == 2
    assert "그럼 지금 나갈게오" in chunks[0].content
    assert "욥" in chunks[0].content
    assert chunks[0].start_timestamp == base
    assert chunks[0].end_timestamp == base + timedelta(minutes=1)


def test_chunk_does_not_merge_different_speaker():
    from app.parser import ParsedMessage

    base = datetime(2026, 7, 6, 14, 0)
    messages = [
        ParsedMessage("가", base, "안녕"),
        ParsedMessage("나", base + timedelta(minutes=1), "반가워"),
    ]
    chunks = chunk_messages(messages)
    assert len(chunks) == 2


def test_strips_control_characters_from_nickname():
    """실제 샘플에 백스페이스(0x08) 등 제어문자가 낀 닉네임이 있어(65·168행),
    같은 사람이 다른 닉네임으로 파싱되지 않도록 제어문자를 제거한다."""
    text = (
        "--------------- 2026년 7월 6일 월요일 ---------------\n"
        "[손 흔드는 \x08팬더주니어] [오후 3:02] 첫 메시지\n"
        "[손 흔드는 팬더주니어] [오후 3:57] 둘째 메시지\n"
    )
    messages = parse_kakao_txt(text)
    assert {m.nickname for m in messages} == {"손 흔드는 팬더주니어"}


def test_chunk_does_not_merge_beyond_five_minute_gap():
    from app.parser import ParsedMessage

    base = datetime(2026, 7, 6, 14, 0)
    messages = [
        ParsedMessage("가", base, "첫 메시지"),
        ParsedMessage("가", base + timedelta(minutes=6), "6분 뒤 메시지"),
    ]
    chunks = chunk_messages(messages)
    assert len(chunks) == 2
