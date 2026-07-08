from pydantic import BaseModel, Field


class ProfileChip(BaseModel):
    label: str
    is_set: bool


class PrivacyChip(BaseModel):
    label: str
    is_verified: bool


class MeetingHost(BaseModel):
    profile_id: str
    nickname: str
    badge: str | None = None


class MeetingCta(BaseModel):
    label: str
    enabled: bool
    requires_auth: bool


class HomeMeeting(BaseModel):
    id: str
    category: str
    title: str
    description: str | None = None
    starts_at: str
    ends_at: str
    place_label: str
    host: MeetingHost
    capacity: int
    approved_count: int
    status: str
    cta: MeetingCta
    # 인기/NEW 배지 판정은 백엔드 단일 계산(local_store._meeting_from_row)만 신뢰한다.
    # 프론트는 이 값을 그대로 렌더링만 하고 자체 판단 로직을 두지 않는다.
    is_popular: bool
    is_new: bool
    # 'service'(서비스 내 작성) | 'kakao_chat'(오픈채팅 수집→콜드스타트 자동 변환).
    # 후자는 호스트가 없는 외부 글이라 신청/승인 흐름을 붙이지 않는다(cta.enabled=False).
    source: str = "service"


class ActivitySummary(BaseModel):
    active_people_count: int
    thumbnail_keys: list[str] = Field(default_factory=list)


class RagStrip(BaseModel):
    title: str
    subtitle: str
    suggestions: list[str]


class MeetingSummary(BaseModel):
    open_count: int


class HomeResponse(BaseModel):
    profile_chip: ProfileChip
    privacy_chip: PrivacyChip
    meeting_summary: MeetingSummary
    meeting_filters: list[str]
    meetings: list[HomeMeeting]
    activity_summary: ActivitySummary
    rag_strip: RagStrip
