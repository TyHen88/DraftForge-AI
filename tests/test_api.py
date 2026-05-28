from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from writer_ai_assistant.api import create_app
from writer_ai_assistant.config import Settings
from writer_ai_assistant.persistence import PreferencesStore
from writer_ai_assistant.rate_limit import SlidingWindowRateLimiter

from .test_initdata import BOT_TOKEN, make_init_data


class StubOpenAIService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def generate(self, mode, user_text, **kwargs) -> str:
        self.calls.append({"mode": mode, "text": user_text, **kwargs})
        return f"[{mode.value}] {user_text}"


def build_settings(tmp_path: Path, *, max_requests: int = 20) -> Settings:
    return Settings(
        telegram_bot_token=BOT_TOKEN,
        openai_api_key="sk-test",
        openai_base_url="https://api.openai.com/v1",
        openai_model="gpt-test",
        openai_system_role="system",
        max_input_chars=8000,
        max_output_tokens=800,
        temperature=0.7,
        rate_limit_max_requests=max_requests,
        rate_limit_window_seconds=60,
        openai_timeout_seconds=30,
        log_level="INFO",
        api_host="127.0.0.1",
        api_port=8000,
        frontend_origin="*",
        db_path=str(tmp_path / "api.db"),
        initdata_max_age_seconds=86400,
    )


def make_client(settings: Settings) -> tuple[TestClient, StubOpenAIService]:
    service = StubOpenAIService()
    limiter = SlidingWindowRateLimiter(
        settings.rate_limit_max_requests, settings.rate_limit_window_seconds
    )
    store = PreferencesStore(settings.db_path)
    app = create_app(settings, service, limiter, store)  # type: ignore[arg-type]
    return TestClient(app), service


def auth_headers() -> dict:
    return {"Authorization": f"tma {make_init_data()}"}


def test_health_is_open(tmp_path: Path) -> None:
    client, _ = make_client(build_settings(tmp_path))
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_generate_requires_auth(tmp_path: Path) -> None:
    client, _ = make_client(build_settings(tmp_path))
    resp = client.post("/api/generate", json={"mode": "email", "text": "hi"})
    assert resp.status_code == 401


def test_generate_happy_path(tmp_path: Path) -> None:
    client, service = make_client(build_settings(tmp_path))
    resp = client.post(
        "/api/generate",
        json={"mode": "improve", "text": "make this better", "tone": "friendly"},
        headers=auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"] == "[improve] make this better"
    assert body["mode"] == "improve"
    assert service.calls[0]["tone"] == "friendly"


def test_generate_rejects_unknown_mode(tmp_path: Path) -> None:
    client, _ = make_client(build_settings(tmp_path))
    resp = client.post(
        "/api/generate",
        json={"mode": "nonsense", "text": "x"},
        headers=auth_headers(),
    )
    assert resp.status_code == 422


def test_generate_rejects_empty_text(tmp_path: Path) -> None:
    client, _ = make_client(build_settings(tmp_path))
    resp = client.post(
        "/api/generate",
        json={"mode": "email", "text": "   "},
        headers=auth_headers(),
    )
    assert resp.status_code == 422


def test_template_overrides_mode(tmp_path: Path) -> None:
    client, service = make_client(build_settings(tmp_path))
    resp = client.post(
        "/api/generate",
        json={"mode": "email", "text": "a gadget", "template": "social_caption"},
        headers=auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "template"
    assert service.calls[0]["template_instruction"]


def test_rate_limit_returns_429(tmp_path: Path) -> None:
    client, _ = make_client(build_settings(tmp_path, max_requests=1))
    payload = {"mode": "email", "text": "hi"}
    first = client.post("/api/generate", json=payload, headers=auth_headers())
    assert first.status_code == 200
    second = client.post("/api/generate", json=payload, headers=auth_headers())
    assert second.status_code == 429
    assert "Retry-After" in second.headers


def test_prefs_persist_across_requests(tmp_path: Path) -> None:
    client, _ = make_client(build_settings(tmp_path))
    put = client.put("/api/prefs", json={"signature": "Best, Ada"}, headers=auth_headers())
    assert put.status_code == 200
    me = client.get("/api/me", headers=auth_headers())
    assert me.json()["prefs"]["signature"] == "Best, Ada"
