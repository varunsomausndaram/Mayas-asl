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

> (To be filled in when Phase 1 core edits, if any, are made.)

## Phase 2 — Real-estate core

> (To be filled in.)

## Phase 3 — Leads + outreach + agent

> (To be filled in.)

## Phase 4 — Analytics overlay + polish

> (To be filled in.)
