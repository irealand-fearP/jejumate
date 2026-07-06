"""API 요청/응답 Pydantic 스키마."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class PartyPostCreate(BaseModel):
    """파티 등록 폼(화면흐름.md 6장). 카테고리는 LLM 분류 없이 사용자가 직접 고른다."""

    category: Literal["ride", "drink", "run", "walk", "tour"]
    content: str = Field(min_length=1)
    capacity: int = Field(ge=1)
    deadline_minutes: int = Field(ge=1)
    nickname: str = Field(min_length=1)


class PartyPostCreateResponse(BaseModel):
    id: str
    owner_secret: str
    deadline: datetime
