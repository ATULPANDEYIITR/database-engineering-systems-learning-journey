/*
 * QUERY OPTIMIZER
 * Cost Estimation, Statistics and Plan Selection
 *
 * PostgreSQL 15+
 *
 * Features:
 * - Relational statistics catalog
 * - Column statistics and MCV distributions
 * - Histogram boundaries
 * - Index statistics
 * - Predicate selectivity estimation
 * - Filtered cardinality estimation
 * - Sequential and index scan costing
 * - Hash and nested-loop join costing
 * - Statistics freshness monitoring
 * - Cost-based plan candidate ranking
 * - Reporting and validation
 *
 * This is an educational cost-based optimizer model.
 * It does not replace PostgreSQL's native optimizer.
 */

BEGIN;

CREATE SCHEMA IF NOT EXISTS query_lab;

SET search_path TO query_lab, public;

-- ============================================================
-- 1. ENUM TYPES
-- ============================================================

CREATE TYPE query_lab.predicate_operator AS ENUM (
    'EQUAL',
    'LESS_THAN',
    'GREATER_THAN',
    'BETWEEN'
);

CREATE TYPE query_lab.plan_operation AS ENUM (
    'SEQUENTIAL_SCAN',
    'INDEX_SCAN',
    'HASH_JOIN',
    'NESTED_LOOP'
);

CREATE TYPE query_lab.query_state AS ENUM (
    'DRAFT',
    'VALIDATED',
    'OPTIMIZED',
    'FAILED'
);

-- ============================================================
-- 2. COST CONFIGURATION
-- ============================================================

CREATE TABLE query_lab.cost_configuration (
    configuration_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    configuration_name VARCHAR(100) NOT NULL UNIQUE,

    sequential_page_cost NUMERIC(12, 6) NOT NULL
        CHECK (sequential_page_cost > 0),

    random_page_cost NUMERIC(12, 6) NOT NULL
        CHECK (random_page_cost > 0),

    cpu_tuple_cost NUMERIC(12, 6) NOT NULL
        CHECK (cpu_tuple_cost > 0),

    cpu_operator_cost NUMERIC(12, 6) NOT NULL
        CHECK (cpu_operator_cost > 0),

    hash_build_cost NUMERIC(12, 6) NOT NULL
        CHECK (hash_build_cost > 0),

    nested_loop_cost NUMERIC(12, 6) NOT NULL
        CHECK (nested_loop_cost > 0),

    cache_discount NUMERIC(5, 4) NOT NULL
        CHECK (
            cache_discount > 0
            AND cache_discount <= 1
        ),

    is_active BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO query_lab.cost_configuration (
    configuration_name,
    sequential_page_cost,
    random_page_cost,
    cpu_tuple_cost,
    cpu_operator_cost,
    hash_build_cost,
    nested_loop_cost,
    cache_discount,
    is_active
)
VALUES (
    'DEFAULT_COST_MODEL',
    1.0,
    4.0,
    0.01,
    0.0025,
    0.015,
    0.005,
    0.75,
    TRUE
);

-- ============================================================
-- 3. RELATIONAL STATISTICS
-- ============================================================

CREATE TABLE query_lab.relation_statistics (
    relation_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    relation_name VARCHAR(128) NOT NULL UNIQUE,

    schema_name VARCHAR(128) NOT NULL DEFAULT 'public',

    estimated_rows BIGINT NOT NULL
        CHECK (estimated_rows >= 0),

    estimated_pages BIGINT NOT NULL
        CHECK (estimated_pages >= 0),

    statistics_target INTEGER NOT NULL DEFAULT 100
        CHECK (statistics_target > 0),

    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        estimated_rows = 0 OR estimated_pages > 0
    )
);

CREATE INDEX idx_relation_statistics_analyzed
ON query_lab.relation_statistics (analyzed_at);

-- ============================================================
-- 4. COLUMN STATISTICS
-- ============================================================

CREATE TABLE query_lab.column_statistics (
    column_statistics_id BIGINT
        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    relation_id BIGINT NOT NULL
        REFERENCES query_lab.relation_statistics(relation_id)
        ON DELETE CASCADE,

    column_name VARCHAR(128) NOT NULL,

    distinct_values BIGINT NOT NULL
        CHECK (distinct_values > 0),

    null_fraction NUMERIC(8, 6) NOT NULL DEFAULT 0
        CHECK (
            null_fraction >= 0
            AND null_fraction <= 1
        ),

    most_common_values JSONB NOT NULL DEFAULT '{}'::JSONB,

    histogram_boundaries NUMERIC[],

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (relation_id, column_name)
);

CREATE INDEX idx_column_statistics_relation
ON query_lab.column_statistics (
    relation_id,
    column_name
);

-- ============================================================
-- 5. INDEX STATISTICS
-- ============================================================

CREATE TABLE query_lab.index_statistics (
    index_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    relation_id BIGINT NOT NULL
        REFERENCES query_lab.relation_statistics(relation_id)
        ON DELETE CASCADE,

    column_name VARCHAR(128) NOT NULL,

    index_name VARCHAR(128) NOT NULL UNIQUE,

    index_pages BIGINT NOT NULL
        CHECK (index_pages > 0),

    is_unique BOOLEAN NOT NULL DEFAULT FALSE,

    is_index_only BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (relation_id, column_name)
);

CREATE INDEX idx_index_statistics_relation
ON query_lab.index_statistics (
    relation_id,
    column_name
);

-- ============================================================
-- 6. QUERY WORKLOAD
-- ============================================================

CREATE TABLE query_lab.query_workload (
    query_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    query_name VARCHAR(150) NOT NULL UNIQUE,

    description TEXT,

    state query_lab.query_state NOT NULL DEFAULT 'DRAFT',

    submitted_by VARCHAR(128) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    optimized_at TIMESTAMPTZ
);

CREATE TABLE query_lab.query_relations (
    query_id BIGINT NOT NULL
        REFERENCES query_lab.query_workload(query_id)
        ON DELETE CASCADE,

    relation_id BIGINT NOT NULL
        REFERENCES query_lab.relation_statistics(relation_id),

    execution_order INTEGER NOT NULL
        CHECK (execution_order > 0),

    PRIMARY KEY (query_id, relation_id),

    UNIQUE (query_id, execution_order)
);

CREATE TABLE query_lab.query_predicates (
    predicate_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    query_id BIGINT NOT NULL,

    relation_id BIGINT NOT NULL,

    column_name VARCHAR(128) NOT NULL,

    operator query_lab.predicate_operator NOT NULL,

    predicate_value TEXT,

    upper_value NUMERIC,

    FOREIGN KEY (query_id, relation_id)
        REFERENCES query_lab.query_relations(
            query_id,
            relation_id
        )
        ON DELETE CASCADE,

    CHECK (
        operator <> 'BETWEEN'
        OR (
            predicate_value IS NOT NULL
            AND upper_value IS NOT NULL
        )
    )
);

CREATE INDEX idx_query_predicates_query
ON query_lab.query_predicates (
    query_id,
    relation_id
);

CREATE TABLE query_lab.query_joins (
    join_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    query_id BIGINT NOT NULL
        REFERENCES query_lab.query_workload(query_id)
        ON DELETE CASCADE,

    left_relation_id BIGINT NOT NULL
        REFERENCES query_lab.relation_statistics(relation_id),

    left_column VARCHAR(128) NOT NULL,

    right_relation_id BIGINT NOT NULL
        REFERENCES query_lab.relation_statistics(relation_id),

    right_column VARCHAR(128) NOT NULL,

    CHECK (left_relation_id <> right_relation_id)
);

CREATE INDEX idx_query_joins_query
ON query_lab.query_joins(query_id);

-- ============================================================
-- 7. EXECUTION PLAN CANDIDATES
-- ============================================================

CREATE TABLE query_lab.execution_plan_candidates (
    plan_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    query_id BIGINT NOT NULL
        REFERENCES query_lab.query_workload(query_id)
        ON DELETE CASCADE,

    operation query_lab.plan_operation NOT NULL,

    relation_id BIGINT
        REFERENCES query_lab.relation_statistics(relation_id),

    estimated_rows NUMERIC(24, 4) NOT NULL
        CHECK (estimated_rows >= 0),

    estimated_cost NUMERIC(24, 6) NOT NULL
        CHECK (estimated_cost >= 0),

    plan_details JSONB NOT NULL DEFAULT '{}'::JSONB,

    is_selected BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_plan_candidates_ranking
ON query_lab.execution_plan_candidates (
    query_id,
    estimated_cost
);

-- ============================================================
-- 8. OPTIMIZATION RESULTS
-- ============================================================

CREATE TABLE query_lab.optimization_results (
    result_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    query_id BIGINT NOT NULL
        REFERENCES query_lab.query_workload(query_id)
        ON DELETE CASCADE,

    selected_plan_id BIGINT
        REFERENCES query_lab.execution_plan_candidates(plan_id),

    estimated_total_cost NUMERIC(24, 6) NOT NULL
        CHECK (estimated_total_cost >= 0),

    estimated_output_rows NUMERIC(24, 4) NOT NULL
        CHECK (estimated_output_rows >= 0),

    optimization_method VARCHAR(100) NOT NULL,

    statistics_revision TIMESTAMPTZ,

    optimized_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_optimization_results_query
ON query_lab.optimization_results (
    query_id,
    optimized_at DESC
);

-- ============================================================
-- 9. UPDATED_AT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION query_lab.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_relation_statistics_updated
BEFORE UPDATE ON query_lab.relation_statistics
FOR EACH ROW
EXECUTE FUNCTION query_lab.set_updated_at();

-- ============================================================
-- 10. STATISTICS VALIDATION TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION query_lab.validate_column_statistics()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_total NUMERIC;
    v_item JSONB;
BEGIN
    IF jsonb_typeof(NEW.most_common_values) <> 'object' THEN
        RAISE EXCEPTION
            'Most common values must be a JSON object';
    END IF;

    v_total := 0;

    FOR v_item IN
        SELECT value
        FROM jsonb_each(NEW.most_common_values)
    LOOP
        IF jsonb_typeof(v_item) <> 'number' THEN
            RAISE EXCEPTION
                'MCV frequencies must be numeric';
        END IF;

        IF (v_item #>> '{}')::NUMERIC < 0
           OR (v_item #>> '{}')::NUMERIC > 1 THEN
            RAISE EXCEPTION
                'MCV frequency must be between 0 and 1';
        END IF;

        v_total := v_total + (v_item #>> '{}')::NUMERIC;
    END LOOP;

    IF v_total > 1 THEN
        RAISE EXCEPTION
            'MCV frequencies cannot exceed one';
    END IF;

    IF NEW.histogram_boundaries IS NOT NULL THEN
        IF cardinality(NEW.histogram_boundaries) < 2 THEN
            RAISE EXCEPTION
                'Histogram requires at least two boundaries';
        END IF;

        IF EXISTS (
            SELECT 1
            FROM generate_subscripts(
                NEW.histogram_boundaries,
                1
            ) AS positions(i)
            WHERE i > 1
              AND NEW.histogram_boundaries[i]
                  <= NEW.histogram_boundaries[i - 1]
        ) THEN
            RAISE EXCEPTION
                'Histogram boundaries must be increasing';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_column_statistics
BEFORE INSERT OR UPDATE
ON query_lab.column_statistics
FOR EACH ROW
EXECUTE FUNCTION query_lab.validate_column_statistics();

-- ============================================================
-- 11. PREDICATE SELECTIVITY FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION query_lab.estimate_selectivity(
    p_relation_id BIGINT,
    p_column_name VARCHAR,
    p_operator query_lab.predicate_operator,
    p_value TEXT,
    p_upper NUMERIC DEFAULT NULL
)
RETURNS NUMERIC
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_column query_lab.column_statistics%ROWTYPE;
    v_mcv NUMERIC;
    v_low NUMERIC;
    v_high NUMERIC;
    v_min NUMERIC;
    v_max NUMERIC;
    v_selectivity NUMERIC;
BEGIN

    SELECT *
    INTO v_column
    FROM query_lab.column_statistics
    WHERE relation_id = p_relation_id
      AND column_name = p_column_name;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Statistics unavailable for column %.%',
            p_relation_id,
            p_column_name;
    END IF;

    IF p_operator = 'EQUAL' THEN

        IF p_value IS NULL THEN
            RETURN v_column.null_fraction;
        END IF;

        IF p_value = 'NULL' THEN
            RETURN v_column.null_fraction;
        END IF;

        IF v_column.most_common_values ? p_value THEN
            RETURN (
                v_column.most_common_values ->> p_value
            )::NUMERIC;
        END IF;

        RETURN (
            (1 - v_column.null_fraction)
            / v_column.distinct_values
        );

    END IF;

    IF v_column.histogram_boundaries IS NULL THEN

        IF p_operator = 'BETWEEN' THEN
            RETURN 0.25;
        END IF;

        RETURN 0.33;
    END IF;

    v_min := v_column.histogram_boundaries[1];

    v_max := v_column.histogram_boundaries[
        cardinality(v_column.histogram_boundaries)
    ];

    IF p_operator = 'LESS_THAN' THEN

        v_low := v_min;
        v_high := p_value::NUMERIC;

    ELSIF p_operator = 'GREATER_THAN' THEN

        v_low := p_value::NUMERIC;
        v_high := v_max;

    ELSIF p_operator = 'BETWEEN' THEN

        IF p_upper IS NULL THEN
            RAISE EXCEPTION
                'BETWEEN requires an upper boundary';
        END IF;

        v_low := p_value::NUMERIC;
        v_high := p_upper;

    ELSE
        RAISE EXCEPTION 'Unsupported predicate operator';
    END IF;

    IF v_low > v_high THEN
        RAISE EXCEPTION 'Invalid histogram range';
    END IF;

    IF v_high <= v_min OR v_low >= v_max THEN
        RETURN 0;
    END IF;

    v_selectivity :=
        GREATEST(
            0,
            LEAST(v_high, v_max)
            - GREATEST(v_low, v_min)
        )
        / NULLIF(v_max - v_min, 0);

    RETURN LEAST(1, GREATEST(0, v_selectivity));
END;
$$;

-- ============================================================
-- 12. FILTERED CARDINALITY ESTIMATION
-- ============================================================

CREATE OR REPLACE FUNCTION query_lab.estimate_filtered_rows(
    p_relation_id BIGINT,
    p_query_id BIGINT DEFAULT NULL
)
RETURNS NUMERIC
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_base_rows NUMERIC;
    v_selectivity NUMERIC;
    v_predicate RECORD;
BEGIN

    SELECT estimated_rows
    INTO v_base_rows
    FROM query_lab.relation_statistics
    WHERE relation_id = p_relation_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Relation statistics not found';
    END IF;

    IF p_query_id IS NULL THEN
        RETURN v_base_rows;
    END IF;

    v_selectivity := 1;

    FOR v_predicate IN
        SELECT *
        FROM query_lab.query_predicates
        WHERE query_id = p_query_id
          AND relation_id = p_relation_id
        ORDER BY predicate_id
    LOOP

        v_selectivity := v_selectivity *
            query_lab.estimate_selectivity(
                v_predicate.relation_id,
                v_predicate.column_name,
                v_predicate.operator,
                v_predicate.predicate_value,
                v_predicate.upper_value
            );

    END LOOP;

    RETURN GREATEST(
        0,
        v_base_rows * v_selectivity
    );
END;
$$;

-- ============================================================
-- 13. ACCESS PATH COST EVALUATION
-- ============================================================

CREATE OR REPLACE FUNCTION query_lab.evaluate_access_paths(
    p_query_id BIGINT,
    p_relation_id BIGINT
)
RETURNS TABLE (
    operation query_lab.plan_operation,
    estimated_rows NUMERIC,
    estimated_cost NUMERIC,
    index_name VARCHAR
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_relation query_lab.relation_statistics%ROWTYPE;
    v_config query_lab.cost_configuration%ROWTYPE;
    v_rows NUMERIC;
    v_cost NUMERIC;
    v_index RECORD;
    v_predicate RECORD;
    v_height NUMERIC;
    v_heap_pages NUMERIC;
BEGIN

    SELECT *
    INTO v_relation
    FROM query_lab.relation_statistics
    WHERE relation_id = p_relation_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown relation';
    END IF;

    SELECT *
    INTO v_config
    FROM query_lab.cost_configuration
    WHERE is_active = TRUE
    ORDER BY configuration_id
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'No active cost configuration';
    END IF;

    v_rows := query_lab.estimate_filtered_rows(
        p_relation_id,
        p_query_id
    );

    v_cost :=
        v_relation.estimated_pages
            * v_config.sequential_page_cost
        + v_relation.estimated_rows
            * v_config.cpu_tuple_cost;

    FOR v_predicate IN
        SELECT *
        FROM query_lab.query_predicates
        WHERE query_id = p_query_id
          AND relation_id = p_relation_id
    LOOP

        v_cost := v_cost +
            v_relation.estimated_rows
            * v_config.cpu_operator_cost;

    END LOOP;

    operation := 'SEQUENTIAL_SCAN';
    estimated_rows := v_rows;
    estimated_cost := v_cost;
    index_name := NULL;

    RETURN NEXT;

    FOR v_index IN
        SELECT
            i.index_name,
            i.index_pages,
            i.column_name,
            i.is_index_only
        FROM query_lab.index_statistics i
        JOIN query_lab.query_predicates p
          ON p.relation_id = i.relation_id
         AND p.column_name = i.column_name
        WHERE p.query_id = p_query_id
          AND p.relation_id = p_relation_id
          AND p.operator = 'EQUAL'
    LOOP

        v_height := GREATEST(
            1,
            CEIL(
                LN(v_index.index_pages + 1)
                / LN(2)
            )
        );

        v_heap_pages := CASE
            WHEN v_relation.estimated_rows = 0 THEN 0
            ELSE
                v_rows
                * v_relation.estimated_pages
                / v_relation.estimated_rows
        END;

        IF v_index.is_index_only THEN
            v_heap_pages := v_heap_pages * 0.1;
        END IF;

        v_cost :=
            v_height * v_config.random_page_cost
            + v_heap_pages
                * v_config.random_page_cost
                * v_config.cache_discount
            + v_rows * v_config.cpu_tuple_cost;

        operation := 'INDEX_SCAN';
        estimated_rows := v_rows;
        estimated_cost := v_cost;
        index_name := v_index.index_name;

        RETURN NEXT;

    END LOOP;

END;
$$;

-- ============================================================
-- 14. JOIN CARDINALITY ESTIMATION
-- ============================================================

CREATE OR REPLACE FUNCTION query_lab.estimate_join_rows(
    p_left_relation_id BIGINT,
    p_left_column VARCHAR,
    p_right_relation_id BIGINT,
    p_right_column VARCHAR,
    p_left_rows NUMERIC,
    p_right_rows NUMERIC
)
RETURNS NUMERIC
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_left_ndv NUMERIC;
    v_right_ndv NUMERIC;
BEGIN

    SELECT distinct_values
    INTO v_left_ndv
    FROM query_lab.column_statistics
    WHERE relation_id = p_left_relation_id
      AND column_name = p_left_column;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Missing left join statistics';
    END IF;

    SELECT distinct_values
    INTO v_right_ndv
    FROM query_lab.column_statistics
    WHERE relation_id = p_right_relation_id
      AND column_name = p_right_column;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Missing right join statistics';
    END IF;

    RETURN (
        p_left_rows * p_right_rows
    ) / GREATEST(v_left_ndv, v_right_ndv, 1);
END;
$$;

-- ============================================================
-- 15. JOIN ALGORITHM COST EVALUATION
-- ============================================================

CREATE OR REPLACE FUNCTION query_lab.evaluate_join_costs(
    p_left_cost NUMERIC,
    p_right_cost NUMERIC,
    p_left_rows NUMERIC,
    p_right_rows NUMERIC,
    p_output_rows NUMERIC
)
RETURNS TABLE (
    operation query_lab.plan_operation,
    estimated_cost NUMERIC
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_config query_lab.cost_configuration%ROWTYPE;
    v_hash_cost NUMERIC;
    v_nested_cost NUMERIC;
BEGIN

    SELECT *
    INTO v_config
    FROM query_lab.cost_configuration
    WHERE is_active = TRUE
    ORDER BY configuration_id
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No active cost configuration';
    END IF;

    v_hash_cost :=
        p_left_cost
        + p_right_cost
        + LEAST(p_left_rows, p_right_rows)
            * v_config.hash_build_cost
        + GREATEST(p_left_rows, p_right_rows)
            * v_config.cpu_operator_cost
        + (p_left_rows + p_right_rows)
            * v_config.cpu_tuple_cost;

    v_nested_cost :=
        p_left_cost
        + p_right_cost
        + p_left_rows
            * p_right_rows
            * v_config.nested_loop_cost
        + p_output_rows
            * v_config.cpu_tuple_cost;

    operation := 'HASH_JOIN';
    estimated_cost := v_hash_cost;
    RETURN NEXT;

    operation := 'NESTED_LOOP';
    estimated_cost := v_nested_cost;
    RETURN NEXT;

END;
$$;

-- ============================================================
-- 16. STATISTICS REFRESH PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE query_lab.refresh_relation_statistics(
    p_relation_name VARCHAR,
    p_estimated_rows BIGINT,
    p_estimated_pages BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN

    IF p_estimated_rows < 0 OR p_estimated_pages < 0 THEN
        RAISE EXCEPTION
            'Statistics cannot contain negative values';
    END IF;

    IF p_estimated_rows > 0 AND p_estimated_pages = 0 THEN
        RAISE EXCEPTION
            'Nonempty relations require at least one page';
    END IF;

    UPDATE query_lab.relation_statistics
    SET
        estimated_rows = p_estimated_rows,
        estimated_pages = p_estimated_pages,
        analyzed_at = NOW()
    WHERE relation_name = p_relation_name;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Relation not registered: %',
            p_relation_name;
    END IF;

END;
$$;

-- ============================================================
-- 17. PLAN RANKING VIEW
-- ============================================================

CREATE OR REPLACE VIEW query_lab.v_plan_ranking AS
SELECT
    p.plan_id,
    p.query_id,
    q.query_name,
    p.operation,
    p.estimated_rows,
    p.estimated_cost,
    p.plan_details,
    p.is_selected,
    RANK() OVER (
        PARTITION BY p.query_id
        ORDER BY p.estimated_cost
    ) AS cost_rank
FROM query_lab.execution_plan_candidates p
JOIN query_lab.query_workload q
    ON q.query_id = p.query_id;

-- ============================================================
-- 18. STATISTICS FRESHNESS VIEW
-- ============================================================

CREATE OR REPLACE VIEW query_lab.v_statistics_health AS
SELECT
    relation_id,
    relation_name,
    estimated_rows,
    estimated_pages,
    analyzed_at,
    NOW() - analyzed_at AS statistics_age,
    CASE
        WHEN analyzed_at < NOW() - INTERVAL '24 hours'
            THEN 'STALE'
        ELSE 'FRESH'
    END AS statistics_status
FROM query_lab.relation_statistics;

-- ============================================================
-- 19. SAMPLE RELATION STATISTICS
-- ============================================================

INSERT INTO query_lab.relation_statistics (
    relation_name,
    estimated_rows,
    estimated_pages
)
VALUES
    ('customers', 100000, 1000),
    ('orders', 1000000, 12000),
    ('payments', 850000, 9000);

-- ============================================================
-- 20. SAMPLE COLUMN STATISTICS
-- ============================================================

INSERT INTO query_lab.column_statistics (
    relation_id,
    column_name,
    distinct_values,
    null_fraction,
    most_common_values,
    histogram_boundaries
)
SELECT
    r.relation_id,
    data.column_name,
    data.distinct_values,
    data.null_fraction,
    data.mcv,
    data.histogram
FROM (
    VALUES
    (
        'customers',
        'customer_id',
        100000::BIGINT,
        0.0::NUMERIC,
        '{}'::JSONB,
        NULL::NUMERIC[]
    ),
    (
        'customers',
        'region',
        10::BIGINT,
        0.0::NUMERIC,
        '{"North":0.35,"South":0.25,"East":0.20,"West":0.15}'::JSONB,
        NULL::NUMERIC[]
    ),
    (
        'orders',
        'order_id',
        1000000::BIGINT,
        0.0::NUMERIC,
        '{}'::JSONB,
        NULL::NUMERIC[]
    ),
    (
        'orders',
        'customer_id',
        100000::BIGINT,
        0.0::NUMERIC,
        '{}'::JSONB,
        NULL::NUMERIC[]
    ),
    (
        'orders',
        'status',
        4::BIGINT,
        0.0::NUMERIC,
        '{"COMPLETED":0.65,"PENDING":0.20,"CANCELLED":0.10,"FAILED":0.05}'::JSONB,
        NULL::NUMERIC[]
    ),
    (
        'orders',
        'amount',
        50000::BIGINT,
        0.0::NUMERIC,
        '{}'::JSONB,
        ARRAY[0,100,250,500,1000,5000,10000]::NUMERIC[]
    ),
    (
        'payments',
        'payment_id',
        850000::BIGINT,
        0.0::NUMERIC,
        '{}'::JSONB,
        NULL::NUMERIC[]
    ),
    (
        'payments',
        'order_id',
        800000::BIGINT,
        0.0::NUMERIC,
        '{}'::JSONB,
        NULL::NUMERIC[]
    ),
    (
        'payments',
        'payment_status',
        3::BIGINT,
        0.0::NUMERIC,
        '{"SUCCESS":0.80,"PENDING":0.15,"FAILED":0.05}'::JSONB,
        NULL::NUMERIC[]
    )
) AS data(
    relation_name,
    column_name,
    distinct_values,
    null_fraction,
    mcv,
    histogram
)
JOIN query_lab.relation_statistics r
    ON r.relation_name = data.relation_name;

-- ============================================================
-- 21. SAMPLE INDEX STATISTICS
-- ============================================================

INSERT INTO query_lab.index_statistics (
    relation_id,
    column_name,
    index_name,
    index_pages,
    is_unique,
    is_index_only
)
SELECT
    r.relation_id,
    data.column_name,
    data.index_name,
    data.index_pages,
    data.is_unique,
    data.is_index_only
FROM (
    VALUES
    ('customers', 'customer_id', 'idx_customers_id', 250::BIGINT, TRUE, FALSE),
    ('customers', 'region', 'idx_customers_region', 80::BIGINT, FALSE, FALSE),
    ('orders', 'customer_id', 'idx_orders_customer', 2000::BIGINT, FALSE, FALSE),
    ('orders', 'status', 'idx_orders_status', 500::BIGINT, FALSE, FALSE),
    ('orders', 'order_id', 'idx_orders_id', 2500::BIGINT, TRUE, FALSE),
    ('payments', 'order_id', 'idx_payments_order', 1800::BIGINT, FALSE, FALSE),
    ('payments', 'payment_id', 'idx_payments_id', 2000::BIGINT, TRUE, FALSE)
) AS data(
    relation_name,
    column_name,
    index_name,
    index_pages,
    is_unique,
    is_index_only
)
JOIN query_lab.relation_statistics r
    ON r.relation_name = data.relation_name;

-- ============================================================
-- 22. SAMPLE QUERY WORKLOAD
-- ============================================================

INSERT INTO query_lab.query_workload (
    query_name,
    description,
    state,
    submitted_by
)
VALUES
(
    'regional_completed_orders',
    'Retrieve completed orders and successful payments for North region customers.',
    'DRAFT',
    'query_engine'
),
(
    'full_order_history',
    'Retrieve the complete order and payment history.',
    'DRAFT',
    'reporting_service'
),
(
    'invalid_range_test',
    'Validation test for an invalid range predicate.',
    'FAILED',
    'test_runner'
);

INSERT INTO query_lab.query_relations (
    query_id,
    relation_id,
    execution_order
)
SELECT
    q.query_id,
    r.relation_id,
    CASE r.relation_name
        WHEN 'customers' THEN 1
        WHEN 'orders' THEN 2
        WHEN 'payments' THEN 3
    END
FROM query_lab.query_workload q
CROSS JOIN query_lab.relation_statistics r
WHERE q.query_name = 'regional_completed_orders'
  AND r.relation_name IN (
      'customers',
      'orders',
      'payments'
  );

INSERT INTO query_lab.query_relations (
    query_id,
    relation_id,
    execution_order
)
SELECT
    q.query_id,
    r.relation_id,
    CASE r.relation_name
        WHEN 'orders' THEN 1
        WHEN 'payments' THEN 2
    END
FROM query_lab.query_workload q
CROSS JOIN query_lab.relation_statistics r
WHERE q.query_name = 'full_order_history'
  AND r.relation_name IN (
      'orders',
      'payments'
  );

-- ============================================================
-- 23. SAMPLE PREDICATES
-- ============================================================

INSERT INTO query_lab.query_predicates (
    query_id,
    relation_id,
    column_name,
    operator,
    predicate_value,
    upper_value
)
SELECT
    q.query_id,
    r.relation_id,
    data.column_name,
    data.operator,
    data.predicate_value,
    data.upper_value
FROM (
    VALUES
    (
        'customers',
        'region',
        'EQUAL'::query_lab.predicate_operator,
        'North'::TEXT,
        NULL::NUMERIC
    ),
    (
        'orders',
        'status',
        'EQUAL'::query_lab.predicate_operator,
        'COMPLETED'::TEXT,
        NULL::NUMERIC
    ),
    (
        'orders',
        'amount',
        'BETWEEN'::query_lab.predicate_operator,
        '100'::TEXT,
        1000::NUMERIC
    ),
    (
        'payments',
        'payment_status',
        'EQUAL'::query_lab.predicate_operator,
        'SUCCESS'::TEXT,
        NULL::NUMERIC
    )
) AS data(
    relation_name,
    column_name,
    operator,
    predicate_value,
    upper_value
)
JOIN query_lab.query_workload q
    ON q.query_name = 'regional_completed_orders'
JOIN query_lab.relation_statistics r
    ON r.relation_name = data.relation_name;

-- ============================================================
-- 24. SAMPLE JOIN CONDITIONS
-- ============================================================

INSERT INTO query_lab.query_joins (
    query_id,
    left_relation_id,
    left_column,
    right_relation_id,
    right_column
)
SELECT
    q.query_id,
    left_relation.relation_id,
    'customer_id',
    right_relation.relation_id,
    'customer_id'
FROM query_lab.query_workload q
JOIN query_lab.relation_statistics left_relation
    ON left_relation.relation_name = 'customers'
JOIN query_lab.relation_statistics right_relation
    ON right_relation.relation_name = 'orders'
WHERE q.query_name = 'regional_completed_orders';

INSERT INTO query_lab.query_joins (
    query_id,
    left_relation_id,
    left_column,
    right_relation_id,
    right_column
)
SELECT
    q.query_id,
    left_relation.relation_id,
    'order_id',
    right_relation.relation_id,
    'order_id'
FROM query_lab.query_workload q
JOIN query_lab.relation_statistics left_relation
    ON left_relation.relation_name = 'orders'
JOIN query_lab.relation_statistics right_relation
    ON right_relation.relation_name = 'payments'
WHERE q.query_name = 'regional_completed_orders';

-- ============================================================
-- 25. SAMPLE ACCESS PATH CANDIDATES
-- ============================================================

INSERT INTO query_lab.execution_plan_candidates (
    query_id,
    operation,
    relation_id,
    estimated_rows,
    estimated_cost,
    plan_details
)
SELECT
    q.query_id,
    candidate.operation,
    candidate.relation_id,
    candidate.estimated_rows,
    candidate.estimated_cost,
    jsonb_build_object(
        'index_name',
        candidate.index_name,
        'method',
        'cost_based_access_path'
    )
FROM query_lab.query_workload q
JOIN query_lab.query_relations qr
    ON qr.query_id = q.query_id
CROSS JOIN LATERAL query_lab.evaluate_access_paths(
    q.query_id,
    qr.relation_id
) AS candidate
WHERE q.query_name = 'regional_completed_orders';

-- ============================================================
-- 26. WORKLOAD VALIDATION
-- ============================================================

UPDATE query_lab.query_workload q
SET state = 'VALIDATED'
WHERE q.query_name = 'regional_completed_orders'
AND NOT EXISTS (
    SELECT 1
    FROM query_lab.query_relations qr
    WHERE qr.query_id = q.query_id
    GROUP BY qr.query_id
    HAVING COUNT(*) = 0
);

-- ============================================================
-- 27. SELECT THE LOWEST-COST ACCESS PATH
-- ============================================================

WITH ranked_candidates AS (
    SELECT
        plan_id,
        query_id,
        ROW_NUMBER() OVER (
            PARTITION BY query_id, relation_id
            ORDER BY estimated_cost, plan_id
        ) AS position
    FROM query_lab.execution_plan_candidates
)
UPDATE query_lab.execution_plan_candidates p
SET is_selected = (r.position = 1)
FROM ranked_candidates r
WHERE p.plan_id = r.plan_id;

-- ============================================================
-- 28. OPTIMIZATION RESULTS
-- ============================================================

INSERT INTO query_lab.optimization_results (
    query_id,
    selected_plan_id,
    estimated_total_cost,
    estimated_output_rows,
    optimization_method,
    statistics_revision
)
SELECT
    p.query_id,
    p.plan_id,
    p.estimated_cost,
    p.estimated_rows,
    'LOWEST_COST_ACCESS_PATH',
    MAX(r.analyzed_at)
FROM query_lab.execution_plan_candidates p
JOIN query_lab.relation_statistics r
    ON r.relation_id = p.relation_id
WHERE p.is_selected = TRUE
GROUP BY
    p.query_id,
    p.plan_id,
    p.estimated_cost,
    p.estimated_rows;

UPDATE query_lab.query_workload
SET
    state = 'OPTIMIZED',
    optimized_at = NOW()
WHERE query_name = 'regional_completed_orders';

COMMIT;

-- ============================================================
-- 29. RETRIEVAL QUERIES
-- ============================================================

-- Registered relations and estimated physical size.

SELECT
    relation_name,
    estimated_rows,
    estimated_pages,
    analyzed_at
FROM query_lab.relation_statistics
ORDER BY estimated_rows DESC;

-- Column statistics and distributions.

SELECT
    r.relation_name,
    c.column_name,
    c.distinct_values,
    c.null_fraction,
    c.most_common_values,
    c.histogram_boundaries
FROM query_lab.column_statistics c
JOIN query_lab.relation_statistics r
    ON r.relation_id = c.relation_id
ORDER BY r.relation_name, c.column_name;

-- Index catalog.

SELECT
    r.relation_name,
    i.index_name,
    i.column_name,
    i.index_pages,
    i.is_unique,
    i.is_index_only
FROM query_lab.index_statistics i
JOIN query_lab.relation_statistics r
    ON r.relation_id = i.relation_id
ORDER BY r.relation_name;

-- ============================================================
-- 30. VALIDATION QUERIES
-- ============================================================

-- Detect missing column statistics.

SELECT
    r.relation_name,
    i.column_name,
    i.index_name
FROM query_lab.index_statistics i
JOIN query_lab.relation_statistics r
    ON r.relation_id = i.relation_id
LEFT JOIN query_lab.column_statistics c
    ON c.relation_id = i.relation_id
   AND c.column_name = i.column_name
WHERE c.column_statistics_id IS NULL;

-- Detect stale statistics.

SELECT *
FROM query_lab.v_statistics_health
WHERE statistics_status = 'STALE';

-- Detect relations with zero or inconsistent estimates.

SELECT *
FROM query_lab.relation_statistics
WHERE estimated_rows < 0
   OR estimated_pages < 0
   OR (
       estimated_rows > 0
       AND estimated_pages = 0
   );

-- ============================================================
-- 31. CARDINALITY ESTIMATION QUERIES
-- ============================================================

SELECT
    r.relation_name,
    c.column_name,
    query_lab.estimate_selectivity(
        r.relation_id,
        c.column_name,
        'EQUAL',
        'North'
    ) AS estimated_selectivity
FROM query_lab.relation_statistics r
JOIN query_lab.column_statistics c
    ON c.relation_id = r.relation_id
WHERE r.relation_name = 'customers'
  AND c.column_name = 'region';

-- Estimated rows after all query predicates.

SELECT
    q.query_name,
    r.relation_name,
    query_lab.estimate_filtered_rows(
        r.relation_id,
        q.query_id
    ) AS estimated_filtered_rows
FROM query_lab.query_workload q
JOIN query_lab.query_relations qr
    ON qr.query_id = q.query_id
JOIN query_lab.relation_statistics r
    ON r.relation_id = qr.relation_id
WHERE q.query_name = 'regional_completed_orders'
ORDER BY qr.execution_order;

-- ============================================================
-- 32. ACCESS PATH REPORTING
-- ============================================================

SELECT
    q.query_name,
    r.relation_name,
    candidate.operation,
    candidate.estimated_rows,
    candidate.estimated_cost,
    candidate.index_name
FROM query_lab.query_workload q
JOIN query_lab.query_relations qr
    ON qr.query_id = q.query_id
JOIN query_lab.relation_statistics r
    ON r.relation_id = qr.relation_id
CROSS JOIN LATERAL query_lab.evaluate_access_paths(
    q.query_id,
    r.relation_id
) candidate
WHERE q.query_name = 'regional_completed_orders'
ORDER BY
    r.relation_name,
    candidate.estimated_cost;

-- ============================================================
-- 33. JOIN ESTIMATION REPORT
-- ============================================================

SELECT
    q.query_name,
    left_relation.relation_name AS left_relation,
    j.left_column,
    right_relation.relation_name AS right_relation,
    j.right_column,
    query_lab.estimate_join_rows(
        j.left_relation_id,
        j.left_column,
        j.right_relation_id,
        j.right_column,
        query_lab.estimate_filtered_rows(
            j.left_relation_id,
            q.query_id
        ),
        query_lab.estimate_filtered_rows(
            j.right_relation_id,
            q.query_id
        )
    ) AS estimated_join_rows
FROM query_lab.query_joins j
JOIN query_lab.query_workload q
    ON q.query_id = j.query_id
JOIN query_lab.relation_statistics left_relation
    ON left_relation.relation_id = j.left_relation_id
JOIN query_lab.relation_statistics right_relation
    ON right_relation.relation_id = j.right_relation_id
WHERE q.query_name = 'regional_completed_orders';

-- ============================================================
-- 34. JOIN ALGORITHM COMPARISON
-- ============================================================

SELECT *
FROM query_lab.evaluate_join_costs(
    120.0,
    90.0,
    35000,
    650000,
    227500
)
ORDER BY estimated_cost;

-- ============================================================
-- 35. COST-BASED PLAN REPORT
-- ============================================================

SELECT
    query_name,
    plan_id,
    operation,
    estimated_rows,
    estimated_cost,
    cost_rank,
    is_selected
FROM query_lab.v_plan_ranking
WHERE query_name = 'regional_completed_orders'
ORDER BY cost_rank, plan_id;

-- ============================================================
-- 36. AGGREGATION REPORT
-- ============================================================

SELECT
    q.query_name,
    p.operation,
    COUNT(*) AS candidate_count,
    MIN(p.estimated_cost) AS minimum_cost,
    MAX(p.estimated_cost) AS maximum_cost,
    AVG(p.estimated_cost) AS average_cost
FROM query_lab.execution_plan_candidates p
JOIN query_lab.query_workload q
    ON q.query_id = p.query_id
GROUP BY
    q.query_name,
    p.operation
ORDER BY q.query_name, p.operation;

-- ============================================================
-- 37. QUERY WORKLOAD STATUS
-- ============================================================

SELECT
    state,
    COUNT(*) AS query_count
FROM query_lab.query_workload
GROUP BY state
ORDER BY state;

-- ============================================================
-- 38. OPTIMIZATION HISTORY
-- ============================================================

SELECT
    q.query_name,
    o.optimization_method,
    o.estimated_total_cost,
    o.estimated_output_rows,
    o.optimized_at
FROM query_lab.optimization_results o
JOIN query_lab.query_workload q
    ON q.query_id = o.query_id
ORDER BY o.optimized_at DESC;

-- ============================================================
-- 39. ELIGIBILITY DETERMINATION
-- ============================================================

-- A query is eligible for plan selection when:
-- 1. It has validated query relations.
-- 2. Every referenced relation has statistics.
-- 3. Every predicate has corresponding column statistics.
-- 4. An active cost configuration exists.
-- 5. At least one candidate plan is available.

SELECT
    q.query_id,
    q.query_name,
    CASE
        WHEN q.state = 'FAILED'
            THEN 'INELIGIBLE'
        WHEN NOT EXISTS (
            SELECT 1
            FROM query_lab.query_relations qr
            WHERE qr.query_id = q.query_id
        )
            THEN 'INELIGIBLE'
        WHEN NOT EXISTS (
            SELECT 1
            FROM query_lab.execution_plan_candidates p
            WHERE p.query_id = q.query_id
        )
            THEN 'INELIGIBLE'
        WHEN NOT EXISTS (
            SELECT 1
            FROM query_lab.cost_configuration
            WHERE is_active = TRUE
        )
            THEN 'INELIGIBLE'
        ELSE 'ELIGIBLE'
    END AS optimization_eligibility
FROM query_lab.query_workload q
ORDER BY q.query_id;

-- ============================================================
-- 40. TRANSACTIONAL STATISTICS UPDATE EXAMPLE
-- ============================================================

BEGIN;

CALL query_lab.refresh_relation_statistics(
    'customers',
    105000,
    1050
);

-- Verify the changed statistics before committing.

SELECT
    relation_name,
    estimated_rows,
    estimated_pages,
    analyzed_at
FROM query_lab.relation_statistics
WHERE relation_name = 'customers';

COMMIT;

-- ============================================================
-- 41. FINAL SYSTEM REPORT
-- ============================================================

SELECT
    'RELATIONS' AS metric,
    COUNT(*)::TEXT AS metric_value
FROM query_lab.relation_statistics

UNION ALL

SELECT
    'COLUMN STATISTICS',
    COUNT(*)::TEXT
FROM query_lab.column_statistics

UNION ALL

SELECT
    'INDEXES',
    COUNT(*)::TEXT
FROM query_lab.index_statistics

UNION ALL

SELECT
    'QUERIES',
    COUNT(*)::TEXT
FROM query_lab.query_workload

UNION ALL

SELECT
    'PLAN CANDIDATES',
    COUNT(*)::TEXT
FROM query_lab.execution_plan_candidates

UNION ALL

SELECT
    'OPTIMIZATION RESULTS',
    COUNT(*)::TEXT
FROM query_lab.optimization_results;
