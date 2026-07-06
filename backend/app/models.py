"""posts 테이블 ORM 모델 (기획서 3장·6장 기준, 0001_create_posts 마이그레이션과 1:1)."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base, FlexibleVector

SOURCE_VALUES = ("kakao", "user_post")
POST_TYPE_VALUES = ("party", "info")
STATUS_VALUES = ("active", "closed")
# 6장 카테고리 체계: party 5종 + info 5종 = 10종
CATEGORY_VALUES = (
    "ride", "drink", "run", "walk", "tour",      # party
    "food", "cafe", "stay", "living", "qna",     # info
)
APPLICATION_STATUS_VALUES = ("pending", "approved", "rejected")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    source: Mapped[str] = mapped_column(String, nullable=False)
    post_type: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_nickname: Mapped[str] = mapped_column(String, nullable=False)
    original_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    chat_room_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")

    # party 전용 필드 (info 글은 전부 null)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_secret: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    embedding: Mapped[Optional[list]] = mapped_column(FlexibleVector(1536), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        CheckConstraint(f"source IN {SOURCE_VALUES}", name="ck_posts_source"),
        CheckConstraint(f"post_type IN {POST_TYPE_VALUES}", name="ck_posts_post_type"),
        CheckConstraint(f"category IN {CATEGORY_VALUES}", name="ck_posts_category"),
        CheckConstraint(f"status IN {STATUS_VALUES}", name="ck_posts_status"),
    )


class Application(Base):
    """파티 참여 신청(태스크13·14). RAG 임베딩·검색 대상이 아니다(기획서 3장-11)."""

    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id"), nullable=False)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        CheckConstraint(f"status IN {APPLICATION_STATUS_VALUES}", name="ck_applications_status"),
    )
