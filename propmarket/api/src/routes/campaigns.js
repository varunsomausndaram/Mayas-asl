'use strict';
const express = require('express');
const pool    = require('../db/pool');

const router = express.Router();

// GET /api/campaign-presets?line=beach-houses
router.get('/presets', async (req, res) => {
  const { line } = req.query;
  let query = `
    SELECT cp.*, pl.slug AS line_slug, pl.name AS line_name
    FROM pm_campaign_presets cp
    JOIN pm_property_lines pl ON pl.id = cp.line_id
    WHERE cp.active = true
  `;
  const params = [];
  if (line) {
    params.push(line);
    query += ` AND pl.slug = $${params.length}`;
  }
  query += ' ORDER BY pl.id, cp.name';

  const { rows } = await pool.query(query, params);
  res.json(rows);
});

// GET /api/campaign-presets/:slug
router.get('/presets/:slug', async (req, res) => {
  const { rows } = await pool.query(
    `SELECT cp.*, pl.slug AS line_slug
     FROM pm_campaign_presets cp
     JOIN pm_property_lines pl ON pl.id = cp.line_id
     WHERE cp.slug = $1`,
    [req.params.slug]
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found' });
  res.json(rows[0]);
});

// GET /api/campaign-runs?property_id=&status=active
router.get('/runs', async (req, res) => {
  const { property_id, status } = req.query;
  let query = `
    SELECT cr.*, cp.name AS preset_name, cp.preset_type, cp.steps,
           p.name AS property_name, pl.slug AS line_slug
    FROM pm_campaign_runs cr
    JOIN pm_campaign_presets cp ON cp.id = cr.preset_id
    JOIN pm_properties p ON p.id = cr.property_id
    JOIN pm_property_lines pl ON pl.id = cp.line_id
    WHERE 1=1
  `;
  const params = [];
  if (property_id) { params.push(property_id); query += ` AND cr.property_id = $${params.length}`; }
  if (status)      { params.push(status);      query += ` AND cr.status = $${params.length}`; }
  query += ' ORDER BY cr.created_at DESC';

  const { rows } = await pool.query(query, params);
  res.json(rows);
});

// POST /api/campaign-runs  — start a campaign run for a property
router.post('/runs', async (req, res) => {
  const { preset_id, property_id, start_date, config = {} } = req.body;
  if (!preset_id || !property_id || !start_date) {
    return res.status(400).json({ error: 'preset_id, property_id, and start_date are required' });
  }

  const { rows } = await pool.query(
    `INSERT INTO pm_campaign_runs (preset_id, property_id, start_date, config)
     VALUES ($1, $2, $3, $4) RETURNING *`,
    [preset_id, property_id, start_date, config]
  );
  res.status(201).json(rows[0]);
});

// PATCH /api/campaign-runs/:id  — update status or config
router.patch('/runs/:id', async (req, res) => {
  const { status, config } = req.body;
  const fields = [], params = [];

  if (status) { params.push(status); fields.push(`status = $${params.length}`); }
  if (config) { params.push(config); fields.push(`config = $${params.length}`); }
  if (!fields.length) return res.status(400).json({ error: 'Nothing to update' });

  params.push(req.params.id);
  const { rows } = await pool.query(
    `UPDATE pm_campaign_runs SET ${fields.join(', ')} WHERE id = $${params.length} RETURNING *`,
    params
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found' });
  res.json(rows[0]);
});

module.exports = router;
