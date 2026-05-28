# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Telegram bot that wraps an OpenAI-compatible chat API to act as a writing assistant (emails, replies, rewrites, idea generation, templated content). Runs as a long-lived polling worker — no webhook, no HTTP port.

## Commands

```bash
pip install -e ".[dev,api]"               # install with dev tooling + API deps (Python 3.11+)
python -m writer_ai_assistant             # run the bot (polling); same as `... run`
python -m writer_ai_assistant serve       # run the Mini App HTTP API (FastAPI/uvicorn)
python -m writer_ai_assistant doctor      # print masked config + make one test API call

pytest -q                                 # run the test suite
ruff check .                              # lint (and `ruff check . --fix` to autofix)

docker build -t writer-ai-assistant .
docker run --rm --env-file .env writer-ai-assistant
```

Config is read from a `.env` file (see `.env.example`); `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY` are required or `load_settings()` raises. `load_dotenv(..., override=True)` means `.env` wins over pre-set shell env vars — useful to know when debugging stale-config issues.

Tooling (added in Mini App Phase 0): `pytest` (tests in `tests/`), `ruff` (config in `pyproject.toml`; `E501` is intentionally ignored because prompt strings are long), and `mypy` are dev dependencies. `doctor` remains the live-API smoke test; run it after touching config, prompts, or the OpenAI client. `tests/test_import_safety.py` guards the key seam — the reusable core must not import `telegram`.

## Architecture

Flow: Telegram update → handler (`handlers.py`) → `prompt_builder` builds system+user prompts → `OpenAIService.generate()` → `split_for_telegram()` chunks the reply to ≤4096 chars → sent back.

- **`__main__.py`** — argparse entry with two subcommands (`run`, `doctor`); bare invocation defaults to `run`.
- **`telegram_bot.py`** — `run_polling()` builds the PTB `Application`, constructs the singletons (`Settings`, `SlidingWindowRateLimiter`, `OpenAIService`) once, and **injects them into handlers via `functools.partial`** at registration time. This is the dependency-injection seam — handlers receive these as keyword args rather than importing globals.
- **`handlers.py`** — the bulk of the logic. Slash-command handlers are thin; the heavy lifting is in `text_message_handler`, a single dispatcher that handles (in order): reply-keyboard button labels, multi-step conversation flows, tone selection, then default text processing. All AI calls funnel through `_process_text()` (input-length check → rate-limit check → typing indicator → `OpenAIService.generate` → chunked reply).
- **`prompt_builder.py`** — `Mode` (a `StrEnum`) is the central concept that drives everything. `SYSTEM_INSTRUCTIONS` holds the stable system prompt incl. prompt-injection guardrails; `prompt_spec_for_mode()` returns per-mode instructions + a user-text prefix. Adding a feature usually means adding a `Mode` member here.
- **`openai_service.py`** — wraps `AsyncOpenAI` with a timeout and 3 retries (linear backoff). `OPENAI_SYSTEM_ROLE` may be `developer` instead of `system` to support OpenAI-compatible providers (e.g. AICC) that reject the `system` role.
- **`preferences.py`** — `ChatPreferences` is serialized to/from PTB's `context.chat_data` (`load_prefs`/`save_prefs`). `Mode` enums are stored as their `.value` strings and parsed back defensively. **`chat_data` is in-memory only** (no PTB persistence configured), so all per-chat state — mode, tone, signature, in-progress flow steps — is lost on restart.
- **`templates.py`** — four canned content templates, all using `Mode.TEMPLATE`; a template adds an `instruction` string that gets folded into the prompt.
- **`menu_ui.py`** — builds the reply keyboards. Button labels carry emoji prefixes (e.g. `"✉️ Email"`), and `text_message_handler` matches against these exact label constants — so changing a label string requires updating both the menu and the handler comparisons.
- **`rate_limit.py`** — in-process sliding-window limiter keyed per user.

### Mini App HTTP API (Phase 1)

A FastAPI backend added per `docs/mini-app-analysis.md`. It is a **separate entrypoint** (`serve`); the polling bot is untouched, and the two share no process today. The API reuses the transport-agnostic core unchanged.

- **`serve.py`** — `run_api()` builds the same singletons as the bot (`Settings`, `SlidingWindowRateLimiter`, `OpenAIService`) plus a `PreferencesStore`, wires them into the app, and runs uvicorn on `API_PORT` (Railway's injected `PORT` takes precedence).
- **`api.py`** — `create_app(settings, openai_service, limiter, store)` builds the FastAPI app. Endpoints: `GET /api/health`, `GET /api/me`, `PUT /api/prefs`, `POST /api/generate`. Auth is a `current_user` dependency that validates Telegram `initData` from the `Authorization: tma <initData>` header (or `X-Telegram-Init-Data`); the rate limiter is keyed by the **validated** user id, never a client-sent id. CORS allows `FRONTEND_ORIGIN` (comma-separated).
- **`initdata.py`** — `validate_init_data()` does the HMAC-SHA256 check (secret = `HMAC_SHA256("WebAppData", bot_token)`) plus `auth_date` freshness; raises `InitDataError`.
- **`persistence.py`** — `PreferencesStore` (SQLite at `DB_PATH`) persists per-user prefs across restarts, reusing `ChatPreferences` + `load_prefs`/`save_prefs` serialization. This is the API's replacement for the bot's in-memory `chat_data`.

### Multi-step conversation flows

`REPLY` and `EMAIL` are not single-shot. They run small state machines tracked by `prefs.reply_step` / `prefs.email_step` (e.g. `awaiting_context` → `awaiting_tone` → `awaiting_additional`), with `prefs.reply_context` holding the user's text across turns. `text_message_handler` branches on these step fields before falling through to normal processing. When editing these flows, account for every step value and reset them (`prefs.*_step = ""`) when the flow completes or `⬅️ Back` is pressed.

### Mode vs. tone overlap

Some quick-action buttons (Shorten, Friendly, Professional, Polish, Normal) map to `Mode` members, while the tone menu offers overlapping names (`shortened`, `professional`, `polished`, etc.) parsed by `_normalize_tone_choice`. These are distinct mechanisms — a `Mode` selects the task/prompt; a tone is metadata folded into the user prompt. Keep them straight when adding either.

## Deployment

Railway via `railway.toml` (Dockerfile builder, `startCommand = "python -m writer_ai_assistant run"`, `restartPolicyType = ALWAYS`). Because the bot uses polling, only one instance may run per bot token at a time — running locally and on Railway simultaneously causes Telegram `getUpdates` conflicts.
