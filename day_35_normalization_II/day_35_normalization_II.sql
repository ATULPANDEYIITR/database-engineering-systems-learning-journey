/*
 * Normalization II: 1NF, 2NF, and 3NF
 *
 * PostgreSQL-compatible executable demonstration.
 *
 * The script intentionally begins with a denormalized staging relation,
 * demonstrates the 1NF, 2NF, and 3NF transformations, and then creates the
 * final normalized relational model with database-level integrity rules.
 *
 * The four final relations are:
 *
 *   customers
 *   orders
 *   products
 *   order_items
 *
 * The 1NF teaching point is removal of repeating product groups.
 * The 2NF teaching point is removal of partial dependencies from the
 * (order_id, product_id) composite key.
 * The 3NF teaching point is removal of customer attributes that depend on
 * customer_id rather than directly on order_id.
 */

DROP SCHEMA IF EXISTS normalization_ii CASCADE;
CREATE SCHEMA normalization_ii;

SET search_path TO normalization_ii;

/*
 * This staging table deliberately permits a comma-separated product group.
 * It is not the final relational design. It exists to show why a repeating
 * group violates the atomic-value requirement of 1NF.
 */
CREATE TABLE unnormalized_orders (
    order_id       integer PRIMARY KEY,
    order_date     date NOT NULL,
    customer_id    varchar(20) NOT NULL,
    customer_name  varchar(100) NOT NULL,
    customer_city  varchar(100) NOT NULL,
    product_ids    text NOT NULL,
    product_names  text NOT NULL,
    quantities     text NOT NULL
);

INSERT INTO unnormalized_orders (
    order_id,
    order_date,
    customer_id,
    customer_name,
    customer_city,
    product_ids,
    product_names,
    quantities
)
VALUES
    (1001, DATE '2026-10-01', 'C001', 'Asha Rao', 'Lucknow',
     'P101,P102', 'Keyboard,Mouse', '2,1'),
    (1002, DATE '2026-10-02', 'C002', 'Rohan Mehta', 'Delhi',
     'P101', 'Keyboard', '1');

/*
 * 1NF demonstration.
 *
 * A proper relational row stores one product occurrence per row rather than
 * packing several product values into one attribute. PostgreSQL's
 * string_to_array/unnest functions are used only to transform the teaching
 * data into atomic rows.
 */
CREATE TABLE first_nf_order_lines (
    order_id       integer NOT NULL,
    order_date     date NOT NULL,
    customer_id    varchar(20) NOT NULL,
    customer_name  varchar(100) NOT NULL,
    customer_city  varchar(100) NOT NULL,
    product_id     varchar(20) NOT NULL,
    product_name   varchar(100) NOT NULL,
    quantity       integer NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (order_id, product_id)
);

INSERT INTO first_nf_order_lines (
    order_id,
    order_date,
    customer_id,
    customer_name,
    customer_city,
    product_id,
    product_name,
    quantity
)
SELECT
    u.order_id,
    u.order_date,
    u.customer_id,
    u.customer_name,
    u.customer_city,
    product_id,
    product_name,
    quantity
FROM unnormalized_orders AS u
CROSS JOIN LATERAL unnest(
    string_to_array(u.product_ids, ','),
    string_to_array(u.product_names, ','),
    string_to_array(u.quantities, ',')
) AS x(product_id, product_name, quantity_text)
CROSS JOIN LATERAL (
    SELECT x.quantity_text::integer AS quantity
) AS q;

/*
 * The following query confirms that the 1NF relation has one atomic product
 * value per row and a composite key for order lines.
 */
SELECT
    order_id,
    product_id,
    product_name,
    quantity
FROM first_nf_order_lines
ORDER BY order_id, product_id;

/*
 * 2NF decomposition.
 *
 * The candidate key of first_nf_order_lines is:
 *
 *     (order_id, product_id)
 *
 * Functional dependencies include:
 *
 *     order_id -> order_date, customer_id, customer_name, customer_city
 *     product_id -> product_name
 *     (order_id, product_id) -> quantity
 *
 * order-level attributes depend on only order_id, while product_name depends
 * on only product_id. These are partial dependencies on components of the
 * composite key.
 */

CREATE TABLE second_nf_orders (
    order_id       integer PRIMARY KEY,
    order_date     date NOT NULL,
    customer_id    varchar(20) NOT NULL,
    customer_name  varchar(100) NOT NULL,
    customer_city  varchar(100) NOT NULL
);

CREATE TABLE second_nf_products (
    product_id     varchar(20) PRIMARY KEY,
    product_name   varchar(100) NOT NULL
);

CREATE TABLE second_nf_order_items (
    order_id       integer NOT NULL,
    product_id     varchar(20) NOT NULL,
    quantity       integer NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (order_id, product_id),
    FOREIGN KEY (order_id)
        REFERENCES second_nf_orders(order_id),
    FOREIGN KEY (product_id)
        REFERENCES second_nf_products(product_id)
);

INSERT INTO second_nf_orders (
    order_id,
    order_date,
    customer_id,
    customer_name,
    customer_city
)
SELECT DISTINCT
    order_id,
    order_date,
    customer_id,
    customer_name,
    customer_city
FROM first_nf_order_lines;

INSERT INTO second_nf_products (
    product_id,
    product_name
)
SELECT DISTINCT
    product_id,
    product_name
FROM first_nf_order_lines;

INSERT INTO second_nf_order_items (
    order_id,
    product_id,
    quantity
)
SELECT
    order_id,
    product_id,
    quantity
FROM first_nf_order_lines;

/*
 * 2NF integrity checks.
 */
SELECT
    o.order_id,
    o.order_date,
    o.customer_id,
    oi.product_id,
    oi.quantity
FROM second_nf_orders AS o
JOIN second_nf_order_items AS oi
    ON oi.order_id = o.order_id
ORDER BY o.order_id, oi.product_id;

/*
 * 3NF decomposition.
 *
 * In second_nf_orders:
 *
 *     order_id -> customer_id
 *
 * and the customer identifier determines:
 *
 *     customer_id -> customer_name, customer_city
 *
 * Therefore customer_name and customer_city are transitively dependent on
 * order_id. They belong in a customer relation.
 */

CREATE TABLE customers (
    customer_id    varchar(20) PRIMARY KEY,
    customer_name  varchar(100) NOT NULL,
    customer_city  varchar(100) NOT NULL,
    CONSTRAINT customers_name_not_blank
        CHECK (length(trim(customer_name)) > 0),
    CONSTRAINT customers_city_not_blank
        CHECK (length(trim(customer_city)) > 0)
);

CREATE TABLE products (
    product_id     varchar(20) PRIMARY KEY,
    product_name   varchar(100) NOT NULL,
    CONSTRAINT products_name_not_blank
        CHECK (length(trim(product_name)) > 0)
);

CREATE TABLE orders (
    order_id       integer PRIMARY KEY,
    order_date     date NOT NULL,
    customer_id    varchar(20) NOT NULL,
    CONSTRAINT orders_customer_fk
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    order_id       integer NOT NULL,
    product_id     varchar(20) NOT NULL,
    quantity       integer NOT NULL,
    PRIMARY KEY (order_id, product_id),
    CONSTRAINT order_items_order_fk
        FOREIGN KEY (order_id)
        REFERENCES orders(order_id)
        ON DELETE CASCADE,
    CONSTRAINT order_items_product_fk
        FOREIGN KEY (product_id)
        REFERENCES products(product_id),
    CONSTRAINT order_items_positive_quantity
        CHECK (quantity > 0)
);

/*
 * Populate the final 3NF relations from the validated 2NF data.
 */
INSERT INTO customers (
    customer_id,
    customer_name,
    customer_city
)
SELECT DISTINCT
    customer_id,
    customer_name,
    customer_city
FROM second_nf_orders;

INSERT INTO products (
    product_id,
    product_name
)
SELECT
    product_id,
    product_name
FROM second_nf_products;

INSERT INTO orders (
    order_id,
    order_date,
    customer_id
)
SELECT
    order_id,
    order_date,
    customer_id
FROM second_nf_orders;

INSERT INTO order_items (
    order_id,
    product_id,
    quantity
)
SELECT
    order_id,
    product_id,
    quantity
FROM second_nf_order_items;

/*
 * The index on orders.customer_id supports the common relationship query
 * from customers to their orders. Primary keys already provide indexes for
 * the entity identifiers and the OrderItems composite key.
 */
CREATE INDEX idx_orders_customer_id
    ON orders(customer_id);

/*
 * Reconstructing the business view demonstrates that normalization does not
 * destroy information. It changes where facts are stored; joins recover the
 * combined operational view.
 */
CREATE VIEW order_business_view AS
SELECT
    o.order_id,
    o.order_date,
    c.customer_id,
    c.customer_name,
    c.customer_city,
    p.product_id,
    p.product_name,
    oi.quantity
FROM orders AS o
JOIN customers AS c
    ON c.customer_id = o.customer_id
JOIN order_items AS oi
    ON oi.order_id = o.order_id
JOIN products AS p
    ON p.product_id = oi.product_id;

SELECT *
FROM order_business_view
ORDER BY order_id, product_id;

/*
 * Demonstrate a database-enforced update.
 *
 * The customer city changes in one authoritative relation. Orders reference
 * the customer and therefore do not duplicate the city.
 */
BEGIN;

UPDATE customers
SET customer_city = 'Kanpur'
WHERE customer_id = 'C001';

SELECT
    o.order_id,
    c.customer_name,
    c.customer_city
FROM orders AS o
JOIN customers AS c
    ON c.customer_id = o.customer_id
WHERE c.customer_id = 'C001'
ORDER BY o.order_id;

COMMIT;

/*
 * Demonstrate insertion independence.
 *
 * A product can exist without an order. This is an insertion anomaly avoided
 * by separating product facts from order facts.
 */
INSERT INTO products (
    product_id,
    product_name
)
VALUES ('P103', 'USB-C Hub');

SELECT *
FROM products
WHERE product_id = 'P103';

/*
 * The new product is removed again so the script leaves the final sample
 * dataset compact.
 */
DELETE FROM products
WHERE product_id = 'P103';

/*
 * Demonstrate foreign-key enforcement.
 *
 * This transaction intentionally fails when an OrderItem references a product
 * that does not exist. PostgreSQL aborts the statement and the transaction is
 * rolled back explicitly.
 */
BEGIN;

INSERT INTO order_items (
    order_id,
    product_id,
    quantity
)
VALUES (1001, 'P999', 1);

ROLLBACK;

/*
 * Demonstrate CHECK enforcement using a savepoint so the rest of the script
 * remains usable after the intentionally invalid statement.
 */
BEGIN;

SAVEPOINT invalid_quantity_test;

INSERT INTO order_items (
    order_id,
    product_id,
    quantity
)
VALUES (1001, 'P101', 0);

ROLLBACK TO SAVEPOINT invalid_quantity_test;
COMMIT;

/*
 * Dependency-oriented inspection.
 *
 * These queries make the determinants visible:
 *
 * customer_id identifies customer facts;
 * product_id identifies product facts;
 * order_id identifies order facts;
 * (order_id, product_id) identifies order-line quantity.
 */

SELECT
    customer_id,
    count(*) AS rows_for_customer
FROM customers
GROUP BY customer_id
HAVING count(*) > 1;

SELECT
    product_id,
    count(*) AS rows_for_product
FROM products
GROUP BY product_id
HAVING count(*) > 1;

SELECT
    order_id,
    count(*) AS rows_for_order
FROM orders
GROUP BY order_id
HAVING count(*) > 1;

SELECT
    order_id,
    product_id,
    count(*) AS rows_for_order_product
FROM order_items
GROUP BY order_id, product_id
HAVING count(*) > 1;

/*
 * Final normalized schema inspection.
 */
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'normalization_ii'
  AND table_name IN (
      'customers',
      'products',
      'orders',
      'order_items'
  )
ORDER BY table_name, ordinal_position;
