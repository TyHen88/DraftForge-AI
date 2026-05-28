# Mini App + Feature Improvement Analysis

Branch: `feature/mini-app-ux`

## Decisions locked (2026-05-28)

- **Frontend:** React + TypeScript + Vite + `@telegram-apps/sdk-react` +
  `@telegram-apps/telegram-ui` (see §3). Vanilla MVP rejected.
- **Backend topology:** separate standalone FastAPI service; existing polling bot stays
  unchanged (Option A in §3). Webhook consolidation deferred to a possible Phase 4.
- **Frontend hosting:** GitHub Pages (static, free, HTTPS). See §7 for Pages-specific
  gotchas (Vite `base`, CORS origin, SPA 404).
- **Status:** analysis only — no implementation started yet. Phases 0–4 below are the
  agreed roadmap, to be picked up on direction.

## 1. Where we are today

- **Transport:** Telegram bot, long-polling worker. No HTTP server, no public port.
- **UI:** reply-keyboard buttons (`menu_ui.py`) + slash commands. Multi-step flows
  (EMAIL/REPLY) are hand-rolled state machines driven by `prefs.*_step` string fields.
- **State:** per-chat prefs live in PTB `context.chat_data` — **in-memory only**, lost on
  every restart. No DB.
- **Business logic is already decoupled** from Telegram and reusable as-is:
  - `openai_service.py` — `AsyncOpenAI` wrapper, retries, timeout, system/developer role.
  - `prompt_builder.py` — `Mode` enum + per-mode prompt specs + injection guardrails.
  - `templates.py`, `rate_limit.py`, `text_utils.py`.
- **Telegram-coupled** (would be partly replaced/duplicated by an API): `handlers.py`,
  `menu_ui.py`, `telegram_bot.py`.
- **Partly reusable:** `preferences.py` imports no Telegram — `load_prefs`/`save_prefs`
  operate on a plain `dict`, so the `ChatPreferences` model + (de)serialization are
  transport-agnostic (only the dict's *source*, PTB `context.chat_data`, is Telegram-specific).
  `ChatPreferences` can seed the Phase-1 persistence schema directly.

**Implication:** the bulk of the value (prompting + OpenAI calls) can be exposed behind an
HTTP API with almost no change. The work is adding a web server, auth, persistence, and a
frontend — not rewriting the core.

## 2. What a Telegram Mini App actually requires

A Mini App is an HTTPS web page launched from the bot (menu button / keyboard button /
inline). It is **not** a reply keyboard. To ship one we need three new pieces:

1. **A backend HTTP API** (we have none today). Responsibilities:
   - Validate Telegram `initData` to authenticate the user — no separate login. The check is
     HMAC-SHA256 over the sorted data-check-string using a secret key derived as
     `HMAC-SHA256("WebAppData", bot_token)` (two-step — not the raw bot token), plus an
     `auth_date` freshness check. **Never trust the client-sent user id.**
   - Expose endpoints (e.g. `POST /api/generate`) that reuse `OpenAIService` +
     `prompt_builder` + the rate limiter (keyed by the validated Telegram user id).
   - Keep the OpenAI key server-side (it already is — must stay that way).
2. **A static HTTPS frontend** (the SPA the user sees inside Telegram).
3. **Bot wiring** — set the menu button / a keyboard button to the web-app URL. The bot
   keeps handling `/start` etc.

## 3. Recommended target architecture

```
Telegram app
  ├── Bot (polling, unchanged)         → /start, /help, "Open app" button
  └── Mini App (webview)
        → React SPA (static, CDN)
            → POST /api/generate  ──►  FastAPI
                                         ├── initData validation
                                         ├── rate_limit (reuse)
                                         ├── prompt_builder (reuse)
                                         └── OpenAIService (reuse)
                                         └── SQLite/Postgres (prefs + history)
```

### Backend: add FastAPI
- Natural fit (Python 3.11, async already). Runs `uvicorn`.
- Reuses every service module unchanged. `handlers.py` logic becomes thin API endpoints.
- **Deploy choice — two options:**
  - **A. Two roles, one repo (recommended start):** keep the polling bot as today; add a
    separate FastAPI service for the API. Simple, isolates the polling single-instance
    constraint from the web tier.
  - **B. Single webhook service:** move the bot to webhook and serve bot + API + static
    from one FastAPI deployable. More cohesive, one URL, but requires webhook setup and
    couples bot uptime to the web service. Consider later.

### Frontend: React + Vite + Telegram UI kit (recommended)
- **React + TypeScript + Vite** — fastest DX, richest Mini App ecosystem.
- **`@telegram-apps/sdk-react`** — theme params, `initData`, MainButton, BackButton,
  haptics, viewport handling.
- **`@telegram-apps/telegram-ui`** — official-style components that match Telegram's
  native look (auto light/dark, iOS/Android variants) so it feels built-in, not bolted-on.
- **TanStack Query** for the generate calls (loading/error states, caching, retries).
- **Host** the static build on **GitHub Pages** (the locked choice — free, HTTPS, CDN; see
  §7 for Pages-specific gotchas). Cloudflare Pages / Vercel are equivalent fallbacks if that
  changes — note the §7 gotchas (Vite `base`, CORS origin) are written for GitHub Pages.

**Alternatives considered:**
- *Vanilla HTML/JS + `telegram-web-app.js`* — zero build, ship a v1 in hours. Good as a
  throwaway MVP, but no component kit; UX investment doesn't compound. Use only if speed
  beats polish for a first demo.
- *Vue/Svelte* — both viable; chosen against only because React has the
  `telegram-ui` kit and the largest Mini App community. No strong technical blocker.

## 4. UX wins the Mini App unlocks (vs reply keyboards)

- Real multiline text area with a live character counter against `MAX_INPUT_CHARS`.
- Proper forms: mode tabs, tone dropdown, length toggle, template picker **with
  descriptions** (today templates are opaque button labels).
- Theme-adaptive native styling + haptic feedback + a single "Generate" MainButton.
- Result actions: **copy to clipboard**, **regenerate**, **refine inline**, and **send the
  result back into the chat** (`WebApp.sendData` for keyboard-button apps / `switchInlineQuery`).
- **Streaming output** (typing effect) — large perceived-latency win in a webview.
- Persistent **history** screen (needs backend storage).
- **Diff view** for improve/rewrite/grammar (highlight what changed).
- A real **settings screen** (signature, default tone) that actually persists.

## 5. Feature backlog (transport-independent, reusable by bot + Mini App)

Prioritized:

1. **Persistence** — replace in-memory `chat_data` with SQLite (Railway: Postgres). Fixes
   "state lost on restart"; prerequisite for history & settings.
2. **Iterative refine** — generalize the ad-hoc REPLY multi-step refine into a reusable
   "refine last result with this instruction" capability (keep last output server-side).
3. **Streaming responses** (SSE) — biggest perceived-speed improvement.
4. **Distinct error surfacing** — today all exceptions collapse to one generic message;
   separate rate-limit / bad-key / timeout / content errors (the `doctor` already
   distinguishes these — reuse that logic).
5. **Daily quota** — current limiter is per-window only; add a per-user daily cap for cost.
6. **Usage/cost tracking** — log tokens per request (no PII / no full user text).
7. **Regenerate / N variations.**
8. **Diff view** for improve/grammar/rewrite.
9. **Multilingual** output (language selector).
10. **Custom user templates/snippets.**
11. **Tooling/tests** — `.gitignore` already anticipates `ruff`/`mypy`/`pytest` but none are
    configured. The decoupled modules (`prompt_builder`, `rate_limit`, `text_utils`) are
    trivially unit-testable; add a minimal CI-able setup.

## 6. Suggested phasing

- **Phase 0 — tooling & seams:** add ruff/mypy/pytest; confirm services are import-safe
  without Telegram. Small, de-risks everything after.
- **Phase 1 — API + persistence:** FastAPI `POST /api/generate` with initData validation,
  reuse rate limiter; SQLite for prefs. Bot stays polling. (Backend usable via curl.)
- **Phase 2 — frontend MVP:** React + Vite + telegram-ui; theme + initData + MainButton;
  one generate flow end-to-end; deploy static; set bot menu button to the URL.
- **Phase 3 — UX depth:** streaming, history, refine, copy/share, settings, diff view.
- **Phase 4 (optional):** consolidate bot onto webhook served by the same FastAPI.

## 7. Deployment topology (Railway-aware)

Today: **one** Railway service — a polling *worker* (no port), `python -m
writer_ai_assistant run`. The concern: does going React force more services? **No.**

A React Mini App has two deployable parts plus the existing bot:

1. **Frontend** — a static build (`vite build` → `dist/`). **Not a Railway service.**
   Hosting: **GitHub Pages** (chosen) — free, HTTPS, deploy via `actions/deploy-pages`.
   Pages gotchas:
   - **Vite `base`** must be `'/<repo>/'` for a project page (`<user>.github.io/<repo>/`),
     else assets 404 / blank page. Use `'/'` only for a user/org page or custom domain.
   - **SPA deep links 404** (no server rewrite) — copy `index.html`→`404.html` or use hash
     routing if you add multi-route navigation. Single-screen app: usually moot.
   - **CORS origin** to allow on the API is `https://<user>.github.io` (scheme+host, no path).
   - `index.html` caches ~10 min on the CDN; Vite hashed filenames cache-bust assets.
2. **API + bot** — stays on Railway.

### Reconciling "separate API service" with "one Railway service"

"Separate" was a **code/process** decision (a standalone FastAPI app module that doesn't
entangle the bot), not necessarily a **separate Railway service**. Two ways to deploy it
(labeled Deploy-1 / Deploy-2 to avoid colliding with §3's code-topology Option A/B):

- **Deploy-1 — one Railway service, combined process (recommended given the constraint):**
  one container runs FastAPI (uvicorn on `$PORT`) **and** the polling bot in the same
  asyncio loop (`application.initialize/start` + `updater.start_polling()` run concurrently
  with the uvicorn server via `asyncio.gather`). The service flips from *worker* to *web*
  (gets a public HTTPS URL for the API). **Still one Railway service. No cost increase.**
- **Deploy-2 — two Railway services (same repo, different start commands):** a `worker`
  (bot) + a `web` (API). Cleaner isolation and independent restarts, but doubles the
  Railway footprint. Adopt only when the web tier needs to scale independently.

### Scaling caveat (why Deploy-1 has a ceiling)

Polling requires **exactly one** bot instance per token. In the combined process you
therefore can't run >1 replica without two pollers fighting over `getUpdates`. If web
traffic ever needs horizontal scaling, the clean fix is to **move the bot to webhook** —
it becomes a route inside FastAPI, and then a single service handles bot + API *and*
scales. That's the natural end-state single-service design (the deferred Phase 4), and it's
worth knowing Deploy-1 is a stepping stone toward it, not a dead end.

### Concrete changes for Deploy-1

- `railway.toml`: `startCommand` changes from `... run` to a combined entrypoint; the
  service now needs to listen on `$PORT` (Railway injects it).
- New env: `FRONTEND_ORIGIN` (for CORS — the Pages/Vercel domain), `PORT`, plus a public
  app URL used when setting the bot's menu button.
- FastAPI must enable **CORS** for the frontend origin; OpenAI/bot tokens stay server-side.
- **Local dev:** the webview can't load `http://localhost`, so testing the Mini App inside
  Telegram needs an HTTPS tunnel (`cloudflared`/`ngrok`) pointing at local uvicorn.

### Recommendation

Frontend on **GitHub Pages** (free, the locked choice) + **Deploy-1** (single-service) on
Railway → you stay at **one Railway service**, no new recurring cost. Revisit Deploy-2 /
webhook only when scaling demands it.

## 8. Risks & constraints

- **Polling is single-instance per token** — local + deployed bot at once = `getUpdates`
  conflict. (Already noted in CLAUDE.md.) The web API tier does not have this limit.
- **In-process rate limiter isn't shared across processes.** `SlidingWindowRateLimiter`
  counts in a per-process dict, so a global per-user limit only holds when bot and API run
  in **one** process (Deploy-1). Under Deploy-2 each process counts independently (~2× the
  cap per user). Move the limiter to Redis if you split the processes.
- **initData must be validated server-side** every request; treat the client as untrusted.
  Respect the `auth_date` freshness window.
- **HTTPS required.** Local Mini App testing needs a tunnel (cloudflared/ngrok) or
  Telegram's test environment — you can't load `http://localhost` inside the webview.
- **Hosting:** frontend free-tier is fine; backend needs an always-on public service
  (Railway already in use). CORS must allow the frontend origin.
- **Secrets:** OpenAI/bot tokens never reach the frontend bundle.
