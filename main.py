import asyncio
import logging
import os
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

# ───────────── ХРАНЕНИЕ ДАННЫХ ─────────────
user_states = {}
user_orders = {}

# ───────────── ГЛАВНЫЕ КНОПКИ (КАК НА ФОТО) ─────────────
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

# ───────────── /start ─────────────
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
    service = call.data.split(":", 1)[1]
    user_states[call.from_user.id]["service"] = service
    await call.message.answer("📅 Напишіть дату (наприклад 15.01):")

@dp.message(F.text.regexp(r"\d{2}\.\d{2}"))
async def choose_date(message: Message):
    if message.from_user.id not in user_states:
        return
    user_states[message.from_user.id]["date"] = message.text

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=f"time:{t}")]
            for t in TIMES
        ]
    )
    await message.answer("⏰ Оберіть час:", reply_markup=kb)

@dp.callback_query(F.data.startswith("time:"))
async def finish_order(call: CallbackQuery):
    time = call.data.split(":", 1)[1]
    uid = call.from_user.id

    order = user_states.pop(uid)
    order["time"] = time

    user_orders.setdefault(uid, []).append(order)

    await call.message.answer(
        "✅ Запис успішно створено!\nМи з вами звʼяжемось 💖",
        reply_markup=main_keyboard()
    )

    await bot.send_message(
        MASTER_ID,
        f"📩 НОВИЙ ЗАПИС\n\n"
        f"👤 @{call.from_user.username or call.from_user.first_name}\n"
        f"💅 {order['service']}\n"
        f"📅 {order['date']}\n"
        f"⏰ {order['time']}"
    )

# ───────────── СКАСУВАННЯ ЗАПИСУ ─────────────
@dp.message(F.text == "❌ Скасувати запис")
async def cancel_order(message: Message):
    orders = user_orders.get(message.from_user.id)
    if not orders:
        await message.answer("❗ У вас немає активних записів.", reply_markup=main_keyboard())
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{o['service']} | {o['date']} {o['time']}",
                    callback_data=f"cancel:{i}"
                )
            ]
            for i, o in enumerate(orders)
        ]
    )
    await message.answer("Оберіть запис для скасування:", reply_markup=kb)

@dp.callback_query(F.data.startswith("cancel:"))
async def confirm_cancel(call: CallbackQuery):
    idx = int(call.data.split(":")[1])
    order = user_orders[call.from_user.id].pop(idx)

    await call.message.answer(
        "❌ Запис скасовано.",
        reply_markup=main_keyboard()
    )

    await bot.send_message(
        MASTER_ID,
        f"❌ ЗАПИС СКАСОВАНО\n\n"
        f"👤 @{call.from_user.username or call.from_user.first_name}\n"
        f"💅 {order['service']}\n"
        f"📅 {order['date']} {order['time']}"
    )

# ───────────── ИНФО КНОПКИ ─────────────
@dp.message(F.text == "📜 Наші Послуги")
async def show_services(message: Message):
    await message.answer(
        "💅 Наші послуги:\n\n" + "\n".join(f"• {s}" for s in SERVICES),
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "📱 Соц. Мережі")
async def socials(message: Message):
    await message.answer(
        "📱 Ми в соцмережах:\nInstagram: @your_instagram\nTelegram: @your_channel",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "✍️ Залишити відгук")
async def feedback(message: Message):
    await message.answer(
        "💖 Напишіть ваш відгук просто в чаті!",
        reply_markup=main_keyboard()
    )

# ───────────── ЗАПУСК ─────────────
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
