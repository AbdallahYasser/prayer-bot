"""
Aladhan API service — free, no API key required.
Docs: https://aladhan.com/prayer-times-api

Two fetch strategies:
  1. fetch_by_coords(lat, lng, method, date_str) — most accurate (GPS-level)
  2. fetch_by_city(city, country, method, date_str) — city-level fallback

Both return:
  {"Fajr": "04:32", "Dhuhr": "12:01", "Asr": "15:44",
   "Maghrib": "18:21", "Isha": "19:51", "timezone": "Africa/Cairo"}
or None on any error.
"""

import logging
import datetime
import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://api.aladhan.com/v1"
PRAYER_KEYS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]


def _strip_suffix(time_str: str) -> str:
    """Aladhan sometimes returns '04:32 (EET)' — strip the suffix."""
    return time_str.split(" ")[0].strip() if time_str else time_str


def _parse_response(data: dict) -> dict | None:
    """Extract prayer times and timezone from Aladhan response data dict."""
    try:
        timings = data["timings"]
        timezone = data["meta"]["timezone"]
        result = {k: _strip_suffix(timings[k]) for k in PRAYER_KEYS}
        result["timezone"] = timezone
        return result
    except (KeyError, TypeError) as e:
        logger.warning("Failed to parse Aladhan response: %s", e)
        return None


async def fetch_by_coords(
    lat: float,
    lng: float,
    method: int,
    date_str: str,  # "YYYY-MM-DD"
) -> dict | None:
    """
    Fetch prayer times using GPS coordinates.
    Uses Unix timestamp (noon UTC on the given date) as the time parameter.
    """
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(
            hour=12, tzinfo=datetime.timezone.utc
        )
        timestamp = int(dt.timestamp())

        url = f"{BASE_URL}/timings/{timestamp}"
        params = {"latitude": lat, "longitude": lng, "method": method}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning("Aladhan coords API returned %s", resp.status)
                    return None
                body = await resp.json()
                if body.get("code") != 200:
                    logger.warning("Aladhan coords API error: %s", body.get("status"))
                    return None
                return _parse_response(body["data"])
    except Exception as e:
        logger.error("fetch_by_coords error: %s", e)
        return None


async def fetch_by_city(
    city: str,
    country: str,
    method: int,
    date_str: str,  # "YYYY-MM-DD"
) -> dict | None:
    """
    Fetch prayer times using city + country name.
    NOTE: timingsByCity uses DD-MM-YYYY date format (different from coords endpoint).
    """
    try:
        # Convert YYYY-MM-DD → DD-MM-YYYY for this endpoint
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        aladhan_date = dt.strftime("%d-%m-%Y")

        url = f"{BASE_URL}/timingsByCity"
        params = {
            "city": city,
            "country": country,
            "method": method,
            "date": aladhan_date,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning("Aladhan city API returned %s", resp.status)
                    return None
                body = await resp.json()
                if body.get("code") != 200:
                    logger.warning("Aladhan city API error: %s", body.get("status"))
                    return None
                return _parse_response(body["data"])
    except Exception as e:
        logger.error("fetch_by_city error: %s", e)
        return None


async def fetch_for_user(user_row: dict, date_str: str) -> dict | None:
    """
    Convenience wrapper: choose coordinate or city endpoint based on what the user has set.
    """
    if user_row.get("lat") is not None and user_row.get("lng") is not None:
        return await fetch_by_coords(
            lat=user_row["lat"],
            lng=user_row["lng"],
            method=user_row.get("calc_method", 5),
            date_str=date_str,
        )
    elif user_row.get("city") and user_row.get("country"):
        return await fetch_by_city(
            city=user_row["city"],
            country=user_row["country"],
            method=user_row.get("calc_method", 5),
            date_str=date_str,
        )
    return None
