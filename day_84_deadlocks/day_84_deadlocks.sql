-- ============================================================
-- DEADLOCK MANAGEMENT DATABASE
-- Detection, Prevention and Recovery
--
-- PostgreSQL 15+
--
-- Models:
--   Transactions
--   Resources
--   Resource ownership
--   Waiting requests
--   Wait-for graph
--   Deadlock detection
--   Resource-ordering prevention
--   Victim selection
--   Transaction recovery
--   Audit and reporting
--
-- Run as a PostgreSQL user with schema creation privileges.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS deadlock_lab;

SET search_path TO deadlock_lab, public;

-- ============================================================
-- 1. DOMAIN TYPES
-- ============================================================

CREATE TYPE transaction_status AS ENUM (
    'ACTIVE',
    'WAITING',
    'COMMITTED',
    'ABORTED'
);

CREATE TYPE prevention_policy AS ENUM (
    'NONE',
    'RESOURCE_ORDERING',
    'WAIT_DIE',
    'WOUND_WAIT'
);

CREATE TYPE recovery_policy AS ENUM (
    'YOUNGEST_TRANSACTION',
    'FEWEST_LOCKS'
);

-- ============================================================
-- 2. CORE TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_name VARCHAR(100) NOT NULL UNIQUE,

    start_timestamp TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    status transaction_status NOT NULL DEFAULT 'ACTIVE',

    policy prevention_policy NOT NULL DEFAULT 'NONE',

    rollback_count INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (rollback_count >= 0)
);

CREATE TABLE IF NOT EXISTS resources (
    resource_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    resource_name VARCHAR(100) NOT NULL UNIQUE,

    resource_order INTEGER NOT NULL UNIQUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (resource_order >= 0)
);

-- One resource has at most one current owner.
CREATE TABLE IF NOT EXISTS held_locks (
    resource_id BIGINT PRIMARY KEY
        REFERENCES resources(resource_id),

    transaction_id BIGINT NOT NULL
        REFERENCES transactions(transaction_id),

    acquired_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    UNIQUE (transaction_id, resource_id)
);

-- A transaction may wait for multiple distinct resources.
CREATE TABLE IF NOT EXISTS lock_waits (
    wait_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id BIGINT NOT NULL
        REFERENCES transactions(transaction_id),

    resource_id BIGINT NOT NULL
        REFERENCES resources(resource_id),

    requested_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    UNIQUE (transaction_id, resource_id)
);

CREATE TABLE IF NOT EXISTS deadlock_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    cycle BIGINT[] NOT NULL,

    victim_transaction_id BIGINT
        REFERENCES transactions(transaction_id),

    recovery_policy recovery_policy NOT NULL,

    recovery_reason TEXT NOT NULL,

    CHECK (cardinality(cycle) >= 2)
);

CREATE TABLE IF NOT EXISTS transaction_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id BIGINT
        REFERENCES transactions(transaction_id),

    event_type VARCHAR(60) NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- ============================================================
-- 3. PERFORMANCE INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_transactions_status
    ON transactions(status);

CREATE INDEX IF NOT EXISTS idx_transactions_start
    ON transactions(start_timestamp);

CREATE INDEX IF NOT EXISTS idx_held_locks_transaction
    ON held_locks(transaction_id);

CREATE INDEX IF NOT EXISTS idx_lock_waits_resource
    ON lock_waits(resource_id, requested_at);

CREATE INDEX IF NOT EXISTS idx_lock_waits_transaction
    ON lock_waits(transaction_id);

CREATE INDEX IF NOT EXISTS idx_deadlock_events_timestamp
    ON deadlock_events(detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_transaction
    ON transaction_audit(transaction_id, event_timestamp DESC);

-- ============================================================
-- 4. AUDIT FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION log_transaction_event(
    p_transaction_id BIGINT,
    p_event_type VARCHAR,
    p_details JSONB DEFAULT '{}'::JSONB
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO transaction_audit (
        transaction_id,
        event_type,
        details
    )
    VALUES (
        p_transaction_id,
        p_event_type,
        COALESCE(p_details, '{}'::JSONB)
    );
END;
$$;

-- ============================================================
-- 5. VALIDATION TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION validate_lock_wait()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_status transaction_status;
BEGIN
    SELECT status
    INTO v_status
    FROM transactions
    WHERE transaction_id = NEW.transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Transaction does not exist.';
    END IF;

    IF v_status NOT IN ('ACTIVE', 'WAITING') THEN
        RAISE EXCEPTION
            'Transaction % cannot request resources in state %',
            NEW.transaction_id,
            v_status;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validate_lock_wait
ON lock_waits;

CREATE TRIGGER trg_validate_lock_wait
BEFORE INSERT ON lock_waits
FOR EACH ROW
EXECUTE FUNCTION validate_lock_wait();

-- ============================================================
-- 6. RESOURCE ACQUISITION
-- ============================================================

CREATE OR REPLACE FUNCTION request_resource(
    p_transaction_id BIGINT,
    p_resource_id BIGINT
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_owner BIGINT;
    v_status transaction_status;
BEGIN
    SELECT status
    INTO v_status
    FROM transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown transaction.';
    END IF;

    IF v_status NOT IN ('ACTIVE', 'WAITING') THEN
        RAISE EXCEPTION
            'Transaction is not eligible to request resources.';
    END IF;

    PERFORM 1
    FROM resources
    WHERE resource_id = p_resource_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown resource.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM held_locks
        WHERE transaction_id = p_transaction_id
          AND resource_id = p_resource_id
    ) THEN
        RETURN 'ALREADY_HELD';
    END IF;

    SELECT transaction_id
    INTO v_owner
    FROM held_locks
    WHERE resource_id = p_resource_id
    FOR UPDATE;

    IF NOT FOUND THEN
        INSERT INTO held_locks (
            resource_id,
            transaction_id
        )
        VALUES (
            p_resource_id,
            p_transaction_id
        );

        UPDATE transactions
        SET status = 'ACTIVE'
        WHERE transaction_id = p_transaction_id;

        PERFORM log_transaction_event(
            p_transaction_id,
            'RESOURCE_ACQUIRED',
            jsonb_build_object('resource_id', p_resource_id)
        );

        RETURN 'GRANTED';
    END IF;

    IF v_owner = p_transaction_id THEN
        RETURN 'ALREADY_HELD';
    END IF;

    INSERT INTO lock_waits (
        transaction_id,
        resource_id
    )
    VALUES (
        p_transaction_id,
        p_resource_id
    )
    ON CONFLICT (transaction_id, resource_id)
    DO NOTHING;

    UPDATE transactions
    SET status = 'WAITING'
    WHERE transaction_id = p_transaction_id;

    PERFORM log_transaction_event(
        p_transaction_id,
        'RESOURCE_WAITING',
        jsonb_build_object(
            'resource_id', p_resource_id,
            'owner', v_owner
        )
    );

    RETURN 'WAITING';
END;
$$;

-- ============================================================
-- 7. RESOURCE ORDERING PREVENTION
-- ============================================================

CREATE OR REPLACE FUNCTION request_resource_ordered(
    p_transaction_id BIGINT,
    p_resource_id BIGINT
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_max_order INTEGER;
    v_requested_order INTEGER;
BEGIN
    SELECT MAX(r.resource_order)
    INTO v_max_order
    FROM held_locks h
    JOIN resources r
      ON r.resource_id = h.resource_id
    WHERE h.transaction_id = p_transaction_id;

    SELECT resource_order
    INTO v_requested_order
    FROM resources
    WHERE resource_id = p_resource_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown resource.';
    END IF;

    IF v_max_order IS NOT NULL
       AND v_requested_order < v_max_order THEN

        RAISE EXCEPTION
            'Resource ordering violation: requested %, highest held order %',
            v_requested_order,
            v_max_order;
    END IF;

    RETURN request_resource(
        p_transaction_id,
        p_resource_id
    );
END;
$$;

-- ============================================================
-- 8. WAIT-FOR GRAPH
-- ============================================================

-- Edge A -> B means transaction A waits for a resource
-- currently owned by transaction B.

CREATE OR REPLACE VIEW wait_for_edges AS
SELECT
    w.transaction_id AS waiting_transaction,
    h.transaction_id AS blocking_transaction,
    w.resource_id,
    w.requested_at
FROM lock_waits w
JOIN held_locks h
  ON h.resource_id = w.resource_id
WHERE w.transaction_id <> h.transaction_id;

-- ============================================================
-- 9. DEADLOCK DETECTION
-- ============================================================

CREATE OR REPLACE FUNCTION detect_deadlocks()
RETURNS TABLE (
    cycle BIGINT[],
    victim_id BIGINT
)
LANGUAGE sql
STABLE
AS $$
    WITH RECURSIVE walk (
        start_id,
        current_id,
        path,
        is_cycle
    ) AS (
        SELECT
            e.waiting_transaction,
            e.blocking_transaction,
            ARRAY[
                e.waiting_transaction,
                e.blocking_transaction
            ]::BIGINT[],
            e.blocking_transaction = e.waiting_transaction
        FROM wait_for_edges e

        UNION ALL

        SELECT
            w.start_id,
            e.blocking_transaction,
            w.path || e.blocking_transaction,
            e.blocking_transaction = w.start_id
        FROM walk w
        JOIN wait_for_edges e
          ON e.waiting_transaction = w.current_id
        WHERE NOT w.is_cycle
          AND NOT e.blocking_transaction = ANY(w.path)
    ),
    cycles AS (
        SELECT DISTINCT path AS cycle
        FROM walk
        WHERE is_cycle
          AND cardinality(path) >= 3
    )
    SELECT
        c.cycle,
        (
            SELECT t.transaction_id
            FROM transactions t
            WHERE t.transaction_id = ANY(c.cycle)
            ORDER BY
                t.start_timestamp DESC,
                t.transaction_id DESC
            LIMIT 1
        ) AS victim_id
    FROM cycles c;
$$;

-- ============================================================
-- 10. RESOURCE RELEASE AND WAITER SCHEDULING
-- ============================================================

CREATE OR REPLACE FUNCTION release_transaction_resources(
    p_transaction_id BIGINT
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_resource BIGINT;
    v_next_transaction BIGINT;
    v_released INTEGER := 0;
BEGIN
    -- A transaction must not retain pending requests after release.
    DELETE FROM lock_waits
    WHERE transaction_id = p_transaction_id;

    FOR v_resource IN
        SELECT resource_id
        FROM held_locks
        WHERE transaction_id = p_transaction_id
        ORDER BY resource_id
        FOR UPDATE
    LOOP
        DELETE FROM held_locks
        WHERE resource_id = v_resource
          AND transaction_id = p_transaction_id;

        v_released := v_released + 1;

        -- Grant the resource to the oldest eligible waiter.
        SELECT w.transaction_id
        INTO v_next_transaction
        FROM lock_waits w
        JOIN transactions t
          ON t.transaction_id = w.transaction_id
        WHERE w.resource_id = v_resource
          AND t.status = 'WAITING'
        ORDER BY
            w.requested_at,
            w.transaction_id
        LIMIT 1
        FOR UPDATE OF w, t SKIP LOCKED;

        IF FOUND THEN
            INSERT INTO held_locks (
                resource_id,
                transaction_id
            )
            VALUES (
                v_resource,
                v_next_transaction
            );

            DELETE FROM lock_waits
            WHERE transaction_id = v_next_transaction
              AND resource_id = v_resource;

            UPDATE transactions
            SET status = 'ACTIVE'
            WHERE transaction_id = v_next_transaction;

            PERFORM log_transaction_event(
                v_next_transaction,
                'RESOURCE_GRANTED',
                jsonb_build_object(
                    'resource_id', v_resource
                )
            );
        END IF;
    END LOOP;

    RETURN v_released;
END;
$$;

-- ============================================================
-- 11. TRANSACTION COMMIT
-- ============================================================

CREATE OR REPLACE PROCEDURE commit_transaction(
    p_transaction_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_status transaction_status;
BEGIN
    SELECT status
    INTO v_status
    FROM transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown transaction.';
    END IF;

    IF v_status <> 'ACTIVE' THEN
        RAISE EXCEPTION
            'Only active transactions can commit. Current state: %',
            v_status;
    END IF;

    UPDATE transactions
    SET status = 'COMMITTED'
    WHERE transaction_id = p_transaction_id;

    PERFORM release_transaction_resources(
        p_transaction_id
    );

    PERFORM log_transaction_event(
        p_transaction_id,
        'TRANSACTION_COMMITTED'
    );
END;
$$;

-- ============================================================
-- 12. DEADLOCK RECOVERY
-- ============================================================

CREATE OR REPLACE PROCEDURE recover_deadlocks(
    p_policy recovery_policy DEFAULT 'YOUNGEST_TRANSACTION'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_cycle BIGINT[];
    v_victim BIGINT;
    v_released INTEGER;
BEGIN
    LOOP
        SELECT d.cycle, d.victim_id
        INTO v_cycle, v_victim
        FROM detect_deadlocks() d
        LIMIT 1;

        IF NOT FOUND THEN
            EXIT;
        END IF;

        IF p_policy = 'FEWEST_LOCKS' THEN
            SELECT t.transaction_id
            INTO v_victim
            FROM transactions t
            LEFT JOIN held_locks h
              ON h.transaction_id = t.transaction_id
            WHERE t.transaction_id = ANY(v_cycle)
            GROUP BY t.transaction_id
            ORDER BY
                COUNT(h.resource_id),
                MAX(t.start_timestamp) DESC
            LIMIT 1;
        END IF;

        -- Remove pending requests and release every held resource.
        DELETE FROM lock_waits
        WHERE transaction_id = v_victim;

        UPDATE transactions
        SET status = 'ABORTED',
            rollback_count = rollback_count + 1
        WHERE transaction_id = v_victim
          AND status IN ('ACTIVE', 'WAITING');

        IF NOT FOUND THEN
            EXIT;
        END IF;

        v_released := release_transaction_resources(v_victim);

        INSERT INTO deadlock_events (
            cycle,
            victim_transaction_id,
            recovery_policy,
            recovery_reason
        )
        VALUES (
            v_cycle,
            v_victim,
            p_policy,
            'Transaction aborted to eliminate circular wait.'
        );

        PERFORM log_transaction_event(
            v_victim,
            'DEADLOCK_RECOVERY',
            jsonb_build_object(
                'cycle', v_cycle,
                'released_resources', v_released,
                'policy', p_policy
            )
        );
    END LOOP;
END;
$$;

-- ============================================================
-- 13. TRANSACTION ABORT
-- ============================================================

CREATE OR REPLACE PROCEDURE abort_transaction(
    p_transaction_id BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE transactions
    SET status = 'ABORTED',
        rollback_count = rollback_count + 1
    WHERE transaction_id = p_transaction_id
      AND status IN ('ACTIVE', 'WAITING');

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Transaction does not exist or cannot be aborted.';
    END IF;

    PERFORM release_transaction_resources(
        p_transaction_id
    );

    PERFORM log_transaction_event(
        p_transaction_id,
        'TRANSACTION_ABORTED'
    );
END;
$$;

-- ============================================================
-- 14. REPORTING VIEWS
-- ============================================================

CREATE OR REPLACE VIEW transaction_resource_summary AS
SELECT
    t.transaction_id,
    t.transaction_name,
    t.status,
    COUNT(DISTINCT h.resource_id) AS held_resources,
    COUNT(DISTINCT w.resource_id) AS waiting_resources,
    t.rollback_count,
    t.start_timestamp
FROM transactions t
LEFT JOIN held_locks h
    ON h.transaction_id = t.transaction_id
LEFT JOIN lock_waits w
    ON w.transaction_id = t.transaction_id
GROUP BY
    t.transaction_id,
    t.transaction_name,
    t.status,
    t.rollback_count,
    t.start_timestamp;

CREATE OR REPLACE VIEW resource_contention_report AS
SELECT
    r.resource_id,
    r.resource_name,
    h.transaction_id AS current_owner,
    COUNT(w.wait_id) AS waiting_transactions
FROM resources r
LEFT JOIN held_locks h
    ON h.resource_id = r.resource_id
LEFT JOIN lock_waits w
    ON w.resource_id = r.resource_id
GROUP BY
    r.resource_id,
    r.resource_name,
    h.transaction_id;

CREATE OR REPLACE VIEW transaction_eligibility AS
SELECT
    t.transaction_id,
    t.transaction_name,
    t.status,
    CASE
        WHEN t.status = 'ACTIVE'
         AND NOT EXISTS (
             SELECT 1
             FROM lock_waits w
             WHERE w.transaction_id = t.transaction_id
         )
        THEN TRUE
        ELSE FALSE
    END AS commit_eligible
FROM transactions t;

-- ============================================================
-- 15. SAMPLE DATA
-- ============================================================

INSERT INTO resources (
    resource_name,
    resource_order
)
VALUES
    ('DATABASE', 1),
    ('FILE_SYSTEM', 2),
    ('ACCOUNT', 3),
    ('LEDGER', 4),
    ('AUDIT_LOG', 5)
ON CONFLICT (resource_name) DO NOTHING;

INSERT INTO transactions (
    transaction_name,
    status,
    policy
)
VALUES
    ('PAYMENT_T1', 'ACTIVE', 'NONE'),
    ('REPORT_T2', 'ACTIVE', 'NONE'),
    ('ORDER_T3', 'ACTIVE', 'RESOURCE_ORDERING'),
    ('AUDIT_T4', 'ACTIVE', 'NONE'),
    ('COMPLETED_T5', 'COMMITTED', 'NONE')
ON CONFLICT (transaction_name) DO NOTHING;

-- Retrieve generated identifiers.
-- The first scenario intentionally creates a circular wait.

DO $$
DECLARE
    t1 BIGINT;
    t2 BIGINT;
    db BIGINT;
    fs BIGINT;
BEGIN
    SELECT transaction_id
    INTO t1
    FROM transactions
    WHERE transaction_name = 'PAYMENT_T1';

    SELECT transaction_id
    INTO t2
    FROM transactions
    WHERE transaction_name = 'REPORT_T2';

    SELECT resource_id
    INTO db
    FROM resources
    WHERE resource_name = 'DATABASE';

    SELECT resource_id
    INTO fs
    FROM resources
    WHERE resource_name = 'FILE_SYSTEM';

    -- Clear previous demonstration allocations.
    DELETE FROM lock_waits
    WHERE transaction_id IN (t1, t2);

    DELETE FROM held_locks
    WHERE transaction_id IN (t1, t2);

    UPDATE transactions
    SET status = 'ACTIVE'
    WHERE transaction_id IN (t1, t2);

    -- T1 holds DATABASE.
    INSERT INTO held_locks (
        resource_id,
        transaction_id
    )
    VALUES (db, t1)
    ON CONFLICT (resource_id) DO NOTHING;

    -- T2 holds FILE_SYSTEM.
    INSERT INTO held_locks (
        resource_id,
        transaction_id
    )
    VALUES (fs, t2)
    ON CONFLICT (resource_id) DO NOTHING;

    -- T1 waits for FILE_SYSTEM.
    INSERT INTO lock_waits (
        transaction_id,
        resource_id
    )
    VALUES (t1, fs)
    ON CONFLICT DO NOTHING;

    -- T2 waits for DATABASE.
    INSERT INTO lock_waits (
        transaction_id,
        resource_id
    )
    VALUES (t2, db)
    ON CONFLICT DO NOTHING;

    UPDATE transactions
    SET status = 'WAITING'
    WHERE transaction_id IN (t1, t2);
END;
$$;

-- ============================================================
-- 16. RETRIEVAL QUERIES
-- ============================================================

-- Current transaction status.
SELECT
    transaction_name,
    status,
    rollback_count,
    start_timestamp
FROM transactions
ORDER BY transaction_id;

-- Current resource ownership.
SELECT
    r.resource_name,
    t.transaction_name AS owner
FROM resources r
LEFT JOIN held_locks h
    ON h.resource_id = r.resource_id
LEFT JOIN transactions t
    ON t.transaction_id = h.transaction_id
ORDER BY r.resource_order;

-- Current waiting requests.
SELECT
    waiting.transaction_name AS waiting_transaction,
    owner.transaction_name AS blocking_transaction,
    r.resource_name,
    w.requested_at
FROM wait_for_edges e
JOIN transactions waiting
    ON waiting.transaction_id = e.waiting_transaction
JOIN transactions owner
    ON owner.transaction_id = e.blocking_transaction
JOIN resources r
    ON r.resource_id = e.resource_id
JOIN lock_waits w
    ON w.transaction_id = e.waiting_transaction
   AND w.resource_id = e.resource_id
ORDER BY w.requested_at;

-- ============================================================
-- 17. DEADLOCK DETECTION QUERY
-- ============================================================

SELECT
    cycle,
    victim_id
FROM detect_deadlocks();

-- ============================================================
-- 18. AGGREGATION AND CONTENTION REPORTS
-- ============================================================

SELECT *
FROM transaction_resource_summary
ORDER BY transaction_id;

SELECT *
FROM resource_contention_report
ORDER BY waiting_transactions DESC, resource_name;

-- ============================================================
-- 19. ELIGIBILITY EVALUATION
-- ============================================================

SELECT
    transaction_name,
    status,
    commit_eligible
FROM transaction_eligibility
ORDER BY transaction_id;

-- ============================================================
-- 20. VALIDATION QUERIES
-- ============================================================

-- No resource can have multiple owners because held_locks
-- uses resource_id as its primary key.

SELECT resource_id, COUNT(*)
FROM held_locks
GROUP BY resource_id
HAVING COUNT(*) > 1;

-- Detect invalid ownership references.
SELECT h.*
FROM held_locks h
JOIN transactions t
    ON t.transaction_id = h.transaction_id
WHERE t.status NOT IN ('ACTIVE', 'WAITING');

-- Detect unresolved requests from inactive transactions.
SELECT w.*
FROM lock_waits w
JOIN transactions t
    ON t.transaction_id = w.transaction_id
WHERE t.status NOT IN ('ACTIVE', 'WAITING');

-- ============================================================
-- 21. EXECUTE DEADLOCK RECOVERY
-- ============================================================

CALL recover_deadlocks('YOUNGEST_TRANSACTION');

-- ============================================================
-- 22. POST-RECOVERY REPORT
-- ============================================================

SELECT
    transaction_name,
    status,
    rollback_count
FROM transactions
ORDER BY transaction_id;

SELECT
    resource_name,
    current_owner,
    waiting_transactions
FROM resource_contention_report
ORDER BY resource_name;

SELECT *
FROM deadlock_events
ORDER BY detected_at DESC;

SELECT
    t.transaction_name,
    a.event_type,
    a.details,
    a.event_timestamp
FROM transaction_audit a
LEFT JOIN transactions t
    ON t.transaction_id = a.transaction_id
ORDER BY a.event_timestamp DESC;

-- ============================================================
-- 23. RESOURCE ORDERING VALIDATION
-- ============================================================

DO $$
DECLARE
    ordered_tx BIGINT;
    account_id BIGINT;
    ledger_id BIGINT;
BEGIN
    SELECT transaction_id
    INTO ordered_tx
    FROM transactions
    WHERE transaction_name = 'ORDER_T3';

    SELECT resource_id
    INTO account_id
    FROM resources
    WHERE resource_name = 'ACCOUNT';

    SELECT resource_id
    INTO ledger_id
    FROM resources
    WHERE resource_name = 'LEDGER';

    -- Ensure a clean demonstration state.
    DELETE FROM lock_waits
    WHERE transaction_id = ordered_tx;

    DELETE FROM held_locks
    WHERE transaction_id = ordered_tx;

    UPDATE transactions
    SET status = 'ACTIVE'
    WHERE transaction_id = ordered_tx;

    -- ACCOUNT has order 3 and LEDGER has order 4.
    PERFORM request_resource_ordered(
        ordered_tx,
        account_id
    );

    PERFORM request_resource_ordered(
        ordered_tx,
        ledger_id
    );

    -- Requesting ACCOUNT after LEDGER must fail.
    BEGIN
        PERFORM request_resource_ordered(
            ordered_tx,
            account_id
        );

        RAISE EXCEPTION
            'Expected resource ordering violation was not raised.';
    EXCEPTION
        WHEN raise_exception THEN
            IF SQLERRM LIKE 'Expected resource ordering%' THEN
                RAISE;
            END IF;

            RAISE NOTICE 'Ordering prevention validated: %',
                SQLERRM;
    END;

    CALL commit_transaction(ordered_tx);
END;
$$;

-- ============================================================
-- 24. TRANSACTIONAL PROCESSING EXAMPLE
-- ============================================================

BEGIN;

DO $$
DECLARE
    test_tx BIGINT;
    test_resource BIGINT;
    result TEXT;
BEGIN
    INSERT INTO transactions (
        transaction_name,
        status,
        policy
    )
    VALUES (
        'ATOMIC_TEST_TRANSACTION',
        'ACTIVE',
        'NONE'
    )
    RETURNING transaction_id INTO test_tx;

    SELECT resource_id
    INTO test_resource
    FROM resources
    WHERE resource_name = 'AUDIT_LOG';

    result := request_resource(
        test_tx,
        test_resource
    );

    IF result = 'GRANTED' THEN
        PERFORM log_transaction_event(
            test_tx,
            'ATOMIC_OPERATION',
            jsonb_build_object(
                'resource', 'AUDIT_LOG',
                'result', result
            )
        );
    END IF;

    CALL commit_transaction(test_tx);
END;
$$;

COMMIT;

-- ============================================================
-- END OF DEADLOCK MANAGEMENT DATABASE
-- ============================================================
