"""Стрим-очередь: зрители закидывают трек админу на оценку."""

from __future__ import annotations

from aiogram import Bot, F, html, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import MAX_AUDIO_SIZE_BYTES, REPORT_CHAT_ID, is_soundcloud_url
from database import (
    add_stream_submission,
    get_or_create_user,
    get_stream_submission,
    get_track,
    get_user_stream_submissions_count,
    get_user_tracks,
    is_stream_active,
    review_stream_submission_admin,
    start_stream,
    stop_stream_and_skip_waiting,
)
from keyboards import (
    BTN_CANCEL,
    BTN_STREAM_ADD,
    cancel_keyboard,
    main_menu_keyboard,
)

router = Router(name="stream")


class StreamAddState(StatesGroup):
    choosing_source = State()
    waiting_audio = State()
    waiting_title = State()


def _is_stream_admin(chat_id: int) -> bool:
    """Проверка: команда выполняется только в чате админа."""
    return bool(REPORT_CHAT_ID) and str(chat_id) == str(REPORT_CHAT_ID)


@router.message(Command("stream"))
async def stream_command(message: Message) -> None:
    """Админ управляет стрим-очередью.

    Использование:
    /stream start  — начать стрим (разрешить закидывать треки)
    /stream stop   — остановить стрим (закрыть очередь: waiting -> skipped)
    """
    if not message.chat:
        return
    if not _is_stream_admin(message.chat.id):
        return

    parts = (message.text or "").split()
    action = parts[1].lower() if len(parts) > 1 else ""

    if action in ("start", "on"):
        await start_stream()
        await message.answer("🎙 Стрим запущен. Можно закидывать треки на оценку.")
        return

    if action in ("stop", "end", "off"):
        skipped = await stop_stream_and_skip_waiting()
        await message.answer(
            f"🎙 Стрим остановлен. Очередь закрыта. Пропущено (waiting -> skipped): {skipped}"
        )
        return

    await message.answer("Используй: /stream start или /stream stop")


def _get_audio_file_id_and_size(message: Message) -> tuple[str | None, int | None, str | None]:
    """Получить file_id, размер и имя файла из аудио или документа."""
    if message.audio:
        a = message.audio
        return a.file_id, a.file_size, getattr(a, "file_name", None) or None
    if message.document:
        d = message.document
        if d.mime_type and d.mime_type.startswith("audio/"):
            return d.file_id, d.file_size, getattr(d, "file_name", None) or None
    return None, None, None


def _stream_admin_rate_keyboard(stream_item_id: int) -> InlineKeyboardMarkup:
    """Клавиатура админа: 0..10 и пропустить."""
    builder = InlineKeyboardBuilder()

    # 0..10 -> строки по 5 кнопок (0-4, 5-9, 10)
    scores = list(range(0, 11))
    chunked = [scores[:5], scores[5:10], scores[10:]]
    for ch in chunked:
        builder.row(
            *[
                InlineKeyboardButton(
                    text=str(s),
                    callback_data=f"stream_admin_rate:{stream_item_id}:{s}",
                )
                for s in ch
            ]
        )

    builder.row(
        InlineKeyboardButton(
            text="⏭️ Пропустить",
            callback_data=f"stream_admin_skip:{stream_item_id}",
        )
    )
    return builder.as_markup()


async def _send_to_stream_admin(bot: Bot, stream_item_id: int, sender: dict, title: str) -> None:
    """Отправить трек админу с кнопками оценивания."""
    if not REPORT_CHAT_ID:
        return

    item = await get_stream_submission(stream_item_id)
    if not item:
        return

    admin_chat_id = int(REPORT_CHAT_ID)
    sender_label = sender.get("username") or str(sender.get("user_id"))
    caption = (
        f"🎙 <b>Очередь стрима</b>\n\n"
        f"От: <b>{html.quote(str(sender_label))}</b>\n"
        f"Трек: {html.quote(title)}\n\n"
        "Оцени трек числом от 0 до 10 или нажми «Пропустить»."
    )

    kb = _stream_admin_rate_keyboard(stream_item_id)

    if item.get("source_url"):
        await bot.send_message(
            chat_id=admin_chat_id,
            text=caption + f"\n🔗 <a href=\"{item['source_url']}\">SoundCloud</a>",
            reply_markup=kb,
        )
    else:
        file_id = item.get("file_id")
        if not file_id:
            return
        await bot.send_audio(
            chat_id=admin_chat_id,
            audio=file_id,
            caption=caption,
            reply_markup=kb,
        )


@router.message(F.text == BTN_STREAM_ADD)
async def stream_add_start(message: Message, state: FSMContext) -> None:
    """Начать отправку трека на стрим."""
    user = message.from_user
    if not user:
        return

    if not await is_stream_active():
        await state.clear()
        await message.answer(
            "🎙 У bigsomani! стрим ещё не начался.\n"
            "Подожди, пока стример запустит его командой: /stream start",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.clear()
    await state.set_state(StreamAddState.choosing_source)
    await get_or_create_user(
        user_id=user.id,
        username=user.username or str(user.id),
        full_name=user.full_name or "User",
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Из твоих треков", callback_data="stream_pick:existing")],
            [InlineKeyboardButton(text="➕ Загрузить новый", callback_data="stream_pick:new")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="stream_pick:cancel")],
        ]
    )
    await message.answer("Куда отправить трек на стрим?", reply_markup=kb)


@router.callback_query(F.data == "stream_pick:cancel")
async def stream_pick_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Отменено.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "stream_pick:existing")
async def stream_pick_existing(callback: CallbackQuery, state: FSMContext) -> None:
    """Показать список треков пользователя."""
    user = callback.from_user
    if not user:
        await callback.answer()
        return

    if not await is_stream_active():
        await callback.answer(
            "Стрим ещё не начался.",
            show_alert=True,
        )
        await state.clear()
        return

    await state.clear()
    tracks = await get_user_tracks(user.id)
    if not tracks:
        await callback.message.answer(
            "У тебя пока нет треков для отправки на стрим.",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for t in tracks[:20]:
        builder.row(
            InlineKeyboardButton(
                text=(t.get("title") or "?")[:40],
                callback_data=f"stream_pick_track:{t['track_id']}",
            )
        )

    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="stream_pick:cancel"))
    await callback.message.answer("Выбери трек из своих:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "stream_pick:new")
async def stream_pick_new(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать загрузку нового трека именно для стрима."""
    user = callback.from_user
    if not user:
        await callback.answer()
        return

    if not await is_stream_active():
        await callback.answer("Стрим ещё не начался.", show_alert=True)
        await state.clear()
        return

    await state.clear()
    await state.set_state(StreamAddState.waiting_audio)
    await callback.message.answer(
        "📤 Отправь аудиофайл (mp3, m4a, ogg) до 20 МБ\nили вставь ссылку SoundCloud.\n\n"
        "После этого нужно будет указать название трека.",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(StreamAddState.waiting_audio, F.audio)
@router.message(StreamAddState.waiting_audio, F.document)
async def stream_receive_audio(message: Message, state: FSMContext) -> None:
    """Приём аудиофайла для стрим-трека."""
    file_id, file_size, _file_name = _get_audio_file_id_and_size(message)
    if not file_id:
        await message.answer("Отправь аудиофайл (mp3, m4a, ogg) или SoundCloud-ссылку.")
        return
    if file_size and file_size > MAX_AUDIO_SIZE_BYTES:
        await message.answer(
            f"Файл слишком большой. Максимум 20 МБ.\nТвой размер: {file_size / (1024*1024):.1f} МБ"
        )
        return

    await state.update_data(file_id=file_id, source_url=None)
    await state.set_state(StreamAddState.waiting_title)
    await message.answer("Отлично! Теперь введи название трека:")


@router.message(StreamAddState.waiting_audio, F.text == BTN_CANCEL)
async def stream_cancel_upload(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Загрузка отменена.", reply_markup=main_menu_keyboard())


@router.message(StreamAddState.waiting_audio, F.text)
async def stream_receive_soundcloud(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not is_soundcloud_url(text):
        await message.answer(
            "Отправь аудиофайл или валидную ссылку SoundCloud.\n"
            "Примеры: soundcloud.com/artist/track или on.soundcloud.com/xxxxx"
        )
        return
    await state.update_data(file_id=None, source_url=text)
    await state.set_state(StreamAddState.waiting_title)
    await message.answer("Отлично! Теперь введи название трека:")


@router.message(StreamAddState.waiting_title, F.text == BTN_CANCEL)
async def stream_cancel_title(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Загрузка отменена.", reply_markup=main_menu_keyboard())


@router.message(StreamAddState.waiting_title, F.text)
async def stream_receive_title(message: Message, state: FSMContext, bot: Bot) -> None:
    """Приём названия трека — создаём stream_queue item."""
    user = message.from_user
    if not user:
        await state.clear()
        return

    if not await is_stream_active():
        await state.clear()
        await message.answer(
            "🎙 У bigsomani! стрим ещё не начался. Попробуй отправить трек позже.",
            reply_markup=main_menu_keyboard(),
        )
        return

    title = (message.text or "").strip()
    if not title:
        await message.answer("Введи корректное название:")
        return
    if len(title) > 200:
        await message.answer("Слишком длинное название. До 200 символов.")
        return

    data = await state.get_data()
    file_id = data.get("file_id")
    source_url = data.get("source_url")

    # sender_user_id и название
    stream_item_id = await add_stream_submission(
        sender_user_id=user.id,
        title=title,
        file_id=file_id,
        source_url=source_url,
    )

    # отправляем админу
    sender = {"user_id": user.id, "username": user.username or str(user.id)}
    await state.clear()

    await _send_to_stream_admin(bot, stream_item_id, sender, title)
    await message.answer("✅ Трек отправлен на стрим. Ждёт оценки.", reply_markup=main_menu_keyboard())


@router.callback_query(F.data.startswith("stream_pick_track:"))
async def stream_pick_track_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Выбран трек из твоих треков — создаём стрим-очередь."""
    user = callback.from_user
    if not user:
        await callback.answer()
        return

    if not await is_stream_active():
        await callback.answer("Стрим ещё не начался.", show_alert=True)
        await state.clear()
        return

    track_id = int(callback.data.split(":", 1)[1])

    track = await get_track(track_id)
    if not track or int(track.get("user_id")) != user.id:
        await callback.answer("Ошибка: трек недоступен.", show_alert=True)
        return
    if int(track.get("user_id")) == user.id and int(track.get("deleted", 0) or 0) == 1:
        await callback.answer("Этот трек удалён.", show_alert=True)
        return

    stream_item_id = await add_stream_submission(
        sender_user_id=user.id,
        title=track.get("title") or "?",
        file_id=track.get("file_id"),
        source_url=track.get("source_url"),
    )

    await state.clear()
    sender = {"user_id": user.id, "username": track.get("username") or user.username or str(user.id)}
    await _send_to_stream_admin(bot, stream_item_id, sender, track.get("title") or "?")

    await callback.message.answer(
        "✅ Трек отправлен на стрим. Ждёт оценки.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("stream_admin_rate:"))
async def stream_admin_rate_callback(callback: CallbackQuery, bot: Bot) -> None:
    """Админ ставит оценку 0..10."""
    if not REPORT_CHAT_ID or str(callback.message.chat.id) != str(REPORT_CHAT_ID):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    _prefix, stream_item_id_str, score_str = callback.data.split(":", 2)
    stream_item_id = int(stream_item_id_str)
    score = int(score_str)

    ok, msg = await review_stream_submission_admin(
        stream_item_id=stream_item_id,
        score=score,
    )
    try:
        if ok:
            await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer(msg, show_alert=not ok)


@router.callback_query(F.data.startswith("stream_admin_skip:"))
async def stream_admin_skip_callback(callback: CallbackQuery) -> None:
    """Админ нажимает «Пропустить»."""
    if not REPORT_CHAT_ID or str(callback.message.chat.id) != str(REPORT_CHAT_ID):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    stream_item_id = int(callback.data.split(":", 1)[1])
    ok, msg = await review_stream_submission_admin(stream_item_id=stream_item_id, score=None)

    try:
        if ok:
            await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer(msg, show_alert=not ok)

