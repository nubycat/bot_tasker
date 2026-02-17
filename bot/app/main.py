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
from aiogram.exceptions import TelegramNetworkError
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
CB_NOOP = "noop"


# ---- helpers ----
async def backend_get(path: str, *, params: dict) -> dict | list:
    """GET JSON from backend."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{BACKEND_URL}{path}", params=params)
        r.raise_for_status()
        return r.json()


async def backend_post(
    path: str, *, params: dict | None = None, json: dict | None = None
):
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(f"{BACKEND_URL}{path}", params=params, json=json)
        r.raise_for_status()
        return r.json() if r.content else {}


async def backend_patch(path: str, *, params: dict) -> dict:
    """PATCH JSON from backend."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.patch(f"{BACKEND_URL}{path}", params=params)
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


class TeamJoin(StatesGroup):
    waiting_join_code = State()


# ---------- Keyboards ----------
def mode_choose_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Лично", callback_data="mode:personal")
    kb.button(text="👥 Команда", callback_data="mode:team")
    kb.adjust(2)
    return kb.as_markup()


def mode_menu_kb(mode: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить задачу", callback_data=f"task:add:{mode}")
    kb.button(text="📅 Задачи сегодня", callback_data=f"task:today:{mode}")
    kb.button(text="⬅️ Выбор режима", callback_data="mode:choose")
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
async def on_mode(callback: CallbackQuery, state: FSMContext) -> None:
    data = callback.data or ""

    if data == "mode:personal":
        await callback.message.answer(
            "Режим: Лично ✅", reply_markup=mode_menu_kb("personal")
        )

    elif data == "mode:team":
        await state.set_state(TeamJoin.waiting_join_code)
        await callback.message.answer("Пришли join_code команды (код приглашения).")

    elif data == "mode:choose":
        await callback.message.answer(
            "Выбери режим работы:", reply_markup=mode_choose_kb()
        )

    await callback.answer()


#  создание задачи
@router.callback_query(F.data.startswith("task:add:"))
async def on_task_add(callback: CallbackQuery, state: FSMContext) -> None:
    data = callback.data or ""
    mode = data.split(":")[-1]  # personal | team

    await state.update_data(mode=mode)  # ✅ запомнили режим
    await state.set_state(TaskCreateFSM.waiting_title)

    await callback.message.answer(f"Ок ✅ Создаём задачу ({mode}). Пришли title.")
    await callback.answer()


#  Хендлер на кнопку 📅 Задачи сегодня
async def render_today(message, *, tg_id: int, mode: str) -> None:
    """Рисует список Today (open/done) в указанном message."""
    try:
        path = "/tasks/personal/today" if mode == "personal" else "/tasks/team/today"
        data = await backend_get(path, params={"telegram_id": tg_id})

    except RequestError:
        await message.answer("Backend недоступен 😕 Попробуй позже.")
        return
    except HTTPStatusError as e:
        await message.answer(f"Ошибка backend: {e.response.status_code}")
        return

    open_tasks = data.get("open", [])
    done_tasks = data.get("done", [])

    if not open_tasks and not done_tasks:
        await message.answer(
            "Сегодня задач нет ✅", reply_markup=mode_menu_kb("personal")
        )
        return

    kb = InlineKeyboardBuilder()

    # Невыполненные (с временем)
    for t in open_tasks:
        task_id = t["id"]
        title = (t.get("title") or "").strip() or "(без названия)"
        hhmm = format_due_hhmm(t["due_at"])
        kb.button(
            text=f"{hhmm} — {title}", callback_data=f"today_task:{mode}:{task_id}"
        )

    # Выполненные (коротко) — тоже кликабельные
    for t in done_tasks:
        task_id = t["id"]
        title = (t.get("title") or "").strip() or "(без названия)"
        kb.button(
            text=f"{title} | Выполнено ✅", callback_data=f"done_task:{mode}:{task_id}"
        )

    kb.button(text="⬅ В меню", callback_data="menu:personal")
    kb.adjust(1)

    try:
        await message.edit_text("Задачи на сегодня:", reply_markup=kb.as_markup())
    except Exception:
        await message.answer("Задачи на сегодня:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("task:today:"))
async def on_today(callback: CallbackQuery) -> None:
    mode = (callback.data or "").split(":")[-1]
    if mode != "personal":
        await callback.message.answer("Today пока только для личных задач ✅")
        await callback.answer()
        return

    tg_id = callback.from_user.id
    await render_today(callback.message, tg_id=tg_id)
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

    text = f"#{t['id']}\n\n{title}\n\n{desc}\n\nВремя: {hhmm}"

    # 4) Кнопки действий
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Выполненно", callback_data=f"task_done:{t['id']}")
    kb.button(text="⏭ На завтра", callback_data=f"task_tomorrow:{t['id']}")
    kb.button(text="⬅ Назад к списку", callback_data="task:today:personal")
    kb.adjust(2, 1)

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


# Хендлер на клик по выполненной задаче done_task:<id>
@router.callback_query(F.data.startswith("done_task:"))
async def on_done_task(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id

    # 1) Достаём task_id из callback_data вида "done_task:<id>"
    try:
        task_id = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer()
        return

    # 2) Запрашиваем детали задачи
    try:
        t = await backend_get(
            f"/tasks/personal/{task_id}", params={"telegram_id": tg_id}
        )
    except RequestError:
        await callback.message.answer("Backend недоступен 😕 Попробуй позже.")
        await callback.answer()
        return
    except HTTPStatusError as e:
        code = e.response.status_code
        if code == 404:
            await callback.message.answer("Задача не найдена или недоступна.")
        else:
            await callback.message.answer(f"Ошибка backend: {code}")
        await callback.answer()
        return

    # 3) Формируем карточку
    title = (t.get("title") or "").strip() or "(без названия)"
    desc = (t.get("description") or "").strip() or "(без описания)"
    hhmm = format_due_hhmm(t["due_at"])

    text = f"#{t['id']} ✅ Выполнено\n{title}\n\n{desc}\nВремя: {hhmm}"

    # 4) Только “назад к списку”
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ Назад к списку", callback_data="task:today:personal")
    kb.adjust(1)

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


# Хендлер на клик по кнопке Done
@router.callback_query(F.data.startswith("task_done:"))
async def on_task_done(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id

    try:
        task_id = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный id", show_alert=True)
        return

    try:
        await backend_patch(
            f"/tasks/personal/{task_id}/done", params={"telegram_id": tg_id}
        )
    except RequestError:
        await callback.answer("Backend недоступен 😕", show_alert=True)
        return
    except HTTPStatusError as e:
        await callback.answer(
            f"Ошибка backend: {e.response.status_code}", show_alert=True
        )
        return

    await render_today(callback.message, tg_id=tg_id)
    await callback.answer("Готово ✅")


# Хендлер на клик по кнопке отложить на завтра
@router.callback_query(F.data.startswith("task_tomorrow:"))
async def on_task_tomorrow(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id

    try:
        task_id = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный id", show_alert=True)
        return

    try:
        await backend_patch(
            f"/tasks/personal/{task_id}/tomorrow", params={"telegram_id": tg_id}
        )
    except RequestError:
        await callback.answer("Backend недоступен 😕", show_alert=True)
        return
    except HTTPStatusError as e:
        await callback.answer(
            f"Ошибка backend: {e.response.status_code}", show_alert=True
        )
        return

    # Возвращаемся к списку Today (через render_today, НЕ меняя callback.data)
    await render_today(callback.message, tg_id=tg_id)
    await callback.answer("Перенёс на завтра ⏭")


# Хендлер меню личного режима
@router.callback_query(F.data == "menu:personal")
async def on_menu_personal(callback: CallbackQuery) -> None:
    """Show personal mode menu."""
    await callback.message.edit_text(
        "Меню (лично):", reply_markup=mode_menu_kb("personal")
    )
    await callback.answer()


# Хендлер на ввод join_code
@router.message(TeamJoin.waiting_join_code)
async def on_join_code(message: Message, state: FSMContext) -> None:
    join_code = (message.text or "").strip()
    join_code = join_code.strip('"').strip("'")

    if not join_code:
        await message.answer("Код пустой. Пришли join_code текстом.")
        return

    tg_id = message.from_user.id

    # 1) join по коду -> получаем team_id
    try:
        data = await backend_post(
            "/teams/join",
            params={"telegram_id": tg_id},
            json={"join_code": join_code},
        )
    except RequestError:
        await message.answer("Backend недоступен 😕 Попробуй позже.")
        return
    except HTTPStatusError as e:
        status = e.response.status_code
        try:
            detail = e.response.json().get("detail")
        except Exception:
            detail = e.response.text

        await message.answer(f"Ошибка backend: {status} — {detail}")
        return

    team_id = data.get("team_id")
    if not team_id:
        await message.answer("Backend не вернул team_id. Проверь /teams/join.")
        return

    # 2) activate
    try:
        await backend_post(f"/teams/{team_id}/activate", params={"telegram_id": tg_id})
    except Exception:
        await message.answer("Команду нашли, но активировать не получилось 😕")
        return

    await state.clear()
    await message.answer("Режим: Команда ✅", reply_markup=mode_menu_kb("team"))


# Пустой callback: нужен для "информационных" кнопок, которые ничего не делают
@router.callback_query(F.data == CB_NOOP)
async def on_noop(callback: CallbackQuery) -> None:
    """
    Заглушка для inline-кнопок, которые не выполняют действий.

    Зачем:
    - Telegram ожидает callback.answer() на любое нажатие inline-кнопки.
      Если не ответить, у пользователя может "крутиться" загрузка.
    - Используется для кнопок-меток (например: "Done ✅", "Недоступно", "Только просмотр").

    Поведение:
    - Ничего не меняет и не отправляет сообщений.
    - Просто закрывает "ожидание" на стороне Telegram.
    """
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
        "Теперь пришли время *remind_at*: например `18` или `18:30` или `1830`.",
        parse_mode="Markdown",
    )


@router.message(TaskCreateFSM.waiting_remind_at)
async def fsm_remind_at(message: Message, state: FSMContext) -> None:
    """
    Финальный шаг FSM создания задачи:
    - берём введённое время remind_at
    - собираем payload из FSM + Telegram user
    - отправляем POST /tasks в backend
    - показываем результат и возвращаем пользователя в меню текущего режима (personal/team)
    """

    # 1) читаем время из сообщения
    remind_at = (message.text or "").strip()
    if not remind_at:
        await message.answer(
            "Время пустое. Пришли `18` или `18:30`.", parse_mode="Markdown"
        )
        return

    # 2) забираем данные, накопленные в FSM на предыдущих шагах (title/description/mode)
    data = await state.get_data()

    # 3) формируем payload для backend /tasks
    payload = {
        "telegram_id": message.from_user.id,
        "title": data["title"],
        "description": data.get("description"),
        "remind_at": remind_at,  # backend сам нормализует (18 -> 18:00)
        "username": message.from_user.username,
        "first_name": message.from_user.first_name,
    }

    # 4) отправляем запрос в backend
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{BACKEND_URL}/tasks", json=payload)

            # если формат времени неверный — backend вернёт 422
            if r.status_code == 422:
                await message.answer(
                    "Неверный формат времени. Пришли `18` или `18:30`.",
                    parse_mode="Markdown",
                )
                return

            r.raise_for_status()
            task = r.json()

    except httpx.RequestError:
        # backend недоступен (нет сети / контейнер упал / таймаут)
        await message.answer("Backend недоступен 😕 Попробуй позже.")
        await state.clear()
        return

    except httpx.HTTPStatusError as e:
        # любые 4xx/5xx кроме 422 (которые мы обработали выше)
        await message.answer(f"Ошибка backend: {e.response.status_code}")
        await state.clear()
        return

    # 5) режим берём из FSM (запомнили его при нажатии "Добавить задачу")
    mode = data.get("mode", "personal")

    # 6) сообщаем об успехе
    await message.answer(f"Задача создана ✅ (#{task.get('id')})")

    # 7) возвращаем пользователя в меню того режима, где он создавал задачу
    await message.answer(
        f"Режим: {'Команда' if mode == 'team' else 'Лично'} ✅",
        reply_markup=mode_menu_kb(mode),
    )

    # 8) чистим FSM ОДИН раз в самом конце
    await state.clear()


async def wait_telegram(bot: Bot, tries: int = 10) -> None:
    for _ in range(tries):
        try:
            await bot.get_me(request_timeout=20)
            return
        except TelegramNetworkError:
            await asyncio.sleep(2)
    await bot.get_me(request_timeout=20)


async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Put it into bot/.env")

    bot = Bot(token=token)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await wait_telegram(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
