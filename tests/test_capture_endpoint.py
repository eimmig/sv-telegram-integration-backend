import base64
import io
from collections.abc import Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import redis
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from testcontainers.community.redis import RedisContainer

from telegram_integration.bets_client import SubmitOutcome
from telegram_integration.catalog_client import CatalogEntry
from telegram_integration.main import app, get_redis_client

_STUB_CATALOG = {
    "betting-houses": [CatalogEntry(id="bh-1", name="Bet365")],
    "sports": [CatalogEntry(id="sp-1", name="Futebol")],
    "leagues": [CatalogEntry(id="lg-1", name="Brasileirão")],
    "markets": [CatalogEntry(id="mk-1", name="Vencedor")],
}


def _stub_fetch_catalog(resource: str, _telegram_user_id: str, _correlation_id: str) -> list[CatalogEntry]:
    return _STUB_CATALOG[resource]


def _stub_submit_bet(
    _bet: dict[str, str], _telegram_user_id: str, _idempotency_key: str, _correlation_id: str
) -> SubmitOutcome:
    return SubmitOutcome.CREATED


@pytest.fixture(scope="module")
def redis_client() -> Iterator[redis.Redis]:
    with RedisContainer() as container:
        client: redis.Redis = container.get_client()
        app.dependency_overrides[get_redis_client] = lambda: client
        yield client
        app.dependency_overrides.clear()


@pytest.fixture
def client(redis_client: redis.Redis) -> TestClient:
    return TestClient(app, headers={"X-Service-Key": "test-service-key"})


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


def test_returns_complete_after_resolving_every_catalog(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    monkeypatch.setattr("telegram_integration.main.submit_bet", _stub_submit_bet)

    first = client.post(
        "/bets/capture",
        json={
            "telegramUserId": "endpoint-user-2",
            "languageCode": "pt-BR",
            "chatId": "chat-2",
            "text": "Bet365, odd 1.85, valor R$ 50,00",
        },
    )
    # Betting house name matched the (stubbed) catalog exactly, so it's auto-resolved -
    # sport/league/market are always asked, never auto-chosen.
    assert first.json()["status"] == "pending"
    assert first.json()["message"].startswith("Qual o esporte")

    for expected_prefix in ("Qual a liga", "Qual o mercado"):
        step = client.post(
            "/bets/capture",
            json={
                "telegramUserId": "endpoint-user-2",
                "languageCode": "pt-BR",
                "chatId": "chat-2",
                "text": "1",
            },
        )
        assert step.json()["status"] == "pending"
        assert step.json()["message"].startswith(expected_prefix)

    last = client.post(
        "/bets/capture",
        json={
            "telegramUserId": "endpoint-user-2",
            "languageCode": "pt-BR",
            "chatId": "chat-2",
            "text": "1",
        },
    )
    body = last.json()
    assert body["status"] == "complete"
    assert body["message"] == "Aposta registrada com sucesso!"
    assert body["bet"]["odd"] == "1.85"
    assert body["bet"]["stake"] == "50.00"
    assert body["bet"]["bettingHouseId"] == "bh-1"
    assert body["bet"]["sportId"] == "sp-1"
    assert body["bet"]["leagueId"] == "lg-1"
    assert body["bet"]["marketId"] == "mk-1"
    # Not extracted from text (see extraction.py) - always defaults to today.
    assert body["bet"]["bet_date"] == datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()


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


def test_multi_turn_conversation_carries_state_across_separate_requests(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    monkeypatch.setattr("telegram_integration.main.submit_bet", _stub_submit_bet)

    def post(text: str) -> dict[str, object]:
        response = client.post(
            "/bets/capture",
            json={
                "telegramUserId": "endpoint-user-5",
                "languageCode": "pt-BR",
                "chatId": "chat-5",
                "text": text,
            },
        )
        return response.json()  # type: ignore[no-any-return]

    first = post("odd 1.85")
    assert first["status"] == "pending"
    assert first["message"] == "Quanto você apostou (valor em R$)?"

    second = post("50")
    assert second["status"] == "pending"
    assert str(second["message"]).startswith("Não consegui identificar a casa de apostas")

    for expected_prefix in ("Qual o esporte", "Qual a liga", "Qual o mercado"):
        step = post("1")
        assert step["status"] == "pending"
        assert str(step["message"]).startswith(expected_prefix)

    final = post("1")
    assert final["status"] == "complete"
    assert final["message"] == "Aposta registrada com sucesso!"
    assert final["bet"] == {
        "odd": "1.85",
        "stake": "50",
        "bet_date": datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat(),
        "betting_house": None,
        "sport": None,
        "league": None,
        "market": None,
        "team1": None,
        "team2": None,
        "bettingHouseId": "bh-1",
        "sportId": "sp-1",
        "leagueId": "lg-1",
        "marketId": "mk-1",
    }


def _reach_complete(client: TestClient, telegram_user_id: str, chat_id: str) -> dict[str, object]:
    """Drives a fresh conversation through every question (betting house
    auto-matches "Bet365") up to the final submission call, returning that
    last response.
    """
    client.post(
        "/bets/capture",
        json={
            "telegramUserId": telegram_user_id,
            "languageCode": "pt-BR",
            "chatId": chat_id,
            "text": "Bet365, odd 1.85, valor R$ 50,00",
        },
    )
    response = None
    for _ in range(3):  # sport, league, market
        response = client.post(
            "/bets/capture",
            json={
                "telegramUserId": telegram_user_id,
                "languageCode": "pt-BR",
                "chatId": chat_id,
                "text": "1",
            },
        )
    assert response is not None
    return response.json()  # type: ignore[no-any-return]


def test_blocked_when_submission_finds_no_telegram_link(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    monkeypatch.setattr(
        "telegram_integration.main.submit_bet", lambda *_a, **_kw: SubmitOutcome.NO_TELEGRAM_LINK
    )

    body = _reach_complete(client, "endpoint-user-6", "chat-6")

    assert body["status"] == "blocked"
    assert str(body["message"]).startswith("Sua conta do Telegram ainda não está vinculada")
    assert body["bet"] is None


def test_blocked_when_submission_fails_validation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    monkeypatch.setattr(
        "telegram_integration.main.submit_bet", lambda *_a, **_kw: SubmitOutcome.VALIDATION_FAILED
    )

    body = _reach_complete(client, "endpoint-user-7", "chat-7")

    assert body["status"] == "blocked"
    assert body["message"] == (
        "Os valores informados não são válidos para essa aposta (confira a odd e o valor "
        "apostado). Envie os dados da aposta novamente."
    )

    # Unlike NO_TELEGRAM_LINK/SERVICE_UNAVAILABLE, the bet's own data is what's
    # wrong here - preserving it would make every retry fail identically forever,
    # so state is cleared and the next message starts a fresh conversation.
    retry = client.post(
        "/bets/capture",
        json={
            "telegramUserId": "endpoint-user-7",
            "languageCode": "pt-BR",
            "chatId": "chat-7",
            "text": "qualquer coisa",
        },
    )
    assert retry.json()["status"] == "pending"
    assert retry.json()["message"] == "Qual foi a odd dessa aposta?"


def test_blocked_when_gateway_unreachable_during_submission(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    monkeypatch.setattr(
        "telegram_integration.main.submit_bet", lambda *_a, **_kw: SubmitOutcome.SERVICE_UNAVAILABLE
    )

    body = _reach_complete(client, "endpoint-user-8", "chat-8")

    assert body["status"] == "blocked"
    assert body["message"] == "Ocorreu um erro. Tente novamente mais tarde."


def test_blocked_when_a_resolved_catalog_entry_no_longer_exists(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    monkeypatch.setattr(
        "telegram_integration.main.submit_bet", lambda *_a, **_kw: SubmitOutcome.CATALOG_ENTRY_NOT_FOUND
    )

    body = _reach_complete(client, "endpoint-user-12", "chat-12")

    assert body["status"] == "blocked"
    assert body["message"] == (
        "Uma das opções escolhidas não existe mais. Envie os dados da aposta novamente."
    )

    # A stale catalog id (rare race - deleted mid-conversation) can't be fixed by
    # blindly retrying the same submission - state is cleared so the user
    # re-resolves against the current catalog instead of looping forever.
    retry = client.post(
        "/bets/capture",
        json={
            "telegramUserId": "endpoint-user-12",
            "languageCode": "pt-BR",
            "chatId": "chat-12",
            "text": "qualquer coisa",
        },
    )
    assert retry.json()["status"] == "pending"
    assert retry.json()["message"] == "Qual foi a odd dessa aposta?"


def test_failed_submission_preserves_state_for_a_retry(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    monkeypatch.setattr(
        "telegram_integration.main.submit_bet", lambda *_a, **_kw: SubmitOutcome.SERVICE_UNAVAILABLE
    )

    first_attempt = _reach_complete(client, "endpoint-user-9", "chat-9")
    assert first_attempt["status"] == "blocked"

    monkeypatch.setattr("telegram_integration.main.submit_bet", _stub_submit_bet)
    retry = client.post(
        "/bets/capture",
        json={
            "telegramUserId": "endpoint-user-9",
            "languageCode": "pt-BR",
            "chatId": "chat-9",
            "text": "tentar de novo",
        },
    )
    body = retry.json()

    assert body["status"] == "complete"
    assert body["message"] == "Aposta registrada com sucesso!"
    assert body["bet"]["bettingHouseId"] == "bh-1"


def test_idempotency_key_derived_from_telegram_update_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    captured_keys: list[str] = []

    def recording_submit_bet(
        _bet: dict[str, str], _telegram_user_id: str, idempotency_key: str, _correlation_id: str
    ) -> SubmitOutcome:
        captured_keys.append(idempotency_key)
        return SubmitOutcome.CREATED

    monkeypatch.setattr("telegram_integration.main.submit_bet", recording_submit_bet)

    client.post(
        "/bets/capture",
        json={
            "telegramUserId": "endpoint-user-10",
            "languageCode": "pt-BR",
            "chatId": "chat-10",
            "text": "Bet365, odd 1.85, valor R$ 50,00",
            "telegramUpdateId": "555000111",
        },
    )
    for _ in range(3):
        client.post(
            "/bets/capture",
            json={
                "telegramUserId": "endpoint-user-10",
                "languageCode": "pt-BR",
                "chatId": "chat-10",
                "text": "1",
                "telegramUpdateId": "555000111",
            },
        )

    assert captured_keys == ["endpoint-user-10:555000111"]


def test_idempotency_key_falls_back_when_telegram_update_id_is_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    captured_keys: list[str] = []

    def recording_submit_bet(
        _bet: dict[str, str], _telegram_user_id: str, idempotency_key: str, _correlation_id: str
    ) -> SubmitOutcome:
        captured_keys.append(idempotency_key)
        return SubmitOutcome.CREATED

    monkeypatch.setattr("telegram_integration.main.submit_bet", recording_submit_bet)

    body = _reach_complete(client, "endpoint-user-11", "chat-11")

    assert body["status"] == "complete"
    assert len(captured_keys) == 1
    assert captured_keys[0]  # non-empty fallback (uuid4), just not the "user:update_id" shape
    assert ":" not in captured_keys[0]
