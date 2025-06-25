# -*- coding: utf-8 -*-
import os
import logging
import psycopg2
import re
from datetime import datetime
import io

from telegram import Update, ParseMode, InputFile
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# --- الإعدادات الأساسية ---
# قم بجلب التوكن الخاص بالبوت وعنوان قاعدة البيانات من إعدادات Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

# إعدادات المستخدمين والصلاحيات
USERS = {
    5615500221: "معتز",
    6940043771: "أسامه",
    6795122268: "عمر"
}
OMAR_ID = 6795122268
MOATAZ_ID = 5615500221
MOATAZ_RATE = 4.5 / 100  # 4.5 دولار لكل 100 نقطة

# إعداد نظام التسجيل (Logging) لتتبع أداء البوت والأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- قاموس تحويل الكلمات العربية إلى أرقام ---
ARABIC_WORDS_TO_NUM = {
    'واحد': 1, 'واحدة': 1, 'اثنين': 2, 'اثنان': 2, 'اثنتين': 2,
    'ثلاث': 3, 'ثلاثة': 3, 'اربع': 4, 'أربع': 4, 'اربعة': 4, 'أربعة': 4,
    'خمس': 5, 'خمسة': 5, 'ست': 6, 'ستة': 6, 'سبع': 7, 'سبعة': 7,
    'ثمان': 8, 'ثماني': 8, 'ثمانية': 8, 'تسع': 9, 'تسعة': 9,
    'عشر': 10, 'عشرة': 10, 'عشرين': 20, 'ثلاثين': 30, 'اربعين': 40, 'أربعين': 40,
    'خمسين': 50, 'ستين': 60, 'سبعين': 70, 'ثمانين': 80, 'تسعين': 90,
    'مئة': 100, 'مائة': 100, 'مئتين': 200, 'مائتين': 200,
    'ألف': 1000, 'الف': 1000, 'الفين': 2000, 'ألفين': 2000
}

# --- دوال التعامل مع قاعدة البيانات (PostgreSQL) ---
def get_db_connection():
    """إنشاء اتصال آمن بقاعدة البيانات."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None

def setup_database():
    """إنشاء الجدول الخاص بتسجيل النقاط إذا لم يكن موجودًا."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS work_log (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        user_name VARCHAR(255) NOT NULL,
                        quantity INTEGER NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                conn.commit()
                logger.info("Database table 'work_log' is ready.")
        except Exception as e:
            logger.error(f"Error setting up database table: {e}")
        finally:
            conn.close()

def log_work(user_id, user_name, quantity):
    """تسجيل كمية منجزة لمستخدم في قاعدة البيانات."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO work_log (user_id, user_name, quantity) VALUES (%s, %s, %s)",
                    (user_id, user_name, quantity)
                )
                conn.commit()
                logger.info(f"Logged {quantity} points for {user_name} ({user_id})")
                return True
        except Exception as e:
            logger.error(f"Error logging work: {e}")
            return False
        finally:
            conn.close()
    return False

# --- دوال تحليل الكمية من النصوص ---
def parse_quantity(text):
    """
    تحليل النص لاستخلاص الكمية بأولوية:
    1. أرقام عادية (123)
    2. أرقام عربية شرقية (١٢٣)
    3. كلمات عربية (مئة)
    """
    # 1. البحث عن أرقام عادية
    found_digits = re.findall(r'\d+', text)
    if found_digits:
        return int(found_digits[0])

    # 2. تحويل الأرقام العربية الشرقية والبحث مجددًا
    eastern_to_western = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    western_text = text.translate(eastern_to_western)
    found_digits = re.findall(r'\d+', western_text)
    if found_digits:
        return int(found_digits[0])

    # 3. البحث عن كلمات عربية
    for word in text.split():
        if word in ARABIC_WORDS_TO_NUM:
            return ARABIC_WORDS_TO_NUM[word]
    
    return None

# --- أوامر البوت ---
def start(update: Update, context: CallbackContext) -> None:
    """أمر الترحيب عند بدء استخدام البوت."""
    user_name = update.effective_user.first_name
    update.message.reply_text(f'أهلاً بك يا {user_name}!\nأنا جاهز لتسجيل وتتبع الطلبات.')

def daily_report(update: Update, context: CallbackContext) -> None:
    """إرسال تقرير بالكميات المنجزة اليوم."""
    conn = get_db_connection()
    if not conn:
        update.message.reply_text("حدث خطأ أثناء الاتصال بقاعدة البيانات. يرجى المحاولة لاحقاً.")
        return

    try:
        with conn.cursor() as cur:
            # جلب البيانات المجمعة لليوم الحالي
            cur.execute("""
                SELECT user_name, SUM(quantity)
                FROM work_log
                WHERE timestamp >= CURRENT_DATE
                GROUP BY user_name;
            """)
            results = cur.fetchall()

            today_date = datetime.now().strftime('%Y-%m-%d')
            if not results:
                update.message.reply_text(f"لم يتم تسجيل أي طلبات اليوم ({today_date}).")
                return

            report_text = f"📊 **تقرير اليوم: {today_date}**\n\n"
            total_today = 0
            for row in results:
                user_name, total_quantity = row
                report_text += f"👤 **{user_name}**: {total_quantity} نقطة\n"
                total_today += total_quantity
            
            report_text += f"\n- - - - -\n**المجموع الكلي لليوم**: {total_today} نقطة"
            update.message.reply_text(report_text, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Error generating daily report: {e}")
        update.message.reply_text("حدث خطأ أثناء إعداد التقرير اليومي.")
    finally:
        conn.close()

def full_report(update: Update, context: CallbackContext) -> None:
    """إرسال تقرير شامل مع ملف نصي."""
    conn = get_db_connection()
    if not conn:
        update.message.reply_text("حدث خطأ أثناء الاتصال بقاعدة البيانات.")
        return

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_name, SUM(quantity)
                FROM work_log
                GROUP BY user_name
                ORDER BY SUM(quantity) DESC;
            """)
            results = cur.fetchall()

            if not results:
                update.message.reply_text("لا توجد بيانات مسجلة لإنشاء تقرير.")
                return

            report_text = "📑 **التقرير الشامل**\n\n"
            total_all_time = 0
            moataz_total = 0

            for user_name, total_quantity in results:
                report_text += f"👤 **{user_name}**: {total_quantity} نقطة\n"
                total_all_time += total_quantity
                if user_name == "معتز":
                    moataz_total = total_quantity
            
            moataz_due = moataz_total * MOATAZ_RATE
            report_text += f"\n- - - - -\n"
            report_text += f"💰 **المستحق لمعتز**: {moataz_due:.2f} دولار\n"
            report_text += f"📈 **المجموع الكلي**: {total_all_time} نقطة"

            # إنشاء ملف نصي وإرساله
            file_content = report_text.replace("**", "") # إزالة تنسيق الماركدوان للملف النصي
            file_to_send = io.StringIO(file_content)
            file_to_send.name = "Taqreer_Shamel.txt"
            context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=InputFile(file_to_send, filename="Taqreer_Shamel.txt"),
                caption="إليك التقرير الشامل والمفصل."
            )

    except Exception as e:
        logger.error(f"Error generating full report: {e}")
        update.message.reply_text("حدث خطأ أثناء إعداد التقرير الشامل.")
    finally:
        conn.close()

def reset_data(update: Update, context: CallbackContext) -> None:
    """أمر تصفير البيانات (خاص بعمر فقط)."""
    user_id = update.effective_user.id
    if user_id != OMAR_ID:
        update.message.reply_text("⚠️ **عفواً، هذه الخدمة غير متاحة لك.**")
        return

    conn = get_db_connection()
    if not conn:
        update.message.reply_text("حدث خطأ أثناء الاتصال بقاعدة البيانات.")
        return
        
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE work_log RESTART IDENTITY;")
            conn.commit()
            logger.info(f"Data reset by OMAR (ID: {user_id})")
            update.message.reply_text("✅ **تم تصفير جميع البيانات بنجاح. تم البدء من الصفر.**")
    except Exception as e:
        logger.error(f"Error resetting data: {e}")
        update.message.reply_text("حدث خطأ فني أثناء محاولة تصفير البيانات.")
    finally:
        conn.close()


# --- معالج الرسائل الرئيسي ---
def handle_message(update: Update, context: CallbackContext) -> None:
    """المعالج الرئيسي الذي يستجيب لكلمة 'تم'."""
    message = update.message
    # التأكد أن الرسالة نصية وأنها رد على رسالة أخرى
    if not (message.text and message.reply_to_message and message.reply_to_message.text):
        return

    # تحقق إذا كان الرد هو "تم" بالضبط (مع تجاهل المسافات)
    if message.text.strip() == "تم":
        user_id = message.from_user.id
        
        # تحقق إذا كان المستخدم من ضمن القائمة المسموح بها
        if user_id not in USERS:
            # يمكنك إرسال تنبيه أو التجاهل بصمت
            return
            
        user_name = USERS[user_id]
        original_message = message.reply_to_message
        
        # استخلاص الكمية من الرسالة الأصلية
        quantity = parse_quantity(original_message.text)
        
        if quantity is None:
            # إذا لم يتمكن من قراءة الكمية، يرسل تنبيه
            context.bot.send_message(
                chat_id=message.chat_id,
                text=f"⚠️ **تنبيه لـ عمر:** لم أتمكن من قراءة الكمية في الطلب الذي رد عليه {user_name}. يرجى المراجعة."
            )
            return
        
        # تسجيل العمل في قاعدة البيانات
        if log_work(user_id, user_name, quantity):
            # في حال النجاح، قم بحذف الرسالتين
            try:
                context.bot.delete_message(chat_id=message.chat_id, message_id=original_message.message_id)
                context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
                logger.info(f"Successfully processed and deleted messages for {quantity} points by {user_name}.")
            except Exception as e:
                logger.error(f"Could not delete messages: {e}")
        else:
            # إذا فشلت عملية التسجيل في قاعدة البيانات
            context.bot.send_message(
                chat_id=message.chat_id,
                text=f"🔴 **خطأ فني:** لم أتمكن من تسجيل {quantity} نقطة لـ {user_name}. يرجى المحاولة مرة أخرى."
            )


def main() -> None:
    """الدالة الرئيسية لتشغيل البوت."""
    if not TELEGRAM_TOKEN or not DATABASE_URL:
        logger.error("FATAL: TELEGRAM_TOKEN or DATABASE_URL environment variables not set.")
        return

    # إعداد قاعدة البيانات عند بدء التشغيل
    setup_database()

    # إعداد البوت
    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher

    # تسجيل الأوامر باللغة العربية
    dispatcher.add_handler(CommandHandler("بدء", start))
    dispatcher.add_handler(CommandHandler("تقرير_يومي", daily_report))
    dispatcher.add_handler(CommandHandler("تقرير_شامل", full_report))
    dispatcher.add_handler(CommandHandler("تصفير", reset_data))


    # تسجيل معالج الرسائل لكلمة "تم"
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # بدء تشغيل البوت
    # في Render, يتم تحديد المنفذ تلقائياً
    PORT = int(os.environ.get('PORT', 8443))
    updater.start_webhook(listen="0.0.0.0",
                          port=PORT,
                          url_path=TELEGRAM_TOKEN,
                          webhook_url=f"https://work-bot-app.onrender.com/{TELEGRAM_TOKEN}")

    logger.info("Bot started successfully.")
    updater.idle()

if __name__ == '__main__':
    main()
