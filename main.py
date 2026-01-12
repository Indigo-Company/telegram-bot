import asyncio
import logging
import os

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


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

# ───────────── ПОСЛУГИ (МЕНЯЕШЬ ТУТ) ─────────────
SERVICES = [
    "Класичний манікюр",
    "Манікюр + гель-лак",
    "Нарощування",
    "Педикюр"
]

TIMES = ["10:00", "12:00", "14:00", "16:00", "18:00"]

# ───────────── ХРАНЕНИЕ ─────────────
user_states = {}
user_orders = {}

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
        keyboard=[
            [KeyboardButton(text="📲 Надіслати номер", request_contact=True)]
        ],
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
    await call.message.answer("📅 Введіть дату (наприклад 15.01):")

@dp.message(F.text.regexp(r"\d{2}\.\d{2}"))
async def choose_date(message: Message):
    uid = message.from_user.id
    if uid not in user_states:
        return

    user_states[uid]["date"] = message.text

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=f"time:{t}")]
            for t in TIMES
        ]
    )
    await message.answer("⏰ Оберіть час:", reply_markup=kb)

@dp.callback_query(F.data.startswith("time:"))
async def choose_time(call: CallbackQuery):
    uid = call.from_user.id
    user_states[uid]["time"] = call.data.split(":", 1)[1]

    await call.message.answer(
        "📞 Для підтвердження запису, будь ласка, поділіться номером телефону",
        reply_markup=phone_keyboard()
    )

# ───────────── ПОЛУЧЕНИЕ ТЕЛЕФОНА ─────────────
@dp.message(F.contact)
async def get_phone(message: Message):
    uid = message.from_user.id
    if uid not in user_states:
        await message.answer("❗ Немає активного запису.")
        return

    order = user_states.pop(uid)

    phone = message.contact.phone_number
    full_name = message.from_user.full_name
    username = message.from_user.username

    order["phone"] = phone
    order["name"] = full_name

    # ⬇️ UPSERT (если клиент уже есть — обновится)
    supabase.table("clients").upsert({
        "user_id": uid,
        "username": username,
        "full_name": full_name,
        "phone": phone
    }).execute()

    user_orders.setdefault(uid, []).append(order)

    await message.answer(
        "✅ Запис підтверджено!\nМи звʼяжемось з вами найближчим часом 💖",
        reply_markup=main_keyboard()
    )

    await bot.send_message(
        MASTER_ID,
        f"📩 НОВИЙ ЗАПИС\n\n"
        f"👤 {full_name}\n"
        f"🔗 @{username if username else 'немає'}\n"
        f"📞 {phone}\n"
        f"💅 {order['service']}\n"
        f"📅 {order['date']}\n"
        f"⏰ {order['time']}"
    )


# ───────────── СКАСУВАННЯ ─────────────
@dp.message(F.text == "❌ Скасувати запис")
async def cancel_order(message: Message):
    orders = user_orders.get(message.from_user.id)
    if not orders:
        await message.answer("❗ У вас немає активних записів.", reply_markup=main_keyboard())
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{o['service']} | {o['date']} {o['time']}",
                callback_data=f"cancel:{i}"
            )]
            for i, o in enumerate(orders)
        ]
    )
    await message.answer("Оберіть запис для скасування:", reply_markup=kb)

@dp.callback_query(F.data.startswith("cancel:"))
async def confirm_cancel(call: CallbackQuery):
    uid = call.from_user.id
    idx = int(call.data.split(":")[1])
    order = user_orders[uid].pop(idx)

    await call.message.answer("❌ Запис скасовано.", reply_markup=main_keyboard())

    await bot.send_message(
        MASTER_ID,
        f"❌ ЗАПИС СКАСОВАНО\n\n"
        f"👤 {order['name']}\n"
        f"📞 {order['phone']}\n"
        f"💅 {order['service']}\n"
        f"📅 {order['date']} {order['time']}"
    )

# ───────────── ИНФО ─────────────
@dp.message(F.text == "📜 Наші Послуги")
async def show_services(message: Message):
    await message.answer(
        "💅 Наші послуги:\n\n" + "\n".join(f"• {s}" for s in SERVICES),
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "📱 Соц. Мережі")
async def socials(message: Message):
    await message.answer(
        f"📱 Наші контакти:\n\n"
        f"📞 {MASTER_PHONE}\n"
        f"Instagram: @your_instagram",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "✍️ Залишити відгук")
async def feedback(message: Message):
    await message.answer(
        "💖 Напишіть ваш відгук просто в чаті!",
        reply_markup=main_keyboard()
    )

# ───────────── RUN ─────────────
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

