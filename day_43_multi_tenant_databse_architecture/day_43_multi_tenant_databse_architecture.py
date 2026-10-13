#!/usr/bin/env python3
"""
Multi-tenant database architecture laboratory.

Compares three isolation strategies:
- Shared schema: tenant_id separates tenant-owned rows.
- Separate schema: each tenant has a dedicated PostgreSQL schema.
- Separate database: each tenant has an independent database.

The simulation uses only the Python standard library. It demonstrates
tenant isolation, provisioning, query scoping, authorization, migration
coordination, connection routing, resource limits, and architecture trade-offs.

Run:
    python multi_tenant_database.py

The in-memory repository is an educational simulation, not a replacement
for PostgreSQL row-level security, database permissions, or transactions.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import unittest
import uuid

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable


class Architecture(str, Enum):
    SHARED_SCHEMA = "shared_schema"
    SEPARATE_SCHEMA = "separate_schema"
    SEPARATE_DATABASE = "separate_database"


class TenantStatus(str, Enum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPROVISIONED = "deprovisioned"


class TenantNotFoundError(Exception):
    """Raised when a tenant cannot be resolved."""


class TenantAccessError(Exception):
    """Raised when a caller attempts unauthorized tenant access."""


class DuplicateTenantError(Exception):
    """Raised when a tenant identifier or slug already exists."""


class ProvisioningError(Exception):
    """Raised when tenant resources cannot be provisioned."""


class MigrationError(Exception):
    """Raised when a migration cannot safely be applied."""


def validate_identifier(value: str, label: str = "identifier") -> str:
    """Validate an identifier before using it in routing or SQL identifiers."""
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,39}", value):
        raise ValueError(
            f"{label} must contain 3-40 lowercase letters, digits, or underscores "
            "and begin with a letter."
        )
    return value


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    slug: str
    display_name: str
    architecture: Architecture
    region: str
    status: TenantStatus = TenantStatus.PROVISIONING
    schema_name: str | None = None
    database_name: str | None = None
    connection_key: str | None = None
    max_projects: int = 100
    max_members: int = 50

    def __post_init__(self) -> None:
        validate_identifier(self.tenant_id, "tenant_id")
        validate_identifier(self.slug, "slug")
        if not self.display_name.strip():
            raise ValueError("display_name cannot be empty.")
        if not self.region.strip():
            raise ValueError("region cannot be empty.")
        if self.max_projects < 1 or self.max_members < 1:
            raise ValueError("Tenant resource limits must be positive.")


@dataclass(frozen=True)
class Project:
    project_id: str
    tenant_id: str
    name: str
    status: str = "active"
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_ids: frozenset[str]
    platform_admin: bool = False


@dataclass
class TenantResources:
    """Simulated infrastructure resources for a tenant."""

    projects: dict[str, Project] = field(default_factory=dict)
    schema_name: str | None = None
    database_name: str | None = None
    connection_key: str | None = None
    applied_versions: set[int] = field(default_factory=set)


class TenantRegistry:
    """Central control-plane registry, separate from tenant application data."""

    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._slugs: dict[str, str] = {}

    def register(self, tenant: Tenant) -> None:
        if tenant.tenant_id in self._tenants:
            raise DuplicateTenantError(tenant.tenant_id)
        if tenant.slug in self._slugs:
            raise DuplicateTenantError(tenant.slug)
        self._tenants[tenant.tenant_id] = tenant
        self._slugs[tenant.slug] = tenant.tenant_id

    def get(self, tenant_id: str) -> Tenant:
        try:
            return self._tenants[tenant_id]
        except KeyError as exc:
            raise TenantNotFoundError(tenant_id) from exc

    def update_status(self, tenant_id: str, status: TenantStatus) -> Tenant:
        current = self.get(tenant_id)
        updated = Tenant(
            **{
                **asdict(current),
                "architecture": current.architecture,
                "status": status,
            }
        )
        self._tenants[tenant_id] = updated
        return updated

    def list_active(self) -> list[Tenant]:
        return sorted(
            (tenant for tenant in self._tenants.values()
             if tenant.status == TenantStatus.ACTIVE),
            key=lambda tenant: tenant.tenant_id,
        )


class SharedSchemaStore:
    """
    A small SQLite-backed demonstration of shared-table tenant isolation.

    SQLite does not provide PostgreSQL row-level security. Every operation
    therefore includes tenant_id in its query and validates ownership.
    """

    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE tenants (
                tenant_id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL
                    CHECK (status IN ('provisioning', 'active',
                                       'suspended', 'deprovisioned'))
            );

            CREATE TABLE projects (
                project_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                status TEXT NOT NULL DEFAULT 'active',
                created_at REAL NOT NULL,
                UNIQUE (tenant_id, name)
            );

            CREATE INDEX idx_projects_tenant_created
                ON projects (tenant_id, created_at DESC);
            """
        )

    def register_tenant(self, tenant: Tenant) -> None:
        self.connection.execute(
            "INSERT INTO tenants (tenant_id, slug, status) VALUES (?, ?, ?)",
            (tenant.tenant_id, tenant.slug, tenant.status.value),
        )
        self.connection.commit()

    def create_project(self, project: Project) -> None:
        with self.connection:
            tenant = self.connection.execute(
                "SELECT status FROM tenants WHERE tenant_id = ?",
                (project.tenant_id,),
            ).fetchone()
            if tenant is None:
                raise TenantNotFoundError(project.tenant_id)
            if tenant["status"] != TenantStatus.ACTIVE.value:
                raise TenantAccessError("Tenant is not active.")

            self.connection.execute(
                """
                INSERT INTO projects
                    (project_id, tenant_id, name, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project.project_id,
                    project.tenant_id,
                    project.name,
                    project.status,
                    project.created_at,
                ),
            )

    def list_projects(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT project_id, tenant_id, name, status, created_at
            FROM projects
            WHERE tenant_id = ?
            ORDER BY created_at DESC
            """,
            (tenant_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self.connection.close()


class MultiTenantPlatform:
    """Models tenant lifecycle and three physical data-isolation strategies."""

    def __init__(self) -> None:
        self.registry = TenantRegistry()
        self.resources: dict[str, TenantResources] = {}
        self.shared_store = SharedSchemaStore()
        self.schema_names: set[str] = set()
        self.database_names: set[str] = set()
        self.connection_catalog: dict[str, str] = {}

    def provision(
        self,
        tenant_id: str,
        slug: str,
        display_name: str,
        architecture: Architecture,
        region: str = "ap-south-1",
        max_projects: int = 100,
        max_members: int = 50,
    ) -> Tenant:
        validate_identifier(tenant_id, "tenant_id")
        validate_identifier(slug, "slug")

        tenant = Tenant(
            tenant_id=tenant_id,
            slug=slug,
            display_name=display_name,
            architecture=architecture,
            region=region,
            max_projects=max_projects,
            max_members=max_members,
        )

        resources = TenantResources()

        if architecture == Architecture.SEPARATE_SCHEMA:
            resources.schema_name = f"tenant_{tenant_id}"
            validate_identifier(resources.schema_name, "schema_name")
            if resources.schema_name in self.schema_names:
                raise ProvisioningError("Schema already exists.")
        elif architecture == Architecture.SEPARATE_DATABASE:
            resources.database_name = f"db_{tenant_id}"
            validate_identifier(resources.database_name, "database_name")
            resources.connection_key = f"conn_{tenant_id}"
            if resources.database_name in self.database_names:
                raise ProvisioningError("Database already exists.")

        self.registry.register(tenant)

        try:
            if architecture == Architecture.SHARED_SCHEMA:
                self.shared_store.register_tenant(tenant)
            elif architecture == Architecture.SEPARATE_SCHEMA:
                self.schema_names.add(resources.schema_name or "")
            else:
                self.database_names.add(resources.database_name or "")
                self.connection_catalog[resources.connection_key or ""] = (
                    resources.database_name or ""
                )

            active_tenant = self.registry.update_status(
                tenant_id, TenantStatus.ACTIVE
            )
            self.resources[tenant_id] = resources
            return active_tenant
        except Exception as exc:
            # A production provisioner should compensate for partially created
            # cloud resources and record failed cleanup operations.
            self.registry.update_status(tenant_id, TenantStatus.SUSPENDED)
            raise ProvisioningError(
                f"Provisioning failed for {tenant_id}: {exc}"
            ) from exc

    def resolve_tenant(
        self,
        principal: Principal,
        requested_tenant_id: str,
    ) -> Tenant:
        tenant = self.registry.get(requested_tenant_id)

        # Platform administrators still need explicit, audited administrative
        # operations; this flag is not an unrestricted application-data token.
        if (
            requested_tenant_id not in principal.tenant_ids
            and not principal.platform_admin
        ):
            raise TenantAccessError(
                f"User {principal.user_id} cannot access {requested_tenant_id}."
            )

        if tenant.status != TenantStatus.ACTIVE:
            raise TenantAccessError(
                f"Tenant {requested_tenant_id} is {tenant.status.value}."
            )

        return tenant

    def create_project(
        self,
        principal: Principal,
        tenant_id: str,
        name: str,
    ) -> Project:
        tenant = self.resolve_tenant(principal, tenant_id)
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Project name cannot be empty.")

        resources = self.resources[tenant_id]
        if len(resources.projects) >= tenant.max_projects:
            raise ValueError("Tenant project quota exceeded.")

        if any(
            project.name.casefold() == normalized_name.casefold()
            for project in resources.projects.values()
        ):
            raise ValueError("Project names must be unique within a tenant.")

        project = Project(
            project_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=normalized_name,
        )

        if tenant.architecture == Architecture.SHARED_SCHEMA:
            self.shared_store.create_project(project)

        resources.projects[project.project_id] = project
        return project

    def list_projects(
        self,
        principal: Principal,
        tenant_id: str,
    ) -> list[Project]:
        tenant = self.resolve_tenant(principal, tenant_id)
        resources = self.resources[tenant.tenant_id]

        if tenant.architecture == Architecture.SHARED_SCHEMA:
            records = self.shared_store.list_projects(tenant_id)
            return [
                Project(
                    project_id=record["project_id"],
                    tenant_id=record["tenant_id"],
                    name=record["name"],
                    status=record["status"],
                    created_at=record["created_at"],
                )
                for record in records
            ]

        return sorted(
            resources.projects.values(),
            key=lambda project: project.created_at,
            reverse=True,
        )

    def apply_migration(
        self,
        version: int,
        migration: Callable[[Tenant, TenantResources], None],
        tenant_ids: Iterable[str] | None = None,
    ) -> dict[str, str]:
        if version < 1:
            raise ValueError("Migration version must be positive.")

        targets = (
            list(tenant_ids)
            if tenant_ids is not None
            else [tenant.tenant_id for tenant in self.registry.list_active()]
        )
        results: dict[str, str] = {}

        for tenant_id in targets:
            tenant = self.registry.get(tenant_id)
            resources = self.resources[tenant_id]

            if tenant.status != TenantStatus.ACTIVE:
                results[tenant_id] = "skipped: tenant is not active"
                continue
            if version in resources.applied_versions:
                results[tenant_id] = "skipped: already applied"
                continue

            try:
                migration(tenant, resources)
                resources.applied_versions.add(version)
                results[tenant_id] = "applied"
            except Exception as exc:
                results[tenant_id] = f"failed: {exc}"

        return results

    def architecture_report(self) -> list[dict[str, Any]]:
        report = []
        for tenant in sorted(
            self.registry._tenants.values(),
            key=lambda item: item.tenant_id,
        ):
            resources = self.resources.get(tenant.tenant_id)
            report.append(
                {
                    "tenant": tenant.tenant_id,
                    "architecture": tenant.architecture.value,
                    "status": tenant.status.value,
                    "schema": resources.schema_name if resources else None,
                    "database": resources.database_name if resources else None,
                    "project_count": len(resources.projects) if resources else 0,
                    "migrations": sorted(resources.applied_versions)
                    if resources else [],
                }
            )
        return report

    def close(self) -> None:
        self.shared_store.close()


def demonstrate() -> None:
    print("\n=== Multi-Tenant Database Architecture Laboratory ===")

    platform = MultiTenantPlatform()
    try:
        alpha = platform.provision(
            "tenant_alpha", "alpha", "Alpha Analytics",
            Architecture.SHARED_SCHEMA, max_projects=2,
        )
        beta = platform.provision(
            "tenant_beta", "beta", "Beta Logistics",
            Architecture.SEPARATE_SCHEMA,
        )
        gamma = platform.provision(
            "tenant_gamma", "gamma", "Gamma Research",
            Architecture.SEPARATE_DATABASE,
        )

        alpha_user = Principal("user_alpha", frozenset({"tenant_alpha"}))
        beta_user = Principal("user_beta", frozenset({"tenant_beta"}))
        gamma_user = Principal("user_gamma", frozenset({"tenant_gamma"}))

        platform.create_project(alpha_user, alpha.tenant_id, "Fraud Analytics")
        platform.create_project(alpha_user, alpha.tenant_id, "Risk Dashboard")
        platform.create_project(beta_user, beta.tenant_id, "Fleet Operations")
        platform.create_project(gamma_user, gamma.tenant_id, "Quantum Experiments")

        print("\nProvisioned tenant resources:")
        print(json.dumps(platform.architecture_report(), indent=2))

        print("\nAlpha tenant projects:")
        for project in platform.list_projects(alpha_user, alpha.tenant_id):
            print(f"- {project.name} ({project.project_id})")

        print("\nAttempting cross-tenant access:")
        try:
            platform.list_projects(alpha_user, beta.tenant_id)
        except TenantAccessError as exc:
            print(f"Blocked: {exc}")

        print("\nAttempting quota violation:")
        try:
            platform.create_project(
                alpha_user, alpha.tenant_id, "Unauthorized Third Project"
            )
        except ValueError as exc:
            print(f"Blocked: {exc}")

        def add_reporting_index(
            tenant: Tenant,
            resources: TenantResources,
        ) -> None:
            # In a real deployment, each strategy needs a different target:
            # shared table, tenant schema, or tenant database.
            if tenant.architecture == Architecture.SHARED_SCHEMA:
                print(f"  Shared-table migration for {tenant.tenant_id}")
            elif tenant.architecture == Architecture.SEPARATE_SCHEMA:
                print(f"  Schema migration for {resources.schema_name}")
            else:
                print(f"  Database migration for {resources.database_name}")

        print("\nApplying migration version 3:")
        print(json.dumps(platform.apply_migration(3, add_reporting_index), indent=2))
        print("\nRepeating migration version 3:")
        print(json.dumps(platform.apply_migration(3, add_reporting_index), indent=2))

    finally:
        platform.close()


class MultiTenantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.platform = MultiTenantPlatform()
        self.platform.provision(
            "tenant_one", "one", "Tenant One",
            Architecture.SHARED_SCHEMA, max_projects=1,
        )
        self.platform.provision(
            "tenant_two", "two", "Tenant Two",
            Architecture.SEPARATE_SCHEMA,
        )
        self.one = Principal("user_one", frozenset({"tenant_one"}))
        self.two = Principal("user_two", frozenset({"tenant_two"}))

    def tearDown(self) -> None:
        self.platform.close()

    def test_cross_tenant_access_is_denied(self) -> None:
        with self.assertRaises(TenantAccessError):
            self.platform.list_projects(self.one, "tenant_two")

    def test_project_quota_is_enforced(self) -> None:
        self.platform.create_project(self.one, "tenant_one", "First")
        with self.assertRaises(ValueError):
            self.platform.create_project(self.one, "tenant_one", "Second")

    def test_case_insensitive_project_uniqueness(self) -> None:
        self.platform.create_project(self.two, "tenant_two", "Fleet")
        with self.assertRaises(ValueError):
            self.platform.create_project(self.two, "tenant_two", " fleet ")

    def test_migration_is_idempotently_recorded(self) -> None:
        migration = lambda tenant, resources: None
        first = self.platform.apply_migration(8, migration)
        second = self.platform.apply_migration(8, migration)
        self.assertEqual(first["tenant_one"], "applied")
        self.assertEqual(second["tenant_one"], "skipped: already applied")

    def test_duplicate_tenant_is_rejected(self) -> None:
        with self.assertRaises(DuplicateTenantError):
            self.platform.provision(
                "tenant_one", "other", "Duplicate",
                Architecture.SHARED_SCHEMA,
            )

    def test_inactive_tenant_is_rejected(self) -> None:
        self.platform.registry.update_status(
            "tenant_one", TenantStatus.SUSPENDED
        )
        with self.assertRaises(TenantAccessError):
            self.platform.list_projects(self.one, "tenant_one")


if __name__ == "__main__":
    demonstrate()
    print("\n=== Automated Tests ===")
    unittest.main(argv=["multi_tenant_database.py"], exit=False, verbosity=2)
