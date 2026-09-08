import base64
import io
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
import redis
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from testcontainers.community.redis import RedisContainer

from telegram_integration.main import app, get_redis_client


@pytest.fixture(scope="module")
def redis_client() -> Iterator[redis.Redis]:
    with RedisContainer() as container:
        client: redis.Redis = container.get_client()
        app.dependency_overrides[get_redis_client] = lambda: client
        yield client
        app.dependency_overrides.clear()


@pytest.fixture
def client(redis_client: redis.Redis) -> TestClient:
    return TestClient(app)


def _render_text_image(text: str) -> str:
    image = Image.new("RGB", (700, 100), color="white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=40)
    draw.text((10, 10), text, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_returns_pending_and_asks_for_missing_field(client: TestClient) -> None:
    response = client.post(
        "/bets/capture",
        json={
            "telegramUserId": "endpoint-user-1",
            "languageCode": "pt-BR",
            "chatId": "chat-1",
            "text": "sem nada reconhecivel",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["message"] == "Qual foi a odd dessa aposta?"
    assert body["chatId"] == "chat-1"
    assert body["bet"] is None


def test_returns_complete_when_text_has_everything(client: TestClient) -> None:
    response = client.post(
        "/bets/capture",
        json={
            "telegramUserId": "endpoint-user-2",
            "languageCode": "pt-BR",
            "chatId": "chat-2",
            "text": "Bet365, odd 1.85, valor R$ 50,00",
        },
    )

    body = response.json()
    assert body["status"] == "complete"
    assert body["bet"]["odd"] == "1.85"
    assert body["bet"]["stake"] == "50.00"
    # Not extracted from text (see extraction.py) - always defaults to today.
    assert body["bet"]["bet_date"] == datetime.now(UTC).date().isoformat()


def test_extracts_from_a_photo_via_ocr(client: TestClient) -> None:
    photo_base64 = _render_text_image("ODD 1.85")

    response = client.post(
        "/bets/capture",
        json={
            "telegramUserId": "endpoint-user-3",
            "languageCode": "pt-BR",
            "chatId": "chat-3",
            "photoBase64": photo_base64,
        },
    )

    body = response.json()
    assert body["status"] == "pending"
    # Odd was found (from the OCR'd image), so the next question is about stake.
    assert body["message"] == "Quanto você apostou (valor em R$)?"


def test_malformed_photo_bytes_do_not_crash_the_service(client: TestClient) -> None:
    response = client.post(
        "/bets/capture",
        json={
            "telegramUserId": "endpoint-user-4",
            "languageCode": "pt-BR",
            "chatId": "chat-4",
            "photoBase64": base64.b64encode(b"not a real image").decode("ascii"),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_multi_turn_conversation_carries_state_across_separate_requests(client: TestClient) -> None:
    first = client.post(
        "/bets/capture",
        json={
            "telegramUserId": "endpoint-user-5",
            "languageCode": "pt-BR",
            "chatId": "chat-5",
            "text": "odd 1.85",
        },
    )
    assert first.json()["status"] == "pending"
    assert first.json()["message"] == "Quanto você apostou (valor em R$)?"

    second = client.post(
        "/bets/capture",
        json={
            "telegramUserId": "endpoint-user-5",
            "languageCode": "pt-BR",
            "chatId": "chat-5",
            "text": "50",
        },
    )
    assert second.json()["status"] == "complete"
    assert second.json()["bet"] == {
        "odd": "1.85",
        "stake": "50",
        "bet_date": datetime.now(UTC).date().isoformat(),
        "betting_house": None,
        "sport": None,
        "league": None,
        "market": None,
        "team1": None,
        "team2": None,
    }
