"""Главный файл бота оценки музыкальных треков."""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, REENGAGEMENT_ENABLED, YOO_KASSA_ENABLED
from database import init_db, get_all_pending_payments, add_purchase, remove_pending_payment
from handlers import start, profile, upload, vote, ratings, king, admin, stream
# from handlers import payments  # ВРЕМЕННО ОТКЛЮЧЕНО: раскомментировать когда подключишь ЮKassa
from activity_middleware import ActivityMiddleware
from subscription import SubscriptionMiddleware
from ban_middleware import BanMiddleware
from reengagement import reengagement_loop

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MESSAGES = {
    "TRACK_39": "✅ Оплата получена! +1 слот для загрузки трека.",
    "PACK_5_159": "✅ Оплата получена! +5 слотов для загрузки треков.",
    "REPLACEMENT_29": "✅ Оплата получена! +1 замена трека.",
}


async def _payment_polling_task(bot: Bot) -> None:
    """Фоновая проверка статуса ожидающих платежей."""
    from payments import check_payment_status
    while True:
        try:
            await asyncio.sleep(30)
            pending = await get_all_pending_payments()
            for p in pending:
                status = await check_payment_status(p["payment_id"])
                if status == "succeeded":
                    await add_purchase(
                        p["user_id"],
                        p["product_type"],
                        p["amount"],
                        p["payment_id"],
                        quantity=1,
                    )
                    await remove_pending_payment(p["payment_id"])
                    msg = MESSAGES.get(p["product_type"], "✅ Оплата получена!")
                    try:
                        await bot.send_message(p["user_id"], msg)
                    except Exception:
                        pass
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Payment polling error: %s", e)


async def main() -> None:
    if not BOT_TOKEN:
        logger.error("Установи переменную окружения BOT_TOKEN")
        sys.exit(1)

    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(ActivityMiddleware())
    dp.update.outer_middleware(BanMiddleware(bot))
    dp.update.outer_middleware(SubscriptionMiddleware(bot))

    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(upload.router)
    dp.include_router(vote.router)
    dp.include_router(ratings.router)
    dp.include_router(king.router)
    dp.include_router(admin.router)
    dp.include_router(stream.router)
    # dp.include_router(payments.router)  # ВРЕМЕННО ОТКЛЮЧЕНО

    if YOO_KASSA_ENABLED:
        asyncio.create_task(_payment_polling_task(bot))

    if REENGAGEMENT_ENABLED:
        asyncio.create_task(reengagement_loop(bot))

    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
