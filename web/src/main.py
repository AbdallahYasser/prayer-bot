"""
Prayer Web — FastAPI backend.
Serves the static frontend and provides read-only API endpoints.
All endpoints require a valid session cookie (set by /api/auth/telegram).
"""
import datetime
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src import auth, db

app = FastAPI(docs_url=None, redoc_url=None)

STATIC_DIR = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/telegram")
async def telegram_auth(request: Request, response: Response):
    data = await request.json()

    if not auth.verify_telegram_hash(data):
        raise HTTPException(status_code=403, detail="Invalid Telegram auth")

    user_id = int(data["id"])

    if auth.ALLOWED_USERS and user_id not in auth.ALLOWED_USERS:
        raise HTTPException(status_code=403, detail="Access denied")

    token = auth.create_session_token(user_id)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=auth.SESSION_DAYS * 86400,
    )
    return {"ok": True, "first_name": data.get("first_name", "")}


@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Data endpoints — all require valid session cookie
# ---------------------------------------------------------------------------

@app.get("/api/me")
async def me(user_id: int = Depends(auth.get_current_user)):
    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found in bot database")

    tz_str = user.get("timezone") or "UTC"
    isha_window = user.get("isha_window") or "midnight"
    lang = user.get("language") or "en"
    isha_label = db.ISHA_WINDOW_LABELS.get(isha_window, {}).get(lang, isha_window)

    return {
        "user_id":          user_id,
        "first_name":       user.get("first_name") or "",
        "timezone":         tz_str,
        "language":         lang,
        "isha_window":      isha_window,
        "isha_label":       isha_label,
        "reminder_interval": user.get("reminder_interval") or 5,
    }


@app.get("/api/stats")
async def stats(user_id: int = Depends(auth.get_current_user)):
    user = await db.get_user(user_id)
    tz_str = (user or {}).get("timezone") or "UTC"
    return await db.get_stats(user_id, tz_str)


@app.get("/api/heatmap")
async def heatmap(year: int | None = None, user_id: int = Depends(auth.get_current_user)):
    user = await db.get_user(user_id)
    tz_str = (user or {}).get("timezone") or "UTC"

    import pytz
    try:
        tz = pytz.timezone(tz_str)
    except Exception:
        tz = pytz.UTC

    if year is None:
        year = datetime.datetime.now(tz).year

    rows = await db.get_yearly_log(user_id, year)
    return {"year": year, "days": rows}


@app.get("/api/month")
async def month(m: str | None = None, user_id: int = Depends(auth.get_current_user)):
    """m = 'YYYY-MM', defaults to current month."""
    user = await db.get_user(user_id)
    tz_str = (user or {}).get("timezone") or "UTC"

    import pytz
    try:
        tz = pytz.timezone(tz_str)
    except Exception:
        tz = pytz.UTC

    now = datetime.datetime.now(tz)
    if m:
        try:
            year, month_num = map(int, m.split("-"))
        except ValueError:
            raise HTTPException(status_code=400, detail="m must be YYYY-MM")
    else:
        year, month_num = now.year, now.month

    rows = await db.get_monthly_log(user_id, year, month_num)
    return {"month": f"{year:04d}-{month_num:02d}", "days": rows}


# ---------------------------------------------------------------------------
# Static frontend — mounted last so API routes take priority
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text()


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
