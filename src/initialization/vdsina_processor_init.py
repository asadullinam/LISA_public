import os

from dotenv import load_dotenv

from api_processors.vdsina_processor import VDSinaAPI
import logging

load_dotenv()
VDSINA_EMAIL = os.getenv("VDSINA_EMAIL")
VDSINA_PASSWORD = os.getenv("VDSINA_PASSWORD")

vdsina_processor = VDSinaAPI()

logger = logging.getLogger(__name__)


async def vdsina_processor_init():
    logger.info("Ожидание инициализации VDSina processor...")
    await vdsina_processor.authenticate(VDSINA_EMAIL, VDSINA_PASSWORD)
    logger.info("VDSina processor initialized")
