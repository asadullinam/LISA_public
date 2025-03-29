import pytest
from aiogram import types
from unittest.mock import patch, AsyncMock
from bot.routers.admin_router import (
    router,
)  # Предположим, что у вас есть роутер с обработчиком


# Мокаем ответ от бота
@pytest.mark.asyncio
async def test_admin_start():
    message = types.Message(
        message_id=1,
        from_user=types.User(
            id=123456789, is_bot=False, first_name="Test", username="testuser"
        ),
        chat=types.Chat(id=123456789, type="private"),
        text="/admin",
    )

    # Эмулируем вызов команды /admin
    with patch("aiogram.Bot.send_message", new_callable=AsyncMock) as mock_send_message:
        # Предположим, что router.message(Command("admin")) это вызов вашего обработчика
        # Также проверьте, что сам обработчик правильно вызывает send_message
        await router.message(message)

        # Проверим, что бот ответил правильным сообщением
        mock_send_message.assert_called_once_with(
            message.chat.id,
            "🔒 Введите пароль для доступа к админ-панели.",
            reply_markup=mock.ANY,
        )


# Тестируем ситуацию, когда у пользователя нет доступа
@pytest.mark.asyncio
async def test_admin_no_access():
    message = types.Message(
        message_id=1,
        from_user=types.User(
            id=987654321, is_bot=False, first_name="Test", username="testuser"
        ),
        chat=types.Chat(id=987654321, type="private"),
        text="/admin",
    )

    with patch("aiogram.Bot.send_message", new_callable=AsyncMock) as mock_send_message:
        await router.message(message)

        mock_send_message.assert_called_once_with(
            message.chat.id, "🚫 У вас нет доступа.", reply_markup=mock.ANY
        )
