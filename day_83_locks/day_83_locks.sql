-- locks.sql
-- Shared Locks, Exclusive Locks, and Lock Compatibility
-- PostgreSQL 14+
--
-- Transaction locking model with:
--   1. Resource and transaction registries
--   2. Shared and exclusive lock modes
--   3. Explicit compatibility matrix
--   4. Lock requests and granted holdings
--   5. FIFO scheduling metadata
--   6. Upgrade conflict prevention
--   7. Resource-specific policies
--   8. Eligibility views and reporting
--
-- This schema models application-level logical locks.
-- PostgreSQL's native row locks and advisory locks remain separate mechanisms.

BEGIN;

DROP SCHEMA IF EXISTS lock_lab CASCADE;

CREATE SCHEMA lock_lab;

CREATE TYPE lock_lab.lock_mode AS ENUM ('S', 'X');

CREATE TYPE lock_lab.request_status AS ENUM (
    'WAITING',
    'GRANTED',
    'REJECTED',
    'CANCELLED'
);

CREATE TYPE lock_lab.transaction_status AS ENUM (
    'ACTIVE',
    'COMMITTED',
    'ROLLED_BACK'
);

-- ------------------------------------------------------------
-- 1. Core domain tables
-- ------------------------------------------------------------

CREATE TABLE lock_lab.repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name VARCHAR(150) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lock_lab.resources (
    resource_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT REFERENCES lock_lab.repositories(repository_id),
    resource_name VARCHAR(200) NOT NULL,
    resource_type VARCHAR(40) NOT NULL,
    allow_shared BOOLEAN NOT NULL DEFAULT TRUE,
    allow_exclusive BOOLEAN NOT NULL DEFAULT TRUE,
    allow_upgrade BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (repository_id, resource_name),
    CHECK (resource_type IN (
        'ACCOUNT',
        'INVENTORY',
        'ORDER',
        'DOCUMENT',
        'CONFIGURATION'
    ))
);

CREATE TABLE lock_lab.transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_reference VARCHAR(80) NOT NULL UNIQUE,
    application_name VARCHAR(100) NOT NULL,
    owner_name VARCHAR(100) NOT NULL,
    transaction_state lock_lab.transaction_status
        NOT NULL DEFAULT 'ACTIVE',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    CHECK (
        (transaction_state = 'ACTIVE' AND completed_at IS NULL)
        OR
        (transaction_state <> 'ACTIVE' AND completed_at IS NOT NULL)
    )
);

-- ------------------------------------------------------------
-- 2. Lock compatibility
-- ------------------------------------------------------------

CREATE TABLE lock_lab.lock_compatibility (
    requested_mode lock_lab.lock_mode NOT NULL,
    held_mode lock_lab.lock_mode NOT NULL,
    is_compatible BOOLEAN NOT NULL,
    PRIMARY KEY (requested_mode, held_mode)
);

INSERT INTO lock_lab.lock_compatibility
    (requested_mode, held_mode, is_compatible)
VALUES
    ('S', 'S', TRUE),
    ('S', 'X', FALSE),
    ('X', 'S', FALSE),
    ('X', 'X', FALSE);

-- ------------------------------------------------------------
-- 3. Granted locks
-- ------------------------------------------------------------

CREATE TABLE lock_lab.lock_holders (
    holder_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_id BIGINT NOT NULL
        REFERENCES lock_lab.resources(resource_id),
    transaction_id BIGINT NOT NULL
        REFERENCES lock_lab.transactions(transaction_id),
    mode lock_lab.lock_mode NOT NULL,
    acquisition_count INTEGER NOT NULL DEFAULT 1,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (resource_id, transaction_id),
    CHECK (acquisition_count > 0)
);

CREATE INDEX idx_lock_holders_resource_mode
ON lock_lab.lock_holders(resource_id, mode);

CREATE INDEX idx_lock_holders_transaction
ON lock_lab.lock_holders(transaction_id);

-- ------------------------------------------------------------
-- 4. Lock requests
-- ------------------------------------------------------------

CREATE TABLE lock_lab.lock_requests (
    request_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_id BIGINT NOT NULL
        REFERENCES lock_lab.resources(resource_id),
    transaction_id BIGINT NOT NULL
        REFERENCES lock_lab.transactions(transaction_id),
    requested_mode lock_lab.lock_mode NOT NULL,
    status lock_lab.request_status NOT NULL DEFAULT 'WAITING',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ,
    rejection_reason TEXT,
    CHECK (
        (status = 'WAITING' AND processed_at IS NULL)
        OR
        (status <> 'WAITING' AND processed_at IS NOT NULL)
    )
);

CREATE INDEX idx_lock_requests_queue
ON lock_lab.lock_requests(resource_id, request_id)
WHERE status = 'WAITING';

CREATE INDEX idx_lock_requests_transaction
ON lock_lab.lock_requests(transaction_id, status);

-- ------------------------------------------------------------
-- 5. Lock event history
-- ------------------------------------------------------------

CREATE TABLE lock_lab.lock_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resource_id BIGINT NOT NULL
        REFERENCES lock_lab.resources(resource_id),
    transaction_id BIGINT NOT NULL
        REFERENCES lock_lab.transactions(transaction_id),
    event_type VARCHAR(30) NOT NULL,
    lock_mode lock_lab.lock_mode,
    event_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (event_type IN (
        'REQUESTED',
        'GRANTED',
        'RELEASED',
        'REJECTED',
        'CANCELLED',
        'UPGRADED'
    ))
);

CREATE INDEX idx_lock_events_resource_time
ON lock_lab.lock_events(resource_id, event_time DESC);

-- ------------------------------------------------------------
-- 6. Validation trigger
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION lock_lab.validate_lock_holder()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_active BOOLEAN;
    v_allowed BOOLEAN;
    v_conflict BOOLEAN;
BEGIN
    SELECT transaction_state = 'ACTIVE'
    INTO v_active
    FROM lock_lab.transactions
    WHERE transaction_id = NEW.transaction_id;

    IF NOT COALESCE(v_active, FALSE) THEN
        RAISE EXCEPTION
            'Cannot grant a lock to an inactive transaction %',
            NEW.transaction_id;
    END IF;

    SELECT CASE
        WHEN NEW.mode = 'S' THEN allow_shared
        ELSE allow_exclusive
    END
    INTO v_allowed
    FROM lock_lab.resources
    WHERE resource_id = NEW.resource_id;

    IF NOT COALESCE(v_allowed, FALSE) THEN
        RAISE EXCEPTION
            'Requested lock mode is disabled for resource %',
            NEW.resource_id;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM lock_lab.lock_holders h
        JOIN lock_lab.lock_compatibility c
          ON c.requested_mode = NEW.mode
         AND c.held_mode = h.mode
        WHERE h.resource_id = NEW.resource_id
          AND h.transaction_id <> NEW.transaction_id
          AND NOT c.is_compatible
    )
    INTO v_conflict;

    IF v_conflict THEN
        RAISE EXCEPTION
            'Incompatible lock already exists for resource %',
            NEW.resource_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_lock_holder
BEFORE INSERT OR UPDATE OF resource_id, transaction_id, mode
ON lock_lab.lock_holders
FOR EACH ROW
EXECUTE FUNCTION lock_lab.validate_lock_holder();

-- ------------------------------------------------------------
-- 7. Request acquisition function
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION lock_lab.request_lock(
    p_transaction_id BIGINT,
    p_resource_id BIGINT,
    p_mode lock_lab.lock_mode
)
RETURNS TABLE (
    result_status lock_lab.request_status,
    result_request_id BIGINT,
    result_message TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_state lock_lab.transaction_status;
    v_resource lock_lab.resources%ROWTYPE;
    v_holder lock_lab.lock_holders%ROWTYPE;
    v_request_id BIGINT;
    v_conflict BOOLEAN;
    v_blocked_by_queue BOOLEAN;
    v_upgrade BOOLEAN := FALSE;
BEGIN
    -- Validate the transaction.
    SELECT transaction_state
    INTO v_transaction_state
    FROM lock_lab.transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND OR v_transaction_state <> 'ACTIVE' THEN
        RAISE EXCEPTION
            'Transaction % is missing or inactive',
            p_transaction_id;
    END IF;

    -- Serialize lock decisions for one logical resource.
    SELECT *
    INTO v_resource
    FROM lock_lab.resources
    WHERE resource_id = p_resource_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown resource %', p_resource_id;
    END IF;

    IF p_mode = 'S' AND NOT v_resource.allow_shared THEN
        RAISE EXCEPTION 'Shared locks are disabled for this resource';
    END IF;

    IF p_mode = 'X' AND NOT v_resource.allow_exclusive THEN
        RAISE EXCEPTION 'Exclusive locks are disabled for this resource';
    END IF;

    SELECT *
    INTO v_holder
    FROM lock_lab.lock_holders
    WHERE resource_id = p_resource_id
      AND transaction_id = p_transaction_id
    FOR UPDATE;

    IF FOUND THEN
        IF v_holder.mode = 'X' OR p_mode = 'S' THEN
            UPDATE lock_lab.lock_holders
            SET acquisition_count = acquisition_count + 1
            WHERE holder_id = v_holder.holder_id;

            RETURN QUERY
            SELECT
                'GRANTED'::lock_lab.request_status,
                NULL::BIGINT,
                'Reentrant acquisition granted'::TEXT;

            RETURN;
        END IF;

        v_upgrade := TRUE;

        IF NOT v_resource.allow_upgrade THEN
            RETURN QUERY
            SELECT
                'REJECTED'::lock_lab.request_status,
                NULL::BIGINT,
                'Lock upgrade disabled by policy'::TEXT;

            RETURN;
        END IF;

        IF EXISTS (
            SELECT 1
            FROM lock_lab.lock_holders h
            WHERE h.resource_id = p_resource_id
              AND h.transaction_id <> p_transaction_id
        ) THEN
            RETURN QUERY
            SELECT
                'REJECTED'::lock_lab.request_status,
                NULL::BIGINT,
                'Upgrade rejected because competing holders exist'::TEXT;

            RETURN;
        END IF;
    END IF;

    -- Evaluate the compatibility matrix.
    SELECT EXISTS (
        SELECT 1
        FROM lock_lab.lock_holders h
        JOIN lock_lab.lock_compatibility c
          ON c.requested_mode = p_mode
         AND c.held_mode = h.mode
        WHERE h.resource_id = p_resource_id
          AND h.transaction_id <> p_transaction_id
          AND NOT c.is_compatible
    )
    INTO v_conflict;

    -- Prevent an exclusive request from being bypassed by later readers.
    SELECT EXISTS (
        SELECT 1
        FROM lock_lab.lock_requests q
        WHERE q.resource_id = p_resource_id
          AND q.status = 'WAITING'
          AND (
              q.requested_mode = 'X'
              OR p_mode = 'X'
          )
    )
    INTO v_blocked_by_queue;

    INSERT INTO lock_lab.lock_requests (
        resource_id,
        transaction_id,
        requested_mode,
        status,
        processed_at,
        rejection_reason
    )
    VALUES (
        p_resource_id,
        p_transaction_id,
        p_mode,
        CASE
            WHEN NOT v_conflict AND NOT v_blocked_by_queue
                THEN 'GRANTED'::lock_lab.request_status
            ELSE 'WAITING'::lock_lab.request_status
        END,
        CASE
            WHEN NOT v_conflict AND NOT v_blocked_by_queue
                THEN CURRENT_TIMESTAMP
            ELSE NULL
        END,
        NULL
    )
    RETURNING request_id INTO v_request_id;

    INSERT INTO lock_lab.lock_events (
        resource_id,
        transaction_id,
        event_type,
        lock_mode,
        details
    )
    VALUES (
        p_resource_id,
        p_transaction_id,
        'REQUESTED',
        p_mode,
        jsonb_build_object('upgrade', v_upgrade)
    );

    IF NOT v_conflict AND NOT v_blocked_by_queue THEN
        IF v_upgrade THEN
            UPDATE lock_lab.lock_holders
            SET mode = 'X',
                acquisition_count = 1
            WHERE holder_id = v_holder.holder_id;
        ELSE
            INSERT INTO lock_lab.lock_holders (
                resource_id,
                transaction_id,
                mode
            )
            VALUES (
                p_resource_id,
                p_transaction_id,
                p_mode
            );
        END IF;

        INSERT INTO lock_lab.lock_events (
            resource_id,
            transaction_id,
            event_type,
            lock_mode
        )
        VALUES (
            p_resource_id,
            p_transaction_id,
            CASE WHEN v_upgrade THEN 'UPGRADED' ELSE 'GRANTED' END,
            p_mode
        );

        RETURN QUERY
        SELECT
            'GRANTED'::lock_lab.request_status,
            v_request_id,
            'Lock successfully granted'::TEXT;
    ELSE
        RETURN QUERY
        SELECT
            'WAITING'::lock_lab.request_status,
            v_request_id,
            'Lock request queued; acquisition is not yet granted'::TEXT;
    END IF;
END;
$$;

-- ------------------------------------------------------------
-- 8. Release function
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION lock_lab.release_lock(
    p_transaction_id BIGINT,
    p_resource_id BIGINT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_holder lock_lab.lock_holders%ROWTYPE;
BEGIN
    PERFORM 1
    FROM lock_lab.resources
    WHERE resource_id = p_resource_id
    FOR UPDATE;

    SELECT *
    INTO v_holder
    FROM lock_lab.lock_holders
    WHERE resource_id = p_resource_id
      AND transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF v_holder.acquisition_count > 1 THEN
        UPDATE lock_lab.lock_holders
        SET acquisition_count = acquisition_count - 1
        WHERE holder_id = v_holder.holder_id;
    ELSE
        DELETE FROM lock_lab.lock_holders
        WHERE holder_id = v_holder.holder_id;
    END IF;

    INSERT INTO lock_lab.lock_events (
        resource_id,
        transaction_id,
        event_type,
        lock_mode
    )
    VALUES (
        p_resource_id,
        p_transaction_id,
        'RELEASED',
        v_holder.mode
    );

    RETURN TRUE;
END;
$$;

-- ------------------------------------------------------------
-- 9. Transaction completion
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION lock_lab.finish_transaction(
    p_transaction_id BIGINT,
    p_final_state lock_lab.transaction_status
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_resource_id BIGINT;
BEGIN
    IF p_final_state = 'ACTIVE' THEN
        RAISE EXCEPTION
            'Final state must be COMMITTED or ROLLED_BACK';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM lock_lab.transactions
        WHERE transaction_id = p_transaction_id
          AND transaction_state = 'ACTIVE'
    ) THEN
        RAISE EXCEPTION 'Transaction is not active';
    END IF;

    -- Release resources in deterministic order.
    FOR v_resource_id IN
        SELECT DISTINCT resource_id
        FROM lock_lab.lock_holders
        WHERE transaction_id = p_transaction_id
        ORDER BY resource_id
    LOOP
        PERFORM 1
        FROM lock_lab.resources
        WHERE resource_id = v_resource_id
        FOR UPDATE;

        DELETE FROM lock_lab.lock_holders
        WHERE resource_id = v_resource_id
          AND transaction_id = p_transaction_id;

        UPDATE lock_lab.lock_requests
        SET status = 'CANCELLED',
            processed_at = CURRENT_TIMESTAMP
        WHERE resource_id = v_resource_id
          AND transaction_id = p_transaction_id
          AND status = 'WAITING';
    END LOOP;

    UPDATE lock_lab.transactions
    SET transaction_state = p_final_state,
        completed_at = CURRENT_TIMESTAMP
    WHERE transaction_id = p_transaction_id;
END;
$$;

-- ------------------------------------------------------------
-- 10. Views
-- ------------------------------------------------------------

CREATE VIEW lock_lab.current_lock_table AS
SELECT
    r.resource_id,
    r.resource_name,
    h.transaction_id,
    t.transaction_reference,
    h.mode,
    h.acquisition_count,
    h.acquired_at
FROM lock_lab.resources r
JOIN lock_lab.lock_holders h
  ON h.resource_id = r.resource_id
JOIN lock_lab.transactions t
  ON t.transaction_id = h.transaction_id;

CREATE VIEW lock_lab.waiting_lock_requests AS
SELECT
    q.request_id,
    r.resource_name,
    t.transaction_reference,
    q.requested_mode,
    q.requested_at,
    q.status
FROM lock_lab.lock_requests q
JOIN lock_lab.resources r
  ON r.resource_id = q.resource_id
JOIN lock_lab.transactions t
  ON t.transaction_id = q.transaction_id
WHERE q.status = 'WAITING';

CREATE VIEW lock_lab.lock_compatibility_report AS
SELECT
    requested_mode,
    held_mode,
    is_compatible,
    CASE
        WHEN is_compatible THEN 'COMPATIBLE'
        ELSE 'CONFLICT'
    END AS interpretation
FROM lock_lab.lock_compatibility;

CREATE VIEW lock_lab.resource_contention_report AS
SELECT
    r.resource_name,
    COUNT(DISTINCT h.transaction_id) AS active_holders,
    COUNT(DISTINCT q.request_id)
        FILTER (WHERE q.status = 'WAITING') AS waiting_requests,
    COUNT(DISTINCT h.transaction_id)
        FILTER (WHERE h.mode = 'S') AS shared_holders,
    COUNT(DISTINCT h.transaction_id)
        FILTER (WHERE h.mode = 'X') AS exclusive_holders
FROM lock_lab.resources r
LEFT JOIN lock_lab.lock_holders h
  ON h.resource_id = r.resource_id
LEFT JOIN lock_lab.lock_requests q
  ON q.resource_id = r.resource_id
GROUP BY r.resource_id, r.resource_name;

-- ------------------------------------------------------------
-- 11. Sample domain data
-- ------------------------------------------------------------

INSERT INTO lock_lab.repositories (repository_name)
VALUES
    ('banking-ledger'),
    ('inventory-platform');

INSERT INTO lock_lab.resources (
    repository_id,
    resource_name,
    resource_type,
    allow_shared,
    allow_exclusive,
    allow_upgrade
)
SELECT
    repository_id,
    resource_name,
    resource_type,
    TRUE,
    TRUE,
    FALSE
FROM lock_lab.repositories
CROSS JOIN (
    VALUES
        ('account:1001', 'ACCOUNT'),
        ('inventory:500', 'INVENTORY'),
        ('order:9001', 'ORDER'),
        ('configuration:global', 'CONFIGURATION')
) AS resource_data(resource_name, resource_type);

INSERT INTO lock_lab.transactions (
    transaction_reference,
    application_name,
    owner_name
)
VALUES
    ('TXN-100', 'statement-service', 'reader-a'),
    ('TXN-200', 'statement-service', 'reader-b'),
    ('TXN-300', 'payment-service', 'payment-writer'),
    ('TXN-400', 'inventory-service', 'stock-reader'),
    ('TXN-500', 'inventory-service', 'stock-writer');

-- ------------------------------------------------------------
-- 12. Compatibility retrieval
-- ------------------------------------------------------------

SELECT *
FROM lock_lab.lock_compatibility_report
ORDER BY requested_mode, held_mode;

-- ------------------------------------------------------------
-- 13. Shared lock demonstration
-- ------------------------------------------------------------

SELECT *
FROM lock_lab.request_lock(
    1,
    (
        SELECT resource_id
        FROM lock_lab.resources
        WHERE resource_name = 'account:1001'
    ),
    'S'
);

SELECT *
FROM lock_lab.request_lock(
    2,
    (
        SELECT resource_id
        FROM lock_lab.resources
        WHERE resource_name = 'account:1001'
    ),
    'S'
);

-- ------------------------------------------------------------
-- 14. Exclusive lock conflict
-- ------------------------------------------------------------

SELECT *
FROM lock_lab.request_lock(
    3,
    (
        SELECT resource_id
        FROM lock_lab.resources
        WHERE resource_name = 'account:1001'
    ),
    'X'
);

-- The request remains WAITING because two shared locks exist.

SELECT *
FROM lock_lab.current_lock_table;

SELECT *
FROM lock_lab.waiting_lock_requests;

-- ------------------------------------------------------------
-- 15. Independent resource access
-- ------------------------------------------------------------

SELECT *
FROM lock_lab.request_lock(
    4,
    (
        SELECT resource_id
        FROM lock_lab.resources
        WHERE resource_name = 'inventory:500'
    ),
    'S'
);

SELECT *
FROM lock_lab.request_lock(
    5,
    (
        SELECT resource_id
        FROM lock_lab.resources
        WHERE resource_name = 'order:9001'
    ),
    'X'
);

-- ------------------------------------------------------------
-- 16. Evaluation and aggregation
-- ------------------------------------------------------------

SELECT *
FROM lock_lab.resource_contention_report
ORDER BY waiting_requests DESC, active_holders DESC;

SELECT
    requested_mode,
    COUNT(*) AS combinations,
    COUNT(*) FILTER (WHERE is_compatible) AS compatible_combinations,
    COUNT(*) FILTER (WHERE NOT is_compatible) AS conflicts
FROM lock_lab.lock_compatibility
GROUP BY requested_mode
ORDER BY requested_mode;

-- ------------------------------------------------------------
-- 17. Eligibility determination
-- ------------------------------------------------------------

-- Determine whether an exclusive request would conflict with
-- currently granted locks on account:1001.

SELECT
    r.resource_name,
    NOT EXISTS (
        SELECT 1
        FROM lock_lab.lock_holders h
        JOIN lock_lab.lock_compatibility c
          ON c.requested_mode = 'X'
         AND c.held_mode = h.mode
        WHERE h.resource_id = r.resource_id
          AND NOT c.is_compatible
    ) AS exclusive_compatible_with_current_holders
FROM lock_lab.resources r
WHERE r.resource_name = 'account:1001';

-- ------------------------------------------------------------
-- 18. Transaction handling
-- ------------------------------------------------------------

-- Release one shared acquisition for TXN-100.
SELECT lock_lab.release_lock(
    1,
    (
        SELECT resource_id
        FROM lock_lab.resources
        WHERE resource_name = 'account:1001'
    )
);

-- Complete TXN-100 and release its remaining holdings.
SELECT lock_lab.finish_transaction(1, 'COMMITTED');

-- Complete TXN-200.
SELECT lock_lab.finish_transaction(2, 'COMMITTED');

-- The application must process queued requests again after releases.
-- The request records preserve the waiting state until a scheduler
-- explicitly grants or cancels them.

-- Complete remaining independent transactions.
SELECT lock_lab.finish_transaction(4, 'ROLLED_BACK');
SELECT lock_lab.finish_transaction(5, 'COMMITTED');

-- ------------------------------------------------------------
-- 19. Historical reporting
-- ------------------------------------------------------------

SELECT
    e.event_type,
    e.lock_mode,
    t.transaction_reference,
    r.resource_name,
    e.event_time,
    e.details
FROM lock_lab.lock_events e
JOIN lock_lab.transactions t
  ON t.transaction_id = e.transaction_id
JOIN lock_lab.resources r
  ON r.resource_id = e.resource_id
ORDER BY e.event_time, e.event_id;

-- ------------------------------------------------------------
-- 20. Integrity validation
-- ------------------------------------------------------------

-- No inactive transaction should own a granted lock.
SELECT
    h.holder_id,
    t.transaction_reference,
    t.transaction_state
FROM lock_lab.lock_holders h
JOIN lock_lab.transactions t
  ON t.transaction_id = h.transaction_id
WHERE t.transaction_state <> 'ACTIVE';

-- No incompatible granted lock combinations should exist.
SELECT
    a.resource_id,
    a.transaction_id AS transaction_a,
    b.transaction_id AS transaction_b,
    a.mode AS mode_a,
    b.mode AS mode_b
FROM lock_lab.lock_holders a
JOIN lock_lab.lock_holders b
  ON b.resource_id = a.resource_id
 AND b.transaction_id > a.transaction_id
JOIN lock_lab.lock_compatibility c
  ON c.requested_mode = a.mode
 AND c.held_mode = b.mode
WHERE NOT c.is_compatible;

COMMIT;
