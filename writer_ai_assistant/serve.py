"""Entrypoint for the Mini App API server (``python -m writer_ai_assistant serve``).

Builds the same singletons the bot uses (settings, rate limiter, OpenAI service) plus the
SQLite preference store, wires them into the FastAPI app, and runs uvicorn. The polling bot
is a separate entrypoint (``run``); this serves only the HTTP API.
"""

from __future__ import annotations

import logging

import uvicorn

from writer_ai_assistant.api import create_app
from writer_ai_assistant.config import load_settings
from writer_ai_assistant.openai_service import OpenAIService
from writer_ai_assistant.persistence import PreferencesStore
from writer_ai_assistant.rate_limit import SlidingWindowRateLimiter


def run_api() -> None:
    settings = load_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    limiter = SlidingWindowRateLimiter(
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    openai_service = OpenAIService(settings)
    store = PreferencesStore(settings.db_path)

    app = create_app(settings, openai_service, limiter, store)

    logging.getLogger(__name__).info(
        "API starting on %s:%s (model=%s, origin=%s)",
        settings.api_host,
        settings.api_port,
        settings.openai_model,
        settings.frontend_origin,
    )
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
