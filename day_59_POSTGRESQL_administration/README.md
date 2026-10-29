# PostgreSQL Administration: Users, Roles, Permissions, and Database Management

## Scope

This implementation models PostgreSQL administration as a set of distinct but connected responsibilities:

1. **Users and login roles** identify sessions that may connect to a database.
2. **Group roles** collect permissions that can be inherited by login roles.
3. **Permissions** determine which operations a role may perform on database objects.
4. **Database management** controls ownership, connections, connection limits, schemas, and administrative policy.
5. **Audit and validation** provide visibility into administrative changes and prevent invalid role configurations.

The central relationship is:

Repository-style administrative model

`Database → Schema → Object`

and

`Login Role → Group Role → Object Privileges`

with database-level privileges evaluated before object-level operations.

The implementation deliberately separates identity, role membership, privileges, and database-management state. A login role is not automatically equivalent to an administrator, and membership in a group role does not imply unrestricted database access.

---

## Administrative Model

The domain contains these principal entities:

| Entity | Purpose |
|---|---|
| Role | Represents a PostgreSQL identity or group |
| Login role | Role permitted to establish sessions |
| Group role | `NOLOGIN` role used to aggregate privileges |
| Role membership | Connects a login role to one or more group roles |
| Database | Logical database with an owner and connection policy |
| Schema | Namespace owned by a role |
| Object | Table, view, sequence, or function inside a schema |
| Object privilege | Grants an operation on an individual object |
| Database privilege | Controls operations such as `CONNECT` |
| Policy | Describes administrative access requirements |
| Audit event | Records administrative operations and outcomes |

A typical deployment represented by the code is:

`platform administrator`

`        ↓`

`application owner`

`        ↓`

`application_reader ← report_user`

`application_writer ← api_user`

The separation is intentional. The application roles contain permissions, while the login roles represent identities that use those permissions.

---

## Users and Login Roles

PostgreSQL calls its identity system roles. A role can have the `LOGIN` attribute and therefore function as a user for connection purposes.

A login role can have attributes such as:

- `LOGIN`
- `SUPERUSER`
- `CREATEDB`
- `CREATEROLE`
- `INHERIT`
- connection limits

A `NOLOGIN` role is useful as a permission container. It can be granted to login roles without becoming an independent session identity.

The implementations use:

| Role | Type | Purpose |
|---|---|---|
| `platform_admin` / `postgres` | Login | Administrative authority |
| `app_owner` | Group | Owns application resources |
| `app_readonly` | Group | Read-only access |
| `app_writer` | Group | Application write access |
| `api_service` / `api_user` | Login | Service identity |
| `report_service` / `report_user` | Login | Reporting identity |

The distinction prevents application sessions from receiving administrative capabilities simply because they need access to application tables.

---

## Role Attributes

The Python, JavaScript, C++17, and Java 17 implementations represent role attributes explicitly.

A role can therefore be evaluated before permission checking.

For example:

- A `NOLOGIN` role cannot establish a database session.
- A disabled login role cannot establish a new session.
- A superuser bypasses ordinary object privilege checks in the model.
- A role with `CREATEROLE` can manage role definitions in the simulated administrative layer.
- A connection limit constrains the number of active sessions associated with a role.

The PostgreSQL implementation also inspects actual server roles through `pg_roles`.

---

## Role Membership and Inheritance

Role membership is separate from object privileges.

For example:

`api_user → app_writer`

means that `api_user` can inherit permissions assigned to `app_writer` when inheritance is enabled.

The effective-role calculation traverses the membership graph.

The implementations reject:

`role_a → role_b → role_a`

because circular inheritance makes authorization reasoning ambiguous.

The Python, JavaScript, C++17, and Java implementations explicitly perform graph traversal. The PostgreSQL implementation uses a recursive CTE to detect reachable roles and a trigger to reject circular membership.

This graph-based approach also makes nested group roles possible.

Example:

`api_user → application_writer → application_data_access`

The effective permission set can therefore be calculated from the reachable role hierarchy rather than copied into every login role.

---

## Permissions

Permissions answer a different question from role identity.

A role may exist without having access to an object.

For an application table, the relevant privileges may include:

| Privilege | Meaning |
|---|---|
| `SELECT` | Read rows |
| `INSERT` | Add rows |
| `UPDATE` | Modify rows |
| `DELETE` | Remove rows |
| `REFERENCES` | Create foreign-key references |
| `TRIGGER` | Create or operate relevant triggers |
| `USAGE` | Use a schema or similar namespace object |
| `CREATE` | Create objects in an applicable namespace |
| `EXECUTE` | Execute a function or procedure |

The permission model therefore has two dimensions:

`Who is the role?`

and

`What may that role do?`

The implementations keep those dimensions separate.

---

## Database-Level Access

A user generally needs database-level access before meaningful object operations can occur.

The PostgreSQL model stores:

- database owner
- environment
- connection policy
- connection limit
- whether connections are accepted
- database-level privileges

The important distinction is that database access does not automatically provide table access.

For example:

`CONNECT on business_db`

does not mean:

`SELECT on application.customers`

The latter requires a separate applicable object privilege.

---

## Schema Access

Schemas provide namespaces for objects.

The model contains an `application` schema owned by `app_owner`.

A role can receive:

`USAGE on schema application`

without receiving unrestricted access to every table inside that schema.

This supports layered permission design:

`Database CONNECT`

↓

`Schema USAGE`

↓

`Table SELECT / INSERT / UPDATE / DELETE`

Each layer answers a different authorization question.

---

## Object Ownership

The model records an owner for databases, schemas, and objects.

Ownership is distinct from ordinary grants.

An application role can receive operational privileges while an owner role remains responsible for structural administration.

This reduces the need to give application identities elevated administrative capabilities.

The PostgreSQL script demonstrates the ownership relationship in its relational model and also creates actual `NOLOGIN` PostgreSQL group roles for administrative permission aggregation.

---

## Pulling Privileges Through Role Membership

The effective authorization process used by the source implementations is:

`Login Role`

↓

`Direct privileges`

`+`

`Inherited Group Roles`

↓

`Effective privileges`

For example:

`api_user`

inherits from:

`app_writer`

and therefore receives the writer role's `SELECT`, `INSERT`, and `UPDATE` permissions.

The application identity itself does not need to own those permissions directly.

This supports centralized administration.

Changing the `app_writer` role can change the access of every member that inherits it.

---

## Default Privileges

Normal grants affect existing objects.

PostgreSQL also supports `ALTER DEFAULT PRIVILEGES`, which controls privileges automatically applied to objects created in the relevant scope.

The SQL implementation demonstrates default privileges for future tables in `pg_admin_lab`.

This distinction is important:

| Mechanism | Primary effect |
|---|---|
| `GRANT` | Existing object |
| `REVOKE` | Removes an existing grant |
| `ALTER DEFAULT PRIVILEGES` | Controls privileges on subsequently created objects |

Default privileges do not retroactively modify every existing object.

That difference is a frequent source of administrative mistakes.

---

## Database Management

Database administration includes more than permissions.

The model includes:

- database ownership
- connection availability
- connection limits
- environment classification
- schema ownership
- object ownership
- administrative roles
- audit records

A database connection can fail even when the role has appropriate object privileges.

Examples include:

- role does not have `LOGIN`
- role is disabled
- database rejects connections
- database connection limit is reached
- role connection limit is reached

The Python, JavaScript, C++17, and Java programs simulate these failure conditions explicitly.

---

## Python Implementation

The Python program uses a domain-oriented model.

### Main mechanisms

`Role` is a dataclass representing identity attributes and role membership.

`DatabaseObject` identifies databases, schemas, tables, and functions.

`PermissionCatalog` stores object-level grants.

`RoleManager` manages:

- role creation
- membership
- cycle detection
- effective-role calculation
- password-policy validation
- administrative audit events

`AccessController` evaluates inherited permissions.

`Database` models database connection limits.

### Permission evaluation

The Python authorization process first checks whether the role exists and then evaluates:

1. direct role identity
2. superuser status
3. inherited roles
4. object privilege
5. requested operation

A failed authorization raises `PermissionError`.

### Validation

The script rejects:

- empty role names
- invalid connection limits
- invalid role membership
- membership cycles
- weak passwords
- unauthorized role-management operations

Assertions verify important domain rules after the demonstration workflow.

### Security model

The example stores a SHA-256 digest only to demonstrate password-state handling. A real PostgreSQL installation should use PostgreSQL's supported password authentication mechanisms, particularly SCRAM-based authentication, rather than implementing password storage in application code.

---

## JavaScript Implementation

The JavaScript implementation uses an event-driven design.

### Main mechanisms

`EventEmitter` provides an audit event channel.

`RoleDirectory` maintains roles and membership relationships.

`PermissionStore` maintains object grants and default privilege definitions.

`AccessPolicy` performs authorization decisions.

`DatabaseSessionManager` manages active sessions and connection limits.

### Event-driven auditing

Administrative actions emit audit events asynchronously.

This models a common service architecture where an administrative operation can publish an event to an audit subsystem without mixing audit storage with permission evaluation.

### JavaScript-specific design

`Map` is used for role and permission indexes.

`Set` represents role memberships and privilege collections.

`Promise` and `setImmediate()` model asynchronous event delivery.

`crypto.randomUUID()` provides unique simulated session identifiers.

The implementation does not require npm dependencies.

---

## C++17 Implementation

The C++ program treats administration as a governance engine.

### Domain structures

The implementation uses:

- `enum class` for privileges and object types
- `struct` for value-oriented objects
- classes for role management
- `std::map` for deterministic indexes
- `std::set` for role membership
- `std::vector` for audit events

`PermissionStore` owns grants, while `GovernanceEngine` evaluates them.

This separation prevents authorization policy from becoming dependent on the storage representation.

### Complexity

For the principal operations:

| Operation | Approximate complexity |
|---|---|
| Direct grant lookup | `O(log G)` |
| Effective-role traversal | `O(R + M)` |
| Connection lookup | `O(log U)` |
| Membership cycle detection | `O(R + M)` |

Where:

- `G` is the number of grant entries
- `R` is the number of reachable roles
- `M` is the number of membership edges
- `U` is the number of roles with active sessions

The program favors deterministic STL containers and explicit ownership of state.

### Failure handling

The program handles:

- unknown roles
- invalid role attributes
- unauthorized membership changes
- circular membership
- missing privileges
- invalid connection limits
- exhausted database connections
- `NOLOGIN` identities

Exceptions terminate invalid administrative operations instead of silently continuing with inconsistent state.

---

## Java 17 Implementation

The Java implementation models administration as an enterprise service layer.

### Domain model

Java records are used for immutable value objects such as:

- `DatabaseObject`
- `AuditEvent`
- `PermissionKey`

Classes represent mutable administrative aggregates such as `Role`, `RoleService`, and `PermissionService`.

The `Policy` interface provides a clear abstraction for authorization evaluation.

### Role service

`RoleService` owns:

- role creation
- membership changes
- effective-role traversal
- password validation
- role disabling
- audit events

The service validates administrative operations before mutating state.

### Permission service

`PermissionService` stores object-level grants and default privilege definitions.

It supports:

- grant
- revoke
- default privileges
- privilege lookup

### Authorization service

`AuthorizationService` separates policy evaluation from role storage.

Its effective permission calculation follows:

`role → inherited roles → object grants`

This allows application services to ask whether an operation is permitted without directly manipulating role internals.

### Explicit state

The Java implementation introduces `RoleState` with:

- `ACTIVE`
- `DISABLED`

A disabled role may remain represented in the administrative system while being prevented from establishing new sessions.

This is different from deleting the role and preserves administrative history.

---

## PostgreSQL Implementation

The SQL script provides the most database-oriented representation.

The schema is:

`pg_admin_lab`

### Core tables

| Table | Responsibility |
|---|---|
| `admin_roles` | Role attributes and administrative state |
| `role_memberships` | Role inheritance relationships |
| `databases` | Database ownership and connection policy |
| `schemas` | Namespace ownership |
| `objects` | Database objects |
| `object_privileges` | Object-level grants |
| `database_privileges` | Database-level grants |
| `approval_policies` | Administrative access policies |
| `role_policy_assignments` | Role-to-policy relationships |
| `admin_audit` | Administrative event history |

### Constraints

The schema uses:

- primary keys
- foreign keys
- unique constraints
- check constraints
- cascading deletes
- explicit privilege enumerations through `CHECK`

For example, role connection limits allow only:

`-1`

or a non-negative integer.

The database and role models therefore reject invalid connection limits at the database layer.

---

## Recursive Role Evaluation

The SQL function `pg_admin_lab.effective_role_ids()` uses a recursive CTE.

Conceptually:

`api_service`

↓

`app_writer`

↓

writer privileges

The recursive query follows role membership edges until all inherited roles are reached.

This supports nested group roles without duplicating permissions.

The function is marked `STABLE` because it reads database state without modifying it.

---

## Circular Membership Protection

The trigger function `pg_admin_lab.prevent_membership_cycle()` checks whether adding a membership edge would make the role hierarchy circular.

A proposed relationship such as:

`app_writer → api_service`

is rejected when:

`api_service → app_writer`

already exists.

This rule belongs at the database layer because administrative consistency should not depend solely on the correctness of one client application.

---

## Actual PostgreSQL Roles

The SQL script also demonstrates actual PostgreSQL role creation:

- `pg_admin_lab_owner`
- `pg_admin_lab_readonly`
- `pg_admin_lab_writer`

They are created as `NOLOGIN` group roles.

The script then grants schema and table privileges to these roles.

This illustrates the difference between:

`database model`

and

`server-level PostgreSQL roles`

The relational model provides an auditable learning representation, while the PostgreSQL `CREATE ROLE`, `GRANT`, and `ALTER DEFAULT PRIVILEGES` statements demonstrate native administrative mechanisms.

---

## `GRANT` and `REVOKE`

`GRANT` adds authorization.

`REVOKE` removes authorization.

The SQL model records grants explicitly in `object_privileges`.

For example:

`app_reader → application.customers → SELECT`

means that the reader role can read the customer table.

A writer role receives:

`SELECT`

`INSERT`

`UPDATE`

but not `DELETE`.

This intentionally demonstrates least privilege.

---

## Least Privilege

The examples use different permission levels for different identities.

### Reader

`SELECT`

### Writer

`SELECT`

`INSERT`

`UPDATE`

### Owner

Structural control such as schema creation and object ownership.

### Administrator

Role-management and database-management capabilities.

The service identities are therefore prevented from receiving administrative authority merely because they need to process application data.

---

## Security Considerations

Several security principles are represented directly.

### Separation of duties

Application users do not need to be superusers.

### Group-based authorization

Permissions are attached to group roles rather than duplicated across every login identity.

### Least privilege

Reader identities receive read permissions without write or delete permissions.

### Connection controls

Database and role connection limits restrict session consumption.

### Password policy

The application simulations reject weak passwords. Real PostgreSQL password management should rely on PostgreSQL authentication configuration rather than application-side hashing.

### Auditability

Administrative changes produce audit events in the application models and rows in the PostgreSQL audit model.

### Default privileges

Future objects can receive controlled permissions without requiring administrators to repeatedly grant access manually.

---

## Failure Conditions

The implementations deliberately exercise failures rather than treating only successful operations as valid.

| Failure | Expected behavior |
|---|---|
| Empty role name | Validation failure |
| Invalid connection limit | Validation failure |
| Unknown role | Lookup failure |
| `NOLOGIN` session attempt | Authorization failure |
| Disabled role session attempt | Authorization failure |
| Circular role membership | Rejected |
| Unauthorized role creation | Rejected |
| Unauthorized membership change | Rejected |
| Reader attempts `DELETE` | Denied |
| Database connection limit reached | Connection failure |
| Role connection limit reached | Connection failure |
| Weak password | Password-policy failure |

These conditions represent administrative invariants rather than optional application behavior.

---

## Permission Evaluation Workflow

The complete authorization path can be represented as:

`Session Identity`

↓

`Role Attributes`

↓

`Direct Role`

↓

`Inherited Group Roles`

↓

`Database Privilege`

↓

`Schema Privilege`

↓

`Object Privilege`

↓

`Requested Operation`

↓

`ALLOW / DENY`

A successful `CONNECT` check does not automatically imply successful table access.

Likewise, membership in a writer role does not automatically grant database-level administrative authority.

---

## Database Administration Workflow

A practical administrative workflow represented by the artifacts is:

`Create group role`

↓

`Define login role`

↓

`Grant group membership`

↓

`Configure database access`

↓

`Grant schema access`

↓

`Grant object privileges`

↓

`Configure default privileges`

↓

`Validate effective permissions`

↓

`Monitor sessions`

↓

`Audit administrative changes`

The separation of these stages makes permission errors easier to identify.

---

## Distinguishing Identity, Permission, and Administration

These concepts are intentionally not interchangeable.

| Concept | Question answered |
|---|---|
| Login role | Who can establish a session? |
| Group role | Which permission set should be inherited? |
| Membership | Which role permissions can be inherited? |
| Database privilege | Can the role perform a database-level operation? |
| Schema privilege | Can the role use or create within a namespace? |
| Object privilege | What can the role do to a specific object? |
| Ownership | Which role controls an object structurally? |
| Connection limit | How many concurrent sessions are allowed? |
| Default privilege | What access should future objects receive? |
| Audit record | What administrative action occurred? |

Keeping these concepts separate is central to reliable PostgreSQL administration.

---

## Practical Design Decisions

The artifacts use group roles for reusable permissions, login roles for identities, and separate authorization services for policy evaluation.

The Python implementation emphasizes executable simulation and assertions.

The JavaScript implementation emphasizes asynchronous events and policy evaluation.

The C++17 implementation emphasizes deterministic containers, explicit governance state, and algorithmic traversal.

The Java 17 implementation emphasizes enterprise domain services, immutable records, explicit role state, and policy abstractions.

The PostgreSQL implementation moves integrity rules into database constraints, triggers, recursive queries, indexes, and functions.

These perspectives describe the same administrative domain without requiring the implementations to be mechanical translations of each other.
