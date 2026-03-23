"""Обработчики оплаты."""
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import PRICE_TRACK, PRICE_PACK_5, PRICE_REPLACEMENT
from keyboards import main_menu_keyboard
from payments import create_payment, PRODUCTS

router = Router(name="payments")
logger = logging.getLogger(__name__)


def pay_keyboard(block_reason: str) -> InlineKeyboardMarkup | None:
    """Кнопки оплаты в зависимости от причины блокировки."""
    builder = InlineKeyboardBuilder()
    if block_reason == "limit":
        builder.row(
            InlineKeyboardButton(text=f"1 трек — {PRICE_TRACK}₽", callback_data="pay:TRACK_39"),
            InlineKeyboardButton(text=f"5 треков — {PRICE_PACK_5}₽", callback_data="pay:PACK_5_159"),
        )
    elif block_reason == "replace":
        builder.row(
            InlineKeyboardButton(text=f"Замена — {PRICE_REPLACEMENT}₽", callback_data="pay:REPLACEMENT_29"),
        )
    return builder.as_markup() if builder.buttons else None


@router.callback_query(F.data.startswith("pay:"))
async def pay_callback(callback: CallbackQuery) -> None:
    """Обработка нажатия кнопки оплаты."""
    user = callback.from_user
    if not user:
        return

    product_type = callback.data.split(":")[1]
    if product_type not in PRODUCTS:
        await callback.answer("Неизвестный товар.", show_alert=True)
        return

    url, err = await create_payment(user.id, product_type)
    await callback.answer()

    if url:
        price, desc, _ = PRODUCTS[product_type]
        await callback.message.answer(
            f"Оплата {price}₽ — {desc}\n\n"
            f"Перейди по ссылке и оплати:\n{url}\n\n"
            "После оплаты слот будет зачислен в течение минуты.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await callback.message.answer(
            err or "Ошибка создания платежа.",
            reply_markup=main_menu_keyboard(),
        )
