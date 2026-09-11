"""Generic heuristic extraction of bet fields from free text (typed by the user,
or OCR'd from a bet-slip screenshot - see `ocr.py`). No bookmaker-specific
template - validated against 5 real screenshots from real Brazilian bookmakers
(Bet365, Betano, Novibet, Vupi, and one unidentified brand - not committed to
the repo, see docs/DECISIONS-LOG.md 2026-09-08 for the findings) after the
first pass had none to check against: `odd` extraction succeeds cleanly for a
plain bold-text style
(2/5 samples); the other 3/5 fail safely (OCR either garbled the boosted/colored
odd digits entirely, or dropped the decimal point/`@` symbol) and correctly fall
back to asking the user, rather than capturing a wrong value - that degradation
is the intended design, not a defect to chase with more fragile regex. `stake`
and `betting_house` (a short list of known Brazilian bookmakers) are similarly
best-effort. `sport`/`league`/`market`/`team1`/`team2` are intentionally never
guessed - no reliable pattern for free-form entity names. `bet_date` is not
extracted from text at all (see `orchestration.py`): a real bet-slip normally
shows the event's date, not necessarily when the bet was placed, and asking the
user to retype a date they can see is worse UX than defaulting to "now".
Everything this module can't fill goes through the conversational fallback
(see `conversation.py`).

`bets-service` expects catalog IDs (bettingHouseId/sportId/leagueId/marketId),
not names - resolving an extracted name against the tenant's catalog is
`feat-004`'s responsibility, not this module's.
"""

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
    # A stake/payout amount (e.g. "R$5,00") also matches the bare 2-decimal
    # pattern below - strip currency-prefixed amounts first so they can never
    # be mistaken for the odd (real bug found against exemplo_eds.png, where
    # "R$2.50" - the stake - would otherwise win over the real odd "5.50").
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
    return stripped


def extract_fields(text: str) -> ExtractedBet:
    return ExtractedBet(
        odd=_extract_odd(text),
        stake=_extract_stake(text),
        betting_house=_extract_betting_house(text),
    )
