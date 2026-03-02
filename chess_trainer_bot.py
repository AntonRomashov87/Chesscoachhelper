"""
♟️ Chess Trainer Bot v3.1 — Telegram-бот для тренера шахової школи
MongoDB Atlas для постійного зберігання даних
ВИПРАВЛЕНО: insert_one не модифікує оригінал, delete_one за конкретними полями
Залежності: pip install python-telegram-bot[job-queue]==20.7 pymongo[srv]==4.7.0
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
BOT_TOKEN   = os.environ.get("BOT_TOKEN")
TRAINER_ID  = int(os.environ.get("TRAINER_ID"))
MONGODB_URI = os.environ.get("MONGODB_URI")

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
    CHAT_MENU, BROADCAST_MSG, ATTENDANCE_MENU, MARK_ATTENDANCE,
    PARENT_MENU, LINK_PARENT
) = range(17)

# ─────────────────────────────────────────────
# MONGODB — підключення та helpers
# ─────────────────────────────────────────────
mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
mdb = mongo_client["chess_trainer"]

# ── Перевірка підключення при старті ──
def check_mongo_connection():
    try:
        mongo_client.admin.command('ping')
        logger.info("✅ MongoDB підключено успішно!")
        return True
    except Exception as e:
        logger.error(f"❌ MongoDB помилка підключення: {e}")
        return False

def col(name):
    return mdb[name]

# ─────────────────────────────────────────────
# ВИПРАВЛЕННЯ: використовуємо deepcopy перед insert_one
# щоб MongoDB не модифікувала оригінальний словник (не додавала _id)
# ─────────────────────────────────────────────

# ── Учні ──
def db_get_students() -> list:
    return list(col("students").find({}, {"_id": 0}))

def db_add_student(student: dict):
    col("students").insert_one(deepcopy(student))  # ✅ deepcopy захищає від мутації

def db_delete_student(idx: int):
    items = db_get_students()
    if 0 <= idx < len(items):
        col("students").delete_one({"name": items[idx]["name"]})

# ── Розклад ──
def db_get_schedule() -> list:
    return list(col("schedule").find({}, {"_id": 0}))

def db_add_schedule(entry: dict):
    col("schedule").insert_one(deepcopy(entry))

def db_delete_schedule(idx: int):
    items = db_get_schedule()
    if 0 <= idx < len(items):
        item = items[idx]
        # ✅ Видаляємо за конкретними полями, не за всім словником
        col("schedule").delete_one({
            "day": item["day"],
            "time": item["time"],
            "group": item["group"]
        })

# ── Домашні завдання ──
def db_get_homework() -> list:
    return list(col("homework").find({}, {"_id": 0}))

def db_add_homework(hw: dict):
    col("homework").insert_one(deepcopy(hw))

def db_delete_homework(idx: int):
    items = db_get_homework()
    if 0 <= idx < len(items):
        item = items[idx]
        col("homework").delete_one({
            "group": item["group"],
            "task": item["task"],
            "deadline": item["deadline"]
        })

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
# КЛАВІАТУРИ — ТРЕНЕР
# ─────────────────────────────────────────────
def main_keyboard():
    return ReplyKeyboardMarkup([
        ["📋 Список учнів",    "📅 Розклад занять"],
        ["📚 Домашні завдання","📢 Новини/Оголошення"],
        ["🎓 Матеріали",       "💬 Чат з батьками"],
        ["✅ Відвідуваність"],
    ], resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup([["⬅️ Головне меню"]], resize_keyboard=True)

def back_to_schedule_keyboard():
    return ReplyKeyboardMarkup([
        ["⬅️ До розкладу"],
        ["⬅️ Головне меню"]
    ], resize_keyboard=True)

def back_to_students_keyboard():
    return ReplyKeyboardMarkup([
        ["⬅️ До списку учнів"],
        ["⬅️ Головне меню"]
    ], resize_keyboard=True)

def back_to_homework_keyboard():
    return ReplyKeyboardMarkup([
        ["⬅️ До завдань"],
        ["⬅️ Головне меню"]
    ], resize_keyboard=True)

def back_to_news_keyboard():
    return ReplyKeyboardMarkup([
        ["⬅️ До новин"],
        ["⬅️ Головне меню"]
    ], resize_keyboard=True)

def back_to_materials_keyboard():
    return ReplyKeyboardMarkup([
        ["⬅️ До матеріалів"],
        ["⬅️ Головне меню"]
    ], resize_keyboard=True)

def students_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Додати учня",  "🗑 Видалити учня"],
        ["📄 Показати всіх","⬅️ Головне меню"],
    ], resize_keyboard=True)

def schedule_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Додати заняття","📋 Показати розклад"],
        ["🗑 Видалити заняття","⬅️ Головне меню"],
    ], resize_keyboard=True)

def homework_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Задати домашнє","📋 Показати завдання"],
        ["🗑 Видалити завдання","⬅️ Головне меню"],
    ], resize_keyboard=True)

def news_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Додати новину","📋 Показати новини"],
        ["🗑 Видалити новину","⬅️ Головне меню"],
    ], resize_keyboard=True)

def materials_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ Додати матеріал","📋 Показати матеріали"],
        ["🗑 Видалити матеріал","⬅️ Головне меню"],
    ], resize_keyboard=True)

def chat_keyboard():
    return ReplyKeyboardMarkup([
        ["📣 Розіслати всім батькам","👥 Список батьків"],
        ["🔗 Прив'язати батька до учня","⬅️ Головне меню"],
    ], resize_keyboard=True)

def attendance_keyboard():
    return ReplyKeyboardMarkup([
        ["📝 Відмітити відвідуваність","📊 Статистика відвідуваності"],
        ["📋 Журнал за датою","⬅️ Головне меню"],
    ], resize_keyboard=True)

# ─────────────────────────────────────────────
# КЛАВІАТУРА — БАТЬКИ
# ─────────────────────────────────────────────
def parent_keyboard():
    return ReplyKeyboardMarkup([
        ["📅 Розклад занять"],
        ["📚 Домашні завдання"],
        ["✅ Відвідуваність моєї дитини"],
    ], resize_keyboard=True)

# ─────────────────────────────────────────────
# ПЕРЕВІРКА
# ─────────────────────────────────────────────
def is_trainer(update: Update) -> bool:
    return update.effective_user.id == TRAINER_ID

def is_parent(update: Update) -> bool:
    return str(update.effective_user.id) in db_get_parents()

# ─────────────────────────────────────────────
# АВТОНАГАДУВАННЯ
# ─────────────────────────────────────────────
DAYS_UA_TO_NUM = {"Пн": 0, "Вт": 1, "Ср": 2, "Чт": 3, "Пт": 4, "Сб": 5, "Нд": 6}

async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Запускається щогодини — надсилає нагадування за 2 години до заняття."""
    now = datetime.now()
    today_weekday = now.weekday()
    current_hour = now.hour
    current_minute = now.minute

    for lesson in db_get_schedule():
        day_num = DAYS_UA_TO_NUM.get(lesson.get("day"), -1)
        if day_num != today_weekday:
            continue
        try:
            lesson_hour, lesson_minute = map(int, lesson["time"].split(":"))
        except Exception:
            continue

        total_lesson_mins = lesson_hour * 60 + lesson_minute
        total_now_mins = current_hour * 60 + current_minute
        diff = total_lesson_mins - total_now_mins

        if 115 <= diff <= 125:
            group = lesson.get("group", "")
            place = lesson.get("place", "")
            msg = (
                f"⏰ Нагадування!\n\n"
                f"Через 2 години заняття з шахів!\n"
                f"👥 Група: {group}\n"
                f"🕐 Час: {lesson['time']}\n"
                f"📍 Місце: {place}\n\n"
                f"Не забудьте! ♟️"
            )
            sent = 0
            for pid in db_get_parents():
                try:
                    await context.bot.send_message(chat_id=int(pid), text=msg)
                    sent += 1
                except Exception:
                    pass
            if sent > 0:
                logger.info(f"Нагадування надіслано {sent} батькам для групи {group}")

# ─────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id == TRAINER_ID:
        await update.message.reply_text(
            f"♟️ Вітаємо, тренере {user.first_name}!\n\nОберіть розділ у меню нижче 👇",
            reply_markup=main_keyboard()
        )
        return MAIN_MENU

    parents = db_get_parents()
    if str(user.id) not in parents:
        db_upsert_parent(str(user.id), user.full_name, "")

    await update.message.reply_text(
        f"👋 Вітаємо, {user.first_name}!\n\n"
        "Ви зареєстровані як батько/мати учня.\n"
        "Тут ви можете переглядати розклад, домашні завдання та відвідуваність вашої дитини.\n\n"
        "Оберіть що вас цікавить 👇",
        reply_markup=parent_keyboard()
    )
    return PARENT_MENU

# ─────────────────────────────────────────────
# МЕНЮ ДЛЯ БАТЬКІВ
# ─────────────────────────────────────────────
async def parent_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_trainer(update):
        await update.message.reply_text("Головне меню тренера:", reply_markup=main_keyboard())
        return MAIN_MENU

    text = update.message.text
    user_id = str(update.effective_user.id)

    if text == "📅 Розклад занять":
        schedule = db_get_schedule()
        if not schedule:
            await update.message.reply_text("📭 Розклад ще не додано.", reply_markup=parent_keyboard())
        else:
            days_order = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
            sorted_schedule = sorted(schedule,
                key=lambda x: days_order.index(x["day"]) if x["day"] in days_order else 9)
            msg = "📅 Розклад занять:\n\n"
            for s in sorted_schedule:
                msg += f"📌 {s['day']} {s['time']} — {s['group']} ({s['place']})\n"
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

    elif text == "✅ Відвідуваність моєї дитини":
        parents = db_get_parents()
        parent_info = parents.get(user_id, {})
        student_name = parent_info.get("student", "")

        if not student_name:
            await update.message.reply_text(
                "⚠️ Ваша дитина ще не прив'язана до акаунту.\n"
                "Зверніться до тренера щоб він прив'язав вас до учня.",
                reply_markup=parent_keyboard()
            )
            return PARENT_MENU

        present_count = 0
        absent_count = 0
        for key, record in db_get_attendance().items():
            if student_name in record.get("present", []):
                present_count += 1
            elif student_name in record.get("absent", []):
                absent_count += 1

        total = present_count + absent_count
        percent = round(present_count / total * 100) if total > 0 else 0

        msg = (
            f"✅ Відвідуваність: {student_name}\n\n"
            f"✔️ Був(ла): {present_count} занять\n"
            f"❌ Пропустив(ла): {absent_count} занять\n"
            f"📊 Відсоток: {percent}%"
        )
        await update.message.reply_text(msg, reply_markup=parent_keyboard())

    return PARENT_MENU

# ─────────────────────────────────────────────
# ГОЛОВНЕ МЕНЮ ТРЕНЕРА
# ─────────────────────────────────────────────
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update):
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
        parents_count = len(db_get_parents())
        await update.message.reply_text(
            f"💬 Комунікація з батьками\n👥 Зареєстровано батьків: {parents_count}",
            reply_markup=chat_keyboard()
        )
        return CHAT_MENU
    elif text == "✅ Відвідуваність":
        await update.message.reply_text("✅ Журнал відвідуваності:", reply_markup=attendance_keyboard())
        return ATTENDANCE_MENU

    return MAIN_MENU

# ─────────────────────────────────────────────
# УЧНІ
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
                msg += f"{i}. {s['name']} — {s['level']} | {s['phone']}\n"
            await update.message.reply_text(msg, reply_markup=students_keyboard())
        return STUDENTS_MENU
    elif text == "➕ Додати учня":
        await update.message.reply_text(
            "Введіть дані учня у форматі:\n"
            "<b>Ім'я Прізвище | рівень | телефон батьків</b>\n\n"
            "Приклад: Олег Іванов | початківець | +380991234567",
            parse_mode="HTML", reply_markup=back_to_students_keyboard()
        )
        return ADD_STUDENT
    elif text == "🗑 Видалити учня":
        students = db_get_students()
        if not students:
            await update.message.reply_text("Список порожній.", reply_markup=students_keyboard())
            return STUDENTS_MENU
        keyboard = [[InlineKeyboardButton(s["name"], callback_data=f"del_student_{i}")]
                    for i, s in enumerate(students)]
        await update.message.reply_text("Оберіть учня для видалення:",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return STUDENTS_MENU
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
        parts = [p.strip() for p in update.message.text.split("|")]
        logger.info(f"[ADD_STUDENT] Розібрано: {parts}")
        if len(parts) < 3:
            raise ValueError(f"Недостатньо полів — отримано {len(parts)}: {parts}")
        student = {
            "name": parts[0],
            "level": parts[1],
            "phone": parts[2],
            "added": datetime.now().strftime("%d.%m.%Y")
        }
        db_add_student(student)
        logger.info(f"[ADD_STUDENT] ✅ Учня {student['name']} збережено!")
        await update.message.reply_text(
            f"✅ Учня {student['name']} успішно додано!",
            reply_markup=students_keyboard()
        )
    except Exception as e:
        logger.error(f"[ADD_STUDENT] ❌ Помилка: {e}")
        await update.message.reply_text(
            f"❌ Помилка: {e}\n\nФормат: <b>Ім'я | рівень | телефон</b>",
            parse_mode="HTML",
            reply_markup=back_to_students_keyboard()
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
            sorted_schedule = sorted(schedule,
                key=lambda x: days_order.index(x["day"]) if x["day"] in days_order else 9)
            msg = "📅 Розклад занять:\n\n"
            for s in sorted_schedule:
                msg += f"📌 {s['day']} {s['time']} — {s['group']} ({s['place']})\n"
            await update.message.reply_text(msg, reply_markup=schedule_keyboard())
        return SCHEDULE_MENU
    elif text == "➕ Додати заняття":
        await update.message.reply_text(
            "Введіть заняття у форматі:\n"
            "<b>День | Час | Група | Місце</b>\n\n"
            "Приклад: Пн | 17:00 | Початківці | Зал №1",
            parse_mode="HTML", reply_markup=back_to_schedule_keyboard()
        )
        return ADD_SCHEDULE
    elif text == "🗑 Видалити заняття":
        schedule = db_get_schedule()
        if not schedule:
            await update.message.reply_text("Розклад порожній.", reply_markup=schedule_keyboard())
            return SCHEDULE_MENU
        keyboard = [[InlineKeyboardButton(
            f"{s['day']} {s['time']} — {s['group']}", callback_data=f"del_schedule_{i}")]
            for i, s in enumerate(schedule)]
        await update.message.reply_text("Оберіть заняття для видалення:",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return SCHEDULE_MENU
    return SCHEDULE_MENU

async def add_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    logger.info(f"[ADD_SCHEDULE] Отримано повідомлення: '{text}'")  # ← лог для діагностики
    if text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    if text == "⬅️ До розкладу":
        await update.message.reply_text("📅 Управління розкладом:", reply_markup=schedule_keyboard())
        return SCHEDULE_MENU
    try:
        parts = [p.strip() for p in text.split("|")]
        logger.info(f"[ADD_SCHEDULE] Розібрано частини: {parts}")
        if len(parts) < 4:
            raise ValueError(f"Потрібно 4 поля через |, отримано {len(parts)}: {parts}")
        entry = {"day": parts[0], "time": parts[1], "group": parts[2], "place": parts[3]}
        logger.info(f"[ADD_SCHEDULE] Зберігаємо в MongoDB: {entry}")
        db_add_schedule(entry)
        logger.info(f"[ADD_SCHEDULE] ✅ Збережено успішно!")
        await update.message.reply_text(
            f"✅ Заняття {entry['day']} {entry['time']} додано!\n\n"
            f"🔔 Батьки будуть отримувати автонагадування за 2 години до цього заняття.",
            reply_markup=schedule_keyboard()
        )
    except Exception as e:
        logger.error(f"[ADD_SCHEDULE] ❌ Помилка: {e}")
        await update.message.reply_text(
            f"❌ Помилка: {e}\n\nФормат: <b>День | Час | Група | Місце</b>",
            parse_mode="HTML",
            reply_markup=back_to_schedule_keyboard()
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
        return HOMEWORK_MENU
    elif text == "➕ Задати домашнє":
        await update.message.reply_text(
            "Введіть завдання у форматі:\n"
            "<b>Група | Завдання | Дедлайн</b>\n\n"
            "Приклад: Початківці | Вивчити відкриття e4 e5 | 15.03.2025",
            parse_mode="HTML", reply_markup=back_to_homework_keyboard()
        )
        return ADD_HOMEWORK
    elif text == "🗑 Видалити завдання":
        homework = db_get_homework()
        if not homework:
            await update.message.reply_text("Завдань немає.", reply_markup=homework_keyboard())
            return HOMEWORK_MENU
        keyboard = [[InlineKeyboardButton(
            f"[{h['group']}] {h['task'][:30]}...", callback_data=f"del_hw_{i}")]
            for i, h in enumerate(homework)]
        await update.message.reply_text("Оберіть завдання для видалення:",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return HOMEWORK_MENU
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
        parts = [p.strip() for p in update.message.text.split("|")]
        if len(parts) < 3:
            raise ValueError("Потрібно 3 поля через |")
        hw = {
            "group": parts[0],
            "task": parts[1],
            "deadline": parts[2],
            "created": datetime.now().strftime("%d.%m.%Y")
        }
        db_add_homework(hw)
        sent = 0
        for pid in db_get_parents():
            try:
                await context.bot.send_message(
                    chat_id=int(pid),
                    text=f"📚 Нове домашнє завдання!\n\n"
                         f"👥 Група: {hw['group']}\n"
                         f"📝 Завдання: {hw['task']}\n"
                         f"📅 Здати до: {hw['deadline']}"
                )
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(
            f"✅ Завдання додано! Надіслано {sent} батькам.",
            reply_markup=homework_keyboard()
        )
    except Exception as e:
        logger.error(f"add_homework помилка: {e}")
        await update.message.reply_text(
            f"❌ Помилка: {e}\n\nФормат: <b>Група | Завдання | Дедлайн</b>",
            parse_mode="HTML",
            reply_markup=homework_keyboard()
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
        return NEWS_MENU
    elif text == "➕ Додати новину":
        await update.message.reply_text(
            "Введіть новину у форматі:\n<b>Заголовок | Текст</b>\n\n"
            "Приклад: Турнір у квітні | Запрошуємо всіх учнів 12 квітня!",
            parse_mode="HTML", reply_markup=back_to_news_keyboard()
        )
        return ADD_NEWS
    elif text == "🗑 Видалити новину":
        news = db_get_news()
        if not news:
            await update.message.reply_text("Новин немає.", reply_markup=news_keyboard())
            return NEWS_MENU
        keyboard = [[InlineKeyboardButton(n["title"], callback_data=f"del_news_{i}")]
                    for i, n in enumerate(news)]
        await update.message.reply_text("Оберіть новину для видалення:",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return NEWS_MENU
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
        parts = [p.strip() for p in update.message.text.split("|")]
        if len(parts) < 2:
            raise ValueError("Потрібно 2 поля через |")
        news_item = {
            "title": parts[0],
            "text": parts[1],
            "date": datetime.now().strftime("%d.%m.%Y")
        }
        db_add_news(news_item)
        sent = 0
        for pid in db_get_parents():
            try:
                await context.bot.send_message(
                    chat_id=int(pid),
                    text=f"📢 {news_item['title']}\n\n{news_item['text']}"
                )
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(
            f"✅ Новину опубліковано! Надіслано {sent} батькам.",
            reply_markup=news_keyboard()
        )
    except Exception as e:
        logger.error(f"add_news помилка: {e}")
        await update.message.reply_text(
            f"❌ Помилка: {e}\n\nФормат: <b>Заголовок | Текст</b>",
            parse_mode="HTML",
            reply_markup=news_keyboard()
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
        return MATERIALS_MENU
    elif text == "➕ Додати матеріал":
        await update.message.reply_text(
            "Введіть матеріал у форматі:\n<b>Назва | Посилання | Категорія</b>\n\n"
            "Приклад: Збірник задач | https://example.com | Задачники",
            parse_mode="HTML", reply_markup=back_to_materials_keyboard()
        )
        return ADD_MATERIAL
    elif text == "🗑 Видалити матеріал":
        materials = db_get_materials()
        if not materials:
            await update.message.reply_text("Матеріалів немає.", reply_markup=materials_keyboard())
            return MATERIALS_MENU
        keyboard = [[InlineKeyboardButton(m["title"], callback_data=f"del_material_{i}")]
                    for i, m in enumerate(materials)]
        await update.message.reply_text("Оберіть матеріал для видалення:",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return MATERIALS_MENU
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
        parts = [p.strip() for p in update.message.text.split("|")]
        if len(parts) < 3:
            raise ValueError("Потрібно 3 поля через |")
        mat = {
            "title": parts[0],
            "link": parts[1],
            "category": parts[2],
            "date": datetime.now().strftime("%d.%m.%Y")
        }
        db_add_material(mat)
        await update.message.reply_text(
            f"✅ Матеріал '{mat['title']}' додано!",
            reply_markup=materials_keyboard()
        )
    except Exception as e:
        logger.error(f"add_material помилка: {e}")
        await update.message.reply_text(
            f"❌ Помилка: {e}\n\nФормат: <b>Назва | Посилання | Категорія</b>",
            parse_mode="HTML",
            reply_markup=materials_keyboard()
        )
    return MATERIALS_MENU

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
                student = info.get("student", "не вказано")
                msg += f"• {info['name']} → учень: {student} (ID: {pid})\n"
            await update.message.reply_text(msg, reply_markup=chat_keyboard())
        return CHAT_MENU
    elif text == "🔗 Прив'язати батька до учня":
        parents = db_get_parents()
        students = db_get_students()
        if not parents:
            await update.message.reply_text("📭 Жоден батько ще не зареєструвався.", reply_markup=chat_keyboard())
            return CHAT_MENU
        if not students:
            await update.message.reply_text("📭 Спочатку додайте учнів.", reply_markup=chat_keyboard())
            return CHAT_MENU
        keyboard = []
        for pid, info in parents.items():
            student = info.get("student", "не вказано")
            keyboard.append([InlineKeyboardButton(
                f"{info['name']} → {student}", callback_data=f"link_parent_{pid}"
            )])
        await update.message.reply_text(
            "Оберіть батька для прив'язки до учня:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHAT_MENU
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
            await context.bot.send_message(
                chat_id=int(pid),
                text=f"📣 Повідомлення від тренера:\n\n{update.message.text}"
            )
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
        keyboard = []
        for i, s in enumerate(students):
            keyboard.append([
                InlineKeyboardButton(f"✅ {s['name']}", callback_data=f"att_present_{i}"),
                InlineKeyboardButton(f"❌ {s['name']}", callback_data=f"att_absent_{i}"),
            ])
        keyboard.append([InlineKeyboardButton("💾 Зберегти", callback_data="att_save")])

        context.user_data["attendance_today"] = {"date": today, "present": [], "absent": []}
        await update.message.reply_text(
            f"📝 Відмітьте відвідуваність на {today}\n✅ = був(ла) | ❌ = не прийшов(ла)",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ATTENDANCE_MENU

    elif text == "📊 Статистика відвідуваності":
        attendance = db_get_attendance()
        if not attendance:
            await update.message.reply_text("📭 Даних ще немає.", reply_markup=attendance_keyboard())
            return ATTENDANCE_MENU

        stats = {}
        for record in attendance.values():
            for name in record.get("present", []):
                stats.setdefault(name, {"present": 0, "absent": 0})
                stats[name]["present"] += 1
            for name in record.get("absent", []):
                stats.setdefault(name, {"present": 0, "absent": 0})
                stats[name]["absent"] += 1

        msg = "📊 Статистика відвідуваності:\n\n"
        for name, data in stats.items():
            total = data["present"] + data["absent"]
            pct = round(data["present"] / total * 100) if total > 0 else 0
            msg += f"👤 {name}\n   ✅ {data['present']} | ❌ {data['absent']} | 📊 {pct}%\n\n"
        await update.message.reply_text(msg, reply_markup=attendance_keyboard())
        return ATTENDANCE_MENU

    elif text == "📋 Журнал за датою":
        attendance = db_get_attendance()
        if not attendance:
            await update.message.reply_text("📭 Даних ще немає.", reply_markup=attendance_keyboard())
            return ATTENDANCE_MENU
        msg = "📋 Журнал відвідуваності:\n\n"
        for key, record in sorted(attendance.items(), reverse=True)[:10]:
            date = record.get("date", key)
            present = ", ".join(record.get("present", [])) or "—"
            absent = ", ".join(record.get("absent", [])) or "—"
            msg += f"📅 {date}\n✅ {present}\n❌ {absent}\n\n"
        await update.message.reply_text(msg, reply_markup=attendance_keyboard())
        return ATTENDANCE_MENU

    return ATTENDANCE_MENU

# ─────────────────────────────────────────────
# CALLBACK — ВІДВІДУВАНІСТЬ + ПРИВ'ЯЗКА + ВИДАЛЕННЯ
# ─────────────────────────────────────────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── Прив'язка батька — крок 1 ──
    if data.startswith("link_parent_"):
        pid = data.replace("link_parent_", "")
        context.user_data["linking_parent_id"] = pid
        students = db_get_students()
        parents = db_get_parents()
        parent_name = parents.get(pid, {}).get("name", "?")
        keyboard = [[InlineKeyboardButton(s["name"], callback_data=f"link_student_{i}")]
                    for i, s in enumerate(students)]
        await query.edit_message_text(
            f"👤 Батько: <b>{parent_name}</b>\n\nОберіть учня для прив'язки:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ── Прив'язка батька — крок 2 ──
    elif data.startswith("link_student_"):
        idx = int(data.split("_")[-1])
        pid = context.user_data.get("linking_parent_id")
        if not pid:
            await query.edit_message_text("❌ Помилка. Спробуйте знову.")
            return
        students = db_get_students()
        student_name = students[idx]["name"]
        db_link_parent_to_student(pid, student_name)
        parents = db_get_parents()
        parent_name = parents.get(pid, {}).get("name", "?")
        try:
            await context.bot.send_message(
                chat_id=int(pid),
                text=f"✅ Тренер прив'язав вас до учня: <b>{student_name}</b>\n"
                     f"Тепер ви можете переглядати відвідуваність своєї дитини.",
                parse_mode="HTML"
            )
        except Exception:
            pass
        await query.edit_message_text(f"✅ Готово!\n\n👨‍👩‍👦 {parent_name} → 🎓 {student_name}")
        return

    # ── Відвідуваність ──
    elif data.startswith("att_present_"):
        idx = int(data.split("_")[-1])
        students = db_get_students()
        name = students[idx]["name"]
        att = context.user_data.get("attendance_today", {"date": "", "present": [], "absent": []})
        if name not in att["present"]:
            att["present"].append(name)
        if name in att.get("absent", []):
            att["absent"].remove(name)
        context.user_data["attendance_today"] = att
        await query.answer(f"✅ {name} — присутній(я)")

    elif data.startswith("att_absent_"):
        idx = int(data.split("_")[-1])
        students = db_get_students()
        name = students[idx]["name"]
        att = context.user_data.get("attendance_today", {"date": "", "present": [], "absent": []})
        if name not in att.get("absent", []):
            att.setdefault("absent", []).append(name)
        if name in att.get("present", []):
            att["present"].remove(name)
        context.user_data["attendance_today"] = att
        await query.answer(f"❌ {name} — відсутній(я)")

    elif data == "att_save":
        att = context.user_data.get("attendance_today", {})
        date = att.get("date", datetime.now().strftime("%d.%m.%Y"))
        key = date.replace(".", "-")
        db_save_attendance(key, att)

        present = ", ".join(att.get("present", [])) or "—"
        absent = ", ".join(att.get("absent", [])) or "—"

        # Сповіщаємо батьків відсутніх
        for pid, info in db_get_parents().items():
            student_name = info.get("student", "")
            if student_name and student_name in att.get("absent", []):
                try:
                    await context.bot.send_message(
                        chat_id=int(pid),
                        text=f"⚠️ {student_name} сьогодні ({date}) не з'явився(лась) на занятті.\n"
                             f"Якщо це помилка — зверніться до тренера."
                    )
                except Exception:
                    pass

        await query.edit_message_text(
            f"✅ Відвідуваність збережено!\n\n"
            f"📅 Дата: {date}\n"
            f"✅ Присутні: {present}\n"
            f"❌ Відсутні: {absent}"
        )

    # ── Видалення ──
    elif data.startswith("del_student_"):
        idx = int(data.split("_")[-1])
        students = db_get_students()
        if 0 <= idx < len(students):
            name = students[idx]["name"]
            db_delete_student(idx)
            await query.edit_message_text(f"🗑 Учня {name} видалено.")
        else:
            await query.edit_message_text("❌ Учня не знайдено.")

    elif data.startswith("del_schedule_"):
        idx = int(data.split("_")[-1])
        schedule = db_get_schedule()
        if 0 <= idx < len(schedule):
            s = schedule[idx]
            db_delete_schedule(idx)
            await query.edit_message_text(f"🗑 Заняття {s['day']} {s['time']} видалено.")
        else:
            await query.edit_message_text("❌ Заняття не знайдено.")

    elif data.startswith("del_hw_"):
        idx = int(data.split("_")[-1])
        db_delete_homework(idx)
        await query.edit_message_text("🗑 Завдання видалено.")

    elif data.startswith("del_news_"):
        idx = int(data.split("_")[-1])
        news = db_get_news()
        if 0 <= idx < len(news):
            n = news[idx]
            db_delete_news(idx)
            await query.edit_message_text(f"🗑 Новину '{n['title']}' видалено.")
        else:
            await query.edit_message_text("❌ Новину не знайдено.")

    elif data.startswith("del_material_"):
        idx = int(data.split("_")[-1])
        materials = db_get_materials()
        if 0 <= idx < len(materials):
            m = materials[idx]
            db_delete_material(idx)
            await query.edit_message_text(f"🗑 Матеріал '{m['title']}' видалено.")
        else:
            await query.edit_message_text("❌ Матеріал не знайдено.")

# ─────────────────────────────────────────────
# ЗАПУСК
# ─────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Перевіряємо MongoDB при старті ──
    if not check_mongo_connection():
        print("❌ КРИТИЧНА ПОМИЛКА: Не вдалося підключитися до MongoDB! Перевірте MONGODB_URI")
        return

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU:       [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler)],
            PARENT_MENU:     [MessageHandler(filters.TEXT & ~filters.COMMAND, parent_menu_handler)],
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
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Автонагадування — перевірка щогодини
    app.job_queue.run_repeating(send_reminders, interval=3600, first=10)

    print("♟️ Chess Trainer Bot v3.1 + MongoDB запущено!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
