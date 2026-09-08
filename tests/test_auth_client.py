import json

import httpx
import pytest

from telegram_integration.auth_client import LinkOutcome, confirm_telegram_link


def _mock_client(status_code: int) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/telegram-accounts"
        assert request.headers["X-Correlation-Id"] == "corr-1"
        assert json.loads(request.content) == {"telegramUserId": "999", "code": "ABCD1234"}
        return httpx.Response(status_code)

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://auth-service.local")


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (201, LinkOutcome.SUCCESS),
        (404, LinkOutcome.CODE_NOT_FOUND),
        (422, LinkOutcome.CODE_EXPIRED),
        (409, LinkOutcome.ALREADY_LINKED),
        (500, LinkOutcome.SERVICE_UNAVAILABLE),
    ],
)
def test_maps_auth_service_status_to_outcome(
    monkeypatch: pytest.MonkeyPatch, status_code: int, expected: LinkOutcome
) -> None:
    client = _mock_client(status_code)
    monkeypatch.setattr("telegram_integration.auth_client.httpx.post", client.post)

    outcome = confirm_telegram_link("999", "ABCD1234", correlation_id="corr-1")

    assert outcome is expected


def test_returns_service_unavailable_when_auth_service_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_connect_error(*_args: object, **_kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("telegram_integration.auth_client.httpx.post", raise_connect_error)

    outcome = confirm_telegram_link("999", "ABCD1234", correlation_id="corr-1")

    assert outcome is LinkOutcome.SERVICE_UNAVAILABLE


def test_uses_auth_service_url_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://custom-auth:9001")
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(201)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("telegram_integration.auth_client.httpx.post", client.post)

    confirm_telegram_link("999", "ABCD1234", correlation_id="corr-1")

    assert captured_urls == ["http://custom-auth:9001/api/v1/telegram-accounts"]
