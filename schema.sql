CREATE SEQUENCE IF NOT EXISTS seq_commit_id START 1;

CREATE TABLE IF NOT EXISTS verified_selectors (
    target_id VARCHAR,
    platform_name VARCHAR,
    element_intent VARCHAR,
    primary_selector VARCHAR,
    fallback_selector VARCHAR,
    resolved_tag VARCHAR,
    resolved_classes VARCHAR,
    verification_status VARCHAR,
    content_hash VARCHAR,
    last_verified_utc VARCHAR,
    PRIMARY KEY (target_id, element_intent)
);

CREATE TABLE IF NOT EXISTS ledger (
    commit_id BIGINT PRIMARY KEY,
    timestamp_utc VARCHAR,
    operation VARCHAR,
    target_id VARCHAR,
    element_intent VARCHAR,
    selector_state VARCHAR,
    detail VARCHAR
);
