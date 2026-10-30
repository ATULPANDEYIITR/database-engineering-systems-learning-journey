# PostgreSQL Engineering Project

A production-style PostgreSQL order management system with transactional inventory operations, multi-tenant data isolation, controlled state transitions, auditing, operational monitoring, and connection-capacity planning.

The project treats PostgreSQL as an application platform and operational system. Data integrity is enforced at the database boundary, concurrent stock operations use explicit locking, tenant-owned records use Row-Level Security, and administrative utilities inspect database health and workload capacity.

## 1. System Scope

The implemented workload is a multi-tenant order management service. Customers create orders containing products. Orders begin as drafts, reserve inventory, and eventually become fulfilled or cancelled.

The implementation covers five engineering concerns:

| Area | Implemented capability |
|---|---|
| Relational design | Keys, foreign keys, unique constraints, checks, generated columns |
| Transaction processing | Atomic stock reservation, fulfillment and cancellation |
| Security | Tenant isolation policies, restricted schemas, role-oriented grants |
| Operations | Health inspection, connection monitoring, relation-size and lock reports |
| Deployment planning | Connection-pool capacity and rollout-surge calculations |

The database is the authority for order state, stock availability and transaction integrity. Application code does not calculate these rules independently and then assume that the database will accept them.

## 2. Architecture

The system separates application data from operational metadata.

    Application Services
           |
           | JDBC / psql
           v
    PostgreSQL Database
           |
           +-- app schema
           |     |
           |     +-- tenant
           |     +-- customer
           |     +-- product
           |     +-- warehouse
           |     +-- inventory
           |     +-- sales_order
           |     +-- order_item
           |     +-- order_reservation
           |     +-- audit_log
           |
           +-- ops schema
                 |
                 +-- schema_migration
                 +-- v_inventory_availability
                 +-- v_order_status_counts

    Administrative Utilities
           |
           +-- Python: deployment and diagnostic commands
           +-- JavaScript: event-driven health monitoring
           +-- C++17: connection-capacity planning
           +-- Java 17: transactional order command service

The `app` schema holds transactional records. The `ops` schema contains operational reporting and migration metadata. Administrative views are not automatically exposed to the application role.

## 3. Relational Model

### 3.1 Entity relationships

    tenant
      |
      +---- customer
                |
                +---- sales_order
                         |
                         +---- order_item
                         |       |
                         |       +---- product
                         |
                         +---- order_reservation
                                  |
                                  +---- inventory
                                           |
                                           +---- warehouse
                                           +---- product

A tenant can own multiple customers. Each order references a customer through a composite foreign key containing both `tenant_id` and `customer_id`. This prevents an order from referencing a customer belonging to a different tenant.

An order contains one or more order items. Each item identifies a product, quantity and agreed unit price. Its `line_total` is a stored generated column, so it cannot become inconsistent with the quantity and unit price through an application-side calculation error.

The reservation table records the stock allocation associated with each order line. Its foreign keys ensure that a reservation references an existing order item and an existing warehouse-product inventory record.

### 3.2 Important constraints

| Database object | Integrity rule |
|---|---|
| `customer` | Email addresses are normalized to lowercase and unique within a tenant |
| `product` | SKU is unique and unit price cannot be negative |
| `inventory` | On-hand and reserved quantities cannot be negative |
| `inventory` | Reserved quantity cannot exceed on-hand quantity |
| `sales_order` | Tenant and idempotency key form a unique pair |
| `sales_order` | Customer must belong to the same tenant |
| `order_item` | Quantity must be positive and line number must be valid |
| `order_item` | A product appears at most once in an order |
| `order_reservation` | Reservation quantity must be positive |
| `order_reservation` | Reservation state must be recognized |

Identity columns provide generated identifiers. They do not replace uniqueness or foreign-key constraints. The relational constraints remain effective regardless of whether a write originates from Python, JavaScript, Java, a SQL client or another service.

## 4. Order Lifecycle and Transaction Semantics

The database defines four order states:

| State | Meaning | Permitted next states |
|---|---|---|
| `draft` | Order lines can be edited | `reserved`, `cancelled` |
| `reserved` | Inventory has been allocated | `fulfilled`, `cancelled` |
| `fulfilled` | Reserved inventory has been consumed | None |
| `cancelled` | The order is no longer active | None |

The `enforce_order_status_transition` trigger rejects invalid state changes. A client cannot directly change an order from `draft` to `fulfilled`, or reopen a completed order through an ordinary update.

### 4.1 Inventory accounting

The inventory model uses two quantities:

- `on_hand` represents physical stock still recorded at a warehouse.
- `reserved` represents the part of that stock allocated to active orders.

Available stock is:

    available = on_hand - reserved

For example, an inventory record with 100 units on hand and 15 reserved has 85 available units.

Reservation increases `reserved` without reducing `on_hand`. Fulfillment reduces both quantities by the fulfilled amount. Cancellation decreases `reserved` without changing `on_hand`.

This model avoids treating an allocation as a physical stock movement.

### 4.2 Atomic reservation

`app.reserve_order(order_id, warehouse_id)` performs the following work inside the caller's transaction:

1. Locks the order row.
2. Checks that the order is visible to the current tenant.
3. Verifies that the order is in the `draft` state.
4. Locks order items in product order.
5. Updates available inventory only when sufficient stock exists.
6. Inserts one reservation for each order item.
7. Changes the order state to `reserved`.

If any product lacks sufficient stock, the function raises an exception. The caller must roll back the transaction. PostgreSQL then reverses earlier changes from that reservation attempt, including inventory updates and inserted reservations.

The deterministic product ordering reduces the chance of deadlocks when concurrent transactions reserve overlapping products.

### 4.3 Fulfillment and cancellation

`app.fulfill_order(order_id)` locks the order and its active reservations. It consumes inventory and marks reservations as consumed. It changes the order state only after processing the reservations.

`app.cancel_order(order_id)` releases active reservations and changes the order state to `cancelled`. A fulfilled order cannot be cancelled through this operation because its stock has already been consumed.

The functions are designed to be called within an explicit transaction. They do not commit independently, so the application controls the transaction boundary.

### 4.4 Idempotency

The unique constraint on `(tenant_id, idempotency_key)` prevents duplicate order creation when an application retries a request.

The key is scoped to a tenant because two independent tenants may legitimately use the same request identifier.

The sample SQL uses deterministic keys such as `seed-reserved`. Its inserts use conflict handling so the sample records are not duplicated on repeated executions.

## 5. Python Implementation

The Python file is a command-line administration utility built with the standard library.

### 5.1 Commands

| Command | Purpose |
|---|---|
| `self-test` | Validates local connection-capacity calculations without a database |
| `migrate` | Runs the PostgreSQL SQL file using `psql` |
| `doctor` | Checks server version, connection use, blocking sessions and transaction age |
| `report` | Produces a structured operational report |

Running the file without arguments executes `self-test`.

The `PsqlClient` class invokes the PostgreSQL client with `subprocess.run`. It uses an argument array instead of a shell command, applies execution timeouts and enables `ON_ERROR_STOP` so SQL errors produce a non-zero result.

The program reads connection details through the libpq environment. It does not print passwords or accept them as ordinary command-line arguments.

### 5.2 Connection budget validation

`ConnectionBudget` estimates total application pool demand:

    application_connections =
        application_instances * pool_size_per_instance

It subtracts superuser and maintenance reserves from the server's `max_connections` setting before deciding whether the estimated pool demand fits.

This check is a deployment estimate, not a live connection-pool measurement. It should be compared with real connection activity and application pool metrics before a server configuration change.

### 5.3 Diagnostic behavior

The health query collects:

- PostgreSQL version and database name.
- Maximum and currently used connections.
- Blocked session count.
- Age of the oldest open transaction.
- Database size.
- Whether the connected server is in recovery.

The doctor command applies explicit thresholds and returns a non-zero exit code when a required check fails.

The report command retrieves connection states, blocked sessions, long transactions, relation sizes and replication information as JSON.

## 6. JavaScript Implementation

The JavaScript file provides an asynchronous monitoring service for Node.js.

### 6.1 Event-driven monitoring

`PostgresMonitor` extends `EventEmitter`. It collects database metrics and emits events after evaluating the sample:

| Event | Meaning |
|---|---|
| `sample` | A health sample was collected |
| `healthy` | No configured warning condition was detected |
| `alert` | One or more health conditions require attention |
| `report` | An operational report was collected |

`HealthPolicy` contains the evaluation rules. The current policy reports high connection utilization, blocked sessions, old transactions and standby connections.

The policy is separate from the query client. This allows monitoring thresholds to change without rewriting SQL execution or output handling.

### 6.2 Asynchronous execution

The script uses Node.js `execFile` through `promisify`. The execution API accepts an executable and argument array, avoiding shell interpretation of database commands.

The `watch` command collects samples sequentially. It does not start another database query while a previous sample is still running. This avoids overlapping monitoring work when the database is slow.

The polling interval is validated and bounded. `SIGINT` stops the monitoring loop cleanly.

### 6.3 Failure handling

A missing `psql` executable, query timeout, invalid JSON response and PostgreSQL execution error are treated as failures. Credentials remain in the process environment and are not included in monitoring output.

## 7. C++17 Connection-Capacity Planner

The C++ program evaluates PostgreSQL connection demand using explicit workload models.

It models three application workloads:

- API services.
- Background workers.
- Reporting services.

Each workload defines its instance count and pool size per instance.

### 7.1 Rolling-deployment demand

A rolling deployment may temporarily run more application instances than the steady-state configuration. The planner therefore calculates peak instances using a surge factor.

    peak_instances =
        ceil(configured_instances * rollout_surge_factor)

    peak_connections =
        peak_instances * pool_size_per_instance

The default surge factor is 1.5. It models temporary deployment overlap, not an assertion that every deployment platform uses that exact behavior.

### 7.2 Protected server capacity

The planner distinguishes application demand from protected capacity:

    application_capacity =
        max_connections
        - superuser_reserve
        - maintenance_reserve

The plan is safe only when the peak application demand does not exceed the remaining application capacity.

The program validates integer inputs, duplicate workload names, empty workloads, invalid reserve values and unreasonable planning parameters. `--strict` returns a non-zero status when a capacity plan is unsafe.

### 7.3 Engineering limitation

The C++ implementation is a configuration planner, not a PostgreSQL connection client. It does not replace measurements from `pg_stat_activity`, application pool instrumentation or load testing. Its value is to identify an obviously unsafe pool configuration before deployment.

## 8. Java 17 Transaction Service

The Java implementation provides an enterprise-oriented command service for the database's inventory operations.

### 8.1 Database connectivity

`DatabaseConfiguration` reads the JDBC URL and credentials from environment variables. `ConnectionProvider` separates connection creation from transaction execution.

The implementation uses `DriverManager` so it compiles with Java 17 without a third-party compile-time dependency. A PostgreSQL JDBC driver is still required at runtime for live database commands.

The connection provider is an interface so a deployment can supply a pooled connection provider without changing the order command service.

### 8.2 Transaction boundaries

`TransactionExecutor` establishes an explicit transaction with `READ COMMITTED` isolation. It configures local statement and lock timeouts before executing the business operation.

The executor commits when the database function succeeds. On SQL or runtime failure, it attempts rollback and preserves rollback errors as suppressed exceptions.

### 8.3 Retry policy

The retry policy recognizes two PostgreSQL transaction failures:

| SQLSTATE | Meaning | Behavior |
|---|---|---|
| `40001` | Serialization failure | Bounded retry |
| `40P01` | Deadlock detected | Bounded retry |
| `23505` | Unique constraint violation | No retry |
| `23503` | Foreign-key violation | No retry |
| `P0001` | Application-level business rule failure | No retry |

Retries use a bounded delay with jitter. Constraint violations and business rule failures are not treated as transient infrastructure failures.

The policy deliberately avoids retrying arbitrary network or connection failures. A connection failure during commit can make the transaction outcome uncertain. Retrying such an operation without an idempotency strategy can produce duplicate effects.

### 8.4 Database function integration

`OrderCommandService` uses prepared statements to call:

- `app.reserve_order`
- `app.fulfill_order`
- `app.cancel_order`

The business rules remain in PostgreSQL. The Java service validates command identifiers, establishes transaction boundaries and translates database operations into application-level commands.

## 9. PostgreSQL Security Model

### 9.1 Row-Level Security

Row-Level Security is enabled and forced on:

- `app.customer`
- `app.sales_order`
- `app.order_item`
- `app.order_reservation`

The policies filter tenant-owned records through `app.current_tenant_id()`.

Child records use an existence check against their parent order, preventing a tenant from accessing another tenant's order items or reservations through a direct child-table query.

The sample implementation reads the tenant identifier from the `app.tenant_id` session setting. This is appropriate only when a trusted application layer controls the database session and sets the value from authenticated context. A user with unrestricted SQL access can change an ordinary custom session setting. It must not be treated as an independent authentication mechanism.

For direct, untrusted database access, tenant identity should be derived from a separately authenticated database principal or an equivalent database-enforced mapping.

### 9.2 Role separation

The SQL file does not create login roles or assign passwords. These are deployment decisions.

When `app_runtime` already exists, the script applies restricted application grants. The runtime role receives access to application operations but does not receive unrestricted access to the audit log or operational schema.

The application runtime role should not own the schema or tables. A separate migration owner should administer DDL.

### 9.3 Function security

The inventory workflow functions use `SECURITY DEFINER` with a fixed search path and schema-qualified object references. Public execution is revoked, and execution is granted to `app_runtime` only when that role exists.

This permits the application to invoke controlled inventory operations without granting unrestricted direct updates to inventory records.

## 10. PostgreSQL Operational Design

### 10.1 Index strategy

The SQL file creates indexes for known access patterns rather than indexing every column.

| Index | Query pattern |
|---|---|
| `idx_sales_order_tenant_created` | Tenant order history ordered by creation time |
| `idx_order_item_product` | Reverse lookup of orders containing a product |
| `idx_reservation_active_product` | Active reservations by product and warehouse |
| `idx_audit_entity_time` | Audit history for an individual entity |

The partial reservation index excludes completed and released reservations. This keeps the index focused on the active reservation workload.

The primary keys and unique constraints already create their supporting indexes. Creating duplicate indexes for those same key combinations would add write overhead without providing a useful access path.

### 10.2 Transaction and locking considerations

Inventory operations update records under row-level locks. They use a consistent lock order to reduce deadlock probability.

A deadlock is still possible when multiple database transactions acquire other resources in different orders. The Java service retries PostgreSQL deadlock and serialization errors within a bounded policy.

Transactions should remain short. External network requests, user interaction and lengthy computation should not occur while inventory rows are locked.

### 10.3 Monitoring queries

Operational inspection uses PostgreSQL system views and functions:

| Source | Operational purpose |
|---|---|
| `pg_stat_activity` | Session state and transaction age |
| `pg_blocking_pids()` | Identifying blocking sessions |
| `pg_database_size()` | Database-level size |
| `pg_stat_user_tables` | User-table relation inspection |
| `pg_total_relation_size()` | Table, index and auxiliary storage size |
| `pg_is_in_recovery()` | Primary or standby detection |
| `pg_last_wal_receive_lsn()` | Standby WAL receive position |
| `pg_last_wal_replay_lsn()` | Standby WAL replay position |

Monitoring permissions depend on the database role and PostgreSQL configuration. Some session details may require elevated monitoring privileges.

## 11. Schema Change Management

The `ops.schema_migration` table stores a migration version, SHA-256 checksum, application timestamp and database user.

A production migration runner should:

1. Compute the checksum from the exact migration file.
2. Acquire a database advisory lock to prevent concurrent migration runners.
3. Check whether the migration version already exists.
4. Compare the stored checksum with the supplied checksum.
5. Reject a changed migration that has already been applied.
6. Apply compatible DDL in a transaction.
7. Record the migration only after successful execution.

The Python `migrate` command runs the complete SQL baseline file. It is not a versioned migration framework and does not calculate or verify migration checksums. The migration metadata table provides the database structure for a separate version-aware deployment process.

Schema deployment should be separated from ordinary application startup. Application services should not require DDL ownership.

## 12. Execution and Validation

Save the six deliverables in one directory:

| File | Purpose |
|---|---|
| `postgres_admin.py` | Python operations utility |
| `postgres_monitor.js` | Node.js health monitor |
| `postgres_capacity.cpp` | C++17 connection planner |
| `PostgresOperations.java` | Java transaction service |
| `postgresql.sql` | Database schema and sample workflow |
| `README.md` | Project documentation |

### 12.1 Python

Run the local validation:

`python postgres_admin.py self-test`

Apply the SQL baseline:

`python postgres_admin.py migrate`

Inspect the server:

`python postgres_admin.py doctor`

Generate an operational report:

`python postgres_admin.py report`

The live commands require `psql` on `PATH` and valid libpq connection configuration. The default migration path is the `postgresql.sql` file in the same directory.

### 12.2 JavaScript

Run local policy tests:

`node postgres_monitor.js self-test`

Inspect health:

`node postgres_monitor.js health`

Generate a report:

`node postgres_monitor.js report`

Monitor at 15-second intervals:

`node postgres_monitor.js watch 15000`

The watch interval must be between 5 and 300 seconds.

### 12.3 C++17

Compile:

`g++ -std=c++17 -O2 -Wall -Wextra -pedantic postgres_capacity.cpp -o postgres_capacity`

Run the default capacity plan:

`./postgres_capacity`

Test a constrained server configuration:

`./postgres_capacity --max-connections 100 --strict`

On Windows, run the resulting executable as `postgres_capacity.exe`.

### 12.4 Java 17

Compile:

`javac PostgresOperations.java`

Run local validation:

`java PostgresOperations self-test`

For live database access, make a compatible PostgreSQL JDBC driver available on the runtime classpath and set `PGJDBC_URL`, `PGUSER` and `PGPASSWORD` as appropriate.

Inspect the database:

`java PostgresOperations health`

Execute inventory operations:

`java PostgresOperations reserve ORDER_ID WAREHOUSE_ID`

`java PostgresOperations fulfill ORDER_ID`

`java PostgresOperations cancel ORDER_ID`

The order identifier and warehouse identifier must refer to existing records visible to the configured tenant context.

### 12.5 PostgreSQL

Execute the SQL file:

`psql -X -v ON_ERROR_STOP=1 -f postgresql.sql`

The script requires PostgreSQL 14 or later. It creates the schemas, tables, constraints, indexes, functions, triggers, policies, views and deterministic sample records in one transaction.

The sample workflow creates draft, reserved, fulfilled and cancelled orders. It also demonstrates tenant context selection and inventory accounting.

The SQL file does not configure server-wide settings, create login roles or perform external backups.

## 13. Failure Conditions and Recovery

| Condition | Database behavior | Operational response |
|---|---|---|
| Invalid order transition | Trigger raises an exception | Correct the requested workflow state |
| Insufficient stock | Reservation function raises an exception | Roll back and review stock availability |
| Duplicate tenant idempotency key | Unique constraint rejects the insert | Return or retrieve the existing order |
| Invalid customer relationship | Foreign key rejects the order | Verify tenant and customer identifiers |
| Duplicate order product | Unique constraint rejects the line | Update the existing draft line |
| Concurrent reservation conflict | Row locking serializes inventory changes | Retry only recognized transaction failures |
| Deadlock | PostgreSQL aborts one transaction | Use bounded retry and inspect lock ordering |
| Tenant mismatch | RLS or function validation rejects the request | Verify authenticated tenant context |
| Long-running transaction | Monitoring detects its age | Inspect transaction owner and application state |
| Connection exhaustion | New connections may be refused | Review pool sizes and reserve capacity |
| Migration checksum mismatch | Migration runner should refuse deployment | Investigate the modified migration before proceeding |

A failed database transaction must be rolled back before the same connection is reused. A failed transaction is not repaired by issuing another ordinary statement inside the aborted transaction.

## 14. Production Boundaries

This project provides an executable relational baseline and operational examples. It is not a complete deployment platform.

Production operation still requires decisions and controls that depend on the environment:

- Automated backups with documented retention and encryption.
- Point-in-time recovery using an appropriate base-backup and WAL archive strategy.
- Restore testing rather than relying only on successful backup jobs.
- A tested primary and standby topology where high availability is required.
- Replication monitoring and a controlled failover procedure.
- Connection pooling sized against actual workload concurrency.
- Credential rotation and restricted network access.
- Migration review, release coordination and rollback planning.
- Monitoring for replication lag, disk utilization, WAL growth, vacuum progress and transaction age.
- Operational access controls for database inspection and emergency maintenance.

The connection-capacity planner estimates configured pool demand. It does not measure query throughput or determine an optimal `max_connections` value. Increasing the connection limit without measuring memory and workload behavior can reduce server stability.

The SQL sample uses a custom tenant session setting as a trusted-application boundary. Deployments that permit arbitrary database clients must use an independently authenticated tenant identity model.

## 15. Technical Design Decisions

| Decision | Reason |
|---|---|
| Composite tenant/customer foreign key | Prevents cross-tenant customer references |
| Stored generated line total | Keeps derived line values consistent |
| Unique idempotency key per tenant | Prevents duplicate order creation during retries |
| Separate reservation table | Preserves allocation history and lifecycle |
| Explicit order-state trigger | Centralizes permitted state transitions |
| Ordered inventory locking | Reduces deadlock risk for overlapping reservations |
| Transactional database functions | Keeps multi-table inventory operations atomic |
| Row-Level Security | Enforces tenant filtering at the database boundary |
| Restricted operational schema | Separates application access from administrative reporting |
| Partial active-reservation index | Limits index entries to the active reservation workload |
| Java prepared statements | Separates data values from SQL syntax |
| Bounded Java retries | Avoids unbounded transaction replay |
| Sequential JavaScript polling | Prevents overlapping monitoring requests |
| C++ rollout-surge model | Accounts for temporary connection demand during deployment |

The result is a database-centered engineering design in which integrity rules, transactional behavior, application access and operational inspection have explicit boundaries.
