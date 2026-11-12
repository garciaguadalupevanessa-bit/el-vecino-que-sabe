-- Auditable source-grounded agent verification/publication attempts.
CREATE TABLE IF NOT EXISTS bdns_ai_finalization_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code),
    payload_sha256 TEXT NOT NULL,
    extraction_fingerprint TEXT NOT NULL,
    model TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('published', 'needs_human_review', 'failed')),
    details JSONB NOT NULL CHECK (jsonb_typeof(details) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bdns_ai_finalization_latest
    ON bdns_ai_finalization_events (bdns_code, created_at DESC, event_id DESC);

CREATE OR REPLACE FUNCTION prevent_bdns_ai_finalization_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'BDNS AI finalization events are append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS bdns_ai_finalization_events_append_only ON bdns_ai_finalization_events;
CREATE TRIGGER bdns_ai_finalization_events_append_only
    BEFORE UPDATE OR DELETE ON bdns_ai_finalization_events
    FOR EACH ROW EXECUTE FUNCTION prevent_bdns_ai_finalization_mutation();
