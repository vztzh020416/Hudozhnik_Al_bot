import telebot
from telebot import types
import requests
import sqlite3
import time
import random

BOT_TOKEN = "8543701615:AAEsc7fZp9ZREZkSVkIUQ7z4LznudgGqCAY"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

DB = "users.db"

# ---------- БАЗА ----------
def db():
    return sqlite3.connect(DB, check_same_thread=False)

conn = db()
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY,
credits INTEGER DEFAULT 5
)
""")
conn.commit()

def get_credits(uid):
    cur.execute("SELECT credits FROM users WHERE id=?", (uid,))
    r = cur.fetchone()
    if r:
        return r[0]
    cur.execute("INSERT INTO users(id,credits) VALUES(?,5)", (uid,))
    conn.commit()
    return 5

def add_credit(uid, n):
    cur.execute("UPDATE users SET credits=credits+? WHERE id=?", (n, uid))
    conn.commit()

def sub_credit(uid):
    cur.execute("UPDATE users SET credits=credits-1 WHERE id=?", (uid,))
    conn.commit()

# ---------- МЕНЮ ----------
def menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("🎨 Создать", "💰 Баланс")
    m.add("⭐ Купить")
    return m

# ---------- СЕРВИСЫ ----------
def gen1(prompt):
    url = f"https://image.pollinations.ai/prompt/{prompt}"
    return requests.get(url, timeout=60).content

def gen2(prompt):
    url = f"https://api.dicebear.com/7.x/bottts/png?seed={prompt}"
    return requests.get(url, timeout=60).content

def gen3(prompt):
    url = f"https://picsum.photos/seed/{prompt}/512"
    return requests.get(url, timeout=60).content

def gen4(prompt):
    url = f"https://loremflickr.com/512/512/{prompt}"
    return requests.get(url, timeout=60).content

def gen5(prompt):
    url = f"https://robohash.org/{prompt}.png?size=512x512"
    return requests.get(url, timeout=60).content

SERVICES = [gen1, gen2, gen3, gen4, gen5]

# ---------- ГЕНЕРАЦИЯ ----------
def generate(prompt):
    random.shuffle(SERVICES)
    for s in SERVICES:
        try:
            img = s(prompt)
            if img and len(img) > 1000:
                return img
        except:
            pass
    return None

# ---------- СТАРТ ----------
@bot.message_handler(commands=["start"])
def start(m):
    uid = m.from_user.id
    get_credits(uid)
    bot.send_message(uid,
        "🎨 <b>AI Художник</b>\n\n"
        "Напиши описание картинки\n"
        "например:\n"
        "<i>аниме девушка с мечом</i>",
        reply_markup=menu()
    )

# ---------- БАЛАНС ----------
@bot.message_handler(func=lambda m: m.text=="💰 Баланс")
def balance(m):
    c = get_credits(m.from_user.id)
    bot.send_message(m.chat.id, f"💰 Картинок: {c}", reply_markup=menu())

# ---------- КУПИТЬ ----------
@bot.message_handler(func=lambda m: m.text=="⭐ Купить")
def buy(m):
    add_credit(m.from_user.id, 10)
    bot.send_message(m.chat.id, "⭐ Начислено 10 картинок", reply_markup=menu())

# ---------- СОЗДАТЬ ----------
@bot.message_handler(func=lambda m: m.text=="🎨 Создать")
def create(m):
    bot.send_message(m.chat.id,
        "✏ Напиши описание картинки",
        reply_markup=menu()
    )

# ---------- ТЕКСТ ----------
@bot.message_handler(func=lambda m: True)
def text(m):
    uid = m.from_user.id

    if m.text in ["🎨 Создать","💰 Баланс","⭐ Купить"]:
        return

    credits = get_credits(uid)

    if credits <= 0:
        bot.send_message(uid,"❌ Нет картинок",reply_markup=menu())
        return

    msg = bot.send_message(uid,"⏳ Генерация...")

    try:
        img = generate(m.text)

        if not img:
            bot.edit_message_text("❌ Все сервисы недоступны", uid, msg.message_id)
            return

        sub_credit(uid)

        bot.delete_message(uid, msg.message_id)
        bot.send_photo(uid, img, caption="✅ Готово", reply_markup=menu())

    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка:\n{e}", uid, msg.message_id)

# ---------- СТАРТ ----------
print("BOT STARTED")
bot.infinity_polling()


