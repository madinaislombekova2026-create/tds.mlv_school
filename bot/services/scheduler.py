import logging
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from bot.database.db import _session_factory
from bot.services.admin_service import assign_daily_admins_job

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def setup_scheduler(bot: Bot, timezone_str: str) -> AsyncIOScheduler:
    global _scheduler
    tz = pytz.timezone(timezone_str)
    _scheduler = AsyncIOScheduler(timezone=tz)

    # Schedule daily at 07:00 AM local time
    _scheduler.add_job(
        assign_daily_admins_job,
        trigger=CronTrigger(hour=7, minute=0, timezone=tz),
        args=[bot, _session_factory, timezone_str],
        id="daily_admin_rotation",
        replace_existing=True
    )
    logger.info(f"Scheduled daily admin rotation for 07:00 AM ({timezone_str})")
    return _scheduler


def start_scheduler():
    global _scheduler
    if _scheduler and not _scheduler.running:
        _scheduler.start()
        logger.info("APScheduler started successfully.")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")
