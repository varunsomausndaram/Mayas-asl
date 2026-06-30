'use strict';
const express = require('express');
const pool    = require('../db/pool');

const router = express.Router();

// GET /api/properties?line=beach-houses&active=true
router.get('/', async (req, res) => {
  const { line, active } = req.query;
  let query = `
    SELECT p.*, pl.slug AS line_slug, pl.name AS line_name
    FROM pm_properties p
    JOIN pm_property_lines pl ON pl.id = p.line_id
    WHERE 1=1
  `;
  const params = [];

  if (line) {
    params.push(line);
    query += ` AND pl.slug = $${params.length}`;
  }
  if (active !== undefined) {
    params.push(active !== 'false');
    query += ` AND p.active = $${params.length}`;
  }

  query += ' ORDER BY pl.id, p.name';

  const { rows } = await pool.query(query, params);
  res.json(rows);
});

// GET /api/properties/:id
router.get('/:id', async (req, res) => {
  const { rows } = await pool.query(
    `SELECT p.*, pl.slug AS line_slug, pl.name AS line_name
     FROM pm_properties p
     JOIN pm_property_lines pl ON pl.id = p.line_id
     WHERE p.id = $1`,
    [req.params.id]
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found' });
  res.json(rows[0]);
});

// POST /api/properties
router.post('/', async (req, res) => {
  const {
    line_id, slug, name, location, beds, baths, max_guests,
    base_rate, hero_photo_url, photo_urls, key_features,
    amenities, brand_voice_notes
  } = req.body;

  if (!line_id || !slug || !name) {
    return res.status(400).json({ error: 'line_id, slug, and name are required' });
  }

  const { rows } = await pool.query(
    `INSERT INTO pm_properties
       (line_id, slug, name, location, beds, baths, max_guests, base_rate,
        hero_photo_url, photo_urls, key_features, amenities, brand_voice_notes)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
     RETURNING *`,
    [
      line_id, slug, name, location || null, beds || null, baths || null,
      max_guests || null, base_rate || null, hero_photo_url || null,
      photo_urls || [], key_features || [], amenities || {},
      brand_voice_notes || null,
    ]
  );
  res.status(201).json(rows[0]);
});

// PATCH /api/properties/:id
router.patch('/:id', async (req, res) => {
  const allowed = [
    'name','location','beds','baths','max_guests','base_rate',
    'hero_photo_url','photo_urls','key_features','amenities',
    'brand_voice_notes','active',
  ];
  const fields = [], params = [];
  for (const key of allowed) {
    if (req.body[key] !== undefined) {
      params.push(req.body[key]);
      fields.push(`${key} = $${params.length}`);
    }
  }
  if (!fields.length) return res.status(400).json({ error: 'No valid fields to update' });

  params.push(req.params.id);
  const { rows } = await pool.query(
    `UPDATE pm_properties SET ${fields.join(', ')} WHERE id = $${params.length} RETURNING *`,
    params
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found' });
  res.json(rows[0]);
});

// DELETE /api/properties/:id  (soft delete — sets active = false)
router.delete('/:id', async (req, res) => {
  const { rows } = await pool.query(
    'UPDATE pm_properties SET active = false WHERE id = $1 RETURNING id',
    [req.params.id]
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found' });
  res.json({ ok: true, id: rows[0].id });
});

module.exports = router;
