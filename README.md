# 🎵 Бот оценки музыкальных треков

Telegram-бот на Python (aiogram 3.x) для оценки музыкальных треков — аналог Bibinto.

## Функции

- **Регистрация и профиль** — username, список треков, рейтинг исполнителя
- **Загрузка треков** — аудио mp3/m4a/ogg до 20 МБ или ссылка SoundCloud
- **Голосование** — случайный трек, оценка 1–10, кнопка «Пожаловаться»
- **Рейтинги** — ТОП-10 треков и ТОП-10 исполнителей

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

1. Создай бота через [@BotFather](https://t.me/BotFather)
2. Установи переменные окружения:
   ```bash
   set BOT_TOKEN=your_bot_token
   set REPORT_CHAT_ID=your_telegram_user_id
   ```
   `REPORT_CHAT_ID` — твой ID для получения жалоб (узнать: [@userinfobot](https://t.me/userinfobot)). Чтобы банить: напиши боту `/ban 12345` (id исполнителя из жалобы).
3. Запусти:
   ```bash
   python main.py
   ```

## Структура

- `main.py` — точка входа
- `config.py` — настройки
- `database.py` — работа с SQLite
- `keyboards.py` — inline-клавиатуры
- `handlers/` — обработчики команд и callback'ов

Аудио хранится по `file_id` в Telegram (без загрузки на сервер).
