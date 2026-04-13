"""
Telegram Login Widget verification + JWT session cookie.
"""
import hashlib
import hmac
import os
import time

import aiosqlite
from jose import JWTError, jwt
from fastapi import Cookie, HTTPException

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SECRET_KEY = os.getenv("SECRET_KEY", "changeme")
ALGORITHM = "HS256"
SESSION_DAYS = 30


def verify_telegram_hash(data: dict) -> bool:
    """
    Verify the hash sent by Telegram Login Widget.
    https://core.telegram.org/widgets/login#checking-authorization
    """
    received_hash = data.get("hash", "")
    check_data = {k: v for k, v in data.items() if k != "hash"}
    data_check_string = "\n".join(sorted(f"{k}={v}" for k, v in check_data.items()))
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if expected != received_hash:
        return False
    # Reject auth data older than 24 hours
    auth_date = int(data.get("auth_date", 0))
    if time.time() - auth_date > 86400:
        return False
    return True


def create_session_token(user_id: int) -> str:
    exp = int(time.time()) + SESSION_DAYS * 86400
    return jwt.encode({"user_id": user_id, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


async def is_user_allowed(user_id: int) -> bool:
    """Return True if the whitelist is empty (bot is public) or user_id is in it."""
    from web.src.db import _db_uri
    async with aiosqlite.connect(_db_uri(), uri=True) as db:
        async with db.execute("SELECT COUNT(*) FROM allowed_users") as cur:
            total = (await cur.fetchone())[0]
        if total == 0:
            return True  # empty whitelist = public bot
        async with db.execute(
            "SELECT 1 FROM allowed_users WHERE user_id = ? LIMIT 1", (user_id,)
        ) as cur:
            return await cur.fetchone() is not None


def get_current_user(session: str | None = Cookie(default=None)) -> int:
    """FastAPI dependency — returns user_id from session cookie or raises 401."""
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(session, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid session")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid session")
