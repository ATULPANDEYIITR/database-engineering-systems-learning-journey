-- PostgreSQL Configuration Laboratory
-- Models configuration metadata, configuration files, memory settings,
-- connection settings, validation, reload/restart semantics, and reporting.

DROP SCHEMA IF EXISTS pg_config_lab CASCADE;
CREATE SCHEMA pg_config_lab;

SET search_path = pg_config_lab, public;

CREATE TYPE setting_category AS ENUM (
    'memory',
    'connection',
    'general'
);

CREATE TYPE apply_mode AS ENUM (
    'reload',
    'restart'
);

CREATE TYPE server_state AS ENUM (
    'running',
    'reload_pending',
    'restart_pending'
);

CREATE TABLE repositories (
    repository_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name text NOT NULL UNIQUE,
    environment text NOT NULL CHECK (
        environment IN ('development', 'staging', 'production')
    ),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE configuration_files (
    configuration_file_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id bigint NOT NULL REFERENCES repositories(repository_id),
    file_name text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    UNIQUE (repository_id, file_name)
);

CREATE TABLE setting_definitions (
    setting_name text PRIMARY KEY,
    category setting_category NOT NULL,
    default_value text NOT NULL,
    minimum_value bigint,
    maximum_value bigint,
    requires_restart boolean NOT NULL DEFAULT false,
    description text NOT NULL,
    CHECK (
        minimum_value IS NULL
        OR maximum_value IS NULL
        OR minimum_value <= maximum_value
    )
);

CREATE TABLE configuration_values (
    configuration_file_id bigint NOT NULL
        REFERENCES configuration_files(configuration_file_id)
        ON DELETE CASCADE,
    setting_name text NOT NULL
        REFERENCES setting_definitions(setting_name),
    setting_value text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (configuration_file_id, setting_name)
);

CREATE TABLE database_sessions (
    session_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id bigint NOT NULL REFERENCES repositories(repository_id),
    application_name text NOT NULL,
    session_started_at timestamptz NOT NULL DEFAULT now(),
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE session_overrides (
    session_id bigint NOT NULL
        REFERENCES database_sessions(session_id)
        ON DELETE CASCADE,
    setting_name text NOT NULL
        REFERENCES setting_definitions(setting_name),
    setting_value text NOT NULL,
    PRIMARY KEY (session_id, setting_name)
);

CREATE TABLE configuration_changes (
    change_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id bigint NOT NULL REFERENCES repositories(repository_id),
    setting_name text NOT NULL REFERENCES setting_definitions(setting_name),
    old_value text,
    new_value text NOT NULL,
    apply_mode apply_mode NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT now(),
    applied boolean NOT NULL DEFAULT false
);

CREATE TABLE server_runtime (
    repository_id bigint PRIMARY KEY
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    state server_state NOT NULL DEFAULT 'running',
    last_reload_at timestamptz,
    last_restart_at timestamptz
);

INSERT INTO repositories (repository_name, environment)
VALUES
    ('orders-api', 'production'),
    ('analytics-api', 'staging'),
    ('developer-db', 'development');

INSERT INTO configuration_files (repository_id, file_name)
SELECT repository_id, 'postgresql.conf'
FROM repositories;

INSERT INTO setting_definitions (
    setting_name,
    category,
    default_value,
    minimum_value,
    maximum_value,
    requires_restart,
    description
)
VALUES
(
    'max_connections',
    'connection',
    '100',
    10,
    10000,
    false,
    'Maximum number of concurrent server connections'
),
(
    'shared_buffers',
    'memory',
    '128MB',
    16777216,
    1099511627776,
    true,
    'Memory allocated to PostgreSQL shared buffers'
),
(
    'work_mem',
    'memory',
    '4MB',
    65536,
    1073741824,
    false,
    'Memory available to an individual query operation'
),
(
    'maintenance_work_mem',
    'memory',
    '64MB',
    1048576,
    2147483648,
    false,
    'Memory available to maintenance operations'
),
(
    'effective_cache_size',
    'memory',
    '4GB',
    134217728,
    4398046511104,
    false,
    'Planner estimate of filesystem cache'
),
(
    'statement_timeout',
    'connection',
    '0',
    0,
    86400000,
    false,
    'Maximum statement duration in milliseconds'
),
(
    'idle_in_transaction_session_timeout',
    'connection',
    '0',
    0,
    86400000,
    false,
    'Maximum idle transaction duration in milliseconds'
),
(
    'listen_addresses',
    'connection',
    'localhost',
    NULL,
    NULL,
    false,
    'Network addresses accepted by the PostgreSQL server'
),
(
    'port',
    'connection',
    '5432',
    1,
    65535,
    true,
    'TCP listener port'
);

INSERT INTO configuration_values (
    configuration_file_id,
    setting_name,
    setting_value
)
SELECT
    cf.configuration_file_id,
    v.setting_name,
    v.setting_value
FROM configuration_files cf
JOIN repositories r
  ON r.repository_id = cf.repository_id
CROSS JOIN LATERAL (
    VALUES
        ('max_connections', CASE
            WHEN r.environment = 'production' THEN '200'
            WHEN r.environment = 'staging' THEN '120'
            ELSE '80'
        END),
        ('shared_buffers', CASE
            WHEN r.environment = 'production' THEN '512MB'
            WHEN r.environment = 'staging' THEN '256MB'
            ELSE '128MB'
        END),
        ('work_mem', CASE
            WHEN r.environment = 'production' THEN '8MB'
            ELSE '4MB'
        END),
        ('maintenance_work_mem', CASE
            WHEN r.environment = 'production' THEN '128MB'
            ELSE '64MB'
        END),
        ('effective_cache_size', CASE
            WHEN r.environment = 'production' THEN '4GB'
            ELSE '1GB'
        END),
        ('statement_timeout', CASE
            WHEN r.environment = 'production' THEN '30000'
            ELSE '0'
        END),
        ('idle_in_transaction_session_timeout', CASE
            WHEN r.environment = 'production' THEN '60000'
            ELSE '0'
        END),
        ('listen_addresses', 'localhost'),
        ('port', '5432')
) AS v(setting_name, setting_value)
WHERE cf.file_name = 'postgresql.conf';

INSERT INTO database_sessions (repository_id, application_name)
SELECT repository_id, 'orders-worker'
FROM repositories
WHERE repository_name = 'orders-api';

INSERT INTO session_overrides (
    session_id,
    setting_name,
    setting_value
)
SELECT
    ds.session_id,
    'work_mem',
    '16MB'
FROM database_sessions ds
JOIN repositories r
  ON r.repository_id = ds.repository_id
WHERE r.repository_name = 'orders-api';

INSERT INTO server_runtime (repository_id)
SELECT repository_id
FROM repositories;

CREATE OR REPLACE FUNCTION numeric_setting_value(p_value text)
RETURNS bigint
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    cleaned text;
    amount bigint;
    unit text;
BEGIN
    cleaned := lower(regexp_replace(trim(p_value), '\s+', '', 'g'));

    IF cleaned !~ '^[0-9]+(kb|mb|gb)?$' THEN
        RAISE EXCEPTION 'Invalid numeric configuration value: %', p_value;
    END IF;

    amount := regexp_replace(cleaned, '[^0-9]', '', 'g')::bigint;
    unit := regexp_replace(cleaned, '^[0-9]+', '');

    RETURN CASE unit
        WHEN '' THEN amount
        WHEN 'kb' THEN amount * 1024
        WHEN 'mb' THEN amount * 1024 * 1024
        WHEN 'gb' THEN amount * 1024 * 1024 * 1024
        ELSE NULL
    END;
END;
$$;

CREATE OR REPLACE FUNCTION validate_configuration_value()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    definition setting_definitions%ROWTYPE;
    numeric_value bigint;
BEGIN
    SELECT *
    INTO definition
    FROM setting_definitions
    WHERE setting_name = NEW.setting_name;

    IF definition.minimum_value IS NULL
       AND definition.maximum_value IS NULL THEN
        IF btrim(NEW.setting_value) = '' THEN
            RAISE EXCEPTION
                'Setting % cannot be empty',
                NEW.setting_name;
        END IF;
    ELSE
        numeric_value := numeric_setting_value(NEW.setting_value);

        IF definition.minimum_value IS NOT NULL
           AND numeric_value < definition.minimum_value THEN
            RAISE EXCEPTION
                'Setting % is below minimum',
                NEW.setting_name;
        END IF;

        IF definition.maximum_value IS NOT NULL
           AND numeric_value > definition.maximum_value THEN
            RAISE EXCEPTION
                'Setting % exceeds maximum',
                NEW.setting_name;
        END IF;
    END IF;

    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER configuration_value_validation
BEFORE INSERT OR UPDATE
ON configuration_values
FOR EACH ROW
EXECUTE FUNCTION validate_configuration_value();

CREATE OR REPLACE FUNCTION configuration_change_audit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    definition setting_definitions%ROWTYPE;
    repository_id_value bigint;
    previous_value text;
BEGIN
    SELECT *
    INTO definition
    FROM setting_definitions
    WHERE setting_name = NEW.setting_name;

    SELECT cf.repository_id
    INTO repository_id_value
    FROM configuration_files cf
    WHERE cf.configuration_file_id = NEW.configuration_file_id;

    SELECT cv.setting_value
    INTO previous_value
    FROM configuration_values cv
    WHERE cv.configuration_file_id = NEW.configuration_file_id
      AND cv.setting_name = NEW.setting_name;

    INSERT INTO configuration_changes (
        repository_id,
        setting_name,
        old_value,
        new_value,
        apply_mode
    )
    VALUES (
        repository_id_value,
        NEW.setting_name,
        previous_value,
        NEW.setting_value,
        CASE
            WHEN definition.requires_restart THEN 'restart'::apply_mode
            ELSE 'reload'::apply_mode
        END
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER configuration_change_audit_trigger
AFTER INSERT OR UPDATE
ON configuration_values
FOR EACH ROW
EXECUTE FUNCTION configuration_change_audit();

CREATE OR REPLACE VIEW effective_configuration AS
SELECT
    r.repository_name,
    r.environment,
    sd.setting_name,
    sd.category,
    sd.default_value,
    cv.setting_value AS file_value,
    COALESCE(cv.setting_value, sd.default_value) AS effective_value,
    sd.requires_restart
FROM repositories r
JOIN configuration_files cf
  ON cf.repository_id = r.repository_id
 AND cf.active
JOIN setting_definitions sd
  ON true
LEFT JOIN configuration_values cv
  ON cv.configuration_file_id = cf.configuration_file_id
 AND cv.setting_name = sd.setting_name;

CREATE OR REPLACE VIEW configuration_memory_report AS
SELECT
    repository_name,
    environment,
    numeric_setting_value(
        MAX(effective_value) FILTER (
            WHERE setting_name = 'max_connections'
        )
    ) AS max_connections,
    numeric_setting_value(
        MAX(effective_value) FILTER (
            WHERE setting_name = 'work_mem'
        )
    ) AS work_mem_bytes,
    numeric_setting_value(
        MAX(effective_value) FILTER (
            WHERE setting_name = 'shared_buffers'
        )
    ) AS shared_buffers_bytes
FROM effective_configuration
GROUP BY repository_name, environment;

CREATE OR REPLACE FUNCTION configuration_warnings(
    p_repository_name text
)
RETURNS TABLE (
    warning_type text,
    detail text
)
LANGUAGE plpgsql
AS $$
DECLARE
    max_connections bigint;
    work_mem bigint;
    shared_buffers bigint;
    listener text;
BEGIN
    SELECT
        numeric_setting_value(
            MAX(effective_value) FILTER (
                WHERE setting_name = 'max_connections'
            )
        ),
        numeric_setting_value(
            MAX(effective_value) FILTER (
                WHERE setting_name = 'work_mem'
            )
        ),
        numeric_setting_value(
            MAX(effective_value) FILTER (
                WHERE setting_name = 'shared_buffers'
            )
        ),
        MAX(effective_value) FILTER (
            WHERE setting_name = 'listen_addresses'
        )
    INTO
        max_connections,
        work_mem,
        shared_buffers,
        listener
    FROM effective_configuration
    WHERE repository_name = p_repository_name;

    IF max_connections * work_mem > shared_buffers * 4 THEN
        warning_type := 'memory_pressure';
        detail := 'max_connections multiplied by work_mem is high relative to shared_buffers';
        RETURN NEXT;
    END IF;

    IF max_connections > 2000 THEN
        warning_type := 'connection_scale';
        detail := 'Very high max_connections; connection pooling should be considered';
        RETURN NEXT;
    END IF;

    IF listener = '*' THEN
        warning_type := 'network_exposure';
        detail := 'listen_addresses exposes the server on all interfaces';
        RETURN NEXT;
    END IF;
END;
$$;

CREATE INDEX idx_configuration_values_setting
    ON configuration_values(setting_name);

CREATE INDEX idx_configuration_changes_repository_time
    ON configuration_changes(repository_id, changed_at DESC);

CREATE INDEX idx_sessions_repository_active
    ON database_sessions(repository_id, active);

-- Retrieval: complete effective configuration for production.
SELECT *
FROM effective_configuration
WHERE environment = 'production'
ORDER BY setting_name;

-- Memory assessment.
SELECT *
FROM configuration_memory_report
ORDER BY repository_name;

-- Validation and warnings.
SELECT *
FROM configuration_warnings('orders-api');

-- Approval-like operational check: settings requiring restart.
SELECT
    repository_name,
    setting_name,
    effective_value
FROM effective_configuration
WHERE requires_restart
ORDER BY repository_name, setting_name;

-- Session-level overrides demonstrate that a session value can differ
-- from the persistent configuration file.
SELECT
    r.repository_name,
    ds.application_name,
    so.setting_name,
    so.setting_value AS session_value,
    ec.effective_value AS persistent_value
FROM session_overrides so
JOIN database_sessions ds
  ON ds.session_id = so.session_id
JOIN repositories r
  ON r.repository_id = ds.repository_id
JOIN effective_configuration ec
  ON ec.repository_name = r.repository_name
 AND ec.setting_name = so.setting_name;

-- Change audit.
SELECT
    r.repository_name,
    cc.setting_name,
    cc.old_value,
    cc.new_value,
    cc.apply_mode,
    cc.changed_at
FROM configuration_changes cc
JOIN repositories r
  ON r.repository_id = cc.repository_id
ORDER BY cc.changed_at DESC;

-- Transactional configuration update.
BEGIN;

UPDATE configuration_values cv
SET setting_value = '10MB'
FROM configuration_files cf
JOIN repositories r
  ON r.repository_id = cf.repository_id
WHERE cv.configuration_file_id = cf.configuration_file_id
  AND cv.setting_name = 'work_mem'
  AND r.repository_name = 'orders-api';

-- The trigger validates the value before the transaction can commit.
COMMIT;

-- Demonstrate a failed transaction without leaving invalid data behind.
BEGIN;

DO $$
BEGIN
    UPDATE configuration_values cv
    SET setting_value = '1MB'
    FROM configuration_files cf
    JOIN repositories r
      ON r.repository_id = cf.repository_id
    WHERE cv.configuration_file_id = cf.configuration_file_id
      AND cv.setting_name = 'shared_buffers'
      AND r.repository_name = 'orders-api';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Expected configuration validation failure: %', SQLERRM;
        ROLLBACK;
END;
$$;

-- PostgreSQL configuration is controlled by server configuration files,
-- ALTER SYSTEM, ALTER DATABASE, ALTER ROLE, and session-level SET commands.
-- This schema models the resulting configuration lifecycle but does not
-- replace PostgreSQL's actual postgresql.conf or pg_hba.conf processing.
