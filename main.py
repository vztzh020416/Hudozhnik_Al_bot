import telebot
import sqlite3
import requests
import urllib.parse
import random
import time  # Добавлено для реализации паузы
from telebot import types

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
ADMIN_ID = 1005217438
DB_NAME = "users.db"

bot = telebot.TeleBot(TOKEN)

# Словарь для хранения времени последней генерации пользователя
last_gen_time = {}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, credits INTEGER DEFAULT 10, 
                       generations INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT credits, generations FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def log_gen(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits - 1, generations = generations + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# --- ИНТЕРФЕЙС (ГЛАВНОЕ МЕНЮ) ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🎨 Рисовать"), types.KeyboardButton("👤 Профиль"))
    return markup

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()
    bot.send_message(
        message.chat.id, 
        "✨ Бот готов! Нажмите кнопку ниже, чтобы начать.", 
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = get_user(message.from_user.id)
    if user:
        bot.send_message(
            message.chat.id, 
            f"👤 **Ваш профиль:**\nКредиты: {user[0]}\nГенераций: {user[1]}",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def ask_prompt(message):
    user_id = message.from_user.id
    current_time = time.time()

    # ПРОВЕРКА ПАУЗЫ (Анти-спам 10 секунд)
    if user_id in last_gen_time:
        elapsed_time = current_time - last_gen_time[user_id]
        if elapsed_time < 10:
            remaining = int(10 - elapsed_time)
            bot.send_message(message.chat.id, f"⏳ Подождите еще {remaining} сек. перед следующей генерацией.")
            return

    user = get_user(user_id)
    if user and user[0] > 0:
        msg = bot.send_message(
            message.chat.id, 
            "🖌 Введите описание картинки на английском:",
            reply_markup=types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(msg, generate_image)
    else:
        bot.send_message(message.chat.id, "❌ У вас закончились попытки.", reply_markup=main_menu())

# --- ЛОГИКА ГЕНЕРАЦИИ ---
def generate_image(message):
    if not message.text or message.text.startswith('/') or message.text in ["🎨 Рисовать", "👤 Профиль"]:
        bot.send_message(message.chat.id, "Генерация отменена.", reply_markup=main_menu())
        return

    prompt = message.text
    user_id = message.from_user.id

    # Запоминаем время начала генерации для анти-спама
    last_gen_time[user_id] = time.time()

    safe_prompt = urllib.parse.quote(prompt)
    seed = random.randint(1, 1000000)

    status_msg = bot.send_message(message.chat.id, "⏳ Рисую... Пожалуйста, подождите.")

    urls = [
        f"https://pollinations.ai/p/{safe_prompt}?seed={seed}&width=1024&height=1024&nologo=true",
        f"https://image.pollinations.ai/prompt/{safe_prompt}?seed={seed}&nologo=true"
    ]

    success = False
    for url in urls:
        try:
            response = requests.get(url, timeout=45, verify=False)
            if response.status_code == 200 and len(response.content) > 10000:
                bot.send_photo(
                    message.chat.id, 
                    response.content, 
                    caption=f"✅ Готово: {prompt}",
                    reply_markup=main_menu()
                )
                log_gen(user_id)
                bot.delete_message(message.chat.id, status_msg.message_id)
                success = True
                break
        except Exception as e:
            print(f"Ошибка сервера {url}: {e}")
            continue

    if not success:
        bot.edit_message_text(
            "❌ Не удалось получить картинку. Попробуйте другой запрос.", 
            message.chat.id, 
            status_msg.message_id
        )
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=main_menu())

# --- ЗАПУСК ---
if __name__ == "__main__":
    init_db()
    requests.packages.urllib3.disable_warnings() 
    print("Бот запущен! Анти-спам 10 сек активен.")
    bot.infinity_polling(skip_pending=True)
