from __future__ import annotations

import asyncio
import os
import sys

from writer_ai_assistant.config import load_settings
from writer_ai_assistant.prompt_builder import Mode


def _mask(s: str, keep: int = 4) -> str:
    if not s:
        return ""
    if len(s) <= keep:
        return "*" * len(s)
    return ("*" * (len(s) - keep)) + s[-keep:]


async def _doctor_async() -> int:
    settings = load_settings()

    print("Loaded settings:")
    print(f"- OPENAI_BASE_URL={settings.openai_base_url}")
    print(f"- OPENAI_MODEL={settings.openai_model}")
    print(f"- OPENAI_SYSTEM_ROLE={settings.openai_system_role}")
    print(f"- OPENAI_API_KEY={_mask(settings.openai_api_key)} (present={bool(settings.openai_api_key)})")
    print(f"- TELEGRAM_BOT_TOKEN={_mask(settings.telegram_bot_token)} (present={bool(settings.telegram_bot_token)})")
    print("")

    # Minimal test request (does not require Telegram to be working).
    try:
        from writer_ai_assistant.openai_service import OpenAIService
    except ModuleNotFoundError as exc:
        if exc.name == "openai":
            print("OpenAI SDK is not installed in this environment.")
            print("Install dependencies (in your venv): pip install -e .")
            return 3
        raise

    service = OpenAIService(settings)
    try:
        text = await service.generate(Mode.REPLY, "Hello! (diagnostic test)")
        print("API call: OK")
        print(text[:4000])
        return 0
    except Exception as exc:
        print("API call: FAILED")
        print(f"{type(exc).__name__}: {exc}")

        # Best-effort extra details for OpenAI SDK errors.
        status = getattr(exc, "status_code", None)
        if status is not None:
            print(f"status_code={status}")
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                print(f"response.url={getattr(response, 'url', None)}")
            except Exception:
                pass

        # Also show env overrides (common cause of confusion).
        print("")
        print("Env check:")
        for name in ["OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_SYSTEM_ROLE"]:
            val = os.getenv(name)
            if val is None:
                print(f"- {name} is not set in process env")
            elif name.endswith("_KEY"):
                print(f"- {name}={_mask(val)}")
            else:
                print(f"- {name}={val}")
        return 2


def run_doctor() -> None:
    try:
        code = asyncio.run(_doctor_async())
    except KeyboardInterrupt:
        code = 130
    sys.exit(code)
