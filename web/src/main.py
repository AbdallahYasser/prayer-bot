"""
Prayer Web — FastAPI backend.
Serves the static frontend and provides read-only API endpoints.
All endpoints require a valid session cookie (set by /api/auth/telegram).
Notifications: pre/post deploy commands send Telegram messages via the prayer bot.
"""
import datetime
import os
import time
from pathlib import Path

# Set once when the container starts — rotates on every Coolify deploy.
# Injected into asset URLs to bust Cloudflare's edge cache automatically.
_DEPLOY_TS = str(int(time.time()))

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

    if not await auth.is_user_allowed(user_id):
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
    calc_method = user.get("calc_method") or 5
    calc_method_name = db.CALC_METHODS.get(calc_method, str(calc_method))

    return {
        "user_id":           user_id,
        "username":          user.get("username") or "",
        "first_name":        user.get("first_name") or "",
        "city":              user.get("city") or "",
        "country":           user.get("country") or "",
        "timezone":          tz_str,
        "language":          lang,
        "calc_method":       calc_method,
        "calc_method_name":  calc_method_name,
        "reminders_on":      bool(user.get("reminders_on", 1)),
        "isha_window":       isha_window,
        "isha_label":        isha_label,
        "reminder_interval": user.get("reminder_interval") or 5,
        "created_at":        user.get("created_at") or "",
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


@app.get("/api/config")
async def config():
    """Public — bot config for the login widget."""
    return {"bot_username": os.getenv("BOT_USERNAME", "islamic_prayer_reminder_bot")}


@app.get("/api/today")
async def today(user_id: int = Depends(auth.get_current_user)):
    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found in bot database")

    tz_str = (user or {}).get("timezone") or "UTC"
    import pytz
    try:
        tz = pytz.timezone(tz_str)
    except Exception:
        tz = pytz.UTC

    now = datetime.datetime.now(tz)
    today_str = now.strftime("%Y-%m-%d")
    today_display = now.strftime("%A, %d %B %Y")

    times = await db.get_prayer_times(user_id, today_str)
    log   = await db.get_daily_log(user_id, today_str)

    prayers = []
    for slot in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
        entry = log.get(slot) or {"name": slot, "status": "pending"}
        prayers.append({
            "name":   entry["name"],     # actual stored name: "Sobh", "Jumu'ah", etc.
            "time":   (times or {}).get(slot),
            "status": entry["status"],
        })

    return {
        "date":         today_str,
        "date_display": today_display,
        "prayers":      prayers,
        "has_times":    times is not None,
    }


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
    content = (STATIC_DIR / "index.html").read_text()
    # Inject deploy timestamp into local asset URLs so Cloudflare sees a new
    # cache key on every deploy and is forced to fetch from origin.
    content = content.replace('src="./app.js"',      f'src="./app.js?v={_DEPLOY_TS}"')
    content = content.replace('href="./style.css"',  f'href="./style.css?v={_DEPLOY_TS}"')
    return HTMLResponse(content=content, headers={"Cache-Control": "no-store"})


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


app.mount("/", NoCacheStaticFiles(directory=str(STATIC_DIR), html=True), name="static")
