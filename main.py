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

# --- БАЗА ДАННЫХ (теперь только для статистики) ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  total_generations INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

def log_generation(user_id):
    """Просто записываем факт генерации, без списания лимитов"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    c.execute('UPDATE users SET total_generations = total_generations + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_stats(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT total_generations FROM users WHERE user_id = ?', (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    total = get_stats(message.from_user.id)
    bot.reply_to(message, 
        f"🎨 Привет! Я рисую картинки **без ограничений**.\n"
        f"📊 Вы уже создали: {total} изображений.\n\n"
        f"Просто напиши, что нарисовать (на английском).")

@bot.message_handler(func=lambda message: True)
def draw(message):
    user_id = message.from_user.id
    prompt = message.text

    if prompt.startswith('/'):
        return

    # Сообщение о начале работы
    msg = bot.reply_to(message, "🎨 Рисую... это может занять до 30 секунд.")
    
    # Подготовка URL (добавил flux для качества и случайный seed)
    safe_prompt = urllib.parse.quote(prompt)
    seed = random.randint(1, 10000000)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?seed={seed}&model=flux&width=1024&height=1024&nologo=true"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=60)
        
        if response.status_code == 200 and len(response.content) > 1000:
            # Успешная отправка
            bot.send_photo(
                message.chat.id, 
                BytesIO(response.content), 
                caption=f"✨ Готово!",
                reply_to_message_id=message.message_id
            )
            bot.delete_message(message.chat.id, msg.message_id)
            log_generation(user_id) # Считаем статистику
        else:
            # Если API выдало ошибку
            error_msg = f"❌ Ошибка API ({response.status_code})."
            if response.status_code == 403:
                error_msg += "\nДоступ заблокирован (403). Попробуйте сменить промпт."
            elif response.status_code == 503:
                error_msg += "\nСервис перегружен (503). Подождите минуту."
                
            bot.edit_message_text(error_msg, message.chat.id, msg.message_id)
            
    except Exception as e:
        # Отображение технических ошибок в чате
        bot.edit_message_text(f"⚠️ Ошибка соединения:\n`{str(e)}`", message.chat.id, msg.message_id, parse_mode="Markdown")

if __name__ == "__main__":
    print("Бот запущен в режиме БЕЗЛИМИТА...")
    bot.infinity_polling()
