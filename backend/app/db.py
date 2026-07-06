"""
SQLAlchemy 공용 설정.

FlexibleVector: Postgres에서는 pgvector의 실제 vector(dim) 컬럼을 쓰고,
그 외 dialect(SQLite 등, 로컬 docker/postgres가 없는 개발 환경에서 테스트용)에서는
JSON으로 저장해 같은 모델 코드로 양쪽을 다 지원한다. 실제 서비스(Supabase)는
항상 Postgres이므로 운영 코드 경로는 pgvector.sqlalchemy.Vector 그대로 탄다.
"""
from pgvector.sqlalchemy import Vector
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import JSON, TypeDecorator

from app.config import settings


class Base(DeclarativeBase):
    pass


class FlexibleVector(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int, *args, **kwargs):
        self.dim = dim
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())


engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)
