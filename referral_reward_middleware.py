"""Начисление реферального бонуса до обработчика (подписка уже проверена выше по цепочке)."""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from referral_service import try_complete_referral_reward


class ReferralRewardMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        bot = data.get("bot")
        if bot and isinstance(event, (Message, CallbackQuery)) and event.from_user:
            await try_complete_referral_reward(bot, event.from_user.id, event)
        return await handler(event, data)
