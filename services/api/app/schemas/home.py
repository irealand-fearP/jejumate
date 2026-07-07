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
    starts_at: str
    ends_at: str
    place_label: str
    host: MeetingHost
    capacity: int
    approved_count: int
    status: str
    cta: MeetingCta


class ActivitySummary(BaseModel):
    active_people_count: int
    thumbnail_keys: list[str] = Field(default_factory=list)


class RagStrip(BaseModel):
    title: str
    subtitle: str
    suggestions: list[str]


class HomePolicy(BaseModel):
    id: str
    title: str
    summary: str
    region: str
    field: str
    status: str
    application_end_date: str
    d_day: int
    official_url: str


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
    policies: list[HomePolicy]
