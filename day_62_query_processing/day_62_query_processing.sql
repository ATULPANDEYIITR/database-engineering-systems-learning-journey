DROP SCHEMA IF EXISTS query_processing CASCADE;
CREATE SCHEMA query_processing;

SET search_path TO query_processing, public;

CREATE TYPE query_processing.query_status AS ENUM (
    'RECEIVED',
    'PARSED',
    'ANALYZED',
    'REWRITTEN',
    'PLANNED',
    'EXECUTED',
    'FAILED'
);

CREATE TYPE query_processing.plan_node_type AS ENUM (
    'SCAN',
    'FILTER',
    'SORT',
    'LIMIT',
    'PROJECT'
);

CREATE TABLE query_processing.repositories (
    repository_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_name TEXT NOT NULL UNIQUE,
    owner_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE query_processing.tables_catalog (
    table_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    repository_id BIGINT REFERENCES query_processing.repositories(repository_id)
        ON DELETE CASCADE,
    table_name TEXT NOT NULL,
    row_estimate BIGINT NOT NULL CHECK (row_estimate >= 0),
    UNIQUE (repository_id, table_name)
);

CREATE TABLE query_processing.columns_catalog (
    column_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_id BIGINT NOT NULL REFERENCES query_processing.tables_catalog(table_id)
        ON DELETE CASCADE,
    column_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    ordinal_position INTEGER NOT NULL CHECK (ordinal_position > 0),
    nullable BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (table_id, column_name),
    UNIQUE (table_id, ordinal_position)
);

CREATE TABLE query_processing.indexes_catalog (
    index_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_id BIGINT NOT NULL REFERENCES query_processing.tables_catalog(table_id)
        ON DELETE CASCADE,
    index_name TEXT NOT NULL,
    indexed_columns TEXT[] NOT NULL CHECK (cardinality(indexed_columns) > 0),
    estimated_selectivity NUMERIC(6,5)
        CHECK (
            estimated_selectivity IS NULL OR
            estimated_selectivity BETWEEN 0 AND 1
        ),
    is_unique BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (table_id, index_name)
);

CREATE TABLE query_processing.queries (
    query_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sql_text TEXT NOT NULL CHECK (length(btrim(sql_text)) > 0),
    status query_processing.query_status NOT NULL DEFAULT 'RECEIVED',
    received_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    CHECK (
        (status <> 'FAILED' AND error_message IS NULL)
        OR
        (status = 'FAILED')
    )
);

CREATE TABLE query_processing.query_tables (
    query_id BIGINT NOT NULL REFERENCES query_processing.queries(query_id)
        ON DELETE CASCADE,
    table_id BIGINT NOT NULL REFERENCES query_processing.tables_catalog(table_id),
    access_type TEXT NOT NULL CHECK (
        access_type IN ('READ', 'WRITE')
    ),
    PRIMARY KEY (query_id, table_id)
);

CREATE TABLE query_processing.query_predicates (
    predicate_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    query_id BIGINT NOT NULL REFERENCES query_processing.queries(query_id)
        ON DELETE CASCADE,
    column_id BIGINT NOT NULL REFERENCES query_processing.columns_catalog(column_id),
    operator TEXT NOT NULL CHECK (
        operator IN ('=', '!=', '<>', '>', '<', '>=', '<=')
    ),
    literal_value TEXT NOT NULL
);

CREATE TABLE query_processing.plan_nodes (
    plan_node_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    query_id BIGINT NOT NULL REFERENCES query_processing.queries(query_id)
        ON DELETE CASCADE,
    parent_node_id BIGINT REFERENCES query_processing.plan_nodes(plan_node_id),
    node_type query_processing.plan_node_type NOT NULL,
    relation_name TEXT,
    estimated_rows NUMERIC(20,2),
    estimated_cost NUMERIC(20,4) CHECK (
        estimated_cost IS NULL OR estimated_cost >= 0
    ),
    actual_rows BIGINT CHECK (actual_rows IS NULL OR actual_rows >= 0),
    actual_cost NUMERIC(20,4) CHECK (
        actual_cost IS NULL OR actual_cost >= 0
    ),
    node_order INTEGER NOT NULL CHECK (node_order > 0),
    UNIQUE (query_id, node_order)
);

CREATE TABLE query_processing.query_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    query_id BIGINT NOT NULL REFERENCES query_processing.queries(query_id)
        ON DELETE CASCADE,
    event_status query_processing.query_status NOT NULL,
    event_time TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    detail JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_queries_status
    ON query_processing.queries(status);

CREATE INDEX idx_query_tables_table
    ON query_processing.query_tables(table_id);

CREATE INDEX idx_predicates_query
    ON query_processing.query_predicates(query_id);

CREATE INDEX idx_plan_nodes_query
    ON query_processing.plan_nodes(query_id, node_order);

CREATE INDEX idx_query_events_query_time
    ON query_processing.query_events(query_id, event_time);

CREATE OR REPLACE FUNCTION query_processing.record_query_event()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO query_processing.query_events(
        query_id,
        event_status,
        detail
    )
    VALUES (
        NEW.query_id,
        NEW.status,
        jsonb_build_object(
            'sql_length',
            length(NEW.sql_text)
        )
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_record_query_event
AFTER INSERT OR UPDATE OF status
ON query_processing.queries
FOR EACH ROW
EXECUTE FUNCTION query_processing.record_query_event();

CREATE OR REPLACE FUNCTION query_processing.validate_query_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    previous_status query_processing.query_status;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        previous_status := OLD.status;

        IF NEW.status = 'PARSED'
           AND previous_status <> 'RECEIVED' THEN
            RAISE EXCEPTION
                'PARSED requires RECEIVED state';
        END IF;

        IF NEW.status = 'ANALYZED'
           AND previous_status <> 'PARSED' THEN
            RAISE EXCEPTION
                'ANALYZED requires PARSED state';
        END IF;

        IF NEW.status = 'REWRITTEN'
           AND previous_status <> 'ANALYZED' THEN
            RAISE EXCEPTION
                'REWRITTEN requires ANALYZED state';
        END IF;

        IF NEW.status = 'PLANNED'
           AND previous_status <> 'REWRITTEN' THEN
            RAISE EXCEPTION
                'PLANNED requires REWRITTEN state';
        END IF;

        IF NEW.status = 'EXECUTED'
           AND previous_status <> 'PLANNED' THEN
            RAISE EXCEPTION
                'EXECUTED requires PLANNED state';
        END IF;
    END IF;

    IF NEW.status = 'EXECUTED' AND NEW.completed_at IS NULL THEN
        NEW.completed_at := clock_timestamp();
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_query_status
BEFORE UPDATE OF status
ON query_processing.queries
FOR EACH ROW
EXECUTE FUNCTION query_processing.validate_query_status();

CREATE OR REPLACE FUNCTION query_processing.register_query(
    p_sql TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_query_id BIGINT;
BEGIN
    IF p_sql IS NULL OR length(btrim(p_sql)) = 0 THEN
        RAISE EXCEPTION 'Query text cannot be empty';
    END IF;

    INSERT INTO query_processing.queries(sql_text)
    VALUES (p_sql)
    RETURNING query_id INTO v_query_id;

    RETURN v_query_id;
END;
$$;

CREATE OR REPLACE FUNCTION query_processing.advance_query(
    p_query_id BIGINT,
    p_status query_processing.query_status
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE query_processing.queries
    SET status = p_status
    WHERE query_id = p_query_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown query id %', p_query_id;
    END IF;
END;
$$;

CREATE OR REPLACE VIEW query_processing.query_pipeline AS
SELECT
    q.query_id,
    q.sql_text,
    q.status,
    q.received_at,
    q.completed_at,
    count(DISTINCT qt.table_id) AS referenced_tables,
    count(DISTINCT qp.predicate_id) AS predicates,
    count(DISTINCT pn.plan_node_id) AS plan_nodes
FROM query_processing.queries q
LEFT JOIN query_processing.query_tables qt
    ON qt.query_id = q.query_id
LEFT JOIN query_processing.query_predicates qp
    ON qp.query_id = q.query_id
LEFT JOIN query_processing.plan_nodes pn
    ON pn.query_id = q.query_id
GROUP BY
    q.query_id,
    q.sql_text,
    q.status,
    q.received_at,
    q.completed_at;

CREATE OR REPLACE VIEW query_processing.plan_report AS
SELECT
    pn.query_id,
    pn.node_order,
    pn.node_type,
    pn.relation_name,
    pn.estimated_rows,
    pn.estimated_cost,
    pn.actual_rows,
    pn.actual_cost
FROM query_processing.plan_nodes pn
ORDER BY pn.query_id, pn.node_order;

INSERT INTO query_processing.repositories(
    repository_name,
    owner_name
)
VALUES
    ('analytics-platform', 'platform-team'),
    ('security-reporting', 'security-team');

INSERT INTO query_processing.tables_catalog(
    repository_id,
    table_name,
    row_estimate
)
SELECT
    r.repository_id,
    v.table_name,
    v.row_estimate
FROM query_processing.repositories r
JOIN (
    VALUES
        ('analytics-platform', 'employees', 50000::BIGINT),
        ('analytics-platform', 'departments', 120::BIGINT),
        ('security-reporting', 'incidents', 150000::BIGINT)
) AS v(repository_name, table_name, row_estimate)
ON v.repository_name = r.repository_name;

INSERT INTO query_processing.columns_catalog(
    table_id,
    column_name,
    data_type,
    ordinal_position,
    nullable
)
SELECT
    t.table_id,
    v.column_name,
    v.data_type,
    v.ordinal_position,
    v.nullable
FROM query_processing.tables_catalog t
JOIN (
    VALUES
        ('employees', 'id', 'integer', 1, false),
        ('employees', 'name', 'text', 2, false),
        ('employees', 'department', 'text', 3, false),
        ('employees', 'salary', 'integer', 4, false),
        ('departments', 'id', 'integer', 1, false),
        ('departments', 'name', 'text', 2, false),
        ('incidents', 'id', 'integer', 1, false),
        ('incidents', 'severity', 'integer', 2, false),
        ('incidents', 'status', 'text', 3, false)
) AS v(table_name, column_name, data_type, ordinal_position, nullable)
ON v.table_name = t.table_name;

INSERT INTO query_processing.indexes_catalog(
    table_id,
    index_name,
    indexed_columns,
    estimated_selectivity,
    is_unique
)
SELECT
    t.table_id,
    v.index_name,
    v.indexed_columns,
    v.estimated_selectivity,
    v.is_unique
FROM query_processing.tables_catalog t
JOIN (
    VALUES
        (
            'employees',
            'employees_department_idx',
            ARRAY['department']::TEXT[],
            0.08::NUMERIC,
            false
        ),
        (
            'employees',
            'employees_salary_idx',
            ARRAY['salary']::TEXT[],
            0.18::NUMERIC,
            false
        ),
        (
            'incidents',
            'incidents_severity_idx',
            ARRAY['severity']::TEXT[],
            0.04::NUMERIC,
            false
        )
) AS v(
    table_name,
    index_name,
    indexed_columns,
    estimated_selectivity,
    is_unique
)
ON v.table_name = t.table_name;

BEGIN;

SELECT query_processing.register_query(
    'SELECT name, salary FROM employees WHERE salary >= 90000 ORDER BY salary DESC LIMIT 3'
);

COMMIT;

UPDATE query_processing.queries
SET status = 'PARSED'
WHERE query_id = 1;

INSERT INTO query_processing.query_tables(
    query_id,
    table_id,
    access_type
)
SELECT
    1,
    table_id,
    'READ'
FROM query_processing.tables_catalog
WHERE table_name = 'employees';

INSERT INTO query_processing.query_predicates(
    query_id,
    column_id,
    operator,
    literal_value
)
SELECT
    1,
    c.column_id,
    '>=',
    '90000'
FROM query_processing.columns_catalog c
JOIN query_processing.tables_catalog t
    ON t.table_id = c.table_id
WHERE t.table_name = 'employees'
  AND c.column_name = 'salary';

UPDATE query_processing.queries
SET status = 'ANALYZED'
WHERE query_id = 1;

UPDATE query_processing.queries
SET status = 'REWRITTEN'
WHERE query_id = 1;

INSERT INTO query_processing.plan_nodes(
    query_id,
    node_type,
    relation_name,
    estimated_rows,
    estimated_cost,
    node_order
)
VALUES
    (1, 'SCAN', 'employees', 50000, 50.00, 1),
    (1, 'FILTER', 'employees', 9000, 25.00, 2),
    (1, 'SORT', 'employees', 9000, 70.00, 3),
    (1, 'LIMIT', 'employees', 3, 0.10, 4),
    (1, 'PROJECT', 'employees', 3, 0.05, 5);

UPDATE query_processing.queries
SET status = 'PLANNED'
WHERE query_id = 1;

UPDATE query_processing.plan_nodes
SET actual_rows = CASE node_type
    WHEN 'SCAN' THEN 50000
    WHEN 'FILTER' THEN 9000
    WHEN 'SORT' THEN 9000
    WHEN 'LIMIT' THEN 3
    WHEN 'PROJECT' THEN 3
END,
actual_cost = CASE node_type
    WHEN 'SCAN' THEN 47.20
    WHEN 'FILTER' THEN 19.30
    WHEN 'SORT' THEN 62.70
    WHEN 'LIMIT' THEN 0.08
    WHEN 'PROJECT' THEN 0.03
END
WHERE query_id = 1;

UPDATE query_processing.queries
SET status = 'EXECUTED'
WHERE query_id = 1;

BEGIN;

SELECT query_processing.register_query(
    'SELECT unknown_column FROM employees'
);

UPDATE query_processing.queries
SET status = 'FAILED',
    error_message = 'Unknown column: unknown_column'
WHERE query_id = 2;

COMMIT;

SELECT
    query_id,
    sql_text,
    status,
    referenced_tables,
    predicates,
    plan_nodes
FROM query_processing.query_pipeline
ORDER BY query_id;

SELECT
    query_id,
    node_order,
    node_type,
    relation_name,
    estimated_rows,
    estimated_cost,
    actual_rows,
    actual_cost
FROM query_processing.plan_report
WHERE query_id = 1
ORDER BY node_order;

WITH predicate_usage AS (
    SELECT
        c.column_name,
        count(*) AS predicate_count
    FROM query_processing.query_predicates qp
    JOIN query_processing.columns_catalog c
        ON c.column_id = qp.column_id
    GROUP BY c.column_name
)
SELECT
    column_name,
    predicate_count
FROM predicate_usage
ORDER BY predicate_count DESC, column_name;

SELECT
    q.query_id,
    q.status,
    e.event_status,
    e.event_time,
    e.detail
FROM query_processing.queries q
JOIN query_processing.query_events e
    ON e.query_id = q.query_id
ORDER BY q.query_id, e.event_time;
