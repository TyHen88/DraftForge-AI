"""Validate Telegram Mini App ``initData`` server-side.

The client sends ``initData`` (a urlencoded string) with every request. We authenticate the
user from it — never from a client-sent id. Validation (per Telegram's spec):

1. Parse the urlencoded pairs; pull out ``hash``.
2. Build the data-check-string: remaining pairs as ``key=value``, sorted by key, joined by
   ``\\n``.
3. Derive ``secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)`` (two-step — not the
   raw bot token).
4. Valid iff ``hex(HMAC_SHA256(key=secret_key, msg=data_check_string)) == hash``.
5. Reject stale data via the ``auth_date`` freshness window.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    """Raised when initData is missing, malformed, forged, or expired."""


@dataclass(frozen=True)
class TelegramUser:
    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    language_code: str = ""


def _data_check_string(pairs: list[tuple[str, str]]) -> str:
    kept = [(k, v) for k, v in pairs if k != "hash"]
    kept.sort(key=lambda kv: kv[0])
    return "\n".join(f"{k}={v}" for k, v in kept)


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 86400,
    now: float | None = None,
) -> TelegramUser:
    if not init_data:
        raise InitDataError("empty initData")

    pairs = parse_qsl(init_data, keep_blank_values=True)
    fields = dict(pairs)

    received_hash = fields.get("hash")
    if not received_hash:
        raise InitDataError("missing hash")

    data_check_string = _data_check_string(pairs)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise InitDataError("hash mismatch")

    auth_date_raw = fields.get("auth_date")
    if not auth_date_raw:
        raise InitDataError("missing auth_date")
    try:
        auth_date = int(auth_date_raw)
    except ValueError as exc:
        raise InitDataError("invalid auth_date") from exc

    current = time.time() if now is None else now
    if current - auth_date > max_age_seconds:
        raise InitDataError("initData expired")

    user_raw = fields.get("user")
    if not user_raw:
        raise InitDataError("missing user")
    try:
        user = json.loads(user_raw)
        user_id = int(user["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise InitDataError("invalid user payload") from exc

    return TelegramUser(
        id=user_id,
        first_name=str(user.get("first_name", "")),
        last_name=str(user.get("last_name", "")),
        username=str(user.get("username", "")),
        language_code=str(user.get("language_code", "")),
    )
