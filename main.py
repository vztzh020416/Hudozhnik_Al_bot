import telebot
import sqlite3
import requests
import urllib.parse
import traceback
import time
import random
import base64
import json
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
        full_log = f"🆘 *ОШИБКА В БОТЕ*\n\n{user_info}\n\n`{error_text[:3500]}`"
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
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def is_valid_image(data):
    """Проверяет, что данные - это настоящая картинка (JPEG или PNG)"""
    return (len(data) > 5000 and 
            (data[:2] == b'\xff\xd8' or  # JPEG
             data[:4] == b'\x89PNG'))    # PNG

# ==================== 6 ДВИЖКОВ ГЕНЕРАЦИИ ====================

# --- ДВИЖОК 1: POLLINATIONS (БЕСПЛАТНО) ---
def fetch_pollinations(prompt):
    """Основной бесплатный движок"""
    formats = [
        f"https://pollinations.ai/p/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true&seed={int(time.time())}",
        f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true",
        f"https://pollinations.ai/p/{urllib.parse.quote(prompt)}"
    ]
    for url in formats:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and is_valid_image(r.content):
                return r.content, "Pollinations"
        except:
            continue
    return None, None

# --- ДВИЖОК 2: NANO BANANA (GEMINI 3 PRO - БЕСПЛАТНО ЧЕРЕЗ ПРОКСИ) ---
def fetch_nano_banana(prompt):
    """Nano Banana Pro (Gemini 3 Pro) через бесплатные прокси [citation:3]"""
    try:
        # Используем публичный API от felo.ai (бесплатный, без регистрации)
        url = "https://api.felo.ai/v1/gemini-image-gen"
        headers = {"Content-Type": "application/json"}
        payload = {
            "prompt": prompt,
            "resolution": "2048x2048",
            "model": "gemini-3-pro-image-preview"
        }
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            if 'image' in data:
                img_data = base64.b64decode(data['image'])
                if is_valid_image(img_data):
                    return img_data, "Nano Banana (Gemini 3 Pro)"
    except:
        pass
    return None, None

# --- ДВИЖОК 3: FELO.AI (БЕСПЛАТНО, БЕЗ РЕГИСТРАЦИИ) ---
def fetch_felo(prompt):
    """Бесплатный движок с felo.ai [citation:3]"""
    try:
        url = "https://felo.ai/api/image"
        payload = {
            "prompt": prompt,
            "style": "photorealistic",
            "resolution": "1024x1024"
        }
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            if 'image_url' in data:
                img_r = requests.get(data['image_url'], timeout=15)
                if img_r.status_code == 200 and is_valid_image(img_r.content):
                    return img_r.content, "Felo AI"
    except:
        pass
    return None, None

# --- ДВИЖОК 4: PERCHANCE AI (ЗАПАСНОЙ) ---
def fetch_perchance(prompt):
    """Бесплатный движок генерации"""
    try:
        url = "https://image-generation.perchance.org/api/generate"
        data = {"prompt": prompt, "seed": random.randint(1, 999999)}
        r = requests.post(url, json=data, timeout=30)
        if r.status_code == 200:
            img_data = r.content
            if is_valid_image(img_data):
                return img_data, "Perchance AI"
    except:
        pass
    return None, None

# --- ДВИЖОК 5: PRODIA (БЕСПЛАТНО, СТАБИЛЬНЫЙ) ---
def fetch_prodia(prompt):
    """Бесплатный API через prodia (SDXL)"""
    try:
        # Используем публичный endpoint prodia (есть бесплатный tier)
        url = "https://api.prodia.com/v1/sdxl/generate"
        payload = {
            "prompt": prompt,
            "model": "sd_xl_base_1.0.safetensors",
            "steps": 20,
            "cfg_scale": 7
        }
        headers = {"Content-Type": "application/json"}
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            if 'imageUrl' in data:
                img_r = requests.get(data['imageUrl'], timeout=15)
                if img_r.status_code == 200 and is_valid_image(img_r.content):
                    return img_r.content, "Prodia SDXL"
    except:
        pass
    return None, None

# --- ДВИЖОК 6: GLM-Image (КИТАЙСКАЯ МОДЕЛЬ, БЕСПЛАТНО) ---
def fetch_glm_image(prompt):
    """Китайская модель GLM-Image от Zhipu AI (мировой тренд 2026) [citation:8]"""
    try:
        # Публичный API через Hugging Face (бесплатно)
        url = "https://api-inference.huggingface.co/models/ZhipuAI/GLM-Image"
        headers = {"Content-Type": "application/json"}
        payload = {"inputs": prompt}
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code == 200 and is_valid_image(r.content):
            return r.content, "GLM-Image (Zhipu AI)"
    except:
        pass
    return None, None

# ==================== ОСНОВНАЯ ЛОГИКА ====================

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
    bot.send_message(message.chat.id, "🎨 Привет! Нажми 'Рисовать', чтобы начать. У тебя 57 попыток.", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = get_user(message.from_user.id)
    if user:
        bot.send_message(message.chat.id, f"💰 Кредиты: {user[0]}\n🖼 Всего создано: {user[1]}")
    else:
        bot.send_message(message.chat.id, "👤 Профиль не найден")

@bot.message_handler(func=lambda m: m.text == "🎨 Рисовать")
def draw(message):
    user = get_user(message.from_user.id)
    if not user:
        bot.send_message(message.chat.id, "❌ Ошибка: пользователь не найден")
        return
    if user[0] <= 0:
        bot.send_message(message.chat.id, "❌ Закончились кредиты.")
        return
    
    msg = bot.send_message(message.chat.id, "Опишите картинку (English):", reply_markup=types.ForceReply())
    bot.register_next_step_handler(msg, process_draw)

def process_draw(message):
    if not message.text or message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ Некорректный запрос")
        return
    
    prompt = message.text
    wait_msg = bot.send_message(message.chat.id, "⏳ Пробую движки генерации...")
    
    # Список движков в порядке приоритета
    engines = [
        fetch_pollinations,
        fetch_nano_banana,
        fetch_felo,
        fetch_glm_image,
        fetch_prodia,
        fetch_perchance
    ]
    
    img_data = None
    engine_name = None
    
    for i, engine in enumerate(engines):
        try:
            bot.edit_message_text(f"⏳ Пробую движок {i+1}/{len(engines)}...", message.chat.id, wait_msg.message_id)
            img_data, engine_name = engine(prompt)
            if img_data:
                bot.edit_message_text(f"✅ Движок {engine_name} сработал!", message.chat.id, wait_msg.message_id)
                break
        except Exception as e:
            continue
    
    try:
        if img_data:
            bot.send_photo(message.chat.id, BytesIO(img_data), 
                         caption=f"✨ Готово через {engine_name}!\n📝 {prompt[:50]}...")
            update_credits(message.from_user.id, -1)
            
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET total_gen = total_gen + 1 WHERE user_id = ?", (message.from_user.id,))
            conn.commit()
            conn.close()
        else:
            bot.send_message(message.chat.id, "❌ Все 6 движков не отвечают. Попробуйте позже.")
            send_error_to_admin(f"Все движки не вернули картинку для: {prompt}", message)
    
    except Exception as e:
        error_text = f"Ошибка: {str(e)}\n{traceback.format_exc()}"
        bot.send_message(message.chat.id, "❌ Техническая ошибка. Попробуйте позже.")
        send_error_to_admin(f"{error_text}\n\nPrompt: {prompt}", message)
    
    finally:
        bot.delete_message(message.chat.id, wait_msg.message_id)

if __name__ == "__main__":
    print("🤖 Бот с 6 движками запущен...")
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)
