"""Telegram WebApp initData validation.

Spec: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def _data_check_string(parsed: list[tuple[str, str]]) -> str:
    pairs = [(k, v) for k, v in parsed if k != "hash"]
    pairs.sort(key=lambda kv: kv[0])
    return "\n".join(f"{k}={v}" for k, v in pairs)


def parse_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict | None:
    """Verify HMAC and return parsed user dict, or None on failure."""
    if not init_data:
        return None
    parsed = list(parse_qsl(init_data, keep_blank_values=True))
    data = dict(parsed)
    received_hash = data.get("hash")
    if not received_hash:
        return None

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    check_str = _data_check_string(parsed)
    calc_hash = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, received_hash):
        return None

    auth_date = int(data.get("auth_date", "0"))
    if auth_date and (time.time() - auth_date) > max_age_seconds:
        return None

    user_raw = data.get("user")
    if not user_raw:
        return None
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        return None
    return user
