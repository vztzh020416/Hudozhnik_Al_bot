import telebot
import sqlite3
import requests
import base64
from telebot import types
from io import BytesIO

# ================= CONFIG =================
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
OPENAI_API_KEY = "OPENAI_KEY"
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

def get_user(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT credits,total_gen FROM users WHERE user_id=?", (uid,))
    u = c.fetchone()
    conn.close()
    return u

def register(uid, ref=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id,credits,referrer_id) VALUES(?,57,?)",(uid,ref))
    if ref and c.rowcount>0:
        c.execute("UPDATE users SET credits=credits+1 WHERE user_id=?",(ref,))
    conn.commit()
    conn.close()

def add_credits(uid, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET credits=credits+? WHERE user_id=?",(amount,uid))
    conn.commit()
    conn.close()

def add_gen(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET total_gen=total_gen+1 WHERE user_id=?",(uid,))
    conn.commit()
    conn.close()

# ================= OPENAI =================
def generate_image(prompt, retries=3):
    url = "https://api.openai.com/v1/images/generations"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-image-1",
        "prompt": prompt,
        "size": "1024x1024"
    }

    for _ in range(retries):
        try:
            r = requests.post(url, json=data, headers=headers, timeout=120)

            if r.status_code != 200:
                continue

            js = r.json()

            if "data" not in js:
                continue

            b64 = js["data"][0]["b64_json"]
            img = base64.b64decode(b64)
            return img

        except Exception as e:
            last_error = str(e)

    return None

# ================= MENU =================
def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎨 Рисовать", "👤 Профиль")
    kb.add("⭐ Купить", "👥 Рефералка")
    return kb

# ================= START =================
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    args = m.text.split()

    ref = None
    if len(args)>1 and args[1].isdigit():
        ref = int(args[1])
        if ref==uid:
            ref=None

    register(uid, ref)

    bot.send_message(
        uid,
        "🎨 Я рисую изображения ИИ\n57 бесплатных генераций",
        reply_markup=menu()
    )

# ================= PROFILE =================
@bot.message_handler(func=lambda m: m.text=="👤 Профиль")
def profile(m):
    u = get_user(m.from_user.id)
    if not u: return

    bot.send_message(
        m.chat.id,
        f"👤 Профиль\n\n💰 Кредиты: {u[0]}\n🖼 Генераций: {u[1]}"
    )

# ================= REF =================
@bot.message_handler(func=lambda m: m.text=="👥 Рефералка")
def ref(m):
    link=f"https://t.me/{bot.get_me().username}?start={m.from_user.id}"
    bot.send_message(m.chat.id,f"Приглашай друзей +1 кредит\n{link}")

# ================= SHOP =================
@bot.message_handler(func=lambda m: m.text=="⭐ Купить")
def shop(m):
    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("10 генераций ⭐10",callback_data="buy10"))
    kb.add(types.InlineKeyboardButton("25 генераций ⭐20",callback_data="buy25"))
    kb.add(types.InlineKeyboardButton("60 генераций ⭐45",callback_data="buy60"))
    bot.send_message(m.chat.id,"Выбери пакет:",reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("buy"))
def buy(call):
    packs={
        "buy10":(10,10),
        "buy25":(25,20),
        "buy60":(60,45)
    }

    credits,stars=packs[call.data]

    prices=[types.LabeledPrice("Генерации",stars)]

    bot.send_invoice(
        call.message.chat.id,
        "Покупка генераций",
        f"{credits} генераций",
        call.data,
        provider_token="",
        currency="XTR",
        prices=prices
    )

@bot.pre_checkout_query_handler(func=lambda q: True)
def checkout(q):
    bot.answer_pre_checkout_query(q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def pay_ok(m):
    payload=m.successful_payment.invoice_payload
    packs={
        "buy10":10,
        "buy25":25,
        "buy60":60
    }

    add_credits(m.from_user.id,packs[payload])
    bot.send_message(m.chat.id,"✅ Оплата прошла")

# ================= DRAW =================
@bot.message_handler(func=lambda m: m.text=="🎨 Рисовать")
def draw(m):
    u=get_user(m.from_user.id)
    if not u or u[0]<=0:
        bot.send_message(m.chat.id,"❌ Нет кредитов")
        return

    msg=bot.send_message(m.chat.id,"Опиши что нарисовать:")
    bot.register_next_step_handler(msg,gen)

def gen(m):
    if not m.text:
        return

    uid=m.from_user.id
    prompt=m.text

    wait=bot.send_message(m.chat.id,"🎨 Рисую...")

    try:
        img=generate_image(prompt)

        if not img:
            bot.send_message(m.chat.id,"❌ Ошибка генерации")
            bot.send_message(ADMIN_ID,f"GEN FAIL: {prompt}")
            return

        kb=types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔁 Повторить",callback_data=f"redo|{prompt}"))

        bot.send_photo(
            m.chat.id,
            BytesIO(img),
            caption=f"📝 {prompt}",
            reply_markup=kb
        )

        add_credits(uid,-1)
        add_gen(uid)

    except Exception as e:
        bot.send_message(m.chat.id,f"❌ Ошибка: {e}")
        bot.send_message(ADMIN_ID,f"ERROR: {e}")

    finally:
        bot.delete_message(m.chat.id,wait.message_id)

@bot.callback_query_handler(func=lambda c:c.data.startswith("redo"))
def redo(call):
    prompt=call.data.split("|",1)[1]
    fake=types.Message(
        message_id=0,
        from_user=call.from_user,
        date=None,
        chat=call.message.chat,
        content_type="text",
        options={}
    )
    fake.text=prompt
    gen(fake)

# ================= ADMIN =================
@bot.message_handler(commands=['stats'])
def stats(m):
    if m.from_user.id!=ADMIN_ID:
        return

    conn=sqlite3.connect(DB_NAME)
    c=conn.cursor()
    users=c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    gens=c.execute("SELECT SUM(total_gen) FROM users").fetchone()[0]
    conn.close()

    bot.send_message(
        ADMIN_ID,
        f"Пользователей: {users}\nГенераций: {gens or 0}"
    )

# ================= RUN =================
print("BOT STARTED")
bot.infinity_polling()
