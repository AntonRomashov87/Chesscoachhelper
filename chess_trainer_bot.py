"""
♟️ Chess Trainer Bot — Telegram-бот для тренера шахової школи
Залежності: pip install python-telegram-bot==20.7
"""

import logging
import json
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)

# ─────────────────────────────────────────────
# НАЛАШТУВАННЯ — читаємо з середовища Render
# ─────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRAINER_ID = int(os.environ.get("TRAINER_ID"))

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
    CHAT_MENU, BROADCAST_MSG
) = range(13)

# ─────────────────────────────────────────────
# БАЗА ДАНИХ (JSON-файл)
# ─────────────────────────────────────────────
DB_FILE = "chess_bot_data.json"

def load_db() -> dict:
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "students": [],
        "schedule": [],
        "homework": [],
        "news": [],
        "materials": [],
        "parents": {}
    }

def save_db(data: dict):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

db = load_db()

# ─────────────────────────────────────────────
# КЛАВІАТУРИ
# ─────────────────────────────────────────────
def main_keyboard():
    return ReplyKeyboardMarkup([
        ["📋 Список учнів",    "📅 Розклад занять"],
        ["📚 Домашні завдання","📢 Новини/Оголошення"],
        ["🎓 Матеріали",       "💬 Чат з батьками"],
    ], resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup([["⬅️ Головне меню"]], resize_keyboard=True)

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
        ["⬅️ Головне меню"],
    ], resize_keyboard=True)

# ─────────────────────────────────────────────
# ПЕРЕВІРКА ТРЕНЕРА
# ─────────────────────────────────────────────
def is_trainer(update: Update) -> bool:
    return update.effective_user.id == TRAINER_ID

async def access_denied(update: Update):
    await update.message.reply_text(
        "⛔️ Цей бот призначений лише для тренера.\n"
        "Якщо ви батько/мати учня — зверніться до тренера для доступу."
    )

# ─────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id != TRAINER_ID:
        db["parents"][str(user.id)] = user.full_name
        save_db(db)
        await update.message.reply_text(
            f"👋 Вітаємо, {user.first_name}!\n\n"
            "Ви зареєстровані як батько/мати учня.\n"
            "Тренер зможе надсилати вам повідомлення, розклад та домашні завдання.\n\n"
            f"Ваш ID: <code>{user.id}</code>",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"♟️ Вітаємо, тренере {user.first_name}!\n\n"
        "Оберіть розділ у меню нижче 👇",
        reply_markup=main_keyboard()
    )
    return MAIN_MENU

# ─────────────────────────────────────────────
# ГОЛОВНЕ МЕНЮ
# ─────────────────────────────────────────────
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update):
        await access_denied(update)
        return ConversationHandler.END

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
        parents_count = len(db["parents"])
        await update.message.reply_text(
            f"💬 Комунікація з батьками\n👥 Зареєстровано батьків: {parents_count}",
            reply_markup=chat_keyboard()
        )
        return CHAT_MENU

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
        if not db["students"]:
            await update.message.reply_text("📭 Список учнів порожній.", reply_markup=students_keyboard())
        else:
            msg = "📋 Список учнів:\n\n"
            for i, s in enumerate(db["students"], 1):
                msg += f"{i}. {s['name']} — {s['level']} | {s['phone']}\n"
            await update.message.reply_text(msg, reply_markup=students_keyboard())
        return STUDENTS_MENU
    elif text == "➕ Додати учня":
        await update.message.reply_text(
            "Введіть дані учня у форматі:\n"
            "<b>Ім'я Прізвище | рівень | телефон батьків</b>\n\n"
            "Приклад: Олег Іванов | початківець | +380991234567",
            parse_mode="HTML", reply_markup=back_keyboard()
        )
        return ADD_STUDENT
    elif text == "🗑 Видалити учня":
        if not db["students"]:
            await update.message.reply_text("Список порожній.", reply_markup=students_keyboard())
            return STUDENTS_MENU
        keyboard = [[InlineKeyboardButton(s["name"], callback_data=f"del_student_{i}")]
                    for i, s in enumerate(db["students"])]
        await update.message.reply_text("Оберіть учня для видалення:",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return STUDENTS_MENU
    return STUDENTS_MENU

async def add_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    try:
        parts = [p.strip() for p in update.message.text.split("|")]
        student = {"name": parts[0], "level": parts[1], "phone": parts[2],
                   "added": datetime.now().strftime("%d.%m.%Y")}
        db["students"].append(student)
        save_db(db)
        await update.message.reply_text(f"✅ Учня {student['name']} додано!", reply_markup=students_keyboard())
    except Exception:
        await update.message.reply_text("❌ Невірний формат. Спробуйте ще раз.", reply_markup=students_keyboard())
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
        if not db["schedule"]:
            await update.message.reply_text("📭 Розклад порожній.", reply_markup=schedule_keyboard())
        else:
            days_order = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
            sorted_schedule = sorted(db["schedule"],
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
            parse_mode="HTML", reply_markup=back_keyboard()
        )
        return ADD_SCHEDULE
    elif text == "🗑 Видалити заняття":
        if not db["schedule"]:
            await update.message.reply_text("Розклад порожній.", reply_markup=schedule_keyboard())
            return SCHEDULE_MENU
        keyboard = [[InlineKeyboardButton(
            f"{s['day']} {s['time']} — {s['group']}", callback_data=f"del_schedule_{i}")]
            for i, s in enumerate(db["schedule"])]
        await update.message.reply_text("Оберіть заняття для видалення:",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return SCHEDULE_MENU
    return SCHEDULE_MENU

async def add_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    try:
        parts = [p.strip() for p in update.message.text.split("|")]
        entry = {"day": parts[0], "time": parts[1], "group": parts[2], "place": parts[3]}
        db["schedule"].append(entry)
        save_db(db)
        await update.message.reply_text(f"✅ Заняття {entry['day']} {entry['time']} додано!", reply_markup=schedule_keyboard())
    except Exception:
        await update.message.reply_text("❌ Невірний формат. Спробуйте ще раз.", reply_markup=schedule_keyboard())
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
        if not db["homework"]:
            await update.message.reply_text("📭 Завдань немає.", reply_markup=homework_keyboard())
        else:
            msg = "📚 Домашні завдання:\n\n"
            for i, h in enumerate(db["homework"], 1):
                msg += f"{i}. [{h['group']}] {h['task']}\n   📅 До: {h['deadline']}\n\n"
            await update.message.reply_text(msg, reply_markup=homework_keyboard())
        return HOMEWORK_MENU
    elif text == "➕ Задати домашнє":
        await update.message.reply_text(
            "Введіть завдання у форматі:\n"
            "<b>Група | Завдання | Дедлайн</b>\n\n"
            "Приклад: Початківці | Вивчити відкриття e4 e5 | 15.03.2025",
            parse_mode="HTML", reply_markup=back_keyboard()
        )
        return ADD_HOMEWORK
    elif text == "🗑 Видалити завдання":
        if not db["homework"]:
            await update.message.reply_text("Завдань немає.", reply_markup=homework_keyboard())
            return HOMEWORK_MENU
        keyboard = [[InlineKeyboardButton(
            f"[{h['group']}] {h['task'][:30]}...", callback_data=f"del_hw_{i}")]
            for i, h in enumerate(db["homework"])]
        await update.message.reply_text("Оберіть завдання для видалення:",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return HOMEWORK_MENU
    return HOMEWORK_MENU

async def add_homework(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    try:
        parts = [p.strip() for p in update.message.text.split("|")]
        hw = {"group": parts[0], "task": parts[1], "deadline": parts[2],
              "created": datetime.now().strftime("%d.%m.%Y")}
        db["homework"].append(hw)
        save_db(db)
        sent = 0
        for pid in db["parents"]:
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
    except Exception:
        await update.message.reply_text("❌ Невірний формат. Спробуйте ще раз.", reply_markup=homework_keyboard())
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
        if not db["news"]:
            await update.message.reply_text("📭 Новин немає.", reply_markup=news_keyboard())
        else:
            msg = "📢 Новини/Оголошення:\n\n"
            for i, n in enumerate(db["news"], 1):
                msg += f"{i}. {n['title']}\n   {n['text']}\n   📅 {n['date']}\n\n"
            await update.message.reply_text(msg, reply_markup=news_keyboard())
        return NEWS_MENU
    elif text == "➕ Додати новину":
        await update.message.reply_text(
            "Введіть новину у форматі:\n"
            "<b>Заголовок | Текст</b>\n\n"
            "Приклад: Турнір у квітні | Запрошуємо всіх учнів на міський турнір 12 квітня!",
            parse_mode="HTML", reply_markup=back_keyboard()
        )
        return ADD_NEWS
    elif text == "🗑 Видалити новину":
        if not db["news"]:
            await update.message.reply_text("Новин немає.", reply_markup=news_keyboard())
            return NEWS_MENU
        keyboard = [[InlineKeyboardButton(n["title"], callback_data=f"del_news_{i}")]
                    for i, n in enumerate(db["news"])]
        await update.message.reply_text("Оберіть новину для видалення:",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return NEWS_MENU
    return NEWS_MENU

async def add_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    try:
        parts = [p.strip() for p in update.message.text.split("|")]
        news_item = {"title": parts[0], "text": parts[1],
                     "date": datetime.now().strftime("%d.%m.%Y")}
        db["news"].append(news_item)
        save_db(db)
        sent = 0
        for pid in db["parents"]:
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
    except Exception:
        await update.message.reply_text("❌ Невірний формат.", reply_markup=news_keyboard())
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
        if not db["materials"]:
            await update.message.reply_text("📭 Матеріалів немає.", reply_markup=materials_keyboard())
        else:
            msg = "🎓 Навчальні матеріали:\n\n"
            for i, m in enumerate(db["materials"], 1):
                msg += f"{i}. {m['title']}\n   🔗 {m['link']}\n   📁 {m['category']}\n\n"
            await update.message.reply_text(msg, reply_markup=materials_keyboard())
        return MATERIALS_MENU
    elif text == "➕ Додати матеріал":
        await update.message.reply_text(
            "Введіть матеріал у форматі:\n"
            "<b>Назва | Посилання | Категорія</b>\n\n"
            "Приклад: Збірник задач для початківців | https://example.com | Задачники",
            parse_mode="HTML", reply_markup=back_keyboard()
        )
        return ADD_MATERIAL
    elif text == "🗑 Видалити матеріал":
        if not db["materials"]:
            await update.message.reply_text("Матеріалів немає.", reply_markup=materials_keyboard())
            return MATERIALS_MENU
        keyboard = [[InlineKeyboardButton(m["title"], callback_data=f"del_material_{i}")]
                    for i, m in enumerate(db["materials"])]
        await update.message.reply_text("Оберіть матеріал для видалення:",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return MATERIALS_MENU
    return MATERIALS_MENU

async def add_material(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU
    try:
        parts = [p.strip() for p in update.message.text.split("|")]
        mat = {"title": parts[0], "link": parts[1], "category": parts[2],
               "date": datetime.now().strftime("%d.%m.%Y")}
        db["materials"].append(mat)
        save_db(db)
        await update.message.reply_text(f"✅ Матеріал '{mat['title']}' додано!", reply_markup=materials_keyboard())
    except Exception:
        await update.message.reply_text("❌ Невірний формат.", reply_markup=materials_keyboard())
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
        if not db["parents"]:
            await update.message.reply_text("📭 Жоден батько ще не зареєструвався.", reply_markup=chat_keyboard())
        else:
            msg = "👥 Зареєстровані батьки:\n\n"
            for pid, name in db["parents"].items():
                msg += f"• {name} (ID: {pid})\n"
            await update.message.reply_text(msg, reply_markup=chat_keyboard())
        return CHAT_MENU
    elif text == "📣 Розіслати всім батькам":
        await update.message.reply_text(
            "Введіть повідомлення для розсилки всім батькам:",
            reply_markup=back_keyboard()
        )
        return BROADCAST_MSG
    return CHAT_MENU

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Головне меню":
        await update.message.reply_text("Головне меню:", reply_markup=main_keyboard())
        return MAIN_MENU

    message_text = update.message.text
    sent = 0
    failed = 0
    for pid in db["parents"]:
        try:
            await context.bot.send_message(
                chat_id=int(pid),
                text=f"📣 Повідомлення від тренера:\n\n{message_text}"
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
# CALLBACK — ВИДАЛЕННЯ
# ─────────────────────────────────────────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("del_student_"):
        idx = int(data.split("_")[-1])
        name = db["students"][idx]["name"]
        db["students"].pop(idx)
        save_db(db)
        await query.edit_message_text(f"🗑 Учня {name} видалено.")
    elif data.startswith("del_schedule_"):
        idx = int(data.split("_")[-1])
        s = db["schedule"][idx]
        db["schedule"].pop(idx)
        save_db(db)
        await query.edit_message_text(f"🗑 Заняття {s['day']} {s['time']} видалено.")
    elif data.startswith("del_hw_"):
        idx = int(data.split("_")[-1])
        db["homework"].pop(idx)
        save_db(db)
        await query.edit_message_text("🗑 Завдання видалено.")
    elif data.startswith("del_news_"):
        idx = int(data.split("_")[-1])
        n = db["news"][idx]
        db["news"].pop(idx)
        save_db(db)
        await query.edit_message_text(f"🗑 Новину '{n['title']}' видалено.")
    elif data.startswith("del_material_"):
        idx = int(data.split("_")[-1])
        m = db["materials"][idx]
        db["materials"].pop(idx)
        save_db(db)
        await query.edit_message_text(f"🗑 Матеріал '{m['title']}' видалено.")

# ─────────────────────────────────────────────
# ЗАПУСК
# ─────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU:      [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler)],
            STUDENTS_MENU:  [MessageHandler(filters.TEXT & ~filters.COMMAND, students_menu)],
            ADD_STUDENT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_student)],
            SCHEDULE_MENU:  [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_menu)],
            ADD_SCHEDULE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_schedule)],
            HOMEWORK_MENU:  [MessageHandler(filters.TEXT & ~filters.COMMAND, homework_menu)],
            ADD_HOMEWORK:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_homework)],
            NEWS_MENU:      [MessageHandler(filters.TEXT & ~filters.COMMAND, news_menu)],
            ADD_NEWS:       [MessageHandler(filters.TEXT & ~filters.COMMAND, add_news)],
            MATERIALS_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, materials_menu)],
            ADD_MATERIAL:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_material)],
            CHAT_MENU:      [MessageHandler(filters.TEXT & ~filters.COMMAND, chat_menu)],
            BROADCAST_MSG:  [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("♟️ Chess Trainer Bot запущено!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
if __name__ == "__main__":
    main()
