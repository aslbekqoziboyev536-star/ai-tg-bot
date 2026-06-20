import os
import io
import base64
import logging
from typing import Optional

from PIL import Image
from groq import Groq, BadRequestError
from flask import Flask, request
import telebot

# ====================== SOZLAMALAR ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ====================== GROQ SOZLAMALARI ======================
TEXT_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
VISION_MODELS = ["meta-llama/llama-4-scout-17b-16e-instruct", "qwen/qwen3.6-27b"]

SYSTEM_PROMPT_TEXT = (
    "Sen foydalanuvchi yuborgan matnni tahlil qiladigan yordamchi botsan. "
    "Javobni qisqa, aniq va foydali ber. O‘rinsiz uzunlik qilma."
)
SYSTEM_PROMPT_IMAGE = (
    "Sen foydalanuvchi yuborgan rasmni tahlil qiladigan yordamchi botsan. "
    "Rasmda ko‘rinayotgan narsalarni aniq tasvirla, ehtimoliy xulosa ber, "
    "lekin ko‘rinmaydigan narsani aniq deb aytma."
)

# Global client
groq_client: Optional[Groq] = None

def get_client() -> Groq:
    if groq_client is None:
        raise RuntimeError("Groq client hali initialize qilinmagan.")
    return groq_client

# ====================== YORDAMCHI FUNKSIYALAR ======================
def sanitize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return text.strip()

def split_message(text: str, limit: int = 3900) -> list[str]:
    text = text.strip()
    if not text:
        return ["(bo‘sh javob)"]
    return [text[i:i + limit] for i in range(0, len(text), limit)]

def compress_image_for_groq(raw_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(raw_bytes)) as img:
        img = img.convert("RGB")
        img.thumbnail((1280, 1280))
        for quality in (85, 75, 65, 55, 45, 35, 25):
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=quality, optimize=True)
            data = out.getvalue()
            if len(data) <= 2_800_000:
                return data
        return data or raw_bytes

def groq_chat_completion(model: str, messages: list[dict]) -> str:
    client = get_client()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        max_tokens=900,
    )
    return sanitize_text(resp.choices[0].message.content)

# ====================== FLASK APP ======================
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        bot.process_new_updates([update])
    except Exception as e:
        logger.exception("Webhook xatosi")
    return 'OK', 200

@app.route('/')
def index():
    return "🤖 Groq AI Bot ishlamoqda!"

# ====================== ANALIZ FUNKSIYALARI ======================
def analyze_text_sync(user_text: str) -> str:
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
            logger.exception(f"Text model xatosi: {model}")
    return "❌ Matn tahlilida xatolik yuz berdi."

def analyze_image_sync(image_bytes: bytes, prompt: str) -> str:
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
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        ],
                    },
                ],
            )
        except Exception as e:
            logger.exception(f"Vision model xatosi: {model}")
    return "❌ Rasm tahlilida xatolik yuz berdi."

# ====================== HANDLERLAR ======================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🤖 Salom! Menga matn yoki rasm yuboring.")

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    try:
        if message.photo:
            prompt = sanitize_text(message.caption) or "Bu rasmni batafsil tahlil qil."
            photo = message.photo[-1]
            file_info = bot.get_file(photo.file_id)
            raw = bot.download_file(file_info.file_path)
            reply = analyze_image_sync(raw, prompt)
        else:
            text = sanitize_text(message.text or message.caption)
            if not text:
                return
            reply = analyze_text_sync(text)

        for chunk in split_message(reply):
            bot.reply_to(message, chunk)
    except Exception as e:
        logger.exception("Message handler xatosi")
        bot.reply_to(message, f"❌ Xatolik: {str(e)[:500]}")

# ====================== SERVERNI ISHGA TUSHIRISH ======================
if __name__ == "__main__":
    if not BOT_TOKEN or not GROQ_API_KEY:
        logger.error("BOT_TOKEN yoki GROQ_API_KEY topilmadi!")
        exit(1)

    # Clientni yaratamiz
    global groq_client
    groq_client = Groq(api_key=GROQ_API_KEY)

    # Webhookni o‘rnatish
    bot.remove_webhook()
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
    bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Webhook o‘rnatildi: {webhook_url}")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
