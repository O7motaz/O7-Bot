# -*- coding: utf-8 -*-
import os
import telebot
from telebot import types
import json
import re
from datetime import datetime, timedelta
import io

# -- requirements.txt --
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
print("O7 Bot System: Online with Arabic Command Interface.")

# --- دوال مساعدة لإدارة البيانات ---
def get_data():
    data = collection.find_one({"document_id": "main_config"})
    if data:
        return data
    else:
        initial_data = {
            "document_id": "main_config", "group_chat_id": None,
            "config": {
                "main_admin": 5615500221,
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
    if '_id' in new_data:
        del new_data['_id']
    collection.replace_one({"document_id": "main_config"}, new_data, upsert=True)

def parse_quantity(text):
    match = re.search(r'\d+', text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
    return int(match.group(0)) if match else None

# --- ✨ رسالة الترحيب المبسطة ✨ ---
@bot.message_handler(commands=['start', 'مساعدة'])
def handle_start(message):
    welcome_text = "👋 **أهلاً بك في بوت O7**\n\nأضفني إلى مجموعتك وقم بترقيتي إلى مشرف مع صلاحية حذف الرسائل لبدء إدارة البيانات."
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

# --- معالجات الرسائل الأساسية ---
@bot.message_handler(func=lambda message: str(message.from_user.id) in get_data()['config']['workers'] and message.chat.type in ['group', 'supergroup'] and not message.text.startswith('/'))
def handle_new_order(message):
    data = get_data()
    quantity = parse_quantity(message.text)
    if not quantity: return
    if data.get("group_chat_id") is None: data["group_chat_id"] = message.chat.id
    requester_info = data['config']['workers'].get(str(message.from_user.id), {})
    new_order = {
        "message_id": message.message_id, "chat_id": message.chat.id, "text": message.text, "quantity": quantity,
        "requester_id": message.from_user.id, "requester_name": requester_info.get("name"), "status": "pending",
        "worker_id": None, "worker_name": None, "paid": False,
        "request_time": datetime.now().isoformat(), "completion_time": None
    }
    data["orders"].append(new_order)
    update_data(data)

@bot.message_handler(func=lambda message: message.text and message.text.strip().lower() == "تم" and str(message.from_user.id) in get_data()['config']['workers'] and message.reply_to_message)
def handle_order_completion(message):
    data = get_data()
    worker_info = data['config']['workers'].get(str(message.from_user.id))
    original_order_message_id = message.reply_to_message.message_id
    chat_id = message.chat.id
    order_found = False
    for order in data["orders"]:
        if order["message_id"] == original_order_message_id and order["status"] == "pending":
            order.update({
                "status": "completed", "worker_id": message.from_user.id, "worker_name": worker_info.get("name"),
                "completion_time": datetime.now().isoformat()
            })
            update_data(data)
            order_found = True
            break
    if order_found:
        try: bot.delete_message(chat_id, original_order_message_id)
        except Exception as e: print(f"O7 ERROR: Could not delete ORIGINAL message. Check permissions. {e}")
    try: bot.delete_message(chat_id, message.message_id)
    except Exception as e: print(f"O7 ERROR: Could not delete 'تم' message. Check permissions. {e}")

# --- نظام التقارير المالي ---
def generate_financial_report(message, start_date, end_date, for_user_id=None):
    data = get_data()
    end_date_inclusive = end_date + timedelta(days=1)
    unpaid_orders = [o for o in data.get("orders", []) if o.get("status") == "completed" and not o.get("paid")]
    
    filtered_orders = [
        o for o in unpaid_orders if o.get("completion_time") and 
        start_date <= datetime.fromisoformat(o["completion_time"]) < end_date_inclusive and
        (for_user_id is None or o.get("worker_id") == for_user_id)
    ]
    
    start_str, end_str = start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    report_title = f"📊 **تقرير ليوم {start_str}**" if start_str == end_str else f"📊 **تقرير من {start_str} إلى {end_str}**"
    if for_user_id: report_title = f"📄 **تقريرك الشخصي**"
    
    if not filtered_orders:
        report_text = f"{report_title}\n\nلا يوجد عمل مسجل في هذه الفترة."
    else:
        report_text = f"{report_title}\n\n"
        worker_summary = {}
        for order in filtered_orders:
            worker_id_str = str(order.get("worker_id"))
            name = order.get("worker_name", "غير معروف")
            if name not in worker_summary: worker_summary[name] = {"count": 0, "total_quantity": 0, "id": worker_id_str}
            worker_summary[name]["count"] += 1
            worker_summary[name]["total_quantity"] += order.get("quantity", 0)
        
        total_quantity_all = sum(s['total_quantity'] for s in worker_summary.values())
        report_text += f"✨ *إجمالي الطلبات: {len(filtered_orders)}* | 📦 *إجمالي الكميات: {total_quantity_all}*\n--------------------\n"
        
        for worker, summary in worker_summary.items():
            worker_config = data['config']['workers'].get(summary["id"], {})
            rate = worker_config.get("rate", 0)
            wage = (summary['total_quantity'] / 100) * rate if rate > 0 else 0
            report_text += f"👷‍♂️ *{worker}*: {summary['count']} طلبات (كمية: {summary['total_quantity']})"
            if wage > 0: report_text += f" | 💰 *الأجر المستحق: ${wage:.2f}*"
            report_text += "\n"
            
    bot.send_message(message.chat.id, report_text, parse_mode='Markdown')

# --- معالجات الأوامر (باللغة العربية) ---

@bot.message_handler(commands=['تقرير'])
def daily_report_command(message):
    data = get_data()
    if str(message.from_user.id) not in data['config']['workers']:
        return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    generate_financial_report(message, today, today, for_user_id=message.from_user.id)

@bot.message_handler(commands=['تقريري'])
def custom_personal_report_command(message):
    data = get_data()
    if str(message.from_user.id) not in data['config']['workers']:
        return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    parts = message.text.split()
    if len(parts) != 3:
        return bot.reply_to(message, "صيغة خاطئة. استخدم:\n/تقريري [YYYY-MM-DD] [YYYY-MM-DD]")
    try:
        start_date = datetime.strptime(parts[1], '%Y-%m-%d')
        end_date = datetime.strptime(parts[2], '%Y-%m-%d')
        generate_financial_report(message, start_date, end_date, for_user_id=message.from_user.id)
    except ValueError:
        bot.reply_to(message, "⚠️ صيغة التاريخ خاطئة: `YYYY-MM-DD`")

@bot.message_handler(commands=['احصائيات'])
def custom_team_report_command(message):
    data = get_data()
    if message.from_user.id not in data['config']['admins']:
        return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    parts = message.text.split()
    if len(parts) == 1:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return generate_financial_report(message, today, today)
    if len(parts) != 3:
        return bot.reply_to(message, "صيغة خاطئة. استخدم:\n/احصائيات [YYYY-MM-DD] [YYYY-MM-DD]")
    try:
        start_date = datetime.strptime(parts[1], '%Y-%m-%d')
        end_date = datetime.strptime(parts[2], '%Y-%m-%d')
        generate_financial_report(message, start_date, end_date)
    except ValueError:
        bot.reply_to(message, "⚠️ صيغة التاريخ خاطئة: `YYYY-MM-DD`")

@bot.message_handler(commands=['اضافة_عامل'])
def add_worker_command(message):
    data = get_data()
    if message.from_user.id != data['config']['main_admin']:
        return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    parts = message.text.split()
    if len(parts) != 5:
        return bot.reply_to(message, "صيغة خاطئة. استخدم:\n/اضافة_عامل [ID] [الاسم] [اليوزر] [الأجرة]")
    worker_id, name, username, rate_str = parts[1], parts[2], parts[3], parts[4]
    try:
        rate = float(rate_str)
        data['config']['workers'][worker_id] = {"name": name, "username": username, "rate": rate}
        update_data(data)
        bot.reply_to(message, f"✅ تم إضافة العامل '{name}' بنجاح.")
    except ValueError:
        bot.reply_to(message, "⚠️ الأجرة يجب أن تكون رقمًا.")

@bot.message_handler(commands=['حذف_عامل'])
def remove_worker_command(message):
    data = get_data()
    if message.from_user.id != data['config']['main_admin']:
        return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    parts = message.text.split()
    if len(parts) != 2: return bot.reply_to(message, "صيغة خاطئة. استخدم: /حذف_عامل [ID]")
    worker_id_to_remove = parts[1]
    if worker_id_to_remove in data['config']['workers']:
        removed_name = data['config']['workers'].pop(worker_id_to_remove)['name']
        update_data(data)
        bot.reply_to(message, f"🗑️ تم حذف العامل '{removed_name}' من النظام.")
    else: bot.reply_to(message, "لم يتم العثور على عامل بهذا الـ ID.")

@bot.message_handler(commands=['تصفير_عامل'])
def reset_worker_command(message):
    data = get_data()
    if message.from_user.id != data['config']['main_admin']:
        return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    parts = message.text.split()
    if len(parts) != 2: return bot.reply_to(message, "صيغة خاطئة. استخدم: /تصفير_عامل [ID]")
    try:
        worker_id_to_reset = int(parts[1])
        total_paid_quantity = 0
        for order in data["orders"]:
            if order.get("worker_id") == worker_id_to_reset and not order.get("paid"):
                total_paid_quantity += order.get("quantity", 0)
                order["paid"] = True
        update_data(data)
        bot.reply_to(message, f"💸 تم تصفير مستحقات العامل (ID: {worker_id_to_reset}).\nإجمالي الكمية التي تم تصفيرها: {total_paid_quantity}.")
    except ValueError: bot.reply_to(message, "الـ ID يجب أن يكون رقمًا.")

@bot.message_handler(commands=['تصفير_الكل'])
def reset_command(message):
    data = get_data()
    if message.from_user.id not in data['config']['admins']:
        return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("نعم، أرشفة غير المدفوع", callback_data="confirm_reset"), types.InlineKeyboardButton("إلغاء", callback_data="cancel_reset"))
    bot.send_message(message.chat.id, "🚨 **تحذير:** هل أنت متأكد أنك تريد أرشفة جميع بيانات العمل **غير المدفوعة**؟", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_reset", "cancel_reset"])
def handle_reset_callback(call):
    data = get_data()
    if call.from_user.id not in data['config']['admins']: return bot.answer_callback_query(call.id, "🚫 ليس لديك الصلاحية لهذا الإجراء.")
    if call.data == "confirm_reset":
        for order in data["orders"]:
            if not order.get("paid"): order["paid"] = True
        update_data(data)
        bot.edit_message_text("✅ تم أرشفة جميع بيانات العمل غير المدفوعة بنجاح.", call.message.chat.id, call.message.message_id)
    else: bot.edit_message_text("👍 تم إلغاء العملية.", call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['متوسط_السعر'])
def average_price_command(message):
    data = get_data()
    if message.from_user.id not in data['config']['average_price_users']:
        return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    numbers = re.findall(r'[\d\.]+', message.text)
    if not numbers: return bot.reply_to(message, "لم يتم العثور على أرقام. أدخل الأسعار بعد الأمر.")
    prices = [float(n) for n in numbers]
    average = sum(prices) / len(prices)
    bot.reply_to(message, f"📊 متوسط السعر هو: *${average:.2f}*", parse_mode='Markdown')

@bot.message_handler(commands=['نسخة_احتياطية'])
def backup_command(message):
    data = get_data()
    if message.from_user.id != data['config']['main_admin']:
        return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    try:
        if '_id' in data: del data['_id']
        data_str = json.dumps(data, indent=4, ensure_ascii=False, default=str)
        data_bytes = io.BytesIO(data_str.encode('utf-8'))
        data_bytes.name = f"backup-{datetime.now().strftime('%Y-%m-%d')}.json"
        bot.send_document(message.chat.id, data_bytes, caption=f"💾 نسخة احتياطية من قاعدة البيانات بتاريخ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    except Exception as e:
        bot.reply_to(message, "حدث خطأ أثناء إنشاء النسخة الاحتياطية.")
        print(f"Backup Error: {e}")

# --- نظام التشغيل ---
if __name__ == "__main__":
    get_data() # Ensure data structure exists on first run
    print("O7 Bot System: Polling for messages...")
    bot.polling(none_stop=True)
