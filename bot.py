# -*- coding: utf-8 -*-
import os
import telebot
from telebot import types
import schedule
import time
import threading
import json
import re
from datetime import datetime, timedelta
import io

# -- requirements.txt remains the same --
# pyTelegramBotAPI==4.12.0
# pymongo[srv]

from pymongo import MongoClient

# --- إعدادات بوت O7 الخاصة ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')

# --- الاتصال بقاعدة البيانات ---
try:
    client = MongoClient(MONGO_URI)
    db = client.get_default_database()
    collection = db['data_store']
    print("O7 Bot System: Successfully connected to MongoDB Atlas.")
except Exception as e:
    print(f"FATAL: Could not connect to MongoDB. Error: {e}")
    exit()

bot = telebot.TeleBot(TELEGRAM_TOKEN)
print("O7 Bot System: Online with Interactive UI.")

# --- دوال مساعدة لإدارة البيانات ---
def get_data():
    data = collection.find_one({"document_id": "main_config"})
    if data:
        return data
    else:
        initial_data = {
            "document_id": "main_config", "group_chat_id": None,
            "config": {
                "main_admin": 5615500221, # The one and only main admin
                "admins": [5615500221, 6795122268, 6940043771],
                "workers": {
                    "5615500221": {"name": "معتز", "username": "@o7_7gg", "rate": 4.5},
                    "6795122268": {"name": "عمر", "username": "@B3NEI", "rate": 4.5},
                    "6940043771": {"name": "اسامه", "username": "@i_x_u", "rate": 4.5}
                },
                "average_price_users": [6795122268, 6940043771]
            }, "orders": []
        }
        collection.insert_one(initial_data)
        return initial_data

def update_data(new_data):
    collection.replace_one({"document_id": "main_config"}, new_data, upsert=True)

def parse_quantity(text):
    match = re.search(r'\d+', text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
    return int(match.group(0)) if match else None

# --- ✨ لوحة التحكم الرئيسية ✨ ---
def main_panel_keyboard(user_id):
    """إنشاء لوحة التحكم الرئيسية بناءً على صلاحيات المستخدم."""
    data = get_data()
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Buttons for everyone
    markup.add(types.InlineKeyboardButton("📄 تقريري اليومي", callback_data="report_personal_today"))
    markup.add(types.InlineKeyboardButton("📅 تقريري المخصص", callback_data="report_personal_custom"))

    # Buttons for Admins
    if user_id in data['config']['admins']:
        markup.add(types.InlineKeyboardButton("📊 تقرير الفريق الشامل", callback_data="report_team_today"))
    
    # Buttons for Main Admin (Moataz)
    if user_id == data['config']['main_admin']:
        markup.add(types.InlineKeyboardButton("👑 إدارة الفريق", callback_data="panel_manage_team"))
        markup.add(types.InlineKeyboardButton("⚙️ إعدادات متقدمة", callback_data="panel_advanced_settings"))

    return markup

@bot.message_handler(commands=['panel', 'start'])
def show_main_panel(message):
    user_id = message.from_user.id
    data = get_data()
    if str(user_id) not in data['config']['workers']:
        # If user is not a worker, show a simple welcome message
        return bot.reply_to(message, "أهلاً بك. هذا البوت مخصص لفريق عمل O7.")
        
    keyboard = main_panel_keyboard(user_id)
    bot.send_message(message.chat.id, "👋 **أهلاً بك في لوحة تحكم O7**\n\nاختر أحد الخيارات من الأزرار أدناه:", reply_markup=keyboard, parse_mode='Markdown')

# --- معالجات الأزرار (Callback Handlers) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    """يعالج جميع ضغطات الأزرار ويوجهها للدالة المناسبة."""
    user_id = call.from_user.id
    action = call.data.split(':')[0] # e.g., "promote_user"
    
    # Main Panel Navigation
    if action == "panel_main":
        keyboard = main_panel_keyboard(user_id)
        bot.edit_message_text("🔙 القائمة الرئيسية", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    # Reports Panel
    elif action.startswith("report_"):
        handle_report_callbacks(call)
        
    # Team Management Panel
    elif action.startswith("panel_manage") or action in ["promote_user", "demote_user"]:
        handle_team_management_callbacks(call)
    
    # Advanced Settings Panel
    elif action.startswith("panel_advanced") or action.startswith("confirm_"):
         handle_advanced_settings_callbacks(call)

# --- معالجات أزرار إدارة الفريق ---
def handle_team_management_callbacks(call):
    user_id = call.from_user.id
    data = get_data()
    action, *params = call.data.split(':')

    if user_id != data['config']['main_admin']:
        return bot.answer_callback_query(call.id, "🚫 هذه الخدمة للمشرف الرئيسي فقط.")

    if action == "panel_manage_team":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("👥 عرض الفريق", callback_data="panel_manage_list"))
        markup.add(types.InlineKeyboardButton("⬆️ ترقية مشرف", callback_data="panel_manage_promote"))
        markup.add(types.InlineKeyboardButton("⬇️ تخفيض مشرف", callback_data="panel_manage_demote"))
        markup.add(types.InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="panel_main"))
        bot.edit_message_text("👑 **إدارة الفريق**\n\nاختر الإجراء المطلوب:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    elif action == "panel_manage_list":
        workers_text = "👥 **فريق العمل الحالي:**\n\n"
        for worker_id, info in data['config']['workers'].items():
            role = "👑 مشرف" if int(worker_id) in data['config']['admins'] else "👷‍♂️ عامل"
            workers_text += f"- {info['name']} ({info['username']}) - {role}\n"
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 العودة لإدارة الفريق", callback_data="panel_manage_team"))
        bot.edit_message_text(workers_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    elif action == "panel_manage_promote":
        markup = types.InlineKeyboardMarkup(row_width=1)
        # Show only non-admin workers
        for worker_id, info in data['config']['workers'].items():
            if int(worker_id) not in data['config']['admins']:
                markup.add(types.InlineKeyboardButton(f"⬆️ {info['name']}", callback_data=f"promote_user:{worker_id}"))
        markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="panel_manage_team"))
        bot.edit_message_text("اختر العامل لترقيته إلى مشرف:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif action == "promote_user":
        user_to_promote = int(params[0])
        if user_to_promote not in data['config']['admins']:
            data['config']['admins'].append(user_to_promote)
            update_data(data)
            bot.answer_callback_query(call.id, "✅ تم الترقية بنجاح!")
        else:
            bot.answer_callback_query(call.id, "⚠️ هذا المستخدم مشرف بالفعل.")
        # Refresh the promotion list
        handle_team_management_callbacks(types.CallbackQuery(id=call.id, from_user=call.from_user, data="panel_manage_promote", chat_instance=call.chat_instance, message=call.message, json_string=""))

    elif action == "panel_manage_demote":
        markup = types.InlineKeyboardMarkup(row_width=1)
        # Show only non-main admins
        for admin_id in data['config']['admins']:
            if admin_id != data['config']['main_admin']:
                worker_info = data['config']['workers'].get(str(admin_id))
                if worker_info:
                    markup.add(types.InlineKeyboardButton(f"⬇️ {worker_info['name']}", callback_data=f"demote_user:{admin_id}"))
        markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="panel_manage_team"))
        bot.edit_message_text("اختر المشرف لتخفيضه إلى عامل:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif action == "demote_user":
        user_to_demote = int(params[0])
        if user_to_demote in data['config']['admins'] and user_to_demote != data['config']['main_admin']:
            data['config']['admins'].remove(user_to_demote)
            update_data(data)
            bot.answer_callback_query(call.id, "✅ تم التخفيض بنجاح!")
        else:
            bot.answer_callback_query(call.id, "⚠️ لا يمكن تخفيض هذا المستخدم.")
        # Refresh the demotion list
        handle_team_management_callbacks(types.CallbackQuery(id=call.id, from_user=call.from_user, data="panel_manage_demote", chat_instance=call.chat_instance, message=call.message, json_string=""))


# --- معالجات الأوامر النصية القديمة (للاستخدام السريع) ---
# ... (يمكن إبقاء بعض الأوامر النصية هنا كاختصارات للمحترفين) ...
@bot.message_handler(commands=['add_worker', 'remove_worker', 'reset_worker'])
def handle_text_admin_commands(message):
    bot.reply_to(message, "يرجى استخدام لوحة التحكم التفاعلية عبر الأمر /panel لإدارة الفريق.")

# ... Rest of the code for handling orders, reports, etc. needs to be here ...
# This is a placeholder for the rest of your bot's logic which remains largely unchanged
# but would call get_data() and update_data() instead of using a local file.
# For brevity, I'll only include the new/modified parts. The core logic from the previous
# version for report generation, order handling, etc., should be copied here.


# --- نظام التشغيل ---
if __name__ == "__main__":
    get_data() # Ensure data exists on first run
    print("O7 Bot System: Polling for messages...")
    bot.polling(none_stop=True)
