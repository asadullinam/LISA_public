import os

from dotenv import load_dotenv

from api_processors.vless_processor import VlessProcessor

load_dotenv()

vless_ip = os.getenv("VLESS_IP")
vless_password = os.getenv("VLESS_PASSWORD")

vless_processor = VlessProcessor(ip=vless_ip, password=vless_password)
