import os
import io
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests

# ==========================================
# 1. SOZLAMALAR VA XAVFSIZLIK (Railway Variables)
# ==========================================
TOKEN = os.environ.get('BOT_TOKEN', 'SIZNING_BOT_TOKENINGIZ')
BILLZ_API_KEY = os.environ.get('BILLZ_API_KEY', 'SIZNING_API_KALITINGIZ')
BILLZ_API_URL = 'https://billzuz.notion.site/API-c2f91aa254f94f8eb7c1b26415dcb25b' # Billz API manzili (hujjatga qarab o'zgarishi mumkin)

# Ruxsat etilgan xodimlar ro'yxati (Whitelist)
allowed_users_str = os.environ.get('ALLOWED_USERS', '') 
ALLOWED_USERS = [int(uid.strip()) for uid in allowed_users_str.split(',') if uid.strip().isdigit()]

bot = telebot.TeleBot(TOKEN)
user_drafts = {} # Xodimlarning vaqtinchalik ma'lumotlari

# Himoya qatlami (Faqat ruxsati borlar uchun)
def is_allowed(message):
    if message.chat.id not in ALLOWED_USERS:
        bot.send_message(message.chat.id, "⛔️ Kechirasiz, siz ushbu ombor tizimidan foydalanish huquqiga ega emassiz.")
        return False
    return True

# ==========================================
# 2. BILLZ API BILAN ISHLASH FUNKSIYALARI
# ==========================================
def get_categories():
    headers = {'Authorization': f'Bearer {BILLZ_API_KEY}'}
    try:
        # Haqiqiy so'rov: response = requests.get(f'{BILLZ_API_URL}/categories', headers=headers)
        # return [cat['name'] for cat in response.json()]
        return ["Kabellar", "Avtomatlar", "Rozetkalar", "Lampalar"] # Vaqtinchalik namuna
    except Exception:
        return []

def create_category_in_billz(category_name):
    headers = {'Authorization': f'Bearer {BILLZ_API_KEY}'}
    # requests.post(f'{BILLZ_API_URL}/categories', json={'name': category_name}, headers=headers)
    return True

def download_image(url):
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code == 200:
            return io.BytesIO(response.content)
    except Exception:
        pass
    return None

def send_to_billz(draft):
    # Bu yerda Billz API'ga tayyorlangan ma'lumot jo'natiladi
    headers = {'Authorization': f'Bearer {BILLZ_API_KEY}'}
    
    payload = {
        'barcode': draft['barcode'],
        'name': draft.get('full_name', draft['name']),
        'category': draft['category'],
        'cost_price': draft['cost_price'],
        'retail_price': draft['retail_price'],
        'wholesale_price': draft['wholesale_price'],
        'stock': draft['quantity'],
        'min_stock': 5
    }
    
    # Rasm bo'lsa uni ham fayl sifatida qo'shib jo'natamiz
    files = None
    if draft.get('image_stream'):
        files = {'image': ('product.jpg', draft['image_stream'], 'image/jpeg')}
        
    # requests.post(f'{BILLZ_API_URL}/products', data=payload, files=files, headers=headers)
    return True # Hozircha doim "muvaffaqiyatli" qaytaradi

# ==========================================
# 3. BOT MANTIG'I (ZANJIR)
# ==========================================
@bot.message_handler(commands=['start', 'cancel'])
def start(message):
    if not is_allowed(message): return
    bot.send_message(message.chat.id, "📦 Ombor tizimi faol!\n\nMahsulot SHTRIX KODINI kiriting yoki skaner qiling (bekor qilish uchun /cancel):")
    bot.register_next_step_handler(message, process_barcode)

def process_barcode(message):
    if message.text == '/cancel': return start(message)
    
    chat_id = message.chat.id
    # Agar variatsiya kiritilayotgan bo'lsa, eskisini saqlab qolamiz
    if chat_id in user_drafts and user_drafts[chat_id].get('is_variation'):
        user_drafts[chat_id]['barcode'] = message.text
        msg = bot.send_message(chat_id, f"Asosiy nom: *{user_drafts[chat_id]['name']}*\nO'lcham/Rang (Variatsiya) ni kiriting (masalan: 2*4,0):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_variation_name)
    else:
        user_drafts[chat_id] = {'barcode': message.text, 'is_variation': False}
        categories = get_categories()
        markup = InlineKeyboardMarkup()
        for cat in categories[:10]: # Ekranga sig'ishi uchun 10 ta
            markup.add(InlineKeyboardButton(cat, callback_data=f"cat_{cat}"))
        markup.add(InlineKeyboardButton("➕ Yangi katalog", callback_data="add_cat"))
        bot.send_message(chat_id, "Katalogni tanlang yoki yangi qo'shing:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_') or call.data == 'add_cat')
def process_category(call):
    chat_id = call.message.chat.id
    if call.data == 'add_cat':
        msg = bot.edit_message_text("Yangi katalog nomini yozing:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, create_custom_category)
    else:
        category = call.data.split('_')[1]
        user_drafts[chat_id]['category'] = category
        msg = bot.edit_message_text(f"Katalog: {category}\n\nMahsulotning ASOSIY NOMINI kiriting:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, process_name)

def create_custom_category(message):
    new_cat = message.text
    create_category_in_billz(new_cat)
    user_drafts[message.chat.id]['category'] = new_cat
    msg = bot.send_message(message.chat.id, f"✅ Katalog yaratildi.\n\nMahsulotning ASOSIY NOMINI kiriting:")
    bot.register_next_step_handler(msg, process_name)

def process_name(message):
    user_drafts[message.chat.id]['name'] = message.text
    user_drafts[message.chat.id]['full_name'] = message.text # Variatsiya bo'lmasa, shu qoladi
    msg = bot.send_message(message.chat.id, "Kelish narxini kiriting (faqat raqam):")
    bot.register_next_step_handler(msg, process_price)

def process_variation_name(message):
    chat_id = message.chat.id
    variation = message.text
    # Asosiy nom bilan variatsiyani qo'shamiz
    user_drafts[chat_id]['full_name'] = f"{user_drafts[chat_id]['name']} {variation}"
    msg = bot.send_message(chat_id, "Kelish narxini kiriting (faqat raqam):")
    bot.register_next_step_handler(msg, process_price)

def process_price(message):
    chat_id = message.chat.id
    try:
        cost = float(message.text.replace(',', '.'))
        user_drafts[chat_id]['cost_price'] = cost
        user_drafts[chat_id]['retail_price'] = round(cost * 1.30, 2)   # Chakana +30%
        user_drafts[chat_id]['wholesale_price'] = round(cost * 1.15, 2) # Optom +15%
        
        msg = bot.send_message(chat_id, "Do'konda nechta (yoki necha metr) qoldi? (Faqat raqam):")
        bot.register_next_step_handler(msg, process_quantity)
    except ValueError:
        msg = bot.send_message(chat_id, "❌ Xato. Narxni faqat raqamda kiriting:")
        bot.register_next_step_handler(msg, process_price)

def process_quantity(message):
    chat_id = message.chat.id
    try:
        user_drafts[chat_id]['quantity'] = float(message.text.replace(',', '.'))
        msg = bot.send_message(chat_id, "Rasm linkini tashlang (Internetdan nusxalangan) yoki 'yoq' deb yozing:")
        bot.register_next_step_handler(msg, process_image)
    except ValueError:
        msg = bot.send_message(chat_id, "❌ Xato. Soni/metrini raqamda kiriting:")
        bot.register_next_step_handler(msg, process_quantity)

def process_image(message):
    chat_id = message.chat.id
    if message.text.lower() not in ['yoq', "yo'q", 'net', 'no']:
        bot.send_message(chat_id, "Rasm yuklab olinmoqda... Kuting ⏳")
        img_stream = download_image(message.text)
        if img_stream:
            user_drafts[chat_id]['image_stream'] = img_stream
            bot.send_message(chat_id, "✅ Rasm muvaffaqiyatli saqlandi!")
        else:
            bot.send_message(chat_id, "❌ Rasmni yuklab olish imkonsiz bo'ldi. Rasm tizimga kirmaydi.")
            user_drafts[chat_id]['image_stream'] = None
    else:
        user_drafts[chat_id]['image_stream'] = None
        
    show_draft(chat_id)

def show_draft(chat_id):
    draft = user_drafts[chat_id]
    text = (
        f"📋 **MA'LUMOTLARNI TASDIQLANG:**\n\n"
        f"🔢 Shtrix kod: {draft['barcode']}\n"
        f"📂 Katalog: {draft['category']}\n"
        f"🏷 Nomi: {draft.get('full_name', draft['name'])}\n"
        f"💰 Kelish narxi: {draft['cost_price']}\n"
        f"💳 Chakana narx (+30%): {draft['retail_price']}\n"
        f"🤝 Optom narx (+15%): {draft['wholesale_price']}\n"
        f"📦 Qoldiq: {draft['quantity']}\n"
    )
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Billzga yuklash", callback_data="confirm"))
    markup.add(InlineKeyboardButton("❌ Boshidan boshlash", callback_data="restart"))
    
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ['confirm', 'restart'])
def final_action(call):
    chat_id = call.message.chat.id
    if call.data == 'restart':
        bot.delete_message(chat_id, call.message.message_id)
        return start(call.message)
        
    if call.data == 'confirm':
        bot.edit_message_text("Ma'lumotlar Billzga yuborilmoqda... ⏳", chat_id, call.message.message_id)
        
        # API orqali jo'natish funksiyasi chaqiriladi
        success = send_to_billz(user_drafts[chat_id])
        
        if success:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("Yangi mahsulot", callback_data="restart"))
            markup.add(InlineKeyboardButton("Yana shu turdan (Variatsiya)", callback_data="variation"))
            bot.send_message(chat_id, "✅ MUVAFFAQIYATLI YUKLANDI! \n\nKeyingi qadamni tanlang:", reply_markup=markup)
        else:
            bot.send_message(chat_id, "❌ Billz bilan ulanishda xatolik yuz berdi. Dasturchi bilan bog'laning.")

@bot.callback_query_handler(func=lambda call: call.data == 'variation')
def start_variation(call):
    chat_id = call.message.chat.id
    user_drafts[chat_id]['is_variation'] = True
    bot.edit_message_text(f"Katalog: {user_drafts[chat_id]['category']}\nAsosiy nom: {user_drafts[chat_id]['name']}\n\nO'zgarishlar eslab qolindi. Yangi SHTRIX KODNI kiriting:", chat_id, call.message.message_id)
    bot.register_next_step_handler(call.message, process_barcode)

bot.polling(none_stop=True)
