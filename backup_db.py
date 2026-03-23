"""Скрипт для резервного копирования базы данных.
Запуск: python backup_db.py
Создаёт копию music_ratings.db в папке backups/ с датой в имени."""
import os
import shutil
from datetime import datetime

from config import DB_PATH

BACKUP_DIR = "backups"


def backup() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    backup_path = os.path.join(BACKUP_DIR, f"music_ratings_{date_str}.db")
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


if __name__ == "__main__":
    path = backup()
    print(f"Бэкап сохранён: {path}")
