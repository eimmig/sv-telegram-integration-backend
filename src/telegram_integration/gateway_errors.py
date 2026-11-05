from __future__ import annotations

import httpx

_TELEGRAM_ACCOUNT_NOT_FOUND_TYPE_SUFFIX = "/telegram-account-not-found"


def is_telegram_account_not_found(response: httpx.Response) -> bool:
    if response.status_code != 404:
        return False
    try:
        body = response.json()
    except ValueError:
        return False
    problem_type = body.get("type") if isinstance(body, dict) else None
    return isinstance(problem_type, str) and problem_type.endswith(_TELEGRAM_ACCOUNT_NOT_FOUND_TYPE_SUFFIX)
