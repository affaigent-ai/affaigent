from contextlib import contextmanager

from psycopg import connect
from psycopg.rows import dict_row

from app.config import settings


@contextmanager
def get_db():
    with connect(
        settings.postgres_conninfo,
        row_factory=dict_row,
        autocommit=True,
    ) as conn:
        yield conn
