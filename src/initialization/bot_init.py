import os
import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv


load_dotenv()
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TOKEN")

if not BOT_TOKEN:
    logger.critical("BOT_TOKEN не задан. Проверьте .env файл.")
    exit("Отсутствует BOT_TOKEN")

logger.info("Инициализация бота...")
bot = Bot(token=BOT_TOKEN)
logger.info("Инициализация хранилища состояний (MemoryStorage)...")
storage = MemoryStorage()

logger.info("Инициализация диспетчера...")
dp = Dispatcher(storage=storage)

logger.info("Бот инициализирован.")
