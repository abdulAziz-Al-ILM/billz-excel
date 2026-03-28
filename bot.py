import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import os
import requests
import base64

# ==========================================
# 1. SOZLAMALAR VA XAVFSIZLIK
# ==========================================
TOKEN = os.environ.get('BOT_TOKEN', 'SIZNING_BOT_TOKENINGIZ')
BILLZ_API_TOKEN = os.environ.get('BILLZ_API_TOKEN', 'SIZNING_BILLZ_TOKENINGIZ')
ALLOWED_USERS = [x.strip() for x in os.environ.get('ALLOWED_USERS', '').split(',') if x.strip()]

# 🔥 YANILANGAN MANZILLAR 
BILLZ_API_BASE = 'https://api-admin.billz.ai/v2'
BILLZ_API_POST_URL = f'{BILLZ_API_BASE}/product?Billz-Response-Channel=HTTP'

# 🔥 SIZNING BAZA ID RAQAMLARINGIZ
COMPANY_ID = "630c1af2-74be-478f-8e06-dff80bfe9edb"
SHOP_ID = "65f67287-f129-4994-b850-03299567b4ac"
PRODUCT_TYPE_ID = "69e939aa-9b8f-46a9-b605-8b2675475b7b"
MEASUREMENT_UNIT_ID = "4250db2b-fa5a-4702-8f6d-a22d8e671d7c"

bot = telebot.TeleBot(TOKEN)
drafts = {}
db = {}
CURRENT_ACCESS_TOKEN = None 

CATEGORIES = ["elektr", "santexnika", "injeneriya", "suxoy smest", "melich", "xoztovar", "instrument", "addelka", "kraska imulsiya", "kraska", "utipleniya", "pena silikon", "plintus", "kafel"]
UNITS = ["dona", "metr", "litr", "kg", "quti", "komplekt", "rulon"]

def is_allowed(message):
    if str(message.chat.id) not in ALLOWED_USERS:
        bot.send_message(message.chat.id, "⛔️ Ruxsat etilmagan foydalanuvchi.")
        return False
    return True

# ==========================================
# 🔐 BILLZ 2.0 AVTORIZATSIYA
# ==========================================
def get_valid_headers():
    global CURRENT_ACCESS_TOKEN
    if not CURRENT_ACCESS_TOKEN:
        auth_url = "https://api-admin.billz.ai/v1/auth/login"
        resp = requests.post(auth_url, json={"secret_token": BILLZ_API_TOKEN})
        if resp.status_code == 200:
            CURRENT_ACCESS_TOKEN = resp.json()['data']['access_token']
        else:
            raise Exception(f"Avtorizatsiya xatosi: {resp.text}")
    return {
        'Authorization': f'Bearer {CURRENT_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }

def execute_billz_request(method, url, payload=None):
    global CURRENT_ACCESS_TOKEN
    headers = get_valid_headers()
    if method == 'POST':
        response = requests.post(url, json=payload, headers=headers)
    else:
        response = requests.patch(url, json=payload, headers=headers)
        
    if response.status_code == 401:
        CURRENT_ACCESS_TOKEN = None
        headers = get_valid_headers()
        if method == 'POST':
            response = requests.post(url, json=payload, headers=headers)
        else:
            response = requests.patch(url, json=payload, headers=headers)
    return response

# ==========================================
# 2. ASOSIY MENU
# ==========================================
@bot.message_handler(commands=['start', 'menu'])
def main_menu(message):
    if not is_allowed(message): return
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("📦 Yangi mahsulot"))
    markup.add(KeyboardButton("✏️ Tahrirlash"), KeyboardButton("🔀 Variant kiritish"))
    bot.send_message(message.chat.id, "Asosiy menu. Tanlang:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in ["📦 Yangi mahsulot", "✏️ Tahrirlash", "🔀 Variant kiritish"])
def router(message):
    if not is_allowed(message): return
    if message.text == "📦 Yangi mahsulot":
        start_new_product(message)
    elif message.text == "✏️ Tahrirlash":
        start_edit(message)
    elif message.text == "🔀 Variant kiritish":
        start_variation(message)

# ==========================================
# 3. ZANJIR (YARATISH)
# ==========================================
def start_new_product(message):
    chat_id = message.chat.id
    drafts[chat_id] = {'type': 'new'}
    msg = bot.send_message(chat_id, "1️⃣ **Rasmni yuboring** (yoki guruhdan ulashing):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_photo)

def step_photo(message):
    chat_id = message.chat.id
    if message.photo:
        drafts[chat_id]['photo_id'] = message.photo[-1].file_id
    else:
        return bot.register_next_step_handler(bot.send_message(chat_id, "❌ Rasm yuboring!"), step_photo)
    bot.register_next_step_handler(bot.send_message(chat_id, "2️⃣ Asosiy nomini kiriting:"), step_base_name)

def step_base_name(message):
    drafts[message.chat.id]['base_name'] = message.text
    bot.register_next_step_handler(bot.send_message(message.chat.id, "3️⃣ Variativ nomini kiriting (yo'q bo'lsa '-' qo'ying):"), step_var_name)

def step_var_name(message):
    drafts[message.chat.id]['var_name'] = message.text if message.text != '-' else ''
    bot.register_next_step_handler(bot.send_message(message.chat.id, "4️⃣ Artikulni kiriting:"), step_article)

def step_article(message):
    drafts[message.chat.id]['article'] = message.text
    bot.register_next_step_handler(bot.send_message(message.chat.id, "5️⃣ Kelish narxini kiriting (KGS):"), step_cost)

def step_cost(message):
    chat_id = message.chat.id
    try:
        drafts[chat_id]['cost'] = float(message.text.replace(',', '.'))
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⚡️ Standart (+10% chakana, +7% optom)", callback_data="price_std"))
        markup.add(InlineKeyboardButton("⚙️ Manual (O'zim kiritaman)", callback_data="price_man"))
        bot.send_message(chat_id, "6️⃣ Sotish narxini qanday hisoblaymiz?", reply_markup=markup)
    except ValueError:
        bot.register_next_step_handler(bot.send_message(chat_id, "❌ Raqam kiriting:"), step_cost)

@bot.callback_query_handler(func=lambda call: call.data in ['price_std', 'price_man'])
def handle_pricing(call):
    chat_id = call.message.chat.id
    cost = drafts[chat_id]['cost']
    if call.data == 'price_std':
        drafts[chat_id]['retail'] = round(cost * 1.10, 2)
        drafts[chat_id]['wholesale'] = round(cost * 1.07, 2)
        bot.edit_message_text(f"✅ Standart narxlar:\nChakana: {drafts[chat_id]['retail']}\nOptom: {drafts[chat_id]['wholesale']}", chat_id, call.message.message_id)
        bot.register_next_step_handler(bot.send_message(chat_id, "7️⃣ Qanchadan boshlab optom hisoblanadi? (Raqam):"), step_optom_limit)
    else:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💰 Aniq narx yozaman", callback_data="man_amount"), InlineKeyboardButton("📊 Foiz yozaman", callback_data="man_percent"))
        bot.edit_message_text("Qanday usulda manual kiritasiz?", chat_id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['man_amount', 'man_percent'])
def handle_manual_type(call):
    chat_id = call.message.chat.id
    drafts[chat_id]['man_type'] = call.data
    text = "Chakana narxni kiriting (KGS):" if call.data == 'man_amount' else "Chakana ustama FOIZNI kiriting:"
    bot.register_next_step_handler(bot.edit_message_text(text, chat_id, call.message.message_id), step_man_retail)

def step_man_retail(message):
    chat_id = message.chat.id
    val = float(message.text.replace(',', '.'))
    drafts[chat_id]['retail'] = val if drafts[chat_id]['man_type'] == 'man_amount' else round(drafts[chat_id]['cost'] * (1 + val/100), 2)
    text = "Optom narxni kiriting (KGS):" if drafts[chat_id]['man_type'] == 'man_amount' else "Optom ustama FOIZNI kiriting:"
    bot.register_next_step_handler(bot.send_message(chat_id, text), step_man_wholesale)

def step_man_wholesale(message):
    chat_id = message.chat.id
    val = float(message.text.replace(',', '.'))
    drafts[chat_id]['wholesale'] = val if drafts[chat_id]['man_type'] == 'man_amount' else round(drafts[chat_id]['cost'] * (1 + val/100), 2)
    bot.register_next_step_handler(bot.send_message(chat_id, "7️⃣ Qanchadan boshlab optom hisoblanadi? (Raqam):"), step_optom_limit)

def step_optom_limit(message):
    drafts[message.chat.id]['optom_limit'] = message.text
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(*[InlineKeyboardButton(c.capitalize(), callback_data=f"cat_{c}") for c in CATEGORIES])
    markup.add(InlineKeyboardButton("➕ Yangi qo'shish", callback_data="cat_new"))
    bot.send_message(message.chat.id, "8️⃣ Katalogni tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def step_category(call):
    chat_id = call.message.chat.id
    if call.data == 'cat_new':
        bot.register_next_step_handler(bot.edit_message_text("Yangi katalog nomini yozing:", chat_id, call.message.message_id), add_cat)
    else:
        drafts[chat_id]['category'] = call.data.split('_')[1]
        bot.register_next_step_handler(bot.edit_message_text("9️⃣ Firmani kiriting:", chat_id, call.message.message_id), step_brand)

def add_cat(message):
    CATEGORIES.append(message.text.lower())
    drafts[message.chat.id]['category'] = message.text.lower()
    bot.register_next_step_handler(bot.send_message(message.chat.id, "9️⃣ Firmani kiriting:"), step_brand)

def step_brand(message):
    drafts[message.chat.id]['brand'] = message.text
    bot.register_next_step_handler(bot.send_message(message.chat.id, "🔟 Qancha qolganda signal bersin?:"), step_signal)

def step_signal(message):
    drafts[message.chat.id]['signal'] = message.text
    bot.register_next_step_handler(bot.send_message(message.chat.id, "1️⃣1️⃣ Hozir nechta keldi (Qoldiq)?:"), step_stock)

def step_stock(message):
    chat_id = message.chat.id
    drafts[chat_id]['stock'] = message.text
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(*[InlineKeyboardButton(u, callback_data=f"unit_{u}") for u in UNITS])
    bot.send_message(chat_id, "1️⃣2️⃣ O'lchov birligini tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('unit_'))
def step_unit(call):
    chat_id = call.message.chat.id
    drafts[chat_id]['unit'] = call.data.split('_')[1]
    bot.register_next_step_handler(bot.edit_message_text("1️⃣3️⃣ Izoh kiriting (yo'q bo'lsa '-' qo'ying):", chat_id, call.message.message_id), step_comment)

def step_comment(message):
    chat_id = message.chat.id
    drafts[chat_id]['comment'] = message.text
    save_to_billz(message)

# ==========================================
# 🚀 4. BILLZ 2.0 GA MUKAMMAL KLON PAYLOAD BILAN YUBORISH
# ==========================================
def save_to_billz(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "⏳ Billz tizimiga yuborilmoqda...")
    d = drafts[chat_id]
    
    full_name = f"{d['base_name']} {d.get('var_name', '')}".strip()
    cost_val = float(d['cost'])
    retail_val = float(d['retail'])
    wholesale_val = float(d['wholesale'])
    stock_val = float(d['stock'])
    
    # 📸 RASMNI TELEGRAMDAN OLIB BASE64 FORMATGA O'TKAZISH
    image_payload_list = []
    try:
        file_info = bot.get_file(d['photo_id'])
        downloaded_file = bot.download_file(file_info.file_path)
        base64_str = base64.b64encode(downloaded_file).decode('utf-8')
        
        # Hozircha eng oddiy taxmin bilan yuborib ko'ramiz
        image_payload_list = [f"data:image/jpeg;base64,{base64_str}"]
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Rasm ishlashda botda xato: {e}")

    payload = {
        "barcode": str(d['article']),
        "brand_id": "",
        "brand_name": str(d['brand']),
        "category_ids": [],
        "company_id": COMPANY_ID,
        "description": f"Katalog: {d['category']}, Izoh: {d['comment']}",
        "has_expiration_date": False,
        "images": image_payload_list, # 🔥 Rasm shu yerda ketadi
        "free_price": False,
        "is_auto_delivery": True,
        "is_auto_tax": True,
        "is_divisible": False,
        "is_variative": False,
        "measurement_type": "",
        "measurement_unit_id": MEASUREMENT_UNIT_ID,
        "name": full_name,
        "product_type_id": PRODUCT_TYPE_ID,
        "retail_price": retail_val,
        "shipments": [
            {
                "has_trigger": False,
                "measurement_value": stock_val,
                "shop_id": SHOP_ID,
                "small_left_measurement_value": 0,
                "total_measurement_value": stock_val
            }
        ],
        "shop_prices": [
            {
                "shop_id": SHOP_ID,
                "retail_price": retail_val,
                "supply_price": cost_val,
                "wholesale_price": wholesale_val,
                "min_price": 0,
                "max_price": 0
            }
        ],
        "sku": str(d['article']),
        "supplier_ids": [],
        "supply_price": cost_val,
        "tax_tariff_id": "",
        "variants": [],
        "is_marked": False,
        "scale_plu": None
    }

    try:
        response = execute_billz_request('POST', BILLZ_API_POST_URL, payload)
        
        # 🔥 Xatoni aniq o'qish uchun 500 ta harfgacha kattalashtirdik
        bot.send_message(chat_id, f"🔍 **Rentgen:**\n`{response.text[:500]}...`", parse_mode="Markdown")
        
        if response.status_code in [200, 201]:
            db[d['article']] = d 
            bot.send_photo(
                chat_id, 
                d['photo_id'], 
                caption=f"✅ **So'rov ketdi!**\n\nNom: {full_name}\nArtikul: {d['article']}\nBarkod: {d['article']}",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(chat_id, f"❌ Billz qabul qilmadi!\nKodi: {response.status_code}\nSabab: {response.text}")
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ API xatolik: {str(e)}")

    main_menu(message)

# ==========================================
# 5. TAHRIRLASH VA VARIANT (O'ZGARISHSZ)
# ==========================================
def start_edit(message):
    bot.register_next_step_handler(bot.send_message(message.chat.id, "🔍 Tahrirlash uchun ARTIKULNI kiriting:"), find_edit)

def find_edit(message):
    chat_id = message.chat.id
    art = message.text
    if art not in db:
        return bot.send_message(chat_id, "❌ Bunday artikul bot xotirasida yo'q. Avval yarating.")
    drafts[chat_id] = {'type': 'edit', 'article': art}
    show_edit_menu(chat_id)

def show_edit_menu(chat_id):
    art = drafts[chat_id]['article']
    p = db[art]
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [("Nomi", "name"), ("Kelish narx", "cost"), ("Chakana narx", "price"), ("Optom narx", "wholesale_price"), ("Qoldiq (+ qo'shish)", "stock")]
    markup.add(*[InlineKeyboardButton(text, callback_data=f"edit_{code}") for text, code in buttons])
    bot.send_message(chat_id, f"📝 Tahrirlash: **{p['base_name']} {p.get('var_name', '')}**\nNimani o'zgartirasiz?", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_') and not call.data.startswith('edit_again_'))
def handle_edit_choice(call):
    chat_id = call.message.chat.id
    drafts[chat_id]['edit_field'] = call.data.replace('edit_', '')
    bot.register_next_step_handler(bot.edit_message_text("Yangi qiymatni yozing:", chat_id, call.message.message_id), save_edit)

def save_edit(message):
    chat_id = message.chat.id
    field = drafts[chat_id]['edit_field']
    art = drafts[chat_id]['article']
    p_id = db[art].get('product_id', art)
    
    new_val = float(message.text) if field in ['cost', 'price', 'wholesale_price', 'stock'] else message.text
    if field == 'stock':
        new_val = float(db[art]['stock']) + new_val
        db[art]['stock'] = new_val
    else:
        db[art][field] = new_val

    bot.send_message(chat_id, "⏳ O'zgarish Billzga yuborilmoqda...")
    patch_url = f"{BILLZ_API_BASE}/product/{p_id}/patch-props"
    
    try:
        response = execute_billz_request('PATCH', patch_url, {field: new_val})
        if response.status_code in [200, 201]:
            bot.send_message(chat_id, "✅ Muvaffaqiyatli tahrirlandi!")
        else:
            bot.send_message(chat_id, f"❌ Billz qabul qilmadi: {response.text}")
    except Exception as e:
         bot.send_message(chat_id, f"❌ API xatoligi: {str(e)}")
    main_menu(message)

def start_variation(message):
    bot.register_next_step_handler(bot.send_message(message.chat.id, "🔀 Asosiy (Ona) mahsulot ARTIKULINI kiriting:"), find_var)

def find_var(message):
    chat_id = message.chat.id
    art = message.text
    if art not in db:
        return bot.send_message(chat_id, "❌ Bunday artikul topilmadi.")
    drafts[chat_id] = db[art].copy() 
    drafts[chat_id]['type'] = 'variant'
    bot.register_next_step_handler(bot.send_message(chat_id, f"Asos topildi: {db[art]['base_name']}.\n\nYangi variantning XUSUSIYATINI yozing (masalan: 20x15):"), step_var_new_name)

def step_var_new_name(message):
    chat_id = message.chat.id
    drafts[chat_id]['var_name'] = message.text
    bot.register_next_step_handler(bot.send_message(chat_id, "Yangi variant uchun ARTIKUL kiriting:"), step_var_art)

def step_var_art(message):
    chat_id = message.chat.id
    drafts[chat_id]['article'] = message.text
    bot.register_next_step_handler(bot.send_message(chat_id, "Kelish narxi va Nechta kelganini probel bilan yozing (Masalan: 15000 50):"), step_var_cost_stock)

def step_var_cost_stock(message):
    chat_id = message.chat.id
    try:
        cost, stock = message.text.split()
        drafts[chat_id]['cost'] = float(cost.replace(',', '.'))
        drafts[chat_id]['stock'] = stock
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Standart (+10%, +7%)", callback_data="price_std"))
        markup.add(InlineKeyboardButton("Manual", callback_data="price_man"))
        bot.send_message(chat_id, "Sotish narxini qanday hisoblaymiz?", reply_markup=markup)
    except ValueError:
        bot.register_next_step_handler(bot.send_message(chat_id, "❌ Xato format"), step_var_cost_stock)

if __name__ == '__main__':
    bot.polling(none_stop=True)
