"""Обработчики старта и главного меню."""
from aiogram import Router, F, html
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import get_or_create_user
from keyboards import main_menu_keyboard, BTN_MAIN_MENU

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Команда /start — регистрация и приветствие."""
    user = message.from_user
    if not user:
        return
    is_new = await get_or_create_user(
        user_id=user.id,
        username=user.username or str(user.id),
        full_name=user.full_name or "User",
    )
    name = html.quote(user.full_name or user.username or "Пользователь")
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

    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(F.text == "/myid")
async def cmd_myid(message: Message) -> None:
    """Показать свой chat_id (для настройки REPORT_CHAT_ID)."""
    await message.answer(f"Твой chat_id: <code>{message.chat.id}</code>\n\nСкопируй и укажи в переменной REPORT_CHAT_ID.")


@router.message(F.text == BTN_MAIN_MENU)
async def back_to_main(message: Message, state: FSMContext) -> None:
    """Возврат в главное меню."""
    await state.clear()
    await message.answer("Выбери действие:", reply_markup=main_menu_keyboard())
