from collections.abc import Iterator

import pytest
import redis
from testcontainers.community.redis import RedisContainer

from telegram_integration.conversation import PendingBet, clear_pending, get_pending, save_pending


@pytest.fixture(scope="module")
def redis_client() -> Iterator[redis.Redis]:
    with RedisContainer() as container:
        client: redis.Redis = container.get_client()
        yield client


def test_get_pending_returns_none_when_nothing_saved(redis_client: redis.Redis) -> None:
    assert get_pending(redis_client, "no-such-user") is None


def test_save_then_get_pending_round_trips(redis_client: redis.Redis) -> None:
    pending = PendingBet(fields={"odd": "1.85", "stake": None}, awaiting_field="stake")

    save_pending(redis_client, "user-1", pending)
    loaded = get_pending(redis_client, "user-1")

    assert loaded == pending


def test_clear_pending_removes_the_state(redis_client: redis.Redis) -> None:
    save_pending(redis_client, "user-2", PendingBet(fields={}, awaiting_field="odd"))

    clear_pending(redis_client, "user-2")

    assert get_pending(redis_client, "user-2") is None


def test_save_pending_sets_a_ttl(redis_client: redis.Redis) -> None:
    save_pending(redis_client, "user-3", PendingBet(fields={}, awaiting_field="odd"))

    ttl = redis_client.ttl("telegram:pending-bet:user-3")

    assert 0 < ttl <= 15 * 60
