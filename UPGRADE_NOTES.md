# UPGRADE_NOTES.md — Postiz core-file change log

When applying a future upstream Postiz update (`git merge postiz-upstream/main`),
reconcile every entry below before completing the merge.

## Format

```
### <date> — <Postiz file path>
**What changed:** <description>
**Why:** <reason from spec>
**Reconcile:** <what to check on next upstream merge>
```

---

## Phase 0 — Fork & bring-up

No Postiz core files were modified in Phase 0.

The following Postiz behaviors are overridden **entirely via environment variables**
(no code changes needed):

| Env var                  | Value  | Effect                                      |
|--------------------------|--------|---------------------------------------------|
| `DISABLE_REGISTRATION`   | `true` | Disables the public sign-up page/API        |
| `IS_GENERAL`             | `true` | Required by Postiz (per official docs)      |
| `OPENAI_BASE_URL`        | (set)  | Redirects Postiz's built-in AI to our gateway (Phase 1) |

## Phase 1 — LLM Gateway

No Postiz core files were modified in Phase 1.

Postiz's built-in AI is redirected to the gateway via environment variables:

| Env var            | Value                          | Effect                                           |
|--------------------|--------------------------------|--------------------------------------------------|
| `OPENAI_BASE_URL`  | `http://llm-gateway:3001/v1`   | All Postiz AI calls go to the gateway            |
| `OPENAI_API_KEY`   | `${LLM_API_KEY}`               | Passed through; gateway uses its own key config  |

The gateway itself lives in `propmarket/modules/gateway/` — a standalone Express service
that the whole system (Postiz + n8n) calls on the Docker internal network.

**Reconcile on next Postiz upgrade:** confirm `OPENAI_BASE_URL` is still a respected env var
in the new Postiz version. If Postiz adds a native gateway/provider abstraction, evaluate
whether to retire our gateway or keep it as the single-provider interface.

## Phase 2 — Real-estate core

> (To be filled in.)

## Phase 3 — Leads + outreach + agent

> (To be filled in.)

## Phase 4 — Analytics overlay + polish

No Postiz core files were modified in Phase 4.

Custom analytics (pm_analytics_events, pm_funnel_summary view) live entirely
in the propmarket-api service's own migrations — zero overlap with Postiz tables.

Dashboard and queue UIs are served by propmarket-api at :3002/admin/* — they
are completely independent of Postiz's frontend.
