-- Idempotent schema: applied at startup and by the seed script.
CREATE TABLE IF NOT EXISTS aids (
    id           TEXT PRIMARY KEY,
    scope        TEXT NOT NULL,
    reliability  TEXT NOT NULL CHECK (reliability IN ('verified', 'extracted', 'metadata_only')),
    data         JSONB NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_aids_scope ON aids (scope);

-- Source call records stay separate from user-facing, reviewed aid rules.
CREATE TABLE IF NOT EXISTS bdns_calls (
    bdns_code   TEXT PRIMARY KEY,
    bdns_id     BIGINT,
    reliability TEXT NOT NULL DEFAULT 'metadata_only'
                CHECK (reliability IN ('verified', 'extracted', 'metadata_only')),
    data        JSONB NOT NULL,
    payload_sha256 TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending_review'
                  CHECK (review_status IN (
                      'pending_review', 'review_required', 'reviewed',
                      'accepted_for_extraction', 'out_of_scope'
                  )),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE bdns_calls ADD COLUMN IF NOT EXISTS payload_sha256 TEXT;
ALTER TABLE bdns_calls ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'pending_review'
    CHECK (review_status IN (
        'pending_review', 'review_required', 'reviewed',
        'accepted_for_extraction', 'out_of_scope'
    ));
ALTER TABLE bdns_calls DROP CONSTRAINT IF EXISTS bdns_calls_review_status_check;
ALTER TABLE bdns_calls ADD CONSTRAINT bdns_calls_review_status_check CHECK (review_status IN (
    'pending_review', 'review_required', 'reviewed',
    'accepted_for_extraction', 'out_of_scope'
));
CREATE INDEX IF NOT EXISTS idx_bdns_calls_reliability ON bdns_calls (reliability);

-- Current BDNS region tree, refreshed alongside bounded imports.
CREATE TABLE IF NOT EXISTS bdns_regions (
    region_id INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    nuts_code TEXT,
    parent_region_id INTEGER REFERENCES bdns_regions (region_id) ON DELETE SET NULL,
    depth INTEGER NOT NULL CHECK (depth >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Persist bounded import attempts and their per-region, per-term coverage evidence.
CREATE TABLE IF NOT EXISTS bdns_import_runs (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    region_ids JSONB NOT NULL,
    search_terms JSONB NOT NULL,
    max_pages INTEGER NOT NULL CHECK (max_pages > 0),
    page_size INTEGER NOT NULL CHECK (page_size > 0),
    candidate_count INTEGER NOT NULL DEFAULT 0 CHECK (candidate_count >= 0),
    indexed_call_count INTEGER NOT NULL DEFAULT 0 CHECK (indexed_call_count >= 0),
    error_summary TEXT
);
CREATE INDEX IF NOT EXISTS idx_bdns_import_runs_started ON bdns_import_runs (started_at DESC);

CREATE TABLE IF NOT EXISTS bdns_import_run_queries (
    query_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES bdns_import_runs (run_id) ON DELETE CASCADE,
    region_id INTEGER NOT NULL,
    search_term TEXT NOT NULL,
    activity_scope TEXT NOT NULL CHECK (activity_scope IN ('agriculture', 'livestock', 'mixed', 'unknown')),
    candidate_count INTEGER NOT NULL CHECK (candidate_count >= 0),
    indexed_call_count INTEGER NOT NULL CHECK (indexed_call_count >= 0),
    page_limit_reached BOOLEAN NOT NULL,
    queried_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, region_id, search_term)
);
CREATE INDEX IF NOT EXISTS idx_bdns_import_queries_region ON bdns_import_run_queries (region_id, queried_at DESC);

-- Exact record membership enables reviewer filters by import run and territory.
CREATE TABLE IF NOT EXISTS bdns_import_run_calls (
    run_id BIGINT NOT NULL REFERENCES bdns_import_runs (run_id) ON DELETE CASCADE,
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code) ON DELETE CASCADE,
    region_id INTEGER NOT NULL,
    search_term TEXT NOT NULL,
    PRIMARY KEY (run_id, bdns_code, region_id, search_term)
);
CREATE INDEX IF NOT EXISTS idx_bdns_import_run_calls_region
    ON bdns_import_run_calls (region_id, run_id, bdns_code);
CREATE INDEX IF NOT EXISTS idx_bdns_import_run_calls_code
    ON bdns_import_run_calls (bdns_code, run_id);

-- Append-only source review decisions; these never promote an aid to verified.
CREATE TABLE IF NOT EXISTS bdns_call_reviews (
    review_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code) ON DELETE CASCADE,
    payload_sha256 TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('accepted_for_extraction', 'out_of_scope')),
    notes TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Keep review decisions as a durable audit trail, even if a source call is retired.
ALTER TABLE bdns_call_reviews DROP CONSTRAINT IF EXISTS bdns_call_reviews_bdns_code_fkey;
ALTER TABLE bdns_call_reviews ADD CONSTRAINT bdns_call_reviews_bdns_code_fkey
    FOREIGN KEY (bdns_code) REFERENCES bdns_calls (bdns_code);
CREATE INDEX IF NOT EXISTS idx_bdns_call_reviews_code ON bdns_call_reviews (bdns_code, created_at DESC);

-- Human-confirmed activity/category/campaign assignments, separate from eligibility verification.
CREATE TABLE IF NOT EXISTS bdns_call_classification_events (
    classification_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code),
    payload_sha256 TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    activities JSONB NOT NULL CHECK (jsonb_typeof(activities) = 'array'),
    categories JSONB NOT NULL CHECK (jsonb_typeof(categories) = 'array'),
    campaign_year INTEGER,
    campaign_label TEXT,
    evidence JSONB NOT NULL CHECK (jsonb_typeof(evidence) = 'array'),
    notes TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bdns_classification_latest
    ON bdns_call_classification_events (bdns_code, created_at DESC, classification_event_id DESC);
CREATE OR REPLACE FUNCTION prevent_bdns_classification_event_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'BDNS classification history is append-only';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS bdns_classification_events_append_only ON bdns_call_classification_events;
CREATE TRIGGER bdns_classification_events_append_only
    BEFORE UPDATE OR DELETE ON bdns_call_classification_events
    FOR EACH ROW EXECUTE FUNCTION prevent_bdns_classification_event_mutation();

CREATE OR REPLACE FUNCTION prevent_bdns_review_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'BDNS review history is append-only';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS bdns_call_reviews_append_only ON bdns_call_reviews;
CREATE TRIGGER bdns_call_reviews_append_only
    BEFORE UPDATE OR DELETE ON bdns_call_reviews
    FOR EACH ROW EXECUTE FUNCTION prevent_bdns_review_mutation();

-- Human approval of source-backed rules is distinct from extraction review.
-- Every activation and reopening is retained as an immutable event.
CREATE TABLE IF NOT EXISTS bdns_call_verification_events (
    verification_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code),
    event_type TEXT NOT NULL CHECK (event_type IN ('verified', 'reopened')),
    payload_sha256 TEXT NOT NULL,
    document_fingerprint TEXT NOT NULL,
    extraction_fingerprint TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    notes TEXT NOT NULL,
    approved_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bdns_call_verification_latest
    ON bdns_call_verification_events (bdns_code, created_at DESC, verification_event_id DESC);
CREATE OR REPLACE FUNCTION prevent_bdns_call_verification_event_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'BDNS verification history is append-only';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS bdns_call_verification_events_append_only ON bdns_call_verification_events;
CREATE TRIGGER bdns_call_verification_events_append_only
    BEFORE UPDATE OR DELETE ON bdns_call_verification_events
    FOR EACH ROW EXECUTE FUNCTION prevent_bdns_call_verification_event_mutation();

-- Immutable canonical source snapshots and the change events between them.
CREATE TABLE IF NOT EXISTS bdns_call_snapshots (
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code) ON DELETE CASCADE,
    payload_sha256 TEXT NOT NULL,
    source_payload JSONB NOT NULL,
    canonical_record JSONB NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (bdns_code, payload_sha256)
);
CREATE TABLE IF NOT EXISTS bdns_call_changes (
    change_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('discovered', 'changed')),
    previous_sha256 TEXT,
    current_sha256 TEXT NOT NULL,
    changed_paths JSONB NOT NULL DEFAULT '[]'::jsonb,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (bdns_code, previous_sha256)
        REFERENCES bdns_call_snapshots (bdns_code, payload_sha256),
    FOREIGN KEY (bdns_code, current_sha256)
        REFERENCES bdns_call_snapshots (bdns_code, payload_sha256)
);
CREATE INDEX IF NOT EXISTS idx_bdns_call_changes_code ON bdns_call_changes (bdns_code, detected_at DESC);

-- Current per-document inventory; binaries live in content-addressed storage.
CREATE TABLE IF NOT EXISTS bdns_documents (
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code) ON DELETE CASCADE,
    bdns_document_id BIGINT NOT NULL,
    source_metadata JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('downloaded', 'rejected', 'failed', 'removed')),
    content_type TEXT,
    content_sha256 TEXT,
    stored_object_uri TEXT,
    downloaded_size_bytes BIGINT,
    last_error TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (bdns_code, bdns_document_id)
);
ALTER TABLE bdns_documents DROP CONSTRAINT IF EXISTS bdns_documents_status_check;
ALTER TABLE bdns_documents ADD CONSTRAINT bdns_documents_status_check
    CHECK (status IN ('downloaded', 'rejected', 'failed', 'removed'));

-- Keep references to prior content when the same source document changes.
CREATE TABLE IF NOT EXISTS bdns_document_versions (
    bdns_code TEXT NOT NULL,
    bdns_document_id BIGINT NOT NULL,
    content_sha256 TEXT NOT NULL,
    content_type TEXT NOT NULL,
    stored_object_uri TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    downloaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (bdns_code, bdns_document_id, content_sha256),
    FOREIGN KEY (bdns_code, bdns_document_id)
        REFERENCES bdns_documents (bdns_code, bdns_document_id) ON DELETE CASCADE
);

-- Machine-extracted candidates remain separate from approved/user-facing aid rules.
-- A new source fingerprint creates a new row instead of overwriting prior output.
CREATE TABLE IF NOT EXISTS bdns_extractions (
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code),
    source_fingerprint TEXT NOT NULL,
    reliability TEXT NOT NULL DEFAULT 'extracted' CHECK (reliability = 'extracted'),
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (bdns_code, source_fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_bdns_extractions_latest
    ON bdns_extractions (bdns_code, created_at DESC);
CREATE OR REPLACE FUNCTION prevent_bdns_extraction_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'BDNS extraction history is append-only';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS bdns_extractions_append_only ON bdns_extractions;
CREATE TRIGGER bdns_extractions_append_only
    BEFORE UPDATE OR DELETE ON bdns_extractions
    FOR EACH ROW EXECUTE FUNCTION prevent_bdns_extraction_mutation();

-- Current actionable extraction review tasks; reviewed facts remain at reliability=extracted.
CREATE TABLE IF NOT EXISTS bdns_extraction_review_tasks (
    task_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code),
    payload_sha256 TEXT NOT NULL,
    extraction_fingerprint TEXT NOT NULL DEFAULT '',
    issue_key TEXT NOT NULL,
    issue_type TEXT NOT NULL CHECK (issue_type IN (
        'missing_data', 'ambiguous_data', 'conflicting_data', 'quality_finding', 'source_changed'
    )),
    field TEXT,
    summary TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
        'open', 'needs_correction', 'reviewed_candidate', 'stale'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (bdns_code, payload_sha256, extraction_fingerprint, issue_key)
);
CREATE INDEX IF NOT EXISTS idx_bdns_extraction_review_queue
    ON bdns_extraction_review_tasks (status, updated_at DESC, task_id);
CREATE INDEX IF NOT EXISTS idx_bdns_extraction_review_code
    ON bdns_extraction_review_tasks (bdns_code, created_at DESC);

-- Reviewer actions and automatic task lifecycle changes are retained append-only.
CREATE TABLE IF NOT EXISTS bdns_extraction_review_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES bdns_extraction_review_tasks (task_id),
    reviewer TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN (
        'reviewed_candidate', 'needs_correction', 'superseded', 'source_changed',
        'quality_issue_cleared', 'extraction_completed'
    )),
    notes TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bdns_extraction_review_events_task
    ON bdns_extraction_review_events (task_id, created_at DESC, event_id DESC);
CREATE OR REPLACE FUNCTION prevent_bdns_extraction_review_event_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'BDNS extraction review history is append-only';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS bdns_extraction_review_events_append_only ON bdns_extraction_review_events;
CREATE TRIGGER bdns_extraction_review_events_append_only
    BEFORE UPDATE OR DELETE ON bdns_extraction_review_events
    FOR EACH ROW EXECUTE FUNCTION prevent_bdns_extraction_review_event_mutation();

-- Append-only results from repeatable source and extraction quality checks.
CREATE TABLE IF NOT EXISTS bdns_quality_checks (
    check_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code),
    payload_sha256 TEXT,
    report JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bdns_quality_checks_latest
    ON bdns_quality_checks (bdns_code, created_at DESC, check_id DESC);
CREATE OR REPLACE FUNCTION prevent_bdns_quality_check_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'BDNS quality-check history is append-only';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS bdns_quality_checks_append_only ON bdns_quality_checks;
CREATE TRIGGER bdns_quality_checks_append_only
    BEFORE UPDATE OR DELETE ON bdns_quality_checks
    FOR EACH ROW EXECUTE FUNCTION prevent_bdns_quality_check_mutation();

-- Current and historical official links. A removed URL remains in history.
CREATE TABLE IF NOT EXISTS bdns_links (
    bdns_code TEXT NOT NULL REFERENCES bdns_calls (bdns_code) ON DELETE CASCADE,
    resource_type TEXT NOT NULL,
    resource_key TEXT NOT NULL,
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unknown'
          CHECK (status IN ('unknown', 'reachable', 'broken', 'removed')),
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    status_code INTEGER,
    last_error TEXT,
    checked_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (bdns_code, resource_type, resource_key, url)
);
CREATE INDEX IF NOT EXISTS idx_bdns_links_current ON bdns_links (bdns_code, is_current);

CREATE TABLE IF NOT EXISTS blocks (
    name          TEXT PRIMARY KEY,
    requirements  JSONB NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
