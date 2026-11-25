-- ============================================================
-- PESSIMISTIC CONCURRENCY: LOCK-BASED APPROACHES
-- PostgreSQL 15+
--
-- Domain: Enterprise banking and concurrent transfers.
--
-- Demonstrates:
-- 1. Row-level pessimistic locking.
-- 2. SELECT FOR UPDATE.
-- 3. SELECT FOR NO KEY UPDATE.
-- 4. SELECT FOR SHARE.
-- 5. SELECT FOR UPDATE NOWAIT.
-- 6. SELECT FOR UPDATE SKIP LOCKED.
-- 7. Lock timeout and statement timeout.
-- 8. Consistent lock ordering.
-- 9. Deadlock prevention and handling.
-- 10. Atomic transactions and rollback.
-- 11. Transaction isolation.
-- 12. Audit logging and operational monitoring.
--
-- Execute using psql.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS concurrency_lab;

SET search_path TO concurrency_lab, public;

CREATE TABLE IF NOT EXISTS accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_number VARCHAR(30) NOT NULL UNIQUE,
    owner_name VARCHAR(120) NOT NULL,
    balance NUMERIC(18, 2) NOT NULL DEFAULT 0,
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    account_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT positive_balance
        CHECK (balance >= 0),

    CONSTRAINT valid_account_status
        CHECK (
            account_status IN (
                'ACTIVE',
                'FROZEN',
                'CLOSED'
            )
        ),

    CONSTRAINT valid_version
        CHECK (version >= 0)
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reference_number UUID NOT NULL UNIQUE,
    source_account_id BIGINT NOT NULL REFERENCES accounts(account_id),
    destination_account_id BIGINT NOT NULL REFERENCES accounts(account_id),
    amount NUMERIC(18, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,

    CONSTRAINT positive_transfer_amount
        CHECK (amount > 0),

    CONSTRAINT different_accounts
        CHECK (source_account_id <> destination_account_id),

    CONSTRAINT valid_transaction_status
        CHECK (
            status IN (
                'PENDING',
                'COMPLETED',
                'FAILED'
            )
        )
);

CREATE TABLE IF NOT EXISTS account_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(account_id),
    transaction_id BIGINT,
    old_balance NUMERIC(18, 2) NOT NULL,
    new_balance NUMERIC(18, 2) NOT NULL,
    operation VARCHAR(30) NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    database_user TEXT NOT NULL DEFAULT CURRENT_USER
);

CREATE TABLE IF NOT EXISTS transfer_jobs (
    job_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'READY',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ,

    CONSTRAINT valid_job_status
        CHECK (
            status IN (
                'READY',
                'PROCESSING',
                'COMPLETED',
                'FAILED'
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_transactions_source
    ON transactions(source_account_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_destination
    ON transactions(destination_account_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_status
    ON transactions(status, created_at);

CREATE INDEX IF NOT EXISTS idx_account_audit_account
    ON account_audit(account_id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_ready_jobs
    ON transfer_jobs(job_id)
    WHERE status = 'READY';

COMMIT;

-- ------------------------------------------------------------
-- SAMPLE DATA
-- ------------------------------------------------------------

INSERT INTO accounts (
    account_number,
    owner_name,
    balance,
    currency
)
VALUES
    ('ACC-1001', 'Ananya Sharma', 100000, 'INR'),
    ('ACC-1002', 'Rahul Verma', 80000, 'INR'),
    ('ACC-1003', 'Priya Singh', 60000, 'INR')
ON CONFLICT (account_number) DO NOTHING;

INSERT INTO transfer_jobs(payload)
VALUES
    ('{"type":"TRANSFER","reference":"JOB-001"}'),
    ('{"type":"TRANSFER","reference":"JOB-002"}'),
    ('{"type":"TRANSFER","reference":"JOB-003"}');

-- ------------------------------------------------------------
-- AUDIT TRIGGER
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION audit_account_balance()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.balance IS DISTINCT FROM OLD.balance THEN
        INSERT INTO account_audit (
            account_id,
            old_balance,
            new_balance,
            operation
        )
        VALUES (
            NEW.account_id,
            OLD.balance,
            NEW.balance,
            'BALANCE_UPDATE'
        );

        NEW.version := OLD.version + 1;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_account_balance_audit
ON accounts;

CREATE TRIGGER trg_account_balance_audit
BEFORE UPDATE OF balance ON accounts
FOR EACH ROW
EXECUTE FUNCTION audit_account_balance();

-- ------------------------------------------------------------
-- PESSIMISTIC TRANSFER FUNCTION
--
-- SELECT FOR UPDATE obtains exclusive row-level locks.
--
-- Accounts are locked in ascending primary-key order.
-- Consistent ordering reduces circular-wait deadlocks.
--
-- Both updates and transaction records are atomic.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION transfer_money(
    p_source_account BIGINT,
    p_destination_account BIGINT,
    p_amount NUMERIC(18, 2)
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_source_balance NUMERIC(18, 2);
    v_destination_balance NUMERIC(18, 2);
    v_source_currency CHAR(3);
    v_destination_currency CHAR(3);
    v_source_status VARCHAR(20);
    v_destination_status VARCHAR(20);
    v_transaction_id BIGINT;
    v_reference UUID := gen_random_uuid();
    v_account BIGINT;
BEGIN
    IF p_source_account = p_destination_account THEN
        RAISE EXCEPTION 'Source and destination must differ';
    END IF;

    IF p_amount IS NULL OR p_amount <= 0 THEN
        RAISE EXCEPTION 'Transfer amount must be positive';
    END IF;

    -- Lock rows in a globally consistent order.
    FOR v_account IN
        SELECT account_id
        FROM accounts
        WHERE account_id IN (
            p_source_account,
            p_destination_account
        )
        ORDER BY account_id
        FOR UPDATE
    LOOP
        NULL;
    END LOOP;

    SELECT
        balance,
        currency,
        account_status
    INTO
        v_source_balance,
        v_source_currency,
        v_source_status
    FROM accounts
    WHERE account_id = p_source_account;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Source account not found';
    END IF;

    SELECT
        balance,
        currency,
        account_status
    INTO
        v_destination_balance,
        v_destination_currency,
        v_destination_status
    FROM accounts
    WHERE account_id = p_destination_account;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Destination account not found';
    END IF;

    IF v_source_status <> 'ACTIVE'
       OR v_destination_status <> 'ACTIVE' THEN
        RAISE EXCEPTION 'Both accounts must be active';
    END IF;

    IF v_source_currency <> v_destination_currency THEN
        RAISE EXCEPTION 'Cross-currency transfer not supported';
    END IF;

    IF v_source_balance < p_amount THEN
        RAISE EXCEPTION 'Insufficient funds';
    END IF;

    IF v_destination_balance >
       9999999999999999.99 - p_amount THEN
        RAISE EXCEPTION 'Destination balance limit exceeded';
    END IF;

    INSERT INTO transactions (
        reference_number,
        source_account_id,
        destination_account_id,
        amount,
        status
    )
    VALUES (
        v_reference,
        p_source_account,
        p_destination_account,
        p_amount,
        'PENDING'
    )
    RETURNING transaction_id INTO v_transaction_id;

    UPDATE accounts
    SET balance = balance - p_amount
    WHERE account_id = p_source_account;

    UPDATE accounts
    SET balance = balance + p_amount
    WHERE account_id = p_destination_account;

    UPDATE transactions
    SET
        status = 'COMPLETED',
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = v_transaction_id;

    RETURN v_transaction_id;
END;
$$;

-- ------------------------------------------------------------
-- PROCEDURE FOR TRANSACTION PROCESSING
--
-- The procedure runs within the caller's transaction.
-- It does not commit independently.
-- ------------------------------------------------------------

CREATE OR REPLACE PROCEDURE execute_transfer(
    p_source_account BIGINT,
    p_destination_account BIGINT,
    p_amount NUMERIC(18, 2)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
BEGIN
    v_id := transfer_money(
        p_source_account,
        p_destination_account,
        p_amount
    );

    RAISE NOTICE 'Transfer completed. Transaction ID: %', v_id;
END;
$$;

-- ------------------------------------------------------------
-- DEMONSTRATION 1: ATOMIC TRANSFER
-- ------------------------------------------------------------

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '15s';

CALL execute_transfer(1, 2, 5000.00);

COMMIT;

-- ------------------------------------------------------------
-- DEMONSTRATION 2: ROLLBACK
--
-- The transfer is intentionally rolled back.
-- No balance changes remain after ROLLBACK.
-- ------------------------------------------------------------

BEGIN;

SELECT transfer_money(2, 3, 1000.00);

ROLLBACK;

-- ------------------------------------------------------------
-- DEMONSTRATION 3: SHARED LOCK
--
-- Multiple transactions can hold compatible shared locks.
-- Shared locks conflict with exclusive updates.
-- ------------------------------------------------------------

BEGIN;

SELECT account_id, account_number, balance
FROM accounts
WHERE account_id = 1
FOR SHARE;

COMMIT;

-- ------------------------------------------------------------
-- DEMONSTRATION 4: NO KEY UPDATE
--
-- Acquires a row lock that conflicts with updates and
-- competing NO KEY UPDATE locks, but permits KEY SHARE.
-- ------------------------------------------------------------

BEGIN;

SELECT account_id, balance
FROM accounts
WHERE account_id = 1
FOR NO KEY UPDATE;

COMMIT;

-- ------------------------------------------------------------
-- DEMONSTRATION 5: NOWAIT
--
-- Immediately raises an error if the requested row is locked.
-- Execute in a separate transaction to test contention.
-- ------------------------------------------------------------

BEGIN;

SELECT account_id, balance
FROM accounts
WHERE account_id = 1
FOR UPDATE NOWAIT;

COMMIT;

-- ------------------------------------------------------------
-- DEMONSTRATION 6: SKIP LOCKED
--
-- Suitable for multiple queue workers.
-- Locked jobs are skipped instead of blocking.
-- ------------------------------------------------------------

BEGIN;

WITH selected_jobs AS (
    SELECT job_id
    FROM transfer_jobs
    WHERE status = 'READY'
    ORDER BY job_id
    LIMIT 2
    FOR UPDATE SKIP LOCKED
)
UPDATE transfer_jobs AS jobs
SET
    status = 'PROCESSING'
FROM selected_jobs
WHERE jobs.job_id = selected_jobs.job_id
RETURNING jobs.job_id, jobs.status, jobs.payload;

COMMIT;

-- ------------------------------------------------------------
-- DEMONSTRATION 7: LOCK-BASED ELIGIBILITY
--
-- A worker should process only a job it successfully locks.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION claim_transfer_job()
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_job_id BIGINT;
BEGIN
    SELECT job_id
    INTO v_job_id
    FROM transfer_jobs
    WHERE status = 'READY'
    ORDER BY job_id
    LIMIT 1
    FOR UPDATE SKIP LOCKED;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    UPDATE transfer_jobs
    SET status = 'PROCESSING'
    WHERE job_id = v_job_id;

    RETURN v_job_id;
END;
$$;

BEGIN;

SELECT claim_transfer_job();

COMMIT;

-- ------------------------------------------------------------
-- DEMONSTRATION 8: REPORTING
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW account_balance_report AS
SELECT
    a.account_id,
    a.account_number,
    a.owner_name,
    a.balance,
    a.currency,
    a.account_status,
    a.version,
    COUNT(t.transaction_id) AS transfer_count
FROM accounts a
LEFT JOIN transactions t
    ON t.source_account_id = a.account_id
    OR t.destination_account_id = a.account_id
GROUP BY
    a.account_id,
    a.account_number,
    a.owner_name,
    a.balance,
    a.currency,
    a.account_status,
    a.version;

SELECT *
FROM account_balance_report
ORDER BY account_id;

-- ------------------------------------------------------------
-- DEMONSTRATION 9: TRANSACTION AGGREGATION
-- ------------------------------------------------------------

WITH transfer_summary AS (
    SELECT
        status,
        COUNT(*) AS total_transactions,
        SUM(amount) AS total_amount,
        AVG(amount) AS average_amount
    FROM transactions
    GROUP BY status
)
SELECT *
FROM transfer_summary
ORDER BY status;

-- ------------------------------------------------------------
-- DEMONSTRATION 10: AUDIT RETRIEVAL
-- ------------------------------------------------------------

SELECT
    account_id,
    old_balance,
    new_balance,
    operation,
    changed_at,
    database_user
FROM account_audit
ORDER BY audit_id DESC;

-- ------------------------------------------------------------
-- DEMONSTRATION 11: CURRENT LOCK OBSERVABILITY
--
-- Requires appropriate PostgreSQL monitoring privileges
-- for complete visibility into other sessions.
-- ------------------------------------------------------------

SELECT
    a.pid,
    a.usename,
    a.state,
    a.wait_event_type,
    a.wait_event,
    l.locktype,
    l.mode,
    l.granted,
    a.query
FROM pg_stat_activity a
JOIN pg_locks l
    ON l.pid = a.pid
WHERE a.datname = current_database()
ORDER BY a.pid, l.granted;

-- ------------------------------------------------------------
-- DEMONSTRATION 12: BLOCKING RELATIONSHIPS
-- ------------------------------------------------------------

SELECT
    blocked.pid AS blocked_pid,
    blocked.query AS blocked_query,
    blocker.pid AS blocker_pid,
    blocker.query AS blocker_query
FROM pg_stat_activity blocked
JOIN LATERAL unnest(
    pg_blocking_pids(blocked.pid)
) AS blocker_pid(pid)
    ON TRUE
JOIN pg_stat_activity blocker
    ON blocker.pid = blocker_pid.pid;

-- ------------------------------------------------------------
-- DEMONSTRATION 13: CONSTRAINT VALIDATION
--
-- The following query identifies invalid account states.
-- ------------------------------------------------------------

SELECT
    account_id,
    account_number,
    balance,
    account_status
FROM accounts
WHERE balance < 0
   OR account_status NOT IN (
       'ACTIVE',
       'FROZEN',
       'CLOSED'
   );

-- ------------------------------------------------------------
-- DEMONSTRATION 14: ISOLATION LEVEL
-- ------------------------------------------------------------

SHOW transaction_isolation;

-- ------------------------------------------------------------
-- OPERATIONAL NOTES
--
-- Deadlock handling:
-- PostgreSQL detects deadlocks and aborts one participant.
-- SQLSTATE 40P01 indicates deadlock_detected.
--
-- Lock timeout:
-- SQLSTATE 55P03 indicates lock_not_available.
--
-- Serialization failure:
-- SQLSTATE 40001 indicates serialization_failure.
--
-- Retry the entire transaction for retryable failures.
-- Never retry only the failed statement when earlier
-- transaction operations depend on it.
--
-- Locks are released at transaction end.
-- Long-running transactions increase contention.
--
-- Row locks do not automatically prevent every possible
-- phantom or predicate-level anomaly.
-- Use SERIALIZABLE when the business invariant requires it.
--
-- Run EXPLAIN (ANALYZE, BUFFERS) on production queries.
-- Ensure indexed predicates avoid unnecessarily large scans.
-- ------------------------------------------------------------
