"""
SQL Joins I: INNER JOIN, LEFT JOIN, RIGHT JOIN

A self-contained study program for learning the fundamentals and practical
behavior of SQL joins.

The examples use Python's standard-library sqlite3 module so the program can
be executed without installing third-party packages.

SQLite does not provide RIGHT JOIN in older releases, so this program detects
support and also demonstrates the equivalent RIGHT JOIN using a reversed
LEFT JOIN. The SQL examples are written so that the concepts remain useful
across major relational database systems.
"""

from __future__ import annotations

import sqlite3
from typing import Iterable, Sequence


DATABASE = ":memory:"


def print_title(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def print_subtitle(title: str) -> None:
    """Print a smaller subsection heading."""
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)


def print_rows(
    rows: Iterable[sqlite3.Row],
    columns: Sequence[str] | None = None,
) -> None:
    """Display query results without requiring external formatting packages."""
    rows = list(rows)

    if not rows:
        print("(no rows)")
        return

    if columns is None:
        columns = rows[0].keys()

    widths = {column: len(column) for column in columns}

    for row in rows:
        for column in columns:
            value = row[column]
            text = "NULL" if value is None else str(value)
            widths[column] = max(widths[column], len(text))

    header = " | ".join(
        column.ljust(widths[column]) for column in columns
    )
    separator = "-+-".join("-" * widths[column] for column in columns)

    print(header)
    print(separator)

    for row in rows:
        values = []
        for column in columns:
            value = row[column]
            text = "NULL" if value is None else str(value)
            values.append(text.ljust(widths[column]))
        print(" | ".join(values))


def run_query(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple = (),
    label: str | None = None,
) -> list[sqlite3.Row]:
    """Execute a SELECT statement and display the result."""
    if label:
        print_subtitle(label)

    print("SQL:")
    print(sql.strip())

    cursor = connection.execute(sql, parameters)
    rows = cursor.fetchall()
    print("\nResult:")
    print_rows(rows)
    return rows


def create_database(connection: sqlite3.Connection) -> None:
    """Create a small relational model for join demonstrations."""
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS departments;
        DROP TABLE IF EXISTS employees;

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            city TEXT NOT NULL
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product TEXT NOT NULL,
            amount REAL NOT NULL CHECK (amount >= 0),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE departments (
            department_id INTEGER PRIMARY KEY,
            department_name TEXT NOT NULL
        );

        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY,
            employee_name TEXT NOT NULL,
            department_id INTEGER,
            salary REAL NOT NULL CHECK (salary >= 0),
            FOREIGN KEY (department_id) REFERENCES departments(department_id)
        );

        INSERT INTO customers (customer_id, customer_name, city) VALUES
            (1, 'Asha', 'Lucknow'),
            (2, 'Bharat', 'Delhi'),
            (3, 'Chitra', 'Mumbai'),
            (4, 'Dev', 'Pune'),
            (5, 'Esha', 'Jaipur');

        INSERT INTO orders (order_id, customer_id, product, amount) VALUES
            (101, 1, 'Laptop', 75000),
            (102, 1, 'Mouse', 1500),
            (103, 2, 'Monitor', 18000),
            (104, 3, 'Keyboard', 3500),
            (105, NULL, 'Unassigned Device', 9000);

        INSERT INTO departments (department_id, department_name) VALUES
            (10, 'Engineering'),
            (20, 'Finance'),
            (30, 'Human Resources'),
            (40, 'Security');

        INSERT INTO employees (
            employee_id,
            employee_name,
            department_id,
            salary
        ) VALUES
            (1, 'Anita', 10, 95000),
            (2, 'Ravi', 10, 110000),
            (3, 'Meera', 20, 90000),
            (4, 'Karan', NULL, 70000),
            (5, 'Nisha', 30, 85000);
        """
    )


def demonstrate_basic_selects(connection: sqlite3.Connection) -> None:
    """Establish the two tables that will participate in joins."""
    print_title("1. Relational foundation")

    run_query(
        connection,
        """
        SELECT customer_id, customer_name, city
        FROM customers
        ORDER BY customer_id;
        """,
        label="Customers",
    )

    run_query(
        connection,
        """
        SELECT order_id, customer_id, product, amount
        FROM orders
        ORDER BY order_id;
        """,
        label="Orders",
    )

    print(
        """
A relational database normally stores related facts in separate tables.

The customers table identifies customers.
The orders table identifies purchases.

customer_id is a primary key in customers and acts as a foreign key in
orders. The common column gives SQL a relationship that can be used by JOIN.

A primary key identifies a row within its table.
A foreign key stores a value referring to a key in another table.
A JOIN combines rows from multiple tables according to a join condition.
"""
    )


def demonstrate_inner_join(connection: sqlite3.Connection) -> None:
    """Demonstrate INNER JOIN from basic to more advanced usage."""
    print_title("2. INNER JOIN")

    run_query(
        connection,
        """
        SELECT
            customers.customer_id,
            customers.customer_name,
            orders.order_id,
            orders.product,
            orders.amount
        FROM customers
        INNER JOIN orders
            ON customers.customer_id = orders.customer_id
        ORDER BY customers.customer_id, orders.order_id;
        """,
        label="Basic INNER JOIN",
    )

    print(
        """
INNER JOIN returns only rows for which the join condition is true.

Asha has two orders, Bharat has one, and Chitra has one.
Dev and Esha have no matching orders, so they are absent.

The unmatched order whose customer_id is NULL is also absent because NULL
does not satisfy an equality condition such as customer_id = customer_id.
"""
    )

    run_query(
        connection,
        """
        SELECT
            c.customer_name AS customer,
            o.product,
            o.amount
        FROM customers AS c
        INNER JOIN orders AS o
            ON c.customer_id = o.customer_id
        WHERE o.amount >= 5000
        ORDER BY o.amount DESC;
        """,
        label="INNER JOIN with aliases and WHERE",
    )

    run_query(
        connection,
        """
        SELECT
            c.customer_name AS customer,
            COUNT(o.order_id) AS order_count,
            COALESCE(SUM(o.amount), 0) AS total_spend
        FROM customers AS c
        INNER JOIN orders AS o
            ON c.customer_id = o.customer_id
        GROUP BY c.customer_id, c.customer_name
        ORDER BY total_spend DESC;
        """,
        label="INNER JOIN with GROUP BY and aggregation",
    )

    print(
        """
Important distinction:

COUNT(o.order_id) counts matching order IDs.
COUNT(*) counts rows produced by the JOIN.

For an INNER JOIN they often produce the same count for this model, but
the distinction becomes important when the preserved side of an OUTER JOIN
contains unmatched rows.
"""
    )


def demonstrate_left_join(connection: sqlite3.Connection) -> None:
    """Demonstrate LEFT JOIN and NULL preservation."""
    print_title("3. LEFT JOIN")

    run_query(
        connection,
        """
        SELECT
            c.customer_id,
            c.customer_name,
            o.order_id,
            o.product,
            o.amount
        FROM customers AS c
        LEFT JOIN orders AS o
            ON c.customer_id = o.customer_id
        ORDER BY c.customer_id, o.order_id;
        """,
        label="Basic LEFT JOIN",
    )

    print(
        """
LEFT JOIN preserves every row from the left table.

Customers Dev and Esha have no matching orders. Their customer columns are
present, while order columns become NULL.

This is one of the most important practical differences between INNER JOIN
and LEFT JOIN.
"""
    )

    run_query(
        connection,
        """
        SELECT
            c.customer_id,
            c.customer_name
        FROM customers AS c
        LEFT JOIN orders AS o
            ON c.customer_id = o.customer_id
        WHERE o.order_id IS NULL
        ORDER BY c.customer_id;
        """,
        label="Finding customers with no orders",
    )

    run_query(
        connection,
        """
        SELECT
            c.customer_name,
            COUNT(o.order_id) AS order_count,
            COALESCE(SUM(o.amount), 0) AS total_spend
        FROM customers AS c
        LEFT JOIN orders AS o
            ON c.customer_id = o.customer_id
        GROUP BY c.customer_id, c.customer_name
        ORDER BY c.customer_id;
        """,
        label="Including customers with zero orders",
    )


def demonstrate_on_vs_where(connection: sqlite3.Connection) -> None:
    """Show one of the most common JOIN mistakes."""
    print_title("4. ON versus WHERE")

    run_query(
        connection,
        """
        SELECT
            c.customer_name,
            o.product,
            o.amount
        FROM customers AS c
        LEFT JOIN orders AS o
            ON c.customer_id = o.customer_id
           AND o.amount >= 5000
        ORDER BY c.customer_id, o.order_id;
        """,
        label="Condition in ON: preserve all customers",
    )

    run_query(
        connection,
        """
        SELECT
            c.customer_name,
            o.product,
            o.amount
        FROM customers AS c
        LEFT JOIN orders AS o
            ON c.customer_id = o.customer_id
        WHERE o.amount >= 5000
        ORDER BY c.customer_id, o.order_id;
        """,
        label="Condition in WHERE: remove NULL matches",
    )

    print(
        """
The first query keeps every customer and only matches orders meeting the
amount condition.

The second query first performs the LEFT JOIN, then WHERE removes rows where
the order amount is NULL. The result therefore behaves much more like an
INNER JOIN for this condition.

Rule of thumb:
- ON controls which rows match.
- WHERE filters the rows after the JOIN result has been produced.

The distinction is especially important for OUTER JOINs.
"""
    )


def demonstrate_right_join(connection: sqlite3.Connection) -> None:
    """Demonstrate RIGHT JOIN conceptually and with an equivalent LEFT JOIN."""
    print_title("5. RIGHT JOIN")

    print(
        """
A RIGHT JOIN preserves every row from the right-hand table.

Conceptually:

    A RIGHT JOIN B

can be understood as:

    B LEFT JOIN A

with the table positions reversed.

SQLite installations differ by version in RIGHT JOIN support. To make this
program portable, the following query expresses the exact same preservation
logic with LEFT JOIN.
"""
    )

    run_query(
        connection,
        """
        SELECT
            o.order_id,
            o.product,
            c.customer_id,
            c.customer_name
        FROM orders AS o
        LEFT JOIN customers AS c
            ON c.customer_id = o.customer_id
        ORDER BY o.order_id;
        """,
        label="RIGHT JOIN equivalent using reversed LEFT JOIN",
    )

    if sqlite3.sqlite_version_info >= (3, 39, 0):
        run_query(
            connection,
            """
            SELECT
                o.order_id,
                o.product,
                c.customer_id,
                c.customer_name
            FROM customers AS c
            RIGHT JOIN orders AS o
                ON c.customer_id = o.customer_id
            ORDER BY o.order_id;
            """,
            label="Native RIGHT JOIN when supported",
        )
    else:
        print(
            "\nNative RIGHT JOIN is not available in this SQLite version."
        )

    print(
        """
Here orders are preserved. The order with customer_id NULL remains visible,
and the customer columns are NULL.

A RIGHT JOIN is not a fundamentally different matching mechanism from a LEFT
JOIN. The important idea is which side is preserved.
"""
    )


def demonstrate_null_behavior(connection: sqlite3.Connection) -> None:
    """Explain SQL's three-valued logic as it affects joins."""
    print_title("6. NULL behavior")

    run_query(
        connection,
        """
        SELECT
            o.order_id,
            o.customer_id,
            c.customer_name
        FROM orders AS o
        LEFT JOIN customers AS c
            ON o.customer_id = c.customer_id
        ORDER BY o.order_id;
        """,
        label="NULL foreign key during a LEFT JOIN",
    )

    print(
        """
SQL NULL does not mean zero, an empty string, or a missing object that can
be compared normally.

An expression such as:

    NULL = 5

does not evaluate to TRUE. It evaluates to UNKNOWN.

A JOIN's ON condition needs a matching TRUE result. Therefore NULL does not
match a normal equality comparison.

To test whether something is NULL, use IS NULL or IS NOT NULL.
Do not use = NULL or <> NULL.
"""
    )

    run_query(
        connection,
        """
        SELECT order_id, product
        FROM orders
        WHERE customer_id IS NULL
        ORDER BY order_id;
        """,
        label="Correct NULL test",
    )


def demonstrate_multiple_matches(connection: sqlite3.Connection) -> None:
    """Show why one-to-many joins increase the number of rows."""
    print_title("7. One-to-many relationships and row multiplication")

    run_query(
        connection,
        """
        SELECT
            c.customer_name,
            o.order_id,
            o.product
        FROM customers AS c
        INNER JOIN orders AS o
            ON c.customer_id = o.customer_id
        WHERE c.customer_id = 1
        ORDER BY o.order_id;
        """,
        label="One customer matching multiple orders",
    )

    print(
        """
A JOIN does not automatically collapse related rows.

If one customer has two orders, that customer appears twice in the joined
result. If a customer has five matching orders, that customer contributes
five joined rows.

This behavior is correct. Aggregation with GROUP BY is used when a summary
rather than one output row per relationship is required.
"""
    )


def demonstrate_three_table_join(connection: sqlite3.Connection) -> None:
    """Demonstrate joining more than two relations."""
    print_title("8. Joining multiple tables")

    run_query(
        connection,
        """
        SELECT
            e.employee_id,
            e.employee_name,
            d.department_name,
            e.salary
        FROM employees AS e
        INNER JOIN departments AS d
            ON e.department_id = d.department_id
        ORDER BY d.department_name, e.employee_name;
        """,
        label="Employees with assigned departments",
    )

    run_query(
        connection,
        """
        SELECT
            d.department_id,
            d.department_name,
            e.employee_name,
            e.salary
        FROM departments AS d
        LEFT JOIN employees AS e
            ON d.department_id = e.department_id
        ORDER BY d.department_id, e.employee_id;
        """,
        label="All departments, including departments with no employees",
    )

    print(
        """
When several JOINs are chained, each JOIN operates on the result produced
by the preceding part of the FROM clause.

The logical structure should remain clear:
1. Identify the entities.
2. Identify their relationship keys.
3. Decide which side must be preserved.
4. Write the JOIN condition.
5. Apply filters deliberately.
6. Aggregate only when the required result is a summary.
"""
    )


def demonstrate_join_with_condition(connection: sqlite3.Connection) -> None:
    """Show non-key conditions inside an ON expression."""
    print_title("9. Join conditions beyond simple equality")

    run_query(
        connection,
        """
        SELECT
            c.customer_name,
            o.product,
            o.amount
        FROM customers AS c
        LEFT JOIN orders AS o
            ON c.customer_id = o.customer_id
           AND o.amount BETWEEN 5000 AND 20000
        ORDER BY c.customer_id, o.amount;
        """,
        label="LEFT JOIN with an additional ON predicate",
    )

    print(
        """
A join condition can contain more than one predicate.

Equality on keys is common:

    c.customer_id = o.customer_id

but additional restrictions can be included when they describe which rows
should participate in the match.

Keeping relationship logic in ON and post-join filtering in WHERE often
makes an OUTER JOIN easier to reason about.
"""
    )


def demonstrate_self_join(connection: sqlite3.Connection) -> None:
    """Demonstrate the related concept of joining a table to itself."""
    print_title("10. Related concept: self JOIN")

    connection.execute("DROP TABLE IF EXISTS employees_hierarchy")
    connection.executescript(
        """
        CREATE TABLE employees_hierarchy (
            employee_id INTEGER PRIMARY KEY,
            employee_name TEXT NOT NULL,
            manager_id INTEGER
        );

        INSERT INTO employees_hierarchy
            (employee_id, employee_name, manager_id)
        VALUES
            (1, 'Director', NULL),
            (2, 'Engineering Lead', 1),
            (3, 'Developer', 2),
            (4, 'Analyst', 1);
        """
    )

    run_query(
        connection,
        """
        SELECT
            employee.employee_name AS employee,
            manager.employee_name AS manager
        FROM employees_hierarchy AS employee
        LEFT JOIN employees_hierarchy AS manager
            ON employee.manager_id = manager.employee_id
        ORDER BY employee.employee_id;
        """,
        label="Employees and their managers",
    )

    print(
        """
A self JOIN uses aliases to treat one table as two logical roles.

It is useful for hierarchical data such as:
- employee and manager
- category and parent category
- city and parent region
- account and parent account
"""
    )


def demonstrate_common_mistakes(connection: sqlite3.Connection) -> None:
    """Demonstrate several common mistakes and their safer alternatives."""
    print_title("11. Common JOIN mistakes")

    print_subtitle("Mistake 1: forgetting the join condition")
    print(
        """
A query such as:

    SELECT *
    FROM customers
    JOIN orders;

can produce a Cartesian product when no valid relationship condition is
specified or when CROSS JOIN semantics are used.

If there are 5 customers and 5 orders, a Cartesian product has 25 row
combinations. This is usually unintended.
"""
    )

    run_query(
        connection,
        """
        SELECT COUNT(*) AS combinations
        FROM customers
        CROSS JOIN orders;
        """,
        label="Explicit Cartesian product",
    )

    print_subtitle("Mistake 2: ambiguous column names")
    print(
        """
When multiple tables contain the same column name, qualify it with a table
name or alias.

Prefer:

    c.customer_id = o.customer_id

over an unqualified reference when both relations contain customer_id.
"""
    )

    print_subtitle("Mistake 3: accidental INNER behavior")
    print(
        """
For a LEFT JOIN, placing a condition on the nullable right-hand table in
WHERE can remove the unmatched rows.

Move such a condition into ON when the requirement is to preserve all left
rows while limiting matches.
"""
    )

    print_subtitle("Mistake 4: using SELECT * in production queries")
    print(
        """
SELECT * can expose unnecessary columns, create duplicate column names, and
make downstream code fragile when schemas change.

Explicitly selecting required columns is generally clearer and safer.
"""
    )

    print_subtitle("Mistake 5: joining on the wrong key")
    print(
        """
A syntactically valid JOIN can still be logically incorrect.

Always verify:
- the key represents the intended relationship;
- data types are compatible;
- uniqueness assumptions are true;
- NULL behavior is understood;
- the resulting row count is plausible.
"""
    )


def demonstrate_explain_query_plan(connection: sqlite3.Connection) -> None:
    """Use SQLite's query planner output to introduce performance analysis."""
    print_title("12. Performance and query plans")

    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_orders_customer_id "
        "ON orders(customer_id)"
    )

    query = """
        SELECT
            c.customer_name,
            o.product,
            o.amount
        FROM customers AS c
        INNER JOIN orders AS o
            ON c.customer_id = o.customer_id
        WHERE c.customer_id = ?
    """

    print_subtitle("EXPLAIN QUERY PLAN")
    print(query.strip())

    rows = connection.execute(
        "EXPLAIN QUERY PLAN " + query,
        (1,),
    ).fetchall()

    for row in rows:
        print(tuple(row))

    print(
        """
Indexes can make JOIN operations much faster when they allow the database
engine to locate matching rows efficiently.

A foreign-key relationship does not automatically mean every database
creates an index on the foreign-key column. Index strategy should therefore
be considered separately.

Typical performance considerations:
- index frequently joined columns;
- index useful filtering columns when justified;
- avoid unnecessary columns;
- inspect execution plans;
- understand table cardinality;
- avoid accidental Cartesian products;
- benchmark representative data volumes.

The exact algorithm chosen by a database optimizer depends on the database
engine, statistics, indexes, predicates, and data distribution.
"""
    )


def demonstrate_join_algorithms_conceptually() -> None:
    """Explain common physical join strategies."""
    print_title("13. Physical join algorithms")

    print(
        """
SQL specifies the desired result, not the exact physical algorithm.

Database engines commonly use strategies such as:

Nested-loop join
    For rows from one input, search for matching rows in the other input.
    With a useful index, this can be highly effective.

Hash join
    Build a hash structure for one input and probe it with rows from the
    other input. It is commonly useful for equality joins.

Merge join
    Read two inputs in sorted join-key order and advance through them
    together. It can be efficient when useful ordering already exists.

The SQL statement:

    SELECT ...
    FROM customers AS c
    INNER JOIN orders AS o
        ON c.customer_id = o.customer_id

does not force one of these algorithms.

The optimizer chooses a physical execution plan based on available
information and engine-specific rules.
"""
    )


def demonstrate_join_order_and_cardinality(connection: sqlite3.Connection) -> None:
    """Show why row counts are useful when debugging joins."""
    print_title("14. Cardinality and debugging")

    counts = {
        "customers": connection.execute(
            "SELECT COUNT(*) FROM customers"
        ).fetchone()[0],
        "orders": connection.execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0],
        "inner_join": connection.execute(
            """
            SELECT COUNT(*)
            FROM customers AS c
            INNER JOIN orders AS o
                ON c.customer_id = o.customer_id
            """
        ).fetchone()[0],
        "left_join": connection.execute(
            """
            SELECT COUNT(*)
            FROM customers AS c
            LEFT JOIN orders AS o
                ON c.customer_id = o.customer_id
            """
        ).fetchone()[0],
    }

    for name, count in counts.items():
        print(f"{name:15} = {count}")

    print(
        """
Row-count checks are simple but powerful JOIN debugging tools.

If a result unexpectedly contains millions of rows, inspect:
- whether a join condition is missing;
- whether the relationship is one-to-many or many-to-many;
- whether duplicate keys exist;
- whether the wrong columns were joined;
- whether filtering happened at the intended stage.
"""
    )


def demonstrate_relationship_validation(connection: sqlite3.Connection) -> None:
    """Use SQL to inspect key uniqueness and orphan-like conditions."""
    print_title("15. Relationship validation")

    run_query(
        connection,
        """
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        WHERE customer_id IS NOT NULL
        GROUP BY customer_id
        ORDER BY customer_id;
        """,
        label="Orders grouped by customer",
    )

    run_query(
        connection,
        """
        SELECT
            o.order_id,
            o.customer_id
        FROM orders AS o
        LEFT JOIN customers AS c
            ON o.customer_id = c.customer_id
        WHERE o.customer_id IS NOT NULL
          AND c.customer_id IS NULL;
        """,
        label="Detecting orders without a matching customer",
    )

    print(
        """
In a properly constrained relational model, foreign-key enforcement can
prevent invalid references. In real systems, imported data, disabled
constraints, legacy databases, or transformation pipelines can still make
relationship validation important.
"""
    )


def demonstrate_parameterized_query(connection: sqlite3.Connection) -> None:
    """Demonstrate safe parameter binding for JOIN queries."""
    print_title("16. Parameterized JOIN queries and security")

    city = "Lucknow"

    run_query(
        connection,
        """
        SELECT
            c.customer_name,
            o.product,
            o.amount
        FROM customers AS c
        INNER JOIN orders AS o
            ON c.customer_id = o.customer_id
        WHERE c.city = ?
        ORDER BY o.amount DESC;
        """,
        (city,),
        label="Parameterized JOIN query",
    )

    print(
        """
Use parameterized queries rather than constructing SQL by concatenating
untrusted strings.

Unsafe conceptual pattern:

    "... WHERE city = '" + user_input + "'"

Safe pattern:

    "... WHERE city = ?"

and pass user_input separately as a parameter.

The database driver then handles the value as data instead of treating it
as SQL syntax. This is a fundamental defense against SQL injection.
"""
    )


def demonstrate_transactional_data(connection: sqlite3.Connection) -> None:
    """Demonstrate how joins can support a business validation query."""
    print_title("17. Practical business validation")

    print(
        """
Suppose an application needs to identify customers whose total spending
exceeds a threshold. The JOIN connects customer identity to transaction
records, while GROUP BY and HAVING perform the business rule.
"""
    )

    run_query(
        connection,
        """
        SELECT
            c.customer_id,
            c.customer_name,
            SUM(o.amount) AS total_spend
        FROM customers AS c
        INNER JOIN orders AS o
            ON c.customer_id = o.customer_id
        GROUP BY c.customer_id, c.customer_name
        HAVING SUM(o.amount) > ?
        ORDER BY total_spend DESC;
        """,
        (10000,),
        label="Customers above a spending threshold",
    )


def run_edge_case_tests(connection: sqlite3.Connection) -> None:
    """Run assertions that verify important JOIN semantics."""
    print_title("18. Automated semantic tests")

    inner_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM customers AS c
        INNER JOIN orders AS o
            ON c.customer_id = o.customer_id
        """
    ).fetchone()[0]

    left_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM customers AS c
        LEFT JOIN orders AS o
            ON c.customer_id = o.customer_id
        """
    ).fetchone()[0]

    unmatched_customers = connection.execute(
        """
        SELECT COUNT(*)
        FROM customers AS c
        LEFT JOIN orders AS o
            ON c.customer_id = o.customer_id
        WHERE o.order_id IS NULL
        """
    ).fetchone()[0]

    null_customer_order_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE customer_id IS NULL
        """
    ).fetchone()[0]

    assert inner_count == 4
    assert left_count == 6
    assert unmatched_customers == 2
    assert null_customer_order_count == 1

    print("INNER JOIN row-count assertion: PASSED")
    print("LEFT JOIN row-count assertion: PASSED")
    print("Unmatched-customer assertion: PASSED")
    print("NULL foreign-key assertion: PASSED")

    print(
        """
The LEFT JOIN produces six rows rather than five because Asha has two
orders. The two customers without orders still appear once each.

This illustrates an important point: a LEFT JOIN preserves left-side rows,
but it does not guarantee one output row per left-side row when multiple
right-side matches exist.
"""
    )


def demonstrate_rewrite_equivalences(connection: sqlite3.Connection) -> None:
    """Compare equivalent query formulations."""
    print_title("19. JOIN rewrites and readability")

    query_one = """
        SELECT c.customer_name, o.product
        FROM customers AS c
        INNER JOIN orders AS o
            ON c.customer_id = o.customer_id
        ORDER BY c.customer_name, o.product;
    """

    query_two = """
        SELECT c.customer_name, o.product
        FROM orders AS o
        INNER JOIN customers AS c
            ON o.customer_id = c.customer_id
        ORDER BY c.customer_name, o.product;
    """

    first = connection.execute(query_one).fetchall()
    second = connection.execute(query_two).fetchall()

    print("Same matching relationship with reversed table order:")
    print(first == second)

    print(
        """
For INNER JOINs, reversing the table order often preserves the matching
semantics, provided projections, filters, ordering, and other operations are
adjusted consistently.

For OUTER JOINs, table order matters because it determines which relation is
preserved.

That is why LEFT JOIN and RIGHT JOIN cannot be treated as interchangeable
without reversing the table positions.
"""
    )


def advanced_join_patterns(connection: sqlite3.Connection) -> None:
    """Demonstrate practical patterns frequently used in application SQL."""
    print_title("20. Advanced practical JOIN patterns")

    run_query(
        connection,
        """
        SELECT
            c.customer_name,
            COALESCE(SUM(o.amount), 0) AS total_spend,
            CASE
                WHEN COALESCE(SUM(o.amount), 0) = 0 THEN 'No orders'
                WHEN SUM(o.amount) < 10000 THEN 'Standard'
                ELSE 'High value'
            END AS customer_segment
        FROM customers AS c
        LEFT JOIN orders AS o
            ON c.customer_id = o.customer_id
        GROUP BY c.customer_id, c.customer_name
        ORDER BY total_spend DESC;
        """,
        label="LEFT JOIN + COALESCE + CASE + aggregation",
    )

    run_query(
        connection,
        """
        SELECT
            d.department_name,
            COUNT(e.employee_id) AS employees,
            ROUND(AVG(e.salary), 2) AS average_salary
        FROM departments AS d
        LEFT JOIN employees AS e
            ON d.department_id = e.department_id
        GROUP BY d.department_id, d.department_name
        ORDER BY d.department_id;
        """,
        label="Department report including empty departments",
    )

    print(
        """
COALESCE is useful after an OUTER JOIN because unmatched values are NULL.

CASE can turn relational results into business classifications.

LEFT JOIN + GROUP BY is a common reporting pattern when every entity must
appear even when it has no related records.
"""
    )


def show_join_comparison() -> None:
    """Print a compact conceptual comparison."""
    print_title("21. Join comparison")

    comparison = [
        ("INNER JOIN", "Only matching rows", "No"),
        ("LEFT JOIN", "All left rows + matching right rows", "Yes"),
        ("RIGHT JOIN", "All right rows + matching left rows", "Yes"),
    ]

    print(f"{'Join':15} | {'Result':45} | {'Preserves unmatched side'}")
    print("-" * 78)
    for join_type, result, preserved in comparison:
        print(f"{join_type:15} | {result:45} | {preserved}")

    print(
        """
A useful mental model is:

INNER JOIN
    Intersection of matching rows.

LEFT JOIN
    Keep everything on the left and attach matches from the right.

RIGHT JOIN
    Keep everything on the right and attach matches from the left.

RIGHT JOIN can generally be rewritten as a LEFT JOIN by reversing the table
order. Many teams standardize on LEFT JOIN because it makes the preserved
side visually obvious.
"""
    )


def main() -> None:
    """Run the complete SQL JOIN study program."""
    print_title("SQL Joins I: INNER JOIN, LEFT JOIN, RIGHT JOIN")

    print(
        """
This program is an executable study guide.

Core vocabulary:
- Relation: a table-like collection of records.
- Row: one record.
- Column: one attribute.
- Primary key: a column or set of columns that uniquely identifies rows.
- Foreign key: a reference to a key in another relation.
- Join key: the expression used to associate rows.
- Predicate: a Boolean condition used to determine or filter rows.
- Cardinality: the number of rows or the relationship multiplicity.
- NULL: an SQL marker representing an unknown or absent value.

Logical SQL processing is often described approximately as:

FROM / JOIN
WHERE
GROUP BY
HAVING
SELECT
ORDER BY

This describes logical processing order, not necessarily the physical
execution order selected by a database optimizer.
"""
    )

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    try:
        create_database(connection)
        demonstrate_basic_selects(connection)
        demonstrate_inner_join(connection)
        demonstrate_left_join(connection)
        demonstrate_on_vs_where(connection)
        demonstrate_right_join(connection)
        demonstrate_null_behavior(connection)
        demonstrate_multiple_matches(connection)
        demonstrate_three_table_join(connection)
        demonstrate_join_with_condition(connection)
        demonstrate_self_join(connection)
        demonstrate_common_mistakes(connection)
        demonstrate_explain_query_plan(connection)
        demonstrate_join_order_and_cardinality(connection)
        demonstrate_relationship_validation(connection)
        demonstrate_parameterized_query(connection)
        demonstrate_transactional_data(connection)
        run_edge_case_tests(connection)
        demonstrate_rewrite_equivalences(connection)
        advanced_join_patterns(connection)
        show_join_comparison()

        print_title("22. Final executable checks")
        print("SQLite version:", sqlite3.sqlite_version)
        print("All demonstrations completed successfully.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
