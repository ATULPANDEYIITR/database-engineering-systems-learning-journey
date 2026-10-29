#!/usr/bin/env python3
"""
PostgreSQL Administration: Users, Roles, Permissions, and Database Management

A self-contained simulation of PostgreSQL administration concepts:
- users and login roles
- group roles and role membership
- object privileges
- ownership
- default privileges
- database-management policies
- permission evaluation
- role inheritance
- connection limits
- password-policy validation
- audit events
- administrative workflows

The program does not require a PostgreSQL server or third-party packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class Privilege(str, Enum):
    CONNECT = "CONNECT"
    USAGE = "USAGE"
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    REFERENCES = "REFERENCES"
    TRIGGER = "TRIGGER"
    CREATE = "CREATE"
    EXECUTE = "EXECUTE"


class ObjectType(str, Enum):
    DATABASE = "database"
    SCHEMA = "schema"
    TABLE = "table"
    FUNCTION = "function"


class AuditAction(str, Enum):
    CREATE_ROLE = "CREATE_ROLE"
    GRANT = "GRANT"
    REVOKE = "REVOKE"
    ALTER_ROLE = "ALTER_ROLE"
    CONNECTION = "CONNECTION"
    DISCONNECT = "DISCONNECT"
    ACCESS_DENIED = "ACCESS_DENIED"


@dataclass(frozen=True)
class DatabaseObject:
    name: str
    object_type: ObjectType
    schema: str | None = None

    @property
    def identifier(self) -> str:
        if self.schema:
            return f"{self.schema}.{self.name}"
        return self.name


@dataclass
class Role:
    name: str
    login: bool = False
    superuser: bool = False
    createdb: bool = False
    createrole: bool = False
    inherit: bool = True
    connection_limit: int = -1
    password_hash: str | None = None
    memberships: set[str] = field(default_factory=set)

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Role name cannot be empty")
        if self.connection_limit < -1:
            raise ValueError("Connection limit must be -1 or non-negative")
        if not self.login and self.password_hash is not None:
            raise ValueError("NOLOGIN roles should not store a password")


@dataclass
class Grant:
    role: str
    object_id: str
    privileges: set[Privilege]
    grant_option: bool = False


@dataclass
class AuditEvent:
    action: AuditAction
    actor: str
    target: str
    success: bool
    detail: str


class PasswordPolicy:
    """A deliberately simple policy suitable for demonstrating validation."""

    MIN_LENGTH = 12

    @classmethod
    def validate(cls, password: str) -> None:
        if len(password) < cls.MIN_LENGTH:
            raise ValueError("Password must contain at least 12 characters")
        if not any(ch.isupper() for ch in password):
            raise ValueError("Password must contain an uppercase character")
        if not any(ch.islower() for ch in password):
            raise ValueError("Password must contain a lowercase character")
        if not any(ch.isdigit() for ch in password):
            raise ValueError("Password must contain a digit")


class PermissionCatalog:
    """Stores object grants independently from role membership."""

    def __init__(self) -> None:
        self.grants: dict[tuple[str, str], Grant] = {}

    def grant(
        self,
        role: str,
        obj: DatabaseObject,
        privileges: Iterable[Privilege],
        grant_option: bool = False,
    ) -> None:
        key = (role, obj.identifier)
        privilege_set = set(privileges)

        if not privilege_set:
            raise ValueError("At least one privilege is required")

        existing = self.grants.get(key)
        if existing:
            existing.privileges.update(privilege_set)
            existing.grant_option = existing.grant_option or grant_option
        else:
            self.grants[key] = Grant(
                role=role,
                object_id=obj.identifier,
                privileges=privilege_set,
                grant_option=grant_option,
            )

    def revoke(
        self,
        role: str,
        obj: DatabaseObject,
        privileges: Iterable[Privilege],
    ) -> None:
        key = (role, obj.identifier)
        existing = self.grants.get(key)
        if not existing:
            return

        existing.privileges.difference_update(set(privileges))
        if not existing.privileges:
            del self.grants[key]

    def privileges_for(self, role: str, object_id: str) -> set[Privilege]:
        grant = self.grants.get((role, object_id))
        return set() if grant is None else set(grant.privileges)


class RoleManager:
    def __init__(self) -> None:
        self.roles: dict[str, Role] = {}
        self.audit: list[AuditEvent] = []

    def create_role(self, actor: str, role: Role) -> None:
        role.validate()

        if role.name in self.roles:
            raise ValueError(f"Role already exists: {role.name}")

        actor_role = self.roles.get(actor)
        if actor_role and not actor_role.superuser and not actor_role.createrole:
            self._record(
                AuditAction.CREATE_ROLE,
                actor,
                role.name,
                False,
                "CREATEROLE privilege required",
            )
            raise PermissionError("Actor is not allowed to create roles")

        self.roles[role.name] = role
        self._record(
            AuditAction.CREATE_ROLE,
            actor,
            role.name,
            True,
            "Role created",
        )

    def grant_membership(self, actor: str, member: str, group: str) -> None:
        if member not in self.roles or group not in self.roles:
            raise KeyError("Both member and group roles must exist")

        if actor not in self.roles:
            raise KeyError(f"Unknown actor: {actor}")

        actor_role = self.roles[actor]
        if not actor_role.superuser and not actor_role.createrole:
            self._record(
                AuditAction.GRANT,
                actor,
                f"{member}->{group}",
                False,
                "CREATEROLE privilege required",
            )
            raise PermissionError("Actor cannot manage role membership")

        if member == group:
            raise ValueError("A role cannot be granted membership in itself")

        if self._would_create_cycle(member, group):
            raise ValueError("Role membership would create a cycle")

        self.roles[member].memberships.add(group)
        self._record(
            AuditAction.GRANT,
            actor,
            f"{member}->{group}",
            True,
            "Role membership granted",
        )

    def revoke_membership(self, actor: str, member: str, group: str) -> None:
        actor_role = self.roles.get(actor)
        if actor_role is None:
            raise KeyError(f"Unknown actor: {actor}")

        if not actor_role.superuser and not actor_role.createrole:
            raise PermissionError("Actor cannot manage role membership")

        self.roles[member].memberships.discard(group)
        self._record(
            AuditAction.REVOKE,
            actor,
            f"{member}->{group}",
            True,
            "Role membership revoked",
        )

    def effective_roles(self, role_name: str) -> set[str]:
        if role_name not in self.roles:
            raise KeyError(f"Unknown role: {role_name}")

        result: set[str] = set()
        stack = [role_name]

        while stack:
            current = stack.pop()
            if current in result:
                continue

            result.add(current)

            role = self.roles[current]
            if role.inherit:
                stack.extend(role.memberships)

        return result

    def can_login(self, role_name: str) -> bool:
        role = self.roles.get(role_name)
        return bool(role and role.login)

    def set_password(self, actor: str, role_name: str, password: str) -> None:
        PasswordPolicy.validate(password)

        actor_role = self.roles.get(actor)
        target = self.roles.get(role_name)

        if actor_role is None or target is None:
            raise KeyError("Unknown actor or target role")

        if actor != role_name and not actor_role.superuser:
            raise PermissionError("Only a superuser can set another user's password")

        # Demonstration hash only. Production PostgreSQL should use SCRAM-SHA-256.
        import hashlib

        target.password_hash = hashlib.sha256(password.encode()).hexdigest()
        self._record(
            AuditAction.ALTER_ROLE,
            actor,
            role_name,
            True,
            "Password policy accepted",
        )

    def _would_create_cycle(self, member: str, group: str) -> bool:
        to_visit = [group]
        visited: set[str] = set()

        while to_visit:
            current = to_visit.pop()
            if current == member:
                return True
            if current in visited:
                continue
            visited.add(current)
            to_visit.extend(self.roles[current].memberships)

        return False

    def _record(
        self,
        action: AuditAction,
        actor: str,
        target: str,
        success: bool,
        detail: str,
    ) -> None:
        self.audit.append(
            AuditEvent(
                action=action,
                actor=actor,
                target=target,
                success=success,
                detail=detail,
            )
        )


class AccessController:
    def __init__(
        self,
        roles: RoleManager,
        permissions: PermissionCatalog,
    ) -> None:
        self.roles = roles
        self.permissions = permissions

    def has_privilege(
        self,
        role_name: str,
        obj: DatabaseObject,
        privilege: Privilege,
    ) -> bool:
        role = self.roles.roles.get(role_name)
        if role is None:
            return False

        if role.superuser:
            return True

        for effective_role in self.roles.effective_roles(role_name):
            if privilege in self.permissions.privileges_for(
                effective_role,
                obj.identifier,
            ):
                return True

        return False

    def require(
        self,
        role_name: str,
        obj: DatabaseObject,
        privilege: Privilege,
    ) -> None:
        if not self.has_privilege(role_name, obj, privilege):
            self.roles._record(
                AuditAction.ACCESS_DENIED,
                role_name,
                obj.identifier,
                False,
                f"Missing {privilege.value} privilege",
            )
            raise PermissionError(
                f"{role_name} lacks {privilege.value} on {obj.identifier}"
            )


@dataclass
class Database:
    name: str
    owner: str
    allow_connections: bool = True
    connection_limit: int = -1
    active_connections: int = 0

    def connect(self, role: Role) -> None:
        if not role.login:
            raise PermissionError(f"{role.name} is NOLOGIN")
        if not self.allow_connections:
            raise PermissionError(f"Connections disabled for database {self.name}")

        if self.connection_limit != -1 and self.active_connections >= self.connection_limit:
            raise ConnectionError("Database connection limit reached")

        if role.connection_limit != -1:
            # This simulation treats one active session per role as the unit.
            if role.connection_limit <= 0:
                raise ConnectionError("Role connection limit reached")

        self.active_connections += 1

    def disconnect(self) -> None:
        if self.active_connections > 0:
            self.active_connections -= 1


def print_permission_matrix(
    controller: AccessController,
    objects: list[DatabaseObject],
    roles: list[str],
) -> None:
    print("\nPermission matrix")
    print("-" * 72)

    for role in roles:
        print(f"\nRole: {role}")
        for obj in objects:
            permissions = [
                privilege.value
                for privilege in Privilege
                if controller.has_privilege(role, obj, privilege)
            ]
            print(
                f"  {obj.identifier:<30} "
                f"{', '.join(permissions) if permissions else 'NONE'}"
            )


def run_demo() -> None:
    manager = RoleManager()

    # Administrative role. PostgreSQL superuser privileges are represented
    # explicitly because the program is a workflow simulation.
    manager.roles["postgres"] = Role(
        name="postgres",
        login=True,
        superuser=True,
        createrole=True,
        createdb=True,
    )

    manager.create_role(
        "postgres",
        Role(name="app_owner", login=False, createrole=False),
    )
    manager.create_role(
        "postgres",
        Role(name="app_readonly", login=False),
    )
    manager.create_role(
        "postgres",
        Role(name="app_writer", login=False),
    )
    manager.create_role(
        "postgres",
        Role(
            name="application_user",
            login=True,
            connection_limit=20,
        ),
    )
    manager.create_role(
        "postgres",
        Role(
            name="report_user",
            login=True,
            connection_limit=5,
        ),
    )

    manager.grant_membership("postgres", "application_user", "app_writer")
    manager.grant_membership("postgres", "report_user", "app_readonly")

    permissions = PermissionCatalog()

    database = DatabaseObject(
        name="business_db",
        object_type=ObjectType.DATABASE,
    )
    schema = DatabaseObject(
        name="app",
        object_type=ObjectType.SCHEMA,
    )
    customers = DatabaseObject(
        name="customers",
        object_type=ObjectType.TABLE,
        schema="app",
    )
    invoices = DatabaseObject(
        name="invoices",
        object_type=ObjectType.TABLE,
        schema="app",
    )

    permissions.grant(
        "app_owner",
        database,
        {Privilege.CONNECT},
    )
    permissions.grant(
        "app_owner",
        schema,
        {Privilege.USAGE, Privilege.CREATE},
    )

    permissions.grant(
        "app_readonly",
        database,
        {Privilege.CONNECT},
    )
    permissions.grant(
        "app_readonly",
        schema,
        {Privilege.USAGE},
    )
    permissions.grant(
        "app_readonly",
        customers,
        {Privilege.SELECT},
    )
    permissions.grant(
        "app_readonly",
        invoices,
        {Privilege.SELECT},
    )

    permissions.grant(
        "app_writer",
        database,
        {Privilege.CONNECT},
    )
    permissions.grant(
        "app_writer",
        schema,
        {Privilege.USAGE},
    )
    permissions.grant(
        "app_writer",
        customers,
        {Privilege.SELECT, Privilege.INSERT, Privilege.UPDATE},
    )
    permissions.grant(
        "app_writer",
        invoices,
        {Privilege.SELECT, Privilege.INSERT, Privilege.UPDATE},
    )

    controller = AccessController(manager, permissions)

    print("PostgreSQL Administration Simulation")
    print("=" * 72)

    print_permission_matrix(
        controller,
        [database, schema, customers, invoices],
        [
            "postgres",
            "application_user",
            "report_user",
            "app_readonly",
            "app_writer",
        ],
    )

    print("\nEffective roles")
    print("-" * 72)
    for role_name in ["application_user", "report_user"]:
        print(f"{role_name}: {sorted(manager.effective_roles(role_name))}")

    print("\nPermission checks")
    print("-" * 72)

    controller.require(
        "application_user",
        customers,
        Privilege.UPDATE,
    )
    print("application_user can UPDATE app.customers")

    controller.require(
        "report_user",
        customers,
        Privilege.SELECT,
    )
    print("report_user can SELECT app.customers")

    try:
        controller.require(
            "report_user",
            customers,
            Privilege.DELETE,
        )
    except PermissionError as exc:
        print(f"Expected denial: {exc}")

    print("\nConnection management")
    print("-" * 72)

    db = Database(
        name="business_db",
        owner="app_owner",
        connection_limit=2,
    )

    db.connect(manager.roles["application_user"])
    db.connect(manager.roles["report_user"])
    print(f"Active connections: {db.active_connections}")

    try:
        db.connect(manager.roles["application_user"])
    except ConnectionError as exc:
        print(f"Expected connection failure: {exc}")

    db.disconnect()
    print(f"Active connections after disconnect: {db.active_connections}")

    print("\nPassword policy")
    print("-" * 72)

    try:
        manager.set_password(
            "postgres",
            "application_user",
            "Weak1",
        )
    except ValueError as exc:
        print(f"Expected password rejection: {exc}")

    manager.set_password(
        "postgres",
        "application_user",
        "StrongPassword7",
    )
    print("Strong password accepted and stored as a hash")

    print("\nFailure handling")
    print("-" * 72)

    try:
        manager.grant_membership(
            "postgres",
            "app_writer",
            "application_user",
        )
    except ValueError as exc:
        print(f"Expected membership-cycle rejection: {exc}")

    try:
        manager.grant_membership(
            "report_user",
            "application_user",
            "app_writer",
        )
    except PermissionError as exc:
        print(f"Expected authorization rejection: {exc}")

    print("\nAudit trail")
    print("-" * 72)
    for event in manager.audit:
        status = "SUCCESS" if event.success else "DENIED"
        print(
            f"{event.action.value:<16} "
            f"{status:<7} "
            f"actor={event.actor:<18} "
            f"target={event.target:<30} "
            f"{event.detail}"
        )

    # Assertions act as executable checks for the key domain rules.
    assert manager.can_login("application_user")
    assert not manager.can_login("app_writer")
    assert controller.has_privilege(
        "application_user",
        customers,
        Privilege.UPDATE,
    )
    assert not controller.has_privilege(
        "report_user",
        customers,
        Privilege.DELETE,
    )
    assert db.active_connections == 1

    print("\nAll administrative workflow assertions passed.")


if __name__ == "__main__":
    run_demo()
