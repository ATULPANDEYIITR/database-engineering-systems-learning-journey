# Optimistic Concurrency Control: Versioning and Conflict Detection

## Project Description

This project implements Optimistic Concurrency Control (OCC), a transaction-management technique that allows multiple operations to work on shared data without continuously locking records during the entire transaction.

The central mechanism is version-based conflict detection.

A transaction reads a record and its version, performs its business calculations, and attempts to commit its changes only if the stored version still matches the version originally observed.

If another transaction has modified the record, the version changes. The stale transaction is rejected instead of silently overwriting newer data.

The implementations demonstrate this mechanism through financial accounts, inventory reservations, document updates, concurrent counters, and multi-record transactions.

## 1. Core Concepts

### 1.1 Optimistic Concurrency Control

Optimistic concurrency assumes that simultaneous write conflicts are relatively uncommon.

Instead of acquiring long-duration locks before reading data, a transaction follows three stages:

1. Read: Retrieve the record and its current version.
2. Process: Perform calculations or business operations using the retrieved data.
3. Validate and commit: Check whether the stored version remains unchanged before writing.

The workflow is:

Read record and version
        |
        v
Perform business operation
        |
        v
Compare expected and actual versions
        |
        +------ Versions match ------> Commit changes
        |
        +------ Versions differ -----> Reject transaction
                                         |
                                         v
                                  Retry or abort

The transaction does not assume that its original snapshot remains current throughout execution.

### 1.2 Versioning

A version is a monotonically increasing identifier associated with a record.

Example:

| Operation | Stored balance | Version |
|---|---:|---:|
| Initial creation | 1,000 | 1 |
| First successful update | 1,200 | 2 |
| Second successful update | 1,500 | 3 |
| Third successful update | 1,400 | 4 |

A successful modification increments the version.

A rejected modification does not change the version.

Versions provide a simple mechanism for identifying whether a record has changed since it was read.

They do not necessarily represent the number of business transactions, the number of users, or the amount of data modified.

### 1.3 Expected Version and Actual Version

Two version values are essential.

- Expected version: The version observed when the transaction originally read the record.
- Actual version: The version currently stored when the transaction attempts to commit.

A transaction can commit only when the versions match.

| Expected version | Actual version | Result |
|---:|---:|---|
| 1 | 1 | Eligible |
| 1 | 2 | Conflict |
| 2 | 2 | Eligible |
| 2 | 4 | Conflict |
| 5 | 3 | Conflict |

Version equality is necessary for a version-based update, although other business and database constraints must also be satisfied.

## 2. Lost Updates and Conflict Detection

### 2.1 Lost Update Problem

A lost update occurs when concurrent transactions read the same original value and subsequently overwrite each other's modifications.

Consider an account with a balance of 1,000.

| Step | Transaction A | Transaction B |
|---|---|---|
| 1 | Reads 1,000 | |
| 2 | | Reads 1,000 |
| 3 | Calculates 1,100 | |
| 4 | | Calculates 1,200 |
| 5 | Writes 1,100 | |
| 6 | | Writes 1,200 |

The final balance becomes 1,200.

Transaction A's update disappears.

The correct balance, assuming both changes represent independent increments, should be 1,300.

Optimistic concurrency prevents this outcome by validating the version before committing.

### 2.2 Conflict Detection

Suppose both transactions initially read version 1.

Transaction A commits first:

- Expected version: 1
- Actual version: 1
- New version: 2
- Result: Committed

Transaction B subsequently attempts its update:

- Expected version: 1
- Actual version: 2
- Result: Conflict

Transaction B must obtain a fresh snapshot and recalculate its business operation.

This is important because retrying an old calculated value can reproduce the original lost-update problem.

### 2.3 Compare-and-Swap

Compare-and-Swap (CAS) is the central operation used by the implementations.

Its logical contract is:

- Compare the stored version against the expected version.
- Reject the update if the versions differ.
- Replace the record data and increment its version if they match.

The comparison and modification must form one atomic operation.

An implementation that checks the version and subsequently performs an unprotected update is not a correct compare-and-swap implementation.

The Python and C++ implementations use synchronization around the critical section.

Java synchronizes on the individual versioned record.

JavaScript performs comparison and modification in one synchronous execution section.

PostgreSQL uses row-level locking and version validation.

## 3. Transaction Processing

### 3.1 Transaction Lifecycle

The implementations distinguish the following transaction states:

| State | Meaning |
|---|---|
| PENDING | Transaction has started |
| COMMITTED | Changes were successfully persisted |
| CONFLICTED | Version validation failed |
| ABORTED | Transaction could not complete |

A conflict is not necessarily a permanent transaction failure.

A transaction can encounter a conflict, obtain a fresh version, and successfully commit on a subsequent attempt.

An aborted transaction must not be represented as committed.

### 3.2 Retry Mechanism

Retrying is appropriate when:

- The conflict is temporary.
- The business operation can safely be recalculated.
- The transaction has not produced irreversible external side effects.
- The retry limit has not been exceeded.

The implementations use bounded retry attempts.

A simplified retry sequence is:

Attempt 1: Read version 1, conflict
Attempt 2: Read version 2, conflict
Attempt 3: Read version 3, commit

Unbounded retries can create excessive load and prevent transactions from completing under heavy contention.

### 3.3 Exponential Backoff

Exponential backoff increases the waiting time between failed attempts.

A common formula is:

\[
D_n = \min(D_{\max},D_0 \times 2^n)
\]

Where:

- \(D_n\): Delay for attempt \(n\).
- \(D_0\): Initial delay.
- \(D_{\max}\): Maximum permitted delay.

Random jitter can be added to avoid synchronized retry attempts.

This is especially useful when many application instances compete for the same records.

### 3.4 Retry Safety

Retrying a database update is different from repeating an external business action.

For example, an inventory reservation can be recalculated against the latest stock quantity.

An external payment request, email delivery, or message publication must not be blindly repeated because the first attempt may already have succeeded.

Production systems should use idempotency keys, transaction identifiers, transactional outboxes, and deduplication mechanisms where appropriate.

## 4. Versioning Strategies

Different systems use different methods to detect concurrent modifications.

| Strategy | Mechanism | Typical application |
|---|---|---|
| Integer version | Incrementing integer | Relational records |
| Timestamp version | Last-modified timestamp | Business applications |
| Row version | Database-maintained row identifier | Database-specific concurrency |
| ETag | HTTP entity tag | REST APIs |
| Content hash | Hash of record content | Immutable or content-addressed data |
| Revision number | Explicit document revision | Collaborative documents |

### Integer Versioning

Integer versioning is used throughout this project.

Advantages:

- Simple comparison.
- Easy auditing.
- No clock synchronization dependency.
- Straightforward conflict reporting.

Limitations:

- Every successful modification must increment the version.
- Incorrect direct updates can violate version integrity.
- A version alone does not identify which fields changed.

### Timestamp Versioning

A timestamp can represent the most recent modification.

Its reliability depends on timestamp precision, database behavior, and consistent update mechanisms.

Two updates occurring within the same timestamp resolution can create ambiguity.

Integer versioning avoids this particular issue.

### Content Hash Versioning

A content hash identifies the content state.

If the content changes, its hash should change.

This can be useful for immutable documents and content-addressed storage.

A hash is not automatically a substitute for transactional atomicity or a monotonically increasing version.

## 5. Pull-Based and API-Based Concurrency

Optimistic concurrency is commonly exposed through HTTP APIs.

A client first retrieves a resource containing an ETag.

It then submits an update with the previously observed ETag.

The server compares the supplied value with the current resource version.

| HTTP mechanism | Purpose |
|---|---|
| GET | Retrieve the current resource |
| ETag | Identify the current representation |
| If-Match | Require a matching representation |
| PUT | Replace a resource |
| PATCH | Modify selected fields |
| 412 Precondition Failed | Reject an unmet conditional request |
| 409 Conflict | Report a business-level conflict where appropriate |

Example interaction:

Client retrieves account version 7.

Server returns:

- Account balance: 5,000
- ETag: `"7"`

The client submits an update with:

- If-Match: `"7"`

If the resource has advanced to version 8, the server rejects the stale update.

The client must retrieve the current resource before attempting another modification.

HTTP conditional requests provide a useful interface-level mechanism, but the server must still enforce atomic version validation in its persistence layer.

## 6. Multi-Record Transactions

A transaction may involve several records.

Consider transferring 500 between two accounts.

Initial state:

| Account | Balance | Version |
|---|---:|---:|
| Source | 5,000 | 1 |
| Destination | 2,000 | 1 |

Expected state:

| Account | Balance | Version |
|---|---:|---:|
| Source | 4,500 | 2 |
| Destination | 2,500 | 2 |

Both changes must commit together.

If only the debit succeeds, financial integrity is violated.

The Python, JavaScript, C++, Java, and PostgreSQL implementations demonstrate coordinated multi-record updates.

For an in-memory implementation, both records must be protected by a common critical section or an equivalent transaction mechanism.

For Java, deterministic lock ordering reduces deadlock risk.

For PostgreSQL, a database transaction provides atomic commit and rollback.

For distributed systems, coordinating multiple independent storage systems requires additional mechanisms such as distributed transactions, sagas, or transactional messaging.

## 7. Python Implementation

The Python script uses a repository abstraction to manage versioned records.

### Main components

| Component | Responsibility |
|---|---|
| Snapshot | Captures record data and its observed version |
| StoredRecord | Maintains current record state |
| VersionConflictError | Identifies stale updates |
| VersionedRepository | Implements storage and compare-and-swap |
| Transaction | Represents transaction state |
| AuditEvent | Records successful modifications |

### Important mechanisms

The repository uses `threading.RLock` to protect shared data.

Reading returns a copied snapshot rather than exposing the mutable internal record.

The business operation executes outside the repository lock.

The compare-and-swap operation subsequently acquires the lock, validates the expected version, and commits the modification.

The retry implementation recalculates the operation against a fresh snapshot.

The transfer implementation checks both account versions and updates both accounts inside the same critical section.

### Performance considerations

The in-memory repository uses a dictionary for record lookup.

Average dictionary lookup is approximately \(O(1)\).

The audit list supports sequential retrieval, with total storage growing according to the number of successful operations.

The global repository lock provides simple atomicity but limits parallel write throughput.

A production implementation could use database transactions or finer-grained synchronization.

## 8. JavaScript Implementation

The JavaScript implementation provides an event-driven concurrency model.

### Main components

| Component | Responsibility |
|---|---|
| VersionedStore | Maintains records in a Map |
| RetryPolicy | Controls retry limits and delays |
| VersionConflictError | Represents stale writes |
| InventoryService | Demonstrates concurrent stock reservations |
| EventEmitter | Publishes transaction and conflict events |

### Event-driven behavior

The repository emits two important events:

- `committed`: A versioned update succeeds.
- `conflict`: The expected version does not match the current version.

This separates persistence behavior from monitoring and reporting.

A monitoring component can subscribe to these events without modifying the underlying transaction implementation.

### Asynchronous transactions

The update method supports asynchronous business operations.

The business operation can yield control to the event loop before committing.

Another transaction may update the same record during that interval.

When the original operation resumes, compare-and-swap detects whether the snapshot is stale.

### JavaScript concurrency limitation

JavaScript's single-threaded event loop does not mean that asynchronous operations cannot conflict.

Two asynchronous tasks can read the same version, suspend execution, and later attempt to commit.

The synchronous compare-and-swap section prevents interleaving within that particular execution context.

This in-memory implementation does not provide cross-process or cross-server coordination.

A shared database or distributed atomic storage mechanism is necessary for those environments.

## 9. C++17 Implementation

The C++ implementation models versioned account storage using STL containers and synchronization primitives.

### Main components

| Component | Responsibility |
|---|---|
| AccountData | Stores account information |
| VersionedRecord | Maintains the current version |
| Snapshot | Represents a consistent read |
| VersionedRepository | Implements atomic updates |
| InventoryService | Handles stock reservations |
| AuditEntry | Stores modification history |

### Synchronization

The repository uses `std::mutex` and `std::lock_guard`.

The lock protects:

- Record lookup during critical operations.
- Version validation.
- Record replacement.
- Version increments.
- Audit insertion.

The business calculation occurs outside the critical section.

This reduces the duration for which the shared repository is locked.

### Concurrent execution

The program launches multiple threads that increment a shared counter.

Each thread performs version-validated updates.

The expected result is 1,000 successful increments.

The program checks the final balance to detect lost updates.

### Design tradeoffs

A single mutex simplifies atomicity across multiple records.

It also limits concurrency because unrelated records share the same lock.

A production implementation may introduce per-record locking, lock ordering, database-backed transactions, or sharded storage.

Per-record locking requires additional care when a transaction updates several records.

## 10. Java 17 Enterprise Implementation

The Java implementation uses explicit domain types, repository interfaces, immutable records, and service classes.

### Main components

| Component | Responsibility |
|---|---|
| Account | Immutable account representation |
| Snapshot | Captures a versioned account |
| VersionedAccount | Maintains mutable persistence state |
| AccountRepository | Defines persistence operations |
| InMemoryAccountRepository | Implements versioned storage |
| TransactionService | Executes retry-aware transactions |
| InventoryService | Applies inventory business rules |
| RetryPolicy | Defines bounded retry behavior |

### Immutable domain objects

The `Account` record is immutable.

An update creates a replacement account rather than modifying the original business object.

This reduces accidental mutation and makes transaction calculations easier to reason about.

### Repository abstraction

The `AccountRepository` interface separates persistence operations from business services.

The transaction service does not need to understand the repository's internal storage mechanism.

A different implementation could use PostgreSQL or another transactional database.

### Lock ordering

The transfer implementation acquires account locks in a deterministic order based on account identifiers.

This reduces the risk of deadlocks caused by transactions acquiring the same pair of locks in opposite orders.

### Enterprise implications

Production systems should distinguish:

- Business validation errors.
- Stale-version conflicts.
- Infrastructure failures.
- Retry exhaustion.
- Transaction cancellation.

These conditions should not all be handled as generic exceptions.

Monitoring should include conflict rates, transaction duration, retry counts, and failure frequency.

## 11. PostgreSQL Implementation

The PostgreSQL script models optimistic concurrency using relational tables, database constraints, functions, procedures, triggers, and transactions.

### Database structure

The main relationships are:

repository_records
    |
    +---- accounts
    |
    +---- inventory
    |
    +---- concurrency_audit
    |
    +---- conflict_events

transactions
    |
    +---- concurrency_audit
    |
    +---- conflict_events

### Main tables

| Table | Purpose |
|---|---|
| repository_records | Stores versioned business records |
| transactions | Tracks transaction lifecycle |
| concurrency_audit | Records successful changes |
| conflict_events | Records stale-version attempts |
| accounts | Stores account balances |
| inventory | Stores available and reserved quantities |

The `repository_records` table contains a JSONB payload and a numeric version.

Business-specific tables provide typed relational constraints for account and inventory data.

### Compare-and-swap function

The `compare_and_swap` function:

1. Retrieves the requested record.
2. Obtains a row-level lock using `FOR UPDATE`.
3. Compares the stored and expected versions.
4. Records a conflict when they differ.
5. Updates the payload and increments the version when they match.
6. Records the successful modification.
7. Updates the transaction state.

The row-level lock ensures that competing transactions cannot simultaneously modify the same locked record.

### Version-integrity trigger

The trigger prevents several invalid operations:

- Decreasing the version.
- Skipping version numbers.
- Changing a payload without incrementing the version.
- Incrementing the version without changing the payload.

This provides an additional database-level integrity mechanism.

The trigger does not replace access control. Production applications should restrict direct table updates and expose controlled database operations.

### Account transfers

The `transfer_funds` procedure demonstrates atomic financial transactions.

Both account rows are locked before the balances change.

The source is debited, the destination is credited, and both versioned records are updated within the same database transaction.

If an exception occurs, the transaction must roll back.

### Inventory reservations

The inventory function validates:

- Positive reservation quantities.
- Available stock.
- Expected version.
- Current inventory state.

A stale request is recorded as a conflict.

An insufficient-stock request is rejected without modifying inventory.

### Isolation considerations

PostgreSQL supports multiple transaction isolation levels.

| Isolation level | Main behavior |
|---|---|
| READ COMMITTED | Each statement sees a committed snapshot |
| REPEATABLE READ | Transaction-level snapshot consistency |
| SERIALIZABLE | Enforces serializable transaction behavior |

Optimistic version checking and isolation levels solve related but different problems.

Version checking protects against stale application-level updates.

Transaction isolation controls visibility and interaction among database transactions.

A version check should not be treated as a substitute for all isolation requirements.

Applications must also handle serialization failures and deadlocks by retrying the complete database transaction when appropriate.

## 12. Conflict Resolution

Detecting a conflict does not automatically determine how it should be resolved.

The correct strategy depends on the business operation.

| Scenario | Appropriate approach |
|---|---|
| Account balance update | Re-read and recalculate |
| Inventory reservation | Recheck available stock |
| Document editing | Compare changes and request user resolution |
| Configuration modification | Validate the new configuration against current state |
| Shopping cart update | Reconcile independent item changes |
| Financial transfer | Revalidate both accounts and retry atomically |

### Automatic retry

Suitable when the operation can be safely recalculated against the latest state.

### Manual resolution

Suitable when two users make conflicting edits to the same business content.

### Field-level reconciliation

Suitable when independent changes affect different fields.

For example, one user changes a document title while another modifies its description.

A system may merge these changes if the business rules permit it.

### Reject and reload

Suitable when the proposed change depends heavily on the original snapshot and cannot safely be reconciled.

Blindly replacing the latest record with an older snapshot is not a valid conflict-resolution strategy.

## 13. Optimistic Versus Pessimistic Concurrency

| Characteristic | Optimistic concurrency | Pessimistic concurrency |
|---|---|---|
| Primary mechanism | Version validation | Lock acquisition |
| Initial assumption | Conflicts are uncommon | Conflicts require prevention |
| Read operation | Usually does not acquire a long-duration write lock | May acquire locks |
| Write operation | Validates version before committing | Requires appropriate locks |
| Conflict handling | Reject, retry, or reconcile | Wait, reject, or time out |
| Lock contention | Usually lower during business processing | Can be higher |
| Retry requirement | Common | Depends on locking and transaction failures |
| Typical workload | Read-heavy applications | Highly contended shared resources |

Neither strategy is universally superior.

Optimistic concurrency is useful when conflicts are relatively infrequent and transactions can be safely retried.

Pessimistic locking can be preferable when contention is high or when business operations require explicit coordination.

## 14. Performance and Complexity

Let:

- \(N\) represent the number of stored records.
- \(K\) represent the number of concurrent transactions.
- \(R\) represent the number of retry attempts.

| Operation | Expected complexity |
|---|---|
| Dictionary or hash-map lookup | \(O(1)\) average |
| Ordered-map lookup | \(O(\log N)\) |
| Version comparison | \(O(1)\) |
| Version increment | \(O(1)\) |
| Audit insertion into an append-only list | \(O(1)\) amortized |
| Audit retrieval | \(O(A)\), where A is audit size |
| Retry processing | Depends on business operation and R |

Performance is influenced by:

- Record contention.
- Transaction duration.
- Retry frequency.
- Lock duration.
- Database index design.
- Audit volume.
- Transaction isolation.
- Network latency.

When many transactions repeatedly update one record, optimistic concurrency can generate substantial retry overhead.

A conflict rate that remains high indicates that the concurrency strategy or data model may need revision.

Possible changes include partitioning shared data, reducing transaction duration, using atomic database operations, or selecting a different locking strategy.

## 15. Security and Data Integrity

Concurrency control is also a data-integrity concern.

Important production controls include:

- Validate all expected versions on the server.
- Do not trust client-supplied version values without checking them.
- Restrict direct database modifications.
- Apply database constraints to important business values.
- Keep audit records protected from unauthorized modification.
- Use transaction identifiers for traceability.
- Avoid exposing sensitive record contents in conflict messages.
- Apply authorization checks before modifying records.
- Prevent duplicate external operations using idempotency controls.
- Monitor repeated conflict and retry patterns.

Version numbers are not authorization credentials.

A correct version does not grant permission to modify a record.

Authentication, authorization, validation, and concurrency control must remain separate controls.

## 16. Edge Cases and Failure Conditions

| Condition | Expected behavior |
|---|---|
| Record does not exist | Reject the operation |
| Expected version is invalid | Reject the request |
| Version is stale | Record a conflict |
| New balance is negative | Reject the operation |
| Inventory is insufficient | Reject the reservation |
| Retry limit is exhausted | Abort the transaction |
| Two-account transfer fails | Roll back both changes |
| External operation is repeated | Apply idempotency protection |
| Database serialization failure | Retry the complete transaction when safe |
| Audit insertion fails | Preserve transactional consistency or roll back |

A successful version comparison does not guarantee business correctness.

The proposed values must still satisfy domain rules and database constraints.

## 17. Testing Scenarios

The implementations include executable demonstrations of the following scenarios.

| Test | Expected outcome |
|---|---|
| Two readers observe the same version | Both obtain the same initial version |
| First reader commits | Version increases |
| Second reader submits stale version | Conflict detected |
| Multiple counter increments | No lost updates |
| Concurrent inventory reservations | Reservations are validated against current stock |
| Transfer between accounts | Both balances change atomically |
| Negative balance | Validation failure |
| Insufficient funds | Transfer rejected |
| Repeated conflicts | Bounded retry or abort |
| Audit retrieval | Successful modifications are traceable |

Important additional production tests include:

- High-contention stress testing.
- Process termination during transaction execution.
- Database connection interruption.
- Deadlock handling.
- Serialization failure handling.
- Duplicate request delivery.
- Concurrent modifications to different fields.
- Concurrent updates across application instances.
- Audit retention and storage growth.

## 18. Practical Applications

Optimistic concurrency is particularly useful in systems where many users or services read shared information and periodically modify it.

Examples include:

- Banking account management.
- Inventory management.
- Order processing.
- Collaborative document editing.
- Enterprise configuration management.
- Customer relationship management.
- Reservation platforms.
- Distributed business applications.
- REST-based resource management.
- Version-controlled metadata.

The central engineering requirement remains consistent across these applications: a transaction must not commit a modification based on an obsolete record state without detecting the conflict.

## 19. Implementation Limitations

The in-memory implementations demonstrate concurrency behavior within a single application process.

They do not provide durable storage, crash recovery, or cross-process synchronization.

The PostgreSQL implementation provides transactional persistence, but its sample schema intentionally keeps the domain model compact.

The JavaScript implementation's synchronous critical section protects only its in-memory event-loop execution context.

The C++ and Python examples use synchronization primitives that simplify correctness at the cost of some write parallelism.

The Java implementation uses in-process locks and therefore requires database-backed coordination when multiple application instances share persistent records.

A production deployment must combine version validation with appropriate transaction boundaries, authorization, idempotency, durable audit records, failure recovery, and operational monitoring.

## 20. Key Technical Distinctions

| Concept | Exact responsibility |
|---|---|
| Versioning | Identifies a record state |
| Snapshot | Captures the state observed by a transaction |
| Compare-and-swap | Validates and conditionally commits a change |
| Conflict detection | Identifies a stale transaction |
| Conflict resolution | Determines how conflicting changes should proceed |
| Retry | Re-executes a transaction against a fresh state |
| Atomicity | Ensures a transaction's changes succeed or fail together |
| Isolation | Controls interactions and visibility among concurrent transactions |
| Idempotency | Prevents repeated requests from producing unintended duplicate effects |
| Audit logging | Records transaction and modification history |

Optimistic concurrency is effective when version validation is implemented at the actual persistence boundary, business operations are safely recalculated, and conflicts are handled as explicit transaction outcomes rather than silently overwritten.
