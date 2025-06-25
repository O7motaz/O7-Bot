# -*- coding: utf-8 -*-
import os
import telebot
import schedule
import time
import threading
import json
import re
from datetime import datetime

# --- إعدادات بوت O7 الخاصة ---
# سيتم قراءة التوكن من بيئة الاستضافة لضمان الأمان
# لا تضع التوكن هنا مباشرة في النسخة النهائية
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN_HERE')

# ملف تخزين البيانات الخاص بالبوت
DATA_FILE = 'data.json'

# --- ⚠️ قسم التعديل: أدخل بيانات فريقك هنا ---

# 👨‍💼 مرسلو الطلبات (الأشخاص المصرح لهم بإرسال الأوامر)
# استبدل الأرقام والأسماء بالبيانات الحقيقية التي جمعتها
AUTHORIZED_SENDERS = {
    123456789: "مالك",
    987654321: "ليث"
}

# 👷‍♂️ المنفذون (العمال الذين يردون بـ "تم")
# استبدل كل البيانات أدناه ببيانات فريقك الحقيقية
AUTHORIZED_WORKERS = {
    111111111: {"name": "أحمد", "username": "@ahmad_user"},
    222222222: {"name": "سارة", "username": "@sara_user"},
    333333333: {"name": "مالك", "username": "@malik_worker_user"},
    444444444: {"name": "تالا", "username": "@tala_user"}
}

# --- نهاية قسم التعديل ---


# تهيئة البوت
bot = telebot.TeleBot(TELEGRAM_TOKEN)
print("O7 Bot System: Online and ready.")


# --- دوال مساعدة لإدارة البيانات ---

def load_data():
    """تحميل البيانات من ملف JSON."""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # في حال عدم وجود الملف، يتم إنشاء هيكل بيانات جديد
        return {"orders": [], "group_chat_id": None}


def save_data(data):
    """حفظ البيانات في ملف JSON."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def parse_quantity(text):
    """استخراج أي كمية رقمية من النص بدقة."""
    eastern_to_western = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    processed_text = text.translate(eastern_to_western)
    match = re.search(r'\d+', processed_text)
    return int(match.group(0)) if match else None


# --- معالجات رسائل البوت الأساسية ---

# معالج الطلبات الجديدة
@bot.message_handler(
    func=lambda message: message.from_user.id in AUTHORIZED_SENDERS and message.chat.type in ['group', 'supergroup'])
def handle_new_order(message):
    quantity = parse_quantity(message.text)
    if not quantity: return  # تجاهل الرسالة إذا لم تحتوي على كمية

    data = load_data()
    if data.get("group_chat_id") is None:
        data["group_chat_id"] = message.chat.id
        print(f"O7 Bot System: Group chat ID locked to {message.chat.id}")

    new_order = {
        "message_id": message.message_id, "text": message.text, "quantity": quantity,
        "requester_id": message.from_user.id, "requester_name": AUTHORIZED_SENDERS.get(message.from_user.id),
        "status": "pending", "worker_id": None, "worker_name": None, "worker_username": None,
        "request_time": datetime.now().isoformat(), "completion_time": None
    }
    data["orders"].append(new_order)
    save_data(data)
    print(f"O7 Bot System: New order logged for quantity {quantity}.")


# معالج ردود "تم" من العمال
@bot.message_handler(func=lambda
        message: message.text and message.text.strip().lower() == "تم" and message.from_user.id in AUTHORIZED_WORKERS and message.reply_to_message)
def handle_order_completion(message):
    data = load_data()
    worker_info = AUTHORIZED_WORKERS.get(message.from_user.id)

    # تحديث الطلب الأصلي
    for order in data["orders"]:
        if order["message_id"] == message.reply_to_message.message_id and order["status"] == "pending":
            order.update({
                "status": "completed",
                "worker_id": message.from_user.id,
                "worker_name": worker_info.get("name"),
                "worker_username": worker_info.get("username"),
                "completion_time": datetime.now().isoformat()
            })
            save_data(data)
            print(f"O7 Bot System: Order {order['message_id']} completed by {worker_info.get('name')}.")
            break

    # حذف رسالة "تم" في كل الحالات
    try:
        bot.delete_message(message.chat.id, message.message_id)
        print(f"O7 Bot System: 'تم' message deleted successfully.")
    except Exception as e:
        print(f"O7 Bot System: Failed to delete message. Reason: {e}")


# --- نظام التقارير ---
def generate_and_send_report(chat_id):
    if not chat_id:
        print("O7 Bot System: Report generation failed. Chat ID not available.")
        return

    data = load_data()
    today_str = datetime.now().strftime('%Y-%m-%d')
    completed_today = [o for o in data["orders"] if
                       o["status"] == "completed" and o["completion_time"] and o["completion_time"].startswith(
                           today_str)]

    if not completed_today:
        report_text = f"📋 **تقرير O7 ليوم {today_str}**\n\nلم يتم تنفيذ أي طلبات اليوم."
    else:
        report_text = f"📋 **تقرير O7 ليوم {today_str}**\n\n"
        worker_summary = {}
        for order in completed_today:
            name = order.get("worker_name", "غير معروف")
            if name not in worker_summary: worker_summary[name] = {"count": 0, "total_quantity": 0}
            worker_summary[name]["count"] += 1
            worker_summary[name]["total_quantity"] += order.get("quantity", 0)

        report_text += f"✨ *إجمالي الطلبات المنفذة: {len(completed_today)}*\n--------------------\n"
        for worker, summary in worker_summary.items():
            report_text += f"👷‍♂️ *{worker}*: {summary['count']} طلبات (إجمالي الكمية: {summary['total_quantity']})\n"

    try:
        bot.send_message(chat_id, report_text, parse_mode='Markdown')
        print(f"O7 Bot System: Daily report sent to group {chat_id}.")
    except Exception as e:
        print(f"O7 Bot System: Failed to send report. Reason: {e}")


# أمر يدوي للتقرير
@bot.message_handler(commands=['report', 'تقرير'])
def manual_report_command(message):
    user_id = message.from_user.id
    if user_id in AUTHORIZED_SENDERS or user_id in AUTHORIZED_WORKERS:
        generate_and_send_report(message.chat.id)
    else:
        # البوت يتجاهل الأمر بصمت إذا كان من شخص غير مصرح له
        print(f"O7 Bot System: Unauthorized report request from user {user_id}.")


# --- نظام التشغيل والجدولة ---
def run_scheduler():
    schedule.every().day.at("23:59").do(lambda: generate_and_send_report(load_data().get("group_chat_id")))
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