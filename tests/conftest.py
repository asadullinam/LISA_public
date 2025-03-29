from dotenv import load_dotenv
from api_processors.outline_processor import OutlineProcessor
from api_processors.vless_processor import VlessProcessor
from database.models import Server
from unittest import mock
import os
import pytest

load_dotenv()


@pytest.fixture
def mock_outline_server():
    """Mock-сервер"""
    server_id = 1
    api_url = os.getenv("OUTLINE_API_URL")
    cert_sha256 = os.getenv("OUTLINE_CERT_SHA")
    protocol_type = "Outline"

    return Server(
        id=server_id,
        api_url=api_url,
        cert_sha256=cert_sha256,
        protocol_type=protocol_type,
    )


@pytest.fixture
def mock_outline_processor(mock_outline_server):
    """Фикстура для процессора с патчем."""
    with mock.patch(
        "database.db_processor.DbProcessor.get_server_with_min_users",
        return_value=mock_outline_server,
    ):
        processor = OutlineProcessor()
        yield processor


@pytest.fixture
@pytest.mark.asyncio
async def mock_outline_vpn_key(mock_outline_processor):
    """Фикстура для создания и автоматического удаления VPN-ключа."""
    key, server_id = await mock_outline_processor.create_vpn_key()
    try:
        yield key, server_id
    finally:
        await mock_outline_processor.delete_key(key.key_id, server_id=server_id)


@pytest.fixture
def mock_vless_server():
    """Mock-сервер"""
    id = 1
    ip = os.getenv("VLESS_IP")
    password = os.getenv("VLESS_PASSWORD")
    protocol_type = "VLESS"
    return Server(id=id, ip=ip, password=password, protocol_type=protocol_type)


@pytest.fixture
def mock_vless_processor(mock_vless_server):
    """Фикстура для процессора с патчем."""
    with mock.patch(
        "database.db_processor.DbProcessor.get_server_with_min_users",
        return_value=mock_vless_server,
    ):
        processor = VlessProcessor(os.getenv("VLESS_IP"), os.getenv("VLESS_PASSWORD"))
        yield processor


@pytest.fixture
@pytest.mark.asyncio
async def mock_vless_vpn_key(mock_vless_processor):
    """Фикстура для создания и автоматического удаления VPN-ключа."""
    key, server_id = await mock_vless_processor.create_vpn_key()
    try:
        yield key, server_id
    finally:
        await mock_processor.delete_key(key.key_id, server_id=server_id)
