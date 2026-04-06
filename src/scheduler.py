"""
Prayer scheduler using APScheduler AsyncIOScheduler.

Startup flow:
  1. schedule_all_users()  — called once from main.py on bot start
  2. For each user: fetch today's prayer times → schedule notify + ask jobs
  3. Schedule midnight reschedule job per user (CronTrigger)

On bot restart: schedule_all_users() re-runs; only future jobs are added
(replace_existing=True + "if > now" guard make this fully idempotent).

Job naming:
  {user_id}_{prayer}_{date}_notify   → fires at prayer time
  {user_id}_{prayer}_{date}_ask      → fires 15 min after prayer time
  {user_id}_midnight                 → fires at 00:01 in user's timezone daily
"""

import asyncio
import logging
import datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from src.config import PRAYERS, DB_PATH
from src import state

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

async def schedule_all_users(bot) -> None:
    """
    Called once on bot startup.
    Loads all users with location set, schedules today's prayers for each.
    """
    from src.db import users as db_users
    from src.db import prayer_times as db_pt
    from src.db import prayer_log as db_log

    all_users = await db_users.get_all_active_users()
    logger.info("Scheduling prayers for %d users", len(all_users))

    for user in all_users:
        user_id = user["user_id"]
        tz_str = user.get("timezone") or "UTC"
        try:
            tz = pytz.timezone(tz_str)
        except pytz.UnknownTimeZoneError:
            tz = pytz.UTC

        today_str = datetime.datetime.now(tz).strftime("%Y-%m-%d")

        times = await db_pt.get_or_fetch(user_id, today_str, user)
        if not times:
            logger.warning("Could not get prayer times for user %d on %s", user_id, today_str)
            continue

        await db_log.init_daily_log(user_id, today_str)
        _schedule_user_day(user_id, today_str, times, tz_str)
        _schedule_midnight_job(user_id, tz_str)

    logger.info("Scheduler setup complete")


async def reschedule_user_today(user_id: int) -> None:
    """
    Call after a user updates their location or settings.
    Removes existing jobs for this user and reschedules from scratch.
    """
    from src.db import users as db_users
    from src.db import prayer_times as db_pt
    from src.db import prayer_log as db_log

    _remove_user_jobs(user_id)

    user = await db_users.get_user(user_id)
    if not user:
        return

    tz_str = user.get("timezone") or "UTC"
    try:
        tz = pytz.timezone(tz_str)
    except pytz.UnknownTimeZoneError:
        tz = pytz.UTC

    today_str = datetime.datetime.now(tz).strftime("%Y-%m-%d")
    # Invalidate cache so fresh times are fetched after a location change
    times = await db_pt.get_or_fetch(user_id, today_str, user)
    if not times:
        return

    await db_log.init_daily_log(user_id, today_str)
    _schedule_user_day(user_id, today_str, times, tz_str)
    _schedule_midnight_job(user_id, tz_str)


# ---------------------------------------------------------------------------
# Internal scheduling helpers
# ---------------------------------------------------------------------------

def _remove_user_jobs(user_id: int) -> None:
    """Remove all scheduler jobs for this user."""
    prefix = f"{user_id}_"
    for job in scheduler.get_jobs():
        if job.id.startswith(prefix):
            job.remove()


def _schedule_user_day(user_id: int, date_str: str, times: dict, tz_str: str) -> None:
    """
    Schedule notify + ask jobs for all 5 prayers on a given date.
    Only schedules jobs that are still in the future.
    """
    try:
        tz = pytz.timezone(tz_str)
    except pytz.UnknownTimeZoneError:
        tz = pytz.UTC

    now_utc = datetime.datetime.now(datetime.timezone.utc)

    for prayer in PRAYERS:
        time_str = times.get(prayer)
        if not time_str:
            continue

        try:
            hour, minute = map(int, time_str.split(":"))
        except ValueError:
            logger.warning("Bad time format for %s: %s", prayer, time_str)
            continue

        naive_dt = datetime.datetime.strptime(f"{date_str} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")
        try:
            aware_dt = tz.localize(naive_dt)
        except Exception:
            aware_dt = naive_dt.replace(tzinfo=pytz.UTC)

        # Notify job — at prayer time
        if aware_dt > now_utc:
            job_id = f"{user_id}_{prayer}_{date_str}_notify"
            scheduler.add_job(
                _send_prayer_notification,
                trigger=DateTrigger(run_date=aware_dt),
                id=job_id,
                replace_existing=True,
                args=[user_id, prayer, date_str, time_str],
                misfire_grace_time=300,
            )
            logger.debug("Scheduled notify: %s at %s", job_id, aware_dt)

        # Ask job — 15 minutes after prayer time
        ask_dt = aware_dt + datetime.timedelta(minutes=15)
        if ask_dt > now_utc:
            job_id = f"{user_id}_{prayer}_{date_str}_ask"
            scheduler.add_job(
                _send_prayer_ask,
                trigger=DateTrigger(run_date=ask_dt),
                id=job_id,
                replace_existing=True,
                args=[user_id, prayer, date_str],
                misfire_grace_time=300,
            )
            logger.debug("Scheduled ask: %s at %s", job_id, ask_dt)


def _schedule_midnight_job(user_id: int, tz_str: str) -> None:
    """
    Schedule a daily job at 00:01 in the user's timezone to set up
    the next day's prayer reminders.
    """
    try:
        tz = pytz.timezone(tz_str)
    except pytz.UnknownTimeZoneError:
        tz = pytz.UTC

    scheduler.add_job(
        _midnight_reschedule,
        trigger=CronTrigger(hour=0, minute=1, timezone=tz),
        id=f"{user_id}_midnight",
        replace_existing=True,
        args=[user_id],
    )


# ---------------------------------------------------------------------------
# Scheduled job functions
# ---------------------------------------------------------------------------

async def _send_prayer_notification(user_id: int, prayer: str, date_str: str, time_str: str) -> None:
    """Fires at prayer time. Sends the initial reminder message."""
    from src.bot_instance import bot
    from src.db import users as db_users
    from src.localization import t, prayer_name

    user = await db_users.get_user(user_id)
    if not user or not user.get("reminders_on"):
        return

    lang = user.get("language", "en")
    p_name = prayer_name(prayer, lang)

    text = t(lang, "prayer_time").format(prayer=p_name, time=time_str)

    try:
        await bot.send_message(user_id, text)
        logger.info("Sent prayer notification to %d: %s", user_id, prayer)
    except Exception as e:
        logger.error("Failed to send prayer notification to %d: %s", user_id, e)


async def _send_prayer_ask(user_id: int, prayer: str, date_str: str) -> None:
    """
    Fires 15 min after prayer time.
    Sends 'Did you pray?' inline keyboard.
    Starts the 5-min repeat loop.
    """
    from src.bot_instance import bot
    from src.db import users as db_users
    from src.db import prayer_log as db_log
    from src.localization import t, prayer_name

    user = await db_users.get_user(user_id)
    if not user or not user.get("reminders_on"):
        return

    # Already confirmed? Don't ask.
    status = await db_log.get_status(user_id, date_str, prayer)
    if status == "prayed":
        return

    lang = user.get("language", "en")
    p_name = prayer_name(prayer, lang)

    await _send_ask_message(bot, user_id, prayer, date_str, p_name, lang)

    # Start 5-min repeat loop
    task_key = f"{user_id}_{prayer}_{date_str}"
    if task_key not in state.active_reminder_tasks:
        task = asyncio.create_task(
            _repeat_reminder_loop(user_id, prayer, date_str)
        )
        state.active_reminder_tasks[task_key] = task


async def _send_ask_message(bot, user_id: int, prayer: str, date_str: str, p_name: str, lang: str) -> None:
    """Send the 'Did you pray?' message with Yes/No inline keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Yes" if lang == "en" else "✅ نعم",
            callback_data=f"pray:yes:{prayer}:{date_str}",
        ),
        InlineKeyboardButton(
            text="❌ No" if lang == "en" else "❌ لا",
            callback_data=f"pray:no:{prayer}:{date_str}",
        ),
    ]])

    from src.localization import t
    text = t(lang, "did_you_pray").format(prayer=p_name)

    try:
        await bot.send_message(user_id, text, reply_markup=keyboard)
    except Exception as e:
        logger.error("Failed to send ask message to %d: %s", user_id, e)


async def _repeat_reminder_loop(user_id: int, prayer: str, date_str: str) -> None:
    """
    Runs as an asyncio.Task.
    Every 5 minutes: check if still pending → if next prayer has arrived → mark missed and stop.
    Otherwise, resend the 'Did you pray?' message.
    """
    from src.bot_instance import bot
    from src.db import users as db_users
    from src.db import prayer_log as db_log
    from src.db import prayer_times as db_pt
    from src.localization import prayer_name

    task_key = f"{user_id}_{prayer}_{date_str}"

    try:
        while True:
            await asyncio.sleep(300)  # 5 minutes

            status = await db_log.get_status(user_id, date_str, prayer)
            if status in ("prayed", "missed"):
                break

            user = await db_users.get_user(user_id)
            if not user or not user.get("reminders_on"):
                break

            # Check if the next prayer's time has passed → window is closed
            if await _is_window_closed(user_id, prayer, date_str, user):
                await db_log.update_status(user_id, date_str, prayer, "missed")
                logger.info("Marked %s as missed for user %d on %s", prayer, user_id, date_str)
                break

            lang = user.get("language", "en")
            p_name = prayer_name(prayer, lang)
            await _send_ask_message(bot, user_id, prayer, date_str, p_name, lang)

    except asyncio.CancelledError:
        pass  # Task cancelled because user tapped ✅ Yes
    finally:
        state.active_reminder_tasks.pop(task_key, None)


async def _is_window_closed(user_id: int, prayer: str, date_str: str, user: dict) -> bool:
    """
    Returns True if the reminder window for this prayer has closed.

    Window rules:
      Fajr    → closes at Sunrise (شروق) — you cannot pray Fajr after the sun rises
      Dhuhr–Maghrib → closes when the next prayer time arrives
      Isha    → closes 30 min after Isha time (gives room for late confirmation)
    """
    from src.db import prayer_times as db_pt

    times = await db_pt.get_prayer_times(user_id, date_str)
    if not times:
        return True

    tz_str = user.get("timezone") or "UTC"
    try:
        tz = pytz.timezone(tz_str)
    except pytz.UnknownTimeZoneError:
        tz = pytz.UTC

    now = datetime.datetime.now(tz)

    def _aware(time_str: str) -> datetime.datetime:
        h, m = map(int, time_str.split(":"))
        naive = datetime.datetime.strptime(f"{date_str} {h:02d}:{m:02d}", "%Y-%m-%d %H:%M")
        return tz.localize(naive)

    if prayer == "Fajr":
        # Fajr window closes at Sunrise
        sunrise_str = times.get("Sunrise")
        if sunrise_str:
            return now >= _aware(sunrise_str)
        # Fallback: use Dhuhr if Sunrise not stored
        return now >= _aware(times.get("Dhuhr", "12:00"))

    next_prayer_idx = PRAYERS.index(prayer) + 1

    if next_prayer_idx >= len(PRAYERS):
        # Isha: window closes 30 minutes after Isha time
        window_end = _aware(times.get("Isha", "00:00")) + datetime.timedelta(minutes=30)
        return now > window_end
    else:
        next_prayer = PRAYERS[next_prayer_idx]
        return now >= _aware(times.get(next_prayer, "00:00"))


async def _midnight_reschedule(user_id: int) -> None:
    """
    Fires at 00:01 in the user's timezone.
    Fetches tomorrow's prayer times and schedules jobs for the new day.
    """
    from src.db import users as db_users
    from src.db import prayer_times as db_pt
    from src.db import prayer_log as db_log

    user = await db_users.get_user(user_id)
    if not user:
        return

    tz_str = user.get("timezone") or "UTC"
    try:
        tz = pytz.timezone(tz_str)
    except pytz.UnknownTimeZoneError:
        tz = pytz.UTC

    tomorrow_str = (datetime.datetime.now(tz) + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    times = await db_pt.get_or_fetch(user_id, tomorrow_str, user)
    if not times:
        logger.warning("Could not get prayer times for user %d on %s", user_id, tomorrow_str)
        return

    await db_log.init_daily_log(user_id, tomorrow_str)
    _schedule_user_day(user_id, tomorrow_str, times, tz_str)
    logger.info("Midnight reschedule done for user %d → %s", user_id, tomorrow_str)
