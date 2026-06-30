'use strict';
/**
 * Gateway config — loaded from environment variables.
 * Runtime overrides are stored in memory only (restart resets to env).
 * The Settings UI PATCHes /api/settings which updates this in-memory config.
 *
 * NEVER log cfg.apiKey or cfg.fallbackApiKey.
 */

let cfg = buildFromEnv();

function buildFromEnv() {
  return {
    provider:    process.env.LLM_PROVIDER    || 'openai_compatible',
    baseUrl:     process.env.LLM_BASE_URL    || 'https://api.openai.com/v1',
    apiKey:      process.env.LLM_API_KEY     || '',
    model:       process.env.LLM_MODEL       || 'gpt-4o',

    embedBaseUrl: process.env.EMBED_BASE_URL || process.env.LLM_BASE_URL || 'https://api.openai.com/v1',
    embedModel:   process.env.EMBED_MODEL    || 'text-embedding-3-small',

    fallbackBaseUrl: process.env.LLM_FALLBACK_BASE_URL || '',
    fallbackApiKey:  process.env.LLM_FALLBACK_API_KEY  || '',
    fallbackModel:   process.env.LLM_FALLBACK_MODEL    || '',

    port: parseInt(process.env.GATEWAY_PORT || '3001', 10),
    requestTimeout: parseInt(process.env.GATEWAY_TIMEOUT_MS || '120000', 10),
  };
}

function get() {
  return cfg;
}

/** Merge a partial update into the in-memory config. */
function update(patch) {
  cfg = { ...cfg, ...patch };
}

/** Reset to environment variables (called on container start, also available via API). */
function reset() {
  cfg = buildFromEnv();
}

/** Safe representation — strips keys for display in the settings UI. */
function safeView() {
  return {
    provider:     cfg.provider,
    baseUrl:      cfg.baseUrl,
    model:        cfg.model,
    embedBaseUrl: cfg.embedBaseUrl,
    embedModel:   cfg.embedModel,
    fallbackBaseUrl: cfg.fallbackBaseUrl,
    fallbackModel:   cfg.fallbackModel,
    hasApiKey:       cfg.apiKey.length > 0,
    hasFallbackKey:  cfg.fallbackApiKey.length > 0,
  };
}

module.exports = { get, update, reset, safeView };
