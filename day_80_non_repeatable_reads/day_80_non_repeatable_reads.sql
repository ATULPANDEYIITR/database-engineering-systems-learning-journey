/*
===============================================================================
NON-REPEATABLE READS
Concurrency Behavior and Transaction Isolation
PostgreSQL 14+

This script creates:
- A transaction management schema.
- Accounts and transaction records.
- Version tracking.
- Atomic transfer processing.
- Transaction audit records.
- Isolation experiment data.
- Reporting and validation views.
- Concurrency demonstrations for separate PostgreSQL sessions.

IMPORTANT:
PostgreSQL READ UNCOMMITTED behaves as READ COMMITTED.
PostgreSQL REPEATABLE READ uses snapshot isolation.
PostgreSQL SERIALIZABLE uses Serializable Snapshot Isolation (SSI).

A single SQL session cannot reproduce genuine concurrent execution.
The concurrent experiments are therefore provided as separate-session
instructions following the executable database setup.
===============================================================================
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS concurrency_lab;

SET search_path TO concurrency_lab, public;

DROP VIEW IF EXISTS account_balance_report CASCADE;
DROP VIEW IF EXISTS transaction_summary CASCADE;
DROP TABLE IF EXISTS transaction_audit CASCADE;
DROP TABLE IF EXISTS account_transactions CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;

CREATE TABLE accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_name VARCHAR(100) NOT NULL,
    balance NUMERIC(15, 2) NOT NULL DEFAULT 0,
    version BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT account_name_unique UNIQUE (account_name),
    CONSTRAINT account_balance_nonnegative CHECK (balance >= 0),
    CONSTRAINT account_version_positive CHECK (version > 0)
);

CREATE TABLE account_transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_account_id BIGINT NOT NULL REFERENCES accounts(account_id),
    target_account_id BIGINT NOT NULL REFERENCES accounts(account_id),
    amount NUMERIC(15, 2) NOT NULL,
    transaction_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT transfer_positive CHECK (amount > 0),
    CONSTRAINT transfer_distinct_accounts
        CHECK (source_account_id <> target_account_id),
    CONSTRAINT transaction_status_valid
        CHECK (
            transaction_status IN (
                'PENDING',
                'COMPLETED',
                'FAILED'
            )
        )
);

CREATE TABLE transaction_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id BIGINT REFERENCES account_transactions(transaction_id),
    account_id BIGINT NOT NULL REFERENCES accounts(account_id),
    old_balance NUMERIC(15, 2),
    new_balance NUMERIC(15, 2),
    old_version BIGINT,
    new_version BIGINT,
    operation VARCHAR(30) NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transactions_source
    ON account_transactions(source_account_id, created_at DESC);

CREATE INDEX idx_transactions_target
    ON account_transactions(target_account_id, created_at DESC);

CREATE INDEX idx_transactions_status
    ON account_transactions(transaction_status, created_at DESC);

CREATE INDEX idx_audit_account
    ON transaction_audit(account_id, changed_at DESC);

INSERT INTO accounts(account_name, balance)
VALUES
    ('OPERATIONS', 10000.00),
    ('ENGINEERING', 15000.00),
    ('RESEARCH', 20000.00),
    ('SECURITY', 5000.00);

COMMIT;


/*
===============================================================================
1. AUTOMATIC ACCOUNT CHANGE AUDIT
===============================================================================
*/

CREATE OR REPLACE FUNCTION audit_account_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = concurrency_lab, pg_temp
AS $$
BEGIN
    IF NEW.balance IS DISTINCT FROM OLD.balance THEN
        NEW.version := OLD.version + 1;
        NEW.updated_at := CURRENT_TIMESTAMP;

        INSERT INTO transaction_audit (
            account_id,
            old_balance,
            new_balance,
            old_version,
            new_version,
            operation
        )
        VALUES (
            OLD.account_id,
            OLD.balance,
            NEW.balance,
            OLD.version,
            NEW.version,
            TG_OP
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_account_audit
BEFORE UPDATE ON accounts
FOR EACH ROW
EXECUTE FUNCTION audit_account_change();


/*
===============================================================================
2. ATOMIC MONEY TRANSFER
===============================================================================
The two account rows are locked in ascending ID order to reduce deadlocks.
Both changes succeed or neither change is committed.
===============================================================================
*/

CREATE OR REPLACE PROCEDURE transfer_funds(
    p_source BIGINT,
    p_target BIGINT,
    p_amount NUMERIC
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_source_balance NUMERIC(15, 2);
    v_target_balance NUMERIC(15, 2);
    v_transaction_id BIGINT;
BEGIN
    IF p_source = p_target THEN
        RAISE EXCEPTION 'Source and target must differ';
    END IF;

    IF p_amount IS NULL OR p_amount <= 0 THEN
        RAISE EXCEPTION 'Transfer amount must be positive';
    END IF;

    INSERT INTO account_transactions (
        source_account_id,
        target_account_id,
        amount
    )
    VALUES (
        p_source,
        p_target,
        p_amount
    )
    RETURNING transaction_id INTO v_transaction_id;

    -- Lock accounts in a consistent order.
    PERFORM account_id
    FROM accounts
    WHERE account_id IN (p_source, p_target)
    ORDER BY account_id
    FOR UPDATE;

    IF (
        SELECT COUNT(*)
        FROM accounts
        WHERE account_id IN (p_source, p_target)
    ) <> 2 THEN
        RAISE EXCEPTION 'Source or target account does not exist';
    END IF;

    SELECT balance
    INTO v_source_balance
    FROM accounts
    WHERE account_id = p_source;

    SELECT balance
    INTO v_target_balance
    FROM accounts
    WHERE account_id = p_target;

    IF v_source_balance < p_amount THEN
        UPDATE account_transactions
        SET transaction_status = 'FAILED'
        WHERE transaction_id = v_transaction_id;

        RAISE EXCEPTION 'Insufficient funds';
    END IF;

    UPDATE accounts
    SET balance = balance - p_amount
    WHERE account_id = p_source;

    UPDATE accounts
    SET balance = balance + p_amount
    WHERE account_id = p_target;

    UPDATE account_transactions
    SET transaction_status = 'COMPLETED'
    WHERE transaction_id = v_transaction_id;

    RAISE NOTICE 'Transfer % completed', v_transaction_id;
END;
$$;


/*
===============================================================================
3. ACCOUNT REPORTING VIEWS
===============================================================================
*/

CREATE OR REPLACE VIEW account_balance_report AS
SELECT
    account_id,
    account_name,
    balance,
    version,
    updated_at
FROM accounts;

CREATE OR REPLACE VIEW transaction_summary AS
SELECT
    COUNT(*) AS total_transactions,
    COUNT(*) FILTER (
        WHERE transaction_status = 'COMPLETED'
    ) AS completed_transactions,
    COUNT(*) FILTER (
        WHERE transaction_status = 'FAILED'
    ) AS failed_transactions,
    COALESCE(
        SUM(amount) FILTER (
            WHERE transaction_status = 'COMPLETED'
        ),
        0
    ) AS completed_amount
FROM account_transactions;


/*
===============================================================================
4. BASIC RETRIEVAL AND VALIDATION
===============================================================================
*/

SELECT *
FROM account_balance_report
ORDER BY account_id;

SELECT *
FROM transaction_summary;

-- Detect invalid negative balances.
SELECT account_id, account_name, balance
FROM accounts
WHERE balance < 0;

-- Identify accounts with the greatest number of audited modifications.
SELECT
    account_id,
    COUNT(*) AS modification_count
FROM transaction_audit
GROUP BY account_id
ORDER BY modification_count DESC;


/*
===============================================================================
5. COMMITTED TRANSACTION DEMONSTRATION
===============================================================================
*/

BEGIN;

CALL transfer_funds(1, 2, 100.00);

COMMIT;

SELECT *
FROM account_balance_report
ORDER BY account_id;

SELECT *
FROM transaction_audit
ORDER BY audit_id;


/*
===============================================================================
6. COMMON TABLE EXPRESSION: TRANSACTION EVALUATION
===============================================================================
*/

WITH transaction_metrics AS (
    SELECT
        source_account_id AS account_id,
        SUM(amount) AS total_outgoing,
        COUNT(*) AS outgoing_count
    FROM account_transactions
    WHERE transaction_status = 'COMPLETED'
    GROUP BY source_account_id

    UNION ALL

    SELECT
        target_account_id,
        -SUM(amount),
        COUNT(*)
    FROM account_transactions
    WHERE transaction_status = 'COMPLETED'
    GROUP BY target_account_id
),
account_activity AS (
    SELECT
        account_id,
        SUM(total_outgoing) AS net_outgoing,
        SUM(outgoing_count) AS transaction_count
    FROM transaction_metrics
    GROUP BY account_id
)
SELECT
    a.account_name,
    a.balance,
    COALESCE(x.net_outgoing, 0) AS net_outgoing,
    COALESCE(x.transaction_count, 0) AS transaction_count
FROM accounts a
LEFT JOIN account_activity x
    ON a.account_id = x.account_id
ORDER BY a.account_id;


/*
===============================================================================
7. NON-REPEATABLE READ EXPERIMENT
===============================================================================

Use TWO independent psql sessions.

SESSION A
---------

BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED;

SELECT balance
FROM concurrency_lab.accounts
WHERE account_id = 1;

-- Leave the transaction open.

SESSION B
---------

BEGIN;

UPDATE concurrency_lab.accounts
SET balance = balance + 500
WHERE account_id = 1;

COMMIT;

SESSION A
---------

SELECT balance
FROM concurrency_lab.accounts
WHERE account_id = 1;

COMMIT;

Expected behavior:
The second SELECT in Session A can return a different balance.

Reason:
READ COMMITTED obtains a fresh committed snapshot for each statement.
The first SELECT does not permanently fix the transaction's row version.


===============================================================================
8. REPEATABLE READ EXPERIMENT
===============================================================================

SESSION A
---------

BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;

SELECT balance
FROM concurrency_lab.accounts
WHERE account_id = 1;

-- Leave transaction open.

SESSION B
---------

BEGIN;

UPDATE concurrency_lab.accounts
SET balance = balance + 700
WHERE account_id = 1;

COMMIT;

SESSION A
---------

SELECT balance
FROM concurrency_lab.accounts
WHERE account_id = 1;

COMMIT;

Expected behavior:
Session A sees its original snapshot in both SELECT statements.

A transaction attempting to update a row changed after its snapshot
was established can receive SQLSTATE 40001.


===============================================================================
9. REPEATABLE READ WRITE-WRITE CONFLICT
===============================================================================

SESSION A
---------

BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;

SELECT balance
FROM concurrency_lab.accounts
WHERE account_id = 1;

SESSION B
---------

BEGIN;

UPDATE concurrency_lab.accounts
SET balance = balance + 100
WHERE account_id = 1;

COMMIT;

SESSION A
---------

UPDATE concurrency_lab.accounts
SET balance = balance + 200
WHERE account_id = 1;

-- PostgreSQL can reject this update with SQLSTATE 40001.

ROLLBACK;


===============================================================================
10. SERIALIZABLE ISOLATION EXPERIMENT
===============================================================================

SESSION A
---------

BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;

SELECT SUM(balance)
FROM concurrency_lab.accounts;

-- Leave transaction open.

SESSION B
---------

BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;

SELECT SUM(balance)
FROM concurrency_lab.accounts;

UPDATE concurrency_lab.accounts
SET balance = balance - 100
WHERE account_id = 1;

COMMIT;

SESSION A
---------

UPDATE concurrency_lab.accounts
SET balance = balance - 100
WHERE account_id = 2;

COMMIT;

Depending on the interleaving, PostgreSQL may reject a transaction
with SQLSTATE 40001 to preserve serializable execution.

Serializable Snapshot Isolation can detect dependency cycles that
ordinary row-level write conflict checks cannot detect.


===============================================================================
11. ISOLATION LEVEL COMPARISON
===============================================================================
*/

SELECT
    name,
    behavior,
    dirty_reads,
    non_repeatable_reads,
    phantom_reads
FROM (
    VALUES
        (
            'READ UNCOMMITTED',
            'READ COMMITTED behavior in PostgreSQL',
            'Not possible',
            'Possible',
            'Possible'
        ),
        (
            'READ COMMITTED',
            'Fresh statement snapshot',
            'Not possible',
            'Possible',
            'Possible'
        ),
        (
            'REPEATABLE READ',
            'Transaction-level snapshot',
            'Not possible',
            'Not possible',
            'Not possible'
        ),
        (
            'SERIALIZABLE',
            'Serializable execution with conflict detection',
            'Not possible',
            'Not possible',
            'Not possible'
        )
) AS isolation_comparison(
    name,
    behavior,
    dirty_reads,
    non_repeatable_reads,
    phantom_reads
);


/*
===============================================================================
12. OPERATIONAL DIAGNOSTICS
===============================================================================
*/

-- Active database transactions.
SELECT
    pid,
    usename,
    state,
    xact_start,
    query_start,
    wait_event_type,
    wait_event,
    LEFT(query, 150) AS query_text
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid()
ORDER BY xact_start NULLS LAST;

-- Lock information for the current database.
SELECT
    locktype,
    relation::regclass AS relation_name,
    mode,
    granted
FROM pg_locks
WHERE database = (
    SELECT oid
    FROM pg_database
    WHERE datname = current_database()
)
ORDER BY relation_name, mode;


/*
===============================================================================
13. SAVEPOINT AND PARTIAL ROLLBACK
===============================================================================
*/

BEGIN;

SAVEPOINT before_update;

UPDATE accounts
SET balance = balance + 50
WHERE account_id = 1;

ROLLBACK TO SAVEPOINT before_update;

COMMIT;


/*
===============================================================================
14. FINAL DATABASE VALIDATION
===============================================================================
*/

DO $$
DECLARE
    invalid_count BIGINT;
BEGIN
    SELECT COUNT(*)
    INTO invalid_count
    FROM accounts
    WHERE balance < 0 OR version <= 0;

    IF invalid_count <> 0 THEN
        RAISE EXCEPTION
            'Integrity validation failed: % invalid accounts',
            invalid_count;
    END IF;

    RAISE NOTICE 'Account integrity validation passed';
END;
$$;

SELECT
    a.account_id,
    a.account_name,
    a.balance,
    a.version,
    COUNT(t.audit_id) AS audit_entries
FROM accounts a
LEFT JOIN transaction_audit t
    ON a.account_id = t.account_id
GROUP BY
    a.account_id,
    a.account_name,
    a.balance,
    a.version
ORDER BY a.account_id;
