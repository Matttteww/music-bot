"""Middleware: блокировка забаненных пользователей."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Update

from database import is_user_banned


class BanMiddleware(BaseMiddleware):
    """Если user_id есть в banned_users — не пропускаем апдейт в хэндлеры."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        user = None
        msg_or_cb = None

        if event.message and event.message.from_user:
            user = event.message.from_user
            msg_or_cb = event.message
        elif event.callback_query and event.callback_query.from_user:
            user = event.callback_query.from_user
            msg_or_cb = event.callback_query.message
        elif event.edited_message and event.edited_message.from_user:
            user = event.edited_message.from_user
            msg_or_cb = event.edited_message

        if not user or not msg_or_cb:
            return await handler(event, data)

        if await is_user_banned(user.id):
            chat_id = msg_or_cb.chat.id
            if event.callback_query:
                await event.callback_query.answer("🚫 Ты заблокирован.", show_alert=True)
                return None

            await self.bot.send_message(chat_id=chat_id, text="🚫 Ты заблокирован.")
            return None

        return await handler(event, data)

