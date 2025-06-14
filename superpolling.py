import asyncio
import logging
import os
import sqlite3
import subprocess

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

API_TOKEN = "7583219884:AAF_T3Pb3OIdX4S59TK0Caf4v8YhdBMnk4c"
ADMIN_ID = 8162058247
FILES_DIR = "uploaded_bots"

logging.basicConfig(level=logging.INFO)
os.makedirs(FILES_DIR, exist_ok=True)

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# --- DB connection ---
conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        approved INTEGER DEFAULT 0,
        banned INTEGER DEFAULT 0
    )
""")
conn.commit()

# --- DB helpers ---
def is_user_approved(user_id: int) -> bool:
    cursor.execute("SELECT approved FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row is not None and row[0] == 1

def is_user_banned(user_id: int) -> bool:
    cursor.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row is not None and row[0] == 1

def approve_user(user_id: int):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute("UPDATE users SET approved = 1, banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()

def ban_user(user_id: int):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute("UPDATE users SET banned = 1, approved = 0 WHERE user_id = ?", (user_id,))
    conn.commit()

# --- /start komandasi ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id

    if is_user_banned(user_id):
        return await message.answer("🚫 Siz botdan foydalanishdan banlangansiz.")

    if is_user_approved(user_id):
        return await message.answer("✅ Siz tasdiqlangansiz.\nIltimos, <b>.py</b> fayl yuboring.")

    user = message.from_user
    text = (
        f"🆕 <b>Yangi foydalanuvchi:</b>\n"
        f"👤 Ism: {user.full_name}\n"
        f"🔗 Username: @{user.username if user.username else 'yo‘q'}\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        f"❓ Tasdiqlaysizmi yoki ban qilasizmi?"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve:{user_id}"),
                InlineKeyboardButton(text="❌ Banlash", callback_data=f"ban:{user_id}")
            ]
        ]
    )
    await bot.send_message(chat_id=ADMIN_ID, text=text, reply_markup=keyboard)
    await message.answer("⏳ So‘rovingiz yuborildi. Admin tasdiqlamaguncha kuting.")

# --- Callback approve ---
@dp.callback_query(F.data.startswith("approve:"))
async def approve_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("⛔ Sizda ruxsat yo‘q.", show_alert=True)

    user_id = int(callback.data.split(":")[1])
    approve_user(user_id)

    await bot.send_message(chat_id=user_id, text="✅ Siz tasdiqlandingiz! Endi .py fayl yuboring.")
    await callback.message.edit_text("✅ Foydalanuvchi tasdiqlandi.")
    await callback.answer()

# --- Callback ban ---
@dp.callback_query(F.data.startswith("ban:"))
async def ban_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("⛔ Sizda ruxsat yo‘q.", show_alert=True)

    user_id = int(callback.data.split(":")[1])
    ban_user(user_id)

    await bot.send_message(chat_id=user_id, text="🚫 Siz botdan foydalanishdan banlangansiz.")
    await callback.message.edit_text("❌ Foydalanuvchi ban qilindi.")
    await callback.answer()

# --- Fayl qabul qilish ---
@dp.message(F.document)
async def handle_file(message: types.Message):
    user_id = message.from_user.id

    if is_user_banned(user_id):
        return await message.answer("🚫 Siz banlangansiz.")
    if not is_user_approved(user_id):
        return await message.answer("⏳ Siz hali tasdiqlanmadingiz.")

    document = message.document
    if not document.file_name.endswith(".py"):
        return await message.answer("⚠️ Faqat .py fayl yuboring.")

    user_dir = os.path.join(FILES_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)

    file_path = os.path.join(user_dir, document.file_name)
    log_path = file_path + ".log"
    pid_path = file_path + ".pid"

    await bot.download(document, destination=file_path)

    subprocess.Popen(
        f"nohup python3 {file_path} > {log_path} 2>&1 & echo $! > {pid_path}",
        shell=True
    )

    await message.answer(f"✅ Fayl saqlandi: <code>{document.file_name}</code>\n🚀 Fon rejimda ishga tushdi.")

# --- /mybots komandasi ---
@dp.message(Command("mybots"))
async def my_bots(message: types.Message):
    user_id = message.from_user.id

    if is_user_banned(user_id):
        return await message.answer("🚫 Siz banlangansiz.")
    if not is_user_approved(user_id):
        return await message.answer("⏳ Siz hali tasdiqlanmadingiz.")

    user_dir = os.path.join(FILES_DIR, str(user_id))
    if not os.path.exists(user_dir):
        return await message.answer("📂 Hech qanday fayl topilmadi.")

    files = [f for f in os.listdir(user_dir) if f.endswith(".py")]
    if not files:
        return await message.answer("📂 Hech qanday ishga tushirilgan fayl yo‘q.")

    for filename in files:
        file_path = os.path.join(user_dir, filename)
        log_path = file_path + ".log"
        pid_path = file_path + ".pid"

        buttons = [InlineKeyboardButton(text="📥 Log", callback_data=f"log:{filename}")]
        if os.path.exists(pid_path):
            buttons.append(InlineKeyboardButton(text="🔴 To‘xtatish", callback_data=f"stop:{filename}"))

        markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
        await message.answer(f"🤖 <code>{filename}</code>", reply_markup=markup)

# --- Log ko‘rish ---
@dp.callback_query(F.data.startswith("log:"))
async def log_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    filename = callback.data.split(":")[1]
    file_path = os.path.join(FILES_DIR, str(user_id), filename + ".log")

    if not os.path.exists(file_path):
        return await callback.answer("❌ Log fayli topilmadi.", show_alert=True)

    await callback.message.answer_document(FSInputFile(file_path), caption="📥 Log fayli")
    await callback.answer()

# --- To‘xtatish ---
@dp.callback_query(F.data.startswith("stop:"))
async def stop_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    filename = callback.data.split(":")[1]
    pid_path = os.path.join(FILES_DIR, str(user_id), filename + ".pid")

    if not os.path.exists(pid_path):
        return await callback.answer("❌ PID topilmadi.", show_alert=True)

    with open(pid_path, "r") as f:
        pid = f.read().strip()

    subprocess.call(["kill", pid])
    os.remove(pid_path)

    await callback.answer("🛑 Bot to‘xtatildi.")
    await callback.message.edit_text(f"🔴 <code>{filename}</code> to‘xtatildi.")

# --- Default ---
@dp.message()
async def fallback_message(message: types.Message):
    user_id = message.from_user.id

    if is_user_banned(user_id):
        return await message.answer("🚫 Siz banlangansiz.")
    if not is_user_approved(user_id):
        return await message.answer("⏳ Siz hali tasdiqlanmadingiz.")

    await message.answer("✅ Siz tasdiqlangansiz.\nIltimos, <b>.py</b> fayl yuboring.")

# --- Start ---
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))