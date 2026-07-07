from app.schemas.resources import MeetingsResponse, PoliciesResponse, ProfilePreviewResponse
from app.services.home_service import get_home_data


def get_meetings_data() -> MeetingsResponse:
    home = get_home_data()
    return MeetingsResponse(
        filters=home.meeting_filters,
        meetings=home.meetings,
        privacy_note="모임 신청 시 공개되는 정보는 닉네임과 신청 상태입니다.",
    )


def get_policies_data() -> PoliciesResponse:
    return PoliciesResponse(
        policies=get_home_data().policies,
        last_synced_at="2026-07-07T09:00:00+09:00",
        source_note="정책 정보는 RAG 답변에 사용되더라도 최종 신청 전 공식 링크 확인이 필요합니다.",
    )


def get_profile_preview_data() -> ProfilePreviewResponse:
    return ProfilePreviewResponse(
        public_fields=["닉네임", "관심사", "참여 신청 상태"],
        hidden_fields=["실명", "전화번호", "생년월일", "인증 원본"],
        default_interests=["밥친구", "작업", "러닝", "정책"],
        safety_notes=[
            "공개 프로필은 닉네임 중심으로 노출됩니다.",
            "실명 인증 정보는 안전 확인과 운영자 검토에만 사용됩니다.",
            "신고/차단 정보는 상대 사용자에게 공개하지 않습니다.",
        ],
    )
