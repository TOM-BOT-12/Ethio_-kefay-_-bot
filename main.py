import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from dotenv import load_dotenv

from database import create_db, add_user

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(commands=["start"])
async def start(message: Message):
    await add_user(
        message.from_user.id,
        message.from_user.username
    )

    await message.answer(
        "👋 እንኳን ወደ Referral Bot በደህና መጡ!\n\n"
        "ነጥብ ለማግኘት ጓደኞችዎን ይጋብዙ።"
    )


async def main():
    await create_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
