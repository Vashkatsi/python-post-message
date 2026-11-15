import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlsplit

MAX_MESSAGE_LENGTH = 200

_LINK_CANDIDATE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_TRAILING_ASCII_PUNCTUATION = frozenset(".,;:!?)]}'\"")
_TRAILING_UNICODE_CATEGORIES = frozenset({"Pe", "Pf", "Pi"})
_BRACKET_PAIRS = {")": "(", "]": "[", "}": "{"}
_INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf"})
_HEADLINE_EDGE_CHARACTERS = " .,:;-|/"
_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$",
    re.IGNORECASE,
)


class InvalidMessageError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Message:
    text: str
    cta_url: str = field(init=False)

    def __post_init__(self) -> None:
        text = self.text.strip()
        if not text:
            raise InvalidMessageError("Message must not be empty")
        if len(text) > MAX_MESSAGE_LENGTH:
            raise InvalidMessageError(
                f"Message must not exceed {MAX_MESSAGE_LENGTH} characters, got {len(text)}"
            )
        if any(_is_invisible(character) for character in text):
            raise InvalidMessageError("Message must not contain invisible or control characters")
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "cta_url", _extract_single_cta_url(text))

    @property
    def headline(self) -> str:
        text_without_link = " ".join(word for word in self.text.split() if self.cta_url not in word)
        return (
            text_without_link.strip(_HEADLINE_EDGE_CHARACTERS)
            or urlsplit(self.cta_url).hostname
            or self.cta_url
        )


def _extract_single_cta_url(text: str) -> str:
    links: list[str] = [
        _strip_trailing_punctuation(match) for match in _LINK_CANDIDATE.findall(text)
    ]
    if len(links) != 1:
        raise InvalidMessageError(f"Message must contain exactly one CTA link, found {len(links)}")
    link = links[0]
    if not _is_valid_web_url(link):
        raise InvalidMessageError(f"CTA link is not a valid absolute http(s) URL: {link}")
    return link


def _is_invisible(character: str) -> bool:
    return unicodedata.category(character) in _INVISIBLE_CATEGORIES and not character.isspace()


def _strip_trailing_punctuation(candidate: str) -> str:
    link = candidate
    while link and _is_trailing_punctuation(link[-1]):
        opener = _BRACKET_PAIRS.get(link[-1])
        if opener is not None and link.count(opener) >= link.count(link[-1]):
            return link
        link = link[:-1]
    return link


def _is_trailing_punctuation(character: str) -> bool:
    if character in _TRAILING_ASCII_PUNCTUATION:
        return True
    category = unicodedata.category(character)
    return category in _TRAILING_UNICODE_CATEGORIES or (
        category == "Po" and not character.isascii()
    )


def _is_valid_hostname_text(hostname: str) -> bool:
    return bool(hostname) and all(
        character.isalnum() or character in "-." for character in hostname
    )


def _is_valid_web_url(candidate: str) -> bool:
    try:
        parts = urlsplit(candidate)
        port_is_valid = parts.port is None or parts.port > 0
        hostname = parts.hostname or ""
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError, ValueError:
        return False
    return (
        parts.scheme in {"http", "https"}
        and port_is_valid
        and parts.username is None
        and parts.password is None
        and _is_valid_hostname_text(hostname)
        and _HOSTNAME.fullmatch(ascii_hostname) is not None
    )
