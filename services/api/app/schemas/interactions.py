from datetime import datetime

from pydantic import BaseModel, Field, model_validator


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
    """모임 등록. jejumate/backend(POST /posts/party)와 동일하게 4자리 관리 코드를 발급한다.

    starts_at/ends_at은 사용자가 직접 고른 로컬(Asia/Seoul 기준) 날짜·시간 문자열이다
    (예: "2026-07-10T14:30", <input type="datetime-local"> 값 그대로). 과거엔 등록
    시점을 시작 시각으로 고정하고 duration_minutes로 마감 시각을 계산했지만, 사용자가
    시작·마감을 직접 지정하도록 바뀌었다.
    """

    category: str = Field(min_length=1, max_length=30)
    title: str = Field(min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=300)
    place_label: str = Field(min_length=1, max_length=60)
    capacity: int = Field(ge=1)
    starts_at: str
    ends_at: str
    nickname: str = Field(min_length=2, max_length=20)
    anonymous_id: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def _check_time_order(self) -> "MeetingCreateRequest":
        try:
            starts = datetime.fromisoformat(self.starts_at)
            ends = datetime.fromisoformat(self.ends_at)
        except ValueError as exc:
            raise ValueError("시작/마감 시각 형식이 올바르지 않습니다") from exc
        if ends <= starts:
            raise ValueError("마감 시각은 시작 시각보다 늦어야 합니다")
        return self


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
    owner_secret: str | None = Field(default=None, max_length=4)


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
    supports_answer: bool | None = None


class RagAskResponse(BaseModel):
    answer: str
    sources: list[RagSource]
    safety_note: str
    suggestions: list[str]
    query_log_id: str | None = None
    persisted: bool = False
    # 신뢰도 검증: gpt-5-mini가 만든 답변이 근거와 실제로 부합하는지 자체 검증한 결과.
    # confidence_grade: "none"(근거 없음, LLM 미호출) / "high"(근거 전부 부합) /
    # "medium"(일부만 부합) / "low"(근거 있었지만 하나도 부합 안 함, 환각 의심).
    confidence_grade: str = "none"
    verified_source_count: int = 0
    total_source_count: int = 0
