"""
SQL Introduction: SQL Purpose, Statements, Commands, and Syntax Fundamentals
=============================================================================

This self-contained Python study script teaches introductory SQL concepts by
using Python's built-in sqlite3 module. SQLite is included with Python, so no
external database server or package is required.

The script demonstrates:

1. What SQL is and why it is used
2. Database, table, row, column, schema, and data types
3. SQL statements and command categories
4. DDL, DML, DQL, DCL, and TCL concepts
5. CREATE, ALTER, DROP, INSERT, UPDATE, DELETE, and SELECT
6. WHERE, ORDER BY, LIMIT, DISTINCT, aliases, and expressions
7. SQL operators and predicates
8. NULL handling
9. Aggregate functions and GROUP BY
10. HAVING
11. JOIN fundamentals
12. Constraints and data integrity
13. Transactions
14. Views and indexes
15. Parameterized queries and SQL injection prevention
16. Error handling and debugging
17. Performance and design considerations
18. Common SQL mistakes and edge cases

SQLite does not implement every SQL feature available in enterprise database
systems. Where relevant, comments explain differences between SQLite and more
feature-rich systems such as PostgreSQL, MySQL, SQL Server, and Oracle.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Sequence


# =============================================================================
# SECTION 1: INTRODUCTION TO SQL
# =============================================================================

def print_title(title: str) -> None:
    """Print a visible section title."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_rows(cursor: sqlite3.Cursor) -> None:
    """
    Print rows returned by a SELECT statement.

    The sqlite3.Row row factory allows column access by name while still
    behaving similarly to a sequence.
    """
    rows = cursor.fetchall()

    if not rows:
        print("(No rows returned)")
        return

    column_names = rows[0].keys()
    print(" | ".join(column_names))
    print("-" * 80)

    for row in rows:
        print(" | ".join(str(row[column]) for column in column_names))


print_title("1. SQL INTRODUCTION")

print(
    """
SQL stands for Structured Query Language.

SQL is used to communicate with relational database management systems.

Typical SQL operations include:
- Creating databases and tables
- Defining data structures
- Inserting records
- Retrieving records
- Updating records
- Deleting records
- Enforcing data integrity
- Managing transactions
- Controlling access in database systems that support permissions

A relational database organizes information into related tables.

Example conceptual table:

Students
+------------+----------+-----+
| student_id | name     | age |
+------------+----------+-----+
| 1          | Ananya   | 21  |
| 2          | Ravi     | 22  |
+------------+----------+-----+

In SQL terminology:
- Database: A collection of related database objects and data.
- Table: A structured collection of rows and columns.
- Row: One record.
- Column: One attribute or field.
- Schema: The structural definition of database objects.
- Primary key: A column or group of columns that uniquely identifies a row.
- Foreign key: A column that references a key in another table.
"""
)


# =============================================================================
# SECTION 2: CONNECTING TO A DATABASE
# =============================================================================

print_title("2. CREATING AN IN-MEMORY SQLITE DATABASE")

# ":memory:" creates a temporary database stored in memory.
# It exists only while this Python program is running.
connection = sqlite3.connect(":memory:")

# Enable named column access.
connection.row_factory = sqlite3.Row

# A cursor executes SQL statements and retrieves results.
cursor = connection.cursor()

# SQLite does not enforce foreign keys unless explicitly enabled.
cursor.execute("PRAGMA foreign_keys = ON")

print("SQLite database connection created successfully.")


# =============================================================================
# SECTION 3: SQL STATEMENT STRUCTURE
# =============================================================================

print_title("3. SQL STATEMENT FUNDAMENTALS")

print(
    """
A SQL statement is an instruction sent to a database.

A simple SELECT statement has the structure:

    SELECT column_name
    FROM table_name
    WHERE condition;

Important syntax concepts:

1. SQL keywords
   Examples: SELECT, FROM, WHERE, INSERT, CREATE.

2. Identifiers
   Names of tables, columns, views, indexes, and other database objects.

3. Literals
   Fixed values such as:
       10
       3.14
       'Ananya'
       NULL

4. Expressions
   Combinations of values, columns, operators, and functions.

5. Clauses
   Logical components of statements such as SELECT, FROM, WHERE, GROUP BY,
   HAVING, and ORDER BY.

SQL keywords are generally case-insensitive, although object naming rules and
string comparisons depend on the database system and configuration.

These are usually equivalent:

    SELECT * FROM students;
    select * from students;

A common professional convention is:
- SQL keywords in uppercase
- Table and column names in lowercase or a consistent naming style

Semicolons commonly terminate SQL statements. Some database APIs accept SQL
without a semicolon when executing a single statement.
"""
)


# =============================================================================
# SECTION 4: SQL COMMAND CLASSIFICATIONS
# =============================================================================

print_title("4. SQL COMMAND CLASSIFICATIONS")

print(
    """
SQL commands are commonly grouped into categories.

DDL: Data Definition Language
--------------------------------
Defines database structures.

Examples:
    CREATE
    ALTER
    DROP

DML: Data Manipulation Language
--------------------------------
Changes data.

Examples:
    INSERT
    UPDATE
    DELETE

DQL: Data Query Language
--------------------------------
Retrieves data.

Primary example:
    SELECT

TCL: Transaction Control Language
--------------------------------
Controls transactions.

Examples:
    BEGIN
    COMMIT
    ROLLBACK
    SAVEPOINT

DCL: Data Control Language
--------------------------------
Controls permissions in database systems that support authorization.

Examples:
    GRANT
    REVOKE

SQLite has a different security architecture from server-based systems, so
GRANT and REVOKE are not demonstrated as executable SQLite permission commands.
"""
)


# =============================================================================
# SECTION 5: DDL - CREATING TABLES
# =============================================================================

print_title("5. DDL: CREATE TABLE")

cursor.execute(
    """
    CREATE TABLE departments (
        department_id INTEGER PRIMARY KEY,
        department_name TEXT NOT NULL UNIQUE
    )
    """
)

cursor.execute(
    """
    CREATE TABLE students (
        student_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        age INTEGER CHECK (age >= 0 AND age <= 150),
        department_id INTEGER,
        admission_year INTEGER DEFAULT 2026,
        scholarship REAL DEFAULT 0 CHECK (scholarship >= 0),

        FOREIGN KEY (department_id)
            REFERENCES departments(department_id)
            ON DELETE SET NULL
    )
    """
)

print(
    """
Two tables were created: departments and students.

Important constraints demonstrated:

PRIMARY KEY
    Uniquely identifies each row.

NOT NULL
    Prevents a column from storing NULL.

UNIQUE
    Prevents duplicate non-NULL values according to the database's uniqueness
    rules.

CHECK
    Enforces a Boolean condition.

DEFAULT
    Supplies a value when INSERT does not provide one.

FOREIGN KEY
    Creates a relationship between tables.
"""
)


# =============================================================================
# SECTION 6: DML - INSERT
# =============================================================================

print_title("6. DML: INSERT")

# Insert department rows.
departments = [
    (1, "Computer Science"),
    (2, "Business"),
    (3, "Mathematics"),
]

cursor.executemany(
    """
    INSERT INTO departments (department_id, department_name)
    VALUES (?, ?)
    """,
    departments,
)

# Insert student rows.
students = [
    (1, "Ananya Sharma", "ananya@example.com", 21, 1, 2025, 25000),
    (2, "Ravi Kumar", "ravi@example.com", 22, 1, 2024, 0),
    (3, "Meera Singh", "meera@example.com", 20, 2, 2026, 15000),
    (4, "Arjun Patel", "arjun@example.com", 23, 3, 2023, 5000),
    (5, "Sara Khan", "sara@example.com", 21, None, 2026, 0),
]

cursor.executemany(
    """
    INSERT INTO students (
        student_id,
        name,
        email,
        age,
        department_id,
        admission_year,
        scholarship
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    students,
)

connection.commit()

print("Sample records inserted.")

print("\nBasic INSERT syntax:")
print(
    """
    INSERT INTO table_name (column1, column2)
    VALUES (value1, value2);

Multiple rows can be inserted individually or through database API batch
operations such as executemany() in Python.
"""
)


# =============================================================================
# SECTION 7: DQL - SELECT
# =============================================================================

print_title("7. DQL: SELECT")

print("\nSELECT all columns:")
result = cursor.execute("SELECT * FROM students")
print_rows(result)

print("\nSELECT specific columns:")
result = cursor.execute(
    """
    SELECT student_id, name, age
    FROM students
    """
)
print_rows(result)

print("\nSELECT with an expression and alias:")
result = cursor.execute(
    """
    SELECT
        name,
        scholarship,
        scholarship * 1.10 AS scholarship_after_increase
    FROM students
    """
)
print_rows(result)

print(
    """
The AS keyword gives an expression or column a result-set alias.

Aliases improve readability and are particularly useful for:
- Calculated expressions
- Aggregate values
- Self-joins
- Tables with long names
"""
)


# =============================================================================
# SECTION 8: WHERE AND OPERATORS
# =============================================================================

print_title("8. FILTERING DATA WITH WHERE")

print("\nStudents older than 21:")
result = cursor.execute(
    """
    SELECT name, age
    FROM students
    WHERE age > 21
    """
)
print_rows(result)

print("\nStudents aged 20 through 22 using BETWEEN:")
result = cursor.execute(
    """
    SELECT name, age
    FROM students
    WHERE age BETWEEN 20 AND 22
    """
)
print_rows(result)

print("\nStudents in selected departments using IN:")
result = cursor.execute(
    """
    SELECT name, department_id
    FROM students
    WHERE department_id IN (1, 2)
    """
)
print_rows(result)

print("\nNames beginning with 'A' using LIKE:")
result = cursor.execute(
    """
    SELECT name
    FROM students
    WHERE name LIKE 'A%'
    """
)
print_rows(result)

print(
    """
Common SQL comparison operators:

=       Equal
<>      Not equal in standard SQL
!=      Not equal in many systems, including SQLite
>       Greater than
<       Less than
>=      Greater than or equal
<=      Less than or equal

Logical operators:

AND     Both conditions must be true.
OR      At least one condition must be true.
NOT     Negates a condition.

Other common predicates:

BETWEEN
IN
LIKE
IS NULL
IS NOT NULL

LIKE wildcard characters commonly include:

%       Zero or more characters
_       Exactly one character

Pattern behavior and case sensitivity vary by database system and configuration.
"""
)


# =============================================================================
# SECTION 9: DISTINCT, ORDER BY, AND LIMIT
# =============================================================================

print_title("9. DISTINCT, ORDER BY, AND LIMIT")

print("\nDistinct admission years:")
result = cursor.execute(
    """
    SELECT DISTINCT admission_year
    FROM students
    ORDER BY admission_year DESC
    """
)
print_rows(result)

print("\nStudents sorted by age, then name:")
result = cursor.execute(
    """
    SELECT name, age
    FROM students
    ORDER BY age ASC, name ASC
    """
)
print_rows(result)

print("\nTop three students by scholarship:")
result = cursor.execute(
    """
    SELECT name, scholarship
    FROM students
    ORDER BY scholarship DESC
    LIMIT 3
    """
)
print_rows(result)

print(
    """
ORDER BY controls result ordering.

ASC
    Ascending order. Usually the default.

DESC
    Descending order.

Without ORDER BY, SQL result order should generally not be treated as guaranteed.
Database engines may change the physical retrieval order because of indexes,
execution plans, storage changes, or other internal decisions.

LIMIT is common in SQLite, PostgreSQL, and MySQL.
Other systems may use alternatives such as TOP or FETCH FIRST.
"""
)


# =============================================================================
# SECTION 10: NULL
# =============================================================================

print_title("10. NULL AND THREE-VALUED LOGIC")

print("\nStudents without an assigned department:")
result = cursor.execute(
    """
    SELECT name, department_id
    FROM students
    WHERE department_id IS NULL
    """
)
print_rows(result)

print(
    """
NULL does not mean:
- Zero
- An empty string
- False

NULL generally means that a value is unknown, missing, unavailable, or not
applicable.

Incorrect:
    WHERE department_id = NULL

Correct:
    WHERE department_id IS NULL

SQL uses three-valued logic:
- TRUE
- FALSE
- UNKNOWN

A comparison involving NULL often produces UNKNOWN.

For example:
    NULL = NULL

does not evaluate to ordinary TRUE in standard SQL logic.

This is one reason IS NULL exists.
"""
)

print("\nDemonstrating NULL with COALESCE:")
result = cursor.execute(
    """
    SELECT
        name,
        department_id,
        COALESCE(department_id, -1) AS department_or_default
    FROM students
    """
)
print_rows(result)


# =============================================================================
# SECTION 11: AGGREGATE FUNCTIONS
# =============================================================================

print_title("11. AGGREGATE FUNCTIONS")

result = cursor.execute(
    """
    SELECT
        COUNT(*) AS total_rows,
        COUNT(department_id) AS non_null_departments,
        AVG(age) AS average_age,
        MIN(age) AS youngest_age,
        MAX(age) AS oldest_age,
        SUM(scholarship) AS total_scholarship
    FROM students
    """
)

print_rows(result)

print(
    """
Important distinction:

COUNT(*)
    Counts rows.

COUNT(column_name)
    Counts non-NULL values in that column.

Aggregate functions combine multiple rows into one result.

Common aggregate functions:
- COUNT
- SUM
- AVG
- MIN
- MAX

NULL handling differs by function and database system. Aggregates such as SUM
and AVG generally ignore NULL values, while COUNT(*) counts rows regardless of
NULL values.
"""
)


# =============================================================================
# SECTION 12: GROUP BY AND HAVING
# =============================================================================

print_title("12. GROUP BY AND HAVING")

print("\nStudent count by department_id:")
result = cursor.execute(
    """
    SELECT
        department_id,
        COUNT(*) AS student_count,
        AVG(age) AS average_age
    FROM students
    GROUP BY department_id
    ORDER BY student_count DESC
    """
)
print_rows(result)

print("\nGroups having at least two students:")
result = cursor.execute(
    """
    SELECT
        department_id,
        COUNT(*) AS student_count
    FROM students
    GROUP BY department_id
    HAVING COUNT(*) >= 2
    """
)
print_rows(result)

print(
    """
WHERE and HAVING have different purposes.

WHERE
    Filters individual rows before grouping.

HAVING
    Filters groups after GROUP BY.

Conceptual processing order is approximately:

FROM
WHERE
GROUP BY
HAVING
SELECT
ORDER BY
LIMIT

The exact physical execution strategy is chosen by the database optimizer.
"""
)


# =============================================================================
# SECTION 13: UPDATE
# =============================================================================

print_title("13. DML: UPDATE")

print("\nUpdating Ravi's scholarship.")

cursor.execute(
    """
    UPDATE students
    SET scholarship = 10000
    WHERE student_id = 2
    """
)

connection.commit()

result = cursor.execute(
    """
    SELECT name, scholarship
    FROM students
    WHERE student_id = 2
    """
)
print_rows(result)

print(
    """
Basic syntax:

    UPDATE table_name
    SET column_name = value
    WHERE condition;

A critical mistake is omitting WHERE when only selected rows should change:

    UPDATE students
    SET scholarship = 0;

That statement updates every row in the table.

Before running production UPDATE statements:
- Verify the WHERE condition with SELECT.
- Use transactions where supported.
- Check affected row counts.
- Test against non-production data.
"""
)


# =============================================================================
# SECTION 14: DELETE
# =============================================================================

print_title("14. DML: DELETE")

# Create a temporary row so DELETE can be demonstrated safely.
cursor.execute(
    """
    INSERT INTO students (
        student_id, name, email, age, department_id, admission_year, scholarship
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    (99, "Temporary Student", "temporary@example.com", 19, 3, 2026, 0),
)

connection.commit()

print("\nTemporary row before DELETE:")
result = cursor.execute(
    """
    SELECT student_id, name
    FROM students
    WHERE student_id = 99
    """
)
print_rows(result)

cursor.execute(
    """
    DELETE FROM students
    WHERE student_id = 99
    """
)

connection.commit()

print("\nTemporary row after DELETE:")
result = cursor.execute(
    """
    SELECT student_id, name
    FROM students
    WHERE student_id = 99
    """
)
print_rows(result)

print(
    """
Basic syntax:

    DELETE FROM table_name
    WHERE condition;

DELETE without WHERE can remove all rows:

    DELETE FROM students;

This removes table data but does not necessarily remove the table structure.

DROP TABLE removes the database object itself.
"""
)


# =============================================================================
# SECTION 15: JOIN FUNDAMENTALS
# =============================================================================

print_title("15. JOIN FUNDAMENTALS")

print("\nINNER JOIN:")
result = cursor.execute(
    """
    SELECT
        students.name,
        departments.department_name
    FROM students
    INNER JOIN departments
        ON students.department_id = departments.department_id
    ORDER BY students.name
    """
)
print_rows(result)

print("\nLEFT JOIN:")
result = cursor.execute(
    """
    SELECT
        students.name,
        departments.department_name
    FROM students
    LEFT JOIN departments
        ON students.department_id = departments.department_id
    ORDER BY students.name
    """
)
print_rows(result)

print(
    """
INNER JOIN
    Returns matching rows from both sides.

LEFT JOIN
    Returns all rows from the left table and matching rows from the right table.
    If no match exists, right-side columns contain NULL.

Important JOIN concepts:

ON
    Specifies the relationship condition.

Table aliases
    Short names that improve readability.

Example:

    SELECT s.name, d.department_name
    FROM students AS s
    JOIN departments AS d
        ON s.department_id = d.department_id;

Common JOIN mistakes:
- Missing the ON condition.
- Joining unrelated columns.
- Using non-unique relationships unintentionally and creating duplicate rows.
- Filtering a LEFT JOIN incorrectly in WHERE and accidentally changing it into
  behavior similar to an INNER JOIN.
"""
)


# =============================================================================
# SECTION 16: ALTER TABLE
# =============================================================================

print_title("16. DDL: ALTER TABLE")

cursor.execute(
    """
    ALTER TABLE students
    ADD COLUMN active INTEGER NOT NULL DEFAULT 1
    """
)

connection.commit()

print("Column 'active' added successfully.")

result = cursor.execute(
    """
    SELECT student_id, name, active
    FROM students
    LIMIT 3
    """
)
print_rows(result)

print(
    """
ALTER TABLE changes an existing table structure.

Capabilities vary significantly between database systems.

Possible operations may include:
- Adding columns
- Dropping columns
- Renaming columns
- Changing data types
- Adding or removing constraints

SQLite supports a subset of ALTER TABLE operations compared with some
enterprise database systems.
"""
)


# =============================================================================
# SECTION 17: TRANSACTIONS
# =============================================================================

print_title("17. TRANSACTIONS: BEGIN, COMMIT, AND ROLLBACK")

print(
    """
A transaction groups database operations into a logical unit.

Core transaction concepts:

BEGIN
    Starts a transaction.

COMMIT
    Permanently saves successful changes.

ROLLBACK
    Reverses uncommitted changes.

A common principle is atomicity:
Either all required operations succeed, or the transaction is rolled back.
"""
)

# Explicit transaction demonstration.
connection.execute("BEGIN")

try:
    connection.execute(
        """
        INSERT INTO students (
            student_id, name, email, age, department_id, admission_year,
            scholarship, active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (100, "Transaction Example", "transaction@example.com", 25, 2, 2026, 0, 1),
    )

    # Artificially trigger an error by inserting a duplicate email.
    connection.execute(
        """
        INSERT INTO students (
            student_id, name, email, age, department_id, admission_year,
            scholarship, active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (101, "Duplicate Email", "transaction@example.com", 26, 2, 2026, 0, 1),
    )

    connection.commit()

except sqlite3.IntegrityError as error:
    print(f"Transaction failed: {error}")
    connection.rollback()
    print("Transaction rolled back.")

result = cursor.execute(
    """
    SELECT name
    FROM students
    WHERE student_id IN (100, 101)
    """
)
print_rows(result)


# =============================================================================
# SECTION 18: SAVEPOINTS
# =============================================================================

print_title("18. SAVEPOINTS")

connection.execute("BEGIN")

try:
    connection.execute(
        """
        INSERT INTO students (
            student_id, name, email, age, department_id, admission_year,
            scholarship, active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (102, "Before Savepoint", "before.savepoint@example.com", 24, 1, 2026, 0, 1),
    )

    connection.execute("SAVEPOINT student_change")

    connection.execute(
        """
        INSERT INTO students (
            student_id, name, email, age, department_id, admission_year,
            scholarship, active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (103, "After Savepoint", "after.savepoint@example.com", 24, 1, 2026, 0, 1),
    )

    # Roll back only to the savepoint.
    connection.execute("ROLLBACK TO SAVEPOINT student_change")
    connection.execute("RELEASE SAVEPOINT student_change")

    connection.commit()

except sqlite3.DatabaseError:
    connection.rollback()
    raise

result = cursor.execute(
    """
    SELECT student_id, name
    FROM students
    WHERE student_id IN (102, 103)
    ORDER BY student_id
    """
)
print_rows(result)

print(
    """
SAVEPOINT allows partial rollback within a transaction.

ROLLBACK TO SAVEPOINT
    Reverses work performed after the savepoint.

RELEASE SAVEPOINT
    Removes the savepoint marker.

The exact transaction behavior and concurrency model depend on the database
management system.
"""
)


# =============================================================================
# SECTION 19: CONSTRAINT VIOLATIONS
# =============================================================================

print_title("19. DATA INTEGRITY AND CONSTRAINT VIOLATIONS")

print("\nAttempting to insert a duplicate email:")

try:
    cursor.execute(
        """
        INSERT INTO students (
            student_id, name, email, age, department_id,
            admission_year, scholarship, active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (200, "Duplicate Example", "ananya@example.com", 22, 1, 2026, 0, 1),
    )
    connection.commit()

except sqlite3.IntegrityError as error:
    connection.rollback()
    print(f"Integrity error caught: {error}")

print(
    """
Constraints protect data integrity at the database level.

Application validation is useful, but database constraints remain important
because data may enter through:
- Multiple applications
- Administrative tools
- Scripts
- APIs
- Data imports
- Scheduled jobs

Database constraints provide a final structural layer of validation.
"""
)


# =============================================================================
# SECTION 20: DROP
# =============================================================================

print_title("20. DDL: DROP")

cursor.execute(
    """
    CREATE TABLE temporary_notes (
        note_id INTEGER PRIMARY KEY,
        note TEXT
    )
    """
)

cursor.execute(
    """
    INSERT INTO temporary_notes (note_id, note)
    VALUES (1, 'This table will be removed')
    """
)

cursor.execute("DROP TABLE temporary_notes")

print(
    """
DROP removes a database object.

Example:

    DROP TABLE temporary_notes;

After DROP TABLE, both the table structure and its data are removed.

DROP is different from DELETE:

DELETE
    Removes rows while leaving the table structure.

DROP TABLE
    Removes the table object itself.

DROP operations can be destructive and should be handled carefully.
"""
)


# =============================================================================
# SECTION 21: VIEWS
# =============================================================================

print_title("21. VIEWS")

cursor.execute(
    """
    CREATE VIEW student_directory AS
    SELECT
        s.student_id,
        s.name,
        s.email,
        d.department_name
    FROM students AS s
    LEFT JOIN departments AS d
        ON s.department_id = d.department_id
    """
)

result = cursor.execute(
    """
    SELECT *
    FROM student_directory
    ORDER BY student_id
    """
)
print_rows(result)

print(
    """
A view is a named SQL query that can be queried similarly to a table.

Benefits:
- Simplifies repeated queries
- Encapsulates query logic
- Can expose selected columns instead of entire tables
- Can support security boundaries in systems with advanced authorization

Views are often virtual rather than independently storing data, although some
database systems also support materialized views.
"""
)


# =============================================================================
# SECTION 22: INDEXES
# =============================================================================

print_title("22. INDEXES")

cursor.execute(
    """
    CREATE INDEX idx_students_department_id
    ON students(department_id)
    """
)

print(
    """
An index is a data structure that can improve the speed of certain operations.

Example:

    CREATE INDEX idx_students_department_id
    ON students(department_id);

Indexes can improve:
- Searches
- JOIN operations
- Sorting
- Filtering

Trade-offs:
- Additional storage
- Slower INSERT operations
- Slower UPDATE operations for indexed columns
- Slower DELETE operations in some workloads
- Maintenance overhead

Indexes should support actual query patterns rather than being created
indiscriminately.

Database query planners decide whether an index is beneficial for a particular
query.
"""
)


# =============================================================================
# SECTION 23: PARAMETERIZED QUERIES AND SQL INJECTION
# =============================================================================

print_title("23. PARAMETERIZED QUERIES AND SQL INJECTION PREVENTION")

user_supplied_name = "Ananya Sharma"

# Correct approach: parameterized SQL.
result = cursor.execute(
    """
    SELECT student_id, name, email
    FROM students
    WHERE name = ?
    """,
    (user_supplied_name,),
)

print_rows(result)

print(
    """
Parameterized queries separate SQL code from data.

Safe conceptual pattern:

    cursor.execute(
        "SELECT * FROM students WHERE name = ?",
        (user_input,)
    )

Unsafe pattern:

    sql = "SELECT * FROM students WHERE name = '" + user_input + "'"

String concatenation can allow malicious input to change SQL syntax in systems
where multiple statements or vulnerable parsing behavior are possible.

Important distinction:

Parameterized queries protect data values.

They generally cannot be used directly for arbitrary SQL identifiers such as
table names or column names. Dynamic identifiers require careful validation
against a controlled allowlist.
"""
)


def fetch_students_by_allowed_sort_column(sort_column: str) -> list[sqlite3.Row]:
    """
    Demonstrate safe dynamic SQL identifier handling.

    SQL parameter placeholders represent data values, not table or column names.
    Therefore, dynamic identifiers are selected from an allowlist.
    """
    allowed_columns = {"name", "age", "scholarship"}

    if sort_column not in allowed_columns:
        raise ValueError(
            f"Invalid sort column: {sort_column!r}. "
            f"Allowed columns: {sorted(allowed_columns)}"
        )

    sql = f"""
        SELECT student_id, name, age, scholarship
        FROM students
        ORDER BY {sort_column}
    """

    return connection.execute(sql).fetchall()


print("\nSafe dynamic ORDER BY using an allowlist:")

for row in fetch_students_by_allowed_sort_column("age"):
    print(dict(row))

try:
    fetch_students_by_allowed_sort_column("name; DROP TABLE students")
except ValueError as error:
    print(f"\nRejected unsafe identifier: {error}")


# =============================================================================
# SECTION 24: SQL FUNCTIONS AND EXPRESSIONS
# =============================================================================

print_title("24. SQL FUNCTIONS AND EXPRESSIONS")

result = cursor.execute(
    """
    SELECT
        name,
        UPPER(name) AS uppercase_name,
        LENGTH(name) AS name_length,
        age + 1 AS age_next_year,
        scholarship / 1000.0 AS scholarship_in_thousands
    FROM students
    ORDER BY student_id
    LIMIT 5
    """
)

print_rows(result)

print(
    """
SQL expressions can combine:
- Column values
- Literal values
- Operators
- Functions

Examples:

    age + 1
    salary * 1.10
    UPPER(name)
    COUNT(*)

Available built-in functions vary by database system.
"""
)


# =============================================================================
# SECTION 25: CASE EXPRESSIONS
# =============================================================================

print_title("25. CONDITIONAL LOGIC WITH CASE")

result = cursor.execute(
    """
    SELECT
        name,
        scholarship,
        CASE
            WHEN scholarship >= 20000 THEN 'High'
            WHEN scholarship >= 5000 THEN 'Medium'
            ELSE 'Low'
        END AS scholarship_category
    FROM students
    ORDER BY scholarship DESC
    """
)

print_rows(result)

print(
    """
CASE provides conditional logic in SQL.

General structure:

    CASE
        WHEN condition THEN result
        WHEN another_condition THEN another_result
        ELSE default_result
    END
"""
)


# =============================================================================
# SECTION 26: SUBQUERIES
# =============================================================================

print_title("26. SUBQUERIES")

print("\nStudents older than the average age:")

result = cursor.execute(
    """
    SELECT
        name,
        age
    FROM students
    WHERE age > (
        SELECT AVG(age)
        FROM students
    )
    ORDER BY age DESC
    """
)

print_rows(result)

print(
    """
A subquery is a query nested inside another SQL statement.

Subqueries may appear in:
- WHERE
- FROM
- SELECT
- HAVING
- INSERT
- UPDATE
- DELETE

Performance characteristics depend on the database optimizer. A database may
transform some subqueries into equivalent internal execution strategies.
"""
)


# =============================================================================
# SECTION 27: CTE FUNDAMENTALS
# =============================================================================

print_title("27. COMMON TABLE EXPRESSIONS (CTEs)")

result = cursor.execute(
    """
    WITH department_statistics AS (
        SELECT
            department_id,
            COUNT(*) AS student_count,
            AVG(age) AS average_age
        FROM students
        WHERE department_id IS NOT NULL
        GROUP BY department_id
    )
    SELECT
        d.department_name,
        ds.student_count,
        ds.average_age
    FROM department_statistics AS ds
    JOIN departments AS d
        ON ds.department_id = d.department_id
    ORDER BY ds.student_count DESC
    """
)

print_rows(result)

print(
    """
A Common Table Expression is a named temporary result used within a single SQL
statement.

Basic structure:

    WITH name AS (
        SELECT ...
    )
    SELECT ...
    FROM name;

CTEs can improve readability when a query contains multiple logical stages.
They can also support recursive queries in database systems that implement
recursive CTE functionality.
"""
)


# =============================================================================
# SECTION 28: DATABASE DESIGN FUNDAMENTALS
# =============================================================================

print_title("28. RELATIONAL DATABASE DESIGN FUNDAMENTALS")

print(
    """
Good SQL usage depends on good database design.

Key design principles:

1. Use meaningful table names.

2. Use stable primary keys.

3. Choose appropriate data types.

4. Define relationships using foreign keys.

5. Use constraints for critical business rules.

6. Avoid unnecessary duplicate data.

7. Normalize data when appropriate.

Normalization commonly separates repeated concepts into related tables.

For example, instead of storing:

    student_name
    department_name
    department_head
    department_location

repeated for every student, store department information once in a departments
table and reference it using department_id.

Benefits:
- Reduced duplication
- Improved consistency
- Easier updates

Trade-off:
Highly normalized designs may require more JOIN operations.

Some high-performance analytical systems intentionally denormalize data to
reduce query complexity or improve specific workload characteristics.
"""
)


# =============================================================================
# SECTION 29: COMMON SQL MISTAKES
# =============================================================================

print_title("29. COMMON SQL MISTAKES")

common_mistakes = [
    (
        "Forgetting WHERE in UPDATE",
        "Can modify every row in the table.",
    ),
    (
        "Forgetting WHERE in DELETE",
        "Can delete every row.",
    ),
    (
        "Using = NULL",
        "Use IS NULL instead.",
    ),
    (
        "Assuming SELECT order",
        "Use ORDER BY when order matters.",
    ),
    (
        "Using SELECT * everywhere",
        "Can retrieve unnecessary data and make applications fragile.",
    ),
    (
        "Concatenating user input into SQL",
        "Can create SQL injection vulnerabilities.",
    ),
    (
        "Ignoring transactions",
        "Multi-step operations can leave partially changed data after failures.",
    ),
    (
        "Creating too many indexes",
        "Indexes consume storage and increase write overhead.",
    ),
    (
        "Ignoring constraints",
        "Application-only validation cannot guarantee database integrity.",
    ),
    (
        "Using incorrect JOIN conditions",
        "Can create missing rows or unintended duplicates.",
    ),
]

for number, (mistake, consequence) in enumerate(common_mistakes, start=1):
    print(f"{number}. {mistake}: {consequence}")


# =============================================================================
# SECTION 30: ERROR HANDLING
# =============================================================================

print_title("30. SQL ERROR HANDLING")

def execute_query_safely(
    database_connection: sqlite3.Connection,
    sql: str,
    parameters: Sequence[Any] = (),
) -> list[sqlite3.Row]:
    """
    Execute a query with basic error handling.

    This helper is intentionally simple for educational purposes.
    Production systems should use structured logging, appropriate exception
    boundaries, transaction policies, and database-specific error handling.
    """
    try:
        query_cursor = database_connection.execute(sql, parameters)
        return query_cursor.fetchall()

    except sqlite3.DatabaseError as error:
        print(f"Database error: {error}")
        raise


print("\nExecuting a valid query:")
rows = execute_query_safely(
    connection,
    "SELECT name FROM students WHERE age >= ? ORDER BY name",
    (21,),
)

for row in rows:
    print(row["name"])

print("\nExecuting an invalid query:")

try:
    execute_query_safely(
        connection,
        "SELECT imaginary_column FROM students",
    )
except sqlite3.DatabaseError:
    print("Invalid SQL error handled successfully.")


# =============================================================================
# SECTION 31: DEBUGGING SQL
# =============================================================================

print_title("31. DEBUGGING SQL")

print(
    """
Useful SQL debugging techniques:

1. Start with a simple SELECT.
2. Add one clause at a time.
3. Check table and column names.
4. Verify data types.
5. Inspect NULL values explicitly.
6. Run JOIN components independently.
7. Check row counts before and after grouping.
8. Verify WHERE conditions before UPDATE or DELETE.
9. Examine database error messages.
10. Use query execution plans when investigating performance.

Example debugging progression:

Step 1:
    SELECT * FROM students;

Step 2:
    SELECT * FROM students
    WHERE age > 20;

Step 3:
    SELECT s.name, d.department_name
    FROM students AS s
    LEFT JOIN departments AS d
        ON s.department_id = d.department_id
    WHERE s.age > 20;

Building a query incrementally often makes logical errors easier to identify.
"""
)


# =============================================================================
# SECTION 32: QUERY PLANS AND PERFORMANCE
# =============================================================================

print_title("32. QUERY PERFORMANCE FUNDAMENTALS")

query_plan = cursor.execute(
    """
    EXPLAIN QUERY PLAN
    SELECT *
    FROM students
    WHERE department_id = 1
    """
)

print_rows(query_plan)

print(
    """
Database systems use query optimizers to select execution strategies.

Performance can be influenced by:
- Table size
- Indexes
- Data distribution
- JOIN order
- Filter selectivity
- Sorting
- Aggregation
- Network latency
- Hardware
- Database configuration
- Concurrent workload

General performance practices:

- Retrieve only needed columns.
- Filter early when appropriate.
- Index frequently searched columns where justified.
- Use appropriate JOIN conditions.
- Avoid unnecessary repeated queries.
- Measure performance instead of assuming.
- Examine execution plans for expensive queries.

Optimization is database-specific. A query that performs well in SQLite may
require different tuning in PostgreSQL, MySQL, SQL Server, Oracle, or a cloud
data warehouse.
"""
)


# =============================================================================
# SECTION 33: SQL DIALECTS
# =============================================================================

print_title("33. SQL DIALECTS AND PORTABILITY")

print(
    """
SQL is standardized, but database products implement different SQL dialects.

Examples of database systems:
- SQLite
- PostgreSQL
- MySQL
- MariaDB
- Microsoft SQL Server
- Oracle Database

Differences can include:
- Data types
- String functions
- Date and time functions
- Auto-increment behavior
- LIMIT versus TOP syntax
- JSON functionality
- Full-text search
- Stored procedures
- User-defined functions
- Permission models
- Transaction and locking behavior

For portable SQL:
- Prefer widely supported standard syntax where practical.
- Avoid unnecessary vendor-specific features.
- Document database-specific dependencies.
- Test queries against the actual target database.
"""
)


# =============================================================================
# SECTION 34: ACID TRANSACTION CONCEPTS
# =============================================================================

print_title("34. ACID TRANSACTION CONCEPTS")

print(
    """
Transactions are commonly described using ACID properties.

Atomicity
    A transaction's operations are treated as a single logical unit.

Consistency
    Valid transactions move the database between valid states according to
    constraints and rules.

Isolation
    Concurrent transactions should not improperly interfere with one another.
    Exact isolation guarantees depend on the database isolation level.

Durability
    Committed data should survive expected failures according to the database
    system's durability guarantees.

Different database systems implement concurrency, locking, journaling, and
isolation differently.
"""
)


# =============================================================================
# SECTION 35: PRACTICAL REPORT QUERY
# =============================================================================

print_title("35. PRACTICAL INTEGRATED SQL REPORT")

result = cursor.execute(
    """
    SELECT
        d.department_name AS department,
        COUNT(s.student_id) AS student_count,
        ROUND(AVG(s.age), 2) AS average_age,
        ROUND(SUM(s.scholarship), 2) AS total_scholarship
    FROM departments AS d
    LEFT JOIN students AS s
        ON d.department_id = s.department_id
    GROUP BY d.department_id, d.department_name
    HAVING COUNT(s.student_id) >= 1
    ORDER BY total_scholarship DESC
    """
)

print_rows(result)

print(
    """
This report combines multiple introductory SQL concepts:

- SELECT chooses output columns.
- FROM identifies the starting table.
- LEFT JOIN combines related tables.
- ON defines the relationship.
- COUNT, AVG, and SUM aggregate rows.
- GROUP BY creates department-level groups.
- HAVING filters groups.
- ORDER BY sorts the final result.
- Aliases improve readability.
"""
)


# =============================================================================
# SECTION 36: PRACTICAL SEARCH FUNCTION
# =============================================================================

print_title("36. PRACTICAL PARAMETERIZED SEARCH FUNCTION")

def search_students(
    minimum_age: int | None = None,
    department_id: int | None = None,
    name_pattern: str | None = None,
) -> list[sqlite3.Row]:
    """
    Search students using optional filters.

    The SQL statement is built dynamically, while actual data values remain
    parameterized to avoid SQL injection through values.
    """
    sql = """
        SELECT
            student_id,
            name,
            email,
            age,
            department_id,
            scholarship
        FROM students
        WHERE 1 = 1
    """

    parameters: list[Any] = []

    if minimum_age is not None:
        sql += " AND age >= ?"
        parameters.append(minimum_age)

    if department_id is not None:
        sql += " AND department_id = ?"
        parameters.append(department_id)

    if name_pattern is not None:
        sql += " AND name LIKE ?"
        parameters.append(f"%{name_pattern}%")

    sql += " ORDER BY name"

    return connection.execute(sql, parameters).fetchall()


print("\nSearch: minimum_age=21, department_id=1")

search_results = search_students(
    minimum_age=21,
    department_id=1,
)

for row in search_results:
    print(dict(row))


# =============================================================================
# SECTION 37: CLEANUP
# =============================================================================

print_title("37. CLEANUP")

connection.close()

print(
    """
The SQLite connection has been closed.

Core SQL ideas demonstrated in this script include:

- Database structure
- DDL, DML, DQL, TCL, and DCL concepts
- CREATE, ALTER, DROP
- INSERT, UPDATE, DELETE
- SELECT and result sets
- WHERE and logical operators
- NULL
- DISTINCT, ORDER BY, LIMIT
- Aggregate functions
- GROUP BY and HAVING
- JOINs
- Constraints
- Transactions and savepoints
- Views
- Indexes
- Parameterized queries
- SQL injection prevention
- CASE expressions
- Subqueries
- CTEs
- Database design
- Debugging
- Performance fundamentals
- SQL dialect differences
- Practical integrated queries
"""
)
