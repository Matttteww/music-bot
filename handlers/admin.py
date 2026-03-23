"""Админ-команды: бан исполнителей, очистка треков."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from config import REPORT_CHAT_ID
from database import ban_user, clear_all_tracks

router = Router(name="admin")


def _is_admin(chat_id: int) -> bool:
    return bool(REPORT_CHAT_ID and str(chat_id) == str(REPORT_CHAT_ID))


@router.message(Command("cleartracks"))
async def cmd_cleartracks(message: Message) -> None:
    """Удалить все треки и оценки (только для админа)."""
    if not _is_admin(message.chat.id):
        return
    count = await clear_all_tracks()
    await message.answer(f"✅ Удалено треков: {count}. База очищена.")


@router.message(Command("ban"))
async def cmd_ban(message: Message) -> None:
    """Забанить исполнителя: /ban <user_id>"""
    if not _is_admin(message.chat.id):
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
