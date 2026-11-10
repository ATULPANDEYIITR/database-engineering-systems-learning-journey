/*
===============================================================================
DATABASE CHECKPOINTS, DIRTY PAGES, WRITE-AHEAD LOGGING AND RECOVERY
PostgreSQL 14+

Models:
- Database repositories and storage-engine instances
- Pages and persistent page images
- Write-ahead log records
- Log sequence numbers
- Transactions
- Dirty-page tracking
- Fuzzy checkpoints
- Checkpoint transaction snapshots
- Recovery analysis
- Redo and undo decisions
- Compensation log records
- Recovery eligibility and reporting

This is an educational storage-engine model. It does not replace PostgreSQL's
native WAL, checkpoint, buffer manager, crash recovery or replication systems.
===============================================================================
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS checkpoint_lab;

SET search_path TO checkpoint_lab, public;

-- ============================================================================
-- 1. DOMAIN TYPES
-- ============================================================================

CREATE TYPE transaction_status AS ENUM (
    'ACTIVE',
    'COMMITTED',
    'ABORTED',
    'ENDED'
);

CREATE TYPE log_record_type AS ENUM (
    'BEGIN',
    'UPDATE',
    'COMMIT',
    'ABORT',
    'END',
    'CHECKPOINT_BEGIN',
    'CHECKPOINT_END',
    'CLR'
);

CREATE TYPE checkpoint_status AS ENUM (
    'IN_PROGRESS',
    'COMPLETED',
    'FAILED'
);

CREATE TYPE recovery_status AS ENUM (
    'PENDING',
    'ANALYSIS',
    'REDO',
    'UNDO',
    'COMPLETED',
    'FAILED'
);

-- ============================================================================
-- 2. STORAGE ENGINE AND DATABASE INSTANCE
-- ============================================================================

CREATE TABLE storage_engines (
    engine_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_name VARCHAR(100) NOT NULL UNIQUE,
    database_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    current_lsn BIGINT NOT NULL DEFAULT 0 CHECK (current_lsn >= 0),
    durable_lsn BIGINT NOT NULL DEFAULT 0 CHECK (durable_lsn >= 0),
    CONSTRAINT valid_durable_boundary
        CHECK (durable_lsn <= current_lsn)
);

-- ============================================================================
-- 3. TRANSACTIONS
-- ============================================================================

CREATE TABLE database_transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_id BIGINT NOT NULL REFERENCES storage_engines(engine_id),
    status transaction_status NOT NULL DEFAULT 'ACTIVE',
    begin_lsn BIGINT NOT NULL CHECK (begin_lsn > 0),
    last_lsn BIGINT NOT NULL CHECK (last_lsn > 0),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    CONSTRAINT valid_transaction_lsn
        CHECK (last_lsn >= begin_lsn),
    CONSTRAINT valid_completion
        CHECK (
            (status = 'ACTIVE' AND completed_at IS NULL)
            OR
            (status <> 'ACTIVE' AND completed_at IS NOT NULL)
        )
);

CREATE INDEX idx_transactions_engine_status
    ON database_transactions(engine_id, status);

-- ============================================================================
-- 4. DATABASE PAGES
-- ============================================================================

CREATE TABLE database_pages (
    engine_id BIGINT NOT NULL REFERENCES storage_engines(engine_id),
    page_id VARCHAR(128) NOT NULL,
    page_value BIGINT NOT NULL,
    page_lsn BIGINT NOT NULL DEFAULT 0 CHECK (page_lsn >= 0),
    dirty BOOLEAN NOT NULL DEFAULT FALSE,
    rec_lsn BIGINT,
    last_flushed_at TIMESTAMPTZ,
    PRIMARY KEY (engine_id, page_id),
    CONSTRAINT valid_rec_lsn
        CHECK (
            (dirty = TRUE AND rec_lsn IS NOT NULL)
            OR
            (dirty = FALSE AND rec_lsn IS NULL)
        ),
    CONSTRAINT valid_page_lsn
        CHECK (rec_lsn IS NULL OR rec_lsn <= page_lsn)
);

CREATE INDEX idx_dirty_pages
    ON database_pages(engine_id, rec_lsn)
    WHERE dirty = TRUE;

-- ============================================================================
-- 5. WRITE-AHEAD LOG
-- ============================================================================

CREATE TABLE wal_records (
    engine_id BIGINT NOT NULL REFERENCES storage_engines(engine_id),
    lsn BIGINT NOT NULL CHECK (lsn > 0),
    transaction_id BIGINT,
    record_type log_record_type NOT NULL,
    page_id VARCHAR(128),
    old_value BIGINT,
    new_value BIGINT,
    undo_next_lsn BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (engine_id, lsn),

    FOREIGN KEY (transaction_id)
        REFERENCES database_transactions(transaction_id),

    CONSTRAINT valid_update_record
        CHECK (
            record_type NOT IN ('UPDATE', 'CLR')
            OR (
                transaction_id IS NOT NULL
                AND page_id IS NOT NULL
                AND old_value IS NOT NULL
                AND new_value IS NOT NULL
            )
        ),

    CONSTRAINT valid_undo_pointer
        CHECK (
            undo_next_lsn IS NULL
            OR undo_next_lsn < lsn
        )
);

CREATE INDEX idx_wal_transaction
    ON wal_records(engine_id, transaction_id, lsn DESC);

CREATE INDEX idx_wal_page
    ON wal_records(engine_id, page_id, lsn)
    WHERE page_id IS NOT NULL;

CREATE INDEX idx_wal_record_type
    ON wal_records(engine_id, record_type, lsn);

ALTER TABLE wal_records
    ADD CONSTRAINT fk_wal_page
    FOREIGN KEY (engine_id, page_id)
    REFERENCES database_pages(engine_id, page_id);

-- ============================================================================
-- 6. CHECKPOINT METADATA
-- ============================================================================

CREATE TABLE checkpoints (
    checkpoint_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_id BIGINT NOT NULL REFERENCES storage_engines(engine_id),
    begin_lsn BIGINT NOT NULL CHECK (begin_lsn > 0),
    end_lsn BIGINT,
    status checkpoint_status NOT NULL DEFAULT 'IN_PROGRESS',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    CONSTRAINT valid_checkpoint_range
        CHECK (end_lsn IS NULL OR end_lsn >= begin_lsn),
    CONSTRAINT valid_checkpoint_completion
        CHECK (
            (status = 'IN_PROGRESS'
                AND end_lsn IS NULL
                AND completed_at IS NULL)
            OR
            (status = 'COMPLETED'
                AND end_lsn IS NOT NULL
                AND completed_at IS NOT NULL)
            OR
            (status = 'FAILED'
                AND completed_at IS NOT NULL)
        )
);

CREATE INDEX idx_checkpoint_latest
    ON checkpoints(engine_id, end_lsn DESC)
    WHERE status = 'COMPLETED';

CREATE TABLE checkpoint_dirty_pages (
    checkpoint_id BIGINT NOT NULL
        REFERENCES checkpoints(checkpoint_id) ON DELETE CASCADE,
    engine_id BIGINT NOT NULL,
    page_id VARCHAR(128) NOT NULL,
    rec_lsn BIGINT NOT NULL CHECK (rec_lsn > 0),

    PRIMARY KEY (checkpoint_id, page_id),

    FOREIGN KEY (engine_id, page_id)
        REFERENCES database_pages(engine_id, page_id)
);

CREATE TABLE checkpoint_transactions (
    checkpoint_id BIGINT NOT NULL
        REFERENCES checkpoints(checkpoint_id) ON DELETE CASCADE,
    transaction_id BIGINT NOT NULL
        REFERENCES database_transactions(transaction_id),
    status transaction_status NOT NULL,
    last_lsn BIGINT NOT NULL CHECK (last_lsn > 0),

    PRIMARY KEY (checkpoint_id, transaction_id)
);

-- ============================================================================
-- 7. RECOVERY EXECUTION
-- ============================================================================

CREATE TABLE recovery_runs (
    recovery_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_id BIGINT NOT NULL REFERENCES storage_engines(engine_id),
    checkpoint_id BIGINT REFERENCES checkpoints(checkpoint_id),
    status recovery_status NOT NULL DEFAULT 'PENDING',
    redo_start_lsn BIGINT,
    redo_count BIGINT NOT NULL DEFAULT 0 CHECK (redo_count >= 0),
    undo_count BIGINT NOT NULL DEFAULT 0 CHECK (undo_count >= 0),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE TABLE recovery_actions (
    action_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recovery_id BIGINT NOT NULL
        REFERENCES recovery_runs(recovery_id) ON DELETE CASCADE,
    lsn BIGINT NOT NULL,
    transaction_id BIGINT,
    page_id VARCHAR(128),
    action_type VARCHAR(20) NOT NULL
        CHECK (action_type IN ('REDO', 'UNDO', 'SKIP')),
    old_value BIGINT,
    new_value BIGINT,
    action_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_recovery_actions_run
    ON recovery_actions(recovery_id, action_type, lsn);

-- ============================================================================
-- 8. WAL APPEND FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION append_wal_record(
    p_engine_id BIGINT,
    p_record_type log_record_type,
    p_transaction_id BIGINT DEFAULT NULL,
    p_page_id VARCHAR DEFAULT NULL,
    p_old_value BIGINT DEFAULT NULL,
    p_new_value BIGINT DEFAULT NULL,
    p_undo_next_lsn BIGINT DEFAULT NULL
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_lsn BIGINT;
BEGIN
    UPDATE storage_engines
    SET current_lsn = current_lsn + 1
    WHERE engine_id = p_engine_id
    RETURNING current_lsn INTO v_lsn;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown engine: %', p_engine_id;
    END IF;

    INSERT INTO wal_records (
        engine_id,
        lsn,
        transaction_id,
        record_type,
        page_id,
        old_value,
        new_value,
        undo_next_lsn
    )
    VALUES (
        p_engine_id,
        v_lsn,
        p_transaction_id,
        p_record_type,
        p_page_id,
        p_old_value,
        p_new_value,
        p_undo_next_lsn
    );

    RETURN v_lsn;
END;
$$;

-- ============================================================================
-- 9. WAL FLUSH FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION flush_wal(
    p_engine_id BIGINT,
    p_target_lsn BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_current BIGINT;
    v_durable BIGINT;
BEGIN
    SELECT current_lsn, durable_lsn
    INTO v_current, v_durable
    FROM storage_engines
    WHERE engine_id = p_engine_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown engine';
    END IF;

    IF p_target_lsn < v_durable
       OR p_target_lsn > v_current THEN
        RAISE EXCEPTION 'Invalid WAL flush boundary';
    END IF;

    UPDATE storage_engines
    SET durable_lsn = p_target_lsn
    WHERE engine_id = p_engine_id;
END;
$$;

-- ============================================================================
-- 10. TRANSACTION START
-- ============================================================================

CREATE OR REPLACE FUNCTION begin_transaction(
    p_engine_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_id BIGINT;
    v_lsn BIGINT;
BEGIN
    INSERT INTO database_transactions (
        engine_id,
        begin_lsn,
        last_lsn
    )
    VALUES (
        p_engine_id,
        1,
        1
    )
    RETURNING transaction_id INTO v_transaction_id;

    v_lsn := append_wal_record(
        p_engine_id,
        'BEGIN',
        v_transaction_id
    );

    UPDATE database_transactions
    SET begin_lsn = v_lsn,
        last_lsn = v_lsn
    WHERE transaction_id = v_transaction_id;

    RETURN v_transaction_id;
END;
$$;

-- ============================================================================
-- 11. PAGE UPDATE WITH WAL-FIRST ORDERING
-- ============================================================================

CREATE OR REPLACE FUNCTION update_database_page(
    p_transaction_id BIGINT,
    p_page_id VARCHAR,
    p_new_value BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_engine_id BIGINT;
    v_old_value BIGINT;
    v_lsn BIGINT;
    v_dirty BOOLEAN;
BEGIN
    SELECT engine_id
    INTO v_engine_id
    FROM database_transactions
    WHERE transaction_id = p_transaction_id
      AND status = 'ACTIVE'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Transaction is not active';
    END IF;

    SELECT page_value, dirty
    INTO v_old_value, v_dirty
    FROM database_pages
    WHERE engine_id = v_engine_id
      AND page_id = p_page_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Page does not exist: %', p_page_id;
    END IF;

    v_lsn := append_wal_record(
        v_engine_id,
        'UPDATE',
        p_transaction_id,
        p_page_id,
        v_old_value,
        p_new_value
    );

    UPDATE database_pages
    SET page_value = p_new_value,
        page_lsn = v_lsn,
        dirty = TRUE,
        rec_lsn = CASE
            WHEN v_dirty THEN rec_lsn
            ELSE v_lsn
        END
    WHERE engine_id = v_engine_id
      AND page_id = p_page_id;

    UPDATE database_transactions
    SET last_lsn = v_lsn
    WHERE transaction_id = p_transaction_id;

    RETURN v_lsn;
END;
$$;

-- ============================================================================
-- 12. TRANSACTION COMMIT
-- ============================================================================

CREATE OR REPLACE PROCEDURE commit_transaction(
    p_transaction_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_engine_id BIGINT;
    v_commit_lsn BIGINT;
    v_end_lsn BIGINT;
BEGIN
    SELECT engine_id
    INTO v_engine_id
    FROM database_transactions
    WHERE transaction_id = p_transaction_id
      AND status = 'ACTIVE'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Cannot commit inactive transaction';
    END IF;

    v_commit_lsn := append_wal_record(
        v_engine_id,
        'COMMIT',
        p_transaction_id
    );

    UPDATE database_transactions
    SET last_lsn = v_commit_lsn
    WHERE transaction_id = p_transaction_id;

    -- Force commit WAL to stable storage before acknowledging commit.
    PERFORM flush_wal(v_engine_id, v_commit_lsn);

    UPDATE database_transactions
    SET status = 'COMMITTED',
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = p_transaction_id;

    v_end_lsn := append_wal_record(
        v_engine_id,
        'END',
        p_transaction_id
    );

    UPDATE database_transactions
    SET last_lsn = v_end_lsn
    WHERE transaction_id = p_transaction_id;
END;
$$;

-- ============================================================================
-- 13. DATA PAGE FLUSH
-- ============================================================================

CREATE OR REPLACE PROCEDURE flush_database_page(
    p_engine_id BIGINT,
    p_page_id VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_page_lsn BIGINT;
    v_durable_lsn BIGINT;
BEGIN
    SELECT page_lsn
    INTO v_page_lsn
    FROM database_pages
    WHERE engine_id = p_engine_id
      AND page_id = p_page_id
      AND dirty = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT durable_lsn
    INTO v_durable_lsn
    FROM storage_engines
    WHERE engine_id = p_engine_id;

    IF v_durable_lsn < v_page_lsn THEN
        RAISE EXCEPTION
            'WAL must be flushed before page %',
            p_page_id;
    END IF;

    UPDATE database_pages
    SET dirty = FALSE,
        rec_lsn = NULL,
        last_flushed_at = CURRENT_TIMESTAMP
    WHERE engine_id = p_engine_id
      AND page_id = p_page_id;
END;
$$;

-- ============================================================================
-- 14. FUZZY CHECKPOINT CREATION
-- ============================================================================

CREATE OR REPLACE PROCEDURE create_checkpoint(
    p_engine_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_begin_lsn BIGINT;
    v_end_lsn BIGINT;
    v_checkpoint_id BIGINT;
BEGIN
    v_begin_lsn := append_wal_record(
        p_engine_id,
        'CHECKPOINT_BEGIN'
    );

    INSERT INTO checkpoints (
        engine_id,
        begin_lsn
    )
    VALUES (
        p_engine_id,
        v_begin_lsn
    )
    RETURNING checkpoint_id INTO v_checkpoint_id;

    -- Capture the current dirty-page table.
    INSERT INTO checkpoint_dirty_pages (
        checkpoint_id,
        engine_id,
        page_id,
        rec_lsn
    )
    SELECT
        v_checkpoint_id,
        engine_id,
        page_id,
        rec_lsn
    FROM database_pages
    WHERE engine_id = p_engine_id
      AND dirty = TRUE;

    -- Capture transactions that are still active.
    INSERT INTO checkpoint_transactions (
        checkpoint_id,
        transaction_id,
        status,
        last_lsn
    )
    SELECT
        v_checkpoint_id,
        transaction_id,
        status,
        last_lsn
    FROM database_transactions
    WHERE engine_id = p_engine_id
      AND status = 'ACTIVE';

    v_end_lsn := append_wal_record(
        p_engine_id,
        'CHECKPOINT_END'
    );

    PERFORM flush_wal(p_engine_id, v_end_lsn);

    UPDATE checkpoints
    SET end_lsn = v_end_lsn,
        status = 'COMPLETED',
        completed_at = CURRENT_TIMESTAMP
    WHERE checkpoint_id = v_checkpoint_id;
END;
$$;

-- ============================================================================
-- 15. RECOVERY ANALYSIS VIEW
-- ============================================================================

CREATE OR REPLACE VIEW recovery_transaction_analysis AS
SELECT
    engine_id,
    transaction_id,
    MAX(lsn) FILTER (
        WHERE record_type = 'BEGIN'
    ) AS begin_lsn,
    MAX(lsn) FILTER (
        WHERE record_type = 'COMMIT'
    ) AS commit_lsn,
    MAX(lsn) FILTER (
        WHERE record_type = 'ABORT'
    ) AS abort_lsn,
    MAX(lsn) AS last_lsn,
    CASE
        WHEN BOOL_OR(record_type = 'COMMIT') THEN 'COMMITTED'
        WHEN BOOL_OR(record_type = 'ABORT') THEN 'ABORTED'
        WHEN BOOL_OR(record_type = 'BEGIN') THEN 'ACTIVE'
        ELSE 'UNKNOWN'
    END AS inferred_state
FROM wal_records
GROUP BY engine_id, transaction_id;

-- ============================================================================
-- 16. RECOVERY PLAN FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_recovery_plan(
    p_engine_id BIGINT
)
RETURNS TABLE (
    checkpoint_id BIGINT,
    checkpoint_end_lsn BIGINT,
    redo_start_lsn BIGINT,
    dirty_page_count BIGINT,
    active_transaction_count BIGINT
)
LANGUAGE sql
STABLE
AS $$
    WITH latest_checkpoint AS (
        SELECT
            c.checkpoint_id,
            c.end_lsn
        FROM checkpoints c
        JOIN storage_engines e
          ON e.engine_id = c.engine_id
        WHERE c.engine_id = p_engine_id
          AND c.status = 'COMPLETED'
          AND c.end_lsn <= e.durable_lsn
        ORDER BY c.end_lsn DESC
        LIMIT 1
    ),
    checkpoint_statistics AS (
        SELECT
            lc.checkpoint_id,
            lc.end_lsn,
            MIN(dp.rec_lsn) AS earliest_rec_lsn,
            COUNT(DISTINCT dp.page_id) AS dirty_count,
            COUNT(DISTINCT ct.transaction_id) AS active_count
        FROM latest_checkpoint lc
        LEFT JOIN checkpoint_dirty_pages dp
          ON dp.checkpoint_id = lc.checkpoint_id
        LEFT JOIN checkpoint_transactions ct
          ON ct.checkpoint_id = lc.checkpoint_id
        GROUP BY lc.checkpoint_id, lc.end_lsn
    )
    SELECT
        cs.checkpoint_id,
        cs.end_lsn,
        COALESCE(
            cs.earliest_rec_lsn,
            cs.end_lsn + 1
        ),
        cs.dirty_count,
        cs.active_count
    FROM checkpoint_statistics cs;
$$;

-- ============================================================================
-- 17. RECOVERY ELIGIBILITY VIEW
-- ============================================================================

CREATE OR REPLACE VIEW recovery_eligibility AS
SELECT
    e.engine_id,
    e.engine_name,
    e.current_lsn,
    e.durable_lsn,
    COUNT(p.page_id) FILTER (
        WHERE p.dirty = TRUE
    ) AS dirty_page_count,
    COUNT(t.transaction_id) FILTER (
        WHERE t.status = 'ACTIVE'
    ) AS active_transaction_count,
    CASE
        WHEN e.durable_lsn > e.current_lsn THEN FALSE
        WHEN COUNT(p.page_id) FILTER (
            WHERE p.dirty = TRUE
              AND p.rec_lsn IS NULL
        ) > 0 THEN FALSE
        ELSE TRUE
    END AS metadata_valid
FROM storage_engines e
LEFT JOIN database_pages p
    ON p.engine_id = e.engine_id
LEFT JOIN database_transactions t
    ON t.engine_id = e.engine_id
GROUP BY
    e.engine_id,
    e.engine_name,
    e.current_lsn,
    e.durable_lsn;

-- ============================================================================
-- 18. REPORTING QUERIES
-- ============================================================================

-- Latest completed checkpoint for every engine.
CREATE OR REPLACE VIEW latest_checkpoint_report AS
SELECT DISTINCT ON (engine_id)
    engine_id,
    checkpoint_id,
    begin_lsn,
    end_lsn,
    started_at,
    completed_at
FROM checkpoints
WHERE status = 'COMPLETED'
ORDER BY engine_id, end_lsn DESC;

-- Dirty-page reporting.
CREATE OR REPLACE VIEW dirty_page_report AS
SELECT
    engine_id,
    page_id,
    page_lsn,
    rec_lsn,
    page_lsn - rec_lsn AS lsn_span
FROM database_pages
WHERE dirty = TRUE;

-- WAL volume by record type.
CREATE OR REPLACE VIEW wal_statistics AS
SELECT
    engine_id,
    record_type,
    COUNT(*) AS record_count,
    MIN(lsn) AS first_lsn,
    MAX(lsn) AS last_lsn
FROM wal_records
GROUP BY engine_id, record_type;

-- ============================================================================
-- 19. SAMPLE STORAGE ENGINE
-- ============================================================================

INSERT INTO storage_engines (
    engine_name,
    database_name
)
VALUES (
    'ACCOUNT_STORAGE_ENGINE',
    'banking_database'
);

INSERT INTO database_pages (
    engine_id,
    page_id,
    page_value
)
VALUES
    (1, 'ACCOUNT_101', 1000),
    (1, 'ACCOUNT_202', 2000),
    (1, 'ACCOUNT_303', 3000);

-- ============================================================================
-- 20. TRANSACTION 1: COMMITTED UPDATE
-- ============================================================================

DO $$
DECLARE
    v_transaction_id BIGINT;
BEGIN
    v_transaction_id := begin_transaction(1);

    PERFORM update_database_page(
        v_transaction_id,
        'ACCOUNT_101',
        1100
    );

    CALL commit_transaction(v_transaction_id);

    -- The WAL is durable before the page can be flushed.
    CALL flush_database_page(1, 'ACCOUNT_101');
END;
$$;

-- ============================================================================
-- 21. TRANSACTION 2: ACTIVE AT CHECKPOINT
-- ============================================================================

DO $$
DECLARE
    v_transaction_id BIGINT;
BEGIN
    v_transaction_id := begin_transaction(1);

    PERFORM update_database_page(
        v_transaction_id,
        'ACCOUNT_202',
        1800
    );

    CALL create_checkpoint(1);

    -- Another update occurs after the checkpoint.
    PERFORM update_database_page(
        v_transaction_id,
        'ACCOUNT_202',
        1700
    );

    -- No COMMIT is issued.
END;
$$;

-- ============================================================================
-- 22. TRANSACTION 3: COMMITTED AFTER CHECKPOINT
-- ============================================================================

DO $$
DECLARE
    v_transaction_id BIGINT;
BEGIN
    v_transaction_id := begin_transaction(1);

    PERFORM update_database_page(
        v_transaction_id,
        'ACCOUNT_303',
        3500
    );

    CALL commit_transaction(v_transaction_id);
END;
$$;

-- ============================================================================
-- 23. RECOVERY SIMULATION
-- ============================================================================

/*
The following transaction demonstrates a recovery plan and records
analysis decisions. It models recovery decisions, not physical disk
recovery performed by PostgreSQL itself.
*/

BEGIN;

INSERT INTO recovery_runs (
    engine_id,
    checkpoint_id,
    status
)
SELECT
    c.engine_id,
    c.checkpoint_id,
    'ANALYSIS'
FROM latest_checkpoint_report c
WHERE c.engine_id = 1
RETURNING recovery_id;

-- Analysis and redo starting point.
WITH recovery_plan AS (
    SELECT *
    FROM calculate_recovery_plan(1)
),
durable_log AS (
    SELECT w.*
    FROM wal_records w
    JOIN storage_engines e
      ON e.engine_id = w.engine_id
    WHERE w.engine_id = 1
      AND w.lsn <= e.durable_lsn
)
SELECT
    d.lsn,
    d.record_type,
    d.transaction_id,
    d.page_id,
    d.old_value,
    d.new_value,
    CASE
        WHEN d.record_type IN ('UPDATE', 'CLR')
         AND d.lsn >= COALESCE(
             p.redo_start_lsn,
             1
         )
        THEN 'REDO_CANDIDATE'
        ELSE 'ANALYSIS_ONLY'
    END AS recovery_decision
FROM durable_log d
CROSS JOIN recovery_plan p
ORDER BY d.lsn;

-- Identify committed and incomplete transactions.
SELECT
    transaction_id,
    inferred_state,
    begin_lsn,
    commit_lsn,
    last_lsn
FROM recovery_transaction_analysis
WHERE engine_id = 1
ORDER BY transaction_id;

-- ============================================================================
-- 24. VALIDATION QUERIES
-- ============================================================================

-- No dirty page may lack a recovery LSN.
SELECT
    engine_id,
    page_id,
    dirty,
    rec_lsn
FROM database_pages
WHERE dirty = TRUE
  AND rec_lsn IS NULL;

-- No data page may require WAL that is not durable.
SELECT
    p.engine_id,
    p.page_id,
    p.page_lsn,
    e.durable_lsn
FROM database_pages p
JOIN storage_engines e
    ON e.engine_id = p.engine_id
WHERE p.page_lsn > e.durable_lsn;

-- Incomplete transactions.
SELECT
    transaction_id,
    engine_id,
    status,
    begin_lsn,
    last_lsn
FROM database_transactions
WHERE status = 'ACTIVE'
ORDER BY transaction_id;

-- Checkpoint recovery start positions.
SELECT *
FROM calculate_recovery_plan(1);

-- ============================================================================
-- 25. AGGREGATION AND REPORTING
-- ============================================================================

SELECT
    e.engine_name,
    COUNT(DISTINCT p.page_id) AS total_pages,
    COUNT(DISTINCT p.page_id) FILTER (
        WHERE p.dirty
    ) AS dirty_pages,
    COUNT(DISTINCT t.transaction_id) AS total_transactions,
    COUNT(DISTINCT t.transaction_id) FILTER (
        WHERE t.status = 'COMMITTED'
    ) AS committed_transactions,
    COUNT(DISTINCT t.transaction_id) FILTER (
        WHERE t.status = 'ACTIVE'
    ) AS active_transactions
FROM storage_engines e
LEFT JOIN database_pages p
    ON p.engine_id = e.engine_id
LEFT JOIN database_transactions t
    ON t.engine_id = e.engine_id
GROUP BY e.engine_id, e.engine_name;

SELECT * FROM latest_checkpoint_report;
SELECT * FROM dirty_page_report;
SELECT * FROM wal_statistics;
SELECT * FROM recovery_eligibility;

-- ============================================================================
-- 26. ROLLBACK OF REPORTING TRANSACTION
-- ============================================================================

-- The preceding recovery analysis is observational.
-- Preserve the sample database and its checkpoint metadata.
COMMIT;

/*
Operational considerations:

1. PostgreSQL's actual WAL is maintained by the database storage engine.
2. A SQL transaction commit does not expose internal page flush ordering.
3. A fuzzy checkpoint does not require all dirty pages to be written.
4. The earliest rec_lsn in the dirty-page table determines a conservative
   redo starting point in this educational model.
5. WAL durability must precede corresponding data-page durability.
6. Real recovery requires durable page images, complete WAL records,
   transaction-chain information, compensation records and crash-safe
   metadata.
7. Production systems also account for full-page images, WAL recycling,
   replication, archive recovery, timelines and storage failures.
*/
