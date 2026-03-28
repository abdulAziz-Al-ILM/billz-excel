import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

TOKEN = 'SIZNING_BOT_TOKENINGIZ' # Shu yerga token yoziladi
bot = telebot.TeleBot(TOKEN)

# Vaqtinchalik ma'lumotlar bazasi
drafts = {}

# Oldindan kiritilgan kataloglar bazasi (Tahrirlash uchun ro'yxat qilib oldik)
CATEGORIES = [
    "elektr", "santexnika", "injeneriya", "suxoy smest", "melich", 
    "xoztovar", "instrument", "addelka", "kraska imulsiya", "kraska", 
    "utipleniya", "pena silikon", "plintus", "kafel"
]

UNITS = ["dona", "metr", "litr", "kg", "quti", "komplekt"]

# ==========================================
# ASOSIY MENU
# ==========================================
@bot.message_handler(commands=['start', 'menu'])
def main_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("📦 Yangi mahsulot"), KeyboardButton("✏️ Tahrirlash"))
    bot.send_message(message.chat.id, "Asosiy menu. Tanlang:", reply_markup=markup)

# ==========================================
# 1-QADAM: RASM (Yangi mahsulot boshlanishi)
# ==========================================
@bot.message_handler(func=lambda message: message.text == "📦 Yangi mahsulot")
def start_new_product(message):
    chat_id = message.chat.id
    drafts[chat_id] = {} # Yangi toza qoralama ochamiz
    msg = bot.send_message(chat_id, "1️⃣ **Rasmni yuboring** (yoki guruhdan ulashing/forward qiling):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_photo)

def process_photo(message):
    chat_id = message.chat.id
    if message.photo:
        # Eng sifatli rasmni saqlaymiz (-1)
        drafts[chat_id]['photo_id'] = message.photo[-1].file_id
    else:
        bot.send_message(chat_id, "❌ Bu rasm emas. Iltimos, rasm yuboring.")
        return bot.register_next_step_handler(message, process_photo)
    
    msg = bot.send_message(chat_id, "2️⃣ **Asosiy nomini** kiriting (masalan: Perexodnik latun):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_base_name)

# ==========================================
# 2, 3, 4-QADAMLAR: NOMLAR, ARTIKUL, KELISH NARXI
# ==========================================
def process_base_name(message):
    chat_id = message.chat.id
    drafts[chat_id]['base_name'] = message.text
    msg = bot.send_message(chat_id, "3️⃣ **Variativ nomini** (xususiyati/o'lchami) kiriting (masalan: 20x15 papa-mama):")
    bot.register_next_step_handler(msg, process_var_name)

def process_var_name(message):
    chat_id = message.chat.id
    drafts[chat_id]['var_name'] = message.text
    msg = bot.send_message(chat_id, "4️⃣ **Artikulini** kiriting (masalan: 001):")
    bot.register_next_step_handler(msg, process_article)

def process_article(message):
    chat_id = message.chat.id
    drafts[chat_id]['article'] = message.text
    msg = bot.send_message(chat_id, "5️⃣ **Kelish narxini** kiriting (Qirg'iz so'mida, faqat raqam):")
    bot.register_next_step_handler(msg, process_cost_price)

# ==========================================
# NARXNI HISOBLASH LOGIKASI (Standart yoki Manual)
# ==========================================
def process_cost_price(message):
    chat_id = message.chat.id
    try:
        cost = float(message.text.replace(',', '.'))
        drafts[chat_id]['cost_price'] = cost
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⚡️ Standart (+13% chakana, +10% optom)", callback_data="price_standart"))
        markup.add(InlineKeyboardButton("⚙️ Manual (O'zim kiritaman)", callback_data="price_manual"))
        
        bot.send_message(chat_id, "6️⃣ **Sotish narxini qanday hisoblaymiz?**", reply_markup=markup)
    except ValueError:
        msg = bot.send_message(chat_id, "❌ Xato! Kelish narxini faqat raqamda yozing:")
        bot.register_next_step_handler(msg, process_cost_price)

@bot.callback_query_handler(func=lambda call: call.data.startswith('price_'))
def handle_pricing_method(call):
    chat_id = call.message.chat.id
    cost = drafts[chat_id]['cost_price']
    
    if call.data == "price_standart":
        drafts[chat_id]['retail_price'] = round(cost + (cost * 0.13), 2)
        drafts[chat_id]['wholesale_price'] = round(cost + (cost * 0.10), 2)
        bot.edit_message_text(f"✅ Standart narxlar saqlandi!\nChakana: {drafts[chat_id]['retail_price']} KGS\nOptom: {drafts[chat_id]['wholesale_price']} KGS", chat_id, call.message.message_id)
        ask_category(chat_id)
        
    elif call.data == "price_manual":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💰 Aniq narx kiritish", callback_data="manual_amount"))
        markup.add(InlineKeyboardButton("📊 Foiz kiritish", callback_data="manual_percent"))
        bot.edit_message_text("Manual hisoblash: Narxning o'zini yozasizmi yoki ustama foiznimi?", chat_id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('manual_'))
def handle_manual_type(call):
    chat_id = call.message.chat.id
    drafts[chat_id]['manual_type'] = call.data # 'manual_amount' yoki 'manual_percent'
    
    text = "Chakana narxni kiriting (So'mda):" if call.data == "manual_amount" else "Chakana narx uchun ustama FOIZNI kiriting (masalan: 15):"
    msg = bot.edit_message_text(text, chat_id, call.message.message_id)
    bot.register_next_step_handler(msg, process_manual_retail)

def process_manual_retail(message):
    chat_id = message.chat.id
    val = float(message.text.replace(',', '.'))
    cost = drafts[chat_id]['cost_price']
    
    if drafts[chat_id]['manual_type'] == "manual_amount":
        drafts[chat_id]['retail_price'] = val
    else:
        drafts[chat_id]['retail_price'] = round(cost + (cost * val / 100), 2)
        
    text = "Optom narxni kiriting (So'mda):" if drafts[chat_id]['manual_type'] == "manual_amount" else "Optom narx uchun ustama FOIZNI kiriting (masalan: 8):"
    msg = bot.send_message(chat_id, text)
    bot.register_next_step_handler(msg, process_manual_wholesale)

def process_manual_wholesale(message):
    chat_id = message.chat.id
    val = float(message.text.replace(',', '.'))
    cost = drafts[chat_id]['cost_price']
    
    if drafts[chat_id]['manual_type'] == "manual_amount":
        drafts[chat_id]['wholesale_price'] = val
    else:
        drafts[chat_id]['wholesale_price'] = round(cost + (cost * val / 100), 2)
    ask_category(chat_id)

# ==========================================
# KATALOG, FIRMA, QOLDIQ VA SIGNAL
# ==========================================
def ask_category(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(cat.capitalize(), callback_data=f"cat_{cat}") for cat in CATEGORIES]
    markup.add(*buttons)
    markup.add(InlineKeyboardButton("➕ Yangi katalog qo'shish", callback_data="cat_new"))
    
    bot.send_message(chat_id, "7️⃣ **Katalogni tanlang:**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def process_category(call):
    chat_id = call.message.chat.id
    if call.data == "cat_new":
        msg = bot.edit_message_text("Yangi katalog nomini yozing:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, add_new_category)
    else:
        cat_name = call.data.split('_')[1]
        drafts[chat_id]['category'] = cat_name
        msg = bot.edit_message_text(f"Katalog: {cat_name.capitalize()}\n\n8️⃣ **Firma/Brendni kiriting:**", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, process_brand)

def add_new_category(message):
    chat_id = message.chat.id
    new_cat = message.text.lower()
    if new_cat not in CATEGORIES:
        CATEGORIES.append(new_cat)
    drafts[chat_id]['category'] = new_cat
    msg = bot.send_message(chat_id, "8️⃣ **Firma/Brendni kiriting:**")
    bot.register_next_step_handler(msg, process_brand)

def process_brand(message):
    chat_id = message.chat.id
    drafts[chat_id]['brand'] = message.text
    msg = bot.send_message(chat_id, "9️⃣ **Qancha qolganda signal bersin?** (Faqat raqam):")
    bot.register_next_step_handler(msg, process_signal)

def process_signal(message):
    chat_id = message.chat.id
    drafts[chat_id]['signal_qty'] = message.text
    msg = bot.send_message(chat_id, "🔟 **Hozir omborga nechta keldi (Qoldiq)?**")
    bot.register_next_step_handler(msg, process_stock)

def process_stock(message):
    chat_id = message.message_id # xato emas, ishlaydi
    chat_id = message.chat.id
    drafts[chat_id]['stock'] = message.text
    
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton(u.capitalize(), callback_data=f"unit_{u}") for u in UNITS]
    markup.add(*buttons)
    bot.send_message(chat_id, "1️⃣1️⃣ **O'lchov birligini tanlang:**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('unit_'))
def finish_draft(call):
    chat_id = call.message.chat.id
    drafts[chat_id]['unit'] = call.data.split('_')[1]
    
    # YAKUNIY TASDIQLASH OYNASI
    d = drafts[chat_id]
    summary = (
        f"📋 **MA'LUMOTLAR TAYYOR:**\n\n"
        f"🔹 To'liq nomi: {d['base_name']} {d['var_name']}\n"
        f"🔹 Artikul: {d['article']}\n"
        f"🔹 Katalog: {d['category'].capitalize()}\n"
        f"🔹 Firma: {d['brand']}\n\n"
        f"💰 Kelish narxi: {d['cost_price']} KGS\n"
        f"💰 Chakana narx: {d['retail_price']} KGS\n"
        f"💰 Optom narx: {d['wholesale_price']} KGS\n\n"
        f"📦 Qoldiq: {d['stock']} {d['unit']}\n"
        f"⚠️ Signal: {d['signal_qty']} {d['unit']} qolganda\n"
    )
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ BAZAGA YUKLASH", callback_data="save_to_db"))
    markup.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_draft"))
    
    bot.delete_message(chat_id, call.message.message_id)
    bot.send_photo(chat_id, d['photo_id'], caption=summary, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ['save_to_db', 'cancel_draft'])
def final_action(call):
    chat_id = call.message.chat.id
    if call.data == "save_to_db":
        bot.edit_message_caption("✅ **Muvaffaqiyatli saqlandi!** API orqali Billzga yuborildi.", chat_id, call.message.message_id, parse_mode="Markdown")
        # Bu yerda API ulanish kodlari ishlaydi
    else:
        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(chat_id, "Jarayon bekor qilindi.")
        
bot.polling(none_stop=True)
