import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, Response, status
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import Config
from bot.database.db import setup_db, init_db, close_db
from bot.handlers import registration_router, profile_router, menu_router, broadcast_router
from bot.services.scheduler import setup_scheduler, start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


def create_app(config: Config) -> FastAPI:
    # Initialize bot and dispatcher
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Include handler routers in clear sequence
    dp.include_router(registration_router)
    dp.include_router(profile_router)
    dp.include_router(menu_router)
    dp.include_router(broadcast_router)

    # Lifespan context for startup and shutdown
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Initializing database connection...")
        setup_db(config.DATABASE_URL)
        await init_db()
        logger.info("Database schemas initialized.")

        # Setup scheduler
        setup_scheduler(bot, config.TIMEZONE)
        start_scheduler()

        # Setup Webhook with Telegram
        webhook_target = config.full_webhook_url
        logger.info(f"Setting Telegram webhook to: {webhook_target}")
        await bot.set_webhook(
            url=webhook_target,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=False
        )
        logger.info("Telegram webhook set successfully.")

        yield

        # Shutdown sequence
        logger.info("Shutting down bot application...")
        stop_scheduler()
        try:
            await bot.delete_webhook()
            logger.info("Webhook deleted.")
        except Exception as e:
            logger.warning(f"Error deleting webhook: {e}")
        await bot.session.close()
        await close_db()
        logger.info("Shutdown completed.")

    app = FastAPI(title="School Telegram Bot", lifespan=lifespan)

    @app.get("/health", status_code=status.HTTP_200_OK)
    async def health_check():
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "school-telegram-bot"
        }

    @app.post(config.WEBHOOK_PATH)
    async def telegram_webhook(request: Request) -> Response:
        try:
            data = await request.json()
            update = Update.model_validate(data, context={"bot": bot})
            await dp.feed_update(bot=bot, update=update)
            return Response(status_code=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error processing update: {e}", exc_info=True)
            return Response(status_code=status.HTTP_200_OK) # Always respond 200 OK to Telegram

    return app
