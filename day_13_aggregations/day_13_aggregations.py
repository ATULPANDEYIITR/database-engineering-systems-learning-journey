"""
SQL Aggregations: COUNT, SUM, AVG, MIN, MAX, and GROUP BY
===========================================================

This standalone Python script teaches SQL aggregation concepts from beginner
through advanced level by using Python's built-in sqlite3 database engine.

Topics covered:
    - Relational data and SQL basics
    - Aggregate functions
    - COUNT
    - SUM
    - AVG
    - MIN
    - MAX
    - NULL behavior
    - GROUP BY
    - WHERE versus HAVING
    - DISTINCT
    - Multiple aggregate functions
    - Grouping by multiple columns
    - Conditional aggregation
    - CASE expressions
    - Aggregating expressions
    - Integer and decimal behavior
    - Aggregate functions with JOIN
    - LEFT JOIN and zero-count groups
    - Subqueries and derived results
    - Common Table Expressions
    - Window functions versus GROUP BY
    - Filtering grouped data
    - Date-based aggregation
    - Percentage calculations
    - Weighted averages
    - Data-quality considerations
    - Performance and indexing
    - SQL injection safety
    - Validation and testing
    - Edge cases and common mistakes

The examples use only Python's standard library.
"""

import sqlite3
from contextlib import closing
from decimal import Decimal


# ---------------------------------------------------------------------------
# 1. DATABASE SETUP
# ---------------------------------------------------------------------------

def create_database():
    """
    Create an in-memory SQLite database and return the connection.

    An in-memory database is useful for learning because:
        - no external file is required,
        - every execution starts with clean data,
        - the examples are completely self-contained.
    """
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def create_tables(connection):
    """Create customers, products, and orders tables."""

    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            city TEXT NOT NULL,
            segment TEXT NOT NULL,
            signup_date TEXT NOT NULL
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit_price REAL NOT NULL,
            cost_price REAL NOT NULL
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            discount_percent REAL NOT NULL DEFAULT 0,
            sales_channel TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
        """
    )


def insert_sample_data(connection):
    """Insert realistic sample data for the aggregation examples."""

    customers = [
        (1, "Aarav Sharma", "Lucknow", "Retail", "2025-01-15"),
        (2, "Priya Singh", "Delhi", "Corporate", "2025-02-10"),
        (3, "Rahul Verma", "Mumbai", "Retail", "2025-02-18"),
        (4, "Neha Gupta", "Lucknow", "Corporate", "2025-03-05"),
        (5, "Vikram Rao", "Bengaluru", "Enterprise", "2025-03-20"),
        (6, "Ananya Mehta", "Delhi", "Retail", "2025-04-02"),
        (7, "Kabir Khan", "Pune", "Corporate", "2025-04-15"),
        (8, "Isha Kapoor", "Mumbai", "Enterprise", "2025-05-01"),
        (9, "Rohan Das", "Kolkata", "Retail", "2025-05-12"),
        (10, "Meera Nair", "Chennai", "Corporate", "2025-06-01"),
    ]

    products = [
        (1, "Laptop Pro", "Electronics", 75000.00, 60000.00),
        (2, "Monitor 27", "Electronics", 22000.00, 16000.00),
        (3, "Keyboard", "Accessories", 2500.00, 1500.00),
        (4, "Mouse", "Accessories", 1200.00, 700.00),
        (5, "Office Chair", "Furniture", 15000.00, 10000.00),
        (6, "Desk", "Furniture", 18000.00, 12000.00),
        (7, "Headphones", "Accessories", 5000.00, 3000.00),
    ]

    orders = [
        (1, 1, 1, "2025-01-20", 1, 75000, 0, "Online", "Completed"),
        (2, 1, 3, "2025-01-22", 2, 2500, 5, "Online", "Completed"),
        (3, 2, 1, "2025-02-15", 2, 75000, 10, "Sales", "Completed"),
        (4, 2, 2, "2025-02-17", 3, 22000, 5, "Sales", "Completed"),
        (5, 3, 5, "2025-02-20", 2, 15000, 0, "Online", "Completed"),
        (6, 3, 7, "2025-03-02", 1, 5000, 0, "Online", "Cancelled"),
        (7, 4, 6, "2025-03-10", 4, 18000, 15, "Sales", "Completed"),
        (8, 4, 4, "2025-03-12", 5, 1200, 0, "Online", "Completed"),
        (9, 5, 1, "2025-03-25", 5, 75000, 12, "Sales", "Completed"),
        (10, 5, 2, "2025-03-27", 5, 22000, 10, "Sales", "Completed"),
        (11, 6, 3, "2025-04-10", 10, 2500, 8, "Online", "Completed"),
        (12, 6, 4, "2025-04-11", 10, 1200, 5, "Online", "Completed"),
        (13, 7, 5, "2025-04-20", 3, 15000, 10, "Sales", "Completed"),
        (14, 7, 6, "2025-04-21", 2, 18000, 10, "Sales", "Completed"),
        (15, 8, 1, "2025-05-05", 3, 75000, 5, "Sales", "Completed"),
        (16, 8, 7, "2025-05-07", 4, 5000, 0, "Online", "Completed"),
        (17, 9, 4, "2025-05-15", 7, 1200, 0, "Online", "Completed"),
        (18, 9, 3, "2025-05-16", 3, 2500, 0, "Online", "Completed"),
        (19, 10, 2, "2025-06-10", 4, 22000, 7, "Sales", "Completed"),
        (20, 10, 5, "2025-06-12", 2, 15000, 5, "Sales", "Completed"),
        (21, 1, 4, "2025-06-15", 3, 1200, 0, "Online", "Completed"),
        (22, 2, 7, "2025-06-20", 2, 5000, 5, "Online", "Completed"),
        (23, 3, 2, "2025-06-22", 1, 22000, 0, "Online", "Completed"),
        (24, 5, 6, "2025-06-25", 3, 18000, 8, "Sales", "Completed"),
    ]

    connection.executemany(
        """
        INSERT INTO customers
        (customer_id, customer_name, city, segment, signup_date)
        VALUES (?, ?, ?, ?, ?)
        """,
        customers,
    )

    connection.executemany(
        """
        INSERT INTO products
        (product_id, product_name, category, unit_price, cost_price)
        VALUES (?, ?, ?, ?, ?)
        """,
        products,
    )

    connection.executemany(
        """
        INSERT INTO orders
        (
            order_id,
            customer_id,
            product_id,
            order_date,
            quantity,
            unit_price,
            discount_percent,
            sales_channel,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        orders,
    )

    connection.commit()


# ---------------------------------------------------------------------------
# 2. HELPER FUNCTIONS FOR DISPLAY
# ---------------------------------------------------------------------------

def execute_query(connection, sql, parameters=()):
    """Execute a SELECT query and return rows."""
    with closing(connection.cursor()) as cursor:
        cursor.execute(sql, parameters)
        return cursor.fetchall()


def print_title(title):
    """Print a readable section title."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_rows(rows):
    """Print SQLite Row objects as dictionaries."""
    if not rows:
        print("(no rows)")
        return

    for row in rows:
        print(dict(row))


def print_query(connection, title, sql, parameters=()):
    """Run and display a query."""
    print_title(title)
    print("SQL:")
    print(sql.strip())
    rows = execute_query(connection, sql, parameters)
    print("\nResult:")
    print_rows(rows)
    return rows


# ---------------------------------------------------------------------------
# 3. BASIC SQL AGGREGATION CONCEPT
# ---------------------------------------------------------------------------

def demonstrate_aggregation_basics(connection):
    """
    Aggregation reduces multiple input rows into summary values.

    Example:
        24 order rows can become one number representing total orders.

    A normal SELECT usually returns one result per matching row.

    An aggregate query can return one summary result for the entire
    matching dataset when GROUP BY is not used.
    """

    print_title("3. Aggregation fundamentals")

    print(
        """
Aggregation means calculating a summary from multiple rows.

The main aggregate functions demonstrated in this script are:

    COUNT() -> number of rows or non-NULL values
    SUM()   -> total numeric value
    AVG()   -> arithmetic mean
    MIN()   -> smallest value
    MAX()   -> largest value

Without GROUP BY, an aggregate query normally produces one summary row.
With GROUP BY, SQL produces one summary row for each group.
"""
    )

    print_query(
        connection,
        "Count all order rows",
        """
        SELECT COUNT(*) AS order_count
        FROM orders;
        """,
    )


# ---------------------------------------------------------------------------
# 4. COUNT
# ---------------------------------------------------------------------------

def demonstrate_count(connection):
    """Demonstrate the different important forms of COUNT."""

    print_title("4. COUNT")

    print(
        """
COUNT is used to count records or non-NULL values.

Important forms:

    COUNT(*)          counts every row.
    COUNT(column)     counts rows where the column is not NULL.
    COUNT(DISTINCT x) counts distinct non-NULL values.

COUNT(*) is generally the clearest choice when the question is:
"How many rows are present?"
"""
    )

    print_query(
        connection,
        "COUNT(*) counts all order rows",
        """
        SELECT COUNT(*) AS total_orders
        FROM orders;
        """,
    )

    print_query(
        connection,
        "COUNT(column) counts non-NULL values",
        """
        SELECT COUNT(status) AS orders_with_status
        FROM orders;
        """,
    )

    print_query(
        connection,
        "COUNT(DISTINCT) counts unique customers who placed orders",
        """
        SELECT COUNT(DISTINCT customer_id) AS unique_customers
        FROM orders;
        """,
    )

    print_query(
        connection,
        "Count orders by status",
        """
        SELECT
            status,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY status;
        """,
    )

    print_query(
        connection,
        "Count orders by sales channel",
        """
        SELECT
            sales_channel,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY sales_channel;
        """,
    )


# ---------------------------------------------------------------------------
# 5. SUM
# ---------------------------------------------------------------------------

def demonstrate_sum(connection):
    """Demonstrate SUM and calculated expressions."""

    print_title("5. SUM")

    print(
        """
SUM adds numeric values.

For this dataset, gross line value is:

    quantity * unit_price

Discounted line value is:

    quantity * unit_price * (1 - discount_percent / 100)

Aggregate functions can operate on expressions, not only stored columns.
"""
    )

    print_query(
        connection,
        "Total quantity sold",
        """
        SELECT SUM(quantity) AS total_units
        FROM orders
        WHERE status = 'Completed';
        """,
    )

    print_query(
        connection,
        "Gross sales before discounts",
        """
        SELECT
            SUM(quantity * unit_price) AS gross_sales
        FROM orders
        WHERE status = 'Completed';
        """,
    )

    print_query(
        connection,
        "Net sales after line-level discounts",
        """
        SELECT
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS net_sales
        FROM orders
        WHERE status = 'Completed';
        """,
    )

    print_query(
        connection,
        "Sales by channel",
        """
        SELECT
            sales_channel,
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS net_sales
        FROM orders
        WHERE status = 'Completed'
        GROUP BY sales_channel;
        """,
    )


# ---------------------------------------------------------------------------
# 6. AVG
# ---------------------------------------------------------------------------

def demonstrate_avg(connection):
    """Demonstrate AVG and explain what average actually represents."""

    print_title("6. AVG")

    print(
        """
AVG calculates the arithmetic mean:

    AVG(x) = SUM(x) / COUNT(x)

AVG(column) ignores NULL values.

An important analytical distinction is the difference between:

    average order value
and
    average item price

They answer different questions because they aggregate different units.
"""
    )

    print_query(
        connection,
        "Average quantity per order",
        """
        SELECT
            AVG(quantity) AS average_quantity
        FROM orders
        WHERE status = 'Completed';
        """,
    )

    print_query(
        connection,
        "Average unit price",
        """
        SELECT
            AVG(unit_price) AS average_unit_price
        FROM orders
        WHERE status = 'Completed';
        """,
    )

    print_query(
        connection,
        "Average order line value",
        """
        SELECT
            AVG(quantity * unit_price) AS average_gross_line_value
        FROM orders
        WHERE status = 'Completed';
        """,
    )

    print_query(
        connection,
        "Average discount",
        """
        SELECT
            AVG(discount_percent) AS average_discount_percent
        FROM orders
        WHERE status = 'Completed';
        """,
    )


# ---------------------------------------------------------------------------
# 7. MIN AND MAX
# ---------------------------------------------------------------------------

def demonstrate_min_max(connection):
    """Demonstrate minimum and maximum values."""

    print_title("7. MIN and MAX")

    print(
        """
MIN returns the smallest non-NULL value.
MAX returns the largest non-NULL value.

They can be applied to numeric, text, and date-like values.

For ISO-formatted dates such as YYYY-MM-DD, lexical ordering matches
chronological ordering, which makes MIN and MAX useful for date ranges.
"""
    )

    print_query(
        connection,
        "Minimum and maximum unit price",
        """
        SELECT
            MIN(unit_price) AS minimum_unit_price,
            MAX(unit_price) AS maximum_unit_price
        FROM orders
        WHERE status = 'Completed';
        """,
    )

    print_query(
        connection,
        "Earliest and latest completed order date",
        """
        SELECT
            MIN(order_date) AS first_order_date,
            MAX(order_date) AS latest_order_date
        FROM orders
        WHERE status = 'Completed';
        """,
    )

    print_query(
        connection,
        "Minimum and maximum discount",
        """
        SELECT
            MIN(discount_percent) AS minimum_discount,
            MAX(discount_percent) AS maximum_discount
        FROM orders
        WHERE status = 'Completed';
        """,
    )


# ---------------------------------------------------------------------------
# 8. MULTIPLE AGGREGATES IN ONE QUERY
# ---------------------------------------------------------------------------

def demonstrate_multiple_aggregates(connection):
    """Show how several metrics can be calculated together."""

    print_title("8. Multiple aggregate functions")

    print_query(
        connection,
        "Sales dashboard metrics",
        """
        SELECT
            COUNT(*) AS completed_order_lines,
            COUNT(DISTINCT customer_id) AS unique_customers,
            SUM(quantity) AS units_sold,
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS net_sales,
            AVG(quantity) AS average_quantity,
            MIN(quantity) AS minimum_quantity,
            MAX(quantity) AS maximum_quantity
        FROM orders
        WHERE status = 'Completed';
        """,
    )


# ---------------------------------------------------------------------------
# 9. GROUP BY
# ---------------------------------------------------------------------------

def demonstrate_group_by(connection):
    """Demonstrate grouping at increasing levels of complexity."""

    print_title("9. GROUP BY")

    print(
        """
GROUP BY partitions rows into groups.

For example:

    GROUP BY sales_channel

creates one group for Online and one group for Sales.

An aggregate is then calculated independently inside each group.

Conceptually:

    input rows
        |
        +-- Online group -> COUNT, SUM, AVG, ...
        |
        +-- Sales group  -> COUNT, SUM, AVG, ...

Every selected column that is not aggregated normally needs to participate
in the grouping logic.
"""
    )

    print_query(
        connection,
        "Count orders per customer",
        """
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY customer_id
        ORDER BY order_count DESC;
        """,
    )

    print_query(
        connection,
        "Sales by customer",
        """
        SELECT
            customer_id,
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS total_sales
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id
        ORDER BY total_sales DESC;
        """,
    )

    print_query(
        connection,
        "Sales by product",
        """
        SELECT
            product_id,
            SUM(quantity) AS units_sold,
            SUM(quantity * unit_price) AS gross_sales
        FROM orders
        WHERE status = 'Completed'
        GROUP BY product_id
        ORDER BY gross_sales DESC;
        """,
    )


# ---------------------------------------------------------------------------
# 10. GROUPING BY MULTIPLE COLUMNS
# ---------------------------------------------------------------------------

def demonstrate_multiple_group_columns(connection):
    """Demonstrate grouping by combinations of dimensions."""

    print_title("10. GROUP BY multiple columns")

    print(
        """
Multiple grouping columns create groups based on combinations.

For example:

    GROUP BY sales_channel, status

produces a separate group for every channel/status combination.
"""
    )

    print_query(
        connection,
        "Orders by channel and status",
        """
        SELECT
            sales_channel,
            status,
            COUNT(*) AS order_count,
            SUM(quantity) AS units
        FROM orders
        GROUP BY sales_channel, status
        ORDER BY sales_channel, status;
        """,
    )

    print_query(
        connection,
        "Sales by month and channel",
        """
        SELECT
            substr(order_date, 1, 7) AS order_month,
            sales_channel,
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS net_sales
        FROM orders
        WHERE status = 'Completed'
        GROUP BY order_month, sales_channel
        ORDER BY order_month, sales_channel;
        """,
    )


# ---------------------------------------------------------------------------
# 11. WHERE VERSUS HAVING
# ---------------------------------------------------------------------------

def demonstrate_where_having(connection):
    """Demonstrate the crucial distinction between WHERE and HAVING."""

    print_title("11. WHERE versus HAVING")

    print(
        """
WHERE filters individual rows before grouping.

HAVING filters groups after aggregation.

Typical logical processing is approximately:

    FROM
    WHERE
    GROUP BY
    HAVING
    SELECT
    ORDER BY

Example:

    WHERE status = 'Completed'

removes cancelled rows before totals are calculated.

Then:

    HAVING SUM(...) > 100000

keeps only customer groups whose calculated sales exceed the threshold.
"""
    )

    print_query(
        connection,
        "WHERE filters rows before aggregation",
        """
        SELECT
            customer_id,
            COUNT(*) AS completed_orders
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id;
        """,
    )

    print_query(
        connection,
        "HAVING filters groups after aggregation",
        """
        SELECT
            customer_id,
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS total_sales
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id
        HAVING total_sales > 100000
        ORDER BY total_sales DESC;
        """,
    )

    print(
        """
Common mistake:

    SELECT customer_id, COUNT(*)
    FROM orders
    WHERE COUNT(*) > 2
    GROUP BY customer_id;

This is invalid because COUNT(*) is an aggregate and cannot be used
as a normal row-level WHERE condition.

Correct:

    SELECT customer_id, COUNT(*) AS order_count
    FROM orders
    GROUP BY customer_id
    HAVING COUNT(*) > 2;
"""
    )


# ---------------------------------------------------------------------------
# 12. DISTINCT WITH AGGREGATION
# ---------------------------------------------------------------------------

def demonstrate_distinct(connection):
    """Demonstrate DISTINCT and COUNT(DISTINCT ...)."""

    print_title("12. DISTINCT and aggregation")

    print_query(
        connection,
        "Number of distinct cities",
        """
        SELECT COUNT(DISTINCT city) AS city_count
        FROM customers;
        """,
    )

    print_query(
        connection,
        "Number of distinct products ordered",
        """
        SELECT COUNT(DISTINCT product_id) AS products_ordered
        FROM orders
        WHERE status = 'Completed';
        """,
    )

    print_query(
        connection,
        "Unique customer count by channel",
        """
        SELECT
            sales_channel,
            COUNT(DISTINCT customer_id) AS unique_customers
        FROM orders
        WHERE status = 'Completed'
        GROUP BY sales_channel;
        """,
    )


# ---------------------------------------------------------------------------
# 13. JOIN + AGGREGATION
# ---------------------------------------------------------------------------

def demonstrate_join_aggregation(connection):
    """Show how dimensions from other tables can be used for grouping."""

    print_title("13. JOIN combined with aggregation")

    print(
        """
Real analytical queries often aggregate facts using descriptive dimensions.

Here:
    orders = transactional fact data
    customers = customer dimension
    products = product dimension

A JOIN makes customer names, cities, product names, and categories
available to the aggregation query.
"""
    )

    print_query(
        connection,
        "Revenue by customer segment",
        """
        SELECT
            c.segment,
            COUNT(*) AS order_lines,
            COUNT(DISTINCT o.customer_id) AS customers,
            SUM(o.quantity) AS units,
            SUM(
                o.quantity * o.unit_price
                * (1 - o.discount_percent / 100.0)
            ) AS net_sales
        FROM orders AS o
        INNER JOIN customers AS c
            ON o.customer_id = c.customer_id
        WHERE o.status = 'Completed'
        GROUP BY c.segment
        ORDER BY net_sales DESC;
        """,
    )

    print_query(
        connection,
        "Revenue by product category",
        """
        SELECT
            p.category,
            COUNT(*) AS order_lines,
            SUM(o.quantity) AS units_sold,
            SUM(
                o.quantity * o.unit_price
                * (1 - o.discount_percent / 100.0)
            ) AS net_sales
        FROM orders AS o
        INNER JOIN products AS p
            ON o.product_id = p.product_id
        WHERE o.status = 'Completed'
        GROUP BY p.category
        ORDER BY net_sales DESC;
        """,
    )

    print_query(
        connection,
        "Revenue by customer city",
        """
        SELECT
            c.city,
            COUNT(DISTINCT c.customer_id) AS customers,
            SUM(
                o.quantity * o.unit_price
                * (1 - o.discount_percent / 100.0)
            ) AS net_sales
        FROM orders AS o
        INNER JOIN customers AS c
            ON o.customer_id = c.customer_id
        WHERE o.status = 'Completed'
        GROUP BY c.city
        ORDER BY net_sales DESC;
        """,
    )


# ---------------------------------------------------------------------------
# 14. LEFT JOIN AND ZERO-COUNT GROUPS
# ---------------------------------------------------------------------------

def demonstrate_left_join_counts(connection):
    """
    Show why COUNT(*) and COUNT(joined_column) can produce different results.

    The products table includes every product, while orders contain only
    products that have been purchased. LEFT JOIN preserves products with
    no matching orders.
    """

    print_title("14. LEFT JOIN and zero-count groups")

    print_query(
        connection,
        "Products including products with no matching orders",
        """
        SELECT
            p.product_name,
            COUNT(o.order_id) AS order_count,
            COALESCE(SUM(o.quantity), 0) AS units_sold
        FROM products AS p
        LEFT JOIN orders AS o
            ON p.product_id = o.product_id
            AND o.status = 'Completed'
        GROUP BY p.product_id, p.product_name
        ORDER BY units_sold DESC;
        """,
    )

    print(
        """
Why COUNT(o.order_id) matters:

With a LEFT JOIN, an unmatched product still creates a result row,
but the joined order columns are NULL.

COUNT(o.order_id) counts only actual matching orders.

COUNT(*) would count the preserved LEFT JOIN row itself and could therefore
return 1 for a product with no orders.

COALESCE converts NULL SUM results into zero for reporting.
"""
    )


# ---------------------------------------------------------------------------
# 15. CONDITIONAL AGGREGATION
# ---------------------------------------------------------------------------

def demonstrate_conditional_aggregation(connection):
    """Use CASE inside aggregate functions."""

    print_title("15. Conditional aggregation")

    print(
        """
Conditional aggregation calculates several filtered metrics in one query.

A common pattern is:

    SUM(CASE WHEN condition THEN value ELSE 0 END)

For counts:

    SUM(CASE WHEN condition THEN 1 ELSE 0 END)

This is useful for dashboards because multiple metrics can be returned
without running a separate query for each metric.
"""
    )

    print_query(
        connection,
        "Completed and cancelled orders in one query",
        """
        SELECT
            COUNT(*) AS total_orders,
            SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END)
                AS completed_orders,
            SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END)
                AS cancelled_orders
        FROM orders;
        """,
    )

    print_query(
        connection,
        "Channel-level conditional metrics",
        """
        SELECT
            sales_channel,
            SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END)
                AS completed_orders,
            SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END)
                AS cancelled_orders,
            SUM(
                CASE
                    WHEN status = 'Completed'
                    THEN quantity * unit_price
                    ELSE 0
                END
            ) AS completed_gross_sales
        FROM orders
        GROUP BY sales_channel;
        """,
    )


# ---------------------------------------------------------------------------
# 16. CASE WITH AGGREGATION
# ---------------------------------------------------------------------------

def demonstrate_case_bucketing(connection):
    """Create analytical groups with CASE."""

    print_title("16. CASE expressions and aggregation")

    print_query(
        connection,
        "Group orders into quantity bands",
        """
        SELECT
            CASE
                WHEN quantity = 1 THEN 'Single item'
                WHEN quantity BETWEEN 2 AND 4 THEN '2-4 items'
                WHEN quantity BETWEEN 5 AND 9 THEN '5-9 items'
                ELSE '10+ items'
            END AS quantity_band,
            COUNT(*) AS order_lines,
            SUM(quantity) AS units
        FROM orders
        WHERE status = 'Completed'
        GROUP BY quantity_band
        ORDER BY
            CASE quantity_band
                WHEN 'Single item' THEN 1
                WHEN '2-4 items' THEN 2
                WHEN '5-9 items' THEN 3
                ELSE 4
            END;
        """,
    )


# ---------------------------------------------------------------------------
# 17. AGGREGATION OF EXPRESSIONS
# ---------------------------------------------------------------------------

def demonstrate_expression_aggregation(connection):
    """Demonstrate calculations inside aggregate functions."""

    print_title("17. Aggregating calculated expressions")

    print(
        """
A database does not need to store every analytical metric as a column.

For example:

    quantity * unit_price

calculates gross line revenue.

Then:

    SUM(quantity * unit_price)

calculates total gross revenue.

This reduces unnecessary duplicated storage but requires careful definition
of business logic.
"""
    )

    print_query(
        connection,
        "Gross sales, discount amount, and net sales",
        """
        SELECT
            SUM(quantity * unit_price) AS gross_sales,
            SUM(
                quantity * unit_price * discount_percent / 100.0
            ) AS discount_amount,
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS net_sales
        FROM orders
        WHERE status = 'Completed';
        """,
    )


# ---------------------------------------------------------------------------
# 18. PROFIT AGGREGATION
# ---------------------------------------------------------------------------

def demonstrate_profit(connection):
    """Calculate revenue and estimated gross profit."""

    print_title("18. Aggregating revenue and profit")

    print(
        """
The product table contains a cost price.

Gross profit per line can be estimated as:

    quantity * (selling price after discount - cost price)

This demonstrates why joining transactional and master data is important
for business analytics.
"""
    )

    print_query(
        connection,
        "Profit by product category",
        """
        SELECT
            p.category,
            SUM(
                o.quantity * o.unit_price
                * (1 - o.discount_percent / 100.0)
            ) AS revenue,
            SUM(
                o.quantity * (
                    o.unit_price
                    * (1 - o.discount_percent / 100.0)
                    - p.cost_price
                )
            ) AS gross_profit
        FROM orders AS o
        INNER JOIN products AS p
            ON o.product_id = p.product_id
        WHERE o.status = 'Completed'
        GROUP BY p.category
        ORDER BY gross_profit DESC;
        """,
    )


# ---------------------------------------------------------------------------
# 19. SUBQUERIES WITH AGGREGATES
# ---------------------------------------------------------------------------

def demonstrate_subqueries(connection):
    """Use an aggregate subquery to compare groups with a global metric."""

    print_title("19. Aggregate subqueries")

    print_query(
        connection,
        "Customers whose sales exceed average customer sales",
        """
        SELECT
            customer_sales.customer_id,
            customer_sales.total_sales
        FROM (
            SELECT
                customer_id,
                SUM(
                    quantity * unit_price
                    * (1 - discount_percent / 100.0)
                ) AS total_sales
            FROM orders
            WHERE status = 'Completed'
            GROUP BY customer_id
        ) AS customer_sales
        WHERE customer_sales.total_sales > (
            SELECT AVG(total_sales)
            FROM (
                SELECT
                    customer_id,
                    SUM(
                        quantity * unit_price
                        * (1 - discount_percent / 100.0)
                    ) AS total_sales
                FROM orders
                WHERE status = 'Completed'
                GROUP BY customer_id
            )
        )
        ORDER BY customer_sales.total_sales DESC;
        """,
    )


# ---------------------------------------------------------------------------
# 20. COMMON TABLE EXPRESSIONS
# ---------------------------------------------------------------------------

def demonstrate_cte(connection):
    """Use a CTE to make multi-stage aggregation easier to read."""

    print_title("20. Common Table Expressions")

    print(
        """
A Common Table Expression, or CTE, is introduced with WITH.

It is useful when a query naturally has multiple logical stages.

Example:

    Stage 1: calculate customer-level sales.
    Stage 2: calculate the average of those customer-level sales.
    Stage 3: compare each customer against the average.

CTEs often improve readability compared with deeply nested subqueries.
"""
    )

    print_query(
        connection,
        "Customer sales compared with average customer sales",
        """
        WITH customer_sales AS (
            SELECT
                customer_id,
                SUM(
                    quantity * unit_price
                    * (1 - discount_percent / 100.0)
                ) AS total_sales
            FROM orders
            WHERE status = 'Completed'
            GROUP BY customer_id
        ),
        benchmark AS (
            SELECT AVG(total_sales) AS average_customer_sales
            FROM customer_sales
        )
        SELECT
            cs.customer_id,
            cs.total_sales,
            b.average_customer_sales,
            cs.total_sales - b.average_customer_sales
                AS difference_from_average
        FROM customer_sales AS cs
        CROSS JOIN benchmark AS b
        ORDER BY cs.total_sales DESC;
        """,
    )


# ---------------------------------------------------------------------------
# 21. RATIO AND PERCENTAGE METRICS
# ---------------------------------------------------------------------------

def demonstrate_percentages(connection):
    """Calculate percentages from aggregated values."""

    print_title("21. Percentages and ratios")

    print(
        """
Ratios require careful control of numeric types.

In some database systems, dividing two integers can perform integer
division. Using a decimal such as 100.0 helps force decimal arithmetic.

The following example calculates each channel's share of total completed
sales.
"""
    )

    print_query(
        connection,
        "Channel sales percentage",
        """
        WITH channel_sales AS (
            SELECT
                sales_channel,
                SUM(
                    quantity * unit_price
                    * (1 - discount_percent / 100.0)
                ) AS sales
            FROM orders
            WHERE status = 'Completed'
            GROUP BY sales_channel
        ),
        total_sales AS (
            SELECT SUM(sales) AS total
            FROM channel_sales
        )
        SELECT
            cs.sales_channel,
            cs.sales,
            ROUND(cs.sales * 100.0 / ts.total, 2) AS sales_percentage
        FROM channel_sales AS cs
        CROSS JOIN total_sales AS ts
        ORDER BY cs.sales DESC;
        """,
    )


# ---------------------------------------------------------------------------
# 22. WEIGHTED AVERAGE
# ---------------------------------------------------------------------------

def demonstrate_weighted_average(connection):
    """Demonstrate why a simple AVG can be different from a weighted average."""

    print_title("22. Weighted average")

    print(
        """
A simple average gives every row equal weight.

That may be incorrect for some business questions.

Suppose different quantities were sold at different unit prices.
The average unit price across order lines is not the same as the average
price paid per unit.

A weighted average unit price is:

    SUM(quantity * unit_price) / SUM(quantity)

This gives each physical unit appropriate weight.
"""
    )

    print_query(
        connection,
        "Simple versus weighted average unit price",
        """
        SELECT
            AVG(unit_price) AS simple_average_unit_price,
            SUM(quantity * unit_price)
                / NULLIF(SUM(quantity), 0)
                AS weighted_average_unit_price
        FROM orders
        WHERE status = 'Completed';
        """,
    )


# ---------------------------------------------------------------------------
# 23. AVG AND NULL
# ---------------------------------------------------------------------------

def demonstrate_null_behavior(connection):
    """Create a temporary table to demonstrate NULL behavior precisely."""

    print_title("23. NULL behavior in aggregate functions")

    connection.execute(
        """
        CREATE TEMP TABLE nullable_values (
            id INTEGER,
            amount REAL
        );
        """
    )

    connection.executemany(
        "INSERT INTO nullable_values (id, amount) VALUES (?, ?)",
        [
            (1, 10.0),
            (2, 20.0),
            (3, None),
            (4, 30.0),
        ],
    )

    print_query(
        connection,
        "COUNT(*) versus COUNT(amount)",
        """
        SELECT
            COUNT(*) AS row_count,
            COUNT(amount) AS non_null_amount_count
        FROM nullable_values;
        """,
    )

    print_query(
        connection,
        "SUM and AVG ignore NULL amounts",
        """
        SELECT
            SUM(amount) AS total_amount,
            AVG(amount) AS average_amount,
            MIN(amount) AS minimum_amount,
            MAX(amount) AS maximum_amount
        FROM nullable_values;
        """,
    )

    print(
        """
Important behavior:

    COUNT(*) counts rows, including rows containing NULLs.

    COUNT(amount) counts only non-NULL amount values.

    SUM, AVG, MIN, and MAX ignore NULL values.

If every input value is NULL, SUM, AVG, MIN, and MAX generally return NULL.
COALESCE can be used when the application requires a numeric default.
"""
    )


# ---------------------------------------------------------------------------
# 24. COALESCE
# ---------------------------------------------------------------------------

def demonstrate_coalesce(connection):
    """Demonstrate replacing NULL aggregate results."""

    print_title("24. COALESCE with aggregation")

    print_query(
        connection,
        "COALESCE converts NULL totals to zero",
        """
        SELECT
            COALESCE(SUM(quantity), 0) AS units
        FROM orders
        WHERE status = 'A_STATUS_THAT_DOES_NOT_EXIST';
        """,
    )

    print(
        """
Do not automatically replace every NULL with zero.

NULL can mean:
    - unknown,
    - missing,
    - not applicable,
    - no matching rows.

Zero means:
    - a known numeric quantity equal to zero.

The correct choice depends on the business meaning.
"""
    )


# ---------------------------------------------------------------------------
# 25. GROUP BY DATE PERIODS
# ---------------------------------------------------------------------------

def demonstrate_date_aggregation(connection):
    """Demonstrate month-level and year-level aggregation."""

    print_title("25. Date-based aggregation")

    print_query(
        connection,
        "Monthly sales",
        """
        SELECT
            substr(order_date, 1, 7) AS order_month,
            COUNT(*) AS order_lines,
            SUM(quantity) AS units,
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS net_sales
        FROM orders
        WHERE status = 'Completed'
        GROUP BY order_month
        ORDER BY order_month;
        """,
    )

    print_query(
        connection,
        "Year-level sales",
        """
        SELECT
            substr(order_date, 1, 4) AS order_year,
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS net_sales
        FROM orders
        WHERE status = 'Completed'
        GROUP BY order_year;
        """,
    )

    print(
        """
Date grouping should match the database's date type and dialect.

This example uses SQLite text dates in ISO format.

Production systems often use native DATE or TIMESTAMP types and
database-specific date functions.
"""
    )


# ---------------------------------------------------------------------------
# 26. GROUP BY AND ORDER BY
# ---------------------------------------------------------------------------

def demonstrate_ordering_groups(connection):
    """Demonstrate ordering aggregate results."""

    print_title("26. ORDER BY aggregated results")

    print_query(
        connection,
        "Top customers by net sales",
        """
        SELECT
            customer_id,
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS net_sales
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id
        ORDER BY net_sales DESC
        LIMIT 5;
        """,
    )

    print(
        """
ORDER BY is applied after grouped results have been produced.

Aliases such as net_sales can often be used in ORDER BY, which makes
analytical queries easier to read.
"""
    )


# ---------------------------------------------------------------------------
# 27. GROUP BY AND LIMIT
# ---------------------------------------------------------------------------

def demonstrate_top_n(connection):
    """Demonstrate top-N aggregation."""

    print_title("27. Top-N grouped results")

    print_query(
        connection,
        "Top three products by units sold",
        """
        SELECT
            p.product_name,
            SUM(o.quantity) AS units_sold
        FROM orders AS o
        INNER JOIN products AS p
            ON o.product_id = p.product_id
        WHERE o.status = 'Completed'
        GROUP BY p.product_id, p.product_name
        ORDER BY units_sold DESC
        LIMIT 3;
        """,
    )


# ---------------------------------------------------------------------------
# 28. GROUP BY A DERIVED CATEGORY
# ---------------------------------------------------------------------------

def demonstrate_margin_bands(connection):
    """Calculate margin percentages and group products by profitability."""

    print_title("28. Grouping by calculated business metrics")

    print_query(
        connection,
        "Product margin bands",
        """
        WITH product_metrics AS (
            SELECT
                p.product_id,
                p.product_name,
                p.category,
                p.unit_price,
                p.cost_price,
                (
                    (p.unit_price - p.cost_price)
                    * 100.0
                    / NULLIF(p.unit_price, 0)
                ) AS margin_percent
            FROM products AS p
        )
        SELECT
            CASE
                WHEN margin_percent < 20 THEN 'Low margin'
                WHEN margin_percent < 40 THEN 'Medium margin'
                ELSE 'High margin'
            END AS margin_band,
            COUNT(*) AS product_count,
            AVG(margin_percent) AS average_margin
        FROM product_metrics
        GROUP BY margin_band
        ORDER BY average_margin;
        """,
    )


# ---------------------------------------------------------------------------
# 29. GROUP BY WITH HAVING AND MULTIPLE METRICS
# ---------------------------------------------------------------------------

def demonstrate_having_complex(connection):
    """Use multiple aggregate conditions in HAVING."""

    print_title("29. Multiple conditions in HAVING")

    print_query(
        connection,
        "Customers with at least two completed order lines and high sales",
        """
        SELECT
            customer_id,
            COUNT(*) AS order_lines,
            SUM(quantity) AS units,
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS net_sales
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id
        HAVING
            COUNT(*) >= 2
            AND SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) > 50000
        ORDER BY net_sales DESC;
        """,
    )


# ---------------------------------------------------------------------------
# 30. AGGREGATION AFTER JOIN: DUPLICATION RISK
# ---------------------------------------------------------------------------

def demonstrate_join_duplication_risk(connection):
    """
    Explain a major production-level aggregation problem:
    many-to-many joins can multiply rows and inflate aggregates.
    """

    print_title("30. Join duplication risk")

    print(
        """
Aggregates are only correct when the query's row grain is understood.

If a JOIN turns one business event into several rows, SUM and COUNT can
become inflated.

Example:

    One order line
        JOIN
    Multiple matching dimension rows
        =
    Multiple result rows for the same order line

The safest practice is to identify the intended grain before aggregating.

In this dataset, products and customers have one row per ID, so the
JOINs used above preserve the order-line grain.
"""
    )

    print_query(
        connection,
        "Verify order-line grain",
        """
        SELECT
            COUNT(*) AS order_rows,
            COUNT(DISTINCT order_id) AS distinct_order_ids
        FROM orders;
        """,
    )


# ---------------------------------------------------------------------------
# 31. AGGREGATE QUERY GRAIN
# ---------------------------------------------------------------------------

def demonstrate_grain(connection):
    """Show how grouping changes the grain of a result."""

    print_title("31. Understanding result grain")

    print(
        """
Grain means what one row represents.

Examples:

    orders table:
        one row = one order line

    GROUP BY customer_id:
        one row = one customer

    GROUP BY category:
        one row = one product category

    GROUP BY customer_id, product_id:
        one row = one customer-product combination

Before writing an aggregate query, define the desired grain.
"""
    )

    print_query(
        connection,
        "Customer-product grain",
        """
        SELECT
            customer_id,
            product_id,
            SUM(quantity) AS units
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id, product_id
        ORDER BY customer_id, product_id;
        """,
    )


# ---------------------------------------------------------------------------
# 32. GROUP BY WITH JOINED NAMES
# ---------------------------------------------------------------------------

def demonstrate_named_reporting(connection):
    """Produce a human-readable customer report."""

    print_title("32. Human-readable grouped reporting")

    print_query(
        connection,
        "Customer sales report",
        """
        SELECT
            c.customer_name,
            c.segment,
            c.city,
            COUNT(o.order_id) AS completed_order_lines,
            SUM(o.quantity) AS units,
            ROUND(
                SUM(
                    o.quantity * o.unit_price
                    * (1 - o.discount_percent / 100.0)
                ),
                2
            ) AS net_sales
        FROM customers AS c
        INNER JOIN orders AS o
            ON c.customer_id = o.customer_id
        WHERE o.status = 'Completed'
        GROUP BY
            c.customer_id,
            c.customer_name,
            c.segment,
            c.city
        ORDER BY net_sales DESC;
        """,
    )


# ---------------------------------------------------------------------------
# 33. GROUPING WITHOUT AGGREGATE FUNCTIONS
# ---------------------------------------------------------------------------

def demonstrate_group_by_distinct(connection):
    """Explain that GROUP BY can also produce unique combinations."""

    print_title("33. GROUP BY versus DISTINCT")

    print_query(
        connection,
        "Unique customer-city combinations using GROUP BY",
        """
        SELECT
            city,
            segment
        FROM customers
        GROUP BY city, segment
        ORDER BY city, segment;
        """,
    )

    print_query(
        connection,
        "Equivalent uniqueness operation using DISTINCT",
        """
        SELECT DISTINCT
            city,
            segment
        FROM customers
        ORDER BY city, segment;
        """,
    )

    print(
        """
DISTINCT is generally clearer when the goal is simply to remove duplicate
combinations.

GROUP BY is more appropriate when aggregate calculations are involved.
"""
    )


# ---------------------------------------------------------------------------
# 34. GROUP BY AND NULL GROUPS
# ---------------------------------------------------------------------------

def demonstrate_null_groups(connection):
    """Show how NULL behaves as a grouping value."""

    print_title("34. NULL as a GROUP BY value")

    connection.execute(
        """
        CREATE TEMP TABLE nullable_groups (
            id INTEGER,
            department TEXT,
            amount REAL
        );
        """
    )

    connection.executemany(
        """
        INSERT INTO nullable_groups
        (id, department, amount)
        VALUES (?, ?, ?)
        """,
        [
            (1, "Technology", 100),
            (2, "Technology", 200),
            (3, None, 150),
            (4, None, 250),
        ],
    )

    print_query(
        connection,
        "NULL values form their own group",
        """
        SELECT
            department,
            COUNT(*) AS row_count,
            SUM(amount) AS total_amount
        FROM nullable_groups
        GROUP BY department;
        """,
    )

    print(
        """
In GROUP BY, rows with NULL in the grouping expression are grouped
together.

This differs from ordinary equality logic, where NULL is not compared
using = in the same way as ordinary values.
"""
    )


# ---------------------------------------------------------------------------
# 35. AGGREGATES OVER EMPTY INPUT
# ---------------------------------------------------------------------------

def demonstrate_empty_input(connection):
    """Demonstrate aggregate behavior when no rows match."""

    print_title("35. Aggregates over an empty input")

    print_query(
        connection,
        "Aggregate result when WHERE matches no rows",
        """
        SELECT
            COUNT(*) AS count_rows,
            SUM(quantity) AS total_quantity,
            AVG(quantity) AS average_quantity,
            MIN(quantity) AS minimum_quantity,
            MAX(quantity) AS maximum_quantity
        FROM orders
        WHERE order_date = '1900-01-01';
        """,
    )

    print(
        """
COUNT(*) returns 0 because there are zero rows.

SUM, AVG, MIN, and MAX return NULL because there is no value from which
to calculate the corresponding result.

This distinction is important in reporting and application code.
"""
    )


# ---------------------------------------------------------------------------
# 36. CONDITIONAL COUNT USING FILTER-LIKE LOGIC
# ---------------------------------------------------------------------------

def demonstrate_conditional_counts(connection):
    """Show several approaches to conditional counts."""

    print_title("36. Conditional counts")

    print_query(
        connection,
        "Conditional counts with CASE",
        """
        SELECT
            SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END)
                AS completed_count,
            SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END)
                AS cancelled_count
        FROM orders;
        """,
    )

    print(
        """
Some SQL dialects also support:

    COUNT(*) FILTER (WHERE condition)

SQLite supports FILTER in modern versions, but CASE is demonstrated here
because CASE-based conditional aggregation is broadly portable across
SQL systems.
"""
    )

    print_query(
        connection,
        "Conditional counts with FILTER",
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'Completed')
                AS completed_count,
            COUNT(*) FILTER (WHERE status = 'Cancelled')
                AS cancelled_count
        FROM orders;
        """,
    )


# ---------------------------------------------------------------------------
# 37. WINDOW FUNCTIONS VERSUS GROUP BY
# ---------------------------------------------------------------------------

def demonstrate_window_vs_group_by(connection):
    """Compare grouped aggregation with window aggregation."""

    print_title("37. GROUP BY versus window aggregation")

    print(
        """
GROUP BY collapses multiple rows into fewer rows.

Window functions calculate across related rows while preserving the
individual rows.

GROUP BY example:

    one row per customer

Window example:

    every order row remains visible,
    while customer total sales are added to each order row.

This distinction is fundamental in analytical SQL.
"""
    )

    print_query(
        connection,
        "GROUP BY produces one row per customer",
        """
        SELECT
            customer_id,
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS customer_sales
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id
        ORDER BY customer_id;
        """,
    )

    print_query(
        connection,
        "Window SUM preserves individual order rows",
        """
        SELECT
            order_id,
            customer_id,
            quantity,
            unit_price,
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) OVER (
                PARTITION BY customer_id
            ) AS customer_total_sales
        FROM orders
        WHERE status = 'Completed'
        ORDER BY customer_id, order_id;
        """,
    )


# ---------------------------------------------------------------------------
# 38. WINDOW RANKING AFTER AGGREGATION
# ---------------------------------------------------------------------------

def demonstrate_ranking_aggregates(connection):
    """Rank customers using aggregated sales."""

    print_title("38. Ranking aggregated results")

    print_query(
        connection,
        "Rank customers by sales",
        """
        WITH customer_sales AS (
            SELECT
                customer_id,
                SUM(
                    quantity * unit_price
                    * (1 - discount_percent / 100.0)
                ) AS total_sales
            FROM orders
            WHERE status = 'Completed'
            GROUP BY customer_id
        )
        SELECT
            customer_id,
            total_sales,
            RANK() OVER (
                ORDER BY total_sales DESC
            ) AS sales_rank
        FROM customer_sales
        ORDER BY sales_rank;
        """,
    )


# ---------------------------------------------------------------------------
# 39. ADVANCED GROUPING LOGIC
# ---------------------------------------------------------------------------

def demonstrate_rollup_concept(connection):
    """
    Explain ROLLUP without relying on SQLite-specific unsupported syntax.

    Many production database systems support GROUP BY ROLLUP for subtotals
    and grand totals. SQLite does not provide the same syntax.
    """

    print_title("39. ROLLUP and subtotal concepts")

    print(
        """
Advanced SQL dialects may provide GROUP BY ROLLUP, CUBE, or GROUPING SETS.

These features can calculate:

    category + channel detail
    category subtotal
    channel subtotal
    grand total

SQLite does not support the standard ROLLUP syntax, so the same idea can
be demonstrated explicitly with UNION ALL.
"""
    )

    print_query(
        connection,
        "Detail rows, category subtotals, and grand total",
        """
        SELECT
            p.category,
            o.sales_channel,
            SUM(
                o.quantity * o.unit_price
                * (1 - o.discount_percent / 100.0)
            ) AS net_sales
        FROM orders AS o
        JOIN products AS p
            ON o.product_id = p.product_id
        WHERE o.status = 'Completed'
        GROUP BY p.category, o.sales_channel

        UNION ALL

        SELECT
            p.category,
            'ALL CHANNELS' AS sales_channel,
            SUM(
                o.quantity * o.unit_price
                * (1 - o.discount_percent / 100.0)
            ) AS net_sales
        FROM orders AS o
        JOIN products AS p
            ON o.product_id = p.product_id
        WHERE o.status = 'Completed'
        GROUP BY p.category

        UNION ALL

        SELECT
            'ALL CATEGORIES' AS category,
            'ALL CHANNELS' AS sales_channel,
            SUM(
                o.quantity * o.unit_price
                * (1 - o.discount_percent / 100.0)
            ) AS net_sales
        FROM orders AS o
        WHERE o.status = 'Completed'

        ORDER BY category, sales_channel;
        """,
    )


# ---------------------------------------------------------------------------
# 40. SQL INJECTION SAFETY
# ---------------------------------------------------------------------------

def demonstrate_parameterized_aggregation(connection):
    """Demonstrate safe parameters in an aggregate query."""

    print_title("40. Parameterized SQL and security")

    city = "Delhi"

    print_query(
        connection,
        "Safe parameterized query",
        """
        SELECT
            COUNT(*) AS order_count,
            SUM(
                o.quantity * o.unit_price
                * (1 - o.discount_percent / 100.0)
            ) AS net_sales
        FROM orders AS o
        JOIN customers AS c
            ON o.customer_id = c.customer_id
        WHERE c.city = ?
          AND o.status = 'Completed';
        """,
        (city,),
    )

    print(
        """
Never construct SQL by directly concatenating untrusted input.

Unsafe conceptual pattern:

    "... WHERE city = '" + user_input + "'"

Use parameter placeholders instead:

    "... WHERE city = ?"

and pass the value separately.

Parameterized SQL prevents user data from being interpreted as SQL syntax.
"""
    )


# ---------------------------------------------------------------------------
# 41. EXPLAIN QUERY PLAN
# ---------------------------------------------------------------------------

def demonstrate_query_plan(connection):
    """Inspect a query plan for performance analysis."""

    print_title("41. Query plans and performance")

    query = """
        SELECT
            customer_id,
            SUM(quantity * unit_price) AS gross_sales
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id;
    """

    print("Query:")
    print(query.strip())

    rows = execute_query(
        connection,
        "EXPLAIN QUERY PLAN " + query,
    )

    print("\nSQLite query plan:")
    print_rows(rows)

    print(
        """
EXPLAIN QUERY PLAN helps inspect how a database intends to execute a query.

For large production datasets, aggregation performance depends on factors
such as:

    - table size,
    - indexes,
    - filtering selectivity,
    - join strategy,
    - grouping cardinality,
    - sorting requirements,
    - memory available for intermediate results,
    - database engine and configuration.

Indexes can accelerate filtering and joins, but they also have storage
and write-maintenance costs.
"""
    )


# ---------------------------------------------------------------------------
# 42. INDEX FOR FILTERING
# ---------------------------------------------------------------------------

def demonstrate_indexing(connection):
    """Create an index and inspect its role in a grouped query."""

    print_title("42. Indexing considerations")

    connection.execute(
        """
        CREATE INDEX idx_orders_status_customer
        ON orders(status, customer_id);
        """
    )

    query = """
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id;
    """

    print_query(
        connection,
        "Grouped query after creating a filtering/grouping index",
        query,
    )

    print(
        """
An index on (status, customer_id) may help because the query filters on
status and groups by customer_id.

Index usefulness is workload-dependent. An index is not automatically
beneficial for every aggregation query.

Production optimization should be based on actual query plans and
representative data volumes rather than assumptions.
"""
    )


# ---------------------------------------------------------------------------
# 43. DATA QUALITY VALIDATION
# ---------------------------------------------------------------------------

def demonstrate_data_quality_checks(connection):
    """Use aggregates to detect data-quality problems."""

    print_title("43. Aggregation for data-quality checks")

    print_query(
        connection,
        "Detect invalid quantities",
        """
        SELECT
            COUNT(*) AS invalid_quantity_rows
        FROM orders
        WHERE quantity <= 0;
        """,
    )

    print_query(
        connection,
        "Detect invalid discounts",
        """
        SELECT
            COUNT(*) AS invalid_discount_rows
        FROM orders
        WHERE discount_percent < 0
           OR discount_percent > 100;
        """,
    )

    print_query(
        connection,
        "Detect invalid prices",
        """
        SELECT
            COUNT(*) AS invalid_price_rows
        FROM orders
        WHERE unit_price < 0;
        """,
    )

    print(
        """
Aggregations are not only for dashboards.

COUNT, MIN, MAX, and SUM are also useful for validation.

Examples:

    COUNT(*) WHERE quantity <= 0
    MIN(price)
    MAX(discount)
    COUNT(DISTINCT business_key)

These checks can identify unexpected source-data conditions before
aggregated reports are trusted.
"""
    )


# ---------------------------------------------------------------------------
# 44. BUSINESS METRIC VALIDATION
# ---------------------------------------------------------------------------

def demonstrate_reconciliation(connection):
    """Reconcile total sales with grouped sales."""

    print_title("44. Reconciliation of aggregated results")

    overall = execute_query(
        connection,
        """
        SELECT
            SUM(
                quantity * unit_price
                * (1 - discount_percent / 100.0)
            ) AS total_sales
        FROM orders
        WHERE status = 'Completed';
        """,
    )[0]["total_sales"]

    grouped = execute_query(
        connection,
        """
        SELECT
            SUM(customer_sales) AS total_grouped_sales
        FROM (
            SELECT
                customer_id,
                SUM(
                    quantity * unit_price
                    * (1 - discount_percent / 100.0)
                ) AS customer_sales
            FROM orders
            WHERE status = 'Completed'
            GROUP BY customer_id
        );
        """,
    )[0]["total_grouped_sales"]

    print(f"Overall sales:       {overall:.2f}")
    print(f"Grouped sales total: {grouped:.2f}")
    print(f"Difference:          {overall - grouped:.2f}")

    print(
        """
A powerful production habit is reconciliation.

For additive metrics, the sum of correctly grouped subtotals should often
match the corresponding overall total.

Unexpected differences can indicate:

    - duplicate joins,
    - incorrect filters,
    - missing records,
    - incorrect grouping,
    - NULL handling problems,
    - different business definitions.
"""
    )


# ---------------------------------------------------------------------------
# 45. AGGREGATION TESTS
# ---------------------------------------------------------------------------

def run_tests(connection):
    """Run assertions that validate important aggregation behavior."""

    print_title("45. Automated aggregation tests")

    total_orders = execute_query(
        connection,
        "SELECT COUNT(*) AS value FROM orders",
    )[0]["value"]

    assert total_orders == 24, "Expected 24 sample orders."

    completed_orders = execute_query(
        connection,
        """
        SELECT COUNT(*) AS value
        FROM orders
        WHERE status = 'Completed'
        """,
    )[0]["value"]

    cancelled_orders = execute_query(
        connection,
        """
        SELECT COUNT(*) AS value
        FROM orders
        WHERE status = 'Cancelled'
        """,
    )[0]["value"]

    assert completed_orders + cancelled_orders == total_orders

    distinct_customers = execute_query(
        connection,
        """
        SELECT COUNT(DISTINCT customer_id) AS value
        FROM orders
        """,
    )[0]["value"]

    assert distinct_customers == 10

    minimum_quantity = execute_query(
        connection,
        """
        SELECT MIN(quantity) AS value
        FROM orders
        """,
    )[0]["value"]

    maximum_quantity = execute_query(
        connection,
        """
        SELECT MAX(quantity) AS value
        FROM orders
        """,
    )[0]["value"]

    assert minimum_quantity == 1
    assert maximum_quantity == 10

    null_test = execute_query(
        connection,
        """
        SELECT
            COUNT(*) AS all_rows,
            COUNT(amount) AS non_null_rows
        FROM nullable_values
        """,
    )[0]

    assert null_test["all_rows"] == 4
    assert null_test["non_null_rows"] == 3

    print("All aggregation tests passed.")


# ---------------------------------------------------------------------------
# 46. COMMON MISTAKES
# ---------------------------------------------------------------------------

def demonstrate_common_mistakes():
    """Print common aggregation mistakes as executable-study notes."""

    print_title("46. Common aggregation mistakes")

    print(
        """
1. Using WHERE for aggregate conditions

Wrong:
    WHERE COUNT(*) > 5

Correct:
    HAVING COUNT(*) > 5

2. Counting rows after an accidental many-to-many JOIN

A JOIN can multiply records and inflate COUNT and SUM.

3. Confusing COUNT(*) and COUNT(column)

COUNT(*) counts rows.
COUNT(column) ignores NULL values.

4. Assuming AVG always represents the business metric needed

A simple average may be inappropriate when observations have different
weights.

5. Forgetting NULL behavior

SUM(NULL) does not mean zero.
AVG ignores NULL values.

6. Dividing integers when decimal precision is required

Use decimal arithmetic deliberately.

7. Grouping at the wrong grain

A report can be mathematically valid SQL but conceptually wrong if the
grouping level does not match the business question.

8. Ignoring cancelled, returned, or refunded records

Business metrics require explicit status definitions.

9. Relying on implicit column selection in GROUP BY

Portable SQL should explicitly group all selected non-aggregated columns.

10. Treating aliases as universally available everywhere

Alias support differs by SQL clause and database dialect.

11. Assuming aggregate ordering is stable without ORDER BY

SQL does not guarantee result ordering unless ORDER BY is specified.

12. Replacing every NULL with zero

NULL and zero have different meanings.

13. Using SELECT * in analytical production queries

Explicit columns make grain, dependencies, and performance easier to
understand.

14. Building SQL through string concatenation

Use parameterized SQL for user-supplied values.
"""
    )


# ---------------------------------------------------------------------------
# 47. PORTABILITY CONSIDERATIONS
# ---------------------------------------------------------------------------

def demonstrate_sql_dialect_notes():
    """Explain differences between SQL implementations."""

    print_title("47. SQL dialect considerations")

    print(
        """
SQL is standardized, but individual database systems implement dialects.

The examples use SQLite because it is available through Python's standard
library.

Production environments may use:

    PostgreSQL
    MySQL
    Microsoft SQL Server
    Oracle Database
    Snowflake
    BigQuery
    Databricks SQL
    and other systems.

Aggregation concepts such as COUNT, SUM, AVG, MIN, MAX, GROUP BY, WHERE,
and HAVING are widely supported.

Syntax around:

    date functions,
    ROLLUP,
    GROUPING SETS,
    FILTER,
    type conversion,
    numeric precision,
    NULL handling details,
    optimizer behavior

can vary between database systems.

Always verify dialect-specific syntax before moving a query between
database engines.
"""
    )


# ---------------------------------------------------------------------------
# 48. PRECISION CONSIDERATIONS
# ---------------------------------------------------------------------------

def demonstrate_numeric_precision():
    """Explain monetary precision without pretending SQLite REAL is exact."""

    print_title("48. Numeric precision and monetary values")

    print(
        """
This educational database uses SQLite REAL values for simplicity.

Floating-point types are convenient but are not ideal for exact financial
accounting because binary floating-point representation can introduce
small rounding differences.

For financial production systems, use a database NUMERIC/DECIMAL type
with an explicitly chosen scale and precision where supported.

Python's Decimal type is also useful when exact decimal arithmetic is
required in application code.
"""
    )

    amount_a = Decimal("100.10")
    amount_b = Decimal("0.20")

    print("Decimal example:")
    print(f"{amount_a} + {amount_b} = {amount_a + amount_b}")


# ---------------------------------------------------------------------------
# 49. PRACTICAL REPORT
# ---------------------------------------------------------------------------

def generate_business_report(connection):
    """Generate a concise multi-metric business report."""

    print_title("49. Practical aggregation report")

    report_query = """
        SELECT
            p.category,
            COUNT(DISTINCT o.order_id) AS order_lines,
            COUNT(DISTINCT o.customer_id) AS customers,
            SUM(o.quantity) AS units_sold,
            ROUND(
                SUM(
                    o.quantity * o.unit_price
                    * (1 - o.discount_percent / 100.0)
                ),
                2
            ) AS revenue,
            ROUND(
                AVG(o.discount_percent),
                2
            ) AS average_discount,
            ROUND(
                SUM(
                    o.quantity * (
                        o.unit_price
                        * (1 - o.discount_percent / 100.0)
                        - p.cost_price
                    )
                ),
                2
            ) AS gross_profit
        FROM orders AS o
        JOIN products AS p
            ON o.product_id = p.product_id
        WHERE o.status = 'Completed'
        GROUP BY p.category
        HAVING revenue > 0
        ORDER BY revenue DESC;
    """

    print_query(
        connection,
        "Category performance report",
        report_query,
    )


# ---------------------------------------------------------------------------
# 50. AGGREGATION DECISION GUIDE
# ---------------------------------------------------------------------------

def print_decision_guide():
    """Print a compact decision guide."""

    print_title("50. Aggregation decision guide")

    print(
        """
Use COUNT when:
    - you need row counts,
    - you need distinct entity counts,
    - you need conditional counts.

Use SUM when:
    - values are additive,
    - you need totals,
    - you need revenue, units, costs, or quantities.

Use AVG when:
    - an arithmetic mean answers the business question,
    - observations have comparable weight,
    - NULL handling is understood.

Use MIN when:
    - you need the earliest date,
    - smallest value,
    - lowest price,
    - minimum measurement.

Use MAX when:
    - you need the latest date,
    - largest value,
    - highest price,
    - maximum measurement.

Use GROUP BY when:
    - you need one aggregate result per category, customer, date period,
      channel, location, or combination of dimensions.

Use HAVING when:
    - a condition depends on an aggregate result.

Use WHERE when:
    - a condition filters individual rows before aggregation.

Use CASE inside aggregates when:
    - several conditional metrics need to be calculated together.

Use JOIN + GROUP BY when:
    - transactional data must be summarized by descriptive attributes.

Use a CTE or subquery when:
    - an aggregate result becomes the input to another calculation.

Use window functions when:
    - you need aggregate context while retaining individual rows.
"""
    )


# ---------------------------------------------------------------------------
# 51. MAIN PROGRAM
# ---------------------------------------------------------------------------

def main():
    """Run the complete SQL aggregation learning program."""

    connection = create_database()

    try:
        create_tables(connection)
        insert_sample_data(connection)

        demonstrate_aggregation_basics(connection)
        demonstrate_count(connection)
        demonstrate_sum(connection)
        demonstrate_avg(connection)
        demonstrate_min_max(connection)
        demonstrate_multiple_aggregates(connection)
        demonstrate_group_by(connection)
        demonstrate_multiple_group_columns(connection)
        demonstrate_where_having(connection)
        demonstrate_distinct(connection)
        demonstrate_join_aggregation(connection)
        demonstrate_left_join_counts(connection)
        demonstrate_conditional_aggregation(connection)
        demonstrate_case_bucketing(connection)
        demonstrate_expression_aggregation(connection)
        demonstrate_profit(connection)
        demonstrate_subqueries(connection)
        demonstrate_cte(connection)
        demonstrate_percentages(connection)
        demonstrate_weighted_average(connection)
        demonstrate_null_behavior(connection)
        demonstrate_coalesce(connection)
        demonstrate_date_aggregation(connection)
        demonstrate_ordering_groups(connection)
        demonstrate_top_n(connection)
        demonstrate_margin_bands(connection)
        demonstrate_having_complex(connection)
        demonstrate_join_duplication_risk(connection)
        demonstrate_grain(connection)
        demonstrate_named_reporting(connection)
        demonstrate_group_by_distinct(connection)
        demonstrate_null_groups(connection)
        demonstrate_empty_input(connection)
        demonstrate_conditional_counts(connection)
        demonstrate_window_vs_group_by(connection)
        demonstrate_ranking_aggregates(connection)
        demonstrate_rollup_concept(connection)
        demonstrate_parameterized_aggregation(connection)
        demonstrate_query_plan(connection)
        demonstrate_indexing(connection)
        demonstrate_data_quality_checks(connection)
        demonstrate_reconciliation(connection)
        run_tests(connection)
        demonstrate_common_mistakes()
        demonstrate_sql_dialect_notes()
        demonstrate_numeric_precision()
        generate_business_report(connection)
        print_decision_guide()

        print_title("Program completed")
        print(
            """
The database demonstrations completed successfully.

The script has demonstrated aggregation from basic COUNT, SUM, AVG, MIN,
and MAX operations through grouped analysis, joins, conditional metrics,
NULL behavior, financial calculations, CTEs, window functions, performance,
security, data validation, and testing.
"""
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
