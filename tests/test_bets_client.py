import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from telegram_integration.bets_client import SubmitOutcome, bet_instant, submit_bet

_BET: dict[str, str | None] = {
    "odd": "1.85",
    "stake": "50.00",
    "bet_date": datetime.now(UTC).date().isoformat(),
    "bettingHouseId": "bh-1",
    "sportId": "sp-1",
    "leagueId": "lg-1",
    "marketId": "mk-1",
}


# a aposta de hoje vai com o instante atual; em UTC, pode ja ser o dia seguinte
_BET_DATE_LOCAL_PREFIXES = (
    str(_BET["bet_date"]),
    (datetime.fromisoformat(str(_BET["bet_date"])) + timedelta(days=1)).date().isoformat(),
)


def _mock_client(status_code: int, problem_type: str | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/bets"
        assert request.headers["X-Service-Key"] == "test-key"
        assert request.headers["X-Telegram-User-Id"] == "999"
        assert request.headers["X-Correlation-Id"] == "corr-1"
        assert request.headers["Idempotency-Key"] == "idem-1"
        body = json.loads(request.content)
        assert body.pop("betDate").startswith(_BET_DATE_LOCAL_PREFIXES)
        assert body == {
            "bettingHouseId": "bh-1",
            "sportId": "sp-1",
            "leagueId": "lg-1",
            "marketId": "mk-1",
            "stake": "50.00",
            "odd": "1.85",
        }
        if problem_type is None:
            return httpx.Response(status_code)
        return httpx.Response(status_code, json={"type": problem_type, "status": status_code})

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (201, SubmitOutcome.CREATED),
        (200, SubmitOutcome.ALREADY_SUBMITTED),
        (401, SubmitOutcome.SERVICE_UNAVAILABLE),
        (404, SubmitOutcome.CATALOG_ENTRY_NOT_FOUND),
        (422, SubmitOutcome.VALIDATION_FAILED),
        (400, SubmitOutcome.REJECTED),
        (403, SubmitOutcome.REJECTED),
        (409, SubmitOutcome.REJECTED),
        (408, SubmitOutcome.SERVICE_UNAVAILABLE),
        (429, SubmitOutcome.SERVICE_UNAVAILABLE),
        (500, SubmitOutcome.SERVICE_UNAVAILABLE),
        (503, SubmitOutcome.SERVICE_UNAVAILABLE),
    ],
)
def test_maps_bets_service_status_to_outcome(
    monkeypatch: pytest.MonkeyPatch, status_code: int, expected: SubmitOutcome
) -> None:
    monkeypatch.setenv("SERVICE_KEY", "test-key")
    client = _mock_client(status_code)
    monkeypatch.setattr("telegram_integration.bets_client.httpx.post", client.post)

    outcome = submit_bet(_BET, "999", "idem-1", "corr-1")

    assert outcome is expected


def test_returns_service_unavailable_when_gateway_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_connect_error(*_args: object, **_kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("telegram_integration.bets_client.httpx.post", raise_connect_error)

    outcome = submit_bet(_BET, "999", "idem-1", "corr-1")

    assert outcome is SubmitOutcome.SERVICE_UNAVAILABLE


def test_uses_api_gateway_url_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_GATEWAY_URL", "http://custom-gateway:9000")
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(201)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("telegram_integration.bets_client.httpx.post", client.post)

    submit_bet(_BET, "999", "idem-1", "corr-1")

    assert captured_urls == ["http://custom-gateway:9000/api/v1/bets"]


@pytest.mark.parametrize(
    ("problem_type", "expected"),
    [
        ("https://docs/errors/telegram-account-not-found", SubmitOutcome.NO_TELEGRAM_LINK),
        ("https://docs/errors/betting-house-not-found", SubmitOutcome.CATALOG_ENTRY_NOT_FOUND),
    ],
)
def test_distinguishes_missing_link_from_missing_catalog_entry_on_404(
    monkeypatch: pytest.MonkeyPatch, problem_type: str, expected: SubmitOutcome
) -> None:
    monkeypatch.setenv("SERVICE_KEY", "test-key")
    client = _mock_client(404, problem_type)
    monkeypatch.setattr("telegram_integration.bets_client.httpx.post", client.post)

    outcome = submit_bet(_BET, "999", idempotency_key="idem-1", correlation_id="corr-1")

    assert outcome is expected


def test_bet_instant_today_in_brasilia_uses_current_instant_even_after_utc_midnight() -> None:
    # 24/11 21:30 em Brasilia = 25/11 00:30 UTC; antes ia como 24/11 00:00 UTC (23/11 21h local)
    now = datetime(2026, 11, 25, 0, 30, 15, tzinfo=UTC)
    assert bet_instant("2026-11-24", now) == "2026-11-25T00:30:15Z"


def test_bet_instant_today_in_the_morning_uses_current_instant() -> None:
    now = datetime(2026, 11, 24, 11, 5, 0, tzinfo=UTC)
    assert bet_instant("2026-11-24", now) == "2026-11-24T11:05:00Z"


def test_bet_instant_other_day_goes_to_noon_in_brasilia() -> None:
    now = datetime(2026, 11, 24, 15, 0, 0, tzinfo=UTC)
    assert bet_instant("2026-11-20", now) == "2026-11-20T15:00:00Z"


def test_bet_instant_without_now_uses_the_clock() -> None:
    today_local = datetime.now(UTC).astimezone(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    sent = datetime.strptime(bet_instant(today_local), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert abs((datetime.now(UTC) - sent).total_seconds()) < 5
