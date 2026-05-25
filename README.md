# Dotu Poker

A minimalist Telegram **Mini App** for Texas Hold'em against three AI opponents.
Includes virtual currency, a customization shop (card backs, chip styles, table
felts), and a player profile.

```
.
├── main.py          # entrypoint: runs FastAPI + aiogram bot together
├── app/
│   ├── poker.py     # Texas Hold'em engine (hand eval, betting, AI)
│   ├── shop.py      # cosmetics catalogue
│   ├── db.py        # SQLite storage
│   └── auth.py      # Telegram WebApp initData HMAC validation
├── webapp/          # the Mini App (vanilla JS, no build step)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── scripts/         # smoke / API tests
├── requirements.txt
└── .env.example
```

## Features

- **Texas Hold'em** vs 3 AI bots with three play styles (tight / balanced /
  aggressive). Hand evaluator covers all standard categories incl. wheel
  straight. Side pots are computed correctly when players go all-in.
- **Virtual currency.** Each new account gets 2,500 chips. Wins/losses adjust
  the balance. Per-hand seat stack defaults to 1,000.
- **Shop & customization.** 14 cosmetic items across three categories. All
  changes apply immediately to the table (felt color, chip color, card back
  pattern).
- **Profile.** Telegram avatar/name, balance, level (every 10 hands), hands
  played, hands won, win rate.
- **Minimalist dark UI.** Single-page, no framework. Designed for the Telegram
  Mini App container with safe-area insets, haptic feedback, and tab navigation.

## Running locally

1. Create the bot in [@BotFather](https://t.me/BotFather), grab a token, then:

   ```bash
   cp .env.example .env
   # edit .env: set BOT_TOKEN and (later) WEBAPP_URL
   ```

2. Install dependencies (Python 3.11+):

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Run the server. It serves both the bot (long polling) and the Mini App
   (HTTP):

   ```bash
   python main.py
   ```

4. Telegram requires the Mini App to be served over **HTTPS**. The simplest
   way for development is [ngrok](https://ngrok.com/):

   ```bash
   ngrok http 8080
   # copy the https://...ngrok-free.app URL into .env as WEBAPP_URL
   # restart `python main.py`
   ```

5. In BotFather, run `/mybots` → choose your bot → *Bot Settings* → *Menu
   Button* → set the same `WEBAPP_URL`. Optional but nice.

6. Open the bot in Telegram, send `/start`, tap **Open Dotu Poker**.

### Browser dev mode

For UI work without Telegram set `DEV_MODE=1` and open
`http://localhost:8080/?dev_user=42` in a regular browser. The server will
treat the request as user `42`. Disable in production.

## Deployment

Any host that can run a long-lived Python process and expose HTTPS works:

- **Render / Railway / Fly.io** — set `BOT_TOKEN` and `WEBAPP_URL` env vars,
  start command `python main.py`, expose port from `$PORT`.
- **Self-hosted (VPS)** — terminate TLS with Caddy/Nginx in front of port 8080.

The SQLite file `data.db` lives next to the code; mount a persistent volume in
production.

## Security note

The bot token gives full control over your bot. Treat it like a password:

- Keep it only in `.env` (already gitignored).
- Rotate via `/revoke` in BotFather if it ever leaks.
- Never commit it.

`X-Init-Data` is verified server-side using the documented HMAC scheme so
clients cannot impersonate other users in production (`DEV_MODE=0`).

## Tests

```bash
.venv/bin/python scripts/smoke.py     # poker engine
.venv/bin/python scripts/test_api.py  # full HTTP API in dev mode
```
