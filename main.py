import telebot
import requests
import sqlite3
from io import BytesIO
from datetime import datetime

TOKEN = "ВСТАВЬ_СВОЙ_ТОКЕН_СЮДА"
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

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()
    bot.reply_to(message, "🎨 Привет! Я рисую картинки. Напиши что нарисовать, например: cute kitten")

@bot.message_handler(func=lambda message: True)
def draw(message):
    prompt = message.text
    bot.reply_to(message, "🎨 Рисую...")
    url = f"https://pollinations.ai/p/{prompt}?model=flux&width=512&height=512&nologo=true"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            bot.send_photo(message.chat.id, BytesIO(response.content))
    except:
        bot.reply_to(message, "😢 Ошибка")

bot.polling()