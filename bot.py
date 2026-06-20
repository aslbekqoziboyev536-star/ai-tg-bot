import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from groq import Groq

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)

# ENV
TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# DEBUG PRINT (Render logda ko‘rasan)
print("🔑 BOT_TOKEN:", TOKEN)
print("🔑 GROQ_API_KEY:", GROQ_API_KEY)

# Groq client (agar key bo‘lsa)
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


# 1️⃣ START COMMAND TEST
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ BOT ISHLAYAPTI (START OK)")


# 2️⃣ HANDLER TEST
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    # STEP 1: handler test
    if user_text.lower() == "test":
        await update.message.reply_text("🧪 HANDLER OK")
        return

    # STEP 2: ENV test
    if not GROQ_API_KEY:
        await update.message.reply_text("❌ GROQ_API_KEY YO‘Q (ENV muammo)")
        return

    # STEP 3: AI test
    try:
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[
                {"role": "system", "content": "Sen qisqa va aniq javob beradigan botsan."},
                {"role": "user", "content": user_text}
            ]
        )

        reply = response.choices[0].message.content
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"❌ GROQ ERROR: {e}")


# MAIN
def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN topilmadi!")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
