# Mani Marketing — AI Property-Marketing Hub

Private internal tool for Varun. Drives direct bookings for **Beach Houses** (STR)
and **Student Condos** (LTR) by combining social scheduling, AI content generation,
past-guest re-marketing, lead capture, and an approval-gated agent — all in one hub.

Built on [Postiz](https://github.com/gitroomhq/postiz-app) (Apache-2.0) +
self-hosted n8n + a provider-agnostic LLM gateway.

---

## Quick start

### 1. Copy and fill in secrets

```bash
cp .env.example .env
# Edit .env — fill in every value marked CHANGE_ME
```

Minimum required values:
- `JWT_SECRET` — generate with `openssl rand -hex 32`
- `POSTGRES_PASSWORD`
- `N8N_PASSWORD`, `N8N_DB_PASSWORD`, `N8N_ENCRYPTION_KEY`

### 2. Start the hub

```bash
# Core stack (Postiz + n8n + databases)
docker compose up -d

# ── OR ── with LiteLLM + Ollama sidecars
docker compose -f docker-compose.yml -f docker-compose.llm.yml up -d
```

### 3. First-time setup

| Service   | Default URL             | Credentials          |
|-----------|-------------------------|----------------------|
| Postiz    | http://localhost:4200   | create first account |
| n8n       | http://localhost:5678   | `N8N_USER` + `N8N_PASSWORD` from .env |
| LiteLLM   | http://localhost:4000   | `LITELLM_MASTER_KEY` |

On first Postiz start, use the "Create account" flow for the **owner account**.
Registration is then **automatically disabled** (`DISABLE_REGISTRATION=true`),
so no one else can sign up.

---

## Switching AI providers (zero code changes)

Edit `.env` and restart:

```bash
# Option A: OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o

# Option B: Anthropic via LiteLLM sidecar
LLM_BASE_URL=http://litellm:4000/v1
LLM_API_KEY=sk-mani-local
LLM_MODEL=claude-sonnet-4-6

# Option C: Local Ollama (on this server)
LLM_BASE_URL=http://ollama:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.1:70b

# Option D: Remote Ollama / LM Studio (your laptop)
LLM_BASE_URL=http://192.168.1.X:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.1:70b
```

After editing:
```bash
docker compose restart postiz n8n
```

The `Settings → AI Provider` page (Phase 1) also allows switching via the UI without a restart.

---

## Deploying to VPS

1. Clone this repo onto the VPS.
2. Copy `.env.example` → `.env`, update `FRONTEND_URL`, `NEXT_PUBLIC_BACKEND_URL`,
   and `BACKEND_INTERNAL_URL` to your domain.
3. Put Caddy or Nginx in front (reverse-proxy to ports 4200 and 5678).
4. Run `docker compose up -d`.

---

## Pulling upstream Postiz updates

```bash
git fetch postiz-upstream
git diff postiz-upstream/main HEAD -- <core-file>   # review per UPGRADE_NOTES.md
git merge postiz-upstream/main
```

Check `UPGRADE_NOTES.md` before merging — it lists every core file touched and what to reconcile.

---

## Repository layout

```
.
├── docker-compose.yml           Core stack (Postiz + n8n + DBs)
├── docker-compose.llm.yml       Optional LiteLLM + Ollama sidecars
├── .env.example                 All environment variables documented
├── litellm/config.yaml          LiteLLM model routing config
├── propmarket/                  ALL custom code lives here
│   ├── modules/gateway/         LLM Gateway — Phase 1
│   ├── modules/properties/      Property-line + property records — Phase 2
│   ├── modules/templates/       Listing-content template library — Phase 2
│   ├── modules/campaigns/       Seasonal campaign presets — Phase 2
│   ├── modules/leads/           Lead capture + inbox — Phase 3
│   ├── modules/guests/          Past-guest CSV + win-back — Phase 3
│   ├── modules/queue/           Approval queue — Phase 3
│   ├── modules/analytics/       Analytics overlay — Phase 4
│   ├── migrations/              Custom DB migrations
│   └── n8n-workflows/           n8n workflow JSON exports
├── BUILD_SPEC.md                Full project specification
└── UPGRADE_NOTES.md             Log of every Postiz core file change
```
