-- Migration 002: Listing-content template library

CREATE TABLE IF NOT EXISTS pm_templates (
  id           SERIAL PRIMARY KEY,
  -- null line_id = applies to all lines
  line_id      INTEGER REFERENCES pm_property_lines(id) ON DELETE SET NULL,
  slug         VARCHAR(100) UNIQUE NOT NULL,
  name         VARCHAR(200) NOT NULL,
  category     VARCHAR(50) NOT NULL,   -- 'seasonal_promo'|'last_minute'|'amenity'|'ugc_repost'
                                        -- 'availability'|'tour_invite'|'move_in_push'
  platform     VARCHAR(50),             -- null = generic; 'instagram'|'facebook'|etc.
  prompt_template TEXT NOT NULL,        -- Handlebars-style {{variable}} prompt sent to LLM
  variables    TEXT[] NOT NULL DEFAULT '{}',  -- list of required variable names
  example_output TEXT,                  -- cached/reference example
  tone         VARCHAR(50) DEFAULT 'friendly',
  max_length   SMALLINT DEFAULT 280,
  active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pm_templates_line ON pm_templates(line_id);
CREATE INDEX IF NOT EXISTS idx_pm_templates_category ON pm_templates(category);

-- ── Seed: Beach Houses templates ─────────────────────────────────────────────
INSERT INTO pm_templates (line_id, slug, name, category, platform, prompt_template, variables, tone, max_length)
SELECT
  pl.id,
  t.slug, t.name, t.category, t.platform, t.prompt_template, t.variables::TEXT[], t.tone, t.max_length
FROM pm_property_lines pl, (VALUES
  (
    'beach-seasonal-promo',
    'Beach House — Seasonal Promo',
    'seasonal_promo', NULL,
    $T$Write an engaging social media post promoting {{property_name}} in {{location}} for {{season}}. Highlight: {{key_features}}. Current rate: ${{base_rate}}/week. Include a direct booking call-to-action. Tone: warm, aspirational, vacation-ready. Max {{max_length}} characters.$T$,
    '{"property_name","location","season","key_features","base_rate","max_length"}',
    'aspirational', 280
  ),
  (
    'beach-last-minute',
    'Beach House — Last-Minute Deal',
    'last_minute', NULL,
    $T$Write an urgent last-minute deal post for {{property_name}} in {{location}}. Available: {{available_dates}}. Special rate: ${{deal_rate}}/week (normally ${{base_rate}}). Create urgency without being pushy. Emphasise direct booking. Max {{max_length}} characters.$T$,
    '{"property_name","location","available_dates","deal_rate","base_rate","max_length"}',
    'urgent', 280
  ),
  (
    'beach-amenity-highlight',
    'Beach House — Amenity Highlight',
    'amenity', NULL,
    $T$Write a social post spotlighting one specific amenity of {{property_name}}: {{amenity_name}}. Describe it vividly and explain why guests love it. Location: {{location}}. End with a soft booking nudge. Max {{max_length}} characters.$T$,
    '{"property_name","location","amenity_name","max_length"}',
    'vivid', 280
  ),
  (
    'beach-ugc-repost',
    'Beach House — Guest Review / UGC Repost',
    'ugc_repost', NULL,
    $T$Write a grateful social caption to accompany a guest review or photo of {{property_name}}. Quote or paraphrase the guest review: "{{guest_review}}". Express genuine appreciation and invite others to book directly. Max {{max_length}} characters.$T$,
    '{"property_name","guest_review","max_length"}',
    'grateful', 280
  )
) AS t(slug,name,category,platform,prompt_template,variables,tone,max_length)
WHERE pl.slug = 'beach-houses'
ON CONFLICT (slug) DO NOTHING;

-- ── Seed: Student Condos templates ───────────────────────────────────────────
INSERT INTO pm_templates (line_id, slug, name, category, platform, prompt_template, variables, tone, max_length)
SELECT
  pl.id,
  t.slug, t.name, t.category, t.platform, t.prompt_template, t.variables::TEXT[], t.tone, t.max_length
FROM pm_property_lines pl, (VALUES
  (
    'student-availability',
    'Student Condo — Availability',
    'availability', NULL,
    $T$Write a social post announcing availability at {{property_name}} for the {{academic_term}} term. Location near {{university}}. {{beds}} bed / {{baths}} bath. Rate: ${{base_rate}}/month. Key features: {{key_features}}. Direct inquiry link. Max {{max_length}} characters.$T$,
    '{"property_name","academic_term","university","beds","baths","base_rate","key_features","max_length"}',
    'informative', 280
  ),
  (
    'student-tour-invite',
    'Student Condo — Tour Invite',
    'tour_invite', NULL,
    $T$Write a social post inviting students to tour {{property_name}} near {{university}}. Tour dates: {{tour_dates}}. Mention {{key_features}}. Keep it friendly, student-focused, FOMO-inducing. Include direct contact/booking link. Max {{max_length}} characters.$T$,
    '{"property_name","university","tour_dates","key_features","max_length"}',
    'friendly', 280
  ),
  (
    'student-amenity-highlight',
    'Student Condo — Amenity / Location Highlight',
    'amenity', NULL,
    $T$Write a student-focused social post highlighting the {{amenity_name}} at {{property_name}}, near {{university}}. Explain why this matters to students. Subtle booking call-to-action. Max {{max_length}} characters.$T$,
    '{"property_name","university","amenity_name","max_length"}',
    'relatable', 280
  ),
  (
    'student-move-in-push',
    'Student Condo — Move-In Season Push',
    'move_in_push', NULL,
    $T$Write an urgent move-in season post for {{property_name}} near {{university}}. Move-in deadline / last units: {{urgency_note}}. Rate: ${{base_rate}}/month. Key features: {{key_features}}. Create urgency without pressure. Direct inquiry link. Max {{max_length}} characters.$T$,
    '{"property_name","university","urgency_note","base_rate","key_features","max_length"}',
    'urgent', 280
  )
) AS t(slug,name,category,platform,prompt_template,variables,tone,max_length)
WHERE pl.slug = 'student-condos'
ON CONFLICT (slug) DO NOTHING;
