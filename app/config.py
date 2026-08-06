from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    app_name: str = "Copilote IA QA"
    app_env: str = "development"
    app_version: str = "0.4.1"
    log_level: str = "INFO"
    database_url: str = "sqlite+pysqlite:///./copilote_qa.db"
    policy_path: str = "policies/qa-rules-v1.0.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
