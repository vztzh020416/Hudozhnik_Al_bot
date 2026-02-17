import telebot
import sqlite3
import requests
import base64
from telebot import types
from io import BytesIO

# ========= CONFIG =========
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
OPENAI_API_KEY = "OPENAI_KEY"
ADMIN_ID = 1005217438
DB_NAME = "users.db"

bot = telebot.TeleBot(TOKEN)

# ========= DB =========
def db():
    return sqlite3.connect(DB_NAME)

def init_db():
    with db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 57,
            total_gen INTEGER DEFAULT 0
        )
        """)

init_db()

def get_user(uid):
    with db() as conn:
        r = conn.execute(
            "SELECT credits,total_gen FROM users WHERE user_id=?",
            (uid,)
        ).fetchone()
    return r

def add_user(uid):
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(user_id,credits) VALUES(?,57)",
            (uid,)
        )

def add_credits(uid, n):
    with db() as conn:
        conn.execute(
            "UPDATE users SET credits=credits+? WHERE user_id=?",
            (n, uid)
        )

def add_gen(uid):
    with db() as conn:
        conn.execute(
            "UPDATE users SET total_gen=total_gen+1 WHERE user_id=?",
            (uid,)
        )

# ========= OPENAI =========
def generate_image(prompt):
    try:
        r = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-image-1",
                "prompt": prompt,
                "size": "1024x1024"
            },
            timeout=120
        )

        if r.status_code != 200:
            return None, f"HTTP {r.status_code}: {r.text}"

        js = r.json()

        if "data" not in js or not js["data"]:
            return None, f"Bad response: {js}"

        b64 = js["data"][0].get("b64_json")
        if not b64:
            return None, f"No b64 in response: {js}"

        img = base64.b64decode(b64)
        return img, None

    except Exception as e:
        return None, str(e)

# ========= MENU =========
def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎨 Рисовать", "👤 Профиль")
    kb.add("⭐ Купить")
    return kb

# ========= START =========
@bot.message_handler(commands=["start"])
def start(m):
    uid = m.from_user.id
    add_user(uid)
    bot.send_message(
        uid,
        "🎨 Я рисую изображения ИИ\n57 бесплатных генераций",
        reply_markup=menu()
    )

# ========= PROFILE =========
@bot.message_handler(func=lambda m: m.text=="👤 Профиль")
def profile(m):
    u = get_user(m.from_user.id)
    if not u:
        return
    bot.send_message(
        m.chat.id,
        f"💰 Кредиты: {u[0]}\n🖼 Генераций: {u[1]}"
    )

# ========= SHOP =========
@bot.message_handler(func=lambda m: m.text=="⭐ Купить")
def shop(m):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("10 генераций ⭐10",callback_data="buy_10"))
    kb.add(types.InlineKeyboardButton("25 генераций ⭐20",callback_data="buy_25"))
    kb.add(types.InlineKeyboardButton("60 генераций ⭐45",callback_data="buy_60"))
    bot.send_message(m.chat.id,"Пакеты:",reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("buy_"))
def buy(call):
    packs = {
        "buy_10": (10,10),
        "buy_25": (25,20),
        "buy_60": (60,45)
    }

    credits, stars = packs[call.data]

    bot.send_invoice(
        chat_id=call.message.chat.id,
        title="Покупка генераций",
        description=f"{credits} генераций",
        invoice_payload=call.data,
        provider_token="",  # Stars
        currency="XTR",
        prices=[types.LabeledPrice("Генерации", stars)]
    )

@bot.pre_checkout_query_handler(func=lambda q: True)
def checkout(q):
    bot.answer_pre_checkout_query(q.id, ok=True)

@bot.message_handler(content_types=["successful_payment"])
def payment_ok(m):
    packs = {
        "buy_10":10,
        "buy_25":25,
        "buy_60":60
    }

    payload = m.successful_payment.invoice_payload
    if payload in packs:
        add_credits(m.from_user.id, packs[payload])
        bot.send_message(m.chat.id,"✅ Оплата прошла")

# ========= DRAW =========
@bot.message_handler(func=lambda m: m.text=="🎨 Рисовать")
def ask(m):
    u = get_user(m.from_user.id)
    if not u or u[0] <= 0:
        bot.send_message(m.chat.id,"❌ Нет кредитов")
        return

    msg = bot.send_message(m.chat.id,"Опиши что нарисовать:")
    bot.register_next_step_handler(msg, draw)

def draw(m):
    prompt = m.text
    uid = m.from_user.id

    wait = bot.send_message(m.chat.id,"🎨 Генерация...")

    img, err = generate_image(prompt)

    if err:
        bot.send_message(m.chat.id,"❌ Ошибка генерации")
        bot.send_message(ADMIN_ID,f"GEN ERROR:\n{prompt}\n{err}")
        bot.delete_message(m.chat.id, wait.message_id)
        return

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔁 Повторить",callback_data=f"redo|{prompt}"))

    bot.send_photo(
        m.chat.id,
        BytesIO(img),
        caption=f"📝 {prompt}",
        reply_markup=kb
    )

    add_credits(uid,-1)
    add_gen(uid)
    bot.delete_message(m.chat.id, wait.message_id)

@bot.callback_query_handler(func=lambda c:c.data.startswith("redo|"))
def redo(call):
    prompt = call.data.split("|",1)[1]

    wait = bot.send_message(call.message.chat.id,"🎨 Повтор...")

    img, err = generate_image(prompt)

    if err:
        bot.send_message(call.message.chat.id,"❌ Ошибка генерации")
        bot.send_message(ADMIN_ID,f"REDO ERROR:\n{prompt}\n{err}")
        bot.delete_message(call.message.chat.id, wait.message_id)
        return

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔁 Повторить",callback_data=f"redo|{prompt}"))

    bot.send_photo(
        call.message.chat.id,
        BytesIO(img),
        caption=f"📝 {prompt}",
        reply_markup=kb
    )

    add_credits(call.from_user.id,-1)
    add_gen(call.from_user.id)
    bot.delete_message(call.message.chat.id, wait.message_id)

# ========= ADMIN =========
@bot.message_handler(commands=["stats"])
def stats(m):
    if m.from_user.id != ADMIN_ID:
        return

    with db() as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        gens = conn.execute("SELECT SUM(total_gen) FROM users").fetchone()[0]

    bot.send_message(
        ADMIN_ID,
        f"👤 Пользователей: {users}\n🖼 Генераций: {gens or 0}"
    )

# ========= RUN =========
print("BOT STARTED")
bot.infinity_polling()
