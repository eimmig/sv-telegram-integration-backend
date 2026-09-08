"""Orchestrates one incoming n8n-normalized message into either a follow-up
question (a required field or catalog choice is still missing) or a
captured-so-far result. Two kinds of follow-up question exist: a free-text
field (odd/stake, see extraction.py) and a numbered catalog choice
(sport/league/market/betting_house, resolved against the tenant's
bets-service catalog via catalog_client.py - see docs/DECISIONS-LOG.md
2026-09-08 "Resolucao de catalogo... no fluxo Telegram"). Actually submitting
the resolved bet to bets-service is main.py's job (bets_client.py), not
this module's - "complete" here means "every field and catalog id resolved,
ready to submit", not "already submitted".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import redis

from telegram_integration.catalog_client import CatalogEntry, fetch_catalog
from telegram_integration.conversation import (
    CatalogQuestion,
    PendingBet,
    clear_pending,
    get_pending,
    save_pending,
)
from telegram_integration.extraction import REQUIRED_FIELDS, ExtractedBet, extract_fields, parse_direct_answer
from telegram_integration.i18n import get_message

_QUESTION_KEYS = {
    "odd": "ask_odd",
    "stake": "ask_stake",
}

# Order is arbitrary but fixed - betting_house first since it's the only one
# extraction.py ever has a best-effort name for (fuzzy match may skip the
# question entirely); sport/league/market always ask, per the decision that
# nothing is ever auto-chosen for them.
_CATALOG_ORDER = ("betting_house", "sport", "league", "market")
_CATALOG_RESOURCE = {
    "betting_house": "betting-houses",
    "sport": "sports",
    "league": "leagues",
    "market": "markets",
}
_CATALOG_RESULT_FIELD = {
    "betting_house": "bettingHouseId",
    "sport": "sportId",
    "league": "leagueId",
    "market": "marketId",
}
_CATALOG_QUESTION_KEYS = {
    "betting_house": "ask_betting_house_choice",
    "sport": "ask_sport",
    "league": "ask_league",
    "market": "ask_market",
}
_CATALOG_EMPTY_KEYS = {
    "betting_house": "catalog_empty_betting_house",
    "sport": "catalog_empty_sport",
    "league": "catalog_empty_league",
    "market": "catalog_empty_market",
}


@dataclass
class CaptureResult:
    status: Literal["pending", "complete", "blocked"]
    message: str
    bet: dict[str, str | None] | None = None


def _merge(existing: dict[str, str | None], newly_extracted: ExtractedBet) -> dict[str, str | None]:
    """Always returns the full ExtractedBet shape (every field name present,
    even as None) - a sparse dict here would make the "bet" output
    inconsistent between a single complete message (full shape) and a
    multi-turn conversation (would otherwise only contain whichever fields
    were actually ever assigned a value).
    """
    merged = dict(existing)
    for name, value in newly_extracted.__dict__.items():
        if merged.get(name) is None:
            merged[name] = value
    return merged


def _format_choice_question(question_key: str, options: list[CatalogEntry], language_code: str | None) -> str:
    base = get_message(question_key, language_code)
    listing = "\n".join(f"{index + 1}. {option.name}" for index, option in enumerate(options))
    return f"{base}\n{listing}"


def _fuzzy_match_betting_house(name: str | None, options: list[CatalogEntry]) -> CatalogEntry | None:
    """Case-insensitive exact match only - a substring match (e.g. "Bet" against
    both "Betano" and "Betfair") would be ambiguous, and a wrong silent match is
    worse than falling back to the same numbered-list question used for the
    catalogs that are never guessed at all.
    """
    if name is None:
        return None
    lowered = name.strip().lower()
    matches = [option for option in options if option.name.strip().lower() == lowered]
    return matches[0] if len(matches) == 1 else None


def _parse_choice_index(text: str, option_count: int) -> int | None:
    stripped = text.strip()
    if not stripped.isdigit():
        return None
    value = int(stripped)
    return value - 1 if 1 <= value <= option_count else None


def _advance_catalog(
    client: redis.Redis,
    telegram_user_id: str,
    language_code: str | None,
    correlation_id: str,
    fields: dict[str, str | None],
    catalog_ids: dict[str, str],
) -> CaptureResult:
    for catalog_type in _CATALOG_ORDER:
        result_field = _CATALOG_RESULT_FIELD[catalog_type]
        if result_field in catalog_ids:
            continue

        options = fetch_catalog(_CATALOG_RESOURCE[catalog_type], telegram_user_id, correlation_id)
        if options is None:
            # Gateway/bets-service unreachable - not the user's fault. Save
            # progress so far so a retry doesn't lose the fields/catalog ids
            # already resolved this conversation.
            save_pending(client, telegram_user_id, PendingBet(fields=fields, catalog_ids=catalog_ids))
            error_message = get_message("generic_error", language_code)
            return CaptureResult(status="blocked", message=error_message, bet=None)

        if not options:
            clear_pending(client, telegram_user_id)
            return CaptureResult(
                status="blocked",
                message=get_message(_CATALOG_EMPTY_KEYS[catalog_type], language_code),
                bet=None,
            )

        if catalog_type == "betting_house":
            match = _fuzzy_match_betting_house(fields.get("betting_house"), options)
            if match is not None:
                catalog_ids[result_field] = match.id
                continue

        save_pending(
            client,
            telegram_user_id,
            PendingBet(
                fields=fields,
                catalog_ids=catalog_ids,
                awaiting_catalog=CatalogQuestion(
                    catalog_type=catalog_type,
                    options=[{"id": option.id, "name": option.name} for option in options],
                ),
            ),
        )
        question = _format_choice_question(_CATALOG_QUESTION_KEYS[catalog_type], options, language_code)
        return CaptureResult(status="pending", message=question, bet=None)

    # Not cleared here on purpose: main.py still needs to submit the bet to
    # bets-service. If that submission fails, the resolved fields/catalog ids
    # stay in Redis so the user can retry with any message instead of
    # re-answering every question - this branch already has nothing left to
    # resolve, so the next call reaches "complete" again immediately.
    save_pending(client, telegram_user_id, PendingBet(fields=fields, catalog_ids=catalog_ids))
    confirmation = get_message("bet_captured", language_code)
    return CaptureResult(status="complete", message=confirmation, bet={**fields, **catalog_ids})


def _handle_catalog_answer(
    client: redis.Redis,
    telegram_user_id: str,
    language_code: str | None,
    correlation_id: str,
    text: str,
    pending: PendingBet,
) -> CaptureResult:
    question = pending.awaiting_catalog
    assert question is not None  # only called when it isn't
    index = _parse_choice_index(text, len(question.options))

    if index is None:
        options = [CatalogEntry(id=option["id"], name=option["name"]) for option in question.options]
        question_key = _CATALOG_QUESTION_KEYS[question.catalog_type]
        invalid_prefix = get_message("invalid_catalog_choice", language_code)
        repeated_question = _format_choice_question(question_key, options, language_code)
        return CaptureResult(status="pending", message=f"{invalid_prefix}\n{repeated_question}", bet=None)

    chosen = question.options[index]
    catalog_ids = dict(pending.catalog_ids)
    catalog_ids[_CATALOG_RESULT_FIELD[question.catalog_type]] = chosen["id"]
    fields = dict(pending.fields)
    return _advance_catalog(client, telegram_user_id, language_code, correlation_id, fields, catalog_ids)


def handle_message(
    client: redis.Redis,
    telegram_user_id: str,
    language_code: str | None,
    text: str,
    correlation_id: str,
) -> CaptureResult:
    pending = get_pending(client, telegram_user_id)

    if pending is not None and pending.awaiting_catalog is not None:
        return _handle_catalog_answer(client, telegram_user_id, language_code, correlation_id, text, pending)

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

    if fields.get("bet_date") is None:
        # Not extracted from text on purpose (see extraction.py's module
        # docstring) - a bet-slip normally shows the event's date, not
        # necessarily when the bet was placed, and today is right far more
        # often than a guess from the slip would be.
        fields["bet_date"] = datetime.now(UTC).date().isoformat()

    catalog_ids = dict(pending.catalog_ids) if pending is not None else {}
    return _advance_catalog(client, telegram_user_id, language_code, correlation_id, fields, catalog_ids)
