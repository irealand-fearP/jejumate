"""모임 생성 시각(starts_at/ends_at) 관련 검증 로직 테스트.

'마감 시간'(30분/1시간/2시간 버튼) 대신 사용자가 시작·마감 시각을 직접 입력하게
바뀌면서 생긴 요구사항: 마감이 시작보다 늦어야 한다는 최소 유효성과, 오프셋 없는
로컬(KST) 문자열을 UTC로 정확히 변환하는지를 확인한다.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.repositories.local_store import _local_kst_to_utc_iso
from app.schemas.interactions import MeetingCreateRequest


def _base_payload(**overrides):
    payload = {
        "category": "move",
        "title": "공항 택시팟",
        "description": None,
        "place_label": "제주공항",
        "capacity": 3,
        "starts_at": "2026-07-10T14:00",
        "ends_at": "2026-07-10T15:00",
        "nickname": "바당이",
        "anonymous_id": None,
    }
    payload.update(overrides)
    return payload


def test_meeting_create_request_accepts_valid_time_order():
    request = MeetingCreateRequest(**_base_payload())
    assert request.starts_at == "2026-07-10T14:00"


def test_meeting_create_request_rejects_ends_before_starts():
    with pytest.raises(ValidationError):
        MeetingCreateRequest(**_base_payload(starts_at="2026-07-10T15:00", ends_at="2026-07-10T14:00"))


def test_meeting_create_request_rejects_equal_times():
    with pytest.raises(ValidationError):
        MeetingCreateRequest(**_base_payload(starts_at="2026-07-10T14:00", ends_at="2026-07-10T14:00"))


def test_quick_match_rejects_a_duration_longer_than_one_hour():
    with pytest.raises(ValidationError):
        MeetingCreateRequest(
            **_base_payload(category="quick", starts_at="2026-07-10T14:00", ends_at="2026-07-10T15:01")
        )


def test_meeting_create_request_rejects_malformed_time():
    with pytest.raises(ValidationError):
        MeetingCreateRequest(**_base_payload(starts_at="not-a-date"))


def test_local_kst_to_utc_iso_converts_nine_hour_offset():
    # 한국은 UTC+9 고정(서머타임 없음) — KST 14:00은 UTC 05:00이어야 한다.
    result = _local_kst_to_utc_iso("2026-07-10T14:00")
    assert result == "2026-07-10T05:00:00+00:00"
