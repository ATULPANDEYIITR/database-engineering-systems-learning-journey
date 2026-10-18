"""
PostgreSQL Table Engineering
Demonstrates CREATE TABLE, ALTER TABLE, constraints, schema evolution,
data integrity, migration safety, and catalog inspection.

Requirements:
    Python 3.10+
    PostgreSQL 14+
    Optional database connection: pip install "psycopg[binary]"

Configure DATABASE_URL before executing against a PostgreSQL database.
Without DATABASE_URL, the script runs its built-in metadata and validation
demonstrations without connecting to PostgreSQL.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class ColumnDefinition:
    name: str
    data_type: str
    nullable: bool = True
    default: str | None = None

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.name):
            raise ValueError(f"Unsafe column identifier: {self.name}")
        allowed_types = {
            "INTEGER",
            "BIGINT",
            "TEXT",
            "BOOLEAN",
            "DATE",
            "NUMERIC(12,2)",
            "TIMESTAMPTZ",
            "UUID",
        }
        if self.data_type not in allowed_types:
            raise ValueError(f"Unsupported data type: {self.data_type}")
        if self.default is not None and ";" in self.default:
            raise ValueError("Default expressions cannot contain semicolons")


def demonstrate_table_definitions() -> list[ColumnDefinition]:
    """Model columns for a realistic inventory and order-management database."""
    print("\n=== Table definitions ===")

    columns = [
        ColumnDefinition("product_id", "BIGINT", nullable=False),
        ColumnDefinition("sku", "TEXT", nullable=False),
        ColumnDefinition("product_name", "TEXT", nullable=False),
        ColumnDefinition("unit_price", "NUMERIC(12,2)", nullable=False),
        ColumnDefinition("active", "BOOLEAN", nullable=False, default="TRUE"),
    ]

    for column in columns:
        column.validate()
        print(
            f"{column.name}: {column.data_type}, "
            f"nullable={column.nullable}, default={column.default}"
        )

    # PostgreSQL identifiers should be fixed in application code or quoted
    # correctly. Parameter placeholders cannot substitute table or column names.
    invalid = ColumnDefinition("sku; DROP TABLE products; --", "TEXT")
    try:
        invalid.validate()
    except ValueError as error:
        print(f"Rejected unsafe identifier: {error}")

    return columns


def demonstrate_constraints() -> None:
    """Explain distinct integrity rules using concrete inventory examples."""
    print("\n=== Constraint evaluation ===")

    def validate_product(
        sku: str,
        name: str,
        price: Decimal,
        quantity: int,
    ) -> None:
        if not sku.strip():
            raise ValueError("SKU must not be empty")
        if not name.strip():
            raise ValueError("Product name must not be empty")
        if price < Decimal("0.00"):
            raise ValueError("Price must be non-negative")
        if quantity < 0:
            raise ValueError("Quantity must be non-negative")

    examples = [
        ("KB-100", "Mechanical Keyboard", Decimal("3499.00"), 20),
        ("MS-200", "Wireless Mouse", Decimal("1299.00"), 45),
    ]

    for example in examples:
        validate_product(*example)
        print(f"Valid product: {example[0]}")

    invalid_examples = [
        ("", "Unnamed product", Decimal("100.00"), 2),
        ("BAD-PRICE", "Damaged Sample", Decimal("-5.00"), 1),
        ("BAD-STOCK", "Negative Stock", Decimal("25.00"), -1),
    ]

    for example in invalid_examples:
        try:
            validate_product(*example)
        except ValueError as error:
            print(f"Rejected {example[0] or '<empty SKU>'}: {error}")

    print(
        "Application validation improves error messages; PostgreSQL "
        "constraints remain the final integrity boundary."
    )


def build_schema_sql() -> list[str]:
    """Return an executable PostgreSQL schema and migration sequence."""
    statements = [
        """
        CREATE SCHEMA IF NOT EXISTS inventory
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory.categories (
            category_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            category_name TEXT NOT NULL,
            CONSTRAINT uq_categories_name UNIQUE (category_name),
            CONSTRAINT ck_categories_name_nonempty
                CHECK (length(btrim(category_name)) > 0)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory.products (
            product_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            sku TEXT NOT NULL,
            product_name TEXT NOT NULL,
            category_id BIGINT,
            unit_price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
            stock_quantity INTEGER NOT NULL DEFAULT 0,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_products_sku UNIQUE (sku),
            CONSTRAINT ck_products_sku_nonempty
                CHECK (length(btrim(sku)) > 0),
            CONSTRAINT ck_products_name_nonempty
                CHECK (length(btrim(product_name)) > 0),
            CONSTRAINT ck_products_price_nonnegative
                CHECK (unit_price >= 0),
            CONSTRAINT ck_products_stock_nonnegative
                CHECK (stock_quantity >= 0),
            CONSTRAINT fk_products_category
                FOREIGN KEY (category_id)
                REFERENCES inventory.categories(category_id)
                ON DELETE SET NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory.customers (
            customer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            email TEXT NOT NULL,
            full_name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_customers_email UNIQUE (email),
            CONSTRAINT ck_customers_email_nonempty
                CHECK (length(btrim(email)) > 0),
            CONSTRAINT ck_customers_name_nonempty
                CHECK (length(btrim(full_name)) > 0)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory.orders (
            order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            customer_id BIGINT NOT NULL,
            order_status TEXT NOT NULL DEFAULT 'pending',
            ordered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_orders_customer
                FOREIGN KEY (customer_id)
                REFERENCES inventory.customers(customer_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_orders_status
                CHECK (
                    order_status IN (
                        'pending', 'confirmed', 'shipped',
                        'delivered', 'cancelled'
                    )
                )
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory.order_items (
            order_id BIGINT NOT NULL,
            product_id BIGINT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price NUMERIC(12,2) NOT NULL,
            PRIMARY KEY (order_id, product_id),
            CONSTRAINT fk_items_order
                FOREIGN KEY (order_id)
                REFERENCES inventory.orders(order_id)
                ON DELETE CASCADE,
            CONSTRAINT fk_items_product
                FOREIGN KEY (product_id)
                REFERENCES inventory.products(product_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_items_quantity
                CHECK (quantity > 0),
            CONSTRAINT ck_items_price
                CHECK (unit_price >= 0)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_products_category_active
            ON inventory.products(category_id, active)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_orders_customer_date
            ON inventory.orders(customer_id, ordered_at DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_order_items_product
            ON inventory.order_items(product_id)
        """,
        """
        ALTER TABLE inventory.products
            ADD COLUMN IF NOT EXISTS description TEXT
        """,
        """
        ALTER TABLE inventory.products
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
                NOT NULL DEFAULT CURRENT_TIMESTAMP
        """,
        """
        ALTER TABLE inventory.products
            ALTER COLUMN description SET DEFAULT ''
        """,
    ]
    return [statement.strip() for statement in statements]


def demonstrate_schema_evolution() -> None:
    print("\n=== CREATE TABLE and ALTER TABLE ===")
    for index, statement in enumerate(build_schema_sql(), start=1):
        compact = " ".join(statement.split())
        print(f"{index:02d}. {compact}")

    print(
        "\nMigration notes:\n"
        "- IF NOT EXISTS supports rerunning selected DDL but does not "
        "verify that an existing object has the intended definition.\n"
        "- Adding a column with a constant default is often efficient "
        "on modern PostgreSQL, but lock acquisition still matters.\n"
        "- Existing data must satisfy a new CHECK or NOT NULL rule "
        "before that rule can be enforced.\n"
        "- Production schema changes should be versioned and reviewed."
    )


def connect_and_run(database_url: str) -> None:
    """Apply the demonstration schema and query PostgreSQL metadata."""
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must use postgres:// or postgresql://")

    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError(
            'Install the optional driver with: pip install "psycopg[binary]"'
        ) from error

    print("\n=== PostgreSQL execution ===")

    # psycopg executes parameterized SQL safely. DDL here uses fixed,
    # application-controlled identifiers and no user-supplied SQL fragments.
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for statement in build_schema_sql():
                cursor.execute(statement)

            cursor.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """,
                ("inventory",),
            )
            for schema, table in cursor.fetchall():
                print(f"Table available: {schema}.{table}")

            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                ("inventory", "products"),
            )
            print("\nProducts table columns:")
            for row in cursor.fetchall():
                print(row)

            cursor.execute(
                """
                SELECT
                    conname,
                    contype
                FROM pg_constraint
                WHERE conrelid = 'inventory.products'::regclass
                ORDER BY conname
                """
            )
            print("\nProducts table constraints:")
            for name, constraint_type in cursor.fetchall():
                print(f"{name}: {constraint_type}")

        # The connection context commits when the block succeeds and rolls
        # back when an uncaught exception occurs.
    print("Schema statements completed successfully.")


def demonstrate_design_decisions() -> None:
    print("\n=== Design decisions ===")
    decisions = {
        "PRIMARY KEY": "Identifies each row and guarantees uniqueness.",
        "UNIQUE": "Prevents duplicate business identifiers such as SKU.",
        "NOT NULL": "Prevents missing values in mandatory attributes.",
        "CHECK": "Enforces row-level rules such as non-negative prices.",
        "FOREIGN KEY": "Prevents references to nonexistent parent rows.",
        "DEFAULT": "Supplies a value when an insert omits a column.",
        "ALTER TABLE": "Changes an existing schema without recreating it.",
    }
    for rule, explanation in decisions.items():
        print(f"{rule}: {explanation}")

    print(
        "\nA CHECK constraint accepts TRUE or UNKNOWN in PostgreSQL. "
        "Pair CHECK with NOT NULL when NULL must be prohibited.\n"
        "A UNIQUE constraint normally permits multiple NULL values. "
        "Use NOT NULL when the business key is mandatory.\n"
        "Foreign keys do not automatically create indexes on the "
        "referencing columns; add them when query patterns justify it."
    )


def main() -> int:
    demonstrate_table_definitions()
    demonstrate_constraints()
    demonstrate_schema_evolution()
    demonstrate_design_decisions()

    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        try:
            connect_and_run(database_url)
        except Exception as error:
            print(f"PostgreSQL execution failed: {error}", file=sys.stderr)
            return 1
    else:
        print(
            "\nNo DATABASE_URL configured. Offline demonstrations completed. "
            "Set DATABASE_URL to execute the DDL against PostgreSQL."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
