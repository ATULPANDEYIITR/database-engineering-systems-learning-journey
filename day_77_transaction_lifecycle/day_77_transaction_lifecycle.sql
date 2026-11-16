/*
===============================================================================
TRANSACTION LIFECYCLE MANAGEMENT SYSTEM
PostgreSQL 14+

Topics:
- Transaction states
- BEGIN, COMMIT, ROLLBACK
- Savepoints
- ACID properties
- Isolation levels
- Optimistic concurrency
- Account transfers
- Transaction audit events
- Transaction processing procedures
- Deferred integrity validation
- Failure handling
- Transaction reporting

Execution:
    psql -U postgres -d postgres -f transaction_lifecycle.sql

The script creates a dedicated schema and sample transactional records.
===============================================================================
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS transaction_lab;

SET LOCAL search_path TO transaction_lab, public;

-- ============================================================================
-- 1. DOMAIN TYPES
-- ============================================================================

CREATE TYPE transaction_state AS ENUM (
    'NEW',
    'ACTIVE',
    'COMMITTING',
    'COMMITTED',
    'ROLLING_BACK',
    'ROLLED_BACK',
    'FAILED'
);

CREATE TYPE operation_type AS ENUM (
    'DEPOSIT',
    'WITHDRAWAL',
    'TRANSFER'
);

CREATE TYPE audit_event_type AS ENUM (
    'STARTED',
    'OPERATION_STAGED',
    'SAVEPOINT_CREATED',
    'SAVEPOINT_RESTORED',
    'COMMIT_STARTED',
    'COMMITTED',
    'ROLLBACK_STARTED',
    'ROLLED_BACK',
    'FAILED'
);

-- ============================================================================
-- 2. ACCOUNT MASTER DATA
-- ============================================================================

CREATE TABLE accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    account_number VARCHAR(30) NOT NULL UNIQUE,

    owner_name VARCHAR(120) NOT NULL,

    currency CHAR(3) NOT NULL DEFAULT 'INR',

    balance NUMERIC(18, 2) NOT NULL DEFAULT 0,

    version BIGINT NOT NULL DEFAULT 0,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_account_number
        CHECK (account_number ~ '^[A-Z0-9-]{4,30}$'),

    CONSTRAINT valid_owner_name
        CHECK (length(trim(owner_name)) > 0),

    CONSTRAINT valid_balance
        CHECK (balance >= 0),

    CONSTRAINT valid_version
        CHECK (version >= 0),

    CONSTRAINT valid_currency
        CHECK (currency ~ '^[A-Z]{3}$')
);

-- ============================================================================
-- 3. TRANSACTION MASTER
-- ============================================================================

CREATE TABLE transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_reference UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),

    transaction_type operation_type NOT NULL,

    state transaction_state NOT NULL DEFAULT 'NEW',

    initiated_by VARCHAR(120) NOT NULL,

    description TEXT,

    expected_operation_count INTEGER NOT NULL DEFAULT 0,

    isolation_level_name VARCHAR(30),

    error_message TEXT,

    started_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_initiator
        CHECK (length(trim(initiated_by)) > 0),

    CONSTRAINT valid_operation_count
        CHECK (expected_operation_count >= 0),

    CONSTRAINT valid_completion_time
        CHECK (
            completed_at IS NULL
            OR started_at IS NULL
            OR completed_at >= started_at
        )
);

CREATE INDEX idx_transactions_state
    ON transactions(state, created_at DESC);

CREATE INDEX idx_transactions_reference
    ON transactions(transaction_reference);

CREATE INDEX idx_transactions_initiator
    ON transactions(initiated_by, created_at DESC);

-- ============================================================================
-- 4. TRANSACTION OPERATIONS
-- ============================================================================

CREATE TABLE transaction_operations (
    operation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id BIGINT NOT NULL
        REFERENCES transactions(transaction_id),

    operation_sequence INTEGER NOT NULL,

    operation_type operation_type NOT NULL,

    source_account_id BIGINT
        REFERENCES accounts(account_id),

    destination_account_id BIGINT
        REFERENCES accounts(account_id),

    amount NUMERIC(18, 2) NOT NULL,

    currency CHAR(3) NOT NULL DEFAULT 'INR',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_operation_sequence
        UNIQUE(transaction_id, operation_sequence),

    CONSTRAINT valid_operation_amount
        CHECK (amount > 0),

    CONSTRAINT valid_operation_accounts
        CHECK (
            source_account_id IS NULL
            OR destination_account_id IS NULL
            OR source_account_id <> destination_account_id
        ),

    CONSTRAINT operation_account_requirements
        CHECK (
            (
                operation_type = 'DEPOSIT'
                AND source_account_id IS NULL
                AND destination_account_id IS NOT NULL
            )
            OR
            (
                operation_type = 'WITHDRAWAL'
                AND source_account_id IS NOT NULL
                AND destination_account_id IS NULL
            )
            OR
            (
                operation_type = 'TRANSFER'
                AND source_account_id IS NOT NULL
                AND destination_account_id IS NOT NULL
            )
        )
);

CREATE INDEX idx_operations_transaction
    ON transaction_operations(transaction_id, operation_sequence);

CREATE INDEX idx_operations_source
    ON transaction_operations(source_account_id);

CREATE INDEX idx_operations_destination
    ON transaction_operations(destination_account_id);

-- ============================================================================
-- 5. TRANSACTION AUDIT
-- ============================================================================

CREATE TABLE transaction_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id BIGINT NOT NULL
        REFERENCES transactions(transaction_id),

    event_type audit_event_type NOT NULL,

    previous_state transaction_state,

    current_state transaction_state,

    event_description TEXT NOT NULL,

    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    actor VARCHAR(120) NOT NULL
);

CREATE INDEX idx_transaction_audit_history
    ON transaction_audit(transaction_id, event_timestamp, audit_id);

-- ============================================================================
-- 6. SAVEPOINT METADATA
-- ============================================================================

CREATE TABLE transaction_savepoints (
    savepoint_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id BIGINT NOT NULL
        REFERENCES transactions(transaction_id),

    savepoint_name VARCHAR(100) NOT NULL,

    operation_sequence INTEGER NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_savepoint_name
        UNIQUE(transaction_id, savepoint_name),

    CONSTRAINT valid_savepoint_sequence
        CHECK (operation_sequence >= 0)
);

-- ============================================================================
-- 7. STATE TRANSITION VALIDATION
-- ============================================================================

CREATE FUNCTION validate_transaction_state_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.state = OLD.state THEN
        RETURN NEW;
    END IF;

    IF NOT (
        (OLD.state = 'NEW' AND NEW.state = 'ACTIVE')
        OR
        (
            OLD.state = 'ACTIVE'
            AND NEW.state IN (
                'COMMITTING',
                'ROLLING_BACK',
                'FAILED'
            )
        )
        OR
        (
            OLD.state = 'COMMITTING'
            AND NEW.state IN ('COMMITTED', 'FAILED')
        )
        OR
        (
            OLD.state = 'ROLLING_BACK'
            AND NEW.state IN ('ROLLED_BACK', 'FAILED')
        )
        OR
        (
            OLD.state = 'FAILED'
            AND NEW.state = 'ROLLING_BACK'
        )
    ) THEN
        RAISE EXCEPTION
            'Invalid transaction state transition: % -> %',
            OLD.state,
            NEW.state;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_transaction_state
BEFORE UPDATE OF state
ON transactions
FOR EACH ROW
EXECUTE FUNCTION validate_transaction_state_transition();

-- ============================================================================
-- 8. AUDIT AUTOMATION
-- ============================================================================

CREATE FUNCTION record_transaction_state_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    event_kind audit_event_type;
BEGIN
    IF NEW.state = OLD.state THEN
        RETURN NEW;
    END IF;

    event_kind := CASE NEW.state
        WHEN 'ACTIVE' THEN 'STARTED'
        WHEN 'COMMITTING' THEN 'COMMIT_STARTED'
        WHEN 'COMMITTED' THEN 'COMMITTED'
        WHEN 'ROLLING_BACK' THEN 'ROLLBACK_STARTED'
        WHEN 'ROLLED_BACK' THEN 'ROLLED_BACK'
        WHEN 'FAILED' THEN 'FAILED'
        ELSE 'OPERATION_STAGED'
    END;

    INSERT INTO transaction_audit (
        transaction_id,
        event_type,
        previous_state,
        current_state,
        event_description,
        actor
    )
    VALUES (
        NEW.transaction_id,
        event_kind,
        OLD.state,
        NEW.state,
        'Transaction state changed.',
        NEW.initiated_by
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_transaction_audit
AFTER UPDATE OF state
ON transactions
FOR EACH ROW
EXECUTE FUNCTION record_transaction_state_change();

-- ============================================================================
-- 9. ACCOUNT VERSION MANAGEMENT
-- ============================================================================

CREATE FUNCTION update_account_metadata()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.balance IS DISTINCT FROM OLD.balance THEN
        NEW.version := OLD.version + 1;
    END IF;

    NEW.updated_at := CURRENT_TIMESTAMP;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_account_version
BEFORE UPDATE ON accounts
FOR EACH ROW
EXECUTE FUNCTION update_account_metadata();

-- ============================================================================
-- 10. TRANSACTION START FUNCTION
-- ============================================================================

CREATE FUNCTION begin_business_transaction(
    p_type operation_type,
    p_initiated_by VARCHAR(120),
    p_description TEXT DEFAULT NULL
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_id BIGINT;
BEGIN
    IF p_initiated_by IS NULL
       OR length(trim(p_initiated_by)) = 0 THEN
        RAISE EXCEPTION 'Transaction initiator is required.';
    END IF;

    INSERT INTO transactions (
        transaction_type,
        state,
        initiated_by,
        description,
        started_at,
        isolation_level_name
    )
    VALUES (
        p_type,
        'NEW',
        p_initiated_by,
        p_description,
        CURRENT_TIMESTAMP,
        current_setting('transaction_isolation')
    )
    RETURNING transaction_id INTO v_transaction_id;

    UPDATE transactions
    SET state = 'ACTIVE'
    WHERE transaction_id = v_transaction_id;

    RETURN v_transaction_id;
END;
$$;

-- ============================================================================
-- 11. OPERATION STAGING FUNCTION
-- ============================================================================

CREATE FUNCTION stage_operation(
    p_transaction_id BIGINT,
    p_type operation_type,
    p_source_account BIGINT,
    p_destination_account BIGINT,
    p_amount NUMERIC(18, 2)
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_sequence INTEGER;
    v_operation_id BIGINT;
    v_source_currency CHAR(3);
    v_destination_currency CHAR(3);
BEGIN
    IF p_amount IS NULL OR p_amount <= 0 THEN
        RAISE EXCEPTION 'Amount must be greater than zero.';
    END IF;

    -- Serialize operations belonging to the same transaction.
    PERFORM 1
    FROM transactions
    WHERE transaction_id = p_transaction_id
      AND state = 'ACTIVE'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Transaction does not exist or is not active.';
    END IF;

    IF p_type = 'DEPOSIT' THEN
        IF p_source_account IS NOT NULL
           OR p_destination_account IS NULL THEN
            RAISE EXCEPTION 'Invalid deposit account configuration.';
        END IF;

    ELSIF p_type = 'WITHDRAWAL' THEN
        IF p_source_account IS NULL
           OR p_destination_account IS NOT NULL THEN
            RAISE EXCEPTION 'Invalid withdrawal account configuration.';
        END IF;

    ELSIF p_type = 'TRANSFER' THEN
        IF p_source_account IS NULL
           OR p_destination_account IS NULL
           OR p_source_account = p_destination_account THEN
            RAISE EXCEPTION 'Invalid transfer account configuration.';
        END IF;
    END IF;

    IF p_source_account IS NOT NULL THEN
        SELECT currency
        INTO v_source_currency
        FROM accounts
        WHERE account_id = p_source_account
          AND is_active = TRUE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Source account is unavailable.';
        END IF;
    END IF;

    IF p_destination_account IS NOT NULL THEN
        SELECT currency
        INTO v_destination_currency
        FROM accounts
        WHERE account_id = p_destination_account
          AND is_active = TRUE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Destination account is unavailable.';
        END IF;
    END IF;

    IF p_type = 'TRANSFER'
       AND v_source_currency <> v_destination_currency THEN
        RAISE EXCEPTION
            'Cross-currency transfers require an exchange-rate workflow.';
    END IF;

    SELECT COALESCE(MAX(operation_sequence), 0) + 1
    INTO v_sequence
    FROM transaction_operations
    WHERE transaction_id = p_transaction_id;

    INSERT INTO transaction_operations (
        transaction_id,
        operation_sequence,
        operation_type,
        source_account_id,
        destination_account_id,
        amount,
        currency
    )
    VALUES (
        p_transaction_id,
        v_sequence,
        p_type,
        p_source_account,
        p_destination_account,
        p_amount,
        COALESCE(v_source_currency, v_destination_currency)
    )
    RETURNING operation_id INTO v_operation_id;

    UPDATE transactions
    SET expected_operation_count = expected_operation_count + 1
    WHERE transaction_id = p_transaction_id;

    INSERT INTO transaction_audit (
        transaction_id,
        event_type,
        event_description,
        actor
    )
    SELECT
        transaction_id,
        'OPERATION_STAGED',
        'Operation staged: ' || p_type,
        initiated_by
    FROM transactions
    WHERE transaction_id = p_transaction_id;

    RETURN v_operation_id;
END;
$$;

-- ============================================================================
-- 12. TRANSACTION COMMIT PROCEDURE
-- ============================================================================

CREATE PROCEDURE commit_business_transaction(
    p_transaction_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction transactions%ROWTYPE;
    v_operation transaction_operations%ROWTYPE;
    v_balance NUMERIC(18, 2);
    v_account BIGINT;
    v_source_balance NUMERIC(18, 2);
BEGIN
    SELECT *
    INTO v_transaction
    FROM transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Transaction does not exist.';
    END IF;

    IF v_transaction.state <> 'ACTIVE' THEN
        RAISE EXCEPTION
            'Cannot commit transaction in state %',
            v_transaction.state;
    END IF;

    UPDATE transactions
    SET state = 'COMMITTING'
    WHERE transaction_id = p_transaction_id;

    /*
     * All balance changes occur inside the caller's database transaction.
     * If any operation fails, the caller must roll back the database
     * transaction, including the COMMITTING state and audit records.
     */

    FOR v_operation IN
        SELECT *
        FROM transaction_operations
        WHERE transaction_id = p_transaction_id
        ORDER BY operation_sequence
    LOOP

        IF v_operation.operation_type = 'DEPOSIT' THEN

            UPDATE accounts
            SET balance = balance + v_operation.amount
            WHERE account_id = v_operation.destination_account_id
              AND is_active = TRUE
            RETURNING account_id INTO v_account;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'Deposit account unavailable.';
            END IF;

        ELSIF v_operation.operation_type = 'WITHDRAWAL' THEN

            UPDATE accounts
            SET balance = balance - v_operation.amount
            WHERE account_id = v_operation.source_account_id
              AND is_active = TRUE
              AND balance >= v_operation.amount
            RETURNING balance INTO v_balance;

            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'Withdrawal rejected: insufficient funds or inactive account.';
            END IF;

        ELSIF v_operation.operation_type = 'TRANSFER' THEN

            /*
             * Lock accounts in ascending order to reduce deadlock risk.
             */
            PERFORM account_id
            FROM accounts
            WHERE account_id IN (
                v_operation.source_account_id,
                v_operation.destination_account_id
            )
            ORDER BY account_id
            FOR UPDATE;

            UPDATE accounts
            SET balance = balance - v_operation.amount
            WHERE account_id = v_operation.source_account_id
              AND is_active = TRUE
              AND balance >= v_operation.amount
            RETURNING balance INTO v_source_balance;

            IF NOT FOUND THEN
                RAISE EXCEPTION
                    'Transfer rejected: source account has insufficient funds.';
            END IF;

            UPDATE accounts
            SET balance = balance + v_operation.amount
            WHERE account_id = v_operation.destination_account_id
              AND is_active = TRUE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'Destination account unavailable.';
            END IF;

        END IF;

    END LOOP;

    UPDATE transactions
    SET state = 'COMMITTED',
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = p_transaction_id;

END;
$$;

-- ============================================================================
-- 13. TRANSACTION ROLLBACK PROCEDURE
-- ============================================================================

CREATE PROCEDURE rollback_business_transaction(
    p_transaction_id BIGINT,
    p_reason TEXT DEFAULT 'Business transaction cancelled.'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_state transaction_state;
BEGIN
    SELECT state
    INTO v_state
    FROM transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Transaction does not exist.';
    END IF;

    IF v_state NOT IN ('ACTIVE', 'FAILED') THEN
        RAISE EXCEPTION
            'Cannot roll back transaction in state %',
            v_state;
    END IF;

    UPDATE transactions
    SET state = 'ROLLING_BACK',
        error_message = p_reason
    WHERE transaction_id = p_transaction_id;

    -- Staged operations are retained for audit purposes.

    UPDATE transactions
    SET state = 'ROLLED_BACK',
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = p_transaction_id;

END;
$$;

-- ============================================================================
-- 14. REPORTING VIEWS
-- ============================================================================

CREATE VIEW transaction_status_report AS
SELECT
    t.transaction_id,
    t.transaction_reference,
    t.transaction_type,
    t.state,
    t.initiated_by,
    t.expected_operation_count,
    COUNT(o.operation_id) AS actual_operation_count,
    COALESCE(SUM(o.amount), 0) AS total_operation_value,
    t.started_at,
    t.completed_at,
    t.error_message
FROM transactions t
LEFT JOIN transaction_operations o
    ON o.transaction_id = t.transaction_id
GROUP BY
    t.transaction_id,
    t.transaction_reference,
    t.transaction_type,
    t.state,
    t.initiated_by,
    t.expected_operation_count,
    t.started_at,
    t.completed_at,
    t.error_message;

CREATE VIEW account_balance_report AS
SELECT
    account_id,
    account_number,
    owner_name,
    currency,
    balance,
    version,
    is_active,
    updated_at
FROM accounts;

CREATE VIEW transaction_audit_report AS
SELECT
    t.transaction_id,
    t.initiated_by,
    a.event_type,
    a.previous_state,
    a.current_state,
    a.event_description,
    a.event_timestamp
FROM transaction_audit a
JOIN transactions t
    ON t.transaction_id = a.transaction_id;

-- ============================================================================
-- 15. SAMPLE ACCOUNT DATA
-- ============================================================================

INSERT INTO accounts (
    account_number,
    owner_name,
    currency,
    balance
)
VALUES
    ('ACC-1001', 'Alice Sharma', 'INR', 10000.00),
    ('ACC-1002', 'Bob Verma', 'INR', 5000.00),
    ('ACC-1003', 'Charlie Singh', 'INR', 2500.00),
    ('ACC-1004', 'Enterprise Treasury', 'INR', 100000.00);

COMMIT;

-- ============================================================================
-- 16. SCENARIO A: SUCCESSFUL TRANSACTION
-- ============================================================================

BEGIN;

SET TRANSACTION ISOLATION LEVEL READ COMMITTED;

DO $$
DECLARE
    v_transaction BIGINT;
    v_source BIGINT;
    v_destination BIGINT;
BEGIN
    SELECT account_id INTO v_source
    FROM transaction_lab.accounts
    WHERE account_number = 'ACC-1001';

    SELECT account_id INTO v_destination
    FROM transaction_lab.accounts
    WHERE account_number = 'ACC-1002';

    v_transaction :=
        transaction_lab.begin_business_transaction(
            'TRANSFER',
            'alice.sharma',
            'Monthly payment transfer'
        );

    PERFORM transaction_lab.stage_operation(
        v_transaction,
        'TRANSFER',
        v_source,
        v_destination,
        1500.00
    );

    CALL transaction_lab.commit_business_transaction(
        v_transaction
    );
END;
$$;

COMMIT;

-- ============================================================================
-- 17. SCENARIO B: SAVEPOINT AND PARTIAL ROLLBACK
-- ============================================================================

BEGIN;

DO $$
DECLARE
    v_transaction BIGINT;
    v_account BIGINT;
BEGIN
    SELECT account_id INTO v_account
    FROM transaction_lab.accounts
    WHERE account_number = 'ACC-1001';

    v_transaction :=
        transaction_lab.begin_business_transaction(
            'DEPOSIT',
            'finance.operator',
            'Savepoint demonstration'
        );

    PERFORM transaction_lab.stage_operation(
        v_transaction,
        'DEPOSIT',
        NULL,
        v_account,
        250.00
    );

    INSERT INTO transaction_lab.transaction_savepoints (
        transaction_id,
        savepoint_name,
        operation_sequence
    )
    VALUES (
        v_transaction,
        'BEFORE_SECOND_OPERATION',
        1
    );

    SAVEPOINT before_second_operation;

    PERFORM transaction_lab.stage_operation(
        v_transaction,
        'DEPOSIT',
        NULL,
        v_account,
        500.00
    );

    -- Undo the second staged operation.
    ROLLBACK TO SAVEPOINT before_second_operation;

    DELETE FROM transaction_lab.transaction_operations
    WHERE transaction_id = v_transaction
      AND operation_sequence > 1;

    UPDATE transaction_lab.transactions
    SET expected_operation_count = 1
    WHERE transaction_id = v_transaction;

    CALL transaction_lab.commit_business_transaction(
        v_transaction
    );
END;
$$;

COMMIT;

-- ============================================================================
-- 18. SCENARIO C: FULL DATABASE ROLLBACK
-- ============================================================================

BEGIN;

DO $$
DECLARE
    v_transaction BIGINT;
    v_account BIGINT;
BEGIN
    SELECT account_id INTO v_account
    FROM transaction_lab.accounts
    WHERE account_number = 'ACC-1002';

    v_transaction :=
        transaction_lab.begin_business_transaction(
            'WITHDRAWAL',
            'cashier.user',
            'Transaction intentionally cancelled'
        );

    PERFORM transaction_lab.stage_operation(
        v_transaction,
        'WITHDRAWAL',
        v_account,
        NULL,
        100.00
    );

    -- The business transaction is rolled back before publication.
    CALL transaction_lab.rollback_business_transaction(
        v_transaction,
        'Customer cancelled request.'
    );
END;
$$;

COMMIT;

-- ============================================================================
-- 19. SCENARIO D: FAILED OPERATION AND ROLLBACK
-- ============================================================================

BEGIN;

DO $$
DECLARE
    v_transaction BIGINT;
    v_account BIGINT;
BEGIN
    SELECT account_id INTO v_account
    FROM transaction_lab.accounts
    WHERE account_number = 'ACC-1002';

    v_transaction :=
        transaction_lab.begin_business_transaction(
            'WITHDRAWAL',
            'risk.control',
            'Insufficient funds test'
        );

    PERFORM transaction_lab.stage_operation(
        v_transaction,
        'WITHDRAWAL',
        v_account,
        NULL,
        999999.00
    );

    CALL transaction_lab.commit_business_transaction(
        v_transaction
    );

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Expected transaction failure: %', SQLERRM;
        -- Re-raise so the outer SQL transaction is rolled back.
        RAISE;
END;
$$;

-- The preceding statement is expected to fail when executed independently.
-- Execute this scenario inside a client-managed transaction and issue
-- ROLLBACK after the exception.

ROLLBACK;

-- ============================================================================
-- 20. SCENARIO E: EXPLICIT DATABASE ROLLBACK
-- ============================================================================

BEGIN;

UPDATE transaction_lab.accounts
SET balance = balance + 1000.00
WHERE account_number = 'ACC-1001';

-- No balance change becomes durable.
ROLLBACK;

-- ============================================================================
-- 21. TRANSACTION STATE REPORTING
-- ============================================================================

SELECT
    transaction_id,
    transaction_type,
    state,
    initiated_by,
    expected_operation_count,
    actual_operation_count,
    total_operation_value,
    started_at,
    completed_at
FROM transaction_lab.transaction_status_report
ORDER BY transaction_id;

-- ============================================================================
-- 22. ACCOUNT BALANCE REPORTING
-- ============================================================================

SELECT
    account_number,
    owner_name,
    currency,
    balance,
    version,
    is_active
FROM transaction_lab.account_balance_report
ORDER BY account_number;

-- ============================================================================
-- 23. AUDIT HISTORY
-- ============================================================================

SELECT
    transaction_id,
    initiated_by,
    event_type,
    previous_state,
    current_state,
    event_description,
    event_timestamp
FROM transaction_lab.transaction_audit_report
ORDER BY transaction_id, event_timestamp, audit_id;

-- ============================================================================
-- 24. TRANSACTION AGGREGATION
-- ============================================================================

SELECT
    state,
    COUNT(*) AS transaction_count,
    SUM(expected_operation_count) AS total_expected_operations
FROM transaction_lab.transactions
GROUP BY state
ORDER BY state;

-- ============================================================================
-- 25. OPERATION VALUE ANALYSIS
-- ============================================================================

SELECT
    operation_type,
    COUNT(*) AS operation_count,
    SUM(amount) AS total_value,
    AVG(amount) AS average_value,
    MIN(amount) AS minimum_value,
    MAX(amount) AS maximum_value
FROM transaction_lab.transaction_operations
GROUP BY operation_type
ORDER BY operation_type;

-- ============================================================================
-- 26. ACCOUNT ACTIVITY ANALYSIS
-- ============================================================================

WITH account_activity AS (
    SELECT
        source_account_id AS account_id,
        -amount AS signed_amount
    FROM transaction_lab.transaction_operations
    WHERE source_account_id IS NOT NULL

    UNION ALL

    SELECT
        destination_account_id AS account_id,
        amount AS signed_amount
    FROM transaction_lab.transaction_operations
    WHERE destination_account_id IS NOT NULL
)
SELECT
    a.account_number,
    a.owner_name,
    COUNT(activity.account_id) AS operation_count,
    COALESCE(SUM(activity.signed_amount), 0) AS net_staged_movement
FROM transaction_lab.accounts a
LEFT JOIN account_activity activity
    ON activity.account_id = a.account_id
GROUP BY a.account_id, a.account_number, a.owner_name
ORDER BY a.account_number;

-- ============================================================================
-- 27. TRANSACTION INTEGRITY VALIDATION
-- ============================================================================

SELECT
    t.transaction_id,
    t.state,
    t.expected_operation_count,
    COUNT(o.operation_id) AS actual_operation_count,
    CASE
        WHEN t.expected_operation_count = COUNT(o.operation_id)
        THEN 'COUNT_MATCH'
        ELSE 'COUNT_MISMATCH'
    END AS validation_result
FROM transaction_lab.transactions t
LEFT JOIN transaction_lab.transaction_operations o
    ON o.transaction_id = t.transaction_id
GROUP BY
    t.transaction_id,
    t.state,
    t.expected_operation_count
ORDER BY t.transaction_id;

-- ============================================================================
-- 28. INCOMPLETE TRANSACTION MONITORING
-- ============================================================================

SELECT
    transaction_id,
    transaction_reference,
    initiated_by,
    state,
    started_at,
    CURRENT_TIMESTAMP - started_at AS elapsed_time
FROM transaction_lab.transactions
WHERE state IN (
    'NEW',
    'ACTIVE',
    'COMMITTING',
    'ROLLING_BACK',
    'FAILED'
)
ORDER BY started_at;

-- ============================================================================
-- 29. DAILY TRANSACTION REPORT
-- ============================================================================

SELECT
    DATE(created_at) AS transaction_date,
    transaction_type,
    state,
    COUNT(*) AS transaction_count
FROM transaction_lab.transactions
GROUP BY
    DATE(created_at),
    transaction_type,
    state
ORDER BY transaction_date DESC, transaction_type, state;

-- ============================================================================
-- 30. EXPLICIT ISOLATION LEVEL DEMONSTRATION
-- ============================================================================

-- READ COMMITTED:
-- Each statement can observe newly committed data.

BEGIN ISOLATION LEVEL READ COMMITTED;

SELECT
    account_number,
    balance
FROM transaction_lab.accounts
WHERE account_number = 'ACC-1001';

COMMIT;

-- REPEATABLE READ:
-- The transaction retains a consistent snapshot for its reads.

BEGIN ISOLATION LEVEL REPEATABLE READ;

SELECT
    account_number,
    balance
FROM transaction_lab.accounts
WHERE account_number = 'ACC-1001';

COMMIT;

-- SERIALIZABLE:
-- PostgreSQL may reject a transaction with a serialization failure.
-- Applications must retry the entire transaction when appropriate.

BEGIN ISOLATION LEVEL SERIALIZABLE;

SELECT
    SUM(balance) AS total_account_balance
FROM transaction_lab.accounts
WHERE is_active = TRUE;

COMMIT;

-- ============================================================================
-- 31. OPERATIONAL NOTES
-- ============================================================================

/*
1. A database transaction is not the same as the business transaction row.

2. The SQL transaction provides actual atomicity and durability.

3. The business transaction state records the workflow status.

4. A successful COMMIT makes database modifications durable.

5. ROLLBACK discards all changes made within the current SQL transaction.

6. ROLLBACK TO SAVEPOINT preserves work performed before that savepoint.

7. A failed SQL statement can leave a transaction in the aborted state.
   Issue ROLLBACK or ROLLBACK TO SAVEPOINT before continuing.

8. The sample business commit procedure is intended to run inside a
   caller-managed SQL transaction.

9. The business commit procedure does not commit the surrounding SQL
   transaction itself. The application must issue COMMIT after success.

10. For production use, restrict execution privileges on transaction
    procedures and audit tables.

11. Use SERIALIZABLE or explicit row locking where business invariants
    require stronger concurrency guarantees.

12. External API calls, email delivery, and message publication cannot
    be rolled back by PostgreSQL. Use an outbox pattern for reliable
    integration with external systems.

13. Idempotency keys should be added for payment APIs to prevent
    duplicate processing after retries.

14. A database transaction is atomic only within its participating
    database transaction boundary. Distributed transactions require
    separate coordination mechanisms.
*/

SELECT 'TRANSACTION LIFECYCLE DEMONSTRATION COMPLETED' AS execution_status;
