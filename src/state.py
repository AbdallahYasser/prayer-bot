"""
Module-level in-memory state dicts.
All state here is lost on bot restart — this is intentional.
The scheduler re-creates jobs from DB on startup.
"""
import asyncio

# Key: f"{user_id}_{prayer}_{date_str}"  →  asyncio.Task (the 5-min repeat reminder loop)
active_reminder_tasks: dict[str, asyncio.Task] = {}

# Key: user_id  →  {"step": "awaiting_location" | "awaiting_city_text"}
onboarding_state: dict[int, dict] = {}

# Key: user_id  →  {"step": "awaiting_method" | ...}
settings_state: dict[int, dict] = {}

# Whitelist: user IDs allowed to use the bot. Empty set = bot is public.
# Loaded from the allowed_users DB table at startup; updated live by admin commands.
allowed_users: set[int] = set()
