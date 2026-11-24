from __future__ import annotations

import logging
import os
from datetime import UTC, date, datetime, time
from enum import Enum, auto
from zoneinfo import ZoneInfo

import httpx

from telegram_integration.gateway_errors import is_telegram_account_not_found

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5.0
_LOCAL_TIMEZONE = ZoneInfo("America/Sao_Paulo")
# Data sem hora vinda de outro dia (nao de hoje) vai ao meio-dia de Brasilia: longe da meia-noite,
# o dia nao muda em nenhum fuso entre UTC-12 e UTC+11.
_DATE_ONLY_LOCAL_TIME = time(12, 0)


class SubmitOutcome(Enum):
    CREATED = auto()
    ALREADY_SUBMITTED = auto()
    NO_TELEGRAM_LINK = auto()
    CATALOG_ENTRY_NOT_FOUND = auto()
    VALIDATION_FAILED = auto()
    REJECTED = auto()
    SERVICE_UNAVAILABLE = auto()


_STATUS_TO_OUTCOME = {
    201: SubmitOutcome.CREATED,
    200: SubmitOutcome.ALREADY_SUBMITTED,
    404: SubmitOutcome.CATALOG_ENTRY_NOT_FOUND,
    422: SubmitOutcome.VALIDATION_FAILED,
}
_TRANSIENT_CLIENT_ERRORS = (408, 429)


def _api_gateway_url() -> str:
    return os.environ.get("API_GATEWAY_URL", "http://localhost:8080")


def _service_key() -> str:
    return os.environ.get("SERVICE_KEY", "")


def bet_instant(bet_date: str, now: datetime | None = None) -> str:
    """Converte a data da aposta (AAAA-MM-DD, dia em Brasilia) no instante enviado como betDate.

    Antes era sempre meia-noite UTC, ou seja, 21h do dia anterior em Brasilia: a aposta aparecia
    um dia antes no historico. A aposta de hoje leva o instante atual; a de outro dia, meio-dia local.
    """
    current = now if now is not None else datetime.now(UTC)
    day = date.fromisoformat(bet_date)
    if day == current.astimezone(_LOCAL_TIMEZONE).date():
        instant = current
    else:
        instant = datetime.combine(day, _DATE_ONLY_LOCAL_TIME, tzinfo=_LOCAL_TIMEZONE)
    return instant.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def submit_bet(
    bet: dict[str, str | None], telegram_user_id: str, idempotency_key: str, correlation_id: str
) -> SubmitOutcome:
    body = {
        "bettingHouseId": bet["bettingHouseId"],
        "sportId": bet["sportId"],
        "leagueId": bet["leagueId"],
        "marketId": bet["marketId"],
        "stake": bet["stake"],
        "odd": bet["odd"],
        "betDate": bet_instant(str(bet["bet_date"])),
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

    if is_telegram_account_not_found(response):
        logger.info("no telegram link submitting bet [correlationId=%s]", correlation_id)
        return SubmitOutcome.NO_TELEGRAM_LINK
    if response.status_code == 401:
        logger.error(
            "api-gateway rejected the service credentials submitting bet [correlationId=%s]", correlation_id
        )
        return SubmitOutcome.SERVICE_UNAVAILABLE

    outcome = _STATUS_TO_OUTCOME.get(response.status_code)
    if outcome is not None:
        return outcome
    logger.warning(
        "unexpected status %s submitting bet [correlationId=%s]", response.status_code, correlation_id
    )
    if 400 <= response.status_code < 500 and response.status_code not in _TRANSIENT_CLIENT_ERRORS:
        return SubmitOutcome.REJECTED
    return SubmitOutcome.SERVICE_UNAVAILABLE
