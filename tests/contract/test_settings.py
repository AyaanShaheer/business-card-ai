from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.common.settings import Settings


def test_settings_load_database_url(monkeypatch):
    database_url = (
        "postgresql+psycopg://user:password@localhost:5432/testdb"
    )

    monkeypatch.setenv("DATABASE_URL", database_url)

    settings = Settings()

    assert str(settings.database_url) == database_url


def test_settings_reject_missing_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_have_safe_default_limits(monkeypatch):
    database_url = (
        "postgresql+psycopg://user:password@localhost:5432/testdb"
    )

    monkeypatch.setenv("DATABASE_URL", database_url)

    settings = Settings()

    assert settings.max_file_size_mb > 0
    assert settings.max_files_per_job > 0


def test_settings_respect_environment_overrides(monkeypatch):
    database_url = (
        "postgresql+psycopg://user:password@localhost:5432/testdb"
    )

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "20")
    monkeypatch.setenv("MAX_FILES_PER_JOB", "100")

    settings = Settings()

    assert settings.max_file_size_mb == 20
    assert settings.max_files_per_job == 100


def test_settings_reject_invalid_file_limit(monkeypatch):
    database_url = (
        "postgresql+psycopg://user:password@localhost:5432/testdb"
    )

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "0")

    with pytest.raises(ValidationError):
        Settings()