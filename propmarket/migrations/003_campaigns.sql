-- Migration 003: Seasonal campaign presets

CREATE TABLE IF NOT EXISTS pm_campaign_presets (
  id          SERIAL PRIMARY KEY,
  line_id     INTEGER NOT NULL REFERENCES pm_property_lines(id) ON DELETE CASCADE,
  slug        VARCHAR(100) UNIQUE NOT NULL,
  name        VARCHAR(200) NOT NULL,
  -- 'student_fill_cycle' | 'beach_season_cycle'
  preset_type VARCHAR(50) NOT NULL,
  description TEXT,
  -- JSON array of steps: [{week_offset, template_slug, variables_defaults, channels}]
  steps       JSONB NOT NULL DEFAULT '[]',
  -- default config for campaign scheduling
  default_config JSONB NOT NULL DEFAULT '{}',
  active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pm_campaigns_line ON pm_campaign_presets(line_id);

-- ── Seed: Student fill cycle ──────────────────────────────────────────────────
INSERT INTO pm_campaign_presets (line_id, slug, name, preset_type, description, steps, default_config)
SELECT
  pl.id,
  'student-fill-cycle',
  'Student Fill Cycle',
  'student_fill_cycle',
  'Academic-year lead generation campaign — Jan through Apr for fall move-in. Runs a cadence of availability, tour-invite, amenity, and urgency posts.',
  '[
    {"week_offset": 0,  "template_slug": "student-availability",      "label": "Open availability announcement",   "channels": ["instagram","facebook"]},
    {"week_offset": 1,  "template_slug": "student-amenity-highlight",  "label": "Amenity spotlight",                "channels": ["instagram"]},
    {"week_offset": 2,  "template_slug": "student-tour-invite",        "label": "Tour invite",                      "channels": ["instagram","facebook"]},
    {"week_offset": 4,  "template_slug": "student-availability",       "label": "Availability reminder",            "channels": ["instagram","facebook"]},
    {"week_offset": 6,  "template_slug": "student-amenity-highlight",  "label": "Second amenity spotlight",         "channels": ["instagram"]},
    {"week_offset": 8,  "template_slug": "student-tour-invite",        "label": "Second tour invite",               "channels": ["instagram","facebook"]},
    {"week_offset": 10, "template_slug": "student-move-in-push",       "label": "Move-in urgency push",             "channels": ["instagram","facebook"]},
    {"week_offset": 12, "template_slug": "student-move-in-push",       "label": "Final availability push",          "channels": ["instagram","facebook"]}
  ]'::JSONB,
  '{"start_month": 1, "start_day": 15, "lead_window_weeks": 16, "post_time": "10:00", "timezone": "America/New_York"}'::JSONB
FROM pm_property_lines pl WHERE pl.slug = 'student-condos'
ON CONFLICT (slug) DO NOTHING;

-- ── Seed: Beach season cycle ──────────────────────────────────────────────────
INSERT INTO pm_campaign_presets (line_id, slug, name, preset_type, description, steps, default_config)
SELECT
  pl.id,
  'beach-season-cycle',
  'Beach Season Cycle',
  'beach_season_cycle',
  'Full-year beach rental campaign — peak summer promo, shoulder-season fill, and last-minute week alerts.',
  '[
    {"week_offset": 0,  "template_slug": "beach-seasonal-promo",    "label": "Summer season launch",            "channels": ["instagram","facebook"]},
    {"week_offset": 2,  "template_slug": "beach-amenity-highlight",  "label": "Amenity spotlight",               "channels": ["instagram"]},
    {"week_offset": 4,  "template_slug": "beach-seasonal-promo",    "label": "Peak season push",                "channels": ["instagram","facebook"]},
    {"week_offset": 6,  "template_slug": "beach-ugc-repost",        "label": "Guest review highlight",          "channels": ["instagram","facebook"]},
    {"week_offset": 8,  "template_slug": "beach-last-minute",       "label": "Last-minute week deal",           "channels": ["instagram","facebook"]},
    {"week_offset": 10, "template_slug": "beach-amenity-highlight",  "label": "Second amenity spotlight",        "channels": ["instagram"]},
    {"week_offset": 12, "template_slug": "beach-seasonal-promo",    "label": "Shoulder season promo",           "channels": ["instagram","facebook"]},
    {"week_offset": 14, "template_slug": "beach-last-minute",       "label": "Shoulder season last-minute",     "channels": ["instagram","facebook"]},
    {"week_offset": 16, "template_slug": "beach-ugc-repost",        "label": "End-of-season social proof",      "channels": ["instagram","facebook"]}
  ]'::JSONB,
  '{"start_month": 4, "start_day": 1, "lead_window_weeks": 20, "post_time": "09:00", "timezone": "America/New_York"}'::JSONB
FROM pm_property_lines pl WHERE pl.slug = 'beach-houses'
ON CONFLICT (slug) DO NOTHING;

-- Campaign runs — tracks each time a preset is started for a specific property
CREATE TABLE IF NOT EXISTS pm_campaign_runs (
  id           SERIAL PRIMARY KEY,
  preset_id    INTEGER NOT NULL REFERENCES pm_campaign_presets(id) ON DELETE CASCADE,
  property_id  INTEGER NOT NULL REFERENCES pm_properties(id) ON DELETE CASCADE,
  status       VARCHAR(20) NOT NULL DEFAULT 'active',  -- 'active'|'paused'|'completed'|'cancelled'
  start_date   DATE NOT NULL,
  config       JSONB NOT NULL DEFAULT '{}',  -- overrides for this run
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS pm_campaign_runs_updated_at ON pm_campaign_runs;
CREATE TRIGGER pm_campaign_runs_updated_at
  BEFORE UPDATE ON pm_campaign_runs
  FOR EACH ROW EXECUTE FUNCTION pm_set_updated_at();

CREATE INDEX IF NOT EXISTS idx_pm_campaign_runs_property ON pm_campaign_runs(property_id);
CREATE INDEX IF NOT EXISTS idx_pm_campaign_runs_status   ON pm_campaign_runs(status);
