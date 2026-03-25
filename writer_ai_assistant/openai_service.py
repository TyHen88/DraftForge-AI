from __future__ import annotations

import asyncio

from openai import AsyncOpenAI

from writer_ai_assistant.config import Settings
from writer_ai_assistant.prompt_builder import Mode, build_instructions, build_user_input


class OpenAIService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
        )

    async def generate(
        self,
        mode: Mode,
        user_text: str,
        *,
        tone: str = "default",
        length: str = "normal",
        signature: str = "",
        template_instruction: str = "",
    ) -> str:
        system_prompt = build_instructions(mode)
        user_prompt = build_user_input(
            mode,
            user_text,
            tone=tone,
            length=length,
            signature=signature,
            template_instruction=template_instruction,
        )

        system_role = "developer" if self._settings.openai_system_role == "developer" else "system"

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                completion = await self._client.chat.completions.create(
                    model=self._settings.openai_model,
                    messages=[
                        {"role": system_role, "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=self._settings.temperature,
                    max_tokens=self._settings.max_output_tokens,
                )
                content = (completion.choices[0].message.content or "").strip()
                return content
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    await asyncio.sleep(0.6 * attempt)
                    continue
                raise

        raise last_error or RuntimeError("OpenAI request failed")
