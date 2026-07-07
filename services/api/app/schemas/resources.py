from pydantic import BaseModel, Field

from app.schemas.home import HomeMeeting, HomePolicy


class MeetingsResponse(BaseModel):
    filters: list[str]
    meetings: list[HomeMeeting]
    privacy_note: str


class PoliciesResponse(BaseModel):
    policies: list[HomePolicy]
    last_synced_at: str
    source_note: str


class ProfilePreviewResponse(BaseModel):
    public_fields: list[str] = Field(default_factory=list)
    hidden_fields: list[str] = Field(default_factory=list)
    default_interests: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
