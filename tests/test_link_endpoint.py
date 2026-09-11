import pytest
from fastapi.testclient import TestClient

from telegram_integration.auth_client import LinkOutcome
from telegram_integration.main import app

client = TestClient(app, headers={"X-Service-Key": "test-service-key"})


@pytest.mark.parametrize(
    ("outcome", "expected_message_pt", "expected_message_en"),
    [
        (LinkOutcome.SUCCESS, "Conta vinculada com sucesso!", "Account linked successfully!"),
        (LinkOutcome.CODE_NOT_FOUND, "Código não encontrado.", "Code not found."),
        (LinkOutcome.CODE_EXPIRED, "Esse código expirou.", "That code expired."),
        (LinkOutcome.ALREADY_LINKED, "Essa conta já está vinculada.", "This account is already linked."),
        (LinkOutcome.SERVICE_UNAVAILABLE, "Ocorreu um erro.", "Something went wrong."),
    ],
)
def test_link_account_maps_every_outcome_to_a_localized_message(
    monkeypatch: pytest.MonkeyPatch, outcome: LinkOutcome, expected_message_pt: str, expected_message_en: str
) -> None:
    monkeypatch.setattr("telegram_integration.main.confirm_telegram_link", lambda *_args, **_kwargs: outcome)

    response_pt = client.post(
        "/telegram/link",
        json={"telegramUserId": "999", "code": "ABCD1234", "chatId": "111", "languageCode": "pt-BR"},
    )
    response_en = client.post(
        "/telegram/link",
        json={"telegramUserId": "999", "code": "ABCD1234", "chatId": "111", "languageCode": "en"},
    )

    assert response_pt.status_code == 200
    assert response_pt.json()["message"].startswith(expected_message_pt)
    assert response_pt.json()["chatId"] == "111"
    assert response_en.status_code == 200
    assert response_en.json()["message"].startswith(expected_message_en)


def test_link_account_passes_telegram_user_id_and_code_to_auth_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_confirm(telegram_user_id: str, code: str, correlation_id: str) -> LinkOutcome:
        captured["telegram_user_id"] = telegram_user_id
        captured["code"] = code
        captured["correlation_id"] = correlation_id
        return LinkOutcome.SUCCESS

    monkeypatch.setattr("telegram_integration.main.confirm_telegram_link", fake_confirm)

    response = client.post(
        "/telegram/link", json={"telegramUserId": "999", "code": "ABCD1234", "chatId": "111"}
    )

    assert response.status_code == 200
    assert captured["telegram_user_id"] == "999"
    assert captured["code"] == "ABCD1234"
    assert isinstance(captured["correlation_id"], str)
    assert captured["correlation_id"]
