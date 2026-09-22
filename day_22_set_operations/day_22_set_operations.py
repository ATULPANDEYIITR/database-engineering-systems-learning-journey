"""
Set Operations: UNION, UNION ALL, INTERSECT, EXCEPT

A self-contained study program demonstrating SQL-style set operations
with Python's built-in sqlite3 module.

The examples progress from basic set theory and SQL syntax to:
- UNION
- UNION ALL
- INTERSECT
- EXCEPT
- duplicate handling
- column compatibility
- NULL behavior
- ordering
- filtering before set operations
- joins versus set operations
- recursive-style reasoning about multiple operations
- query validation
- realistic customer/order/reporting examples
- performance considerations
- edge cases
- testing

The program uses only Python's standard library.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable, Sequence


# ---------------------------------------------------------------------------
# 1. FUNDAMENTAL IDEA
# ---------------------------------------------------------------------------
#
# A SQL set operation combines the result of two SELECT statements.
#
# Example:
#
#   SELECT city FROM customers_a
#   UNION
#   SELECT city FROM customers_b;
#
# The two SELECT statements must be union-compatible:
# - same number of output columns
# - corresponding columns should have compatible types
#
# UNION:
#   combines rows and removes duplicates
#
# UNION ALL:
#   combines rows and preserves duplicates
#
# INTERSECT:
#   returns rows appearing in both result sets
#
# EXCEPT:
#   returns rows appearing in the first result set but not the second
#
# These operations are different from JOIN:
# - JOIN combines columns horizontally using a relationship.
# - SET operations combine compatible rows vertically.


def heading(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_rows(rows: Sequence[sqlite3.Row], label: str = "Rows") -> None:
    print(f"\n{label}:")
    if not rows:
        print("  <no rows>")
        return

    for row in rows:
        print(" ", tuple(row))


def execute_and_print(
    connection: sqlite3.Connection,
    sql: str,
    label: str,
) -> list[sqlite3.Row]:
    rows = connection.execute(sql).fetchall()
    print_rows(rows, label)
    return rows


# ---------------------------------------------------------------------------
# 2. CREATE DATABASE
# ---------------------------------------------------------------------------

connection = sqlite3.connect(":memory:")
connection.row_factory = sqlite3.Row

connection.executescript(
    """
    CREATE TABLE department_a (
        employee_id INTEGER,
        employee_name TEXT,
        department TEXT
    );

    CREATE TABLE department_b (
        employee_id INTEGER,
        employee_name TEXT,
        department TEXT
    );

    INSERT INTO department_a VALUES
        (1, 'Asha', 'Engineering'),
        (2, 'Ravi', 'Engineering'),
        (3, 'Meera', 'Finance'),
        (4, 'John', 'Security'),
        (4, 'John', 'Security');

    INSERT INTO department_b VALUES
        (4, 'John', 'Security'),
        (5, 'Neha', 'Marketing'),
        (6, 'Arjun', 'Finance'),
        (2, 'Ravi', 'Engineering');

    CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY,
        customer_name TEXT NOT NULL,
        region TEXT NOT NULL
    );

    CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        order_status TEXT NOT NULL,
        amount REAL NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    );

    CREATE TABLE active_customers (
        customer_id INTEGER
    );

    CREATE TABLE premium_customers (
        customer_id INTEGER
    );

    CREATE TABLE email_campaign_a (
        email TEXT
    );

    CREATE TABLE email_campaign_b (
        email TEXT
    );

    INSERT INTO customers VALUES
        (101, 'Ananya', 'North'),
        (102, 'Bharat', 'North'),
        (103, 'Charu', 'South'),
        (104, 'Dev', 'East'),
        (105, 'Esha', 'West'),
        (106, 'Farhan', 'South'),
        (107, 'Gauri', 'North'),
        (108, 'Hari', 'East');

    INSERT INTO orders VALUES
        (1001, 101, 'completed', 1200.00),
        (1002, 101, 'completed', 800.00),
        (1003, 102, 'pending', 500.00),
        (1004, 103, 'completed', 2400.00),
        (1005, 104, 'cancelled', 1000.00),
        (1006, 105, 'completed', 3200.00),
        (1007, 106, 'completed', 1500.00),
        (1008, 107, 'completed', 700.00),
        (1009, 108, 'pending', 900.00);

    INSERT INTO active_customers VALUES
        (101), (102), (103), (104), (107);

    INSERT INTO premium_customers VALUES
        (101), (103), (105), (107);

    INSERT INTO email_campaign_a VALUES
        ('a@example.com'),
        ('b@example.com'),
        ('c@example.com'),
        ('c@example.com');

    INSERT INTO email_campaign_b VALUES
        ('c@example.com'),
        ('d@example.com'),
        ('e@example.com');
    """
)


# ---------------------------------------------------------------------------
# 3. BASIC UNION
# ---------------------------------------------------------------------------

heading("1. UNION: COMBINE RESULTS AND REMOVE DUPLICATES")

execute_and_print(
    connection,
    """
    SELECT employee_id, employee_name, department
    FROM department_a
    UNION
    SELECT employee_id, employee_name, department
    FROM department_b
    ORDER BY employee_id;
    """,
    "UNION result",
)

# John and Ravi appear in both input tables, but UNION keeps only one copy
# of each identical row.


# ---------------------------------------------------------------------------
# 4. UNION ALL
# ---------------------------------------------------------------------------

heading("2. UNION ALL: COMBINE RESULTS AND PRESERVE DUPLICATES")

execute_and_print(
    connection,
    """
    SELECT employee_id, employee_name, department
    FROM department_a
    UNION ALL
    SELECT employee_id, employee_name, department
    FROM department_b
    ORDER BY employee_id;
    """,
    "UNION ALL result",
)

# UNION ALL is usually cheaper than UNION because the database does not
# need to remove duplicate rows.


# ---------------------------------------------------------------------------
# 5. INTERSECT
# ---------------------------------------------------------------------------

heading("3. INTERSECT: ROWS COMMON TO BOTH RESULTS")

execute_and_print(
    connection,
    """
    SELECT employee_id, employee_name, department
    FROM department_a
    INTERSECT
    SELECT employee_id, employee_name, department
    FROM department_b
    ORDER BY employee_id;
    """,
    "INTERSECT result",
)

# Only rows that are identical across the complete selected columns appear.


# ---------------------------------------------------------------------------
# 6. EXCEPT
# ---------------------------------------------------------------------------

heading("4. EXCEPT: ROWS IN THE FIRST RESULT BUT NOT THE SECOND")

execute_and_print(
    connection,
    """
    SELECT employee_id, employee_name, department
    FROM department_a
    EXCEPT
    SELECT employee_id, employee_name, department
    FROM department_b
    ORDER BY employee_id;
    """,
    "EXCEPT result",
)

# EXCEPT is directional.
#
# A EXCEPT B is not equivalent to B EXCEPT A.


# ---------------------------------------------------------------------------
# 7. DIRECTION OF EXCEPT
# ---------------------------------------------------------------------------

heading("5. EXCEPT IS DIRECTIONAL")

execute_and_print(
    connection,
    """
    SELECT employee_id
    FROM department_a
    EXCEPT
    SELECT employee_id
    FROM department_b
    ORDER BY employee_id;
    """,
    "A EXCEPT B",
)

execute_and_print(
    connection,
    """
    SELECT employee_id
    FROM department_b
    EXCEPT
    SELECT employee_id
    FROM department_a
    ORDER BY employee_id;
    """,
    "B EXCEPT A",
)


# ---------------------------------------------------------------------------
# 8. SINGLE-COLUMN SET OPERATIONS
# ---------------------------------------------------------------------------

heading("6. SET OPERATIONS ON SINGLE COLUMNS")

execute_and_print(
    connection,
    """
    SELECT department
    FROM department_a
    UNION
    SELECT department
    FROM department_b
    ORDER BY department;
    """,
    "Distinct departments",
)

execute_and_print(
    connection,
    """
    SELECT department
    FROM department_a
    INTERSECT
    SELECT department
    FROM department_b
    ORDER BY department;
    """,
    "Departments common to both tables",
)


# ---------------------------------------------------------------------------
# 9. UNION COMPATIBILITY
# ---------------------------------------------------------------------------

heading("7. UNION-COMPATIBLE RESULT SETS")

# The following is valid because both SELECT statements return two columns.

execute_and_print(
    connection,
    """
    SELECT employee_id, employee_name
    FROM department_a
    UNION
    SELECT employee_id, employee_name
    FROM department_b
    ORDER BY employee_id;
    """,
    "Two-column compatible UNION",
)

# Conceptually invalid:
#
# SELECT employee_id, employee_name FROM department_a
# UNION
# SELECT employee_id FROM department_b;
#
# The number of columns does not match.
#
# Databases may differ in their exact type coercion rules, so compatible
# column types should be chosen deliberately rather than relying on
# implicit conversions.


# ---------------------------------------------------------------------------
# 10. FILTERING BEFORE UNION
# ---------------------------------------------------------------------------

heading("8. WHERE FILTERS CAN BE APPLIED BEFORE SET OPERATIONS")

execute_and_print(
    connection,
    """
    SELECT employee_id, employee_name
    FROM department_a
    WHERE department = 'Engineering'
    UNION
    SELECT employee_id, employee_name
    FROM department_b
    WHERE department = 'Finance'
    ORDER BY employee_id;
    """,
    "Filtered UNION",
)


# ---------------------------------------------------------------------------
# 11. UNION WITH COMPUTED COLUMNS
# ---------------------------------------------------------------------------

heading("9. SET OPERATIONS WITH COMPUTED COLUMNS")

execute_and_print(
    connection,
    """
    SELECT employee_id, UPPER(employee_name) AS normalized_name
    FROM department_a
    UNION
    SELECT employee_id, UPPER(employee_name) AS normalized_name
    FROM department_b
    ORDER BY employee_id;
    """,
    "Computed-column UNION",
)


# ---------------------------------------------------------------------------
# 12. CUSTOMER SEGMENTS
# ---------------------------------------------------------------------------

heading("10. REALISTIC CUSTOMER SEGMENT EXAMPLE")

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM active_customers
    UNION
    SELECT customer_id
    FROM premium_customers
    ORDER BY customer_id;
    """,
    "Customers who are active OR premium",
)

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM active_customers
    INTERSECT
    SELECT customer_id
    FROM premium_customers
    ORDER BY customer_id;
    """,
    "Customers who are active AND premium",
)

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM active_customers
    EXCEPT
    SELECT customer_id
    FROM premium_customers
    ORDER BY customer_id;
    """,
    "Active but not premium customers",
)


# ---------------------------------------------------------------------------
# 13. UNION AS LOGICAL OR
# ---------------------------------------------------------------------------

heading("11. SET OPERATIONS AND LOGICAL THINKING")

# These two approaches can express related business questions:
#
# UNION:
#   customers satisfying condition A
#   OR
#   customers satisfying condition B
#
# INTERSECT:
#   customers satisfying condition A
#   AND
#   customers satisfying condition B
#
# EXCEPT:
#   customers satisfying condition A
#   BUT NOT condition B
#
# The exact query shape matters when duplicates, NULLs, computed columns,
# and different source tables are involved.

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM orders
    WHERE order_status = 'completed'
    UNION
    SELECT customer_id
    FROM orders
    WHERE amount >= 3000
    ORDER BY customer_id;
    """,
    "Completed OR high-value customers",
)


# ---------------------------------------------------------------------------
# 14. INTERSECT AS LOGICAL AND
# ---------------------------------------------------------------------------

heading("12. INTERSECT FOR MULTIPLE CONDITIONS")

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM orders
    WHERE order_status = 'completed'
    INTERSECT
    SELECT customer_id
    FROM orders
    WHERE amount >= 1000
    ORDER BY customer_id;
    """,
    "Customers with completed and high-value orders",
)


# ---------------------------------------------------------------------------
# 15. EXCEPT AS EXCLUSION
# ---------------------------------------------------------------------------

heading("13. EXCEPT FOR EXCLUSION RULES")

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM orders
    WHERE order_status = 'completed'
    EXCEPT
    SELECT customer_id
    FROM orders
    WHERE order_status = 'cancelled'
    ORDER BY customer_id;
    """,
    "Completed-order customers excluding customers with cancellations",
)


# ---------------------------------------------------------------------------
# 16. UNION ALL FOR EVENT-LIKE DATA
# ---------------------------------------------------------------------------

heading("14. UNION ALL FOR APPENDING RECORDS")

# UNION ALL is appropriate when each input row represents a separate event
# and duplicate-looking rows are still meaningful records.

execute_and_print(
    connection,
    """
    SELECT customer_id, 'completed' AS source
    FROM orders
    WHERE order_status = 'completed'
    UNION ALL
    SELECT customer_id, 'pending' AS source
    FROM orders
    WHERE order_status = 'pending'
    ORDER BY customer_id;
    """,
    "Appended event-like records",
)


# ---------------------------------------------------------------------------
# 17. DISTINCT AND UNION
# ---------------------------------------------------------------------------

heading("15. UNION ALREADY PERFORMS DISTINCT-STYLE DEDUPLICATION")

union_rows = connection.execute(
    """
    SELECT email FROM email_campaign_a
    UNION
    SELECT email FROM email_campaign_b
    ORDER BY email;
    """
).fetchall()

union_all_rows = connection.execute(
    """
    SELECT email FROM email_campaign_a
    UNION ALL
    SELECT email FROM email_campaign_b
    ORDER BY email;
    """
).fetchall()

print_rows(union_rows, "UNION email list")
print_rows(union_all_rows, "UNION ALL email list")


# ---------------------------------------------------------------------------
# 18. COUNTING THE DIFFERENCE
# ---------------------------------------------------------------------------

heading("16. COUNTING UNION VERSUS UNION ALL")

counts = connection.execute(
    """
    SELECT
        (SELECT COUNT(*) FROM (
            SELECT email FROM email_campaign_a
            UNION
            SELECT email FROM email_campaign_b
        )) AS union_count,
        (SELECT COUNT(*) FROM (
            SELECT email FROM email_campaign_a
            UNION ALL
            SELECT email FROM email_campaign_b
        )) AS union_all_count;
    """
).fetchone()

print(f"UNION count     : {counts['union_count']}")
print(f"UNION ALL count : {counts['union_all_count']}")


# ---------------------------------------------------------------------------
# 19. ORDER BY PLACEMENT
# ---------------------------------------------------------------------------

heading("17. ORDER BY WITH SET OPERATIONS")

# ORDER BY normally belongs to the final combined result.

execute_and_print(
    connection,
    """
    SELECT employee_id, employee_name
    FROM department_a
    UNION
    SELECT employee_id, employee_name
    FROM department_b
    ORDER BY employee_name;
    """,
    "Final result ordered by name",
)

# A common mistake is attempting to put unrelated ORDER BY clauses into each
# branch without understanding the SQL dialect's grammar. When ordering the
# complete set, put ORDER BY after the final SELECT.


# ---------------------------------------------------------------------------
# 20. PARENTHESES AND COMPLEX EXPRESSIONS
# ---------------------------------------------------------------------------

heading("18. MULTI-STAGE SET OPERATIONS")

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM active_customers
    UNION
    SELECT customer_id
    FROM premium_customers
    EXCEPT
    SELECT customer_id
    FROM orders
    WHERE order_status = 'cancelled'
    ORDER BY customer_id;
    """,
    "Multi-stage set expression",
)

# When a query becomes complicated, explicit subqueries can make the intended
# logical stages easier to read and maintain.

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM (
        SELECT customer_id
        FROM active_customers
        UNION
        SELECT customer_id
        FROM premium_customers
    ) AS eligible
    EXCEPT
    SELECT customer_id
    FROM orders
    WHERE order_status = 'cancelled'
    ORDER BY customer_id;
    """,
    "Explicitly staged set expression",
)


# ---------------------------------------------------------------------------
# 21. NULL BEHAVIOR
# ---------------------------------------------------------------------------

heading("19. NULL AND SET OPERATIONS")

connection.executescript(
    """
    CREATE TABLE null_set_a (value TEXT);
    CREATE TABLE null_set_b (value TEXT);

    INSERT INTO null_set_a VALUES
        ('A'),
        (NULL),
        ('B');

    INSERT INTO null_set_b VALUES
        ('B'),
        (NULL),
        ('C');
    """
)

execute_and_print(
    connection,
    """
    SELECT value FROM null_set_a
    UNION
    SELECT value FROM null_set_b
    ORDER BY value IS NOT NULL DESC, value;
    """,
    "UNION involving NULL",
)

execute_and_print(
    connection,
    """
    SELECT value FROM null_set_a
    INTERSECT
    SELECT value FROM null_set_b
    ORDER BY value IS NOT NULL DESC, value;
    """,
    "INTERSECT involving NULL",
)

# SQL set operations treat NULLs according to duplicate/equality semantics
# defined by the SQL implementation. This differs from ordinary SQL
# three-valued comparison logic such as:
#
#   NULL = NULL
#
# which does not evaluate to TRUE.
#
# This distinction is important when comparing set operations with JOIN or
# WHERE predicates.


# ---------------------------------------------------------------------------
# 22. SET OPERATIONS VERSUS JOIN
# ---------------------------------------------------------------------------

heading("20. SET OPERATIONS VERSUS JOIN")

# Set operation: rows are stacked.
execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM active_customers
    UNION
    SELECT customer_id
    FROM premium_customers
    ORDER BY customer_id;
    """,
    "Vertical combination",
)

# Join: columns from related rows are combined horizontally.
execute_and_print(
    connection,
    """
    SELECT
        c.customer_id,
        c.customer_name,
        c.region
    FROM customers AS c
    INNER JOIN active_customers AS a
        ON a.customer_id = c.customer_id
    ORDER BY c.customer_id;
    """,
    "Horizontal relational combination",
)


# ---------------------------------------------------------------------------
# 23. EXCEPT VERSUS NOT EXISTS
# ---------------------------------------------------------------------------

heading("21. EXCEPT VERSUS NOT EXISTS")

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM active_customers
    EXCEPT
    SELECT customer_id
    FROM premium_customers
    ORDER BY customer_id;
    """,
    "EXCEPT",
)

execute_and_print(
    connection,
    """
    SELECT a.customer_id
    FROM active_customers AS a
    WHERE NOT EXISTS (
        SELECT 1
        FROM premium_customers AS p
        WHERE p.customer_id = a.customer_id
    )
    ORDER BY a.customer_id;
    """,
    "Equivalent exclusion expressed with NOT EXISTS",
)

# These expressions can be conceptually similar, but they are not always
# interchangeable in every schema. NULLs, duplicates, additional columns,
# optimizer behavior, and database-specific semantics can matter.


# ---------------------------------------------------------------------------
# 24. INTERSECT VERSUS EXISTS
# ---------------------------------------------------------------------------

heading("22. INTERSECT VERSUS EXISTS")

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM active_customers
    INTERSECT
    SELECT customer_id
    FROM premium_customers
    ORDER BY customer_id;
    """,
    "INTERSECT",
)

execute_and_print(
    connection,
    """
    SELECT a.customer_id
    FROM active_customers AS a
    WHERE EXISTS (
        SELECT 1
        FROM premium_customers AS p
        WHERE p.customer_id = a.customer_id
    )
    ORDER BY a.customer_id;
    """,
    "Equivalent existence-based expression",
)


# ---------------------------------------------------------------------------
# 25. REALISTIC REPORTING QUERY
# ---------------------------------------------------------------------------

heading("23. INDUSTRY-STYLE REPORTING QUERY")

# Requirement:
# Identify customers who either:
# 1. have completed at least one order, OR
# 2. are currently active,
# then remove customers whose orders include cancellations.

report_rows = execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM (
        SELECT customer_id
        FROM orders
        WHERE order_status = 'completed'

        UNION

        SELECT customer_id
        FROM active_customers
    ) AS eligible_customers

    EXCEPT

    SELECT customer_id
    FROM orders
    WHERE order_status = 'cancelled'

    ORDER BY customer_id;
    """,
    "Eligible customer report",
)

# Convert identifiers into a richer report using a JOIN after the set
# operation has established membership.

execute_and_print(
    connection,
    """
    SELECT
        c.customer_id,
        c.customer_name,
        c.region
    FROM customers AS c
    INNER JOIN (
        SELECT customer_id
        FROM (
            SELECT customer_id
            FROM orders
            WHERE order_status = 'completed'

            UNION

            SELECT customer_id
            FROM active_customers
        ) AS eligible

        EXCEPT

        SELECT customer_id
        FROM orders
        WHERE order_status = 'cancelled'
    ) AS final_customers
        ON final_customers.customer_id = c.customer_id
    ORDER BY c.customer_id;
    """,
    "Enriched customer report",
)


# ---------------------------------------------------------------------------
# 26. VALIDATION OF INPUTS
# ---------------------------------------------------------------------------

heading("24. PYTHON VALIDATION AROUND SQL SET OPERATIONS")


def validate_set_query_parts(
    left_query: str,
    right_query: str,
    operation: str,
) -> None:
    """Perform simple application-level validation.

    This does not parse SQL and therefore cannot prove that the queries are
    semantically compatible. It demonstrates an important engineering idea:
    validate configuration before sending dynamic SQL to a database.
    """
    allowed_operations = {"UNION", "UNION ALL", "INTERSECT", "EXCEPT"}

    if operation.upper() not in allowed_operations:
        raise ValueError(
            f"Unsupported set operation: {operation}. "
            f"Expected one of {sorted(allowed_operations)}."
        )

    if not left_query.strip():
        raise ValueError("The left SELECT query cannot be empty.")

    if not right_query.strip():
        raise ValueError("The right SELECT query cannot be empty.")


validate_set_query_parts(
    "SELECT customer_id FROM active_customers",
    "SELECT customer_id FROM premium_customers",
    "UNION",
)

print("Set-query configuration validation succeeded.")


# ---------------------------------------------------------------------------
# 27. REUSABLE PYTHON HELPER
# ---------------------------------------------------------------------------

heading("25. REUSABLE PYTHON SET-OPERATION HELPER")


def run_set_operation(
    connection: sqlite3.Connection,
    left_sql: str,
    right_sql: str,
    operation: str,
) -> list[sqlite3.Row]:
    """Execute a controlled SQL set operation.

    The operation is validated because SQL identifiers/operators cannot be
    safely supplied as ordinary parameter placeholders.
    """
    normalized_operation = operation.strip().upper()

    if normalized_operation not in {
        "UNION",
        "UNION ALL",
        "INTERSECT",
        "EXCEPT",
    }:
        raise ValueError(f"Unsupported operation: {operation}")

    query = f"""
        {left_sql}
        {normalized_operation}
        {right_sql}
    """

    return connection.execute(query).fetchall()


helper_result = run_set_operation(
    connection,
    "SELECT customer_id FROM active_customers",
    "SELECT customer_id FROM premium_customers",
    "INTERSECT",
)

print_rows(helper_result, "Reusable helper result")


# ---------------------------------------------------------------------------
# 28. ERROR HANDLING
# ---------------------------------------------------------------------------

heading("26. ERROR HANDLING")

try:
    run_set_operation(
        connection,
        "SELECT customer_id FROM active_customers",
        "SELECT customer_id FROM premium_customers",
        "INVALID_OPERATION",
    )
except ValueError as error:
    print(f"Caught validation error: {error}")


# ---------------------------------------------------------------------------
# 29. TESTING EXPECTED SET SEMANTICS
# ---------------------------------------------------------------------------

heading("27. AUTOMATED TESTS")

def scalar_set(
    connection: sqlite3.Connection,
    sql: str,
) -> set[tuple]:
    """Return query rows as Python tuples for semantic testing."""
    return {tuple(row) for row in connection.execute(sql).fetchall()}


union_values = scalar_set(
    connection,
    """
    SELECT customer_id FROM active_customers
    UNION
    SELECT customer_id FROM premium_customers
    """,
)

intersection_values = scalar_set(
    connection,
    """
    SELECT customer_id FROM active_customers
    INTERSECT
    SELECT customer_id FROM premium_customers
    """,
)

difference_values = scalar_set(
    connection,
    """
    SELECT customer_id FROM active_customers
    EXCEPT
    SELECT customer_id FROM premium_customers
    """,
)

assert union_values == {(101,), (102,), (103,), (104,), (105,), (107,)}
assert intersection_values == {(101,), (103,), (107,)}
assert difference_values == {(102,), (104,)}

print("UNION test passed.")
print("INTERSECT test passed.")
print("EXCEPT test passed.")


# ---------------------------------------------------------------------------
# 30. PYTHON NATIVE SETS VERSUS SQL SET OPERATIONS
# ---------------------------------------------------------------------------

heading("28. SQL SET OPERATIONS AND PYTHON SETS")

python_a = {101, 102, 103, 104, 107}
python_b = {101, 103, 105, 107}

print("Python union       :", sorted(python_a | python_b))
print("Python intersection:", sorted(python_a & python_b))
print("Python difference  :", sorted(python_a - python_b))

# Python sets help illustrate the mathematical intuition:
#
# A | B = union
# A & B = intersection
# A - B = difference
#
# SQL adds database-specific concerns such as:
# - duplicate rows
# - NULL
# - column compatibility
# - query planning
# - indexes
# - disk-based processing
# - transaction isolation
# - collation
# - data types
# - optimizer behavior


# ---------------------------------------------------------------------------
# 31. PERFORMANCE CONSIDERATIONS
# ---------------------------------------------------------------------------

heading("29. PERFORMANCE CONSIDERATIONS")

connection.executescript(
    """
    CREATE INDEX idx_orders_customer_id
    ON orders(customer_id);

    CREATE INDEX idx_orders_status
    ON orders(order_status);

    CREATE INDEX idx_orders_amount
    ON orders(amount);
    """
)

# The indexes can help the database locate relevant rows before or during
# set-operation processing. They do not guarantee a particular execution
# plan. The optimizer chooses a plan based on statistics, cardinality,
# indexes, predicates, database engine, and other factors.

plan = connection.execute(
    """
    EXPLAIN QUERY PLAN
    SELECT customer_id
    FROM orders
    WHERE order_status = 'completed'
    UNION
    SELECT customer_id
    FROM active_customers;
    """
).fetchall()

print_rows(plan, "SQLite query plan")


# ---------------------------------------------------------------------------
# 32. UNION VERSUS UNION ALL PERFORMANCE IDEA
# ---------------------------------------------------------------------------

heading("30. UNION VERSUS UNION ALL: COST MODEL")

print(
    """
UNION:
  1. Reads both input result sets.
  2. Combines them.
  3. Removes duplicate rows.
  4. Produces a distinct result.

UNION ALL:
  1. Reads both input result sets.
  2. Appends them.
  3. Does not perform duplicate elimination.

When duplicates are known to be meaningful or impossible, UNION ALL can avoid
unnecessary duplicate-elimination work. When unique results are required,
UNION provides the required deduplication semantics.
""".strip()
)


# ---------------------------------------------------------------------------
# 33. COMMON MISTAKES
# ---------------------------------------------------------------------------

heading("31. COMMON MISTAKES")

mistakes = [
    (
        "Using UNION when duplicate records are meaningful",
        "Use UNION ALL when every input row should remain represented.",
    ),
    (
        "Using UNION ALL when unique rows are required",
        "Use UNION or another explicit deduplication strategy.",
    ),
    (
        "Selecting different numbers of columns",
        "Make both SELECT statements return the same number of columns.",
    ),
    (
        "Assuming EXCEPT is symmetric",
        "Remember that A EXCEPT B differs from B EXCEPT A.",
    ),
    (
        "Confusing UNION with JOIN",
        "UNION combines rows; JOIN combines related columns.",
    ),
    (
        "Ordering each branch when final ordering is intended",
        "Usually apply ORDER BY to the final combined result.",
    ),
    (
        "Ignoring NULL behavior",
        "Understand the database's set-comparison semantics.",
    ),
    (
        "Building dynamic SQL without validation",
        "Validate operation names and avoid unsafe string construction.",
    ),
]

for mistake, correction in mistakes:
    print(f"- Mistake: {mistake}")
    print(f"  Correction: {correction}")


# ---------------------------------------------------------------------------
# 34. COMPARISON TABLE AS DATA
# ---------------------------------------------------------------------------

heading("32. OPERATIONAL COMPARISON")

comparison = [
    ("UNION", "Combines results", "Removes duplicates", "A OR B style membership"),
    ("UNION ALL", "Combines results", "Preserves duplicates", "Append/aggregation pipelines"),
    ("INTERSECT", "Common results", "Returns distinct rows", "A AND B style membership"),
    ("EXCEPT", "First minus second", "Returns distinct rows", "A NOT IN B style membership"),
]

for operation, behavior, duplicates, typical_use in comparison:
    print(
        f"{operation:12} | "
        f"{behavior:24} | "
        f"{duplicates:24} | "
        f"{typical_use}"
    )


# ---------------------------------------------------------------------------
# 35. PRACTICAL DATA-QUALITY SCENARIO
# ---------------------------------------------------------------------------

heading("33. DATA QUALITY: FINDING OVERLAPPING CUSTOMER SOURCES")

connection.executescript(
    """
    CREATE TABLE crm_import (
        customer_id INTEGER
    );

    CREATE TABLE marketing_import (
        customer_id INTEGER
    );

    INSERT INTO crm_import VALUES
        (101), (102), (103), (104);

    INSERT INTO marketing_import VALUES
        (103), (104), (105), (106);
    """
)

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM crm_import
    INTERSECT
    SELECT customer_id
    FROM marketing_import
    ORDER BY customer_id;
    """,
    "Customers present in both systems",
)

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM crm_import
    EXCEPT
    SELECT customer_id
    FROM marketing_import
    ORDER BY customer_id;
    """,
    "CRM-only customers",
)

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM marketing_import
    EXCEPT
    SELECT customer_id
    FROM crm_import
    ORDER BY customer_id;
    """,
    "Marketing-only customers",
)


# ---------------------------------------------------------------------------
# 36. AUDIENCE CONSTRUCTION
# ---------------------------------------------------------------------------

heading("34. MARKETING AUDIENCE CONSTRUCTION")

execute_and_print(
    connection,
    """
    SELECT customer_id
    FROM active_customers
    UNION
    SELECT customer_id
    FROM premium_customers
    EXCEPT
    SELECT customer_id
    FROM orders
    WHERE order_status = 'cancelled'
    ORDER BY customer_id;
    """,
    "Candidate marketing audience",
)


# ---------------------------------------------------------------------------
# 37. SET OPERATION WITH AGGREGATION
# ---------------------------------------------------------------------------

heading("35. AGGREGATION AROUND SET OPERATIONS")

execute_and_print(
    connection,
    """
    SELECT COUNT(*) AS customer_count
    FROM (
        SELECT customer_id
        FROM active_customers
        UNION
        SELECT customer_id
        FROM premium_customers
    ) AS combined_segments;
    """,
    "Distinct customers across segments",
)

execute_and_print(
    connection,
    """
    SELECT COUNT(*) AS row_count
    FROM (
        SELECT customer_id
        FROM active_customers
        UNION ALL
        SELECT customer_id
        FROM premium_customers
    ) AS appended_segments;
    """,
    "Total rows across segments",
)


# ---------------------------------------------------------------------------
# 38. SET OPERATIONS WITH DIFFERENT SOURCE TABLES
# ---------------------------------------------------------------------------

heading("36. DIFFERENT SOURCE TABLES WITH COMMON OUTPUT SHAPE")

execute_and_print(
    connection,
    """
    SELECT customer_id, 'ACTIVE' AS segment
    FROM active_customers

    UNION ALL

    SELECT customer_id, 'PREMIUM' AS segment
    FROM premium_customers

    ORDER BY customer_id, segment;
    """,
    "Segment membership records",
)

# UNION ALL is particularly useful here because one customer may belong to
# multiple segments. Removing duplicates would destroy useful membership
# information.


# ---------------------------------------------------------------------------
# 39. TESTING DUPLICATE SEMANTICS
# ---------------------------------------------------------------------------

heading("37. DUPLICATE SEMANTICS")

connection.executescript(
    """
    CREATE TABLE duplicate_a (value INTEGER);
    CREATE TABLE duplicate_b (value INTEGER);

    INSERT INTO duplicate_a VALUES
        (1), (1), (2), (3);

    INSERT INTO duplicate_b VALUES
        (2), (2), (3), (4);
    """
)

execute_and_print(
    connection,
    """
    SELECT value FROM duplicate_a
    UNION
    SELECT value FROM duplicate_b
    ORDER BY value;
    """,
    "Duplicate inputs with UNION",
)

execute_and_print(
    connection,
    """
    SELECT value FROM duplicate_a
    UNION ALL
    SELECT value FROM duplicate_b
    ORDER BY value;
    """,
    "Duplicate inputs with UNION ALL",
)

execute_and_print(
    connection,
    """
    SELECT value FROM duplicate_a
    INTERSECT
    SELECT value FROM duplicate_b
    ORDER BY value;
    """,
    "Duplicate inputs with INTERSECT",
)

execute_and_print(
    connection,
    """
    SELECT value FROM duplicate_a
    EXCEPT
    SELECT value FROM duplicate_b
    ORDER BY value;
    """,
    "Duplicate inputs with EXCEPT",
)

# Important distinction:
# INTERSECT and EXCEPT generally produce distinct result rows in standard
# SQL set semantics. UNION ALL is the operation specifically designed to
# preserve duplicates.


# ---------------------------------------------------------------------------
# 40. TRANSACTIONAL CONSIDERATIONS
# ---------------------------------------------------------------------------

heading("38. TRANSACTION AND CONSISTENCY CONSIDERATIONS")

print(
    """
When set operations read multiple tables in a production system, the
transaction isolation level can affect which committed versions of data
are observed.

For reporting workloads, consistency matters when the two input SELECTs
must represent the same logical point in time.

A database transaction can provide an appropriate consistency boundary,
depending on the database engine and isolation level.
""".strip()
)


# ---------------------------------------------------------------------------
# 41. SECURITY CONSIDERATIONS
# ---------------------------------------------------------------------------

heading("39. SECURITY CONSIDERATIONS")

print(
    """
Set operations themselves are not a substitute for secure query construction.

Important practices include:
- Use parameterized SQL for user-supplied values.
- Validate dynamically selected operation names.
- Restrict database permissions.
- Avoid constructing arbitrary SELECT expressions from untrusted input.
- Expose only the columns needed by the application.
- Consider row-level security where supported.
- Audit sensitive reporting queries.
""".strip()
)


# ---------------------------------------------------------------------------
# 42. FINAL PRACTICAL DEMONSTRATION
# ---------------------------------------------------------------------------

heading("40. FINAL END-TO-END SET-OPERATION CASE STUDY")

final_query = """
WITH completed_customers AS (
    SELECT customer_id
    FROM orders
    WHERE order_status = 'completed'
),
active_or_premium AS (
    SELECT customer_id
    FROM active_customers

    UNION

    SELECT customer_id
    FROM premium_customers
),
eligible_customers AS (
    SELECT customer_id
    FROM completed_customers

    UNION

    SELECT customer_id
    FROM active_or_premium
),
excluded_customers AS (
    SELECT customer_id
    FROM orders
    WHERE order_status = 'cancelled'
),
final_customers AS (
    SELECT customer_id
    FROM eligible_customers

    EXCEPT

    SELECT customer_id
    FROM excluded_customers
)
SELECT
    c.customer_id,
    c.customer_name,
    c.region
FROM customers AS c
INNER JOIN final_customers AS f
    ON f.customer_id = c.customer_id
ORDER BY c.customer_id;
"""

execute_and_print(
    connection,
    final_query,
    "Final customer eligibility report",
)


# ---------------------------------------------------------------------------
# 43. KEY RULES PRINTED AS A MACHINE-READABLE REFERENCE
# ---------------------------------------------------------------------------

heading("41. QUICK REFERENCE")

rules = {
    "UNION": "Combines compatible SELECT results and removes duplicates.",
    "UNION ALL": "Combines compatible SELECT results and preserves duplicates.",
    "INTERSECT": "Returns distinct rows common to both SELECT results.",
    "EXCEPT": "Returns distinct rows present in the first result but absent from the second.",
    "Compatibility": "Both SELECT statements should return the same number of columns with compatible types.",
    "Ordering": "ORDER BY the final combined result when final-result ordering is required.",
    "Direction": "EXCEPT is directional.",
    "JOIN distinction": "Set operations combine rows; joins combine columns across related rows.",
    "Performance": "UNION ALL can avoid duplicate-elimination work required by UNION.",
    "Security": "Validate dynamic SQL components and parameterize values.",
}

for operation, rule in rules.items():
    print(f"{operation}: {rule}")


# ---------------------------------------------------------------------------
# 44. CLEANUP
# ---------------------------------------------------------------------------

connection.close()

print("\nStudy program completed successfully.")
