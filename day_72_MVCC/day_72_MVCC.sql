/*
 * MVCC: Multi-Version Concurrency Control
 *
 * PostgreSQL 15+
 *
 * Demonstrates:
 * - PostgreSQL MVCC transaction snapshots
 * - Transaction isolation levels
 * - Row version creation and visibility
 * - Concurrent updates
 * - Row-level locking
 * - Serialization failures
 * - Optimistic version checking
 * - Transaction auditing
 * - Logical version history
 * - Version cleanup
 * - Vacuum monitoring
 * - Concurrency reporting
 *
 * Important:
 * PostgreSQL internally manages tuple versions using transaction
 * identifiers, transaction status, visibility maps and snapshots.
 *
 * The application-level version_history table below is an audit
 * history, not a replacement for PostgreSQL's internal MVCC engine.
 */

DROP SCHEMA IF EXISTS mvcc_lab CASCADE;

CREATE SCHEMA mvcc_lab;

SET search_path TO mvcc_lab, public;

-- ============================================================
-- 1. DOMAIN TYPES
-- ============================================================

CREATE TYPE isolation_mode AS ENUM (
    'READ COMMITTED',
    'REPEATABLE READ',
    'SERIALIZABLE'
);

CREATE TYPE transaction_status AS ENUM (
    'ACTIVE',
    'COMMITTED',
    'ABORTED'
);

CREATE TYPE operation_type AS ENUM (
    'INSERT',
    'UPDATE',
    'DELETE'
);

-- ============================================================
-- 2. TRANSACTION REGISTRY
-- ============================================================

CREATE TABLE transaction_registry (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    application_name TEXT NOT NULL,

    isolation isolation_mode NOT NULL,

    status transaction_status NOT NULL DEFAULT 'ACTIVE',

    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    finished_at TIMESTAMPTZ,

    CHECK (
        (status = 'ACTIVE' AND finished_at IS NULL)
        OR
        (status <> 'ACTIVE' AND finished_at IS NOT NULL)
    )
);

CREATE INDEX idx_transaction_status_started
ON transaction_registry(status, started_at);

-- ============================================================
-- 3. ACCOUNT TABLE
-- ============================================================

CREATE TABLE accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    account_number VARCHAR(30) NOT NULL UNIQUE,

    owner_name VARCHAR(120) NOT NULL,

    balance NUMERIC(18, 2) NOT NULL,

    row_version BIGINT NOT NULL DEFAULT 1,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CHECK (balance >= 0),

    CHECK (row_version > 0)
);

CREATE INDEX idx_accounts_updated
ON accounts(updated_at);

-- ============================================================
-- 4. APPLICATION-LEVEL VERSION HISTORY
-- ============================================================

CREATE TABLE version_history (
    version_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    account_id BIGINT NOT NULL,

    transaction_id BIGINT,

    operation operation_type NOT NULL,

    old_balance NUMERIC(18, 2),

    new_balance NUMERIC(18, 2),

    old_version BIGINT,

    new_version BIGINT,

    changed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    database_transaction_id TEXT NOT NULL DEFAULT txid_current()::TEXT,

    CONSTRAINT fk_history_account
        FOREIGN KEY (account_id)
        REFERENCES accounts(account_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_history_transaction
        FOREIGN KEY (transaction_id)
        REFERENCES transaction_registry(transaction_id),

    CHECK (
        (operation = 'INSERT' AND old_balance IS NULL)
        OR
        (operation = 'UPDATE' AND old_balance IS NOT NULL
                               AND new_balance IS NOT NULL)
        OR
        (operation = 'DELETE' AND new_balance IS NULL)
    )
);

CREATE INDEX idx_history_account_time
ON version_history(account_id, changed_at DESC);

CREATE INDEX idx_history_transaction
ON version_history(transaction_id);

-- ============================================================
-- 5. TRANSACTION EVENT AUDIT
-- ============================================================

CREATE TABLE transaction_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id BIGINT,

    event_name TEXT NOT NULL,

    event_details JSONB NOT NULL DEFAULT '{}'::JSONB,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_events_transaction_time
ON transaction_events(transaction_id, occurred_at DESC);

-- ============================================================
-- 6. ACCOUNT VERSION TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION maintain_account_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_id BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.row_version := 1;
        NEW.updated_at := clock_timestamp();

        INSERT INTO version_history (
            account_id,
            operation,
            old_balance,
            new_balance,
            new_version
        )
        VALUES (
            NEW.account_id,
            'INSERT',
            NULL,
            NEW.balance,
            NEW.row_version
        );

        RETURN NEW;

    ELSIF TG_OP = 'UPDATE' THEN
        IF NEW.account_id <> OLD.account_id THEN
            RAISE EXCEPTION 'Account identity cannot be changed';
        END IF;

        IF NEW.balance IS DISTINCT FROM OLD.balance THEN
            NEW.row_version := OLD.row_version + 1;
        ELSE
            NEW.row_version := OLD.row_version;
        END IF;

        NEW.updated_at := clock_timestamp();

        IF NEW.balance IS DISTINCT FROM OLD.balance THEN
            INSERT INTO version_history (
                account_id,
                operation,
                old_balance,
                new_balance,
                old_version,
                new_version
            )
            VALUES (
                OLD.account_id,
                'UPDATE',
                OLD.balance,
                NEW.balance,
                OLD.row_version,
                NEW.row_version
            );
        END IF;

        RETURN NEW;

    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO version_history (
            account_id,
            operation,
            old_balance,
            new_balance,
            old_version
        )
        VALUES (
            OLD.account_id,
            'DELETE',
            OLD.balance,
            NULL,
            OLD.row_version
        );

        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_account_version
BEFORE INSERT OR UPDATE OR DELETE
ON accounts
FOR EACH ROW
EXECUTE FUNCTION maintain_account_version();

-- ============================================================
-- 7. INITIAL SAMPLE DATA
-- ============================================================

INSERT INTO accounts (
    account_number,
    owner_name,
    balance
)
VALUES
    ('ACC-1001', 'Aarav Sharma', 10000.00),
    ('ACC-1002', 'Priya Verma', 7500.00),
    ('ACC-1003', 'Rahul Singh', 5000.00),
    ('ACC-1004', 'Neha Gupta', 2500.00);

-- ============================================================
-- 8. OPTIMISTIC CONCURRENCY CONTROL FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION update_balance_optimistic(
    p_account_id BIGINT,
    p_expected_version BIGINT,
    p_new_balance NUMERIC
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows INTEGER;
BEGIN
    IF p_new_balance < 0 THEN
        RAISE EXCEPTION 'Balance cannot be negative';
    END IF;

    UPDATE accounts
    SET balance = p_new_balance
    WHERE account_id = p_account_id
      AND row_version = p_expected_version;

    GET DIAGNOSTICS v_rows = ROW_COUNT;

    IF v_rows = 0 THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$;

-- ============================================================
-- 9. ATOMIC ACCOUNT TRANSFER
-- ============================================================

CREATE OR REPLACE PROCEDURE transfer_balance(
    p_source BIGINT,
    p_destination BIGINT,
    p_amount NUMERIC
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_source_balance NUMERIC(18, 2);
    v_destination_balance NUMERIC(18, 2);
    v_first BIGINT;
    v_second BIGINT;
BEGIN
    IF p_amount <= 0 THEN
        RAISE EXCEPTION 'Transfer amount must be positive';
    END IF;

    IF p_source = p_destination THEN
        RAISE EXCEPTION 'Source and destination must differ';
    END IF;

    -- Acquire locks in a deterministic order to reduce deadlocks.
    v_first := LEAST(p_source, p_destination);
    v_second := GREATEST(p_source, p_destination);

    PERFORM account_id
    FROM accounts
    WHERE account_id IN (v_first, v_second)
    ORDER BY account_id
    FOR UPDATE;

    IF (
        SELECT COUNT(*)
        FROM accounts
        WHERE account_id IN (p_source, p_destination)
    ) <> 2 THEN
        RAISE EXCEPTION 'One or both accounts do not exist';
    END IF;

    SELECT balance
    INTO v_source_balance
    FROM accounts
    WHERE account_id = p_source;

    SELECT balance
    INTO v_destination_balance
    FROM accounts
    WHERE account_id = p_destination;

    IF v_source_balance < p_amount THEN
        RAISE EXCEPTION 'Insufficient funds';
    END IF;

    UPDATE accounts
    SET balance = balance - p_amount
    WHERE account_id = p_source;

    UPDATE accounts
    SET balance = balance + p_amount
    WHERE account_id = p_destination;

    INSERT INTO transaction_events (
        event_name,
        event_details
    )
    VALUES (
        'ACCOUNT_TRANSFER',
        jsonb_build_object(
            'source', p_source,
            'destination', p_destination,
            'amount', p_amount
        )
    );
END;
$$;

-- ============================================================
-- 10. SNAPSHOT AND VERSION REPORTING
-- ============================================================

CREATE OR REPLACE VIEW account_version_report AS
SELECT
    a.account_id,
    a.account_number,
    a.owner_name,
    a.balance AS current_balance,
    a.row_version AS current_version,
    a.updated_at,
    COUNT(h.version_id) AS recorded_changes
FROM accounts a
LEFT JOIN version_history h
    ON h.account_id = a.account_id
GROUP BY
    a.account_id,
    a.account_number,
    a.owner_name,
    a.balance,
    a.row_version,
    a.updated_at;

CREATE OR REPLACE VIEW active_transaction_report AS
SELECT
    pid,
    usename,
    application_name,
    state,
    xact_start,
    query_start,
    wait_event_type,
    wait_event,
    backend_xid,
    backend_xmin,
    query
FROM pg_stat_activity
WHERE datname = current_database()
  AND xact_start IS NOT NULL;

-- ============================================================
-- 11. VERSION HISTORY RETRIEVAL
-- ============================================================

SELECT
    account_id,
    operation,
    old_balance,
    new_balance,
    old_version,
    new_version,
    changed_at
FROM version_history
ORDER BY account_id, version_id;

-- ============================================================
-- 12. OPTIMISTIC CONCURRENCY EXAMPLE
-- ============================================================

DO $$
DECLARE
    v_account_id BIGINT;
    v_version BIGINT;
    v_success BOOLEAN;
BEGIN
    SELECT account_id, row_version
    INTO v_account_id, v_version
    FROM accounts
    WHERE account_number = 'ACC-1001';

    v_success := update_balance_optimistic(
        v_account_id,
        v_version,
        10500.00
    );

    RAISE NOTICE 'Optimistic update successful: %', v_success;

    -- A stale version must not overwrite a newer version.
    v_success := update_balance_optimistic(
        v_account_id,
        v_version,
        11000.00
    );

    RAISE NOTICE 'Stale update accepted: %', v_success;
END;
$$;

-- ============================================================
-- 13. ATOMIC TRANSFER EXAMPLE
-- ============================================================

BEGIN;

CALL transfer_balance(
    (SELECT account_id FROM accounts WHERE account_number = 'ACC-1001'),
    (SELECT account_id FROM accounts WHERE account_number = 'ACC-1002'),
    250.00
);

COMMIT;

-- ============================================================
-- 14. VALIDATION AND REPORTING
-- ============================================================

-- Current balances.
SELECT
    account_number,
    owner_name,
    balance,
    row_version
FROM accounts
ORDER BY account_number;

-- Version counts by account.
SELECT
    account_id,
    COUNT(*) AS total_versions,
    COUNT(*) FILTER (
        WHERE operation = 'UPDATE'
    ) AS update_count,
    COUNT(*) FILTER (
        WHERE operation = 'DELETE'
    ) AS delete_count
FROM version_history
GROUP BY account_id
ORDER BY account_id;

-- Balance change analysis using a window function.
WITH history_sequence AS (
    SELECT
        account_id,
        version_id,
        old_balance,
        new_balance,
        changed_at,
        LAG(new_balance) OVER (
            PARTITION BY account_id
            ORDER BY version_id
        ) AS previous_balance
    FROM version_history
)
SELECT
    account_id,
    version_id,
    old_balance,
    new_balance,
    previous_balance,
    changed_at
FROM history_sequence
ORDER BY account_id, version_id;

-- Detect inconsistent version sequences.
SELECT
    account_id,
    version_id,
    old_version,
    new_version
FROM version_history
WHERE operation = 'UPDATE'
  AND new_version <> old_version + 1;

-- ============================================================
-- 15. TRANSACTION ISOLATION DEMONSTRATIONS
-- ============================================================

-- READ COMMITTED:
-- Each SQL statement receives a fresh snapshot.
BEGIN ISOLATION LEVEL READ COMMITTED;

SELECT
    account_number,
    balance,
    row_version
FROM accounts
WHERE account_number = 'ACC-1001';

SELECT
    account_number,
    balance,
    row_version
FROM accounts
WHERE account_number = 'ACC-1001';

COMMIT;

-- REPEATABLE READ:
-- The transaction retains its snapshot.
BEGIN ISOLATION LEVEL REPEATABLE READ;

SELECT
    account_number,
    balance
FROM accounts
WHERE account_number = 'ACC-1001';

COMMIT;

-- SERIALIZABLE:
-- PostgreSQL detects serialization anomalies and can abort
-- a transaction with SQLSTATE 40001.
BEGIN ISOLATION LEVEL SERIALIZABLE;

SELECT
    account_number,
    balance
FROM accounts
WHERE balance > 0;

COMMIT;

-- ============================================================
-- 16. ROW LOCKING DEMONSTRATION
-- ============================================================

BEGIN;

SELECT
    account_id,
    account_number,
    balance
FROM accounts
WHERE account_number = 'ACC-1001'
FOR UPDATE;

COMMIT;

-- FOR UPDATE blocks conflicting row modifications.
-- Ordinary MVCC readers can generally continue reading
-- an older visible row version.

-- ============================================================
-- 17. TRANSACTION SNAPSHOT INSPECTION
-- ============================================================

SELECT
    txid_current() AS current_transaction_id,
    txid_current_snapshot() AS current_snapshot,
    pg_snapshot_xmin(txid_current_snapshot()) AS snapshot_xmin,
    pg_snapshot_xmax(txid_current_snapshot()) AS snapshot_xmax;

-- ============================================================
-- 18. VACUUM AND DEAD-TUPLE MONITORING
-- ============================================================

SELECT
    schemaname,
    relname,
    n_live_tup,
    n_dead_tup,
    last_vacuum,
    last_autovacuum,
    vacuum_count,
    autovacuum_count
FROM pg_stat_user_tables
WHERE schemaname = 'mvcc_lab';

-- VACUUM reclaims space occupied by obsolete row versions
-- when they are no longer needed by active snapshots.
-- VACUUM FULL requires stronger locking and rewrites the table.
VACUUM (ANALYZE) mvcc_lab.accounts;

VACUUM (ANALYZE) mvcc_lab.version_history;

-- ============================================================
-- 19. TRANSACTION FAILURE EXAMPLE
-- ============================================================

DO $$
BEGIN
    BEGIN
        UPDATE accounts
        SET balance = -100
        WHERE account_number = 'ACC-1001';

    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'Expected failure: balance constraint';
    END;
END;
$$;

-- ============================================================
-- 20. FINAL REPORT
-- ============================================================

SELECT
    account_number,
    owner_name,
    balance,
    row_version,
    updated_at
FROM accounts
ORDER BY account_number;

SELECT
    operation,
    COUNT(*) AS event_count,
    MIN(changed_at) AS first_event,
    MAX(changed_at) AS latest_event
FROM version_history
GROUP BY operation
ORDER BY operation;

SELECT
    COUNT(*) AS recorded_versions,
    COUNT(DISTINCT account_id) AS affected_accounts
FROM version_history;

RESET search_path;
