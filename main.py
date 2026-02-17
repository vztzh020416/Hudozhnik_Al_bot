import telebot
from telebot import types
import requests
import sqlite3
import time
import random

# ⚠️ ВСТАВЬТЕ СЮДА НОВЫЙ ТОКЕН (старый скомпрометирован!)
BOT_TOKEN = "8543701615:AAEsc7fZp9ZREZkSVkIUQ7z4LznudgGqCAY"
ADMIN_ID = 1005217438

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

# ---------- СЧЕТЧИК ПОЛЬЗОВАТЕЛЕЙ ----------
def users_count():
    cur.execute("SELECT COUNT(*) FROM users")
    return cur.fetchone()[0]

# ---------- МЕНЮ ----------
def menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("🎨 Создать", "💰 Баланс")
    m.add("⭐ Купить")
    m.add("📊 Статистика")  # <--- ДОБАВИЛ КНОПКУ СЮДА
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

# ---------- СТАТИСТИКА (КОМАНДА /stats) ----------
@bot.message_handler(commands=["stats"])
def stats_cmd(m):
    if m.from_user.id == ADMIN_ID:
        count = users_count()
        bot.send_message(m.chat.id,
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: <b>{count}</b>",
            reply_markup=menu()
        )

# ---------- СТАТИСТИКА (КНОПКА В МЕНЮ) ----------
@bot.message_handler(func=lambda m: m.text == "📊 Статистика")
def stats_btn(m):
    if m.from_user.id == ADMIN_ID:
        count = users_count()
        bot.send_message(m.chat.id,
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: <b>{count}</b>",
            reply_markup=menu()
        )
    else:
        bot.send_message(m.chat.id, "❌ Доступ запрещен. Это меню только для админа.", reply_markup=menu())

# ---------- БАЛАНС ----------
@bot.message_handler(func=lambda m: m.text=="💰 Баланс")
def balance(m):
    c = get_credits(m.from_user.id)
    bot.send_message(m.chat.id, f"💰 Картинок осталось: {c}", reply_markup=menu())

# ---------- КУПИТЬ ----------
@bot.message_handler(func=lambda m: m.text=="⭐ Купить")
def buy(m):
    add_credit(m.from_user.id, 10)
    bot.send_message(m.chat.id, "⭐ Начислено 10 картинок", reply_markup=menu())

# ---------- СОЗДАТЬ ----------
@bot.message_handler(func=lambda m: m.text=="🎨 Создать")
def create(m):
    bot.send_message(m.chat.id,
        "✏ Напиши описание картинки (можно по-русски или по-английски)",
        reply_markup=menu()
    )

# ---------- ОБРАБОТКА ТЕКСТА ----------
@bot.message_handler(func=lambda m: True)
def text_handler(m):
    uid = m.from_user.id

    # Игнорируем нажатия кнопок меню (добавил Статистику в список)
    if m.text in ["🎨 Создать","💰 Баланс","⭐ Купить", "📊 Статистика"]:
        return

    credits = get_credits(uid)

    if credits <= 0:
        bot.send_message(uid,"❌ У вас закончились картинки. Нажмите '⭐ Купить', чтобы пополнить.", reply_markup=menu())
        return

    msg = bot.send_message(uid,"⏳ <b>Генерация началась...</b>", parse_mode="HTML")

    try:
        img = generate(m.text)

        if not img:
            bot.edit_message_text("❌ Сейчас все ИИ-сервисы заняты. Попробуйте другой запрос.", uid, msg.message_id)
            return

        sub_credit(uid)

        bot.delete_message(uid, msg.message_id)
        bot.send_photo(uid, img, caption="✅ <b>Ваша картинка готова!</b>", reply_markup=menu())

    except Exception as e:
        bot.edit_message_text(f"❌ Произошла ошибка:\n<code>{e}</code>", uid, msg.message_id)

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    print(">>> БОТ ЗАПУЩЕН")
    bot.infinity_polling(skip_pending=True)

