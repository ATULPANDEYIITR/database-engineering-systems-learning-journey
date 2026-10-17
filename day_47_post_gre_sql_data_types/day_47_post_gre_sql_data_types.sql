-- PostgreSQL data types: an industrial equipment registry and telemetry model.
-- Compatible with PostgreSQL 13+.
-- gen_random_uuid() is available in supported modern PostgreSQL installations.

BEGIN;

CREATE SCHEMA IF NOT EXISTS industrial_registry;

SET LOCAL search_path TO industrial_registry, public;

CREATE TABLE IF NOT EXISTS manufacturers (
    manufacturer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    country_code VARCHAR(2),
    CONSTRAINT manufacturers_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT manufacturers_country_code_valid
        CHECK (country_code IS NULL OR country_code ~ '^[A-Z]{2}$')
);

CREATE TABLE IF NOT EXISTS equipment (
    equipment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    serial_number VARCHAR(40) NOT NULL UNIQUE,
    manufacturer_id UUID NOT NULL
        REFERENCES manufacturers(manufacturer_id),
    nominal_pressure_bar NUMERIC(10, 2) NOT NULL,
    is_active BOOLEAN,
    labels TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT equipment_serial_not_blank
        CHECK (btrim(serial_number) <> ''),

    CONSTRAINT equipment_pressure_nonnegative
        CHECK (nominal_pressure_bar >= 0),

    CONSTRAINT equipment_labels_no_null_elements
        CHECK (array_position(labels, NULL) IS NULL),

    CONSTRAINT equipment_metadata_is_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS equipment_manufacturer_idx
    ON equipment (manufacturer_id);

CREATE INDEX IF NOT EXISTS equipment_metadata_gin_idx
    ON equipment USING GIN (metadata);

CREATE INDEX IF NOT EXISTS equipment_labels_gin_idx
    ON equipment USING GIN (labels);

CREATE TABLE IF NOT EXISTS telemetry_readings (
    reading_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id UUID NOT NULL
        REFERENCES equipment(equipment_id) ON DELETE CASCADE,
    measured_at TIMESTAMPTZ NOT NULL,
    pressure_bar NUMERIC(12, 4) NOT NULL,
    temperature_c DOUBLE PRECISION,
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    payload JSONB NOT NULL DEFAULT '{}'::JSONB,

    CONSTRAINT telemetry_pressure_nonnegative
        CHECK (pressure_bar >= 0),

    CONSTRAINT telemetry_temperature_finite
        CHECK (
            temperature_c IS NULL
            OR temperature_c > '-Infinity'::DOUBLE PRECISION
               AND temperature_c < 'Infinity'::DOUBLE PRECISION
        ),

    CONSTRAINT telemetry_payload_object
        CHECK (jsonb_typeof(payload) = 'object')
);

CREATE INDEX IF NOT EXISTS telemetry_equipment_time_idx
    ON telemetry_readings (equipment_id, measured_at DESC);

CREATE INDEX IF NOT EXISTS telemetry_payload_gin_idx
    ON telemetry_readings USING GIN (payload);

INSERT INTO manufacturers (name, country_code)
VALUES
    ('Precision Instruments Ltd.', 'IN'),
    ('Industrial Measurement Systems', 'DE')
ON CONFLICT (name) DO NOTHING;

INSERT INTO equipment (
    serial_number,
    manufacturer_id,
    nominal_pressure_bar,
    is_active,
    labels,
    metadata
)
SELECT
    source.serial_number,
    manufacturer.manufacturer_id,
    source.nominal_pressure_bar,
    source.is_active,
    source.labels,
    source.metadata
FROM (
    VALUES
        (
            'PS-2026-0042',
            'Precision Instruments Ltd.',
            10.00::NUMERIC,
            TRUE,
            ARRAY['plant-a', 'critical']::TEXT[],
            '{"protocol":"modbus","calibration":{"valid":true}}'::JSONB
        ),
        (
            'PS-2026-0043',
            'Industrial Measurement Systems',
            16.00::NUMERIC,
            NULL::BOOLEAN,
            ARRAY['plant-b']::TEXT[],
            '{"protocol":"mqtt","calibration":{"valid":false}}'::JSONB
        )
) AS source(
    serial_number,
    manufacturer_name,
    nominal_pressure_bar,
    is_active,
    labels,
    metadata
)
JOIN manufacturers AS manufacturer
    ON manufacturer.name = source.manufacturer_name
ON CONFLICT (serial_number) DO NOTHING;

INSERT INTO telemetry_readings (
    equipment_id,
    measured_at,
    pressure_bar,
    temperature_c,
    is_valid,
    payload
)
SELECT
    equipment_id,
    now() - interval '5 minutes',
    7.4200,
    28.6,
    TRUE,
    '{"source":"edge-gateway-01","unit":"bar"}'::JSONB
FROM equipment
WHERE serial_number = 'PS-2026-0042'
AND NOT EXISTS (
    SELECT 1
    FROM telemetry_readings AS existing
    WHERE existing.equipment_id = equipment.equipment_id
      AND existing.payload ->> 'source' = 'edge-gateway-01'
);

-- NUMERIC stores exact decimal values for quantities that require decimal
-- precision. Use DOUBLE PRECISION for scientific measurements where binary
-- floating-point behavior is acceptable.
SELECT
    serial_number,
    nominal_pressure_bar,
    pg_typeof(nominal_pressure_bar) AS actual_type
FROM equipment
ORDER BY serial_number;

-- Boolean NULL is distinct from FALSE. IS UNKNOWN makes the distinction clear.
SELECT
    serial_number,
    is_active,
    CASE
        WHEN is_active IS TRUE THEN 'active'
        WHEN is_active IS FALSE THEN 'inactive'
        ELSE 'unknown'
    END AS activity_state
FROM equipment
ORDER BY serial_number;

-- UUID values can be generated by PostgreSQL and used as relational keys.
SELECT equipment_id, serial_number
FROM equipment
WHERE serial_number = 'PS-2026-0042';

-- JSONB extraction operators return JSONB or text depending on the operator.
SELECT
    serial_number,
    metadata -> 'calibration' AS calibration_document,
    metadata ->> 'protocol' AS communication_protocol,
    metadata #>> '{calibration,valid}' AS calibration_valid_text
FROM equipment
WHERE metadata @> '{"protocol":"modbus"}'::JSONB;

-- Array membership uses ANY; GIN indexes can support appropriate array queries.
SELECT serial_number, labels
FROM equipment
WHERE 'critical' = ANY(labels);

-- Telemetry payload and scalar columns can be filtered together.
SELECT
    equipment.serial_number,
    telemetry.measured_at,
    telemetry.pressure_bar,
    telemetry.payload ->> 'source' AS gateway
FROM telemetry_readings AS telemetry
JOIN equipment
    ON equipment.equipment_id = telemetry.equipment_id
WHERE telemetry.is_valid IS TRUE
ORDER BY telemetry.measured_at DESC;

-- A view can expose typed business attributes while retaining JSONB metadata.
CREATE OR REPLACE VIEW equipment_calibration_status AS
SELECT
    equipment_id,
    serial_number,
    metadata #>> '{calibration,valid}' AS calibration_valid,
    metadata ->> 'protocol' AS protocol
FROM equipment;

SELECT *
FROM equipment_calibration_status
ORDER BY serial_number;

-- The following invalid writes are deliberately documented rather than run:
-- INSERT INTO equipment (...) VALUES (..., -1.00, ...);
-- Rejected by equipment_pressure_nonnegative.
--
-- INSERT INTO equipment (...) VALUES (..., '{"unexpected": [}'::JSONB);
-- Rejected because the JSONB literal is invalid JSON.
--
-- INSERT INTO equipment (...) VALUES (..., ARRAY['critical', NULL], ...);
-- Rejected by equipment_labels_no_null_elements.
--
-- INSERT INTO equipment (...) VALUES (..., NULL, ...);
-- A missing nominal pressure is rejected by NOT NULL.

-- NUMERIC precision and scale can be inspected directly.
SELECT
    table_name,
    column_name,
    data_type,
    numeric_precision,
    numeric_scale,
    udt_name
FROM information_schema.columns
WHERE table_schema = 'industrial_registry'
  AND table_name IN ('equipment', 'telemetry_readings')
ORDER BY table_name, ordinal_position;

COMMIT;

-- Production design notes:
-- Keep stable, frequently queried business attributes in typed columns.
-- Use JSONB for flexible attributes that still require structured validation.
-- Normalize arrays into child tables when elements require independent
-- constraints, relationships, frequent updates, or individual lifecycle rules.
-- Use parameterized queries for values and least-privilege database roles.
