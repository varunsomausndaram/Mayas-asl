'use strict';
const express  = require('express');
const multer   = require('multer');
const { parse } = require('csv-parse/sync');
const pool     = require('../db/pool');
const fetch    = require('node-fetch');

const router  = express.Router();
const upload  = multer({ storage: multer.memoryStorage(), limits: { fileSize: 5 * 1024 * 1024 } });

const GATEWAY_URL = process.env.LLM_GATEWAY_URL || 'http://llm-gateway:3001';

// GET /api/past-guests?property_id=&opted_out=false
router.get('/', async (req, res) => {
  const { property_id, opted_out, line } = req.query;
  let query = `
    SELECT g.*, p.name AS property_name, pl.slug AS line_slug
    FROM pm_past_guests g
    LEFT JOIN pm_properties p  ON p.id = g.property_id
    LEFT JOIN pm_property_lines pl ON pl.id = p.line_id
    WHERE 1=1
  `;
  const params = [];
  if (property_id) { params.push(property_id); query += ` AND g.property_id = $${params.length}`; }
  if (opted_out !== undefined) { params.push(opted_out !== 'false'); query += ` AND g.opted_out = $${params.length}`; }
  if (line) { params.push(line); query += ` AND pl.slug = $${params.length}`; }
  query += ' ORDER BY g.check_in DESC NULLS LAST';

  const { rows } = await pool.query(query, params);
  res.json(rows);
});

/**
 * POST /api/past-guests/import
 * Accepts a CSV upload (Airbnb export format).
 * Expected columns (case-insensitive): name, email, phone, check_in, check_out, nights
 * Additional columns are stored in metadata.
 */
router.post('/import', upload.single('csv'), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No CSV file provided' });

  const { property_id } = req.body;

  let records;
  try {
    records = parse(req.file.buffer, {
      columns: (header) => header.map((h) => h.toLowerCase().trim().replace(/\s+/g, '_')),
      skip_empty_lines: true,
      trim: true,
    });
  } catch (err) {
    return res.status(400).json({ error: 'CSV parse error: ' + err.message });
  }

  let inserted = 0, skipped = 0;
  for (const row of records) {
    try {
      await pool.query(
        `INSERT INTO pm_past_guests
           (property_id, name, email, phone, check_in, check_out, nights, source, metadata)
         VALUES ($1, $2, $3, $4, $5, $6, $7, 'airbnb_csv', $8)
         ON CONFLICT (property_id, lower(email)) DO NOTHING`,
        [
          property_id || null,
          row.name || row.guest_name || null,
          row.email || null,
          row.phone || null,
          row.check_in || row.checkin || null,
          row.check_out || row.checkout || null,
          row.nights ? parseInt(row.nights, 10) : null,
          JSON.stringify(row),
        ]
      );
      inserted++;
    } catch {
      skipped++;
    }
  }

  res.json({ ok: true, total: records.length, inserted, skipped });
});

/**
 * POST /api/past-guests/winback-campaign
 * Body: { property_id, season, campaign_type, guest_ids? }
 * Enqueues win-back email drafts for all eligible guests (or specified guest_ids)
 * → approval queue. Sends nothing automatically.
 */
router.post('/winback-campaign', async (req, res) => {
  const { property_id, season = 'upcoming season', campaign_type = 'seasonal_winback', guest_ids } = req.body;
  if (!property_id) return res.status(400).json({ error: 'property_id is required' });

  // Fetch property details
  const { rows: propRows } = await pool.query(
    'SELECT * FROM pm_properties WHERE id = $1 AND active = true',
    [property_id]
  );
  if (!propRows.length) return res.status(404).json({ error: 'Property not found' });
  const property = propRows[0];

  // Fetch eligible guests
  let guestQuery = `
    SELECT * FROM pm_past_guests
    WHERE property_id = $1
      AND opted_out = false
      AND email IS NOT NULL
  `;
  const params = [property_id];
  if (guest_ids && guest_ids.length) {
    params.push(guest_ids);
    guestQuery += ` AND id = ANY($${params.length})`;
  }

  const { rows: guests } = await pool.query(guestQuery, params);
  if (!guests.length) return res.json({ ok: true, queued: 0, message: 'No eligible guests found' });

  let queued = 0;
  for (const guest of guests) {
    try {
      const draft = await generateWinbackEmail({ guest, property, season, campaign_type });
      await pool.query(
        `INSERT INTO pm_pending_actions
           (action_type, property_id, guest_id, draft_content, agent_reasoning,
            channel, recipient_name, recipient_email, recipient_phone)
         VALUES ('winback_email', $1, $2, $3, $4, 'email', $5, $6, $7)`,
        [
          property_id, guest.id,
          draft.content, draft.reasoning,
          guest.name, guest.email, guest.phone || null,
        ]
      );
      queued++;
    } catch (err) {
      console.error('[guests] Failed to enqueue winback for guest', guest.id, err.message);
    }
  }

  // Mark guests as contacted
  await pool.query(
    'UPDATE pm_past_guests SET last_contacted_at = NOW() WHERE id = ANY($1)',
    [guests.map((g) => g.id)]
  );

  res.json({ ok: true, queued, total_guests: guests.length });
});

// PATCH /api/past-guests/:id/opt-out
router.patch('/:id/opt-out', async (req, res) => {
  const { rows } = await pool.query(
    'UPDATE pm_past_guests SET opted_out = true WHERE id = $1 RETURNING id',
    [req.params.id]
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found' });
  res.json({ ok: true });
});

async function generateWinbackEmail({ guest, property, season, campaign_type }) {
  const prompt = `Write a warm, personalised win-back email to a past guest of ${property.name}.

Guest: ${guest.name || 'Guest'}, last stayed ${guest.check_in ? `check-in ${guest.check_in}` : 'previously'}.
Property: ${property.name}, ${property.location || ''}. ${property.beds}bd/${property.baths}ba. Rate: $${property.base_rate}.
Key features: ${(property.key_features || []).join(', ')}.
Season/campaign: ${season}.
Campaign type: ${campaign_type}.

Goal: invite them to book directly (not through Airbnb) for the upcoming season.
Tone: warm, personal, not salesy. Short — 3–4 sentences max.

Return JSON: {"subject": "...", "body": "...", "reasoning": "one sentence on why this guest is a good winback candidate"}`;

  try {
    const gwRes = await fetch(`${GATEWAY_URL}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [{ role: 'user', content: prompt }],
        max_tokens: 400,
        temperature: 0.7,
      }),
    });

    if (!gwRes.ok) throw new Error(`Gateway ${gwRes.status}`);
    const json = await gwRes.json();
    const raw = json?.choices?.[0]?.message?.content?.trim() || '';

    try {
      const parsed = JSON.parse(raw);
      return {
        content: `Subject: ${parsed.subject}\n\n${parsed.body}`,
        reasoning: parsed.reasoning || '',
      };
    } catch {
      return { content: raw, reasoning: '' };
    }
  } catch {
    return {
      content: `Hi ${guest.name || 'there'},\n\nWe'd love to have you back at ${property.name} this ${season}. Book directly for the best rate!\n\n— The ${property.name} team`,
      reasoning: 'Fallback template (gateway unavailable)',
    };
  }
}

module.exports = router;
