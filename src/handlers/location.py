"""
Location handlers:
  1. Telegram native location share (F.location)
  2. Text input (city + country) when onboarding_state is active
"""

import logging
import datetime

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove

from src import state
from src.localization import t

logger = logging.getLogger(__name__)
router = Router()


def _format_today_times(times: dict, log: list, lang: str) -> str:
    """Build a quick summary of today's prayer times after location is set."""
    from src.config import PRAYERS
    from src.localization import prayer_name

    lines = []
    status_map = {row["prayer"]: row["status"] for row in log} if log else {}

    for prayer in PRAYERS:
        time_str = times.get(prayer, "—")
        status = status_map.get(prayer, "pending")
        icon = {"prayed": "✅", "missed": "❌"}.get(status, "⏳")
        p_name = prayer_name(prayer, lang)
        lines.append(f"{icon} <b>{p_name}</b>  {time_str}")

    return "\n".join(lines)


async def _apply_location(message: Message, lat: float | None, lng: float | None,
                           city: str | None, country: str | None) -> None:
    """
    Common logic after location is received (either GPS or text).
    1. Call Aladhan to validate + get timezone.
    2. Store in DB.
    3. Reschedule today's prayers.
    4. Reply with today's times.
    """
    import datetime
    from src.db import users as db_users
    from src.db import prayer_times as db_pt
    from src.db import prayer_log as db_log
    from src import scheduler as sched
    from src.services import aladhan

    user_id = message.from_user.id
    user = await db_users.get_user(user_id)
    lang = user.get("language", "en") if user else "en"
    method = user.get("calc_method", 5) if user else 5

    today_str = datetime.date.today().isoformat()

    # Fetch from Aladhan (validates location + gets timezone)
    if lat is not None and lng is not None:
        result = await aladhan.fetch_by_coords(lat, lng, method, today_str)
    else:
        result = await aladhan.fetch_by_city(city, country, method, today_str)

    if not result:
        await message.answer(t(lang, "location_invalid"), reply_markup=ReplyKeyboardRemove())
        return

    timezone = result.pop("timezone", "UTC")  # extract before storing times

    # Save location to DB
    if lat is not None and lng is not None:
        await db_users.update_location_coords(user_id, lat, lng, timezone)
    else:
        await db_users.update_location_city(user_id, city, country, timezone)

    # Now use correct timezone for today's date
    import pytz
    try:
        tz = pytz.timezone(timezone)
    except Exception:
        tz = pytz.UTC
    today_str = datetime.datetime.now(tz).strftime("%Y-%m-%d")

    # Cache times and init log
    await db_pt.upsert_prayer_times(user_id, today_str, result)
    await db_log.init_daily_log(user_id, today_str)
    daily_log = await db_log.get_daily_log(user_id, today_str)

    # Reschedule
    await sched.reschedule_user_today(user_id)

    # Clear onboarding state
    state.onboarding_state.pop(user_id, None)

    # Reply
    today_summary = _format_today_times(result, daily_log, lang)
    already_set = user and (user.get("lat") or user.get("city"))
    msg_key = "location_updated" if already_set else "location_set"

    await message.answer(
        t(lang, msg_key).format(today_times=today_summary),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(F.location)
async def handle_location_share(message: Message) -> None:
    """Handle Telegram native location share (GPS)."""
    if state.allowed_users and message.from_user.id not in state.allowed_users:
        return

    await _apply_location(
        message,
        lat=message.location.latitude,
        lng=message.location.longitude,
        city=None,
        country=None,
    )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_input(message: Message) -> None:
    """
    Handle plain text when user is in location-setup flow.
    Expected format: "Cairo Egypt" or "Cairo, Egypt"
    """
    if state.allowed_users and message.from_user.id not in state.allowed_users:
        return

    user_id = message.from_user.id
    s = state.onboarding_state.get(user_id)

    if not s or s.get("step") != "awaiting_city_text":
        # Not in location flow — ignore (other handlers will catch it)
        return

    text = message.text.strip()

    # Parse "City Country" or "City, Country"
    text_clean = text.replace(",", " ")
    parts = text_clean.split()
    if len(parts) < 2:
        from src.db import users as db_users
        user = await db_users.get_user(user_id)
        lang = user.get("language", "en") if user else "en"
        await message.answer(t(lang, "location_invalid"))
        return

    # Last word = country, everything before = city
    country = parts[-1]
    city = " ".join(parts[:-1])

    await _apply_location(message, lat=None, lng=None, city=city, country=country)
