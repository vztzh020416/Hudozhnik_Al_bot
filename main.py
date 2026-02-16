import telebot
import sqlite3
import requests
import urllib.parse
import logging
import random
import string
from telebot import types
from io import BytesIO
from datetime import datetime

# --- КОНФИГУРАЦИЯ ---
# ВСТАВЬТЕ СЮДА НОВЫЙ ТОКЕН ПОСЛЕ СБРОСА СТАРОГО!
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8" 
ADMIN_ID = 1005217438
DB_NAME = "users.db"
LOG_FILE = "bot.log"

# --- НАСТРОЙКА ЛОГГЕРА ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN)

try:
    bot_username = bot.get_me().username
    logger.info(f"Бот запущен: @{bot_username}")
except Exception as e:
    logger.error(f"Ошибка при запуске (проверьте токен): {e}")
    bot_username = "Bot"

# --- ГЕНЕРАТОР КОДОВ ОШИБОК ---
def generate_error_code():
    return "ERR-" + ''.join(random.choices(string.digits, k=4))

# --- ОТПРАВКА ОШИБКИ ПОЛЬЗОВАТЕЛЮ И АДМИНУ ---
def notify_error(chat_id, exception, context="Неизвестная ошибка"):
    error_code = generate_error_code()
    
    # Сообщение пользователю (вежливое)
    user_msg = f"❌ Произошла ошибка при выполнении операции.\nКод ошибки: `{error_code}`\nПопробуйте позже или напишите администратору."
    try:
        bot.send_message(chat_id, user_msg, parse_mode="Markdown")
    except:
        pass # Если даже сообщение об ошибке не уходит, молчим

    # Сообщение админу (полное)
    admin_msg = (
        f"🚨 **КРИТИЧЕСКАЯ ОШИБКА**\n\n"
        f"🆔 Код: `{error_code}`\n"
        f"👤 User ID: `{chat_id}`\n"
        f"📍 Контекст: {context}\n"
        f"⚠️ Исключение: `{type(exception).__name__}`\n"
        f"📄 Текст: `{str(exception)}`"
    )
    try:
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
    except:
        pass
    
    logger.error(f"[{error_code}] User: {chat_id}, Context: {context}, Error: {exception}")

# --- ИНИЦИАЛИЗАЦИЯ БД ---
def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY, 
                      credits INTEGER DEFAULT 57, 
                      referrer_id INTEGER,
                      total_gen INTEGER DEFAULT 0)''')
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована.")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")

init_db()

# --- ФУНКЦИИ БД ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_user(user_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT credits, referrer_id, total_gen FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"DB Error (get_user): {e}")
        return None

def register_user(user_id, ref_id=None):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, credits, referrer_id) VALUES (?, ?, ?)", (user_id, 57, ref_id))
        if ref_id and c.rowcount > 0: 
            c.execute("UPDATE users SET credits = credits + 1 WHERE user_id = ?", (ref_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB Error (register_user): {e}")

def update_credits(user_id, amount):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB Error (update_credits): {e}")

def increment_gen_count(user_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE users SET total_gen = total_gen + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB Error (increment_gen_count): {e}")

# --- КЛАВИАТУРА ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎨 Рисовать", "👤 Профиль")
    markup.add("👥 Рефералка", "⭐ Купить попытки")
    return markup

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = message.from_user.id
        args = message.text.split()
        
        ref_id = None
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
            if ref_id == user_id: ref_id = None

        register_user(user_id, ref_id)
        
        bot.send_message(user_id, f"🎨 Привет! Я создаю шедевры с помощью ИИ.\nУ тебя есть 57 бесплатных попыток!", reply_markup=main_menu())
        if ref_id:
            try:
                bot.send_message(ref_id, "🔔 У вас новый реферал! +1 кредит зачислен.")
            except: pass
    except Exception as e:
        notify_error(message.chat.id, e, "Command /start")

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    try:
        user = get_user(message.from_user.id)
        if user:
            text = (f"👤 *Ваш профиль*\n\n"
                    f"💰 Кредиты: {user[0]}\n"
                    f"🖼 Всего генераций: {user[2]}")
            bot.send_message(message.chat.id, text, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "Ошибка загрузки профиля.")
    except Exception as e:
        notify_error(message.chat.id, e, "Menu Profile")

@bot.message_handler(func=lambda m: m.text == "👥 Рефералка")
def referral(message):
    try:
        link = f"https://t.me/{bot_username}?start={message.from_user.id}"
        bot.send_message(message.chat.id, f"👥 Приглашай друзей и получай **1 кредит** за каждого!\n\nТвоя ссылка:\n`{link}`", parse_mode="Markdown")
    except Exception as e:
        notify_error(message.chat.id, e, "Menu Referral")

@bot.message_handler(func=lambda m: m.text == "⭐ Купить попытки")
def shop(message):
    try:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("5 попыток — 5 ⭐", callback_data="buy_5"))
        markup.add(types.InlineKeyboardButton("12 попыток — 10 ⭐", callback_data="buy_10"))
        markup.add(types.InlineKeyboardButton("35 попыток — 25 ⭐", callback_data="buy_25"))
        markup.add(types.InlineKeyboardButton("75 попыток — 50 ⭐", callback_data="buy_50"))
        bot.send_message(message.chat.id, "Выберите пакет кредитов:", reply_markup=markup)
    except Exception as e:
        notify_error(message.chat.id, e, "Menu Shop")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    try:
        prices = {"buy_5": 5, "buy_10": 10, "buy_25": 25, "buy_50": 50}
        credits_map = {"buy_5": 5, "buy_10": 12, "buy_25": 35, "buy_50": 75}
        
        amount = prices[call.data]
        # Для Telegram Stars provider_token не нужен (оставляем пустым)
        bot.send_invoice(
            call.message.chat.id,
            title="Пополнение баланса",
            description=f"Покупка {credits_map[call.data]} кредитов для генерации",
            invoice_payload=f"pay_{credits_map[call.data]}",
            provider_token="", 
            currency="XTR",
            prices=[types.LabeledPrice(label="Кредиты", amount=amount)]
        )
    except Exception as e:
        notify_error(call.message.chat.id, e, "Callback Buy")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    try:
        amount = int(message.successful_payment.invoice_payload.split('_')[1])
        update_credits(message.from_user.id, amount)
        bot.send_message(message.chat.id, f"✅ Оплата успешна! Начислено {amount} кредитов.")
    except Exception as e:
        notify_error(message.chat.id, e, "Payment Success")

@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def ask_prompt(message):
    try:
        user = get_user(message.from_user.id)
        if not user or user[0] <= 0:
            bot.send_message(message.chat.id, "❌ У вас закончились кредиты. Пригласите друга или купите попытки.")
            return
        msg = bot.send_message(message.chat.id, "Опишите, что вы хотите увидеть (лучше на английском):", reply_markup=types.ForceReply())
        bot.register_next_step_handler(msg, process_generation)
    except Exception as e:
        notify_error(message.chat.id, e, "Menu Draw")

def process_generation(message):
    if not message.text or message.text.startswith('/'): return
    
    user_id = message.from_user.id
    prompt = message.text
    
    # Проверка кредитов еще раз (защита от гонки)
    user = get_user(user_id)
    if not user or user[0] <= 0:
        bot.send_message(message.chat.id, "❌ Кредиты закончились во время ожидания.")
        return

    wait_msg = bot.send_message(message.chat.id, "⏳ Генерирую шедевр...")
    
    try:
        safe_prompt = urllib.parse.quote(prompt)
        # ИСПРАВЛЕНО: убраны пробелы в URL
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true&seed={random.randint(1, 9999)}"
        
        response = requests.get(url, timeout=60)
        
        if response.status_code == 200 and len(response.content) > 0:
            bot.send_photo(
                message.chat.id, 
                BytesIO(response.content), 
                caption=f"📝 {prompt}\n\nСоздано в @{bot_username}",
                reply_markup=main_menu()
            )
            update_credits(user_id, -1)
            increment_gen_count(user_id)
        else:
            raise Exception(f"API Status: {response.status_code}")
            
    except Exception as e:
        notify_error(message.chat.id, e, f"Generation: {prompt[:20]}")
    finally:
        try:
            bot.delete_message(message.chat.id, wait_msg.message_id)
        except: pass

# --- АДМИН-КОМАНДЫ И ТЕСТЫ ---

@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id == ADMIN_ID:
        try:
            conn = get_db_connection()
            c = conn.cursor()
            users_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_gen = c.execute("SELECT SUM(total_gen) FROM users").fetchone()[0]
            conn.close()
            bot.send_message(ADMIN_ID, f"📊 *Статистика бота*\n\n👤 Пользователей: {users_count}\n🖼 Всего генераций: {total_gen or 0}", parse_mode="Markdown")
        except Exception as e:
            notify_error(ADMIN_ID, e, "Admin Stats")

@bot.message_handler(commands=['add_credits'])
def add_credits_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        args = message.text.split()
        if len(args) < 3:
            bot.send_message(message.chat.id, "⚠️ Формат: `/add_credits ID 10`", parse_mode="Markdown")
            return
        target_id = int(args[1])
        amount = int(args[2])
        update_credits(target_id, amount)
        bot.send_message(message.chat.id, f"✅ Добавлено {amount} кредитов пользователю `{target_id}`.", parse_mode="Markdown")
        bot.send_message(target_id, f"🎁 Вам начислено {amount} бесплатных генераций!")
    except Exception as e:
        notify_error(ADMIN_ID, e, "Admin Add Credits")

@bot.message_handler(commands=['my_id'])
def get_my_id(message):
    bot.send_message(message.chat.id, f"Ваш ID: `{message.from_user.id}`", parse_mode="Markdown")

@bot.message_handler(commands=['ping'])
def ping_command(message):
    bot.send_message(message.chat.id, "🏓 Понг! Бот работает.")

@bot.message_handler(commands=['test_db'])
def test_db_command(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT 1")
        conn.close()
        bot.send_message(message.chat.id, "✅ База данных работает корректно.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка БД: {e}")
        notify_error(ADMIN_ID, e, "Test DB")

@bot.message_handler(commands=['test_api'])
def test_api_command(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        url = "https://image.pollinations.ai/prompt/test?width=100&height=100"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            bot.send_message(message.chat.id, "✅ Связь с Pollinations AI установлена.")
        else:
            bot.send_message(message.chat.id, f"❌ Ошибка API: {r.status_code}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка сети: {e}")
        notify_error(ADMIN_ID, e, "Test API")

if __name__ == "__main__":
    logger.info("Запуск polling...")
    bot.infinity_polling()
