import telebot
import sqlite3
import requests
import random
import time
import urllib.parse
from telebot import types
from io import BytesIO

TOKEN = "8543701615:AAEsc7fZp9ZREZkSVkIUQ7z4LznudgGqCAY"
ADMIN_ID = 1005217438

bot = telebot.TeleBot(TOKEN)

try:
    bot_username = bot.get_me().username
except:
    bot_username = "bot"

# ---------- БАЗА ----------
conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    credits INTEGER DEFAULT 57,
    total INTEGER DEFAULT 0
)
""")
conn.commit()

def add_user(uid):
    cur.execute("INSERT OR IGNORE INTO users(id) VALUES(?)",(uid,))
    conn.commit()

def get_user(uid):
    cur.execute("SELECT credits,total FROM users WHERE id=?",(uid,))
    return cur.fetchone()

def add_credits(uid,n):
    cur.execute("UPDATE users SET credits=credits+? WHERE id=?",(n,uid))
    conn.commit()

def use_credit(uid):
    cur.execute("UPDATE users SET credits=credits-1,total=total+1 WHERE id=?",(uid,))
    conn.commit()

# ---------- МЕНЮ ----------
def menu(uid=None):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("🎨 Рисовать","👤 Профиль")
    m.add("⭐ Купить")
    if uid == ADMIN_ID:
        m.add("📊 Статистика")
    return m

# ---------- СЕРВЕРА ----------
SERVERS = [
"https://image.pollinations.ai/prompt/{p}?seed={s}&r={r}",
"https://image.pollinations.ai/prompt/{p}?style=realistic&seed={s}&r={r}",
"https://image.pollinations.ai/prompt/{p}?style=anime&seed={s}&r={r}",
"https://image.pollinations.ai/prompt/{p}?style=photo&seed={s}&r={r}",
"https://image.pollinations.ai/prompt/{p}?width=768&height=768&seed={s}&r={r}",
"https://image.pollinations.ai/prompt/{p}?width=512&height=512&seed={s}&r={r}"
]

def generate(prompt):
    prompt = prompt + ", detailed, high quality"
    p = urllib.parse.quote(prompt)

    random.shuffle(SERVERS)

    for i,url in enumerate(SERVERS,1):
        seed = random.randint(1,9999999)
        r = int(time.time()*1000)
        link = url.format(p=p,s=seed,r=r)

        try:
            resp = requests.get(link,timeout=20)
            if resp.status_code==200 and len(resp.content)>5000:
                return resp.content,f"Сервер {i}"
        except:
            pass

    return None,None

# ---------- ХЕНДЛЕРЫ ----------
@bot.message_handler(commands=["start"])
def start(m):
    add_user(m.from_user.id)
    bot.send_message(m.chat.id,
        "🎨 Бот генерации изображений\nУ тебя 57 попыток",
        reply_markup=menu(m.from_user.id))

@bot.message_handler(func=lambda m: m.text=="👤 Профиль")
def profile(m):
    u = get_user(m.from_user.id)
    if u:
        bot.send_message(m.chat.id,
            f"Кредиты: {u[0]}\nГенераций: {u[1]}",
            reply_markup=menu(m.from_user.id))

@bot.message_handler(func=lambda m: m.text=="⭐ Купить")
def buy(m):
    add_credits(m.from_user.id,10)
    bot.send_message(m.chat.id,
        "🎁 Добавлено 10 попыток бесплатно",
        reply_markup=menu(m.from_user.id))

@bot.message_handler(func=lambda m: m.text=="📊 Статистика")
def stats(m):
    if m.from_user.id!=ADMIN_ID:
        return
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]
    cur.execute("SELECT SUM(total) FROM users")
    gen = cur.fetchone()[0]
    bot.send_message(m.chat.id,
        f"Пользователей: {users}\nГенераций: {gen or 0}",
        reply_markup=menu(m.from_user.id))

@bot.message_handler(func=lambda m: m.text=="🎨 Рисовать")
def draw(m):
    u = get_user(m.from_user.id)
    if not u or u[0]<=0:
        bot.send_message(m.chat.id,"Нет попыток",reply_markup=menu(m.from_user.id))
        return
    msg = bot.send_message(m.chat.id,"Напиши запрос")
    bot.register_next_step_handler(msg,gen)

def gen(m):
    if not m.text:
        return

    wait = bot.send_message(m.chat.id,"⏳ Генерация...")
    img,server = generate(m.text)

    if img:
        use_credit(m.from_user.id)
        bot.send_photo(m.chat.id,BytesIO(img),
            caption=f"{m.text}\n{server}",
            reply_markup=menu(m.from_user.id))
    else:
        bot.send_message(m.chat.id,
            "❌ Все бесплатные сервисы недоступны",
            reply_markup=menu(m.from_user.id))

    bot.delete_message(m.chat.id,wait.message_id)

print("BOT STARTED")
bot.infinity_polling()
