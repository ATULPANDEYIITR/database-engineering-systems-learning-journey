/*
 * INDEX INTERNALS
 * B-trees, tree traversal, index pages, and PostgreSQL diagnostics.
 *
 * Requires PostgreSQL 14 or later.
 *
 * Demonstrates:
 * - B-tree index structure and database index metadata.
 * - Index creation and index-page inspection.
 * - Composite and partial indexes.
 * - Index traversal through EXPLAIN.
 * - Index-only scans and visibility maps.
 * - Page inspection using pageinspect when installed.
 * - Index maintenance and integrity reporting.
 * - Transactional record modifications.
 *
 * PostgreSQL indexes are managed by the database engine.
 * The sample B-tree page hierarchy is therefore inspected through
 * system catalogs and optional pageinspect functions rather than
 * manually maintaining database index pages.
 */

BEGIN;

CREATE SCHEMA IF NOT EXISTS index_lab;

SET search_path TO index_lab, public;

DROP VIEW IF EXISTS v_index_usage_report CASCADE;
DROP VIEW IF EXISTS v_customer_order_summary CASCADE;
DROP TABLE IF EXISTS index_audit CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS index_config CASCADE;

CREATE TABLE customers (
    customer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_name VARCHAR(120) NOT NULL,
    email VARCHAR(180) NOT NULL UNIQUE,
    region VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_customer_status
        CHECK (status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')),

    CONSTRAINT chk_customer_name
        CHECK (length(trim(customer_name)) > 0)
);

CREATE TABLE orders (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    order_number VARCHAR(40) NOT NULL UNIQUE,
    order_date DATE NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    description TEXT,

    CONSTRAINT fk_order_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_order_amount
        CHECK (amount >= 0),

    CONSTRAINT chk_order_status
        CHECK (
            status IN (
                'PENDING',
                'PROCESSING',
                'COMPLETED',
                'CANCELLED'
            )
        )
);

CREATE TABLE index_config (
    config_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    index_name TEXT NOT NULL UNIQUE,
    table_name TEXT NOT NULL,
    indexed_columns TEXT NOT NULL,
    index_purpose TEXT NOT NULL,
    fillfactor SMALLINT NOT NULL DEFAULT 90,

    CONSTRAINT chk_fillfactor
        CHECK (fillfactor BETWEEN 10 AND 100)
);

CREATE TABLE index_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    operation VARCHAR(20) NOT NULL,
    table_name TEXT NOT NULL,
    affected_record_id BIGINT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    transaction_id BIGINT NOT NULL DEFAULT txid_current()
);

-- PostgreSQL B-tree indexes maintain sorted keys and page pointers.
-- The primary-key and unique constraints also create indexes.

CREATE INDEX idx_customers_region_status
    ON customers USING BTREE (region, status);

CREATE INDEX idx_customers_created
    ON customers USING BTREE (created_at DESC);

CREATE INDEX idx_orders_customer_date
    ON orders USING BTREE (customer_id, order_date DESC);

CREATE INDEX idx_orders_date
    ON orders USING BTREE (order_date);

CREATE INDEX idx_orders_amount
    ON orders USING BTREE (amount)
    WHERE status = 'COMPLETED';

CREATE INDEX idx_orders_customer_covering
    ON orders USING BTREE (customer_id)
    INCLUDE (order_date, amount, status);

INSERT INTO index_config (
    index_name,
    table_name,
    indexed_columns,
    index_purpose,
    fillfactor
)
VALUES
(
    'customers_pkey',
    'customers',
    'customer_id',
    'Unique customer lookup',
    90
),
(
    'customers_email_key',
    'customers',
    'email',
    'Unique email lookup',
    90
),
(
    'idx_customers_region_status',
    'customers',
    'region, status',
    'Regional customer filtering',
    90
),
(
    'idx_orders_customer_date',
    'orders',
    'customer_id, order_date DESC',
    'Customer order history',
    85
),
(
    'idx_orders_amount',
    'orders',
    'amount WHERE status = COMPLETED',
    'Completed order amount filtering',
    90
);

INSERT INTO customers (
    customer_name,
    email,
    region,
    status
)
VALUES
('Aarav Sharma', 'aarav@example.com', 'NORTH', 'ACTIVE'),
('Diya Verma', 'diya@example.com', 'SOUTH', 'ACTIVE'),
('Kabir Singh', 'kabir@example.com', 'WEST', 'ACTIVE'),
('Meera Gupta', 'meera@example.com', 'EAST', 'INACTIVE'),
('Rohan Kumar', 'rohan@example.com', 'NORTH', 'ACTIVE'),
('Ananya Das', 'ananya@example.com', 'EAST', 'SUSPENDED'),
('Ishaan Patel', 'ishaan@example.com', 'WEST', 'ACTIVE'),
('Sara Khan', 'sara@example.com', 'SOUTH', 'ACTIVE');

INSERT INTO orders (
    customer_id,
    order_number,
    order_date,
    amount,
    status,
    description
)
SELECT
    c.customer_id,
    'ORD-' || lpad(n::TEXT, 5, '0'),
    DATE '2026-01-01' + (n % 300),
    (500 + n * 125)::NUMERIC(12, 2),
    CASE
        WHEN n % 5 = 0 THEN 'CANCELLED'
        WHEN n % 3 = 0 THEN 'PENDING'
        ELSE 'COMPLETED'
    END,
    'Customer order record ' || n
FROM generate_series(1, 120) AS n
JOIN customers c
    ON c.customer_id = ((n - 1) % 8) + 1;

-- Audit trigger for data modifications.

CREATE OR REPLACE FUNCTION audit_order_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO index_audit (
        operation,
        table_name,
        affected_record_id
    )
    VALUES (
        TG_OP,
        TG_TABLE_NAME,
        CASE
            WHEN TG_OP = 'DELETE' THEN OLD.order_id
            ELSE NEW.order_id
        END
    );

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_orders_audit
AFTER INSERT OR UPDATE OR DELETE
ON orders
FOR EACH ROW
EXECUTE FUNCTION audit_order_change();

-- Index usage view combines catalog information and workload counters.
-- Statistics are cumulative since the last statistics reset.

CREATE OR REPLACE VIEW v_index_usage_report AS
SELECT
    schemaname,
    relname AS table_name,
    indexrelname AS index_name,
    idx_scan AS index_scans,
    idx_tup_read AS index_tuples_read,
    idx_tup_fetch AS index_tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    pg_relation_size(indexrelid) AS index_size_bytes
FROM pg_stat_user_indexes
WHERE schemaname = 'index_lab';

CREATE OR REPLACE VIEW v_customer_order_summary AS
SELECT
    c.customer_id,
    c.customer_name,
    c.region,
    COUNT(o.order_id) AS order_count,
    COALESCE(SUM(o.amount), 0) AS total_amount,
    COUNT(*) FILTER (
        WHERE o.status = 'COMPLETED'
    ) AS completed_orders
FROM customers c
LEFT JOIN orders o
    ON o.customer_id = c.customer_id
GROUP BY
    c.customer_id,
    c.customer_name,
    c.region;

COMMIT;

-- 1. Retrieve index definitions and access methods.

SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'index_lab'
ORDER BY tablename, indexname;

-- 2. Inspect index metadata and B-tree access method.

SELECT
    ns.nspname AS schema_name,
    tbl.relname AS table_name,
    idx.relname AS index_name,
    am.amname AS access_method,
    pg_get_indexdef(idx.oid) AS definition,
    pg_size_pretty(pg_relation_size(idx.oid)) AS index_size
FROM pg_index i
JOIN pg_class idx
    ON idx.oid = i.indexrelid
JOIN pg_class tbl
    ON tbl.oid = i.indrelid
JOIN pg_namespace ns
    ON ns.oid = tbl.relnamespace
JOIN pg_am am
    ON am.oid = idx.relam
WHERE ns.nspname = 'index_lab'
ORDER BY tbl.relname, idx.relname;

-- 3. Inspect the B-tree hierarchy using the planner.

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT
    customer_id,
    customer_name,
    email
FROM customers
WHERE customer_id = 3;

-- 4. Composite index retrieval.
-- The leading customer_id column supports this access pattern.

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    order_id,
    order_date,
    amount
FROM orders
WHERE customer_id = 3
ORDER BY order_date DESC;

-- 5. Range retrieval using an indexed numeric column.

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    order_id,
    amount,
    status
FROM orders
WHERE amount BETWEEN 3000 AND 10000;

-- 6. Partial index eligibility.

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    order_id,
    amount
FROM orders
WHERE status = 'COMPLETED'
  AND amount >= 5000;

-- 7. Covering index and index-only scan candidate.
-- Actual index-only execution depends on visibility-map coverage.

VACUUM (ANALYZE) index_lab.orders;

EXPLAIN (ANALYZE, BUFFERS)
SELECT
    customer_id,
    order_date,
    amount,
    status
FROM orders
WHERE customer_id = 2;

-- 8. Aggregation and reporting.

SELECT *
FROM v_customer_order_summary
ORDER BY total_amount DESC;

-- 9. Index usage reporting.

SELECT *
FROM v_index_usage_report
ORDER BY table_name, index_name;

-- 10. Page counts and physical relation information.

SELECT
    c.relname AS relation_name,
    c.relkind AS relation_type,
    c.relpages AS estimated_pages,
    c.reltuples AS estimated_rows,
    pg_relation_size(c.oid) AS relation_bytes,
    pg_size_pretty(pg_relation_size(c.oid)) AS relation_size
FROM pg_class c
JOIN pg_namespace n
    ON n.oid = c.relnamespace
WHERE n.nspname = 'index_lab'
ORDER BY pg_relation_size(c.oid) DESC;

-- 11. Check index validity and readiness.

SELECT
    tbl.relname AS table_name,
    idx.relname AS index_name,
    i.indisvalid AS is_valid,
    i.indisready AS is_ready,
    i.indisunique AS is_unique,
    i.indisprimary AS is_primary,
    i.indisclustered AS is_clustered
FROM pg_index i
JOIN pg_class idx
    ON idx.oid = i.indexrelid
JOIN pg_class tbl
    ON tbl.oid = i.indrelid
JOIN pg_namespace n
    ON n.oid = tbl.relnamespace
WHERE n.nspname = 'index_lab'
ORDER BY tbl.relname, idx.relname;

-- 12. Validate index configuration records.

SELECT
    config_id,
    index_name,
    table_name,
    indexed_columns,
    index_purpose,
    fillfactor
FROM index_config
ORDER BY config_id;

-- 13. Demonstrate transactional index-related data changes.

BEGIN;

INSERT INTO orders (
    customer_id,
    order_number,
    order_date,
    amount,
    status,
    description
)
VALUES (
    1,
    'ORD-90001',
    CURRENT_DATE,
    12500.00,
    'COMPLETED',
    'Transactional test order'
);

SAVEPOINT before_invalid_change;

-- The following update is rejected by the amount check constraint.
-- The exception is handled in a PL/pgSQL block so the transaction
-- can continue after the failed statement's subtransaction rolls back.

DO $$
BEGIN
    BEGIN
        UPDATE index_lab.orders
        SET amount = -100
        WHERE order_number = 'ORD-90001';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'Negative order amount rejected';
    END;
END;
$$;

SELECT
    order_number,
    amount,
    status
FROM index_lab.orders
WHERE order_number = 'ORD-90001';

ROLLBACK;

-- 14. Workflow validation and eligibility reporting.

SELECT
    c.customer_id,
    c.customer_name,
    c.status,
    COUNT(o.order_id) AS total_orders,
    COUNT(*) FILTER (
        WHERE o.status = 'COMPLETED'
    ) AS completed_orders,
    CASE
        WHEN c.status = 'ACTIVE'
         AND COUNT(o.order_id) > 0
        THEN 'ELIGIBLE'
        ELSE 'NOT_ELIGIBLE'
    END AS customer_eligibility
FROM index_lab.customers c
LEFT JOIN index_lab.orders o
    ON o.customer_id = c.customer_id
GROUP BY
    c.customer_id,
    c.customer_name,
    c.status
ORDER BY c.customer_id;

-- 15. Index audit records.

SELECT
    audit_id,
    operation,
    table_name,
    affected_record_id,
    event_time,
    transaction_id
FROM index_lab.index_audit
ORDER BY audit_id;

-- 16. Optional physical B-tree page inspection.
--
-- pageinspect must be installed by a database administrator.
-- The extension is created only when it is available and permitted.
--
-- The following block checks for the extension before attempting
-- to inspect physical B-tree pages.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_available_extensions
        WHERE name = 'pageinspect'
    ) THEN
        CREATE EXTENSION IF NOT EXISTS pageinspect;
        RAISE NOTICE 'pageinspect is available';
    ELSE
        RAISE NOTICE 'pageinspect is not installed';
    END IF;
END;
$$;

-- Run the following statements separately if pageinspect is installed
-- and the executing role has the required permissions:
--
-- SELECT *
-- FROM bt_metap('index_lab.idx_orders_customer_date');
--
-- SELECT *
-- FROM bt_page_stats(
--     'index_lab.idx_orders_customer_date',
--     1
-- );
--
-- SELECT *
-- FROM bt_page_items(
--     'index_lab.idx_orders_customer_date',
--     1
-- );
--
-- Page 1 is not guaranteed to exist as a leaf or internal page.
-- Use bt_metap to identify the root block and inspect valid block
-- numbers obtained from the index's physical page layout.
--
-- Physical page inspection is PostgreSQL-version-specific and may
-- require elevated privileges.

-- 17. Maintenance and planner statistics.

ANALYZE index_lab.customers;
ANALYZE index_lab.orders;

-- REINDEX rebuilds an index and can require significant resources.
-- REINDEX INDEX index_lab.idx_orders_customer_date;

-- 18. Verify the final table and index inventory.

SELECT
    current_database() AS database_name,
    current_schema() AS current_schema,
    COUNT(*) AS customer_count
FROM index_lab.customers;

SELECT
    COUNT(*) AS order_count,
    SUM(amount) AS total_order_value
FROM index_lab.orders;

SELECT
    COUNT(*) AS index_count
FROM pg_indexes
WHERE schemaname = 'index_lab';
