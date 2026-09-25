"""
Analytical Windows: LAG, LEAD, FIRST_VALUE, LAST_VALUE
========================================================

A self-contained study file using Python's standard-library sqlite3 module.

The examples use SQLite window functions to demonstrate:

    - Window functions and OVER()
    - PARTITION BY
    - ORDER BY
    - Window frames
    - LAG()
    - LEAD()
    - FIRST_VALUE()
    - LAST_VALUE()
    - Relative-row analysis
    - Previous/next period comparisons
    - First/last values within partitions
    - Running and bounded windows
    - NULL handling
    - Duplicate ordering and deterministic ordering
    - Common LAST_VALUE() frame mistakes
    - Performance considerations
    - Practical analytical patterns
    - Validation and testing

Requirements:
    Python 3.9+
    No third-party packages.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable, Sequence


# ---------------------------------------------------------------------------
# 1. CONNECTION AND SAMPLE DATA
# ---------------------------------------------------------------------------

def create_connection() -> sqlite3.Connection:
    """Create an in-memory SQLite database with useful row access."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the sales table used throughout the demonstrations."""
    connection.executescript(
        """
        CREATE TABLE sales (
            sale_id       INTEGER PRIMARY KEY,
            customer_id   INTEGER NOT NULL,
            region        TEXT NOT NULL,
            sale_date     TEXT NOT NULL,
            product       TEXT NOT NULL,
            quantity      INTEGER NOT NULL CHECK (quantity > 0),
            unit_price    REAL NOT NULL CHECK (unit_price >= 0),
            revenue       REAL GENERATED ALWAYS AS
                          (quantity * unit_price) STORED
        );

        CREATE INDEX idx_sales_customer_date
            ON sales(customer_id, sale_date, sale_id);

        CREATE INDEX idx_sales_region_date
            ON sales(region, sale_date, sale_id);
        """
    )


def populate_data(connection: sqlite3.Connection) -> None:
    """Insert a deterministic dataset with several analytical edge cases."""
    rows = [
        (1, 101, "North", "2026-01-05", "Laptop", 1, 1200.00),
        (2, 101, "North", "2026-01-20", "Mouse", 2, 25.00),
        (3, 101, "North", "2026-02-03", "Monitor", 1, 350.00),
        (4, 101, "North", "2026-02-20", "Keyboard", 1, 80.00),
        (5, 101, "North", "2026-03-10", "Laptop", 1, 1250.00),

        (6, 102, "South", "2026-01-07", "Phone", 1, 800.00),
        (7, 102, "South", "2026-01-25", "Case", 2, 30.00),
        (8, 102, "South", "2026-02-11", "Phone", 1, 820.00),
        (9, 102, "South", "2026-03-05", "Earbuds", 1, 150.00),

        (10, 103, "North", "2026-01-15", "Tablet", 1, 500.00),
        (11, 103, "North", "2026-02-15", "Tablet", 1, 500.00),
        (12, 103, "North", "2026-03-15", "Stylus", 1, 60.00),

        (13, 104, "West", "2026-01-03", "Camera", 1, 1000.00),
        (14, 104, "West", "2026-01-03", "Tripod", 1, 120.00),
        (15, 104, "West", "2026-02-01", "Lens", 1, 700.00),
        (16, 104, "West", "2026-03-01", "Camera", 1, 1100.00),

        (17, 105, "East", "2026-02-01", "Chair", 1, 250.00),
        (18, 105, "East", "2026-03-01", "Desk", 1, 450.00),
    ]

    connection.executemany(
        """
        INSERT INTO sales
            (sale_id, customer_id, region, sale_date, product, quantity, unit_price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.commit()


# ---------------------------------------------------------------------------
# 2. OUTPUT HELPERS
# ---------------------------------------------------------------------------

def print_title(title: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def print_rows(rows: Iterable[sqlite3.Row]) -> None:
    rows = list(rows)

    if not rows:
        print("(no rows)")
        return

    columns = rows[0].keys()
    widths = {}

    for column in columns:
        widths[column] = max(
            len(column),
            max(len(str(row[column])) for row in rows),
        )

    header = " | ".join(
        str(column).ljust(widths[column]) for column in columns
    )
    separator = "-+-".join("-" * widths[column] for column in columns)

    print(header)
    print(separator)

    for row in rows:
        print(
            " | ".join(
                str(row[column]).ljust(widths[column])
                for column in columns
            )
        )


def execute_and_print(
    connection: sqlite3.Connection,
    sql: str,
    parameters: Sequence = (),
) -> list[sqlite3.Row]:
    rows = connection.execute(sql, parameters).fetchall()
    print_rows(rows)
    return rows


# ---------------------------------------------------------------------------
# 3. FUNDAMENTALS: WHAT A WINDOW FUNCTION DOES
# ---------------------------------------------------------------------------

def demonstrate_basic_window_function(connection: sqlite3.Connection) -> None:
    print_title("1. Basic Window Function: ROW NUMBER BY CUSTOMER")

    sql = """
        SELECT
            sale_id,
            customer_id,
            sale_date,
            product,
            revenue,
            ROW_NUMBER() OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS customer_sale_number
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 4. LAG()
# ---------------------------------------------------------------------------

def demonstrate_lag(connection: sqlite3.Connection) -> None:
    print_title("2. LAG(): Access the Previous Row")

    sql = """
        SELECT
            sale_id,
            customer_id,
            sale_date,
            product,
            revenue,
            LAG(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS previous_revenue
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


def demonstrate_lag_difference(connection: sqlite3.Connection) -> None:
    print_title("3. LAG(): Revenue Difference From Previous Sale")

    sql = """
        SELECT
            sale_id,
            customer_id,
            sale_date,
            revenue,
            LAG(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS previous_revenue,
            revenue -
            LAG(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS revenue_change
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


def demonstrate_lag_offset(connection: sqlite3.Connection) -> None:
    print_title("4. LAG(): Offset and Default Value")

    sql = """
        SELECT
            sale_id,
            customer_id,
            sale_date,
            revenue,
            LAG(revenue, 2, 0) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS revenue_two_sales_ago
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 5. LEAD()
# ---------------------------------------------------------------------------

def demonstrate_lead(connection: sqlite3.Connection) -> None:
    print_title("5. LEAD(): Access the Following Row")

    sql = """
        SELECT
            sale_id,
            customer_id,
            sale_date,
            product,
            revenue,
            LEAD(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS next_revenue
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


def demonstrate_lead_difference(connection: sqlite3.Connection) -> None:
    print_title("6. LEAD(): Compare Current Revenue With Next Revenue")

    sql = """
        SELECT
            sale_id,
            customer_id,
            sale_date,
            revenue,
            LEAD(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS next_revenue,
            LEAD(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) - revenue AS change_to_next_sale
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 6. FIRST_VALUE()
# ---------------------------------------------------------------------------

def demonstrate_first_value(connection: sqlite3.Connection) -> None:
    print_title("7. FIRST_VALUE(): First Value in the Window")

    sql = """
        SELECT
            sale_id,
            customer_id,
            sale_date,
            product,
            revenue,
            FIRST_VALUE(product) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS first_product,
            FIRST_VALUE(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS first_revenue
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


def demonstrate_first_value_region(connection: sqlite3.Connection) -> None:
    print_title("8. FIRST_VALUE(): First Sale in Each Region")

    sql = """
        SELECT
            sale_id,
            region,
            customer_id,
            sale_date,
            product,
            FIRST_VALUE(product) OVER (
                PARTITION BY region
                ORDER BY sale_date, sale_id
            ) AS first_region_product
        FROM sales
        ORDER BY region, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 7. LAST_VALUE() AND THE FRAME PROBLEM
# ---------------------------------------------------------------------------

def demonstrate_last_value_common_mistake(
    connection: sqlite3.Connection,
) -> None:
    print_title("9. LAST_VALUE(): The Important Window-Frame Trap")

    print(
        "\nA frequent mistake is assuming LAST_VALUE() automatically means "
        "the last row of the entire partition."
    )

    sql = """
        SELECT
            sale_id,
            customer_id,
            sale_date,
            revenue,
            LAST_VALUE(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS apparent_last_value
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)

    print(
        "\nWith the default frame, the last row of the frame is often the "
        "current row, so the result can equal the current revenue."
    )


def demonstrate_last_value_correct(
    connection: sqlite3.Connection,
) -> None:
    print_title("10. LAST_VALUE(): Correct Full-Partition Frame")

    sql = """
        SELECT
            sale_id,
            customer_id,
            sale_date,
            revenue,
            LAST_VALUE(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS actual_last_revenue
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


def demonstrate_first_and_last_together(
    connection: sqlite3.Connection,
) -> None:
    print_title("11. FIRST_VALUE() and LAST_VALUE() Together")

    sql = """
        SELECT
            sale_id,
            customer_id,
            sale_date,
            revenue,
            FIRST_VALUE(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS first_revenue,

            LAST_VALUE(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS last_revenue
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 8. CUSTOMER JOURNEY ANALYSIS
# ---------------------------------------------------------------------------

def demonstrate_customer_journey(
    connection: sqlite3.Connection,
) -> None:
    print_title("12. Customer Journey: Previous, Current, Next")

    sql = """
        SELECT
            customer_id,
            sale_date,
            product,
            revenue,

            LAG(product) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS previous_product,

            LEAD(product) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS next_product,

            revenue -
            LAG(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS change_from_previous,

            LEAD(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) - revenue AS change_to_next
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 9. FIRST/LAST PURCHASE ANALYSIS
# ---------------------------------------------------------------------------

def demonstrate_customer_lifecycle(
    connection: sqlite3.Connection,
) -> None:
    print_title("13. Customer Lifecycle Analysis")

    sql = """
        SELECT
            customer_id,
            sale_date,
            product,
            revenue,

            FIRST_VALUE(sale_date) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS first_purchase_date,

            LAST_VALUE(sale_date) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS last_purchase_date
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 10. SALES CHANGE CLASSIFICATION
# ---------------------------------------------------------------------------

def demonstrate_change_classification(
    connection: sqlite3.Connection,
) -> None:
    print_title("14. Classifying Revenue Movement")

    sql = """
        WITH comparisons AS (
            SELECT
                sale_id,
                customer_id,
                sale_date,
                revenue,
                LAG(revenue) OVER (
                    PARTITION BY customer_id
                    ORDER BY sale_date, sale_id
                ) AS previous_revenue
            FROM sales
        )
        SELECT
            sale_id,
            customer_id,
            sale_date,
            revenue,
            previous_revenue,
            CASE
                WHEN previous_revenue IS NULL THEN 'FIRST SALE'
                WHEN revenue > previous_revenue THEN 'INCREASE'
                WHEN revenue < previous_revenue THEN 'DECREASE'
                ELSE 'UNCHANGED'
            END AS movement
        FROM comparisons
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 11. PERCENTAGE CHANGE
# ---------------------------------------------------------------------------

def demonstrate_percentage_change(
    connection: sqlite3.Connection,
) -> None:
    print_title("15. Percentage Change From Previous Sale")

    sql = """
        WITH comparisons AS (
            SELECT
                sale_id,
                customer_id,
                sale_date,
                revenue,
                LAG(revenue) OVER (
                    PARTITION BY customer_id
                    ORDER BY sale_date, sale_id
                ) AS previous_revenue
            FROM sales
        )
        SELECT
            sale_id,
            customer_id,
            sale_date,
            revenue,
            previous_revenue,
            CASE
                WHEN previous_revenue IS NULL
                     OR previous_revenue = 0
                THEN NULL
                ELSE ROUND(
                    (revenue - previous_revenue)
                    * 100.0
                    / previous_revenue,
                    2
                )
            END AS percentage_change
        FROM comparisons
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 12. ADVANCED: WINDOW FRAME
# ---------------------------------------------------------------------------

def demonstrate_bounded_frame(
    connection: sqlite3.Connection,
) -> None:
    print_title("16. Bounded Window Frame")

    sql = """
        SELECT
            customer_id,
            sale_date,
            revenue,

            AVG(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING
            ) AS centered_three_row_average
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


def demonstrate_running_total(
    connection: sqlite3.Connection,
) -> None:
    print_title("17. Running Total")

    sql = """
        SELECT
            customer_id,
            sale_date,
            revenue,
            SUM(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cumulative_revenue
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 13. FIRST/LAST AND DETERMINISTIC ORDERING
# ---------------------------------------------------------------------------

def demonstrate_tie_breaking(
    connection: sqlite3.Connection,
) -> None:
    print_title("18. Deterministic Ordering With Duplicate Dates")

    print(
        "\nCustomer 104 has two sales on 2026-01-03. "
        "sale_id is used as a tie-breaker."
    )

    sql = """
        SELECT
            sale_id,
            customer_id,
            sale_date,
            product,
            LAG(product) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS previous_product
        FROM sales
        WHERE customer_id = 104
        ORDER BY sale_date, sale_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 14. NULL BEHAVIOR
# ---------------------------------------------------------------------------

def demonstrate_null_behavior(
    connection: sqlite3.Connection,
) -> None:
    print_title("19. NULL Behavior")

    print(
        "\nLAG() returns NULL when the requested previous row does not exist. "
        "LEAD() behaves similarly at the end of a partition."
    )

    sql = """
        SELECT
            customer_id,
            sale_date,
            revenue,
            LAG(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS previous_revenue,
            LEAD(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS next_revenue
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 15. PRACTICAL KPI: RETENTION-LIKE ACTIVITY GAP
# ---------------------------------------------------------------------------

def demonstrate_activity_gap(
    connection: sqlite3.Connection,
) -> None:
    print_title("20. Activity Gap Between Customer Transactions")

    sql = """
        WITH ordered_sales AS (
            SELECT
                customer_id,
                sale_date,
                LAG(sale_date) OVER (
                    PARTITION BY customer_id
                    ORDER BY sale_date, sale_id
                ) AS previous_sale_date
            FROM sales
        )
        SELECT
            customer_id,
            sale_date,
            previous_sale_date,
            CASE
                WHEN previous_sale_date IS NULL THEN NULL
                ELSE CAST(
                    julianday(sale_date)
                    - julianday(previous_sale_date)
                    AS INTEGER
                )
            END AS days_since_previous_sale
        FROM ordered_sales
        ORDER BY customer_id, sale_date;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 16. PRACTICAL KPI: FIRST AND LAST REVENUE
# ---------------------------------------------------------------------------

def demonstrate_lifecycle_value(
    connection: sqlite3.Connection,
) -> None:
    print_title("21. First vs Last Revenue")

    sql = """
        SELECT DISTINCT
            customer_id,

            FIRST_VALUE(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS first_revenue,

            LAST_VALUE(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS last_revenue,

            LAST_VALUE(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
            -
            FIRST_VALUE(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS first_to_last_change

        FROM sales
        ORDER BY customer_id;
    """

    execute_and_print(connection, sql)


# ---------------------------------------------------------------------------
# 17. COMPARISON WITH SELF-JOIN
# ---------------------------------------------------------------------------

def demonstrate_window_vs_self_join(
    connection: sqlite3.Connection,
) -> None:
    print_title("22. Window Function vs Self-Join Concept")

    print(
        "\nThe window-function version is compact and directly expresses "
        "relative-row intent."
    )

    window_sql = """
        SELECT
            customer_id,
            sale_date,
            revenue,
            LAG(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS previous_revenue
        FROM sales
        ORDER BY customer_id, sale_date, sale_id;
    """

    execute_and_print(connection, window_sql)


# ---------------------------------------------------------------------------
# 18. VALIDATION
# ---------------------------------------------------------------------------

def validate_core_behavior(connection: sqlite3.Connection) -> None:
    print_title("23. Automated Validation")

    first_customer_rows = connection.execute(
        """
        SELECT
            sale_id,
            LAG(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS previous_revenue,
            LEAD(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
            ) AS next_revenue
        FROM sales
        WHERE customer_id = 101
        ORDER BY sale_date, sale_id;
        """
    ).fetchall()

    assert first_customer_rows[0]["previous_revenue"] is None
    assert first_customer_rows[-1]["next_revenue"] is None
    assert first_customer_rows[1]["previous_revenue"] == 1200.0
    assert first_customer_rows[0]["next_revenue"] == 50.0

    lifecycle = connection.execute(
        """
        SELECT DISTINCT
            customer_id,
            FIRST_VALUE(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS first_revenue,
            LAST_VALUE(revenue) OVER (
                PARTITION BY customer_id
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS last_revenue
        FROM sales
        WHERE customer_id = 101;
        """
    ).fetchone()

    assert lifecycle["first_revenue"] == 1200.0
    assert lifecycle["last_revenue"] == 1250.0

    print("All assertions passed.")


# ---------------------------------------------------------------------------
# 19. SQL ANALYSIS GUIDELINES
# ---------------------------------------------------------------------------

def print_guidelines() -> None:
    print_title("24. Practical Rules")

    rules = [
        "LAG(value) reads a value from an earlier row in the window.",
        "LEAD(value) reads a value from a later row in the window.",
        "FIRST_VALUE(value) returns the first value according to window ordering.",
        "LAST_VALUE(value) is highly sensitive to the window frame.",
        "PARTITION BY creates independent analytical groups.",
        "ORDER BY defines the sequence used by relative-row functions.",
        "Use a deterministic tie-breaker when ordering values can be equal.",
        "The first LAG row and final LEAD row normally produce NULL.",
        "Use an explicit full frame when LAST_VALUE must mean the final partition value.",
        "Window functions preserve row detail; GROUP BY normally collapses rows.",
        "Indexes can reduce sorting and partition-ordering costs.",
        "Do not calculate a percentage change without protecting against NULL and zero denominators.",
    ]

    for number, rule in enumerate(rules, start=1):
        print(f"{number:2}. {rule}")


# ---------------------------------------------------------------------------
# 20. MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    connection = create_connection()

    try:
        create_schema(connection)
        populate_data(connection)

        demonstrate_basic_window_function(connection)
        demonstrate_lag(connection)
        demonstrate_lag_difference(connection)
        demonstrate_lag_offset(connection)
        demonstrate_lead(connection)
        demonstrate_lead_difference(connection)
        demonstrate_first_value(connection)
        demonstrate_first_value_region(connection)
        demonstrate_last_value_common_mistake(connection)
        demonstrate_last_value_correct(connection)
        demonstrate_first_and_last_together(connection)
        demonstrate_customer_journey(connection)
        demonstrate_customer_lifecycle(connection)
        demonstrate_change_classification(connection)
        demonstrate_percentage_change(connection)
        demonstrate_bounded_frame(connection)
        demonstrate_running_total(connection)
        demonstrate_tie_breaking(connection)
        demonstrate_null_behavior(connection)
        demonstrate_activity_gap(connection)
        demonstrate_lifecycle_value(connection)
        demonstrate_window_vs_self_join(connection)
        validate_core_behavior(connection)
        print_guidelines()

        print_title("25. Study File Completed")
        print(
            "The demonstrations covered LAG, LEAD, FIRST_VALUE, LAST_VALUE, "
            "partitions, ordering, frames, edge cases, comparisons, "
            "validation, and practical analytical patterns."
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
