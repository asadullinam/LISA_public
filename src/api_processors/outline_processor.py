import asyncio
import base64
import json
import re
import typing
import logging
from typing import Optional

import aiohttp
import asyncssh
from coolname import generate_slug

from api_processors.key_models import OutlineKey
from api_processors.base_processor import BaseProcessor
from bot.routers.admin_router_sending_message import (
    send_error_report,
    send_new_server_report,
)

logger = logging.getLogger(__name__)


def get_db_processor():
    from initialization.db_processor_init import db_processor

    return db_processor


class OutlineServerErrorException(Exception):
    """
    Исключение, возникающее при ошибках на сервере Outline
    """

    pass


def get_aiohttp_fingerprint(ssl_assert_fingerprint: str) -> aiohttp.Fingerprint:
    """
    Преобразует строку с отпечатком SSL в aiohttp.Fingerprint
    :param ssl_assert_fingerprint:
    :return: aiohttp.Fingerprint
    """
    fingerprint = ssl_assert_fingerprint.replace(":", "")
    return aiohttp.Fingerprint(base64.b16decode(fingerprint, casefold=True))


class OutlineProcessor(BaseProcessor):
    """
    Класс для работы с сервером Outline
    """

    def __init__(self):
        self.api_url = None
        self.cert_sha256 = None
        self.session: aiohttp.ClientSession | None = None
        self.server_id = None

    @staticmethod
    def create_server_session_by_id(func) -> typing.Callable:
        """
        Декоратор для создания сессии для сервера по его id
        Если сессия уже создана, то она не будет создана заново
        :return:
        """

        async def wrapper(self, *args, **kwargs):
            if self.session is None:
                if kwargs.get("server_id") is None:
                    raise ValueError(
                        "!!!server_id must be passed as a keyword argument!!!"
                    )

                server_id = kwargs.get("server_id")

                server = get_db_processor().get_server_by_id(server_id)
                self.api_url = server.api_url
                self.server_id = server_id
                connector = aiohttp.TCPConnector(
                    ssl=get_aiohttp_fingerprint(
                        ssl_assert_fingerprint=server.cert_sha256
                    )
                )
                session = aiohttp.ClientSession(connector=connector)
                self.session = session

            return await func(self, *args, **kwargs)

        return wrapper

    async def create_server_session(self, user_id : int | None = None) -> None:
        """
        Инициализирует сессию HTTP-клиента для сервера с минимальным числом пользователей.

        Метод выполняет следующие шаги:
        1. Получает сервер с минимальным количеством пользователей, использующий протокол "Outline".
        2. Сохраняет URL API и идентификатор сервера в атрибутах объекта.
        3. Создает `aiohttp.ClientSession` с SSL-коннектором, настроенным на отпечаток сертификата сервера.

        :return: None
        """

        server = await get_db_processor().get_server_with_min_users("outline", user_id=user_id)

        self.api_url = server.api_url
        self.server_id = server.id

        ssl_context = get_aiohttp_fingerprint(ssl_assert_fingerprint=server.cert_sha256)
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        self.session = aiohttp.ClientSession(connector=connector)

    async def create_server_session_for_server(self, server) -> None:
        """
        Создает сессию для конкретного сервера
        :param server: Объект сервера
        :return: None
        """
        self.api_url = server.api_url
        self.server_id = server.id
        connector = aiohttp.TCPConnector(
            ssl=get_aiohttp_fingerprint(ssl_assert_fingerprint=server.cert_sha256)
        )
        self.session = aiohttp.ClientSession(connector=connector)

    async def _get_metrics(self) -> dict:
        """
        Получает метрики с Outline сервера
        :return:
        """
        async with self.session.get(url=f"{self.api_url}/metrics/transfer") as resp:
            resp_json = await resp.json()
            if resp.status >= 400 or "bytesTransferredByUserId" not in resp_json:
                raise OutlineServerErrorException("Unable to get metrics")
            return resp_json

    async def _get_raw_keys(self) -> list[OutlineKey]:
        """
        Получает все ключи с сервера
        :return:
        """
        async with self.session.get(url=f"{self.api_url}/access-keys/") as resp:
            response_data = await resp.json()
            if resp.status != 200 or "accessKeys" not in response_data:
                raise OutlineServerErrorException("Unable to retrieve keys")
        return [
            OutlineKey.from_key_json(key_data)
            for key_data in response_data.get("accessKeys", [])
        ]

    async def create_vpn_key(self, user_id, data_limit=200 * 1024**3) -> tuple[OutlineKey, int]:
        """
        Создает ключ для подключения к VPN
        :return: Кортеж из ключа и id сервера
        """
        await self.create_server_session(user_id=user_id)

        async with self.session.post(url=f"{self.api_url}/access-keys/") as resp:
            if resp.status != 201:
                raise OutlineServerErrorException("Unable to create key")
            key_data = await resp.json()

        tmp_key = OutlineKey.from_key_json(key_data)
        logger.info(tmp_key)

        key_name = generate_slug(2).replace("-", " ")
        # data_limit = 200 * 1024**3

        await self.rename_key(tmp_key.key_id, key_name)
        await self.update_data_limit(tmp_key.key_id, data_limit, self.server_id)

        key_data["name"] = key_name
        key_data["used_bytes"] = 0
        key_data["dataLimit"] = {"bytes": data_limit}

        outline_key = OutlineKey.from_key_json(key_data)
        return outline_key, self.server_id

    @create_server_session_by_id
    async def get_key_info(self, key_id: int, server_id=None) -> OutlineKey:
        """
        Получает информацию по ключу.
        Обратите внимание, что server_id необходимо передавать как именованный параметр.

        :param key_id: Идентификатор ключа.
        :param server_id: Идентификатор сервера.
        :return: Экземпляр OutlineKey с обновленной информацией.
        """
        async with self.session.get(url=f"{self.api_url}/access-keys/{key_id}") as resp:
            if resp.status != 200:
                raise OutlineServerErrorException("Unable to retrieve keys")
            key_json = await resp.json()

        client_data = OutlineKey.from_key_json(key_json)
        # print(client_data)

        current_metrics = await self._get_metrics()
        # print(json.dumps(current_metrics.get("bytesTransferredByUserId"), indent=4))

        client_data.used_bytes = current_metrics.get(
            "bytesTransferredByUserId", {}
        ).get(str(client_data.key_id), 0)
        return client_data

    @create_server_session_by_id
    async def delete_key(self, key_id: int, server_id=None) -> bool:
        """
        Удаляет ключ с сервера.

        :param key_id: Идентификатор ключа.
        :param server_id: Идентификатор сервера.
        :return: True, если удаление прошло успешно.
        """
        async with self.session.delete(
            url=f"{self.api_url}/access-keys/{key_id}"
        ) as resp:
            return resp.status == 204

    @create_server_session_by_id
    async def rename_key(self, key_id, new_key_name, server_id=None) -> bool:
        """
        Переименовывает ключ.

        :param key_id: Идентификатор ключа.
        :param new_key_name: Новое имя ключа.
        :param server_id: Идентификатор сервера.
        :return: True, если операция прошла успешно.
        """
        async with self.session.put(
            url=f"{self.api_url}/access-keys/{key_id}/name", data={"name": new_key_name}
        ) as resp:
            return resp.status == 204

    async def _fulfill_keys_with_metrics(
        self, keys: list[OutlineKey]
    ) -> list[OutlineKey]:
        """
        Обогащает список ключей информацией о переданных данных.

        :param keys: Список OutlineKey.
        :return: Обновленный список OutlineKey.
        """
        current_metrics = await self._get_metrics()
        for key in keys:
            key.used_bytes = current_metrics.get("bytesTransferredByUserId", {}).get(
                key.key_id, 0
            )
        return keys

    @create_server_session_by_id
    async def get_keys(self, server_id) -> list[OutlineKey]:
        """
        Получает список всех ключей с сервера Outline.
        """
        raw_keys = await self._get_raw_keys()
        result_keys = await self._fulfill_keys_with_metrics(keys=raw_keys)
        return result_keys

    @create_server_session_by_id
    async def update_data_limit(
        self, key_id: int, new_limit_bytes: int, server_id: int = None, key_name=None
    ) -> bool:
        """
        Устанавливает лимит передачи данных для ключа.

        :param key_id: Идентификатор ключа.
        :param new_limit_bytes: Лимит в байтах.
        :return: True, если операция прошла успешно.
        """
        data = {"limit": {"bytes": new_limit_bytes}}
        async with self.session.put(
            url=f"{self.api_url}/access-keys/{key_id}/data-limit", json=data
        ) as resp:
            return resp.status == 204

    @create_server_session_by_id
    async def delete_data_limit(self, key_id: int, server_id: int) -> bool:
        """
        Убирает лимит передачи данных для ключа.

        :param key_id: Идентификатор ключа.
        :return: True, если операция прошла успешно.
        """
        async with self.session.delete(
            url=f"{self.api_url}/access-keys/{key_id}/data-limit"
        ) as resp:
            return resp.status == 204

    async def get_transferred_data(self) -> dict:
        """
        Получает данные о передаче для всех ключей.

        :return: Словарь с информацией о переданных байтах по каждому ключу.
        """
        async with self.session.get(url=f"{self.api_url}/metrics/transfer") as resp:
            resp_json = await resp.json()
            if resp.status >= 400 or "bytesTransferredByUserId" not in resp_json:
                raise OutlineServerErrorException("Unable to get metrics")
        return resp_json

    async def get_server_info(self, server) -> dict:
        """
        Получает информацию о сервере.

        :param server: Объект сервера с полями api_url и cert_sha256.
        :return: Словарь с информацией о сервере.
        """

        ssl_context = get_aiohttp_fingerprint(ssl_assert_fingerprint=server.cert_sha256)
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url=f"{server.api_url}/server") as resp:
                resp_json = await resp.json()
                if resp.status != 200:
                    raise OutlineServerErrorException(
                        "Unable to get information about the server"
                    )
        return resp_json

    async def set_server_name(self, name: str) -> bool:
        """
        Переименовывает сервер.

        :param name: Новое имя сервера.
        :return: True, если операция прошла успешно.
        """
        data = {"name": name}
        async with self.session.put(url=f"{self.api_url}/name", json=data) as resp:
            return resp.status == 204

    async def set_hostname(self, hostname: str) -> bool:
        """
        Изменяет hostname для доступа к ключам.

        :param hostname: Новый hostname.
        :return: True, если операция прошла успешно.
        """
        data = {"hostname": hostname}
        async with self.session.put(
            url=f"{self.api_url}/server/hostname-for-access-keys", json=data
        ) as resp:
            return resp.status == 204

    async def get_metrics_status(self) -> bool:
        """
        Проверяет, включены ли метрики на сервере.

        :return:
        """
        async with self.session.get(url=f"{self.api_url}/metrics/enabled") as resp:
            resp_json = await resp.json()
            return resp_json.get("metricsEnabled", False)

    async def set_metrics_status(self, status: bool) -> bool:
        """
        Включает или выключает передачу метрик.

        :param status: True для включения, False для выключения.
        :return: True, если операция прошла успешно.
        """
        data = {"metricsEnabled": status}
        async with self.session.put(
            url=f"{self.api_url}/metrics/enabled", json=data
        ) as resp:
            return resp.status == 204

    async def set_port_new_for_access_keys(self, port: int) -> bool:
        """
        Устанавливает порт для создания новых ключей.

        :param port: Порт (от 1 до 65535).
        :return: True, если операция прошла успешно.
        :raises OutlineServerErrorException: При некорректном порте или конфликте.
        """
        data = {"port": port}
        async with self.session.put(
            url=f"{self.api_url}/server/port-for-new-access-keys", json=data
        ) as resp:
            if resp.status == 400:
                raise OutlineServerErrorException(
                    "The requested port wasn't an integer from 1 through 65535, or the request had no port parameter."
                )
            elif resp.status == 409:
                raise OutlineServerErrorException(
                    "The requested port was already in use by another service."
                )
            return resp.status == 204

    async def set_data_limit_for_all_keys(self, limit_bytes: int) -> bool:
        """
        Устанавливает лимит передачи данных для всех ключей.

        :param limit_bytes: Лимит в байтах.
        :return: True, если операция прошла успешно.
        """
        data = {"limit": {"bytes": limit_bytes}}
        async with self.session.put(
            url=f"{self.api_url}/server/access-key-data-limit", json=data
        ) as resp:
            return resp.status == 204

    async def delete_data_limit_for_all_keys(self) -> bool:
        """
        Убирает лимит передачи данных для всех ключей.

        :return: True, если операция прошла успешно.
        """
        async with self.session.delete(
            url=f"{self.api_url}/server/access-key-data-limit"
        ) as resp:
            return resp.status == 204

    async def _close(self) -> None:
        """
        Закрывает активную сессию.
        """
        if self.session:
            await self.session.close()

    async def close(self):
        """
        Публичный метод для закрытия сессии.
        """
        if self.session:
            await self.session.close()

    def __del__(self) -> None:
        """
        Деструктор, пытающийся корректно закрыть сессию при уничтожении объекта.
        """
        if self.session is None:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._close())
        except RuntimeError:
            # Нет активного event loop — пропускаем асинхронное закрытие
            pass

    @staticmethod
    def extract_outline_config(output: str) -> dict | None:
        """
        Извлекает конфигурацию сервера Outline из текстового вывода.

        :param output: Строка с JSON-конфигурацией.
        :return: Словарь с конфигурацией или None.
        """
        match = re.search(r"(\{[^}]+\})", output)
        if match:
            json_str = match.group(1)
            try:
                config = json.loads(json_str)
                if "apiUrl" in config and "certSha256" in config:
                    return config
            except json.JSONDecodeError:
                pass
        return None

    async def setup_server(self, server) -> bool:
        """
        Устанавливает сервер Outline, выполняя установку необходимых пакетов через SSH и извлекая конфигурацию.
        В случае неудачи делает до 5 попыток с паузой 10 секунд между ними.

        :param server: Объект сервера с необходимыми полями (ip, password и т.д.).
        :return: True, если установка прошла успешно, иначе False.
        """
        max_attempts = 5
        for attempt in range(max_attempts):
            cmd_update = "sudo apt update"
            cmd_install_outline = (
                'sudo bash -c "$(wget -qO- https://raw.githubusercontent.com/Jigsaw-Code/outline-server/'
                'master/src/server_manager/install_scripts/install_server.sh)"'
            )
            try:
                async with asyncssh.connect(
                    host=server.ip,
                    username="root",
                    password=server.password,
                    known_hosts=None,
                ) as conn:
                    result_update = await conn.run(cmd_update)
                    logger.info("Вывод обновления:\n" + result_update.stdout)
                    if result_update.exit_status != 0:
                        raise Exception(
                            f"Ошибка выполнения обновления: {result_update.stderr}"
                        )
                    result_install = await conn.run(cmd_install_outline, input="y\n")
                    stdout_outline = result_install.stdout
                    stderr_outline = result_install.stderr
                    logger.info("Вывод установки Outline:\n" + stdout_outline)
                    if stderr_outline:
                        logger.error("Ошибка установки Outline:\n" + stderr_outline)
                        raise Exception("Ошибка установки Outline")
                    config = self.extract_outline_config(stdout_outline)
                    if config is None:
                        raise Exception("Ошибка при извлечении конфигурации Outline")
                    get_db_processor().update_server_by_id(
                        server.id, config["apiUrl"], config["certSha256"]
                    )
                    logger.info(f"🎉 Сервер Outline установлен")
                    await send_new_server_report(
                        server_id=server.id,
                        ip=server.ip,
                        protocol="outline",
                        api_url=config["apiUrl"],
                        cert_sha256=config["certSha256"],
                    )
                    await asyncio.sleep(10)
                    return True  # Успешно – возвращаем True
            except Exception as e:
                if attempt != 0:
                    await send_error_report(e)
                logger.error(f"Попытка {attempt + 1}/{max_attempts} не удалась: {e}")
                if attempt < max_attempts - 1:
                    logger.info("Повторная попытка через 10 секунд...")
                    await asyncio.sleep(10)
        return False

    @create_server_session_by_id
    async def extend_data_limit_plus_200gb(self, key_id: int, server_id=None) -> bool:
        """
        Увеличивает лимит для ключа: "текущий used_bytes + 200 ГБ".
        Возвращает True в случае успеха.

        :param key_id: идентификатор ключа Outline
        :param server_id: ID сервера (передавать как именованный аргумент)
        """
        try:
            # 1) Узнаём текущий usage (сколько уже потрачено)
            usage_info = await self.get_key_info(key_id=key_id, server_id=server_id)
            used_bytes = usage_info.used_bytes

            # 2) Складываем used_bytes + 200 ГБ
            addition_limit = 200 * 1024**3  # 200 GB в байтах
            new_limit_bytes = used_bytes + addition_limit

            # 3) Обновляем лимит
            updated = await self.update_data_limit(
                key_id=key_id,
                new_limit_bytes=new_limit_bytes,
                server_id=server_id,
            )
            if updated:
                logger.info(
                    f"[Outline] Лимит ключа {key_id} обновлён: {new_limit_bytes} байт (израсходовано={used_bytes})."
                )
            else:
                logger.warning(
                    f"[Outline] Не удалось обновить лимит ключа {key_id} на сервере {server_id}."
                )
            return updated
        except Exception as e:
            logger.error(f"[Outline] Ошибка при увеличении лимита: {e}")
            return False
