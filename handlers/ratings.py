"""Обработчики рейтингов."""
from aiogram import Router, F, html
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database import get_top_tracks, get_top_artists
from keyboards import ratings_menu_keyboard, back_to_ratings_keyboard, main_menu_keyboard, BTN_RATINGS, BTN_TOP_TRACKS, BTN_TOP_ARTISTS, BTN_BACK

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


@router.message(F.text == BTN_TOP_TRACKS)
async def show_top_tracks(message: Message, state: FSMContext) -> None:
    """ТОП-10 треков."""
    tracks = await get_top_tracks(limit=10)
    if not tracks:
        text = (
            "🎵 <b>ТОП треков</b>\n\n"
            "Пока нет треков с минимум 5 оценками.\n"
            "Оценивай треки — рейтинг появится!"
        )
    else:
        lines = ["🎵 <b>ТОП-10 треков</b>\n\n"]
        for i, t in enumerate(tracks, 1):
            avg = round(float(t.get('avg_score') or 0), 1)
            cnt = int(t.get('rating_count') or 0)
            lines.append(
                f"{i}. {html.quote(t['title'])} — @{html.quote(t.get('username', 'unknown'))}\n"
                f"   {avg}/10 ({cnt} оценок)"
            )
        text = "\n".join(lines)
    await state.set_state(RatingsState.viewing)
    await message.answer(text, reply_markup=back_to_ratings_keyboard())


@router.message(F.text == BTN_TOP_ARTISTS)
async def show_top_artists(message: Message, state: FSMContext) -> None:
    """ТОП-10 исполнителей."""
    artists = await get_top_artists(limit=10)
    if not artists:
        text = (
            "👤 <b>ТОП исполнителей</b>\n\n"
            "Пока нет исполнителей с минимум 10 оценками на все треки.\n"
            "Голосуй за треки — рейтинг появится!"
        )
    else:
        lines = ["👤 <b>ТОП-10 исполнителей</b>\n\n"]
        for i, a in enumerate(artists, 1):
            cnt = int(a.get('total_ratings') or 0)
            lines.append(
                f"{i}. @{html.quote(a.get('username', 'unknown'))} — {a['artist_avg']}/10 "
                f"({cnt} оценок)"
            )
        text = "\n".join(lines)
    await state.set_state(RatingsState.viewing)
    await message.answer(text, reply_markup=back_to_ratings_keyboard())


@router.message(RatingsState.menu, F.text == BTN_BACK)
async def back_from_ratings_menu(message: Message, state: FSMContext) -> None:
    """Назад из меню рейтингов в главное меню."""
    await state.clear()
    await message.answer("Выбери действие:", reply_markup=main_menu_keyboard())


@router.message(RatingsState.viewing, F.text == BTN_BACK)
async def back_from_top(message: Message, state: FSMContext) -> None:
    """Назад из топа в меню рейтингов."""
    await state.set_state(RatingsState.menu)
    await message.answer(
        "🏆 <b>Рейтинги</b>\n\nВыбери категорию:",
        reply_markup=ratings_menu_keyboard(),
    )
