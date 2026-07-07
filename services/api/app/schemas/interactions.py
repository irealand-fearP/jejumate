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
