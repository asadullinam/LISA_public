from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Integer,
)

Base = declarative_base()


class User(Base):
    """Модель таблицы users, содержащая информацию о пользователях."""

    __tablename__ = "users"

    user_telegram_id = Column(
        String, primary_key=True
    )  # Уникальный Telegram ID пользователя
    subscription_status = Column(String)  # Статус подписки ('active' / 'inactive')
    use_trial_period = Column(Boolean)  # Использовал ли пользователь пробный период

    # Связь один ко многим с таблицей Key (у пользователя может быть несколько ключей)
    keys = relationship("VpnKey", back_populates="user", cascade="all, delete-orphan")


class VpnKey(Base):
    """Модель таблицы keys, содержащая информацию о VPN-ключах."""

    __tablename__ = "keys"

    key_id = Column(String, primary_key=True)  # Уникальный идентификатор ключа
    user_telegram_id = Column(
        String, ForeignKey("users.user_telegram_id")
    )  # telegram_id пользователя

    # Связь с таблицей User (обратная связь)
    user = relationship("User", back_populates="keys")

    start_date = Column(DateTime)  # Дата начала подписки
    expiration_date = Column(DateTime)  # Дата окончания подписки

    name = Column(String, default=None)  # имя ключа
    used_bytes_last_month = Column(
        Integer, default=0
    )  # использовано байтов к концу прошлого месяца
    protocol_type = Column(String, default="Outline")  # Тип протокола (Outline/VLESS)

    server_id = Column(
        Integer, ForeignKey("servers.id")
    )  # ID сервера, на котором находится ключ

    # Связь с таблицей Server (каждый ключ привязан к серверу)
    server = relationship("Server", back_populates="keys")


# Определение таблицы Servers
class Server(Base):
    """Модель таблицы servers, содержащая информацию о серверах VPN."""

    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, autoincrement=True)  # Уникальный ID сервера
    ip = Column(
        String, default=None
    )  # IP-адрес сервера (заполняется для VLESS-сервера)
    password = Column(
        String, default=None
    )  # Пароль администратора (заполняется для VLESS-сервера)
    api_url = Column(
        String, default=None
    )  # API URL сервера (заполняется для Outline-сервера)
    cert_sha256 = Column(
        String, default=None
    )  # SHA-256 сертификат API (заполняется для Outline-сервера)
    cnt_users = Column(Integer, default=0)  # Количество пользователей на сервере
    protocol_type = Column(String, default="Outline")  # Тип VPN-протокола сервера

    # Связь один ко многим с таблицей Key (на сервере может быть несколько ключей)
    keys = relationship("VpnKey", back_populates="server")
