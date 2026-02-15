import telebot
import requests
import sqlite3
import time
import random
import urllib.parse
from io import BytesIO
from datetime import datetime

# ВАШ ТОКЕН
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
bot = telebot.TeleBot(TOKEN)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  credits INTEGER DEFAULT 10)''') # Увеличил дефолт до 10 для теста
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
        # Если пользователя нет, создаем его
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()
        return 10

def update_credits(user_id, amount):
    """Универсальная функция для изменения баланса (отрицательное amount — трата, положительное — возврат)"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    credits = get_credits(message.from_user.id)
    bot.reply_to(message, f"🎨 Привет! Я рисую картинки.\n💰 Твой баланс: {credits} генераций.\n\nПросто напиши мне, что нарисовать (на английском).")

@bot.message_handler(func=lambda message: True)
def draw(message):
    user_id = message.from_user.id
    prompt = message.text

    # Проверка на команды
    if prompt.startswith('/'):
        return

    credits = get_credits(user_id)
    if credits <= 0:
        bot.reply_to(message, "😢 У тебя закончились генерации.")
        return

    # Списываем 1 кредит перед началом
    update_credits(user_id, -1)
    
    msg = bot.reply_to(message, "🎨 Начинаю рисовать... подожди немного.")
    
    # Правильное кодирование текста (чтобы не было ошибок с пробелами)
    safe_prompt = urllib.parse.quote(prompt)
    seed = random.randint(1, 1000000)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?seed={seed}&model=flux&width=1024&height=1024&nologo=true"
    
    try:
        # Устанавливаем заголовки, чтобы имитировать браузер (меньше шансов на бан)
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=60)
        
        if response.status_code == 200 and len(response.content) > 1000:
            bot.send_photo(
                message.chat.id, 
                BytesIO(response.content), 
                caption=f"✨ Готово! (Осталось: {get_credits(user_id)})",
                reply_to_message_id=message.message_id
            )
            bot.delete_message(message.chat.id, msg.message_id)
        else:
            # Если сервер вернул не 200, выводим код ошибки
            error_text = f"❌ Ошибка сервера API\nКод: {response.status_code}\nТекст: {response.text[:100]}"
            bot.edit_message_text(error_text, message.chat.id, msg.message_id)
            update_credits(user_id, 1) # Возвращаем кредит
            
    except requests.exceptions.Timeout:
        bot.edit_message_text("⏳ Ошибка: Сервер слишком долго не отвечает. Попробуй позже.", message.chat.id, msg.message_id)
        update_credits(user_id, 1)
    except Exception as e:
        # Вывод любой другой технической ошибки
        bot.edit_message_text(f"⚠️ Техническая ошибка:\n`{str(e)}`", message.chat.id, msg.message_id, parse_mode="Markdown")
        update_credits(user_id, 1)

if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
