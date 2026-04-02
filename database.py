"""База данных для бота оценки треков."""
import aiosqlite

from config import DB_PATH, FREE_TRACKS_LIMIT, UNLIMITED_MODE


async def init_db() -> None:
    """Инициализация БД."""
    global DB_PATH
    # DB_PATH из config (env) — приоритет. Иначе fallback: /tmp, затем локально
    paths = [DB_PATH, "/tmp/music_ratings.db", "music_ratings.db"]
    paths = list(dict.fromkeys(paths))
    for path in paths:
        try:
            async with aiosqlite.connect(path) as db:
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
            DB_PATH = path
            break
        except Exception:
            continue
    else:
        raise RuntimeError("Не удалось открыть БД ни в одном из путей")
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
        if "free_replacements_used" not in user_cols:
            await db.execute("ALTER TABLE users ADD COLUMN free_replacements_used INTEGER DEFAULT 0")
            await db.commit()
        if "paid_replacements_used" not in user_cols:
            await db.execute("ALTER TABLE users ADD COLUMN paid_replacements_used INTEGER DEFAULT 0")
            await db.commit()
        if "last_activity_at" not in user_cols:
            await db.execute("ALTER TABLE users ADD COLUMN last_activity_at TEXT")
            await db.commit()
        if "king_wins" not in user_cols:
            await db.execute("ALTER TABLE users ADD COLUMN king_wins INTEGER DEFAULT 0")
            await db.commit()
        if "last_reengagement_sent_at" not in user_cols:
            await db.execute(
                "ALTER TABLE users ADD COLUMN last_reengagement_sent_at TEXT"
            )
            await db.commit()

        # Таблица забаненных пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

        # Флаг: идёт ли стрим (влияет на возможность добавлять треки в stream_queue).
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stream_meta (
                id INTEGER PRIMARY KEY,
                active INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute(
            "INSERT OR IGNORE INTO stream_meta (id, active) VALUES (1, 0)"
        )
        await db.commit()

        # Оценки треков со стримов (отдельно от обычных ratings/top).
        # Пользователь отправляет трек админу, админ оценивает или пропускает.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stream_queue (
                stream_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                file_id TEXT,
                source_url TEXT,
                status TEXT NOT NULL DEFAULT 'waiting'
                    CHECK(status IN ('waiting', 'rated', 'skipped')),
                score INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                FOREIGN KEY (sender_user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_stream_queue_sender ON stream_queue(sender_user_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_stream_queue_status ON stream_queue(status)"
        )
        await db.commit()

        # Избранное (лайки)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER NOT NULL,
                track_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, track_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (track_id) REFERENCES tracks(track_id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_favorites_track ON favorites(track_id)")
        await db.commit()

        # Покупки (оплаченные слоты)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_type TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                amount INTEGER NOT NULL,
                payment_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

        # Ожидающие оплаты платежи (для проверки статуса)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                payment_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def fetch_users_for_reengagement(idle_minutes: int) -> list[int]:
    """
    Пользователи без активности не менее idle_minutes минут, ещё без напоминания
    за текущий период неактивности (после нового захода можно снова один раз).

    Сравнение через julianday — стабильнее, чем datetime('now', ?) с модификатором.
    """
    m = float(max(1, int(idle_minutes)))
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT user_id FROM users
            WHERE last_activity_at IS NOT NULL
              AND TRIM(last_activity_at) != ''
              AND (julianday('now') - julianday(last_activity_at)) * 24 * 60 >= ?
              AND (
                last_reengagement_sent_at IS NULL
                OR TRIM(last_reengagement_sent_at) = ''
                OR julianday(last_reengagement_sent_at) < julianday(last_activity_at)
              )
              AND user_id NOT IN (SELECT user_id FROM banned_users)
            """,
            (m,),
        )
        rows = await cursor.fetchall()
        return [int(r[0]) for r in rows]


async def mark_reengagement_sent(user_id: int) -> None:
    """Фиксирует отправку напоминания (не дублировать, пока снова не будет активности)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users SET last_reengagement_sent_at = datetime('now')
            WHERE user_id = ?
            """,
            (user_id,),
        )
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


async def touch_user_activity(user_id: int, username: str = "", full_name: str = "") -> None:
    """Обновить время последней активности (любое взаимодействие с ботом)."""
    uname = (username or str(user_id))[:255]
    fname = (full_name or "User")[:255]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (user_id, username, full_name, last_activity_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET last_activity_at = datetime('now')""",
            (user_id, uname, fname),
        )
        await db.commit()


async def get_admin_live_stats() -> dict[str, int]:
    """
    Статистика для админа:
    - active_last_minute: пользователи с активностью за последнюю минуту
    - active_last_24h: за последние 24 часа (по last_activity_at)
    - total_users: всего записей в users
    - uploaders_count: уникальные пользователи с хотя бы одним (не удалённым) треком
    - tracks_total: все активные (не удалённые) треки
    - rated_tracks_count: сколько треков получили хотя бы одну оценку
    - total_track_ratings: сколько всего оценок (в таблице ratings) у активных треков
    - raters_count: уникальные пользователи, поставившие хотя бы одну оценку
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT COUNT(*) FROM users
               WHERE last_activity_at IS NOT NULL
                 AND datetime(last_activity_at) >= datetime('now', '-1 minute')""",
        )
        active = (await cursor.fetchone())[0] or 0

        cursor = await db.execute(
            """SELECT COUNT(*) FROM users
               WHERE last_activity_at IS NOT NULL
                 AND datetime(last_activity_at) >= datetime('now', '-24 hours')""",
        )
        active_24h = (await cursor.fetchone())[0] or 0

        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0] or 0

        cursor = await db.execute(
            """SELECT COUNT(DISTINCT user_id) FROM tracks
               WHERE COALESCE(deleted, 0) = 0""",
        )
        uploaders = (await cursor.fetchone())[0] or 0

        cursor = await db.execute(
            """SELECT COUNT(*) FROM tracks WHERE COALESCE(deleted, 0) = 0""",
        )
        tracks_total = (await cursor.fetchone())[0] or 0

        cursor = await db.execute("SELECT COUNT(DISTINCT user_id) FROM ratings")
        raters = (await cursor.fetchone())[0] or 0

        cursor = await db.execute(
            """SELECT COUNT(DISTINCT r.track_id)
               FROM ratings r
               JOIN tracks t ON t.track_id = r.track_id
               WHERE COALESCE(t.deleted, 0) = 0""",
        )
        rated_tracks_count = (await cursor.fetchone())[0] or 0

        cursor = await db.execute(
            """SELECT COUNT(*)
               FROM ratings r
               JOIN tracks t ON t.track_id = r.track_id
               WHERE COALESCE(t.deleted, 0) = 0""",
        )
        total_track_ratings = (await cursor.fetchone())[0] or 0

    return {
        "active_last_minute": active,
        "active_last_24h": active_24h,
        "total_users": total_users,
        "uploaders_count": uploaders,
        "tracks_total": tracks_total,
        "rated_tracks_count": rated_tracks_count,
        "total_track_ratings": total_track_ratings,
        "raters_count": raters,
    }


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


async def get_user_tracks_count(user_id: int) -> int:
    """Количество треков пользователя (не удалённых)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM tracks WHERE user_id = ? AND COALESCE(deleted, 0) = 0",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] or 0


async def get_paid_upload_slots(user_id: int) -> int:
    """Оплаченные слоты для загрузки (1 за TRACK_39, 5 за PACK_5_159)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT product_type, SUM(quantity) FROM purchases
               WHERE user_id = ? AND product_type IN ('TRACK_39', 'PACK_5_159')
               GROUP BY product_type""",
            (user_id,),
        )
        slots = 0
        async for row in cursor:
            if row[0] == "TRACK_39":
                slots += row[1] or 0
            elif row[0] == "PACK_5_159":
                slots += (row[1] or 0) * 5
        return slots


async def can_user_upload(user_id: int) -> tuple[bool, int, str]:
    """
    Может ли пользователь загрузить трек.
    Возвращает (can_upload, ratings_needed, block_reason).
    10 треков бесплатно, далее — оплата. После каждых 3 загрузок нужно 5 оценок.
    """
    tracks_count = await get_user_tracks_count(user_id)
    paid_slots = await get_paid_upload_slots(user_id)
    max_allowed = FREE_TRACKS_LIMIT + paid_slots

    # ВРЕМЕННО ОТКЛЮЧЕНО: при UNLIMITED_MODE не блокируем по лимиту треков
    if not UNLIMITED_MODE and tracks_count >= max_allowed:
        return False, 0, "limit"  # Лимит треков, нужна оплата

    # ВРЕМЕННО ОТКЛЮЧЕНО: требование 5 оценок после каждых 3 загрузок (раскомментировать когда понадобится)
    return True, 0, ""
    # async with aiosqlite.connect(DB_PATH) as db:
    #     cursor = await db.execute(
    #         """SELECT last_upload_ratings_count, tracks_since_checkpoint
    #            FROM users WHERE user_id = ?""",
    #         (user_id,),
    #     )
    #     row = await cursor.fetchone()
    #     ratings_at_checkpoint = (row[0] or 0) if row else 0
    #     tracks_since = (row[1] or 0) if row else 0
    #
    # current = await get_ratings_given_count(user_id)
    # diff = current - ratings_at_checkpoint
    #
    # if tracks_since in (0, 1, 2):
    #     return True, 0, ""
    # if tracks_since == 3:
    #     needed = max(0, 5 - diff)
    #     return (needed == 0, needed, "" if needed == 0 else "ratings")
    # return False, 5, "ratings"


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


FREE_REPLACEMENTS_LIMIT = 3


async def get_replacements_available(user_id: int) -> int:
    """Сколько замен доступно: 3 бесплатных + оплаченные - использованные."""
    # ВРЕМЕННО ОТКЛЮЧЕНО: без лимитов при UNLIMITED_MODE
    if UNLIMITED_MODE:
        return 999
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT COALESCE(free_replacements_used, 0), COALESCE(paid_replacements_used, 0)
               FROM users WHERE user_id = ?""",
            (user_id,),
        )
        row = await cursor.fetchone()
        free_used = row[0] if row else 0
        paid_used = row[1] if row else 0

        cursor = await db.execute(
            """SELECT COALESCE(SUM(quantity), 0) FROM purchases
               WHERE user_id = ? AND product_type = 'REPLACEMENT_29'""",
            (user_id,),
        )
        paid_total = (await cursor.fetchone())[0] or 0

    free_left = max(0, FREE_REPLACEMENTS_LIMIT - free_used)
    paid_left = max(0, paid_total - paid_used)
    return free_left + paid_left


async def get_free_replacements_left(user_id: int) -> int:
    """Сколько замен доступно (бесплатные + оплаченные)."""
    return await get_replacements_available(user_id)


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
    3 бесплатные замены на аккаунт. Возвращает (success, message).
    """
    fid = file_id if file_id else ""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM tracks WHERE track_id = ? AND COALESCE(deleted, 0) = 0",
            (track_id,),
        )
        row = await cursor.fetchone()
        if not row or row[0] != user_id:
            return False, "Трек не найден."

        # ВРЕМЕННО ОТКЛЮЧЕНО: проверка лимита замен при UNLIMITED_MODE
        if not UNLIMITED_MODE:
            available = await get_replacements_available(user_id)
            if available <= 0:
                return False, (
                    f"Лимит замен исчерпан. Дополнительная замена — 29₽ "
                    "(оплата скоро будет доступна)."
                )

        free_used = 0
        paid_used = 0
        cursor = await db.execute(
            """SELECT COALESCE(free_replacements_used, 0), COALESCE(paid_replacements_used, 0)
               FROM users WHERE user_id = ?""",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            free_used, paid_used = row[0], row[1]

        # ВРЕМЕННО ОТКЛЮЧЕНО: не списывать замены при UNLIMITED_MODE
        if not UNLIMITED_MODE and free_used < FREE_REPLACEMENTS_LIMIT:
            await db.execute(
                "UPDATE users SET free_replacements_used = COALESCE(free_replacements_used, 0) + 1 WHERE user_id = ?",
                (user_id,),
            )
        elif not UNLIMITED_MODE:
            await db.execute(
                "UPDATE users SET paid_replacements_used = COALESCE(paid_replacements_used, 0) + 1 WHERE user_id = ?",
                (user_id,),
            )

        await db.execute(
            """UPDATE tracks SET file_id = ?, source_url = ?, title = ?, file_name = ?
               WHERE track_id = ?""",
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


async def add_purchase(
    user_id: int,
    product_type: str,
    amount: int,
    payment_id: str,
    quantity: int = 1,
) -> None:
    """Записать успешную покупку."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO purchases (user_id, product_type, quantity, amount, payment_id)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, product_type, quantity, amount, payment_id),
        )
        await db.commit()


async def add_pending_payment(
    payment_id: str,
    user_id: int,
    product_type: str,
    amount: int,
) -> None:
    """Добавить ожидающий платёж."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO pending_payments (payment_id, user_id, product_type, amount)
               VALUES (?, ?, ?, ?)""",
            (payment_id, user_id, product_type, amount),
        )
        await db.commit()


async def get_pending_payment(payment_id: str) -> dict | None:
    """Получить ожидающий платёж."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM pending_payments WHERE payment_id = ?",
            (payment_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def remove_pending_payment(payment_id: str) -> None:
    """Удалить ожидающий платёж после обработки."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM pending_payments WHERE payment_id = ?", (payment_id,))
        await db.commit()


async def get_all_pending_payments() -> list[dict]:
    """Все ожидающие платежи для проверки статуса."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM pending_payments")
        return [dict(r) for r in await cursor.fetchall()]


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


async def unban_user(user_id: int) -> bool:
    """Разбанить исполнителя. Возвращает True, если запись была удалена."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM banned_users WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
        return bool(cursor.rowcount)


async def get_user_id_by_username(username: str) -> int | None:
    """Найти user_id по Telegram username (без @)."""
    username = (username or "").strip().lstrip("@")
    if not username:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE username = ? LIMIT 1",
            (username,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else None


async def is_user_banned(user_id: int) -> bool:
    """Проверяет, забанен ли пользователь."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM banned_users WHERE user_id = ? LIMIT 1",
            (user_id,),
        )
        return (await cursor.fetchone()) is not None


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


async def delete_track_by_user(track_id: int, user_id: int) -> tuple[bool, str]:
    """
    Удаляет трек исполнителем (помечает deleted).
    Проверяет принадлежность трека пользователю. Без предупреждения.
    Возвращает (success, message).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, title FROM tracks WHERE track_id = ? AND COALESCE(deleted, 0) = 0",
            (track_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return False, "Трек не найден."
        if row[0] != user_id:
            return False, "Это не твой трек."
        await db.execute(
            "UPDATE tracks SET deleted = 1 WHERE track_id = ?",
            (track_id,),
        )
        await db.commit()
        return True, row[1] or "Трек"


async def toggle_favorite(user_id: int, track_id: int) -> tuple[bool, bool]:
    """
    Переключает трек в избранном. Возвращает (success, now_in_favorites).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND track_id = ?",
            (user_id, track_id),
        )
        exists = await cursor.fetchone()
        if exists:
            await db.execute(
                "DELETE FROM favorites WHERE user_id = ? AND track_id = ?",
                (user_id, track_id),
            )
            await db.commit()
            return True, False
        else:
            await db.execute(
                "INSERT OR IGNORE INTO favorites (user_id, track_id) VALUES (?, ?)",
                (user_id, track_id),
            )
            await db.commit()
            return True, True


async def is_track_in_favorites(user_id: int, track_id: int) -> bool:
    """Проверяет, есть ли трек в избранном у пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND track_id = ?",
            (user_id, track_id),
        )
        return await cursor.fetchone() is not None


async def get_track_likes_count(track_id: int) -> int:
    """Количество лайков (добавлений в избранное) трека."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM favorites WHERE track_id = ?",
            (track_id,),
        )
        return (await cursor.fetchone())[0] or 0


async def get_user_favorites(user_id: int) -> list[dict]:
    """Треки в избранном пользователя с рейтингами и лайками."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT t.track_id, t.title, t.file_id, t.source_url, t.user_id,
                      COALESCE(NULLIF(u.display_name, ''), u.username) as username,
                      COALESCE(r.avg_score, 0) as avg_score,
                      COALESCE(r.rating_count, 0) as rating_count,
                      (SELECT COUNT(*) FROM favorites WHERE track_id = t.track_id) as likes_count
               FROM favorites f
               JOIN tracks t ON f.track_id = t.track_id AND COALESCE(t.deleted, 0) = 0
               JOIN users u ON t.user_id = u.user_id
               LEFT JOIN (
                   SELECT track_id, AVG(score) as avg_score, COUNT(*) as rating_count
                   FROM ratings GROUP BY track_id
               ) r ON t.track_id = r.track_id
               WHERE f.user_id = ?
               ORDER BY f.created_at DESC""",
            (user_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]


async def clear_all_tracks() -> int:
    """
    Удаляет все треки и оценки. Для очистки тестовых данных.
    Возвращает количество удалённых треков.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM tracks")
        count = (await cursor.fetchone())[0]
        await db.execute("DELETE FROM ratings")
        await db.execute("DELETE FROM tracks")
        await db.execute(
            "UPDATE users SET tracks_since_checkpoint = 0, last_upload_ratings_count = 0"
        )
        await db.commit()
        return count


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


async def add_stream_submission(
    sender_user_id: int,
    title: str,
    file_id: str | None,
    source_url: str | None,
) -> int:
    """Добавляет трек в очередь стрим-оценки (оценки не влияют на обычные рейтинги)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO stream_queue (sender_user_id, title, file_id, source_url, status, score)
               VALUES (?, ?, ?, ?, 'waiting', NULL)""",
            (sender_user_id, title, file_id, source_url),
        )
        await db.commit()
        return cursor.lastrowid


async def get_user_stream_submissions_count(user_id: int) -> int:
    """Сколько треков этого пользователя есть в очереди стрима."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM stream_queue WHERE sender_user_id = ?",
            (user_id,),
        )
        return (await cursor.fetchone())[0] or 0


async def get_user_stream_submissions(
    user_id: int,
    limit: int,
    offset: int,
) -> list[dict]:
    """Список треков пользователя из очереди стрима."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT stream_item_id, title, status, score, created_at
               FROM stream_queue
               WHERE sender_user_id = ?
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_stream_submission(stream_item_id: int) -> dict | None:
    """Получить одну стрим-сдачу (для админского оценивания)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT stream_item_id, sender_user_id, title, file_id, source_url, status, score
               FROM stream_queue
               WHERE stream_item_id = ?""",
            (stream_item_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def review_stream_submission_admin(
    stream_item_id: int,
    score: int | None,
) -> tuple[bool, str]:
    """Оценить/пропустить трек со стрима (всё хранится в stream_queue)."""
    if score is not None and not (0 <= score <= 10):
        return False, "Некорректная оценка."

    status = "skipped" if score is None else "rated"

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """UPDATE stream_queue
               SET status = ?, score = ?, reviewed_at = datetime('now')
               WHERE stream_item_id = ? AND status = 'waiting'""",
            (status, score, stream_item_id),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return False, "Эта запись уже оценена или не найдена."
        return True, "Готово."


async def is_stream_active() -> bool:
    """Стрим запущен (активен) или нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT active FROM stream_meta WHERE id = 1"
        )
        row = await cursor.fetchone()
        return bool(row[0]) if row else False


async def start_stream() -> None:
    """Включить режим стрима (разрешить отправку треков на оценку)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE stream_meta SET active = 1, updated_at = datetime('now') WHERE id = 1"
        )
        await db.commit()


async def stop_stream_and_skip_waiting() -> int:
    """
    Выключить режим стрима и закрыть очередь:
    все позиции со статусом waiting переводим в skipped.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE stream_meta SET active = 0, updated_at = datetime('now') WHERE id = 1"
        )
        cursor = await db.execute(
            """UPDATE stream_queue
               SET status = 'skipped',
                   score = NULL,
                   reviewed_at = datetime('now')
               WHERE status = 'waiting'"""
        )
        skipped_count = cursor.rowcount if cursor.rowcount is not None else 0
        await db.commit()
        return int(skipped_count)


async def get_user_tracks(user_id: int) -> list[dict]:
    """Возвращает список треков пользователя с рейтингами и лайками."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT t.track_id, t.title, t.genre,
                      COALESCE(r.avg_score, 0) as avg_score,
                      COALESCE(r.rating_count, 0) as rating_count,
                      COALESCE(t.replaced_count, 0) as replaced_count,
                      (SELECT COUNT(*) FROM favorites WHERE track_id = t.track_id) as likes_count
               FROM tracks t
               LEFT JOIN (
                   SELECT track_id, AVG(score) as avg_score, COUNT(*) as rating_count
                   FROM ratings GROUP BY track_id
               ) r ON t.track_id = r.track_id
               WHERE t.user_id = ? AND COALESCE(t.deleted, 0) = 0
               ORDER BY t.created_at DESC""",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [
            {**dict(r), "likes_count": r["likes_count"] or 0}
            for r in rows
        ]


async def get_user_tracks_replaceable(user_id: int) -> list[dict]:
    """Все треки пользователя (для замены — лимит 3 бесплатно на аккаунт)."""
    return await get_user_tracks(user_id)


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
        cursor = await db.execute(
            "SELECT COALESCE(king_wins, 0) FROM users WHERE user_id = ?",
            (user_id,),
        )
        wins_row = await cursor.fetchone()
        return {
            "tracks_count": row["tracks_count"] or 0,
            "total_ratings": row["total_ratings"] or 0,
            "artist_avg": round(float(row["artist_avg"] or 0), 1),
            "king_wins": (wins_row[0] if wins_row else 0) or 0,
        }


async def get_king_tournament_tracks(user_id: int, limit: int = 10) -> list[dict]:
    """Случайные треки для режима «Царь SoundCloud'а»."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT t.track_id, t.user_id, t.title, t.file_id, t.source_url,
                      COALESCE(NULLIF(u.display_name, ''), u.username) as username
               FROM tracks t
               JOIN users u ON t.user_id = u.user_id
               WHERE COALESCE(t.deleted, 0) = 0
                 AND t.user_id != ?
                 AND t.user_id NOT IN (SELECT user_id FROM banned_users)
               ORDER BY RANDOM()
               LIMIT ?""",
            (user_id, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]


async def add_king_win(user_id: int) -> None:
    """+1 победа в режиме «Царь SoundCloud'а» для исполнителя."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET king_wins = COALESCE(king_wins, 0) + 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def get_top_tracks(limit: int = 10) -> list[dict]:
    """ТОП треков по среднему баллу. Треки с >= 5 оценками. Лайки не влияют на рейтинг."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT t.track_id, t.title, t.user_id,
                      COALESCE(NULLIF(u.display_name, ''), u.username) as username,
                      r.avg_score, r.rating_count,
                      (SELECT COUNT(*) FROM favorites WHERE track_id = t.track_id) as likes_count
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
        rows = await cursor.fetchall()
        return [
            {
                **dict(r),
                "likes_count": r["likes_count"] or 0,
            }
            for r in rows
        ]


async def get_top_artists(limit: int = 10) -> list[dict]:
    """
    ТОП исполнителей по среднему баллу всех треков.
    Исполнители с >= 10 оценками (суммарно по всем трекам). Лайки не влияют на средний балл.
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
        result = []
        for r in rows:
            cur2 = await db.execute(
                """SELECT COUNT(*) FROM favorites f
                   JOIN tracks t ON f.track_id = t.track_id AND t.user_id = ? AND COALESCE(t.deleted, 0) = 0""",
                (r["user_id"],)
            )
            total_likes = (await cur2.fetchone())[0] or 0
            result.append({
                "user_id": r["user_id"],
                "username": r["username"],
                "total_ratings": r["total_ratings"],
                "artist_avg": round(float(r["artist_avg"]), 1),
                "total_likes": total_likes,
            })
        return result


async def get_artist_rank(user_id: int) -> tuple[int | None, int]:
    """
    Место исполнителя в общем рейтинге (как в ТОП исполнителей, не только топ-10).
    Возвращает (место с 1, число исполнителей в рейтинге) или (None, N), если нет оценённых треков.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT u.user_id,
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
               ORDER BY artist_avg DESC, total_ratings DESC""",
        )
        rows = await cursor.fetchall()
    ordered_ids = [r[0] for r in rows]
    total = len(ordered_ids)
    try:
        pos = ordered_ids.index(user_id) + 1
    except ValueError:
        return None, total
    return pos, total
