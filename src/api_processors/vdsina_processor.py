import aiohttp
import certifi
import ssl
import os
import logging

from bot.routers.admin_router_sending_message import send_error_report
from dotenv import load_dotenv


logger = logging.getLogger(__name__)

load_dotenv()

token = os.getenv("VDSINA_TOKEN")


class VDSinaAPI:
    def __init__(self):
        self.token = token  # Можно сразу брать из .env, если есть
        self.email = None
        self.password = None
        self.base_url = "https://userapi.vdsina.com/v1"

    async def authenticate(
        self, email: str | None = None, password: str | None = None
    ) -> None:
        """
        Получение токена для авторизации в системе.

        :param email: Адрес электронной почты для аутентификации. Если не указан, используется текущий.
        :param password: Пароль для аутентификации. Если не указан, используется текущий.

        :raises Exception: Если не указаны `email` и `password` для аутентификации.
        :raises Exception: Если произошла ошибка при получении токена.

        :return: None

        Алгоритм работы:
        1. Проверяет наличие значений для email и password.
        2. Отправляет POST-запрос на сервер с данными для авторизации.
        3. Если запрос успешен, сохраняет полученный токен.
        4. В случае неуспешной авторизации выбрасывает исключение с ошибкой.
        """
        if email:
            self.email = email
        if password:
            self.password = password

        if not self.email or not self.password:
            raise Exception("Необходимо указать email и password для аутентификации.")

        url = f"{self.base_url}/auth"
        payload = {"email": self.email, "password": self.password}
        headers = {"Content-Type": "application/json"}
        ssl_context = ssl.create_default_context(cafile=certifi.where())

        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl_context)
        ) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                response_data = await response.json()
                if response_data.get("status") == "ok":
                    self.token = response_data["data"]["token"]
                    logger.info(
                        f"Авторизация успешна. Получен токен: {self.token[:10]}..."
                    )
                else:
                    raise Exception(
                        "Ошибка авторизации: "
                        + response_data.get("status_msg", "Неизвестная ошибка")
                    )

    async def request(self, method: str, endpoint: str, data: dict | None = None):
        """
        Универсальный метод для отправки запросов к API VDSina.

        :param method: HTTP-метод для запроса (GET, POST, PUT, DELETE).
        :param endpoint: Эндпоинт API, к которому будет сделан запрос.
        :param data: Данные, которые отправляются в запросе (для POST, PUT).

        :raises Exception: Если не установлен авторизационный токен.
        :raises ValueError: Если метод запроса не поддерживается.

        :return: Ответ от сервера в виде JSON.

        Алгоритм работы:
        1. Проверяет наличие авторизационного токена.
        2. Формирует полный URL для запроса.
        3. Отправляет запрос соответствующего метода (GET, POST, PUT, DELETE).
        4. Возвращает результат в виде JSON.
        5. Если метод не поддерживается, выбрасывает исключение.
        """
        if not self.token:
            # Можно либо вызвать authenticate, либо выдать ошибку
            raise Exception(
                "Нет авторизационного токена. Сначала вызовите authenticate()."
            )

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": self.token, "Content-Type": "application/json"}

        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl_context)
        ) as session:
            if method.upper() == "GET":
                async with session.get(url, headers=headers) as response:
                    return await response.json()
            elif method.upper() == "POST":
                async with session.post(url, json=data, headers=headers) as response:
                    return await response.json()
            elif method.upper() == "PUT":
                async with session.put(url, json=data, headers=headers) as response:
                    return await response.json()
            elif method.upper() == "DELETE":
                async with session.delete(url, json=data, headers=headers) as response:
                    return await response.json()
            else:
                await send_error_report(f"Неподдерживаемый метод запроса: {method}")
                raise ValueError(f"Неподдерживаемый метод запроса: {method}")

    async def get_datacenters(self) -> dict:
        """Получение списка дата-центров"""
        return await self.request("GET", "/datacenter")

    async def get_server_plans(self, group_id=1) -> dict:
        """Получение списка тарифов"""
        return await self.request("GET", f"/server-plan/{group_id}")

    async def get_templates(self) -> dict:
        """Получение списка доступных ОС"""
        return await self.request("GET", "/template")

    async def deploy_server(
        self,
        name: str,
        datacenter_id: int,
        server_plan_id: int,
        template_id: int,
        ip4=1,
    ):
        """
        Разворачивание нового сервера на платформе VDSina.
        :param name: Имя сервера
        :param datacenter_id: Идентификатор дата-центра, в котором будет размещен сервер.
        :param server_plan_id: Идентификатор плана сервера, который будет использоваться.
        :param template_id: Идентификатор шаблона для нового сервера.
        :param name: Имя сервера (по умолчанию "MyServer").

        :return: Ответ от сервера в виде JSON, содержащий информацию о развернутом сервере.

        Алгоритм работы:
        1. Формирует данные для запроса, включая параметры дата-центра, плана, шаблона и имени.
        2. Отправляет POST-запрос на создание нового сервера.
        3. Возвращает ответ сервера.
        """
        payload = {
            "name": name,
            "datacenter": datacenter_id,
            "server-plan": server_plan_id,
            "template": template_id,
            "backup": 0,
            "name": name,
            "ip4": ip4,
        }
        return await self.request("POST", "/server", payload)

    async def get_server_status(self, server_id):
        """
        Получение информации о статусе сервера на платформе VDSina.

        :param server_id: Идентификатор сервера, статус которого необходимо получить.

        :return: Ответ от сервера в виде JSON, содержащий информацию о статусе сервера.

        Алгоритм работы:
        1. Отправляет GET-запрос на получение статуса сервера по его идентификатору.
        2. Возвращает ответ сервера с информацией о текущем состоянии сервера.
        """
        return await self.request("GET", f"/server/{server_id}")

    async def create_new_server(
        self,
        name,
        datacenter_id,
        server_plan_id,
        template_id,
        ip4=1,
        email=None,
        password=None,
    ):
        """
        Создание нового сервера на платформе VDSina с предварительной авторизацией.

        :param datacenter_id: Идентификатор дата-центра для размещения сервера.
        :param server_plan_id: Идентификатор плана сервера (характеристики).
        :param template_id: Идентификатор шаблона ОС для сервера.
        :param ip4: Флаг, указывающий на необходимость использования IPv4 адреса (по умолчанию 1).
        :param email: Email для аутентификации, если токен отсутствует.
        :param password: Пароль для аутентификации, если токен отсутствует.

        :return: Ответ от API о создании сервера в виде JSON.

        Алгоритм работы:
        1. Проверяет наличие авторизационного токена. Если токен отсутствует, вызывает метод для авторизации.
        2. После успешной авторизации вызывает метод для развертывания нового сервера с переданными параметрами.
        3. Возвращает результат запроса, который содержит информацию о созданном сервере.
        """
        # Если токена нет, пробуем авторизоваться
        if not self.token:
            await self.authenticate(email, password)
        # После успешной авторизации пробуем создать сервер
        return await self.deploy_server(
            name, datacenter_id, server_plan_id, template_id, ip4
        )

    async def get_servers(self):
        return await self.request("GET", "/server")

    async def get_server_statistics(self, server_id, from_date=None, to_date=None):
        if not from_date and to_date:
            endpoint = f"/server.stat/{server_id}?to={to_date}"
        elif from_date and not to_date:
            endpoint = f"/server.stat/{server_id}?from={from_date}"
        elif from_date and to_date:
            endpoint = f"/server.stat/{server_id}?from={from_date}&to={to_date}"
        else:
            endpoint = f"/server.stat/{server_id}"

        return await self.request("GET", endpoint)
