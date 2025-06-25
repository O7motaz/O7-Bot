# -*- coding: utf-8 -*-
import os
import telebot
from telebot import types
import json
import re
from datetime import datetime, timedelta
import io
import schedule
import threading
import time

# -- IMPORTANT: Update your requirements.txt file --
# pyTelegramBotAPI==4.12.0
# pymongo[srv]
# schedule

from pymongo import MongoClient

# --- إعدادات بوت O7 الخاصة ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')

# --- الاتصال بقاعدة البيانات ---
try:
    client = MongoClient(MONGO_URI)
    db = client['O7_Bot_DB'] 
    collection = db['data_store']
    print("O7 Bot System: Successfully connected to MongoDB Atlas.")
except Exception as e:
    print(f"FATAL: Could not connect to MongoDB. Error: {e}")
    exit()

bot = telebot.TeleBot(TELEGRAM_TOKEN)
print("O7 Bot System: Online with Full Interactive UI.")

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
    if '_id' in new_data: del new_data['_id']
    collection.replace_one({"document_id": "main_config"}, new_data, upsert=True)

def parse_quantity(text):
    match = re.search(r'\d+', text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
    return int(match.group(0)) if match else None

# --- ✨ الواجهة الرئيسية واللوحات التفاعلية ✨ ---

@bot.message_handler(commands=['start', 'مساعدة'])
def show_main_interface(message):
    """يعرض الواجهة الرئيسية مع خياري المشرف والعامل."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👨‍💻 مشرف", callback_data="panel:admin"),
        types.InlineKeyboardButton("👷‍♂️ عامل", callback_data="panel:worker")
    )
    bot.send_message(message.chat.id, "👋 **أهلاً بك في بوت O7**\n\nالرجاء تحديد دورك للوصول إلى لوحة التحكم الخاصة بك:", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['المطور'])
def show_developer_panel(message):
    """يعرض لوحة تحكم المطور الخاصة."""
    data = get_data()
    if message.from_user.id != data['config']['main_admin']:
        return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👑 إدارة الصلاحيات", callback_data="dev:manage_permissions"),
        types.InlineKeyboardButton("➕ إضافة عامل", callback_data="dev:add_worker_prompt"),
        types.InlineKeyboardButton("➖ حذف عامل", callback_data="dev:remove_worker_prompt"),
        types.InlineKeyboardButton("💸 تصفير عامل", callback_data="dev:reset_worker_prompt"),
        types.InlineKeyboardButton("💾 نسخة احتياطية", callback_data="dev:backup")
    )
    bot.send_message(message.chat.id, "👑 **لوحة تحكم المطور**", reply_markup=markup, parse_mode='Markdown')

# --- معالج الأزرار المركزي ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    """يعالج جميع ضغطات الأزرار ويوجهها."""
    data = get_data()
    user_id = call.from_user.id
    action, *params = call.data.split(':')

    # Main Panel Logic
    if action == "panel":
        panel_type = params[0]
        if panel_type == "admin":
            if user_id not in data['config']['admins']:
                return bot.answer_callback_query(call.id, "🚫 هذه الخدمة للمشرفين فقط.", show_alert=True)
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📊 إحصائيات اليوم", callback_data="cmd:stats_today"),
                types.InlineKeyboardButton("📅 إحصائيات مخصصة", callback_data="cmd:stats_custom"),
                types.InlineKeyboardButton("🏆 لوحة الصدارة", callback_data="cmd:leaderboard"),
                types.InlineKeyboardButton("🔄 تصفير الكل", callback_data="cmd:reset_all"),
                types.InlineKeyboardButton("💰 تحديد الأجر", callback_data="cmd:set_rate_prompt")
            )
            bot.edit_message_text("👨‍💻 **لوحة تحكم المشرف**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        
        elif panel_type == "worker":
            if str(user_id) not in data['config']['workers']:
                return bot.answer_callback_query(call.id, "🚫 هذه الخدمة غير متوفرة لك.", show_alert=True)
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📄 تقريري اليومي", callback_data="cmd:report_today"),
                types.InlineKeyboardButton("📅 تقريري المخصص", callback_data="cmd:report_custom"),
                types.InlineKeyboardButton("🏆 لوحة الصدارة", callback_data="cmd:leaderboard")
            )
            bot.edit_message_text("👷‍♂️ **لوحة تحكم العامل**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    # Developer Panel Logic
    elif action == "dev":
        if user_id != data['config']['main_admin']: return bot.answer_callback_query(call.id, "🚫 للمطور فقط.")
        command_type = params[0]
        if command_type == "manage_permissions":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("⬆️ ترقية مشرف", callback_data="dev:promote_list"),
                types.InlineKeyboardButton("⬇️ تخفيض مشرف", callback_data="dev:demote_list")
            )
            bot.edit_message_text("👑 **إدارة الصلاحيات**", call.message.chat.id, call.message.message_id, reply_markup=markup)
        elif command_type == "promote_list":
            markup = types.InlineKeyboardMarkup(row_width=1)
            for worker_id_str, info in data['config']['workers'].items():
                worker_id = int(worker_id_str)
                if worker_id not in data['config']['admins']:
                    markup.add(types.InlineKeyboardButton(f"⬆️ {info['name']}", callback_data=f"dev:promote:{worker_id}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="dev:manage_permissions"))
            bot.edit_message_text("اختر العامل لترقيته:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        elif command_type == "promote":
            user_to_promote = int(params[1])
            if user_to_promote not in data['config']['admins']:
                data['config']['admins'].append(user_to_promote)
                update_data(data)
                bot.answer_callback_query(call.id, "✅ تم الترقية بنجاح!")
            call.data = "dev:promote_list"
            handle_callbacks(call) # Refresh list
        elif command_type == "demote_list":
            markup = types.InlineKeyboardMarkup(row_width=1)
            for admin_id in data['config']['admins']:
                if admin_id != data['config']['main_admin']:
                    worker_info = data['config']['workers'].get(str(admin_id))
                    markup.add(types.InlineKeyboardButton(f"⬇️ {worker_info['name']}", callback_data=f"dev:demote:{admin_id}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="dev:manage_permissions"))
            bot.edit_message_text("اختر المشرف لتخفيضه:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        elif command_type == "demote":
            user_to_demote = int(params[1])
            if user_to_demote in data['config']['admins'] and user_to_demote != data['config']['main_admin']:
                data['config']['admins'].remove(user_to_demote)
                update_data(data)
                bot.answer_callback_query(call.id, "✅ تم التخفيض بنجاح!")
            call.data = "dev:demote_list"
            handle_callbacks(call) # Refresh list
        else: # Prompts for text commands
            prompts = {
                "add_worker_prompt": "لإضافة عامل، أرسل الأمر:\n`/اضافة_عامل [ID] [الاسم] [اليوزر] [الأجرة]`",
                "remove_worker_prompt": "لحذف عامل، أرسل الأمر:\n`/حذف_عامل [ID]`",
                "reset_worker_prompt": "لتصفير مستحقات عامل، أرسل الأمر:\n`/تصفير_عامل [ID]`"
            }
            if command_type in prompts: bot.send_message(call.message.chat.id, prompts[command_type])
            elif command_type == "backup": backup_command(call.message)
            bot.answer_callback_query(call.id)

    # Command Execution Logic
    elif action == "cmd":
        command_type = params[0]
        if command_type == "report_today": daily_report_command(call.message)
        elif command_type == "report_custom": bot.send_message(call.message.chat.id, "لعرض تقرير مخصص، أرسل الأمر:\n`/تقريري [YYYY-MM-DD] [YYYY-MM-DD]`")
        elif command_type == "stats_today": custom_team_report_command(call.message)
        elif command_type == "stats_custom": bot.send_message(call.message.chat.id, "لعرض إحصائيات مخصصة، أرسل الأمر:\n`/احصائيات [YYYY-MM-DD] [YYYY-MM-DD]`")
        elif command_type == "reset_all": reset_command(call.message)
        elif command_type == "leaderboard": leaderboard_command(call.message)
        elif command_type == "set_rate_prompt": bot.send_message(call.message.chat.id, "لتحديد أجر عامل، أرسل الأمر:\n`/تحديد_الاجر [ID] [الأجرة الجديدة]`")
        bot.answer_callback_query(call.id)
    
    # Confirmation Logic
    elif action == "confirm_reset": handle_reset_callback(call)

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
        "worker_id": None, "worker_name": None, "paid": False, "alert_sent": False,
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
    data = get_data()
    if str(message.from_user.id) not in data['config']['workers']: return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    generate_financial_report(message, today, today, for_user_id=message.from_user.id)

@bot.message_handler(commands=['تقريري'])
def custom_personal_report_command(message):
    data = get_data(); parts = message.text.split()
    if str(message.from_user.id) not in data['config']['workers']: return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    if len(parts) != 3: return bot.reply_to(message, "صيغة خاطئة. استخدم:\n/تقريري [YYYY-MM-DD] [YYYY-MM-DD]")
    try:
        start_date, end_date = datetime.strptime(parts[1], '%Y-%m-%d'), datetime.strptime(parts[2], '%Y-%m-%d')
        generate_financial_report(message, start_date, end_date, for_user_id=message.from_user.id)
    except ValueError: bot.reply_to(message, "⚠️ صيغة التاريخ خاطئة: `YYYY-MM-DD`")

@bot.message_handler(commands=['احصائيات'])
def custom_team_report_command(message):
    data = get_data(); parts = message.text.split()
    if message.from_user.id not in data['config']['admins']: return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    if len(parts) == 1:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return generate_financial_report(message, today, today)
    if len(parts) != 3: return bot.reply_to(message, "صيغة خاطئة. استخدم:\n/احصائيات [YYYY-MM-DD] [YYYY-MM-DD]")
    try:
        start_date, end_date = datetime.strptime(parts[1], '%Y-%m-%d'), datetime.strptime(parts[2], '%Y-%m-%d')
        generate_financial_report(message, start_date, end_date)
    except ValueError: bot.reply_to(message, "⚠️ صيغة التاريخ خاطئة: `YYYY-MM-DD`")

@bot.message_handler(commands=['لوحة_الصدارة'])
def leaderboard_command(message):
    data = get_data()
    if str(message.from_user.id) not in data['config']['workers']: return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_orders = [o for o in data["orders"] if o["status"] == "completed" and o.get("completion_time") and datetime.fromisoformat(o["completion_time"]) >= seven_days_ago]
    if not recent_orders: return bot.reply_to(message, "🏆 **لوحة الصدارة الأسبوعية**\n\nلا يوجد عمل مسجل في آخر 7 أيام.")
    leaderboard = {};
    for order in recent_orders:
        name, quantity = order.get("worker_name", "غير معروف"), order.get("quantity", 0)
        leaderboard[name] = leaderboard.get(name, 0) + quantity
    sorted_workers = sorted(leaderboard.items(), key=lambda item: item[1], reverse=True)
    report_text = "🏆 **لوحة الصدارة لأفضل العمال (آخر 7 أيام)**\n\n"; medals = ["🥇", "🥈", "🥉"]
    for i, (worker, total_quantity) in enumerate(sorted_workers):
        medal = medals[i] if i < 3 else "🔹"; report_text += f"{medal} *{worker}*: {total_quantity} وحدة\n"
    bot.reply_to(message, report_text, parse_mode='Markdown')

@bot.message_handler(commands=['اضافة_عامل'])
def add_worker_command(message):
    data = get_data()
    if message.from_user.id != data['config']['main_admin']: return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    parts = message.text.split()
    if len(parts) != 5: return bot.reply_to(message, "صيغة خاطئة. استخدم:\n/اضافة_عامل [ID] [الاسم] [اليوزر] [الأجرة]")
    worker_id, name, username, rate_str = parts[1], parts[2], parts[3], parts[4]
    try:
        rate = float(rate_str); data['config']['workers'][worker_id] = {"name": name, "username": username, "rate": rate}
        update_data(data); bot.reply_to(message, f"✅ تم إضافة العامل '{name}' بنجاح.")
    except ValueError: bot.reply_to(message, "⚠️ الأجرة يجب أن تكون رقمًا.")

@bot.message_handler(commands=['حذف_عامل'])
def remove_worker_command(message):
    data = get_data()
    if message.from_user.id != data['config']['main_admin']: return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    parts = message.text.split();
    if len(parts) != 2: return bot.reply_to(message, "صيغة خاطئة. استخدم: /حذف_عامل [ID]")
    worker_id_to_remove = parts[1]
    if worker_id_to_remove in data['config']['workers']:
        removed_name = data['config']['workers'].pop(worker_id_to_remove)['name']; update_data(data)
        bot.reply_to(message, f"🗑️ تم حذف العامل '{removed_name}' من النظام.")
    else: bot.reply_to(message, "لم يتم العثور على عامل بهذا الـ ID.")

@bot.message_handler(commands=['تحديد_الاجر'])
def set_rate_command(message):
    data = get_data()
    if message.from_user.id not in data['config']['admins']: return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    parts = message.text.split()
    if len(parts) != 3: return bot.reply_to(message, "صيغة خاطئة. استخدم:\n/تحديد_الاجر [ID العامل] [الأجرة الجديدة]")
    worker_id, new_rate_str = parts[1], parts[2]
    if worker_id not in data['config']['workers']: return bot.reply_to(message, f"⚠️ لم يتم العثور على عامل بالـ ID التالي: {worker_id}")
    try:
        new_rate = float(new_rate_str); data['config']['workers'][worker_id]['rate'] = new_rate; update_data(data)
        worker_name = data['config']['workers'][worker_id]['name']
        bot.reply_to(message, f"✅ تم تحديث أجرة العامل '{worker_name}' إلى ${new_rate:.2f} لكل 100 وحدة.")
    except ValueError: bot.reply_to(message, "⚠️ الأجرة يجب أن تكون رقمًا صحيحًا أو عشريًا.")

@bot.message_handler(commands=['تصفير_عامل'])
def reset_worker_command(message):
    data = get_data()
    if message.from_user.id != data['config']['main_admin']: return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    parts = message.text.split()
    if len(parts) != 2: return bot.reply_to(message, "صيغة خاطئة. استخدم: /تصفير_عامل [ID]")
    try:
        worker_id_to_reset = int(parts[1]); total_paid_quantity = 0
        for order in data["orders"]:
            if order.get("worker_id") == worker_id_to_reset and not order.get("paid"):
                total_paid_quantity += order.get("quantity", 0); order["paid"] = True
        update_data(data); bot.reply_to(message, f"💸 تم تصفير مستحقات العامل (ID: {worker_id_to_reset}).\nإجمالي الكمية التي تم تصفيرها: {total_paid_quantity}.")
    except ValueError: bot.reply_to(message, "الـ ID يجب أن يكون رقمًا.")

@bot.message_handler(commands=['تصفير_الكل'])
def reset_command(message):
    data = get_data()
    if message.from_user.id not in data['config']['admins']: return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("نعم، أرشفة غير المدفوع", callback_data="confirm_reset:all"), types.InlineKeyboardButton("إلغاء", callback_data="cancel"))
    bot.send_message(message.chat.id, "🚨 **تحذير:** هل أنت متأكد أنك تريد أرشفة جميع بيانات العمل **غير المدفوعة**؟", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_reset"))
def handle_reset_callback(call):
    data = get_data()
    if call.from_user.id not in data['config']['admins']: return bot.answer_callback_query(call.id, "🚫 ليس لديك الصلاحية لهذا الإجراء.")
    for order in data["orders"]:
        if not order.get("paid"): order["paid"] = True
    update_data(data)
    bot.edit_message_text("✅ تم أرشفة جميع بيانات العمل غير المدفوعة بنجاح.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def handle_cancel_callback(call):
    bot.edit_message_text("👍 تم إلغاء العملية.", call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['متوسط_السعر'])
def average_price_command(message):
    data = get_data()
    if message.from_user.id not in data['config']['average_price_users']: return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    numbers = re.findall(r'[\d\.]+', message.text);
    if not numbers: return bot.reply_to(message, "لم يتم العثور على أرقام. أدخل الأسعار بعد الأمر.")
    prices = [float(n) for n in numbers]; average = sum(prices) / len(prices)
    bot.reply_to(message, f"📊 متوسط السعر هو: *${average:.2f}*", parse_mode='Markdown')

@bot.message_handler(commands=['نسخة_احتياطية'])
def backup_command(message):
    data = get_data()
    if message.from_user.id != data['config']['main_admin']: return bot.reply_to(message, "🚫 هذه الخدمة غير متوفرة لك.")
    try:
        if '_id' in data: del data['_id']
        data_str = json.dumps(data, indent=4, ensure_ascii=False, default=str)
        data_bytes = io.BytesIO(data_str.encode('utf-8'))
        data_bytes.name = f"backup-{datetime.now().strftime('%Y-%m-%d')}.json"
        bot.send_document(message.chat.id, data_bytes, caption=f"💾 نسخة احتياطية من قاعدة البيانات بتاريخ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    except Exception as e:
        bot.reply_to(message, "حدث خطأ أثناء إنشاء النسخة الاحتياطية."); print(f"Backup Error: {e}")

# --- نظام التشغيل والجدولة ---
def check_pending_orders():
    """يفحص الطلبات المعلقة ويرسل تنبيهات."""
    data = get_data()
    group_id = data.get('group_chat_id')
    if not group_id: return

    now = datetime.now()
    alert_threshold = timedelta(minutes=30)
    changed = False

    for order in data.get('orders', []):
        if order.get('status') == 'pending' and not order.get('alert_sent'):
            request_time = datetime.fromisoformat(order['request_time'])
            if now - request_time > alert_threshold:
                alert_text = f"🔔 **تنبيه: طلب معلق** 🔔\n\nالطلب \"{order.get('text', 'N/A')}\" لم يتم تنفيذه منذ أكثر من 30 دقيقة."
                try: bot.send_message(group_id, alert_text, parse_mode='Markdown')
                except Exception as e: print(f"Failed to send alert to group {group_id}. Error: {e}")
                order['alert_sent'] = True
                changed = True
    
    if changed:
        update_data(data)

def run_scheduler():
    schedule.every(5).minutes.do(check_pending_orders)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    get_data() # Ensure data structure exists on first run
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("O7 Bot System: Polling for messages...")
    bot.polling(none_stop=True)
