#!/usr/bin/env python3
"""
PostgreSQL Fundamentals: installation, architecture, psql, databases, and schemas.

This self-contained teaching program models PostgreSQL cluster architecture,
database and schema boundaries, connection handling, catalog inspection,
SQL execution, transactions, and operational diagnostics.

The standard-library simulation runs without a PostgreSQL installation.
An optional real-server mode uses psql through subprocess and never embeds
credentials in command-line arguments.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Schema:
    name: str
    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


@dataclass
class Database:
    name: str
    owner: str
    schemas: dict[str, Schema] = field(default_factory=dict)
    connections: int = 0

    def create_schema(self, name: str) -> None:
        validate_identifier(name)
        if name in self.schemas:
            raise ValueError(f"Schema already exists: {name}")
        self.schemas[name] = Schema(name)

    def create_table(self, schema_name: str, table_name: str) -> None:
        validate_identifier(table_name)
        if schema_name not in self.schemas:
            raise ValueError(f"Schema does not exist: {schema_name}")
        schema = self.schemas[schema_name]
        if table_name in schema.tables:
            raise ValueError(f"Table already exists: {schema_name}.{table_name}")
        schema.tables[table_name] = []


@dataclass
class Cluster:
    system_identifier: str
    databases: dict[str, Database] = field(default_factory=dict)
    roles: set[str] = field(default_factory=set)

    def create_role(self, role: str) -> None:
        validate_identifier(role)
        if role in self.roles:
            raise ValueError(f"Role already exists: {role}")
        self.roles.add(role)

    def create_database(self, name: str, owner: str) -> None:
        validate_identifier(name)
        if owner not in self.roles:
            raise ValueError(f"Database owner does not exist: {owner}")
        if name in self.databases:
            raise ValueError(f"Database already exists: {name}")
        self.databases[name] = Database(name, owner)
        self.databases[name].schemas["public"] = Schema("public")
        self.databases[name].schemas["app"] = Schema("app")


@dataclass(frozen=True)
class Connection:
    host: str
    port: int
    database: str
    user: str

    def describe(self) -> str:
        return (
            f"user={self.user} database={self.database} "
            f"host={self.host} port={self.port}"
        )


def validate_identifier(value: str) -> None:
    """Reject empty or unsafe identifiers in this simplified teaching model."""
    if not value or not value.replace("_", "a").isalnum():
        raise ValueError(f"Invalid identifier: {value!r}")
    if value[0].isdigit():
        raise ValueError(f"Identifier cannot begin with a digit: {value!r}")


def demonstrate_architecture() -> Cluster:
    print("\n=== PostgreSQL cluster architecture ===")
    print("A cluster is a collection of databases managed by one server instance.")
    print("Roles are cluster-wide; schemas and tables belong to individual databases.")
    print("A server installation can host multiple clusters using separate data directories.")

    cluster = Cluster(system_identifier="training-cluster-001")
    cluster.create_role("postgres")
    cluster.create_role("app_owner")
    cluster.create_role("analyst")
    cluster.create_database("operations", "app_owner")
    cluster.create_database("reporting", "postgres")

    operations = cluster.databases["operations"]
    operations.create_table("app", "assets")
    operations.create_table("app", "maintenance_events")
    operations.create_table("public", "import_log")

    reporting = cluster.databases["reporting"]
    reporting.create_table("public", "daily_metrics")

    print(f"Cluster identifier: {cluster.system_identifier}")
    print(f"Cluster-wide roles: {sorted(cluster.roles)}")
    for database in cluster.databases.values():
        print(f"\nDatabase: {database.name}; owner: {database.owner}")
        for schema in database.schemas.values():
            print(f"  Schema {schema.name}: {list(schema.tables)}")

    try:
        operations.create_table("analytics", "results")
    except ValueError as exc:
        print(f"\nExpected boundary check: {exc}")

    print(
        "Database boundary: an ordinary connection uses one current database. "
        "Cross-database access requires a separate connection or an explicit "
        "integration mechanism."
    )
    return cluster


def demonstrate_connections(cluster: Cluster) -> None:
    print("\n=== Connection parameters ===")
    connection = Connection(
        host="localhost",
        port=5432,
        database="operations",
        user="app_owner",
    )
    print(connection.describe())
    print("Connection string example:")
    print("postgresql://app_owner@localhost:5432/operations")
    print("No password is embedded in the displayed connection string.")

    database = cluster.databases[connection.database]
    database.connections += 1
    print(f"Simulated active connection count: {database.connections}")

    try:
        Connection("localhost", 99999, "operations", "app_owner")
        validate_port(99999)
    except ValueError as exc:
        print(f"Expected connection validation failure: {exc}")


def validate_port(port: int) -> None:
    if not 1 <= port <= 65535:
        raise ValueError(f"TCP port must be between 1 and 65535: {port}")


def demonstrate_catalogs(cluster: Cluster) -> None:
    print("\n=== Catalog-style inspection ===")
    database = cluster.databases["operations"]

    print("Equivalent PostgreSQL inspection queries:")
    print("  SELECT current_database(), current_user;")
    print("  SHOW server_version;")
    print("  SHOW search_path;")
    print("  SELECT datname FROM pg_database ORDER BY datname;")
    print(
        "  SELECT schemaname, tablename "
        "FROM pg_tables WHERE schemaname NOT IN "
        "('pg_catalog', 'information_schema');"
    )

    for schema_name, schema in database.schemas.items():
        for table_name in schema.tables:
            print(f"  {database.name}.{schema_name}.{table_name}")

    print("System catalogs such as pg_database and pg_class store server metadata.")
    print("information_schema provides standardized views of accessible objects.")


def demonstrate_search_path(cluster: Cluster) -> None:
    print("\n=== Schemas and object resolution ===")
    database = cluster.databases["operations"]
    database.schemas["app"].tables["assets"] = [
        {"asset_id": 1, "asset_name": "Pump P-104"},
        {"asset_id": 2, "asset_name": "Transformer T-208"},
    ]
    database.schemas["public"].tables["assets"] = [
        {"asset_id": 101, "asset_name": "Imported legacy asset"}
    ]

    search_path = ["app", "public"]
    print(f"Configured search_path: {', '.join(search_path)}")

    for schema_name in search_path:
        if "assets" in database.schemas[schema_name].tables:
            print(f"Unqualified assets resolves to {schema_name}.assets")
            break

    print("Explicit qualification removes ambiguity:")
    print("  SELECT * FROM app.assets;")
    print("  SELECT * FROM public.assets;")
    print(
        "A schema organizes names; it is not a separate database or "
        "a complete security boundary by itself."
    )


def demonstrate_transaction_model() -> None:
    print("\n=== Transaction behavior ===")
    inventory = {"pump": 10, "valve": 25}
    original = inventory.copy()

    try:
        inventory["pump"] -= 2
        inventory["valve"] -= 40
        if any(quantity < 0 for quantity in inventory.values()):
            raise ValueError("Inventory quantity cannot become negative")
    except ValueError as exc:
        inventory = original.copy()
        print(f"Transaction rolled back: {exc}")

    print(f"Inventory after rollback: {inventory}")
    print("PostgreSQL equivalent:")
    print("  BEGIN;")
    print("  UPDATE app.inventory SET quantity = quantity - 2 WHERE item_id = 1;")
    print("  COMMIT;")
    print("Use ROLLBACK when a transaction cannot safely complete.")
    print("A database transaction provides atomicity; this Python example models it.")


def demonstrate_installation_guidance() -> None:
    print("\n=== Installation and service verification ===")
    print("Windows:")
    print("  Install PostgreSQL using the official Windows installer.")
    print("  Verify the PostgreSQL service in Services.")
    print("  Add the PostgreSQL bin directory to PATH if needed.")
    print("macOS with Homebrew:")
    print("  brew install postgresql@17")
    print("  brew services start postgresql@17")
    print("Debian or Ubuntu:")
    print("  sudo apt update")
    print("  sudo apt install postgresql postgresql-client")
    print("  sudo systemctl status postgresql")
    print("These commands are platform-specific; package versions vary.")
    print("\nCheck whether psql is available:")
    executable = shutil.which("psql")
    print(f"psql executable: {executable or 'not found in PATH'}")
    print("Then use psql --version to inspect the client version.")
    print("The psql client version and server version can differ.")


def run_psql(sql: str, database: str, host: str, port: int, user: str) -> int:
    """Execute a fixed, trusted SQL statement using psql without shell expansion."""
    executable = shutil.which("psql")
    if executable is None:
        print("Cannot run real-server mode: psql is not available in PATH.")
        return 2

    validate_identifier(database)
    validate_identifier(user)
    validate_port(port)

    command = [
        executable,
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        host,
        "-p",
        str(port),
        "-U",
        user,
        "-d",
        database,
        "-c",
        sql,
    ]

    environment = os.environ.copy()
    print("\nExecuting a read-only diagnostic query through psql...")
    try:
        result = subprocess.run(
            command,
            env=environment,
            text=True,
            check=False,
            timeout=30,
        )
        return result.returncode
    except subprocess.TimeoutExpired:
        print("Connection command timed out.")
        return 124
    except OSError as exc:
        print(f"Unable to start psql: {exc}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explore PostgreSQL installation, architecture, psql, databases, and schemas."
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Run a read-only query against an existing PostgreSQL server.",
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="postgres")
    parser.add_argument("--user", default=os.environ.get("PGUSER", "postgres"))
    args = parser.parse_args()

    try:
        cluster = demonstrate_architecture()
        demonstrate_connections(cluster)
        demonstrate_catalogs(cluster)
        demonstrate_search_path(cluster)
        demonstrate_transaction_model()
        demonstrate_installation_guidance()
    except (ValueError, KeyError) as exc:
        print(f"Demonstration error: {exc}", file=sys.stderr)
        return 1

    if args.real:
        return run_psql(
            "SELECT current_database() AS database, "
            "current_user AS role, version() AS server_version;",
            args.database,
            args.host,
            args.port,
            args.user,
        )

    print("\nSimulation completed. Use --real to inspect an accessible server.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
