/*
 * PostgreSQL Fundamentals
 * Installation verification, server architecture, databases, schemas,
 * roles, catalog inspection, transaction behavior, and practical operations.
 *
 * Execute against a PostgreSQL database using:
 *   psql -X -v ON_ERROR_STOP=1 -d postgres -f postgres_fundamentals.sql
 *
 * This script creates a dedicated schema inside the database to which it
 * connects. Database creation is intentionally not automated because CREATE
 * DATABASE cannot run inside a transaction block and requires elevated rights.
 *
 * The script targets PostgreSQL 15 or later.
 */

\set ON_ERROR_STOP on
\pset pager off
\timing on

\echo '=== Client and connection diagnostics ==='

SELECT version() AS server_version,
       current_database() AS connected_database,
       current_user AS current_role,
       session_user AS authenticated_role,
       inet_server_addr() AS server_address,
       inet_server_port() AS server_port;

SHOW server_version;
SHOW server_encoding;
SHOW port;
SHOW listen_addresses;
SHOW search_path;
SHOW transaction_isolation;

\echo '=== Cluster-wide database inventory ==='

SELECT d.datname AS database_name,
       pg_get_userbyid(d.datdba) AS database_owner,
       pg_encoding_to_char(d.encoding) AS encoding,
       d.datallowconn AS allows_connections,
       d.datconnlimit AS connection_limit,
       pg_size_pretty(pg_database_size(d.datname)) AS database_size
FROM pg_database AS d
ORDER BY d.datname;

\echo '=== Cluster-wide roles ==='

SELECT rolname,
       rolsuper,
       rolinherit,
       rolcreaterole,
       rolcreatedb,
       rolcanlogin,
       rolconnlimit
FROM pg_roles
WHERE rolname !~ '^pg_'
ORDER BY rolname;

BEGIN;

CREATE SCHEMA IF NOT EXISTS pg_fundamentals_lab;

CREATE TABLE IF NOT EXISTS pg_fundamentals_lab.sites (
    site_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_code TEXT NOT NULL UNIQUE,
    site_name TEXT NOT NULL,
    region TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT sites_code_nonempty CHECK (length(trim(site_code)) > 0),
    CONSTRAINT sites_name_nonempty CHECK (length(trim(site_name)) > 0)
);

CREATE TABLE IF NOT EXISTS pg_fundamentals_lab.assets (
    asset_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_code TEXT NOT NULL UNIQUE,
    asset_name TEXT NOT NULL,
    site_id BIGINT NOT NULL
        REFERENCES pg_fundamentals_lab.sites(site_id)
        ON DELETE RESTRICT,
    asset_status TEXT NOT NULL DEFAULT 'active',
    commissioned_on DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT assets_code_nonempty CHECK (length(trim(asset_code)) > 0),
    CONSTRAINT assets_name_nonempty CHECK (length(trim(asset_name)) > 0),
    CONSTRAINT assets_status_valid
        CHECK (asset_status IN ('active', 'maintenance', 'retired'))
);

CREATE TABLE IF NOT EXISTS pg_fundamentals_lab.inspection_results (
    inspection_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id BIGINT NOT NULL
        REFERENCES pg_fundamentals_lab.assets(asset_id)
        ON DELETE RESTRICT,
    inspected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    inspector_name TEXT NOT NULL,
    result TEXT NOT NULL,
    observations TEXT,
    CONSTRAINT inspection_result_valid
        CHECK (result IN ('pass', 'fail', 'follow_up')),
    CONSTRAINT inspection_name_nonempty
        CHECK (length(trim(inspector_name)) > 0)
);

CREATE INDEX IF NOT EXISTS assets_site_status_idx
    ON pg_fundamentals_lab.assets (site_id, asset_status);

CREATE INDEX IF NOT EXISTS inspection_asset_date_idx
    ON pg_fundamentals_lab.inspection_results (asset_id, inspected_at DESC);

CREATE INDEX IF NOT EXISTS inspection_failures_idx
    ON pg_fundamentals_lab.inspection_results (inspected_at DESC)
    WHERE result = 'fail';

COMMENT ON SCHEMA pg_fundamentals_lab IS
    'Demonstration objects for PostgreSQL database and schema fundamentals';

COMMENT ON TABLE pg_fundamentals_lab.assets IS
    'Assets belong to sites within the current database and schema';

INSERT INTO pg_fundamentals_lab.sites (site_code, site_name, region)
VALUES
    ('PLANT-N', 'Northern Manufacturing Plant', 'North'),
    ('PLANT-S', 'Southern Manufacturing Plant', 'South')
ON CONFLICT (site_code) DO UPDATE
SET site_name = EXCLUDED.site_name,
    region = EXCLUDED.region;

INSERT INTO pg_fundamentals_lab.assets
    (asset_code, asset_name, site_id, asset_status, commissioned_on)
SELECT input.asset_code,
       input.asset_name,
       sites.site_id,
       input.asset_status,
       input.commissioned_on
FROM (
    VALUES
        ('P-104', 'Cooling Water Pump', 'PLANT-N', 'active',
         DATE '2022-04-12'),
        ('T-208', 'Power Transformer', 'PLANT-S', 'maintenance',
         DATE '2020-09-01'),
        ('C-310', 'Air Compressor', 'PLANT-N', 'active',
         DATE '2023-02-18')
) AS input(asset_code, asset_name, site_code, asset_status, commissioned_on)
JOIN pg_fundamentals_lab.sites AS sites
  ON sites.site_code = input.site_code
ON CONFLICT (asset_code) DO UPDATE
SET asset_name = EXCLUDED.asset_name,
    site_id = EXCLUDED.site_id,
    asset_status = EXCLUDED.asset_status,
    commissioned_on = EXCLUDED.commissioned_on;

INSERT INTO pg_fundamentals_lab.inspection_results
    (asset_id, inspected_at, inspector_name, result, observations)
SELECT assets.asset_id,
       input.inspected_at,
       input.inspector_name,
       input.result,
       input.observations
FROM (
    VALUES
        ('P-104', TIMESTAMPTZ '2026-10-10 09:00:00+05:30',
         'R. Sharma', 'pass', 'Vibration within operating limits'),
        ('P-104', TIMESTAMPTZ '2026-10-15 10:30:00+05:30',
         'A. Singh', 'follow_up', 'Seal temperature requires rechecking'),
        ('T-208', TIMESTAMPTZ '2026-10-14 14:15:00+05:30',
         'R. Sharma', 'fail', 'Insulation inspection identified a defect'),
        ('C-310', TIMESTAMPTZ '2026-10-12 11:45:00+05:30',
         'M. Das', 'pass', 'Pressure readings are acceptable')
) AS input(asset_code, inspected_at, inspector_name, result, observations)
JOIN pg_fundamentals_lab.assets AS assets
  ON assets.asset_code = input.asset_code
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_fundamentals_lab.inspection_results AS existing
    WHERE existing.asset_id = assets.asset_id
      AND existing.inspected_at = input.inspected_at
      AND existing.inspector_name = input.inspector_name
);

COMMIT;

\echo '=== Schema inventory ==='

SELECT n.nspname AS schema_name,
       pg_get_userbyid(n.nspowner) AS schema_owner
FROM pg_namespace AS n
WHERE n.nspname NOT LIKE 'pg_temp_%'
  AND n.nspname NOT LIKE 'pg_toast%'
ORDER BY n.nspname;

\echo '=== User relations and estimated sizes ==='

SELECT schemaname,
       tablename,
       tableowner,
       n_live_tup AS estimated_live_rows
FROM pg_stat_user_tables
WHERE schemaname = 'pg_fundamentals_lab'
ORDER BY tablename;

\echo '=== information_schema inspection ==='

SELECT table_schema,
       table_name,
       table_type
FROM information_schema.tables
WHERE table_schema = 'pg_fundamentals_lab'
ORDER BY table_name;

SELECT table_schema,
       table_name,
       ordinal_position,
       column_name,
       data_type,
       is_nullable
FROM information_schema.columns
WHERE table_schema = 'pg_fundamentals_lab'
ORDER BY table_name, ordinal_position;

\echo '=== Join across related tables ==='

SELECT sites.site_code,
       sites.site_name,
       assets.asset_code,
       assets.asset_name,
       assets.asset_status
FROM pg_fundamentals_lab.sites AS sites
JOIN pg_fundamentals_lab.assets AS assets
  ON assets.site_id = sites.site_id
ORDER BY sites.site_code, assets.asset_code;

\echo '=== Latest inspection per asset ==='

SELECT DISTINCT ON (assets.asset_id)
       assets.asset_code,
       assets.asset_name,
       inspections.inspected_at,
       inspections.result,
       inspections.observations
FROM pg_fundamentals_lab.assets AS assets
JOIN pg_fundamentals_lab.inspection_results AS inspections
  ON inspections.asset_id = assets.asset_id
ORDER BY assets.asset_id, inspections.inspected_at DESC;

\echo '=== Common table expression and aggregate reporting ==='

WITH inspection_summary AS (
    SELECT asset_id,
           COUNT(*) AS total_inspections,
           COUNT(*) FILTER (WHERE result = 'fail') AS failed_inspections,
           COUNT(*) FILTER (WHERE result = 'follow_up') AS follow_up_inspections,
           MAX(inspected_at) AS latest_inspection
    FROM pg_fundamentals_lab.inspection_results
    GROUP BY asset_id
)
SELECT assets.asset_code,
       assets.asset_name,
       COALESCE(summary.total_inspections, 0) AS total_inspections,
       COALESCE(summary.failed_inspections, 0) AS failed_inspections,
       COALESCE(summary.follow_up_inspections, 0) AS follow_up_inspections,
       summary.latest_inspection
FROM pg_fundamentals_lab.assets AS assets
LEFT JOIN inspection_summary AS summary
  ON summary.asset_id = assets.asset_id
ORDER BY failed_inspections DESC, assets.asset_code;

\echo '=== Query plan inspection ==='

EXPLAIN
SELECT inspection_id, inspected_at, result
FROM pg_fundamentals_lab.inspection_results
WHERE asset_id = (
    SELECT asset_id
    FROM pg_fundamentals_lab.assets
    WHERE asset_code = 'P-104'
)
ORDER BY inspected_at DESC;

\echo '=== Transaction rollback demonstration ==='

BEGIN;

UPDATE pg_fundamentals_lab.assets
SET asset_status = 'maintenance'
WHERE asset_code = 'P-104';

SELECT asset_code, asset_status
FROM pg_fundamentals_lab.assets
WHERE asset_code = 'P-104';

ROLLBACK;

SELECT asset_code, asset_status
FROM pg_fundamentals_lab.assets
WHERE asset_code = 'P-104';

\echo '=== Database and schema boundary examples ==='

-- This qualified name refers to the schema inside the current database.
SELECT COUNT(*) AS asset_count
FROM pg_fundamentals_lab.assets;

-- PostgreSQL does not support ordinary cross-database references using
-- database.schema.table syntax. Connect to another database with \c instead.
-- Example psql command: \c postgres

\echo '=== Search path demonstration ==='

SHOW search_path;

SET search_path TO pg_fundamentals_lab, public;

SELECT current_database() AS database_name,
       current_schema() AS current_schema,
       current_schemas(true) AS effective_schemas;

-- Explicit qualification is preferable for important application queries.
SELECT asset_code, asset_name
FROM pg_fundamentals_lab.assets
ORDER BY asset_code;

RESET search_path;

\echo '=== Installation and connection commands ==='

\echo 'Client version: run psql --version in the operating system shell.'
\echo 'Readiness: pg_isready -h localhost -p 5432'
\echo 'Connect: psql -X -h localhost -p 5432 -U postgres -d postgres'
\echo 'List databases: \l'
\echo 'Connect to database: \c plant_operations'
\echo 'List schemas: \dn'
\echo 'List tables: \dt pg_fundamentals_lab.*'
\echo 'Describe a relation: \d pg_fundamentals_lab.assets'
\echo 'Quit psql: \q'

\echo '=== Operational notes ==='

SELECT current_database() AS current_database,
       current_user AS current_role,
       pg_postmaster_start_time() AS server_started_at,
       pg_is_in_recovery() AS is_standby;

\echo 'The lab schema remains in the current database for inspection.'
\echo 'Remove it only when its demonstration data is no longer needed.'
