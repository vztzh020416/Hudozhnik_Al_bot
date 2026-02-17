import telebot
import sqlite3
import requests
import urllib.parse
from telebot import types
from io import BytesIO

# ====== НАСТРОЙКИ ======
TOKEN = "8543701615:AAEsc7fZp9ZREZkSVkIUQ7z4LznudgGqCAY"
ADMIN_ID = 1005217438
DB_NAME = "users.db"

bot = telebot.TeleBot(TOKEN)

# ====== БАЗА ======
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        credits INTEGER DEFAULT 10,
        total_gen INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT credits,total_gen FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    conn.close()
    return row

def add_user(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id,credits) VALUES(?,10)", (uid,))
    conn.commit()
    conn.close()

def add_credits(uid, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET credits=credits+? WHERE user_id=?", (amount, uid))
    conn.commit()
    conn.close()

def add_gen(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET total_gen=total_gen+1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()

# ====== МЕНЮ ======
def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎨 Рисовать", "👤 Профиль")
    kb.add("⭐ Купить", "📊 Статистика")
    return kb

# ====== СЕРВИСЫ ГЕНЕРАЦИИ ======
SERVICES = [
    "https://image.pollinations.ai/prompt/{p}?width=1024&height=1024",
    "https://image.pollinations.ai/prompt/{p}?width=768&height=768",
    "https://image.pollinations.ai/prompt/{p}",
    "https://image.pollinations.ai/prompt/{p}?nologo=true",
    "https://image.pollinations.ai/prompt/{p}?width=512&height=512"
]

# ====== СТАРТ ======
@bot.message_handler(commands=['start'])
def start(msg):
    add_user(msg.from_user.id)
    bot.send_message(msg.chat.id,
        "🎨 Бот генерации изображений\nУ тебя 10 бесплатных попыток",
        reply_markup=menu()
    )

# ====== ПРОФИЛЬ ======
@bot.message_handler(func=lambda m: m.text=="👤 Профиль")
def profile(msg):
    u = get_user(msg.from_user.id)
    if not u:
        return
    bot.send_message(
        msg.chat.id,
        f"👤 Профиль\n\nКредиты: {u[0]}\nГенераций: {u[1]}",
        reply_markup=menu()
    )

# ====== АДМИН СТАТ ======
@bot.message_handler(func=lambda m: m.text=="📊 Статистика")
def stats(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    gens = c.execute("SELECT SUM(total_gen) FROM users").fetchone()[0]
    conn.close()
    bot.send_message(
        msg.chat.id,
        f"📊 Статистика\nПользователей: {users}\nГенераций: {gens or 0}",
        reply_markup=menu()
    )

# ====== КУПИТЬ (БЕСПЛАТНО) ======
@bot.message_handler(func=lambda m: m.text=="⭐ Купить")
def buy(msg):
    add_credits(msg.from_user.id, 10)
    bot.send_message(
        msg.chat.id,
        "🎁 Тебе добавлено 10 попыток бесплатно",
        reply_markup=menu()
    )

# ====== РИСОВАТЬ ======
@bot.message_handler(func=lambda m: m.text=="🎨 Рисовать")
def draw(msg):
    u = get_user(msg.from_user.id)
    if not u or u[0] <= 0:
        bot.send_message(msg.chat.id,"❌ Нет попыток", reply_markup=menu())
        return
    m = bot.send_message(msg.chat.id,"Напиши запрос")
    bot.register_next_step_handler(m, gen)

def gen(msg):
    uid = msg.from_user.id
    prompt = msg.text
    safe = urllib.parse.quote(prompt)

    bot.send_message(msg.chat.id,"⏳ Генерация...")

    for url in SERVICES:
        try:
            r = requests.get(url.format(p=safe), timeout=30)
            if r.status_code == 200 and r.content:
                bot.send_photo(
                    msg.chat.id,
                    BytesIO(r.content),
                    caption=prompt,
                    reply_markup=menu()
                )
                add_credits(uid, -1)
                add_gen(uid)
                return
            else:
                bot.send_message(msg.chat.id,f"⚠️ Ошибка сервиса: {r.status_code}")
        except Exception as e:
            bot.send_message(msg.chat.id,f"⚠️ {e}")

    bot.send_message(msg.chat.id,"❌ Все сервисы недоступны", reply_markup=menu())

# ====== ЗАПУСК ======
print("BOT START")
bot.infinity_polling()
