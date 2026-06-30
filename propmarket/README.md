# propmarket/ — Mani Marketing custom modules

All code added on top of the Postiz fork lives here.
Postiz core files are NOT modified unless strictly unavoidable; every such edit
is logged in /UPGRADE_NOTES.md.

## Directory layout

```
propmarket/
├── migrations/       Custom DB migrations (tables: properties, property_lines,
│                     leads, pending_actions, campaign_presets, past_guests …)
├── modules/
│   ├── gateway/      LLM Gateway — the single provider-agnostic AI client
│   ├── properties/   Property-line + property CRUD API
│   ├── templates/    Listing-content template library
│   ├── campaigns/    Seasonal campaign presets
│   ├── leads/        Lead capture form + inbox
│   ├── guests/       Past-guest CSV import + win-back campaigns
│   ├── queue/        Approval queue API + mobile UI
│   └── analytics/    Per-line/per-property funnel overlay
├── n8n-workflows/    n8n workflow JSON exports (auto-imported on n8n start)
└── public/           Static assets for lead forms (mounted into postiz)
```

## Phase tracker

| Phase | Description                        | Status  |
|-------|------------------------------------|---------|
| 0     | Fork & bring-up                    | ✅ done |
| 1     | Switchable LLM Gateway             | ✅ done |
| 2     | Real-estate core (properties)      | ✅ done |
| 3     | Leads + outreach + agent           | ✅ done |
| 4     | Analytics overlay + polish         | ✅ done |
| 5     | CRM / RAG / MCP (optional)         | pending |
