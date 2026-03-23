"""Конфигурация бота."""
import os
import re

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MAX_AUDIO_SIZE_MB = 20
MAX_AUDIO_SIZE_BYTES = MAX_AUDIO_SIZE_MB * 1024 * 1024
ALLOWED_AUDIO_EXTENSIONS = (".mp3", ".m4a", ".ogg")
DB_PATH = "music_ratings.db"

# Куда отправлять жалобы (chat_id админа @bigsomanii)
REPORT_CHAT_ID = os.getenv("REPORT_CHAT_ID", "942340947")

# Проверка SoundCloud-ссылки (soundcloud.com/user/track-name)
SOUNDCLOUD_PATTERN = re.compile(
    r"^https?://(www\.|m\.)?soundcloud\.com/[^/]+/[^/\s]+",
    re.IGNORECASE,
)


def is_soundcloud_url(text: str) -> bool:
    """Проверяет, является ли строка ссылкой на SoundCloud."""
    if not text or not isinstance(text, str):
        return False
    url = text.strip()
    return bool(SOUNDCLOUD_PATTERN.match(url))
