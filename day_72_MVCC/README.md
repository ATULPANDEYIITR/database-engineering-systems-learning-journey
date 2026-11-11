# Multi-Version Concurrency Control (MVCC)

## 1. Introduction

Multi-Version Concurrency Control (MVCC) is a database concurrency mechanism that maintains multiple versions of a logical record. Transactions access versions according to their visibility rules rather than requiring every reader to wait for concurrent writers.

MVCC is designed to support concurrent database operations while maintaining transactional consistency.

A database using MVCC can allow:

- One transaction to read a previously committed version.
- Another transaction to create a newer version.
- Multiple readers to access compatible snapshots.
- Writers to create new versions without immediately overwriting versions required by existing readers.
- Database maintenance processes to remove versions that are no longer required.

PostgreSQL uses MVCC as a central component of its transaction processing architecture.

The implementations in this repository model transaction snapshots, version chains, visibility, isolation, conflict detection, rollback, and version cleanup.

## 2. Core Concepts

### 2.1 Multi-version storage

A traditional single-version representation stores one current value for each logical record.

An MVCC representation maintains a sequence of versions.

For example, consider a bank account:

| Version | Balance | Creating transaction | Deleting transaction |
|---|---:|---|---|
| V1 | 1,000 | T1 | T2 |
| V2 | 1,200 | T2 | T3 |
| V3 | 1,500 | T3 | Active |

The logical record has three historical versions. A transaction does not automatically see the newest physical version. It sees the version permitted by its snapshot.

The version chain can be represented as:

`Account → V1 → V2 → V3`

The arrows represent historical succession, not necessarily physical memory pointers.

### 2.2 Transaction identifiers

Transactions receive identifiers that distinguish their operations.

Two important version attributes are:

| Attribute | Meaning |
|---|---|
| `xmin` | Transaction that created the version |
| `xmax` | Transaction that deleted or superseded the version |

In PostgreSQL, tuple visibility also depends on transaction commit status, snapshots, transaction identifiers, and other internal metadata.

The implementations use simplified transaction identifiers to demonstrate these relationships.

### 2.3 Transaction snapshots

A snapshot describes which transactions are visible to a particular transaction.

A transaction may continue reading an older committed version even after another transaction commits a newer version.

Consider:

1. T1 begins and reads a balance of 1,000.
2. T2 updates the balance to 1,200.
3. T2 commits.
4. T1 reads the balance again.

Under repeatable read, T1 continues seeing 1,000.

A new transaction started after T2 commits can see 1,200.

This behavior separates physical version creation from logical visibility.

### 2.4 Version visibility

A version is visible only when its creating transaction satisfies the transaction's snapshot rules and its deleting transaction does not make it invisible.

A simplified visibility evaluation considers:

- Whether the creating transaction is the current transaction.
- Whether the creating transaction was active when the snapshot was established.
- Whether the creating transaction committed.
- Whether the deleting transaction is the current transaction.
- Whether the deleting transaction was active when the snapshot was established.
- Whether the deleting transaction committed.

A transaction's own uncommitted writes can be visible to that transaction even though other transactions cannot see them.

### 2.5 Version chains

A version chain maintains multiple representations of the same logical record.

The Python, JavaScript, C++, and Java implementations store versions in ordered collections.

PostgreSQL manages tuple versions internally within its storage engine.

An important distinction is that an application-level history table is not PostgreSQL's internal MVCC version chain. The SQL implementation maintains an audit history separately from the native tuple-version mechanism.

## 3. Transaction Lifecycle

The lifecycle implemented across the programming languages is:

`BEGIN → READ / WRITE → VALIDATE → COMMIT`

An unsuccessful transaction follows:

`BEGIN → READ / WRITE → ERROR → ROLLBACK`

### 3.1 Begin

Beginning a transaction establishes:

- A transaction identifier.
- An isolation level.
- A starting timestamp.
- A snapshot of relevant active transactions.
- Empty read and write sets.

### 3.2 Read

A read operation searches the version chain for a version visible under the transaction's snapshot.

The read operation does not necessarily retrieve the newest physical version.

### 3.3 Write

A write is buffered within the transaction.

The implementation records the affected key and the proposed value.

A buffered write is not equivalent to a committed database change.

Other transactions must not observe an uncommitted version.

### 3.4 Validation

Before committing, an optimistic concurrency model checks whether another committed transaction has modified the affected record since the original observation.

Serializable transactions also require additional dependency validation.

### 3.5 Commit

A successful commit:

- Validates write dependencies.
- Establishes the committed transaction state.
- Creates new logical versions.
- Marks previous versions as superseded.
- Makes committed changes visible to eligible future snapshots.

Real database engines also require write-ahead logging, recovery protocols, and durable commit handling.

### 3.6 Rollback

Rollback discards buffered changes and marks the transaction as aborted.

An aborted transaction must not expose its proposed values to other transactions.

## 4. Isolation Levels

Isolation levels define which concurrent transaction effects a transaction may observe.

The four commonly discussed SQL isolation levels are:

| Isolation level | Dirty reads | Non-repeatable reads | Phantom reads |
|---|---|---|---|
| Read Uncommitted | Not permitted in PostgreSQL | Possible | Possible |
| Read Committed | Prevented | Possible | Possible |
| Repeatable Read | Prevented | Prevented | SQL-standard phantom protection; PostgreSQL provides snapshot isolation |
| Serializable | Prevented | Prevented | Prevented through serializable execution guarantees |

PostgreSQL treats Read Uncommitted as Read Committed.

### 4.1 Read Committed

Each statement obtains a new snapshot.

A transaction can observe changes committed by other transactions between successive statements.

Example:

- T1 reads 1,000.
- T2 changes the value to 1,200 and commits.
- T1 performs another read.
- T1 sees 1,200.

The Python, JavaScript, C++, and Java models refresh the snapshot before each read or write operation in their Read Committed mode.

### 4.2 Repeatable Read

The transaction retains its snapshot throughout its lifetime.

Previously committed data remains visible according to that snapshot, even if another transaction commits a newer version.

PostgreSQL implements Repeatable Read using snapshot isolation.

Concurrent modifications to rows that a transaction attempts to update can produce serialization-related errors.

### 4.3 Serializable

Serializable isolation aims to ensure that committed concurrent transactions produce a result equivalent to some serial execution order.

PostgreSQL uses Serializable Snapshot Isolation (SSI).

SSI detects dangerous dependency structures and can abort transactions when a serialization anomaly is possible.

An application must be prepared to retry transactions that fail with SQLSTATE `40001`.

The simplified programming implementations use optimistic read-set validation. They do not implement PostgreSQL's complete SSI dependency tracking or predicate-locking mechanisms.

## 5. Concurrency Anomalies

### 5.1 Dirty reads

A dirty read occurs when one transaction reads another transaction's uncommitted modification.

Example:

1. T1 changes an account balance to 5,000.
2. T1 has not committed.
3. T2 attempts to read the balance.
4. T2 observes 5,000.
5. T1 rolls back.

T2 has observed a value that never became committed database state.

MVCC visibility rules prevent this in PostgreSQL.

### 5.2 Non-repeatable reads

A non-repeatable read occurs when the same row returns different committed values during one transaction.

Read Committed permits this behavior.

Repeatable Read prevents it by maintaining a consistent transaction snapshot.

### 5.3 Phantom reads

A phantom read occurs when repeating a predicate-based query produces a different set of matching rows.

For example:

- T1 queries all accounts with balances above 5,000.
- T2 inserts another qualifying account and commits.
- T1 repeats its query.

The result can include an additional row under Read Committed.

PostgreSQL Repeatable Read maintains a stable snapshot, while Serializable also protects the serial execution guarantee.

### 5.4 Lost updates

A lost update occurs when concurrent transactions overwrite each other's modifications without adequate conflict handling.

Optimistic concurrency control can detect this using an expected version number.

The PostgreSQL implementation uses:

- A `row_version` column.
- An expected-version argument.
- A conditional `UPDATE`.
- A row-count check.

If the expected version no longer matches, the update fails without overwriting the newer value.

### 5.5 Write skew

Write skew is possible under snapshot isolation when transactions read overlapping information but update different rows.

Consider two doctors who must maintain at least one doctor on duty.

Both transactions observe two available doctors.

T1 marks doctor A unavailable.

T2 marks doctor B unavailable.

Both update different rows. Both may commit under snapshot isolation, leaving no doctor available.

A simple row-level write-conflict check cannot necessarily detect this anomaly.

Serializable isolation provides stronger protection by detecting relevant dependency structures.

## 6. MVCC and Locking

MVCC and locking serve related but different purposes.

MVCC controls which record versions are visible to a transaction.

Locking coordinates conflicting operations and protects database resources.

| Mechanism | Purpose |
|---|---|
| MVCC snapshot | Determines visible versions |
| Row lock | Coordinates conflicting row modifications |
| Table lock | Coordinates operations on table-level resources |
| Predicate lock | Supports serializable dependency detection |
| Transaction lock | Coordinates transaction-level resources |

Ordinary PostgreSQL readers can generally read an older visible version while another transaction updates a row.

A `SELECT ... FOR UPDATE` operation requests row-level locking and can wait for conflicting transactions.

MVCC does not mean that databases never use locks.

## 7. Write-Write Conflict Detection

Optimistic concurrency control permits transactions to proceed without immediately locking every row they read.

Before commit, the database validates whether another transaction has modified the target record.

The simplified implementations maintain:

- A read set.
- A write set.
- The observed version identifier.
- The transaction snapshot.

A conflicting modification produces a `WriteConflict` or equivalent exception.

In a production system, the application should distinguish between retryable conflicts and permanent failures.

A retry must execute the complete transaction again, including its reads and business-rule calculations.

Retrying only the final write can preserve stale application decisions.

## 8. Garbage Collection and Vacuum

Historical versions cannot remain indefinitely.

Old versions consume storage and increase maintenance costs.

However, deleting a version too early can break a transaction that still requires it.

MVCC garbage collection must respect the oldest relevant visibility horizon.

### 8.1 Vacuum

PostgreSQL VACUUM reclaims space occupied by dead tuples that are no longer needed by active transactions and other visibility requirements.

Important operations include:

- Identifying obsolete tuple versions.
- Making reusable space available.
- Updating visibility information.
- Maintaining database statistics.
- Preventing transaction ID wraparound through appropriate maintenance.

`VACUUM ANALYZE` also updates planner statistics.

`VACUUM FULL` rewrites the table and requires a stronger lock. It is not interchangeable with ordinary VACUUM.

### 8.2 Long-running transactions

Long-running transactions can prevent obsolete versions from being removed.

Consequences include:

- Increased table bloat.
- Higher storage consumption.
- Reduced vacuum effectiveness.
- More expensive maintenance.
- Increased risk of transaction ID wraparound if maintenance is neglected.

The PostgreSQL SQL implementation includes transaction and dead-tuple monitoring queries.

### 8.3 Simplified garbage collection

The programming implementations remove versions whose creators aborted or whose deletion transactions committed before the active transaction horizon.

This demonstrates the core idea but does not reproduce PostgreSQL's complete vacuum safety rules.

A production implementation must account for additional visibility requirements, including replication slots, prepared transactions, exported snapshots, and recovery-related horizons.

## 9. Python Implementation

The Python program provides an educational transactional storage engine.

### Main components

| Component | Responsibility |
|---|---|
| `Version` | Stores one record version |
| `Transaction` | Maintains transaction state |
| `IsolationLevel` | Defines visibility policy |
| `TransactionState` | Represents lifecycle state |
| `MVCCDatabase` | Manages versions and commits |
| `TransactionConflict` | Reports concurrent modification |
| `SerializationFailure` | Reports serializable validation failure |

### Important mechanisms

- Dataclasses represent version and transaction metadata.
- Dictionaries maintain version chains and transaction records.
- Sets track active, committed, and aborted transactions.
- `RLock` protects shared state during concurrent access.
- Exceptions distinguish conflicts from invalid lifecycle operations.
- JSON export provides transaction diagnostics.

The implementation demonstrates fundamental version visibility and optimistic validation without requiring external packages.

The serializable validator is intentionally simplified. It does not implement complete predicate-based SSI.

## 10. JavaScript Implementation

The JavaScript program emphasizes event-driven transaction management.

### Main components

| Component | Responsibility |
|---|---|
| `VersionedStore` | Maintains version chains |
| `EventEmitter` | Publishes transaction events |
| `Map` | Stores records and transaction state |
| `Set` | Tracks transaction identifiers |
| `execute()` | Provides asynchronous transaction execution |
| `vacuum()` | Removes obsolete versions |

### Event model

The store emits events for:

- Transaction creation.
- Reads.
- Buffered writes.
- Deletes.
- Commits.
- Rollbacks.
- Vacuum completion.

Consumers can subscribe to these events for operational monitoring.

### Retry behavior

The asynchronous execution method supports bounded retries with exponential backoff and jitter.

Only recognized concurrency failures are retried.

This avoids treating validation errors, programming errors, and invalid data as temporary concurrency problems.

The implementation requires Node.js 18 or later because it uses `structuredClone()`.

Its transaction coordination is an in-memory simulation. The event emitter is not a durable event log, and the implementation does not provide crash-safe commits.

## 11. C++17 Implementation

The C++ program emphasizes explicit domain modeling and deterministic storage operations.

### Main components

| Component | Responsibility |
|---|---|
| `Version` | Represents an immutable version record |
| `Transaction` | Maintains transactional read and write sets |
| `MVCCDatabase` | Owns database state |
| `IsolationLevel` | Defines isolation behavior |
| `TransactionState` | Controls legal transitions |
| `WriteConflict` | Reports write conflicts |
| `SerializationFailure` | Reports validation failure |

### Engineering decisions

- `std::map` maintains deterministic key ordering.
- `std::vector` maintains version chains.
- `std::set` tracks transaction states.
- `std::optional` represents missing values and deletion metadata.
- `std::remove_if` supports version cleanup.
- Exceptions communicate transaction failures.

The implementation performs validation before applying buffered writes.

It is a single-process educational model. It does not implement durable storage, write-ahead logging, crash recovery, or thread-safe transaction coordination.

## 12. Java 17 Implementation

The Java implementation uses an enterprise-oriented service architecture.

### Main components

| Component | Responsibility |
|---|---|
| `MVCCStore` | Maintains versioned records |
| `Transaction` | Encapsulates transaction state |
| `TransactionService` | Implements business operations |
| `Version` | Represents historical record state |
| `TransactionListener` | Provides event monitoring |
| `DatabaseStatistics` | Exposes storage statistics |
| `IsolationLevel` | Defines transaction isolation |

### Enterprise workflow

The `TransactionService` implements a bank transfer.

The workflow:

1. Starts a serializable transaction.
2. Reads the source account.
3. Reads the destination account.
4. Checks the available balance.
5. Buffers both account modifications.
6. Commits the transaction.
7. Rolls back if validation or business rules fail.

`Math.addExact()` detects integer overflow in destination balance calculations.

Records provide immutable metadata structures, while collections maintain the mutable storage engine state.

The event listener separates operational monitoring from transaction execution.

Listener failures are isolated so that monitoring problems do not automatically invalidate committed database operations.

The implementation uses synchronized methods for in-process coordination. This is not a replacement for database-level concurrency control in a distributed production system.

## 13. PostgreSQL Implementation

The SQL implementation demonstrates native PostgreSQL transaction processing and a separate application-level version audit.

### Database objects

| Object | Purpose |
|---|---|
| `transaction_registry` | Stores application transaction metadata |
| `accounts` | Stores current account records |
| `version_history` | Stores application-level record history |
| `transaction_events` | Stores operational events |
| `maintain_account_version()` | Maintains version numbers and history |
| `update_balance_optimistic()` | Performs expected-version updates |
| `transfer_balance()` | Executes an atomic transfer |
| `account_version_report` | Reports current record state |
| `active_transaction_report` | Reports active database transactions |

### Native PostgreSQL MVCC

PostgreSQL manages physical tuple versions internally.

A normal `UPDATE` creates a new tuple version rather than simply overwriting a value in place.

The old tuple may remain available to transactions whose snapshots require it.

The SQL implementation demonstrates this native behavior through actual transactions and isolation-level declarations.

### Application-level version tracking

The `row_version` column provides an application-visible version number.

It supports optimistic concurrency control.

The `version_history` table records business-level changes.

These mechanisms serve different purposes:

- Native MVCC supports database concurrency.
- `row_version` supports application conflict detection.
- `version_history` provides application audit history.

An audit table does not expose every physical PostgreSQL tuple version.

### Optimistic updates

The function `update_balance_optimistic()` updates a record only if its current version matches the expected version.

A failed version comparison returns `FALSE`.

This prevents a stale application request from silently overwriting a newer balance.

### Atomic transfers

The `transfer_balance()` procedure:

- Validates the transfer amount.
- Rejects transfers between identical accounts.
- Locks account rows in deterministic identifier order.
- Checks account existence.
- Checks sufficient funds.
- Updates both balances.
- Records a transaction event.

The caller controls the surrounding transaction boundary.

If an error occurs, the caller must roll back the transaction.

### Isolation testing

The SQL file demonstrates:

- Read Committed.
- Repeatable Read.
- Serializable.
- `SELECT FOR UPDATE`.
- Transaction snapshot inspection.
- Serialization-related transaction handling.

PostgreSQL can abort serializable transactions when it detects dangerous dependency structures.

Applications must handle and retry eligible serialization failures.

## 14. Performance Considerations

MVCC improves concurrent read behavior but introduces storage and maintenance costs.

| Area | Performance consideration |
|---|---|
| Version lookup | Searching long version chains increases read work |
| Write activity | Updates create additional tuple versions |
| Snapshot lifetime | Long-lived snapshots delay cleanup |
| Index maintenance | Updates can require index changes |
| Vacuum | Requires background maintenance resources |
| Transaction contention | Conflicting writers may wait or abort |
| Version history | Audit records increase storage requirements |
| Serializable validation | Additional dependency tracking has computational costs |

The programming implementations use hash-based lookup in Python and JavaScript and ordered key structures in C++.

The PostgreSQL implementation uses indexes for account identifiers, history retrieval, and transaction reporting.

Indexes should be selected according to actual query patterns rather than added indiscriminately.

## 15. Security and Reliability

MVCC does not automatically provide application-level authorization or data confidentiality.

Production implementations must separately address:

- Database role permissions.
- Row-level security where appropriate.
- Parameterized SQL execution.
- Transaction ownership.
- Audit record access.
- Sensitive data retention.
- Backup and recovery.
- Connection management.
- Deadlock handling.
- Serialization retry policies.
- Transaction timeout limits.

Application-level history tables should be protected against unauthorized modification.

Database transaction logs and diagnostic exports may contain sensitive information.

The example programs are educational simulations and should not be used as replacements for a production database engine.

## 16. Failure Conditions and Edge Cases

| Condition | Expected handling |
|---|---|
| Read of nonexistent record | Return no value |
| Empty record key | Reject input |
| Write after commit | Reject transaction operation |
| Write after rollback | Reject transaction operation |
| Concurrent update | Detect conflict |
| Concurrent deletion | Detect conflicting state |
| Serializable dependency change | Abort transaction |
| Insufficient transfer balance | Roll back transfer |
| Invalid transfer amount | Reject operation |
| Stale optimistic version | Reject update |
| Long-running snapshot | Delay obsolete-version cleanup |
| Monitoring listener failure | Isolate monitoring failure |
| Database crash | Requires durable logging and recovery |

The educational engines model transaction-state failures and common concurrency conflicts.

They do not provide full database crash recovery or distributed transaction guarantees.

## 17. Implementation Comparison

| Capability | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Version chains | Yes | Yes | Yes | Yes | Native |
| Snapshot visibility | Simplified | Simplified | Simplified | Simplified | Native |
| Read Committed | Yes | Yes | Yes | Yes | Native |
| Repeatable Read | Yes | Yes | Snapshot model | Yes | Native |
| Serializable | Simplified | Simplified | Simplified | Simplified | SSI |
| Write conflict detection | Yes | Yes | Yes | Yes | Native |
| Rollback | Yes | Yes | Yes | Yes | Native |
| Version cleanup | Simplified | Simplified | Simplified | Simplified | VACUUM |
| Async transaction workflow | No | Yes | No | No | Client-dependent |
| Business transaction | Example | Example | Example model | Bank transfer | Bank transfer |
| Durable storage | No | No | No | No | Yes |

## 18. Repository Execution

### Python

Run the self-contained script using Python 3:

- `python mvcc.py`

The script uses only the Python standard library.

### JavaScript

Run using Node.js 18 or later:

- `node mvcc.js`

No external npm packages are required.

### C++17

Compile:

- `g++ -std=c++17 -O2 -Wall -Wextra -pedantic mvcc.cpp -o mvcc`

Execute:

- `./mvcc`

On Windows, execute `mvcc.exe`.

### Java 17

Compile:

- `javac MVCCEnterprise.java`

Execute:

- `java MVCCEnterprise`

### PostgreSQL

Execute the SQL file using a PostgreSQL 15 or later database connection.

The script recreates the `mvcc_lab` schema, so existing objects in that schema are removed.

The SQL examples use explicit transaction boundaries and create application-level audit records.

## 19. Technical Limitations

The four programming implementations are educational in-memory models.

Their simplified snapshot and conflict-validation algorithms demonstrate the principles of MVCC but do not reproduce all implementation details of a production database.

In particular:

- They do not implement PostgreSQL transaction ID wraparound management.
- They do not implement complete SSI predicate dependency tracking.
- They do not implement WAL or crash recovery.
- They do not provide durable commits.
- They do not implement distributed transaction coordination.
- Their garbage collection does not account for every production visibility horizon.
- Their concurrency controls are not interchangeable with database locking mechanisms.

PostgreSQL provides the production database implementation in this collection.

## 20. Practical Implications

MVCC is particularly relevant to workloads that combine frequent reads with concurrent updates.

Examples include:

- Financial account processing.
- Inventory management.
- Order processing.
- Enterprise resource planning.
- Transactional reporting.
- Multi-user business applications.
- Operational monitoring systems.

The central engineering decision is to maintain the correct relationship between transaction snapshots, version visibility, write validation, and obsolete-version cleanup.

A transaction must see a logically consistent database state, concurrent modifications must be handled according to the selected isolation level, and historical versions must remain available for as long as active transactions require them.
