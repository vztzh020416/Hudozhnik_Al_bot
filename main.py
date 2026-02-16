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
        full_log = f"🆘 *ОШИБКА В БОТЕ*\n\n{user_info}\n\n`{error_text}`"
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

# --- ФУНКЦИИ БД ---
def get_user(user_id):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT credits, referrer_id, total_gen FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone(); conn.close()
    return user

def register_user(user_id, ref_id=None):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, credits, referrer_id) VALUES (?, ?, ?)", (user_id, 57, ref_id))
    if ref_id and c.rowcount > 0: 
        c.execute("UPDATE users SET credits = credits + 1 WHERE user_id = ?", (ref_id,))
    conn.commit(); conn.close()

def update_credits(user_id, amount):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit(); conn.close()

# --- ЛОГИКА ГЕНЕРАЦИИ (3 ДВИЖКА) ---

def engine_1_pollinations(prompt):
    """Движок #1: Pollinations.ai"""
    safe_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true&seed={int(time.time())}"
    response = requests.get(url, timeout=30)
    if response.status_code == 200:
        return response.content
    return None

def engine_2_flux(prompt):
    """Движок #2: Flux via Cloudflare (Mirror)"""
    safe_prompt = urllib.parse.quote(prompt)
    # Используем альтернативное зеркало Flux
    url = f"https://api.airforce/v1/imagine?prompt={safe_prompt}&model=flux&size=1:1"
    response = requests.get(url, timeout=30)
    if response.status_code == 200:
        return response.content
    return None

def engine_3_magicstudio(prompt):
    """Движок #3: MagicStudio"""
    # Этот сервис часто работает, когда другие лежат
    url = f"https://api.magicstudio.com/v1/ai-art-generator/image"
    payload = {
        'prompt': prompt,
        'output_format': 'jpg',
        'user_profile_id': 'null',
        'anonymous_user_id': 'abcd-1234',
        'request_from': 'magicstudio'
    }
    response = requests.post(url, data=payload, timeout=30)
    if response.status_code == 200:
        return response.content
    return None

# --- КЛАВИАТУРА ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎨 Рисовать", "👤 Профиль")
    markup.add("👥 Рефералка", "⭐ Купить попытки")
    return markup

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    register_user(message.from_user.id)
    bot.send_message(message.chat.id, "🎨 Привет! У тебя есть 57 попыток.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = get_user(message.from_user.id)
    if user:
        bot.send_message(message.chat.id, f"👤 *Профиль*\n\n💰 Кредиты: {user[0]}\n🖼 Генераций: {user[2]}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def ask_prompt(message):
    user = get_user(message.from_user.id)
    if not user or user[0] <= 0:
        bot.send_message(message.chat.id, "❌ Нет кредитов.")
        return
    msg = bot.send_message(message.chat.id, "Опишите картинку (English):", reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_generation)

def process_generation(message):
    if not message.text or message.text.startswith('/'): return
    prompt = message.text
    wait_msg = bot.send_message(message.chat.id, "⏳ Генерирую (пробую движок #1)...")
    
    image_data = None
    engines = [
        ("Pollinations", engine_1_pollinations),
        ("Flux", engine_2_flux),
        ("MagicStudio", engine_3_magicstudio)
    ]

    # ПЕРЕБОР ДВИЖКОВ
    for name, func in engines:
        try:
            bot.edit_message_text(f"⏳ Работает движок: *{name}*...", message.chat.id, wait_msg.message_id, parse_mode="Markdown")
            image_data = func(prompt)
            if image_data:
                break # Если получили картинку, выходим из цикла
        except Exception as e:
            print(f"Ошибка движка {name}: {e}")
            continue # Пробуем следующий

    if image_data:
        try:
            bot.send_photo(message.chat.id, BytesIO(image_data), caption=f"✅ Готово!\nИспользован: {name}")
            update_credits(message.from_user.id, -1)
            # Обновляем счетчик
            conn = sqlite3.connect(DB_NAME); c = conn.cursor()
            c.execute("UPDATE users SET total_gen = total_gen + 1 WHERE user_id = ?", (message.from_user.id,))
            conn.commit(); conn.close()
        except Exception as e:
            send_error_to_admin(traceback.format_exc(), message)
    else:
        bot.send_message(message.chat.id, "❌ К сожалению, ни один движок не ответил. Попробуйте другой запрос.")
        send_error_to_admin(f"All engines failed for prompt: {prompt}", message)

    bot.delete_message(message.chat.id, wait_msg.message_id)

# --- АДМИН КОМАНДЫ ---

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id != ADMIN_ID: return
    msg = bot.send_message(ADMIN_ID, "Введите текст для всех:")
    bot.register_next_step_handler(msg, run_broadcast)

def run_broadcast(message):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    users = c.execute("SELECT user_id FROM users").fetchall(); conn.close()
    for u in users:
        try: bot.send_message(u[0], message.text); time.sleep(0.1)
        except: pass
    bot.send_message(ADMIN_ID, "📢 Готово!")

# --- ЗАПУСК ---
if __name__ == "__main__":
    print("Бот запущен с 3 движками...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except:
            time.sleep(5)
