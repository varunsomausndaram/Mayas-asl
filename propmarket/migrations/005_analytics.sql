-- Migration 005: Analytics overlay
-- Tracks funnel events: reach → engagement → leads → direct inquiries/bookings

CREATE TABLE IF NOT EXISTS pm_analytics_events (
  id           BIGSERIAL PRIMARY KEY,
  property_id  INTEGER REFERENCES pm_properties(id) ON DELETE SET NULL,
  -- 'reach'|'engagement'|'lead'|'inquiry'|'direct_booking'|'spend'
  event_type   VARCHAR(30) NOT NULL,
  channel      VARCHAR(50),        -- 'instagram'|'facebook'|'email'|'sms'|'direct'|etc.
  value        NUMERIC(12,2) DEFAULT 1,  -- count or spend amount
  period_start DATE NOT NULL,
  period_end   DATE NOT NULL,
  metadata     JSONB DEFAULT '{}',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pm_analytics_property ON pm_analytics_events(property_id);
CREATE INDEX IF NOT EXISTS idx_pm_analytics_type     ON pm_analytics_events(event_type);
CREATE INDEX IF NOT EXISTS idx_pm_analytics_period   ON pm_analytics_events(period_start, period_end);

-- Convenience view: funnel summary per property per month
CREATE OR REPLACE VIEW pm_funnel_summary AS
SELECT
  p.id                  AS property_id,
  p.name                AS property_name,
  pl.slug               AS line_slug,
  pl.name               AS line_name,
  date_trunc('month', ae.period_start) AS month,
  ae.event_type,
  ae.channel,
  SUM(ae.value)         AS total
FROM pm_analytics_events ae
JOIN pm_properties p    ON p.id  = ae.property_id
JOIN pm_property_lines pl ON pl.id = p.line_id
GROUP BY p.id, p.name, pl.slug, pl.name,
         date_trunc('month', ae.period_start), ae.event_type, ae.channel;
