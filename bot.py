import os
import io
import re
import html
import base64
import asyncio
import logging
from typing import Optional
const port = process.env.PORT || 4000 

from PIL import Image, UnidentifiedImageError
from groq import Groq
from groq import BadRequestError

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Text uchun barqaror model, rasm uchun current multimodal model.
TEXT_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3.6-27b",
]

SYSTEM_PROMPT_TEXT = (
    "Sen foydalanuvchi yuborgan matnni tahlil qiladigan yordamchi botsan. "
    "Javobni qisqa, aniq va foydali ber. O‘rinsiz uzunlik qilma."
)

SYSTEM_PROMPT_IMAGE = (
    "Sen foydalanuvchi yuborgan rasmni tahlil qiladigan yordamchi botsan. "
    "Rasmda ko‘rinayotgan narsalarni aniq tasvirla, ehtimoliy xulosa ber, "
    "lekin ko‘rinmaydigan narsani aniq deb aytma."
)

groq_client: Optional[Groq] = None


def get_client() -> Groq:
    if groq_client is None:
        raise RuntimeError("Groq client initialize qilinmagan.")
    return groq_client


def sanitize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return text.strip()


def split_message(text: str, limit: int = 3900) -> list[str]:
    text = text.strip()
    if not text:
        return ["(bo‘sh javob)"]
    return [text[i:i + limit] for i in range(0, len(text), limit)]


async def send_long_message(bot, chat_id: int, text: str) -> None:
    for chunk in split_message(text):
        await bot.send_message(chat_id=chat_id, text=chunk)


def compress_image_for_groq(raw_bytes: bytes) -> bytes:
    """
    Groq vision docs base64 image input uchun limit qo‘yadi.
    Shu sabab rasmni kichraytirib, JPEGga aylantiramiz.
    """
    with Image.open(io.BytesIO(raw_bytes)) as img:
        img = img.convert("RGB")
        img.thumbnail((1280, 1280))

        best_bytes = None
        for quality in (85, 75, 65, 55, 45, 35, 25):
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=quality, optimize=True)
            data = out.getvalue()
            best_bytes = data
            # base64 overhead hisobga olingan xavfsizroq chegara
            if len(data) <= 2_800_000:
                return data

        return best_bytes or raw_bytes


def groq_chat_completion(model: str, messages: list[dict]) -> str:
    client = get_client()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        max_tokens=900,
    )
    content = resp.choices[0].message.content
    return sanitize_text(content)


def analyze_text_sync(user_text: str) -> str:
    last_error: Exception | None = None

    for model in TEXT_MODELS:
        try:
            return groq_chat_completion(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_TEXT},
                    {"role": "user", "content": user_text},
                ],
            )
        except Exception as e:
            last_error = e
            logger.exception("Text model failed: %s", model)

    return f"❌ Matn tahlilida xatolik yuz berdi: {last_error}"


def analyze_image_sync(image_bytes: bytes, prompt: str) -> str:
    last_error: Exception | None = None

    prepared = compress_image_for_groq(image_bytes)
    image_b64 = base64.b64encode(prepared).decode("ascii")

    for model in VISION_MODELS:
        try:
            return groq_chat_completion(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_IMAGE},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_b64}"
                                },
                            },
                        ],
                    },
                ],
            )
        except BadRequestError as e:
            # Model decommission bo‘lsa yoki request formati mos kelmasa, keyingi modelga o‘tamiz.
            last_error = e
            logger.exception("Vision model bad request: %s", model)
        except Exception as e:
            last_error = e
            logger.exception("Vision model failed: %s", model)

    return f"❌ Rasm tahlilida xatolik yuz berdi: {last_error}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message:
        await message.reply_text("🤖 Tayyor. Menga text yoki rasm yuboring.")


async def handle_incoming(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat

    if message is None or chat is None:
        return

    try:
        # RASM
        if message.photo:
            prompt = sanitize_text(message.caption) or "Bu rasmni tahlil qil."
            photo = message.photo[-1]
            file = await photo.get_file()
            raw = await file.download_as_bytearray()

            reply = await asyncio.to_thread(
                analyze_image_sync,
                bytes(raw),
                prompt,
            )
            await send_long_message(context.bot, chat.id, reply)
            return

        # TEXT
        text = sanitize_text(message.text or message.caption)
        if text:
            reply = await asyncio.to_thread(analyze_text_sync, text)
            await send_long_message(context.bot, chat.id, reply)

    except Exception as e:
        logger.exception("Message processing error")
        await send_long_message(context.bot, chat.id, f"❌ Ichki xatolik: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled PTB error: %s", context.error)


async def main() -> None:
    global groq_client

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN topilmadi.")
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY topilmadi.")

    groq_client = Groq(api_key=GROQ_API_KEY)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_incoming))
    app.add_error_handler(error_handler)

    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        # Botni doimiy ish holatida ushlab turadi.
        await asyncio.Event().wait()

    finally:
        try:
            await app.updater.stop()
        except Exception:
            pass
        try:
            await app.stop()
        except Exception:
            pass
        try:
            await app.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
