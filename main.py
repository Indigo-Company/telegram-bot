import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import Command

# ───────────── НАСТРОЙКИ ─────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
MASTER_ID = int(os.getenv("MASTER_ID"))
MASTER_PHONE = "+380939547603"

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ───────────── БАЗА ДАННЫХ ─────────────
db = sqlite3.connect("orders.db")
sql = db.cursor()

sql.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    phone TEXT,
    service TEXT,
    date TEXT,
    time TEXT
)
""")
db.commit()

# ───────────── ПОСЛУГИ ─────────────
SERVICES = [
    "Класичний манікюр",
    "Манікюр + гель-лак",
    "Нарощування",
    "Педикюр"
]

TIMES = ["10:00", "12:00", "14:00", "16:00", "18:00"]

# ───────────── ХРАНЕНИЕ СОСТОЯНИЙ ─────────────
user_states = {}

# ───────────── КЛАВИАТУРЫ ─────────────
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Записатися")],
            [KeyboardButton(text="📜 Наші Послуги")],
            [KeyboardButton(text="📱 Соц. Мережі")],
            [KeyboardButton(text="✍️ Залишити відгук")],
            [KeyboardButton(text="❌ Скасувати запис")]
        ],
        resize_keyboard=True
    )

def phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📲 Надіслати номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# ───────────── START ─────────────
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "💅 Вітаємо у студії манікюру!\nОберіть дію 👇",
        reply_markup=main_keyboard()
    )

# ───────────── ЗАПИС ─────────────
@dp.message(F.text == "🛒 Записатися")
async def start_order(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=s, callback_data=f"service:{s}")]
            for s in SERVICES
        ]
    )
    user_states[message.from_user.id] = {}
    await message.answer("💅 Оберіть послугу:", reply_markup=kb)

@dp.callback_query(F.data.startswith("service:"))
async def choose_service(call: CallbackQuery):
    user_states[call.from_user.id]["service"] = call.data.split(":", 1)[1]
    await call.message.answer("📅 Введіть дату (ДД.ММ):")

@dp.message(F.text.regexp(r"\d{2}\.\d{2}"))
async def choose_date(message: Message):
    uid = message.from_user.id
    if uid not in user_states:
        return

    user_states[uid]["date"] = message.text

    busy = sql.execute(
        "SELECT time FROM orders WHERE date=?",
        (message.text,)
    ).fetchall()
    busy_times = {b[0] for b in busy}

    free_times = [t for t in TIMES if t not in busy_times]

    if not free_times:
        await message.answer("❌ На цю дату немає вільних годин.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=f"time:{t}")]
            for t in free_times
        ]
    )
    await message.answer("⏰ Оберіть час:", reply_markup=kb)

@dp.callback_query(F.data.startswith("time:"))
async def choose_time(call: CallbackQuery):
    uid = call.from_user.id
    user_states[uid]["time"] = call.data.split(":", 1)[1]

    await call.message.answer(
        "📞 Для підтвердження запису поділіться номером телефону",
        reply_markup=phone_keyboard()
    )

# ───────────── ПОЛУЧЕНИЕ ТЕЛЕФОНА ─────────────
@dp.message(F.contact)
async def get_phone(message: Message):
    uid = message.from_user.id
    if uid not in user_states:
        return

    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone

    data = user_states.pop(uid)

    sql.execute(
        "INSERT INTO orders (user_id, name, phone, service, date, time) VALUES (?, ?, ?, ?, ?, ?)",
        (
            uid,
            message.from_user.full_name,
            phone,
            data["service"],
            data["date"],
            data["time"]
        )
    )
    db.commit()

    await message.answer(
        "✅ Запис підтверджено!\nМи з вами звʼяжемось 💖",
        reply_markup=main_keyboard()
    )

    await bot.send_message(
        MASTER_ID,
        f"🔔 НОВИЙ ЗАПИС\n\n"
        f"👤 {message.from_user.full_name}\n"
        f"📞 {phone}\n"
        f"💅 {data['service']}\n"
        f"📅 {data['date']}\n"
        f"⏰ {data['time']}",
        disable_notification=False
    )

# ───────────── СКАСУВАННЯ ─────────────
@dp.message(F.text == "❌ Скасувати запис")
async def cancel_order(message: Message):
    rows = sql.execute(
        "SELECT id, service, date, time FROM orders WHERE user_id=?",
        (message.from_user.id,)
    ).fetchall()

    if not rows:
        await message.answer("❗ У вас немає активних записів.", reply_markup=main_keyboard())
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{r[1]} | {r[2]} {r[3]}",
                callback_data=f"cancel:{r[0]}"
            )]
            for r in rows
        ]
    )
    await message.answer("Оберіть запис для скасування:", reply_markup=kb)

@dp.callback_query(F.data.startswith("cancel:"))
async def confirm_cancel(call: CallbackQuery):
    order_id = call.data.split(":")[1]

    order = sql.execute(
        "SELECT name, phone, service, date, time FROM orders WHERE id=?",
        (order_id,)
    ).fetchone()

    sql.execute("DELETE FROM orders WHERE id=?", (order_id,))
    db.commit()

    await call.message.answer("❌ Запис скасовано.", reply_markup=main_keyboard())

    if order:
        await bot.send_message(
            MASTER_ID,
            f"🔕 ЗАПИС СКАСОВАНО\n\n"
            f"👤 {order[0]}\n"
            f"📞 {order[1]}\n"
            f"💅 {order[2]}\n"
            f"📅 {order[3]} {order[4]}",
            disable_notification=False
        )

# ───────────── АДМИН-ПАНЕЛЬ ─────────────
@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != MASTER_ID:
        return
    await message.answer(
        "/records — всі записи\n"
        "/delete ID — видалити запис"
    )

@dp.message(Command("records"))
async def records(message: Message):
    if message.from_user.id != MASTER_ID:
        return

    rows = sql.execute("SELECT id, service, date, time FROM orders").fetchall()
    if not rows:
        await message.answer("Записів немає.")
        return

    text = "\n".join([f"{r[0]} | {r[1]} | {r[2]} {r[3]}" for r in rows])
    await message.answer(text)

@dp.message(Command("delete"))
async def admin_delete(message: Message):
    if message.from_user.id != MASTER_ID:
        return
    try:
        order_id = message.text.split()[1]
        sql.execute("DELETE FROM orders WHERE id=?", (order_id,))
        db.commit()
        await message.answer("✅ Запис видалено.")
    except:
        await message.answer("❌ Помилка. Використання: /delete ID")

# ───────────── RUN ─────────────
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
