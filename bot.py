# -*- coding: utf-8 -*-
import os
import telebot
import schedule
import time
import threading
import json
import re
from datetime import datetime, timedelta

# --- إعدادات بوت O7 الخاصة ---
# سيتم قراءة التوكن من بيئة الاستضافة لضمان الأمان
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN_HERE')

# ملف تخزين البيانات الخاص بالبوت
DATA_FILE = 'data.json'

# --- ✅ بيانات فريقك الحقيقية ---

# 👑 المشرف صاحب التحكم الكامل (معتز)
ADMIN_USER_ID = 5615500221

# 👨‍💼 مرسلو الطلبات (الأشخاص المصرح لهم بإرسال الأوامر)
AUTHORIZED_SENDERS = {
    6795122268: "عمر",
    6940043771: "اسامه"
}

# 👷‍♂️ المنفذون (العمال الذين يردون بـ "تم")
AUTHORIZED_WORKERS = {
    5615500221: {"name": "معتز", "username": "@o7_7gg"},
    6795122268: {"name": "عمر", "username": "@B3NEI"},
    6940043771: {"name": "اسامه", "username": "@i_x_u"}
}

# --- نهاية قسم البيانات ---


# تهيئة البوت
bot = telebot.TeleBot(TELEGRAM_TOKEN)
print("O7 Bot System: Online and ready.")


# --- ✨ وظيفة جديدة: رسالة الترحيب ✨ ---
@bot.message_handler(commands=['start'], func=lambda message: message.chat.type == 'private')
def handle_start(message):
    """يرسل رسالة ترحيبية وإرشادية عند بدء محادثة خاصة مع البوت."""
    welcome_message = "مرحبًا، أنا بوت O7 جاهز للعمل.\n\nأضفني إلى مجموعتك وقم بترقيتي إلى مشرف مع صلاحية حذف الرسائل لكي أبدأ في إدارة الطلبات."
    bot.reply_to(message, welcome_message)
    print(f"O7 Bot System: Sent welcome message to user {message.from_user.id}.")


# --- دوال مساعدة لإدارة البيانات ---

def load_data():
    """تحميل البيانات من ملف JSON."""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
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

# --- معالجات رسائل البوت الأساسية في المجموعة ---

@bot.message_handler(func=lambda message: message.from_user.id in AUTHORIZED_SENDERS and message.chat.type in ['group', 'supergroup'])
def handle_new_order(message):
    quantity = parse_quantity(message.text)
    if not quantity: return

    data = load_data()
    if data.get("group_chat_id") is None:
        data["group_chat_id"] = message.chat.id
        print(f"O7 Bot System: Group chat ID locked to {message.chat.id}")

    new_order = {
        "message_id": message.message_id, "chat_id": message.chat.id, "text": message.text, "quantity": quantity,
        "requester_id": message.from_user.id, "requester_name": AUTHORIZED_SENDERS.get(message.from_user.id),
        "status": "pending", "worker_id": None, "worker_name": None, "worker_username": None,
        "request_time": datetime.now().isoformat(), "completion_time": None
    }
    data["orders"].append(new_order)
    save_data(data)
    print(f"O7 Bot System: New order logged for quantity {quantity}.")

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
                "status": "completed",
                "worker_id": message.from_user.id, "worker_name": worker_info.get("name"),
                "worker_username": worker_info.get("username"), "completion_time": datetime.now().isoformat()
            })
            save_data(data)
            print(f"O7 Bot System: Order {order['message_id']} completed by {worker_info.get('name')}.")
            order_found = True
            break
            
    # 🧹 حذف رسالة "تم" ورسالة الطلب الأصلية
    if order_found:
        try:
            bot.delete_message(chat_id, original_order_message_id)
            print(f"O7 Bot System: Original order message {original_order_message_id} deleted.")
        except Exception as e:
            print(f"O7 Bot System: FAILED to delete original message. CHECK PERMISSIONS. Error: {e}")
    
    try:
        bot.delete_message(chat_id, message.message_id)
        print(f"O7 Bot System: 'تم' message {message.message_id} deleted.")
    except Exception as e:
        print(f"O7 Bot System: FAILED to delete 'تم' message. CHECK PERMISSIONS. Error: {e}")


# --- ✨ نظام التقارير الموحد والذكي ✨ ---
def generate_custom_report(chat_id, start_date, end_date):
    """ينشئ تقريرًا مخصصًا لفترة زمنية محددة."""
    data = load_data()
    # إضافة يوم واحد للتاريخ النهائي ليشمل كل اليوم عند استخدام نطاق
    end_date_inclusive = end_date + timedelta(days=1)

    filtered_orders = [
        o for o in data["orders"] 
        if o["status"] == "completed" and o.get("completion_time") and
           start_date <= datetime.fromisoformat(o["completion_time"]) < end_date_inclusive
    ]

    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    # تحديد عنوان التقرير بناءً على ما إذا كانت الفترة يومًا واحدًا أم نطاقًا
    if start_str == end_str:
        report_title = f"📊 **تقرير O7 ليوم {start_str}**"
    else:
        report_title = f"📊 **إحصائيات O7 من {start_str} إلى {end_str}**"

    if not filtered_orders:
        report_text = f"{report_title}\n\nلا توجد طلبات منفذة في هذه الفترة."
    else:
        report_text = f"{report_title}\n\n"
        worker_summary = {}
        for order in filtered_orders:
            name = order.get("worker_name", "غير معروف")
            if name not in worker_summary: worker_summary[name] = {"count": 0, "total_quantity": 0}
            worker_summary[name]["count"] += 1
            worker_summary[name]["total_quantity"] += order.get("quantity", 0)
        
        total_completed = len(filtered_orders)
        total_quantity_all = sum(s['total_quantity'] for s in worker_summary.values())
        
        report_text += f"✨ *إجمالي الطلبات المنفذة: {total_completed}*\n"
        report_text += f"📦 *إجمالي الكميات: {total_quantity_all}*\n--------------------\n"
        for worker, summary in worker_summary.items():
            report_text += f"👷‍♂️ *{worker}*: {summary['count']} طلبات (إجمالي الكمية: {summary['total_quantity']})\n"
            
    bot.send_message(chat_id, report_text, parse_mode='Markdown')

# تم دمج كل أوامر التقارير هنا
@bot.message_handler(commands=['report', 'تقرير', 'stats', 'احصائيات'])
def handle_all_report_commands(message):
    """
    يعالج جميع طلبات التقارير بذكاء.
    - /report, /stats, etc: يعطي تقرير اليوم لأي مستخدم مصرح له.
    - /stats YYYY-MM-DD YYYY-MM-DD: يعطي تقريرًا مخصصًا للمشرف فقط.
    """
    user_id = message.from_user.id
    parts = message.text.split()

    # الحالة 1: تقرير اليوم (الأمر بدون تواريخ)
    if len(parts) == 1:
        if user_id in AUTHORIZED_WORKERS or user_id in AUTHORIZED_SENDERS:
            bot.reply_to(message, "👍 حسنًا، جاري إعداد تقرير اليوم...")
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            generate_custom_report(message.chat.id, today, today)
        else:
            print(f"O7 Bot System: Unauthorized daily report request from user {user_id}.")
        return

    # الحالة 2: تقرير مخصص للمشرف (الأمر مع تواريخ)
    if len(parts) == 3:
        if user_id != ADMIN_USER_ID:
            bot.reply_to(message, "🚫 هذا الأمر مع التواريخ مخصص للمشرف فقط.")
            return

        try:
            start_date = datetime.strptime(parts[1], '%Y-%m-%d')
            end_date = datetime.strptime(parts[2], '%Y-%m-%d')
            bot.reply_to(message, "👍 حسنًا، جاري إعداد التقرير المخصص للفترة المطلوبة...")
            generate_custom_report(message.chat.id, start_date, end_date)
        except ValueError:
            bot.reply_to(message, "⚠️ صيغة التاريخ خاطئة.\nالرجاء استخدام: `YYYY-MM-DD`")
        return
    
    # الحالة 3: صيغة خاطئة
    bot.reply_to(message, "⚠️ صيغة الأمر خاطئة.\n- للحصول على تقرير اليوم: `/تقرير`\n- للمشرف فقط: `/احصائيات YYYY-MM-DD YYYY-MM-DD`")


# --- نظام التشغيل والجدولة ---
def run_scheduler():
    # الجدولة التلقائية للتقرير اليومي
    def send_daily_report():
        chat_id = load_data().get("group_chat_id")
        if chat_id:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            generate_custom_report(chat_id, today, today)

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
