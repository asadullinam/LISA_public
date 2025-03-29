from coolname import generate_slug
from dotenv import load_dotenv
import requests
import asyncssh
import asyncio
import urllib3
import json
import uuid
import os
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from api_processors.base_processor import BaseProcessor
from api_processors.key_models import VlessKey

from bot.routers.admin_router_sending_message import (
    send_error_report,
    send_new_server_report,
)

logger = logging.getLogger(__name__)

load_dotenv()

NAME_VPN_CONFIG = "MyNewInbound"


class VlessProcessor(BaseProcessor):
    def __init__(self, ip, password):
        self.ip = None
        self.sub_port = None
        self.port_panel = None
        self.host = None
        self.data = None
        self.ses = None
        self.con = None
        self.server_id = None

    @staticmethod
    def create_server_session_by_id(func):
        """
        Декоратор для создания сессии с сервером по переданному ID сервера.

        :param func: Функция, которую декоратор оборачивает.
        :return: Результат выполнения функции, обернутой декоратором.

        Алгоритм работы:
        1. Извлекает `server_id` из аргументов функции.
        2. Если `server_id` не передан, выбрасывает исключение.
        3. Использует `db_processor` для получения данных о сервере по ID.
        4. Если сервер не найден, выбрасывает исключение.
        5. Инициализирует параметры подключения (IP, порт, данные).
        6. Создает новую сессию с помощью `requests.Session`.
        7. Выполняет исходную функцию с аргументами.
        8. В случае ошибки при установке соединения выбрасывает исключение.
        """

        def wrapper(self, *args, **kwargs):
            server_id = kwargs.get("server_id")
            if server_id is None:
                raise ValueError("!!!server_id must be passed as a keyword argument!!!")

            from initialization.db_processor_init import db_processor

            server = db_processor.get_server_by_id(server_id)
            if server is None:
                raise ValueError(f"Сервер с ID {server_id} не найден в базе данных")

            self.ip = server.ip
            self.sub_port = 2096
            self.port_panel = 2053
            self.host = f"https://{self.ip}:{self.port_panel}"
            self.data = {"username": "lisa_admin", "password": server.password}

            try:
                self.ses = requests.Session()
                self.ses.verify = False
                self.con = self._connect()
            except Exception as e:
                asyncio.create_task(send_error_report(e))
                self.ses = None
                raise RuntimeError(f"Ошибка при установке соединения: {e}")

            return func(self, *args, **kwargs)

        return wrapper

    async def create_server_session(self, user_id=None):
        """
        Создает сессию для подключения к серверу с минимальным количеством пользователей для типа "vless".

        :return: `None`

        Алгоритм работы:
        1. Получает сервер с минимальным количеством пользователей для типа "vless" с использованием `db_processor`.
        2. Извлекает параметры подключения (IP, порты, данные для аутентификации).
        3. Инициализирует объект сессии с помощью `requests.Session`.
        4. Отключает проверку сертификатов с помощью `self.ses.verify = False`.
        5. Устанавливает соединение с сервером через метод `_connect()`.
        6. Сохраняет ID сервера в атрибуте `self.server_id`.
        """
        from initialization.db_processor_init import db_processor

        # if self.ses is not None:
        #     return

        server = await db_processor.get_server_with_min_users("vless", user_id=user_id)

        self.ip = server.ip
        self.sub_port = 2096
        self.port_panel = 2053
        self.host = f"https://{self.ip}:{self.port_panel}"
        self.data = {"username": "lisa_admin", "password": server.password}
        self.ses = requests.Session()
        self.ses.verify = False
        self.con = self._connect()
        self.server_id = server.id

    def _connect(self) -> bool:
        """
        Логин в панель 3x-ui. Возвращает True, если успешно.
        """
        try:
            resp = self.ses.post(f"{self.host}/login", data=self.data, timeout=10)
            resp.raise_for_status()
            resp_json = resp.json()
            if resp_json.get("success") is True:
                logger.debug(f"✅Подключение к панели 3x-ui {self.ip} прошло успешно!")
                return True
            else:
                msg = resp_json.get("msg", "Unknown error from /login")
                logger.warning(f"🛑Ошибка логина: {msg} на {self.ip}")
                return False
        except (requests.RequestException, ValueError) as e:
            logger.error(f"Ошибка сети/JSON при логине к {self.host}: {e}")
            return False

    def _reconnect(self) -> bool:
        """
        Закрывает старую сессию, создаёт новую и пробует снова залогиниться.
        """
        logger.info("Переавторизация (reconnect) в 3x-ui...")
        if self.ses:
            self.ses.close()
        self.ses = requests.Session()
        self.ses.verify = False
        self.con = self._connect()
        return self.con

    def _check_connect(self) -> bool:
        """
        Проверяем, есть ли уже inbound (подключение), или нужно создавать новое.
        """
        if not self.con:
            return False

        try:
            resource = self.ses.post(
                f"{self.host}/panel/inbound/list/", data=self.data
            ).json()
            if not resource.get("success"):
                logger.warning(
                    f'🛑Ошибка при проверке подключения: {resource.get("msg")}'
                )
                return False
            # Если inbound'ы есть, считаем, что подключение уже настроено
            if resource.get("obj") and len(resource["obj"]) > 0:
                logger.debug(f"Подключение уже есть")
                return True

            logger.warning(f"⚠️Подключение (inbound) не найдено")
            return False
        except requests.RequestException as e:
            asyncio.create_task(send_error_report(e))
            logger.error(f"Ошибка сети при _check_connect: {e}")
            return False

    def _ensure_session_ok(self) -> bool:
        """
        "Рефреш сессии": если self.con = False, пытаемся залогиниться заново.
        Возвращает True, если сессия теперь в порядке; False – если нет.
        """
        if not self.con:
            logger.info("Сессия неактивна, пробуем авторизоваться заново...")
            ok = self._reconnect()
            if not ok:
                logger.error("Не удалось переавторизоваться!")
                return False
        return True

    def _request_json(
        self,
        endpoint: str,
        data: dict = None,
        method: str = "post",
        max_retries: int = 2,
        **kwargs,
    ) -> dict | None:
        """
        Универсальный метод для запросов к 3x-UI (POST или GET) с парсингом JSON.
        Если получили ошибку/HTML, переавторизуемся и пробуем ещё раз.
        """
        if data is None:
            data = {}
        url = f"{self.host}{endpoint}"

        for attempt in range(max_retries):
            try:
                if method.lower() == "post":
                    resp = self.ses.post(url, data=data, timeout=10, **kwargs)
                else:
                    resp = self.ses.get(url, timeout=10, **kwargs)

                resp.raise_for_status()
                result = resp.json()
                return result

            except (requests.RequestException, json.JSONDecodeError) as e:
                logger.error(
                    f"Ошибка при запросе {url}, попытка {attempt + 1}/{max_retries}: {e}"
                )
                if attempt < max_retries - 1:
                    # Пробуем переавторизоваться и повторить
                    ok = self._reconnect()
                    if not ok:
                        logger.error("Переавторизация не удалась.")
                        return None
                else:
                    return None

        return None

    def _add_new_connect(self) -> tuple[bool, str]:
        """
        Добавляет новый inbound (подключение).
        """
        if not self._ensure_session_ok():
            return False, "Сессия недоступна"

        logger.debug(f"Добавляем новое подключение на сервере {self.ip}...")

        # Шаг 1: Получаем ключи (privateKey/publicKey)
        cert_ok, cert_obj_or_msg = self._get_new_x25519_cert()
        if not cert_ok:
            logger.warning(f"Не удалось получить X25519-сертификат: {cert_obj_or_msg}")
            return False, cert_obj_or_msg

        private_key = cert_obj_or_msg["privateKey"]
        public_key = cert_obj_or_msg["publicKey"]

        # Шаг 2: Собираем JSON для inbound/add
        header = {"Accept": "application/json"}
        payload = {
            "up": 0,
            "down": 0,
            "total": 0,
            "remark": NAME_VPN_CONFIG,  # Название inbound
            "enable": True,
            "expiryTime": 0,
            "listen": "",
            "port": 443,
            "protocol": "vless",
            "settings": json.dumps(
                {
                    "clients": [
                        {
                            "id": "test1",
                            "flow": "xtls-rprx-vision",
                            "email": "test1",
                            "limitIp": 0,
                            "totalGB": 0,
                            "expiryTime": 0,
                            "enable": True,
                            "tgId": "",
                            "subId": "yap2ddklr1imbhfq",
                        }
                    ],
                    "decryption": "none",
                    "fallbacks": [],
                }
            ),
            "streamSettings": json.dumps(
                {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "xver": 0,
                        "dest": "google.com:443",
                        "serverNames": ["google.com", "www.google.com"],
                        "privateKey": private_key,
                        "minClient": "",
                        "maxClient": "",
                        "maxTimediff": 0,
                        "shortIds": [
                            "03b090ff397c50b9",
                            "7ea960",
                            "765c89c0ab102d",
                            "b5b79d7c18f0",
                            "1f52d659ec",
                            "4da9671e",
                            "45a0",
                            "d3",
                        ],  # Короткий ID
                        "settings": {
                            "publicKey": public_key,
                            "fingerprint": "chrome",
                            "serverName": "",
                            "spiderX": "/",
                        },
                    },
                    "tcpSettings": {
                        "acceptProxyProtocol": False,
                        "header": {"type": "none"},
                    },
                }
            ),
            "sniffing": json.dumps({"enabled": False, "destOverride": []}),
        }

        # Шаг 3: Добавляем inbound
        resp_json = self._request_json(
            "/panel/inbound/add", data=payload, headers=header
        )
        if not resp_json:
            return False, "Пустой ответ /panel/inbound/add"
        if resp_json.get("success"):
            logger.debug("Успешно создали inbound!")
            return True, "OK"
        else:
            msg = resp_json.get("msg", "Неизвестная ошибка inbound/add")
            logger.warning(f"Ошибка при добавлении inbound: {msg}")
            return False, msg

    def _get_new_x25519_cert(self) -> tuple[bool, dict]:
        """
        Запрашивает у панели новую пару ключей (privateKey / publicKey).
        """
        if not self._ensure_session_ok():
            return False, "Сессия недоступна"

        resp_json = self._request_json("/server/getNewX25519Cert", data=self.data)
        if not resp_json:
            return False, "Не получили JSON /server/getNewX25519Cert"
        if resp_json.get("success"):
            return True, resp_json["obj"]
        else:
            return False, resp_json.get("msg", "Неизвестная ошибка")

    def _get_link(self, key_id: str, key_name: str) -> str | bool:
        """
        Генерация ссылки для клиента (vless://...) для подключения к серверу.

        :param key_id: Уникальный идентификатор ключа для клиента.
        :param key_name: Имя ключа для клиента, которое будет отображаться в ссылке.

        :return: Сгенерированная ссылка для клиента, если успешно, иначе `False`.

        Алгоритм работы:
        1. Проверяется наличие активного соединения.
        2. Выполняется POST-запрос к панели управления для получения списка inbound соединений.
        3. Проверяется наличие успешного ответа и данных о первом inbound соединении.
        4. Извлекаются параметры настройки потока (streamSettings), включая публичный ключ.
        5. Формируется ссылка для клиента с использованием полученных данных.
        6. В случае ошибок в процессе генерируется лог с подробным описанием.
        """

        if not self._ensure_session_ok():
            return False

        resource = self._request_json("/panel/inbound/list/", data=self.data)
        if not resource or not resource.get("success"):
            logger.error("Не удалось получить inbound/list для _get_link.")
            return False
        inbound_list = resource.get("obj", [])
        if not inbound_list:
            logger.error("Нет inbound'ов (пусто).")
            return False

        inbound_obj = inbound_list[0]
        stream_settings_str = inbound_obj.get("streamSettings")
        if not stream_settings_str:
            return False

        try:
            stream_settings = json.loads(stream_settings_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError при парсинге streamSettings: {e}")
            return False

        port = inbound_obj.get("port", 443)
        reality = stream_settings.get("realitySettings", {})
        sett = reality.get("settings", {})
        public_key = sett.get("publicKey", "")
        sni = "dl.google.com"
        flow = stream_settings.get("flow", "xtls-rprx-vision")
        short_ids = reality.get("shortIds", [])
        sid = short_ids[0] if short_ids else "deced1f3"

        return (
            f"vless://{key_id}@{self.ip}:{port}/?type=tcp&security=reality&pbk={public_key}"
            f"&fp=chrome&sni={sni}&sid={sid}&spx=%2F&flow={flow}#{key_name}"
        )

    async def create_vpn_key(
        self,
        user_id: int | None = None,
        expire_time: int = 0,
        sni: str = "dl.google.com",
        port: int = 443,
        data_limit: int = 200 * 1024**3,
    ) -> tuple[VlessKey, int]:
        """
        Создает новый VPN-ключ VLESS на удаленном сервере,
        помещая клиента в первый доступный inbound (или создаёт inbound, если его нет).
        ...
        """
        await self.create_server_session(user_id=user_id)
        if not self._ensure_session_ok():
            return None, "Сессия недоступна"

        inbound_list_data = self._request_json("/panel/inbound/list/", data=self.data)
        if not inbound_list_data or not inbound_list_data.get("success"):
            logger.warning(
                "Не удалось получить inbound/list, пробуем создать inbound..."
            )
            add_ok, add_msg = self._add_new_connect()
            if not add_ok:
                return None, f"Не удалось создать inbound: {add_msg}"
            inbound_list_data = self._request_json(
                "/panel/inbound/list/", data=self.data
            )
            if not inbound_list_data or not inbound_list_data.get("obj"):
                return None, "Inbound list по-прежнему пуст"

        inbound_list = inbound_list_data.get("obj", [])
        if not inbound_list:
            return None, "Нет inbound для создания клиента"
        first_inbound = inbound_list[0]
        inbound_id = first_inbound.get("id")
        if not inbound_id:
            return None, "Inbound не имеет ID"

        # 2) Формируем ссылку
        stream_settings_str = first_inbound.get("streamSettings", "{}")
        try:
            stream_settings = json.loads(stream_settings_str)
        except json.JSONDecodeError:
            logger.error("Невалидный JSON streamSettings")
            return None, "Невалидный JSON streamSettings"

        reality = stream_settings.get("realitySettings", {})
        sett = reality.get("settings", {})
        public_key = sett.get("publicKey", "")
        flow = stream_settings.get("flow", "xtls-rprx-vision")
        short_ids = reality.get("shortIds", [])
        sid = short_ids[0] if short_ids else "deced1f3"

        key_name = generate_slug(2).replace("-", " ")
        unique_id = str(uuid.uuid4())

        access_url = (
            f"vless://{unique_id}@{self.ip}:{port}/?type=tcp&security=reality&pbk={public_key}"
            f"&fp=chrome&sni={sni}&sid={sid}&spx=%2F&flow={flow}#{key_name}"
        )

        # 3) Добавляем клиента
        payload = {
            "id": inbound_id,
            "settings": json.dumps(
                {
                    "clients": [
                        {
                            "id": unique_id,
                            "alterId": 0,
                            "email": unique_id,
                            "limitIp": 5,
                            "totalGB": data_limit,
                            "expiryTime": expire_time,
                            "enable": True,
                            "flow": flow,
                            "subId": unique_id,
                            "comment": key_name,
                        }
                    ]
                }
            ),
        }
        header = {"Accept": "application/json"}
        resource = self._request_json(
            "/panel/inbound/addClient", data=payload, headers=header
        )
        if not resource:
            return None, "Нет ответа /panel/inbound/addClient"
        if resource.get("success"):
            return (
                VlessKey(
                    key_id=unique_id,
                    email=unique_id,
                    name=key_name,
                    access_url=access_url,
                    used_bytes=0,
                    data_limit=data_limit,
                ),
                self.server_id,
            )
        else:
            msg = resource.get("msg", "Неизвестная ошибка addClient")
            return None, msg

    @create_server_session_by_id
    async def rename_key(self, key_id: str, server_id: int, new_key_name: str) -> bool:
        """
        Переименовывает существующий VPN-ключ (VLESS) на удаленном сервере,
        меняя только поле 'comment'. Остальные настройки ключа не трогаются.

        :param key_id: Уникальный идентификатор ключа (client.id).
        :param server_id: Идентификатор сервера, на котором находится ключ.
        :param new_key_name: Новое имя (comment) для VPN-ключа.
        :return: True, если ключ успешно переименован, иначе False.
        """

        if not self._ensure_session_ok():
            return False

        resource = self._request_json("/panel/inbound/list/", data=self.data)
        if not resource or not resource.get("success"):
            logger.warning("Не получили inbound list при rename_key.")
            return False

        inbound_list = resource.get("obj", [])
        for inbound in inbound_list:
            inbound_id = inbound.get("id")
            settings_str = inbound.get("settings", "{}")
            try:
                inbound_settings = json.loads(settings_str)
            except json.JSONDecodeError:
                continue
            clients = inbound_settings.get("clients", [])
            for client in clients:
                if client.get("id") == key_id:
                    old_comment = client.get("comment", "")
                    client["comment"] = new_key_name
                    update_payload = {
                        "id": inbound_id,
                        "settings": json.dumps({"clients": [client]}),
                    }
                    resp = self._request_json(
                        f"/panel/inbound/updateClient/{key_id}", data=update_payload
                    )
                    if not resp:
                        logger.warning("Нет ответа updateClient (rename_key).")
                        return False
                    if resp.get("success"):
                        logger.debug(
                            f"Переименовали {key_id}: {old_comment} -> {new_key_name}"
                        )
                        return True
                    else:
                        logger.warning(f"Ошибка rename_key: {resp.get('msg')}")
                        return False
        return False

    @create_server_session_by_id
    async def delete_key(self, key_id: str, server_id: int | None = None) -> bool:
        """
        Удаляет клиентский ключ по указанному ID на сервере,
        находя реальный inbound, где лежит ключ.
        """
        if not self._ensure_session_ok():
            return False

        resource = self._request_json("/panel/inbound/list/", data=self.data)
        if not resource or not resource.get("success"):
            logger.warning("Не получили inbound list при delete_key.")
            return False

        inbound_list = resource.get("obj", [])
        if not inbound_list:
            return False

        for inbound in inbound_list:
            inbound_id = inbound.get("id")
            settings_str = inbound.get("settings", "{}")
            try:
                inbound_settings = json.loads(settings_str)
            except json.JSONDecodeError:
                continue

            for client in inbound_settings.get("clients", []):
                if client.get("id") == key_id:
                    # Удаляем
                    url = f"/panel/inbound/{inbound_id}/delClient/{key_id}"
                    del_resp = self._request_json(url, data=self.data)
                    if not del_resp:
                        logger.warning("Нет ответа при удалении ключа.")
                        return False
                    if del_resp.get("success"):
                        logger.debug(f"Удалили ключ {key_id}.")
                        return True
                    else:
                        msg = del_resp.get("msg", "Неизвестная ошибка delClient")
                        logger.warning(f"Ошибка при удалении ключа {key_id}: {msg}")
                        return False
        return False

    @create_server_session_by_id
    async def get_key_info(self, key_id: str, server_id: int = None) -> VlessKey | None:
        """
        Получает информацию о VPN-ключе VLESS с удаленного сервера.

        :param key_id: Уникальный идентификатор ключа.
        :param server_id: Идентификатор сервера (опционально).
        :return: Объект `VlessKey`, содержащий информацию о ключе, либо None, если ключ не найден.
        """

        if not self._ensure_session_ok():
            return None

        resource = self._request_json("/panel/inbound/list/", data=self.data)
        if not resource or not resource.get("success"):
            logger.warning("Не удалось получить inbound list при get_key_info.")
            return None

        inbound_list = resource.get("obj", [])
        if not inbound_list:
            logger.warning("Список inbound пуст, ключ не найден (get_key_info).")
            return None

        used_bytes = 0
        for inbound in inbound_list:
            for stat in inbound.get("clientStats", []):
                if stat.get("email") == key_id:
                    used_bytes = stat.get("up", 0) + stat.get("down", 0)
                    break

        # clients
        for inbound in inbound_list:
            settings_str = inbound.get("settings", "{}")
            try:
                inbound_settings = json.loads(settings_str)
            except json.JSONDecodeError as ex:
                logger.error(f"JSONDecodeError inbound.settings: {ex}")
                continue

            for client in inbound_settings.get("clients", []):
                if client.get("id") == key_id:
                    name = client.get("comment", "")
                    email = client.get("email", "")
                    access_url = self._get_link(key_id, name)
                    data_limit = client.get("totalGB") or 0
                    return VlessKey(
                        key_id=key_id,
                        name=name,
                        email=email,
                        access_url=access_url,
                        used_bytes=used_bytes,
                        data_limit=data_limit,
                    )
        logger.warning(f"Ключ {key_id} не найден в inbound'ах.")
        return None

    @create_server_session_by_id
    async def update_data_limit(
        self,
        key_id: str,
        new_limit_bytes: int,
        server_id: int = None,
        key_name: str = None,
    ) -> bool:
        """
        Меняет totalGB (и при желании comment) у клиента, где client.id == key_id.
        """
        if not self._ensure_session_ok():
            return False

        resource = self._request_json("/panel/inbound/list/", data=self.data)
        if not resource or not resource.get("success"):
            logger.warning("Не получили inbound list при update_data_limit.")
            return False

        inbound_list = resource.get("obj", [])
        if not inbound_list:
            logger.warning("Пуст inbound_list при update_data_limit.")
            return False

        for inbound in inbound_list:
            inbound_id = inbound.get("id")
            settings_str = inbound.get("settings", "{}")
            try:
                inbound_settings = json.loads(settings_str)
            except json.JSONDecodeError:
                continue

            for client in inbound_settings.get("clients", []):
                if client.get("id") == key_id:
                    old_comment = client.get("comment", "")
                    client["totalGB"] = new_limit_bytes
                    if key_name:
                        client["comment"] = key_name

                    update_payload = {
                        "id": inbound_id,
                        "settings": json.dumps({"clients": [client]}),
                    }
                    resp = self._request_json(
                        f"/panel/inbound/updateClient/{key_id}", data=update_payload
                    )
                    if not resp:
                        logger.warning("Нет ответа updateClient (update_data_limit).")
                        return False
                    if resp.get("success"):
                        logger.debug(
                            f"Обновили лимит ключа {key_id}: old='{old_comment}',"
                            f" new='{client.get('comment')}', limit={new_limit_bytes}"
                        )
                        return True
                    else:
                        msg = resp.get("msg", "Неизвестная ошибка update_data_limit")
                        logger.warning(f"Ошибка update_data_limit {key_id}: {msg}")
                        return False
        return False

    async def setup_server(self, server):
        """
        Автоматическая установка 3X-UI на сервер с предварительной настройкой Docker.

        :param server: Объект сервера с атрибутами `ip` и `password`.

        :return: `True` в случае успешной установки, иначе `False`.

        Алгоритм работы:
        1. Подключается к серверу через SSH.
        2. Останавливает и удаляет старый Docker.
        3. Очищает систему от остаточных файлов Docker.
        4. Устанавливает свежую версию Docker и Docker Compose.
        5. Загружает и выполняет скрипт установки `setup.sh`.
        6. Передает в `setup.sh` необходимые данные для автоматической настройки.
        7. Логирует все этапы выполнения, включая возможные ошибки.
        """

        # Команды для остановки Docker-сервисов
        stop_docker_cmds = [
            "sudo systemctl stop docker",
            "sudo systemctl stop docker.socket",
            "sudo systemctl stop containerd",
            "sudo systemctl stop containerd.socket",
            "sudo killall -9 dockerd containerd",
            "sudo apt remove --purge -y docker docker.io containerd runc",
            "sudo umount /var/run/docker/netns/default || true",
            "sudo rm -rf /var/lib/docker /etc/docker /var/run/docker*",
        ]

        # Команды для удаления старого Docker (включая удаление файла репозитория)
        remove_docker_cmds = [
            "sudo apt update",
            "sudo apt install -y ca-certificates curl gnupg lsb-release",
            "sudo install -m 0755 -d /etc/apt/keyrings",
            "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc > /dev/null",
            "sudo chmod a+r /etc/apt/keyrings/docker.asc",
            # Удаляем старый файл репозитория (если существует)
            "sudo rm -f /etc/apt/sources.list.d/docker.list",
            "apt remove --purge -y docker docker-engine docker.io containerd runc",
            "rm -rf /var/lib/docker /etc/docker /var/run/docker*",
        ]

        # Команды для установки Docker и Docker Compose
        install_docker_cmds = [
            "sudo apt update",
            "apt install -y apt-transport-https ca-certificates curl software-properties-common",
            # Добавляем ключ и репозиторий Docker для Ubuntu 22.04 (jammy)
            "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc > /dev/null",
            "sudo chmod a+r /etc/apt/keyrings/docker.asc",
            # Удаляем старый репозиторий, если он есть, и создаём новый
            "sudo rm -f /etc/apt/sources.list.d/docker.list",
            "echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu jammy stable' | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null",
            "sudo apt update",
            "apt install -y docker-ce docker-ce-cli containerd.io",
            'curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose',
            "sudo chmod +x /usr/local/bin/docker-compose",
        ]
        vless_email = os.getenv("VLESS_EMAIL")
        vless_bot_token = os.getenv("VLESS_BOT_TOKEN")
        # Команда для скачивания setup.sh
        setup_script = "curl -sSL https://raw.githubusercontent.com/torikki-tou/team418/main/setup.sh -o setup.sh && chmod +x setup.sh"
        # Данные для автоматического ввода в setup.sh (каждая строка — ответ на соответствующий вопрос)
        setup_answers = (
            "\n".join(
                [
                    "lisa_admin",  # Логин
                    server.password,  # Пароль
                    "2053",  # Порт 3X-UI
                    server.ip,  # IP/домен
                    vless_email,  # Email
                    vless_bot_token,  # Telegram Bot Token
                    "lisa_helper",  # Telegram admin profile
                    "y",  # Автоматическое подтверждение перезаписи конфига
                ]
            )
            + "\n"
        )
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                async with asyncssh.connect(
                    host=server.ip,
                    username="root",
                    password=server.password,
                    known_hosts=None,
                ) as conn:
                    logger.info(f"Попытка {attempt + 1}/{max_attempts}...")
                    logger.info(f"🔗 Подключение к серверу {server.ip} установлено!")

                    # Остановка и удаление старого Docker
                    logger.info("🛑 Останавливаем старый Docker...")
                    for cmd in stop_docker_cmds:
                        logger.info(f"➡ Выполняем: {cmd}")
                        result = await conn.run(cmd, check=False)
                        if result.exit_status != 0:
                            logger.warning(
                                f"⚠ Ошибка при выполнении {cmd}: {result.stderr.strip()}"
                            )

                    logger.info("🗑️ Удаляем старый Docker (очистка)...")
                    for cmd in remove_docker_cmds:
                        logger.info(f"➡ Выполняем: {cmd}")
                        result = await conn.run(cmd, check=False)
                        if result.exit_status != 0:
                            logger.warning(
                                f"⚠ Ошибка при выполнении {cmd}: {result.stderr.strip()}"
                            )
                        else:
                            logger.info(result.stdout)

                    # Установка нового Docker
                    logger.info("⬇ Устанавливаем Docker и Docker Compose...")
                    for cmd in install_docker_cmds:
                        logger.info(f"➡ Выполняем: {cmd}")
                        result = await conn.run(cmd, check=False)
                        if result.exit_status != 0:
                            raise Exception(
                                f"Ошибка при установке Docker: {cmd}\n{result.stderr.strip()}"
                            )
                        logger.info(result.stdout)

                    # Скачивание setup.sh
                    logger.info("📥 Загружаем setup.sh...")
                    result = await conn.run(setup_script)
                    if result.exit_status != 0:
                        raise Exception(
                            f"Ошибка при загрузке setup.sh: {result.stderr.strip()}"
                        )
                    logger.info(result.stdout)

                    # Запуск setup.sh с автоматическим вводом ответов
                    logger.info(
                        "⚙️ Запускаем setup.sh с автоматическим вводом данных..."
                    )
                    result = await conn.run('bash -c "./setup.sh"', input=setup_answers)
                    if result.exit_status != 0:
                        raise Exception(
                            f"Ошибка при установке 3X-UI: {result.stderr.strip()}"
                        )
                    logger.info(result.stdout)
                    await send_new_server_report(
                        server_id=server.id,
                        ip=server.ip,
                        protocol="vless",
                        management_panel_url=f"https://{server.ip}:2053",
                    )
                    logger.info(
                        f"🎉 3X-UI успешно установлена! Теперь панель доступна на {server.ip}:2053"
                    )
                    await asyncio.sleep(30)
                    return True

            except Exception as e:
                if attempt != 0:
                    await send_error_report(e)
                logger.info(
                    f"❌ Ошибка при установке 3X-UI: {e}, попытка {attempt + 1}/{max_attempts}"
                )
                if attempt < max_attempts - 1:
                    logger.info("Повторная попытка через 10 секунд...")
                    await asyncio.sleep(10)

        return False

    async def get_server_info(self, server) -> dict:
        """
        Получение информации о сервере
        Возвращает данные в виде:
        {
            "name": "My Server",
            "serverId": "7fda0079-5317-4e5a-bb41-5a431dddae21",
            "metricsEnabled": true,
            "createdTimestampMs": 1536613192052,
            "version": "1.0.0",
            "accessKeyDataLimit": {"bytes": 8589934592},
            "portForNewAccessKeys": 1234,
            "hostnameForAccessKeys": "example.com"
        }
        """
        # Инициализация соединения с сервером панели
        self.ip = server.ip
        self.port_panel = 2053
        self.host = f"https://{self.ip}:{self.port_panel}"
        self.data = {"username": "lisa_admin", "password": server.password}
        self.ses = requests.Session()
        self.ses.verify = False

        if not self._connect():
            raise Exception("Не удалось подключиться к панели сервера")

        resp = self._request_json("/server/info", data=self.data)
        if not resp:
            raise Exception("Сервер не вернул JSON при get_server_info")
        if resp.get("success"):
            return resp.get("obj", {})
        else:
            raise Exception(resp.get("msg", "Ошибка получения информации о сервере"))

    @create_server_session_by_id
    async def extend_data_limit_plus_200gb(self, key_id: str, server_id=None) -> bool:
        """
        Увеличивает лимит для ключа VLESS: "текущий used_bytes + 200 ГБ".
        Возвращает True в случае успеха.

        :param key_id: ID клиента (UUID), который хранится в поле client.id
        :param server_id: ID сервера VLESS (обязательно передавать как именованный аргумент)
        """
        try:
            # 1) Получаем информацию по ключу (сколько уже использовано)
            usage_info = await self.get_key_info(key_id=key_id, server_id=server_id)
            if usage_info is None:
                logger.error(f"[VLESS] Ключ {key_id} не найден на сервере {server_id}")
                return False

            used_bytes = usage_info.used_bytes

            # 2) Складываем used_bytes + 200 ГБ
            addition_limit = 200 * 1024**3  # 200 GB в байтах
            new_limit_bytes = used_bytes + addition_limit

            # 3) Обновляем лимит
            updated = await self.update_data_limit(
                key_id=key_id,
                new_limit_bytes=new_limit_bytes,
                server_id=server_id,
                key_name=usage_info.name,  # необязательно, если хотите оставить имя
            )
            if updated:
                logger.info(
                    f"[VLESS] Лимит ключа {key_id} обновлён: {new_limit_bytes} байт "
                    f"(израсходовано={used_bytes})."
                )
            else:
                logger.warning(
                    f"[VLESS] Не удалось обновить лимит ключа {key_id} на сервере {server_id}."
                )
            return updated

        except Exception as e:
            logger.error(f"[VLESS] Ошибка при увеличении лимита: {e}")
            return False
