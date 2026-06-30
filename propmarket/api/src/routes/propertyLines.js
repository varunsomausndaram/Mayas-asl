'use strict';
const express = require('express');
const pool    = require('../db/pool');

const router = express.Router();

// GET /api/property-lines
router.get('/', async (_req, res) => {
  const { rows } = await pool.query(
    'SELECT * FROM pm_property_lines ORDER BY id'
  );
  res.json(rows);
});

// GET /api/property-lines/:slug
router.get('/:slug', async (req, res) => {
  const { rows } = await pool.query(
    'SELECT * FROM pm_property_lines WHERE slug = $1',
    [req.params.slug]
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found' });
  res.json(rows[0]);
});

module.exports = router;
