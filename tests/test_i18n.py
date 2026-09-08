import pytest

from telegram_integration.i18n import get_message, resolve_locale

CASES = [
    ("pt-BR", "pt-BR"),
    ("pt-br", "pt-BR"),
    ("pt", "pt-BR"),
    ("en-US", "en-US"),
    ("en", "en-US"),
    ("es-AR", "es"),
    ("es", "es"),
]


@pytest.mark.parametrize(("language_code", "expected_locale"), CASES)
def test_resolve_locale_maps_telegram_language_code(language_code: str, expected_locale: str) -> None:
    assert resolve_locale(language_code) == expected_locale


def test_resolve_locale_falls_back_to_default_when_missing() -> None:
    assert resolve_locale(None) == "pt-BR"


def test_resolve_locale_falls_back_to_default_when_unrecognized() -> None:
    assert resolve_locale("ru") == "pt-BR"


def test_resolve_locale_does_not_match_on_single_character_prefix() -> None:
    # "e" is not a real Telegram language_code, but must not accidentally match
    # "en-US" via a loose startswith comparison against the 2-letter subtag.
    assert resolve_locale("e") == "pt-BR"


def test_get_message_returns_different_text_per_locale() -> None:
    pt_br = get_message("generic_error", "pt-BR")
    en_us = get_message("generic_error", "en")
    es = get_message("generic_error", "es")

    assert pt_br != en_us
    assert pt_br != es
    assert en_us != es
