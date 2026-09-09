"""
SELECT Fundamentals: SELECT, FROM, WHERE, aliases, and expressions
=====================================================================

A self-contained SQLite tutorial that progresses from absolute beginner
concepts to advanced SELECT techniques.

The examples use Python's standard-library sqlite3 module, so no external
packages or database server are required.

Topics covered:
    1. Database and relational concepts
    2. SELECT and FROM
    3. Selecting columns
    4. SELECT *
    5. Column aliases
    6. Table aliases
    7. Expressions
    8. Arithmetic, comparison, and logical expressions
    9. WHERE filtering
   10. NULL and three-valued logic
   11. Text, numeric, and date/time expressions
   12. CASE expressions
   13. DISTINCT
   14. ORDER BY and LIMIT as practical SELECT companions
   15. Aggregate expressions
   16. Correlated and scalar subqueries
   17. EXISTS and conditional filtering
   18. CTEs
   19. Window expressions
   20. Parameterized SQL and security
   21. Query plans and indexes
   22. Edge cases and common mistakes
   23. Testing and validation
   24. A practical reporting example
   25. Production-oriented query practices

The script intentionally prints results so it can be used as a study file.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Iterable, Sequence


# ---------------------------------------------------------------------------
# 1. Utility functions
# ---------------------------------------------------------------------------

def print_title(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def print_query(
    connection: sqlite3.Connection,
    sql: str,
    parameters: Sequence[object] = (),
    description: str | None = None,
) -> list[sqlite3.Row]:
    """
    Execute a SELECT statement and print its columns and rows.

    Row objects are converted to dictionaries for readability.
    """
    if description:
        print(f"\n{description}")

    print("\nSQL:")
    print(sql.strip())

    if parameters:
        print(f"Parameters: {tuple(parameters)}")

    cursor = connection.execute(sql, parameters)
    rows = cursor.fetchall()

    if cursor.description is None:
        print("Statement did not return a result set.")
        return rows

    column_names = [column[0] for column in cursor.description]
    print("Columns:", column_names)

    for row in rows:
        print(dict(row))

    print(f"Rows returned: {len(rows)}")
    return rows


def print_scalar(
    connection: sqlite3.Connection,
    sql: str,
    parameters: Sequence[object] = (),
    description: str | None = None,
) -> object:
    """Execute a query expected to return one value."""
    if description:
        print(f"\n{description}")

    row = connection.execute(sql, parameters).fetchone()

    if row is None:
        print("No row returned.")
        return None

    value = row[0]
    print("Result:", value)
    return value


def assert_query(
    connection: sqlite3.Connection,
    sql: str,
    expected: Iterable[tuple],
    parameters: Sequence[object] = (),
) -> None:
    """Small helper for executable query tests."""
    actual = [tuple(row) for row in connection.execute(sql, parameters).fetchall()]
    expected_list = list(expected)

    if actual != expected_list:
        raise AssertionError(
            f"Query result mismatch.\nExpected: {expected_list}\nActual: {actual}"
        )

    print("Test passed.")


# ---------------------------------------------------------------------------
# 2. Database setup
# ---------------------------------------------------------------------------

def create_database() -> sqlite3.Connection:
    """
    Create an in-memory relational database.

    SQLite is used because it is part of Python's standard library.
    The same SELECT fundamentals apply to major SQL databases, although
    individual functions and data types can differ between vendors.
    """
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE departments (
            department_id INTEGER PRIMARY KEY,
            department_name TEXT NOT NULL UNIQUE,
            location TEXT NOT NULL
        );

        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department_id INTEGER,
            job_title TEXT NOT NULL,
            salary REAL NOT NULL CHECK (salary >= 0),
            commission REAL,
            hire_date TEXT NOT NULL,
            manager_id INTEGER,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            FOREIGN KEY (department_id) REFERENCES departments(department_id),
            FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
        );

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            city TEXT NOT NULL,
            email TEXT,
            signup_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('active', 'inactive'))
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            amount REAL NOT NULL CHECK (amount >= 0),
            status TEXT NOT NULL CHECK (
                status IN ('pending', 'shipped', 'delivered', 'cancelled')
            ),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL CHECK (price >= 0),
            stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0)
        );

        CREATE INDEX idx_employees_department
            ON employees(department_id);

        CREATE INDEX idx_employees_salary
            ON employees(salary);

        CREATE INDEX idx_employees_hire_date
            ON employees(hire_date);

        CREATE INDEX idx_orders_customer
            ON orders(customer_id);

        CREATE INDEX idx_orders_order_date
            ON orders(order_date);
        """
    )

    departments = [
        (1, "Engineering", "Bengaluru"),
        (2, "Finance", "Mumbai"),
        (3, "Human Resources", "Delhi"),
        (4, "Sales", "Pune"),
        (5, "Cybersecurity", "Hyderabad"),
        (6, "Research", "Noida"),
    ]

    connection.executemany(
        """
        INSERT INTO departments
            (department_id, department_name, location)
        VALUES (?, ?, ?)
        """,
        departments,
    )

    employees = [
        (1, "Aarav", "Sharma", "aarav@example.com", 1, "Engineering Manager",
         145000, 15000, "2018-04-12", None, 1),
        (2, "Priya", "Verma", "priya@example.com", 1, "Senior Python Developer",
         120000, None, "2020-06-20", 1, 1),
        (3, "Rohan", "Mehta", "rohan@example.com", 1, "Data Engineer",
         98000, 5000, "2022-01-15", 1, 1),
        (4, "Neha", "Singh", "neha@example.com", 2, "Finance Analyst",
         82000, None, "2021-03-18", None, 1),
        (5, "Vikram", "Patel", "vikram@example.com", 2, "Finance Manager",
         110000, 10000, "2019-08-05", None, 1),
        (6, "Ananya", "Gupta", "ananya@example.com", 3, "HR Specialist",
         76000, None, "2023-02-10", None, 1),
        (7, "Kabir", "Joshi", "kabir@example.com", 4, "Sales Executive",
         70000, 12000, "2022-09-01", None, 1),
        (8, "Isha", "Nair", "isha@example.com", 4, "Sales Manager",
         105000, 25000, "2017-11-23", None, 1),
        (9, "Aditya", "Rao", "aditya@example.com", 5, "Security Analyst",
         102000, None, "2021-12-01", None, 1),
        (10, "Meera", "Iyer", "meera@example.com", 5, "Security Engineer",
         115000, 8000, "2020-10-11", 9, 1),
        (11, "Sahil", "Khan", "sahil@example.com", 6, "Research Scientist",
         125000, None, "2019-05-30", None, 1),
        (12, "Tanya", "Das", "tanya@example.com", None, "Consultant",
         90000, None, "2024-01-08", None, 1),
        (13, "Arjun", "Bose", "arjun@example.com", 1, "Junior Developer",
         58000, None, "2024-06-01", 2, 1),
        (14, "Pooja", "Malik", "pooja@example.com", 4, "Sales Executive",
         68000, 7000, "2023-07-15", 8, 0),
    ]

    connection.executemany(
        """
        INSERT INTO employees (
            employee_id, first_name, last_name, email, department_id,
            job_title, salary, commission, hire_date, manager_id, active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        employees,
    )

    customers = [
        (1, "Alpha Technologies", "Delhi", "alpha@example.com", "2024-01-10", "active"),
        (2, "Bright Retail", "Mumbai", "bright@example.com", "2024-02-15", "active"),
        (3, "Core Systems", "Bengaluru", "core@example.com", "2024-03-20", "active"),
        (4, "Delta Foods", "Pune", None, "2024-04-05", "inactive"),
        (5, "Elite Services", "Lucknow", "elite@example.com", "2024-05-17", "active"),
    ]

    connection.executemany(
        """
        INSERT INTO customers
            (customer_id, customer_name, city, email, signup_date, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        customers,
    )

    orders = [
        (1, 1, "2025-01-05", 12000, "delivered"),
        (2, 1, "2025-02-10", 18000, "delivered"),
        (3, 2, "2025-01-15", 7500, "shipped"),
        (4, 2, "2025-03-12", 22000, "delivered"),
        (5, 3, "2025-02-20", 45000, "pending"),
        (6, 3, "2025-03-01", 30000, "cancelled"),
        (7, 4, "2025-01-22", 5000, "delivered"),
        (8, 5, "2025-03-15", 16000, "delivered"),
    ]

    connection.executemany(
        """
        INSERT INTO orders
            (order_id, customer_id, order_date, amount, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        orders,
    )

    products = [
        (1, "Laptop", "Electronics", 85000, 12),
        (2, "Monitor", "Electronics", 22000, 25),
        (3, "Keyboard", "Accessories", 3500, 80),
        (4, "Security Scanner", "Cybersecurity", 125000, 7),
        (5, "Cloud License", "Software", 45000, 0),
        (6, "Desk Chair", "Furniture", 18000, 15),
    ]

    connection.executemany(
        """
        INSERT INTO products
            (product_id, product_name, category, price, stock_quantity)
        VALUES (?, ?, ?, ?, ?)
        """,
        products,
    )

    return connection


# ---------------------------------------------------------------------------
# 3. Fundamental SQL concepts
# ---------------------------------------------------------------------------

def demonstrate_database_fundamentals(connection: sqlite3.Connection) -> None:
    print_title("1. Database and Relational Fundamentals")

    print(
        """
A relational database organizes information into tables.

A table consists of:
    - rows: individual records
    - columns: attributes describing each record
    - a schema: definitions and constraints for the table

Examples in this database:
    employees       -> employee records
    departments     -> organizational units
    customers       -> customer records
    orders          -> sales transactions
    products        -> product inventory

A SELECT statement retrieves data without changing the stored rows.

The basic conceptual form is:

    SELECT column1, column2
    FROM table_name;

SQL is declarative. You describe the result you want rather than manually
telling the database which physical operations to perform.
"""
    )

    print_query(
        connection,
        """
        SELECT employee_id, first_name, last_name
        FROM employees;
        """,
        description="A first SELECT query.",
    )


# ---------------------------------------------------------------------------
# 4. SELECT and FROM
# ---------------------------------------------------------------------------

def demonstrate_select_and_from(connection: sqlite3.Connection) -> None:
    print_title("2. SELECT and FROM")

    print_query(
        connection,
        """
        SELECT first_name
        FROM employees;
        """,
        description="Selecting one column.",
    )

    print_query(
        connection,
        """
        SELECT first_name, last_name, job_title
        FROM employees;
        """,
        description="Selecting several columns.",
    )

    print_query(
        connection,
        """
        SELECT *
        FROM departments;
        """,
        description="SELECT * returns every column.",
    )

    print(
        """
SELECT * is convenient for exploration, but explicit columns are generally
better in production queries because they:
    - document which fields are required
    - avoid transferring unnecessary data
    - reduce accidental dependency on schema changes
    - make application interfaces more stable
"""
    )


# ---------------------------------------------------------------------------
# 5. Column aliases
# ---------------------------------------------------------------------------

def demonstrate_column_aliases(connection: sqlite3.Connection) -> None:
    print_title("3. Column Aliases")

    print_query(
        connection,
        """
        SELECT
            first_name AS first,
            last_name AS last,
            job_title AS role
        FROM employees;
        """,
        description="AS gives result columns readable names.",
    )

    # AS is optional for column aliases in SQLite and many SQL dialects.
    print_query(
        connection,
        """
        SELECT
            first_name first,
            last_name last
        FROM employees;
        """,
        description="AS may be omitted for a simple column alias.",
    )

    print_query(
        connection,
        """
        SELECT
            first_name || ' ' || last_name AS full_name
        FROM employees;
        """,
        description="An expression can also receive an alias.",
    )

    print(
        """
Important distinction:
    column alias -> changes the name displayed in the result
    table alias  -> gives a temporary name to a table reference

An alias does not rename the underlying database column.
"""
    )


# ---------------------------------------------------------------------------
# 6. Table aliases
# ---------------------------------------------------------------------------

def demonstrate_table_aliases(connection: sqlite3.Connection) -> None:
    print_title("4. Table Aliases")

    print_query(
        connection,
        """
        SELECT
            e.employee_id,
            e.first_name,
            e.last_name,
            e.salary
        FROM employees AS e;
        """,
        description="e is a table alias.",
    )

    # Table aliases become especially useful when the same table is referenced
    # more than once.
    print_query(
        connection,
        """
        SELECT
            employee.first_name || ' ' || employee.last_name AS employee_name,
            manager.first_name || ' ' || manager.last_name AS manager_name
        FROM employees AS employee
        LEFT JOIN employees AS manager
            ON employee.manager_id = manager.employee_id;
        """,
        description="Self-reference: one table appears as two aliases.",
    )


# ---------------------------------------------------------------------------
# 7. Expressions
# ---------------------------------------------------------------------------

def demonstrate_expressions(connection: sqlite3.Connection) -> None:
    print_title("5. Expressions")

    print(
        """
An expression is a piece of SQL that produces a value.

Examples:
    salary
    salary * 12
    first_name || ' ' || last_name
    salary > 100000
    commission IS NULL
    CASE WHEN salary >= 100000 THEN 'High' ELSE 'Standard' END

Expressions can appear in SELECT lists, WHERE predicates, ORDER BY clauses,
CASE expressions, aggregate calculations, and other SQL constructs.
"""
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            salary,
            salary * 12 AS annual_salary,
            salary + COALESCE(commission, 0) AS total_compensation
        FROM employees;
        """,
        description="Arithmetic expressions.",
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            salary,
            salary / 12.0 AS monthly_salary,
            salary * 0.10 AS estimated_ten_percent_bonus
        FROM employees;
        """,
        description="Division and multiplication.",
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            last_name,
            first_name || ' ' || last_name AS full_name,
            UPPER(last_name) AS uppercase_last_name,
            LENGTH(first_name) AS first_name_length
        FROM employees;
        """,
        description="String expressions and functions.",
    )


# ---------------------------------------------------------------------------
# 8. WHERE
# ---------------------------------------------------------------------------

def demonstrate_where(connection: sqlite3.Connection) -> None:
    print_title("6. WHERE Filtering")

    print(
        """
WHERE restricts which rows qualify for the result.

Conceptually:

    SELECT columns
    FROM table
    WHERE condition;

The condition is a predicate. A row is returned when the predicate evaluates
to TRUE. SQL's treatment of NULL introduces a third logical state, UNKNOWN.
"""
    )

    print_query(
        connection,
        """
        SELECT employee_id, first_name, salary
        FROM employees
        WHERE salary > 100000;
        """,
        description="Comparison predicate.",
    )

    print_query(
        connection,
        """
        SELECT employee_id, first_name, salary
        FROM employees
        WHERE salary >= 80000
          AND salary <= 120000;
        """,
        description="AND combines predicates.",
    )

    print_query(
        connection,
        """
        SELECT employee_id, first_name, department_id
        FROM employees
        WHERE department_id = 1
           OR department_id = 5;
        """,
        description="OR allows either predicate to qualify.",
    )

    print_query(
        connection,
        """
        SELECT employee_id, first_name, salary
        FROM employees
        WHERE salary BETWEEN 80000 AND 120000;
        """,
        description="BETWEEN is inclusive at both boundaries.",
    )

    print_query(
        connection,
        """
        SELECT employee_id, first_name, department_id
        FROM employees
        WHERE department_id IN (1, 4, 5);
        """,
        description="IN checks membership in a set of values.",
    )

    print_query(
        connection,
        """
        SELECT employee_id, first_name, job_title
        FROM employees
        WHERE job_title LIKE '%Engineer%';
        """,
        description="LIKE performs pattern matching.",
    )

    print_query(
        connection,
        """
        SELECT employee_id, first_name, job_title
        FROM employees
        WHERE job_title NOT LIKE '%Manager%';
        """,
        description="NOT can negate a predicate.",
    )


# ---------------------------------------------------------------------------
# 9. Logical precedence
# ---------------------------------------------------------------------------

def demonstrate_logical_precedence(connection: sqlite3.Connection) -> None:
    print_title("7. Logical Operators and Precedence")

    print(
        """
When several logical operators appear together, parentheses make the
intended meaning explicit.

A common precedence ordering is:

    NOT
    AND
    OR

Therefore:

    A OR B AND C

is interpreted as:

    A OR (B AND C)

not:

    (A OR B) AND C

Do not rely on readers remembering precedence. Parenthesize complicated
business rules.
"""
    )

    print_query(
        connection,
        """
        SELECT first_name, department_id, salary
        FROM employees
        WHERE department_id = 1
           OR department_id = 5
          AND salary > 100000;
        """,
        description="AND binds more tightly than OR.",
    )

    print_query(
        connection,
        """
        SELECT first_name, department_id, salary
        FROM employees
        WHERE (department_id = 1 OR department_id = 5)
          AND salary > 100000;
        """,
        description="Parentheses explicitly change the logical grouping.",
    )


# ---------------------------------------------------------------------------
# 10. NULL
# ---------------------------------------------------------------------------

def demonstrate_null(connection: sqlite3.Connection) -> None:
    print_title("8. NULL and Three-Valued Logic")

    print(
        """
NULL means an absent, unknown, or not-applicable value. It is not:
    - zero
    - an empty string
    - FALSE

A crucial rule is:

    column = NULL

does not test for NULL.

Use:

    column IS NULL
    column IS NOT NULL

SQL comparisons involving NULL can produce UNKNOWN rather than TRUE or FALSE.
WHERE returns only rows for which the predicate is TRUE.
"""
    )

    print_query(
        connection,
        """
        SELECT employee_id, first_name, commission
        FROM employees
        WHERE commission IS NULL;
        """,
        description="Correct NULL test.",
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            commission,
            COALESCE(commission, 0) AS commission_or_zero
        FROM employees;
        """,
        description="COALESCE substitutes a fallback value.",
    )

    # Demonstrate why "=" does not work as a NULL test.
    null_comparison_count = print_scalar(
        connection,
        """
        SELECT COUNT(*)
        FROM employees
        WHERE commission = NULL;
        """,
        description="commission = NULL returns no qualifying rows.",
    )

    assert null_comparison_count == 0


# ---------------------------------------------------------------------------
# 11. CASE expressions
# ---------------------------------------------------------------------------

def demonstrate_case(connection: sqlite3.Connection) -> None:
    print_title("9. CASE Expressions")

    print(
        """
CASE is SQL's conditional expression.

Searched CASE form:

    CASE
        WHEN condition1 THEN result1
        WHEN condition2 THEN result2
        ELSE default_result
    END

The first matching WHEN branch is selected.
"""
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            salary,
            CASE
                WHEN salary >= 120000 THEN 'Executive'
                WHEN salary >= 100000 THEN 'Senior'
                WHEN salary >= 80000 THEN 'Mid-level'
                ELSE 'Entry-level'
            END AS salary_band
        FROM employees;
        """,
        description="Classifying employees with CASE.",
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            active,
            CASE active
                WHEN 1 THEN 'Active'
                WHEN 0 THEN 'Inactive'
                ELSE 'Unknown'
            END AS employment_status
        FROM employees;
        """,
        description="Simple CASE form.",
    )


# ---------------------------------------------------------------------------
# 12. DISTINCT
# ---------------------------------------------------------------------------

def demonstrate_distinct(connection: sqlite3.Connection) -> None:
    print_title("10. DISTINCT")

    print_query(
        connection,
        """
        SELECT DISTINCT department_id
        FROM employees;
        """,
        description="DISTINCT removes duplicate result rows.",
    )

    print_query(
        connection,
        """
        SELECT DISTINCT job_title
        FROM employees;
        """,
        description="Unique job titles.",
    )

    print_query(
        connection,
        """
        SELECT DISTINCT department_id, active
        FROM employees;
        """,
        description="DISTINCT applies to the complete selected combination.",
    )

    print(
        """
DISTINCT is not a general-purpose substitute for fixing duplicate rows
caused by an incorrect join. If a join creates unintended multiplicity,
fix the join rather than hiding the problem with DISTINCT.
"""
    )


# ---------------------------------------------------------------------------
# 13. ORDER BY and LIMIT
# ---------------------------------------------------------------------------

def demonstrate_order_and_limit(connection: sqlite3.Connection) -> None:
    print_title("11. ORDER BY and LIMIT as SELECT Companions")

    print_query(
        connection,
        """
        SELECT first_name, salary
        FROM employees
        ORDER BY salary DESC;
        """,
        description="Descending salary order.",
    )

    print_query(
        connection,
        """
        SELECT first_name, salary
        FROM employees
        ORDER BY salary ASC, first_name ASC;
        """,
        description="Multiple sort keys.",
    )

    print_query(
        connection,
        """
        SELECT first_name, salary
        FROM employees
        ORDER BY salary DESC
        LIMIT 5;
        """,
        description="Top five salaries.",
    )

    print_query(
        connection,
        """
        SELECT first_name, salary
        FROM employees
        ORDER BY salary DESC
        LIMIT 3 OFFSET 2;
        """,
        description="Pagination-style LIMIT/OFFSET.",
    )

    print(
        """
A query without ORDER BY does not guarantee a meaningful business order.
Physical row order is not a substitute for explicit sorting.
"""
    )


# ---------------------------------------------------------------------------
# 14. Aggregate expressions
# ---------------------------------------------------------------------------

def demonstrate_aggregates(connection: sqlite3.Connection) -> None:
    print_title("12. Aggregate Expressions")

    print(
        """
Aggregate functions reduce multiple input rows to a calculated value.

Common aggregates:
    COUNT
    SUM
    AVG
    MIN
    MAX

Important COUNT distinction:
    COUNT(*) counts rows.
    COUNT(column) counts non-NULL values in that column.
"""
    )

    print_query(
        connection,
        """
        SELECT
            COUNT(*) AS employee_count,
            AVG(salary) AS average_salary,
            MIN(salary) AS minimum_salary,
            MAX(salary) AS maximum_salary,
            SUM(salary) AS total_salary
        FROM employees;
        """,
        description="Aggregates over the entire employee table.",
    )

    print_query(
        connection,
        """
        SELECT
            COUNT(*) AS all_rows,
            COUNT(commission) AS employees_with_commission
        FROM employees;
        """,
        description="COUNT(*) versus COUNT(column).",
    )

    print_query(
        connection,
        """
        SELECT
            department_id,
            COUNT(*) AS employee_count,
            AVG(salary) AS average_salary
        FROM employees
        GROUP BY department_id;
        """,
        description="Grouped aggregate expressions.",
    )

    print_query(
        connection,
        """
        SELECT
            department_id,
            COUNT(*) AS employee_count,
            AVG(salary) AS average_salary
        FROM employees
        GROUP BY department_id
        HAVING COUNT(*) >= 2;
        """,
        description="HAVING filters groups after aggregation.",
    )


# ---------------------------------------------------------------------------
# 15. SELECT evaluation model
# ---------------------------------------------------------------------------

def demonstrate_query_processing(connection: sqlite3.Connection) -> None:
    print_title("13. Conceptual SQL Query Processing Order")

    print(
        """
Written SQL usually begins with SELECT, but a useful conceptual processing
model is:

    FROM / JOIN
    WHERE
    GROUP BY
    HAVING
    SELECT
    DISTINCT
    ORDER BY
    LIMIT / OFFSET

This explains several important behaviors.

For example, a SELECT alias generally cannot be referenced in WHERE because
WHERE is conceptually evaluated before the SELECT list.

Use the original expression or move the query into a subquery/CTE when an
alias needs to become an input to a later query level.
"""
    )

    # SQLite permits aliases in ORDER BY, which is why this works.
    print_query(
        connection,
        """
        SELECT
            first_name,
            salary * 12 AS annual_salary
        FROM employees
        ORDER BY annual_salary DESC;
        """,
        description="SELECT alias used by ORDER BY.",
    )

    # A derived table creates a new query level where the alias is now a
    # genuine column of the intermediate result.
    print_query(
        connection,
        """
        SELECT
            employee_name,
            annual_salary
        FROM (
            SELECT
                first_name || ' ' || last_name AS employee_name,
                salary * 12 AS annual_salary
            FROM employees
        )
        WHERE annual_salary > 1200000;
        """,
        description="A subquery makes an expression alias available to an outer WHERE.",
    )


# ---------------------------------------------------------------------------
# 16. Joins and qualified column references
# ---------------------------------------------------------------------------

def demonstrate_joins(connection: sqlite3.Connection) -> None:
    print_title("14. SELECT with Multiple Tables")

    print(
        """
SELECT becomes more powerful when information is distributed across related
tables.

A qualified column reference has the form:

    table_alias.column_name

Qualification prevents ambiguity and makes relationships explicit.
"""
    )

    print_query(
        connection,
        """
        SELECT
            e.first_name,
            e.last_name,
            d.department_name,
            d.location
        FROM employees AS e
        INNER JOIN departments AS d
            ON e.department_id = d.department_id;
        """,
        description="INNER JOIN combines matching employee and department rows.",
    )

    print_query(
        connection,
        """
        SELECT
            e.first_name,
            e.last_name,
            d.department_name
        FROM employees AS e
        LEFT JOIN departments AS d
            ON e.department_id = d.department_id;
        """,
        description="LEFT JOIN preserves employees without a department.",
    )

    print(
        """
The consultant Tanya has no department. INNER JOIN excludes that row because
there is no matching department. LEFT JOIN retains the employee and produces
NULL values for the department columns.

This distinction is essential when deciding whether missing relationships
should eliminate rows or remain visible.
"""
    )


# ---------------------------------------------------------------------------
# 17. Scalar subqueries
# ---------------------------------------------------------------------------

def demonstrate_scalar_subqueries(connection: sqlite3.Connection) -> None:
    print_title("15. Scalar Subqueries")

    print_query(
        connection,
        """
        SELECT
            first_name,
            salary,
            (
                SELECT AVG(salary)
                FROM employees
            ) AS company_average_salary
        FROM employees;
        """,
        description="A scalar subquery produces one value used by each outer row.",
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            salary,
            salary - (
                SELECT AVG(salary)
                FROM employees
            ) AS difference_from_average
        FROM employees;
        """,
        description="Comparing each row with a scalar aggregate.",
    )


# ---------------------------------------------------------------------------
# 18. EXISTS and conditional filtering
# ---------------------------------------------------------------------------

def demonstrate_exists(connection: sqlite3.Connection) -> None:
    print_title("16. EXISTS and Correlated Subqueries")

    print(
        """
EXISTS tests whether a subquery produces at least one row.

It is particularly useful for questions such as:

    Which customers have at least one order?

A correlated subquery refers to a column from the current outer row.
"""
    )

    print_query(
        connection,
        """
        SELECT
            c.customer_id,
            c.customer_name
        FROM customers AS c
        WHERE EXISTS (
            SELECT 1
            FROM orders AS o
            WHERE o.customer_id = c.customer_id
        );
        """,
        description="Customers who have at least one order.",
    )

    print_query(
        connection,
        """
        SELECT
            c.customer_id,
            c.customer_name
        FROM customers AS c
        WHERE NOT EXISTS (
            SELECT 1
            FROM orders AS o
            WHERE o.customer_id = c.customer_id
        );
        """,
        description="Customers with no orders.",
    )


# ---------------------------------------------------------------------------
# 19. CTEs
# ---------------------------------------------------------------------------

def demonstrate_ctes(connection: sqlite3.Connection) -> None:
    print_title("17. Common Table Expressions")

    print(
        """
A Common Table Expression (CTE) is introduced with WITH.

CTEs provide a named intermediate query result and can make complicated
queries easier to understand.

They are especially useful when:
    - an intermediate calculation deserves a name
    - a query has multiple logical stages
    - the same derived result is referenced more than once
    - recursive processing is required

A CTE is not automatically a permanent table.
"""
    )

    print_query(
        connection,
        """
        WITH employee_compensation AS (
            SELECT
                employee_id,
                first_name,
                last_name,
                salary + COALESCE(commission, 0) AS total_compensation
            FROM employees
        )
        SELECT
            first_name,
            last_name,
            total_compensation
        FROM employee_compensation
        WHERE total_compensation >= 110000
        ORDER BY total_compensation DESC;
        """,
        description="CTE containing a derived compensation calculation.",
    )


# ---------------------------------------------------------------------------
# 20. Window expressions
# ---------------------------------------------------------------------------

def demonstrate_window_functions(connection: sqlite3.Connection) -> None:
    print_title("18. Advanced SELECT: Window Expressions")

    print(
        """
Window functions calculate values across related rows without collapsing
those rows into a single aggregate row.

GROUP BY:
    multiple input rows -> fewer result rows

Window function:
    multiple input rows -> same number of result rows, plus calculations

Common window functions include:
    ROW_NUMBER
    RANK
    DENSE_RANK
    LAG
    LEAD
    SUM(...) OVER (...)
    AVG(...) OVER (...)

PARTITION BY defines independent groups for the window calculation.
ORDER BY defines the logical order inside the window.
"""
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            department_id,
            salary,
            ROW_NUMBER() OVER (
                PARTITION BY department_id
                ORDER BY salary DESC
            ) AS salary_position
        FROM employees
        WHERE department_id IS NOT NULL
        ORDER BY department_id, salary_position;
        """,
        description="Ranking employees within each department.",
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            salary,
            AVG(salary) OVER () AS company_average,
            salary - AVG(salary) OVER () AS difference_from_company_average
        FROM employees;
        """,
        description="Window average without collapsing employee rows.",
    )

    print_query(
        connection,
        """
        SELECT
            order_id,
            customer_id,
            order_date,
            amount,
            SUM(amount) OVER (
                PARTITION BY customer_id
                ORDER BY order_date, order_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS customer_running_total
        FROM orders
        ORDER BY customer_id, order_date, order_id;
        """,
        description="Running total per customer.",
    )


# ---------------------------------------------------------------------------
# 21. Date and text expressions
# ---------------------------------------------------------------------------

def demonstrate_text_and_dates(connection: sqlite3.Connection) -> None:
    print_title("19. Text and Date/Time Expressions")

    print(
        """
SQL date/time behavior differs substantially between database systems.
SQLite stores dates commonly as TEXT, REAL, or INTEGER rather than using a
dedicated DATE type.

The examples below use ISO-style YYYY-MM-DD text, which sorts chronologically.
"""
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            last_name,
            LOWER(email) AS normalized_email,
            SUBSTR(first_name, 1, 3) AS first_three_characters
        FROM employees;
        """,
        description="Common string transformations.",
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            hire_date,
            strftime('%Y', hire_date) AS hire_year,
            strftime('%m', hire_date) AS hire_month
        FROM employees
        ORDER BY hire_date;
        """,
        description="Extracting date components in SQLite.",
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            hire_date
        FROM employees
        WHERE hire_date >= '2022-01-01'
          AND hire_date < '2025-01-01'
        ORDER BY hire_date;
        """,
        description="Half-open date interval: >= start and < end.",
    )


# ---------------------------------------------------------------------------
# 22. Boolean expressions
# ---------------------------------------------------------------------------

def demonstrate_boolean_expressions(connection: sqlite3.Connection) -> None:
    print_title("20. Boolean and Comparison Expressions")

    print_query(
        connection,
        """
        SELECT
            first_name,
            salary,
            salary >= 100000 AS is_high_earner
        FROM employees;
        """,
        description="A comparison can itself be returned as an expression.",
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            salary,
            CASE
                WHEN salary >= 100000 AND active = 1 THEN 'Priority'
                ELSE 'Standard'
            END AS employee_segment
        FROM employees;
        """,
        description="Combining multiple conditions inside CASE.",
    )


# ---------------------------------------------------------------------------
# 23. Parameterized queries and SQL injection
# ---------------------------------------------------------------------------

def demonstrate_parameterized_queries(connection: sqlite3.Connection) -> None:
    print_title("21. Parameterized SELECT Queries and Security")

    print(
        """
Never construct SQL by directly concatenating untrusted input.

Unsafe conceptual pattern:

    SELECT ... WHERE email = '""" + "{user_input}" + """'

A malicious value can change the meaning of the SQL statement.

Use parameterized queries instead. The SQL structure remains separate from
the supplied data.
"""
    )

    user_supplied_salary = 100000

    print_query(
        connection,
        """
        SELECT employee_id, first_name, salary
        FROM employees
        WHERE salary >= ?
        ORDER BY salary DESC;
        """,
        parameters=(user_supplied_salary,),
        description="Safe parameter binding with sqlite3.",
    )

    user_supplied_department = 4

    print_query(
        connection,
        """
        SELECT employee_id, first_name, job_title
        FROM employees
        WHERE department_id = ?;
        """,
        parameters=(user_supplied_department,),
        description="Another parameterized filter.",
    )

    print(
        """
Parameters represent values, not SQL identifiers. You generally cannot bind
a table name or column name with a normal value placeholder.

If dynamic identifiers are required, validate them against a strict allowlist
before constructing SQL.
"""
    )


# ---------------------------------------------------------------------------
# 24. Dynamic query construction with an allowlist
# ---------------------------------------------------------------------------

def demonstrate_safe_dynamic_sort(connection: sqlite3.Connection) -> None:
    print_title("22. Safe Dynamic SQL for Identifiers")

    allowed_sort_columns = {
        "name": "last_name",
        "salary": "salary",
        "hire_date": "hire_date",
    }

    requested_sort = "salary"

    # The requested value is not inserted blindly. It is translated through
    # an allowlist controlled by application code.
    sort_column = allowed_sort_columns.get(requested_sort)

    if sort_column is None:
        raise ValueError("Unsupported sort field.")

    sql = f"""
        SELECT first_name, last_name, salary, hire_date
        FROM employees
        ORDER BY {sort_column} DESC;
    """

    print_query(
        connection,
        sql,
        description="Dynamic ORDER BY using a strict allowlist.",
    )


# ---------------------------------------------------------------------------
# 25. Query plans and performance
# ---------------------------------------------------------------------------

def demonstrate_query_plans(connection: sqlite3.Connection) -> None:
    print_title("23. Performance and EXPLAIN QUERY PLAN")

    print(
        """
SELECT performance depends on factors such as:
    - number of rows
    - predicates
    - joins
    - indexes
    - sorting
    - grouping
    - data distribution
    - selected columns
    - database statistics
    - query optimizer behavior

Indexes can accelerate selective lookups, but indexes also consume storage
and impose write/update maintenance costs.

EXPLAIN QUERY PLAN gives SQLite's high-level execution strategy.
"""
    )

    print_query(
        connection,
        """
        EXPLAIN QUERY PLAN
        SELECT employee_id, first_name, salary
        FROM employees
        WHERE salary >= 100000;
        """,
        description="Query plan for an indexed salary predicate.",
    )

    print_query(
        connection,
        """
        EXPLAIN QUERY PLAN
        SELECT employee_id, first_name
        FROM employees
        WHERE department_id = 1;
        """,
        description="Query plan for an indexed department predicate.",
    )

    print(
        """
Performance practices:
    1. Select only required columns.
    2. Filter as early as practical.
    3. Index columns used frequently for selective filtering or joins.
    4. Inspect execution plans for expensive production queries.
    5. Avoid indexes that provide little selectivity or excessive maintenance.
    6. Measure with realistic data rather than assuming an optimization works.
"""
    )


# ---------------------------------------------------------------------------
# 26. Edge cases
# ---------------------------------------------------------------------------

def demonstrate_edge_cases(connection: sqlite3.Connection) -> None:
    print_title("24. Important Edge Cases")

    print(
        """
Edge cases frequently produce incorrect SQL because SQL differs from
ordinary programming-language intuition.
"""
    )

    # Empty result sets are valid. SELECT does not guarantee a row.
    print_query(
        connection,
        """
        SELECT employee_id, first_name
        FROM employees
        WHERE salary > 1000000;
        """,
        description="A valid query may return zero rows.",
    )

    # NULL propagation in arithmetic.
    print_query(
        connection,
        """
        SELECT
            first_name,
            commission,
            commission * 2 AS doubled_commission
        FROM employees
        WHERE commission IS NULL
        LIMIT 3;
        """,
        description="Arithmetic involving NULL produces NULL.",
    )

    # COALESCE prevents NULL propagation when a business default is appropriate.
    print_query(
        connection,
        """
        SELECT
            first_name,
            COALESCE(commission, 0) * 2 AS doubled_commission_defaulted
        FROM employees
        WHERE commission IS NULL
        LIMIT 3;
        """,
        description="COALESCE supplies a business-defined default.",
    )

    # Division by zero behavior varies across SQL engines. SQLite produces NULL
    # for numeric division by zero rather than raising the same error as some
    # other database systems.
    print_query(
        connection,
        """
        SELECT
            10 / 2.0 AS normal_division,
            10 / 0.0 AS sqlite_division_by_zero;
        """,
        description="Division-by-zero behavior is database-specific.",
    )

    # NULL ordering is also vendor-dependent in default ORDER BY behavior.
    print_query(
        connection,
        """
        SELECT
            first_name,
            commission
        FROM employees
        ORDER BY commission ASC;
        """,
        description="Default NULL ordering should not be assumed across databases.",
    )


# ---------------------------------------------------------------------------
# 27. Common mistakes
# ---------------------------------------------------------------------------

def demonstrate_common_mistakes(connection: sqlite3.Connection) -> None:
    print_title("25. Common SELECT Mistakes")

    print(
        """
Mistake 1: Using SELECT * in stable application interfaces.
Better: explicitly select required columns.

Mistake 2: Testing NULL with =.
Wrong:
    WHERE commission = NULL
Correct:
    WHERE commission IS NULL

Mistake 3: Forgetting operator precedence.
Better:
    use parentheses for business logic.

Mistake 4: Using DISTINCT to hide an incorrect join.
Better:
    determine why rows are duplicated.

Mistake 5: Assuming row order without ORDER BY.
Better:
    specify an explicit ordering.

Mistake 6: Comparing dates as inconsistent strings.
Better:
    use a consistent database-supported date representation.

Mistake 7: Building SQL by concatenating user input.
Better:
    use parameters for values and validated allowlists for identifiers.

Mistake 8: Assuming SQL dialects are identical.
Better:
    verify functions, data types, NULL ordering, date handling, and
    optimizer behavior for the target database.

Mistake 9: Applying a function to an indexed column unnecessarily.
For example:
    WHERE LOWER(email) = ?
may prevent use of a normal index depending on the database and index design.
Better:
    normalize data at ingestion or create an appropriate functional index
    when supported and justified.
"""
    )

    # Demonstrate explicit predicate grouping as a corrective pattern.
    print_query(
        connection,
        """
        SELECT first_name, department_id, salary
        FROM employees
        WHERE (department_id IN (1, 5))
          AND salary >= 100000
        ORDER BY salary DESC;
        """,
        description="Explicit grouping avoids ambiguity.",
    )


# ---------------------------------------------------------------------------
# 28. Practical reporting query
# ---------------------------------------------------------------------------

def demonstrate_practical_report(connection: sqlite3.Connection) -> None:
    print_title("26. Practical Multi-Concept Reporting Query")

    print(
        """
The following report combines:
    - SELECT
    - aliases
    - joins
    - expressions
    - COALESCE
    - CASE
    - WHERE
    - ORDER BY

It shows how basic SELECT concepts compose into a useful business query.
"""
    )

    print_query(
        connection,
        """
        SELECT
            e.employee_id,
            e.first_name || ' ' || e.last_name AS employee_name,
            d.department_name AS department,
            e.job_title,
            e.salary,
            COALESCE(e.commission, 0) AS commission,
            e.salary + COALESCE(e.commission, 0) AS total_compensation,
            CASE
                WHEN e.salary >= 120000 THEN 'A'
                WHEN e.salary >= 90000 THEN 'B'
                ELSE 'C'
            END AS compensation_band
        FROM employees AS e
        LEFT JOIN departments AS d
            ON e.department_id = d.department_id
        WHERE e.active = 1
          AND e.salary >= 70000
        ORDER BY total_compensation DESC, employee_name ASC;
        """,
        description="A production-style employee compensation report.",
    )


# ---------------------------------------------------------------------------
# 29. Advanced customer/order report
# ---------------------------------------------------------------------------

def demonstrate_advanced_report(connection: sqlite3.Connection) -> None:
    print_title("27. Advanced Customer and Order Analysis")

    print_query(
        connection,
        """
        SELECT
            c.customer_name,
            c.city,
            COUNT(o.order_id) AS order_count,
            COALESCE(SUM(o.amount), 0) AS total_order_value,
            COALESCE(AVG(o.amount), 0) AS average_order_value,
            MAX(o.order_date) AS most_recent_order
        FROM customers AS c
        LEFT JOIN orders AS o
            ON c.customer_id = o.customer_id
        GROUP BY
            c.customer_id,
            c.customer_name,
            c.city
        ORDER BY total_order_value DESC;
        """,
        description="Customer-level sales report preserving customers with no orders.",
    )

    print_query(
        connection,
        """
        WITH customer_totals AS (
            SELECT
                c.customer_id,
                c.customer_name,
                COALESCE(SUM(o.amount), 0) AS total_value
            FROM customers AS c
            LEFT JOIN orders AS o
                ON c.customer_id = o.customer_id
            GROUP BY c.customer_id, c.customer_name
        )
        SELECT
            customer_name,
            total_value,
            CASE
                WHEN total_value >= 40000 THEN 'Platinum'
                WHEN total_value >= 20000 THEN 'Gold'
                WHEN total_value > 0 THEN 'Silver'
                ELSE 'No purchases'
            END AS customer_segment
        FROM customer_totals
        ORDER BY total_value DESC;
        """,
        description="CTE plus CASE for customer segmentation.",
    )


# ---------------------------------------------------------------------------
# 30. Expressions versus filtering
# ---------------------------------------------------------------------------

def demonstrate_expression_boundaries(connection: sqlite3.Connection) -> None:
    print_title("28. Expressions in SELECT Versus WHERE")

    print(
        """
A SELECT expression controls what value is returned.

A WHERE expression controls which rows survive.

These are different responsibilities.

Example:
    SELECT salary * 12 AS annual_salary
    FROM employees
    WHERE salary >= 100000;

The SELECT expression transforms qualifying rows. WHERE determines
qualification before the final projection.
"""
    )

    print_query(
        connection,
        """
        SELECT
            first_name,
            salary,
            salary * 12 AS annual_salary
        FROM employees
        WHERE salary >= 100000;
        """,
        description="Filtering on the source column and projecting a derived value.",
    )


# ---------------------------------------------------------------------------
# 31. Testing SELECT statements
# ---------------------------------------------------------------------------

def demonstrate_query_testing(connection: sqlite3.Connection) -> None:
    print_title("29. Testing and Validation")

    print(
        """
SELECT statements should be tested against known conditions.

Useful checks include:
    - expected number of rows
    - expected columns
    - boundary values
    - NULL behavior
    - duplicate behavior
    - empty result sets
    - ordering when order matters
    - join behavior for missing relationships
"""
    )

    assert_query(
        connection,
        """
        SELECT COUNT(*)
        FROM employees
        WHERE active = 1;
        """,
        [(13,)],
    )

    assert_query(
        connection,
        """
        SELECT first_name
        FROM employees
        WHERE employee_id = 1;
        """,
        [("Aarav",)],
    )

    assert_query(
        connection,
        """
        SELECT COUNT(*)
        FROM employees
        WHERE department_id IS NULL;
        """,
        [(1,)],
    )

    assert_query(
        connection,
        """
        SELECT MIN(salary)
        FROM employees;
        """,
        [(58000.0,)],
    )

    # Boundary test: BETWEEN includes both endpoints.
    assert_query(
        connection,
        """
        SELECT COUNT(*)
        FROM employees
        WHERE salary BETWEEN 82000 AND 82000;
        """,
        [(1,)],
    )

    # Empty result test.
    assert_query(
        connection,
        """
        SELECT COUNT(*)
        FROM employees
        WHERE salary > 9999999;
        """,
        [(0,)],
    )


# ---------------------------------------------------------------------------
# 32. SQL dialect considerations
# ---------------------------------------------------------------------------

def demonstrate_dialect_considerations() -> None:
    print_title("30. SQL Dialect and Portability Considerations")

    print(
        """
SQL is standardized, but real database systems implement dialect-specific
features.

SQLite, PostgreSQL, MySQL, SQL Server, and Oracle differ in areas such as:
    - string concatenation syntax
    - date/time functions
    - data types
    - identifier quoting
    - LIMIT/TOP/FETCH syntax
    - NULL ordering defaults
    - regular expression support
    - JSON features
    - optimizer behavior
    - locking and transaction semantics

Portable SQL should prefer standard constructs when practical, but production
code should be written and tested against the actual target database.

This tutorial uses SQLite syntax intentionally because it is executable with
Python's standard library.
"""
    )


# ---------------------------------------------------------------------------
# 33. SQL style
# ---------------------------------------------------------------------------

def demonstrate_sql_style() -> None:
    print_title("31. SQL Style and Maintainability")

    print(
        """
Readable SQL is easier to validate.

Recommended style:
    - put major clauses on separate lines
    - use meaningful aliases
    - qualify columns when multiple tables are involved
    - keep complex CASE expressions vertically formatted
    - use explicit column lists
    - use parentheses around complicated Boolean logic
    - give derived expressions meaningful aliases
    - keep naming conventions consistent

Poor formatting can hide logical errors even when the SQL is syntactically
valid.
"""
    )


# ---------------------------------------------------------------------------
# 34. Production considerations
# ---------------------------------------------------------------------------

def demonstrate_production_considerations() -> None:
    print_title("32. Production Considerations")

    print(
        """
A production SELECT should be evaluated on more than syntax.

Correctness:
    Does it return exactly the intended rows and values?

Security:
    Are user-supplied values parameterized?
    Are dynamic identifiers validated?

Performance:
    Does the query scale with realistic data volume?
    Are indexes appropriate?
    Is sorting or aggregation expensive?

Maintainability:
    Are aliases meaningful?
    Is the query understandable?
    Are business rules explicit?

Reliability:
    Is NULL behavior intentional?
    Are missing relationships handled correctly?
    Are empty results expected and handled by the application?

Portability:
    Is the SQL tied to a particular database dialect?

Observability:
    Can slow queries be identified and investigated?

Data correctness:
    Are duplicates, missing values, stale records, and inconsistent date
    representations handled according to the application's requirements?
"""
    )


# ---------------------------------------------------------------------------
# 35. Comprehensive final example
# ---------------------------------------------------------------------------

def demonstrate_comprehensive_example(connection: sqlite3.Connection) -> None:
    print_title("33. Comprehensive SELECT Example")

    sql = """
        WITH active_employees AS (
            SELECT
                e.employee_id,
                e.first_name || ' ' || e.last_name AS employee_name,
                e.department_id,
                e.salary,
                COALESCE(e.commission, 0) AS commission
            FROM employees AS e
            WHERE e.active = 1
        ),
        enriched_employees AS (
            SELECT
                ae.employee_id,
                ae.employee_name,
                d.department_name,
                d.location,
                ae.salary,
                ae.commission,
                ae.salary + ae.commission AS total_compensation,
                AVG(ae.salary) OVER () AS average_active_salary,
                RANK() OVER (
                    PARTITION BY ae.department_id
                    ORDER BY ae.salary DESC
                ) AS department_salary_rank
            FROM active_employees AS ae
            LEFT JOIN departments AS d
                ON ae.department_id = d.department_id
        )
        SELECT
            employee_id,
            employee_name,
            COALESCE(department_name, 'Unassigned') AS department,
            COALESCE(location, 'Unknown') AS office_location,
            salary,
            commission,
            total_compensation,
            ROUND(average_active_salary, 2) AS average_active_salary,
            ROUND(total_compensation - average_active_salary, 2)
                AS difference_from_average,
            department_salary_rank,
            CASE
                WHEN total_compensation >= 140000 THEN 'Premium'
                WHEN total_compensation >= 100000 THEN 'Standard'
                ELSE 'Base'
            END AS compensation_category
        FROM enriched_employees
        WHERE total_compensation >= 70000
        ORDER BY
            total_compensation DESC,
            employee_name ASC;
    """

    print_query(
        connection,
        sql,
        description=(
            "Multi-stage query combining CTEs, aliases, joins, expressions, "
            "NULL handling, window functions, CASE, filtering, and ordering."
        ),
    )


# ---------------------------------------------------------------------------
# 36. Main execution
# ---------------------------------------------------------------------------

def main() -> None:
    connection = create_database()

    try:
        demonstrate_database_fundamentals(connection)
        demonstrate_select_and_from(connection)
        demonstrate_column_aliases(connection)
        demonstrate_table_aliases(connection)
        demonstrate_expressions(connection)
        demonstrate_where(connection)
        demonstrate_logical_precedence(connection)
        demonstrate_null(connection)
        demonstrate_case(connection)
        demonstrate_distinct(connection)
        demonstrate_order_and_limit(connection)
        demonstrate_aggregates(connection)
        demonstrate_query_processing(connection)
        demonstrate_joins(connection)
        demonstrate_scalar_subqueries(connection)
        demonstrate_exists(connection)
        demonstrate_ctes(connection)
        demonstrate_window_functions(connection)
        demonstrate_text_and_dates(connection)
        demonstrate_boolean_expressions(connection)
        demonstrate_parameterized_queries(connection)
        demonstrate_safe_dynamic_sort(connection)
        demonstrate_query_plans(connection)
        demonstrate_edge_cases(connection)
        demonstrate_common_mistakes(connection)
        demonstrate_practical_report(connection)
        demonstrate_advanced_report(connection)
        demonstrate_expression_boundaries(connection)
        demonstrate_query_testing(connection)
        demonstrate_dialect_considerations()
        demonstrate_sql_style()
        demonstrate_production_considerations()
        demonstrate_comprehensive_example(connection)

        print_title("34. End of SELECT Fundamentals Tutorial")
        print(
            """
The executable examples have covered the SELECT statement from basic
projection and filtering through expressions, NULL handling, joins,
subqueries, CTEs, aggregation, window functions, security, testing,
performance, and production-oriented design.
"""
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
