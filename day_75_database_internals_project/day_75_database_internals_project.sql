-- ============================================================
-- DATABASE INTERNALS PROJECT
-- PostgreSQL relational model for storage and query behavior
--
-- PostgreSQL 15+
--
-- Models:
--   Catalog and physical storage metadata
--   Heap pages and buffer observations
--   Transactions and write-ahead log metadata
--   Relational tables and indexes
--   Query plans and execution statistics
--   MVCC-oriented tuple versions
--   Database workload monitoring
--
-- PostgreSQL itself supplies the actual storage engine,
-- WAL implementation, buffer manager, and query executor.
-- This schema records observations and models selected concepts.
-- ============================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS dbinternals;

SET search_path TO dbinternals, public;

-- ============================================================
-- 1. DATABASE CATALOG AND RELATIONAL OBJECTS
-- ============================================================

CREATE TABLE IF NOT EXISTS database_instances (
    database_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    database_name TEXT NOT NULL UNIQUE,
    engine_version TEXT NOT NULL,
    page_size_bytes INTEGER NOT NULL DEFAULT 8192,
    block_size_bytes INTEGER NOT NULL DEFAULT 8192,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_page_size
        CHECK (page_size_bytes >= 512),

    CONSTRAINT valid_block_size
        CHECK (block_size_bytes >= 512)
);

CREATE TABLE IF NOT EXISTS database_tables (
    table_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    database_id BIGINT NOT NULL
        REFERENCES database_instances(database_id),
    schema_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    storage_type TEXT NOT NULL DEFAULT 'HEAP',
    estimated_rows BIGINT NOT NULL DEFAULT 0,
    actual_rows BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_storage_type
        CHECK (storage_type IN ('HEAP', 'TEMPORARY', 'PARTITIONED')),

    CONSTRAINT valid_table_counts
        CHECK (
            estimated_rows >= 0
            AND actual_rows >= 0
        ),

    CONSTRAINT unique_catalog_table
        UNIQUE(database_id, schema_name, table_name)
);

CREATE TABLE IF NOT EXISTS database_columns (
    column_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_id BIGINT NOT NULL
        REFERENCES database_tables(table_id)
        ON DELETE CASCADE,
    column_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    ordinal_position INTEGER NOT NULL,
    is_nullable BOOLEAN NOT NULL DEFAULT TRUE,
    is_indexed BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT unique_column_name
        UNIQUE(table_id, column_name),

    CONSTRAINT unique_column_position
        UNIQUE(table_id, ordinal_position),

    CONSTRAINT valid_ordinal
        CHECK (ordinal_position > 0)
);

-- ============================================================
-- 2. PHYSICAL STORAGE AND PAGE OBSERVATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS storage_pages (
    page_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_id BIGINT NOT NULL
        REFERENCES database_tables(table_id)
        ON DELETE CASCADE,
    page_number BIGINT NOT NULL,
    page_type TEXT NOT NULL DEFAULT 'HEAP',
    page_size_bytes INTEGER NOT NULL DEFAULT 8192,
    used_bytes INTEGER NOT NULL DEFAULT 0,
    free_bytes INTEGER NOT NULL DEFAULT 8192,
    tuple_count INTEGER NOT NULL DEFAULT 0,
    page_lsn BIGINT NOT NULL DEFAULT 0,
    checksum_value TEXT,
    is_dirty BOOLEAN NOT NULL DEFAULT FALSE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_page_type
        CHECK (page_type IN ('HEAP', 'INDEX', 'TOAST')),

    CONSTRAINT valid_page_number
        CHECK (page_number >= 0),

    CONSTRAINT valid_page_capacity
        CHECK (
            used_bytes >= 0
            AND free_bytes >= 0
            AND used_bytes + free_bytes <= page_size_bytes
        ),

    CONSTRAINT valid_tuple_count
        CHECK (tuple_count >= 0),

    CONSTRAINT unique_table_page
        UNIQUE(table_id, page_number)
);

CREATE INDEX IF NOT EXISTS idx_storage_pages_table
    ON storage_pages(table_id, page_number);

CREATE INDEX IF NOT EXISTS idx_storage_pages_dirty
    ON storage_pages(is_dirty, observed_at)
    WHERE is_dirty = TRUE;

CREATE TABLE IF NOT EXISTS buffer_pool_observations (
    observation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    database_id BIGINT NOT NULL
        REFERENCES database_instances(database_id),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    pool_capacity INTEGER NOT NULL,
    pages_resident INTEGER NOT NULL,
    cache_hits BIGINT NOT NULL DEFAULT 0,
    cache_misses BIGINT NOT NULL DEFAULT 0,
    evictions BIGINT NOT NULL DEFAULT 0,
    dirty_pages INTEGER NOT NULL DEFAULT 0,
    flush_operations BIGINT NOT NULL DEFAULT 0,

    CONSTRAINT valid_pool_capacity
        CHECK (
            pool_capacity > 0
            AND pages_resident >= 0
            AND pages_resident <= pool_capacity
        ),

    CONSTRAINT valid_buffer_counters
        CHECK (
            cache_hits >= 0
            AND cache_misses >= 0
            AND evictions >= 0
            AND dirty_pages >= 0
            AND flush_operations >= 0
        )
);

CREATE INDEX IF NOT EXISTS idx_buffer_observations_time
    ON buffer_pool_observations(database_id, observed_at DESC);

-- ============================================================
-- 3. TRANSACTION AND WAL OBSERVABILITY
-- ============================================================

CREATE TABLE IF NOT EXISTS database_transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    database_id BIGINT NOT NULL
        REFERENCES database_instances(database_id),
    application_name TEXT NOT NULL,
    transaction_status TEXT NOT NULL DEFAULT 'ACTIVE',
    isolation_level TEXT NOT NULL DEFAULT 'READ COMMITTED',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    commit_lsn BIGINT,
    abort_reason TEXT,

    CONSTRAINT valid_transaction_status
        CHECK (
            transaction_status IN (
                'ACTIVE',
                'COMMITTED',
                'ABORTED'
            )
        ),

    CONSTRAINT valid_isolation_level
        CHECK (
            isolation_level IN (
                'READ UNCOMMITTED',
                'READ COMMITTED',
                'REPEATABLE READ',
                'SERIALIZABLE'
            )
        ),

    CONSTRAINT valid_completion_time
        CHECK (
            completed_at IS NULL
            OR completed_at >= started_at
        ),

    CONSTRAINT valid_terminal_state
        CHECK (
            (
                transaction_status = 'ACTIVE'
                AND completed_at IS NULL
            )
            OR
            (
                transaction_status IN ('COMMITTED', 'ABORTED')
                AND completed_at IS NOT NULL
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_transactions_active
    ON database_transactions(database_id, started_at)
    WHERE transaction_status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS wal_observations (
    wal_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    database_id BIGINT NOT NULL
        REFERENCES database_instances(database_id),
    transaction_id BIGINT
        REFERENCES database_transactions(transaction_id),
    lsn TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    relation_name TEXT,
    record_size_bytes INTEGER NOT NULL DEFAULT 0,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    durable BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT valid_wal_operation
        CHECK (
            operation_type IN (
                'INSERT',
                'UPDATE',
                'DELETE',
                'COMMIT',
                'ABORT',
                'CHECKPOINT',
                'FULL_PAGE_IMAGE'
            )
        ),

    CONSTRAINT valid_wal_size
        CHECK (record_size_bytes >= 0),

    CONSTRAINT unique_database_lsn
        UNIQUE(database_id, lsn)
);

CREATE INDEX IF NOT EXISTS idx_wal_transaction
    ON wal_observations(transaction_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_wal_durable
    ON wal_observations(database_id, durable, observed_at);

-- ============================================================
-- 4. MVCC TUPLE VERSION OBSERVATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS tuple_versions (
    tuple_version_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_id BIGINT NOT NULL
        REFERENCES database_tables(table_id),
    logical_row_id BIGINT NOT NULL,
    xmin_transaction BIGINT
        REFERENCES database_transactions(transaction_id),
    xmax_transaction BIGINT
        REFERENCES database_transactions(transaction_id),
    version_number INTEGER NOT NULL,
    tuple_data JSONB NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_version_number
        CHECK (version_number > 0),

    CONSTRAINT valid_row_id
        CHECK (logical_row_id > 0)
);

CREATE INDEX IF NOT EXISTS idx_tuple_versions_row
    ON tuple_versions(table_id, logical_row_id, version_number DESC);

CREATE INDEX IF NOT EXISTS idx_tuple_versions_xmin
    ON tuple_versions(xmin_transaction);

CREATE INDEX IF NOT EXISTS idx_tuple_versions_xmax
    ON tuple_versions(xmax_transaction)
    WHERE xmax_transaction IS NOT NULL;

-- ============================================================
-- 5. INDEX CATALOG AND INDEX STATISTICS
-- ============================================================

CREATE TABLE IF NOT EXISTS database_indexes (
    index_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_id BIGINT NOT NULL
        REFERENCES database_tables(table_id)
        ON DELETE CASCADE,
    index_name TEXT NOT NULL,
    index_type TEXT NOT NULL,
    indexed_column TEXT NOT NULL,
    is_unique BOOLEAN NOT NULL DEFAULT FALSE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    estimated_entries BIGINT NOT NULL DEFAULT 0,
    tree_height INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_index_type
        CHECK (
            index_type IN (
                'BTREE',
                'HASH',
                'GIN',
                'GIST',
                'BRIN'
            )
        ),

    CONSTRAINT valid_index_statistics
        CHECK (
            estimated_entries >= 0
            AND tree_height >= 1
        ),

    CONSTRAINT unique_table_index
        UNIQUE(table_id, index_name)
);

CREATE INDEX IF NOT EXISTS idx_database_indexes_table
    ON database_indexes(table_id, index_type);

CREATE TABLE IF NOT EXISTS index_observations (
    index_observation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    index_id BIGINT NOT NULL
        REFERENCES database_indexes(index_id)
        ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    index_scans BIGINT NOT NULL DEFAULT 0,
    tuples_read BIGINT NOT NULL DEFAULT 0,
    tuples_returned BIGINT NOT NULL DEFAULT 0,
    index_size_bytes BIGINT NOT NULL DEFAULT 0,
    fragmentation_ratio NUMERIC(6,5),

    CONSTRAINT valid_index_counters
        CHECK (
            index_scans >= 0
            AND tuples_read >= 0
            AND tuples_returned >= 0
            AND index_size_bytes >= 0
        ),

    CONSTRAINT valid_fragmentation
        CHECK (
            fragmentation_ratio IS NULL
            OR fragmentation_ratio BETWEEN 0 AND 1
        )
);

-- ============================================================
-- 6. QUERY EXECUTION AND QUERY PLANS
-- ============================================================

CREATE TABLE IF NOT EXISTS query_executions (
    execution_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    database_id BIGINT NOT NULL
        REFERENCES database_instances(database_id),
    transaction_id BIGINT
        REFERENCES database_transactions(transaction_id),
    query_fingerprint TEXT NOT NULL,
    query_text TEXT NOT NULL,
    execution_status TEXT NOT NULL DEFAULT 'COMPLETED',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    execution_time_ms NUMERIC(14,3),
    rows_returned BIGINT NOT NULL DEFAULT 0,
    shared_blocks_hit BIGINT NOT NULL DEFAULT 0,
    shared_blocks_read BIGINT NOT NULL DEFAULT 0,
    temporary_blocks_written BIGINT NOT NULL DEFAULT 0,
    error_message TEXT,

    CONSTRAINT valid_execution_status
        CHECK (
            execution_status IN (
                'RUNNING',
                'COMPLETED',
                'FAILED',
                'CANCELLED'
            )
        ),

    CONSTRAINT valid_execution_metrics
        CHECK (
            rows_returned >= 0
            AND shared_blocks_hit >= 0
            AND shared_blocks_read >= 0
            AND temporary_blocks_written >= 0
            AND (
                execution_time_ms IS NULL
                OR execution_time_ms >= 0
            )
        ),

    CONSTRAINT valid_execution_times
        CHECK (
            completed_at IS NULL
            OR completed_at >= started_at
        )
);

CREATE INDEX IF NOT EXISTS idx_query_execution_time
    ON query_executions(database_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_query_fingerprint
    ON query_executions(query_fingerprint);

CREATE TABLE IF NOT EXISTS query_plan_nodes (
    plan_node_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    execution_id BIGINT NOT NULL
        REFERENCES query_executions(execution_id)
        ON DELETE CASCADE,
    parent_node_id BIGINT
        REFERENCES query_plan_nodes(plan_node_id),
    node_type TEXT NOT NULL,
    relation_name TEXT,
    index_name TEXT,
    estimated_rows NUMERIC(16,3),
    actual_rows NUMERIC(16,3),
    startup_cost NUMERIC(16,4),
    total_cost NUMERIC(16,4),
    actual_time_ms NUMERIC(16,4),
    loops BIGINT NOT NULL DEFAULT 1,

    CONSTRAINT valid_plan_node_type
        CHECK (
            node_type IN (
                'SEQ_SCAN',
                'INDEX_SCAN',
                'INDEX_ONLY_SCAN',
                'BITMAP_HEAP_SCAN',
                'NESTED_LOOP',
                'HASH_JOIN',
                'MERGE_JOIN',
                'HASH_AGGREGATE',
                'SORT',
                'LIMIT',
                'MATERIALIZE'
            )
        ),

    CONSTRAINT valid_plan_metrics
        CHECK (
            loops >= 0
            AND (estimated_rows IS NULL OR estimated_rows >= 0)
            AND (actual_rows IS NULL OR actual_rows >= 0)
            AND (startup_cost IS NULL OR startup_cost >= 0)
            AND (total_cost IS NULL OR total_cost >= 0)
        )
);

CREATE INDEX IF NOT EXISTS idx_plan_execution
    ON query_plan_nodes(execution_id);

CREATE INDEX IF NOT EXISTS idx_plan_node_type
    ON query_plan_nodes(node_type);

-- ============================================================
-- 7. EXECUTION STATISTICS AND COST ANALYSIS
-- ============================================================

CREATE TABLE IF NOT EXISTS table_statistics (
    statistics_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_id BIGINT NOT NULL
        REFERENCES database_tables(table_id)
        ON DELETE CASCADE,
    column_name TEXT NOT NULL,
    sampled_rows BIGINT NOT NULL,
    estimated_distinct_values BIGINT NOT NULL,
    null_fraction NUMERIC(6,5) NOT NULL DEFAULT 0,
    correlation NUMERIC(7,5),
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_table_column_statistics
        UNIQUE(table_id, column_name),

    CONSTRAINT valid_column_statistics
        CHECK (
            sampled_rows >= 0
            AND estimated_distinct_values >= 0
            AND null_fraction BETWEEN 0 AND 1
            AND (
                correlation IS NULL
                OR correlation BETWEEN -1 AND 1
            )
        )
);

CREATE TABLE IF NOT EXISTS query_cost_estimates (
    cost_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    execution_id BIGINT
        REFERENCES query_executions(execution_id),
    access_method TEXT NOT NULL,
    estimated_page_reads NUMERIC(16,4) NOT NULL,
    estimated_cpu_cost NUMERIC(16,4) NOT NULL,
    estimated_total_cost NUMERIC(16,4) NOT NULL,
    chosen_plan BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_access_method
        CHECK (
            access_method IN (
                'TABLE_SCAN',
                'INDEX_SCAN',
                'INDEX_ONLY_SCAN',
                'BITMAP_SCAN'
            )
        ),

    CONSTRAINT valid_cost_values
        CHECK (
            estimated_page_reads >= 0
            AND estimated_cpu_cost >= 0
            AND estimated_total_cost >= 0
        )
);

-- ============================================================
-- 8. SAMPLE DATABASE AND CATALOG DATA
-- ============================================================

INSERT INTO database_instances (
    database_name,
    engine_version
)
VALUES (
    'enterprise_hr',
    'PostgreSQL 17'
)
ON CONFLICT (database_name) DO NOTHING;

INSERT INTO database_tables (
    database_id,
    schema_name,
    table_name,
    estimated_rows,
    actual_rows
)
SELECT
    database_id,
    'public',
    'employees',
    10000,
    4
FROM database_instances
WHERE database_name = 'enterprise_hr'
ON CONFLICT (database_id, schema_name, table_name)
DO NOTHING;

INSERT INTO database_tables (
    database_id,
    schema_name,
    table_name,
    estimated_rows,
    actual_rows
)
SELECT
    database_id,
    'public',
    'departments',
    100,
    3
FROM database_instances
WHERE database_name = 'enterprise_hr'
ON CONFLICT (database_id, schema_name, table_name)
DO NOTHING;

INSERT INTO database_columns (
    table_id,
    column_name,
    data_type,
    ordinal_position,
    is_nullable,
    is_indexed
)
SELECT
    t.table_id,
    c.column_name,
    c.data_type,
    c.ordinal_position,
    c.is_nullable,
    c.is_indexed
FROM database_tables t
CROSS JOIN (
    VALUES
        ('employee_id', 'INTEGER', 1, FALSE, TRUE),
        ('employee_name', 'TEXT', 2, FALSE, FALSE),
        ('department_id', 'INTEGER', 3, FALSE, TRUE),
        ('salary', 'NUMERIC', 4, FALSE, FALSE)
) AS c(column_name, data_type, ordinal_position, is_nullable, is_indexed)
WHERE t.table_name = 'employees'
ON CONFLICT (table_id, column_name) DO NOTHING;

INSERT INTO database_columns (
    table_id,
    column_name,
    data_type,
    ordinal_position,
    is_nullable,
    is_indexed
)
SELECT
    t.table_id,
    c.column_name,
    c.data_type,
    c.ordinal_position,
    c.is_nullable,
    c.is_indexed
FROM database_tables t
CROSS JOIN (
    VALUES
        ('department_id', 'INTEGER', 1, FALSE, TRUE),
        ('department_name', 'TEXT', 2, FALSE, TRUE)
) AS c(column_name, data_type, ordinal_position, is_nullable, is_indexed)
WHERE t.table_name = 'departments'
ON CONFLICT (table_id, column_name) DO NOTHING;

-- ============================================================
-- 9. OPERATIONAL BUSINESS TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS departments (
    department_id INTEGER PRIMARY KEY,
    department_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id INTEGER PRIMARY KEY,
    employee_name TEXT NOT NULL,
    department_id INTEGER NOT NULL
        REFERENCES departments(department_id),
    salary NUMERIC(12,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_employee_salary
        CHECK (salary >= 0),

    CONSTRAINT valid_employee_name
        CHECK (length(trim(employee_name)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_employees_department
    ON employees(department_id);

CREATE INDEX IF NOT EXISTS idx_employees_salary
    ON employees(salary DESC);

CREATE INDEX IF NOT EXISTS idx_employees_name
    ON employees(employee_name);

INSERT INTO departments (
    department_id,
    department_name
)
VALUES
    (1, 'Engineering'),
    (2, 'Research'),
    (3, 'Operations')
ON CONFLICT (department_id) DO NOTHING;

INSERT INTO employees (
    employee_id,
    employee_name,
    department_id,
    salary
)
VALUES
    (101, 'Asha', 1, 90000),
    (102, 'Ravi', 1, 85000),
    (103, 'Meera', 2, 110000),
    (104, 'Kabir', 2, 95000)
ON CONFLICT (employee_id) DO NOTHING;

-- ============================================================
-- 10. CATALOG INDEX METADATA
-- ============================================================

INSERT INTO database_indexes (
    table_id,
    index_name,
    index_type,
    indexed_column,
    is_unique,
    is_primary,
    estimated_entries,
    tree_height
)
SELECT
    t.table_id,
    'employees_pkey',
    'BTREE',
    'employee_id',
    TRUE,
    TRUE,
    4,
    1
FROM database_tables t
WHERE t.table_name = 'employees'
ON CONFLICT (table_id, index_name) DO NOTHING;

INSERT INTO database_indexes (
    table_id,
    index_name,
    index_type,
    indexed_column,
    estimated_entries,
    tree_height
)
SELECT
    t.table_id,
    'idx_employees_department',
    'BTREE',
    'department_id',
    4,
    1
FROM database_tables t
WHERE t.table_name = 'employees'
ON CONFLICT (table_id, index_name) DO NOTHING;

-- ============================================================
-- 11. DATABASE OBSERVATION FUNCTIONS
-- ============================================================

CREATE OR REPLACE FUNCTION buffer_hit_ratio(
    p_hits BIGINT,
    p_misses BIGINT
)
RETURNS NUMERIC
LANGUAGE plpgsql
IMMUTABLE
STRICT
AS $$
BEGIN
    IF p_hits < 0 OR p_misses < 0 THEN
        RAISE EXCEPTION
            'Buffer counters cannot be negative';
    END IF;

    IF p_hits + p_misses = 0 THEN
        RETURN 0;
    END IF;

    RETURN ROUND(
        p_hits::NUMERIC /
        (p_hits + p_misses)::NUMERIC,
        5
    );
END;
$$;

CREATE OR REPLACE FUNCTION estimate_table_scan_cost(
    p_row_count BIGINT,
    p_rows_per_page INTEGER
)
RETURNS NUMERIC
LANGUAGE plpgsql
IMMUTABLE
STRICT
AS $$
BEGIN
    IF p_row_count < 0 OR p_rows_per_page <= 0 THEN
        RAISE EXCEPTION 'Invalid scan statistics';
    END IF;

    RETURN CEIL(
        p_row_count::NUMERIC / p_rows_per_page
    );
END;
$$;

CREATE OR REPLACE FUNCTION estimate_index_scan_cost(
    p_row_count BIGINT,
    p_distinct_values BIGINT
)
RETURNS NUMERIC
LANGUAGE plpgsql
IMMUTABLE
STRICT
AS $$
BEGIN
    IF p_row_count < 0 OR p_distinct_values < 0 THEN
        RAISE EXCEPTION 'Invalid index statistics';
    END IF;

    IF p_row_count = 0 OR p_distinct_values = 0 THEN
        RETURN 'Infinity'::NUMERIC;
    END IF;

    RETURN ROUND(
        LN(GREATEST(2, p_row_count)::NUMERIC) /
        LN(2::NUMERIC)
        + p_row_count::NUMERIC /
        p_distinct_values::NUMERIC,
        4
    );
END;
$$;

CREATE OR REPLACE FUNCTION choose_access_path(
    p_row_count BIGINT,
    p_distinct_values BIGINT,
    p_rows_per_page INTEGER
)
RETURNS TABLE (
    selected_access_path TEXT,
    table_scan_cost NUMERIC,
    index_scan_cost NUMERIC
)
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    table_scan_cost :=
        estimate_table_scan_cost(
            p_row_count,
            p_rows_per_page
        );

    index_scan_cost :=
        estimate_index_scan_cost(
            p_row_count,
            p_distinct_values
        );

    selected_access_path :=
        CASE
            WHEN index_scan_cost < table_scan_cost
                THEN 'INDEX_SCAN'
            ELSE 'TABLE_SCAN'
        END;

    RETURN NEXT;
END;
$$;

-- ============================================================
-- 12. TRANSACTION STATE TRANSITION ENFORCEMENT
-- ============================================================

CREATE OR REPLACE FUNCTION enforce_transaction_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.transaction_status <> 'ACTIVE'
       AND NEW.transaction_status <> OLD.transaction_status THEN
        RAISE EXCEPTION
            'Terminal transaction state cannot be changed';
    END IF;

    IF OLD.transaction_status = 'ACTIVE'
       AND NEW.transaction_status NOT IN (
           'ACTIVE',
           'COMMITTED',
           'ABORTED'
       ) THEN
        RAISE EXCEPTION
            'Invalid transaction transition';
    END IF;

    IF NEW.transaction_status IN ('COMMITTED', 'ABORTED')
       AND NEW.completed_at IS NULL THEN
        NEW.completed_at := CURRENT_TIMESTAMP;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_transaction_transition
    ON database_transactions;

CREATE TRIGGER trg_transaction_transition
BEFORE UPDATE ON database_transactions
FOR EACH ROW
EXECUTE FUNCTION enforce_transaction_transition();

-- ============================================================
-- 13. PAGE INTEGRITY ENFORCEMENT
-- ============================================================

CREATE OR REPLACE FUNCTION validate_page_accounting()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.used_bytes + NEW.free_bytes > NEW.page_size_bytes THEN
        RAISE EXCEPTION
            'Page accounting exceeds physical page capacity';
    END IF;

    IF NEW.page_type = 'HEAP' AND NEW.tuple_count = 0
       AND NEW.used_bytes > 0 THEN
        RAISE EXCEPTION
            'Empty heap page cannot report occupied tuple space';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validate_page_accounting
    ON storage_pages;

CREATE TRIGGER trg_validate_page_accounting
BEFORE INSERT OR UPDATE ON storage_pages
FOR EACH ROW
EXECUTE FUNCTION validate_page_accounting();

-- ============================================================
-- 14. WORKFLOW PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE complete_database_transaction(
    p_transaction_id BIGINT,
    p_commit BOOLEAN
)
LANGUAGE plpgsql
AS $$
DECLARE
    current_status TEXT;
BEGIN
    SELECT transaction_status
    INTO current_status
    FROM database_transactions
    WHERE transaction_id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Transaction % does not exist',
            p_transaction_id;
    END IF;

    IF current_status <> 'ACTIVE' THEN
        RAISE EXCEPTION
            'Transaction is already in a terminal state';
    END IF;

    IF p_commit THEN
        UPDATE database_transactions
        SET
            transaction_status = 'COMMITTED',
            completed_at = CURRENT_TIMESTAMP
        WHERE transaction_id = p_transaction_id;

        INSERT INTO wal_observations (
            database_id,
            transaction_id,
            lsn,
            operation_type,
            durable
        )
        SELECT
            database_id,
            transaction_id,
            'SIMULATED-' || transaction_id || '-COMMIT',
            'COMMIT',
            TRUE
        FROM database_transactions
        WHERE transaction_id = p_transaction_id;

    ELSE
        UPDATE database_transactions
        SET
            transaction_status = 'ABORTED',
            completed_at = CURRENT_TIMESTAMP,
            abort_reason = 'Explicit transaction rollback'
        WHERE transaction_id = p_transaction_id;

        INSERT INTO wal_observations (
            database_id,
            transaction_id,
            lsn,
            operation_type,
            durable
        )
        SELECT
            database_id,
            transaction_id,
            'SIMULATED-' || transaction_id || '-ABORT',
            'ABORT',
            TRUE
        FROM database_transactions
        WHERE transaction_id = p_transaction_id;
    END IF;
END;
$$;

-- ============================================================
-- 15. SAMPLE OBSERVABILITY RECORDS
-- ============================================================

INSERT INTO buffer_pool_observations (
    database_id,
    pool_capacity,
    pages_resident,
    cache_hits,
    cache_misses,
    evictions,
    dirty_pages,
    flush_operations
)
SELECT
    database_id,
    128,
    64,
    8500,
    1200,
    450,
    12,
    75
FROM database_instances
WHERE database_name = 'enterprise_hr';

INSERT INTO storage_pages (
    table_id,
    page_number,
    page_type,
    page_size_bytes,
    used_bytes,
    free_bytes,
    tuple_count,
    page_lsn,
    checksum_value,
    is_dirty
)
SELECT
    table_id,
    0,
    'HEAP',
    8192,
    3200,
    4992,
    4,
    1001,
    'sample-checksum-001',
    FALSE
FROM database_tables
WHERE table_name = 'employees'
ON CONFLICT (table_id, page_number) DO NOTHING;

INSERT INTO table_statistics (
    table_id,
    column_name,
    sampled_rows,
    estimated_distinct_values,
    null_fraction,
    correlation
)
SELECT
    table_id,
    'employee_id',
    10000,
    10000,
    0,
    0.98
FROM database_tables
WHERE table_name = 'employees'
ON CONFLICT (table_id, column_name)
DO UPDATE SET
    sampled_rows = EXCLUDED.sampled_rows,
    estimated_distinct_values =
        EXCLUDED.estimated_distinct_values,
    analyzed_at = CURRENT_TIMESTAMP;

INSERT INTO database_transactions (
    database_id,
    application_name,
    transaction_status,
    isolation_level,
    completed_at
)
SELECT
    database_id,
    'employee-import',
    'COMMITTED',
    'READ COMMITTED',
    CURRENT_TIMESTAMP
FROM database_instances
WHERE database_name = 'enterprise_hr';

INSERT INTO database_transactions (
    database_id,
    application_name,
    transaction_status,
    isolation_level,
    completed_at,
    abort_reason
)
SELECT
    database_id,
    'failed-import',
    'ABORTED',
    'SERIALIZABLE',
    CURRENT_TIMESTAMP,
    'Simulated constraint violation'
FROM database_instances
WHERE database_name = 'enterprise_hr';

-- ============================================================
-- 16. QUERY EXECUTION SAMPLE
-- ============================================================

INSERT INTO query_executions (
    database_id,
    query_fingerprint,
    query_text,
    execution_status,
    completed_at,
    execution_time_ms,
    rows_returned,
    shared_blocks_hit,
    shared_blocks_read
)
SELECT
    database_id,
    'employee-department-summary',
    'SELECT department_id, AVG(salary) FROM employees GROUP BY department_id',
    'COMPLETED',
    CURRENT_TIMESTAMP,
    2.450,
    2,
    35,
    3
FROM database_instances
WHERE database_name = 'enterprise_hr';

INSERT INTO query_executions (
    database_id,
    query_fingerprint,
    query_text,
    execution_status,
    completed_at,
    execution_time_ms,
    error_message
)
SELECT
    database_id,
    'invalid-column-query',
    'SELECT unknown_column FROM employees',
    'FAILED',
    CURRENT_TIMESTAMP,
    0.120,
    'column does not exist'
FROM database_instances
WHERE database_name = 'enterprise_hr';

INSERT INTO query_plan_nodes (
    execution_id,
    node_type,
    relation_name,
    estimated_rows,
    actual_rows,
    startup_cost,
    total_cost,
    actual_time_ms
)
SELECT
    execution_id,
    'SEQ_SCAN',
    'employees',
    10000,
    4,
    0,
    145,
    0.350
FROM query_executions
WHERE query_fingerprint = 'employee-department-summary'
ORDER BY execution_id DESC
LIMIT 1;

-- ============================================================
-- 17. QUERY: BUFFER POOL HIT RATIO
-- ============================================================

SELECT
    observation_id,
    observed_at,
    cache_hits,
    cache_misses,
    buffer_hit_ratio(
        cache_hits,
        cache_misses
    ) AS hit_ratio,
    evictions,
    dirty_pages
FROM buffer_pool_observations
ORDER BY observed_at DESC;

-- ============================================================
-- 18. QUERY: PHYSICAL PAGE UTILIZATION
-- ============================================================

SELECT
    t.table_name,
    COUNT(p.page_id) AS total_pages,
    COALESCE(SUM(p.tuple_count), 0) AS total_tuples,
    COALESCE(SUM(p.used_bytes), 0) AS used_bytes,
    COALESCE(SUM(p.free_bytes), 0) AS free_bytes,
    ROUND(
        100.0 * SUM(p.used_bytes) /
        NULLIF(SUM(p.page_size_bytes), 0),
        2
    ) AS utilization_percentage
FROM database_tables t
LEFT JOIN storage_pages p
    ON p.table_id = t.table_id
GROUP BY t.table_id, t.table_name
ORDER BY t.table_name;

-- ============================================================
-- 19. QUERY: DIRTY PAGE IDENTIFICATION
-- ============================================================

SELECT
    p.page_id,
    t.table_name,
    p.page_number,
    p.page_lsn,
    p.used_bytes,
    p.free_bytes,
    p.observed_at
FROM storage_pages p
JOIN database_tables t
    ON t.table_id = p.table_id
WHERE p.is_dirty = TRUE
ORDER BY p.observed_at;

-- ============================================================
-- 20. QUERY: TRANSACTION LIFECYCLE
-- ============================================================

SELECT
    transaction_id,
    application_name,
    transaction_status,
    isolation_level,
    started_at,
    completed_at,
    EXTRACT(
        EPOCH FROM completed_at - started_at
    ) AS duration_seconds,
    abort_reason
FROM database_transactions
ORDER BY started_at DESC;

-- ============================================================
-- 21. QUERY: INDEX USAGE AND EFFICIENCY
-- ============================================================

SELECT
    t.table_name,
    i.index_name,
    i.index_type,
    i.indexed_column,
    i.estimated_entries,
    i.tree_height,
    COALESCE(o.index_scans, 0) AS index_scans,
    COALESCE(o.tuples_read, 0) AS tuples_read,
    COALESCE(o.tuples_returned, 0) AS tuples_returned
FROM database_indexes i
JOIN database_tables t
    ON t.table_id = i.table_id
LEFT JOIN LATERAL (
    SELECT *
    FROM index_observations io
    WHERE io.index_id = i.index_id
    ORDER BY io.observed_at DESC
    LIMIT 1
) o ON TRUE
ORDER BY t.table_name, i.index_name;

-- ============================================================
-- 22. QUERY: QUERY PLAN AND CARDINALITY ESTIMATION
-- ============================================================

SELECT
    q.execution_id,
    q.query_fingerprint,
    n.node_type,
    n.relation_name,
    n.estimated_rows,
    n.actual_rows,
    n.total_cost,
    n.actual_time_ms,
    CASE
        WHEN n.estimated_rows IS NULL
             OR n.estimated_rows = 0
            THEN NULL
        ELSE ROUND(
            n.actual_rows / n.estimated_rows,
            3
        )
    END AS cardinality_error_ratio
FROM query_executions q
JOIN query_plan_nodes n
    ON n.execution_id = q.execution_id
ORDER BY q.execution_id, n.plan_node_id;

-- ============================================================
-- 23. QUERY: COST-BASED ACCESS PATH EVALUATION
-- ============================================================

SELECT *
FROM choose_access_path(
    100000,
    100000,
    64
);

SELECT *
FROM choose_access_path(
    100000,
    10,
    64
);

-- ============================================================
-- 24. QUERY: RELATIONAL QUERY EXECUTION
-- ============================================================

EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT TEXT)
SELECT
    d.department_name,
    COUNT(*) AS employee_count,
    AVG(e.salary) AS average_salary,
    MIN(e.salary) AS minimum_salary,
    MAX(e.salary) AS maximum_salary
FROM employees e
JOIN departments d
    ON d.department_id = e.department_id
WHERE e.salary >= 85000
GROUP BY d.department_name
ORDER BY average_salary DESC;

-- ============================================================
-- 25. QUERY: COMMON TABLE EXPRESSION
-- ============================================================

WITH department_statistics AS (
    SELECT
        department_id,
        COUNT(*) AS employee_count,
        SUM(salary) AS total_salary,
        AVG(salary) AS average_salary
    FROM employees
    GROUP BY department_id
),
ranked_departments AS (
    SELECT
        d.department_name,
        s.employee_count,
        s.total_salary,
        s.average_salary,
        RANK() OVER (
            ORDER BY s.average_salary DESC
        ) AS salary_rank
    FROM department_statistics s
    JOIN departments d
        ON d.department_id = s.department_id
)
SELECT *
FROM ranked_departments
ORDER BY salary_rank;

-- ============================================================
-- 26. QUERY: AGGREGATED WORKLOAD REPORT
-- ============================================================

SELECT
    query_fingerprint,
    COUNT(*) AS execution_count,
    ROUND(AVG(execution_time_ms), 3) AS average_ms,
    ROUND(MAX(execution_time_ms), 3) AS maximum_ms,
    SUM(shared_blocks_hit) AS total_cache_hits,
    SUM(shared_blocks_read) AS total_disk_reads,
    SUM(temporary_blocks_written) AS temporary_blocks
FROM query_executions
GROUP BY query_fingerprint
ORDER BY average_ms DESC NULLS LAST;

-- ============================================================
-- 27. QUERY: EXPIRED MVCC VERSION CANDIDATES
-- ============================================================

SELECT
    v.tuple_version_id,
    t.table_name,
    v.logical_row_id,
    v.version_number,
    v.xmin_transaction,
    v.xmax_transaction,
    creator.transaction_status AS creator_status,
    deleter.transaction_status AS deleter_status
FROM tuple_versions v
JOIN database_tables t
    ON t.table_id = v.table_id
LEFT JOIN database_transactions creator
    ON creator.transaction_id = v.xmin_transaction
LEFT JOIN database_transactions deleter
    ON deleter.transaction_id = v.xmax_transaction
WHERE v.xmax_transaction IS NOT NULL
  AND deleter.transaction_status IN (
      'COMMITTED',
      'ABORTED'
  )
ORDER BY v.logical_row_id, v.version_number;

-- This query identifies candidates for investigation.
-- It does not implement PostgreSQL vacuum visibility rules.

-- ============================================================
-- 28. QUERY: FAILURE AND RESOURCE REPORT
-- ============================================================

SELECT
    database_name,
    query_fingerprint,
    execution_status,
    execution_time_ms,
    error_message,
    started_at
FROM query_executions q
JOIN database_instances d
    ON d.database_id = q.database_id
WHERE execution_status IN ('FAILED', 'CANCELLED')
ORDER BY started_at DESC;

-- ============================================================
-- 29. TRANSACTIONAL WORKFLOW DEMONSTRATION
-- ============================================================

DO $$
DECLARE
    v_database_id BIGINT;
    v_transaction_id BIGINT;
BEGIN
    SELECT database_id
    INTO v_database_id
    FROM database_instances
    WHERE database_name = 'enterprise_hr';

    INSERT INTO database_transactions (
        database_id,
        application_name,
        transaction_status,
        isolation_level
    )
    VALUES (
        v_database_id,
        'procedure-demonstration',
        'ACTIVE',
        'READ COMMITTED'
    )
    RETURNING transaction_id
    INTO v_transaction_id;

    CALL complete_database_transaction(
        v_transaction_id,
        TRUE
    );
END;
$$;

-- ============================================================
-- 30. VALIDATION AND FAILURE TESTS
-- ============================================================

-- Valid page accounting.
INSERT INTO storage_pages (
    table_id,
    page_number,
    page_type,
    page_size_bytes,
    used_bytes,
    free_bytes,
    tuple_count,
    is_dirty
)
SELECT
    table_id,
    1,
    'HEAP',
    8192,
    1024,
    7168,
    2,
    TRUE
FROM database_tables
WHERE table_name = 'employees'
ON CONFLICT (table_id, page_number) DO NOTHING;

-- The following invalid operations are isolated inside
-- exception blocks so the complete script remains executable.

DO $$
BEGIN
    BEGIN
        INSERT INTO employees (
            employee_id,
            employee_name,
            department_id,
            salary
        )
        VALUES (
            999,
            'Invalid Salary',
            1,
            -500
        );

        RAISE EXCEPTION
            'Expected salary constraint violation was not raised';

    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE
                'Expected salary validation succeeded';
    END;

    BEGIN
        INSERT INTO storage_pages (
            table_id,
            page_number,
            page_type,
            page_size_bytes,
            used_bytes,
            free_bytes,
            tuple_count
        )
        SELECT
            table_id,
            999,
            'HEAP',
            8192,
            7000,
            2000,
            2
        FROM database_tables
        WHERE table_name = 'employees';

        RAISE EXCEPTION
            'Expected page accounting failure was not raised';

    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE
                'Expected page accounting validation succeeded';
    END;
END;
$$;

-- ============================================================
-- 31. USEFUL OPERATIONAL VIEWS
-- ============================================================

CREATE OR REPLACE VIEW database_storage_report AS
SELECT
    t.table_name,
    COUNT(p.page_id) AS page_count,
    COALESCE(SUM(p.tuple_count), 0) AS tuple_count,
    COALESCE(SUM(p.used_bytes), 0) AS used_bytes,
    COALESCE(SUM(p.free_bytes), 0) AS free_bytes,
    COUNT(*) FILTER (
        WHERE p.is_dirty = TRUE
    ) AS dirty_page_count
FROM database_tables t
LEFT JOIN storage_pages p
    ON p.table_id = t.table_id
GROUP BY t.table_id, t.table_name;

CREATE OR REPLACE VIEW database_query_performance AS
SELECT
    query_fingerprint,
    COUNT(*) AS execution_count,
    ROUND(AVG(execution_time_ms), 3) AS average_execution_ms,
    MAX(execution_time_ms) AS maximum_execution_ms,
    SUM(shared_blocks_hit) AS shared_hits,
    SUM(shared_blocks_read) AS shared_reads,
    COUNT(*) FILTER (
        WHERE execution_status = 'FAILED'
    ) AS failures
FROM query_executions
GROUP BY query_fingerprint;

CREATE OR REPLACE VIEW active_database_transactions AS
SELECT
    transaction_id,
    database_id,
    application_name,
    isolation_level,
    started_at,
    CURRENT_TIMESTAMP - started_at AS transaction_age
FROM database_transactions
WHERE transaction_status = 'ACTIVE';

-- ============================================================
-- 32. FINAL VALIDATION QUERIES
-- ============================================================

SELECT * FROM database_storage_report;

SELECT * FROM database_query_performance;

SELECT * FROM active_database_transactions;

SELECT
    COUNT(*) AS employee_count,
    COUNT(DISTINCT department_id) AS department_count,
    AVG(salary) AS average_salary
FROM employees;

-- ============================================================
-- END OF PROJECT
-- ============================================================

COMMIT;
