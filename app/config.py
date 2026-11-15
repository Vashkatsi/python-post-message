from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        frozen=True,
    )

    publish_timeout_seconds: float = Field(default=20, gt=0)
    http_timeout_seconds: float = Field(default=10, gt=0)
    access_check_timeout_seconds: float = Field(default=10, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
