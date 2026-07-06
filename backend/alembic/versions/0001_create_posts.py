"""0001_create_posts

posts 테이블 생성 (기획서 3장 기능명세 + 6장 카테고리 체계 기준).
post_type(party/info)·capacity·deadline·owner_secret을 처음부터 포함해
Day 2.5(파티 모집 기능) 때 컬럼 추가 재작업이 없게 한다.

Revision ID: 0001_create_posts
Revises:
Create Date: 2026-07-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0001_create_posts"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "posts",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("post_type", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author_nickname", sa.String(), nullable=False),
        sa.Column("original_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chat_room_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        # party 전용 (info 글은 전부 NULL)
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_secret", sa.String(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("source IN ('kakao', 'user_post')", name="ck_posts_source"),
        sa.CheckConstraint("post_type IN ('party', 'info')", name="ck_posts_post_type"),
        sa.CheckConstraint(
            "category IN ('ride','drink','run','walk','tour','food','cafe','stay','living','qna')",
            name="ck_posts_category",
        ),
        sa.CheckConstraint("status IN ('active', 'closed')", name="ck_posts_status"),
    )

    op.create_index("ix_posts_category", "posts", ["category"])
    op.create_index("ix_posts_post_type", "posts", ["post_type"])
    op.create_index("ix_posts_status", "posts", ["status"])

    # 벡터 유사도 검색용 인덱스 (코사인 거리 기준)
    op.execute(
        "CREATE INDEX ix_posts_embedding_cosine ON posts "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_posts_embedding_cosine")
    op.drop_index("ix_posts_status", table_name="posts")
    op.drop_index("ix_posts_post_type", table_name="posts")
    op.drop_index("ix_posts_category", table_name="posts")
    op.drop_table("posts")
