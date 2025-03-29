import logging
import os
import sys
from logging.handlers import RotatingFileHandler

LOG_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "bot.log"))


def configure_logging():
    # Устанавливаем общий уровень логирования
    logging.basicConfig(level=logging.INFO)

    # Формат
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )

    # Обработчик ротации (max 5 МБ, храним 3 файла)
    file_handler = RotatingFileHandler(
        LOG_FILE_PATH, maxBytes=10 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(formatter)

    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Очищаем обработчики у root-логгера и добавляем наши
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Если нужен уровень именно на root
    root_logger.setLevel(logging.INFO)
