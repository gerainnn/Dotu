"""Launch cloudflared, capture the public URL, then run main.py with WEBAPP_URL set.

This is for ephemeral hosting (sandbox / dev). For real deployments use a stable
HTTPS URL and just run `python main.py`.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

PORT = int(os.getenv("PORT", "8080"))


def start_tunnel(local_url: str) -> str:
    """Spawn cloudflared and read its stdout until it prints the public URL."""
    cf = shutil.which("cloudflared")
    if not cf:
        # Fallback: bundled binary in .runtime/
        local = os.path.join(os.path.dirname(__file__), ".runtime", "cloudflared")
        if os.path.isfile(local) and os.access(local, os.X_OK):
            cf = local
        else:
            raise SystemExit("cloudflared binary not found")

    proc = subprocess.Popen(
        [cf, "tunnel", "--no-autoupdate", "--url", local_url],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    url_holder: dict = {}
    pat = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)

    def reader() -> None:
        for line in proc.stdout:  # type: ignore[union-attr]
            sys.stdout.write(f"[cf] {line}")
            sys.stdout.flush()
            if "url" not in url_holder:
                m = pat.search(line)
                if m:
                    url_holder["url"] = m.group(0)

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    deadline = time.time() + 60
    while time.time() < deadline and "url" not in url_holder:
        if proc.poll() is not None:
            raise SystemExit("cloudflared exited early")
        time.sleep(0.5)

    if "url" not in url_holder:
        proc.terminate()
        raise SystemExit("cloudflared did not produce a URL within 60s")

    print(f"[run] tunnel URL: {url_holder['url']}", flush=True)

    # Stash the proc so we can kill it on exit
    setup_signal_cleanup(proc)
    return url_holder["url"]


def setup_signal_cleanup(proc: subprocess.Popen) -> None:
    def _terminate(*_a):
        try:
            proc.terminate()
        except Exception:
            pass
        sys.exit(0)
    signal.signal(signal.SIGTERM, _terminate)
    signal.signal(signal.SIGINT, _terminate)


def main() -> None:
    public_url = start_tunnel(f"http://127.0.0.1:{PORT}")
    os.environ["WEBAPP_URL"] = public_url
    os.environ["PUBLIC_URL"] = public_url

    # Import main now that env is set (BOT_TOKEN, WEBAPP_URL, PORT are read at import).
    import main as botmain

    # Expose the tunnel URL so the operator can discover it without seeing logs.
    @botmain.api.get("/tunnel")
    async def _tunnel():
        return {"url": public_url}

    botmain.main()


if __name__ == "__main__":
    main()
