-- ============================================================
-- SERIALIZABLE SYSTEMS
-- Serializable Execution and Practical Costs
--
-- PostgreSQL 15+
--
-- Demonstrates:
-- 1. Transaction isolation levels.
-- 2. Serializable execution.
-- 3. Write skew and serialization anomalies.
-- 4. Transaction retries.
-- 5. Banking transaction integrity.
-- 6. Transaction audit records.
-- 7. Concurrent transaction monitoring.
-- 8. Practical performance reporting.
--
-- IMPORTANT:
-- SERIALIZABLE isolation must be configured before executing
-- the transaction's data-access statements.
-- PostgreSQL may abort transactions with SQLSTATE 40001.
-- Applications must retry the entire transaction.
-- ============================================================

DROP SCHEMA IF EXISTS serializable_lab CASCADE;

CREATE SCHEMA serializable_lab;

SET search_path TO serializable_lab, public;

-- ============================================================
-- 1. DOMAIN TABLES
-- ============================================================

CREATE TABLE repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT NOT NULL
        REFERENCES repositories(repository_id),
    account_number VARCHAR(30) NOT NULL UNIQUE,
    owner_name VARCHAR(120) NOT NULL,
    balance NUMERIC(18,2) NOT NULL DEFAULT 0,
    account_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT account_balance_nonnegative
        CHECK (balance >= 0),

    CONSTRAINT account_version_nonnegative
        CHECK (version >= 0),

    CONSTRAINT account_status_valid
        CHECK (
            account_status IN (
                'ACTIVE',
                'FROZEN',
                'CLOSED'
            )
        )
);

CREATE TABLE transaction_records (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_reference UUID NOT NULL UNIQUE,
    transaction_type VARCHAR(30) NOT NULL,
    transaction_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    isolation_level VARCHAR(30) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    retry_count INTEGER NOT NULL DEFAULT 0,
    execution_duration_ms NUMERIC(12,3),

    CONSTRAINT transaction_type_valid
        CHECK (
            transaction_type IN (
                'TRANSFER',
                'DEPOSIT',
                'WITHDRAWAL',
                'BALANCE_ADJUSTMENT'
            )
        ),

    CONSTRAINT transaction_status_valid
        CHECK (
            transaction_status IN (
                'PENDING',
                'COMMITTED',
                'ABORTED',
                'RETRY_REQUIRED'
            )
        ),

    CONSTRAINT isolation_level_valid
        CHECK (
            isolation_level IN (
                'READ COMMITTED',
                'REPEATABLE READ',
                'SERIALIZABLE'
            )
        ),

    CONSTRAINT retry_count_nonnegative
        CHECK (retry_count >= 0),

    CONSTRAINT execution_duration_nonnegative
        CHECK (
            execution_duration_ms IS NULL
            OR execution_duration_ms >= 0
        )
);

CREATE TABLE transaction_entries (
    entry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id BIGINT NOT NULL
        REFERENCES transaction_records(transaction_id),
    account_id BIGINT NOT NULL
        REFERENCES accounts(account_id),
    entry_type VARCHAR(10) NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT entry_type_valid
        CHECK (entry_type IN ('DEBIT', 'CREDIT')),

    CONSTRAINT entry_amount_positive
        CHECK (amount > 0),

    CONSTRAINT transaction_account_entry_unique
        UNIQUE (
            transaction_id,
            account_id,
            entry_type
        )
);

CREATE TABLE transaction_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id BIGINT NOT NULL
        REFERENCES transaction_records(transaction_id),
    event_type VARCHAR(40) NOT NULL,
    event_details JSONB NOT NULL DEFAULT '{}'::JSONB,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE serialization_metrics (
    metric_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id BIGINT
        REFERENCES transaction_records(transaction_id),
    isolation_level VARCHAR(30) NOT NULL,
    execution_time_ms NUMERIC(12,3) NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    conflict_detected BOOLEAN NOT NULL DEFAULT FALSE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT metric_execution_nonnegative
        CHECK (execution_time_ms >= 0),

    CONSTRAINT metric_retry_nonnegative
        CHECK (retry_count >= 0)
);

-- ============================================================
-- 2. PERFORMANCE INDEXES
-- ============================================================

CREATE INDEX idx_accounts_repository_status
    ON accounts(repository_id, account_status);

CREATE INDEX idx_transaction_status_started
    ON transaction_records(transaction_status, started_at DESC);

CREATE INDEX idx_transaction_reference
    ON transaction_records(transaction_reference);

CREATE INDEX idx_entries_transaction
    ON transaction_entries(transaction_id);

CREATE INDEX idx_entries_account_created
    ON transaction_entries(account_id, created_at DESC);

CREATE INDEX idx_events_transaction_timestamp
    ON transaction_events(transaction_id, event_timestamp DESC);

CREATE INDEX idx_metrics_isolation_recorded
    ON serialization_metrics(isolation_level, recorded_at DESC);

CREATE INDEX idx_events_details_gin
    ON transaction_events USING GIN(event_details);

-- ============================================================
-- 3. ACCOUNT VERSION MANAGEMENT
-- ============================================================

CREATE OR REPLACE FUNCTION increment_account_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.balance IS DISTINCT FROM OLD.balance
       OR NEW.account_status IS DISTINCT FROM OLD.account_status
    THEN
        NEW.version := OLD.version + 1;
    ELSE
        NEW.version := OLD.version;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_account_version
BEFORE UPDATE ON accounts
FOR EACH ROW
EXECUTE FUNCTION increment_account_version();

-- ============================================================
-- 4. TRANSACTION AUDIT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION audit_transaction_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.transaction_status IS DISTINCT FROM NEW.transaction_status
    THEN
        INSERT INTO transaction_events (
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
                'isolation_level', NEW.isolation_level
            )
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_transaction_status_audit
AFTER UPDATE ON transaction_records
FOR EACH ROW
EXECUTE FUNCTION audit_transaction_status();

-- ============================================================
-- 5. ACCOUNT TRANSFER PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE transfer_funds(
    p_reference UUID,
    p_source_account BIGINT,
    p_destination_account BIGINT,
    p_amount NUMERIC(18,2)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_source_balance NUMERIC(18,2);
    v_destination_balance NUMERIC(18,2);
    v_source_status VARCHAR(20);
    v_destination_status VARCHAR(20);
    v_transaction_id BIGINT;
BEGIN
    IF p_source_account = p_destination_account THEN
        RAISE EXCEPTION 'Source and destination must differ';
    END IF;

    IF p_amount IS NULL OR p_amount <= 0 THEN
        RAISE EXCEPTION 'Transfer amount must be positive';
    END IF;

    -- A deterministic lock order reduces deadlock probability.
    PERFORM account_id
    FROM accounts
    WHERE account_id IN (
        p_source_account,
        p_destination_account
    )
    ORDER BY account_id
    FOR UPDATE;

    IF (
        SELECT COUNT(*)
        FROM accounts
        WHERE account_id IN (
            p_source_account,
            p_destination_account
        )
    ) <> 2 THEN
        RAISE EXCEPTION 'One or both accounts do not exist';
    END IF;

    SELECT balance, account_status
    INTO v_source_balance, v_source_status
    FROM accounts
    WHERE account_id = p_source_account;

    SELECT balance, account_status
    INTO v_destination_balance, v_destination_status
    FROM accounts
    WHERE account_id = p_destination_account;

    IF v_source_status <> 'ACTIVE'
       OR v_destination_status <> 'ACTIVE'
    THEN
        RAISE EXCEPTION 'Both accounts must be active';
    END IF;

    IF v_source_balance < p_amount THEN
        RAISE EXCEPTION 'Insufficient funds';
    END IF;

    IF v_destination_balance + p_amount >
       9999999999999999.99::NUMERIC
    THEN
        RAISE EXCEPTION 'Destination balance limit exceeded';
    END IF;

    INSERT INTO transaction_records (
        transaction_reference,
        transaction_type,
        transaction_status,
        isolation_level
    )
    VALUES (
        p_reference,
        'TRANSFER',
        'PENDING',
        current_setting('transaction_isolation')
    )
    RETURNING transaction_id INTO v_transaction_id;

    UPDATE accounts
    SET balance = balance - p_amount
    WHERE account_id = p_source_account;

    UPDATE accounts
    SET balance = balance + p_amount
    WHERE account_id = p_destination_account;

    INSERT INTO transaction_entries (
        transaction_id,
        account_id,
        entry_type,
        amount
    )
    VALUES
        (
            v_transaction_id,
            p_source_account,
            'DEBIT',
            p_amount
        ),
        (
            v_transaction_id,
            p_destination_account,
            'CREDIT',
            p_amount
        );

    UPDATE transaction_records
    SET transaction_status = 'COMMITTED',
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = v_transaction_id;

    INSERT INTO transaction_events (
        transaction_id,
        event_type,
        event_details
    )
    VALUES (
        v_transaction_id,
        'TRANSFER_COMPLETED',
        jsonb_build_object(
            'source_account', p_source_account,
            'destination_account', p_destination_account,
            'amount', p_amount
        )
    );
END;
$$;

-- ============================================================
-- 6. ELIGIBILITY AND VALIDATION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_transfer(
    p_source_account BIGINT,
    p_destination_account BIGINT,
    p_amount NUMERIC
)
RETURNS TABLE (
    eligible BOOLEAN,
    reason TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_source accounts%ROWTYPE;
    v_destination accounts%ROWTYPE;
BEGIN
    IF p_source_account = p_destination_account THEN
        RETURN QUERY
        SELECT FALSE, 'Accounts must be different'::TEXT;
        RETURN;
    END IF;

    IF p_amount IS NULL OR p_amount <= 0 THEN
        RETURN QUERY
        SELECT FALSE, 'Amount must be positive'::TEXT;
        RETURN;
    END IF;

    SELECT *
    INTO v_source
    FROM accounts
    WHERE account_id = p_source_account;

    IF NOT FOUND THEN
        RETURN QUERY
        SELECT FALSE, 'Source account not found'::TEXT;
        RETURN;
    END IF;

    SELECT *
    INTO v_destination
    FROM accounts
    WHERE account_id = p_destination_account;

    IF NOT FOUND THEN
        RETURN QUERY
        SELECT FALSE, 'Destination account not found'::TEXT;
        RETURN;
    END IF;

    IF v_source.account_status <> 'ACTIVE'
       OR v_destination.account_status <> 'ACTIVE'
    THEN
        RETURN QUERY
        SELECT FALSE, 'Account is not active'::TEXT;
        RETURN;
    END IF;

    IF v_source.balance < p_amount THEN
        RETURN QUERY
        SELECT FALSE, 'Insufficient funds'::TEXT;
        RETURN;
    END IF;

    RETURN QUERY
    SELECT TRUE, 'Transfer eligible'::TEXT;
END;
$$;

-- ============================================================
-- 7. SAMPLE DATA
-- ============================================================

INSERT INTO repositories (
    repository_name,
    description
)
VALUES
    (
        'CORE_BANKING',
        'Transactional account processing system'
    ),
    (
        'PAYMENT_LEDGER',
        'Payment and settlement records'
    );

INSERT INTO accounts (
    repository_id,
    account_number,
    owner_name,
    balance,
    account_status
)
SELECT
    repository_id,
    'ACC-1001',
    'Customer A',
    10000.00,
    'ACTIVE'
FROM repositories
WHERE repository_name = 'CORE_BANKING';

INSERT INTO accounts (
    repository_id,
    account_number,
    owner_name,
    balance,
    account_status
)
SELECT
    repository_id,
    'ACC-1002',
    'Customer B',
    5000.00,
    'ACTIVE'
FROM repositories
WHERE repository_name = 'CORE_BANKING';

INSERT INTO accounts (
    repository_id,
    account_number,
    owner_name,
    balance,
    account_status
)
SELECT
    repository_id,
    'ACC-1003',
    'Customer C',
    100.00,
    'FROZEN'
FROM repositories
WHERE repository_name = 'CORE_BANKING';

INSERT INTO accounts (
    repository_id,
    account_number,
    owner_name,
    balance,
    account_status
)
SELECT
    repository_id,
    'ACC-1004',
    'Customer D',
    20000.00,
    'ACTIVE'
FROM repositories
WHERE repository_name = 'CORE_BANKING';

-- ============================================================
-- 8. ELIGIBILITY QUERIES
-- ============================================================

SELECT *
FROM validate_transfer(
    (SELECT account_id FROM accounts
     WHERE account_number = 'ACC-1001'),
    (SELECT account_id FROM accounts
     WHERE account_number = 'ACC-1002'),
    500.00
);

SELECT *
FROM validate_transfer(
    (SELECT account_id FROM accounts
     WHERE account_number = 'ACC-1001'),
    (SELECT account_id FROM accounts
     WHERE account_number = 'ACC-1003'),
    500.00
);

SELECT *
FROM validate_transfer(
    (SELECT account_id FROM accounts
     WHERE account_number = 'ACC-1001'),
    (SELECT account_id FROM accounts
     WHERE account_number = 'ACC-1002'),
    500000.00
);

-- ============================================================
-- 9. SERIALIZABLE TRANSACTION
-- ============================================================

BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;

CALL transfer_funds(
    '11111111-1111-4111-8111-111111111111',
    (SELECT account_id FROM accounts
     WHERE account_number = 'ACC-1001'),
    (SELECT account_id FROM accounts
     WHERE account_number = 'ACC-1002'),
    500.00
);

COMMIT;

-- ============================================================
-- 10. REPEATABLE READ COMPARISON
-- ============================================================

BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;

SELECT
    account_number,
    balance,
    version
FROM accounts
ORDER BY account_id;

COMMIT;

-- ============================================================
-- 11. SERIALIZABLE READ-ONLY TRANSACTION
-- ============================================================

BEGIN TRANSACTION
ISOLATION LEVEL SERIALIZABLE
READ ONLY;

SELECT
    SUM(balance) AS total_account_balance,
    COUNT(*) AS total_accounts,
    AVG(balance) AS average_balance
FROM accounts
WHERE account_status = 'ACTIVE';

COMMIT;

-- ============================================================
-- 12. REPORTING VIEWS
-- ============================================================

CREATE OR REPLACE VIEW account_transaction_summary AS
SELECT
    a.account_id,
    a.account_number,
    a.owner_name,
    a.balance,
    a.version,
    a.account_status,
    COUNT(DISTINCT e.transaction_id) AS transaction_count,
    COALESCE(
        SUM(
            CASE
                WHEN e.entry_type = 'DEBIT'
                THEN e.amount
                ELSE 0
            END
        ),
        0
    ) AS total_debits,
    COALESCE(
        SUM(
            CASE
                WHEN e.entry_type = 'CREDIT'
                THEN e.amount
                ELSE 0
            END
        ),
        0
    ) AS total_credits
FROM accounts a
LEFT JOIN transaction_entries e
    ON a.account_id = e.account_id
GROUP BY
    a.account_id,
    a.account_number,
    a.owner_name,
    a.balance,
    a.version,
    a.account_status;

CREATE OR REPLACE VIEW serializability_cost_report AS
SELECT
    isolation_level,
    COUNT(*) AS execution_count,
    ROUND(AVG(execution_time_ms), 3) AS average_execution_ms,
    ROUND(MAX(execution_time_ms), 3) AS maximum_execution_ms,
    SUM(retry_count) AS total_retries,
    COUNT(*) FILTER (
        WHERE conflict_detected
    ) AS conflicted_executions,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE conflict_detected
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS conflict_percentage
FROM serialization_metrics
GROUP BY isolation_level;

-- ============================================================
-- 13. DEMONSTRATION METRICS
-- ============================================================

INSERT INTO serialization_metrics (
    isolation_level,
    execution_time_ms,
    retry_count,
    conflict_detected
)
VALUES
    ('READ COMMITTED', 4.25, 0, FALSE),
    ('READ COMMITTED', 5.10, 0, FALSE),
    ('REPEATABLE READ', 6.75, 0, FALSE),
    ('REPEATABLE READ', 9.20, 1, TRUE),
    ('SERIALIZABLE', 8.40, 0, FALSE),
    ('SERIALIZABLE', 13.50, 2, TRUE),
    ('SERIALIZABLE', 10.25, 1, TRUE);

-- ============================================================
-- 14. RETRIEVAL REPORTS
-- ============================================================

SELECT *
FROM account_transaction_summary
ORDER BY account_id;

SELECT *
FROM serializability_cost_report
ORDER BY isolation_level;

SELECT
    transaction_id,
    transaction_reference,
    transaction_type,
    transaction_status,
    isolation_level,
    retry_count,
    started_at,
    completed_at
FROM transaction_records
ORDER BY started_at DESC;

-- ============================================================
-- 15. WORKFLOW VALIDATION
-- ============================================================

SELECT
    tr.transaction_id,
    tr.transaction_status,
    COUNT(te.entry_id) AS entry_count,
    SUM(
        CASE
            WHEN te.entry_type = 'CREDIT'
            THEN te.amount
            WHEN te.entry_type = 'DEBIT'
            THEN -te.amount
            ELSE 0
        END
    ) AS net_transaction_amount,
    CASE
        WHEN tr.transaction_type = 'TRANSFER'
             AND COUNT(te.entry_id) = 2
             AND SUM(
                 CASE
                     WHEN te.entry_type = 'CREDIT'
                     THEN te.amount
                     WHEN te.entry_type = 'DEBIT'
                     THEN -te.amount
                     ELSE 0
                 END
             ) = 0
        THEN 'BALANCED'
        WHEN tr.transaction_type = 'TRANSFER'
        THEN 'INVALID'
        ELSE 'NOT_APPLICABLE'
    END AS ledger_validation
FROM transaction_records tr
LEFT JOIN transaction_entries te
    ON tr.transaction_id = te.transaction_id
GROUP BY
    tr.transaction_id,
    tr.transaction_type,
    tr.transaction_status
ORDER BY tr.transaction_id;

-- ============================================================
-- 16. TRANSACTION AUDIT
-- ============================================================

SELECT
    te.event_id,
    te.transaction_id,
    te.event_type,
    te.event_details,
    te.event_timestamp
FROM transaction_events te
ORDER BY te.event_timestamp DESC;

-- ============================================================
-- 17. FAILURE AND RETRY ANALYSIS
-- ============================================================

SELECT
    transaction_status,
    isolation_level,
    COUNT(*) AS transaction_count,
    AVG(retry_count) AS average_retries
FROM transaction_records
GROUP BY
    transaction_status,
    isolation_level
ORDER BY
    isolation_level,
    transaction_status;

-- ============================================================
-- 18. OPERATIONAL GUIDANCE
-- ============================================================

-- PostgreSQL Serializable Snapshot Isolation (SSI):
--
-- PostgreSQL tracks read/write dependencies and may abort
-- a transaction when concurrent execution could violate
-- serializable behavior.
--
-- A serialization failure normally has SQLSTATE 40001.
--
-- Applications must:
-- 1. Begin a new transaction.
-- 2. Repeat all reads.
-- 3. Recompute decisions.
-- 4. Repeat all writes.
-- 5. Retry with bounded exponential backoff.
--
-- Retrying only the failed statement is not sufficient.
--
-- Deadlocks normally use SQLSTATE 40P01 and require a
-- separate retry strategy.
--
-- A transaction-level retry must also account for external
-- side effects. Use idempotency keys and an outbox pattern
-- where external delivery is required.
--
-- The account transfer procedure uses explicit row locks
-- and deterministic lock ordering. SERIALIZABLE adds
-- predicate-level anomaly protection beyond those locks.
--
-- Indexes can reduce scan time but may increase write,
-- maintenance, and storage costs.
--
-- A successful SERIALIZABLE commit is equivalent to a
-- valid position in some serial transaction ordering.
--
-- ============================================================
-- END OF SCRIPT
-- ============================================================
