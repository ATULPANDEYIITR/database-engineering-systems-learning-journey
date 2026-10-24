DROP SCHEMA IF EXISTS transaction_lab CASCADE;

CREATE SCHEMA transaction_lab;

SET search_path TO transaction_lab;

-- Accounts represent durable business state.
CREATE TABLE accounts (
    account_id BIGSERIAL PRIMARY KEY,
    owner_name TEXT NOT NULL,
    balance NUMERIC(14, 2) NOT NULL DEFAULT 0,
    account_version INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT accounts_owner_name_ck
        CHECK (length(btrim(owner_name)) >= 2),

    CONSTRAINT accounts_balance_ck
        CHECK (balance >= 0),

    CONSTRAINT accounts_version_ck
        CHECK (account_version >= 0)
);

CREATE TABLE repositories (
    repository_id BIGSERIAL PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    current_version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT repositories_name_ck
        CHECK (length(btrim(repository_name)) >= 2)
);

CREATE TABLE transaction_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    transaction_label TEXT NOT NULL,
    account_id BIGINT REFERENCES accounts(account_id),
    operation TEXT NOT NULL,
    amount NUMERIC(14, 2),
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT transaction_audit_operation_ck
        CHECK (
            operation IN (
                'DEPOSIT',
                'WITHDRAW',
                'TRANSFER'
            )
        ),

    CONSTRAINT transaction_audit_amount_ck
        CHECK (amount IS NULL OR amount > 0)
);

CREATE INDEX transaction_audit_account_idx
    ON transaction_audit(account_id, created_at DESC);

CREATE TABLE transfer_requests (
    transfer_id BIGSERIAL PRIMARY KEY,
    source_account_id BIGINT NOT NULL
        REFERENCES accounts(account_id),
    target_account_id BIGINT NOT NULL
        REFERENCES accounts(account_id),
    amount NUMERIC(14, 2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT transfer_amount_ck
        CHECK (amount > 0),

    CONSTRAINT transfer_distinct_accounts_ck
        CHECK (
            source_account_id <> target_account_id
        ),

    CONSTRAINT transfer_status_ck
        CHECK (
            status IN (
                'PENDING',
                'COMPLETED',
                'REJECTED'
            )
        )
);

CREATE INDEX transfer_status_idx
    ON transfer_requests(status, created_at DESC);

INSERT INTO repositories (
    repository_name
)
VALUES (
    'transaction-lab'
);

INSERT INTO accounts (
    owner_name,
    balance
)
VALUES
    ('Alice', 1500.00),
    ('Bob', 900.00),
    ('Carol', 300.00);

-- This trigger prevents an account from ever becoming negative,
-- including changes issued inside an application transaction.
CREATE OR REPLACE FUNCTION prevent_negative_balance()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.balance < 0 THEN
        RAISE EXCEPTION
            'account % cannot have negative balance',
            NEW.account_id
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER accounts_prevent_negative_balance
BEFORE INSERT OR UPDATE OF balance
ON accounts
FOR EACH ROW
EXECUTE FUNCTION prevent_negative_balance();

-- Every committed balance change increments an application-visible
-- row version. PostgreSQL itself provides MVCC transaction metadata;
-- this column is useful for explicit optimistic concurrency checks.
CREATE OR REPLACE FUNCTION increment_account_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.balance IS DISTINCT FROM OLD.balance THEN
        NEW.account_version := OLD.account_version + 1;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER accounts_increment_version
BEFORE UPDATE OF balance
ON accounts
FOR EACH ROW
EXECUTE FUNCTION increment_account_version();

CREATE OR REPLACE FUNCTION record_balance_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.balance > OLD.balance THEN
        INSERT INTO transaction_audit (
            transaction_label,
            account_id,
            operation,
            amount,
            details
        )
        VALUES (
            current_setting(
                'transaction_lab.label',
                true
            ),
            NEW.account_id,
            'DEPOSIT',
            NEW.balance - OLD.balance,
            'balance increased'
        );
    ELSIF NEW.balance < OLD.balance THEN
        INSERT INTO transaction_audit (
            transaction_label,
            account_id,
            operation,
            amount,
            details
        )
        VALUES (
            current_setting(
                'transaction_lab.label',
                true
            ),
            NEW.account_id,
            'WITHDRAW',
            OLD.balance - NEW.balance,
            'balance decreased'
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER accounts_record_balance_change
AFTER UPDATE OF balance
ON accounts
FOR EACH ROW
EXECUTE FUNCTION record_balance_change();

CREATE OR REPLACE FUNCTION transfer_funds(
    p_source BIGINT,
    p_target BIGINT,
    p_amount NUMERIC(14, 2)
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_source_balance NUMERIC(14, 2);
BEGIN
    IF p_source = p_target THEN
        RAISE EXCEPTION
            'source and target accounts must differ';
    END IF;

    IF p_amount IS NULL OR p_amount <= 0 THEN
        RAISE EXCEPTION
            'transfer amount must be positive';
    END IF;

    /*
     * FOR UPDATE locks both account rows until COMMIT or ROLLBACK.
     * Sorting the IDs before locking reduces the risk of deadlocks
     * when concurrent transfers operate on the same accounts.
     */
    IF p_source < p_target THEN
        PERFORM 1
        FROM accounts
        WHERE account_id IN (p_source, p_target)
        ORDER BY account_id
        FOR UPDATE;
    ELSE
        PERFORM 1
        FROM accounts
        WHERE account_id IN (p_target, p_source)
        ORDER BY account_id
        FOR UPDATE;
    END IF;

    SELECT balance
    INTO v_source_balance
    FROM accounts
    WHERE account_id = p_source
    FOR UPDATE;

    IF v_source_balance IS NULL THEN
        RAISE EXCEPTION
            'source account % does not exist',
            p_source;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM accounts
        WHERE account_id = p_target
    ) THEN
        RAISE EXCEPTION
            'target account % does not exist',
            p_target;
    END IF;

    IF v_source_balance < p_amount THEN
        RAISE EXCEPTION
            'insufficient funds in account %',
            p_source;
    END IF;

    UPDATE accounts
    SET balance = balance - p_amount
    WHERE account_id = p_source;

    UPDATE accounts
    SET balance = balance + p_amount
    WHERE account_id = p_target;

    INSERT INTO transaction_audit (
        transaction_label,
        operation,
        amount,
        details
    )
    VALUES (
        current_setting(
            'transaction_lab.label',
            true
        ),
        'TRANSFER',
        p_amount,
        format(
            'source=%s,target=%s',
            p_source,
            p_target
        )
    );
END;
$$;

-- A complete successful transaction.
BEGIN;

SET LOCAL transaction_lab.label = 'successful-transfer';

SELECT transfer_funds(
    1,
    2,
    125.00
);

COMMIT;

-- Demonstrate atomic rollback. The first update succeeds inside
-- the transaction, but the later exception causes the entire
-- transaction to be rolled back.
BEGIN;

SET LOCAL transaction_lab.label = 'rollback-example';

UPDATE accounts
SET balance = balance + 100.00
WHERE account_id = 1;

DO $$
BEGIN
    RAISE EXCEPTION
        'simulated downstream failure';
END;
$$;

ROLLBACK;

-- Savepoints allow partial recovery without discarding the entire
-- transaction.
BEGIN;

SET LOCAL transaction_lab.label = 'savepoint-example';

UPDATE accounts
SET balance = balance + 50.00
WHERE account_id = 1;

SAVEPOINT before_risky_operation;

-- This statement fails because the CHECK constraint rejects a
-- negative balance. The surrounding transaction remains usable
-- because the failure is handled by rolling back to the savepoint.
UPDATE accounts
SET balance = -500.00
WHERE account_id = 2;

ROLLBACK TO SAVEPOINT before_risky_operation;

UPDATE accounts
SET balance = balance + 25.00
WHERE account_id = 2;

RELEASE SAVEPOINT before_risky_operation;

COMMIT;

-- A failed transfer can be handled with a savepoint while preserving
-- earlier valid work in the same transaction.
BEGIN;

SET LOCAL transaction_lab.label = 'partial-recovery';

UPDATE accounts
SET balance = balance + 10.00
WHERE account_id = 3;

SAVEPOINT before_transfer;

SELECT transfer_funds(
    2,
    1,
    100000.00
);

ROLLBACK TO SAVEPOINT before_transfer;

UPDATE accounts
SET balance = balance + 5.00
WHERE account_id = 3;

COMMIT;

-- Explicit row locking provides a deterministic transaction boundary
-- for concurrent balance modifications.
BEGIN;

SET LOCAL transaction_lab.label = 'locked-withdrawal';

SELECT balance
FROM accounts
WHERE account_id = 1
FOR UPDATE;

UPDATE accounts
SET balance = balance - 20.00
WHERE account_id = 1
  AND balance >= 20.00;

IF NOT EXISTS (
    SELECT 1
    FROM accounts
    WHERE account_id = 1
      AND balance >= 0
) THEN
    ROLLBACK;
ELSE
    COMMIT;
END IF;

-- Transactional request creation followed by processing.
BEGIN;

INSERT INTO transfer_requests (
    source_account_id,
    target_account_id,
    amount
)
VALUES (
    1,
    3,
    75.00
);

SELECT transfer_funds(
    1,
    3,
    75.00
);

UPDATE transfer_requests
SET status = 'COMPLETED'
WHERE transfer_id = (
    SELECT max(transfer_id)
    FROM transfer_requests
);

COMMIT;

-- Retrieval of durable state after all committed work.
SELECT
    account_id,
    owner_name,
    balance,
    account_version
FROM accounts
ORDER BY account_id;

-- Audit reporting.
SELECT
    account_id,
    operation,
    COUNT(*) AS operation_count,
    SUM(amount) AS total_amount
FROM transaction_audit
GROUP BY account_id, operation
ORDER BY account_id, operation;

-- Transaction-level audit trail.
SELECT
    audit_id,
    transaction_label,
    account_id,
    operation,
    amount,
    details,
    created_at
FROM transaction_audit
ORDER BY audit_id;

-- Workflow state reporting.
SELECT
    status,
    COUNT(*) AS request_count,
    COALESCE(SUM(amount), 0) AS total_amount
FROM transfer_requests
GROUP BY status
ORDER BY status;

-- Optimistic concurrency example:
-- application code can read account_version and later require
-- the same version during its UPDATE.
BEGIN;

SET LOCAL transaction_lab.label = 'optimistic-update';

WITH expected_version AS (
    SELECT account_version
    FROM accounts
    WHERE account_id = 1
)
UPDATE accounts AS a
SET balance = a.balance + 15.00
FROM expected_version AS e
WHERE a.account_id = 1
  AND a.account_version = e.account_version;

COMMIT;

-- A view separates reporting from operational transaction logic.
CREATE OR REPLACE VIEW account_transaction_summary AS
SELECT
    a.account_id,
    a.owner_name,
    a.balance,
    a.account_version,
    COUNT(t.audit_id) AS recorded_operations,
    COALESCE(SUM(t.amount), 0) AS recorded_amount
FROM accounts AS a
LEFT JOIN transaction_audit AS t
    ON t.account_id = a.account_id
GROUP BY
    a.account_id,
    a.owner_name,
    a.balance,
    a.account_version;

SELECT *
FROM account_transaction_summary
ORDER BY account_id;

-- CTE-based validation query: identify accounts whose recorded
-- transaction activity does not match their current state assumptions.
WITH account_activity AS (
    SELECT
        account_id,
        COUNT(*) AS operation_count,
        SUM(
            CASE
                WHEN operation = 'DEPOSIT'
                    THEN amount
                WHEN operation = 'WITHDRAW'
                    THEN -amount
                ELSE 0
            END
        ) AS net_recorded_change
    FROM transaction_audit
    WHERE account_id IS NOT NULL
    GROUP BY account_id
)
SELECT
    a.account_id,
    a.owner_name,
    a.balance,
    aa.operation_count,
    aa.net_recorded_change
FROM accounts AS a
LEFT JOIN account_activity AS aa
    ON aa.account_id = a.account_id
ORDER BY a.account_id;
