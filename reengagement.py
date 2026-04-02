"""Напоминания неактивным пользователям (вернуться в бота)."""
import asyncio
import logging
import random

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import REENGAGEMENT_IDLE_MINUTES, REENGAGEMENT_POLL_SEC
from database import fetch_users_for_reengagement, mark_reengagement_sent

logger = logging.getLogger(__name__)

# Тематика: оценка треков, загрузки, голосование, рейтинги, король, стрим, избранное
REENGAGEMENT_MESSAGES: tuple[str, ...] = (
    "Бро, давно не видел тебя в боте — зайди, там снова крутят свежие треки на оценку 🎧",
    "Скучаем по твоим лайкам: без тебя голосование как будто тише. Загляни поставить баллы другим 🔥",
    "Ты пропал на 6+ часов — а рейтинги обновились. Может, глянешь топ и свои места?",
    "Есть минута? Закинь трек или ссылку на SoundCloud — пусть комьюнити оценит по 10-балльной шкале.",
    "Король недели не вечен 👑 Заходи в бот — вдруг пора отвоёвывать титул или просто посмотреть, кто в топе.",
    "Давно не загружал ничего нового? Слоты ждут — покажи, что слушают у тебя в наушниках.",
    "Голосовалка жива: кто-то только что залил трек и мечтает о честной оценке. Ты как раз подойдёшь.",
    "Стрим/очередь треков не спит без зрителей. Загляни — может, поймаешь момент, когда идёт разбор.",
    "Собери фавориты в избранное ⭐ Пока тебя не было, мимо прошло несколько бэнгеров — не упусти.",
    "Профиль и статистика скучают без твоих заходов. Зайди — проверь, как двигаются твои цифры.",
    "Без тебя средний балл по площадке чуть грустнее. Заходи поставить честные цифры — это реально помогает авторам.",
    "Ты как будто в творческом отпуске 😄 Вернись: кто-то ждёт фидбек по своему саунду.",
    "Рейтинг исполнителей перетасовался — интересно, где ты сейчас? Один тап в боте — и всё видно.",
    "Напоминаю мягко: тут не только заливать, но и слушать чужое и учиться по оценкам. Загляни на пару минут.",
    "Если давно не менял ник или данные — окно возможностей открыто. Плюс свежее меню с кучей кнопок.",
    "Кто-то залил жанр, который ты любишь — без твоего голоса топ будет неполным. Заходи проголосовать.",
    "Твой последний трек мог уже набрать новые оценки, пока ты офлайн. Проверь отклик комьюнити.",
    "Мы не спамим просто так — правда соскучились по активности. Зайди, кинь трек или хотя бы один круг по голосованию.",
    "Хочешь честный разбор звука? Тут не сторисы — тут цифры и люди, которые слушают до конца. Возвращайся.",
    "Коротко: бот про музыку и честные оценки. Давно не был — самое время зайти и влиться обратно 🎵",
)


def pick_reengagement_message() -> str:
    return random.choice(REENGAGEMENT_MESSAGES)


async def reengagement_loop(bot: Bot) -> None:
    """Периодически ищет пользователей без активности и шлёт одно напоминание за «сессию» неактивности."""
    poll = max(15, int(REENGAGEMENT_POLL_SEC))
    logger.info(
        "reengagement: цикл запущен (простой %s мин, опрос каждые %s с)",
        REENGAGEMENT_IDLE_MINUTES,
        poll,
    )
    while True:
        try:
            user_ids = await fetch_users_for_reengagement(REENGAGEMENT_IDLE_MINUTES)
            if user_ids:
                logger.info("reengagement: кандидатов на напоминание: %s", len(user_ids))
            for uid in user_ids:
                text = pick_reengagement_message()
                try:
                    await bot.send_message(uid, text)
                    await mark_reengagement_sent(uid)
                    logger.info("reengagement: отправлено user_id=%s", uid)
                except TelegramForbiddenError:
                    await mark_reengagement_sent(uid)
                    logger.info("reengagement: user_id=%s недоступен (forbidden), помечаем отправленным", uid)
                except TelegramBadRequest as e:
                    err = (e.message or str(e)).lower()
                    if "chat not found" in err or "blocked" in err or "deactivated" in err:
                        await mark_reengagement_sent(uid)
                        logger.info(
                            "reengagement: user_id=%s недоступен (%s), помечаем отправленным",
                            uid,
                            err[:80],
                        )
                    else:
                        logger.warning("reengagement TelegramBadRequest uid=%s: %s", uid, e)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning("reengagement send failed uid=%s: %s", uid, e)
            await asyncio.sleep(poll)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("reengagement loop error: %s", e)
            await asyncio.sleep(poll)
