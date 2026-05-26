"""Per-user chat history in sqlite. Keeps last N turns per user.

Trade-off: simple, no migrations, single writer. Fine for a personal bot.
For multi-tenant — switch to postgres and add a TTL job.
"""

from __future__ import annotations

import time
from pathlib import Path

import aiosqlite


DB_PATH = Path(__file__).parent / "history.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    user_id INTEGER NOT NULL,
    ts      INTEGER NOT NULL,
    role    TEXT    NOT NULL,
    content TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_history_user_ts ON history(user_id, ts);
"""


async def init() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


async def append(user_id: int, role: str, content: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO history(user_id, ts, role, content) VALUES (?,?,?,?)",
            (user_id, int(time.time() * 1000), role, content),
        )
        await db.commit()


async def get_recent(user_id: int, limit: int = 40) -> list[dict]:
    """Return last `limit` messages in chronological order."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT role, content FROM history WHERE user_id=? "
            "ORDER BY ts DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cur.fetchall()
    return [{"role": r, "content": c} for r, c in reversed(rows)]


async def reset(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM history WHERE user_id=?", (user_id,))
        await db.commit()
