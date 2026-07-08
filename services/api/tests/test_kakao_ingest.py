"""카톡 수집 노이즈 필터·개인정보 마스킹 테스트.

실제 배포 DB(1,971건) 품질 점검에서 발견한 사례를 그대로 회귀 테스트로 옮겼다:
- 카카오톡 시스템 알림("~님이 들어왔습니다/나갔습니다", "메시지가 삭제되었습니다")이
  노이즈 필터를 통과해 실제 대화와 섞여 저장되던 문제(1,971건 중 223건, 11.3%).
- 유선전화(지역번호)·인스타그램 핸들이 마스킹되지 않던 문제(광고성 콘텐츠 사례에서 발견).
"""
from __future__ import annotations

from app.services.kakao_ingest import _is_noise, _strip_system_notices, mask_personal_info


def test_strip_system_notices_removes_trailing_join_notice():
    result = _strip_system_notices("지금 돌아가실분~ 벙찐 튜브님이 들어왔습니다.")
    assert result == "지금 돌아가실분~"


def test_strip_system_notices_removes_deleted_message_notice():
    result = _strip_system_notices("10시는 시간이 늦어서.. 죄송합니다 ㅜㅜ 메시지가 삭제되었습니다.")
    assert result == "10시는 시간이 늦어서.. 죄송합니다 ㅜㅜ"


def test_strip_system_notices_removes_multiple_leave_notices():
    result = _strip_system_notices("예민한 팬더주니어님이 나갔습니다.응원하는 니니즈님이 나갔습니다.")
    assert result == ""


def test_strip_system_notices_preserves_real_content_before_question_mark():
    # '?' 뒤에 바로 시스템 알림이 붙어도 앞의 실제 질문 문장은 지워지면 안 된다.
    result = _strip_system_notices("본점 가셨나요?? 예민한 팬더주니어님이 나갔습니다.")
    assert result == "본점 가셨나요??"


def test_pure_system_notice_becomes_noise_after_stripping():
    stripped = _strip_system_notices("메시지가 삭제되었습니다.")
    assert _is_noise(stripped)


def test_mixed_content_with_notice_is_not_noise_after_stripping():
    stripped = _strip_system_notices("9시쯤 탑동에서 기숙사 넘어가실 분 2명 구해요!! 티비 보는 라이언님이 들어왔습니다.")
    assert stripped == "9시쯤 탑동에서 기숙사 넘어가실 분 2명 구해요!!"
    assert not _is_noise(stripped)


def test_mask_personal_info_masks_landline_number():
    result = mask_personal_info("자세한 내용은 제주대 교육혁신과로 연락해주시기 바랍니다. 064-754-2023")
    assert "064-754-2023" not in result
    assert "[연락처 비공개]" in result


def test_mask_personal_info_masks_instagram_handle():
    result = mask_personal_info("예약 및 문의 : 인스타그램 DM\n인스타그램 : @muzigae_yacht")
    assert "@muzigae_yacht" not in result
    assert "[SNS 계정 비공개]" in result


def test_mask_personal_info_still_masks_mobile_and_url():
    result = mask_personal_info("연락은 010-1234-5678로, 자세한 건 https://example.com 참고")
    assert "010-1234-5678" not in result
    assert "https://example.com" not in result
    assert "[연락처 비공개]" in result
    assert "[링크 비공개]" in result
