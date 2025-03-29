import logging

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from outline_vpn.outline_vpn import OutlineKey

from bot.lexicon.lexicon import Notification
from bot.utils.string_makers import get_your_key_string
from initialization.bot_init import bot
from bot.keyboards.keyboards import (
    get_back_button_to_key_params,
    get_vless_installation_button,
    get_outline_installation_button,
    get_key_name_extension_keyboard_with_names,
)

logger = logging.getLogger(__name__)


async def send_key_to_user(
    message: Message,
    key: OutlineKey,
    text: str,
    state: FSMContext,
    vpn_type: str,
) -> None:
    """Отправляет ключ пользователю."""
    logger.info(f"Key created: {key} for user {message.from_user.id}")
    await state.update_data(key_access_url=key.access_url)
    if vpn_type.lower() == "vless":
        await message.edit_text(
            get_your_key_string(key, text),
            parse_mode="Markdown",
            reply_markup=get_vless_installation_button(),
        )
    else:
        await message.edit_text(
            get_your_key_string(key, text),
            parse_mode="Markdown",
            reply_markup=get_outline_installation_button(),
        )


async def send_key_to_user_with_back_button(message: Message, key_info, text: str):
    """Отправляет ключ пользователю c кнопкой назад в параметры ключа"""
    await message.edit_text(
        get_your_key_string(key_info, text),
        parse_mode="Markdown",
        reply_markup=get_back_button_to_key_params(),
    )


async def send_message_subscription_expired(user_tg_id, keys):
    await bot.send_message(
        user_tg_id,
        Notification.SUBSCRIPTION_EXPIRING.value,
        parse_mode="HTML",
        reply_markup=get_key_name_extension_keyboard_with_names(keys),
    )
