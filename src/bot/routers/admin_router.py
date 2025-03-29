from datetime import datetime, timedelta
from dotenv import load_dotenv
import textwrap
import os
import json
import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.filters import Command
from aiogram import Router, F

from bot.routers.admin_router_sending_message import send_error_report
from initialization.outline_processor_init import async_outline_processor
from initialization.vdsina_processor_init import vdsina_processor
from initialization.vless_processor_init import vless_processor
from initialization.db_processor_init import db_processor
from bot.utils.string_makers import get_your_key_string
from bot.keyboards.keyboards import (
    get_confirm_broadcast_keyboard,
    get_admin_period_keyboard,
)
from initialization.bot_init import bot
from bot.fsm.states import AdminAccess
from bot.keyboards.keyboards import (
    get_admin_keyboard,
    get_back_button,
    get_back_admin_panel_keyboard,
)

load_dotenv()
router = Router()
logger = logging.getLogger(__name__)

load_dotenv()

admin_passwords = json.loads(os.getenv("ADMIN_PASSWORDS"))
admin_passwords = {int(k): v for k, v in admin_passwords.items()}

pending_admin = {}
try:
    admin_ids_str = os.getenv("ADMIN_IDS", "[]")
    ADMIN_IDS = list(map(int, json.loads(admin_ids_str)))
except Exception as e:
    logger.error(f"Ошибка загрузки ADMIN_IDS: {e}")
    ADMIN_IDS = []


@router.message(Command("admin"))
async def admin_start(message: Message, state: FSMContext):
    await message.delete()
    if message.from_user.id in admin_passwords:
        pending_admin[message.from_user.id] = True

        data = await state.get_data()
        prompt_msg_id = data.get("prompt_msg_id")

        new_prompt = await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=prompt_msg_id,
            text="🔒 Введите пароль для доступа к админ-панели.",
            reply_markup=get_back_button(),
        )

        await state.update_data(prompt_msg_id=new_prompt.message_id)
        await state.set_state(AdminAccess.wait_password_enter)
    else:
        await message.answer("🚫 У вас нет доступа.", reply_markup=get_back_button())


@router.message(StateFilter(AdminAccess.wait_password_enter))
async def admin_auth(message: Message, state: FSMContext):
    # Удаляем сообщение с введённым паролем
    await message.delete()

    if pending_admin.get(message.from_user.id):
        # Извлекаем id исходного сообщения с запросом пароля из состояния
        data = await state.get_data()
        prompt_msg_id = data.get("prompt_msg_id")
        if message.text == admin_passwords[message.from_user.id]:
            if prompt_msg_id:
                try:
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=prompt_msg_id,
                        text="👑 Добро пожаловать в Админ-панель",
                        reply_markup=get_admin_keyboard(),
                    )
                except TelegramBadRequest as e:
                    # await send_error_report(e)
                    if "message is not modified" in str(e):
                        # Сообщение не изменилось – игнорируем ошибку
                        pass
                    # else:
                    #     raise
            await state.set_state(AdminAccess.correct_password)
            pending_admin.pop(message.from_user.id, None)
        else:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=prompt_msg_id,
                    text="🚫 Неверный пароль. Попробуйте снова или вернитесь в главное меню",
                    reply_markup=get_back_button(),
                )
            except TelegramBadRequest as e:
                # await send_error_report(e)
                if "message is not modified" in str(e):
                    # Сообщение не изменилось – игнорируем ошибку
                    pass
                # else:
                #     raise


async def make_servers_info_text(servers):
    servers_info = "Информация по серверам за послдение 30 дней:\n\n"
    for server in servers:
        servers_info += f"Информация по серверу «{server}»:\n"
        servers_info += await make_info(servers[server]) + "\n"
    return servers_info


async def make_info(server):
    virtual_traffic_in_tb = server["vnet_rx"] // 1000
    virtual_traffic_in_gb = server["vnet_rx"] % 1000
    virtual_traffic_out_tb = server["vnet_tx"] // 1000
    virtual_traffic_out_gb = server["vnet_tx"] % 1000

    if virtual_traffic_in_tb > 0:
        virtual_traffix_in_text = (
            f"{virtual_traffic_in_tb:.1f} Тб, {virtual_traffic_in_gb:.1f} Гб"
        )
    else:
        virtual_traffix_in_text = f"{virtual_traffic_in_gb:.1f} Гб"

    if virtual_traffic_out_tb > 0:
        virtual_traffix_out_text = (
            f"{virtual_traffic_out_tb:.1f} Тб, {virtual_traffic_out_gb:.1f} Гб"
        )
    else:
        virtual_traffix_out_text = f"{virtual_traffic_out_gb:.1f} Гб"

    return textwrap.dedent(f"""\
        Процент использования дискового пространства: {((server['vnet_rx'] + server['vnet_tx']) / server['data_limit']) * 100:.2f}%
        Средняя в час загрузка CPU: {server["cpu"]:.1f}%
        Трафик виртуальной сети:
            - входящий: {virtual_traffix_in_text}
            - исходящий: {virtual_traffix_out_text}
        """)


async def aggregate_statistics(response):
    # Ключи, значения которых можно суммировать
    keys_to_sum = [
        "disk_reads",
        "disk_writes",
        "lnet_rx",
        "lnet_tx",
        "vnet_rx",
        "vnet_tx",
    ]

    aggregated = {key: 0 for key in keys_to_sum}
    total_cpu = 0
    count = 0

    for entry in response.get("data", []):
        stat = entry.get("stat", {})
        for key in keys_to_sum:
            aggregated[key] += stat.get(key, 0)
        # Для CPU считаем среднее значение
        total_cpu += stat.get("cpu", 0)
        count += 1

    aggregated["cpu"] = total_cpu / count if count else 0
    # Конвертация трафика из байт в гигабайты (1 ГБ = 10^9 байт)
    for key in ["lnet_rx", "lnet_tx", "vnet_rx", "vnet_tx"]:
        aggregated[key] /= 1e9

    return aggregated


@router.callback_query(F.data == "get_servers_info")
async def get_servers_info(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Получение информации по серверам...")
    now = datetime.now()
    start = now - timedelta(days=30)
    servers_lst = await vdsina_processor.get_servers()
    # print(json.dumps(servers_lst, indent=4, ensure_ascii=False))

    data = {}
    # print(json.dumps(servers_lst["data"], indent=4, ensure_ascii=False))
    for server in servers_lst["data"]:
        # print(server['id'])
        info = await vdsina_processor.get_server_statistics(server["id"])
        status = await vdsina_processor.get_server_status(server["id"])
        server_data_limit = status.get("data", {}).get("data", {}).get("traff", 0).get('bytes', 0) / 1e9

        data[server["id"]] = await aggregate_statistics(info)
        data[server["id"]]["data_limit"] = server_data_limit
    info = await make_servers_info_text(data)
    await callback.message.edit_text(
        text=info, reply_markup=get_back_admin_panel_keyboard()
    )
    await state.set_state(AdminAccess.correct_password)


@router.callback_query(
    StateFilter(AdminAccess.admin_choosing_vpn_protocol_type),
    F.data.in_(["VPNtype_VLESS", "VPNtype_Outline"]),
)
async def choose_period_for_admin_key(callback: CallbackQuery, state: FSMContext):
    await state.update_data(chosen_protocol=callback.data.split("_")[1].lower())
    await state.set_state(AdminAccess.admin_choosing_period_for_key)
    await callback.message.edit_text(
        "Выберите период подписки:",
        reply_markup=get_admin_period_keyboard(),
    )


@router.callback_query(
    StateFilter(AdminAccess.admin_choosing_period_for_key),
    ~F.data.in_("back_to_admin_panel"),
)
async def make_key_for_admin(callback: CallbackQuery, state: FSMContext):
    chosen_period = callback.data.split("_")[0]
    data = await state.get_data()
    protocol_type = data.get("chosen_protocol")
    try:
        match protocol_type:
            case "outline":
                protocol_type = "Outline"
                key, server_id = await async_outline_processor.create_vpn_key()
            case "vless":
                protocol_type = "VLESS"
                key, server_id = await vless_processor.create_vpn_key()

        logger.info(f"Key created: {key} for user {callback.from_user.id}")

        await callback.message.edit_text(
            get_your_key_string(key, f"Ваш ключ «{key.name}»"),
            parse_mode="Markdown",
            reply_markup=get_back_admin_panel_keyboard(),
        )

        db_processor.update_database_with_key(
            callback.from_user.id, key, chosen_period, server_id, protocol_type
        )

        # Отправка инструкций по установке
        await state.update_data(key_access_url=key.access_url)
    except Exception as e:
        await send_error_report(e)
        logger.error(f"Произошла ошибка: {e}")
        await callback.answer(
            "Произошла ошибка при создании ключа. Пожалуйста, свяжитесь с поддержкой."
        )
        await state.set_state(AdminAccess.correct_password)


@router.callback_query(
    F.data == "back_to_admin_panel",
    StateFilter(
        AdminAccess.correct_password,
        AdminAccess.admin_choosing_vpn_protocol_type,
        AdminAccess.admin_choosing_period_for_key,
    ),
)
async def admin_panel(callback: CallbackQuery):
    await callback.message.edit_text(
        "👑 Вы вернулись в админ-панель", reply_markup=get_admin_keyboard()
    )


ADMIN_IDS = list(map(int, json.loads(os.getenv("ADMIN_IDS", "[]"))))


@router.callback_query(F.data == "get_db", StateFilter(AdminAccess.correct_password))
async def send_db(callback: CallbackQuery, state: FSMContext):
    """
    Отправляет файл базы данных администратору по команде /get_db
    """
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 У вас нет доступа.")
        return

    db_path = os.path.abspath("./database/vpn_users.db")  # Укажите правильный путь к БД
    if not os.path.exists(db_path):
        await callback.message.answer("🚫 База данных не найдена! {db_path}")
        return

    db_file = FSInputFile(db_path)
    await state.set_state(AdminAccess.correct_password)
    await callback.message.answer_document(db_file, caption="📂 Вот ваша база данных.")


@router.callback_query(
    F.data == "admin_broadcast",
    StateFilter(
        AdminAccess.correct_password, AdminAccess.admin_choosing_vpn_protocol_type
    ),
)
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите текст для рассылки всем пользователям:",
        reply_markup=get_back_admin_panel_keyboard(),
    )
    await state.set_state(AdminAccess.broadcast_wait_text)


@router.callback_query(
    F.data == "back_to_admin_panel", StateFilter(AdminAccess.broadcast_wait_text)
)
async def cancel_broadcast_input(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminAccess.correct_password)
    try:
        await callback.message.edit_text(
            "Операция рассылки отменена.", reply_markup=get_admin_keyboard()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise
    await state.update_data(broadcast_text=None)


@router.message(StateFilter(AdminAccess.broadcast_wait_text))
async def admin_broadcast_get_text(message: Message, state: FSMContext):
    broadcast_text = message.text
    await state.update_data(broadcast_text=broadcast_text)
    await message.answer(
        f"Вы уверены, что хотите отправить следующее сообщение всем пользователям?\n\n{broadcast_text}",
        reply_markup=get_confirm_broadcast_keyboard(),
    )
    await state.set_state(AdminAccess.broadcast_confirm)


@router.callback_query(
    F.data.in_(["broadcast_confirm", "broadcast_cancel"]),
    StateFilter(AdminAccess.broadcast_confirm),
)
async def admin_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")
    if callback.data == "broadcast_confirm":
        user_ids = await db_processor.get_all_user_ids()
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, broadcast_text)
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
        await callback.message.edit_text(
            "Рассылка завершена.", reply_markup=get_admin_keyboard()
        )
    else:
        await callback.message.edit_text(
            "Рассылка отменена.", reply_markup=get_admin_keyboard()
        )
    await state.set_state(AdminAccess.correct_password)
    await state.update_data(broadcast_text=None)
