from abc import ABC, abstractmethod

from api_processors.key_models import OutlineKey, VlessKey


class BaseProcessor(ABC):
    @abstractmethod
    def create_server_session(self):
        """
        Создает сессию для работы с сервером.
        """
        pass

    @abstractmethod
    def create_vpn_key(self):
        """
        Создает VPN-ключ на сервере и возвращает строку ключа.
        """
        pass

    @abstractmethod
    def delete_key(self, key_id: str):
        """
        Удаляет ключ с сервера.
        Возвращает результат удаления.
        """
        pass

    @abstractmethod
    def rename_key(self, key_id: str, server_id: str, new_key_name: str):
        """
        Переименовывает ключ на сервере.
        Возвращает успешность операции.
        """
        pass

    @abstractmethod
    def get_key_info(self, key_id: str, server_id: int = None):
        """
        Получает информацию о ключе с сервера.
        Возвращает объект с информацией о ключе.
        """
        pass

    @abstractmethod
    def get_server_info(self, server):
        """
        Получает информацию о сервере.
        Возвращает словарь с данными о сервере.
        """
        pass
