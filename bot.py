import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import os
import requests
import json
import random
import time

# ==========================================
# 1. SOZLAMALAR VA XAVFSIZLIK
# ==========================================
TOKEN = os.environ.get('BOT_TOKEN', 'SIZNING_BOT_TOKENINGIZ')
BILLZ_API_TOKEN = os.environ.get('BILLZ_API_TOKEN', 'SIZNING_BILLZ_TOKENINGIZ')
ALLOWED_USERS = [x.strip() for x in os.environ.get('ALLOWED_USERS', '').split(',') if x.strip()]

# 🤖 AI API KALITINGIZ SHU YERGA KIRITILADI (Masalan: OpenAI yoki shunga o'xshash)
AI_API_KEY = "SIZNING_AI_API_KALITINGIZ"

BILLZ_API_BASE = 'https://api-admin.billz.ai/v2'
BILLZ_API_POST_URL = f'{BILLZ_API_BASE}/product?Billz-Response-Channel=HTTP'
BILLZ_UPLOAD_URL = 'https://sss.billz.ai/api/v1/upload' 

COMPANY_ID = "630c1af2-74be-478f-8e06-dff80bfe9edb"
SHOP_ID = "65f67287-f129-4994-b850-03299567b4ac"
PRODUCT_TYPE_ID = "69e939aa-9b8f-46a9-b605-8b2675475b7b"
MEASUREMENT_UNIT_ID = "4250db2b-fa5a-4702-8f6d-a22d8e671d7c"

bot = telebot.TeleBot(TOKEN)
drafts = {}
db = {}
CURRENT_ACCESS_TOKEN = None 

CATEGORIES_DB = {
    "elektr jihozlari": "59ce55e6-0b1e-4be2-a646-87f3c8e95876", 
    "santexnika": "79233dfd-cec2-47ca-a787-403829e554d4", 
    "qurilish qorishmalari": "", 
    "bo'yoqlar va emulsiya": "3a34e878-0f32-410c-bd0c-fc62c2ab8f60", 
    "kafel va plitkalar": "0325476b-8cab-4da1-94ec-ade1727f53ac", 
    "asbob-uskunalar": "7552b39d-aff3-4b21-a756-7014c17e8cbc",
    "issiqlik izolyatsiyasi": "03147648-a1bc-433f-a444-9cfaa2806c39", 
    "xo'jalik mollari": "45e95524-5047-43a6-8cf3-79e9f08becb8", 
    "pena, silikon va yelimlar": "6ed8fe11-e13e-4eb4-bfb4-8f69343695d1",
    "pardozlash materiallari": "335d4496-d096-478f-a813-73c21f1fc129", 
    "mayda qotirish vositalari": "4327ed6a-a49d-4966-98ff-34dd439f8254",
    "plintus va profillar": "a4bc6969-da19-4455-96dd-5de4aea6f441", 
    "muhandislik tizimlari": "f53dfb0f-6113-4a9e-b913-09c44cbbef10", 
    "boshqa": "" 
}

CATEGORIES = list(CATEGORIES_DB.keys())
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
# 2. ASOSIY MENU (YANGI AI TUGMASI QO'SHILDI)
# ==========================================
@bot.message_handler(commands=['start', 'menu'])
def main_menu(message):
    if not is_allowed(message): return
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("📦 Yangi mahsulot"), KeyboardButton("🤖 AI orqali yuklash"))
    markup.add(KeyboardButton("✏️ Tahrirlash"), KeyboardButton("🔀 Variant kiritish"))
    bot.send_message(message.chat.id, "Asosiy menu. Tanlang:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in ["📦 Yangi mahsulot", "🤖 AI orqali yuklash", "✏️ Tahrirlash", "🔀 Variant kiritish"])
def router(message):
    if not is_allowed(message): return
    if message.text == "📦 Yangi mahsulot":
        start_new_product(message)
    elif message.text == "🤖 AI orqali yuklash":
        start_ai_upload(message)
    elif message.text == "✏️ Tahrirlash":
        start_edit(message)
    elif message.text == "🔀 Variant kiritish":
        start_variation(message)

# ==========================================
# 🤖 AI PARALLEL FUNKSIYASI (YANGI ZANJIR)
# ==========================================
def start_ai_upload(message):
    msg = bot.send_message(message.chat.id, "📄 Mahsulotlar ro'yxati (jadval) rasmini yuboring:\nAI uni o'qib, o'zi Billzga avtomatik joylaydi.")
    bot.register_next_step_handler(msg, process_ai_image)

def process_ai_image(message):
    chat_id = message.chat.id
    if not message.photo:
        return bot.send_message(chat_id, "❌ Iltimos, faqat rasm yuboring!")

    bot.send_message(chat_id, "⏳ Rasm qabul qilindi. AI jadvalni o'qib, ma'lumotlarni tahlil qilmoqda... (Biroz kutamiz)")
    
    # 1. Rasmni yuklab olish (Sizning API'ga yuborish uchun)
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    # =========================================================
    # ❗️ DIQQAT: API ULANADIGAN JOY (Bu yerga API kodingizni qo'yasiz)
    # Siz aytgan logikani AI ga yuboramiz. 
    # MOCK (AI yubordi deb faraz qilingan tayyor ro'yxat, test uchun):
    # =========================================================
    try:
        # ai_response_text = call_your_ai_api(downloaded_file, prompt=Sizning_qoidangiz)
        # ai_parsed_data = json.loads(ai_response_text)
        
        # Test qilish uchun sun'iy ma'lumot (API ulamasdan oldin test qilib oling)
        ai_parsed_data = [
            {"name": "DESPINA ВЫКЛ. 1 КЛАВ. ГРАФИТ", "stock": 10, "unit": "dona", "cost": 130.5, "optom_limit": 5, "signal": 2, "category": "elektr jihozlari", "brand": "DESPINA"},
            {"name": "DESPINA РАМКА 2-Я ГРАФИТ", "stock": 16, "unit": "dona", "cost": 76.5, "optom_limit": 10, "signal": 5, "category": "elektr jihozlari", "brand": "DESPINA"}
        ]
        
        bot.send_message(chat_id, f"✅ AI {len(ai_parsed_data)} ta mahsulotni aniqladi! Billzga yuklash boshlandi...")
        
        success_count = 0
        for item in ai_parsed_data:
            if auto_save_to_billz(chat_id, item):
                success_count += 1
                
        bot.send_message(chat_id, f"🎉 Jarayon tugadi! Billzga avtomatik {success_count} ta mahsulot qo'shildi.")
        main_menu(message)
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ AI xatosi yuz berdi: {str(e)}")
        main_menu(message)

def auto_save_to_billz(chat_id, p_data):
    """ AI orqali kelgan ma'lumotni Billz formatiga solib jo'natadi """
    full_name = p_data.get('name', 'Nomsiz')
    cost_val = float(p_data.get('cost', 0))
    stock_val = float(p_data.get('stock', 0))
    brand_name = p_data.get('brand', '-')
    category_name = p_data.get('category', 'boshqa')
    optom_limit_val = p_data.get('optom_limit', 5)
    signal_val = float(p_data.get('signal', 1))
    
    # +10% va +7% logika botning o'zida hisoblanadi
    retail_val = round(cost_val * 1.10, 2)
    wholesale_val = round(cost_val * 1.07, 2)
    
    # 🤖 AI Artikul yaratilishi
    ai_article = f"AI-kirgizdi-{random.randint(1000, 9999)}"
    
    cat_id = CATEGORIES_DB.get(category_name, "")
    cat_list = [cat_id] if cat_id else []

    payload = {
        "barcode": ai_article,
        "brand_id": "",
        "brand_name": brand_name,
        "category_ids": cat_list,
        "company_id": COMPANY_ID,
        "description": f"Katalog: {category_name} | Brend: {brand_name} | Optom: {optom_limit_val} tadan | Izoh: AI ro'yxatdan kiritdi",
        "has_expiration_date": False,
        "images": [], # AI rasmsiz yuboradi, keyin o'zingiz qo'shasiz
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
        "retail_currency": "KGS",
        "supply_price": cost_val,
        "supply_currency": "KGS",
        "wholesale_currency": "KGS",
        "currency": "KGS",
        "shipments": [{"has_trigger": False, "measurement_value": stock_val, "shop_id": SHOP_ID, "small_left_measurement_value": signal_val, "total_measurement_value": stock_val}],
        "shop_measurement_values": [{"has_trigger": False, "measurement_value": stock_val, "shop_id": SHOP_ID, "small_left_measurement_value": signal_val, "total_measurement_value": stock_val}],
        "shop_prices": [{"shop_id": SHOP_ID, "retail_price": retail_val, "supply_price": cost_val, "wholesale_price": wholesale_val, "min_price": 0, "max_price": 0, "retail_currency": "KGS", "supply_currency": "KGS", "wholesale_currency": "KGS", "currency": "KGS"}],
        "sku": ai_article,
        "supplier_ids": [],
        "tax_tariff_id": "",
        "variants": [],
        "is_marked": False,
        "scale_plu": None
    }

    try:
        response = execute_billz_request('POST', BILLZ_API_POST_URL, payload)
        if response.status_code in [200, 201]:
            # Bazaga eslab qolamiz (Tahrirlash ishlashi uchun)
            p_data['article'] = ai_article
            p_data['base_name'] = full_name
            db[ai_article] = p_data
            return True
        else:
            bot.send_message(chat_id, f"⚠️ '{full_name}' qo'shilmadi: {response.status_code}")
            return False
    except Exception as e:
        bot.send_message(chat_id, f"❌ Dasturiy xato: {str(e)}")
        return False

# ==========================================
# 3. ZANJIR (QO'LDA YARATISH) - SIZNING ORIGINAL KODINGIZ
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
        bot.register_next_step_handler(bot.send_message(chat_id, "7️⃣ Qanchadan boshlab optom hisoblanadi? (Raqam kiriting):"), step_optom_limit)
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
    bot.register_next_step_handler(bot.send_message(chat_id, "7️⃣ Qanchadan boshlab optom hisoblanadi? (Raqam kiriting):"), step_optom_limit)

def step_optom_limit(message):
    drafts[message.chat.id]['optom_limit'] = message.text
    bot.register_next_step_handler(bot.send_message(message.chat.id, "8️⃣ Qancha qolganda ogohlantirsin (Kam qoldiq signali)?:"), step_signal)

def step_signal(message):
    drafts[message.chat.id]['signal'] = message.text
    bot.register_next_step_handler(bot.send_message(message.chat.id, "9️⃣ Hozir nechta keldi (Qoldiq)?:"), step_stock)

def step_stock(message):
    chat_id = message.chat.id
    drafts[chat_id]['stock'] = message.text
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(*[InlineKeyboardButton(c.capitalize(), callback_data=f"cat_{c}") for c in CATEGORIES])
    bot.send_message(chat_id, "🔟 Katalogni tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def step_category(call):
    chat_id = call.message.chat.id
    drafts[chat_id]['category'] = call.data.split('_')[1]
    bot.register_next_step_handler(bot.edit_message_text("1️⃣1️⃣ Brend nomini kiriting:", chat_id, call.message.message_id), step_brand)

def step_brand(message):
    drafts[message.chat.id]['brand'] = message.text
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(*[InlineKeyboardButton(u, callback_data=f"unit_{u}") for u in UNITS])
    bot.send_message(message.chat.id, "1️⃣2️⃣ O'lchov birligini tanlang:", reply_markup=markup)

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
# 🚀 4. BILLZ 2.0 GA MUKAMMAL YUBORISH
# ==========================================
def save_to_billz(message):
    chat_id = message.chat.id
    d = drafts[chat_id]
    
    full_name = f"{d['base_name']} {d.get('var_name', '')}".strip()
    cost_val = float(d['cost'])
    retail_val = float(d['retail'])
    wholesale_val = float(d['wholesale'])
    stock_val = float(d.get('stock', 0))
    signal_val = float(d.get('signal', 0))
    optom_limit_val = d.get('optom_limit', 'Belgilanmagan')
    
    image_payload_list = []
    bot.send_message(chat_id, "📸 Rasm Billz serveriga yuklanmoqda...")
    try:
        file_info = bot.get_file(d['photo_id'])
        downloaded_file = bot.download_file(file_info.file_path)
        
        headers = {
            'Authorization': f'Bearer {CURRENT_ACCESS_TOKEN}',
            'platform-id': '7d4a4c38-dd84-4902-b744-0488b80a4c01'
        }
        files = {'file': ('product_image.png', downloaded_file, 'image/png')}
        
        up_res = requests.post(BILLZ_UPLOAD_URL, headers=headers, files=files)
        
        if up_res.status_code in [200, 201]:
            up_data = up_res.json()
            img_val = None
            if 'data' in up_data:
                if isinstance(up_data['data'], str):
                    img_val = up_data['data']
                elif isinstance(up_data['data'], dict):
                    img_val = up_data['data'].get('url', up_data['data'].get('id', str(up_data['data'])))
            else:
                img_val = up_data.get('url', str(up_data))
                
            image_payload_list = [img_val] if img_val else []
            bot.send_message(chat_id, "✅ Rasm omborga joylandi. Endi to'var yuborilmoqda...")
        else:
            bot.send_message(chat_id, f"⚠️ Rasm yuklashda xato (kod {up_res.status_code}): {up_res.text}")
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Botda rasm ishlash xatosi: {e}")

    cat_id = CATEGORIES_DB.get(d['category'], "")
    cat_list = [cat_id] if cat_id else []

    payload = {
        "barcode": str(d['article']),
        "brand_id": "",
        "brand_name": str(d['brand']),
        "category_ids": cat_list,
        "company_id": COMPANY_ID,
        "description": f"Katalog: {d['category']} | Brend: {d['brand']} | Optom: {optom_limit_val} tadan | Izoh: {d['comment']}",
        "has_expiration_date": False,
        "images": image_payload_list,
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
        "retail_currency": "KGS",
        "supply_price": cost_val,
        "supply_currency": "KGS",
        "wholesale_currency": "KGS",
        "currency": "KGS",
        "shipments": [{"has_trigger": False, "measurement_value": stock_val, "shop_id": SHOP_ID, "small_left_measurement_value": signal_val, "total_measurement_value": stock_val}],
        "shop_measurement_values": [{"has_trigger": False, "measurement_value": stock_val, "shop_id": SHOP_ID, "small_left_measurement_value": signal_val, "total_measurement_value": stock_val}],
        "shop_prices": [{"shop_id": SHOP_ID, "retail_price": retail_val, "supply_price": cost_val, "wholesale_price": wholesale_val, "min_price": 0, "max_price": 0, "currency": "KGS", "retail_currency": "KGS", "supply_currency": "KGS", "wholesale_currency": "KGS"}],
        "sku": str(d['article']),
        "supplier_ids": [],
        "tax_tariff_id": "",
        "variants": [],
        "is_marked": False,
        "scale_plu": None
    }

    try:
        response = execute_billz_request('POST', BILLZ_API_POST_URL, payload)
        if response.status_code in [200, 201]:
            db[d['article']] = d 
            bot.send_photo(chat_id, d['photo_id'], caption=f"✅ **Barcha so'rovlar muvaffaqiyatli ketdi!**\n\nNom: {full_name}\nArtikul: {d['article']}\nOptom: {optom_limit_val} tadan", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"❌ Billz to'varni qabul qilmadi!\nKodi: {response.status_code}\nSabab: {response.text}")
    except Exception as e:
        bot.send_message(chat_id, f"❌ API xatolik: {str(e)}")

    main_menu(message)

# ==========================================
# 5. TAHRIRLASH VA VARIANT [ESKI HOLATDA QOLDI]
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
