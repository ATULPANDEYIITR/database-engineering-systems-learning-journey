"""
Sorting and Limiting in SQL
===========================

Topic:
    ORDER BY, ASC, DESC, LIMIT, OFFSET

This standalone Python program teaches SQL sorting and limiting from
absolute beginner level through advanced practical usage.

SQLite is used because it is included with Python's standard library.
No external package is required.

The examples cover:
    - ORDER BY
    - ASC and DESC
    - Sorting numbers, text, and dates
    - Multiple-column sorting
    - NULL ordering
    - LIMIT
    - OFFSET
    - Pagination
    - Top-N and bottom-N queries
    - LIMIT/OFFSET with WHERE
    - LIMIT/OFFSET with aggregation
    - Deterministic ordering
    - Tie-breaking
    - Performance considerations
    - Indexes
    - Keyset pagination
    - Common mistakes
    - Edge cases
    - Practical real-world examples
    - Validation and testing

The program creates its own in-memory database, so it can be run directly.
"""

import sqlite3
from datetime import datetime
from typing import Iterable, Sequence


# ---------------------------------------------------------------------------
# 1. DATABASE SETUP
# ---------------------------------------------------------------------------

def create_connection() -> sqlite3.Connection:
    """Create an in-memory SQLite database connection."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def create_tables(connection: sqlite3.Connection) -> None:
    """Create tables used throughout the tutorial."""
    connection.executescript(
        """
        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            job_title TEXT NOT NULL,
            salary REAL NOT NULL,
            hire_date TEXT NOT NULL,
            city TEXT,
            performance_score REAL,
            bonus REAL,
            email TEXT
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            rating REAL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE sales (
            sale_id INTEGER PRIMARY KEY,
            employee_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            sale_amount REAL NOT NULL,
            sale_date TEXT NOT NULL,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
        """
    )


def insert_sample_data(connection: sqlite3.Connection) -> None:
    """Insert realistic sample records."""
    employees = [
        (1, "Aarav Sharma", "Engineering", "Software Engineer", 85000, "2021-03-15", "Delhi", 8.7, 5000, "aarav@example.com"),
        (2, "Priya Singh", "Finance", "Financial Analyst", 72000, "2022-07-10", "Mumbai", 9.1, 6500, "priya@example.com"),
        (3, "Rohan Verma", "Engineering", "Senior Software Engineer", 105000, "2019-01-22", "Bengaluru", 9.4, 9000, "rohan@example.com"),
        (4, "Ananya Gupta", "Marketing", "Marketing Manager", 78000, "2020-11-05", "Pune", 8.9, 7000, "ananya@example.com"),
        (5, "Vikram Rao", "Engineering", "DevOps Engineer", 95000, "2020-05-18", "Hyderabad", 8.5, 6000, "vikram@example.com"),
        (6, "Meera Iyer", "Finance", "Senior Financial Analyst", 91000, "2018-09-12", "Chennai", 9.6, 10000, "meera@example.com"),
        (7, "Kabir Khan", "Sales", "Sales Executive", 58000, "2023-02-14", "Delhi", 7.8, 4500, "kabir@example.com"),
        (8, "Ishita Das", "Marketing", "Content Specialist", 62000, "2022-04-25", "Kolkata", 8.2, 3500, "ishita@example.com"),
        (9, "Aditya Nair", "Sales", "Sales Manager", 88000, "2017-06-30", "Kochi", 9.0, 8500, "aditya@example.com"),
        (10, "Sneha Patel", "Engineering", "Software Engineer", 85000, "2023-08-21", "Ahmedabad", 8.7, 5000, "sneha@example.com"),
        (11, "Neha Joshi", "Finance", "Accountant", 65000, "2021-12-01", "Jaipur", 8.0, 3000, "neha@example.com"),
        (12, "Arjun Mehta", "Sales", "Sales Executive", 58000, "2023-09-17", "Mumbai", 7.8, 4500, "arjun@example.com"),
        (13, "Diya Kapoor", "Engineering", "Data Engineer", 98000, "2020-02-11", "Bengaluru", 9.2, 8000, "diya@example.com"),
        (14, "Rahul Bansal", "Marketing", "Marketing Analyst", 68000, "2021-10-19", "Noida", 8.4, 4000, "rahul@example.com"),
        (15, "Tanya Roy", "Finance", "Finance Manager", 110000, "2016-04-08", "Kolkata", 9.7, 12000, "tanya@example.com"),
        (16, "Sahil Kapoor", "Engineering", "QA Engineer", 76000, "2022-01-29", "Chandigarh", 8.6, 4500, "sahil@example.com"),
        (17, "Pooja Menon", "Sales", "Sales Executive", 60000, "2024-01-08", "Kochi", None, 3000, "pooja@example.com"),
        (18, "Karan Malhotra", "Engineering", "Software Engineer", 85000, "2024-03-16", "Delhi", 8.7, 5000, "karan@example.com"),
    ]

    products = [
        (1, "Laptop Pro", "Electronics", 1200, 15, 4.8, "2024-01-10"),
        (2, "Wireless Mouse", "Electronics", 35, 120, 4.4, "2024-02-15"),
        (3, "Mechanical Keyboard", "Electronics", 95, 60, 4.7, "2024-03-20"),
        (4, "Office Chair", "Furniture", 280, 25, 4.5, "2024-01-25"),
        (5, "Standing Desk", "Furniture", 450, 10, 4.9, "2024-04-05"),
        (6, "Notebook", "Stationery", 8, 500, 4.2, "2024-02-01"),
        (7, "Pen Set", "Stationery", 12, 300, 4.1, "2024-03-01"),
        (8, "Monitor", "Electronics", 350, 35, 4.6, "2024-05-12"),
        (9, "Headphones", "Electronics", 150, 80, 4.3, "2024-04-22"),
        (10, "Desk Lamp", "Furniture", 55, 90, 4.5, "2024-05-30"),
    ]

    sales = [
        (1, 1, 1, 2, 2400, "2024-06-01"),
        (2, 3, 8, 4, 1400, "2024-06-02"),
        (3, 4, 4, 3, 840, "2024-06-03"),
        (4, 7, 2, 10, 350, "2024-06-04"),
        (5, 9, 5, 2, 900, "2024-06-05"),
        (6, 13, 3, 5, 475, "2024-06-06"),
        (7, 2, 9, 6, 900, "2024-06-07"),
        (8, 5, 1, 1, 1200, "2024-06-08"),
        (9, 6, 5, 3, 1350, "2024-06-09"),
        (10, 12, 7, 20, 240, "2024-06-10"),
        (11, 10, 8, 2, 700, "2024-06-11"),
        (12, 14, 10, 8, 440, "2024-06-12"),
        (13, 15, 1, 3, 3600, "2024-06-13"),
        (14, 8, 6, 30, 240, "2024-06-14"),
        (15, 16, 3, 7, 665, "2024-06-15"),
        (16, 18, 9, 5, 750, "2024-06-16"),
    ]

    connection.executemany(
        """
        INSERT INTO employees
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        employees,
    )

    connection.executemany(
        """
        INSERT INTO products
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        products,
    )

    connection.executemany(
        """
        INSERT INTO sales
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        sales,
    )

    connection.commit()


# ---------------------------------------------------------------------------
# 2. GENERAL QUERY HELPERS
# ---------------------------------------------------------------------------

def print_title(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def print_rows(
    rows: Iterable[sqlite3.Row],
    columns: Sequence[str] | None = None,
) -> None:
    """Print SQLite rows in a simple table-like format."""
    rows = list(rows)

    if not rows:
        print("(no rows)")
        return

    if columns is None:
        columns = rows[0].keys()

    column_names = list(columns)

    widths = {}
    for column in column_names:
        values = [str(row[column]) if row[column] is not None else "NULL" for row in rows]
        widths[column] = max(
            len(column),
            *(len(value) for value in values),
        )

    header = " | ".join(column.ljust(widths[column]) for column in column_names)
    separator = "-+-".join("-" * widths[column] for column in column_names)

    print(header)
    print(separator)

    for row in rows:
        formatted_values = []
        for column in column_names:
            value = row[column]
            text = "NULL" if value is None else str(value)
            formatted_values.append(text.ljust(widths[column]))

        print(" | ".join(formatted_values))


def run_query(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple = (),
    columns: Sequence[str] | None = None,
) -> list[sqlite3.Row]:
    """Execute a SELECT query and display its results."""
    rows = connection.execute(sql, parameters).fetchall()
    print_rows(rows, columns)
    return rows


# ---------------------------------------------------------------------------
# 3. SQL FUNDAMENTALS
# ---------------------------------------------------------------------------

def demonstrate_basic_select(connection: sqlite3.Connection) -> None:
    print_title("1. Basic SELECT: The Starting Point")

    print(
        """
SELECT retrieves rows from a table.

Without ORDER BY, SQL does not promise a particular presentation order.
A database may appear to return rows in insertion order during simple tests,
but production code must not depend on that behavior.
"""
    )

    sql = """
        SELECT employee_id, name, department, salary
        FROM employees
        LIMIT 5
    """

    run_query(connection, sql)


# ---------------------------------------------------------------------------
# 4. ORDER BY
# ---------------------------------------------------------------------------

def demonstrate_order_by(connection: sqlite3.Connection) -> None:
    print_title("2. ORDER BY: Sorting Query Results")

    print(
        """
ORDER BY tells SQL how the result set should be sorted.

General structure:

SELECT columns
FROM table
ORDER BY column;

The default direction is ascending.
"""
    )

    print("\nEmployees sorted by salary:")
    run_query(
        connection,
        """
        SELECT employee_id, name, salary
        FROM employees
        ORDER BY salary
        """,
    )

    print("\nEmployees explicitly sorted in ascending salary order:")
    run_query(
        connection,
        """
        SELECT employee_id, name, salary
        FROM employees
        ORDER BY salary ASC
        """,
    )


# ---------------------------------------------------------------------------
# 5. ASC AND DESC
# ---------------------------------------------------------------------------

def demonstrate_asc_desc(connection: sqlite3.Connection) -> None:
    print_title("3. ASC and DESC")

    print(
        """
ASC means ascending.

For numbers:
    small -> large

For text:
    alphabetically earlier -> later

For dates:
    older -> newer

DESC means descending and reverses the ordering.
"""
    )

    print("\nHighest-paid employees first:")
    run_query(
        connection,
        """
        SELECT name, salary
        FROM employees
        ORDER BY salary DESC
        """,
    )

    print("\nLowest-paid employees first:")
    run_query(
        connection,
        """
        SELECT name, salary
        FROM employees
        ORDER BY salary ASC
        """,
    )

    print("\nNames in ascending alphabetical order:")
    run_query(
        connection,
        """
        SELECT name
        FROM employees
        ORDER BY name ASC
        """,
    )

    print("\nMost recently hired employees first:")
    run_query(
        connection,
        """
        SELECT name, hire_date
        FROM employees
        ORDER BY hire_date DESC
        """,
    )


# ---------------------------------------------------------------------------
# 6. MULTIPLE-COLUMN SORTING
# ---------------------------------------------------------------------------

def demonstrate_multiple_column_sorting(connection: sqlite3.Connection) -> None:
    print_title("4. Multiple-Column ORDER BY")

    print(
        """
ORDER BY can contain multiple columns.

Example:

ORDER BY department ASC, salary DESC

The database first sorts by department.
For employees within the same department, it sorts by salary descending.

This is called hierarchical or lexicographic sorting.
"""
    )

    run_query(
        connection,
        """
        SELECT name, department, salary
        FROM employees
        ORDER BY department ASC, salary DESC
        """,
    )

    print(
        """
Each ORDER BY expression can have its own direction.
For example:

ORDER BY department ASC, salary DESC, name ASC
"""
    )

    run_query(
        connection,
        """
        SELECT name, department, salary
        FROM employees
        ORDER BY department ASC, salary DESC, name ASC
        """,
    )


# ---------------------------------------------------------------------------
# 7. SORTING BY EXPRESSIONS
# ---------------------------------------------------------------------------

def demonstrate_sorting_expressions(connection: sqlite3.Connection) -> None:
    print_title("5. Sorting by Calculated Expressions")

    print(
        """
ORDER BY does not have to use only a stored column.
It can sort using an expression.

For example, total compensation can be approximated as:

salary + bonus
"""
    )

    run_query(
        connection,
        """
        SELECT
            name,
            salary,
            bonus,
            salary + bonus AS total_compensation
        FROM employees
        ORDER BY total_compensation DESC
        """,
    )

    print("\nSorting by an expression without selecting the expression:")
    run_query(
        connection,
        """
        SELECT name, salary, bonus
        FROM employees
        ORDER BY salary + bonus DESC
        """,
    )


# ---------------------------------------------------------------------------
# 8. LIMIT
# ---------------------------------------------------------------------------

def demonstrate_limit(connection: sqlite3.Connection) -> None:
    print_title("6. LIMIT: Restricting the Number of Rows")

    print(
        """
LIMIT restricts how many rows are returned.

Example:

SELECT ...
FROM employees
ORDER BY salary DESC
LIMIT 5;

The ORDER BY is important. LIMIT by itself does not mean "top 5".
It means "return some 5 rows" unless an ordering requirement is established.
"""
    )

    print("\nTop 5 salaries:")
    run_query(
        connection,
        """
        SELECT name, salary
        FROM employees
        ORDER BY salary DESC
        LIMIT 5
        """,
    )

    print("\nBottom 3 salaries:")
    run_query(
        connection,
        """
        SELECT name, salary
        FROM employees
        ORDER BY salary ASC
        LIMIT 3
        """,
    )


# ---------------------------------------------------------------------------
# 9. OFFSET
# ---------------------------------------------------------------------------

def demonstrate_offset(connection: sqlite3.Connection) -> None:
    print_title("7. OFFSET: Skipping Rows")

    print(
        """
OFFSET tells the database to skip a specified number of rows before
returning results.

Example:

ORDER BY salary DESC
LIMIT 5 OFFSET 5

This skips the first five rows in the sorted result and returns the next five.

OFFSET is usually meaningful together with ORDER BY and LIMIT.
"""
    )

    print("\nRows 6 through 10 by salary:")
    run_query(
        connection,
        """
        SELECT name, salary
        FROM employees
        ORDER BY salary DESC
        LIMIT 5 OFFSET 5
        """,
    )


# ---------------------------------------------------------------------------
# 10. PAGINATION
# ---------------------------------------------------------------------------

def demonstrate_pagination(connection: sqlite3.Connection) -> None:
    print_title("8. Pagination with LIMIT and OFFSET")

    print(
        """
A common pagination formula is:

OFFSET = (page_number - 1) * page_size

For page 1 with 5 rows:
    OFFSET = (1 - 1) * 5 = 0

For page 2:
    OFFSET = (2 - 1) * 5 = 5

For page 3:
    OFFSET = (3 - 1) * 5 = 10
"""
    )

    page_size = 5

    for page_number in range(1, 5):
        offset = (page_number - 1) * page_size

        print(f"\nPage {page_number}:")
        run_query(
            connection,
            """
            SELECT employee_id, name, salary
            FROM employees
            ORDER BY employee_id ASC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        )


# ---------------------------------------------------------------------------
# 11. LIMIT WITH WHERE
# ---------------------------------------------------------------------------

def demonstrate_where_order_limit(connection: sqlite3.Connection) -> None:
    print_title("9. WHERE + ORDER BY + LIMIT")

    print(
        """
A common query pattern is:

SELECT ...
FROM ...
WHERE condition
ORDER BY ...
LIMIT ...;

Conceptually:
    1. Identify rows matching WHERE.
    2. Sort the matching rows.
    3. Restrict the sorted result using LIMIT.

Example: highest-paid Engineering employees.
"""
    )

    run_query(
        connection,
        """
        SELECT name, department, salary
        FROM employees
        WHERE department = 'Engineering'
        ORDER BY salary DESC
        LIMIT 5
        """,
    )

    print("\nThree most recent Finance hires:")
    run_query(
        connection,
        """
        SELECT name, hire_date
        FROM employees
        WHERE department = 'Finance'
        ORDER BY hire_date DESC
        LIMIT 3
        """,
    )


# ---------------------------------------------------------------------------
# 12. TOP-N PROBLEMS
# ---------------------------------------------------------------------------

def demonstrate_top_n_patterns(connection: sqlite3.Connection) -> None:
    print_title("10. Top-N and Bottom-N Query Patterns")

    examples = [
        (
            "Top 3 highest-paid employees",
            """
            SELECT name, salary
            FROM employees
            ORDER BY salary DESC, employee_id ASC
            LIMIT 3
            """,
        ),
        (
            "Bottom 3 salaries",
            """
            SELECT name, salary
            FROM employees
            ORDER BY salary ASC, employee_id ASC
            LIMIT 3
            """,
        ),
        (
            "Three highest performance scores",
            """
            SELECT name, performance_score
            FROM employees
            WHERE performance_score IS NOT NULL
            ORDER BY performance_score DESC, employee_id ASC
            LIMIT 3
            """,
        ),
        (
            "Most expensive products",
            """
            SELECT product_name, price
            FROM products
            ORDER BY price DESC, product_id ASC
            LIMIT 5
            """,
        ),
        (
            "Products with the lowest stock",
            """
            SELECT product_name, stock
            FROM products
            ORDER BY stock ASC, product_id ASC
            LIMIT 5
            """,
        ),
    ]

    for title, sql in examples:
        print(f"\n{title}:")
        run_query(connection, sql)


# ---------------------------------------------------------------------------
# 13. TIES AND DETERMINISTIC ORDERING
# ---------------------------------------------------------------------------

def demonstrate_ties(connection: sqlite3.Connection) -> None:
    print_title("11. Ties and Deterministic Ordering")

    print(
        """
Several employees have the same salary.

If a query uses only:

ORDER BY salary DESC
LIMIT 5

then employees tied around the fifth position may not have a guaranteed
relative order.

A stable business query should provide a tie-breaker.

Example:

ORDER BY salary DESC, employee_id ASC

Salary is the primary sort key.
employee_id becomes the secondary sort key.
"""
    )

    print("\nDeterministic top 8 salaries:")
    run_query(
        connection,
        """
        SELECT employee_id, name, salary
        FROM employees
        ORDER BY salary DESC, employee_id ASC
        LIMIT 8
        """,
    )

    print(
        """
The same principle is important for pagination. If the ordering is not
deterministic, records can appear on different pages between executions,
especially when the underlying data changes.
"""
    )


# ---------------------------------------------------------------------------
# 14. NULL ORDERING
# ---------------------------------------------------------------------------

def demonstrate_null_ordering(connection: sqlite3.Connection) -> None:
    print_title("12. NULL Values and Sorting")

    print(
        """
NULL means "missing/unknown value", not zero and not an empty string.

NULL ordering is database-specific in some respects, so production SQL
should explicitly control NULL placement when the requirement matters.

SQLite normally places NULL before non-NULL values for ASC and after them
for DESC.

SQLite also supports:

ORDER BY performance_score IS NULL, performance_score DESC

The boolean expression moves non-NULL values first.
"""
    )

    print("\nSQLite's natural ASC ordering of performance_score:")
    run_query(
        connection,
        """
        SELECT name, performance_score
        FROM employees
        ORDER BY performance_score ASC
        """,
    )

    print("\nExplicitly put NULL values last:")
    run_query(
        connection,
        """
        SELECT name, performance_score
        FROM employees
        ORDER BY performance_score IS NULL ASC,
                 performance_score DESC
        """,
    )


# ---------------------------------------------------------------------------
# 15. ALIASES IN ORDER BY
# ---------------------------------------------------------------------------

def demonstrate_alias_sorting(connection: sqlite3.Connection) -> None:
    print_title("13. Sorting by a SELECT Alias")

    print(
        """
A calculated expression can receive an alias and the alias can commonly
be referenced by ORDER BY.

Example:

salary + bonus AS total_compensation

ORDER BY total_compensation DESC
"""
    )

    run_query(
        connection,
        """
        SELECT
            name,
            salary,
            bonus,
            salary + bonus AS total_compensation
        FROM employees
        ORDER BY total_compensation DESC
        LIMIT 7
        """,
    )


# ---------------------------------------------------------------------------
# 16. ORDER OF SQL CLAUSES
# ---------------------------------------------------------------------------

def demonstrate_clause_order(connection: sqlite3.Connection) -> None:
    print_title("14. SQL Query Clause Structure")

    print(
        """
A useful written form is:

SELECT columns
FROM table
WHERE conditions
GROUP BY grouping_columns
HAVING group_conditions
ORDER BY sorting_expression
LIMIT row_count
OFFSET rows_to_skip;

ORDER BY belongs after WHERE, GROUP BY, and HAVING.
LIMIT and OFFSET appear after ORDER BY.

This is the practical syntax order you write in a query.
"""
    )

    run_query(
        connection,
        """
        SELECT department, AVG(salary) AS average_salary
        FROM employees
        WHERE salary >= 60000
        GROUP BY department
        HAVING AVG(salary) >= 70000
        ORDER BY average_salary DESC
        LIMIT 3
        """,
    )


# ---------------------------------------------------------------------------
# 17. LIMIT WITH AGGREGATION
# ---------------------------------------------------------------------------

def demonstrate_aggregation_and_limit(connection: sqlite3.Connection) -> None:
    print_title("15. GROUP BY + ORDER BY + LIMIT")

    print(
        """
LIMIT can be applied after aggregation.

Example:
    Find departments with the highest average salary.

GROUP BY creates one result row per department.
AVG calculates each department's average.
ORDER BY ranks those department rows.
LIMIT selects the highest-ranked departments.
"""
    )

    run_query(
        connection,
        """
        SELECT
            department,
            COUNT(*) AS employee_count,
            ROUND(AVG(salary), 2) AS average_salary
        FROM employees
        GROUP BY department
        ORDER BY average_salary DESC
        LIMIT 3
        """,
    )


# ---------------------------------------------------------------------------
# 18. DISTINCT + ORDER BY + LIMIT
# ---------------------------------------------------------------------------

def demonstrate_distinct_order_limit(connection: sqlite3.Connection) -> None:
    print_title("16. DISTINCT + ORDER BY + LIMIT")

    print(
        """
DISTINCT removes duplicate result values.

Example:
    Find three highest unique salary levels.
"""
    )

    run_query(
        connection,
        """
        SELECT DISTINCT salary
        FROM employees
        ORDER BY salary DESC
        LIMIT 3
        """,
    )

    print("\nThree cities represented by the employee data:")
    run_query(
        connection,
        """
        SELECT DISTINCT city
        FROM employees
        WHERE city IS NOT NULL
        ORDER BY city ASC
        LIMIT 3
        """,
    )


# ---------------------------------------------------------------------------
# 19. STRING SORTING
# ---------------------------------------------------------------------------

def demonstrate_text_sorting(connection: sqlite3.Connection) -> None:
    print_title("17. Sorting Text")

    print(
        """
Text ordering follows the database's collation rules.

Simple alphabetical sorting is often enough, but real systems may need
case-insensitive or locale-aware ordering.

SQLite's NOCASE collation provides a basic case-insensitive comparison.
"""
    )

    run_query(
        connection,
        """
        SELECT name, city
        FROM employees
        ORDER BY city ASC, name ASC
        """,
    )

    print("\nCase-insensitive ordering example:")
    run_query(
        connection,
        """
        SELECT name
        FROM employees
        ORDER BY name COLLATE NOCASE ASC
        """,
    )


# ---------------------------------------------------------------------------
# 20. DATE SORTING
# ---------------------------------------------------------------------------

def demonstrate_date_sorting(connection: sqlite3.Connection) -> None:
    print_title("18. Date Sorting")

    print(
        """
The sample dates use ISO format:

YYYY-MM-DD

Lexicographic ordering of this format matches chronological ordering.

For example:
    2024-01-01
    2024-06-01
    2025-01-01

For production systems, use an appropriate database date/time type or a
well-defined canonical representation.
"""
    )

    print("\nOldest hires:")
    run_query(
        connection,
        """
        SELECT name, hire_date
        FROM employees
        ORDER BY hire_date ASC
        LIMIT 5
        """,
    )

    print("\nNewest hires:")
    run_query(
        connection,
        """
        SELECT name, hire_date
        FROM employees
        ORDER BY hire_date DESC
        LIMIT 5
        """,
    )


# ---------------------------------------------------------------------------
# 21. JOIN + ORDER BY + LIMIT
# ---------------------------------------------------------------------------

def demonstrate_join_sort_limit(connection: sqlite3.Connection) -> None:
    print_title("19. JOIN + ORDER BY + LIMIT")

    print(
        """
ORDER BY can sort a result assembled from multiple tables.

Example:
    Which products generated the largest individual sales transactions?
"""
    )

    run_query(
        connection,
        """
        SELECT
            s.sale_id,
            p.product_name,
            e.name AS salesperson,
            s.sale_amount,
            s.sale_date
        FROM sales AS s
        JOIN products AS p
            ON p.product_id = s.product_id
        JOIN employees AS e
            ON e.employee_id = s.employee_id
        ORDER BY s.sale_amount DESC, s.sale_id ASC
        LIMIT 5
        """,
    )


# ---------------------------------------------------------------------------
# 22. TOP SALES BY EMPLOYEE
# ---------------------------------------------------------------------------

def demonstrate_grouped_sales(connection: sqlite3.Connection) -> None:
    print_title("20. Aggregation + JOIN + ORDER BY + LIMIT")

    print(
        """
This is a realistic analytics pattern.

The query:
    - joins employees to sales
    - groups sales by employee
    - calculates total revenue
    - counts transactions
    - ranks employees by revenue
    - returns the top performers
"""
    )

    run_query(
        connection,
        """
        SELECT
            e.name,
            COUNT(s.sale_id) AS transactions,
            ROUND(SUM(s.sale_amount), 2) AS total_revenue
        FROM employees AS e
        JOIN sales AS s
            ON s.employee_id = e.employee_id
        GROUP BY e.employee_id, e.name
        ORDER BY total_revenue DESC, e.employee_id ASC
        LIMIT 5
        """,
    )


# ---------------------------------------------------------------------------
# 23. OFFSET PAGINATION WITH A FILTER
# ---------------------------------------------------------------------------

def demonstrate_filtered_pagination(connection: sqlite3.Connection) -> None:
    print_title("21. Filtered Pagination")

    print(
        """
Pagination can be combined with filtering.

For example:
    Display Engineering employees five at a time, ordered by salary.
"""
    )

    page_size = 3

    for page_number in (1, 2):
        offset = (page_number - 1) * page_size

        print(f"\nEngineering page {page_number}:")
        run_query(
            connection,
            """
            SELECT employee_id, name, salary
            FROM employees
            WHERE department = 'Engineering'
            ORDER BY salary DESC, employee_id ASC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        )


# ---------------------------------------------------------------------------
# 24. OFFSET EDGE CASES
# ---------------------------------------------------------------------------

def demonstrate_offset_edge_cases(connection: sqlite3.Connection) -> None:
    print_title("22. LIMIT and OFFSET Edge Cases")

    print(
        """
Important edge cases:

1. LIMIT 0
   Returns zero rows.

2. OFFSET larger than the result size
   Returns zero rows.

3. LIMIT larger than the available rows
   Returns all remaining rows.

4. OFFSET 0
   Means do not skip anything.

5. Negative values
   Behavior can be database-specific. Do not rely on accidental behavior.
   Validate application inputs before constructing pagination requests.
"""
    )

    print("\nLIMIT 0:")
    run_query(
        connection,
        """
        SELECT name
        FROM employees
        ORDER BY employee_id
        LIMIT 0
        """,
    )

    print("\nOFFSET larger than the dataset:")
    run_query(
        connection,
        """
        SELECT name
        FROM employees
        ORDER BY employee_id
        LIMIT 5 OFFSET 1000
        """,
    )

    print("\nLIMIT larger than available rows:")
    run_query(
        connection,
        """
        SELECT name
        FROM employees
        ORDER BY employee_id
        LIMIT 1000
        """,
    )


# ---------------------------------------------------------------------------
# 25. VALIDATING PAGINATION INPUT
# ---------------------------------------------------------------------------

def validate_pagination(page: int, page_size: int) -> tuple[int, int]:
    """
    Validate pagination parameters.

    Applications should not blindly trust user-provided page numbers or
    page sizes. Limits protect both correctness and database workload.
    """
    if not isinstance(page, int) or isinstance(page, bool):
        raise TypeError("page must be an integer")

    if not isinstance(page_size, int) or isinstance(page_size, bool):
        raise TypeError("page_size must be an integer")

    if page < 1:
        raise ValueError("page must be at least 1")

    if page_size < 1:
        raise ValueError("page_size must be at least 1")

    # Application-specific maximum to prevent excessive result sizes.
    maximum_page_size = 100

    if page_size > maximum_page_size:
        raise ValueError(
            f"page_size cannot exceed {maximum_page_size}"
        )

    offset = (page - 1) * page_size

    return page_size, offset


def demonstrate_pagination_validation(
    connection: sqlite3.Connection,
) -> None:
    print_title("23. Safe Pagination Input Validation")

    valid_requests = [
        (1, 5),
        (2, 5),
        (3, 10),
    ]

    for page, page_size in valid_requests:
        validated_size, offset = validate_pagination(page, page_size)

        print(f"\nPage={page}, size={validated_size}, offset={offset}")
        run_query(
            connection,
            """
            SELECT employee_id, name
            FROM employees
            ORDER BY employee_id ASC
            LIMIT ? OFFSET ?
            """,
            (validated_size, offset),
        )

    invalid_requests = [
        (0, 5),
        (-1, 5),
        (1, 0),
        (1, -5),
        (1, 1000),
    ]

    print("\nInvalid requests:")
    for page, page_size in invalid_requests:
        try:
            validate_pagination(page, page_size)
        except (TypeError, ValueError) as error:
            print(f"page={page}, page_size={page_size} -> {error}")


# ---------------------------------------------------------------------------
# 26. PARAMETERIZED LIMIT AND OFFSET
# ---------------------------------------------------------------------------

def demonstrate_parameterized_pagination(
    connection: sqlite3.Connection,
) -> None:
    print_title("24. Parameterized LIMIT and OFFSET")

    print(
        """
Pagination values can be passed as SQL parameters.

This is preferable to concatenating user input into SQL text.

For values, use parameter binding:

LIMIT ?
OFFSET ?

Parameterization helps prevent SQL injection and avoids quoting mistakes.
"""
    )

    page_size = 4
    page = 2
    offset = (page - 1) * page_size

    run_query(
        connection,
        """
        SELECT employee_id, name, salary
        FROM employees
        ORDER BY employee_id ASC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )


# ---------------------------------------------------------------------------
# 27. SQL INJECTION AND DYNAMIC ORDER BY
# ---------------------------------------------------------------------------

def demonstrate_safe_dynamic_sorting(
    connection: sqlite3.Connection,
) -> None:
    print_title("25. Safe Dynamic ORDER BY Design")

    print(
        """
A subtle security issue occurs when applications allow users to choose
a sorting column.

Values can normally be parameterized:

WHERE department = ?

Identifiers such as column names cannot be safely supplied using the same
value placeholder syntax.

Do NOT build SQL like:

ORDER BY {user_input}

unless the input is strictly controlled.

Use an allowlist that maps accepted application choices to trusted SQL
identifiers.
"""
    )

    allowed_sort_columns = {
        "name": "name",
        "salary": "salary",
        "hire_date": "hire_date",
        "performance": "performance_score",
    }

    requested_sort = "salary"

    if requested_sort not in allowed_sort_columns:
        raise ValueError("Unsupported sort field")

    trusted_column = allowed_sort_columns[requested_sort]

    sql = f"""
        SELECT name, salary, hire_date, performance_score
        FROM employees
        ORDER BY {trusted_column} DESC, employee_id ASC
        LIMIT ?
    """

    run_query(connection, sql, (5,))

    print(
        """
The f-string above is safe only because trusted_column comes exclusively
from a fixed allowlist. Never insert unrestricted user input into SQL.
"""
    )


# ---------------------------------------------------------------------------
# 28. SORT DIRECTION ALLOWLIST
# ---------------------------------------------------------------------------

def demonstrate_safe_dynamic_direction(
    connection: sqlite3.Connection,
) -> None:
    print_title("26. Safely Handling ASC and DESC Selection")

    allowed_directions = {
        "ascending": "ASC",
        "descending": "DESC",
    }

    requested_direction = "descending"

    if requested_direction not in allowed_directions:
        raise ValueError("Unsupported sort direction")

    direction = allowed_directions[requested_direction]

    sql = f"""
        SELECT name, salary
        FROM employees
        ORDER BY salary {direction}, employee_id ASC
        LIMIT ?
    """

    run_query(connection, sql, (5,))


# ---------------------------------------------------------------------------
# 29. KEYSET PAGINATION
# ---------------------------------------------------------------------------

def demonstrate_keyset_pagination(connection: sqlite3.Connection) -> None:
    print_title("27. Keyset Pagination")

    print(
        """
OFFSET pagination is simple:

ORDER BY employee_id
LIMIT 5 OFFSET 100000

But a large OFFSET can become inefficient because the database may need
to walk past many earlier rows.

Keyset pagination, also called cursor pagination, uses the last value from
the previous page.

For a unique increasing employee_id:

WHERE employee_id > ?
ORDER BY employee_id ASC
LIMIT ?

This avoids asking the database to skip a large number of rows.
"""
    )

    page_size = 5
    last_seen_id = 0

    for page_number in range(1, 4):
        print(f"\nKeyset page {page_number} after employee_id={last_seen_id}:")

        rows = connection.execute(
            """
            SELECT employee_id, name, salary
            FROM employees
            WHERE employee_id > ?
            ORDER BY employee_id ASC
            LIMIT ?
            """,
            (last_seen_id, page_size),
        ).fetchall()

        print_rows(rows)

        if rows:
            last_seen_id = rows[-1]["employee_id"]


# ---------------------------------------------------------------------------
# 30. KEYSET PAGINATION WITH A COMPOSITE SORT
# ---------------------------------------------------------------------------

def demonstrate_composite_keyset_pagination(
    connection: sqlite3.Connection,
) -> None:
    print_title("28. Keyset Pagination with Multiple Sort Columns")

    print(
        """
When ordering by multiple columns, the cursor condition must represent
the same ordering.

Suppose the ordering is:

ORDER BY salary DESC, employee_id ASC

The next page condition is:

WHERE
    salary < ?
    OR (salary = ? AND employee_id > ?)

The first part moves to lower salaries.
The second part handles ties in salary.
"""
    )

    page_size = 5
    last_salary = float("inf")
    last_employee_id = -1

    for page_number in range(1, 4):
        print(
            f"\nComposite keyset page {page_number} "
            f"after salary={last_salary}, id={last_employee_id}:"
        )

        rows = connection.execute(
            """
            SELECT employee_id, name, salary
            FROM employees
            WHERE
                salary < ?
                OR (salary = ? AND employee_id > ?)
            ORDER BY salary DESC, employee_id ASC
            LIMIT ?
            """,
            (
                last_salary,
                last_salary,
                last_employee_id,
                page_size,
            ),
        ).fetchall()

        print_rows(rows)

        if rows:
            last_salary = rows[-1]["salary"]
            last_employee_id = rows[-1]["employee_id"]


# ---------------------------------------------------------------------------
# 31. EXPLAIN QUERY PLAN
# ---------------------------------------------------------------------------

def demonstrate_query_plan(connection: sqlite3.Connection) -> None:
    print_title("29. EXPLAIN QUERY PLAN")

    print(
        """
EXPLAIN QUERY PLAN helps inspect how SQLite intends to execute a query.

A query involving ORDER BY may require a temporary sorting structure if
the database cannot obtain the requested order efficiently from an index.
"""
    )

    print("\nQuery plan before an appropriate index:")
    run_query(
        connection,
        """
        EXPLAIN QUERY PLAN
        SELECT name, salary
        FROM employees
        ORDER BY salary DESC
        LIMIT 5
        """,
    )


# ---------------------------------------------------------------------------
# 32. INDEX FOR ORDER BY
# ---------------------------------------------------------------------------

def demonstrate_index_for_sorting(connection: sqlite3.Connection) -> None:
    print_title("30. Indexes and ORDER BY Performance")

    print(
        """
An index can sometimes allow the database to produce rows in the desired
order without sorting the entire result set.

Create an index on salary:

CREATE INDEX idx_employees_salary
ON employees(salary);

The optimizer can then consider the index when executing salary-based
ordering and filtering.

Indexes are not automatically beneficial for every query. They consume
storage and add write/update overhead.
"""
    )

    connection.execute(
        """
        CREATE INDEX idx_employees_salary
        ON employees(salary)
        """
    )

    print("\nQuery plan after creating a salary index:")
    run_query(
        connection,
        """
        EXPLAIN QUERY PLAN
        SELECT name, salary
        FROM employees
        ORDER BY salary DESC
        LIMIT 5
        """,
    )


# ---------------------------------------------------------------------------
# 33. COMPOSITE INDEX
# ---------------------------------------------------------------------------

def demonstrate_composite_index(connection: sqlite3.Connection) -> None:
    print_title("31. Composite Index for Filtering and Sorting")

    print(
        """
A composite index contains multiple columns.

For this query:

WHERE department = ?
ORDER BY salary DESC, employee_id ASC
LIMIT 5

an index beginning with department and continuing with the ordering keys
can be useful:

CREATE INDEX idx_department_salary_id
ON employees(department, salary DESC, employee_id ASC);

Whether the optimizer uses it depends on the database, data distribution,
statistics, and query shape.
"""
    )

    connection.execute(
        """
        CREATE INDEX idx_department_salary_id
        ON employees(department, salary DESC, employee_id ASC)
        """
    )

    run_query(
        connection,
        """
        EXPLAIN QUERY PLAN
        SELECT name, salary
        FROM employees
        WHERE department = 'Engineering'
        ORDER BY salary DESC, employee_id ASC
        LIMIT 5
        """,
    )


# ---------------------------------------------------------------------------
# 34. LIMIT WITH UPDATE/DELETE: CONCEPTUAL WARNING
# ---------------------------------------------------------------------------

def demonstrate_mutation_warning(connection: sqlite3.Connection) -> None:
    print_title("32. LIMIT and Data Modification")

    print(
        """
LIMIT is most commonly demonstrated with SELECT.

Database support for LIMIT with UPDATE or DELETE differs across SQL
implementations. Do not assume that syntax written for one database works
unchanged in another.

For destructive operations, a safer pattern is often:

1. Identify the exact target rows with a SELECT.
2. Verify the target set.
3. Perform the controlled modification inside a transaction.

Sorting is particularly important when the requirement says something like
"delete the oldest 10 records", because "10 arbitrary records" is a
different operation.
"""
    )

    print("\nIdentify the oldest three employees without modifying data:")
    run_query(
        connection,
        """
        SELECT employee_id, name, hire_date
        FROM employees
        ORDER BY hire_date ASC, employee_id ASC
        LIMIT 3
        """,
    )


# ---------------------------------------------------------------------------
# 35. REAL-WORLD PRODUCT CATALOG
# ---------------------------------------------------------------------------

def demonstrate_product_catalog(connection: sqlite3.Connection) -> None:
    print_title("33. Real-World Product Catalog Queries")

    queries = [
        (
            "Most expensive products",
            """
            SELECT product_name, category, price
            FROM products
            ORDER BY price DESC, product_id ASC
            LIMIT 5
            """,
        ),
        (
            "Highest-rated products",
            """
            SELECT product_name, rating
            FROM products
            WHERE rating IS NOT NULL
            ORDER BY rating DESC, product_id ASC
            LIMIT 5
            """,
        ),
        (
            "Products with lowest stock",
            """
            SELECT product_name, stock
            FROM products
            ORDER BY stock ASC, product_id ASC
            LIMIT 5
            """,
        ),
        (
            "Newest products",
            """
            SELECT product_name, created_at
            FROM products
            ORDER BY created_at DESC, product_id ASC
            LIMIT 5
            """,
        ),
        (
            "Electronics between pages",
            """
            SELECT product_name, price
            FROM products
            WHERE category = 'Electronics'
            ORDER BY price DESC, product_id ASC
            LIMIT 2 OFFSET 1
            """,
        ),
    ]

    for title, sql in queries:
        print(f"\n{title}:")
        run_query(connection, sql)


# ---------------------------------------------------------------------------
# 36. REAL-WORLD EMPLOYEE SEARCH
# ---------------------------------------------------------------------------

def demonstrate_employee_directory(connection: sqlite3.Connection) -> None:
    print_title("34. Real-World Employee Directory")

    print("\nSearch Engineering employees by salary:")
    run_query(
        connection,
        """
        SELECT
            name,
            job_title,
            salary
        FROM employees
        WHERE department = 'Engineering'
        ORDER BY salary DESC, name ASC
        LIMIT 10
        """,
    )

    print("\nRecently hired employees:")
    run_query(
        connection,
        """
        SELECT
            name,
            department,
            hire_date
        FROM employees
        ORDER BY hire_date DESC, employee_id ASC
        LIMIT 5
        """,
    )


# ---------------------------------------------------------------------------
# 37. BUSINESS ANALYTICS
# ---------------------------------------------------------------------------

def demonstrate_business_analytics(connection: sqlite3.Connection) -> None:
    print_title("35. Business Analytics Ranking")

    print("\nTop departments by total salary expenditure:")
    run_query(
        connection,
        """
        SELECT
            department,
            COUNT(*) AS employees,
            ROUND(SUM(salary), 2) AS total_salary
        FROM employees
        GROUP BY department
        ORDER BY total_salary DESC, department ASC
        LIMIT 5
        """,
    )

    print("\nTop sales products by revenue:")
    run_query(
        connection,
        """
        SELECT
            p.product_name,
            SUM(s.quantity) AS units_sold,
            ROUND(SUM(s.sale_amount), 2) AS revenue
        FROM sales AS s
        JOIN products AS p
            ON p.product_id = s.product_id
        GROUP BY p.product_id, p.product_name
        ORDER BY revenue DESC, p.product_id ASC
        LIMIT 5
        """,
    )


# ---------------------------------------------------------------------------
# 38. "LATEST RECORDS" PATTERN
# ---------------------------------------------------------------------------

def demonstrate_latest_records(connection: sqlite3.Connection) -> None:
    print_title("36. Finding the Latest Records")

    print(
        """
A common application requirement is:

"Give me the latest 5 transactions."

The query should have an explicit timestamp/date ordering.
"""
    )

    run_query(
        connection,
        """
        SELECT
            sale_id,
            sale_amount,
            sale_date
        FROM sales
        ORDER BY sale_date DESC, sale_id DESC
        LIMIT 5
        """,
    )


# ---------------------------------------------------------------------------
# 39. LIMIT 1 FOR EXTREME VALUES
# ---------------------------------------------------------------------------

def demonstrate_limit_one(connection: sqlite3.Connection) -> None:
    print_title("37. LIMIT 1 for Single Best Match")

    print(
        """
LIMIT 1 is useful when a sorted result needs only the first row.

Examples:
    - highest salary
    - newest transaction
    - cheapest product
    - latest employee

An aggregate such as MAX() can also find an extreme value, but ORDER BY
LIMIT 1 can return the complete row associated with that extreme value.
"""
    )

    print("\nHighest-paid employee:")
    run_query(
        connection,
        """
        SELECT employee_id, name, salary
        FROM employees
        ORDER BY salary DESC, employee_id ASC
        LIMIT 1
        """,
    )

    print("\nNewest employee:")
    run_query(
        connection,
        """
        SELECT employee_id, name, hire_date
        FROM employees
        ORDER BY hire_date DESC, employee_id DESC
        LIMIT 1
        """,
    )


# ---------------------------------------------------------------------------
# 40. SECOND-HIGHEST AND NTH-HIGHEST PATTERNS
# ---------------------------------------------------------------------------

def demonstrate_nth_highest(connection: sqlite3.Connection) -> None:
    print_title("38. Nth-Highest Values with LIMIT and OFFSET")

    print(
        """
A simple nth-position pattern is:

ORDER BY salary DESC
LIMIT 1 OFFSET n - 1

For the second row:
    LIMIT 1 OFFSET 1

For the third row:
    LIMIT 1 OFFSET 2

This finds the nth row in the sorted result, not necessarily the nth
distinct salary.

That distinction matters when duplicate values exist.
"""
    )

    print("\nSecond employee by salary:")
    run_query(
        connection,
        """
        SELECT name, salary
        FROM employees
        ORDER BY salary DESC, employee_id ASC
        LIMIT 1 OFFSET 1
        """,
    )

    print("\nThird distinct salary level:")
    run_query(
        connection,
        """
        SELECT DISTINCT salary
        FROM employees
        ORDER BY salary DESC
        LIMIT 1 OFFSET 2
        """,
    )


# ---------------------------------------------------------------------------
# 41. COMPARING LIMIT/OFFSET WITH KEYSET PAGINATION
# ---------------------------------------------------------------------------

def demonstrate_pagination_tradeoffs() -> None:
    print_title("39. Pagination Strategy Comparison")

    print(
        """
LIMIT/OFFSET pagination

Advantages:
    - Easy to understand.
    - Easy to implement.
    - Supports direct page numbers.
    - Works naturally with small result sets.

Disadvantages:
    - Large offsets can become expensive.
    - Results can shift when rows are inserted or deleted.
    - Deep pages can be inefficient.

Keyset/cursor pagination

Advantages:
    - Efficient for sequential navigation over large datasets.
    - Avoids skipping large numbers of rows.
    - Better suited to continuously changing feeds.

Disadvantages:
    - More complex query conditions.
    - Direct "jump to page 1000" is not natural.
    - Requires a suitable stable ordering key.

Neither technique is universally superior. The correct choice depends on
the application's navigation model and data volume.
"""
    )


# ---------------------------------------------------------------------------
# 42. OFFSET CONSISTENCY PROBLEM
# ---------------------------------------------------------------------------

def demonstrate_offset_consistency_problem(
    connection: sqlite3.Connection,
) -> None:
    print_title("40. Why OFFSET Pagination Can Shift")

    print(
        """
Imagine page 1 contains:

1, 2, 3, 4, 5

A new row is inserted at the beginning before page 2 is requested.

Page 2 uses OFFSET 5, but the dataset has shifted.
A row may be duplicated or skipped between requests.

A deterministic ORDER BY helps with stable ordering, but it cannot by itself
make OFFSET pagination immune to concurrent data changes.

For critical pagination, consider:
    - keyset pagination
    - snapshot/transaction semantics
    - a stable immutable ordering key
    - an explicit "as of" boundary
"""
    )

    print("\nCurrent deterministic ordering:")
    run_query(
        connection,
        """
        SELECT employee_id, name
        FROM employees
        ORDER BY employee_id ASC
        LIMIT 5 OFFSET 5
        """,
    )


# ---------------------------------------------------------------------------
# 43. PERFORMANCE COMPLEXITY
# ---------------------------------------------------------------------------

def demonstrate_performance_concepts() -> None:
    print_title("41. Performance Considerations")

    print(
        """
Sorting can require substantial work.

A conceptual in-memory sort often has approximately O(n log n) comparison
complexity, although actual database execution depends on the optimizer,
indexes, storage engine, data distribution, and query plan.

Important considerations:

1. ORDER BY on a large unindexed result may require an explicit sort.

2. LIMIT can reduce the amount of result data sent to the application.

3. LIMIT does not automatically mean the database avoids examining many
   rows. The optimizer must still determine which rows are the best matches.

4. A suitable index can sometimes provide rows in the requested order.

5. OFFSET 1,000,000 can be much more expensive than retrieving the next
   page through a keyset condition.

6. Returning only required columns reduces data transfer and may enable
   more efficient index-only strategies in some database systems.

7. Always inspect real query plans and benchmark representative workloads.
"""
    )


# ---------------------------------------------------------------------------
# 44. EXPLAINING INDEX DESIGN
# ---------------------------------------------------------------------------

def demonstrate_index_design_rules() -> None:
    print_title("42. Practical Index Design Rules")

    print(
        """
When ORDER BY is important for performance:

- Index columns used repeatedly for filtering and sorting.
- Consider the order of columns in a composite index.
- Include a unique tie-breaker when deterministic pagination matters.
- Avoid creating indexes for every possible sort column without measuring.
- Remember that indexes increase storage and write costs.
- Check the actual query plan instead of assuming an index will be used.

Example workload:

WHERE department = 'Engineering'
ORDER BY salary DESC, employee_id ASC
LIMIT 20

A possible index shape is:

(department, salary DESC, employee_id ASC)

The best index depends on the complete workload, not one query in isolation.
"""
    )


# ---------------------------------------------------------------------------
# 45. COMMON MISTAKES
# ---------------------------------------------------------------------------

def demonstrate_common_mistakes(connection: sqlite3.Connection) -> None:
    print_title("43. Common Mistakes")

    mistakes = [
        (
            "Mistake: Using LIMIT without ORDER BY for a top-N requirement.",
            """
            SELECT name, salary
            FROM employees
            LIMIT 5
            """,
        ),
        (
            "Correct: Explicitly define what top means.",
            """
            SELECT name, salary
            FROM employees
            ORDER BY salary DESC, employee_id ASC
            LIMIT 5
            """,
        ),
        (
            "Mistake: Forgetting a tie-breaker for deterministic pagination.",
            """
            SELECT name, salary
            FROM employees
            ORDER BY salary DESC
            LIMIT 5
            """,
        ),
        (
            "Correct: Add a unique or sufficiently unique secondary key.",
            """
            SELECT employee_id, name, salary
            FROM employees
            ORDER BY salary DESC, employee_id ASC
            LIMIT 5
            """,
        ),
    ]

    for description, sql in mistakes:
        print(f"\n{description}")
        run_query(connection, sql)


# ---------------------------------------------------------------------------
# 46. LIMIT AND OFFSET SYNTAX VARIATIONS
# ---------------------------------------------------------------------------

def demonstrate_syntax_portability() -> None:
    print_title("44. SQL Dialect Differences")

    print(
        """
LIMIT/OFFSET syntax is common but not universal across all SQL databases.

SQLite supports:

LIMIT row_count OFFSET rows_to_skip

Some SQL systems support:

OFFSET rows_to_skip ROWS
FETCH NEXT row_count ROWS ONLY

Other systems historically use constructs such as TOP for limiting rows.

The general concepts are portable:
    - sort the result
    - select a bounded number of rows
    - optionally skip an initial segment

The exact syntax should be checked for the target database.
"""
    )


# ---------------------------------------------------------------------------
# 47. LIMIT AND NULL
# ---------------------------------------------------------------------------

def demonstrate_limit_with_null_filtering(
    connection: sqlite3.Connection,
) -> None:
    print_title("45. Combining NULL Filtering with Sorting and LIMIT")

    print(
        """
If NULL values should not compete with real values for the top positions,
filter them explicitly.

Example:
    Find the three highest known performance scores.
"""
    run_query(
        connection,
        """
        SELECT name, performance_score
        FROM employees
        WHERE performance_score IS NOT NULL
        ORDER BY performance_score DESC, employee_id ASC
        LIMIT 3
        """,
    )


# ---------------------------------------------------------------------------
# 48. SUBQUERY WITH ORDER BY AND LIMIT
# ---------------------------------------------------------------------------

def demonstrate_subquery_limit(connection: sqlite3.Connection) -> None:
    print_title("46. ORDER BY and LIMIT Inside a Subquery")

    print(
        """
A subquery can first select a limited set of rows, after which an outer
query can process those rows.

For example, first identify the five highest salaries and then calculate
their average.
"""
    )

    run_query(
        connection,
        """
        SELECT ROUND(AVG(salary), 2) AS average_top_five_salary
        FROM (
            SELECT salary
            FROM employees
            ORDER BY salary DESC, employee_id ASC
            LIMIT 5
        ) AS top_five
        """,
    )


# ---------------------------------------------------------------------------
# 49. TOP-N PER GROUP
# ---------------------------------------------------------------------------

def demonstrate_top_n_per_group(connection: sqlite3.Connection) -> None:
    print_title("47. Top-N Per Group with Window Functions")

    print(
        """
A difficult requirement is:

"Give me the top two employees by salary in every department."

A global:

ORDER BY salary DESC
LIMIT 2

would return only two employees across the entire company.

For top-N per group, use a window function such as ROW_NUMBER().
"""
    )

    run_query(
        connection,
        """
        SELECT
            department,
            name,
            salary
        FROM (
            SELECT
                department,
                name,
                salary,
                ROW_NUMBER() OVER (
                    PARTITION BY department
                    ORDER BY salary DESC, employee_id ASC
                ) AS position
            FROM employees
        ) AS ranked
        WHERE position <= 2
        ORDER BY department ASC, position ASC
        """,
    )


# ---------------------------------------------------------------------------
# 50. RANKING WITH TIES
# ---------------------------------------------------------------------------

def demonstrate_rank_and_dense_rank(connection: sqlite3.Connection) -> None:
    print_title("48. RANK, DENSE_RANK, and ROW_NUMBER")

    print(
        """
Window functions are useful when ties have semantic importance.

ROW_NUMBER:
    Every row receives a unique sequential position.

RANK:
    Tied rows receive the same rank, and gaps appear after ties.

DENSE_RANK:
    Tied rows receive the same rank, without gaps.

These are different from simply applying LIMIT.
"""
    )

    run_query(
        connection,
        """
        SELECT
            name,
            salary,
            ROW_NUMBER() OVER (
                ORDER BY salary DESC, employee_id ASC
            ) AS row_number_position,
            RANK() OVER (
                ORDER BY salary DESC
            ) AS salary_rank,
            DENSE_RANK() OVER (
                ORDER BY salary DESC
            ) AS dense_salary_rank
        FROM employees
        ORDER BY salary DESC, employee_id ASC
        """,
    )


# ---------------------------------------------------------------------------
# 51. FETCHING ALL TIES AT THE NTH POSITION
# ---------------------------------------------------------------------------

def demonstrate_ties_at_cutoff(connection: sqlite3.Connection) -> None:
    print_title("49. Returning All Rows Tied at a Ranking Boundary")

    print(
        """
Suppose the requirement is:

"Return everyone who belongs to the top three salary levels."

LIMIT 3 returns exactly three rows.
That may exclude employees tied with the third salary.

DENSE_RANK can express the business requirement more accurately.
"""
    )

    run_query(
        connection,
        """
        SELECT name, salary
        FROM (
            SELECT
                name,
                salary,
                DENSE_RANK() OVER (
                    ORDER BY salary DESC
                ) AS salary_level
            FROM employees
        ) AS ranked
        WHERE salary_level <= 3
        ORDER BY salary DESC, name ASC
        """,
    )


# ---------------------------------------------------------------------------
# 52. MULTIPLE SORTING CONDITIONS
# ---------------------------------------------------------------------------

def demonstrate_business_sort_priority(
    connection: sqlite3.Connection,
) -> None:
    print_title("50. Business-Oriented Sort Priorities")

    print(
        """
ORDER BY can represent business priorities.

Example:
    1. Highest performance score first.
    2. If tied, highest salary first.
    3. If still tied, earliest employee_id first.

The order of expressions is significant.
"""
    )

    run_query(
        connection,
        """
        SELECT name, performance_score, salary
        FROM employees
        WHERE performance_score IS NOT NULL
        ORDER BY
            performance_score DESC,
            salary DESC,
            employee_id ASC
        LIMIT 10
        """,
    )


# ---------------------------------------------------------------------------
# 53. CONDITIONAL SORTING
# ---------------------------------------------------------------------------

def demonstrate_conditional_sorting(connection: sqlite3.Connection) -> None:
    print_title("51. Conditional Sorting with CASE")

    print(
        """
CASE can implement custom business ordering.

Suppose the desired department priority is:

1. Engineering
2. Finance
3. Sales
4. Marketing

Alphabetical ordering does not satisfy that requirement.
"""
    )

    run_query(
        connection,
        """
        SELECT name, department, salary
        FROM employees
        ORDER BY
            CASE department
                WHEN 'Engineering' THEN 1
                WHEN 'Finance' THEN 2
                WHEN 'Sales' THEN 3
                WHEN 'Marketing' THEN 4
                ELSE 5
            END,
            name ASC
        LIMIT 12
        """,
    )


# ---------------------------------------------------------------------------
# 54. SORTING BY NULLS LAST WITH CASE
# ---------------------------------------------------------------------------

def demonstrate_explicit_null_strategy(
    connection: sqlite3.Connection,
) -> None:
    print_title("52. Explicit NULL Strategy")

    print(
        """
CASE can make NULL placement explicit in a portable style.

The first expression puts non-NULL values before NULL values.
The second expression determines the actual descending score order.
"""
    )

    run_query(
        connection,
        """
        SELECT name, performance_score
        FROM employees
        ORDER BY
            CASE
                WHEN performance_score IS NULL THEN 1
                ELSE 0
            END,
            performance_score DESC,
            employee_id ASC
        """,
    )


# ---------------------------------------------------------------------------
# 55. APPLICATION FUNCTION
# ---------------------------------------------------------------------------

def get_employee_page(
    connection: sqlite3.Connection,
    department: str | None,
    page: int,
    page_size: int,
) -> list[sqlite3.Row]:
    """
    Return one validated employee page.

    The department filter is parameterized.
    The sort column and direction are fixed by application logic rather
    than supplied directly by the caller.
    """
    validated_size, offset = validate_pagination(page, page_size)

    if department is None:
        return connection.execute(
            """
            SELECT employee_id, name, department, salary
            FROM employees
            ORDER BY salary DESC, employee_id ASC
            LIMIT ? OFFSET ?
            """,
            (validated_size, offset),
        ).fetchall()

    return connection.execute(
        """
        SELECT employee_id, name, department, salary
        FROM employees
        WHERE department = ?
        ORDER BY salary DESC, employee_id ASC
        LIMIT ? OFFSET ?
        """,
        (department, validated_size, offset),
    ).fetchall()


def demonstrate_application_function(
    connection: sqlite3.Connection,
) -> None:
    print_title("53. Building a Reusable Paginated Query Function")

    rows = get_employee_page(
        connection,
        department="Engineering",
        page=1,
        page_size=4,
    )

    print_rows(rows)


# ---------------------------------------------------------------------------
# 56. TESTS
# ---------------------------------------------------------------------------

def test_salary_descending(connection: sqlite3.Connection) -> None:
    """Verify that salary sorting is descending."""
    rows = connection.execute(
        """
        SELECT salary
        FROM employees
        ORDER BY salary DESC, employee_id ASC
        """
    ).fetchall()

    salaries = [row["salary"] for row in rows]
    assert salaries == sorted(salaries, reverse=True)


def test_limit(connection: sqlite3.Connection) -> None:
    """Verify that LIMIT restricts the number of rows."""
    rows = connection.execute(
        """
        SELECT employee_id
        FROM employees
        ORDER BY employee_id
        LIMIT 5
        """
    ).fetchall()

    assert len(rows) == 5


def test_offset(connection: sqlite3.Connection) -> None:
    """Verify that OFFSET skips the expected rows."""
    rows = connection.execute(
        """
        SELECT employee_id
        FROM employees
        ORDER BY employee_id
        LIMIT 3 OFFSET 5
        """
    ).fetchall()

    ids = [row["employee_id"] for row in rows]
    assert ids == [6, 7, 8]


def test_multiple_column_sort(connection: sqlite3.Connection) -> None:
    """Verify salary descending and employee_id ascending tie-breaking."""
    rows = connection.execute(
        """
        SELECT employee_id, salary
        FROM employees
        ORDER BY salary DESC, employee_id ASC
        """
    ).fetchall()

    for first, second in zip(rows, rows[1:]):
        if first["salary"] == second["salary"]:
            assert first["employee_id"] < second["employee_id"]
        else:
            assert first["salary"] >= second["salary"]


def test_pagination_validation() -> None:
    """Verify valid and invalid pagination inputs."""
    assert validate_pagination(1, 10) == (10, 0)
    assert validate_pagination(3, 10) == (10, 20)

    invalid_cases = [
        (0, 10),
        (-1, 10),
        (1, 0),
        (1, -10),
        (1, 101),
    ]

    for page, page_size in invalid_cases:
        try:
            validate_pagination(page, page_size)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(
                f"Expected validation error for page={page}, "
                f"page_size={page_size}"
            )


def test_keyset_pagination(connection: sqlite3.Connection) -> None:
    """Verify that keyset pagination returns the expected sequence."""
    first_page = connection.execute(
        """
        SELECT employee_id
        FROM employees
        WHERE employee_id > ?
        ORDER BY employee_id ASC
        LIMIT ?
        """,
        (0, 5),
    ).fetchall()

    last_id = first_page[-1]["employee_id"]

    second_page = connection.execute(
        """
        SELECT employee_id
        FROM employees
        WHERE employee_id > ?
        ORDER BY employee_id ASC
        LIMIT ?
        """,
        (last_id, 5),
    ).fetchall()

    first_ids = [row["employee_id"] for row in first_page]
    second_ids = [row["employee_id"] for row in second_page]

    assert first_ids == [1, 2, 3, 4, 5]
    assert second_ids == [6, 7, 8, 9, 10]


def run_tests(connection: sqlite3.Connection) -> None:
    print_title("54. Automated Tests")

    tests = [
        test_salary_descending,
        test_limit,
        test_offset,
        test_multiple_column_sort,
        lambda conn: test_pagination_validation(),
        test_keyset_pagination,
    ]

    passed = 0

    for test in tests:
        test(connection)
        print(f"PASS: {test.__name__}")
        passed += 1

    print(f"\n{passed}/{len(tests)} tests passed.")


# ---------------------------------------------------------------------------
# 57. FINAL REFERENCE EXAMPLES
# ---------------------------------------------------------------------------

def demonstrate_reference_queries(connection: sqlite3.Connection) -> None:
    print_title("55. Practical Query Reference")

    reference_queries = {
        "Ascending":
            """
            SELECT *
            FROM employees
            ORDER BY salary ASC
            """,

        "Descending":
            """
            SELECT *
            FROM employees
            ORDER BY salary DESC
            """,

        "Top 5":
            """
            SELECT *
            FROM employees
            ORDER BY salary DESC, employee_id ASC
            LIMIT 5
            """,

        "Rows 11 to 15":
            """
            SELECT *
            FROM employees
            ORDER BY employee_id ASC
            LIMIT 5 OFFSET 10
            """,

        "Filtered top 5":
            """
            SELECT *
            FROM employees
            WHERE department = 'Engineering'
            ORDER BY salary DESC, employee_id ASC
            LIMIT 5
            """,

        "Highest unique salaries":
            """
            SELECT DISTINCT salary
            FROM employees
            ORDER BY salary DESC
            LIMIT 5
            """,

        "Top 2 per department":
            """
            SELECT department, name, salary
            FROM (
                SELECT
                    department,
                    name,
                    salary,
                    ROW_NUMBER() OVER (
                        PARTITION BY department
                        ORDER BY salary DESC, employee_id ASC
                    ) AS position
                FROM employees
            )
            WHERE position <= 2
            """,
    }

    for label, sql in reference_queries.items():
        print(f"\n{label}:")
        print(" ".join(line.strip() for line in sql.strip().splitlines()))


# ---------------------------------------------------------------------------
# 58. MAIN PROGRAM
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Run the complete tutorial.

    The examples intentionally print results so the script functions as an
    executable study document rather than only a collection of comments.
    """
    connection = create_connection()

    try:
        create_tables(connection)
        insert_sample_data(connection)

        demonstrate_basic_select(connection)
        demonstrate_order_by(connection)
        demonstrate_asc_desc(connection)
        demonstrate_multiple_column_sorting(connection)
        demonstrate_sorting_expressions(connection)
        demonstrate_limit(connection)
        demonstrate_offset(connection)
        demonstrate_pagination(connection)
        demonstrate_where_order_limit(connection)
        demonstrate_top_n_patterns(connection)
        demonstrate_ties(connection)
        demonstrate_null_ordering(connection)
        demonstrate_alias_sorting(connection)
        demonstrate_clause_order(connection)
        demonstrate_aggregation_and_limit(connection)
        demonstrate_distinct_order_limit(connection)
        demonstrate_text_sorting(connection)
        demonstrate_date_sorting(connection)
        demonstrate_join_sort_limit(connection)
        demonstrate_grouped_sales(connection)
        demonstrate_filtered_pagination(connection)
        demonstrate_offset_edge_cases(connection)
        demonstrate_pagination_validation(connection)
        demonstrate_parameterized_pagination(connection)
        demonstrate_safe_dynamic_sorting(connection)
        demonstrate_safe_dynamic_direction(connection)
        demonstrate_keyset_pagination(connection)
        demonstrate_composite_keyset_pagination(connection)
        demonstrate_query_plan(connection)
        demonstrate_index_for_sorting(connection)
        demonstrate_composite_index(connection)
        demonstrate_mutation_warning(connection)
        demonstrate_product_catalog(connection)
        demonstrate_employee_directory(connection)
        demonstrate_business_analytics(connection)
        demonstrate_latest_records(connection)
        demonstrate_limit_one(connection)
        demonstrate_nth_highest(connection)
        demonstrate_pagination_tradeoffs()
        demonstrate_offset_consistency_problem(connection)
        demonstrate_performance_concepts()
        demonstrate_index_design_rules()
        demonstrate_common_mistakes(connection)
        demonstrate_syntax_portability()
        demonstrate_limit_with_null_filtering(connection)
        demonstrate_subquery_limit(connection)
        demonstrate_top_n_per_group(connection)
        demonstrate_rank_and_dense_rank(connection)
        demonstrate_ties_at_cutoff(connection)
        demonstrate_business_sort_priority(connection)
        demonstrate_conditional_sorting(connection)
        demonstrate_explicit_null_strategy(connection)
        demonstrate_application_function(connection)
        run_tests(connection)
        demonstrate_reference_queries(connection)

        print_title("Tutorial completed")
        print(
            """
The database was created entirely in memory.
All examples and tests completed without requiring external packages.
"""
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
