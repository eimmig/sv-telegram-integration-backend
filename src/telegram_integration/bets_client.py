"""HTTP client for the final `POST /api/v1/bets` submission, through api-gateway
(same X-Service-Key/X-Telegram-User-Id pair already used by catalog_client.py -
the Gateway resolves the tenant and injects X-User-Id/X-Tenant-Id before
bets-service ever sees the request). Doesn't duplicate bets-service's business
rules (RN02/RN03/RN06/RN07) - only maps its response into an outcome the bot
can turn into a localized message.
"""

from __future__ import annotations

import logging
import os
from enum import Enum, auto

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5.0


class SubmitOutcome(Enum):
    CREATED = auto()
    ALREADY_SUBMITTED = auto()  # idempotent replay (200, not 201) - still a success
    NO_TELEGRAM_LINK = auto()
    CATALOG_ENTRY_NOT_FOUND = auto()
    VALIDATION_FAILED = auto()
    SERVICE_UNAVAILABLE = auto()


_STATUS_TO_OUTCOME = {
    201: SubmitOutcome.CREATED,
    200: SubmitOutcome.ALREADY_SUBMITTED,
    401: SubmitOutcome.NO_TELEGRAM_LINK,
    404: SubmitOutcome.CATALOG_ENTRY_NOT_FOUND,
    422: SubmitOutcome.VALIDATION_FAILED,
}


def _api_gateway_url() -> str:
    return os.environ.get("API_GATEWAY_URL", "http://localhost:8080")


def _service_key() -> str:
    return os.environ.get("SERVICE_KEY", "")


def submit_bet(
    bet: dict[str, str | None], telegram_user_id: str, idempotency_key: str, correlation_id: str
) -> SubmitOutcome:
    """`bet` must already carry the resolved catalog ids (bettingHouseId/sportId/
    leagueId/marketId, see orchestration.py) plus odd/stake/bet_date - it's the
    dict `handle_message` returns on `status == "complete"`.
    """
    body = {
        "bettingHouseId": bet["bettingHouseId"],
        "sportId": bet["sportId"],
        "leagueId": bet["leagueId"],
        "marketId": bet["marketId"],
        "stake": bet["stake"],
        "odd": bet["odd"],
        # CreateBetRequest.betDate is an Instant, not a bare date - the date-only
        # ISO string orchestration.py stores would fail Jackson deserialization.
        "betDate": f"{bet['bet_date']}T00:00:00Z",
    }
    try:
        response = httpx.post(
            f"{_api_gateway_url()}/api/v1/bets",
            json=body,
            headers={
                "X-Service-Key": _service_key(),
                "X-Telegram-User-Id": telegram_user_id,
                "X-Correlation-Id": correlation_id,
                "Idempotency-Key": idempotency_key,
            },
            timeout=_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError:
        logger.warning("api-gateway unreachable submitting bet [correlationId=%s]", correlation_id)
        return SubmitOutcome.SERVICE_UNAVAILABLE

    outcome = _STATUS_TO_OUTCOME.get(response.status_code)
    if outcome is None:
        logger.warning(
            "unexpected status %s submitting bet [correlationId=%s]", response.status_code, correlation_id
        )
        return SubmitOutcome.SERVICE_UNAVAILABLE
    return outcome
