"""0002_create_applications

applications 테이블 생성 (기획서 3장-8, 태스크11). 파티 참여 신청을 담는다.
post_id는 posts.id를 참조하며, 신청/승인 데이터는 RAG 임베딩·검색 대상이
아니므로(기획서 3장-11) embedding 컬럼을 두지 않는다.

Revision ID: 0002_create_applications
Revises: 0001_create_posts
Create Date: 2026-07-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_create_applications"
down_revision: Union[str, None] = "0001_create_posts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("nickname", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_applications_status"),
    )
    op.create_index("ix_applications_post_id", "applications", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_applications_post_id", table_name="applications")
    op.drop_table("applications")
