/*
 * ACID FUNDAMENTALS
 * PostgreSQL Transaction Management Laboratory
 *
 * Demonstrates:
 * A - Atomicity
 * C - Consistency
 * I - Isolation
 * D - Durability
 *
 * PostgreSQL 15+
 *
 * Includes:
 * - Relational banking model
 * - Account constraints
 * - Transaction ledger
 * - Immutable transaction records
 * - Audit history
 * - Idempotency
 * - Transaction procedures
 * - Row locking
 * - Optimistic version validation
 * - Isolation-level demonstrations
 * - Reporting and integrity checks
 *
 * Run against a database where the executing role can create schemas.
 */

BEGIN;

CREATE SCHEMA IF NOT EXISTS acid_lab;

SET LOCAL search_path TO acid_lab, public;

CREATE TABLE IF NOT EXISTS accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    owner_name VARCHAR(120) NOT NULL,

    account_type VARCHAR(20) NOT NULL
        CHECK (
            account_type IN (
                'CURRENT',
                'SAVINGS',
                'CORPORATE'
            )
        ),

    balance NUMERIC(18, 2) NOT NULL DEFAULT 0.00
        CHECK (balance >= 0),

    version BIGINT NOT NULL DEFAULT 0
        CHECK (version >= 0),

    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_account_owner_type
        UNIQUE (owner_name, account_type)
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    source_account BIGINT NOT NULL
        REFERENCES accounts(account_id),

    destination_account BIGINT NOT NULL
        REFERENCES accounts(account_id),

    amount NUMERIC(18, 2) NOT NULL
        CHECK (amount > 0),

    status VARCHAR(20) NOT NULL
        CHECK (
            status IN (
                'COMMITTED',
                'REVERSED'
            )
        ),

    idempotency_key VARCHAR(150) UNIQUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (source_account <> destination_account)
);

CREATE TABLE IF NOT EXISTS transaction_ledger (
    ledger_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id UUID NOT NULL
        REFERENCES transactions(transaction_id),

    account_id BIGINT NOT NULL
        REFERENCES accounts(account_id),

    entry_type VARCHAR(10) NOT NULL
        CHECK (entry_type IN ('DEBIT', 'CREDIT')),

    amount NUMERIC(18, 2) NOT NULL
        CHECK (amount > 0),

    balance_after NUMERIC(18, 2) NOT NULL
        CHECK (balance_after >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (transaction_id, account_id, entry_type)
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id UUID,

    event_type VARCHAR(40) NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transaction_requests (
    idempotency_key VARCHAR(150) PRIMARY KEY,

    transaction_id UUID NOT NULL UNIQUE
        REFERENCES transactions(transaction_id),

    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_source
    ON transactions(source_account, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_destination
    ON transactions(destination_account, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ledger_account_time
    ON transaction_ledger(account_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_event_time
    ON audit_log(event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_accounts_active
    ON accounts(account_id)
    WHERE active = TRUE;

COMMIT;


/*
 * CONSISTENCY ENFORCEMENT
 *
 * Prevents updates to transaction history after insertion.
 * Account balances remain mutable because they represent current state.
 */

CREATE OR REPLACE FUNCTION acid_lab.prevent_transaction_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'Transaction history is immutable. Use a compensating transaction.';
END;
$$;

DROP TRIGGER IF EXISTS trg_immutable_transactions
    ON acid_lab.transactions;

CREATE TRIGGER trg_immutable_transactions
BEFORE UPDATE OR DELETE ON acid_lab.transactions
FOR EACH ROW
EXECUTE FUNCTION acid_lab.prevent_transaction_mutation();


CREATE OR REPLACE FUNCTION acid_lab.prevent_ledger_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'Ledger entries cannot be modified or deleted.';
END;
$$;

DROP TRIGGER IF EXISTS trg_immutable_ledger
    ON acid_lab.transaction_ledger;

CREATE TRIGGER trg_immutable_ledger
BEFORE UPDATE OR DELETE ON acid_lab.transaction_ledger
FOR EACH ROW
EXECUTE FUNCTION acid_lab.prevent_ledger_mutation();


/*
 * DATABASE AUDIT FUNCTION
 */

CREATE OR REPLACE FUNCTION acid_lab.write_audit(
    p_transaction_id UUID,
    p_event_type VARCHAR,
    p_details JSONB
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO acid_lab.audit_log(
        transaction_id,
        event_type,
        details
    )
    VALUES (
        p_transaction_id,
        p_event_type,
        COALESCE(p_details, '{}'::jsonb)
    );
END;
$$;


/*
 * TRANSFER PROCEDURE
 *
 * Atomicity:
 * Both account updates, transaction record, ledger records and audit
 * entry belong to the caller's database transaction.
 *
 * Consistency:
 * Positive amount, valid accounts, active accounts and nonnegative
 * balances are enforced.
 *
 * Isolation:
 * SELECT FOR UPDATE locks both account rows in ascending ID order.
 *
 * Durability:
 * COMMIT by the caller persists the transaction according to the
 * PostgreSQL durability configuration.
 *
 * IMPORTANT:
 * This procedure does not issue COMMIT. The caller controls the
 * transaction boundary.
 */

CREATE OR REPLACE PROCEDURE acid_lab.transfer_funds(
    IN p_source BIGINT,
    IN p_destination BIGINT,
    IN p_amount NUMERIC(18, 2),
    IN p_idempotency_key VARCHAR(150),
    INOUT p_transaction_id UUID DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_source_balance NUMERIC(18, 2);
    v_destination_balance NUMERIC(18, 2);
    v_source_active BOOLEAN;
    v_destination_active BOOLEAN;
    v_existing UUID;
BEGIN
    IF p_source = p_destination THEN
        RAISE EXCEPTION
            'Source and destination accounts must differ.';
    END IF;

    IF p_amount IS NULL OR p_amount <= 0 THEN
        RAISE EXCEPTION
            'Transfer amount must be positive.';
    END IF;

    IF p_amount <> ROUND(p_amount, 2) THEN
        RAISE EXCEPTION
            'Amount must have at most two decimal places.';
    END IF;

    IF p_idempotency_key IS NULL
       OR LENGTH(TRIM(p_idempotency_key)) = 0 THEN
        RAISE EXCEPTION
            'Idempotency key is required.';
    END IF;

    /*
     * A transaction-scoped advisory lock serializes requests
     * sharing the same idempotency key.
     */
    PERFORM pg_advisory_xact_lock(
        hashtextextended(p_idempotency_key, 0)
    );

    SELECT transaction_id
    INTO v_existing
    FROM acid_lab.transaction_requests
    WHERE idempotency_key = p_idempotency_key;

    IF FOUND THEN
        p_transaction_id := v_existing;

        RAISE EXCEPTION
            'Duplicate request. Existing transaction: %',
            v_existing
            USING ERRCODE = '23505';
    END IF;

    /*
     * Lock rows in a deterministic order to reduce deadlocks.
     */

    PERFORM account_id
    FROM acid_lab.accounts
    WHERE account_id IN (p_source, p_destination)
    ORDER BY account_id
    FOR UPDATE;

    SELECT balance, active
    INTO v_source_balance, v_source_active
    FROM acid_lab.accounts
    WHERE account_id = p_source;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Source account % does not exist.',
            p_source;
    END IF;

    SELECT balance, active
    INTO v_destination_balance, v_destination_active
    FROM acid_lab.accounts
    WHERE account_id = p_destination;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Destination account % does not exist.',
            p_destination;
    END IF;

    IF NOT v_source_active OR NOT v_destination_active THEN
        RAISE EXCEPTION
            'Both accounts must be active.';
    END IF;

    IF v_source_balance < p_amount THEN
        RAISE EXCEPTION
            'Insufficient funds. Available: %, requested: %',
            v_source_balance,
            p_amount
            USING ERRCODE = '23514';
    END IF;

    UPDATE acid_lab.accounts
    SET balance = balance - p_amount,
        version = version + 1
    WHERE account_id = p_source;

    UPDATE acid_lab.accounts
    SET balance = balance + p_amount,
        version = version + 1
    WHERE account_id = p_destination;

    p_transaction_id := gen_random_uuid();

    INSERT INTO acid_lab.transactions(
        transaction_id,
        source_account,
        destination_account,
        amount,
        status,
        idempotency_key
    )
    VALUES (
        p_transaction_id,
        p_source,
        p_destination,
        p_amount,
        'COMMITTED',
        p_idempotency_key
    );

    INSERT INTO acid_lab.transaction_requests(
        idempotency_key,
        transaction_id
    )
    VALUES (
        p_idempotency_key,
        p_transaction_id
    );

    INSERT INTO acid_lab.transaction_ledger(
        transaction_id,
        account_id,
        entry_type,
        amount,
        balance_after
    )
    VALUES
    (
        p_transaction_id,
        p_source,
        'DEBIT',
        p_amount,
        v_source_balance - p_amount
    ),
    (
        p_transaction_id,
        p_destination,
        'CREDIT',
        p_amount,
        v_destination_balance + p_amount
    );

    PERFORM acid_lab.write_audit(
        p_transaction_id,
        'TRANSFER_CREATED',
        jsonb_build_object(
            'source', p_source,
            'destination', p_destination,
            'amount', p_amount,
            'idempotency_key', p_idempotency_key
        )
    );

END;
$$;


/*
 * OPTIMISTIC CONCURRENCY CONTROL
 *
 * An application can update a record only if its previously
 * observed version is still current.
 */

CREATE OR REPLACE FUNCTION acid_lab.update_balance_optimistically(
    p_account_id BIGINT,
    p_expected_version BIGINT,
    p_new_balance NUMERIC(18, 2)
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    IF p_new_balance < 0 THEN
        RAISE EXCEPTION 'Balance cannot be negative.';
    END IF;

    UPDATE acid_lab.accounts
    SET balance = p_new_balance,
        version = version + 1
    WHERE account_id = p_account_id
      AND version = p_expected_version
      AND active = TRUE;

    GET DIAGNOSTICS v_updated = ROW_COUNT;

    IF v_updated = 0 THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$;


/*
 * REPORTING VIEW
 */

CREATE OR REPLACE VIEW acid_lab.account_transaction_summary AS
SELECT
    a.account_id,
    a.owner_name,
    a.account_type,
    a.balance,
    a.version,
    COUNT(DISTINCT t.transaction_id) AS transaction_count,
    COALESCE(
        SUM(
            CASE
                WHEN l.entry_type = 'DEBIT'
                THEN l.amount
                ELSE 0
            END
        ),
        0
    ) AS total_debits,
    COALESCE(
        SUM(
            CASE
                WHEN l.entry_type = 'CREDIT'
                THEN l.amount
                ELSE 0
            END
        ),
        0
    ) AS total_credits
FROM acid_lab.accounts a
LEFT JOIN acid_lab.transaction_ledger l
    ON l.account_id = a.account_id
LEFT JOIN acid_lab.transactions t
    ON t.transaction_id = l.transaction_id
GROUP BY
    a.account_id,
    a.owner_name,
    a.account_type,
    a.balance,
    a.version;


/*
 * SAMPLE DATA
 */

INSERT INTO acid_lab.accounts(
    owner_name,
    account_type,
    balance
)
VALUES
    ('Corporate Treasury', 'CORPORATE', 10000.00),
    ('Research Department', 'CORPORATE', 2500.00),
    ('Operations Department', 'CURRENT', 5000.00),
    ('Employee Savings', 'SAVINGS', 1500.00)
ON CONFLICT (owner_name, account_type)
DO NOTHING;


/*
 * SUCCESSFUL ATOMIC TRANSFER
 */

BEGIN;

CALL acid_lab.transfer_funds(
    1,
    2,
    500.00,
    'ACID-DEMO-001',
    NULL
);

COMMIT;


/*
 * CONSISTENCY VALIDATION
 *
 * The following queries report the state after the committed transfer.
 */

SELECT
    account_id,
    owner_name,
    balance,
    version
FROM acid_lab.accounts
ORDER BY account_id;

SELECT
    transaction_id,
    source_account,
    destination_account,
    amount,
    status,
    created_at
FROM acid_lab.transactions
ORDER BY created_at DESC;

SELECT
    transaction_id,
    account_id,
    entry_type,
    amount,
    balance_after
FROM acid_lab.transaction_ledger
ORDER BY ledger_id;


/*
 * ATOMICITY DEMONSTRATION
 *
 * The debit and credit are both rolled back when the transaction
 * is deliberately aborted.
 */

BEGIN;

UPDATE acid_lab.accounts
SET balance = balance - 100.00,
    version = version + 1
WHERE account_id = 1
  AND balance >= 100.00;

UPDATE acid_lab.accounts
SET balance = balance + 100.00,
    version = version + 1
WHERE account_id = 2;

ROLLBACK;


/*
 * CONSTRAINT FAILURE DEMONSTRATION
 *
 * This block catches the intentional constraint violation.
 * The failed statement does not leave a negative balance.
 */

DO $$
BEGIN
    BEGIN
        UPDATE acid_lab.accounts
        SET balance = -100.00
        WHERE account_id = 1;

    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE
                'Consistency enforced: negative balance rejected.';
    END;
END;
$$;


/*
 * IDEMPOTENCY VALIDATION
 *
 * Reusing ACID-DEMO-001 is rejected.
 */

DO $$
BEGIN
    BEGIN
        CALL acid_lab.transfer_funds(
            1,
            2,
            100.00,
            'ACID-DEMO-001',
            NULL
        );

    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE
                'Duplicate request rejected.';
    END;
END;
$$;


/*
 * OPTIMISTIC CONCURRENCY DEMONSTRATION
 */

DO $$
DECLARE
    v_version BIGINT;
    v_result BOOLEAN;
BEGIN
    SELECT version
    INTO v_version
    FROM acid_lab.accounts
    WHERE account_id = 3;

    v_result :=
        acid_lab.update_balance_optimistically(
            3,
            v_version,
            5100.00
        );

    RAISE NOTICE
        'First update accepted: %',
        v_result;

    v_result :=
        acid_lab.update_balance_optimistically(
            3,
            v_version,
            5200.00
        );

    RAISE NOTICE
        'Stale update accepted: %',
        v_result;

    IF v_result THEN
        RAISE EXCEPTION
            'Optimistic concurrency validation failed.';
    END IF;
END;
$$;


/*
 * ISOLATION TESTING
 *
 * Run the following transaction in a separate database session
 * to observe concurrent row-lock behavior.
 *
 * Session A:
 *
 * BEGIN;
 * SELECT * FROM acid_lab.accounts
 * WHERE account_id = 1
 * FOR UPDATE;
 * SELECT pg_sleep(10);
 * COMMIT;
 *
 * Session B:
 *
 * BEGIN;
 * UPDATE acid_lab.accounts
 * SET balance = balance + 10
 * WHERE account_id = 1;
 * COMMIT;
 *
 * Session B waits until Session A releases its row lock.
 *
 * SERIALIZABLE transactions may instead fail with SQLSTATE 40001.
 * Applications should retry the complete transaction when safe.
 */


/*
 * AGGREGATION AND REPORTING
 */

SELECT *
FROM acid_lab.account_transaction_summary
ORDER BY account_id;


/*
 * TRANSACTION ACTIVITY REPORT
 */

SELECT
    t.transaction_id,
    source.owner_name AS source_owner,
    destination.owner_name AS destination_owner,
    t.amount,
    t.status,
    t.created_at
FROM acid_lab.transactions t
JOIN acid_lab.accounts source
    ON source.account_id = t.source_account
JOIN acid_lab.accounts destination
    ON destination.account_id = t.destination_account
ORDER BY t.created_at DESC;


/*
 * LEDGER BALANCING VALIDATION
 *
 * Every committed transfer must contain one debit and one credit
 * of equal value.
 */

WITH ledger_validation AS (
    SELECT
        transaction_id,
        COUNT(*) AS entry_count,
        SUM(
            CASE
                WHEN entry_type = 'DEBIT'
                THEN amount
                ELSE 0
            END
        ) AS debits,
        SUM(
            CASE
                WHEN entry_type = 'CREDIT'
                THEN amount
                ELSE 0
            END
        ) AS credits
    FROM acid_lab.transaction_ledger
    GROUP BY transaction_id
)
SELECT
    transaction_id,
    entry_count,
    debits,
    credits,
    (
        entry_count = 2
        AND debits = credits
    ) AS balanced
FROM ledger_validation;


/*
 * CONSISTENCY CHECK: ACCOUNT BALANCES
 */

SELECT
    account_id,
    owner_name,
    balance,
    balance >= 0 AS valid_balance,
    version >= 0 AS valid_version
FROM acid_lab.accounts;


/*
 * AUDIT REPORT
 */

SELECT
    audit_id,
    transaction_id,
    event_type,
    details,
    created_at
FROM acid_lab.audit_log
ORDER BY audit_id;


/*
 * TOTAL ASSETS
 */

SELECT
    SUM(balance) AS total_account_balance
FROM acid_lab.accounts;


/*
 * TRANSACTION ELIGIBILITY REPORT
 */

SELECT
    a.account_id,
    a.owner_name,
    a.active,
    a.balance,
    CASE
        WHEN NOT a.active
            THEN 'INACTIVE'
        WHEN a.balance <= 0
            THEN 'INSUFFICIENT_BALANCE'
        ELSE 'ELIGIBLE_FOR_TRANSFER'
    END AS transfer_eligibility
FROM acid_lab.accounts a
ORDER BY a.account_id;


/*
 * DURABILITY CONFIGURATION INSPECTION
 *
 * These values affect the durability guarantees and should be
 * evaluated against the deployment's failure model.
 */

SHOW fsync;
SHOW synchronous_commit;
SHOW full_page_writes;
SHOW wal_level;


/*
 * ACID IMPLEMENTATION NOTES
 *
 * PostgreSQL WAL supports crash recovery.
 * COMMIT establishes the transaction boundary.
 * Row-level locks coordinate conflicting writes.
 * MVCC provides consistent snapshots.
 * Constraints protect relational invariants.
 * SERIALIZABLE isolation detects serialization anomalies.
 *
 * Database administrators should use appropriate privileges,
 * backup policies, WAL archiving and replication configuration.
 */
