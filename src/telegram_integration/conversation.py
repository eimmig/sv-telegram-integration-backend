"""Conversation state for the follow-up-question fallback: when field extraction
(see `extraction.py`) can't confidently fill every field, the bot asks the user
one field at a time and needs to remember, between separate webhook calls, what
was already collected. Backed by the Redis instance already provisioned in
`infra/` for `stats-service` (see docs/DECISIONS-LOG.md 2026-09-08).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import redis

PENDING_TTL_SECONDS = 15 * 60
_KEY_PREFIX = "telegram:pending-bet:"


def build_redis_client() -> redis.Redis:  # pragma: no cover - thin env-var wiring, no branch to test
    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        password=os.environ.get("REDIS_PASSWORD") or None,
        decode_responses=True,
    )


@dataclass
class CatalogQuestion:
    """A numbered-list question already asked, with the exact options shown -
    snapshotted so a later numeric reply resolves against what the user actually
    saw, not whatever the tenant's catalog looks like by the time they answer
    (which could have gained/lost entries in between).
    """

    catalog_type: str
    options: list[dict[str, str]]


@dataclass
class PendingBet:
    fields: dict[str, str | None] = field(default_factory=dict)
    awaiting_field: str | None = None
    catalog_ids: dict[str, str] = field(default_factory=dict)
    awaiting_catalog: CatalogQuestion | None = None


def get_pending(client: redis.Redis, telegram_user_id: str) -> PendingBet | None:
    raw = client.get(_KEY_PREFIX + telegram_user_id)
    if raw is None:
        return None
    data = json.loads(raw)
    awaiting_catalog_data = data.get("awaiting_catalog")
    awaiting_catalog = (
        CatalogQuestion(
            catalog_type=awaiting_catalog_data["catalog_type"],
            options=awaiting_catalog_data["options"],
        )
        if awaiting_catalog_data is not None
        else None
    )
    return PendingBet(
        fields=data["fields"],
        awaiting_field=data.get("awaiting_field"),
        catalog_ids=data.get("catalog_ids", {}),
        awaiting_catalog=awaiting_catalog,
    )


def save_pending(client: redis.Redis, telegram_user_id: str, pending: PendingBet) -> None:
    payload = json.dumps(
        {
            "fields": pending.fields,
            "awaiting_field": pending.awaiting_field,
            "catalog_ids": pending.catalog_ids,
            "awaiting_catalog": (
                {
                    "catalog_type": pending.awaiting_catalog.catalog_type,
                    "options": pending.awaiting_catalog.options,
                }
                if pending.awaiting_catalog is not None
                else None
            ),
        }
    )
    client.set(_KEY_PREFIX + telegram_user_id, payload, ex=PENDING_TTL_SECONDS)


def clear_pending(client: redis.Redis, telegram_user_id: str) -> None:
    client.delete(_KEY_PREFIX + telegram_user_id)
