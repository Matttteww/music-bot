"""Админ-команды: бан исполнителей, очистка треков. + fallback для необработанных апдейтов."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import REPORT_CHAT_ID
from database import ban_user, clear_all_tracks, get_admin_live_stats
from keyboards import main_menu_keyboard

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


@router.message()
async def fallback_unknown_message(message: Message, state: FSMContext) -> None:
    """Любое сообщение, не попавшее в другие обработчики."""
    await state.clear()
    await message.answer(
        "Используй кнопки меню для навигации 👇",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query()
async def fallback_unknown_callback(callback: CallbackQuery) -> None:
    """Любой callback, не попавший в другие обработчики (устаревшие кнопки и т.п.)."""
    await callback.answer()
