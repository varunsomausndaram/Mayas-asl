'use strict';
const express = require('express');
const pool    = require('../db/pool');
const fetch   = require('node-fetch');

const router = express.Router();

const GATEWAY_URL = process.env.LLM_GATEWAY_URL || 'http://llm-gateway:3001';

// GET /api/leads?property_id=&status=new&line=beach-houses
router.get('/', async (req, res) => {
  const { property_id, status, line } = req.query;
  let query = `
    SELECT l.*, p.name AS property_name, pl.slug AS line_slug
    FROM pm_leads l
    LEFT JOIN pm_properties p  ON p.id = l.property_id
    LEFT JOIN pm_property_lines pl ON pl.id = p.line_id
    WHERE 1=1
  `;
  const params = [];
  if (property_id) { params.push(property_id); query += ` AND l.property_id = $${params.length}`; }
  if (status)      { params.push(status);      query += ` AND l.status = $${params.length}`; }
  if (line)        { params.push(line);         query += ` AND pl.slug = $${params.length}`; }
  query += ' ORDER BY l.created_at DESC';

  const { rows } = await pool.query(query, params);
  res.json(rows);
});

// GET /api/leads/:id
router.get('/:id', async (req, res) => {
  const { rows } = await pool.query(
    `SELECT l.*, p.name AS property_name, pl.slug AS line_slug
     FROM pm_leads l
     LEFT JOIN pm_properties p  ON p.id = l.property_id
     LEFT JOIN pm_property_lines pl ON pl.id = p.line_id
     WHERE l.id = $1`,
    [req.params.id]
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found' });
  res.json(rows[0]);
});

// POST /api/leads — public lead form submission (no auth required — called from lead form page)
router.post('/', async (req, res) => {
  const { property_id, source = 'form', name, email, phone, message, move_in_date, stay_duration, metadata = {} } = req.body;

  const { rows } = await pool.query(
    `INSERT INTO pm_leads
       (property_id, source, name, email, phone, message, move_in_date, stay_duration, metadata)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
     RETURNING *`,
    [property_id || null, source, name || null, email || null, phone || null,
     message || null, move_in_date || null, stay_duration || null, metadata]
  );

  const lead = rows[0];

  // Enqueue an agent action to qualify + draft a response (goes to approval queue)
  await enqueueDraftResponse(lead);

  res.status(201).json({ ok: true, id: lead.id });
});

// PATCH /api/leads/:id — update status
router.patch('/:id', async (req, res) => {
  const { status } = req.body;
  if (!status) return res.status(400).json({ error: 'status is required' });
  const { rows } = await pool.query(
    'UPDATE pm_leads SET status = $1 WHERE id = $2 RETURNING *',
    [status, req.params.id]
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found' });
  res.json(rows[0]);
});

/**
 * Call the LLM Gateway to qualify the lead and draft a reply,
 * then write a pending_action for the approval queue.
 */
async function enqueueDraftResponse(lead) {
  try {
    // Fetch property info if we have a property_id
    let propertyContext = '';
    if (lead.property_id) {
      const { rows } = await pool.query(
        'SELECT name, location, beds, baths, base_rate, key_features, brand_voice_notes FROM pm_properties WHERE id = $1',
        [lead.property_id]
      );
      if (rows.length) {
        const p = rows[0];
        propertyContext = `Property: ${p.name}, ${p.location || ''}. ${p.beds}bd/${p.baths}ba. Rate: $${p.base_rate}. Features: ${(p.key_features || []).join(', ')}.${p.brand_voice_notes ? ' Brand voice: ' + p.brand_voice_notes : ''}`;
      }
    }

    const prompt = `You are a friendly, professional property manager at Mani Marketing.
A new inquiry came in. Draft a warm, helpful response to this lead.
${propertyContext ? '\n' + propertyContext : ''}

Lead name: ${lead.name || 'Prospective Guest'}
Lead message: "${lead.message || '(no message provided)'}"
Move-in / stay date: ${lead.move_in_date || 'not specified'}
Duration: ${lead.stay_duration || 'not specified'}

Write the reply email/message body only. Be concise, friendly, and guide them toward booking directly.
Also provide a one-sentence qualification note (is this lead serious? high/medium/low priority?).

Format your response as JSON: {"reply": "...", "qualification": "..."}`;

    const gwRes = await fetch(`${GATEWAY_URL}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [{ role: 'user', content: prompt }],
        max_tokens: 600,
        temperature: 0.6,
      }),
    });

    let draftContent = '(Agent draft unavailable — reply manually)';
    let reasoning = '';

    if (gwRes.ok) {
      const gwJson = await gwRes.json();
      const raw = gwJson?.choices?.[0]?.message?.content?.trim() || '';
      try {
        const parsed = JSON.parse(raw);
        draftContent = parsed.reply || raw;
        reasoning = parsed.qualification || '';
      } catch {
        draftContent = raw;
      }
    }

    await pool.query(
      `INSERT INTO pm_pending_actions
         (action_type, property_id, lead_id, draft_content, agent_reasoning,
          channel, recipient_name, recipient_email, recipient_phone)
       VALUES ('lead_reply', $1, $2, $3, $4, $5, $6, $7, $8)`,
      [
        lead.property_id || null,
        lead.id,
        draftContent,
        reasoning,
        lead.email ? 'email' : (lead.phone ? 'sms' : 'manual'),
        lead.name || null,
        lead.email || null,
        lead.phone || null,
      ]
    );
  } catch (err) {
    // Non-fatal — the lead is still saved even if draft fails
    console.error('[leads] Failed to enqueue draft response:', err.message);
  }
}

module.exports = router;
