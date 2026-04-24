"""Обработчики рейтингов."""
from aiogram import Router, F, html, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils import pluralize_likes, pluralize_ratings
from database import (
    get_top_tracks,
    get_top_artists,
    get_track,
    get_user_tracks,
    get_user_display_info,
    get_user_favorites,
)
from keyboards import (
    ratings_menu_keyboard,
    back_to_ratings_keyboard,
    main_menu_keyboard,
    BTN_RATINGS,
    BTN_TOP_TRACKS,
    BTN_TOP_ARTISTS,
    BTN_TRACKS_DAY,
    BTN_TRACKS_RISING,
    BTN_TRACKS_WORST,
    BTN_FAVORITES,
    BTN_BACK,
)

router = Router(name="ratings")


class RatingsState(StatesGroup):
    menu = State()
    viewing = State()


@router.message(F.text == BTN_RATINGS)
async def show_ratings_menu(message: Message, state: FSMContext) -> None:
    """Меню рейтингов."""
    await state.set_state(RatingsState.menu)
    await message.answer(
        "🏆 <b>Рейтинги</b>\n\nВыбери категорию:",
        reply_markup=ratings_menu_keyboard(),
    )


def _track_listen_caption(title: str, username: str, source_url: str | None) -> str:
    """Подпись трека для прослушивания."""
    text = f"🎵 <b>{html.quote(title)}</b>\nИсполнитель: @{html.quote(username)}"
    if source_url:
        text += f"\n\n🔗 <a href=\"{source_url}\">Слушать на SoundCloud</a>"
    return text


async def _send_track_for_listen(bot: Bot, track: dict, chat_id: int) -> None:
    """Отправить трек для прослушивания (без кнопок оценки)."""
    caption = _track_listen_caption(
        track["title"],
        track.get("username") or "unknown",
        track.get("source_url"),
    )
    if track.get("source_url"):
        await bot.send_message(chat_id=chat_id, text=caption)
    else:
        await bot.send_audio(
            chat_id=chat_id,
            audio=track["file_id"],
            caption=caption,
        )


@router.message(F.text == BTN_TOP_TRACKS)
async def show_top_tracks(message: Message, state: FSMContext) -> None:
    """ТОП-10 треков с кнопками для прослушивания."""
    tracks = await get_top_tracks(limit=10)
    if not tracks:
        text = (
            "🎵 <b>ТОП треков</b>\n\n"
            "Пока нет оценённых треков. Голосуй — рейтинг появится!"
        )
        kb = back_to_ratings_keyboard()
    else:
        user = message.from_user
        uid = user.id if user else None
        in_top = uid is not None and any(t.get("user_id") == uid for t in tracks)

        lines = [
            "🎵 <b>Топ треков</b>",
            "",
            "Ниже — лидеры по среднему баллу. Жми кнопку, чтобы послушать.",
            "",
        ]
        builder = InlineKeyboardBuilder()
        for i, t in enumerate(tracks, 1):
            avg = round(float(t.get("avg_score") or 0), 1)
            cnt = int(t.get("rating_count") or 0)
            likes = int(t.get("likes_count") or 0)
            title_short = (t.get("title") or "?")[:35]
            medal = "🥇 " if i == 1 else "🥈 " if i == 2 else "🥉 " if i == 3 else ""
            title_esc = html.quote(t.get("title") or "?")
            artist_esc = html.quote(t.get("username") or "unknown")
            lines.append(f"{medal}<b>{i}.</b> {title_esc} · {artist_esc}")
            lines.append(
                f"   ╰ 🎧 {pluralize_ratings(cnt)} · ⭐️ {avg} средний балл · {pluralize_likes(likes)}"
            )
            lines.append("")
            builder.row(
                InlineKeyboardButton(
                    text=f"🎵 {title_short} ({avg}/10, {pluralize_likes(likes)})",
                    callback_data=f"listen:{t['track_id']}",
                )
            )
        if not in_top:
            lines.append("💡 Пока ни один твой трек не в этом топе — зови слушателей и копи оценки.")
        text = "\n".join(lines).rstrip()
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="ratings_back"))
        kb = builder.as_markup()
    await state.set_state(RatingsState.viewing)
    await message.answer(text, reply_markup=kb)


@router.message(F.text == BTN_TOP_ARTISTS)
async def show_top_artists(message: Message, state: FSMContext) -> None:
    """ТОП-10 исполнителей с кнопками — нажать = треки исполнителя."""
    artists = await get_top_artists(limit=10)
    if not artists:
        text = (
            "👤 <b>Топ исполнителей</b>\n\n"
            "Пока нет оценённых исполнителей. Голосуй — рейтинг появится!"
        )
        kb = back_to_ratings_keyboard()
    else:
        user = message.from_user
        uid = user.id if user else None
        in_top = uid is not None and any(a.get("user_id") == uid for a in artists)

        lines = [
            "👤 <b>Топ исполнителей</b>",
            "",
            "Сортировка по среднему баллу по всем трекам. Жми кнопку — откроется список треков.",
            "",
        ]
        builder = InlineKeyboardBuilder()
        for i, a in enumerate(artists, 1):
            cnt = int(a.get("total_ratings") or 0)
            likes = int(a.get("total_likes") or 0)
            avg = a["artist_avg"]
            uname = a.get("username", "unknown")
            uname_esc = html.quote(uname)
            medal = "🥇 " if i == 1 else "🥈 " if i == 2 else "🥉 " if i == 3 else ""
            lines.append(f"{medal}<b>{i}.</b> {uname_esc}")
            lines.append(
                f"   ╰ 🎧 {pluralize_ratings(cnt)} · ⭐️ {avg} средний балл · {pluralize_likes(likes)}"
            )
            lines.append("")
            builder.row(
                InlineKeyboardButton(
                    text=f"👤 @{uname[:25]} ({avg}/10, {pluralize_likes(likes)})",
                    callback_data=f"artist:{a['user_id']}",
                )
            )
        if not in_top:
            lines.append(
                "💡 Тебя пока нет в этом топе — качай средний балл и собирай оценки на треках."
            )
        text = "\n".join(lines).rstrip()
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="ratings_back"))
        kb = builder.as_markup()
    await state.set_state(RatingsState.viewing)
    await message.answer(text, reply_markup=kb)


@router.message(F.text.in_({BTN_TRACKS_DAY, BTN_TRACKS_RISING, BTN_TRACKS_WORST}))
async def show_extra_tracks_categories(message: Message, state: FSMContext) -> None:
    tracks = await get_top_tracks(limit=10)
    await state.set_state(RatingsState.viewing)
    if not tracks:
        await message.answer(
            "Пока нет данных для этой категории.",
            reply_markup=back_to_ratings_keyboard(),
        )
        return

    if message.text == BTN_TRACKS_DAY:
        track = tracks[0]
        await message.answer(
            f"🔥 <b>Трек дня</b>\n"
            f"{html.quote(track.get('title') or '?')} · @{html.quote(track.get('username') or 'unknown')}\n"
            f"⭐️ {round(float(track.get('avg_score') or 0), 1)}/10",
            reply_markup=back_to_ratings_keyboard(),
        )
        return

    if message.text == BTN_TRACKS_RISING:
        rising = sorted(tracks, key=lambda t: int(t.get("rating_count") or 0), reverse=True)[:5]
        lines = ["📈 <b>Растущие</b>", ""]
        for i, t in enumerate(rising, 1):
            lines.append(
                f"{i}. {html.quote(t.get('title') or '?')} "
                f"— {int(t.get('rating_count') or 0)} оценок"
            )
        await message.answer("\n".join(lines), reply_markup=back_to_ratings_keyboard())
        return

    worst = sorted(tracks, key=lambda t: float(t.get("avg_score") or 0))[:5]
    lines = ["💀 <b>Худшие</b>", ""]
    for i, t in enumerate(worst, 1):
        lines.append(
            f"{i}. {html.quote(t.get('title') or '?')} "
            f"— ⭐️ {round(float(t.get('avg_score') or 0), 1)}/10"
        )
    await message.answer("\n".join(lines), reply_markup=back_to_ratings_keyboard())


@router.message(RatingsState.menu, F.text == BTN_FAVORITES)
async def show_favorites(message: Message, state: FSMContext, bot: Bot) -> None:
    """Показать избранные треки пользователя."""
    user = message.from_user
    if not user:
        return

    tracks = await get_user_favorites(user.id)
    if not tracks:
        await message.answer(
            "❤️ <b>Избранные треки</b>\n\n"
            "У тебя пока нет избранных треков.\n"
            "Нажми «В избранное» при голосовании, чтобы добавить.",
            reply_markup=back_to_ratings_keyboard(),
        )
        await state.set_state(RatingsState.viewing)
        return

    lines = ["❤️ <b>Избранные треки</b>\n\nНажми на трек, чтобы послушать:"]
    builder = InlineKeyboardBuilder()
    for t in tracks[:20]:
        avg = round(float(t.get('avg_score') or 0), 1)
        cnt = int(t.get('rating_count') or 0)
        likes = int(t.get('likes_count') or 0)
        title_short = (t.get("title") or "?")[:35]
        builder.row(
            InlineKeyboardButton(
                text=f"🎵 {title_short} ({avg}/10, {pluralize_likes(likes)})",
                callback_data=f"listen:{t['track_id']}",
            )
        )
    if len(tracks) > 20:
        builder.row(
            InlineKeyboardButton(text=f"... ещё {len(tracks) - 20}", callback_data="noop"),
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="ratings_back"))
    text = "\n".join(lines)
    await state.set_state(RatingsState.viewing)
    await message.answer(text, reply_markup=builder.as_markup())


@router.message(RatingsState.menu, F.text == BTN_BACK)
async def back_from_ratings_menu(message: Message, state: FSMContext) -> None:
    """Назад из меню рейтингов в главное меню."""
    await state.clear()
    await message.answer("Выбери действие:", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "ratings_back")
async def callback_ratings_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Назад в меню рейтингов (из inline)."""
    await state.set_state(RatingsState.menu)
    try:
        await callback.message.edit_text(
            "🏆 <b>Рейтинги</b>\n\nВыбери категорию:",
            reply_markup=None,
        )
    except Exception:
        await callback.message.answer(
            "🏆 <b>Рейтинги</b>\n\nВыбери категорию:",
            reply_markup=ratings_menu_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("listen:"))
async def callback_listen_track(callback: CallbackQuery, bot: Bot) -> None:
    """Отправить трек для прослушивания."""
    track_id = int(callback.data.split(":")[1])
    track = await get_track(track_id)
    if not track:
        await callback.answer("Трек не найден.", show_alert=True)
        return
    await _send_track_for_listen(bot, track, callback.message.chat.id)
    await callback.answer("🎵")


@router.callback_query(F.data.startswith("artist:"))
async def callback_artist_tracks(callback: CallbackQuery) -> None:
    """Показать треки исполнителя со средним баллом."""
    user_id = int(callback.data.split(":")[1])
    tracks = await get_user_tracks(user_id)
    if not tracks:
        await callback.answer("У исполнителя нет треков.", show_alert=True)
        return
    disp = await get_user_display_info(user_id)
    uname = disp.get("display_name") or (f"@{disp['username']}" if disp.get("username") else "?")
    # Средний балл исполнителя по трекам
    artist_avg = 0.0
    total_rated = 0
    if tracks:
        weighted = sum(
            float(t.get("avg_score") or 0) * int(t.get("rating_count") or 0)
            for t in tracks
        )
        total_rated = sum(int(t.get("rating_count") or 0) for t in tracks)
        artist_avg = round(weighted / total_rated, 1) if total_rated else 0.0
    builder = InlineKeyboardBuilder()
    for t in tracks[:15]:
        avg = round(float(t.get("avg_score") or 0), 1)
        cnt = int(t.get("rating_count") or 0)
        likes = int(t.get("likes_count") or 0)
        title_short = (t.get("title") or "?")[:30]
        builder.row(
            InlineKeyboardButton(
                text=f"🎵 {title_short} — {avg}/10 ({cnt} оц., {pluralize_likes(likes)})",
                callback_data=f"listen:{t['track_id']}",
            )
        )
    if len(tracks) > 15:
        builder.row(
            InlineKeyboardButton(
                text=f"... ещё {len(tracks) - 15}",
                callback_data="noop",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="ratings_back"))
    text = (
        f"👤 <b>Треки {html.quote(uname)}</b>\n"
        f"Средний балл: {artist_avg}/10 ({total_rated} оценок)\n\n"
        "Нажми на трек, чтобы послушать:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(RatingsState.viewing, F.text == BTN_BACK)
async def back_from_top(message: Message, state: FSMContext) -> None:
    """Назад из топа в меню рейтингов."""
    await state.set_state(RatingsState.menu)
    await message.answer(
        "🏆 <b>Рейтинги</b>\n\nВыбери категорию:",
        reply_markup=ratings_menu_keyboard(),
    )
