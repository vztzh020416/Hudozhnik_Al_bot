import telebot
from telebot import types
import requests
import sqlite3
import time

BOT_TOKEN = "8543701615:AAEsc7fZp9ZREZkSVkIUQ7z4LznudgGqCAY"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ---------- БАЗА ----------
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY,
credits INTEGER DEFAULT 5,
created INTEGER DEFAULT 0
)
""")
conn.commit()

def get_user(uid):
    cur.execute("SELECT credits,created FROM users WHERE id=?", (uid,))
    r = cur.fetchone()
    if r:
        return r
    cur.execute("INSERT INTO users(id) VALUES(?)", (uid,))
    conn.commit()
    return (5,0)

def add_credit(uid, n):
    cur.execute("UPDATE users SET credits=credits+? WHERE id=?", (n,uid))
    conn.commit()

def sub_credit(uid):
    cur.execute("UPDATE users SET credits=credits-1 WHERE id=?", (uid,))
    conn.commit()

def add_created(uid):
    cur.execute("UPDATE users SET created=created+1 WHERE id=?", (uid,))
    conn.commit()

def stats():
    cur.execute("SELECT COUNT(*), SUM(created) FROM users")
    r = cur.fetchone()
    users = r[0] if r[0] else 0
    imgs = r[1] if r[1] else 0
    return users, imgs

# ---------- МЕНЮ ----------
def menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("🎨 Создать", "💰 Баланс")
    m.add("⭐ Купить", "📊 Статистика")
    return m

# ---------- ГЕНЕРАЦИЯ ----------
def generate(prompt):
    url = f"https://image.pollinations.ai/prompt/{prompt}"
    r = requests.get(url, timeout=120)
    if r.status_code == 200 and len(r.content) > 5000:
        return r.content
    return None

# ---------- СТАРТ ----------
@bot.message_handler(commands=["start"])
def start(m):
    get_user(m.from_user.id)
    bot.send_message(
        m.chat.id,
        "🎨 <b>AI Художник</b>\n\n"
        "Опиши картинку словами\n"
        "пример:\n"
        "<i>realistic house in forest</i>",
        reply_markup=menu()
    )

# ---------- БАЛАНС ----------
@bot.message_handler(func=lambda m: m.text=="💰 Баланс")
def balance(m):
    credits, created = get_user(m.from_user.id)
    bot.send_message(
        m.chat.id,
        f"💰 Осталось: {credits}\n"
        f"🎨 Создано: {created}",
        reply_markup=menu()
    )

# ---------- КУПИТЬ ----------
@bot.message_handler(func=lambda m: m.text=="⭐ Купить")
def buy(m):
    add_credit(m.from_user.id, 10)
    bot.send_message(m.chat.id,"⭐ +10 картинок",reply_markup=menu())

# ---------- СТАТА ----------
@bot.message_handler(func=lambda m: m.text=="📊 Статистика")
def stat(m):
    u,i = stats()
    bot.send_message(
        m.chat.id,
        f"👥 Пользователей: {u}\n"
        f"🖼 Картинок создано: {i}",
        reply_markup=menu()
    )

# ---------- СОЗДАТЬ ----------
@bot.message_handler(func=lambda m: m.text=="🎨 Создать")
def create(m):
    bot.send_message(m.chat.id,"✏ Напиши описание",reply_markup=menu())

# ---------- ТЕКСТ ----------
@bot.message_handler(func=lambda m: True)
def text(m):
    uid = m.from_user.id

    if m.text in ["🎨 Создать","💰 Баланс","⭐ Купить","📊 Статистика"]:
        return

    credits, created = get_user(uid)

    if credits <= 0:
        bot.send_message(uid,"❌ Нет картинок",reply_markup=menu())
        return

    msg = bot.send_message(uid,"⏳ Рисую...")

    try:
        img = generate(m.text)

        if not img:
            bot.edit_message_text("❌ Сервис недоступен",uid,msg.message_id)
            return

        sub_credit(uid)
        add_created(uid)

        bot.delete_message(uid,msg.message_id)
        bot.send_photo(uid,img,"✅ Готово",reply_markup=menu())

    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка:\n{e}",uid,msg.message_id)

print("BOT OK")
bot.infinity_polling()
