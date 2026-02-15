import telebot
import requests
import sqlite3
from io import BytesIO
from datetime import datetime

TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
bot = telebot.TeleBot(TOKEN)

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  credits INTEGER DEFAULT 3)''')
    conn.commit()
    conn.close()

init_db()

def get_credits(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT credits FROM users WHERE user_id = ?', (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 3

def use_credit(user_id):
    credits = get_credits(user_id)
    if credits > 0:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('UPDATE users SET credits = credits - 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True
    return False

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()
    credits = get_credits(user_id)
    bot.reply_to(message, f"🎨 Привет! Я рисую картинки. У тебя {credits} бесплатных генераций. Напиши что нарисовать, например: cute kitten")

@bot.message_handler(func=lambda message: True)
def draw(message):
    user_id = message.from_user.id
    prompt = message.text

    credits = get_credits(user_id)
    if credits <= 0:
        bot.reply_to(message, "😢 У тебя закончились бесплатные генерации. Приведи друга и получи ещё!")
        return

    if use_credit(user_id):
        bot.reply_to(message, "🎨 Рисую...")
        url = f"https://pollinations.ai/p/{prompt}?model=flux&width=512&height=512&nologo=true"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                bot.send_photo(message.chat.id, BytesIO(response.content))
        except:
            bot.reply_to(message, "😢 Ошибка")

bot.polling()
