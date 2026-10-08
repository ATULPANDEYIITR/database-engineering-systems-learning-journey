DROP SCHEMA IF EXISTS referential_integrity_demo CASCADE;

CREATE SCHEMA referential_integrity_demo;

SET search_path TO referential_integrity_demo;

-- The customer table is the parent relation.
-- Its primary key is the candidate key referenced by child tables.
CREATE TABLE customer (
    customer_id BIGINT GENERATED ALWAYS AS IDENTITY,
    customer_code TEXT NOT NULL,
    customer_name TEXT NOT NULL,

    CONSTRAINT pk_customer
        PRIMARY KEY (customer_id),

    CONSTRAINT uq_customer_code
        UNIQUE (customer_code),

    CONSTRAINT ck_customer_code_not_blank
        CHECK (btrim(customer_code) <> ''),

    CONSTRAINT ck_customer_name_not_blank
        CHECK (btrim(customer_name) <> '')
);

-- The order table demonstrates a mandatory foreign-key relationship.
-- RESTRICT prevents deleting a customer while dependent orders exist.
CREATE TABLE customer_order (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY,
    customer_id BIGINT NOT NULL,
    order_reference TEXT NOT NULL,
    order_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
    order_status TEXT NOT NULL DEFAULT 'OPEN',

    CONSTRAINT pk_customer_order
        PRIMARY KEY (order_id),

    CONSTRAINT uq_order_reference
        UNIQUE (order_reference),

    CONSTRAINT fk_order_customer
        FOREIGN KEY (customer_id)
        REFERENCES customer(customer_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT ck_order_amount
        CHECK (order_amount >= 0),

    CONSTRAINT ck_order_status
        CHECK (order_status IN ('OPEN', 'PAID', 'CANCELLED'))
);

-- PostgreSQL does not automatically create an index on the referencing
-- column of a foreign key. This index improves customer-specific lookups
-- and helps parent-row deletion checks.
CREATE INDEX idx_customer_order_customer_id
    ON customer_order(customer_id);

-- Order items use CASCADE because an item has no independent meaning
-- once its containing order is deleted.
CREATE TABLE order_item (
    order_item_id BIGINT GENERATED ALWAYS AS IDENTITY,
    order_id BIGINT NOT NULL,
    product_code TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,

    CONSTRAINT pk_order_item
        PRIMARY KEY (order_item_id),

    CONSTRAINT fk_order_item_order
        FOREIGN KEY (order_id)
        REFERENCES customer_order(order_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT ck_order_item_quantity
        CHECK (quantity > 0),

    CONSTRAINT ck_order_item_unit_price
        CHECK (unit_price >= 0),

    CONSTRAINT uq_order_product
        UNIQUE (order_id, product_code)
);

CREATE INDEX idx_order_item_order_id
    ON order_item(order_id);

-- A contact can optionally reference a customer.
-- SET NULL is appropriate here because the contact record can remain
-- meaningful even if the associated customer is removed.
CREATE TABLE customer_contact (
    contact_id BIGINT GENERATED ALWAYS AS IDENTITY,
    customer_id BIGINT,
    contact_name TEXT NOT NULL,
    email TEXT,

    CONSTRAINT pk_customer_contact
        PRIMARY KEY (contact_id),

    CONSTRAINT fk_contact_customer
        FOREIGN KEY (customer_id)
        REFERENCES customer(customer_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,

    CONSTRAINT ck_contact_name
        CHECK (btrim(contact_name) <> '')
);

CREATE INDEX idx_customer_contact_customer_id
    ON customer_contact(customer_id);

-- A self-referencing hierarchy demonstrates that a foreign key can
-- reference the same table. The root employee has manager_id = NULL.
CREATE TABLE employee (
    employee_id BIGINT GENERATED ALWAYS AS IDENTITY,
    employee_name TEXT NOT NULL,
    manager_id BIGINT,

    CONSTRAINT pk_employee
        PRIMARY KEY (employee_id),

    CONSTRAINT fk_employee_manager
        FOREIGN KEY (manager_id)
        REFERENCES employee(employee_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,

    CONSTRAINT ck_employee_name
        CHECK (btrim(employee_name) <> '')
);

CREATE INDEX idx_employee_manager_id
    ON employee(manager_id);

INSERT INTO customer (
    customer_code,
    customer_name
)
VALUES
    ('CUST-001', 'Atlas Manufacturing'),
    ('CUST-002', 'Northstar Engineering'),
    ('CUST-003', 'Cascade Systems');

INSERT INTO customer_order (
    customer_id,
    order_reference,
    order_amount,
    order_status
)
SELECT
    customer_id,
    'ORD-001',
    25000.00,
    'OPEN'
FROM customer
WHERE customer_code = 'CUST-001';

INSERT INTO customer_order (
    customer_id,
    order_reference,
    order_amount,
    order_status
)
SELECT
    customer_id,
    'ORD-002',
    17500.00,
    'PAID'
FROM customer
WHERE customer_code = 'CUST-001';

INSERT INTO customer_order (
    customer_id,
    order_reference,
    order_amount,
    order_status
)
SELECT
    customer_id,
    'ORD-003',
    8900.00,
    'OPEN'
FROM customer
WHERE customer_code = 'CUST-002';

INSERT INTO order_item (
    order_id,
    product_code,
    quantity,
    unit_price
)
SELECT
    order_id,
    'SENSOR-X',
    10,
    450.00
FROM customer_order
WHERE order_reference = 'ORD-001';

INSERT INTO order_item (
    order_id,
    product_code,
    quantity,
    unit_price
)
SELECT
    order_id,
    'GATEWAY-A',
    2,
    3500.00
FROM customer_order
WHERE order_reference = 'ORD-001';

INSERT INTO order_item (
    order_id,
    product_code,
    quantity,
    unit_price
)
SELECT
    order_id,
    'LICENSE-PRO',
    5,
    900.00
FROM customer_order
WHERE order_reference = 'ORD-002';

INSERT INTO customer_contact (
    customer_id,
    contact_name,
    email
)
SELECT
    customer_id,
    'Operations Desk',
    'operations@example.invalid'
FROM customer
WHERE customer_code = 'CUST-001';

INSERT INTO employee (
    employee_name,
    manager_id
)
VALUES
    ('Anita Rao', NULL);

INSERT INTO employee (
    employee_name,
    manager_id
)
SELECT
    'Vikram Shah',
    employee_id
FROM employee
WHERE employee_name = 'Anita Rao';

INSERT INTO employee (
    employee_name,
    manager_id
)
SELECT
    'Neha Singh',
    employee_id
FROM employee
WHERE employee_name = 'Anita Rao';

-- Demonstrate the valid parent-child relationship.
SELECT
    c.customer_code,
    c.customer_name,
    o.order_reference,
    o.order_status,
    o.order_amount
FROM customer AS c
JOIN customer_order AS o
    ON o.customer_id = c.customer_id
ORDER BY c.customer_code, o.order_reference;

-- Demonstrate a multi-level relationship.
-- The joins are valid because every order_item must reference an
-- existing customer_order, which must reference an existing customer.
SELECT
    c.customer_code,
    o.order_reference,
    oi.product_code,
    oi.quantity,
    oi.unit_price,
    oi.quantity * oi.unit_price AS line_value
FROM customer AS c
JOIN customer_order AS o
    ON o.customer_id = c.customer_id
JOIN order_item AS oi
    ON oi.order_id = o.order_id
ORDER BY c.customer_code, o.order_reference, oi.product_code;

-- Detect potential orphan rows with a LEFT JOIN.
-- With enforced foreign keys this should return zero rows.
SELECT
    o.order_id,
    o.customer_id
FROM customer_order AS o
LEFT JOIN customer AS c
    ON c.customer_id = o.customer_id
WHERE c.customer_id IS NULL;

-- Demonstrate aggregation through a valid relationship.
SELECT
    c.customer_code,
    c.customer_name,
    COUNT(o.order_id) AS order_count,
    COALESCE(SUM(o.order_amount), 0) AS total_order_value
FROM customer AS c
LEFT JOIN customer_order AS o
    ON o.customer_id = c.customer_id
GROUP BY
    c.customer_id,
    c.customer_code,
    c.customer_name
ORDER BY c.customer_code;

-- Demonstrate RESTRICT.
-- This statement is intentionally placed inside a transaction and rolled
-- back so the demonstration does not destroy the sample dataset.
BEGIN;

DO $$
DECLARE
    target_customer_id BIGINT;
BEGIN
    SELECT customer_id
    INTO target_customer_id
    FROM customer
    WHERE customer_code = 'CUST-001';

    BEGIN
        DELETE FROM customer
        WHERE customer_id = target_customer_id;
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE
                'RESTRICT prevented deletion of CUST-001 because dependent orders exist.';
    END;
END
$$;

ROLLBACK;

-- Demonstrate ON DELETE CASCADE.
-- Deleting ORD-001 removes its dependent order_item rows automatically.
BEGIN;

DELETE FROM customer_order
WHERE order_reference = 'ORD-001';

SELECT
    COUNT(*) AS remaining_items_for_deleted_order
FROM order_item AS oi
WHERE NOT EXISTS (
    SELECT 1
    FROM customer_order AS o
    WHERE o.order_id = oi.order_id
);

ROLLBACK;

-- Demonstrate ON DELETE SET NULL.
-- The contact remains after its customer is deleted, but customer_id becomes
-- NULL. The transaction is rolled back after inspection.
BEGIN;

WITH deleted_customer AS (
    DELETE FROM customer
    WHERE customer_code = 'CUST-003'
    RETURNING customer_id
)
SELECT
    cc.contact_id,
    cc.contact_name,
    cc.customer_id
FROM customer_contact AS cc
JOIN deleted_customer AS dc
    ON cc.customer_id IS NOT DISTINCT FROM dc.customer_id;

ROLLBACK;

-- A simpler SET NULL demonstration using the contact attached to CUST-001.
-- The operation is again rolled back.
BEGIN;

WITH target AS (
    SELECT customer_id
    FROM customer
    WHERE customer_code = 'CUST-001'
)
DELETE FROM customer
WHERE customer_id IN (SELECT customer_id FROM target);

SELECT
    contact_id,
    contact_name,
    customer_id
FROM customer_contact
WHERE contact_name = 'Operations Desk';

ROLLBACK;

-- Demonstrate ON UPDATE CASCADE.
-- Primary-key updates are uncommon in production systems, but PostgreSQL
-- can propagate a referenced-key change when ON UPDATE CASCADE is defined.
BEGIN;

WITH target AS (
    SELECT customer_id
    FROM customer
    WHERE customer_code = 'CUST-001'
)
UPDATE customer
SET customer_id = customer_id + 100000
WHERE customer_id IN (SELECT customer_id FROM target);

SELECT
    order_reference,
    customer_id
FROM customer_order
WHERE order_reference IN ('ORD-001', 'ORD-002');

ROLLBACK;

-- Demonstrate database-level rejection of an orphan insert.
-- The statement is intentionally wrapped in a block so execution can
-- continue after the expected constraint violation.
DO $$
BEGIN
    BEGIN
        INSERT INTO customer_order (
            customer_id,
            order_reference,
            order_amount,
            order_status
        )
        VALUES (
            999999999,
            'ORD-INVALID',
            500.00,
            'OPEN'
        );
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE
                'Foreign key rejected an order referencing a nonexistent customer.';
    END;
END
$$;

-- Demonstrate database-level rejection of an orphan order item.
DO $$
BEGIN
    BEGIN
        INSERT INTO order_item (
            order_id,
            product_code,
            quantity,
            unit_price
        )
        VALUES (
            999999999,
            'INVALID-PRODUCT',
            1,
            10.00
        );
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE
                'Foreign key rejected an item referencing a nonexistent order.';
    END;
END
$$;

-- Show the referential graph.
SELECT
    tc.table_name AS child_table,
    kcu.column_name AS child_column,
    ccu.table_name AS parent_table,
    ccu.column_name AS parent_column,
    rc.delete_rule,
    rc.update_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON tc.constraint_name = ccu.constraint_name
    AND tc.table_schema = ccu.table_schema
JOIN information_schema.referential_constraints AS rc
    ON tc.constraint_name = rc.constraint_name
    AND tc.table_schema = rc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'referential_integrity_demo'
ORDER BY tc.table_name, kcu.column_name;

-- Self-referencing hierarchy query.
WITH RECURSIVE employee_tree AS (
    SELECT
        employee_id,
        employee_name,
        manager_id,
        0 AS depth
    FROM employee
    WHERE manager_id IS NULL

    UNION ALL

    SELECT
        child.employee_id,
        child.employee_name,
        child.manager_id,
        parent.depth + 1
    FROM employee AS child
    JOIN employee_tree AS parent
        ON child.manager_id = parent.employee_id
)
SELECT
    employee_id,
    employee_name,
    manager_id,
    depth
FROM employee_tree
ORDER BY depth, employee_id;

-- Referential integrity design notes:
-- * A foreign key prevents a non-null child key from pointing to a nonexistent
--   parent key.
-- * RESTRICT blocks parent deletion while dependent rows exist.
-- * CASCADE propagates deletion to dependent rows.
-- * SET NULL preserves the child but requires a nullable foreign-key column.
-- * ON UPDATE CASCADE propagates changes to referenced keys.
-- * Foreign keys are integrity constraints, not substitutes for application
--   validation. Both layers can provide useful guarantees.
-- * Indexes on foreign-key columns are important for join performance and
--   efficient dependent-row discovery, especially for large child tables.
