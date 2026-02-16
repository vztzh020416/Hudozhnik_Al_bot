import telebot
import sqlite3
import requests
import urllib.parse
from telebot import types
from deep_translator import GoogleTranslator

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
DB_NAME = "users.db"

bot = telebot.TeleBot(TOKEN)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, credits INTEGER DEFAULT 57)''')
    conn.commit()
    conn.close()

@bot.message_handler(commands=['start'])
def start(message):
    init_db()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎨 Рисовать")
    bot.send_message(message.chat.id, "✅ Бот запущен! Нажми кнопку ниже.", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def draw_step(message):
    msg = bot.send_message(message.chat.id, "Что нарисовать? (Пиши по-русски)")
    bot.register_next_step_handler(msg, generate)

def generate(message):
    prompt_ru = message.text
    wait_msg = bot.send_message(message.chat.id, "⏳ Генерирую...")
    
    try:
        # Перевод
        prompt_en = GoogleTranslator(source='auto', target='en').translate(prompt_ru)
        # Генерация через Pollinations
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt_en)}?nologo=true"
        r = requests.get(url)
        
        if r.status_code == 200:
            bot.send_photo(message.chat.id, r.content, caption=f"Готово! Запрос: {prompt_ru}")
        else:
            bot.send_message(message.chat.id, "Ошибка сервера генерации.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")
    finally:
        bot.delete_message(message.chat.id, wait_msg.message_id)

if __name__ == "__main__":
    print(">>> Бот запускается... Если это сообщение есть, а старт не работает - проверь токен.")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"Критическая ошибка: {e}")
