-- PostgreSQL 15+.
-- Database design patterns: audit tables, soft deletes, and status models.
--
-- The schema models industrial equipment and its lifecycle. Operational
-- status is separate from deletion state. Audit events record attributable
-- changes. Constraints protect invariants even when application validation
-- is bypassed.
--
-- Execute in a disposable learning database. The script resets its own
-- demo schema to make repeated execution deterministic.

BEGIN;

DROP SCHEMA IF EXISTS lifecycle_demo CASCADE;
CREATE SCHEMA lifecycle_demo;
SET search_path TO lifecycle_demo, public;

CREATE TYPE equipment_status AS ENUM (
    'requested',
    'approved',
    'in_service',
    'maintenance',
    'retired'
);

CREATE TYPE audit_action AS ENUM (
    'created',
    'renamed',
    'status_changed',
    'soft_deleted',
    'restored'
);

CREATE TABLE app_users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT username_nonempty CHECK (btrim(username) <> ''),
    CONSTRAINT display_name_nonempty CHECK (btrim(display_name) <> '')
);

CREATE TABLE equipment (
    equipment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_tag TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status equipment_status NOT NULL DEFAULT 'requested',
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    deleted_by BIGINT REFERENCES app_users(user_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    created_by BIGINT NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_by BIGINT NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT equipment_tag_nonempty CHECK (btrim(asset_tag) <> ''),
    CONSTRAINT equipment_name_nonempty CHECK (btrim(name) <> ''),
    CONSTRAINT equipment_version_positive CHECK (version > 0),
    CONSTRAINT equipment_deletion_metadata_consistent CHECK (
        (is_deleted AND deleted_at IS NOT NULL AND deleted_by IS NOT NULL)
        OR
        (NOT is_deleted AND deleted_at IS NULL AND deleted_by IS NULL)
    )
);

-- A soft-deleted row still occupies its unique asset_tag. If business rules
-- allow tag reuse, use a partial unique index instead of the table constraint.
CREATE INDEX equipment_active_status_idx
    ON equipment(status, asset_tag)
    WHERE is_deleted = FALSE;

CREATE INDEX equipment_deleted_at_idx
    ON equipment(deleted_at)
    WHERE is_deleted = TRUE;

CREATE TABLE equipment_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    equipment_id BIGINT NOT NULL REFERENCES equipment(equipment_id)
        ON DELETE RESTRICT,
    action audit_action NOT NULL,
    actor_id BIGINT NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    old_values JSONB NOT NULL DEFAULT '{}'::jsonb,
    new_values JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason TEXT,
    correlation_id UUID NOT NULL DEFAULT gen_random_uuid(),
    CONSTRAINT audit_old_values_object CHECK (
        jsonb_typeof(old_values) = 'object'
    ),
    CONSTRAINT audit_new_values_object CHECK (
        jsonb_typeof(new_values) = 'object'
    )
);

CREATE INDEX equipment_audit_history_idx
    ON equipment_audit(equipment_id, occurred_at, audit_id);

CREATE INDEX equipment_audit_action_idx
    ON equipment_audit(action, occurred_at DESC);

CREATE TABLE status_transition_rules (
    from_status equipment_status NOT NULL,
    to_status equipment_status NOT NULL,
    requires_reason BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (from_status, to_status),
    CONSTRAINT no_self_transition CHECK (from_status <> to_status)
);

INSERT INTO status_transition_rules(from_status, to_status)
VALUES
    ('requested', 'approved'),
    ('approved', 'in_service'),
    ('approved', 'retired'),
    ('in_service', 'maintenance'),
    ('in_service', 'retired'),
    ('maintenance', 'in_service'),
    ('maintenance', 'retired');

CREATE TABLE idempotency_keys (
    operation_key TEXT PRIMARY KEY,
    operation_name TEXT NOT NULL,
    equipment_id BIGINT NOT NULL REFERENCES equipment(equipment_id)
        ON DELETE RESTRICT,
    actor_id BIGINT NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    result_audit_id BIGINT REFERENCES equipment_audit(audit_id)
        ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT idempotency_key_nonempty CHECK (btrim(operation_key) <> ''),
    CONSTRAINT idempotency_operation_nonempty
        CHECK (btrim(operation_name) <> '')
);

-- Audit records are append-only through ordinary application roles.
-- A database owner or superuser can still alter them, so high-assurance
-- deployments need separate ownership, permissions, backups, and monitoring.
CREATE FUNCTION prevent_audit_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'Audit events cannot be updated or deleted through ordinary DML';
END;
$$;

CREATE TRIGGER equipment_audit_immutable
BEFORE UPDATE OR DELETE ON equipment_audit
FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();

CREATE FUNCTION validate_equipment_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF NOT EXISTS (
            SELECT 1
            FROM status_transition_rules rule
            WHERE rule.from_status = OLD.status
              AND rule.to_status = NEW.status
        ) THEN
            RAISE EXCEPTION 'Invalid equipment status transition: % -> %',
                OLD.status, NEW.status
                USING ERRCODE = '23514';
        END IF;
    END IF;

    IF OLD.is_deleted AND NOT NEW.is_deleted THEN
        IF NEW.deleted_at IS NOT NULL OR NEW.deleted_by IS NOT NULL THEN
            RAISE EXCEPTION
                'Restored records must clear deletion metadata';
        END IF;
    END IF;

    IF NOT OLD.is_deleted AND NEW.is_deleted THEN
        IF NEW.deleted_at IS NULL OR NEW.deleted_by IS NULL THEN
            RAISE EXCEPTION
                'Soft deletion requires timestamp and actor';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER equipment_transition_guard
BEFORE UPDATE ON equipment
FOR EACH ROW EXECUTE FUNCTION validate_equipment_transition();

CREATE FUNCTION record_equipment_audit()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    audit_actor BIGINT;
    audit_kind audit_action;
    old_document JSONB := '{}'::jsonb;
    new_document JSONB := '{}'::jsonb;
    event_reason TEXT;
    event_correlation UUID;
BEGIN
    IF TG_OP = 'INSERT' THEN
        audit_actor := NEW.created_by;
        audit_kind := 'created';
        new_document := jsonb_build_object(
            'asset_tag', NEW.asset_tag,
            'name', NEW.name,
            'status', NEW.status,
            'is_deleted', NEW.is_deleted,
            'version', NEW.version
        );
        event_reason := 'Initial registration';
        event_correlation := gen_random_uuid();

        INSERT INTO equipment_audit(
            equipment_id, action, actor_id,
            old_values, new_values, reason, correlation_id
        )
        VALUES (
            NEW.equipment_id, audit_kind, audit_actor,
            old_document, new_document, event_reason, event_correlation
        );

        RETURN NEW;
    END IF;

    -- The application supplies the authenticated actor and reason with
    -- transaction-local settings. Missing identity is rejected.
    audit_actor := NULLIF(current_setting('app.actor_id', TRUE), '')::BIGINT;
    event_reason := NULLIF(current_setting('app.audit_reason', TRUE), '');
    event_correlation := COALESCE(
        NULLIF(current_setting('app.correlation_id', TRUE), '')::UUID,
        gen_random_uuid()
    );

    IF audit_actor IS NULL THEN
        RAISE EXCEPTION 'app.actor_id must be set for equipment updates';
    END IF;

    IF event_reason IS NULL THEN
        RAISE EXCEPTION 'app.audit_reason must be set for equipment updates';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        audit_kind := 'status_changed';
    ELSIF NOT OLD.is_deleted AND NEW.is_deleted THEN
        audit_kind := 'soft_deleted';
    ELSIF OLD.is_deleted AND NOT NEW.is_deleted THEN
        audit_kind := 'restored';
    ELSIF NEW.name IS DISTINCT FROM OLD.name THEN
        audit_kind := 'renamed';
    ELSE
        RAISE EXCEPTION
            'Update does not match a supported audited business operation';
    END IF;

    old_document := jsonb_build_object(
        'name', OLD.name,
        'status', OLD.status,
        'is_deleted', OLD.is_deleted,
        'deleted_at', OLD.deleted_at,
        'deleted_by', OLD.deleted_by,
        'version', OLD.version
    );

    new_document := jsonb_build_object(
        'name', NEW.name,
        'status', NEW.status,
        'is_deleted', NEW.is_deleted,
        'deleted_at', NEW.deleted_at,
        'deleted_by', NEW.deleted_by,
        'version', NEW.version
    );

    INSERT INTO equipment_audit(
        equipment_id, action, actor_id,
        old_values, new_values, reason, correlation_id
    )
    VALUES (
        NEW.equipment_id, audit_kind, audit_actor,
        old_document, new_document, event_reason, event_correlation
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER equipment_audit_after_insert
AFTER INSERT ON equipment
FOR EACH ROW EXECUTE FUNCTION record_equipment_audit();

CREATE TRIGGER equipment_audit_after_update
AFTER UPDATE ON equipment
FOR EACH ROW EXECUTE FUNCTION record_equipment_audit();

CREATE VIEW active_equipment AS
SELECT
    equipment_id,
    asset_tag,
    name,
    status,
    created_at,
    updated_at,
    version
FROM equipment
WHERE is_deleted = FALSE;

CREATE VIEW equipment_lifecycle_report AS
SELECT
    e.equipment_id,
    e.asset_tag,
    e.name,
    e.status,
    e.is_deleted,
    e.deleted_at,
    COUNT(a.audit_id) AS audit_event_count,
    MAX(a.occurred_at) AS latest_audit_at
FROM equipment e
LEFT JOIN equipment_audit a
    ON a.equipment_id = e.equipment_id
GROUP BY
    e.equipment_id, e.asset_tag, e.name, e.status,
    e.is_deleted, e.deleted_at;

INSERT INTO app_users(username, display_name)
VALUES
    ('asset_clerk', 'Asset Registration Clerk'),
    ('maintenance_manager', 'Maintenance Manager'),
    ('plant_supervisor', 'Plant Supervisor'),
    ('records_officer', 'Records Officer');

-- The application should use bound parameters. These literal values are
-- demonstration data only.
INSERT INTO equipment(asset_tag, name, created_by, updated_by)
SELECT 'PUMP-501', 'Cooling water pump', user_id, user_id
FROM app_users WHERE username = 'asset_clerk';

INSERT INTO equipment(asset_tag, name, created_by, updated_by)
SELECT 'MOTOR-502', 'Conveyor drive motor', user_id, user_id
FROM app_users WHERE username = 'asset_clerk';

-- A status update is accepted only when a rule exists. The actor and reason
-- are attached to the transaction, not supplied by an untrusted client.
SELECT set_config(
    'app.actor_id',
    (SELECT user_id::TEXT FROM app_users
     WHERE username = 'maintenance_manager'),
    TRUE
);
SELECT set_config(
    'app.audit_reason',
    'Engineering specifications reviewed.',
    TRUE
);
SELECT set_config('app.correlation_id', gen_random_uuid()::TEXT, TRUE);

UPDATE equipment
SET status = 'approved',
    version = version + 1,
    updated_at = clock_timestamp(),
    updated_by = (
        SELECT user_id FROM app_users
        WHERE username = 'maintenance_manager'
    )
WHERE asset_tag = 'PUMP-501'
  AND is_deleted = FALSE
  AND version = 1;

-- Soft deletion does not erase the row or its audit history.
SELECT set_config(
    'app.actor_id',
    (SELECT user_id::TEXT FROM app_users
     WHERE username = 'records_officer'),
    TRUE
);
SELECT set_config(
    'app.audit_reason',
    'Equipment assigned to the wrong department.',
    TRUE
);
SELECT set_config('app.correlation_id', gen_random_uuid()::TEXT, TRUE);

UPDATE equipment
SET is_deleted = TRUE,
    deleted_at = clock_timestamp(),
    deleted_by = (
        SELECT user_id FROM app_users
        WHERE username = 'records_officer'
    ),
    version = version + 1,
    updated_at = clock_timestamp(),
    updated_by = (
        SELECT user_id FROM app_users
        WHERE username = 'records_officer'
    )
WHERE asset_tag = 'MOTOR-502'
  AND is_deleted = FALSE
  AND version = 1;

-- Normal application queries use the active view.
SELECT asset_tag, name, status, version
FROM active_equipment
ORDER BY asset_tag;

-- Administrative queries can inspect retained deleted records.
SELECT asset_tag, name, status, is_deleted, deleted_at
FROM equipment
ORDER BY asset_tag;

-- Audit history identifies who changed what and why.
SELECT
    e.asset_tag,
    a.action,
    u.username AS actor,
    a.occurred_at,
    a.old_values,
    a.new_values,
    a.reason,
    a.correlation_id
FROM equipment_audit a
JOIN equipment e ON e.equipment_id = a.equipment_id
JOIN app_users u ON u.user_id = a.actor_id
ORDER BY a.audit_id;

-- Find records with no creation event. This query should return no rows.
SELECT e.equipment_id, e.asset_tag
FROM equipment e
LEFT JOIN equipment_audit a
    ON a.equipment_id = e.equipment_id
   AND a.action = 'created'
WHERE a.audit_id IS NULL;

-- Event counts support lifecycle investigation and retention monitoring.
SELECT
    action,
    COUNT(*) AS event_count,
    MIN(occurred_at) AS first_event,
    MAX(occurred_at) AS last_event
FROM equipment_audit
GROUP BY action
ORDER BY action;

-- Optimistic concurrency: a production API checks the row count returned by
-- UPDATE ... WHERE version = expected_version. Zero rows means stale data or
-- an invisible record. The expected version must come from the client request.
--
-- Example:
-- UPDATE lifecycle_demo.equipment
-- SET name = $1, version = version + 1, updated_at = clock_timestamp(),
--     updated_by = $2
-- WHERE equipment_id = $3 AND version = $4 AND is_deleted = FALSE
-- RETURNING equipment_id, version;

-- Transaction rollback also removes the audit event because the entity and
-- audit trigger execute in the same PostgreSQL transaction.
SAVEPOINT before_invalid_operation;

-- The next statement is deliberately commented out because PostgreSQL would
-- raise a constraint exception and abort the current transaction until
-- rollback. The transition guard rejects requested -> retired.
--
-- UPDATE equipment
-- SET status = 'retired', version = version + 1
-- WHERE asset_tag = 'PUMP-501';

ROLLBACK TO SAVEPOINT before_invalid_operation;

-- This report separates operational state from record visibility.
SELECT
    status,
    is_deleted,
    COUNT(*) AS equipment_count
FROM equipment
GROUP BY status, is_deleted
ORDER BY status, is_deleted;

COMMIT;
