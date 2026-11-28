-- ============================================================
-- DISTRIBUTED TRANSACTIONS
-- TWO-PHASE COMMIT AND COORDINATION
-- PostgreSQL 17+
--
-- This schema models the coordinator and independent
-- participants of a distributed transaction.
--
-- IMPORTANT:
-- PostgreSQL transactions in this script model coordination
-- records. They do not create a real multi-server 2PC deployment.
-- Real distributed 2PC requires participant-side prepared
-- transactions and an external coordinator or transaction manager.
-- ============================================================

DROP SCHEMA IF EXISTS distributed_tx CASCADE;

CREATE SCHEMA distributed_tx;

SET search_path TO distributed_tx, public;

-- ============================================================
-- 1. ENUMERATED DOMAIN STATES
-- ============================================================

CREATE TYPE transaction_state AS ENUM (
    'ACTIVE',
    'PREPARING',
    'PREPARED',
    'COMMITTING',
    'COMMITTED',
    'ABORTING',
    'ABORTED',
    'IN_DOUBT'
);

CREATE TYPE participant_state AS ENUM (
    'ACTIVE',
    'PREPARED',
    'COMMITTED',
    'ABORTED',
    'FAILED'
);

CREATE TYPE transaction_decision AS ENUM (
    'COMMIT',
    'ABORT'
);

CREATE TYPE participant_vote AS ENUM (
    'YES',
    'NO'
);

CREATE TYPE event_type AS ENUM (
    'BEGIN',
    'ENLIST',
    'PREPARE_REQUESTED',
    'VOTE',
    'ALL_PREPARED',
    'GLOBAL_DECISION',
    'DELIVERY_ATTEMPT',
    'DELIVERY_ACKNOWLEDGED',
    'DELIVERY_FAILED',
    'COMPLETED',
    'RECOVERY_REQUESTED'
);

-- ============================================================
-- 2. RESOURCE PARTICIPANTS
-- ============================================================

CREATE TABLE participants (
    participant_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    participant_name VARCHAR(100) NOT NULL UNIQUE,

    endpoint VARCHAR(500) NOT NULL,

    resource_type VARCHAR(50) NOT NULL,

    available BOOLEAN NOT NULL DEFAULT TRUE,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT participant_name_not_empty
        CHECK (LENGTH(TRIM(participant_name)) > 0),

    CONSTRAINT endpoint_not_empty
        CHECK (LENGTH(TRIM(endpoint)) > 0)
);

-- ============================================================
-- 3. RESOURCE ACCOUNTS
--
-- This table provides an example resource managed by
-- an individual transaction participant.
-- ============================================================

CREATE TABLE resource_accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    participant_id BIGINT NOT NULL
        REFERENCES participants(participant_id),

    account_reference VARCHAR(50) NOT NULL UNIQUE,

    balance NUMERIC(18, 2) NOT NULL,

    version BIGINT NOT NULL DEFAULT 0,

    CONSTRAINT nonnegative_balance CHECK (balance >= 0),

    CONSTRAINT valid_account_version CHECK (version >= 0)
);

CREATE INDEX idx_resource_accounts_participant
    ON resource_accounts(participant_id);

-- ============================================================
-- 4. GLOBAL TRANSACTIONS
-- ============================================================

CREATE TABLE distributed_transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    description TEXT NOT NULL,

    state transaction_state NOT NULL DEFAULT 'ACTIVE',

    decision transaction_decision,

    coordinator_id VARCHAR(100) NOT NULL,

    timeout_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    version BIGINT NOT NULL DEFAULT 0,

    CONSTRAINT description_not_empty
        CHECK (LENGTH(TRIM(description)) > 0),

    CONSTRAINT valid_transaction_version
        CHECK (version >= 0),

    CONSTRAINT completion_consistency
        CHECK (
            (state IN ('COMMITTED', 'ABORTED'))
            = (completed_at IS NOT NULL)
        ),

    CONSTRAINT decision_state_consistency
        CHECK (
            decision IS NULL
            OR (
                decision = 'COMMIT'
                AND state IN (
                    'COMMITTING',
                    'COMMITTED',
                    'IN_DOUBT'
                )
            )
            OR (
                decision = 'ABORT'
                AND state IN (
                    'ABORTING',
                    'ABORTED',
                    'IN_DOUBT'
                )
            )
        )
);

CREATE INDEX idx_transactions_state_created
    ON distributed_transactions(state, created_at);

CREATE INDEX idx_transactions_recovery
    ON distributed_transactions(updated_at)
    WHERE state = 'IN_DOUBT';

CREATE INDEX idx_transactions_active_timeout
    ON distributed_transactions(timeout_at)
    WHERE state IN (
        'ACTIVE',
        'PREPARING',
        'PREPARED',
        'COMMITTING',
        'ABORTING',
        'IN_DOUBT'
    );

-- ============================================================
-- 5. TRANSACTION PARTICIPANTS
--
-- One row represents the relationship between a global
-- transaction and an individual resource participant.
-- ============================================================

CREATE TABLE transaction_participants (
    transaction_id UUID NOT NULL
        REFERENCES distributed_transactions(transaction_id),

    participant_id BIGINT NOT NULL
        REFERENCES participants(participant_id),

    state participant_state NOT NULL DEFAULT 'ACTIVE',

    vote participant_vote,

    operation_type VARCHAR(30) NOT NULL,

    debit_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,

    credit_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,

    prepared_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    attempts INTEGER NOT NULL DEFAULT 0,

    last_error TEXT,

    PRIMARY KEY (transaction_id, participant_id),

    CONSTRAINT valid_debit CHECK (debit_amount >= 0),

    CONSTRAINT valid_credit CHECK (credit_amount >= 0),

    CONSTRAINT valid_attempts CHECK (attempts >= 0),

    CONSTRAINT valid_operation
        CHECK (
            operation_type IN (
                'TRANSFER',
                'DEBIT',
                'CREDIT',
                'UPDATE',
                'RESERVATION'
            )
        ),

    CONSTRAINT vote_required_for_prepared
        CHECK (
            state NOT IN ('PREPARED', 'COMMITTED')
            OR vote = 'YES'
        ),

    CONSTRAINT prepared_timestamp_required
        CHECK (
            state <> 'PREPARED'
            OR prepared_at IS NOT NULL
        ),

    CONSTRAINT completion_timestamp_consistency
        CHECK (
            (state IN ('COMMITTED', 'ABORTED'))
            = (completed_at IS NOT NULL)
        )
);

CREATE INDEX idx_tx_participants_state
    ON transaction_participants(
        transaction_id,
        state
    );

CREATE INDEX idx_tx_participants_failed
    ON transaction_participants(participant_id, state)
    WHERE state = 'FAILED';

-- ============================================================
-- 6. COORDINATOR EVENT JOURNAL
--
-- An append-oriented journal records votes, decisions,
-- acknowledgements and failures.
-- ============================================================

CREATE TABLE transaction_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id UUID NOT NULL
        REFERENCES distributed_transactions(transaction_id),

    participant_id BIGINT
        REFERENCES participants(participant_id),

    event event_type NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_transaction_events_history
    ON transaction_events(transaction_id, event_id);

CREATE INDEX idx_transaction_events_type
    ON transaction_events(event, created_at);

-- ============================================================
-- 7. PROTECT GLOBAL DECISIONS
--
-- Once persisted, a global decision cannot be reversed.
-- A COMMIT cannot become ABORT and vice versa.
-- ============================================================

CREATE OR REPLACE FUNCTION enforce_transaction_decision()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.decision IS NOT NULL
       AND NEW.decision IS DISTINCT FROM OLD.decision THEN
        RAISE EXCEPTION
            'Global transaction decision cannot be reversed';
    END IF;

    IF OLD.state IN ('COMMITTED', 'ABORTED')
       AND NEW.state <> OLD.state THEN
        RAISE EXCEPTION
            'Terminal transaction state cannot be changed';
    END IF;

    IF OLD.decision = 'COMMIT'
       AND NEW.state IN ('ABORTING', 'ABORTED') THEN
        RAISE EXCEPTION
            'Committed decision cannot transition to abort';
    END IF;

    IF OLD.decision = 'ABORT'
       AND NEW.state IN ('COMMITTING', 'COMMITTED') THEN
        RAISE EXCEPTION
            'Aborted decision cannot transition to commit';
    END IF;

    NEW.updated_at := NOW();
    NEW.version := OLD.version + 1;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_transaction_decision
BEFORE UPDATE ON distributed_transactions
FOR EACH ROW
EXECUTE FUNCTION enforce_transaction_decision();

-- ============================================================
-- 8. TRANSACTION EVENT INSERTION
-- ============================================================

CREATE OR REPLACE FUNCTION log_transaction_event(
    p_transaction_id UUID,
    p_event event_type,
    p_details JSONB DEFAULT '{}'::JSONB,
    p_participant_id BIGINT DEFAULT NULL
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_event_id BIGINT;
BEGIN
    INSERT INTO transaction_events (
        transaction_id,
        participant_id,
        event,
        details
    )
    VALUES (
        p_transaction_id,
        p_participant_id,
        p_event,
        COALESCE(p_details, '{}'::JSONB)
    )
    RETURNING event_id INTO v_event_id;

    RETURN v_event_id;
END;
$$;

-- ============================================================
-- 9. CREATE A GLOBAL TRANSACTION
-- ============================================================

CREATE OR REPLACE FUNCTION begin_transaction(
    p_description TEXT,
    p_coordinator_id VARCHAR(100),
    p_timeout_seconds INTEGER DEFAULT 60
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_transaction_id UUID;
BEGIN
    IF p_description IS NULL
       OR LENGTH(TRIM(p_description)) = 0 THEN
        RAISE EXCEPTION 'Transaction description is required';
    END IF;

    IF p_coordinator_id IS NULL
       OR LENGTH(TRIM(p_coordinator_id)) = 0 THEN
        RAISE EXCEPTION 'Coordinator ID is required';
    END IF;

    IF p_timeout_seconds <= 0 THEN
        RAISE EXCEPTION 'Timeout must be positive';
    END IF;

    INSERT INTO distributed_transactions (
        description,
        coordinator_id,
        timeout_at
    )
    VALUES (
        p_description,
        p_coordinator_id,
        NOW() + MAKE_INTERVAL(secs => p_timeout_seconds)
    )
    RETURNING transaction_id INTO v_transaction_id;

    PERFORM log_transaction_event(
        v_transaction_id,
        'BEGIN',
        JSONB_BUILD_OBJECT(
            'description', p_description,
            'coordinator', p_coordinator_id
        )
    );

    RETURN v_transaction_id;
END;
$$;

-- ============================================================
-- 10. ENLIST A PARTICIPANT
-- ============================================================

CREATE OR REPLACE PROCEDURE enlist_participant(
    p_transaction_id UUID,
    p_participant_id BIGINT,
    p_operation_type VARCHAR(30),
    p_debit NUMERIC(18, 2),
    p_credit NUMERIC(18, 2)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_state transaction_state;
    v_available BOOLEAN;
BEGIN
    SELECT state
    INTO v_state
    FROM distributed_transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown transaction';
    END IF;

    IF v_state <> 'ACTIVE' THEN
        RAISE EXCEPTION 'Participants can only be enlisted while ACTIVE';
    END IF;

    SELECT available
    INTO v_available
    FROM participants
    WHERE participant_id = p_participant_id
      AND enabled = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Participant does not exist or is disabled';
    END IF;

    IF NOT v_available THEN
        RAISE EXCEPTION 'Participant is unavailable';
    END IF;

    INSERT INTO transaction_participants (
        transaction_id,
        participant_id,
        operation_type,
        debit_amount,
        credit_amount
    )
    VALUES (
        p_transaction_id,
        p_participant_id,
        p_operation_type,
        p_debit,
        p_credit
    );

    PERFORM log_transaction_event(
        p_transaction_id,
        'ENLIST',
        JSONB_BUILD_OBJECT(
            'participant_id', p_participant_id,
            'operation', p_operation_type,
            'debit', p_debit,
            'credit', p_credit
        ),
        p_participant_id
    );
END;
$$;

-- ============================================================
-- 11. RECORD PARTICIPANT VOTES
--
-- A participant voting YES promises to preserve its
-- prepared state until it receives the global decision.
-- ============================================================

CREATE OR REPLACE FUNCTION record_vote(
    p_transaction_id UUID,
    p_participant_id BIGINT,
    p_vote participant_vote,
    p_error TEXT DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_state transaction_state;
    v_old_vote participant_vote;
BEGIN
    SELECT state
    INTO v_state
    FROM distributed_transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown transaction';
    END IF;

    IF v_state <> 'PREPARING' THEN
        RAISE EXCEPTION 'Transaction is not in PREPARING state';
    END IF;

    SELECT vote
    INTO v_old_vote
    FROM transaction_participants
    WHERE transaction_id = p_transaction_id
      AND participant_id = p_participant_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Participant is not enlisted';
    END IF;

    IF v_old_vote IS NOT NULL THEN
        IF v_old_vote <> p_vote THEN
            RAISE EXCEPTION 'Participant vote cannot be reversed';
        END IF;

        RETURN;
    END IF;

    UPDATE transaction_participants
    SET vote = p_vote,
        state = CASE
            WHEN p_vote = 'YES' THEN 'PREPARED'::participant_state
            ELSE 'FAILED'::participant_state
        END,
        prepared_at = CASE
            WHEN p_vote = 'YES' THEN NOW()
            ELSE NULL
        END,
        last_error = p_error,
        attempts = attempts + 1
    WHERE transaction_id = p_transaction_id
      AND participant_id = p_participant_id;

    PERFORM log_transaction_event(
        p_transaction_id,
        'VOTE',
        JSONB_BUILD_OBJECT(
            'vote', p_vote,
            'error', p_error
        ),
        p_participant_id
    );
END;
$$;

-- ============================================================
-- 12. PHASE 1: INITIATE PREPARATION
-- ============================================================

CREATE OR REPLACE PROCEDURE start_prepare(
    p_transaction_id UUID
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_state transaction_state;
    v_count INTEGER;
BEGIN
    SELECT state
    INTO v_state
    FROM distributed_transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown transaction';
    END IF;

    IF v_state <> 'ACTIVE' THEN
        RAISE EXCEPTION 'Transaction cannot start preparation';
    END IF;

    SELECT COUNT(*)
    INTO v_count
    FROM transaction_participants
    WHERE transaction_id = p_transaction_id;

    IF v_count = 0 THEN
        RAISE EXCEPTION 'At least one participant is required';
    END IF;

    UPDATE distributed_transactions
    SET state = 'PREPARING'
    WHERE transaction_id = p_transaction_id;

    PERFORM log_transaction_event(
        p_transaction_id,
        'PREPARE_REQUESTED',
        JSONB_BUILD_OBJECT('participant_count', v_count)
    );
END;
$$;

-- ============================================================
-- 13. DETERMINE UNANIMOUS PREPARATION
-- ============================================================

CREATE OR REPLACE FUNCTION all_participants_prepared(
    p_transaction_id UUID
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT
        COUNT(*) > 0
        AND BOOL_AND(state = 'PREPARED' AND vote = 'YES')
    FROM transaction_participants
    WHERE transaction_id = p_transaction_id;
$$;

-- ============================================================
-- 14. PHASE 2: RECORD GLOBAL DECISION
--
-- The global decision is written before delivery.
-- This ordering allows recovery to distinguish a committed
-- decision from a transaction whose decision is unknown.
-- ============================================================

CREATE OR REPLACE PROCEDURE decide_transaction(
    p_transaction_id UUID,
    p_decision transaction_decision
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_state transaction_state;
    v_existing transaction_decision;
BEGIN
    SELECT state, decision
    INTO v_state, v_existing
    FROM distributed_transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown transaction';
    END IF;

    IF v_existing IS NOT NULL THEN
        IF v_existing <> p_decision THEN
            RAISE EXCEPTION 'Global decision cannot be reversed';
        END IF;

        RETURN;
    END IF;

    IF p_decision = 'COMMIT' THEN
        IF v_state <> 'PREPARED' THEN
            RAISE EXCEPTION 'COMMIT requires PREPARED state';
        END IF;

        IF NOT all_participants_prepared(p_transaction_id) THEN
            RAISE EXCEPTION 'Not all participants voted YES';
        END IF;

        UPDATE distributed_transactions
        SET decision = 'COMMIT',
            state = 'COMMITTING'
        WHERE transaction_id = p_transaction_id;

    ELSE
        IF v_state NOT IN (
            'ACTIVE',
            'PREPARING',
            'PREPARED',
            'ABORTING'
        ) THEN
            RAISE EXCEPTION 'ABORT is not valid from state %', v_state;
        END IF;

        UPDATE distributed_transactions
        SET decision = 'ABORT',
            state = 'ABORTING'
        WHERE transaction_id = p_transaction_id;
    END IF;

    PERFORM log_transaction_event(
        p_transaction_id,
        'GLOBAL_DECISION',
        JSONB_BUILD_OBJECT('decision', p_decision)
    );
END;
$$;

-- ============================================================
-- 15. PARTICIPANT PHASE-2 ACKNOWLEDGEMENT
--
-- This records delivery acknowledgement. The actual remote
-- participant must execute the operation under its own durable
-- transaction and report its outcome.
-- ============================================================

CREATE OR REPLACE PROCEDURE acknowledge_participant(
    p_transaction_id UUID,
    p_participant_id BIGINT,
    p_decision transaction_decision
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_global_decision transaction_decision;
    v_state transaction_state;
    v_participant_state participant_state;
BEGIN
    SELECT decision, state
    INTO v_global_decision, v_state
    FROM distributed_transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown transaction';
    END IF;

    IF v_global_decision IS DISTINCT FROM p_decision THEN
        RAISE EXCEPTION 'Acknowledgement conflicts with global decision';
    END IF;

    IF v_state NOT IN ('COMMITTING', 'ABORTING', 'IN_DOUBT') THEN
        RAISE EXCEPTION 'Transaction is not delivering a decision';
    END IF;

    SELECT state
    INTO v_participant_state
    FROM transaction_participants
    WHERE transaction_id = p_transaction_id
      AND participant_id = p_participant_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Participant is not enlisted';
    END IF;

    IF p_decision = 'COMMIT' THEN
        IF v_participant_state = 'COMMITTED' THEN
            RETURN;
        END IF;

        IF v_participant_state <> 'PREPARED' THEN
            RAISE EXCEPTION 'Participant must be PREPARED to commit';
        END IF;

        UPDATE transaction_participants
        SET state = 'COMMITTED',
            completed_at = NOW(),
            attempts = attempts + 1,
            last_error = NULL
        WHERE transaction_id = p_transaction_id
          AND participant_id = p_participant_id;

    ELSE
        IF v_participant_state = 'ABORTED' THEN
            RETURN;
        END IF;

        IF v_participant_state = 'COMMITTED' THEN
            RAISE EXCEPTION 'Cannot abort committed participant';
        END IF;

        UPDATE transaction_participants
        SET state = 'ABORTED',
            completed_at = NOW(),
            attempts = attempts + 1,
            last_error = NULL
        WHERE transaction_id = p_transaction_id
          AND participant_id = p_participant_id;
    END IF;

    PERFORM log_transaction_event(
        p_transaction_id,
        'DELIVERY_ACKNOWLEDGED',
        JSONB_BUILD_OBJECT('decision', p_decision),
        p_participant_id
    );
END;
$$;

-- ============================================================
-- 16. RECORD PHASE-2 DELIVERY FAILURE
-- ============================================================

CREATE OR REPLACE PROCEDURE record_delivery_failure(
    p_transaction_id UUID,
    p_participant_id BIGINT,
    p_error TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_decision transaction_decision;
BEGIN
    SELECT decision
    INTO v_decision
    FROM distributed_transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND OR v_decision IS NULL THEN
        RAISE EXCEPTION 'No global decision available';
    END IF;

    UPDATE transaction_participants
    SET attempts = attempts + 1,
        last_error = p_error
    WHERE transaction_id = p_transaction_id
      AND participant_id = p_participant_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Participant is not enlisted';
    END IF;

    UPDATE distributed_transactions
    SET state = 'IN_DOUBT'
    WHERE transaction_id = p_transaction_id
      AND state IN ('COMMITTING', 'ABORTING', 'IN_DOUBT');

    PERFORM log_transaction_event(
        p_transaction_id,
        'DELIVERY_FAILED',
        JSONB_BUILD_OBJECT(
            'decision', v_decision,
            'error', p_error
        ),
        p_participant_id
    );
END;
$$;

-- ============================================================
-- 17. COMPLETE GLOBAL TRANSACTION
--
-- Completion is allowed only when every enlisted participant
-- acknowledges the same durable global decision.
-- ============================================================

CREATE OR REPLACE PROCEDURE complete_transaction(
    p_transaction_id UUID
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_decision transaction_decision;
    v_count INTEGER;
    v_completed INTEGER;
BEGIN
    SELECT decision
    INTO v_decision
    FROM distributed_transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND OR v_decision IS NULL THEN
        RAISE EXCEPTION 'Global decision is not recorded';
    END IF;

    SELECT
        COUNT(*),
        COUNT(*) FILTER (
            WHERE state = CASE
                WHEN v_decision = 'COMMIT'
                    THEN 'COMMITTED'::participant_state
                ELSE 'ABORTED'::participant_state
            END
        )
    INTO v_count, v_completed
    FROM transaction_participants
    WHERE transaction_id = p_transaction_id;

    IF v_count = 0 OR v_count <> v_completed THEN
        UPDATE distributed_transactions
        SET state = 'IN_DOUBT'
        WHERE transaction_id = p_transaction_id
          AND state IN ('COMMITTING', 'ABORTING', 'IN_DOUBT');

        RAISE EXCEPTION
            'Transaction incomplete: % of % acknowledgements',
            v_completed,
            v_count;
    END IF;

    UPDATE distributed_transactions
    SET state = CASE
        WHEN v_decision = 'COMMIT' THEN 'COMMITTED'
        ELSE 'ABORTED'
    END,
    completed_at = NOW()
    WHERE transaction_id = p_transaction_id;

    PERFORM log_transaction_event(
        p_transaction_id,
        'COMPLETED',
        JSONB_BUILD_OBJECT(
            'decision', v_decision,
            'participant_count', v_count
        )
    );
END;
$$;

-- ============================================================
-- 18. RECOVERY QUEUE
-- ============================================================

CREATE OR REPLACE VIEW recovery_queue AS
SELECT
    t.transaction_id,
    t.description,
    t.state,
    t.decision,
    t.coordinator_id,
    t.updated_at,
    COUNT(tp.participant_id) AS participant_count,
    COUNT(tp.participant_id) FILTER (
        WHERE tp.state IN ('COMMITTED', 'ABORTED')
    ) AS acknowledged_count,
    COUNT(tp.participant_id) FILTER (
        WHERE tp.state NOT IN ('COMMITTED', 'ABORTED')
    ) AS pending_count
FROM distributed_transactions t
LEFT JOIN transaction_participants tp
    ON tp.transaction_id = t.transaction_id
WHERE t.state = 'IN_DOUBT'
   OR t.state IN ('COMMITTING', 'ABORTING')
GROUP BY
    t.transaction_id,
    t.description,
    t.state,
    t.decision,
    t.coordinator_id,
    t.updated_at;

-- ============================================================
-- 19. MERGE-FREE TRANSACTION ELIGIBILITY REPORT
--
-- This query determines whether a transaction can safely
-- complete according to the coordinator's recorded state.
-- ============================================================

CREATE OR REPLACE VIEW transaction_eligibility AS
SELECT
    t.transaction_id,
    t.description,
    t.state,
    t.decision,

    COUNT(tp.participant_id) AS participant_count,

    COUNT(tp.participant_id) FILTER (
        WHERE tp.vote = 'YES'
    ) AS yes_votes,

    COUNT(tp.participant_id) FILTER (
        WHERE tp.vote = 'NO'
    ) AS no_votes,

    COUNT(tp.participant_id) FILTER (
        WHERE tp.state = 'PREPARED'
    ) AS prepared_count,

    COUNT(tp.participant_id) FILTER (
        WHERE tp.state = 'COMMITTED'
    ) AS committed_count,

    COUNT(tp.participant_id) FILTER (
        WHERE tp.state = 'ABORTED'
    ) AS aborted_count,

    CASE
        WHEN t.decision = 'COMMIT'
         AND COUNT(tp.participant_id) > 0
         AND BOOL_AND(tp.state = 'COMMITTED')
            THEN TRUE

        WHEN t.decision = 'ABORT'
         AND COUNT(tp.participant_id) > 0
         AND BOOL_AND(tp.state = 'ABORTED')
            THEN TRUE

        WHEN t.decision IS NULL
         AND t.state = 'PREPARED'
         AND COUNT(tp.participant_id) > 0
         AND BOOL_AND(
             tp.vote = 'YES'
             AND tp.state = 'PREPARED'
         )
            THEN TRUE

        ELSE FALSE
    END AS completion_eligible

FROM distributed_transactions t
LEFT JOIN transaction_participants tp
    ON tp.transaction_id = t.transaction_id
GROUP BY
    t.transaction_id,
    t.description,
    t.state,
    t.decision;

-- ============================================================
-- 20. AGGREGATED PARTICIPANT PERFORMANCE
-- ============================================================

CREATE OR REPLACE VIEW participant_performance AS
SELECT
    p.participant_id,
    p.participant_name,
    p.available,

    COUNT(tp.transaction_id) AS total_transactions,

    COUNT(tp.transaction_id) FILTER (
        WHERE tp.state = 'COMMITTED'
    ) AS committed_transactions,

    COUNT(tp.transaction_id) FILTER (
        WHERE tp.state = 'ABORTED'
    ) AS aborted_transactions,

    COUNT(tp.transaction_id) FILTER (
        WHERE tp.state = 'FAILED'
    ) AS failed_transactions,

    COALESCE(SUM(tp.attempts), 0) AS delivery_attempts

FROM participants p
LEFT JOIN transaction_participants tp
    ON tp.participant_id = p.participant_id
GROUP BY
    p.participant_id,
    p.participant_name,
    p.available;

-- ============================================================
-- 21. SAMPLE PARTICIPANTS
-- ============================================================

INSERT INTO participants (
    participant_name,
    endpoint,
    resource_type
)
VALUES
(
    'BANK_A',
    'https://bank-a.internal/transactions',
    'BANKING'
),
(
    'BANK_B',
    'https://bank-b.internal/transactions',
    'BANKING'
),
(
    'BANK_C',
    'https://bank-c.internal/transactions',
    'BANKING'
),
(
    'INVENTORY',
    'https://inventory.internal/transactions',
    'INVENTORY'
);

INSERT INTO resource_accounts (
    participant_id,
    account_reference,
    balance
)
SELECT
    participant_id,
    CASE participant_name
        WHEN 'BANK_A' THEN 'ACC-A-001'
        WHEN 'BANK_B' THEN 'ACC-B-001'
        WHEN 'BANK_C' THEN 'ACC-C-001'
        ELSE 'ACC-INV-001'
    END,
    CASE participant_name
        WHEN 'BANK_A' THEN 10000.00
        WHEN 'BANK_B' THEN 5000.00
        WHEN 'BANK_C' THEN 7000.00
        ELSE 1000.00
    END
FROM participants;

-- ============================================================
-- 22. CASE 1: SUCCESSFUL TRANSACTION
-- ============================================================

BEGIN;

DO $$
DECLARE
    v_tx UUID;
    v_a BIGINT;
    v_b BIGINT;
BEGIN
    SELECT participant_id INTO v_a
    FROM participants
    WHERE participant_name = 'BANK_A';

    SELECT participant_id INTO v_b
    FROM participants
    WHERE participant_name = 'BANK_B';

    v_tx := begin_transaction(
        'Transfer 1000 from BANK_A to BANK_B',
        'COORDINATOR_01',
        60
    );

    CALL enlist_participant(
        v_tx, v_a, 'DEBIT', 1000.00, 0.00
    );

    CALL enlist_participant(
        v_tx, v_b, 'CREDIT', 0.00, 1000.00
    );

    CALL start_prepare(v_tx);

    PERFORM record_vote(v_tx, v_a, 'YES', NULL);
    PERFORM record_vote(v_tx, v_b, 'YES', NULL);

    UPDATE distributed_transactions
    SET state = 'PREPARED'
    WHERE transaction_id = v_tx
      AND all_participants_prepared(v_tx);

    CALL decide_transaction(v_tx, 'COMMIT');

    CALL acknowledge_participant(v_tx, v_a, 'COMMIT');
    CALL acknowledge_participant(v_tx, v_b, 'COMMIT');

    CALL complete_transaction(v_tx);

    RAISE NOTICE 'Successful transaction: %', v_tx;
END;
$$;

COMMIT;

-- ============================================================
-- 23. CASE 2: NEGATIVE VOTE AND ABORT
-- ============================================================

BEGIN;

DO $$
DECLARE
    v_tx UUID;
    v_a BIGINT;
    v_c BIGINT;
BEGIN
    SELECT participant_id INTO v_a
    FROM participants
    WHERE participant_name = 'BANK_A';

    SELECT participant_id INTO v_c
    FROM participants
    WHERE participant_name = 'BANK_C';

    v_tx := begin_transaction(
        'Rejected transaction due to insufficient funds',
        'COORDINATOR_01',
        60
    );

    CALL enlist_participant(
        v_tx, v_a, 'DEBIT', 500.00, 0.00
    );

    CALL enlist_participant(
        v_tx, v_c, 'DEBIT', 100000.00, 0.00
    );

    CALL start_prepare(v_tx);

    PERFORM record_vote(v_tx, v_a, 'YES', NULL);

    PERFORM record_vote(
        v_tx,
        v_c,
        'NO',
        'Insufficient available balance'
    );

    CALL decide_transaction(v_tx, 'ABORT');

    CALL acknowledge_participant(v_tx, v_a, 'ABORT');
    CALL acknowledge_participant(v_tx, v_c, 'ABORT');

    CALL complete_transaction(v_tx);

    RAISE NOTICE 'Aborted transaction: %', v_tx;
END;
$$;

COMMIT;

-- ============================================================
-- 24. CASE 3: INCOMPLETE PHASE-2 DELIVERY
--
-- BANK_B does not acknowledge the COMMIT decision.
-- The coordinator retains IN_DOUBT for recovery.
-- ============================================================

BEGIN;

DO $$
DECLARE
    v_tx UUID;
    v_a BIGINT;
    v_b BIGINT;
BEGIN
    SELECT participant_id INTO v_a
    FROM participants
    WHERE participant_name = 'BANK_A';

    SELECT participant_id INTO v_b
    FROM participants
    WHERE participant_name = 'BANK_B';

    v_tx := begin_transaction(
        'Commit awaiting BANK_B acknowledgement',
        'COORDINATOR_01',
        60
    );

    CALL enlist_participant(
        v_tx, v_a, 'DEBIT', 200.00, 0.00
    );

    CALL enlist_participant(
        v_tx, v_b, 'CREDIT', 0.00, 200.00
    );

    CALL start_prepare(v_tx);

    PERFORM record_vote(v_tx, v_a, 'YES', NULL);
    PERFORM record_vote(v_tx, v_b, 'YES', NULL);

    UPDATE distributed_transactions
    SET state = 'PREPARED'
    WHERE transaction_id = v_tx
      AND all_participants_prepared(v_tx);

    CALL decide_transaction(v_tx, 'COMMIT');

    CALL acknowledge_participant(v_tx, v_a, 'COMMIT');

    CALL record_delivery_failure(
        v_tx,
        v_b,
        'Participant endpoint timed out during COMMIT delivery'
    );

    RAISE NOTICE 'In-doubt transaction: %', v_tx;
END;
$$;

COMMIT;

-- ============================================================
-- 25. RECOVERY OF CASE 3
--
-- The coordinator retries the existing COMMIT decision.
-- It does not create a new transaction or reverse the decision.
-- ============================================================

BEGIN;

DO $$
DECLARE
    v_tx UUID;
    v_b BIGINT;
BEGIN
    SELECT transaction_id
    INTO v_tx
    FROM distributed_transactions
    WHERE description =
        'Commit awaiting BANK_B acknowledgement';

    SELECT participant_id
    INTO v_b
    FROM participants
    WHERE participant_name = 'BANK_B';

    PERFORM log_transaction_event(
        v_tx,
        'RECOVERY_REQUESTED',
        JSONB_BUILD_OBJECT('strategy', 'RETRY_COMMIT')
    );

    CALL acknowledge_participant(v_tx, v_b, 'COMMIT');

    CALL complete_transaction(v_tx);

    RAISE NOTICE 'Recovered transaction: %', v_tx;
END;
$$;

COMMIT;

-- ============================================================
-- 26. VALIDATION QUERIES
-- ============================================================

-- A. Retrieve all transactions and their global decisions.

SELECT
    transaction_id,
    description,
    state,
    decision,
    created_at,
    completed_at
FROM distributed_transactions
ORDER BY created_at;

-- B. Inspect participant votes and final states.

SELECT
    t.transaction_id,
    t.description,
    p.participant_name,
    tp.vote,
    tp.state,
    tp.attempts,
    tp.last_error
FROM transaction_participants tp
JOIN distributed_transactions t
    ON t.transaction_id = tp.transaction_id
JOIN participants p
    ON p.participant_id = tp.participant_id
ORDER BY t.created_at, p.participant_name;

-- C. Determine transaction completion eligibility.

SELECT *
FROM transaction_eligibility
ORDER BY transaction_id;

-- D. Find transactions requiring recovery.

SELECT *
FROM recovery_queue
ORDER BY updated_at;

-- E. Aggregate participant reliability.

SELECT *
FROM participant_performance
ORDER BY participant_name;

-- F. Inspect the event history of every transaction.

SELECT
    event_id,
    transaction_id,
    event,
    participant_id,
    details,
    created_at
FROM transaction_events
ORDER BY event_id;

-- G. Verify that every committed transaction has unanimous YES votes.

SELECT
    t.transaction_id,
    t.state,
    COUNT(tp.participant_id) AS participants,
    COUNT(tp.participant_id) FILTER (
        WHERE tp.vote = 'YES'
    ) AS yes_votes,
    BOOL_AND(tp.state = 'COMMITTED') AS all_committed
FROM distributed_transactions t
JOIN transaction_participants tp
    ON tp.transaction_id = t.transaction_id
WHERE t.decision = 'COMMIT'
GROUP BY t.transaction_id, t.state;

-- H. Verify that completed transactions have no pending participants.

SELECT
    t.transaction_id,
    t.state,
    COUNT(*) FILTER (
        WHERE tp.state NOT IN ('COMMITTED', 'ABORTED')
    ) AS pending_participants
FROM distributed_transactions t
JOIN transaction_participants tp
    ON tp.transaction_id = t.transaction_id
WHERE t.state IN ('COMMITTED', 'ABORTED')
GROUP BY t.transaction_id, t.state;

-- I. Inspect resource-account balances.

SELECT
    p.participant_name,
    a.account_reference,
    a.balance,
    a.version
FROM resource_accounts a
JOIN participants p
    ON p.participant_id = a.participant_id
ORDER BY p.participant_name;

-- ============================================================
-- 27. VALIDATION: GLOBAL DECISION REVERSAL MUST FAIL
-- ============================================================

DO $$
DECLARE
    v_tx UUID;
BEGIN
    SELECT transaction_id
    INTO v_tx
    FROM distributed_transactions
    WHERE description = 'Transfer 1000 from BANK_A to BANK_B';

    BEGIN
        UPDATE distributed_transactions
        SET decision = 'ABORT'
        WHERE transaction_id = v_tx;

        RAISE EXCEPTION
            'Validation failure: decision reversal unexpectedly succeeded';

    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM NOT LIKE
                'Global transaction decision cannot be reversed%' THEN
                RAISE;
            END IF;

            RAISE NOTICE
                'Expected validation: global decision reversal rejected';
    END;
END;
$$;

-- ============================================================
-- 28. VALIDATION: FINAL STATE CONSISTENCY
-- ============================================================

DO $$
DECLARE
    v_invalid BIGINT;
BEGIN
    SELECT COUNT(*)
    INTO v_invalid
    FROM distributed_transactions t
    WHERE
        (
            t.state = 'COMMITTED'
            AND (
                t.decision <> 'COMMIT'
                OR EXISTS (
                    SELECT 1
                    FROM transaction_participants tp
                    WHERE tp.transaction_id = t.transaction_id
                      AND tp.state <> 'COMMITTED'
                )
            )
        )
        OR
        (
            t.state = 'ABORTED'
            AND (
                t.decision <> 'ABORT'
                OR EXISTS (
                    SELECT 1
                    FROM transaction_participants tp
                    WHERE tp.transaction_id = t.transaction_id
                      AND tp.state <> 'ABORTED'
                )
            )
        );

    IF v_invalid > 0 THEN
        RAISE EXCEPTION
            'Found % inconsistent completed transactions',
            v_invalid;
    END IF;

    RAISE NOTICE 'All completed transactions passed consistency checks';
END;
$$;

-- ============================================================
-- 29. OPERATIONAL NOTES
--
-- 1. A YES vote must correspond to a genuinely durable
--    participant-side prepared transaction.
--
-- 2. A coordinator must persist the global decision before
--    delivering COMMIT or ABORT.
--
-- 3. A participant must execute phase-2 messages idempotently.
--
-- 4. A missing acknowledgement does not justify reversing
--    an already persisted global decision.
--
-- 5. The IN_DOUBT state requires retry and reconciliation.
--
-- 6. PostgreSQL PREPARE TRANSACTION, COMMIT PREPARED and
--    ROLLBACK PREPARED are database-level prepared transaction
--    facilities. They are distinct from this logical workflow.
--
-- 7. Prepared PostgreSQL transactions retain locks and other
--    resources. Monitoring and cleanup are operationally important.
--
-- 8. A production deployment requires durable coordinator storage,
--    authenticated participant communication, fencing, retry
--    policies, monitoring and controlled recovery.
-- ============================================================
