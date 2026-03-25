"""Фиксация последней активности пользователя для статистики «онлайн»."""
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from database import touch_user_activity

logger = logging.getLogger(__name__)


def _user_from_update(update: Update) -> tuple[int, str, str] | None:
    """(user_id, username, full_name) или None."""
    if update.message and update.message.from_user:
        u = update.message.from_user
        return u.id, u.username or "", u.full_name or ""
    if update.callback_query and update.callback_query.from_user:
        u = update.callback_query.from_user
        return u.id, u.username or "", u.full_name or ""
    if update.edited_message and update.edited_message.from_user:
        u = update.edited_message.from_user
        return u.id, u.username or "", u.full_name or ""
    if update.inline_query and update.inline_query.from_user:
        u = update.inline_query.from_user
        return u.id, u.username or "", u.full_name or ""
    if update.chosen_inline_result and update.chosen_inline_result.from_user:
        u = update.chosen_inline_result.from_user
        return u.id, u.username or "", u.full_name or ""
    return None


class ActivityMiddleware(BaseMiddleware):
    """Любое действие пользователя обновляет last_activity_at."""

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Update):
            info = _user_from_update(event)
            if info:
                uid, uname, fname = info
                try:
                    await touch_user_activity(uid, uname, fname)
                except Exception as e:
                    logger.warning("touch_user_activity failed: %s", e)
        return await handler(event, data)
