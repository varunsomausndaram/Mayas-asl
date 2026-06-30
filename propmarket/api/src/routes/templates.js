'use strict';
const express  = require('express');
const pool     = require('../db/pool');
const fetch    = require('node-fetch');

const router = express.Router();

const GATEWAY_URL = process.env.LLM_GATEWAY_URL || 'http://llm-gateway:3001';

// GET /api/templates?line=beach-houses&category=seasonal_promo
router.get('/', async (req, res) => {
  const { line, category } = req.query;
  let query = `
    SELECT t.*, pl.slug AS line_slug, pl.name AS line_name
    FROM pm_templates t
    LEFT JOIN pm_property_lines pl ON pl.id = t.line_id
    WHERE t.active = true
  `;
  const params = [];

  if (line) {
    params.push(line);
    query += ` AND (pl.slug = $${params.length} OR t.line_id IS NULL)`;
  }
  if (category) {
    params.push(category);
    query += ` AND t.category = $${params.length}`;
  }

  query += ' ORDER BY pl.id NULLS LAST, t.name';

  const { rows } = await pool.query(query, params);
  res.json(rows);
});

// GET /api/templates/:slug
router.get('/:slug', async (req, res) => {
  const { rows } = await pool.query(
    `SELECT t.*, pl.slug AS line_slug
     FROM pm_templates t
     LEFT JOIN pm_property_lines pl ON pl.id = t.line_id
     WHERE t.slug = $1`,
    [req.params.slug]
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found' });
  res.json(rows[0]);
});

/**
 * POST /api/templates/:slug/generate
 * Body: { property_id, variables: { key: value, ... } }
 *
 * Fills template variables from the property record + caller-supplied values,
 * calls the LLM Gateway, returns the generated post text.
 */
router.post('/:slug/generate', async (req, res) => {
  const { property_id, variables = {} } = req.body;

  // Fetch template
  const { rows: tmplRows } = await pool.query(
    'SELECT * FROM pm_templates WHERE slug = $1 AND active = true',
    [req.params.slug]
  );
  if (!tmplRows.length) return res.status(404).json({ error: 'Template not found' });
  const template = tmplRows[0];

  // Fetch property to auto-fill variables
  let property = null;
  if (property_id) {
    const { rows: propRows } = await pool.query(
      'SELECT * FROM pm_properties WHERE id = $1',
      [property_id]
    );
    if (propRows.length) property = propRows[0];
  }

  // Merge property fields + caller-supplied variables
  const merged = {
    max_length: template.max_length || 280,
    ...(property ? {
      property_name:    property.name,
      location:         property.location || '',
      beds:             property.beds || '',
      baths:            property.baths || '',
      base_rate:        property.base_rate || '',
      key_features:     (property.key_features || []).join(', '),
      brand_voice_notes: property.brand_voice_notes || '',
    } : {}),
    ...variables,
  };

  // Interpolate the prompt template
  let prompt = template.prompt_template;
  for (const [key, val] of Object.entries(merged)) {
    prompt = prompt.replaceAll(`{{${key}}}`, String(val));
  }

  // Call the gateway
  const gwRes = await fetch(`${GATEWAY_URL}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: [
        {
          role: 'system',
          content: `You are a skilled social media copywriter for a real estate marketing team. Write crisp, engaging posts exactly matching the requested tone. Return ONLY the post text — no commentary, no hashtag suggestions unless explicitly requested.${merged.brand_voice_notes ? '\n\nBrand voice notes: ' + merged.brand_voice_notes : ''}`,
        },
        { role: 'user', content: prompt },
      ],
      max_tokens: Math.ceil((merged.max_length || 280) * 1.5),
      temperature: 0.75,
    }),
  });

  if (!gwRes.ok) {
    const err = await gwRes.text().catch(() => '');
    return res.status(502).json({ error: 'Gateway error', detail: err.slice(0, 200) });
  }

  const gwJson = await gwRes.json();
  const generatedText = gwJson?.choices?.[0]?.message?.content?.trim() || '';

  res.json({
    template_slug: template.slug,
    property_id:   property?.id || null,
    generated:     generatedText,
    prompt_used:   prompt,
    variables:     merged,
  });
});

module.exports = router;
