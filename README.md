# Jarvis

> *"At your service, sir."*

A personal AI assistant — Iron-Man-grade, phone-first, local-by-default.
Talks, listens, plans, schedules, reads the news, pulls the weather,
drives your GitHub repos, and hands off heavy coding work to
[Claude Code](https://claude.ai/code) in its own sandbox. Runs on your
laptop, on your phone (as a PWA), or in Docker. Keeps a persistent memory
of you, your voice, your preferences, and your inside jokes. Nothing moves
without your permission when it matters.

---

## What you get

### Conversation
- **Jarvis persona.** Dry British butler, concise by default, adjustable
  humor and verbosity.
- **Streaming replies** over SSE and WebSocket.
- **Barge-in interrupts.** Tap the mic (or press Enter) mid-sentence;
  Jarvis stops speaking, captures your new turn, and continues from the
  point of interruption if you want.
- **Long-term memory.** Learns your name, preferred address, timezone,
  humor level, and anything you tell him to remember.

### Skills
- **Filesystem (sandboxed)** — read / write / list inside a workspace.
- **Web search & fetch** — DuckDuckGo, readable-text extractor.
- **News** — Google News RSS (no API key needed).
- **Weather** — Open-Meteo current + 7-day forecast.
- **GitHub** — list repos, read files, open issues, search.
- **Scheduler** — one-shot timers, reminders, 5-field cron jobs.
  Scheduled prompts fire through Jarvis and notify you.
- **System** — CPU/RAM/disk info, cross-platform desktop notifications.
- **Shell (opt-in)** — allowlisted commands only, timeout-bounded.
- **Claude Code dispatch** — hand off a prompt + repo to a headless
  `claude -p` session in an isolated workspace and stream the log back.

### LLM backends
Swap with one env var.
- **Ollama** → local Gemma, Llama, Qwen, anything Ollama serves.
- **Anthropic** → Claude (Sonnet 4.6, Opus 4.7, etc.)
- **OpenAI-compatible** → OpenAI, Groq, Together, Fireworks, OpenRouter,
  Gemini via the OpenAI shim.
- **Echo** → deterministic, offline, used by the test suite.
- **Automatic fallback** — when the primary is unreachable, Jarvis
  transparently retries on the secondary.

### Security
- **API key auth** on every REST, WS, SSE, and voice route.
- **Permission broker.** Every tool call is assessed for risk
  (`none / low / medium / high / critical`). Low runs silently, anything
  above asks you first and shows the reason, the arguments, and whether
  it's reversible. Approve once, for the session, forever, or deny.
- **Egress allowlist.** Outbound HTTP is confined to a known set of hosts
  by default; private IPs are blocked.
- **Audit log** in SQLite — every tool call, approval, dispatch.
- **Rate limiter** per-key.
- **Workspace sandbox.** Filesystem tools refuse `..` / symlink escapes.
- **Shell off by default.** Flip a flag, declare an allowlist.

### Interfaces
- **Web PWA** (`/`). Phone-first. Voice input via Web Speech API. Voice
  output via `speechSynthesis`. Barge-in, approval cards, scheduled-job
  manager, settings panel with live persona tuning. Installable to your
  home screen on iOS and Android.
- **CLI** (`jarvis`). `ask`, `chat` (streaming REPL with slash commands),
  `voice` (push-to-talk on the desktop), `dispatch`, `schedule`,
  `profile`, `tray`.
- **System tray** (`jarvis tray`). Quick-ask, status dot, open UI, quit.

---

## Install

### Quickstart (macOS / Linux)

```bash
git clone <your repo> jarvis && cd jarvis
./scripts/install.sh            # creates .venv, writes .env, generates API key
source .venv/bin/activate

# Optional: local model
ollama serve &
ollama pull gemma2:2b

# Optional: cloud model
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env

jarvisd                         # start the server
open http://127.0.0.1:8765/     # open the web UI
```

On macOS: `./scripts/install-macos.sh` installs `portaudio` and `ffmpeg`
via Homebrew so voice mode works out of the box.

### Docker

```bash
cp .env.example .env             # edit it, set JARVIS_API_KEY
docker compose -f docker/docker-compose.yml up -d
```

Compose brings up Jarvis and an Ollama side-car. Pull a model once with
`docker exec jarvis-ollama ollama pull gemma2:2b`.

### Run on your phone

1. Start Jarvis on your laptop: `jarvisd`.
2. Make it reachable — either on your LAN (`http://<laptop-ip>:8765`)
   or over a tunnel:
   ```bash
   ./scripts/mobile-tunnel.sh   # cloudflared or ngrok
   ```
3. Open the URL on your phone. Add to Home Screen.
4. Tap the ⚙ icon, paste the URL and API key from `.env`, save.
5. Tap the mic and say *"Jarvis, what's on my schedule?"*

---

## Using Jarvis

### Voice

**On the phone (PWA):** tap the mic. Speak. Jarvis streams the reply and
reads it aloud. Tap the mic again to cut him off — he notices and
incorporates your new turn. Toggle *"Wake word: Jarvis"* in settings to
let him listen passively.

**On the desktop (`jarvis voice`):** press ENTER to start recording,
ENTER again to stop. Transcribed locally with `faster-whisper`. Press
ENTER during playback to barge in.

### Chat

```bash
$ jarvis chat
jarvis> Right away, sir. What should we look at?
you> dispatch a refactor of the auth module
jarvis> Understood. Dispatching to Claude Code.
→ claude_code_dispatch({"prompt":"Refactor the auth module to use async/await."})
Approval requested — risk=high — not easily reversible
yellow> use /approvals then /approve <id>
```

### Slash commands

```
/help           /new          /session <id>    /sessions
/interrupt      /approvals    /approve <id>    /deny <id>
/info           /quit
```

### Scheduling

```bash
# In 25 minutes
jarvis schedule remind "tea time" --in-seconds 1500

# Weekdays at 9am: ask Jarvis for the top headlines
jarvis schedule cron "0 9 * * 1-5" "morning briefing" \
    --prompt "Give me the top three news headlines and today's weather in Austin."
```

Or just say it: *"Jarvis, remind me to call Mom in one hour."*

### Dispatch to Claude Code

```bash
jarvis dispatch "Add a GraphQL layer to the user service." \
    --repo https://github.com/you/users
```

Jarvis clones the repo into `var/workspaces/<job>/`, invokes `claude -p`
in headless streaming mode, and pipes the progress back to your terminal
or UI. Cancel anytime with `POST /v1/dispatch/jobs/<id>/cancel`.

---

## Configuration

Everything is environment-driven. See [`.env.example`](.env.example) for
the full list. Hotspots:

| Variable                    | Default        | Notes |
|-----------------------------|----------------|-------|
| `JARVIS_API_KEY`            | *(required)*   | shared secret between clients and server |
| `JARVIS_LLM_PROVIDER`       | `ollama`       | `ollama / anthropic / openai / echo` |
| `JARVIS_LLM_FALLBACK`       | `anthropic`    | used when primary fails |
| `OLLAMA_MODEL`              | `gemma2:2b`    | any Ollama model tag |
| `ANTHROPIC_MODEL`           | `claude-sonnet-4-6` | |
| `JARVIS_ALLOWED_TOOLS`      | sensible default | comma list or `*` |
| `JARVIS_SHELL_ENABLED`      | `false`        | turn on to let Jarvis run shell |
| `JARVIS_SHELL_ALLOWLIST`    | `ls,pwd,...`   | first token of every command |
| `GITHUB_TOKEN`              | *(empty)*      | required for the GitHub tools |
| `CLAUDE_CODE_CLI`           | `claude`       | path to the Claude Code CLI |

---

## Architecture

```
 ┌─────────── UI ───────────┐   ┌──────── LLMs ─────────┐
 │ PWA (web/)               │   │ Ollama (Gemma)        │
 │ CLI (jarvis)             │   │ Anthropic (Claude)    │
 │ Tray (pystray)           │   │ OpenAI-compatible     │
 └────────┬─────────────────┘   └──────────▲────────────┘
          │                                │
          ▼                                │
 ┌────────────────── FastAPI server ──────┴──────┐
 │ /v1/chat · /v1/chat/stream · /v1/ws          │
 │ /v1/voice · /v1/approvals · /v1/scheduler    │
 │ /v1/dispatch · /v1/profile · /v1/audit       │
 └─────┬────────────────────────────────────────┘
       │
       ▼
 ┌──── Orchestrator ─────────────────────────────┐
 │ Persona → system prompt                       │
 │ Memory (sqlite) ← → UserProfileStore (JSON)   │
 │ Tool registry ← → PermissionBroker            │
 │ EventBus → WebSocket / SSE                    │
 └─────┬──────────────────────────────────┬──────┘
       │                                  │
       ▼                                  ▼
 ┌── Tools ───┐                     ┌─ Dispatcher ─┐
 │ fs, shell, │                     │ Claude Code  │
 │ web, news, │                     │ subprocess    │
 │ weather,   │                     │ per-job ws   │
 │ github,    │                     └──────────────┘
 │ reminders, │                     ┌─ Scheduler ──┐
 │ cron       │                     │ sqlite + cron│
 └────────────┘                     └──────────────┘
```

Every subsystem is isolated behind a small interface so you can swap
parts (different LLM, different STT, a different scheduler) without
touching the orchestrator.

---

## API

Human-friendly OpenAPI docs: `http://localhost:8765/docs`.

A few of the endpoints you'll reach for most:

- `POST /v1/chat` — one-shot reply.
- `POST /v1/chat/stream` — SSE, streams `OrchestratorEvent`s.
- `WS /v1/ws` — bidirectional; supports `chat`, `interrupt`, `approve`, `ping`.
- `GET /v1/approvals/pending` / `POST /v1/approvals/{id}` — permission UX.
- `POST /v1/scheduler/jobs` — create timers, reminders, cron.
- `POST /v1/dispatch` / `GET /v1/dispatch/jobs/{id}/stream` — Claude Code
  dispatch with a live stream.
- `POST /v1/voice/transcribe` / `POST /v1/voice/speak` — server-side STT/TTS.
- `GET /v1/audit` — everything sensitive that has happened.

---

## Development

```bash
make install-dev
make test           # pytest
make lint           # ruff
make format         # ruff format
make dev            # uvicorn --reload
```

The test suite exercises the whole stack against the in-process `echo`
LLM and a fake `claude` binary, so it runs without network or GPU. 30+
tests covering config, memory, permissions, scheduler (cron + persistence
+ firing), tools (filesystem sandbox, shell allowlist), egress policy,
rate limiter, orchestrator turn and interrupt, HTTP/WebSocket routes, TTS
chunking, and Claude Code dispatch.

---

## License

MIT. See [LICENSE](LICENSE).

---

## Notes

- **Nothing hardcoded about my identity ships with Jarvis.** The first
  time you say *"my name is X"* he writes it to the profile and uses it
  from then on.
- **Keep your `JARVIS_API_KEY` private.** Anyone with it can talk to
  your Jarvis — and through him, to your tools. If you tunnel to a phone,
  use an HTTPS tunnel (cloudflared/ngrok), not plain LAN HTTP, unless
  you trust the network.
- **Shell & Claude Code dispatch are high-leverage.** They always ask
  first, but your approval chain is the last line of defence — read the
  arguments before clicking.

At your service, sir.
