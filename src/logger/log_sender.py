import json
import logging
from aiogram.types import Message


logger = logging.getLogger(__name__)


class LogSender:
    @staticmethod
    def log_payment_details(message: Message):
        """Логирует детали успешного платежа."""
        logger.info(json.dumps(message.dict(), indent=4, default=str))
