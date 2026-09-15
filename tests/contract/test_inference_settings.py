import pytest
from pydantic import ValidationError

from packages.common.settings import Settings


def test_inference_settings_have_safe_defaults(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:password@localhost:5432/db",
    )

    settings = Settings(_env_file=None)

    assert settings.inference_base_url == "http://localhost:8001/v1"
    assert settings.inference_model == "Qwen/Qwen3-VL-8B-Instruct"
    assert settings.inference_api_key == "local-dev"
    assert settings.inference_timeout_seconds == 60.0


def test_inference_settings_can_be_overridden(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:password@localhost:5432/db",
    )
    monkeypatch.setenv(
        "INFERENCE_BASE_URL",
        "http://qwen:8000/v1",
    )
    monkeypatch.setenv(
        "INFERENCE_MODEL",
        "custom-qwen-model",
    )
    monkeypatch.setenv(
        "INFERENCE_API_KEY",
        "secret-key",
    )
    monkeypatch.setenv(
        "INFERENCE_TIMEOUT_SECONDS",
        "90",
    )

    settings = Settings()

    assert settings.inference_base_url == "http://qwen:8000/v1"
    assert settings.inference_model == "custom-qwen-model"
    assert settings.inference_api_key == "secret-key"
    assert settings.inference_timeout_seconds == 90.0


def test_inference_timeout_must_be_positive(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:password@localhost:5432/db",
    )
    monkeypatch.setenv(
        "INFERENCE_TIMEOUT_SECONDS",
        "0",
    )

    with pytest.raises(ValidationError):
        Settings()