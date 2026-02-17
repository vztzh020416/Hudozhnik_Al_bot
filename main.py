import telebot
import sqlite3
import requests
from telebot import types
from io import BytesIO

# ================= CONFIG =================
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
OPENAI_API_KEY = "OPENAI_API_KEY"
ADMIN_ID = 1005217438
DB_NAME = "users.db"

bot = telebot.TeleBot(TOKEN)

# ================= DB =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 57,
            referrer_id INTEGER,
            total_gen INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT credits, referrer_id, total_gen FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def register_user(user_id, ref_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (user_id, credits, referrer_id) VALUES (?,57,?)",
        (user_id, ref_id)
    )
    if ref_id and c.rowcount > 0:
        c.execute("UPDATE users SET credits=credits+1 WHERE user_id=?", (ref_id,))
    conn.commit()
    conn.close()

def update_credits(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET credits=credits+? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def add_generation(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET total_gen=total_gen+1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# ================= MENU =================
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎨 Рисовать", "👤 Профиль")
    kb.add("👥 Рефералка")
    return kb

# ================= OPENAI IMAGE =================
def generate_image(prompt):
    url = "https://api.openai.com/v1/images/generations"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-image-1",
        "prompt": prompt,
        "size": "1024x1024",
        "quality": "high"
    }

    r = requests.post(url, json=data, headers=headers, timeout=120)

    if r.status_code != 200:
        return None

    img_url = r.json()["data"][0]["url"]
    img = requests.get(img_url, timeout=60)
    return img.content

# ================= HANDLERS =================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()

    ref_id = None
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
        if ref_id == user_id:
            ref_id = None

    register_user(user_id, ref_id)

    bot.send_message(
        user_id,
        "🎨 Привет! Я рисую изображения ИИ.\nУ тебя 57 бесплатных генераций.",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = get_user(message.from_user.id)
    if not user:
        return

    text = (
        f"👤 Профиль\n\n"
        f"💰 Кредиты: {user[0]}\n"
        f"🖼 Генераций: {user[2]}"
    )
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "👥 Рефералка")
def ref(message):
    link = f"https://t.me/{bot.get_me().username}?start={message.from_user.id}"
    bot.send_message(
        message.chat.id,
        f"Приглашай друзей и получай 1 кредит\n{link}"
    )

# ================= DRAW =================
@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def draw(message):
    user = get_user(message.from_user.id)

    if not user or user[0] <= 0:
        bot.send_message(message.chat.id, "❌ Нет кредитов")
        return

    msg = bot.send_message(message.chat.id, "Опиши что нарисовать:")
    bot.register_next_step_handler(msg, process_draw)

def process_draw(message):
    if not message.text:
        return

    user_id = message.from_user.id
    prompt = message.text

    wait = bot.send_message(message.chat.id, "🎨 Рисую...")

    try:
        img = generate_image(prompt)

        if not img:
            bot.send_message(message.chat.id, "❌ Ошибка генерации")
            return

        bot.send_photo(
            message.chat.id,
            BytesIO(img),
            caption=f"📝 {prompt}",
            reply_markup=main_menu()
        )

        update_credits(user_id, -1)
        add_generation(user_id)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

    finally:
        bot.delete_message(message.chat.id, wait.message_id)

# ================= ADMIN =================
@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    gens = c.execute("SELECT SUM(total_gen) FROM users").fetchone()[0]
    conn.close()

    bot.send_message(
        ADMIN_ID,
        f"Пользователей: {users}\nГенераций: {gens or 0}"
    )

# ================= RUN =================
print("BOT STARTED")
bot.infinity_polling()

