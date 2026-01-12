import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import *
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")
MASTER_ID = int(os.getenv("MASTER_ID"))
MASTER_PHONE = "+380939547603"

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ───────────── DATABASE ─────────────
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

# ───────────── DATA ─────────────
SERVICES = [
    "Класичний манікюр",
    "Манікюр + гель-лак",
    "Нарощування",
    "Педикюр"
]

TIMES = ["10:00", "12:00", "14:00", "16:00", "18:00"]
user_states = {}

# ───────────── KEYBOARDS ─────────────
def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Записатися")],
            [KeyboardButton(text="📜 Наші Послуги")],
            [KeyboardButton(text="📱 Соц. Мережі")],
            [KeyboardButton(text="❌ Скасувати запис")]
        ],
        resize_keyboard=True
    )

def phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📲 Надіслати номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# ───────────── START ─────────────
@dp.message(Command("start"))
async def start(m: Message):
    await m.answer("💅 Вітаємо! Оберіть дію 👇", reply_markup=main_kb())

# ───────────── ORDER ─────────────
@dp.message(F.text == "🛒 Записатися")
async def order(m: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=s, callback_data=f"s:{s}")]] for s in SERVICES
    )
    user_states[m.from_user.id] = {}
    await m.answer("Оберіть послугу:", reply_markup=kb)

@dp.callback_query(F.data.startswith("s:"))
async def service(c: CallbackQuery):
    user_states[c.from_user.id]["service"] = c.data[2:]
    await c.message.answer("Введіть дату (ДД.ММ):")

@dp.message(F.text.regexp(r"\d{2}\.\d{2}"))
async def date(m: Message):
    uid = m.from_user.id
    if uid not in user_states:
        return

    user_states[uid]["date"] = m.text
    busy = sql.execute(
        "SELECT time FROM orders WHERE date=?", (m.text,)
    ).fetchall()
    busy_times = {b[0] for b in busy}

    free = [t for t in TIMES if t not in busy_times]

    if not free:
        await m.answer("❌ На цю дату немає вільного часу.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=f"t:{t}")]] for t in free
    )
    await m.answer("Оберіть час:", reply_markup=kb)

@dp.callback_query(F.data.startswith("t:"))
async def time(c: CallbackQuery):
    user_states[c.from_user.id]["time"] = c.data[2:]
    await c.message.answer("Надішліть номер телефону:", reply_markup=phone_kb())

@dp.message(F.contact)
async def phone(m: Message):
    uid = m.from_user.id
    if uid not in user_states:
        return

    phone = m.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone

    d = user_states.pop(uid)

    sql.execute(
        "INSERT INTO orders (user_id,name,phone,service,date,time) VALUES (?,?,?,?,?,?)",
        (uid, m.from_user.full_name, phone, d["service"], d["date"], d["time"])
    )
    db.commit()

    await m.answer("✅ Запис підтверджено!", reply_markup=main_kb())

    await bot.send_message(
        MASTER_ID,
        f"🔔 НОВИЙ ЗАПИС\n\n"
        f"👤 {m.from_user.full_name}\n"
        f"📞 {phone}\n"
        f"💅 {d['service']}\n"
        f"📅 {d['date']} {d['time']}",
        disable_notification=False
    )

# ───────────── CANCEL ─────────────
@dp.message(F.text == "❌ Скасувати запис")
async def cancel(m: Message):
    rows = sql.execute(
        "SELECT id, service, date, time FROM orders WHERE user_id=?",
        (m.from_user.id,)
    ).fetchall()

    if not rows:
        await m.answer("❗ Записів немає")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{r[1]} | {r[2]} {r[3]}", callback_data=f"del:{r[0]}")]
            for r in rows
        ]
    )
    await m.answer("Оберіть запис:", reply_markup=kb)

@dp.callback_query(F.data.startswith("del:"))
async def delete(c: CallbackQuery):
    oid = c.data[4:]
    sql.execute("DELETE FROM orders WHERE id=?", (oid,))
    db.commit()

    await c.message.answer("❌ Запис скасовано", reply_markup=main_kb())
    await bot.send_message(MASTER_ID, "🔕 Запис скасовано", disable_notification=False)

# ───────────── ADMIN ─────────────
@dp.message(Command("admin"))
async def admin(m: Message):
    if m.from_user.id != MASTER_ID:
        return
    await m.answer("/records — всі записи\n/delete ID — видалити")

@dp.message(Command("records"))
async def records(m: Message):
    if m.from_user.id != MASTER_ID:
        return
    rows = sql.execute("SELECT * FROM orders").fetchall()
    text = "\n".join([f"{r[0]} | {r[4]} | {r[5]} {r[6]}" for r in rows])
    await m.answer(text or "Порожньо")

@dp.message(Command("delete"))
async def admin_delete(m: Message):
    if m.from_user.id != MASTER_ID:
        return
    try:
        oid = m.text.split()[1]
        sql.execute("DELETE FROM orders WHERE id=?", (oid,))
        db.commit()
        await m.answer("✅ Видалено")
    except:
        await m.answer("❌ Помилка")

# ───────────── RUN ─────────────
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
