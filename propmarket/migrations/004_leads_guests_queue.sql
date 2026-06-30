-- Migration 004: Leads, past guests, and approval queue

-- ── Leads (captured from lead forms + social DMs) ────────────────────────────
CREATE TABLE IF NOT EXISTS pm_leads (
  id             SERIAL PRIMARY KEY,
  property_id    INTEGER REFERENCES pm_properties(id) ON DELETE SET NULL,
  source         VARCHAR(50) NOT NULL DEFAULT 'form',  -- 'form'|'social_dm'|'email'|'manual'
  name           VARCHAR(200),
  email          VARCHAR(200),
  phone          VARCHAR(50),
  message        TEXT,
  move_in_date   DATE,
  stay_duration  VARCHAR(100),    -- e.g. '1 week' or 'Fall semester'
  status         VARCHAR(30) NOT NULL DEFAULT 'new',  -- 'new'|'contacted'|'qualified'|'lost'|'converted'
  metadata       JSONB DEFAULT '{}',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pm_leads_property  ON pm_leads(property_id);
CREATE INDEX IF NOT EXISTS idx_pm_leads_status    ON pm_leads(status);
CREATE INDEX IF NOT EXISTS idx_pm_leads_email     ON pm_leads(email);

DROP TRIGGER IF EXISTS pm_leads_updated_at ON pm_leads;
CREATE TRIGGER pm_leads_updated_at
  BEFORE UPDATE ON pm_leads
  FOR EACH ROW EXECUTE FUNCTION pm_set_updated_at();

-- ── Past guests (imported from Airbnb CSV exports) ────────────────────────────
CREATE TABLE IF NOT EXISTS pm_past_guests (
  id             SERIAL PRIMARY KEY,
  property_id    INTEGER REFERENCES pm_properties(id) ON DELETE SET NULL,
  name           VARCHAR(200),
  email          VARCHAR(200),
  phone          VARCHAR(50),
  check_in       DATE,
  check_out      DATE,
  nights         SMALLINT,
  source         VARCHAR(50) DEFAULT 'airbnb_csv',
  -- Winback campaign tracking
  last_contacted_at  TIMESTAMPTZ,
  opted_out          BOOLEAN NOT NULL DEFAULT FALSE,
  metadata           JSONB DEFAULT '{}',
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pm_past_guests_property ON pm_past_guests(property_id);
CREATE INDEX IF NOT EXISTS idx_pm_past_guests_email    ON pm_past_guests(email);
CREATE INDEX IF NOT EXISTS idx_pm_past_guests_opted_out ON pm_past_guests(opted_out);

-- Dedup: one guest record per (property, email) pair
CREATE UNIQUE INDEX IF NOT EXISTS idx_pm_past_guests_unique
  ON pm_past_guests(property_id, lower(email))
  WHERE email IS NOT NULL;

-- ── Approval queue (pending_actions from the agent) ───────────────────────────
CREATE TABLE IF NOT EXISTS pm_pending_actions (
  id             SERIAL PRIMARY KEY,
  action_type    VARCHAR(50) NOT NULL,
  -- 'post_draft'|'campaign_step'|'lead_reply'|'winback_email'|'winback_sms'|'social_reply'
  property_id    INTEGER REFERENCES pm_properties(id) ON DELETE SET NULL,
  -- Reference IDs (nullable depending on action_type)
  lead_id        INTEGER REFERENCES pm_leads(id) ON DELETE SET NULL,
  guest_id       INTEGER REFERENCES pm_past_guests(id) ON DELETE SET NULL,
  campaign_run_id INTEGER REFERENCES pm_campaign_runs(id) ON DELETE SET NULL,
  -- Content
  draft_content  TEXT NOT NULL,
  agent_reasoning TEXT,           -- LLM's explanation for why it drafted this
  -- Delivery target
  channel        VARCHAR(50),     -- 'email'|'sms'|'instagram'|'facebook'|etc.
  recipient_name  VARCHAR(200),
  recipient_email VARCHAR(200),
  recipient_phone VARCHAR(50),
  -- Scheduling (for posts)
  scheduled_for  TIMESTAMPTZ,
  postiz_org_id  VARCHAR(100),    -- Postiz org to publish to
  -- Status
  status         VARCHAR(20) NOT NULL DEFAULT 'pending',
  -- 'pending'|'approved'|'rejected'|'sent'|'failed'
  reviewed_at    TIMESTAMPTZ,
  reviewer_note  TEXT,
  -- Execution
  executed_at    TIMESTAMPTZ,
  execution_result JSONB DEFAULT '{}',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pm_pending_actions_status  ON pm_pending_actions(status);
CREATE INDEX IF NOT EXISTS idx_pm_pending_actions_type    ON pm_pending_actions(action_type);
CREATE INDEX IF NOT EXISTS idx_pm_pending_actions_property ON pm_pending_actions(property_id);
CREATE INDEX IF NOT EXISTS idx_pm_pending_actions_created ON pm_pending_actions(created_at DESC);

DROP TRIGGER IF EXISTS pm_pending_actions_updated_at ON pm_pending_actions;
CREATE TRIGGER pm_pending_actions_updated_at
  BEFORE UPDATE ON pm_pending_actions
  FOR EACH ROW EXECUTE FUNCTION pm_set_updated_at();
