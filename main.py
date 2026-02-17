import telebot
import sqlite3
import requests
import urllib.parse
from telebot import types
from io import BytesIO

TOKEN = "8543701615:AAEsc7fZp9ZREZkSVkIUQ7z4LznudgGqCAY"
ADMIN_ID = 1005217438
DB_NAME = "users.db"

bot = telebot.TeleBot(TOKEN)

# ---------- БД ----------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        credits INTEGER DEFAULT 57,
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
    c.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,))
    conn.commit()
    conn.close()

def change_credits(uid, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount,uid))
    conn.commit()
    conn.close()

# ---------- МЕНЮ ----------
def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎨 Рисовать")
    kb.add("👤 Профиль","⭐ Купить")
    return kb

# ---------- START ----------
@bot.message_handler(commands=['start'])
def start(m):
    add_user(m.from_user.id)
    bot.send_message(
        m.chat.id,
        "🎨 Бот генерации\nУ тебя 57 попыток",
        reply_markup=menu()
    )

# ---------- ПРОФИЛЬ ----------
@bot.message_handler(func=lambda m: m.text=="👤 Профиль")
def profile(m):
    u = get_user(m.from_user.id)
    bot.send_message(
        m.chat.id,
        f"Кредиты: {u[0]}\nГенераций: {u[1]}",
        reply_markup=menu()
    )

# ---------- ПОКУПКА ----------
@bot.message_handler(func=lambda m: m.text=="⭐ Купить")
def buy(m):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("10 ⭐ = 10", callback_data="buy10"))
    kb.add(types.InlineKeyboardButton("50 ⭐ = 60", callback_data="buy50"))
    bot.send_message(m.chat.id,"Покупка:",reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy"))
def buy_cb(c):
    if c.data=="buy10":
        change_credits(c.from_user.id,10)
        bot.send_message(c.message.chat.id,"Начислено 10")
    if c.data=="buy50":
        change_credits(c.from_user.id,60)
        bot.send_message(c.message.chat.id,"Начислено 60")

# ---------- ГЕНЕРАЦИЯ ----------
@bot.message_handler(func=lambda m: m.text=="🎨 Рисовать")
def draw(m):
    u = get_user(m.from_user.id)
    if u[0]<=0:
        bot.send_message(m.chat.id,"Нет попыток",reply_markup=menu())
        return

    msg = bot.send_message(m.chat.id,"Напиши запрос")
    bot.register_next_step_handler(msg,gen)

def gen(m):
    uid = m.from_user.id
    prompt = m.text

    wait = bot.send_message(m.chat.id,"⏳ Генерация...")

    img = try_generate(prompt, m.chat.id)

    if img:
        bot.send_photo(
            m.chat.id,
            img,
            caption=prompt,
            reply_markup=menu()
        )
        change_credits(uid,-1)
    else:
        bot.send_message(
            m.chat.id,
            "❌ Все сервисы умерли",
            reply_markup=menu()
        )

    bot.delete_message(m.chat.id,wait.message_id)

# ---------- MULTI API ----------
def try_generate(prompt, chat_id):

    safe = urllib.parse.quote(prompt)

    apis = [
        f"https://image.pollinations.ai/prompt/{safe}",
        f"https://image.pollinations.ai/prompt/{safe}?model=flux",
        f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024",
        f"https://stablehorde.net/generate/{safe}"
    ]

    for url in apis:
        try:
            r = requests.get(url,timeout=40)
            if r.status_code==200:
                return BytesIO(r.content)
            else:
                bot.send_message(chat_id,f"⚠️ API ошибка {r.status_code}")
        except Exception as e:
            bot.send_message(chat_id,f"⚠️ API сбой {e}")

    return None

# ---------- RUN ----------
print("BOT OK")
bot.infinity_polling()
