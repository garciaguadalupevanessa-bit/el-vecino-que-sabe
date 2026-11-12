-- Keep automatic source-scope decisions auditable and separate from human review history.
CREATE TABLE IF NOT EXISTS bdns_ai_review_decisions (
    decision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code),
    payload_sha256 TEXT NOT NULL,
    suggestion_id BIGINT NOT NULL REFERENCES bdns_ai_review_suggestions (suggestion_id),
    decision TEXT NOT NULL CHECK (decision IN ('accepted_for_extraction', 'out_of_scope')),
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bdns_ai_decision_latest
    ON bdns_ai_review_decisions (bdns_code, created_at DESC, decision_id DESC);

CREATE OR REPLACE FUNCTION prevent_bdns_ai_review_decision_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'BDNS AI review decisions are append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS bdns_ai_review_decisions_append_only ON bdns_ai_review_decisions;
CREATE TRIGGER bdns_ai_review_decisions_append_only
    BEFORE UPDATE OR DELETE ON bdns_ai_review_decisions
    FOR EACH ROW EXECUTE FUNCTION prevent_bdns_ai_review_decision_mutation();
