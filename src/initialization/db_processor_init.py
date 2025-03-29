import os
from dotenv import load_dotenv

from database.db_processor import DbProcessor
from database.models import Server

load_dotenv()

# Инициализация объекта процессора БД
db_processor = DbProcessor()


def main_init_db():
    db_processor.init_db()


# def main_init_db():
#     db_processor.init_db()
#     with db_processor.session_scope() as session:
#         if session.query(Server).count() == 0:
#             servers = [
#                 Server(
#                     api_url=os.getenv("OUTLINE_API_URL"),
#                     cert_sha256=os.getenv("OUTLINE_CERT_SHA"),
#                     cnt_users=0,
#                     protocol_type="outline",
#                 ),
#                 Server(
#                     ip=os.getenv("VLESS_IP"),
#                     password=os.getenv("VLESS_PASSWORD"),
#                     cnt_users=100,
#                     protocol_type="vless",
#                 ),
#             ]
#             session.add_all(servers)
