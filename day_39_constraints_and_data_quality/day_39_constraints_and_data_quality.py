#!/usr/bin/env python3
"""
Constraints and Data Quality: CHECK, NOT NULL, UNIQUE, and Business Rules.

A self-contained demonstration of relational integrity, data validation,
constraint enforcement, data-quality diagnostics, and transaction safety.

Run with:
    python constraints_data_quality.py

The implementation uses only the Python standard library and SQLite.
"""

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


DATABASE_NAME = "quality_demo.db"


class DataQualityError(ValueError):
    """Raised when an application-level data-quality rule is violated."""


@dataclass(frozen=True)
class Employee:
    employee_code: str
    email: str
    full_name: str
    age: int
    salary: Decimal
    department: str
    active: bool = True


def normalize_email(email: str) -> str:
    """Normalize an email identifier before enforcing uniqueness."""
    if not isinstance(email, str):
        raise DataQualityError("Email must be text.")

    normalized = email.strip().casefold()

    if not normalized or normalized.count("@") != 1:
        raise DataQualityError("Email must contain exactly one @ symbol.")

    local_part, domain = normalized.split("@")

    if not local_part or "." not in domain or domain.startswith("."):
        raise DataQualityError("Email has an invalid basic structure.")

    if domain.endswith(".") or any(character.isspace() for character in normalized):
        raise DataQualityError("Email contains invalid whitespace or domain syntax.")

    return normalized


def parse_salary(value: Any) -> Decimal:
    """Parse salary as Decimal to avoid binary floating-point money errors."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise DataQualityError("Salary must be a valid decimal amount.") from None

    if not amount.is_finite():
        raise DataQualityError("Salary must be finite.")

    if amount < 0:
        raise DataQualityError("Salary cannot be negative.")

    if amount.as_tuple().exponent < -2:
        raise DataQualityError("Salary cannot have more than two decimal places.")

    return amount.quantize(Decimal("0.01"))


def validate_employee(employee: Employee) -> Employee:
    """Apply business rules that require clear application-level feedback."""
    code = employee.employee_code.strip().upper()
    name = employee.full_name.strip()
    department = employee.department.strip()

    if not code or len(code) > 20:
        raise DataQualityError("Employee code must contain 1 to 20 characters.")

    if not name or len(name) > 100:
        raise DataQualityError("Full name must contain 1 to 100 characters.")

    if not isinstance(employee.age, int) or isinstance(employee.age, bool):
        raise DataQualityError("Age must be an integer.")

    if not 18 <= employee.age <= 100:
        raise DataQualityError("Employee age must be between 18 and 100.")

    if not department or len(department) > 50:
        raise DataQualityError("Department must contain 1 to 50 characters.")

    if not isinstance(employee.active, bool):
        raise DataQualityError("Active status must be a Boolean.")

    return Employee(
        employee_code=code,
        email=normalize_email(employee.email),
        full_name=name,
        age=employee.age,
        salary=parse_salary(employee.salary),
        department=department,
        active=employee.active,
    )


def connect_database(database: str = ":memory:") -> sqlite3.Connection:
    """Configure SQLite so foreign keys and CHECK constraints are enforced."""
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA ignore_check_constraints = OFF")
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    """Create relational tables with independent integrity responsibilities."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS departments (
            department_name TEXT PRIMARY KEY,
            annual_budget NUMERIC NOT NULL
                CHECK (
                    typeof(annual_budget) IN ('integer', 'real')
                    AND annual_budget >= 0
                )
        );

        CREATE TABLE IF NOT EXISTS employees (
            employee_id INTEGER PRIMARY KEY,
            employee_code TEXT NOT NULL UNIQUE
                CHECK (
                    length(trim(employee_code)) BETWEEN 1 AND 20
                ),
            email TEXT NOT NULL UNIQUE
                CHECK (
                    length(trim(email)) > 0
                    AND instr(email, '@') > 1
                ),
            full_name TEXT NOT NULL
                CHECK (length(trim(full_name)) BETWEEN 1 AND 100),
            age INTEGER NOT NULL
                CHECK (age BETWEEN 18 AND 100),
            salary NUMERIC NOT NULL
                CHECK (
                    typeof(salary) IN ('integer', 'real')
                    AND salary >= 0
                ),
            department_name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
                CHECK (active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_name)
                REFERENCES departments(department_name)
        );

        CREATE INDEX IF NOT EXISTS idx_employees_department_active
            ON employees(department_name, active);

        CREATE TABLE IF NOT EXISTS quality_audit (
            audit_id INTEGER PRIMARY KEY,
            employee_code TEXT,
            attempted_value TEXT NOT NULL,
            rule_name TEXT NOT NULL,
            error_message TEXT NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def seed_departments(connection: sqlite3.Connection) -> None:
    departments = [
        ("Engineering", Decimal("250000.00")),
        ("Finance", Decimal("150000.00")),
        ("Operations", Decimal("200000.00")),
    ]

    with connection:
        connection.executemany(
            """
            INSERT INTO departments(department_name, annual_budget)
            VALUES (?, ?)
            ON CONFLICT(department_name) DO NOTHING
            """,
            [(name, str(budget)) for name, budget in departments],
        )


def insert_employee(
    connection: sqlite3.Connection,
    employee: Employee,
) -> int:
    """Validate the record and rely on database constraints as the final guard."""
    valid = validate_employee(employee)

    with connection:
        cursor = connection.execute(
            """
            INSERT INTO employees (
                employee_code,
                email,
                full_name,
                age,
                salary,
                department_name,
                active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                valid.employee_code,
                valid.email,
                valid.full_name,
                valid.age,
                str(valid.salary),
                valid.department,
                int(valid.active),
            ),
        )

    return int(cursor.lastrowid)


def update_salary(
    connection: sqlite3.Connection,
    employee_code: str,
    new_salary: Any,
) -> None:
    """Update a salary without allowing negative or malformed amounts."""
    salary = parse_salary(new_salary)

    with connection:
        cursor = connection.execute(
            """
            UPDATE employees
            SET salary = ?
            WHERE employee_code = ?
            """,
            (str(salary), employee_code.strip().upper()),
        )

        if cursor.rowcount != 1:
            raise DataQualityError(
                f"Employee {employee_code!r} does not exist."
            )


def try_insert_invalid(
    connection: sqlite3.Connection,
    employee: Employee,
    rule_name: str,
) -> None:
    """Record a failed attempt without leaving a partial employee row."""
    try:
        insert_employee(connection, employee)
    except (DataQualityError, sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
        message = str(exc)
        print(f"Rejected [{rule_name}]: {message}")

        with connection:
            connection.execute(
                """
                INSERT INTO quality_audit (
                    employee_code,
                    attempted_value,
                    rule_name,
                    error_message
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    employee.employee_code,
                    employee.email,
                    rule_name,
                    message,
                ),
            )
    else:
        print(f"Unexpectedly accepted [{rule_name}].")


def demonstrate_constraint_failures(
    connection: sqlite3.Connection,
) -> None:
    print("\nConstraint and business-rule failures")

    invalid_records = [
        (
            Employee("E-101", "duplicate@example.com", "Duplicate Code", 30,
                     "60000.00", "Engineering"),
            "UNIQUE employee_code",
        ),
        (
            Employee("E-104", "alice@company.com", "Duplicate Email", 31,
                     "61000.00", "Engineering"),
            "UNIQUE email",
        ),
        (
            Employee("E-105", "badage@example.com", "Underage Employee", 16,
                     "40000.00", "Finance"),
            "CHECK age range",
        ),
        (
            Employee("E-106", "negative@example.com", "Negative Salary", 28,
                     "-500.00", "Finance"),
            "CHECK salary nonnegative",
        ),
        (
            Employee("E-107", "missingdept@example.com", "Unknown Department", 29,
                     "50000.00", "Legal"),
            "FOREIGN KEY department",
        ),
        (
            Employee("E-108", "invalid@example.com", "Missing Email", 27,
                     "45000.00", "Finance"),
            "Email structure",
        ),
    ]

    for employee, rule_name in invalid_records:
        try_insert_invalid(connection, employee, rule_name)

    # Application validation normally catches blank names before SQL executes.
    # This direct SQL attempt proves the database independently enforces NOT NULL.
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO employees (
                    employee_code, email, full_name, age,
                    salary, department_name, active
                )
                VALUES (?, ?, NULL, ?, ?, ?, ?)
                """,
                ("E-109", "nullname@example.com", 30, 50000, "Finance", 1),
            )
    except sqlite3.IntegrityError as exc:
        print(f"Rejected [NOT NULL full_name]: {exc}")


def demonstrate_unique_null_semantics(
    connection: sqlite3.Connection,
) -> None:
    """Show why NOT NULL is needed alongside UNIQUE for mandatory identifiers."""
    connection.execute(
        """
        CREATE TEMP TABLE unique_null_demo (
            optional_identifier TEXT UNIQUE
        )
        """
    )

    with connection:
        connection.execute(
            "INSERT INTO unique_null_demo(optional_identifier) VALUES (NULL)"
        )
        connection.execute(
            "INSERT INTO unique_null_demo(optional_identifier) VALUES (NULL)"
        )

    count = connection.execute(
        "SELECT COUNT(*) FROM unique_null_demo"
    ).fetchone()[0]

    print(
        "\nSQLite permits multiple NULL values in a UNIQUE column; "
        f"the demonstration table contains {count} rows."
    )
    print("Mandatory unique identifiers should normally use both UNIQUE and NOT NULL.")


def run_quality_report(connection: sqlite3.Connection) -> None:
    print("\nEmployee data-quality report")

    rows = connection.execute(
        """
        SELECT
            department_name,
            COUNT(*) AS employee_count,
            SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) AS active_count,
            MIN(salary) AS minimum_salary,
            MAX(salary) AS maximum_salary,
            ROUND(AVG(salary), 2) AS average_salary
        FROM employees
        GROUP BY department_name
        ORDER BY department_name
        """
    ).fetchall()

    for row in rows:
        print(
            f"{row['department_name']}: employees={row['employee_count']}, "
            f"active={row['active_count']}, "
            f"minimum_salary={row['minimum_salary']}, "
            f"maximum_salary={row['maximum_salary']}, "
            f"average_salary={row['average_salary']}"
        )

    audit_count = connection.execute(
        "SELECT COUNT(*) FROM quality_audit"
    ).fetchone()[0]

    print(f"Recorded validation failures: {audit_count}")


def demonstrate_transaction_rollback(
    connection: sqlite3.Connection,
) -> None:
    print("\nTransaction rollback")

    initial_count = connection.execute(
        "SELECT COUNT(*) FROM employees"
    ).fetchone()[0]

    try:
        with connection:
            connection.execute(
                """
                INSERT INTO employees (
                    employee_code, email, full_name, age,
                    salary, department_name, active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "E-900",
                    "temporary@example.com",
                    "Temporary Record",
                    30,
                    40000,
                    "Finance",
                    1,
                ),
            )

            # A duplicate code violates UNIQUE and rolls back the transaction.
            connection.execute(
                """
                INSERT INTO employees (
                    employee_code, email, full_name, age,
                    salary, department_name, active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "E-900",
                    "second@example.com",
                    "Duplicate Record",
                    30,
                    40000,
                    "Finance",
                    1,
                ),
            )
    except sqlite3.IntegrityError as exc:
        print(f"Transaction rolled back: {exc}")

    final_count = connection.execute(
        "SELECT COUNT(*) FROM employees"
    ).fetchone()[0]

    print(f"Rows before transaction: {initial_count}")
    print(f"Rows after rollback: {final_count}")
    assert initial_count == final_count


def demonstrate_atomic_salary_change(
    connection: sqlite3.Connection,
) -> None:
    print("\nAtomic salary update")

    try:
        update_salary(connection, "E-101", "72000.00")
        print("Salary update committed.")
    except DataQualityError as exc:
        print(f"Salary update rejected: {exc}")

    try:
        update_salary(connection, "E-101", "-100.00")
    except DataQualityError as exc:
        print(f"Invalid salary update rejected: {exc}")


def demonstrate_query_plan(connection: sqlite3.Connection) -> None:
    print("\nQuery plan for department and active-status lookup")

    plan = connection.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT employee_code, full_name
        FROM employees
        WHERE department_name = ? AND active = ?
        """,
        ("Engineering", 1),
    ).fetchall()

    for row in plan:
        print(row["detail"])


def main() -> None:
    # An in-memory database makes the demonstration reproducible and leaves
    # no persistent file behind.
    with connect_database() as connection:
        create_schema(connection)
        seed_departments(connection)

        employees = [
            Employee(
                "E-101",
                " Alice@Example.com ",
                "Alice Sharma",
                32,
                Decimal("65000.00"),
                "Engineering",
            ),
            Employee(
                "E-102",
                "rahul@example.com",
                "Rahul Verma",
                41,
                Decimal("82000.00"),
                "Finance",
            ),
            Employee(
                "E-103",
                "meera@example.com",
                "Meera Singh",
                27,
                Decimal("54000.00"),
                "Operations",
                active=False,
            ),
        ]

        print("Valid employee inserts")

        for employee in employees:
            employee_id = insert_employee(connection, employee)
            print(f"Inserted {employee.employee_code} with ID {employee_id}")

        demonstrate_constraint_failures(connection)
        demonstrate_unique_null_semantics(connection)
        demonstrate_atomic_salary_change(connection)
        run_quality_report(connection)
        demonstrate_transaction_rollback(connection)
        demonstrate_query_plan(connection)

        print("\nFinal employee records")

        for row in connection.execute(
            """
            SELECT employee_code, email, full_name, age, salary,
                   department_name, active
            FROM employees
            ORDER BY employee_code
            """
        ):
            print(dict(row))

        print("\nDemonstration completed successfully.")


if __name__ == "__main__":
    main()
