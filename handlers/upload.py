"""Обработчики загрузки треков."""
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import MAX_AUDIO_SIZE_BYTES, is_soundcloud_url, PAYMENTS_DISABLED, UNLIMITED_MODE
from database import (
    add_track,
    get_or_create_user,
    can_user_upload,
    update_after_upload,
    find_duplicate_track,
    replace_track_and_reset_ratings,
    get_free_replacements_left,
)
from keyboards import main_menu_keyboard, cancel_keyboard, BTN_UPLOAD, BTN_CANCEL

router = Router(name="upload")


class UploadTrack(StatesGroup):
    waiting_audio = State()
    waiting_title = State()
    replace_confirm = State()


@router.message(F.text == BTN_UPLOAD)
async def start_upload(message: Message, state: FSMContext) -> None:
    """Начало загрузки трека."""
    user = message.from_user
    if not user:
        return

    can_upload, needed, block_reason = await can_user_upload(user.id)
    if not can_upload:
        if block_reason == "limit":
            # ВРЕМЕННО ОТКЛЮЧЕНО: kb = pay_keyboard("limit") — при PAYMENTS_DISABLED показываем сообщение
            if PAYMENTS_DISABLED:
                await message.answer(
                    "📤 Лимит бесплатных треков (10) исчерпан.\n\nОплата скоро будет доступна.",
                    reply_markup=main_menu_keyboard(),
                )
            else:
                from handlers.payments import pay_keyboard
                kb = pay_keyboard("limit")
                await message.answer(
                    "📤 Лимит бесплатных треков (10) исчерпан.\n\n"
                    "Оплати дополнительные слоты:\n• 1 трек — 39₽\n• Пакет 5 треков — 159₽ (выгоднее!)",
                    reply_markup=kb or main_menu_keyboard(),
                )
        else:
            await message.answer(
                f"📤 Первые 3 трека можно загрузить без оценок. "
                f"После каждых 3 загруженных треков нужно оценить 5 чужих.\n\n"
                f"Осталось оценок: {needed}/5\n\n"
                f"Нажми «🎵 Голосовать», чтобы оценить треки.",
                reply_markup=main_menu_keyboard(),
            )
        return

    await state.set_state(UploadTrack.waiting_audio)
    await message.answer(
        "📤 Отправь аудиофайл (mp3, m4a, ogg) до 20 МБ\n"
        "или вставь ссылку на SoundCloud.\n\n"
        "После этого нужно будет указать название трека.",
        reply_markup=cancel_keyboard(),
    )


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


def _replace_confirm_keyboard(track_id: int) -> InlineKeyboardMarkup:
    """Кнопки: заменить файл / отмена."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Заменить файл", callback_data=f"replace_upload:{track_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="replace_upload:cancel"),
    )
    return builder.as_markup()


@router.message(UploadTrack.waiting_audio, F.audio)
@router.message(UploadTrack.waiting_audio, F.document)
async def receive_audio(message: Message, state: FSMContext, bot: Bot) -> None:
    """Приём аудиофайла."""
    file_id, file_size, file_name = _get_audio_file_id_and_size(message)
    if not file_id:
        if message.document:
            await message.answer(
                "Отправь аудиофайл (mp3, m4a, ogg). "
                "Документ должен быть с типом audio/*."
            )
        return
    if file_size and file_size > MAX_AUDIO_SIZE_BYTES:
        await message.answer(
            f"Файл слишком большой. Максимум 20 МБ.\n"
            f"Размер вашего файла: {file_size / (1024*1024):.1f} МБ"
        )
        return
    await state.update_data(file_id=file_id, source_url=None, file_name=file_name)
    await state.set_state(UploadTrack.waiting_title)
    await message.answer("Отлично! Теперь введи название трека:")


@router.message(UploadTrack.waiting_audio, F.text == BTN_CANCEL)
@router.message(UploadTrack.waiting_title, F.text == BTN_CANCEL)
@router.message(UploadTrack.replace_confirm, F.text == BTN_CANCEL)
async def cancel_upload(message: Message, state: FSMContext) -> None:
    """Отмена загрузки."""
    await state.clear()
    await message.answer("Загрузка отменена.", reply_markup=main_menu_keyboard())


@router.message(UploadTrack.waiting_audio, F.text)
async def receive_soundcloud_link(message: Message, state: FSMContext) -> None:
    """Приём ссылки на SoundCloud."""
    text = (message.text or "").strip()
    if not is_soundcloud_url(text):
        await message.answer(
            "Отправь аудиофайл или валидную ссылку SoundCloud.\n"
            "Пример: https://soundcloud.com/artist/track-name"
        )
        return
    await state.update_data(source_url=text, file_id=None, file_name=None)
    await state.set_state(UploadTrack.waiting_title)
    await message.answer("Отлично! Теперь введи название трека:")


@router.message(UploadTrack.waiting_audio, F.voice)
async def reject_voice(message: Message) -> None:
    await message.answer(
        "Пожалуйста, отправь именно аудиофайл (mp3, m4a, ogg), "
        "а не голосовое сообщение."
    )


@router.message(UploadTrack.waiting_audio)
async def invalid_audio(message: Message) -> None:
    await message.answer("Отправь аудиофайл или ссылку SoundCloud. Для отмены нажми «❌ Отмена»")


@router.message(UploadTrack.waiting_title, F.text)
async def receive_title(message: Message, state: FSMContext) -> None:
    """Приём названия трека. Проверка на дубликат."""
    title = (message.text or "").strip()
    if not title:
        await message.answer("Введи корректное название:")
        return
    if len(title) > 200:
        await message.answer("Слишком длинное название. До 200 символов.")
        return

    user = message.from_user
    if not user:
        await state.clear()
        return

    data = await state.get_data()
    file_id = data.get("file_id") or None
    source_url = data.get("source_url") or None
    file_name = data.get("file_name")

    await get_or_create_user(
        user_id=user.id,
        username=user.username or str(user.id),
        full_name=user.full_name or "User",
    )

    dup = await find_duplicate_track(
        user.id, title=title, file_name=file_name, source_url=source_url
    )
    if dup:
        replacements_left = await get_free_replacements_left(user.id)
        if replacements_left <= 0:
            if PAYMENTS_DISABLED:
                await message.answer(
                    "⚠️ Вы уже загружали этот трек. Лимит замен исчерпан. Оплата скоро будет доступна.",
                    reply_markup=main_menu_keyboard(),
                )
            else:
                from handlers.payments import pay_keyboard
                kb = pay_keyboard("replace")
                await message.answer(
                    "⚠️ Вы уже загружали этот трек. Лимит замен исчерпан. Доп. замена — 29₽",
                    reply_markup=kb or main_menu_keyboard(),
                )
            await state.clear()
            return
        await state.set_state(UploadTrack.replace_confirm)
        await state.update_data(
            existing_track_id=dup["track_id"],
            file_id=file_id,
            source_url=source_url,
            title=title,
            file_name=file_name,
        )
        repl_str = "∞" if UNLIMITED_MODE else f"{replacements_left}/3"
        await message.answer(
            "⚠️ Вы его уже загружали. Хотите поменять файл?\n\n"
            f"При замене статистика трека обнулится. Бесплатных замен осталось: {repl_str}",
            reply_markup=_replace_confirm_keyboard(dup["track_id"]),
        )
        return

    await state.clear()
    await add_track(
        user_id=user.id,
        title=title,
        genre="",
        file_id=file_id,
        source_url=source_url,
        file_name=file_name,
    )
    await update_after_upload(user.id)
    await message.answer(
        f"✅ Трек «{title}» успешно загружен!\n\n"
        "Он добавлен в пул для голосования. Другие пользователи смогут его оценить.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("replace_upload:"))
async def replace_upload_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора: заменить файл или отмена."""
    user = callback.from_user
    if not user:
        return

    if callback.data == "replace_upload:cancel":
        await state.clear()
        try:
            await callback.message.edit_text("Загрузка отменена.", reply_markup=None)
        except Exception:
            pass
        await callback.message.answer("Выбери действие:", reply_markup=main_menu_keyboard())
        await callback.answer()
        return

    track_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    existing_id = data.get("existing_track_id")
    if existing_id != track_id:
        await callback.answer("Ошибка: неверный трек.", show_alert=True)
        return

    file_id = data.get("file_id") or None
    source_url = data.get("source_url") or None
    title = data.get("title", "")
    file_name = data.get("file_name")
    await state.clear()

    ok, err_msg = await replace_track_and_reset_ratings(
        track_id=track_id,
        user_id=user.id,
        file_id=file_id,
        source_url=source_url,
        title=title,
        file_name=file_name,
    )
    if not ok:
        try:
            await callback.message.edit_text(
                err_msg or "Ошибка замены трека.",
                reply_markup=None,
            )
        except Exception:
            pass
        await callback.message.answer(
            "Выбери действие:",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(
        f"✅ Файл трека «{title}» заменён.\n\n"
        "⚠️ Статистика трека (оценки) обнулена.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer("Трек заменён")


@router.message(UploadTrack.replace_confirm)
async def replace_confirm_ignore(message: Message) -> None:
    """Ожидаем нажатия кнопки замены."""
    await message.answer("Нажми кнопку выше: «🔄 Заменить файл» или «❌ Отмена».")


@router.message(UploadTrack.waiting_title)
async def invalid_title(message: Message) -> None:
    await message.answer("Отправь текстом название трека. Для отмены нажми «❌ Отмена»")


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    """Отмена по /cancel."""
    current = await state.get_state()
    if current is None:
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu_keyboard())
