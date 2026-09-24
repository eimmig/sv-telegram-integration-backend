import json
from functools import lru_cache
from pathlib import Path

SUPPORTED_LOCALES = ("pt-BR", "en-US", "es")
DEFAULT_LOCALE = "pt-BR"

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"


@lru_cache
def _load_locale(locale: str) -> dict[str, str]:
    path = _LOCALES_DIR / f"{locale}.json"
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def resolve_locale(language_code: str | None) -> str:
    if not language_code:
        return DEFAULT_LOCALE
    subtag = language_code.strip().lower().split("-")[0]
    for locale in SUPPORTED_LOCALES:
        if locale.lower().split("-")[0] == subtag:
            return locale
    return DEFAULT_LOCALE


def get_message(key: str, language_code: str | None) -> str:
    locale = resolve_locale(language_code)
    return _load_locale(locale)[key]
