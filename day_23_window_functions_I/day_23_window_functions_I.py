"""
Window Functions I | OVER, PARTITION BY, ORDER BY

A self-contained study program for SQL window functions, with emphasis on:
    - OVER()
    - PARTITION BY
    - ORDER BY inside OVER()
    - aggregate window functions
    - ranking functions
    - row-wise comparisons
    - running calculations
    - frames and their subtle behavior
    - NULL handling
    - ties
    - deterministic ordering
    - performance and indexing
    - practical analytical queries

The program uses Python's standard-library sqlite3 module so that the SQL
examples can be executed directly without installing third-party packages.

Requirements:
    Python 3.9+
    SQLite with window-function support
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable, Sequence


# ---------------------------------------------------------------------------
# 1. DATABASE SETUP
# ---------------------------------------------------------------------------

def create_connection() -> sqlite3.Connection:
    """
    Create an in-memory SQLite database.

    An in-memory database is useful for a teaching program because:
    - no external database server is required;
    - no files need to be created;
    - every execution starts from the same clean state.
    """
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    """Create tables used by the examples."""
    connection.executescript(
        """
        CREATE TABLE departments (
            department_id INTEGER PRIMARY KEY,
            department_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY,
            employee_name TEXT NOT NULL,
            department_id INTEGER NOT NULL,
            salary REAL NOT NULL CHECK (salary >= 0),
            hire_date TEXT NOT NULL,
            FOREIGN KEY (department_id) REFERENCES departments(department_id)
        );

        CREATE TABLE sales (
            sale_id INTEGER PRIMARY KEY,
            employee_id INTEGER NOT NULL,
            sale_date TEXT NOT NULL,
            region TEXT NOT NULL,
            product TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            unit_price REAL NOT NULL CHECK (unit_price >= 0),
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        );

        CREATE INDEX idx_employees_department_salary
            ON employees(department_id, salary);

        CREATE INDEX idx_sales_employee_date
            ON sales(employee_id, sale_date);

        CREATE INDEX idx_sales_region_date
            ON sales(region, sale_date);
        """
    )


def insert_sample_data(connection: sqlite3.Connection) -> None:
    """Insert a deterministic dataset containing ties and multiple partitions."""
    connection.executemany(
        """
        INSERT INTO departments(department_id, department_name)
        VALUES (?, ?)
        """,
        [
            (10, "Engineering"),
            (20, "Sales"),
            (30, "Finance"),
            (40, "Operations"),
        ],
    )

    connection.executemany(
        """
        INSERT INTO employees(
            employee_id, employee_name, department_id, salary, hire_date
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (101, "Aarav", 10, 95000, "2022-02-15"),
            (102, "Diya", 10, 110000, "2021-07-01"),
            (103, "Kabir", 10, 110000, "2023-03-12"),
            (104, "Meera", 10, 82000, "2024-01-20"),
            (105, "Rohan", 20, 90000, "2022-05-18"),
            (106, "Anaya", 20, 105000, "2021-03-11"),
            (107, "Vihaan", 20, 105000, "2023-09-09"),
            (108, "Ishita", 20, 76000, "2024-04-05"),
            (109, "Arjun", 30, 120000, "2020-11-30"),
            (110, "Sara", 30, 98000, "2022-08-22"),
            (111, "Neil", 30, 98000, "2024-02-01"),
            (112, "Tara", 40, 88000, "2023-01-10"),
        ],
    )

    connection.executemany(
        """
        INSERT INTO sales(
            sale_id, employee_id, sale_date, region, product, quantity, unit_price
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (1, 105, "2026-01-02", "North", "Laptop", 2, 900),
            (2, 106, "2026-01-03", "North", "Phone", 5, 500),
            (3, 107, "2026-01-03", "North", "Laptop", 1, 900),
            (4, 105, "2026-01-05", "North", "Monitor", 3, 300),
            (5, 106, "2026-01-08", "North", "Laptop", 2, 900),
            (6, 107, "2026-01-10", "North", "Phone", 4, 500),
            (7, 108, "2026-01-11", "North", "Monitor", 2, 300),
            (8, 105, "2026-01-15", "North", "Phone", 3, 500),
            (9, 109, "2026-01-02", "West", "Laptop", 1, 900),
            (10, 110, "2026-01-04", "West", "Phone", 4, 500),
            (11, 111, "2026-01-04", "West", "Monitor", 5, 300),
            (12, 109, "2026-01-07", "West", "Laptop", 2, 900),
            (13, 110, "2026-01-12", "West", "Phone", 2, 500),
            (14, 111, "2026-01-14", "West", "Laptop", 3, 900),
            (15, 112, "2026-01-03", "South", "Monitor", 4, 300),
            (16, 112, "2026-01-09", "South", "Laptop", 2, 900),
        ],
    )

    connection.commit()


# ---------------------------------------------------------------------------
# 2. DISPLAY HELPERS
# ---------------------------------------------------------------------------

def print_rows(
    connection: sqlite3.Connection,
    sql: str,
    parameters: Sequence[object] = (),
    title: str = "",
) -> None:
    """
    Execute a query and print its result.

    The helper intentionally keeps the SQL visible in the program so a learner
    can copy the query into a SQL client and experiment with it.
    """
    if title:
        print(f"\n{'=' * 80}\n{title}\n{'=' * 80}")

    print("\nSQL:")
    print(sql.strip())

    cursor = connection.execute(sql, parameters)
    rows = cursor.fetchall()

    if not rows:
        print("\n(no rows)")
        return

    column_names = rows[0].keys()
    print("\n" + " | ".join(column_names))
    print("-" * 80)

    for row in rows:
        values = []
        for column in column_names:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:.2f}")
            else:
                values.append(str(value))
        print(" | ".join(values))


# ---------------------------------------------------------------------------
# 3. FUNDAMENTALS: A NORMAL AGGREGATE VERSUS A WINDOW AGGREGATE
# ---------------------------------------------------------------------------

def demonstrate_basic_difference(connection: sqlite3.Connection) -> None:
    """
    Show the fundamental difference between GROUP BY and a window function.

    GROUP BY changes the number of rows.
    A window function calculates across related rows while preserving the
    individual rows in the result.
    """
    print_rows(
        connection,
        """
        SELECT
            department_id,
            COUNT(*) AS employee_count,
            ROUND(AVG(salary), 2) AS average_salary
        FROM employees
        GROUP BY department_id
        ORDER BY department_id;
        """,
        title="GROUP BY: rows are collapsed into groups",
    )

    print_rows(
        connection,
        """
        SELECT
            employee_id,
            employee_name,
            department_id,
            salary,
            COUNT(*) OVER (
                PARTITION BY department_id
            ) AS department_employee_count,
            ROUND(
                AVG(salary) OVER (
                    PARTITION BY department_id
                ),
                2
            ) AS department_average_salary
        FROM employees
        ORDER BY department_id, salary DESC, employee_id;
        """,
        title="Window aggregate: individual rows are preserved",
    )


# ---------------------------------------------------------------------------
# 4. OVER()
# ---------------------------------------------------------------------------

def demonstrate_over_without_partition(connection: sqlite3.Connection) -> None:
    """
    OVER() defines a window over the query result.

    With no PARTITION BY and no ORDER BY, the window normally represents the
    entire result set.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_id,
            employee_name,
            salary,
            COUNT(*) OVER () AS total_employees,
            ROUND(AVG(salary) OVER (), 2) AS company_average_salary,
            MIN(salary) OVER () AS minimum_company_salary,
            MAX(salary) OVER () AS maximum_company_salary
        FROM employees
        ORDER BY employee_id;
        """,
        title="OVER(): one window covering the complete result set",
    )


# ---------------------------------------------------------------------------
# 5. PARTITION BY
# ---------------------------------------------------------------------------

def demonstrate_partition_by(connection: sqlite3.Connection) -> None:
    """
    PARTITION BY divides rows into independent logical windows.

    It does not remove rows. It controls which rows can contribute to the
    calculation for each current row.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_name,
            department_id,
            salary,
            ROUND(
                AVG(salary) OVER (
                    PARTITION BY department_id
                ),
                2
            ) AS department_average
        FROM employees
        ORDER BY department_id, employee_name;
        """,
        title="PARTITION BY: one independent window per department",
    )

    print_rows(
        connection,
        """
        SELECT
            employee_name,
            department_id,
            salary,
            salary - AVG(salary) OVER (
                PARTITION BY department_id
            ) AS difference_from_department_average
        FROM employees
        ORDER BY department_id, salary DESC, employee_id;
        """,
        title="Comparing every employee with their department average",
    )


# ---------------------------------------------------------------------------
# 6. ORDER BY INSIDE OVER()
# ---------------------------------------------------------------------------

def demonstrate_order_by(connection: sqlite3.Connection) -> None:
    """
    ORDER BY inside OVER() defines the logical sequence used by many window
    calculations.

    This is different from the final SELECT ORDER BY, which controls the
    presentation order of the result set.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_name,
            department_id,
            salary,
            ROW_NUMBER() OVER (
                PARTITION BY department_id
                ORDER BY salary DESC, employee_id
            ) AS salary_position
        FROM employees
        ORDER BY department_id, salary_position;
        """,
        title="ORDER BY inside OVER(): row numbering within each department",
    )

    print_rows(
        connection,
        """
        SELECT
            employee_name,
            department_id,
            salary,
            ROW_NUMBER() OVER (
                ORDER BY salary DESC, employee_id
            ) AS company_salary_position
        FROM employees
        ORDER BY company_salary_position;
        """,
        title="ORDER BY without PARTITION BY: one company-wide sequence",
    )


# ---------------------------------------------------------------------------
# 7. RANKING FUNCTIONS
# ---------------------------------------------------------------------------

def demonstrate_ranking_functions(connection: sqlite3.Connection) -> None:
    """
    ROW_NUMBER, RANK, and DENSE_RANK behave differently when ties exist.

    Example:
        salaries = 110000, 110000, 95000

        ROW_NUMBER  -> 1, 2, 3
        RANK        -> 1, 1, 3
        DENSE_RANK  -> 1, 1, 2
    """
    print_rows(
        connection,
        """
        SELECT
            employee_name,
            department_id,
            salary,
            ROW_NUMBER() OVER (
                PARTITION BY department_id
                ORDER BY salary DESC, employee_id
            ) AS row_number_value,
            RANK() OVER (
                PARTITION BY department_id
                ORDER BY salary DESC
            ) AS rank_value,
            DENSE_RANK() OVER (
                PARTITION BY department_id
                ORDER BY salary DESC
            ) AS dense_rank_value
        FROM employees
        ORDER BY department_id, salary DESC, employee_id;
        """,
        title="ROW_NUMBER versus RANK versus DENSE_RANK",
    )


# ---------------------------------------------------------------------------
# 8. FIRST_VALUE, LAST_VALUE, NTH_VALUE
# ---------------------------------------------------------------------------

def demonstrate_value_functions(connection: sqlite3.Connection) -> None:
    """
    FIRST_VALUE and LAST_VALUE are sensitive to the window frame.

    LAST_VALUE is a common source of confusion: with the default frame, the
    current row may be the frame's last row, so LAST_VALUE can equal the
    current value rather than the final value of the partition.

    An explicit ROWS frame makes the intention clear.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_name,
            department_id,
            salary,
            FIRST_VALUE(employee_name) OVER (
                PARTITION BY department_id
                ORDER BY salary DESC, employee_id
            ) AS highest_paid_employee,

            LAST_VALUE(employee_name) OVER (
                PARTITION BY department_id
                ORDER BY salary DESC, employee_id
            ) AS default_frame_last_value,

            LAST_VALUE(employee_name) OVER (
                PARTITION BY department_id
                ORDER BY salary DESC, employee_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) AS actual_last_employee_in_order
        FROM employees
        ORDER BY department_id, salary DESC, employee_id;
        """,
        title="FIRST_VALUE and LAST_VALUE with explicit frame comparison",
    )


# ---------------------------------------------------------------------------
# 9. LAG AND LEAD
# ---------------------------------------------------------------------------

def demonstrate_lag_lead(connection: sqlite3.Connection) -> None:
    """
    LAG accesses an earlier row.
    LEAD accesses a later row.

    They are useful for:
        - period-over-period comparisons;
        - detecting changes;
        - calculating deltas;
        - identifying gaps;
        - trend analysis.
    """
    print_rows(
        connection,
        """
        SELECT
            sale_id,
            sale_date,
            region,
            product,
            quantity * unit_price AS revenue,
            LAG(quantity * unit_price) OVER (
                PARTITION BY region
                ORDER BY sale_date, sale_id
            ) AS previous_sale_revenue,
            LEAD(quantity * unit_price) OVER (
                PARTITION BY region
                ORDER BY sale_date, sale_id
            ) AS next_sale_revenue
        FROM sales
        ORDER BY region, sale_date, sale_id;
        """,
        title="LAG and LEAD for previous and next rows",
    )

    print_rows(
        connection,
        """
        SELECT
            sale_id,
            sale_date,
            region,
            quantity * unit_price AS revenue,
            quantity * unit_price
                - LAG(quantity * unit_price) OVER (
                    PARTITION BY region
                    ORDER BY sale_date, sale_id
                ) AS change_from_previous_sale
        FROM sales
        ORDER BY region, sale_date, sale_id;
        """,
        title="Revenue change from the previous sale",
    )


# ---------------------------------------------------------------------------
# 10. RUNNING TOTALS
# ---------------------------------------------------------------------------

def demonstrate_running_totals(connection: sqlite3.Connection) -> None:
    """Demonstrate cumulative calculations using ORDER BY and an explicit frame."""
    print_rows(
        connection,
        """
        SELECT
            sale_id,
            sale_date,
            region,
            quantity * unit_price AS revenue,
            SUM(quantity * unit_price) OVER (
                PARTITION BY region
                ORDER BY sale_date, sale_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS running_region_revenue
        FROM sales
        ORDER BY region, sale_date, sale_id;
        """,
        title="Running revenue by region",
    )


# ---------------------------------------------------------------------------
# 11. MOVING WINDOWS
# ---------------------------------------------------------------------------

def demonstrate_moving_window(connection: sqlite3.Connection) -> None:
    """
    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW means:
        current row + previous two physical rows.

    This is a three-row moving average, not necessarily a three-day average.
    The distinction matters when dates have gaps or duplicate dates.
    """
    print_rows(
        connection,
        """
        SELECT
            sale_id,
            sale_date,
            region,
            quantity * unit_price AS revenue,
            ROUND(
                AVG(quantity * unit_price) OVER (
                    PARTITION BY region
                    ORDER BY sale_date, sale_id
                    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                ),
                2
            ) AS three_row_moving_average
        FROM sales
        ORDER BY region, sale_date, sale_id;
        """,
        title="Three-row moving average",
    )


# ---------------------------------------------------------------------------
# 12. NTILE
# ---------------------------------------------------------------------------

def demonstrate_ntile(connection: sqlite3.Connection) -> None:
    """
    NTILE(n) distributes ordered rows into approximately equal-sized buckets.

    It is useful for analytical segmentation such as quartiles or deciles.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_name,
            salary,
            NTILE(4) OVER (
                ORDER BY salary DESC, employee_id
            ) AS salary_quartile
        FROM employees
        ORDER BY salary DESC, employee_id;
        """,
        title="NTILE(4): salary segmentation into four buckets",
    )


# ---------------------------------------------------------------------------
# 13. PERCENT_RANK AND CUME_DIST
# ---------------------------------------------------------------------------

def demonstrate_distribution_functions(
    connection: sqlite3.Connection,
) -> None:
    """Demonstrate relative position functions."""
    print_rows(
        connection,
        """
        SELECT
            employee_name,
            salary,
            ROUND(
                PERCENT_RANK() OVER (
                    ORDER BY salary
                ),
                3
            ) AS percent_rank,
            ROUND(
                CUME_DIST() OVER (
                    ORDER BY salary
                ),
                3
            ) AS cumulative_distribution
        FROM employees
        ORDER BY salary, employee_id;
        """,
        title="PERCENT_RANK and CUME_DIST",
    )


# ---------------------------------------------------------------------------
# 14. MULTIPLE PARTITIONING COLUMNS
# ---------------------------------------------------------------------------

def demonstrate_multiple_partition_columns(
    connection: sqlite3.Connection,
) -> None:
    """
    PARTITION BY can contain multiple columns.

    Each unique combination becomes a separate partition.
    """
    print_rows(
        connection,
        """
        SELECT
            sale_id,
            sale_date,
            region,
            product,
            quantity * unit_price AS revenue,
            SUM(quantity * unit_price) OVER (
                PARTITION BY region, product
            ) AS region_product_revenue
        FROM sales
        ORDER BY region, product, sale_date, sale_id;
        """,
        title="Partitioning by more than one column",
    )


# ---------------------------------------------------------------------------
# 15. WINDOW FUNCTION WITH CASE
# ---------------------------------------------------------------------------

def demonstrate_conditional_window_logic(
    connection: sqlite3.Connection,
) -> None:
    """
    Window expressions can be combined with CASE.

    The conditional expression can be evaluated before the window aggregate.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_name,
            department_id,
            salary,
            SUM(
                CASE
                    WHEN salary >= 100000 THEN salary
                    ELSE 0
                END
            ) OVER (
                PARTITION BY department_id
            ) AS high_salary_total
        FROM employees
        ORDER BY department_id, salary DESC, employee_id;
        """,
        title="Conditional expression inside a window aggregate",
    )


# ---------------------------------------------------------------------------
# 16. FILTER WITH WINDOW AGGREGATES
# ---------------------------------------------------------------------------

def demonstrate_filter(connection: sqlite3.Connection) -> None:
    """
    SQLite supports FILTER for aggregate functions.

    FILTER allows an aggregate window function to consider only rows matching
    a condition while retaining the original result rows.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_name,
            department_id,
            salary,
            COUNT(*) FILTER (
                WHERE salary >= 100000
            ) OVER (
                PARTITION BY department_id
            ) AS high_earner_count
        FROM employees
        ORDER BY department_id, employee_name;
        """,
        title="FILTER with a window aggregate",
    )


# ---------------------------------------------------------------------------
# 17. WINDOW CLAUSE
# ---------------------------------------------------------------------------

def demonstrate_named_window(connection: sqlite3.Connection) -> None:
    """
    A named WINDOW definition can reduce repetition when several functions use
    the same PARTITION BY and ORDER BY specification.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_name,
            department_id,
            salary,
            ROW_NUMBER() OVER department_window AS row_number_value,
            RANK() OVER department_window AS rank_value,
            DENSE_RANK() OVER department_window AS dense_rank_value
        FROM employees
        WINDOW department_window AS (
            PARTITION BY department_id
            ORDER BY salary DESC, employee_id
        )
        ORDER BY department_id, salary DESC, employee_id;
        """,
        title="Named WINDOW specification",
    )


# ---------------------------------------------------------------------------
# 18. TOP-N PER GROUP
# ---------------------------------------------------------------------------

def demonstrate_top_n_per_group(connection: sqlite3.Connection) -> None:
    """
    Window functions solve a common SQL problem:

        "Return the top two employees by salary from every department."

    A window function first assigns ranks. An outer query then filters those
    ranks. Window functions generally cannot be referenced directly in WHERE
    at the same query level where they are calculated.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_id,
            employee_name,
            department_id,
            salary,
            salary_rank
        FROM (
            SELECT
                employee_id,
                employee_name,
                department_id,
                salary,
                ROW_NUMBER() OVER (
                    PARTITION BY department_id
                    ORDER BY salary DESC, employee_id
                ) AS salary_rank
            FROM employees
        )
        WHERE salary_rank <= 2
        ORDER BY department_id, salary_rank;
        """,
        title="Top two employees per department",
    )


# ---------------------------------------------------------------------------
# 19. DE-DUPLICATION WITH ROW_NUMBER
# ---------------------------------------------------------------------------

def demonstrate_deduplication_pattern(connection: sqlite3.Connection) -> None:
    """
    A common production pattern is:
        1. partition by the business key;
        2. order by a timestamp or priority;
        3. assign ROW_NUMBER;
        4. keep row_number = 1.

    The example below uses employee department + salary as an intentionally
    simple analytical key. Real systems should use a domain-specific key.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_id,
            employee_name,
            department_id,
            salary,
            ROW_NUMBER() OVER (
                PARTITION BY department_id, salary
                ORDER BY hire_date ASC, employee_id
            ) AS duplicate_group_position
        FROM employees
        ORDER BY department_id, salary, duplicate_group_position;
        """,
        title="ROW_NUMBER as a deterministic de-duplication pattern",
    )


# ---------------------------------------------------------------------------
# 20. DATE-ORDERED SALES ANALYSIS
# ---------------------------------------------------------------------------

def demonstrate_sales_analysis(connection: sqlite3.Connection) -> None:
    """
    Build several analytical values from one sales stream.

    This demonstrates why window functions are valuable: each sale remains
    visible while aggregate context is added to that row.
    """
    print_rows(
        connection,
        """
        SELECT
            sale_id,
            sale_date,
            region,
            product,
            quantity * unit_price AS revenue,

            SUM(quantity * unit_price) OVER (
                PARTITION BY region
            ) AS region_total,

            ROUND(
                100.0 * (quantity * unit_price)
                / SUM(quantity * unit_price) OVER (
                    PARTITION BY region
                ),
                2
            ) AS percentage_of_region_total,

            ROW_NUMBER() OVER (
                PARTITION BY region
                ORDER BY quantity * unit_price DESC, sale_id
            ) AS revenue_rank_in_region
        FROM sales
        ORDER BY region, revenue_rank_in_region;
        """,
        title="Multi-metric sales analysis",
    )


# ---------------------------------------------------------------------------
# 21. CTE + WINDOW FUNCTION
# ---------------------------------------------------------------------------

def demonstrate_cte_with_window(connection: sqlite3.Connection) -> None:
    """
    Common table expressions make multi-stage analytical queries easier to
    read. Here the first stage calculates revenue and the second stage applies
    window functions to that calculated value.
    """
    print_rows(
        connection,
        """
        WITH sale_values AS (
            SELECT
                sale_id,
                sale_date,
                region,
                product,
                quantity * unit_price AS revenue
            FROM sales
        ),
        ranked_sales AS (
            SELECT
                *,
                RANK() OVER (
                    PARTITION BY region
                    ORDER BY revenue DESC
                ) AS regional_rank
            FROM sale_values
        )
        SELECT
            sale_id,
            sale_date,
            region,
            product,
            revenue,
            regional_rank
        FROM ranked_sales
        WHERE regional_rank <= 2
        ORDER BY region, regional_rank, sale_id;
        """,
        title="CTE followed by a window function",
    )


# ---------------------------------------------------------------------------
# 22. EDGE CASE: TIES
# ---------------------------------------------------------------------------

def demonstrate_tie_behavior(connection: sqlite3.Connection) -> None:
    """
    Ties matter when ranking.

    RANK gives equal values the same rank and leaves gaps after ties.
    DENSE_RANK gives equal values the same rank without gaps.
    ROW_NUMBER always assigns unique sequence numbers.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_name,
            department_id,
            salary,
            ROW_NUMBER() OVER (
                PARTITION BY department_id
                ORDER BY salary DESC, employee_id
            ) AS row_number_with_tiebreaker,
            RANK() OVER (
                PARTITION BY department_id
                ORDER BY salary DESC
            ) AS rank_with_ties,
            DENSE_RANK() OVER (
                PARTITION BY department_id
                ORDER BY salary DESC
            ) AS dense_rank_with_ties
        FROM employees
        WHERE department_id = 10
        ORDER BY salary DESC, employee_id;
        """,
        title="Tie behavior in the Engineering department",
    )


# ---------------------------------------------------------------------------
# 23. EDGE CASE: NULLS
# ---------------------------------------------------------------------------

def demonstrate_null_ordering(connection: sqlite3.Connection) -> None:
    """
    Create a temporary table containing NULL values to demonstrate that
    NULL ordering can affect rankings.

    Explicit NULL handling is preferable when the desired ordering matters.
    """
    connection.execute(
        """
        CREATE TEMP TABLE nullable_scores (
            person TEXT NOT NULL,
            score REAL
        )
        """
    )

    connection.executemany(
        "INSERT INTO nullable_scores(person, score) VALUES (?, ?)",
        [
            ("A", 90),
            ("B", None),
            ("C", 75),
            ("D", None),
            ("E", 95),
        ],
    )

    print_rows(
        connection,
        """
        SELECT
            person,
            score,
            ROW_NUMBER() OVER (
                ORDER BY score DESC
            ) AS descending_position,
            ROW_NUMBER() OVER (
                ORDER BY
                    CASE WHEN score IS NULL THEN 1 ELSE 0 END,
                    score DESC
            ) AS explicit_nulls_last_position
        FROM nullable_scores
        ORDER BY explicit_nulls_last_position;
        """,
        title="NULL ordering and explicit NULL placement",
    )


# ---------------------------------------------------------------------------
# 24. EDGE CASE: DUPLICATE ORDERING VALUES
# ---------------------------------------------------------------------------

def demonstrate_deterministic_ordering(connection: sqlite3.Connection) -> None:
    """
    If the ORDER BY columns do not uniquely identify a row, ROW_NUMBER can
    assign tied rows in an order that is not guaranteed to remain stable.

    Adding a unique column such as employee_id creates a deterministic
    tiebreaker.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_name,
            salary,
            ROW_NUMBER() OVER (
                ORDER BY salary DESC
            ) AS potentially_nondeterministic_position,
            ROW_NUMBER() OVER (
                ORDER BY salary DESC, employee_id
            ) AS deterministic_position
        FROM employees
        ORDER BY salary DESC, employee_id;
        """,
        title="Deterministic ordering with a unique tiebreaker",
    )


# ---------------------------------------------------------------------------
# 25. EXPLAIN QUERY PLAN
# ---------------------------------------------------------------------------

def demonstrate_query_plan(connection: sqlite3.Connection) -> None:
    """
    Window queries may require sorting or temporary structures.

    Indexes can help with filtering and ordering, but an index is not a
    guarantee that every window query will avoid sorting.

    EXPLAIN QUERY PLAN is a practical first diagnostic tool in SQLite.
    """
    print_rows(
        connection,
        """
        EXPLAIN QUERY PLAN
        SELECT
            employee_id,
            department_id,
            salary,
            ROW_NUMBER() OVER (
                PARTITION BY department_id
                ORDER BY salary DESC, employee_id
            ) AS salary_position
        FROM employees
        ORDER BY department_id, salary DESC, employee_id;
        """,
        title="Inspecting the query plan for a window query",
    )


# ---------------------------------------------------------------------------
# 26. SQL LOGIC ORDER
# ---------------------------------------------------------------------------

def demonstrate_query_processing_concept(connection: sqlite3.Connection) -> None:
    """
    This query illustrates a common mental model:

        FROM
        WHERE
        GROUP BY
        HAVING
        window calculations
        SELECT result presentation
        ORDER BY

    Exact implementation details vary by database engine, but the key practical
    rule is that a window function cannot normally be used directly in WHERE
    at the same query level.

    The outer query therefore filters a value produced by the inner query.
    """
    print_rows(
        connection,
        """
        SELECT
            employee_name,
            department_id,
            salary,
            salary_rank
        FROM (
            SELECT
                employee_name,
                department_id,
                salary,
                RANK() OVER (
                    PARTITION BY department_id
                    ORDER BY salary DESC
                ) AS salary_rank
            FROM employees
            WHERE salary >= 80000
        )
        WHERE salary_rank <= 2
        ORDER BY department_id, salary_rank, employee_name;
        """,
        title="Filtering the result of a window calculation",
    )


# ---------------------------------------------------------------------------
# 27. VALIDATION HELPERS
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Employee:
    """A Python representation of an employee record."""

    employee_id: int
    employee_name: str
    department_id: int
    salary: float


def validate_employee(employee: Employee) -> None:
    """Validate basic business rules before a record enters an application."""
    if employee.employee_id <= 0:
        raise ValueError("employee_id must be positive")

    if not employee.employee_name.strip():
        raise ValueError("employee_name cannot be empty")

    if employee.salary < 0:
        raise ValueError("salary cannot be negative")


def demonstrate_python_validation() -> None:
    """Show application-level validation related to analytical data."""
    print(f"\n{'=' * 80}\nPython-side validation\n{'=' * 80}")

    valid_employee = Employee(999, "Test User", 10, 75000)
    validate_employee(valid_employee)
    print(f"Valid record accepted: {valid_employee}")

    invalid_employee = Employee(1000, "", 10, -50)

    try:
        validate_employee(invalid_employee)
    except ValueError as error:
        print(f"Invalid record rejected: {error}")


# ---------------------------------------------------------------------------
# 28. TESTING EXPECTATIONS
# ---------------------------------------------------------------------------

def run_assertions(connection: sqlite3.Connection) -> None:
    """
    Lightweight tests verify important window-function behavior.

    These tests make the study file executable as both a teaching program and
    a small regression test suite.
    """
    total_employees = connection.execute(
        "SELECT COUNT(*) FROM employees"
    ).fetchone()[0]
    assert total_employees == 12

    engineering_count = connection.execute(
        """
        SELECT DISTINCT
            COUNT(*) OVER (PARTITION BY department_id)
        FROM employees
        WHERE department_id = 10
        """
    ).fetchone()[0]
    assert engineering_count == 4

    ranking = connection.execute(
        """
        SELECT employee_name, salary, rank_value
        FROM (
            SELECT
                employee_name,
                salary,
                RANK() OVER (
                    PARTITION BY department_id
                    ORDER BY salary DESC
                ) AS rank_value
            FROM employees
        )
        WHERE department_id IS NULL
        """
    ).fetchall()
    assert ranking == []

    tied_ranks = connection.execute(
        """
        SELECT
            RANK() OVER (
                PARTITION BY department_id
                ORDER BY salary DESC
            ) AS rank_value,
            DENSE_RANK() OVER (
                PARTITION BY department_id
                ORDER BY salary DESC
            ) AS dense_rank_value
        FROM employees
        WHERE department_id = 10
        ORDER BY salary DESC, employee_id
        """
    ).fetchall()

    assert tied_ranks[0][0] == 1
    assert tied_ranks[1][0] == 1
    assert tied_ranks[2][0] == 3
    assert tied_ranks[2][1] == 2

    print(f"\n{'=' * 80}\nAssertions\n{'=' * 80}")
    print("All window-function assertions passed.")


# ---------------------------------------------------------------------------
# 29. COMMON MISTAKES AS EXECUTABLE EXAMPLES
# ---------------------------------------------------------------------------

def demonstrate_common_mistakes(connection: sqlite3.Connection) -> None:
    """
    Demonstrate several mistakes that frequently occur when learning windows.
    """
    print(f"\n{'=' * 80}\nCommon mistakes\n{'=' * 80}")

    print(
        "\nMistake 1: confusing PARTITION BY with GROUP BY.\n"
        "GROUP BY reduces rows; PARTITION BY keeps the rows and changes the\n"
        "set of rows visible to each window calculation."
    )

    print(
        "\nMistake 2: confusing the two ORDER BY clauses.\n"
        "ORDER BY inside OVER() controls window calculation order.\n"
        "ORDER BY at the end controls final output order."
    )

    print(
        "\nMistake 3: using RANK when unique sequential numbers are required.\n"
        "Use ROW_NUMBER when each row must receive a distinct position."
    )

    print(
        "\nMistake 4: forgetting a deterministic tiebreaker.\n"
        "For ROW_NUMBER, add a unique column after the business sort columns."
    )

    print(
        "\nMistake 5: misunderstanding LAST_VALUE.\n"
        "Specify an explicit frame when the intended meaning is the final row\n"
        "of the complete partition."
    )

    print_rows(
        connection,
        """
        SELECT
            employee_name,
            salary,
            ROW_NUMBER() OVER (
                ORDER BY salary DESC, employee_id
            ) AS position
        FROM employees
        ORDER BY employee_id;
        """,
        title="Window order and final output order are independent",
    )


# ---------------------------------------------------------------------------
# 30. PRODUCTION-ORIENTED EXAMPLE
# ---------------------------------------------------------------------------

def demonstrate_production_style_report(connection: sqlite3.Connection) -> None:
    """
    Produce a compact employee analytics report resembling an internal
    business intelligence query.
    """
    print_rows(
        connection,
        """
        WITH employee_metrics AS (
            SELECT
                e.employee_id,
                e.employee_name,
                d.department_name,
                e.salary,

                AVG(e.salary) OVER (
                    PARTITION BY e.department_id
                ) AS department_average,

                RANK() OVER (
                    PARTITION BY e.department_id
                    ORDER BY e.salary DESC
                ) AS department_rank,

                LAG(e.salary) OVER (
                    PARTITION BY e.department_id
                    ORDER BY e.hire_date, e.employee_id
                ) AS salary_of_previous_hire
            FROM employees AS e
            JOIN departments AS d
                ON d.department_id = e.department_id
        )
        SELECT
            employee_id,
            employee_name,
            department_name,
            salary,
            ROUND(department_average, 2) AS department_average,
            department_rank,
            salary_of_previous_hire,
            CASE
                WHEN salary > department_average THEN 'Above average'
                WHEN salary < department_average THEN 'Below average'
                ELSE 'At average'
            END AS salary_position
        FROM employee_metrics
        ORDER BY department_name, department_rank, employee_name;
        """,
        title="Production-style employee analytics report",
    )


# ---------------------------------------------------------------------------
# 31. MAIN PROGRAM
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the complete study sequence."""
    print("=" * 80)
    print("WINDOW FUNCTIONS I | OVER, PARTITION BY, ORDER BY")
    print("=" * 80)
    print(
        "\nThis executable study file uses SQLite to demonstrate SQL window "
        "functions from fundamentals through advanced analytical patterns."
    )

    connection = create_connection()

    try:
        create_schema(connection)
        insert_sample_data(connection)

        demonstrate_basic_difference(connection)
        demonstrate_over_without_partition(connection)
        demonstrate_partition_by(connection)
        demonstrate_order_by(connection)
        demonstrate_ranking_functions(connection)
        demonstrate_value_functions(connection)
        demonstrate_lag_lead(connection)
        demonstrate_running_totals(connection)
        demonstrate_moving_window(connection)
        demonstrate_ntile(connection)
        demonstrate_distribution_functions(connection)
        demonstrate_multiple_partition_columns(connection)
        demonstrate_conditional_window_logic(connection)
        demonstrate_filter(connection)
        demonstrate_named_window(connection)
        demonstrate_top_n_per_group(connection)
        demonstrate_deduplication_pattern(connection)
        demonstrate_sales_analysis(connection)
        demonstrate_cte_with_window(connection)
        demonstrate_tie_behavior(connection)
        demonstrate_null_ordering(connection)
        demonstrate_deterministic_ordering(connection)
        demonstrate_query_plan(connection)
        demonstrate_query_processing_concept(connection)
        demonstrate_python_validation()
        run_assertions(connection)
        demonstrate_common_mistakes(connection)
        demonstrate_production_style_report(connection)

        print(f"\n{'=' * 80}")
        print("Study program completed successfully.")
        print(f"{'=' * 80}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
