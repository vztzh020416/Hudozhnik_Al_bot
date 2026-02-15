import telebot
import sqlite3
import requests
import urllib.parse
from telebot import types
from io import BytesIO

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
ADMIN_ID = 1005217438  # Замените на ваш реальный ID, если он отличается
DB_NAME = "users.db"

bot = telebot.TeleBot(TOKEN)
bot_username = bot.get_me().username

# --- ИНИЦИАЛИЗАЦИЯ БД ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  credits INTEGER DEFAULT 3, 
                  referrer_id INTEGER,
                  total_gen INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# --- ФУНКЦИИ БД ---
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
    c.execute("INSERT OR IGNORE INTO users (user_id, credits, referrer_id) VALUES (?, ?, ?)", (user_id, 3, ref_id))
    if ref_id and c.rowcount > 0: # Если юзер новый и есть реферер
        c.execute("UPDATE users SET credits = credits + 1 WHERE user_id = ?", (ref_id,))
    conn.commit()
    conn.close()

def update_credits(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- КЛАВИАТУРА ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎨 Рисовать", "👤 Профиль")
    markup.add("👥 Рефералка", "⭐ Купить попытки")
    return markup

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    ref_id = None
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
        if ref_id == user_id: ref_id = None

    register_user(user_id, ref_id)
    
    bot.send_message(user_id, f"🎨 Привет! Я создаю шедевры с помощью ИИ.\nУ тебя есть 3 бесплатные попытки!", reply_markup=main_menu())
    if ref_id:
        try:
            bot.send_message(ref_id, "🔔 У вас новый реферал! +1 кредит зачислен.")
        except: pass

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = get_user(message.from_user.id)
    text = (f"👤 *Ваш профиль*\n\n"
            f"💰 Кредиты: {user[0]}\n"
            f"🖼 Всего генераций: {user[2]}")
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👥 Рефералка")
def referral(message):
    link = f"https://t.me/{bot_username}?start={message.from_user.id}"
    bot.send_message(message.chat.id, f"👥 Приглашай друзей и получай **1 кредит** за каждого!\n\nТвоя ссылка:\n`{link}`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "⭐ Купить попытки")
def shop(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("5 попыток — 5 ⭐", callback_data="buy_5"))
    markup.add(types.InlineKeyboardButton("12 попыток — 10 ⭐", callback_data="buy_10"))
    markup.add(types.InlineKeyboardButton("35 попыток — 25 ⭐", callback_data="buy_25"))
    markup.add(types.InlineKeyboardButton("75 попыток — 50 ⭐", callback_data="buy_50"))
    bot.send_message(message.chat.id, "Выберите пакет кредитов:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    prices = {"buy_5": 5, "buy_10": 10, "buy_25": 25, "buy_50": 50}
    credits = {"buy_5": 5, "buy_10": 12, "buy_25": 35, "buy_50": 75}
    
    amount = prices[call.data]
    bot.send_invoice(
        call.message.chat.id,
        title="Пополнение баланса",
        description=f"Покупка {credits[call.data]} кредитов для генерации",
        invoice_payload=f"pay_{credits[call.data]}",
        provider_token="", # Для Telegram Stars оставляем пустым
        currency="XTR",
        prices=[types.LabeledPrice(label="Кредиты", amount=amount)]
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    amount = int(message.successful_payment.invoice_payload.split('_')[1])
    update_credits(message.from_user.id, amount)
    bot.send_message(message.chat.id, f"✅ Оплата успешна! Начислено {amount} кредитов.")

@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def ask_prompt(message):
    user = get_user(message.from_user.id)
    if user[0] <= 0:
        bot.send_message(message.chat.id, "❌ У вас закончились кредиты. Пригласите друга или купите попытки.")
        return
    msg = bot.send_message(message.chat.id, "Опишите, что вы хотите увидеть (на английском):", reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_generation)

def process_generation(message):
    if not message.text: return
    user_id = message.from_user.id
    prompt = message.text
    
    wait_msg = bot.send_message(message.chat.id, "⏳ Генерирую шедевр...")
    
    safe_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
    
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            bot.send_photo(
                message.chat.id, 
                BytesIO(response.content), 
                caption=f"📝 {prompt}\n\nСоздано в @{bot_username}",
                reply_markup=main_menu()
            )
            update_credits(user_id, -1)
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET total_gen = total_gen + 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
        else:
            bot.send_message(message.chat.id, "❌ Ошибка сервера. Попробуйте позже.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка: {e}")
    finally:
        bot.delete_message(message.chat.id, wait_msg.message_id)

@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id == ADMIN_ID:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        users_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_gen = c.execute("SELECT SUM(total_gen) FROM users").fetchone()[0]
        conn.close()
        bot.send_message(ADMIN_ID, f"📊 *Статистика бота*\n\n👤 Пользователей: {users_count}\n🖼 Всего генераций: {total_gen or 0}", parse_mode="Markdown")

if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
