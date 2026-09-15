from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    inference_base_url: str = Field(
        default="http://localhost:8001/v1",
        min_length=1,
    )

    inference_model: str = Field(
        default="Qwen/Qwen3-VL-8B-Instruct",
        min_length=1,
    )

    inference_api_key: str = Field(
        default="local-dev",
        min_length=1,
    )

    inference_timeout_seconds: float = Field(
        default=60.0,
        gt=0,
    )