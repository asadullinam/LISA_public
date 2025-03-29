import logging

from datetime import timedelta

from initialization.db_processor_init import db_processor
from database.models import VpnKey


logger = logging.getLogger(__name__)


# add_period: в днях
# возвращает новую дату конца активации ключа
def extend_key_in_db(key_id: str, add_period: int):
    session = db_processor.get_session()
    try:
        # Находим ключ по его ID
        key = session.query(VpnKey).filter_by(key_id=key_id).first()
        if not key:
            logger.error(f"Ключ с ID {key_id} не найден.")
            return False  # Возвращаем False в случае ошибки

        # Проверка, что expiration_date не None
        if not key.expiration_date:
            logger.error(f"У ключа с ID {key_id} отсутствует дата окончания.")
            return False

        # Продлеваем дату окончания
        key.expiration_date += timedelta(days=add_period)
        session.commit()
        logger.info(
            f"Ключ с ID {key_id} успешно продлён на {add_period} дней. Новая дата окончания: {key.expiration_date}"
        )
        return key.expiration_date  # Возвращаем True при успешном завершении

    except Exception as e:
        logger.error(f"Ошибка при продлении ключа с ID {key_id}: {e}")
        session.rollback()  # Откатываем изменения при ошибке
        return False
    finally:
        session.close()
