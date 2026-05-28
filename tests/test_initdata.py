from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from writer_ai_assistant.initdata import InitDataError, validate_init_data

BOT_TOKEN = "123456:TEST-TOKEN"


def make_init_data(
    *,
    bot_token: str = BOT_TOKEN,
    user: dict | None = None,
    auth_date: int | None = None,
    tamper: bool = False,
) -> str:
    user = user or {"id": 42, "first_name": "Ada", "username": "ada"}
    auth_date = auth_date if auth_date is not None else int(time.time())

    fields = {
        "query_id": "AAH",
        "user": json.dumps(user),
        "auth_date": str(auth_date),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()

    fields["hash"] = "0" * 64 if tamper else digest
    return urlencode(fields)


def test_valid_init_data_returns_user() -> None:
    user = validate_init_data(make_init_data(), BOT_TOKEN)
    assert user.id == 42
    assert user.username == "ada"


def test_tampered_hash_rejected() -> None:
    with pytest.raises(InitDataError):
        validate_init_data(make_init_data(tamper=True), BOT_TOKEN)


def test_wrong_bot_token_rejected() -> None:
    with pytest.raises(InitDataError):
        validate_init_data(make_init_data(), "999:OTHER-TOKEN")


def test_expired_init_data_rejected() -> None:
    old = int(time.time()) - 10_000
    with pytest.raises(InitDataError):
        validate_init_data(make_init_data(auth_date=old), BOT_TOKEN, max_age_seconds=60)


def test_missing_hash_rejected() -> None:
    with pytest.raises(InitDataError):
        validate_init_data("user=%7B%7D&auth_date=1", BOT_TOKEN)


def test_empty_rejected() -> None:
    with pytest.raises(InitDataError):
        validate_init_data("", BOT_TOKEN)
