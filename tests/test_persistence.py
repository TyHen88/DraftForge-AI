from __future__ import annotations

from pathlib import Path

from writer_ai_assistant.persistence import PreferencesStore
from writer_ai_assistant.preferences import ChatPreferences
from writer_ai_assistant.prompt_builder import Mode


def test_load_missing_user_returns_defaults(tmp_path: Path) -> None:
    store = PreferencesStore(str(tmp_path / "t.db"))
    prefs = store.load(1)
    assert prefs.tone == "professional"
    assert prefs.mode is None


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    store = PreferencesStore(str(tmp_path / "t.db"))
    prefs = ChatPreferences(mode=Mode.EMAIL, tone="friendly", signature="Best, Ada")
    store.save(7, prefs)

    loaded = store.load(7)
    assert loaded.mode == Mode.EMAIL
    assert loaded.tone == "friendly"
    assert loaded.signature == "Best, Ada"


def test_save_is_upsert(tmp_path: Path) -> None:
    store = PreferencesStore(str(tmp_path / "t.db"))
    store.save(7, ChatPreferences(tone="friendly"))
    store.save(7, ChatPreferences(tone="academic"))
    assert store.load(7).tone == "academic"
