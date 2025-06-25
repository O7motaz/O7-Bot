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

# --- إعدادات بوت O7 الخاصة ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN_HERE')
DATA_FILE = 'data.json'

bot = telebot.TeleBot(TELEGRAM_TOKEN)
print("O7 Bot System: Online with HR & Payroll Management.")

# --- دوال مساعدة لإدارة البيانات ---
def load_data():
    """تحميل البيانات من ملف JSON. إذا لم يكن موجودًا، يتم إنشاؤه بهيكل أساسي."""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # الهيكل الأساسي للبيانات عند أول تشغيل
        return {
            "group_chat_id": None,
            "config": {
                "admins": [5615500221, 6795122268, 6940043771],
                "workers": {
                    "5615500221": {"name": "معتز", "username": "@o7_7gg", "rate": 4.5},
                    "6795122268": {"name": "عمر", "username": "@B3NEI", "rate": 4.5},
                    "6940043771": {"name": "اسامه", "username": "@i_x_u", "rate": 4.5}
                },
                "average_price_users": [6795122268, 6940043771]
            },
            "orders": []
        }

def save_data(data):
    """حفظ البيانات في ملف JSON."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def parse_quantity(text):
    match = re.search(r'\d+', text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
    return int(match.group(0)) if match else None

# --- ✨ رسالة المساعدة الشاملة ✨ ---
@bot.message_handler(commands=['start'], func=lambda message: message.chat.type == 'private')
def handle_start(message):
    help_text = """
👋 **أهلاً بك في بوت O7 لإدارة العمليات**

**📋 الأوامر الأساسية لجميع العمال:**
- `/تقرير`: تقرير عملك لليوم الحالي.
- `/my_report [تاريخ بداية] [تاريخ نهاية]`: تقرير مفصل لعملك خلال فترة محددة.
  (مثال: `/my_report 2024-05-01 2024-05-31`)

**👑 أوامر المشرفين (معتز, عمر, اسامه):**
- `/احصائيات`: تقرير شامل لعمل جميع الفريق لليوم.
- `/احصائيات [تاريخ بداية] [تاريخ نهاية]`: تقرير شامل عن فترة محددة.
- `/reset`: لإعادة تعيين بيانات العمل غير المدفوعة **لجميع العمال**.

**💼 أوامر الإدارة العليا (معتز فقط):**
- `/add_worker [ID] [الاسم] [اليوزر] [الأجرة]`: لإضافة عامل جديد.
  (مثال: `/add_worker 123456789 علي @ali_user 4.0`)
- `/remove_worker [ID]`: لحذف عامل من النظام.
- `/reset_worker [ID]`: لتصفير مستحقات عامل معين بعد دفع أجره.

**حاسبة خاصة (لأسامة وعمر):**
- `/مجموع_الاعمال [أرقام]`: لحساب متوسط سعر.
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

# --- معالجات الرسائل الأساسية ---
@bot.message_handler(func=lambda message: str(message.from_user.id) in load_data()['config']['workers'] and message.chat.type in ['group', 'supergroup'] and not message.text.startswith('/'))
def handle_new_order(message):
    data = load_data()
    quantity = parse_quantity(message.text)
    if not quantity: return
    if data.get("group_chat_id") is None: data["group_chat_id"] = message.chat.id
    requester_info = data['config']['workers'].get(str(message.from_user.id), {})
    new_order = {
        "message_id": message.message_id, "chat_id": message.chat.id, "text": message.text, "quantity": quantity,
        "requester_id": message.from_user.id, "requester_name": requester_info.get("name"), "status": "pending",
        "worker_id": None, "worker_name": None, "worker_username": None, "paid": False,
        "request_time": datetime.now().isoformat(), "completion_time": None
    }
    data["orders"].append(new_order)
    save_data(data)

@bot.message_handler(func=lambda message: message.text and message.text.strip().lower() == "تم" and str(message.from_user.id) in load_data()['config']['workers'] and message.reply_to_message)
def handle_order_completion(message):
    data = load_data()
    worker_info = data['config']['workers'].get(str(message.from_user.id))
    original_order_message_id = message.reply_to_message.message_id
    chat_id = message.chat.id
    order_found = False
    for order in data["orders"]:
        if order["message_id"] == original_order_message_id and order["status"] == "pending":
            order.update({
                "status": "completed", "worker_id": message.from_user.id, "worker_name": worker_info.get("name"),
                "worker_username": worker_info.get("username"), "completion_time": datetime.now().isoformat()
            })
            save_data(data)
            order_found = True
            break
    if order_found:
        try: bot.delete_message(chat_id, original_order_message_id)
        except Exception as e: print(f"O7 ERROR: Could not delete ORIGINAL message. Check permissions. {e}")
    try: bot.delete_message(chat_id, message.message_id)
    except Exception as e: print(f"O7 ERROR: Could not delete 'تم' message. Check permissions. {e}")

# --- نظام التقارير المالي ---
def generate_financial_report(chat_id, start_date, end_date, for_user_id=None):
    data = load_data()
    end_date_inclusive = end_date + timedelta(days=1)
    # فلترة الطلبات غير المدفوعة فقط
    unpaid_orders = [o for o in data["orders"] if o["status"] == "completed" and not o.get("paid")]
    
    # فلترة إضافية حسب التاريخ والمستخدم (إذا تم تحديده)
    filtered_orders = [
        o for o in unpaid_orders if o.get("completion_time") and 
        start_date <= datetime.fromisoformat(o["completion_time"]) < end_date_inclusive and
        (for_user_id is None or o.get("worker_id") == for_user_id)
    ]
    
    start_str, end_str = start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    report_title = f"📊 **تقرير O7 ليوم {start_str}**" if start_str == end_str else f"📊 **إحصائيات O7 من {start_str} إلى {end_str}**"
    if for_user_id: report_title = f"📄 **تقرير عملك الشخصي**"
    
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
            
    bot.send_message(chat_id, report_text, parse_mode='Markdown')

# --- 👑 أوامر الإدارة العليا (معتز فقط) ---
@bot.message_handler(commands=['add_worker'])
def add_worker_command(message):
    data = load_data()
    if message.from_user.id != data['config']['admins'][0]: return # معتز فقط
    parts = message.text.split()
    if len(parts) != 5:
        bot.reply_to(message, "صيغة خاطئة. استخدم:\n/add_worker [ID] [الاسم] [اليوزر] [الأجرة]")
        return
    worker_id, name, username, rate_str = parts[1], parts[2], parts[3], parts[4]
    try:
        rate = float(rate_str)
        data['config']['workers'][worker_id] = {"name": name, "username": username, "rate": rate}
        save_data(data)
        bot.reply_to(message, f"✅ تم إضافة العامل '{name}' بنجاح.")
    except ValueError:
        bot.reply_to(message, "⚠️ الأجرة يجب أن تكون رقمًا.")

@bot.message_handler(commands=['remove_worker'])
def remove_worker_command(message):
    data = load_data()
    if message.from_user.id != data['config']['admins'][0]: return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "صيغة خاطئة. استخدم: /remove_worker [ID]")
        return
    worker_id_to_remove = parts[1]
    if worker_id_to_remove in data['config']['workers']:
        removed_name = data['config']['workers'].pop(worker_id_to_remove)['name']
        save_data(data)
        bot.reply_to(message, f"🗑️ تم حذف العامل '{removed_name}' من النظام.")
    else:
        bot.reply_to(message, "لم يتم العثور على عامل بهذا الـ ID.")

@bot.message_handler(commands=['reset_worker'])
def reset_worker_command(message):
    data = load_data()
    if message.from_user.id != data['config']['admins'][0]: return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "صيغة خاطئة. استخدم: /reset_worker [ID]")
        return
    try:
        worker_id_to_reset = int(parts[1])
        total_paid_quantity = 0
        for order in data["orders"]:
            if order.get("worker_id") == worker_id_to_reset and not order.get("paid"):
                total_paid_quantity += order.get("quantity", 0)
                order["paid"] = True
        save_data(data)
        bot.reply_to(message, f"💸 تم تصفير مستحقات العامل (ID: {worker_id_to_reset}).\nإجمالي الكمية التي تم تصفيرها: {total_paid_quantity}.")
    except ValueError:
        bot.reply_to(message, "الـ ID يجب أن يكون رقمًا.")

# --- الأوامر الإدارية والعامة ---
@bot.message_handler(commands=['report', 'تقرير', 'stats', 'احصائيات'])
def handle_all_report_commands(message):
    data, user_id, parts = load_data(), message.from_user.id, message.text.split()
    is_admin = user_id in data['config']['admins']
    
    if len(parts) == 1:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        generate_financial_report(message.chat.id, today, today, for_user_id=None if is_admin else user_id)
    elif len(parts) == 3 and is_admin:
        try:
            start_date = datetime.strptime(parts[1], '%Y-%m-%d')
            end_date = datetime.strptime(parts[2], '%Y-%m-%d')
            generate_financial_report(message.chat.id, start_date, end_date)
        except ValueError: bot.reply_to(message, "⚠️ صيغة التاريخ خاطئة: `YYYY-MM-DD`")
    elif len(parts) == 3 and not is_admin:
        bot.reply_to(message, "🚫 هذا الأمر مع التواريخ مخصص للمشرفين فقط.")

@bot.message_handler(commands=['my_report'])
def my_report_command(message):
    user_id, parts = message.from_user.id, message.text.split()
    if len(parts) == 3:
        try:
            start_date = datetime.strptime(parts[1], '%Y-%m-%d')
            end_date = datetime.strptime(parts[2], '%Y-%m-%d')
            generate_financial_report(message.chat.id, start_date, end_date, for_user_id=user_id)
        except ValueError: bot.reply_to(message, "⚠️ صيغة التاريخ خاطئة: `YYYY-MM-DD`")
    else:
        bot.reply_to(message, "صيغة خاطئة. استخدم:\n/my_report [YYYY-MM-DD] [YYYY-MM-DD]")

@bot.message_handler(commands=['reset'])
def reset_command(message):
    data = load_data()
    if message.from_user.id not in data['config']['admins']: return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("نعم، حذف غير المدفوع", callback_data="confirm_reset"), types.InlineKeyboardButton("إلغاء", callback_data="cancel_reset"))
    bot.send_message(message.chat.id, "🚨 **تحذير:** هل أنت متأكد أنك تريد حذف جميع بيانات العمل **غير المدفوعة**؟", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_reset", "cancel_reset"])
def handle_reset_callback(call):
    data = load_data()
    if call.from_user.id not in data['config']['admins']: return
    if call.data == "confirm_reset":
        # الإبقاء على الطلبات المدفوعة وحذف غير المدفوعة فقط
        data["orders"] = [o for o in data["orders"] if o.get("paid")]
        save_data(data)
        bot.edit_message_text("✅ تم حذف جميع بيانات العمل غير المدفوعة.", call.message.chat.id, call.message.message_id)
    else:
        bot.edit_message_text("👍 تم إلغاء العملية.", call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['average_price', 'مجموع_الاعمال'])
def average_price_command(message):
    data = load_data()
    if message.from_user.id not in data['config']['average_price_users']: return
    numbers = re.findall(r'[\d\.]+', message.text)
    if not numbers:
        bot.reply_to(message, "لم يتم العثور على أرقام. أدخل الأسعار بعد الأمر.")
        return
    prices = [float(n) for n in numbers]
    average = sum(prices) / len(prices)
    bot.reply_to(message, f"📊 متوسط السعر هو: *${average:.2f}*", parse_mode='Markdown')

# --- نظام التشغيل ---
def run_scheduler():
    # ... جدولة التقارير اليومية يمكن إضافتها هنا إذا لزم الأمر ...
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    save_data(load_data()) # لضمان إنشاء الملف عند أول تشغيل
    print("O7 Bot System: Scheduler activated.")
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("O7 Bot System: Polling for messages...")
    bot.polling(none_stop=True)
