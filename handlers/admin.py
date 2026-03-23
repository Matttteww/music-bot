"""Админ-команды: бан исполнителей."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from config import REPORT_CHAT_ID
from database import ban_user

router = Router(name="admin")


@router.message(Command("ban"))
async def cmd_ban(message: Message) -> None:
    """Забанить исполнителя: /ban <user_id>"""
    if not REPORT_CHAT_ID or str(message.chat.id) != str(REPORT_CHAT_ID):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /ban <user_id>")
        return

    try:
        user_id = int(args[1])
        await ban_user(user_id)
        await message.answer(f"✅ Пользователь {user_id} заблокирован.")
    except ValueError:
        await message.answer("Укажи корректный user_id (число).")
