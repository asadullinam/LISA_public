from aiogram.fsm.state import State, StatesGroup


class MainMenu(StatesGroup):
    """Класс состояний, относящихся к главному меню"""

    waiting_for_action = State()
    about_us = State()


class GetKey(StatesGroup):
    """Класс состояний, относящихся к получению ключа"""

    get_trial_key = State()
    choosing_vpn_protocol_type = State()
    choosing_period = State()
    waiting_for_payment = State()
    sending_key = State()
    buy_key = State()
    waiting_for_extension_payment = State()
    choice_extension_period = State()


class ManageKeys(StatesGroup):
    """Класс состояний, относящихся к управлению ключами"""

    key_management_no_key = State()
    choosing_key = State()
    choosing_action = State()
    rename_key = State()
    choose_trial_key = State()
    get_key_params = State()
    choose_key_action = State()
    wait_for_new_name = State()
    confirm_rename = State()
    key_management_pressed = State()
    no_active_keys = State()
    get_instruction = State()


class SubscriptionExtension(StatesGroup):
    """Класс состояний, относящихся к продлению подписки"""

    have_extension_key = State()
    choose_extension_period = State()
    choose_key_for_extension = State()
    waiting_for_extension_payment = State()


class AdminAccess(StatesGroup):
    """Класс состояний, относящихся к админ-доступу"""

    wait_password_enter = State()
    correct_password = State()
    admin_choosing_vpn_protocol_type = State()
    admin_choosing_period_for_key = State()
    broadcast_wait_text = State()
    broadcast_confirm = State()
