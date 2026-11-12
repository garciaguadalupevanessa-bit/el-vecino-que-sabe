-- Store AI pre-review drafts separately from human decisions and verified aid rules.
CREATE TABLE IF NOT EXISTS bdns_ai_review_suggestions (
    suggestion_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code),
    payload_sha256 TEXT NOT NULL,
    model TEXT NOT NULL,
    suggestion JSONB NOT NULL CHECK (jsonb_typeof(suggestion) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bdns_ai_review_latest
    ON bdns_ai_review_suggestions (bdns_code, created_at DESC, suggestion_id DESC);

CREATE OR REPLACE FUNCTION prevent_bdns_ai_review_suggestion_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'BDNS AI review suggestions are append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS bdns_ai_review_suggestions_append_only ON bdns_ai_review_suggestions;
CREATE TRIGGER bdns_ai_review_suggestions_append_only
    BEFORE UPDATE OR DELETE ON bdns_ai_review_suggestions
    FOR EACH ROW EXECUTE FUNCTION prevent_bdns_ai_review_suggestion_mutation();
