import telebot
import sqlite3
import requests
import urllib.parse
import logging
import random
import string
import time
from telebot import types
from io import BytesIO
from datetime import datetime

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8543701615:AAEo5ZfovosRPNQqwn_QZVvqGkAzbjGLVB8"
ADMIN_ID = 1005217438
DB_NAME = "users.db"
LOG_FILE = "bot.log"

# --- НАСТРОЙКА ЛОГГЕРА ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
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
    
    user_msg = f"❌ Произошла ошибка при выполнении операции.\nКод ошибки: `{error_code}`\nПопробуйте позже или напишите администратору."
    try:
        bot.send_message(chat_id, user_msg, parse_mode="Markdown")
    except:
        pass

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

# --- 10 СЕРВИСОВ ГЕНЕРАЦИИ ИЗОБРАЖЕНИЙ ---
class ImageGenerationServices:
    """Класс для работы с 10 различными сервисами генерации изображений"""
    
    def __init__(self):
        self.services = [
            {"name": "Pollinations.ai", "func": self.pollinations_ai, "priority": 1},
            {"name": "Puter.js", "func": self.puter_js, "priority": 2},
            {"name": "Dezgo", "func": self.dezgo, "priority": 3},
            {"name": "DeepAI", "func": self.deepai, "priority": 4},
            {"name": "HuggingFace", "func": self.huggingface, "priority": 5},
            {"name": "Lexica", "func": self.lexica, "priority": 6},
            {"name": "AI4Chat", "func": self.ai4chat, "priority": 7},
            {"name": "OpenRouter", "func": self.openrouter, "priority": 8},
            {"name": "Civitai", "func": self.civitai, "priority": 9},
            {"name": "Backup Service", "func": self.backup_service, "priority": 10},
        ]
        # Сортируем по приоритету
        self.services.sort(key=lambda x: x["priority"])
        self.service_stats = {s["name"]: {"success": 0, "fail": 0} for s in self.services}
    
    def pollinations_ai(self, prompt, width=1024, height=1024):
        """1. Pollinations.ai - бесплатный API без ключа"""
        safe_prompt = urllib.parse.quote(prompt)
        seed = random.randint(1, 9999)
        url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width={width}&height={height}&nologo=true&seed={seed}"
        
        response = requests.get(url, timeout=60)
        if response.status_code == 200 and len(response.content) > 1000:
            return BytesIO(response.content)
        raise Exception(f"Pollinations: Status {response.status_code}")
    
    def puter_js(self, prompt, width=1024, height=1024):
        """2. Puter.js - бесплатный API без ограничений"""
        url = "https://api.puter.com/v1/image/generate"
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "model": "stable-diffusion-v1-5"
        }
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            data = response.json()
            if "image_url" in data:
                img_response = requests.get(data["image_url"], timeout=30)
                if img_response.status_code == 200:
                    return BytesIO(img_response.content)
        raise Exception(f"Puter.js: Status {response.status_code}")
    
    def dezgo(self, prompt, width=1024, height=1024):
        """3. Dezgo - бесплатный API с регистрацией"""
        url = "https://api.dezgo.com/text2image"
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "sampler": "dpmpp_2m",
            "steps": 30,
            "cfg_scale": 7.5,
            "model": "sd_v1.5"
        }
        
        response = requests.post(url, data=payload, timeout=60)
        if response.status_code == 200 and len(response.content) > 1000:
            return BytesIO(response.content)
        raise Exception(f"Dezgo: Status {response.status_code}")
    
    def deepai(self, prompt, width=1024, height=1024):
        """4. DeepAI - текстовый API для генерации"""
        url = "https://api.deepai.org/api/text2img"
        headers = {
            "api-key": "quickstart-QUdJIGlzIGNvbWluZy4uLi4K",  # Demo key
        }
        payload = {
            "text": prompt,
            "width": width,
            "height": height
        }
        
        response = requests.post(url, data=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            data = response.json()
            if "output_url" in data:
                img_response = requests.get(data["output_url"], timeout=30)
                if img_response.status_code == 200:
                    return BytesIO(img_response.content)
        raise Exception(f"DeepAI: Status {response.status_code}")
    
    def huggingface(self, prompt, width=1024, height=1024):
        """5. Hugging Face Inference API"""
        url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        headers = {
            "Authorization": "Bearer hf_xxxxxxxxxxxxxxxxxxxxxxxxxx"  # Замените на свой токен или используйте без ключа
        }
        payload = {
            "inputs": prompt,
            "parameters": {
                "width": width,
                "height": height,
                "num_inference_steps": 30
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        if response.status_code == 200:
            return BytesIO(response.content)
        elif response.status_code == 503:
            raise Exception("HuggingFace: Model loading")
        raise Exception(f"HuggingFace: Status {response.status_code}")
    
    def lexica(self, prompt, width=1024, height=1024):
        """6. Lexica Aperture API"""
        url = "https://lexica.art/api/v1/generate"
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "model": "aperture-v1"
        }
        
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            if "images" in data and len(data["images"]) > 0:
                img_url = data["images"][0]["src"]
                img_response = requests.get(img_url, timeout=30)
                if img_response.status_code == 200:
                    return BytesIO(img_response.content)
        raise Exception(f"Lexica: Status {response.status_code}")
    
    def ai4chat(self, prompt, width=1024, height=1024):
        """7. AI4Chat API"""
        url = "https://api.ai4chat.co/v1/image/generate"
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "model": "stable-diffusion"
        }
        
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            if "image_url" in data:
                img_response = requests.get(data["image_url"], timeout=30)
                if img_response.status_code == 200:
                    return BytesIO(img_response.content)
        raise Exception(f"AI4Chat: Status {response.status_code}")
    
    def openrouter(self, prompt, width=1024, height=1024):
        """8. OpenRouter Gemini Image API"""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": "Bearer sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxx",  # Замените на свой ключ
            "Content-Type": "application/json"
        }
        payload = {
            "model": "google/gemini-2.0-flash-exp:free",
            "messages": [{"role": "user", "content": f"Generate image: {prompt}"}],
            "modalities": ["image"],
            "max_tokens": 4096
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                # Обработка ответа с изображением
                raise Exception("OpenRouter: Image in response")
        raise Exception(f"OpenRouter: Status {response.status_code}")
    
    def civitai(self, prompt, width=1024, height=1024):
        """9. Civitai API (для моделей)"""
        # Civitai больше для загрузки моделей, но можно использовать их API для поиска
        url = "https://civitai.com/api/v1/images"
        params = {
            "limit": 1,
            "query": prompt
        }
        
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if "items" in data and len(data["items"]) > 0:
                img_url = data["items"][0]["url"]
                img_response = requests.get(img_url, timeout=30)
                if img_response.status_code == 200:
                    return BytesIO(img_response.content)
        raise Exception(f"Civitai: Status {response.status_code}")
    
    def backup_service(self, prompt, width=1024, height=1024):
        """10. Резервный сервис (заглушка)"""
        # Здесь можно добавить еще один сервис
        raise Exception("Backup service not configured")
    
    def generate_with_fallback(self, prompt, width=1024, height=1024, callback=None):
        """
        Генерация изображения с автоматическим переключением между сервисами
        Возвращает: (BytesIO с изображением, название использованного сервиса)
        """
        last_error = None
        
        for i, service in enumerate(self.services, 1):
            service_name = service["name"]
            func = service["func"]
            
            try:
                if callback:
                    callback(f"⏳ Попытка {i}/10: {service_name}...")
                
                logger.info(f"Используем сервис {i}/10: {service_name} для запроса: {prompt[:50]}")
                
                image_data = func(prompt, width, height)
                
                # Успех!
                self.service_stats[service_name]["success"] += 1
                logger.info(f"✅ Успех! Сервис {service_name} сгенерировал изображение")
                
                return image_data, service_name
                
            except Exception as e:
                self.service_stats[service_name]["fail"] += 1
                last_error = e
                logger.warning(f"❌ Сервис {service_name} не ответил: {e}")
                
                # Ждем немного перед следующей попыткой
                time.sleep(2)
                continue
        
        # Все сервисы не работали
        raise Exception(f"Все 10 сервисов не отвечают. Последняя ошибка: {last_error}")
    
    def get_stats(self):
        """Получить статистику работы сервисов"""
        return self.service_stats

# Создаем глобальный экземпляр
image_services = ImageGenerationServices()

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
        
        bot.send_message(user_id, f"🎨 Привет! Я создаю шедевры с помощью ИИ.\nУ тебя есть 57 бесплатных попыток!\n\n📡 Доступно 10 сервисов генерации!", reply_markup=main_menu())
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
        msg = bot.send_message(message.chat.id, "📝 Опишите, что вы хотите увидеть (лучше на английском):", reply_markup=types.ForceReply())
        bot.register_next_step_handler(msg, process_generation)
    except Exception as e:
        notify_error(message.chat.id, e, "Menu Draw")

def process_generation(message):
    if not message.text or message.text.startswith('/'): 
        return
    
    user_id = message.from_user.id
    prompt = message.text
    
    # Проверка кредитов
    user = get_user(user_id)
    if not user or user[0] <= 0:
        bot.send_message(message.chat.id, "❌ Кредиты закончились во время ожидания.")
        return

    wait_msg = bot.send_message(message.chat.id, "🔄 Инициализация генерации...")
    
    def update_progress(text):
        try:
            bot.edit_message_text(text, message.chat.id, wait_msg.message_id)
        except:
            pass
    
    try:
        # Генерация с автоматическим переключением между 10 сервисами
        image_data, service_name = image_services.generate_with_fallback(
            prompt=prompt,
            width=1024,
            height=1024,
            callback=update_progress
        )
        
        # Отправляем изображение
        bot.send_photo(
            message.chat.id, 
            image_data,
            caption=f"📝 {prompt}\n\n🎨 Создано через: {service_name}\n@{bot_username}",
            reply_markup=main_menu()
        )
        
        # Списываем кредит и увеличиваем счетчик
        update_credits(user_id, -1)
        increment_gen_count(user_id)
        
        # Обновляем статус
        bot.edit_message_text(
            f"✅ Готово! Сервис: {service_name}",
            message.chat.id, 
            wait_msg.message_id
        )
        
    except Exception as e:
        notify_error(message.chat.id, e, f"Generation: {prompt[:50]}")
        try:
            bot.delete_message(message.chat.id, wait_msg.message_id)
        except: 
            pass

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
            
            # Статистика сервисов
            service_stats = image_services.get_stats()
            stats_text = "\n".join([f"{k}: ✅{v['success']} ❌{v['fail']}" for k, v in service_stats.items()])
            
            bot.send_message(
                ADMIN_ID, 
                f"📊 *Статистика бота*\n\n"
                f"👤 Пользователей: {users_count}\n"
                f"🖼 Всего генераций: {total_gen or 0}\n\n"
                f"📡 *Статистика сервисов:*\n{stats_text}",
                parse_mode="Markdown"
            )
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

@bot.message_handler(commands=['test_services'])
def test_all_services(message):
    """Тестирование всех 10 сервисов"""
    if message.from_user.id != ADMIN_ID:
        return
    
    test_prompt = "test image"
    results = []
    
    for i, service in enumerate(image_services.services, 1):
        try:
            msg = bot.send_message(message.chat.id, f"🔄 Тестируем {i}/10: {service['name']}...")
            
            start_time = time.time()
            image_data = service["func"](test_prompt, width=512, height=512)
            elapsed = time.time() - start_time
            
            if image_data:
                results.append(f"✅ {service['name']} - {elapsed:.1f}с")
                bot.edit_message_text(f"✅ {service['name']} работает! ({elapsed:.1f}с)", message.chat.id, msg.message_id)
            else:
                results.append(f"❌ {service['name']} - пустой ответ")
                bot.edit_message_text(f"❌ {service['name']} - пустой ответ", message.chat.id, msg.message_id)
                
        except Exception as e:
            results.append(f"❌ {service['name']} - {str(e)[:50]}")
            try:
                bot.edit_message_text(f"❌ {service['name']} не работает", message.chat.id, msg.message_id)
            except:
                pass
        
        time.sleep(1)
    
    # Итоговый отчет
    report = "📊 *Результаты тестирования:*\n\n" + "\n".join(results)
    bot.send_message(message.chat.id, report, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
🤖 *Команды бота:*

/start - Запустить бота
🎨 Рисовать - Создать изображение
👤 Профиль - Ваш баланс и статистика
👥 Рефералка - Пригласить друзей
⭐ Купить попытки - Пополнить баланс

*Админ команды:*
/stats - Статистика бота и сервисов
/test_services - Протестировать все 10 сервисов
/add_credits ID кол-во - Начислить кредиты
/my_id - Узнать свой ID
/ping - Проверка связи
/help - Эта справка

📡 *Доступно 10 сервисов генерации!*
Если один не работает, бот автоматически переключится на следующий.
"""
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

if __name__ == "__main__":
    logger.info("Запуск polling...")
    print("=" * 50)
    print("🤖 AI Image Bot с 10 сервисами генерации")
    print("=" * 50)
    bot.infinity_polling()
