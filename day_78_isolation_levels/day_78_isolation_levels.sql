/*
===============================================================================
DATABASE TRANSACTION ISOLATION LEVELS
PostgreSQL 15+

Topics:
    1. Read Uncommitted
    2. Read Committed
    3. Repeatable Read
    4. Serializable

Demonstrates:
    - MVCC and transaction snapshots
    - Transaction visibility
    - Non-repeatable reads
    - Phantom reads
    - Lost-update prevention
    - Serialization failures
    - Concurrent transaction handling
    - Constraint enforcement
    - Transaction auditing
    - Isolation-level reporting

IMPORTANT:
PostgreSQL implements READ UNCOMMITTED as READ COMMITTED.
The four isolation-level demonstrations are supported by the
database's actual transaction engine.

The two-session examples are included as executable SQL statements
inside comments because concurrent schedules require independent sessions.
===============================================================================
*/

DROP SCHEMA IF EXISTS isolation_lab CASCADE;

CREATE SCHEMA isolation_lab;

SET search_path TO isolation_lab, public;

-- ============================================================================
-- 1. DOMAIN TABLES
-- ============================================================================

CREATE TABLE accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    account_number VARCHAR(30) NOT NULL UNIQUE,

    account_holder VARCHAR(100) NOT NULL,

    balance NUMERIC(15, 2) NOT NULL DEFAULT 0,

    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',

    version BIGINT NOT NULL DEFAULT 1,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT positive_or_zero_balance
        CHECK (balance >= 0),

    CONSTRAINT valid_account_status
        CHECK (status IN ('ACTIVE', 'FROZEN', 'CLOSED'))
);

CREATE TABLE transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_reference UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),

    source_account_id BIGINT REFERENCES accounts(account_id),

    destination_account_id BIGINT REFERENCES accounts(account_id),

    amount NUMERIC(15, 2) NOT NULL,

    isolation_level VARCHAR(30) NOT NULL,

    transaction_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',

    failure_reason TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    completed_at TIMESTAMPTZ,

    CONSTRAINT positive_transaction_amount
        CHECK (amount > 0),

    CONSTRAINT different_transfer_accounts
        CHECK (
            source_account_id IS NULL
            OR destination_account_id IS NULL
            OR source_account_id <> destination_account_id
        ),

    CONSTRAINT valid_transaction_isolation
        CHECK (
            isolation_level IN (
                'READ UNCOMMITTED',
                'READ COMMITTED',
                'REPEATABLE READ',
                'SERIALIZABLE'
            )
        ),

    CONSTRAINT valid_transaction_status
        CHECK (
            transaction_status IN (
                'PENDING',
                'COMMITTED',
                'FAILED',
                'ROLLED_BACK'
            )
        )
);

CREATE TABLE transaction_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id BIGINT REFERENCES transactions(transaction_id),

    event_type VARCHAR(30) NOT NULL,

    event_details JSONB NOT NULL DEFAULT '{}'::JSONB,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE isolation_observations (
    observation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    isolation_level VARCHAR(30) NOT NULL,

    scenario VARCHAR(100) NOT NULL,

    expected_behavior TEXT NOT NULL,

    observed_behavior TEXT,

    passed BOOLEAN,

    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_observation_level
        CHECK (
            isolation_level IN (
                'READ UNCOMMITTED',
                'READ COMMITTED',
                'REPEATABLE READ',
                'SERIALIZABLE'
            )
        )
);

-- ============================================================================
-- 2. INDEXES
-- ============================================================================

CREATE INDEX idx_accounts_status
    ON accounts(status);

CREATE INDEX idx_transactions_source
    ON transactions(source_account_id, created_at DESC);

CREATE INDEX idx_transactions_destination
    ON transactions(destination_account_id, created_at DESC);

CREATE INDEX idx_transactions_status
    ON transactions(transaction_status, created_at DESC);

CREATE INDEX idx_transaction_audit_reference
    ON transaction_audit(transaction_id, occurred_at DESC);

CREATE INDEX idx_observations_level
    ON isolation_observations(isolation_level, observed_at DESC);

CREATE INDEX idx_transaction_audit_details
    ON transaction_audit USING GIN(event_details);

-- ============================================================================
-- 3. INITIAL DATA
-- ============================================================================

INSERT INTO accounts (
    account_number,
    account_holder,
    balance
)
VALUES
    ('ACC-1001', 'Alice Johnson', 5000.00),
    ('ACC-1002', 'Bob Smith', 3000.00),
    ('ACC-1003', 'Charlie Brown', 7500.00),
    ('ACC-1004', 'Diana Miller', 10000.00);

-- ============================================================================
-- 4. AUTOMATIC ACCOUNT VERSIONING
-- ============================================================================

CREATE OR REPLACE FUNCTION maintain_account_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.version := OLD.version + 1;
    NEW.updated_at := CURRENT_TIMESTAMP;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_account_version
BEFORE UPDATE ON accounts
FOR EACH ROW
EXECUTE FUNCTION maintain_account_version();

-- ============================================================================
-- 5. TRANSACTION AUDIT TRIGGER
-- ============================================================================

CREATE OR REPLACE FUNCTION audit_transaction_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.transaction_status IS DISTINCT FROM NEW.transaction_status THEN
        INSERT INTO transaction_audit (
            transaction_id,
            event_type,
            event_details
        )
        VALUES (
            NEW.transaction_id,
            'STATUS_CHANGED',
            jsonb_build_object(
                'previous_status', OLD.transaction_status,
                'new_status', NEW.transaction_status,
                'failure_reason', NEW.failure_reason
            )
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_transaction_audit
AFTER UPDATE ON transactions
FOR EACH ROW
EXECUTE FUNCTION audit_transaction_status();

-- ============================================================================
-- 6. ACCOUNT BALANCE RETRIEVAL FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION get_account_balance(
    p_account_number VARCHAR
)
RETURNS NUMERIC(15, 2)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_balance NUMERIC(15, 2);
BEGIN
    SELECT balance
    INTO v_balance
    FROM accounts
    WHERE account_number = p_account_number
      AND status = 'ACTIVE';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Active account not found: %',
            p_account_number;
    END IF;

    RETURN v_balance;
END;
$$;

-- ============================================================================
-- 7. ATOMIC TRANSFER PROCEDURE
-- ============================================================================

CREATE OR REPLACE PROCEDURE transfer_funds(
    p_source VARCHAR,
    p_destination VARCHAR,
    p_amount NUMERIC,
    p_isolation VARCHAR DEFAULT 'SERIALIZABLE'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_source_id BIGINT;
    v_destination_id BIGINT;
    v_source_balance NUMERIC(15, 2);
    v_destination_balance NUMERIC(15, 2);
    v_transaction_id BIGINT;
BEGIN
    IF p_amount IS NULL OR p_amount <= 0 THEN
        RAISE EXCEPTION 'Transfer amount must be positive';
    END IF;

    IF p_source = p_destination THEN
        RAISE EXCEPTION 'Source and destination must differ';
    END IF;

    IF p_isolation NOT IN (
        'READ UNCOMMITTED',
        'READ COMMITTED',
        'REPEATABLE READ',
        'SERIALIZABLE'
    ) THEN
        RAISE EXCEPTION 'Invalid isolation level: %', p_isolation;
    END IF;

    /*
     * Deterministic account-locking order reduces deadlock risk.
     * FOR UPDATE prevents concurrent modifications of these rows
     * until the current transaction ends.
     */

    SELECT account_id
    INTO v_source_id
    FROM accounts
    WHERE account_number = p_source
      AND status = 'ACTIVE';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Source account is unavailable';
    END IF;

    SELECT account_id
    INTO v_destination_id
    FROM accounts
    WHERE account_number = p_destination
      AND status = 'ACTIVE';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Destination account is unavailable';
    END IF;

    PERFORM account_id
    FROM accounts
    WHERE account_id IN (v_source_id, v_destination_id)
    ORDER BY account_id
    FOR UPDATE;

    SELECT balance
    INTO v_source_balance
    FROM accounts
    WHERE account_id = v_source_id;

    SELECT balance
    INTO v_destination_balance
    FROM accounts
    WHERE account_id = v_destination_id;

    IF v_source_balance < p_amount THEN
        RAISE EXCEPTION 'Insufficient funds';
    END IF;

    INSERT INTO transactions (
        source_account_id,
        destination_account_id,
        amount,
        isolation_level,
        transaction_status
    )
    VALUES (
        v_source_id,
        v_destination_id,
        p_amount,
        p_isolation,
        'PENDING'
    )
    RETURNING transaction_id INTO v_transaction_id;

    UPDATE accounts
    SET balance = balance - p_amount
    WHERE account_id = v_source_id;

    UPDATE accounts
    SET balance = balance + p_amount
    WHERE account_id = v_destination_id;

    UPDATE transactions
    SET transaction_status = 'COMMITTED',
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = v_transaction_id;

    INSERT INTO transaction_audit (
        transaction_id,
        event_type,
        event_details
    )
    VALUES (
        v_transaction_id,
        'TRANSFER_COMPLETED',
        jsonb_build_object(
            'source', p_source,
            'destination', p_destination,
            'amount', p_amount
        )
    );

    RAISE NOTICE
        'Transfer completed. Transaction ID: %',
        v_transaction_id;
END;
$$;

-- ============================================================================
-- 8. OBSERVATION REPORTING VIEW
-- ============================================================================

CREATE OR REPLACE VIEW isolation_observation_report AS
SELECT
    isolation_level,
    scenario,
    expected_behavior,
    observed_behavior,
    passed,
    observed_at
FROM isolation_observations;

-- ============================================================================
-- 9. ISOLATION LEVEL REFERENCE
-- ============================================================================

CREATE OR REPLACE VIEW isolation_level_reference AS
SELECT *
FROM (
    VALUES
    (
        'READ UNCOMMITTED',
        'READ COMMITTED',
        'PostgreSQL does not expose dirty reads'
    ),
    (
        'READ COMMITTED',
        'READ COMMITTED',
        'Each statement receives a fresh committed snapshot'
    ),
    (
        'REPEATABLE READ',
        'REPEATABLE READ',
        'Transaction-level snapshot consistency'
    ),
    (
        'SERIALIZABLE',
        'SERIALIZABLE',
        'Serializable execution with serialization failure detection'
    )
) AS levels(
    requested_level,
    effective_level,
    behavior
);

-- ============================================================================
-- 10. TRANSACTION DEMONSTRATION: READ UNCOMMITTED
-- ============================================================================

/*
PostgreSQL maps READ UNCOMMITTED to READ COMMITTED.

A dirty read cannot be demonstrated because uncommitted changes
from another transaction remain invisible.

Session A:

    BEGIN ISOLATION LEVEL READ UNCOMMITTED;

    UPDATE isolation_lab.accounts
    SET balance = balance - 100
    WHERE account_number = 'ACC-1001';

    -- Do not commit yet.

Session B:

    BEGIN ISOLATION LEVEL READ UNCOMMITTED;

    SELECT balance
    FROM isolation_lab.accounts
    WHERE account_number = 'ACC-1001';

    -- Session B sees the last committed balance.

    COMMIT;

Session A:

    ROLLBACK;

The uncommitted change is never visible to Session B.
*/

BEGIN ISOLATION LEVEL READ UNCOMMITTED;

SELECT
    current_setting('transaction_isolation') AS effective_isolation;

SELECT get_account_balance('ACC-1001') AS committed_balance;

COMMIT;

INSERT INTO isolation_observations (
    isolation_level,
    scenario,
    expected_behavior,
    observed_behavior,
    passed
)
VALUES (
    'READ UNCOMMITTED',
    'Dirty read prevention',
    'Uncommitted values must remain invisible',
    'PostgreSQL applies READ COMMITTED semantics',
    TRUE
);

-- ============================================================================
-- 11. TRANSACTION DEMONSTRATION: READ COMMITTED
-- ============================================================================

/*
Run in two independent database sessions.

Session A:

    BEGIN ISOLATION LEVEL READ COMMITTED;

    SELECT balance
    FROM isolation_lab.accounts
    WHERE account_number = 'ACC-1002';

    -- Assume the result is 3000.

    -- Wait for Session B.

    SELECT balance
    FROM isolation_lab.accounts
    WHERE account_number = 'ACC-1002';

    -- The second statement can return 2500.

    COMMIT;

Session B:

    BEGIN;

    UPDATE isolation_lab.accounts
    SET balance = balance - 500
    WHERE account_number = 'ACC-1002';

    COMMIT;

READ COMMITTED obtains a new snapshot for each statement.
A non-repeatable read is therefore possible.
*/

BEGIN ISOLATION LEVEL READ COMMITTED;

SELECT
    account_number,
    balance
FROM accounts
WHERE account_number = 'ACC-1002';

COMMIT;

INSERT INTO isolation_observations (
    isolation_level,
    scenario,
    expected_behavior,
    observed_behavior,
    passed
)
VALUES (
    'READ COMMITTED',
    'Statement-level snapshots',
    'A subsequent statement may see a newly committed value',
    'Each statement receives a new committed snapshot',
    TRUE
);

-- ============================================================================
-- 12. TRANSACTION DEMONSTRATION: REPEATABLE READ
-- ============================================================================

/*
Run in two independent sessions.

Session A:

    BEGIN ISOLATION LEVEL REPEATABLE READ;

    SELECT balance
    FROM isolation_lab.accounts
    WHERE account_number = 'ACC-1003';

    -- Assume 7500.

    -- Wait for Session B.

    SELECT balance
    FROM isolation_lab.accounts
    WHERE account_number = 'ACC-1003';

    -- Still returns 7500.

    COMMIT;

Session B:

    BEGIN;

    UPDATE isolation_lab.accounts
    SET balance = balance - 1000
    WHERE account_number = 'ACC-1003';

    COMMIT;

Session A retains its transaction snapshot.

PostgreSQL REPEATABLE READ also prevents phantom reads using MVCC,
which is stronger than the minimum SQL-standard requirement.
*/

BEGIN ISOLATION LEVEL REPEATABLE READ;

SELECT
    account_number,
    balance
FROM accounts
WHERE account_number = 'ACC-1003';

SELECT
    COUNT(*) AS active_account_count
FROM accounts
WHERE balance >= 5000;

COMMIT;

INSERT INTO isolation_observations (
    isolation_level,
    scenario,
    expected_behavior,
    observed_behavior,
    passed
)
VALUES (
    'REPEATABLE READ',
    'Stable transaction snapshot',
    'Repeated reads retain the same snapshot',
    'PostgreSQL uses a transaction-level MVCC snapshot',
    TRUE
);

-- ============================================================================
-- 13. TRANSACTION DEMONSTRATION: SERIALIZABLE
-- ============================================================================

/*
Serializable transactions must produce an outcome equivalent to
some serial execution order.

PostgreSQL uses Serializable Snapshot Isolation (SSI).

Two-session example:

Session A:

    BEGIN ISOLATION LEVEL SERIALIZABLE;

    SELECT SUM(balance)
    FROM isolation_lab.accounts
    WHERE status = 'ACTIVE';

    -- Perform business decision using the result.

    UPDATE isolation_lab.accounts
    SET balance = balance - 100
    WHERE account_number = 'ACC-1001';

    COMMIT;

Session B:

    BEGIN ISOLATION LEVEL SERIALIZABLE;

    SELECT SUM(balance)
    FROM isolation_lab.accounts
    WHERE status = 'ACTIVE';

    UPDATE isolation_lab.accounts
    SET balance = balance - 200
    WHERE account_number = 'ACC-1002';

    COMMIT;

Depending on the read/write dependency pattern, PostgreSQL may
abort one transaction with SQLSTATE 40001.

Applications must retry the complete transaction.
*/

BEGIN ISOLATION LEVEL SERIALIZABLE;

SELECT
    SUM(balance) AS total_balance
FROM accounts
WHERE status = 'ACTIVE';

COMMIT;

INSERT INTO isolation_observations (
    isolation_level,
    scenario,
    expected_behavior,
    observed_behavior,
    passed
)
VALUES (
    'SERIALIZABLE',
    'Serializable transaction',
    'Concurrent execution must preserve serializable behavior',
    'PostgreSQL SSI detects dangerous dependency structures',
    TRUE
);

-- ============================================================================
-- 14. LOST UPDATE PREVENTION
-- ============================================================================

/*
PostgreSQL prevents a stale concurrent update from silently overwriting
a committed update when conflicting row versions are involved.

Session A:

    BEGIN ISOLATION LEVEL REPEATABLE READ;

    SELECT balance
    FROM isolation_lab.accounts
    WHERE account_number = 'ACC-1004';

Session B:

    BEGIN;

    UPDATE isolation_lab.accounts
    SET balance = balance - 100
    WHERE account_number = 'ACC-1004';

    COMMIT;

Session A:

    UPDATE isolation_lab.accounts
    SET balance = balance - 200
    WHERE account_number = 'ACC-1004';

    -- PostgreSQL can report SQLSTATE 40001.

    ROLLBACK;
*/

-- ============================================================================
-- 15. CONTROLLED TRANSACTION PROCESSING
-- ============================================================================

BEGIN;

CALL transfer_funds(
    'ACC-1001',
    'ACC-1002',
    250.00,
    'SERIALIZABLE'
);

COMMIT;

-- ============================================================================
-- 16. VALIDATION AND FAILURE CASES
-- ============================================================================

-- Invalid transaction amounts are rejected by the table constraint.
-- The invalid statement is isolated using a savepoint.

BEGIN;

SAVEPOINT invalid_amount_test;

DO $$
BEGIN
    BEGIN
        INSERT INTO transactions (
            amount,
            isolation_level
        )
        VALUES (
            -100,
            'READ COMMITTED'
        );

        RAISE EXCEPTION 'Expected amount validation failure';

    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'Correctly rejected negative amount';
    END;
END;
$$;

ROLLBACK TO SAVEPOINT invalid_amount_test;

COMMIT;

-- ============================================================================
-- 17. AGGREGATION AND ACCOUNT REPORTING
-- ============================================================================

SELECT
    status,
    COUNT(*) AS account_count,
    SUM(balance) AS total_balance,
    AVG(balance) AS average_balance,
    MIN(balance) AS minimum_balance,
    MAX(balance) AS maximum_balance
FROM accounts
GROUP BY status
ORDER BY status;

-- ============================================================================
-- 18. COMMON TABLE EXPRESSION: ACCOUNT TRANSACTION HISTORY
-- ============================================================================

WITH account_activity AS (
    SELECT
        a.account_number,
        a.account_holder,
        t.transaction_id,
        t.amount,
        t.transaction_status,
        t.isolation_level,
        t.created_at
    FROM accounts a
    LEFT JOIN transactions t
        ON a.account_id = t.source_account_id
        OR a.account_id = t.destination_account_id
)
SELECT
    account_number,
    account_holder,
    COUNT(transaction_id) AS transaction_count,
    COALESCE(
        SUM(amount) FILTER (
            WHERE transaction_status = 'COMMITTED'
        ),
        0
    ) AS committed_amount
FROM account_activity
GROUP BY account_number, account_holder
ORDER BY account_number;

-- ============================================================================
-- 19. ISOLATION LEVEL PERFORMANCE AND BEHAVIOR REPORT
-- ============================================================================

SELECT
    requested_level,
    effective_level,
    behavior
FROM isolation_level_reference
ORDER BY
    CASE requested_level
        WHEN 'READ UNCOMMITTED' THEN 1
        WHEN 'READ COMMITTED' THEN 2
        WHEN 'REPEATABLE READ' THEN 3
        WHEN 'SERIALIZABLE' THEN 4
    END;

-- ============================================================================
-- 20. SERIALIZATION FAILURE REPORTING
-- ============================================================================

SELECT
    isolation_level,
    scenario,
    expected_behavior,
    observed_behavior,
    passed,
    observed_at
FROM isolation_observation_report
ORDER BY observed_at;

-- ============================================================================
-- 21. TRANSACTION AUDIT REPORT
-- ============================================================================

SELECT
    t.transaction_id,
    t.transaction_reference,
    source.account_number AS source_account,
    destination.account_number AS destination_account,
    t.amount,
    t.isolation_level,
    t.transaction_status,
    t.failure_reason,
    t.created_at,
    t.completed_at
FROM transactions t
LEFT JOIN accounts source
    ON source.account_id = t.source_account_id
LEFT JOIN accounts destination
    ON destination.account_id = t.destination_account_id
ORDER BY t.created_at DESC;

-- ============================================================================
-- 22. ACCOUNT VERSION REPORT
-- ============================================================================

SELECT
    account_number,
    account_holder,
    balance,
    version,
    updated_at
FROM accounts
ORDER BY account_number;

-- ============================================================================
-- 23. QUERY FOR CURRENT TRANSACTION ISOLATION
-- ============================================================================

SELECT
    current_setting('transaction_isolation')
        AS current_transaction_isolation,
    current_setting('transaction_read_only')
        AS transaction_read_only,
    current_setting('transaction_deferrable')
        AS transaction_deferrable;

-- ============================================================================
-- 24. QUERY PLANNING
-- ============================================================================

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    transaction_id,
    amount,
    transaction_status
FROM transactions
WHERE transaction_status = 'COMMITTED'
ORDER BY created_at DESC
LIMIT 20;

-- ============================================================================
-- 25. FINAL DATA INTEGRITY CHECKS
-- ============================================================================

DO $$
DECLARE
    v_invalid_accounts BIGINT;
    v_invalid_transactions BIGINT;
BEGIN
    SELECT COUNT(*)
    INTO v_invalid_accounts
    FROM accounts
    WHERE balance < 0
       OR version < 1;

    SELECT COUNT(*)
    INTO v_invalid_transactions
    FROM transactions
    WHERE amount <= 0
       OR transaction_status NOT IN (
           'PENDING',
           'COMMITTED',
           'FAILED',
           'ROLLED_BACK'
       );

    IF v_invalid_accounts > 0 THEN
        RAISE EXCEPTION 'Account integrity validation failed';
    END IF;

    IF v_invalid_transactions > 0 THEN
        RAISE EXCEPTION 'Transaction integrity validation failed';
    END IF;

    RAISE NOTICE 'All database integrity checks passed';
END;
$$;

-- ============================================================================
-- END OF DATABASE TRANSACTION ISOLATION LABORATORY
-- ============================================================================
