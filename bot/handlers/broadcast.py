import logging
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from bot.database.db import get_session
from bot.database.models import User
from bot.keyboards.keyboards import (
    get_main_menu_keyboard,
    get_post_type_keyboard,
    get_broadcast_confirmation_keyboard
)
from bot.services.admin_service import get_today_admin, get_current_date
from bot.services.broadcast_service import broadcast_to_class
from bot.config import load_config

logger = logging.getLogger(__name__)
router = Router()


class BroadcastFlow(StatesGroup):
    waiting_category = State()
    waiting_confirmation = State()


@router.message(F.photo | (F.text & ~F.text.startswith("/") & ~F.text.in_([
    "📚 ДЗ", "🗓️ Расписание", "📢 Объявления", "👤 Мой профиль", "🔄 Изменить данные", "❌ Отмена"
]) & ~F.text.startswith("👑 Администратор дня")))
async def handle_potential_broadcast(message: Message, state: FSMContext):
    # Verify sender registration and admin rights
    async with get_session() as session:
        res = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = res.scalar_one_or_none()

        if not user:
            await message.answer("⚠️ Вы ещё не зарегистрированы! Отправьте /start.")
            return

        cfg = load_config()
        today = get_current_date(cfg.TIMEZONE)
        admin = await get_today_admin(session, user.school, user.grade, today)

        if not admin or admin.id != user.id:
            await message.answer(
                "ℹ️ <i>Публиковать материалы для класса может только назначенный администратор дня.</i>\n\n"
                f"Текущий администратор: <b>{admin.first_name + ' ' + admin.last_name if admin else 'Не назначен'}</b>",
                parse_mode="HTML"
            )
            return

    # User IS current admin
    photo_id = message.photo[-1].file_id if message.photo else None
    content_text = message.caption if message.photo else message.text

    await state.update_data(
        photo_id=photo_id,
        content_text=content_text
    )

    await message.answer(
        "📝 <b>Выберите категорию сообщения:</b>",
        parse_mode="HTML",
        reply_markup=get_post_type_keyboard()
    )
    await state.set_state(BroadcastFlow.waiting_category)


@router.callback_query(BroadcastFlow.waiting_category, F.data.startswith("category:"))
async def choose_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":")[1]
    await state.update_data(category=category)

    async with get_session() as session:
        res = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = res.scalar_one_or_none()

    data = await state.get_data()
    content_preview = data.get("content_text") or "(только изображение)"
    has_photo = bool(data.get("photo_id"))

    confirm_msg = (
        f"📤 <b>Отправить это сообщение ученикам?</b>\n\n"
        f"🏫 <b>Школа:</b> {user.school}\n"
        f"🎓 <b>Класс:</b> {user.grade}\n"
        f"📁 <b>Категория:</b> {category}\n"
        f"🖼️ <b>Вложение:</b> {'Да (Фото)' if has_photo else 'Нет'}\n"
        f"📄 <b>Текст:</b>\n<i>{content_preview[:300]}</i>"
    )

    await callback.message.edit_text(
        confirm_msg,
        parse_mode="HTML",
        reply_markup=get_broadcast_confirmation_keyboard()
    )
    await state.set_state(BroadcastFlow.waiting_confirmation)
    await callback.answer()


@router.callback_query(F.data == "broadcast_cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Публикация отменена.")
    await callback.answer()


@router.callback_query(BroadcastFlow.waiting_confirmation, F.data == "broadcast_confirm")
async def confirm_and_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.edit_text("⏳ <i>Выполняется рассылка ученикам вашего класса...</i>", parse_mode="HTML")

    data = await state.get_data()
    category = data.get("category", "Информация")
    content_text = data.get("content_text")
    photo_id = data.get("photo_id")

    async with get_session() as session:
        res = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        sender = res.scalar_one_or_none()

        if not sender:
            await callback.message.answer("Ошибка: пользователь не найден.")
            await state.clear()
            return

        stats = await broadcast_to_class(
            bot=bot,
            session=session,
            sender=sender,
            category=category,
            text_content=content_text,
            photo_file_id=photo_id
        )

    await state.clear()

    await callback.message.answer(
        "✅ <b>Рассылка успешно завершена!</b>\n\n"
        f"🏫 <b>Группа:</b> {sender.school} | {sender.grade}\n"
        f"👥 Всего учеников в классе: <b>{stats['total']}</b>\n"
        f"📨 Успешно доставлено: <b>{stats['sent']}</b>\n"
        f"⚠️ Ошибок доставки: <b>{stats['failed']}</b>",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(is_admin=True)
    )
    await callback.answer()
