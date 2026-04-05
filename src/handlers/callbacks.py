"""
Inline keyboard callback handlers.

Callback data formats (all < 64 bytes):
  pray:yes:{prayer}:{date_str}   — user confirms they prayed
  pray:no:{prayer}:{date_str}    — user says they didn't pray
  settings:lang:{lang}           — change language
  settings:method:{n}            — change calculation method
  settings:reminders:{0|1}       — toggle reminders
"""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from src import state
from src.localization import t, prayer_name
from src.config import ALLOWED_USERS, CALC_METHODS

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("pray:"))
async def handle_prayer_callback(cb: CallbackQuery) -> None:
    if ALLOWED_USERS and cb.from_user.id not in ALLOWED_USERS:
        await cb.answer()
        return

    parts = cb.data.split(":")
    # pray : yes/no : prayer : date_str
    if len(parts) != 4:
        await cb.answer()
        return

    _, answer, prayer, date_str = parts
    user_id = cb.from_user.id
    task_key = f"{user_id}_{prayer}_{date_str}"

    from src.db import users as db_users
    from src.db import prayer_log as db_log

    user = await db_users.get_user(user_id)
    lang = user.get("language", "en") if user else "en"
    p_name = prayer_name(prayer, lang)

    if answer == "yes":
        # Cancel the repeat loop task
        task = state.active_reminder_tasks.pop(task_key, None)
        if task and not task.done():
            task.cancel()

        await db_log.update_status(user_id, date_str, prayer, "prayed")

        # Edit the message to show confirmation
        try:
            await cb.message.edit_text(t(lang, "prayer_confirmed").format(prayer=p_name))
        except Exception:
            pass  # message may be too old to edit

        await cb.answer()

    elif answer == "no":
        # Don't cancel the task — loop continues every 5 min
        await cb.answer(t(lang, "reminder_continuing"), show_alert=False)

    else:
        await cb.answer()


@router.callback_query(F.data.startswith("settings:"))
async def handle_settings_callback(cb: CallbackQuery) -> None:
    if ALLOWED_USERS and cb.from_user.id not in ALLOWED_USERS:
        await cb.answer()
        return

    parts = cb.data.split(":")
    user_id = cb.from_user.id
    setting = parts[1] if len(parts) > 1 else ""

    from src.db import users as db_users
    user = await db_users.get_user(user_id)
    lang = user.get("language", "en") if user else "en"

    if setting == "lang":
        new_lang = parts[2]
        await db_users.update_language(user_id, new_lang)
        await cb.answer(t(new_lang, "settings_saved"), show_alert=False)
        # Update the settings menu in the message
        try:
            await cb.message.edit_text(
                _build_settings_text(user, language_override=new_lang),
                reply_markup=_build_settings_keyboard(user, language_override=new_lang),
            )
        except Exception:
            pass

    elif setting == "method":
        new_method = int(parts[2])
        await db_users.update_calc_method(user_id, new_method)
        # Invalidate prayer times cache for today by re-fetching
        from src import scheduler as sched
        await sched.reschedule_user_today(user_id)
        await cb.answer(t(lang, "settings_saved"), show_alert=False)
        updated_user = await db_users.get_user(user_id)
        try:
            await cb.message.edit_text(
                _build_settings_text(updated_user),
                reply_markup=_build_settings_keyboard(updated_user),
            )
        except Exception:
            pass

    elif setting == "reminders":
        reminders_on = parts[2] == "1"
        await db_users.update_reminders(user_id, reminders_on)

        if reminders_on:
            from src import scheduler as sched
            await sched.reschedule_user_today(user_id)
        else:
            # Cancel all active reminder tasks for this user
            keys_to_cancel = [k for k in state.active_reminder_tasks if k.startswith(f"{user_id}_")]
            for k in keys_to_cancel:
                task = state.active_reminder_tasks.pop(k, None)
                if task and not task.done():
                    task.cancel()

        await cb.answer(t(lang, "settings_saved"), show_alert=False)
        updated_user = await db_users.get_user(user_id)
        try:
            await cb.message.edit_text(
                _build_settings_text(updated_user),
                reply_markup=_build_settings_keyboard(updated_user),
            )
        except Exception:
            pass

    elif setting == "show_methods":
        # Show calculation method selection submenu
        try:
            await cb.message.edit_text(
                t(lang, "settings_method_prompt"),
                reply_markup=_build_method_keyboard(lang),
            )
        except Exception:
            pass
        await cb.answer()

    elif setting == "show_langs":
        try:
            await cb.message.edit_text(
                t(lang, "settings_lang_prompt"),
                reply_markup=_build_lang_keyboard(),
            )
        except Exception:
            pass
        await cb.answer()

    else:
        await cb.answer()


# ---------------------------------------------------------------------------
# Settings UI builders
# ---------------------------------------------------------------------------

def _build_settings_text(user: dict, language_override: str | None = None) -> str:
    lang = language_override or user.get("language", "en")
    reminders_on = user.get("reminders_on", 1)
    method_id = user.get("calc_method", 5)
    method_name = CALC_METHODS.get(method_id, str(method_id))

    reminders_label = t(lang, "settings_on") if reminders_on else t(lang, "settings_off")
    lang_label = "العربية 🇪🇬" if lang == "ar" else "English 🇬🇧"

    return (
        f"{t(lang, 'settings_header')}\n\n"
        f"🌐 {t(lang, 'settings_lang')}: <b>{lang_label}</b>\n"
        f"🔢 {t(lang, 'settings_method')}: <b>{method_name}</b>\n"
        f"🔔 {t(lang, 'settings_reminders')}: <b>{reminders_label}</b>"
    )


def _build_settings_keyboard(user: dict, language_override: str | None = None):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    lang = language_override or user.get("language", "en")
    reminders_on = user.get("reminders_on", 1)

    toggle_label = (t(lang, "settings_off") + " 🔕") if reminders_on else (t(lang, "settings_on") + " 🔔")
    toggle_val = "0" if reminders_on else "1"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🌐 {t(lang, 'settings_lang')}", callback_data="settings:show_langs")],
        [InlineKeyboardButton(text=f"🔢 {t(lang, 'settings_method')}", callback_data="settings:show_methods")],
        [InlineKeyboardButton(text=toggle_label, callback_data=f"settings:reminders:{toggle_val}")],
    ])


def _build_method_keyboard(lang: str):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    # Show the most common methods
    shown = [5, 4, 2, 3, 1, 8, 9, 10]
    buttons = []
    row = []
    for i, method_id in enumerate(shown):
        name = CALC_METHODS.get(method_id, str(method_id))
        # Abbreviate long names
        short = name.split(",")[0][:30]
        row.append(InlineKeyboardButton(
            text=f"{method_id}. {short}",
            callback_data=f"settings:method:{method_id}",
        ))
        if len(row) == 1:  # one per row (names are long)
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_lang_keyboard():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="English 🇬🇧", callback_data="settings:lang:en"),
        InlineKeyboardButton(text="العربية 🇪🇬", callback_data="settings:lang:ar"),
    ]])
