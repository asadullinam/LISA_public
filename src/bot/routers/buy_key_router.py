from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram import F, Router

from bot.fsm.states import GetKey, ManageKeys, SubscriptionExtension
from initialization.bot_init import bot
from bot.keyboards.keyboards import (
    get_extension_periods_keyboard,
    get_period_keyboard,
    get_notification_extension_periods_keyboard,
)

import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(
    StateFilter(GetKey.get_trial_key), F.data == "back_to_choice_period"
)
@router.callback_query(
    StateFilter(GetKey.choosing_vpn_protocol_type),
    F.data.in_(["VPNtype_Outline", "VPNtype_VLESS"]),
)
async def buy_key_menu(callback: CallbackQuery, state: FSMContext):
    cur_state = await state.get_state()
    # если мы вернулись из запроса пробного ключа, то тип был выбран ранее

    if cur_state == GetKey.choosing_vpn_protocol_type:
        await state.update_data(vpn_type=callback.data.split("_")[1])

    await state.set_state(GetKey.buy_key)
    await callback.message.edit_text(
        "Выберите период подписки:",
        reply_markup=get_period_keyboard(),
    )


@router.callback_query(
    StateFilter(GetKey.waiting_for_payment, GetKey.waiting_for_extension_payment),
    F.data == "back_to_buy_key",
)
async def back_buy_key_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GetKey.buy_key)
    await callback.message.delete()
    data = await state.get_data()
    payment_message_id = data.get("payment_message_id")

    await bot.edit_message_text(
        text="Выберите период продления:",
        chat_id=callback.message.chat.id,
        message_id=payment_message_id,
        reply_markup=get_period_keyboard(),
    )


@router.callback_query(F.data.startswith("extend_"))
@router.callback_query(F.data.startswith("expired_extend_"))
@router.callback_query(
    F.data.in_(
        [
            "back_to_choice_extension_period",
            "back_to_choice_extension_period_for_expired_key",
        ]
    )
)
async def extension_period_key_menu(callback: CallbackQuery, state: FSMContext):
    if callback.data.startswith("expired_extend_"):
        await state.update_data(selected_key_id=callback.data.split("_")[2])
        await callback.message.edit_text(
            "Выберите период продления:",
            reply_markup=get_notification_extension_periods_keyboard(),
        )
        await state.set_state(SubscriptionExtension.choose_extension_period)
    else:
        data = await state.get_data()
        selected_key_id = data.get("selected_key_id", None)
        if not selected_key_id:
            await state.update_data(selected_key_id=callback.data.split("_")[1])
        current_state = await state.get_state()
        match current_state:
            case GetKey.waiting_for_extension_payment:
                await callback.message.delete()

                data = await state.get_data()
                payment_message_id = data.get("payment_message_id")

                await bot.edit_message_text(
                    text="Выберите период продления:",
                    chat_id=callback.message.chat.id,
                    message_id=payment_message_id,
                    reply_markup=get_extension_periods_keyboard(),
                )
                await state.set_state(GetKey.choice_extension_period)

            case ManageKeys.choose_key_action:
                await callback.message.edit_text(
                    "Выберите период продления:",
                    reply_markup=get_extension_periods_keyboard(),
                )
                await state.set_state(GetKey.choice_extension_period)

            case SubscriptionExtension.waiting_for_extension_payment:
                await callback.message.delete()

                data = await state.get_data()
                payment_message_id = data.get("payment_message_id")

                await bot.edit_message_text(
                    text="Выберите период продления:",
                    chat_id=callback.message.chat.id,
                    message_id=payment_message_id,
                    reply_markup=get_notification_extension_periods_keyboard(),
                )
                await state.set_state(SubscriptionExtension.choose_extension_period)
