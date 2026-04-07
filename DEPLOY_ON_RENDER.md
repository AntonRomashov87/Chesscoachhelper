# 🚀 Деплоймент Chess Trainer Bot на Render (FREE)

## 📋 Передумови
1. GitHub акаунт (обов'язково)
2. MongoDB Atlas (безкоштовна база данних)
3. Telegram BotFather токен
4. ID тренера в Telegram

---

## 🔧 КРОК 1: Підготовка GitHub репозиторію

### 1.1 Створіть репозиторій на GitHub
```bash
1. Йдіть на github.com → Sign in
2. Натисніть + (верхній правий кут) → New repository
3. Repository name: `chess-trainer-bot`
4. Опис: "Telegram bot for chess school"
5. Виберіть PUBLIC (важливо для Render!)
6. Create repository
```

### 1.2 Завантажте код на GitHub
```bash
# Клонуйте репозиторій локально
git clone https://github.com/YOUR_USERNAME/chess-trainer-bot.git
cd chess-trainer-bot

# Скопіюйте файли (ці файли у вас вже є):
# - chess_bot_fixed.py (перейменуйте на bot.py)
# - requirements.txt

# Завантажте на GitHub
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/chess-trainer-bot.git
git push -u origin main
```

### 1.3 Файлова структура репозиторію
```
chess-trainer-bot/
├── bot.py                    ← основний файл (переіменований chess_bot_fixed.py)
├── requirements.txt          ← залежності
├── .env.example             ← шаблон змінних (див. нижче)
└── README.md                ← документація
```

---

## 🔐 КРОК 2: MongoDB Atlas (безкоштовна база данних)

### 2.1 Реєстрація
```
1. Йдіть на mongodb.com/cloud/atlas
2. Натисніть Sign Up або Sign In
3. Виберіть "Create a Team"
4. Заповніть дані (Gmail, пароль)
5. Прийміть Terms of Service
```

### 2.2 Створення кластера
```
1. Натисніть "Create" → "Create a Deployment"
2. Виберіть FREE (M0 - 512MB)
3. Cloud Provider: AWS (або що є в вашому регіоні)
4. Region: Виберіть найближчий (наприклад, eu-west-1 для Європи)
5. Cluster Tier: Free (M0)
6. Натисніть "Create Deployment"
```

### 2.3 Безпека
```
1. Дочекайтесь, поки кластер активується (5-10 хвилин)
2. Натисніть на "Security" (вліво у меню)
3. "Create a Database User":
   - Username: chess_admin
   - Password: (강력й пароль, скопіюйте його!)
   - Create User

4. "Network Access":
   - Add IP Address
   - Виберіть "Allow Access from Anywhere" (0.0.0.0/0)
   - Confirm
```

### 2.4 Отримання Connection String
```
1. Натисніть "Database" → "Clusters"
2. На вашому кластері натисніть "Connect"
3. Виберіть "Connect your application"
4. Копіюйте CONNECTION STRING
   Він буде схожий на:
   mongodb+srv://chess_admin:PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority

5. ЗАМІНІТЬ PASSWORD на ваш реальний пароль!
6. ЗАМІНІТЬ database назву на chess_trainer:
   mongodb+srv://chess_admin:PASSWORD@cluster0.xxxxx.mongodb.net/chess_trainer?retryWrites=true&w=majority

7. Скопіюйте цей рядок - він вам потрібен для Render
```

---

## 🤖 КРОК 3: Telegram токен

```
1. Напишіть @BotFather у Telegram
2. Натисніть /start
3. Натисніть /newbot
4. Дайте ім'я: Chess Trainer Bot
5. Дайте username: chess_trainer_bot_XXXXX (унікальне!)
6. BotFather поверне TOKEN - скопіюйте його

Приклад токена:
123456789:ABCdefGHIjklMNOPqrsTUVwxyz1234567890
```

---

## 🎯 КРОК 4: Render деплоймент

### 4.1 Реєстрація на Render
```
1. Йдіть на render.com
2. Sign up → Sign up with GitHub (обов'язково!)
3. Авторизуйте GitHub у Render
```

### 4.2 Підключення GitHub репозиторію
```
1. Натисніть "New +" (верхній правий кут)
2. Виберіть "Web Service"
3. Натисніть "Connect Repository"
4. Виберіть "chess-trainer-bot" з вашого профілю
5. Натисніть "Connect"
```

### 4.3 Налаштування Render сервісу
```
Name: chess-trainer-bot
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: python bot.py
Plan: Free

Скролите вниз → Advanced
Нижче натисніть "Add Environment Variable"

Додайте ці змінні:
┌─────────────────┬──────────────────────────────────┐
│ BOT_TOKEN       │ 123456789:ABCdefGHIjklMNOPqr... │
│ MONGODB_URI     │ mongodb+srv://chess_admin:...    │
│ TRAINER_ID      │ YOUR_TELEGRAM_ID                 │
└─────────────────┴──────────────────────────────────┘
```

### 4.4 Отримання вашого Telegram ID
```
Найпростіший спосіб:
1. Напишіть @userinfobot у Telegram
2. Він поверне ваш ID (наприклад: 123456789)
3. Скопіюйте це число у TRAINER_ID
```

### 4.5 Деплоймент
```
1. Натисніть "Deploy" (внизу)
2. Дочекайтесь 2-5 хвилин, поки бот розгортається
3. Коли статус буде "Live", бот активний!
```

---

## ✅ КРОК 5: Тестування

### Тест 1: Перевірка бота
```
1. Відкрийте Telegram
2. Пошукайте свого бота: @chess_trainer_bot_XXXXX
3. Натисніть /start
4. Якщо ви - тренер, ви побачите меню тренера
5. Якщо ні, побачите меню для реєстрації
```

### Тест 2: Додавання учня
```
1. Як тренер натисніть "📋 Список учнів"
2. "➕ Додати учня"
3. Введіть:
   Олег Іванов | 1-2 розряд | 1-2 розряд | +380991234567 | +380671234567
4. Натисніть Send
```

### Тест 3: Реєстрація батька/учня
```
1. В іншому чаті спробуйте /start як батько
2. Виберіть "👨‍👩‍👦 Я батько/мати"
3. Зареєструйтеся
4. Тренер зможе вас прив'язати до учня
```

---

## 🔄 КРОК 6: Оновлення коду

### Коли вам потрібно оновити бота:
```bash
# На локальній машині:
git add .
git commit -m "Fixed bug in schedule"
git push origin main

# На Render: автоматично розпочнеться нерове розгортання!
# Статус можна переглядати в Dashboard → Logs
```

---

## 🆘 ПОМИЛКИ І РІШЕННЯ

### ❌ "ModuleNotFoundError: No module named 'telegram'"
```
✅ Рішення: Переконайтесь, що requirements.txt завантажений
   Перебудуйте в Render: Settings → Manual Deploy
```

### ❌ "MongoDB Connection Failed"
```
✅ Рішення:
   1. Перевірте MONGODB_URI (нема пробілів)
   2. Переконайтесь, IP 0.0.0.0/0 дозволений в MongoDB Atlas
   3. Вимкніть VPN якщо вона включена
```

### ❌ Bot не відповідає
```
✅ Рішення:
   1. Перевірте Logs на Render (Dashboard → Logs)
   2. Перевірте BOT_TOKEN (мають бути символи)
   3. Перевірте TRAINER_ID (мають бути цифри)
```

### ❌ "RuntimeError: Event loop is closed"
```
✅ Рішення: Це нормально на Render, бот все одно працює
   Просто ігноруйте це
```

---

## 📊 Моніторинг

### Переглядати логи:
```
1. Render Dashboard
2. Виберіть chess-trainer-bot
3. Натисніть "Logs"
4. Бачите всі повідомлення про помилки в реальному часі
```

### Рестартити бота:
```
1. Settings → Manual Deploy
2. Натисніть "Deploy latest commit"
```

---

## 💰 ВАРТІСТЬ (для вас = 0 грн!)

| Сервіс | План | Вартість |
|--------|------|----------|
| Render | Free | ✅ 0$ |
| MongoDB Atlas | Free (M0) | ✅ 0$ |
| GitHub | Free | ✅ 0$ |
| Telegram Bot API | - | ✅ 0$ |
| **ВСЬОГО** | | ✅ **0$** |

---

## 🎉 Готово!

Ваш бот тепер:
- ✅ Запущений 24/7 на Render
- ✅ Дані зберігаються на MongoDB Atlas
- ✅ Автоматично обновляється при git push
- ✅ Безкоштовно!

---

## 📞 Контакти для допомоги

- **Render Support**: https://render.com/docs
- **MongoDB Support**: https://docs.mongodb.com
- **python-telegram-bot**: https://python-telegram-bot.readthedocs.io

**Успіхів з ботом! 🚀♟️**
