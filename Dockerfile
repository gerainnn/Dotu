FROM python:3.11-slim

WORKDIR /app

# Install cloudflared (used only by run_with_tunnel.py for ephemeral hosting)
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -sSL -o /usr/local/bin/cloudflared \
      https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
 && chmod +x /usr/local/bin/cloudflared \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV HOST=0.0.0.0 PORT=8080
EXPOSE 8080

# By default, run with cloudflared and let the bot publish a public URL via
# setChatMenuButton. Override with `python main.py` if you have a stable URL.
CMD ["python", "run_with_tunnel.py"]
