# -*- coding: utf-8 -*-
import os
import telebot
from telebot import types # تم استيرادها من أجل أزرار التأكيد
import schedule
import time
import threading
import json
import re
from datetime import datetime, timedelta

# --- إعدادات بوت O7 الخاصة ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN_HERE')
DATA_FILE = 'data.json'

# --- ✅ بيانات فريقك وصلاحياته وأجوره ---

# 👑 المشرف صاحب التحكم الكامل (معتز)
ADMIN_USER_ID = 5615500221

# 💵 قائمة أجور العمال (لكل 100 وحدة)
# يمكنك تعديل الأجور أو إضافة عمال جدد هنا
WORKER_RATES = {
    5615500221: 4.5,  # معتز
    6795122268: 4.5,  # عمر
    6940043771: 4.5   # اسامه
}

# 👨‍💼 مرسلو الطلبات
AUTHORIZED_SENDERS = {
    6795122268: "عمر",
    6940043771: "اسامه"
}

# 👷‍♂️ المنفذون
AUTHORIZED_WORKERS = {
    5615500221: {"name": "معتز", "username": "@o7_7gg"},
    6795122268: {"name": "عمر", "username": "@B3NEI"},
    6940043771: {"name": "اسامه", "username": "@i_x_u"}
}

# 👥 المستخدمون المصرح لهم باستخدام حاسبة المتوسط (أسامة وعمر)
AVERAGE_PRICE_USERS = {6795122268, 6940043771}


# --- نهاية قسم البيانات ---


bot = telebot.TeleBot(TELEGRAM_TOKEN)
print("O7 Bot System: Online and ready with Advanced Features.")

# --- دوال مساعدة ---
def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"orders": [], "group_chat_id": None}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)

def parse_quantity(text):
    match = re.search(r'\d+', text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
    return int(match.group(0)) if match else None

# --- معالجات الرسائل الأساسية ---

@bot.message_handler(commands=['start'], func=lambda message: message.chat.type == 'private')
def handle_start(message):
    welcome_message = "مرحبًا، أنا بوت O7 جاهز للعمل.\n\nأضفني إلى مجموعتك وقم بترقيتي إلى مشرف مع صلاحية حذف الرسائل لكي أبدأ في إدارة الطلبات."
    bot.reply_to(message, welcome_message)

@bot.message_handler(func=lambda message: message.from_user.id in AUTHORIZED_SENDERS and message.chat.type in ['group', 'supergroup'])
def handle_new_order(message):
    quantity = parse_quantity(message.text)
    if not quantity: return
    data = load_data()
    if data.get("group_chat_id") is None: data["group_chat_id"] = message.chat.id
    new_order = {
        "message_id": message.message_id, "chat_id": message.chat.id, "text": message.text, "quantity": quantity,
        "requester_id": message.from_user.id, "requester_name": AUTHORIZED_SENDERS.get(message.from_user.id),
        "status": "pending", "worker_id": None, "worker_name": None, "worker_username": None,
        "request_time": datetime.now().isoformat(), "completion_time": None
    }
    data["orders"].append(new_order)
    save_data(data)

@bot.message_handler(func=lambda message: message.text and message.text.strip().lower() == "تم" and message.from_user.id in AUTHORIZED_WORKERS and message.reply_to_message)
def handle_order_completion(message):
    data = load_data()
    worker_info = AUTHORIZED_WORKERS.get(message.from_user.id)
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
        except Exception as e: print(f"O7 FATAL ERROR: Could not delete ORIGINAL message {original_order_message_id}. BOT MUST BE ADMIN WITH DELETE PERMISSIONS. Error: {e}")
    try: bot.delete_message(chat_id, message.message_id)
    except Exception as e: print(f"O7 FATAL ERROR: Could not delete 'تم' message {message.message_id}. BOT MUST BE ADMIN. Error: {e}")

# --- نظام التقارير المالي ---
def generate_financial_report(chat_id, start_date, end_date):
    data = load_data()
    end_date_inclusive = end_date + timedelta(days=1)
    filtered_orders = [o for o in data["orders"] if o["status"] == "completed" and o.get("completion_time") and start_date <= datetime.fromisoformat(o["completion_time"]) < end_date_inclusive]
    start_str, end_str = start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    report_title = f"📊 **تقرير O7 ليوم {start_str}**" if start_str == end_str else f"📊 **إحصائيات O7 من {start_str} إلى {end_str}**"
    if not filtered_orders:
        report_text = f"{report_title}\n\nلا توجد طلبات منفذة في هذه الفترة."
    else:
        report_text = f"{report_title}\n\n"
        worker_summary = {}
        for order in filtered_orders:
            worker_id = order.get("worker_id")
            name = order.get("worker_name", "غير معروف")
            if name not in worker_summary: worker_summary[name] = {"count": 0, "total_quantity": 0, "id": worker_id}
            worker_summary[name]["count"] += 1
            worker_summary[name]["total_quantity"] += order.get("quantity", 0)
        total_completed = len(filtered_orders)
        total_quantity_all = sum(s['total_quantity'] for s in worker_summary.values())
        report_text += f"✨ *إجمالي الطلبات: {total_completed}* | 📦 *إجمالي الكميات: {total_quantity_all}*\n--------------------\n"
        for worker, summary in worker_summary.items():
            rate = WORKER_RATES.get(summary["id"], 0)
            wage = (summary['total_quantity'] / 100) * rate if rate > 0 else 0
            report_text += f"👷‍♂️ *{worker}*: {summary['count']} طلبات (كمية: {summary['total_quantity']})"
            if wage > 0: report_text += f" | 💰 *الأجر: ${wage:.2f}*"
            report_text += "\n"
    bot.send_message(chat_id, report_text, parse_mode='Markdown')

# --- الأوامر الإدارية ---
@bot.message_handler(commands=['report', 'تقرير', 'stats', 'احصائيات'])
def handle_all_report_commands(message):
    user_id, parts = message.from_user.id, message.text.split()
    is_authorized = user_id in AUTHORIZED_WORKERS or user_id in AUTHORIZED_SENDERS
    if len(parts) == 1 and is_authorized:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        generate_financial_report(message.chat.id, today, today)
    elif len(parts) == 3 and user_id == ADMIN_USER_ID:
        try:
            start_date = datetime.strptime(parts[1], '%Y-%m-%d')
            end_date = datetime.strptime(parts[2], '%Y-%m-%d')
            generate_financial_report(message.chat.id, start_date, end_date)
        except ValueError: bot.reply_to(message, "⚠️ صيغة التاريخ خاطئة: `YYYY-MM-DD`")
    elif len(parts) == 3 and user_id != ADMIN_USER_ID:
        bot.reply_to(message, "🚫 هذا الأمر مع التواريخ مخصص للمشرف فقط.")
    elif not is_authorized: return
    else: bot.reply_to(message, "⚠️ صيغة الأمر خاطئة.")

@bot.message_handler(commands=['reset'])
def reset_command(message):
    """يبدأ عملية إعادة تعيين البيانات (للمشرف فقط)."""
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "🚫 هذا الأمر مخصص للمشرف فقط.")
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    confirm_btn = types.InlineKeyboardButton("نعم، قم بإعادة التعيين", callback_data="confirm_reset")
    cancel_btn = types.InlineKeyboardButton("إلغاء", callback_data="cancel_reset")
    markup.add(confirm_btn, cancel_btn)
    bot.send_message(message.chat.id, "🚨 **تحذير:** هل أنت متأكد أنك تريد حذف جميع بيانات الطلبات بشكل نهائي؟ لا يمكن التراجع عن هذا الإجراء.", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_reset", "cancel_reset"])
def handle_reset_callback(call):
    """يعالج رد التأكيد على إعادة التعيين."""
    if call.from_user.id != ADMIN_USER_ID: return # تجاهل إذا لم يكن المشرف
    if call.data == "confirm_reset":
        data = load_data()
        data["orders"] = []
        save_data(data)
        bot.edit_message_text("✅ تم حذف جميع بيانات الطلبات بنجاح.", call.message.chat.id, call.message.message_id)
    else:
        bot.edit_message_text("👍 تم إلغاء عملية إعادة التعيين.", call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['average_price', 'مجموع_الاعمال'])
def average_price_command(message):
    """حاسبة المتوسط الحسابي للأسعار (لأسامة وعمر)."""
    if message.from_user.id not in AVERAGE_PRICE_USERS: return
    numbers = re.findall(r'\d+\.?\d*', message.text)
    if not numbers:
        bot.reply_to(message, "لم يتم العثور على أرقام. أدخل الأسعار بعد الأمر.\nمثال: `/average_price 4 3.5 2.2`")
        return
    prices = [float(n) for n in numbers]
    average = sum(prices) / len(prices)
    bot.reply_to(message, f"📊 متوسط السعر للقيم المدخلة هو: *${average:.2f}*", parse_mode='Markdown')

# --- نظام التشغيل والجدولة ---
def run_scheduler():
    def send_daily_report():
        chat_id = load_data().get("group_chat_id")
        if chat_id:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            generate_financial_report(chat_id, today, today)
    schedule.every().day.at("23:59").do(send_daily_report)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    print("O7 Bot System: Initializing data file...")
    save_data(load_data())
    print("O7 Bot System: Scheduler activated.")
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("O7 Bot System: Polling for messages...")
    bot.polling(none_stop=True)
