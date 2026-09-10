from collections.abc import Iterator

import pytest
import redis
from fastapi.testclient import TestClient
from testcontainers.community.redis import RedisContainer

from telegram_integration.main import app, get_redis_client

_CAPTURE_PAYLOAD = {
    "telegramUserId": "auth-test-user",
    "languageCode": "pt-BR",
    "chatId": "auth-test-chat",
    "text": "sem nada reconhecivel",
}
_LINK_PAYLOAD = {
    "telegramUserId": "auth-test-user",
    "code": "ABCD1234",
    "chatId": "auth-test-chat",
}


@pytest.fixture(scope="module")
def redis_client() -> Iterator[redis.Redis]:
    with RedisContainer() as container:
        client: redis.Redis = container.get_client()
        app.dependency_overrides[get_redis_client] = lambda: client
        yield client
        app.dependency_overrides.clear()


def test_capture_rejects_missing_service_key(redis_client: redis.Redis) -> None:
    client = TestClient(app)

    response = client.post("/bets/capture", json=_CAPTURE_PAYLOAD)

    assert response.status_code == 401


def test_capture_rejects_wrong_service_key(redis_client: redis.Redis) -> None:
    client = TestClient(app, headers={"X-Service-Key": "not-the-real-key"})

    response = client.post("/bets/capture", json=_CAPTURE_PAYLOAD)

    assert response.status_code == 401


def test_capture_accepts_correct_service_key(redis_client: redis.Redis) -> None:
    client = TestClient(app, headers={"X-Service-Key": "test-service-key"})

    response = client.post("/bets/capture", json=_CAPTURE_PAYLOAD)

    assert response.status_code == 200


def test_link_rejects_missing_service_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from telegram_integration.auth_client import LinkOutcome

    monkeypatch.setattr(
        "telegram_integration.main.confirm_telegram_link", lambda *_a, **_kw: LinkOutcome.SUCCESS
    )
    client = TestClient(app)

    response = client.post("/telegram/link", json=_LINK_PAYLOAD)

    assert response.status_code == 401


def test_link_accepts_correct_service_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from telegram_integration.auth_client import LinkOutcome

    monkeypatch.setattr(
        "telegram_integration.main.confirm_telegram_link", lambda *_a, **_kw: LinkOutcome.SUCCESS
    )
    client = TestClient(app, headers={"X-Service-Key": "test-service-key"})

    response = client.post("/telegram/link", json=_LINK_PAYLOAD)

    assert response.status_code == 200


def test_health_needs_no_service_key() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200


def test_oversized_body_is_rejected_before_reaching_the_route(redis_client: redis.Redis) -> None:
    client = TestClient(app, headers={"X-Service-Key": "test-service-key"})
    oversized_text = "x" * (11 * 1024 * 1024)  # over the 10 MiB limit

    response = client.post("/bets/capture", json={**_CAPTURE_PAYLOAD, "text": oversized_text})

    assert response.status_code == 413
