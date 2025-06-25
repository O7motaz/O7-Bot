import logging
import os
import re
from datetime import datetime, time

from pymongo import MongoClient
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters
from telegram.constants import ParseMode

# --- إعدادات أساسية ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- تحميل المتغيرات الحساسة ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
MONGO_URI = os.environ.get('MONGO_URI')

# --- الاتصال بقاعدة البيانات ---
try:
    client = MongoClient(MONGO_URI)
    db = client.get_database("reports_bot_db")
    tasks_collection = db.tasks
    logging.info("تم الاتصال بقاعدة بيانات MongoDB بنجاح.")
except Exception as e:
    logging.error(f"فشل الاتصال بقاعدة البيانات: {e}")
    exit()

# --- بيانات المستخدمين ---
USER_DATA = {
    6795122268: "عمر",
    6940043771: "اسامه",
    5615500221: "معتز"
}

# --- دوال الأوامر (تبقى كما هي) ---
async def done_command(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_name = USER_DATA.get(user.id, user.first_name)
    parts = update.message.text.split()
    
    if len(parts) < 2 or not parts[1].isdigit():
        await update.message.reply_text("❌ خطأ: يرجى إدخال الكمية المنجزة بعد الأمر.\nمثال: `/تم 150`")
        return
        
    quantity = int(parts[1])
    
    task_record = {
        "user_id": user.id,
        "user_name": user_name,
        "quantity": quantity,
        "completed_at": datetime.now()
    }
    tasks_collection.insert_one(task_record)
    
    await update.message.reply_text(f"✅ تم تسجيل {quantity} تعزيز باسمك يا {user_name}!")

async def daily_report_command(update: Update, context: CallbackContext) -> None:
    today_start = datetime.combine(datetime.now().date(), time.min)
    today_end = datetime.combine(datetime.now().date(), time.max)
    
    pipeline = [
        {"$match": {"completed_at": {"$gte": today_start, "$lte": today_end}}},
        {"$group": {"_id": "$user_name", "total": {"$sum": "$quantity"}}},
        {"$sort": {"total": -1}}
    ]
    results = list(tasks_collection.aggregate(pipeline))
    
    today_str = datetime.now().date().strftime('%Y-%m-%d')
    if not results:
        report_text = f"📊 **التقرير اليومي ({today_str})** 📊\n\nلم يتم إنجاز أي مهام اليوم."
    else:
        report_text = f"📊 **التقرير اليومي ({today_str})** 📊\n\n"
        for res in results:
            report_text += f"- **{res['_id']}**: أنجز {res['total']} تعزيز\n"
    
    await update.message.reply_text(text=report_text, parse_mode=ParseMode.MARKDOWN)

async def full_report_command(update: Update, context: CallbackContext) -> None:
    pipeline = [
        {"$group": {"_id": "$user_name", "total": {"$sum": "$quantity"}}},
        {"$sort": {"total": -1}}
    ]
    results = list(tasks_collection.aggregate(pipeline))

    if not results:
        report_text = "📈 **التقرير المفصل** 📈\n\nلا توجد بيانات مسجلة حتى الآن."
    else:
        report_text = "📈 **التقرير المفصل** 📈\n\n"
        for res in results:
            report_text += f"- **{res['_id']}**: أنجز {res['total']} تعزيز\n"
    
    await update.message.reply_text(text=report_text, parse_mode=ParseMode.MARKDOWN)

async def calculate_payment_command(update: Update, context: CallbackContext) -> None:
    moataz_id = 5615500221
    payment_rate_per_100 = 4.5
    
    pipeline = [
        {"$match": {"user_id": moataz_id}},
        {"$group": {"_id": "$user_id", "total": {"$sum": "$quantity"}}}
    ]
    result = list(tasks_collection.aggregate(pipeline))

    payment_text = f"💵 **حساب مستحقات معتز** 💵\n\n"
    if not result or not result[0].get('total'):
        payment_text += "لم ينجز أي مهام حتى الآن."
    else:
        total_boosts = result[0]['total']
        amount_due = (total_boosts / 100) * payment_rate_per_100
        payment_text += f"- **إجمالي الإنجاز:** {total_boosts} تعزيز\n"
        payment_text += f"- **المبلغ المستحق:** `{amount_due:.2f}$`"

    await update.message.reply_text(text=payment_text, parse_mode=ParseMode.MARKDOWN)

async def reset_command(update: Update, context: CallbackContext) -> None:
    tasks_collection.delete_many({})
    await update.message.reply_text("✅ تم حذف جميع البيانات وبدء دورة جديدة.")

def main() -> None:
    if not BOT_TOKEN or not MONGO_URI:
        logging.error("المتغيرات (BOT_TOKEN, MONGO_URI) غير موجودة! يرجى إضافتها.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # --- ((( التعديل الجذري هنا ))) ---
    # تم تحويل جميع الأوامر التي لها أسماء عربية إلى MessageHandler
    
    # فلتر لأمر الإنجاز
    done_filter = filters.Regex(r'^(?:/done|/تم|/انجاز)\b')
    application.add_handler(MessageHandler(done_filter, done_command))

    # فلتر للتقرير اليومي
    daily_report_filter = filters.Regex(r'^(?:/daily_report|/يومي)\b')
    application.add_handler(MessageHandler(daily_report_filter, daily_report_command))

    # فلتر للتقرير المفصل
    full_report_filter = filters.Regex(r'^(?:/full_report|/مفصل)\b')
    application.add_handler(MessageHandler(full_report_filter, full_report_command))

    # فلتر لحساب المستحقات
    payment_filter = filters.Regex(r'^(?:/payment|/مستحقات)\b')
    application.add_handler(MessageHandler(payment_filter, calculate_payment_command))

    # فلتر لإعادة الضبط
    reset_filter = filters.Regex(r'^(?:/reset|/تصفير)\b')
    application.add_handler(MessageHandler(reset_filter, reset_command))

    logging.info("البوت قيد التشغيل...")
    application.run_polling()

if __name__ == '__main__':
    main()
