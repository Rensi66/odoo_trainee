import asyncio
from aiogram import Bot, Dispatcher
import config

from handlers.common import common_router
from handlers.router import router


async def main():
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    dp.include_routers(common_router, router)

    await dp._polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

