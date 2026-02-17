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

try:
    bot_username = bot.get_me().username
except Exception as e:
    print("Ошибка токена:", e)
    bot_username = "bot"

# ====== БАЗА ======
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        credits INTEGER DEFAULT 10,
        referrer_id INTEGER,
        total_gen INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ====== БД ФУНКЦИИ ======
def get_user(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT credits,total_gen FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    conn.close()
    return row

def register(uid, ref=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id,credits,referrer_id) VALUES(?,?,?)",(uid,10,ref))
    if ref and c.rowcount:
        c.execute("UPDATE users SET credits=credits+1 WHERE user_id=?", (ref,))
    conn.commit()
    conn.close()

def add_credits(uid, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET credits=credits+? WHERE user_id=?", (amount,uid))
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
    kb.add("🎨 Рисовать","👤 Профиль")
    kb.add("👥 Рефералка","⭐ Купить")
    return kb

# ====== СЕРВИСЫ ======
def generate_image(prompt):
    safe = urllib.parse.quote(prompt)

    services = [
        f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024",
        f"https://image.pollinations.ai/prompt/{safe}?model=stable-diffusion",
        f"https://image.pollinations.ai/prompt/{safe}?model=flux",
        f"https://image.pollinations.ai/prompt/{safe}?model=deliberate"
    ]

    for url in services:
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200 and len(r.content) > 1000:
                return r.content
        except Exception:
            continue

    return None

# ====== СТАРТ ======
@bot.message_handler(commands=["start"])
def start(msg):
    uid = msg.from_user.id
    args = msg.text.split()
    ref = int(args[1]) if len(args)>1 and args[1].isdigit() else None
    if ref == uid:
        ref=None

    register(uid,ref)

    bot.send_message(uid,
        "🎨 Бот генерации изображений\n\n"
        "У тебя 10 бесплатных попыток",
        reply_markup=menu()
    )

# ====== ПРОФИЛЬ ======
@bot.message_handler(func=lambda m:m.text=="👤 Профиль")
def profile(msg):
    u = get_user(msg.from_user.id)
    if not u: return
    bot.send_message(msg.chat.id,
        f"👤 Профиль\n"
        f"Кредиты: {u[0]}\n"
        f"Генераций: {u[1]}",
        reply_markup=menu()
    )

# ====== РЕФЕРАЛ ======
@bot.message_handler(func=lambda m:m.text=="👥 Рефералка")
def ref(msg):
    link=f"https://t.me/{bot_username}?start={msg.from_user.id}"
    bot.send_message(msg.chat.id,
        f"Приглашай друзей (+1)\n{link}",
        reply_markup=menu()
    )

# ====== МАГАЗИН ======
@bot.message_handler(func=lambda m:m.text=="⭐ Купить")
def shop(msg):
    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("10 ⭐ = 10",callback_data="buy10"))
    kb.add(types.InlineKeyboardButton("25 ⭐ = 30",callback_data="buy30"))
    kb.add(types.InlineKeyboardButton("50 ⭐ = 80",callback_data="buy80"))
    bot.send_message(msg.chat.id,"Покупка:",reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("buy"))
def buy(call):
    data={"buy10":10,"buy30":30,"buy80":80}
    stars=int(call.data.replace("buy",""))
    credits=data[call.data]

    bot.send_invoice(
        call.message.chat.id,
        "Покупка кредитов",
        f"{credits} генераций",
        f"pay_{credits}",
        "",
        "XTR",
        [types.LabeledPrice("Кредиты",stars)]
    )

@bot.pre_checkout_query_handler(func=lambda q:True)
def checkout(q):
    bot.answer_pre_checkout_query(q.id,True)

@bot.message_handler(content_types=["successful_payment"])
def paid(msg):
    credits=int(msg.successful_payment.invoice_payload.split("_")[1])
    add_credits(msg.from_user.id,credits)
    bot.send_message(msg.chat.id,f"Начислено {credits}",reply_markup=menu())

# ====== РИСОВАНИЕ ======
@bot.message_handler(func=lambda m:m.text=="🎨 Рисовать")
def draw(msg):
    u=get_user(msg.from_user.id)
    if not u or u[0]<=0:
        bot.send_message(msg.chat.id,"Нет кредитов",reply_markup=menu())
        return

    m=bot.send_message(msg.chat.id,"Напиши запрос")
    bot.register_next_step_handler(m,gen)

def gen(msg):
    uid=msg.from_user.id
    prompt=msg.text

    wait=bot.send_message(msg.chat.id,"Генерация...")

    try:
        img=generate_image(prompt)

        if not img:
            bot.send_message(msg.chat.id,"❌ Все сервисы недоступны",reply_markup=menu())
            return

        bot.send_photo(msg.chat.id,BytesIO(img),caption=prompt,reply_markup=menu())

        add_credits(uid,-1)
        add_gen(uid)

    except Exception as e:
        bot.send_message(msg.chat.id,f"Ошибка: {e}",reply_markup=menu())

    bot.delete_message(msg.chat.id,wait.message_id)

# ====== СТАТИСТИКА ======
@bot.message_handler(commands=["stats"])
def stats(msg):
    if msg.from_user.id!=ADMIN_ID: return
    conn=sqlite3.connect(DB_NAME)
    c=conn.cursor()
    users=c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    gen=c.execute("SELECT SUM(total_gen) FROM users").fetchone()[0]
    conn.close()
    bot.send_message(msg.chat.id,
        f"Пользователей: {users}\nГенераций: {gen or 0}"
    )

# ====== ЗАПУСК ======
print("BOT STARTED")
bot.infinity_polling()
