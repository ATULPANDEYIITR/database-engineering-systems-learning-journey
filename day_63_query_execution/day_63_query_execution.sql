DROP SCHEMA IF EXISTS query_execution_demo CASCADE;

CREATE SCHEMA query_execution_demo;

SET search_path = query_execution_demo, public;

-- Repository-like relational data is represented as customers and orders.
CREATE TABLE customers (
    customer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_name TEXT NOT NULL CHECK (length(trim(customer_name)) > 0),
    status TEXT NOT NULL CHECK (status IN ('active', 'inactive'))
);

CREATE TABLE orders (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL
        REFERENCES customers(customer_id),
    order_total NUMERIC(12, 2) NOT NULL
        CHECK (order_total >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customers_status
    ON customers(status);

CREATE INDEX idx_orders_customer_id
    ON orders(customer_id);

CREATE INDEX idx_orders_total
    ON orders(order_total);

INSERT INTO customers (customer_name, status)
VALUES
    ('Asha', 'active'),
    ('Bharat', 'active'),
    ('Chen', 'inactive'),
    ('Divya', 'active');

INSERT INTO orders (customer_id, order_total)
SELECT customer_id, order_total
FROM (
    VALUES
        (1::BIGINT, 450.00::NUMERIC),
        (1::BIGINT, 1200.00::NUMERIC),
        (2::BIGINT, 900.00::NUMERIC),
        (3::BIGINT, 2500.00::NUMERIC),
        (4::BIGINT, 1750.00::NUMERIC)
) AS sample(customer_id, order_total);

-- A view exposes the logical result independently of a particular plan.
CREATE VIEW active_customer_orders AS
SELECT
    c.customer_id,
    c.customer_name,
    o.order_id,
    o.order_total,
    o.created_at
FROM customers AS c
JOIN orders AS o
    ON o.customer_id = c.customer_id
WHERE c.status = 'active';

-- Query 1: basic retrieval with filtering and ordering.
SELECT
    customer_id,
    customer_name,
    order_id,
    order_total
FROM active_customer_orders
WHERE order_total >= 800
ORDER BY order_total DESC
LIMIT 3;

-- Query 2: aggregation demonstrates a hash/group aggregate candidate.
SELECT
    c.status,
    COUNT(*) AS order_count,
    SUM(o.order_total) AS total_value,
    AVG(o.order_total) AS average_value
FROM customers AS c
JOIN orders AS o
    ON o.customer_id = c.customer_id
GROUP BY c.status
ORDER BY total_value DESC;

-- Query 3: CTE separates logical filtering from result generation.
WITH eligible_orders AS (
    SELECT
        c.customer_id,
        c.customer_name,
        o.order_id,
        o.order_total
    FROM customers AS c
    JOIN orders AS o
        ON o.customer_id = c.customer_id
    WHERE c.status = 'active'
      AND o.order_total >= 800
)
SELECT
    customer_id,
    customer_name,
    COUNT(*) AS qualifying_orders,
    SUM(order_total) AS qualifying_value
FROM eligible_orders
GROUP BY customer_id, customer_name
ORDER BY qualifying_value DESC;

-- Query 4: explicit validation of referentially valid order ownership.
SELECT
    o.order_id,
    o.customer_id,
    c.customer_name,
    CASE
        WHEN c.customer_id IS NULL THEN 'INVALID'
        ELSE 'VALID'
    END AS ownership_status
FROM orders AS o
LEFT JOIN customers AS c
    ON c.customer_id = o.customer_id
ORDER BY o.order_id;

-- PostgreSQL's planner exposes operators, costs, row estimates and
-- the physical strategy selected for a logical query.
EXPLAIN (COSTS, VERBOSE)
SELECT
    c.customer_name,
    o.order_id,
    o.order_total
FROM customers AS c
JOIN orders AS o
    ON o.customer_id = c.customer_id
WHERE c.status = 'active'
  AND o.order_total >= 800
ORDER BY o.order_total DESC
LIMIT 3;

-- EXPLAIN ANALYZE executes the statement and reports actual rows and timing.
-- It is intentionally run inside a transaction and rolled back so that
-- diagnostic execution cannot persist accidental writes.
BEGIN;

EXPLAIN (ANALYZE, BUFFERS, COSTS, SUMMARY)
SELECT
    c.customer_name,
    o.order_id,
    o.order_total
FROM customers AS c
JOIN orders AS o
    ON o.customer_id = c.customer_id
WHERE c.status = 'active'
  AND o.order_total >= 800
ORDER BY o.order_total DESC
LIMIT 3;

ROLLBACK;

-- A function evaluates whether a customer/order combination is eligible
-- for a business result without embedding application-specific state.
CREATE OR REPLACE FUNCTION is_order_eligible(
    p_customer_id BIGINT,
    p_minimum_total NUMERIC
)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    customer_status TEXT;
    total_value NUMERIC;
BEGIN
    IF p_minimum_total < 0 THEN
        RAISE EXCEPTION 'Minimum total cannot be negative';
    END IF;

    SELECT c.status, o.order_total
    INTO customer_status, total_value
    FROM customers AS c
    JOIN orders AS o
        ON o.customer_id = c.customer_id
    WHERE c.customer_id = p_customer_id
    ORDER BY o.order_id DESC
    LIMIT 1;

    IF customer_status IS NULL THEN
        RETURN FALSE;
    END IF;

    RETURN customer_status = 'active'
       AND total_value >= p_minimum_total;
END;
$$;

SELECT
    customer_id,
    customer_name,
    is_order_eligible(customer_id, 800) AS eligible
FROM customers
ORDER BY customer_id;

-- A trigger protects against impossible monetary values even when data
-- arrives through paths that bypass application validation.
CREATE OR REPLACE FUNCTION validate_order_total()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.order_total < 0 THEN
        RAISE EXCEPTION
            'order_total cannot be negative: %',
            NEW.order_total;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_order_total
BEFORE INSERT OR UPDATE OF order_total
ON orders
FOR EACH ROW
EXECUTE FUNCTION validate_order_total();

-- Transactional workflow: a valid insert is committed atomically.
BEGIN;

INSERT INTO orders (customer_id, order_total)
VALUES (2, 1350.00);

COMMIT;

-- A failed operation is isolated by a savepoint. The transaction remains
-- usable after the rejected row is rolled back.
BEGIN;

SAVEPOINT before_invalid_order;

DO $$
BEGIN
    BEGIN
        INSERT INTO orders (customer_id, order_total)
        VALUES (1, -10.00);
    EXCEPTION
        WHEN others THEN
            RAISE NOTICE 'Expected validation failure: %', SQLERRM;
            ROLLBACK TO SAVEPOINT before_invalid_order;
    END;
END;
$$;

COMMIT;

-- Reporting query with a window operator.
SELECT
    c.customer_name,
    o.order_id,
    o.order_total,
    RANK() OVER (
        PARTITION BY c.customer_id
        ORDER BY o.order_total DESC
    ) AS customer_order_rank
FROM customers AS c
JOIN orders AS o
    ON o.customer_id = c.customer_id
ORDER BY c.customer_id, customer_order_rank;

-- Final state report.
SELECT
    c.customer_id,
    c.customer_name,
    c.status,
    COUNT(o.order_id) AS order_count,
    COALESCE(SUM(o.order_total), 0) AS order_value
FROM customers AS c
LEFT JOIN orders AS o
    ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.customer_name, c.status
ORDER BY c.customer_id;
