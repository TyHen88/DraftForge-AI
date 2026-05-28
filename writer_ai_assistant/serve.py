"""Entrypoints for the Mini App HTTP API.

- ``serve`` (``run_api``)  — API only. Useful for local API dev or a separate web service.
- ``web``   (``run_web``)  — combined: the FastAPI API **and** the polling bot in one asyncio
  loop, listening on ``$PORT``. This is the Railway "Deploy-1" topology (one service, one
  process; see docs/mini-app-analysis.md §7). Polling stays single-instance per bot token.
"""

from __future__ import annotations

import asyncio
import logging

import uvicorn

from writer_ai_assistant.api import create_app
from writer_ai_assistant.config import Settings, load_settings
from writer_ai_assistant.openai_service import OpenAIService
from writer_ai_assistant.persistence import PreferencesStore
from writer_ai_assistant.rate_limit import SlidingWindowRateLimiter


def _configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def run_api() -> None:
    settings = load_settings()
    _configure_logging(settings)

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


def run_web() -> None:
    # Import here so the API-only path (`serve`) never needs Telegram installed/configured.
    from writer_ai_assistant.telegram_bot import build_application

    settings = load_settings()
    _configure_logging(settings)

    limiter = SlidingWindowRateLimiter(
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    openai_service = OpenAIService(settings)
    store = PreferencesStore(settings.db_path)

    # The bot and API share one limiter + OpenAI client (single process → unified limits).
    application = build_application(settings, limiter=limiter, openai_service=openai_service)
    fastapi_app = create_app(settings, openai_service, limiter, store)

    asyncio.run(_run_combined(settings, fastapi_app, application))


async def _run_combined(settings: Settings, fastapi_app, application) -> None:
    config = uvicorn.Config(
        fastapi_app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    log = logging.getLogger(__name__)

    async with application:
        await application.start()
        await application.updater.start_polling(allowed_updates=None)
        log.info(
            "Bot polling + API serving on %s:%s", settings.api_host, settings.api_port
        )
        try:
            await server.serve()
        finally:
            if application.updater.running:
                await application.updater.stop()
            await application.stop()
