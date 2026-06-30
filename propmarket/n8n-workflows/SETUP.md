# n8n AI Setup — Point at the LLM Gateway

n8n's built-in AI nodes use credentials you create in the n8n UI.
After first start, do this once to wire n8n to the same switchable gateway:

## Step 1 — Create an OpenAI-compatible credential

1. Open n8n at http://localhost:5678
2. Go to **Settings → Credentials → New credential**
3. Select **"OpenAI"** (or "OpenAI-compatible API")
4. Fill in:
   - **Base URL:** `http://llm-gateway:3001/v1`
   - **API Key:** *(use the value of `LLM_API_KEY` from your `.env`)*
5. Click **Save**

## Step 2 — Use it in AI workflows

In any AI node (e.g. "AI Agent", "OpenAI Chat Model", "Embeddings OpenAI"):
- Select the credential you created above
- The model field: enter whatever is in `LLM_MODEL` (e.g. `gpt-4o`)

## Switching providers in n8n

When you change `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` in `.env` and
restart the gateway (`docker compose restart llm-gateway`), n8n automatically
uses the new provider — no credential change needed as long as the gateway URL
stays `http://llm-gateway:3001/v1`.

Alternatively, use the **Settings → AI Provider** UI at
http://localhost:3001/settings to switch the gateway's provider at runtime
(no restart required).
