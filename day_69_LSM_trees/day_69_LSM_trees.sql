/*
    LSM Trees: PostgreSQL relational model and operational simulation

    Demonstrates:
    - LSM engine configuration
    - Memtables
    - Write-ahead log records
    - Immutable sorted runs
    - Storage levels
    - Tombstones
    - Sequence-based version resolution
    - Flush processing
    - Size-tiered compaction
    - Bloom filter metadata
    - Sparse index metadata
    - Range retrieval
    - Storage statistics
    - Integrity validation

    PostgreSQL 15+
*/

DROP SCHEMA IF EXISTS lsm_lab CASCADE;

CREATE SCHEMA lsm_lab;

SET search_path TO lsm_lab, public;

-- ------------------------------------------------------------
-- 1. Storage engine configuration
-- ------------------------------------------------------------

CREATE TABLE storage_engine (
    engine_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_name VARCHAR(100) NOT NULL UNIQUE,
    memtable_capacity INTEGER NOT NULL
        CHECK (memtable_capacity > 0),
    level_run_capacity INTEGER NOT NULL
        CHECK (level_run_capacity >= 2),
    sparse_index_interval INTEGER NOT NULL
        CHECK (sparse_index_interval > 0),
    engine_state VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (
            engine_state IN (
                'ACTIVE',
                'FLUSHING',
                'COMPACTING',
                'CLOSED'
            )
        ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 2. Storage levels
-- ------------------------------------------------------------

CREATE TABLE storage_level (
    level_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_id BIGINT NOT NULL
        REFERENCES storage_engine(engine_id)
        ON DELETE CASCADE,
    level_number INTEGER NOT NULL CHECK (level_number >= 0),
    maximum_runs INTEGER NOT NULL CHECK (maximum_runs >= 2),
    UNIQUE (engine_id, level_number)
);

-- ------------------------------------------------------------
-- 3. Write-ahead log
-- ------------------------------------------------------------

CREATE TABLE wal_record (
    wal_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_id BIGINT NOT NULL
        REFERENCES storage_engine(engine_id)
        ON DELETE CASCADE,
    sequence_number BIGINT NOT NULL CHECK (sequence_number > 0),
    record_key TEXT NOT NULL CHECK (length(record_key) > 0),
    record_value TEXT,
    operation VARCHAR(10) NOT NULL
        CHECK (operation IN ('PUT', 'DELETE')),
    committed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (engine_id, sequence_number),
    CHECK (
        (operation = 'PUT' AND record_value IS NOT NULL)
        OR
        (operation = 'DELETE' AND record_value IS NULL)
    )
);

CREATE INDEX idx_wal_engine_sequence
    ON wal_record(engine_id, sequence_number DESC);

CREATE INDEX idx_wal_key_sequence
    ON wal_record(engine_id, record_key, sequence_number DESC);

-- ------------------------------------------------------------
-- 4. Memtable
-- ------------------------------------------------------------

CREATE TABLE memtable_entry (
    entry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_id BIGINT NOT NULL
        REFERENCES storage_engine(engine_id)
        ON DELETE CASCADE,
    record_key TEXT NOT NULL,
    record_value TEXT,
    sequence_number BIGINT NOT NULL CHECK (sequence_number > 0),
    operation VARCHAR(10) NOT NULL
        CHECK (operation IN ('PUT', 'DELETE')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (engine_id, record_key),
    CHECK (
        (operation = 'PUT' AND record_value IS NOT NULL)
        OR
        (operation = 'DELETE' AND record_value IS NULL)
    )
);

CREATE INDEX idx_memtable_sequence
    ON memtable_entry(engine_id, sequence_number DESC);

-- ------------------------------------------------------------
-- 5. Immutable sorted runs
-- ------------------------------------------------------------

CREATE TABLE sstable (
    sstable_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_id BIGINT NOT NULL
        REFERENCES storage_engine(engine_id)
        ON DELETE CASCADE,
    level_id BIGINT NOT NULL
        REFERENCES storage_level(level_id),
    run_number INTEGER NOT NULL CHECK (run_number > 0),
    run_state VARCHAR(20) NOT NULL DEFAULT 'BUILDING'
        CHECK (
            run_state IN (
                'BUILDING',
                'ACTIVE',
                'COMPACTING',
                'RETIRED'
            )
        ),
    minimum_key TEXT,
    maximum_key TEXT,
    entry_count BIGINT NOT NULL DEFAULT 0
        CHECK (entry_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (engine_id, run_number),
    CHECK (
        minimum_key IS NULL
        OR maximum_key IS NULL
        OR minimum_key <= maximum_key
    )
);

CREATE INDEX idx_sstable_level_state
    ON sstable(engine_id, level_id, run_state);

CREATE INDEX idx_sstable_key_range
    ON sstable(engine_id, minimum_key, maximum_key);

-- ------------------------------------------------------------
-- 6. SSTable records
-- ------------------------------------------------------------

CREATE TABLE sstable_entry (
    sstable_entry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sstable_id BIGINT NOT NULL
        REFERENCES sstable(sstable_id)
        ON DELETE CASCADE,
    record_key TEXT NOT NULL,
    record_value TEXT,
    sequence_number BIGINT NOT NULL CHECK (sequence_number > 0),
    operation VARCHAR(10) NOT NULL
        CHECK (operation IN ('PUT', 'DELETE')),
    UNIQUE (sstable_id, record_key),
    CHECK (
        (operation = 'PUT' AND record_value IS NOT NULL)
        OR
        (operation = 'DELETE' AND record_value IS NULL)
    )
);

CREATE INDEX idx_sstable_entry_lookup
    ON sstable_entry(sstable_id, record_key);

CREATE INDEX idx_sstable_entry_sequence
    ON sstable_entry(sequence_number DESC);

-- ------------------------------------------------------------
-- 7. Bloom filter metadata
-- ------------------------------------------------------------

CREATE TABLE bloom_filter_metadata (
    bloom_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sstable_id BIGINT NOT NULL UNIQUE
        REFERENCES sstable(sstable_id)
        ON DELETE CASCADE,
    bit_count BIGINT NOT NULL CHECK (bit_count > 0),
    hash_count INTEGER NOT NULL CHECK (hash_count > 0),
    expected_false_positive_rate NUMERIC(8, 7) NOT NULL
        CHECK (
            expected_false_positive_rate > 0
            AND expected_false_positive_rate < 1
        ),
    actual_insertions BIGINT NOT NULL DEFAULT 0
        CHECK (actual_insertions >= 0)
);

-- ------------------------------------------------------------
-- 8. Sparse index metadata
-- ------------------------------------------------------------

CREATE TABLE sparse_index_entry (
    sparse_index_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sstable_id BIGINT NOT NULL
        REFERENCES sstable(sstable_id)
        ON DELETE CASCADE,
    indexed_key TEXT NOT NULL,
    entry_position BIGINT NOT NULL CHECK (entry_position >= 0),
    UNIQUE (sstable_id, indexed_key),
    UNIQUE (sstable_id, entry_position)
);

CREATE INDEX idx_sparse_index_key
    ON sparse_index_entry(sstable_id, indexed_key);

-- ------------------------------------------------------------
-- 9. Flush and compaction history
-- ------------------------------------------------------------

CREATE TABLE storage_operation (
    operation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    engine_id BIGINT NOT NULL
        REFERENCES storage_engine(engine_id)
        ON DELETE CASCADE,
    operation_type VARCHAR(20) NOT NULL
        CHECK (
            operation_type IN ('FLUSH', 'COMPACTION', 'RECOVERY')
        ),
    source_level INTEGER,
    target_level INTEGER,
    input_entries BIGINT NOT NULL DEFAULT 0,
    output_entries BIGINT NOT NULL DEFAULT 0,
    operation_status VARCHAR(20) NOT NULL DEFAULT 'STARTED'
        CHECK (
            operation_status IN (
                'STARTED',
                'COMPLETED',
                'FAILED'
            )
        ),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    CHECK (
        completed_at IS NULL
        OR completed_at >= started_at
    )
);

-- ------------------------------------------------------------
-- 10. Engine registration
-- ------------------------------------------------------------

INSERT INTO storage_engine (
    engine_name,
    memtable_capacity,
    level_run_capacity,
    sparse_index_interval
)
VALUES (
    'IoT_Telemetry_Engine',
    4,
    3,
    2
);

INSERT INTO storage_level (
    engine_id,
    level_number,
    maximum_runs
)
SELECT engine_id, level_number, 3
FROM storage_engine
CROSS JOIN generate_series(0, 4) AS level_number;

-- ------------------------------------------------------------
-- 11. Write function
-- WAL record is inserted before memtable mutation.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION write_record(
    p_engine_id BIGINT,
    p_key TEXT,
    p_value TEXT,
    p_operation VARCHAR DEFAULT 'PUT'
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_sequence BIGINT;
    v_capacity INTEGER;
    v_count INTEGER;
BEGIN
    IF p_key IS NULL OR length(trim(p_key)) = 0 THEN
        RAISE EXCEPTION 'Invalid record key';
    END IF;

    IF p_operation NOT IN ('PUT', 'DELETE') THEN
        RAISE EXCEPTION 'Unsupported operation';
    END IF;

    IF p_operation = 'PUT' AND p_value IS NULL THEN
        RAISE EXCEPTION 'PUT requires a value';
    END IF;

    IF p_operation = 'DELETE' AND p_value IS NOT NULL THEN
        RAISE EXCEPTION 'DELETE cannot contain a value';
    END IF;

    SELECT memtable_capacity
    INTO v_capacity
    FROM storage_engine
    WHERE engine_id = p_engine_id
      AND engine_state = 'ACTIVE'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Engine is unavailable';
    END IF;

    SELECT COALESCE(MAX(sequence_number), 0) + 1
    INTO v_sequence
    FROM wal_record
    WHERE engine_id = p_engine_id;

    INSERT INTO wal_record (
        engine_id,
        sequence_number,
        record_key,
        record_value,
        operation
    )
    VALUES (
        p_engine_id,
        v_sequence,
        p_key,
        p_value,
        p_operation
    );

    INSERT INTO memtable_entry (
        engine_id,
        record_key,
        record_value,
        sequence_number,
        operation
    )
    VALUES (
        p_engine_id,
        p_key,
        p_value,
        v_sequence,
        p_operation
    )
    ON CONFLICT (engine_id, record_key)
    DO UPDATE SET
        record_value = EXCLUDED.record_value,
        sequence_number = EXCLUDED.sequence_number,
        operation = EXCLUDED.operation,
        created_at = CURRENT_TIMESTAMP;

    SELECT COUNT(*)
    INTO v_count
    FROM memtable_entry
    WHERE engine_id = p_engine_id;

    IF v_count >= v_capacity THEN
        RAISE NOTICE
            'Memtable threshold reached for engine %',
            p_engine_id;
    END IF;

    RETURN v_sequence;
END;
$$;

-- ------------------------------------------------------------
-- 12. Flush function
-- Converts the current memtable into an immutable sorted run.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION flush_memtable(
    p_engine_id BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_level_id BIGINT;
    v_sstable_id BIGINT;
    v_run_number INTEGER;
    v_operation_id BIGINT;
    v_input_count BIGINT;
BEGIN
    SELECT level_id
    INTO v_level_id
    FROM storage_level
    WHERE engine_id = p_engine_id
      AND level_number = 0;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Level zero is missing';
    END IF;

    SELECT COUNT(*)
    INTO v_input_count
    FROM memtable_entry
    WHERE engine_id = p_engine_id;

    IF v_input_count = 0 THEN
        RETURN NULL;
    END IF;

    INSERT INTO storage_operation (
        engine_id,
        operation_type,
        source_level,
        target_level,
        input_entries
    )
    VALUES (
        p_engine_id,
        'FLUSH',
        NULL,
        0,
        v_input_count
    )
    RETURNING operation_id INTO v_operation_id;

    SELECT COALESCE(MAX(run_number), 0) + 1
    INTO v_run_number
    FROM sstable
    WHERE engine_id = p_engine_id;

    INSERT INTO sstable (
        engine_id,
        level_id,
        run_number,
        run_state,
        minimum_key,
        maximum_key,
        entry_count
    )
    SELECT
        p_engine_id,
        v_level_id,
        v_run_number,
        'ACTIVE',
        MIN(record_key),
        MAX(record_key),
        COUNT(*)
    FROM memtable_entry
    WHERE engine_id = p_engine_id
    RETURNING sstable_id INTO v_sstable_id;

    INSERT INTO sstable_entry (
        sstable_id,
        record_key,
        record_value,
        sequence_number,
        operation
    )
    SELECT
        v_sstable_id,
        record_key,
        record_value,
        sequence_number,
        operation
    FROM memtable_entry
    WHERE engine_id = p_engine_id
    ORDER BY record_key;

    INSERT INTO bloom_filter_metadata (
        sstable_id,
        bit_count,
        hash_count,
        expected_false_positive_rate,
        actual_insertions
    )
    VALUES (
        v_sstable_id,
        GREATEST(8, CEIL(v_input_count * 10)::BIGINT),
        7,
        0.01,
        v_input_count
    );

    INSERT INTO sparse_index_entry (
        sstable_id,
        indexed_key,
        entry_position
    )
    SELECT
        v_sstable_id,
        record_key,
        position - 1
    FROM (
        SELECT
            record_key,
            ROW_NUMBER() OVER (
                ORDER BY record_key
            ) AS position
        FROM memtable_entry
        WHERE engine_id = p_engine_id
    ) ordered_entries
    WHERE (position - 1) %
        (
            SELECT sparse_index_interval
            FROM storage_engine
            WHERE engine_id = p_engine_id
        ) = 0;

    DELETE FROM memtable_entry
    WHERE engine_id = p_engine_id;

    UPDATE storage_operation
    SET
        operation_status = 'COMPLETED',
        output_entries = v_input_count,
        completed_at = CURRENT_TIMESTAMP
    WHERE operation_id = v_operation_id;

    RETURN v_sstable_id;
END;
$$;

-- ------------------------------------------------------------
-- 13. Compaction function
-- Merges all active runs at a level.
-- The highest sequence number wins for each key.
-- Tombstones remain until safe deletion can be established.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION compact_level(
    p_engine_id BIGINT,
    p_level_number INTEGER
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_source_level BIGINT;
    v_target_level BIGINT;
    v_sstable_id BIGINT;
    v_operation_id BIGINT;
    v_run_number INTEGER;
    v_input_count BIGINT;
    v_output_count BIGINT;
BEGIN
    SELECT level_id
    INTO v_source_level
    FROM storage_level
    WHERE engine_id = p_engine_id
      AND level_number = p_level_number
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Source level does not exist';
    END IF;

    SELECT level_id
    INTO v_target_level
    FROM storage_level
    WHERE engine_id = p_engine_id
      AND level_number = p_level_number + 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Target level does not exist';
    END IF;

    SELECT COUNT(*)
    INTO v_input_count
    FROM sstable
    WHERE engine_id = p_engine_id
      AND level_id = v_source_level
      AND run_state = 'ACTIVE';

    IF v_input_count < 2 THEN
        RAISE EXCEPTION
            'At least two active runs are required';
    END IF;

    INSERT INTO storage_operation (
        engine_id,
        operation_type,
        source_level,
        target_level,
        input_entries
    )
    VALUES (
        p_engine_id,
        'COMPACTION',
        p_level_number,
        p_level_number + 1,
        (
            SELECT COUNT(*)
            FROM sstable_entry se
            JOIN sstable s
              ON s.sstable_id = se.sstable_id
            WHERE s.engine_id = p_engine_id
              AND s.level_id = v_source_level
              AND s.run_state = 'ACTIVE'
        )
    )
    RETURNING operation_id INTO v_operation_id;

    SELECT COALESCE(MAX(run_number), 0) + 1
    INTO v_run_number
    FROM sstable
    WHERE engine_id = p_engine_id;

    INSERT INTO sstable (
        engine_id,
        level_id,
        run_number,
        run_state,
        minimum_key,
        maximum_key,
        entry_count
    )
    SELECT
        p_engine_id,
        v_target_level,
        v_run_number,
        'ACTIVE',
        MIN(record_key),
        MAX(record_key),
        COUNT(DISTINCT record_key)
    FROM (
        SELECT DISTINCT ON (se.record_key)
            se.record_key,
            se.sequence_number
        FROM sstable_entry se
        JOIN sstable s
          ON s.sstable_id = se.sstable_id
        WHERE s.engine_id = p_engine_id
          AND s.level_id = v_source_level
          AND s.run_state = 'ACTIVE'
        ORDER BY
            se.record_key,
            se.sequence_number DESC
    ) latest_entries
    RETURNING sstable_id INTO v_sstable_id;

    INSERT INTO sstable_entry (
        sstable_id,
        record_key,
        record_value,
        sequence_number,
        operation
    )
    SELECT
        v_sstable_id,
        se.record_key,
        se.record_value,
        se.sequence_number,
        se.operation
    FROM sstable_entry se
    JOIN sstable s
      ON s.sstable_id = se.sstable_id
    WHERE s.engine_id = p_engine_id
      AND s.level_id = v_source_level
      AND s.run_state = 'ACTIVE'
    ORDER BY se.record_key, se.sequence_number DESC
    ON CONFLICT (sstable_id, record_key)
    DO NOTHING;

    -- Correct duplicate resolution is enforced explicitly below.
    DELETE FROM sstable_entry old_entry
    USING (
        SELECT
            record_key,
            MAX(sequence_number) AS newest_sequence
        FROM sstable_entry
        WHERE sstable_id = v_sstable_id
        GROUP BY record_key
    ) newest
    WHERE old_entry.sstable_id = v_sstable_id
      AND old_entry.record_key = newest.record_key
      AND old_entry.sequence_number < newest.newest_sequence;

    UPDATE sstable
    SET entry_count = (
        SELECT COUNT(*)
        FROM sstable_entry
        WHERE sstable_id = v_sstable_id
    )
    WHERE sstable_id = v_sstable_id;

    SELECT entry_count
    INTO v_output_count
    FROM sstable
    WHERE sstable_id = v_sstable_id;

    INSERT INTO bloom_filter_metadata (
        sstable_id,
        bit_count,
        hash_count,
        expected_false_positive_rate,
        actual_insertions
    )
    VALUES (
        v_sstable_id,
        GREATEST(8, CEIL(v_output_count * 10)::BIGINT),
        7,
        0.01,
        v_output_count
    );

    INSERT INTO sparse_index_entry (
        sstable_id,
        indexed_key,
        entry_position
    )
    SELECT
        v_sstable_id,
        record_key,
        position - 1
    FROM (
        SELECT
            record_key,
            ROW_NUMBER() OVER (
                ORDER BY record_key
            ) AS position
        FROM sstable_entry
        WHERE sstable_id = v_sstable_id
    ) ordered_entries
    WHERE (position - 1) %
        (
            SELECT sparse_index_interval
            FROM storage_engine
            WHERE engine_id = p_engine_id
        ) = 0;

    UPDATE sstable
    SET run_state = 'RETIRED'
    WHERE engine_id = p_engine_id
      AND level_id = v_source_level
      AND run_state = 'ACTIVE';

    UPDATE storage_operation
    SET
        operation_status = 'COMPLETED',
        output_entries = v_output_count,
        completed_at = CURRENT_TIMESTAMP
    WHERE operation_id = v_operation_id;

    RETURN v_sstable_id;
END;
$$;

-- ------------------------------------------------------------
-- 14. Point lookup
-- Sequence numbers resolve stale copies across levels.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION get_record(
    p_engine_id BIGINT,
    p_key TEXT
)
RETURNS TABLE (
    record_key TEXT,
    record_value TEXT,
    sequence_number BIGINT,
    operation VARCHAR
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        candidates.record_key,
        candidates.record_value,
        candidates.sequence_number,
        candidates.operation
    FROM (
        SELECT
            me.record_key,
            me.record_value,
            me.sequence_number,
            me.operation
        FROM memtable_entry me
        WHERE me.engine_id = p_engine_id
          AND me.record_key = p_key

        UNION ALL

        SELECT
            se.record_key,
            se.record_value,
            se.sequence_number,
            se.operation
        FROM sstable_entry se
        JOIN sstable s
          ON s.sstable_id = se.sstable_id
        WHERE s.engine_id = p_engine_id
          AND s.run_state = 'ACTIVE'
          AND se.record_key = p_key
    ) candidates
    ORDER BY candidates.sequence_number DESC
    LIMIT 1;
$$;

-- ------------------------------------------------------------
-- 15. Range query
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION scan_range(
    p_engine_id BIGINT,
    p_start_key TEXT,
    p_end_key TEXT
)
RETURNS TABLE (
    record_key TEXT,
    record_value TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF p_start_key > p_end_key THEN
        RAISE EXCEPTION 'Invalid range boundaries';
    END IF;

    RETURN QUERY
    WITH candidates AS (
        SELECT
            me.record_key,
            me.record_value,
            me.sequence_number,
            me.operation
        FROM memtable_entry me
        WHERE me.engine_id = p_engine_id
          AND me.record_key BETWEEN p_start_key AND p_end_key

        UNION ALL

        SELECT
            se.record_key,
            se.record_value,
            se.sequence_number,
            se.operation
        FROM sstable_entry se
        JOIN sstable s
          ON s.sstable_id = se.sstable_id
        WHERE s.engine_id = p_engine_id
          AND s.run_state = 'ACTIVE'
          AND se.record_key BETWEEN p_start_key AND p_end_key
    ),
    latest AS (
        SELECT DISTINCT ON (record_key)
            record_key,
            record_value,
            sequence_number,
            operation
        FROM candidates
        ORDER BY record_key, sequence_number DESC
    )
    SELECT
        latest.record_key,
        latest.record_value
    FROM latest
    WHERE latest.operation = 'PUT'
    ORDER BY latest.record_key;
END;
$$;

-- ------------------------------------------------------------
-- 16. Integrity validation view
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW storage_run_report AS
SELECT
    s.engine_id,
    s.sstable_id,
    sl.level_number,
    s.run_number,
    s.run_state,
    s.entry_count,
    COUNT(se.sstable_entry_id) AS actual_entry_count,
    s.minimum_key,
    s.maximum_key,
    COUNT(DISTINCT se.record_key) AS distinct_keys
FROM sstable s
JOIN storage_level sl
  ON sl.level_id = s.level_id
LEFT JOIN sstable_entry se
  ON se.sstable_id = s.sstable_id
GROUP BY
    s.engine_id,
    s.sstable_id,
    sl.level_number,
    s.run_number,
    s.run_state,
    s.entry_count,
    s.minimum_key,
    s.maximum_key;

-- ------------------------------------------------------------
-- 17. Operational metrics
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW engine_storage_metrics AS
SELECT
    e.engine_id,
    e.engine_name,
    e.engine_state,
    (
        SELECT COUNT(*)
        FROM memtable_entry m
        WHERE m.engine_id = e.engine_id
    ) AS memtable_entries,
    (
        SELECT COUNT(*)
        FROM sstable s
        WHERE s.engine_id = e.engine_id
          AND s.run_state = 'ACTIVE'
    ) AS active_runs,
    (
        SELECT COALESCE(SUM(s.entry_count), 0)
        FROM sstable s
        WHERE s.engine_id = e.engine_id
          AND s.run_state = 'ACTIVE'
    ) AS physical_entries,
    (
        SELECT COUNT(*)
        FROM wal_record w
        WHERE w.engine_id = e.engine_id
    ) AS wal_records
FROM storage_engine e;

-- ------------------------------------------------------------
-- 18. Demonstration records
-- ------------------------------------------------------------

DO $$
DECLARE
    v_engine BIGINT;
BEGIN
    SELECT engine_id
    INTO v_engine
    FROM storage_engine
    WHERE engine_name = 'IoT_Telemetry_Engine';

    PERFORM write_record(
        v_engine,
        'sensor:001',
        'temperature=25.4',
        'PUT'
    );

    PERFORM write_record(
        v_engine,
        'sensor:002',
        'temperature=26.1',
        'PUT'
    );

    PERFORM write_record(
        v_engine,
        'sensor:003',
        'temperature=24.8',
        'PUT'
    );

    PERFORM write_record(
        v_engine,
        'sensor:004',
        'temperature=23.9',
        'PUT'
    );

    PERFORM flush_memtable(v_engine);

    PERFORM write_record(
        v_engine,
        'sensor:002',
        'temperature=27.2',
        'PUT'
    );

    PERFORM write_record(
        v_engine,
        'sensor:003',
        NULL,
        'DELETE'
    );

    PERFORM write_record(
        v_engine,
        'sensor:005',
        'temperature=22.8',
        'PUT'
    );

    PERFORM flush_memtable(v_engine);
END;
$$;

-- ------------------------------------------------------------
-- 19. Transactional compaction
-- ------------------------------------------------------------

BEGIN;

SELECT compact_level(
    (
        SELECT engine_id
        FROM storage_engine
        WHERE engine_name = 'IoT_Telemetry_Engine'
    ),
    0
);

COMMIT;

-- ------------------------------------------------------------
-- 20. Point lookup demonstration
-- ------------------------------------------------------------

SELECT *
FROM get_record(
    (
        SELECT engine_id
        FROM storage_engine
        WHERE engine_name = 'IoT_Telemetry_Engine'
    ),
    'sensor:002'
);

-- ------------------------------------------------------------
-- 21. Tombstone validation
-- ------------------------------------------------------------

SELECT *
FROM get_record(
    (
        SELECT engine_id
        FROM storage_engine
        WHERE engine_name = 'IoT_Telemetry_Engine'
    ),
    'sensor:003'
);

-- ------------------------------------------------------------
-- 22. Range scan
-- ------------------------------------------------------------

SELECT *
FROM scan_range(
    (
        SELECT engine_id
        FROM storage_engine
        WHERE engine_name = 'IoT_Telemetry_Engine'
    ),
    'sensor:001',
    'sensor:005'
);

-- ------------------------------------------------------------
-- 23. Version history
-- ------------------------------------------------------------

SELECT
    record_key,
    sequence_number,
    operation,
    record_value,
    committed_at
FROM wal_record
WHERE engine_id = (
    SELECT engine_id
    FROM storage_engine
    WHERE engine_name = 'IoT_Telemetry_Engine'
)
ORDER BY record_key, sequence_number;

-- ------------------------------------------------------------
-- 24. Storage-level report
-- ------------------------------------------------------------

SELECT *
FROM storage_run_report
ORDER BY level_number, run_number;

-- ------------------------------------------------------------
-- 25. Engine performance metrics
-- ------------------------------------------------------------

SELECT *
FROM engine_storage_metrics;

-- ------------------------------------------------------------
-- 26. Validation queries
-- ------------------------------------------------------------

-- Detect SSTable entry-count inconsistencies.
SELECT *
FROM storage_run_report
WHERE entry_count <> actual_entry_count;

-- Detect invalid sequence ordering in the WAL.
SELECT *
FROM (
    SELECT
        engine_id,
        sequence_number,
        LAG(sequence_number) OVER (
            PARTITION BY engine_id
            ORDER BY sequence_number
        ) AS previous_sequence
    FROM wal_record
) ordered_records
WHERE previous_sequence >= sequence_number;

-- Detect duplicate active key versions inside one run.
SELECT
    sstable_id,
    record_key,
    COUNT(*) AS duplicate_count
FROM sstable_entry
GROUP BY sstable_id, record_key
HAVING COUNT(*) > 1;

-- Detect invalid SSTable key boundaries.
SELECT *
FROM storage_run_report
WHERE
    (
        minimum_key IS NOT NULL
        AND minimum_key > maximum_key
    );

-- ------------------------------------------------------------
-- 27. Aggregated compaction reporting
-- ------------------------------------------------------------

SELECT
    engine_id,
    operation_type,
    operation_status,
    COUNT(*) AS operation_count,
    SUM(input_entries) AS total_input_entries,
    SUM(output_entries) AS total_output_entries,
    SUM(input_entries) -
        SUM(output_entries) AS entries_eliminated
FROM storage_operation
GROUP BY
    engine_id,
    operation_type,
    operation_status
ORDER BY operation_type, operation_status;

-- ------------------------------------------------------------
-- 28. Eligibility determination for compaction
-- ------------------------------------------------------------

SELECT
    e.engine_name,
    sl.level_number,
    COUNT(s.sstable_id) AS active_run_count,
    sl.maximum_runs,
    COUNT(s.sstable_id) >= sl.maximum_runs
        AS compaction_eligible
FROM storage_level sl
JOIN storage_engine e
  ON e.engine_id = sl.engine_id
LEFT JOIN sstable s
  ON s.level_id = sl.level_id
 AND s.run_state = 'ACTIVE'
GROUP BY
    e.engine_name,
    sl.level_number,
    sl.maximum_runs
ORDER BY sl.level_number;

-- ------------------------------------------------------------
-- 29. Transaction rollback demonstration
-- Invalid writes must not leave partial records.
-- ------------------------------------------------------------

BEGIN;

DO $$
DECLARE
    v_engine BIGINT;
BEGIN
    SELECT engine_id
    INTO v_engine
    FROM storage_engine
    WHERE engine_name = 'IoT_Telemetry_Engine';

    BEGIN
        PERFORM write_record(
            v_engine,
            '',
            'invalid',
            'PUT'
        );
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Expected validation failure: %',
                SQLERRM;
    END;
END;
$$;

ROLLBACK;

-- ------------------------------------------------------------
-- 30. Final engine state
-- ------------------------------------------------------------

SELECT
    engine_name,
    engine_state,
    memtable_capacity,
    level_run_capacity,
    sparse_index_interval
FROM storage_engine;
