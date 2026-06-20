"""
Telegram AI Bot — Groq + LLaMA 4 Scout
========================================
Features:
  ✅ Inline keyboard buttons
  ✅ Voice message transcription (Groq Whisper)
  ✅ Image analysis (LLaMA 4 Vision)
  ✅ Multi-language support (auto-detect + /lang)
  ✅ Conversation memory per user
  ✅ Docker + Railway ready
"""

import os, base64, logging, tempfile, json
from io import BytesIO
from pathlib import Path

from groq import Groq
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s │ %(levelname)s │ %(name)s │ %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY   = os.environ["GROQ_API_KEY"]

VISION_MODEL   = "meta-llama/llama-4-scout-17b-16e-instruct"
WHISPER_MODEL  = "whisper-large-v3-turbo"
MAX_HISTORY    = 20
MAX_TOKENS     = 1024

# ── Language config ─────────────────────────────────────────────────────────
LANGUAGES = {
    "en": {"name": "🇬🇧 English",  "system": "You are a helpful, friendly AI assistant in Telegram. Keep responses concise and informative. When the user sends an image, describe it in detail and answer questions about it."},
    "ru": {"name": "🇷🇺 Русский",  "system": "Ты дружелюбный AI-ассистент в Telegram. Отвечай кратко и по делу. Когда пользователь присылает изображение — описывай его подробно и отвечай на вопросы о нём. Всегда отвечай на русском языке."},
    "uz": {"name": "🇺🇿 O'zbek",   "system": "Siz Telegram'dagi do'stona AI yordamchisiz. Qisqa va aniq javob bering. Foydalanuvchi rasm yuborganda uni batafsil tasvirlab, savollarga javob bering. Har doim o'zbek tilida javob bering."},
    "de": {"name": "🇩🇪 Deutsch",  "system": "Du bist ein hilfreicher, freundlicher KI-Assistent in Telegram. Antworte präzise und informativ. Wenn der Nutzer ein Bild schickt, beschreibe es detailliert. Antworte immer auf Deutsch."},
    "fr": {"name": "🇫🇷 Français", "system": "Tu es un assistant IA sympathique dans Telegram. Réponds de façon concise et informative. Quand l'utilisateur envoie une image, décris-la en détail. Réponds toujours en français."},
    "ar": {"name": "🇸🇦 العربية",  "system": "أنت مساعد ذكاء اصطناعي ودود في تيليغرام. أجب بإيجاز وبشكل مفيد. عندما يرسل المستخدم صورة، صفها بالتفصيل. أجب دائماً باللغة العربية."},
    "zh": {"name": "🇨🇳 中文",     "system": "你是Telegram上友好的AI助手。回答要简洁且信息丰富。当用户发送图片时，详细描述图片内容。请始终用中文回答。"},
    "es": {"name": "🇪🇸 Español",  "system": "Eres un asistente de IA amigable en Telegram. Responde de forma concisa e informativa. Cuando el usuario envíe una imagen, descríbela en detalle. Responde siempre en español."},
}
DEFAULT_LANG = "en"

# ── In-memory user state ────────────────────────────────────────────────────
# user_state[user_id] = {"history": [...], "lang": "en"}
user_state: dict[int, dict] = {}

groq_client = Groq(api_key=GROQ_API_KEY)


# ── State helpers ───────────────────────────────────────────────────────────

def get_state(user_id: int) -> dict:
    if user_id not in user_state:
        user_state[user_id] = {"history": [], "lang": DEFAULT_LANG}
    return user_state[user_id]

def get_lang(user_id: int) -> str:
    return get_state(user_id)["lang"]

def get_system(user_id: int) -> str:
    return LANGUAGES[get_lang(user_id)]["system"]

def add_to_history(user_id: int, role: str, content) -> None:
    state = get_state(user_id)
    state["history"].append({"role": role, "content": content})
    if len(state["history"]) > MAX_HISTORY:
        state["history"] = state["history"][-MAX_HISTORY:]

def clear_history(user_id: int) -> None:
    get_state(user_id)["history"] = []


# ── Groq helpers ────────────────────────────────────────────────────────────

async def call_groq(user_id: int) -> str:
    messages = [{"role": "system", "content": get_system(user_id)}] + get_state(user_id)["history"]
    response = groq_client.chat.completions.create(
        model=VISION_MODEL,
        messages=messages,
        max_tokens=MAX_TOKENS,
    )
    return response.choices[0].message.content


async def transcribe_voice(ogg_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(ogg_bytes)
        tmp_path = f.name
    try:
        with open(tmp_path, "rb") as audio_file:
            result = groq_client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=("voice.ogg", audio_file, "audio/ogg"),
                response_format="text",
            )
        return result.strip()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ── Inline keyboards ────────────────────────────────────────────────────────

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑 Clear history", callback_data="clear"),
            InlineKeyboardButton("🌐 Language",      callback_data="lang_menu"),
        ],
        [
            InlineKeyboardButton("ℹ️ Help",          callback_data="help"),
            InlineKeyboardButton("📊 Stats",         callback_data="stats"),
        ],
    ])


def lang_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for code, info in LANGUAGES.items():
        row.append(InlineKeyboardButton(info["name"], callback_data=f"setlang_{code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="main_menu")]])


# ── Command handlers ────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = user.first_name or "there"
    await update.message.reply_text(
        f"👋 *Hello, {name}!* I'm your AI assistant powered by *Groq + LLaMA 4*.\n\n"
        "Here's what I can do:\n"
        "💬 *Chat* — just send me a message\n"
        "📸 *Analyse images* — send any photo\n"
        "🎤 *Transcribe voice* — send a voice message\n"
        "🌐 *Multi-language* — reply in your language\n\n"
        "Use the buttons below or just start chatting!",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📋 *Main Menu* — choose an option:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def cmd_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🌐 *Choose your language:*",
        parse_mode="Markdown",
        reply_markup=lang_keyboard(),
    )


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    clear_history(update.effective_user.id)
    await update.message.reply_text("🗑️ Conversation cleared! Starting fresh.", reply_markup=main_menu_keyboard())


# ── Callback query handler (inline buttons) ─────────────────────────────────

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        await query.edit_message_text(
            "📋 *Main Menu* — choose an option:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    elif data == "clear":
        clear_history(user_id)
        await query.edit_message_text(
            "🗑️ *History cleared!* Ready for a fresh conversation.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    elif data == "lang_menu":
        current = LANGUAGES[get_lang(user_id)]["name"]
        await query.edit_message_text(
            f"🌐 *Choose your language:*\nCurrent: {current}",
            parse_mode="Markdown",
            reply_markup=lang_keyboard(),
        )

    elif data.startswith("setlang_"):
        code = data.replace("setlang_", "")
        if code in LANGUAGES:
            get_state(user_id)["lang"] = code
            lang_name = LANGUAGES[code]["name"]
            await query.edit_message_text(
                f"✅ Language set to *{lang_name}*!\nI'll now reply in that language.",
                parse_mode="Markdown",
                reply_markup=back_keyboard(),
            )

    elif data == "help":
        await query.edit_message_text(
            "🤖 *How to use me:*\n\n"
            "• Send any *text* to chat\n"
            "• Send a *photo* (+ optional caption) to analyse\n"
            "• Send a *voice message* to transcribe & reply\n"
            "• Use */lang* to switch reply language\n"
            "• I remember the last 20 messages\n\n"
            f"_Model: {VISION_MODEL}_\n"
            f"_Whisper: {WHISPER_MODEL}_",
            parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )

    elif data == "stats":
        state = get_state(user_id)
        history_len = len(state["history"])
        lang_name = LANGUAGES[state["lang"]]["name"]
        await query.edit_message_text(
            f"📊 *Your session stats:*\n\n"
            f"💬 Messages in history: *{history_len}*\n"
            f"🌐 Language: *{lang_name}*\n"
            f"🤖 Model: `{VISION_MODEL}`",
            parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )


# ── Message handlers ────────────────────────────────────────────────────────

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    await update.message.chat.send_action("typing")
    add_to_history(user_id, "user", text)
    try:
        reply = await call_groq(user_id)
        add_to_history(user_id, "assistant", reply)
        await update.message.reply_text(reply, reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.error("Groq text error: %s", e)
        await update.message.reply_text("⚠️ Something went wrong. Please try again.")


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    caption = update.message.caption or "Please analyse this image in detail."
    await update.message.chat.send_action("typing")

    photo = update.message.photo[-1]
    file = await ctx.bot.get_file(photo.file_id)
    buf = BytesIO()
    await file.download_to_memory(buf)
    image_b64 = base64.b64encode(buf.getvalue()).decode()

    vision_content = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        {"type": "text", "text": caption},
    ]
    add_to_history(user_id, "user", vision_content)
    try:
        reply = await call_groq(user_id)
        add_to_history(user_id, "assistant", reply)
        await update.message.reply_text(reply, reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.error("Groq vision error: %s", e)
        await update.message.reply_text("⚠️ Could not analyse the image. Please try again.")


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.chat.send_action("typing")

    # Download voice file
    voice = update.message.voice
    file = await ctx.bot.get_file(voice.file_id)
    buf = BytesIO()
    await file.download_to_memory(buf)

    try:
        # Transcribe with Groq Whisper
        transcription = await transcribe_voice(buf.getvalue())
        if not transcription:
            await update.message.reply_text("⚠️ Could not transcribe the voice message.")
            return

        # Show transcription first
        await update.message.reply_text(f"🎤 *Transcribed:*\n_{transcription}_", parse_mode="Markdown")

        # Then respond to it
        await update.message.chat.send_action("typing")
        add_to_history(user_id, "user", transcription)
        reply = await call_groq(user_id)
        add_to_history(user_id, "assistant", reply)
        await update.message.reply_text(reply, reply_markup=main_menu_keyboard())

    except Exception as e:
        logger.error("Voice error: %s", e)
        await update.message.reply_text("⚠️ Could not process voice message. Please try again.")


# ── Entry point ────────────────────────────────────────────────────────────

async def post_init(app) -> None:
    """Set bot commands visible in Telegram UI."""
    await app.bot.set_my_commands([
        BotCommand("start", "Welcome & main menu"),
        BotCommand("menu",  "Show main menu"),
        BotCommand("lang",  "Change language"),
        BotCommand("clear", "Clear chat history"),
        BotCommand("help",  "Usage tips"),
    ])


def main() -> None:
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu",  cmd_menu))
    app.add_handler(CommandHandler("lang",  cmd_lang))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("help",  lambda u, c: handle_callback(
        type("FakeUpdate", (), {"callback_query": type("Q", (), {
            "answer": lambda: None, "from_user": u.effective_user,
            "data": "help",
            "edit_message_text": u.message.reply_text
        })()})(), c
    )))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("🚀 Bot is running…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
