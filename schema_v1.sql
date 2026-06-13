-- ============================================================
-- THE VOW LEDGER v1.0 - COMPLETE DATABASE SCHEMA (CORRECTED FOR POSTGRESQL)
-- ============================================================

-- Connect to the new database
-- \c vow

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- CORE TABLES (WITHOUT INDEXES INSIDE)
-- ============================================================

-- Submissions table
CREATE TABLE submissions (
    submission_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_hash VARCHAR(64) UNIQUE NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    entity_name VARCHAR(200) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    incident_country VARCHAR(100) NOT NULL,
    incident_state VARCHAR(100),
    incident_city VARCHAR(100),
    incident_year INTEGER NOT NULL CHECK (incident_year >= 1900 AND incident_year <= EXTRACT(YEAR FROM NOW())),
    
    life_loss_submitted INTEGER DEFAULT 0 CHECK (life_loss_submitted >= 0),
    financial_loss_submitted DECIMAL(20,2) DEFAULT 0.0 CHECK (financial_loss_submitted >= 0),
    ecosystem_loss_submitted TEXT,
    num_victims_submitted INTEGER DEFAULT 0 CHECK (num_victims_submitted >= 0),
    
    submitter_pubkey_hash VARCHAR(64) NOT NULL,
    client_ip_hash VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING_JURY',
    assigned_jury_session_id UUID,
    jury_complete_at TIMESTAMP,
    resulting_entry_id UUID,
    consensus_data JSONB,
    
    received_at TIMESTAMP DEFAULT NOW(),
    jury_assigned_at TIMESTAMP
);

-- Entries table
CREATE TABLE entries (
    entry_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id VARCHAR(100) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'APPROVED',
    depth_level INTEGER DEFAULT 0 CHECK (depth_level >= 0),
    parent_entry_id UUID REFERENCES entries(entry_id),
    dispute_winner VARCHAR(64),
    systemic_key VARCHAR(64),
    
    submitter_pubkey_hash VARCHAR(64) NOT NULL,
    
    life_loss INTEGER DEFAULT 0,
    financial_loss DECIMAL(20,2) DEFAULT 0.0,
    ecosystem_loss DECIMAL(20,2) DEFAULT 0.0,
    intent_type VARCHAR(20) NOT NULL,
    intent_multiplier DECIMAL(5,2) DEFAULT 1.0,
    num_affected INTEGER DEFAULT 0,
    
    harm_ly DECIMAL(20,2) NOT NULL,
    financial_usd DECIMAL(20,2) NOT NULL,
    harm_ecy DECIMAL(20,2) NOT NULL,
    
    jury_consensus_votes INTEGER DEFAULT 0,
    jury_total_votes INTEGER DEFAULT 0,
    confidence VARCHAR(20) NOT NULL,
    consensus_data JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    locked_at TIMESTAMP
);

-- Systemic patterns table
CREATE TABLE systemic_patterns (
    systemic_pattern_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id VARCHAR(100) NOT NULL,
    pattern_hash VARCHAR(64) UNIQUE NOT NULL,
    description TEXT NOT NULL,
    description_summary TEXT,
    similarity_threshold DECIMAL(3,2) NOT NULL CHECK (similarity_threshold >= 0.5 AND similarity_threshold <= 1.0),
    entry_ids UUID[] NOT NULL CHECK (array_length(entry_ids, 1) >= 2),
    
    total_harm_ly DECIMAL(20,2) NOT NULL DEFAULT 0.0,
    total_financial_usd DECIMAL(20,2) NOT NULL DEFAULT 0.0,
    total_harm_ecy DECIMAL(20,2) NOT NULL DEFAULT 0.0,
    total_affected INTEGER NOT NULL DEFAULT 0,
    pattern_confidence VARCHAR(20) NOT NULL,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    auto_detected BOOLEAN DEFAULT TRUE
);

-- Evidence tables
CREATE TABLE evidence_daily_index (
    date DATE PRIMARY KEY,
    total_files INTEGER DEFAULT 0 CHECK (total_files >= 0),
    total_size_bytes BIGINT DEFAULT 0 CHECK (total_size_bytes >= 0),
    unique_submissions INTEGER DEFAULT 0 CHECK (unique_submissions >= 0),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE evidence_files (
    file_hash VARCHAR(64) PRIMARY KEY,
    submission_id UUID NOT NULL REFERENCES submissions(submission_id) ON DELETE CASCADE,
    original_filename VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL CHECK (file_size > 0),
    mime_type VARCHAR(100),
    storage_location TEXT NOT NULL,
    indexed_at TIMESTAMP DEFAULT NOW(),
    pending BOOLEAN DEFAULT TRUE
);

-- Audit log table
CREATE TABLE audit_log (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action VARCHAR(100) NOT NULL,
    actor_hash VARCHAR(64) NOT NULL,
    actor_type VARCHAR(20) NOT NULL,
    submission_id UUID REFERENCES submissions(submission_id) ON DELETE SET NULL,
    entry_id UUID REFERENCES entries(entry_id) ON DELETE SET NULL,
    new_value JSONB,
    change_description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- CREATE INDEXES SEPARATELY (FIXED SYNTAX)
-- ============================================================

-- Indexes for submissions
CREATE INDEX idx_submissions_status ON submissions (status);
CREATE INDEX idx_submissions_entity ON submissions (entity_id);
CREATE INDEX idx_submissions_hash ON submissions (submission_hash);
CREATE INDEX idx_submissions_submitter ON submissions (submitter_pubkey_hash);
CREATE INDEX idx_submissions_created ON submissions (received_at);

-- Indexes for entries
CREATE INDEX idx_entries_entity ON entries (entity_id);
CREATE INDEX idx_entries_status ON entries (status);
CREATE INDEX idx_entries_created ON entries (created_at);
CREATE INDEX idx_entries_parent ON entries (parent_entry_id);
CREATE INDEX idx_entries_submitter ON entries (submitter_pubkey_hash);
CREATE INDEX idx_entries_systemic ON entries (systemic_key);

-- Indexes for systemic_patterns
CREATE INDEX idx_systemic_entity ON systemic_patterns (entity_id);
CREATE INDEX idx_systemic_hash ON systemic_patterns (pattern_hash);
CREATE INDEX idx_systemic_created ON systemic_patterns (created_at);

-- Indexes for evidence_files
CREATE INDEX idx_evidence_submission ON evidence_files (submission_id);
CREATE INDEX idx_evidence_date ON evidence_files (indexed_at);
CREATE INDEX idx_evidence_pending ON evidence_files (pending);

-- Indexes for audit_log
CREATE INDEX idx_audit_action ON audit_log (action);
CREATE INDEX idx_audit_created ON audit_log (created_at);