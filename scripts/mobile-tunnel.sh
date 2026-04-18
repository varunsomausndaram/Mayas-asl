#!/usr/bin/env bash
# Expose your local Jarvis to your phone over a public URL.
# Prefers cloudflared; falls back to ngrok if installed.

set -euo pipefail

PORT="${JARVIS_PORT:-8765}"

if command -v cloudflared >/dev/null 2>&1; then
  echo "==> Using cloudflared"
  exec cloudflared tunnel --url "http://localhost:${PORT}"
fi

if command -v ngrok >/dev/null 2>&1; then
  echo "==> Using ngrok"
  exec ngrok http "${PORT}"
fi

cat >&2 <<EOF
No tunnel binary found. Install one of:
  - cloudflared: https://github.com/cloudflare/cloudflared
  - ngrok:       https://ngrok.com/download

Or expose port ${PORT} directly on your LAN and open
  http://<your-lan-ip>:${PORT}/ from your phone.
EOF
exit 1
