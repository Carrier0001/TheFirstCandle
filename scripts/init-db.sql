
-- scripts/init-db.sql

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Submissions table (cache only - not source of truth)
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
    -- NO IP storage - removed for security
    status TEXT DEFAULT 'PENDING_JURY',
    ipfs_cid TEXT,
    git_commit_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Jury votes table
CREATE TABLE IF NOT EXISTS jury_votes (
    vote_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID REFERENCES submissions(submission_id),
    juror_pubkey_hash TEXT NOT NULL,
    vote BOOLEAN NOT NULL,
    justification_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(submission_id, juror_pubkey_hash)
);

-- Aggregation cache
CREATE TABLE IF NOT EXISTS entity_aggregates (
    entity_id TEXT PRIMARY KEY,
    total_harm_ly REAL DEFAULT 0,
    total_surplus_ly REAL DEFAULT 0,
    outstanding_ly REAL DEFAULT 0,
    status TEXT DEFAULT 'ACCRUING',
    last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_submissions_entity ON submissions(entity_id, incident_year);
CREATE INDEX idx_submissions_status ON submissions(status);
CREATE INDEX idx_submissions_hash ON submissions(submission_hash);
CREATE INDEX idx_jury_submission ON jury_votes(submission_id);

-- Update trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_submissions_updated_at
    BEFORE UPDATE ON submissions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
