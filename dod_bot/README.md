# dod_bot

Standalone Telegram bot that proxies messages to an OpenAI-compatible LLM with
the Dod persona injected as the system prompt. Per-user chat history in sqlite.

## Setup

```bash
pip install -r requirements.txt           # from project root
cp dod_bot/.env.example dod_bot/.env
# edit dod_bot/.env — fill TG_BOT_TOKEN and LLM_API_KEY at minimum
python -m dod_bot.bot
```

## Lock it down

By default anyone who finds the bot username can talk to it and burn your LLM
quota. To restrict:

1. Start the bot, hit `/whoami` from your TG account, copy the id.
2. Put it into `ALLOWED_USERS` in `dod_bot/.env`, comma-separated for several
   ids.
3. Restart.

## Provider choice notes

- OpenAI `gpt-4o`/`gpt-4o-mini` — cheap and fast, but content filter will
  trim hard horror / violence in `/плотно` and `/рп` modes.
- Anthropic Claude via OpenRouter — better prose, similar policy footprint.
- Open-weights via Groq / Together / local — closest to no-filter experience.
  For Russian-language dark fiction the 70B-class llama-3.3 / Qwen-2.5
  finetunes work decently.

## Files

- `bot.py` — aiogram 3 entrypoint, handlers, message splitting.
- `persona.py` — the system prompt. Edit to tweak voice.
- `llm.py` — async OpenAI-compatible client.
- `storage.py` — sqlite history (`history.db`, gitignored).

## Commands

- `/start` — greet and reset history.
- `/reset` — wipe context for the current user.
- `/whoami` — print your TG id (for the whitelist).
