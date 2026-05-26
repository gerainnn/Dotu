"""Standalone Telegram bot that talks in Dod persona via an OpenAI-compatible LLM.

Run:
    python -m dod_bot.bot

Env (see dod_bot/.env.example):
    TG_BOT_TOKEN     — Telegram bot token from @BotFather
    LLM_API_KEY      — API key for the chosen LLM provider
    LLM_BASE_URL     — OpenAI-compatible endpoint (default: OpenAI)
    LLM_MODEL        — model name (default: gpt-4o-mini)
    LLM_TEMPERATURE  — sampling temperature (default: 0.85)
    LLM_MAX_TOKENS   — optional cap on response tokens
    HISTORY_LIMIT    — how many last turns to keep in context (default: 40)
    ALLOWED_USERS    — comma-separated TG user ids; empty = open to anyone
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

from dod_bot import storage
from dod_bot.llm import chat
from dod_bot.persona import DOD_SYSTEM_PROMPT


# load .env from dod_bot/ first, then project root as fallback
load_dotenv(Path(__file__).parent / ".env")
load_dotenv()  # project root .env if dod_bot/.env didn't set the vars

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("dod_bot")


TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
if not TG_BOT_TOKEN:
    raise SystemExit("TG_BOT_TOKEN is missing. Copy dod_bot/.env.example to dod_bot/.env")

ALLOWED_USERS: set[int] = {
    int(x) for x in os.getenv("ALLOWED_USERS", "").split(",") if x.strip().isdigit()
}
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "40"))

bot = Bot(token=TG_BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
dp = Dispatcher()


def _is_allowed(uid: int) -> bool:
    return not ALLOWED_USERS or uid in ALLOWED_USERS


def _split_for_telegram(text: str, limit: int = 4000) -> list[str]:
    """TG message hard limit is 4096 chars. Split on paragraph/line breaks
    when possible, fall back to hard cut. Keep order."""
    out: list[str] = []
    while text:
        if len(text) <= limit:
            out.append(text)
            break
        cut = text.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        out.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return out


@dp.message(CommandStart())
async def on_start(msg: Message) -> None:
    if not _is_allowed(msg.from_user.id):
        return
    await storage.reset(msg.from_user.id)
    await msg.answer(
        "Дод на связи. Пиво открыто, лаба гудит. Что у тебя.\n\n"
        "Команды: /reset — стереть историю, /whoami — твой TG id."
    )


@dp.message(Command("reset"))
async def on_reset(msg: Message) -> None:
    if not _is_allowed(msg.from_user.id):
        return
    await storage.reset(msg.from_user.id)
    await msg.answer("История стёрта. Заново.")


@dp.message(Command("whoami"))
async def on_whoami(msg: Message) -> None:
    # useful when filling ALLOWED_USERS
    await msg.answer(f"id: {msg.from_user.id}")


@dp.message(F.text)
async def on_text(msg: Message) -> None:
    uid = msg.from_user.id
    if not _is_allowed(uid):
        return

    user_text = msg.text or ""
    if not user_text.strip():
        return

    await bot.send_chat_action(msg.chat.id, ChatAction.TYPING)

    history = await storage.get_recent(uid, limit=HISTORY_LIMIT)
    payload = (
        [{"role": "system", "content": DOD_SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": user_text}]
    )

    try:
        reply = await chat(payload)
    except Exception as e:  # noqa: BLE001 — surface any provider error to chat
        log.exception("LLM call failed")
        await msg.answer(f"Хуйня с апи: {type(e).__name__}: {e}")
        return

    if not reply:
        await msg.answer("Пустой ответ от модели. Скорее всего сработал контент-фильтр провайдера. Попробуй другой провайдер/модель.")
        return

    # persist only after successful LLM round-trip
    await storage.append(uid, "user", user_text)
    await storage.append(uid, "assistant", reply)

    for chunk in _split_for_telegram(reply):
        await msg.answer(chunk)


async def main() -> None:
    await storage.init()
    log.info("Dod bot starting. Allowed users: %s", ALLOWED_USERS or "ANY")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
