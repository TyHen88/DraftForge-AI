from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    openai_system_role: str

    max_input_chars: int
    max_output_tokens: int
    temperature: float

    rate_limit_max_requests: int
    rate_limit_window_seconds: int

    openai_timeout_seconds: int
    log_level: str

    # Web API (Mini App backend). Unused by the polling bot.
    api_host: str
    api_port: int
    frontend_origin: str
    db_path: str
    initdata_max_age_seconds: int

    # Public HTTPS URL of the Mini App. When set, the bot's menu button opens it.
    webapp_url: str


def load_settings() -> Settings:
    # Find .env from current working directory upwards so running from a different cwd still works.
    # Use `.env` as the source of truth for local dev to avoid confusion with stale shell env vars.
    load_dotenv(find_dotenv(usecwd=True), override=True)

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
    openai_system_role = os.getenv("OPENAI_SYSTEM_ROLE", "system").strip().lower() or "system"

    if not telegram_bot_token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN (set it in .env or environment).")
    if not openai_api_key:
        raise RuntimeError("Missing OPENAI_API_KEY (set it in .env or environment).")

    return Settings(
        telegram_bot_token=telegram_bot_token,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        openai_model=openai_model,
        openai_system_role=openai_system_role,
        max_input_chars=_get_int("MAX_INPUT_CHARS", 8000),
        max_output_tokens=_get_int("MAX_OUTPUT_TOKENS", 800),
        temperature=_get_float("TEMPERATURE", 0.7),
        rate_limit_max_requests=_get_int("RATE_LIMIT_MAX_REQUESTS", 20),
        rate_limit_window_seconds=_get_int("RATE_LIMIT_WINDOW_SECONDS", 60),
        openai_timeout_seconds=_get_int("OPENAI_TIMEOUT_SECONDS", 30),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip() or "INFO",
        api_host=os.getenv("API_HOST", "0.0.0.0").strip() or "0.0.0.0",
        # Railway injects PORT; fall back to API_PORT then a local default.
        api_port=_get_int("PORT", _get_int("API_PORT", 8000)),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "*").strip() or "*",
        db_path=os.getenv("DB_PATH", "writer_ai.db").strip() or "writer_ai.db",
        initdata_max_age_seconds=_get_int("INITDATA_MAX_AGE_SECONDS", 86400),
        webapp_url=os.getenv("WEBAPP_URL", "").strip(),
    )
