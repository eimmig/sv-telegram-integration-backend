"""Loads the bot's user-facing messages by locale, selected from the Telegram
update's `language_code` (see docs/CONVENTIONS.md "Internacionalizacao (i18n)").
"""

import json
from functools import lru_cache
from pathlib import Path

SUPPORTED_LOCALES = ("pt-BR", "en-US", "es")
DEFAULT_LOCALE = "pt-BR"

_LOCALES_DIR = Path(__file__).resolve().parents[2] / "locales"


@lru_cache
def _load_locale(locale: str) -> dict[str, str]:
    path = _LOCALES_DIR / f"{locale}.json"
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def resolve_locale(language_code: str | None) -> str:
    """Maps a Telegram `language_code` (e.g. "en", "pt-br", "es-AR") to one of the
    three supported locales, falling back to `DEFAULT_LOCALE` when unrecognized.
    """
    if not language_code:
        return DEFAULT_LOCALE
    prefix = language_code.strip().lower()[:2]
    for locale in SUPPORTED_LOCALES:
        if locale.lower().startswith(prefix):
            return locale
    return DEFAULT_LOCALE


def get_message(key: str, language_code: str | None) -> str:
    locale = resolve_locale(language_code)
    return _load_locale(locale)[key]
