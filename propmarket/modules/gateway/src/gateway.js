'use strict';
/**
 * LLM Gateway — the single AI client for the entire Mani Marketing hub.
 *
 * ALL LLM calls in the system go through this module.
 * No other file may import a provider SDK directly.
 *
 * Contract:
 *   chat({ messages, tools, stream, model, temperature, max_tokens }) → response | ReadableStream
 *   embed({ input, model })                                           → { data, usage }
 *   healthCheck()                                                     → { ok, model, latencyMs }
 *   listModels()                                                      → [{ id, name }]
 */

const fetch = require('node-fetch');
const config = require('./config');
const { prepareNative, prepareJsonFallback, parseJsonFallbackResponse } = require('./toolcall');

// Providers known to support native tool-calling
const NATIVE_TOOL_CALL_PROVIDERS = new Set([
  'openai', 'openai_compatible', 'anthropic', 'groq', 'together',
]);

// Models known to require JSON fallback (pattern-matched)
const JSON_FALLBACK_MODELS = [
  /^ollama\//i,
  /llama/i,
  /mistral/i,
  /phi/i,
  /gemma/i,
];

function needsJsonFallback(model) {
  return JSON_FALLBACK_MODELS.some((re) => re.test(model));
}

/**
 * Build Authorization header.
 * Handles "Bearer" prefix absent on some providers (e.g. Ollama accepts any key).
 */
function authHeader(apiKey) {
  if (!apiKey) return {};
  return { Authorization: `Bearer ${apiKey}` };
}

/**
 * Core fetch wrapper — sends to primary, falls back to secondary on error.
 */
async function fetchWithFallback(path, body, stream = false) {
  const cfg = config.get();

  async function attempt(baseUrl, apiKey, model) {
    const url = `${baseUrl.replace(/\/$/, '')}${path}`;
    const bodyWithModel = { ...body, model: body.model || model };

    let prepared = bodyWithModel;
    if (body.tools?.length) {
      prepared = needsJsonFallback(model)
        ? prepareJsonFallback(bodyWithModel)
        : prepareNative(bodyWithModel);
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), cfg.requestTimeout);

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader(apiKey),
        },
        body: JSON.stringify(prepared),
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`Provider returned ${res.status}: ${text.slice(0, 200)}`);
      }

      return { res, usedJsonFallback: prepared !== bodyWithModel };
    } finally {
      clearTimeout(timeout);
    }
  }

  try {
    return await attempt(cfg.baseUrl, cfg.apiKey, cfg.model);
  } catch (primaryErr) {
    if (cfg.fallbackBaseUrl && cfg.fallbackModel) {
      console.warn('[gateway] Primary failed, trying fallback:', primaryErr.message);
      return await attempt(cfg.fallbackBaseUrl, cfg.fallbackApiKey, cfg.fallbackModel);
    }
    throw primaryErr;
  }
}

/**
 * chat — non-streaming completion.
 * Returns the raw OpenAI-compat JSON response (tool_calls reconstructed if needed).
 */
async function chat({ messages, tools, model, temperature, max_tokens, ...rest }) {
  const body = { messages, ...(tools?.length ? { tools } : {}), ...rest };
  if (model) body.model = model;
  if (temperature !== undefined) body.temperature = temperature;
  if (max_tokens !== undefined) body.max_tokens = max_tokens;

  const { res, usedJsonFallback } = await fetchWithFallback('/chat/completions', body);
  const json = await res.json();

  return usedJsonFallback ? parseJsonFallbackResponse(json) : json;
}

/**
 * stream — streaming chat completion.
 * Returns the raw Response so the caller can pipe res.body to the client.
 */
async function stream({ messages, tools, model, temperature, max_tokens, ...rest }) {
  const body = { messages, stream: true, ...(tools?.length ? { tools } : {}), ...rest };
  if (model) body.model = model;
  if (temperature !== undefined) body.temperature = temperature;
  if (max_tokens !== undefined) body.max_tokens = max_tokens;

  // Streaming + JSON fallback: strip tools and inject prompt, but we can't
  // post-process the stream, so tool reconstruction is skipped (callers that
  // need tool calls should use non-streaming chat()).
  const cfg = config.get();
  const usedModel = model || cfg.model;
  let prepared = body;
  if (body.tools?.length && needsJsonFallback(usedModel)) {
    prepared = prepareJsonFallback(body);
  }

  const { res } = await fetchWithFallback('/chat/completions', prepared, true);
  return res; // caller pipes res.body
}

/**
 * embed — text embeddings.
 */
async function embed({ input, model }) {
  const cfg = config.get();
  const body = {
    model: model || cfg.embedModel,
    input,
  };

  const url = `${cfg.embedBaseUrl.replace(/\/$/, '')}/embeddings`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeader(cfg.apiKey),
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Embed provider returned ${res.status}: ${text.slice(0, 200)}`);
  }

  return res.json();
}

/**
 * healthCheck — calls /models (or does a 1-token completion) to verify the provider.
 * Returns { ok, model, latencyMs, error? }
 */
async function healthCheck() {
  const cfg = config.get();
  const start = Date.now();
  try {
    // Try /models first (cheap, no token cost)
    const url = `${cfg.baseUrl.replace(/\/$/, '')}/models`;
    const res = await fetch(url, {
      headers: { ...authHeader(cfg.apiKey) },
      signal: AbortSignal.timeout(15000),
    });

    if (res.ok) {
      return { ok: true, model: cfg.model, latencyMs: Date.now() - start };
    }

    // Fall back to a 1-token completion
    const body = {
      model: cfg.model,
      messages: [{ role: 'user', content: 'Hi' }],
      max_tokens: 1,
    };
    const chatRes = await fetch(`${cfg.baseUrl.replace(/\/$/, '')}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeader(cfg.apiKey) },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    });

    if (!chatRes.ok) {
      const text = await chatRes.text().catch(() => '');
      throw new Error(`${chatRes.status}: ${text.slice(0, 200)}`);
    }

    return { ok: true, model: cfg.model, latencyMs: Date.now() - start };
  } catch (err) {
    return { ok: false, model: cfg.model, latencyMs: Date.now() - start, error: err.message };
  }
}

/**
 * listModels — returns models from the configured provider.
 * Falls back to an empty array if the provider doesn't support /models.
 */
async function listModels() {
  const cfg = config.get();
  try {
    const url = `${cfg.baseUrl.replace(/\/$/, '')}/models`;
    const res = await fetch(url, {
      headers: { ...authHeader(cfg.apiKey) },
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return [];
    const json = await res.json();
    // OpenAI compat: { data: [{ id, ... }] }
    const models = Array.isArray(json) ? json : (json.data || []);
    return models.map((m) => ({ id: m.id || m.name, name: m.id || m.name }));
  } catch {
    return [];
  }
}

module.exports = { chat, stream, embed, healthCheck, listModels };
