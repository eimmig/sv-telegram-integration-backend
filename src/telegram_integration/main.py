import base64
import uuid
from typing import Annotated, Literal

import redis
from fastapi import Depends, FastAPI
from pydantic import BaseModel, ConfigDict, Field

from telegram_integration.auth_client import LinkOutcome, confirm_telegram_link
from telegram_integration.conversation import build_redis_client
from telegram_integration.i18n import get_message
from telegram_integration.ocr import extract_text
from telegram_integration.orchestration import handle_message

app = FastAPI(title="telegram-integration")

_LINK_OUTCOME_MESSAGE_KEY = {
    LinkOutcome.SUCCESS: "link_success",
    LinkOutcome.CODE_NOT_FOUND: "link_code_invalid",
    LinkOutcome.CODE_EXPIRED: "link_code_expired",
    LinkOutcome.ALREADY_LINKED: "link_already_linked",
    LinkOutcome.SERVICE_UNAVAILABLE: "generic_error",
}

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


class CaptureResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["pending", "complete"]
    message: str
    chat_id: str = Field(alias="chatId")
    bet: dict[str, str | None] | None = None


class LinkAccountRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    telegram_user_id: str = Field(alias="telegramUserId")
    language_code: str | None = Field(default=None, alias="languageCode")
    code: str


class LinkAccountResponse(BaseModel):
    message: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/bets/capture")
def capture_bet(
    payload: NormalizedMessage,
    client: Annotated[redis.Redis, Depends(get_redis_client)],
) -> CaptureResponse:
    if payload.photo_base64:
        text = extract_text(base64.b64decode(payload.photo_base64))
    else:
        text = payload.text or ""

    result = handle_message(client, payload.telegram_user_id, payload.language_code, text)

    return CaptureResponse(
        status=result.status,
        message=result.message,
        chatId=payload.chat_id,
        bet=result.bet,
    )


@app.post("/telegram/link")
def link_account(payload: LinkAccountRequest) -> LinkAccountResponse:
    correlation_id = str(uuid.uuid4())
    outcome = confirm_telegram_link(payload.telegram_user_id, payload.code, correlation_id)
    message_key = _LINK_OUTCOME_MESSAGE_KEY[outcome]
    return LinkAccountResponse(message=get_message(message_key, payload.language_code))
