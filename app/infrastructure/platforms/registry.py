from collections.abc import Callable

import httpx2

from app.application.ports import Publisher
from app.config import Settings
from app.infrastructure.platforms.mastodon import MastodonPublisher
from app.infrastructure.platforms.unconfigured import UnconfiguredPublisher


def build_publishers(settings: Settings, client: httpx2.AsyncClient) -> list[Publisher]:
    return [
        _configured_or_placeholder(
            MastodonPublisher.name,
            settings.mastodon,
            lambda config: MastodonPublisher(client, config),
            ("MASTODON__ACCESS_TOKEN",),
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
