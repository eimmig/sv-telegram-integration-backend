"""Orchestrates one incoming n8n-normalized message into either a follow-up
question (a required field is still missing) or a captured-so-far result.
Resolving extracted names against the tenant's bets-service catalog, and
actually registering the bet, is feat-004's job - this module only produces
the raw extracted/collected fields (see extraction.py's module docstring).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import redis

from telegram_integration.conversation import PendingBet, clear_pending, get_pending, save_pending
from telegram_integration.extraction import REQUIRED_FIELDS, ExtractedBet, extract_fields, parse_direct_answer
from telegram_integration.i18n import get_message

_QUESTION_KEYS = {
    "odd": "ask_odd",
    "stake": "ask_stake",
    "bet_date": "ask_bet_date",
}


@dataclass
class CaptureResult:
    status: Literal["pending", "complete"]
    message: str
    bet: dict[str, str | None] | None = None


def _merge(existing: dict[str, str | None], newly_extracted: ExtractedBet) -> dict[str, str | None]:
    merged = dict(existing)
    for name, value in newly_extracted.__dict__.items():
        if merged.get(name) is None and value is not None:
            merged[name] = value
    return merged


def handle_message(
    client: redis.Redis,
    telegram_user_id: str,
    language_code: str | None,
    text: str,
) -> CaptureResult:
    pending = get_pending(client, telegram_user_id)

    if pending is not None and pending.awaiting_field is not None:
        # The user was asked a specific question - their whole reply is the answer
        # to that field, not run back through the generic heuristic extractor.
        fields = dict(pending.fields)
        fields[pending.awaiting_field] = parse_direct_answer(pending.awaiting_field, text)
    else:
        fields = _merge(pending.fields if pending is not None else {}, extract_fields(text))

    missing = [name for name in REQUIRED_FIELDS if fields.get(name) is None]

    if missing:
        next_field = missing[0]
        save_pending(client, telegram_user_id, PendingBet(fields=fields, awaiting_field=next_field))
        question = get_message(_QUESTION_KEYS[next_field], language_code)
        return CaptureResult(status="pending", message=question, bet=None)

    clear_pending(client, telegram_user_id)
    confirmation = get_message("bet_captured", language_code)
    return CaptureResult(status="complete", message=confirmation, bet=fields)
