import logging
from datetime import date
from typing import Optional, List, Tuple
import pytz
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

from bot.database.models import User, AdminHistory
from bot.keyboards.keyboards import get_main_menu_keyboard

logger = logging.getLogger(__name__)


def get_current_date(timezone_str: str) -> date:
    tz = pytz.timezone(timezone_str)
    return date.today() if not timezone_str else pytz.datetime.datetime.now(tz).date()


async def get_today_admin(session: AsyncSession, school: str, grade: str, target_date: date) -> Optional[User]:
    """Find the assigned admin for this school and grade on a given date."""
    query = (
        select(User)
        .join(AdminHistory, AdminHistory.user_id == User.id)
        .where(
            AdminHistory.school == school,
            AdminHistory.grade == grade,
            AdminHistory.assignment_date == target_date,
            User.is_active.is_(True)
        )
        .order_by(AdminHistory.id.desc())
        .limit(1)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_all_active_groups(session: AsyncSession) -> List[Tuple[str, str]]:
    """Return all unique (school, grade) pairs where there are active users."""
    query = (
        select(User.school, User.grade)
        .where(User.is_active.is_(True))
        .group_by(User.school, User.grade)
    )
    result = await session.execute(query)
    return result.all()


async def select_and_assign_admin_for_group(
    session: AsyncSession,
    school: str,
    grade: str,
    target_date: date
) -> Optional[User]:
    """Fair round-robin admin selection algorithm:
    1. Get all active users in the given school and grade.
    2. Get count of times each user has been admin, and their latest assignment date.
    3. Choose users with the minimum number of assignments.
    4. Among those, choose who hasn't been admin longest (least recent date or None).
    """
    # Check if admin already assigned today
    current = await get_today_admin(session, school, grade, target_date)
    if current:
        return current

    # Get all active users in group
    users_query = select(User).where(
        User.school == school,
        User.grade == grade,
        User.is_active.is_(True)
    )
    users_result = await session.execute(users_query)
    users = users_result.scalars().all()

    if not users:
        return None

    user_ids = [u.id for u in users]

    # Query statistics per user for fair rotation
    stats_query = (
        select(
            AdminHistory.user_id,
            func.count(AdminHistory.id).label("total_assigned"),
            func.max(AdminHistory.assignment_date).label("last_assigned")
        )
        .where(AdminHistory.user_id.in_(user_ids))
        .group_by(AdminHistory.user_id)
    )
    stats_result = await session.execute(stats_query)
    stats_map = {row.user_id: (row.total_assigned, row.last_assigned) for row in stats_result}

    # Rank users:
    # 1. total_assigned ascending (fewer times assigned is better)
    # 2. last_assigned ascending (None comes first - never assigned yet; then older dates)
    def sort_key(u: User):
        assigned_count, last_date = stats_map.get(u.id, (0, None))
        # For sorting: None date treated as earliest possible date (e.g. date.min)
        effective_date = last_date if last_date is not None else date.min
        return (assigned_count, effective_date, u.id)

    sorted_users = sorted(users, key=sort_key)
    selected_user = sorted_users[0]

    # Record assignment in database
    new_admin_history = AdminHistory(
        user_id=selected_user.id,
        assignment_date=target_date,
        school=school,
        grade=grade
    )
    session.add(new_admin_history)
    await session.flush()

    return selected_user


async def notify_admin(bot: Bot, user: User):
    """Send congratulations and instruction message to the selected daily admin."""
    text = (
        "👑 <b>Ты сегодня администратор класса!</b>\n\n"
        f"🏫 <b>Школа:</b> {user.school}\n"
        f"🎓 <b>Класс:</b> {user.grade}\n\n"
        "Сегодня отправляй боту фотографии ДЗ, расписания и важной информации.\n\n"
        "После отправки бот автоматически разошлёт информацию только ученикам твоего класса! 🚀"
    )
    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(is_admin=True)
        )
        logger.info(f"Notified admin {user.telegram_id} for {user.school} {user.grade}")
    except Exception as e:
        logger.warning(f"Could not notify admin {user.telegram_id}: {e}")


async def assign_daily_admins_job(bot: Bot, session_factory, timezone_str: str):
    """Job triggered daily by APScheduler."""
    logger.info("Starting daily admin selection job...")
    target_date = get_current_date(timezone_str)

    async with session_factory() as session:
        groups = await get_all_active_groups(session)
        logger.info(f"Found {len(groups)} active school/class groups.")

        for school, grade in groups:
            try:
                admin_user = await select_and_assign_admin_for_group(
                    session=session,
                    school=school,
                    grade=grade,
                    target_date=target_date
                )
                if admin_user:
                    await session.commit()
                    await notify_admin(bot, admin_user)
            except Exception as e:
                await session.rollback()
                logger.error(f"Error assigning admin for {school} {grade}: {e}", exc_info=True)

    logger.info("Daily admin selection job completed.")
