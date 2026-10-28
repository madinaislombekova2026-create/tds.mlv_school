import logging
import re
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from sqlalchemy import select

from bot.database.db import get_session
from bot.database.models import User
from bot.keyboards.keyboards import (
    get_main_menu_keyboard,
    get_cancel_reply_keyboard,
    get_grade_numbers_inline_keyboard,
    get_grade_letters_inline_keyboard,
    VALID_GRADES
)
from bot.services.admin_service import get_today_admin, get_current_date, select_and_assign_admin_for_group
from bot.config import load_config

logger = logging.getLogger(__name__)
router = Router()


class RegistrationState(StatesGroup):
    waiting_first_name = State()
    waiting_last_name = State()
    waiting_school = State()
    waiting_grade = State()


GRADE_PATTERN = re.compile(r"^(5|6|7|8|9|10|11)[-–—\s]?([А-Яа-яA-Za-z])$")


def clean_grade(raw: str) -> str | None:
    raw = raw.strip().upper()
    match = GRADE_PATTERN.match(raw)
    if not match:
        return None
    num, letter = match.groups()
    # Map latin letters to Cyrillic if typed accidentally
    latin_to_cyr = {"A": "А", "B": "В", "C": "С", "E": "Е", "H": "Н", "K": "К", "M": "М", "O": "О", "P": "Р", "T": "Т", "X": "Х"}
    letter = latin_to_cyr.get(letter, letter)
    return f"{num}-{letter}"


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    await state.clear()
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if user:
            cfg = load_config()
            today = get_current_date(cfg.TIMEZONE)
            current_admin = await get_today_admin(session, user.school, user.grade, today)
            is_admin = (current_admin is not None and current_admin.id == user.id)

            await message.answer(
                f"👋 С возвращением, {user.first_name}!\n\n"
                f"🏫 <b>Школа:</b> {user.school}\n"
                f"🎓 <b>Класс:</b> {user.grade}\n\n"
                f"{'👑 <i>Вы сегодня являетесь администратором класса!</i>' if is_admin else 'Пользуйтесь меню ниже:'}",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard(is_admin=is_admin)
            )
            return

    # User is not registered
    await message.answer(
        "👋 <b>Добро пожаловать в Школьный бот!</b>\n\n"
        "Бот объединяет учеников одного класса, позволяет делиться расписанием, ДЗ "
        "и объявлениями через ежедневного дежурного администратора.\n\n"
        "Для начала давай пройдем быструю регистрацию.\n"
        "👉 <b>Введите ваше имя:</b>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RegistrationState.waiting_first_name)


@router.message(F.text == "🔄 Изменить данные")
async def handle_re_register(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔄 <b>Обновление данных профиля</b>\n\n"
        "Введите ваше <b>Имя</b> (или нажмите «❌ Отмена»):",
        parse_mode="HTML",
        reply_markup=get_cancel_reply_keyboard()
    )
    await state.set_state(RegistrationState.waiting_first_name)


@router.message(RegistrationState.waiting_first_name)
async def process_first_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=get_main_menu_keyboard())
        return

    first_name = message.text.strip()
    if len(first_name) < 2 or len(first_name) > 50:
        await message.answer("⚠️ Имя должно содержать от 2 до 50 символов. Попробуйте еще раз:")
        return

    await state.update_data(first_name=first_name)
    await message.answer("Отлично! Теперь введите вашу <b>Фамилию</b>:", parse_mode="HTML")
    await state.set_state(RegistrationState.waiting_last_name)


@router.message(RegistrationState.waiting_last_name)
async def process_last_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=get_main_menu_keyboard())
        return

    last_name = message.text.strip()
    if len(last_name) < 2 or len(last_name) > 50:
        await message.answer("⚠️ Фамилия должна содержать от 2 до 50 символов. Попробуйте еще раз:")
        return

    await state.update_data(last_name=last_name)
    await message.answer(
        "🏫 Введите номер или название вашей <b>Школы</b>\n"
        "<i>Например: Школа №179 или Лицей №1</i>",
        parse_mode="HTML"
    )
    await state.set_state(RegistrationState.waiting_school)


@router.message(RegistrationState.waiting_school)
async def process_school(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=get_main_menu_keyboard())
        return

    school = message.text.strip()
    if len(school) < 2 or len(school) > 100:
        await message.answer("⚠️ Название школы должно быть от 2 до 100 символов. Попробуйте снова:")
        return

    await state.update_data(school=school)
    await message.answer(
        "🎓 <b>Выберите ваш класс</b> (только 5–11 классы):\n"
        "Вы можете нажать кнопку ниже или написать сообщением (например, <b>8-А</b> или <b>10-Б</b>):",
        parse_mode="HTML",
        reply_markup=get_grade_numbers_inline_keyboard()
    )
    await state.set_state(RegistrationState.waiting_grade)


@router.callback_query(RegistrationState.waiting_grade, F.data.startswith("grade_num:"))
async def process_grade_number_callback(callback: CallbackQuery, state: FSMContext):
    grade_num = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        f"Выбран {grade_num} класс. Теперь выберите букву:",
        reply_markup=get_grade_letters_inline_keyboard(grade_num)
    )
    await callback.answer()


@router.callback_query(RegistrationState.waiting_grade, F.data == "grade_back")
async def process_grade_back_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🎓 <b>Выберите ваш класс</b> (5–11 классы):",
        parse_mode="HTML",
        reply_markup=get_grade_numbers_inline_keyboard()
    )
    await callback.answer()


@router.callback_query(RegistrationState.waiting_grade, F.data.startswith("grade_set:"))
async def process_grade_set_callback(callback: CallbackQuery, state: FSMContext):
    grade = callback.data.split(":")[1]
    await finalize_registration(callback.message, state, callback.from_user.id, grade, is_callback=True)
    await callback.answer()


@router.message(RegistrationState.waiting_grade)
async def process_grade_text(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=get_main_menu_keyboard())
        return

    raw_grade = message.text.strip()
    cleaned = clean_grade(raw_grade)

    if not cleaned:
        await message.answer(
            "⚠️ <b>Неверный формат класса!</b>\n"
            "Разрешены только классы с 5 по 11 (классы 1–4 не поддерживаются).\n\n"
            "Примеры: <code>5-А</code>, <code>8-Б</code>, <code>11-В</code>.\n"
            "Попробуйте написать снова или выберите кнопками выше:",
            parse_mode="HTML"
        )
        return

    await finalize_registration(message, state, message.from_user.id, cleaned, is_callback=False)


async def finalize_registration(
    message: Message,
    state: FSMContext,
    telegram_id: int,
    grade: str,
    is_callback: bool = False
):
    data = await state.get_data()
    first_name = data["first_name"]
    last_name = data["last_name"]
    school = data["school"]

    async with get_session() as session:
        # Check if user already exists
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user:
            user.first_name = first_name
            user.last_name = last_name
            user.school = school
            user.grade = grade
            user.is_active = True
        else:
            user = User(
                telegram_id=telegram_id,
                first_name=first_name,
                last_name=last_name,
                school=school,
                grade=grade,
                is_active=True
            )
            session.add(user)

        await session.flush()

        # If this class currently has no admin today, assign this user immediately!
        cfg = load_config()
        today = get_current_date(cfg.TIMEZONE)
        today_admin = await get_today_admin(session, school, grade, today)
        is_admin = False

        if not today_admin:
            assigned = await select_and_assign_admin_for_group(session, school, grade, today)
            if assigned and assigned.id == user.id:
                is_admin = True
        elif today_admin.id == user.id:
            is_admin = True

        await session.commit()

    await state.clear()

    congrats_text = (
        "🎉 <b>Регистрация успешно завершена!</b>\n\n"
        f"👤 <b>Ученик:</b> {first_name} {last_name}\n"
        f"🏫 <b>Школа:</b> {school}\n"
        f"🎓 <b>Класс:</b> {grade}\n\n"
    )

    if is_admin:
        congrats_text += (
            "👑 <b>Ты сегодня назначен администратором своего класса!</b>\n"
            "Отправляй в этот чат фотографии ДЗ, расписание или школьные объявления — "
            "бот автоматически перешлет их всем одноклассникам!"
        )
    else:
        congrats_text += (
            "Теперь ты будешь получать всё актуальное расписание, ДЗ и объявления "
            "от дежурного администратора твоего класса."
        )

    if is_callback:
        await message.edit_text(congrats_text, parse_mode="HTML")
        await message.answer("Главное меню готово к работе:", reply_markup=get_main_menu_keyboard(is_admin=is_admin))
    else:
        await message.answer(congrats_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard(is_admin=is_admin))
