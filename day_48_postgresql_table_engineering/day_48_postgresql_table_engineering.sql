/*
PostgreSQL Table Engineering
Topic: CREATE TABLE, ALTER TABLE, and relational constraints.

Target: PostgreSQL 14+
This script creates a realistic inventory and order-management schema,
inserts representative records, inspects catalog metadata, and demonstrates
integrity checks.

Run in a dedicated development database. The final DO block intentionally
catches expected integrity failures so the complete script can finish.
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS inventory;

CREATE TABLE IF NOT EXISTS inventory.categories (
    category_id BIGINT GENERATED ALWAYS AS IDENTITY,
    category_name TEXT NOT NULL,
    CONSTRAINT pk_categories PRIMARY KEY (category_id),
    CONSTRAINT uq_categories_name UNIQUE (category_name),
    CONSTRAINT ck_categories_name_nonempty
        CHECK (length(btrim(category_name)) > 0)
);

CREATE TABLE IF NOT EXISTS inventory.products (
    product_id BIGINT GENERATED ALWAYS AS IDENTITY,
    sku TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category_id BIGINT,
    unit_price NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_products PRIMARY KEY (product_id),
    CONSTRAINT uq_products_sku UNIQUE (sku),

    CONSTRAINT ck_products_sku_nonempty
        CHECK (length(btrim(sku)) > 0),

    CONSTRAINT ck_products_name_nonempty
        CHECK (length(btrim(product_name)) > 0),

    CONSTRAINT ck_products_price_nonnegative
        CHECK (unit_price >= 0),

    CONSTRAINT ck_products_stock_nonnegative
        CHECK (stock_quantity >= 0),

    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id)
        REFERENCES inventory.categories(category_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS inventory.customers (
    customer_id BIGINT GENERATED ALWAYS AS IDENTITY,
    email TEXT NOT NULL,
    full_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_customers PRIMARY KEY (customer_id),
    CONSTRAINT uq_customers_email UNIQUE (email),

    CONSTRAINT ck_customers_email_nonempty
        CHECK (length(btrim(email)) > 0),

    CONSTRAINT ck_customers_name_nonempty
        CHECK (length(btrim(full_name)) > 0)
);

CREATE TABLE IF NOT EXISTS inventory.orders (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY,
    customer_id BIGINT NOT NULL,
    order_status TEXT NOT NULL DEFAULT 'pending',
    ordered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_orders PRIMARY KEY (order_id),

    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id)
        REFERENCES inventory.customers(customer_id)
        ON DELETE RESTRICT,

    CONSTRAINT ck_orders_status
        CHECK (
            order_status IN (
                'pending',
                'confirmed',
                'shipped',
                'delivered',
                'cancelled'
            )
        )
);

CREATE TABLE IF NOT EXISTS inventory.order_items (
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,

    CONSTRAINT pk_order_items
        PRIMARY KEY (order_id, product_id),

    CONSTRAINT fk_items_order
        FOREIGN KEY (order_id)
        REFERENCES inventory.orders(order_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_items_product
        FOREIGN KEY (product_id)
        REFERENCES inventory.products(product_id)
        ON DELETE RESTRICT,

    CONSTRAINT ck_items_quantity
        CHECK (quantity > 0),

    CONSTRAINT ck_items_price
        CHECK (unit_price >= 0)
);

/*
Indexes are chosen for actual access paths. PostgreSQL automatically indexes
primary keys and unique constraints, but not the referencing side of every
foreign key.
*/
CREATE INDEX IF NOT EXISTS ix_products_category_active
    ON inventory.products (category_id, active);

CREATE INDEX IF NOT EXISTS ix_orders_customer_ordered_at
    ON inventory.orders (customer_id, ordered_at DESC);

CREATE INDEX IF NOT EXISTS ix_order_items_product
    ON inventory.order_items (product_id);

/*
ALTER TABLE adds new attributes without rebuilding the application-facing
table name. IF NOT EXISTS makes these particular additions rerunnable.
It does not prove that a pre-existing column has the expected definition.
*/
ALTER TABLE inventory.products
    ADD COLUMN IF NOT EXISTS description TEXT;

ALTER TABLE inventory.products
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
        NOT NULL DEFAULT CURRENT_TIMESTAMP;

/*
ALTER COLUMN changes the default for future inserts. It does not rewrite
existing values in the column.
*/
ALTER TABLE inventory.products
    ALTER COLUMN description SET DEFAULT '';

/*
A named constraint is easier to identify in PostgreSQL diagnostics.
The catalog check avoids adding this constraint twice when the script
is rerun against the same schema.
*/
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'inventory.products'::regclass
          AND conname = 'ck_products_description_length'
    ) THEN
        ALTER TABLE inventory.products
            ADD CONSTRAINT ck_products_description_length
            CHECK (length(description) <= 2000);
    END IF;
END;
$$;

INSERT INTO inventory.categories (category_name)
VALUES ('Keyboards'), ('Pointing Devices')
ON CONFLICT (category_name) DO NOTHING;

INSERT INTO inventory.products (
    sku,
    product_name,
    category_id,
    unit_price,
    stock_quantity,
    description
)
SELECT
    sample.sku,
    sample.product_name,
    categories.category_id,
    sample.unit_price,
    sample.stock_quantity,
    sample.description
FROM (
    VALUES
        (
            'KB-100',
            'Mechanical Keyboard',
            'Keyboards',
            3499.00::NUMERIC(12,2),
            20,
            'Hot-swappable mechanical keyboard'
        ),
        (
            'MS-200',
            'Wireless Mouse',
            'Pointing Devices',
            1299.00::NUMERIC(12,2),
            45,
            'Wireless optical mouse'
        )
) AS sample(
    sku,
    product_name,
    category_name,
    unit_price,
    stock_quantity,
    description
)
JOIN inventory.categories AS categories
  ON categories.category_name = sample.category_name
ON CONFLICT (sku) DO NOTHING;

INSERT INTO inventory.customers (email, full_name)
VALUES
    ('buyer@example.com', 'Riya Sharma'),
    ('operations@example.com', 'Dev Kumar')
ON CONFLICT (email) DO NOTHING;

INSERT INTO inventory.orders (customer_id, order_status)
SELECT customer_id, 'pending'
FROM inventory.customers
WHERE email = 'buyer@example.com'
  AND NOT EXISTS (
      SELECT 1
      FROM inventory.orders existing
      WHERE existing.customer_id = inventory.customers.customer_id
        AND existing.order_status = 'pending'
  );

INSERT INTO inventory.order_items (
    order_id,
    product_id,
    quantity,
    unit_price
)
SELECT
    orders.order_id,
    products.product_id,
    1,
    products.unit_price
FROM inventory.orders AS orders
JOIN inventory.customers AS customers
  ON customers.customer_id = orders.customer_id
JOIN inventory.products AS products
  ON products.sku = 'KB-100'
WHERE customers.email = 'buyer@example.com'
  AND orders.order_status = 'pending'
ON CONFLICT (order_id, product_id) DO NOTHING;

/*
Inspect the resulting table definition using PostgreSQL's information schema.
*/
SELECT
    table_schema,
    table_name,
    column_name,
    ordinal_position,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'inventory'
ORDER BY table_name, ordinal_position;

/*
Constraint types: p = primary key, u = unique, f = foreign key,
c = check, and x = exclusion constraint.
*/
SELECT
    table_name,
    constraint_name,
    constraint_type
FROM information_schema.table_constraints
WHERE constraint_schema = 'inventory'
ORDER BY table_name, constraint_name;

/*
A relational query can use the declared keys to produce order totals.
The stored order-item price represents the price captured at purchase time,
rather than changing whenever the current product price changes.
*/
SELECT
    orders.order_id,
    customers.email,
    orders.order_status,
    COALESCE(
        SUM(items.quantity * items.unit_price),
        0
    ) AS order_total
FROM inventory.orders AS orders
JOIN inventory.customers AS customers
  ON customers.customer_id = orders.customer_id
LEFT JOIN inventory.order_items AS items
  ON items.order_id = orders.order_id
GROUP BY
    orders.order_id,
    customers.email,
    orders.order_status
ORDER BY orders.order_id;

/*
The following checks deliberately submit invalid rows. Each failure is
caught inside a PL/pgSQL exception block, leaving the outer transaction usable.
*/
DO $$
BEGIN
    BEGIN
        INSERT INTO inventory.products (
            sku,
            product_name,
            unit_price,
            stock_quantity
        )
        VALUES ('KB-100', 'Duplicate SKU', 10.00, 1);

        RAISE EXCEPTION 'Expected duplicate SKU rejection did not occur';
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE 'Expected failure: duplicate SKU rejected';
    END;

    BEGIN
        INSERT INTO inventory.products (
            sku,
            product_name,
            unit_price,
            stock_quantity
        )
        VALUES ('BAD-PRICE', 'Invalid Price', -10.00, 1);

        RAISE EXCEPTION 'Expected negative price rejection did not occur';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'Expected failure: negative price rejected';
    END;

    BEGIN
        INSERT INTO inventory.products (
            sku,
            product_name,
            unit_price,
            stock_quantity,
            category_id
        )
        VALUES ('BAD-CATEGORY', 'Missing Category', 10.00, 1, -999);

        RAISE EXCEPTION 'Expected foreign key rejection did not occur';
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE 'Expected failure: invalid category rejected';
    END;

    BEGIN
        INSERT INTO inventory.products (
            sku,
            product_name,
            unit_price,
            stock_quantity
        )
        VALUES ('BAD-NULL', NULL, 10.00, 1);

        RAISE EXCEPTION 'Expected NOT NULL rejection did not occur';
    EXCEPTION
        WHEN not_null_violation THEN
            RAISE NOTICE 'Expected failure: NULL product name rejected';
    END;
END;
$$;

/*
PostgreSQL CHECK expressions accept TRUE or UNKNOWN. NOT NULL must be used
separately when a value cannot be absent.

A UNIQUE constraint normally allows multiple NULL values because NULLs are
distinct by default. PostgreSQL also supports UNIQUE NULLS NOT DISTINCT on
versions that implement that syntax when a different policy is required.

For high-traffic deployments, plan lock acquisition, backfills, validation
of existing rows, and index creation deliberately. CREATE INDEX CONCURRENTLY
cannot run inside a transaction block.
*/

COMMIT;
