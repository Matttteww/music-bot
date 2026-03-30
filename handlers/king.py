"""Режим «Царь SoundCloud'а»: турнир 1v1 из 10 случайных треков."""

from __future__ import annotations

import random

from aiogram import Bot, F, Router, html
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import add_king_win, get_king_tournament_tracks, get_track, get_user_display_info
from keyboards import BTN_KING, main_menu_keyboard

router = Router(name="king")


class KingState(StatesGroup):
    active = State()


def _pair_keyboard(left_id: int, right_id: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏆 Выбрать трек 1", callback_data=f"king_pick:{left_id}"),
        InlineKeyboardButton(text="🏆 Выбрать трек 2", callback_data=f"king_pick:{right_id}"),
    )
    builder.row(InlineKeyboardButton(text="❌ Выйти", callback_data="king_exit"))
    return builder


async def _send_track_preview(bot: Bot, chat_id: int, idx: int, track: dict) -> None:
    title = html.quote(track.get("title") or "?")
    artist = html.quote(track.get("username") or "unknown")
    caption = f"🎵 <b>Трек {idx}</b>\n{title}\nИсполнитель: {artist}"
    if track.get("source_url"):
        await bot.send_message(
            chat_id=chat_id,
            text=caption + f"\n🔗 <a href=\"{track['source_url']}\">Слушать на SoundCloud</a>",
        )
    else:
        await bot.send_audio(chat_id=chat_id, audio=track["file_id"], caption=caption)


async def _next_match_or_finish(state: FSMContext, bot: Bot, chat_id: int) -> bool:
    """Показать следующую пару или завершить турнир. Возвращает True если завершён."""
    data = await state.get_data()
    current = data.get("current_round") or []
    nxt = data.get("next_round") or []
    round_no = int(data.get("round_no") or 1)

    while len(current) < 2:
        if len(current) == 1:
            nxt.append(current.pop())

        if not current:
            if len(nxt) == 1:
                winner_track_id = int(nxt[0])
                winner_track = await get_track(winner_track_id)
                if not winner_track:
                    await state.clear()
                    await bot.send_message(chat_id, "Ошибка: победитель не найден.", reply_markup=main_menu_keyboard())
                    return True

                winner_user_id = int(winner_track["user_id"])
                await add_king_win(winner_user_id)

                # Уведомление победителю-исполнителю
                winner_disp = await get_user_display_info(winner_user_id)
                winner_name = winner_disp.get("display_name") or winner_disp.get("username") or str(winner_user_id)
                player_msg = (
                    "👑 <b>Царь SoundCloud'а завершён!</b>\n\n"
                    f"Победитель: <b>{html.quote(winner_track.get('title') or '?')}</b>\n"
                    f"Исполнитель: {html.quote(str(winner_name))}"
                )
                await bot.send_message(chat_id, player_msg, reply_markup=main_menu_keyboard())

                try:
                    await bot.send_message(
                        winner_user_id,
                        "🏆 Твой трек победил в «Царь SoundCloud'а»!\n"
                        "Тебе засчитана +1 победа в профиле.",
                    )
                except Exception:
                    pass

                await state.clear()
                return True

            current = list(nxt)
            random.shuffle(current)
            nxt = []
            round_no += 1

    left_id = int(current.pop(0))
    right_id = int(current.pop(0))
    await state.update_data(
        current_round=current,
        next_round=nxt,
        round_no=round_no,
        current_pair=[left_id, right_id],
    )

    left = await get_track(left_id)
    right = await get_track(right_id)
    if not left or not right:
        return await _next_match_or_finish(state, bot, chat_id)

    await bot.send_message(chat_id, f"⚔️ <b>Раунд {round_no}</b>\nСлушай 2 трека и выбери лучший:")
    await _send_track_preview(bot, chat_id, 1, left)
    await _send_track_preview(bot, chat_id, 2, right)
    await bot.send_message(
        chat_id=chat_id,
        text="Выбери победителя пары:",
        reply_markup=_pair_keyboard(left_id, right_id).as_markup(),
    )
    return False


@router.message(F.text == BTN_KING)
async def start_king(message: Message, state: FSMContext, bot: Bot) -> None:
    user = message.from_user
    if not user:
        return

    tracks = await get_king_tournament_tracks(user.id, limit=10)
    if len(tracks) < 2:
        await message.answer(
            "Недостаточно треков для турнира.\nНужно минимум 2 доступных трека других исполнителей.",
            reply_markup=main_menu_keyboard(),
        )
        return

    track_ids = [int(t["track_id"]) for t in tracks]
    random.shuffle(track_ids)

    await state.set_state(KingState.active)
    await state.update_data(
        current_round=track_ids,
        next_round=[],
        round_no=1,
        current_pair=[],
    )
    await message.answer(
        "👑 <b>Царь SoundCloud'а</b>\n"
        "Турнир начался! Выбирай лучший трек в каждой паре.",
    )
    await _next_match_or_finish(state, bot, message.chat.id)


@router.callback_query(F.data == "king_exit")
async def king_exit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Турнир остановлен.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("king_pick:"))
async def king_pick(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    user = callback.from_user
    if not user:
        await callback.answer()
        return

    data = await state.get_data()
    pair = data.get("current_pair") or []
    if len(pair) != 2:
        await callback.answer("Пара уже закрыта.", show_alert=True)
        return

    picked = int(callback.data.split(":", 1)[1])
    if picked not in pair:
        await callback.answer("Неверный выбор.", show_alert=True)
        return

    nxt = data.get("next_round") or []
    nxt.append(picked)
    await state.update_data(next_round=nxt, current_pair=[])

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.answer("Выбор принят!")
    await _next_match_or_finish(state, bot, callback.message.chat.id)

