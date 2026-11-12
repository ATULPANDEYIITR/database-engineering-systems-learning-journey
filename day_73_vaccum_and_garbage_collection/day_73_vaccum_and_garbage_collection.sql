-- ============================================================
-- VACUUM AND GARBAGE COLLECTION
-- PostgreSQL MVCC, dead tuples, vacuuming and reclamation
--
-- Requires PostgreSQL 15 or later.
--
-- Demonstrates:
--   1. Heap tuple version management
--   2. Dead tuple generation through UPDATE and DELETE
--   3. Transaction visibility
--   4. Standard VACUUM
--   5. VACUUM FULL
--   6. ANALYZE
--   7. Autovacuum configuration and thresholds
--   8. Transaction ID freezing
--   9. Storage monitoring
--  10. Maintenance reporting
--
-- Run this script using psql with permission to create
-- schemas, tables, functions and procedures.
--
-- VACUUM and VACUUM FULL must execute outside an explicit
-- transaction block.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS vacuum_lab;

SET search_path TO vacuum_lab, public;

-- ============================================================
-- 1. DOMAIN TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS vacuum_lab.app_users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vacuum_lab.orders (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    user_id BIGINT NOT NULL
        REFERENCES vacuum_lab.app_users(user_id),

    order_reference VARCHAR(100) NOT NULL UNIQUE,

    amount NUMERIC(14, 2) NOT NULL
        CHECK (amount >= 0),

    status VARCHAR(20) NOT NULL
        CHECK (
            status IN (
                'PENDING',
                'PROCESSING',
                'COMPLETED',
                'CANCELLED'
            )
        ),

    version_number INTEGER NOT NULL DEFAULT 1
        CHECK (version_number >= 1),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vacuum_lab.maintenance_log (
    log_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    relation_name TEXT NOT NULL,

    operation VARCHAR(30) NOT NULL
        CHECK (
            operation IN (
                'VACUUM',
                'ANALYZE',
                'VACUUM_FULL',
                'FREEZE',
                'AUTOVACUUM'
            )
        ),

    dead_before BIGINT NOT NULL DEFAULT 0,
    dead_after BIGINT NOT NULL DEFAULT 0,

    pages_before BIGINT NOT NULL DEFAULT 0,
    pages_after BIGINT NOT NULL DEFAULT 0,

    execution_status VARCHAR(20) NOT NULL
        CHECK (
            execution_status IN (
                'SUCCESS',
                'FAILED',
                'SKIPPED'
            )
        ),

    details TEXT,

    executed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vacuum_lab.autovacuum_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    relation_name TEXT NOT NULL UNIQUE,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    vacuum_threshold BIGINT NOT NULL DEFAULT 50
        CHECK (vacuum_threshold >= 0),

    vacuum_scale_factor NUMERIC(5, 4) NOT NULL DEFAULT 0.20
        CHECK (
            vacuum_scale_factor >= 0
            AND vacuum_scale_factor <= 1
        ),

    analyze_threshold BIGINT NOT NULL DEFAULT 50
        CHECK (analyze_threshold >= 0),

    analyze_scale_factor NUMERIC(5, 4) NOT NULL DEFAULT 0.10
        CHECK (
            analyze_scale_factor >= 0
            AND analyze_scale_factor <= 1
        ),

    max_dead_ratio NUMERIC(5, 4) NOT NULL DEFAULT 0.25
        CHECK (
            max_dead_ratio >= 0
            AND max_dead_ratio <= 1
        )
);

CREATE TABLE IF NOT EXISTS vacuum_lab.transaction_snapshots (
    snapshot_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_label TEXT NOT NULL,

    transaction_xid XID NOT NULL,

    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    completed_at TIMESTAMPTZ,

    CHECK (
        completed_at IS NULL
        OR completed_at >= started_at
    )
);

-- ============================================================
-- 2. PERFORMANCE INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_orders_user_id
    ON vacuum_lab.orders(user_id);

CREATE INDEX IF NOT EXISTS idx_orders_status
    ON vacuum_lab.orders(status);

CREATE INDEX IF NOT EXISTS idx_orders_updated_at
    ON vacuum_lab.orders(updated_at);

CREATE INDEX IF NOT EXISTS idx_maintenance_relation_time
    ON vacuum_lab.maintenance_log(
        relation_name,
        executed_at DESC
    );

CREATE INDEX IF NOT EXISTS idx_transaction_active
    ON vacuum_lab.transaction_snapshots(started_at)
    WHERE completed_at IS NULL;

-- ============================================================
-- 3. UPDATE TIMESTAMP TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION vacuum_lab.set_order_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := clock_timestamp();
    NEW.version_number := OLD.version_number + 1;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_order_updated_at
    ON vacuum_lab.orders;

CREATE TRIGGER trg_order_updated_at
BEFORE UPDATE ON vacuum_lab.orders
FOR EACH ROW
EXECUTE FUNCTION vacuum_lab.set_order_updated_at();

-- ============================================================
-- 4. SAMPLE DATA
-- ============================================================

INSERT INTO vacuum_lab.app_users(username)
VALUES
    ('customer_001'),
    ('customer_002'),
    ('customer_003'),
    ('customer_004'),
    ('customer_005')
ON CONFLICT (username) DO NOTHING;

INSERT INTO vacuum_lab.orders(
    user_id,
    order_reference,
    amount,
    status
)
SELECT
    u.user_id,
    'ORDER-' || u.user_id || '-' || n,
    (100 + n * 15)::NUMERIC(14, 2),
    CASE
        WHEN n % 4 = 0 THEN 'PENDING'
        WHEN n % 4 = 1 THEN 'PROCESSING'
        WHEN n % 4 = 2 THEN 'COMPLETED'
        ELSE 'CANCELLED'
    END
FROM vacuum_lab.app_users u
CROSS JOIN generate_series(1, 100) AS n
ON CONFLICT (order_reference) DO NOTHING;

INSERT INTO vacuum_lab.autovacuum_policies(
    relation_name,
    enabled,
    vacuum_threshold,
    vacuum_scale_factor,
    analyze_threshold,
    analyze_scale_factor,
    max_dead_ratio
)
VALUES (
    'vacuum_lab.orders',
    TRUE,
    20,
    0.10,
    10,
    0.05,
    0.20
)
ON CONFLICT (relation_name)
DO UPDATE SET
    enabled = EXCLUDED.enabled,
    vacuum_threshold = EXCLUDED.vacuum_threshold,
    vacuum_scale_factor = EXCLUDED.vacuum_scale_factor,
    analyze_threshold = EXCLUDED.analyze_threshold,
    analyze_scale_factor = EXCLUDED.analyze_scale_factor,
    max_dead_ratio = EXCLUDED.max_dead_ratio;

-- ============================================================
-- 5. GENERATE DEAD TUPLES
-- ============================================================

-- UPDATE creates new MVCC tuple versions.
-- Old versions become dead after no active snapshot requires them.

UPDATE vacuum_lab.orders
SET
    amount = amount + 25,
    status = 'PROCESSING'
WHERE order_id % 3 = 0;

-- DELETE creates dead tuple versions.

DELETE FROM vacuum_lab.orders
WHERE order_id % 7 = 0;

-- ============================================================
-- 6. STORAGE STATISTICS VIEW
-- ============================================================

CREATE OR REPLACE VIEW vacuum_lab.table_storage_statistics AS
SELECT
    schemaname,
    relname AS table_name,
    n_live_tup,
    n_dead_tup,
    n_tup_ins,
    n_tup_upd,
    n_tup_del,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze,
    vacuum_count,
    autovacuum_count,
    analyze_count,
    autoanalyze_count,

    CASE
        WHEN n_live_tup + n_dead_tup = 0 THEN 0
        ELSE ROUND(
            100.0 * n_dead_tup /
            (n_live_tup + n_dead_tup),
            2
        )
    END AS dead_tuple_percentage

FROM pg_stat_user_tables
WHERE schemaname = 'vacuum_lab';

-- ============================================================
-- 7. RELATION PHYSICAL STORAGE VIEW
-- ============================================================

CREATE OR REPLACE VIEW vacuum_lab.relation_storage AS
SELECT
    c.oid::REGCLASS AS relation_name,
    pg_relation_size(c.oid) AS heap_bytes,
    pg_indexes_size(c.oid) AS index_bytes,
    pg_total_relation_size(c.oid) AS total_bytes,
    pg_size_pretty(pg_relation_size(c.oid)) AS heap_size,
    pg_size_pretty(pg_indexes_size(c.oid)) AS index_size,
    pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_class c
JOIN pg_namespace n
    ON n.oid = c.relnamespace
WHERE n.nspname = 'vacuum_lab'
  AND c.relkind = 'r';

-- ============================================================
-- 8. VACUUM ELIGIBILITY FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION vacuum_lab.evaluate_vacuum(
    p_relation_name TEXT
)
RETURNS TABLE (
    relation_name TEXT,
    live_tuples BIGINT,
    dead_tuples BIGINT,
    vacuum_threshold NUMERIC,
    dead_ratio NUMERIC,
    vacuum_required BOOLEAN
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_policy vacuum_lab.autovacuum_policies%ROWTYPE;
    v_stats RECORD;
BEGIN
    SELECT *
    INTO v_policy
    FROM vacuum_lab.autovacuum_policies p
    WHERE p.relation_name = p_relation_name;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'No autovacuum policy found for %',
            p_relation_name;
    END IF;

    IF NOT v_policy.enabled THEN
        RETURN QUERY
        SELECT
            p_relation_name,
            0::BIGINT,
            0::BIGINT,
            0::NUMERIC,
            0::NUMERIC,
            FALSE;
        RETURN;
    END IF;

    SELECT
        s.n_live_tup,
        s.n_dead_tup
    INTO v_stats
    FROM pg_stat_user_tables s
    WHERE s.schemaname = split_part(p_relation_name, '.', 1)
      AND s.relname = split_part(p_relation_name, '.', 2);

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Statistics not found for %',
            p_relation_name;
    END IF;

    RETURN QUERY
    SELECT
        p_relation_name,
        v_stats.n_live_tup::BIGINT,
        v_stats.n_dead_tup::BIGINT,

        (
            v_policy.vacuum_threshold
            + v_policy.vacuum_scale_factor
              * v_stats.n_live_tup
        )::NUMERIC,

        CASE
            WHEN v_stats.n_live_tup + v_stats.n_dead_tup = 0
                THEN 0::NUMERIC
            ELSE ROUND(
                v_stats.n_dead_tup::NUMERIC /
                (v_stats.n_live_tup + v_stats.n_dead_tup),
                4
            )
        END,

        (
            v_stats.n_dead_tup >
            v_policy.vacuum_threshold
            + v_policy.vacuum_scale_factor
              * v_stats.n_live_tup
        )
        OR
        (
            v_stats.n_dead_tup::NUMERIC /
            GREATEST(
                v_stats.n_live_tup + v_stats.n_dead_tup,
                1
            ) > v_policy.max_dead_ratio
        );
END;
$$;

-- ============================================================
-- 9. ANALYZE ELIGIBILITY FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION vacuum_lab.evaluate_analyze(
    p_relation_name TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_policy vacuum_lab.autovacuum_policies%ROWTYPE;
    v_live BIGINT;
    v_dead BIGINT;
BEGIN
    SELECT *
    INTO v_policy
    FROM vacuum_lab.autovacuum_policies
    WHERE relation_name = p_relation_name;

    IF NOT FOUND OR NOT v_policy.enabled THEN
        RETURN FALSE;
    END IF;

    SELECT n_live_tup, n_dead_tup
    INTO v_live, v_dead
    FROM pg_stat_user_tables
    WHERE schemaname = split_part(p_relation_name, '.', 1)
      AND relname = split_part(p_relation_name, '.', 2);

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    RETURN v_dead >
        v_policy.analyze_threshold
        + v_policy.analyze_scale_factor * v_live;
END;
$$;

-- ============================================================
-- 10. MAINTENANCE REPORTING FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION vacuum_lab.record_maintenance(
    p_relation TEXT,
    p_operation VARCHAR(30),
    p_dead_before BIGINT,
    p_dead_after BIGINT,
    p_pages_before BIGINT,
    p_pages_after BIGINT,
    p_status VARCHAR(20),
    p_details TEXT DEFAULT NULL
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    INSERT INTO vacuum_lab.maintenance_log(
        relation_name,
        operation,
        dead_before,
        dead_after,
        pages_before,
        pages_after,
        execution_status,
        details
    )
    VALUES (
        p_relation,
        p_operation,
        p_dead_before,
        p_dead_after,
        p_pages_before,
        p_pages_after,
        p_status,
        p_details
    )
    RETURNING log_id INTO v_id;

    RETURN v_id;
END;
$$;

-- ============================================================
-- 11. MAINTENANCE EVALUATION REPORT
-- ============================================================

SELECT *
FROM vacuum_lab.evaluate_vacuum('vacuum_lab.orders');

SELECT vacuum_lab.evaluate_analyze('vacuum_lab.orders')
    AS analyze_required;

SELECT *
FROM vacuum_lab.table_storage_statistics;

SELECT *
FROM vacuum_lab.relation_storage;

-- ============================================================
-- 12. TRANSACTION VISIBILITY INFORMATION
-- ============================================================

-- Long-running transactions can prevent removal of dead tuples.
-- This query identifies active transactions and their ages.

SELECT
    pid,
    usename,
    application_name,
    state,
    xact_start,
    clock_timestamp() - xact_start AS transaction_age,
    backend_xid,
    backend_xmin,
    wait_event_type,
    wait_event
FROM pg_stat_activity
WHERE datname = current_database()
  AND xact_start IS NOT NULL
ORDER BY xact_start;

-- Inspect transaction ID age for the demonstration table.

SELECT
    c.oid::REGCLASS AS relation_name,
    age(c.relfrozenxid) AS xid_age,
    current_setting('autovacuum_freeze_max_age')
        AS freeze_max_age
FROM pg_class c
JOIN pg_namespace n
    ON n.oid = c.relnamespace
WHERE n.nspname = 'vacuum_lab'
  AND c.relkind = 'r';

-- ============================================================
-- 13. STANDARD VACUUM
-- ============================================================

-- VACUUM reclaims space occupied by removable dead tuples
-- for reuse within the relation.
--
-- It normally does not return the table's file space to the OS.

VACUUM (VERBOSE, ANALYZE)
    vacuum_lab.orders;

-- ============================================================
-- 14. POST-VACUUM STATISTICS
-- ============================================================

SELECT *
FROM vacuum_lab.table_storage_statistics;

SELECT *
FROM vacuum_lab.relation_storage;

-- ============================================================
-- 15. INSERT AND DELETE A SECOND WORKLOAD
-- ============================================================

INSERT INTO vacuum_lab.orders(
    user_id,
    order_reference,
    amount,
    status
)
SELECT
    u.user_id,
    'MAINTENANCE-' || u.user_id || '-' || n,
    500 + n,
    'PENDING'
FROM vacuum_lab.app_users u
CROSS JOIN generate_series(1, 50) AS n
ON CONFLICT (order_reference) DO NOTHING;

UPDATE vacuum_lab.orders
SET
    amount = amount * 1.10,
    status = 'COMPLETED'
WHERE order_reference LIKE 'MAINTENANCE-%'
  AND order_id % 2 = 0;

DELETE FROM vacuum_lab.orders
WHERE order_reference LIKE 'MAINTENANCE-%'
  AND order_id % 5 = 0;

-- ============================================================
-- 16. STANDARD VACUUM AND ANALYZE
-- ============================================================

VACUUM (VERBOSE, ANALYZE)
    vacuum_lab.orders;

-- ============================================================
-- 17. VACUUM FULL
-- ============================================================

-- VACUUM FULL rewrites the relation into a compact form.
-- It requires an ACCESS EXCLUSIVE lock.
-- It can temporarily require additional disk space.
-- It is not a routine substitute for standard VACUUM.
--
-- Execute outside an explicit transaction block.

VACUUM (FULL, VERBOSE, ANALYZE)
    vacuum_lab.orders;

-- ============================================================
-- 18. STORAGE COMPARISON
-- ============================================================

SELECT
    relation_name,
    heap_bytes,
    index_bytes,
    total_bytes,
    heap_size,
    index_size,
    total_size
FROM vacuum_lab.relation_storage;

-- ============================================================
-- 19. VACUUM FREEZE
-- ============================================================

-- FREEZE requests aggressive freezing of eligible tuples.
-- Freezing protects against transaction ID wraparound.
-- It does not mean that every tuple receives a newly
-- assigned transaction ID.

VACUUM (FREEZE, VERBOSE, ANALYZE)
    vacuum_lab.orders;

-- Inspect frozen transaction horizon.

SELECT
    c.oid::REGCLASS AS relation_name,
    age(c.relfrozenxid) AS xid_age,
    c.relfrozenxid
FROM pg_class c
JOIN pg_namespace n
    ON n.oid = c.relnamespace
WHERE n.nspname = 'vacuum_lab'
  AND c.relkind = 'r';

-- ============================================================
-- 20. AUTOVACUUM CONFIGURATION
-- ============================================================

-- Autovacuum settings are relation-specific where supported.
-- Actual workers operate asynchronously under PostgreSQL control.

ALTER TABLE vacuum_lab.orders
SET (
    autovacuum_enabled = TRUE,
    autovacuum_vacuum_threshold = 20,
    autovacuum_vacuum_scale_factor = 0.10,
    autovacuum_analyze_threshold = 10,
    autovacuum_analyze_scale_factor = 0.05,
    autovacuum_vacuum_cost_limit = 2000
);

-- Display effective relation-level configuration.

SELECT
    c.oid::REGCLASS AS relation_name,
    c.reloptions
FROM pg_class c
JOIN pg_namespace n
    ON n.oid = c.relnamespace
WHERE n.nspname = 'vacuum_lab'
  AND c.relname = 'orders';

-- ============================================================
-- 21. AUTOVACUUM WORKER MONITORING
-- ============================================================

SELECT
    pid,
    datname,
    relid::REGCLASS AS relation_name,
    phase,
    heap_blks_total,
    heap_blks_scanned,
    heap_blks_vacuumed,
    index_vacuum_count,
    num_dead_tuples,
    max_dead_tuples
FROM pg_stat_progress_vacuum;

-- ============================================================
-- 22. AGGREGATED STORAGE REPORT
-- ============================================================

CREATE OR REPLACE VIEW vacuum_lab.maintenance_summary AS
SELECT
    relation_name,
    COUNT(*) AS maintenance_runs,

    COUNT(*) FILTER (
        WHERE execution_status = 'SUCCESS'
    ) AS successful_runs,

    COUNT(*) FILTER (
        WHERE execution_status = 'FAILED'
    ) AS failed_runs,

    SUM(dead_before) AS dead_before_total,
    SUM(dead_after) AS dead_after_total,

    MAX(executed_at) AS last_maintenance

FROM vacuum_lab.maintenance_log
GROUP BY relation_name;

-- ============================================================
-- 23. DEMONSTRATE MAINTENANCE LOGGING
-- ============================================================

SELECT vacuum_lab.record_maintenance(
    'vacuum_lab.orders',
    'VACUUM',
    20,
    0,
    15,
    15,
    'SUCCESS',
    'Standard vacuum completed; reusable space made available'
);

SELECT vacuum_lab.record_maintenance(
    'vacuum_lab.orders',
    'ANALYZE',
    0,
    0,
    15,
    15,
    'SUCCESS',
    'Planner statistics refreshed'
);

-- ============================================================
-- 24. TRANSACTION SNAPSHOT TRACKING
-- ============================================================

-- This table provides an application-level audit example.
-- It does not replace PostgreSQL's internal MVCC snapshots.

BEGIN;

INSERT INTO vacuum_lab.transaction_snapshots(
    transaction_label,
    transaction_xid
)
VALUES (
    'maintenance-audit',
    pg_current_xact_id()::TEXT::XID
);

COMMIT;

UPDATE vacuum_lab.transaction_snapshots
SET completed_at = CURRENT_TIMESTAMP
WHERE transaction_label = 'maintenance-audit'
  AND completed_at IS NULL;

-- ============================================================
-- 25. CTE-BASED DEAD TUPLE EVALUATION
-- ============================================================

WITH storage AS (
    SELECT
        schemaname,
        relname,
        n_live_tup,
        n_dead_tup
    FROM pg_stat_user_tables
    WHERE schemaname = 'vacuum_lab'
),
evaluation AS (
    SELECT
        s.*,
        p.vacuum_threshold
            + p.vacuum_scale_factor * s.n_live_tup
            AS calculated_threshold,
        p.max_dead_ratio
    FROM storage s
    JOIN vacuum_lab.autovacuum_policies p
        ON p.relation_name =
            s.schemaname || '.' || s.relname
)
SELECT
    relname,
    n_live_tup,
    n_dead_tup,
    calculated_threshold,

    ROUND(
        100.0 * n_dead_tup /
        GREATEST(n_live_tup + n_dead_tup, 1),
        2
    ) AS dead_percentage,

    (
        n_dead_tup > calculated_threshold
        OR
        n_dead_tup::NUMERIC /
        GREATEST(n_live_tup + n_dead_tup, 1)
            > max_dead_ratio
    ) AS maintenance_required

FROM evaluation;

-- ============================================================
-- 26. FINAL REPORT
-- ============================================================

SELECT *
FROM vacuum_lab.table_storage_statistics;

SELECT *
FROM vacuum_lab.relation_storage;

SELECT *
FROM vacuum_lab.maintenance_summary;

SELECT
    log_id,
    relation_name,
    operation,
    execution_status,
    dead_before,
    dead_after,
    pages_before,
    pages_after,
    executed_at,
    details
FROM vacuum_lab.maintenance_log
ORDER BY executed_at DESC;

-- ============================================================
-- 27. VALIDATION QUERIES
-- ============================================================

-- Check primary-key uniqueness.

SELECT
    order_id,
    COUNT(*)
FROM vacuum_lab.orders
GROUP BY order_id
HAVING COUNT(*) > 1;

-- Check invalid business values.

SELECT *
FROM vacuum_lab.orders
WHERE amount < 0
   OR version_number < 1
   OR status NOT IN (
       'PENDING',
       'PROCESSING',
       'COMPLETED',
       'CANCELLED'
   );

-- Check orphaned foreign keys.

SELECT o.*
FROM vacuum_lab.orders o
LEFT JOIN vacuum_lab.app_users u
    ON u.user_id = o.user_id
WHERE u.user_id IS NULL;

-- Check failed maintenance operations.

SELECT *
FROM vacuum_lab.maintenance_log
WHERE execution_status = 'FAILED';

-- ============================================================
-- END OF SCRIPT
--
-- Important operational distinction:
--
-- Standard VACUUM:
--   Makes removable dead-tuple space reusable.
--
-- VACUUM FULL:
--   Rewrites and compacts the relation and can return
--   filesystem space, subject to filesystem and storage behavior.
--
-- ANALYZE:
--   Refreshes planner statistics.
--
-- FREEZE:
--   Advances tuple freezing to protect transaction ID safety.
--
-- AUTOVACUUM:
--   PostgreSQL-managed background maintenance.
--
-- VACUUM is not a replacement for transaction management,
-- index maintenance, capacity monitoring, or query optimization.
-- ============================================================
