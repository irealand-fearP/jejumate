from pydantic import BaseModel, Field


class NicknameRequest(BaseModel):
    nickname: str = Field(min_length=2, max_length=20)
    anonymous_id: str | None = Field(default=None, max_length=80)


class NicknameResponse(BaseModel):
    profile_id: str
    nickname: str
    anonymous_id: str
    public_note: str
    persisted: bool = False


class MeetingApplicationRequest(BaseModel):
    nickname: str = Field(min_length=2, max_length=20)
    message: str | None = Field(default=None, max_length=160)
    anonymous_id: str | None = Field(default=None, max_length=80)


class MeetingApplicationResponse(BaseModel):
    application_id: str
    meeting_id: str
    status: str
    public_alias: str
    privacy_note: str
    next_step: str
    persisted: bool = False


class MeetingCreateRequest(BaseModel):
    """모임 등록. jejumate/backend(POST /posts/party)와 동일하게 4자리 관리 코드를 발급한다."""

    category: str = Field(min_length=1, max_length=30)
    title: str = Field(min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=300)
    place_label: str = Field(min_length=1, max_length=60)
    capacity: int = Field(ge=1)
    duration_minutes: int = Field(ge=1)
    nickname: str = Field(min_length=2, max_length=20)
    anonymous_id: str | None = Field(default=None, max_length=80)


class MeetingCreateResponse(BaseModel):
    meeting_id: str
    owner_secret: str
    starts_at: str
    ends_at: str
    persisted: bool = False


class MeetingStatusResponse(BaseModel):
    capacity: int
    approved_count: int
    is_closed: bool


class MeetingApplicationListItem(BaseModel):
    # QA 발견(Fork 통합 QA, QA-REPORT.md): 신청 생성 응답(MeetingApplicationResponse)은
    # application_id 필드를 쓰는데 이 목록 응답만 id를 써서 필드명이 갈렸었다.
    # application_id로 표준화.
    application_id: str | None = None
    nickname: str
    message: str | None = None
    status: str | None = None


class MeetingApplicationListResponse(BaseModel):
    authorized: bool
    applications: list[MeetingApplicationListItem]


class MeetingApplicationDecisionResponse(BaseModel):
    application_id: str
    meeting_id: str
    status: str


class ApplicationDeleteResponse(BaseModel):
    """신청자 본인이 자기 신청을 취소/삭제(코덱스 원본의 신규 기능을 이식).
    호스트 액션이 아니라 신청자 본인 액션이므로 owner_secret이 아니라 신청 생성 시
    쓴 anonymous_id로 본인 확인한다."""

    application_id: str
    meeting_id: str
    status: str


class ApplicantNotification(BaseModel):
    """내 신청 상태 알림(코덱스 원본의 신규 기능을 이식). 승인/거절/대기 상태에 맞는
    안내 문구를 서버가 만들어 내려준다."""

    application_id: str
    meeting_id: str
    meeting_title: str
    starts_at: str
    place_label: str
    host_nickname: str
    status: str
    title: str
    body: str
    created_at: str
    updated_at: str


class ApplicantNotificationsResponse(BaseModel):
    notifications: list[ApplicantNotification]


class ChatMessageRequest(BaseModel):
    nickname: str = Field(min_length=2, max_length=20)
    content: str = Field(min_length=1, max_length=500)
    anonymous_id: str | None = Field(default=None, max_length=80)


class ChatMessage(BaseModel):
    id: str
    meeting_id: str
    sender_nickname: str
    content: str
    created_at: str


class ChatMessagesResponse(BaseModel):
    meeting_id: str
    messages: list[ChatMessage]
    notice: str
    persisted: bool = False


class RagAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=120)
    anonymous_id: str | None = Field(default=None, max_length=80)


class RagSource(BaseModel):
    title: str
    url: str
    source_type: str


class RagAskResponse(BaseModel):
    answer: str
    sources: list[RagSource]
    safety_note: str
    suggestions: list[str]
    query_log_id: str | None = None
    persisted: bool = False
