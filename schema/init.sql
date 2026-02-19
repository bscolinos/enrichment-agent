CREATE DATABASE IF NOT EXISTS leads_demo;
USE leads_demo;

CREATE TABLE IF NOT EXISTS raw_leads (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  lead_id VARCHAR(64) NOT NULL,
  email VARCHAR(255),
  name VARCHAR(255),
  company VARCHAR(255),
  title VARCHAR(255),
  source VARCHAR(64),
  form_data JSON,
  raw_payload JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  SHARD KEY (lead_id)
);

CREATE TABLE IF NOT EXISTS lead_current (
  lead_id VARCHAR(64) PRIMARY KEY,
  email VARCHAR(255),
  name VARCHAR(255),
  company VARCHAR(255),
  title VARCHAR(255),
  normalized_company VARCHAR(255),
  industry VARCHAR(128),
  company_size VARCHAR(64),
  region VARCHAR(64),
  fit_score FLOAT,
  intent_score FLOAT,
  status VARCHAR(32) DEFAULT 'new',
  enriched_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS intent_signals (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  lead_id VARCHAR(64),
  signal_type VARCHAR(64),
  signal_data JSON,
  score_weight FLOAT DEFAULT 1.0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  SHARD KEY (lead_id),
  KEY (lead_id, created_at)
);

CREATE TABLE IF NOT EXISTS account_memory (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  entity_type VARCHAR(32),
  entity_id VARCHAR(64),
  content_type VARCHAR(64),
  content_text TEXT,
  embedding VECTOR(1536),
  metadata JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  SHARD KEY (entity_id),
  VECTOR INDEX (embedding) INDEX_OPTIONS '{"metric_type": "DOT_PRODUCT"}'
);

CREATE TABLE IF NOT EXISTS recommendations (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  lead_id VARCHAR(64),
  action_type VARCHAR(64),
  action_detail JSON,
  confidence FLOAT,
  rationale TEXT,
  data_sources JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  SHARD KEY (lead_id),
  KEY (lead_id, created_at DESC)
);

DELIMITER //
CREATE OR REPLACE PROCEDURE upsert_lead_current(
  p_lead_id VARCHAR(64),
  p_email VARCHAR(255),
  p_name VARCHAR(255),
  p_company VARCHAR(255),
  p_title VARCHAR(255),
  p_source VARCHAR(64),
  p_form_data JSON
)
AS
BEGIN
  INSERT INTO lead_current (
    lead_id,
    email,
    name,
    company,
    title,
    status
  )
  VALUES (
    p_lead_id,
    p_email,
    p_name,
    p_company,
    p_title,
    'new'
  )
  ON DUPLICATE KEY UPDATE
    email = VALUES(email),
    name = VALUES(name),
    company = VALUES(company),
    title = VALUES(title),
    status = IFNULL(lead_current.status, 'new');
END //
DELIMITER ;

DELIMITER //
CREATE OR REPLACE TRIGGER raw_leads_to_current
AFTER INSERT ON raw_leads
AS
BEGIN
  CALL upsert_lead_current(
    NEW.lead_id,
    NEW.email,
    NEW.name,
    NEW.company,
    NEW.title,
    NEW.source,
    NEW.form_data
  );
END //
DELIMITER ;

-- Optional: Kafka pipeline for redpanda broker
-- CREATE OR REPLACE PIPELINE leads_pipeline
-- AS LOAD DATA KAFKA 'redpanda:9092/inbound-leads'
-- INTO TABLE raw_leads
-- FORMAT JSON
-- (
--   lead_id <- lead_id,
--   email <- email,
--   name <- name,
--   company <- company,
--   title <- title,
--   source <- source,
--   form_data <- form_data,
--   raw_payload <- @raw
-- );
-- START PIPELINE leads_pipeline;
