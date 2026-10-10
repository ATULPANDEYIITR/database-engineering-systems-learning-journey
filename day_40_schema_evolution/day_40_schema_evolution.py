#!/usr/bin/env python3
"""Executable demonstrations of safe schema evolution using only the standard library."""

from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class SchemaEvolutionError(Exception):
    """Base exception for schema compatibility and migration failures."""


class ValidationError(SchemaEvolutionError):
    """Raised when data violates the active schema contract."""


class MigrationError(SchemaEvolutionError):
    """Raised when a schema migration cannot complete safely."""


@dataclass(frozen=True)
class Field:
    name: str
    data_type: type
    required: bool = True
    default: Any = None
    has_default: bool = False

    def validate(self, value: Any) -> None:
        if value is None:
            if self.required:
                raise ValidationError(f"{self.name} cannot be null")
            return

        # bool is a subclass of int in Python, so exact type checks matter
        # when a database contract requires an integer rather than a boolean.
        if self.data_type is int:
            valid = type(value) is int
        elif self.data_type is float:
            valid = type(value) in (int, float) and type(value) is not bool
        else:
            valid = isinstance(value, self.data_type)

        if not valid:
            raise ValidationError(
                f"{self.name} must be {self.data_type.__name__}, "
                f"received {type(value).__name__}"
            )


@dataclass(frozen=True)
class Schema:
    version: int
    fields: tuple[Field, ...]

    def __post_init__(self) -> None:
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValidationError("Schema field names must be unique")
        if self.version < 1:
            raise ValidationError("Schema version must be positive")

    @property
    def field_map(self) -> dict[str, Field]:
        return {field.name: field for field in self.fields}

    def validate(self, record: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(record, dict):
            raise ValidationError("A record must be a dictionary")

        known = self.field_map
        unknown = set(record) - set(known)
        if unknown:
            raise ValidationError(
                f"Unknown fields for schema v{self.version}: {sorted(unknown)}"
            )

        normalized: dict[str, Any] = {}

        for field in self.fields:
            if field.name in record:
                value = record[field.name]
            elif field.has_default:
                value = copy.deepcopy(field.default)
            elif field.required:
                raise ValidationError(f"Missing required field: {field.name}")
            else:
                value = None

            field.validate(value)
            normalized[field.name] = value

        return normalized


class SchemaRegistry:
    """Stores immutable schema definitions and migration functions."""

    def __init__(self) -> None:
        self.schemas: dict[int, Schema] = {}
        self.migrations: dict[tuple[int, int], Callable] = {}

    def register(self, schema: Schema) -> None:
        if schema.version in self.schemas:
            raise SchemaEvolutionError(
                f"Schema v{schema.version} is already registered"
            )
        self.schemas[schema.version] = schema

    def register_migration(
        self,
        source_version: int,
        target_version: int,
        migration: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        if target_version != source_version + 1:
            raise MigrationError("Migrations must connect adjacent versions")
        if source_version not in self.schemas or target_version not in self.schemas:
            raise MigrationError("Register both schemas before their migration")
        key = (source_version, target_version)
        if key in self.migrations:
            raise MigrationError(f"Migration {key} already exists")
        self.migrations[key] = migration

    def evolve(
        self,
        record: dict[str, Any],
        source_version: int,
        target_version: int,
    ) -> dict[str, Any]:
        if source_version not in self.schemas or target_version not in self.schemas:
            raise MigrationError("Unknown source or target schema version")
        if target_version < source_version:
            raise MigrationError("Downgrades require an explicit reverse migration")

        current = self.schemas[source_version].validate(record)

        for version in range(source_version, target_version):
            migration = self.migrations.get((version, version + 1))
            if migration is None:
                raise MigrationError(
                    f"No migration from v{version} to v{version + 1}"
                )

            try:
                transformed = migration(copy.deepcopy(current))
                current = self.schemas[version + 1].validate(transformed)
            except Exception as exc:
                raise MigrationError(
                    f"Migration v{version} to v{version + 1} failed: {exc}"
                ) from exc

        return current


class MigrationRunner:
    """Runs data migrations atomically and records applied migration versions."""

    def __init__(self, database: Path) -> None:
        self.database = database
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS migration_history (
                    version INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def apply(
        self,
        version: int,
        description: str,
        migration: Callable[[sqlite3.Connection], None],
    ) -> bool:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                "SELECT 1 FROM migration_history WHERE version = ?",
                (version,),
            ).fetchone()

            if exists:
                connection.rollback()
                return False

            migration(connection)
            connection.execute(
                "INSERT INTO migration_history(version, description) VALUES (?, ?)",
                (version, description),
            )
            connection.commit()
            return True
        except Exception as exc:
            connection.rollback()
            raise MigrationError(
                f"Database migration {version} rolled back: {exc}"
            ) from exc
        finally:
            connection.close()


def create_v1(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        )
    """)
    connection.execute("""
        INSERT INTO customers(id, full_name, email)
        VALUES
            (1, 'Asha Sharma', 'asha@example.com'),
            (2, 'Rahul Verma', 'rahul@example.com')
    """)


def migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    # Adding a nullable column is an expand-phase migration. Existing
    # application versions can continue inserting records without it.
    connection.execute("ALTER TABLE customers ADD COLUMN phone TEXT")


def migrate_v2_to_v3(connection: sqlite3.Connection) -> None:
    # SQLite cannot add a NOT NULL column without a suitable default to a
    # populated table. Rebuilding permits explicit constraints and preserves
    # the existing rows.
    connection.execute("""
        CREATE TABLE customers_new (
            id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            country_code TEXT NOT NULL DEFAULT 'IN'
                CHECK (length(country_code) = 2)
        )
    """)
    connection.execute("""
        INSERT INTO customers_new(id, full_name, email, phone)
        SELECT id, full_name, email, phone
        FROM customers
    """)
    connection.execute("DROP TABLE customers")
    connection.execute("ALTER TABLE customers_new RENAME TO customers")


def demonstrate_registry() -> None:
    print("\nSchema contracts and versioned transformations")

    v1 = Schema(1, (
        Field("id", int),
        Field("name", str),
    ))
    v2 = Schema(2, (
        Field("id", int),
        Field("name", str),
        Field("email", str, has_default=True, default=""),
    ))
    v3 = Schema(3, (
        Field("id", int),
        Field("display_name", str),
        Field("email", str),
        Field("active", bool, has_default=True, default=True),
    ))

    registry = SchemaRegistry()
    for schema in (v1, v2, v3):
        registry.register(schema)

    registry.register_migration(
        1, 2,
        lambda row: {**row, "email": f"user{row['id']}@example.com"},
    )
    registry.register_migration(
        2, 3,
        lambda row: {
            "id": row["id"],
            "display_name": row.pop("name"),
            "email": row["email"],
            "active": True,
        },
    )

    legacy = {"id": 7, "name": "Maya Singh"}
    evolved = registry.evolve(legacy, 1, 3)

    print("Legacy record:", json.dumps(legacy))
    print("Current record:", json.dumps(evolved))

    try:
        v3.validate({"id": True, "display_name": "Invalid", "email": "x"})
    except ValidationError as exc:
        print("Expected validation failure:", exc)


def demonstrate_database_migrations() -> None:
    print("\nTransactional database migrations")

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "customers.db"
        runner = MigrationRunner(database)

        print("Apply v1:", runner.apply(1, "Create customer table", create_v1))
        print("Apply v1 again:", runner.apply(1, "Create customer table", create_v1))
        print("Apply v2:", runner.apply(2, "Add optional phone", migrate_v1_to_v2))
        print("Apply v3:", runner.apply(3, "Add country policy", migrate_v2_to_v3))

        with runner.connect() as connection:
            rows = connection.execute("""
                SELECT id, full_name, email, phone, country_code
                FROM customers ORDER BY id
            """).fetchall()
            print("Migrated records:")
            for row in rows:
                print(dict(row))

            columns = connection.execute(
                "PRAGMA table_info(customers)"
            ).fetchall()
            print("Current columns:", [column["name"] for column in columns])

            try:
                connection.execute("""
                    INSERT INTO customers(id, full_name, email, country_code)
                    VALUES (3, 'Invalid Customer', 'invalid@example.com', 'IND')
                """)
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                print("Expected constraint failure:", exc)

        # A failed migration must not leave either a partial schema change
        # or a successful entry in migration history.
        def broken_migration(connection: sqlite3.Connection) -> None:
            connection.execute("CREATE TABLE transient_data(id INTEGER)")
            raise RuntimeError("Simulated deployment failure")

        try:
            runner.apply(4, "Intentionally failing migration", broken_migration)
        except MigrationError as exc:
            print("Expected rollback:", exc)

        with runner.connect() as connection:
            transient = connection.execute("""
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name = 'transient_data'
            """).fetchone()
            history = connection.execute("""
                SELECT version FROM migration_history ORDER BY version
            """).fetchall()

            assert transient is None
            assert [row["version"] for row in history] == [1, 2, 3]
            print("Rollback verified; history:", [row["version"] for row in history])


def demonstrate_compatibility() -> None:
    print("\nReader and writer compatibility")

    old_writer = {"id": 20, "name": "Old Client"}
    new_writer = {
        "id": 21,
        "name": "New Client",
        "preferred_language": "en",
    }

    # A strict old reader rejects an unknown field. A forward-compatible
    # reader can project only the fields it understands.
    old_fields = {"id", "name"}
    try:
        unknown = set(new_writer) - old_fields
        if unknown:
            raise ValidationError(f"Old reader rejects fields: {sorted(unknown)}")
    except ValidationError as exc:
        print("Strict old reader:", exc)

    projected = {key: value for key, value in new_writer.items() if key in old_fields}
    print("Tolerant old reader:", projected)
    print("Old writer remains readable:", old_writer)

    # A safe rollout generally adds the new field before requiring it.
    # Producers are upgraded before the field is made mandatory.
    print("Recommended rollout: expand, deploy compatible readers, backfill, "
          "deploy writers, enforce, contract.")


class SchemaEvolutionTests(unittest.TestCase):
    def test_default_is_copied(self) -> None:
        default = {"currency": "INR"}
        schema = Schema(1, (
            Field("id", int),
            Field("settings", dict, has_default=True, default=default),
        ))
        first = schema.validate({"id": 1})
        first["settings"]["currency"] = "USD"
        second = schema.validate({"id": 2})
        self.assertEqual(second["settings"]["currency"], "INR")

    def test_required_field_is_enforced(self) -> None:
        schema = Schema(1, (Field("email", str),))
        with self.assertRaises(ValidationError):
            schema.validate({})

    def test_boolean_is_not_integer(self) -> None:
        schema = Schema(1, (Field("count", int),))
        with self.assertRaises(ValidationError):
            schema.validate({"count": True})

    def test_missing_migration_fails(self) -> None:
        registry = SchemaRegistry()
        registry.register(Schema(1, (Field("id", int),)))
        registry.register(Schema(2, (Field("id", int),)))
        with self.assertRaises(MigrationError):
            registry.evolve({"id": 1}, 1, 2)

    def test_unknown_field_fails(self) -> None:
        schema = Schema(1, (Field("id", int),))
        with self.assertRaises(ValidationError):
            schema.validate({"id": 1, "unexpected": "value"})


def main() -> None:
    demonstrate_registry()
    demonstrate_database_migrations()
    demonstrate_compatibility()

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SchemaEvolutionTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
