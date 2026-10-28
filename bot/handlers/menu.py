import logging
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select

from bot.database.db import get_session
from bot.database.models import User, SchoolMessage
from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.services.admin_service import get_today_admin, get_current_date
from bot.config import load_config

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text.startswith("👑 Администратор дня"))
async def show_today_admin(message: Message):
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("⚠️ Пожалуйста, сначала зарегистрируйтесь: /start")
            return

        cfg = load_config()
        today = get_current_date(cfg.TIMEZONE)
        admin = await get_today_admin(session, user.school, user.grade, today)

        if not admin:
            text = (
                f"🏫 <b>{user.school} | {user.grade}</b>\n\n"
                "На сегодня администратор ещё не определен.\n"
                "Система назначит его автоматически."
            )
            await message.answer(text, parse_mode="HTML")
            return

        is_me = (admin.id == user.id)
        if is_me:
            text = (
                f"🏫 <b>{user.school} | {user.grade}</b>\n\n"
                "👑 <b>Сегодня администратор ВЫ!</b> 🎉\n\n"
                "Отправляйте боту фотографии с доски, расписание, ДЗ или важные объявления. "
                "После подтверждения они мгновенно отправятся вашим одноклассникам."
            )
        else:
            text = (
                f"🏫 <b>{user.school} | {user.grade}</b>\n\n"
                f"👑 <b>Администратор дня:</b> {admin.first_name} {admin.last_name}\n\n"
                "Сегодня этот ученик отвечает за публикацию домашнего задания, "
                "расписания и объявлений для вашего класса."
            )

        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard(is_admin=is_me))


@router.message(F.text.in_(["📚 ДЗ", "🗓️ Расписание", "📢 Объявления"]))
async def show_last_category_content(message: Message):
    category_map = {
        "📚 ДЗ": "ДЗ",
        "🗓️ Расписание": "Расписание",
        "📢 Объявления": "Объявление"
    }
    category = category_map[message.text]

    async with get_session() as session:
        res = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = res.scalar_one_or_none()

        if not user:
            await message.answer("⚠️ Пожалуйста, сначала зарегистрируйтесь: /start")
            return

        cfg = load_config()
        today = get_current_date(cfg.TIMEZONE)
        admin = await get_today_admin(session, user.school, user.grade, today)
        is_admin = (admin is not None and admin.id == user.id)

        # Get latest message for this category, school, and grade
        msg_query = (
            select(SchoolMessage)
            .where(
                SchoolMessage.school == user.school,
                SchoolMessage.grade == user.grade,
                SchoolMessage.category == category
            )
            .order_by(SchoolMessage.sent_at.desc())
            .limit(1)
        )
        msg_res = await session.execute(msg_query)
        last_msg = msg_res.scalar_one_or_none()

        if not last_msg:
            hint = ""
            if is_admin:
                hint = "\n\n💡 <i>Как администратор, просто пришлите фото или текст прямо сюда, чтобы опубликовать!</i>"
            await message.answer(
                f"📭 В категории «{message.text}» для <b>{user.school} | {user.grade}</b> пока нет свежих записей.{hint}",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard(is_admin=is_admin)
            )
            return

        caption = (
            f"{message.text} для <b>{user.school} | {user.grade}</b>\n"
            f"📅 Опубликовано: {last_msg.sent_at.strftime('%d.%m.%Y %H:%M')}\n"
            "────────────────────\n"
            f"{last_msg.text_content or ''}"
        )

        if last_msg.photo_file_id:
            await message.answer_photo(
                photo=last_msg.photo_file_id,
                caption=caption[:1024],
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard(is_admin=is_admin)
            )
        else:
            await message.answer(
                caption[:4096],
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard(is_admin=is_admin)
            )
