from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def yes_no_inline_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да", callback_data="yes"),
            InlineKeyboardButton(text="Нет", callback_data="no")
        ]
    ])
    return keyboard

def gender_inline_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Мужской", callback_data="gender_male"),
            InlineKeyboardButton(text="Женский", callback_data="gender_female")
        ]
    ])
    return keyboard

def activity_level_inline_keyboard() -> InlineKeyboardMarkup:
    levels = [
        ("1. Сидячий образ жизни", "activity_sedentary"),
        ("2. Лёгкая активность", "activity_light"),
        ("3. Средняя активность", "activity_moderate"),
        ("4. Высокая активность", "activity_high"),
        ("5. Очень высокая активность", "activity_extra"),
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=callback)] for text, callback in levels
    ])
    return keyboard

def goal_inline_keyboard() -> InlineKeyboardMarkup:
    goals = [
        ("Похудение", "goal_lose_weight"),
        ("Поддержание веса", "goal_maintain_weight"),
        ("Набор массы", "goal_gain_weight")
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=callback)] for text, callback in goals
    ])
    return keyboard

def confirm_inline_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Принимаю", callback_data="accept"),
            InlineKeyboardButton(text="Отклоняю", callback_data="reject")
        ]
    ])
    return keyboard
