#!/usr/bin/env python3
"""
PostgreSQL production operations utility.

Commands:
    python postgres_admin.py
    python postgres_admin.py self-test
    python postgres_admin.py migrate
    python postgres_admin.py doctor
    python postgres_admin.py report

Live commands use the PostgreSQL command-line client and standard libpq
environment variables. No database password is accepted as a command-line
argument.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


HEALTH_SQL = """
SELECT json_build_object(
    'database', current_database(),
    'server_version', current_setting('server_version'),
    'server_version_num', current_setting('server_version_num')::integer,
    'max_connections', current_setting('max_connections')::integer,
    'superuser_reserved_connections',
        current_setting('superuser_reserved_connections')::integer,
    'used_connections', (
        SELECT count(*)
        FROM pg_stat_activity
        WHERE datname = current_database()
    ),
    'blocked_sessions', (
        SELECT count(*)
        FROM pg_stat_activity AS activity
        WHERE activity.datname = current_database()
          AND cardinality(pg_blocking_pids(activity.pid)) > 0
    ),
    'oldest_transaction_seconds', (
        SELECT COALESCE(
            EXTRACT(EPOCH FROM max(clock_timestamp() - xact_start))::integer,
            0
        )
        FROM pg_stat_activity
        WHERE datname = current_database()
          AND xact_start IS NOT NULL
    ),
    'database_size_bytes', pg_database_size(current_database()),
    'is_replica', pg_is_in_recovery()
)::text;
"""


REPORT_SQL = """
SELECT jsonb_pretty(
    jsonb_build_object(
        'database', current_database(),
        'server_version', current_setting('server_version'),
        'database_size_bytes', pg_database_size(current_database()),
        'connections', jsonb_build_object(
            'maximum', current_setting('max_connections')::integer,
            'reserved_for_superusers',
                current_setting('superuser_reserved_connections')::integer,
            'used', (
                SELECT count(*)
                FROM pg_stat_activity
                WHERE datname = current_database()
            ),
            'by_state', COALESCE((
                SELECT jsonb_object_agg(state_name, connection_count)
                FROM (
                    SELECT COALESCE(state, 'unknown') AS state_name,
                           count(*) AS connection_count
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    GROUP BY COALESCE(state, 'unknown')
                ) AS states
            ), '{}'::jsonb)
        ),
        'blocked_sessions', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'pid', activity.pid,
                    'application', activity.application_name,
                    'state', activity.state,
                    'wait_event_type', activity.wait_event_type,
                    'wait_event', activity.wait_event
                )
                ORDER BY activity.pid
            )
            FROM pg_stat_activity AS activity
            WHERE activity.datname = current_database()
              AND cardinality(pg_blocking_pids(activity.pid)) > 0
        ), '[]'::jsonb),
        'long_transactions', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'pid', pid,
                    'application', application_name,
                    'state', state,
                    'duration_seconds',
                        EXTRACT(EPOCH FROM clock_timestamp() - xact_start)::integer
                )
                ORDER BY xact_start
            )
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND xact_start < clock_timestamp() - interval '5 minutes'
        ), '[]'::jsonb),
        'largest_relations', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'schema', schemaname,
                    'table', relname,
                    'total_size_bytes', total_bytes,
                    'table_size_bytes', table_bytes
                )
                ORDER BY total_bytes DESC
            )
            FROM (
                SELECT
                    schemaname,
                    relname,
                    pg_total_relation_size(
                        format('%I.%I', schemaname, relname)::regclass
                    ) AS total_bytes,
                    pg_relation_size(
                        format('%I.%I', schemaname, relname)::regclass
                    ) AS table_bytes
                FROM pg_stat_user_tables
                ORDER BY pg_total_relation_size(
                    format('%I.%I', schemaname, relname)::regclass
                ) DESC
                LIMIT 10
            ) AS relations
        ), '[]'::jsonb),
        'replication', jsonb_build_object(
            'is_replica', pg_is_in_recovery(),
            'replay_lag_bytes', CASE
                WHEN pg_is_in_recovery()
                 AND pg_last_wal_receive_lsn() IS NOT NULL
                 AND pg_last_wal_replay_lsn() IS NOT NULL
                THEN pg_wal_lsn_diff(
                    pg_last_wal_receive_lsn(),
                    pg_last_wal_replay_lsn()
                )
                ELSE NULL
            END
        )
    )
)::text;
"""


class AdminError(RuntimeError):
    """Raised when a PostgreSQL administration operation fails."""


@dataclass(frozen=True)
class ConnectionBudget:
    """Estimate the application connection demand across all instances."""

    application_instances: int
    pool_size_per_instance: int
    maintenance_reserve: int = 20

    def __post_init__(self) -> None:
        if self.application_instances < 1:
            raise ValueError("application_instances must be at least 1")
        if self.pool_size_per_instance < 1:
            raise ValueError("pool_size_per_instance must be at least 1")
        if self.maintenance_reserve < 0:
            raise ValueError("maintenance_reserve cannot be negative")

    @property
    def application_connections(self) -> int:
        return self.application_instances * self.pool_size_per_instance

    def evaluate(
        self,
        max_connections: int,
        superuser_reserved_connections: int,
    ) -> dict[str, Any]:
        if max_connections <= 0:
            raise ValueError("max_connections must be positive")
        if superuser_reserved_connections < 0:
            raise ValueError("reserved connections cannot be negative")

        protected = (
            superuser_reserved_connections + self.maintenance_reserve
        )
        available = max_connections - protected
        safe = available >= 0 and self.application_connections <= available

        return {
            "application_instances": self.application_instances,
            "pool_size_per_instance": self.pool_size_per_instance,
            "application_connections": self.application_connections,
            "server_max_connections": max_connections,
            "superuser_reserved_connections": superuser_reserved_connections,
            "maintenance_reserve": self.maintenance_reserve,
            "available_for_application_pools": max(0, available),
            "headroom_after_application_pools": (
                available - self.application_connections
            ),
            "safe": safe,
        }


class PsqlClient:
    """Run fixed administrative SQL safely without invoking a shell."""

    def __init__(self, executable: str = "psql", timeout: int = 30) -> None:
        resolved = shutil.which(executable)
        if resolved is None:
            raise AdminError(
                "psql was not found. Install PostgreSQL client tools and "
                "ensure psql is available on PATH."
            )
        self.executable = resolved
        self.timeout = timeout

    def execute(
        self,
        sql: str | None = None,
        sql_file: Path | None = None,
        timeout: int | None = None,
    ) -> str:
        if (sql is None) == (sql_file is None):
            raise ValueError("Supply exactly one of sql or sql_file")

        command = [
            self.executable,
            "-X",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
        ]

        if sql_file is not None:
            if not sql_file.is_file():
                raise AdminError(f"SQL file does not exist: {sql_file}")
            command.extend(["-f", str(sql_file)])
        else:
            command.extend(["-A", "-t", "-c", sql or ""])

        environment = os.environ.copy()

        # Never log connection credentials. libpq reads PGPASSWORD,
        # PGPASSFILE, service configuration and PG* variables itself.
        try:
            result = subprocess.run(
                command,
                input=None,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdminError(
                f"psql operation exceeded {timeout or self.timeout} seconds"
            ) from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or "psql returned a non-zero exit code"
            raise AdminError(detail)

        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)

        return result.stdout.strip()

    def query_json(self, sql: str) -> dict[str, Any]:
        output = self.execute(sql=sql)
        if not output:
            raise AdminError("PostgreSQL returned an empty JSON response")
        try:
            value = json.loads(output)
        except json.JSONDecodeError as exc:
            raise AdminError("PostgreSQL returned invalid JSON") from exc

        if not isinstance(value, dict):
            raise AdminError("Expected a JSON object from PostgreSQL")
        return value


def run_self_test() -> None:
    """Exercise local validation and capacity calculations without a server."""

    budget = ConnectionBudget(
        application_instances=4,
        pool_size_per_instance=10,
        maintenance_reserve=20,
    )
    result = budget.evaluate(
        max_connections=180,
        superuser_reserved_connections=3,
    )

    assert result["application_connections"] == 40
    assert result["available_for_application_pools"] == 157
    assert result["headroom_after_application_pools"] == 117
    assert result["safe"] is True

    constrained = budget.evaluate(
        max_connections=50,
        superuser_reserved_connections=3,
    )
    assert constrained["safe"] is False

    try:
        ConnectionBudget(0, 10)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid connection budget was accepted")

    print("Self-test passed.")
    print(json.dumps(result, indent=2))


def run_migration(args: argparse.Namespace) -> None:
    client = PsqlClient(timeout=args.migration_timeout)
    sql_file = args.sql_file.resolve()
    print(f"Applying SQL file: {sql_file}")
    output = client.execute(sql_file=sql_file, timeout=args.migration_timeout)
    if output:
        print(output)
    print("Migration script completed.")


def run_doctor(args: argparse.Namespace) -> None:
    client = PsqlClient()
    health = client.query_json(HEALTH_SQL)

    budget = ConnectionBudget(
        application_instances=args.app_instances,
        pool_size_per_instance=args.pool_size,
        maintenance_reserve=args.maintenance_reserve,
    )
    capacity = budget.evaluate(
        max_connections=int(health["max_connections"]),
        superuser_reserved_connections=int(
            health["superuser_reserved_connections"]
        ),
    )

    version_num = int(health["server_version_num"])
    used = int(health["used_connections"])
    maximum = int(health["max_connections"])
    blocked = int(health["blocked_sessions"])
    transaction_age = int(health["oldest_transaction_seconds"])

    checks = {
        "postgresql_version_supported": version_num >= 140000,
        "connection_capacity_available": capacity["safe"],
        "connection_usage_below_80_percent": used / maximum < 0.80,
        "no_blocked_sessions": blocked == 0,
        "no_transaction_older_than_5_minutes": transaction_age < 300,
        "database_is_primary": health["is_replica"] is False,
    }

    result = {
        "health": health,
        "connection_budget": capacity,
        "checks": checks,
        "healthy": all(checks.values()),
    }
    print(json.dumps(result, indent=2))

    if not result["healthy"]:
        raise AdminError("One or more PostgreSQL health checks failed")


def run_report() -> None:
    client = PsqlClient(timeout=45)
    report = client.query_json(REPORT_SQL)
    print(json.dumps(report, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PostgreSQL production operations utility"
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("self-test", "migrate", "doctor", "report"),
        default="self-test",
    )
    parser.add_argument(
        "--sql-file",
        type=Path,
        default=Path(__file__).with_name("postgresql.sql"),
        help="SQL file used by the migrate command",
    )
    parser.add_argument("--migration-timeout", type=int, default=120)
    parser.add_argument("--app-instances", type=int, default=4)
    parser.add_argument("--pool-size", type=int, default=10)
    parser.add_argument("--maintenance-reserve", type=int, default=20)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "self-test":
            run_self_test()
        elif args.command == "migrate":
            if args.migration_timeout <= 0:
                raise ValueError("migration timeout must be positive")
            run_migration(args)
        elif args.command == "doctor":
            run_doctor(args)
        elif args.command == "report":
            run_report()
        else:
            parser.error("Unsupported command")

        return 0
    except (AdminError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
