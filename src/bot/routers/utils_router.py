import logging

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
from aiogram import F, Router

from bot.fsm.states import MainMenu, GetKey, ManageKeys, SubscriptionExtension
from bot.utils.string_makers import (
    get_outline_instruction_string,
    get_vless_instruction_string,
)
from initialization.db_processor_init import db_processor
from initialization.bot_init import bot
from bot.lexicon.lexicon import INFO
from bot.keyboards.keyboards import (
    get_about_us_keyboard,
    get_back_button,
    get_main_menu_keyboard,
    get_choice_vpn_type_keyboard,
    get_device_vless_keyboard,
    get_device_outline_keyboard,
    get_key_name_extension_keyboard_with_names,
)

router = Router()
logger = logging.getLogger(__name__)


# фильтр запроса инструкции
@router.callback_query(F.data == "outline_installation_instructions")
async def send_installation_instructions(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    key_access_url = data.get("key_access_url", "URL не найден")
    instructions = get_outline_instruction_string(key_access_url)
    await callback.message.edit_text(
        instructions,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=get_back_button(),
    )

    await callback.answer()
    await state.set_state(default_state)


@router.callback_query(F.data == "vless_installation_instructions")
async def send_installation_instructions(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    key_access_url = data.get("key_access_url", "URL не найден")
    instructions = get_vless_instruction_string(key_access_url)
    await callback.message.edit_text(
        instructions,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=get_back_button(),
    )

    await callback.answer()
    await state.set_state(default_state)


@router.callback_query(
    StateFilter(ManageKeys.get_instruction),
    F.data == "back_choice_type_for_instruction",
)
@router.callback_query(
    StateFilter(MainMenu.waiting_for_action), F.data == "get_instruction"
)
async def send_connection_choose(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ManageKeys.get_instruction)
    current_state = await state.get_state()
    await callback.message.edit_text(
        text="🔍 **Выберите интересующий вас тип подключения:**",
        parse_mode="Markdown",
        reply_markup=get_choice_vpn_type_keyboard(current_state),
    )
    await callback.answer()


@router.callback_query(
    StateFilter(ManageKeys.get_instruction),
    F.data.in_(["VPNtype_VLESS", "VPNtype_Outline"]),
)
async def send_connection_choose(callback: CallbackQuery, state: FSMContext):
    vpn_type = callback.data.split("_")[1]
    await state.update_data(vpn_type=vpn_type)

    match vpn_type.lower():
        case "vless":
            await callback.message.edit_text(
                text="💻📱 **Выберите ваше устройство:**",
                parse_mode="Markdown",
                reply_markup=get_device_vless_keyboard(),
            )
        case "outline":
            await callback.message.edit_text(
                text="💻📱 **Выберите ваше устройство:**",
                parse_mode="Markdown",
                reply_markup=get_device_outline_keyboard(),
            )
    await callback.answer()


# фильтр кнопки в главное меню из любого места
@router.callback_query(F.data == "back_to_main_menu")
async def back_button(callback: CallbackQuery, state: FSMContext):
    cur_state = await state.get_state()
    if cur_state in {
        GetKey.waiting_for_payment,
        GetKey.waiting_for_extension_payment,
        SubscriptionExtension.waiting_for_extension_payment,
    }:
        await callback.message.delete()
        data = await state.get_data()
        payment_message_id = data.get("payment_message_id")
        await bot.edit_message_text(
            text="Вы вернулись в главное меню. Выберите, что вы хотите сделать",
            chat_id=callback.message.chat.id,
            message_id=payment_message_id,
            reply_markup=get_main_menu_keyboard(),
        )
        await state.set_state(MainMenu.waiting_for_action)
        await callback.answer()
    else:
        prompt = await callback.message.edit_text(
            "Вы вернулись в главное меню. Выберите, что вы хотите сделать",
            reply_markup=get_main_menu_keyboard(),
        )
        await state.update_data(prompt_msg_id=prompt.message_id)
        await state.set_state(MainMenu.waiting_for_action)
        await callback.answer()


@router.callback_query(F.data == "about_us")
async def show_about_us(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        INFO.ABOUT_US,
        reply_markup=get_about_us_keyboard(),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "none")
async def foo(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "another_expired_keys")
@router.callback_query(
    StateFilter(SubscriptionExtension.choose_extension_period),
    F.data == "back_to_expired_keys",
)
async def send_expired_keys(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubscriptionExtension.choose_key_for_extension)
    user_tg_id = callback.from_user.id
    expired_keys = await db_processor.get_expiring_keys_by_user_id(user_tg_id)
    if expired_keys:
        await callback.message.edit_text(
            text="Ключи с истекающим сроком действия:",
            reply_markup=get_key_name_extension_keyboard_with_names(expired_keys),
        )
    else:
        await callback.message.edit_text(
            text=f"Все ключи будут действовать еще минимум 3 дня!\nВы можете продлить ключ, выбрав его в менеджере ключей",
            reply_markup=get_back_button(),
        )
