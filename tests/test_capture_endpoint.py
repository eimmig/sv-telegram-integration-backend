import base64
import io
from collections.abc import Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
import redis
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from testcontainers.community.redis import RedisContainer

from telegram_integration.bets_client import SubmitOutcome
from telegram_integration.catalog_client import CatalogEntry, CatalogFailure
from telegram_integration.conversation import get_pending
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
    for _ in range(3):
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
    assert body["message"] == (
        "Ocorreu um erro ao registrar a aposta. Os dados foram guardados: "
        "envie qualquer mensagem para tentar de novo ou /cancelar para recomeçar o cadastro."
    )


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
    assert captured_keys[0]
    assert ":" not in captured_keys[0]


def _post_text(
    client: TestClient, telegram_user_id: str, text: str, language_code: str = "pt-BR"
) -> dict[str, object]:
    response = client.post(
        "/bets/capture",
        json={
            "telegramUserId": telegram_user_id,
            "languageCode": language_code,
            "chatId": f"chat-{telegram_user_id}",
            "text": text,
        },
    )
    assert response.status_code == 200
    return response.json()  # type: ignore[no-any-return]


def test_reset_command_discards_a_stuck_conversation_and_next_message_starts_over(
    client: TestClient, redis_client: redis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    submitted: list[dict[str, str]] = []

    def _failing_submit(bet: dict[str, str], *_args: object) -> SubmitOutcome:
        submitted.append(bet)
        return SubmitOutcome.SERVICE_UNAVAILABLE

    monkeypatch.setattr("telegram_integration.main.submit_bet", _failing_submit)
    assert _reach_complete(client, "reset-user-1", "chat-reset-user-1")["status"] == "blocked"
    assert redis_client.exists("telegram:pending-bet:reset-user-1")

    body = _post_text(client, "reset-user-1", "/cancelar")

    assert body["status"] == "cancelled"
    assert body["message"] == (
        "Cadastro cancelado. Os dados da aposta anterior foram descartados. "
        "Envie a foto do bilhete ou os dados da nova aposta."
    )
    assert body["chatId"] == "chat-reset-user-1"
    assert body["bet"] is None
    assert not redis_client.exists("telegram:pending-bet:reset-user-1")

    attempts_before = len(submitted)
    next_message = _post_text(client, "reset-user-1", "sem nada reconhecivel")
    assert next_message["status"] == "pending"
    assert next_message["message"] == "Qual foi a odd dessa aposta?"
    assert len(submitted) == attempts_before


def test_reset_command_without_pending_conversation(client: TestClient, redis_client: redis.Redis) -> None:
    body = _post_text(client, "reset-user-2", "/cancelar")

    assert body["status"] == "cancelled"
    assert body["message"] == (
        "Não havia nenhum cadastro em andamento. Envie a foto do bilhete ou os dados da aposta para começar."
    )
    assert not redis_client.exists("telegram:pending-bet:reset-user-2")


@pytest.mark.parametrize(
    ("language_code", "expected"),
    [
        (
            "en",
            "Bet capture cancelled. The previous bet details were discarded. "
            "Send the bet slip photo or the details of the new bet.",
        ),
        (
            "es",
            "Registro cancelado. Los datos de la apuesta anterior fueron descartados. "
            "Envía la foto del boleto o los datos de la nueva apuesta.",
        ),
    ],
)
def test_reset_confirmation_follows_language_code(
    client: TestClient, language_code: str, expected: str
) -> None:
    user = f"reset-user-locale-{language_code}"
    assert _post_text(client, user, "odd 1.85", language_code)["status"] == "pending"

    body = _post_text(client, user, "/cancelar", language_code)

    assert body["message"] == expected


@pytest.mark.parametrize(
    "command", ["/cancel", "/CANCELAR", "  /cancelar  ", "/cancelar@ArkaBot", "/cancelar agora"]
)
def test_reset_command_variants_are_recognized(
    client: TestClient, redis_client: redis.Redis, command: str
) -> None:
    user = "reset-user-variant"
    redis_client.delete(f"telegram:pending-bet:{user}")
    assert _post_text(client, user, "odd 1.85")["status"] == "pending"

    body = _post_text(client, user, command)

    assert body["status"] == "cancelled"
    assert not redis_client.exists(f"telegram:pending-bet:{user}")


@pytest.mark.parametrize("text", ["", "   ", "cancelar", "/cancelamento", "odd 1.85 /cancelar"])
def test_text_that_is_not_the_reset_command_keeps_the_conversation(
    client: TestClient, redis_client: redis.Redis, text: str
) -> None:
    user = "reset-user-not-command"
    redis_client.delete(f"telegram:pending-bet:{user}")

    body = _post_text(client, user, text)

    assert body["status"] == "pending"
    assert redis_client.exists(f"telegram:pending-bet:{user}")


def test_photo_is_never_treated_as_reset_command(client: TestClient, redis_client: redis.Redis) -> None:
    user = "reset-user-photo"
    response = client.post(
        "/bets/capture",
        json={
            "telegramUserId": user,
            "languageCode": "pt-BR",
            "chatId": "chat-photo",
            "text": "/cancelar",
            "photoBase64": _render_text_image("ODD 1.85"),
        },
    )

    assert response.json()["status"] == "pending"
    assert redis_client.exists(f"telegram:pending-bet:{user}")


def test_generic_error_with_preserved_state_follows_language_code(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "telegram_integration.orchestration.fetch_catalog", lambda *_a: CatalogFailure.UNAVAILABLE
    )

    body = _post_text(client, "pending-error-en", "Bet365, odd 1.85, valor R$ 50,00", "en")

    assert body["status"] == "blocked"
    assert body["message"] == (
        "Something went wrong while capturing the bet. The details were kept: "
        "send any message to try again or /cancelar to start over."
    )


def test_new_photo_discards_the_previous_conversation_instead_of_resending_it(
    client: TestClient, redis_client: redis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    submitted: list[dict[str, str]] = []

    def _failing_submit(bet: dict[str, str], *_args: object) -> SubmitOutcome:
        submitted.append(bet)
        return SubmitOutcome.SERVICE_UNAVAILABLE

    monkeypatch.setattr("telegram_integration.main.submit_bet", _failing_submit)
    assert _reach_complete(client, "photo-reset-user", "chat-photo-reset")["status"] == "blocked"
    attempts_before = len(submitted)

    response = client.post(
        "/bets/capture",
        json={
            "telegramUserId": "photo-reset-user",
            "languageCode": "pt-BR",
            "chatId": "chat-photo-reset",
            "photoBase64": _render_text_image("ODD 2.10"),
        },
    )

    body = response.json()
    assert body["status"] == "pending"
    assert body["message"] == "Quanto você apostou (valor em R$)?"
    assert len(submitted) == attempts_before
    pending = get_pending(redis_client, "photo-reset-user")
    assert pending is not None
    assert pending.fields["odd"] == "2.10"
    assert pending.catalog_ids == {}


def test_permanent_rejection_clears_the_conversation(
    client: TestClient, redis_client: redis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    monkeypatch.setattr("telegram_integration.main.submit_bet", lambda *_a, **_kw: SubmitOutcome.REJECTED)

    body = _reach_complete(client, "rejected-user", "chat-rejected")

    assert body["status"] == "blocked"
    assert body["bet"] is None
    assert body["message"] == (
        "Não foi possível registrar essa aposta e os dados foram descartados. "
        "Envie a foto do bilhete ou os dados da aposta novamente."
    )
    assert get_pending(redis_client, "rejected-user") is None

    retry = _post_text(client, "rejected-user", "qualquer coisa")
    assert retry["status"] == "pending"
    assert retry["message"] == "Qual foi a odd dessa aposta?"


@pytest.mark.parametrize(
    ("language_code", "expected_message"),
    [
        (
            "pt-BR",
            "Sua conta do Telegram ainda não está vinculada. Envie /vincular <código> (gerado no site) "
            "antes de registrar apostas por aqui.",
        ),
        (
            "en-US",
            "Your Telegram account isn't linked yet. Send /vincular <code> (generated on the website) "
            "before capturing bets here.",
        ),
    ],
)
def test_user_without_link_is_told_to_link_when_the_catalog_lookup_gets_the_gateway_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, language_code: str, expected_message: str
) -> None:
    def gateway_without_link(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"type": "https://docs/errors/telegram-account-not-found", "status": 404},
            headers={"Content-Type": "application/problem+json"},
        )

    gateway = httpx.Client(transport=httpx.MockTransport(gateway_without_link))
    monkeypatch.setattr("telegram_integration.catalog_client.httpx.get", gateway.get)

    def _must_not_submit(*_args: object) -> SubmitOutcome:
        raise AssertionError("bet must not be submitted without a link")

    monkeypatch.setattr("telegram_integration.main.submit_bet", _must_not_submit)

    body = _post_text(client, f"no-link-{language_code}", "Bet365, odd 1.85, valor R$ 50,00", language_code)

    assert body["status"] == "blocked"
    assert body["message"] == expected_message
    assert body["bet"] is None


_NO_LINK_TYPE = "https://docs/errors/telegram-account-not-found"


@pytest.mark.parametrize(
    ("gateway_response", "expected_prefix"),
    [
        (
            httpx.Response(404, json={"type": _NO_LINK_TYPE, "status": 404}),
            "Sua conta do Telegram ainda não está vinculada",
        ),
        (
            httpx.Response(401, json={"type": "https://docs/errors/invalid-service-key", "status": 401}),
            "Ocorreu um erro ao registrar a aposta. Os dados foram guardados",
        ),
    ],
)
def test_submission_without_link_or_with_bad_service_key_keeps_the_conversation(
    client: TestClient,
    redis_client: redis.Redis,
    monkeypatch: pytest.MonkeyPatch,
    gateway_response: httpx.Response,
    expected_prefix: str,
) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)
    gateway = httpx.Client(transport=httpx.MockTransport(lambda _request: gateway_response))
    monkeypatch.setattr("telegram_integration.bets_client.httpx.post", gateway.post)
    user = f"submit-{gateway_response.status_code}"

    body = _reach_complete(client, user, f"chat-{user}")

    assert body["status"] == "blocked"
    assert str(body["message"]).startswith(expected_prefix)
    assert get_pending(redis_client, user) is not None
