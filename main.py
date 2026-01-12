import asyncio
import logging
import os
import sys
import re

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ───────────────
# Настройки
# ───────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
MASTER_ID = os.getenv("MASTER_ID")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN не знайдено")
    sys.exit(1)

if not MASTER_ID:
    print("❌ MASTER_ID не знайдено")
    sys.exit(1)

MASTER_ID = int(MASTER_ID)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ───────────────
# Тимчасове сховище замовлень
# ───────────────
orders = {}

# ───────────────
# Функція для безпечного MarkdownV2
# ───────────────
def escape_md(text: str) -> str:
    """
    Екранируем спецсимволы для MarkdownV2
    """
    if not text:
        return ""
    return re.sub(r'([_\*\[\]\(\)~`>#+\-=|{}.!])', r'\\\1', text)

# ───────────────
# Кнопки головного меню
# ───────────────
def main_menu_buttons():
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Зробити замовлення", callback_data="order")
    kb.button(text="📜 Наше Меню", callback_data="menu")
    kb.button(text="🏢 Як нас знайти", callback_data="contacts")
    kb.button(text="✍️ Залишити відгук", callback_data="feedback")
    kb.adjust(1)
    return kb.as_markup()

# ───────────────
# Кнопки послуг
# ───────────────
def services_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="Класичний манікюр", callback_data="service_classic")
    kb.button(text="Манікюр + гель-лак", callback_data="service_gel")
    kb.button(text="Нарощування", callback_data="service_extension")
    kb.adjust(1)
    return kb.as_markup()

# ───────────────
# Кнопки часу
# ───────────────
def time_menu():
    kb = InlineKeyboardBuilder()
    for t in ["10:00", "12:00", "14:00", "16:00", "18:00"]:
        kb.button(text=t, callback_data=f"time_{t}")
    kb.adjust(3)
    return kb.as_markup()

# ───────────────
# /start
# ───────────────
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Вітаю 💖\nОберіть дію 👇",
        reply_markup=main_menu_buttons()
    )

# ───────────────
# Обработка главных кнопок
# ───────────────
@dp.callback_query(F.data == "order")
async def order_start(call: CallbackQuery):
    orders[call.from_user.id] = {}
    await call.message.edit_text(
        "💅 Оберіть послугу для замовлення",
        reply_markup=services_menu()
    )

@dp.callback_query(F.data == "menu")
async def show_menu(call: CallbackQuery):
    await call.message.edit_text(
        "📜 Види манікюру:\n"
        "1. Класичний манікюр\n"
        "2. Манікюр + гель-лак\n"
        "3. Нарощування",
        reply_markup=main_menu_buttons()
    )

@dp.callback_query(F.data == "contacts")
async def show_contacts(call: CallbackQuery):
    await call.message.edit_text(
        "🏢 Соц. мережі:\n"
        "Instagram: @your_instagram\n"
        "Телефон: +380 XX XXX XX XX",
        reply_markup=main_menu_buttons()
    )

@dp.callback_query(F.data == "feedback")
async def feedback(call: CallbackQuery):
    await call.message.edit_text(
        "✍️ Залиште свій відгук у чаті, будь ласка.",
        reply_markup=main_menu_buttons()
    )

# ───────────────
# Обработка выбора услуги
# ───────────────
@dp.callback_query(F.data.startswith("service_"))
async def choose_service(call: CallbackQuery):
    service_map = {
        "service_classic": "Класичний манікюр",
        "service_gel": "Манікюр + гель-лак",
        "service_extension": "Нарощування",
    }

    orders[call.from_user.id]["service"] = service_map[call.data]

    await call.message.edit_text(
        "Напишіть бажану дату 📅\nНаприклад: 15.01"
    )

# ───────────────
# Получаем дату
# ───────────────
@dp.message()
async def get_date(message: Message):
    user_id = message.from_user.id

    if user_id not in orders or "service" not in orders[user_id]:
        return

    orders[user_id]["date"] = message.text

    await message.answer(
        "Оберіть зручний час ⏰",
        reply_markup=time_menu()
    )

# ───────────────
# Выбор времени и уведомление мастеру
# ───────────────
@dp.callback_query(F.data.startswith("time_"))
async def choose_time(call: CallbackQuery):
    time = call.data.replace("time_", "")
    user_id = call.from_user.id

    orders[user_id]["time"] = time
    order = orders[user_id]

    # Уведомление клиенту
    await call.message.edit_text(
        "✅ **Запис підтверджено!**\n\n"
        f"💅 Послуга: {escape_md(order['service'])}\n"
        f"📅 Дата: {escape_md(order['date'])}\n"
        f"⏰ Час: {escape_md(order['time'])}\n\n"
        "Ми зв’яжемось з вами найближчим часом 💖",
        parse_mode="Markdown"
    )

    # Уведомление мастеру
    username = escape_md(call.from_user.username or "без_username")
    service = escape_md(order['service'])
    date = escape_md(order['date'])
    time_text = escape_md(order['time'])

    await bot.send_message(
        chat_id=MASTER_ID,
        text=(
            f"📩 **Нове замовлення\\!**\n\n"
            f"👤 Клієнт: @{username}\n"
            f"💅 Послуга: {service}\n"
            f"📅 Дата: {date}\n"
            f"⏰ Час: {time_text}"
        ),
        parse_mode="MarkdownV2"
    )

# ───────────────
# Запуск
# ───────────────
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

