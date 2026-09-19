"""
SQL Subqueries: Scalar, Correlated, Nested, and Multi-Level Subqueries

This standalone Python study file uses SQLite from Python's standard library to
demonstrate SQL subqueries from beginner through advanced level.

Covered:
- What a subquery is
- Scalar subqueries
- Single-row and single-column subqueries
- IN and NOT IN
- EXISTS and NOT EXISTS
- Nested subqueries
- Multi-level subqueries
- Correlated subqueries
- Correlated EXISTS
- Aggregate subqueries
- Subqueries in SELECT, WHERE, FROM, and HAVING
- Derived tables
- Comparison with JOINs
- NULL behavior and NOT IN
- Edge cases
- Validation and error handling
- Query plans and indexing
- Security through parameterized SQL
- Practical reporting case study
- Testing and reusable query helpers

The examples use an in-memory SQLite database, so no external files or
third-party packages are required.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def print_title(title: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def print_subtitle(title: str) -> None:
    print("\n" + "-" * 72)
    print(title)
    print("-" * 72)


def print_rows(
    rows: Sequence[sqlite3.Row],
    columns: Sequence[str] | None = None,
) -> None:
    """Print SQLite rows in a compact table."""
    if not rows:
        print("(no rows)")
        return

    if columns is None:
        columns = rows[0].keys()

    widths = {
        column: max(
            len(str(column)),
            *(len(str(row[column])) for row in rows),
        )
        for column in columns
    }

    header = " | ".join(str(column).ljust(widths[column]) for column in columns)
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
    parameters: Sequence[Any] = (),
    columns: Sequence[str] | None = None,
) -> list[sqlite3.Row]:
    """Execute a query, print the SQL, and display its result."""
    print("\nSQL:")
    print(sql.strip())

    if parameters:
        print(f"Parameters: {tuple(parameters)}")

    cursor = connection.execute(sql, parameters)
    rows = cursor.fetchall()
    print_rows(rows, columns)
    return rows


def explain_query_plan(
    connection: sqlite3.Connection,
    sql: str,
    parameters: Sequence[Any] = (),
) -> None:
    """Show SQLite's query-plan representation."""
    print("\nQuery plan:")
    plan_rows = connection.execute(
        "EXPLAIN QUERY PLAN " + sql,
        parameters,
    ).fetchall()

    for row in plan_rows:
        print(
            f"selectid={row[0]}, order={row[1]}, from={row[2]}, detail={row[3]}"
        )


@contextmanager
def transaction(connection: sqlite3.Connection):
    """Small transaction context manager with rollback on failure."""
    try:
        yield
        connection.commit()
    except Exception:
        connection.rollback()
        raise


# ---------------------------------------------------------------------------
# Database construction
# ---------------------------------------------------------------------------

def create_database() -> sqlite3.Connection:
    """
    Build an in-memory relational database.

    The schema intentionally contains relationships that make subqueries
    meaningful:
        departments -> employees
        departments -> projects
        employees -> projects through assignments
        employees -> sales
        employees -> performance_reviews
    """
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    schema = """
    CREATE TABLE departments (
        department_id INTEGER PRIMARY KEY,
        department_name TEXT NOT NULL UNIQUE,
        location TEXT NOT NULL,
        budget REAL NOT NULL CHECK (budget >= 0)
    );

    CREATE TABLE employees (
        employee_id INTEGER PRIMARY KEY,
        employee_name TEXT NOT NULL,
        department_id INTEGER NOT NULL,
        manager_id INTEGER,
        salary REAL NOT NULL CHECK (salary > 0),
        hire_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'INACTIVE')),
        FOREIGN KEY (department_id) REFERENCES departments(department_id),
        FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
    );

    CREATE TABLE projects (
        project_id INTEGER PRIMARY KEY,
        project_name TEXT NOT NULL,
        department_id INTEGER NOT NULL,
        budget REAL NOT NULL CHECK (budget >= 0),
        status TEXT NOT NULL CHECK (status IN ('PLANNED', 'ACTIVE', 'CLOSED')),
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
    );

    CREATE TABLE assignments (
        employee_id INTEGER NOT NULL,
        project_id INTEGER NOT NULL,
        hours_allocated REAL NOT NULL CHECK (hours_allocated >= 0),
        PRIMARY KEY (employee_id, project_id),
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
        FOREIGN KEY (project_id) REFERENCES projects(project_id)
    );

    CREATE TABLE sales (
        sale_id INTEGER PRIMARY KEY,
        employee_id INTEGER NOT NULL,
        sale_date TEXT NOT NULL,
        amount REAL NOT NULL CHECK (amount >= 0),
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
    );

    CREATE TABLE performance_reviews (
        review_id INTEGER PRIMARY KEY,
        employee_id INTEGER NOT NULL,
        review_date TEXT NOT NULL,
        score REAL NOT NULL CHECK (score BETWEEN 0 AND 100),
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
    );

    CREATE INDEX idx_employees_department
        ON employees(department_id);

    CREATE INDEX idx_employees_salary
        ON employees(salary);

    CREATE INDEX idx_employees_manager
        ON employees(manager_id);

    CREATE INDEX idx_assignments_employee
        ON assignments(employee_id);

    CREATE INDEX idx_assignments_project
        ON assignments(project_id);

    CREATE INDEX idx_sales_employee
        ON sales(employee_id);

    CREATE INDEX idx_reviews_employee
        ON performance_reviews(employee_id);
    """

    with transaction(connection):
        connection.executescript(schema)

        departments = [
            (1, "Engineering", "Bengaluru", 1800000),
            (2, "Finance", "Mumbai", 900000),
            (3, "Operations", "Delhi", 1200000),
            (4, "Research", "Hyderabad", 1500000),
            (5, "Security", "Pune", 1300000),
        ]

        connection.executemany(
            """
            INSERT INTO departments
            (department_id, department_name, location, budget)
            VALUES (?, ?, ?, ?)
            """,
            departments,
        )

        employees = [
            (1, "Aarav", 1, None, 150000, "2018-02-15", "ACTIVE"),
            (2, "Meera", 1, 1, 125000, "2019-06-10", "ACTIVE"),
            (3, "Kabir", 1, 1, 110000, "2021-01-20", "ACTIVE"),
            (4, "Ishita", 1, 2, 90000, "2022-07-01", "ACTIVE"),
            (5, "Rohan", 2, None, 140000, "2017-03-11", "ACTIVE"),
            (6, "Anaya", 2, 5, 100000, "2020-09-18", "ACTIVE"),
            (7, "Vivaan", 2, 5, 85000, "2023-04-12", "ACTIVE"),
            (8, "Diya", 3, None, 115000, "2018-11-02", "ACTIVE"),
            (9, "Arjun", 3, 8, 78000, "2022-05-09", "ACTIVE"),
            (10, "Sara", 3, 8, 72000, "2024-01-15", "ACTIVE"),
            (11, "Advik", 4, None, 155000, "2016-08-22", "ACTIVE"),
            (12, "Tara", 4, 11, 130000, "2019-10-05", "ACTIVE"),
            (13, "Neil", 4, 11, 95000, "2023-02-14", "ACTIVE"),
            (14, "Kavya", 5, None, 145000, "2017-12-01", "ACTIVE"),
            (15, "Yash", 5, 14, 105000, "2020-03-19", "ACTIVE"),
            (16, "Naina", 5, 14, 88000, "2022-12-10", "ACTIVE"),
            (17, "FormerEmployee", 2, 5, 76000, "2019-01-01", "INACTIVE"),
        ]

        connection.executemany(
            """
            INSERT INTO employees
            (employee_id, employee_name, department_id, manager_id,
             salary, hire_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            employees,
        )

        projects = [
            (1, "Cloud Migration", 1, 600000, "ACTIVE"),
            (2, "Developer Platform", 1, 450000, "ACTIVE"),
            (3, "Fraud Analytics", 2, 300000, "ACTIVE"),
            (4, "Cost Optimization", 2, 180000, "CLOSED"),
            (5, "Supply Forecasting", 3, 350000, "ACTIVE"),
            (6, "AI Research", 4, 700000, "ACTIVE"),
            (7, "Threat Intelligence", 5, 500000, "ACTIVE"),
            (8, "Security Automation", 5, 250000, "PLANNED"),
        ]

        connection.executemany(
            """
            INSERT INTO projects
            (project_id, project_name, department_id, budget, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            projects,
        )

        assignments = [
            (1, 1, 120),
            (2, 1, 160),
            (3, 2, 180),
            (4, 2, 100),
            (5, 3, 150),
            (6, 3, 100),
            (7, 4, 80),
            (8, 5, 150),
            (9, 5, 120),
            (10, 5, 80),
            (11, 6, 180),
            (12, 6, 160),
            (13, 6, 100),
            (14, 7, 180),
            (15, 7, 150),
            (16, 8, 120),
        ]

        connection.executemany(
            """
            INSERT INTO assignments
            (employee_id, project_id, hours_allocated)
            VALUES (?, ?, ?)
            """,
            assignments,
        )

        sales = [
            (1, 2, "2026-01-10", 90000),
            (2, 3, "2026-01-15", 120000),
            (3, 4, "2026-01-20", 75000),
            (4, 5, "2026-02-01", 60000),
            (5, 6, "2026-02-05", 140000),
            (6, 7, "2026-02-10", 95000),
            (7, 8, "2026-02-15", 50000),
            (8, 9, "2026-03-01", 110000),
            (9, 10, "2026-03-05", 70000),
            (10, 11, "2026-03-07", 65000),
            (11, 12, "2026-03-12", 180000),
            (12, 13, "2026-03-18", 130000),
            (13, 14, "2026-03-20", 90000),
            (14, 15, "2026-04-01", 160000),
            (15, 16, "2026-04-03", 105000),
            (16, 17, "2026-04-05", 72000),
        ]

        connection.executemany(
            """
            INSERT INTO sales
            (sale_id, employee_id, sale_date, amount)
            VALUES (?, ?, ?, ?)
            """,
            sales,
        )

        reviews = [
            (1, 2, "2025-12-20", 91),
            (2, 3, "2025-12-21", 84),
            (3, 4, "2025-12-22", 78),
            (4, 6, "2025-12-23", 88),
            (5, 7, "2025-12-24", 74),
            (6, 9, "2025-12-25", 81),
            (7, 10, "2025-12-26", 79),
            (8, 12, "2025-12-27", 95),
            (9, 13, "2025-12-28", 87),
            (10, 15, "2025-12-29", 90),
            (11, 16, "2025-12-30", 76),
        ]

        connection.executemany(
            """
            INSERT INTO performance_reviews
            (review_id, employee_id, review_date, score)
            VALUES (?, ?, ?, ?)
            """,
            reviews,
        )

    return connection


# ---------------------------------------------------------------------------
# Fundamental demonstrations
# ---------------------------------------------------------------------------

def demonstrate_basic_subquery(connection: sqlite3.Connection) -> None:
    print_title("1. What is a subquery?")

    print(
        """
A subquery is a SELECT statement embedded inside another SQL statement.

Conceptually:

    outer query
        |
        +-- subquery

The subquery can produce:
- one value,
- one column containing multiple values,
- one row,
- multiple rows and columns,
- a temporary result set used like a table.

A subquery is usually enclosed in parentheses.
The surrounding query is called the outer query.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT employee_name, salary
        FROM employees
        WHERE salary > (
            SELECT AVG(salary)
            FROM employees
        )
        ORDER BY salary DESC
        """,
    )


def demonstrate_scalar_subquery(connection: sqlite3.Connection) -> None:
    print_title("2. Scalar subqueries")

    print(
        """
A scalar subquery returns exactly one value.

Examples:
- AVG(salary)
- MAX(salary)
- COUNT(*)
- a single selected column from a single row

A scalar subquery can appear anywhere an expression is allowed.
"""
    )

    print_subtitle("Scalar subquery in WHERE")

    execute_and_print(
        connection,
        """
        SELECT employee_name, salary
        FROM employees
        WHERE salary = (
            SELECT MAX(salary)
            FROM employees
        )
        """,
    )

    print_subtitle("Scalar subquery in SELECT")

    execute_and_print(
        connection,
        """
        SELECT
            employee_name,
            salary,
            ROUND(
                salary / (
                    SELECT AVG(salary)
                    FROM employees
                ),
                2
            ) AS salary_vs_company_average
        FROM employees
        WHERE status = 'ACTIVE'
        ORDER BY salary DESC
        """,
    )

    print_subtitle("Scalar subquery used for a derived metric")

    execute_and_print(
        connection,
        """
        SELECT
            department_name,
            budget,
            ROUND(
                budget / (
                    SELECT SUM(budget)
                    FROM departments
                ) * 100,
                2
            ) AS percentage_of_total_budget
        FROM departments
        ORDER BY percentage_of_total_budget DESC
        """,
    )


def demonstrate_single_row_subqueries(connection: sqlite3.Connection) -> None:
    print_title("3. Single-row subqueries and comparison operators")

    print(
        """
A subquery returning one row can be compared with =, <>, >, >=, <, <=
when its result has one compatible column.

Example:

    WHERE salary > (SELECT AVG(salary) FROM employees)

The operator expects a scalar result.
If the subquery unexpectedly returns multiple rows, behavior depends on the
database system. Some systems reject the query with a cardinality error.
SQLite has some permissive behaviors, so production SQL should make the
expected cardinality explicit.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT employee_name, salary
        FROM employees
        WHERE salary > (
            SELECT salary
            FROM employees
            WHERE employee_name = 'Meera'
        )
        ORDER BY salary DESC
        """,
    )


def demonstrate_in_subquery(connection: sqlite3.Connection) -> None:
    print_title("4. IN and NOT IN subqueries")

    print(
        """
IN is appropriate when the subquery returns a set of values.

The following asks:
Which employees work in departments whose budget exceeds 1,300,000?
"""
    )

    execute_and_print(
        connection,
        """
        SELECT employee_name, department_id
        FROM employees
        WHERE department_id IN (
            SELECT department_id
            FROM departments
            WHERE budget > 1300000
        )
        ORDER BY department_id, employee_name
        """,
    )

    print_subtitle("NOT IN")

    execute_and_print(
        connection,
        """
        SELECT department_name
        FROM departments
        WHERE department_id NOT IN (
            SELECT department_id
            FROM employees
            WHERE status = 'ACTIVE'
        )
        """,
    )

    print(
        """
Important NULL rule:

    x NOT IN (1, 2, NULL)

does not behave like a simple exclusion list. SQL uses three-valued logic:
TRUE, FALSE, and UNKNOWN. The presence of NULL can make comparisons
UNKNOWN.

For anti-joins, NOT EXISTS is often safer when NULLs are possible.
"""
    )


def demonstrate_exists(connection: sqlite3.Connection) -> None:
    print_title("5. EXISTS and NOT EXISTS")

    print(
        """
EXISTS asks whether the subquery produces at least one row.

The actual values returned by SELECT inside EXISTS are not important.

EXISTS is therefore naturally suited to questions such as:
- Does this employee have a sale?
- Does this department have an active project?
- Does this customer have at least one order?

NOT EXISTS asks whether no matching row exists.
"""
    )

    print_subtitle("EXISTS")

    execute_and_print(
        connection,
        """
        SELECT d.department_name
        FROM departments AS d
        WHERE EXISTS (
            SELECT 1
            FROM projects AS p
            WHERE p.department_id = d.department_id
              AND p.status = 'ACTIVE'
        )
        ORDER BY d.department_name
        """,
    )

    print_subtitle("NOT EXISTS")

    execute_and_print(
        connection,
        """
        SELECT e.employee_name
        FROM employees AS e
        WHERE NOT EXISTS (
            SELECT 1
            FROM sales AS s
            WHERE s.employee_id = e.employee_id
        )
        ORDER BY e.employee_name
        """,
    )


# ---------------------------------------------------------------------------
# Correlated subqueries
# ---------------------------------------------------------------------------

def demonstrate_correlated_subqueries(connection: sqlite3.Connection) -> None:
    print_title("6. Correlated subqueries")

    print(
        """
A correlated subquery refers to a column from the outer query.

Example structure:

    SELECT ...
    FROM outer_table AS o
    WHERE o.value > (
        SELECT AVG(i.value)
        FROM inner_table AS i
        WHERE i.group_id = o.group_id
    );

The inner query cannot be evaluated independently because it needs a value
from the current outer row.

Logical processing can be understood as:
1. Consider an outer row.
2. Substitute its correlated values into the subquery.
3. Evaluate the subquery.
4. Apply the outer predicate.
5. Repeat logically for other outer rows.

The optimizer may transform this execution strategy, so "runs once per row"
is a useful conceptual model, not a universal physical execution rule.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT
            e.employee_name,
            d.department_name,
            e.salary
        FROM employees AS e
        JOIN departments AS d
          ON d.department_id = e.department_id
        WHERE e.salary > (
            SELECT AVG(e2.salary)
            FROM employees AS e2
            WHERE e2.department_id = e.department_id
        )
        ORDER BY d.department_name, e.salary DESC
        """,
    )

    print_subtitle("Correlated EXISTS")

    execute_and_print(
        connection,
        """
        SELECT
            d.department_name
        FROM departments AS d
        WHERE EXISTS (
            SELECT 1
            FROM employees AS e
            WHERE e.department_id = d.department_id
              AND e.salary > 120000
        )
        ORDER BY d.department_name
        """,
    )


def demonstrate_top_per_group(connection: sqlite3.Connection) -> None:
    print_title("7. Correlated subquery for top-per-group logic")

    print(
        """
A classic correlated-subquery pattern is:
Return an employee when no employee in the same department has a higher
salary.

This is conceptually different from simply finding the company-wide maximum.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT
            e.employee_name,
            e.department_id,
            e.salary
        FROM employees AS e
        WHERE NOT EXISTS (
            SELECT 1
            FROM employees AS higher
            WHERE higher.department_id = e.department_id
              AND higher.salary > e.salary
        )
        ORDER BY e.department_id, e.employee_name
        """,
    )

    print(
        """
If two employees tie for the highest salary, both can be returned because
the condition asks whether a strictly higher salary exists.

This illustrates why business semantics matter when writing a subquery.
"""


# ---------------------------------------------------------------------------
# Nested and multi-level subqueries
# ---------------------------------------------------------------------------

def demonstrate_nested_subqueries(connection: sqlite3.Connection) -> None:
    print_title("8. Nested subqueries")

    print(
        """
A nested subquery is a subquery contained inside another subquery.

Example reasoning:

    Find employees
      whose department
        belongs to departments
          whose budget is above the average department budget.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT employee_name, department_id, salary
        FROM employees
        WHERE department_id IN (
            SELECT department_id
            FROM departments
            WHERE budget > (
                SELECT AVG(budget)
                FROM departments
            )
        )
        ORDER BY department_id, salary DESC
        """,
    )


def demonstrate_multi_level_subquery(connection: sqlite3.Connection) -> None:
    print_title("9. Multi-level subqueries")

    print(
        """
Multi-level subqueries contain several logical layers.

The following question has multiple levels:

Which employees belong to departments whose active-project budget is greater
than the average active-project budget across departments?

Level 1:
    Calculate each department's active-project budget.

Level 2:
    Calculate the average of those departmental totals.

Level 3:
    Select departments whose total exceeds that average.

Level 4:
    Select employees belonging to those departments.

The nested structure is educationally useful, although a CTE or window
function may make production SQL easier to maintain.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT employee_name, department_id, salary
        FROM employees
        WHERE department_id IN (
            SELECT department_id
            FROM (
                SELECT
                    p.department_id,
                    SUM(p.budget) AS active_project_budget
                FROM projects AS p
                WHERE p.status = 'ACTIVE'
                GROUP BY p.department_id
            ) AS department_totals
            WHERE active_project_budget > (
                SELECT AVG(active_project_budget)
                FROM (
                    SELECT
                        p2.department_id,
                        SUM(p2.budget) AS active_project_budget
                    FROM projects AS p2
                    WHERE p2.status = 'ACTIVE'
                    GROUP BY p2.department_id
                ) AS department_totals_2
            )
        )
        ORDER BY department_id, employee_name
        """,
    )


# ---------------------------------------------------------------------------
# Subqueries in different SQL clauses
# ---------------------------------------------------------------------------

def demonstrate_subqueries_in_clauses(connection: sqlite3.Connection) -> None:
    print_title("10. Subqueries in SELECT, WHERE, FROM, and HAVING")

    print_subtitle("Subquery in SELECT")

    execute_and_print(
        connection,
        """
        SELECT
            d.department_name,
            (
                SELECT COUNT(*)
                FROM employees AS e
                WHERE e.department_id = d.department_id
            ) AS employee_count
        FROM departments AS d
        ORDER BY employee_count DESC
        """,
    )

    print_subtitle("Subquery in WHERE")

    execute_and_print(
        connection,
        """
        SELECT employee_name, salary
        FROM employees
        WHERE salary > (
            SELECT AVG(salary)
            FROM employees
        )
        ORDER BY salary DESC
        """,
    )

    print_subtitle("Subquery in FROM: derived table")

    execute_and_print(
        connection,
        """
        SELECT
            department_name,
            employee_count,
            average_salary
        FROM (
            SELECT
                d.department_id,
                d.department_name,
                COUNT(e.employee_id) AS employee_count,
                ROUND(AVG(e.salary), 2) AS average_salary
            FROM departments AS d
            LEFT JOIN employees AS e
              ON e.department_id = d.department_id
             AND e.status = 'ACTIVE'
            GROUP BY d.department_id, d.department_name
        ) AS department_metrics
        WHERE employee_count >= 2
        ORDER BY average_salary DESC
        """,
    )

    print_subtitle("Subquery in HAVING")

    execute_and_print(
        connection,
        """
        SELECT
            department_id,
            AVG(salary) AS average_salary
        FROM employees
        GROUP BY department_id
        HAVING AVG(salary) > (
            SELECT AVG(salary)
            FROM employees
        )
        ORDER BY average_salary DESC
        """,
    )


# ---------------------------------------------------------------------------
# Aggregate subqueries and practical reporting
# ---------------------------------------------------------------------------

def demonstrate_aggregate_subqueries(connection: sqlite3.Connection) -> None:
    print_title("11. Aggregate subqueries")

    print(
        """
Aggregate subqueries are particularly useful when a query needs a reference
value calculated from a broader population.

Common aggregate functions:
COUNT, SUM, AVG, MIN, MAX.

The outer query can compare individual rows or grouped results against that
reference value.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT
            employee_name,
            salary,
            ROUND(
                salary - (
                    SELECT AVG(salary)
                    FROM employees
                ),
                2
            ) AS difference_from_company_average
        FROM employees
        ORDER BY difference_from_company_average DESC
        """,
    )

    print_subtitle("Department average compared with company average")

    execute_and_print(
        connection,
        """
        SELECT
            d.department_name,
            ROUND(AVG(e.salary), 2) AS department_average,
            ROUND(
                (
                    SELECT AVG(salary)
                    FROM employees
                ),
                2
            ) AS company_average
        FROM departments AS d
        JOIN employees AS e
          ON e.department_id = d.department_id
        GROUP BY d.department_id, d.department_name
        ORDER BY department_average DESC
        """,
    )


# ---------------------------------------------------------------------------
# ANY, ALL, and database portability
# ---------------------------------------------------------------------------

def demonstrate_comparison_semantics(connection: sqlite3.Connection) -> None:
    print_title("12. Comparison operators and portability")

    print(
        """
Some SQL systems support quantified comparisons such as:

    value > ALL (subquery)
    value > ANY (subquery)

SQLite does not implement these PostgreSQL/SQL-standard-style constructs in
the same syntax.

Equivalent logic can often be expressed using aggregates.

Example:

    salary > ALL (salaries in department X)

can often be represented as:

    salary > (SELECT MAX(salary) ...)

Likewise:

    salary > ANY (salaries in department X)

can often be represented as:

    salary > (SELECT MIN(salary) ...)

provided the empty-set and NULL semantics are understood.

A portable implementation using MAX is demonstrated below.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT employee_name, salary
        FROM employees
        WHERE salary > (
            SELECT MAX(salary)
            FROM employees
            WHERE department_id = 1
        )
        ORDER BY salary DESC
        """,
    )


# ---------------------------------------------------------------------------
# NULL behavior
# ---------------------------------------------------------------------------

def demonstrate_null_edge_cases(connection: sqlite3.Connection) -> None:
    print_title("13. NULL and subquery edge cases")

    print(
        """
NULL is not an ordinary value.

The expression:

    NULL = NULL

does not evaluate to TRUE. It evaluates to UNKNOWN.

This matters especially for NOT IN.

A robust anti-existence pattern is frequently:

    WHERE NOT EXISTS (
        SELECT 1
        ...
    )

rather than:

    WHERE key NOT IN (
        SELECT key
        ...
    )

when the subquery could contain NULL.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT employee_name
        FROM employees AS e
        WHERE NOT EXISTS (
            SELECT 1
            FROM performance_reviews AS r
            WHERE r.employee_id = e.employee_id
        )
        ORDER BY employee_name
        """,
    )

    print_subtitle("COALESCE can provide an explicit fallback")

    execute_and_print(
        connection,
        """
        SELECT
            e.employee_name,
            COALESCE(
                (
                    SELECT MAX(r.score)
                    FROM performance_reviews AS r
                    WHERE r.employee_id = e.employee_id
                ),
                0
            ) AS latest_available_score
        FROM employees AS e
        ORDER BY latest_available_score DESC
        """,
    )


# ---------------------------------------------------------------------------
# Comparison with joins
# ---------------------------------------------------------------------------

def demonstrate_subquery_vs_join(connection: sqlite3.Connection) -> None:
    print_title("14. Subquery versus JOIN")

    print(
        """
Many subqueries can be rewritten as joins.

Subquery style:
    Filter employees using a department condition.

JOIN style:
    Join employees to departments and filter directly.

Neither form is universally faster. The optimizer, indexes, database
engine, cardinality, statistics, and exact query shape determine performance.

Use the form that expresses the business relationship clearly, then inspect
the actual query plan for important production queries.
"""
    )

    print_subtitle("Subquery version")

    subquery_sql = """
        SELECT e.employee_name, e.salary
        FROM employees AS e
        WHERE e.department_id IN (
            SELECT d.department_id
            FROM departments AS d
            WHERE d.budget > 1300000
        )
        ORDER BY e.salary DESC
    """

    execute_and_print(connection, subquery_sql)

    print_subtitle("JOIN version")

    join_sql = """
        SELECT e.employee_name, e.salary
        FROM employees AS e
        JOIN departments AS d
          ON d.department_id = e.department_id
        WHERE d.budget > 1300000
        ORDER BY e.salary DESC
    """

    execute_and_print(connection, join_sql)


# ---------------------------------------------------------------------------
# EXISTS versus IN
# ---------------------------------------------------------------------------

def demonstrate_exists_vs_in(connection: sqlite3.Connection) -> None:
    print_title("15. EXISTS versus IN")

    print(
        """
IN generally asks:

    Is this value contained in the set returned by the subquery?

EXISTS generally asks:

    Does at least one related row exist?

For a simple non-NULL primary-key relationship, both can often express the
same result.

EXISTS becomes particularly expressive when the matching condition contains
multiple correlated predicates.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT employee_name
        FROM employees
        WHERE department_id IN (
            SELECT department_id
            FROM departments
            WHERE location IN ('Bengaluru', 'Hyderabad')
        )
        ORDER BY employee_name
        """,
    )

    execute_and_print(
        connection,
        """
        SELECT e.employee_name
        FROM employees AS e
        WHERE EXISTS (
            SELECT 1
            FROM departments AS d
            WHERE d.department_id = e.department_id
              AND d.location IN ('Bengaluru', 'Hyderabad')
        )
        ORDER BY e.employee_name
        """,
    )


# ---------------------------------------------------------------------------
# Advanced reporting case study
# ---------------------------------------------------------------------------

def demonstrate_advanced_case_study(connection: sqlite3.Connection) -> None:
    print_title("16. Advanced case study: performance and sales intelligence")

    print(
        """
Business requirement:

Identify active employees who:
1. earn above their department's average salary,
2. have at least one sale,
3. have a performance score above the company-wide average review score,
4. and belong to a department with at least one active project.

This combines:
- a correlated scalar subquery,
- an EXISTS subquery,
- another scalar aggregate subquery,
- a correlated EXISTS,
- multiple business constraints.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT
            e.employee_name,
            d.department_name,
            e.salary,
            ROUND(
                (
                    SELECT AVG(e2.salary)
                    FROM employees AS e2
                    WHERE e2.department_id = e.department_id
                      AND e2.status = 'ACTIVE'
                ),
                2
            ) AS department_average_salary
        FROM employees AS e
        JOIN departments AS d
          ON d.department_id = e.department_id
        WHERE e.status = 'ACTIVE'
          AND e.salary > (
              SELECT AVG(e2.salary)
              FROM employees AS e2
              WHERE e2.department_id = e.department_id
                AND e2.status = 'ACTIVE'
          )
          AND EXISTS (
              SELECT 1
              FROM sales AS s
              WHERE s.employee_id = e.employee_id
          )
          AND (
              SELECT MAX(r.score)
              FROM performance_reviews AS r
              WHERE r.employee_id = e.employee_id
          ) > (
              SELECT AVG(score)
              FROM performance_reviews
          )
          AND EXISTS (
              SELECT 1
              FROM projects AS p
              WHERE p.department_id = e.department_id
                AND p.status = 'ACTIVE'
          )
        ORDER BY e.salary DESC
        """,
    )


# ---------------------------------------------------------------------------
# Multi-level business query with derived tables
# ---------------------------------------------------------------------------

def demonstrate_multilevel_business_query(
    connection: sqlite3.Connection,
) -> None:
    print_title("17. Multi-level department intelligence")

    print(
        """
Goal:

Find departments whose:
- active employee count is above the average active employee count per
  department, and
- total sales are above the average department sales.

The query uses derived tables and scalar subqueries to separate the
calculation layers.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT
            department_name,
            active_employee_count,
            total_sales
        FROM (
            SELECT
                d.department_id,
                d.department_name,
                (
                    SELECT COUNT(*)
                    FROM employees AS e
                    WHERE e.department_id = d.department_id
                      AND e.status = 'ACTIVE'
                ) AS active_employee_count,
                COALESCE(
                    (
                        SELECT SUM(s.amount)
                        FROM sales AS s
                        JOIN employees AS es
                          ON es.employee_id = s.employee_id
                        WHERE es.department_id = d.department_id
                    ),
                    0
                ) AS total_sales
            FROM departments AS d
        ) AS department_metrics
        WHERE active_employee_count > (
            SELECT AVG(active_employee_count)
            FROM (
                SELECT
                    d2.department_id,
                    (
                        SELECT COUNT(*)
                        FROM employees AS e2
                        WHERE e2.department_id = d2.department_id
                          AND e2.status = 'ACTIVE'
                    ) AS active_employee_count
                FROM departments AS d2
            ) AS employee_metrics
        )
        AND total_sales > (
            SELECT AVG(total_sales)
            FROM (
                SELECT
                    d3.department_id,
                    COALESCE(
                        (
                            SELECT SUM(s3.amount)
                            FROM sales AS s3
                            JOIN employees AS e3
                              ON e3.employee_id = s3.employee_id
                            WHERE e3.department_id = d3.department_id
                        ),
                        0
                    ) AS total_sales
                FROM departments AS d3
            ) AS sales_metrics
        )
        ORDER BY total_sales DESC
        """,
    )


# ---------------------------------------------------------------------------
# Safe parameterized subqueries
# ---------------------------------------------------------------------------

def demonstrate_parameterized_queries(
    connection: sqlite3.Connection,
) -> None:
    print_title("18. Security: parameterized subqueries")

    print(
        """
Do not construct SQL by concatenating untrusted user input.

Unsafe pattern:

    "... WHERE salary > " + user_value

Safe pattern:

    "... WHERE salary > ?" with a separate parameter

The database driver treats the parameter as data rather than SQL syntax.
"""
    )

    minimum_salary = 100000

    execute_and_print(
        connection,
        """
        SELECT employee_name, salary
        FROM employees
        WHERE salary > (
            SELECT AVG(salary)
            FROM employees
            WHERE salary >= ?
        )
        ORDER BY salary DESC
        """,
        (minimum_salary,),
    )


# ---------------------------------------------------------------------------
# Query plan and performance
# ---------------------------------------------------------------------------

def demonstrate_performance(connection: sqlite3.Connection) -> None:
    print_title("19. Performance and query plans")

    sql = """
        SELECT
            e.employee_name,
            e.salary
        FROM employees AS e
        WHERE e.salary > (
            SELECT AVG(e2.salary)
            FROM employees AS e2
            WHERE e2.department_id = e.department_id
        )
        ORDER BY e.salary DESC
    """

    execute_and_print(connection, sql)
    explain_query_plan(connection, sql)

    print(
        """
Performance considerations:

1. Correlated subqueries can be expensive when the inner relationship is
   evaluated for many outer rows.

2. Indexes on correlated columns can substantially reduce lookup work.

3. A JOIN, CTE, derived table, window function, or pre-aggregation may be
   clearer or faster for some workloads.

4. Scalar subqueries that return the same global aggregate for every row may
   be optimized by the database, but this should not be assumed blindly.

5. Always benchmark representative data.

6. Query plans are database-engine-specific.

7. Indexes have costs: storage, write overhead, maintenance, and optimizer
   complexity.

For large analytical workloads, window functions often express per-group
comparisons more directly than correlated subqueries.
"""
    )


def demonstrate_window_function_alternative(
    connection: sqlite3.Connection,
) -> None:
    print_title("20. Advanced alternative: window functions")

    print(
        """
The following window-function query produces the same conceptual result as
the correlated department-average salary query.

The window function computes the department average while retaining each
employee row.

This is often easier to read when the goal is to compare each row against a
group statistic.
"""
    )

    execute_and_print(
        connection,
        """
        SELECT
            employee_name,
            department_id,
            salary,
            ROUND(
                AVG(salary) OVER (PARTITION BY department_id),
                2
            ) AS department_average
        FROM employees
        WHERE status = 'ACTIVE'
        ORDER BY department_id, salary DESC
        """,
    )


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

@dataclass
class QueryTest:
    name: str
    sql: str
    expected_minimum_rows: int


def run_query_tests(connection: sqlite3.Connection) -> None:
    print_title("21. Automated correctness checks")

    tests = [
        QueryTest(
            "Employees above company average",
            """
            SELECT employee_id
            FROM employees
            WHERE salary > (
                SELECT AVG(salary)
                FROM employees
            )
            """,
            1,
        ),
        QueryTest(
            "Departments with active projects",
            """
            SELECT department_id
            FROM departments AS d
            WHERE EXISTS (
                SELECT 1
                FROM projects AS p
                WHERE p.department_id = d.department_id
                  AND p.status = 'ACTIVE'
            )
            """,
            1,
        ),
        QueryTest(
            "Employees above department average",
            """
            SELECT e.employee_id
            FROM employees AS e
            WHERE e.salary > (
                SELECT AVG(e2.salary)
                FROM employees AS e2
                WHERE e2.department_id = e.department_id
            )
            """,
            1,
        ),
    ]

    passed = 0

    for test in tests:
        rows = connection.execute(test.sql).fetchall()

        if len(rows) >= test.expected_minimum_rows:
            print(f"PASS: {test.name}")
            passed += 1
        else:
            print(
                f"FAIL: {test.name} "
                f"(expected at least {test.expected_minimum_rows} rows)"
            )

    print(f"\n{passed}/{len(tests)} tests passed.")


# ---------------------------------------------------------------------------
# Error handling demonstration
# ---------------------------------------------------------------------------

def demonstrate_error_handling(connection: sqlite3.Connection) -> None:
    print_title("22. Error handling and cardinality awareness")

    print(
        """
Subqueries must return a shape compatible with the surrounding operator.

Examples:
- A scalar comparison expects one value.
- IN expects one column.
- EXISTS cares about row existence.
- A derived table may return multiple columns and rows.

A production application should catch database exceptions at an appropriate
boundary and log enough information to diagnose the failure without exposing
sensitive SQL parameters.
"""
    )

    invalid_sql = """
        SELECT employee_name
        FROM employees
        WHERE salary = (
            SELECT salary, employee_id
            FROM employees
            LIMIT 1
        )
    """

    try:
        connection.execute(invalid_sql).fetchall()
    except sqlite3.Error as error:
        print("Expected SQL error captured:")
        print(error)


# ---------------------------------------------------------------------------
# Main educational sequence
# ---------------------------------------------------------------------------

def main() -> None:
    print_title("SQL SUBQUERIES: FROM FUNDAMENTALS TO ADVANCED PRACTICE")

    connection = create_database()

    try:
        demonstrate_basic_subquery(connection)
        demonstrate_scalar_subquery(connection)
        demonstrate_single_row_subqueries(connection)
        demonstrate_in_subquery(connection)
        demonstrate_exists(connection)
        demonstrate_correlated_subqueries(connection)
        demonstrate_top_per_group(connection)
        demonstrate_nested_subqueries(connection)
        demonstrate_multi_level_subquery(connection)
        demonstrate_subqueries_in_clauses(connection)
        demonstrate_aggregate_subqueries(connection)
        demonstrate_comparison_semantics(connection)
        demonstrate_null_edge_cases(connection)
        demonstrate_subquery_vs_join(connection)
        demonstrate_exists_vs_in(connection)
        demonstrate_advanced_case_study(connection)
        demonstrate_multilevel_business_query(connection)
        demonstrate_parameterized_queries(connection)
        demonstrate_performance(connection)
        demonstrate_window_function_alternative(connection)
        run_query_tests(connection)
        demonstrate_error_handling(connection)

        print_title("23. Key rules demonstrated by executable examples")

        print(
            """
1. Use a scalar subquery when one value is required.
2. Use IN when comparing against a one-column set.
3. Use EXISTS when the question is whether matching rows exist.
4. Use NOT EXISTS for robust anti-existence logic, especially when NULLs
   could make NOT IN surprising.
5. Use correlated subqueries when the inner calculation depends on the
   current outer row.
6. Nested subqueries can create multiple logical levels.
7. Derived tables turn subquery results into relational inputs.
8. Subqueries can appear in several SQL clauses.
9. A JOIN or window function can often replace a subquery.
10. The clearest formulation depends on the relationship being expressed.
11. NULL introduces three-valued logic and must be handled deliberately.
12. Parameterized queries are essential when external input is involved.
13. Performance should be validated with realistic data and query plans.
14. SQL syntax and optimizer behavior vary between database engines.
"""
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
