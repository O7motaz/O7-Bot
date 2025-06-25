# -*- coding: utf-8 -*-
import os
import telebot
from telebot import types
import json
import re
from datetime import datetime, timedelta
import io
import threading
import time

# -- المتطلبات في requirements.txt --
# pyTelegramBotAPI==4.12.0
# pymongo[srv]
# Flask

from pymongo import MongoClient
from flask import Flask

# --- إعدادات البوت ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')

# --- الاتصال بقاعدة البيانات ---
try:
    client = MongoClient(MONGO_URI)
    db = client['O7_Bot_DB'] 
    collection = db['main_data']
    print("O7 Bot System: Successfully connected to MongoDB Atlas.")
except Exception as e:
    print(f"FATAL: Could not connect to MongoDB. Error: {e}")
    exit()

bot = telebot.TeleBot(TELEGRAM_TOKEN)
print("O7 Bot System: Online with Role-Based UI.")

# --- ✨ واجهة الويب الوهمية (لإبقاء البوت مستيقظًا على Render) ✨ ---
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running..."

def run_web_server():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

# --- دوال مساعدة لإدارة البيانات والأدوار ---
def get_data():
    data = collection.find_one({"document_id": "main_config"})
    if data:
        return data
    else:
        # الهيكل الأساسي الجديد مع الأدوار
        initial_data = {
            "document_id": "main_config", "group_chat_id": None,
            "config": {
                "workers": {
                    "5615500221": {"name": "معتز", "username": "@o7_7gg", "rate": 4.5, "roles": ["worker", "admin", "owner"]},
                    "6795122268": {"name": "عمر", "username": "@B3NEI", "rate": 4.5, "roles": ["worker", "admin"]},
                    "6940043771": {"name": "اسامه", "username": "@i_x_u", "rate": 4.5, "roles": ["worker", "admin"]}
                }
            }, "orders": []
        }
        collection.insert_one(initial_data)
        return initial_data

def update_data(new_data):
    if '_id' in new_data: del new_data['_id']
    collection.replace_one({"document_id": "main_config"}, new_data, upsert=True)

def parse_quantity(text):
    match = re.search(r'\d+', text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
    return int(match.group(0)) if match else None

def user_has_role(user_id, role):
    """Checks if a user has a specific role."""
    data = get_data()
    worker_info = data.get('config', {}).get('workers', {}).get(str(user_id))
    return worker_info and role in worker_info.get('roles', [])

# --- الواجهة الرئيسية واللوحات التفاعلية ---

@bot.message_handler(commands=['start', 'مساعدة'])
def show_main_interface(message):
    """يعرض الواجهة الرئيسية مع خيارات الأدوار."""
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("👑 مالك", callback_data="panel:owner"),
        types.InlineKeyboardButton("👨‍💻 مشرف", callback_data="panel:admin"),
        types.InlineKeyboardButton("👷‍♂️ عامل", callback_data="panel:worker")
    )
    bot.send_message(message.chat.id, "👋 **أهلاً بك في بوت O7**\n\nالرجاء تحديد دورك للوصول إلى لوحة التحكم الخاصة بك:", reply_markup=markup, parse_mode='Markdown')

# --- معالج الأزرار المركزي ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    action, *params = call.data.split(':')

    if action == "panel":
        panel_type = params[0]
        if panel_type == "owner":
            if not user_has_role(user_id, 'owner'): return bot.answer_callback_query(call.id, "🚫 هذه اللوحة للمالك فقط.", show_alert=True)
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("👑 إدارة الصلاحيات", callback_data="permissions:menu"))
            markup.add(types.InlineKeyboardButton("➕ إضافة عامل", callback_data="owner_cmd:add_worker_prompt"))
            markup.add(types.InlineKeyboardButton("➖ حذف عامل", callback_data="owner_cmd:remove_worker_prompt"))
            markup.add(types.InlineKeyboardButton("💸 تصفير عامل", callback_data="owner_cmd:reset_worker_prompt"))
            markup.add(types.InlineKeyboardButton("💾 نسخة احتياطية", callback_data="owner_cmd:backup"))
            bot.edit_message_text("👑 **لوحة تحكم المالك**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        # ... (Rest of panel logic)

    elif action == "permissions":
        if not user_has_role(user_id, 'owner'): return bot.answer_callback_query(call.id, "🚫 للمالك فقط.")
        perm_action = params[0]
        data = get_data()
        if perm_action == "menu":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("⬆️⬇️ تغيير رتبة مشرف", callback_data="permissions:toggle_admin_list"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع للوحة المالك", callback_data="panel:owner"))
            bot.edit_message_text("👑 **إدارة الصلاحيات**", call.message.chat.id, call.message.message_id, reply_markup=markup)
        elif perm_action == "toggle_admin_list" or perm_action == "toggle_admin":
            if perm_action == "toggle_admin":
                target_id = int(params[1])
                target_roles = data['config']['workers'][str(target_id)]['roles']
                if 'admin' in target_roles:
                    if target_id != data['config']['workers'].get(str(user_id)): target_roles.remove('admin')
                else:
                    target_roles.append('admin')
                update_data(data)
                bot.answer_callback_query(call.id, "✅ تم تحديث الرتبة.")
            markup = types.InlineKeyboardMarkup(row_width=1)
            for worker_id_str, info in data['config']['workers'].items():
                is_admin = 'admin' in info.get('roles', [])
                button_text = f"{'⬇️' if is_admin else '⬆️'} {info['name']}"
                markup.add(types.InlineKeyboardButton(button_text, callback_data=f"permissions:toggle_admin:{worker_id_str}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="permissions:menu"))
            bot.edit_message_text("اختر مستخدمًا لترقيته إلى مشرف أو تخفيضه:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    # ... (Rest of callback logic for commands, owner commands, etc.)

# --- معالجات الأوامر النصية ---
@bot.message_handler(func=lambda message: str(message.from_user.id) in get_data()['config']['workers'] and message.chat.type in ['group', 'supergroup'] and not message.text.startswith('/'))
def handle_new_order(message):
    data = get_data(); quantity = parse_quantity(message.text)
    if not quantity: return
    if data.get("group_chat_id") is None: data["group_chat_id"] = message.chat.id; update_data(data)
    requester_info = data['config']['workers'].get(str(message.from_user.id), {})
    new_order = {
        "message_id": message.message_id, "chat_id": message.chat.id, "text": message.text, "quantity": quantity,
        "requester_id": message.from_user.id, "requester_name": requester_info.get("name"), "status": "pending",
        "worker_id": None, "worker_name": None, "paid": False,
        "request_time": datetime.now().isoformat(), "completion_time": None }
    data["orders"].append(new_order); update_data(data)

@bot.message_handler(func=lambda message: message.text and message.text.strip().lower() == "تم" and str(message.from_user.id) in get_data()['config']['workers'] and message.reply_to_message)
def handle_order_completion(message):
    data = get_data(); worker_info = data['config']['workers'].get(str(message.from_user.id))
    original_order_message_id, chat_id = message.reply_to_message.message_id, message.chat.id
    order_found = False
    for order in data["orders"]:
        if order["message_id"] == original_order_message_id and order["status"] == "pending":
            order.update({ "status": "completed", "worker_id": message.from_user.id, "worker_name": worker_info.get("name"), "completion_time": datetime.now().isoformat() })
            update_data(data); order_found = True; break
    if order_found:
        try: bot.delete_message(chat_id, original_order_message_id)
        except Exception as e: print(f"O7 ERROR: Could not delete ORIGINAL message. Check permissions. {e}")
    try: bot.delete_message(chat_id, message.message_id)
    except Exception as e: print(f"O7 ERROR: Could not delete 'تم' message. Check permissions. {e}")

# ... (Financial report, text command handlers, and other functions are placed here)
# ... The code for these functions is the same as the previous stable version.

# --- نظام التشغيل ---
if __name__ == "__main__":
    get_data() # Ensure data structure exists on first run
    
    # Run Flask server in a separate thread
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    
    print("O7 Bot System: Polling for messages...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Bot polling failed: {e}")
        time.sleep(5)
