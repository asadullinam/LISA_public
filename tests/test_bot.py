import os
import warnings
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import sessionmaker

from bot.utils.outline_processor import OutlineProcessor
from database.db_processor import Base, DbProcessor
from logger.logging_config import setup_logger


@pytest.fixture(scope="session", autouse=True)
def fix_logger_path():
    log_file_path = "/Users/aydar/Desktop/VPN2_2/LISA/src/logger/bot.log"
    os.environ["LOG_FILE_PATH"] = log_file_path
    setup_logger()


@pytest.fixture
def test_db():
    """Создаёт тестовую базу данных в памяти."""
    engine = create_engine("sqlite:///:memory:", echo=False)  # База данных в памяти
    Base.metadata.create_all(engine)  # Используем Base напрямую
    Session = sessionmaker(bind=engine)
    yield Session
    engine.dispose()


@pytest.fixture
def db_processor(test_db):
    """Создаёт экземпляр DbProcessor с тестовой базой."""
    processor = DbProcessor()
    processor.engine = test_db.kw["bind"]
    processor.Session = test_db
    return processor


def test_key_creation(db_processor):
    """Тест добавления ключа в базу данных."""
    session = db_processor.get_session()
    user = DbProcessor.User(
        user_telegram_id="12345", subscription_status="active", use_trial_period=False
    )
    session.add(user)
    session.commit()
    key = DbProcessor.Key(
        key_id="key123",
        user_telegram_id="12345",
        expiration_date=datetime(2024, 12, 31, 23, 59, 59),  # Объект datetime
        start_date=datetime(2024, 12, 1, 0, 0, 0),  # Объект datetime
    )
    session.add(key)
    session.commit()
    key_from_db = session.query(DbProcessor.Key).filter_by(key_id="key123").first()
    assert key_from_db is not None
    assert key_from_db.user_telegram_id == "12345"
    session.close()


def test_key_creation_duplicate(db_processor):
    """Тест добавления дублирующего ключа в базу данных."""
    session = db_processor.get_session()
    user = DbProcessor.User(
        user_telegram_id="12345", subscription_status="active", use_trial_period=False
    )
    session.add(user)
    session.commit()

    key = DbProcessor.Key(
        key_id="key123",
        user_telegram_id="12345",
        expiration_date=datetime(2024, 12, 31, 23, 59, 59),
        start_date=datetime(2024, 12, 1, 0, 0, 0),
    )
    session.add(key)
    session.commit()

    duplicate_key = DbProcessor.Key(
        key_id="key123",
        user_telegram_id="12345",
        expiration_date=datetime(2024, 12, 31, 23, 59, 59),
        start_date=datetime(2024, 12, 1, 0, 0, 0),
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SAWarning)  # Подавляем SAWarning
        with pytest.raises(Exception):
            session.add(duplicate_key)
            session.commit()
    session.close()


def test_delete_key_from_database(db_processor):
    """Тест удаления ключа из базы данных."""
    session = db_processor.get_session()
    key = DbProcessor.Key(
        key_id="key123",
        user_telegram_id="12345",
        expiration_date=datetime(2024, 12, 31, 23, 59, 59),
        start_date=datetime(2024, 12, 1, 0, 0, 0),
    )
    session.add(key)
    session.commit()

    session.delete(key)
    session.commit()

    deleted_key = session.query(DbProcessor.Key).filter_by(key_id="key123").first()
    assert deleted_key is None
    session.close()


def test_update_key_data_limit(outline_processor, mock_client):
    """Тест обновления лимита данных у ключа."""
    mock_client.add_data_limit.return_value = "Data Limit Updated"
    status = outline_processor.upd_limit("key123", 10.0)
    assert status == "Data Limit Updated"
    mock_client.add_data_limit.assert_called_once_with(
        "key123", OutlineProcessor.gb_to_bytes(10.0)
    )


def test_delete_non_existent_key(outline_processor, mock_client):
    """Тест удаления несуществующего ключа."""
    mock_client.delete_key.side_effect = Exception("Key not found")
    with pytest.raises(Exception, match="Key not found"):
        outline_processor.delete_key("nonexistent_key")
    mock_client.delete_key.assert_called_once_with("nonexistent_key")


def test_create_vpn_key_duplicate(outline_processor, mock_client):
    """Тест попытки создания дублирующего VPN-ключа."""
    mock_client.get_keys.return_value = [
        MagicMock(key_id="1"),
        MagicMock(key_id="2"),
        MagicMock(key_id="3"),
    ]
    mock_client.create_key.side_effect = Exception("Key already exists")
    with pytest.raises(Exception, match="Key already exists"):
        outline_processor.create_vpn_key()
    mock_client.get_keys.assert_called_once()
    mock_client.create_key.assert_called_once_with(
        key_id=4, name="VPN Key4", data_limit=OutlineProcessor.gb_to_bytes(1)
    )


def test_get_server_information_error(outline_processor, mock_client):
    """Тест ошибки получения информации о сервере."""
    mock_client.get_server_information.side_effect = Exception("Server not reachable")
    with pytest.raises(Exception, match="Server not reachable"):
        outline_processor.get_service_info()
    mock_client.get_server_information.assert_called_once()


def test_key_creation(db_processor):
    """Тест добавления ключа в базу данных."""
    session = db_processor.get_session()

    user = DbProcessor.User(
        user_telegram_id="12345", subscription_status="active", use_trial_period=False
    )
    session.add(user)
    session.commit()

    key = DbProcessor.Key(
        key_id="key123",
        user_telegram_id="12345",
        expiration_date=datetime(2024, 12, 31, 23, 59, 59),
        start_date=datetime(2024, 12, 1, 0, 0, 0),
    )
    session.add(key)
    session.commit()

    # Проверяем, что ключ был добавлен
    key_from_db = session.query(DbProcessor.Key).filter_by(key_id="key123").first()
    assert key_from_db is not None
    assert key_from_db.user_telegram_id == "12345"
    assert key_from_db.expiration_date == datetime(2024, 12, 31, 23, 59, 59)
    assert key_from_db.start_date == datetime(2024, 12, 1, 0, 0, 0)
    session.close()


def test_update_database_with_key(db_processor):
    """Тест обновления базы данных методом update_database_with_key."""
    processor = db_processor
    session = processor.get_session()
    key = DbProcessor.Key(  # Создаём объект ключа
        key_id="test_key",
        user_telegram_id="12345",
        expiration_date=datetime(2024, 12, 31, 23, 59, 59),
        start_date=datetime(2024, 12, 1, 0, 0, 0),
    )
    processor.update_database_with_key(user_id="12345", key=key, period="1 month")
    user_from_db = (
        session.query(DbProcessor.User).filter_by(user_telegram_id="12345").first()
    )
    assert user_from_db is not None
    assert user_from_db.subscription_status == "active"
    keys_from_db = (
        session.query(DbProcessor.Key).filter_by(user_telegram_id="12345").all()
    )
    assert len(keys_from_db) == 1
    session.close()


@pytest.fixture
def mock_client():
    """Создаёт мок клиента для тестирования OutlineProcessor."""
    client = MagicMock()
    return client


@pytest.fixture
def outline_processor(mock_client):
    """Создаёт экземпляр OutlineProcessor с моковым клиентом."""
    return OutlineProcessor(client=mock_client)


def test_gb_to_bytes():
    """Тест конвертации ГБ в байты."""
    result = OutlineProcessor.gb_to_bytes(1.5)
    assert result == 1.5 * 1024**3  # Проверяем, что результат соответствует ожидаемому


def test_get_keys(outline_processor, mock_client):
    """Тест получения ключей."""
    mock_client.get_keys.return_value = ["key1", "key2", "key3"]

    keys = outline_processor.get_keys()
    assert keys == ["key1", "key2", "key3"]
    mock_client.get_keys.assert_called_once()


def test_get_key_info(outline_processor, mock_client):
    """Тест получения информации о ключе."""
    mock_client.get_key.return_value = "Key Info"
    key_info = outline_processor.get_key_info("key123")
    assert key_info == "Key Info"
    mock_client.get_key.assert_called_once_with("key123")


def test_create_new_key(outline_processor, mock_client):
    """Тест создания нового ключа."""
    mock_client.create_key.return_value = "New Key Info"
    new_key_info = outline_processor._create_new_key(
        key_id="key123", name="Test Key", data_limit_gb=2.5
    )
    assert new_key_info == "New Key Info"
    mock_client.create_key.assert_called_once_with(
        key_id="key123", name="Test Key", data_limit=OutlineProcessor.gb_to_bytes(2.5)
    )


def test_rename_key(outline_processor, mock_client):
    """Тест переименования ключа."""
    mock_client.rename_key.return_value = "Renamed"
    rename_status = outline_processor.rename_key("key123", "New Key Name")
    assert rename_status == "Renamed"
    mock_client.rename_key.assert_called_once_with("key123", "New Key Name")


def test_update_limit(outline_processor, mock_client):
    """Тест обновления лимита трафика."""
    mock_client.add_data_limit.return_value = "Limit Updated"
    update_status = outline_processor.upd_limit("key123", 5.0)
    assert update_status == "Limit Updated"
    mock_client.add_data_limit.assert_called_once_with(
        "key123", OutlineProcessor.gb_to_bytes(5.0)
    )


def test_delete_limit(outline_processor, mock_client):
    """Тест удаления лимита трафика."""
    mock_client.delete_data_limit.return_value = "Limit Deleted"
    delete_status = outline_processor.delete_limit("key123")
    assert delete_status == "Limit Deleted"
    mock_client.delete_data_limit.assert_called_once_with("key123")


def test_delete_key(outline_processor, mock_client):
    """Тест удаления ключа."""
    mock_client.delete_key.return_value = "Key Deleted"
    delete_status = outline_processor.delete_key("key123")
    assert delete_status == "Key Deleted"
    mock_client.delete_key.assert_called_once_with("key123")


def test_get_service_info(outline_processor, mock_client):
    """Тест получения информации о сервере."""
    mock_client.get_server_information.return_value = "Service Info"
    service_info = outline_processor.get_service_info()
    assert service_info == "Service Info"
    mock_client.get_server_information.assert_called_once()


def test_create_vpn_key(outline_processor, mock_client):
    """Тест создания нового VPN-ключа."""
    mock_client.get_keys.return_value = [
        MagicMock(key_id="1"),
        MagicMock(key_id="2"),
        MagicMock(key_id="3"),
    ]
    mock_client.create_key.return_value = "VPN Key Created"

    new_key = outline_processor.create_vpn_key()
    assert new_key == "VPN Key Created"
    mock_client.get_keys.assert_called_once()
    mock_client.create_key.assert_called_once_with(
        key_id=4, name="VPN Key4", data_limit=OutlineProcessor.gb_to_bytes(1)
    )
