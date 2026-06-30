-- Migration 001: Property lines and properties
-- Run by propmarket-api on startup via the main postgres instance.

CREATE TABLE IF NOT EXISTS pm_property_lines (
  id          SERIAL PRIMARY KEY,
  slug        VARCHAR(50) UNIQUE NOT NULL,  -- 'beach-houses' | 'student-condos'
  name        VARCHAR(100) NOT NULL,
  description TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the two lines defined in the spec
INSERT INTO pm_property_lines (slug, name, description)
VALUES
  ('beach-houses',   'Beach Houses',   'Weekly vacation rental properties')
 ,('student-condos', 'Student Condos', 'Academic-year lease properties')
ON CONFLICT (slug) DO NOTHING;

CREATE TABLE IF NOT EXISTS pm_properties (
  id               SERIAL PRIMARY KEY,
  line_id          INTEGER NOT NULL REFERENCES pm_property_lines(id) ON DELETE RESTRICT,
  slug             VARCHAR(100) UNIQUE NOT NULL,
  name             VARCHAR(200) NOT NULL,
  location         VARCHAR(200),
  beds             SMALLINT,
  baths            SMALLINT,
  max_guests       SMALLINT,
  base_rate        NUMERIC(10,2),        -- nightly/weekly depending on line
  hero_photo_url   TEXT,
  photo_urls       TEXT[],               -- additional photos
  key_features     TEXT[],               -- e.g. ['Ocean view','Hot tub','Free parking']
  amenities        JSONB DEFAULT '{}',
  brand_voice_notes TEXT,               -- fed to the LLM when generating content
  active           BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pm_properties_line ON pm_properties(line_id);
CREATE INDEX IF NOT EXISTS idx_pm_properties_active ON pm_properties(active);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION pm_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

DROP TRIGGER IF EXISTS pm_properties_updated_at ON pm_properties;
CREATE TRIGGER pm_properties_updated_at
  BEFORE UPDATE ON pm_properties
  FOR EACH ROW EXECUTE FUNCTION pm_set_updated_at();
