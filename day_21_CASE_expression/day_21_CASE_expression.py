"""
CASE Expressions in SQL
=======================

A standalone study program covering SQL CASE expressions from beginner to
advanced level. SQLite is used because it is included with Python's standard
library.

The examples progress through:
1. Basic CASE syntax
2. Simple CASE
3. Searched CASE
4. CASE in SELECT
5. CASE in WHERE
6. CASE in ORDER BY
7. CASE in GROUP BY
8. CASE in UPDATE
9. CASE in INSERT
10. NULL handling
11. Data type behavior
12. Nested CASE
13. Conditional aggregation
14. Business rules
15. Risk classification
16. Financial calculations
17. Bucketing and segmentation
18. Custom sorting
19. Validation
20. Advanced reporting
21. Performance considerations
22. Security considerations
23. Testing and debugging

No third-party packages are required.
"""

import sqlite3
from decimal import Decimal
from typing import Iterable


DATABASE_NAME = ":memory:"


def connect_database() -> sqlite3.Connection:
    """Create an in-memory SQLite database with useful row access."""
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def execute_script(connection: sqlite3.Connection, sql: str) -> None:
    """Execute a multi-statement SQL script."""
    connection.executescript(sql)


def print_title(title: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def print_rows(rows: Iterable[sqlite3.Row]) -> None:
    rows = list(rows)

    if not rows:
        print("(no rows)")
        return

    column_names = rows[0].keys()
    print(" | ".join(column_names))
    print("-" * (len(" | ".join(column_names))))

    for row in rows:
        print(" | ".join(str(row[column]) for column in column_names))


def run_query(
    connection: sqlite3.Connection,
    title: str,
    sql: str,
    parameters: tuple = (),
) -> list[sqlite3.Row]:
    """Execute a query and display its result."""
    print_title(title)
    print("SQL:")
    print(sql.strip())
    rows = connection.execute(sql, parameters).fetchall()
    print("\nResult:")
    print_rows(rows)
    return rows


def create_schema(connection: sqlite3.Connection) -> None:
    """
    Create a small sales system.

    CASE expressions become particularly useful when raw database values must
    be transformed into business-friendly categories.
    """
    execute_script(
        connection,
        """
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS employees;

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            country TEXT,
            annual_income REAL,
            credit_score INTEGER,
            customer_status TEXT,
            signup_days_ago INTEGER
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_status TEXT,
            shipping_days INTEGER,
            discount_rate REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY,
            employee_name TEXT NOT NULL,
            department TEXT,
            salary REAL,
            performance_score INTEGER,
            years_experience INTEGER
        );
        """,
    )


def insert_sample_data(connection: sqlite3.Connection) -> None:
    customers = [
        (1, "Aarav", "India", 45000, 610, "active", 120),
        (2, "Meera", "India", 125000, 790, "active", 840),
        (3, "Daniel", "USA", 95000, 720, "active", 310),
        (4, "Sophia", "UK", 38000, 580, "inactive", 1600),
        (5, "Noah", "Canada", None, None, "prospect", 20),
        (6, "Isha", "India", 220000, 830, "active", 1500),
        (7, "Liam", "Australia", 70000, 680, "active", 90),
        (8, "Zara", None, 52000, 640, "active", 400),
    ]

    orders = [
        (101, 1, "2026-01-05", 450.00, "paid", 3, 0.05),
        (102, 1, "2026-02-10", 1200.00, "paid", 5, 0.10),
        (103, 2, "2026-01-20", 8500.00, "paid", 2, 0.15),
        (104, 2, "2026-02-15", 2200.00, "pending", 8, 0.00),
        (105, 3, "2026-02-18", 5000.00, "paid", 4, 0.05),
        (106, 3, "2026-03-02", 18000.00, "paid", 12, 0.20),
        (107, 4, "2026-01-11", 250.00, "cancelled", 0, 0.00),
        (108, 5, "2026-03-05", 900.00, "pending", 15, 0.00),
        (109, 6, "2026-02-21", 30000.00, "paid", 3, 0.25),
        (110, 6, "2026-03-10", 75000.00, "paid", 6, 0.30),
        (111, 7, "2026-02-01", 3200.00, "paid", 7, 0.08),
        (112, 8, "2026-02-28", 1500.00, "paid", 4, 0.05),
        (113, 8, "2026-03-15", 600.00, "refunded", 0, 0.00),
    ]

    employees = [
        (1, "Ananya", "Engineering", 125000, 95, 8),
        (2, "Rohan", "Engineering", 90000, 78, 4),
        (3, "Kabir", "Sales", 72000, 88, 6),
        (4, "Nisha", "Sales", 58000, 69, 2),
        (5, "Vikram", "Finance", 110000, 91, 10),
        (6, "Tara", "HR", 65000, 82, 5),
    ]

    connection.executemany(
        """
        INSERT INTO customers
        (customer_id, customer_name, country, annual_income, credit_score,
         customer_status, signup_days_ago)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        customers,
    )

    connection.executemany(
        """
        INSERT INTO orders
        (order_id, customer_id, order_date, amount, payment_status,
         shipping_days, discount_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        orders,
    )

    connection.executemany(
        """
        INSERT INTO employees
        (employee_id, employee_name, department, salary,
         performance_score, years_experience)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        employees,
    )

    connection.commit()


def basic_case_examples(connection: sqlite3.Connection) -> None:
    """
    CASE has two major forms.

    Simple CASE:
        CASE expression
            WHEN value1 THEN result1
            WHEN value2 THEN result2
            ELSE result
        END

    Searched CASE:
        CASE
            WHEN condition1 THEN result1
            WHEN condition2 THEN result2
            ELSE result
        END

    Searched CASE is usually more flexible because conditions can contain
    comparisons, ranges, AND/OR expressions, NULL checks, and calculations.
    """

    run_query(
        connection,
        "1. Simple CASE: translating a payment status",
        """
        SELECT
            order_id,
            payment_status,
            CASE payment_status
                WHEN 'paid' THEN 'Payment complete'
                WHEN 'pending' THEN 'Awaiting payment'
                WHEN 'cancelled' THEN 'Order cancelled'
                WHEN 'refunded' THEN 'Money returned'
                ELSE 'Unknown status'
            END AS payment_description
        FROM orders
        ORDER BY order_id;
        """,
    )

    run_query(
        connection,
        "2. Searched CASE: classifying order amounts",
        """
        SELECT
            order_id,
            amount,
            CASE
                WHEN amount < 1000 THEN 'Small'
                WHEN amount < 5000 THEN 'Medium'
                WHEN amount < 20000 THEN 'Large'
                ELSE 'Enterprise'
            END AS order_size
        FROM orders
        ORDER BY amount;
        """,
    )

    print(
        """
Important rule:
CASE conditions are evaluated from top to bottom. Once a matching WHEN
condition is found, its THEN expression is selected.

Therefore, overlapping ranges must be ordered carefully. For example,
WHEN amount >= 1000 THEN 'Medium' placed before
WHEN amount >= 5000 THEN 'Large'
would classify 5000 as Medium.
"""
    )


def case_with_nulls(connection: sqlite3.Connection) -> None:
    """Demonstrate SQL's three-valued logic and explicit NULL handling."""

    run_query(
        connection,
        "3. CASE and NULL values",
        """
        SELECT
            customer_id,
            customer_name,
            annual_income,
            CASE
                WHEN annual_income IS NULL THEN 'Income unavailable'
                WHEN annual_income < 50000 THEN 'Low income'
                WHEN annual_income < 100000 THEN 'Middle income'
                ELSE 'High income'
            END AS income_segment
        FROM customers
        ORDER BY customer_id;
        """,
    )

    run_query(
        connection,
        "4. CASE with a missing country",
        """
        SELECT
            customer_name,
            CASE
                WHEN country IS NULL THEN 'Country not supplied'
                ELSE country
            END AS country_display
        FROM customers
        ORDER BY customer_id;
        """,
    )

    print(
        """
NULL is not the same thing as zero or an empty string.

A condition such as:
    annual_income = NULL

does not correctly test for NULL.

Use:
    annual_income IS NULL

or:
    annual_income IS NOT NULL

SQL uses three-valued logic: TRUE, FALSE, and UNKNOWN. A comparison with
NULL normally produces UNKNOWN rather than TRUE.
"""
    )


def business_segmentation(connection: sqlite3.Connection) -> None:
    """Show realistic customer segmentation using multiple business rules."""

    run_query(
        connection,
        "5. Customer value segmentation",
        """
        SELECT
            customer_id,
            customer_name,
            annual_income,
            credit_score,
            CASE
                WHEN annual_income IS NULL OR credit_score IS NULL
                    THEN 'Insufficient data'
                WHEN credit_score >= 750 AND annual_income >= 100000
                    THEN 'Premium'
                WHEN credit_score >= 650 AND annual_income >= 50000
                    THEN 'Standard'
                WHEN credit_score >= 600
                    THEN 'Developing'
                ELSE 'High risk'
            END AS customer_segment
        FROM customers
        ORDER BY customer_id;
        """,
    )

    run_query(
        connection,
        "6. Customer lifecycle classification",
        """
        SELECT
            customer_name,
            customer_status,
            signup_days_ago,
            CASE
                WHEN customer_status = 'prospect' THEN 'Prospect'
                WHEN customer_status = 'inactive' THEN 'Inactive'
                WHEN signup_days_ago <= 90 THEN 'New active'
                WHEN signup_days_ago <= 365 THEN 'Established active'
                ELSE 'Long-term active'
            END AS lifecycle
        FROM customers
        ORDER BY customer_id;
        """,
    )


def conditional_calculations(connection: sqlite3.Connection) -> None:
    """Use CASE to calculate discounts, fees, and business metrics."""

    run_query(
        connection,
        "7. Conditional discount calculation",
        """
        SELECT
            order_id,
            amount,
            discount_rate,
            amount * discount_rate AS discount_amount,
            amount - (amount * discount_rate) AS net_amount
        FROM orders
        ORDER BY order_id;
        """,
    )

    run_query(
        connection,
        "8. Shipping service classification",
        """
        SELECT
            order_id,
            shipping_days,
            CASE
                WHEN payment_status = 'cancelled' THEN 'Not shipped'
                WHEN shipping_days = 0 THEN 'Not shipped'
                WHEN shipping_days <= 3 THEN 'Express'
                WHEN shipping_days <= 7 THEN 'Standard'
                ELSE 'Delayed'
            END AS shipping_category
        FROM orders
        ORDER BY order_id;
        """,
    )

    run_query(
        connection,
        "9. Conditional service fee",
        """
        SELECT
            order_id,
            amount,
            CASE
                WHEN payment_status IN ('cancelled', 'refunded') THEN 0
                WHEN amount >= 50000 THEN amount * 0.005
                WHEN amount >= 10000 THEN amount * 0.01
                ELSE amount * 0.02
            END AS service_fee
        FROM orders
        ORDER BY order_id;
        """,
    )


def case_in_where(connection: sqlite3.Connection) -> None:
    """
    CASE can appear in WHERE, but it is often clearer and more efficient to
    express the underlying predicate directly.

    The first query demonstrates a legitimate use. The second shows a
    predicate-based alternative.
    """

    run_query(
        connection,
        "10. CASE in WHERE",
        """
        SELECT
            order_id,
            amount,
            payment_status
        FROM orders
        WHERE
            CASE
                WHEN payment_status = 'paid' AND amount >= 5000 THEN 1
                ELSE 0
            END = 1
        ORDER BY amount DESC;
        """,
    )

    run_query(
        connection,
        "11. Equivalent direct predicate",
        """
        SELECT
            order_id,
            amount,
            payment_status
        FROM orders
        WHERE payment_status = 'paid'
          AND amount >= 5000
        ORDER BY amount DESC;
        """,
    )

    print(
        """
Performance consideration:
A CASE expression in a filter can make a predicate harder for a database
optimizer to transform into an index-friendly search.

When a direct predicate expresses the same business rule clearly, prefer the
direct predicate in WHERE.

CASE is especially natural in SELECT, ORDER BY, aggregation, and data
transformation.
"""
    )


def case_in_order_by(connection: sqlite3.Connection) -> None:
    """Demonstrate custom business ordering."""

    run_query(
        connection,
        "12. Custom status ordering",
        """
        SELECT
            order_id,
            payment_status,
            amount
        FROM orders
        ORDER BY
            CASE payment_status
                WHEN 'pending' THEN 1
                WHEN 'paid' THEN 2
                WHEN 'refunded' THEN 3
                WHEN 'cancelled' THEN 4
                ELSE 5
            END,
            order_id;
        """,
    )

    run_query(
        connection,
        "13. Priority sorting based on business value",
        """
        SELECT
            order_id,
            amount,
            payment_status
        FROM orders
        ORDER BY
            CASE
                WHEN payment_status = 'pending' AND amount >= 5000 THEN 1
                WHEN payment_status = 'pending' THEN 2
                WHEN payment_status = 'paid' AND amount >= 20000 THEN 3
                ELSE 4
            END,
            amount DESC;
        """,
    )


def conditional_aggregation(connection: sqlite3.Connection) -> None:
    """
    Conditional aggregation is one of the most important practical uses of
    CASE.

    SUM(CASE WHEN condition THEN 1 ELSE 0 END)
    counts rows matching a condition.

    SUM(CASE WHEN condition THEN amount ELSE 0 END)
    totals values only for matching rows.
    """

    run_query(
        connection,
        "14. Count orders by business state",
        """
        SELECT
            COUNT(*) AS total_orders,
            SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END)
                AS paid_orders,
            SUM(CASE WHEN payment_status = 'pending' THEN 1 ELSE 0 END)
                AS pending_orders,
            SUM(CASE WHEN payment_status = 'cancelled' THEN 1 ELSE 0 END)
                AS cancelled_orders,
            SUM(CASE WHEN payment_status = 'refunded' THEN 1 ELSE 0 END)
                AS refunded_orders
        FROM orders;
        """,
    )

    run_query(
        connection,
        "15. Conditional revenue metrics",
        """
        SELECT
            SUM(CASE
                    WHEN payment_status = 'paid'
                    THEN amount
                    ELSE 0
                END) AS paid_revenue,
            SUM(CASE
                    WHEN payment_status = 'pending'
                    THEN amount
                    ELSE 0
                END) AS pending_revenue,
            SUM(CASE
                    WHEN payment_status IN ('cancelled', 'refunded')
                    THEN amount
                    ELSE 0
                END) AS non_active_revenue
        FROM orders;
        """,
    )

    run_query(
        connection,
        "16. Conditional aggregation by customer",
        """
        SELECT
            customer_id,
            SUM(CASE
                    WHEN payment_status = 'paid' THEN amount
                    ELSE 0
                END) AS paid_value,
            SUM(CASE
                    WHEN payment_status = 'pending' THEN amount
                    ELSE 0
                END) AS pending_value,
            COUNT(CASE
                    WHEN payment_status = 'paid' THEN 1
                END) AS paid_order_count
        FROM orders
        GROUP BY customer_id
        ORDER BY paid_value DESC;
        """,
    )


def case_in_group_by(connection: sqlite3.Connection) -> None:
    """Group continuous numeric data into meaningful business buckets."""

    run_query(
        connection,
        "17. Revenue buckets",
        """
        SELECT
            CASE
                WHEN amount < 1000 THEN '0-999'
                WHEN amount < 5000 THEN '1,000-4,999'
                WHEN amount < 20000 THEN '5,000-19,999'
                ELSE '20,000+'
            END AS revenue_bucket,
            COUNT(*) AS order_count,
            SUM(amount) AS total_amount
        FROM orders
        GROUP BY
            CASE
                WHEN amount < 1000 THEN '0-999'
                WHEN amount < 5000 THEN '1,000-4,999'
                WHEN amount < 20000 THEN '5,000-19,999'
                ELSE '20,000+'
            END
        ORDER BY MIN(amount);
        """,
    )

    print(
        """
A CASE expression used for grouping converts raw values into categorical
dimensions. This is common in reporting, dashboards, customer analytics,
credit analysis, and operational monitoring.
"""
    )


def case_in_update(connection: sqlite3.Connection) -> None:
    """Demonstrate CASE in an UPDATE while preserving the original dataset."""

    connection.execute("DROP TABLE IF EXISTS customer_status_demo")
    connection.execute(
        """
        CREATE TABLE customer_status_demo AS
        SELECT * FROM customers
        """
    )

    print_title("18. CASE in UPDATE")
    connection.execute(
        """
        UPDATE customer_status_demo
        SET customer_status =
            CASE
                WHEN customer_status = 'prospect'
                     AND signup_days_ago <= 30
                    THEN 'new_prospect'
                WHEN customer_status = 'inactive'
                    AND signup_days_ago > 365
                    THEN 'dormant'
                ELSE customer_status
            END;
        """
    )
    connection.commit()

    rows = connection.execute(
        """
        SELECT customer_id, customer_name, customer_status
        FROM customer_status_demo
        ORDER BY customer_id;
        """
    ).fetchall()
    print_rows(rows)


def nested_case(connection: sqlite3.Connection) -> None:
    """
    Nested CASE is possible, but excessive nesting can become difficult to
    maintain. When rules become complex, separate rule tables, CTEs, views,
    or application logic may be more appropriate.
    """

    run_query(
        connection,
        "19. Nested CASE for a two-dimensional classification",
        """
        SELECT
            customer_name,
            annual_income,
            credit_score,
            CASE
                WHEN credit_score IS NULL THEN 'Unknown'
                WHEN credit_score >= 700 THEN
                    CASE
                        WHEN annual_income >= 100000 THEN 'High-score/high-income'
                        WHEN annual_income IS NULL THEN 'High-score/income-unknown'
                        ELSE 'High-score/lower-income'
                    END
                ELSE
                    CASE
                        WHEN annual_income >= 100000 THEN 'Lower-score/high-income'
                        ELSE 'Lower-score/other'
                    END
            END AS profile
        FROM customers
        ORDER BY customer_id;
        """,
    )


def advanced_business_report(connection: sqlite3.Connection) -> None:
    """
    A common production pattern is to calculate a business category in a CTE
    and then reuse that transformed data in later queries.
    """

    run_query(
        connection,
        "20. CTE-based customer risk report",
        """
        WITH customer_rules AS (
            SELECT
                customer_id,
                customer_name,
                annual_income,
                credit_score,
                CASE
                    WHEN credit_score IS NULL OR annual_income IS NULL
                        THEN 'UNKNOWN'
                    WHEN credit_score < 600
                        THEN 'HIGH'
                    WHEN credit_score < 700
                        THEN 'MEDIUM'
                    WHEN annual_income >= 150000
                        THEN 'LOW'
                    ELSE 'LOW'
                END AS risk_level
            FROM customers
        ),
        customer_orders AS (
            SELECT
                c.customer_id,
                c.customer_name,
                c.risk_level,
                COALESCE(SUM(o.amount), 0) AS gross_order_value
            FROM customer_rules AS c
            LEFT JOIN orders AS o
                ON o.customer_id = c.customer_id
               AND o.payment_status = 'paid'
            GROUP BY
                c.customer_id,
                c.customer_name,
                c.risk_level
        )
        SELECT
            customer_id,
            customer_name,
            risk_level,
            gross_order_value,
            CASE
                WHEN risk_level = 'HIGH' THEN 'Manual review'
                WHEN risk_level = 'MEDIUM' AND gross_order_value >= 5000
                    THEN 'Enhanced monitoring'
                WHEN risk_level = 'UNKNOWN'
                    THEN 'Collect missing information'
                ELSE 'Standard monitoring'
            END AS recommended_process
        FROM customer_orders
        ORDER BY
            CASE risk_level
                WHEN 'HIGH' THEN 1
                WHEN 'MEDIUM' THEN 2
                WHEN 'UNKNOWN' THEN 3
                ELSE 4
            END,
            gross_order_value DESC;
        """,
    )


def conditional_pivot(connection: sqlite3.Connection) -> None:
    """
    SQL dialects differ in whether they provide a PIVOT operator. CASE plus
    aggregation is portable and can reproduce many pivot-like reports.
    """

    run_query(
        connection,
        "21. CASE-based pivot report",
        """
        SELECT
            customer_id,
            SUM(CASE
                    WHEN payment_status = 'paid'
                    THEN amount ELSE 0
                END) AS paid_amount,
            SUM(CASE
                    WHEN payment_status = 'pending'
                    THEN amount ELSE 0
                END) AS pending_amount,
            SUM(CASE
                    WHEN payment_status = 'refunded'
                    THEN amount ELSE 0
                END) AS refunded_amount,
            SUM(CASE
                    WHEN payment_status = 'cancelled'
                    THEN amount ELSE 0
                END) AS cancelled_amount
        FROM orders
        GROUP BY customer_id
        ORDER BY customer_id;
        """,
    )


def salary_band_report(connection: sqlite3.Connection) -> None:
    """Show CASE used for HR-style salary and performance analysis."""

    run_query(
        connection,
        "22. Employee compensation and performance classification",
        """
        SELECT
            employee_name,
            department,
            salary,
            performance_score,
            CASE
                WHEN performance_score >= 90 THEN 'Exceptional'
                WHEN performance_score >= 80 THEN 'Strong'
                WHEN performance_score >= 70 THEN 'Developing'
                ELSE 'Needs improvement'
            END AS performance_band,
            CASE
                WHEN salary < 60000 THEN 'Entry compensation'
                WHEN salary < 100000 THEN 'Mid compensation'
                ELSE 'Senior compensation'
            END AS compensation_band
        FROM employees
        ORDER BY performance_score DESC;
        """,
    )


def case_with_coalesce(connection: sqlite3.Connection) -> None:
    """
    COALESCE and CASE solve related but different problems.

    COALESCE chooses the first non-NULL expression.
    CASE evaluates explicit conditions.

    They are often combined when missing data has to be normalized before
    applying business rules.
    """

    run_query(
        connection,
        "23. COALESCE combined with CASE",
        """
        SELECT
            customer_name,
            COALESCE(annual_income, 0) AS normalized_income,
            CASE
                WHEN COALESCE(annual_income, 0) = 0
                    THEN 'Income unavailable'
                WHEN annual_income < 50000
                    THEN 'Low'
                WHEN annual_income < 100000
                    THEN 'Medium'
                ELSE 'High'
            END AS income_class
        FROM customers
        ORDER BY customer_id;
        """,
    )


def demonstrate_case_without_else(connection: sqlite3.Connection) -> None:
    """
    If no WHEN condition matches and ELSE is omitted, CASE returns NULL.

    This is sometimes useful, especially inside conditional aggregation, but
    it can also cause unexpected NULL results.
    """

    run_query(
        connection,
        "24. CASE without ELSE",
        """
        SELECT
            order_id,
            payment_status,
            CASE
                WHEN payment_status = 'paid' THEN 'Recognized'
            END AS recognition
        FROM orders
        ORDER BY order_id;
        """,
    )


def demonstrate_short_circuit_concept(connection: sqlite3.Connection) -> None:
    """
    SQL optimizers can transform expressions, so code should not rely on
    procedural short-circuit behavior as if CASE were a general-purpose
    programming-language control-flow statement.

    This example demonstrates the ordinary logical result without relying on
    dangerous expressions.
    """

    run_query(
        connection,
        "25. Ordered rule precedence",
        """
        SELECT
            order_id,
            amount,
            CASE
                WHEN amount >= 1000 THEN 'At least 1,000'
                WHEN amount >= 5000 THEN 'At least 5,000'
                ELSE 'Below 1,000'
            END AS classification
        FROM orders
        ORDER BY amount;
        """,
    )

    print(
        """
The second WHEN condition is unreachable for amounts >= 5000 because the
first condition already matches.

Correct ordering:
    >= 5000 before >= 1000

Incorrect ordering:
    >= 1000 before >= 5000

CASE is rule ordering, not merely a collection of independent tests.
"""
    )


def validate_business_rules(connection: sqlite3.Connection) -> None:
    """
    CASE can also expose data-quality problems.

    Returning a diagnostic category is often better than silently replacing
    invalid data.
    """

    run_query(
        connection,
        "26. Data-quality validation using CASE",
        """
        SELECT
            customer_id,
            customer_name,
            CASE
                WHEN annual_income IS NULL
                     AND credit_score IS NULL
                    THEN 'Missing income and credit score'
                WHEN annual_income IS NULL
                    THEN 'Missing income'
                WHEN credit_score IS NULL
                    THEN 'Missing credit score'
                WHEN annual_income < 0
                    THEN 'Invalid negative income'
                WHEN credit_score < 300 OR credit_score > 850
                    THEN 'Invalid credit score'
                ELSE 'Valid'
            END AS data_quality_status
        FROM customers
        ORDER BY customer_id;
        """,
    )


def explain_execution_plan(connection: sqlite3.Connection) -> None:
    """Show how CASE-related query design can be inspected."""

    print_title("27. Inspecting an execution plan")

    plan = connection.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT
            order_id,
            CASE
                WHEN amount >= 20000 THEN 'Large'
                ELSE 'Regular'
            END AS size
        FROM orders
        WHERE payment_status = 'paid';
        """
    ).fetchall()

    print_rows(plan)

    print(
        """
EXPLAIN QUERY PLAN is database-specific. In production, use the execution
plan facilities of the actual database engine.

CASE itself is usually inexpensive. Performance problems more often arise
from the surrounding joins, filters, sorting, aggregation, table size, data
distribution, and indexes.
"""
    )


def parameterized_case(connection: sqlite3.Connection) -> None:
    """
    Parameterized queries protect values supplied by users.

    SQL structure should not be built by string concatenation when input is
    untrusted.
    """

    minimum_amount = 5000

    run_query(
        connection,
        "28. Parameterized threshold with CASE",
        """
        SELECT
            order_id,
            amount,
            CASE
                WHEN amount >= ? THEN 'Above threshold'
                ELSE 'Below threshold'
            END AS threshold_status
        FROM orders
        ORDER BY order_id;
        """,
        (minimum_amount,),
    )

    print(
        """
The threshold is supplied as a parameter rather than concatenated into SQL.
This helps prevent SQL injection and avoids quoting problems.

Parameterized values can represent data values, not arbitrary SQL syntax.
Table names, column names, and SQL keywords generally require a different
validated design when they must be dynamic.
"""
    )


def compare_case_with_python(connection: sqlite3.Connection) -> None:
    """
    The same business rule can exist in SQL and Python.

    Prefer SQL CASE when the transformation belongs naturally to the database
    query and reduces unnecessary data transfer.

    Prefer application code when the rule is genuinely application-specific,
    requires complex external services, or is easier to maintain outside SQL.
    """

    rows = connection.execute(
        """
        SELECT order_id, amount
        FROM orders
        ORDER BY order_id
        """
    ).fetchall()

    print_title("29. Comparing SQL CASE with Python logic")

    for row in rows:
        amount = row["amount"]

        if amount < 1000:
            category = "Small"
        elif amount < 5000:
            category = "Medium"
        elif amount < 20000:
            category = "Large"
        else:
            category = "Enterprise"

        print(
            f"Order {row['order_id']}: amount={amount:.2f}, "
            f"Python category={category}"
        )

    print(
        """
Equivalent SQL logic can be executed inside the database:

CASE
    WHEN amount < 1000 THEN 'Small'
    WHEN amount < 5000 THEN 'Medium'
    WHEN amount < 20000 THEN 'Large'
    ELSE 'Enterprise'
END

The important design question is not whether SQL or Python can express the
rule. Both can. The question is where the rule should live.
"""
    )


def advanced_window_example(connection: sqlite3.Connection) -> None:
    """
    CASE works with window functions. The CASE classifies each row while the
    window function provides context across rows.

    This is useful for customer-level reporting and conditional metrics.
    """

    run_query(
        connection,
        "30. CASE combined with a window function",
        """
        SELECT
            order_id,
            customer_id,
            amount,
            SUM(amount) OVER (
                PARTITION BY customer_id
            ) AS customer_total,
            CASE
                WHEN amount >= 0.5 * SUM(amount) OVER (
                    PARTITION BY customer_id
                )
                    THEN 'Major order'
                ELSE 'Regular order'
            END AS order_contribution
        FROM orders
        ORDER BY customer_id, amount DESC;
        """,
    )


def test_case_rules(connection: sqlite3.Connection) -> None:
    """Basic automated tests for important classification boundaries."""

    print_title("31. Testing CASE business rules")

    test_sql = """
        SELECT
            CASE
                WHEN ? < 1000 THEN 'Small'
                WHEN ? < 5000 THEN 'Medium'
                WHEN ? < 20000 THEN 'Large'
                ELSE 'Enterprise'
            END AS category;
    """

    test_cases = [
        (0, "Small"),
        (999.99, "Small"),
        (1000, "Medium"),
        (4999.99, "Medium"),
        (5000, "Large"),
        (19999.99, "Large"),
        (20000, "Enterprise"),
    ]

    passed = 0

    for amount, expected in test_cases:
        result = connection.execute(
            test_sql,
            (amount, amount, amount),
        ).fetchone()["category"]

        status = "PASS" if result == expected else "FAIL"

        print(
            f"{status}: amount={amount:<10} "
            f"expected={expected:<12} actual={result}"
        )

        if result == expected:
            passed += 1

    print(f"\nPassed {passed}/{len(test_cases)} boundary tests.")

    assert passed == len(test_cases), "At least one CASE rule test failed."


def discuss_common_mistakes() -> None:
    print_title("32. Common CASE mistakes")

    mistakes = [
        (
            "Forgetting END",
            "Every CASE expression must terminate with END."
        ),
        (
            "Incorrect NULL comparison",
            "Use IS NULL or IS NOT NULL instead of = NULL or <> NULL."
        ),
        (
            "Wrong WHEN order",
            "Overlapping conditions must be ordered from the most specific "
            "or restrictive rule to the broader rule."
        ),
        (
            "Missing ELSE",
            "If no condition matches, omitted ELSE normally produces NULL."
        ),
        (
            "Mixed result types",
            "Returning incompatible types can cause implicit conversion or "
            "database-specific behavior."
        ),
        (
            "Duplicated business rules",
            "The same CASE copied into many queries can become difficult to "
            "maintain and may require a centralized rule design."
        ),
        (
            "Using CASE where WHERE is clearer",
            "A direct predicate can be easier to read and may be more "
            "optimizer-friendly."
        ),
        (
            "Ignoring database dialects",
            "CASE is widely supported, but type conversion, optimizer "
            "behavior, and related functions differ across databases."
        ),
        (
            "Embedding user input in SQL",
            "Use parameters for values rather than string concatenation."
        ),
    ]

    for mistake, explanation in mistakes:
        print(f"- {mistake}: {explanation}")


def discuss_design_tradeoffs() -> None:
    print_title("33. Design trade-offs")

    print(
        """
CASE is appropriate when:

- A query needs a derived category.
- Business rules are simple enough to express declaratively.
- Classification should happen close to the data.
- Conditional aggregation is required.
- A report needs custom ordering.
- A value must be transformed for presentation or analytics.

Consider another design when:

- Hundreds of changing rules are embedded in deeply nested CASE expressions.
- Business users need to modify rules without changing SQL.
- Rules must be shared across many applications and databases.
- The classification requires external API calls or complex application state.
- The CASE expression becomes so large that testing and maintenance become
  difficult.

For large rule systems, a rules table can sometimes replace hard-coded CASE
logic. A query can then join against ranges, codes, effective dates, or
priorities.

The choice depends on ownership of the rule, change frequency, database
architecture, performance requirements, auditability, and testing strategy.
"""
    )


def discuss_security() -> None:
    print_title("34. Security considerations")

    print(
        """
CASE does not itself create a security boundary.

Important practices include:

1. Use parameterized queries for user-supplied values.
2. Do not concatenate untrusted input into SQL.
3. Validate dynamic identifiers when identifiers must be selected at runtime.
4. Avoid exposing sensitive classifications to unauthorized users.
5. Apply authorization rules independently from display classifications.
6. Be careful when CASE reveals information about confidential data.
7. Test NULL and unexpected values so security-sensitive rules do not silently
   fall into an unintended ELSE branch.
8. Audit changes to high-impact business rules such as credit, pricing,
   eligibility, fraud, or access classification.
"""
    )


def discuss_performance() -> None:
    print_title("35. Performance considerations")

    print(
        """
CASE is an expression, not an index by itself.

Potential performance considerations:

- CASE in SELECT usually adds only expression-evaluation work.
- CASE in ORDER BY can require sorting.
- CASE in WHERE can sometimes make a predicate less directly usable by an
  index.
- Repeating a complicated CASE expression many times increases maintenance
  cost and may increase computation.
- Conditional aggregation scans the rows participating in the aggregation.
- Precomputed or indexed derived values may help when the same classification
  is queried repeatedly, depending on the database engine.
- A generated/computed column can sometimes make a frequently used
  transformation easier to index.
- Query plans should be measured on realistic data instead of assuming that
  one SQL pattern is always faster.

For production systems, inspect actual execution plans and measure with
representative workloads.
"""
    )


def main() -> None:
    connection = connect_database()

    try:
        create_schema(connection)
        insert_sample_data(connection)

        basic_case_examples(connection)
        case_with_nulls(connection)
        business_segmentation(connection)
        conditional_calculations(connection)
        case_in_where(connection)
        case_in_order_by(connection)
        conditional_aggregation(connection)
        case_in_group_by(connection)
        case_in_update(connection)
        nested_case(connection)
        advanced_business_report(connection)
        conditional_pivot(connection)
        salary_band_report(connection)
        case_with_coalesce(connection)
        demonstrate_case_without_else(connection)
        demonstrate_short_circuit_concept(connection)
        validate_business_rules(connection)
        explain_execution_plan(connection)
        parameterized_case(connection)
        compare_case_with_python(connection)
        advanced_window_example(connection)
        test_case_rules(connection)
        discuss_common_mistakes()
        discuss_design_tradeoffs()
        discuss_security()
        discuss_performance()

        print_title("CASE expression reference")
        print(
            """
Simple CASE:
CASE expression
    WHEN value1 THEN result1
    WHEN value2 THEN result2
    ELSE result
END

Searched CASE:
CASE
    WHEN condition1 THEN result1
    WHEN condition2 THEN result2
    ELSE result
END

Conditional count:
SUM(CASE WHEN condition THEN 1 ELSE 0 END)

Conditional total:
SUM(CASE WHEN condition THEN amount ELSE 0 END)

Conditional custom ordering:
ORDER BY CASE status
    WHEN 'pending' THEN 1
    WHEN 'paid' THEN 2
    ELSE 3
END

The core idea is simple: CASE converts conditions into values. Its practical
importance comes from using that mechanism to encode controlled business
transformations inside SQL queries.
"""
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
