from pathlib import Path

import pytest

from app.config import Settings


def test_platform_is_not_configured_when_its_credentials_are_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("MASTODON__ACCESS_TOKEN=\n")

    assert Settings().mastodon is None


def test_reads_nested_platform_settings_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MASTODON__ACCESS_TOKEN", "secret")
    monkeypatch.setenv("MASTODON__BASE_URL", "https://fosstodon.org")

    mastodon = Settings().mastodon

    assert mastodon is not None
    assert mastodon.access_token.get_secret_value() == "secret"
    assert str(mastodon.base_url) == "https://fosstodon.org/"
