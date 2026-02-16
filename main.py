import telebot
import sqlite3
import requests
import urllib.parse
from telebot import types
from io import BytesIO

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
ADMIN_ID = 1005217438
DB_NAME = "users.db"

# Французский прокси (пример, можешь заменить на свой)
PROXIES = {
    "http": "http://51.159.66.58:3128",
    "https": "http://51.159.66.58:3128"
}

# 10 fallback-вариантов Pollinations
GENERATORS = [
    "https://image.pollinations.ai/prompt/{p}?width=1024&height=1024&nologo=true",
    "https://image.pollinations.ai/prompt/{p}?width=768&height=768&nologo=true",
    "https://image.pollinations.ai/prompt/{p}?width=1024&height=768&nologo=true",
    "https://image.pollinations.ai/prompt/{p}?width=768&height=1024&nologo=true",
    "https://image.pollinations.ai/prompt/{p}?width=896&height=1152&nologo=true",
    "https://image.pollinations.ai/prompt/{p}?width=1152&height=896&nologo=true",
    "https://image.pollinations.ai/prompt/{p}?width=640&height=640&nologo=true",
    "https://image.pollinations.ai/prompt/{p}?width=512&height=768&nologo=true",
    "https://image.pollinations.ai/prompt/{p}?width=768&height=512&nologo=true",
    "https://image.pollinations.ai/prompt/{p}?width=1024&height=576&nologo=true",
]

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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT credits, referrer_id, total_gen FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def register_user(user_id, ref_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, credits, referrer_id) VALUES (?, 57, ?)", (user_id, ref_id))
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

# --- КЛАВИАТУРА ---
def main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # ВАЖНО: текст кнопки ДОЛЖЕН совпадать с обработчиком
    m.add("🎨 Рисовать", "👤 Профиль")
    m.add("👥 Рефералка", "⭐ Купить попытки")
    return m

# --- FALLBACK-ГЕНЕРАЦИЯ ---
def generate_image(prompt: str):
    safe = urllib.parse.quote(prompt)

    for idx, template in enumerate(GENERATORS, start=1):
        url = template.format(p=safe)
        try:
            print(f"[GEN {idx}] Запрос: {url}")
            # Увеличил timeout до 90 секунд
            r = requests.get(url, timeout=90, proxies=PROXIES)

            print(f"[GEN {idx}] Статус: {r.status_code} {r.reason}")

            if r.status_code == 200 and r.content and len(r.content) > 1000:
                return r.content

        except Exception as e:
            print(f"[GEN {idx}] Ошибка: {type(e).__name__}: {e}")

    return None

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()

    ref = None
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
        if ref_id != user_id:
            ref = ref_id

    register_user(user_id, ref)

    bot.send_message(
        user_id,
        "🎨 Привет! Я создаю шедевры с помощью ИИ.\nУ тебя есть 57 бесплатных попыток!",
        reply_markup=main_menu()
    )

    if ref:
        try:
            bot.send_message(ref, "🔔 У вас новый реферал! +1 кредит зачислен.")
        except:
            pass

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    u = get_user(message.from_user.id)
    if not u:
        bot.send_message(message.chat.id, "❌ Профиль не найден.")
        return
    bot.send_message(
        message.chat.id,
        f"👤 *Ваш профиль*\n\n💰 Кредиты: {u[0]}\n🖼 Всего генераций: {u[2]}",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "👥 Рефералка")
def ref(message):
    link = f"https://t.me/{bot_username}?start={message.from_user.id}"
    bot.send_message(
        message.chat.id,
        f"👥 Приглашай друзей и получай **1 кредит** за каждого!\n\nТвоя ссылка:\n`{link}`",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "⭐ Купить попытки")
def shop(message):
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("5 попыток — 5 ⭐", callback_data="buy_5"))
    m.add(types.InlineKeyboardButton("12 попыток — 10 ⭐", callback_data="buy_10"))
    m.add(types.InlineKeyboardButton("35 попыток — 25 ⭐", callback_data="buy_25"))
    m.add(types.InlineKeyboardButton("75 попыток — 50 ⭐", callback_data="buy_50"))
    bot.send_message(message.chat.id, "Выберите пакет кредитов:", reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def buy(call):
    prices = {"buy_5": 5, "buy_10": 10, "buy_25": 25, "buy_50": 50}
    credits = {"buy_5": 5, "buy_10": 12, "buy_25": 35, "buy_50": 75}

    bot.send_invoice(
        call.message.chat.id,
        title="Пополнение баланса",
        description=f"Покупка {credits[call.data]} кредитов для генерации",
        invoice_payload=f"pay_{credits[call.data]}",
        provider_token="",  # сюда вставь реальный provider_token, если будешь подключать оплату
        currency="XTR",
        prices=[types.LabeledPrice("Кредиты", prices[call.data])]
    )

@bot.pre_checkout_query_handler(func=lambda q: True)
def checkout(q):
    bot.answer_pre_checkout_query(q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def paid(message):
    amount = int(message.successful_payment.invoice_payload.split('_')[1])
    update_credits(message.from_user.id, amount)
    bot.send_message(message.chat.id, f"✅ Оплата успешна! Начислено {amount} кредитов.")

# --- ВАЖНО: ОБРАБОТЧИК КНОПКИ "🎨 Рисовать" ---
@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def ask(message):
    print("Нажата кнопка Рисовать:", repr(message.text))
    u = get_user(message.from_user.id)
    if not u or u[0] <= 0:
        bot.send_message(message.chat.id, "❌ У вас закончились кредиты. Пригласите друга или купите попытки.")
        return

    msg = bot.send_message(
        message.chat.id,
        "Опишите, что вы хотите увидеть (на английском):",
        reply_markup=types.ForceReply()
    )
    bot.register_next_step_handler(msg, process_generation)

def process_generation(message):
    if not message.text or message.text.startswith('/'):
        return

    user_id = message.from_user.id
    prompt = message.text

    print("process_generation START:", repr(prompt))

    wait = bot.send_message(message.chat.id, "⏳ Генерирую шедевр... (это может занять до 1–2 минут)")

    try:
        img = generate_image(prompt)

        if img:
            bot.send_photo(
                message.chat.id,
                BytesIO(img),
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
            bot.send_message(
                message.chat.id,
                "❌ Все генераторы недоступны или вернули пустой ответ.\n"
                "Возможно, сервис временно недоступен или регион ограничен."
            )

    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Произошла ошибка: {type(e).__name__}\n{e}"
        )

    finally:
        try:
            bot.delete_message(message.chat.id, wait.message_id)
        except:
            pass

# --- АДМИН-КОМАНДЫ ---

@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    users_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_gen = c.execute("SELECT SUM(total_gen) FROM users").fetchone()[0]
    conn.close()
    bot.send_message(
        ADMIN_ID,
        f"📊 *Статистика бота*\n\n👤 Пользователей: {users_count}\n🖼 Всего генераций: {total_gen or 0}",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['add_credits'])
def add_credits_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещен.")
        return

    try:
        args = message.text.split()
        if len(args) < 3:
            bot.send_message(message.chat.id, "⚠️ Формат: `/add_credits ID 10`", parse_mode="Markdown")
            return

        target_id = int(args[1])
        amount = int(args[2])

        update_credits(target_id, amount)
        bot.send_message(
            message.chat.id,
            f"✅ Добавлено {amount} кредитов пользователю `{target_id}`.",
            parse_mode="Markdown"
        )
        bot.send_message(target_id, f"🎁 Вам начислено {amount} бесплатных генераций!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

# --- ЗАПУСК ---
if __name__ == "__main__":
    print("Бот успешно запущен...")
    bot.infinity_polling()
