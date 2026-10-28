from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

VALID_GRADES = [5, 6, 7, 8, 9, 10, 11]
VALID_LETTERS = ["А", "Б", "В", "Г", "Д", "Е"]


def get_main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    admin_star = " ⭐ (Вы админ)" if is_admin else ""
    keyboard = [
        [
            KeyboardButton(text="📚 ДЗ"),
            KeyboardButton(text="🗓️ Расписание")
        ],
        [
            KeyboardButton(text="📢 Объявления"),
            KeyboardButton(text=f"👑 Администратор дня{admin_star}")
        ],
        [
            KeyboardButton(text="👤 Мой профиль"),
            KeyboardButton(text="🔄 Изменить данные")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие из меню..."
    )


def get_cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_grade_numbers_inline_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row1 = [InlineKeyboardButton(text=f"{g} класс", callback_data=f"grade_num:{g}") for g in [5, 6, 7, 8]]
    row2 = [InlineKeyboardButton(text=f"{g} класс", callback_data=f"grade_num:{g}") for g in [9, 10, 11]]
    buttons.append(row1)
    buttons.append(row2)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_grade_letters_inline_keyboard(grade_num: int) -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton(text=f"{grade_num}-{letter}", callback_data=f"grade_set:{grade_num}-{letter}")
        for letter in ["А", "Б", "В"]
    ]
    row2 = [
        InlineKeyboardButton(text=f"{grade_num}-{letter}", callback_data=f"grade_set:{grade_num}-{letter}")
        for letter in ["Г", "Д", "Е"]
    ]
    row_back = [InlineKeyboardButton(text="⬅️ Назад к выбору цифры", callback_data="grade_back")]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2, row_back])


def get_broadcast_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")
            ]
        ]
    )


def get_post_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📚 Домашнее задание", callback_data="category:ДЗ"),
                InlineKeyboardButton(text="🗓️ Расписание", callback_data="category:Расписание")
            ],
            [
                InlineKeyboardButton(text="📢 Объявление", callback_data="category:Объявление"),
                InlineKeyboardButton(text="📝 Изменения", callback_data="category:Изменения")
            ],
            [
                InlineKeyboardButton(text="📸 Фото с доски", callback_data="category:Доска")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")
            ]
        ]
    )
