"""Проверка подписки на обязательный канал."""
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import REQUIRED_CHANNEL

logger = logging.getLogger(__name__)

SUBSCRIBED_STATUSES = ("member", "administrator", "creator", "restricted")

MSG_SUBSCRIBE = (
    "🔒 Чтобы пользоваться ботом, нужно подписаться на канал.\n\n"
    "Подпишись и нажми «Проверить подписку»."
)


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """Проверяет, подписан ли пользователь на обязательный канал."""
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status in SUBSCRIBED_STATUSES
    except Exception as e:
        logger.warning("Ошибка проверки подписки для %s: %s", user_id, e)
        return False


def subscribe_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура: подписаться + проверить."""
    channel_username = REQUIRED_CHANNEL.lstrip("@")
    url = f"https://t.me/{channel_username}"
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Подписаться на канал", url=url),
    )
    builder.row(
        InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub"),
    )
    return builder.as_markup()


class SubscriptionMiddleware(BaseMiddleware):
    """Middleware: блокирует доступ, если пользователь не подписан на канал."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        user = None
        msg_or_cb = None

        if event.message:
            user = event.message.from_user
            msg_or_cb = event.message
            # /start — пропускаем (обработаем в start handler)
            if event.message.text and event.message.text.strip().startswith("/start"):
                return await handler(event, data)
        elif event.callback_query:
            user = event.callback_query.from_user
            msg_or_cb = event.callback_query.message
            # check_sub — пропускаем (проверка подписки)
            if event.callback_query.data == "check_sub":
                return await handler(event, data)

        if not user or not msg_or_cb:
            return await handler(event, data)

        if await is_subscribed(self.bot, user.id):
            return await handler(event, data)

        # Не подписан — показываем сообщение и не передаём в handler
        if event.callback_query:
            await event.callback_query.answer("Сначала подпишись на канал", show_alert=True)
        await self.bot.send_message(
            msg_or_cb.chat.id,
            MSG_SUBSCRIBE,
            reply_markup=subscribe_keyboard(),
        )
