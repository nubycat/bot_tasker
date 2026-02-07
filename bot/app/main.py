import asyncio
import os


import httpx

# from fastapi import status
from datetime import datetime
from httpx import RequestError, HTTPStatusError
from http import HTTPStatus
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


# ---- helpers ----
async def backend_get(path: str, *, params: dict) -> dict | list:
    """GET JSON from backend."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{BACKEND_URL}{path}", params=params)
        r.raise_for_status()
        return r.json()


# ---------- Utils ----------
def format_due_hhmm(iso_dt: str) -> str:
    return datetime.fromisoformat(iso_dt).strftime("%H:%M")


# ---------- FSM ----------
class TaskCreateFSM(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_remind_at = State()


# ---------- Keyboards ----------
def mode_choose_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Лично", callback_data="mode:personal")
    kb.button(text="👥 Команда", callback_data="mode:team")
    kb.adjust(2)
    return kb.as_markup()


def mode_menu_kb(mode: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Add task", callback_data=f"task:add:{mode}")
    kb.button(text="📅 Today", callback_data=f"task:today:{mode}")
    kb.button(text="⬅️ Back", callback_data="mode:choose")
    kb.adjust(2, 1)
    return kb.as_markup()


router = Router()


# ---------- /start ----------
@router.message(CommandStart())
async def start(message: Message) -> None:
    # 1) Upsert user в backend
    payload = {
        "telegram_id": message.from_user.id,
        "username": message.from_user.username,
        "first_name": message.from_user.first_name,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(f"{BACKEND_URL}/users/upsert", json=payload)
        r.raise_for_status()

    # 2) Показать выбор режима
    await message.answer("Выбери режим работы:", reply_markup=mode_choose_kb())


# ---------- Callbacks ----------
@router.callback_query(F.data.startswith("mode:"))
async def on_mode(callback: CallbackQuery) -> None:
    data = callback.data or ""

    if data == "mode:personal":
        await callback.message.answer(
            "Режим: Лично ✅", reply_markup=mode_menu_kb("personal")
        )

    elif data == "mode:team":
        await callback.message.answer(
            "Режим: Команда ✅", reply_markup=mode_menu_kb("team")
        )

    elif data == "mode:choose":
        await callback.message.answer(
            "Выбери режим работы:", reply_markup=mode_choose_kb()
        )

    await callback.answer()


#  создание задачи
@router.callback_query(F.data.startswith("task:add:"))
async def on_task_add(callback: CallbackQuery, state: FSMContext) -> None:
    # mode  (на будущее)
    mode = (callback.data or "").split(":")[-1]
    await state.update_data(mode=mode)

    # старт FSM
    await state.set_state(TaskCreateFSM.waiting_title)
    await callback.message.answer(
        f"Ок ✅ Создаём задачу ({mode}). Пришли *title*.", parse_mode="Markdown"
    )
    await callback.answer()


#  Хендлер на кнопку 📅 Today (только для personal)
@router.callback_query(F.data.startswith("task:today:"))
async def on_today(callback: CallbackQuery) -> None:
    mode = (callback.data or "").split(":")[-1]

    if mode != "personal":
        await callback.message.answer("Today пока только для личных задач ✅")
        await callback.answer()
        return

    tg_id = callback.from_user.id

    try:
        tasks = await backend_get(
            "/tasks/personal/today", params={"telegram_id": tg_id}
        )
    except RequestError:
        await callback.message.answer("Backend недоступен 😕 Попробуй позже.")
        await callback.answer()
        return
    except HTTPStatusError as e:
        await callback.message.answer(f"Ошибка backend: {e.response.status_code}")
        await callback.answer()
        return

    if not tasks:
        await callback.message.answer(
            "Сегодня задач нет ✅", reply_markup=mode_menu_kb("personal")
        )
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for t in tasks:
        task_id = t["id"]
        title = (t.get("title") or "").strip() or "(без названия)"
        hhmm = format_due_hhmm(t["due_at"])
        kb.button(text=f"{hhmm} — {title}", callback_data=f"today_task:{task_id}")

    kb.button(text="⬅ В меню", callback_data="menu:personal")
    kb.adjust(1)

    try:
        await callback.message.edit_text(
            "Задачи на сегодня:", reply_markup=kb.as_markup()
        )
    except Exception:
        await callback.message.answer("Задачи на сегодня:", reply_markup=kb.as_markup())
    await callback.answer()


# Хендлер на клик по задаче today_task:<id> (детали)
@router.callback_query(F.data.startswith("today_task:"))
async def on_today_task(callback: CallbackQuery) -> None:
    """Open task card from Today list: fetch task details and show formatted message."""
    tg_id = callback.from_user.id

    # 1) Достаём task_id из callback_data вида "today_task:<id>"
    try:
        task_id = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer()
        return

    # 2) Запрашиваем детали задачи в backend (проверка доступа идёт по telegram_id)
    try:
        t = await backend_get(
            f"/tasks/personal/{task_id}", params={"telegram_id": tg_id}
        )
    except RequestError:
        await callback.message.answer("Backend недоступен 😕 Попробуй позже.")
        await callback.answer()
        return
    except HTTPStatusError as e:
        # Backend ответил, но статус не 2xx
        code = e.response.status_code
        if code == HTTPStatus.NOT_FOUND:
            await callback.message.answer("Задача не найдена или не доступна.")
        else:
            await callback.message.answer(f"Ошибка backend: {code}")
        await callback.answer()
        return

    # 3) Формируем карточку (подчищаем пустые поля)
    title = (t.get("title") or "").strip() or "(без названия)"
    desc = (t.get("description") or "").strip() or "(без описания)"
    hhmm = format_due_hhmm(t["due_at"])

    text = f"#{t['id']}\n{title}\n\n{desc}\nВремя: {hhmm}"

    # 4) Кнопка “назад” ведёт на перерисовку списка Today
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ Назад к списку", callback_data="task:today:personal")
    kb.adjust(1)

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


# Хендлер меню личного режима
@router.callback_query(F.data == "menu:personal")
async def on_menu_personal(callback: CallbackQuery) -> None:
    """Show personal mode menu."""
    await callback.message.edit_text(
        "Меню (лично):", reply_markup=mode_menu_kb("personal")
    )
    await callback.answer()


# ---------- FSM steps ----------
@router.message(TaskCreateFSM.waiting_title)
async def fsm_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Title пустой. Пришли нормальный title текстом.")
        return

    await state.update_data(title=title)
    await state.set_state(TaskCreateFSM.waiting_description)
    await message.answer(
        "Теперь пришли *description* (можно коротко).", parse_mode="Markdown"
    )


@router.message(TaskCreateFSM.waiting_description)
async def fsm_description(message: Message, state: FSMContext) -> None:
    description = (message.text or "").strip()
    # description можно пустым — но тогда делаем None
    if not description:
        description = None

    await state.update_data(description=description)
    await state.set_state(TaskCreateFSM.waiting_remind_at)
    await message.answer(
        "Теперь пришли время *remind_at*: например `18` или `18:30`.",
        parse_mode="Markdown",
    )


@router.message(TaskCreateFSM.waiting_remind_at)
async def fsm_remind_at(message: Message, state: FSMContext) -> None:
    remind_at = (message.text or "").strip()
    if not remind_at:
        await message.answer(
            "Время пустое. Пришли `18` или `18:30`.", parse_mode="Markdown"
        )
        return

    data = await state.get_data()

    payload = {
        "telegram_id": message.from_user.id,
        "title": data["title"],
        "description": data.get("description"),
        "remind_at": remind_at,  # backend сам нормализует через схему (18 -> 18:00)
        "username": message.from_user.username,
        "first_name": message.from_user.first_name,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{BACKEND_URL}/tasks", json=payload)

            # если время неверное, backend вернет 422 — показываем аккуратно
            if r.status_code == 422:
                await message.answer(
                    "Неверный формат времени. Пришли `18` или `18:30`.",
                    parse_mode="Markdown",
                )
                return

            r.raise_for_status()
            task = r.json()
    except httpx.RequestError:
        await message.answer("Backend недоступен 😕 Попробуй позже.")
        await state.clear()
        return
    except httpx.HTTPStatusError as e:
        await message.answer(f"Ошибка backend: {e.response.status_code}")
        await state.clear()
        return

    await state.clear()
    await message.answer(f"Task created ✅ (#{task.get('id')})")


async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Put it into bot/.env")

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
