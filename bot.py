import sys
import io
import asyncio
import logging

# Windows konsolida emojilar sababli UnicodeEncodeError chiqishining oldini olish
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from config import BOT_TOKEN
from agent.agent_runner import agent_instance

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dp = Dispatcher()

# Doimiy pastki tugmalar paneli (Qulay tezkor menyu)
def get_main_keyboard() -> ReplyKeyboardMarkup:
    kb = [
        [
            KeyboardButton(text="💰 Oylik Tushum"),
            KeyboardButton(text="⚠️ Qarzdorlar")
        ],
        [
            KeyboardButton(text="📊 Executive Summary"),
            KeyboardButton(text="🚗 Avtopark Holati")
        ],
        [
            KeyboardButton(text="🔑 Faol Arendalar"),
            KeyboardButton(text="🔔 Eslatma Jo'natish")
        ],
        [
            KeyboardButton(text="📋 Barcha Buyruqlar (/commands)")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# 1. /start BUYRUG'I
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = (
        "👋 **Assalomu alaykum!**\n\n"
        "Men **Baraka Avto Dealership & Rental AI Boshqaruv Maslahatchisi**man.\n"
        "Avtosalon va mashina arendasi (nasiya/ijara) bo'yicha barcha hisob-kitoblar, "
        "tushumlar va qarzdorlarni nazorat qilishda yordam beraman.\n\n"
        "Barcha buyruqlar ro'yxatini ko'rish uchun **/commands** buyrug'ini yuboring "
        "yoki quyidagi menyu tugmalaridan foydalaning!"
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# 2. /commands VA /help BUYRUQLARI
@dp.message(Command("commands"))
@dp.message(Command("help"))
@dp.message(F.text == "📋 Barcha Buyruqlar (/commands)")
async def cmd_commands(message: types.Message):
    commands_text = (
        "📋 **BARAKA AVTO AI AGENT — BUYRUQLAR RO'YXATI**\n\n"
        "Siz quyidagi buyruqlardan yoki tabiiy tildagi savollardan foydalanishingiz mumkin:\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 **MOLIYA VA HISOBOTLAR:**\n"
        "🔹 **/revenue** — Oylik umumiy tushumlar (Naqd, Bo'lib to'lash, Ijara)\n"
        "🔹 **/summary** — Rahbariyat uchun umumiy tahliliy xulosa (Executive Summary)\n\n"
        "⚠️ **QARZDORLAR VA RISK NAZORATI:**\n"
        "🔹 **/debtors** — To'lov muddati kechikkan qarzdorlar ro'yxati\n"
        "🔹 **/remind** — Qarzdorlarga avtomatik SMS / Telegram eslatmalar jo'natish\n\n"
        "🚗 **AVTOPARK VA INVENTAR:**\n"
        "🔹 **/fleet** — Avtopark inventari holati (Salonda, Arendada, Sotilgan)\n"
        "🔹 **/rentals** — Arendadagi faol mashinalar va qolgan kunlar\n\n"
        "⚙️ **TIZIM BUYRUQLARI:**\n"
        "🔹 **/clear** — AI bilan suhbat tarixini tozalash (yangi muloqot)\n"
        "🔹 **/commands** — Ushbu buyruqlar ro'yxatini ko'rsatish\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 **TABIIY TILDA SAVOL BERISH:**\n"
        "Botga oddiy so'zlar bilan ham yoza olasiz. Masalan:\n"
        "• *\"Bu oy qancha foyda qildik?\"*\n"
        "• *\"Kimlarni arendadan qarzi bor?\"*\n"
        "• *\"Tracker 10 B 123 BB haqida ma'lumot ber\"*\n"
        "• *\"Salonda qanday bo'sh mashinalar bor?\"*\n"
        "• *\"Qarzdorlarga eslatma jo'nat\"*\n\n"
        "Tugmalardan birini bosing yoki o'zingiz xohlagan savolni yozing! 👇"
    )
    await message.answer(commands_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# 3. /revenue VA "💰 Oylik Tushum"
@dp.message(Command("revenue"))
@dp.message(F.text == "💰 Oylik Tushum")
async def cmd_revenue(message: types.Message):
    await send_ai_reply(message, "Bu oy qancha tushum bo'ldi?")

# 4. /debtors VA "⚠️ Qarzdorlar"
@dp.message(Command("debtors"))
@dp.message(F.text == "⚠️ Qarzdorlar")
async def cmd_debtors(message: types.Message):
    await send_ai_reply(message, "Kimlarni qarzi bor? Qarzdorlar ro'yxatini ber")

# 5. /summary VA "📊 Executive Summary"
@dp.message(Command("summary"))
@dp.message(F.text == "📊 Executive Summary")
async def cmd_summary(message: types.Message):
    await send_ai_reply(message, "Executive summary hisobotini tayyorla")

# 6. /fleet VA "🚗 Avtopark Holati"
@dp.message(Command("fleet"))
@dp.message(F.text == "🚗 Avtopark Holati")
async def cmd_fleet(message: types.Message):
    await send_ai_reply(message, "Avtopark inventarizatsiyasi holatini ko'rsat")

# 7. /rentals VA "🔑 Faol Arendalar"
@dp.message(Command("rentals"))
@dp.message(F.text == "🔑 Faol Arendalar")
async def cmd_rentals(message: types.Message):
    await send_ai_reply(message, "Faol arendadagi mashinalar va ularning muddatlarini ko'rsat")

# 8. /remind VA "🔔 Eslatma Jo'natish"
@dp.message(Command("remind"))
@dp.message(F.text == "🔔 Eslatma Jo'natish")
async def cmd_remind(message: types.Message):
    await send_ai_reply(message, "Qarzdorlarga eslatma jo'nat")

# 9. /clear BUYRUG'I
@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    chat_id = str(message.chat.id)
    agent_instance.reset_history(chat_id)
    await message.answer(
        "🔄 **Suhbat tarixi tozalandi!**\n"
        "AI Agent yangi muloqotga tayyor. Savolingizni berishingiz mumkin.",
        parse_mode="Markdown"
    )

# 10. BARCHA MATNLI XABARLARNI AI AGENTGA YUBORISH
@dp.message()
async def handle_message(message: types.Message):
    user_text = message.text
    if not user_text:
        return
    await send_ai_reply(message, user_text)

async def send_ai_reply(message: types.Message, prompt_text: str):
    """AI Agentdan javob olib, Telegram formatida chiroyli uzatish"""
    chat_id = str(message.chat.id)
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    res = await agent_instance.process_message(prompt_text, session_id=chat_id)
    reply_text = res.get("response", "Ma'lumot topilmadi.")

    # Telegram xabari hajmi cheklovi (4096 belgi)
    if len(reply_text) > 4000:
        for chunk in [reply_text[i:i+4000] for i in range(0, len(reply_text), 4000)]:
            try:
                await message.answer(chunk, parse_mode="Markdown")
            except Exception:
                await message.answer(chunk)
    else:
        try:
            await message.answer(reply_text, parse_mode="Markdown")
        except Exception:
            await message.answer(reply_text)

async def set_bot_commands_menu(bot: Bot):
    """Telegram ilovasida '/' tugmasi bosilganda chiqadigan rasmiy buyruqlar menyusi"""
    commands = [
        BotCommand(command="commands", description="Barcha buyruqlar va imkoniyatlar"),
        BotCommand(command="revenue", description="Oylik va umumiy tushumlar hisoboti"),
        BotCommand(command="debtors", description="To'lovni kechiktirgan qarzdorlar"),
        BotCommand(command="summary", description="Rahbariyat uchun Executive Summary"),
        BotCommand(command="fleet", description="Avtopark va inventar holati"),
        BotCommand(command="rentals", description="Faol arendadagi mashinalar"),
        BotCommand(command="remind", description="Qarzdorlarga eslatma jo'natish"),
        BotCommand(command="clear", description="Suhbat tarixini tozalash"),
        BotCommand(command="help", description="Yordam va qo'llanma")
    ]
    await bot.set_my_commands(commands)

async def main():
    if not BOT_TOKEN:
        print("⚠️ BOT_TOKEN ko'rsatilmagan. Botni ishga tushirish uchun .env faylida BOT_TOKEN ni belgilang.")
        return

    bot = Bot(token=BOT_TOKEN)
    print("🤖 Telegram Bot ishga tushmoqda...", flush=True)
    # Menyu buyruqlarini Telegramga ro'yxatga olish
    try:
        await set_bot_commands_menu(bot)
        print("✅ Telegram rasmiy buyruqlar menyusi (/commands, /revenue, ...) o'rnatildi!", flush=True)
    except Exception as e:
        logger.warning(f"Buyruqlar menyusini o'rnatishda ogohlantirish: {e}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
