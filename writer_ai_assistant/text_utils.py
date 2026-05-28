from __future__ import annotations

TELEGRAM_MAX_MESSAGE_CHARS = 4096


def split_for_telegram(text: str, max_len: int = TELEGRAM_MAX_MESSAGE_CHARS) -> list[str]:
    text = (text or "").strip()
    if not text:
        return [""]

    if len(text) <= max_len:
        return [text]

    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_len)
        chunk = text[start:end]
        if end < len(text):
            last_break = max(chunk.rfind("\n\n"), chunk.rfind("\n"))
            if last_break > 0:
                end = start + last_break
                chunk = text[start:end]
        parts.append(chunk.strip())
        start = end

    return [p for p in parts if p != ""]

