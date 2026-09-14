import os

from alembic.config import Config


def test_database_url_is_read_from_environment(monkeypatch):
    database_url = (
        "postgresql+psycopg://user:password@localhost:5432/testdb"
    )

    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config("alembic.ini")

    assert os.getenv("DATABASE_URL") == database_url