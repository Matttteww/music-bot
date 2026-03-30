"""Админ-команды: бан исполнителей, очистка треков. + fallback для необработанных апдейтов."""
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import REPORT_CHAT_ID
from database import (
    ban_user,
    clear_all_tracks,
    get_admin_live_stats,
    get_user_id_by_username,
    unban_user,
)
from keyboards import main_menu_keyboard, BTN_STREAM_ADD, BTN_STREAM_EVALS, BTN_KING

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
    """Забанить исполнителя по @username: /ban @name"""
    if not _is_admin(message.chat.id):
        return

    m = re.search(r"@([A-Za-z0-9_]{3,32})", message.text or "")
    if not m:
        await message.answer("Использование: /ban @username")
        return

    try:
        username = m.group(1)
        user_id = await get_user_id_by_username(username)
        if not user_id:
            await message.answer(f"Пользователь @{username} не найден в базе.")
            return
        await ban_user(user_id)
        await message.answer(f"✅ Забанен: @{username} (id: {user_id}).")
    except Exception:
        await message.answer("Ошибка обработки команды /ban.")


@router.message(Command("unban"))
async def cmd_unban(message: Message) -> None:
    """Разбанить исполнителя по @username: /unban @name"""
    if not _is_admin(message.chat.id):
        return

    m = re.search(r"@([A-Za-z0-9_]{3,32})", message.text or "")
    if not m:
        await message.answer("Использование: /unban @username")
        return

    try:
        username = m.group(1)
        user_id = await get_user_id_by_username(username)
        if not user_id:
            await message.answer(f"Пользователь @{username} не найден в базе.")
            return
        ok = await unban_user(user_id)
        if ok:
            await message.answer(f"✅ Разбанен: @{username} (id: {user_id}).")
        else:
            await message.answer(f"ℹ️ @{username} не был в бане.")
    except Exception:
        await message.answer("Ошибка обработки команды /unban.")


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """Статистика активности (только админ)."""
    if not _is_admin(message.chat.id):
        return

    s = await get_admin_live_stats()
    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"🟢 Активны за последнюю минуту: <b>{s['active_last_minute']}</b>\n"
        f"🕐 Активны за последние 24 часа: <b>{s['active_last_24h']}</b>\n"
        f"👥 Всего пользователей бота: <b>{s['total_users']}</b>\n"
        f"📤 Загружали хотя бы один трек: <b>{s['uploaders_count']}</b>\n"
        f"🎵 Всего загруженных треков: <b>{s['tracks_total']}</b>\n"
        f"🧮 Оценённых треков: <b>{s['rated_tracks_count']}</b>\n"
        f"📝 Всего оценок треков: <b>{s['total_track_ratings']}</b>\n"
        f"⭐ Оценивали хотя бы один трек: <b>{s['raters_count']}</b>",
    )


@router.message(
    ~F.text.in_({BTN_STREAM_ADD, BTN_STREAM_EVALS, BTN_KING}),
    ~F.text.regexp(r"^/(streamon|streamoff|streanno)(@.+)?$"),
)
async def fallback_unknown_message(message: Message, state: FSMContext) -> None:
    """Любое сообщение, не попавшее в другие обработчики."""
    await state.clear()
    await message.answer(
        "Используй кнопки меню для навигации 👇",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(
    ~F.data.startswith("stream_"),
    ~F.data.startswith("king_"),
)
async def fallback_unknown_callback(callback: CallbackQuery) -> None:
    """Любой callback, не попавший в другие обработчики (устаревшие кнопки и т.п.)."""
    await callback.answer()
