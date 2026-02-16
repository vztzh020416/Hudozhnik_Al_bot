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
                  credits INTEGER DEFAULT 100,
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
    # ВСЕ НОВЫЕ ПОЛЬЗОВАТЕЛИ ПОЛУЧАЮТ 100 КРЕДИТОВ
    c.execute("INSERT OR IGNORE INTO users (user_id, credits, referrer_id) VALUES (?, 100, ?)", (user_id, ref_id))
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
    m.add("🎨 Рисовать", "👤 Профиль")
    m.add("👥 Рефералка", "⭐ Купить попытки")
    return m

# --- FALLBACK-ГЕНЕРАЦИЯ С ВОЗВРАТОМ ОШИБКИ ---
def generate_image(prompt: str):
    safe = urllib.parse.quote(prompt)
    last_error = "нет ответа от сервисов"

    for idx, template in enumerate(GENERATORS, start=1):
        url = template.format(p=safe)
        try:
            print(f"[GEN {idx}] Запрос: {url}")
            # Делаем разумный timeout, чтобы не висело вечно
            r = requests.get(url, timeout=40, proxies=PROXIES)

            print(f"[GEN {idx}] Статус: {r.status_code} {r.reason}")

            if r.status_code == 200 and r.content and len(r.content) > 1000:
                return r.content, None
            else:
                last_error = f"HTTP {r.status_code} {r.reason}"

        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            print(f"[GEN {idx}] Ошибка: {last_error}")

    return None, last_error

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()

    ref = None
    if len(args) > 1 and args[1].isdigit() and int(args[1]) != user_id:
        ref = int(args[1])

    register_user(user_id, ref)

    bot.send_message(
        user_id,
        "🎨 Привет! Я создаю шедевры с помощью ИИ.\nУ тебя есть 100 бесплатных попыток!",
        reply_markup=main_menu()
    )

    if ref:
        try:
            bot.send_message(ref, "🔔 Новый реферал! +1 кредит.")
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
        f"👤 *Ваш профиль*\n\n💰 Кредиты: {u[0]}\n🖼 Генераций: {u[2]}",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "👥 Рефералка")
def ref(message):
    link = f"https://t.me/{bot_username}?start={message.from_user.id}"
    bot.send_message(
        message.chat.id,
        f"👥 Приглашай друзей!\nТвоя ссылка:\n`{link}`",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "⭐ Купить попытки")
def shop(message):
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("5 попыток — 5 ⭐", callback_data="buy_5"))
    m.add(types.InlineKeyboardButton("12 попыток — 10 ⭐", callback_data="buy_10"))
    m.add(types.InlineKeyboardButton("35 попыток — 25 ⭐", callback_data="buy_25"))
    m.add(types.InlineKeyboardButton("75 попыток — 50 ⭐", callback_data="buy_50"))
    bot.send_message(message.chat.id, "Выберите пакет:", reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def buy(call):
    prices = {"buy_5": 5, "buy_10": 10, "buy_25": 25, "buy_50": 50}
    credits = {"buy_5": 5, "buy_10": 12, "buy_25": 35, "buy_50": 75}

    bot.send_invoice(
        call.message.chat.id,
        title="Пополнение",
        description=f"{credits[call.data]} кредитов",
        invoice_payload=f"pay_{credits[call.data]}",
        provider_token="",
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
    bot.send_message(message.chat.id, f"✅ Успешно! +{amount} кредитов.")

@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def ask(message):
    u = get_user(message.from_user.id)
    if not u or u[0] <= 0:
        bot.send_message(message.chat.id, "❌ Нет кредитов.")
        return

    msg = bot.send_message(message.chat.id, "Опиши, что нарисовать (EN):", reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process)

def process(message):
    if not message.text or message.text.startswith('/'):
        return

    prompt = message.text
    user_id = message.from_user.id

    wait = bot.send_message(message.chat.id, "⏳ Генерация... (до ~40 секунд)")

    try:
        img, err = generate_image(prompt)

        if img:
            bot.send_photo(
                message.chat.id,
                BytesIO(img),
                caption=f"📝 {prompt}\nСоздано в @{bot_username}",
                reply_markup=main_menu()
            )

            update_credits(user_id, -1)

            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET total_gen = total_gen + 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
        else:
            # Показываем пользователю причину
            bot.send_message(
                message.chat.id,
                f"❌ Генерация не удалась.\nПричина: {err or 'неизвестно'}"
            )
            # И шлём админу подробности
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"⚠️ Ошибка генерации у пользователя {user_id}.\nПромпт: {prompt}\nОшибка: {err}"
                )
            except:
                pass

    except Exception as e:
        err_text = f"{type(e).__name__}: {e}"
        bot.send_message(message.chat.id, f"❌ Внутренняя ошибка: {err_text}")
        try:
            bot.send_message(
                ADMIN_ID,
                f"🔥 Внутренняя ошибка в process у {user_id}.\nПромпт: {prompt}\nОшибка: {err_text}"
            )
        except:
            pass

    finally:
        try:
            bot.delete_message(message.chat.id, wait.message_id)
        except:
            pass

# --- ЗАПУСК ---
if __name__ == "__main__":
    print("Бот запущен.")
    bot.infinity_polling()
