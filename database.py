"""База данных для бота оценки треков."""
import aiosqlite
from config import DB_PATH


async def init_db() -> None:
    """Инициализация БД."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                track_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                title TEXT NOT NULL,
                genre TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                score INTEGER NOT NULL CHECK(score >= 1 AND score <= 10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(track_id, user_id),
                FOREIGN KEY (track_id) REFERENCES tracks(track_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_ratings_track ON ratings(track_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_ratings_user ON ratings(user_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracks_user ON tracks(user_id)
        """)
        await db.commit()
    await _migrate_db()


async def _migrate_db() -> None:
    """Миграции: добавление новых колонок."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]
        migrations = [
            ("display_name", "ALTER TABLE users ADD COLUMN display_name TEXT"),
            ("nickname_changes_count", "ALTER TABLE users ADD COLUMN nickname_changes_count INTEGER DEFAULT 0"),
            ("last_upload_ratings_count", "ALTER TABLE users ADD COLUMN last_upload_ratings_count INTEGER DEFAULT 0"),
            ("tracks_since_checkpoint", "ALTER TABLE users ADD COLUMN tracks_since_checkpoint INTEGER DEFAULT 0"),
        ]
        for col, sql in migrations:
            if col not in columns:
                await db.execute(sql)
        await db.commit()

        cursor = await db.execute("PRAGMA table_info(tracks)")
        track_cols = [row[1] for row in await cursor.fetchall()]
        if "source_url" not in track_cols:
            await db.execute("ALTER TABLE tracks ADD COLUMN source_url TEXT")
            await db.commit()
        if "deleted" not in track_cols:
            await db.execute("ALTER TABLE tracks ADD COLUMN deleted INTEGER DEFAULT 0")
            await db.commit()
        if "file_name" not in track_cols:
            await db.execute("ALTER TABLE tracks ADD COLUMN file_name TEXT")
            await db.commit()
        if "replaced_count" not in track_cols:
            await db.execute("ALTER TABLE tracks ADD COLUMN replaced_count INTEGER DEFAULT 0")
            await db.commit()

        cursor = await db.execute("PRAGMA table_info(users)")
        user_cols = [row[1] for row in await cursor.fetchall()]
        if "warnings_count" not in user_cols:
            await db.execute("ALTER TABLE users ADD COLUMN warnings_count INTEGER DEFAULT 0")
            await db.commit()

        # Таблица забаненных пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def get_or_create_user(user_id: int, username: str, full_name: str) -> bool:
    """
    Регистрирует пользователя или возвращает существующего.
    Возвращает True если пользователь новый.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            await db.execute(
                "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
                (username, full_name, user_id)
            )
            await db.commit()
            return False
        await db.execute(
            "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username or str(user_id), full_name or "User")
        )
        await db.commit()
        return True


async def get_user_display_info(user_id: int) -> dict:
    """display_name, nickname_changes_count, смен осталось."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT display_name, nickname_changes_count, username
               FROM users WHERE user_id = ?""",
            (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return {"display_name": None, "changes_left": 3, "username": str(user_id)}
        display_name, count, username = row
        changes_left = max(0, 3 - (count or 0))
        return {
            "display_name": display_name,
            "changes_left": changes_left,
            "username": username or str(user_id),
        }


async def update_display_name(user_id: int, new_name: str) -> tuple[bool, str]:
    """Меняет ник. Возвращает (success, message). Максимум 3 смены."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT nickname_changes_count FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False, "Пользователь не найден."
        count = row[0] or 0
        if count >= 3:
            return False, "Лимит смен ника исчерпан (макс. 3 раза)."
        new_name = (new_name or "").strip()
        if not new_name:
            return False, "Введи корректный ник."
        if len(new_name) > 50:
            return False, "Ник не более 50 символов."
        await db.execute(
            """UPDATE users SET display_name = ?, nickname_changes_count = ?
               WHERE user_id = ?""",
            (new_name, count + 1, user_id)
        )
        await db.commit()
        return True, f"Ник изменён на «{new_name}»"


async def get_ratings_given_count(user_id: int) -> int:
    """Количество оценок, выставленных пользователем чужим трекам."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT COUNT(*) FROM ratings r
               JOIN tracks t ON r.track_id = t.track_id
               WHERE r.user_id = ? AND t.user_id != ?""",
            (user_id, user_id)
        )
        row = await cursor.fetchone()
        return row[0] or 0


async def can_user_upload(user_id: int) -> tuple[bool, int]:
    """
    Может ли пользователь загрузить трек.
    Возвращает (can_upload, ratings_needed).
    После каждых 3 загруженных треков нужно оценить 5 чужих.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT last_upload_ratings_count, tracks_since_checkpoint
               FROM users WHERE user_id = ?""",
            (user_id,)
        )
        row = await cursor.fetchone()
        ratings_at_checkpoint = (row[0] or 0) if row else 0
        tracks_since = (row[1] or 0) if row else 0
    current = await get_ratings_given_count(user_id)
    diff = current - ratings_at_checkpoint

    # Первые 3 трека — без оценок. После каждых 3 — нужно 5 оценок.
    if tracks_since in (0, 1, 2):
        return (True, 0)
    if tracks_since == 3:
        needed = max(0, 5 - diff)
        return (needed == 0, needed)
    return (False, 5)


async def update_after_upload(user_id: int) -> None:
    """
    Обновляет счётчики после загрузки трека.
    После каждых 3 треков нужны 5 новых оценок.
    """
    current = await get_ratings_given_count(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT last_upload_ratings_count, tracks_since_checkpoint
               FROM users WHERE user_id = ?""",
            (user_id,)
        )
        row = await cursor.fetchone()
        ratings_at_checkpoint = (row[0] or 0) if row else 0
        tracks_since = (row[1] or 0) if row else 0

        if tracks_since == 2:
            ratings_at_checkpoint = current
        elif tracks_since == 3:
            tracks_since = 0
            ratings_at_checkpoint = current
        tracks_since += 1

        await db.execute(
            """UPDATE users SET last_upload_ratings_count = ?,
               tracks_since_checkpoint = ? WHERE user_id = ?""",
            (ratings_at_checkpoint, tracks_since, user_id)
        )
        await db.commit()


def _norm(s: str) -> str:
    """Нормализация для сравнения: нижний регистр, trim."""
    return (s or "").strip().lower()


def _norm_url(url: str | None) -> str | None:
    """Нормализация ссылки: lower, trim, без query-параметров."""
    if not url or not (s := (url or "").strip().lower()):
        return None
    base = s.split("?")[0].rstrip("/")
    return base if base else None


async def find_duplicate_track(
    user_id: int,
    title: str,
    file_name: str | None = None,
    source_url: str | None = None,
    exclude_track_id: int | None = None,
    replaceable_only: bool = False,
) -> dict | None:
    """
    Ищет дубликат у пользователя: по названию файла, названию трека или ссылке (SoundCloud).
    exclude_track_id — не считать дубликатом этот трек (при замене).
    replaceable_only — только треки с replaced_count=0 (можно заменить).
    Возвращает track dict или None.
    """
    norm_title = _norm(title)
    norm_fn = _norm(file_name) if file_name else None
    norm_url = _norm_url(source_url) if source_url else None
    if not norm_title and not norm_fn and not norm_url:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Собираем условия: file_name, title, source_url
        conditions = []
        params = [user_id]
        if norm_fn:
            conditions.append("(file_name IS NOT NULL AND LOWER(TRIM(file_name)) = ?)")
            params.append(norm_fn)
        if norm_title:
            conditions.append("LOWER(TRIM(title)) = ?")
            params.append(norm_title)
        if norm_url:
            # Сравниваем базовую ссылку без query-параметров и trailing slash
            conditions.append(
                "(source_url IS NOT NULL AND RTRIM(LOWER(TRIM(SUBSTR(source_url || '?', 1, INSTR(source_url || '?', '?') - 1))), '/') = ?)"
            )
            params.append(norm_url)
        if not conditions:
            return None
        where_clause = " OR ".join(conditions)
        sql = f"""SELECT track_id, title, file_name, COALESCE(replaced_count, 0) as replaced_count FROM tracks
                WHERE user_id = ? AND COALESCE(deleted, 0) = 0
                AND ({where_clause})"""
        if exclude_track_id is not None:
            sql += " AND track_id != ?"
            params = params + [exclude_track_id]
        if replaceable_only:
            sql += " AND COALESCE(replaced_count, 0) = 0"
        sql += " ORDER BY track_id ASC LIMIT 1"
        cursor = await db.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None


async def replace_track_and_reset_ratings(
    track_id: int,
    user_id: int,
    file_id: str | None,
    source_url: str | None,
    title: str,
    file_name: str | None = None,
) -> tuple[bool, str]:
    """
    Заменяет файл трека, обнуляет оценки.
    Возвращает (success, message). Один трек можно заменить только один раз.
    """
    fid = file_id if file_id else ""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT user_id, COALESCE(replaced_count, 0) FROM tracks
               WHERE track_id = ? AND COALESCE(deleted, 0) = 0""",
            (track_id,),
        )
        row = await cursor.fetchone()
        if not row or row[0] != user_id:
            return False, "Трек не найден."
        if row[1] >= 1:
            return False, "Этот трек уже был заменён. Заменить можно только один раз."
        await db.execute(
            """UPDATE tracks SET file_id = ?, source_url = ?, title = ?, file_name = ?,
               replaced_count = 1 WHERE track_id = ?""",
            (fid, source_url or None, title, file_name or None, track_id),
        )
        await db.execute("DELETE FROM ratings WHERE track_id = ?", (track_id,))
        await db.commit()
        return True, ""


async def add_track(
    user_id: int,
    title: str,
    genre: str = "",
    file_id: str | None = None,
    source_url: str | None = None,
    file_name: str | None = None,
) -> int:
    """Добавляет трек. Либо file_id (Telegram), либо source_url (SoundCloud)."""
    fid = file_id if file_id else ""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO tracks (user_id, file_id, title, genre, source_url, file_name)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, fid, title, genre, source_url or None, file_name or None),
        )
        await db.commit()
        return cursor.lastrowid


async def get_track(track_id: int) -> dict | None:
    """Получает трек по ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT t.*, COALESCE(NULLIF(u.display_name, ''), u.username) as username
               FROM tracks t
               JOIN users u ON t.user_id = u.user_id
               WHERE t.track_id = ?""",
            (track_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_random_track_for_voting(user_id: int) -> dict | None:
    """
    Возвращает случайный трек из пула. Исключает свои треки и треки забаненных.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT t.*, COALESCE(NULLIF(u.display_name, ''), u.username) as username
               FROM tracks t
               JOIN users u ON t.user_id = u.user_id
               WHERE t.user_id != ?
                 AND COALESCE(t.deleted, 0) = 0
                 AND t.user_id NOT IN (SELECT user_id FROM banned_users)
                 AND t.track_id NOT IN (
                     SELECT track_id FROM ratings WHERE user_id = ?
                 )
               ORDER BY RANDOM()
               LIMIT 1""",
            (user_id, user_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def ban_user(user_id: int) -> None:
    """Забанить исполнителя."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)",
            (user_id,)
        )
        await db.commit()


async def delete_track_and_warn_artist(track_id: int) -> tuple[bool, int | None, int]:
    """
    Удаляет трек (помечает deleted), добавляет предупреждение исполнителю.
    Возвращает (success, artist_user_id, new_warnings_count).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM tracks WHERE track_id = ?", (track_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False, None, 0
        artist_id = row[0]

        await db.execute(
            "UPDATE tracks SET deleted = 1 WHERE track_id = ?",
            (track_id,)
        )
        await db.execute(
            "UPDATE users SET warnings_count = COALESCE(warnings_count, 0) + 1 WHERE user_id = ?",
            (artist_id,)
        )
        cursor = await db.execute(
            "SELECT COALESCE(warnings_count, 0) FROM users WHERE user_id = ?",
            (artist_id,)
        )
        w = (await cursor.fetchone())[0]
        await db.commit()
        return True, artist_id, w


async def get_user_warnings(user_id: int) -> int:
    """Количество предупреждений пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(warnings_count, 0) FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def add_rating(track_id: int, user_id: int, score: int) -> tuple[bool, str]:
    """
    Добавляет оценку. Возвращает (success, message).
    Проверяет: нельзя голосовать за свой трек, один голос на трек.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверка: трек существует и не удалён
        cursor = await db.execute(
            "SELECT user_id FROM tracks WHERE track_id = ? AND COALESCE(deleted, 0) = 0",
            (track_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False, "Трек не найден или удалён."
        if row[0] == user_id:
            return False, "Нельзя оценивать свой собственный трек."

        # Проверка: уже оценивал
        cursor = await db.execute(
            "SELECT rating_id FROM ratings WHERE track_id = ? AND user_id = ?",
            (track_id, user_id)
        )
        if await cursor.fetchone():
            return False, "Вы уже оценивали этот трек."

        await db.execute(
            "INSERT INTO ratings (track_id, user_id, score) VALUES (?, ?, ?)",
            (track_id, user_id, score)
        )
        await db.commit()
        return True, "Оценка добавлена."


async def get_track_rating(track_id: int) -> tuple[float, int]:
    """Возвращает (средний балл, количество оценок) для трека."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT AVG(score), COUNT(*) FROM ratings WHERE track_id = ?",
            (track_id,)
        )
        row = await cursor.fetchone()
        avg, count = row[0] or 0, row[1] or 0
        return round(float(avg), 1) if count else 0.0, count


async def get_user_tracks(user_id: int) -> list[dict]:
    """Возвращает список треков пользователя с рейтингами."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT t.track_id, t.title, t.genre,
                      COALESCE(r.avg_score, 0) as avg_score,
                      COALESCE(r.rating_count, 0) as rating_count,
                      COALESCE(t.replaced_count, 0) as replaced_count
               FROM tracks t
               LEFT JOIN (
                   SELECT track_id, AVG(score) as avg_score, COUNT(*) as rating_count
                   FROM ratings GROUP BY track_id
               ) r ON t.track_id = r.track_id
               WHERE t.user_id = ? AND COALESCE(t.deleted, 0) = 0
               ORDER BY t.created_at DESC""",
            (user_id,)
        )
        return [dict(r) for r in await cursor.fetchall()]


async def get_user_tracks_replaceable(user_id: int) -> list[dict]:
    """Треки пользователя, которые ещё можно заменить (никогда не заменялись)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT t.track_id, t.title, t.genre,
                      COALESCE(r.avg_score, 0) as avg_score,
                      COALESCE(r.rating_count, 0) as rating_count
               FROM tracks t
               LEFT JOIN (
                   SELECT track_id, AVG(score) as avg_score, COUNT(*) as rating_count
                   FROM ratings GROUP BY track_id
               ) r ON t.track_id = r.track_id
               WHERE t.user_id = ? AND COALESCE(t.deleted, 0) = 0
               AND COALESCE(t.replaced_count, 0) = 0
               ORDER BY t.created_at DESC""",
            (user_id,)
        )
        return [dict(r) for r in await cursor.fetchall()]


async def get_user_stats(user_id: int) -> dict:
    """Статистика исполнителя: суммарные оценки, средний балл по всем трекам."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT COUNT(DISTINCT t.track_id) as tracks_count,
                      COALESCE(SUM(r.cnt), 0) as total_ratings,
                      COALESCE(AVG(r.avg), 0) as artist_avg
               FROM tracks t
               LEFT JOIN (
                   SELECT track_id, COUNT(*) as cnt, AVG(score) as avg
                   FROM ratings GROUP BY track_id
               ) r ON t.track_id = r.track_id
               WHERE t.user_id = ? AND COALESCE(t.deleted, 0) = 0""",
            (user_id,)
        )
        row = await cursor.fetchone()
        return {
            "tracks_count": row["tracks_count"] or 0,
            "total_ratings": row["total_ratings"] or 0,
            "artist_avg": round(float(row["artist_avg"] or 0), 1),
        }


async def get_top_tracks(limit: int = 10) -> list[dict]:
    """ТОП треков по среднему баллу. Только треки с >= 5 оценок."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT t.track_id, t.title,
                      COALESCE(NULLIF(u.display_name, ''), u.username) as username,
                      r.avg_score, r.rating_count
               FROM tracks t
               JOIN users u ON t.user_id = u.user_id
               JOIN (
                   SELECT track_id, AVG(score) as avg_score, COUNT(*) as rating_count
                   FROM ratings GROUP BY track_id HAVING COUNT(*) >= 5
               ) r ON t.track_id = r.track_id
               WHERE COALESCE(t.deleted, 0) = 0
               ORDER BY r.avg_score DESC, r.rating_count DESC
               LIMIT ?""",
            (limit,)
        )
        return [dict(r) for r in await cursor.fetchall()]


async def get_top_artists(limit: int = 10) -> list[dict]:
    """
    ТОП исполнителей по среднему баллу всех треков.
    Только те, у кого суммарно >= 10 оценок.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT u.user_id, COALESCE(NULLIF(u.display_name, ''), u.username) as username,
                      SUM(r.rating_count) as total_ratings,
                      AVG(r.avg_score) as artist_avg
               FROM users u
               JOIN tracks t ON u.user_id = t.user_id AND COALESCE(t.deleted, 0) = 0
               JOIN (
                   SELECT track_id, AVG(score) as avg_score, COUNT(*) as rating_count
                   FROM ratings GROUP BY track_id
               ) r ON t.track_id = r.track_id
               GROUP BY u.user_id
               HAVING SUM(r.rating_count) >= 10
               ORDER BY artist_avg DESC, total_ratings DESC
               LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [
            {
                "user_id": r["user_id"],
                "username": r["username"],
                "total_ratings": r["total_ratings"],
                "artist_avg": round(float(r["artist_avg"]), 1),
            }
            for r in rows
        ]
