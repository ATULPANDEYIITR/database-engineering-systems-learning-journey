-- PostgreSQL 15+
-- Temporal data modeling for effective-dated business state, immutable history,
-- transaction-time auditing, and event-time processing.

BEGIN;

DROP SCHEMA IF EXISTS temporal_governance CASCADE;
CREATE SCHEMA temporal_governance;
SET search_path TO temporal_governance, public;

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE employees (
    employee_id text PRIMARY KEY,
    full_name text NOT NULL CHECK (length(trim(full_name)) > 0),
    hired_at timestamptz NOT NULL
);

-- Each row represents a fact that is effective during a business-time interval.
-- A separate recorded_at column captures when the database learned the fact.
CREATE TABLE salary_versions (
    salary_version_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    employee_id text NOT NULL REFERENCES employees(employee_id),
    salary_amount numeric(12, 2) NOT NULL CHECK (salary_amount > 0),
    currency_code char(3) NOT NULL DEFAULT 'INR',
    valid_during tstzrange NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    source_reference text NOT NULL,
    CHECK (NOT isempty(valid_during)),
    CHECK (lower_inc(valid_during)),
    CHECK (NOT upper_inc(valid_during)),
    CHECK (lower(valid_during) IS NOT NULL),
    EXCLUDE USING gist (
        employee_id WITH =,
        valid_during WITH &&
    )
);

CREATE INDEX salary_versions_asof_idx
    ON salary_versions(employee_id, recorded_at DESC);

CREATE TABLE temporal_audit (
    audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type text NOT NULL,
    entity_key text NOT NULL,
    operation text NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    transaction_id bigint NOT NULL DEFAULT txid_current(),
    database_user name NOT NULL DEFAULT current_user,
    before_image jsonb,
    after_image jsonb
);

-- This trigger records changes to salary facts without erasing the audit image.
CREATE FUNCTION audit_salary_version()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO temporal_audit (
            entity_type, entity_key, operation, after_image
        )
        VALUES (
            'salary_version', NEW.salary_version_id::text, 'INSERT',
            to_jsonb(NEW)
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO temporal_audit (
            entity_type, entity_key, operation, before_image, after_image
        )
        VALUES (
            'salary_version', NEW.salary_version_id::text, 'UPDATE',
            to_jsonb(OLD), to_jsonb(NEW)
        );
        RETURN NEW;
    ELSE
        INSERT INTO temporal_audit (
            entity_type, entity_key, operation, before_image
        )
        VALUES (
            'salary_version', OLD.salary_version_id::text, 'DELETE',
            to_jsonb(OLD)
        );
        RETURN OLD;
    END IF;
END;
$$;

CREATE TRIGGER salary_versions_audit
AFTER INSERT OR UPDATE OR DELETE ON salary_versions
FOR EACH ROW EXECUTE FUNCTION audit_salary_version();

-- Event time describes when an event happened. Ingestion time describes when
-- this system received it. Late-arriving events retain their original event time.
CREATE TABLE domain_events (
    event_id uuid PRIMARY KEY,
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    event_type text NOT NULL,
    event_time timestamptz NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_sequence bigint,
    CHECK (jsonb_typeof(payload) = 'object'),
    UNIQUE (entity_type, entity_id, source_sequence)
);

CREATE INDEX domain_events_event_time_idx
    ON domain_events(event_time, event_type);

CREATE INDEX domain_events_entity_time_idx
    ON domain_events(entity_type, entity_id, event_time DESC);

CREATE INDEX domain_events_payload_gin_idx
    ON domain_events USING gin(payload);

CREATE TABLE processing_watermarks (
    stream_name text PRIMARY KEY,
    maximum_event_time timestamptz NOT NULL,
    allowed_lateness interval NOT NULL CHECK (allowed_lateness >= interval '0'),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE temporal_corrections (
    correction_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    corrects_event_id uuid REFERENCES domain_events(event_id),
    effective_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    reason text NOT NULL CHECK (length(trim(reason)) > 0),
    correction_payload jsonb NOT NULL,
    CHECK (jsonb_typeof(correction_payload) = 'object')
);

CREATE INDEX temporal_corrections_lookup_idx
    ON temporal_corrections(entity_type, entity_id, effective_at, recorded_at);

INSERT INTO employees (employee_id, full_name, hired_at) VALUES
    ('EMP-104', 'Riya Sharma', '2025-06-01T09:00:00Z'),
    ('EMP-105', 'Kabir Singh', '2025-08-15T09:00:00Z');

INSERT INTO salary_versions (
    employee_id, salary_amount, currency_code, valid_during,
    recorded_at, source_reference
) VALUES
    (
        'EMP-104', 72000, 'INR',
        tstzrange('2026-01-01T00:00:00Z', '2026-04-01T00:00:00Z', '[)'),
        '2026-01-01T00:00:00Z', 'HR-CHANGE-100'
    ),
    (
        'EMP-104', 78000, 'INR',
        tstzrange('2026-04-01T00:00:00Z', '2026-07-01T00:00:00Z', '[)'),
        '2026-04-01T00:00:00Z', 'HR-CHANGE-101'
    ),
    (
        'EMP-104', 84000, 'INR',
        tstzrange('2026-07-01T00:00:00Z', NULL, '[)'),
        '2026-08-10T09:00:00Z', 'HR-CHANGE-102'
    ),
    (
        'EMP-105', 65000, 'INR',
        tstzrange('2026-01-01T00:00:00Z', NULL, '[)'),
        '2026-01-01T00:00:00Z', 'HR-CHANGE-200'
    );

INSERT INTO domain_events (
    event_id, entity_type, entity_id, event_type,
    event_time, ingested_at, payload, source_sequence
) VALUES
    (
        '11111111-1111-4111-8111-111111111111',
        'shipment', 'SHP-301', 'shipment.departed',
        '2026-10-12T10:10:00Z', '2026-10-12T10:11:00Z',
        '{"route":"LKO-DEL","distance_km":490}', 1
    ),
    (
        '22222222-2222-4222-8222-222222222222',
        'shipment', 'SHP-302', 'shipment.delayed',
        '2026-10-12T10:12:00Z', '2026-10-12T10:12:05Z',
        '{"delay_minutes":35}', 1
    ),
    (
        '33333333-3333-4333-8333-333333333333',
        'shipment', 'SHP-303', 'shipment.departed',
        '2026-10-12T10:01:00Z', '2026-10-12T10:13:00Z',
        '{"route":"LKO-KNP","distance_km":90}', 1
    );

INSERT INTO processing_watermarks (
    stream_name, maximum_event_time, allowed_lateness
) VALUES (
    'shipment-events', '2026-10-12T10:12:00Z', interval '5 minutes'
);

-- Effective-state query: range containment respects the half-open boundaries.
SELECT
    employee_id,
    salary_amount,
    lower(valid_during) AS effective_from,
    upper(valid_during) AS effective_until,
    recorded_at
FROM salary_versions
WHERE employee_id = 'EMP-104'
  AND valid_during @> '2026-05-15T12:00:00Z'::timestamptz;

-- Historical reconstruction: find the fact effective at business time that
-- was already recorded by a specified knowledge time.
SELECT employee_id, salary_amount, valid_during, recorded_at
FROM salary_versions
WHERE employee_id = 'EMP-104'
  AND valid_during @> '2026-08-01T00:00:00Z'::timestamptz
  AND recorded_at <= '2026-08-01T00:00:00Z'::timestamptz
ORDER BY recorded_at DESC
LIMIT 1;

-- Compare the latest business-effective state with the current database view.
SELECT
    employee_id,
    salary_amount,
    lower(valid_during) AS effective_from,
    recorded_at,
    CASE
        WHEN recorded_at > lower(valid_during)
        THEN 'recorded after effective date'
        ELSE 'recorded on or before effective date'
    END AS recording_classification
FROM salary_versions
WHERE valid_during @> statement_timestamp()
ORDER BY employee_id;

-- Event-time aggregation is independent of arrival order.
SELECT
    event_type,
    count(*) AS event_count,
    min(event_time) AS first_event_time,
    max(event_time) AS last_event_time,
    count(*) FILTER (
        WHERE ingested_at > event_time + interval '5 minutes'
    ) AS received_more_than_five_minutes_late
FROM domain_events
WHERE event_time >= '2026-10-12T10:00:00Z'
  AND event_time < '2026-10-12T10:15:00Z'
GROUP BY event_type
ORDER BY event_type;

-- A watermark is a processing estimate, not a claim that no earlier event exists.
SELECT
    stream_name,
    maximum_event_time,
    allowed_lateness,
    maximum_event_time - allowed_lateness AS provisional_late_boundary,
    updated_at
FROM processing_watermarks;

-- Corrections are append-only facts; the original event is preserved.
INSERT INTO temporal_corrections (
    entity_type, entity_id, corrects_event_id, effective_at,
    recorded_at, reason, correction_payload
) VALUES (
    'shipment',
    'SHP-303',
    '33333333-3333-4333-8333-333333333333',
    '2026-10-12T10:01:00Z',
    '2026-10-12T10:20:00Z',
    'Source system confirmed corrected route distance',
    '{"route":"LKO-KNP","distance_km":94}'
);

-- Reconstruct a corrected event view as known at a chosen system time.
WITH ranked_corrections AS (
    SELECT
        correction.*,
        row_number() OVER (
            PARTITION BY corrects_event_id
            ORDER BY recorded_at DESC, correction_id DESC
        ) AS correction_rank
    FROM temporal_corrections AS correction
    WHERE recorded_at <= '2026-10-12T10:25:00Z'
)
SELECT
    event.event_id,
    event.event_type,
    event.event_time,
    event.ingested_at,
    COALESCE(correction.correction_payload, event.payload) AS effective_payload,
    correction.recorded_at AS correction_recorded_at
FROM domain_events AS event
LEFT JOIN ranked_corrections AS correction
    ON correction.corrects_event_id = event.event_id
   AND correction.correction_rank = 1
ORDER BY event.event_time, event.event_id;

-- The exclusion constraint rejects overlapping salary intervals for an employee.
-- The nested block catches the expected constraint violation so the rest of
-- this demonstration remains executable.
DO $$
BEGIN
    BEGIN
        INSERT INTO salary_versions (
            employee_id, salary_amount, currency_code,
            valid_during, recorded_at, source_reference
        ) VALUES (
            'EMP-104', 90000, 'INR',
            tstzrange('2026-06-01T00:00:00Z', '2026-08-01T00:00:00Z', '[)'),
            '2026-09-01T00:00:00Z', 'INVALID-OVERLAP'
        );
        RAISE EXCEPTION 'Expected overlapping interval to be rejected';
    EXCEPTION
        WHEN exclusion_violation THEN
            RAISE NOTICE 'Overlapping effective period rejected by database constraint';
    END;
END;
$$;

-- Audit history remains queryable even after a salary record changes.
SELECT
    audit_id,
    entity_key,
    operation,
    changed_at,
    transaction_id,
    before_image,
    after_image
FROM temporal_audit
ORDER BY audit_id;

COMMIT;
