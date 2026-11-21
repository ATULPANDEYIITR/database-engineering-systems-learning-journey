# Lost Updates and Concurrent Write Problems

## 1. Introduction

A lost update is a database concurrency anomaly in which two or more transactions modify the same data using previously retrieved values, causing one transaction's modification to overwrite another transaction's modification.

The problem occurs when an application separates reading a value, calculating a new value, and writing that value without ensuring that the original data has not changed.

Consider a bank account with an initial balance of 1,000.

Two transactions execute concurrently:

| Transaction | Operation | Value read | Calculated balance |
|---|---|---:|---:|
| T1 | Deposit 200 | 1,000 | 1,200 |
| T2 | Withdraw 100 | 1,000 | 900 |

An incorrect execution sequence is:

1. T1 reads 1,000.
2. T2 reads 1,000.
3. T1 calculates 1,200.
4. T2 calculates 900.
5. T1 writes 1,200.
6. T2 writes 900.

The final balance becomes 900.

The correct balance should be 1,100.

The deposit performed by T1 has been lost because T2 writes a value calculated from an outdated snapshot.

## 2. Transaction Fundamentals

A transaction represents a logical unit of database work.

A typical transaction follows these stages:

- Read the required records.
- Validate business conditions.
- Calculate the intended modification.
- Write the modified data.
- Commit the transaction or roll it back.

Concurrent transactions may execute simultaneously or interleave their operations.

The database must preserve the required consistency properties despite this concurrency.

### ACID properties

| Property | Meaning | Relevance to lost updates |
|---|---|---|
| Atomicity | A transaction completes entirely or is rolled back | Prevents partial transaction execution |
| Consistency | Transactions preserve database constraints | Protects valid database states |
| Isolation | Concurrent transactions are controlled according to an isolation level | Addresses interference between transactions |
| Durability | Committed changes survive failures | Protects completed writes |

Atomicity alone does not prevent lost updates. Two individually atomic transactions can still overwrite one another when their operations are based on stale values.

## 3. Lost Update Mechanism

A lost update is fundamentally a read-modify-write problem.

The dangerous operation is:

1. Read a value.
2. Calculate a replacement value outside an appropriately protected database operation.
3. Write the replacement value without checking whether the original value is still current.

The problem is especially common in:

- Banking applications.
- Inventory management.
- Reservation systems.
- E-commerce order processing.
- Employee record management.
- Distributed applications.
- Shared configuration systems.
- Collaborative editing systems.

### Distinguishing related concurrency anomalies

| Anomaly | Description |
|---|---|
| Lost update | One transaction overwrites another transaction's modification |
| Dirty read | A transaction reads another transaction's uncommitted changes |
| Non-repeatable read | Reading the same row twice produces different committed values |
| Phantom read | Repeating a query returns a different set of qualifying rows |
| Write skew | Transactions modify different rows based on a shared condition, producing an invalid combined state |

These anomalies are related to concurrency but are not interchangeable.

## 4. Concurrency Control Approaches

Three principal implementation strategies are demonstrated in the source files.

### 4.1 Unsafe read-modify-write

The unsafe implementation deliberately reproduces the lost-update anomaly.

Both transactions obtain an independent snapshot. Each calculates a replacement balance from its own snapshot.

The second write overwrites the first transaction's result.

The implementations use this approach only to demonstrate the failure mechanism.

It should not be used for production financial or inventory operations.

### 4.2 Pessimistic locking

Pessimistic locking assumes that concurrent modifications are sufficiently likely to justify acquiring a lock before modifying shared data.

The execution sequence is:

1. Acquire the resource lock.
2. Read the latest committed value.
3. Validate the requested operation.
4. Calculate the new value.
5. Update the resource.
6. Commit.
7. Release the lock.

A transaction attempting to modify the same locked resource must wait.

The Python implementation uses account-specific reentrant locks.

The JavaScript implementation uses an asynchronous mutex.

The C++ implementation combines account-specific mutexes with a shared mutex for repository state.

The Java implementation uses fair `ReentrantLock` instances.

PostgreSQL uses `SELECT ... FOR UPDATE` to lock the selected account row.

**Advantages**

- Prevents concurrent writers from independently modifying the same protected resource.
- Provides a straightforward execution model.
- Suitable for operations requiring exclusive access.
- Avoids repeated optimistic conflict retries.

**Limitations**

- Transactions may wait for locks.
- Excessive locking reduces throughput.
- Long-running transactions increase contention.
- Incorrect lock ordering can produce deadlocks.
- Lock management adds operational complexity.

Pessimistic locking is particularly useful when conflicts are frequent or when a transaction requires a sequence of operations that must be performed under exclusive access.

### 4.3 Optimistic concurrency control

Optimistic concurrency assumes that conflicting writes are relatively uncommon.

A version number identifies the state observed by a transaction.

Each successful modification increments the version.

Example:

| Stage | Balance | Version |
|---|---:|---:|
| Initial state | 1,000 | 0 |
| Transaction A reads | 1,000 | 0 |
| Transaction B reads | 1,000 | 0 |
| Transaction A deposits 200 | 1,200 | 1 |
| Transaction B attempts withdrawal | Rejected | 1 |

Transaction B attempts to write using version 0.

The database detects that the current version is 1 and rejects the stale modification.

The application must obtain a fresh snapshot, recalculate the intended operation, and retry if appropriate.

A conceptual conditional update is:

`UPDATE accounts SET balance = balance + 200, version = version + 1 WHERE account_id = 1 AND version = 0;`

The actual PostgreSQL implementation uses a trigger to maintain the version automatically.

A successful conditional update affects one row. A zero-row result indicates that the expected state was not available or the requested operation could not be performed.

**Advantages**

- Does not require transactions to hold long-lived locks while processing.
- Works well for workloads with relatively few conflicts.
- Provides explicit stale-write detection.
- Supports efficient conditional updates.

**Limitations**

- Conflicts require application-level handling.
- Frequent conflicts can produce repeated retries.
- Recalculation must use fresh data.
- External side effects must not be repeated accidentally during retries.

## 5. Version-Based Concurrency

A version column is a simple mechanism for identifying changes to a record.

Consider the following account representation:

| Field | Value |
|---|---|
| account_id | 101 |
| owner_name | Customer A |
| balance | 1,000.00 |
| version | 4 |

A successful update changes the version from 4 to 5.

A transaction that previously read version 4 cannot silently overwrite version 5.

Version values can be implemented using:

- Integer counters.
- Database-generated revision numbers.
- Timestamp-based concurrency tokens.
- Row-version mechanisms.
- Entity revision identifiers.

Integer version counters are generally preferable to timestamps when exact change detection is required.

Timestamp precision, clock differences, and timestamp collisions can make time-based tokens less reliable.

A version number is a concurrency indicator, not an authorization mechanism.

## 6. Atomic Database Operations

A particularly effective technique is to express a modification directly in the database.

Instead of:

1. Retrieve the current balance.
2. Calculate the updated balance in application memory.
3. Write the calculated balance.

Use an atomic relative update:

`UPDATE accounts SET balance = balance + 200 WHERE account_id = 101;`

The database evaluates the expression against the row being modified.

This avoids replacing the balance with a value calculated from an old application snapshot.

Business conditions must still be enforced.

For a withdrawal:

`UPDATE accounts SET balance = balance - 100 WHERE account_id = 101 AND balance >= 100;`

The application should inspect the number of affected rows to determine whether the operation succeeded.

Atomic relative updates do not eliminate every concurrency anomaly, particularly when a business operation spans several records or depends on conditions involving other rows.

## 7. Isolation Levels

Transaction isolation determines which concurrent transaction effects are visible and which conflicting operations are permitted.

| Isolation level | Important behavior |
|---|---|
| Read Uncommitted | PostgreSQL treats this as Read Committed |
| Read Committed | Each statement observes a committed snapshot |
| Repeatable Read | A transaction maintains a stable snapshot and PostgreSQL prevents certain concurrent update anomalies through serialization failures |
| Serializable | Enforces serializable transaction behavior and may reject transactions that must be retried |

### Read Committed

Read Committed is PostgreSQL's default isolation level.

It prevents dirty reads.

It does not automatically prevent every lost-update pattern, particularly when application code calculates replacement values from previously retrieved data.

Conditional updates and row-level locking remain important.

### Repeatable Read

PostgreSQL Repeatable Read provides snapshot isolation.

A transaction observes a consistent snapshot, but a conflicting update may cause a serialization failure rather than silently overwriting a concurrent modification.

Applications must be prepared to retry failed transactions.

### Serializable

Serializable provides the strongest standard SQL isolation level.

It ensures that successfully committed concurrent transactions have an execution equivalent to a serial ordering.

PostgreSQL may terminate a transaction with a serialization failure when it cannot safely preserve serializable behavior.

The application must retry the complete transaction.

Serializable isolation is not a substitute for application-level idempotency or correct transaction design.

## 8. Retry Management

Optimistic concurrency requires a defined conflict-handling strategy.

A suitable retry workflow is:

1. Obtain the latest record.
2. Read its current version.
3. Recalculate the intended operation.
4. Attempt a conditional update.
5. Detect a version conflict.
6. Apply a bounded retry policy.
7. Return a conflict response if the retry limit is reached.

### Exponential backoff

Exponential backoff increases the waiting period between attempts.

An example policy is:

| Attempt | Base delay |
|---|---:|
| 1 | 10 ms |
| 2 | 20 ms |
| 3 | 40 ms |
| 4 | 80 ms |

Random jitter can reduce synchronized retry attempts when many transactions conflict simultaneously.

Retries should be bounded.

A retry must repeat the complete logical transaction when the failed operation depends on multiple database reads or decisions.

External actions such as sending a payment instruction, publishing an event, or sending an email should not be repeated merely because a database transaction was retried.

## 9. Idempotency

Idempotency ensures that repeating the same logical request does not apply the same business operation multiple times.

For example, a payment request may be submitted twice because the client does not receive the first response.

Without idempotency, both requests might deposit or withdraw money.

A unique request identifier provides a basis for duplicate detection.

The PostgreSQL implementation defines a unique `request_key`.

The JavaScript implementation maintains an idempotency-key registry.

The Java implementation uses a concurrent map to retain completed request results.

Production implementations should:

- Store the idempotency key in durable storage.
- Enforce uniqueness at the database level.
- Associate the key with the original request parameters.
- Reject reuse with different parameters.
- Store the final result.
- Coordinate idempotency records and business writes in the same transaction.
- Define how incomplete requests are recovered after process failures.

Idempotency and optimistic concurrency solve different problems.

Optimistic concurrency prevents stale writes. Idempotency prevents duplicate execution of the same logical request.

## 10. Python Implementation

The Python file models an in-memory account repository.

### Main components

| Component | Responsibility |
|---|---|
| `Account` | Represents an account and its version |
| `AccountStore` | Maintains account state and transaction history |
| `WriteStrategy` | Identifies the concurrency strategy |
| `WriteEvent` | Captures transaction changes |
| `ConcurrencyError` | Represents stale-version conflicts |
| `ValidationError` | Represents invalid business operations |

### Important mechanisms

**Unsafe writes**

The implementation accepts a previously retrieved balance and uses it to calculate a replacement balance.

This intentionally exposes the lost-update problem.

**Pessimistic writes**

An account-specific lock serializes modifications to the same account.

**Optimistic writes**

The method compares the expected version with the current version before modifying the account.

**Retry handling**

The retry method retrieves a fresh snapshot and recalculates the operation.

**Audit reporting**

Transaction events record:

- Transaction identifier.
- Account identifier.
- Operation.
- Old and new balances.
- Old and new versions.
- Concurrency strategy.
- Timestamp.

The file-writing function writes to a temporary file before replacing the target report, reducing the risk of exposing an incomplete report.

The implementation uses an in-memory store. Its locks do not coordinate independent processes or separate application servers.

A production implementation requires shared database-level concurrency controls.

## 11. JavaScript Implementation

The JavaScript file demonstrates event-driven concurrency management.

Its main distinction is the use of asynchronous operations and promises.

### Main components

| Component | Responsibility |
|---|---|
| `Account` | Validated account representation |
| `Mutex` | Asynchronous exclusive execution |
| `EventBus` | Publishes account-update events |
| `AccountService` | Executes account operations |
| `ConflictError` | Represents optimistic conflicts |
| `ValidationError` | Represents invalid operations |

### Asynchronous execution

JavaScript operations can interleave when execution yields to the event loop.

An asynchronous read-modify-write sequence is therefore vulnerable to lost updates even though ordinary JavaScript execution in one Node.js event loop is single-threaded.

The `unsafeWrite` method deliberately creates an asynchronous gap between reading and writing.

Two transactions can use the same snapshot and overwrite each other's modifications.

### Mutex behavior

The `Mutex` class maintains a queue of waiting operations.

Only one operation executes inside its exclusive section at a time.

The release operation runs in a `finally` block so that a failed operation does not leave the mutex permanently locked.

### Event-driven behavior

The event bus publishes successful account modifications.

Subscribers receive immutable event objects.

Observer failures are isolated from the already completed account modification.

For critical production event delivery, an in-memory event bus is insufficient. A transactional outbox or equivalent durable event mechanism is needed.

### Idempotency

The service associates request keys with their original results.

Repeated identical requests return the existing result instead of performing another modification.

The demonstration uses in-memory storage. Durable request tracking is necessary for multi-process production deployments.

## 12. C++17 Implementation

The C++17 file implements a repository governance model for concurrent account writes.

### Domain structures

| Structure or class | Purpose |
|---|---|
| `Account` | Stores account state |
| `AccountSnapshot` | Captures an immutable-style read representation |
| `TransactionResult` | Reports transaction outcomes |
| `AuditEntry` | Stores transaction history |
| `Repository` | Coordinates access and updates |
| `ValidationError` | Handles invalid operations |

### Synchronization mechanisms

The implementation combines:

- `std::shared_mutex` for repository state.
- `std::shared_lock` for concurrent reads.
- `std::unique_lock` for exclusive state modifications.
- Account-specific `std::mutex` objects for pessimistic writes.
- `std::atomic` for transaction identifier generation.
- STL containers for account and audit management.

The account-specific mutex prevents unrelated accounts from being serialized unnecessarily by the pessimistic locking policy.

The repository-level shared mutex protects the account containers and account fields.

### Optimistic writes

The optimistic implementation compares the expected version while holding the exclusive repository lock.

Version validation and modification therefore form one protected operation.

### Performance characteristics

| Operation | Expected complexity |
|---|---|
| Account lookup | Average O(1) with unordered maps |
| Snapshot retrieval | Average O(1), excluding lock waiting |
| Conditional update | Average O(1), excluding synchronization |
| Audit insertion | Amortized O(1) |
| Audit retrieval | O(n) |

Actual throughput depends on lock contention, thread scheduling, hardware, and workload distribution.

The implementation is an in-process demonstration. Its locks cannot coordinate separate processes or machines.

## 13. Java 17 Enterprise Implementation

The Java file uses explicit domain modeling and service-oriented transaction execution.

### Enterprise components

| Component | Responsibility |
|---|---|
| `Account` | Mutable aggregate representing account state |
| `AccountSnapshot` | Immutable record of observed account state |
| `TransactionRequest` | Validated business request |
| `TransactionResult` | Structured execution outcome |
| `AuditEvent` | Immutable transaction history |
| `AccountRepository` | Manages account persistence behavior |
| `TransactionService` | Coordinates transaction execution |
| `TransactionPolicy` | Defines the concurrency policy |
| `OptimisticPolicy` | Delegates version-controlled writes |
| `PessimisticPolicy` | Delegates lock-controlled writes |

### Policy separation

The `TransactionPolicy` interface separates transaction execution from the selected concurrency strategy.

This makes the service easier to extend with additional execution policies.

The optimistic policy uses a snapshot version.

The pessimistic policy obtains an exclusive account lock before modifying the record.

### State transitions

The transaction status enumeration defines three outcomes:

- `COMMITTED`: the requested modification succeeded.
- `CONFLICT`: the observed version was stale.
- `REJECTED`: the operation failed a business or validation rule.

These states distinguish concurrency conflicts from invalid business operations.

### Enterprise considerations

The implementation includes:

- Immutable records for transaction requests and snapshots.
- Explicit validation.
- Custom exceptions.
- Thread-safe collections.
- Fair account-level locks.
- Bounded optimistic retries.
- Audit events.
- Request-key tracking.

The in-memory idempotency registry is illustrative. A production implementation must enforce request-key uniqueness in durable storage and coordinate request processing with transaction commits.

## 14. PostgreSQL Implementation

The SQL file models a relational transaction-management workflow.

### Relational structure

The primary entities are:

| Table | Purpose |
|---|---|
| `repositories` | Groups account-owning services |
| `accounts` | Stores current account state |
| `transaction_requests` | Stores requested operations and execution outcomes |
| `account_audit` | Stores historical balance and version transitions |

The schema uses primary keys, foreign keys, unique constraints, check constraints, indexes, and enumerated data types.

### Version trigger

The `enforce_account_version` trigger automatically increments the version when the account balance changes.

This avoids depending on every application client to increment the version correctly.

The trigger also updates the modification timestamp.

### Optimistic stored function

`optimistic_update` performs a conditional update.

It verifies:

- Request validity.
- Account existence.
- Expected version.
- Available balance.
- Numeric balance limits.
- Duplicate request identifiers.

A version mismatch produces a conflict result.

A business-rule failure produces a rejected result.

A successful write records the resulting version and an audit entry.

### Pessimistic stored function

`pessimistic_update` obtains a row lock using `SELECT ... FOR UPDATE`.

The transaction then reads the latest balance, validates the operation, modifies the row, and commits the result as part of the calling transaction.

Concurrent modifications to the same account must wait for the lock to be released.

### Audit management

The audit table captures:

- Transaction identifier.
- Account identifier.
- Previous balance.
- New balance.
- Previous version.
- New version.
- Concurrency strategy.
- Operation.
- Change timestamp.

Audit records are important for diagnosing overwritten values and reconstructing transaction histories.

In a production implementation, audit records should be written in the same database transaction as the corresponding business modification.

### Indexing

The SQL script includes indexes for:

- Repository-based account retrieval.
- Account transaction history.
- Transaction status reporting.
- Account version audit retrieval.

Indexes improve frequently used retrieval paths but increase storage requirements and write overhead.

Index selection should be based on actual query patterns and execution plans.

## 15. Relationship Between the Implementations

The five implementations share the same logical problem but emphasize different engineering approaches.

| Dimension | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Primary perspective | Workflow simulation | Event-driven execution | Synchronization and state management | Enterprise domain architecture | Relational transaction control |
| Unsafe writes | Yes | Yes | Yes | Yes | Yes |
| Optimistic locking | Version check | Version check | Version check | Version check | Conditional UPDATE |
| Pessimistic locking | Account lock | Async mutex | Mutex and shared mutex | ReentrantLock | SELECT FOR UPDATE |
| Retry handling | Yes | Yes | Yes | Yes | Application-managed |
| Audit | Event list | Event list | Audit vector | Audit collection | Audit table |
| Idempotency | Not implemented | Yes | Not implemented | Yes | Unique request key |

The implementations are educational models rather than interchangeable production systems.

The in-memory implementations provide synchronization within a single process. PostgreSQL provides transaction coordination for shared database records.

A distributed deployment must rely on a shared consistency mechanism rather than assuming that process-local locks protect shared resources.

## 16. Failure Modes and Operational Risks

### Stale reads

A transaction uses data that has changed since it was retrieved.

**Control:** Validate the version before writing.

### Incorrect retry logic

A transaction repeats using the original stale snapshot.

**Control:** Read the latest state and recalculate the complete operation.

### Excessive contention

Many transactions compete for the same locked record.

**Control:** Reduce lock duration, use appropriate isolation, and evaluate optimistic concurrency where suitable.

### Deadlocks

Transactions acquire multiple locks in incompatible orders.

**Control:** Establish consistent lock ordering, keep transactions short, and handle database deadlock errors.

### Duplicate requests

A client repeats a previously submitted request.

**Control:** Use durable idempotency keys and unique database constraints.

### Partial audit history

A business update succeeds but its corresponding audit entry fails.

**Control:** Commit the business change and audit entry within the same database transaction.

### Unbounded retries

Transactions repeatedly retry without a maximum attempt count.

**Control:** Apply bounded retries, exponential backoff, jitter, and clear failure responses.

### Cross-process synchronization

Separate application servers use different in-memory locks.

**Control:** Use database transactions, database locks, or an appropriately designed distributed coordination mechanism.

## 17. Security and Data Integrity

Concurrency management must be combined with appropriate security controls.

Important requirements include:

- Authenticate the transaction requester.
- Authorize access to the specific account.
- Validate operation types and amounts.
- Enforce non-negative balance constraints.
- Use parameterized SQL statements.
- Restrict direct table modification privileges.
- Protect audit records from unauthorized modification.
- Validate idempotency-key ownership and request parameters.
- Avoid exposing sensitive account information in error messages.
- Use appropriate transaction timeouts.
- Monitor repeated conflicts and abnormal write patterns.

A version number prevents certain stale writes but does not establish that a caller is authorized to modify a record.

Database constraints provide an additional integrity boundary, but they do not replace application authorization or business validation.

## 18. Performance and Design Trade-offs

| Consideration | Optimistic approach | Pessimistic approach |
|---|---|---|
| Conflict handling | Detects conflicts after an attempted write | Blocks competing operations |
| Lock duration | Usually shorter | Can be longer |
| Contention | Can produce retries | Can produce waiting |
| Throughput | Often effective for low-conflict workloads | Often effective for highly contended resources |
| Implementation | Requires version management | Requires lock management |
| Failure handling | Conflict and retry management | Lock timeout and deadlock management |
| Suitable workload | Frequent reads, relatively rare conflicts | Frequent conflicts or critical exclusive sequences |

There is no universally optimal strategy.

The appropriate choice depends on:

- Transaction frequency.
- Conflict probability.
- Number of concurrent writers.
- Duration of business operations.
- Acceptable latency.
- Data consistency requirements.
- Recovery behavior.
- Database capabilities.

## 19. Testing Scenarios

The implementations exercise several important conditions.

| Scenario | Expected behavior |
|---|---|
| Two transactions read the same version | The second stale optimistic write is rejected |
| Two unsafe writes use the same snapshot | A lost update occurs |
| Concurrent deposits use pessimistic locking | Every valid deposit is retained |
| Withdrawal exceeds the balance | Operation is rejected |
| Negative transaction amount | Validation fails |
| Account does not exist | Operation is rejected |
| Optimistic conflict occurs | Application obtains a fresh snapshot |
| Retry limit is reached | Transaction reports failure |
| Same idempotency key is submitted twice | Original result is reused |
| Account version changes | Earlier snapshots become stale |

For real database testing, concurrent sessions should be used to verify lock waiting, transaction isolation, stale updates, rollback behavior, deadlock handling, and serialization failures.

## 20. Practical Application

Lost-update prevention is important wherever multiple users, application instances, or automated processes can modify shared records.

In financial systems, an incorrect balance can cause accounting discrepancies.

In inventory systems, concurrent sales and stock adjustments can result in inaccurate quantities.

In reservation systems, multiple customers may attempt to reserve the same resource.

In collaborative applications, one user's changes may unintentionally replace another user's work.

The essential design principle is that a modification must be based on a valid and appropriately protected version of the underlying state.

A robust implementation combines atomic database operations, appropriate concurrency control, transaction boundaries, integrity constraints, auditability, and idempotent request processing.
