import asyncio
import os
import httpx

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


def mode_menu_kb(mode: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Add task", callback_data=f"task:add:{mode}")
    kb.button(text="⬅️ Back", callback_data="mode:choose")
    kb.adjust(1, 1)
    return kb.as_markup()


def mode_choose_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Лично", callback_data="mode:personal")
    kb.button(text="👥 Команда", callback_data="mode:team")
    kb.adjust(2)
    return kb.as_markup()


async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Put it into bot/.env")

    bot = Bot(token=token)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        payload = {
            "telegram_id": message.from_user.id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{BACKEND_URL}/users/upsert", json=payload)
            r.raise_for_status()

        await message.answer("Выбери режим работы:", reply_markup=mode_choose_kb())

    @dp.callback_query()
    async def on_mode(callback: CallbackQuery) -> None:
        data = callback.data or ""

        if data == "mode:personal":
            await callback.message.answer(
                "Режим: Лично ✅",
                reply_markup=mode_menu_kb("personal"),
            )

        elif data == "mode:team":
            await callback.message.answer(
                "Режим: Команда ✅",
                reply_markup=mode_menu_kb("team"),
            )

        elif data == "mode:choose":
            await callback.message.answer(
                "Выбери режим работы:",
                reply_markup=mode_choose_kb(),
            )

        elif data.startswith("task:add:"):
            mode = data.split(":")[-1]
            await callback.message.answer(
                f"Ок ✅ Создаём задачу ({mode}). Сначала пришли title."
            )

        await callback.answer()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
