import telebot
import sqlite3
import requests
import urllib.parse
from telebot import types
from io import BytesIO

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8543701615:AAEsc7fZp9ZREZkSVkIUQ7z4LznudgGqCAY"
ADMIN_ID = 1005217438
DB_NAME = "users.db"

bot = telebot.TeleBot(TOKEN)

try:
    bot_username = bot.get_me().username
except Exception as e:
    print(f"Ошибка при запуске: {e}")
    bot_username = "Bot"

# --- ИНИЦИАЛИЗАЦИЯ БД ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 57,
            referrer_id INTEGER,
            total_gen INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- БД ---
def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT credits, referrer_id, total_gen FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def register_user(user_id, ref_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (user_id, credits, referrer_id) VALUES (?, ?, ?)",
        (user_id, 57, ref_id)
    )
    if ref_id and c.rowcount > 0:
        c.execute("UPDATE users SET credits = credits + 1 WHERE user_id = ?", (ref_id,))
    conn.commit()
    conn.close()

def update_credits(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- UI ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎨 Рисовать", "👤 Профиль")
    markup.add("👥 Рефералка", "⭐ Купить попытки")
    return markup

# --- START ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()
    ref_id = None

    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
        if ref_id == user_id:
            ref_id = None

    register_user(user_id, ref_id)

    bot.send_message(
        user_id,
        "🎨 Привет! Я создаю шедевры с помощью ИИ.\nУ тебя есть 57 бесплатных попыток!",
        reply_markup=main_menu()
    )

# --- ПРОФИЛЬ ---
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = get_user(message.from_user.id)
    if user:
        bot.send_message(
            message.chat.id,
            f"👤 Профиль\n\n💰 Кредиты: {user[0]}\n🖼 Генераций: {user[2]}"
        )

# --- РИСОВАТЬ ---
@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def ask_prompt(message):
    user = get_user(message.from_user.id)

    if not user or user[0] <= 0:
        bot.send_message(message.chat.id, "❌ Нет кредитов")
        return

    msg = bot.send_message(
        message.chat.id,
        "Опиши картинку на английском:",
        reply_markup=types.ForceReply()
    )
    bot.register_next_step_handler(msg, process_generation)

def process_generation(message):
    if not message.text:
        return

    user_id = message.from_user.id
    prompt = message.text

    wait_msg = bot.send_message(message.chat.id, "⏳ Генерация...")

    try:
        safe_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"

        response = requests.get(url, timeout=60)

        # --- ЛОГ В ТЕЛЕГРАМ ---
        bot.send_message(
            ADMIN_ID,
            f"DEBUG\nStatus: {response.status_code}\nURL: {url}"
        )

        if response.status_code != 200:
            bot.send_message(
                message.chat.id,
                f"❌ Ошибка API\nStatus: {response.status_code}"
            )
            return

        if not response.content:
            bot.send_message(message.chat.id, "❌ Пустой ответ от сервера")
            return

        bot.send_photo(
            message.chat.id,
            BytesIO(response.content),
            caption=f"📝 {prompt}"
        )

        update_credits(user_id, -1)

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE users SET total_gen = total_gen + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

    except Exception as e:
        # --- ОШИБКА В ТЕЛЕГРАМ ---
        bot.send_message(message.chat.id, f"❌ Ошибка генерации:\n{e}")
        bot.send_message(ADMIN_ID, f"ERROR:\n{e}")

    finally:
        try:
            bot.delete_message(message.chat.id, wait_msg.message_id)
        except:
            pass

# --- RUN ---
if __name__ == "__main__":
    print("Бот запущен")
    bot.infinity_polling()



