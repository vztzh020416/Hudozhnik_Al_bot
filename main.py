import telebot
import sqlite3
import requests
import urllib.parse
import time
import random
from telebot import types
from io import BytesIO
from deep_translator import GoogleTranslator  # Добавили переводчик

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
ADMIN_ID = 1005217438
DB_NAME = "users.db"

bot = telebot.TeleBot(TOKEN)

# --- ИНИЦИАЛИЗАЦИЯ БД ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  credits INTEGER DEFAULT 57, 
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
    c.execute("UPDATE users SET credits = credits + ?, total_gen = total_gen + (CASE WHEN ? < 0 THEN 1 ELSE 0 END) WHERE user_id = ?", 
              (amount, amount, user_id))
    conn.commit()
    conn.close()

def is_valid_image(data):
    if not data or len(data) < 2000: return False
    return data[:2] == b'\xff\xd8' or data[:4] == b'\x89PNG' or b'WEBP' in data[:12]

# --- ДВИЖКИ ГЕНЕРАЦИИ ---
def engine_pollinations(prompt):
    try:
        seed = random.randint(1, 999999)
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true&seed={seed}"
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and is_valid_image(r.content):
            return r.content, "Pollinations"
    except: pass
    return None, None

def engine_hercai(prompt):
    try:
        url = f"https://hercai.onrender.com/v3/text2image?prompt={urllib.parse.quote(prompt)}"
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            img_url = r.json().get("url")
            img_r = requests.get(img_url, timeout=20)
            if is_valid_image(img_r.content):
                return img_r.content, "Hercai"
    except: pass
    return None, None

# ==================== ЛОГИКА БОТА ====================

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
    bot.send_message(message.chat.id, "🎨 **Бот готов!**\nТеперь можно писать запросы на любом языке (даже на русском).", 
                     reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = get_user(message.from_user.id)
    if user:
        bot.send_message(message.chat.id, f"👤 **Профиль**\n\n💰 Кредиты: `{user[0]}`\n🖼 Создано: `{user[1]}`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def draw_request(message):
    user = get_user(message.from_user.id)
    if not user or user[0] <= 0:
        bot.send_message(message.chat.id, "❌ Лимиты исчерпаны.")
        return
    
    msg = bot.send_message(message.chat.id, "📝 **Опишите картинку:**\n(Можно на русском, например: 'рыжий кот в скафандре')", 
                           reply_markup=types.ForceReply(), parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_generation)

def process_generation(message):
    if not message.text or message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ Отменено.")
        return

    raw_text = message.text
    wait_msg = bot.send_message(message.chat.id, "⏳ *Перевожу и генерирую...*", parse_mode="Markdown")
    
    try:
        # Автоматический перевод на английский
        translated_prompt = GoogleTranslator(source='auto', target='en').translate(raw_text)
    except:
        translated_prompt = raw_text # Если перевод упал, пробуем как есть

    engines = [engine_pollinations, engine_hercai]
    img_data, used_engine = None, None

    for engine in engines:
        img_data, used_engine = engine(translated_prompt)
        if img_data: break

    if img_data:
        bot.send_chat_action(message.chat.id, 'upload_photo')
        bot.send_photo(message.chat.id, img_data, 
                       caption=f"✅ **Готово!**\n🌍 Перевод: `{translated_prompt}`\n🎨 Движок: `{used_engine}`", 
                       parse_mode="Markdown")
        update_credits(message.from_user.id, -1)
    else:
        bot.send_message(message.chat.id, "❌ Не удалось создать картинку. Попробуйте другой запрос.")

    bot.delete_message(message.chat.id, wait_msg.message_id)

if __name__ == "__main__":
    print("🚀 Бот запущен (с поддержкой русского языка)!")
    bot.infinity_polling()
