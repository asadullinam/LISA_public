import os
import pytest
from api_processors.key_models import VlessKey


@pytest.mark.asyncio
async def test_create_server_session(mock_vless_processor):
    """Тестирование создания соединения с сервером
    создаем объект Server с паролем и логином из env
    запускаем функцию с сервером
    проверяем что сессия создалась
    """
    await mock_vless_processor.create_server_session()
    assert mock_vless_processor.ip == os.getenv("VLESS_IP")
    assert mock_vless_processor.server_id == 1


@pytest.mark.asyncio
async def test_create_vpn_key(mock_vless_processor, mock_vless_vpn_key):
    """Тестирование создания ключа для обычного пользователя и админа"""
    key, server_id = await anext(mock_vless_vpn_key)
    assert key is not None
    assert key.data_limit == 200 * 1024**3
    assert key.name is not None
    assert key.used_bytes is not None


@pytest.mark.asyncio
async def test_delete_key(mock_vless_processor, mock_vless_vpn_key):
    """Тестирование возможности удалить ключ"""
    key, server_id = await anext(mock_vless_vpn_key)
    delete_status = await mock_vless_processor.delete_key(key.key_id)
    assert delete_status is True


@pytest.mark.asyncio
async def test_valid_get_key_info(mock_vless_processor, mock_vless_vpn_key):
    """Тестирование получение информации о существующих ключах"""
    key, server_id = await anext(mock_vless_vpn_key)
    key_info = await mock_vless_processor.get_key_info(key.key_id, server_id=server_id)
    assert isinstance(key_info, VlessKey)
    assert key_info.key_id == key.key_id
    assert key_info.name == key.name
    assert key_info.data_limit == key.data_limit


@pytest.mark.asyncio
async def test_invalid_get_key_info_(mock_vless_processor):
    """Тестирование получение информации о несуществующих ключах"""
    with pytest.raises(
        ValueError, match="!!!server_id must be passed as a keyword argument!!!"
    ):
        await mock_vless_processor.get_key_info("invalid_key_id")
        await mock_vless_processor.get_key_info(
            "invalid_key_id", "not_keyword_server_id"
        )


@pytest.mark.asyncio
async def test_rename_key(mock_vless_processor, mock_vless_vpn_key):
    """Тестирование переименования ключа"""
    key, server_id = await anext(mock_vless_vpn_key)
    new_key_name = "new_key_name"
    rename_status = await mock_vless_processor.rename_key(
        key.key_id, server_id, new_key_name
    )
    assert rename_status is True
    key_info = await mock_vless_processor.get_key_info(key.key_id, server_id=server_id)
    assert key_info.name == new_key_name


@pytest.mark.asyncio
async def test_update_data_limit(mock_vless_processor, mock_vless_vpn_key):
    key, server_id = await anext(mock_vless_vpn_key)
    assert key.data_limit == 200 * 1024**3
    new_data_limit = 300 * 10**9
    await mock_vless_processor.update_data_limit(
        key.key_id, new_data_limit, server_id=server_id, key_name=key.name
    )
    key_info = await mock_vless_processor.get_key_info(key.key_id, server_id=server_id)
    assert key_info.data_limit == new_data_limit
    assert key_info.name == key.name
