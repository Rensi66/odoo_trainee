from aiogram import Router, types
from aiogram.filters import Command

from handlers.odoo_client import odoo

from keyboards import reply_kb
from keyboards import inline_kb


common_router = Router()

@common_router.message(Command("start"))
async def cmn_start(message: types.Message):
    partner_ids = odoo.execute("res.partner", "search", [["tg_chat_id", "=", str(message.chat.id)]])

    if not partner_ids:
        await message.answer("""
        Welcome to World of Tennis! To link your account to our centers, please provide your phone number.""",
        reply_markup=reply_kb.register_reply_kb())
    else:
        partner_name = odoo.execute("res.partner", "read", [partner_ids[0]], ["name"])
        await message.answer(f"Welcome, {partner_name[0]['name']}!")
        await message.answer("Select the section that interests you.",
                             reply_markup=inline_kb.inline_kb())

