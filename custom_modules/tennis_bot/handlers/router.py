from aiogram import F, Router, types
from aiogram.types import ReplyKeyboardRemove

from datetime import datetime
from handlers.odoo_client import odoo
from zoneinfo import ZoneInfo

from keyboards import inline_kb

router = Router()


@router.message(F.contact)
async def get_contact(message: types.Message):
    contact = message.contact.phone_number

    clean_prone = contact.replace("+", "")

    partner_ids = odoo.execute("res.partner", "search", [["phone", 'ilike', clean_prone]])

    if partner_ids:
        partner_data = odoo.execute("res.partner", "read", [partner_ids[0]], ["name"])
        partner_name = partner_data[0]["name"]

        odoo.execute("res.partner", "write", [partner_ids[0]], {"tg_chat_id": str(message.chat.id)})

        await message.answer(f"Welcome, {partner_name}!",
                            reply_markup = ReplyKeyboardRemove())

        await message.answer("Select the section that interests you.",
                             reply_markup=inline_kb.inline_kb())
    else:
        await message.answer("Your account was not found. To verify your information, please call the center manager.")

@router.callback_query(F.data == "my_balance")
async def get_balance(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id

    balance = odoo.execute("res.partner", "search_read", [["tg_chat_id", "=", str(chat_id)]], ["tennis_balance"])

    if balance:
        await callback_query.message.answer(f"Your Balance in the Sports Network: {balance[0]['tennis_balance']}.",
                                    reply_markup=inline_kb.inline_kb())
        await callback_query.answer()
    else:
        await callback_query.message.answer("You have not yet set up a balance. To do so, please contact a manager.",
                                            reply_markup=inline_kb.inline_kb())
        await callback_query.answer()

@router.callback_query(F.data == "my_training")
async def get_training(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id

    partner_ids = odoo.execute("res.partner", "search_read", [["tg_chat_id", "=", str(chat_id)]], ["tz"])

    server_local_datetime_utc = datetime.now().astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


    training_ids = odoo.execute("tennis.training", "search_read", [["client_ids", "in", partner_ids[0]["id"]], ["start_datetime", ">", server_local_datetime_utc]],
                                ["center_id", "court", "tennis_coach_id", "start_datetime"], 0, 5, "start_datetime asc")

    if not training_ids:
        await callback_query.message.answer("You have no upcoming trainings.", reply_markup=inline_kb.inline_kb())
        await callback_query.answer()
        return

    response = "📋 Your upcoming trainings:\n\n"
    for training in training_ids:
        center = training["center_id"][1] if training["center_id"] else "Not specified"
        coach = training["tennis_coach_id"][1] if training["tennis_coach_id"] else "Without a Coach"
        court_key = training.get("court")
        court = "Court " + court_key.replace("court_", "") if court_key else "Not specified"

        utc_datetime = datetime.strptime(training["start_datetime"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=ZoneInfo("UTC"))
        local_user_datetime = utc_datetime.astimezone(ZoneInfo(partner_ids[0]["tz"] or 'UTC'))
        start_datetime = local_user_datetime.strftime("%d.%m.%Y %H:%M")

        response += f"🏢 Center: {center}\n🎾 Court: {court}\n👤 Coach: {coach}\n📅 Date/Time: {start_datetime}\n\n"

    await callback_query.message.answer(response, reply_markup=inline_kb.inline_kb())
    await callback_query.answer()













