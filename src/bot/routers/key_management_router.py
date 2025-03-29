from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram import F, Router

from bot.routers.admin_router_sending_message import send_error_report
from initialization.db_processor_init import db_processor
from bot.fsm.states import ManageKeys, MainMenu, GetKey
from database.models import User

from bot.keyboards.keyboards import (
    get_buttons_for_trial_period,
    get_key_name_choosing_keyboard,
)

import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(
    StateFilter(
        ManageKeys.no_active_keys,
        MainMenu.waiting_for_action,
        ManageKeys.choose_key_action,
        GetKey.get_trial_key,
        GetKey.choosing_vpn_protocol_type,
    ),
    F.data == "key_management_pressed",
)
# @router.callback_query(StateFilter(MainMenu.waiting_for_action), F.data == "key_management_pressed")
async def choosing_key_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_id_str = str(user_id)
    session = db_processor.get_session()

    try:
        user = session.query(User).filter_by(user_telegram_id=user_id_str).first()
        if not user or len(user.keys) == 0:
            await state.set_state(ManageKeys.no_active_keys)
            await callback.message.edit_text(
                "У вас нет активных ключей, но вы можете получить пробный период или приобрести ключ",
                reply_markup=get_buttons_for_trial_period(),
            )

        else:
            await state.clear()
            # user.keys - это список объектов алхимии Key
            keyboard = await get_key_name_choosing_keyboard(user.keys)
            await callback.message.edit_text(
                "Выберите ключ для управления:",
                reply_markup=keyboard,
            )
            await state.set_state(ManageKeys.get_key_params)
    except Exception as e:
        await send_error_report(e)
        logger.error(f"Ошибка при выборе ключа: {e}")
        await callback.message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")
        await state.clear()
    finally:
        session.close()
