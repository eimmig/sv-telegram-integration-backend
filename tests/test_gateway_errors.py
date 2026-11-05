import httpx
import pytest

from telegram_integration.gateway_errors import is_telegram_account_not_found

_NO_LINK_TYPE = "https://docs/errors/telegram-account-not-found"


def test_recognizes_the_no_link_problem_from_the_gateway() -> None:
    response = httpx.Response(404, json={"type": _NO_LINK_TYPE, "status": 404})

    assert is_telegram_account_not_found(response)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404, json={"type": "https://docs/errors/betting-house-not-found"}),
        httpx.Response(404, json={"title": "no type field"}),
        httpx.Response(404, json=[_NO_LINK_TYPE]),
        httpx.Response(404, json={"type": 404}),
        httpx.Response(404, text="<html>Not Found</html>"),
        httpx.Response(401, json={"type": _NO_LINK_TYPE}),
    ],
)
def test_other_responses_are_not_the_no_link_problem(response: httpx.Response) -> None:
    assert not is_telegram_account_not_found(response)
