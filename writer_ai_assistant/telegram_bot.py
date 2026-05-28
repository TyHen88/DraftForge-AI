from __future__ import annotations

import logging
from functools import partial

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from writer_ai_assistant.config import Settings, load_settings
from writer_ai_assistant.handlers import (
    clear_signature_handler,
    help_handler,
    menu_handler,
    mode_command_handler,
    post_init,
    signature_handler,
    start_handler,
    templates_handler,
    text_message_handler,
    tone_handler,
)
from writer_ai_assistant.openai_service import OpenAIService
from writer_ai_assistant.prompt_builder import Mode
from writer_ai_assistant.rate_limit import SlidingWindowRateLimiter


def build_application(
    settings: Settings,
    *,
    limiter: SlidingWindowRateLimiter,
    openai_service: OpenAIService,
) -> Application:
    app = ApplicationBuilder().token(settings.telegram_bot_token).post_init(post_init).build()

    logging.getLogger(__name__).info("OpenAI base_url=%s model=%s role=%s", settings.openai_base_url, settings.openai_model, settings.openai_system_role)

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("menu", menu_handler))
    app.add_handler(CommandHandler("templates", templates_handler))
    app.add_handler(CommandHandler("tone", tone_handler))
    app.add_handler(CommandHandler("signature", signature_handler))
    app.add_handler(CommandHandler("clearsignature", clear_signature_handler))

    app.add_handler(
        CommandHandler(
            "email",
            partial(
                mode_command_handler,
                mode=Mode.EMAIL,
                settings=settings,
                limiter=limiter,
                openai_service=openai_service,
            ),
        )
    )
    app.add_handler(
        CommandHandler(
            "reply",
            partial(
                mode_command_handler,
                mode=Mode.REPLY,
                settings=settings,
                limiter=limiter,
                openai_service=openai_service,
            ),
        )
    )
    app.add_handler(
        CommandHandler(
            "improve",
            partial(
                mode_command_handler,
                mode=Mode.IMPROVE,
                settings=settings,
                limiter=limiter,
                openai_service=openai_service,
            ),
        )
    )
    app.add_handler(
        CommandHandler(
            "explain",
            partial(
                mode_command_handler,
                mode=Mode.EXPLAIN,
                settings=settings,
                limiter=limiter,
                openai_service=openai_service,
            ),
        )
    )

    app.add_handler(
        CommandHandler(
            "idea",
            partial(
                mode_command_handler,
                mode=Mode.IDEA,
                settings=settings,
                limiter=limiter,
                openai_service=openai_service,
            ),
        )
    )
    app.add_handler(
        CommandHandler(
            "rewrite",
            partial(
                mode_command_handler,
                mode=Mode.REWRITE,
                settings=settings,
                limiter=limiter,
                openai_service=openai_service,
            ),
        )
    )
    app.add_handler(
        CommandHandler(
            "grammar",
            partial(
                mode_command_handler,
                mode=Mode.GRAMMAR,
                settings=settings,
                limiter=limiter,
                openai_service=openai_service,
            ),
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            partial(
                text_message_handler,
                settings=settings,
                limiter=limiter,
                openai_service=openai_service,
            ),
        )
    )

    return app


def run_polling() -> None:
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

    app = build_application(settings, limiter=limiter, openai_service=openai_service)

    logging.getLogger(__name__).info("Bot starting (polling)...")
    app.run_polling(allowed_updates=None)
