import pytest

from app.domain.message import MAX_MESSAGE_LENGTH, InvalidMessageError, Message


@pytest.mark.parametrize(
    ("text", "expected_url"),
    [
        ("Grow your visibility https://example.com", "https://example.com"),
        ("Read more at https://example.com/path?ref=1.", "https://example.com/path?ref=1"),
        ("(see http://sub.example.co.uk:8080/page)", "http://sub.example.co.uk:8080/page"),
        ("Visit https://пример.рф now", "https://пример.рф"),
        ("Visit “https://example.com/path”", "https://example.com/path"),
        ("Читайте «https://example.com»…", "https://example.com"),
        ("Docs: https://example.com/a/", "https://example.com/a/"),
        (
            "See https://en.wikipedia.org/wiki/Python_(programming_language)",
            "https://en.wikipedia.org/wiki/Python_(programming_language)",
        ),
        (
            "(see https://en.wikipedia.org/wiki/Python_(programming_language))",
            "https://en.wikipedia.org/wiki/Python_(programming_language)",
        ),
        ("Line one\nhttps://example.com", "https://example.com"),
    ],
)
def test_extracts_the_single_cta_link(text: str, expected_url: str) -> None:
    assert Message(text).cta_url == expected_url


def test_strips_surrounding_whitespace() -> None:
    assert Message("  Hello https://example.com  ").text == "Hello https://example.com"


def test_accepts_message_of_exactly_max_length() -> None:
    link = " https://example.com"
    text = "a" * (MAX_MESSAGE_LENGTH - len(link)) + link

    assert Message(text).text == text


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", "must not be empty"),
        ("   ", "must not be empty"),
        ("a" * MAX_MESSAGE_LENGTH + " https://example.com", "must not exceed 200 characters"),
        ("No link here", "exactly one CTA link, found 0"),
        ("Two https://a.com and https://b.com", "exactly one CTA link, found 2"),
        ("Bare www.example.com", r"not a valid absolute http\(s\) URL"),
        ("Local https://localhost", r"not a valid absolute http\(s\) URL"),
        ("Creds https://user:secret@example.com", r"not a valid absolute http\(s\) URL"),
        ("Port https://example.com:0", r"not a valid absolute http\(s\) URL"),
        ("Broken https://exa_mple.com", r"not a valid absolute http\(s\) URL"),
        ("Quote inside https://exa”mple.com", r"not a valid absolute http\(s\) URL"),
        ("Hidden https://exa\u200bmple.com", "invisible or control characters"),
        ("Joined https://a.com\u200bhttps://evil.com", "invisible or control characters"),
    ],
)
def test_rejects_invalid_messages(text: str, reason: str) -> None:
    with pytest.raises(InvalidMessageError, match=reason):
        Message(text)


def test_message_is_immutable() -> None:
    message = Message("Hello https://example.com")

    with pytest.raises(AttributeError):
        message.text = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("text", "headline"),
    [
        ("Grow your   visibility: https://example.com", "Grow your visibility"),
        ("Read https://example.com/a today.", "Read today"),
        ("Visit (https://example.com), please", "Visit please"),
        ("- https://www.example.com -", "www.example.com"),
    ],
)
def test_headline_is_the_text_without_the_link(text: str, headline: str) -> None:
    assert Message(text).headline == headline
