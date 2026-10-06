# Telegram Bot & AI Agent sozlamalari
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# 1. Avval .env faylini yuklaymiz
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file)

# 2. Agar .env da token bo'lmasa yoki .env bo'lmasa, .env.example dan yuklash
if not os.getenv("BOT_TOKEN"):
    example_file = BASE_DIR / ".env.example"
    if example_file.exists():
        load_dotenv(example_file)

# Telegram Bot Token (@BotFather dan olinadi)
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# AI Provider sozlamalari (OpenAI yoki OpenAI-formatidagi Gemini / DeepSeek)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", None)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Admin yoki Moliya bo'limi Telegram Chat ID
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()

# Server porti va xosti
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "127.0.0.1")

# Ma'lumotlar bazasi fayli
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "database" / "moshina_arenda.db"))
