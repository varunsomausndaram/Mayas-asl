#!/usr/bin/env bash
# macOS helper: Homebrew deps + tray-app prerequisites, then runs install.sh.

set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
  echo "error: Homebrew not found. Install from https://brew.sh/" >&2
  exit 1
fi

echo "==> Installing system deps"
brew install python portaudio ffmpeg || true

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JARVIS_INSTALL_VOICE=1 bash "$ROOT/scripts/install.sh"

cat <<'EOF'

On macOS you can also install the system-tray extra:
  source .venv/bin/activate
  pip install -e ".[tray]"
  jarvis tray &
EOF
