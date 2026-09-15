"""
SQL Foundations Project
=======================

Build and query a complete small relational database.

This standalone study script uses Python's standard-library sqlite3 module to
teach SQL from foundational relational concepts through practical database
design, querying, constraints, transactions, indexing, views, aggregation,
joins, subqueries, common table expressions, window functions, validation,
performance inspection, and production-oriented practices.

No external Python packages are required.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from pprint import pprint
import random
import statistics
import time


DATABASE_NAME = ":memory:"


def section(title):
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def subsection(title):
    print("\n" + "-" * 72)
    print(title)
    print("-" * 72)


def show_rows(cursor, rows, limit=None):
    rows = rows if limit is None else rows[:limit]
    if not rows:
        print("(no rows)")
        return

    columns = [description[0] for description in cursor.description]
    print(" | ".join(columns))
    print("-" * (len(" | ".join(columns)) + 4))
    for row in rows:
        print(" | ".join(str(value) for value in row))


def execute_and_show(connection, sql, parameters=()):
    cursor = connection.execute(sql, parameters)
    rows = cursor.fetchall()
    show_rows(cursor, rows)
    return rows


def explain_sql(connection, sql, parameters=()):
    print("SQL:", " ".join(sql.split()))
    cursor = connection.execute("EXPLAIN QUERY PLAN " + sql, parameters)
    for row in cursor.fetchall():
        print(row)


@contextmanager
def transaction(connection):
    """
    A transaction groups several statements into one atomic unit.

    If an exception escapes the context, the transaction is rolled back.
    Otherwise it is committed.
    """
    try:
        connection.execute("BEGIN")
        yield
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def create_schema(connection):
    """
    The schema models a small online learning business.

    Relationships:
        customers 1 -> many orders
        orders 1 -> many order_items
        products 1 -> many order_items
        categories 1 -> many products
        customers 1 -> many payments
        employees 1 -> many orders
    """
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        DROP VIEW IF EXISTS customer_order_summary;
        DROP TABLE IF EXISTS payments;
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS categories;
        DROP TABLE IF EXISTS employees;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            city TEXT NOT NULL,
            signup_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'inactive', 'blocked'))
        );

        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            department TEXT NOT NULL,
            salary NUMERIC NOT NULL CHECK (salary >= 0)
        );

        CREATE TABLE categories (
            category_id INTEGER PRIMARY KEY,
            category_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            category_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price NUMERIC NOT NULL CHECK (price >= 0),
            stock_quantity INTEGER NOT NULL DEFAULT 0
                CHECK (stock_quantity >= 0),
            active INTEGER NOT NULL DEFAULT 1
                CHECK (active IN (0, 1)),
            FOREIGN KEY (category_id)
                REFERENCES categories(category_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            employee_id INTEGER,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled')),
            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT,
            FOREIGN KEY (employee_id)
                REFERENCES employees(employee_id)
                ON DELETE SET NULL
        );

        CREATE TABLE order_items (
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            unit_price NUMERIC NOT NULL CHECK (unit_price >= 0),
            PRIMARY KEY (order_id, product_id),
            FOREIGN KEY (order_id)
                REFERENCES orders(order_id)
                ON DELETE CASCADE,
            FOREIGN KEY (product_id)
                REFERENCES products(product_id)
                ON DELETE RESTRICT
        );

        CREATE TABLE payments (
            payment_id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL UNIQUE,
            amount NUMERIC NOT NULL CHECK (amount >= 0),
            payment_method TEXT NOT NULL
                CHECK (payment_method IN ('card', 'upi', 'bank_transfer', 'cash')),
            paid_at TEXT,
            status TEXT NOT NULL
                CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
            FOREIGN KEY (order_id)
                REFERENCES orders(order_id)
                ON DELETE CASCADE
        );

        CREATE INDEX idx_customers_city
            ON customers(city);

        CREATE INDEX idx_orders_customer_date
            ON orders(customer_id, order_date);

        CREATE INDEX idx_orders_status
            ON orders(status);

        CREATE INDEX idx_products_category
            ON products(category_id);

        CREATE INDEX idx_order_items_product
            ON order_items(product_id);
        """
    )


def seed_data(connection):
    customers = [
        (1, "Aarav Sharma", "aarav@example.com", "Lucknow", "2025-01-12", "active"),
        (2, "Priya Singh", "priya@example.com", "Delhi", "2025-02-20", "active"),
        (3, "Rohan Verma", "rohan@example.com", "Mumbai", "2025-03-05", "active"),
        (4, "Ananya Gupta", "ananya@example.com", "Lucknow", "2025-03-18", "active"),
        (5, "Kabir Khan", "kabir@example.com", "Bengaluru", "2025-04-02", "inactive"),
        (6, "Meera Joshi", "meera@example.com", "Pune", "2025-04-15", "active"),
        (7, "Vikram Rao", "vikram@example.com", "Hyderabad", "2025-05-11", "blocked"),
        (8, "Ishita Patel", "ishita@example.com", "Ahmedabad", "2025-06-21", "active"),
    ]

    employees = [
        (1, "Neha Kapoor", "Sales", 65000),
        (2, "Arjun Mehta", "Operations", 72000),
        (3, "Sana Ali", "Support", 58000),
    ]

    categories = [
        (1, "Programming"),
        (2, "Data"),
        (3, "Business"),
        (4, "Cloud"),
    ]

    products = [
        (1, 1, "Python Foundations", 4999, 50, 1),
        (2, 1, "Advanced Python", 6999, 40, 1),
        (3, 2, "SQL Foundations", 3999, 100, 1),
        (4, 2, "Data Analytics", 5999, 60, 1),
        (5, 3, "Product Management", 5499, 30, 1),
        (6, 3, "Business Metrics", 4499, 25, 1),
        (7, 4, "Cloud Fundamentals", 7999, 20, 1),
        (8, 4, "DevOps Foundations", 8999, 15, 0),
    ]

    orders = [
        (1, 1, 1, "2025-07-01 10:30:00", "paid"),
        (2, 2, 1, "2025-07-02 11:10:00", "shipped"),
        (3, 1, 2, "2025-07-04 09:15:00", "paid"),
        (4, 3, 2, "2025-07-06 15:20:00", "cancelled"),
        (5, 4, 1, "2025-07-10 16:45:00", "shipped"),
        (6, 6, 3, "2025-07-12 13:00:00", "paid"),
        (7, 2, 2, "2025-07-15 12:00:00", "pending"),
        (8, 8, 1, "2025-07-20 17:30:00", "paid"),
    ]

    order_items = [
        (1, 3, 1, 3999),
        (1, 1, 1, 4999),
        (2, 4, 1, 5999),
        (2, 6, 2, 4499),
        (3, 2, 1, 6999),
        (3, 3, 2, 3999),
        (4, 7, 1, 7999),
        (5, 5, 1, 5499),
        (5, 3, 1, 3999),
        (6, 1, 1, 4999),
        (6, 4, 1, 5999),
        (7, 7, 1, 7999),
        (8, 2, 1, 6999),
        (8, 5, 1, 5499),
    ]

    payments = [
        (1, 1, 8998, "upi", "2025-07-01 10:31:00", "completed"),
        (2, 2, 14997, "card", "2025-07-02 11:11:00", "completed"),
        (3, 3, 14997, "upi", "2025-07-04 09:16:00", "completed"),
        (4, 4, 7999, "card", "2025-07-06 15:21:00", "refunded"),
        (5, 5, 9498, "upi", "2025-07-10 16:46:00", "completed"),
        (6, 6, 10998, "bank_transfer", "2025-07-12 13:01:00", "completed"),
        (7, 7, 7999, "upi", None, "pending"),
        (8, 8, 12498, "card", "2025-07-20 17:31:00", "completed"),
    ]

    connection.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)", customers
    )
    connection.executemany(
        "INSERT INTO employees VALUES (?, ?, ?, ?)", employees
    )
    connection.executemany(
        "INSERT INTO categories VALUES (?, ?)", categories
    )
    connection.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", products
    )
    connection.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?)", orders
    )
    connection.executemany(
        "INSERT INTO order_items VALUES (?, ?, ?, ?)", order_items
    )
    connection.executemany(
        "INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?)", payments
    )
    connection.commit()


def fundamentals(connection):
    section("1. RELATIONAL DATABASE FUNDAMENTALS")

    print(
        """
A relational database stores data in relations, commonly represented as
tables. A row is a record and a column represents an attribute.

Important terms:
- Database: an organized collection of data.
- Table: a relation containing rows and columns.
- Row: one tuple or record.
- Column: an attribute with a defined meaning and type.
- Primary key: uniquely identifies each row.
- Foreign key: references a key in another table.
- Constraint: a rule enforced by the database.
- Schema: the structural definition of tables, relationships and constraints.
- SQL: Structured Query Language.
- DDL: Data Definition Language such as CREATE and ALTER.
- DML: Data Manipulation Language such as INSERT, UPDATE and DELETE.
- DQL: Data Query Language, commonly represented by SELECT.
- DCL: Data Control Language such as GRANT and REVOKE.
- TCL: Transaction Control Language such as COMMIT and ROLLBACK.

The schema above separates customers, products, orders and payments rather
than duplicating customer or product information in every order.
"""
    )

    subsection("Inspecting the schema")
    execute_and_show(
        connection,
        """
        SELECT name, type
        FROM sqlite_master
        WHERE type IN ('table', 'index', 'view')
        ORDER BY type, name
        """,
    )

    subsection("Selecting columns")
    execute_and_show(
        connection,
        """
        SELECT customer_id, full_name, city
        FROM customers
        ORDER BY customer_id
        """,
    )

    subsection("Aliases and computed expressions")
    execute_and_show(
        connection,
        """
        SELECT
            product_name AS course,
            price,
            price * 0.18 AS tax,
            price * 1.18 AS price_with_tax
        FROM products
        WHERE active = 1
        ORDER BY price DESC
        """,
    )


def filtering_sorting(connection):
    section("2. FILTERING, SORTING AND BASIC EXPRESSIONS")

    subsection("WHERE with comparison operators")
    execute_and_show(
        connection,
        """
        SELECT full_name, city, status
        FROM customers
        WHERE status = 'active' AND city = 'Lucknow'
        """,
    )

    subsection("IN, BETWEEN and LIKE")
    execute_and_show(
        connection,
        """
        SELECT full_name, city
        FROM customers
        WHERE city IN ('Lucknow', 'Delhi', 'Mumbai')
          AND signup_date BETWEEN '2025-01-01' AND '2025-04-30'
        """,
    )

    execute_and_show(
        connection,
        """
        SELECT product_name
        FROM products
        WHERE product_name LIKE '%Python%'
        """,
    )

    subsection("NULL is not an ordinary value")
    execute_and_show(
        connection,
        """
        SELECT order_id, employee_id
        FROM orders
        WHERE employee_id IS NULL
        """,
    )

    print(
        """
Do not write employee_id = NULL. SQL uses three-valued logic:
TRUE, FALSE and UNKNOWN. IS NULL and IS NOT NULL explicitly test nullness.
"""
    )

    subsection("CASE expressions")
    execute_and_show(
        connection,
        """
        SELECT
            product_name,
            price,
            CASE
                WHEN price >= 7000 THEN 'premium'
                WHEN price >= 5000 THEN 'standard'
                ELSE 'entry'
            END AS price_band
        FROM products
        ORDER BY price DESC
        """,
    )


def joins(connection):
    section("3. JOINS AND RELATIONSHIPS")

    subsection("INNER JOIN")
    execute_and_show(
        connection,
        """
        SELECT
            o.order_id,
            c.full_name AS customer,
            o.order_date,
            o.status
        FROM orders AS o
        INNER JOIN customers AS c
            ON c.customer_id = o.customer_id
        ORDER BY o.order_id
        """,
    )

    subsection("Multiple joins")
    execute_and_show(
        connection,
        """
        SELECT
            o.order_id,
            c.full_name AS customer,
            p.product_name,
            oi.quantity,
            oi.unit_price,
            oi.quantity * oi.unit_price AS line_total
        FROM orders AS o
        JOIN customers AS c
            ON c.customer_id = o.customer_id
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        JOIN products AS p
            ON p.product_id = oi.product_id
        WHERE o.status <> 'cancelled'
        ORDER BY o.order_id, p.product_name
        """,
    )

    subsection("LEFT JOIN preserves unmatched rows")
    execute_and_show(
        connection,
        """
        SELECT
            c.customer_id,
            c.full_name,
            COUNT(o.order_id) AS order_count
        FROM customers AS c
        LEFT JOIN orders AS o
            ON o.customer_id = c.customer_id
        GROUP BY c.customer_id, c.full_name
        ORDER BY order_count DESC, c.customer_id
        """,
    )

    print(
        """
INNER JOIN returns matching rows.
LEFT JOIN returns every row from the left table and matching rows from the
right table. Missing right-side data becomes NULL.

A common mistake is putting a LEFT JOIN filter on the right table in WHERE,
which can unintentionally turn it into inner-join behavior.
"""
    )


def aggregation(connection):
    section("4. AGGREGATION AND GROUPING")

    subsection("COUNT, SUM, AVG, MIN and MAX")
    execute_and_show(
        connection,
        """
        SELECT
            COUNT(*) AS total_customers,
            COUNT(DISTINCT city) AS unique_cities
        FROM customers
        """,
    )

    execute_and_show(
        connection,
        """
        SELECT
            c.city,
            COUNT(*) AS customers,
            AVG(CAST(LENGTH(c.full_name) AS REAL)) AS avg_name_length
        FROM customers AS c
        GROUP BY c.city
        HAVING COUNT(*) >= 1
        ORDER BY customers DESC, c.city
        """,
    )

    subsection("Revenue by product")
    execute_and_show(
        connection,
        """
        SELECT
            p.product_name,
            SUM(oi.quantity) AS units_sold,
            SUM(oi.quantity * oi.unit_price) AS revenue
        FROM order_items AS oi
        JOIN products AS p
            ON p.product_id = oi.product_id
        JOIN orders AS o
            ON o.order_id = oi.order_id
        WHERE o.status IN ('paid', 'shipped')
        GROUP BY p.product_id, p.product_name
        HAVING SUM(oi.quantity * oi.unit_price) >= 5000
        ORDER BY revenue DESC
        """,
    )

    print(
        """
WHERE filters individual rows before grouping.
HAVING filters groups after aggregation.

COUNT(*) counts rows. COUNT(column) ignores NULL values.
COUNT(DISTINCT column) counts unique non-NULL values.
"""
    )


def subqueries_and_ctes(connection):
    section("5. SUBQUERIES AND COMMON TABLE EXPRESSIONS")

    subsection("Scalar subquery")
    execute_and_show(
        connection,
        """
        SELECT
            product_name,
            price
        FROM products
        WHERE price > (
            SELECT AVG(price)
            FROM products
        )
        ORDER BY price DESC
        """,
    )

    subsection("Correlated subquery")
    execute_and_show(
        connection,
        """
        SELECT
            c.full_name,
            (
                SELECT COUNT(*)
                FROM orders AS o
                WHERE o.customer_id = c.customer_id
            ) AS order_count
        FROM customers AS c
        ORDER BY order_count DESC
        """,
    )

    subsection("CTE")
    execute_and_show(
        connection,
        """
        WITH order_totals AS (
            SELECT
                o.order_id,
                o.customer_id,
                SUM(oi.quantity * oi.unit_price) AS order_total
            FROM orders AS o
            JOIN order_items AS oi
                ON oi.order_id = o.order_id
            WHERE o.status <> 'cancelled'
            GROUP BY o.order_id, o.customer_id
        )
        SELECT
            c.full_name,
            COUNT(ot.order_id) AS orders,
            COALESCE(SUM(ot.order_total), 0) AS customer_revenue
        FROM customers AS c
        LEFT JOIN order_totals AS ot
            ON ot.customer_id = c.customer_id
        GROUP BY c.customer_id, c.full_name
        ORDER BY customer_revenue DESC
        """,
    )


def window_functions(connection):
    section("6. WINDOW FUNCTIONS")

    subsection("Ranking without collapsing rows")
    execute_and_show(
        connection,
        """
        SELECT
            product_name,
            price,
            RANK() OVER (ORDER BY price DESC) AS price_rank,
            DENSE_RANK() OVER (ORDER BY price DESC) AS dense_price_rank
        FROM products
        ORDER BY price_rank
        """,
    )

    subsection("Partitioned ranking")
    execute_and_show(
        connection,
        """
        SELECT
            c.category_name,
            p.product_name,
            p.price,
            ROW_NUMBER() OVER (
                PARTITION BY p.category_id
                ORDER BY p.price DESC
            ) AS category_position
        FROM products AS p
        JOIN categories AS c
            ON c.category_id = p.category_id
        ORDER BY c.category_name, category_position
        """,
    )

    subsection("Running totals")
    execute_and_show(
        connection,
        """
        WITH daily_sales AS (
            SELECT
                substr(o.order_date, 1, 10) AS sales_date,
                SUM(oi.quantity * oi.unit_price) AS revenue
            FROM orders AS o
            JOIN order_items AS oi
                ON oi.order_id = o.order_id
            WHERE o.status IN ('paid', 'shipped')
            GROUP BY substr(o.order_date, 1, 10)
        )
        SELECT
            sales_date,
            revenue,
            SUM(revenue) OVER (
                ORDER BY sales_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cumulative_revenue
        FROM daily_sales
        ORDER BY sales_date
        """,
    )


def views_and_reusable_queries(connection):
    section("7. VIEWS AND REUSABLE DATABASE LOGIC")

    connection.execute(
        """
        CREATE VIEW customer_order_summary AS
        SELECT
            c.customer_id,
            c.full_name,
            c.city,
            COUNT(o.order_id) AS order_count,
            COALESCE(
                SUM(
                    CASE
                        WHEN o.status <> 'cancelled'
                        THEN (
                            SELECT COALESCE(SUM(oi.quantity * oi.unit_price), 0)
                            FROM order_items AS oi
                            WHERE oi.order_id = o.order_id
                        )
                        ELSE 0
                    END
                ),
                0
            ) AS gross_order_value
        FROM customers AS c
        LEFT JOIN orders AS o
            ON o.customer_id = c.customer_id
        GROUP BY c.customer_id, c.full_name, c.city
        """
    )

    execute_and_show(
        connection,
        """
        SELECT *
        FROM customer_order_summary
        ORDER BY gross_order_value DESC
        """,
    )

    print(
        """
A view stores a query definition rather than a separate copy of its result.
Views can simplify reporting queries and provide controlled interfaces over
complex joins. They are not automatically materialized tables.
"""
    )


def constraints_and_validation(connection):
    section("8. CONSTRAINTS, VALIDATION AND FAILURE CONDITIONS")

    subsection("NOT NULL and CHECK")
    try:
        connection.execute(
            """
            INSERT INTO products
                (product_id, category_id, product_name, price, stock_quantity)
            VALUES
                (999, 1, 'Invalid Course', -100, 10)
            """
        )
    except sqlite3.IntegrityError as error:
        print("Expected constraint failure:", error)

    subsection("UNIQUE")
    try:
        connection.execute(
            """
            INSERT INTO customers
                (customer_id, full_name, email, city, signup_date)
            VALUES
                (999, 'Duplicate', 'aarav@example.com', 'Delhi', '2025-08-01')
            """
        )
    except sqlite3.IntegrityError as error:
        print("Expected unique failure:", error)

    subsection("FOREIGN KEY")
    try:
        connection.execute(
            """
            INSERT INTO orders
                (order_id, customer_id, employee_id, order_date, status)
            VALUES
                (999, 99999, 1, '2025-08-01 10:00:00', 'pending')
            """
        )
    except sqlite3.IntegrityError as error:
        print("Expected foreign-key failure:", error)

    subsection("Application validation with parameterized SQL")
    email = "new.customer@example.com"
    city = "Kanpur"

    if "@" not in email:
        raise ValueError("Invalid email address")

    connection.execute(
        """
        INSERT INTO customers
            (full_name, email, city, signup_date, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("New Customer", email, city, "2025-08-01", "active"),
    )
    connection.commit()

    print("Parameterized insert succeeded.")

    print(
        """
Parameterized queries are important because SQL syntax and data values are
kept separate. Never build SQL by concatenating untrusted user input.

For production systems, validate data at both application and database
boundaries. Database constraints protect integrity even when another client
writes to the database.
"""
    )


def transactions(connection):
    section("9. TRANSACTIONS AND ATOMICITY")

    subsection("Successful transaction")
    before = connection.execute(
        "SELECT stock_quantity FROM products WHERE product_id = 1"
    ).fetchone()[0]

    with transaction(connection):
        connection.execute(
            """
            UPDATE products
            SET stock_quantity = stock_quantity - ?
            WHERE product_id = ?
              AND stock_quantity >= ?
            """,
            (2, 1, 2),
        )

    after = connection.execute(
        "SELECT stock_quantity FROM products WHERE product_id = 1"
    ).fetchone()[0]

    print("Stock before:", before)
    print("Stock after :", after)

    subsection("Rollback after failure")
    original = connection.execute(
        "SELECT stock_quantity FROM products WHERE product_id = 2"
    ).fetchone()[0]

    try:
        with transaction(connection):
            connection.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity - 1
                WHERE product_id = 2
                  AND stock_quantity >= 1
                """
            )
            raise RuntimeError("Simulated payment failure")
    except RuntimeError as error:
        print("Transaction aborted:", error)

    restored = connection.execute(
        "SELECT stock_quantity FROM products WHERE product_id = 2"
    ).fetchone()[0]

    print("Stock before failed transaction:", original)
    print("Stock after rollback:", restored)

    print(
        """
ACID:
- Atomicity: all statements in a transaction succeed or the transaction is
  rolled back.
- Consistency: constraints and rules preserve valid database states.
- Isolation: concurrent transactions should not incorrectly interfere.
- Durability: committed changes survive normal system failure.

Exact isolation behavior depends on the database engine and configuration.
SQLite's locking and transaction model differs from server databases such as
PostgreSQL and MySQL.
"""
    )


def update_delete_and_upsert(connection):
    section("10. UPDATE, DELETE AND UPSERT")

    subsection("Safe UPDATE")
    connection.execute(
        """
        UPDATE products
        SET price = price * 1.05
        WHERE category_id = ?
          AND active = 1
        """,
        (1,),
    )
    connection.commit()

    execute_and_show(
        connection,
        """
        SELECT product_name, price
        FROM products
        WHERE category_id = 1
        ORDER BY product_id
        """,
    )

    subsection("UPSERT")
    connection.execute(
        """
        INSERT INTO categories(category_id, category_name)
        VALUES (?, ?)
        ON CONFLICT(category_id)
        DO UPDATE SET category_name = excluded.category_name
        """,
        (4, "Cloud Computing"),
    )
    connection.commit()

    execute_and_show(
        connection,
        "SELECT * FROM categories ORDER BY category_id",
    )

    print(
        """
DELETE permanently removes matching rows unless the transaction is rolled
back. UPDATE without a WHERE clause can modify every row, so destructive
operations should be reviewed and tested carefully.
"""
    )


def normalization_demo():
    section("11. NORMALIZATION AND DATA MODELING")

    print(
        """
Consider an unnormalized order record:

order_id | customer_name | customer_email | product1 | product2 | product3

Problems:
- Repeating groups make the number of products fixed.
- Customer data is duplicated.
- Product information is difficult to update consistently.
- Searching and aggregating become awkward.

A normalized design separates entities:
customers
products
orders
order_items

Typical normalization goals:
1NF: atomic values and no repeating groups.
2NF: non-key attributes depend on the whole key.
3NF: non-key attributes should not depend transitively on another non-key
attribute.

Normalization reduces redundancy and update anomalies. Excessive
normalization can increase join complexity, so analytical systems sometimes
intentionally denormalize data for read performance.
"""
    )


def date_text_demo(connection):
    section("12. DATES, TEXT AND SQL EXPRESSIONS")

    subsection("Date filtering")
    execute_and_show(
        connection,
        """
        SELECT order_id, order_date
        FROM orders
        WHERE order_date >= '2025-07-10'
        ORDER BY order_date
        """,
    )

    subsection("String functions")
    execute_and_show(
        connection,
        """
        SELECT
            full_name,
            UPPER(full_name) AS uppercase_name,
            LENGTH(full_name) AS character_count
        FROM customers
        ORDER BY character_count DESC
        LIMIT 5
        """,
    )

    print(
        """
SQLite commonly stores dates as TEXT, REAL or INTEGER rather than having a
separate strict DATE storage class. Server databases may have dedicated date,
time and timestamp types. Always understand the type and timezone behavior
of the database engine being used.
"""
    )


def advanced_reporting(connection):
    section("13. ADVANCED REPORTING QUERY")

    query = """
    WITH valid_lines AS (
        SELECT
            o.order_id,
            o.customer_id,
            substr(o.order_date, 1, 10) AS order_day,
            oi.product_id,
            oi.quantity,
            oi.unit_price,
            oi.quantity * oi.unit_price AS line_total
        FROM orders AS o
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status IN ('paid', 'shipped')
    ),
    customer_revenue AS (
        SELECT
            customer_id,
            SUM(line_total) AS revenue
        FROM valid_lines
        GROUP BY customer_id
    )
    SELECT
        c.full_name,
        c.city,
        cr.revenue,
        RANK() OVER (ORDER BY cr.revenue DESC) AS revenue_rank,
        CASE
            WHEN cr.revenue >= 15000 THEN 'high value'
            WHEN cr.revenue >= 8000 THEN 'medium value'
            ELSE 'standard'
        END AS customer_segment
    FROM customer_revenue AS cr
    JOIN customers AS c
        ON c.customer_id = cr.customer_id
    ORDER BY revenue_rank;
    """

    execute_and_show(connection, query)

    print(
        """
This report combines:
- CTEs for readable intermediate datasets.
- JOINs for relationships.
- aggregation for revenue.
- CASE for business classification.
- a window function for ranking.

This illustrates how SQL expresses business logic close to the data.
"""


def parameterization_demo(connection):
    section("14. PARAMETERIZED QUERIES AND SQL INJECTION")

    city = "Lucknow"

    # The ? placeholder tells the database that the value is data, not SQL.
    execute_and_show(
        connection,
        """
        SELECT customer_id, full_name, email
        FROM customers
        WHERE city = ?
        """,
        (city,),
    )

    malicious_input = "' OR 1=1 --"

    safe_rows = execute_and_show(
        connection,
        """
        SELECT customer_id, full_name
        FROM customers
        WHERE email = ?
        """,
        (malicious_input,),
    )

    print("Rows returned for malicious-looking input:", len(safe_rows))

    print(
        """
Unsafe pattern:
    SQL = "SELECT ... WHERE email = '" + user_input + "'"

Safe pattern:
    SQL = "SELECT ... WHERE email = ?"
    execute(SQL, (user_input,))

Parameterized queries are one of the most important protections against SQL
injection. They do not replace authorization, input validation or secure
database permissions.
"""
    )


def performance_demo(connection):
    section("15. INDEXES AND QUERY PERFORMANCE")

    subsection("Query plan for an indexed predicate")
    query = """
    SELECT order_id, customer_id, order_date
    FROM orders
    WHERE customer_id = ?
    ORDER BY order_date
    """
    explain_sql(connection, query, (2,))

    subsection("Query plan for city lookup")
    explain_sql(
        connection,
        """
        SELECT customer_id, full_name
        FROM customers
        WHERE city = ?
        """,
        ("Lucknow",),
    )

    print(
        """
Indexes provide faster lookup paths for suitable predicates, joins and
ordering operations. They also consume storage and make INSERT, UPDATE and
DELETE operations more expensive because indexes must be maintained.

Good indexing decisions depend on actual workload:
- Index frequently filtered columns.
- Index useful foreign keys where joins benefit.
- Consider composite indexes for common multi-column access patterns.
- Avoid creating indexes for every column.
- Inspect query plans.
- Benchmark realistic data volumes.

The order of columns in a composite index matters. The index
(customer_id, order_date) is especially useful for queries filtering by
customer_id and then ordering or filtering by order_date.
"""
    )


def database_metadata(connection):
    section("16. DATABASE METADATA")

    subsection("Table definitions")
    tables = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    for (table_name,) in tables:
        print(f"\n{table_name}:")
        cursor = connection.execute(f"PRAGMA table_info({table_name})")
        for row in cursor.fetchall():
            print(row)

    subsection("Foreign-key relationships")
    for table_name in [row[0] for row in tables]:
        print(f"\n{table_name}:")
        for row in connection.execute(
            f"PRAGMA foreign_key_list({table_name})"
        ).fetchall():
            print(row)


def mini_test_suite(connection):
    section("17. SIMPLE DATABASE TESTS")

    tests = []

    def test(name, condition):
        tests.append((name, bool(condition)))

    customer_count = connection.execute(
        "SELECT COUNT(*) FROM customers"
    ).fetchone()[0]
    test("customers exist", customer_count >= 8)

    duplicate_emails = connection.execute(
        """
        SELECT email, COUNT(*)
        FROM customers
        GROUP BY email
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    test("emails are unique", len(duplicate_emails) == 0)

    invalid_products = connection.execute(
        """
        SELECT COUNT(*)
        FROM products
        WHERE price < 0 OR stock_quantity < 0
        """
    ).fetchone()[0]
    test("product financial values are valid", invalid_products == 0)

    orphan_orders = connection.execute(
        """
        SELECT COUNT(*)
        FROM orders AS o
        LEFT JOIN customers AS c
            ON c.customer_id = o.customer_id
        WHERE c.customer_id IS NULL
        """
    ).fetchone()[0]
    test("orders have valid customers", orphan_orders == 0)

    for name, passed in tests:
        print(f"{'PASS' if passed else 'FAIL'}: {name}")

    assert all(passed for _, passed in tests)


def practical_order_transaction(connection):
    section("18. PRACTICAL ORDER CREATION TRANSACTION")

    new_customer_id = 20
    new_order_id = 20

    try:
        with transaction(connection):
            connection.execute(
                """
                INSERT INTO customers
                    (customer_id, full_name, email, city, signup_date, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    new_customer_id,
                    "Transaction Customer",
                    "transaction@example.com",
                    "Lucknow",
                    "2025-08-05",
                    "active",
                ),
            )

            connection.execute(
                """
                INSERT INTO orders
                    (order_id, customer_id, employee_id, order_date, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    new_order_id,
                    new_customer_id,
                    1,
                    "2025-08-05 10:00:00",
                    "paid",
                ),
            )

            product_id = 3
            quantity = 2

            product = connection.execute(
                """
                SELECT price, stock_quantity
                FROM products
                WHERE product_id = ?
                """,
                (product_id,),
            ).fetchone()

            if product is None:
                raise ValueError("Product does not exist")

            price, stock = product
            if stock < quantity:
                raise ValueError("Insufficient stock")

            connection.execute(
                """
                INSERT INTO order_items
                    (order_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
                """,
                (new_order_id, product_id, quantity, price),
            )

            connection.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity - ?
                WHERE product_id = ?
                """,
                (quantity, product_id),
            )

            total = price * quantity

            connection.execute(
                """
                INSERT INTO payments
                    (order_id, amount, payment_method, paid_at, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    new_order_id,
                    total,
                    "upi",
                    "2025-08-05 10:01:00",
                    "completed",
                ),
            )

        print("Complete order transaction committed.")
    except (sqlite3.Error, ValueError) as error:
        print("Order transaction failed:", error)

    execute_and_show(
        connection,
        """
        SELECT
            o.order_id,
            c.full_name,
            p.product_name,
            oi.quantity,
            oi.unit_price,
            oi.quantity * oi.unit_price AS total
        FROM orders AS o
        JOIN customers AS c ON c.customer_id = o.customer_id
        JOIN order_items AS oi ON oi.order_id = o.order_id
        JOIN products AS p ON p.product_id = oi.product_id
        WHERE o.order_id = ?
        """,
        (new_order_id,),
    )


def common_mistakes():
    section("19. COMMON SQL MISTAKES")

    mistakes = {
        "Missing WHERE on UPDATE/DELETE":
            "May modify every row. Test the SELECT equivalent first.",
        "Using = NULL":
            "Use IS NULL or IS NOT NULL.",
        "Ambiguous column names":
            "Use table aliases such as c.customer_id.",
        "Filtering a LEFT JOIN in WHERE":
            "Can remove unmatched rows. Place right-side conditions in ON when appropriate.",
        "SELECT * in production APIs":
            "Explicit columns make contracts clearer and reduce unnecessary data transfer.",
        "String concatenation for SQL":
            "Use parameterized queries.",
        "Ignoring transactions":
            "Multi-step business operations can leave partial state.",
        "Over-indexing":
            "Indexes consume resources and slow writes.",
        "No constraints":
            "Application bugs can create invalid or orphaned data.",
        "Assuming SQL is identical everywhere":
            "Syntax, types, functions, isolation and optimizer behavior vary by engine.",
        "Confusing WHERE and HAVING":
            "WHERE filters rows; HAVING filters aggregate groups.",
        "Accidental Cartesian product":
            "A missing or incorrect join condition can multiply rows dramatically.",
    }

    for mistake, explanation in mistakes.items():
        print(f"\n{mistake}\n  {explanation}")


def production_considerations():
    section("20. PRODUCTION DATABASE CONSIDERATIONS")

    print(
        """
A production relational database requires more than correct SELECT queries.

Schema design:
- Choose stable primary keys.
- Define foreign keys deliberately.
- Use NOT NULL, UNIQUE and CHECK constraints for invariants.
- Normalize transactional data where appropriate.
- Document business rules.

Security:
- Use least-privilege database accounts.
- Parameterize SQL.
- Never expose database credentials in source control.
- Encrypt connections when supported and required.
- Restrict network access.
- Protect backups.
- Audit sensitive operations.
- Avoid returning unnecessary personal information.

Reliability:
- Use transactions for atomic workflows.
- Define backup and restore procedures.
- Test restores rather than assuming backups work.
- Understand replication and failover if using a server database.
- Monitor storage, locks, query latency and error rates.

Performance:
- Inspect query plans.
- Measure before optimizing.
- Index based on real workload.
- Avoid unbounded result sets.
- Use pagination for large API responses.
- Select only required columns.
- Keep transactions reasonably short.

Operations:
- Use schema migrations rather than manually changing production tables.
- Separate development, testing and production databases.
- Record migration versions.
- Test migrations against realistic data.
- Monitor slow queries.

Portability:
SQLite is excellent for learning, embedded applications and small workloads.
PostgreSQL and MySQL are common server-side relational systems with different
features, concurrency models, operational requirements and SQL dialects.
"""
    )


def run():
    section("SQL FOUNDATIONS PROJECT")
    print(
        "Building a complete relational database with Python's sqlite3 module."
    )

    connection = sqlite3.connect(DATABASE_NAME)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        create_schema(connection)
        seed_data(connection)

        fundamentals(connection)
        filtering_sorting(connection)
        joins(connection)
        aggregation(connection)
        subqueries_and_ctes(connection)
        window_functions(connection)
        views_and_reusable_queries(connection)
        constraints_and_validation(connection)
        transactions(connection)
        update_delete_and_upsert(connection)
        normalization_demo()
        date_text_demo(connection)
        advanced_reporting(connection)
        parameterization_demo(connection)
        performance_demo(connection)
        database_metadata(connection)
        practical_order_transaction(connection)
        mini_test_suite(connection)
        common_mistakes()
        production_considerations()

        section("FINAL DATABASE CHECK")
        execute_and_show(
            connection,
            """
            SELECT
                (SELECT COUNT(*) FROM customers) AS customers,
                (SELECT COUNT(*) FROM products) AS products,
                (SELECT COUNT(*) FROM orders) AS orders,
                (SELECT COUNT(*) FROM order_items) AS order_items,
                (SELECT COUNT(*) FROM payments) AS payments
            """,
        )

        print(
            "\nThe complete SQL foundations demonstration executed successfully."
        )

    finally:
        connection.close()


if __name__ == "__main__":
    run()
