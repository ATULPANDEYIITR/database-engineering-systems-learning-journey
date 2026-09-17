```python
"""
SQL Joins II: FULL JOIN, CROSS JOIN, and SELF JOIN

A self-contained study program demonstrating:
- Relational concepts behind joins
- INNER JOIN as a reference point
- FULL OUTER JOIN
- CROSS JOIN
- SELF JOIN
- Join predicates and NULL behavior
- Duplicate rows and cardinality
- Anti-join and semi-join patterns
- Multiple joins
- Aggregation after joins
- Recursive relationships
- Validation and edge cases
- Query-planning and performance concepts
- Security and production considerations

The examples use SQLite because it is included with Python.
SQLite does not implement FULL OUTER JOIN in older versions, so the
script includes both native FULL OUTER JOIN detection and a portable
UNION-based implementation.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def create_connection() -> sqlite3.Connection:
    """Create an in-memory database for repeatable demonstrations."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    """Create a small business database with intentionally varied data."""
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE departments (
            department_id INTEGER PRIMARY KEY,
            department_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY,
            employee_name TEXT NOT NULL,
            manager_id INTEGER,
            department_id INTEGER,
            salary REAL NOT NULL CHECK (salary >= 0),
            FOREIGN KEY (manager_id) REFERENCES employees(employee_id),
            FOREIGN KEY (department_id) REFERENCES departments(department_id)
        );

        CREATE TABLE projects (
            project_id INTEGER PRIMARY KEY,
            project_name TEXT NOT NULL,
            department_id INTEGER,
            FOREIGN KEY (department_id) REFERENCES departments(department_id)
        );

        CREATE TABLE employee_projects (
            employee_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            allocation_percent INTEGER NOT NULL CHECK (
                allocation_percent BETWEEN 1 AND 100
            ),
            PRIMARY KEY (employee_id, project_id),
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            order_amount REAL NOT NULL CHECK (order_amount >= 0),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );
        """
    )


def seed_data(connection: sqlite3.Connection) -> None:
    """Insert data designed to expose join edge cases."""
    connection.executemany(
        "INSERT INTO departments VALUES (?, ?)",
        [
            (10, "Engineering"),
            (20, "Finance"),
            (30, "Security"),
            (40, "Research"),
            (50, "Legal"),
        ],
    )

    connection.executemany(
        """
        INSERT INTO employees
            (employee_id, employee_name, manager_id, department_id, salary)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (1, "Asha", None, 10, 125000),
            (2, "Bharat", 1, 10, 95000),
            (3, "Chen", 1, 10, 98000),
            (4, "Divya", None, 20, 110000),
            (5, "Ethan", 4, 20, 88000),
            (6, "Fatima", None, 30, 118000),
            (7, "Gopal", 6, 30, 90000),
            (8, "Hina", None, None, 76000),
        ],
    )

    connection.executemany(
        "INSERT INTO projects VALUES (?, ?, ?)",
        [
            (100, "Payment Platform", 10),
            (200, "Audit Automation", 20),
            (300, "Threat Detection", 30),
            (400, "Independent Research", 40),
        ],
    )

    connection.executemany(
        "INSERT INTO employee_projects VALUES (?, ?, ?)",
        [
            (1, 100, 50),
            (2, 100, 100),
            (4, 200, 60),
            (6, 300, 70),
            (7, 300, 30),
        ],
    )

    connection.executemany(
        "INSERT INTO customers VALUES (?, ?)",
        [
            (1, "Alpha"),
            (2, "Beta"),
            (3, "Gamma"),
            (4, "Delta"),
        ],
    )

    connection.executemany(
        "INSERT INTO orders VALUES (?, ?, ?)",
        [
            (101, 1, 500.00),
            (102, 1, 250.00),
            (103, 2, 900.00),
            (104, None, 120.00),
        ],
    )


# ---------------------------------------------------------------------------
# Generic output helpers
# ---------------------------------------------------------------------------

def print_rows(title: str, rows: Iterable[sqlite3.Row]) -> None:
    """Print query results without requiring a third-party table package."""
    rows = list(rows)
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")

    if not rows:
        print("(no rows)")
        return

    column_names = rows[0].keys()
    print(" | ".join(column_names))
    print("-" * 78)

    for row in rows:
        values = []
        for column in column_names:
            value = row[column]
            values.append("NULL" if value is None else str(value))
        print(" | ".join(values))


def execute(connection: sqlite3.Connection, title: str, query: str) -> None:
    """Execute a SELECT statement and display its result."""
    rows = connection.execute(query).fetchall()
    print_rows(title, rows)


# ---------------------------------------------------------------------------
# Fundamental concept: join cardinality
# ---------------------------------------------------------------------------

def explain_cardinality() -> None:
    print(
        """
JOIN cardinality describes how many output rows can be produced from
matching rows on the left and right sides.

For a one-to-one relationship:
    one left row -> at most one right row

For one-to-many:
    one left row -> many right rows

For many-to-many:
    one left row -> many right rows
    and each right row -> many left rows

A join does not inherently mean "one row in, one row out".
The relationship determines the number of output rows.
"""
    )


# ---------------------------------------------------------------------------
# INNER JOIN reference point
# ---------------------------------------------------------------------------

def demonstrate_inner_join(connection: sqlite3.Connection) -> None:
    execute(
        connection,
        "INNER JOIN: employees matched to departments",
        """
        SELECT
            e.employee_name,
            d.department_name
        FROM employees AS e
        INNER JOIN departments AS d
            ON e.department_id = d.department_id
        ORDER BY e.employee_id;
        """,
    )

    print(
        """
INNER JOIN returns only rows satisfying the join condition.

Hina has no department, so Hina is absent.
Research and Legal have no employees, so they are absent.
"""
    )


# ---------------------------------------------------------------------------
# FULL OUTER JOIN
# ---------------------------------------------------------------------------

def full_outer_join_portable(
    connection: sqlite3.Connection,
) -> list[sqlite3.Row]:
    """
    Portable FULL OUTER JOIN construction.

    LEFT JOIN returns:
        every left row + matching right rows

    The second LEFT JOIN, restricted to unmatched right rows, supplies:
        right rows having no left match

    UNION removes duplicate complete rows.
    """
    query = """
        SELECT
            d.department_id,
            d.department_name,
            e.employee_id,
            e.employee_name
        FROM departments AS d
        LEFT JOIN employees AS e
            ON d.department_id = e.department_id

        UNION

        SELECT
            d.department_id,
            d.department_name,
            e.employee_id,
            e.employee_name
        FROM employees AS e
        LEFT JOIN departments AS d
            ON e.department_id = d.department_id
        WHERE d.department_id IS NULL

        ORDER BY department_id, employee_id;
    """
    return connection.execute(query).fetchall()


def demonstrate_full_join(connection: sqlite3.Connection) -> None:
    print_rows(
        "FULL OUTER JOIN using a portable UNION construction",
        full_outer_join_portable(connection),
    )

    # Modern SQLite versions support FULL OUTER JOIN directly.
    try:
        rows = connection.execute(
            """
            SELECT
                d.department_id,
                d.department_name,
                e.employee_id,
                e.employee_name
            FROM departments AS d
            FULL OUTER JOIN employees AS e
                ON d.department_id = e.department_id
            ORDER BY d.department_id, e.employee_id;
            """
        ).fetchall()

        print_rows(
            "Native FULL OUTER JOIN when supported by the SQLite version",
            rows,
        )
    except sqlite3.OperationalError as error:
        print("\nNative FULL OUTER JOIN unavailable:", error)

    print(
        """
FULL OUTER JOIN preserves unmatched rows from BOTH sides.

This makes it useful for reconciliation:
- records existing in both datasets
- records existing only on the left
- records existing only on the right

A NULL on one side means that no matching row existed on that side.
"""
    )


# ---------------------------------------------------------------------------
# FULL JOIN with classification
# ---------------------------------------------------------------------------

def demonstrate_full_join_classification(connection: sqlite3.Connection) -> None:
    query = """
        SELECT
            d.department_name,
            e.employee_name,
            CASE
                WHEN d.department_id IS NULL THEN 'employee_without_department'
                WHEN e.employee_id IS NULL THEN 'department_without_employee'
                ELSE 'matched'
            END AS relationship_status
        FROM departments AS d
        FULL OUTER JOIN employees AS e
            ON d.department_id = e.department_id
        ORDER BY relationship_status, d.department_id, e.employee_id;
    """

    try:
        execute(
            connection,
            "FULL JOIN classified as matched / left-only / right-only",
            query,
        )
    except sqlite3.OperationalError:
        print_rows(
            "FULL JOIN classification using portable logic",
            connection.execute(
                """
                SELECT
                    d.department_name,
                    e.employee_name,
                    CASE
                        WHEN d.department_id IS NULL
                            THEN 'employee_without_department'
                        WHEN e.employee_id IS NULL
                            THEN 'department_without_employee'
                        ELSE 'matched'
                    END AS relationship_status
                FROM departments d
                LEFT JOIN employees e
                    ON d.department_id = e.department_id

                UNION ALL

                SELECT
                    d.department_name,
                    e.employee_name,
                    'department_without_employee'
                FROM employees e
                LEFT JOIN departments d
                    ON e.department_id = d.department_id
                WHERE d.department_id IS NULL;
                """
            ).fetchall(),
        )


# ---------------------------------------------------------------------------
# CROSS JOIN
# ---------------------------------------------------------------------------

def demonstrate_cross_join(connection: sqlite3.Connection) -> None:
    execute(
        connection,
        "CROSS JOIN: every selected employee paired with every project",
        """
        SELECT
            e.employee_name,
            p.project_name
        FROM employees AS e
        CROSS JOIN projects AS p
        WHERE e.employee_id <= 2
        ORDER BY e.employee_id, p.project_id;
        """,
    )

    print(
        """
CROSS JOIN has no matching predicate.

If relation A has m rows and relation B has n rows,
the Cartesian product contains m × n rows.

Example:
    2 employees × 4 projects = 8 combinations

This can be intentional for:
- scenario generation
- test matrices
- schedules
- product combinations
- date/time grids

It can also be dangerous when accidentally produced by an incomplete join.
"""
    )


def demonstrate_cross_join_filter(connection: sqlite3.Connection) -> None:
    execute(
        connection,
        "CROSS JOIN followed by a filter",
        """
        SELECT
            e.employee_name,
            p.project_name,
            d.department_name
        FROM employees AS e
        CROSS JOIN projects AS p
        LEFT JOIN departments AS d
            ON p.department_id = d.department_id
        WHERE e.department_id = p.department_id
        ORDER BY e.employee_id, p.project_id;
        """,
    )

    print(
        """
A CROSS JOIN followed by WHERE can resemble a filtered Cartesian product.

For readability, a normal INNER JOIN is generally preferable when the
relationship itself is the main concept. CROSS JOIN communicates that
the Cartesian product is intentional.
"""
    )


# ---------------------------------------------------------------------------
# SELF JOIN
# ---------------------------------------------------------------------------

def demonstrate_self_join(connection: sqlite3.Connection) -> None:
    execute(
        connection,
        "SELF JOIN: employee to manager",
        """
        SELECT
            employee.employee_name AS employee,
            manager.employee_name AS manager
        FROM employees AS employee
        LEFT JOIN employees AS manager
            ON employee.manager_id = manager.employee_id
        ORDER BY employee.employee_id;
        """,
    )

    print(
        """
A SELF JOIN joins a table to itself.

The aliases are essential because the same table participates twice:
    employee
    manager

The table is not physically copied. SQL exposes two logical references
to the same relation.
"""
    )


def demonstrate_self_join_peer_pairs(connection: sqlite3.Connection) -> None:
    execute(
        connection,
        "SELF JOIN: employees in the same department",
        """
        SELECT
            a.employee_name AS employee_a,
            b.employee_name AS employee_b,
            a.department_id
        FROM employees AS a
        INNER JOIN employees AS b
            ON a.department_id = b.department_id
           AND a.employee_id < b.employee_id
        ORDER BY a.department_id, a.employee_id, b.employee_id;
        """,
    )

    print(
        """
The condition a.employee_id < b.employee_id prevents:
    A,B and B,A

It also prevents:
    A,A

Without this constraint, a self join used for pair generation can
produce symmetric duplicates and self-pairs.
"""
    )


# ---------------------------------------------------------------------------
# NULL and three-valued logic
# ---------------------------------------------------------------------------

def demonstrate_null_behavior(connection: sqlite3.Connection) -> None:
    execute(
        connection,
        "NULL does not equal NULL in ordinary SQL equality",
        """
        SELECT
            employee_name,
            department_id,
            department_id = NULL AS equality_test,
            department_id IS NULL AS is_null_test
        FROM employees
        WHERE employee_name = 'Hina';
        """,
    )

    print(
        """
SQL uses three-valued logic:
    TRUE
    FALSE
    UNKNOWN

The expression:
    department_id = NULL

does not evaluate to TRUE.

Use:
    department_id IS NULL
or:
    department_id IS NOT NULL

This matters heavily when interpreting outer-join results.
"""
    )


# ---------------------------------------------------------------------------
# WHERE versus ON with outer joins
# ---------------------------------------------------------------------------

def demonstrate_on_vs_where(connection: sqlite3.Connection) -> None:
    execute(
        connection,
        "Condition in ON: preserves departments without employees",
        """
        SELECT
            d.department_name,
            e.employee_name
        FROM departments AS d
        LEFT JOIN employees AS e
            ON d.department_id = e.department_id
           AND e.salary >= 100000
        ORDER BY d.department_id, e.employee_id;
        """,
    )

    execute(
        connection,
        "Condition in WHERE: removes NULL-extended departments",
        """
        SELECT
            d.department_name,
            e.employee_name
        FROM departments AS d
        LEFT JOIN employees AS e
            ON d.department_id = e.department_id
        WHERE e.salary >= 100000
        ORDER BY d.department_id, e.employee_id;
        """,
    )

    print(
        """
For an outer join, moving a condition between ON and WHERE can change
the result set.

ON controls which right-side rows qualify as matches.
WHERE filters the result after the join has produced rows.

A WHERE predicate referencing the nullable outer side can effectively
turn a LEFT JOIN into an INNER-like result for that condition.
"""
    )


# ---------------------------------------------------------------------------
# Many-to-many joins
# ---------------------------------------------------------------------------

def demonstrate_many_to_many(connection: sqlite3.Connection) -> None:
    execute(
        connection,
        "Many-to-many relationship through a junction table",
        """
        SELECT
            e.employee_name,
            p.project_name,
            ep.allocation_percent
        FROM employee_projects AS ep
        INNER JOIN employees AS e
            ON ep.employee_id = e.employee_id
        INNER JOIN projects AS p
            ON ep.project_id = p.project_id
        ORDER BY e.employee_id, p.project_id;
        """,
    )

    print(
        """
employee_projects is a junction table.

Instead of storing multiple project IDs in employees, each employee/project
relationship gets its own row.

This normalized structure allows:
    employee -> many projects
    project  -> many employees

The join therefore exposes relationship rows rather than duplicating
project information inside the employee table.
"""
    )


# ---------------------------------------------------------------------------
# Aggregation after joins
# ---------------------------------------------------------------------------

def demonstrate_aggregation(connection: sqlite3.Connection) -> None:
    execute(
        connection,
        "LEFT JOIN with aggregation: include departments with zero employees",
        """
        SELECT
            d.department_name,
            COUNT(e.employee_id) AS employee_count,
            COALESCE(AVG(e.salary), 0) AS average_salary
        FROM departments AS d
        LEFT JOIN employees AS e
            ON d.department_id = e.department_id
        GROUP BY d.department_id, d.department_name
        ORDER BY d.department_id;
        """,
    )

    print(
        """
COUNT(e.employee_id) is preferable to COUNT(*) here.

For a department with no matching employee:
    COUNT(e.employee_id) = 0
    COUNT(*) = 1

The outer join still produces a NULL-extended row, and COUNT(*) counts
that row. COUNT(column) ignores NULL values.
"""
    )


# ---------------------------------------------------------------------------
# Reconciliation pattern
# ---------------------------------------------------------------------------

def demonstrate_reconciliation(connection: sqlite3.Connection) -> None:
    """
    Compare customers and orders to find:
    - customers with orders
    - customers without orders
    - orders without a valid customer
    """
    execute(
        connection,
        "Reconciliation using FULL JOIN",
        """
        SELECT
            c.customer_id,
            c.customer_name,
            o.order_id,
            o.order_amount,
            CASE
                WHEN c.customer_id IS NULL THEN 'orphan_order'
                WHEN o.order_id IS NULL THEN 'customer_without_order'
                ELSE 'matched'
            END AS status
        FROM customers AS c
        FULL OUTER JOIN orders AS o
            ON c.customer_id = o.customer_id
        ORDER BY status, c.customer_id, o.order_id;
        """,
    )


# ---------------------------------------------------------------------------
# Semi-join and anti-join concepts
# ---------------------------------------------------------------------------

def demonstrate_semi_and_anti_join(connection: sqlite3.Connection) -> None:
    execute(
        connection,
        "Semi-join pattern: departments having at least one employee",
        """
        SELECT
            d.department_name
        FROM departments AS d
        WHERE EXISTS (
            SELECT 1
            FROM employees AS e
            WHERE e.department_id = d.department_id
        )
        ORDER BY d.department_id;
        """,
    )

    execute(
        connection,
        "Anti-join pattern: departments having no employees",
        """
        SELECT
            d.department_name
        FROM departments AS d
        WHERE NOT EXISTS (
            SELECT 1
            FROM employees AS e
            WHERE e.department_id = d.department_id
        )
        ORDER BY d.department_id;
        """,
    )

    print(
        """
A semi-join returns left rows for which a matching right row exists,
without duplicating the left row for every match.

An anti-join returns left rows for which no matching right row exists.

EXISTS and NOT EXISTS are explicit ways to express these intentions.
"""
    )


# ---------------------------------------------------------------------------
# Join using composite keys
# ---------------------------------------------------------------------------

def demonstrate_composite_key_concept() -> None:
    print(
        """
Composite join keys use multiple columns.

Example:

    SELECT ...
    FROM table_a AS a
    JOIN table_b AS b
      ON a.company_id = b.company_id
     AND a.account_id = b.account_id;

Joining on only one component can create incorrect matches.

The join predicate should identify the intended relationship, not merely
a column that happens to have similar values.
"""
    )


# ---------------------------------------------------------------------------
# Dynamic SQL security
# ---------------------------------------------------------------------------

def demonstrate_parameterized_sql(connection: sqlite3.Connection) -> None:
    minimum_salary = 100000

    rows = connection.execute(
        """
        SELECT employee_name, salary
        FROM employees
        WHERE salary >= ?
        ORDER BY salary DESC;
        """,
        (minimum_salary,),
    ).fetchall()

    print_rows(
        "Parameterized query for safe value binding",
        rows,
    )

    print(
        """
Never construct SQL values by directly concatenating untrusted strings.

Prefer parameter binding:
    WHERE salary >= ?

with:
    connection.execute(query, (value,))

Parameters protect values from being interpreted as SQL syntax.
Identifiers such as table names generally require a different strategy:
they should be selected from a trusted allowlist rather than passed as
ordinary value parameters.
"""
    )


# ---------------------------------------------------------------------------
# Explain query plans
# ---------------------------------------------------------------------------

def demonstrate_query_plan(connection: sqlite3.Connection) -> None:
    print_rows(
        "SQLite query plan for an indexed join",
        connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT
                e.employee_name,
                d.department_name
            FROM employees AS e
            JOIN departments AS d
                ON e.department_id = d.department_id
            WHERE d.department_id = 10;
            """
        ).fetchall(),
    )

    print(
        """
Query planners may choose algorithms such as:
- nested-loop joins
- index-assisted lookups
- hash joins
- merge joins

The exact algorithms depend on the database engine and available indexes.

Indexes can reduce lookup work, but they also consume storage and increase
write/update overhead. The useful index depends on data distribution and
query patterns.
"""
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def demonstrate_edge_cases(connection: sqlite3.Connection) -> None:
    execute(
        connection,
        "Edge case: NULL department",
        """
        SELECT
            employee_name,
            department_id
        FROM employees
        WHERE department_id IS NULL;
        """,
    )

    execute(
        connection,
        "Edge case: departments with no employees",
        """
        SELECT
            d.department_name
        FROM departments AS d
        LEFT JOIN employees AS e
            ON d.department_id = e.department_id
        WHERE e.employee_id IS NULL;
        """,
    )

    execute(
        connection,
        "Edge case: employee-manager relationships",
        """
        SELECT
            e.employee_name,
            e.manager_id,
            m.employee_name AS manager_name
        FROM employees AS e
        LEFT JOIN employees AS m
            ON e.manager_id = m.employee_id
        WHERE e.manager_id IS NULL
           OR m.employee_id IS NOT NULL
        ORDER BY e.employee_id;
        """,
    )


# ---------------------------------------------------------------------------
# Assertions as lightweight tests
# ---------------------------------------------------------------------------

def run_assertions(connection: sqlite3.Connection) -> None:
    """Verify important properties of the examples."""

    inner_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM employees AS e
        INNER JOIN departments AS d
            ON e.department_id = d.department_id;
        """
    ).fetchone()[0]

    assert inner_count == 7, "Seven employees have departments."

    department_count = connection.execute(
        "SELECT COUNT(*) FROM departments;"
    ).fetchone()[0]

    assert department_count == 5

    employees_without_department = connection.execute(
        """
        SELECT COUNT(*)
        FROM employees
        WHERE department_id IS NULL;
        """
    ).fetchone()[0]

    assert employees_without_department == 1

    empty_departments = connection.execute(
        """
        SELECT COUNT(*)
        FROM departments AS d
        LEFT JOIN employees AS e
            ON d.department_id = e.department_id
        WHERE e.employee_id IS NULL;
        """
    ).fetchone()[0]

    assert empty_departments == 2

    cross_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT e.employee_id, p.project_id
            FROM employees AS e
            CROSS JOIN projects AS p
            WHERE e.employee_id <= 2
        );
        """
    ).fetchone()[0]

    assert cross_count == 8

    print("\nAll assertions passed.")


# ---------------------------------------------------------------------------
# Compact practical comparison
# ---------------------------------------------------------------------------

def print_comparison() -> None:
    print(
        """
JOIN comparison

INNER JOIN
    Keeps matching rows only.
    Common for ordinary relationships.

FULL OUTER JOIN
    Keeps matching rows and unmatched rows from both sides.
    Useful for reconciliation and completeness analysis.

CROSS JOIN
    Produces every left/right combination.
    Useful for deliberate Cartesian products.

SELF JOIN
    Joins a table to another logical reference of itself.
    Useful for hierarchies, peer relationships, and comparisons within
    one table.

LEFT JOIN
    Keeps every left row and matching right rows.
    Frequently used when optional relationships must remain visible.
"""
    )


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def main() -> None:
    print("SQL Joins II: FULL JOIN, CROSS JOIN, SELF JOIN")

    explain_cardinality()

    connection = create_connection()
    try:
        create_schema(connection)
        seed_data(connection)

        demonstrate_inner_join(connection)
        demonstrate_full_join(connection)
        demonstrate_full_join_classification(connection)
        demonstrate_cross_join(connection)
        demonstrate_cross_join_filter(connection)
        demonstrate_self_join(connection)
        demonstrate_self_join_peer_pairs(connection)
        demonstrate_null_behavior(connection)
        demonstrate_on_vs_where(connection)
        demonstrate_many_to_many(connection)
        demonstrate_aggregation(connection)
        demonstrate_reconciliation(connection)
        demonstrate_semi_and_anti_join(connection)
        demonstrate_composite_key_concept()
        demonstrate_parameterized_sql(connection)
        demonstrate_query_plan(connection)
        demonstrate_edge_cases()
        run_assertions(connection)
        print_comparison()

        print(
            """
Production checklist

1. Define the relationship before writing the join.
2. Use explicit JOIN ... ON syntax.
3. Give tables meaningful aliases.
4. Verify cardinality before aggregating.
5. Check NULL behavior for outer joins.
6. Distinguish ON filtering from WHERE filtering.
7. Use CROSS JOIN only when a Cartesian product is intentional.
8. Use inequality conditions carefully in SELF JOINs.
9. Use indexes that support actual workload patterns.
10. Inspect execution plans for expensive queries.
11. Parameterize user-supplied values.
12. Test unmatched rows, duplicate keys, NULL keys, and empty tables.
"""
        )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
```
