import aiosqlite
from src.config import DB_PATH


async def upsert_user(user_id: int, username: str | None, first_name: str | None, language: str = "en") -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, first_name, language)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name,
                updated_at = datetime('now')
            """,
            (user_id, username, first_name, language),
        )
        await db.commit()


async def update_location_coords(user_id: int, lat: float, lng: float, timezone: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET lat = ?, lng = ?, city = NULL, country = NULL, timezone = ?, updated_at = datetime('now')
            WHERE user_id = ?
            """,
            (lat, lng, timezone, user_id),
        )
        await db.commit()


async def update_location_city(user_id: int, city: str, country: str, timezone: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET lat = NULL, lng = NULL, city = ?, country = ?, timezone = ?, updated_at = datetime('now')
            WHERE user_id = ?
            """,
            (city, country, timezone, user_id),
        )
        await db.commit()


async def update_language(user_id: int, language: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET language = ?, updated_at = datetime('now') WHERE user_id = ?",
            (language, user_id),
        )
        await db.commit()


async def update_calc_method(user_id: int, method: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET calc_method = ?, updated_at = datetime('now') WHERE user_id = ?",
            (method, user_id),
        )
        await db.commit()


async def update_isha_window(user_id: int, isha_window: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET isha_window = ?, updated_at = datetime('now') WHERE user_id = ?",
            (isha_window, user_id),
        )
        await db.commit()


async def update_reminder_interval(user_id: int, minutes: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET reminder_interval = ?, updated_at = datetime('now') WHERE user_id = ?",
            (minutes, user_id),
        )
        await db.commit()


async def update_reminders(user_id: int, reminders_on: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET reminders_on = ?, updated_at = datetime('now') WHERE user_id = ?",
            (1 if reminders_on else 0, user_id),
        )
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_all_active_users() -> list[dict]:
    """Return all users who have a location set and reminders enabled."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM users
            WHERE reminders_on = 1
              AND (
                (lat IS NOT NULL AND lng IS NOT NULL)
                OR (city IS NOT NULL AND country IS NOT NULL)
              )
            """
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def has_location(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user:
        return False
    return (user["lat"] is not None and user["lng"] is not None) or (
        user["city"] is not None and user["country"] is not None
    )
