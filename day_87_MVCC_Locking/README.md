# MVCC vs Locking: Architectural Trade-offs

## 1. Technical Scope

Multi-Version Concurrency Control (MVCC) and locking are two important mechanisms for managing concurrent database transactions.

They address a common problem: multiple transactions accessing or modifying shared data without producing inconsistent results.

The central architectural difference is how concurrent access is coordinated.

- MVCC maintains multiple versions of records so transactions can read an appropriate committed version.
- Locking coordinates access by restricting conflicting operations while a transaction holds the necessary locks.

These mechanisms are not universally exclusive. Modern relational database systems can combine MVCC-based visibility with explicit row-level, table-level, and other locks.

PostgreSQL is an important example. It uses MVCC for transaction visibility and provides explicit locking mechanisms such as `SELECT FOR UPDATE`.

The implementations in this repository model these mechanisms separately to make their operational differences observable.

## 2. Core Terminology

| Term | Meaning |
|---|---|
| Transaction | A logical unit of database operations |
| Commit | Successful publication of transactional changes |
| Rollback | Discarding uncommitted changes |
| Snapshot | The transaction-visible database state at a particular logical time |
| Version | A representation of a record at a particular commit timestamp |
| Write conflict | An incompatible concurrent modification |
| Lock | A mechanism controlling concurrent access to a resource |
| Lock owner | The transaction currently holding a lock |
| Lock contention | Competition between transactions for incompatible locks |
| Deadlock | A circular dependency in which transactions wait for resources held by one another |
| Isolation level | The rules determining which concurrent transaction effects can be observed |
| First-committer-wins | A conflict policy that rejects a transaction when another transaction has already committed an incompatible write |
| Optimistic concurrency | A strategy that allows operations to proceed before validating whether conflicting modifications occurred |
| Pessimistic concurrency | A strategy that acquires protective locks before performing potentially conflicting operations |
| Write skew | A snapshot-isolation anomaly in which individually valid transactions produce a globally invalid state |

## 3. Multi-Version Concurrency Control

### 3.1 Concept

MVCC maintains multiple versions of database records rather than requiring every reader to wait for a writer.

A transaction reads data according to its visibility rules and snapshot.

When a transaction modifies a record, the database creates a new version instead of immediately replacing the version visible to every active transaction.

This allows readers and writers to operate with fewer direct conflicts.

### 3.2 Version Management

Consider an inventory record:

| Version | Commit timestamp | Available quantity |
|---|---:|---:|
| V1 | 1 | 100 |
| V2 | 2 | 90 |
| V3 | 3 | 75 |

A transaction with a snapshot timestamp of 1 sees V1.

A transaction beginning after timestamp 2 can see V2, assuming no later version is visible to it.

The existence of V3 does not automatically make it visible to transactions using an earlier snapshot.

A simplified visibility rule is:

`Visible version = newest committed version whose timestamp is not later than the transaction snapshot`

Actual database visibility rules also consider transaction identifiers, transaction commit status, isolation level, and database-specific implementation details.

### 3.3 Read and Write Behavior

A simplified MVCC transaction follows this sequence:

1. Begin a transaction.
2. Establish its visibility snapshot.
3. Read the appropriate record versions.
4. Stage modifications.
5. Validate conflicting writes.
6. Publish new versions atomically.
7. Commit or abort.

The Python, JavaScript, C++17, and Java 17 implementations use logical commit timestamps.

They implement first-committer-wins validation for modified records.

If two transactions begin with the same snapshot and both modify the same record, the first successful commit is accepted. The second transaction is rejected.

### 3.4 Read-Your-Writes

A transaction should normally see its own uncommitted modifications.

For example:

- Initial balance: 1,000.
- Transaction reads balance: 1,000.
- Transaction stages a debit of 100.
- Transaction reads the same balance again: 900.

The implementations maintain a transaction-local write set to provide this behavior.

### 3.5 Advantages

- High read concurrency.
- Reduced interference between ordinary readers and writers.
- Consistent transaction snapshots.
- Suitable for reporting and analytical workloads.
- Fewer reader-writer blocking situations.
- Historical versions can support snapshot-based processing.

### 3.6 Limitations

MVCC introduces version-management costs.

Important concerns include:

- Storage overhead from multiple versions.
- Garbage collection of obsolete versions.
- Vacuum requirements in PostgreSQL.
- Transaction metadata management.
- Long-running snapshots.
- Write-write conflicts.
- Retry requirements.
- Isolation anomalies under weaker isolation guarantees.

Long-running transactions can prevent obsolete versions from being reclaimed.

This can increase storage consumption and degrade database performance.

### 3.7 Snapshot Isolation Is Not Full Serializability

An important distinction is that snapshot isolation does not automatically guarantee serializable execution.

Consider a hospital staffing system.

Two administrators independently check that at least one doctor remains on duty.

Initial state:

| Doctor | On duty |
|---|---|
| Doctor A | Yes |
| Doctor B | Yes |

Transaction A switches Doctor A off duty after observing Doctor B on duty.

Transaction B switches Doctor B off duty after observing Doctor A on duty.

Both transactions may successfully commit under snapshot isolation because they modify different records.

The resulting state violates the business rule that at least one doctor must remain on duty.

This is a write-skew anomaly.

Solutions can include:

- Serializable isolation.
- Explicit locking of a shared coordination record.
- Database constraints where the rule can be expressed declaratively.
- Carefully designed application-level coordination.

The Python and other educational MVCC engines implement simplified snapshot isolation and do not claim full serializable behavior.

## 4. Locking-Based Concurrency Control

### 4.1 Concept

Locking coordinates access by assigning ownership of database resources to transactions.

A transaction acquires a lock before performing an operation that requires protection.

Other transactions attempting incompatible operations must wait, fail, or be aborted.

Locks may apply to:

- Rows.
- Tables.
- Pages or other storage structures.
- Database objects.
- Application-managed resources.

The exact locking behavior depends on the database engine and lock mode.

### 4.2 Exclusive Locks

An exclusive lock prevents competing transactions from obtaining incompatible locks on the same resource.

Consider an inventory record:

| Transaction | Operation | Result |
|---|---|---|
| T1 | Acquire exclusive lock | Granted |
| T1 | Read inventory | Allowed |
| T2 | Request incompatible lock | Must wait or fail |
| T1 | Update inventory | Allowed |
| T1 | Commit | Lock released |
| T2 | Acquire lock | Granted |

The C++, Python, and Java implementations use simplified exclusive-lock ownership.

The JavaScript implementation adds an asynchronous FIFO waiting queue.

These educational implementations use exclusive locks for both reads and writes. They do not implement a complete shared/exclusive database locking hierarchy.

### 4.3 Two-Phase Locking

Two-Phase Locking (2PL) divides a transaction into two phases.

**Growing phase**

The transaction acquires locks and does not release previously acquired locks.

**Shrinking phase**

The transaction releases locks and cannot acquire new locks under the conventional 2PL protocol.

Strict 2PL retains write locks until transaction completion. Implementations commonly retain other relevant locks as well, depending on the isolation and locking protocol.

The simplified pessimistic engines retain their acquired exclusive locks until commit or rollback.

### 4.4 Advantages

- Explicit control over conflicting operations.
- Useful for highly contested business records.
- Supports coordinated updates.
- Can protect business invariants when the correct records are locked.
- Provides predictable serialization for appropriately designed workflows.
- Useful for inventory reservations, financial transfers, and exclusive resource allocation.

### 4.5 Limitations

- Lock waiting.
- Lock contention.
- Deadlocks.
- Reduced throughput under high contention.
- Lock-management overhead.
- Long transactions holding resources.
- Increased operational complexity.

Locking does not automatically eliminate every concurrency anomaly. Correct isolation requires appropriate lock modes, resource selection, transaction boundaries, and database guarantees.

## 5. MVCC vs Locking: Technical Comparison

| Evaluation criterion | MVCC | Pessimistic locking |
|---|---|---|
| Primary mechanism | Multiple record versions | Lock ownership |
| Ordinary reads | Read visible versions | May require locks depending on isolation and operation |
| Reader-writer interference | Often reduced | Can occur |
| Concurrent writers | Conflict validation or serialization | Incompatible locks coordinate access |
| Storage overhead | Version storage | Lock-management overhead |
| Long transactions | Can delay version cleanup | Can retain locks and block others |
| Deadlocks | Possible when explicit locks are involved | Important operational concern |
| Read-heavy systems | Often suitable | May introduce unnecessary contention |
| Highly contested records | Can generate write conflicts | Can provide predictable serialization |
| Retry behavior | Often required for write conflicts | May be required after deadlocks or serialization failures |
| Historical visibility | Supported through versions and snapshots | Not inherently provided by locking |
| Implementation complexity | Version visibility and cleanup | Lock management and deadlock handling |
| Operational monitoring | Version retention and transaction age | Lock waits, blocked sessions, deadlocks |

Neither mechanism is universally faster.

Performance depends on workload distribution, transaction duration, access patterns, isolation requirements, database implementation, hardware, and operational configuration.

## 6. Optimistic and Pessimistic Concurrency

MVCC is frequently associated with optimistic concurrency, while explicit locking is associated with pessimistic concurrency.

These concepts are related but not identical.

### 6.1 Optimistic Concurrency

Optimistic concurrency assumes that conflicting writes are relatively uncommon.

Transactions perform work and validate whether the data has changed before committing.

A common application-level implementation uses a version column.

Example:

| Inventory ID | Quantity | Version |
|---|---:|---:|
| 101 | 100 | 5 |

An application reads version 5 and later attempts an update.

The update succeeds only if the current version remains 5.

The operation increments the version to 6.

If another transaction has already changed the record, the update affects zero rows and the application must handle the conflict.

Optimistic concurrency is useful when:

- Conflicts are relatively uncommon.
- Transactions are short.
- Application users may edit records over extended periods.
- Avoiding long-held application-level locks is important.

### 6.2 Pessimistic Concurrency

Pessimistic concurrency assumes that conflicting operations are sufficiently likely or expensive to justify acquiring protection before performing the operation.

Example:

A warehouse receives multiple reservation requests for the same limited inventory.

A transaction locks the inventory record, checks available quantity, performs the reservation, and commits.

Other conflicting transactions must wait for the lock to be released.

This approach is useful when:

- Hot records receive frequent updates.
- Conflicting operations must be coordinated.
- Business operations have strict consistency requirements.
- The cost of repeated optimistic failures is high.

### 6.3 Important Distinction

Optimistic concurrency is not synonymous with MVCC.

Pessimistic concurrency is not synonymous with every form of locking.

MVCC describes version-based visibility and concurrency management.

Optimistic concurrency describes a conflict-detection strategy.

Locking describes coordination through resource ownership.

A database can use MVCC internally while an application also implements optimistic version checks or requests explicit locks.

## 7. Isolation Levels and Concurrency Anomalies

Isolation levels determine which effects of concurrent transactions can be observed.

| Isolation level | Important behavior |
|---|---|
| Read Uncommitted | Permits weaker visibility guarantees where supported; PostgreSQL treats it as Read Committed |
| Read Committed | Each statement generally sees a snapshot of committed data at statement start |
| Repeatable Read | PostgreSQL provides transaction-level snapshot consistency and prevents non-repeatable reads |
| Serializable | Provides serializable execution, potentially requiring transaction retries |

Important anomalies include:

**Dirty read**

A transaction reads another transaction's uncommitted changes.

**Non-repeatable read**

A transaction reads the same record twice and obtains different committed values.

**Phantom read**

Repeated execution of a predicate-based query produces a different qualifying row set.

**Lost update**

A concurrent update overwrites another update without correctly accounting for the earlier modification.

**Write skew**

Two transactions modify different records based on overlapping snapshots, producing a state that violates a cross-record invariant.

Isolation level selection should follow business correctness requirements rather than a general assumption that stronger isolation is always preferable.

## 8. Architectural Trade-offs

### 8.1 Read-Heavy Analytical Systems

Examples:

- Business intelligence dashboards.
- Reporting platforms.
- Historical transaction analysis.
- Enterprise search.
- Operational monitoring.

MVCC is frequently suitable because ordinary readers can access consistent versions without routinely blocking writers.

Important considerations include:

- Snapshot duration.
- Version retention.
- Vacuum activity.
- Query execution time.
- Memory and storage consumption.

### 8.2 High-Contention Transactional Systems

Examples:

- Inventory reservations.
- Seat allocation.
- Financial account operations.
- Limited-resource scheduling.
- Payment processing.

Explicit locking may be appropriate when transactions repeatedly compete for the same records.

Important considerations include:

- Lock acquisition order.
- Transaction duration.
- Deadlock detection.
- Lock timeouts.
- Retry policies.
- Atomicity of multi-record operations.

### 8.3 Long-Running Transactions

Long-running transactions are problematic for both architectures.

In MVCC systems, they may retain old snapshots and delay version cleanup.

In locking systems, they may hold locks for extended periods and block competing transactions.

The correct response is generally to reduce transaction duration, avoid unnecessary external operations inside transactions, and design appropriate transaction boundaries.

### 8.4 Distributed Systems

Distributed databases introduce additional concerns:

- Network latency.
- Distributed transaction coordination.
- Replication lag.
- Leader election.
- Consensus.
- Cross-node locking.
- Conflict resolution.
- Availability during network partitions.

Local database locking and local MVCC are not sufficient descriptions of distributed consistency.

The architectural decision must account for the database's distributed transaction and replication model.

## 9. Repository Implementation Architecture

The six deliverables provide five executable implementations and one integrated technical reference.

| File | Architectural perspective | Main mechanisms |
|---|---|---|
| Python | Transaction simulation | Version history, snapshots, conflict validation, exclusive locks |
| JavaScript | Asynchronous concurrency | EventEmitter, Promises, FIFO lock queues, timeout handling |
| C++17 | Storage-engine simulation | STL containers, ordered version lookup, lock ownership |
| Java 17 | Enterprise transaction service | Domain objects, transaction interface, metrics, policy evaluation |
| PostgreSQL | Relational concurrency laboratory | MVCC, SELECT FOR UPDATE, version checks, triggers, indexes, transactions |
| README.md | Integrated technical explanation | Mechanisms, isolation, trade-offs, operational implications |

### 9.1 Python Implementation

The Python script contains two independent storage engines.

`MVCCStore` maintains a version history for every record.

Its main structures are:

- A dictionary mapping keys to version histories.
- A logical commit clock.
- Transaction snapshots.
- Transaction-local read and write sets.
- A metrics object.

`LockingStore` maintains current record values and an exclusive-lock ownership map.

The demonstration includes:

- Two transactions reading the same version.
- Competing writes.
- First-committer-wins validation.
- Lock contention.
- Lock release after completion.
- Rollback behavior.
- Workload evaluation.

The engine uses an in-memory reentrant mutex to protect its internal state. It does not implement persistent storage or a production lock-wait queue.

### 9.2 JavaScript Implementation

The JavaScript implementation focuses on asynchronous transaction coordination.

`EventDrivenStore` emits transaction lifecycle events.

`LockManager` manages exclusive locks and waiting requests through Promises.

Its FIFO queue transfers lock ownership before waking the next waiting transaction.

A timeout rejects a waiting request. The affected transaction is aborted and its previously held locks are released.

`ArchitectureEvaluator` provides a workload-based comparative score.

The JavaScript event loop ensures that synchronous publication within the commit method is not interleaved with another event-loop callback.

This does not provide cross-process synchronization or distributed transaction guarantees.

### 9.3 C++17 Implementation

The C++ program demonstrates storage-engine data structures and deterministic transaction execution.

`MVCCEngine` maintains:

- An unordered map of records.
- Ordered version histories.
- Snapshot timestamps.
- Transaction-local write sets.
- First-committer-wins validation.

The implementation uses `upper_bound` to locate the newest version visible to a snapshot.

For a record with V versions, this lookup takes O(log V) time.

`PessimisticLockingEngine` uses a map of lock owners.

The educational lock manager immediately rejects incompatible lock requests instead of blocking.

This makes lock contention observable without introducing operating-system synchronization or a scheduling subsystem.

### 9.4 Java 17 Implementation

The Java program uses explicit enterprise domain types.

Important structures include:

- `Transaction`
- `Version`
- `Metrics`
- `TransactionEngine`
- `MvccEngine`
- `LockingEngine`
- `Workload`
- `ArchitecturePolicy`

The `TransactionEngine` interface separates transaction operations from their underlying concurrency implementation.

The MVCC service synchronizes access to its in-memory storage.

The locking service maintains explicit record ownership and releases locks after transaction completion.

The architecture policy evaluates workloads using read ratio, contention, write concentration, and transaction duration.

The scoring model is illustrative and must not be interpreted as a measured performance result.

### 9.5 PostgreSQL Implementation

The SQL script models a warehouse inventory system.

Its principal tables are:

- `inventory`
- `transactions`
- `transaction_audit`
- `concurrency_events`

The inventory table maintains both the available quantity and a version number.

The SQL implementation demonstrates three distinct approaches:

**Snapshot-based reading**

Transactions use PostgreSQL's native MVCC visibility rules.

**Pessimistic reservation**

`reserve_inventory_locked` uses `SELECT FOR UPDATE` before validating and modifying inventory.

**Optimistic reservation**

`reserve_inventory_optimistic` checks the expected version during the update.

The version predicate prevents an application from silently applying an update based on stale data.

PostgreSQL still uses internal row locking for the actual update.

The multi-row transfer function demonstrates deterministic lock acquisition order.

The reporting views, triggers, indexes, and operational inspection queries expose transaction activity and concurrency-related database behavior.

## 10. PostgreSQL-Specific Architecture

### 10.1 MVCC Internals

PostgreSQL stores tuple versions and uses transaction metadata to determine visibility.

An UPDATE generally creates a new tuple version rather than modifying the version visible to all existing snapshots.

Old versions are not immediately removed because active transactions may still need them.

Vacuum reclaims storage occupied by versions that are no longer required.

### 10.2 SELECT FOR UPDATE

`SELECT FOR UPDATE` requests row-level locking.

A transaction that successfully acquires the lock can perform a protected modification.

Other transactions requesting conflicting locks on the same row may have to wait.

The lock normally remains held until transaction completion.

It is important that `SELECT FOR UPDATE` operates alongside PostgreSQL MVCC rather than replacing it.

### 10.3 Version Columns

An application-managed version column provides a convenient optimistic concurrency mechanism.

A typical record contains:

- Primary key.
- Business data.
- Version number.
- Last modification timestamp.

The update checks both the primary key and expected version.

If no row is updated, the application must determine whether the record was deleted, modified by another transaction, or rejected by a business condition.

### 10.4 Deadlock Prevention

Consider two transactions:

- Transaction A locks inventory record 1 and then record 2.
- Transaction B locks inventory record 2 and then record 1.

Both may end up waiting for one another.

A consistent lock acquisition order reduces this risk.

The PostgreSQL transfer function acquires locks in ascending inventory ID order.

This is a common technique for preventing avoidable deadlocks.

It does not eliminate every possible deadlock because other database operations and resources can introduce additional dependencies.

## 11. Performance and Complexity

### 11.1 MVCC

The simplified educational implementation uses:

| Operation | Approximate complexity |
|---|---|
| Begin transaction | O(1) |
| Read latest visible version | O(V) in Python and JavaScript |
| Read visible version | O(log V) in C++ |
| Stage a write | O(1) average |
| Validate write set | O(W) average |
| Publish write set | O(W) |

Where:

- V is the number of versions for a record.
- W is the number of records modified by a transaction.

The implementations do not model the full storage-engine costs of production MVCC.

### 11.2 Pessimistic Locking

| Operation | Simplified complexity |
|---|---|
| Acquire lock | O(1) average with hash-based ownership |
| Read record | O(1) average |
| Stage write | O(1) average |
| Commit W writes | O(W) average |
| Release L locks | O(L) average |

Where L represents the number of held locks.

Real database lock managers have additional synchronization, memory, scheduling, and deadlock-detection costs.

### 11.3 Important Benchmark Variables

A meaningful comparison requires measurements under controlled conditions.

Relevant variables include:

- Read-to-write ratio.
- Number of concurrent transactions.
- Record access distribution.
- Write hotspot concentration.
- Transaction duration.
- Average and tail latency.
- Conflict frequency.
- Lock wait time.
- Abort frequency.
- Retry overhead.
- Storage consumption.
- Version cleanup activity.
- CPU and memory consumption.

The workload scoring functions in the source files are educational decision aids, not substitutes for controlled benchmarking.

## 12. Failure Handling and Security

### 12.1 Transaction Failure

A transaction must not publish partial modifications.

The implementations stage changes in transaction-local write sets and validate before publication.

The PostgreSQL functions execute within their caller's transaction boundaries.

### 12.2 Conflict Handling

An optimistic conflict should not automatically be treated as a permanent business failure.

A retry policy may be appropriate when:

- The operation is safe to retry.
- The transaction can obtain fresh data.
- The retry count is bounded.
- Backoff prevents repeated contention.
- External side effects are controlled.

### 12.3 Lock Timeouts

Lock waits should be bounded according to application requirements.

A transaction exceeding its allowed wait time should follow a defined failure path.

PostgreSQL provides `lock_timeout` and `statement_timeout` configuration options.

### 12.4 Deadlocks

Deadlock detection and transaction aborts must be handled by the application.

Retries should be limited and should distinguish deadlock errors from permanent validation failures.

### 12.5 Data Integrity

Concurrency mechanisms do not replace database constraints.

Important controls include:

- Primary keys.
- Foreign keys.
- Unique constraints.
- Check constraints.
- Transaction boundaries.
- Atomic updates.
- Authorization.
- Input validation.

The PostgreSQL implementation uses a non-negative inventory constraint to prevent invalid committed quantities.

### 12.6 Security

Database concurrency design should consider:

- Least-privilege database roles.
- Restricted access to sensitive records.
- Parameterized application queries.
- Controlled transaction boundaries.
- Audit retention.
- Sensitive-data exposure through logs.
- Denial-of-service risks caused by excessive long-running transactions.
- Resource exhaustion caused by excessive lock waits or version retention.

Operational logs should avoid exposing credentials, authentication tokens, and unnecessary sensitive business data.

## 13. Practical Architecture Selection

| Scenario | Mechanism worth evaluating | Main consideration |
|---|---|---|
| Business intelligence | MVCC | Consistent reads with reduced reader-writer interference |
| Reporting during operational updates | MVCC | Snapshot visibility and version cleanup |
| Limited inventory reservation | Pessimistic locking | Coordination of competing reservations |
| User editing an existing record | Optimistic version checks | Detection of stale application state |
| Financial account transfer | Atomic transactions with appropriate locking | Consistency across multiple records |
| Long-running data analysis | MVCC with controlled snapshot duration | Version retention |
| High-contention resource allocation | Pessimistic locking | Lock wait and transaction duration |
| Cross-record business invariants | Serializable isolation or explicit coordination | Prevention of write skew |
| Distributed transaction processing | Database-specific distributed concurrency controls | Network and coordination costs |

A production architecture may combine these techniques.

For example, a warehouse application can use MVCC for inventory reporting, optimistic version checks for ordinary product updates, and `SELECT FOR UPDATE` for highly contested reservations.

The appropriate mechanism is determined by the consistency guarantees, workload characteristics, and operational constraints of the application.

## 14. Execution Requirements

| Deliverable | Runtime | Dependencies |
|---|---|---|
| Python | Python 3.10 or later | Standard library |
| JavaScript | Node.js 18 or later | Standard library |
| C++17 | C++17-compatible compiler | Standard library |
| Java | Java 17 | Standard library |
| PostgreSQL | PostgreSQL 15 or later | PostgreSQL database |

The PostgreSQL script uses `gen_random_uuid()` for transaction event references. It is available in supported PostgreSQL installations; installations requiring an extension can enable `pgcrypto`.

The SQL script creates the `concurrency_lab` schema and its tables, functions, triggers, indexes, sample records, and reporting views.

## 15. Implementation Limitations

These implementations are educational concurrency models rather than production database engines.

| Area | Limitation |
|---|---|
| MVCC | Simplified logical timestamps and snapshot visibility |
| Isolation | Snapshot isolation does not implement full serializability |
| Version cleanup | No production garbage collection or vacuum implementation in the in-memory engines |
| Locking | Educational exclusive locks rather than a complete lock-mode hierarchy |
| Deadlocks | No complete deadlock detection in the in-memory implementations |
| Scheduling | Deterministic demonstrations rather than a full concurrent workload benchmark |
| Durability | In-memory implementations do not provide crash recovery |
| Distributed consistency | No consensus or distributed transaction coordinator |
| Performance evaluation | Comparative heuristic scores rather than measured benchmark results |

PostgreSQL provides the production-oriented database perspective in this repository. Its actual isolation behavior, lock management, MVCC implementation, and operational statistics should be distinguished from the simplified educational models.

## 16. Integrated Architectural Model

The relationship between the principal components can be represented as follows:

Transaction Request
        |
        v
Transaction Manager
        |
        +-------------------------------+
        |                               |
        v                               v
Version Visibility                Lock Manager
        |                               |
        v                               v
MVCC Snapshot Read              Lock Acquisition
        |                               |
        v                               v
Local Transaction Changes       Protected Operations
        |                               |
        v                               v
Conflict Validation             Lock Ownership Validation
        |                               |
        +---------------+---------------+
                        |
                        v
                 Commit or Abort
                        |
             +----------+----------+
             |                     |
             v                     v
       Publish Changes       Discard Changes
             |
             v
       Metrics and Audit
             |
             v
      Operational Monitoring

The central architectural decision is not simply whether to use MVCC or locking. It is how to coordinate transaction visibility, concurrent modifications, business invariants, resource ownership, and transaction completion while meeting the application's correctness and performance requirements.
