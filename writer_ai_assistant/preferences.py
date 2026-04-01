from __future__ import annotations

from dataclasses import dataclass

from writer_ai_assistant.prompt_builder import Mode


@dataclass
class ChatPreferences:
    mode: Mode | None = None
    tone: str = "professional"  # professional|academic|marketing|storytelling
    length: str = "normal"  # short|normal
    signature: str = ""
    pending_mode: Mode | None = None
    template: str = ""  # template key
    reply_context: str = ""
    reply_step: str = ""  # awaiting_context | awaiting_confirmation | awaiting_tone | awaiting_additional
    email_step: str = ""  # awaiting_context | awaiting_tone


def load_prefs(chat_data: dict) -> ChatPreferences:
    mode_val = chat_data.get("mode")
    pending_val = chat_data.get("pending_mode")
    prefs = ChatPreferences(
        tone=(chat_data.get("tone") or "professional"),
        length=(chat_data.get("length") or "normal"),
        signature=(chat_data.get("signature") or ""),
        template=(chat_data.get("template") or ""),
        reply_context=(chat_data.get("reply_context") or ""),
        reply_step=(chat_data.get("reply_step") or ""),
        email_step=(chat_data.get("email_step") or ""),
    )
    if mode_val:
        try:
            prefs.mode = Mode(mode_val)
        except Exception:
            prefs.mode = None
    if pending_val:
        try:
            prefs.pending_mode = Mode(pending_val)
        except Exception:
            prefs.pending_mode = None
    return prefs


def save_prefs(chat_data: dict, prefs: ChatPreferences) -> None:
    if prefs.mode is None:
        chat_data.pop("mode", None)
    else:
        chat_data["mode"] = prefs.mode.value

    chat_data["tone"] = prefs.tone
    chat_data["length"] = prefs.length
    chat_data["signature"] = prefs.signature

    if prefs.pending_mode is None:
        chat_data.pop("pending_mode", None)
    else:
        chat_data["pending_mode"] = prefs.pending_mode.value

    chat_data["template"] = prefs.template
    chat_data["reply_context"] = prefs.reply_context
    chat_data["reply_step"] = prefs.reply_step
    chat_data["email_step"] = prefs.email_step
