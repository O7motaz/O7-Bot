# -*- coding: utf-8 -*-
import os
import telebot
from telebot import types
import json
import re
from datetime import datetime, timedelta
import threading
import time

# -- المتطلبات في requirements.txt --
# pyTelegramBotAPI==4.12.0
# pymongo[srv]
# Flask
# gunicorn

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

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
app = Flask(__name__)

# --- واجهة الويب (لإبقاء البوت مستيقظًا على Render) ---
@app.route('/')
def index():
    return "Bot is running and stable."

# --- دوال مساعدة لإدارة البيانات ---
def get_data():
    data = collection.find_one({"document_id": "main_config"})
    if data:
        return data
    else:
        # الهيكل الأساسي المبسط
        initial_data = {
            "document_id": "main_config",
            "group_chat_id": None,
            "config": {
                "owner_id": 5615500221, # Moataz Only
                "workers": {
                    "5615500221": {"name": "معتز", "rate": 4.5},
                    "6795122268": {"name": "عمر", "rate": 4.5},
                    "6940043771": {"name": "اسامه", "rate": 4.5}
                }
            }, 
            "orders": []
        }
        collection.insert_one(initial_data)
        return initial_data

def update_data(new_data):
    if '_id' in new_data: del new_data['_id']
    collection.replace_one({"document_id": "main_config"}, new_data, upsert=True)

def parse_quantity(text):
    match = re.search(r'\d+', text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
    return int(match.group(0)) if match else None

# --- معالجات الأوامر الأساسية ---

@bot.message_handler(commands=['start', 'مساعدة'])
def handle_start(message):
    """يرسل رسالة ترحيبية بسيطة مع قائمة الأوامر المحدثة."""
    welcome_text = (
        "👋 **أهلاً بك في بوت O7**\n\n"
        "أنا هنا لتسجيل الطلبات وتتبع العمل اليومي وحساب الأجور.\n\n"
        "**الأوامر المتاحة:**\n"
        "`/تقرير` - لعرض ملخص العمل والأجور لليوم الحالي.\n"
        "`/تقرير_مفصل` - لعرض تقرير تراكمي لجميع الأعمال المستحقة.\n"
        "`/تصفير_الكل` - (للمطور فقط) لأرشفة البيانات الحالية."
    )
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: str(message.from_user.id) in get_data()['config']['workers'] and message.chat.type in ['group', 'supergroup'] and not message.text.startswith('/'))
def handle_new_order(message):
    """يعالج الطلبات الجديدة من العمال في المجموعة."""
    data = get_data()
    quantity = parse_quantity(message.text)
    if not quantity: return
    
    if data.get("group_chat_id") is None:
        data["group_chat_id"] = message.chat.id
        update_data(data)

    new_order = {
        "message_id": message.message_id,
        "chat_id": message.chat.id,
        "text": message.text,
        "quantity": quantity,
        "requester_id": message.from_user.id,
        "status": "pending",
        "archived": False,
        "request_time": datetime.now().isoformat()
    }
    data["orders"].append(new_order)
    update_data(data)

@bot.message_handler(func=lambda message: message.text and message.text.strip().lower() == "تم" and str(message.from_user.id) in get_data()['config']['workers'] and message.reply_to_message)
def handle_order_completion(message):
    """يعالج تنفيذ الطلبات ويحذف الرسائل."""
    data = get_data()
    worker_info = data['config']['workers'].get(str(message.from_user.id))
    original_order_message_id = message.reply_to_message.message_id
    chat_id = message.chat.id
    order_found = False

    for order in data["orders"]:
        if order["message_id"] == original_order_message_id and order["status"] == "pending":
            order.update({
                "status": "completed",
                "worker_id": message.from_user.id,
                "worker_name": worker_info.get("name"),
                "completion_time": datetime.now().isoformat()
            })
            update_data(data)
            order_found = True
            break
            
    if order_found:
        try:
            bot.delete_message(chat_id, original_order_message_id)
        except Exception as e:
            print(f"O7 ERROR: Could not delete ORIGINAL message. Check permissions. {e}")
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"O7 ERROR: Could not delete 'تم' message. Check permissions. {e}")

@bot.message_handler(commands=['تقرير'])
def daily_report_command(message):
    """ينشئ تقريرًا بعمل اليوم مع حساب الأجور."""
    data = get_data()
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # Filter for completed orders from today that are not archived
    todays_orders = [
        o for o in data.get("orders", []) 
        if o.get("status") == "completed" and 
           not o.get("archived") and 
           o.get("completion_time", "").startswith(today_str)
    ]
    
    if not todays_orders:
        return bot.reply_to(message, f"📊 **تقرير اليوم ({today_str})**\n\nلم يتم تنفيذ أي عمل اليوم.")

    worker_summary = {}
    for order in todays_orders:
        worker_id_str = str(order.get("worker_id"))
        name = order.get("worker_name", "غير معروف")
        quantity = order.get("quantity", 0)
        
        if name not in worker_summary:
            worker_summary[name] = {"quantity": 0, "id": worker_id_str}
        
        worker_summary[name]["quantity"] += quantity
        
    total_quantity = sum(summary["quantity"] for summary in worker_summary.values())
    report_text = f"📊 **تقرير اليوم ({today_str})**\n\n"
    report_text += f"✨ *إجمالي الكمية المنفذة: {total_quantity}*\n--------------------\n"
    
    for worker_name, summary in worker_summary.items():
        worker_id = summary["id"]
        worker_rate = data.get("config", {}).get("workers", {}).get(worker_id, {}).get("rate", 0)
        
        qty = summary["quantity"]
        wage = (qty / 100) * worker_rate
        
        report_text += f"👷‍♂️ *{worker_name}*: {qty} وحدة | 💰 *الأجر المستحق: ${wage:.2f}*\n"
            
    bot.send_message(message.chat.id, report_text, parse_mode='Markdown')


@bot.message_handler(commands=['تقرير_مفصل'])
def detailed_report_command(message):
    """✅ أمر جديد: ينشئ تقريرًا تراكميًا بجميع الأعمال المستحقة."""
    data = get_data()
    
    # Filter for all completed orders that are not archived
    unarchived_orders = [
        o for o in data.get("orders", []) 
        if o.get("status") == "completed" and not o.get("archived")
    ]
    
    if not unarchived_orders:
        return bot.reply_to(message, "🧾 **التقرير المفصل**\n\nلا توجد أي أعمال مستحقة حاليًا.")

    worker_summary = {}
    for order in unarchived_orders:
        worker_id_str = str(order.get("worker_id"))
        name = order.get("worker_name", "غير معروف")
        quantity = order.get("quantity", 0)
        
        if name not in worker_summary:
            worker_summary[name] = {"quantity": 0, "id": worker_id_str}
        
        worker_summary[name]["quantity"] += quantity
        
    total_quantity = sum(summary["quantity"] for summary in worker_summary.values())
    report_text = f"🧾 **التقرير المفصل لجميع الأعمال المستحقة**\n\n"
    report_text += f"✨ *إجمالي الكمية المستحقة: {total_quantity}*\n--------------------\n"
    
    # حساب الأجور لكل عامل
    for worker_name, summary in worker_summary.items():
        worker_id = summary["id"]
        worker_rate = data.get("config", {}).get("workers", {}).get(worker_id, {}).get("rate", 0)
        
        qty = summary["quantity"]
        wage = (qty / 100) * worker_rate
        
        report_text += f"👷‍♂️ *{worker_name}*: {qty} وحدة | 💰 *إجمالي الأجر المستحق: ${wage:.2f}*\n"
            
    bot.send_message(message.chat.id, report_text, parse_mode='Markdown')


@bot.message_handler(commands=['تصفير_الكل'])
def reset_all_command(message):
    """يقوم بأرشفة جميع البيانات (للمطور فقط)."""
    data = get_data()
    if message.from_user.id != data['config']['owner_id']:
        return bot.reply_to(message, "🚫 هذه الخدمة للمطور فقط.")

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("نعم، قم بالأرشفة", callback_data="confirm_reset"),
        types.InlineKeyboardButton("إلغاء", callback_data="cancel_reset")
    )
    bot.send_message(message.chat.id, "🚨 **تحذير:** هل أنت متأكد أنك تريد أرشفة جميع بيانات العمل الحالية؟", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_reset", "cancel_reset"])
def handle_reset_callback(call):
    """يعالج رد التأكيد على الأرشفة."""
    data = get_data()
    if call.from_user.id != data['config']['owner_id']:
        return bot.answer_callback_query(call.id, "🚫 ليس لديك الصلاحية لهذا الإجراء.")

    if call.data == "confirm_reset":
        # Mark all completed orders as archived
        for order in data["orders"]:
            if order.get("status") == "completed":
                order["archived"] = True
        update_data(data)
        bot.edit_message_text("✅ تم أرشفة جميع بيانات العمل المكتملة بنجاح.", call.message.chat.id, call.message.message_id)
    else:
        bot.edit_message_text("👍 تم إلغاء العملية.", call.message.chat.id, call.message.message_id)


# --- نظام التشغيل ---
def run_bot_polling():
    print("O7 Bot System: Starting bot polling...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Bot polling failed: {e}")
        time.sleep(5)

# يتم تشغيل البوت في خيط منفصل
polling_thread = threading.Thread(target=run_bot_polling)
polling_thread.daemon = True
polling_thread.start()

# gunicorn سيقوم بتشغيل 'app' من هذا الملف
if __name__ == "__main__":
    print("O7 Bot System is ready and running.")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
