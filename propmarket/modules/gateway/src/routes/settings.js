'use strict';
/**
 * Settings routes — AI Provider configuration UI + API.
 *
 * GET  /settings           → serves the HTML settings page
 * GET  /api/settings       → returns current config (keys redacted)
 * POST /api/settings       → updates in-memory config (restart to persist to env)
 * POST /api/settings/test  → runs healthCheck() and returns result
 * GET  /api/settings/models → lists models from the currently configured provider
 */

const express = require('express');
const path    = require('path');
const config  = require('../config');
const gateway = require('../gateway');

const router = express.Router();

// ── Serve the HTML UI ────────────────────────────────────────────────────────
router.get('/settings', (_req, res) => {
  res.sendFile(path.join(__dirname, '../../public/settings.html'));
});

// ── GET current config (keys redacted) ──────────────────────────────────────
router.get('/api/settings', (_req, res) => {
  res.json(config.safeView());
});

// ── PATCH/POST update config ─────────────────────────────────────────────────
router.post('/api/settings', (req, res) => {
  const allowed = ['provider', 'baseUrl', 'apiKey', 'model', 'embedBaseUrl', 'embedModel',
                   'fallbackBaseUrl', 'fallbackApiKey', 'fallbackModel'];
  const patch = {};
  for (const key of allowed) {
    if (req.body[key] !== undefined) patch[key] = req.body[key];
  }
  config.update(patch);
  res.json({ ok: true, config: config.safeView() });
});

// ── POST test connection ─────────────────────────────────────────────────────
router.post('/api/settings/test', async (_req, res) => {
  const result = await gateway.healthCheck();
  res.status(result.ok ? 200 : 503).json(result);
});

// ── GET models from current provider ────────────────────────────────────────
router.get('/api/settings/models', async (_req, res) => {
  const models = await gateway.listModels();
  res.json({ models });
});

module.exports = router;
