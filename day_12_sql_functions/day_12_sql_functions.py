"""
SQL FUNCTIONS: STRING, NUMERIC, DATE, CONDITIONAL, AND NULL-HANDLING FUNCTIONS

A self-contained study script using Python's built-in sqlite3 module.

The script teaches SQL functions from beginner through advanced concepts by
creating an in-memory relational database and executing practical SQL queries.

Important dialect note:
SQLite is used so that the script runs without external packages. SQL
functions vary across database systems. PostgreSQL, MySQL, SQL Server, Oracle,
and SQLite share many concepts but do not always use identical function names
or syntax. Comments identify important portability differences.
"""

import sqlite3
from datetime import datetime


# =============================================================================
# SECTION 1: DATABASE SETUP
# =============================================================================

def create_connection():
    """Create an in-memory SQLite database connection."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    return connection


def create_tables(connection):
    """Create tables used throughout the demonstrations."""
    connection.executescript(
        """
        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            department TEXT,
            job_title TEXT,
            salary REAL,
            commission REAL,
            hire_date TEXT,
            birth_date TEXT,
            manager_id INTEGER,
            status TEXT,
            phone TEXT,
            FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
        );

        CREATE TABLE sales (
            sale_id INTEGER PRIMARY KEY,
            employee_id INTEGER,
            sale_date TEXT,
            product TEXT,
            quantity INTEGER,
            unit_price REAL,
            discount REAL,
            region TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        );

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT,
            email TEXT,
            city TEXT,
            state TEXT,
            signup_date TEXT,
            referral_code TEXT,
            credit_limit REAL
        );
        """
    )


def insert_sample_data(connection):
    """Insert realistic data, including NULL values for edge-case testing."""
    employees = [
        (
            1, "Aarav", "Sharma", "aarav.sharma@example.com",
            "Technology", "Senior Developer", 125000, 8500,
            "2018-04-15", "1990-08-21", None, "ACTIVE", "+91-9876543210"
        ),
        (
            2, "Priya", "Verma", "PRIYA.VERMA@EXAMPLE.COM",
            "Finance", "Financial Analyst", 95000, None,
            "2020-07-01", "1994-02-14", 1, "ACTIVE", "+91-9876500000"
        ),
        (
            3, "Rohan", "Gupta", None,
            "Sales", "Sales Executive", 72000, 12500,
            "2022-01-10", "1997-11-05", 1, "ACTIVE", None
        ),
        (
            4, "Neha", "Singh", "neha.singh@example.com",
            "Technology", "Data Engineer", None, 6000,
            "2021-03-19", "1995-06-17", 1, "ACTIVE", "+91-9999999999"
        ),
        (
            5, "Vikram", "Mehta", "vikram.mehta@example.com",
            "Human Resources", "HR Manager", 88000, None,
            "2016-09-12", "1988-12-30", None, "ON_LEAVE", "+91-9123456789"
        ),
        (
            6, "Ananya", "Rao", "ananya.rao@example.com",
            "Sales", "Account Executive", 68000, 4200,
            "2023-05-22", "1999-01-09", 3, "ACTIVE", "+91-9000000000"
        ),
        (
            7, "Kabir", "Khan", "kabir.khan@example.com",
            "Technology", "DevOps Engineer", 115000, 5000,
            "2019-11-11", "1992-04-25", 1, "ACTIVE", "+91-9111111111"
        ),
        (
            8, "Ishita", "Patel", "ishita.patel@example.com",
            "Finance", "Accountant", 78000, None,
            "2024-02-01", "1998-09-16", 2, "ACTIVE", "+91-9222222222"
        ),
        (
            9, "Arjun", "Nair", "arjun.nair@example.com",
            "Sales", "Sales Manager", 102000, 15000,
            "2017-06-25", "1989-03-12", None, "ACTIVE", "+91-9333333333"
        ),
        (
            10, "Meera", "Iyer", "meera.iyer@example.com",
            "Technology", "QA Engineer", 83000, 2500,
            "2022-08-08", "1996-07-20", 7, "TERMINATED", None
        ),
    ]

    sales = [
        (1, 3, "2026-01-05", "Laptop", 2, 85000, 0.05, "North"),
        (2, 6, "2026-01-08", "Monitor", 5, 18000, 0.10, "West"),
        (3, 9, "2026-01-15", "Laptop", 1, 90000, 0.00, "South"),
        (4, 3, "2026-02-02", "Keyboard", 10, 2500, 0.05, "North"),
        (5, 6, "2026-02-14", "Laptop", 3, 82000, 0.08, "West"),
        (6, 9, "2026-02-20", "Server", 1, 350000, 0.12, "South"),
        (7, 3, "2026-03-01", "Mouse", 25, 1200, None, "North"),
        (8, 6, "2026-03-09", "Monitor", 4, 17500, 0.05, "West"),
        (9, 9, "2026-03-15", "Laptop", 2, 88000, 0.03, "South"),
        (10, 6, "2026-04-01", "Keyboard", 12, 2400, 0.00, "West"),
    ]

    customers = [
        (1, "Alpha Technologies", "contact@alpha.example.com", "Lucknow", "UP", "2024-01-10", "ALPHA10", 500000),
        (2, "Beta Retail", "sales@beta.example.com", "Delhi", "DL", "2024-04-22", None, 250000),
        (3, "Gamma Industries", None, "Mumbai", "MH", "2025-02-18", "GAMMA20", None),
        (4, "Delta Labs", "hello@delta.example.com", "Bengaluru", "KA", "2025-07-09", "DELTA5", 750000),
        (5, "Epsilon Services", "support@epsilon.example.com", "Pune", "MH", "2026-01-03", None, 100000),
    ]

    connection.executemany(
        """
        INSERT INTO employees
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        employees,
    )

    connection.executemany(
        """
        INSERT INTO sales
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        sales,
    )

    connection.executemany(
        """
        INSERT INTO customers
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        customers,
    )

    connection.commit()


# =============================================================================
# SECTION 2: OUTPUT HELPERS
# =============================================================================

def section(title):
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)


def run_query(connection, sql, parameters=(), title=None):
    """
    Execute a SELECT query and print its result.

    SQLite's parameter placeholders are used instead of string concatenation.
    This is important for security when values originate from users.
    """
    if title:
        print(f"\n{title}")

    cursor = connection.execute(sql, parameters)
    rows = cursor.fetchall()

    if not rows:
        print("(no rows)")
        return rows

    columns = rows[0].keys()
    print(" | ".join(columns))
    print("-" * 90)

    for row in rows:
        values = []
        for column in columns:
            value = row[column]
            values.append("NULL" if value is None else str(value))
        print(" | ".join(values))

    return rows


# =============================================================================
# SECTION 3: WHAT IS A SQL FUNCTION?
# =============================================================================

def demonstrate_function_fundamentals(connection):
    section("SQL FUNCTION FUNDAMENTALS")

    print(
        """
A SQL function is an operation that accepts one or more values and returns
a value.

General form:

    FUNCTION(argument1, argument2, ...)

Examples:

    UPPER(first_name)
    ROUND(salary, 2)
    LENGTH(email)
    COALESCE(commission, 0)

SQL functions can be used in SELECT, WHERE, ORDER BY, GROUP BY, HAVING,
JOIN conditions, CASE expressions, and expressions.

There are two broad conceptual families:

1. Scalar functions
   Operate on each row independently and return one value per row.

2. Aggregate functions
   Operate across multiple rows and return a value for a group or the
   complete result set.

This lesson focuses primarily on scalar functions requested for practical
SQL work: string, numeric, date, conditional, and NULL-handling functions.
Aggregate functions are also demonstrated where they interact with these
functions.
"""
    )

    run_query(
        connection,
        """
        SELECT
            first_name,
            UPPER(first_name) AS uppercase_name,
            LENGTH(first_name) AS name_length
        FROM employees
        ORDER BY employee_id
        """,
        title="One function can transform a column for every row",
    )


# =============================================================================
# SECTION 4: STRING FUNCTIONS
# =============================================================================

def demonstrate_string_functions(connection):
    section("STRING FUNCTIONS")

    print(
        """
String functions manipulate character data.

Common operations include:

    UPPER       Convert characters to uppercase
    LOWER       Convert characters to lowercase
    LENGTH      Count characters
    TRIM        Remove leading/trailing whitespace
    SUBSTR      Extract part of a string
    REPLACE     Replace matching text
    INSTR       Find the position of text
    CONCAT      Combine strings in dialects that support it
    ||          SQLite string concatenation operator

Important portability note:
SQLite uses || for concatenation. PostgreSQL also supports ||.
MySQL commonly uses CONCAT(). SQL Server commonly uses + or CONCAT().
Oracle supports ||.
"""
    )

    run_query(
        connection,
        """
        SELECT
            first_name,
            last_name,
            UPPER(first_name) AS first_upper,
            LOWER(last_name) AS last_lower,
            LENGTH(first_name) AS first_name_length
        FROM employees
        """,
        title="UPPER, LOWER, and LENGTH",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name || ' ' || last_name AS full_name
        FROM employees
        ORDER BY employee_id
        """,
        title="Concatenating strings with ||",
    )

    run_query(
        connection,
        """
        SELECT
            first_name,
            last_name,
            first_name || ' ' || SUBSTR(last_name, 1, 1) || '.' AS display_name
        FROM employees
        """,
        title="SUBSTR for constructing a display name",
    )

    run_query(
        connection,
        """
        SELECT
            email,
            LOWER(email) AS normalized_email,
            REPLACE(LOWER(email), 'example.com', 'company.com') AS company_email
        FROM employees
        WHERE email IS NOT NULL
        """,
        title="LOWER and REPLACE for email normalization",
    )

    run_query(
        connection,
        """
        SELECT
            first_name,
            INSTR(LOWER(first_name), 'a') AS first_a_position
        FROM employees
        """,
        title="INSTR searches for a substring",
    )

    run_query(
        connection,
        """
        SELECT
            first_name,
            TRIM('   ' || first_name || '   ') AS trimmed_name
        FROM employees
        """,
        title="TRIM removes surrounding whitespace",
    )

    print(
        """
String function edge cases:

    LENGTH(NULL) returns NULL.
    UPPER(NULL) returns NULL.
    LOWER(NULL) returns NULL.
    REPLACE(NULL, 'x', 'y') returns NULL.

NULL is not the same thing as an empty string.
An empty string has a value of zero characters; NULL represents missing or
unknown data.
"""
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            email,
            LENGTH(email) AS email_length
        FROM employees
        ORDER BY employee_id
        """,
        title="NULL behavior in string functions",
    )


# =============================================================================
# SECTION 5: NUMERIC FUNCTIONS
# =============================================================================

def demonstrate_numeric_functions(connection):
    section("NUMERIC FUNCTIONS")

    print(
        """
Numeric functions transform or analyze numbers.

Common SQL numeric functions include:

    ABS       Absolute value
    ROUND     Round a number
    CEIL      Round upward
    FLOOR     Round downward
    MOD       Remainder
    POWER     Raise a number to a power
    SQRT      Square root
    SIGN      Determine sign in dialects that support it

SQLite provides many mathematical functions in modern builds, but portability
varies. Basic functions such as ROUND and ABS are widely available.
"""
    )

    run_query(
        connection,
        """
        SELECT
            sale_id,
            unit_price,
            discount,
            ROUND(unit_price, 2) AS rounded_price,
            ABS(discount) AS absolute_discount
        FROM sales
        """,
        title="ROUND and ABS",
    )

    run_query(
        connection,
        """
        SELECT
            sale_id,
            quantity,
            unit_price,
            quantity * unit_price AS gross_amount,
            ROUND(quantity * unit_price * (1 - COALESCE(discount, 0)), 2)
                AS net_amount
        FROM sales
        """,
        title="Numeric expressions combined with COALESCE",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            salary,
            ROUND(salary / 12.0, 2) AS monthly_salary,
            ROUND(COALESCE(commission, 0) / 12.0, 2) AS monthly_commission
        FROM employees
        """,
        title="Monthly compensation calculation",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            salary,
            ROUND(COALESCE(salary, 0) * 1.10, 2) AS salary_after_10_percent_raise
        FROM employees
        """,
        title="ROUND applied to a business calculation",
    )

    run_query(
        connection,
        """
        SELECT
            sale_id,
            quantity,
            quantity % 2 AS remainder_when_divided_by_two
        FROM sales
        """,
        title="Modulo using the SQLite % operator",
    )

    print(
        """
Rounding deserves careful attention.

ROUND(10.125, 2) asks the database to round a numeric result. Exact behavior
around floating-point boundaries can differ from decimal arithmetic performed
with exact numeric types.

For financial systems, database-specific DECIMAL/NUMERIC types and explicit
rounding rules are generally preferable to uncontrolled floating-point
calculations.
"""
    )


# =============================================================================
# SECTION 6: DATE AND TIME FUNCTIONS
# =============================================================================

def demonstrate_date_functions(connection):
    section("DATE AND TIME FUNCTIONS")

    print(
        """
SQLite stores dates commonly as TEXT, REAL, or INTEGER values rather than
having a dedicated DATE type.

Useful SQLite functions include:

    date()
    time()
    datetime()
    julianday()
    strftime()

Other database systems have different syntax.

Examples:
    PostgreSQL: CURRENT_DATE, CURRENT_TIMESTAMP, EXTRACT()
    MySQL: CURDATE(), NOW(), DATE_FORMAT()
    SQL Server: GETDATE(), DATEPART(), DATEADD()
    Oracle: SYSDATE, ADD_MONTHS(), TRUNC()

Dates should normally be stored in an unambiguous representation such as
YYYY-MM-DD when SQLite TEXT storage is used.
"""
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            hire_date,
            strftime('%Y', hire_date) AS hire_year,
            strftime('%m', hire_date) AS hire_month,
            strftime('%d', hire_date) AS hire_day
        FROM employees
        """,
        title="Extracting date components with strftime",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            hire_date,
            date(hire_date, '+1 year') AS first_anniversary
        FROM employees
        """,
        title="Adding one year to a date",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            hire_date,
            CAST(
                julianday('2026-09-12') - julianday(hire_date)
                AS INTEGER
            ) AS days_since_hiring
        FROM employees
        """,
        title="Calculating elapsed days",
    )

    run_query(
        connection,
        """
        SELECT
            sale_id,
            sale_date,
            date(sale_date, 'start of month') AS month_start,
            date(sale_date, '+1 month', 'start of month', '-1 day')
                AS month_end
        FROM sales
        """,
        title="Finding month boundaries",
    )

    run_query(
        connection,
        """
        SELECT
            sale_id,
            sale_date,
            strftime('%Y-%m', sale_date) AS sales_month
        FROM sales
        ORDER BY sales_month, sale_id
        """,
        title="Creating a year-month reporting key",
    )

    print(
        """
Date edge cases:

- Invalid date strings can produce NULL or unexpected results.
- Time zones require special care.
- Daylight-saving changes matter when working with local timestamps.
- Comparing dates as strings only works safely when the stored format is
  lexicographically sortable, such as YYYY-MM-DD.
- A date and a timestamp are not interchangeable concepts.
- Business-day calculations often require a calendar table rather than
  simple date arithmetic.
"""
    )


# =============================================================================
# SECTION 7: CONDITIONAL LOGIC WITH CASE
# =============================================================================

def demonstrate_conditional_functions(connection):
    section("CONDITIONAL FUNCTIONS AND CASE EXPRESSIONS")

    print(
        """
SQL conditional logic is commonly expressed with CASE.

General searched CASE form:

    CASE
        WHEN condition1 THEN result1
        WHEN condition2 THEN result2
        ELSE default_result
    END

Simple CASE form:

    CASE column
        WHEN value1 THEN result1
        WHEN value2 THEN result2
        ELSE default_result
    END

CASE is an expression, not merely a programming-language-style statement.
It produces a value that can be selected, sorted, grouped, aggregated, or
used inside another expression.
"""
    )

    run_query(
        connection,
        """
        SELECT
            first_name,
            salary,
            CASE
                WHEN salary IS NULL THEN 'Salary unavailable'
                WHEN salary >= 120000 THEN 'Executive range'
                WHEN salary >= 90000 THEN 'Senior range'
                WHEN salary >= 70000 THEN 'Professional range'
                ELSE 'Entry range'
            END AS salary_band
        FROM employees
        ORDER BY salary DESC
        """,
        title="Searched CASE expression",
    )

    run_query(
        connection,
        """
        SELECT
            first_name,
            status,
            CASE status
                WHEN 'ACTIVE' THEN 'Currently employed'
                WHEN 'ON_LEAVE' THEN 'Temporarily unavailable'
                WHEN 'TERMINATED' THEN 'Employment ended'
                ELSE 'Unknown status'
            END AS status_description
        FROM employees
        """,
        title="Simple CASE expression",
    )

    run_query(
        connection,
        """
        SELECT
            sale_id,
            quantity * unit_price AS gross_amount,
            CASE
                WHEN quantity * unit_price >= 300000 THEN 'Very High'
                WHEN quantity * unit_price >= 100000 THEN 'High'
                WHEN quantity * unit_price >= 50000 THEN 'Medium'
                ELSE 'Low'
            END AS transaction_size
        FROM sales
        """,
        title="CASE based on a calculated expression",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            CASE
                WHEN commission IS NULL THEN 'No commission'
                WHEN commission = 0 THEN 'Zero commission'
                ELSE 'Commission eligible'
            END AS commission_status
        FROM employees
        """,
        title="CASE distinguishes NULL from zero",
    )

    print(
        """
Important distinction:

    commission IS NULL

is different from:

    commission = 0

NULL means the value is unknown, missing, or not applicable.
Zero is a known numeric value.
"""
    )


# =============================================================================
# SECTION 8: NULL FUNDAMENTALS
# =============================================================================

def demonstrate_null_fundamentals(connection):
    section("NULL FUNDAMENTALS")

    print(
        """
NULL is one of the most important concepts in SQL.

NULL generally represents missing, unknown, or unavailable information.

NULL does not mean:

- zero
- false
- empty string
- blank text
- an ordinary value

SQL uses three-valued logic:

    TRUE
    FALSE
    UNKNOWN

A comparison involving NULL normally produces UNKNOWN.

For example:

    salary = NULL

does not correctly find NULL salaries.

Use:

    salary IS NULL

or:

    salary IS NOT NULL
"""
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            salary
        FROM employees
        WHERE salary IS NULL
        """,
        title="Correct NULL test with IS NULL",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            commission
        FROM employees
        WHERE commission IS NOT NULL
        """,
        title="IS NOT NULL",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            salary,
            salary + 10000 AS salary_plus_raise
        FROM employees
        """,
        title="Arithmetic involving NULL produces NULL",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            commission,
            COALESCE(commission, 0) AS commission_or_zero
        FROM employees
        """,
        title="COALESCE converts NULL to a fallback value",
    )


# =============================================================================
# SECTION 9: COALESCE
# =============================================================================

def demonstrate_coalesce(connection):
    section("COALESCE")

    print(
        """
COALESCE returns the first non-NULL expression.

General form:

    COALESCE(value1, value2, value3, ...)

Examples:

    COALESCE(commission, 0)

    COALESCE(phone, 'Not provided')

    COALESCE(email, phone, 'No contact information')

COALESCE is useful for defaults, reporting, calculations, and presentation.
"""
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            COALESCE(phone, 'Not provided') AS contact_phone,
            COALESCE(email, 'Email unavailable') AS contact_email
        FROM employees
        """,
        title="Replacing missing presentation values",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            salary,
            commission,
            COALESCE(salary, 0) + COALESCE(commission, 0) AS total_compensation
        FROM employees
        """,
        title="Safely adding potentially NULL numbers",
    )

    run_query(
        connection,
        """
        SELECT
            customer_id,
            customer_name,
            COALESCE(referral_code, 'NO-REFERRAL') AS effective_referral_code,
            COALESCE(credit_limit, 0) AS effective_credit_limit
        FROM customers
        """,
        title="Multiple NULL defaults in customer data",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            COALESCE(email, phone, 'No contact available') AS best_contact
        FROM employees
        """,
        title="COALESCE with multiple fallback options",
    )


# =============================================================================
# SECTION 10: NULLIF
# =============================================================================

def demonstrate_nullif(connection):
    section("NULLIF")

    print(
        """
NULLIF compares two expressions.

    NULLIF(a, b)

If a equals b, NULLIF returns NULL.
Otherwise, it returns a.

It is particularly useful for avoiding special values such as zero from
participating in calculations or for converting sentinel values into NULL.

Example:

    revenue / NULLIF(expenses, 0)

If expenses is zero, the denominator becomes NULL instead of zero.
"""
    )

    connection.execute(
        """
        CREATE TABLE ratios (
            metric_id INTEGER PRIMARY KEY,
            numerator REAL,
            denominator REAL
        )
        """
    )

    connection.executemany(
        "INSERT INTO ratios VALUES (?, ?, ?)",
        [
            (1, 100, 20),
            (2, 100, 0),
            (3, 100, None),
            (4, 0, 10),
        ],
    )

    run_query(
        connection,
        """
        SELECT
            metric_id,
            numerator,
            denominator,
            numerator / NULLIF(denominator, 0) AS safe_ratio
        FROM ratios
        """,
        title="NULLIF prevents division by zero",
    )

    run_query(
        connection,
        """
        SELECT
            metric_id,
            NULLIF(denominator, 0) AS normalized_denominator
        FROM ratios
        """,
        title="NULLIF converting zero into NULL",
    )


# =============================================================================
# SECTION 11: IFNULL AND DIALECT DIFFERENCES
# =============================================================================

def demonstrate_ifnull(connection):
    section("IFNULL AND DIALECT-SPECIFIC NULL HANDLING")

    print(
        """
SQLite provides IFNULL(value, fallback).

It behaves similarly to the two-argument form of COALESCE:

    IFNULL(commission, 0)

The portable SQL approach is usually:

    COALESCE(commission, 0)

because COALESCE is part of standard SQL and accepts multiple arguments.

Other database systems have related functions:

    SQL Server: ISNULL()
    MySQL: IFNULL()
    Oracle: NVL()
    Standard SQL: COALESCE()
"""
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            commission,
            IFNULL(commission, 0) AS commission_ifnull,
            COALESCE(commission, 0) AS commission_coalesce
        FROM employees
        """,
        title="IFNULL and COALESCE comparison in SQLite",
    )


# =============================================================================
# SECTION 12: AGGREGATES + FUNCTIONS
# =============================================================================

def demonstrate_aggregate_interactions(connection):
    section("AGGREGATE FUNCTIONS COMBINED WITH SCALAR FUNCTIONS")

    print(
        """
Aggregate functions operate across rows.

Common aggregate functions:

    COUNT
    SUM
    AVG
    MIN
    MAX

Scalar functions operate row by row.

They can be combined.

For example:

    ROUND(AVG(salary), 2)

first calculates the average and then rounds the result.

Another important issue is NULL behavior:

    AVG(salary)

ignores NULL salary values.

    SUM(commission)

also ignores NULL commission values.

    COUNT(commission)

counts only rows where commission is non-NULL.

    COUNT(*)

counts rows regardless of NULL values in individual columns.
"""
    )

    run_query(
        connection,
        """
        SELECT
            department,
            COUNT(*) AS employee_count,
            COUNT(salary) AS employees_with_salary,
            ROUND(AVG(salary), 2) AS average_salary,
            MIN(salary) AS minimum_salary,
            MAX(salary) AS maximum_salary
        FROM employees
        GROUP BY department
        ORDER BY department
        """,
        title="Aggregate functions and NULL-aware behavior",
    )

    run_query(
        connection,
        """
        SELECT
            department,
            ROUND(AVG(COALESCE(salary, 0)), 2) AS average_treating_missing_as_zero
        FROM employees
        GROUP BY department
        ORDER BY department
        """,
        title="How COALESCE changes aggregate meaning",
    )

    print(
        """
The two averages above answer different business questions.

AVG(salary):
    Average among employees whose salary is known.

AVG(COALESCE(salary, 0)):
    Average after treating missing salary as zero.

The second interpretation may be mathematically valid but business-wise
incorrect. NULL-handling is therefore a data-modeling and business-rule
decision, not merely a syntax decision.
"""
    )


# =============================================================================
# SECTION 13: FUNCTIONS IN WHERE
# =============================================================================

def demonstrate_functions_in_where(connection):
    section("FUNCTIONS IN WHERE CLAUSES")

    print(
        """
Functions can be used to transform values before filtering.

Example:

    WHERE LOWER(email) = '...'

This is convenient for case normalization.

A performance concern arises when a function is applied to an indexed column.
A normal index may not be usable efficiently depending on the database,
expression, and optimizer.

Alternatives include:

- normalized stored data
- generated columns
- functional/expression indexes where supported
- case-insensitive data types or collations where appropriate
"""
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            email
        FROM employees
        WHERE LOWER(email) = 'priya.verma@example.com'
        """,
        title="Case-insensitive lookup using LOWER",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            salary
        FROM employees
        WHERE ROUND(COALESCE(salary, 0), -4) >= 100000
        """,
        title="Numeric function used for filtering",
    )


# =============================================================================
# SECTION 14: FUNCTIONS IN ORDER BY
# =============================================================================

def demonstrate_functions_in_order_by(connection):
    section("FUNCTIONS IN ORDER BY")

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            last_name
        FROM employees
        ORDER BY LENGTH(first_name), LOWER(first_name)
        """,
        title="Sorting by calculated values",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            commission
        FROM employees
        ORDER BY COALESCE(commission, 0) DESC, first_name
        """,
        title="Sorting NULL values through COALESCE",
    )


# =============================================================================
# SECTION 15: FUNCTIONS IN GROUP BY
# =============================================================================

def demonstrate_functions_in_group_by(connection):
    section("FUNCTIONS IN GROUP BY")

    run_query(
        connection,
        """
        SELECT
            strftime('%Y-%m', sale_date) AS sales_month,
            COUNT(*) AS number_of_sales,
            ROUND(SUM(quantity * unit_price * (1 - COALESCE(discount, 0))), 2)
                AS net_sales
        FROM sales
        GROUP BY strftime('%Y-%m', sale_date)
        ORDER BY sales_month
        """,
        title="Grouping transactions by month",
    )

    run_query(
        connection,
        """
        SELECT
            CASE
                WHEN quantity * unit_price >= 100000 THEN 'Large'
                ELSE 'Small'
            END AS transaction_class,
            COUNT(*) AS transaction_count
        FROM sales
        GROUP BY
            CASE
                WHEN quantity * unit_price >= 100000 THEN 'Large'
                ELSE 'Small'
            END
        ORDER BY transaction_class
        """,
        title="Grouping using CASE",
    )


# =============================================================================
# SECTION 16: HAVING WITH FUNCTION RESULTS
# =============================================================================

def demonstrate_having(connection):
    section("HAVING WITH FUNCTION RESULTS")

    print(
        """
WHERE filters rows before grouping.

HAVING filters groups after aggregation.

This distinction matters:

    WHERE salary > 80000

filters individual employees.

    HAVING AVG(salary) > 80000

filters departments based on an aggregate result.
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
        HAVING AVG(salary) > 80000
        ORDER BY average_salary DESC
        """,
        title="HAVING filters groups",
    )


# =============================================================================
# SECTION 17: NESTED FUNCTIONS
# =============================================================================

def demonstrate_nested_functions(connection):
    section("NESTED FUNCTIONS")

    print(
        """
Functions can be nested.

For example:

    UPPER(TRIM(first_name))

The database evaluates the inner expression and passes its result to the
outer function.

A practical example:

    COALESCE(LOWER(TRIM(email)), 'missing')

This first trims the value, then converts it to lowercase, then replaces
NULL with a fallback.

Deep nesting can become difficult to read. CTEs, subqueries, views, or
generated columns may improve maintainability.
"""
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            email,
            COALESCE(LOWER(TRIM(email)), 'missing') AS normalized_email
        FROM employees
        """,
        title="Nested string and NULL functions",
    )

    run_query(
        connection,
        """
        SELECT
            sale_id,
            ROUND(
                ABS(
                    quantity * unit_price *
                    (1 - COALESCE(discount, 0))
                ),
                2
            ) AS normalized_amount
        FROM sales
        """,
        title="Nested numeric and NULL functions",
    )


# =============================================================================
# SECTION 18: REAL-WORLD BUSINESS METRICS
# =============================================================================

def demonstrate_business_metrics(connection):
    section("REAL-WORLD BUSINESS METRICS")

    print(
        """
SQL functions are frequently used to construct analytical metrics.

Examples include:

    revenue
    discount-adjusted revenue
    commission
    average transaction value
    salary bands
    customer age or tenure
    monthly revenue
    missing-data indicators
    contact-data completeness
    performance classifications
"""
    )

    run_query(
        connection,
        """
        SELECT
            s.sale_id,
            e.first_name || ' ' || e.last_name AS salesperson,
            s.product,
            s.quantity,
            s.unit_price,
            COALESCE(s.discount, 0) AS discount_rate,
            ROUND(s.quantity * s.unit_price, 2) AS gross_revenue,
            ROUND(
                s.quantity * s.unit_price *
                (1 - COALESCE(s.discount, 0)),
                2
            ) AS net_revenue
        FROM sales AS s
        JOIN employees AS e
            ON e.employee_id = s.employee_id
        ORDER BY net_revenue DESC
        """,
        title="Net revenue per transaction",
    )

    run_query(
        connection,
        """
        SELECT
            e.department,
            COUNT(s.sale_id) AS transactions,
            ROUND(
                SUM(
                    s.quantity * s.unit_price *
                    (1 - COALESCE(s.discount, 0))
                ),
                2
            ) AS net_revenue
        FROM employees AS e
        LEFT JOIN sales AS s
            ON s.employee_id = e.employee_id
        GROUP BY e.department
        ORDER BY net_revenue DESC
        """,
        title="Department-level net revenue",
    )


# =============================================================================
# SECTION 19: DATE + CONDITIONAL + NULL COMBINATION
# =============================================================================

def demonstrate_combined_logic(connection):
    section("COMBINING STRING, NUMERIC, DATE, CONDITIONAL, AND NULL FUNCTIONS")

    run_query(
        connection,
        """
        SELECT
            e.employee_id,
            UPPER(e.first_name || ' ' || e.last_name) AS employee_name,
            COALESCE(e.email, 'NO EMAIL') AS email_status,
            COALESCE(e.salary, 0) AS salary_value,
            ROUND(COALESCE(e.commission, 0), 2) AS commission_value,
            strftime('%Y-%m', e.hire_date) AS hire_month,
            CASE
                WHEN e.salary IS NULL THEN 'MISSING SALARY'
                WHEN e.salary >= 100000 THEN 'HIGH'
                WHEN e.salary >= 80000 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS salary_category
        FROM employees AS e
        ORDER BY e.employee_id
        """,
        title="Multi-function employee report",
    )

    run_query(
        connection,
        """
        SELECT
            sale_id,
            UPPER(product) AS product_name,
            date(sale_date) AS transaction_date,
            strftime('%Y-%m', sale_date) AS reporting_month,
            ROUND(quantity * unit_price, 2) AS gross_amount,
            ROUND(
                quantity * unit_price *
                (1 - COALESCE(discount, 0)),
                2
            ) AS net_amount,
            CASE
                WHEN quantity * unit_price >= 250000 THEN 'Enterprise'
                WHEN quantity * unit_price >= 100000 THEN 'Large'
                WHEN quantity * unit_price >= 50000 THEN 'Medium'
                ELSE 'Small'
            END AS deal_size
        FROM sales
        ORDER BY sale_date
        """,
        title="Multi-function sales report",
    )


# =============================================================================
# SECTION 20: CONDITIONAL NULL-HANDLING PATTERNS
# =============================================================================

def demonstrate_conditional_null_patterns(connection):
    section("CONDITIONAL NULL-HANDLING PATTERNS")

    print(
        """
A common pattern is:

    CASE
        WHEN value IS NULL THEN ...
        ELSE ...
    END

Another is:

    COALESCE(value, fallback)

They are not interchangeable in every situation.

Use COALESCE when the requirement is:
    "Give me the first available non-NULL value."

Use CASE when the requirement is:
    "Apply business rules based on conditions."

Use NULLIF when the requirement is:
    "Convert a particular value into NULL."
"""
    )

    run_query(
        connection,
        """
        SELECT
            first_name,
            CASE
                WHEN email IS NULL THEN 'Missing'
                WHEN LENGTH(TRIM(email)) = 0 THEN 'Blank'
                ELSE 'Available'
            END AS email_quality
        FROM employees
        """,
        title="CASE for data-quality classification",
    )

    run_query(
        connection,
        """
        SELECT
            customer_name,
            COALESCE(
                NULLIF(TRIM(email), ''),
                'No usable email'
            ) AS usable_email
        FROM customers
        """,
        title="NULLIF + COALESCE for blank-or-NULL handling",
    )


# =============================================================================
# SECTION 21: DIVISION BY ZERO AND SAFE METRICS
# =============================================================================

def demonstrate_safe_calculations(connection):
    section("SAFE CALCULATIONS AND EDGE CASES")

    connection.execute(
        """
        CREATE TABLE performance (
            employee_id INTEGER,
            revenue REAL,
            target REAL
        )
        """
    )

    connection.executemany(
        "INSERT INTO performance VALUES (?, ?, ?)",
        [
            (1, 150000, 100000),
            (2, 80000, 0),
            (3, 50000, None),
            (4, 0, 100000),
        ],
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            revenue,
            target,
            ROUND(
                revenue / NULLIF(target, 0) * 100,
                2
            ) AS achievement_percent
        FROM performance
        """,
        title="Safe percentage calculation",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            revenue,
            target,
            CASE
                WHEN target IS NULL THEN 'Target unavailable'
                WHEN target = 0 THEN 'Target is zero'
                WHEN revenue >= target THEN 'Target achieved'
                ELSE 'Target not achieved'
            END AS performance_status
        FROM performance
        """,
        title="CASE handles multiple edge cases",
    )


# =============================================================================
# SECTION 22: STRING DATA QUALITY
# =============================================================================

def demonstrate_data_cleaning(connection):
    section("DATA CLEANING WITH SQL FUNCTIONS")

    connection.execute(
        """
        CREATE TABLE raw_contacts (
            contact_id INTEGER PRIMARY KEY,
            raw_name TEXT,
            raw_email TEXT,
            raw_phone TEXT
        )
        """
    )

    connection.executemany(
        "INSERT INTO raw_contacts VALUES (?, ?, ?, ?)",
        [
            (1, "  Rahul Sharma ", " RAHUL@EXAMPLE.COM ", " +91 98765 43210 "),
            (2, "PRIYA VERMA", "priya@example.com", None),
            (3, None, "   ", "9999999999"),
            (4, "  ananya   rao  ", None, " 9000000000 "),
        ],
    )

    run_query(
        connection,
        """
        SELECT
            contact_id,
            raw_name,
            TRIM(raw_name) AS trimmed_name,
            LOWER(TRIM(raw_email)) AS normalized_email,
            TRIM(raw_phone) AS normalized_phone
        FROM raw_contacts
        """,
        title="Basic data cleaning",
    )

    run_query(
        connection,
        """
        SELECT
            contact_id,
            COALESCE(
                NULLIF(LOWER(TRIM(raw_email)), ''),
                'missing@example.com'
            ) AS safe_email
        FROM raw_contacts
        """,
        title="Handling whitespace and NULL together",
    )

    run_query(
        connection,
        """
        SELECT
            contact_id,
            REPLACE(
                REPLACE(TRIM(raw_phone), ' ', ''),
                '-',
                ''
            ) AS normalized_phone
        FROM raw_contacts
        """,
        title="Removing formatting characters",
    )


# =============================================================================
# SECTION 23: FUNCTIONAL INDEX CONCEPT
# =============================================================================

def demonstrate_expression_index(connection):
    section("PERFORMANCE: EXPRESSION INDEXES")

    print(
        """
Applying a function to an indexed column can prevent a normal index from
being used efficiently.

Example condition:

    WHERE LOWER(email) = ?

A database may need to evaluate LOWER(email) for many rows.

Some database systems support expression or functional indexes:

    CREATE INDEX ... ON employees (LOWER(email))

SQLite also supports indexes on expressions.

The exact optimizer behavior depends on the database version, expression,
query, statistics, and schema.
"""
    )

    connection.execute(
        """
        CREATE INDEX idx_employees_lower_email
        ON employees(LOWER(email))
        """
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            email
        FROM employees
        WHERE LOWER(email) = ?
        """,
        ("aarav.sharma@example.com",),
        title="Lookup supported by an expression index",
    )

    run_query(
        connection,
        """
        EXPLAIN QUERY PLAN
        SELECT employee_id
        FROM employees
        WHERE LOWER(email) = ?
        """,
        ("aarav.sharma@example.com",),
        title="SQLite query-plan inspection",
    )


# =============================================================================
# SECTION 24: USER INPUT AND SQL INJECTION
# =============================================================================

def demonstrate_parameterized_queries(connection):
    section("SECURITY: PARAMETERIZED SQL")

    print(
        """
Never construct SQL by directly concatenating untrusted input.

Unsafe conceptual pattern:

    SELECT ... WHERE email = '""" + "USER_INPUT" + """'

A malicious value could alter the structure of the SQL statement.

Use parameterized SQL instead:

    WHERE email = ?

The SQL structure and user-supplied value remain separate.

The Python sqlite3 API binds parameters safely.
"""
    )

    user_email = "PRIYA.VERMA@EXAMPLE.COM"

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            email
        FROM employees
        WHERE LOWER(email) = LOWER(?)
        """,
        (user_email,),
        title="Safe parameterized lookup",
    )


# =============================================================================
# SECTION 25: FUNCTION DETERMINISM AND INDEXING CONSIDERATIONS
# =============================================================================

def demonstrate_function_design_concepts():
    section("FUNCTION DESIGN AND DETERMINISM")

    print(
        """
Database systems distinguish between expressions that consistently produce
the same result for the same input and functions whose result can change.

Examples of potentially non-deterministic concepts include:

    CURRENT_TIMESTAMP
    RANDOM()

Deterministic expressions are easier to reason about and can often be used
more predictably in indexes, generated columns, constraints, and caching.

A function can also affect:

    query optimization
    index usage
    sorting
    grouping
    memory consumption
    CPU cost

A function applied to millions of rows can become expensive even when the
function itself appears simple.

The best optimization is often to avoid unnecessary transformation of data
during large scans, while preserving correctness and readability.
"""
    )


# =============================================================================
# SECTION 26: COMMON MISTAKES
# =============================================================================

def demonstrate_common_mistakes(connection):
    section("COMMON SQL FUNCTION MISTAKES")

    print(
        """
Mistake 1: Comparing NULL with =

    WRONG: salary = NULL
    RIGHT: salary IS NULL

Mistake 2: Treating NULL as zero

    NULL and zero represent different information.

Mistake 3: Assuming all SQL dialects have the same functions.

    SQLite, PostgreSQL, MySQL, SQL Server, and Oracle differ.

Mistake 4: Forgetting NULL propagation.

    salary + commission becomes NULL if either operand is NULL.

Mistake 5: Applying a function to an indexed column without considering
performance.

Mistake 6: Using COALESCE to hide a data-quality problem.

    COALESCE(email, 'unknown') is useful for presentation, but it does not
    repair the underlying missing email.

Mistake 7: Treating date strings as valid dates without validation.

Mistake 8: Rounding too early.

    ROUND intermediate values can produce a different result from rounding
    only the final metric.

Mistake 9: Confusing WHERE and HAVING.

Mistake 10: Assuming empty strings and NULL are equivalent.
"""
    )

    run_query(
        connection,
        """
        SELECT
            first_name,
            salary,
            CASE
                WHEN salary IS NULL THEN 'UNKNOWN'
                WHEN salary = 0 THEN 'ZERO'
                ELSE 'POSITIVE'
            END AS salary_state
        FROM employees
        """,
        title="Explicitly distinguishing NULL, zero, and ordinary values",
    )


# =============================================================================
# SECTION 27: SQL DIALECT COMPARISON
# =============================================================================

def demonstrate_dialect_comparison():
    section("SQL DIALECT COMPARISON")

    print(
        """
The underlying concepts are portable, but exact function syntax is not.

Concept                    SQLite                 PostgreSQL
---------------------------------------------------------------------------
Uppercase                  UPPER(x)               UPPER(x)
Lowercase                  LOWER(x)               LOWER(x)
Length                     LENGTH(x)              LENGTH(x)
Substring                  SUBSTR(x,...)          SUBSTRING(...)
Rounding                   ROUND(x, n)            ROUND(x, n)
Absolute value             ABS(x)                 ABS(x)
NULL fallback              COALESCE(...)          COALESCE(...)
Two-value fallback         IFNULL(...)            COALESCE(...)
Current date               date('now')            CURRENT_DATE
Current timestamp          datetime('now')        CURRENT_TIMESTAMP
String concatenation       x || y                 x || y

MySQL often uses:
    CONCAT()
    IFNULL()
    CURDATE()
    DATE_FORMAT()

SQL Server commonly uses:
    CONCAT()
    ISNULL()
    GETDATE()
    DATEPART()

Oracle commonly uses:
    NVL()
    SYSDATE
    ADD_MONTHS()
    TO_CHAR()

The SQL concept should be learned separately from the syntax of one database.
"""
    )


# =============================================================================
# SECTION 28: ADVANCED REPORTING QUERY
# =============================================================================

def demonstrate_advanced_reporting_query(connection):
    section("ADVANCED REPORTING QUERY")

    print(
        """
This query combines:

    joins
    string functions
    numeric functions
    date functions
    CASE
    COALESCE
    aggregation
    GROUP BY
    ORDER BY

The purpose is to demonstrate how functions become part of a real reporting
pipeline rather than being isolated syntax exercises.
"""
    )

    run_query(
        connection,
        """
        SELECT
            e.department,
            UPPER(e.first_name || ' ' || e.last_name) AS employee_name,
            COUNT(s.sale_id) AS transaction_count,
            ROUND(
                COALESCE(
                    SUM(
                        s.quantity * s.unit_price *
                        (1 - COALESCE(s.discount, 0))
                    ),
                    0
                ),
                2
            ) AS net_revenue,
            CASE
                WHEN COALESCE(
                    SUM(
                        s.quantity * s.unit_price *
                        (1 - COALESCE(s.discount, 0))
                    ),
                    0
                ) >= 300000
                    THEN 'Top performer'
                WHEN COALESCE(
                    SUM(
                        s.quantity * s.unit_price *
                        (1 - COALESCE(s.discount, 0))
                    ),
                    0
                ) >= 100000
                    THEN 'Strong performer'
                ELSE 'Developing'
            END AS performance_class
        FROM employees AS e
        LEFT JOIN sales AS s
            ON s.employee_id = e.employee_id
        GROUP BY
            e.employee_id,
            e.department,
            e.first_name,
            e.last_name
        ORDER BY net_revenue DESC, employee_name
        """,
        title="Employee performance report",
    )


# =============================================================================
# SECTION 29: CTE FOR READABILITY
# =============================================================================

def demonstrate_cte_with_functions(connection):
    section("CTEs AND FUNCTION-HEAVY QUERIES")

    print(
        """
A Common Table Expression, or CTE, can separate transformation stages.

Instead of creating one extremely long expression, a CTE can first calculate
a reusable business value and the outer query can classify it.

This often improves readability and debugging.
"""
    )

    run_query(
        connection,
        """
        WITH sales_calculated AS (
            SELECT
                sale_id,
                employee_id,
                sale_date,
                quantity * unit_price AS gross_amount,
                quantity * unit_price *
                    (1 - COALESCE(discount, 0)) AS net_amount
            FROM sales
        )
        SELECT
            sale_id,
            employee_id,
            strftime('%Y-%m', sale_date) AS sales_month,
            ROUND(gross_amount, 2) AS gross_amount,
            ROUND(net_amount, 2) AS net_amount,
            CASE
                WHEN net_amount >= 200000 THEN 'Large'
                WHEN net_amount >= 75000 THEN 'Medium'
                ELSE 'Small'
            END AS deal_class
        FROM sales_calculated
        ORDER BY net_amount DESC
        """,
        title="CTE separating calculation from classification",
    )


# =============================================================================
# SECTION 30: VIEW USING FUNCTIONS
# =============================================================================

def demonstrate_view(connection):
    section("VIEWS AND REUSABLE FUNCTION LOGIC")

    print(
        """
A view can encapsulate frequently used SQL transformations.

This can provide a stable reporting interface while keeping the raw table
schema separate from presentation or analytical logic.
"""
    )

    connection.execute(
        """
        CREATE VIEW employee_directory AS
        SELECT
            employee_id,
            UPPER(first_name || ' ' || last_name) AS employee_name,
            LOWER(email) AS normalized_email,
            COALESCE(phone, 'Not provided') AS phone,
            department,
            CASE
                WHEN status = 'ACTIVE' THEN 'Active'
                WHEN status = 'ON_LEAVE' THEN 'On leave'
                WHEN status = 'TERMINATED' THEN 'Terminated'
                ELSE 'Unknown'
            END AS employment_status
        FROM employees
        """
    )

    run_query(
        connection,
        """
        SELECT *
        FROM employee_directory
        ORDER BY employee_name
        """,
        title="Querying a function-based view",
    )


# =============================================================================
# SECTION 31: WINDOW FUNCTIONS + SCALAR FUNCTIONS
# =============================================================================

def demonstrate_window_functions(connection):
    section("ADVANCED: WINDOW FUNCTIONS WITH SCALAR FUNCTIONS")

    print(
        """
Window functions are not the same as ordinary scalar functions or aggregate
functions.

A window function calculates across related rows while retaining individual
rows.

Examples include:

    ROW_NUMBER()
    RANK()
    SUM(...) OVER (...)
    AVG(...) OVER (...)

Scalar functions can then transform the window result.

This is useful for analytics and reporting.
"""
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            department,
            salary,
            ROUND(
                AVG(salary) OVER (
                    PARTITION BY department
                ),
                2
            ) AS department_average_salary
        FROM employees
        ORDER BY department, salary DESC
        """,
        title="Department average while retaining employee rows",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            first_name,
            salary,
            CASE
                WHEN salary IS NULL THEN 'No salary'
                WHEN salary >= AVG(salary) OVER () THEN 'At or above company average'
                ELSE 'Below company average'
            END AS salary_position
        FROM employees
        ORDER BY employee_id
        """,
        title="CASE using a window-function result",
    )


# =============================================================================
# SECTION 32: TESTING SQL FUNCTION LOGIC
# =============================================================================

def test_sql_functions(connection):
    section("TESTING SQL FUNCTION BEHAVIOR")

    tests = [
        (
            "UPPER converts text",
            "SELECT UPPER('hello') AS result",
            "HELLO",
        ),
        (
            "LOWER converts text",
            "SELECT LOWER('HELLO') AS result",
            "hello",
        ),
        (
            "LENGTH counts characters",
            "SELECT LENGTH('SQL') AS result",
            3,
        ),
        (
            "COALESCE returns fallback",
            "SELECT COALESCE(NULL, 'fallback') AS result",
            "fallback",
        ),
        (
            "COALESCE returns first non-NULL value",
            "SELECT COALESCE(NULL, NULL, 25) AS result",
            25,
        ),
        (
            "NULLIF converts equal values to NULL",
            "SELECT NULLIF(10, 10) AS result",
            None,
        ),
        (
            "ROUND rounds numeric values",
            "SELECT ROUND(12.3456, 2) AS result",
            12.35,
        ),
    ]

    passed = 0

    for name, sql, expected in tests:
        actual = connection.execute(sql).fetchone()["result"]

        if actual == expected:
            print(f"PASS: {name}")
            passed += 1
        else:
            print(f"FAIL: {name} | expected={expected!r} actual={actual!r}")

    print(f"\n{passed}/{len(tests)} SQL function tests passed.")


# =============================================================================
# SECTION 33: PERFORMANCE PRINCIPLES
# =============================================================================

def demonstrate_performance_principles():
    section("PERFORMANCE PRINCIPLES")

    print(
        """
SQL functions have computational costs.

Important considerations:

1. Avoid unnecessary function calls over huge datasets.

2. Be cautious with:
       WHERE LOWER(indexed_column) = ...
   because a conventional index may not be usable.

3. Consider expression indexes when supported and justified.

4. Filter early when possible.

5. Select only required columns.

6. Avoid repeatedly calculating the same expensive expression when a CTE,
   subquery, generated column, view, or materialized result is more suitable.

7. Inspect execution plans for important production queries.

8. Do not optimize solely from intuition. Measure query performance.

9. Be careful with date functions in predicates because transforming a
   timestamp column may affect index usage.

10. Do not sacrifice semantic correctness merely to remove a function call.

A fast query that calculates the wrong business metric is not an optimized
solution.
"""
    )


# =============================================================================
# SECTION 34: PRODUCTION DESIGN PRINCIPLES
# =============================================================================

def demonstrate_production_principles():
    section("PRODUCTION DESIGN PRINCIPLES")

    print(
        """
Production-quality SQL function usage should consider:

Correctness
    Does the expression implement the intended business rule?

NULL semantics
    Does missing data have a defined meaning?

Data types
    Are numeric, date, timestamp, and text types appropriate?

Portability
    Does the application need to support multiple database engines?

Performance
    Can the database use indexes and efficient execution strategies?

Maintainability
    Can another developer understand the expression six months later?

Security
    Are external values passed as parameters rather than concatenated into
    SQL?

Testing
    Are NULL, zero, empty strings, boundary dates, negative numbers, and
    unusual text values tested?

Observability
    Can slow queries and incorrect outputs be identified in production?

Business interpretation
    Does replacing NULL with zero actually make sense?

The function syntax is only one part of a production SQL design.
"""
    )


# =============================================================================
# SECTION 35: MINI EXAM
# =============================================================================

def run_practice_questions(connection):
    section("PRACTICE QUESTIONS WITH EXECUTABLE ANSWERS")

    print(
        """
Question 1:
How can you display employee names in uppercase?

Question 2:
How can you replace missing commissions with zero?

Question 3:
How can you identify employees whose salary is missing?

Question 4:
How can you classify salaries into bands?

Question 5:
How can you calculate net sales when discount may be NULL?

Question 6:
How can you prevent division by zero?

Question 7:
How can you normalize email addresses?

Question 8:
How can you group sales by month?
"""
    )

    run_query(
        connection,
        "SELECT UPPER(first_name || ' ' || last_name) AS name FROM employees",
        title="Answer 1",
    )

    run_query(
        connection,
        """
        SELECT first_name, COALESCE(commission, 0) AS commission
        FROM employees
        """,
        title="Answer 2",
    )

    run_query(
        connection,
        """
        SELECT first_name
        FROM employees
        WHERE salary IS NULL
        """,
        title="Answer 3",
    )

    run_query(
        connection,
        """
        SELECT
            first_name,
            CASE
                WHEN salary IS NULL THEN 'Missing'
                WHEN salary >= 100000 THEN 'High'
                WHEN salary >= 80000 THEN 'Medium'
                ELSE 'Low'
            END AS band
        FROM employees
        """,
        title="Answer 4",
    )

    run_query(
        connection,
        """
        SELECT
            sale_id,
            ROUND(
                quantity * unit_price *
                (1 - COALESCE(discount, 0)),
                2
            ) AS net_sales
        FROM sales
        """,
        title="Answer 5",
    )

    run_query(
        connection,
        """
        SELECT
            numerator / NULLIF(denominator, 0) AS safe_division
        FROM ratios
        """,
        title="Answer 6",
    )

    run_query(
        connection,
        """
        SELECT
            employee_id,
            LOWER(TRIM(email)) AS normalized_email
        FROM employees
        WHERE email IS NOT NULL
        """,
        title="Answer 7",
    )

    run_query(
        connection,
        """
        SELECT
            strftime('%Y-%m', sale_date) AS month,
            ROUND(SUM(
                quantity * unit_price *
                (1 - COALESCE(discount, 0))
            ), 2) AS revenue
        FROM sales
        GROUP BY strftime('%Y-%m', sale_date)
        ORDER BY month
        """,
        title="Answer 8",
    )


# =============================================================================
# SECTION 36: MAIN PROGRAM
# =============================================================================

def main():
    connection = create_connection()

    try:
        create_tables(connection)
        insert_sample_data(connection)

        demonstrate_function_fundamentals(connection)
        demonstrate_string_functions(connection)
        demonstrate_numeric_functions(connection)
        demonstrate_date_functions(connection)
        demonstrate_conditional_functions(connection)
        demonstrate_null_fundamentals(connection)
        demonstrate_coalesce(connection)
        demonstrate_nullif(connection)
        demonstrate_ifnull(connection)
        demonstrate_aggregate_interactions(connection)
        demonstrate_functions_in_where(connection)
        demonstrate_functions_in_order_by(connection)
        demonstrate_functions_in_group_by(connection)
        demonstrate_having(connection)
        demonstrate_nested_functions(connection)
        demonstrate_business_metrics(connection)
        demonstrate_combined_logic(connection)
        demonstrate_conditional_null_patterns(connection)
        demonstrate_safe_calculations(connection)
        demonstrate_data_cleaning(connection)
        demonstrate_expression_index(connection)
        demonstrate_parameterized_queries(connection)
        demonstrate_function_design_concepts()
        demonstrate_common_mistakes(connection)
        demonstrate_dialect_comparison()
        demonstrate_advanced_reporting_query(connection)
        demonstrate_cte_with_functions(connection)
        demonstrate_view(connection)
        demonstrate_window_functions(connection)
        test_sql_functions(connection)
        demonstrate_performance_principles()
        demonstrate_production_principles()
        run_practice_questions(connection)

        section("SCRIPT COMPLETED")
        print(
            """
All demonstrations completed successfully.

The database was created entirely in memory, so running this script does not
create or modify an external database file.
"""
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
