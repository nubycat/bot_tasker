import asyncio
import os
import re


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


def normalize_hhmm(raw: str) -> str | None:
    s = (raw or "").strip()

    # 18 -> 18:00
    if re.fullmatch(r"\d{1,2}", s):
        h = int(s)
        if 0 <= h <= 23:
            return f"{h:02d}:00"
        return None

    # 1830 -> 18:30
    if re.fullmatch(r"\d{4}", s):
        h = int(s[:2])
        m = int(s[2:])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
        return None

    # 18:30 -> 18:30
    m1 = re.fullmatch(r"(\d{1,2}):(\d{2})", s)
    if m1:
        h = int(m1.group(1))
        m = int(m1.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
        return None

    return None


# ---------- FSM ----------
class TaskCreateFSM(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_remind_at = State()


class TeamJoin(StatesGroup):
    waiting_join_code = State()


class TeamCreateFSM(StatesGroup):
    waiting_team_name = State()
    waiting_nickname = State()


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

    if mode == "team":
        kb.button(text="👥 Мои команды", callback_data="team:my")
        kb.button(text="🔗 Код приглашения", callback_data="team:invite")

    kb.button(text="⬅️ Выбор режима", callback_data="mode:choose")

    if mode == "team":
        kb.adjust(2, 2, 1)
    else:
        kb.adjust(2, 1)

    return kb.as_markup()


def team_entry_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Мои команды", callback_data="team:my")
    kb.button(text="🔑 Войти по коду", callback_data="team:join")
    kb.button(
        text="➕ Создать команду", callback_data="team:create"
    )  # можно позже реализовать
    kb.button(text="⬅ Выбор режима", callback_data="mode:choose")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def team_work_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить задачу", callback_data="task:add:team")
    kb.button(text="📅 Задачи сегодня", callback_data="task:today:team")
    kb.button(text="👥 Мои команды", callback_data="team:my")
    kb.button(text="🔗 Код приглашения", callback_data="team:invite")
    kb.button(text="⬅️ Выбор режима", callback_data="mode:choose")
    kb.adjust(2, 2, 1)
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
        tg_id = callback.from_user.id

        # 1) сбросить активную команду в backend
        try:
            await backend_post("/teams/deactivate", params={"telegram_id": tg_id})
        except RequestError:
            await callback.message.answer("Backend недоступен 😕 Попробуй позже.")
            await callback.answer()
            return
        except HTTPStatusError as e:
            await callback.message.answer(f"Ошибка backend: {e.response.status_code}")
            await callback.answer()
            return

        # 2) показать меню личного режима
        await callback.message.answer(
            "Режим: Лично ✅", reply_markup=mode_menu_kb("personal")
        )

    elif data == "mode:team":
        # "входное" меню команд
        await callback.message.answer(
            "Командный режим: выбери действие 👇",
            reply_markup=team_entry_kb(),
        )

    elif data == "mode:choose":
        await callback.message.answer(
            "Выбери режим работы:", reply_markup=mode_choose_kb()
        )

    await callback.answer()


# +++++++++ TEAMS CONTROL MENU +++++++++
#  вход в команду
@router.callback_query(F.data == "team:join")
async def on_team_join(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TeamJoin.waiting_join_code)
    await callback.message.answer("Пришли join_code команды (код приглашения).")
    await callback.answer()


# мои команды
@router.callback_query(F.data == "team:my")
async def on_team_my(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id

    try:
        data = await backend_get("/teams/my", params={"telegram_id": tg_id})
    except RequestError:
        await callback.message.answer("Backend недоступен 😕")
        await callback.answer()
        return
    except HTTPStatusError as e:
        await callback.message.answer(f"Ошибка backend: {e.response.status_code}")
        await callback.answer()
        return

    teams = data.get("teams", [])
    if not teams:
        await callback.message.answer("Ты пока не состоишь ни в одной команде.")
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for t in teams:
        kb.button(text=t["name"], callback_data=f"team:switch:{t['id']}")
    kb.button(text="⬅ Назад", callback_data="mode:team")  # вернёмся к team_entry_kb
    kb.adjust(1)

    await callback.message.answer("Выбери команду:", reply_markup=kb.as_markup())
    await callback.answer()


# хендлер на кнопку team:create


@router.callback_query(F.data == "team:create")
async def on_team_create(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TeamCreateFSM.waiting_team_name)
    await callback.message.answer("Пришли *название команды*.", parse_mode="Markdown")
    await callback.answer()


# создание команды создание ника
@router.message(TeamCreateFSM.waiting_team_name)
async def on_team_create_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название пустое. Пришли нормальное название команды.")
        return

    await state.update_data(team_name=name)
    await state.set_state(TeamCreateFSM.waiting_nickname)
    await message.answer(
        "Теперь пришли *свой ник в команде* (например `Arsu`).", parse_mode="Markdown"
    )


# создание команды создание ника
@router.message(TeamCreateFSM.waiting_nickname)
async def on_team_create_nickname(message: Message, state: FSMContext) -> None:
    nickname = (message.text or "").strip()
    nickname = nickname.strip('"').strip("'")
    if not nickname:
        await message.answer("Ник пустой. Пришли ник текстом.")
        return

    data = await state.get_data()
    team_name = data.get("team_name")
    tg_id = message.from_user.id

    try:
        team = await backend_post(
            "/teams",
            params={"telegram_id": tg_id},
            json={"name": team_name, "nickname": nickname},
        )
    except RequestError:
        await message.answer("Backend недоступен 😕 Попробуй позже.")
        await state.clear()
        return
    except HTTPStatusError as e:
        # покажем detail если есть
        try:
            detail = e.response.json().get("detail")
        except Exception:
            detail = e.response.text
        await message.answer(f"Ошибка backend: {e.response.status_code} — {detail}")
        await state.clear()
        return

    # На всякий случай активируем созданную команду
    team_id = team.get("id")
    if team_id:
        try:
            await backend_post(
                f"/teams/{team_id}/activate", params={"telegram_id": tg_id}
            )
        except Exception:
            pass

    await state.clear()
    await message.answer(f"Команда создана ✅ {team.get('name')} (#{team_id})")
    await message.answer("Режим: Команда ✅", reply_markup=team_work_kb())


# смена активной команды
@router.callback_query(F.data.startswith("team:switch:"))
async def on_team_switch(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id
    team_id_str = (callback.data or "").split(":")[-1]

    if not team_id_str.isdigit():
        await callback.answer("Некорректный id", show_alert=True)
        return

    team_id = int(team_id_str)

    try:
        await backend_post(f"/teams/{team_id}/activate", params={"telegram_id": tg_id})
    except RequestError:
        await callback.message.answer("Backend недоступен 😕")
        await callback.answer()
        return
    except HTTPStatusError as e:
        await callback.message.answer(f"Ошибка backend: {e.response.status_code}")
        await callback.answer()
        return

    await callback.message.answer(
        "Активная команда изменена ✅",
        reply_markup=team_work_kb(),
    )
    await callback.answer()


# код приглашения
@router.callback_query(F.data == "team:invite")
async def on_team_invite(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id

    try:
        data = await backend_get(
            "/teams/active/join_code", params={"telegram_id": tg_id}
        )
    except RequestError:
        await callback.message.answer("Backend недоступен 😕")
        await callback.answer()
        return
    except HTTPStatusError as e:
        await callback.message.answer(f"Ошибка backend: {e.response.status_code}")
        await callback.answer()
        return

    join_code = data.get("join_code")
    if not join_code:
        await callback.message.answer("Backend не вернул join_code 😕")
        await callback.answer()
        return

    await callback.message.answer(
        f"Код приглашения: `{join_code}`", parse_mode="Markdown"
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


# +++++++++ HANDLERS TODAY (personal/team) +++++++++


async def render_today(message, *, tg_id: int, mode: str) -> None:
    """Рисует список Today (open/done) для personal/team."""
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
        await message.answer("Сегодня задач нет ✅", reply_markup=mode_menu_kb(mode))
        return

    kb = InlineKeyboardBuilder()

    # open
    for t in open_tasks:
        task_id = t["id"]
        title = (t.get("title") or "").strip() or "(без названия)"
        hhmm = format_due_hhmm(t["due_at"])
        kb.button(
            text=f"{hhmm} — {title}",
            callback_data=f"today_task:{mode}:{task_id}",
        )

    # done
    for t in done_tasks:
        task_id = t["id"]
        title = (t.get("title") or "").strip() or "(без названия)"
        kb.button(
            text=f"{title} | Выполнено ✅",
            callback_data=f"done_task:{mode}:{task_id}",
        )

    kb.button(text="⬅ В меню", callback_data=f"menu:{mode}")
    kb.adjust(1)

    try:
        await message.edit_text("Задачи на сегодня:", reply_markup=kb.as_markup())
    except Exception:
        await message.answer("Задачи на сегодня:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("task:today:"))
async def on_today(callback: CallbackQuery) -> None:
    mode = (callback.data or "").split(":")[-1]  # personal | team
    tg_id = callback.from_user.id

    await render_today(callback.message, tg_id=tg_id, mode=mode)
    await callback.answer()


# +++++++++ HANDLER TASK DETAILS (personal/team) +++++++++


def _parse_mode_task_id(data: str) -> tuple[str, int] | None:
    # ожидаем "today_task:{mode}:{id}" или "done_task:{mode}:{id}"
    parts = (data or "").split(":")
    if len(parts) != 3:
        return None
    mode = parts[1]
    try:
        task_id = int(parts[2])
    except ValueError:
        return None
    if mode not in ("personal", "team"):
        return None
    return mode, task_id


@router.callback_query(F.data.startswith("today_task:"))
async def on_today_task(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id

    parsed = _parse_mode_task_id(callback.data or "")
    if not parsed:
        await callback.answer()
        return
    mode, task_id = parsed

    # правильный endpoint
    path = (
        f"/tasks/personal/{task_id}" if mode == "personal" else f"/tasks/team/{task_id}"
    )

    try:
        t = await backend_get(path, params={"telegram_id": tg_id})
    except RequestError:
        await callback.message.answer("Backend недоступен 😕 Попробуй позже.")
        await callback.answer()
        return
    except HTTPStatusError as e:
        code = e.response.status_code
        if code == HTTPStatus.NOT_FOUND:
            await callback.message.answer("Задача не найдена или недоступна.")
        else:
            await callback.message.answer(f"Ошибка backend: {code}")
        await callback.answer()
        return

    title = (t.get("title") or "").strip() or "(без названия)"
    desc = (t.get("description") or "").strip() or "(без описания)"
    hhmm = format_due_hhmm(t["due_at"])
    text = f"#{t['id']}\n\n{title}\n\n{desc}\n\nВремя: {hhmm}"

    kb = InlineKeyboardBuilder()

    # действия доступны и в personal, и в team (но для team backend должен поддерживать эндпоинты)
    kb.button(text="✅ Выполнено", callback_data=f"task_done:{mode}:{task_id}")
    kb.button(text="⏭ На завтра", callback_data=f"task_tomorrow:{mode}:{task_id}")

    kb.button(text="⬅ Назад к списку", callback_data=f"task:today:{mode}")
    kb.adjust(2, 1)

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


# HANDLER TASK DONE (personal/team) click fo details
@router.callback_query(F.data.startswith("done_task:"))
async def on_done_task(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id

    parsed = _parse_mode_task_id(callback.data or "")
    if not parsed:
        await callback.answer()
        return
    mode, task_id = parsed

    path = (
        f"/tasks/personal/{task_id}" if mode == "personal" else f"/tasks/team/{task_id}"
    )

    try:
        t = await backend_get(path, params={"telegram_id": tg_id})
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

    title = (t.get("title") or "").strip() or "(без названия)"
    desc = (t.get("description") or "").strip() or "(без описания)"
    hhmm = format_due_hhmm(t["due_at"])
    text = f"#{t['id']} ✅ Выполнено\n{title}\n\n{desc}\nВремя: {hhmm}"

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ Назад к списку", callback_data=f"task:today:{mode}")
    kb.adjust(1)

    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()


# +++++++++ DONE / TOMORROW (personal) +++++++++


def _parse_mode_task_id2(data: str) -> tuple[str, int] | None:
    # ожидаем "task_done:{mode}:{id}" / "task_tomorrow:{mode}:{id}"
    parts = (data or "").split(":")
    if len(parts) != 3:
        return None
    mode = parts[1]
    try:
        task_id = int(parts[2])
    except ValueError:
        return None
    if mode not in ("personal", "team"):
        return None
    return mode, task_id


@router.callback_query(F.data.startswith("task_done:"))
async def on_task_done(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id

    parsed = _parse_mode_task_id2(callback.data or "")
    if not parsed:
        await callback.answer("Некорректный id", show_alert=True)
        return
    mode, task_id = parsed

    path = (
        f"/tasks/personal/{task_id}/done"
        if mode == "personal"
        else f"/tasks/team/{task_id}/done"
    )

    try:
        await backend_patch(path, params={"telegram_id": tg_id})
    except RequestError:
        await callback.answer("Backend недоступен 😕", show_alert=True)
        return
    except HTTPStatusError as e:
        await callback.answer(
            f"Ошибка backend: {e.response.status_code}", show_alert=True
        )
        return

    await render_today(callback.message, tg_id=tg_id, mode=mode)
    await callback.answer("Готово ✅")


# Хендлер на клик по кнопке отложить на завтра
@router.callback_query(F.data.startswith("task_tomorrow:"))
async def on_task_tomorrow(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id

    parsed = _parse_mode_task_id2(callback.data or "")
    if not parsed:
        await callback.answer("Некорректный id", show_alert=True)
        return
    mode, task_id = parsed

    path = (
        f"/tasks/personal/{task_id}/tomorrow"
        if mode == "personal"
        else f"/tasks/team/{task_id}/tomorrow"
    )

    try:
        await backend_patch(path, params={"telegram_id": tg_id})
    except RequestError:
        await callback.answer("Backend недоступен 😕", show_alert=True)
        return
    except HTTPStatusError as e:
        await callback.answer(
            f"Ошибка backend: {e.response.status_code}", show_alert=True
        )
        return

    await render_today(callback.message, tg_id=tg_id, mode=mode)
    await callback.answer("Перенёс на завтра ⏭")


# ++++++++++ MENU (personal/team) +++++++++


@router.callback_query(F.data == "menu:personal")
async def on_menu_personal(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Меню (лично):", reply_markup=mode_menu_kb("personal")
    )
    await callback.answer()


@router.callback_query(F.data == "menu:team")
async def on_menu_team(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Меню (команда):", reply_markup=team_work_kb())
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
    await message.answer("Режим: Команда ✅", reply_markup=team_work_kb())


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
    raw = (message.text or "").strip()
    remind_at = normalize_hhmm(raw)

    if not remind_at:
        await message.answer(
            "Неверный формат времени. Примеры: `18`, `18:30`, `1830`, `09:05`.",
            parse_mode="Markdown",
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
