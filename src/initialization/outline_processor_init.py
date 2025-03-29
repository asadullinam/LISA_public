import os
from dotenv import load_dotenv

from api_processors.outline_processor import OutlineProcessor

load_dotenv()

API_URL = os.getenv("OUTLINE_API_URL")
CERT_SHA256 = os.getenv("OUTLINE_CERT_SHA")

if not API_URL or not CERT_SHA256:
    raise ValueError(
        "Ошибка: Отсутствуют необходимые переменные окружения OUTLINE_API_URL или OUTLINE_CERT_SHA"
    )

async_outline_processor = OutlineProcessor()
