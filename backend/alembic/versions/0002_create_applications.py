"""0002_create_applications

번호만 선점(발번)한 스텁. 실제 테이블 정의(post_id·nickname·message·status 등)는
Day 2.5(파티 모집 신청/승인 기능) 작업 때 채운다. 0001 이후 마이그레이션 번호
충돌을 막기 위해 미리 파일만 만들어둔다.

Revision ID: 0002_create_applications
Revises: 0001_create_posts
Create Date: 2026-07-06

"""
from typing import Sequence, Union

revision: str = "0002_create_applications"
down_revision: Union[str, None] = "0001_create_posts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass  # Day 2.5에 applications 테이블 생성 코드 작성


def downgrade() -> None:
    pass
