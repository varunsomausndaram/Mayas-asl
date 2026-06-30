'use strict';
/**
 * Analytics overlay API.
 *
 * GET /api/analytics/funnel?line=beach-houses&property_id=&from=2025-01-01&to=2025-12-31
 *   → per-line / per-property funnel: reach → engagement → leads → inquiries → bookings
 *
 * GET /api/analytics/summary
 *   → quick counts for the dashboard header (pending queue size, lead count, etc.)
 *
 * POST /api/analytics/events
 *   → record a funnel event (called by n8n when a social post has reach/engagement
 *     data, or when a direct booking is confirmed)
 */
const express = require('express');
const pool    = require('../db/pool');

const router = express.Router();

const FUNNEL_STAGES = ['reach', 'engagement', 'lead', 'inquiry', 'direct_booking'];

// GET /api/analytics/funnel
router.get('/funnel', async (req, res) => {
  const { line, property_id, from, to, channel } = req.query;

  let query = `
    SELECT
      p.id                          AS property_id,
      p.name                        AS property_name,
      pl.slug                       AS line_slug,
      pl.name                       AS line_name,
      ae.event_type,
      ae.channel,
      SUM(ae.value)                 AS total,
      MIN(ae.period_start)          AS from_date,
      MAX(ae.period_end)            AS to_date
    FROM pm_analytics_events ae
    JOIN pm_properties p     ON p.id  = ae.property_id
    JOIN pm_property_lines pl ON pl.id = p.line_id
    WHERE 1=1
  `;
  const params = [];

  if (line)        { params.push(line);        query += ` AND pl.slug = $${params.length}`; }
  if (property_id) { params.push(property_id); query += ` AND p.id = $${params.length}`; }
  if (channel)     { params.push(channel);     query += ` AND ae.channel = $${params.length}`; }
  if (from)        { params.push(from);         query += ` AND ae.period_start >= $${params.length}`; }
  if (to)          { params.push(to);           query += ` AND ae.period_end <= $${params.length}`; }

  query += ' GROUP BY p.id, p.name, pl.slug, pl.name, ae.event_type, ae.channel ORDER BY pl.id, p.name, ae.event_type';

  const { rows } = await pool.query(query, params);

  // Reshape into per-property funnel objects for easier UI consumption
  const byProperty = {};
  for (const row of rows) {
    const key = `${row.property_id}`;
    if (!byProperty[key]) {
      byProperty[key] = {
        property_id:   row.property_id,
        property_name: row.property_name,
        line_slug:     row.line_slug,
        line_name:     row.line_name,
        funnel:        Object.fromEntries(FUNNEL_STAGES.map((s) => [s, 0])),
        by_channel:    {},
      };
    }
    const p = byProperty[key];
    p.funnel[row.event_type] = (p.funnel[row.event_type] || 0) + parseFloat(row.total);
    if (row.channel) {
      if (!p.by_channel[row.channel]) p.by_channel[row.channel] = {};
      p.by_channel[row.channel][row.event_type] =
        (p.by_channel[row.channel][row.event_type] || 0) + parseFloat(row.total);
    }
  }

  res.json(Object.values(byProperty));
});

// GET /api/analytics/summary — quick counts for the dashboard
router.get('/summary', async (_req, res) => {
  const [pendingQ, leadsQ, guestsQ, campaignsQ] = await Promise.all([
    pool.query(`SELECT COUNT(*) FROM pm_pending_actions WHERE status = 'pending'`),
    pool.query(`SELECT COUNT(*) FROM pm_leads WHERE status = 'new'`),
    pool.query(`SELECT COUNT(*) FROM pm_past_guests WHERE opted_out = false`),
    pool.query(`SELECT COUNT(*) FROM pm_campaign_runs WHERE status = 'active'`),
  ]);

  res.json({
    pending_actions:  parseInt(pendingQ.rows[0].count),
    new_leads:        parseInt(leadsQ.rows[0].count),
    active_guests:    parseInt(guestsQ.rows[0].count),
    active_campaigns: parseInt(campaignsQ.rows[0].count),
  });
});

// POST /api/analytics/events — record a funnel event
router.post('/events', async (req, res) => {
  const { property_id, event_type, channel, value = 1, period_start, period_end, metadata = {} } = req.body;

  if (!property_id || !event_type || !period_start || !period_end) {
    return res.status(400).json({ error: 'property_id, event_type, period_start, and period_end are required' });
  }
  if (!FUNNEL_STAGES.includes(event_type) && event_type !== 'spend') {
    return res.status(400).json({ error: `event_type must be one of: ${[...FUNNEL_STAGES, 'spend'].join(', ')}` });
  }

  const { rows } = await pool.query(
    `INSERT INTO pm_analytics_events
       (property_id, event_type, channel, value, period_start, period_end, metadata)
     VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *`,
    [property_id, event_type, channel || null, value, period_start, period_end, metadata]
  );
  res.status(201).json(rows[0]);
});

// GET /api/analytics/line-summary — per-line rollup (for the top-line dashboard view)
router.get('/line-summary', async (req, res) => {
  const { from, to } = req.query;
  let query = `
    SELECT pl.slug AS line_slug, pl.name AS line_name,
           ae.event_type,
           SUM(ae.value) AS total
    FROM pm_analytics_events ae
    JOIN pm_properties p    ON p.id  = ae.property_id
    JOIN pm_property_lines pl ON pl.id = p.line_id
    WHERE 1=1
  `;
  const params = [];
  if (from) { params.push(from); query += ` AND ae.period_start >= $${params.length}`; }
  if (to)   { params.push(to);   query += ` AND ae.period_end <= $${params.length}`; }
  query += ' GROUP BY pl.slug, pl.name, ae.event_type ORDER BY pl.slug, ae.event_type';

  const { rows } = await pool.query(query, params);

  const byLine = {};
  for (const row of rows) {
    if (!byLine[row.line_slug]) {
      byLine[row.line_slug] = { line_slug: row.line_slug, line_name: row.line_name,
        funnel: Object.fromEntries(FUNNEL_STAGES.map((s) => [s, 0])) };
    }
    byLine[row.line_slug].funnel[row.event_type] =
      (byLine[row.line_slug].funnel[row.event_type] || 0) + parseFloat(row.total);
  }

  res.json(Object.values(byLine));
});

module.exports = router;
