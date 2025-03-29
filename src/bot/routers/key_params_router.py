from datetime import datetime, timedelta

from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram import F, Router

from initialization.outline_processor_init import async_outline_processor
from bot.utils.send_message import send_key_to_user_with_back_button
from initialization.db_processor_init import db_processor
from utils.get_processor import get_processor
from bot.lexicon.lexicon import get_day_by_number
from initialization.bot_init import bot
from bot.fsm.states import ManageKeys

from initialization.vless_processor_init import vless_processor
from bot.keyboards.keyboards import (
    get_back_button_to_key_params,
    get_confirmation_keyboard,
    get_key_action_keyboard,
)

import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "to_key_params")
@router.callback_query(
    StateFilter(ManageKeys.get_key_params), ~F.data.in_(["back_to_main_menu", "none"])
)
async def choosing_key_handler(callback: CallbackQuery, state: FSMContext):
    # Проверяем, начинается ли callback.data с "key_"
    if callback.data.startswith("key_"):
        # Извлекаем ID ключа из callback.data
        selected_key_id = callback.data.split("_")[1]
        # Сохраняем ID ключа в состоянии
        await state.update_data(selected_key_id=selected_key_id)
    else:
        # Если callback.data не содержит новый ID ключа, получаем его из состояния
        data = await state.get_data()
        selected_key_id = data.get("selected_key_id")

    # Проверка на случай, если selected_key_id всё ещё пустой
    if not selected_key_id:
        await callback.message.answer("ID ключа не найден.")
        return

    if not selected_key_id:
        await callback.message.answer(
            "Ключ не выбран. Пожалуйста, вернитесь назад и выберите ключ."
        )
        return

    # Получаем информацию о ключе из базы данных
    key = db_processor.get_key_by_id(selected_key_id)
    keyboard = await get_key_action_keyboard(key.key_id)
    await callback.message.edit_text(
        f"Выберите действие для ключа: «{key.name}»",
        reply_markup=keyboard,
    )

    await state.set_state(ManageKeys.choose_key_action)


@router.callback_query(
    StateFilter(ManageKeys.choose_key_action), F.data.startswith("traffic")
)
async def show_traffic_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    key_info = data.get("key_info")
    key = data.get("key")
    if key_info is None:
        key = db_processor.get_key_by_id(data.get("selected_key_id"))
        processor = await get_processor(key.protocol_type)
        key_info = await processor.get_key_info(key.key_id, server_id=key.server_id)
        logger.info(f"Key info: {key_info}")
        # заносим всю инфу о ключе в дату, чтобы оперативно доставать её в других обработчиках
        await state.update_data(key_info=key_info, key_name=key.name, key=key)

    used_bytes = 0

    if key_info.used_bytes is not None:
        used_bytes = key_info.used_bytes - key.used_bytes_last_month
    total_traffic = used_bytes / (1024**3)

    data_limit = key_info.data_limit
    if data_limit == 10 * 1024**3:
        data_limit_str = "10"
    else:
        data_limit_str = "200"

    response = f"""
    Суммарный трафик за месяц: {total_traffic:.2f}/{data_limit_str} Гб
    """
    await callback.message.edit_text(
        response, reply_markup=get_back_button_to_key_params()
    )


# 11.03.2025 - 13.03.2025
# дата окончания активации
@router.callback_query(
    StateFilter(ManageKeys.choose_key_action), F.data.startswith("expiration")
)
async def show_expiration_date_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    key = db_processor.get_key_by_id(data["selected_key_id"])

    expiration_date = key.expiration_date.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if expiration_date:
        remaining_days = (expiration_date - now).days
    else:
        remaining_days = None

    days = get_day_by_number(remaining_days)
    if remaining_days is not None:
        response = f"Действует по: {(expiration_date - timedelta(days=1)).strftime('%d.%m.%Y')}\nДо окончания: {remaining_days} {days}"
    else:
        response = "Дата окончания не установлена."

    await callback.message.edit_text(
        response, reply_markup=get_back_button_to_key_params()
    )
    callback.answer()


@router.callback_query(
    StateFilter(ManageKeys.choose_key_action), F.data.startswith("rename")
)
async def ask_new_name_handler(callback: CallbackQuery, state: FSMContext):
    # Запрашиваем у пользователя новое имя для ключа
    prompt = await callback.message.edit_text("Введите новое имя для ключа:")
    await state.update_data(prompt_msg_id=prompt.message_id)
    # Переходим к следующему состоянию
    await state.set_state(ManageKeys.wait_for_new_name)


@router.message(StateFilter(ManageKeys.wait_for_new_name))
async def receive_new_name_handler(message: Message, state: FSMContext):
    new_name = message.text.strip()  # Получаем введенное имя
    await message.delete()

    data = await state.get_data()
    prompt_msg_id = data.get("prompt_msg_id")

    # Проверяем, что имя не пустое
    if not new_name:
        await message.answer("Имя не может быть пустым. Пожалуйста, введите новое имя.")
        return

    # Сохраняем новое имя в состояние
    await state.update_data(new_name=new_name)

    # Запрашиваем подтверждение переименования
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=prompt_msg_id,
        text=f"Вы хотите переименовать ключ в «{new_name}»? Подтвердите действие.",
        reply_markup=get_confirmation_keyboard(),
    )

    # Переходим к состоянию подтверждения
    await state.set_state(ManageKeys.confirm_rename)


@router.callback_query(
    StateFilter(ManageKeys.confirm_rename), F.data == "confirm_rename"
)
async def confirm_rename_handler(callback: CallbackQuery, state: FSMContext):
    # Получаем данные из состояния
    data = await state.get_data()
    key_id = data["selected_key_id"]
    new_name = data["new_name"]

    # Получаем информацию о ключе из базы данных
    db_processor.rename_key(key_id, new_name)
    key = db_processor.get_key_by_id(key_id)

    await state.update_data(key_name=key.name)

    # Переименовываем ключ через OutlineProcessor (если нужно)
    match key.protocol_type.lower():
        case "outline":
            await async_outline_processor.rename_key(
                key.key_id, new_name, server_id=key.server_id
            )
        case "vless":
            await vless_processor.rename_key(
                key_id=key.key_id, server_id=key.server_id, new_key_name=new_name
            )

    # Отправляем сообщение пользователю
    await callback.message.edit_text(
        f"Ключ переименован в: «{new_name}»",
        reply_markup=get_back_button_to_key_params(),
    )


@router.callback_query(
    StateFilter(ManageKeys.confirm_rename), F.data == "cancel_rename"
)
async def cancel_rename_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "Переименование отменено", reply_markup=get_back_button_to_key_params()
    )


@router.callback_query(
    StateFilter(ManageKeys.choose_key_action), F.data.startswith("access_url")
)
async def show_key_url_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    key_info = data.get("key_info")
    key_name = data.get("key_name")
    if key_info is None:
        key = db_processor.get_key_by_id(data.get("selected_key_id"))
        key_name = key.name
        processor = await get_processor(key.protocol_type)
        key_info = await processor.get_key_info(key.key_id, server_id=key.server_id)
        logger.info(f"Key info: {key_info}")
        # заносим всю инфу о ключе в дату, чтобы оперативно доставать её в других обработчиках
        await state.update_data(key_info=key_info, key_name=key_name, key=key)

    # Отправляем ключ пользователю
    await send_key_to_user_with_back_button(
        callback.message, key_info, f"Ваш ключ «{key_name}»"
    )
