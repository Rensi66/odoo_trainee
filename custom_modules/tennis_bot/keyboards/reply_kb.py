from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def register_reply_kb():
    kb = [
        [KeyboardButton(text="Register", request_contact=True)],
    ]

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)