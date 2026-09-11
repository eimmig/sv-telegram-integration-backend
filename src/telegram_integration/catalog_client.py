"""HTTP client for the tenant catalogs (sports/leagues/markets/betting-houses) that
`bets-service` exposes and `POST /api/v1/bets` requires as foreign keys. Unlike
`auth_client.py`, this call goes THROUGH the api-gateway (X-Service-Key +
X-Telegram-User-Id, same pair used for `POST /api/v1/bets`) - no structural
circularity here, the Gateway resolves the tenant the same way it would for the
final bet submission. Routing for these 3 paths was a real gap fixed in
api-gateway feat-007 (see docs/DECISIONS-LOG.md 2026-09-08) before this client
could work at all.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5.0
_PAGE_SIZE = 100


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    name: str


def _api_gateway_url() -> str:
    return os.environ.get("API_GATEWAY_URL", "http://localhost:8080")


def _service_key() -> str:
    return os.environ.get("SERVICE_KEY", "")


def fetch_catalog(resource: str, telegram_user_id: str, correlation_id: str) -> list[CatalogEntry] | None:
    """Fetches every entry of one catalog resource ("sports", "leagues", "markets"
    or "betting-houses") for the tenant linked to `telegram_user_id`, paging until
    exhausted - the default page size (20) would silently hide entries from a
    tenant with a larger catalog. Returns None (not an empty list) when the
    catalog can't be reached at all, so callers can tell "no entries yet" apart
    from "couldn't ask".
    """
    entries: list[CatalogEntry] = []
    page = 0
    while True:
        try:
            response = httpx.get(
                f"{_api_gateway_url()}/api/v1/{resource}",
                params={"page": page, "size": _PAGE_SIZE},
                headers={
                    "X-Service-Key": _service_key(),
                    "X-Telegram-User-Id": telegram_user_id,
                    "X-Correlation-Id": correlation_id,
                },
                timeout=_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError:
            logger.warning(
                "api-gateway unreachable fetching %s catalog [correlationId=%s]", resource, correlation_id
            )
            return None

        if response.status_code != 200:
            logger.warning(
                "unexpected status %s fetching %s catalog [correlationId=%s]",
                response.status_code,
                resource,
                correlation_id,
            )
            return None

        body = response.json()
        content = body["content"]
        entries.extend(CatalogEntry(id=item["id"], name=item["name"]) for item in content)

        page += 1
        if page >= body["totalPages"] or len(content) < _PAGE_SIZE:
            return entries
