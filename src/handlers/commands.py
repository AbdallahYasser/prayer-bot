"""
Command handlers:
  /start, /setlocation, /today, /progress, /stats, /settings, /pause, /resume, /help
"""

import logging
import datetime
import calendar

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from src import state
from src.localization import t, prayer_name
from src.config import ALLOWED_USERS, PRAYERS, CALC_METHODS

logger = logging.getLogger(__name__)
router = Router()


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if ALLOWED_USERS and message.from_user.id not in ALLOWED_USERS:
        await message.answer(t("en", "private_bot"))
        return

    user_id = message.from_user.id

    # Auto-detect language
    lc = (message.from_user.language_code or "").lower()
    lang = "ar" if lc.startswith("ar") else "en"

    from src.db import users as db_users
    await db_users.upsert_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        language=lang,
    )

    user = await db_users.get_user(user_id)

    # If user already has location, just show today's times
    if user and (user.get("lat") or user.get("city")):
        await _send_today(message, user)
        return

    # New user — ask for location
    state.onboarding_state[user_id] = {"step": "awaiting_location"}
    await message.answer(t(lang, "welcome"))
    await _ask_for_location(message, lang)


# ---------------------------------------------------------------------------
# /setlocation
# ---------------------------------------------------------------------------

@router.message(Command("setlocation"))
async def cmd_setlocation(message: Message) -> None:
    if ALLOWED_USERS and message.from_user.id not in ALLOWED_USERS:
        return

    user_id = message.from_user.id
    state.onboarding_state[user_id] = {"step": "awaiting_location"}

    from src.db import users as db_users
    user = await db_users.get_user(user_id)
    lang = user.get("language", "en") if user else "en"

    await message.answer(t(lang, "setlocation_prompt"))
    await _ask_for_location(message, lang)


# ---------------------------------------------------------------------------
# /today
# ---------------------------------------------------------------------------

@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    if ALLOWED_USERS and message.from_user.id not in ALLOWED_USERS:
        return

    from src.db import users as db_users
    user = await db_users.get_user(message.from_user.id)

    if not user or not (user.get("lat") or user.get("city")):
        lang = user.get("language", "en") if user else "en"
        await message.answer(t(lang, "no_location"))
        return

    await _send_today(message, user)


# ---------------------------------------------------------------------------
# /progress
# ---------------------------------------------------------------------------

@router.message(Command("progress"))
async def cmd_progress(message: Message) -> None:
    if ALLOWED_USERS and message.from_user.id not in ALLOWED_USERS:
        return

    from src.db import users as db_users
    from src.db import prayer_log as db_log

    user = await db_users.get_user(message.from_user.id)
    lang = user.get("language", "en") if user else "en"

    if not user:
        await message.answer(t(lang, "no_location"))
        return

    import pytz
    tz_str = user.get("timezone") or "UTC"
    try:
        tz = pytz.timezone(tz_str)
    except Exception:
        tz = pytz.UTC

    now = datetime.datetime.now(tz)
    year, month = now.year, now.month
    today_str = now.strftime("%Y-%m-%d")

    month_data = await db_log.get_monthly_log(message.from_user.id, year, month)
    day_map = {r["date"]: r for r in month_data}

    # Build calendar grid
    month_name = now.strftime("%B") if lang == "en" else _arabic_month(month)
    text = t(lang, "progress_header").format(month_name=month_name, year=year)

    # Day-of-week header
    if lang == "en":
        text += "Mo Tu We Th Fr Sa Su\n"
    else:
        text += "إث ثلا أرب خم جم سب أح\n"

    # First day of month (0=Mon, 6=Sun)
    first_weekday = calendar.monthrange(year, month)[0]
    num_days = calendar.monthrange(year, month)[1]

    cells = ["  "] * first_weekday  # padding before day 1

    for day in range(1, num_days + 1):
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        if date_str > today_str:
            cells.append("⬜")
        else:
            r = day_map.get(date_str)
            if not r:
                cells.append("⬜")
            else:
                count = r["prayed_count"]
                if count == 5:
                    cells.append("🟩")
                elif count >= 3:
                    cells.append("🟨")
                elif count >= 1:
                    cells.append("🟧")
                else:
                    cells.append("🟥")

    # Build rows of 7
    rows = [cells[i:i+7] for i in range(0, len(cells), 7)]
    for row in rows:
        text += " ".join(row) + "\n"

    text += t(lang, "progress_legend")
    await message.answer(text)


# ---------------------------------------------------------------------------
# /stats
# ---------------------------------------------------------------------------

@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if ALLOWED_USERS and message.from_user.id not in ALLOWED_USERS:
        return

    from src.db import users as db_users
    from src.db import prayer_log as db_log

    user = await db_users.get_user(message.from_user.id)
    lang = user.get("language", "en") if user else "en"

    stats = await db_log.get_stats(message.from_user.id)

    if stats["total_prayed"] == 0:
        await message.answer(t(lang, "stats_none"))
        return

    week_pct = round(stats["week_prayed"] / stats["week_total"] * 100) if stats["week_total"] else 0
    month_pct = round(stats["month_prayed"] / stats["month_total"] * 100) if stats["month_total"] else 0

    text = t(lang, "stats_header")
    text += t(lang, "stats_streak").format(n=stats["current_streak"])
    text += t(lang, "stats_best").format(n=stats["best_streak"])
    text += t(lang, "stats_week").format(
        pct=week_pct, prayed=stats["week_prayed"], total=stats["week_total"]
    )
    text += t(lang, "stats_month").format(
        pct=month_pct, prayed=stats["month_prayed"], total=stats["month_total"]
    )
    text += t(lang, "stats_total").format(total=stats["total_prayed"])

    await message.answer(text)


# ---------------------------------------------------------------------------
# /settings
# ---------------------------------------------------------------------------

@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    if ALLOWED_USERS and message.from_user.id not in ALLOWED_USERS:
        return

    from src.db import users as db_users
    from src.handlers.callbacks import _build_settings_text, _build_settings_keyboard

    user = await db_users.get_user(message.from_user.id)
    if not user:
        return

    await message.answer(
        _build_settings_text(user),
        reply_markup=_build_settings_keyboard(user),
    )


# ---------------------------------------------------------------------------
# /pause
# ---------------------------------------------------------------------------

@router.message(Command("pause"))
async def cmd_pause(message: Message) -> None:
    if ALLOWED_USERS and message.from_user.id not in ALLOWED_USERS:
        return

    user_id = message.from_user.id
    from src.db import users as db_users

    user = await db_users.get_user(user_id)
    lang = user.get("language", "en") if user else "en"

    await db_users.update_reminders(user_id, False)

    # Cancel active reminder tasks
    keys_to_cancel = [k for k in state.active_reminder_tasks if k.startswith(f"{user_id}_")]
    for k in keys_to_cancel:
        task = state.active_reminder_tasks.pop(k, None)
        if task and not task.done():
            task.cancel()

    # Remove today's scheduler jobs (keep midnight job)
    from src import scheduler as sched
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    today_str = datetime.date.today().isoformat()
    for job in sched.scheduler.get_jobs():
        jid = job.id
        if jid.startswith(f"{user_id}_") and today_str in jid:
            job.remove()

    await message.answer(t(lang, "paused"))


# ---------------------------------------------------------------------------
# /resume
# ---------------------------------------------------------------------------

@router.message(Command("resume"))
async def cmd_resume(message: Message) -> None:
    if ALLOWED_USERS and message.from_user.id not in ALLOWED_USERS:
        return

    user_id = message.from_user.id
    from src.db import users as db_users

    user = await db_users.get_user(user_id)
    lang = user.get("language", "en") if user else "en"

    if not user or not (user.get("lat") or user.get("city")):
        await message.answer(t(lang, "no_location"))
        return

    await db_users.update_reminders(user_id, True)

    from src import scheduler as sched
    await sched.reschedule_user_today(user_id)

    # Show today's remaining prayers
    from src.db import prayer_times as db_pt
    from src.db import prayer_log as db_log
    import pytz

    tz_str = user.get("timezone") or "UTC"
    try:
        tz = pytz.timezone(tz_str)
    except Exception:
        tz = pytz.UTC
    today_str = datetime.datetime.now(tz).strftime("%Y-%m-%d")

    times = await db_pt.get_prayer_times(user_id, today_str)
    daily_log = await db_log.get_daily_log(user_id, today_str)

    if times:
        summary = _build_today_text(times, daily_log, lang)
        await message.answer(t(lang, "resumed").format(today_times=summary))
    else:
        await message.answer(t(lang, "resumed").format(today_times=""))


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if ALLOWED_USERS and message.from_user.id not in ALLOWED_USERS:
        return

    from src.db import users as db_users
    user = await db_users.get_user(message.from_user.id)
    lang = user.get("language", "en") if user else "en"

    await message.answer(t(lang, "help"))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _ask_for_location(message: Message, lang: str) -> None:
    """Send the location-request prompt with the GPS share button."""
    user_id = message.from_user.id
    state.onboarding_state[user_id] = {"step": "awaiting_location"}

    # Update state to text input mode (button tap → location handler; text → location handler)
    state.onboarding_state[user_id] = {"step": "awaiting_city_text"}

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Share my location", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer(t(lang, "ask_location"), reply_markup=keyboard)


async def _send_today(message: Message, user: dict) -> None:
    """Build and send today's prayer times + status."""
    import pytz
    from src.db import prayer_times as db_pt
    from src.db import prayer_log as db_log

    user_id = message.from_user.id
    lang = user.get("language", "en")

    tz_str = user.get("timezone") or "UTC"
    try:
        tz = pytz.timezone(tz_str)
    except Exception:
        tz = pytz.UTC

    today_str = datetime.datetime.now(tz).strftime("%Y-%m-%d")
    today_display = datetime.datetime.now(tz).strftime("%A, %d %B %Y")

    times = await db_pt.get_or_fetch(user_id, today_str, user)
    if not times:
        await message.answer(t(lang, "location_invalid"))
        return

    daily_log = await db_log.get_daily_log(user_id, today_str)

    header = t(lang, "today_header").format(date=today_display)
    body = _build_today_text(times, daily_log, lang)
    await message.answer(header + body)


def _build_today_text(times: dict, daily_log: list, lang: str) -> str:
    status_map = {row["prayer"]: row["status"] for row in daily_log}
    icon_map = {"prayed": "✅", "missed": "❌", "pending": "⏳"}
    lines = []
    for prayer in PRAYERS:
        time_str = times.get(prayer, "—")
        status = status_map.get(prayer, "pending")
        icon = icon_map.get(status, "⏳")
        p_name = prayer_name(prayer, lang)
        lines.append(f"{icon} <b>{p_name:<8}</b>  {time_str}")
    return "\n".join(lines)


def _arabic_month(month: int) -> str:
    names = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
    ]
    return names[month - 1]
