"""Конфигурация бота."""
import os
import re

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# Username бота для ссылок t.me/{BOT_USERNAME}?start=ref_... (в Telegram: @Tracklii_Bot, название «Tracklii»)
BOT_USERNAME = (os.getenv("BOT_USERNAME", "Tracklii_Bot") or "").lstrip("@").strip()
MAX_AUDIO_SIZE_MB = 20

# ЮKassa (оплата). Добавь YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY в переменные окружения Bothost
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
# ВРЕМЕННО ОТКЛЮЧЕНО: True = оплата выключена (запуск без ЮKassa)
PAYMENTS_DISABLED = True  # Когда ЮKassa подключишь — поставь False
YOO_KASSA_ENABLED = (not PAYMENTS_DISABLED) and bool(YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY)

# ВРЕМЕННО: True = без лимитов (треков и замен сколько угодно). Когда ЮMoney будет — поставь False
UNLIMITED_MODE = True

# Монетизация
FREE_TRACKS_LIMIT = 10
PRICE_TRACK = 39
PRICE_PACK_5 = 159
PRICE_REPLACEMENT = 29
MAX_AUDIO_SIZE_BYTES = MAX_AUDIO_SIZE_MB * 1024 * 1024
ALLOWED_AUDIO_EXTENSIONS = (".mp3", ".m4a", ".ogg")
# Путь к БД. DB_PATH из env — приоритет (Volume на Basic+). Иначе /tmp в Docker, иначе music_ratings.db
if os.getenv("DB_PATH"):
    DB_PATH = os.getenv("DB_PATH")
elif os.path.exists("/app"):
    DB_PATH = "/tmp/music_ratings.db"
else:
    DB_PATH = "music_ratings.db"

# Куда отправлять жалобы (chat_id админа @bigsomanii)
REPORT_CHAT_ID = os.getenv("REPORT_CHAT_ID", "942340947")

# Напоминания неактивным: простой от N минут и дольше (>=), не «ровно в момент N»
REENGAGEMENT_ENABLED = os.getenv("REENGAGEMENT_ENABLED", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
# 360 = минимум 6 ч без активности (6 ч, 12 ч, сутки — всё ок); тест: REENGAGEMENT_IDLE_MINUTES=5
REENGAGEMENT_IDLE_MINUTES = int(os.getenv("REENGAGEMENT_IDLE_MINUTES", "360"))
# как часто проверять БД (секунды); 900 = раз в 15 минут
REENGAGEMENT_POLL_SEC = int(os.getenv("REENGAGEMENT_POLL_SEC", "900"))

# Обязательная подписка (t.me/bigsomani)
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@bigsomani")

# Проверка SoundCloud-ссылки:
# — длинные: soundcloud.com/user/track-name
# — короткие: on.soundcloud.com/XXXXX
SOUNDCLOUD_PATTERN = re.compile(
    r"^https?://"
    r"(?:(?:www\.|m\.)?soundcloud\.com/[^/]+/[^\s]+"  # soundcloud.com/artist/track
    r"|on\.soundcloud\.com/[a-zA-Z0-9_-]+)"           # on.soundcloud.com/shortId
    r"\s*$",
    re.IGNORECASE,
)


def is_soundcloud_url(text: str) -> bool:
    """Проверяет, является ли строка ссылкой на SoundCloud."""
    if not text or not isinstance(text, str):
        return False
    url = text.strip()
    return bool(SOUNDCLOUD_PATTERN.match(url))
