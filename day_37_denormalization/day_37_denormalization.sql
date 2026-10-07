-- Denormalization case study for PostgreSQL.
--
-- The transactional tables remain normalized. A separate denormalized
-- order_read_model is maintained as derived data for read-heavy reporting.
--
-- PostgreSQL features demonstrated:
--   * primary and foreign keys
--   * CHECK and UNIQUE constraints
--   * indexes
--   * materialized view
--   * triggers
--   * transactional refresh
--   * reconciliation queries
--   * aggregate reporting
--
-- The design intentionally keeps the authoritative facts normalized and
-- treats denormalized values as derived data with an explicit refresh path.

DROP MATERIALIZED VIEW IF EXISTS sales_order_report CASCADE;
DROP TABLE IF EXISTS order_read_model CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    customer_id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    region TEXT NOT NULL,
    CONSTRAINT customers_name_not_blank
        CHECK (btrim(customer_name) <> ''),
    CONSTRAINT customers_region_not_blank
        CHECK (btrim(region) <> '')
);

CREATE TABLE products (
    product_id BIGSERIAL PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    CONSTRAINT products_name_not_blank
        CHECK (btrim(product_name) <> ''),
    CONSTRAINT products_category_not_blank
        CHECK (btrim(category) <> ''),
    CONSTRAINT products_positive_price
        CHECK (unit_price >= 0)
);

CREATE TABLE orders (
    order_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL
        REFERENCES customers(customer_id),
    order_date DATE NOT NULL,
    status TEXT NOT NULL,
    CONSTRAINT orders_valid_status
        CHECK (
            status IN (
                'PROCESSING',
                'SHIPPED',
                'DELIVERED',
                'CANCELLED'
            )
        )
);

CREATE TABLE order_items (
    order_id BIGINT NOT NULL
        REFERENCES orders(order_id)
        ON DELETE CASCADE,
    product_id BIGINT NOT NULL
        REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    PRIMARY KEY (order_id, product_id),
    CONSTRAINT order_items_positive_quantity
        CHECK (quantity > 0)
);

-- This index supports queries that retrieve orders for a customer.
CREATE INDEX idx_orders_customer
    ON orders(customer_id);

-- This index supports product-oriented analysis without scanning every item.
CREATE INDEX idx_order_items_product
    ON order_items(product_id);

INSERT INTO customers (customer_name, region)
VALUES
    ('Aarav Mehta', 'North'),
    ('Priya Nair', 'South'),
    ('Kabir Singh', 'North'),
    ('Meera Shah', 'West');

INSERT INTO products (product_name, category, unit_price)
VALUES
    ('Mechanical Keyboard', 'Peripherals', 89.99),
    ('USB-C Dock', 'Peripherals', 129.50),
    ('27-inch Monitor', 'Displays', 279.00),
    ('Laptop Stand', 'Accessories', 45.00),
    ('Noise-Cancelling Headset', 'Audio', 159.95);

INSERT INTO orders (customer_id, order_date, status)
VALUES
    (1, DATE '2026-09-01', 'SHIPPED'),
    (2, DATE '2026-09-02', 'PROCESSING'),
    (1, DATE '2026-09-03', 'DELIVERED'),
    (3, DATE '2026-09-04', 'SHIPPED'),
    (4, DATE '2026-09-05', 'CANCELLED');

INSERT INTO order_items (order_id, product_id, quantity)
VALUES
    (1, 1, 1),
    (1, 3, 2),
    (2, 2, 1),
    (2, 4, 2),
    (3, 5, 1),
    (3, 1, 2),
    (4, 3, 1),
    (4, 4, 1),
    (5, 2, 1);

-- The normalized query reconstructs the required report by joining
-- customers, orders, order_items, and products.
SELECT
    o.order_id,
    c.customer_name,
    c.region,
    o.status,
    SUM(oi.quantity) AS item_count,
    ROUND(SUM(oi.quantity * p.unit_price), 2) AS total_amount
FROM orders AS o
JOIN customers AS c
    ON c.customer_id = o.customer_id
JOIN order_items AS oi
    ON oi.order_id = o.order_id
JOIN products AS p
    ON p.product_id = oi.product_id
GROUP BY
    o.order_id,
    c.customer_name,
    c.region,
    o.status
ORDER BY o.order_id;

-- The read model intentionally duplicates customer attributes and stores
-- a precomputed order aggregate. It is not the source of truth.
CREATE TABLE order_read_model (
    order_id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    customer_name TEXT NOT NULL,
    region TEXT NOT NULL,
    order_date DATE NOT NULL,
    status TEXT NOT NULL,
    item_count INTEGER NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    source_version BIGINT NOT NULL,
    materialized_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT read_model_nonnegative_items
        CHECK (item_count >= 0),

    CONSTRAINT read_model_nonnegative_total
        CHECK (total_amount >= 0),

    CONSTRAINT read_model_valid_status
        CHECK (
            status IN (
                'PROCESSING',
                'SHIPPED',
                'DELIVERED',
                'CANCELLED'
            )
        )
);

CREATE INDEX idx_read_model_region
    ON order_read_model(region);

CREATE INDEX idx_read_model_status
    ON order_read_model(status);

CREATE INDEX idx_read_model_date
    ON order_read_model(order_date);

CREATE OR REPLACE FUNCTION refresh_order_read_model(
    p_order_id BIGINT,
    p_source_version BIGINT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO order_read_model (
        order_id,
        customer_id,
        customer_name,
        region,
        order_date,
        status,
        item_count,
        total_amount,
        source_version,
        materialized_at
    )
    SELECT
        o.order_id,
        c.customer_id,
        c.customer_name,
        c.region,
        o.order_date,
        o.status,
        COALESCE(SUM(oi.quantity), 0)::INTEGER,
        COALESCE(
            ROUND(SUM(oi.quantity * p.unit_price), 2),
            0
        ),
        p_source_version,
        clock_timestamp()
    FROM orders AS o
    JOIN customers AS c
        ON c.customer_id = o.customer_id
    LEFT JOIN order_items AS oi
        ON oi.order_id = o.order_id
    LEFT JOIN products AS p
        ON p.product_id = oi.product_id
    WHERE o.order_id = p_order_id
    GROUP BY
        o.order_id,
        c.customer_id,
        c.customer_name,
        c.region,
        o.order_date,
        o.status
    ON CONFLICT (order_id)
    DO UPDATE SET
        customer_id = EXCLUDED.customer_id,
        customer_name = EXCLUDED.customer_name,
        region = EXCLUDED.region,
        order_date = EXCLUDED.order_date,
        status = EXCLUDED.status,
        item_count = EXCLUDED.item_count,
        total_amount = EXCLUDED.total_amount,
        source_version = EXCLUDED.source_version,
        materialized_at = EXCLUDED.materialized_at;
END;
$$;

-- Populate the derived read model.
SELECT refresh_order_read_model(order_id, 1)
FROM orders;

-- A read-heavy dashboard can now avoid repeatedly reconstructing each
-- order from several normalized tables.
SELECT
    region,
    COUNT(*) AS orders,
    SUM(item_count) AS units,
    ROUND(SUM(total_amount), 2) AS revenue
FROM order_read_model
WHERE status <> 'CANCELLED'
GROUP BY region
ORDER BY region;

-- Historical snapshots are one legitimate reason to duplicate values.
-- If an invoice must preserve the customer name used when it was issued,
-- storing that snapshot is semantically different from copying a mutable
-- customer name merely to avoid a cheap join.

-- Demonstrate a source update.
BEGIN;

UPDATE customers
SET customer_name = 'Aarav Mehta Kumar'
WHERE customer_id = 1;

-- The normalized source now contains the new name.
SELECT customer_id, customer_name
FROM customers
WHERE customer_id = 1;

-- The derived read model still contains its previous value until refreshed.
SELECT order_id, customer_name, source_version
FROM order_read_model
WHERE customer_id = 1
ORDER BY order_id;

-- Refresh all affected orders inside the same transaction when immediate
-- projection consistency is required for this operation.
SELECT refresh_order_read_model(1, 2);
SELECT refresh_order_read_model(3, 2);

COMMIT;

-- Reconciliation compares derived aggregates against authoritative data.
WITH normalized AS (
    SELECT
        o.order_id,
        c.customer_id,
        c.customer_name,
        c.region,
        o.order_date,
        o.status,
        COALESCE(SUM(oi.quantity), 0)::INTEGER AS item_count,
        COALESCE(
            ROUND(SUM(oi.quantity * p.unit_price), 2),
            0
        ) AS total_amount
    FROM orders AS o
    JOIN customers AS c
        ON c.customer_id = o.customer_id
    LEFT JOIN order_items AS oi
        ON oi.order_id = o.order_id
    LEFT JOIN products AS p
        ON p.product_id = oi.product_id
    GROUP BY
        o.order_id,
        c.customer_id,
        c.customer_name,
        c.region,
        o.order_date,
        o.status
)
SELECT
    r.order_id,
    CASE
        WHEN r.customer_id = n.customer_id
         AND r.customer_name = n.customer_name
         AND r.region = n.region
         AND r.order_date = n.order_date
         AND r.status = n.status
         AND r.item_count = n.item_count
         AND r.total_amount = n.total_amount
        THEN 'CONSISTENT'
        ELSE 'STALE_OR_CORRUPTED'
    END AS consistency_state,
    r.source_version,
    r.materialized_at
FROM order_read_model AS r
JOIN normalized AS n
    ON n.order_id = r.order_id
ORDER BY r.order_id;

-- A materialized view is another PostgreSQL-specific denormalization option.
-- It is useful when the database can own the derived result and periodic
-- REFRESH MATERIALIZED VIEW is acceptable.
CREATE MATERIALIZED VIEW sales_order_report AS
SELECT
    c.region,
    o.status,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(oi.quantity) AS unit_count,
    ROUND(SUM(oi.quantity * p.unit_price), 2) AS revenue
FROM customers AS c
JOIN orders AS o
    ON o.customer_id = c.customer_id
JOIN order_items AS oi
    ON oi.order_id = o.order_id
JOIN products AS p
    ON p.product_id = oi.product_id
GROUP BY
    c.region,
    o.status;

CREATE INDEX idx_sales_order_report_region
    ON sales_order_report(region);

SELECT *
FROM sales_order_report
ORDER BY region, status;

-- REFRESH MATERIALIZED VIEW sales_order_report;
--
-- A refresh strategy is part of the denormalization design. A copied value
-- without a defined refresh or reconciliation mechanism creates an integrity
-- problem rather than a performance optimization.

-- Demonstrate a constraint failure conceptually through a transaction that
-- is rolled back. PostgreSQL enforces this rule before application code can
-- create an invalid quantity.
BEGIN;

DO $$
BEGIN
    BEGIN
        INSERT INTO order_items(order_id, product_id, quantity)
        VALUES (1, 1, 0);
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE
                'Rejected invalid order quantity through CHECK constraint.';
    END;
END;
$$;

ROLLBACK;

-- Query-plan inspection should be performed before deciding that a normalized
-- query is too expensive. Denormalization should not compensate for a missing
-- or inappropriate index without first measuring the actual workload.
EXPLAIN (COSTS, VERBOSE)
SELECT
    o.order_id,
    c.customer_name,
    ROUND(SUM(oi.quantity * p.unit_price), 2) AS total_amount
FROM orders AS o
JOIN customers AS c
    ON c.customer_id = o.customer_id
JOIN order_items AS oi
    ON oi.order_id = o.order_id
JOIN products AS p
    ON p.product_id = oi.product_id
WHERE o.status IN ('PROCESSING', 'SHIPPED', 'DELIVERED')
GROUP BY
    o.order_id,
    c.customer_name;

-- The central database rule is:
-- authoritative transactional facts remain normalized unless there is a
-- deliberate business or performance reason to duplicate them. Derived
-- denormalized data requires ownership, refresh semantics, constraints where
-- possible, monitoring, and reconciliation.
