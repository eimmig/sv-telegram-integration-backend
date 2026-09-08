import json
from datetime import UTC, datetime

import httpx
import pytest

from telegram_integration.bets_client import SubmitOutcome, submit_bet

_BET: dict[str, str | None] = {
    "odd": "1.85",
    "stake": "50.00",
    "bet_date": datetime.now(UTC).date().isoformat(),
    "bettingHouseId": "bh-1",
    "sportId": "sp-1",
    "leagueId": "lg-1",
    "marketId": "mk-1",
}


def _mock_client(status_code: int) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/bets"
        assert request.headers["X-Service-Key"] == "test-key"
        assert request.headers["X-Telegram-User-Id"] == "999"
        assert request.headers["X-Correlation-Id"] == "corr-1"
        assert request.headers["Idempotency-Key"] == "idem-1"
        body = json.loads(request.content)
        assert body == {
            "bettingHouseId": "bh-1",
            "sportId": "sp-1",
            "leagueId": "lg-1",
            "marketId": "mk-1",
            "stake": "50.00",
            "odd": "1.85",
            "betDate": f"{_BET['bet_date']}T00:00:00Z",
        }
        return httpx.Response(status_code)

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (201, SubmitOutcome.CREATED),
        (200, SubmitOutcome.ALREADY_SUBMITTED),
        (401, SubmitOutcome.NO_TELEGRAM_LINK),
        (404, SubmitOutcome.CATALOG_ENTRY_NOT_FOUND),
        (422, SubmitOutcome.VALIDATION_FAILED),
        (500, SubmitOutcome.SERVICE_UNAVAILABLE),
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
