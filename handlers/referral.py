"""Экран реферальной программы."""
from aiogram import Router, F, html
from aiogram.types import Message

from config import BOT_USERNAME
from database import get_referral_coins, list_referrals_for_referrer
from keyboards import BTN_REFERRAL, main_menu_keyboard

router = Router(name="referral")


def referral_link_for_user(user_id: int) -> str | None:
    if not BOT_USERNAME:
        return None
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"


@router.message(F.text == BTN_REFERRAL)
async def show_referral_program(message: Message) -> None:
    if not message.from_user:
        return
    uid = message.from_user.id
    coins = await get_referral_coins(uid)
    link = referral_link_for_user(uid)
    rows = await list_referrals_for_referrer(uid)

    if link:
        link_block = f"<b>Твоя ссылка:</b>\n<code>{html.quote(link)}</code>"
    else:
        link_block = (
            "⚠️ Задай в настройках бота переменную <code>BOT_USERNAME</code> "
            "(username бота <b>без</b> @), чтобы ссылка открывалась в один тап.\n"
            f"Формат вручную: <code>t.me/ТВОЙ_БОТ?start=ref_{uid}</code>"
        )

    parts = [
        "🎁 <b>Реферальная программа</b>\n",
        "Пригласи друга по ссылке.\n"
        "💰 Ты получишь:\n"
        "+10 монет за активацию\n"
        "+5% от активности друга (механика в разработке)\n",
        link_block,
        f"\n<b>Твои монеты:</b> {coins}",
        "\n<b>Приглашённые (бонус начислен):</b>",
    ]
    if not rows:
        parts.append("— пока никого. Поделись ссылкой!")
    else:
        for r in rows:
            rid = r["referred_id"]
            label = r.get("display_name") or r.get("full_name") or r.get("username") or str(rid)
            label = html.quote(str(label).strip() or str(rid))
            parts.append(f"• {label} — +10 монет")

    await message.answer("\n".join(parts), reply_markup=main_menu_keyboard())
