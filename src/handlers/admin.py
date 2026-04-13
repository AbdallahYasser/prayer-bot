"""
Admin commands for managing the bot whitelist.
Only the user whose ID matches ADMIN_USER_ID (env var) can use these.

Commands:
  /adduser <user_id>    — add a user to the whitelist
  /removeuser <user_id> — remove a user from the whitelist
  /listusers            — show all whitelisted users
"""

import aiosqlite
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.config import DB_PATH, ADMIN_USER_ID
from src import state

router = Router()


def _is_admin(user_id: int) -> bool:
    return ADMIN_USER_ID is not None and user_id == ADMIN_USER_ID


@router.message(Command("adduser"))
async def cmd_adduser(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Usage: /adduser <user_id>")
        return

    uid = int(parts[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO allowed_users (user_id, added_by) VALUES (?, ?)",
            (uid, message.from_user.id),
        )
        await db.commit()

    state.allowed_users.add(uid)
    await message.answer(f"✅ User {uid} added to whitelist.")


@router.message(Command("removeuser"))
async def cmd_removeuser(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Usage: /removeuser <user_id>")
        return

    uid = int(parts[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM allowed_users WHERE user_id = ?",
            (uid,),
        )
        await db.commit()

    state.allowed_users.discard(uid)
    await message.answer(f"✅ User {uid} removed from whitelist.")


@router.message(Command("listusers"))
async def cmd_listusers(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    if not state.allowed_users:
        await message.answer("Whitelist is empty — bot is open to everyone.")
        return

    lines = [f"• {uid}" for uid in sorted(state.allowed_users)]
    await message.answer("👥 Allowed users:\n" + "\n".join(lines))
