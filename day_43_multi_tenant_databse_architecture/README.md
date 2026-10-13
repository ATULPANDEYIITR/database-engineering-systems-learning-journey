# Multi-Tenant Database Design

## Architecture and Isolation Strategies

Multi-tenant database design allows one application platform to serve multiple customers while controlling access to each customer's data. A tenant may represent a company, department, institution, business unit, or individual customer account.

The central design decision is where tenant data resides and which database boundaries enforce isolation. Three common approaches are shared schema, separate schema, and separate database. They differ in operational cost, access control, customization, backup and recovery, performance isolation, and the effort required to manage a growing customer population.

This repository implements an executable architecture simulator in Python, an event-driven JavaScript model, a C++ placement engine, a Java enterprise domain model, and a PostgreSQL schema with tenant-scoped security controls.

## The Three Database Architectures

| Property | Shared schema | Separate schema | Separate database |
|---|---|---|---|
| Data placement | Tenants share tables and rows | Each tenant has its own schema in a database | Each tenant has an independent database |
| Tenant identification | A tenant key on each tenant-owned row | A schema or connection context identifies the tenant | A connection configuration identifies the tenant |
| Primary isolation mechanism | Row-level security, tenant-scoped queries, and database constraints | Schema permissions, controlled search paths, and tenant-aware routing | Database permissions, separate credentials, and connection routing |
| Resource overhead | Usually lowest | Moderate | Usually highest |
| Tenant-specific table structure | Difficult without shared-model extensions | More practical, with migration complexity | Most flexible |
| Independent backup and restore | Requires tenant-aware export or restore procedures | Possible at schema level with additional coordination | Usually the clearest independent recovery boundary |
| Performance isolation | Shared database resources | Shared database resources | Stronger resource-management options |
| Cross-tenant reporting | Relatively straightforward with authorized queries | Requires cross-schema coordination | Requires cross-database integration |
| Operational complexity | Low at the infrastructure level, high importance of row isolation | Higher schema and migration management | Higher provisioning, monitoring, connection, and recovery costs |
| Typical fit | Large numbers of relatively similar customers | Customers needing stronger organizational separation | Customers requiring dedicated credentials, recovery, or resource controls |

A separate schema is not equivalent to a separate database. Schemas within one PostgreSQL database share the database instance, connection infrastructure, and many resource constraints. Separate databases provide a stronger administrative boundary, but they do not automatically provide separate physical servers or eliminate the need for application-level authorization.

## Shared Schema: Tenant Isolation at Row Level

A shared-schema application stores multiple customers' records in the same tables. A `tenant_id` column associates each tenant-owned record with its owner.

For example, a project table can contain records for several customers:

| project_id | tenant_id | project_name |
|---|---|---|
| 101 | tenant_alpha | Fraud Analytics |
| 102 | tenant_alpha | Risk Dashboard |
| 201 | tenant_beta | Fleet Operations |

The primary key identifies an individual project. A foreign key links the project to its tenant. A composite unique constraint such as `UNIQUE (tenant_id, project_name)` allows two tenants to use the same project name while preventing duplicates within one tenant.

The application must never treat a user-supplied tenant identifier as sufficient authorization. It must establish that the authenticated principal belongs to the requested tenant and ensure that every tenant-owned read or write uses the authorized tenant context.

### PostgreSQL row-level security

The SQL implementation enables row-level security on `shared_app.projects`. Its policy compares each row's `tenant_id` with the current transaction's `app.tenant_id` setting.

The policy applies both when selecting existing records and when inserting or updating records. A query that omits an explicit tenant filter can still be restricted by row-level security, provided the executing database role is subject to the policy.

The implementation uses `SET LOCAL app.tenant_id` within a transaction so the value does not persist beyond that transaction. This is particularly important with pooled database connections, which are reused across requests.

A custom PostgreSQL setting is not itself a complete authentication mechanism. If an untrusted caller can execute arbitrary SQL using the application role, that caller may be able to change the setting. Production systems must establish tenant context through a trusted application boundary, restrict SQL access, avoid granting `BYPASSRLS`, and test the policy using the actual runtime role.

### Indexing shared tables

An index beginning with `tenant_id`, such as `(tenant_id, created_at DESC)`, supports queries that retrieve recent records for one tenant. It also helps PostgreSQL locate the subset of rows relevant to a tenant-specific operation.

Tenant-scoped indexes do not eliminate all shared-schema scaling concerns. A very large tenant can dominate table growth, maintenance operations, or database resource consumption. Partitioning, workload controls, archival policies, and selective migration to dedicated databases may become necessary.

## Separate Schema: Structural Separation Within One Database

In a separate-schema architecture, each tenant receives a schema such as `tenant_alpha` or `tenant_beta`. Each schema contains its own application tables.

The application resolves a tenant to an approved schema and executes queries through that tenant's authorized database context. Schema ownership and privileges must be configured deliberately. A schema name supplied directly by a client must never be inserted into SQL statements without trusted routing and identifier validation.

PostgreSQL bind parameters protect values, but ordinary SQL parameters cannot substitute for table or schema identifiers. Dynamic schema routing therefore requires a trusted mapping from a validated tenant identity to a provisioned schema. Where dynamic identifiers are unavoidable, use the database driver's identifier-composition facility and enforce a restrictive naming policy.

### Operational consequences

Separate schemas can make customer-specific extensions and selective exports easier than a single shared table model. They also multiply the number of database objects that must be migrated, monitored, inspected, and maintained.

A migration applied to one schema does not automatically update every other schema. The migration service must track progress per tenant, detect partial failures, and support safe retries. A fleet of schemas also creates a risk of schema drift, where tenants gradually end up with different structures.

Separate schemas do not provide independent database-server capacity. CPU, memory, storage throughput, connection limits, and database-wide maintenance remain shared.

## Separate Database: Connection-Level Isolation

In a separate-database architecture, each tenant has a dedicated database and an independently configured connection route. A registry entry can contain a logical connection key, region, lifecycle status, and database name.

The application resolves the authenticated tenant through the control plane, obtains its authorized connection configuration, and performs operations against that database. Credentials should be held in a secret manager or equivalent protected service rather than in application source code.

Separate databases make it easier to apply tenant-specific backup schedules, retention policies, credential rotation, recovery procedures, and maintenance windows. They also provide a practical path to moving high-volume customers to dedicated database instances when stronger resource isolation is required.

The costs include database provisioning, connection-pool management, credential rotation, monitoring, migration coordination, and potentially higher infrastructure charges. A large number of databases can create operational overhead even when each tenant's data volume is small.

A separate logical database does not necessarily imply a separate physical server. If strict performance or failure isolation is required, database placement and underlying infrastructure must be considered together.

## Placement Decisions and Cost Modeling

The C++ and Java implementations use a placement policy that considers estimated workload, monthly budget, and isolation requirements. The policy returns a recommended architecture and an illustrative monthly cost.

The estimates are intentionally simple planning inputs. They are not cloud-provider quotations or universal cost formulas. Actual cost depends on database technology, compute allocation, storage, backups, network transfer, availability requirements, support obligations, and operational staffing.

The key design rule is that mandatory isolation requirements must be evaluated before selecting the lowest-cost option. A customer that requires independent credentials or dedicated backup operations should not be placed in shared tables merely because the shared architecture is cheaper.

A practical placement process separates hard constraints from preferences:

- Mandatory security, residency, recovery, and performance requirements eliminate architectures that cannot satisfy them.
- Workload size and growth estimates inform capacity planning and the expected cost of each remaining architecture.
- Budget determines whether a feasible placement can be funded.
- The final decision records its rationale so later changes in workload or contractual requirements can trigger reassessment.

## Control Plane and Tenant Lifecycle

The control plane manages tenant identity, provisioning state, placement metadata, and lifecycle transitions. It is separate in responsibility from the application data plane, which stores tenant-owned projects and other business records.

The examples use the following lifecycle:

`provisioning -> active -> suspended -> active`

An active tenant may also be deprovisioned. A deprovisioned tenant cannot be reactivated through the simple lifecycle policy used by the C++ and Java models.

Provisioning should create infrastructure and permissions before the tenant becomes active. If provisioning fails partway through, the system must record the failure and clean up or reconcile resources that were already created. Marking a registry record active before its required database resources exist can expose a tenant to failed requests or incorrect routing.

Suspension should prevent new tenant operations even when the underlying data remains intact. Deprovisioning should be a controlled process that addresses data export, backups, retention obligations, legal holds, credential revocation, and verified deletion.

## Python Implementation

The Python program uses a `TenantRegistry` as the control plane and `TenantResources` as the architecture-specific resource model. A tenant receives either a simulated schema name, a database name and connection key, or shared-table placement.

`MultiTenantPlatform.resolve_tenant` checks membership and tenant status before data operations. Project creation also enforces tenant-specific quotas and case-insensitive name uniqueness.

For shared-schema behavior, `SharedSchemaStore` uses SQLite to create a relational example with a tenant foreign key and an index for tenant-scoped retrieval. The example is deliberately explicit about tenant filters because SQLite does not implement PostgreSQL row-level security.

The migration simulator tracks applied versions separately for each tenant. A second application of the same version is skipped, while a failed migration can be reported without pretending that every tenant has been upgraded successfully.

The built-in tests exercise cross-tenant denial, quota enforcement, duplicate names, repeated migrations, duplicate tenant registration, and inactive-tenant access.

Run the program with `python multi_tenant_database.py`. It uses only the Python standard library.

## JavaScript Implementation

The JavaScript model uses Node.js `EventEmitter` to make lifecycle operations observable. Provisioning, project creation, migration outcomes, and status changes generate audit events.

`TenantDirectory` maintains tenant identity and unique slugs. `ResourceRouter` determines whether a tenant uses the shared schema, a dedicated schema, or a dedicated database. `GovernanceEngine` performs authorization before executing tenant-scoped operations.

The model demonstrates why an earlier successful tenant lookup is not a permanent authorization grant. Membership and active status are rechecked when each operation runs.

JavaScript's `Map` and `Set` structures are used for keyed resources and membership checks. Project records and emitted audit-event snapshots are frozen to reduce accidental mutation in the demonstration. This does not make the complete engine immutable, nor does an in-memory event history replace durable audit storage.

The migration handler processes tenants independently and records failures without marking unsuccessful migrations as applied. This models a common operational challenge in multi-tenant systems: one customer can experience a migration failure while other customers successfully upgrade.

Run the program with `node multi_tenant_database.js`. No npm dependencies are required.

## C++ Placement and Governance Case Study

The C++ program models a SaaS provider deciding where to place three enterprise customers.

`PlacementRequest` captures the expected user population, expected project count, region, budget, and isolation requirements. `PlacementPolicy` evaluates the request and produces a `PlacementDecision`.

The policy selects a separate database when dedicated backups, independent credentials, or strict performance isolation are mandatory. For other workloads, it evaluates the estimated cost and workload size before selecting shared-schema or separate-schema placement.

`TenantPlatform` maintains tenant records, routing metadata, project collections, and migration versions. An `unordered_map` supports expected constant-time average lookup by tenant ID, while `set` collections enforce uniqueness for schema names and migration versions.

Project retrieval requires a principal with membership in the requested tenant. The model explicitly rejects cross-tenant access and inactive-tenant requests. A repeated migration version is recorded as already applied rather than applied a second time.

The C++ implementation is an in-memory decision and governance engine. Its estimated cost figures and storage behavior are illustrative. A production deployment would replace these simulated resource collections with transactional database operations, durable migration records, real connection routing, and infrastructure provisioning.

Compile using a C++17 compiler, for example `g++ -std=c++17 -Wall -Wextra -pedantic multi_tenant.cpp -o multi_tenant`.

## Java Enterprise Domain Model

The Java program uses records for immutable domain values, enums for architecture and lifecycle state, and service classes for placement, registration, authorization, and migrations.

`PlacementRequest` validates workload and budget inputs at construction. `PlacementPolicy` evaluates isolation requirements before selecting a cost-based placement. `TenantDirectory` enforces uniqueness of tenant IDs and slugs, while `TenantService` owns tenant routing and project operations.

The `ResourceRoute` record distinguishes schema routing from database routing. Shared-schema tenants resolve to the shared schema, separate-schema tenants receive a tenant-specific schema, and separate-database tenants receive a database-specific route.

The authorization service verifies membership and active status for every operation. The lifecycle transition method rejects invalid transitions instead of relying on arbitrary status changes. `MigrationService` tracks version completion independently for each tenant and avoids recording a version twice.

Java records and immutable membership sets help constrain accidental changes to domain inputs. They do not replace database transactions or concurrency control. In a concurrent production service, quota checks and project insertion must be performed atomically at the database layer to prevent simultaneous requests from exceeding limits.

Compile and run with Java 17 or later:

`javac MultiTenantDatabase.java`

`java MultiTenantDatabase`

## PostgreSQL Data Model

The SQL script defines two schemas:

- `control_plane` contains tenants, tenant memberships, migration history, and audit events.
- `shared_app` contains the shared-schema project data and project memberships.

The tenant registry stores the selected architecture, region, lifecycle status, optional schema name, optional database name, connection key, and project quota. A check constraint ensures that routing fields match the declared architecture. Partial unique indexes prevent duplicate schema or database names when those fields are populated.

The shared project table uses a UUID primary key, a tenant foreign key, a tenant-scoped unique constraint, and an index for recent projects by tenant. A composite foreign key from `project_members` ensures that a project membership cannot accidentally reference a project under a different tenant ID.

The membership table separates a user's tenant relationship from the projects belonging to that tenant. Its role constraint limits membership roles to defined values, and its partial index supports queries for active memberships by user.

### Row-level security and quotas

The SQL script enables and forces row-level security on the shared project tables. The policies use the current tenant setting to restrict visible rows and reject writes targeting a different tenant.

A trigger checks tenant status and project quota before insertion. It locks the tenant registry row before counting existing projects, serializing competing inserts for the same tenant. The quota check must remain consistent with the transaction isolation and concurrency behavior of the production system.

The example is intentionally limited to inserts for quota enforcement. Production systems should also review updates that change a record's tenant, project deletion behavior, bulk writes, and all other tables containing tenant-owned information. Every tenant-owned table needs an appropriate isolation policy or an equivalent enforceable access boundary.

### Transactions and migration records

The sample inserts set the tenant context with `SET LOCAL` inside a transaction. This demonstrates how transaction-scoped settings can prevent tenant context from accidentally remaining on a pooled connection after a transaction completes.

The migration table records a tenant, version, checksum, state, start time, completion time, and failure information. The composite primary key prevents duplicate history rows for the same tenant and version.

Migration history alone does not apply a schema change. A trusted migration orchestrator must execute the actual DDL against the correct target, use suitable locking, verify checksums, record failure details, and support controlled retries.

### Separate-schema and separate-database provisioning

The registry can represent separate-schema and separate-database tenants, but the SQL script does not automatically create their schemas or databases.

Creating a PostgreSQL database is an administrative operation that must be performed outside an ordinary transaction block. A separate-schema workflow creates the schema and configures ownership and permissions within the selected database. A separate-database workflow creates the database, configures its roles, stores its connection information securely, and runs the migration process against that database.

A central control-plane record should not be treated as proof that the external resource exists. Provisioning services should verify actual database resources and reconcile registry state with infrastructure state.

## Isolation, Security, and Failure Modes

### Cross-tenant access

The most dangerous shared-schema failure is a query that omits tenant scoping. Application-level filters alone can be missed in a large codebase, which is why row-level security and tenant-aware foreign keys provide valuable additional controls.

A separate schema can still be exposed by excessive privileges, an unsafe search path, or incorrect routing. A separate database can still be exposed by shared credentials that permit access to multiple customer databases.

Authorization must remain explicit regardless of architecture.

### Connection pools and tenant context

A connection pool reuses database connections across requests. Session-level tenant settings can leak between requests if they are not reset correctly. Transaction-scoped settings, disciplined transaction handling, and connection-pool tests help reduce this risk.

Database routing must use the authorized tenant registry, not an arbitrary connection string or database name supplied by a client.

### Migration failures and schema drift

A multi-tenant migration can partially succeed. One schema or database may upgrade successfully while another fails because of permissions, data quality, capacity, or a conflicting object.

The migration service should preserve tenant-specific status, record errors, verify the intended schema version, and distinguish a safe retry from a partially applied change. Large installations may need canary tenants, bounded rollout batches, and compatibility between old and new application versions.

### Backup and recovery

A shared-schema database backup usually captures many tenants together. Restoring a single tenant can require extracting the tenant's rows while preserving relationships, constraints, audit requirements, and referential integrity.

Separate schemas can simplify extraction but still share the same database-level backup and recovery environment. Separate databases provide a more direct independent recovery boundary, though recovery still depends on the backup system and underlying infrastructure.

### Performance and capacity

Shared-schema deployments have low per-tenant infrastructure overhead, but a high-volume tenant can affect other customers through shared resource consumption. Separate schemas do not remove this shared-resource problem.

Separate databases allow more independent tuning and capacity management. Stronger physical isolation may require dedicated database instances or infrastructure, not just independent logical databases.

### Tenant deletion and data retention

Deprovisioning is not simply a status update or an immediate `DROP DATABASE`. The process must consider retention rules, backups, data exports, legal holds, downstream integrations, credentials, and evidence of deletion.

A safe workflow first blocks new access, completes required exports and retention checks, revokes tenant-specific credentials, removes resources through an authorized provisioning process, and records the outcome in an auditable control plane.

## Operational Design Decisions

Architecture selection should be reviewed as workloads and contractual obligations change. A tenant may start in shared tables and later move to a dedicated database when its scale, recovery needs, or isolation requirements justify the cost.

A migration between architectures requires a controlled data transfer, validation of row counts and relationships, reconciliation of changes made during transfer, a routing cutover, and a rollback strategy. The target architecture should be ready before application traffic is redirected.

The three architectures are placement choices, not complete security solutions. Effective multi-tenant systems combine explicit identity and authorization, enforced data boundaries, reliable provisioning, controlled migrations, tenant-aware observability, and tested backup and recovery procedures.
