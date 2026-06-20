import os
import asyncio
import logging
import base64

from groq import Groq
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)


# 🧠 TEXT + IMAGE ANALYSIS CORE
def ask_ai_text(text: str) -> str:
    res = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[
            {"role": "system", "content": "Sen analiz qiluvchi AI botsan."},
            {"role": "user", "content": text}
        ]
    )
    return res.choices[0].message.content


def ask_ai_image(image_bytes: bytes) -> str:
    img_base64 = base64.b64encode(image_bytes).decode()

    res = client.chat.completions.create(
        model="llama-3.2-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Bu rasmni analiz qil"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_base64}"
                        }
                    }
                ]
            }
        ]
    )
    return res.choices[0].message.content


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 AI bot tayyor. Text yoki rasm yuboring.")


# TEXT HANDLER
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    reply = ask_ai_text(user_text)
    await update.message.reply_text(reply)


# IMAGE HANDLER
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    data = await file.download_as_bytearray()

    reply = ask_ai_image(bytes(data))
    await update.message.reply_text(reply)


# MAIN
async def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN yo‘q!")
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY yo‘q!")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
