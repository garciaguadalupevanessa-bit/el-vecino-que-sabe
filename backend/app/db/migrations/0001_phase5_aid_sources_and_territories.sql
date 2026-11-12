-- Link user-facing aids to campaign-specific BDNS source records and keep
-- their normalized applicability and reviewer history queryable.
CREATE TABLE IF NOT EXISTS aid_territories (
    aid_id TEXT NOT NULL REFERENCES aids (id),
    territory_level TEXT NOT NULL CHECK (territory_level IN (
        'national', 'autonomous_community', 'province', 'municipality'
    )),
    territory_code TEXT,
    territory_name TEXT NOT NULL,
    parent_code TEXT,
    PRIMARY KEY (aid_id, territory_level, territory_name)
);
CREATE INDEX IF NOT EXISTS idx_aid_territories_lookup
    ON aid_territories (territory_level, territory_code, lower(territory_name));

CREATE TABLE IF NOT EXISTS aid_bdns_calls (
    aid_id TEXT NOT NULL REFERENCES aids (id) ON DELETE CASCADE,
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code),
    campaign_year INTEGER CHECK (campaign_year IS NULL OR campaign_year BETWEEN 1900 AND 2200),
    campaign_label TEXT,
    status TEXT NOT NULL CHECK (status IN ('discovered', 'extracted', 'reviewed', 'verified', 'withdrawn')),
    linked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (aid_id, bdns_code)
);
CREATE INDEX IF NOT EXISTS idx_aid_bdns_calls_code ON aid_bdns_calls (bdns_code, aid_id);

CREATE TABLE IF NOT EXISTS aid_review_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    aid_id TEXT NOT NULL REFERENCES aids (id),
    bdns_code TEXT REFERENCES bdns_calls (bdns_code),
    event_fingerprint TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('reviewed', 'accepted_for_extraction', 'verified', 'reopened', 'rejected')),
    notes TEXT NOT NULL DEFAULT '',
    citations JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(citations) = 'array'),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (aid_id, event_fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_aid_review_events_aid ON aid_review_events (aid_id, created_at DESC, event_id DESC);

CREATE OR REPLACE FUNCTION prevent_aid_review_event_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Aid review history is append-only';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS aid_review_events_append_only ON aid_review_events;
CREATE TRIGGER aid_review_events_append_only
    BEFORE UPDATE OR DELETE ON aid_review_events
    FOR EACH ROW EXECUTE FUNCTION prevent_aid_review_event_mutation();
