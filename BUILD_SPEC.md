# BUILD SPEC — "PropMarket": Fork-and-Customize AI Property-Marketing Hub

> 

---

- Save this file as `BUILD_SPEC.md` at the repo root. Work Phase 0 → 5 in order. After each phase, output `✅ Phase N complete` + a 3-bullet test checklist, then STOP and wait for my go-ahead.

## FILL THESE IN
- `APP_NAME` = Mani Marketing
- `OWNER_NAME` = Varun
- `DEPLOY_TARGET` =  VPS (Docker) and/or local machine]
- `DEFAULT_LLM_PROVIDER` = [anthropic | openai | openai_compatible | ollama | lmstudio]
- `DEFAULT_LLM_MODEL` = [e.g. claude-sonnet | gpt-4-class | llama3.1:70b — your default]
- Property line A (STR) = **Beach Houses** (weekly vacation rentals)
- Property line B (LTR) = **Student Condos** (academic-year leases)

---

## CONTEXT (carry forward — LOCKED decisions, do not re-litigate)
- **Single-user / private internal tool.** One owner (+ optionally a few employees as limited users). NO public signups, NO multi-customer SaaS, NO reseller/agency features.
- **This is a MARKETING hub, not a property-management system.** Day-to-day property management is already handled by the owner's team on Airbnb. Do NOT build PM features (rent, leases, maintenance, work orders). Marketing only.
- **Two property lines** (above) must be separable everywhere: content, calendars, campaigns, analytics all filterable per line and per property.
- **Strategic goal:** drive **direct** bookings/leads to reduce platform dependence — so past-guest re-marketing and a lead-capture surface matter.
- **Spine = fork Postiz + self-host n8n + a provider-agnostic LLM gateway.** Postiz is Apache-2.0 (forking + private customization is fully permitted).
- **AUTONOMY = "auto for routine, approve the big stuff."** Agent-proposed high-stakes actions (campaigns, outbound to guests/leads, replies) go to an approval queue; routine drafting/scheduling can flow automatically once approved templates exist.

## THE CENTERPIECE REQUIREMENT — SWITCHABLE, SEAMLESS LLM
The owner may run **Anthropic (Claude), any OpenAI-compatible API key, OR a local model (Ollama / LM Studio)** — and must be able to switch with **zero code changes**. Implement this as the core design constraint, not an afterthought:

**MUST: every LLM call in the entire system goes through ONE internal "LLM Gateway." No file anywhere may import a provider SDK directly.**

- **Gateway contract:** the app speaks **OpenAI-compatible chat-completions format** to a single configurable endpoint. The gateway exposes typed methods: `chat({messages, tools, stream})`, `embed({input})`, `healthCheck()`, `listModels()`.
- **Config (env):** `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_PROVIDER`, plus optional `LLM_FALLBACK_*`. Embeddings: `EMBED_BASE_URL` / `EMBED_MODEL` (may equal the chat provider or a local embedder).
- **Why OpenAI-compatible is the universal target:** OpenAI itself, most API providers, **Ollama** (`/v1`), and **LM Studio** (`/v1`) all already speak it. So switching = changing `LLM_BASE_URL` + key + model. Nothing else.
- **For native Anthropic + 100+ other providers behind the same format:** include an **optional LiteLLM proxy** as a Docker sidecar. When the owner wants Claude, they point `LLM_BASE_URL` at the LiteLLM sidecar and set the model to a Claude model; LiteLLM translates. Document this clearly. (If the owner prefers, the gateway may also call Anthropic's own OpenAI-compatible endpoint directly — support both.)
- **Tool/function calling MUST work uniformly** through the gateway (the agent depends on it). Where a local model lacks native tool-calling, the gateway MUST fall back to a structured-JSON prompting mode and parse the result — so agent features degrade gracefully, never break.
- **Streaming MUST work** for content generation UIs.
- **MUST: a `Settings → AI Provider` page** where the owner picks provider, pastes base URL + key, selects model (populated via `listModels()` when available), and clicks **"Test connection"** (calls `healthCheck()` + a 1-token completion). Switching providers here requires NO redeploy.
- **MUST: n8n's AI nodes point at the same gateway base URL**, so the whole system shares one switchable provider.

---

## STACK & INFRA
- **Base app:** forked **Postiz** (`gitroomhq/postiz-app`) — Next.js + Node, PostgreSQL + Redis. Keep its stack; add to it.
- **Automation/agent backbone:** **n8n**, self-hosted (Docker).
- **LLM:** the gateway above + optional **LiteLLM** sidecar + optional **Ollama** for local models (local model may run on the server or on the owner's machine over the network — make the base URL configurable for either).
- **Everything ships in one `docker-compose.yml`:** postiz-app, postgres, redis, n8n, (optional) litellm, (optional) ollama. One `docker compose up` brings the whole hub online. MUST also run on `DEPLOY_TARGET`.
- **Secrets:** env / Replit Secrets only. NEVER hardcode keys. NEVER log secret values.

---

## CUSTOMIZATION DISCIPLINE (critical for staying upgradeable)
You are forking a living project. To keep future Postiz updates mergeable:
- **MUST** isolate all custom code in clearly named modules/folders (e.g. `propmarket/`), with custom DB tables in their own migrations.
- **MUST** touch Postiz core files as little as possible. Every unavoidable core edit MUST be recorded in `UPGRADE_NOTES.md` (file, what changed, why) so it can be reconciled after upstream updates.
- **MUST NOT** rewrite Postiz's publishing/scheduling/calendar/analytics engine — reuse it. You are adding around it.
- **MUST NOT** add features outside this spec.

## WHAT TO STRIP FROM THE FORK (anti-bloat — do in Phase 0)
Remove or disable: public/open registration, any agency/multi-customer tier, the "buy/sell posts" marketplace, reseller/white-label and team-billing/subscription features. Lock auth to the owner (+ optional limited employee users). Keep it private and lean.

---

## REAL-ESTATE "SAUCE" — THE MODULES YOU ADD (this is the differentiation)
1. **Property-line separation.** Model **Beach Houses** and **Student Condos** as distinct segments, and each individual property beneath them. Content, calendar, campaigns, and analytics MUST be filterable by line and by property.
2. **Listing-content template library.** Reusable, variable-driven post templates the LLM fills: beach-house seasonal promo, last-minute-week deal, amenity highlight, guest-review/UGC repost; student-condo availability, tour invite, amenity/location highlight, move-in-season push. Variables pulled from a simple property record (name, location, beds, rate, hero photos, key features).
3. **Seasonal campaign presets.** Two schedulable campaign templates: (a) **Student fill cycle** (configurable lead window, e.g. Jan–Apr for fall move-in); (b) **Beach season cycle** (peak summer + shoulder-season fill + last-minute weeks). Each preset = a scheduled series of generated posts + optional email/SMS, runnable per property.
4. **Lead capture + light inbox.** A public lead form per property (student housing especially) → `leads` table → agent qualifies + drafts a response (→ approval queue) → owner approves/sends. Capture social comment/DM leads where the platform allows.
5. **Past-guest re-marketing.** Import a guest list via CSV (from the team's Airbnb exports) → segmented seasonal win-back email/SMS campaigns aimed at **direct** rebooking. (Email send via a configurable SMTP/provider; SMS via a configurable provider — keep provider-agnostic, env-driven.)
6. **Approval queue (mobile-first).** One central surface listing every agent-proposed action (posts, replies, campaigns, outreach) with the draft + the agent's reasoning + one-tap Approve / Edit / Reject. MUST be usable on a phone.
7. **Marketing analytics overlay.** On top of Postiz's social analytics, add a per-line / per-property view of the funnel: reach → engagement → leads → **direct bookings/inquiries** → (optional) spend. 

## THE AGENT (built with n8n + the gateway, approval-gated)
Implement the "agent" as **n8n workflows calling the LLM Gateway**, not bespoke agent code:
- Scheduled or triggered workflow → LLM Gateway drafts content/campaign/reply (grounded in the property record + template + brand-voice notes) → writes a **pending_action** record → notifies owner (approval queue + optional email/SMS) → on approval, executes via **Postiz API** (publish/schedule) or sends the email/SMS.
- Routine, pre-approved template posts may auto-schedule; anything new, anything outbound to a human, and any reply MUST pass the approval gate.
- n8n's AI steps MUST use the gateway base URL (shared switchable provider).

---

## BUILD PROCESS — MVP-FIRST, GATED. STOP AT EACH GATE.
After each phase: `✅ Phase N complete`, a one-line summary, a 3-bullet test checklist → STOP for go-ahead.

- **Phase 0 — Fork & bring-up.** Fork Postiz; get it running via Docker; strip the agency/marketplace/registration cruft (above); lock to single-user/private auth. Stand up n8n in the compose file. Confirm the base hub loads and you can connect one social account. **GATE.**
- **Phase 1 — Switchable LLM Gateway (the core MVP).** Build the gateway (OpenAI-compatible, env-driven base URL/key/model, streaming, uniform tool-calling with JSON fallback, `healthCheck`/`listModels`, optional fallback provider). Route ALL of the fork's existing AI features through it. Add `Settings → AI Provider` with Test button. Point n8n AI nodes at the gateway. Add optional LiteLLM + Ollama services to compose. **GATE.**
- **Phase 2 — Real-estate core.** Property-line separation, property records, listing-content template library, seasonal campaign presets. **GATE.**
- **Phase 3 — Leads + outreach + agent.** Lead capture form + light inbox, past-guest CSV import + re-marketing campaigns, the n8n approval-gated agent workflows, the mobile approval queue UI. **GATE.**
- **Phase 4 — Analytics overlay + polish.** Per-line/per-property funnel view, mobile polish, docs (`README` for run/switch-provider, `UPGRADE_NOTES.md`). **GATE.**
- **Phase 5 (optional, on request).** Twenty CRM for deeper lead pipeline; pgvector brand-voice memory/RAG so generated content matches a learned voice; ads/SEO/analytics skills via an MCP layer.

## STOP-AND-ASK TRIGGERS (for you, the build agent)
MUST pause and ask before: adding any **paid** dependency, changing the DB schema after a phase is locked, deleting any file, editing Postiz **core** beyond what a module requires (log it in `UPGRADE_NOTES.md`), or any large refactor. Output `✅` after every milestone. Build only what this spec defines. Prefer correctness and upgradeability over cleverness.

## SUCCESS CRITERIA (binary)
- [ ] Forked Postiz runs privately via one `docker compose up` (no public signup; agency/marketplace features gone).
- [ ] In `Settings → AI Provider`, switching between **Anthropic**, an **OpenAI-compatible key**, and a **local Ollama model** changes the AI with **zero code edits** — proven by the Test button + generating a post under each.
- [ ] n8n's AI steps use the same gateway (one switchable provider across the whole system).
- [ ] Tool-calling still works on a local model (via JSON fallback) — agent features don't break when switching off a frontier API.
- [ ] A **Beach House** post and a **Student Condo** post generate from a template and schedule, filterable by line.
- [ ] A past-guest win-back campaign and a student-housing lead reply are drafted by the agent and land in the **approval queue** (not auto-sent).
- [ ] No provider SDK is imported anywhere outside the gateway module.
