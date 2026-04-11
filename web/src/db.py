"""
Read-only SQLite queries against the bot's database.
SQL is identical to the bot's prayer_log.py / users.py functions.
"""
import datetime
import os

import aiosqlite
import pytz

DB_PATH = os.getenv("DB_PATH", "/app/data/prayer_bot.db")

def _db_uri() -> str:
    """Return a SQLite URI with immutable=1 so WAL-mode DBs can be read
    from a read-only bind-mount without needing to create .db-shm files."""
    return f"file:{DB_PATH}?immutable=1"

ISHA_WINDOW_LABELS = {
    "midnight": {"en": "Until Midnight",       "ar": "حتى منتصف الليل"},
    "fajr":     {"en": "Until Fajr (next day)", "ar": "حتى الفجر (اليوم التالي)"},
    "60":       {"en": "1 hour after Isha",     "ar": "ساعة بعد العشاء"},
    "120":      {"en": "2 hours after Isha",    "ar": "ساعتان بعد العشاء"},
    "180":      {"en": "3 hours after Isha",    "ar": "3 ساعات بعد العشاء"},
}

CALC_METHODS: dict[int, str] = {
    1:  "University of Islamic Sciences, Karachi",
    2:  "Islamic Society of North America (ISNA)",
    3:  "Muslim World League",
    4:  "Umm Al-Qura University, Makkah",
    5:  "Egyptian General Authority of Survey",
    7:  "Institute of Geophysics, University of Tehran",
    8:  "Gulf Region",
    9:  "Kuwait",
    10: "Qatar",
    11: "Majlis Ugama Islam Singapura, Singapore",
    12: "Union Organization Islamic de France",
    13: "Diyanet İşleri Başkanlığı, Turkey",
    14: "Spiritual Administration of Muslims of Russia",
}


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(_db_uri(), uri=True) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_yearly_log(user_id: int, year: int) -> list[dict]:
    """All days in a year: [{date, prayed_count, total}]"""
    async with aiosqlite.connect(_db_uri(), uri=True) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT date,
                   SUM(CASE WHEN status = 'prayed' THEN 1 ELSE 0 END) AS prayed_count,
                   COUNT(*) AS total
            FROM prayer_log
            WHERE user_id = ? AND date LIKE ?
            GROUP BY date
            ORDER BY date ASC
            """,
            (user_id, f"{year}-%"),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_monthly_log(user_id: int, year: int, month: int) -> list[dict]:
    """Days in a month with per-prayer breakdown."""
    month_str = f"{year:04d}-{month:02d}"
    async with aiosqlite.connect(_db_uri(), uri=True) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT date, prayer, status
            FROM prayer_log
            WHERE user_id = ? AND date LIKE ?
            ORDER BY date ASC, prayer ASC
            """,
            (user_id, f"{month_str}-%"),
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    # Group by date
    by_date: dict[str, dict] = {}
    for r in rows:
        d = r["date"]
        if d not in by_date:
            by_date[d] = {"date": d, "prayers": {}}
        by_date[d]["prayers"][r["prayer"]] = r["status"]

    # Add summary counts
    result = []
    for d, entry in sorted(by_date.items()):
        prayed = sum(1 for s in entry["prayers"].values() if s == "prayed")
        entry["prayed_count"] = prayed
        entry["total"] = len(entry["prayers"])
        result.append(entry)
    return result


async def get_prayer_times(user_id: int, date_str: str) -> dict | None:
    """Prayer times for a given date."""
    async with aiosqlite.connect(_db_uri(), uri=True) as db:
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


async def get_daily_log(user_id: int, date_str: str) -> dict:
    """Prayer statuses for a given date: {prayer_name: status}"""
    async with aiosqlite.connect(_db_uri(), uri=True) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT prayer, status FROM prayer_log WHERE user_id = ? AND date = ?",
            (user_id, date_str),
        ) as cur:
            rows = await cur.fetchall()
            return {r["prayer"]: r["status"] for r in rows}


async def get_stats(user_id: int, tz_str: str = "UTC") -> dict:
    """Identical logic to the bot's prayer_log.get_stats()."""
    try:
        tz = pytz.timezone(tz_str)
    except Exception:
        tz = pytz.UTC

    async with aiosqlite.connect(_db_uri(), uri=True) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT date,
                   SUM(CASE WHEN status = 'prayed' THEN 1 ELSE 0 END) AS prayed_count,
                   COUNT(*) AS total
            FROM prayer_log
            WHERE user_id = ?
            GROUP BY date
            ORDER BY date DESC
            """,
            (user_id,),
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    if not rows:
        return {"current_streak": 0, "best_streak": 0,
                "week_prayed": 0, "week_total": 0,
                "month_prayed": 0, "month_total": 0,
                "total_prayed": 0}

    today = datetime.datetime.now(tz).date()

    # Best streak
    best_streak = run = 0
    prev_date = None
    for r in reversed(rows):
        d = datetime.date.fromisoformat(r["date"])
        if r["prayed_count"] == 5 and r["total"] == 5:
            if prev_date is None or (d - prev_date).days == 1:
                run += 1
            else:
                run = 1
            best_streak = max(best_streak, run)
        else:
            run = 0
        prev_date = d

    # Current streak
    current_streak = 0
    check_date = today
    day_map = {r["date"]: r for r in rows}
    while True:
        r = day_map.get(check_date.isoformat())
        if r and r["prayed_count"] == 5 and r["total"] == 5:
            current_streak += 1
            check_date -= datetime.timedelta(days=1)
        else:
            break

    # This week (Sat–Fri)
    week_start = today - datetime.timedelta(days=(today.weekday() - 5) % 7)
    week_rows = [r for r in rows if datetime.date.fromisoformat(r["date"]) >= week_start]
    week_prayed = sum(r["prayed_count"] for r in week_rows)
    week_total  = sum(r["total"]        for r in week_rows)

    # This month
    month_rows   = [r for r in rows if r["date"].startswith(today.strftime("%Y-%m"))]
    month_prayed = sum(r["prayed_count"] for r in month_rows)
    month_total  = sum(r["total"]        for r in month_rows)

    return {
        "current_streak": current_streak,
        "best_streak":    best_streak,
        "week_prayed":    week_prayed,
        "week_total":     week_total,
        "month_prayed":   month_prayed,
        "month_total":    month_total,
        "total_prayed":   sum(r["prayed_count"] for r in rows),
    }
