import aiosqlite
from src.config import DB_PATH, PRAYERS


async def init_daily_log(user_id: int, date_str: str) -> None:
    """
    Insert 5 pending rows for the day. INSERT OR IGNORE makes this idempotent —
    safe to call multiple times without duplicating rows.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        for prayer in PRAYERS:
            await db.execute(
                """
                INSERT OR IGNORE INTO prayer_log (user_id, date, prayer, status)
                VALUES (?, ?, ?, 'pending')
                """,
                (user_id, date_str, prayer),
            )
        await db.commit()


async def update_status(user_id: int, date_str: str, prayer: str, status: str) -> None:
    """status: 'pending' | 'prayed' | 'missed'"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO prayer_log (user_id, date, prayer, status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, date, prayer) DO UPDATE SET
                status    = excluded.status,
                logged_at = datetime('now')
            """,
            (user_id, date_str, prayer, status),
        )
        await db.commit()


async def get_status(user_id: int, date_str: str, prayer: str) -> str | None:
    """Return 'pending', 'prayed', 'missed', or None if no row yet."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT status FROM prayer_log WHERE user_id = ? AND date = ? AND prayer = ?",
            (user_id, date_str, prayer),
        ) as cur:
            row = await cur.fetchone()
            return row["status"] if row else None


async def get_daily_log(user_id: int, date_str: str) -> list[dict]:
    """Return list of {prayer, status} for the day, ordered by PRAYERS order."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT prayer, status FROM prayer_log WHERE user_id = ? AND date = ?",
            (user_id, date_str),
        ) as cur:
            rows = await cur.fetchall()
            by_prayer = {r["prayer"]: r["status"] for r in rows}
            return [{"prayer": p, "status": by_prayer.get(p, "pending")} for p in PRAYERS]


async def get_monthly_log(user_id: int, year: int, month: int) -> list[dict]:
    """
    Return [{date, prayed_count, total}, ...] for each day in the month
    that has any log entry.
    """
    month_str = f"{year:04d}-{month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
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
            (user_id, f"{month_str}-%"),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_stats(user_id: int) -> dict:
    """
    Compute:
    - current_streak: consecutive days (most recent first) where all 5 were prayed
    - best_streak: longest such streak ever
    - week_prayed / week_total: this calendar week (Mon-Sun)
    - month_prayed / month_total: this calendar month
    - total_prayed: all time
    """
    import datetime

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # All days summary
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
        return {
            "current_streak": 0, "best_streak": 0,
            "week_prayed": 0, "week_total": 0,
            "month_prayed": 0, "month_total": 0,
            "total_prayed": 0,
        }

    today = datetime.date.today()

    # Streak: consecutive days where prayed_count == total (all 5)
    current_streak = 0
    best_streak = 0
    run = 0
    prev_date = None

    # rows are DESC — iterate to compute streaks
    for r in reversed(rows):  # ASC order
        d = datetime.date.fromisoformat(r["date"])
        perfect = r["prayed_count"] == 5 and r["total"] == 5

        if perfect:
            if prev_date is None or (d - prev_date).days == 1:
                run += 1
            else:
                run = 1
            best_streak = max(best_streak, run)
        else:
            run = 0
        prev_date = d

    # Current streak: count backwards from today
    current_streak = 0
    check_date = today
    day_map = {r["date"]: r for r in rows}
    while True:
        ds = check_date.isoformat()
        r = day_map.get(ds)
        if r and r["prayed_count"] == 5 and r["total"] == 5:
            current_streak += 1
            check_date -= datetime.timedelta(days=1)
        else:
            break

    # This week (Mon–Sun)
    week_start = today - datetime.timedelta(days=today.weekday())
    week_rows = [r for r in rows if datetime.date.fromisoformat(r["date"]) >= week_start]
    week_prayed = sum(r["prayed_count"] for r in week_rows)
    week_total = sum(r["total"] for r in week_rows)

    # This month
    month_rows = [r for r in rows if r["date"].startswith(today.strftime("%Y-%m"))]
    month_prayed = sum(r["prayed_count"] for r in month_rows)
    month_total = sum(r["total"] for r in month_rows)

    # All time
    total_prayed = sum(r["prayed_count"] for r in rows)

    return {
        "current_streak": current_streak,
        "best_streak": best_streak,
        "week_prayed": week_prayed,
        "week_total": week_total,
        "month_prayed": month_prayed,
        "month_total": month_total,
        "total_prayed": total_prayed,
    }
