-- ============================================================
-- LOST UPDATES: CONCURRENT WRITE MANAGEMENT
-- PostgreSQL 15+
--
-- Demonstrates:
-- 1. Lost updates under unsafe read-modify-write behavior.
-- 2. Optimistic concurrency using version columns.
-- 3. Pessimistic concurrency using SELECT FOR UPDATE.
-- 4. Conditional updates.
-- 5. Idempotent transaction requests.
-- 6. Audit history and transaction reporting.
-- ============================================================

DROP SCHEMA IF EXISTS concurrency_lab CASCADE;

CREATE SCHEMA concurrency_lab;

SET search_path TO concurrency_lab, public;

-- ============================================================
-- 1. DOMAIN TYPES
-- ============================================================

CREATE TYPE transaction_operation AS ENUM (
    'DEPOSIT',
    'WITHDRAW'
);

CREATE TYPE transaction_status AS ENUM (
    'COMMITTED',
    'CONFLICT',
    'REJECTED'
);

CREATE TYPE concurrency_strategy AS ENUM (
    'UNSAFE',
    'OPTIMISTIC',
    'PESSIMISTIC'
);

-- ============================================================
-- 2. REPOSITORY AND ACCOUNT TABLES
-- ============================================================

CREATE TABLE repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name VARCHAR(150) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Account data represents a resource subject to concurrent writes.
CREATE TABLE accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT REFERENCES repositories(repository_id),
    owner_name VARCHAR(150) NOT NULL,
    balance NUMERIC(18, 2) NOT NULL DEFAULT 0,
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT positive_balance CHECK (balance >= 0),
    CONSTRAINT nonnegative_version CHECK (version >= 0)
);

CREATE INDEX idx_accounts_repository
    ON accounts(repository_id);

-- ============================================================
-- 3. TRANSACTION REQUESTS
-- ============================================================

CREATE TABLE transaction_requests (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_key VARCHAR(100) NOT NULL UNIQUE,
    account_id BIGINT NOT NULL REFERENCES accounts(account_id),
    operation transaction_operation NOT NULL,
    amount NUMERIC(18, 2) NOT NULL,
    strategy concurrency_strategy NOT NULL,
    status transaction_status NOT NULL DEFAULT 'REJECTED',
    expected_version BIGINT,
    resulting_version BIGINT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,

    CONSTRAINT positive_transaction_amount CHECK (amount > 0),
    CONSTRAINT valid_expected_version CHECK (
        expected_version IS NULL OR expected_version >= 0
    )
);

CREATE INDEX idx_transaction_account_time
    ON transaction_requests(account_id, created_at DESC);

CREATE INDEX idx_transaction_status
    ON transaction_requests(status, created_at DESC);

-- ============================================================
-- 4. AUDIT HISTORY
-- ============================================================

CREATE TABLE account_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id BIGINT NOT NULL
        REFERENCES transaction_requests(transaction_id),
    account_id BIGINT NOT NULL REFERENCES accounts(account_id),
    old_balance NUMERIC(18, 2) NOT NULL,
    new_balance NUMERIC(18, 2) NOT NULL,
    old_version BIGINT NOT NULL,
    new_version BIGINT NOT NULL,
    strategy concurrency_strategy NOT NULL,
    operation transaction_operation NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_version_transition CHECK (
        new_version = old_version + 1
    )
);

CREATE INDEX idx_audit_account_version
    ON account_audit(account_id, new_version);

-- ============================================================
-- 5. VERSION MANAGEMENT
-- ============================================================

-- Every actual balance change increments the version.
-- Clients must not be allowed to update the version independently.

CREATE OR REPLACE FUNCTION enforce_account_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.balance IS DISTINCT FROM OLD.balance THEN
        NEW.version := OLD.version + 1;
    ELSE
        NEW.version := OLD.version;
    END IF;

    NEW.updated_at := CURRENT_TIMESTAMP;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_account_version
BEFORE UPDATE ON accounts
FOR EACH ROW
EXECUTE FUNCTION enforce_account_version();

-- ============================================================
-- 6. AUDIT GENERATION
-- ============================================================

CREATE OR REPLACE FUNCTION audit_account_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_id BIGINT;
BEGIN
    IF NEW.balance IS DISTINCT FROM OLD.balance THEN

        v_transaction_id :=
            NULLIF(
                current_setting(
                    'concurrency_lab.transaction_id',
                    true
                ),
                ''
            )::BIGINT;

        IF v_transaction_id IS NOT NULL THEN
            INSERT INTO account_audit (
                transaction_id,
                account_id,
                old_balance,
                new_balance,
                old_version,
                new_version,
                strategy,
                operation
            )
            VALUES (
                v_transaction_id,
                NEW.account_id,
                OLD.balance,
                NEW.balance,
                OLD.version,
                NEW.version,
                current_setting(
                    'concurrency_lab.strategy'
                )::concurrency_strategy,
                current_setting(
                    'concurrency_lab.operation'
                )::transaction_operation
            );
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_account_audit
AFTER UPDATE ON accounts
FOR EACH ROW
EXECUTE FUNCTION audit_account_change();

-- ============================================================
-- 7. SAMPLE DATA
-- ============================================================

INSERT INTO repositories (repository_name)
VALUES
    ('CUSTOMER_ACCOUNT_SERVICE'),
    ('PAYMENT_PROCESSING_SERVICE');

INSERT INTO accounts (
    repository_id,
    owner_name,
    balance
)
VALUES
    (1, 'Customer A', 1000.00),
    (1, 'Customer B', 2000.00),
    (2, 'Customer C', 5000.00),
    (2, 'Customer D', 100.00);

-- ============================================================
-- 8. DEMONSTRATE LOST UPDATE
-- ============================================================

-- Transaction A and Transaction B both read 1000.
-- Transaction A calculates 1000 + 200 = 1200.
-- Transaction B calculates 1000 - 100 = 900.
--
-- The second update overwrites the first result.
-- Actual balance becomes 900 instead of 1100.
--
-- Run this section in one transaction for demonstration.

BEGIN;

INSERT INTO transaction_requests (
    request_key,
    account_id,
    operation,
    amount,
    strategy,
    status,
    expected_version
)
VALUES
    (
        'UNSAFE-DEPOSIT-001',
        1,
        'DEPOSIT',
        200,
        'UNSAFE',
        'COMMITTED',
        0
    ),
    (
        'UNSAFE-WITHDRAW-001',
        1,
        'WITHDRAW',
        100,
        'UNSAFE',
        'COMMITTED',
        0
    );

-- Both calculations use the stale initial value.
-- The first statement writes 1200.
SELECT set_config(
    'concurrency_lab.transaction_id',
    (
        SELECT transaction_id::TEXT
        FROM transaction_requests
        WHERE request_key = 'UNSAFE-DEPOSIT-001'
    ),
    true
);

SELECT set_config(
    'concurrency_lab.strategy',
    'UNSAFE',
    true
);

SELECT set_config(
    'concurrency_lab.operation',
    'DEPOSIT',
    true
);

UPDATE accounts
SET balance = 1000.00 + 200.00
WHERE account_id = 1;

-- The second stale calculation overwrites the deposit.
SELECT set_config(
    'concurrency_lab.transaction_id',
    (
        SELECT transaction_id::TEXT
        FROM transaction_requests
        WHERE request_key = 'UNSAFE-WITHDRAW-001'
    ),
    true
);

SELECT set_config(
    'concurrency_lab.operation',
    'WITHDRAW',
    true
);

UPDATE accounts
SET balance = 1000.00 - 100.00
WHERE account_id = 1;

COMMIT;

-- Expected balance: 1100.00
-- Actual balance: 900.00

SELECT
    account_id,
    owner_name,
    balance,
    version
FROM accounts
WHERE account_id = 1;

-- ============================================================
-- 9. OPTIMISTIC CONCURRENCY CONTROL
-- ============================================================

-- A transaction succeeds only if the expected version matches.
-- UPDATE is atomic and the version condition is checked
-- against the row being modified.
--
-- A zero-row update indicates a conflict or missing account.

CREATE OR REPLACE FUNCTION optimistic_update(
    p_request_key VARCHAR,
    p_account_id BIGINT,
    p_expected_version BIGINT,
    p_operation transaction_operation,
    p_amount NUMERIC(18, 2)
)
RETURNS TABLE (
    result_status transaction_status,
    result_balance NUMERIC(18, 2),
    result_version BIGINT,
    result_message TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_id BIGINT;
    v_new_balance NUMERIC(18, 2);
    v_new_version BIGINT;
    v_current_version BIGINT;
BEGIN
    IF p_amount IS NULL OR p_amount <= 0 THEN
        RAISE EXCEPTION 'Amount must be positive.';
    END IF;

    IF p_expected_version < 0 THEN
        RAISE EXCEPTION 'Expected version cannot be negative.';
    END IF;

    IF p_operation NOT IN ('DEPOSIT', 'WITHDRAW') THEN
        RAISE EXCEPTION 'Unsupported operation.';
    END IF;

    INSERT INTO transaction_requests (
        request_key,
        account_id,
        operation,
        amount,
        strategy,
        status,
        expected_version
    )
    VALUES (
        p_request_key,
        p_account_id,
        p_operation,
        p_amount,
        'OPTIMISTIC',
        'REJECTED',
        p_expected_version
    )
    ON CONFLICT (request_key) DO NOTHING
    RETURNING transaction_id INTO v_transaction_id;

    IF v_transaction_id IS NULL THEN
        RETURN QUERY
        SELECT
            tr.status,
            a.balance,
            a.version,
            'Duplicate request key or previously processed request'
        FROM transaction_requests tr
        JOIN accounts a
            ON a.account_id = tr.account_id
        WHERE tr.request_key = p_request_key;

        RETURN;
    END IF;

    IF p_operation = 'DEPOSIT' THEN

        UPDATE accounts
        SET balance = balance + p_amount
        WHERE account_id = p_account_id
          AND version = p_expected_version
          AND balance <= 9999999999999999.99 - p_amount
        RETURNING balance, version
        INTO v_new_balance, v_new_version;

    ELSE

        UPDATE accounts
        SET balance = balance - p_amount
        WHERE account_id = p_account_id
          AND version = p_expected_version
          AND balance >= p_amount
        RETURNING balance, version
        INTO v_new_balance, v_new_version;

    END IF;

    IF NOT FOUND THEN

        SELECT version
        INTO v_current_version
        FROM accounts
        WHERE account_id = p_account_id;

        IF NOT FOUND THEN
            UPDATE transaction_requests
            SET status = 'REJECTED',
                error_message = 'Account not found.',
                completed_at = CURRENT_TIMESTAMP
            WHERE transaction_id = v_transaction_id;

            RETURN QUERY
            SELECT
                'REJECTED'::transaction_status,
                NULL::NUMERIC(18, 2),
                NULL::BIGINT,
                'Account not found';

            RETURN;
        END IF;

        IF v_current_version <> p_expected_version THEN
            UPDATE transaction_requests
            SET status = 'CONFLICT',
                error_message = 'Stale version detected.',
                completed_at = CURRENT_TIMESTAMP
            WHERE transaction_id = v_transaction_id;

            RETURN QUERY
            SELECT
                'CONFLICT'::transaction_status,
                a.balance,
                a.version,
                'Version conflict: refresh and retry'
            FROM accounts a
            WHERE a.account_id = p_account_id;

            RETURN;
        END IF;

        UPDATE transaction_requests
        SET status = 'REJECTED',
            error_message = 'Insufficient funds or invalid balance.',
            completed_at = CURRENT_TIMESTAMP
        WHERE transaction_id = v_transaction_id;

        RETURN QUERY
        SELECT
            'REJECTED'::transaction_status,
            a.balance,
            a.version,
            'Business rule rejected the update'
        FROM accounts a
        WHERE a.account_id = p_account_id;

        RETURN;
    END IF;

    PERFORM set_config(
        'concurrency_lab.transaction_id',
        v_transaction_id::TEXT,
        true
    );

    -- The audit trigger reads transaction metadata.
    -- The update above has already completed. Audit is generated
    -- by the trigger only when metadata is set before the update.
    --
    -- Therefore the audit insert is performed explicitly here.
    INSERT INTO account_audit (
        transaction_id,
        account_id,
        old_balance,
        new_balance,
        old_version,
        new_version,
        strategy,
        operation
    )
    SELECT
        v_transaction_id,
        p_account_id,
        CASE
            WHEN p_operation = 'DEPOSIT'
                THEN v_new_balance - p_amount
            ELSE v_new_balance + p_amount
        END,
        v_new_balance,
        p_expected_version,
        v_new_version,
        'OPTIMISTIC',
        p_operation;

    UPDATE transaction_requests
    SET status = 'COMMITTED',
        resulting_version = v_new_version,
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = v_transaction_id;

    RETURN QUERY
    SELECT
        'COMMITTED'::transaction_status,
        v_new_balance,
        v_new_version,
        'Optimistic update committed';
END;
$$;

-- Account 1 currently has version 2.
SELECT *
FROM optimistic_update(
    'OPT-001',
    1,
    2,
    'DEPOSIT',
    200
);

-- Reusing version 2 must produce a conflict.
SELECT *
FROM optimistic_update(
    'OPT-002',
    1,
    2,
    'WITHDRAW',
    100
);

-- ============================================================
-- 10. PESSIMISTIC CONCURRENCY CONTROL
-- ============================================================

-- SELECT FOR UPDATE locks the selected account row.
-- A concurrent transaction attempting to lock or modify
-- this row must wait until the current transaction finishes.

CREATE OR REPLACE FUNCTION pessimistic_update(
    p_request_key VARCHAR,
    p_account_id BIGINT,
    p_operation transaction_operation,
    p_amount NUMERIC(18, 2)
)
RETURNS TABLE (
    result_status transaction_status,
    result_balance NUMERIC(18, 2),
    result_version BIGINT,
    result_message TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_id BIGINT;
    v_old_balance NUMERIC(18, 2);
    v_new_balance NUMERIC(18, 2);
    v_old_version BIGINT;
    v_new_version BIGINT;
BEGIN
    IF p_amount IS NULL OR p_amount <= 0 THEN
        RAISE EXCEPTION 'Amount must be positive.';
    END IF;

    INSERT INTO transaction_requests (
        request_key,
        account_id,
        operation,
        amount,
        strategy,
        status
    )
    VALUES (
        p_request_key,
        p_account_id,
        p_operation,
        p_amount,
        'PESSIMISTIC',
        'REJECTED'
    )
    ON CONFLICT (request_key) DO NOTHING
    RETURNING transaction_id INTO v_transaction_id;

    IF v_transaction_id IS NULL THEN
        RETURN QUERY
        SELECT
            tr.status,
            a.balance,
            a.version,
            'Duplicate request'
        FROM transaction_requests tr
        JOIN accounts a
            ON a.account_id = tr.account_id
        WHERE tr.request_key = p_request_key;

        RETURN;
    END IF;

    SELECT balance, version
    INTO v_old_balance, v_old_version
    FROM accounts
    WHERE account_id = p_account_id
    FOR UPDATE;

    IF NOT FOUND THEN
        UPDATE transaction_requests
        SET status = 'REJECTED',
            error_message = 'Account not found.',
            completed_at = CURRENT_TIMESTAMP
        WHERE transaction_id = v_transaction_id;

        RETURN QUERY
        SELECT
            'REJECTED'::transaction_status,
            NULL::NUMERIC(18, 2),
            NULL::BIGINT,
            'Account not found';

        RETURN;
    END IF;

    IF p_operation = 'DEPOSIT' THEN
        v_new_balance := v_old_balance + p_amount;
    ELSE
        v_new_balance := v_old_balance - p_amount;
    END IF;

    IF v_new_balance < 0
       OR v_new_balance > 9999999999999999.99 THEN

        UPDATE transaction_requests
        SET status = 'REJECTED',
            error_message = 'Balance validation failed.',
            completed_at = CURRENT_TIMESTAMP
        WHERE transaction_id = v_transaction_id;

        RETURN QUERY
        SELECT
            'REJECTED'::transaction_status,
            v_old_balance,
            v_old_version,
            'Balance validation failed';

        RETURN;
    END IF;

    PERFORM set_config(
        'concurrency_lab.transaction_id',
        v_transaction_id::TEXT,
        true
    );

    PERFORM set_config(
        'concurrency_lab.strategy',
        'PESSIMISTIC',
        true
    );

    PERFORM set_config(
        'concurrency_lab.operation',
        p_operation::TEXT,
        true
    );

    UPDATE accounts
    SET balance = v_new_balance
    WHERE account_id = p_account_id
    RETURNING version
    INTO v_new_version;

    UPDATE transaction_requests
    SET status = 'COMMITTED',
        resulting_version = v_new_version,
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = v_transaction_id;

    RETURN QUERY
    SELECT
        'COMMITTED'::transaction_status,
        v_new_balance,
        v_new_version,
        'Pessimistic update committed';
END;
$$;

SELECT *
FROM pessimistic_update(
    'PESS-001',
    2,
    'DEPOSIT',
    250
);

SELECT *
FROM pessimistic_update(
    'PESS-002',
    2,
    'WITHDRAW',
    100
);

-- ============================================================
-- 11. CONDITIONAL UPDATE WITHOUT A STORED FUNCTION
-- ============================================================

-- Useful when application code already knows the expected version.
-- A zero-row result indicates a stale snapshot or invalid operation.

UPDATE accounts
SET balance = balance + 50
WHERE account_id = 3
  AND version = 0
RETURNING account_id, balance, version;

-- ============================================================
-- 12. TRANSACTIONAL FAILURE HANDLING
-- ============================================================

-- A failed transaction is rolled back completely.

BEGIN;

UPDATE accounts
SET balance = balance + 100
WHERE account_id = 4;

-- Deliberately trigger a constraint violation.
SAVEPOINT before_invalid_update;

UPDATE accounts
SET balance = -500
WHERE account_id = 4;

-- The statement fails because of the positive_balance constraint.
-- In an interactive session, execute:
-- ROLLBACK TO SAVEPOINT before_invalid_update;
-- ROLLBACK;

-- The script continues with a complete rollback.
ROLLBACK;

-- ============================================================
-- 13. RETRIEVAL AND REPORTING
-- ============================================================

-- Current account state.
SELECT
    a.account_id,
    r.repository_name,
    a.owner_name,
    a.balance,
    a.version,
    a.updated_at
FROM accounts a
LEFT JOIN repositories r
    ON r.repository_id = a.repository_id
ORDER BY a.account_id;

-- Transaction history.
SELECT
    transaction_id,
    request_key,
    account_id,
    operation,
    amount,
    strategy,
    status,
    expected_version,
    resulting_version,
    error_message,
    created_at
FROM transaction_requests
ORDER BY transaction_id;

-- Audit history.
SELECT
    audit_id,
    account_id,
    transaction_id,
    old_balance,
    new_balance,
    old_version,
    new_version,
    strategy,
    operation,
    changed_at
FROM account_audit
ORDER BY audit_id;

-- ============================================================
-- 14. CONCURRENCY CONFLICT REPORT
-- ============================================================

SELECT
    strategy,
    status,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount
FROM transaction_requests
GROUP BY strategy, status
ORDER BY strategy, status;

-- ============================================================
-- 15. ACCOUNT VERSION AND CONSISTENCY REPORT
-- ============================================================

WITH latest_audit AS (
    SELECT DISTINCT ON (account_id)
        account_id,
        new_balance,
        new_version,
        changed_at
    FROM account_audit
    ORDER BY account_id, new_version DESC
)
SELECT
    a.account_id,
    a.owner_name,
    a.balance AS current_balance,
    a.version AS current_version,
    la.new_balance AS audited_balance,
    la.new_version AS audited_version,
    CASE
        WHEN la.account_id IS NULL THEN 'NO AUDIT ENTRY'
        WHEN a.balance = la.new_balance
         AND a.version = la.new_version THEN 'CONSISTENT'
        ELSE 'REQUIRES INVESTIGATION'
    END AS consistency_status
FROM accounts a
LEFT JOIN latest_audit la
    ON la.account_id = a.account_id
ORDER BY a.account_id;

-- ============================================================
-- 16. AGGREGATION VIEW
-- ============================================================

CREATE OR REPLACE VIEW account_concurrency_summary AS
SELECT
    a.account_id,
    a.owner_name,
    a.balance,
    a.version,
    COUNT(tr.transaction_id) AS total_requests,
    COUNT(*) FILTER (
        WHERE tr.status = 'COMMITTED'
    ) AS committed_requests,
    COUNT(*) FILTER (
        WHERE tr.status = 'CONFLICT'
    ) AS conflicted_requests,
    COUNT(*) FILTER (
        WHERE tr.status = 'REJECTED'
    ) AS rejected_requests
FROM accounts a
LEFT JOIN transaction_requests tr
    ON tr.account_id = a.account_id
GROUP BY
    a.account_id,
    a.owner_name,
    a.balance,
    a.version;

SELECT *
FROM account_concurrency_summary
ORDER BY account_id;

-- ============================================================
-- 17. ELIGIBILITY AND VERSION VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION check_write_eligibility(
    p_account_id BIGINT,
    p_expected_version BIGINT,
    p_operation transaction_operation,
    p_amount NUMERIC(18, 2)
)
RETURNS TABLE (
    eligible BOOLEAN,
    current_version BIGINT,
    current_balance NUMERIC(18, 2),
    reason TEXT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        CASE
            WHEN a.account_id IS NULL THEN FALSE
            WHEN p_amount IS NULL OR p_amount <= 0 THEN FALSE
            WHEN p_expected_version IS NULL
                OR a.version <> p_expected_version THEN FALSE
            WHEN p_operation = 'WITHDRAW'
                AND a.balance < p_amount THEN FALSE
            WHEN p_operation = 'DEPOSIT'
                AND a.balance > 9999999999999999.99 - p_amount
                THEN FALSE
            ELSE TRUE
        END,
        a.version,
        a.balance,
        CASE
            WHEN a.account_id IS NULL THEN 'ACCOUNT NOT FOUND'
            WHEN p_amount IS NULL OR p_amount <= 0
                THEN 'INVALID AMOUNT'
            WHEN p_expected_version IS NULL
                OR a.version <> p_expected_version
                THEN 'VERSION CONFLICT'
            WHEN p_operation = 'WITHDRAW'
                AND a.balance < p_amount
                THEN 'INSUFFICIENT FUNDS'
            WHEN p_operation = 'DEPOSIT'
                AND a.balance > 9999999999999999.99 - p_amount
                THEN 'BALANCE OVERFLOW'
            ELSE 'WRITE ELIGIBLE'
        END
    FROM (SELECT 1) AS input
    LEFT JOIN accounts a
        ON a.account_id = p_account_id;
$$;

SELECT *
FROM check_write_eligibility(
    1,
    (SELECT version FROM accounts WHERE account_id = 1),
    'DEPOSIT',
    50
);

-- ============================================================
-- 18. OPERATIONAL GUIDANCE
-- ============================================================

-- Optimistic concurrency:
-- Appropriate when conflicts are relatively uncommon.
-- Conditional UPDATE checks the expected version atomically.
--
-- Pessimistic concurrency:
-- Appropriate when conflicts are frequent or operations
-- require exclusive access to a row.
--
-- SERIALIZABLE isolation:
-- Can prevent anomalies that violate serial execution,
-- but applications must handle serialization failures and retry.
--
-- Idempotency:
-- Unique request keys prevent duplicate logical requests.
-- Production implementations should also verify that a reused
-- key has the same request parameters.
--
-- Audit:
-- Store audit events in the same transaction as the business
-- update. The business write and audit entry must commit together.
--
-- Security:
-- Restrict table permissions, expose controlled procedures,
-- validate caller authorization, and avoid trusting client versions
-- as authorization credentials.
--
-- Performance:
-- Index frequently filtered account and transaction columns.
-- Avoid unnecessarily broad locks and long transactions.
--
-- Concurrency:
-- PostgreSQL READ COMMITTED prevents dirty reads but does not
-- automatically prevent every lost-update pattern when applications
-- calculate new values from stale snapshots.
--
-- END OF SCRIPT
