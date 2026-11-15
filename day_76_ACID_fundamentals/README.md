# ACID Fundamentals: Atomicity, Consistency, Isolation and Durability

## 1. Project Scope

This project implements the four fundamental properties of reliable database transactions:

- **Atomicity:** A transaction either completes all its operations or completes none of them.
- **Consistency:** A transaction preserves the database's defined integrity rules.
- **Isolation:** Concurrent transactions behave according to the selected isolation guarantees.
- **Durability:** Successfully committed changes survive failures covered by the database's durability configuration.

The implementations use a financial transaction-processing scenario involving a corporate treasury, research department, operations department and savings accounts.

A transfer moves money between two accounts. The source account is debited, the destination account is credited, and a transaction record is maintained.

The central invariant is:

**Total account balance before a successful transfer = Total account balance after the transfer.**

A failed transfer must not leave a partial debit or credit.

## 2. Domain Model

The relational and object-oriented implementations use the following entities.

| Entity | Responsibility |
|---|---|
| Account | Stores account ownership and current balance |
| Transaction | Represents one logical unit of work |
| Transfer | Describes a debit and corresponding credit |
| Transaction Ledger | Records financial movements |
| Audit Log | Records important transaction events |
| Transaction Manager | Coordinates transaction execution |
| Transaction Snapshot | Represents data observed when a transaction begins |
| Version | Detects concurrent modifications |
| Idempotency Key | Prevents duplicate execution of a request |

### Relationship diagram

Repository-independent transaction architecture:

Account
→ Transaction
→ Transfer Operations
→ Validation
→ Commit or Rollback
→ Audit and Persistence

For a financial transfer:

Source Account
→ Debit
→ Destination Account
→ Credit
→ Transaction Record
→ Commit

All operations belonging to the same transfer must succeed together.

## 3. Atomicity

Atomicity protects a transaction from partial execution.

Consider an account transfer of ₹500:

| Operation | Treasury | Research |
|---|---:|---:|
| Initial balance | ₹10,000 | ₹2,500 |
| Treasury debit | -₹500 | 0 |
| Research credit | 0 | +₹500 |
| Final balance | ₹9,500 | ₹3,000 |

If the destination credit fails after the source debit, the debit must be rolled back.

### Commit and rollback

A transaction normally follows this lifecycle:

ACTIVE
→ Execute operations
→ Validate
→ COMMIT
→ COMMITTED

If an operation fails:

ACTIVE
→ Execute operations
→ Failure
→ ROLLBACK
→ ROLLED_BACK

A rollback discards uncommitted changes.

A commit makes the transaction's changes part of the committed database state.

### Python implementation

The Python program uses SQLite transactions with explicit `BEGIN IMMEDIATE`, `COMMIT` and `ROLLBACK`.

The transfer method performs the following operations within one transaction:

1. Reads both accounts.
2. Checks their existence.
3. Validates available funds.
4. Debits the source.
5. Credits the destination.
6. Records the transfer.
7. Writes an audit event.
8. Commits.

An injected failure after the debit demonstrates that the original balance is preserved.

### JavaScript implementation

The JavaScript program uses staged account changes.

A transaction maintains:

- An account snapshot.
- A collection of staged updates.
- A list of transfer operations.
- A transaction state.

The committed account map is not modified while a transaction is being prepared.

The store publishes staged changes only after validation and persistence succeed.

### C++17 implementation

The C++ engine creates a candidate account map.

Changes are applied to the candidate rather than directly to the committed account map.

If validation succeeds, the candidate replaces the existing state.

This approach avoids partially applying an unsuccessful transaction.

### Java 17 implementation

The enterprise implementation maintains separate committed and staged maps.

A transaction manager validates the candidate state before publishing it.

The durability provider must successfully persist the candidate before the committed account map is replaced.

### PostgreSQL implementation

PostgreSQL provides atomic transaction boundaries through `BEGIN`, `COMMIT` and `ROLLBACK`.

The stored procedure performs the debit, credit, ledger insertion and audit insertion inside the caller's transaction.

If any operation raises an exception, the application can roll back the complete transaction.

### Savepoints

A savepoint provides an intermediate rollback boundary inside a transaction.

For example:

- Begin a transaction.
- Perform the primary operation.
- Create a savepoint.
- Execute an optional operation.
- Roll back to the savepoint if the optional operation fails.
- Continue the outer transaction.
- Commit the outer transaction.

A savepoint does not independently commit data.

## 4. Consistency

Consistency ensures that every committed transaction preserves the database's defined rules.

A database may enforce consistency through:

- Primary keys.
- Foreign keys.
- Unique constraints.
- Check constraints.
- Not-null constraints.
- Triggers.
- Stored procedures.
- Application validation.
- Transaction-level invariant checks.

### Financial invariants

The project implements these rules:

| Rule | Enforcement |
|---|---|
| Account ID must be unique | Primary key |
| Account owner must be present | Not-null and application validation |
| Account balance cannot be negative | Check constraint |
| Transaction amount must be positive | Check constraint |
| Source and destination must differ | Check constraint |
| Transaction accounts must exist | Foreign keys |
| Transaction ID must be unique | Primary key |
| Idempotency key must be unique | Unique constraint |
| Account version cannot be negative | Check constraint |
| Ledger entries must reference transactions | Foreign key |

### Why application validation is insufficient

An application can validate that an account balance is positive before performing an update.

Yet another application, database session or background process may modify the same account.

Database constraints provide an additional integrity boundary that is not dependent on a single application's validation logic.

Application validation improves error handling.

Database constraints protect persisted data.

Both mechanisms have separate responsibilities.

### Integer-based currency

The Python implementation stores money as integer cents.

The JavaScript and C++ implementations also use integer minor units.

The Java implementation uses integer cents with `long`.

The PostgreSQL implementation uses `NUMERIC(18,2)`.

These decisions avoid the rounding errors associated with binary floating-point financial calculations.

## 5. Isolation

Isolation governs how concurrent transactions interact.

Consider two transactions that read the same account balance.

Initial balance: ₹10,000.

- Transaction A reads ₹10,000.
- Transaction B reads ₹10,000.
- Transaction A withdraws ₹2,000.
- Transaction B withdraws ₹3,000.

Without appropriate concurrency control, both transactions might calculate their updates using the same original balance.

The final result may not reflect the intended sequence of operations.

### Common concurrency anomalies

| Anomaly | Description |
|---|---|
| Dirty read | Reading another transaction's uncommitted changes |
| Non-repeatable read | Reading the same row twice and observing different committed values |
| Phantom read | Repeating a query and observing a changed set of rows |
| Lost update | One concurrent update overwrites another |
| Write skew | Concurrent transactions independently preserve local conditions but violate a combined invariant |

### Isolation levels

| Isolation level | Main guarantee |
|---|---|
| Read Uncommitted | Lowest isolation; behavior depends on the database implementation |
| Read Committed | Reads committed data |
| Repeatable Read | Provides a stable transaction snapshot, with database-specific guarantees |
| Serializable | Enforces an outcome equivalent to some serial execution |

PostgreSQL implements Read Uncommitted using Read Committed behavior.

PostgreSQL Repeatable Read uses snapshot isolation. It is stronger than basic repeatable-read implementations but does not prevent every possible serialization anomaly.

Serializable transactions can fail with a serialization error. Applications must retry the complete transaction when appropriate.

### Pessimistic concurrency control

Pessimistic concurrency control locks records before modifying them.

The PostgreSQL procedure uses:

`SELECT ... FOR UPDATE`

The two account rows are locked in ascending account ID order.

This reduces the possibility of deadlocks when multiple transactions transfer money between the same accounts.

SQLite uses `BEGIN IMMEDIATE` to acquire a write reservation before executing the transfer.

### Optimistic concurrency control

Optimistic concurrency control allows transactions to work on snapshots before validating whether the original data changed.

Each account has a version number.

A transaction records the version it originally observed.

At commit time, the current version must match the recorded version.

The condition can be represented as:

`UPDATE accounts SET balance = new_balance, version = version + 1 WHERE account_id = id AND version = expected_version`

If no row is updated, the operation detects a concurrent modification.

The JavaScript, Java and Python implementations demonstrate version-based validation.

The PostgreSQL implementation exposes an optimistic update function.

### Isolation trade-offs

| Approach | Advantage | Trade-off |
|---|---|---|
| Row locking | Prevents conflicting writes while locks are held | Blocking and deadlocks |
| Optimistic validation | Reduces locking during transaction preparation | Conflicts require retries |
| Serializable isolation | Strong transaction-level guarantees | Serialization failures and additional overhead |
| Snapshot-based reads | Consistent view of data | Does not automatically prevent every write anomaly |

## 6. Durability

Durability means committed transactions survive failures covered by the database's configured durability guarantees.

A successful commit must not be treated as a temporary application-memory change.

### Write-ahead logging

Write-ahead logging records changes in a log before the corresponding database pages are considered safely persisted.

The general process is:

Transaction
→ Generate changes
→ Write transaction log
→ Flush required log records
→ Confirm commit
→ Persist database pages
→ Recover from log when necessary

PostgreSQL uses Write-Ahead Logging (WAL).

Its crash-recovery process replays committed changes as required to restore a consistent database state.

### Durability in the implementations

| Implementation | Mechanism | Limitation |
|---|---|---|
| Python | SQLite WAL and database commits | Depends on SQLite configuration and storage guarantees |
| JavaScript | Temporary file, synchronization and atomic rename | A single-process demonstration, not a production database |
| C++17 | Transaction log records | Simplified WAL without full crash-safe recovery |
| Java 17 | Persistent snapshot and atomic replacement | Does not implement database-grade recovery |
| PostgreSQL | Native WAL and transaction commit | Depends on server and storage configuration |

The JavaScript implementation writes the complete candidate state to a temporary file and replaces the previous file only after the write succeeds.

The Java implementation uses the same general snapshot-persistence approach.

These approaches demonstrate the ordering of persistence and publication but are not substitutes for a database engine.

### PostgreSQL durability configuration

Important PostgreSQL settings include:

- `fsync`
- `synchronous_commit`
- `full_page_writes`
- `wal_level`

The appropriate settings depend on the required recovery point, storage behavior, replication architecture and failure model.

Durability also requires reliable backups and an appropriate recovery procedure.

## 7. Transaction Lifecycle and State Management

The implementations use explicit transaction states.

| State | Meaning |
|---|---|
| ACTIVE | Operations may be performed |
| COMMITTED | Changes have been committed |
| ROLLED_BACK | Uncommitted changes were discarded |
| CONFLICT | Concurrency validation failed |

The valid normal transitions are:

ACTIVE → COMMITTED

ACTIVE → ROLLED_BACK

ACTIVE → CONFLICT

A committed or rolled-back transaction cannot be reused.

This prevents accidental execution of operations against an already completed transaction.

## 8. Idempotency

An idempotency key identifies a logical request.

Suppose a payment request reaches the server, commits successfully, but the response is lost because of a network failure.

The client may retry the request.

Without idempotency protection, the same payment could execute twice.

An idempotency key allows the system to identify an already processed request.

The PostgreSQL implementation uses:

- A unique key on the transaction table.
- A separate transaction request table.
- A transaction-scoped advisory lock to coordinate requests sharing the same key.

The JavaScript, Java and C++ implementations also demonstrate duplicate-request protection.

A production implementation should return the original result for a repeated request rather than execute it again.

The key should be associated with a validated request identity and retained for an appropriate period.

## 9. Implementation Architecture

### Python

The Python program uses SQLite as an executable transaction laboratory.

| Component | Responsibility |
|---|---|
| `Database` | Connection management and schema initialization |
| `AccountService` | Account and transfer operations |
| `TransferResult` | Immutable transfer result |
| `Account` | Account representation |
| `transaction()` | Reusable transaction context manager |
| `demonstrate_savepoints()` | Partial rollback demonstration |
| `demonstrate_concurrency()` | Concurrent transaction demonstration |

The implementation includes:

- Explicit transaction boundaries.
- Parameterized SQL.
- Foreign-key enforcement.
- WAL mode.
- Integer-based currency.
- Optimistic version checks.
- Database integrity validation.

### JavaScript

The JavaScript implementation uses Node.js event-driven architecture.

| Component | Responsibility |
|---|---|
| `Transaction` | Maintains transaction snapshots and staged changes |
| `TransactionalStore` | Controls commits and persistent state |
| `EventEmitter` | Publishes successful commit events |
| `persist()` | Writes durable snapshots |
| `withCommitLock()` | Serializes commit operations |
| `commit()` | Validates and publishes transactions |

The implementation demonstrates asynchronous persistence and serialized commit processing.

It is intentionally designed as a single-process example. Multiple independent processes writing the same JSON file would require additional coordination.

### C++17

The C++ implementation focuses on domain modeling and transaction execution.

| Component | Responsibility |
|---|---|
| `Account` | Financial account state |
| `Transaction` | Transaction snapshot and staged operations |
| `WriteAheadLog` | Transaction event logging |
| `Database` | State management and commit coordination |
| `TransferOperation` | Financial transfer representation |
| `SerializationConflict` | Concurrent modification error |

The candidate-state approach prevents unsuccessful operations from modifying committed memory.

The simplified recovery mechanism replays committed operations against initial account data.

It is an educational transaction log rather than a production-grade WAL.

### Java 17

The Java implementation uses enterprise-oriented domain types and service boundaries.

| Component | Responsibility |
|---|---|
| `Account` | Immutable account record |
| `Transfer` | Validated financial operation |
| `Transaction` | Transaction state and staged writes |
| `TransactionManager` | Validation and commit coordination |
| `DurabilityProvider` | Persistence abstraction |
| `FileDurabilityProvider` | Snapshot persistence |
| `AuditEntry` | Transaction audit information |
| `CommitResult` | Commit outcome |

Java records provide immutable data representations.

The `DurabilityProvider` interface separates transaction processing from the persistence mechanism.

The implementation uses a fair `ReentrantLock` to coordinate commit processing.

### PostgreSQL

The SQL implementation uses a dedicated `acid_lab` schema.

| Database object | Responsibility |
|---|---|
| `accounts` | Account state |
| `transactions` | Committed transfer records |
| `transaction_ledger` | Debit and credit entries |
| `audit_log` | Operational audit history |
| `transaction_requests` | Idempotency tracking |
| `transfer_funds()` | Atomic transfer procedure |
| `update_balance_optimistically()` | Version-based update |
| `account_transaction_summary` | Account reporting view |

The database is responsible for transaction coordination and relational integrity.

The application remains responsible for handling errors, retrying eligible transactions and presenting results.

## 10. PostgreSQL Workflow

The transfer procedure follows this sequence:

1. Validate source and destination identifiers.
2. Validate the transfer amount.
3. Validate the idempotency key.
4. Acquire an advisory transaction lock for that key.
5. Check for an existing request.
6. Lock both account records.
7. Validate account existence and active status.
8. Check the available balance.
9. Debit the source account.
10. Credit the destination account.
11. Insert the transaction record.
12. Insert the idempotency record.
13. Insert debit and credit ledger entries.
14. Write the audit event.
15. Return control to the caller.
16. Commit the enclosing transaction.

The procedure does not commit independently.

This permits the caller to include the transfer within a larger atomic operation.

## 11. Failure Handling

| Failure | Expected behavior |
|---|---|
| Insufficient balance | Reject the transfer |
| Unknown account | Reject the transaction |
| Negative balance | Database constraint rejects the update |
| Duplicate request | Idempotency validation rejects execution |
| Stale account version | Optimistic validation detects a conflict |
| Concurrent write | Locking or serialization validation coordinates the operation |
| Failure after debit | Roll back the entire transaction |
| Persistence failure | Do not publish the candidate committed state |
| Invalid transaction state | Reject further transaction operations |
| Corrupted transaction log | Recovery must stop rather than silently accept invalid records |

Deadlocks and serialization failures are not necessarily permanent failures.

An application may retry the complete transaction using bounded retries and appropriate backoff.

It should not blindly retry operations that have uncertain external side effects.

## 12. ACID Properties: Technical Distinctions

The four properties address different failure categories.

| Property | Primary concern | Main mechanism |
|---|---|---|
| Atomicity | Partial execution | Commit and rollback |
| Consistency | Invalid database state | Constraints and invariant validation |
| Isolation | Concurrent interference | Locks, MVCC and serialization |
| Durability | Loss of committed data | WAL and persistent storage |

They are related but not interchangeable.

A transaction may be atomic but violate a business rule if no consistency constraint exists.

A transaction may preserve valid data but suffer a lost update if concurrency control is inadequate.

A transaction may be isolated but lose committed data if durability is improperly configured.

Reliable transaction processing requires all four properties to be considered together.

## 13. Execution Requirements

| Deliverable | Requirement |
|---|---|
| Python | Python 3.10+ |
| JavaScript | Node.js 18+ |
| C++17 | Compiler supporting C++17 |
| Java | Java 17 |
| PostgreSQL | PostgreSQL 15+ |

All application implementations use standard language capabilities without third-party packages.

The PostgreSQL implementation requires permission to create a schema and database objects.

The PostgreSQL `gen_random_uuid()` function is available in supported modern PostgreSQL installations.

### Running the Python implementation

Run the script with the default database:

`python acid_fundamentals.py`

Run using a temporary database:

`python acid_fundamentals.py --temporary`

### Running the JavaScript implementation

`node acid_fundamentals.js`

The script creates `acid_accounts.json` in the working directory.

### Running the C++17 implementation

Compile with a C++17-compatible compiler.

The executable uses `acid_transactions.log` for its transaction records.

### Running the Java implementation

Compile and execute `AcidFundamentals.java` using Java 17.

The persistence demonstration creates `acid_enterprise.dat`.

### Running the PostgreSQL implementation

Execute the complete SQL script against the intended database.

The script creates the `acid_lab` schema, relational objects, stored procedures, sample accounts and demonstration transactions.

## 14. Performance and Security Considerations

### Performance

- Use indexes on frequently filtered account and transaction identifiers.
- Keep transaction duration short.
- Avoid unnecessary row locks.
- Acquire multiple locks in a consistent order.
- Use optimistic validation when conflicts are relatively uncommon.
- Monitor deadlocks and serialization retries.
- Avoid loading unbounded transaction histories into application memory.
- Use database-native transaction processing for concurrent production workloads.

### Security

- Use parameterized SQL rather than dynamically concatenated SQL.
- Restrict database roles to the operations they require.
- Protect transaction logs and persistent snapshots.
- Avoid exposing account information in error responses.
- Validate transaction ownership and authorization before execution.
- Protect idempotency keys against unauthorized reuse.
- Retain audit records according to applicable retention requirements.
- Avoid allowing application users to modify immutable financial history.
- Use encrypted connections and appropriate backup protection.

## 15. Important Limitations

These implementations demonstrate transaction principles rather than providing interchangeable production database engines.

The Python implementation uses SQLite and therefore has different concurrency characteristics from PostgreSQL.

The JavaScript implementation is a single-process persistence model. Its file-based design is not suitable for concurrent independent application instances without additional coordination.

The C++ implementation provides simplified transaction logging. Its log does not implement complete crash-safe WAL semantics, checksums, durable flush guarantees or comprehensive recovery metadata.

The Java implementation uses persistent snapshots and atomic file replacement. It does not provide database-grade multi-process concurrency or complete crash-recovery guarantees.

The PostgreSQL implementation demonstrates native transaction management, MVCC-related behavior, row locking, constraints and WAL-backed durability. Actual durability still depends on server configuration, storage guarantees, replication and backup strategy.

## 16. Practical Interpretation

ACID is a foundation for systems in which partial execution, invalid state, uncontrolled concurrent access or lost committed changes can produce serious consequences.

The banking scenario makes the distinctions concrete:

- Atomicity ensures that a transfer cannot leave money debited without being credited.
- Consistency ensures that account and transaction rules remain valid.
- Isolation ensures that simultaneous transfers do not silently overwrite one another.
- Durability ensures that committed transfers survive the failures covered by the database's persistence guarantees.

The strongest implementation is not the one with the most application-side transaction code. It is the one that places each guarantee at the appropriate boundary and makes the complete transaction behavior verifiable.
