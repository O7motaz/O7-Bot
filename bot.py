# -*- coding: utf-8 -*-
import os
import telebot
from telebot import types
import json
import re
from datetime import datetime, timedelta
import io
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
app = Flask(__name__) # ✨ تم تعريف تطبيق الويب هنا

# --- ✨ واجهة الويب (لإبقاء البوت مستيقظًا على Render) ✨ ---
@app.route('/')
def index():
    return "Bot is running and stable."

# --- دوال مساعدة لإدارة البيانات والأدوار ---
def get_data():
    data = collection.find_one({"document_id": "main_config"})
    if data:
        return data
    else:
        # الهيكل الأساسي الجديد مع الأدوار
        initial_data = {
            "document_id": "main_config", "group_chat_id": None,
            "config": {
                "workers": {
                    "5615500221": {"name": "معتز", "username": "@o7_7gg", "rate": 4.5, "roles": ["worker", "admin", "owner"]},
                    "6795122268": {"name": "عمر", "username": "@B3NEI", "rate": 4.5, "roles": ["worker", "admin"]},
                    "6940043771": {"name": "اسامه", "username": "@i_x_u", "rate": 4.5, "roles": ["worker", "admin"]}
                }
            }, "orders": []
        }
        collection.insert_one(initial_data)
        return initial_data

def update_data(new_data):
    if '_id' in new_data: del new_data['_id']
    collection.replace_one({"document_id": "main_config"}, new_data, upsert=True)

def parse_quantity(text):
    match = re.search(r'\d+', text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
    return int(match.group(0)) if match else None

def user_has_role(user_id, role):
    data = get_data()
    worker_info = data.get('config', {}).get('workers', {}).get(str(user_id))
    return worker_info and role in worker_info.get('roles', [])

# --- الواجهة الرئيسية واللوحات التفاعلية ---

@bot.message_handler(commands=['start', 'مساعدة'])
def show_main_interface(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("👑 مالك", callback_data="panel:owner"),
        types.InlineKeyboardButton("👨‍💻 مشرف", callback_data="panel:admin"),
        types.InlineKeyboardButton("👷‍♂️ عامل", callback_data="panel:worker")
    )
    bot.send_message(message.chat.id, "👋 **أهلاً بك في بوت O7**\n\nالرجاء تحديد دورك للوصول إلى لوحة التحكم الخاصة بك:", reply_markup=markup, parse_mode='Markdown')

# --- معالج الأزرار المركزي ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    action, *params = call.data.split(':')

    if action == "panel":
        panel_type = params[0]
        if panel_type == "owner":
            if not user_has_role(user_id, 'owner'): return bot.answer_callback_query(call.id, "🚫 هذه اللوحة للمالك فقط.", show_alert=True)
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("👑 إدارة الصلاحيات", callback_data="permissions:menu"))
            markup.add(types.InlineKeyboardButton("➕ إضافة عامل", callback_data="owner_cmd:add_worker_prompt"))
            markup.add(types.InlineKeyboardButton("➖ حذف عامل", callback_data="owner_cmd:remove_worker_prompt"))
            markup.add(types.InlineKeyboardButton("💸 تصفير عامل", callback_data="owner_cmd:reset_worker_prompt"))
            markup.add(types.InlineKeyboardButton("💾 نسخة احتياطية", callback_data="owner_cmd:backup"))
            bot.edit_message_text("👑 **لوحة تحكم المالك**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

        elif panel_type == "admin":
            if not user_has_role(user_id, 'admin'): return bot.answer_callback_query(call.id, "🚫 هذه اللوحة للمشرفين فقط.", show_alert=True)
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("📊 إحصائيات الفريق", callback_data="cmd:stats"))
            markup.add(types.InlineKeyboardButton("💰 تحديد الأجر", callback_data="cmd:set_rate"))
            markup.add(types.InlineKeyboardButton("🔄 تصفير الكل", callback_data="cmd:reset_all"))
            bot.edit_message_text("👨‍💻 **لوحة تحكم المشرف**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

        elif panel_type == "worker":
            if not user_has_role(user_id, 'worker'): return bot.answer_callback_query(call.id, "🚫 هذه اللوحة للعمال فقط.", show_alert=True)
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("📄 تقريري اليومي", callback_data="cmd:my_report_today"))
            markup.add(types.InlineKeyboardButton("📅 تقريري المخصص", callback_data="cmd:my_report_custom"))
            bot.edit_message_text("👷‍♂️ **لوحة تحكم العامل**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    elif action == "permissions":
        if not user_has_role(user_id, 'owner'): return bot.answer_callback_query(call.id, "🚫 للمالك فقط.")
        perm_action = params[0]
        data = get_data()
        if perm_action == "menu":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("⬆️⬇️ تغيير رتبة مشرف", callback_data="permissions:toggle_admin_list"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع للوحة المالك", callback_data="panel:owner"))
            bot.edit_message_text("👑 **إدارة الصلاحيات**", call.message.chat.id, call.message.message_id, reply_markup=markup)
            
        elif perm_action in ["toggle_admin_list", "toggle_admin"]:
            if perm_action == "toggle_admin":
                target_id = params[1]
                target_roles = data['config']['workers'][target_id]['roles']
                if 'admin' in target_roles:
                    if 'owner' not in target_roles: target_roles.remove('admin')
                else:
                    target_roles.append('admin')
                update_data(data)
                bot.answer_callback_query(call.id, "✅ تم تحديث الرتبة.")
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            for worker_id_str, info in data['config']['workers'].items():
                if 'owner' in info.get('roles', []): continue
                is_admin = 'admin' in info.get('roles', [])
                button_text = f"{'⬇️' if is_admin else '⬆️'} {info['name']}"
                markup.add(types.InlineKeyboardButton(button_text, callback_data=f"permissions:toggle_admin:{worker_id_str}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="permissions:menu"))
            bot.edit_message_text("اختر مستخدمًا لترقيته إلى مشرف أو تخفيضه:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif action.startswith("cmd"):
        prompts = {
            "my_report_custom": "لعرض تقرير مخصص، أرسل الأمر:\n`/تقريري [YYYY-MM-DD] [YYYY-MM-DD]`",
            "stats": "لعرض إحصائيات الفريق لفترة، أرسل الأمر:\n`/احصائيات [YYYY-MM-DD] [YYYY-MM-DD]`\nأو أرسل `/احصائيات` لتقرير اليوم.",
            "set_rate": "لتحديد أجر عامل، أرسل الأمر:\n`/تحديد_الاجر [ID] [الأجرة الجديدة]`"
        }
        command_type = params[0]
        if command_type in prompts: bot.send_message(call.message.chat.id, prompts[command_type])
        elif command_type == "my_report_today": daily_report_command(call.message)
        elif command_type == "reset_all": reset_command(call.message)
        bot.answer_callback_query(call.id)

    elif action.startswith("owner_cmd"):
        if not user_has_role(user_id, 'owner'): return bot.answer_callback_query(call.id, "🚫 للمالك فقط.")
        prompts = {
            "add_worker_prompt": "لإضافة عامل، أرسل الأمر:\n`/اضافة_عامل [ID] [الاسم] [اليوزر] [الأجرة]`",
            "remove_worker_prompt": "لحذف عامل، أرسل الأمر:\n`/حذف_عامل [ID]`",
            "reset_worker_prompt": "لتصفير مستحقات عامل، أرسل الأمر:\n`/تصفير_عامل [ID]`"
        }
        command_type = params[0]
        if command_type in prompts: bot.send_message(call.message.chat.id, prompts[command_type])
        elif command_type == "backup": backup_command(call.message)
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("confirm_reset"): handle_reset_callback(call)
    elif call.data == "cancel": bot.edit_message_text("👍 تم إلغاء العملية.", call.message.chat.id, call.message.message_id)

# --- معالجات الأوامر النصية ---
@bot.message_handler(func=lambda message: str(message.from_user.id) in get_data()['config']['workers'] and message.chat.type in ['group', 'supergroup'] and not message.text.startswith('/'))
def handle_new_order(message):
    data = get_data(); quantity = parse_quantity(message.text)
    if not quantity: return
    if data.get("group_chat_id") is None: data["group_chat_id"] = message.chat.id; update_data(data)
    requester_info = data['config']['workers'].get(str(message.from_user.id), {})
    new_order = {
        "message_id": message.message_id, "chat_id": message.chat.id, "text": message.text, "quantity": quantity,
        "requester_id": message.from_user.id, "requester_name": requester_info.get("name"), "status": "pending",
        "worker_id": None, "worker_name": None, "paid": False,
        "request_time": datetime.now().isoformat(), "completion_time": None }
    data["orders"].append(new_order); update_data(data)

@bot.message_handler(func=lambda message: message.text and message.text.strip().lower() == "تم" and str(message.from_user.id) in get_data()['config']['workers'] and message.reply_to_message)
def handle_order_completion(message):
    data = get_data(); worker_info = data['config']['workers'].get(str(message.from_user.id))
    original_order_message_id, chat_id = message.reply_to_message.message_id, message.chat.id
    order_found = False
    for order in data["orders"]:
        if order["message_id"] == original_order_message_id and order["status"] == "pending":
            order.update({ "status": "completed", "worker_id": message.from_user.id, "worker_name": worker_info.get("name"), "completion_time": datetime.now().isoformat() })
            update_data(data); order_found = True; break
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
    filtered_orders = [o for o in unpaid_orders if o.get("completion_time") and start_date <= datetime.fromisoformat(o["completion_time"]) < end_date_inclusive and (for_user_id is None or o.get("worker_id") == for_user_id)]
    start_str, end_str = start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    report_title = f"📊 **تقرير ليوم {start_str}**" if start_str == end_str else f"📊 **تقرير من {start_str} إلى {end_str}**"
    if for_user_id: report_title = f"📄 **تقريرك الشخصي**"
    if not filtered_orders:
        report_text = f"{report_title}\n\nلا يوجد عمل مسجل في هذه الفترة."
    else:
        report_text = f"{report_title}\n\n"; worker_summary = {}
        for order in filtered_orders:
            worker_id_str, name = str(order.get("worker_id")), order.get("worker_name", "غير معروف")
            if name not in worker_summary: worker_summary[name] = {"count": 0, "total_quantity": 0, "id": worker_id_str}
            worker_summary[name]["count"] += 1; worker_summary[name]["total_quantity"] += order.get("quantity", 0)
        total_quantity_all = sum(s['total_quantity'] for s in worker_summary.values())
        report_text += f"✨ *إجمالي الطلبات: {len(filtered_orders)}* | 📦 *إجمالي الكميات: {total_quantity_all}*\n--------------------\n"
        for worker, summary in worker_summary.items():
            worker_config = data['config']['workers'].get(summary["id"], {}); rate = worker_config.get("rate", 0)
            wage = (summary['total_quantity'] / 100) * rate if rate > 0 else 0
            report_text += f"👷‍♂️ *{worker}*: {summary['count']} طلبات (كمية: {summary['total_quantity']})"
            if wage > 0: report_text += f" | 💰 *الأجر المستحق: ${wage:.2f}*"; report_text += "\n"
    bot.send_message(message.chat.id, report_text, parse_mode='Markdown')

# --- معالجات الأوامر النصية للتنفيذ ---
@bot.message_handler(commands=['تقرير'])
def daily_report_command(message):
    if not user_has_role(message.from_user.id, 'worker'): return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    generate_financial_report(message, today, today, for_user_id=message.from_user.id)

@bot.message_handler(commands=['تقريري'])
def custom_personal_report_command(message):
    if not user_has_role(message.from_user.id, 'worker'): return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    parts = message.text.split()
    if len(parts) != 3: return bot.reply_to(message, "صيغة خاطئة. استخدم:\n/تقريري [YYYY-MM-DD] [YYYY-MM-DD]")
    try:
        start_date, end_date = datetime.strptime(parts[1], '%Y-%m-%d'), datetime.strptime(parts[2], '%Y-%m-%d')
        generate_financial_report(message, start_date, end_date, for_user_id=message.from_user.id)
    except ValueError: bot.reply_to(message, "⚠️ صيغة التاريخ خاطئة: `YYYY-MM-DD`")

@bot.message_handler(commands=['احصائيات'])
def custom_team_report_command(message):
    if not user_has_role(message.from_user.id, 'admin'): return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    parts = message.text.split()
    if len(parts) == 1:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return generate_financial_report(message, today, today)
    if len(parts) != 3: return bot.reply_to(message, "صيغة خاطئة. استخدم:\n/احصائيات [YYYY-MM-DD] [YYYY-MM-DD]")
    try:
        start_date, end_date = datetime.strptime(parts[1], '%Y-%m-%d'), datetime.strptime(parts[2], '%Y-%m-%d')
        generate_financial_report(message, start_date, end_date)
    except ValueError: bot.reply_to(message, "⚠️ صيغة التاريخ خاطئة: `YYYY-MM-DD`")

@bot.message_handler(commands=['اضافة_عامل'])
def add_worker_command(message):
    if not user_has_role(message.from_user.id, 'owner'): return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    parts = message.text.split()
    if len(parts) != 5: return bot.reply_to(message, "صيغة خاطئة. استخدم:\n/اضافة_عامل [ID] [الاسم] [اليوزر] [الأجرة]")
    worker_id, name, username, rate_str = parts[1], parts[2], parts[3], parts[4]
    try:
        data = get_data()
        rate = float(rate_str); data['config']['workers'][worker_id] = {"name": name, "username": username, "rate": rate, "roles": ["worker"]}
        update_data(data); bot.reply_to(message, f"✅ تم إضافة العامل '{name}' بنجاح.")
    except ValueError: bot.reply_to(message, "⚠️ الأجرة يجب أن تكون رقمًا.")

# ... (Rest of text command handlers for owner/admin)

# --- نظام التشغيل ---
def run_bot_polling():
    print("O7 Bot System: Starting bot polling...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Bot polling failed: {e}")
        time.sleep(5)

# ✨ هذا هو الجزء الجديد الذي يحل المشكلة ✨
# يتم تشغيل البوت في خيط منفصل
polling_thread = threading.Thread(target=run_bot_polling)
polling_thread.daemon = True
polling_thread.start()

# gunicorn سيقوم بتشغيل 'app' من هذا الملف
if __name__ == "__main__":
    # هذا فقط للاختبار المحلي، وليس للإنتاج على Render
    # The production server will be gunicorn
    print("Running Flask app for local testing...")
    app.run(host='0.0.0.0', port=5000)
