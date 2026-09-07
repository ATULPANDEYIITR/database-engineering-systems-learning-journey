"""
DATABASE SCHEMAS
================

A comprehensive, self-contained study script covering database schemas from
absolute beginner concepts through advanced logical organization.

Topics covered:
- Schema fundamentals
- Databases versus schemas
- Namespaces
- Database objects
- Logical organization
- Tables, columns, rows, and constraints
- Keys and relationships
- Schema qualification
- Multiple schemas
- DDL operations
- Views, indexes, sequences, functions, and triggers
- Object dependencies
- Permissions and ownership
- Schema design
- Normalization
- Denormalization trade-offs
- Multi-tenant organization
- Versioning and migrations
- Validation and error handling
- Security considerations
- Performance considerations
- Production design
- SQLite demonstrations of schema-related concepts

This script uses only Python's standard library. SQLite is used because the
sqlite3 module is included with standard Python installations.

Important SQLite note:
SQLite does not implement schemas and namespaces in the same way as systems
such as PostgreSQL, SQL Server, Oracle, or MySQL. SQLite supports attached
databases and catalog-like namespaces, which can demonstrate some namespace
concepts, but its logical organization differs from enterprise RDBMS products.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# =============================================================================
# 1. FUNDAMENTAL DEFINITIONS
# =============================================================================

"""
DATABASE:
A database is an organized collection of data and database objects.

DATABASE SCHEMA:
A schema is a logical definition and organizational structure describing how
database objects are arranged.

The word "schema" has multiple related meanings:

1. Logical schema:
   The structure of tables, columns, relationships, constraints, and objects.

2. Namespace schema:
   A named container used to group database objects.

3. Physical schema:
   Information about physical storage structures, indexes, partitions, and
   storage organization.

In many enterprise relational database systems, a schema acts as a namespace:

    database.schema.object

Examples:

    company.sales.orders
    company.hr.employees
    company.audit.event_log

Not every database product uses these exact levels.
"""


def print_section(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


print_section("1. DATABASE, SCHEMA, AND NAMESPACE FUNDAMENTALS")

database_name = "company"
schema_name = "sales"
object_name = "orders"

fully_qualified_name = f"{database_name}.{schema_name}.{object_name}"

print("Database:", database_name)
print("Schema:", schema_name)
print("Object:", object_name)
print("Fully qualified object name:", fully_qualified_name)


# =============================================================================
# 2. DATABASE VERSUS SCHEMA
# =============================================================================

"""
DATABASE AND SCHEMA ARE NOT ALWAYS THE SAME THING.

A database often represents a larger administrative unit.

A schema usually represents a logical grouping or namespace inside a database.

Example:

    DATABASE: company_db

        SCHEMA: sales
            TABLE: orders
            TABLE: customers
            VIEW: monthly_revenue

        SCHEMA: hr
            TABLE: employees
            TABLE: departments

        SCHEMA: audit
            TABLE: login_events
            TABLE: data_changes

Different database systems implement this hierarchy differently.

PostgreSQL commonly supports:

    database -> schema -> object

SQL Server commonly supports:

    server -> database -> schema -> object

MySQL commonly treats "database" and "schema" as closely related terms.

Oracle historically associates schemas strongly with database users.

SQLite has a much simpler model and does not provide independent SQL schemas
like PostgreSQL.
"""


print_section("2. DATABASE VERSUS SCHEMA")

database_structure = {
    "company_db": {
        "sales": ["customers", "orders", "order_items"],
        "hr": ["employees", "departments"],
        "audit": ["events"],
    }
}

for database, schemas in database_structure.items():
    print(f"Database: {database}")
    for schema, objects in schemas.items():
        print(f"  Schema: {schema}")
        for obj in objects:
            print(f"    Object: {obj}")


# =============================================================================
# 3. NAMESPACES
# =============================================================================

"""
A NAMESPACE is a naming boundary.

Without namespaces, every object name might need to be globally unique:

    employees
    customers
    orders

With namespaces, different schemas can contain objects with identical names:

    hr.employees
    sales.employees

These names refer to different objects.

Namespaces reduce naming conflicts and improve logical organization.
"""


print_section("3. NAMESPACE CONCEPTS")


@dataclass
class DatabaseObject:
    """A simplified representation of a database object."""

    name: str
    object_type: str
    definition: str = ""


@dataclass
class SchemaNamespace:
    """
    A simplified schema namespace.

    Real database systems store metadata internally. This class demonstrates
    the namespace principle without implementing a complete database engine.
    """

    name: str
    objects: Dict[str, DatabaseObject] = field(default_factory=dict)

    def create_object(self, obj: DatabaseObject) -> None:
        """Create an object while preventing duplicate names in one namespace."""
        if obj.name in self.objects:
            raise ValueError(
                f"Object '{obj.name}' already exists in schema '{self.name}'."
            )

        self.objects[obj.name] = obj

    def get_object(self, object_name: str) -> DatabaseObject:
        """Resolve an object name within this namespace."""
        if object_name not in self.objects:
            raise KeyError(
                f"Object '{object_name}' does not exist in schema '{self.name}'."
            )

        return self.objects[object_name]


hr_schema = SchemaNamespace("hr")
sales_schema = SchemaNamespace("sales")

# The same object name can exist in different namespaces.
hr_schema.create_object(DatabaseObject("employees", "TABLE"))
sales_schema.create_object(DatabaseObject("employees", "TABLE"))

print("hr.employees ->", hr_schema.get_object("employees"))
print("sales.employees ->", sales_schema.get_object("employees"))


# =============================================================================
# 4. DATABASE OBJECTS
# =============================================================================

"""
A schema can contain many types of database objects.

Common object types include:

TABLE
    Stores structured rows.

VIEW
    A named query that behaves like a virtual table.

MATERIALIZED VIEW
    Stores results physically in systems that support it.

INDEX
    Accelerates certain data retrieval operations.

SEQUENCE
    Generates numeric values in systems that support sequences.

FUNCTION
    Encapsulates reusable logic and returns a value.

PROCEDURE
    Encapsulates database-side operations.

TRIGGER
    Executes automatically when defined database events occur.

TYPE
    Defines a reusable data type in systems supporting custom types.

CONSTRAINT
    Enforces rules such as uniqueness and referential integrity.

Some objects are directly stored inside schemas, while the exact relationship
between object types and schemas depends on the database product.
"""


print_section("4. COMMON DATABASE OBJECTS")

object_types = [
    "TABLE",
    "VIEW",
    "MATERIALIZED VIEW",
    "INDEX",
    "SEQUENCE",
    "FUNCTION",
    "PROCEDURE",
    "TRIGGER",
    "TYPE",
    "CONSTRAINT",
]

for object_type in object_types:
    print("-", object_type)


# =============================================================================
# 5. TABLE FUNDAMENTALS
# =============================================================================

"""
A TABLE is usually the primary relational data structure.

Example conceptual table:

employees

    employee_id | full_name      | department_id
    ------------+----------------+--------------
    1           | Asha Sharma    | 10
    2           | Ravi Kumar     | 20

A table consists of:

- Table name
- Columns
- Data types
- Rows
- Constraints
- Relationships
- Optional indexes
"""


print_section("5. TABLES, COLUMNS, AND ROWS")


@dataclass
class ColumnDefinition:
    """Simplified logical representation of a table column."""

    name: str
    data_type: str
    nullable: bool = True
    default_value: Optional[Any] = None


employee_columns = [
    ColumnDefinition("employee_id", "INTEGER", nullable=False),
    ColumnDefinition("full_name", "TEXT", nullable=False),
    ColumnDefinition("email", "TEXT", nullable=False),
    ColumnDefinition("department_id", "INTEGER", nullable=True),
]

for column in employee_columns:
    print(
        f"Column: {column.name}, "
        f"Type: {column.data_type}, "
        f"Nullable: {column.nullable}"
    )


# =============================================================================
# 6. DATA TYPES
# =============================================================================

"""
Data types define what kind of values a column can store.

Common relational categories:

INTEGER
    Whole numbers.

DECIMAL / NUMERIC
    Exact decimal values, often preferred for financial data.

REAL / FLOAT / DOUBLE
    Approximate floating-point values.

TEXT / VARCHAR / CHAR
    Character data.

BOOLEAN
    Logical true/false values.

DATE
    Calendar dates.

TIME
    Times of day.

TIMESTAMP
    Date and time.

BLOB / BINARY
    Binary data.

JSON
    Structured document-like values in systems supporting JSON.

The available types and exact behavior differ between database products.

SQLite uses dynamic typing and type affinity, making its behavior different
from strongly typed systems such as PostgreSQL.
"""


print_section("6. DATA TYPE PRINCIPLES")

sample_values = {
    "INTEGER": 42,
    "TEXT": "Database schema",
    "REAL": 3.14159,
    "BOOLEAN_CONCEPT": True,
    "BLOB_CONCEPT": b"\x00\x01\x02",
}

for type_name, value in sample_values.items():
    print(f"{type_name}: {value!r}")


# =============================================================================
# 7. KEYS AND CONSTRAINTS
# =============================================================================

"""
CONSTRAINTS enforce data rules.

PRIMARY KEY:
Uniquely identifies a row.

FOREIGN KEY:
References a row in another table.

UNIQUE:
Prevents duplicate values.

NOT NULL:
Requires a value.

CHECK:
Requires a logical condition.

DEFAULT:
Provides a value when none is supplied.

Example:

CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    salary NUMERIC CHECK (salary >= 0)
);

Constraints are part of schema design because they define valid data.
"""


print_section("7. KEYS AND CONSTRAINTS")

connection = sqlite3.connect(":memory:")
connection.execute("PRAGMA foreign_keys = ON")

connection.executescript(
    """
    CREATE TABLE departments (
        department_id INTEGER PRIMARY KEY,
        department_name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE employees (
        employee_id INTEGER PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        salary REAL NOT NULL CHECK (salary >= 0),
        department_id INTEGER,
        FOREIGN KEY (department_id)
            REFERENCES departments(department_id)
    );
    """
)

connection.execute(
    "INSERT INTO departments (department_id, department_name) VALUES (?, ?)",
    (10, "Engineering"),
)

connection.execute(
    """
    INSERT INTO employees
    (employee_id, full_name, email, salary, department_id)
    VALUES (?, ?, ?, ?, ?)
    """,
    (1, "Asha Sharma", "asha@example.com", 75000, 10),
)

employee = connection.execute(
    "SELECT employee_id, full_name, email, salary, department_id FROM employees"
).fetchone()

print("Valid employee row:", employee)


# Demonstrate a CHECK constraint failure.
try:
    connection.execute(
        """
        INSERT INTO employees
        (employee_id, full_name, email, salary, department_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (2, "Invalid Salary", "invalid@example.com", -100, 10),
    )
except sqlite3.IntegrityError as error:
    print("CHECK constraint prevented invalid data:", error)


# Demonstrate a UNIQUE constraint failure.
try:
    connection.execute(
        """
        INSERT INTO employees
        (employee_id, full_name, email, salary, department_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (3, "Duplicate Email", "asha@example.com", 50000, 10),
    )
except sqlite3.IntegrityError as error:
    print("UNIQUE constraint prevented duplicate data:", error)


# Demonstrate a foreign key failure.
try:
    connection.execute(
        """
        INSERT INTO employees
        (employee_id, full_name, email, salary, department_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (4, "Unknown Department", "unknown@example.com", 50000, 999),
    )
except sqlite3.IntegrityError as error:
    print("FOREIGN KEY constraint prevented invalid relationship:", error)


# =============================================================================
# 8. PRIMARY KEYS
# =============================================================================

"""
A PRIMARY KEY identifies each row uniquely.

Properties usually include:

- Uniqueness
- Non-nullability
- Stable identity

Common primary key strategies:

1. Natural key
   A real-world value such as a country code.

2. Surrogate key
   A generated identifier such as:

       employee_id = 1042

3. UUID
   A globally unique identifier useful in distributed systems.

Trade-off:

Natural keys have business meaning but can change.

Surrogate keys are stable but require additional uniqueness constraints for
business identifiers.
"""


print_section("8. PRIMARY KEY STRATEGIES")

natural_key_example = {"country_code": "IN", "country_name": "India"}
surrogate_key_example = {
    "customer_id": 1001,
    "email": "customer@example.com",
}

print("Natural key example:", natural_key_example)
print("Surrogate key example:", surrogate_key_example)


# =============================================================================
# 9. FOREIGN KEYS AND RELATIONSHIPS
# =============================================================================

"""
Relationships connect tables.

ONE-TO-ONE:

    users
        |
        | 1 : 1
        |
    user_profiles

ONE-TO-MANY:

    departments
        |
        | 1 : many
        |
    employees

MANY-TO-MANY:

    students
        |
        | many : many
        |
    courses

A relational database represents many-to-many relationships using an
intermediate junction table:

    student_courses

        student_id
        course_id
"""


print_section("9. RELATIONSHIPS")

connection.executescript(
    """
    CREATE TABLE students (
        student_id INTEGER PRIMARY KEY,
        student_name TEXT NOT NULL
    );

    CREATE TABLE courses (
        course_id INTEGER PRIMARY KEY,
        course_name TEXT NOT NULL
    );

    CREATE TABLE student_courses (
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,

        PRIMARY KEY (student_id, course_id),

        FOREIGN KEY (student_id)
            REFERENCES students(student_id),

        FOREIGN KEY (course_id)
            REFERENCES courses(course_id)
    );
    """
)

connection.executemany(
    "INSERT INTO students VALUES (?, ?)",
    [
        (1, "Anil"),
        (2, "Priya"),
    ],
)

connection.executemany(
    "INSERT INTO courses VALUES (?, ?)",
    [
        (101, "Database Systems"),
        (102, "Python Programming"),
    ],
)

connection.executemany(
    "INSERT INTO student_courses VALUES (?, ?)",
    [
        (1, 101),
        (1, 102),
        (2, 101),
    ],
)

rows = connection.execute(
    """
    SELECT
        students.student_name,
        courses.course_name
    FROM student_courses
    JOIN students
        ON students.student_id = student_courses.student_id
    JOIN courses
        ON courses.course_id = student_courses.course_id
    ORDER BY students.student_name, courses.course_name
    """
).fetchall()

for row in rows:
    print("Relationship:", row)


# =============================================================================
# 10. LOGICAL ORGANIZATION
# =============================================================================

"""
Logical organization determines how database objects are grouped according to
business meaning and technical responsibility.

A database might be organized by:

1. Business domain
   sales
   hr
   finance
   inventory

2. Application layer
   application
   reporting
   audit

3. Security boundary
   public
   internal
   confidential

4. Lifecycle
   staging
   production
   archive

5. Data architecture layer
   raw
   staging
   curated
   analytics

A good schema structure should balance:

- Discoverability
- Security
- Ownership
- Dependency management
- Operational simplicity
- Future growth
"""


print_section("10. LOGICAL ORGANIZATION")

logical_domains = {
    "sales": [
        "customers",
        "orders",
        "order_items",
        "sales_summary",
    ],
    "inventory": [
        "products",
        "warehouses",
        "stock_levels",
    ],
    "finance": [
        "invoices",
        "payments",
        "ledger_entries",
    ],
    "audit": [
        "login_events",
        "change_events",
    ],
}

for domain, objects in logical_domains.items():
    print(f"\nSchema/domain: {domain}")
    for obj in objects:
        print(f"  - {obj}")


# =============================================================================
# 11. FULLY QUALIFIED NAMES
# =============================================================================

"""
A fully qualified name specifies enough namespace information to identify an
object.

Possible forms:

    table
    schema.table
    database.schema.table
    server.database.schema.table

Examples depend on the database product.

Using explicit schema qualification can reduce ambiguity.

Example:

    SELECT * FROM sales.orders;

Potential benefits:

- Clear dependencies
- Fewer naming conflicts
- Better readability in multi-schema databases

Potential trade-off:

Hard-coded database names can reduce portability between environments.
"""


print_section("11. FULLY QUALIFIED NAME RESOLUTION")


@dataclass
class LogicalDatabase:
    """Simplified database containing multiple schema namespaces."""

    name: str
    schemas: Dict[str, SchemaNamespace] = field(default_factory=dict)

    def create_schema(self, schema_name: str) -> SchemaNamespace:
        """Create a schema namespace."""
        if schema_name in self.schemas:
            raise ValueError(f"Schema '{schema_name}' already exists.")

        schema = SchemaNamespace(schema_name)
        self.schemas[schema_name] = schema
        return schema

    def resolve(self, schema_name: str, object_name: str) -> DatabaseObject:
        """Resolve schema.object."""
        if schema_name not in self.schemas:
            raise KeyError(f"Schema '{schema_name}' does not exist.")

        return self.schemas[schema_name].get_object(object_name)


company_database = LogicalDatabase("company")

sales = company_database.create_schema("sales")
hr = company_database.create_schema("hr")

sales.create_object(DatabaseObject("orders", "TABLE"))
hr.create_object(DatabaseObject("employees", "TABLE"))

resolved_object = company_database.resolve("sales", "orders")
print("Resolved company.sales.orders ->", resolved_object)


# =============================================================================
# 12. SEARCH PATH CONCEPT
# =============================================================================

"""
Some databases support a search path.

A search path is an ordered list of schemas used to resolve unqualified names.

Example conceptual search path:

    ["sales", "public"]

If the query references:

    orders

The database may search:

    sales.orders
    public.orders

Search paths are convenient but can create ambiguity.

Security consideration:
Untrusted schemas should generally not appear in a privileged search path,
because object-name resolution can potentially select an unexpected object.
"""


print_section("12. SEARCH PATH SIMULATION")


def resolve_unqualified_name(
    database: LogicalDatabase,
    search_path: List[str],
    object_name: str,
) -> Tuple[str, DatabaseObject]:
    """
    Resolve an unqualified object using schema search order.

    Raises KeyError if no matching object exists.
    """
    for schema_name in search_path:
        schema = database.schemas.get(schema_name)

        if schema and object_name in schema.objects:
            return schema_name, schema.objects[object_name]

    raise KeyError(
        f"Object '{object_name}' was not found in search path {search_path}."
    )


public_schema = company_database.create_schema("public")
public_schema.create_object(DatabaseObject("orders", "VIEW"))

search_path = ["sales", "public"]

resolved_schema, resolved = resolve_unqualified_name(
    company_database,
    search_path,
    "orders",
)

print(
    f"Unqualified name 'orders' resolved to "
    f"'{resolved_schema}.{resolved.name}' ({resolved.object_type})"
)


# =============================================================================
# 13. DATA DEFINITION LANGUAGE (DDL)
# =============================================================================

"""
DDL defines database structures.

Common DDL operations:

CREATE
    Creates objects.

ALTER
    Changes object definitions.

DROP
    Removes objects.

TRUNCATE
    Removes table data in systems supporting it.

Examples conceptually include:

    CREATE TABLE
    ALTER TABLE
    DROP TABLE
    CREATE INDEX
    CREATE VIEW

DDL changes are important because schema definitions are part of the
application's structural contract.
"""


print_section("13. DDL USING SQLITE")

connection.execute(
    """
    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        product_name TEXT NOT NULL,
        price REAL NOT NULL CHECK (price >= 0)
    )
    """
)

connection.execute(
    "ALTER TABLE products ADD COLUMN active INTEGER NOT NULL DEFAULT 1"
)

connection.execute(
    """
    INSERT INTO products (product_id, product_name, price)
    VALUES (?, ?, ?)
    """,
    (1, "Keyboard", 2500),
)

product_row = connection.execute(
    "SELECT product_id, product_name, price, active FROM products"
).fetchone()

print("Product after CREATE and ALTER:", product_row)


# =============================================================================
# 14. VIEWS
# =============================================================================

"""
A VIEW is a named query.

Example purpose:

Base tables:

    orders
    customers

View:

    sales.customer_order_summary

Advantages:

- Simplifies repeated queries
- Provides logical abstraction
- Can restrict exposed columns
- Helps separate internal structure from consumer-facing interfaces

Limitations:

- Some views are not directly updateable
- Complex views can introduce performance costs
- Changes to underlying objects can break dependent views
"""


print_section("14. VIEWS")

connection.executescript(
    """
    CREATE TABLE view_customers (
        customer_id INTEGER PRIMARY KEY,
        customer_name TEXT NOT NULL
    );

    CREATE TABLE view_orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        FOREIGN KEY (customer_id)
            REFERENCES view_customers(customer_id)
    );

    INSERT INTO view_customers VALUES (1, 'Asha');
    INSERT INTO view_customers VALUES (2, 'Ravi');

    INSERT INTO view_orders VALUES (100, 1, 500.0);
    INSERT INTO view_orders VALUES (101, 1, 700.0);
    INSERT INTO view_orders VALUES (102, 2, 300.0);

    CREATE VIEW customer_order_summary AS
    SELECT
        view_customers.customer_id,
        view_customers.customer_name,
        COUNT(view_orders.order_id) AS order_count,
        COALESCE(SUM(view_orders.amount), 0) AS total_amount
    FROM view_customers
    LEFT JOIN view_orders
        ON view_customers.customer_id = view_orders.customer_id
    GROUP BY
        view_customers.customer_id,
        view_customers.customer_name;
    """
)

summary_rows = connection.execute(
    "SELECT * FROM customer_order_summary ORDER BY customer_id"
).fetchall()

for row in summary_rows:
    print("View result:", row)


# =============================================================================
# 15. INDEXES
# =============================================================================

"""
An INDEX is a data structure used to accelerate certain operations.

Example:

    CREATE INDEX idx_orders_customer_id
    ON orders(customer_id);

Indexes often improve:

- Filtering
- Joining
- Sorting
- Uniqueness enforcement

Indexes also introduce costs:

- Additional storage
- Slower inserts
- Slower updates
- Slower deletes
- Maintenance overhead

An index is not automatically useful for every query.

Index design depends on:

- Query patterns
- Data distribution
- Selectivity
- Table size
- Write frequency
- Database optimizer behavior
"""


print_section("15. INDEXES")

connection.execute(
    """
    CREATE INDEX idx_view_orders_customer_id
    ON view_orders(customer_id)
    """
)

indexes = connection.execute(
    """
    SELECT name, tbl_name
    FROM sqlite_master
    WHERE type = 'index'
      AND tbl_name = 'view_orders'
    """
).fetchall()

print("Indexes on view_orders:", indexes)


# =============================================================================
# 16. SEQUENCES AND IDENTITY CONCEPTS
# =============================================================================

"""
Databases provide different strategies for generated identifiers.

Common mechanisms:

- IDENTITY columns
- AUTO_INCREMENT
- SERIAL-like abstractions
- Sequences
- UUID values

Important distinction:

A generated identifier is not necessarily a guarantee of chronological order
across distributed systems.

Gaps in generated IDs may occur because of:

- Rolled-back transactions
- Cached sequence values
- Deleted rows
- Concurrent operations

Applications should not assume that:

    max(id) == number of rows
"""


print_section("16. GENERATED IDENTIFIER CONCEPTS")

connection.execute(
    """
    CREATE TABLE generated_ids (
        id INTEGER PRIMARY KEY,
        description TEXT NOT NULL
    )
    """
)

connection.execute(
    "INSERT INTO generated_ids (description) VALUES (?)",
    ("First generated row",),
)

connection.execute(
    "INSERT INTO generated_ids (description) VALUES (?)",
    ("Second generated row",),
)

generated_rows = connection.execute(
    "SELECT id, description FROM generated_ids"
).fetchall()

print("Generated identifier rows:", generated_rows)


# =============================================================================
# 17. TRIGGERS
# =============================================================================

"""
A TRIGGER executes automatically in response to an event.

Common trigger events:

- INSERT
- UPDATE
- DELETE

Possible uses:

- Auditing
- Automatic timestamps
- Derived data
- Validation

Risks:

- Hidden side effects
- Difficult debugging
- Unexpected performance costs
- Complex dependency chains

Business logic implemented in triggers should be carefully documented because
the behavior is not always visible from application code.
"""


print_section("17. TRIGGERS")

connection.executescript(
    """
    CREATE TABLE account_balances (
        account_id INTEGER PRIMARY KEY,
        owner TEXT NOT NULL,
        balance REAL NOT NULL DEFAULT 0
    );

    CREATE TABLE balance_audit (
        audit_id INTEGER PRIMARY KEY,
        account_id INTEGER NOT NULL,
        old_balance REAL,
        new_balance REAL,
        changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TRIGGER audit_balance_update
    AFTER UPDATE OF balance ON account_balances
    FOR EACH ROW
    BEGIN
        INSERT INTO balance_audit (
            account_id,
            old_balance,
            new_balance
        )
        VALUES (
            OLD.account_id,
            OLD.balance,
            NEW.balance
        );
    END;

    INSERT INTO account_balances VALUES (1, 'Asha', 1000);
    """
)

connection.execute(
    "UPDATE account_balances SET balance = ? WHERE account_id = ?",
    (1500, 1),
)

audit_rows = connection.execute(
    """
    SELECT account_id, old_balance, new_balance
    FROM balance_audit
    """
).fetchall()

print("Trigger-generated audit rows:", audit_rows)


# =============================================================================
# 18. OBJECT DEPENDENCIES
# =============================================================================

"""
Database objects can depend on one another.

Example:

    table customers
        |
        +--> foreign key from orders
        |
        +--> view customer_summary
        |
        +--> index on customer_id

Changing or deleting a base object can affect dependent objects.

A dependency graph can be represented conceptually as:

    customers -> orders -> customer_order_view

Dependency management matters during:

- Schema migrations
- Object deletion
- Deployment
- Refactoring
"""


print_section("18. OBJECT DEPENDENCY GRAPH")


@dataclass
class DependencyGraph:
    """
    Directed graph where:
        dependency -> dependent
    """

    dependents: Dict[str, Set[str]] = field(default_factory=dict)

    def add_dependency(self, dependency: str, dependent: str) -> None:
        self.dependents.setdefault(dependency, set()).add(dependent)

    def get_dependents(self, object_name: str) -> Set[str]:
        return self.dependents.get(object_name, set())


dependencies = DependencyGraph()

dependencies.add_dependency("sales.customers", "sales.orders")
dependencies.add_dependency("sales.orders", "sales.customer_order_summary")
dependencies.add_dependency("sales.orders", "sales.idx_orders_customer")

for object_name in [
    "sales.customers",
    "sales.orders",
    "sales.customer_order_summary",
]:
    print(
        f"Dependents of {object_name}:",
        dependencies.get_dependents(object_name),
    )


# =============================================================================
# 19. NORMALIZATION
# =============================================================================

"""
NORMALIZATION organizes relational data to reduce unnecessary duplication and
improve consistency.

A simplified progression:

UNNORMALIZED:

    order_id | customer_name | customer_email | product_1 | product_2

FIRST NORMAL FORM (1NF):
Values are atomic rather than repeating groups.

SECOND NORMAL FORM (2NF):
Non-key attributes depend on the full key.

THIRD NORMAL FORM (3NF):
Non-key attributes should not depend transitively on other non-key attributes.

Example normalized design:

customers
    customer_id
    customer_name
    customer_email

orders
    order_id
    customer_id

products
    product_id
    product_name

order_items
    order_id
    product_id
    quantity

Normalization reduces anomalies:

- Insert anomalies
- Update anomalies
- Delete anomalies
"""


print_section("19. NORMALIZATION")


unnormalized_order = {
    "order_id": 1,
    "customer_name": "Asha",
    "customer_email": "asha@example.com",
    "products": [
        {"product_name": "Keyboard", "quantity": 1},
        {"product_name": "Mouse", "quantity": 2},
    ],
}

normalized_structure = {
    "customers": [
        {
            "customer_id": 1,
            "customer_name": "Asha",
            "customer_email": "asha@example.com",
        }
    ],
    "orders": [
        {
            "order_id": 1,
            "customer_id": 1,
        }
    ],
    "products": [
        {
            "product_id": 101,
            "product_name": "Keyboard",
        },
        {
            "product_id": 102,
            "product_name": "Mouse",
        },
    ],
    "order_items": [
        {
            "order_id": 1,
            "product_id": 101,
            "quantity": 1,
        },
        {
            "order_id": 1,
            "product_id": 102,
            "quantity": 2,
        },
    ],
}

print("Unnormalized structure:", unnormalized_order)
print("Normalized tables:", list(normalized_structure))


# =============================================================================
# 20. DENORMALIZATION
# =============================================================================

"""
DENORMALIZATION intentionally duplicates or precomputes data.

Example:

Instead of calculating a customer's total purchases from millions of order
records for every request, a system may store:

    customer_statistics
        customer_id
        lifetime_order_count
        lifetime_spend

Benefits:

- Faster reads
- Reduced aggregation cost
- Simpler reporting queries

Costs:

- Duplicate data
- Synchronization complexity
- Risk of stale values
- More complicated writes

Denormalization is a trade-off, not automatically an improvement.
"""


print_section("20. NORMALIZATION VERSUS DENORMALIZATION")

comparison = {
    "normalized": {
        "duplicate_data": "Low",
        "write_complexity": "Lower duplication risk",
        "read_complexity": "May require joins",
        "consistency": "Usually easier to preserve",
    },
    "denormalized": {
        "duplicate_data": "Higher",
        "write_complexity": "Synchronization required",
        "read_complexity": "Often simpler and faster",
        "consistency": "Staleness risk exists",
    },
}

for approach, properties in comparison.items():
    print(f"\n{approach.upper()}")
    for property_name, value in properties.items():
        print(f"  {property_name}: {value}")


# =============================================================================
# 21. SCHEMA DESIGN BY BUSINESS DOMAIN
# =============================================================================

"""
Schema organization should reflect meaningful boundaries.

Example:

sales schema:
    customers
    orders
    order_items

inventory schema:
    products
    stock_levels
    warehouses

finance schema:
    invoices
    payments
    ledger_entries

This organization can improve:

- Ownership clarity
- Security boundaries
- Discoverability
- Modular design

Excessive fragmentation can also create problems:

- Too many cross-schema dependencies
- Difficult joins
- More complex permissions
- Harder migrations

Schema boundaries should represent real organizational or technical boundaries,
not arbitrary naming preferences.
"""


print_section("21. DOMAIN-ORIENTED SCHEMA DESIGN")

domain_boundaries = {
    "sales": {
        "responsibility": "Customer transactions",
        "objects": ["customers", "orders", "order_items"],
    },
    "inventory": {
        "responsibility": "Product availability",
        "objects": ["products", "warehouses", "stock_levels"],
    },
    "finance": {
        "responsibility": "Financial records",
        "objects": ["invoices", "payments", "ledger_entries"],
    },
}

for schema, information in domain_boundaries.items():
    print(f"\nSchema: {schema}")
    print("Responsibility:", information["responsibility"])
    print("Objects:", ", ".join(information["objects"]))


# =============================================================================
# 22. SCHEMA OWNERSHIP AND SECURITY
# =============================================================================

"""
Schemas can support security organization.

Conceptual permissions:

    GRANT USAGE ON SCHEMA sales TO reporting_role;
    GRANT SELECT ON sales.orders TO reporting_role;

Possible separation:

application_role:
    Reads and writes operational tables.

reporting_role:
    Reads selected reporting objects.

migration_role:
    Creates and modifies schema objects.

administrator:
    Performs administrative operations.

Principle of least privilege:

Grant only the permissions required for the intended task.

Schema-level permissions alone may not be sufficient. Object-level permissions
may also be required.
"""


print_section("22. ROLE-BASED ACCESS SIMULATION")


@dataclass
class Role:
    """Simplified role representation."""

    name: str
    schema_permissions: Dict[str, Set[str]] = field(default_factory=dict)
    object_permissions: Dict[str, Set[str]] = field(default_factory=dict)

    def grant_schema(self, schema_name: str, permission: str) -> None:
        self.schema_permissions.setdefault(schema_name, set()).add(permission)

    def grant_object(self, object_name: str, permission: str) -> None:
        self.object_permissions.setdefault(object_name, set()).add(permission)

    def can_access_object(
        self,
        schema_name: str,
        object_name: str,
        permission: str,
    ) -> bool:
        """Check simplified schema and object permissions."""
        schema_allowed = permission in self.schema_permissions.get(
            schema_name,
            set(),
        )

        object_allowed = permission in self.object_permissions.get(
            object_name,
            set(),
        )

        return schema_allowed or object_allowed


reporting_role = Role("reporting_role")

reporting_role.grant_schema("reporting", "USAGE")
reporting_role.grant_object("reporting.monthly_revenue", "SELECT")

print(
    "Can reporting role SELECT reporting.monthly_revenue?",
    reporting_role.can_access_object(
        "reporting",
        "reporting.monthly_revenue",
        "SELECT",
    ),
)

print(
    "Can reporting role DELETE reporting.monthly_revenue?",
    reporting_role.can_access_object(
        "reporting",
        "reporting.monthly_revenue",
        "DELETE",
    ),
)


# =============================================================================
# 23. SQL INJECTION AND IDENTIFIER SAFETY
# =============================================================================

"""
Parameterized queries protect VALUES, but SQL parameters generally cannot be
used directly as table names, schema names, or column identifiers.

Safe:

    SELECT * FROM users WHERE email = ?

Unsafe conceptual string construction:

    f"SELECT * FROM {user_supplied_table}"

If an identifier must be dynamic:

- Prefer an allow-list.
- Validate against known schema objects.
- Use database-specific safe identifier quoting when appropriate.

Never assume that value parameterization automatically protects dynamic object
names.
"""


print_section("23. IDENTIFIER VALIDATION")


ALLOWED_TABLES = {
    "employees",
    "departments",
    "products",
}


def validate_table_name(table_name: str) -> str:
    """
    Allow only known table names.

    This demonstrates an allow-list approach for dynamic SQL identifiers.
    """
    if table_name not in ALLOWED_TABLES:
        raise ValueError(
            f"Table name '{table_name}' is not an allowed identifier."
        )

    return table_name


for candidate in [
    "employees",
    "employees; DROP TABLE departments;",
]:
    try:
        validated = validate_table_name(candidate)
        print("Allowed identifier:", validated)
    except ValueError as error:
        print("Rejected identifier:", error)


# =============================================================================
# 24. SCHEMA VERSIONING
# =============================================================================

"""
Database schemas evolve.

Example versions:

Version 1:
    users(id, name)

Version 2:
    users(id, name, email)

Version 3:
    users(id, name, email, created_at)

Schema changes should be controlled and reproducible.

A migration is an ordered structural change.

Examples:

- Create table
- Add column
- Add index
- Create view
- Backfill data
- Remove obsolete column

Production migrations should consider:

- Backward compatibility
- Transaction boundaries
- Lock duration
- Large table behavior
- Rollback strategy
- Application deployment order
"""


print_section("24. SCHEMA MIGRATION SIMULATION")


@dataclass
class SchemaMigration:
    """Represents one ordered schema migration."""

    version: int
    description: str
    sql: str


migrations = [
    SchemaMigration(
        version=1,
        description="Create application users table",
        sql="""
        CREATE TABLE application_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE
        );
        """,
    ),
    SchemaMigration(
        version=2,
        description="Add email column",
        sql="""
        ALTER TABLE application_users
        ADD COLUMN email TEXT;
        """,
    ),
    SchemaMigration(
        version=3,
        description="Create email lookup index",
        sql="""
        CREATE INDEX idx_application_users_email
        ON application_users(email);
        """,
    ),
]

migration_connection = sqlite3.connect(":memory:")

for migration in migrations:
    migration_connection.executescript(migration.sql)
    print(f"Applied migration {migration.version}: {migration.description}")

schema_objects = migration_connection.execute(
    """
    SELECT type, name
    FROM sqlite_master
    WHERE name NOT LIKE 'sqlite_%'
    ORDER BY type, name
    """
).fetchall()

print("Migrated schema objects:", schema_objects)


# =============================================================================
# 25. BACKWARD-COMPATIBLE SCHEMA CHANGES
# =============================================================================

"""
A dangerous deployment sequence can occur when application code and database
structure are incompatible.

Unsafe conceptual sequence:

1. Application version A expects column old_status.
2. Migration removes old_status.
3. Application version A is still running.
4. Queries fail.

Safer expand-contract approach:

EXPAND:
    Add new structure while retaining old structure.

MIGRATE:
    Write or copy data into the new structure.

DEPLOY:
    Update applications to use the new structure.

CONTRACT:
    Remove obsolete structure after old application versions are gone.
"""


print_section("25. EXPAND-CONTRACT DESIGN")

expand_contract_steps = [
    "1. Add new column while retaining the old column.",
    "2. Update writes so both representations remain consistent.",
    "3. Backfill historical records.",
    "4. Deploy readers that use the new representation.",
    "5. Verify no active dependency uses the old representation.",
    "6. Remove the obsolete structure.",
]

for step in expand_contract_steps:
    print(step)


# =============================================================================
# 26. MULTI-TENANT SCHEMA ORGANIZATION
# =============================================================================

"""
Multi-tenant systems serve multiple organizations.

Common organizational models:

1. Shared database, shared schema

    customers
        tenant_id
        customer_name

Advantages:
    Operational simplicity.

Risk:
    Tenant isolation must be enforced carefully.

2. Shared database, separate schemas

    tenant_a.customers
    tenant_b.customers

Advantages:
    Stronger logical separation.

Costs:
    More schema objects and migration complexity.

3. Separate database per tenant

Advantages:
    Strong isolation.

Costs:
    Higher operational overhead.

The appropriate model depends on:

- Tenant count
- Isolation requirements
- Regulatory requirements
- Operational capacity
- Scaling characteristics
"""


print_section("26. MULTI-TENANCY COMPARISON")

multi_tenant_models = {
    "shared_schema": {
        "isolation": "Logical isolation using tenant identifiers",
        "operations": "Simpler",
        "schema_count": "Low",
    },
    "schema_per_tenant": {
        "isolation": "Separate namespaces",
        "operations": "More complex",
        "schema_count": "Potentially high",
    },
    "database_per_tenant": {
        "isolation": "Strong administrative separation",
        "operations": "Highest operational overhead",
        "schema_count": "Independent per database",
    },
}

for model, properties in multi_tenant_models.items():
    print(f"\n{model}")
    for name, value in properties.items():
        print(f"  {name}: {value}")


# =============================================================================
# 27. METADATA AND SCHEMA INTROSPECTION
# =============================================================================

"""
Database systems maintain metadata describing objects.

Metadata can include:

- Tables
- Columns
- Data types
- Indexes
- Constraints
- Views
- Object definitions

This metadata supports:

- Database administration
- Code generation
- Migration tools
- Documentation
- Query optimization
- Validation

SQLite exposes schema metadata through sqlite_master and PRAGMA commands.
"""


print_section("27. SCHEMA INTROSPECTION")

table_metadata = connection.execute(
    """
    SELECT type, name
    FROM sqlite_master
    WHERE type IN ('table', 'view', 'index', 'trigger')
      AND name NOT LIKE 'sqlite_%'
    ORDER BY type, name
    """
).fetchall()

print("Schema metadata objects:")
for metadata in table_metadata:
    print(" ", metadata)

employee_column_metadata = connection.execute(
    "PRAGMA table_info(employees)"
).fetchall()

print("\nColumn metadata for employees:")
for column in employee_column_metadata:
    print(column)


# =============================================================================
# 28. LOGICAL VERSUS PHYSICAL DESIGN
# =============================================================================

"""
LOGICAL DESIGN describes:

- Entities
- Attributes
- Relationships
- Constraints
- Business meaning

PHYSICAL DESIGN describes:

- Indexes
- Storage
- Partitioning
- Tablespaces
- Compression
- Replication
- Sharding

Example:

Logical statement:

    Orders belong to customers.

Physical implementation decisions:

    - Index orders(customer_id)
    - Partition orders by date
    - Store data in a particular tablespace

The logical schema should not be confused with physical storage details.
"""


print_section("28. LOGICAL VERSUS PHYSICAL DESIGN")

logical_design = {
    "entity": "orders",
    "attributes": ["order_id", "customer_id", "created_at", "total_amount"],
    "relationship": "orders.customer_id references customers.customer_id",
}

physical_design = {
    "index": "orders(customer_id)",
    "partitioning_concept": "partition by created_at",
    "storage_concept": "database-specific storage strategy",
}

print("Logical design:", logical_design)
print("Physical design:", physical_design)


# =============================================================================
# 29. SCHEMA AND APPLICATION ARCHITECTURE
# =============================================================================

"""
Database schemas often form an important interface boundary.

Applications depend on:

- Table names
- Column names
- Data types
- Constraints
- Views
- Stored procedures

A schema change can therefore act like an API change.

Example:

Old interface:

    users.full_name

New interface:

    users.first_name
    users.last_name

Changing this without coordinating dependent applications can break production
systems.

Views can sometimes provide compatibility layers:

    legacy.users

may expose the old logical shape while internal storage changes.
"""


print_section("29. COMPATIBILITY VIEW EXAMPLE")

compatibility_connection = sqlite3.connect(":memory:")

compatibility_connection.executescript(
    """
    CREATE TABLE modern_users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL
    );

    INSERT INTO modern_users VALUES (1, 'Asha', 'Sharma');

    CREATE VIEW legacy_users AS
    SELECT
        user_id,
        first_name || ' ' || last_name AS full_name
    FROM modern_users;
    """
)

legacy_result = compatibility_connection.execute(
    "SELECT user_id, full_name FROM legacy_users"
).fetchall()

print("Compatibility view result:", legacy_result)


# =============================================================================
# 30. COMMON SCHEMA DESIGN MISTAKES
# =============================================================================

"""
COMMON MISTAKES:

1. Using ambiguous names.

    data
    info
    table1

Prefer meaningful names.

2. Storing multiple values in one relational column.

    "Python, SQL, Java"

This complicates querying and constraints.

3. Missing primary keys.

4. Missing foreign keys where referential integrity is required.

5. Using floating-point types for exact financial values when exact decimal
   semantics are required.

6. Adding indexes without analyzing query patterns.

7. Excessive indexes on write-heavy tables.

8. Treating schema changes as unimportant application changes.

9. Giving applications broad DDL permissions.

10. Depending unintentionally on search-path behavior.

11. Using reserved words or difficult identifiers.

12. Designing schemas based only on current sample data.
"""


print_section("30. COMMON DESIGN MISTAKES")

common_mistakes = [
    "Ambiguous object names",
    "Multiple values stored in one relational column",
    "Missing primary keys",
    "Missing referential constraints",
    "Inappropriate numeric data types",
    "Unnecessary indexes",
    "Unsafe schema migrations",
    "Excessive privileges",
    "Ambiguous namespace resolution",
]

for mistake in common_mistakes:
    print("-", mistake)


# =============================================================================
# 31. NAMING CONVENTIONS
# =============================================================================

"""
Consistent naming improves readability.

Possible conventions:

Schemas:
    sales
    reporting
    audit

Tables:
    customers
    order_items

Primary keys:
    customer_id
    order_id

Foreign keys:
    customer_id
    product_id

Indexes:
    idx_orders_customer_id

Unique constraints:
    uq_users_email

Check constraints:
    chk_products_price_nonnegative

The exact convention is less important than consistency and clarity.
"""


print_section("31. NAMING CONVENTIONS")

naming_examples = {
    "schema": "sales",
    "table": "order_items",
    "primary_key": "order_id",
    "foreign_key": "customer_id",
    "index": "idx_orders_customer_id",
    "unique_constraint": "uq_users_email",
    "check_constraint": "chk_products_price_nonnegative",
}

for category, example in naming_examples.items():
    print(f"{category}: {example}")


# =============================================================================
# 32. TRANSACTIONS AND SCHEMA CHANGES
# =============================================================================

"""
Some database systems allow many DDL operations inside transactions.

Conceptual example:

    BEGIN;
    ALTER TABLE ...
    CREATE INDEX ...
    COMMIT;

If an error occurs:

    ROLLBACK;

DDL transaction support differs by database product and operation.

Production migration design must account for:

- Database-specific DDL behavior
- Locks
- Transaction duration
- Rollback capability
"""


print_section("32. TRANSACTIONAL SCHEMA CHANGE EXAMPLE")

transaction_connection = sqlite3.connect(":memory:")

try:
    with transaction_connection:
        transaction_connection.execute(
            """
            CREATE TABLE transaction_example (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )

        transaction_connection.execute(
            """
            ALTER TABLE transaction_example
            ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
            """
        )

    columns = transaction_connection.execute(
        "PRAGMA table_info(transaction_example)"
    ).fetchall()

    print("Transactional schema change columns:", columns)

except sqlite3.DatabaseError as error:
    print("Schema transaction error:", error)


# =============================================================================
# 33. PERFORMANCE CONSIDERATIONS
# =============================================================================

"""
Schema design affects performance.

Important factors:

1. Index design
2. Join patterns
3. Data types
4. Table width
5. Partitioning
6. Cardinality
7. Query patterns
8. Write volume
9. Locking behavior
10. Statistics used by query optimizers

Example trade-off:

Adding indexes can improve reads but increase write cost.

A schema should be evaluated against actual workload characteristics rather
than assuming that every index improves performance.
"""


print_section("33. PERFORMANCE TRADE-OFFS")

performance_tradeoffs = [
    (
        "More indexes",
        "Potentially faster reads, slower writes and more storage",
    ),
    (
        "Highly normalized schema",
        "Less duplication, potentially more joins",
    ),
    (
        "Denormalized schema",
        "Potentially faster reads, more consistency management",
    ),
    (
        "Large text columns",
        "Flexible storage, potentially larger row sizes",
    ),
]

for choice, consequence in performance_tradeoffs:
    print(f"{choice}: {consequence}")


# =============================================================================
# 34. DEBUGGING SCHEMA PROBLEMS
# =============================================================================

"""
Common schema-related debugging questions:

- Does the table exist?
- Which schema contains the object?
- Is the application using the intended search path?
- Is a view invalid or outdated?
- Does the required column exist?
- Is a migration applied?
- Is an index present?
- Is a foreign key enabled and enforced?
- Are permissions sufficient?
- Is a dependency broken?

Schema introspection is often the first debugging step.
"""


print_section("34. SCHEMA DEBUGGING HELPERS")


def object_exists(
    db_connection: sqlite3.Connection,
    object_name: str,
) -> bool:
    """Check whether a SQLite schema object exists."""
    row = db_connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE name = ?
        LIMIT 1
        """,
        (object_name,),
    ).fetchone()

    return row is not None


for name in [
    "employees",
    "customer_order_summary",
    "missing_table",
]:
    print(f"Object '{name}' exists?", object_exists(connection, name))


# =============================================================================
# 35. VALIDATING EXPECTED SCHEMA
# =============================================================================

"""
Production applications can validate critical schema assumptions.

Example checks:

- Required table exists.
- Required columns exist.
- Required indexes exist.

This can detect deployment problems early.

Validation should be carefully designed because querying metadata during every
request would add unnecessary overhead.
"""


print_section("35. SCHEMA VALIDATION")


def get_sqlite_columns(
    db_connection: sqlite3.Connection,
    table_name: str,
) -> Set[str]:
    """Return column names from SQLite table metadata."""
    rows = db_connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {row[1] for row in rows}


def validate_required_columns(
    db_connection: sqlite3.Connection,
    table_name: str,
    required_columns: Set[str],
) -> None:
    """
    Validate that a table contains all required columns.

    The table name is controlled by program code in this demonstration.
    In dynamic production code, identifier validation is required.
    """
    actual_columns = get_sqlite_columns(db_connection, table_name)

    missing_columns = required_columns - actual_columns

    if missing_columns:
        raise ValueError(
            f"Table '{table_name}' is missing columns: "
            f"{sorted(missing_columns)}"
        )

    print(
        f"Schema validation passed for '{table_name}'. "
        f"Required columns are present."
    )


validate_required_columns(
    connection,
    "employees",
    {
        "employee_id",
        "full_name",
        "email",
        "salary",
    },
)

try:
    validate_required_columns(
        connection,
        "employees",
        {
            "employee_id",
            "nonexistent_column",
        },
    )
except ValueError as error:
    print("Expected schema validation error:", error)


# =============================================================================
# 36. STAGING AND ANALYTICS SCHEMAS
# =============================================================================

"""
Data systems often organize schemas by processing stage.

Example:

raw
    Data as received from source systems.

staging
    Cleaned or transformed intermediate data.

core
    Stable business entities.

analytics
    Reporting-oriented tables and views.

This pattern helps distinguish:

- Source data
- Temporary transformation state
- Authoritative data
- Analytical outputs

The correct boundary depends on the architecture.
"""


print_section("36. DATA PIPELINE ORGANIZATION")

data_pipeline = {
    "raw": [
        "raw_customer_events",
        "raw_orders",
    ],
    "staging": [
        "stg_customer_events",
        "stg_orders",
    ],
    "core": [
        "customers",
        "orders",
    ],
    "analytics": [
        "daily_sales",
        "customer_metrics",
    ],
}

for schema, objects in data_pipeline.items():
    print(f"\n{schema.upper()} SCHEMA")
    for obj in objects:
        print("  ", obj)


# =============================================================================
# 37. ARCHIVAL ORGANIZATION
# =============================================================================

"""
Historical data can be organized separately.

Possible strategies:

1. Archive schema

    archive.orders_2020

2. Partitioning

    orders partitioned by date

3. Separate archive database

The best choice depends on:

- Query frequency
- Retention requirements
- Regulatory requirements
- Storage costs
- Operational complexity

Moving data into an archive schema changes logical organization but does not
automatically solve every performance problem.
"""


print_section("37. ACTIVE VERSUS ARCHIVED ORGANIZATION")

data_lifecycle = {
    "operational": [
        "current_orders",
        "active_customers",
    ],
    "archive": [
        "historical_orders",
        "inactive_customers",
    ],
}

for lifecycle_stage, objects in data_lifecycle.items():
    print(f"{lifecycle_stage}: {', '.join(objects)}")


# =============================================================================
# 38. CROSS-SCHEMA DEPENDENCIES
# =============================================================================

"""
Cross-schema references are useful but create coupling.

Example:

sales.orders
    references
inventory.products

This creates a dependency between the sales and inventory domains.

Questions to consider:

- Which team owns each schema?
- Can migrations be coordinated?
- Does one domain require direct access to another domain's internals?
- Should a stable view or interface be exposed instead?

Excessive cross-schema coupling can make a database difficult to evolve.
"""


print_section("38. CROSS-SCHEMA COUPLING")

cross_schema_dependencies = {
    "sales.orders": ["inventory.products", "sales.customers"],
    "finance.invoices": ["sales.orders"],
    "reporting.monthly_revenue": [
        "sales.orders",
        "finance.payments",
    ],
}

for dependent, dependencies_list in cross_schema_dependencies.items():
    print(f"{dependent} depends on:")
    for dependency in dependencies_list:
        print("  ->", dependency)


# =============================================================================
# 39. SQLITE NAMESPACE DIFFERENCES
# =============================================================================

"""
SQLite differs from multi-schema enterprise databases.

SQLite commonly has:

main
    The primary database.

temp
    Temporary objects.

Attached databases
    Additional database files referenced by names.

An attached database can be addressed conceptually as:

    attached_database.table_name

This is not identical to a PostgreSQL schema namespace.

Database portability requires understanding these differences.
"""


print_section("39. SQLITE ATTACHED DATABASE NAMESPACE")

sqlite_namespace_connection = sqlite3.connect(":memory:")

sqlite_namespace_connection.execute(
    """
    CREATE TABLE main_table (
        id INTEGER PRIMARY KEY,
        value TEXT
    )
    """
)

sqlite_namespace_connection.execute(
    "ATTACH DATABASE ':memory:' AS secondary"
)

sqlite_namespace_connection.execute(
    """
    CREATE TABLE secondary.secondary_table (
        id INTEGER PRIMARY KEY,
        value TEXT
    )
    """
)

sqlite_namespace_connection.execute(
    "INSERT INTO main_table VALUES (?, ?)",
    (1, "main namespace"),
)

sqlite_namespace_connection.execute(
    "INSERT INTO secondary.secondary_table VALUES (?, ?)",
    (1, "secondary namespace"),
)

main_value = sqlite_namespace_connection.execute(
    "SELECT value FROM main_table"
).fetchone()

secondary_value = sqlite_namespace_connection.execute(
    "SELECT value FROM secondary.secondary_table"
).fetchone()

print("main_table:", main_value)
print("secondary.secondary_table:", secondary_value)


# =============================================================================
# 40. PRODUCTION SCHEMA CHECKLIST
# =============================================================================

"""
A production-oriented schema design should consider:

STRUCTURE
- Clear schema boundaries
- Meaningful names
- Stable identifiers

INTEGRITY
- Primary keys
- Foreign keys
- Appropriate constraints

SECURITY
- Least privilege
- Controlled schema ownership
- Restricted DDL permissions
- Safe identifier handling

PERFORMANCE
- Workload-driven indexes
- Appropriate data types
- Query analysis

EVOLUTION
- Version-controlled migrations
- Backward-compatible deployment strategy
- Dependency awareness

OPERATIONS
- Backup strategy
- Monitoring
- Documentation
- Migration verification
"""


print_section("40. PRODUCTION SCHEMA CHECKLIST")

production_checklist = {
    "structure": [
        "Use meaningful object names",
        "Define logical schema boundaries",
        "Document ownership",
    ],
    "integrity": [
        "Define primary keys",
        "Use foreign keys where appropriate",
        "Use CHECK and UNIQUE constraints",
    ],
    "security": [
        "Apply least privilege",
        "Separate administrative roles",
        "Validate dynamic identifiers",
    ],
    "performance": [
        "Design indexes around workload",
        "Measure query behavior",
        "Avoid unnecessary indexes",
    ],
    "evolution": [
        "Use ordered migrations",
        "Consider backward compatibility",
        "Track object dependencies",
    ],
}

for category, items in production_checklist.items():
    print(f"\n{category.upper()}")
    for item in items:
        print("  -", item)


# =============================================================================
# 41. COMPLETE MINI DATABASE DESIGN
# =============================================================================

"""
This final example combines multiple schema principles into a small logical
e-commerce design.

Logical domains:

sales
    customers
    orders
    order_items

catalog
    products

reporting
    customer_revenue

Conceptual relationships:

sales.customers
    1
    |
    | many
    |
sales.orders
    1
    |
    | many
    |
sales.order_items
    many
    |
    | 1
    |
catalog.products

reporting.customer_revenue depends on sales objects.
"""


print_section("41. COMPLETE MINI DATABASE IMPLEMENTATION")

mini_connection = sqlite3.connect(":memory:")
mini_connection.execute("PRAGMA foreign_keys = ON")

mini_connection.executescript(
    """
    CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY,
        customer_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE
    );

    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        product_name TEXT NOT NULL,
        unit_price REAL NOT NULL CHECK (unit_price >= 0)
    );

    CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id)
            REFERENCES customers(customer_id)
    );

    CREATE TABLE order_items (
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        unit_price REAL NOT NULL CHECK (unit_price >= 0),

        PRIMARY KEY (order_id, product_id),

        FOREIGN KEY (order_id)
            REFERENCES orders(order_id),

        FOREIGN KEY (product_id)
            REFERENCES products(product_id)
    );

    CREATE INDEX idx_orders_customer_id
    ON orders(customer_id);

    CREATE INDEX idx_order_items_product_id
    ON order_items(product_id);

    CREATE VIEW customer_revenue AS
    SELECT
        customers.customer_id,
        customers.customer_name,
        COALESCE(
            SUM(order_items.quantity * order_items.unit_price),
            0
        ) AS total_revenue
    FROM customers
    LEFT JOIN orders
        ON customers.customer_id = orders.customer_id
    LEFT JOIN order_items
        ON orders.order_id = order_items.order_id
    GROUP BY
        customers.customer_id,
        customers.customer_name;
    """
)

mini_connection.executemany(
    """
    INSERT INTO customers
    (customer_id, customer_name, email)
    VALUES (?, ?, ?)
    """,
    [
        (1, "Asha Sharma", "asha@example.com"),
        (2, "Ravi Kumar", "ravi@example.com"),
    ],
)

mini_connection.executemany(
    """
    INSERT INTO products
    (product_id, product_name, unit_price)
    VALUES (?, ?, ?)
    """,
    [
        (101, "Keyboard", 2500),
        (102, "Mouse", 800),
        (103, "Monitor", 15000),
    ],
)

mini_connection.executemany(
    """
    INSERT INTO orders
    (order_id, customer_id)
    VALUES (?, ?)
    """,
    [
        (1001, 1),
        (1002, 1),
        (1003, 2),
    ],
)

mini_connection.executemany(
    """
    INSERT INTO order_items
    (order_id, product_id, quantity, unit_price)
    VALUES (?, ?, ?, ?)
    """,
    [
        (1001, 101, 1, 2500),
        (1001, 102, 2, 800),
        (1002, 103, 1, 15000),
        (1003, 102, 3, 800),
    ],
)

revenue_rows = mini_connection.execute(
    """
    SELECT
        customer_id,
        customer_name,
        total_revenue
    FROM customer_revenue
    ORDER BY total_revenue DESC
    """
).fetchall()

print("Customer revenue view:")
for row in revenue_rows:
    print(row)


# =============================================================================
# 42. FINAL METADATA INSPECTION
# =============================================================================

print_section("42. FINAL SCHEMA METADATA INSPECTION")

final_objects = mini_connection.execute(
    """
    SELECT
        type,
        name,
        tbl_name
    FROM sqlite_master
    WHERE name NOT LIKE 'sqlite_%'
    ORDER BY
        type,
        name
    """
).fetchall()

for database_object in final_objects:
    print(database_object)


# =============================================================================
# 43. IMPORTANT PRINCIPLES RECAP THROUGH CODE
# =============================================================================

print_section("43. CORE PRINCIPLES")

principles = {
    "schema": (
        "A logical organization and definition of database objects."
    ),
    "namespace": (
        "A naming boundary that prevents object-name conflicts."
    ),
    "table": (
        "A structured collection of rows and columns."
    ),
    "constraint": (
        "A rule enforced to protect data integrity."
    ),
    "primary_key": (
        "A unique row identifier."
    ),
    "foreign_key": (
        "A relationship constraint referencing another table."
    ),
    "view": (
        "A named query providing logical abstraction."
    ),
    "index": (
        "A structure that can improve query performance at write and storage cost."
    ),
    "migration": (
        "A controlled, ordered change to database structure."
    ),
    "logical_organization": (
        "Grouping objects according to meaningful business, technical, "
        "security, or lifecycle boundaries."
    ),
}

for term, definition in principles.items():
    print(f"{term}: {definition}")


# =============================================================================
# 44. CLEANUP
# =============================================================================

connection.close()
migration_connection.close()
compatibility_connection.close()
transaction_connection.close()
sqlite_namespace_connection.close()
mini_connection.close()

print_section("DATABASE SCHEMA STUDY SCRIPT COMPLETE")
print(
    "The examples demonstrated schema concepts, namespaces, database objects, "
    "logical organization, integrity constraints, dependencies, migrations, "
    "security, performance, and production-oriented design."
)
