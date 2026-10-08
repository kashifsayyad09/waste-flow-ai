-- ============================================================================
-- WasteFlow AI — database schema + demo data (MySQL 8.0+, InnoDB, utf8mb4)
--
-- Import into an EXISTING database named `wasteflow`:
--   mysql -h <RDS_ENDPOINT> -P 3306 -u <USERNAME> -p wasteflow < schema.sql
--
-- This file is the single source of truth for the database structure.
-- The application never creates or alters tables. There are no migrations.
--
-- Safe to re-import: tables use IF NOT EXISTS and seed rows use INSERT IGNORE,
-- so existing tables and data are left untouched (nothing is dropped).
-- All timestamps are stored in UTC.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- bins: one row per physical waste bin
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bins (
    id                       VARCHAR(20)   NOT NULL,
    name                     VARCHAR(120)  NOT NULL,
    location                 VARCHAR(160)  NOT NULL,
    latitude                 DECIMAL(9,6)  NOT NULL,
    longitude                DECIMAL(9,6)  NOT NULL,
    fill_level               TINYINT UNSIGNED NOT NULL COMMENT 'Percent full, 0-100',
    waste_type               ENUM('organic','plastic','paper','glass','mixed') NOT NULL,
    last_collected           DATETIME      NOT NULL COMMENT 'UTC',
    days_since_collection    SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    temperature              DECIMAL(4,1)  NOT NULL COMMENT 'Degrees Celsius',
    estimated_overflow_time  SMALLINT UNSIGNED NOT NULL COMMENT 'Hours until overflow',
    status                   ENUM('normal','warning','critical') NOT NULL DEFAULT 'normal',
    created_at               DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_bins_status (status),
    KEY idx_bins_fill_level (fill_level),
    KEY idx_bins_last_collected (last_collected),
    CONSTRAINT chk_bins_fill_level CHECK (fill_level BETWEEN 0 AND 100),
    CONSTRAINT chk_bins_latitude   CHECK (latitude  BETWEEN -90  AND 90),
    CONSTRAINT chk_bins_longitude  CHECK (longitude BETWEEN -180 AND 180)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- collection_records: history of collection visits (many per bin)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS collection_records (
    id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    bin_id             VARCHAR(20)     NOT NULL,
    collected_at       DATETIME        NOT NULL COMMENT 'UTC',
    collection_status  ENUM('completed','skipped','failed') NOT NULL DEFAULT 'completed',
    notes              VARCHAR(500)    NULL,
    created_at         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_collection_records_bin_time (bin_id, collected_at),
    KEY idx_collection_records_collected_at (collected_at),
    CONSTRAINT fk_collection_records_bin
        FOREIGN KEY (bin_id) REFERENCES bins (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Demo data: 10 Hyderabad bins spanning CRITICAL / HIGH / MEDIUM / LOW.
-- last_collected is relative to the import time so the demo always looks live.
-- Expected priorities with the Phase 1 engine:
--   BIN-004 CRITICAL 97, BIN-001 CRITICAL 86, BIN-007 HIGH 76,
--   BIN-005 MEDIUM 53, BIN-009 MEDIUM 47, BIN-002 LOW 32, BIN-010 LOW 27,
--   BIN-006 LOW 19, BIN-003 LOW 12, BIN-008 LOW 6
-- ----------------------------------------------------------------------------
INSERT IGNORE INTO bins
    (id, name, location, latitude, longitude, fill_level, waste_type,
     last_collected, days_since_collection, temperature, estimated_overflow_time, status)
VALUES
    ('BIN-001', 'Charminar Market Bin',          'Charminar Market',             17.361600, 78.474700, 92, 'organic', UTC_TIMESTAMP() - INTERVAL 2 DAY, 2, 36.0,  4, 'critical'),
    ('BIN-002', 'Hitec City Metro Bin',          'Hitec City Metro Station',     17.443500, 78.377200, 61, 'mixed',   UTC_TIMESTAMP() - INTERVAL 1 DAY, 1, 33.0, 14, 'normal'),
    ('BIN-003', 'Banjara Hills Bin',             'Road No. 12, Banjara Hills',   17.412600, 78.448200, 38, 'plastic', UTC_TIMESTAMP(),                  0, 31.0, 40, 'normal'),
    ('BIN-004', 'Begum Bazaar Fish Market Bin',  'Begum Bazaar',                 17.370000, 78.473000, 97, 'organic', UTC_TIMESTAMP() - INTERVAL 3 DAY, 3, 37.0,  2, 'critical'),
    ('BIN-005', 'Secunderabad Station Bin',      'Secunderabad Railway Station', 17.434400, 78.501300, 78, 'mixed',   UTC_TIMESTAMP() - INTERVAL 2 DAY, 2, 34.0,  8, 'warning'),
    ('BIN-006', 'Financial District Bin',        'Gachibowli Financial District',17.418000, 78.342000, 45, 'paper',   UTC_TIMESTAMP() - INTERVAL 1 DAY, 1, 30.0, 30, 'normal'),
    ('BIN-007', 'Madhapur Food Court Bin',       'Madhapur Food Court',          17.448600, 78.390800, 88, 'organic', UTC_TIMESTAMP() - INTERVAL 1 DAY, 1, 35.0,  6, 'warning'),
    ('BIN-008', 'Jubilee Hills Check Post Bin',  'Jubilee Hills Check Post',     17.432600, 78.407100, 22, 'glass',   UTC_TIMESTAMP(),                  0, 29.0, 60, 'normal'),
    ('BIN-009', 'Kukatpally Housing Board Bin',  'KPHB Colony',                  17.494800, 78.399600, 69, 'mixed',   UTC_TIMESTAMP() - INTERVAL 2 DAY, 2, 32.0, 11, 'normal'),
    ('BIN-010', 'Necklace Road Bin',             'Necklace Road',                17.415600, 78.461900, 55, 'plastic', UTC_TIMESTAMP() - INTERVAL 1 DAY, 1, 31.0, 22, 'normal');

-- One historical collection per bin, matching each bin's last_collected.
INSERT IGNORE INTO collection_records (id, bin_id, collected_at, collection_status, notes)
SELECT n.id, b.id, b.last_collected, 'completed', 'Seed data'
FROM bins b
JOIN (
    SELECT 1 AS id, 'BIN-001' AS bin_id UNION ALL SELECT 2, 'BIN-002' UNION ALL SELECT 3, 'BIN-003'
    UNION ALL SELECT 4, 'BIN-004' UNION ALL SELECT 5, 'BIN-005' UNION ALL SELECT 6, 'BIN-006'
    UNION ALL SELECT 7, 'BIN-007' UNION ALL SELECT 8, 'BIN-008' UNION ALL SELECT 9, 'BIN-009'
    UNION ALL SELECT 10, 'BIN-010'
) n ON n.bin_id = b.id;
