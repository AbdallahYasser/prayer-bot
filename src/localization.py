"""
Localization strings for English and Arabic.
Usage: t(lang, "key") or t(lang, "key").format(prayer="Fajr", time="04:32")
"""

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # Onboarding
        "private_bot": "🔒 This bot is private.",
        "welcome": (
            "🕌 <b>Welcome to Prayer Bot!</b>\n\n"
            "I'll remind you of the 5 daily prayers and help you track your progress.\n\n"
            "First, let me know your location to calculate accurate prayer times."
        ),
        "ask_location": (
            "📍 Please share your location or type your city and country.\n\n"
            "<i>Examples: Cairo Egypt · Alexandria Egypt · Dubai UAE</i>\n\n"
            "Sharing your GPS location gives the most accurate times."
        ),
        "location_set": (
            "✅ Location set! Here are your prayer times for today:\n\n{today_times}\n\n"
            "I'll remind you at each prayer time. May Allah accept your prayers. 🤲"
        ),
        "location_invalid": "❌ Couldn't find prayer times for that location. Try typing it differently, e.g. <i>Cairo Egypt</i>",
        "location_updated": "✅ Location updated! Reminders rescheduled.",
        "setlocation_prompt": "Send your location or type city and country (e.g. <i>Alexandria Egypt</i>):",

        # Prayer notification
        "prayer_time": "🕌 It's <b>{prayer}</b> time! ({time})",
        "prayer_time_ar_name": "🕌 حان وقت <b>{prayer}</b>! ({time})",

        # Prayer ask
        "did_you_pray": "🤲 Did you pray <b>{prayer}</b>?",
        "did_you_pray_sobh": "🌅 Fajr time has passed (sun has risen).\nDid you pray <b>Sobh</b> (make-up)? 🤲",
        "friday_prayer_ask": "🕌 Friday prayer — which did you attend?",
        "prayer_confirmed": "✅ <b>{prayer}</b> logged. Alhamdulillah! 🌟",
        "prayer_confirmed_qadaa": "✅ <b>Sobh</b> (make-up) logged. Alhamdulillah! 🌟",
        "prayer_confirmed_jumuah": "✅ <b>Jumu'ah</b> logged. Alhamdulillah! 🌟",
        "reminder_continuing": "We'll remind you again in {minutes} min.",

        # /today
        "today_header": "📅 <b>Today's Prayers</b> — {date}\n\n",
        "today_row": "{icon} <b>{prayer:<8}</b> {time}\n",
        "no_location": "⚠️ No location set. Use /setlocation to get started.",
        "status_prayed": "✅",
        "status_pending": "⏳",
        "status_missed": "❌",

        # /progress
        "progress_header": "📊 <b>{month_name} {year}</b>\n\n",
        "progress_legend": "\n🟩 5/5  🟦 4/5  🟨 3/5  🟧 2/5  🟫 1/5  🟥 0/5  ⬜ upcoming",

        # /stats
        "stats_header": "📈 <b>Your Prayer Stats</b>\n\n",
        "stats_streak": "🔥 Current streak: <b>{n} day(s)</b>\n",
        "stats_best": "🏆 Best streak: <b>{n} day(s)</b>\n",
        "stats_week": "📅 This week: <b>{pct}%</b> ({prayed}/{total})\n",
        "stats_month": "🗓 This month: <b>{pct}%</b> ({prayed}/{total})\n",
        "stats_total": "🕌 All time: <b>{total} prayers</b> logged\n",
        "stats_none": "No prayer data yet. Start praying and I'll track your progress! 🤲",

        # /settings
        "settings_header": "⚙️ <b>Settings</b>\n\nCurrent settings:",
        "settings_lang": "🌐 Language",
        "settings_method": "🔢 Calculation Method",
        "settings_reminders": "🔔 Reminders",
        "settings_on": "On ✅",
        "settings_off": "Off ❌",
        "settings_isha_window": "⏰ Isha Window",
        "settings_interval": "🔁 Repeat Every",
        "settings_saved": "✅ Settings saved.",
        "settings_method_prompt": "Choose a calculation method:",
        "settings_lang_prompt": "Choose your language:",
        "settings_isha_prompt": "When should Isha reminders stop?",
        "settings_interval_prompt": "How often should I remind you?",

        # /pause /resume
        "paused": "⏸ Reminders paused. Use /resume to turn them back on.",
        "resumed": "▶️ Reminders resumed. Here are your remaining prayers today:\n\n{today_times}",

        # /help
        "help": (
            "🕌 <b>Prayer Bot Commands</b>\n\n"
            "/today — Today's prayer times and status\n"
            "/progress — Monthly prayer calendar\n"
            "/stats — Streaks and percentages\n"
            "/setlocation — Update your location\n"
            "/settings — Language, calculation method, reminders\n"
            "/pause — Pause all reminders\n"
            "/resume — Resume reminders\n"
            "/help — This message"
        ),
    },

    "ar": {
        # Onboarding
        "private_bot": "🔒 هذا البوت خاص.",
        "welcome": (
            "🕌 <b>أهلاً بك في بوت الصلاة!</b>\n\n"
            "سأذكّرك بمواقيت الصلوات الخمس ويساعدك على متابعة تقدّمك.\n\n"
            "أولاً، أخبرني بموقعك لحساب أوقات الصلاة الدقيقة."
        ),
        "ask_location": (
            "📍 شارك موقعك أو اكتب مدينتك والبلد.\n\n"
            "<i>أمثلة: القاهرة مصر · الإسكندرية مصر · دبي الإمارات</i>\n\n"
            "مشاركة موقع GPS تعطي أدق الأوقات."
        ),
        "location_set": (
            "✅ تم تحديد الموقع! إليك أوقات صلواتك اليوم:\n\n{today_times}\n\n"
            "سأذكّرك عند كل وقت صلاة. تقبّل الله صلاتك. 🤲"
        ),
        "location_invalid": "❌ لم أتمكن من العثور على أوقات الصلاة لهذا الموقع. حاول كتابته بشكل مختلف، مثلاً: <i>القاهرة مصر</i>",
        "location_updated": "✅ تم تحديث الموقع! تم إعادة جدولة التنبيهات.",
        "setlocation_prompt": "أرسل موقعك أو اكتب المدينة والبلد (مثلاً: <i>الإسكندرية مصر</i>):",

        # Prayer notification
        "prayer_time": "🕌 حان وقت صلاة <b>{prayer}</b>! ({time})",
        "prayer_time_ar_name": "🕌 حان وقت صلاة <b>{prayer}</b>! ({time})",

        # Prayer ask
        "did_you_pray": "🤲 هل صلّيت <b>{prayer}</b>؟",
        "did_you_pray_sobh": "🌅 انتهى وقت الفجر (الشمس أشرقت).\nهل صلّيت <b>الصبح</b> (قضاء)؟ 🤲",
        "friday_prayer_ask": "🕌 صلاة الجمعة — أيهما أدّيت؟",
        "prayer_confirmed": "✅ تم تسجيل صلاة <b>{prayer}</b>. الحمد لله! 🌟",
        "prayer_confirmed_qadaa": "✅ تم تسجيل <b>الصبح</b> قضاءً. الحمد لله! 🌟",
        "prayer_confirmed_jumuah": "✅ تم تسجيل <b>الجمعة</b>. الحمد لله! 🌟",
        "reminder_continuing": "سنذكّرك مرة أخرى بعد {minutes} دقيقة.",

        # /today
        "today_header": "📅 <b>صلوات اليوم</b> — {date}\n\n",
        "today_row": "{icon} <b>{prayer:<8}</b> {time}\n",
        "no_location": "⚠️ لم يتم تحديد الموقع. استخدم /setlocation للبدء.",
        "status_prayed": "✅",
        "status_pending": "⏳",
        "status_missed": "❌",

        # /progress
        "progress_header": "📊 <b>{month_name} {year}</b>\n\n",
        "progress_legend": "\n🟩 5/5  🟦 4/5  🟨 3/5  🟧 2/5  🟫 1/5  🟥 0/5  ⬜ قادم",

        # /stats
        "stats_header": "📈 <b>إحصائيات صلاتك</b>\n\n",
        "stats_streak": "🔥 السلسلة الحالية: <b>{n} يوم</b>\n",
        "stats_best": "🏆 أفضل سلسلة: <b>{n} يوم</b>\n",
        "stats_week": "📅 هذا الأسبوع: <b>{pct}%</b> ({prayed}/{total})\n",
        "stats_month": "🗓 هذا الشهر: <b>{pct}%</b> ({prayed}/{total})\n",
        "stats_total": "🕌 إجمالي: <b>{total} صلاة</b>\n",
        "stats_none": "لا توجد بيانات صلاة حتى الآن. ابدأ الصلاة وسأتابع تقدّمك! 🤲",

        # /settings
        "settings_header": "⚙️ <b>الإعدادات</b>\n\nالإعدادات الحالية:",
        "settings_lang": "🌐 اللغة",
        "settings_method": "🔢 طريقة الحساب",
        "settings_reminders": "🔔 التنبيهات",
        "settings_on": "مفعّلة ✅",
        "settings_off": "متوقفة ❌",
        "settings_isha_window": "⏰ وقت العشاء",
        "settings_interval": "🔁 تكرار كل",
        "settings_saved": "✅ تم حفظ الإعدادات.",
        "settings_method_prompt": "اختر طريقة حساب المواقيت:",
        "settings_lang_prompt": "اختر لغتك:",
        "settings_isha_prompt": "متى تتوقف تذكيرات العشاء؟",
        "settings_interval_prompt": "كم مرة تريد أن أذكّرك؟",

        # /pause /resume
        "paused": "⏸ تم إيقاف التنبيهات. استخدم /resume لإعادة تفعيلها.",
        "resumed": "▶️ تم استئناف التنبيهات. إليك الصلوات المتبقية اليوم:\n\n{today_times}",

        # /help
        "help": (
            "🕌 <b>أوامر بوت الصلاة</b>\n\n"
            "/today — أوقات الصلاة وحالتها اليوم\n"
            "/progress — تقويم الصلاة الشهري\n"
            "/stats — السلاسل والنسب المئوية\n"
            "/setlocation — تحديث موقعك\n"
            "/settings — اللغة وطريقة الحساب والتنبيهات\n"
            "/pause — إيقاف التنبيهات\n"
            "/resume — استئناف التنبيهات\n"
            "/help — هذه الرسالة"
        ),
    },
}


def t(lang: str, key: str) -> str:
    """Return localized string, falling back to English if key missing."""
    return STRINGS.get(lang, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)


def prayer_name(prayer: str, lang: str) -> str:
    """Return localized prayer name."""
    from src.config import PRAYER_NAMES
    return PRAYER_NAMES.get(prayer, {}).get(lang, prayer)
