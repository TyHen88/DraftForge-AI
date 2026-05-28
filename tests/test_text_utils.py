from __future__ import annotations

from writer_ai_assistant.text_utils import TELEGRAM_MAX_MESSAGE_CHARS, split_for_telegram


def test_short_text_is_single_chunk() -> None:
    assert split_for_telegram("hello") == ["hello"]


def test_empty_text_returns_single_empty_chunk() -> None:
    assert split_for_telegram("   ") == [""]


def test_long_text_is_chunked_within_limit() -> None:
    text = "\n".join(f"line {i}" for i in range(5000))
    chunks = split_for_telegram(text)
    assert len(chunks) > 1
    assert all(len(c) <= TELEGRAM_MAX_MESSAGE_CHARS for c in chunks)


def test_prefers_newline_breaks() -> None:
    block = "a" * 4000
    text = block + "\n" + "b" * 4000
    chunks = split_for_telegram(text)
    assert chunks[0] == block
