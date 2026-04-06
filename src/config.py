import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DB_PATH: str = os.getenv("DB_PATH", "/app/data/prayer_bot.db")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Comma-separated Telegram user IDs allowed to use the bot
_raw = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = {int(x.strip()) for x in _raw.split(",") if x.strip().isdigit()}

PRAYERS: list[str] = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

PRAYER_NAMES: dict[str, dict[str, str]] = {
    "Fajr":    {"en": "Fajr",    "ar": "الفجر"},
    "Dhuhr":   {"en": "Dhuhr",   "ar": "الظهر"},
    "Asr":     {"en": "Asr",     "ar": "العصر"},
    "Maghrib": {"en": "Maghrib", "ar": "المغرب"},
    "Isha":    {"en": "Isha",    "ar": "العشاء"},
}

# Isha window options — value stored in DB as string
# "midnight" = closes at 00:00 user's timezone
# "fajr"     = closes at next day's Fajr time
# "60","120","180" = closes N minutes after Isha time
ISHA_WINDOW_OPTIONS: dict[str, dict[str, str]] = {
    "midnight": {"en": "Until Midnight",        "ar": "حتى منتصف الليل"},
    "fajr":     {"en": "Until Fajr (next day)",  "ar": "حتى الفجر (اليوم التالي)"},
    "60":       {"en": "1 hour after Isha",      "ar": "ساعة بعد العشاء"},
    "120":      {"en": "2 hours after Isha",     "ar": "ساعتان بعد العشاء"},
    "180":      {"en": "3 hours after Isha",     "ar": "3 ساعات بعد العشاء"},
}

# Reminder repeat interval options (minutes)
REMINDER_INTERVALS: list[int] = [1, 2, 3, 5, 10, 15, 30]

# Aladhan calculation methods
CALC_METHODS: dict[int, str] = {
    1: "University of Islamic Sciences, Karachi",
    2: "Islamic Society of North America (ISNA)",
    3: "Muslim World League",
    4: "Umm Al-Qura University, Makkah",
    5: "Egyptian General Authority of Survey",
    7: "Institute of Geophysics, University of Tehran",
    8: "Gulf Region",
    9: "Kuwait",
    10: "Qatar",
    11: "Majlis Ugama Islam Singapura, Singapore",
    12: "Union Organization Islamic de France",
    13: "Diyanet İşleri Başkanlığı, Turkey",
    14: "Spiritual Administration of Muslims of Russia",
}

os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
