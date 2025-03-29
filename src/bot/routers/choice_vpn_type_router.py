from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram import F, Router

from bot.keyboards.keyboards import (
    get_choice_vpn_type_keyboard,
    get_diff_protocol_keyboard,
)
from bot.fsm.states import GetKey, ManageKeys, AdminAccess
from bot.lexicon.lexicon import INFO

import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(
    StateFilter(ManageKeys.no_active_keys), F.data.in_(["get_keys_pressed"])
)
@router.callback_query(
    F.data.in_(["choice_vpn_type", "back_to_choice_vpn_type", "admin_choice_vpn_type"])
)
async def choice_vpn_type(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prev_state = data.get("prev_state")
    current_state = await state.get_state()

    if not current_state:
        current_state = prev_state
    if callback.data in ["admin_choice_vpn_type"]:
        await state.set_state(AdminAccess.admin_choosing_vpn_protocol_type)
    else:
        await state.set_state(GetKey.choosing_vpn_protocol_type)

    await callback.message.edit_text(
        "Выберите тип подключения:\n\n",
        reply_markup=get_choice_vpn_type_keyboard(current_state),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "protocol_diff")
async def protocol_diff_handler(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    await state.update_data(prev_state=current_state)
    await callback.message.edit_text(
        str(f"{INFO.WHAT_TO_CHOOSE.value}"),
        parse_mode="HTML",
        reply_markup=get_diff_protocol_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_previous")
async def back_to_previous_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prev_state = data.get("prev_state")
    if prev_state:
        await state.set_state(prev_state)
    else:
        await state.set_state(GetKey.choosing_vpn_protocol_type)

    await callback.message.edit_text(
        "Выберите тип подключения:\n\n",
        reply_markup=get_choice_vpn_type_keyboard(prev_state),
        parse_mode="HTML",
    )
    await callback.answer()
