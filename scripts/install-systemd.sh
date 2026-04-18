#!/usr/bin/env bash
# Install Jarvis as a per-user systemd service.
# Run as the user who will own the service.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_NAME="jarvis"
UNIT_DIR="$HOME/.config/systemd/user"

mkdir -p "$UNIT_DIR"
install -m 0644 "$ROOT/scripts/jarvis.service" "$UNIT_DIR/${UNIT_NAME}.service"

# Replace %h/jarvis with the actual root directory for user installs.
sed -i.bak "s|%h/jarvis|$ROOT|g" "$UNIT_DIR/${UNIT_NAME}.service"
rm -f "$UNIT_DIR/${UNIT_NAME}.service.bak"

systemctl --user daemon-reload
systemctl --user enable --now "${UNIT_NAME}.service"
systemctl --user status "${UNIT_NAME}.service" --no-pager || true

cat <<EOF
Jarvis is now managed by systemd (user scope).
  - status:    systemctl --user status jarvis
  - restart:   systemctl --user restart jarvis
  - logs:      journalctl --user -u jarvis -f
EOF
