from datetime import datetime, timedelta
import os
import logging
import requests
import asyncio
from contextlib import contextmanager
from git import Repo
from typing import Optional

from sqlalchemy.orm import sessionmaker
from sqlalchemy import (
    func,
    create_engine,
)

from bot.routers.admin_router_sending_message import send_error_report
from initialization.vdsina_processor_init import vdsina_processor
from bot.utils.send_message import send_message_subscription_expired
from database.models import Base, VpnKey, Server, User
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

github_token = os.getenv("GITHUB_TOKEN")
github_username = os.getenv("GITHUB_USERNAME")
repo_owner = os.getenv("REPO_OWNER")
repo_name = os.getenv("REPO_NAME")
github_remote_url = (
    f"https://{github_username}:{github_token}@github.com/{repo_owner}/{repo_name}.git"
)
git_repo_dir = os.path.abspath("DB_LISA")


class DbProcessor:
    def __init__(self):
        # Создаем движок для подключения к базе данных
        base_dir = os.path.dirname(
            os.path.abspath(__file__)
        )  # Получаем путь к текущему файлу (db_processor_init.py)
        db_path = os.path.join(
            base_dir, "..", "database", "vpn_users.db"
        )  # Поднимаемся на уровень выше
        db_uri = "sqlite:////app/database/vpn_users.db"  # Создаем абсолютный путь

        self.engine = create_engine(db_uri, echo=True)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._server_creation_lock = asyncio.Lock()

    def init_db(self):
        """Синхронная инициализация базы данных."""
        Base.metadata.create_all(self.engine)

    def get_session(self):
        """Создает и возвращает новую сессию."""
        return self.Session()

    @contextmanager
    def session_scope(self):
        """
        Контекстный менеджер для работы с сессией.
        Обеспечивает автоматический коммит или откат транзакции.
        :return: Сессия
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def get_key_by_id(self, key_id: str) -> VpnKey | None:
        """Возвращает объект ключа (VpnKey) по его ID или None, если ключ не найден."""
        with self.session_scope() as session:
            return session.query(VpnKey).filter_by(key_id=key_id).first()

    def get_vpn_type_by_key_id(self, key_id: str) -> str:
        """
        Возвращает тип протокола VPN по ID ключа.
        :param key_id:
        :return:
        """
        with self.session_scope() as session:
            key = session.query(VpnKey).filter_by(key_id=key_id).first()
            if key:
                return key.protocol_type
            else:
                logger.error(f"Ошибка при получении информации о ключе {key_id}")
                return None

    def check_trial_period_usage(self, user_id: int):
        """
        Проверяет, использовал ли пользователь пробный период.
        :param user_id:
        :return:
        """
        with self.session_scope() as session:
            user = session.query(User).filter_by(user_telegram_id=str(user_id)).first()
            if user:
                return user.use_trial_period
            else:
                return False

    def update_database_with_key(
            self,
            user_id,
            key,
            period,
            server_id,
            protocol_type="outline",
            is_trial_key=False,
    ) -> bool:
        """
        Обновляет базу данных новым ключом.
        :param user_id:
        :param key:
        :param period:
        :param server_id:
        :param protocol_type:
        :return:
        """
        user_id_str = str(user_id)
        start_date = datetime.now().replace(minute=0, second=0, microsecond=0)

        if is_trial_key:
            expiration_date = (start_date + timedelta(days=2)).replace(
                minute=0, second=0, microsecond=0
            )
        else:
            period_months = int(period.split()[0])
            expiration_date = (start_date + timedelta(days=30 * period_months)).replace(
                minute=0, second=0, microsecond=0
            )

        with self.session_scope() as session:
            user = session.query(User).filter_by(user_telegram_id=user_id_str).first()

            if not user:
                user = User(
                    user_telegram_id=user_id_str,
                    subscription_status="active",
                    use_trial_period=False,
                )
                session.add(user)

            if is_trial_key is True:
                user.use_trial_period = True

            new_key = VpnKey(
                key_id=key.key_id,
                user_telegram_id=user_id_str,
                expiration_date=expiration_date,
                start_date=start_date,
                protocol_type=protocol_type,
                name=key.name,
                server_id=server_id,
            )
            session.add(new_key)
        return True

    async def get_expiring_keys_by_user_id(self, user_id) -> dict[str, tuple[str, int]]:
        """
        Возвращает словарь с истекшими ключами пользователя.
        :param user_id:
        :return:
        """
        with self.session_scope() as session:
            user = session.query(User).filter_by(user_telegram_id=str(user_id)).first()
            keys = await self._check_user_keys(user)
            return keys

    async def check_and_notification_by_expiring_keys(self):
        """
        Асинхронная проверка базы данных на истекшие ключи.
        - Если ключ истекает через 3 дня, отправляется уведомление.
        - Если ключ истекает сегодня, он удаляется из базы данных.
        :return:
        """
        with self.session_scope() as session:
            users = session.query(User).all()
            # Обрабатываем каждого пользователя
            for user in users:
                user_expiring_keys = await self._check_user_keys(user)
                if user_expiring_keys:
                    # Отправляем уведомление пользователю об истекающих ключах
                    await send_message_subscription_expired(
                        user.user_telegram_id, user_expiring_keys
                    )

    @staticmethod
    async def _check_user_keys(user):
        """
        Проверяет ключи пользователя на истечение и выполняет соответствующие действия.
        :param user: Объект пользователя
        :return: Словарь с истекающими ключами пользователя для уведомления
        """
        expiring_keys = {}
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for key in user.keys:
            time_diff = (
                    key.expiration_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    - now
            )
            if timedelta(days=0) < time_diff <= timedelta(days=2):
                # Ключ будет действителен не более 2х дней
                expiring_keys[key.key_id] = (
                    key.name,
                    max(time_diff, timedelta(days=0)).days,
                )
        return expiring_keys

    @staticmethod
    async def _delete_expired_key(key, session):
        """
        Удаляет истекший ключ из базы данных.
        :param key: Ключ для удаления
        :param session: Сессия базы данных
        """
        from utils.get_processor import get_processor

        processor = await get_processor(key.protocol_type.lower())
        await processor.delete_key(key.key_id, server_id=key.server_id)
        session.delete(key)

        # Обновляем количество пользователей на сервере
        key.server.cnt_users = max(0, key.server.cnt_users - 1)

    async def check_and_delete_expired_keys(self):
        """
        Удаляет истекшие ключи из базы данных.
        """
        with self.session_scope() as session:
            keys = session.query(VpnKey).all()
            for key in keys:
                now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                if (
                        key.expiration_date.replace(
                            hour=0, minute=0, second=0, microsecond=0
                        )
                        <= now
                ):
                    await self._delete_expired_key(key, session)

    async def get_server_with_min_users(self, protocol_type: str, user_id: int | None = None) -> Server | None:
        """
        Возвращает сервер с минимальным количеством пользователей
        (для id<=2 лимит 100, для id>2 лимит 200). Если подходящего нет – создаёт новый.
        """
        from utils.get_processor import get_processor
        from initialization.bot_init import bot
        if self._server_creation_lock.locked():
            await asyncio.sleep(1)
            if self._server_creation_lock.locked():
                await bot.send_message(
                    user_id,
                    "Сейчас система обрабатывает запросы и сервер находится под высокой нагрузкой. "
                    "Пожалуйста, ожидайте! Ключ автоматически добавится в менеджер ключей в течение 7 минут."
                )
        async with self._server_creation_lock:
            with self.session_scope() as session:
                count_servers = session.query(Server).count()
                servers = (
                    session.query(Server)
                    .filter(func.lower(Server.protocol_type) == protocol_type.lower())
                    .order_by(Server.cnt_users.asc())
                    .with_for_update()  # Блокируем строку для изменения
                    .all()
                )

                selected_server = None
                for server in servers:
                    max_users = 200 if server.id > 2 else 100
                    if server.cnt_users < max_users:
                        selected_server = server
                        break
                    # Если есть хотя бы один сервер с местом, берем его
                    # считаем их количество по-разному
                if not selected_server:
                    print("Сервера с местом не найдено", user_id)
                    if user_id:
                        await bot.send_message(
                            user_id,
                            (
                                "Пожалуйста, ожидайте!\n\n"
                                "В связи с большой загруженностью сервиса в данный момент, "
                                "добавление нового ключа единоразово может занять до 7 минут. \n\n"
                                "Ваш ключ автоматически добавится в менеджер ключей."
                            )
                        )

                    logger.info(f"Сервера с протоколом {protocol_type} не найдено.")
                    new_server, server_ip, server_password = (
                        await self.create_new_server(count_servers)
                    )

                    if not new_server:
                        await send_error_report("Ошибка при создании нового сервера")
                        logger.error("Ошибка при создании нового сервера")
                        return None

                    new_server_db = self.add_server(
                        new_server, protocol_type, server_ip, server_password
                    )
                    processor = await get_processor(protocol_type.lower())
                    result = await processor.setup_server(new_server_db)
                    if not result:
                        await send_error_report(
                            "Ошибка при настройке сервера {protocol_type}"
                        )
                        logger.error(
                            f"Ошибка при настройке сервера типа {protocol_type}"
                        )
                        return None
                    selected_server = new_server_db
                selected_server.cnt_users += 1
                # self.increment_server_user_count(selected_server.id)
                # selected_server = self.get_server_by_id(selected_server.id)
                return selected_server

    @staticmethod
    def get_server_info(server_id):
        """
        Запрашивает информацию о сервере по его ID.
        :param server_id:
        :return:
        """
        url = f"https://userapi.vdsina.com/v1/server/{server_id}"
        headers = {"Authorization": f"Bearer {os.getenv('VDSINA_TOKEN')}"}

        response = requests.get(url, headers=headers)
        data = response.json()

        if data.get("status") == "ok":
            return data.get("data", {})
        return None

    async def wait_for_server_ready(self, server_id, timeout=300):
        """
        Ожидает, пока сервер станет активным.
        :param server_id: ID сервера
        :param timeout: Максимальное время ожидания в секундах
        :return: True, если сервер активен, иначе False
        """
        for _ in range(timeout // 5):  # Проверяем каждые 5 секунд
            server_data = self.get_server_info(server_id)
            if server_data and server_data.get("status") == "active":
                return True
            logger.info("Сервер еще не активен, ждем...")
            await asyncio.sleep(5)  # Ждем 5 секунд перед следующей проверкой
        logger.error("Таймаут ожидания сервера!")
        await send_error_report("Таймаут ожидания сервера!")
        return False

    @staticmethod
    def get_server_ip(server_id):
        """
        Запрашивает информацию о сервере по его ID.
        :param server_id:
        :return: IP-адрес сервера
        """
        url = f"https://userapi.vdsina.com/v1/server/{server_id}"
        headers = {"Authorization": f"Bearer {os.getenv('VDSINA_TOKEN')}"}
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            if data.get("status") == "ok":
                server_data = data.get("data", {})
                ip_list = server_data.get("ip", [])
                if ip_list:
                    return ip_list[0].get("ip")
        except Exception as e:
            logger.error(f"Ошибка при получении IP сервера {server_id} {e}")
            asyncio.create_task(
                send_error_report(f"Ошибка при получении IP сервера {server_id} {e}")
            )
        return None

    @staticmethod
    def get_server_password(server_id):
        """
        Получает пароль сервера по его ID.
        :param server_id:
        :return: Пароль сервера
        """
        url = f"https://userapi.vdsina.com/v1/server.password/{server_id}"
        headers = {"Authorization": f"Bearer {os.getenv('VDSINA_TOKEN')}"}
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            if data.get("status") == "ok":
                server_data = data.get("data", {})
                password = server_data.get("password", [])
                if password:
                    return password
        except Exception as e:
            logger.error(f"Ошибка при получении пароля сервера {server_id} {e}")
            asyncio.create_task(
                send_error_report(
                    f"Ошибка при получении пароля сервера {server_id} {e}"
                )
            )
        return None

    async def get_notification(self, user_id: int) -> Server:
        # Попытка захватить блокировку с таймаутом
        try:
            print("bwvhbeirvbi3erwbfybvewrybvyerbuycerb")
            await asyncio.wait_for(self._server_creation_lock.acquire(), timeout=1.0)
        except Exception as e:
            pass
        finally:
            print("Люблю даню костина")
            # Если не удалось захватить блокировку, уведомляем пользователя о высокой нагрузке
            from initialization.bot_init import bot
            await bot.send_message(
                user_id,
                "Сейчас система обрабатывает запросы и сервер находится под высокой нагрузкой. "
                "Пожалуйста, попробуйте снова через некоторое время."
            )

    async def create_new_server(self, count_servers):
        """
        Создает новый сервер с выбранным тарифным планом.
        Если server_plan_id == 22, имя будет начинаться с "Server-64tb", иначе – с "Server-".
        """
        template_id = 31  # Шаблон Outline VPN (Ubuntu 22)
        server_name = "Server-64tb" + str(count_servers + 1)
        server_plan_id = 17 #1

        logger.info(
            f"Отправляем запрос на создание нового сервера с именем {server_name} и тарифом {server_plan_id}"
        )
        new_server = await vdsina_processor.create_new_server(
            name=server_name,
            datacenter_id=1,
            server_plan_id=server_plan_id,
            template_id=template_id,
            ip4=1,
            email=os.getenv("VDSINA_EMAIL"),
            password=os.getenv("VDSINA_PASSWORD"),
        )
        if not new_server or new_server.get("status") != "ok":
            await send_error_report("Ошибка при создании нового сервера")
            logger.error("Ошибка при создании нового сервера")
            return None
        server_id = new_server["data"]["id"]
        logger.info(f"Создан новый сервер с ID: {server_id}")
        is_ready = await self.wait_for_server_ready(server_id)
        if not is_ready:
            await send_error_report(
                "Сервер не стал активным, невозможно получить IP и пароль"
            )
            logger.error("Сервер не стал активным, невозможно получить IP и пароль")
            return None
        server_ip = self.get_server_ip(server_id)
        server_password = self.get_server_password(server_id)
        logger.info(f"Сервер готов: IP={server_ip}, Пароль={server_password}")
        return new_server, server_ip, server_password

    def add_server(
            self,
            server_data: dict,
            protocol_type: str,
            server_ip: str,
            server_password: str,
    ) -> Server:
        """
         Добавляет информацию о сервере в базу данных.
        :param server_data: Словарь с данными сервера.
        :param protocol_type: Тип протокола (например, "Outline").
        :return: Объект нового сервера.
        """
        with self.session_scope() as session:
            new_server = Server(
                ip=server_ip,
                password=server_password,
                api_url="https://userapi.vdsina.ru",
                cert_sha256=server_data.get("cert_sha256", ""),
                cnt_users=0,
                protocol_type=protocol_type,
            )
            session.add(new_server)
            session.commit()
            session.refresh(new_server)
            logger.info(f"Сервер {new_server.id} успешно добавлен в БД.")
            return new_server

    def get_server_id_by_key_id(self, key_id) -> int:
        """
        Возвращает ID сервера по ID ключа.
        :param key_id:
        :return: ID сервера
        """
        with self.session_scope() as session:
            key = session.query(VpnKey).filter_by(key_id=key_id).first()
            if key:
                return key.server_id
            else:
                asyncio.create_task(
                    send_error_report(
                        f"Ошибка при получении ID сервера по ключу {key_id}"
                    )
                )
                logger.error(f"Ошибка при получении информации о ключе {key_id}")
                return None

    def get_server_by_id(self, server_id: str) -> Server:
        """
        Возвращает сервер по ID.
        :param server_id:
        :return:
        """
        with self.session_scope() as session:
            server = session.query(Server).filter_by(id=server_id).first()
            if server:
                logger.info(f"Найден сервер с id: {server_id}")
            else:
                asyncio.create_task(
                    send_error_report(f"Сервер с id {server_id} не найден.")
                )
                logger.error(f"Сервер с id {server_id} не найден.")
                raise ValueError("Нет сервера с переданным id")
            return server

    # def increment_server_user_count(self, server_id: int) -> Server:
    #     with self.session_scope() as session:
    #         server = session.query(Server).filter_by(id=server_id).one()
    #         server.cnt_users += 1
    #         session.commit()
    #         session.refresh(server)
    #         return server

    def rename_key(self, key_id: str, new_name: str) -> bool:
        """
        Изменяет имя ключа.
        :param key_id:
        :param new_name:
        :return:
        """
        with self.session_scope() as session:
            key = session.query(VpnKey).filter_by(key_id=key_id).first()
            if not key:
                logger.warning(f"Ключ с ID {key_id} не найден.")
                return False
            key.name = new_name
            logger.info(f"Имя ключа с ID {key_id} изменено на {new_name}")
            return True

    async def check_count_keys_on_servers(self):
        """
        Проверяет число пользователей на серверах с тарифом 17.
        Если все серверы с тарифом 17 заполнены (>= 100 для старых, >= 200 для серверов с именем Server64tb-),
        создается новый сервер с тарифом 17.
        """
        from utils.get_processor import get_processor
        async with self._server_creation_lock:
            with self.session_scope() as session:
                count_servers = session.query(Server).count()
                protocol_types = ("outline", "vless")
                for protocol_type in protocol_types:
                    servers = (
                        session.query(Server)
                        .filter_by(protocol_type=protocol_type)
                        .all()
                    )
                    all_full = True
                    for server in servers:
                        max_users = 200 if server.id > 2 else 100
                        if server.cnt_users < max_users:
                            all_full = False
                            break

                    if all_full:
                        logger.info(
                            f"Все сервера с тарифом 17 для типа {protocol_type} заполнены, создаем новый сервер с тарифом 17."
                        )
                        # При создании нового сервера используем новый префикс
                        new_server, server_ip, server_password = (
                            await self.create_new_server(count_servers)
                        )
                        count_servers += 1
                        if new_server:
                            logger.info(
                                f"Создан новый сервер типа {protocol_type}, записываем в БД."
                            )
                            new_server_db = self.add_server(
                                new_server, protocol_type, server_ip, server_password
                            )
                            processor = await get_processor(protocol_type)
                            logger.info(f"Передаем сервер в setup_server: {new_server}")
                            result = await processor.setup_server(new_server_db)
                            if not result:
                                logger.error(
                                    f"Ошибка при настройке нового сервера {protocol_type}"
                                )
                                await send_error_report(
                                    f"Ошибка при настройке нового сервера {protocol_type}"
                                )
                                return
                            logger.info(f"Настроен сервер {protocol_type}")

    async def check_and_update_key_data_limit(self):
        from utils.get_processor import get_processor

        with self.session_scope() as session:
            keys = session.query(VpnKey).all()
            for key in keys:
                now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                key_start_date = key.start_date.replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                if key.expiration_date > now and (now - key_start_date).days > 0 and (
                        now - key_start_date).days % 30 == 0:
                    processor = await get_processor(key.protocol_type)
                    key_info = await processor.get_key_info(
                        key.key_id, server_id=key.server_id
                    )
                    logger.info(
                        f"Обновляем лимит для ключа {key.key_id} на сервере {key.server_id}"
                    )
                    await processor.update_data_limit(
                        key.key_id,
                        key_info.data_limit
                        + (key_info.used_bytes - key.used_bytes_last_month),
                        server_id=key.server_id,
                        key_name=key.name,
                    )
                    key.used_bytes_last_month = key_info.used_bytes

    def update_server_by_id(self, server_id, api_url, cert_sha256):
        with self.session_scope() as session:
            # Берём сервер непосредственно в этой же сессии
            server = session.query(Server).filter_by(id=server_id).one()
            server.api_url = api_url
            server.cert_sha256 = cert_sha256
            session.commit()
            # При необходимости можно сделать session.refresh(server)
            session.refresh(server)
            logger.info(
                f"Сервер {server_id} успешно обновлен, server.api_url={api_url}, server.cert_sha256={cert_sha256}"
            )

    async def get_all_user_ids(self):
        with self.session_scope() as session:
            users = session.query(User).all()
            return [user.user_telegram_id for user in users]

    @staticmethod
    async def backup_bd():
        db_path = os.path.abspath("database/vpn_users.db")
        if not os.path.exists(db_path):
            logger.error(f"Файл базы данных {db_path} не найден.")
            await send_error_report(f"Файл базы данных {db_path} не найден.")
            return None

        # Абсолютный путь к каталогу репозитория
        repo_dir = "/app/DB_LISA"
        os.makedirs(repo_dir, exist_ok=True)

        # Если .git нет, инициализируем
        if not os.path.exists(os.path.join(repo_dir, ".git")):
            repo = Repo.init(repo_dir)
        else:
            repo = Repo(repo_dir)

        # Подключаемся к удалённому репозиторию, если он не задан
        if "origin" not in [remote.name for remote in repo.remotes]:
            repo.create_remote("origin", github_remote_url)
        origin = repo.remote(name="origin")

        # 1) Сначала пытаемся получить последние изменения c remote
        try:
            origin.pull("master")  # Можно "--rebase=True", если вам нужен rebase
            logger.info("pull завершён без ошибок.")
        except Exception as pull_err:
            logger.error(f"Ошибка при выполнении git pull: {pull_err}")

        # 2) Теперь копируем локальный файл базы данных в репозиторий
        repo_db_path = os.path.join(repo_dir, os.path.basename(db_path))
        with open(db_path, "rb") as f:
            new_content = f.read()

        if os.path.exists(repo_db_path):
            with open(repo_db_path, "rb") as f:
                current_content = f.read()
        else:
            current_content = None

        # Проверяем, изменилась ли БД
        if new_content != current_content:
            with open(repo_db_path, "wb") as f:
                f.write(new_content)
            logger.info(
                f"Файл базы данных '{db_path}' перезаписан в репозитории: {repo_db_path}"
            )

            try:
                # Индексируем и коммитим
                repo.git.add(os.path.basename(db_path))
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                commit_message = f"Backup at {timestamp}"
                repo.index.commit(commit_message)
                logger.info(f"Коммит сделан: {commit_message}")

                # Пробуем обычный push
                try:
                    repo.git.push("--set-upstream", "origin", "master")
                    logger.info(
                        "Изменения отправлены в удалённый репозиторий (обычный push)."
                    )
                except Exception as push_err:
                    logger.warning(f"Обычный push не удался: {push_err}")
                    # Если хотим перезаписать ветку, пробуем force push (опционально):
                    # repo.git.push("--force-with-lease", "origin", "master")
                    # logger.info("Принудительный push выполнен.")

            except Exception as e:
                logger.error(f"Ошибка при резервном копировании: {e}")
                await send_error_report(f"Ошибка при резервном копировании: {e}")
        else:
            logger.info(
                "База данных не изменилась, резервное копирование не требуется."
            )

    async def mark_used_trial_period(self, user_id: int) -> None:
        """
        Помечает, что пользователь использовал пробный период.
        :param user_id: идентификатор пользователя
        :return: True при успешном выполнении
        """
        with self.session_scope() as session:
            user = session.query(User).filter_by(user_telegram_id=str(user_id)).first()

            if not user:
                user = User(user_telegram_id=str(user_id), subscription_status='active', use_trial_period=True)
                session.add(user)
                logger.info(f"Пользователь {user_id} добавлен.")

            user.use_trial_period = True
            logger.info(f"Пользователь {user_id} пробный период отмечен.")
            session.commit()
