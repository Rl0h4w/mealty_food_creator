import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.bot import DefaultBotProperties  # Import DefaultBotProperties

from config import API_TOKEN, LOGGING_LEVEL, LOGGING_FORMAT
from handlers import router

async def main():
    # Configure logging
    logging.basicConfig(
        level=LOGGING_LEVEL,
        format=LOGGING_FORMAT
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting bot...")

    # Initialize Bot with DefaultBotProperties
    bot = Bot(
        token=API_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")  # Use default parameter
    )

    # Initialize Dispatcher
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Bot stopped.")

if __name__ == '__main__':
    asyncio.run(main())
