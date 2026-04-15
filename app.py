import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.middlewares.request_logging import logger

from loader import db, cache


def setup_handlers(dispatcher: Dispatcher) -> None:
    from handlers import setup_routers
    dispatcher.include_router(setup_routers())


def setup_middlewares(dispatcher: Dispatcher) -> None:
    from middlewares.throttling import ThrottlingMiddleware
    dispatcher.message.middleware(ThrottlingMiddleware(slow_mode_delay=0.5))


async def setup_aiogram(dispatcher: Dispatcher, bot: Bot) -> None:
    logger.info("Configuring aiogram")
    setup_handlers(dispatcher=dispatcher)
    setup_middlewares(dispatcher=dispatcher)
    logger.info("Configured aiogram")


async def on_startup(dispatcher: Dispatcher, bot: Bot) -> None:
    from utils.notify_admins import on_startup_notify
    from utils.set_bot_commands import set_default_commands

    await db.create()
    await db.create_tables()
    logger.info("Database connected and tables created")

    await cache.connect()

    await bot.delete_webhook(drop_pending_updates=True)
    await setup_aiogram(bot=bot, dispatcher=dispatcher)
    await on_startup_notify(bot=bot)
    await set_default_commands(bot=bot)
    logger.info("Bot started")


async def on_shutdown(dispatcher: Dispatcher, bot: Bot):
    logger.info("Stopping bot")
    await cache.close()
    await bot.session.close()
    await dispatcher.storage.close()


def main():
    from loader import bot, dispatcher

    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    asyncio.run(dispatcher.start_polling(bot, close_bot_session=True))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped!")
