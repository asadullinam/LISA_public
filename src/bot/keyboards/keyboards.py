import os

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from bot.lexicon.lexicon import get_day_by_number
from bot.fsm.states import GetKey, SubscriptionExtension, AdminAccess, ManageKeys

import socket


# def get_server_ip():
#     """Определяет текущий внешний IP-адрес сервера."""
#     try:
#         # Подключаемся к внешнему серверу, но НЕ отправляем данные
#         with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
#             s.connect(("8.8.8.8", 80))  # Google DNS
#             return s.getsockname()[0]
#     except Exception:
#         return "127.0.0.1"  # fallback на localhost


def get_main_menu_keyboard():
    # Создаем объекты инлайн-кнопок
    get_key = InlineKeyboardButton(
        text="🆕 Получить ключ", callback_data="choice_vpn_type"
    )

    ket_management = InlineKeyboardButton(
        text="🛠️ Менеджер ключей", callback_data="key_management_pressed"
    )

    about_us = InlineKeyboardButton(text="ℹ️ О нас", callback_data="about_us")

    get_instruction = InlineKeyboardButton(
        text="📃 Инструкция по установке", callback_data="get_instruction"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[[get_key], [ket_management], [get_instruction], [about_us]]
    )


def get_choice_vpn_type_keyboard(state: FSMContext = None):
    match state:
        case (
            AdminAccess.admin_choosing_vpn_protocol_type
            | AdminAccess.correct_password
            | AdminAccess.admin_choosing_period_for_key
        ):
            return InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="VLESS", callback_data="VPNtype_VLESS"
                        ),
                        InlineKeyboardButton(
                            text="OUTLINE", callback_data="VPNtype_Outline"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад", callback_data="back_to_admin_panel"
                        )
                    ],
                ]
            )
        case ManageKeys.get_instruction:
            return InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="VLESS", callback_data="VPNtype_VLESS"
                        ),
                        InlineKeyboardButton(
                            text="OUTLINE", callback_data="VPNtype_Outline"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад", callback_data="back_to_main_menu"
                        )
                    ],
                ]
            )
        case ManageKeys.no_active_keys:
            back_button = InlineKeyboardButton(
                text="🔙 Назад", callback_data="key_management_pressed"
            )
        case _:
            back_button = InlineKeyboardButton(
                text="🔙 Назад", callback_data="back_to_main_menu"
            )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="VLESS", callback_data="VPNtype_VLESS"),
                InlineKeyboardButton(text="OUTLINE", callback_data="VPNtype_Outline"),
            ],
            [
                InlineKeyboardButton(
                    text="Узнать отличия протоколов", callback_data="protocol_diff"
                )
            ],
            [back_button],
        ]
    )


def get_diff_protocol_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_previous")]
        ]
    )


def get_choice_vpn_type_keyboard_for_no_key() -> object:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="VLESS", callback_data="VPNtype_VLESS"),
                InlineKeyboardButton(text="OUTLINE", callback_data="VPNtype_Outline"),
            ],
            [
                InlineKeyboardButton(
                    text="Узнать отличия протоколов", callback_data="protocol_diff"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад", callback_data="key_management_pressed"
                )
            ],
        ]
    )


def get_confirm_broadcast_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Отправить", callback_data="broadcast_confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить", callback_data="broadcast_cancel"
                )
            ],
        ]
    )
    return keyboard


def get_device_vless_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🖥 MacOS",
                    callback_data="device_MacOS",
                    url="https://telegra.ph/Instrukciya-po-ustanovke-vless-na-MacOS-01-29",
                ),
                InlineKeyboardButton(
                    text="📱 iPhone",
                    callback_data="device_iPhone",
                    url="https://telegra.ph/Instrukciya-po-ustanovke-vless-na-iPhone-01-29",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💻 Windows",
                    callback_data="device_Windows",
                    url="https://telegra.ph/Instrukciya-po-ustanovke-Vless-na-Windows-03-02",
                ),
                InlineKeyboardButton(
                    text="📲 Android",
                    callback_data="device_Android",
                    url="https://telegra.ph/Instrukciya-po-ustanovke-Vless-na-Android-03-02",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад", callback_data="back_choice_type_for_instruction"
                )
            ],
        ]
    )


def get_device_outline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🖥 MacOS",
                    callback_data="device_MacOS",
                    url="https://telegra.ph/Instrukciya-po-ustanovke-Outline-na-MacOS-03-01",
                ),
                InlineKeyboardButton(
                    text="📱 iPhone",
                    callback_data="device_iPhone",
                    url="https://telegra.ph/Instrukciya-po-ustanovke-Outline-na-iPhone-01-29",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💻 Windows",
                    callback_data="device_Windows",
                    url="https://telegra.ph/Podklyuchenie-Outline-na-Windows-03-02",
                ),
                InlineKeyboardButton(
                    text="📲 Android",
                    callback_data="device_Android",
                    url="https://telegra.ph/Podklyuchenie-Outline-na-Android-02-09",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад", callback_data="back_choice_type_for_instruction"
                )
            ],
        ]
    )


def get_about_us_keyboard():
    back_button = InlineKeyboardButton(
        text="🔙 Назад", callback_data="back_to_main_menu"
    )
    return InlineKeyboardMarkup(inline_keyboard=[[back_button]])


def get_period_keyboard():
    # Кнопки для выбора периода
    month_button = InlineKeyboardButton(text="1 Месяц (89₽)", callback_data="1_month")
    three_month_button = InlineKeyboardButton(
        text="3 Месяца (239₽)", callback_data="3_months"
    )
    six_month_button = InlineKeyboardButton(
        text="6 Месяцев (399₽)", callback_data="6_months"
    )
    year_button = InlineKeyboardButton(
        text="12 Месяцев (729₽)", callback_data="12_months"
    )

    trial_period_button = InlineKeyboardButton(
        text="Пробный период", callback_data="trial_period"
    )

    back_button = InlineKeyboardButton(
        text="🔙 Назад", callback_data="back_to_choice_vpn_type"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [month_button],
            [three_month_button],
            [six_month_button],
            [year_button],
            [trial_period_button],
            [back_button],
        ]
    )


def get_outline_installation_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Инструкция",
                    callback_data="outline_installation_instructions",
                ),
                InlineKeyboardButton(
                    text="В главное меню",
                    callback_data="back_to_main_menu",
                ),
            ]
        ]
    )


def get_vless_installation_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Инструкция",
                    callback_data="vless_installation_instructions",
                ),
                InlineKeyboardButton(
                    text="В главное меню",
                    callback_data="back_to_main_menu",
                ),
            ]
        ]
    )


# это нужно переименовать тк юзается еще в менеджере когда нет активных ключей
def get_buttons_for_trial_period():
    get_trial_key = InlineKeyboardButton(
        text="Пробный ключ", callback_data="get_trial_period"
    )
    buy_key_button = InlineKeyboardButton(
        text="Купить ключ", callback_data="get_keys_pressed"
    )
    back_button = InlineKeyboardButton(
        text="🔙 Назад", callback_data="back_to_main_menu"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[[get_trial_key], [buy_key_button], [back_button]]
    )


def get_back_button():
    # Создаем объекты инлайн-кнопок
    to_main_menu_button = InlineKeyboardButton(
        text="В главное меню", callback_data="back_to_main_menu"
    )
    return InlineKeyboardMarkup(inline_keyboard=[[to_main_menu_button]])


def get_extension_periods_keyboard():
    # Кнопки для выбора периода
    month_button = InlineKeyboardButton(text="1 Месяц (89₽)", callback_data="1_month")
    three_month_button = InlineKeyboardButton(
        text="3 Месяца (239₽)", callback_data="3_months"
    )
    six_month_button = InlineKeyboardButton(
        text="6 Месяцев (399₽)", callback_data="6_months"
    )
    year_button = InlineKeyboardButton(
        text="12 Месяцев (729₽)", callback_data="12_months"
    )
    back_button = InlineKeyboardButton(text="🔙 Назад", callback_data="to_key_params")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [month_button],
            [three_month_button],
            [six_month_button],
            [year_button],
            [back_button],
        ]
    )


async def get_key_name_choosing_keyboard(keys: list):
    keyboard_buttons = []

    outline_keys = [key for key in keys if key.protocol_type == "Outline"]
    vless_keys = [key for key in keys if key.protocol_type == "VLESS"]

    def add_keys_section(title: str, keys: list):
        """Добавляет заголовок и кнопки ключей в клавиатуру."""
        keyboard_buttons.append(
            [InlineKeyboardButton(text=f" {title} 🔽 ", callback_data="none")]
        )

        # Определяем максимальную длину имени ключа для выравнивания
        max_length = max((len(key.name) for key in keys), default=10)

        for key in keys:
            key_name = f"🔑 {key.name}".ljust(max_length + 3)  # +3 для отступов
            keyboard_buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"  {key_name}  ", callback_data=f"key_{key.key_id}"
                    )
                ]
            )

    if outline_keys:
        add_keys_section("OUTLINE", outline_keys)

    if vless_keys:
        add_keys_section("VLESS", vless_keys)

    keyboard_buttons.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main_menu")]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


def get_key_name_extension_keyboard_with_names(keys: dict):
    keyboard_buttons = []
    for key_id in keys:
        days = get_day_by_number(keys[key_id][1])
        button = InlineKeyboardButton(
            text=f"🔑 {keys[key_id][0]} ({keys[key_id][1]} {days})",
            callback_data=f"expired_extend_{key_id}",
        )
        keyboard_buttons.append([button])

    back_button = [
        InlineKeyboardButton(
            text="🔙 В главное меню", callback_data="back_to_main_menu"
        )
    ]
    keyboard_buttons.append(back_button)

    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


async def get_key_action_keyboard(key_id):
    view_traffic_button = InlineKeyboardButton(
        text="📊 Посмотреть объем трафика", callback_data=f"traffic_{key_id}"
    )
    end_data_button = InlineKeyboardButton(
        text="📅 Посмотреть дату конца активации",
        callback_data=f"expiration_{key_id}",
    )
    extend_key_button = InlineKeyboardButton(
        text="⏳ Продлить действие ключа", callback_data=f"extend_{key_id}"
    )
    rename_key_button = InlineKeyboardButton(
        text="✏️ Переименовать ключ", callback_data=f"rename_{key_id}"
    )
    get_url_key_button = InlineKeyboardButton(
        text="🔑 Показать ключ", callback_data=f"access_url_{key_id}"
    )
    launch_app_button = InlineKeyboardButton(
        text="🚀 Запустить в приложении",
        url=f"http://{os.getenv('SERVER_IP')}:8000/open/{key_id}",
    )

    back_button = InlineKeyboardButton(
        text="🔙 Назад", callback_data="key_management_pressed"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [view_traffic_button],
            [end_data_button],
            [extend_key_button],
            [rename_key_button],
            [get_url_key_button],
            [launch_app_button],
            [back_button],
        ]
    )


def get_confirmation_keyboard():
    confirm_button = InlineKeyboardButton(
        text="✅ Подтвердить", callback_data="confirm_rename"
    )
    cancel = InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_rename")

    return InlineKeyboardMarkup(inline_keyboard=[[confirm_button], [cancel]])


def get_already_have_trial_key_keyboard(state: FSMContext):
    match state:
        case GetKey.buy_key:
            back_button = InlineKeyboardButton(
                text="🔙 Назад", callback_data="back_to_choice_period"
            )
        case ManageKeys.no_active_keys:
            back_button = InlineKeyboardButton(
                text="🔙 Назад", callback_data="key_management_pressed"
            )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                back_button,
                InlineKeyboardButton(
                    text="В главное меню", callback_data="back_to_main_menu"
                ),
            ]
        ]
    )


def get_back_button_to_key_params():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="to_key_params"),
                InlineKeyboardButton(
                    text="В главное меню", callback_data="back_to_main_menu"
                ),
            ]
        ]
    )


def get_back_button_to_buy_key(price, state: FSMContext):
    match state:
        case GetKey.waiting_for_payment:
            back_button = InlineKeyboardButton(
                text="🔙 Назад", callback_data="back_to_buy_key"
            )
        case GetKey.waiting_for_extension_payment:
            back_button = InlineKeyboardButton(
                text="🔙 Назад", callback_data="back_to_choice_extension_period"
            )
        case SubscriptionExtension.waiting_for_extension_payment:
            back_button = InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="back_to_choice_extension_period_for_expired_key",
            )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Оплатить {price}₽", pay=True)],
            [
                back_button,
                InlineKeyboardButton(
                    text="В главное меню", callback_data="back_to_main_menu"
                ),
            ],
        ]
    )


def get_notification_extension_periods_keyboard():
    # Кнопки для выбора периода
    month_button = InlineKeyboardButton(text="1 Месяц (89₽)", callback_data="1_month")
    three_month_button = InlineKeyboardButton(
        text="3 Месяца (239₽)", callback_data="3_months"
    )
    six_month_button = InlineKeyboardButton(
        text="6 Месяцев (399₽)", callback_data="6_months"
    )
    year_button = InlineKeyboardButton(
        text="12 Месяцев (729₽)", callback_data="12_months"
    )
    back_button = InlineKeyboardButton(
        text="🔙 Назад", callback_data="back_to_expired_keys"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [month_button],
            [three_month_button],
            [six_month_button],
            [year_button],
            [back_button],
        ]
    )


def get_after_payment_expired_key_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Продлить еще", callback_data="another_expired_keys"
                ),
                InlineKeyboardButton(
                    text="🔙 В главное меню", callback_data="back_to_main_menu"
                ),
            ]
        ]
    )


def get_admin_keyboard():
    get_key = InlineKeyboardButton(
        text="🆕 Получить ключ", callback_data="admin_choice_vpn_type"
    )

    servers_info = InlineKeyboardButton(
        text="📊 Информация о серверах", callback_data="get_servers_info"
    )
    broadcast = InlineKeyboardButton(
        text="📢 Рассылка", callback_data="admin_broadcast"
    )
    get_db = InlineKeyboardButton(
        text="📁 Получить базу данных", callback_data="get_db"
    )
    back_to_main_menu = InlineKeyboardButton(
        text="🔙 В меню", callback_data="back_to_main_menu"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [get_key],
            [servers_info],
            [broadcast],
            [get_db],
            [back_to_main_menu],
        ]
    )


def get_back_admin_panel_keyboard():
    back_button = InlineKeyboardButton(
        text="🔙 Назад", callback_data="back_to_admin_panel"
    )
    return InlineKeyboardMarkup(inline_keyboard=[[back_button]])


def get_admin_period_keyboard():
    month_button = InlineKeyboardButton(text="1 Месяц", callback_data="1_month")
    three_month_button = InlineKeyboardButton(text="3 Месяца", callback_data="3_months")
    six_month_button = InlineKeyboardButton(text="6 Месяцев", callback_data="6_months")
    year_button = InlineKeyboardButton(text="12 Месяцев", callback_data="12_months")
    back_button = InlineKeyboardButton(
        text="🔙 Назад", callback_data="admin_choice_vpn_type"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [month_button],
            [three_month_button],
            [six_month_button],
            [year_button],
            [back_button],
        ]
    )
