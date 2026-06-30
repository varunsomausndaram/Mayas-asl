'use strict';
/**
 * /v1/* — OpenAI-compatible pass-through routes.
 * Postiz and n8n point their OPENAI_BASE_URL here.
 */

const express = require('express');
const gateway = require('../gateway');
const config  = require('../config');

const router = express.Router();

// ── POST /v1/chat/completions ────────────────────────────────────────────────
router.post('/chat/completions', async (req, res) => {
  const body = req.body;

  if (body.stream) {
    const upstream = await gateway.stream(body);
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('X-Accel-Buffering', 'no');
    upstream.body.pipe(res);
    upstream.body.on('error', () => res.end());
    return;
  }

  const result = await gateway.chat(body);
  res.json(result);
});

// ── POST /v1/embeddings ──────────────────────────────────────────────────────
router.post('/embeddings', async (req, res) => {
  const result = await gateway.embed(req.body);
  res.json(result);
});

// ── GET /v1/models ───────────────────────────────────────────────────────────
router.get('/models', async (_req, res) => {
  const models = await gateway.listModels();
  res.json({ object: 'list', data: models.map((m) => ({ id: m.id, object: 'model' })) });
});

// ── GET /v1/health (alias for /health — handy for OpenAI-compat clients) ────
router.get('/health', async (_req, res) => {
  const result = await gateway.healthCheck();
  res.status(result.ok ? 200 : 503).json(result);
});

module.exports = router;
