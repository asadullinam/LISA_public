import asyncio
import aiocron
import logging
import uvicorn

from fastapi import FastAPI
from servers.redirect_server import redirect_server
from initialization.bot_init import dp, bot
from initialization.vdsina_processor_init import vdsina_processor_init
from initialization.db_processor_init import db_processor, main_init_db
from bot.routers import (
    admin_router,
    buy_key_router,
    key_management_router,
    key_params_router,
    main_menu_router,
    payment_router,
    trial_period_router,
    utils_router,
    choice_vpn_type_router,
)

from logger.logging_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)

logger.info("Регистрация обработчиков...")
dp.include_router(main_menu_router.router)
dp.include_router(payment_router.router)
dp.include_router(key_management_router.router)
dp.include_router(buy_key_router.router)
dp.include_router(key_params_router.router)
dp.include_router(trial_period_router.router)
dp.include_router(utils_router.router)
dp.include_router(choice_vpn_type_router.router)
dp.include_router(admin_router.router)

# 00:00 every day
@aiocron.crontab("0 0 * * *")
async def scheduled_check_and_delete_expired_keys():
    await db_processor.check_and_delete_expired_keys()

# 10:00 and 21:00 every day
@aiocron.crontab("0 7,18 * * *")
async def scheduled_check_and_notification_by_expired_keys():
    await db_processor.check_and_notification_by_expiring_keys()

# 01:00 every day
@aiocron.crontab("0 1 * * *")
async def scheduled_update_key_data_limit():
    await db_processor.check_and_update_key_data_limit()

# every 15 minutes
@aiocron.crontab("*/15 * * * *", start=True)
async def scheduled_check_servers():
    await db_processor.check_count_keys_on_servers()

# every hour + 10 minutes
@aiocron.crontab("10 * * * *")
async def scheduled_back_up_db():
    await db_processor.backup_bd()


async def main() -> None:
    await vdsina_processor_init()  # инициализируем VDSina API
    main_init_db()  # инициализируем БД 1ый раз при запуске
    logger.info("Запуск polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.error(f"Произошла ошибка при запуске бота: {e}")
