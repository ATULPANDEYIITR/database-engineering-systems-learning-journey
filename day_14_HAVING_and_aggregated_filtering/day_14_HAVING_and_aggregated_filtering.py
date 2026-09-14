"""
HAVING and Aggregated Filtering
================================

A self-contained study file for learning SQL HAVING, GROUP BY, aggregate
functions, grouped conditions, aggregation logic, and related advanced
patterns.

The examples use Python's built-in sqlite3 module, so no external package
is required.

Run:
    python having_and_aggregated_filtering.py

The script progresses from SQL fundamentals to advanced aggregation patterns,
edge cases, debugging, performance, and production-oriented considerations.
"""

import sqlite3
from pprint import pprint


DATABASE = ":memory:"


def print_title(title):
    """Print a readable section heading."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_rows(rows, columns=None):
    """Display query results in a simple tabular form."""
    if not rows:
        print("(no rows)")
        return

    if columns is None:
        columns = rows[0].keys() if hasattr(rows[0], "keys") else None

    if columns is None:
        for row in rows:
            print(row)
        return

    columns = list(columns)
    widths = []

    for column in columns:
        maximum = len(str(column))
        for row in rows:
            maximum = max(maximum, len(str(row[column])))
        widths.append(maximum)

    header = " | ".join(
        str(column).ljust(width)
        for column, width in zip(columns, widths)
    )
    separator = "-+-".join("-" * width for width in widths)

    print(header)
    print(separator)

    for row in rows:
        print(
            " | ".join(
                str(row[column]).ljust(width)
                for column, width in zip(columns, widths)
            )
        )


def execute_query(connection, sql, parameters=(), show_sql=True):
    """Execute a SELECT query and display its results."""
    if show_sql:
        print("\nSQL:")
        print(sql.strip())

    try:
        cursor = connection.execute(sql, parameters)
        rows = cursor.fetchall()
        print_rows(rows, [description[0] for description in cursor.description])
        return rows
    except sqlite3.Error as error:
        print(f"SQL error: {error}")
        return []


def execute_script(connection, sql):
    """Execute schema or data-definition SQL."""
    connection.executescript(sql)


def create_database():
    """Create a realistic sales database used throughout the examples."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    schema = """
    PRAGMA foreign_keys = ON;

    CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY,
        customer_name TEXT NOT NULL,
        city TEXT NOT NULL,
        customer_segment TEXT NOT NULL
            CHECK (customer_segment IN ('Consumer', 'Business', 'Enterprise'))
    );

    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        unit_price REAL NOT NULL CHECK (unit_price >= 0)
    );

    CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        order_date TEXT NOT NULL,
        status TEXT NOT NULL
            CHECK (status IN ('Completed', 'Pending', 'Cancelled', 'Returned')),
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    );

    CREATE TABLE order_items (
        order_item_id INTEGER PRIMARY KEY,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        unit_price REAL NOT NULL CHECK (unit_price >= 0),
        discount_percent REAL NOT NULL DEFAULT 0
            CHECK (discount_percent BETWEEN 0 AND 100),
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    );
    """

    execute_script(connection, schema)

    customers = [
        (1, "Aarav Industries", "Delhi", "Enterprise"),
        (2, "Blue Retail", "Mumbai", "Business"),
        (3, "Cedar Stores", "Delhi", "Consumer"),
        (4, "Delta Technologies", "Bengaluru", "Enterprise"),
        (5, "Evergreen Traders", "Lucknow", "Business"),
        (6, "Futura Labs", "Hyderabad", "Enterprise"),
        (7, "Green Basket", "Pune", "Consumer"),
        (8, "Horizon Services", "Mumbai", "Business"),
        (9, "Indigo Mart", "Lucknow", "Consumer"),
        (10, "Jupiter Systems", "Chennai", "Enterprise"),
    ]

    products = [
        (1, "Laptop", "Electronics", 75000),
        (2, "Monitor", "Electronics", 22000),
        (3, "Keyboard", "Accessories", 3500),
        (4, "Mouse", "Accessories", 1800),
        (5, "Office Chair", "Furniture", 12000),
        (6, "Desk", "Furniture", 18000),
        (7, "Printer", "Electronics", 28000),
        (8, "Notebook", "Stationery", 250),
    ]

    orders = [
        (1, 1, "2026-01-05", "Completed"),
        (2, 1, "2026-01-12", "Completed"),
        (3, 1, "2026-02-10", "Completed"),
        (4, 2, "2026-01-08", "Completed"),
        (5, 2, "2026-02-15", "Completed"),
        (6, 3, "2026-01-20", "Completed"),
        (7, 3, "2026-02-21", "Returned"),
        (8, 4, "2026-01-11", "Completed"),
        (9, 4, "2026-02-02", "Completed"),
        (10, 4, "2026-03-01", "Completed"),
        (11, 5, "2026-01-25", "Completed"),
        (12, 5, "2026-02-25", "Pending"),
        (13, 6, "2026-01-17", "Completed"),
        (14, 6, "2026-02-18", "Completed"),
        (15, 7, "2026-02-05", "Completed"),
        (16, 8, "2026-01-29", "Completed"),
        (17, 8, "2026-02-28", "Completed"),
        (18, 9, "2026-01-30", "Cancelled"),
        (19, 9, "2026-03-04", "Completed"),
        (20, 10, "2026-01-07", "Completed"),
        (21, 10, "2026-02-07", "Completed"),
        (22, 10, "2026-03-07", "Completed"),
    ]

    order_items = [
        (1, 1, 1, 2, 75000, 5),
        (2, 1, 3, 5, 3500, 0),
        (3, 2, 2, 3, 22000, 10),
        (4, 2, 5, 2, 12000, 0),
        (5, 3, 1, 1, 75000, 0),
        (6, 3, 7, 2, 28000, 5),
        (7, 4, 4, 10, 1800, 0),
        (8, 4, 8, 30, 250, 0),
        (9, 5, 5, 4, 12000, 5),
        (10, 5, 6, 2, 18000, 0),
        (11, 6, 8, 50, 250, 0),
        (12, 7, 8, 20, 250, 0),
        (13, 8, 1, 3, 75000, 8),
        (14, 8, 2, 5, 22000, 5),
        (15, 9, 7, 4, 28000, 10),
        (16, 9, 3, 10, 3500, 0),
        (17, 10, 1, 2, 75000, 10),
        (18, 10, 6, 3, 18000, 5),
        (19, 11, 5, 5, 12000, 0),
        (20, 11, 4, 10, 1800, 0),
        (21, 12, 2, 2, 22000, 0),
        (22, 13, 7, 3, 28000, 5),
        (23, 13, 1, 1, 75000, 0),
        (24, 14, 2, 4, 22000, 10),
        (25, 14, 1, 2, 75000, 5),
        (26, 15, 8, 100, 250, 0),
        (27, 16, 6, 5, 18000, 10),
        (28, 16, 5, 5, 12000, 5),
        (29, 17, 1, 2, 75000, 0),
        (30, 17, 7, 1, 28000, 0),
        (31, 18, 3, 10, 3500, 0),
        (32, 19, 2, 2, 22000, 0),
        (33, 19, 4, 20, 1800, 5),
        (34, 20, 1, 4, 75000, 12),
        (35, 20, 2, 6, 22000, 10),
        (36, 21, 7, 2, 28000, 0),
        (37, 21, 6, 2, 18000, 0),
        (38, 22, 1, 3, 75000, 5),
        (39, 22, 2, 2, 22000, 5),
    ]

    connection.executemany(
        """
        INSERT INTO customers
        (customer_id, customer_name, city, customer_segment)
        VALUES (?, ?, ?, ?)
        """,
        customers,
    )

    connection.executemany(
        """
        INSERT INTO products
        (product_id, product_name, category, unit_price)
        VALUES (?, ?, ?, ?)
        """,
        products,
    )

    connection.executemany(
        """
        INSERT INTO orders
        (order_id, customer_id, order_date, status)
        VALUES (?, ?, ?, ?)
        """,
        orders,
    )

    connection.executemany(
        """
        INSERT INTO order_items
        (order_item_id, order_id, product_id, quantity, unit_price, discount_percent)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        order_items,
    )

    connection.commit()
    return connection


def section_01_foundations(connection):
    print_title("1. SQL aggregation foundations")

    execute_query(
        connection,
        """
        SELECT
            COUNT(*) AS total_orders
        FROM orders;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            COUNT(*) AS total_customers,
            COUNT(DISTINCT city) AS cities,
            COUNT(DISTINCT customer_segment) AS segments
        FROM customers;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            SUM(quantity) AS total_units,
            AVG(unit_price) AS average_item_price,
            MIN(unit_price) AS lowest_price,
            MAX(unit_price) AS highest_price
        FROM order_items;
        """,
    )

    print(
        """
Aggregate functions reduce multiple input rows into a value.

Common aggregate functions:
    COUNT(*)       Counts rows.
    COUNT(column)  Counts non-NULL values in a column.
    COUNT(DISTINCT column)
                    Counts unique non-NULL values.
    SUM(column)    Adds numeric values.
    AVG(column)    Calculates the arithmetic mean.
    MIN(column)    Finds the smallest value.
    MAX(column)    Finds the largest value.

HAVING becomes important when an aggregate result itself must be filtered.
"""
    )


def section_02_where_vs_having(connection):
    print_title("2. WHERE versus HAVING")

    print(
        """
WHERE filters individual rows before grouping.

HAVING filters groups after GROUP BY and aggregation.

Conceptual order:
    FROM
    WHERE
    GROUP BY
    HAVING
    SELECT
    ORDER BY
    LIMIT

A useful mental model is:

    WHERE -> Which source rows participate?
    GROUP BY -> How are participating rows grouped?
    HAVING -> Which resulting groups survive?
"""
    )

    execute_query(
        connection,
        """
        SELECT
            status,
            COUNT(*) AS order_count
        FROM orders
        WHERE status = 'Completed'
        GROUP BY status;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS completed_orders
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id
        HAVING COUNT(*) >= 2
        ORDER BY completed_orders DESC;
        """,
    )

    print(
        """
The second query demonstrates both clauses:

    WHERE status = 'Completed'

removes non-completed orders before grouping.

Then:

    HAVING COUNT(*) >= 2

keeps only customers whose remaining completed-order group contains
at least two rows.
"""
    )


def section_03_basic_having(connection):
    print_title("3. Basic HAVING examples")

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY customer_id
        HAVING COUNT(*) > 1
        ORDER BY order_count DESC;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY customer_id
        HAVING COUNT(*) = 3
        ORDER BY customer_id;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            status,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY status
        HAVING COUNT(*) >= 2
        ORDER BY order_count DESC;
        """,
    )


def section_04_grouped_revenue(connection):
    print_title("4. Filtering groups by calculated revenue")

    revenue_expression = """
        oi.quantity * oi.unit_price *
        (1 - oi.discount_percent / 100.0)
    """

    execute_query(
        connection,
        f"""
        SELECT
            o.customer_id,
            ROUND(SUM({revenue_expression}), 2) AS revenue
        FROM orders AS o
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'Completed'
        GROUP BY o.customer_id
        HAVING SUM({revenue_expression}) >= 100000
        ORDER BY revenue DESC;
        """,
    )

    print(
        """
The important distinction is that revenue is calculated across many rows
for each customer. HAVING evaluates the aggregate result for each group.

The expression:

    SUM(quantity * unit_price * (1 - discount_percent / 100.0))

is a group-level calculation.

A WHERE condition cannot directly perform the same role:

    WHERE SUM(...) >= 100000

is invalid in standard SQL because SUM(...) does not exist at the
row-filtering stage.
"""
    )


def section_05_multiple_having_conditions(connection):
    print_title("5. Multiple conditions in HAVING")

    revenue_expression = """
        oi.quantity * oi.unit_price *
        (1 - oi.discount_percent / 100.0)
    """

    execute_query(
        connection,
        f"""
        SELECT
            o.customer_id,
            COUNT(DISTINCT o.order_id) AS completed_orders,
            SUM(oi.quantity) AS units,
            ROUND(SUM({revenue_expression}), 2) AS revenue
        FROM orders AS o
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'Completed'
        GROUP BY o.customer_id
        HAVING COUNT(DISTINCT o.order_id) >= 2
           AND SUM(oi.quantity) >= 5
           AND SUM({revenue_expression}) >= 100000
        ORDER BY revenue DESC;
        """,
    )

    execute_query(
        connection,
        f"""
        SELECT
            o.customer_id,
            COUNT(DISTINCT o.order_id) AS completed_orders,
            ROUND(SUM({revenue_expression}), 2) AS revenue
        FROM orders AS o
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'Completed'
        GROUP BY o.customer_id
        HAVING COUNT(DISTINCT o.order_id) >= 2
           OR SUM({revenue_expression}) >= 200000
        ORDER BY revenue DESC;
        """,
    )

    print(
        """
HAVING supports Boolean logic:

    AND  -> every condition must be true.
    OR   -> at least one condition must be true.
    NOT  -> negates a condition.

Parentheses should be used when mixing AND and OR so the intended
precedence is explicit.
"""
    )


def section_06_having_without_group_by(connection):
    print_title("6. HAVING without GROUP BY")

    execute_query(
        connection,
        """
        SELECT
            COUNT(*) AS completed_orders
        FROM orders
        WHERE status = 'Completed'
        HAVING COUNT(*) >= 10;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            COUNT(*) AS completed_orders
        FROM orders
        WHERE status = 'Completed'
        HAVING COUNT(*) >= 100;
        """,
    )

    print(
        """
Without GROUP BY, the entire filtered result can be treated as one
aggregate group.

This makes:

    SELECT COUNT(*)
    FROM orders
    WHERE status = 'Completed'
    HAVING COUNT(*) >= 10;

a test of whether the complete filtered dataset satisfies the condition.

If the HAVING condition is false, the aggregate group produces no output row.

This is useful for threshold checks, although application code or EXISTS
may sometimes communicate the intent more clearly.
"""
    )


def section_07_count_variants(connection):
    print_title("7. COUNT(*) versus COUNT(column) versus COUNT(DISTINCT ...)")

    execute_query(
        connection,
        """
        SELECT
            COUNT(*) AS all_order_rows,
            COUNT(status) AS non_null_status_values,
            COUNT(DISTINCT status) AS distinct_statuses
        FROM orders;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            city,
            COUNT(*) AS customer_count
        FROM customers
        GROUP BY city
        HAVING COUNT(*) >= 2
        ORDER BY customer_count DESC, city;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(DISTINCT order_date) AS active_days
        FROM orders
        GROUP BY customer_id
        HAVING COUNT(DISTINCT order_date) >= 2
        ORDER BY active_days DESC;
        """,
    )

    print(
        """
COUNT(*) counts rows.

COUNT(column) ignores NULL values.

COUNT(DISTINCT column) counts unique non-NULL values.

These are not interchangeable. In grouped filtering, choosing the wrong
COUNT variant can change which groups satisfy HAVING.
"""
    )


def section_08_nulls(connection):
    print_title("8. NULL behavior in aggregation and HAVING")

    connection.execute(
        """
        CREATE TABLE null_demo (
            group_name TEXT,
            amount REAL
        );
        """
    )

    connection.executemany(
        """
        INSERT INTO null_demo (group_name, amount)
        VALUES (?, ?);
        """,
        [
            ("A", 10),
            ("A", None),
            ("A", 20),
            ("B", None),
            ("B", None),
            ("C", 50),
        ],
    )
    connection.commit()

    execute_query(
        connection,
        """
        SELECT
            group_name,
            COUNT(*) AS row_count,
            COUNT(amount) AS amount_count,
            SUM(amount) AS total,
            AVG(amount) AS average
        FROM null_demo
        GROUP BY group_name
        ORDER BY group_name;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            group_name,
            SUM(amount) AS total
        FROM null_demo
        GROUP BY group_name
        HAVING SUM(amount) > 15
        ORDER BY group_name;
        """,
    )

    print(
        """
Most numeric aggregates ignore NULL values.

For group B, SUM(amount) is NULL because there are no non-NULL amounts.
A comparison such as:

    SUM(amount) > 15

does not evaluate to TRUE for NULL. SQL uses three-valued logic:
TRUE, FALSE, and UNKNOWN.

HAVING retains groups only when its condition is TRUE.
"""
    )


def section_09_case_inside_aggregate(connection):
    print_title("9. Conditional aggregation with CASE")

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS total_orders,
            SUM(
                CASE
                    WHEN status = 'Completed' THEN 1
                    ELSE 0
                END
            ) AS completed_orders,
            SUM(
                CASE
                    WHEN status = 'Cancelled' THEN 1
                    ELSE 0
                END
            ) AS cancelled_orders
        FROM orders
        GROUP BY customer_id
        ORDER BY customer_id;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            SUM(
                CASE
                    WHEN status = 'Completed' THEN 1
                    ELSE 0
                END
            ) AS completed_orders
        FROM orders
        GROUP BY customer_id
        HAVING SUM(
            CASE
                WHEN status = 'Completed' THEN 1
                ELSE 0
            END
        ) >= 2
        ORDER BY completed_orders DESC;
        """,
    )

    print(
        """
Conditional aggregation creates several group-level metrics from the
same underlying rows.

A common pattern is:

    SUM(CASE WHEN condition THEN 1 ELSE 0 END)

This can be combined with HAVING to filter groups according to a
conditional count.

Some database systems also support:

    COUNT(*) FILTER (WHERE condition)

but syntax varies across database engines. CASE-based conditional
aggregation is broadly portable.
"""
    )


def section_10_having_aliases(connection):
    print_title("10. Aggregate aliases and portability")

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY customer_id
        HAVING order_count >= 2
        ORDER BY order_count DESC;
        """,
    )

    print(
        """
SQLite permits the SELECT alias order_count in HAVING.

Other database systems may have different alias-resolution rules.
For maximum portability, repeating the aggregate expression is often safer:

    HAVING COUNT(*) >= 2

Aliases are especially reliable in ORDER BY, but SQL dialect behavior
should be checked before depending on aliases in HAVING.
"""
    )


def section_11_grouping_multiple_columns(connection):
    print_title("11. GROUP BY multiple columns with HAVING")

    execute_query(
        connection,
        """
        SELECT
            c.city,
            c.customer_segment,
            COUNT(DISTINCT c.customer_id) AS customers,
            COUNT(DISTINCT o.order_id) AS orders
        FROM customers AS c
        JOIN orders AS o
            ON o.customer_id = c.customer_id
        WHERE o.status = 'Completed'
        GROUP BY
            c.city,
            c.customer_segment
        HAVING COUNT(DISTINCT o.order_id) >= 2
        ORDER BY c.city, c.customer_segment;
        """,
    )

    print(
        """
When multiple columns appear in GROUP BY, each distinct combination
forms a group.

For:

    GROUP BY city, customer_segment

a group represents one city-segment combination, not merely one city
and not merely one segment.

HAVING then evaluates each combination independently.
"""
    )


def section_12_join_multiplication(connection):
    print_title("12. Join multiplication and incorrect aggregation")

    execute_query(
        connection,
        """
        SELECT
            c.customer_id,
            c.customer_name,
            COUNT(*) AS joined_rows
        FROM customers AS c
        JOIN orders AS o
            ON o.customer_id = c.customer_id
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'Completed'
        GROUP BY c.customer_id, c.customer_name
        HAVING COUNT(*) >= 3
        ORDER BY joined_rows DESC;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            c.customer_id,
            c.customer_name,
            COUNT(DISTINCT o.order_id) AS completed_orders
        FROM customers AS c
        JOIN orders AS o
            ON o.customer_id = c.customer_id
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'Completed'
        GROUP BY c.customer_id, c.customer_name
        HAVING COUNT(DISTINCT o.order_id) >= 2
        ORDER BY completed_orders DESC;
        """,
    )

    print(
        """
Joining orders to order_items changes the row grain.

One order can have multiple order-item rows.

Therefore:

    COUNT(*)

after the join counts order-item rows, not orders.

Use:

    COUNT(DISTINCT o.order_id)

when the business question is about unique orders.

This is one of the most important practical aggregation errors.
Always identify the grain of the result before selecting COUNT, SUM, or
other aggregate logic.
"""
    )


def section_13_subqueries(connection):
    print_title("13. HAVING compared with a subquery")

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY customer_id
        HAVING COUNT(*) > (
            SELECT AVG(order_count)
            FROM (
                SELECT
                    customer_id,
                    COUNT(*) AS order_count
                FROM orders
                GROUP BY customer_id
            ) AS customer_order_counts
        )
        ORDER BY order_count DESC;
        """,
    )

    print(
        """
HAVING can compare one group's aggregate against a value calculated by
another query.

This example identifies customers whose order count is above the average
customer-level order count.

The inner query first calculates one count per customer. The outer
subquery calculates the average of those customer-level counts.
"""
    )


def section_14_cte_and_having(connection):
    print_title("14. Common table expressions and HAVING")

    revenue_expression = """
        oi.quantity * oi.unit_price *
        (1 - oi.discount_percent / 100.0)
    """

    execute_query(
        connection,
        f"""
        WITH customer_metrics AS (
            SELECT
                o.customer_id,
                COUNT(DISTINCT o.order_id) AS completed_orders,
                SUM(oi.quantity) AS units,
                SUM({revenue_expression}) AS revenue
            FROM orders AS o
            JOIN order_items AS oi
                ON oi.order_id = o.order_id
            WHERE o.status = 'Completed'
            GROUP BY o.customer_id
        )
        SELECT
            customer_id,
            completed_orders,
            units,
            ROUND(revenue, 2) AS revenue
        FROM customer_metrics
        WHERE completed_orders >= 2
          AND revenue >= 100000
        ORDER BY revenue DESC;
        """,
    )

    print(
        """
A CTE can separate aggregation from later filtering.

Conceptually:

    raw rows
        -> grouped metrics
        -> filtered metrics

The CTE approach is useful when the aggregate result will be reused,
needs several filters, or becomes easier to understand as a named
intermediate relation.

HAVING is often preferable when the condition belongs directly to the
GROUP BY operation.
"""
    )


def section_15_derived_table(connection):
    print_title("15. Filtering an aggregate using a derived table")

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            order_count
        FROM (
            SELECT
                customer_id,
                COUNT(*) AS order_count
            FROM orders
            GROUP BY customer_id
        ) AS customer_counts
        WHERE order_count >= 2
        ORDER BY order_count DESC;
        """,
    )

    print(
        """
A derived table turns the grouped result into a relation that an outer
query can filter with WHERE.

Compare:

    GROUP BY ... HAVING COUNT(*) >= 2

with:

    SELECT ...
    FROM (
        SELECT ..., COUNT(*) AS order_count
        FROM ...
        GROUP BY ...
    )
    WHERE order_count >= 2

Both express grouped filtering, but the second form is useful when the
calculated aggregate becomes an explicit intermediate dataset.
"""
    )


def section_16_window_functions(connection):
    print_title("16. HAVING versus window functions")

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY customer_id
        HAVING COUNT(*) >= 2
        ORDER BY order_count DESC;
        """,
    )

    execute_query(
        connection,
        """
        WITH customer_counts AS (
            SELECT
                customer_id,
                COUNT(*) AS order_count
            FROM orders
            GROUP BY customer_id
        )
        SELECT
            customer_id,
            order_count,
            ROUND(
                100.0 * order_count /
                SUM(order_count) OVER (),
                2
            ) AS percentage_of_all_orders
        FROM customer_counts
        ORDER BY order_count DESC;
        """,
    )

    print(
        """
GROUP BY collapses rows into groups.

Window functions calculate across related rows while preserving the
individual result rows.

HAVING answers questions such as:

    Which customer groups have at least two orders?

A window function answers questions such as:

    What percentage of the total orders belongs to each customer?

A common advanced pattern is:
    1. GROUP BY to create group-level metrics.
    2. HAVING to remove unwanted groups.
    3. Window functions to compare surviving groups.
"""
    )


def section_17_top_groups(connection):
    print_title("17. HAVING with ORDER BY and LIMIT")

    revenue_expression = """
        oi.quantity * oi.unit_price *
        (1 - oi.discount_percent / 100.0)
    """

    execute_query(
        connection,
        f"""
        SELECT
            o.customer_id,
            ROUND(SUM({revenue_expression}), 2) AS revenue
        FROM orders AS o
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'Completed'
        GROUP BY o.customer_id
        HAVING SUM({revenue_expression}) >= 50000
        ORDER BY revenue DESC
        LIMIT 3;
        """,
    )

    print(
        """
HAVING and LIMIT solve different problems.

HAVING establishes eligibility:

    revenue >= 50000

ORDER BY establishes ranking:

    highest revenue first

LIMIT chooses how many ranked rows to return:

    LIMIT 3

The sequence matters. Filtering eligible groups and selecting the top
groups are separate logical operations.
"""
    )


def section_18_date_grouping(connection):
    print_title("18. Time-based grouping and HAVING")

    revenue_expression = """
        oi.quantity * oi.unit_price *
        (1 - oi.discount_percent / 100.0)
    """

    execute_query(
        connection,
        f"""
        SELECT
            substr(o.order_date, 1, 7) AS month,
            COUNT(DISTINCT o.order_id) AS completed_orders,
            ROUND(SUM({revenue_expression}), 2) AS revenue
        FROM orders AS o
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'Completed'
        GROUP BY substr(o.order_date, 1, 7)
        HAVING SUM({revenue_expression}) >= 100000
        ORDER BY month;
        """,
    )

    print(
        """
Time-based reporting frequently uses:

    GROUP BY month

followed by:

    HAVING revenue threshold

The exact date functions differ across SQL databases. PostgreSQL,
MySQL, SQL Server, Oracle, and SQLite have different date-expression
syntax, so production SQL should use the functions appropriate for the
target engine.
"""
    )


def section_19_product_performance(connection):
    print_title("19. Product-level aggregated filtering")

    revenue_expression = """
        oi.quantity * oi.unit_price *
        (1 - oi.discount_percent / 100.0)
    """

    execute_query(
        connection,
        f"""
        SELECT
            p.product_name,
            p.category,
            SUM(oi.quantity) AS units_sold,
            COUNT(DISTINCT oi.order_id) AS orders_containing_product,
            ROUND(SUM({revenue_expression}), 2) AS revenue
        FROM products AS p
        JOIN order_items AS oi
            ON oi.product_id = p.product_id
        JOIN orders AS o
            ON o.order_id = oi.order_id
        WHERE o.status = 'Completed'
        GROUP BY p.product_id, p.product_name, p.category
        HAVING SUM(oi.quantity) >= 5
           AND COUNT(DISTINCT oi.order_id) >= 2
        ORDER BY revenue DESC;
        """,
    )

    print(
        """
This is a typical business-analysis use case:

    Group by product.
    Count distinct orders containing the product.
    Sum units.
    Calculate revenue.
    Keep products satisfying multiple performance thresholds.

The query demonstrates that HAVING can use several aggregate measures
at the same time.
"""
    )


def section_20_segment_analysis(connection):
    print_title("20. Segment-level aggregation")

    revenue_expression = """
        oi.quantity * oi.unit_price *
        (1 - oi.discount_percent / 100.0)
    """

    execute_query(
        connection,
        f"""
        SELECT
            c.customer_segment,
            COUNT(DISTINCT c.customer_id) AS customers,
            COUNT(DISTINCT o.order_id) AS orders,
            ROUND(SUM({revenue_expression}), 2) AS revenue,
            ROUND(AVG({revenue_expression}), 2) AS average_item_revenue
        FROM customers AS c
        JOIN orders AS o
            ON o.customer_id = c.customer_id
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'Completed'
        GROUP BY c.customer_segment
        HAVING COUNT(DISTINCT o.order_id) >= 3
        ORDER BY revenue DESC;
        """,
    )


def section_21_anti_patterns(connection):
    print_title("21. Common mistakes and why they fail")

    print(
        """
Mistake 1: Using WHERE for an aggregate condition.

Incorrect:

    SELECT customer_id, COUNT(*)
    FROM orders
    WHERE COUNT(*) >= 2
    GROUP BY customer_id;

COUNT(*) is an aggregate and is not available to WHERE.

Correct:

    SELECT customer_id, COUNT(*)
    FROM orders
    GROUP BY customer_id
    HAVING COUNT(*) >= 2;


Mistake 2: Filtering after aggregation when row filtering was intended.

Suppose only completed orders should contribute to the count.

Preferred:

    WHERE status = 'Completed'
    GROUP BY customer_id
    HAVING COUNT(*) >= 2

Using HAVING for status can produce different semantics and can make the
query less clear.


Mistake 3: Counting joined rows instead of business entities.

If one order has five items:

    COUNT(*) = 5
    COUNT(DISTINCT order_id) = 1

Choose the aggregate according to the question.


Mistake 4: Forgetting that NULL affects aggregate results.

COUNT(column), SUM(column), and AVG(column) do not treat NULL exactly
like ordinary numeric values.


Mistake 5: Grouping at the wrong grain.

A query grouped by customer may answer a different question from one
grouped by customer and month.


Mistake 6: Mixing AND and OR without parentheses.

Prefer:

    HAVING
        (COUNT(*) >= 2 AND SUM(amount) >= 100000)
        OR MAX(amount) >= 75000

rather than relying on implicit operator precedence.


Mistake 7: Assuming aliases work identically across all SQL engines.

SQL dialects differ. Test production queries against the actual target
database.
"""
    )


def section_22_three_valued_logic(connection):
    print_title("22. Three-valued logic and HAVING")

    connection.execute(
        """
        CREATE TABLE logic_demo (
            group_name TEXT,
            value REAL
        );
        """
    )

    connection.executemany(
        """
        INSERT INTO logic_demo (group_name, value)
        VALUES (?, ?);
        """,
        [
            ("positive", 20),
            ("positive", 30),
            ("zero", 0),
            ("unknown", None),
            ("unknown", None),
        ],
    )
    connection.commit()

    execute_query(
        connection,
        """
        SELECT
            group_name,
            SUM(value) AS total
        FROM logic_demo
        GROUP BY group_name
        HAVING SUM(value) > 10;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            group_name,
            SUM(value) AS total
        FROM logic_demo
        GROUP BY group_name
        HAVING COALESCE(SUM(value), 0) > 10;
        """,
    )

    print(
        """
COALESCE can replace NULL with a defined fallback.

For example:

    COALESCE(SUM(value), 0)

turns a NULL aggregate result into zero.

This should be done deliberately. NULL can mean "unknown" or "no value",
while zero means an actual numeric amount of zero. Treating them as
equivalent is a business decision, not merely a formatting operation.
"""
    )


def section_23_having_with_distinct(connection):
    print_title("23. DISTINCT and HAVING")

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(DISTINCT status) AS status_count
        FROM orders
        GROUP BY customer_id
        HAVING COUNT(DISTINCT status) >= 2
        ORDER BY customer_id;
        """,
    )

    print(
        """
DISTINCT changes the input to the aggregate.

COUNT(DISTINCT status) asks:

    How many different statuses does this customer have?

COUNT(*) asks:

    How many order rows does this customer have?

The distinction becomes important when the business metric is about
unique entities or unique values rather than physical rows.
"""
    )


def section_24_percentages(connection):
    print_title("24. Aggregated filtering with ratios and percentages")

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS total_orders,
            SUM(
                CASE
                    WHEN status = 'Completed' THEN 1
                    ELSE 0
                END
            ) AS completed_orders,
            ROUND(
                100.0 *
                SUM(
                    CASE
                        WHEN status = 'Completed' THEN 1
                        ELSE 0
                    END
                ) / COUNT(*),
                2
            ) AS completion_rate
        FROM orders
        GROUP BY customer_id
        HAVING
            1.0 *
            SUM(
                CASE
                    WHEN status = 'Completed' THEN 1
                    ELSE 0
                END
            ) / COUNT(*) >= 0.75
        ORDER BY completion_rate DESC;
        """,
    )

    print(
        """
HAVING can filter derived ratios, not just simple SUM or COUNT values.

A percentage is often:

    numerator / denominator

Multiplying by 1.0 in SQLite prevents unintended integer division.

When implementing ratios, consider:
    - division by zero
    - NULL values
    - integer versus decimal arithmetic
    - rounding
    - whether the denominator represents the correct population
"""
    )


def section_25_reusable_query_patterns(connection):
    print_title("25. Reusable HAVING patterns")

    patterns = {
        "Minimum group size": """
            SELECT group_column, COUNT(*) AS row_count
            FROM table_name
            GROUP BY group_column
            HAVING COUNT(*) >= 10;
        """,
        "Minimum total": """
            SELECT group_column, SUM(amount) AS total_amount
            FROM table_name
            GROUP BY group_column
            HAVING SUM(amount) >= 100000;
        """,
        "Range of totals": """
            SELECT group_column, SUM(amount) AS total_amount
            FROM table_name
            GROUP BY group_column
            HAVING SUM(amount) BETWEEN 50000 AND 100000;
        """,
        "Multiple aggregate rules": """
            SELECT group_column
            FROM table_name
            GROUP BY group_column
            HAVING COUNT(*) >= 5
               AND AVG(amount) > 1000;
        """,
        "Unique-value threshold": """
            SELECT group_column
            FROM table_name
            GROUP BY group_column
            HAVING COUNT(DISTINCT category) >= 3;
        """,
        "Conditional count": """
            SELECT group_column
            FROM table_name
            GROUP BY group_column
            HAVING SUM(
                CASE WHEN status = 'Completed' THEN 1 ELSE 0 END
            ) >= 5;
        """,
    }

    for name, query in patterns.items():
        print(f"\n{name}:")
        print(query.strip())

    print(
        """
These patterns cover a large portion of practical grouped-filtering work.
The exact aggregate and grouping columns should always be selected based
on the business definition of a group.
"""
    )


def section_26_explain_query_plan(connection):
    print_title("26. Performance: EXPLAIN QUERY PLAN")

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orders_status_customer
        ON orders(status, customer_id);
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_order_items_order
        ON order_items(order_id);
        """
    )

    plan = connection.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT
            customer_id,
            COUNT(*) AS completed_orders
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id
        HAVING COUNT(*) >= 2;
        """
    ).fetchall()

    print_rows(plan, ["id", "parent", "notused", "detail"])

    print(
        """
HAVING itself is not simply made fast by adding an index on the aggregate
result because the database generally has to form groups before applying
the aggregate predicate.

Performance depends on the entire query:

    FROM and JOIN operations
    -> WHERE filtering
    -> grouping
    -> aggregation
    -> HAVING
    -> ordering

Indexes can often help reduce the rows entering the grouping stage.
For example, an index beginning with status can help a query that strongly
filters by status.

Indexes are not automatically beneficial. They consume storage and can
increase INSERT, UPDATE, and DELETE cost. Query plans should be examined
against realistic data.
"""
    )


def section_27_pushdown_logic(connection):
    print_title("27. Predicate placement and reducing work")

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS completed_orders
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id
        HAVING COUNT(*) >= 2;
        """,
    )

    print(
        """
A predicate that describes source rows generally belongs in WHERE.

For example:

    WHERE status = 'Completed'

allows the database to eliminate non-completed rows before grouping.

The aggregate condition:

    HAVING COUNT(*) >= 2

cannot be evaluated until the relevant group exists.

A strong optimization and correctness habit is to ask:

    Can this condition be evaluated before grouping?

If yes, it is often a WHERE condition.

If it depends on an aggregate over the group, it belongs in HAVING or an
outer query.
"""
    )


def section_28_transactional_data_quality(connection):
    print_title("28. Data quality and aggregation correctness")

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY customer_id
        HAVING COUNT(*) > 0;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(DISTINCT order_id) AS distinct_order_ids
        FROM orders
        GROUP BY customer_id
        HAVING COUNT(DISTINCT order_id) <> COUNT(*);
        """,
    )

    print(
        """
A HAVING query can also support data-quality checks.

The second query looks for groups where COUNT(DISTINCT order_id) differs
from COUNT(*). With a properly constrained orders table, that should not
occur because order_id is the primary key.

Constraints such as PRIMARY KEY, FOREIGN KEY, CHECK, and NOT NULL protect
the assumptions on which aggregate reporting depends.
"""
    )


def section_29_security(connection):
    print_title("29. Security considerations")

    customer_id = 1

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        WHERE customer_id = ?
        GROUP BY customer_id
        HAVING COUNT(*) >= ?;
        """,
        (customer_id, 2),
    )

    print(
        """
Parameterized queries are preferable when values come from users or
external systems.

Do not construct SQL by concatenating untrusted values:

    "... HAVING COUNT(*) >= " + user_value

Instead, use parameters supported by the database driver.

The HAVING clause does not make a query safe by itself. SQL injection
prevention is primarily a matter of correct parameter binding and safe
query construction.

Authorization must also be handled separately. A query that correctly
aggregates data can still expose unauthorized customers if application
access controls are missing.
"""
    )


def section_30_testing_aggregates(connection):
    print_title("30. Testing grouped-filtering logic")

    tests = [
        (
            "Customers with at least two orders",
            """
            SELECT COUNT(*)
            FROM (
                SELECT customer_id
                FROM orders
                GROUP BY customer_id
                HAVING COUNT(*) >= 2
            );
            """,
            6,
        ),
        (
            "Exactly three orders",
            """
            SELECT COUNT(*)
            FROM (
                SELECT customer_id
                FROM orders
                GROUP BY customer_id
                HAVING COUNT(*) = 3
            );
            """,
            3,
        ),
    ]

    for test_name, sql, expected in tests:
        actual = connection.execute(sql).fetchone()[0]
        result = "PASS" if actual == expected else "FAIL"
        print(
            f"{result}: {test_name} | expected={expected}, actual={actual}"
        )

    print(
        """
Grouped SQL should be tested with data that exercises boundaries.

Useful cases include:
    - zero matching rows
    - exactly the threshold
    - one row below the threshold
    - one row above the threshold
    - NULL values
    - duplicate business entities
    - multiple child rows per parent
    - groups containing only filtered-out rows
    - empty groups produced by outer joins
"""
    )


def section_31_left_join_and_zero_groups(connection):
    print_title("31. LEFT JOIN, zero counts, and HAVING")

    execute_query(
        connection,
        """
        SELECT
            c.customer_id,
            c.customer_name,
            COUNT(o.order_id) AS order_count
        FROM customers AS c
        LEFT JOIN orders AS o
            ON o.customer_id = c.customer_id
            AND o.status = 'Completed'
        GROUP BY c.customer_id, c.customer_name
        HAVING COUNT(o.order_id) = 0
        ORDER BY c.customer_id;
        """,
    )

    print(
        """
The LEFT JOIN preserves customers even when they have no matching
completed orders.

Placing:

    o.status = 'Completed'

inside the ON clause preserves zero-order customers.

If the same condition were placed in WHERE, unmatched rows would be
removed and the LEFT JOIN would effectively behave like an INNER JOIN
for that condition.

COUNT(o.order_id) is useful here because order_id is NULL for unmatched
rows, so the count becomes zero.
"""
    )


def section_32_having_and_outer_join_edge_case(connection):
    print_title("32. HAVING and outer-join edge-case comparison")

    execute_query(
        connection,
        """
        SELECT
            c.customer_id,
            c.customer_name,
            COUNT(o.order_id) AS completed_orders
        FROM customers AS c
        LEFT JOIN orders AS o
            ON o.customer_id = c.customer_id
            AND o.status = 'Completed'
        GROUP BY c.customer_id, c.customer_name
        HAVING COUNT(o.order_id) >= 1
        ORDER BY c.customer_id;
        """,
    )

    execute_query(
        connection,
        """
        SELECT
            c.customer_id,
            c.customer_name,
            COUNT(o.order_id) AS completed_orders
        FROM customers AS c
        LEFT JOIN orders AS o
            ON o.customer_id = c.customer_id
            AND o.status = 'Completed'
        GROUP BY c.customer_id, c.customer_name
        HAVING COUNT(o.order_id) = 0
        ORDER BY c.customer_id;
        """,
    )

    print(
        """
HAVING can retain or eliminate the zero-count groups produced by an
outer join.

This pattern is widely used for:
    - customers with no orders
    - products with no sales
    - employees with no assignments
    - accounts with no transactions
"""
    )


def section_33_grouping_business_logic(connection):
    print_title("33. Translating business questions into HAVING")

    business_questions = [
        (
            "Customers with at least 3 orders",
            """
            SELECT customer_id
            FROM orders
            GROUP BY customer_id
            HAVING COUNT(*) >= 3;
            """,
        ),
        (
            "Cities with at least 2 customers",
            """
            SELECT city
            FROM customers
            GROUP BY city
            HAVING COUNT(*) >= 2;
            """,
        ),
        (
            "Products sold in at least 2 orders",
            """
            SELECT product_id
            FROM order_items
            GROUP BY product_id
            HAVING COUNT(DISTINCT order_id) >= 2;
            """,
        ),
    ]

    for question, sql in business_questions:
        print(f"\nBusiness question: {question}")
        execute_query(connection, sql)

    print(
        """
The translation process is:

    1. Identify the entity being measured.
    2. Identify the grouping key.
    3. Identify the metric.
    4. Determine whether the metric is aggregate.
    5. Put row-level restrictions in WHERE.
    6. Put group-level restrictions in HAVING.
    7. Validate the grain of the result.
"""
    )


def section_34_advanced_customer_segmentation(connection):
    print_title("34. Advanced customer qualification")

    revenue_expression = """
        oi.quantity * oi.unit_price *
        (1 - oi.discount_percent / 100.0)
    """

    execute_query(
        connection,
        f"""
        SELECT
            c.customer_id,
            c.customer_name,
            c.customer_segment,
            COUNT(DISTINCT o.order_id) AS completed_orders,
            SUM(oi.quantity) AS units,
            ROUND(SUM({revenue_expression}), 2) AS revenue,
            ROUND(AVG({revenue_expression}), 2) AS average_line_value
        FROM customers AS c
        JOIN orders AS o
            ON o.customer_id = c.customer_id
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'Completed'
        GROUP BY
            c.customer_id,
            c.customer_name,
            c.customer_segment
        HAVING COUNT(DISTINCT o.order_id) >= 2
           AND SUM(oi.quantity) >= 5
           AND SUM({revenue_expression}) >= 100000
           AND AVG({revenue_expression}) >= 5000
        ORDER BY revenue DESC;
        """,
    )

    print(
        """
This query illustrates multi-dimensional group qualification.

A customer must satisfy:
    - a minimum number of completed orders
    - a minimum number of units
    - a minimum total revenue
    - a minimum average line value

The result is a qualified population rather than a raw transaction list.
"""
    )


def section_35_materialized_reporting(connection):
    print_title("35. Production reporting considerations")

    print(
        """
For small or moderately sized datasets, direct GROUP BY and HAVING
queries are often sufficient.

For large analytical workloads, repeated aggregation can become
expensive. Production systems may use:

    - indexed source tables
    - summary tables
    - materialized views
    - partitioning
    - incremental aggregation
    - analytical databases
    - precomputed reporting datasets

The design decision depends on data volume, update frequency, query
latency requirements, consistency requirements, and database engine.

A summary table can reduce repeated work, but introduces the problem of
keeping derived data synchronized with source data.

HAVING remains the logical concept even when aggregation is performed
through a larger reporting architecture.
"""
    )


def section_36_sql_dialect_differences(connection):
    print_title("36. SQL dialect differences")

    print(
        """
The logical concept of HAVING is broadly standardized:

    GROUP BY creates groups.
    Aggregate functions calculate group metrics.
    HAVING filters groups.

Implementation details can differ among database engines.

Potential differences include:
    - whether SELECT aliases are accepted in HAVING
    - date and time functions
    - aggregate-specific functions
    - FILTER syntax
    - NULL behavior of special aggregates
    - GROUP BY strictness
    - expression rules
    - optimizer behavior
    - execution-plan representation

For production work, write queries against the actual database engine
rather than assuming SQLite, PostgreSQL, MySQL, SQL Server, Oracle, and
other systems behave identically in every detail.
"""
    )


def section_37_aggregate_logic_checklist(connection):
    print_title("37. Aggregate-query debugging checklist")

    print(
        """
When a HAVING query returns an unexpected result, inspect it in layers.

Layer 1: Source rows
    SELECT ...
    FROM ...
    WHERE ...

Layer 2: Grouping
    SELECT group_key, COUNT(*)
    FROM ...
    WHERE ...
    GROUP BY group_key

Layer 3: Aggregate values
    Add SUM, AVG, MIN, MAX, COUNT(DISTINCT ...).

Layer 4: HAVING
    Add the group condition.

Layer 5: Ordering
    Add ORDER BY.

Layer 6: Limiting
    Add LIMIT only after the ranking logic is correct.

Common debugging questions:

    What is one row in the current query?
    What is the intended group?
    Is a JOIN multiplying rows?
    Should COUNT(*) be COUNT(DISTINCT id)?
    Are NULLs present?
    Is the threshold inclusive or exclusive?
    Should the condition happen before grouping?
    Is integer division occurring?
    Is the date grouping correct?
    Is the SQL dialect behaving as expected?
"""
    )

    execute_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS rows_in_group,
            MIN(order_date) AS first_order,
            MAX(order_date) AS last_order
        FROM orders
        GROUP BY customer_id
        ORDER BY customer_id;
        """,
    )


def section_38_boundary_examples(connection):
    print_title("38. Boundary conditions")

    thresholds = [0, 1, 2, 3, 4]

    for threshold in thresholds:
        rows = connection.execute(
            """
            SELECT customer_id
            FROM orders
            GROUP BY customer_id
            HAVING COUNT(*) >= ?
            ORDER BY customer_id;
            """,
            (threshold,),
        ).fetchall()

        print(
            f"Threshold >= {threshold}: "
            f"{len(rows)} qualifying customer groups"
        )

    print(
        """
Boundary tests help reveal whether the requirement means:

    > 5
    >= 5
    < 5
    <= 5
    = 5
    BETWEEN 5 AND 10

For analytical queries, a one-character difference can materially change
the business population.
"""
    )


def section_39_having_vs_where_table():
    print_title("39. WHERE versus HAVING comparison")

    comparison = [
        ("Primary purpose", "Filter source rows", "Filter groups"),
        ("Typical stage", "Before GROUP BY", "After GROUP BY"),
        ("Aggregate expressions", "Generally not valid", "Designed for them"),
        ("Example", "WHERE status = 'Completed'", "HAVING COUNT(*) >= 2"),
        ("Effect", "Changes rows entering groups", "Changes groups returned"),
    ]

    print_rows(
        [
            {
                "Aspect": aspect,
                "WHERE": where_value,
                "HAVING": having_value,
            }
            for aspect, where_value, having_value in comparison
        ],
        ["Aspect", "WHERE", "HAVING"],
    )


def section_40_final_integrated_example(connection):
    print_title("40. Integrated advanced example")

    revenue_expression = """
        oi.quantity * oi.unit_price *
        (1 - oi.discount_percent / 100.0)
    """

    query = f"""
    WITH customer_metrics AS (
        SELECT
            c.customer_id,
            c.customer_name,
            c.city,
            c.customer_segment,
            COUNT(DISTINCT o.order_id) AS completed_orders,
            COUNT(DISTINCT substr(o.order_date, 1, 7)) AS active_months,
            SUM(oi.quantity) AS units,
            SUM({revenue_expression}) AS revenue,
            AVG({revenue_expression}) AS average_line_value,
            SUM(
                CASE
                    WHEN oi.discount_percent >= 10 THEN 1
                    ELSE 0
                END
            ) AS discounted_lines
        FROM customers AS c
        JOIN orders AS o
            ON o.customer_id = c.customer_id
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'Completed'
        GROUP BY
            c.customer_id,
            c.customer_name,
            c.city,
            c.customer_segment
        HAVING COUNT(DISTINCT o.order_id) >= 2
           AND COUNT(DISTINCT substr(o.order_date, 1, 7)) >= 2
           AND SUM(oi.quantity) >= 5
           AND SUM({revenue_expression}) >= 100000
    )
    SELECT
        customer_id,
        customer_name,
        city,
        customer_segment,
        completed_orders,
        active_months,
        units,
        ROUND(revenue, 2) AS revenue,
        ROUND(average_line_value, 2) AS average_line_value,
        discounted_lines,
        ROUND(
            100.0 * revenue /
            SUM(revenue) OVER (),
            2
        ) AS percentage_of_qualified_revenue
    FROM customer_metrics
    ORDER BY revenue DESC;
    """

    execute_query(connection, query)

    print(
        """
This integrated query combines:

    JOIN
    WHERE
    GROUP BY
    COUNT(DISTINCT ...)
    SUM(...)
    AVG(...)
    CASE
    HAVING
    CTE
    window aggregation
    ORDER BY

The CTE first produces qualified customer groups using HAVING.

The outer query then calculates each qualified customer's percentage of
the total qualified revenue using a window function.

This illustrates an important architectural pattern:

    transaction-level data
        -> row filtering
        -> grouping
        -> aggregate qualification
        -> group-level analytical calculations
        -> final presentation
"""
    )


def run_all_sections():
    connection = create_database()

    try:
        section_01_foundations(connection)
        section_02_where_vs_having(connection)
        section_03_basic_having(connection)
        section_04_grouped_revenue(connection)
        section_05_multiple_having_conditions(connection)
        section_06_having_without_group_by(connection)
        section_07_count_variants(connection)
        section_08_nulls(connection)
        section_09_case_inside_aggregate(connection)
        section_10_having_aliases(connection)
        section_11_grouping_multiple_columns(connection)
        section_12_join_multiplication(connection)
        section_13_subqueries(connection)
        section_14_cte_and_having(connection)
        section_15_derived_table(connection)
        section_16_window_functions(connection)
        section_17_top_groups(connection)
        section_18_date_grouping(connection)
        section_19_product_performance(connection)
        section_20_segment_analysis(connection)
        section_21_anti_patterns(connection)
        section_22_three_valued_logic(connection)
        section_23_having_with_distinct(connection)
        section_24_percentages(connection)
        section_25_reusable_query_patterns(connection)
        section_26_explain_query_plan(connection)
        section_27_pushdown_logic(connection)
        section_28_transactional_data_quality(connection)
        section_29_security(connection)
        section_30_testing_aggregates(connection)
        section_31_left_join_and_zero_groups(connection)
        section_32_having_and_outer_join_edge_case(connection)
        section_33_grouping_business_logic(connection)
        section_34_advanced_customer_segmentation(connection)
        section_35_materialized_reporting(connection)
        section_36_sql_dialect_differences(connection)
        section_37_aggregate_logic_checklist(connection)
        section_38_boundary_examples(connection)
        section_39_having_vs_where_table()
        section_40_final_integrated_example(connection)

        print_title("Study file completed")
        print(
            """
The database connection is an in-memory SQLite database, so all example
tables and data disappear when the script exits.

Core pattern to remember:

    SELECT group_column, AGGREGATE(...)
    FROM source
    WHERE row_condition
    GROUP BY group_column
    HAVING aggregate_condition
    ORDER BY aggregate_result;

The critical distinction is:

    WHERE -> row-level filtering
    HAVING -> group-level filtering
"""
        )

    finally:
        connection.close()


if __name__ == "__main__":
    run_all_sections()
