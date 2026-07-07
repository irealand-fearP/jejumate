from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow, dict_row

from app.core.config import settings


def _psycopg_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def get_connection() -> Iterator[Connection[DictRow]]:
    connection = psycopg.connect(
        _psycopg_url(settings.database_url),
        connect_timeout=2,
        row_factory=dict_row,
    )
    try:
        yield connection
    finally:
        connection.close()
