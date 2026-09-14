from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


ROOT_DIR = Path(__file__).resolve().parents[2]

@pytest.fixture(autouse=True)
def clear_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)


def _alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_database_can_upgrade_to_head(tmp_path):
    database_path = tmp_path / "migration_test.db"
    database_url = f"sqlite:///{database_path}"

    config = _alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert {
        "jobs",
        "documents",
        "extractions",
        "leads",
        "exports",
    }.issubset(tables)


def test_database_can_downgrade_to_base(tmp_path):
    database_path = tmp_path / "migration_test.db"
    database_url = f"sqlite:///{database_path}"

    config = _alembic_config(database_url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(database_url)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert "jobs" not in tables
    assert "documents" not in tables
    assert "extractions" not in tables
    assert "leads" not in tables
    assert "exports" not in tables


def test_initial_schema_has_expected_job_columns(tmp_path):
    database_path = tmp_path / "migration_test.db"
    database_url = f"sqlite:///{database_path}"

    config = _alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)

    columns = {
        column["name"]
        for column in inspector.get_columns("jobs")
    }

    assert {
        "id",
        "status",
        "total_documents",
        "processed_documents",
        "successful_documents",
        "failed_documents",
        "review_documents",
        "created_at",
        "started_at",
        "completed_at",
    }.issubset(columns)