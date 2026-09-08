"""Generic heuristic extraction of bet fields from free text (typed by the user,
or OCR'd from a bet-slip screenshot - see `ocr.py`). No bookmaker-specific
template and no real bet-slip sample was available to validate against (see
docs/DECISIONS-LOG.md 2026-09-08): only the fields with a genuinely universal
lexical pattern (a decimal odd, a currency-prefixed stake, a date) are extracted
with real confidence. `sport`/`league`/`market`/`team1`/`team2` are intentionally
never guessed here - there is no reliable pattern for free-form entity names
without a real sample to validate against, and `betting_house` is only matched
against a short list of well-known Brazilian bookmakers, not extracted freely.
Everything this module can't fill goes through the conversational fallback
(see `conversation.py`).

`bets-service` expects catalog IDs (bettingHouseId/sportId/leagueId/marketId),
not names - resolving an extracted name against the tenant's catalog is
`feat-004`'s responsibility, not this module's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ODD_PATTERN = re.compile(r"(?<![\d.,])(\d{1,3}[.,]\d{2})(?![\d.,])")
_STAKE_PATTERN = re.compile(r"(?:R\$|\$)\s*(\d+(?:[.,]\d{2})?)", re.IGNORECASE)
_DATE_PATTERN = re.compile(r"\b(\d{2})[/-](\d{2})[/-](\d{2,4})\b")
_ODD_KEYWORD_LINE = re.compile(r"(?:odd|cota[cç][aã]o)\D{0,10}(\d{1,3}[.,]\d{2})", re.IGNORECASE)

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
)

REQUIRED_FIELDS = ("odd", "stake", "bet_date")


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
    for candidate in _ODD_PATTERN.finditer(text):
        value = float(candidate.group(1).replace(",", "."))
        if 1.01 <= value <= 1000:
            return candidate.group(1).replace(",", ".")
    return None


def _extract_stake(text: str) -> str | None:
    match = _STAKE_PATTERN.search(text)
    if match is None:
        return None
    return match.group(1).replace(",", ".")


def _extract_bet_date(text: str) -> str | None:
    match = _DATE_PATTERN.search(text)
    if match is None:
        return None
    day, month, year = match.groups()
    if len(year) == 2:
        year = f"20{year}"
    return f"{year}-{month}-{day}"


def _extract_betting_house(text: str) -> str | None:
    lowered = text.lower()
    for house in _KNOWN_BETTING_HOUSES:
        if house.lower() in lowered:
            return house
    return None


_BARE_NUMBER_PATTERN = re.compile(r"\d{1,3}[.,]\d{1,2}|\d+")


def parse_direct_answer(field: str, text: str) -> str:
    """Normalizes a reply the user typed directly in answer to a specific
    conversational-fallback question (see `orchestration.py`) - more lenient
    than the free-text search in `extract_fields`, since the whole message is
    known to be the answer for that one field (e.g. a bare "50" for stake,
    without the R$ prefix `_extract_stake` requires when scanning free text).
    Falls back to the stripped raw text when nothing recognizable is found,
    rather than losing the user's answer.
    """
    stripped = text.strip()
    if field in ("odd", "stake"):
        match = _BARE_NUMBER_PATTERN.search(stripped)
        return match.group(0).replace(",", ".") if match else stripped
    if field == "bet_date":
        return _extract_bet_date(stripped) or stripped
    return stripped


def extract_fields(text: str) -> ExtractedBet:
    return ExtractedBet(
        odd=_extract_odd(text),
        stake=_extract_stake(text),
        bet_date=_extract_bet_date(text),
        betting_house=_extract_betting_house(text),
    )
