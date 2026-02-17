import telebot
import sqlite3
import requests
import urllib.parse
import base64
from telebot import types
from io import BytesIO

# ===== НАСТРОЙКИ =====
TOKEN = "8543701615:AAEsc7fZp9ZREZkSVkIUQ7z4LznudgGqCAY"
ADMIN_ID = 1005217438
GEMINI_API_KEY = "AIzaSyCDPblP4egW9Fd6EG4XIcB0gJEHnFgoocc"

bot = telebot.TeleBot(TOKEN)

# ===== БАЗА =====
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS users (
user_id INTEGER PRIMARY KEY,
credits INTEGER DEFAULT 57,
referrer INTEGER,
total_gen INTEGER DEFAULT 0
)
""")
conn.commit()

# ===== ПОЛЬЗОВАТЕЛЬ =====
def get_user(uid):
    c.execute("SELECT credits,total_gen FROM users WHERE user_id=?", (uid,))
    return c.fetchone()

def add_user(uid, ref=None):
    c.execute("INSERT OR IGNORE INTO users (user_id,referrer) VALUES (?,?)", (uid, ref))
    if ref:
        c.execute("UPDATE users SET credits=credits+1 WHERE user_id=?", (ref,))
    conn.commit()

def add_credits(uid, val):
    c.execute("UPDATE users SET credits=credits+? WHERE user_id=?", (val, uid))
    conn.commit()

def add_gen(uid):
    c.execute("UPDATE users SET total_gen=total_gen+1 WHERE user_id=?", (uid,))
    conn.commit()

def users_count():
    return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]

# ===== МЕНЮ =====
def menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("🎨 Рисовать","👤 Профиль")
    m.add("👥 Рефералка","⭐ Купить попытки")
    return m

# ===== СТАРТ =====
@bot.message_handler(commands=['start'])
def start(msg):
    uid = msg.from_user.id
    args = msg.text.split()
    ref = int(args[1]) if len(args)>1 and args[1].isdigit() else None
    if ref == uid:
        ref=None
    add_user(uid, ref)
    bot.send_message(uid,"🎨 ИИ художник готов!\nУ тебя 57 попыток",reply_markup=menu())

# ===== ПРОФИЛЬ =====
@bot.message_handler(func=lambda m:m.text=="👤 Профиль")
def profile(msg):
    u = get_user(msg.from_user.id)
    if u:
        bot.send_message(msg.chat.id,
        f"👤 Профиль\n\n💰 Кредиты: {u[0]}\n🖼 Генераций: {u[1]}",
        reply_markup=menu())

# ===== РЕФ =====
@bot.message_handler(func=lambda m:m.text=="👥 Рефералка")
def ref(msg):
    me = bot.get_me().username
    link = f"https://t.me/{me}?start={msg.from_user.id}"
    bot.send_message(msg.chat.id,f"Приглашай друзей:\n{link}",reply_markup=menu())

# ===== МАГАЗИН =====
@bot.message_handler(func=lambda m:m.text=="⭐ Купить попытки")
def shop(msg):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("5 ⭐ = 5",callback_data="b5"))
    kb.add(types.InlineKeyboardButton("10 ⭐ = 12",callback_data="b10"))
    kb.add(types.InlineKeyboardButton("25 ⭐ = 35",callback_data="b25"))
    bot.send_message(msg.chat.id,"Покупка:",reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("b"))
def buy(cq):
    packs={"b5":5,"b10":12,"b25":35}
    add_credits(cq.from_user.id,packs[cq.data])
    bot.answer_callback_query(cq.id,"Начислено")
    bot.send_message(cq.message.chat.id,"✅ Кредиты добавлены",reply_markup=menu())

# ===== СТАТ АДМИН =====
@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id==ADMIN_ID:
        bot.send_message(msg.chat.id,
        f"👥 Пользователей: {users_count()}",
        reply_markup=menu())

# ===== РИСОВАНИЕ =====
@bot.message_handler(func=lambda m:m.text=="🎨 Рисовать")
def draw(msg):
    u=get_user(msg.from_user.id)
    if not u or u[0]<=0:
        bot.send_message(msg.chat.id,"Нет кредитов",reply_markup=menu())
        return
    m=bot.send_message(msg.chat.id,"Напиши что рисовать")
    bot.register_next_step_handler(m,gen)

# ===== GEMINI =====
def gen_gemini(prompt):
    url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    data={
    "contents":[{"parts":[{"text":f"Create image: {prompt}"}]}]
    }
    r=requests.post(url,json=data,timeout=60)
    if r.status_code==200:
        js=r.json()
        if "candidates" in js:
            txt=js["candidates"][0]["content"]["parts"][0].get("text")
            return None
    return None

# ===== POLLINATIONS =====
def gen_poll(prompt):
    try:
        safe=urllib.parse.quote(prompt)
        url=f"https://image.pollinations.ai/prompt/{safe}?width=1024&height=1024"
        r=requests.get(url,timeout=60)
        if r.status_code==200:
            return r.content
    except:
        pass
    return None

# ===== ГЕН =====
def gen(msg):
    uid=msg.from_user.id
    prompt=msg.text

    wait=bot.send_message(msg.chat.id,"🎨 Генерация...")

    img=gen_poll(prompt)

    if not img:
        bot.send_message(msg.chat.id,"⚠️ Gemini fallback...")
        img=gen_gemini(prompt)

    if img:
        bot.send_photo(msg.chat.id,BytesIO(img),caption=prompt,reply_markup=menu())
        add_credits(uid,-1)
        add_gen(uid)
    else:
        bot.send_message(msg.chat.id,"❌ Все сервисы недоступны",reply_markup=menu())

    bot.delete_message(msg.chat.id,wait.message_id)

# ===== ЗАПУСК =====
print("BOT OK")
bot.infinity_polling()
