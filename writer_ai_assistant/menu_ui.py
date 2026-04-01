from __future__ import annotations

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from writer_ai_assistant.templates import TEMPLATES


BTN_IDEA = "💡 Idea"
BTN_TEMPLATES = "🧩 Templates"
BTN_EMAIL = "✉️ Email"
BTN_REPLY = "💬 Reply"
BTN_IMPROVE = "✨ Improve"
BTN_REWRITE = "🔁 Rewrite"
BTN_GRAMMAR = "✅ Grammar"
BTN_EXPLAIN = "📚 Explain"
BTN_TONE = "🎭 Tone"
BTN_BACK = "⬅️ Back"
BTN_YES = "✅ YES"
BTN_NO = "❌ NO"

BTN_SHORTEN = "🤏 Shorten"
BTN_FRIENDLY = "😊 Friendly"
BTN_PROFESSIONAL_MODE = "👔 Professional"
BTN_POLISH = "✨ Polish"
BTN_NORMAL = "🆗 Normal"

TEMPLATE_BUTTONS: dict[str, str] = {
    "blog_post": "📝 Blog Post",
    "product_description": "🛍️ Product Description",
    "email_reply_template": "✉️ Email Reply",
    "social_caption": "📣 Social Caption",
}

TONE_BUTTONS: dict[str, str] = {
    "shortened": "🤏 Shortened",
    "friendly": "😊 Friendly",
    "professional": "💼 Professional",
    "academic": "🎓 Academic",
    "marketing": "📣 Marketing",
    "storytelling": "📖 Storytelling",
    "polished": "✨ Polished",
    "normal": "🆗 Normal",
}


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(BTN_IDEA), KeyboardButton(BTN_TEMPLATES), KeyboardButton(BTN_TONE)],
        [KeyboardButton(BTN_EMAIL), KeyboardButton(BTN_REPLY)],
        [KeyboardButton(BTN_IMPROVE), KeyboardButton(BTN_REWRITE), KeyboardButton(BTN_GRAMMAR)],
        [KeyboardButton(BTN_SHORTEN), KeyboardButton(BTN_FRIENDLY), KeyboardButton(BTN_PROFESSIONAL_MODE)],
        [KeyboardButton(BTN_POLISH), KeyboardButton(BTN_NORMAL), KeyboardButton(BTN_EXPLAIN)],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)


def templates_menu() -> ReplyKeyboardMarkup:
    # Keep order stable and simple
    keys = ["blog_post", "product_description", "email_reply_template", "social_caption"]
    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for key in keys:
        t = TEMPLATES.get(key)
        if not t:
            continue
        row.append(KeyboardButton(TEMPLATE_BUTTONS.get(key, t.title)))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(BTN_BACK)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)


def tone_menu(current: str) -> ReplyKeyboardMarkup:
    tones = ["shortened", "friendly", "professional", "academic", "marketing", "storytelling", "polished", "normal"]
    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for tone in tones:
        base = TONE_BUTTONS.get(tone, tone)
        label = f"{base} ✅" if tone == current else base
        row.append(KeyboardButton(label))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(BTN_BACK)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)


def template_key_from_button(text: str) -> str | None:
    normalized = (text or "").strip().lower()
    for key, label in TEMPLATE_BUTTONS.items():
        if normalized == label.strip().lower():
            return key
    return None


def yes_no_menu() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(BTN_YES), KeyboardButton(BTN_NO)],
        [KeyboardButton(BTN_BACK)],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)
