"""Entry point: runs the FastAPI HTTP server and the aiogram bot together.

Both are started inside one asyncio loop. Stop with Ctrl+C.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.auth import parse_init_data
from app.poker import GameManager, serialize_game
from app.shop import CATALOGUE, CATALOGUE_BY_ID

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dotu")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
DEV_MODE = os.getenv("DEV_MODE", "0") == "1"

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN is missing. Copy .env.example to .env and fill it in.")

WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"
db.init_db()

# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def _open_keyboard() -> InlineKeyboardMarkup:
    if WEBAPP_URL:
        btn = InlineKeyboardButton(text="Open Dotu Poker", web_app=WebAppInfo(url=WEBAPP_URL))
    else:
        btn = InlineKeyboardButton(text="Set WEBAPP_URL", url="https://core.telegram.org/bots/webapps")
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])


@dp.message(CommandStart())
async def on_start(msg: Message) -> None:
    user = msg.from_user
    db.get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
    )
    text = (
        f"<b>Dotu Poker</b>\n\n"
        f"Hi, {user.first_name or 'player'}. Texas Hold'em vs three bots,\n"
        f"virtual chips, and a small shop for cosmetics.\n\n"
        f"Tap the button below to play."
    )
    await msg.answer(text, reply_markup=_open_keyboard())


@dp.message(F.text == "/play")
async def on_play(msg: Message) -> None:
    await msg.answer("Open the table:", reply_markup=_open_keyboard())


@dp.message(F.text == "/balance")
async def on_balance(msg: Message) -> None:
    user = db.get_or_create_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    await msg.answer(f"Balance: <b>{user['balance']}</b> chips")


# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------

games = GameManager()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # start polling alongside HTTP
    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    log.info("Bot polling started.")
    try:
        yield
    finally:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()


api = FastAPI(lifespan=lifespan, title="Dotu Poker")


def _auth_user(init_data: str | None, dev_user: str | None) -> dict:
    if init_data:
        u = parse_init_data(init_data, BOT_TOKEN)
        if u:
            return u
    if DEV_MODE and dev_user:
        try:
            uid = int(dev_user)
        except ValueError:
            raise HTTPException(401, "bad dev user")
        return {"id": uid, "first_name": f"Dev{uid}", "username": f"dev{uid}"}
    raise HTTPException(401, "unauthorized")


def _profile_payload(user_id: int) -> dict:
    user = db.get_user(user_id)
    owned = set(db.list_owned(user_id))
    equipped = db.list_equipped(user_id)
    win_rate = (user["hands_won"] / user["hands_played"]) if user["hands_played"] else 0
    level = 1 + user["hands_played"] // 10
    return {
        "user": {
            "id": user["user_id"],
            "username": user["username"],
            "first_name": user["first_name"],
            "photo_url": user["photo_url"],
            "balance": user["balance"],
            "hands_played": user["hands_played"],
            "hands_won": user["hands_won"],
            "win_rate": round(win_rate, 3),
            "level": level,
        },
        "owned": sorted(owned),
        "equipped": equipped,
    }


@api.post("/api/profile")
async def profile(request: Request,
                  x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
                  x_dev_user: str | None = Header(default=None, alias="X-Dev-User")):
    u = _auth_user(x_init_data, x_dev_user)
    db.get_or_create_user(
        user_id=u["id"],
        username=u.get("username"),
        first_name=u.get("first_name"),
        photo_url=u.get("photo_url"),
    )
    return _profile_payload(u["id"])


@api.post("/api/shop")
async def shop(x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
               x_dev_user: str | None = Header(default=None, alias="X-Dev-User")):
    u = _auth_user(x_init_data, x_dev_user)
    db.get_or_create_user(u["id"], u.get("username"), u.get("first_name"))
    owned = set(db.list_owned(u["id"]))
    equipped = db.list_equipped(u["id"])
    items = []
    for it in CATALOGUE:
        items.append({
            **it,
            "owned": it["id"] in owned,
            "equipped": equipped.get(it["category"]) == it["id"],
        })
    return {"items": items}


@api.post("/api/buy")
async def buy(payload: dict,
              x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
              x_dev_user: str | None = Header(default=None, alias="X-Dev-User")):
    u = _auth_user(x_init_data, x_dev_user)
    item_id = payload.get("item_id")
    if item_id not in CATALOGUE_BY_ID:
        raise HTTPException(400, "bad item")
    item = CATALOGUE_BY_ID[item_id]
    ok, status, balance = db.buy_item(u["id"], item_id, item["price"])
    if not ok:
        return JSONResponse({"ok": False, "error": status, "balance": balance}, status_code=400)
    return {"ok": True, "balance": balance}


@api.post("/api/equip")
async def equip(payload: dict,
                x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
                x_dev_user: str | None = Header(default=None, alias="X-Dev-User")):
    u = _auth_user(x_init_data, x_dev_user)
    item_id = payload.get("item_id")
    if item_id not in CATALOGUE_BY_ID:
        raise HTTPException(400, "bad item")
    category = CATALOGUE_BY_ID[item_id]["category"]
    if not db.equip_item(u["id"], category, item_id):
        raise HTTPException(400, "not owned")
    return {"ok": True, "equipped": db.list_equipped(u["id"])}


# ---- poker ----

BUY_IN = 1000
MIN_BALANCE = 200  # required to sit down


@api.post("/api/poker/new")
async def poker_new(x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
                    x_dev_user: str | None = Header(default=None, alias="X-Dev-User")):
    u = _auth_user(x_init_data, x_dev_user)
    user = db.get_or_create_user(u["id"], u.get("username"), u.get("first_name"))
    if user["balance"] < MIN_BALANCE:
        raise HTTPException(400, "Not enough chips. Minimum 200 to play.")
    name = (u.get("first_name") or u.get("username") or "You")[:14]
    g = games.new_hand(u["id"], name, buy_in=BUY_IN)
    return serialize_game(g, u["id"])


@api.post("/api/poker/state")
async def poker_state(x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
                      x_dev_user: str | None = Header(default=None, alias="X-Dev-User")):
    u = _auth_user(x_init_data, x_dev_user)
    g = games.get(u["id"])
    if not g:
        raise HTTPException(404, "no game")
    return serialize_game(g, u["id"])


@api.post("/api/poker/action")
async def poker_action(payload: dict,
                       x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
                       x_dev_user: str | None = Header(default=None, alias="X-Dev-User")):
    u = _auth_user(x_init_data, x_dev_user)
    g = games.get(u["id"])
    if not g:
        raise HTTPException(404, "no game")
    action = payload.get("action")
    amount = int(payload.get("amount", 0))
    if action not in ("fold", "check", "call", "raise", "allin"):
        raise HTTPException(400, "bad action")
    g = games.human_action(u["id"], action, amount)
    return serialize_game(g, u["id"])


@api.post("/api/poker/settle")
async def poker_settle(x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
                       x_dev_user: str | None = Header(default=None, alias="X-Dev-User")):
    """Apply hand result to the player's balance and stats. Idempotent per hand."""
    u = _auth_user(x_init_data, x_dev_user)
    g = games.get(u["id"])
    if not g or g.stage != "finished":
        raise HTTPException(400, "not finished")
    delta = g.delta
    won = delta > 0
    # mark settled by zeroing delta in the in-memory game
    if not getattr(g, "_settled", False):
        balance = db.adjust_balance(u["id"], delta)
        db.record_hand(u["id"], won=won)
        g._settled = True  # type: ignore[attr-defined]
    else:
        balance = db.get_user(u["id"])["balance"]
    return {"balance": balance, "delta": delta, "won": won}


# ---- static webapp ----

@api.get("/")
async def index() -> FileResponse:
    return FileResponse(WEBAPP_DIR / "index.html")


@api.get("/health")
async def health():
    return {"ok": True}


api.mount("/static", StaticFiles(directory=WEBAPP_DIR), name="static")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def main() -> None:
    config = uvicorn.Config(api, host=HOST, port=PORT, log_level="info")
    server = uvicorn.Server(config)
    asyncio.run(server.serve())


if __name__ == "__main__":
    main()
