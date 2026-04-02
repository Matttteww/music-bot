"""Начисление бонуса рефереру после подписки и действия приглашённого."""
import logging

from aiogram import Bot, html
from aiogram.types import CallbackQuery, Message

from database import get_pending_referral, get_referral_coins, get_user_display_label, pay_referral_bonus
from subscription import is_subscribed

logger = logging.getLogger(__name__)


async def try_complete_referral_reward(bot: Bot, user_id: int, event: Message | CallbackQuery) -> None:
    """
    Если у пользователя есть незакрытый реферал, он подписан на канал
    и событие — не «голый» /start, начислить рефереру 10 монет (один раз).
    """
    if isinstance(event, Message):
        if not event.text:
            return
        if event.text.strip().startswith("/start"):
            return
    elif not isinstance(event, CallbackQuery):
        return

    if await get_pending_referral(user_id) is None:
        return

    if not await is_subscribed(bot, user_id):
        return

    ok, referrer_id = await pay_referral_bonus(user_id)
    if not ok or referrer_id is None:
        return

    label = html.quote(await get_user_display_label(user_id))
    coins = await get_referral_coins(referrer_id)
    text = (
        f"🎉 +10 монет! Пользователь {label} подписался на канал и воспользовался ботом по твоей ссылке.\n"
        f"Твой баланс: <b>{coins}</b> монет."
    )
    try:
        await bot.send_message(referrer_id, text)
    except Exception as e:
        logger.warning("referral notify referrer %s: %s", referrer_id, e)
