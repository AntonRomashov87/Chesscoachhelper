"""
♟️ Chess Trainer Bot v4.0 — Telegram-бот для тренера шахової школи
НОВЕ: Окремі ролі для учня, батька і тренера
Залежності: pip install python-telegram-bot[job-queue]==20.7 pymongo[srv]==4.9.2 certifi dnspython
"""

import logging
import os
from copy import deepcopy
from datetime import datetime
from pymongo import MongoClient
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)

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
# СТАНИ РОЗМОВИ
# ─────────────────────────────────────────────
(
    MAIN_MENU, STUDENTS_MENU, ADD_STUDENT, SCHEDULE_MENU,
    ADD_SCHEDULE, HOMEWORK_MENU, ADD_HOMEWORK,
    NEWS_MENU, ADD_NEWS, MATERIALS_MENU, ADD_MATERIAL,
    CHAT_MENU, BROADCAST_MSG, ATTENDANCE_MENU,
    PARENT_MENU, STUDENT_MENU,
    TOURNAMENTS_MENU, ADD_TOURNAMENT,
    CHOOSE_ROLE, REGISTER_STUDENT, REGISTER_PARENT,
    LINK_PARENT
) = range(22)

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

# ── Учні ──
def db_get_students() -> list:
    return list(col("students").find({}, {"_id": 0}))

def db_add_student(student: dict):
    col("students").insert_one(deepcopy(student))

def db_delete_student(idx: int):
    items = db_get_students()
    if 0 <= idx < len(items):
        col("students").delete_one({"name": items[idx]["name"]})

def db_find_student_by_phone(phone: str):
    """Знаходить учня за телефоном учня"""
    return col("students").find_one({"student_phone": phone}, {"_id": 0})

# ── Розклад ──
def db_get_schedule() -> list:
    return list(col("schedule").find({}, {"_id": 0}))

def db_add_schedule(entry: dict):
    col("schedule").insert_one(deepcopy(entry))

def db_delete_schedule(idx: int):
    items = db_get_schedule()
    if 0 <= idx < len(items):
        item = items[idx]
        col("schedule").delete_one({"day": item["day"], "time": item["time"], "group": item["group"]})

# ── Домашні завдання ──
def db_get_homework() -> list:
    return list(col("homework").find({}, {"_id": 0}))

def db_add_homework(hw: dict):
    col("homework").insert_one(deepcopy(hw))

def db_delete_homework(idx: int):
    items = db_get_homework()
    if 0 <= idx < len(items):
        item = items[idx]
        col("homework").delete_one({"group": item["group"], "task": item["task"], "deadline": item["deadline"]})

# ── Новини ──
def db_get_news() -> list:
    return list(col("news").find({}, {"_id": 0}))

def db_add_news(item: dict):
    col("news").insert_one(deepcopy(item))

def db_delete_news(idx: int):
    items = db_get_news()
    if 0 <= idx < len(items):
        item = items[idx]
        col("news").delete_one({"title": item["title"], "date": item["date"]})

# ── Матеріали ──
def db_get_materials() -> list:
    return list(col("materials").find({}, {"_id": 0}))

def db_add_material(mat: dict):
    col("materials").insert_one(deepcopy(mat))

def db_delete_material(idx: int):
    items = db_get_materials()
    if 0 <= idx < len(items):
        item = items[idx]
        col("materials").delete_one({"title": item["title"], "link": item["link"]})

# ── Турніри ──
def db_get_tournaments() -> list:
    return list(col("tournaments").find({}, {"_id": 0}))

def db_add_tournament(t: dict):
    col("tournaments").insert_one(deepcopy(t))

def db_delete_tournament(idx: int):
    items = db_get_tournaments()
    if 0 <= idx < len(items):
        col("tournaments").delete_one({"title": items[idx]["title"], "date": items[idx]["date"]})

# ── Батьки ──
def db_get_parents() -> dict:
    result = {}
    for p in col("parents").find({}, {"_id": 0}):
        result[p["pid"]] = {"name": p["name"], "student": p.get("student", "")}
    return result

def db_upsert_parent(pid: str, name: str, student: str = ""):
    col("parents").update_one(
        {"pid": pid},
        {"$set": {"pid": pid, "name": name, "student": student}},
        upsert=True
    )

def db_link_parent_to_student(pid: str, student_name: str):
    col("parents").update_one({"pid": pid}, {"$set": {"student": student_name}})

# ── Учні-користувачі (Telegram акаунти учнів) ──
def db_get_student_users() -> dict:
    result = {}
    for s in col("student_users").find({}, {"_id": 0}):
        result[s["uid"]] = {"name": s["name"], "student_name": s.get("student_name", "")}
    return result

def db_upsert_student_user(uid: str, name: str, student_name: str = ""):
    col("student_users").update_one(
        {"uid": uid},
        {"$set": {"uid": uid, "name": name, "student_name": student_name}},
        upsert=True
    )

# ── Відвідуваність ──
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
# ПЕРЕВІРКА РОЛІ
# ─────────────────────────────────────────────
def is_trainer(update: Update) -> bool:
    return update.effective_user.id == TRAINER_ID

def is_student_user(update: Update) -> bool:
    uid = str(update.effective_user.id)
    return uid in db_get_student_users()

def is_parent(update: Update) -> bool:
    uid = str(update.effective_user.id)
    return uid in db_get_parents()

# ─────────────────────────────────────────────
# КЛАВІАТУРИ — ТРЕНЕР
# ─────────────────────────────────────────────
def main_keyboard():
    return ReplyKeyboardMarkup([
        ["📋 Список учнів",     "📅 Розклад занять"],
        ["📚 Домашні завдання", "📢 Новини/Оголошення"],
        ["🎓 Матеріали",        "💬 Чат з батьками"],
        ["✅ Відвідуваність",   "🏆 Турніри"],
    ], resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup([["⬅️ Головне меню"]], resize_keyboard=True)

def back_to_schedule_keyboard():
    return ReplyKeyboardMarkup([["⬅️ До розкладу"], ["⬅️ Головне меню"]], resize_keyboard=True)

def back_to_students_keyboard():
    return ReplyKeyboardMarkup([["⬅️ До списку учнів"], ["⬅️ Головне меню"]], resize_keyboard=True)

def back_to_homework_keyboard():
    return ReplyKeyboardMarkup([["⬅️ До завдань"], ["⬅️ Головне меню"]], resize_keyboard=True)

def back_to_news_keyboard():
    return ReplyKeyboardMarkup([["⬅️ До новин"], ["⬅️ Головне меню"]], resize_keyboard=True)

def back_to_materials_keyboard():
    return ReplyKeyboardMarkup([["⬅️ До матеріалів"], ["⬅️ Головне меню"]], resize_keyboard=True)

def back_to_tournaments_keyboard():
    return ReplyKeyboardMarkup([["⬅️ До турнірів"], ["⬅️ Головне меню"]], resize_keyboard=True)

def students_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Додати учня",   "🗑 Видалити учня"],
        ["📄 Показати всіх", "⬅️ Головне меню"],
    ], resize_keyboard=True)

def schedule_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Додати заняття",  "📋 Показати розклад"],
        ["🗑 Видалити заняття", "⬅️ Головне меню"],
    ], resize_keyboard=True)

def homework_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Задати домашнє",   "📋 Показати завдання"],
        ["🗑 Видалити завдання", "⬅️ Головне меню"],
    ], resize_keyboard=True)

def news_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Додати новину",  "📋 Показати новини"],
        ["🗑 Видалити новину", "⬅️ Головне меню"],
    ], resize_keyboard=True)

def materials_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Додати матеріал",  "📋 Показати матеріали"],
        ["🗑 Видалити матеріал", "⬅️ Головне меню"],
    ], resize_keyboard=True)

def chat_keyboard():
    return ReplyKeyboardMarkup([
        ["📣 Розіслати всім батькам", "👥 Список батьків"],
        ["🔗 Прив'язати батька до учня", "⬅️ Головне меню"],
    ], resize_keyboard=True)

def attendance_keyboard():
    return ReplyKeyboardMarkup([
        ["📝 Відмітити відвідуваність", "📊 Статистика відвідуваності"],
        ["📋 Журнал за датою",           "⬅️ Головне меню"],
    ], resize_keyboard=True)

def tournaments_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Додати турнір",  "📋 Показати турніри"],
        ["🗑 Видалити турнір", "⬅️ Головне меню"],
    ], resize_keyboard=True)

# ─────────────────────────────────────────────
# КЛАВІАТУРИ — БАТЬКИ
# ─────────────────────────────────────────────
def parent_keyboard():
    return ReplyKeyboardMarkup([
        ["📅 Розклад занять",          "📚 Домашні завдання"],
        ["✅ Відвідуваність дитини",   "🏆 Турніри"],
    ], resize_keyboard=True)

# ─────────────────────────────────────────────
# КЛАВІАТУРИ — УЧНІ
# ─────────────────────────────────────────────
def student_keyboard():
    return ReplyKeyboardMarkup([
        ["📅 Розклад занять",    "📚 Домашні завдання"],
        ["✅ Моя відвідуваність","🎓 Навчальні матеріали"],
        ["🏆 Турніри"],
    ], resize_keyboard=True)

# ─────────────────────────────────────────────
# КЛАВІАТУРА — ВИБІР РОЛІ
# ─────────────────────────────────────────────
def role_keyboard():
    return ReplyKeyboardMarkup([
        ["♟️ Я учень"],
        ["👨‍👩‍👦 Я батько/мати"],
    ], resize_keyboard=True)

# ─────────────────────────────────────────────
# АВТОНАГАДУВАННЯ
# ─────────────────────────────────────────────
DAYS_UA_TO_NUM = {"Пн": 0, "Вт": 1, "Ср": 2, "Чт": 3, "Пт": 4, "Сб": 5, "Нд": 6}

async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    total_now_mins = now.hour * 60 + now.minute
    for lesson in db_get_schedule():
        day_num = DAYS_UA_TO_NUM.get(lesson.get("day"), -1)
        if day_num != now.weekday():
            continue
        try:
            h, m = map(int, lesson["time"].split(":"))
        except Exception:
            continue
        diff = (h * 60 + m) - total_now_mins
        if 115 <= diff <= 125:
            msg = (
                f"⏰ Нагадування!\n\nЧерез 2 години заняття з шахів!\n"
                f"👥 Група: {lesson.get('group','')}\n"
                f"🕐 Час: {lesson['time']}\n"
                f"📍 Місце: {lesson.get('place','')}\n\nНе забудьте! ♟️"
            )
            # Надсилаємо батькам
            for pid in db_get_parents():
                try:
                    await context.bot.send_message(chat_id=int(pid), text=msg)
                except Exception:
                    pass
            # Надсилаємо учням
            for uid in db_get_student_users():
                try:
                    await context.bot.send_message(chat_id=int(uid), text=msg)
                except Exception:
                    pass

# ─────────────────────────────────────────────
# /start — ВИБІР РОЛІ
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Тренер
    if user.id == TRAINER_ID:
        await update.message.reply_text(
            f"♟️ Вітаємо, тренере {user.first_name}!\n\nОберіть розділ 👇",
            reply_markup=main_keyboard()
        )
        return MAIN_MENU

    # Якщо вже зареєстрований учень
    if str(user.id) in db_get_student_users():
        await update.message.reply_text(
            f"♟️ Вітаємо, {user.first_name}!", reply_markup=student_keyboard()
        )
        return STUDENT_MENU

    # Якщо вже зареєстрований батько
    if str(user.id) in db_get_parents():
        await update.message.reply_text(
            f"👋 Вітаємо, {user.first_name}!", reply_markup=parent_keyboard()
        )
        return PARENT_MENU

    # Новий користувач — вибір ролі
    await update.message.reply_text(
        f"👋 Вітаємо, {user.first_name}!\n\n"
        "Будь ласка, оберіть хто ви:",
        reply_markup=role_keyboard()
    )
    return CHOOSE_ROLE

# ─────────────────────────────────────────────
# ВИБІР РОЛІ
# ─────────────────────────────────────────────
async def choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user

    if text == "♟️ Я учень":
        await update.message.reply_text(
            "📱 Введіть ваш номер телефону який вказав тренер при реєстрації:\n\n"
            "Формат: +380991234567",
            reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
        )
        return REGISTER_STUDENT

    elif text == "👨‍👩‍👦 Я батько/мати":
        db_upsert_parent(str(user.id), user.full_name, "")
        await update.message.reply_text(
            f"✅ Ви зареєстровані як батько/мати!\n\n"
            "Тренер прив'яже вас до вашої дитини.\n"
            "До того часу ви можете переглядати розклад та домашні завдання.",
            reply_markup=parent_keyboard()
        )
        return PARENT_MENU

    return CHOOSE_ROLE

# ─────────────────────────────────────────────
# РЕЄСТРАЦІЯ УЧНЯ ЗА ТЕЛЕФОНОМ
# ─────────────────────────────────────────────
async def register_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user

    if text == "⬅️ Назад":
        await update.message.reply_text("Оберіть роль:", reply_markup=role_keyboard())
        return CHOOSE_ROLE

    # Шукаємо учня за телефоном
    student = db_find_student_by_phone(text)
    if not student:
        await update.message.reply_text(
            "❌ Номер телефону не знайдено в базі.\n\n"
            "Перевірте номер або зверніться до тренера.\n\n"
            "Спробуйте ще раз:",
            reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
        )
        return REGISTER_STUDENT

    # Реєструємо учня
    db_upsert_student_user(str(user.id), user.full_name, student["name"])
    await update.message.reply_text(
        f"✅ Вітаємо, {student['name']}!\n\n"
        f"Ви успішно увійшли як учень ♟️\n"
        f"Тепер ви маєте доступ до розкладу, домашніх завдань та матеріалів.",
        reply_markup=student_keyboard()
    )
    return STUDENT_MENU

# ─────────────────────────────────────────────
# МЕНЮ УЧНЯ
# ─────────────────────────────────────────────
async def student_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_trainer(update):
        await update.message.reply_text("Меню тренера:", reply_markup=main_keyboard())
        return MAIN_MENU

    text = update.message.text
    uid = str(update.effective_user.id)
    student_users = db_get_student_users()
    student_name = student_users.get(uid, {}).get("student_name", "")

    if text == "📅 Розклад занять":
        schedule = db_get_schedule()
        if not schedule:
            await update.message.reply_text("📭 Розклад ще не додано.", reply_markup=student_keyboard())
        else:
            days_order = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
            sorted_s = sorted(schedule, key=lambda x: days_order.index(x["day"]) if x["day"] in days_order else 9)
            msg = "📅 Розклад занять:\n\n" + "".join(
                f"📌 {s['day']} {s['time']} — {s['group']} ({s['place']})\n" for s in sorted_s)
            await update.message.reply_text(msg, reply_markup=student_keyboard())

    elif text == "📚 Домашні завдання":
        homework = db_get_homework()
        if not homework:
            await update.message.reply_text("📭 Домашніх завдань немає.", reply_markup=student_keyboard())
        else:
            msg = "📚 Домашні завдання:\n\n"
            for i, h in enumerate(homework, 1):
                msg += f"{i}. [{h['group']}] {h['task']}\n   📅 До: {h['deadline']}\n\n"
            await update.message.reply_text(msg, reply_markup=student_keyboard())

    elif text == "✅ Моя відвідуваність":
        if not student_name:
            await update.message.reply_text("⚠️ Помилка. Зверніться до тренера.", reply_markup=student_keyboard())
            return STUDENT_MENU
        present_count = absent_count = 0
        for record in db_get_attendance().values():
            if student_name in record.get("present", []):
                present_count += 1
            elif student_name in record.get("absent", []):
                absent_count += 1
        total = present_count + absent_count
        percent = round(present_count / total * 100) if total > 0 else 0
        await update.message.reply_text(
            f"✅ Моя відвідуваність\n\n"
            f"👤 {student_name}\n"
            f"✔️ Був(ла): {present_count} занять\n"
            f"❌ Пропустив(ла): {absent_count} занять\n"
            f"📊 Відсоток: {percent}%",
            reply_markup=student_keyboard()
        )

    elif text == "🎓 Навчальні матеріали":
        materials = db_get_materials()
        if not materials:
            await update.message.reply_text("📭 Матеріалів ще немає.", reply_markup=student_keyboard())
        else:
            msg = "🎓 Навчальні матеріали:\n\n"
            for i, m in enumerate(materials, 1):
                msg += f"{i}. {m['title']}\n   🔗 {m['link']}\n   📁 {m['category']}\n\n"
            await update.message.reply_text(msg, reply_markup=student_keyboard())

    elif text == "🏆 Турніри":
        tournaments = db_get_tournaments()
        if not tournaments:
            await update.message.reply_text("📭 Турнірів ще немає.", reply_markup=student_keyboard())
        else:
            msg = "🏆 Заплановані турніри:\n\n"
            for i, t in enumerate(tournaments, 1):
                msg += f"{i}. {t['title']}\n   📅 {t['date']}\n   📍 {t['place']}\n   ℹ️ {t['info']}\n\n"
            await update.message.reply_text(msg, reply_markup=student_keyboard())

    return STUDENT_MENU

# ─────────────────────────────────────────────
# МЕНЮ БАТЬКІВ
# ─────────────────────────────────────────────
async def parent_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_trainer(update):
        await update.message.reply_text("Меню тренера:", reply_markup=main_keyboard())
        return MAIN_MENU

    text = update.message.text
    user_id = str(update.effective_user.id)

    if text == "📅 Розклад занять":
        schedule = db_get_schedule()
        if not schedule:
            await update.message.reply_text("📭 Розклад ще не додано.", reply_markup=parent_keyboard())
        else:
            days_order = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
            sorted_s = sorted(schedule, key=lambda x: days_order.index(x["day"]) if x["day"] in days_order else 9)
            msg = "📅 Розклад занять:\n\n" + "".join(
                f"📌 {s['day']} {s['time']} — {s['group']} ({s['place']})\n" for s in sorted_s)
            await update.message.reply_text(msg, reply_markup=parent_keyboard())

    elif text == "📚 Домашні завдання":
        homework = db_get_homework()
        if not homework:
            await update.message.reply_text("📭 Домашніх завдань немає.", reply_markup=parent_keyboard())
        else:
            msg = "📚 Актуальні домашні завдання:\n\n"
            for i, h in enumerate(homework, 1):
                msg += f"{i}. [{h['group']}] {h['task']}\n   📅 До: {h['deadline']}\n\n"
            await update.message.reply_text(msg, reply_markup=parent_keyboard())

    elif text == "✅ Відвідуваність дитини":
        parent_info = db_get_parents().get(user_id, {})
        student_name = parent_info.get("student", "")
        if not student_name:
            await update.message.reply_text(
                "⚠️ Вашу дитину ще не прив'язано.\nЗверніться до тренера.",
                reply_markup=parent_keyboard()
            )
            return PARENT_MENU
        present_count = absent_count = 0
        for record in db_get_attendance().values():
            if student_name in record.get("present", []):
                present_count += 1
            elif student_name in record.get("absent", []):
                absent_count += 1
        total = present_count + absent_count
        percent = round(present_count / total * 100) if total > 0 else 0
        await update.message.reply_text(
            f"✅ Відвідуваність: {student_name}\n\n"
            f"✔️ Був(ла): {present_count} занять\n"
            f"❌ Пропустив(ла): {absent_count} занять\n"
            f"📊 Відсоток: {percent}%",
            reply_markup=parent_keyboard()
        )

    elif text == "🏆 Турніри":
        tournaments = db_get_tournaments()
        if not tournaments:
            await update.message.reply_text("📭 Турнірів ще немає.", reply_markup=parent_keyboard())
        else:
            msg = "🏆 Заплановані турніри:\n\n"
            for i, t in enumerate(tournaments, 1):
                msg += f"{i}. {t['title']}\n   📅 {t['date']}\n   📍 {t['place']}\n   ℹ️ {t['info']}\n\n"
            await update.message.reply_text(msg, reply_markup=parent_keyboard())

    return PARENT_MENU

# ─────────────────────────────────────────────
# ГОЛОВНЕ МЕНЮ ТРЕНЕРА
# ─────────────────────────────────────────────
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update):
        # Перенаправляємо в правильне меню
        uid = str(update.effective_user.id)
        if uid in db_get_student_users():
            await update.message.reply_text("Ваше меню:", reply_markup=student_keyboard())
            return STUDENT_MENU
        await update.message.reply_text("Ваше меню:", reply_markup=parent_keyboard())
        return PARENT_MENU

    text = update.message.text
    if text == "📋 Список учнів":
        await update.message.reply_text("👦 Управління учнями:", reply_markup=students_keyboard())
        return STUDENTS_MENU
    elif text == "📅 Розклад занять":
        await update.message.reply_text("📅 Управління розкладом:", reply_markup=schedule_keyboard())
        return SCHEDULE_MENU
    elif text == "📚 Домашні завдання":
        await update.message.reply_text("📚 Домашні завдання:", reply_markup=homework_keyboard())
        return HOMEWORK_MENU
    elif text == "📢 Новини/Оголошення":
        await update.message.reply_text("📢 Новини школи:", reply_markup=news_keyboard())
        return NEWS_MENU
    elif text == "🎓 Матеріали":
        await update.message.reply_text("🎓 Навчальні матеріали:", reply_markup=materials_keyboard())
        return MATERIALS_MENU
    elif text == "💬 Чат з батьками":
        await update.message.reply_text(
            f"💬 Комунікація з батьками\n👥 Зареєстровано батьків: {len(db_get_parents())}",
            reply_markup=chat_keyboard()
        )
        return CHAT_MENU
    elif text == "✅ Відвідуваність":
        await update.message.reply_text("✅ Журнал відвідуваності:", reply_markup=attendance_keyboard())
        return ATTENDANCE_MENU
    elif text == "🏆 Турніри":
        await update.message.reply_text("🏆 Управління турнірами:", reply_markup=tournaments_keyboard())
        return TOURNAMENTS_MENU
    return MAIN_MENU

# ─────────────────────────────────────────────
# УЧНІ (ТРЕНЕР)
# ─────────────────────────────────────────────
async def students_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update): return ConversationHandler.END
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    elif text == "📄 Показати всіх":
        students = db_get_students()
        if not students:
            await update.message.reply_text("📭 Список учнів порожній.", reply_markup=students_keyboard())
        else:
            msg = "📋 Список учнів:\n\n"
            for i, s in enumerate(students, 1):
                msg += f"{i}. {s['name']} — {s['level']}\n   👨‍👩‍👦 Батьки: {s['parent_phone']} | 👤 Учень: {s.get('student_phone','—')}\n\n"
            await update.message.reply_text(msg, reply_markup=students_keyboard())
    elif text == "➕ Додати учня":
        await update.message.reply_text(
            "Введіть дані учня у форматі:\n"
            "<b>Ім'я Прізвище | рівень | телефон батьків | телефон учня</b>\n\n"
            "Приклад: Олег Іванов | початківець | +380991234567 | +380671234567\n\n"
            "💡 Телефон учня потрібен для його реєстрації в боті",
            parse_mode="HTML", reply_markup=back_to_students_keyboard()
        )
        return ADD_STUDENT
    elif text == "🗑 Видалити учня":
        students = db_get_students()
        if not students:
            await update.message.reply_text("Список порожній.", reply_markup=students_keyboard())
            return STUDENTS_MENU
        keyboard = [[InlineKeyboardButton(s["name"], callback_data=f"del_student_{i}")] for i, s in enumerate(students)]
        await update.message.reply_text("Оберіть учня для видалення:", reply_markup=InlineKeyboardMarkup(keyboard))
    return STUDENTS_MENU

async def add_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    if text == "⬅️ До списку учнів":
        await update.message.reply_text("👦 Управління учнями:", reply_markup=students_keyboard())
        return STUDENTS_MENU
    try:
        parts = [p.strip() for p in text.split("|")]
        logger.info(f"[ADD_STUDENT] parts: {parts}")
        if len(parts) < 3:
            raise ValueError(f"Потрібно мінімум 3 поля через |, отримано {len(parts)}")
        student = {
            "name": parts[0],
            "level": parts[1],
            "parent_phone": parts[2],
            "student_phone": parts[3] if len(parts) > 3 else "",
            "added": datetime.now().strftime("%d.%m.%Y")
        }
        db_add_student(student)
        logger.info(f"[ADD_STUDENT] ✅ Збережено: {student['name']}")
        msg = f"✅ Учня {student['name']} успішно додано!\n\n"
        if student["student_phone"]:
            msg += f"📱 Учень може увійти в бот використавши номер: {student['student_phone']}"
        else:
            msg += "⚠️ Телефон учня не вказано — він не зможе зареєструватись самостійно"
        await update.message.reply_text(msg, reply_markup=students_keyboard())
    except Exception as e:
        logger.error(f"[ADD_STUDENT] ❌ {e}")
        await update.message.reply_text(
            f"❌ Помилка: {e}\n\nФормат: <b>Ім'я | рівень | тел.батьків | тел.учня</b>",
            parse_mode="HTML", reply_markup=back_to_students_keyboard()
        )
    return STUDENTS_MENU

# ─────────────────────────────────────────────
# РОЗКЛАД
# ─────────────────────────────────────────────
async def schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update): return ConversationHandler.END
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    elif text == "📋 Показати розклад":
        schedule = db_get_schedule()
        if not schedule:
            await update.message.reply_text("📭 Розклад порожній.", reply_markup=schedule_keyboard())
        else:
            days_order = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
            sorted_s = sorted(schedule, key=lambda x: days_order.index(x["day"]) if x["day"] in days_order else 9)
            msg = "📅 Розклад занять:\n\n" + "".join(
                f"📌 {s['day']} {s['time']} — {s['group']} ({s['place']})\n" for s in sorted_s)
            await update.message.reply_text(msg, reply_markup=schedule_keyboard())
    elif text == "➕ Додати заняття":
        await update.message.reply_text(
            "Введіть заняття у форматі:\n<b>День | Час | Група | Місце</b>\n\nПриклад: Пн | 17:00 | Початківці | Зал №1",
            parse_mode="HTML", reply_markup=back_to_schedule_keyboard()
        )
        return ADD_SCHEDULE
    elif text == "🗑 Видалити заняття":
        schedule = db_get_schedule()
        if not schedule:
            await update.message.reply_text("Розклад порожній.", reply_markup=schedule_keyboard())
            return SCHEDULE_MENU
        keyboard = [[InlineKeyboardButton(f"{s['day']} {s['time']} — {s['group']}", callback_data=f"del_schedule_{i}")] for i, s in enumerate(schedule)]
        await update.message.reply_text("Оберіть заняття для видалення:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SCHEDULE_MENU

async def add_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    if text == "⬅️ До розкладу":
        await update.message.reply_text("📅 Управління розкладом:", reply_markup=schedule_keyboard())
        return SCHEDULE_MENU
    try:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 4:
            raise ValueError(f"Потрібно 4 поля через |, отримано {len(parts)}")
        entry = {"day": parts[0], "time": parts[1], "group": parts[2], "place": parts[3]}
        db_add_schedule(entry)
        await update.message.reply_text(
            f"✅ Заняття {entry['day']} {entry['time']} додано!\n🔔 Всі отримають нагадування за 2 год.",
            reply_markup=schedule_keyboard()
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Помилка: {e}\n\nФормат: <b>День | Час | Група | Місце</b>",
            parse_mode="HTML", reply_markup=back_to_schedule_keyboard()
        )
    return SCHEDULE_MENU

# ─────────────────────────────────────────────
# ДОМАШНІ ЗАВДАННЯ
# ─────────────────────────────────────────────
async def homework_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update): return ConversationHandler.END
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    elif text == "📋 Показати завдання":
        homework = db_get_homework()
        if not homework:
            await update.message.reply_text("📭 Завдань немає.", reply_markup=homework_keyboard())
        else:
            msg = "📚 Домашні завдання:\n\n"
            for i, h in enumerate(homework, 1):
                msg += f"{i}. [{h['group']}] {h['task']}\n   📅 До: {h['deadline']}\n\n"
            await update.message.reply_text(msg, reply_markup=homework_keyboard())
    elif text == "➕ Задати домашнє":
        await update.message.reply_text(
            "Введіть завдання у форматі:\n<b>Група | Завдання | Дедлайн</b>\n\nПриклад: Початківці | Вивчити e4 e5 | 15.03.2025",
            parse_mode="HTML", reply_markup=back_to_homework_keyboard()
        )
        return ADD_HOMEWORK
    elif text == "🗑 Видалити завдання":
        homework = db_get_homework()
        if not homework:
            await update.message.reply_text("Завдань немає.", reply_markup=homework_keyboard())
            return HOMEWORK_MENU
        keyboard = [[InlineKeyboardButton(f"[{h['group']}] {h['task'][:30]}...", callback_data=f"del_hw_{i}")] for i, h in enumerate(homework)]
        await update.message.reply_text("Оберіть завдання для видалення:", reply_markup=InlineKeyboardMarkup(keyboard))
    return HOMEWORK_MENU

async def add_homework(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    if text == "⬅️ До завдань":
        await update.message.reply_text("📚 Домашні завдання:", reply_markup=homework_keyboard())
        return HOMEWORK_MENU
    try:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 3:
            raise ValueError(f"Потрібно 3 поля через |, отримано {len(parts)}")
        hw = {"group": parts[0], "task": parts[1], "deadline": parts[2], "created": datetime.now().strftime("%d.%m.%Y")}
        db_add_homework(hw)
        sent = 0
        # Надсилаємо батькам
        for pid in db_get_parents():
            try:
                await context.bot.send_message(chat_id=int(pid),
                    text=f"📚 Нове домашнє завдання!\n\n👥 Група: {hw['group']}\n📝 {hw['task']}\n📅 До: {hw['deadline']}")
                sent += 1
            except Exception:
                pass
        # Надсилаємо учням
        for uid in db_get_student_users():
            try:
                await context.bot.send_message(chat_id=int(uid),
                    text=f"📚 Нове домашнє завдання!\n\n👥 Група: {hw['group']}\n📝 {hw['task']}\n📅 До: {hw['deadline']}")
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(f"✅ Завдання додано! Надіслано {sent} повідомлень.", reply_markup=homework_keyboard())
    except Exception as e:
        await update.message.reply_text(
            f"❌ Помилка: {e}\n\nФормат: <b>Група | Завдання | Дедлайн</b>",
            parse_mode="HTML", reply_markup=back_to_homework_keyboard()
        )
    return HOMEWORK_MENU

# ─────────────────────────────────────────────
# НОВИНИ
# ─────────────────────────────────────────────
async def news_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update): return ConversationHandler.END
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    elif text == "📋 Показати новини":
        news = db_get_news()
        if not news:
            await update.message.reply_text("📭 Новин немає.", reply_markup=news_keyboard())
        else:
            msg = "📢 Новини:\n\n"
            for i, n in enumerate(news, 1):
                msg += f"{i}. {n['title']}\n   {n['text']}\n   📅 {n['date']}\n\n"
            await update.message.reply_text(msg, reply_markup=news_keyboard())
    elif text == "➕ Додати новину":
        await update.message.reply_text(
            "Введіть новину у форматі:\n<b>Заголовок | Текст</b>",
            parse_mode="HTML", reply_markup=back_to_news_keyboard()
        )
        return ADD_NEWS
    elif text == "🗑 Видалити новину":
        news = db_get_news()
        if not news:
            await update.message.reply_text("Новин немає.", reply_markup=news_keyboard())
            return NEWS_MENU
        keyboard = [[InlineKeyboardButton(n["title"], callback_data=f"del_news_{i}")] for i, n in enumerate(news)]
        await update.message.reply_text("Оберіть новину для видалення:", reply_markup=InlineKeyboardMarkup(keyboard))
    return NEWS_MENU

async def add_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    if text == "⬅️ До новин":
        await update.message.reply_text("📢 Новини школи:", reply_markup=news_keyboard())
        return NEWS_MENU
    try:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 2:
            raise ValueError(f"Потрібно 2 поля через |")
        news_item = {"title": parts[0], "text": parts[1], "date": datetime.now().strftime("%d.%m.%Y")}
        db_add_news(news_item)
        sent = 0
        for pid in db_get_parents():
            try:
                await context.bot.send_message(chat_id=int(pid), text=f"📢 {news_item['title']}\n\n{news_item['text']}")
                sent += 1
            except Exception:
                pass
        for uid in db_get_student_users():
            try:
                await context.bot.send_message(chat_id=int(uid), text=f"📢 {news_item['title']}\n\n{news_item['text']}")
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(f"✅ Новину опубліковано! Надіслано {sent} повідомлень.", reply_markup=news_keyboard())
    except Exception as e:
        await update.message.reply_text(
            f"❌ Помилка: {e}\n\nФормат: <b>Заголовок | Текст</b>",
            parse_mode="HTML", reply_markup=back_to_news_keyboard()
        )
    return NEWS_MENU

# ─────────────────────────────────────────────
# МАТЕРІАЛИ
# ─────────────────────────────────────────────
async def materials_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update): return ConversationHandler.END
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    elif text == "📋 Показати матеріали":
        materials = db_get_materials()
        if not materials:
            await update.message.reply_text("📭 Матеріалів немає.", reply_markup=materials_keyboard())
        else:
            msg = "🎓 Навчальні матеріали:\n\n"
            for i, m in enumerate(materials, 1):
                msg += f"{i}. {m['title']}\n   🔗 {m['link']}\n   📁 {m['category']}\n\n"
            await update.message.reply_text(msg, reply_markup=materials_keyboard())
    elif text == "➕ Додати матеріал":
        await update.message.reply_text(
            "Введіть матеріал у форматі:\n<b>Назва | Посилання | Категорія</b>\n\nПриклад: Збірник задач | https://example.com | Задачники",
            parse_mode="HTML", reply_markup=back_to_materials_keyboard()
        )
        return ADD_MATERIAL
    elif text == "🗑 Видалити матеріал":
        materials = db_get_materials()
        if not materials:
            await update.message.reply_text("Матеріалів немає.", reply_markup=materials_keyboard())
            return MATERIALS_MENU
        keyboard = [[InlineKeyboardButton(m["title"], callback_data=f"del_material_{i}")] for i, m in enumerate(materials)]
        await update.message.reply_text("Оберіть матеріал для видалення:", reply_markup=InlineKeyboardMarkup(keyboard))
    return MATERIALS_MENU

async def add_material(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    if text == "⬅️ До матеріалів":
        await update.message.reply_text("🎓 Навчальні матеріали:", reply_markup=materials_keyboard())
        return MATERIALS_MENU
    try:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 3:
            raise ValueError(f"Потрібно 3 поля через |")
        mat = {"title": parts[0], "link": parts[1], "category": parts[2], "date": datetime.now().strftime("%d.%m.%Y")}
        db_add_material(mat)
        await update.message.reply_text(f"✅ Матеріал '{mat['title']}' додано!", reply_markup=materials_keyboard())
    except Exception as e:
        await update.message.reply_text(
            f"❌ Помилка: {e}\n\nФормат: <b>Назва | Посилання | Категорія</b>",
            parse_mode="HTML", reply_markup=back_to_materials_keyboard()
        )
    return MATERIALS_MENU

# ─────────────────────────────────────────────
# ТУРНІРИ
# ─────────────────────────────────────────────
async def tournaments_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update): return ConversationHandler.END
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    elif text == "📋 Показати турніри":
        tournaments = db_get_tournaments()
        if not tournaments:
            await update.message.reply_text("📭 Турнірів немає.", reply_markup=tournaments_keyboard())
        else:
            msg = "🏆 Заплановані турніри:\n\n"
            for i, t in enumerate(tournaments, 1):
                msg += f"{i}. {t['title']}\n   📅 {t['date']}\n   📍 {t['place']}\n   ℹ️ {t['info']}\n\n"
            await update.message.reply_text(msg, reply_markup=tournaments_keyboard())
    elif text == "➕ Додати турнір":
        await update.message.reply_text(
            "Введіть турнір у форматі:\n<b>Назва | Дата | Місце | Інфо</b>\n\n"
            "Приклад: Кубок міста | 15.04.2025 | ДЮСШ №3 | Реєстрація до 10.04",
            parse_mode="HTML", reply_markup=back_to_tournaments_keyboard()
        )
        return ADD_TOURNAMENT
    elif text == "🗑 Видалити турнір":
        tournaments = db_get_tournaments()
        if not tournaments:
            await update.message.reply_text("Турнірів немає.", reply_markup=tournaments_keyboard())
            return TOURNAMENTS_MENU
        keyboard = [[InlineKeyboardButton(t["title"], callback_data=f"del_tournament_{i}")] for i, t in enumerate(tournaments)]
        await update.message.reply_text("Оберіть турнір для видалення:", reply_markup=InlineKeyboardMarkup(keyboard))
    return TOURNAMENTS_MENU

async def add_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    if text == "⬅️ До турнірів":
        await update.message.reply_text("🏆 Управління турнірами:", reply_markup=tournaments_keyboard())
        return TOURNAMENTS_MENU
    try:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 4:
            raise ValueError(f"Потрібно 4 поля через |")
        t = {"title": parts[0], "date": parts[1], "place": parts[2], "info": parts[3]}
        db_add_tournament(t)
        sent = 0
        notify_text = f"🏆 Новий турнір!\n\n{t['title']}\n📅 {t['date']}\n📍 {t['place']}\nℹ️ {t['info']}"
        for pid in db_get_parents():
            try:
                await context.bot.send_message(chat_id=int(pid), text=notify_text)
                sent += 1
            except Exception:
                pass
        for uid in db_get_student_users():
            try:
                await context.bot.send_message(chat_id=int(uid), text=notify_text)
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(f"✅ Турнір додано! Надіслано {sent} повідомлень.", reply_markup=tournaments_keyboard())
    except Exception as e:
        await update.message.reply_text(
            f"❌ Помилка: {e}\n\nФормат: <b>Назва | Дата | Місце | Інфо</b>",
            parse_mode="HTML", reply_markup=back_to_tournaments_keyboard()
        )
    return TOURNAMENTS_MENU

# ─────────────────────────────────────────────
# ЧАТ З БАТЬКАМИ
# ─────────────────────────────────────────────
async def chat_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update): return ConversationHandler.END
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    elif text == "👥 Список батьків":
        parents = db_get_parents()
        if not parents:
            await update.message.reply_text("📭 Жоден батько ще не зареєструвався.", reply_markup=chat_keyboard())
        else:
            msg = "👥 Зареєстровані батьки:\n\n"
            for pid, info in parents.items():
                student_link = info.get('student', 'не прив\'язано')
                msg += f"• {info['name']} → {student_link} (ID: {pid})\n"
            await update.message.reply_text(msg, reply_markup=chat_keyboard())
    elif text == "🔗 Прив'язати батька до учня":
        parents = db_get_parents()
        students = db_get_students()
        if not parents:
            await update.message.reply_text("📭 Жоден батько не зареєструвався.", reply_markup=chat_keyboard())
            return CHAT_MENU
        if not students:
            await update.message.reply_text("📭 Спочатку додайте учнів.", reply_markup=chat_keyboard())
            return CHAT_MENU
        keyboard = [[InlineKeyboardButton(f"{info['name']} → {info.get('student','—')}", callback_data=f"link_parent_{pid}")] for pid, info in parents.items()]
        await update.message.reply_text("Оберіть батька для прив'язки:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif text == "📣 Розіслати всім батькам":
        await update.message.reply_text("Введіть повідомлення для розсилки:", reply_markup=back_keyboard())
        return BROADCAST_MSG
    return CHAT_MENU

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    sent = failed = 0
    for pid in db_get_parents():
        try:
            await context.bot.send_message(chat_id=int(pid), text=f"📣 Повідомлення від тренера:\n\n{text}")
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"✅ Розсилку завершено!\n📨 Надіслано: {sent}\n❌ Не вдалося: {failed}",
        reply_markup=chat_keyboard()
    )
    return CHAT_MENU

# ─────────────────────────────────────────────
# ВІДВІДУВАНІСТЬ
# ─────────────────────────────────────────────
async def attendance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update): return ConversationHandler.END
    text = update.message.text
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    elif text == "📝 Відмітити відвідуваність":
        students = db_get_students()
        if not students:
            await update.message.reply_text("📭 Спочатку додайте учнів.", reply_markup=attendance_keyboard())
            return ATTENDANCE_MENU
        today = datetime.now().strftime("%d.%m.%Y")
        keyboard = [[
            InlineKeyboardButton(f"✅ {s['name']}", callback_data=f"att_present_{i}"),
            InlineKeyboardButton(f"❌ {s['name']}", callback_data=f"att_absent_{i}")
        ] for i, s in enumerate(students)]
        keyboard.append([InlineKeyboardButton("💾 Зберегти", callback_data="att_save")])
        context.user_data["attendance_today"] = {"date": today, "present": [], "absent": []}
        await update.message.reply_text(
            f"📝 Відвідуваність на {today}\n✅ = присутній | ❌ = відсутній",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif text == "📊 Статистика відвідуваності":
        attendance = db_get_attendance()
        if not attendance:
            await update.message.reply_text("📭 Даних ще немає.", reply_markup=attendance_keyboard())
            return ATTENDANCE_MENU
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
        await update.message.reply_text(msg, reply_markup=attendance_keyboard())
    elif text == "📋 Журнал за датою":
        attendance = db_get_attendance()
        if not attendance:
            await update.message.reply_text("📭 Даних ще немає.", reply_markup=attendance_keyboard())
            return ATTENDANCE_MENU
        msg = "📋 Журнал відвідуваності:\n\n"
        for key, record in sorted(attendance.items(), reverse=True)[:10]:
            present = ", ".join(record.get("present", [])) or "—"
            absent  = ", ".join(record.get("absent",  [])) or "—"
            msg += f"📅 {record.get('date', key)}\n✅ {present}\n❌ {absent}\n\n"
        await update.message.reply_text(msg, reply_markup=attendance_keyboard())
    return ATTENDANCE_MENU

# ─────────────────────────────────────────────
# CALLBACK HANDLER
# ─────────────────────────────────────────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("link_parent_"):
        pid = data.replace("link_parent_", "")
        context.user_data["linking_parent_id"] = pid
        students = db_get_students()
        parent_name = db_get_parents().get(pid, {}).get("name", "?")
        keyboard = [[InlineKeyboardButton(s["name"], callback_data=f"link_student_{i}")] for i, s in enumerate(students)]
        await query.edit_message_text(
            f"👤 Батько: <b>{parent_name}</b>\n\nОберіть учня:",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("link_student_"):
        idx = int(data.split("_")[-1])
        pid = context.user_data.get("linking_parent_id")
        if not pid:
            await query.edit_message_text("❌ Помилка. Спробуйте знову.")
            return
        students = db_get_students()
        student_name = students[idx]["name"]
        db_link_parent_to_student(pid, student_name)
        parent_name = db_get_parents().get(pid, {}).get("name", "?")
        try:
            await context.bot.send_message(chat_id=int(pid),
                text=f"✅ Тренер прив'язав вас до учня: <b>{student_name}</b>", parse_mode="HTML")
        except Exception:
            pass
        await query.edit_message_text(f"✅ Готово!\n\n👨‍👩‍👦 {parent_name} → 🎓 {student_name}")

    elif data.startswith("att_present_"):
        idx = int(data.split("_")[-1])
        name = db_get_students()[idx]["name"]
        att = context.user_data.get("attendance_today", {"date": "", "present": [], "absent": []})
        if name not in att["present"]: att["present"].append(name)
        if name in att["absent"]: att["absent"].remove(name)
        context.user_data["attendance_today"] = att
        await query.answer(f"✅ {name} — присутній(я)")

    elif data.startswith("att_absent_"):
        idx = int(data.split("_")[-1])
        name = db_get_students()[idx]["name"]
        att = context.user_data.get("attendance_today", {"date": "", "present": [], "absent": []})
        if name not in att["absent"]: att["absent"].append(name)
        if name in att["present"]: att["present"].remove(name)
        context.user_data["attendance_today"] = att
        await query.answer(f"❌ {name} — відсутній(я)")

    elif data == "att_save":
        att = context.user_data.get("attendance_today", {})
        date = att.get("date", datetime.now().strftime("%d.%m.%Y"))
        db_save_attendance(date.replace(".", "-"), att)
        # Сповіщаємо батьків відсутніх
        for pid, info in db_get_parents().items():
            sname = info.get("student", "")
            if sname and sname in att.get("absent", []):
                try:
                    await context.bot.send_message(chat_id=int(pid),
                        text=f"⚠️ {sname} сьогодні ({date}) не з'явився(лась) на занятті.")
                except Exception:
                    pass
        # Сповіщаємо учнів про свою відсутність
        for uid, info in db_get_student_users().items():
            sname = info.get("student_name", "")
            if sname and sname in att.get("absent", []):
                try:
                    await context.bot.send_message(chat_id=int(uid),
                        text=f"⚠️ Тренер відмітив тебе відсутнім сьогодні ({date}).")
                except Exception:
                    pass
        present = ", ".join(att.get("present", [])) or "—"
        absent  = ", ".join(att.get("absent",  [])) or "—"
        await query.edit_message_text(f"✅ Відвідуваність збережено!\n\n📅 {date}\n✅ {present}\n❌ {absent}")

    elif data.startswith("del_student_"):
        idx = int(data.split("_")[-1])
        students = db_get_students()
        if 0 <= idx < len(students):
            name = students[idx]["name"]
            db_delete_student(idx)
            await query.edit_message_text(f"🗑 Учня {name} видалено.")
        else:
            await query.edit_message_text("❌ Не знайдено.")

    elif data.startswith("del_schedule_"):
        idx = int(data.split("_")[-1])
        schedule = db_get_schedule()
        if 0 <= idx < len(schedule):
            s = schedule[idx]
            db_delete_schedule(idx)
            await query.edit_message_text(f"🗑 Заняття {s['day']} {s['time']} видалено.")
        else:
            await query.edit_message_text("❌ Не знайдено.")

    elif data.startswith("del_hw_"):
        idx = int(data.split("_")[-1])
        homework = db_get_homework()
        if 0 <= idx < len(homework):
            db_delete_homework(idx)
            await query.edit_message_text("🗑 Завдання видалено.")
        else:
            await query.edit_message_text("❌ Не знайдено.")

    elif data.startswith("del_news_"):
        idx = int(data.split("_")[-1])
        news = db_get_news()
        if 0 <= idx < len(news):
            n = news[idx]
            db_delete_news(idx)
            await query.edit_message_text(f"🗑 Новину '{n['title']}' видалено.")
        else:
            await query.edit_message_text("❌ Не знайдено.")

    elif data.startswith("del_material_"):
        idx = int(data.split("_")[-1])
        materials = db_get_materials()
        if 0 <= idx < len(materials):
            m = materials[idx]
            db_delete_material(idx)
            await query.edit_message_text(f"🗑 Матеріал '{m['title']}' видалено.")
        else:
            await query.edit_message_text("❌ Не знайдено.")

    elif data.startswith("del_tournament_"):
        idx = int(data.split("_")[-1])
        tournaments = db_get_tournaments()
        if 0 <= idx < len(tournaments):
            t = tournaments[idx]
            db_delete_tournament(idx)
            await query.edit_message_text(f"🗑 Турнір '{t['title']}' видалено.")
        else:
            await query.edit_message_text("❌ Не знайдено.")

# ─────────────────────────────────────────────
# ЗАПУСК
# ─────────────────────────────────────────────
def main():
    try:
        init_mongo()
    except Exception as e:
        print(f"❌ КРИТИЧНА ПОМИЛКА MongoDB: {e}")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_ROLE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_role)],
            REGISTER_STUDENT:[MessageHandler(filters.TEXT & ~filters.COMMAND, register_student)],
            MAIN_MENU:       [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler)],
            PARENT_MENU:     [MessageHandler(filters.TEXT & ~filters.COMMAND, parent_menu_handler)],
            STUDENT_MENU:    [MessageHandler(filters.TEXT & ~filters.COMMAND, student_menu_handler)],
            STUDENTS_MENU:   [MessageHandler(filters.TEXT & ~filters.COMMAND, students_menu)],
            ADD_STUDENT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student)],
            SCHEDULE_MENU:   [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_menu)],
            ADD_SCHEDULE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_schedule)],
            HOMEWORK_MENU:   [MessageHandler(filters.TEXT & ~filters.COMMAND, homework_menu)],
            ADD_HOMEWORK:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_homework)],
            NEWS_MENU:       [MessageHandler(filters.TEXT & ~filters.COMMAND, news_menu)],
            ADD_NEWS:        [MessageHandler(filters.TEXT & ~filters.COMMAND, add_news)],
            MATERIALS_MENU:  [MessageHandler(filters.TEXT & ~filters.COMMAND, materials_menu)],
            ADD_MATERIAL:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_material)],
            CHAT_MENU:       [MessageHandler(filters.TEXT & ~filters.COMMAND, chat_menu)],
            BROADCAST_MSG:   [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message)],
            LINK_PARENT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, chat_menu)],
            ATTENDANCE_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, attendance_menu)],
            TOURNAMENTS_MENU:[MessageHandler(filters.TEXT & ~filters.COMMAND, tournaments_menu)],
            ADD_TOURNAMENT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tournament)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.job_queue.run_repeating(send_reminders, interval=3600, first=10)

    print("♟️ Chess Trainer Bot v4.0 запущено!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
