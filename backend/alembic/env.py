"""
alembic 마이그레이션 환경 설정.

로컬에 실제 Postgres(docker)나 Supabase 접속정보(.env의 DATABASE_URL)가 없으면
online 모드(실제 DB 접속)로는 실행할 수 없다. 대신 `--sql` 옵션(offline 모드)으로
생성될 DDL 자체는 DB 접속 없이도 확인할 수 있다:

    alembic upgrade head --sql

실제 Supabase/docker postgres가 준비되면 .env에 DATABASE_URL을 넣고
`alembic upgrade head` 로 그대로 적용한다.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db import Base
from app import models  # noqa: F401  (Base.metadata에 테이블 등록)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = settings.database_url
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
