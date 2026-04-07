"""
♟️ Chess Trainer Bot v5.4 — pyTelegramBotAPI 4.14.0 + RENDER
"""

import logging
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from copy import deepcopy
from datetime import datetime
from pymongo import MongoClient
import telebot
from telebot import types

# ─────────────────────────────────────────────
# НАЛАШТУВАННЯ
# ─────────────────────────────────────────────
BOT_TOKEN  = os.environ.get("BOT_TOKEN")
TRAINER_ID = int(os.environ.get("TRAINER_ID", "0"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# MONGODB
# ─────────────────────────────────────────────
mongo_client = None
mdb = None

def init_mongo():
    global mongo_client, mdb
    uri = os.environ.get("MONGODB_URI")
    logger.info(f"🔗 MONGODB_URI: {'✅ знайдено' if uri else '❌ ПОРОЖНЬО!'}")
    if not uri:
        raise ValueError("MONGODB_URI не знайдено!")
    mongo_client = MongoClient(
        uri,
        serverSelectionTimeoutMS=5000,
        tls=True,
        tlsAllowInvalidCertificates=True
    )
    mdb = mongo_client["chess_trainer"]
    mongo_client.admin.command("ping")
    logger.info("✅ MongoDB Atlas підключено!")

def col(name):
    return mdb[name]

# ─────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────
def db_get_students() -> list:
    return list(col("students").find({}, {"_id": 0}))

def db_add_student(student: dict):
    col("students").insert_one(deepcopy(student))

def db_delete_student(name: str):
    col("students").delete_one({"name": name})

def db_find_student_by_phone(phone: str):
    return col("students").find_one({"student_phone": phone}, {"_id": 0})

def db_get_schedule() -> list:
    return list(col("schedule").find({}, {"_id": 0}))

def db_add_schedule(entry: dict):
    col("schedule").insert_one(deepcopy(entry))

def db_delete_schedule(day: str, time: str, group: str):
    col("schedule").delete_one({"day": day, "time": time, "group": group})

def db_get_homework() -> list:
    return list(col("homework").find({}, {"_id": 0}))

def db_add_homework(hw: dict):
    col("homework").insert_one(deepcopy(hw))

def db_delete_homework(group: str, task: str):
    col("homework").delete_one({"group": group, "task": task})

def db_get_news() -> list:
    return list(col("news").find({}, {"_id": 0}))

def db_add_news(item: dict):
    col("news").insert_one(deepcopy(item))

def db_delete_news(title: str, date: str):
    col("news").delete_one({"title": title, "date": date})

def db_get_materials() -> list:
    return list(col("materials").find({}, {"_id": 0}))

def db_add_material(mat: dict):
    col("materials").insert_one(deepcopy(mat))

def db_delete_material(title: str, link: str):
    col("materials").delete_one({"title": title, "link": link})

def db_get_tournaments() -> list:
    return list(col("tournaments").find({}, {"_id": 0}))

def db_add_tournament(t: dict):
    col("tournaments").insert_one(deepcopy(t))

def db_delete_tournament(title: str, date: str):
    col("tournaments").delete_one({"title": title, "date": date})

def db_get_parents() -> dict:
    result = {}
    for p in col("parents").find({}, {"_id": 0}):
        result[p["pid"]] = {
            "name": p["name"],
            "student": p.get("student", ""),
            "group": p.get("group", ""),
            "rank": p.get("rank", ""),
        }
    return result

def db_upsert_parent(pid: str, name: str, student: str = "", group: str = "", rank: str = ""):
    col("parents").update_one(
        {"pid": pid},
        {"$set": {"pid": pid, "name": name, "student": student, "group": group, "rank": rank}},
        upsert=True
    )

def db_link_parent_to_student(pid: str, student_name: str, group: str, rank: str):
    col("parents").update_one(
        {"pid": pid},
        {"$set": {"student": student_name, "group": group, "rank": rank}}
    )

def db_get_student_users() -> dict:
    result = {}
    for s in col("student_users").find({}, {"_id": 0}):
        result[s["uid"]] = {
            "name": s["name"],
            "student_name": s.get("student_name", ""),
            "group": s.get("group", ""),
            "rank": s.get("rank", ""),
        }
    return result

def db_upsert_student_user(uid: str, name: str, student_name: str = "", group: str = "", rank: str = ""):
    col("student_users").update_one(
        {"uid": uid},
        {"$set": {"uid": uid, "name": name, "student_name": student_name, "group": group, "rank": rank}},
        upsert=True
    )

def db_get_attendance() -> dict:
    result = {}
    for a in col("attendance").find({}, {"_id": 0}):
        result[a["key"]] = a
    return result

def db_save_attendance(key: str, record: dict):
    data = deepcopy(record)
    data["key"] = key
    col("attendance").update_one({"key": key}, {"$set": data}, upsert=True)

# ─────────────────────────────────────────────
# HEALTH SERVER ДЛЯ RENDER
# ─────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"✅ Health server запущено на порту {port}")
    server.serve_forever()

# ─────────────────────────────────────────────
# HELPERS — групові розсилки
# ─────────────────────────────────────────────
def group_matches(user_group: str, user_rank: str, target_group: str) -> bool:
    if not target_group or target_group.lower() in ("всі", "all", ""):
        return True
    target_lower = target_group.lower()
    return (user_group.lower() == target_lower or
            user_rank.lower() == target_lower or
            target_lower in user_group.lower() or
            target_lower in user_rank.lower())

def notify_group(bot, target_group: str, text: str):
    sent = 0
    for pid, info in db_get_parents().items():
        if group_matches(info.get("group", ""), info.get("rank", ""), target_group):
            try:
                bot.send_message(chat_id=int(pid), text=text)
                sent += 1
            except Exception as e:
                logger.error(f"Помилка при надіслані батькові {pid}: {e}")
    for uid, info in db_get_student_users().items():
        if group_matches(info.get("group", ""), info.get("rank", ""), target_group):
            try:
                bot.send_message(chat_id=int(uid), text=text)
                sent += 1
            except Exception as e:
                logger.error(f"Помилка при надіслані учню {uid}: {e}")
    return sent

def notify_all(bot, text: str):
    return notify_group(bot, "", text)

# ─────────────────────────────────────────────
# ПЕРЕВІРКА РОЛІ
# ─────────────────────────────────────────────
def is_trainer(user_id: int) -> bool:
    return user_id == TRAINER_ID

# ─────────────────────────────────────────────
# КЛАВІАТУРИ
# ─────────────────────────────────────────────
def main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("📋 Список учнів", "📅 Розклад занять")
    keyboard.add("📚 Домашні завдання", "📢 Новини/Оголошення")
    keyboard.add("🎓 Матеріали", "💬 Чат з батьками")
    keyboard.add("✅ Відвідуваність", "🏆 Турніри")
    return keyboard

def back_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("⬅️ Головне меню")
    return keyboard

def students_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("➕ Додати учня", "🗑 Видалити учня")
    keyboard.add("📄 Показати всіх", "⬅️ Головне меню")
    return keyboard

def schedule_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("➕ Додати заняття", "📋 Показати розклад")
    keyboard.add("🗑 Видалити заняття", "⬅️ Головне меню")
    return keyboard

def homework_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("➕ Задати домашнє", "📋 Показати завдання")
    keyboard.add("🗑 Видалити завдання", "⬅️ Головне меню")
    return keyboard

def news_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("➕ Додати новину", "📋 Показати новини")
    keyboard.add("🗑 Видалити новину", "⬅️ Головне меню")
    return keyboard

def materials_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("➕ Додати матеріал", "📋 Показати матеріали")
    keyboard.add("🗑 Видалити матеріал", "⬅️ Головне меню")
    return keyboard

def chat_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("📣 Розіслати всім батькам", "👥 Список батьків")
    keyboard.add("🔗 Прив'язати батька до учня", "⬅️ Головне меню")
    return keyboard

def attendance_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("📝 Відмітити відвідуваність", "📊 Статистика відвідуваності")
    keyboard.add("📋 Журнал за датою", "⬅️ Головне меню")
    return keyboard

def tournaments_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("➕ Додати турнір", "📋 Показати турніри")
    keyboard.add("🗑 Видалити турнір", "⬅️ Головне меню")
    return keyboard

def parent_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("📅 Розклад занять", "📚 Домашні завдання")
    keyboard.add("✅ Відвідуваність дитини", "🏆 Турніри")
    return keyboard

def student_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("📅 Розклад занять", "📚 Домашні завдання")
    keyboard.add("✅ Моя відвідуваність", "🎓 Навчальні матеріали")
    keyboard.add("🏆 Турніри")
    return keyboard

def role_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("♟️ Я учень")
    keyboard.add("👨‍👩‍👦 Я батько/мати")
    return keyboard

# ─────────────────────────────────────────────
# BOT INSTANCE
# ─────────────────────────────────────────────
bot = telebot.TeleBot(BOT_TOKEN)

# Зберігаємо стан користувача
user_states = {}

# ─────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user = message.from_user

    if is_trainer(user_id):
        bot.send_message(
            user_id,
            f"♟️ Вітаємо, тренере {user.first_name}!\n\nОберіть розділ 👇",
            reply_markup=main_keyboard()
        )
        user_states[user_id] = "main_menu"
        return

    if str(user_id) in db_get_student_users():
        info = db_get_student_users()[str(user_id)]
        bot.send_message(
            user_id,
            f"♟️ Вітаємо, {info['student_name']}!\n"
            f"👥 Група: {info.get('group','')} | 🏅 Розряд: {info.get('rank','')}",
            reply_markup=student_keyboard()
        )
        user_states[user_id] = "student_menu"
        return

    if str(user_id) in db_get_parents():
        info = db_get_parents()[str(user_id)]
        bot.send_message(
            user_id,
            f"👋 Вітаємо, {user.first_name}!\n"
            f"👤 Дитина: {info.get('student') or 'ще не прив`язано'}",
            reply_markup=parent_keyboard()
        )
        user_states[user_id] = "parent_menu"
        return

    bot.send_message(
        user_id,
        f"👋 Вітаємо, {user.first_name}!\n\nБудь ласка, оберіть хто ви:",
        reply_markup=role_keyboard()
    )
    user_states[user_id] = "choose_role"

# ─────────────────────────────────────────────
# ВИБІР РОЛІ
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "choose_role")
def choose_role(message):
    user_id = message.from_user.id
    text = message.text

    if text == "♟️ Я учень":
        bot.send_message(
            user_id,
            "📱 Введіть ваш номер телефону який вказав тренер при реєстрації:\n\nФормат: +380991234567",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("⬅️ Назад")
        )
        user_states[user_id] = "register_student"

    elif text == "👨‍👩‍👦 Я батько/мати":
        db_upsert_parent(str(user_id), message.from_user.full_name)
        bot.send_message(
            user_id,
            "✅ Ви зареєстровані як батько/мати!\n\n"
            "Тренер прив'яже вас до вашої дитини.\n"
            "До того часу ви можете переглядати розклад та домашні завдання.",
            reply_markup=parent_keyboard()
        )
        user_states[user_id] = "parent_menu"

# ─────────────────────────────────────────────
# РЕЄСТРАЦІЯ УЧНЯ
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "register_student")
def register_student(message):
    user_id = message.from_user.id
    text = message.text.strip()

    if text == "⬅️ Назад":
        bot.send_message(user_id, "Оберіть роль:", reply_markup=role_keyboard())
        user_states[user_id] = "choose_role"
        return

    student = db_find_student_by_phone(text)
    if not student:
        bot.send_message(
            user_id,
            "❌ Номер телефону не знайдено в базі.\n\n"
            "Перевірте номер або зверніться до тренера.\n\nСпробуйте ще раз:",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("⬅️ Назад")
        )
        return

    db_upsert_student_user(
        str(user_id), message.from_user.full_name,
        student["name"],
        student.get("group", ""),
        student.get("rank", "")
    )
    bot.send_message(
        user_id,
        f"✅ Вітаємо, {student['name']}!\n\n"
        f"👥 Ваша група: {student.get('group', '—')}\n"
        f"🏅 Розряд: {student.get('rank', '—')}\n\n"
        "Тепер ви маєте доступ до розкладу, домашніх завдань та матеріалів ♟️",
        reply_markup=student_keyboard()
    )
    user_states[user_id] = "student_menu"

# ─────────────────────────────────────────────
# МЕНЮ УЧНЯ
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "student_menu")
def student_menu_handler(message):
    user_id = message.from_user.id
    text = message.text

    if text == "⬅️ Головне меню":
        if is_trainer(user_id):
            bot.send_message(user_id, "Меню тренера:", reply_markup=main_keyboard())
            user_states[user_id] = "main_menu"
        return

    uid = str(user_id)
    info = db_get_student_users().get(uid, {})
    student_name = info.get("student_name", "")
    student_group = info.get("group", "")
    student_rank = info.get("rank", "")

    if text == "📅 Розклад занять":
        schedule = db_get_schedule()
        my_schedule = [s for s in schedule if group_matches(student_group, student_rank, s.get("group", ""))]
        if not my_schedule:
            bot.send_message(user_id, "📭 Занять для вашої групи не знайдено.", reply_markup=student_keyboard())
        else:
            days_order = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
            sorted_s = sorted(my_schedule, key=lambda x: days_order.index(x["day"]) if x["day"] in days_order else 9)
            msg = f"📅 Розклад для групи {student_group}:\n\n" + "".join(
                f"📌 {s['day']} {s['time']} — {s['group']} ({s['place']})\n" for s in sorted_s)
            bot.send_message(user_id, msg, reply_markup=student_keyboard())

    elif text == "📚 Домашні завдання":
        homework = db_get_homework()
        my_hw = [h for h in homework if group_matches(student_group, student_rank, h.get("group", ""))]
        if not my_hw:
            bot.send_message(user_id, "📭 Домашніх завдань для вашої групи немає.", reply_markup=student_keyboard())
        else:
            msg = f"📚 Домашні завдання для групи {student_group}:\n\n"
            for i, h in enumerate(my_hw, 1):
                msg += f"{i}. [{h['group']}] {h['task']}\n   📅 До: {h['deadline']}\n\n"
            bot.send_message(user_id, msg, reply_markup=student_keyboard())

    elif text == "✅ Моя відвідуваність":
        if not student_name:
            bot.send_message(user_id, "⚠️ Помилка. Зверніться до тренера.", reply_markup=student_keyboard())
            return
        present_count = absent_count = 0
        for record in db_get_attendance().values():
            if student_name in record.get("present", []):
                present_count += 1
            elif student_name in record.get("absent", []):
                absent_count += 1
        total = present_count + absent_count
        percent = round(present_count / total * 100) if total > 0 else 0
        bot.send_message(
            user_id,
            f"✅ Моя відвідуваність\n\n"
            f"👤 {student_name}\n"
            f"👥 Група: {student_group} | 🏅 {student_rank}\n"
            f"✔️ Був(ла): {present_count} занять\n"
            f"❌ Пропустив(ла): {absent_count} занять\n"
            f"📊 Відсоток: {percent}%",
            reply_markup=student_keyboard()
        )

    elif text == "🎓 Навчальні матеріали":
        materials = db_get_materials()
        if not materials:
            bot.send_message(user_id, "📭 Матеріалів ще немає.", reply_markup=student_keyboard())
        else:
            msg = "🎓 Навчальні матеріали:\n\n"
            for i, m in enumerate(materials, 1):
                msg += f"{i}. {m['title']}\n   🔗 {m['link']}\n   📁 {m['category']}\n\n"
            bot.send_message(user_id, msg, reply_markup=student_keyboard())

    elif text == "🏆 Турніри":
        tournaments = db_get_tournaments()
        my_tournaments = [t for t in tournaments
                          if group_matches(student_group, student_rank, t.get("for_group", ""))]
        if not my_tournaments:
            bot.send_message(user_id, "📭 Турнірів для вашої групи немає.", reply_markup=student_keyboard())
        else:
            msg = "🏆 Турніри для вашої групи:\n\n"
            for i, t in enumerate(my_tournaments, 1):
                for_who = t.get("for_group", "Всі")
                msg += f"{i}. {t['title']}\n   📅 {t['date']}\n   📍 {t['place']}\n   👥 Для: {for_who}\n   ℹ️ {t['info']}\n\n"
            bot.send_message(user_id, msg, reply_markup=student_keyboard())

# ─────────────────────────────────────────────
# МЕНЮ БАТЬКІВ
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "parent_menu")
def parent_menu_handler(message):
    user_id = message.from_user.id
    text = message.text

    if text == "⬅️ Головне меню":
        if is_trainer(user_id):
            bot.send_message(user_id, "Меню тренера:", reply_markup=main_keyboard())
            user_states[user_id] = "main_menu"
        return

    user_id_str = str(user_id)
    parent_info = db_get_parents().get(user_id_str, {})
    parent_group = parent_info.get("group", "")
    parent_rank = parent_info.get("rank", "")

    if text == "📅 Розклад занять":
        schedule = db_get_schedule()
        my_schedule = [s for s in schedule if group_matches(parent_group, parent_rank, s.get("group", ""))]
        if not my_schedule:
            bot.send_message(user_id, "📭 Розклад для вашої групи ще не додано.", reply_markup=parent_keyboard())
        else:
            days_order = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
            sorted_s = sorted(my_schedule, key=lambda x: days_order.index(x["day"]) if x["day"] in days_order else 9)
            child = parent_info.get("student", "")
            msg = f"📅 Розклад занять{f' ({child})' if child else ''}:\n\n" + "".join(
                f"📌 {s['day']} {s['time']} — {s['group']} ({s['place']})\n" for s in sorted_s)
            bot.send_message(user_id, msg, reply_markup=parent_keyboard())

    elif text == "📚 Домашні завдання":
        homework = db_get_homework()
        my_hw = [h for h in homework if group_matches(parent_group, parent_rank, h.get("group", ""))]
        if not my_hw:
            bot.send_message(user_id, "📭 Домашніх завдань для вашої групи немає.", reply_markup=parent_keyboard())
        else:
            child = parent_info.get("student", "")
            msg = f"📚 Домашні завдання{f' ({child})' if child else ''}:\n\n"
            for i, h in enumerate(my_hw, 1):
                msg += f"{i}. [{h['group']}] {h['task']}\n   📅 До: {h['deadline']}\n\n"
            bot.send_message(user_id, msg, reply_markup=parent_keyboard())

    elif text == "✅ Відвідуваність дитини":
        student_name = parent_info.get("student", "")
        if not student_name:
            bot.send_message(
                user_id,
                "⚠️ Вашу дитину ще не прив'язано.\nЗверніться до тренера.",
                reply_markup=parent_keyboard()
            )
            return
        present_count = absent_count = 0
        for record in db_get_attendance().values():
            if student_name in record.get("present", []):
                present_count += 1
            elif student_name in record.get("absent", []):
                absent_count += 1
        total = present_count + absent_count
        percent = round(present_count / total * 100) if total > 0 else 0
        bot.send_message(
            user_id,
            f"✅ Відвідуваність: {student_name}\n\n"
            f"👥 Група: {parent_group} | 🏅 {parent_rank}\n"
            f"✔️ Був(ла): {present_count} занять\n"
            f"❌ Пропустив(ла): {absent_count} занять\n"
            f"📊 Відсоток: {percent}%",
            reply_markup=parent_keyboard()
        )

    elif text == "🏆 Турніри":
        tournaments = db_get_tournaments()
        my_tournaments = [t for t in tournaments
                          if group_matches(parent_group, parent_rank, t.get("for_group", ""))]
        if not my_tournaments:
            bot.send_message(user_id, "📭 Турнірів для вашої групи немає.", reply_markup=parent_keyboard())
        else:
            msg = "🏆 Турніри:\n\n"
            for i, t in enumerate(my_tournaments, 1):
                msg += f"{i}. {t['title']}\n   📅 {t['date']}\n   📍 {t['place']}\n   👥 Для: {t.get('for_group','Всі')}\n   ℹ️ {t['info']}\n\n"
            bot.send_message(user_id, msg, reply_markup=parent_keyboard())

# ─────────────────────────────────────────────
# ГОЛОВНЕ МЕНЮ ТРЕНЕРА
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "main_menu")
def main_menu_handler(message):
    user_id = message.from_user.id
    if not is_trainer(user_id):
        uid = str(user_id)
        if uid in db_get_student_users():
            bot.send_message(user_id, "Ваше меню:", reply_markup=student_keyboard())
            user_states[user_id] = "student_menu"
        else:
            bot.send_message(user_id, "Ваше меню:", reply_markup=parent_keyboard())
            user_states[user_id] = "parent_menu"
        return

    text = message.text
    if text == "📋 Список учнів":
        bot.send_message(user_id, "👦 Управління учнями:", reply_markup=students_keyboard())
        user_states[user_id] = "students_menu"
    elif text == "📅 Розклад занять":
        bot.send_message(user_id, "📅 Управління розкладом:", reply_markup=schedule_keyboard())
        user_states[user_id] = "schedule_menu"
    elif text == "📚 Домашні завдання":
        bot.send_message(user_id, "📚 Домашні завдання:", reply_markup=homework_keyboard())
        user_states[user_id] = "homework_menu"
    elif text == "📢 Новини/Оголошення":
        bot.send_message(user_id, "📢 Новини школи:", reply_markup=news_keyboard())
        user_states[user_id] = "news_menu"
    elif text == "🎓 Матеріали":
        bot.send_message(user_id, "🎓 Навчальні матеріали:", reply_markup=materials_keyboard())
        user_states[user_id] = "materials_menu"
    elif text == "💬 Чат з батьками":
        bot.send_message(
            user_id,
            f"💬 Комунікація з батьками\n👥 Зареєстровано батьків: {len(db_get_parents())}",
            reply_markup=chat_keyboard()
        )
        user_states[user_id] = "chat_menu"
    elif text == "✅ Відвідуваність":
        bot.send_message(user_id, "✅ Журнал відвідуваності:", reply_markup=attendance_keyboard())
        user_states[user_id] = "attendance_menu"
    elif text == "🏆 Турніри":
        bot.send_message(user_id, "🏆 Управління турнірами:", reply_markup=tournaments_keyboard())
        user_states[user_id] = "tournaments_menu"

# ─────────────────────────────────────────────
# УЧНІ
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "students_menu")
def students_menu(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
    elif text == "📄 Показати всіх":
        students = db_get_students()
        if not students:
            bot.send_message(user_id, "📭 Список учнів порожній.", reply_markup=students_keyboard())
        else:
            msg = "📋 Список учнів:\n\n"
            for i, s in enumerate(students, 1):
                msg += (f"{i}. {s['name']}\n"
                        f"   🏅 {s.get('rank','—')} | 👥 {s.get('group','—')}\n"
                        f"   👨‍👩‍👦 {s.get('parent_phone','—')} | 📱 {s.get('student_phone','—')}\n\n")
            bot.send_message(user_id, msg, reply_markup=students_keyboard())
    elif text == "➕ Додати учня":
        bot.send_message(
            user_id,
            "Введіть дані учня у форматі:\n"
            "<b>Ім'я | Розряд | Група | Тел.батьків | Тел.учня</b>\n\n"
            "Приклад:\nОлег Іванов | 1-2 розряд | 1-2 розряд | +380991234567 | +380671234567",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )
        user_states[user_id] = "add_student"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "add_student")
def add_student(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
        return
    
    try:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 4:
            raise ValueError(f"Потрібно мінімум 4 поля через |, отримано {len(parts)}")
        student = {
            "name":          parts[0],
            "rank":          parts[1],
            "group":         parts[2],
            "parent_phone":  parts[3],
            "student_phone": parts[4] if len(parts) > 4 else "",
            "added":         datetime.now().strftime("%d.%m.%Y")
        }
        db_add_student(student)
        msg = (f"✅ Учня {student['name']} успішно додано!\n\n"
               f"🏅 Розряд: {student['rank']}\n"
               f"👥 Група: {student['group']}\n")
        if student["student_phone"]:
            msg += f"\n📱 Учень може увійти через номер: {student['student_phone']}"
        else:
            msg += "\n⚠️ Телефон учня не вказано"
        bot.send_message(user_id, msg, reply_markup=students_keyboard())
        user_states[user_id] = "students_menu"
    except Exception as e:
        bot.send_message(
            user_id,
            f"❌ Помилка: {e}\n\nФормат:\n<b>Ім'я | Розряд | Група | Тел.батьків | Тел.учня</b>",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )

# ─────────────────────────────────────────────
# РОЗКЛАД
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "schedule_menu")
def schedule_menu(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
    elif text == "📋 Показати розклад":
        schedule = db_get_schedule()
        if not schedule:
            bot.send_message(user_id, "📭 Розклад порожній.", reply_markup=schedule_keyboard())
        else:
            days_order = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
            sorted_s = sorted(schedule, key=lambda x: days_order.index(x["day"]) if x["day"] in days_order else 9)
            msg = "📅 Розклад занять:\n\n" + "".join(
                f"📌 {s['day']} {s['time']} — {s['group']} ({s['place']})\n" for s in sorted_s)
            bot.send_message(user_id, msg, reply_markup=schedule_keyboard())
    elif text == "➕ Додати заняття":
        bot.send_message(
            user_id,
            "Введіть заняття у форматі:\n<b>День | Час | Група | Місце</b>\n\n"
            "Приклад: Пн | 17:00 | 1-2 розряд | Зал №1",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )
        user_states[user_id] = "add_schedule"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "add_schedule")
def add_schedule(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
        return
    
    try:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 4:
            raise ValueError(f"Потрібно 4 поля")
        entry = {"day": parts[0], "time": parts[1], "group": parts[2], "place": parts[3]}
        db_add_schedule(entry)
        notify_text = (
            f"📅 Нова заняття в розкладі!\n\n"
            f"📌 {entry['day']} о {entry['time']}\n"
            f"📍 {entry['place']}"
        )
        sent = notify_group(bot, entry['group'], notify_text)
        bot.send_message(
            user_id,
            f"✅ Заняття {entry['day']} {entry['time']} для групи {entry['group']} додано!\n"
            f"📨 Надіслано {sent} повідомлень.",
            reply_markup=schedule_keyboard()
        )
        user_states[user_id] = "schedule_menu"
    except Exception as e:
        bot.send_message(
            user_id,
            f"❌ Помилка: {e}\n\nФормат: <b>День | Час | Група | Місце</b>",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )

# ─────────────────────────────────────────────
# ДОМАШНІ ЗАВДАННЯ
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "homework_menu")
def homework_menu(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
    elif text == "📋 Показати завдання":
        homework = db_get_homework()
        if not homework:
            bot.send_message(user_id, "📭 Завдань немає.", reply_markup=homework_keyboard())
        else:
            msg = "📚 Домашні завдання:\n\n"
            for i, h in enumerate(homework, 1):
                msg += f"{i}. [{h['group']}] {h['task']}\n   📅 До: {h['deadline']}\n\n"
            bot.send_message(user_id, msg, reply_markup=homework_keyboard())
    elif text == "➕ Задати домашнє":
        bot.send_message(
            user_id,
            "Введіть завдання у форматі:\n<b>Група | Завдання | Дедлайн</b>\n\n"
            "Приклад: 1-2 розряд | Вивчити захист Філідора | 15.03.2025",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )
        user_states[user_id] = "add_homework"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "add_homework")
def add_homework(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
        return
    
    try:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 3:
            raise ValueError("Потрібно 3 поля")
        hw = {"group": parts[0], "task": parts[1], "deadline": parts[2],
              "created": datetime.now().strftime("%d.%m.%Y")}
        db_add_homework(hw)
        notify_text = (f"📚 Нове домашнє завдання!\n\n"
                       f"👥 Група: {hw['group']}\n"
                       f"📝 {hw['task']}\n"
                       f"📅 До: {hw['deadline']}")
        sent = notify_group(bot, hw["group"], notify_text)
        bot.send_message(
            user_id,
            f"✅ Завдання для групи {hw['group']} додано!\n📨 Надіслано {sent} повідомлень.",
            reply_markup=homework_keyboard()
        )
        user_states[user_id] = "homework_menu"
    except Exception as e:
        bot.send_message(
            user_id,
            f"❌ Помилка: {e}\n\nФормат: <b>Група | Завдання | Дедлайн</b>",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )

# ─────────────────────────────────────────────
# НОВИНИ
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "news_menu")
def news_menu(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
    elif text == "📋 Показати новини":
        news = db_get_news()
        if not news:
            bot.send_message(user_id, "📭 Новин немає.", reply_markup=news_keyboard())
        else:
            msg = "📢 Новини:\n\n"
            for i, n in enumerate(news, 1):
                msg += f"{i}. {n['title']}\n   {n['text']}\n   📅 {n['date']}\n\n"
            bot.send_message(user_id, msg, reply_markup=news_keyboard())
    elif text == "➕ Додати новину":
        bot.send_message(
            user_id,
            "Введіть новину у форматі:\n<b>Заголовок | Текст</b>\n\n"
            "💡 Новини надсилаються ВСІМ батькам і учням",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )
        user_states[user_id] = "add_news"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "add_news")
def add_news(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
        return
    
    try:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 2:
            raise ValueError("Потрібно 2 поля")
        news_item = {"title": parts[0], "text": parts[1], "date": datetime.now().strftime("%d.%m.%Y")}
        db_add_news(news_item)
        notify_text = f"📢 {news_item['title']}\n\n{news_item['text']}"
        sent = notify_all(bot, notify_text)
        bot.send_message(
            user_id,
            f"✅ Новину опубліковано! Надіслано {sent} повідомлень.",
            reply_markup=news_keyboard()
        )
        user_states[user_id] = "news_menu"
    except Exception as e:
        bot.send_message(
            user_id,
            f"❌ Помилка: {e}\n\nФормат: <b>Заголовок | Текст</b>",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )

# ─────────────────────────────────────────────
# МАТЕРІАЛИ
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "materials_menu")
def materials_menu(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
    elif text == "📋 Показати матеріали":
        materials = db_get_materials()
        if not materials:
            bot.send_message(user_id, "📭 Матеріалів немає.", reply_markup=materials_keyboard())
        else:
            msg = "🎓 Навчальні матеріали:\n\n"
            for i, m in enumerate(materials, 1):
                msg += f"{i}. {m['title']}\n   🔗 {m['link']}\n   📁 {m['category']}\n\n"
            bot.send_message(user_id, msg, reply_markup=materials_keyboard())
    elif text == "➕ Додати матеріал":
        bot.send_message(
            user_id,
            "Введіть матеріал у форматі:\n<b>Назва | Посилання | Категорія</b>\n\n"
            "Приклад: Збірник задач | https://example.com | Задачники",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )
        user_states[user_id] = "add_material"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "add_material")
def add_material(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
        return
    
    try:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 3:
            raise ValueError("Потрібно 3 поля")
        mat = {"title": parts[0], "link": parts[1], "category": parts[2],
               "date": datetime.now().strftime("%d.%m.%Y")}
        db_add_material(mat)
        bot.send_message(user_id, f"✅ Матеріал '{mat['title']}' додано!", reply_markup=materials_keyboard())
        user_states[user_id] = "materials_menu"
    except Exception as e:
        bot.send_message(
            user_id,
            f"❌ Помилка: {e}\n\nФормат: <b>Назва | Посилання | Категорія</b>",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )

# ─────────────────────────────────────────────
# ТУРНІРИ
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "tournaments_menu")
def tournaments_menu(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
    elif text == "📋 Показати турніри":
        tournaments = db_get_tournaments()
        if not tournaments:
            bot.send_message(user_id, "📭 Турнірів немає.", reply_markup=tournaments_keyboard())
        else:
            msg = "🏆 Турніри:\n\n"
            for i, t in enumerate(tournaments, 1):
                msg += (f"{i}. {t['title']}\n"
                        f"   📅 {t['date']} | 📍 {t['place']}\n"
                        f"   👥 Для: {t.get('for_group', 'Всі')}\n"
                        f"   ℹ️ {t['info']}\n\n")
            bot.send_message(user_id, msg, reply_markup=tournaments_keyboard())
    elif text == "➕ Додати турнір":
        bot.send_message(
            user_id,
            "Введіть турнір у форматі:\n<b>Назва | Дата | Місце | Для кого | Інфо</b>\n\n"
            "Приклади:\nКубок міста | 15.04.2025 | ДЮСШ №3 | 1-2 розряд | Реєстрація до 10.04",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )
        user_states[user_id] = "add_tournament"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "add_tournament")
def add_tournament(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
        return
    
    try:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 5:
            raise ValueError("Потрібно 5 полів")
        t = {"title": parts[0], "date": parts[1], "place": parts[2],
             "for_group": parts[3], "info": parts[4]}
        db_add_tournament(t)
        notify_text = (f"🏆 Новий турнір!\n\n{t['title']}\n"
                       f"📅 {t['date']}\n📍 {t['place']}\n"
                       f"👥 Для: {t['for_group']}\nℹ️ {t['info']}")
        sent = notify_group(bot, t["for_group"], notify_text)
        bot.send_message(
            user_id,
            f"✅ Турнір додано!\n👥 Для: {t['for_group']}\n📨 Надіслано {sent} повідомлень.",
            reply_markup=tournaments_keyboard()
        )
        user_states[user_id] = "tournaments_menu"
    except Exception as e:
        bot.send_message(
            user_id,
            f"❌ Помилка: {e}\n\nФормат: <b>Назва | Дата | Місце | Для кого | Інфо</b>",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )

# ─────────────────────────────────────────────
# ЧАТ З БАТЬКАМИ
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "chat_menu")
def chat_menu(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
    elif text == "👥 Список батьків":
        parents = db_get_parents()
        if not parents:
            bot.send_message(user_id, "📭 Жоден батько ще не зареєструвався.", reply_markup=chat_keyboard())
        else:
            msg = "👥 Зареєстровані батьки:\n\n"
            for pid, info in parents.items():
                msg += (f"• {info['name']}\n"
                        f"  👤 {info.get('student','—')} | 👥 {info.get('group','—')}\n\n")
            bot.send_message(user_id, msg, reply_markup=chat_keyboard())
    elif text == "📣 Розіслати всім батькам":
        bot.send_message(user_id, "Введіть повідомлення для розсилки:", reply_markup=back_keyboard())
        user_states[user_id] = "broadcast_msg"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "broadcast_msg")
def broadcast_message(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
        return
    
    sent = failed = 0
    for pid in db_get_parents():
        try:
            bot.send_message(chat_id=int(pid), text=f"📣 Від тренера:\n\n{text}")
            sent += 1
        except Exception:
            failed += 1
    
    bot.send_message(
        user_id,
        f"✅ Розсилку завершено!\n📨 Надіслано: {sent}\n❌ Не вдалося: {failed}",
        reply_markup=chat_keyboard()
    )
    user_states[user_id] = "chat_menu"

# ─────────────────────────────────────────────
# ВІДВІДУВАНІСТЬ
# ─────────────────────────────────────────────
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "attendance_menu")
def attendance_menu(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == "⬅️ Головне меню":
        bot.send_message(user_id, "Головне меню:", reply_markup=main_keyboard())
        user_states[user_id] = "main_menu"
    elif text == "📝 Відмітити відвідуваність":
        students = db_get_students()
        if not students:
            bot.send_message(user_id, "📭 Спочатку додайте учнів.", reply_markup=attendance_keyboard())
            return
        
        today = datetime.now().strftime("%d.%m.%Y")
        msg = f"📝 Відвідуваність на {today}\n\nОберіть учнів:\n\n"
        for s in students:
            msg += f"✅ {s['name']} чи ❌\n"
        
        bot.send_message(user_id, msg, reply_markup=attendance_keyboard())
        user_states[user_id] = "attendance_mark"
    
    elif text == "📊 Статистика відвідуваності":
        attendance = db_get_attendance()
        if not attendance:
            bot.send_message(user_id, "📭 Даних ще немає.", reply_markup=attendance_keyboard())
            return
        
        stats = {}
        for record in attendance.values():
            for name in record.get("present", []):
                stats.setdefault(name, {"present": 0, "absent": 0})["present"] += 1
            for name in record.get("absent", []):
                stats.setdefault(name, {"present": 0, "absent": 0})["absent"] += 1
        
        msg = "📊 Статистика відвідуваності:\n\n"
        for name, data in stats.items():
            total = data["present"] + data["absent"]
            pct = round(data["present"] / total * 100) if total > 0 else 0
            msg += f"👤 {name}\n   ✅ {data['present']} | ❌ {data['absent']} | 📊 {pct}%\n\n"
        bot.send_message(user_id, msg, reply_markup=attendance_keyboard())
    
    elif text == "📋 Журнал за датою":
        attendance = db_get_attendance()
        if not attendance:
            bot.send_message(user_id, "📭 Даних ще немає.", reply_markup=attendance_keyboard())
            return
        
        msg = "📋 Журнал відвідуваності:\n\n"
        for key, record in sorted(attendance.items(), reverse=True)[:10]:
            present = ", ".join(record.get("present", [])) or "—"
            absent  = ", ".join(record.get("absent",  [])) or "—"
            msg += f"📅 {record.get('date', key)}\n✅ {present}\n❌ {absent}\n\n"
        bot.send_message(user_id, msg, reply_markup=attendance_keyboard())

# ─────────────────────────────────────────────
# ЗАПУСК
# ─────────────────────────────────────────────
def main():
    try:
        init_mongo()
    except Exception as e:
        logger.error(f"❌ КРИТИЧНА ПОМИЛКА MongoDB: {e}")
        return

    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не знайдено!")
        return

    # ✅ Запускаємо health server в окремому потоці
    threading.Thread(target=run_health_server, daemon=True).start()

    logger.info("♟️ Chess Trainer Bot v5.4 запущено (pyTelegramBotAPI 4.14.0)!")
    bot.polling(none_stop=True)


if __name__ == "__main__":
    main()
