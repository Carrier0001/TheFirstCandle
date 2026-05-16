
-- scripts/init-db.sql
-- scripts/init-db.sql
-- PostgreSQL initialization script for Vow Ledger

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==================== CORE TABLES ====================

-- Submissions table (cache only - JSON files are source of truth)
CREATE TABLE IF NOT EXISTS submissions (
    submission_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_hash TEXT UNIQUE NOT NULL,
    entity_id TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    incident_country TEXT NOT NULL,
    incident_state TEXT,
    incident_city TEXT,
    incident_year INTEGER NOT NULL,
    life_loss_submitted INTEGER DEFAULT 0,
    financial_loss_submitted REAL DEFAULT 0,
    ecosystem_loss_submitted TEXT,
    num_victims_submitted INTEGER DEFAULT 0,
    submitter_pubkey_hash TEXT NOT NULL,
    -- NO IP address stored - removed for privacy/security
    status TEXT DEFAULT 'PENDING_JURY',
    ipfs_cid TEXT,
    git_commit_hash TEXT,
    jury_consensus BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Jury votes table
CREATE TABLE IF NOT EXISTS jury_votes (
    vote_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID REFERENCES submissions(submission_id) ON DELETE CASCADE,
    juror_pubkey_hash TEXT NOT NULL,
    vote BOOLEAN NOT NULL,
    justification_hash TEXT,
    weight INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(submission_id, juror_pubkey_hash)
);

-- Entity aggregation cache (for fast queries)
CREATE TABLE IF NOT EXISTS entity_aggregates (
    entity_id TEXT PRIMARY KEY,
    entity_name TEXT,
    total_harm_ly REAL DEFAULT 0,
    total_harm_ecy REAL DEFAULT 0,
    total_surplus_ly REAL DEFAULT 0,
    total_surplus_ecy REAL DEFAULT 0,
    outstanding_ly REAL DEFAULT 0,
    outstanding_ecy REAL DEFAULT 0,
    status TEXT DEFAULT 'ACCRUING',
    last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    calculation_version INTEGER DEFAULT 1
);

-- Evidence files reference
CREATE TABLE IF NOT EXISTS evidence_files (
    file_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID REFERENCES submissions(submission_id) ON DELETE CASCADE,
    file_hash TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type TEXT,
    ipfs_cid TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rate limiting table (in-memory only in production, but here for reference)
CREATE TABLE IF NOT EXISTS rate_limits (
    bucket_key TEXT PRIMARY KEY,
    tokens REAL DEFAULT 1.0,
    last_refill TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== INDEXES ====================

CREATE INDEX idx_submissions_entity ON submissions(entity_id, incident_year);
CREATE INDEX idx_submissions_status ON submissions(status);
CREATE INDEX idx_submissions_hash ON submissions(submission_hash);
CREATE INDEX idx_submissions_created ON submissions(created_at);
CREATE INDEX idx_jury_submission ON jury_votes(submission_id);
CREATE INDEX idx_jury_juror ON jury_votes(juror_pubkey_hash);
CREATE INDEX idx_aggregates_status ON entity_aggregates(status);
CREATE INDEX idx_evidence_submission ON evidence_files(submission_id);

-- ==================== FUNCTIONS & TRIGGERS ====================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_submissions_updated_at
    BEFORE UPDATE ON submissions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Auto-calculate entity aggregates on submission
CREATE OR REPLACE FUNCTION refresh_entity_aggregates()
RETURNS TRIGGER AS $$
BEGIN
    -- Mark entity aggregate as stale
    UPDATE entity_aggregates 
    SET last_calculated = '1970-01-01' 
    WHERE entity_id = NEW.entity_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER submission_updates_aggregates
    AFTER INSERT OR UPDATE ON submissions
    FOR EACH ROW
    EXECUTE FUNCTION refresh_entity_aggregates();

-- ==================== INITIAL DATA ====================

-- Insert some initial entities if needed (optional)
INSERT INTO entity_aggregates (entity_id, entity_name, status)
VALUES 
    ('system', 'Vow Ledger System', 'REPAIRED')
ON CONFLICT (entity_id) DO NOTHING;

-- ==================== CLEANUP FUNCTIONS ====================

-- Auto-clean old rate limit entries (run via cron)
CREATE OR REPLACE FUNCTION cleanup_rate_limits()
RETURNS void AS $$
BEGIN
    DELETE FROM rate_limits 
    WHERE last_refill < NOW() - INTERVAL '1 hour';
END;
$$ LANGUAGE plpgsql;

-- ==================== HELPER FUNCTIONS ====================

-- Get submission statistics for an entity
CREATE OR REPLACE FUNCTION get_entity_stats(p_entity_id TEXT)
RETURNS TABLE(
    total_submissions BIGINT,
    pending_jury BIGINT,
    approved BIGINT,
    rejected BIGINT,
    total_harm_ly REAL,
    total_surplus_ly REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT,
        COUNT(*) FILTER (WHERE status = 'PENDING_JURY')::BIGINT,
        COUNT(*) FILTER (WHERE status = 'APPROVED')::BIGINT,
        COUNT(*) FILTER (WHERE status = 'REJECTED')::BIGINT,
        COALESCE(SUM(life_loss_submitted), 0)::REAL,
        COALESCE(SUM(financial_loss_submitted), 0)::REAL
    FROM submissions
    WHERE entity_id = p_entity_id;
END;
$$ LANGUAGE plpgsql;

-- ==================== COMMENTS ====================

COMMENT ON TABLE submissions IS 'Cache of ledger submissions - JSON files are source of truth';
COMMENT ON TABLE jury_votes IS 'Jury consensus votes for submissions';
COMMENT ON TABLE entity_aggregates IS 'Pre-calculated entity aggregates for fast queries';
COMMENT ON COLUMN submissions.submitter_pubkey_hash IS 'SHA-256 hash of submitter public key - NOT the original key';
