'use strict';
require('express-async-errors');

const express = require('express');
const path    = require('path');
const migrate = require('./db/migrate');

const propertyLinesRouter = require('./routes/propertyLines');
const propertiesRouter    = require('./routes/properties');
const templatesRouter     = require('./routes/templates');
const campaignsRouter     = require('./routes/campaigns');
const leadsRouter         = require('./routes/leads');
const guestsRouter        = require('./routes/guests');
const queueRouter         = require('./routes/queue');

const app  = express();
const PORT = parseInt(process.env.PROPMARKET_API_PORT || '3002', 10);

app.use(express.json({ limit: '5mb' }));
app.use(express.urlencoded({ extended: false }));
app.use(express.static(path.join(__dirname, '../public/admin')));

// ── Health ─────────────────────────────────────────────────────────────────
app.get('/health', (_req, res) => res.json({ ok: true, service: 'propmarket-api' }));

// ── Lead form public pages ─────────────────────────────────────────────────
app.get('/inquire', (_req, res) =>
  res.sendFile(path.join(__dirname, '../public/lead-form.html'))
);

// ── Approval queue UI ──────────────────────────────────────────────────────
app.get('/admin/queue', (_req, res) =>
  res.sendFile(path.join(__dirname, '../public/admin/queue.html'))
);

// ── API routes ─────────────────────────────────────────────────────────────
app.use('/api/property-lines',   propertyLinesRouter);
app.use('/api/properties',       propertiesRouter);
app.use('/api/templates',        templatesRouter);
app.use('/api/campaign-presets', campaignsRouter);
app.use('/api/campaign-runs',    campaignsRouter);
app.use('/api/leads',            leadsRouter);
app.use('/api/past-guests',      guestsRouter);
app.use('/api/queue',            queueRouter);

// ── Error handler ──────────────────────────────────────────────────────────
app.use((err, _req, res, _next) => {
  console.error('[propmarket-api] error:', err.message);
  res.status(500).json({ error: err.message || 'Internal server error' });
});

// ── Boot ───────────────────────────────────────────────────────────────────
async function boot() {
  console.log('[propmarket-api] Running migrations…');
  await migrate.run();
  app.listen(PORT, () => {
    console.log(`[propmarket-api] Listening on :${PORT}`);
  });
}

boot().catch((err) => {
  console.error('[propmarket-api] Boot failed:', err.message);
  process.exit(1);
});
