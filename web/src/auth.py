"""
Telegram Login Widget verification + JWT session cookie.
"""
import hashlib
import hmac
import os
import time

from jose import JWTError, jwt
from fastapi import Cookie, HTTPException

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SECRET_KEY = os.getenv("SECRET_KEY", "changeme")
ALGORITHM = "HS256"
SESSION_DAYS = 30

_raw_allowed = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = {int(x.strip()) for x in _raw_allowed.split(",") if x.strip().isdigit()}


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
