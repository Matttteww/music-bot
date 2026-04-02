"""Обработчики старта и главного меню."""
from aiogram import Bot, Router, F, html
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import get_or_create_user, register_referral_invite
from keyboards import main_menu_keyboard, BTN_MAIN_MENU
from subscription import is_subscribed, subscribe_keyboard, MSG_SUBSCRIBE

router = Router(name="start")


def _parse_start_referrer_id(text: str | None) -> int | None:
    """Диплинк t.me/bot?start=ref_USER_ID → /start ref_USER_ID."""
    if not text:
        return None
    t = text.strip()
    if not t.startswith("/start"):
        return None
    parts = t.split(maxsplit=1)
    if len(parts) < 2:
        return None
    payload = parts[1].strip().split()[0]
    if not payload.startswith("ref_"):
        return None
    try:
        return int(payload[4:])
    except ValueError:
        return None


async def _send_main_menu(bot: Bot, chat_id: int, is_new: bool, name: str) -> None:
    """Отправляет приветствие и главное меню."""
    if is_new:
        text = (
            f"👋 Привет, {name}!\n\n"
            "Добро пожаловать в бота оценки музыкальных треков.\n\n"
            "Здесь ты можешь:\n"
            "• Загружать свои треки и получать оценки\n"
            "• Голосовать за треки других исполнителей\n"
            "• Смотреть рейтинги лучших треков и исполнителей\n\n"
            "Выбери действие:"
        )
    else:
        text = f"С возвращением, {name}! Чем займёмся?"
    await bot.send_message(chat_id, text, reply_markup=main_menu_keyboard())


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    """Команда /start — проверка подписки, регистрация и приветствие."""
    user = message.from_user
    if not user:
        return

    ref_by = _parse_start_referrer_id(message.text)
    if ref_by is not None:
        await register_referral_invite(user.id, ref_by)

    if not await is_subscribed(bot, user.id):
        await message.answer(MSG_SUBSCRIBE, reply_markup=subscribe_keyboard())
        return

    is_new = await get_or_create_user(
        user_id=user.id,
        username=user.username or str(user.id),
        full_name=user.full_name or "User",
    )
    name = html.quote(user.full_name or user.username or "Пользователь")
    await _send_main_menu(bot, message.chat.id, is_new, name)


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery, bot: Bot) -> None:
    """Проверка подписки по нажатию кнопки."""
    user = callback.from_user
    if not user:
        return

    if not await is_subscribed(bot, user.id):
        await callback.answer("Подпишись на канал и попробуй снова", show_alert=True)
        return

    await callback.answer("✅ Подписка подтверждена!")
    if not callback.message:
        return
    is_new = await get_or_create_user(
        user_id=user.id,
        username=user.username or str(user.id),
        full_name=user.full_name or "User",
    )
    name = html.quote(user.full_name or user.username or "Пользователь")
    try:
        await callback.message.edit_text(
            f"✅ Отлично, {name}! Добро пожаловать.",
            reply_markup=None,
        )
    except Exception:
        pass
    await _send_main_menu(bot, callback.message.chat.id, is_new, name)


@router.message(F.text == "/myid")
async def cmd_myid(message: Message) -> None:
    """Показать свой chat_id (для настройки REPORT_CHAT_ID)."""
    await message.answer(f"Твой chat_id: <code>{message.chat.id}</code>\n\nСкопируй и укажи в переменной REPORT_CHAT_ID.")


@router.message(F.text == BTN_MAIN_MENU)
async def back_to_main(message: Message, state: FSMContext) -> None:
    """Возврат в главное меню."""
    await state.clear()
    await message.answer("Выбери действие:", reply_markup=main_menu_keyboard())
