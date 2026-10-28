import logging
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select, func

from bot.database.db import get_session
from bot.database.models import User, AdminHistory
from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.services.admin_service import get_today_admin, get_current_date
from bot.config import load_config

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: Message):
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("⚠️ Вы ещё не зарегистрированы! Отправьте /start для регистрации.")
            return

        # Count total times assigned as admin
        admin_count_res = await session.execute(
            select(func.count(AdminHistory.id)).where(AdminHistory.user_id == user.id)
        )
        admin_count = admin_count_res.scalar() or 0

        # Check today's admin status
        cfg = load_config()
        today = get_current_date(cfg.TIMEZONE)
        today_admin = await get_today_admin(session, user.school, user.grade, today)
        is_today_admin = (today_admin is not None and today_admin.id == user.id)

        status_line = "👑 <b>Статус сегодня:</b> Администратор класса! ⭐" if is_today_admin else "🎓 <b>Статус:</b> Ученик"

        profile_text = (
            "👤 <b>Ваш профиль:</b>\n"
            "────────────────────\n"
            f"👤 <b>Имя и фамилия:</b> {user.first_name} {user.last_name}\n"
            f"🏫 <b>Школа:</b> {user.school}\n"
            f"🎓 <b>Класс:</b> {user.grade}\n"
            f"👑 <b>Назначений администратором:</b> {admin_count}\n"
            f"{status_line}\n"
            f"📅 <b>Дата регистрации:</b> {user.registered_at.strftime('%d.%m.%Y')}\n"
            "────────────────────\n"
            "💡 <i>Если данные изменились, нажмите «🔄 Изменить данные».</i>"
        )

        await message.answer(
            profile_text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(is_admin=is_today_admin)
        )
