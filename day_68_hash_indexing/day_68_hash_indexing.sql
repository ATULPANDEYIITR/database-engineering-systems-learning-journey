/*
 * HASH INDEXING IN POSTGRESQL
 *
 * Models a transaction-processing system with:
 * - Relational primary and foreign keys
 * - Hash indexes for equality-based access
 * - B-tree indexes for ordered and range access
 * - Transaction and account retrieval
 * - Index statistics
 * - Hash-index execution-plan inspection
 * - Operational audit records
 * - Functions, procedures, and triggers
 *
 * Execute using PostgreSQL 14 or later.
 *
 * Run in a dedicated database or test environment.
 */

BEGIN;

CREATE SCHEMA IF NOT EXISTS hash_index_lab;

SET search_path TO hash_index_lab, public;


/* ============================================================
   1. DOMAIN TABLES
   ============================================================ */

CREATE TABLE IF NOT EXISTS customers (
    customer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_code VARCHAR(30) NOT NULL UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(254) NOT NULL UNIQUE,
    customer_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT customers_code_format
        CHECK (customer_code ~ '^CUST-[0-9]{4,}$'),

    CONSTRAINT customers_name_valid
        CHECK (length(trim(full_name)) > 0),

    CONSTRAINT customers_status_valid
        CHECK (
            customer_status IN (
                'ACTIVE',
                'SUSPENDED',
                'CLOSED'
            )
        )
);


CREATE TABLE IF NOT EXISTS accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_number VARCHAR(30) NOT NULL UNIQUE,
    customer_id BIGINT NOT NULL REFERENCES customers(customer_id),
    account_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    balance NUMERIC(16, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT accounts_balance_nonnegative
        CHECK (balance >= 0),

    CONSTRAINT accounts_status_valid
        CHECK (
            account_status IN (
                'ACTIVE',
                'SUSPENDED',
                'CLOSED'
            )
        )
);


CREATE TABLE IF NOT EXISTS transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_reference VARCHAR(40) NOT NULL UNIQUE,
    account_id BIGINT NOT NULL REFERENCES accounts(account_id),
    amount NUMERIC(16, 2) NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,
    transaction_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT transaction_reference_format
        CHECK (transaction_reference ~ '^TX-[0-9]{4,}$'),

    CONSTRAINT transaction_amount_positive
        CHECK (amount > 0),

    CONSTRAINT transaction_type_valid
        CHECK (
            transaction_type IN (
                'CREDIT',
                'DEBIT'
            )
        ),

    CONSTRAINT transaction_status_valid
        CHECK (
            transaction_status IN (
                'PENDING',
                'APPROVED',
                'REJECTED',
                'SETTLED'
            )
        )
);


CREATE TABLE IF NOT EXISTS index_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id BIGINT,
    operation VARCHAR(20) NOT NULL,
    previous_status VARCHAR(20),
    new_status VARCHAR(20),
    performed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    database_user TEXT NOT NULL DEFAULT CURRENT_USER,

    CONSTRAINT audit_operation_valid
        CHECK (
            operation IN (
                'INSERT',
                'UPDATE',
                'DELETE'
            )
        )
);


/* ============================================================
   2. HASH AND BTREE INDEXES
   ============================================================ */

/*
 * Hash indexes support equality comparisons.
 * They do not support range scans or ordered retrieval.
 */

CREATE INDEX IF NOT EXISTS idx_transactions_reference_hash
    ON transactions USING HASH (transaction_reference);

CREATE INDEX IF NOT EXISTS idx_accounts_number_hash
    ON accounts USING HASH (account_number);

CREATE INDEX IF NOT EXISTS idx_customers_code_hash
    ON customers USING HASH (customer_code);

CREATE INDEX IF NOT EXISTS idx_transactions_status_hash
    ON transactions USING HASH (transaction_status);


/*
 * B-tree indexes remain appropriate for range conditions,
 * ordering, composite searches, and foreign-key access patterns.
 */

CREATE INDEX IF NOT EXISTS idx_transactions_account_created
    ON transactions (account_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_created
    ON transactions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_accounts_customer
    ON accounts (customer_id);

CREATE INDEX IF NOT EXISTS idx_transactions_pending
    ON transactions (created_at)
    WHERE transaction_status = 'PENDING';


/* ============================================================
   3. AUDIT TRIGGER
   ============================================================ */

CREATE OR REPLACE FUNCTION audit_transaction_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO index_audit (
            transaction_id,
            operation,
            previous_status,
            new_status
        )
        VALUES (
            NEW.transaction_id,
            'INSERT',
            NULL,
            NEW.transaction_status
        );

        RETURN NEW;

    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO index_audit (
            transaction_id,
            operation,
            previous_status,
            new_status
        )
        VALUES (
            NEW.transaction_id,
            'UPDATE',
            OLD.transaction_status,
            NEW.transaction_status
        );

        NEW.updated_at = CURRENT_TIMESTAMP;

        RETURN NEW;

    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO index_audit (
            transaction_id,
            operation,
            previous_status,
            new_status
        )
        VALUES (
            OLD.transaction_id,
            'DELETE',
            OLD.transaction_status,
            NULL
        );

        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$;


DROP TRIGGER IF EXISTS trg_transaction_audit
ON transactions;

CREATE TRIGGER trg_transaction_audit
BEFORE INSERT OR UPDATE OR DELETE
ON transactions
FOR EACH ROW
EXECUTE FUNCTION audit_transaction_change();


/* ============================================================
   4. TRANSACTION RETRIEVAL FUNCTION
   ============================================================ */

CREATE OR REPLACE FUNCTION find_transaction_by_reference(
    p_reference VARCHAR
)
RETURNS TABLE (
    transaction_id BIGINT,
    transaction_reference VARCHAR,
    account_number VARCHAR,
    amount NUMERIC,
    transaction_status VARCHAR,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF p_reference IS NULL OR
       p_reference !~ '^TX-[0-9]{4,}$' THEN
        RAISE EXCEPTION
            'Invalid transaction reference: %',
            p_reference
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT
        t.transaction_id,
        t.transaction_reference,
        a.account_number,
        t.amount,
        t.transaction_status,
        t.created_at
    FROM transactions t
    JOIN accounts a
        ON a.account_id = t.account_id
    WHERE t.transaction_reference = p_reference;
END;
$$;


/* ============================================================
   5. WORKFLOW PROCEDURE
   ============================================================ */

CREATE OR REPLACE PROCEDURE update_transaction_status(
    p_reference VARCHAR,
    p_new_status VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_id BIGINT;
    v_current_status VARCHAR(20);
BEGIN
    IF p_new_status NOT IN (
        'PENDING',
        'APPROVED',
        'REJECTED',
        'SETTLED'
    ) THEN
        RAISE EXCEPTION
            'Invalid transaction status: %',
            p_new_status;
    END IF;

    SELECT
        transaction_id,
        transaction_status
    INTO
        v_transaction_id,
        v_current_status
    FROM transactions
    WHERE transaction_reference = p_reference
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Transaction not found: %',
            p_reference;
    END IF;

    IF v_current_status = p_new_status THEN
        RAISE NOTICE
            'Transaction already has status %',
            p_new_status;
        RETURN;
    END IF;

    IF v_current_status IN ('REJECTED', 'SETTLED') THEN
        RAISE EXCEPTION
            'Terminal transaction status cannot be changed: %',
            v_current_status;
    END IF;

    IF (
        v_current_status = 'PENDING'
        AND p_new_status NOT IN ('APPROVED', 'REJECTED')
    ) THEN
        RAISE EXCEPTION
            'Invalid transition from PENDING to %',
            p_new_status;
    END IF;

    IF (
        v_current_status = 'APPROVED'
        AND p_new_status NOT IN ('SETTLED', 'REJECTED')
    ) THEN
        RAISE EXCEPTION
            'Invalid transition from APPROVED to %',
            p_new_status;
    END IF;

    UPDATE transactions
    SET transaction_status = p_new_status
    WHERE transaction_id = v_transaction_id;
END;
$$;


/* ============================================================
   6. REPORTING VIEW
   ============================================================ */

CREATE OR REPLACE VIEW transaction_index_report AS
SELECT
    c.customer_code,
    c.full_name,
    a.account_number,
    a.account_status,
    COUNT(t.transaction_id) AS transaction_count,
    COALESCE(
        SUM(t.amount) FILTER (
            WHERE t.transaction_status = 'SETTLED'
        ),
        0
    ) AS settled_amount,
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'PENDING'
    ) AS pending_count
FROM customers c
JOIN accounts a
    ON a.customer_id = c.customer_id
LEFT JOIN transactions t
    ON t.account_id = a.account_id
GROUP BY
    c.customer_id,
    c.customer_code,
    c.full_name,
    a.account_number,
    a.account_status;


/* ============================================================
   7. SAMPLE RECORDS
   ============================================================ */

INSERT INTO customers (
    customer_code,
    full_name,
    email
)
VALUES
    ('CUST-1001', 'Aarav Sharma', 'aarav@example.com'),
    ('CUST-1002', 'Diya Verma', 'diya@example.com'),
    ('CUST-1003', 'Kabir Singh', 'kabir@example.com'),
    ('CUST-1004', 'Meera Joshi', 'meera@example.com')
ON CONFLICT DO NOTHING;


INSERT INTO accounts (
    account_number,
    customer_id,
    account_status,
    balance
)
SELECT
    v.account_number,
    c.customer_id,
    v.account_status,
    v.balance
FROM (
    VALUES
        ('ACC-1001', 'CUST-1001', 'ACTIVE', 50000.00::NUMERIC),
        ('ACC-1002', 'CUST-1002', 'ACTIVE', 75000.00::NUMERIC),
        ('ACC-1003', 'CUST-1003', 'SUSPENDED', 30000.00::NUMERIC),
        ('ACC-1004', 'CUST-1004', 'ACTIVE', 90000.00::NUMERIC)
) AS v(account_number, customer_code, account_status, balance)
JOIN customers c
    ON c.customer_code = v.customer_code
ON CONFLICT DO NOTHING;


INSERT INTO transactions (
    transaction_reference,
    account_id,
    amount,
    transaction_type,
    transaction_status,
    description
)
SELECT
    v.reference,
    a.account_id,
    v.amount,
    v.transaction_type,
    v.transaction_status,
    v.description
FROM (
    VALUES
        (
            'TX-1001',
            'ACC-1001',
            12500.00::NUMERIC,
            'DEBIT',
            'APPROVED',
            'Supplier payment'
        ),
        (
            'TX-1002',
            'ACC-1002',
            8500.00::NUMERIC,
            'CREDIT',
            'PENDING',
            'Customer deposit'
        ),
        (
            'TX-1003',
            'ACC-1003',
            24000.00::NUMERIC,
            'DEBIT',
            'SETTLED',
            'Infrastructure payment'
        ),
        (
            'TX-1004',
            'ACC-1004',
            5200.00::NUMERIC,
            'CREDIT',
            'REJECTED',
            'Rejected transfer'
        ),
        (
            'TX-1005',
            'ACC-1001',
            17500.00::NUMERIC,
            'DEBIT',
            'PENDING',
            'Service payment'
        )
) AS v(
    reference,
    account_number,
    amount,
    transaction_type,
    transaction_status,
    description
)
JOIN accounts a
    ON a.account_number = v.account_number
ON CONFLICT DO NOTHING;


/* ============================================================
   8. EQUALITY-BASED HASH INDEX RETRIEVAL
   ============================================================ */

-- Equality lookup on the hash-indexed reference column.
SELECT *
FROM find_transaction_by_reference('TX-1001');


-- Direct account lookup using a hash index.
SELECT
    account_number,
    customer_id,
    balance
FROM accounts
WHERE account_number = 'ACC-1001';


-- Customer equality lookup.
SELECT
    customer_code,
    full_name
FROM customers
WHERE customer_code = 'CUST-1001';


/* ============================================================
   9. VALIDATION QUERIES
   ============================================================ */

-- Duplicate transaction references.
SELECT
    transaction_reference,
    COUNT(*) AS duplicate_count
FROM transactions
GROUP BY transaction_reference
HAVING COUNT(*) > 1;


-- Transactions referencing invalid or missing accounts.
SELECT t.transaction_reference
FROM transactions t
LEFT JOIN accounts a
    ON a.account_id = t.account_id
WHERE a.account_id IS NULL;


-- Check transaction amounts and statuses.
SELECT
    transaction_reference,
    amount,
    transaction_status
FROM transactions
WHERE amount <= 0
   OR transaction_status NOT IN (
       'PENDING',
       'APPROVED',
       'REJECTED',
       'SETTLED'
   );


/* ============================================================
   10. AGGREGATION AND REPORTING
   ============================================================ */

SELECT *
FROM transaction_index_report
ORDER BY customer_code, account_number;


SELECT
    transaction_status,
    COUNT(*) AS total_transactions,
    SUM(amount) AS total_amount,
    AVG(amount) AS average_amount
FROM transactions
GROUP BY transaction_status
ORDER BY transaction_status;


-- Equality lookup combined with aggregation.
SELECT
    account_id,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount
FROM transactions
WHERE transaction_status = 'APPROVED'
GROUP BY account_id;


/* ============================================================
   11. HASH INDEX METADATA
   ============================================================ */

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'hash_index_lab'
ORDER BY indexname;


-- Inspect hash index metadata and physical size.
SELECT
    indexrelid::regclass AS index_name,
    relpages,
    reltuples,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_index
WHERE indrelid = 'hash_index_lab.transactions'::regclass;


-- Database statistics for index usage.
SELECT
    indexrelname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'hash_index_lab'
ORDER BY idx_scan DESC;


/* ============================================================
   12. QUERY PLAN COMPARISON
   ============================================================ */

-- The planner chooses an access method based on estimated cost.
-- ANALYZE and realistic table size influence the decision.

ANALYZE customers;
ANALYZE accounts;
ANALYZE transactions;

EXPLAIN
SELECT *
FROM transactions
WHERE transaction_reference = 'TX-1001';


EXPLAIN
SELECT *
FROM transactions
WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
ORDER BY created_at DESC;


-- A sequential scan can be preferable for small tables.
-- Do not assume that every hash-indexed equality lookup uses
-- its hash index.


/* ============================================================
   13. HASH INDEX AND BTREE INDEX DISTINCTIONS
   ============================================================ */

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'hash_index_lab'
  AND tablename = 'transactions';


/*
 * Hash:
 *   Supports equality comparisons.
 *   Does not support range or ordering operations.
 *
 * B-tree:
 *   Supports equality, range comparisons, sorting,
 *   and ordered scans.
 *
 * Unique constraints:
 *   Use an appropriate unique B-tree index.
 *
 * Hash indexes are not unique indexes.
 */


/* ============================================================
   14. TRANSACTIONAL WORKFLOW
   ============================================================ */

SAVEPOINT before_status_update;

CALL update_transaction_status(
    'TX-1002',
    'APPROVED'
);

-- Verify the updated record.
SELECT
    transaction_reference,
    transaction_status,
    updated_at
FROM transactions
WHERE transaction_reference = 'TX-1002';

-- Demonstrate savepoint rollback.
ROLLBACK TO SAVEPOINT before_status_update;

-- The transaction is committed after the validation queries.
RELEASE SAVEPOINT before_status_update;

COMMIT;


/* ============================================================
   15. FINAL VERIFICATION
   ============================================================ */

SET search_path TO hash_index_lab, public;

SELECT
    transaction_reference,
    transaction_status,
    amount
FROM transactions
ORDER BY transaction_reference;


SELECT
    operation,
    COUNT(*) AS audit_events
FROM index_audit
GROUP BY operation
ORDER BY operation;


SELECT
    COUNT(*) AS total_customers
FROM customers;


SELECT
    COUNT(*) AS total_accounts
FROM accounts;


SELECT
    COUNT(*) AS total_transactions
FROM transactions;
