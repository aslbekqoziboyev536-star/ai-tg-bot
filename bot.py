import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Logging
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)

TOKEN = os.getenv("BOT_TOKEN")  # Render env ga qo'yasan

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Bot ishga tushdi!")

# oddiy text handler
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(f"Siz yozdingiz: {text}")

def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN environment variable topilmadi!")

    app = Application.builder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # BOT RUN (ENG TO‘G‘RI USUL)
    app.run_polling()

if __name__ == "__main__":
    main()
