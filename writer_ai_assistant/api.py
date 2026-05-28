"""FastAPI backend for the Telegram Mini App (docs/mini-app-analysis.md, Phase 1).

Reuses the transport-agnostic core unchanged: ``OpenAIService`` + ``prompt_builder`` for
generation, ``SlidingWindowRateLimiter`` keyed by the validated Telegram user id, and
``PreferencesStore`` for persistence. The polling bot is untouched.

Auth: every request carries Telegram ``initData`` in the ``Authorization: tma <initData>``
header (``X-Telegram-Init-Data`` is also accepted). It is validated server-side; the
client-sent user id is never trusted.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from writer_ai_assistant.config import Settings
from writer_ai_assistant.initdata import InitDataError, TelegramUser, validate_init_data
from writer_ai_assistant.openai_service import OpenAIService
from writer_ai_assistant.persistence import PreferencesStore
from writer_ai_assistant.preferences import ChatPreferences
from writer_ai_assistant.prompt_builder import Mode
from writer_ai_assistant.rate_limit import SlidingWindowRateLimiter
from writer_ai_assistant.templates import TEMPLATES, get_template


class GenerateRequest(BaseModel):
    mode: str
    text: str
    tone: str | None = None
    length: str | None = None
    signature: str | None = None
    template: str | None = None
    extra_instruction: str | None = None


class GenerateResponse(BaseModel):
    result: str
    mode: str
    tone: str


class PrefsUpdate(BaseModel):
    tone: str | None = None
    length: str | None = None
    signature: str | None = None
    default_mode: str | None = None


class PrefsResponse(BaseModel):
    mode: str | None = None
    tone: str = "professional"
    length: str = "normal"
    signature: str = ""


def _prefs_response(prefs: ChatPreferences) -> PrefsResponse:
    return PrefsResponse(
        mode=prefs.mode.value if prefs.mode else None,
        tone=prefs.tone,
        length=prefs.length,
        signature=prefs.signature,
    )


def _parse_init_data(authorization: str | None, x_init_data: str | None) -> str:
    if x_init_data:
        return x_init_data
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "tma" and value:
            return value
    raise HTTPException(status_code=401, detail="missing Telegram initData")


def create_app(
    settings: Settings,
    openai_service: OpenAIService,
    limiter: SlidingWindowRateLimiter,
    store: PreferencesStore,
) -> FastAPI:
    app = FastAPI(title="Writer AI Assistant API")

    # An Origin is scheme+host[+port] with no trailing slash; strip any so a value like
    # "https://app.example.com/" still matches the browser-sent Origin header.
    allow_origins = [
        o.strip().rstrip("/") for o in settings.frontend_origin.split(",") if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["*"],
    )

    def current_user(
        authorization: str | None = Header(default=None),
        x_telegram_init_data: str | None = Header(default=None),
    ) -> TelegramUser:
        init_data = _parse_init_data(authorization, x_telegram_init_data)
        try:
            return validate_init_data(
                init_data,
                settings.telegram_bot_token,
                max_age_seconds=settings.initdata_max_age_seconds,
            )
        except InitDataError as exc:
            raise HTTPException(status_code=401, detail=f"invalid initData: {exc}") from exc

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "model": settings.openai_model}

    @app.get("/api/me")
    def me(user: TelegramUser = Depends(current_user)) -> dict:
        prefs = store.load(user.id)
        return {
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "username": user.username,
            },
            "prefs": _prefs_response(prefs).model_dump(),
            "modes": [m.value for m in Mode],
            "templates": [
                {"key": t.key, "title": t.title, "ask": t.ask} for t in TEMPLATES.values()
            ],
        }

    @app.put("/api/prefs", response_model=PrefsResponse)
    def update_prefs(
        update: PrefsUpdate,
        user: TelegramUser = Depends(current_user),
    ) -> PrefsResponse:
        prefs = store.load(user.id)
        if update.tone is not None:
            prefs.tone = update.tone
        if update.length is not None:
            prefs.length = update.length
        if update.signature is not None:
            prefs.signature = update.signature
        if update.default_mode is not None:
            try:
                prefs.mode = Mode(update.default_mode) if update.default_mode else None
            except ValueError as exc:
                raise HTTPException(
                    status_code=422, detail=f"unknown mode: {update.default_mode}"
                ) from exc
        store.save(user.id, prefs)
        return _prefs_response(prefs)

    @app.post("/api/generate", response_model=GenerateResponse)
    async def generate(
        req: GenerateRequest,
        user: TelegramUser = Depends(current_user),
    ) -> GenerateResponse:
        text = (req.text or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="text is required")
        if len(text) > settings.max_input_chars:
            raise HTTPException(
                status_code=413,
                detail=f"text exceeds {settings.max_input_chars} characters",
            )

        template_instruction = ""
        if req.template:
            template = get_template(req.template)
            if template is None:
                raise HTTPException(status_code=422, detail=f"unknown template: {req.template}")
            mode = Mode.TEMPLATE
            template_instruction = template.instruction
        else:
            try:
                mode = Mode(req.mode)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"unknown mode: {req.mode}") from exc

        decision = limiter.check(str(user.id))
        if not decision.allowed:
            raise HTTPException(
                status_code=429,
                detail="rate limit exceeded",
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )

        stored = store.load(user.id)
        tone = req.tone if req.tone is not None else stored.tone
        length = req.length if req.length is not None else stored.length
        signature = req.signature if req.signature is not None else stored.signature

        try:
            result = await openai_service.generate(
                mode,
                text,
                tone=tone,
                length=length,
                signature=signature,
                template_instruction=template_instruction,
                extra_instruction=req.extra_instruction or "",
            )
        except Exception as exc:  # noqa: BLE001 - surface upstream failures as 502
            raise HTTPException(status_code=502, detail="generation failed") from exc

        stored.mode = mode
        stored.tone = tone
        stored.length = length
        if req.signature is not None:
            stored.signature = signature
        store.save(user.id, stored)

        return GenerateResponse(result=result, mode=mode.value, tone=tone)

    return app
