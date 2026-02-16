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
        full_log = f"🆘 *ОШИБКА В БОТЕ*\n\n{user_info}\n\n`{error_text[:3500]}`" # Ограничение длины
        bot.send_message(ADMIN_ID, full_log, parse_mode="Markdown")
    except: pass

# --- ИНИЦИАЛИЗАЦИЯ БД ---
def init_db():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, credits INTEGER DEFAULT 57, 
                  referrer_id INTEGER, total_gen INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

init_db()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_user(user_id):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT credits, total_gen FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone(); conn.close()
    return user

def update_credits(user_id, amount):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit(); conn.close()

# --- ДВИЖКИ ГЕНЕРАЦИИ ---
def fetch_pollinations(prompt):
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true&seed={int(time.time())}"
    r = requests.get(url, timeout=30)
    return r.content if r.status_code == 200 else None

def fetch_airforce(prompt):
    url = f"https://api.airforce/v1/imagine?prompt={urllib.parse.quote(prompt)}&model=flux"
    r = requests.get(url, timeout=30)
    return r.content if r.status_code == 200 else None

def fetch_magic(prompt):
    url = "https://api.magicstudio.com/v1/ai-art-generator/image"
    r = requests.post(url, data={'prompt': prompt, 'output_format': 'jpg', 'request_from': 'magicstudio'}, timeout=30)
    return r.content if r.status_code == 200 else None

# --- ГЛАВНАЯ ЛОГИКА ---
@bot.message_handler(commands=['start'])
def start(message):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit(); conn.close()
    bot.send_message(message.chat.id, "🎨 Привет! Нажми 'Рисовать', чтобы начать. У тебя 57 попыток.", 
                     reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🎨 Рисовать", "👤 Профиль"))

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = get_user(message.from_user.id)
    if user: bot.send_message(message.chat.id, f"💰 Кредиты: {user[0]}\n🖼 Всего создано: {user[1]}")

@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def draw(message):
    user = get_user(message.from_user.id)
    if not user or user[0] <= 0:
        return bot.send_message(message.chat.id, "❌ Закончились кредиты.")
    msg = bot.send_message(message.chat.id, "Опишите картинку (English):", reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_draw)

def process_draw(message):
    if not message.text or message.text.startswith('/'): return
    prompt = message.text
    wait_msg = bot.send_message(message.chat.id, "⏳ Начинаю работу...")
    
    engines = [("Pollinations", fetch_pollinations), ("Flux", fetch_airforce), ("MagicStudio", fetch_magic)]
    success = False

    for name, func in engines:
        try:
            bot.edit_message_text(f"⏳ Пробую движок: *{name}*...", message.chat.id, wait_msg.message_id, parse_mode="Markdown")
            img_data = func(prompt)
            
            if img_data:
                # Пытаемся отправить фото. Если Telegram выдаст IMAGE_PROCESS_FAILED, это уйдет в except и запустит следующий движок.
                bot.send_photo(message.chat.id, BytesIO(img_data), caption=f"✅ Готово через {name}!")
                update_credits(message.from_user.id, -1)
                conn = sqlite3.connect(DB_NAME); c = conn.cursor()
                c.execute("UPDATE users SET total_gen = total_gen + 1 WHERE user_id = ?", (message.from_user.id,))
                conn.commit(); conn.close()
                success = True
                break
        except Exception as e:
            print(f"Ошибка движка {name}: {e}")
            # Не пугаем пользователя, просто идем к следующему движку в цикле
            continue

    if not success:
        bot.send_message(message.chat.id, "❌ Все движки сейчас заняты. Попробуйте через минуту.")
        send_error_to_admin("All engines failed to provide a valid image.", message)
    
    bot.delete_message(message.chat.id, wait_msg.message_id)

if __name__ == "__main__":
    while True:
        try: bot.polling(none_stop=True)
        except: time.sleep(5)
