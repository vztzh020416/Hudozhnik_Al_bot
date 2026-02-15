import telebot
import requests
import sqlite3
import time
import random
import urllib.parse
from io import BytesIO

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
bot = telebot.TeleBot(TOKEN)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # Создаем колонку credits с дефолтным значением 100
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  credits INTEGER DEFAULT 100)''')
    conn.commit()
    conn.close()

init_db()

def get_credits(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT credits FROM users WHERE user_id = ?', (user_id,))
    res = c.fetchone()
    conn.close()
    if res:
        return res[0]
    else:
        # Если пользователя нет, регистрируем и даем 100 кредитов
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (user_id, credits) VALUES (?, ?)', (user_id, 100))
        conn.commit()
        conn.close()
        return 100

def update_credits(user_id, amount):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    credits = get_credits(message.from_user.id)
    bot.reply_to(message, 
        f"🎨 Привет! Я рисую картинки по твоему описанию.\n"
        f"🎁 Тебе начислено: **{credits} генераций**.\n\n"
        f"Напиши, что нарисовать (на английском), например: `cyberpunk city`", 
        parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def draw(message):
    user_id = message.from_user.id
    prompt = message.text

    if prompt.startswith('/'):
        return

    credits = get_credits(user_id)
    if credits <= 0:
        bot.reply_to(message, "😢 Твои 100 генераций закончились.")
        return

    # Списываем 1 кредит
    update_credits(user_id, -1)
    
    msg = bot.reply_to(message, f"🎨 Рисую... (Осталось: {credits - 1})")
    
    # Подготовка URL
    safe_prompt = urllib.parse.quote(prompt)
    seed = random.randint(1, 9999999)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?seed={seed}&model=flux&width=1024&height=1024&nologo=true"
    
    try:
        # Заголовки для имитации браузера
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=60)
        
        if response.status_code == 200 and len(response.content) > 1000:
            bot.send_photo(
                message.chat.id, 
                BytesIO(response.content), 
                caption=f"✅ Готово! У тебя осталось {get_credits(user_id)} попыток.",
                reply_to_message_id=message.message_id
            )
            bot.delete_message(message.chat.id, msg.message_id)
        else:
            # Вывод кода ошибки сервера (403, 500, 503 и т.д.)
            bot.edit_message_text(f"❌ Ошибка API: {response.status_code}\nПопробуйте другой текст.", message.chat.id, msg.message_id)
            update_credits(user_id, 1) # Возврат кредита при ошибке
            
    except Exception as e:
        # Вывод технической ошибки (проблемы с интернетом или кодом)
        bot.edit_message_text(f"⚠️ Ошибка соединения:\n`{str(e)}`", message.chat.id, msg.message_id, parse_mode="Markdown")
        update_credits(user_id, 1) # Возврат кредита

if __name__ == "__main__":
    print("Бот запущен. Лимит: 100 генераций на пользователя.")
    bot.infinity_polling()
