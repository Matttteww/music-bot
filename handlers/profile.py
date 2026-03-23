"""Обработчики профиля."""
from aiogram import Router, F, html
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import MAX_AUDIO_SIZE_BYTES, is_soundcloud_url, PAYMENTS_DISABLED, UNLIMITED_MODE
# from handlers.payments import pay_keyboard  # ВРЕМЕННО: импорт внутри при PAYMENTS_DISABLED=False
from database import (
    get_user_tracks,
    get_user_tracks_replaceable,
    get_user_stats,
    get_user_tracks_count,
    get_or_create_user,
    get_user_display_info,
    update_display_name,
    replace_track_and_reset_ratings,
    find_duplicate_track,
    get_free_replacements_left,
)
from handlers.upload import _get_audio_file_id_and_size
from keyboards import (
    profile_keyboard,
    main_menu_keyboard,
    cancel_keyboard,
    BTN_PROFILE,
    BTN_CHANGE_NICK,
    BTN_REPLACE_TRACK,
    BTN_CANCEL,
)

router = Router(name="profile")


class ChangeNick(StatesGroup):
    waiting_nick = State()


class ReplaceTrack(StatesGroup):
    choosing = State()
    waiting_audio = State()
    waiting_title = State()


def _tracks_select_keyboard(tracks: list[dict]) -> InlineKeyboardMarkup:
    """Inline-кнопки выбора трека для замены."""
    builder = InlineKeyboardBuilder()
    for t in tracks[:20]:
        title = (t.get("title") or "?")[:40]
        builder.row(
            InlineKeyboardButton(
                text=f"🎵 {title}",
                callback_data=f"repl_tr:{t['track_id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="repl_tr:cancel"))
    return builder.as_markup()


@router.message(F.text == BTN_PROFILE)
async def show_profile(message: Message, state: FSMContext) -> None:
    """Показать профиль пользователя."""
    user = message.from_user
    if not user:
        return

    await state.clear()
    await get_or_create_user(
        user_id=user.id,
        username=user.username or str(user.id),
        full_name=user.full_name or "User",
    )

    stats = await get_user_stats(user.id)
    tracks = await get_user_tracks(user.id)
    disp = await get_user_display_info(user.id)

    name = html.quote(disp["display_name"] or disp["username"] or "Пользователь")
    replacements_left = await get_free_replacements_left(user.id)
    tracks_count = await get_user_tracks_count(user.id)
    repl_text = "∞" if UNLIMITED_MODE else str(replacements_left)
    lines = [
        f"👤 <b>Профиль</b>",
        f"Исполнитель: {name}",
        f"Смен ника осталось: {disp['changes_left']}/3",
        f"Треков: {tracks_count} | Замен доступно: {repl_text}",
        "",
        f"📊 <b>Рейтинг исполнителя:</b> {stats['artist_avg']}/10",
        f"📈 <b>Всего оценок:</b> {stats['total_ratings']}",
        "",
        f"🎵 <b>Мои треки ({len(tracks)}):</b>",
    ]
    for i, t in enumerate(tracks[:15], 1):
        avg = round(float(t.get('avg_score') or 0), 1)
        cnt = int(t.get('rating_count') or 0)
        lines.append(
            f"  {i}. {html.quote(t['title'])} — "
            f"{avg}/10 ({cnt} оценок)"
        )
    if len(tracks) > 15:
        lines.append(f"  ... и ещё {len(tracks) - 15}")

    text = "\n".join(lines)
    await message.answer(
        text,
        reply_markup=profile_keyboard(
            disp["changes_left"],
            has_tracks=len(tracks) > 0,
        ),
    )


@router.message(F.text == BTN_CHANGE_NICK)
async def start_change_nick(message: Message, state: FSMContext) -> None:
    """Начать смену ника."""
    user = message.from_user
    if not user:
        return

    disp = await get_user_display_info(user.id)
    if disp["changes_left"] <= 0:
        await message.answer("Лимит смен ника исчерпан.")
        return

    await state.set_state(ChangeNick.waiting_nick)
    await message.answer(
        f"Введи новый ник (до 50 символов).\n\n"
        f"Смен осталось: {disp['changes_left']}/3",
        reply_markup=cancel_keyboard(),
    )


@router.message(ChangeNick.waiting_nick, Command("cancel"))
@router.message(ChangeNick.waiting_nick, F.text == BTN_CANCEL)
async def cancel_change_nick(message: Message, state: FSMContext) -> None:
    """Отмена смены ника."""
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu_keyboard())


@router.message(ChangeNick.waiting_nick, F.text)
async def receive_new_nick(message: Message, state: FSMContext) -> None:
    """Приём нового ника."""
    user = message.from_user
    if not user:
        await state.clear()
        return

    success, msg = await update_display_name(user.id, message.text or "")
    await state.clear()

    if success:
        await message.answer(msg, reply_markup=main_menu_keyboard())
    else:
        await message.answer(msg)


@router.message(ChangeNick.waiting_nick)
async def invalid_nick(message: Message) -> None:
    await message.answer("Отправь текстом новый ник. Для отмены нажми «❌ Отмена»")


# ----- Замена трека -----


@router.message(F.text == BTN_REPLACE_TRACK)
async def start_replace_track(message: Message, state: FSMContext) -> None:
    """Начать замену трека — показать список треков (только те, что ещё не заменялись)."""
    user = message.from_user
    if not user:
        return

    await state.clear()
    tracks = await get_user_tracks_replaceable(user.id)
    if not tracks:
        await message.answer(
            "У тебя нет треков для замены.",
            reply_markup=main_menu_keyboard(),
        )
        return

    replacements_left = await get_free_replacements_left(user.id)
    if replacements_left <= 0:
        # ВРЕМЕННО ОТКЛЮЧЕНО: kb = pay_keyboard("replace")
        if PAYMENTS_DISABLED:
            await message.answer(
                "Лимит бесплатных замен исчерпан (3/3). Оплата скоро будет доступна.",
                reply_markup=main_menu_keyboard(),
            )
        else:
            from handlers.payments import pay_keyboard
            kb = pay_keyboard("replace")
            await message.answer(
                "Лимит бесплатных замен исчерпан (3/3). Дополнительная замена — 29₽",
                reply_markup=kb or main_menu_keyboard(),
            )
        return

    await state.set_state(ReplaceTrack.choosing)
    await message.answer(
        "Выбери трек, который хочешь заменить:",
        reply_markup=_tracks_select_keyboard(tracks),
    )


@router.callback_query(F.data.startswith("repl_tr:"))
async def replace_track_select(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор трека для замены."""
    user = callback.from_user
    if not user:
        return

    if callback.data == "repl_tr:cancel":
        await state.clear()
        try:
            await callback.message.edit_text("Отмена.", reply_markup=None)
        except Exception:
            pass
        await callback.message.answer("Выбери действие:", reply_markup=main_menu_keyboard())
        await callback.answer()
        return

    track_id = int(callback.data.split(":")[1])
    tracks = await get_user_tracks_replaceable(user.id)
    if not any(t["track_id"] == track_id for t in tracks):
        await callback.answer("Трек не найден.", show_alert=True)
        return

    await state.update_data(replace_track_id=track_id)
    await state.set_state(ReplaceTrack.waiting_audio)
    try:
        await callback.message.edit_text(
            "Отправь новый аудиофайл (mp3, m4a, ogg) до 20 МБ\n"
            "или ссылку на SoundCloud.\n\n"
            "При замене статистика трека обнулится.",
            reply_markup=None,
        )
    except Exception:
        pass
    await callback.message.answer("Ожидаю файл или ссылку...", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(ReplaceTrack.waiting_audio, F.audio)
@router.message(ReplaceTrack.waiting_audio, F.document)
async def replace_receive_audio(message: Message, state: FSMContext) -> None:
    """Приём нового аудио для замены."""
    file_id, file_size, file_name = _get_audio_file_id_and_size(message)
    if not file_id:
        if message.document:
            await message.answer("Отправь аудиофайл (mp3, m4a, ogg).")
        return
    if file_size and file_size > MAX_AUDIO_SIZE_BYTES:
        await message.answer(
            f"Файл слишком большой. Максимум 20 МБ.\n"
            f"Размер: {file_size / (1024*1024):.1f} МБ"
        )
        return

    data = await state.get_data()
    replace_track_id = data.get("replace_track_id")
    if not replace_track_id:
        await state.clear()
        await message.answer("Ошибка. Начни заново.", reply_markup=main_menu_keyboard())
        return

    await state.update_data(file_id=file_id, source_url=None, file_name=file_name)
    await state.set_state(ReplaceTrack.waiting_title)
    await message.answer("Отлично! Введи название трека:", reply_markup=cancel_keyboard())


@router.message(ReplaceTrack.waiting_audio, F.text)
async def replace_receive_soundcloud(message: Message, state: FSMContext) -> None:
    """Приём ссылки SoundCloud для замены."""
    text = (message.text or "").strip()
    if not is_soundcloud_url(text):
        await message.answer(
            "Отправь аудиофайл или валидную ссылку SoundCloud.\n"
            "Пример: https://soundcloud.com/artist/track"
        )
        return

    data = await state.get_data()
    replace_track_id = data.get("replace_track_id")
    if not replace_track_id:
        await state.clear()
        await message.answer("Ошибка. Начни заново.", reply_markup=main_menu_keyboard())
        return

    await state.update_data(source_url=text, file_id=None, file_name=None)
    await state.set_state(ReplaceTrack.waiting_title)
    await message.answer("Отлично! Введи название трека:", reply_markup=cancel_keyboard())


@router.message(ReplaceTrack.waiting_audio, F.voice)
async def replace_reject_voice(message: Message) -> None:
    await message.answer("Отправь аудиофайл (mp3, m4a, ogg), а не голосовое.")


@router.message(ReplaceTrack.choosing)
async def replace_choosing_ignore(message: Message) -> None:
    await message.answer("Выбери трек кнопкой выше или нажми «❌ Отмена».")


@router.message(ReplaceTrack.waiting_audio)
async def replace_invalid_audio(message: Message) -> None:
    await message.answer("Отправь аудиофайл или ссылку SoundCloud. Для отмены нажми «❌ Отмена»")


@router.message(ReplaceTrack.waiting_audio, F.text == BTN_CANCEL)
@router.message(ReplaceTrack.waiting_title, F.text == BTN_CANCEL)
async def replace_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Замена отменена.", reply_markup=main_menu_keyboard())


@router.message(ReplaceTrack.waiting_title, F.text)
async def replace_receive_title(message: Message, state: FSMContext) -> None:
    """Приём названия и выполнение замены."""
    user = message.from_user
    if not user:
        await state.clear()
        return

    title = (message.text or "").strip()
    if not title:
        await message.answer("Введи корректное название:")
        return
    if len(title) > 200:
        await message.answer("Слишком длинное название. До 200 символов.")
        return

    data = await state.get_data()
    replace_track_id = data.get("replace_track_id")
    file_id = data.get("file_id") or None
    source_url = data.get("source_url") or None
    file_name = data.get("file_name")
    await state.clear()

    if not replace_track_id:
        await message.answer("Ошибка. Начни заново.", reply_markup=main_menu_keyboard())
        return

    dup = await find_duplicate_track(
        user.id, title=title, file_name=file_name, source_url=source_url,
        exclude_track_id=replace_track_id,
    )
    if dup:
        await message.answer(
            "⚠️ Такое название/файл уже есть у другого твоего трека.\n"
            "Выбери другое название или замени тот трек из профиля.",
            reply_markup=main_menu_keyboard(),
        )
        return

    ok, err_msg = await replace_track_and_reset_ratings(
        track_id=replace_track_id,
        user_id=user.id,
        file_id=file_id,
        source_url=source_url,
        title=title,
        file_name=file_name,
    )
    if ok:
        await message.answer(
            f"✅ Трек «{html.quote(title)}» заменён.\n\n"
            "⚠️ Статистика трека (оценки) обнулена.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await message.answer(
            err_msg or "Ошибка замены. Попробуй снова.",
            reply_markup=main_menu_keyboard(),
        )


@router.message(ReplaceTrack.waiting_title)
async def replace_invalid_title(message: Message) -> None:
    await message.answer("Отправь текстом название трека. Для отмены нажми «❌ Отмена»")
