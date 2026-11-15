from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.infrastructure.platforms.bluesky import BlueskySettings
from app.infrastructure.platforms.devto import DevtoSettings
from app.infrastructure.platforms.github_gist import GithubGistSettings
from app.infrastructure.platforms.huggingface import HuggingFaceSettings
from app.infrastructure.platforms.mastodon import MastodonSettings
from app.infrastructure.platforms.telegram import TelegramSettings
from app.infrastructure.platforms.telegraph import TelegraphSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
    )

    publish_timeout_seconds: float = Field(default=20, gt=0)
    http_timeout_seconds: float = Field(default=10, gt=0)
    access_check_timeout_seconds: float = Field(default=10, gt=0)

    mastodon: MastodonSettings | None = None
    huggingface: HuggingFaceSettings | None = None
    telegraph: TelegraphSettings | None = None
    devto: DevtoSettings | None = None
    github_gist: GithubGistSettings | None = None
    bluesky: BlueskySettings | None = None
    telegram: TelegramSettings | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
