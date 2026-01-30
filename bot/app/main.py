import asyncio
import os

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

load_dotenv()


async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Put it into bot/.env")

    bot = Bot(token=token)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        kb = InlineKeyboardBuilder()
        kb.button(text="👤 Лично", callback_data="mode:personal")
        kb.button(text="👥 Команда", callback_data="mode:team")
        kb.adjust(2)
        await message.answer("Выбери режим работы:", reply_markup=kb.as_markup())

    @dp.callback_query()
    async def on_mode(callback: CallbackQuery) -> None:
        data = callback.data or ""
        if data == "mode:personal":
            await callback.message.answer("Ок! Режим: Лично ✅")
        elif data == "mode:team":
            await callback.message.answer("Ок! Режим: Команда ✅")
        await callback.answer()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
