"""Обработчики старта и главного меню."""
from aiogram import Bot, Router, F, html
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import get_or_create_user, register_referral_invite
from keyboards import (
    main_menu_keyboard,
    role_menu_keyboard,
    listener_intro_keyboard,
    artist_intro_keyboard,
    streamer_intro_keyboard,
    BTN_MAIN_MENU,
    BTN_ROLE_LISTENER,
    BTN_ROLE_ARTIST,
    BTN_ROLE_STREAMER,
    BTN_ARTIST_MY_TRACKS,
    BTN_ARTIST_PROMOTE,
    BTN_STREAM_FREE,
    BTN_STREAM_PREMIUM,
    BTN_STREAM_PRO,
    BTN_STREAM_START_SESSION,
)
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
    _ = is_new
    text = (
        f"👋 Добро пожаловать в Trackli, {name}!\n\n"
        "Здесь ты можешь:\n"
        "🎧 Оценивать треки и зарабатывать монеты\n"
        "🎤 Продвигать свою музыку\n"
        "📡 Попадать на стримы и получать аудиторию\n\n"
        "👇 Выбери, как ты хочешь использовать бота:"
    )
    await bot.send_message(chat_id, text, reply_markup=role_menu_keyboard())


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
    await message.answer(
        "Главное меню:\n"
        "• 🎵 Голосовать\n"
        "• 📤 Загрузить трек\n"
        "• 👤 Профиль\n"
        "• 🏆 Рейтинги\n"
        "• 👑 Царь SC\n"
        "• 🎁 Рефералы",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == BTN_ROLE_LISTENER)
async def start_listener_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🎧 <b>Оценивай треки и получай монеты</b>\n\n"
        "— Слушай музыку\n"
        "— Ставь оценки\n"
        "— Участвуй в турнирах\n\n"
        "Нажми «Начать», чтобы получить первый трек.",
        reply_markup=listener_intro_keyboard(),
    )


@router.message(F.text == BTN_ROLE_ARTIST)
async def start_artist_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🎤 <b>Продвигай свою музыку</b>\n\n"
        "— Получай оценки\n"
        "— Попадай на стримы\n"
        "— Расти в рейтингах\n\n"
        "👇 Выбери следующий шаг:",
        reply_markup=artist_intro_keyboard(),
    )


@router.message(F.text == BTN_ROLE_STREAMER)
async def start_streamer_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "📡 <b>Подключи бот к своему стриму</b>\n\n"
        "Ты получаешь:\n"
        "— поток треков\n"
        "— зрителей\n"
        "— доход\n\n"
        "👇 Выбери тариф:",
        reply_markup=streamer_intro_keyboard(),
    )


@router.message(F.text.in_({BTN_STREAM_FREE, BTN_STREAM_PREMIUM, BTN_STREAM_PRO}))
async def streamer_tariff_info(message: Message) -> None:
    await message.answer(
        "🎧 <b>Как это работает:</b>\n\n"
        "1. Треки приходят автоматически\n"
        "2. Ты слушаешь их на стриме\n"
        "3. Зрители оценивают\n"
        "4. Ты получаешь деньги/трафик\n\n"
        "Жми «▶️ Начать стрим-сессию», чтобы перейти к отправке треков в стрим-очередь.",
        reply_markup=streamer_intro_keyboard(),
    )


@router.message(F.text == BTN_STREAM_START_SESSION)
async def streamer_start_session(message: Message) -> None:
    await message.answer(
        "Запускаем стрим-сценарий. Нажми «🎙 Закинуть трек на стрим» в меню профиля.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == BTN_ARTIST_MY_TRACKS)
async def artist_my_tracks_hint(message: Message) -> None:
    await message.answer(
        "Открой «👤 Профиль» — там статистика и список твоих треков.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == BTN_ARTIST_PROMOTE)
async def artist_promote_hint(message: Message) -> None:
    await message.answer(
        "🚀 Продвижение ускоряет попадание в прослушивания и на стримы.\n"
        "Пока доступна базовая очередь: загрузи трек и следи за статистикой в профиле.",
        reply_markup=main_menu_keyboard(),
    )
