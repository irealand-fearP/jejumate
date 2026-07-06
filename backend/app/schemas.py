"""API 요청/응답 Pydantic 스키마."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    post_type: str
    category: str
    content: str
    author_nickname: str
    original_timestamp: datetime
    chat_room_name: str | None
    status: str
    capacity: int | None
    deadline: datetime | None
    created_at: datetime


class SearchRequest(BaseModel):
    query: str
    category: str | None = None


class EvidenceOut(BaseModel):
    id: str
    content: str
    author_nickname: str
    original_timestamp: datetime
    source: str
    category: str
    post_type: str


class SearchResponse(BaseModel):
    answer: str
    evidence: list[EvidenceOut]
