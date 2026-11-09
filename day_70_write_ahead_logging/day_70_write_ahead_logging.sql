/*
 * WRITE-AHEAD LOGGING: DURABILITY AND CRASH RECOVERY
 * PostgreSQL 14+
 *
 * This script implements an educational WAL model.
 * It does not modify PostgreSQL's internal WAL subsystem.
 *
 * Demonstrates:
 * - Repositories of database transactions and log records
 * - Monotonic LSN allocation
 * - Transaction lifecycle
 * - Write-ahead ordering
 * - Checksums
 * - Commit durability metadata
 * - Checkpoints
 * - Dirty-page tracking
 * - Analysis, REDO and UNDO
 * - Recovery completion
 * - Transaction isolation through row locks
 * - Constraints, triggers, indexes and reporting
 *
 * Execute using psql.
 */

DROP SCHEMA IF EXISTS wal_lab CASCADE;
CREATE SCHEMA wal_lab;

SET search_path TO wal_lab, public;

-- ============================================================
-- 1. DOMAIN TYPES
-- ============================================================

CREATE TYPE log_record_type AS ENUM (
    'BEGIN',
    'UPDATE',
    'COMMIT',
    'ABORT',
    'CHECKPOINT'
);

CREATE TYPE transaction_status AS ENUM (
    'ACTIVE',
    'COMMITTED',
    'ABORTED'
);

CREATE TYPE recovery_phase AS ENUM (
    'ANALYSIS',
    'REDO',
    'UNDO',
    'COMPLETED'
);

-- ============================================================
-- 2. TRANSACTION METADATA
-- ============================================================

CREATE TABLE wal_transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_name VARCHAR(100) NOT NULL,
    status transaction_status NOT NULL DEFAULT 'ACTIVE',
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ,
    CHECK (
        (status = 'ACTIVE' AND completed_at IS NULL)
        OR
        (status <> 'ACTIVE' AND completed_at IS NOT NULL)
    )
);

-- ============================================================
-- 3. DATA PAGES
-- ============================================================

CREATE TABLE database_pages (
    page_key VARCHAR(128) PRIMARY KEY,
    page_value BIGINT NOT NULL,
    page_lsn BIGINT NOT NULL DEFAULT 0,
    is_dirty BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- ============================================================
-- 4. WRITE-AHEAD LOG
-- ============================================================

CREATE TABLE wal_records (
    lsn BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id BIGINT NOT NULL
        REFERENCES wal_transactions(transaction_id),
    record_type log_record_type NOT NULL,
    page_key VARCHAR(128),
    old_value BIGINT,
    new_value BIGINT,
    checksum TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CHECK (
        (record_type = 'UPDATE'
            AND page_key IS NOT NULL
            AND new_value IS NOT NULL)
        OR
        (record_type <> 'UPDATE'
            AND page_key IS NULL
            AND old_value IS NULL
            AND new_value IS NULL)
    )
);

CREATE INDEX idx_wal_transaction_lsn
    ON wal_records(transaction_id, lsn);

CREATE INDEX idx_wal_record_type_lsn
    ON wal_records(record_type, lsn);

CREATE INDEX idx_wal_page_lsn
    ON wal_records(page_key, lsn)
    WHERE record_type = 'UPDATE';

-- ============================================================
-- 5. CHECKPOINT METADATA
-- ============================================================

CREATE TABLE wal_checkpoints (
    checkpoint_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    checkpoint_lsn BIGINT NOT NULL UNIQUE,
    active_transactions BIGINT[] NOT NULL DEFAULT '{}',
    dirty_pages JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- ============================================================
-- 6. RECOVERY EXECUTION
-- ============================================================

CREATE TABLE recovery_runs (
    recovery_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ,
    phase recovery_phase NOT NULL DEFAULT 'ANALYSIS',
    recovery_message TEXT,
    CHECK (
        (phase = 'COMPLETED' AND completed_at IS NOT NULL)
        OR
        (phase <> 'COMPLETED' AND completed_at IS NULL)
    )
);

CREATE TABLE recovery_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recovery_id BIGINT NOT NULL
        REFERENCES recovery_runs(recovery_id),
    transaction_id BIGINT,
    lsn BIGINT,
    phase recovery_phase NOT NULL,
    operation TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_recovery_events_run
    ON recovery_events(recovery_id, phase, event_id);

-- ============================================================
-- 7. CHECKSUM FUNCTION
-- ============================================================

CREATE FUNCTION calculate_wal_checksum(
    p_lsn BIGINT,
    p_transaction_id BIGINT,
    p_type log_record_type,
    p_key TEXT,
    p_old BIGINT,
    p_new BIGINT
)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT md5(
        concat_ws(
            '|',
            p_lsn,
            p_transaction_id,
            p_type::TEXT,
            COALESCE(p_key, ''),
            COALESCE(p_old::TEXT, 'NULL'),
            COALESCE(p_new::TEXT, 'NULL')
        )
    );
$$;

-- ============================================================
-- 8. WAL INSERT VALIDATION
-- ============================================================

CREATE FUNCTION validate_wal_record()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.record_type = 'UPDATE' THEN
        IF NEW.page_key IS NULL OR NEW.new_value IS NULL THEN
            RAISE EXCEPTION 'UPDATE requires a key and new value';
        END IF;
    END IF;

    IF NEW.record_type IN ('COMMIT', 'ABORT') THEN
        IF EXISTS (
            SELECT 1
            FROM wal_records
            WHERE transaction_id = NEW.transaction_id
              AND record_type IN ('COMMIT', 'ABORT')
        ) THEN
            RAISE EXCEPTION
                'Transaction % already has a terminal record',
                NEW.transaction_id;
        END IF;
    END IF;

    NEW.checksum := calculate_wal_checksum(
        NEW.lsn,
        NEW.transaction_id,
        NEW.record_type,
        NEW.page_key,
        NEW.old_value,
        NEW.new_value
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_wal_record
BEFORE INSERT ON wal_records
FOR EACH ROW
EXECUTE FUNCTION validate_wal_record();

-- ============================================================
-- 9. TRANSACTION STATE VALIDATION
-- ============================================================

CREATE FUNCTION prevent_terminal_transaction_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status <> 'ACTIVE' THEN
        RAISE EXCEPTION
            'Terminal transaction % cannot be modified',
            OLD.transaction_id;
    END IF;

    IF NEW.status = 'ACTIVE' THEN
        NEW.completed_at := NULL;
    ELSE
        NEW.completed_at := clock_timestamp();
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_transaction_state
BEFORE UPDATE ON wal_transactions
FOR EACH ROW
EXECUTE FUNCTION prevent_terminal_transaction_mutation();

-- ============================================================
-- 10. LOG APPEND FUNCTION
-- ============================================================

CREATE FUNCTION append_wal_record(
    p_transaction_id BIGINT,
    p_type log_record_type,
    p_key VARCHAR DEFAULT NULL,
    p_old BIGINT DEFAULT NULL,
    p_new BIGINT DEFAULT NULL
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_lsn BIGINT;
    v_status transaction_status;
BEGIN
    SELECT status
    INTO v_status
    FROM wal_transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown transaction %', p_transaction_id;
    END IF;

    IF p_transaction_id <> 0 AND v_status <> 'ACTIVE' THEN
        RAISE EXCEPTION 'Transaction is not active';
    END IF;

    IF p_type = 'CHECKPOINT' AND p_transaction_id <> 0 THEN
        RAISE EXCEPTION 'Checkpoint must use transaction ID 0';
    END IF;

    IF p_type <> 'CHECKPOINT' AND p_transaction_id = 0 THEN
        RAISE EXCEPTION 'Transaction ID 0 is reserved for checkpoints';
    END IF;

    INSERT INTO wal_records (
        transaction_id,
        record_type,
        page_key,
        old_value,
        new_value,
        checksum
    )
    VALUES (
        p_transaction_id,
        p_type,
        p_key,
        p_old,
        p_new,
        'PENDING'
    )
    RETURNING lsn INTO v_lsn;

    RETURN v_lsn;
END;
$$;

-- ============================================================
-- 11. TRANSACTION SERVICES
-- ============================================================

CREATE FUNCTION begin_transaction(p_name VARCHAR)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    IF p_name IS NULL OR length(trim(p_name)) = 0 THEN
        RAISE EXCEPTION 'Transaction name is required';
    END IF;

    INSERT INTO wal_transactions(transaction_name)
    VALUES (p_name)
    RETURNING transaction_id INTO v_id;

    PERFORM append_wal_record(
        v_id, 'BEGIN', NULL, NULL, NULL
    );

    RETURN v_id;
END;
$$;

CREATE PROCEDURE update_page(
    p_transaction_id BIGINT,
    p_key VARCHAR,
    p_new_value BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_old_value BIGINT;
    v_exists BOOLEAN;
    v_lsn BIGINT;
BEGIN
    IF p_key IS NULL OR length(p_key) = 0
       OR length(p_key) > 128 THEN
        RAISE EXCEPTION 'Invalid page key';
    END IF;

    -- Serialize updates to the same page.
    SELECT page_value
    INTO v_old_value
    FROM database_pages
    WHERE page_key = p_key
    FOR UPDATE;

    v_exists := FOUND;

    -- The log record is inserted before the page is changed.
    v_lsn := append_wal_record(
        p_transaction_id,
        'UPDATE',
        p_key,
        CASE WHEN v_exists THEN v_old_value ELSE NULL END,
        p_new_value
    );

    INSERT INTO database_pages(
        page_key, page_value, page_lsn, is_dirty
    )
    VALUES (
        p_key, p_new_value, v_lsn, TRUE
    )
    ON CONFLICT (page_key)
    DO UPDATE SET
        page_value = EXCLUDED.page_value,
        page_lsn = EXCLUDED.page_lsn,
        is_dirty = TRUE,
        updated_at = clock_timestamp();
END;
$$;

CREATE PROCEDURE commit_transaction(
    p_transaction_id BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- In a real database, the commit record and transaction status
    -- are committed atomically. PostgreSQL WAL durability is managed
    -- by its own transaction and storage engine.
    PERFORM append_wal_record(
        p_transaction_id, 'COMMIT', NULL, NULL, NULL
    );

    UPDATE wal_transactions
    SET status = 'COMMITTED'
    WHERE transaction_id = p_transaction_id;
END;
$$;

CREATE PROCEDURE abort_transaction(
    p_transaction_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM wal_transactions
        WHERE transaction_id = p_transaction_id
          AND status = 'ACTIVE'
    ) THEN
        RAISE EXCEPTION 'Transaction is not active';
    END IF;

    -- UNDO updates in reverse log order.
    FOR r IN
        SELECT *
        FROM wal_records
        WHERE transaction_id = p_transaction_id
          AND record_type = 'UPDATE'
        ORDER BY lsn DESC
    LOOP
        IF r.old_value IS NULL THEN
            DELETE FROM database_pages
            WHERE page_key = r.page_key;
        ELSE
            UPDATE database_pages
            SET page_value = r.old_value,
                page_lsn = r.lsn,
                is_dirty = TRUE
            WHERE page_key = r.page_key;
        END IF;
    END LOOP;

    PERFORM append_wal_record(
        p_transaction_id, 'ABORT', NULL, NULL, NULL
    );

    UPDATE wal_transactions
    SET status = 'ABORTED'
    WHERE transaction_id = p_transaction_id;
END;
$$;

-- ============================================================
-- 12. CHECKPOINT PROCEDURE
-- ============================================================

CREATE PROCEDURE create_checkpoint()
LANGUAGE plpgsql
AS $$
DECLARE
    v_lsn BIGINT;
    v_active BIGINT[];
    v_dirty JSONB;
BEGIN
    SELECT COALESCE(
        array_agg(transaction_id),
        ARRAY[]::BIGINT[]
    )
    INTO v_active
    FROM wal_transactions
    WHERE status = 'ACTIVE';

    SELECT COALESCE(
        jsonb_object_agg(page_key, page_lsn),
        '{}'::JSONB
    )
    INTO v_dirty
    FROM database_pages
    WHERE is_dirty = TRUE;

    v_lsn := append_wal_record(
        0, 'CHECKPOINT', NULL, NULL, NULL
    );

    INSERT INTO wal_checkpoints(
        checkpoint_lsn,
        active_transactions,
        dirty_pages
    )
    VALUES (
        v_lsn,
        v_active,
        v_dirty
    );

    -- The educational checkpoint represents completed page flushing.
    UPDATE database_pages
    SET is_dirty = FALSE;
END;
$$;

-- ============================================================
-- 13. RECOVERY SERVICE
-- ============================================================

CREATE PROCEDURE recover_database(
    OUT p_recovery_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
    v_active BIGINT[];
    v_committed BIGINT[];
    v_aborted BIGINT[];
BEGIN
    INSERT INTO recovery_runs(phase, recovery_message)
    VALUES ('ANALYSIS', 'Recovery started')
    RETURNING recovery_id INTO p_recovery_id;

    -- --------------------------------------------------------
    -- ANALYSIS
    -- --------------------------------------------------------

    SELECT COALESCE(
        array_agg(transaction_id),
        ARRAY[]::BIGINT[]
    )
    INTO v_active
    FROM wal_transactions
    WHERE status = 'ACTIVE';

    SELECT COALESCE(
        array_agg(transaction_id),
        ARRAY[]::BIGINT[]
    )
    INTO v_committed
    FROM wal_transactions
    WHERE status = 'COMMITTED';

    SELECT COALESCE(
        array_agg(transaction_id),
        ARRAY[]::BIGINT[]
    )
    INTO v_aborted
    FROM wal_transactions
    WHERE status = 'ABORTED';

    INSERT INTO recovery_events(
        recovery_id, phase, operation, details
    )
    VALUES (
        p_recovery_id,
        'ANALYSIS',
        'CLASSIFY_TRANSACTIONS',
        jsonb_build_object(
            'active', v_active,
            'committed', v_committed,
            'aborted', v_aborted
        )
    );

    UPDATE recovery_runs SET phase = 'REDO'
    WHERE recovery_id = p_recovery_id;

    -- --------------------------------------------------------
    -- REDO
    -- --------------------------------------------------------

    FOR r IN
        SELECT wr.*
        FROM wal_records wr
        WHERE wr.record_type = 'UPDATE'
          AND (
              wr.transaction_id = ANY(v_committed)
              OR wr.transaction_id = ANY(v_active)
          )
        ORDER BY wr.lsn
    LOOP
        -- REDO is idempotent for this model because records are
        -- replayed in ascending LSN order.
        INSERT INTO database_pages(
            page_key, page_value, page_lsn, is_dirty
        )
        VALUES (
            r.page_key, r.new_value, r.lsn, TRUE
        )
        ON CONFLICT (page_key)
        DO UPDATE SET
            page_value = EXCLUDED.page_value,
            page_lsn = EXCLUDED.page_lsn,
            is_dirty = TRUE
        WHERE database_pages.page_lsn < EXCLUDED.page_lsn;

        INSERT INTO recovery_events(
            recovery_id,
            transaction_id,
            lsn,
            phase,
            operation,
            details
        )
        VALUES (
            p_recovery_id,
            r.transaction_id,
            r.lsn,
            'REDO',
            'REPLAY_UPDATE',
            jsonb_build_object(
                'key', r.page_key,
                'value', r.new_value
            )
        );
    END LOOP;

    UPDATE recovery_runs SET phase = 'UNDO'
    WHERE recovery_id = p_recovery_id;

    -- --------------------------------------------------------
    -- UNDO
    -- --------------------------------------------------------

    FOR r IN
        SELECT wr.*
        FROM wal_records wr
        WHERE wr.record_type = 'UPDATE'
          AND wr.transaction_id = ANY(v_active)
        ORDER BY wr.lsn DESC
    LOOP
        IF r.old_value IS NULL THEN
            DELETE FROM database_pages
            WHERE page_key = r.page_key;
        ELSE
            INSERT INTO database_pages(
                page_key, page_value, page_lsn, is_dirty
            )
            VALUES (
                r.page_key, r.old_value, r.lsn, TRUE
            )
            ON CONFLICT (page_key)
            DO UPDATE SET
                page_value = EXCLUDED.page_value,
                page_lsn = EXCLUDED.page_lsn,
                is_dirty = TRUE
            WHERE database_pages.page_lsn <= EXCLUDED.page_lsn;
        END IF;

        INSERT INTO recovery_events(
            recovery_id,
            transaction_id,
            lsn,
            phase,
            operation,
            details
        )
        VALUES (
            p_recovery_id,
            r.transaction_id,
            r.lsn,
            'UNDO',
            'REVERSE_UPDATE',
            jsonb_build_object(
                'key', r.page_key,
                'restored_value', r.old_value
            )
        );
    END LOOP;

    -- Mark incomplete transactions as aborted.
    FOR r IN
        SELECT transaction_id
        FROM wal_transactions
        WHERE status = 'ACTIVE'
        ORDER BY transaction_id
        FOR UPDATE
    LOOP
        PERFORM append_wal_record(
            r.transaction_id, 'ABORT', NULL, NULL, NULL
        );

        UPDATE wal_transactions
        SET status = 'ABORTED'
        WHERE transaction_id = r.transaction_id;
    END LOOP;

    UPDATE database_pages SET is_dirty = FALSE;

    UPDATE recovery_runs
    SET phase = 'COMPLETED',
        completed_at = clock_timestamp(),
        recovery_message = 'Analysis, REDO and UNDO completed'
    WHERE recovery_id = p_recovery_id;
END;
$$;

-- ============================================================
-- 14. REPORTING VIEWS
-- ============================================================

CREATE VIEW transaction_summary AS
SELECT
    t.transaction_id,
    t.transaction_name,
    t.status,
    COUNT(w.lsn) AS log_record_count,
    MIN(w.lsn) AS first_lsn,
    MAX(w.lsn) AS last_lsn,
    t.started_at,
    t.completed_at
FROM wal_transactions t
LEFT JOIN wal_records w
    ON w.transaction_id = t.transaction_id
GROUP BY
    t.transaction_id,
    t.transaction_name,
    t.status,
    t.started_at,
    t.completed_at;

CREATE VIEW wal_integrity_report AS
SELECT
    lsn,
    transaction_id,
    record_type,
    checksum,
    calculate_wal_checksum(
        lsn,
        transaction_id,
        record_type,
        page_key,
        old_value,
        new_value
    ) = checksum AS checksum_valid
FROM wal_records;

CREATE VIEW page_recovery_state AS
SELECT
    page_key,
    page_value,
    page_lsn,
    is_dirty,
    updated_at
FROM database_pages;

-- ============================================================
-- 15. SAMPLE WORKLOAD
-- ============================================================

BEGIN;

DO $$
DECLARE
    t1 BIGINT;
    t2 BIGINT;
    t3 BIGINT;
    v_recovery_id BIGINT;
BEGIN
    -- Successful committed transaction.
    t1 := begin_transaction('Transfer transaction');

    CALL update_page(t1, 'account_A', 1000);
    CALL update_page(t1, 'account_B', 500);
    CALL commit_transaction(t1);

    -- Incomplete transaction: simulates a crash before commit.
    t2 := begin_transaction('Interrupted transfer');

    CALL update_page(t2, 'account_A', 800);
    CALL update_page(t2, 'account_B', 700);

    -- Another committed transaction.
    t3 := begin_transaction('Inventory update');

    CALL update_page(t3, 'inventory_101', 250);
    CALL commit_transaction(t3);

    CALL create_checkpoint();

    RAISE NOTICE 'Before recovery: account_A = %, account_B = %',
        (SELECT page_value FROM database_pages
         WHERE page_key = 'account_A'),
        (SELECT page_value FROM database_pages
         WHERE page_key = 'account_B');

    -- Demonstrate recovery inside the same database transaction.
    CALL recover_database(v_recovery_id);

    RAISE NOTICE 'Recovery ID: %', v_recovery_id;

    RAISE NOTICE 'After recovery: account_A = %, account_B = %',
        (SELECT page_value FROM database_pages
         WHERE page_key = 'account_A'),
        (SELECT page_value FROM database_pages
         WHERE page_key = 'account_B');

    IF (SELECT page_value FROM database_pages
        WHERE page_key = 'account_A') <> 1000 THEN
        RAISE EXCEPTION 'Account A recovery failed';
    END IF;

    IF (SELECT page_value FROM database_pages
        WHERE page_key = 'account_B') <> 500 THEN
        RAISE EXCEPTION 'Account B recovery failed';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM wal_transactions
        WHERE transaction_id = t2
          AND status = 'ABORTED'
    ) THEN
        RAISE EXCEPTION 'Incomplete transaction was not aborted';
    END IF;
END;
$$;

COMMIT;

-- ============================================================
-- 16. RETRIEVAL AND VALIDATION QUERIES
-- ============================================================

-- Complete WAL sequence.
SELECT
    lsn,
    transaction_id,
    record_type,
    page_key,
    old_value,
    new_value,
    checksum
FROM wal_records
ORDER BY lsn;

-- Transaction lifecycle and log volume.
SELECT *
FROM transaction_summary
ORDER BY transaction_id;

-- Validate all stored checksums.
SELECT *
FROM wal_integrity_report
WHERE checksum_valid = FALSE;

-- Identify any unresolved transactions.
SELECT *
FROM wal_transactions
WHERE status = 'ACTIVE';

-- ============================================================
-- 17. AGGREGATION AND REPORTING
-- ============================================================

-- Record counts by operation type.
SELECT
    record_type,
    COUNT(*) AS total_records,
    MIN(lsn) AS first_lsn,
    MAX(lsn) AS last_lsn
FROM wal_records
GROUP BY record_type
ORDER BY record_type;

-- Transaction completion statistics.
SELECT
    status,
    COUNT(*) AS transaction_count,
    AVG(
        EXTRACT(
            EPOCH FROM completed_at - started_at
        )
    ) AS average_duration_seconds
FROM wal_transactions
GROUP BY status;

-- Recovery phase statistics.
SELECT
    recovery_id,
    phase,
    COUNT(*) AS events
FROM recovery_events
GROUP BY recovery_id, phase
ORDER BY recovery_id, phase;

-- ============================================================
-- 18. ELIGIBILITY AND OPERATIONAL DIAGNOSTICS
-- ============================================================

-- A transaction is eligible for successful completion only
-- when it is active and has not already emitted a terminal record.
SELECT
    t.transaction_id,
    t.transaction_name,
    t.status,
    NOT EXISTS (
        SELECT 1
        FROM wal_records w
        WHERE w.transaction_id = t.transaction_id
          AND w.record_type IN ('COMMIT', 'ABORT')
    ) AS eligible_for_completion
FROM wal_transactions t;

-- Identify pages whose latest update is associated with a
-- transaction that has not committed.
SELECT
    p.page_key,
    p.page_value,
    p.page_lsn,
    w.transaction_id,
    t.status
FROM database_pages p
JOIN wal_records w
    ON w.lsn = p.page_lsn
JOIN wal_transactions t
    ON t.transaction_id = w.transaction_id
WHERE w.record_type = 'UPDATE'
  AND t.status <> 'COMMITTED';

-- Display recovery execution history.
SELECT
    rr.recovery_id,
    rr.phase,
    rr.started_at,
    rr.completed_at,
    rr.recovery_message
FROM recovery_runs rr
ORDER BY rr.recovery_id;

-- ============================================================
-- 19. DESIGN AND OPERATIONAL NOTES
-- ============================================================

1. WAL ordering:
   UPDATE records are inserted before database_pages is modified.

2. Commit:
   A COMMIT record and transaction state transition are persisted
   together by the surrounding PostgreSQL transaction.

3. Durability:
   PostgreSQL's own WAL, commit processing, storage synchronization
   and recovery mechanisms provide actual database durability.
   This educational schema models the concepts, not the internal
   PostgreSQL WAL implementation.

4. Checkpoints:
   The sample checkpoint captures active transactions and dirty
   page metadata. It is not a production fuzzy checkpoint.

5. REDO:
   Replays committed and incomplete updates in ascending LSN order.

6. UNDO:
   Reverses incomplete transaction updates in descending LSN order.

7. Integrity:
   The checksum is an educational MD5 integrity demonstration.
   Production systems should use appropriate binary record framing,
   stronger integrity checks, durable storage and replication controls.

8. Recovery limitations:
   This model uses transaction metadata and logical page values.
   It does not implement ARIES compensation log records, pageLSN
   persistence, log truncation, partial-page writes or concurrent
   recovery workers.

9. Real crash simulation:
   A production crash test requires process termination or
   infrastructure-level failure injection. The demonstration
   performs logical recovery within a controlled SQL transaction.
