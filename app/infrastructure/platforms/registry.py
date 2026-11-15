from collections.abc import Callable

import httpx2

from app.application.ports import Clock, Publisher
from app.config import Settings
from app.infrastructure.platforms.bluesky import BlueskyPublisher
from app.infrastructure.platforms.devto import DevtoPublisher
from app.infrastructure.platforms.github_gist import GithubGistPublisher
from app.infrastructure.platforms.mastodon import MastodonPublisher
from app.infrastructure.platforms.telegram import TelegramPublisher
from app.infrastructure.platforms.unconfigured import UnconfiguredPublisher


def build_publishers(
    settings: Settings, client: httpx2.AsyncClient, clock: Clock
) -> list[Publisher]:
    return [
        _configured_or_placeholder(
            MastodonPublisher.name,
            settings.mastodon,
            lambda config: MastodonPublisher(client, config),
            ("MASTODON__ACCESS_TOKEN",),
        ),
        _configured_or_placeholder(
            TelegramPublisher.name,
            settings.telegram,
            lambda config: TelegramPublisher(client, config),
            ("TELEGRAM__BOT_TOKEN", "TELEGRAM__CHANNEL_USERNAME"),
        ),
        _configured_or_placeholder(
            BlueskyPublisher.name,
            settings.bluesky,
            lambda config: BlueskyPublisher(client, config, clock),
            ("BLUESKY__HANDLE", "BLUESKY__APP_PASSWORD"),
        ),
        _configured_or_placeholder(
            GithubGistPublisher.name,
            settings.github_gist,
            lambda config: GithubGistPublisher(client, config),
            ("GITHUB_GIST__TOKEN",),
        ),
        _configured_or_placeholder(
            DevtoPublisher.name,
            settings.devto,
            lambda config: DevtoPublisher(client, config),
            ("DEVTO__API_KEY",),
        ),
    ]


def _configured_or_placeholder[ConfigT](
    name: str,
    config: ConfigT | None,
    factory: Callable[[ConfigT], Publisher],
    required_settings: tuple[str, ...],
) -> Publisher:
    if config is None:
        return UnconfiguredPublisher(name, required_settings)
    return factory(config)
