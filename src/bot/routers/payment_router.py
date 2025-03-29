import os
import uuid
import json
import logging
from dotenv import load_dotenv

from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from initialization.outline_processor_init import async_outline_processor
from initialization.vless_processor_init import vless_processor
from initialization.db_processor_init import db_processor
from bot.fsm.states import GetKey, SubscriptionExtension
from initialization.bot_init import bot
from bot.keyboards.keyboards import (
    get_back_button_to_key_params,
    get_after_payment_expired_key_keyboard,
    get_back_button_to_buy_key,
)

from bot.utils.dicts import prices_dict
from bot.utils.extend_key_in_db import extend_key_in_db
from bot.utils.send_message import send_key_to_user
from bot.lexicon.lexicon import get_month_by_number

from logger.log_sender import LogSender


load_dotenv()
provider_token = os.getenv("PROVIDER_PAYMENT_TOKEN")

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(
    StateFilter(SubscriptionExtension.choose_extension_period),
    ~F.data.in_(["back_to_expired_keys"]),
)
@router.callback_query(
    StateFilter(GetKey.buy_key),
    ~F.data.in_(
        [
            "trial_period",
            "back_to_choice_vpn_type",
            "back_to_main_menu",
            "installation_instructions",
        ]
    ),
)
@router.callback_query(
    StateFilter(GetKey.choice_extension_period),
    ~F.data.in_(
        [
            "to_key_params",
            "back_to_choice_vpn_type",
            "back_to_main_menu",
            "installation_instructions",
        ]
    ),
)
async def handle_period_selection(callback: CallbackQuery, state: FSMContext):
    selected_period = callback.data.split("_")[0]
    amount = prices_dict[selected_period]
    prices = [LabeledPrice(label="Ключ от VPN", amount=amount)]

    moths = get_month_by_number(int(selected_period))
    cur_state = await state.get_state()
    data = await state.get_data()
    match cur_state:
        case GetKey.buy_key:
            vpn_type = data.get("vpn_type")
            description = f"Ключ от VPN {vpn_type} на {selected_period} {moths}"
            title = "Покупка ключа"

        case (
            GetKey.choice_extension_period
            | SubscriptionExtension.choose_extension_period
        ):
            selected_key_id = data.get("selected_key_id")
            vpn_type = db_processor.get_vpn_type_by_key_id(selected_key_id)
            await state.update_data(vpn_type=vpn_type)
            key = db_processor.get_key_by_id(selected_key_id)
            await state.update_data(key_name=key.name)
            title = "Продление ключа"
            description = f"Продление ключа «{key.name}» от VPN {vpn_type} на {selected_period} {moths}"
            await state.update_data(selected_period=selected_period)

    match cur_state:
        case GetKey.buy_key:
            await state.set_state(GetKey.waiting_for_payment)
        case GetKey.choice_extension_period:
            await state.set_state(GetKey.waiting_for_extension_payment)
        case SubscriptionExtension.choose_extension_period:
            await state.set_state(SubscriptionExtension.waiting_for_extension_payment)

    # Сохранение выбранного периода в состоянии
    await state.update_data(selected_period=selected_period)

    logger.info(f"Sending invoice with currency=RUB, amount={prices}")
    payment_message = await callback.message.edit_text(text="Оплата")
    await state.update_data(payment_message_id=payment_message.message_id)

    current_state = await state.get_state()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=title,
        description=description,
        payload=str(uuid.uuid4()),
        provider_token=provider_token,
        start_parameter=str(uuid.uuid4()),
        currency="rub",
        prices=prices,
        reply_markup=get_back_button_to_buy_key(amount / 100, current_state),
    )

    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout_query(pre_checkout_q: PreCheckoutQuery):
    # Проверяем данные платежа
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


# Обработчик успешного платежа при ПОКУПКЕ ключа
@router.message(
    StateFilter(GetKey.waiting_for_payment), lambda message: message.successful_payment
)
async def successful_payment(message: Message, state: FSMContext):
    try:
        # Логирование успешного платежа
        data = await state.get_data()
        period = data.get("selected_period")
        LogSender.log_payment_details(message)
        # Создание нового ключа VPN
        match data.get("vpn_type").lower():
            case "outline":
                protocol_type = "Outline"
                key, server_id = await async_outline_processor.create_vpn_key(user_id=message.from_user.id)
            case "vless":
                protocol_type = "VLESS"
                key, server_id = await vless_processor.create_vpn_key(user_id=message.from_user.id)

        logger.info(f"Key created: {key} for user {message.from_user.id}")

        new_message = await message.answer(text="Оплата прошла успешно")
        await send_key_to_user(
            new_message,
            key,
            f"Ваш ключ «{key.name}» добавлен в менеджер ключей (в нем можно его переименовать)",
            state,
            data.get("vpn_type").lower(),
        )

        # Обновление базы данных
        db_processor.update_database_with_key(
            message.from_user.id, key, period, server_id, protocol_type
        )

        # Отправка инструкций по установке
        await state.update_data(key_access_url=key.access_url)
        await state.set_state(GetKey.sending_key)

        amount = message.successful_payment.total_amount
        await notify_admins(amount)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")
        await message.answer(
            "Произошла ошибка при создании ключа. Пожалуйста, свяжитесь с поддержкой."
        )
        await state.clear()


# Обработчик успешного платежа при продлении ключа
@router.message(
    StateFilter(GetKey.waiting_for_extension_payment),
    lambda message: message.successful_payment,
)
@router.message(
    StateFilter(SubscriptionExtension.waiting_for_extension_payment),
    lambda message: message.successful_payment,
)
async def successful_extension_payment(message: Message, state: FSMContext):
    try:
        # Логирование успешного платежа
        LogSender.log_payment_details(message)
        # Находим ключ по его ID
        data = await state.get_data()
        key_id = data.get("selected_key_id")
        add_period = int(data.get("selected_period").split()[0])
        add_period = 30 * add_period

        new_message = await message.answer(text="Оплата прошла успешно")
        expiration_date = extend_key_in_db(key_id=key_id, add_period=add_period)

        key_obj = db_processor.get_key_by_id(key_id)
        protocol = key_obj.protocol_type.lower()
        server_id = key_obj.server_id
        if protocol == "outline":
            await async_outline_processor.extend_data_limit_plus_200gb(
                key_id=key_id, server_id=server_id
            )

        elif protocol == "vless":
            await vless_processor.extend_data_limit_plus_200gb(
                key_id=key_id, server_id=server_id
            )

        data = await state.get_data()
        current_state = await state.get_state()
        match current_state:
            case GetKey.waiting_for_extension_payment:
                keyboard = get_back_button_to_key_params()
            case SubscriptionExtension.waiting_for_extension_payment:
                keyboard = get_after_payment_expired_key_keyboard()
        await new_message.edit_text(
            f'Действие ключа «{data.get("key_name")}» продлено до <b>{expiration_date.strftime("%d.%m.%Y")}</b>',
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        await state.set_state(GetKey.sending_key)

        amount = message.successful_payment.total_amount
        await notify_admins(amount)
    except Exception as e:
        logger.info(e)


async def notify_admins(amount: int):
    """
    Отправляет сообщение администраторам о новой оплате.

    :param amount: Сумма оплаты в копейках (например, 1500 означает 15.00 руб).
    """
    # Преобразуем сумму в рубли
    amount_rub = amount / 100

    # Получаем список ID администраторов из переменной окружения
    admin_ids_str = os.getenv("ADMIN_IDS", "[]")
    try:
        admin_ids = json.loads(admin_ids_str)
    except Exception as e:
        logger.error(f"Ошибка парсинга ADMIN_IDS: {e}")
        admin_ids = []

    message_text = f"💵 Новая оплата на сумму {amount_rub} руб 💵"
    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=int(admin_id), text=message_text)
            logger.info(f"Сообщение отправлено админу {admin_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения админу {admin_id}: {e}")
