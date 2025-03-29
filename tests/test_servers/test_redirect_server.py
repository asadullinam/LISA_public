from unittest import mock
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from dotenv import load_dotenv
import os

from api_processors.outline_processor import OutlineProcessor
from api_processors.vless_processor import VlessProcessor
from servers.redirect_server import redirect_server
from database.models import Server, VpnKey

load_dotenv()


@pytest.fixture
def mock_outline_server():
    """Mock-сервер"""
    id = 1
    api_url = os.getenv("OUTLINE_API_URL")
    cert_sha256 = os.getenv("OUTLINE_CERT_SHA")
    protocol_type = "Outline"
    return Server(
        id=id, api_url=api_url, cert_sha256=cert_sha256, protocol_type=protocol_type
    )


@pytest.fixture
def mock_outline_processor(mock_outline_server):
    """Фикстура для процессора с патчем."""
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
        await mock_vless_processor.delete_key(key.key_id, server_id=server_id)


@pytest.fixture
def client():
    return TestClient(redirect_server)


@pytest.mark.asyncio
@patch("utils.get_processor.get_processor")
@patch("database.db_processor.DbProcessor.get_key_by_id")
async def test_open_connection_outline(
    mock_get_key_by_id,
    mock_get_processor,
    mock_outline_processor,
    mock_outline_vpn_key,
    client,
):
    key, server_id = await anext(mock_outline_vpn_key)

    mock_get_key_by_id.return_value = VpnKey(
        key_id=key.key_id,
        start_date="2025-01-01",
        expiration_date="2025-01-31",
        name=key.name,
        protocol_type="Outline",
        server_id=server_id,
    )
    mock_get_processor.return_value = mock_outline_processor

    response = client.get(f"/open/{key.key_id}")

    assert response.status_code == 200
    assert "Launch Outline" in response.text


@pytest.mark.asyncio
@patch("utils.get_processor.get_processor")
@patch("database.db_processor.DbProcessor.get_key_by_id")
async def test_open_connection_vless(
    mock_get_key_by_id,
    mock_get_processor,
    mock_vless_processor,
    mock_vless_vpn_key,
    client,
):
    key, server_id = await anext(mock_vless_vpn_key)

    mock_get_key_by_id.return_value = VpnKey(
        key_id=key.key_id,
        start_date="2025-01-01",
        expiration_date="2025-01-31",
        name=key.name,
        protocol_type="Vless",
        server_id=server_id,
    )
    mock_get_processor.return_value = mock_vless_processor

    response = client.get(f"/open/{key.key_id}")

    assert response.status_code == 200
    assert "Launch Hiddify" in response.text
