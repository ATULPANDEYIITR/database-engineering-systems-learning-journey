-- =========================================================
-- OPTIMISTIC CONCURRENCY CONTROL
-- PostgreSQL 18 compatible implementation
--
-- Demonstrates:
--   1. Versioned records
--   2. Compare-and-swap updates
--   3. Lost-update prevention
--   4. Transaction conflicts
--   5. Automatic conflict detection
--   6. Retry-aware transaction workflows
--   7. Atomic multi-account operations
--   8. Audit logging
--   9. Inventory reservation
--  10. Conflict reporting
--
-- Execute using psql:
--   psql -v ON_ERROR_STOP=1 -d your_database -f optimistic_concurrency.sql
-- =========================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS concurrency_lab;

SET search_path TO concurrency_lab, public;


-- =========================================================
-- 1. ENUM TYPES
-- =========================================================

CREATE TYPE transaction_status AS ENUM (
    'PENDING',
    'COMMITTED',
    'CONFLICTED',
    'ABORTED'
);

CREATE TYPE operation_type AS ENUM (
    'CREATE',
    'UPDATE',
    'TRANSFER_DEBIT',
    'TRANSFER_CREDIT',
    'RESERVATION'
);


-- =========================================================
-- 2. CORE TABLES
-- =========================================================

CREATE TABLE repository_records (
    record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    external_key VARCHAR(100) NOT NULL UNIQUE,

    record_type VARCHAR(30) NOT NULL,

    payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    version BIGINT NOT NULL DEFAULT 1,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_version
        CHECK (version >= 1),

    CONSTRAINT valid_payload
        CHECK (jsonb_typeof(payload) = 'object'),

    CONSTRAINT valid_record_type
        CHECK (
            record_type IN (
                'ACCOUNT',
                'INVENTORY',
                'DOCUMENT',
                'CONFIGURATION'
            )
        )
);


CREATE TABLE transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    transaction_type VARCHAR(40) NOT NULL,

    status transaction_status NOT NULL DEFAULT 'PENDING',

    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    completed_at TIMESTAMPTZ,

    retry_count INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT valid_retry_count
        CHECK (retry_count >= 0)
);


CREATE TABLE concurrency_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id UUID REFERENCES transactions(transaction_id),

    record_id BIGINT REFERENCES repository_records(record_id),

    external_key VARCHAR(100) NOT NULL,

    old_version BIGINT,

    new_version BIGINT,

    operation operation_type NOT NULL,

    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_audit_version
        CHECK (
            old_version IS NULL
            OR new_version IS NULL
            OR new_version > old_version
        )
);


CREATE TABLE conflict_events (
    conflict_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id UUID REFERENCES transactions(transaction_id),

    record_id BIGINT REFERENCES repository_records(record_id),

    external_key VARCHAR(100) NOT NULL,

    expected_version BIGINT NOT NULL,

    actual_version BIGINT NOT NULL,

    conflict_reason TEXT NOT NULL,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT expected_version_positive
        CHECK (expected_version >= 1),

    CONSTRAINT actual_version_positive
        CHECK (actual_version >= 1),

    CONSTRAINT versions_differ
        CHECK (expected_version <> actual_version)
);


-- =========================================================
-- 3. BUSINESS TABLES
-- =========================================================

CREATE TABLE accounts (
    account_id BIGINT PRIMARY KEY
        REFERENCES repository_records(record_id),

    account_number VARCHAR(30) NOT NULL UNIQUE,

    balance NUMERIC(18,2) NOT NULL,

    CONSTRAINT non_negative_balance
        CHECK (balance >= 0)
);


CREATE TABLE inventory (
    inventory_id BIGINT PRIMARY KEY
        REFERENCES repository_records(record_id),

    sku VARCHAR(50) NOT NULL UNIQUE,

    available_quantity INTEGER NOT NULL,

    reserved_quantity INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT valid_available_quantity
        CHECK (available_quantity >= 0),

    CONSTRAINT valid_reserved_quantity
        CHECK (reserved_quantity >= 0)
);


-- =========================================================
-- 4. INDEXES
-- =========================================================

CREATE INDEX idx_records_external_key
    ON repository_records(external_key);

CREATE INDEX idx_records_type_updated
    ON repository_records(record_type, updated_at DESC);

CREATE INDEX idx_audit_record_created
    ON concurrency_audit(record_id, created_at DESC);

CREATE INDEX idx_audit_transaction
    ON concurrency_audit(transaction_id);

CREATE INDEX idx_conflicts_record_detected
    ON conflict_events(record_id, detected_at DESC);

CREATE INDEX idx_transactions_status
    ON transactions(status, started_at DESC);


-- =========================================================
-- 5. VERSIONED RECORD CREATION
-- =========================================================

CREATE OR REPLACE FUNCTION create_versioned_record(
    p_external_key VARCHAR,
    p_record_type VARCHAR,
    p_payload JSONB
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_record_id BIGINT;
    v_transaction_id UUID;
BEGIN

    IF p_external_key IS NULL OR length(trim(p_external_key)) = 0 THEN
        RAISE EXCEPTION 'External key is required.';
    END IF;

    IF p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object' THEN
        RAISE EXCEPTION 'Payload must be a JSON object.';
    END IF;

    INSERT INTO transactions(transaction_type, status)
    VALUES ('CREATE_RECORD', 'PENDING')
    RETURNING transaction_id INTO v_transaction_id;

    INSERT INTO repository_records(
        external_key,
        record_type,
        payload,
        version
    )
    VALUES (
        p_external_key,
        p_record_type,
        p_payload,
        1
    )
    RETURNING record_id INTO v_record_id;

    INSERT INTO concurrency_audit(
        transaction_id,
        record_id,
        external_key,
        old_version,
        new_version,
        operation,
        event_data
    )
    VALUES (
        v_transaction_id,
        v_record_id,
        p_external_key,
        NULL,
        1,
        'CREATE',
        p_payload
    );

    UPDATE transactions
    SET status = 'COMMITTED',
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = v_transaction_id;

    RETURN v_record_id;

END;
$$;


-- =========================================================
-- 6. ATOMIC COMPARE-AND-SWAP FUNCTION
-- =========================================================

CREATE OR REPLACE FUNCTION compare_and_swap(
    p_external_key VARCHAR,
    p_expected_version BIGINT,
    p_new_payload JSONB,
    p_transaction_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_record repository_records%ROWTYPE;
    v_new_version BIGINT;
BEGIN

    IF p_expected_version < 1 THEN
        RAISE EXCEPTION 'Expected version must be positive.';
    END IF;

    IF p_new_payload IS NULL
       OR jsonb_typeof(p_new_payload) <> 'object' THEN
        RAISE EXCEPTION 'New payload must be a JSON object.';
    END IF;

    SELECT *
    INTO v_record
    FROM repository_records
    WHERE external_key = p_external_key
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Record not found: %', p_external_key;
    END IF;

    -- The row lock serializes competing writers.
    -- The version predicate prevents stale updates.
    IF v_record.version <> p_expected_version THEN

        INSERT INTO conflict_events(
            transaction_id,
            record_id,
            external_key,
            expected_version,
            actual_version,
            conflict_reason
        )
        VALUES (
            p_transaction_id,
            v_record.record_id,
            p_external_key,
            p_expected_version,
            v_record.version,
            'Expected version differs from stored version.'
        );

        UPDATE transactions
        SET status = 'CONFLICTED'
        WHERE transaction_id = p_transaction_id
          AND status = 'PENDING';

        RETURN FALSE;
    END IF;

    UPDATE repository_records
    SET payload = p_new_payload,
        version = version + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE record_id = v_record.record_id
      AND version = p_expected_version
    RETURNING version INTO v_new_version;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    INSERT INTO concurrency_audit(
        transaction_id,
        record_id,
        external_key,
        old_version,
        new_version,
        operation,
        event_data
    )
    VALUES (
        p_transaction_id,
        v_record.record_id,
        p_external_key,
        p_expected_version,
        v_new_version,
        'UPDATE',
        p_new_payload
    );

    UPDATE transactions
    SET status = 'COMMITTED',
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = p_transaction_id;

    RETURN TRUE;

END;
$$;


-- =========================================================
-- 7. VERSION VALIDATION TRIGGER
-- =========================================================

CREATE OR REPLACE FUNCTION enforce_version_increment()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    IF NEW.version < OLD.version THEN
        RAISE EXCEPTION 'Version cannot decrease.';
    END IF;

    IF NEW.version > OLD.version + 1 THEN
        RAISE EXCEPTION 'Version cannot skip increments.';
    END IF;

    IF NEW.version = OLD.version
       AND NEW.payload IS DISTINCT FROM OLD.payload THEN
        RAISE EXCEPTION
            'Payload changes require a version increment.';
    END IF;

    IF NEW.version = OLD.version + 1
       AND NEW.payload IS NOT DISTINCT FROM OLD.payload THEN
        RAISE EXCEPTION
            'Version increment requires a payload change.';
    END IF;

    NEW.updated_at = CURRENT_TIMESTAMP;

    RETURN NEW;

END;
$$;


CREATE TRIGGER trg_version_integrity
BEFORE UPDATE ON repository_records
FOR EACH ROW
EXECUTE FUNCTION enforce_version_increment();


-- =========================================================
-- 8. ACCOUNT UPDATE FUNCTION
-- =========================================================

CREATE OR REPLACE FUNCTION update_account_balance(
    p_account_number VARCHAR,
    p_expected_version BIGINT,
    p_new_balance NUMERIC,
    p_transaction_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_account_id BIGINT;
    v_current_version BIGINT;
BEGIN

    IF p_new_balance < 0 THEN
        RAISE EXCEPTION 'Balance cannot be negative.';
    END IF;

    SELECT r.record_id, r.version
    INTO v_account_id, v_current_version
    FROM accounts a
    JOIN repository_records r
      ON r.record_id = a.account_id
    WHERE a.account_number = p_account_number
    FOR UPDATE OF r, a;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Account not found.';
    END IF;

    IF v_current_version <> p_expected_version THEN

        INSERT INTO conflict_events(
            transaction_id,
            record_id,
            external_key,
            expected_version,
            actual_version,
            conflict_reason
        )
        SELECT
            p_transaction_id,
            v_account_id,
            external_key,
            p_expected_version,
            v_current_version,
            'Stale account version.'
        FROM repository_records
        WHERE record_id = v_account_id;

        UPDATE transactions
        SET status = 'CONFLICTED'
        WHERE transaction_id = p_transaction_id
          AND status = 'PENDING';

        RETURN FALSE;
    END IF;

    UPDATE repository_records
    SET payload = jsonb_build_object(
        'balance',
        p_new_balance
    ),
    version = version + 1
    WHERE record_id = v_account_id
      AND version = p_expected_version;

    UPDATE accounts
    SET balance = p_new_balance
    WHERE account_id = v_account_id;

    INSERT INTO concurrency_audit(
        transaction_id,
        record_id,
        external_key,
        old_version,
        new_version,
        operation,
        event_data
    )
    SELECT
        p_transaction_id,
        v_account_id,
        external_key,
        p_expected_version,
        p_expected_version + 1,
        'UPDATE',
        jsonb_build_object('balance', p_new_balance)
    FROM repository_records
    WHERE record_id = v_account_id;

    UPDATE transactions
    SET status = 'COMMITTED',
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = p_transaction_id;

    RETURN TRUE;

END;
$$;


-- =========================================================
-- 9. ATOMIC MULTI-ACCOUNT TRANSFER PROCEDURE
-- =========================================================

CREATE OR REPLACE PROCEDURE transfer_funds(
    p_source VARCHAR,
    p_destination VARCHAR,
    p_amount NUMERIC
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_source accounts%ROWTYPE;
    v_destination accounts%ROWTYPE;

    v_transaction_id UUID;
    v_source_record_id BIGINT;
    v_destination_record_id BIGINT;

    v_source_version BIGINT;
    v_destination_version BIGINT;
BEGIN

    IF p_source = p_destination THEN
        RAISE EXCEPTION 'Source and destination must differ.';
    END IF;

    IF p_amount IS NULL OR p_amount <= 0 THEN
        RAISE EXCEPTION 'Transfer amount must be positive.';
    END IF;

    INSERT INTO transactions(transaction_type)
    VALUES ('ACCOUNT_TRANSFER')
    RETURNING transaction_id INTO v_transaction_id;

    -- Deterministic locking order reduces deadlock risk.
    PERFORM 1
    FROM accounts
    WHERE account_number IN (p_source, p_destination)
    ORDER BY account_id
    FOR UPDATE;

    SELECT *
    INTO v_source
    FROM accounts
    WHERE account_number = p_source;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Source account not found.';
    END IF;

    SELECT *
    INTO v_destination
    FROM accounts
    WHERE account_number = p_destination;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Destination account not found.';
    END IF;

    IF v_source.balance < p_amount THEN
        RAISE EXCEPTION 'Insufficient funds.';
    END IF;

    SELECT r.record_id, r.version
    INTO v_source_record_id, v_source_version
    FROM repository_records r
    WHERE r.record_id = v_source.account_id
    FOR UPDATE;

    SELECT r.record_id, r.version
    INTO v_destination_record_id, v_destination_version
    FROM repository_records r
    WHERE r.record_id = v_destination.account_id
    FOR UPDATE;

    -- Both business records and their versioned representations
    -- change within the same database transaction.

    UPDATE accounts
    SET balance = balance - p_amount
    WHERE account_id = v_source.account_id;

    UPDATE accounts
    SET balance = balance + p_amount
    WHERE account_id = v_destination.account_id;

    UPDATE repository_records
    SET payload = jsonb_build_object(
        'balance',
        v_source.balance - p_amount
    ),
    version = version + 1
    WHERE record_id = v_source_record_id
      AND version = v_source_version;

    UPDATE repository_records
    SET payload = jsonb_build_object(
        'balance',
        v_destination.balance + p_amount
    ),
    version = version + 1
    WHERE record_id = v_destination_record_id
      AND version = v_destination_version;

    INSERT INTO concurrency_audit(
        transaction_id,
        record_id,
        external_key,
        old_version,
        new_version,
        operation,
        event_data
    )
    SELECT
        v_transaction_id,
        record_id,
        external_key,
        version - 1,
        version,
        CASE
            WHEN record_id = v_source_record_id
                THEN 'TRANSFER_DEBIT'::operation_type
            ELSE 'TRANSFER_CREDIT'::operation_type
        END,
        payload
    FROM repository_records
    WHERE record_id IN (
        v_source_record_id,
        v_destination_record_id
    );

    UPDATE transactions
    SET status = 'COMMITTED',
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = v_transaction_id;

EXCEPTION
    WHEN OTHERS THEN

        UPDATE transactions
        SET status = 'ABORTED',
            completed_at = CURRENT_TIMESTAMP
        WHERE transaction_id = v_transaction_id;

        RAISE;

END;
$$;


-- =========================================================
-- 10. INVENTORY RESERVATION
-- =========================================================

CREATE OR REPLACE FUNCTION reserve_inventory(
    p_sku VARCHAR,
    p_quantity INTEGER,
    p_expected_version BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_inventory inventory%ROWTYPE;
    v_transaction_id UUID;
    v_actual_version BIGINT;
BEGIN

    IF p_quantity IS NULL OR p_quantity <= 0 THEN
        RAISE EXCEPTION 'Reservation quantity must be positive.';
    END IF;

    INSERT INTO transactions(transaction_type)
    VALUES ('INVENTORY_RESERVATION')
    RETURNING transaction_id INTO v_transaction_id;

    SELECT i.*
    INTO v_inventory
    FROM inventory i
    WHERE i.sku = p_sku
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Inventory item not found.';
    END IF;

    SELECT version
    INTO v_actual_version
    FROM repository_records
    WHERE record_id = v_inventory.inventory_id
    FOR UPDATE;

    IF v_actual_version <> p_expected_version THEN

        INSERT INTO conflict_events(
            transaction_id,
            record_id,
            external_key,
            expected_version,
            actual_version,
            conflict_reason
        )
        SELECT
            v_transaction_id,
            record_id,
            external_key,
            p_expected_version,
            v_actual_version,
            'Inventory version mismatch.'
        FROM repository_records
        WHERE record_id = v_inventory.inventory_id;

        UPDATE transactions
        SET status = 'CONFLICTED'
        WHERE transaction_id = v_transaction_id;

        RETURN FALSE;
    END IF;

    IF v_inventory.available_quantity < p_quantity THEN

        UPDATE transactions
        SET status = 'ABORTED',
            completed_at = CURRENT_TIMESTAMP
        WHERE transaction_id = v_transaction_id;

        RETURN FALSE;
    END IF;

    UPDATE inventory
    SET available_quantity = available_quantity - p_quantity,
        reserved_quantity = reserved_quantity + p_quantity
    WHERE inventory_id = v_inventory.inventory_id;

    UPDATE repository_records
    SET payload = jsonb_build_object(
        'available_quantity',
        v_inventory.available_quantity - p_quantity,
        'reserved_quantity',
        v_inventory.reserved_quantity + p_quantity
    ),
    version = version + 1
    WHERE record_id = v_inventory.inventory_id
      AND version = p_expected_version;

    INSERT INTO concurrency_audit(
        transaction_id,
        record_id,
        external_key,
        old_version,
        new_version,
        operation,
        event_data
    )
    SELECT
        v_transaction_id,
        record_id,
        external_key,
        p_expected_version,
        p_expected_version + 1,
        'RESERVATION',
        payload
    FROM repository_records
    WHERE record_id = v_inventory.inventory_id;

    UPDATE transactions
    SET status = 'COMMITTED',
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = v_transaction_id;

    RETURN TRUE;

END;
$$;


-- =========================================================
-- 11. REPORTING VIEWS
-- =========================================================

CREATE OR REPLACE VIEW versioned_record_report AS
SELECT
    r.record_id,
    r.external_key,
    r.record_type,
    r.version,
    r.payload,
    r.created_at,
    r.updated_at,
    COUNT(a.audit_id) AS modification_count,
    MAX(a.created_at) AS last_audit_time
FROM repository_records r
LEFT JOIN concurrency_audit a
    ON a.record_id = r.record_id
GROUP BY
    r.record_id,
    r.external_key,
    r.record_type,
    r.version,
    r.payload,
    r.created_at,
    r.updated_at;


CREATE OR REPLACE VIEW concurrency_conflict_report AS
SELECT
    c.conflict_id,
    c.external_key,
    c.expected_version,
    c.actual_version,
    c.actual_version - c.expected_version AS version_difference,
    c.conflict_reason,
    c.detected_at,
    t.transaction_type,
    t.status
FROM conflict_events c
LEFT JOIN transactions t
    ON t.transaction_id = c.transaction_id;


CREATE OR REPLACE VIEW account_balance_report AS
SELECT
    a.account_number,
    a.balance,
    r.version,
    r.updated_at
FROM accounts a
JOIN repository_records r
    ON r.record_id = a.account_id;


-- =========================================================
-- 12. SAMPLE RECORDS
-- =========================================================

INSERT INTO repository_records(
    external_key,
    record_type,
    payload
)
VALUES
(
    'ACC-001',
    'ACCOUNT',
    '{"balance":5000}'::jsonb
),
(
    'ACC-002',
    'ACCOUNT',
    '{"balance":2000}'::jsonb
),
(
    'SKU-001',
    'INVENTORY',
    '{"available_quantity":100,"reserved_quantity":0}'::jsonb
),
(
    'DOC-001',
    'DOCUMENT',
    '{"title":"Quarterly Report","state":"DRAFT"}'::jsonb
);


INSERT INTO accounts(
    account_id,
    account_number,
    balance
)
SELECT
    record_id,
    external_key,
    (payload->>'balance')::NUMERIC
FROM repository_records
WHERE record_type = 'ACCOUNT';


INSERT INTO inventory(
    inventory_id,
    sku,
    available_quantity,
    reserved_quantity
)
SELECT
    record_id,
    external_key,
    (payload->>'available_quantity')::INTEGER,
    (payload->>'reserved_quantity')::INTEGER
FROM repository_records
WHERE record_type = 'INVENTORY';


-- =========================================================
-- 13. SAMPLE TRANSACTION RECORDS
-- =========================================================

INSERT INTO transactions(
    transaction_id,
    transaction_type,
    status,
    completed_at
)
VALUES
(
    '00000000-0000-0000-0000-000000000001',
    'DOCUMENT_UPDATE',
    'PENDING',
    NULL
),
(
    '00000000-0000-0000-0000-000000000002',
    'DOCUMENT_UPDATE',
    'COMMITTED',
    CURRENT_TIMESTAMP
),
(
    '00000000-0000-0000-0000-000000000003',
    'DOCUMENT_UPDATE',
    'CONFLICTED',
    CURRENT_TIMESTAMP
);


COMMIT;


-- =========================================================
-- 14. INITIAL AUDIT
-- =========================================================

INSERT INTO concurrency_audit(
    record_id,
    external_key,
    old_version,
    new_version,
    operation,
    event_data
)
SELECT
    record_id,
    external_key,
    NULL,
    version,
    'CREATE',
    payload
FROM repository_records;


-- =========================================================
-- 15. RETRIEVAL QUERIES
-- =========================================================

-- Retrieve a complete versioned record.
SELECT
    record_id,
    external_key,
    record_type,
    payload,
    version,
    updated_at
FROM repository_records
WHERE external_key = 'ACC-001';


-- Retrieve modification history.
SELECT
    external_key,
    old_version,
    new_version,
    operation,
    transaction_id,
    created_at
FROM concurrency_audit
WHERE external_key = 'ACC-001'
ORDER BY created_at, audit_id;


-- =========================================================
-- 16. CONFLICT DETECTION DEMONSTRATION
-- =========================================================

-- Simulate two readers observing the same version.
-- Both initially read version 1.

INSERT INTO transactions(
    transaction_id,
    transaction_type,
    status
)
VALUES (
    '00000000-0000-0000-0000-000000000010',
    'CONCURRENT_UPDATE',
    'PENDING'
);

INSERT INTO transactions(
    transaction_id,
    transaction_type,
    status
)
VALUES (
    '00000000-0000-0000-0000-000000000011',
    'CONCURRENT_UPDATE',
    'PENDING'
);


-- First transaction commits version 1 -> 2.
SELECT compare_and_swap(
    'DOC-001',
    1,
    '{"title":"Quarterly Report","state":"REVIEW"}'::jsonb,
    '00000000-0000-0000-0000-000000000010'
);


-- Second transaction uses stale version 1.
-- Expected result: FALSE and a recorded conflict.
SELECT compare_and_swap(
    'DOC-001',
    1,
    '{"title":"Quarterly Report","state":"APPROVED"}'::jsonb,
    '00000000-0000-0000-0000-000000000011'
);


-- =========================================================
-- 17. CONFLICT REPORTING
-- =========================================================

SELECT
    external_key,
    expected_version,
    actual_version,
    conflict_reason,
    detected_at
FROM concurrency_conflict_report
ORDER BY detected_at DESC;


-- =========================================================
-- 18. TRANSACTIONAL ACCOUNT TRANSFER
-- =========================================================

BEGIN;

CALL transfer_funds(
    'ACC-001',
    'ACC-002',
    500.00
);

COMMIT;


-- Verify conservation of total account balance.
SELECT
    SUM(balance) AS total_balance
FROM accounts;


-- =========================================================
-- 19. INVENTORY RESERVATION
-- =========================================================

-- Retrieve the current inventory version.
SELECT
    r.external_key,
    r.version,
    i.available_quantity,
    i.reserved_quantity
FROM repository_records r
JOIN inventory i
    ON i.inventory_id = r.record_id
WHERE r.external_key = 'SKU-001';


-- Reserve ten units using the current version.
SELECT reserve_inventory(
    'SKU-001',
    10,
    1
);


-- =========================================================
-- 20. VALIDATION AND AGGREGATION
-- =========================================================

-- Identify inconsistent account representations.
SELECT
    a.account_number,
    a.balance AS relational_balance,
    (r.payload->>'balance')::NUMERIC AS document_balance
FROM accounts a
JOIN repository_records r
    ON r.record_id = a.account_id
WHERE a.balance IS DISTINCT FROM
      (r.payload->>'balance')::NUMERIC;


-- Identify inconsistent inventory representations.
SELECT
    i.sku,
    i.available_quantity,
    (r.payload->>'available_quantity')::INTEGER AS payload_available,
    i.reserved_quantity,
    (r.payload->>'reserved_quantity')::INTEGER AS payload_reserved
FROM inventory i
JOIN repository_records r
    ON r.record_id = i.inventory_id
WHERE i.available_quantity <>
      (r.payload->>'available_quantity')::INTEGER
   OR i.reserved_quantity <>
      (r.payload->>'reserved_quantity')::INTEGER;


-- Modification frequency.
SELECT
    external_key,
    COUNT(*) AS total_operations,
    COUNT(DISTINCT transaction_id) AS transaction_count
FROM concurrency_audit
GROUP BY external_key
ORDER BY total_operations DESC;


-- =========================================================
-- 21. WORKFLOW ELIGIBILITY
-- =========================================================

-- Records eligible for modification when the caller
-- possesses the current version.
CREATE OR REPLACE FUNCTION is_version_current(
    p_external_key VARCHAR,
    p_expected_version BIGINT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM repository_records
        WHERE external_key = p_external_key
          AND version = p_expected_version
    );
$$;


SELECT
    external_key,
    version,
    is_version_current(external_key, version) AS eligible,
    is_version_current(external_key, version - 1) AS stale_request
FROM repository_records;


-- =========================================================
-- 22. CONFLICT AND PERFORMANCE METRICS
-- =========================================================

SELECT
    COUNT(*) AS total_conflicts,
    COUNT(DISTINCT transaction_id) AS affected_transactions,
    COUNT(DISTINCT record_id) AS affected_records
FROM conflict_events;


SELECT
    status,
    COUNT(*) AS transaction_count,
    AVG(retry_count) AS average_retries
FROM transactions
GROUP BY status
ORDER BY status;


-- =========================================================
-- 23. SAMPLE CONFLICT TESTS
-- =========================================================

DO $$
DECLARE
    v_current_version BIGINT;
    v_transaction_id UUID;
    v_result BOOLEAN;
BEGIN

    SELECT version
    INTO v_current_version
    FROM repository_records
    WHERE external_key = 'DOC-001';

    INSERT INTO transactions(transaction_type)
    VALUES ('VALIDATION_TEST')
    RETURNING transaction_id INTO v_transaction_id;

    -- Current version should succeed.
    v_result := compare_and_swap(
        'DOC-001',
        v_current_version,
        '{"title":"Quarterly Report","state":"VALIDATED"}'::jsonb,
        v_transaction_id
    );

    IF NOT v_result THEN
        RAISE EXCEPTION 'Valid compare-and-swap failed.';
    END IF;

    -- The previous version must now be rejected.
    INSERT INTO transactions(transaction_type)
    VALUES ('STALE_VERSION_TEST')
    RETURNING transaction_id INTO v_transaction_id;

    v_result := compare_and_swap(
        'DOC-001',
        v_current_version,
        '{"title":"Quarterly Report","state":"STALE"}'::jsonb,
        v_transaction_id
    );

    IF v_result THEN
        RAISE EXCEPTION 'Stale update was incorrectly accepted.';
    END IF;

    RAISE NOTICE 'Optimistic concurrency tests passed.';

END;
$$;


-- =========================================================
-- 24. FINAL REPORT
-- =========================================================

SELECT * FROM versioned_record_report
ORDER BY record_id;

SELECT * FROM account_balance_report
ORDER BY account_number;

SELECT * FROM concurrency_conflict_report
ORDER BY detected_at DESC;

SELECT
    operation,
    COUNT(*) AS operation_count
FROM concurrency_audit
GROUP BY operation
ORDER BY operation;
