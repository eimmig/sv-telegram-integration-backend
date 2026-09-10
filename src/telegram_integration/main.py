import base64
import os
import uuid
from typing import Annotated, Literal

import redis
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from telegram_integration.auth_client import LinkOutcome, confirm_telegram_link
from telegram_integration.bets_client import SubmitOutcome, submit_bet
from telegram_integration.body_size_limit import BodySizeLimitMiddleware
from telegram_integration.conversation import build_redis_client, clear_pending
from telegram_integration.i18n import get_message
from telegram_integration.ocr import extract_text
from telegram_integration.orchestration import handle_message

app = FastAPI(title="telegram-integration")
# 10 MiB: photoBase64 carries a Telegram bot photo (compressed by the Bot API) - well above any
# real message, generous enough to never reject a legitimate one.
app.add_middleware(BodySizeLimitMiddleware, max_bytes=10 * 1024 * 1024)


def _expected_service_key() -> str:
    return os.environ.get("SERVICE_KEY", "")


def require_service_key(x_service_key: Annotated[str | None, Header()] = None) -> None:
    """n8n -> this service, same X-Service-Key credential already used for this
    service's own outbound calls to api-gateway (bets_client.py/catalog_client.py) -
    not a new secret. Was accepted as unauthenticated while the service only ran on
    the host, unexposed (see services/telegram-integration/n8n/README.md); now that
    it's containerized (infra/feat-004), the documented trigger for revisiting it
    is met.
    """
    expected = _expected_service_key()
    if not expected or x_service_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing X-Service-Key"
        )

_LINK_OUTCOME_MESSAGE_KEY = {
    LinkOutcome.SUCCESS: "link_success",
    LinkOutcome.CODE_NOT_FOUND: "link_code_invalid",
    LinkOutcome.CODE_EXPIRED: "link_code_expired",
    LinkOutcome.ALREADY_LINKED: "link_already_linked",
    LinkOutcome.SERVICE_UNAVAILABLE: "generic_error",
}

_SUBMIT_OUTCOME_MESSAGE_KEY = {
    SubmitOutcome.CREATED: "bet_submitted",
    SubmitOutcome.ALREADY_SUBMITTED: "bet_submitted",
    SubmitOutcome.NO_TELEGRAM_LINK: "bet_submit_no_link",
    SubmitOutcome.CATALOG_ENTRY_NOT_FOUND: "bet_submit_catalog_not_found",
    SubmitOutcome.VALIDATION_FAILED: "bet_submit_validation_failed",
    SubmitOutcome.SERVICE_UNAVAILABLE: "generic_error",
}
_SUBMIT_SUCCESS_OUTCOMES = (SubmitOutcome.CREATED, SubmitOutcome.ALREADY_SUBMITTED)
# NO_TELEGRAM_LINK/SERVICE_UNAVAILABLE keep the resolved bet in Redis on purpose -
# the data itself is fine, only an external condition needs to change before a
# retry can succeed (link the account; wait out the outage). CATALOG_ENTRY_NOT_FOUND
# and VALIDATION_FAILED mean the bet's own data is what's wrong - preserving it
# would just make every retry fail the same way forever, so those also clear state
# alongside a real success.
_SUBMIT_OUTCOMES_THAT_CLEAR_STATE = (
    *_SUBMIT_SUCCESS_OUTCOMES,
    SubmitOutcome.CATALOG_ENTRY_NOT_FOUND,
    SubmitOutcome.VALIDATION_FAILED,
)

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:  # pragma: no cover - overridden in tests
    global _redis_client
    if _redis_client is None:
        _redis_client = build_redis_client()
    return _redis_client


class NormalizedMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    telegram_user_id: str = Field(alias="telegramUserId")
    language_code: str | None = Field(default=None, alias="languageCode")
    chat_id: str = Field(alias="chatId")
    text: str | None = None
    photo_base64: str | None = Field(default=None, alias="photoBase64")
    telegram_update_id: str | None = Field(default=None, alias="telegramUpdateId")


class CaptureResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["pending", "complete", "blocked"]
    message: str
    chat_id: str = Field(alias="chatId")
    bet: dict[str, str | None] | None = None


class LinkAccountRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    telegram_user_id: str = Field(alias="telegramUserId")
    language_code: str | None = Field(default=None, alias="languageCode")
    chat_id: str = Field(alias="chatId")
    code: str


class LinkAccountResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str
    chat_id: str = Field(alias="chatId")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/bets/capture", dependencies=[Depends(require_service_key)])
def capture_bet(
    payload: NormalizedMessage,
    client: Annotated[redis.Redis, Depends(get_redis_client)],
) -> CaptureResponse:
    if payload.photo_base64:
        text = extract_text(base64.b64decode(payload.photo_base64))
    else:
        text = payload.text or ""

    correlation_id = str(uuid.uuid4())
    result = handle_message(client, payload.telegram_user_id, payload.language_code, text, correlation_id)

    status, message, bet = result.status, result.message, result.bet
    if result.status == "complete" and result.bet is not None:
        idempotency_key = (
            f"{payload.telegram_user_id}:{payload.telegram_update_id}"
            if payload.telegram_update_id
            else str(uuid.uuid4())
        )
        outcome = submit_bet(result.bet, payload.telegram_user_id, idempotency_key, correlation_id)
        message = get_message(_SUBMIT_OUTCOME_MESSAGE_KEY[outcome], payload.language_code)
        if outcome in _SUBMIT_OUTCOMES_THAT_CLEAR_STATE:
            clear_pending(client, payload.telegram_user_id)
        status = "complete" if outcome in _SUBMIT_SUCCESS_OUTCOMES else "blocked"
        if status == "blocked":
            bet = None

    return CaptureResponse(
        status=status,
        message=message,
        chatId=payload.chat_id,
        bet=bet,
    )


@app.post("/telegram/link", dependencies=[Depends(require_service_key)])
def link_account(payload: LinkAccountRequest) -> LinkAccountResponse:
    correlation_id = str(uuid.uuid4())
    outcome = confirm_telegram_link(payload.telegram_user_id, payload.code, correlation_id)
    message_key = _LINK_OUTCOME_MESSAGE_KEY[outcome]
    message = get_message(message_key, payload.language_code)
    return LinkAccountResponse(message=message, chatId=payload.chat_id)
