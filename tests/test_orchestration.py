from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
import redis
from testcontainers.community.redis import RedisContainer

from telegram_integration.catalog_client import CatalogEntry
from telegram_integration.conversation import get_pending
from telegram_integration.orchestration import handle_message

_STUB_CATALOG = {
    "betting-houses": [CatalogEntry(id="bh-1", name="Bet365")],
    "sports": [CatalogEntry(id="sp-1", name="Futebol")],
    "leagues": [CatalogEntry(id="lg-1", name="Brasileirão")],
    "markets": [CatalogEntry(id="mk-1", name="Vencedor")],
}


def _stub_fetch_catalog(resource: str, _telegram_user_id: str, _correlation_id: str) -> list[CatalogEntry]:
    return _STUB_CATALOG[resource]


@pytest.fixture(scope="module")
def redis_client() -> Iterator[redis.Redis]:
    with RedisContainer() as container:
        client: redis.Redis = container.get_client()
        yield client


@pytest.fixture(autouse=True)
def stub_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", _stub_fetch_catalog)


def test_asks_for_the_first_missing_required_field(redis_client: redis.Redis) -> None:
    result = handle_message(redis_client, "user-a", "pt-BR", "mensagem sem nada reconhecivel", "corr-1")

    assert result.status == "pending"
    assert result.message == "Qual foi a odd dessa aposta?"
    assert result.bet is None


def test_asks_for_stake_when_only_odd_was_found(redis_client: redis.Redis) -> None:
    result = handle_message(redis_client, "user-b", "pt-BR", "odd 1.85", "corr-1")

    assert result.status == "pending"
    assert result.message == "Quanto você apostou (valor em R$)?"


def test_after_required_fields_known_bot_asks_for_betting_house_choice(redis_client: redis.Redis) -> None:
    handle_message(redis_client, "user-c", "pt-BR", "odd 1.85", "corr-1")

    result = handle_message(redis_client, "user-c", "pt-BR", "50", "corr-1")

    assert result.status == "pending"
    assert result.message == (
        "Não consegui identificar a casa de apostas. Qual das opções abaixo é a certa? "
        "Responda com o número:\n1. Bet365"
    )
    assert result.bet is None


def test_betting_house_fuzzy_match_skips_the_question(redis_client: redis.Redis) -> None:
    result = handle_message(redis_client, "user-h", "pt-BR", "Bet365, odd 1.85, valor R$ 50,00", "corr-1")

    assert result.status == "pending"
    assert result.message == "Qual o esporte dessa aposta? Responda com o número da opção:\n1. Futebol"


def test_full_multi_turn_flow_resolves_every_catalog_and_completes(redis_client: redis.Redis) -> None:
    handle_message(redis_client, "user-d", "pt-BR", "odd 1.85", "corr-1")
    handle_message(redis_client, "user-d", "pt-BR", "50", "corr-1")  # -> asks betting house
    handle_message(redis_client, "user-d", "pt-BR", "1", "corr-1")  # -> asks sport
    handle_message(redis_client, "user-d", "pt-BR", "1", "corr-1")  # -> asks league
    result = handle_message(redis_client, "user-d", "pt-BR", "1", "corr-1")  # -> asks market

    assert result.status == "pending"
    assert result.message == "Qual o mercado dessa aposta? Responda com o número da opção:\n1. Vencedor"

    final = handle_message(redis_client, "user-d", "pt-BR", "1", "corr-1")

    assert final.status == "complete"
    assert final.message == "Captura concluída até aqui. O restante do cadastro continua em breve."
    assert final.bet is not None
    assert final.bet["odd"] == "1.85"
    assert final.bet["stake"] == "50"
    assert final.bet["bettingHouseId"] == "bh-1"
    assert final.bet["sportId"] == "sp-1"
    assert final.bet["leagueId"] == "lg-1"
    assert final.bet["marketId"] == "mk-1"
    # Not cleared here - main.py only clears it after actually submitting the
    # bet to bets-service (see bets_client.py); a retry (any message) reaches
    # "complete" again immediately since nothing is left to resolve.
    pending = get_pending(redis_client, "user-d")
    assert pending is not None
    assert pending.awaiting_catalog is None
    assert pending.awaiting_field is None

    retry = handle_message(redis_client, "user-d", "pt-BR", "qualquer coisa", "corr-1")
    assert retry.status == "complete"
    assert retry.bet == final.bet


def test_invalid_catalog_choice_reprompts_the_same_question(redis_client: redis.Redis) -> None:
    handle_message(redis_client, "user-i", "pt-BR", "Bet365, odd 1.85, valor R$ 50,00", "corr-1")

    result = handle_message(redis_client, "user-i", "pt-BR", "99", "corr-1")

    assert result.status == "pending"
    assert result.message == (
        "Não entendi sua escolha.\nQual o esporte dessa aposta? Responda com o número da opção:\n1. Futebol"
    )

    non_numeric = handle_message(redis_client, "user-i", "pt-BR", "futebol", "corr-1")
    assert non_numeric.status == "pending"
    assert non_numeric.message.startswith("Não entendi sua escolha.")

    recovered = handle_message(redis_client, "user-i", "pt-BR", "1", "corr-1")
    assert recovered.status == "pending"
    assert recovered.message.startswith("Qual a liga")


def test_empty_catalog_blocks_capture_and_clears_state(
    redis_client: redis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    def empty_sports(resource: str, telegram_user_id: str, correlation_id: str) -> list[CatalogEntry]:
        return [] if resource == "sports" else _stub_fetch_catalog(resource, telegram_user_id, correlation_id)

    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", empty_sports)

    result = handle_message(redis_client, "user-j", "pt-BR", "Bet365, odd 1.85, valor R$ 50,00", "corr-1")

    assert result.status == "blocked"
    assert result.message == (
        "Você ainda não cadastrou nenhum esporte. Cadastre pelo menos um no site antes de "
        "registrar apostas por aqui."
    )
    assert get_pending(redis_client, "user-j") is None


def test_unreachable_catalog_blocks_but_preserves_progress(
    redis_client: redis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unreachable_sports(
        resource: str, telegram_user_id: str, correlation_id: str
    ) -> list[CatalogEntry] | None:
        if resource == "sports":
            return None
        return _stub_fetch_catalog(resource, telegram_user_id, correlation_id)

    monkeypatch.setattr("telegram_integration.orchestration.fetch_catalog", unreachable_sports)

    result = handle_message(redis_client, "user-k", "pt-BR", "Bet365, odd 1.85, valor R$ 50,00", "corr-1")

    assert result.status == "blocked"
    assert result.message == "Ocorreu um erro. Tente novamente mais tarde."
    pending = get_pending(redis_client, "user-k")
    assert pending is not None
    assert pending.catalog_ids == {"bettingHouseId": "bh-1"}
    assert pending.awaiting_catalog is None


def test_bet_date_defaults_to_today_when_not_otherwise_known(redis_client: redis.Redis) -> None:
    handle_message(redis_client, "user-g", "pt-BR", "odd 1.85, R$ 50,00", "corr-1")
    handle_message(redis_client, "user-g", "pt-BR", "1", "corr-1")
    handle_message(redis_client, "user-g", "pt-BR", "1", "corr-1")
    handle_message(redis_client, "user-g", "pt-BR", "1", "corr-1")
    result = handle_message(redis_client, "user-g", "pt-BR", "1", "corr-1")

    assert result.status == "complete"
    assert result.bet is not None
    assert result.bet["bet_date"] == datetime.now(UTC).date().isoformat()


def test_asks_in_english_when_language_code_is_en(redis_client: redis.Redis) -> None:
    result = handle_message(redis_client, "user-f", "en", "no useful info here", "corr-1")

    assert result.message == "What was the odd on that bet?"
