from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
import redis
from testcontainers.community.redis import RedisContainer

from telegram_integration.conversation import get_pending
from telegram_integration.orchestration import handle_message


@pytest.fixture(scope="module")
def redis_client() -> Iterator[redis.Redis]:
    with RedisContainer() as container:
        client: redis.Redis = container.get_client()
        yield client


def test_asks_for_the_first_missing_required_field(redis_client: redis.Redis) -> None:
    result = handle_message(redis_client, "user-a", "pt-BR", "mensagem sem nada reconhecivel")

    assert result.status == "pending"
    assert result.message == "Qual foi a odd dessa aposta?"
    assert result.bet is None


def test_asks_for_stake_when_only_odd_was_found(redis_client: redis.Redis) -> None:
    result = handle_message(redis_client, "user-b", "pt-BR", "odd 1.85")

    assert result.status == "pending"
    assert result.message == "Quanto você apostou (valor em R$)?"


def test_follow_up_answer_fills_the_awaited_field_and_completes(redis_client: redis.Redis) -> None:
    handle_message(redis_client, "user-c", "pt-BR", "odd 1.85")

    result = handle_message(redis_client, "user-c", "pt-BR", "50")

    assert result.status == "complete"
    assert result.bet is not None
    assert result.bet["odd"] == "1.85"
    assert result.bet["stake"] == "50"
    assert get_pending(redis_client, "user-c") is None


def test_completes_and_clears_state_once_every_required_field_is_known(redis_client: redis.Redis) -> None:
    handle_message(redis_client, "user-d", "pt-BR", "odd 1.85")

    result = handle_message(redis_client, "user-d", "pt-BR", "50")

    assert result.status == "complete"
    assert result.message == "Captura concluída até aqui. O restante do cadastro continua em breve."
    assert result.bet is not None
    assert result.bet["odd"] == "1.85"
    assert result.bet["stake"] == "50"
    assert get_pending(redis_client, "user-d") is None


def test_extracts_everything_from_a_single_complete_message(redis_client: redis.Redis) -> None:
    result = handle_message(redis_client, "user-e", "pt-BR", "Bet365, odd 1.85, valor R$ 50,00")

    assert result.status == "complete"
    assert result.bet is not None
    assert result.bet["odd"] == "1.85"
    assert result.bet["stake"] == "50.00"
    assert result.bet["betting_house"] == "Bet365"


def test_bet_date_defaults_to_today_when_not_otherwise_known(redis_client: redis.Redis) -> None:
    result = handle_message(redis_client, "user-g", "pt-BR", "odd 1.85, R$ 50,00")

    assert result.status == "complete"
    assert result.bet is not None
    assert result.bet["bet_date"] == datetime.now(UTC).date().isoformat()


def test_asks_in_english_when_language_code_is_en(redis_client: redis.Redis) -> None:
    result = handle_message(redis_client, "user-f", "en", "no useful info here")

    assert result.message == "What was the odd on that bet?"
