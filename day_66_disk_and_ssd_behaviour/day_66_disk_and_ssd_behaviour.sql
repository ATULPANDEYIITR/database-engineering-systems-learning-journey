-- ============================================================
-- DISK AND SSD BEHAVIOR
-- PostgreSQL 18 compatible storage performance monitoring model
--
-- Models:
-- 1. Storage device inventory
-- 2. Sequential and random I/O workloads
-- 3. Benchmark execution
-- 4. Request-level latency measurements
-- 5. Queue depth
-- 6. Performance policies
-- 7. Latency percentile analysis
-- 8. SLA evaluation
-- 9. Device availability and maintenance
--
-- All throughput and latency values are estimates or recorded
-- measurements. The database does not perform physical I/O
-- benchmarking on the host storage device.
-- ============================================================

DROP SCHEMA IF EXISTS storage_lab CASCADE;

CREATE SCHEMA storage_lab;

SET search_path TO storage_lab, public;

-- ============================================================
-- 1. DOMAIN TYPES
-- ============================================================

CREATE TYPE storage_type AS ENUM (
    'HDD',
    'SATA_SSD',
    'NVME_SSD'
);

CREATE TYPE io_operation AS ENUM (
    'SEQUENTIAL_READ',
    'RANDOM_READ',
    'SEQUENTIAL_WRITE',
    'RANDOM_WRITE'
);

CREATE TYPE device_status AS ENUM (
    'ACTIVE',
    'DEGRADED',
    'MAINTENANCE',
    'FAILED'
);

CREATE TYPE benchmark_status AS ENUM (
    'CREATED',
    'RUNNING',
    'COMPLETED',
    'FAILED'
);

CREATE TYPE policy_decision AS ENUM (
    'PASS',
    'WARNING',
    'CRITICAL',
    'REJECTED'
);

-- ============================================================
-- 2. STORAGE INVENTORY
-- ============================================================

CREATE TABLE storage_devices (
    device_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    device_name VARCHAR(150) NOT NULL UNIQUE,

    device_type storage_type NOT NULL,

    manufacturer VARCHAR(100),

    capacity_gb NUMERIC(12, 2) NOT NULL,

    sequential_read_mbps NUMERIC(14, 2) NOT NULL,

    sequential_write_mbps NUMERIC(14, 2) NOT NULL,

    random_read_iops NUMERIC(14, 2) NOT NULL,

    random_write_iops NUMERIC(14, 2) NOT NULL,

    access_latency_ms NUMERIC(12, 6) NOT NULL,

    maximum_queue_depth INTEGER NOT NULL,

    current_status device_status NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT positive_capacity
        CHECK (capacity_gb > 0),

    CONSTRAINT positive_sequential_read
        CHECK (sequential_read_mbps > 0),

    CONSTRAINT positive_sequential_write
        CHECK (sequential_write_mbps > 0),

    CONSTRAINT positive_random_read
        CHECK (random_read_iops > 0),

    CONSTRAINT positive_random_write
        CHECK (random_write_iops > 0),

    CONSTRAINT positive_latency
        CHECK (access_latency_ms > 0),

    CONSTRAINT positive_queue_depth
        CHECK (maximum_queue_depth > 0)
);

CREATE INDEX idx_devices_type_status
ON storage_devices(device_type, current_status);

-- ============================================================
-- 3. APPLICATION INVENTORY
-- ============================================================

CREATE TABLE applications (
    application_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    application_name VARCHAR(150) NOT NULL UNIQUE,

    workload_category VARCHAR(50) NOT NULL,

    criticality VARCHAR(20) NOT NULL,

    CONSTRAINT valid_criticality
        CHECK (
            criticality IN (
                'LOW',
                'MEDIUM',
                'HIGH',
                'CRITICAL'
            )
        )
);

-- ============================================================
-- 4. PERFORMANCE POLICIES
-- ============================================================

CREATE TABLE performance_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(150) NOT NULL UNIQUE,

    maximum_average_latency_ms NUMERIC(12, 4) NOT NULL,

    maximum_p95_latency_ms NUMERIC(12, 4) NOT NULL,

    maximum_p99_latency_ms NUMERIC(12, 4) NOT NULL,

    minimum_iops NUMERIC(14, 2) NOT NULL,

    minimum_throughput_mbps NUMERIC(14, 2) NOT NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_latency_limits
        CHECK (
            maximum_average_latency_ms > 0
            AND maximum_p95_latency_ms > 0
            AND maximum_p99_latency_ms > 0
        ),

    CONSTRAINT valid_performance_limits
        CHECK (
            minimum_iops > 0
            AND minimum_throughput_mbps > 0
        )
);

CREATE INDEX idx_active_policies
ON performance_policies(policy_id)
WHERE is_active = TRUE;

-- ============================================================
-- 5. BENCHMARK EXECUTION
-- ============================================================

CREATE TABLE benchmark_runs (
    benchmark_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    device_id BIGINT NOT NULL
        REFERENCES storage_devices(device_id),

    application_id BIGINT NOT NULL
        REFERENCES applications(application_id),

    policy_id BIGINT
        REFERENCES performance_policies(policy_id),

    operation io_operation NOT NULL,

    block_size_bytes BIGINT NOT NULL,

    requested_operations INTEGER NOT NULL,

    queue_depth INTEGER NOT NULL DEFAULT 1,

    status benchmark_status NOT NULL DEFAULT 'CREATED',

    started_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_block_size
        CHECK (block_size_bytes > 0),

    CONSTRAINT valid_operation_count
        CHECK (requested_operations > 0),

    CONSTRAINT valid_benchmark_queue
        CHECK (queue_depth > 0),

    CONSTRAINT valid_completion_time
        CHECK (
            completed_at IS NULL
            OR (
                started_at IS NOT NULL
                AND completed_at >= started_at
            )
        ),

    CONSTRAINT valid_failure_message
        CHECK (
            status <> 'FAILED'
            OR error_message IS NOT NULL
        )
);

CREATE INDEX idx_benchmark_device_created
ON benchmark_runs(device_id, created_at DESC);

CREATE INDEX idx_benchmark_status
ON benchmark_runs(status, created_at);

CREATE INDEX idx_benchmark_operation
ON benchmark_runs(operation, device_id);

-- ============================================================
-- 6. INDIVIDUAL I/O OBSERVATIONS
-- ============================================================

CREATE TABLE io_observations (
    observation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    benchmark_id BIGINT NOT NULL
        REFERENCES benchmark_runs(benchmark_id)
        ON DELETE CASCADE,

    operation_number INTEGER NOT NULL,

    bytes_transferred BIGINT NOT NULL,

    latency_ms NUMERIC(14, 6) NOT NULL,

    queue_wait_ms NUMERIC(14, 6) NOT NULL DEFAULT 0,

    service_time_ms NUMERIC(14, 6) NOT NULL,

    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_operation_per_run
        UNIQUE (benchmark_id, operation_number),

    CONSTRAINT positive_operation_number
        CHECK (operation_number > 0),

    CONSTRAINT positive_bytes
        CHECK (bytes_transferred > 0),

    CONSTRAINT positive_latency
        CHECK (latency_ms > 0),

    CONSTRAINT nonnegative_queue_wait
        CHECK (queue_wait_ms >= 0),

    CONSTRAINT positive_service_time
        CHECK (service_time_ms > 0)
);

CREATE INDEX idx_observations_benchmark
ON io_observations(benchmark_id);

CREATE INDEX idx_observations_latency
ON io_observations(latency_ms DESC);

-- ============================================================
-- 7. BENCHMARK RESULTS
-- ============================================================

CREATE TABLE benchmark_results (
    benchmark_id BIGINT PRIMARY KEY
        REFERENCES benchmark_runs(benchmark_id)
        ON DELETE CASCADE,

    total_bytes BIGINT NOT NULL,

    average_latency_ms NUMERIC(14, 6) NOT NULL,

    p95_latency_ms NUMERIC(14, 6) NOT NULL,

    p99_latency_ms NUMERIC(14, 6) NOT NULL,

    throughput_mbps NUMERIC(14, 4) NOT NULL,

    achieved_iops NUMERIC(14, 4) NOT NULL,

    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT positive_result_bytes
        CHECK (total_bytes > 0),

    CONSTRAINT valid_result_latency
        CHECK (
            average_latency_ms > 0
            AND p95_latency_ms > 0
            AND p99_latency_ms > 0
            AND p95_latency_ms >= average_latency_ms
            AND p99_latency_ms >= p95_latency_ms
        ),

    CONSTRAINT positive_result_performance
        CHECK (
            throughput_mbps > 0
            AND achieved_iops > 0
        )
);

-- ============================================================
-- 8. POLICY EVALUATIONS
-- ============================================================

CREATE TABLE policy_evaluations (
    evaluation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    benchmark_id BIGINT NOT NULL
        REFERENCES benchmark_runs(benchmark_id),

    policy_id BIGINT NOT NULL
        REFERENCES performance_policies(policy_id),

    decision policy_decision NOT NULL,

    violations TEXT[] NOT NULL DEFAULT '{}',

    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (benchmark_id, policy_id)
);

CREATE INDEX idx_policy_evaluations_decision
ON policy_evaluations(decision, evaluated_at DESC);

-- ============================================================
-- 9. DEVICE STATUS HISTORY
-- ============================================================

CREATE TABLE device_status_history (
    history_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    device_id BIGINT NOT NULL
        REFERENCES storage_devices(device_id),

    previous_status device_status,

    new_status device_status NOT NULL,

    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    reason TEXT
);

-- ============================================================
-- 10. DEVICE STATUS TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION record_device_status_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.current_status IS DISTINCT FROM NEW.current_status THEN

        IF OLD.current_status = 'FAILED'
           AND NEW.current_status = 'ACTIVE' THEN

            RAISE EXCEPTION
                'Failed storage devices cannot return to ACTIVE directly';

        END IF;

        INSERT INTO device_status_history (
            device_id,
            previous_status,
            new_status,
            reason
        )
        VALUES (
            NEW.device_id,
            OLD.current_status,
            NEW.current_status,
            'Device status updated'
        );

    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_device_status_change
AFTER UPDATE OF current_status
ON storage_devices
FOR EACH ROW
EXECUTE FUNCTION record_device_status_change();

-- ============================================================
-- 11. BENCHMARK STATE VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_benchmark_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'CREATED' THEN
            RAISE EXCEPTION
                'New benchmarks must begin in CREATED state';
        END IF;

        RETURN NEW;
    END IF;

    IF OLD.status IN ('COMPLETED', 'FAILED') THEN
        RAISE EXCEPTION
            'Terminal benchmark states cannot be modified';
    END IF;

    IF OLD.status = 'CREATED'
       AND NEW.status NOT IN ('CREATED', 'RUNNING', 'FAILED') THEN
        RAISE EXCEPTION
            'Invalid CREATED benchmark transition';
    END IF;

    IF OLD.status = 'RUNNING'
       AND NEW.status NOT IN ('RUNNING', 'COMPLETED', 'FAILED') THEN
        RAISE EXCEPTION
            'Invalid RUNNING benchmark transition';
    END IF;

    IF NEW.status = 'RUNNING'
       AND NEW.started_at IS NULL THEN
        RAISE EXCEPTION
            'RUNNING benchmark requires started_at';
    END IF;

    IF NEW.status IN ('COMPLETED', 'FAILED')
       AND NEW.completed_at IS NULL THEN
        RAISE EXCEPTION
            'Terminal benchmark requires completed_at';
    END IF;

    IF NEW.status = 'COMPLETED'
       AND NEW.error_message IS NOT NULL THEN
        RAISE EXCEPTION
            'Completed benchmark cannot contain an error';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_benchmark_transition
BEFORE INSERT OR UPDATE
ON benchmark_runs
FOR EACH ROW
EXECUTE FUNCTION validate_benchmark_transition();

-- ============================================================
-- 12. PERFORMANCE RESULT VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION validate_benchmark_result()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_status benchmark_status;
    v_device_status device_status;
    v_count BIGINT;
    v_bytes BIGINT;
BEGIN
    SELECT
        br.status,
        sd.current_status
    INTO
        v_status,
        v_device_status
    FROM benchmark_runs br
    JOIN storage_devices sd
      ON sd.device_id = br.device_id
    WHERE br.benchmark_id = NEW.benchmark_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Benchmark does not exist';
    END IF;

    IF v_status <> 'RUNNING' THEN
        RAISE EXCEPTION
            'Results can only be saved for RUNNING benchmarks';
    END IF;

    IF v_device_status NOT IN ('ACTIVE', 'DEGRADED') THEN
        RAISE EXCEPTION
            'Device is not eligible for benchmark result storage';
    END IF;

    SELECT
        COUNT(*),
        COALESCE(SUM(bytes_transferred), 0)
    INTO
        v_count,
        v_bytes
    FROM io_observations
    WHERE benchmark_id = NEW.benchmark_id;

    IF v_count = 0 THEN
        RAISE EXCEPTION
            'Benchmark has no observations';
    END IF;

    IF NEW.total_bytes <> v_bytes THEN
        RAISE EXCEPTION
            'Result byte count does not match observations';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_benchmark_result
BEFORE INSERT OR UPDATE
ON benchmark_results
FOR EACH ROW
EXECUTE FUNCTION validate_benchmark_result();

-- ============================================================
-- 13. BENCHMARK CALCULATION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION calculate_benchmark(
    p_benchmark_id BIGINT
)
RETURNS TABLE (
    total_bytes BIGINT,
    average_latency_ms NUMERIC,
    p95_latency_ms NUMERIC,
    p99_latency_ms NUMERIC,
    throughput_mbps NUMERIC,
    achieved_iops NUMERIC
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_bytes BIGINT;
    v_avg NUMERIC;
    v_p95 NUMERIC;
    v_p99 NUMERIC;
    v_elapsed NUMERIC;
BEGIN
    SELECT
        SUM(bytes_transferred),
        AVG(latency_ms),
        percentile_cont(0.95)
            WITHIN GROUP (ORDER BY latency_ms),
        percentile_cont(0.99)
            WITHIN GROUP (ORDER BY latency_ms),
        SUM(latency_ms)
    INTO
        v_bytes,
        v_avg,
        v_p95,
        v_p99,
        v_elapsed
    FROM io_observations
    WHERE benchmark_id = p_benchmark_id;

    IF v_bytes IS NULL OR v_elapsed IS NULL OR v_elapsed <= 0 THEN
        RAISE EXCEPTION
            'No valid observations for benchmark %',
            p_benchmark_id;
    END IF;

    RETURN QUERY
    SELECT
        v_bytes,
        v_avg,
        v_p95,
        v_p99,
        (
            v_bytes::NUMERIC / 1048576.0
        ) / (v_elapsed / 1000.0),
        (
            1000.0 * (
                SELECT COUNT(*)
                FROM io_observations
                WHERE benchmark_id = p_benchmark_id
            ) / v_elapsed
        );
END;
$$;

-- ============================================================
-- 14. POLICY EVALUATION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_benchmark_policy(
    p_benchmark_id BIGINT,
    p_policy_id BIGINT
)
RETURNS policy_decision
LANGUAGE plpgsql
AS $$
DECLARE
    v_result benchmark_results%ROWTYPE;
    v_policy performance_policies%ROWTYPE;

    v_violations TEXT[] := '{}';

    v_decision policy_decision;
BEGIN
    SELECT *
    INTO v_result
    FROM benchmark_results
    WHERE benchmark_id = p_benchmark_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Benchmark results do not exist';
    END IF;

    SELECT *
    INTO v_policy
    FROM performance_policies
    WHERE policy_id = p_policy_id
      AND is_active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Active performance policy does not exist';
    END IF;

    IF v_result.average_latency_ms >
       v_policy.maximum_average_latency_ms THEN

        v_violations := array_append(
            v_violations,
            'Average latency exceeds limit'
        );
    END IF;

    IF v_result.p95_latency_ms >
       v_policy.maximum_p95_latency_ms THEN

        v_violations := array_append(
            v_violations,
            'P95 latency exceeds limit'
        );
    END IF;

    IF v_result.p99_latency_ms >
       v_policy.maximum_p99_latency_ms THEN

        v_violations := array_append(
            v_violations,
            'P99 latency exceeds limit'
        );
    END IF;

    IF v_result.achieved_iops < v_policy.minimum_iops THEN

        v_violations := array_append(
            v_violations,
            'IOPS below minimum'
        );
    END IF;

    IF v_result.throughput_mbps <
       v_policy.minimum_throughput_mbps THEN

        v_violations := array_append(
            v_violations,
            'Throughput below minimum'
        );
    END IF;

    IF cardinality(v_violations) = 0 THEN
        v_decision := 'PASS';
    ELSIF v_result.p99_latency_ms >
          v_policy.maximum_p99_latency_ms * 2 THEN
        v_decision := 'CRITICAL';
    ELSE
        v_decision := 'WARNING';
    END IF;

    INSERT INTO policy_evaluations (
        benchmark_id,
        policy_id,
        decision,
        violations
    )
    VALUES (
        p_benchmark_id,
        p_policy_id,
        v_decision,
        v_violations
    )
    ON CONFLICT (benchmark_id, policy_id)
    DO UPDATE SET
        decision = EXCLUDED.decision,
        violations = EXCLUDED.violations,
        evaluated_at = CURRENT_TIMESTAMP;

    RETURN v_decision;
END;
$$;

-- ============================================================
-- 15. BENCHMARK COMPLETION PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE complete_benchmark(
    p_benchmark_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_result RECORD;
    v_expected INTEGER;
    v_actual BIGINT;
    v_device device_status;
BEGIN
    SELECT requested_operations, sd.current_status
    INTO v_expected, v_device
    FROM benchmark_runs br
    JOIN storage_devices sd
      ON sd.device_id = br.device_id
    WHERE br.benchmark_id = p_benchmark_id
      AND br.status = 'RUNNING';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Benchmark must be RUNNING before completion';
    END IF;

    IF v_device NOT IN ('ACTIVE', 'DEGRADED') THEN
        RAISE EXCEPTION
            'Storage device is unavailable';
    END IF;

    SELECT COUNT(*)
    INTO v_actual
    FROM io_observations
    WHERE benchmark_id = p_benchmark_id;

    IF v_actual <> v_expected THEN
        RAISE EXCEPTION
            'Expected % observations, received %',
            v_expected,
            v_actual;
    END IF;

    SELECT *
    INTO v_result
    FROM calculate_benchmark(p_benchmark_id);

    INSERT INTO benchmark_results (
        benchmark_id,
        total_bytes,
        average_latency_ms,
        p95_latency_ms,
        p99_latency_ms,
        throughput_mbps,
        achieved_iops
    )
    VALUES (
        p_benchmark_id,
        v_result.total_bytes,
        v_result.average_latency_ms,
        v_result.p95_latency_ms,
        v_result.p99_latency_ms,
        v_result.throughput_mbps,
        v_result.achieved_iops
    );

    UPDATE benchmark_runs
    SET
        status = 'COMPLETED',
        completed_at = CURRENT_TIMESTAMP
    WHERE benchmark_id = p_benchmark_id;
END;
$$;

-- ============================================================
-- 16. REPORTING VIEW
-- ============================================================

CREATE VIEW storage_performance_report AS
SELECT
    br.benchmark_id,
    sd.device_name,
    sd.device_type,
    sd.current_status,
    ap.application_name,
    br.operation,
    br.block_size_bytes,
    br.queue_depth,
    br.status AS benchmark_status,
    res.total_bytes,
    res.average_latency_ms,
    res.p95_latency_ms,
    res.p99_latency_ms,
    res.throughput_mbps,
    res.achieved_iops,
    pe.decision,
    pe.violations,
    br.created_at
FROM benchmark_runs br
JOIN storage_devices sd
    ON sd.device_id = br.device_id
JOIN applications ap
    ON ap.application_id = br.application_id
LEFT JOIN benchmark_results res
    ON res.benchmark_id = br.benchmark_id
LEFT JOIN policy_evaluations pe
    ON pe.benchmark_id = br.benchmark_id
   AND pe.policy_id = br.policy_id;

-- ============================================================
-- 17. SAMPLE DEVICES
-- ============================================================

INSERT INTO storage_devices (
    device_name,
    device_type,
    manufacturer,
    capacity_gb,
    sequential_read_mbps,
    sequential_write_mbps,
    random_read_iops,
    random_write_iops,
    access_latency_ms,
    maximum_queue_depth
)
VALUES
(
    'Enterprise HDD 7200 RPM',
    'HDD',
    'Enterprise Storage',
    4000,
    180,
    160,
    120,
    110,
    8.0,
    4
),
(
    'SATA SSD 1TB',
    'SATA_SSD',
    'Solid State Systems',
    1000,
    550,
    500,
    90000,
    80000,
    0.08,
    32
),
(
    'NVMe SSD 2TB',
    'NVME_SSD',
    'High Performance Storage',
    2000,
    3500,
    3000,
    600000,
    500000,
    0.02,
    64
);

-- ============================================================
-- 18. SAMPLE APPLICATIONS
-- ============================================================

INSERT INTO applications (
    application_name,
    workload_category,
    criticality
)
VALUES
(
    'Database OLTP',
    'TRANSACTIONAL',
    'CRITICAL'
),
(
    'Backup Service',
    'SEQUENTIAL',
    'HIGH'
),
(
    'Analytics Platform',
    'ANALYTICAL',
    'HIGH'
),
(
    'File Archive',
    'ARCHIVAL',
    'MEDIUM'
);

-- ============================================================
-- 19. SAMPLE POLICIES
-- ============================================================

INSERT INTO performance_policies (
    policy_name,
    maximum_average_latency_ms,
    maximum_p95_latency_ms,
    maximum_p99_latency_ms,
    minimum_iops,
    minimum_throughput_mbps
)
VALUES
(
    'Database OLTP SLA',
    5,
    10,
    20,
    10000,
    10
),
(
    'Sequential Backup SLA',
    20,
    30,
    50,
    100,
    100
),
(
    'General Storage SLA',
    50,
    75,
    100,
    100,
    10
);

-- ============================================================
-- 20. SAMPLE BENCHMARKS AND OBSERVATIONS
--
-- These records are illustrative measurements.
-- They are not physical benchmark results.
-- ============================================================

DO $$
DECLARE
    v_device BIGINT;
    v_application BIGINT;
    v_policy BIGINT;
    v_benchmark BIGINT;

    v_operation io_operation;

    v_i INTEGER;
    v_latency NUMERIC;
    v_service NUMERIC;
    v_bytes BIGINT;

BEGIN

    SELECT device_id INTO v_device
    FROM storage_devices
    WHERE device_type = 'HDD';

    SELECT application_id INTO v_application
    FROM applications
    WHERE application_name = 'Database OLTP';

    SELECT policy_id INTO v_policy
    FROM performance_policies
    WHERE policy_name = 'Database OLTP SLA';

    FOREACH v_operation IN ARRAY ARRAY[
        'RANDOM_READ'::io_operation,
        'SEQUENTIAL_READ'::io_operation
    ]
    LOOP

        INSERT INTO benchmark_runs (
            device_id,
            application_id,
            policy_id,
            operation,
            block_size_bytes,
            requested_operations,
            queue_depth
        )
        VALUES (
            v_device,
            v_application,
            v_policy,
            v_operation,
            CASE
                WHEN v_operation = 'RANDOM_READ'
                THEN 4096
                ELSE 1048576
            END,
            100,
            8
        )
        RETURNING benchmark_id INTO v_benchmark;

        UPDATE benchmark_runs
        SET
            status = 'RUNNING',
            started_at = CURRENT_TIMESTAMP
        WHERE benchmark_id = v_benchmark;

        FOR v_i IN 1..100
        LOOP

            IF v_operation = 'RANDOM_READ' THEN
                v_service := 8.0 + 1000.0 / 120.0;
                v_latency := v_service +
                    ((v_i % 7) * 0.03);
                v_bytes := 4096;
            ELSE
                v_service :=
                    8.0 + (1048576.0 / (180.0 * 1048576.0)) * 1000;
                v_latency := v_service +
                    ((v_i % 7) * 0.03);
                v_bytes := 1048576;
            END IF;

            INSERT INTO io_observations (
                benchmark_id,
                operation_number,
                bytes_transferred,
                latency_ms,
                queue_wait_ms,
                service_time_ms
            )
            VALUES (
                v_benchmark,
                v_i,
                v_bytes,
                v_latency,
                GREATEST(v_latency - v_service, 0),
                v_service
            );

        END LOOP;

        CALL complete_benchmark(v_benchmark);

        PERFORM evaluate_benchmark_policy(
            v_benchmark,
            v_policy
        );

    END LOOP;
END;
$$;

-- ============================================================
-- 21. RETRIEVAL: DEVICE INVENTORY
-- ============================================================

SELECT
    device_name,
    device_type,
    capacity_gb,
    sequential_read_mbps,
    sequential_write_mbps,
    random_read_iops,
    random_write_iops,
    access_latency_ms,
    maximum_queue_depth,
    current_status
FROM storage_devices
ORDER BY device_type, device_name;

-- ============================================================
-- 22. RETRIEVAL: COMPLETED BENCHMARKS
-- ============================================================

SELECT *
FROM storage_performance_report
WHERE benchmark_status = 'COMPLETED'
ORDER BY benchmark_id;

-- ============================================================
-- 23. AGGREGATION: PERFORMANCE BY DEVICE
-- ============================================================

SELECT
    device_name,
    device_type,
    operation,
    COUNT(*) AS benchmark_count,
    ROUND(AVG(average_latency_ms), 4)
        AS average_latency_ms,
    ROUND(AVG(p99_latency_ms), 4)
        AS average_p99_latency_ms,
    ROUND(AVG(throughput_mbps), 2)
        AS average_throughput_mbps,
    ROUND(AVG(achieved_iops), 2)
        AS average_iops
FROM storage_performance_report
WHERE benchmark_status = 'COMPLETED'
GROUP BY
    device_name,
    device_type,
    operation
ORDER BY
    device_type,
    operation;

-- ============================================================
-- 24. VALIDATION: EXPECTED OBSERVATION COUNT
-- ============================================================

SELECT
    br.benchmark_id,
    br.requested_operations,
    COUNT(io.observation_id) AS actual_operations,
    CASE
        WHEN COUNT(io.observation_id) = br.requested_operations
        THEN 'VALID'
        ELSE 'INVALID'
    END AS observation_validation
FROM benchmark_runs br
LEFT JOIN io_observations io
    ON io.benchmark_id = br.benchmark_id
GROUP BY
    br.benchmark_id,
    br.requested_operations
ORDER BY br.benchmark_id;

-- ============================================================
-- 25. EVALUATION: POLICY VIOLATIONS
-- ============================================================

SELECT
    sd.device_name,
    br.operation,
    pe.decision,
    pe.violations,
    pe.evaluated_at
FROM policy_evaluations pe
JOIN benchmark_runs br
    ON br.benchmark_id = pe.benchmark_id
JOIN storage_devices sd
    ON sd.device_id = br.device_id
ORDER BY pe.evaluated_at DESC;

-- ============================================================
-- 26. ANALYSIS: SEQUENTIAL VERSUS RANDOM I/O
-- ============================================================

SELECT
    sd.device_name,
    sd.device_type,

    ROUND(
        AVG(res.throughput_mbps)
        FILTER (
            WHERE br.operation IN (
                'SEQUENTIAL_READ',
                'SEQUENTIAL_WRITE'
            )
        ),
        2
    ) AS sequential_throughput_mbps,

    ROUND(
        AVG(res.achieved_iops)
        FILTER (
            WHERE br.operation IN (
                'RANDOM_READ',
                'RANDOM_WRITE'
            )
        ),
        2
    ) AS random_iops,

    ROUND(
        AVG(res.average_latency_ms)
        FILTER (
            WHERE br.operation IN (
                'RANDOM_READ',
                'RANDOM_WRITE'
            )
        ),
        4
    ) AS random_average_latency_ms

FROM benchmark_runs br
JOIN storage_devices sd
    ON sd.device_id = br.device_id
JOIN benchmark_results res
    ON res.benchmark_id = br.benchmark_id

GROUP BY
    sd.device_name,
    sd.device_type;

-- ============================================================
-- 27. CTE: RANK DEVICES BY RANDOM READ LATENCY
-- ============================================================

WITH random_read_metrics AS (
    SELECT
        sd.device_name,
        sd.device_type,
        AVG(res.average_latency_ms) AS average_latency,
        AVG(res.achieved_iops) AS average_iops
    FROM benchmark_runs br
    JOIN storage_devices sd
        ON sd.device_id = br.device_id
    JOIN benchmark_results res
        ON res.benchmark_id = br.benchmark_id
    WHERE br.operation = 'RANDOM_READ'
    GROUP BY sd.device_name, sd.device_type
),
ranked_devices AS (
    SELECT
        *,
        DENSE_RANK() OVER (
            ORDER BY average_latency ASC
        ) AS latency_rank
    FROM random_read_metrics
)
SELECT
    device_name,
    device_type,
    ROUND(average_latency, 4) AS average_latency_ms,
    ROUND(average_iops, 2) AS average_iops,
    latency_rank
FROM ranked_devices
ORDER BY latency_rank;

-- ============================================================
-- 28. WORKFLOW: BENCHMARK ELIGIBILITY
-- ============================================================

SELECT
    br.benchmark_id,
    sd.device_name,
    br.status,
    sd.current_status,
    CASE
        WHEN br.status <> 'CREATED'
            THEN 'BENCHMARK_NOT_NEW'
        WHEN sd.current_status <> 'ACTIVE'
            THEN 'DEVICE_NOT_ACTIVE'
        WHEN NOT pp.is_active
            THEN 'POLICY_INACTIVE'
        ELSE 'ELIGIBLE'
    END AS eligibility
FROM benchmark_runs br
JOIN storage_devices sd
    ON sd.device_id = br.device_id
LEFT JOIN performance_policies pp
    ON pp.policy_id = br.policy_id
ORDER BY br.benchmark_id;

-- ============================================================
-- 29. CTE: LATENCY DISTRIBUTION
-- ============================================================

WITH latency_groups AS (
    SELECT
        br.benchmark_id,
        sd.device_name,
        br.operation,
        CASE
            WHEN io.latency_ms < 1 THEN 'Below 1 ms'
            WHEN io.latency_ms < 5 THEN '1-5 ms'
            WHEN io.latency_ms < 10 THEN '5-10 ms'
            WHEN io.latency_ms < 50 THEN '10-50 ms'
            ELSE '50 ms and above'
        END AS latency_bucket
    FROM io_observations io
    JOIN benchmark_runs br
        ON br.benchmark_id = io.benchmark_id
    JOIN storage_devices sd
        ON sd.device_id = br.device_id
)
SELECT
    device_name,
    operation,
    latency_bucket,
    COUNT(*) AS operation_count
FROM latency_groups
GROUP BY
    device_name,
    operation,
    latency_bucket
ORDER BY
    device_name,
    operation,
    latency_bucket;

-- ============================================================
-- 30. TRANSACTION: DEVICE MAINTENANCE
--
-- Failed devices cannot return directly to ACTIVE.
-- Maintenance changes are recorded in status history.
-- ============================================================

BEGIN;

UPDATE storage_devices
SET current_status = 'MAINTENANCE'
WHERE device_name = 'SATA SSD 1TB'
  AND current_status = 'ACTIVE';

COMMIT;

SELECT *
FROM device_status_history
ORDER BY changed_at DESC;

-- ============================================================
-- 31. PERFORMANCE INDEX USAGE DESIGN
--
-- The following indexes support:
-- - Recent device benchmarks
-- - Benchmark status filtering
-- - Observation retrieval by benchmark
-- - Latency sorting
-- - Policy decision reporting
--
-- For very large telemetry tables, time partitioning,
-- retention policies, and archival storage should be
-- evaluated according to actual workload characteristics.
-- ============================================================

ANALYZE storage_devices;
ANALYZE benchmark_runs;
ANALYZE io_observations;
ANALYZE benchmark_results;
ANALYZE policy_evaluations;

-- ============================================================
-- END OF STORAGE PERFORMANCE DATABASE
-- ============================================================
