# Quick start

The bot `@Dotudorusshbot` exists on Telegram and the code is ready, but
**the bot needs to actually be running somewhere reachable by Telegram**.
This sandbox cannot host it long-term, so you need to run it yourself.
Pick one of the three options below.

> Important: rotate the leaked token first. In `@BotFather` send `/revoke`,
> get a new token, put it in `.env`.

---

## Option A — your laptop (1 minute, with Docker)

```bash
git clone https://github.com/gerainnn/Dotu.git
cd Dotu
cp .env.example .env
# edit .env: set BOT_TOKEN=<new token from BotFather>
docker build -t dotu .
docker run --rm -e BOT_TOKEN=$(grep BOT_TOKEN .env | cut -d= -f2) dotu
```

The container starts cloudflared automatically, gets a free public HTTPS URL,
sets it as the bot's menu button via Telegram API, and starts polling.

You can then open `@Dotudorusshbot` in Telegram → tap **Play** at the bottom
of chat → Mini App opens.

When you stop the container the URL goes away; restart and a new URL is
auto-applied.

## Option B — your laptop (no Docker)

```bash
git clone https://github.com/gerainnn/Dotu.git
cd Dotu
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # set BOT_TOKEN
# install cloudflared (single binary, no signup):
curl -sL -o cloudflared \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/   # or just put it on PATH
python run_with_tunnel.py
```

## Option C — permanent hosting (free tier)

For something always-on, deploy to **Render**, **Railway**, or **Fly.io**.
Any platform that:
1. Accepts a Dockerfile or a `python main.py` start command
2. Gives you an HTTPS URL

Then set two env vars:
- `BOT_TOKEN` = your bot token
- `WEBAPP_URL` = the platform's HTTPS URL (e.g. `https://dotu.onrender.com`)

Start command: `python main.py` (skip cloudflared since the platform gives
you the URL directly).

---

## Verifying it works

When the bot is running, you should see in the logs:

```
INFO dotu: Bot polling started.
INFO dotu: Default chat menu button set to https://...
```

Send `/start` to your bot in Telegram — you'll get a "Open Dotu Poker" button
and a "Play" menu item at the bottom of the chat.
