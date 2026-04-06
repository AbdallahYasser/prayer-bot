import aiosqlite
from src.config import DB_PATH, PRAYERS


async def upsert_prayer_times(user_id: int, date_str: str, times: dict) -> None:
    """Cache prayer times for a user/date. times = {Fajr: "04:32", Sunrise: "06:01", ...}"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO prayer_times (user_id, date, fajr, sunrise, dhuhr, asr, maghrib, isha)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                fajr    = excluded.fajr,
                sunrise = excluded.sunrise,
                dhuhr   = excluded.dhuhr,
                asr     = excluded.asr,
                maghrib = excluded.maghrib,
                isha    = excluded.isha
            """,
            (
                user_id, date_str,
                times["Fajr"], times.get("Sunrise"),
                times["Dhuhr"], times["Asr"],
                times["Maghrib"], times["Isha"],
            ),
        )
        await db.commit()


async def get_prayer_times(user_id: int, date_str: str) -> dict | None:
    """Return cached prayer times as {Fajr: "04:32", Sunrise: "06:01", ...} or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM prayer_times WHERE user_id = ? AND date = ?",
            (user_id, date_str),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "Fajr":    row["fajr"],
                "Sunrise": row["sunrise"],
                "Dhuhr":   row["dhuhr"],
                "Asr":     row["asr"],
                "Maghrib": row["maghrib"],
                "Isha":    row["isha"],
            }


async def get_or_fetch(user_id: int, date_str: str, user_row: dict) -> dict | None:
    """
    Check cache first. On miss, call Aladhan API, store result, return it.
    Returns None if Aladhan API fails.
    """
    cached = await get_prayer_times(user_id, date_str)
    if cached:
        return cached

    from src.services import aladhan

    if user_row.get("lat") is not None and user_row.get("lng") is not None:
        result = await aladhan.fetch_by_coords(
            lat=user_row["lat"],
            lng=user_row["lng"],
            method=user_row.get("calc_method", 5),
            date_str=date_str,
        )
    elif user_row.get("city") and user_row.get("country"):
        result = await aladhan.fetch_by_city(
            city=user_row["city"],
            country=user_row["country"],
            method=user_row.get("calc_method", 5),
            date_str=date_str,
        )
    else:
        return None

    if result:
        await upsert_prayer_times(user_id, date_str, result)

    return result
