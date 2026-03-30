"""Обработчики голосования."""
from aiogram import Router, F, Bot, html
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import REPORT_CHAT_ID
from database import (
    get_random_track_for_voting,
    add_rating,
    get_or_create_user,
    get_track,
    get_user_display_info,
    delete_track_and_warn_artist,
    ban_user,
    toggle_favorite,
    is_track_in_favorites,
)
from keyboards import (
    rating_keyboard,
    main_menu_keyboard,
    BTN_VOTE,
    BTN_STOP_VOTE,
    BTN_REPORT,
    BTN_FAVORITE_ADD,
    BTN_FAVORITE_REMOVE,
    BTN_REPORT_1,
    BTN_REPORT_2,
    BTN_REPORT_3,
    BTN_REPORT_4,
    BTN_REPORT_CANCEL,
    report_reason_keyboard,
    report_cancel_keyboard,
)

router = Router(name="vote")


class VotingState(StatesGroup):
    active = State()


class ReportState(StatesGroup):
    reason = State()
    custom = State()


def _format_track_caption(title: str, username: str, source_url: str | None = None) -> str:
    safe_title = html.quote(title or "?")
    safe_username = html.quote(username or "unknown")
    text = (
        f"🎵 <b>{safe_title}</b>\n"
        f"Исполнитель: @{safe_username}\n\n"
    )
    if source_url:
        text += f'🔗 <a href="{html.quote(source_url)}">Слушать на SoundCloud</a>\n\n'
    text += "Оцени трек от 1 до 10 (нажми кнопку):"
    return text


def _report_admin_keyboard(track_id: int) -> InlineKeyboardMarkup:
    """Кнопки админа: удалить трек / отклонить жалобу."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить трек", callback_data=f"adm_del:{track_id}"),
        InlineKeyboardButton(text="✅ Отклонить", callback_data=f"adm_ok:{track_id}"),
    )
    return builder.as_markup()


async def _send_report_to_admin(
    bot: Bot,
    track: dict,
    reporter_name: str,
    reporter_username: str,
    reason: str,
) -> bool:
    """Отправить жалобу админу: трек + текст с кнопками вердикта."""
    if not REPORT_CHAT_ID:
        return False
    title = track.get("title", "?")
    artist_name = track.get("username", "?")
    artist_id = track.get("user_id", "?")
    track_id = track.get("track_id", "?")
    source = track.get("source_url") or "Telegram file"

    report_text = (
        "🚩 <b>Жалоба на трек</b>\n\n"
        f"Трек: {html.quote(title)}\n"
        f"ID трека: {track_id}\n"
        f"Исполнитель: @{html.quote(str(artist_name))} (id: {artist_id})\n"
        f"Источник: {html.quote(str(source))}\n\n"
        f"Причина: {html.quote(reason)}\n\n"
        f"Пожаловался: {html.quote(reporter_name)} ({reporter_username})"
    )
    try:
        chat_id = int(REPORT_CHAT_ID)
        if track.get("source_url"):
            await bot.send_message(
                chat_id=chat_id,
                text=f"🎵 Трек на который жалоба:\n{html.quote(title)}\n🔗 {track['source_url']}",
            )
        else:
            await bot.send_audio(
                chat_id=chat_id,
                audio=track["file_id"],
                caption=f"🎵 Трек на который жалоба: {html.quote(title)}",
            )
        await bot.send_message(
            chat_id=chat_id,
            text=report_text,
            reply_markup=_report_admin_keyboard(track_id),
        )
        return True
    except Exception:
        return False


async def _send_track(
    message: Message, bot: Bot, track: dict, chat_id: int, user_id: int
) -> None:
    """Отправить трек (аудио или сообщение со ссылкой SoundCloud)."""
    in_fav = await is_track_in_favorites(user_id, track["track_id"])
    caption = _format_track_caption(
        track["title"],
        track.get("username") or "unknown",
        track.get("source_url"),
    )
    if track.get("source_url"):
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=rating_keyboard(in_favorites=in_fav),
        )
    else:
        await bot.send_audio(
            chat_id=chat_id,
            audio=track["file_id"],
            caption=caption,
            reply_markup=rating_keyboard(in_favorites=in_fav),
        )


@router.message(F.text == BTN_VOTE)
async def send_track_for_voting(message: Message, state: FSMContext, bot: Bot) -> None:
    """Отправить случайный трек для голосования."""
    user = message.from_user
    if not user:
        return

    await state.clear()
    await get_or_create_user(
        user_id=user.id,
        username=user.username or str(user.id),
        full_name=user.full_name or "User",
    )

    track = await get_random_track_for_voting(user.id)
    if not track:
        await message.answer(
            "😔 Нет доступных треков для оценки.\n\n"
            "Загрузи свой трек или дождись появления новых!",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.set_state(VotingState.active)
    await state.update_data(track_id=track["track_id"])
    await _send_track(message, bot, track, message.chat.id, user.id)


@router.message(VotingState.active, F.text.in_({BTN_FAVORITE_ADD, BTN_FAVORITE_REMOVE}))
async def toggle_favorite_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    """Добавить/убрать трек из избранного."""
    user = message.from_user
    if not user:
        return

    data = await state.get_data()
    track_id = data.get("track_id")
    if not track_id:
        return

    ok, now_in_fav = await toggle_favorite(user.id, track_id)
    if not ok:
        return

    if now_in_fav:
        await message.answer("❤️ Добавлено в избранное")
    else:
        await message.answer("💔 Убрано из избранного")

    track = await get_track(track_id)
    if track:
        await _send_track(message, bot, track, message.chat.id, user.id)


@router.message(VotingState.active, F.text == BTN_STOP_VOTE)
async def stop_voting(message: Message, state: FSMContext) -> None:
    """Выход из голосования."""
    await state.clear()
    await message.answer("Выбери действие:", reply_markup=main_menu_keyboard())


@router.message(VotingState.active, F.text == BTN_REPORT)
async def start_report(message: Message, state: FSMContext) -> None:
    """Начать жалобу — показать выбор причины."""
    data = await state.get_data()
    track_id = data.get("track_id")
    if not track_id:
        await message.answer("Ошибка: трек не найден.", reply_markup=main_menu_keyboard())
        await state.clear()
        return

    await state.set_state(ReportState.reason)
    await state.update_data(track_id=track_id)
    await message.answer(
        "На что жалуешься? Выбери причину:",
        reply_markup=report_reason_keyboard(),
    )


@router.message(ReportState.reason, F.text.in_({BTN_REPORT_1, BTN_REPORT_2, BTN_REPORT_3}))
async def report_with_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    """Жалоба с выбранной причиной 1–3."""
    user = message.from_user
    if not user:
        return

    data = await state.get_data()
    track_id = data.get("track_id")
    if not track_id:
        await state.clear()
        await message.answer("Ошибка.", reply_markup=main_menu_keyboard())
        return

    track = await get_track(track_id)
    if not track:
        await message.answer("Трек не найден.", reply_markup=main_menu_keyboard())
        await state.clear()
        return

    reason_map = {
        BTN_REPORT_1: "Неподобающий контент",
        BTN_REPORT_2: "Оскорбительный контент",
        BTN_REPORT_3: "Реклама запрещёнки",
    }
    reason = reason_map.get(message.text, message.text)
    reporter_name = user.full_name or user.username or f"id{user.id}"
    reporter_username = f"@{user.username}" if user.username else f"id{user.id}"

    ok = await _send_report_to_admin(bot, track, reporter_name, reporter_username, reason)
    await state.clear()

    if ok:
        await message.answer(
            "Жалоба отправлена. Спасибо за помощь!",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await message.answer(
            "Жалобы пока не настроены. Обратитесь к @bigsomanii.",
            reply_markup=main_menu_keyboard(),
        )


@router.message(ReportState.reason, F.text == BTN_REPORT_CANCEL)
async def report_reason_cancel(message: Message, state: FSMContext, bot: Bot) -> None:
    """Отмена выбора причины — вернуться к треку."""
    data = await state.get_data()
    track_id = data.get("track_id")
    await state.set_state(VotingState.active)
    await state.update_data(track_id=track_id)
    track = await get_track(track_id)
    user = message.from_user
    if track and user:
        await _send_track(message, bot, track, message.chat.id, user.id)
    else:
        await state.clear()
        await message.answer("Выбери действие:", reply_markup=main_menu_keyboard())


@router.message(ReportState.reason, F.text == BTN_REPORT_4)
async def report_other_reason(message: Message, state: FSMContext) -> None:
    """Выбрана «другая причина» — ждём текст от пользователя."""
    await state.set_state(ReportState.custom)
    await message.answer(
        "Опиши причину жалобы и отправь сообщение:",
        reply_markup=report_cancel_keyboard(),
    )


@router.message(ReportState.custom, F.text == BTN_REPORT_CANCEL)
async def report_cancel(message: Message, state: FSMContext, bot: Bot) -> None:
    """Отмена жалобы — вернуться к голосованию."""
    user = message.from_user
    if not user:
        return
    data = await state.get_data()
    track_id = data.get("track_id")
    await state.set_state(VotingState.active)
    await state.update_data(track_id=track_id)

    track = await get_track(track_id)
    if track:
        await _send_track(message, bot, track, message.chat.id, user.id)
    else:
        await state.clear()
        await message.answer("Выбери действие:", reply_markup=main_menu_keyboard())


@router.message(ReportState.custom, F.text)
async def report_custom_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    """Жалоба с произвольным текстом причины."""
    user = message.from_user
    if not user:
        return

    data = await state.get_data()
    track_id = data.get("track_id")
    if not track_id:
        await state.clear()
        await message.answer("Ошибка.", reply_markup=main_menu_keyboard())
        return

    track = await get_track(track_id)
    if not track:
        await message.answer("Трек не найден.", reply_markup=main_menu_keyboard())
        await state.clear()
        return

    reason = (message.text or "").strip() or "Не указана"
    reporter_name = user.full_name or user.username or f"id{user.id}"
    reporter_username = f"@{user.username}" if user.username else f"id{user.id}"

    ok = await _send_report_to_admin(bot, track, reporter_name, reporter_username, reason)
    await state.clear()

    if ok:
        await message.answer(
            "Жалоба отправлена. Спасибо за помощь!",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await message.answer(
            "Жалобы пока не настроены. Обратитесь к @bigsomanii.",
            reply_markup=main_menu_keyboard(),
        )


@router.message(ReportState.reason)
async def report_reason_invalid(message: Message) -> None:
    """Некорректный ввод при выборе причины."""
    await message.answer("Выбери одну из кнопок причины жалобы.")


@router.message(ReportState.custom)
async def report_custom_invalid(message: Message) -> None:
    """Некорректный ввод при описании причины."""
    await message.answer("Опиши причину текстом или нажми «◀️ Отмена».")


@router.callback_query(F.data.startswith("adm_del:"))
async def admin_delete_track(callback: CallbackQuery, bot: Bot) -> None:
    """Админ удаляет трек по жалобе: предупреждение исполнителю, при 3 — бан."""
    if not REPORT_CHAT_ID or str(callback.message.chat.id) != str(REPORT_CHAT_ID):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    track_id = int(callback.data.split(":")[1])
    track = await get_track(track_id)
    title = track.get("title", "трек") if track else "трек"
    ok, artist_id, warnings = await delete_track_and_warn_artist(track_id)
    if not ok:
        await callback.answer("Трек не найден или уже удалён.", show_alert=True)
        return

    # Предупреждение исполнителю в ЛС с названием трека
    warn_text = (
        "⚠️ <b>Предупреждение</b>\n\n"
        f"Твой трек «{html.quote(title)}» был удалён по жалобе.\n"
        f"Предупреждений: {warnings}/3.\n\n"
        "При трёх предупреждениях доступ будет заблокирован."
    )
    try:
        await bot.send_message(chat_id=artist_id, text=warn_text)
    except Exception:
        pass  # пользователь мог заблокировать бота

    if warnings >= 3:
        await ban_user(artist_id)
        try:
            await bot.send_message(
                chat_id=artist_id,
                text="🚫 Ты получил 3 предупреждения. Доступ к боту заблокирован.",
            )
        except Exception:
            pass

    new_text = callback.message.text or ""
    if "✅ Трек удалён" not in new_text:
        new_text = new_text.rstrip() + "\n\n✅ <b>Трек удалён.</b>"
    await callback.message.edit_text(new_text, reply_markup=None)
    await callback.answer("Трек удалён, предупреждение отправлено.")


@router.callback_query(F.data.startswith("adm_ok:"))
async def admin_reject_report(callback: CallbackQuery) -> None:
    """Админ отклоняет жалобу."""
    if not REPORT_CHAT_ID or str(callback.message.chat.id) != str(REPORT_CHAT_ID):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    new_text = callback.message.text or ""
    if "❌ Жалоба отклонена" not in new_text:
        new_text = new_text.rstrip() + "\n\n❌ <b>Жалоба отклонена.</b>"
    await callback.message.edit_text(new_text, reply_markup=None)
    await callback.answer("Жалоба отклонена.")


@router.message(VotingState.active, F.text.in_({"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}))
async def process_rating(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработка оценки (кнопка 1-10)."""
    user = message.from_user
    if not user:
        return

    data = await state.get_data()
    track_id = data.get("track_id")
    if not track_id:
        await state.clear()
        return

    score = int(message.text)

    success, msg = await add_rating(track_id=track_id, user_id=user.id, score=score)
    if not success:
        await message.answer(msg)
        return

    # Уведомить автора трека об оценке
    rated_track = await get_track(track_id)
    if rated_track and rated_track.get("user_id") != user.id:
        artist_id = rated_track["user_id"]
        title = rated_track.get("title") or "трек"
        voter_info = await get_user_display_info(user.id)
        voter_name = (
            voter_info.get("display_name")
            or (f"@{voter_info['username']}" if voter_info.get("username") else None)
            or user.full_name
            or "Пользователь"
        )
        voter_name_safe = voter_name if str(voter_name).startswith("@") else html.quote(str(voter_name))
        notify_text = f"{voter_name_safe} оценил ваш трек «{html.quote(title)}» на {score} баллов."
        try:
            await bot.send_message(artist_id, notify_text)
        except Exception:
            pass

    track = await get_random_track_for_voting(user.id)
    if track:
        await state.update_data(track_id=track["track_id"])
        await _send_track(message, bot, track, message.chat.id, user.id)
    else:
        await state.clear()
        await message.answer(
            "✅ Спасибо за оценку!\n\n😔 Пока нет других треков для оценки.\nЗагрузи свой трек или заходи позже!",
            reply_markup=main_menu_keyboard(),
        )
