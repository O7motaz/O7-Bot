import logging
import os
from datetime import datetime, time

from pymongo import MongoClient
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from telegram.constants import ParseMode

# --- إعدادات أساسية ---
# يفضل تفعيلها لمتابعة أي أخطاء قد تحدث
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- تحميل المتغيرات الحساسة من بيئة النظام (مهم جداً لأمان حساباتك) ---
# ستحتاج لإضافة هذه المتغيرات في منصة الاستضافة
BOT_TOKEN = os.environ.get('BOT_TOKEN')
MONGO_URI = os.environ.get('MONGO_URI')

# --- الاتصال بقاعدة البيانات ---
# تأكد من أن الرابط الذي ستضعه في متغير MONGO_URI صحيح
try:
    client = MongoClient(MONGO_URI)
    db = client.get_database("reports_bot_db")
    tasks_collection = db.tasks
    logging.info("تم الاتصال بقاعدة البيانات بنجاح.")
except Exception as e:
    logging.error(f"فشل الاتصال بقاعدة البيانات: {e}")
    # سيتوقف البوت إذا لم يتمكن من الاتصال بقاعدة البيانات
    exit()

# --- بيانات المستخدمين (يمكنك التعديل عليها أو إضافتها هنا) ---
USER_DATA = {
    6795122268: "عمر",
    6940043771: "اسامه",
    5615500221: "معتز"
}


# --- الأمر الرئيسي لإضافة إنجاز ---
async def done_command(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    # يبحث عن اسم المستخدم في القائمة، وإذا لم يجده يستخدم اسمه الأول من تليجرام
    user_name = USER_DATA.get(user.id, user.first_name)

    # التأكد من أن المستخدم أدخل كمية (رقم) بعد الأمر
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ خطأ: يرجى إدخال الكمية المنجزة بعد الأمر.\nمثال: `/done 150`")
        return

    quantity = int(context.args[0])

    # إنشاء سجل للمهمة وتخزينه في قاعدة البيانات
    task_record = {
        "user_id": user.id,
        "user_name": user_name,
        "quantity": quantity,
        "completed_at": datetime.now()
    }
    tasks_collection.insert_one(task_record)

    await update.message.reply_text(f"✅ تم تسجيل {quantity} تعزيز باسمك يا {user_name}!")


# --- أوامر التقارير ---
async def daily_report_command(update: Update, context: CallbackContext) -> None:
    today = datetime.now().date()
    start_of_day = datetime.combine(today, time.min)
    end_of_day = datetime.combine(today, time.max)

    pipeline = [
        {"$match": {"completed_at": {"$gte": start_of_day, "$lte": end_of_day}}},
        {"$group": {"_id": "$user_name", "total": {"$sum": "$quantity"}}},
        {"$sort": {"total": -1}}
    ]
    results = list(tasks_collection.aggregate(pipeline))

    if not results:
        report_text = f"📊 **التقرير اليومي ({today})** 📊\n\nلم يتم إنجاز أي مهام اليوم."
    else:
        report_text = f"📊 **التقرير اليومي ({today})** 📊\n\n"
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
    if not result:
        payment_text += "لم ينجز أي مهام حتى الآن."
    else:
        total_boosts = result[0]['total']
        amount_due = (total_boosts / 100) * payment_rate_per_100
        payment_text += f"- **إجمالي الإنجاز:** {total_boosts} تعزيز\n"
        payment_text += f"- **المبلغ المستحق:** `{amount_due:.2f}$`"

    await update.message.reply_text(text=payment_text, parse_mode=ParseMode.MARKDOWN)


async def reset_command(update: Update, context: CallbackContext) -> None:
    # يمكنك إضافة ID المشرف هنا للتحقق من هوية المستخدم
    # admin_id = 123456789
    # if update.effective_user.id != admin_id:
    #     await update.message.reply_text("هذا الأمر للمشرف فقط.")
    #     return

    tasks_collection.delete_many({})
    await update.message.reply_text("✅ تم حذف جميع البيانات وبدء دورة جديدة.")


def main() -> None:
    """الدالة الرئيسية لتشغيل البوت"""
    if not BOT_TOKEN or not MONGO_URI:
        logging.error("المتغيرات (BOT_TOKEN, MONGO_URI) غير موجودة! يرجى إضافتها.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # إضافة الأوامر التي سيتفاعل معها البوت
    application.add_handler(CommandHandler(["done", "تم", "انجاز"], done_command))
    application.add_handler(CommandHandler(["daily_report", "يومي"], daily_report_command))
    application.add_handler(CommandHandler(["full_report", "مفصل"], full_report_command))
    application.add_handler(CommandHandler(["payment", "مستحقات"], calculate_payment_command))
    application.add_handler(CommandHandler(["reset", "تصفير"], reset_command))

    # بدء تشغيل البوت
    logging.info("البوت قيد التشغيل...")
    application.run_polling()


if __name__ == '__main__':
    main()