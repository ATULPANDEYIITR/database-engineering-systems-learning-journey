"""
KEYS AND CONSTRAINTS IN RELATIONAL DATABASES
============================================

A comprehensive, executable study script covering:

1. Relational-table fundamentals
2. Candidate keys
3. Primary keys
4. Foreign keys
5. Unique keys
6. NOT NULL, CHECK, DEFAULT constraints
7. Composite keys
8. Natural and surrogate keys
9. Referential integrity
10. Entity integrity
11. Domain integrity
12. Constraint enforcement in SQLite
13. INSERT, UPDATE, DELETE behavior
14. Foreign-key actions: CASCADE, SET NULL, RESTRICT, NO ACTION
15. NULL and UNIQUE behavior
16. Constraint naming and introspection
17. Constraint interactions
18. Schema design trade-offs
19. Edge cases and common mistakes
20. Transactions and atomicity
21. Performance considerations
22. Security considerations
23. Testing constraints
24. Advanced schema examples
25. Practical design patterns

The script uses only Python's standard library, primarily sqlite3.
It creates in-memory databases, so no external database server or files
are required.

Run with:

    python keys_and_constraints.py
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from typing import Callable, Iterable, Optional


# =============================================================================
# 1. HELPER FUNCTIONS
# =============================================================================

def print_title(title: str) -> None:
    """Print a visually distinct section title."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_subtitle(title: str) -> None:
    """Print a subsection title."""
    print("\n" + "-" * 70)
    print(title)
    print("-" * 70)


def show_rows(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple = (),
) -> None:
    """Execute a SELECT statement and print rows with column names."""
    cursor = connection.execute(sql, parameters)
    rows = cursor.fetchall()

    if not rows:
        print("(no rows)")
        return

    column_names = [description[0] for description in cursor.description]
    print(" | ".join(column_names))
    print("-" * (len(" | ".join(column_names)) + 2))

    for row in rows:
        print(" | ".join(str(value) for value in row))


def try_sql(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple = (),
    description: str = "",
) -> bool:
    """
    Execute SQL and report whether it succeeded.

    Integrity constraint violations are expected during several teaching
    examples. They are caught so that one failure does not terminate the
    complete study script.
    """
    if description:
        print(f"\n{description}")

    try:
        connection.execute(sql, parameters)
        connection.commit()
        print("SUCCESS")
        return True
    except sqlite3.IntegrityError as error:
        connection.rollback()
        print(f"INTEGRITY ERROR: {error}")
        return False
    except sqlite3.Error as error:
        connection.rollback()
        print(f"SQL ERROR: {error}")
        return False


def explain_constraint_failure(
    operation: Callable[[], object],
    expected_concept: str,
) -> None:
    """
    Execute an operation that is expected to fail and explain the reason.

    This helper makes constraint behavior explicit rather than silently
    swallowing errors.
    """
    try:
        operation()
        print("UNEXPECTED RESULT: operation succeeded.")
    except sqlite3.IntegrityError as error:
        print(f"Expected {expected_concept} violation:")
        print(f"  {error}")


def create_connection() -> sqlite3.Connection:
    """
    Create an in-memory SQLite database with foreign-key enforcement enabled.

    SQLite does not enforce foreign keys unless PRAGMA foreign_keys is enabled
    for the connection.
    """
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# =============================================================================
# 2. RELATIONAL DATABASE FUNDAMENTALS
# =============================================================================

def fundamentals() -> None:
    print_title("1. RELATIONAL DATABASE FUNDAMENTALS")

    print(
        """
A relational database represents information using relations, commonly
visualized as tables.

A table contains:
    - Rows: individual records or tuples.
    - Columns: attributes or fields.
    - A schema: the definition of the table and its rules.

Example:

    Student(student_id, email, full_name)

A key is a set of one or more attributes whose values can identify rows
according to a particular key definition.

A constraint is a rule imposed by the database to restrict invalid data.

Keys and constraints solve different but related problems:

    Keys:
        Identify rows and relationships between tables.

    Constraints:
        Enforce rules that keep stored data valid and consistent.

The database should enforce important integrity rules itself rather than
depending entirely on application code.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE students (
                student_id INTEGER,
                email TEXT,
                full_name TEXT
            )
            """
        )

        connection.executemany(
            "INSERT INTO students VALUES (?, ?, ?)",
            [
                (1, "a@example.com", "Asha"),
                (2, "b@example.com", "Bharat"),
                (3, "c@example.com", "Chitra"),
            ],
        )

        print_subtitle("A simple relation")
        show_rows(connection, "SELECT * FROM students")

        print(
            """
Notice that this table currently has no declared key or integrity
constraints. The database can therefore accept duplicate student_id values,
NULL values, and duplicate email addresses.

That is structurally possible but usually undesirable for identifiers.
"""
        )


# =============================================================================
# 3. CANDIDATE KEYS
# =============================================================================

def candidate_keys() -> None:
    print_title("2. CANDIDATE KEYS")

    print(
        """
A candidate key is a minimal set of attributes that can uniquely identify
each row in a relation.

Two properties are central:

    1. Uniqueness:
       No two rows may have the same candidate-key value.

    2. Minimality:
       Removing any attribute from the candidate key destroys the ability
       to uniquely identify rows.

Suppose:

    Employee(employee_id, email, national_id, name)

If employee_id, email, and national_id are each individually unique and
non-null, each may be a candidate key.

One candidate key is selected as the primary key.

The remaining candidate keys are called alternate keys.

Candidate key is a relational-model concept. UNIQUE constraints are a common
SQL mechanism for enforcing uniqueness for candidate or alternate keys.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                government_id TEXT NOT NULL UNIQUE,
                employee_name TEXT NOT NULL
            )
            """
        )

        connection.executemany(
            """
            INSERT INTO employees
                (employee_id, email, government_id, employee_name)
            VALUES (?, ?, ?, ?)
            """,
            [
                (101, "asha@example.com", "GOV-001", "Asha"),
                (102, "bharat@example.com", "GOV-002", "Bharat"),
            ],
        )

        print_subtitle("Possible candidate keys")
        show_rows(connection, "SELECT * FROM employees")

        print(
            """
In this design:

    employee_id
        Primary key and candidate key.

    email
        Candidate key enforced through UNIQUE.

    government_id
        Candidate key enforced through UNIQUE.

The database does not normally label all of these as "candidate keys".
Candidate-key reasoning is part of schema design; SQL constraints implement
the required properties.
"""
        )

        explain_constraint_failure(
            lambda: connection.execute(
                """
                INSERT INTO employees
                    (employee_id, email, government_id, employee_name)
                VALUES (103, 'asha@example.com', 'GOV-003', 'Another Asha')
                """
            ),
            "UNIQUE",
        )


# =============================================================================
# 4. PRIMARY KEYS
# =============================================================================

def primary_keys() -> None:
    print_title("3. PRIMARY KEYS")

    print(
        """
A primary key is the key chosen to uniquely identify rows in a table.

Important properties:

    - It identifies each row.
    - It must be unique.
    - It cannot contain NULL.
    - There is one primary-key definition per table.
    - It may contain one column or multiple columns.
    - It can be referenced by foreign keys.

The phrase "one primary key" does not mean "one column".
A composite primary key can contain multiple columns.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE departments (
                department_id INTEGER PRIMARY KEY,
                department_name TEXT NOT NULL
            )
            """
        )

        connection.executemany(
            "INSERT INTO departments VALUES (?, ?)",
            [
                (10, "Engineering"),
                (20, "Finance"),
                (30, "Human Resources"),
            ],
        )

        print_subtitle("Primary key in action")
        show_rows(connection, "SELECT * FROM departments")

        print_subtitle("Duplicate primary key")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO departments VALUES (?, ?)",
                (10, "Another Engineering"),
            ),
            "PRIMARY KEY",
        )

        print_subtitle("NULL primary key")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO departments VALUES (?, ?)",
                (None, "Unassigned"),
            ),
            "primary-key",
        )


# =============================================================================
# 5. INTEGER PRIMARY KEY AND GENERATED IDENTIFIERS IN SQLITE
# =============================================================================

def sqlite_integer_primary_key() -> None:
    print_title("4. SQLITE INTEGER PRIMARY KEY BEHAVIOR")

    print(
        """
SQLite has a special behavior for:

    INTEGER PRIMARY KEY

It aliases the table's internal rowid.

When an INSERT omits this column or supplies NULL, SQLite can automatically
assign an unused integer identifier.

This is useful for surrogate identifiers.

AUTOINCREMENT is different from merely declaring INTEGER PRIMARY KEY.
AUTOINCREMENT prevents reuse of certain previously generated ROWID values,
but it has additional storage and performance overhead and is not required
for ordinary automatically generated identifiers.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY,
                product_name TEXT NOT NULL
            )
            """
        )

        connection.execute(
            "INSERT INTO products (product_name) VALUES (?)",
            ("Keyboard",),
        )
        connection.execute(
            "INSERT INTO products (product_name) VALUES (?)",
            ("Mouse",),
        )
        connection.commit()

        show_rows(connection, "SELECT * FROM products")

        print_subtitle("Explicitly supplying an identifier")
        connection.execute(
            "INSERT INTO products VALUES (?, ?)",
            (500, "Monitor"),
        )
        connection.commit()
        show_rows(connection, "SELECT * FROM products")

        print(
            """
Do not assume this exact auto-generation behavior exists identically in
every database management system. PostgreSQL, MySQL, SQL Server, Oracle,
and SQLite have different identity-generation mechanisms.
"""
        )


# =============================================================================
# 6. UNIQUE KEYS / UNIQUE CONSTRAINTS
# =============================================================================

def unique_constraints() -> None:
    print_title("5. UNIQUE KEYS AND UNIQUE CONSTRAINTS")

    print(
        """
A UNIQUE constraint requires non-NULL values in the constrained key to be
unique according to the database's comparison rules.

It may be declared:

    Column-level:
        email TEXT UNIQUE

    Table-level:
        UNIQUE (email)

A UNIQUE constraint may contain multiple columns.

A composite UNIQUE constraint means the combination must be unique, not
necessarily each individual column.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE
            )
            """
        )

        connection.executemany(
            "INSERT INTO users (username, email) VALUES (?, ?)",
            [
                ("asha", "asha@example.com"),
                ("bharat", "bharat@example.com"),
            ],
        )

        print_subtitle("Valid unique values")
        show_rows(connection, "SELECT * FROM users")

        print_subtitle("Duplicate username")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO users (username, email) VALUES (?, ?)",
                ("asha", "new@example.com"),
            ),
            "UNIQUE",
        )

        print_subtitle("Duplicate email")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO users (username, email) VALUES (?, ?)",
                ("new_user", "asha@example.com"),
            ),
            "UNIQUE",
        )


# =============================================================================
# 7. NULL AND UNIQUE
# =============================================================================

def null_and_unique() -> None:
    print_title("6. NULL AND UNIQUE: AN IMPORTANT EDGE CASE")

    print(
        """
SQL NULL means "unknown", "missing", or "not applicable", depending on
context. It is not the same as zero, an empty string, or false.

A subtle point:

    UNIQUE does not automatically mean NOT NULL.

In SQLite, multiple NULL values can exist in a UNIQUE column because NULL is
not considered equal to another NULL for ordinary UNIQUE constraint purposes.

Therefore:

    email TEXT UNIQUE

allows multiple NULL email values.

If the business rule is:

    "Every row must have an email and every email must be unique"

use:

    email TEXT NOT NULL UNIQUE
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE contacts (
                contact_id INTEGER PRIMARY KEY,
                email TEXT UNIQUE
            )
            """
        )

        connection.executemany(
            "INSERT INTO contacts (email) VALUES (?)",
            [
                (None,),
                (None,),
                ("person@example.com",),
            ],
        )
        connection.commit()

        print_subtitle("Multiple NULLs under UNIQUE")
        show_rows(connection, "SELECT * FROM contacts")

        print_subtitle("Duplicate non-NULL value")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO contacts (email) VALUES (?)",
                ("person@example.com",),
            ),
            "UNIQUE",
        )


# =============================================================================
# 8. FOREIGN KEYS
# =============================================================================

def foreign_keys() -> None:
    print_title("7. FOREIGN KEYS")

    print(
        """
A foreign key establishes a relationship between a child table and a
parent table.

Example:

    departments
        department_id PRIMARY KEY

    employees
        department_id FOREIGN KEY REFERENCES departments(department_id)

The foreign key says that an employee's department_id must refer to a
permitted department, subject to NULLability and the configured referential
actions.

Foreign keys protect referential integrity.

A foreign key does not have to reference the primary key if the referenced
columns have an appropriate UNIQUE constraint and satisfy the DBMS rules.

Typical terminology:

    Parent table:
        The table containing the referenced key.

    Child table:
        The table containing the foreign-key column(s).

    Referenced key:
        The parent-side key.

    Referencing key:
        The child-side foreign key.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE departments (
                department_id INTEGER PRIMARY KEY,
                department_name TEXT NOT NULL UNIQUE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                employee_name TEXT NOT NULL,
                department_id INTEGER NOT NULL,
                FOREIGN KEY (department_id)
                    REFERENCES departments(department_id)
            )
            """
        )

        connection.execute(
            "INSERT INTO departments VALUES (?, ?)",
            (10, "Engineering"),
        )

        connection.execute(
            "INSERT INTO employees VALUES (?, ?, ?)",
            (1001, "Asha", 10),
        )
        connection.commit()

        print_subtitle("Valid foreign-key reference")
        show_rows(
            connection,
            """
            SELECT employee_id, employee_name, department_name
            FROM employees
            JOIN departments
              ON employees.department_id = departments.department_id
            """,
        )

        print_subtitle("Invalid foreign-key reference")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO employees VALUES (?, ?, ?)",
                (1002, "Bharat", 999),
            ),
            "FOREIGN KEY",
        )


# =============================================================================
# 9. FOREIGN KEY NULLABILITY
# =============================================================================

def nullable_foreign_keys() -> None:
    print_title("8. NULLABLE FOREIGN KEYS")

    print(
        """
A foreign key can be nullable.

If department_id is nullable:

    department_id INTEGER REFERENCES departments(department_id)

then:

    NULL

does not represent a reference to a nonexistent department. It represents
the absence of a department reference.

This is different from:

    department_id = 999

which attempts to reference an actual department with identifier 999.

If every employee must belong to a department, add NOT NULL.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE departments (
                department_id INTEGER PRIMARY KEY
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                department_id INTEGER,
                FOREIGN KEY (department_id)
                    REFERENCES departments(department_id)
            )
            """
        )

        connection.execute(
            "INSERT INTO employees VALUES (?, ?)",
            (1, None),
        )
        connection.commit()

        print_subtitle("NULL foreign key is allowed")
        show_rows(connection, "SELECT * FROM employees")

        print_subtitle("Nonexistent non-NULL foreign key is rejected")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO employees VALUES (?, ?)",
                (2, 999),
            ),
            "FOREIGN KEY",
        )


# =============================================================================
# 10. COMPOSITE PRIMARY KEYS
# =============================================================================

def composite_primary_keys() -> None:
    print_title("9. COMPOSITE PRIMARY KEYS")

    print(
        """
A composite key consists of multiple columns.

Example:

    Enrollment(student_id, course_id)

A student can enroll in many courses.
A course can have many students.
But the same student-course pair should occur only once.

Therefore:

    PRIMARY KEY (student_id, course_id)

is appropriate.

The pair is unique even though student_id repeats and course_id repeats.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE students (
                student_id INTEGER PRIMARY KEY,
                student_name TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE courses (
                course_id INTEGER PRIMARY KEY,
                course_name TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE enrollments (
                student_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                enrolled_on TEXT NOT NULL,
                PRIMARY KEY (student_id, course_id),
                FOREIGN KEY (student_id)
                    REFERENCES students(student_id),
                FOREIGN KEY (course_id)
                    REFERENCES courses(course_id)
            )
            """
        )

        connection.executemany(
            "INSERT INTO students VALUES (?, ?)",
            [(1, "Asha"), (2, "Bharat")],
        )

        connection.executemany(
            "INSERT INTO courses VALUES (?, ?)",
            [(101, "Database Systems"), (102, "Networks")],
        )

        connection.executemany(
            "INSERT INTO enrollments VALUES (?, ?, ?)",
            [
                (1, 101, "2026-09-01"),
                (1, 102, "2026-09-02"),
                (2, 101, "2026-09-03"),
            ],
        )
        connection.commit()

        print_subtitle("Many-to-many relationship")
        show_rows(connection, "SELECT * FROM enrollments")

        print_subtitle("Duplicate pair")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO enrollments VALUES (?, ?, ?)",
                (1, 101, "2026-09-10"),
            ),
            "COMPOSITE PRIMARY KEY",
        )


# =============================================================================
# 11. COMPOSITE UNIQUE CONSTRAINTS
# =============================================================================

def composite_unique_constraints() -> None:
    print_title("10. COMPOSITE UNIQUE CONSTRAINTS")

    print(
        """
A composite UNIQUE constraint enforces uniqueness of a combination.

Example:

    UNIQUE (building_id, room_number)

This allows:

    (1, 101)
    (1, 102)
    (2, 101)

but rejects:

    (1, 101)

a second time.

It does not mean building_id itself must be unique or room_number itself
must be globally unique.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE rooms (
                room_id INTEGER PRIMARY KEY,
                building_id INTEGER NOT NULL,
                room_number TEXT NOT NULL,
                UNIQUE (building_id, room_number)
            )
            """
        )

        connection.executemany(
            """
            INSERT INTO rooms (building_id, room_number)
            VALUES (?, ?)
            """,
            [
                (1, "101"),
                (1, "102"),
                (2, "101"),
            ],
        )
        connection.commit()

        print_subtitle("Valid combinations")
        show_rows(connection, "SELECT * FROM rooms")

        print_subtitle("Duplicate combination")
        explain_constraint_failure(
            lambda: connection.execute(
                """
                INSERT INTO rooms (building_id, room_number)
                VALUES (?, ?)
                """,
                (1, "101"),
            ),
            "COMPOSITE UNIQUE",
        )


# =============================================================================
# 12. NATURAL KEYS VS SURROGATE KEYS
# =============================================================================

def natural_vs_surrogate_keys() -> None:
    print_title("11. NATURAL KEYS VS SURROGATE KEYS")

    print(
        """
Natural key:
    A key derived from meaningful business data.

Examples:
    - ISO country code
    - Government-issued identifier
    - ISBN
    - A formally defined business code

Surrogate key:
    An artificial identifier introduced primarily to identify a row.

Examples:
    - integer sequence
    - UUID
    - generated numeric identifier

Natural-key advantages:
    - Can directly represent an existing real-world identifier.
    - Can prevent duplicate business identifiers.

Natural-key risks:
    - Business values can change.
    - They may be long.
    - They can expose meaningful information.
    - Composite natural keys may make relationships cumbersome.

Surrogate-key advantages:
    - Stable internal identifier.
    - Usually compact.
    - Relationships can remain unchanged when business attributes change.

Surrogate-key limitation:
    - It does not automatically enforce business uniqueness.

A common design is:

    id INTEGER PRIMARY KEY
    email TEXT NOT NULL UNIQUE

The surrogate primary key identifies the row while the UNIQUE constraint
protects a business rule.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                customer_code TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            INSERT INTO customers
                (customer_code, email, customer_name)
            VALUES (?, ?, ?)
            """,
            ("CUS-001", "asha@example.com", "Asha"),
        )
        connection.commit()

        print_subtitle("Surrogate primary key plus natural/business keys")
        show_rows(connection, "SELECT * FROM customers")


# =============================================================================
# 13. NOT NULL
# =============================================================================

def not_null_constraint() -> None:
    print_title("12. NOT NULL CONSTRAINT")

    print(
        """
NOT NULL requires a column to contain a non-NULL value.

It is a domain/entity rule about mandatory data.

Compare:

    name TEXT

with:

    name TEXT NOT NULL

The first permits NULL.
The second rejects NULL.

NOT NULL does not reject an empty string:

    ""

An empty string and NULL are different values.

Therefore, if a business rule requires non-empty text, additional validation
may be necessary, commonly through CHECK.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE people (
                person_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )

        print_subtitle("NULL violates NOT NULL")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO people (person_id, name) VALUES (?, ?)",
                (1, None),
            ),
            "NOT NULL",
        )

        print_subtitle("Empty string is not NULL")
        connection.execute(
            "INSERT INTO people VALUES (?, ?)",
            (2, ""),
        )
        connection.commit()
        show_rows(connection, "SELECT * FROM people")


# =============================================================================
# 14. CHECK CONSTRAINT
# =============================================================================

def check_constraints() -> None:
    print_title("13. CHECK CONSTRAINTS")

    print(
        """
CHECK imposes a Boolean condition on inserted or updated row values.

Examples:

    age INTEGER CHECK (age >= 0)

    salary NUMERIC CHECK (salary >= 0)

    status TEXT CHECK (status IN ('ACTIVE', 'INACTIVE'))

CHECK is useful for domain rules that are local to the row.

It should not be used as a substitute for relational constraints when the
rule is fundamentally about relationships between rows or tables.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE accounts (
                account_id INTEGER PRIMARY KEY,
                balance NUMERIC NOT NULL CHECK (balance >= 0),
                status TEXT NOT NULL
                    CHECK (status IN ('ACTIVE', 'BLOCKED'))
            )
            """
        )

        connection.execute(
            """
            INSERT INTO accounts VALUES (?, ?, ?)
            """,
            (1, 1000, "ACTIVE"),
        )
        connection.commit()

        print_subtitle("Valid CHECK values")
        show_rows(connection, "SELECT * FROM accounts")

        print_subtitle("Negative balance")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO accounts VALUES (?, ?, ?)",
                (2, -100, "ACTIVE"),
            ),
            "CHECK",
        )

        print_subtitle("Invalid status")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO accounts VALUES (?, ?, ?)",
                (3, 100, "UNKNOWN"),
            ),
            "CHECK",
        )


# =============================================================================
# 15. DEFAULT
# =============================================================================

def default_constraints() -> None:
    print_title("14. DEFAULT VALUES")

    print(
        """
DEFAULT supplies a value when an INSERT omits the column.

Examples:

    status TEXT NOT NULL DEFAULT 'ACTIVE'

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

DEFAULT does not normally prevent a caller from explicitly providing a
different value.

It is therefore different from CHECK or UNIQUE.

DEFAULT is best viewed as a value-generation rule, often combined with
other constraints.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE tasks (
                task_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING', 'DONE')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            "INSERT INTO tasks (title) VALUES (?)",
            ("Study database constraints",),
        )
        connection.commit()

        show_rows(connection, "SELECT * FROM tasks")

        print(
            """
The DEFAULT supplied PENDING because status was omitted.

If an application explicitly inserts NULL into status, NOT NULL still
applies. DEFAULT is not a replacement for NOT NULL.
"""
        )


# =============================================================================
# 16. ENTITY, REFERENTIAL, AND DOMAIN INTEGRITY
# =============================================================================

def integrity_categories() -> None:
    print_title("15. INTEGRITY CATEGORIES")

    print(
        """
Entity integrity:
    Each entity/row should have a reliable identifier.
    Primary-key constraints are the classic SQL mechanism.

Referential integrity:
    References between related tables must remain valid.
    Foreign keys enforce this.

Domain integrity:
    Attribute values must conform to permitted rules.
    NOT NULL, CHECK, data types, and appropriate defaults contribute to it.

Business integrity:
    Organization-specific rules such as:
        - salary must be non-negative
        - an account may have only certain statuses
        - an employee must belong to a department
        - a room number is unique within a building

Some business rules can be represented directly with standard constraints;
others require triggers, assertions where supported, transactions, or
application-level coordination.
"""
    )


# =============================================================================
# 17. FOREIGN KEY REFERENTIAL ACTIONS
# =============================================================================

def foreign_key_actions() -> None:
    print_title("16. FOREIGN KEY REFERENTIAL ACTIONS")

    print(
        """
When a referenced parent row is updated or deleted, the foreign key can
specify what should happen to dependent child rows.

Common actions:

    NO ACTION
        The operation is rejected if it would leave an invalid reference.

    RESTRICT
        Prevents the parent modification while dependent rows exist.
        Exact timing semantics can differ from NO ACTION in some systems.

    CASCADE
        Propagates the update or delete to dependent rows.

    SET NULL
        Sets child foreign-key values to NULL.
        The child column therefore needs to permit NULL.

    SET DEFAULT
        Sets child values to their declared defaults, subject to the
        referenced-key rules.

The correct action depends on the meaning and lifecycle of the relationship.
"""
    )

    print_subtitle("ON DELETE CASCADE")

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE authors (
                author_id INTEGER PRIMARY KEY,
                author_name TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE books (
                book_id INTEGER PRIMARY KEY,
                author_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                FOREIGN KEY (author_id)
                    REFERENCES authors(author_id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            "INSERT INTO authors VALUES (?, ?)",
            (1, "Author A"),
        )
        connection.executemany(
            "INSERT INTO books VALUES (?, ?, ?)",
            [
                (10, 1, "Book One"),
                (11, 1, "Book Two"),
            ],
        )
        connection.commit()

        print("Before deleting author:")
        show_rows(connection, "SELECT * FROM books")

        connection.execute(
            "DELETE FROM authors WHERE author_id = ?",
            (1,),
        )
        connection.commit()

        print("After deleting author:")
        show_rows(connection, "SELECT * FROM books")

    print_subtitle("ON DELETE SET NULL")

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE departments (
                department_id INTEGER PRIMARY KEY
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                department_id INTEGER,
                FOREIGN KEY (department_id)
                    REFERENCES departments(department_id)
                    ON DELETE SET NULL
            )
            """
        )

        connection.execute(
            "INSERT INTO departments VALUES (?)",
            (10,),
        )
        connection.execute(
            "INSERT INTO employees VALUES (?, ?)",
            (100, 10),
        )
        connection.commit()

        connection.execute(
            "DELETE FROM departments WHERE department_id = ?",
            (10,),
        )
        connection.commit()

        print("Employee remains, but department_id becomes NULL:")
        show_rows(connection, "SELECT * FROM employees")


# =============================================================================
# 18. FOREIGN KEY UPDATE CASCADE
# =============================================================================

def update_cascade() -> None:
    print_title("17. ON UPDATE CASCADE")

    print(
        """
ON UPDATE CASCADE propagates a changed referenced key to dependent foreign
keys.

Primary keys are often intentionally stable, so this action is less commonly
needed with surrogate identifiers. It can be useful when a referenced
business identifier is legitimately changed.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE countries (
                country_code TEXT PRIMARY KEY,
                country_name TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE offices (
                office_id INTEGER PRIMARY KEY,
                country_code TEXT NOT NULL,
                FOREIGN KEY (country_code)
                    REFERENCES countries(country_code)
                    ON UPDATE CASCADE
            )
            """
        )

        connection.execute(
            "INSERT INTO countries VALUES (?, ?)",
            ("IN", "India"),
        )
        connection.execute(
            "INSERT INTO offices VALUES (?, ?)",
            (1, "IN"),
        )
        connection.commit()

        connection.execute(
            """
            UPDATE countries
            SET country_code = ?
            WHERE country_code = ?
            """,
            ("IND", "IN"),
        )
        connection.commit()

        print("The child reference follows the parent key:")
        show_rows(connection, "SELECT * FROM offices")


# =============================================================================
# 19. MULTIPLE FOREIGN KEYS
# =============================================================================

def multiple_foreign_keys() -> None:
    print_title("18. MULTIPLE FOREIGN KEYS IN ONE TABLE")

    print(
        """
A table can contain multiple foreign keys.

Example:

    orders
        customer_id -> customers
        shipping_address_id -> addresses
        billing_address_id -> addresses

A single table can therefore have multiple relationships to the same
parent table.

When the same parent table is referenced multiple times, each foreign key
represents a different semantic relationship.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE addresses (
                address_id INTEGER PRIMARY KEY,
                address_text TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                billing_address_id INTEGER NOT NULL,
                shipping_address_id INTEGER NOT NULL,
                FOREIGN KEY (billing_address_id)
                    REFERENCES addresses(address_id),
                FOREIGN KEY (shipping_address_id)
                    REFERENCES addresses(address_id)
            )
            """
        )

        connection.executemany(
            "INSERT INTO addresses VALUES (?, ?)",
            [
                (1, "Billing Address"),
                (2, "Shipping Address"),
            ],
        )

        connection.execute(
            "INSERT INTO orders VALUES (?, ?, ?)",
            (100, 1, 2),
        )
        connection.commit()

        show_rows(connection, "SELECT * FROM orders")


# =============================================================================
# 20. REFERENCING UNIQUE NON-PRIMARY KEY
# =============================================================================

def foreign_key_to_unique_key() -> None:
    print_title("19. FOREIGN KEY REFERENCING A UNIQUE KEY")

    print(
        """
A foreign key can reference a candidate/alternate key rather than only
the primary key when the DBMS supports the required rules.

For example:

    departments.department_code UNIQUE

    employees.department_code
        REFERENCES departments(department_code)

This is useful when a stable business identifier is deliberately used for
relationships.

The referenced columns should be declared with an appropriate UNIQUE or
PRIMARY KEY constraint.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE departments (
                department_id INTEGER PRIMARY KEY,
                department_code TEXT NOT NULL UNIQUE,
                department_name TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                employee_name TEXT NOT NULL,
                department_code TEXT NOT NULL,
                FOREIGN KEY (department_code)
                    REFERENCES departments(department_code)
            )
            """
        )

        connection.execute(
            """
            INSERT INTO departments
                VALUES (?, ?, ?)
            """,
            (1, "ENG", "Engineering"),
        )

        connection.execute(
            """
            INSERT INTO employees
                VALUES (?, ?, ?)
            """,
            (100, "Asha", "ENG"),
        )
        connection.commit()

        show_rows(
            connection,
            """
            SELECT e.employee_name, d.department_name
            FROM employees e
            JOIN departments d
              ON e.department_code = d.department_code
            """,
        )


# =============================================================================
# 21. CONSTRAINT INTERACTIONS
# =============================================================================

def constraint_interactions() -> None:
    print_title("20. CONSTRAINT INTERACTIONS")

    print(
        """
Constraints are frequently combined.

Consider:

    user_id INTEGER PRIMARY KEY
    email TEXT NOT NULL UNIQUE
    age INTEGER CHECK (age >= 18)
    status TEXT NOT NULL DEFAULT 'ACTIVE'
    department_id INTEGER
        REFERENCES departments(department_id)

Each rule solves a different problem:

    PRIMARY KEY
        Identity.

    NOT NULL
        Mandatory value.

    UNIQUE
        No duplicate value.

    CHECK
        Allowed domain/range.

    DEFAULT
        Automatic value when omitted.

    FOREIGN KEY
        Valid relationship.

A robust schema usually combines several constraints instead of trying to
make one constraint perform unrelated jobs.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE departments (
                department_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                age INTEGER NOT NULL CHECK (age >= 18),
                status TEXT NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'BLOCKED')),
                department_id INTEGER,
                FOREIGN KEY (department_id)
                    REFERENCES departments(department_id)
            )
            """
        )

        connection.execute(
            "INSERT INTO departments VALUES (?, ?)",
            (1, "Engineering"),
        )

        connection.execute(
            """
            INSERT INTO users
                (email, age, department_id)
            VALUES (?, ?, ?)
            """,
            ("asha@example.com", 25, 1),
        )
        connection.commit()

        show_rows(connection, "SELECT * FROM users")


# =============================================================================
# 22. UPDATE CONSTRAINTS
# =============================================================================

def update_constraints() -> None:
    print_title("21. CONSTRAINTS APPLY TO UPDATE TOO")

    print(
        """
Constraints are not only INSERT rules.

An UPDATE can violate:

    - PRIMARY KEY
    - UNIQUE
    - NOT NULL
    - CHECK
    - FOREIGN KEY

Therefore, validation must be considered for both new rows and modified
existing rows.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY,
                sku TEXT NOT NULL UNIQUE,
                price NUMERIC NOT NULL CHECK (price >= 0)
            )
            """
        )

        connection.executemany(
            "INSERT INTO products VALUES (?, ?, ?)",
            [
                (1, "SKU-001", 100),
                (2, "SKU-002", 200),
            ],
        )
        connection.commit()

        print_subtitle("UPDATE causing UNIQUE violation")
        explain_constraint_failure(
            lambda: connection.execute(
                "UPDATE products SET sku = ? WHERE product_id = ?",
                ("SKU-001", 2),
            ),
            "UNIQUE",
        )

        print_subtitle("UPDATE causing CHECK violation")
        explain_constraint_failure(
            lambda: connection.execute(
                "UPDATE products SET price = ? WHERE product_id = ?",
                (-50, 2),
            ),
            "CHECK",
        )

        print_subtitle("Valid UPDATE")
        connection.execute(
            "UPDATE products SET price = ? WHERE product_id = ?",
            (250, 2),
        )
        connection.commit()
        show_rows(connection, "SELECT * FROM products")


# =============================================================================
# 23. DELETE CONSTRAINTS
# =============================================================================

def delete_constraints() -> None:
    print_title("22. DELETE AND REFERENTIAL INTEGRITY")

    print(
        """
A parent row cannot necessarily be deleted while child rows reference it.

The behavior depends on the foreign-key action.

With the default restrictive behavior, deleting a referenced parent can
fail.

This protects child rows from becoming orphaned.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE departments (
                department_id INTEGER PRIMARY KEY
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                department_id INTEGER NOT NULL,
                FOREIGN KEY (department_id)
                    REFERENCES departments(department_id)
            )
            """
        )

        connection.execute("INSERT INTO departments VALUES (1)")
        connection.execute("INSERT INTO employees VALUES (10, 1)")
        connection.commit()

        print_subtitle("Deleting a referenced parent")
        explain_constraint_failure(
            lambda: connection.execute(
                "DELETE FROM departments WHERE department_id = 1"
            ),
            "FOREIGN KEY",
        )


# =============================================================================
# 24. TRANSACTIONS AND CONSTRAINTS
# =============================================================================

def transactions_and_constraints() -> None:
    print_title("23. TRANSACTIONS AND CONSTRAINTS")

    print(
        """
Constraints are particularly valuable when combined with transactions.

A transaction groups operations into a unit of work.

If a constraint violation occurs and the transaction is rolled back, the
database can return to its previous consistent state.

A typical pattern is:

    BEGIN
    perform related changes
    if all succeed:
        COMMIT
    otherwise:
        ROLLBACK

Application code should explicitly define transaction boundaries for
multi-step operations that must remain consistent.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE accounts (
                account_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL CHECK (balance >= 0)
            )
            """
        )

        connection.executemany(
            "INSERT INTO accounts VALUES (?, ?)",
            [(1, 1000), (2, 500)],
        )
        connection.commit()

        print_subtitle("A transaction containing an invalid operation")

        try:
            connection.execute("BEGIN")

            connection.execute(
                "UPDATE accounts SET balance = balance - 200 WHERE account_id = 1"
            )

            connection.execute(
                "UPDATE accounts SET balance = balance + 200 WHERE account_id = 2"
            )

            # This intentionally violates CHECK.
            connection.execute(
                "UPDATE accounts SET balance = -1 WHERE account_id = 2"
            )

            connection.commit()

        except sqlite3.IntegrityError as error:
            print(f"Constraint failure: {error}")
            connection.rollback()

        print("Balances after rollback:")
        show_rows(connection, "SELECT * FROM accounts")


# =============================================================================
# 25. CONSTRAINT INTROSPECTION
# =============================================================================

def introspection() -> None:
    print_title("24. INSPECTING CONSTRAINTS")

    print(
        """
Database systems provide metadata mechanisms for inspecting schemas.

SQLite provides PRAGMA commands such as:

    PRAGMA table_info(table_name)
    PRAGMA foreign_key_list(table_name)
    PRAGMA index_list(table_name)
    PRAGMA index_info(index_name)

Schema introspection is useful for debugging migrations, verifying generated
schemas, and understanding an existing database.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE departments (
                department_id INTEGER PRIMARY KEY,
                department_code TEXT NOT NULL UNIQUE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                department_code TEXT NOT NULL,
                salary NUMERIC CHECK (salary >= 0),
                FOREIGN KEY (department_code)
                    REFERENCES departments(department_code)
            )
            """
        )

        print_subtitle("PRAGMA table_info")
        show_rows(
            connection,
            "PRAGMA table_info(employees)",
        )

        print_subtitle("PRAGMA foreign_key_list")
        show_rows(
            connection,
            "PRAGMA foreign_key_list(employees)",
        )

        print_subtitle("PRAGMA index_list")
        show_rows(
            connection,
            "PRAGMA index_list(employees)",
        )


# =============================================================================
# 26. NAMED CONSTRAINTS
# =============================================================================

def named_constraints() -> None:
    print_title("25. NAMED CONSTRAINTS")

    print(
        """
Many SQL systems allow constraints to be explicitly named.

Conceptually:

    CONSTRAINT uq_customer_email
        UNIQUE (email)

    CONSTRAINT fk_employee_department
        FOREIGN KEY (department_id)
        REFERENCES departments(department_id)

Names make database errors, migrations, documentation, and administration
easier to understand.

Exact error-message behavior and support for altering or dropping named
constraints vary between database systems.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL,
                CONSTRAINT uq_customer_email UNIQUE (email)
            )
            """
        )

        connection.execute(
            "INSERT INTO customers VALUES (?, ?)",
            (1, "a@example.com"),
        )
        connection.commit()

        print("Named UNIQUE constraint created successfully.")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO customers VALUES (?, ?)",
                (2, "a@example.com"),
            ),
            "UNIQUE",
        )


# =============================================================================
# 27. PRIMARY KEY VS UNIQUE
# =============================================================================

def primary_vs_unique() -> None:
    print_title("26. PRIMARY KEY VS UNIQUE")

    print(
        """
PRIMARY KEY:

    - Main row identifier.
    - One primary-key definition per table.
    - NULL is not allowed.
    - Frequently referenced by foreign keys.
    - Represents the chosen primary candidate key.

UNIQUE:

    - Enforces uniqueness.
    - Multiple UNIQUE constraints can exist in one table.
    - NULL handling is DBMS-dependent and commonly allows multiple NULLs.
    - Useful for alternate/candidate business identifiers.

Example:

    user_id INTEGER PRIMARY KEY
    email TEXT NOT NULL UNIQUE
    employee_code TEXT NOT NULL UNIQUE

Here user_id is the selected primary key while email and employee_code
can represent alternate candidate keys.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                employee_code TEXT NOT NULL UNIQUE
            )
            """
        )

        connection.execute(
            """
            INSERT INTO employees
            VALUES (?, ?, ?)
            """,
            (1, "asha@example.com", "EMP-001"),
        )
        connection.commit()

        show_rows(connection, "SELECT * FROM employees")


# =============================================================================
# 28. KEY CLASSIFICATION
# =============================================================================

def key_classification() -> None:
    print_title("27. KEY CLASSIFICATION")

    print(
        """
Super key:
    Any set of attributes that uniquely identifies rows.
    It may contain unnecessary attributes.

Candidate key:
    A minimal super key.

Primary key:
    The candidate key selected as the principal row identifier.

Alternate key:
    A candidate key that was not selected as the primary key.

Composite key:
    A key containing multiple attributes.

Natural key:
    A key based on meaningful domain/business data.

Surrogate key:
    An artificial identifier introduced for database identification.

Foreign key:
    Attributes in one relation that reference a key in another relation.

Important relationship:

    Every candidate key is a super key.
    Not every super key is a candidate key.

Example:

    If email is unique:

        {email}        -> candidate key
        {email, name}  -> super key, but not minimal

because name can be removed while uniqueness remains.
"""
    )


# =============================================================================
# 29. SUPER KEY MINIMALITY DEMONSTRATION
# =============================================================================

def super_key_minimality() -> None:
    print_title("28. SUPER KEY VS CANDIDATE KEY")

    print(
        """
Suppose a table contains:

    employee_id
    email
    employee_name

and employee_id is unique.

Then:

    {employee_id}
    {employee_id, employee_name}
    {employee_id, email}
    {employee_id, email, employee_name}

can all uniquely identify rows.

But only:

    {employee_id}

is minimal.

Therefore the first is a candidate key, while the larger sets are super keys.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                employee_name TEXT NOT NULL
            )
            """
        )

        connection.executemany(
            "INSERT INTO employees VALUES (?, ?, ?)",
            [
                (1, "a@example.com", "Asha"),
                (2, "b@example.com", "Bharat"),
            ],
        )
        connection.commit()

        show_rows(
            connection,
            """
            SELECT employee_id, email, employee_name
            FROM employees
            ORDER BY employee_id
            """,
        )


# =============================================================================
# 30. CONSTRAINTS AND BUSINESS RULES
# =============================================================================

def business_rule_examples() -> None:
    print_title("29. TRANSLATING BUSINESS RULES INTO CONSTRAINTS")

    print(
        """
Business requirement:
    "Every customer must have a unique email."

Possible schema:

    email TEXT NOT NULL UNIQUE

Business requirement:
    "Every order belongs to an existing customer."

Possible schema:

    customer_id INTEGER NOT NULL
        REFERENCES customers(customer_id)

Business requirement:
    "Product price cannot be negative."

Possible schema:

    price NUMERIC NOT NULL CHECK (price >= 0)

Business requirement:
    "An employee may optionally have a manager."

Possible schema:

    manager_id INTEGER
        REFERENCES employees(employee_id)

Business requirement:
    "A room number is unique within a building."

Possible schema:

    UNIQUE (building_id, room_number)

The first step in schema design is translating business rules into precise
data-integrity statements.
"""
    )


# =============================================================================
# 31. SELF-REFERENCING FOREIGN KEY
# =============================================================================

def self_referencing_foreign_key() -> None:
    print_title("30. SELF-REFERENCING FOREIGN KEY")

    print(
        """
A foreign key can reference the same table.

A classic example is an organizational hierarchy:

    employee.manager_id -> employee.employee_id

The manager is also an employee.

This supports tree-like relationships within one table.

The root employee can have manager_id = NULL if the relationship is
optional.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                employee_name TEXT NOT NULL,
                manager_id INTEGER,
                FOREIGN KEY (manager_id)
                    REFERENCES employees(employee_id)
            )
            """
        )

        connection.executemany(
            """
            INSERT INTO employees
                (employee_id, employee_name, manager_id)
            VALUES (?, ?, ?)
            """,
            [
                (1, "CEO", None),
                (2, "Engineering Head", 1),
                (3, "Developer", 2),
            ],
        )
        connection.commit()

        show_rows(connection, "SELECT * FROM employees")

        print_subtitle("Invalid manager")
        explain_constraint_failure(
            lambda: connection.execute(
                """
                INSERT INTO employees
                    (employee_id, employee_name, manager_id)
                VALUES (?, ?, ?)
                """,
                (4, "Invalid Employee", 999),
            ),
            "FOREIGN KEY",
        )


# =============================================================================
# 32. MANY-TO-MANY DESIGN
# =============================================================================

def many_to_many_design() -> None:
    print_title("31. MANY-TO-MANY RELATIONSHIP WITH COMPOSITE KEY")

    print(
        """
A many-to-many relationship is commonly represented using a junction,
bridge, or associative table.

Example:

    students <-> courses

becomes:

    students
    courses
    enrollments

The junction table commonly has:

    PRIMARY KEY (student_id, course_id)

and two foreign keys.

This design prevents duplicate relationship rows and provides referential
integrity on both sides.
"""
    )

    with closing(create_connection()) as connection:
        connection.executescript(
            """
            CREATE TABLE students (
                student_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE courses (
                course_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE enrollments (
                student_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                PRIMARY KEY (student_id, course_id),
                FOREIGN KEY (student_id)
                    REFERENCES students(student_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (course_id)
                    REFERENCES courses(course_id)
                    ON DELETE CASCADE
            );
            """
        )

        connection.executemany(
            "INSERT INTO students VALUES (?, ?)",
            [(1, "Asha"), (2, "Bharat")],
        )
        connection.executemany(
            "INSERT INTO courses VALUES (?, ?)",
            [(10, "SQL"), (20, "Python")],
        )
        connection.executemany(
            "INSERT INTO enrollments VALUES (?, ?)",
            [(1, 10), (1, 20), (2, 10)],
        )
        connection.commit()

        show_rows(
            connection,
            """
            SELECT s.name AS student, c.name AS course
            FROM enrollments e
            JOIN students s ON s.student_id = e.student_id
            JOIN courses c ON c.course_id = e.course_id
            ORDER BY s.student_id, c.course_id
            """,
        )


# =============================================================================
# 33. DEFERRABLE CONSTRAINT CONCEPT
# =============================================================================

def deferrable_constraint_concept() -> None:
    print_title("32. DEFERRABLE CONSTRAINTS: ADVANCED CONCEPT")

    print(
        """
Some database systems support deferrable constraints.

A deferrable constraint may be checked at transaction commit rather than
immediately after each statement.

This can be useful when a sequence of related operations temporarily creates
an intermediate state that is invalid but ends in a valid state.

Typical syntax in systems that support it includes concepts such as:

    DEFERRABLE
    INITIALLY DEFERRED
    INITIALLY IMMEDIATE

Support and exact behavior vary significantly by DBMS.

SQLite has support for some deferred foreign-key behavior, but this script
does not rely on it for the fundamental examples.

The design lesson is important:
constraint timing can matter when operations have dependencies on each other.
"""
    )


# =============================================================================
# 34. PARTIAL / CONDITIONAL UNIQUENESS
# =============================================================================

def conditional_uniqueness() -> None:
    print_title("33. CONDITIONAL UNIQUENESS WITH A PARTIAL INDEX")

    print(
        """
A useful advanced pattern is conditional uniqueness.

Business rule:

    "Only active usernames must be unique."

Some database systems support filtered or partial indexes.

SQLite supports partial indexes.

Example:

    CREATE UNIQUE INDEX ...
    WHERE active = 1

This is different from a normal UNIQUE constraint because uniqueness applies
only to rows satisfying the predicate.

This is especially useful for soft-delete designs.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE accounts (
                account_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                active INTEGER NOT NULL CHECK (active IN (0, 1))
            )
            """
        )

        connection.execute(
            """
            CREATE UNIQUE INDEX uq_active_username
            ON accounts(username)
            WHERE active = 1
            """
        )

        connection.executemany(
            "INSERT INTO accounts VALUES (?, ?, ?)",
            [
                (1, "asha", 1),
                (2, "asha", 0),
            ],
        )
        connection.commit()

        print("Same username is allowed when one account is inactive:")
        show_rows(connection, "SELECT * FROM accounts")

        print_subtitle("Second active username is rejected")
        explain_constraint_failure(
            lambda: connection.execute(
                "INSERT INTO accounts VALUES (?, ?, ?)",
                (3, "asha", 1),
            ),
            "CONDITIONAL UNIQUE",
        )


# =============================================================================
# 35. NULL AND COMPOSITE UNIQUE
# =============================================================================

def null_composite_unique() -> None:
    print_title("34. NULL WITH COMPOSITE UNIQUE CONSTRAINTS")

    print(
        """
Composite UNIQUE constraints and NULL require careful thought.

For:

    UNIQUE (country_code, phone_number)

the exact behavior with NULL components follows the DBMS's NULL and
uniqueness semantics.

In SQLite, rows containing NULL can coexist under UNIQUE in situations where
the complete combinations are not considered equal.

If the business rule requires both values to exist, explicitly use:

    country_code TEXT NOT NULL
    phone_number TEXT NOT NULL
    UNIQUE (country_code, phone_number)
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE phone_numbers (
                row_id INTEGER PRIMARY KEY,
                country_code TEXT,
                phone_number TEXT,
                UNIQUE (country_code, phone_number)
            )
            """
        )

        connection.executemany(
            """
            INSERT INTO phone_numbers
                (country_code, phone_number)
            VALUES (?, ?)
            """,
            [
                ("+91", "1111111111"),
                ("+91", None),
                ("+91", None),
                (None, "2222222222"),
            ],
        )
        connection.commit()

        show_rows(connection, "SELECT * FROM phone_numbers")


# =============================================================================
# 36. DATA TYPE AND CONSTRAINT INTERACTION
# =============================================================================

def type_and_constraint_interaction() -> None:
    print_title("35. DATA TYPES ARE NOT A SUBSTITUTE FOR CONSTRAINTS")

    print(
        """
A column data type and a constraint solve different problems.

For example:

    price NUMERIC

does not necessarily express:

    price must exist
    price must be non-negative

Those requirements are better expressed as:

    price NUMERIC NOT NULL CHECK (price >= 0)

Similarly:

    status TEXT

does not automatically mean:

    status must be ACTIVE, BLOCKED, or CLOSED

A CHECK constraint can express that domain rule.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE invoices (
                invoice_id INTEGER PRIMARY KEY,
                amount NUMERIC NOT NULL CHECK (amount >= 0),
                status TEXT NOT NULL
                    CHECK (status IN ('OPEN', 'PAID', 'CANCELLED'))
            )
            """
        )

        connection.execute(
            "INSERT INTO invoices VALUES (?, ?, ?)",
            (1, 2500, "OPEN"),
        )
        connection.commit()

        show_rows(connection, "SELECT * FROM invoices")


# =============================================================================
# 37. CONSTRAINT VALIDATION TEST SUITE
# =============================================================================

@dataclass
class ConstraintTest:
    """Represents one expected constraint behavior."""

    name: str
    operation: Callable[[sqlite3.Connection], None]
    expected_error_fragment: str


def run_constraint_tests(
    connection: sqlite3.Connection,
    tests: Iterable[ConstraintTest],
) -> None:
    """Run small schema-integrity tests and report their outcomes."""
    passed = 0
    failed = 0

    for test in tests:
        try:
            connection.execute("BEGIN")
            test.operation(connection)
            connection.rollback()
            print(f"FAIL: {test.name} unexpectedly succeeded")
            failed += 1
        except sqlite3.IntegrityError as error:
            connection.rollback()
            error_text = str(error).lower()

            if test.expected_error_fragment.lower() in error_text:
                print(f"PASS: {test.name}")
                passed += 1
            else:
                print(
                    f"FAIL: {test.name} produced an unexpected error: {error}"
                )
                failed += 1

    print(f"\nTest results: {passed} passed, {failed} failed")


def constraint_testing() -> None:
    print_title("36. TESTING DATABASE CONSTRAINTS")

    print(
        """
Constraints should be tested like application logic.

A useful test suite checks:

    - duplicate primary keys
    - duplicate UNIQUE values
    - NULL in NOT NULL columns
    - invalid CHECK values
    - invalid foreign keys
    - valid boundary values
    - update violations
    - delete behavior
    - cascade behavior
    - nullable relationships

The database is part of the correctness boundary, so its schema rules
deserve automated tests.
"""
    )

    with closing(create_connection()) as connection:
        connection.executescript(
            """
            CREATE TABLE departments (
                department_id INTEGER PRIMARY KEY
            );

            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                age INTEGER NOT NULL CHECK (age >= 18),
                department_id INTEGER NOT NULL,
                FOREIGN KEY (department_id)
                    REFERENCES departments(department_id)
            );

            INSERT INTO departments VALUES (1);

            INSERT INTO employees
                VALUES (100, 'asha@example.com', 25, 1);
            """
        )
        connection.commit()

        tests = [
            ConstraintTest(
                name="duplicate primary key",
                operation=lambda db: db.execute(
                    """
                    INSERT INTO employees
                    VALUES (100, 'another@example.com', 25, 1)
                    """
                ),
                expected_error_fragment="UNIQUE",
            ),
            ConstraintTest(
                name="duplicate unique email",
                operation=lambda db: db.execute(
                    """
                    INSERT INTO employees
                    VALUES (101, 'asha@example.com', 25, 1)
                    """
                ),
                expected_error_fragment="UNIQUE",
            ),
            ConstraintTest(
                name="NULL email",
                operation=lambda db: db.execute(
                    """
                    INSERT INTO employees
                    VALUES (101, NULL, 25, 1)
                    """
                ),
                expected_error_fragment="NOT NULL",
            ),
            ConstraintTest(
                name="CHECK violation",
                operation=lambda db: db.execute(
                    """
                    INSERT INTO employees
                    VALUES (101, 'b@example.com', 17, 1)
                    """
                ),
                expected_error_fragment="CHECK",
            ),
            ConstraintTest(
                name="foreign-key violation",
                operation=lambda db: db.execute(
                    """
                    INSERT INTO employees
                    VALUES (101, 'b@example.com', 25, 999)
                    """
                ),
                expected_error_fragment="FOREIGN KEY",
            ),
        ]

        run_constraint_tests(connection, tests)


# =============================================================================
# 38. INDEXES AND CONSTRAINT PERFORMANCE
# =============================================================================

def indexes_and_performance() -> None:
    print_title("37. PERFORMANCE CONSIDERATIONS")

    print(
        """
UNIQUE and PRIMARY KEY constraints commonly require indexes or index-like
structures to enforce uniqueness efficiently.

Indexes can improve:

    - uniqueness checks
    - primary-key lookups
    - joins
    - foreign-key-related queries

But indexes also have costs:

    - additional storage
    - additional work during INSERT
    - additional work during UPDATE
    - additional work during DELETE
    - maintenance complexity

A foreign-key column is often worth indexing in a production schema,
especially when parent rows are frequently updated/deleted or child rows are
frequently joined/filtering by the foreign key.

Do not blindly index every column. Indexes should support actual access
patterns and constraint-related workloads.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                order_total NUMERIC NOT NULL CHECK (order_total >= 0),
                FOREIGN KEY (customer_id)
                    REFERENCES customers(customer_id)
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX idx_orders_customer_id
            ON orders(customer_id)
            """
        )

        print("Indexes created for key enforcement and query performance.")
        show_rows(connection, "PRAGMA index_list(customers)")
        show_rows(connection, "PRAGMA index_list(orders)")


# =============================================================================
# 39. SECURITY CONSIDERATIONS
# =============================================================================

def security_considerations() -> None:
    print_title("38. SECURITY CONSIDERATIONS")

    print(
        """
Constraints are not a complete security model, but they are an important
defense against invalid state.

Examples:

    NOT NULL
        Prevents required security-related attributes from being absent.

    CHECK
        Can restrict states such as account status.

    FOREIGN KEY
        Prevents references to nonexistent objects.

    UNIQUE
        Prevents duplicate identifiers where uniqueness is a security or
        business requirement.

Constraints should not be treated as authorization.

For example:

    FOREIGN KEY does not mean a user is authorized to access the referenced
    record.

Authorization belongs to the access-control layer.

Use parameterized SQL rather than string concatenation to prevent SQL
injection.

This script demonstrates parameterized statements throughout most examples.
"""
    )

    with closing(create_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE
            )
            """
        )

        username = "user'; DROP TABLE users; --"

        # Parameterization treats this as data rather than executable SQL.
        connection.execute(
            "INSERT INTO users (username) VALUES (?)",
            (username,),
        )
        connection.commit()

        print("Stored potentially dangerous-looking text safely as data:")
        show_rows(connection, "SELECT * FROM users")


# =============================================================================
# 40. COMMON MISTAKES
# =============================================================================

def common_mistakes() -> None:
    print_title("39. COMMON MISTAKES")

    print(
        """
Mistake 1:
    Assuming UNIQUE automatically means NOT NULL.

Correction:
    Use NOT NULL UNIQUE when both rules are required.

Mistake 2:
    Assuming every database treats constraints identically.

Correction:
    Check DBMS-specific behavior.

Mistake 3:
    Forgetting to enable foreign keys in SQLite.

Correction:
    Execute:

        PRAGMA foreign_keys = ON

    for the connection.

Mistake 4:
    Using application-only validation for core integrity rules.

Correction:
    Put critical invariants in the database whenever appropriate.

Mistake 5:
    Treating a surrogate key as proof of business uniqueness.

Correction:
    Add UNIQUE constraints for business identifiers.

Mistake 6:
    Creating an unnecessarily wide composite primary key.

Correction:
    Evaluate whether a surrogate primary key plus targeted UNIQUE
    constraints produces a clearer and more maintainable design.

Mistake 7:
    Making a foreign key nullable when the relationship is mandatory.

Correction:
    Add NOT NULL.

Mistake 8:
    Using ON DELETE CASCADE without considering business consequences.

Correction:
    Decide whether deletion should cascade, be restricted, set NULL,
    or be prevented through another lifecycle design.

Mistake 9:
    Assuming data types alone enforce all business rules.

Correction:
    Combine types with CHECK, NOT NULL, UNIQUE, and foreign keys.

Mistake 10:
    Ignoring UPDATE behavior.

Correction:
    Test updates as well as inserts and deletes.
"""
    )


# =============================================================================
# 41. EDGE CASES
# =============================================================================

def edge_cases() -> None:
    print_title("40. IMPORTANT EDGE CASES")

    print(
        """
Edge cases worth considering during schema design:

    1. NULL values
       Especially with UNIQUE and foreign keys.

    2. Empty strings
       They are not the same as NULL.

    3. Composite keys
       Uniqueness applies to the complete combination.

    4. Parent deletion
       May fail or trigger a referential action.

    5. Parent-key update
       May fail or cascade.

    6. Self-referencing rows
       Can model hierarchies but require careful lifecycle handling.

    7. Soft deletes
       May require partial/filtered uniqueness.

    8. Mutable natural keys
       Can affect every referencing relationship.

    9. Concurrent transactions
       Database locking and isolation behavior can affect when conflicts
       become visible.

    10. Database-specific NULL and CHECK semantics
        SQL standard concepts and actual DBMS implementations are not
        perfectly interchangeable.

    11. Empty tables
        A key is a schema property even before any data exists.

    12. Boundary values
        Test exactly permitted and forbidden values, such as age 18 versus 17.

    13. Multiple constraints
        A single operation may violate more than one rule. The exact error
        reported can depend on the database engine and evaluation order.
"""
    )


# =============================================================================
# 42. NORMALIZATION CONNECTION
# =============================================================================

def normalization_connection() -> None:
    print_title("41. KEYS AND NORMALIZATION")

    print(
        """
Keys are fundamental to normalization.

Functional dependency:

    X -> Y

means that if two rows agree on X, they must agree on Y.

Candidate keys are especially important when analyzing functional
dependencies and normal forms.

For example:

    employee_id -> employee_name, email, department_id

If employee_id is a candidate key, its value determines the non-key
attributes in the relation.

Normalization uses these dependencies to reduce undesirable redundancy and
update anomalies.

Constraints then provide executable enforcement of important parts of the
intended model.
"""
    )


# =============================================================================
# 43. PRIMARY KEY DESIGN DECISION
# =============================================================================

def primary_key_design_decision() -> None:
    print_title("42. PRIMARY KEY DESIGN DECISION")

    print(
        """
When choosing a primary key, consider:

    Stability:
        Will the value change?

    Uniqueness:
        Is uniqueness guaranteed by the domain?

    Nullability:
        Can the value ever be absent?

    Width:
        How large is the key in indexes and foreign keys?

    Meaning:
        Does the identifier expose business information?

    Generation:
        Is it generated by the application or database?

    Distribution:
        For distributed systems, will generation remain safe and scalable?

A simple numeric surrogate key can be excellent for internal identity,
while a separate UNIQUE constraint can protect a business identifier.

There is no universal rule that natural keys or surrogate keys are always
superior.
"""
    )


# =============================================================================
# 44. PRODUCTION SCHEMA EXAMPLE
# =============================================================================

def production_style_schema() -> None:
    print_title("43. PRODUCTION-STYLE SCHEMA")

    print(
        """
The following example combines many concepts in one coherent design:

    organizations
        organization_id PRIMARY KEY
        organization_code UNIQUE

    users
        user_id PRIMARY KEY
        email UNIQUE
        organization_id FOREIGN KEY

    projects
        project_id PRIMARY KEY
        organization_id FOREIGN KEY

    project_members
        composite PRIMARY KEY
        two foreign keys

The example also demonstrates CHECK, NOT NULL, DEFAULT, CASCADE, and
indexes.
"""
    )

    with closing(create_connection()) as connection:
        connection.executescript(
            """
            CREATE TABLE organizations (
                organization_id INTEGER PRIMARY KEY,
                organization_code TEXT NOT NULL UNIQUE,
                organization_name TEXT NOT NULL
            );

            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                organization_id INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
                    CHECK (active IN (0, 1)),
                FOREIGN KEY (organization_id)
                    REFERENCES organizations(organization_id)
                    ON DELETE RESTRICT
            );

            CREATE TABLE projects (
                project_id INTEGER PRIMARY KEY,
                organization_id INTEGER NOT NULL,
                project_code TEXT NOT NULL,
                project_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'ARCHIVED')),
                UNIQUE (organization_id, project_code),
                FOREIGN KEY (organization_id)
                    REFERENCES organizations(organization_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE project_members (
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL
                    CHECK (role IN ('OWNER', 'MEMBER')),
                PRIMARY KEY (project_id, user_id),
                FOREIGN KEY (project_id)
                    REFERENCES projects(project_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX idx_users_organization
                ON users(organization_id);

            CREATE INDEX idx_projects_organization
                ON projects(organization_id);

            CREATE INDEX idx_project_members_user
                ON project_members(user_id);
            """
        )

        connection.execute(
            """
            INSERT INTO organizations
                (organization_id, organization_code, organization_name)
            VALUES (?, ?, ?)
            """,
            (1, "ORG-A", "Organization A"),
        )

        connection.executemany(
            """
            INSERT INTO users
                (user_id, email, full_name, organization_id)
            VALUES (?, ?, ?, ?)
            """,
            [
                (1, "asha@example.com", "Asha", 1),
                (2, "bharat@example.com", "Bharat", 1),
            ],
        )

        connection.executemany(
            """
            INSERT INTO projects
                (project_id, organization_id, project_code, project_name)
            VALUES (?, ?, ?, ?)
            """,
            [
                (10, 1, "P-001", "Data Platform"),
                (11, 1, "P-002", "Security Platform"),
            ],
        )

        connection.executemany(
            """
            INSERT INTO project_members
                (project_id, user_id, role)
            VALUES (?, ?, ?)
            """,
            [
                (10, 1, "OWNER"),
                (10, 2, "MEMBER"),
                (11, 2, "OWNER"),
            ],
        )

        connection.commit()

        print_subtitle("Organizations")
        show_rows(connection, "SELECT * FROM organizations")

        print_subtitle("Users")
        show_rows(connection, "SELECT * FROM users")

        print_subtitle("Projects")
        show_rows(connection, "SELECT * FROM projects")

        print_subtitle("Project members")
        show_rows(connection, "SELECT * FROM project_members")

        print_subtitle("Joined business view")
        show_rows(
            connection,
            """
            SELECT
                p.project_code,
                p.project_name,
                u.email,
                pm.role
            FROM project_members pm
            JOIN projects p
              ON p.project_id = pm.project_id
            JOIN users u
              ON u.user_id = pm.user_id
            ORDER BY p.project_id, u.user_id
            """,
        )

        print_subtitle("Duplicate project code inside same organization")
        explain_constraint_failure(
            lambda: connection.execute(
                """
                INSERT INTO projects
                    (organization_id, project_code, project_name)
                VALUES (?, ?, ?)
                """,
                (1, "P-001", "Duplicate"),
            ),
            "COMPOSITE UNIQUE",
        )

        print_subtitle("Same project code in another organization")
        connection.execute(
            """
            INSERT INTO organizations
                (organization_id, organization_code, organization_name)
            VALUES (?, ?, ?)
            """,
            (2, "ORG-B", "Organization B"),
        )

        connection.execute(
            """
            INSERT INTO projects
                (organization_id, project_code, project_name)
            VALUES (?, ?, ?)
            """,
            (2, "P-001", "Different Organization Project"),
        )
        connection.commit()

        show_rows(
            connection,
            """
            SELECT organization_id, project_code, project_name
            FROM projects
            ORDER BY organization_id
            """,
        )


# =============================================================================
# 45. CASCADE TRADE-OFF DEMONSTRATION
# =============================================================================

def cascade_tradeoffs() -> None:
    print_title("44. CASCADE TRADE-OFFS")

    print(
        """
CASCADE can be convenient for dependent data whose lifecycle is inseparable
from the parent.

Examples:

    order -> order_items
    project -> project_members
    post -> post_comments

CASCADE can be dangerous when deletion of one parent unexpectedly removes
large amounts of dependent data.

For business-critical data, RESTRICT or soft-delete strategies may be more
appropriate.

The correct question is not:

    "Which action is easiest?"

The correct question is:

    "What should happen to dependent business data when the parent
     relationship disappears?"
"""
    )

    with closing(create_connection()) as connection:
        connection.executescript(
            """
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY
            );

            CREATE TABLE order_items (
                order_item_id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                FOREIGN KEY (order_id)
                    REFERENCES orders(order_id)
                    ON DELETE CASCADE
            );
            """
        )

        connection.execute("INSERT INTO orders VALUES (1)")
        connection.execute(
            "INSERT INTO order_items VALUES (?, ?, ?)",
            (100, 1, "Keyboard"),
        )
        connection.commit()

        print("Before order deletion:")
        show_rows(connection, "SELECT * FROM order_items")

        connection.execute("DELETE FROM orders WHERE order_id = 1")
        connection.commit()

        print("After order deletion:")
        show_rows(connection, "SELECT * FROM order_items")


# =============================================================================
# 46. PRACTICAL SCHEMA REVIEW CHECKLIST
# =============================================================================

def schema_review_checklist() -> None:
    print_title("45. PRACTICAL SCHEMA REVIEW CHECKLIST")

    checklist = [
        "Does every important entity have a primary key?",
        "Is the primary key stable and appropriate?",
        "Are alternate business identifiers protected with UNIQUE?",
        "Are mandatory attributes declared NOT NULL?",
        "Are domain ranges and enumerated states protected with CHECK?",
        "Are foreign keys declared for real relationships?",
        "Are nullable foreign keys intentional?",
        "Are composite keys truly necessary and minimal?",
        "Are composite UNIQUE constraints expressed at the correct scope?",
        "Are DELETE actions deliberately selected?",
        "Are UPDATE actions deliberately selected?",
        "Are foreign-key columns indexed where workload requires it?",
        "Are NULL semantics understood?",
        "Are natural and surrogate identifiers used intentionally?",
        "Are transaction boundaries sufficient for multi-step invariants?",
        "Are constraints tested during INSERT, UPDATE, and DELETE?",
        "Are DBMS-specific semantics documented?",
        "Are destructive CASCADE actions reviewed carefully?",
        "Are sensitive identifiers exposed unnecessarily?",
        "Are application validation and database constraints aligned?",
    ]

    for number, item in enumerate(checklist, start=1):
        print(f"{number:2}. [ ] {item}")


# =============================================================================
# 47. CONSTRAINT DECISION TABLE
# =============================================================================

def decision_table() -> None:
    print_title("46. CONSTRAINT DECISION TABLE")

    print(
        """
Requirement                                Typical SQL mechanism
---------------------------------------------------------------------------
Identify each row                           PRIMARY KEY
Prevent duplicate values                   UNIQUE
Require a value                            NOT NULL
Restrict a value to a domain               CHECK
Provide an omitted value                   DEFAULT
Connect rows across tables                 FOREIGN KEY
Delete children with parent                ON DELETE CASCADE
Detach children from deleted parent        ON DELETE SET NULL
Prevent parent deletion                    ON DELETE RESTRICT / NO ACTION
Propagate referenced-key changes           ON UPDATE CASCADE
Enforce conditional uniqueness             Partial/filtered UNIQUE index
Enforce multi-column identity              Composite PRIMARY KEY
Enforce multi-column business uniqueness   Composite UNIQUE

These mechanisms are complementary rather than interchangeable.
"""
    )


# =============================================================================
# 48. FINAL INTEGRATED EXERCISES
# =============================================================================

def integrated_exercises() -> None:
    print_title("47. INTEGRATED EXAMPLES AND EDGE-CASE TESTS")

    with closing(create_connection()) as connection:
        connection.executescript(
            """
            CREATE TABLE departments (
                department_id INTEGER PRIMARY KEY,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            );

            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                employee_code TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                salary NUMERIC NOT NULL CHECK (salary >= 0),
                department_id INTEGER,
                manager_id INTEGER,
                status TEXT NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'INACTIVE')),
                FOREIGN KEY (department_id)
                    REFERENCES departments(department_id)
                    ON DELETE SET NULL,
                FOREIGN KEY (manager_id)
                    REFERENCES employees(employee_id)
            );

            CREATE TABLE projects (
                project_id INTEGER PRIMARY KEY,
                department_id INTEGER NOT NULL,
                project_code TEXT NOT NULL,
                project_name TEXT NOT NULL,
                UNIQUE (department_id, project_code),
                FOREIGN KEY (department_id)
                    REFERENCES departments(department_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE project_assignments (
                project_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                assignment_role TEXT NOT NULL
                    CHECK (assignment_role IN ('LEAD', 'MEMBER')),
                PRIMARY KEY (project_id, employee_id),
                FOREIGN KEY (project_id)
                    REFERENCES projects(project_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (employee_id)
                    REFERENCES employees(employee_id)
                    ON DELETE CASCADE
            );
            """
        )

        connection.executemany(
            "INSERT INTO departments VALUES (?, ?, ?)",
            [
                (1, "ENG", "Engineering"),
                (2, "FIN", "Finance"),
            ],
        )

        connection.execute(
            """
            INSERT INTO employees
                (employee_id, employee_code, email, name, salary, department_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (1, "EMP-001", "asha@example.com", "Asha", 90000, 1),
        )

        connection.execute(
            """
            INSERT INTO employees
                (employee_id, employee_code, email, name, salary,
                 department_id, manager_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (2, "EMP-002", "bharat@example.com", "Bharat", 70000, 1, 1),
        )

        connection.execute(
            """
            INSERT INTO projects
                (project_id, department_id, project_code, project_name)
            VALUES (?, ?, ?, ?)
            """,
            (100, 1, "PLATFORM", "Platform Engineering"),
        )

        connection.executemany(
            """
            INSERT INTO project_assignments
                (project_id, employee_id, assignment_role)
            VALUES (?, ?, ?)
            """,
            [
                (100, 1, "LEAD"),
                (100, 2, "MEMBER"),
            ],
        )

        connection.commit()

        print_subtitle("Integrated schema data")
        show_rows(
            connection,
            """
            SELECT
                e.employee_id,
                e.employee_code,
                e.name,
                d.code AS department_code,
                e.manager_id,
                e.status
            FROM employees e
            LEFT JOIN departments d
              ON d.department_id = e.department_id
            ORDER BY e.employee_id
            """,
        )

        print_subtitle("Invalid salary")
        explain_constraint_failure(
            lambda: connection.execute(
                """
                INSERT INTO employees
                    (employee_id, employee_code, email, name, salary)
                VALUES (?, ?, ?, ?, ?)
                """,
                (3, "EMP-003", "c@example.com", "Chitra", -1),
            ),
            "CHECK",
        )

        print_subtitle("Invalid manager")
        explain_constraint_failure(
            lambda: connection.execute(
                """
                INSERT INTO employees
                    (employee_id, employee_code, email, name, salary, manager_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (3, "EMP-003", "c@example.com", "Chitra", 50000, 999),
            ),
            "FOREIGN KEY",
        )

        print_subtitle("Duplicate employee code")
        explain_constraint_failure(
            lambda: connection.execute(
                """
                INSERT INTO employees
                    (employee_id, employee_code, email, name, salary)
                VALUES (?, ?, ?, ?, ?)
                """,
                (3, "EMP-001", "c@example.com", "Chitra", 50000),
            ),
            "UNIQUE",
        )

        print_subtitle("Duplicate project code in same department")
        explain_constraint_failure(
            lambda: connection.execute(
                """
                INSERT INTO projects
                    (project_id, department_id, project_code, project_name)
                VALUES (?, ?, ?, ?)
                """,
                (101, 1, "PLATFORM", "Duplicate Platform"),
            ),
            "UNIQUE",
        )

        print_subtitle("Deleting a department with ON DELETE SET NULL")

        connection.execute(
            "DELETE FROM departments WHERE department_id = ?",
            (1,),
        )
        connection.commit()

        print("Projects were deleted through ON DELETE CASCADE.")
        show_rows(connection, "SELECT * FROM projects")

        print("Employees remain, but department_id becomes NULL.")
        show_rows(
            connection,
            """
            SELECT employee_id, name, department_id
            FROM employees
            ORDER BY employee_id
            """,
        )

        print("Project assignments were deleted through project CASCADE.")
        show_rows(connection, "SELECT * FROM project_assignments")


# =============================================================================
# 49. LEARNING MAP
# =============================================================================

def learning_map() -> None:
    print_title("48. CONCEPTUAL LEARNING MAP")

    print(
        """
RELATIONAL MODEL
|
+-- Attributes
|
+-- Tuples / Rows
|
+-- Keys
|   |
|   +-- Super Key
|   |
|   +-- Candidate Key
|   |   |
|   |   +-- Primary Key
|   |   |
|   |   +-- Alternate Keys
|   |
|   +-- Composite Key
|   |
|   +-- Natural Key
|   |
|   +-- Surrogate Key
|   |
|   +-- Foreign Key
|
+-- Constraints
    |
    +-- PRIMARY KEY
    |
    +-- UNIQUE
    |
    +-- NOT NULL
    |
    +-- CHECK
    |
    +-- DEFAULT
    |
    +-- FOREIGN KEY
        |
        +-- CASCADE
        +-- RESTRICT
        +-- NO ACTION
        +-- SET NULL
        +-- SET DEFAULT

The key idea is to model identity and relationships precisely, then let
the database enforce the invariants that belong at the data layer.
"""
    )


# =============================================================================
# 50. MAIN
# =============================================================================

def main() -> None:
    """
    Execute the complete educational program.

    Every section uses an isolated in-memory database where appropriate,
    allowing examples to be run repeatedly without persistent side effects.
    """
    sections = [
        fundamentals,
        candidate_keys,
        primary_keys,
        sqlite_integer_primary_key,
        unique_constraints,
        null_and_unique,
        foreign_keys,
        nullable_foreign_keys,
        composite_primary_keys,
        composite_unique_constraints,
        natural_vs_surrogate_keys,
        not_null_constraint,
        check_constraints,
        default_constraints,
        integrity_categories,
        foreign_key_actions,
        update_cascade,
        multiple_foreign_keys,
        foreign_key_to_unique_key,
        constraint_interactions,
        update_constraints,
        delete_constraints,
        transactions_and_constraints,
        introspection,
        named_constraints,
        primary_vs_unique,
        key_classification,
        super_key_minimality,
        business_rule_examples,
        self_referencing_foreign_key,
        many_to_many_design,
        deferrable_constraint_concept,
        conditional_uniqueness,
        null_composite_unique,
        type_and_constraint_interaction,
        constraint_testing,
        indexes_and_performance,
        security_considerations,
        common_mistakes,
        edge_cases,
        normalization_connection,
        primary_key_design_decision,
        production_style_schema,
        cascade_tradeoffs,
        schema_review_checklist,
        decision_table,
        integrated_exercises,
        learning_map,
    ]

    print_title("KEYS AND CONSTRAINTS IN RELATIONAL DATABASES")
    print(
        """
This executable study program progresses from relational fundamentals to
advanced key and constraint design.

The examples use SQLite through Python's standard-library sqlite3 module.
Foreign-key enforcement is explicitly enabled on every demonstration
connection.
"""
    )

    for section in sections:
        section()

    print_title("END OF STUDY SCRIPT")
    print(
        """
The important design distinction is:

    Keys answer:
        "How is a row identified or related?"

    Constraints answer:
        "What states are allowed in the database?"

Good relational design combines both so that important data invariants are
precisely represented and reliably enforced.
"""
    )


if __name__ == "__main__":
    main()
