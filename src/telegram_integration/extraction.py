from __future__ import annotations

import re
from dataclasses import dataclass

_CURRENCY_AMOUNT_PATTERN = re.compile(r"(?:R\$|\$)\s*\d+(?:[.,]\d{2})?", re.IGNORECASE)
_ODD_PATTERN = re.compile(r"(?<![\d.,])(\d{1,3}[.,]\d{2})(?![\d.,])")
_STAKE_PATTERN = re.compile(r"(?:R\$|\$)\s*(\d+(?:[.,]\d{2})?)", re.IGNORECASE)
_ODD_KEYWORD_LINE = re.compile(r"(?:odd|cota[cç][aã]o)\D{0,10}(\d{1,3}[.,]\d{2})", re.IGNORECASE)
_ODD_AT_PATTERN = re.compile(r"@\s*(\d{1,3}[.,]\d{2})")

_KNOWN_BETTING_HOUSES = (
    "Bet365",
    "Betano",
    "Sportingbet",
    "KTO",
    "Betfair",
    "Betnacional",
    "Pixbet",
    "Novibet",
    "Stake",
    "Vupi",
)

REQUIRED_FIELDS = ("odd", "stake")


@dataclass
class ExtractedBet:
    odd: str | None = None
    stake: str | None = None
    bet_date: str | None = None
    betting_house: str | None = None
    sport: str | None = None
    league: str | None = None
    market: str | None = None
    team1: str | None = None
    team2: str | None = None

    def missing_required_fields(self) -> list[str]:
        return [name for name in REQUIRED_FIELDS if getattr(self, name) is None]


def _extract_odd(text: str) -> str | None:
    keyword_match = _ODD_KEYWORD_LINE.search(text)
    if keyword_match:
        return keyword_match.group(1).replace(",", ".")
    at_match = _ODD_AT_PATTERN.search(text)
    if at_match:
        return at_match.group(1).replace(",", ".")
    text_without_currency = _CURRENCY_AMOUNT_PATTERN.sub("", text)
    for candidate in _ODD_PATTERN.finditer(text_without_currency):
        value = float(candidate.group(1).replace(",", "."))
        if 1.01 <= value <= 1000:
            return candidate.group(1).replace(",", ".")
    return None


def _extract_stake(text: str) -> str | None:
    match = _STAKE_PATTERN.search(text)
    if match is None:
        return None
    return match.group(1).replace(",", ".")


def _extract_betting_house(text: str) -> str | None:
    lowered = text.lower()
    for house in _KNOWN_BETTING_HOUSES:
        if house.lower() in lowered:
            return house
    return None


_BARE_NUMBER_PATTERN = re.compile(r"\d{1,3}[.,]\d{1,2}|\d+")


def parse_direct_answer(field: str, text: str) -> str:
    stripped = text.strip()
    if field in ("odd", "stake"):
        match = _BARE_NUMBER_PATTERN.search(stripped)
        return match.group(0).replace(",", ".") if match else stripped
    return stripped


def extract_fields(text: str) -> ExtractedBet:
    return ExtractedBet(
        odd=_extract_odd(text),
        stake=_extract_stake(text),
        betting_house=_extract_betting_house(text),
    )
