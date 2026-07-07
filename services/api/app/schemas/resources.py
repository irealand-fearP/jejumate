from pydantic import BaseModel, Field

from app.schemas.home import HomeMeeting


class MeetingsResponse(BaseModel):
    filters: list[str]
    meetings: list[HomeMeeting]
    privacy_note: str


class ProfilePreviewResponse(BaseModel):
    public_fields: list[str] = Field(default_factory=list)
    hidden_fields: list[str] = Field(default_factory=list)
    default_interests: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class BoardPost(BaseModel):
    id: str
    category: str
    title: str
    body: str
    author_nickname: str
    created_at: str
    comment_count: int = 0
    can_delete: bool = False
    comments: list["BoardComment"] = Field(default_factory=list)


class BoardComment(BaseModel):
    id: str
    post_id: str
    body: str
    author_nickname: str
    created_at: str


class BoardPostCreateRequest(BaseModel):
    category: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=2, max_length=80)
    body: str = Field(min_length=2, max_length=500)
    author_nickname: str = Field(min_length=2, max_length=20)
    anonymous_id: str | None = Field(default=None, max_length=80)


class BoardCommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=300)
    author_nickname: str = Field(min_length=2, max_length=20)
    anonymous_id: str | None = Field(default=None, max_length=80)


class BoardReportRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=120)
    anonymous_id: str | None = Field(default=None, max_length=80)


class BoardDeleteResponse(BaseModel):
    post_id: str
    status: str


class BoardReportResponse(BaseModel):
    target_type: str
    target_id: str
    status: str


class BoardResponse(BaseModel):
    categories: list[str]
    posts: list[BoardPost]
    notice: str
