import asyncio
import logging
import random
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

TOKEN = "8543701615:AAEsc7fZp9ZREZkSVkIUQ7z4LznudgGqCAY"

logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN)
dp = Dispatcher()

# ---------- ДАННЫЕ ----------
users = {}
ADMIN_ID = None

# ---------- МЕНЮ ----------
def menu(uid):
    buttons = [
        [KeyboardButton(text="🎨 Рисовать")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="⭐ Купить")]
    ]
    if uid == ADMIN_ID:
        buttons.append([KeyboardButton(text="📊 Статистика")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

# ---------- БЕСПЛАТНЫЕ СЕРВИСЫ ----------
SERVICES = [
    "https://image.pollinations.ai/prompt/{prompt}",
    "https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024",
    "https://image.pollinations.ai/prompt/{prompt}?nologo=true",
    "https://image.pollinations.ai/prompt/{prompt}?model=flux",
    "https://image.pollinations.ai/prompt/{prompt}?model=turbo",
    "https://image.pollinations.ai/prompt/{prompt}?enhance=true",
    "https://image.pollinations.ai/prompt/{prompt}?style=anime",
    "https://image.pollinations.ai/prompt/{prompt}?style=realistic",
    "https://image.pollinations.ai/prompt/{prompt}?seed=1",
    "https://image.pollinations.ai/prompt/{prompt}?seed=2",
]

# ---------- ПОЛЬЗОВАТЕЛЬ ----------
def add_user(uid):
    if uid not in users:
        users[uid] = {"credits": 5, "gen": 0}

# ---------- СТАРТ ----------
@dp.message(CommandStart())
async def start(msg: Message):
    global ADMIN_ID
    uid = msg.from_user.id
    add_user(uid)

    if ADMIN_ID is None:
        ADMIN_ID = uid

    await msg.answer(
        "🎨 Бот генерации изображений\n"
        f"У тебя {users[uid]['credits']} попыток",
        reply_markup=menu(uid)
    )

# ---------- ПРОФИЛЬ ----------
@dp.message(F.text == "👤 Профиль")
async def profile(msg: Message):
    uid = msg.from_user.id
    add_user(uid)
    u = users[uid]

    await msg.answer(
        f"👤 Профиль\n"
        f"Кредиты: {u['credits']}\n"
        f"Генераций: {u['gen']}",
        reply_markup=menu(uid)
    )

# ---------- ПОКУПКА ----------
@dp.message(F.text == "⭐ Купить")
async def buy(msg: Message):
    uid = msg.from_user.id
    add_user(uid)

    users[uid]["credits"] += 10

    await msg.answer(
        "⭐ Начислено +10 кредитов",
        reply_markup=menu(uid)
    )

# ---------- СТАТИСТИКА ----------
@dp.message(F.text == "📊 Статистика")
async def stat(msg: Message):
    uid = msg.from_user.id
    if uid != ADMIN_ID:
        return

    total_users = len(users)
    total_gen = sum(u["gen"] for u in users.values())

    await msg.answer(
        f"📊 Статистика\n"
        f"Пользователей: {total_users}\n"
        f"Генераций: {total_gen}",
        reply_markup=menu(uid)
    )

# ---------- РИСОВАТЬ ----------
@dp.message(F.text == "🎨 Рисовать")
async def draw(msg: Message):
    await msg.answer(
        "Напиши запрос (например: cat, car, house)",
        reply_markup=menu(msg.from_user.id)
    )

# ---------- ГЕНЕРАЦИЯ ----------
@dp.message()
async def generate(msg: Message):
    uid = msg.from_user.id
    add_user(uid)

    if msg.text.startswith("/"):
        return

    if msg.text in ["🎨 Рисовать", "👤 Профиль", "⭐ Купить", "📊 Статистика"]:
        return

    if users[uid]["credits"] <= 0:
        await msg.answer("❌ Нет кредитов", reply_markup=menu(uid))
        return

    prompt = msg.text.replace(" ", "%20")

    errors = []

    async with aiohttp.ClientSession() as session:
        for url in SERVICES:
            link = url.format(prompt=prompt)

            try:
                async with session.get(link, timeout=30) as r:
                    if r.status == 200:
                        img = await r.read()
                        if len(img) > 1000:
                            users[uid]["credits"] -= 1
                            users[uid]["gen"] += 1
                            await msg.answer_photo(
                                img,
                                caption="✅ Готово",
                                reply_markup=menu(uid)
                            )
                            return
                        else:
                            errors.append("пусто")
                    else:
                        errors.append(str(r.status))
            except Exception as e:
                errors.append(str(e))

    await msg.answer(
        "❌ Все сервисы не ответили\n"
        + "\n".join(errors[:5]),
        reply_markup=menu(uid)
    )

# ---------- ЗАПУСК ----------
async def main():
    await dp.start_polling(bot)

asyncio.run(main())
