"""Интеграция ЮKassa для монетизации."""
import asyncio
import logging
from typing import Optional

from config import (
    YOO_KASSA_ENABLED,
    YOOKASSA_SHOP_ID,
    YOOKASSA_SECRET_KEY,
    PRICE_TRACK,
    PRICE_PACK_5,
    PRICE_REPLACEMENT,
)
from database import (
    add_purchase,
    add_pending_payment,
    get_pending_payment,
    remove_pending_payment,
)

logger = logging.getLogger(__name__)

PRODUCTS = {
    "TRACK_39": (PRICE_TRACK, "1 трек", 1),
    "PACK_5_159": (PRICE_PACK_5, "Пакет 5 треков", 5),
    "REPLACEMENT_29": (PRICE_REPLACEMENT, "Доп. замена трека", 1),
}


def _create_payment_sync(user_id: int, product_type: str) -> tuple[Optional[str], Optional[str], int]:
    """Синхронное создание платежа. Возвращает (url, payment_id, amount) или (None, error, 0)."""
    if not YOO_KASSA_ENABLED:
        return None, "Оплата пока не настроена. Скоро будет доступна.", 0
    if product_type not in PRODUCTS:
        return None, "Неизвестный товар", 0
    price, description, qty = PRODUCTS[product_type]
    try:
        from yookassa import Configuration, Payment
        Configuration.configure(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
        payment = Payment.create({
            "amount": {"value": f"{price}.00", "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": "https://t.me/bigsomanii"},
            "capture": True,
            "description": f"{description} (user={user_id})",
            "metadata": {"user_id": user_id, "product_type": product_type},
        })
        url = payment.confirmation.confirmation_url if payment.confirmation else None
        pid = payment.id
        return url, pid, price
    except Exception as e:
        logger.exception("YooKassa create payment error: %s", e)
        return None, str(e), 0


def _check_payment_sync(payment_id: str) -> Optional[str]:
    """Проверить статус платежа. Возвращает 'succeeded' или None."""
    if not YOO_KASSA_ENABLED:
        return None
    try:
        from yookassa import Configuration, Payment
        Configuration.configure(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
        payment = Payment.find_one(payment_id)
        return payment.status if payment and payment.status == "succeeded" else None
    except Exception as e:
        logger.warning("YooKassa check payment error: %s", e)
        return None


PAYMENT_TIMEOUT = 15  # секунд на запрос к YooKassa

async def create_payment(user_id: int, product_type: str) -> tuple[Optional[str], Optional[str]]:
    """Создать платёж. Возвращает (url, payment_id) или (None, error)."""
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _create_payment_sync, user_id, product_type),
            timeout=PAYMENT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("YooKassa create payment timeout")
        return None, "Превышено время ожидания. Попробуй позже."
    url, pid_or_err, amount = result
    if url and pid_or_err and amount > 0:
        await add_pending_payment(pid_or_err, user_id, product_type, amount)
        return url, pid_or_err
    err = pid_or_err if isinstance(pid_or_err, str) else "Ошибка"
    return None, err


async def check_payment_status(payment_id: str) -> Optional[str]:
    """Проверить статус платежа асинхронно."""
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, _check_payment_sync, payment_id),
            timeout=PAYMENT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("YooKassa check payment timeout")
        return None
