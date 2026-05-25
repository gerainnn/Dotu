"""SQLite storage for users, balances, owned items, equipped cosmetics."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).resolve().parent.parent / "data.db"
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _lock, _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id      INTEGER PRIMARY KEY,
                username     TEXT,
                first_name   TEXT,
                photo_url    TEXT,
                balance      INTEGER NOT NULL DEFAULT 2500,
                hands_played INTEGER NOT NULL DEFAULT 0,
                hands_won    INTEGER NOT NULL DEFAULT 0,
                created_at   INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            );
            CREATE TABLE IF NOT EXISTS owned_items (
                user_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                PRIMARY KEY (user_id, item_id)
            );
            CREATE TABLE IF NOT EXISTS equipped (
                user_id  INTEGER NOT NULL,
                category TEXT NOT NULL,
                item_id  TEXT NOT NULL,
                PRIMARY KEY (user_id, category)
            );
            """
        )


def get_or_create_user(
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    photo_url: Optional[str] = None,
) -> dict:
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            c.execute(
                "INSERT INTO users (user_id, username, first_name, photo_url) VALUES (?, ?, ?, ?)",
                (user_id, username, first_name, photo_url),
            )
            # default equipped cosmetics
            for category, item_id in (
                ("card_back", "back_classic"),
                ("chip_style", "chip_gold"),
                ("table_felt", "felt_emerald"),
            ):
                c.execute(
                    "INSERT OR IGNORE INTO equipped (user_id, category, item_id) VALUES (?, ?, ?)",
                    (user_id, category, item_id),
                )
            for item_id in ("back_classic", "chip_gold", "felt_emerald"):
                c.execute(
                    "INSERT OR IGNORE INTO owned_items (user_id, item_id) VALUES (?, ?)",
                    (user_id, item_id),
                )
            row = c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        else:
            # update profile bits if changed
            c.execute(
                "UPDATE users SET username = COALESCE(?, username), "
                "first_name = COALESCE(?, first_name), photo_url = COALESCE(?, photo_url) "
                "WHERE user_id = ?",
                (username, first_name, photo_url, user_id),
            )
        return dict(row)


def get_user(user_id: int) -> Optional[dict]:
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def adjust_balance(user_id: int, delta: int) -> int:
    with _lock, _conn() as c:
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id))
        row = c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row["balance"]


def record_hand(user_id: int, won: bool) -> None:
    with _lock, _conn() as c:
        c.execute(
            "UPDATE users SET hands_played = hands_played + 1, "
            "hands_won = hands_won + ? WHERE user_id = ?",
            (1 if won else 0, user_id),
        )


def list_owned(user_id: int) -> list[str]:
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT item_id FROM owned_items WHERE user_id = ?", (user_id,)
        ).fetchall()
        return [r["item_id"] for r in rows]


def buy_item(user_id: int, item_id: str, price: int) -> tuple[bool, str, int]:
    with _lock, _conn() as c:
        owned = c.execute(
            "SELECT 1 FROM owned_items WHERE user_id = ? AND item_id = ?",
            (user_id, item_id),
        ).fetchone()
        if owned:
            row = c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return False, "already_owned", row["balance"]
        row = c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row or row["balance"] < price:
            return False, "insufficient_funds", row["balance"] if row else 0
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
        c.execute(
            "INSERT INTO owned_items (user_id, item_id) VALUES (?, ?)",
            (user_id, item_id),
        )
        new_row = c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return True, "ok", new_row["balance"]


def equip_item(user_id: int, category: str, item_id: str) -> bool:
    with _lock, _conn() as c:
        owned = c.execute(
            "SELECT 1 FROM owned_items WHERE user_id = ? AND item_id = ?",
            (user_id, item_id),
        ).fetchone()
        if not owned:
            return False
        c.execute(
            "INSERT INTO equipped (user_id, category, item_id) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, category) DO UPDATE SET item_id = excluded.item_id",
            (user_id, category, item_id),
        )
        return True


def list_equipped(user_id: int) -> dict[str, str]:
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT category, item_id FROM equipped WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {r["category"]: r["item_id"] for r in rows}
