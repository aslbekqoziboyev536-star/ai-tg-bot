# 🤖 Telegram AI Bot — Groq + LLaMA 4

A production-ready Telegram bot with **image analysis**, **voice transcription**, **inline buttons**, and **multi-language support** — powered by [Groq](https://groq.com) (free & fast).

---

## ✨ Features

| Feature | Details |
|---|---|
| 💬 Chat | Multi-turn conversation with memory (last 20 messages) |
| 📸 Image analysis | Send any photo — described & answered via LLaMA 4 Vision |
| 🎤 Voice messages | Transcribed with Groq Whisper, then AI replies |
| 🌐 Multi-language | 8 languages: EN, RU, UZ, DE, FR, AR, ZH, ES |
| 🔘 Inline buttons | Menu, language picker, stats, clear history |
| ⚡ Speed | Groq inference is extremely fast (often < 1s) |
| 🆓 Free | Groq free tier is generous for personal/small-team use |
| 🐳 Docker ready | Single `docker compose up` to deploy anywhere |
| 🚂 Railway ready | Push to GitHub → auto-deploy on Railway |

---

## 🚀 Local Setup (5 minutes)

### 1 · Get a Telegram Bot Token
1. Open Telegram → search **@BotFather**
2. Send `/newbot`, follow the steps
3. Copy the token (looks like `123456:ABC-DEF...`)

### 2 · Get a Groq API Key
1. Sign up free at [console.groq.com](https://console.groq.com)
2. **API Keys → Create API Key**
3. Copy the key (starts with `gsk_...`)

### 3 · Run locally
```bash
pip install -r requirements.txt

export TELEGRAM_TOKEN="your_token_here"
export GROQ_API_KEY="your_groq_key_here"

python bot.py
```

Or with `.env` file:
```bash
cp .env.example .env
# Edit .env, then:
export $(grep -v '^#' .env | xargs) && python bot.py
```

---

## 🐳 Deploy with Docker

```bash
# 1. Fill in your keys
cp .env.example .env
nano .env

# 2. Build & run
docker compose up -d

# 3. Check logs
docker compose logs -f
```

---

## 🚂 Deploy on Railway (free, 24/7)

Railway gives you a free hobby plan with 500 hours/month — enough for a personal bot.

### Option A — One-click via GitHub
1. Push this folder to a GitHub repo
2. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub**
3. Select your repo
4. Go to **Variables** tab and add:
   - `TELEGRAM_TOKEN` = your bot token
   - `GROQ_API_KEY` = your Groq key
5. Railway auto-builds the Dockerfile and deploys 🎉

### Option B — Railway CLI
```bash
npm install -g @railway/cli
railway login
railway init
railway up

# Set env vars
railway variables set TELEGRAM_TOKEN=your_token
railway variables set GROQ_API_KEY=your_key
```

---

## 💬 Bot Commands

| Command | Action |
|---|---|
| `/start` | Welcome message + main menu |
| `/menu` | Show main menu buttons |
| `/lang` | Choose reply language |
| `/clear` | Reset conversation history |
| `/help` | Usage tips |

### Inline Menu Buttons
- 🗑 **Clear history** — forget the conversation
- 🌐 **Language** — switch between 8 languages
- ℹ️ **Help** — usage guide
- 📊 **Stats** — messages in history, current language

---

## 🌐 Supported Languages

| Code | Language |
|---|---|
| `en` | 🇬🇧 English (default) |
| `ru` | 🇷🇺 Russian |
| `uz` | 🇺🇿 Uzbek |
| `de` | 🇩🇪 German |
| `fr` | 🇫🇷 French |
| `ar` | 🇸🇦 Arabic |
| `zh` | 🇨🇳 Chinese |
| `es` | 🇪🇸 Spanish |

---

## 🧠 Models Used

| Task | Model |
|---|---|
| Chat + Vision | `meta-llama/llama-4-scout-17b-16e-instruct` |
| Voice → Text | `whisper-large-v3-turbo` |

Both are available on Groq's **free tier**.

---

## 📁 Project Structure

```
telegram_groq_bot/
├── bot.py              # Main bot (all features)
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container build
├── docker-compose.yml  # Local Docker orchestration
├── railway.toml        # Railway deploy config
├── .env.example        # Environment variable template
└── README.md           # This file
```
