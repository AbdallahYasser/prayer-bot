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
    "Fajr":    {"en": "Fajr",    "ar": "الفجر (الصبح)"},
    "Dhuhr":   {"en": "Dhuhr",   "ar": "الظهر"},
    "Asr":     {"en": "Asr",     "ar": "العصر"},
    "Maghrib": {"en": "Maghrib", "ar": "المغرب"},
    "Isha":    {"en": "Isha",    "ar": "العشاء"},
}

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
