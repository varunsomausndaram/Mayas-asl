'use strict';
require('express-async-errors');

const express  = require('express');
const path     = require('path');
const config   = require('./config');
const v1Routes       = require('./routes/v1');
const healthRoute    = require('./routes/health');
const settingsRoutes = require('./routes/settings');

const app = express();

app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: false }));
app.use(express.static(path.join(__dirname, '../public')));

// ── Routes ───────────────────────────────────────────────────────────────────
app.use('/v1',      v1Routes);
app.use('/health',  healthRoute);
app.use('/',        settingsRoutes);

// Root redirect → settings UI
app.get('/', (_req, res) => res.redirect('/settings'));

// ── Error handler ────────────────────────────────────────────────────────────
app.use((err, _req, res, _next) => {
  console.error('[gateway] error:', err.message);
  res.status(500).json({ error: err.message || 'Internal gateway error' });
});

// ── Start ────────────────────────────────────────────────────────────────────
const { port } = config.get();
app.listen(port, () => {
  const cfg = config.get();
  console.log(`[gateway] Mani LLM Gateway listening on :${port}`);
  console.log(`[gateway] Provider: ${cfg.provider} | Model: ${cfg.model} | Base URL: ${cfg.baseUrl}`);
  console.log(`[gateway] Settings UI: http://localhost:${port}/settings`);
});
