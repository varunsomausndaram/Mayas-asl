#!/usr/bin/env bash
# Jarvis — one-shot installer. Creates a venv, installs core + voice extras,
# writes a .env template, and prints next steps. Idempotent.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "error: $PY not found. Install Python 3.10+ first." >&2
  exit 1
fi

echo "==> Creating virtualenv at .venv"
"$PY" -m venv .venv

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Upgrading pip"
python -m pip install --upgrade pip wheel setuptools

echo "==> Installing Jarvis (core + anthropic + openai extras)"
pip install -e ".[anthropic,openai]"

if [[ "${JARVIS_INSTALL_VOICE:-1}" == "1" ]]; then
  echo "==> Installing voice extras (may take a minute)"
  pip install -e ".[voice]" || echo "warn: voice extras failed — voice mode will be unavailable."
fi

if [[ ! -f .env ]]; then
  echo "==> Writing .env from .env.example"
  cp .env.example .env
  if command -v openssl >/dev/null 2>&1; then
    key="$(openssl rand -base64 32 | tr -d '=+/' | cut -c1-40)"
    sed -i.bak "s|JARVIS_API_KEY=.*|JARVIS_API_KEY=$key|" .env && rm -f .env.bak
    echo "   - generated a fresh JARVIS_API_KEY"
  fi
fi

mkdir -p var/workspaces var/logs

cat <<'EOF'

==========================================
 Jarvis installed.

 Next steps:
   1. Edit .env — add your provider keys (Anthropic / OpenAI / GitHub).
   2. (Optional) Start Ollama + pull a model for local Gemma:
        ollama serve &
        ollama pull gemma2:2b
   3. Start the server:
        source .venv/bin/activate
        jarvisd
   4. Open http://127.0.0.1:8765/ in your browser.
   5. On your phone, visit the same URL over your LAN / tunnel and
      "Add to Home Screen" to install Jarvis as a PWA.

 To dispatch a coding task through Claude Code:
   jarvis dispatch "Refactor the auth module to use async/await."
==========================================
EOF
