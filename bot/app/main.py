import asyncio
import os

import httpx
from httpx import RequestError, HTTPStatusError
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
    kb.button(text="⬅️ Back", callback_data="mode:choose")
    kb.adjust(1, 1)
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


@router.callback_query(F.data.startswith("task:add:"))
async def on_task_add(callback: CallbackQuery, state: FSMContext) -> None:
    # mode пока просто запомним (на будущее)
    mode = (callback.data or "").split(":")[-1]
    await state.update_data(mode=mode)

    # старт FSM
    await state.set_state(TaskCreateFSM.waiting_title)
    await callback.message.answer(
        f"Ок ✅ Создаём задачу ({mode}). Пришли *title*.", parse_mode="Markdown"
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
