'use strict';
/**
 * Approval queue API.
 * All agent-proposed actions land here as 'pending'.
 * Owner approves / edits / rejects from the mobile-first queue UI.
 * Approved actions are executed (post to Postiz API, send email/SMS) by the executor.
 */
const express = require('express');
const pool    = require('../db/pool');
const fetch   = require('node-fetch');

const router = express.Router();

const POSTIZ_URL         = process.env.POSTIZ_INTERNAL_URL || 'http://postiz:5000';
const POSTIZ_API_KEY     = process.env.POSTIZ_API_KEY || '';

// GET /api/queue?status=pending&action_type=lead_reply&line=beach-houses
router.get('/', async (req, res) => {
  const { status = 'pending', action_type, line, property_id } = req.query;
  let query = `
    SELECT pa.*,
           p.name  AS property_name, pl.slug AS line_slug,
           l.name  AS lead_name,  l.email AS lead_email,
           g.name  AS guest_name, g.email AS guest_email
    FROM pm_pending_actions pa
    LEFT JOIN pm_properties p    ON p.id  = pa.property_id
    LEFT JOIN pm_property_lines pl ON pl.id = p.line_id
    LEFT JOIN pm_leads         l  ON l.id  = pa.lead_id
    LEFT JOIN pm_past_guests   g  ON g.id  = pa.guest_id
    WHERE 1=1
  `;
  const params = [];
  if (status)      { params.push(status);      query += ` AND pa.status = $${params.length}`; }
  if (action_type) { params.push(action_type); query += ` AND pa.action_type = $${params.length}`; }
  if (line)        { params.push(line);         query += ` AND pl.slug = $${params.length}`; }
  if (property_id) { params.push(property_id); query += ` AND pa.property_id = $${params.length}`; }
  query += ' ORDER BY pa.created_at DESC LIMIT 100';

  const { rows } = await pool.query(query, params);
  res.json(rows);
});

// GET /api/queue/stats — counts by status (for dashboard badge)
router.get('/stats', async (_req, res) => {
  const { rows } = await pool.query(
    `SELECT status, action_type, COUNT(*) AS count
     FROM pm_pending_actions
     GROUP BY status, action_type
     ORDER BY status, action_type`
  );
  res.json(rows);
});

// GET /api/queue/:id
router.get('/:id', async (req, res) => {
  const { rows } = await pool.query(
    `SELECT pa.*,
            p.name AS property_name, pl.slug AS line_slug
     FROM pm_pending_actions pa
     LEFT JOIN pm_properties p    ON p.id  = pa.property_id
     LEFT JOIN pm_property_lines pl ON pl.id = p.line_id
     WHERE pa.id = $1`,
    [req.params.id]
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found' });
  res.json(rows[0]);
});

/**
 * POST /api/queue/:id/approve
 * Body: { edited_content? }  — optionally override the draft before executing
 * Marks as approved + triggers execution.
 */
router.post('/:id/approve', async (req, res) => {
  const { edited_content } = req.body;

  const { rows } = await pool.query(
    `UPDATE pm_pending_actions
     SET status = 'approved',
         reviewed_at = NOW(),
         draft_content = COALESCE($2, draft_content)
     WHERE id = $1 AND status = 'pending'
     RETURNING *`,
    [req.params.id, edited_content || null]
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found or not pending' });

  const action = rows[0];

  // Execute the action asynchronously — don't wait for delivery
  executeAction(action).catch((err) =>
    console.error('[queue] Execution failed for action', action.id, err.message)
  );

  res.json({ ok: true, action });
});

/**
 * POST /api/queue/:id/reject
 */
router.post('/:id/reject', async (req, res) => {
  const { reviewer_note } = req.body;
  const { rows } = await pool.query(
    `UPDATE pm_pending_actions
     SET status = 'rejected', reviewed_at = NOW(), reviewer_note = $2
     WHERE id = $1 AND status = 'pending'
     RETURNING id, status`,
    [req.params.id, reviewer_note || null]
  );
  if (!rows.length) return res.status(404).json({ error: 'Not found or not pending' });
  res.json({ ok: true, id: rows[0].id });
});

/**
 * Execute an approved action — routes to the right delivery channel.
 * Postiz handles social posting; email/SMS uses configured providers.
 */
async function executeAction(action) {
  let result = {};
  try {
    if (['post_draft', 'campaign_step'].includes(action.action_type)) {
      result = await postToPostiz(action);
    } else if (['lead_reply', 'winback_email'].includes(action.action_type)) {
      result = await sendEmail(action);
    } else if (action.action_type === 'winback_sms') {
      result = await sendSms(action);
    }

    await pool.query(
      `UPDATE pm_pending_actions
       SET status = 'sent', executed_at = NOW(), execution_result = $2
       WHERE id = $1`,
      [action.id, result]
    );
  } catch (err) {
    await pool.query(
      `UPDATE pm_pending_actions
       SET status = 'failed', executed_at = NOW(),
           execution_result = $2
       WHERE id = $1`,
      [action.id, { error: err.message }]
    );
    throw err;
  }
}

async function postToPostiz(action) {
  if (!POSTIZ_API_KEY) return { skipped: true, reason: 'POSTIZ_API_KEY not configured' };

  const body = {
    content: action.draft_content,
    date:    action.scheduled_for || new Date(Date.now() + 5 * 60 * 1000).toISOString(),
  };

  const res = await fetch(`${POSTIZ_URL}/api/posts`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${POSTIZ_API_KEY}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Postiz API ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}

async function sendEmail(action) {
  // Email delivery is handled by n8n workflows triggered via webhook.
  // This stub logs the intent; the n8n workflow picks it up.
  // In Phase 4 / full deployment, replace with direct SMTP/Resend call.
  const payload = {
    to:      action.recipient_email,
    name:    action.recipient_name,
    subject: extractSubject(action.draft_content),
    body:    action.draft_content,
    action_id: action.id,
  };

  const webhookUrl = process.env.N8N_EMAIL_WEBHOOK_URL;
  if (webhookUrl) {
    const res = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return { webhook_status: res.status };
  }

  console.log('[queue] Email send (no webhook configured):', payload.to, payload.subject);
  return { logged: true, payload };
}

async function sendSms(action) {
  const payload = {
    to:       action.recipient_phone,
    message:  action.draft_content,
    action_id: action.id,
  };

  const webhookUrl = process.env.N8N_SMS_WEBHOOK_URL;
  if (webhookUrl) {
    const res = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return { webhook_status: res.status };
  }

  console.log('[queue] SMS send (no webhook configured):', payload.to);
  return { logged: true, payload };
}

function extractSubject(content) {
  const match = content.match(/^Subject:\s*(.+)/m);
  return match ? match[1].trim() : 'Message from Mani Marketing';
}

module.exports = router;
