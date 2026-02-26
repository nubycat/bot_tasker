

# 🤖 Telegram Tasker Bot

**Telegram Tasker Bot** — это backend-ориентированный pet-project для управления задачами через Telegram-бота с отдельным API-сервером.

Проект построен как **реальный сервис**, а не учебный CRUD:

* отдельный бот и backend
* чистая архитектура
* PostgreSQL + миграции
* подготовка к масштабированию (командные задачи, роли, тесты)

---

## 🚀 Основная идея

Пользователь создаёт задачи **напрямую в Telegram**, бот собирает данные пошагово (FSM) и отправляет их в backend API, где задачи сохраняются в базе данных.

**Поток данных:**

```
Telegram → Bot (aiogram) → FastAPI → PostgreSQL
```

---

## ✨ Возможности (на текущий момент)

### ✅ Реализовано

* Telegram-бот (aiogram)

* FastAPI backend

* PostgreSQL

* SQLAlchemy 2.0 (async)

* Alembic миграции

* Docker + docker-compose

* Модель пользователей (Telegram ID)

* Модель задач

* Создание задач через API

* Парсинг времени (18, 18:30)

* FSM (пошаговый ввод задачи)

* Team mode (create / join / active context)

* Разделение personal / team задач

* Базовые статусы задач

* Timezone support (APP_TZ)

### 🚧 В процессе

* ⏳ Отображение, кто именно выполнил задачу в team mode
* ⏳ Pytest (endpoint + DB tests)

### 🗺 Планируется

* 🔜 Напоминания по времени (scheduler / background worker)
* 🔜 Роли и права доступа
* 🔜 Улучшение UX командного режима
* 🔜 CI (GitHub Actions)
* 🔜 Больше тестов


---

## 🧱 Архитектура проекта

```
bot_tasker/

├── bot/                         # Telegram bot (aiogram)
│   ├── app/
│   │   ├── handlers/            # Message & callback handlers
│   │   ├── states/              # FSM states
│   │   └── main.py              # Bot entrypoint
│   └── requirements.txt

├── backend/                     # FastAPI backend
│   ├── app/
│   │   ├── core/                # Settings, config, timezone
│   │   ├── db/                  # DB engine & session
│   │   ├── models/              # SQLAlchemy models
│   │   │   ├── user.py
│   │   │   ├── task.py
│   │   │   ├── team.py
│   │   │   └── team_member.py
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── repository/          # DB access layer
│   │   ├── routers/             # API endpoints
│   │   └── main.py              # FastAPI entrypoint
│   ├── alembic/                 # DB migrations
│   └── requirements.txt

├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🛠️ Стек технологий

**Backend**

* Python 3.13
* FastAPI
* SQLAlchemy 2.0 (async)
* PostgreSQL
* Alembic

**Bot**

* aiogram 3
* FSM (Finite State Machine)

**Infrastructure**

* Docker
* Docker Compose

---

## ⚙️ Установка и запуск

### 1️⃣ Клонировать репозиторий

```bash
git clone https://github.com/nubycat/bot_tasker.git
cd bot_tasker
```

### 2️⃣ Создать `.env`

```bash
cp .env.example .env
```

### 3️⃣ Запустить через Docker

```bash
docker compose up -d --build
```

### 4️⃣ Применить миграции базы (обязательно)

```bash
docker compose exec backend alembic upgrade head
```

Backend будет доступен по адресу:

```
http://localhost:8000
```

Swagger:

```
http://localhost:8000/docs
```

---

## 🧪 Тестирование (план)

Планируется полноценное тестирование:

* API endpoints
* работа с БД
* edge cases
* отдельная test-БД

---

## 🎯 Цель проекта

Проект создаётся как:

* 📌 **сильный pet-project для стажировки / junior-позиции**
* 📌 демонстрация backend-мышления
* 📌 пример чистой архитектуры и реального API
* 📌 основа для масштабирования (не одноразовый CRUD)

---

## 👤 Автор

**Rustam Musaev**
GitHub: [https://github.com/nubycat](https://github.com/nubycat)

---

## 📌 Статус

> 🚀 MVP завершён (end-to-end рабочий продукт)
Проект полностью функционирует и может быть запущен локально через Docker.
Основная логика (личные задачи, командный режим, разделение personal / team контекста, timezone support) реализована и стабильна.

>🔧 Проект поддерживается и может дорабатываться точечно в рамках roadmap.

---








