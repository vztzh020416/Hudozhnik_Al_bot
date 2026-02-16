import telebot
import sqlite3
import requests
import urllib.parse
import traceback
import time
from telebot import types
from io import BytesIO

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
ADMIN_ID = 1005217438
DB_NAME = "users.db"

bot = telebot.TeleBot(TOKEN)

def send_error_to_admin(error_text, message=None):
    try:
        user_info = f"👤 User ID: {message.from_user.id}" if message else "Системная ошибка"
        full_log = f"🆘 *ОШИБКА В БОТЕ*\n\n{user_info}\n\n`{error_text[:3500]}`"
        bot.send_message(ADMIN_ID, full_log, parse_mode="Markdown")
    except:
        pass

# --- ИНИЦИАЛИЗАЦИЯ БД ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  credits INTEGER DEFAULT 57, 
                  referrer_id INTEGER, 
                  total_gen INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT credits, total_gen FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def update_credits(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def is_valid_image(data):
    """Проверяет, что данные - это настоящая картинка (JPEG или PNG)"""
    return (len(data) > 5000 and 
            (data[:2] == b'\xff\xd8' or  # JPEG
             data[:4] == b'\x89PNG'))    # PNG

# --- ОСНОВНОЙ ДВИЖОК (ТОЛЬКО ПОЛЛИНЕЙШНС) ---
def fetch_pollinations(prompt):
    """Пытается получить картинку из Pollinations с разными параметрами"""
    formats = [
        f"https://pollinations.ai/p/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true&seed={int(time.time())}",
        f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true",
        f"https://pollinations.ai/p/{urllib.parse.quote(prompt)}"
    ]
    
    for url in formats:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and is_valid_image(r.content):
                return r.content
        except:
            continue
    return None

# --- ГЛАВНАЯ ЛОГИКА ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎨 Рисовать", "👤 Профиль")
    bot.send_message(message.chat.id, "🎨 Привет! Нажми 'Рисовать', чтобы начать. У тебя 57 попыток.", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = get_user(message.from_user.id)
    if user:
        bot.send_message(message.chat.id, f"💰 Кредиты: {user[0]}\n🖼 Всего создано: {user[1]}")
    else:
        bot.send_message(message.chat.id, "👤 Профиль не найден")

@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def draw(message):
    user = get_user(message.from_user.id)
    if not user:
        bot.send_message(message.chat.id, "❌ Ошибка: пользователь не найден")
        return
    if user[0] <= 0:
        bot.send_message(message.chat.id, "❌ Закончились кредиты.")
        return
    
    msg = bot.send_message(message.chat.id, "Опишите картинку (English):", reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_draw)

def process_draw(message):
    if not message.text or message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ Некорректный запрос")
        return
    
    prompt = message.text
    wait_msg = bot.send_message(message.chat.id, "⏳ Рисую...")
    
    try:
        img_data = fetch_pollinations(prompt)
        
        if img_data:
            bot.send_photo(message.chat.id, BytesIO(img_data), caption=f"✨ Готово!\n📝 {prompt[:50]}...")
            update_credits(message.from_user.id, -1)
            
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET total_gen = total_gen + 1 WHERE user_id = ?", (message.from_user.id,))
            conn.commit()
            conn.close()
        else:
            bot.send_message(message.chat.id, "❌ Не удалось создать картинку. Попробуйте позже.")
            send_error_to_admin(f"Pollinations не вернул картинку для: {prompt}", message)
    
    except Exception as e:
        error_text = f"Ошибка: {str(e)}\n{traceback.format_exc()}"
        bot.send_message(message.chat.id, "❌ Техническая ошибка. Попробуйте позже.")
        send_error_to_admin(f"{error_text}\n\nPrompt: {prompt}", message)
    
    finally:
        bot.delete_message(message.chat.id, wait_msg.message_id)

if __name__ == "__main__":
    print("🤖 Бот запущен...")
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)
