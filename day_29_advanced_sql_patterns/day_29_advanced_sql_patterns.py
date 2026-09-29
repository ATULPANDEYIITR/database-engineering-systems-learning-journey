"""
Advanced SQL Patterns
=====================

Topic:
    Top-N, gaps-and-islands, deduplication, and pivot-style analysis

This standalone study script uses Python's standard-library sqlite3 module to
execute real SQL against an in-memory relational database.

The examples progress from foundational SQL concepts to advanced analytical
patterns and include:
    - Window functions
    - ROW_NUMBER, RANK, and DENSE_RANK
    - Top-N per group
    - Top-N with ties
    - Running totals
    - LAG and LEAD
    - Gaps-and-islands analysis
    - Consecutive-date streaks
    - Sessionization
    - Duplicate detection
    - Deterministic deduplication
    - Keeping the newest or highest-quality record
    - Pivot-style conditional aggregation
    - Dynamic pivot SQL generation
    - Cohort-style summaries
    - Edge cases
    - Query validation
    - Performance considerations
    - Indexing
    - Transaction-safe deletion
    - Testing

Requirements:
    Python 3.9+
    No third-party packages
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Sequence


# ---------------------------------------------------------------------------
# 1. Database setup
# ---------------------------------------------------------------------------

def connect_database() -> sqlite3.Connection:
    """Create an in-memory SQLite database with useful row access."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def execute_script(connection: sqlite3.Connection, sql: str) -> None:
    """Execute a multi-statement SQL script."""
    connection.executescript(sql)


def print_rows(
    title: str,
    rows: Iterable[sqlite3.Row],
    limit: int | None = None,
) -> None:
    """Print query results in a readable table."""
    rows = list(rows)

    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)

    if not rows:
        print("(no rows)")
        return

    if limit is not None:
        rows = rows[:limit]

    columns = rows[0].keys()
    widths = {
        column: max(
            len(column),
            max(len(str(row[column])) for row in rows),
        )
        for column in columns
    }

    header = " | ".join(column.ljust(widths[column]) for column in columns)
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


def run_query(
    connection: sqlite3.Connection,
    title: str,
    sql: str,
    parameters: Sequence[object] = (),
    limit: int | None = None,
) -> list[sqlite3.Row]:
    """Execute and print a SELECT query."""
    rows = connection.execute(sql, parameters).fetchall()
    print_rows(title, rows, limit)
    return rows


# ---------------------------------------------------------------------------
# 2. Sample relational model
# ---------------------------------------------------------------------------

SCHEMA = """
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS customer_events;
DROP TABLE IF EXISTS employee_records;

CREATE TABLE sales (
    sale_id         INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    salesperson     TEXT NOT NULL,
    region          TEXT NOT NULL,
    product         TEXT NOT NULL,
    sale_date       TEXT NOT NULL,
    amount          REAL NOT NULL CHECK (amount >= 0)
);

CREATE TABLE customer_events (
    event_id        INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    event_date      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    session_gap_min INTEGER NOT NULL DEFAULT 30,
    event_value     REAL NOT NULL DEFAULT 0
);

CREATE TABLE employee_records (
    record_id       INTEGER PRIMARY KEY,
    employee_id     INTEGER NOT NULL,
    employee_name   TEXT NOT NULL,
    email           TEXT NOT NULL,
    department      TEXT NOT NULL,
    salary          REAL NOT NULL,
    updated_at      TEXT NOT NULL
);
"""

SALES_DATA = [
    (1, 101, "Asha", "North", "Laptop", "2026-01-03", 1200.00),
    (2, 101, "Asha", "North", "Phone", "2026-01-04", 800.00),
    (3, 101, "Asha", "North", "Laptop", "2026-01-09", 1500.00),
    (4, 102, "Ravi", "North", "Tablet", "2026-01-05", 600.00),
    (5, 102, "Ravi", "North", "Phone", "2026-01-06", 900.00),
    (6, 102, "Ravi", "North", "Laptop", "2026-01-10", 2100.00),
    (7, 103, "Meera", "South", "Laptop", "2026-01-02", 2200.00),
    (8, 103, "Meera", "South", "Phone", "2026-01-08", 700.00),
    (9, 103, "Meera", "South", "Tablet", "2026-01-11", 500.00),
    (10, 104, "Kabir", "South", "Laptop", "2026-01-02", 1800.00),
    (11, 104, "Kabir", "South", "Phone", "2026-01-07", 1100.00),
    (12, 104, "Kabir", "South", "Tablet", "2026-01-09", 900.00),
    (13, 105, "Nisha", "West", "Laptop", "2026-01-03", 1300.00),
    (14, 105, "Nisha", "West", "Phone", "2026-01-03", 1300.00),
    (15, 105, "Nisha", "West", "Tablet", "2026-01-12", 400.00),
]

EVENT_DATA = [
    (1, 101, "2026-01-01", "login", 30, 0),
    (2, 101, "2026-01-02", "purchase", 30, 120),
    (3, 101, "2026-01-03", "login", 30, 0),
    (4, 101, "2026-01-04", "purchase", 30, 90),
    (5, 101, "2026-01-10", "login", 30, 0),
    (6, 101, "2026-01-11", "purchase", 30, 150),
    (7, 102, "2026-01-02", "login", 30, 0),
    (8, 102, "2026-01-03", "purchase", 30, 80),
    (9, 102, "2026-01-08", "login", 30, 0),
    (10, 102, "2026-01-09", "purchase", 30, 100),
    (11, 102, "2026-01-10", "purchase", 30, 60),
    (12, 103, "2026-01-01", "login", 30, 0),
    (13, 103, "2026-01-15", "purchase", 30, 300),
]

EMPLOYEE_DATA = [
    (1, 501, "Arjun", "arjun@example.com", "Engineering", 90000, "2026-01-01T09:00:00"),
    (2, 501, "Arjun Kumar", "arjun@example.com", "Engineering", 95000, "2026-02-01T09:00:00"),
    (3, 502, "Bhavna", "bhavna@example.com", "Finance", 85000, "2026-01-15T09:00:00"),
    (4, 502, "Bhavna", "bhavna@example.com", "Finance", 88000, "2026-02-15T09:00:00"),
    (5, 503, "Chirag", "chirag@example.com", "Engineering", 78000, "2026-01-10T09:00:00"),
    (6, 504, "Divya", "divya@example.com", "HR", 70000, "2026-01-05T09:00:00"),
    (7, 504, "Divya", "divya@example.com", "HR", 72000, "2026-03-05T09:00:00"),
]


def seed_database(connection: sqlite3.Connection) -> None:
    """Create tables and populate them with deterministic demonstration data."""
    execute_script(connection, SCHEMA)

    connection.executemany(
        """
        INSERT INTO sales
            (sale_id, customer_id, salesperson, region, product, sale_date, amount)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        SALES_DATA,
    )

    connection.executemany(
        """
        INSERT INTO customer_events
            (event_id, customer_id, event_date, event_type,
             session_gap_min, event_value)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        EVENT_DATA,
    )

    connection.executemany(
        """
        INSERT INTO employee_records
            (record_id, employee_id, employee_name, email, department,
             salary, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        EMPLOYEE_DATA,
    )

    connection.commit()


# ---------------------------------------------------------------------------
# 3. SQL foundations needed for advanced patterns
# ---------------------------------------------------------------------------

def demonstrate_foundations(connection: sqlite3.Connection) -> None:
    """Show aggregation and ordering before introducing window functions."""

    run_query(
        connection,
        "Foundation: grouped sales totals",
        """
        SELECT
            region,
            SUM(amount) AS total_sales,
            COUNT(*) AS transaction_count,
            AVG(amount) AS average_sale
        FROM sales
        GROUP BY region
        ORDER BY total_sales DESC
        """,
    )

    run_query(
        connection,
        "Foundation: ordinary global TOP-N",
        """
        SELECT
            sale_id,
            salesperson,
            amount
        FROM sales
        ORDER BY amount DESC, sale_id
        LIMIT 5
        """,
    )

    run_query(
        connection,
        "Foundation: conditional aggregation",
        """
        SELECT
            region,
            SUM(CASE WHEN product = 'Laptop' THEN amount ELSE 0 END)
                AS laptop_sales,
            SUM(CASE WHEN product = 'Phone' THEN amount ELSE 0 END)
                AS phone_sales,
            SUM(CASE WHEN product = 'Tablet' THEN amount ELSE 0 END)
                AS tablet_sales
        FROM sales
        GROUP BY region
        ORDER BY region
        """,
    )


# ---------------------------------------------------------------------------
# 4. Window functions
# ---------------------------------------------------------------------------

def demonstrate_window_functions(connection: sqlite3.Connection) -> None:
    """Demonstrate ranking, previous/next rows, and cumulative calculations."""

    run_query(
        connection,
        "ROW_NUMBER: unique sequential position within each region",
        """
        SELECT
            region,
            salesperson,
            sale_id,
            amount,
            ROW_NUMBER() OVER (
                PARTITION BY region
                ORDER BY amount DESC, sale_id
            ) AS row_number
        FROM sales
        ORDER BY region, row_number
        """,
    )

    run_query(
        connection,
        "RANK: ties share a rank and create gaps",
        """
        SELECT
            salesperson,
            amount,
            RANK() OVER (
                ORDER BY amount DESC
            ) AS rank_position
        FROM sales
        ORDER BY rank_position, sale_id
        """,
    )

    run_query(
        connection,
        "DENSE_RANK: ties share a rank without rank gaps",
        """
        SELECT
            salesperson,
            amount,
            DENSE_RANK() OVER (
                ORDER BY amount DESC
            ) AS dense_rank_position
        FROM sales
        ORDER BY dense_rank_position, amount DESC
        """,
    )

    run_query(
        connection,
        "LAG and LEAD: compare adjacent rows",
        """
        SELECT
            salesperson,
            sale_date,
            amount,
            LAG(amount) OVER (
                PARTITION BY salesperson
                ORDER BY sale_date, sale_id
            ) AS previous_amount,
            LEAD(amount) OVER (
                PARTITION BY salesperson
                ORDER BY sale_date, sale_id
            ) AS next_amount
        FROM sales
        ORDER BY salesperson, sale_date, sale_id
        """,
    )

    run_query(
        connection,
        "Running total: windowed SUM",
        """
        SELECT
            sale_date,
            sale_id,
            amount,
            SUM(amount) OVER (
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS running_sales
        FROM sales
        ORDER BY sale_date, sale_id
        """,
    )


# ---------------------------------------------------------------------------
# 5. Top-N per group
# ---------------------------------------------------------------------------

def top_n_per_group(
    connection: sqlite3.Connection,
    n: int = 2,
) -> list[sqlite3.Row]:
    """
    Return the top N sales per region.

    ROW_NUMBER gives exactly N rows per group when enough rows exist.
    The tie-breaker sale_id makes the result deterministic.
    """
    sql = """
    WITH ranked AS (
        SELECT
            sale_id,
            region,
            salesperson,
            product,
            amount,
            ROW_NUMBER() OVER (
                PARTITION BY region
                ORDER BY amount DESC, sale_id
            ) AS rn
        FROM sales
    )
    SELECT
        sale_id,
        region,
        salesperson,
        product,
        amount,
        rn
    FROM ranked
    WHERE rn <= ?
    ORDER BY region, rn
    """

    return run_query(
        connection,
        f"Top {n} sales per region using ROW_NUMBER",
        sql,
        (n,),
    )


def top_n_with_ties(
    connection: sqlite3.Connection,
    n: int = 2,
) -> list[sqlite3.Row]:
    """
    Return all rows whose rank is within the top N ranks.

    RANK is appropriate when tied rows should all be included.
    """
    sql = """
    WITH ranked AS (
        SELECT
            sale_id,
            region,
            salesperson,
            amount,
            RANK() OVER (
                PARTITION BY region
                ORDER BY amount DESC
            ) AS ranking
        FROM sales
    )
    SELECT
        sale_id,
        region,
        salesperson,
        amount,
        ranking
    FROM ranked
    WHERE ranking <= ?
    ORDER BY region, ranking, sale_id
    """

    return run_query(
        connection,
        f"Top {n} ranks per region including ties",
        sql,
        (n,),
    )


# ---------------------------------------------------------------------------
# 6. Gaps-and-islands
# ---------------------------------------------------------------------------

def demonstrate_gaps_and_islands(connection: sqlite3.Connection) -> None:
    """
    Demonstrate the classic gaps-and-islands technique.

    An "island" is a consecutive run of records.
    A "gap" separates one run from another.

    The key technique is:
        current_value - ROW_NUMBER()

    For consecutive dates, date arithmetic is used instead.
    """

    run_query(
        connection,
        "Date gaps: previous event and day difference",
        """
        SELECT
            customer_id,
            event_date,
            LAG(event_date) OVER (
                PARTITION BY customer_id
                ORDER BY event_date, event_id
            ) AS previous_date,
            CAST(
                JULIANDAY(event_date)
                - JULIANDAY(
                    LAG(event_date) OVER (
                        PARTITION BY customer_id
                        ORDER BY event_date, event_id
                    )
                )
                AS INTEGER
            ) AS days_since_previous
        FROM customer_events
        ORDER BY customer_id, event_date
        """,
    )

    run_query(
        connection,
        "Consecutive daily islands",
        """
        WITH ordered AS (
            SELECT
                customer_id,
                event_date,
                event_id,
                DATE(
                    event_date,
                    '-' || ROW_NUMBER() OVER (
                        PARTITION BY customer_id
                        ORDER BY event_date, event_id
                    ) || ' days'
                ) AS island_key
            FROM customer_events
            GROUP BY customer_id, event_date, event_id
        ),
        islands AS (
            SELECT
                customer_id,
                island_key,
                MIN(event_date) AS start_date,
                MAX(event_date) AS end_date,
                COUNT(*) AS event_count
            FROM ordered
            GROUP BY customer_id, island_key
        )
        SELECT
            customer_id,
            start_date,
            end_date,
            event_count,
            CAST(
                JULIANDAY(end_date) - JULIANDAY(start_date) + 1
                AS INTEGER
            ) AS calendar_days
        FROM islands
        ORDER BY customer_id, start_date
        """,
    )


# ---------------------------------------------------------------------------
# 7. Sessionization: a practical gaps-and-islands variant
# ---------------------------------------------------------------------------

def demonstrate_sessionization(connection: sqlite3.Connection) -> None:
    """
    Create sessions by starting a new island whenever the time gap exceeds
    a threshold.

    This pattern is common in clickstream, product analytics, and monitoring.
    """

    run_query(
        connection,
        "Sessionization: classify new sessions",
        """
        WITH ordered AS (
            SELECT
                event_id,
                customer_id,
                event_date,
                event_type,
                event_value,
                LAG(event_date) OVER (
                    PARTITION BY customer_id
                    ORDER BY event_date, event_id
                ) AS previous_event_date
            FROM customer_events
        ),
        marked AS (
            SELECT
                *,
                CASE
                    WHEN previous_event_date IS NULL THEN 1
                    WHEN CAST(
                        JULIANDAY(event_date)
                        - JULIANDAY(previous_event_date)
                        AS INTEGER
                    ) > 1 THEN 1
                    ELSE 0
                END AS new_session
            FROM ordered
        ),
        numbered AS (
            SELECT
                *,
                SUM(new_session) OVER (
                    PARTITION BY customer_id
                    ORDER BY event_date, event_id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS session_number
            FROM marked
        )
        SELECT
            customer_id,
            session_number,
            MIN(event_date) AS session_start,
            MAX(event_date) AS session_end,
            COUNT(*) AS events,
            SUM(event_value) AS session_value
        FROM numbered
        GROUP BY customer_id, session_number
        ORDER BY customer_id, session_number
        """,
    )


# ---------------------------------------------------------------------------
# 8. Deduplication
# ---------------------------------------------------------------------------

def demonstrate_duplicate_detection(connection: sqlite3.Connection) -> None:
    """Find logical duplicates before deleting anything."""

    run_query(
        connection,
        "Duplicate groups by logical business key",
        """
        SELECT
            email,
            COUNT(*) AS duplicate_count,
            MIN(updated_at) AS first_seen,
            MAX(updated_at) AS last_seen
        FROM employee_records
        GROUP BY email
        HAVING COUNT(*) > 1
        ORDER BY email
        """,
    )

    run_query(
        connection,
        "Duplicate records with ROW_NUMBER",
        """
        SELECT
            record_id,
            employee_id,
            employee_name,
            email,
            department,
            salary,
            updated_at,
            ROW_NUMBER() OVER (
                PARTITION BY email
                ORDER BY updated_at DESC, record_id DESC
            ) AS keep_rank
        FROM employee_records
        ORDER BY email, keep_rank
        """,
    )


def deduplicate_keep_latest(connection: sqlite3.Connection) -> None:
    """
    Remove duplicates while keeping the newest deterministic record.

    The DELETE is wrapped in a transaction and validated before commit.
    """
    before = connection.execute(
        "SELECT COUNT(*) FROM employee_records"
    ).fetchone()[0]

    connection.execute("BEGIN")

    try:
        connection.execute(
            """
            DELETE FROM employee_records
            WHERE record_id IN (
                SELECT record_id
                FROM (
                    SELECT
                        record_id,
                        ROW_NUMBER() OVER (
                            PARTITION BY email
                            ORDER BY updated_at DESC, record_id DESC
                        ) AS rn
                    FROM employee_records
                )
                WHERE rn > 1
            )
            """
        )

        after = connection.execute(
            "SELECT COUNT(*) FROM employee_records"
        ).fetchone()[0]

        if after >= before:
            raise RuntimeError(
                "Deduplication validation failed: row count did not decrease."
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    run_query(
        connection,
        "Employee records after keeping newest row per email",
        """
        SELECT
            record_id,
            employee_id,
            employee_name,
            email,
            department,
            salary,
            updated_at
        FROM employee_records
        ORDER BY employee_id
        """,
    )


# ---------------------------------------------------------------------------
# 9. Pivot-style analysis
# ---------------------------------------------------------------------------

def demonstrate_pivot_style_analysis(connection: sqlite3.Connection) -> None:
    """
    SQLite does not provide a PIVOT keyword.

    Conditional aggregation produces a portable pivot-style result.
    """

    run_query(
        connection,
        "Pivot-style sales by region and product",
        """
        SELECT
            region,
            SUM(CASE WHEN product = 'Laptop' THEN amount ELSE 0 END)
                AS laptop,
            SUM(CASE WHEN product = 'Phone' THEN amount ELSE 0 END)
                AS phone,
            SUM(CASE WHEN product = 'Tablet' THEN amount ELSE 0 END)
                AS tablet,
            SUM(amount) AS total
        FROM sales
        GROUP BY region
        ORDER BY region
        """,
    )

    run_query(
        connection,
        "Pivot-style counts by product",
        """
        SELECT
            region,
            SUM(CASE WHEN product = 'Laptop' THEN 1 ELSE 0 END)
                AS laptop_transactions,
            SUM(CASE WHEN product = 'Phone' THEN 1 ELSE 0 END)
                AS phone_transactions,
            SUM(CASE WHEN product = 'Tablet' THEN 1 ELSE 0 END)
                AS tablet_transactions
        FROM sales
        GROUP BY region
        ORDER BY region
        """,
    )


def build_dynamic_pivot_sql(
    categories: Sequence[str],
    table_name: str = "sales",
) -> str:
    """
    Build pivot-style SQL for a known-safe list of category values.

    Identifiers cannot normally be passed as SQL parameters, so dynamically
    generated identifiers must come from a trusted allow-list rather than
    arbitrary user input.
    """
    allowed_identifier_characters = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789_"
    )

    expressions: list[str] = []

    for category in categories:
        if not category:
            raise ValueError("Category names cannot be empty.")

        if any(character not in allowed_identifier_characters for character in category):
            raise ValueError(
                "Unsafe category identifier. Use an application-level allow-list."
            )

        escaped_value = category.replace("'", "''")
        expressions.append(
            "SUM(CASE WHEN product = "
            f"'{escaped_value}' THEN amount ELSE 0 END) AS "
            f'"{category.lower()}_sales"'
        )

    if not expressions:
        raise ValueError("At least one category is required.")

    return (
        "SELECT region,\n    "
        + ",\n    ".join(expressions)
        + f"\nFROM {table_name}\nGROUP BY region\nORDER BY region"
    )


# ---------------------------------------------------------------------------
# 10. Advanced combined analysis
# ---------------------------------------------------------------------------

def demonstrate_combined_analysis(connection: sqlite3.Connection) -> None:
    """
    Combine aggregation, ranking, percentage-of-total, and cumulative values.

    This resembles a business reporting query where each region's sales are
    ranked and each transaction's contribution is calculated.
    """

    run_query(
        connection,
        "Combined analytical report",
        """
        WITH region_totals AS (
            SELECT
                region,
                SUM(amount) AS region_total
            FROM sales
            GROUP BY region
        ),
        enriched AS (
            SELECT
                s.sale_id,
                s.region,
                s.salesperson,
                s.product,
                s.sale_date,
                s.amount,
                rt.region_total,
                ROW_NUMBER() OVER (
                    PARTITION BY s.region
                    ORDER BY s.amount DESC, s.sale_id
                ) AS region_rank,
                SUM(s.amount) OVER (
                    PARTITION BY s.region
                    ORDER BY s.sale_date, s.sale_id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS region_running_total
            FROM sales AS s
            JOIN region_totals AS rt
                ON rt.region = s.region
        )
        SELECT
            sale_id,
            region,
            salesperson,
            product,
            amount,
            region_total,
            ROUND(amount * 100.0 / region_total, 2)
                AS percent_of_region,
            region_rank,
            region_running_total
        FROM enriched
        ORDER BY region, region_rank
        """,
    )


# ---------------------------------------------------------------------------
# 11. Edge cases and important distinctions
# ---------------------------------------------------------------------------

def demonstrate_edge_cases(connection: sqlite3.Connection) -> None:
    """Show how NULL and ties can change analytical results."""

    connection.execute(
        """
        CREATE TEMP TABLE edge_sales (
            id INTEGER PRIMARY KEY,
            group_name TEXT,
            amount REAL
        )
        """
    )

    connection.executemany(
        """
        INSERT INTO edge_sales(id, group_name, amount)
        VALUES (?, ?, ?)
        """,
        [
            (1, "A", 100),
            (2, "A", 100),
            (3, "A", 90),
            (4, "A", None),
            (5, "B", 50),
        ],
    )

    run_query(
        connection,
        "Edge case: ROW_NUMBER versus RANK versus DENSE_RANK",
        """
        SELECT
            id,
            group_name,
            amount,
            ROW_NUMBER() OVER (
                PARTITION BY group_name
                ORDER BY amount DESC
            ) AS row_number,
            RANK() OVER (
                PARTITION BY group_name
                ORDER BY amount DESC
            ) AS rank_value,
            DENSE_RANK() OVER (
                PARTITION BY group_name
                ORDER BY amount DESC
            ) AS dense_rank_value
        FROM edge_sales
        ORDER BY group_name, row_number
        """,
    )

    run_query(
        connection,
        "Edge case: explicit NULL ordering",
        """
        SELECT
            id,
            group_name,
            amount
        FROM edge_sales
        ORDER BY
            amount IS NULL,
            amount DESC
        """,
    )


# ---------------------------------------------------------------------------
# 12. Query plans and indexes
# ---------------------------------------------------------------------------

def demonstrate_indexes_and_query_plan(connection: sqlite3.Connection) -> None:
    """
    Indexes can reduce sorting and filtering cost, but they add storage and
    write overhead. Window functions may still require temporary sorting.
    """

    connection.execute(
        """
        CREATE INDEX idx_sales_region_amount
        ON sales(region, amount DESC, sale_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX idx_events_customer_date
        ON customer_events(customer_id, event_date, event_id)
        """
    )

    rows = connection.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT
            sale_id,
            region,
            amount
        FROM sales
        WHERE region = 'North'
        ORDER BY amount DESC, sale_id
        """
    ).fetchall()

    print_rows(
        "EXPLAIN QUERY PLAN: indexed regional ordering",
        rows,
    )


# ---------------------------------------------------------------------------
# 13. Validation helpers
# ---------------------------------------------------------------------------

def assert_equal(actual: object, expected: object, message: str) -> None:
    """Simple dependency-free assertion helper."""
    if actual != expected:
        raise AssertionError(
            f"{message}: expected {expected!r}, got {actual!r}"
        )


def run_tests(connection: sqlite3.Connection) -> None:
    """Validate the most important analytical invariants."""

    top_rows = top_n_per_group(connection, 2)
    counts: dict[str, int] = {}

    for row in top_rows:
        counts[row["region"]] = counts.get(row["region"], 0) + 1

    assert_equal(
        counts,
        {"North": 2, "South": 2, "West": 2},
        "Top-N should return two rows per region",
    )

    pivot_rows = connection.execute(
        """
        SELECT
            region,
            SUM(CASE WHEN product = 'Laptop' THEN amount ELSE 0 END) AS laptop,
            SUM(CASE WHEN product = 'Phone' THEN amount ELSE 0 END) AS phone,
            SUM(CASE WHEN product = 'Tablet' THEN amount ELSE 0 END) AS tablet
        FROM sales
        GROUP BY region
        """
    ).fetchall()

    north = next(row for row in pivot_rows if row["region"] == "North")

    assert_equal(
        north["laptop"],
        3600.0,
        "North laptop pivot value",
    )

    assert_equal(
        north["phone"],
        1700.0,
        "North phone pivot value",
    )

    duplicate_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT email
            FROM employee_records
            GROUP BY email
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]

    assert_equal(
        duplicate_count,
        3,
        "Initial duplicate groups",
    )

    print("\n" + "=" * 88)
    print("TESTS PASSED")
    print("=" * 88)


# ---------------------------------------------------------------------------
# 14. Production-oriented safe dynamic SQL
# ---------------------------------------------------------------------------

def demonstrate_parameterization(connection: sqlite3.Connection) -> None:
    """
    Values should be bound as parameters rather than concatenated into SQL.

    Parameterization protects value expressions from SQL injection and also
    lets the database distinguish SQL structure from data.
    """

    requested_region = "North"

    run_query(
        connection,
        "Parameterized query",
        """
        SELECT
            sale_id,
            salesperson,
            amount
        FROM sales
        WHERE region = ?
        ORDER BY amount DESC
        """,
        (requested_region,),
    )


# ---------------------------------------------------------------------------
# 15. Main educational execution
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 88)
    print("ADVANCED SQL PATTERNS")
    print("Top-N | Gaps-and-Islands | Deduplication | Pivot-Style Analysis")
    print("=" * 88)

    connection = connect_database()

    try:
        seed_database(connection)

        demonstrate_foundations(connection)
        demonstrate_window_functions(connection)

        top_n_per_group(connection, 2)
        top_n_with_ties(connection, 2)

        demonstrate_gaps_and_islands(connection)
        demonstrate_sessionization(connection)

        demonstrate_duplicate_detection(connection)

        # Dynamic pivot generation is demonstrated before destructive
        # deduplication so the original employee data remains available.
        dynamic_sql = build_dynamic_pivot_sql(
            ["Laptop", "Phone", "Tablet"]
        )
        run_query(
            connection,
            "Generated dynamic pivot SQL",
            dynamic_sql,
        )

        demonstrate_pivot_style_analysis(connection)
        demonstrate_combined_analysis(connection)
        demonstrate_edge_cases(connection)
        demonstrate_indexes_and_query_plan(connection)
        demonstrate_parameterization(connection)

        # Deduplication is intentionally performed near the end because it is
        # a data-changing operation.
        deduplicate_keep_latest(connection)

        # Re-run duplicate detection after deduplication.
        run_query(
            connection,
            "Duplicate groups after deduplication",
            """
            SELECT
                email,
                COUNT(*) AS row_count
            FROM employee_records
            GROUP BY email
            HAVING COUNT(*) > 1
            """,
        )

        # The duplicate test is run against a fresh temporary copy because the
        # employee table has intentionally changed.
        connection.execute(
            """
            CREATE TEMP TABLE employee_test AS
            SELECT *
            FROM employee_records
            """
        )

        run_tests(connection)

        print("\nStudy file completed successfully.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
