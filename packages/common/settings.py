from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: PostgresDsn

    max_file_size_mb: int = Field(
        default=10,
        gt=0,
    )

    max_files_per_job: int = Field(
        default=50,
        gt=0,
    )