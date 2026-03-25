from __future__ import annotations

from telegram import BotCommand, MenuButtonCommands, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from writer_ai_assistant.config import Settings
from writer_ai_assistant.menu_ui import (
    BTN_BACK,
    BTN_EMAIL,
    BTN_EXPLAIN,
    BTN_GRAMMAR,
    BTN_IDEA,
    BTN_IMPROVE,
    BTN_REPLY,
    BTN_REWRITE,
    BTN_TEMPLATES,
    BTN_TONE,
    main_menu,
    template_key_from_button,
    templates_menu,
    tone_menu,
)
from writer_ai_assistant.openai_service import OpenAIService
from writer_ai_assistant.preferences import load_prefs, save_prefs
from writer_ai_assistant.prompt_builder import Mode
from writer_ai_assistant.rate_limit import SlidingWindowRateLimiter
from writer_ai_assistant.templates import TEMPLATES, get_template
from writer_ai_assistant.text_utils import split_for_telegram


HELP_TEXT = (
    "Writer AI Assistant\n\n"
    "Use the menu buttons below or commands.\n\n"
    "Main features:\n"
    "- 💡 Idea generation\n"
    "- 🧩 Templates (blog/product/email reply/social)\n"
    "- ✉️ Email + 💬 Reply\n"
    "- 📚 Explain (general term/word)\n"
    "- 🎭 Tone (professional/academic/marketing/storytelling)\n"
    "- ✨ Improve / 🔁 Rewrite / ✅ Grammar\n"
)


def _get_user_key(update: Update) -> str:
    user = update.effective_user
    if user and user.id:
        return f"user:{user.id}"
    chat = update.effective_chat
    if chat and chat.id:
        return f"chat:{chat.id}"
    return "unknown"


def _extract_command_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    args = getattr(context, "args", None) or []
    return " ".join(args).strip()


def _normalize_tone_choice(text: str) -> str | None:
    t = (text or "").strip().lower().replace("✅", "").strip()
    for tone in ("professional", "academic", "marketing", "storytelling"):
        if tone in t:
            return tone
    return None


async def post_init(application) -> None:
    # Persistent command menu (Menu Button -> Commands)
    commands = [
        BotCommand("menu", "📋 Show menu buttons"),
        BotCommand("idea", "💡 Brainstorm topics/headlines/outline"),
        BotCommand("templates", "🧩 Pick a template"),
        BotCommand("email", "✉️ Draft a professional email"),
        BotCommand("reply", "💬 Write 1-3 short replies"),
        BotCommand("improve", "✨ Improve clarity and professionalism"),
        BotCommand("rewrite", "🔁 Paraphrase (avoid plagiarism)"),
        BotCommand("grammar", "✅ Fix grammar and readability"),
        BotCommand("explain", "📚 Explain a term/word"),
        BotCommand("tone", "🎭 Set tone (professional/academic/marketing/storytelling)"),
        BotCommand("signature", "Set email signature"),
        BotCommand("clearsignature", "Clear signature"),
        BotCommand("help", "Show help"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception:
        # Non-fatal (permissions or older clients)
        pass


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(HELP_TEXT, reply_markup=main_menu())


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(HELP_TEXT, reply_markup=main_menu())


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text("Menu:", reply_markup=main_menu())


async def templates_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text("🧩 Templates:", reply_markup=templates_menu())


async def tone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    prefs = load_prefs(context.chat_data)
    choice = _extract_command_text(context)
    if not choice:
        await update.message.reply_text(f"🎭 Current tone: {prefs.tone}", reply_markup=tone_menu(prefs.tone))
        return
    tone = _normalize_tone_choice(choice)
    if not tone:
        await update.message.reply_text("Valid tones: professional, academic, marketing, storytelling")
        return
    prefs.tone = tone
    save_prefs(context.chat_data, prefs)
    await update.message.reply_text(f"🎭 Tone set to: {tone}", reply_markup=main_menu())


async def signature_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    sig = _extract_command_text(context)
    if not sig:
        await update.message.reply_text("Usage: /signature <your name/title/team>")
        return
    prefs = load_prefs(context.chat_data)
    prefs.signature = sig.strip()
    save_prefs(context.chat_data, prefs)
    await update.message.reply_text("Signature saved.", reply_markup=main_menu())


async def clear_signature_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    prefs = load_prefs(context.chat_data)
    prefs.signature = ""
    save_prefs(context.chat_data, prefs)
    await update.message.reply_text("Signature cleared.", reply_markup=main_menu())


async def mode_command_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    mode: Mode,
    settings: Settings,
    limiter: SlidingWindowRateLimiter,
    openai_service: OpenAIService,
) -> None:
    if not update.message:
        return

    prefs = load_prefs(context.chat_data)
    prefs.mode = mode
    prefs.template = ""

    user_text = _extract_command_text(context)
    if not user_text:
        prefs.pending_mode = mode
        save_prefs(context.chat_data, prefs)
        await update.message.reply_text(f"OK - send the text for /{mode.value}.", reply_markup=main_menu())
        return

    prefs.pending_mode = None
    save_prefs(context.chat_data, prefs)

    await _process_text(
        update,
        context,
        mode=mode,
        user_text=user_text,
        settings=settings,
        limiter=limiter,
        openai_service=openai_service,
    )


async def template_title_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    title: str,
) -> None:
    if not update.message:
        return
    # Map button titles back to template key (supports icon labels)
    key = template_key_from_button(title)
    if not key:
        for k, t in TEMPLATES.items():
            if t.title.lower() == title.strip().lower():
                key = k
                break
    if not key:
        await update.message.reply_text("Unknown template.", reply_markup=templates_menu())
        return

    tpl = get_template(key)
    if not tpl:
        await update.message.reply_text("Unknown template.", reply_markup=templates_menu())
        return

    prefs = load_prefs(context.chat_data)
    prefs.template = tpl.key
    prefs.mode = tpl.mode
    prefs.pending_mode = tpl.mode
    save_prefs(context.chat_data, prefs)
    await update.message.reply_text(f"{tpl.title}\n{tpl.ask}", reply_markup=main_menu())


async def text_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    settings: Settings,
    limiter: SlidingWindowRateLimiter,
    openai_service: OpenAIService,
) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    prefs = load_prefs(context.chat_data)

    # Menu navigation (reply keyboard button labels)
    if text == BTN_BACK:
        await update.message.reply_text("Menu:", reply_markup=main_menu())
        return
    if text == BTN_TEMPLATES:
        await update.message.reply_text("🧩 Templates:", reply_markup=templates_menu())
        return
    if text == BTN_TONE:
        await update.message.reply_text(f"🎭 Current tone: {prefs.tone}", reply_markup=tone_menu(prefs.tone))
        return

    tone_choice = _normalize_tone_choice(text)
    if tone_choice:
        prefs.tone = tone_choice
        save_prefs(context.chat_data, prefs)
        await update.message.reply_text(f"🎭 Tone set to: {tone_choice}", reply_markup=main_menu())
        return

    if template_key_from_button(text) or text in {t.title for t in TEMPLATES.values()}:
        await template_title_handler(update, context, title=text)
        return

    if text == BTN_IDEA:
        prefs.mode = Mode.IDEA
        prefs.pending_mode = Mode.IDEA
        prefs.template = ""
        save_prefs(context.chat_data, prefs)
        await update.message.reply_text("💡 Send a topic or context for idea generation.", reply_markup=main_menu())
        return
    if text == BTN_EMAIL:
        prefs.mode = Mode.EMAIL
        prefs.pending_mode = Mode.EMAIL
        prefs.template = ""
        save_prefs(context.chat_data, prefs)
        await update.message.reply_text("✉️ Send the email context/draft.", reply_markup=main_menu())
        return
    if text == BTN_REPLY:
        prefs.mode = Mode.REPLY
        prefs.pending_mode = Mode.REPLY
        prefs.template = ""
        save_prefs(context.chat_data, prefs)
        await update.message.reply_text("💬 Send the message/context you want to reply to.", reply_markup=main_menu())
        return
    if text == BTN_IMPROVE:
        prefs.mode = Mode.IMPROVE
        prefs.pending_mode = Mode.IMPROVE
        prefs.template = ""
        save_prefs(context.chat_data, prefs)
        await update.message.reply_text("✨ Send the text to improve.", reply_markup=main_menu())
        return
    if text == BTN_REWRITE:
        prefs.mode = Mode.REWRITE
        prefs.pending_mode = Mode.REWRITE
        prefs.template = ""
        save_prefs(context.chat_data, prefs)
        await update.message.reply_text("🔁 Send the text to rewrite (paraphrase).", reply_markup=main_menu())
        return
    if text == BTN_GRAMMAR:
        prefs.mode = Mode.GRAMMAR
        prefs.pending_mode = Mode.GRAMMAR
        prefs.template = ""
        save_prefs(context.chat_data, prefs)
        await update.message.reply_text("✅ Send the text to fix grammar/style.", reply_markup=main_menu())
        return
    if text == BTN_EXPLAIN:
        prefs.mode = Mode.EXPLAIN
        prefs.pending_mode = Mode.EXPLAIN
        prefs.template = ""
        save_prefs(context.chat_data, prefs)
        await update.message.reply_text("📚 Send the word/term to explain.", reply_markup=main_menu())
        return

    # Normal text processing (pending mode first, else last mode)
    mode = prefs.pending_mode or prefs.mode
    if mode is None:
        await update.message.reply_text(HELP_TEXT, reply_markup=main_menu())
        return

    if prefs.pending_mode is not None:
        prefs.pending_mode = None
        save_prefs(context.chat_data, prefs)

    await _process_text(
        update,
        context,
        mode=mode,
        user_text=text,
        settings=settings,
        limiter=limiter,
        openai_service=openai_service,
    )


async def _process_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    mode: Mode,
    user_text: str,
    settings: Settings,
    limiter: SlidingWindowRateLimiter,
    openai_service: OpenAIService,
) -> None:
    if not update.message:
        return

    cleaned = (user_text or "").strip()
    if not cleaned:
        await update.message.reply_text("Please send some text.", reply_markup=main_menu())
        return

    if len(cleaned) > settings.max_input_chars:
        await update.message.reply_text(
            f"That is too long ({len(cleaned)} chars). Max is {settings.max_input_chars}. Please shorten it.",
            reply_markup=main_menu(),
        )
        return

    key = _get_user_key(update)
    limit = limiter.check(key)
    if not limit.allowed:
        await update.message.reply_text(
            f"Rate limit reached. Try again in {limit.retry_after_seconds}s.", reply_markup=main_menu()
        )
        return

    prefs = load_prefs(context.chat_data)
    template_instruction = ""
    if prefs.template:
        tpl = get_template(prefs.template)
        if tpl:
            template_instruction = tpl.instruction

    await update.message.chat.send_action(action=ChatAction.TYPING)

    try:
        result = await openai_service.generate(
            mode,
            cleaned,
            tone=prefs.tone,
            length=prefs.length,
            signature=prefs.signature,
            template_instruction=template_instruction,
        )
    except Exception:
        await update.message.reply_text("Sorry - I couldn't generate a response right now. Please try again.", reply_markup=main_menu())
        return

    if not result:
        await update.message.reply_text("No output returned. Try rephrasing your request.", reply_markup=main_menu())
        return

    for part in split_for_telegram(result):
        await update.message.reply_text(part, disable_web_page_preview=True, reply_markup=main_menu())
