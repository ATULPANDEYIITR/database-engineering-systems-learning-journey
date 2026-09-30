"""
Advanced SQL Project
Analytical SQL System Using Complex Queries

This self-contained demonstration builds a small analytical SQL environment
with Python's standard-library sqlite3 module. It models customers, products,
orders, order items, payments, and customer events, then executes progressively
more advanced analytical SQL:

- joins and aggregations
- conditional aggregation
- CTEs
- recursive CTEs
- window functions
- ranking and segmentation
- cohort analysis
- retention analysis
- rolling metrics
- anomaly detection
- Pareto analysis
- customer lifetime value
- query validation and execution plans

The database is created entirely in memory, so the program requires no
external package or database server.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable


@dataclass(frozen=True)
class QueryResult:
    title: str
    columns: tuple[str, ...]
    rows: list[tuple]


def connect_database() -> sqlite3.Connection:
    """Create an analytical SQLite database with foreign-key enforcement."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    """Create a normalized transactional schema suitable for analytical queries."""
    connection.executescript(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            region TEXT NOT NULL,
            signup_date TEXT NOT NULL,
            segment TEXT NOT NULL
                CHECK (segment IN ('consumer', 'business', 'enterprise'))
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
            list_price REAL NOT NULL CHECK (list_price >= unit_cost)
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK (status IN ('completed', 'cancelled', 'refunded')),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE order_items (
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            unit_price REAL NOT NULL CHECK (unit_price >= 0),
            discount_rate REAL NOT NULL
                CHECK (discount_rate >= 0 AND discount_rate <= 1),
            PRIMARY KEY (order_id, product_id),
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );

        CREATE TABLE payments (
            payment_id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            payment_date TEXT NOT NULL,
            amount REAL NOT NULL CHECK (amount >= 0),
            method TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK (status IN ('captured', 'failed', 'refunded')),
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );

        CREATE TABLE customer_events (
            event_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            event_date TEXT NOT NULL,
            event_type TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE INDEX idx_orders_customer_date
            ON orders(customer_id, order_date);

        CREATE INDEX idx_orders_date_status
            ON orders(order_date, status);

        CREATE INDEX idx_order_items_product
            ON order_items(product_id);

        CREATE INDEX idx_events_customer_date
            ON customer_events(customer_id, event_date);
        """
    )


def insert_seed_data(connection: sqlite3.Connection) -> None:
    """Insert a realistic compact dataset spanning several analytical periods."""
    customers = [
        (1, "Aarav Industries", "North", "2024-01-05", "enterprise"),
        (2, "Bharat Retail", "North", "2024-01-15", "business"),
        (3, "Cedar Labs", "West", "2024-02-03", "enterprise"),
        (4, "Delta Studio", "West", "2024-02-19", "business"),
        (5, "Epsilon Works", "South", "2024-03-01", "consumer"),
        (6, "Falcon Systems", "South", "2024-03-12", "enterprise"),
        (7, "Ganga Foods", "East", "2024-04-08", "business"),
        (8, "Horizon Media", "East", "2024-04-21", "consumer"),
        (9, "Indus Analytics", "North", "2024-05-04", "business"),
        (10, "Jade Health", "West", "2024-05-18", "enterprise"),
        (11, "Kaveri Design", "South", "2024-06-10", "consumer"),
        (12, "Lotus Commerce", "East", "2024-06-25", "business"),
    ]

    products = [
        (1, "Data Platform", "Software", 180.0, 500.0),
        (2, "Security Suite", "Security", 120.0, 360.0),
        (3, "Analytics Pro", "Analytics", 90.0, 280.0),
        (4, "Cloud Storage", "Infrastructure", 40.0, 140.0),
        (5, "API Gateway", "Infrastructure", 65.0, 190.0),
        (6, "Support Plan", "Services", 35.0, 120.0),
    ]

    connection.executemany(
        """
        INSERT INTO customers
            (customer_id, customer_name, region, signup_date, segment)
        VALUES (?, ?, ?, ?, ?)
        """,
        customers,
    )

    connection.executemany(
        """
        INSERT INTO products
            (product_id, product_name, category, unit_cost, list_price)
        VALUES (?, ?, ?, ?, ?)
        """,
        products,
    )

    orders = [
        (101, 1, "2024-01-20", "completed"),
        (102, 1, "2024-02-20", "completed"),
        (103, 1, "2024-04-10", "completed"),
        (104, 2, "2024-02-02", "completed"),
        (105, 2, "2024-03-14", "completed"),
        (106, 2, "2024-05-17", "completed"),
        (107, 3, "2024-02-20", "completed"),
        (108, 3, "2024-03-22", "completed"),
        (109, 3, "2024-06-05", "completed"),
        (110, 4, "2024-03-01", "completed"),
        (111, 4, "2024-03-18", "refunded"),
        (112, 4, "2024-05-02", "completed"),
        (113, 5, "2024-03-20", "completed"),
        (114, 5, "2024-04-21", "completed"),
        (115, 6, "2024-03-25", "completed"),
        (116, 6, "2024-04-30", "completed"),
        (117, 6, "2024-06-30", "completed"),
        (118, 7, "2024-04-15", "completed"),
        (119, 7, "2024-05-20", "completed"),
        (120, 8, "2024-05-01", "completed"),
        (121, 9, "2024-05-10", "completed"),
        (122, 9, "2024-06-15", "completed"),
        (123, 10, "2024-05-28", "completed"),
        (124, 10, "2024-06-25", "completed"),
        (125, 11, "2024-06-20", "completed"),
        (126, 12, "2024-06-29", "completed"),
        (127, 1, "2024-05-15", "cancelled"),
        (128, 2, "2024-06-18", "completed"),
        (129, 3, "2024-05-15", "completed"),
        (130, 6, "2024-05-15", "completed"),
    ]

    connection.executemany(
        """
        INSERT INTO orders
            (order_id, customer_id, order_date, status)
        VALUES (?, ?, ?, ?)
        """,
        orders,
    )

    item_patterns = {
        101: [(1, 2, 480.0, 0.04), (6, 2, 110.0, 0.00)],
        102: [(3, 3, 260.0, 0.05)],
        103: [(2, 2, 340.0, 0.02), (4, 5, 130.0, 0.00)],
        104: [(3, 2, 270.0, 0.00)],
        105: [(5, 3, 180.0, 0.05), (6, 1, 115.0, 0.00)],
        106: [(1, 1, 490.0, 0.00)],
        107: [(1, 4, 450.0, 0.10), (3, 2, 270.0, 0.00)],
        108: [(2, 3, 350.0, 0.03)],
        109: [(3, 5, 250.0, 0.08)],
        110: [(4, 4, 135.0, 0.00)],
        111: [(5, 2, 185.0, 0.00)],
        112: [(6, 5, 110.0, 0.05)],
        113: [(4, 2, 140.0, 0.00)],
        114: [(3, 2, 275.0, 0.00)],
        115: [(1, 2, 490.0, 0.00)],
        116: [(2, 2, 350.0, 0.00), (6, 2, 115.0, 0.00)],
        117: [(1, 1, 500.0, 0.00)],
        118: [(5, 4, 180.0, 0.05)],
        119: [(6, 3, 120.0, 0.00), (4, 3, 135.0, 0.00)],
        120: [(3, 2, 280.0, 0.00)],
        121: [(2, 3, 355.0, 0.02)],
        122: [(5, 2, 190.0, 0.00)],
        123: [(1, 3, 470.0, 0.04)],
        124: [(2, 2, 360.0, 0.00)],
        125: [(4, 5, 125.0, 0.00)],
        126: [(6, 2, 115.0, 0.00)],
        127: [(1, 1, 500.0, 0.00)],
        128: [(3, 4, 260.0, 0.07)],
        129: [(2, 1, 350.0, 0.00)],
        130: [(1, 1, 500.0, 0.00), (5, 2, 185.0, 0.00)],
    }

    items = []
    for order_id, rows in item_patterns.items():
        for product_id, quantity, unit_price, discount_rate in rows:
            items.append(
                (order_id, product_id, quantity, unit_price, discount_rate)
            )

    connection.executemany(
        """
        INSERT INTO order_items
            (order_id, product_id, quantity, unit_price, discount_rate)
        VALUES (?, ?, ?, ?, ?)
        """,
        items,
    )

    payments = []
    payment_id = 1
    methods = ["card", "bank_transfer", "upi", "card", "bank_transfer"]

    for order_id, customer_id, order_date, status in orders:
        if status == "cancelled":
            payments.append(
                (
                    payment_id,
                    order_id,
                    order_date,
                    0.0,
                    methods[payment_id % len(methods)],
                    "failed",
                )
            )
            payment_id += 1
            continue

        amount = connection.execute(
            """
            SELECT COALESCE(
                SUM(quantity * unit_price * (1.0 - discount_rate)),
                0
            )
            FROM order_items
            WHERE order_id = ?
            """,
            (order_id,),
        ).fetchone()[0]

        payment_status = "refunded" if status == "refunded" else "captured"
        payments.append(
            (
                payment_id,
                order_id,
                order_date,
                round(amount, 2),
                methods[payment_id % len(methods)],
                payment_status,
            )
        )
        payment_id += 1

    connection.executemany(
        """
        INSERT INTO payments
            (payment_id, order_id, payment_date, amount, method, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        payments,
    )

    event_rows = []
    event_id = 1
    for customer_id, _, signup_date, _ in customers:
        signup = date.fromisoformat(signup_date)
        event_rows.append((event_id, customer_id, signup_date, "signup"))
        event_id += 1

        for offset, event_type in (
            (3, "activation"),
            (15, "product_view"),
            (28, "product_view"),
            (45, "support_contact"),
        ):
            event_date = signup + timedelta(days=offset)
            event_rows.append(
                (event_id, customer_id, event_date.isoformat(), event_type)
            )
            event_id += 1

    connection.executemany(
        """
        INSERT INTO customer_events
            (event_id, customer_id, event_date, event_type)
        VALUES (?, ?, ?, ?)
        """,
        event_rows,
    )


def execute_query(
    connection: sqlite3.Connection,
    title: str,
    sql: str,
    parameters: tuple = (),
) -> QueryResult:
    """Execute one analytical query and convert rows into printable values."""
    try:
        cursor = connection.execute(sql, parameters)
        rows = [tuple(row) for row in cursor.fetchall()]
        columns = tuple(column[0] for column in cursor.description or [])
        return QueryResult(title, columns, rows)
    except sqlite3.Error as exc:
        raise RuntimeError(f"Analytical query failed: {exc}") from exc


def print_result(result: QueryResult, max_rows: int = 12) -> None:
    """Render a compact result table without requiring third-party packages."""
    print(f"\n=== {result.title} ===")

    if not result.columns:
        print("(query returned no columns)")
        return

    visible_rows = result.rows[:max_rows]
    widths = [len(column) for column in result.columns]

    formatted_rows = []
    for row in visible_rows:
        formatted = []
        for value in row:
            if isinstance(value, float):
                text = f"{value:.2f}"
            else:
                text = str(value)
            formatted.append(text)
        formatted_rows.append(formatted)

    for row in formatted_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    header = " | ".join(
        column.ljust(widths[index])
        for index, column in enumerate(result.columns)
    )
    print(header)
    print("-+-".join("-" * width for width in widths))

    for row in formatted_rows:
        print(
            " | ".join(
                value.ljust(widths[index])
                for index, value in enumerate(row)
            )
        )

    if len(result.rows) > max_rows:
        print(f"... {len(result.rows) - max_rows} additional rows omitted")


def run_foundational_analytics(connection: sqlite3.Connection) -> None:
    """Demonstrate joins, aggregation, grouping, and conditional metrics."""
    queries = [
        (
            "Revenue by month",
            """
            SELECT
                substr(o.order_date, 1, 7) AS month,
                COUNT(DISTINCT o.order_id) AS completed_orders,
                ROUND(SUM(
                    oi.quantity * oi.unit_price * (1.0 - oi.discount_rate)
                ), 2) AS revenue
            FROM orders AS o
            JOIN order_items AS oi
                ON oi.order_id = o.order_id
            WHERE o.status = 'completed'
            GROUP BY substr(o.order_date, 1, 7)
            ORDER BY month
            """,
        ),
        (
            "Revenue and margin by product category",
            """
            SELECT
                p.category,
                ROUND(SUM(
                    oi.quantity * oi.unit_price * (1.0 - oi.discount_rate)
                ), 2) AS revenue,
                ROUND(SUM(
                    oi.quantity * (
                        oi.unit_price * (1.0 - oi.discount_rate)
                        - p.unit_cost
                    )
                ), 2) AS gross_margin,
                ROUND(
                    100.0 * SUM(
                        oi.quantity * (
                            oi.unit_price * (1.0 - oi.discount_rate)
                            - p.unit_cost
                        )
                    ) / NULLIF(SUM(
                        oi.quantity * oi.unit_price
                        * (1.0 - oi.discount_rate)
                    ), 0),
                    2
                ) AS margin_percent
            FROM orders AS o
            JOIN order_items AS oi
                ON oi.order_id = o.order_id
            JOIN products AS p
                ON p.product_id = oi.product_id
            WHERE o.status = 'completed'
            GROUP BY p.category
            ORDER BY revenue DESC
            """,
        ),
        (
            "Customer order summary",
            """
            SELECT
                c.customer_name,
                c.region,
                COUNT(DISTINCT o.order_id) AS completed_orders,
                ROUND(COALESCE(SUM(
                    CASE
                        WHEN o.status = 'completed'
                        THEN oi.quantity * oi.unit_price
                             * (1.0 - oi.discount_rate)
                        ELSE 0
                    END
                ), 0), 2) AS revenue
            FROM customers AS c
            LEFT JOIN orders AS o
                ON o.customer_id = c.customer_id
            LEFT JOIN order_items AS oi
                ON oi.order_id = o.order_id
            GROUP BY c.customer_id, c.customer_name, c.region
            ORDER BY revenue DESC
            """,
        ),
    ]

    for title, sql in queries:
        print_result(execute_query(connection, title, sql))


def run_cte_analytics(connection: sqlite3.Connection) -> None:
    """Use CTEs to separate metric construction from business interpretation."""
    sql = """
    WITH customer_revenue AS (
        SELECT
            c.customer_id,
            c.customer_name,
            c.segment,
            c.region,
            ROUND(SUM(
                oi.quantity * oi.unit_price * (1.0 - oi.discount_rate)
            ), 2) AS revenue
        FROM customers AS c
        JOIN orders AS o
            ON o.customer_id = c.customer_id
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'completed'
        GROUP BY c.customer_id, c.customer_name, c.segment, c.region
    ),
    segment_stats AS (
        SELECT
            segment,
            COUNT(*) AS active_customers,
            ROUND(AVG(revenue), 2) AS average_revenue,
            ROUND(SUM(revenue), 2) AS segment_revenue
        FROM customer_revenue
        GROUP BY segment
    )
    SELECT
        segment,
        active_customers,
        average_revenue,
        segment_revenue,
        ROUND(
            100.0 * segment_revenue
            / NULLIF(SUM(segment_revenue) OVER (), 0),
            2
        ) AS revenue_share_percent
    FROM segment_stats
    ORDER BY segment_revenue DESC
    """

    print_result(
        execute_query(
            connection,
            "CTE-based customer segment analysis",
            sql,
        )
    )


def run_window_analytics(connection: sqlite3.Connection) -> None:
    """Demonstrate ranking, lag, running totals, and rolling averages."""
    customer_revenue = """
    WITH customer_revenue AS (
        SELECT
            c.customer_id,
            c.customer_name,
            c.region,
            ROUND(SUM(
                oi.quantity * oi.unit_price * (1.0 - oi.discount_rate)
            ), 2) AS revenue
        FROM customers AS c
        JOIN orders AS o
            ON o.customer_id = c.customer_id
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'completed'
        GROUP BY c.customer_id, c.customer_name, c.region
    )
    SELECT
        customer_name,
        region,
        revenue,
        RANK() OVER (
            ORDER BY revenue DESC
        ) AS global_rank,
        DENSE_RANK() OVER (
            PARTITION BY region
            ORDER BY revenue DESC
        ) AS regional_rank,
        ROUND(
            100.0 * revenue / SUM(revenue) OVER (),
            2
        ) AS revenue_share_percent
    FROM customer_revenue
    ORDER BY global_rank
    """

    monthly_revenue = """
    WITH monthly AS (
        SELECT
            substr(o.order_date, 1, 7) AS month,
            ROUND(SUM(
                oi.quantity * oi.unit_price * (1.0 - oi.discount_rate)
            ), 2) AS revenue
        FROM orders AS o
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'completed'
        GROUP BY substr(o.order_date, 1, 7)
    )
    SELECT
        month,
        revenue,
        LAG(revenue) OVER (ORDER BY month) AS previous_month_revenue,
        ROUND(
            100.0 * (
                revenue - LAG(revenue) OVER (ORDER BY month)
            ) / NULLIF(
                LAG(revenue) OVER (ORDER BY month),
                0
            ),
            2
        ) AS month_growth_percent,
        ROUND(
            AVG(revenue) OVER (
                ORDER BY month
                ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
            ),
            2
        ) AS three_month_rolling_average,
        ROUND(
            SUM(revenue) OVER (
                ORDER BY month
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ),
            2
        ) AS cumulative_revenue
    FROM monthly
    ORDER BY month
    """

    print_result(
        execute_query(
            connection,
            "Customer ranking and revenue contribution",
            customer_revenue,
        )
    )

    print_result(
        execute_query(
            connection,
            "Monthly growth, rolling average, and cumulative revenue",
            monthly_revenue,
        )
    )


def run_rfm_segmentation(connection: sqlite3.Connection) -> None:
    """Build an RFM-style customer segmentation model with NTILE."""
    sql = """
    WITH customer_metrics AS (
        SELECT
            c.customer_id,
            c.customer_name,
            MAX(o.order_date) AS last_order_date,
            COUNT(DISTINCT o.order_id) AS frequency,
            ROUND(SUM(
                oi.quantity * oi.unit_price * (1.0 - oi.discount_rate)
            ), 2) AS monetary
        FROM customers AS c
        JOIN orders AS o
            ON o.customer_id = c.customer_id
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'completed'
        GROUP BY c.customer_id, c.customer_name
    ),
    scored AS (
        SELECT
            *,
            NTILE(4) OVER (
                ORDER BY last_order_date ASC
            ) AS recency_score,
            NTILE(4) OVER (
                ORDER BY frequency ASC
            ) AS frequency_score,
            NTILE(4) OVER (
                ORDER BY monetary ASC
            ) AS monetary_score
        FROM customer_metrics
    )
    SELECT
        customer_name,
        last_order_date,
        frequency,
        monetary,
        recency_score,
        frequency_score,
        monetary_score,
        recency_score + frequency_score + monetary_score AS rfm_score,
        CASE
            WHEN recency_score >= 3
                 AND frequency_score >= 3
                 AND monetary_score >= 3
                THEN 'high-value-active'
            WHEN recency_score >= 3
                 AND frequency_score >= 2
                THEN 'active-growth'
            WHEN recency_score <= 2
                 AND monetary_score >= 3
                THEN 'valuable-at-risk'
            ELSE 'standard'
        END AS customer_segment
    FROM scored
    ORDER BY rfm_score DESC, monetary DESC
    """

    print_result(
        execute_query(connection, "RFM customer segmentation", sql)
    )


def run_cohort_retention(connection: sqlite3.Connection) -> None:
    """
    Calculate monthly customer cohorts.

    A cohort is assigned using the customer's first completed order month.
    Retention counts customers whose later completed order occurs in a
    subsequent calendar month.
    """
    sql = """
    WITH first_purchase AS (
        SELECT
            customer_id,
            substr(MIN(order_date), 1, 7) AS cohort_month
        FROM orders
        WHERE status = 'completed'
        GROUP BY customer_id
    ),
    activity AS (
        SELECT DISTINCT
            o.customer_id,
            substr(o.order_date, 1, 7) AS activity_month
        FROM orders AS o
        WHERE o.status = 'completed'
    ),
    cohort_activity AS (
        SELECT
            fp.cohort_month,
            a.activity_month,
            COUNT(DISTINCT a.customer_id) AS active_customers
        FROM first_purchase AS fp
        JOIN activity AS a
            ON a.customer_id = fp.customer_id
        GROUP BY fp.cohort_month, a.activity_month
    ),
    cohort_size AS (
        SELECT
            cohort_month,
            active_customers AS cohort_customers
        FROM cohort_activity
        WHERE activity_month = cohort_month
    )
    SELECT
        ca.cohort_month,
        ca.activity_month,
        ca.active_customers,
        cs.cohort_customers,
        ROUND(
            100.0 * ca.active_customers
            / NULLIF(cs.cohort_customers, 0),
            2
        ) AS retention_percent
    FROM cohort_activity AS ca
    JOIN cohort_size AS cs
        ON cs.cohort_month = ca.cohort_month
    ORDER BY ca.cohort_month, ca.activity_month
    """

    print_result(
        execute_query(connection, "Monthly cohort retention", sql),
        max_rows=30,
    )


def run_pareto_analysis(connection: sqlite3.Connection) -> None:
    """Calculate cumulative revenue contribution for Pareto analysis."""
    sql = """
    WITH product_revenue AS (
        SELECT
            p.product_id,
            p.product_name,
            p.category,
            ROUND(SUM(
                oi.quantity * oi.unit_price * (1.0 - oi.discount_rate)
            ), 2) AS revenue
        FROM products AS p
        JOIN order_items AS oi
            ON oi.product_id = p.product_id
        JOIN orders AS o
            ON o.order_id = oi.order_id
        WHERE o.status = 'completed'
        GROUP BY p.product_id, p.product_name, p.category
    ),
    ranked AS (
        SELECT
            *,
            SUM(revenue) OVER (
                ORDER BY revenue DESC
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cumulative_revenue,
            SUM(revenue) OVER () AS total_revenue
        FROM product_revenue
    )
    SELECT
        product_name,
        category,
        revenue,
        ROUND(
            100.0 * revenue / NULLIF(total_revenue, 0),
            2
        ) AS revenue_share_percent,
        ROUND(
            100.0 * cumulative_revenue / NULLIF(total_revenue, 0),
            2
        ) AS cumulative_share_percent,
        CASE
            WHEN cumulative_revenue <= total_revenue * 0.80
                THEN 'core contribution'
            ELSE 'long tail'
        END AS contribution_group
    FROM ranked
    ORDER BY revenue DESC
    """

    print_result(
        execute_query(connection, "Product Pareto contribution analysis", sql)
    )


def run_anomaly_detection(connection: sqlite3.Connection) -> None:
    """
    Detect unusually large completed orders using mean and standard deviation.

    SQLite does not expose STDDEV as a built-in aggregate, so the query uses
    a mathematically equivalent variance calculation based on SUM and AVG.
    """
    sql = """
    WITH order_values AS (
        SELECT
            o.order_id,
            o.order_date,
            o.customer_id,
            ROUND(SUM(
                oi.quantity * oi.unit_price * (1.0 - oi.discount_rate)
            ), 2) AS order_value
        FROM orders AS o
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'completed'
        GROUP BY o.order_id, o.order_date, o.customer_id
    ),
    statistics AS (
        SELECT
            AVG(order_value) AS average_value,
            AVG(order_value * order_value) AS mean_square
        FROM order_values
    )
    SELECT
        ov.order_id,
        ov.order_date,
        c.customer_name,
        ov.order_value,
        ROUND(s.average_value, 2) AS average_order_value,
        ROUND(
            SQRT(
                MAX(s.mean_square - s.average_value * s.average_value, 0)
            ),
            2
        ) AS population_stddev,
        CASE
            WHEN ov.order_value >
                s.average_value
                + 2.0 * SQRT(
                    MAX(
                        s.mean_square
                        - s.average_value * s.average_value,
                        0
                    )
                )
                THEN 'potential anomaly'
            ELSE 'within expected range'
        END AS classification
    FROM order_values AS ov
    CROSS JOIN statistics AS s
    JOIN customers AS c
        ON c.customer_id = ov.customer_id
    ORDER BY ov.order_value DESC
    """

    print_result(
        execute_query(connection, "Large-order anomaly detection", sql),
        max_rows=20,
    )


def run_customer_lifetime_value(connection: sqlite3.Connection) -> None:
    """
    Estimate observed customer lifetime value.

    This is historical revenue and margin, not a predictive model. Keeping
    observed and predicted values separate prevents the SQL metric from being
    interpreted as a forecast.
    """
    sql = """
    WITH customer_financials AS (
        SELECT
            c.customer_id,
            c.customer_name,
            c.segment,
            COUNT(DISTINCT o.order_id) AS order_count,
            ROUND(SUM(
                oi.quantity * oi.unit_price * (1.0 - oi.discount_rate)
            ), 2) AS revenue,
            ROUND(SUM(
                oi.quantity * (
                    oi.unit_price * (1.0 - oi.discount_rate)
                    - p.unit_cost
                )
            ), 2) AS gross_margin
        FROM customers AS c
        JOIN orders AS o
            ON o.customer_id = c.customer_id
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        JOIN products AS p
            ON p.product_id = oi.product_id
        WHERE o.status = 'completed'
        GROUP BY c.customer_id, c.customer_name, c.segment
    )
    SELECT
        customer_name,
        segment,
        order_count,
        revenue,
        gross_margin,
        ROUND(
            gross_margin / NULLIF(order_count, 0),
            2
        ) AS margin_per_order,
        CASE
            WHEN gross_margin >= 1500 THEN 'high observed value'
            WHEN gross_margin >= 700 THEN 'medium observed value'
            ELSE 'lower observed value'
        END AS value_band
    FROM customer_financials
    ORDER BY gross_margin DESC
    """

    print_result(
        execute_query(connection, "Observed customer lifetime value", sql)
    )


def run_recursive_month_series(connection: sqlite3.Connection) -> None:
    """
    Generate a complete calendar-month series.

    Recursive CTEs are useful when analytical reports must preserve periods
    with zero activity instead of silently dropping them during aggregation.
    """
    sql = """
    WITH RECURSIVE months(month_start) AS (
        SELECT '2024-01-01'
        UNION ALL
        SELECT date(month_start, '+1 month')
        FROM months
        WHERE month_start < '2024-06-01'
    ),
    revenue AS (
        SELECT
            substr(o.order_date, 1, 7) AS month,
            ROUND(SUM(
                oi.quantity * oi.unit_price * (1.0 - oi.discount_rate)
            ), 2) AS revenue
        FROM orders AS o
        JOIN order_items AS oi
            ON oi.order_id = o.order_id
        WHERE o.status = 'completed'
        GROUP BY substr(o.order_date, 1, 7)
    )
    SELECT
        substr(m.month_start, 1, 7) AS month,
        COALESCE(r.revenue, 0) AS revenue
    FROM months AS m
    LEFT JOIN revenue AS r
        ON r.month = substr(m.month_start, 1, 7)
    ORDER BY month
    """

    print_result(
        execute_query(
            connection,
            "Complete month series generated by recursive CTE",
            sql,
        )
    )


def validate_data_quality(connection: sqlite3.Connection) -> None:
    """Run data-quality checks before analytical results are trusted."""
    checks = {
        "orphan order items": """
            SELECT COUNT(*)
            FROM order_items oi
            LEFT JOIN orders o ON o.order_id = oi.order_id
            WHERE o.order_id IS NULL
        """,
        "orphan payments": """
            SELECT COUNT(*)
            FROM payments p
            LEFT JOIN orders o ON o.order_id = p.order_id
            WHERE o.order_id IS NULL
        """,
        "negative effective revenue": """
            SELECT COUNT(*)
            FROM order_items
            WHERE quantity * unit_price * (1.0 - discount_rate) < 0
        """,
        "completed orders without items": """
            SELECT COUNT(*)
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.status = 'completed'
            GROUP BY o.order_id
            HAVING COUNT(oi.product_id) = 0
        """,
    }

    print("\n=== Data quality validation ===")
    for name, sql in checks.items():
        value = connection.execute(sql).fetchone()[0]
        print(f"{name}: {value}")

    invalid_dates = connection.execute(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE date(order_date) IS NULL
        """
    ).fetchone()[0]

    print(f"invalid order dates: {invalid_dates}")


def inspect_query_plan(connection: sqlite3.Connection) -> None:
    """Show the SQLite planner's strategy for an indexed analytical lookup."""
    sql = """
    SELECT
        customer_id,
        order_id,
        order_date
    FROM orders
    WHERE customer_id = 6
      AND order_date >= '2024-04-01'
    ORDER BY order_date
    """

    result = connection.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()

    print("\n=== Query plan inspection ===")
    for row in result:
        print(dict(row))


def demonstrate_transaction_safety(connection: sqlite3.Connection) -> None:
    """
    Demonstrate atomic analytical staging.

    A temporary analytical table can be built inside a transaction and rolled
    back when validation fails, preventing partial derived data from surviving.
    """
    print("\n=== Transaction safety demonstration ===")

    try:
        with connection:
            connection.execute(
                """
                CREATE TEMP TABLE monthly_customer_revenue AS
                SELECT
                    c.customer_id,
                    substr(o.order_date, 1, 7) AS month,
                    ROUND(SUM(
                        oi.quantity * oi.unit_price
                        * (1.0 - oi.discount_rate)
                    ), 2) AS revenue
                FROM customers c
                JOIN orders o ON o.customer_id = c.customer_id
                JOIN order_items oi ON oi.order_id = o.order_id
                WHERE o.status = 'completed'
                GROUP BY c.customer_id, substr(o.order_date, 1, 7)
                """
            )

            staged_rows = connection.execute(
                "SELECT COUNT(*) FROM monthly_customer_revenue"
            ).fetchone()[0]

            if staged_rows == 0:
                raise ValueError("staging validation failed")

            print(f"staged analytical rows: {staged_rows}")

    except (sqlite3.Error, ValueError) as exc:
        print(f"transaction rolled back: {exc}")


def demonstrate_parameterized_filter(connection: sqlite3.Connection) -> None:
    """
    Use a bound parameter instead of string interpolation.

    Parameterization protects analytical filters from SQL injection and also
    makes query reuse easier.
    """
    region = "North"

    sql = """
    SELECT
        c.customer_name,
        COUNT(DISTINCT o.order_id) AS completed_orders,
        ROUND(SUM(
            oi.quantity * oi.unit_price * (1.0 - oi.discount_rate)
        ), 2) AS revenue
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE c.region = ?
      AND o.status = 'completed'
    GROUP BY c.customer_id, c.customer_name
    ORDER BY revenue DESC
    """

    print_result(
        execute_query(
            connection,
            "Parameterized regional revenue filter",
            sql,
            (region,),
        )
    )


def main() -> None:
    connection = connect_database()

    try:
        create_schema(connection)
        insert_seed_data(connection)

        validate_data_quality(connection)
        run_foundational_analytics(connection)
        run_cte_analytics(connection)
        run_window_analytics(connection)
        run_rfm_segmentation(connection)
        run_cohort_retention(connection)
        run_pareto_analysis(connection)
        run_anomaly_detection(connection)
        run_customer_lifetime_value(connection)
        run_recursive_month_series(connection)
        demonstrate_parameterized_filter(connection)
        inspect_query_plan(connection)
        demonstrate_transaction_safety(connection)

    finally:
        connection.close()


if __name__ == "__main__":
    main()
