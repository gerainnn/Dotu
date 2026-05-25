"""End-to-end test of the HTTP API in DEV_MODE without starting the bot."""
import os
os.environ.setdefault("BOT_TOKEN", "12345:dev_token_for_tests_only_AAAAAAAAAAAAAAAA")
os.environ["DEV_MODE"] = "1"

import sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the FastAPI app but skip the lifespan (which starts polling).
import main
api = main.api

from contextlib import asynccontextmanager
@asynccontextmanager
async def _noop(app):
    yield
api.router.lifespan_context = _noop

from fastapi.testclient import TestClient

with TestClient(api) as c:
    H = {"X-Dev-User": "111"}

    r = c.post("/api/profile", headers=H); print("profile", r.status_code)
    assert r.status_code == 200, r.text
    profile = r.json(); print("  balance:", profile["user"]["balance"])

    r = c.post("/api/shop", headers=H); print("shop", r.status_code)
    assert r.status_code == 200
    items = r.json()["items"]
    print(f"  catalogue: {len(items)} items")

    # buy a chip skin
    chip = next(i for i in items if i["id"] == "chip_silver")
    r = c.post("/api/buy", headers=H, json={"item_id": chip["id"]})
    print("buy silver chips:", r.status_code, r.json())
    assert r.status_code == 200 and r.json()["ok"]

    # equip
    r = c.post("/api/equip", headers=H, json={"item_id": chip["id"]})
    print("equip:", r.status_code, r.json())
    assert r.status_code == 200

    # poker hand
    r = c.post("/api/poker/new", headers=H); print("new hand:", r.status_code)
    assert r.status_code == 200
    g = r.json()
    print("  stage:", g["stage"], "turn:", g["turn_seat"], "pot:", g["pot"])

    safety = 0
    while g["stage"] not in ("showdown", "finished"):
        if g["turn_seat"] == 0:
            me = g["players"][0]
            to_call = g["current_bet"] - me["bet"]
            action = "check" if to_call == 0 else "call"
            r = c.post("/api/poker/action", headers=H, json={"action": action})
            assert r.status_code == 200, r.text
            g = r.json()
        else:
            # bots already played; if loop, break
            break
        safety += 1
        if safety > 60: raise SystemExit("loop")
    print("final stage:", g["stage"], "delta:", g["delta"])
    print("winners:", [w["name"] + " " + w["hand"] for w in g["winners"]])

    r = c.post("/api/poker/settle", headers=H); print("settle:", r.status_code, r.json())

    # final profile
    r = c.post("/api/profile", headers=H)
    print("balance after:", r.json()["user"]["balance"], "hands:", r.json()["user"]["hands_played"])
print("ALL OK")
