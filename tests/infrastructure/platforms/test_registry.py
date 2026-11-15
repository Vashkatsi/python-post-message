import httpx2
import pytest
from pydantic import SecretStr

from app.application.ports import PublicationError
from app.config import Settings
from app.domain.message import Message
from app.infrastructure.clock import SystemClock
from app.infrastructure.platforms.mastodon import MastodonPublisher, MastodonSettings
from app.infrastructure.platforms.registry import build_publishers
from app.infrastructure.platforms.unconfigured import UnconfiguredPublisher

EXPECTED_PLATFORMS = [
    "Mastodon",
    "Telegram",
    "Bluesky",
    "GitHub Gist",
    "DEV Community",
    "Telegraph",
    "Hugging Face",
]


def unconfigured_settings() -> Settings:
    return Settings.model_construct(
        publish_timeout_seconds=20,
        http_timeout_seconds=10,
        access_check_timeout_seconds=10,
        mastodon=None,
        telegram=None,
        bluesky=None,
        github_gist=None,
        devto=None,
        telegraph=None,
        huggingface=None,
    )


def test_registers_every_platform_as_placeholder_without_credentials(
    client: httpx2.AsyncClient,
) -> None:
    publishers = build_publishers(unconfigured_settings(), client, SystemClock())

    assert [publisher.name for publisher in publishers] == EXPECTED_PLATFORMS
    assert all(isinstance(publisher, UnconfiguredPublisher) for publisher in publishers)


async def test_placeholder_names_the_missing_settings(client: httpx2.AsyncClient) -> None:
    telegram = build_publishers(unconfigured_settings(), client, SystemClock())[1]

    with pytest.raises(
        PublicationError,
        match=r"^Not configured, set TELEGRAM__BOT_TOKEN, TELEGRAM__CHANNEL_USERNAME$",
    ):
        await telegram.publish(Message("Hello https://example.com"))


def test_builds_real_publisher_for_configured_platform(client: httpx2.AsyncClient) -> None:
    settings = unconfigured_settings().model_copy(
        update={"mastodon": MastodonSettings(access_token=SecretStr("token"))}
    )

    mastodon = build_publishers(settings, client, SystemClock())[0]

    assert isinstance(mastodon, MastodonPublisher)
