from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def inline_kb():
    kb = [
        [InlineKeyboardButton(text="My trainings", callback_data="my_training"),
         InlineKeyboardButton(text="My balance", callback_data="my_balance")],
    ]

    return InlineKeyboardMarkup(inline_keyboard=kb)


