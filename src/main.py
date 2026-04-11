import asyncio
import logging
# prayer-bot

import aiosqlite
from aiogram import Dispatcher
from aiogram.types import BotCommand

from src.config import BOT_TOKEN, DB_PATH, LOG_LEVEL
from src.bot_instance import bot
from src import scheduler as sched
from src.handlers import commands, location, callbacks

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    user_id            INTEGER PRIMARY KEY,
    username           TEXT,
    first_name         TEXT,
    language           TEXT    NOT NULL DEFAULT 'en',
    lat                REAL,
    lng                REAL,
    city               TEXT,
    country            TEXT,
    timezone           TEXT    NOT NULL DEFAULT 'UTC',
    calc_method        INTEGER NOT NULL DEFAULT 5,
    reminders_on       INTEGER NOT NULL DEFAULT 1,
    isha_window        TEXT    NOT NULL DEFAULT 'midnight',
    reminder_interval  INTEGER NOT NULL DEFAULT 5,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""

_CREATE_PRAYER_TIMES = """
CREATE TABLE IF NOT EXISTS prayer_times (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    date        TEXT    NOT NULL,
    fajr        TEXT    NOT NULL,
    sunrise     TEXT,
    dhuhr       TEXT    NOT NULL,
    asr         TEXT    NOT NULL,
    maghrib     TEXT    NOT NULL,
    isha        TEXT    NOT NULL,
    UNIQUE(user_id, date),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)
"""

_CREATE_PRAYER_LOG = """
CREATE TABLE IF NOT EXISTS prayer_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    date       TEXT    NOT NULL,
    prayer     TEXT    NOT NULL,
    status     TEXT    NOT NULL DEFAULT 'pending',
    logged_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, date, prayer),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(_CREATE_USERS)
        await db.execute(_CREATE_PRAYER_TIMES)
        await db.execute(_CREATE_PRAYER_LOG)
        # Migrations: add new columns to existing databases
        for migration in [
            "ALTER TABLE prayer_times ADD COLUMN sunrise TEXT",
            "ALTER TABLE users ADD COLUMN isha_window TEXT NOT NULL DEFAULT 'midnight'",
            "ALTER TABLE users ADD COLUMN reminder_interval INTEGER NOT NULL DEFAULT 5",
        ]:
            try:
                await db.execute(migration)
            except Exception:
                pass  # column already exists
        await db.commit()
    logger.info("Database initialized at %s", DB_PATH)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    await init_db()

    dp = Dispatcher()
    dp.include_router(commands.router)
    dp.include_router(location.router)
    dp.include_router(callbacks.router)

    await bot.set_my_commands([
        BotCommand(command="today",       description="Today's prayer times and status"),
        BotCommand(command="progress",    description="Monthly prayer calendar"),
        BotCommand(command="stats",       description="Streaks and percentages"),
        BotCommand(command="setlocation", description="Update your location"),
        BotCommand(command="settings",    description="Language, calculation method, reminders"),
        BotCommand(command="pause",       description="Pause all reminders"),
        BotCommand(command="resume",      description="Resume reminders"),
        BotCommand(command="help",        description="Command list"),
    ])

    sched.scheduler.start()
    await sched.schedule_all_users(bot)

    logger.info("Bot started. Polling...")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
