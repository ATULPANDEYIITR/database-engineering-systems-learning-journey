# Pessimistic Concurrency: Lock-Based Approaches

## 1. Technical Scope

Pessimistic concurrency control coordinates concurrent transactions by acquiring locks before accessing or modifying shared resources.

The approach assumes that conflicting operations are sufficiently likely or costly that preventing simultaneous incompatible access is preferable to allowing conflicts and resolving them later.

A transaction requests permission to access a resource. The lock manager grants the request when the requested lock is compatible with existing locks. Otherwise, the transaction waits, times out, or becomes a candidate for deadlock resolution.

The implementations use enterprise banking and inventory-management scenarios to demonstrate lock ownership, transaction isolation, atomic updates, lock contention, and failure recovery.

## 2. Fundamental Concepts

### 2.1 Pessimistic concurrency control

Pessimistic concurrency control prevents conflicting transactions from simultaneously accessing a protected resource in incompatible ways.

Consider two transactions attempting to modify the same bank account:

- Transaction T1 reads an account balance of INR 10,000.
- Transaction T2 attempts to withdraw INR 7,000.
- Transaction T1 attempts to withdraw INR 6,000.

Without appropriate coordination, both transactions might make decisions using the same initial balance.

A pessimistic exclusive lock ensures that only one transaction can perform the protected modification at a time.

The principal objective is to preserve transaction correctness by coordinating access before conflicting operations execute.

### 2.2 Shared and exclusive locks

Two fundamental lock modes are used.

| Lock mode | Purpose | Compatibility |
|---|---|---|
| Shared (S) | Reading protected data | Compatible with other shared locks |
| Exclusive (X) | Modifying protected data | Incompatible with other shared and exclusive locks |

The compatibility matrix is:

| Existing lock | Requested S | Requested X |
|---|---|---|
| S | Granted | Blocked |
| X | Blocked | Blocked |

Multiple transactions can therefore read the same resource concurrently, while a modification requires exclusive ownership.

Some database systems also implement additional lock modes, such as update locks and intention locks, to coordinate complex locking hierarchies.

### 2.3 Lock granularity

Lock granularity determines the size of the protected resource.

| Granularity | Protected resource | Typical implication |
|---|---|---|
| Database | Entire database | Maximum contention |
| Table | Complete table | Blocks many unrelated operations |
| Page | Database storage page | Coordinates groups of records |
| Row | Individual record | Allows greater concurrency |
| Field | Individual attribute | Fine-grained coordination |

Fine-grained locking can improve concurrency but increases lock-management overhead.

Coarse-grained locking reduces management overhead but can unnecessarily block unrelated transactions.

The appropriate granularity depends on transaction patterns, resource contention, and database implementation.

## 3. Lock-Based Transaction Protocols

### 3.1 Two-Phase Locking

Two-Phase Locking (2PL) divides transaction execution into two phases.

**Growing phase**

- The transaction acquires locks.
- It may acquire additional locks.
- It may upgrade compatible locks.
- It cannot release locks and subsequently acquire new ones under basic 2PL.

**Shrinking phase**

- The transaction releases locks.
- It cannot acquire additional locks.

The protocol ensures conflict serializability under its assumptions.

The lock point is the instant at which a transaction acquires its final lock. Serial execution order can be established using the ordering of transaction lock points.

### 3.2 Strict Two-Phase Locking

Strict 2PL retains exclusive locks until transaction commit or rollback.

This prevents other transactions from reading or modifying uncommitted changes protected by those locks.

Its important benefits include:

- Preventing dirty reads of exclusively locked data.
- Avoiding cascading rollback caused by reading uncommitted writes.
- Simplifying transaction recovery.
- Maintaining predictable resource ownership.

The Python, JavaScript, C++17, and Java implementations retain acquired locks until transaction termination.

A database may implement strict locking internally using different lock-manager and recovery mechanisms.

### 3.3 Rigorous Two-Phase Locking

Rigorous 2PL retains both shared and exclusive locks until transaction termination.

It is stricter than ordinary strict 2PL.

The distinction matters because strict 2PL generally requires exclusive locks to remain held until completion, while rigorous 2PL requires all locks to remain held.

### 3.4 Lock conversion

Lock conversion changes an existing lock into another mode.

**Lock upgrade**

A transaction holding a shared lock requests an exclusive lock on the same resource.

Example:

- T1 obtains a shared lock on account A.
- T1 reads the account balance.
- T1 decides to update the balance.
- T1 requests an exclusive lock.

The upgrade can block if other transactions still hold shared locks.

Multiple simultaneous upgrade requests can contribute to deadlocks.

**Lock downgrade**

A transaction holding an exclusive lock changes it into a shared lock.

The conversion allows concurrent readers after the transaction no longer requires exclusive access.

Implementations must handle conversion atomically to prevent an unsafe release-and-reacquire interval.

## 4. Deadlocks and Contention

### 4.1 Deadlock

A deadlock occurs when transactions wait indefinitely for resources held by one another.

Example:

| Transaction | First lock | Second request |
|---|---|---|
| T1 | Resource A | Resource B |
| T2 | Resource B | Resource A |

T1 waits for T2, while T2 waits for T1.

Neither can proceed.

### 4.2 Coffman conditions

Four conditions are associated with deadlock:

1. Mutual exclusion: At least one resource cannot be shared.
2. Hold and wait: A transaction holds resources while requesting additional resources.
3. No preemption: Resources cannot simply be taken away from their owners.
4. Circular wait: A circular chain of resource dependencies exists.

Deadlock requires all four conditions.

### 4.3 Wait-for graph

A wait-for graph represents dependencies between transactions.

An edge T1 → T2 means T1 is waiting for a resource held by T2.

A directed cycle indicates a deadlock.

The Python and C++ implementations use depth-first search to identify cycles in their transaction wait-for graphs.

For a graph containing V transactions and E dependency edges, cycle detection takes O(V + E) time.

The JavaScript implementation maintains a wait-for graph while managing asynchronous lock requests.

Production systems generally need additional handling for transaction cancellation, graph maintenance, fairness, and concurrent graph updates.

### 4.4 Deadlock prevention

Deadlock prevention changes transaction behavior to avoid at least one necessary deadlock condition.

Common strategies include:

| Strategy | Mechanism |
|---|---|
| Global lock ordering | Resources are acquired in a consistent order |
| Wait-die | Older transactions wait; younger transactions abort |
| Wound-wait | Older transactions abort younger conflicting transactions |
| No-wait | A conflicting lock request fails immediately |
| Timeout | Transactions exceeding a waiting threshold are aborted |

The banking examples acquire account locks in ascending account identifier order.

Consistent ordering prevents circular waiting between transactions following the same locking protocol.

### 4.5 Deadlock detection and recovery

Deadlock detection identifies an existing cycle.

Recovery generally involves selecting a victim transaction and rolling it back.

Victim selection can consider:

- Transaction age.
- Amount of work performed.
- Number of locks held.
- Rollback cost.
- Business priority.
- Previous abort history.

A transaction that has been rolled back may be retried, subject to an appropriate retry policy.

Repeatedly restarting the same transaction without backoff can produce starvation.

### 4.6 Lock timeout

A lock timeout limits how long a transaction may wait.

It protects applications from unbounded waiting and helps control resource consumption.

A timeout is not equivalent to deadlock detection.

A transaction can time out even when no deadlock exists.

The Python and JavaScript examples use timed lock acquisition. C++ uses `std::condition_variable::wait_until`, and Java uses timed `tryLock`.

## 5. Pulling the Concepts Together: Lock Compatibility and Transaction Execution

The fundamental lifecycle is:

    Transaction begins
          |
          v
    Request resource lock
          |
          v
    Check existing ownership
          |
          +---- Compatible ----> Grant lock
          |
          +---- Incompatible --> Wait / Timeout / Abort
          |
          v
    Read or modify protected resource
          |
          v
    Commit or Rollback
          |
          v
    Release transaction locks

A lock manager is responsible for tracking ownership and coordinating conflicting requests.

It must also handle transaction cancellation, ownership cleanup, lock upgrades, and waiter notification.

## 6. Python Implementation: Transaction Simulation

The Python implementation uses a transaction-oriented banking model.

### Main components

| Component | Responsibility |
|---|---|
| `LockMode` | Defines shared and exclusive modes |
| `TransactionState` | Tracks transaction lifecycle |
| `Transaction` | Stores lock ownership and undo information |
| `LockManager` | Coordinates lock requests |
| `Bank` | Performs atomic account transfers |

### Lock manager

A `threading.Condition` coordinates access to the lock table.

A condition variable allows a transaction to wait until another transaction releases a conflicting lock.

The lock table maps resource identifiers to transaction ownership and lock modes.

A transaction requesting an exclusive lock cannot proceed while another transaction holds a conflicting lock.

### Undo log

Before modifying an account, the transaction stores its previous balance.

If a failure occurs, rollback restores the recorded values.

The undo log illustrates the principle of atomic transaction execution.

A production database uses a durable recovery mechanism rather than relying exclusively on an in-memory application-level undo list.

### Concurrency demonstration

Multiple threads execute account transfers.

The implementation verifies:

- Exclusive resource ownership.
- Lock compatibility.
- Insufficient-funds handling.
- Timeout behavior.
- Atomic balance updates.
- Balance conservation.

The total value of all accounts must remain unchanged after successful transfers.

**Implementation limitation:** The Python example is an educational lock-manager simulation. Its transaction state and undo records are in memory and are not durable across process failure. Its wait-for graph also does not implement a complete production-grade deadlock victim recovery protocol.

## 7. JavaScript Implementation: Asynchronous Lock Management

The JavaScript implementation adopts an event-driven approach using Node.js.

### Main components

| Component | Responsibility |
|---|---|
| `LockManager` | Maintains resource ownership and waiting queues |
| `Transaction` | Encapsulates transaction operations |
| `InventoryService` | Implements inventory reservation |
| `EventEmitter` | Publishes lock and transaction events |

### Asynchronous acquisition

JavaScript uses Promises to represent lock requests.

An operation requesting an unavailable lock waits asynchronously rather than blocking the event loop.

The lock manager maintains:

- A resource map.
- Current lock holders.
- A FIFO waiting queue.
- Transaction state.
- A wait-for graph.
- Timeout handles.

### FIFO scheduling

The queue preserves request ordering.

Compatible shared requests can be granted together, while an exclusive request waits for conflicting holders.

This policy reduces the risk of indefinite bypassing by newer requests, although strict FIFO can reduce throughput when an exclusive request is waiting behind other work.

### Event-driven monitoring

The implementation emits events for:

- Lock acquisition.
- Lock waiting.
- Transaction commit.
- Transaction rollback.

These events provide a basis for transaction monitoring and operational observability.

**Implementation limitation:** Node.js asynchronous execution does not automatically make shared memory safe across worker threads or processes. A production distributed lock manager requires coordination beyond an ordinary in-process JavaScript map.

## 8. C++17 Implementation: Resource Locking Engine

The C++ implementation uses an inventory-management scenario.

Its principal design objective is explicit synchronization and transaction resource management.

### Main components

| Component | Responsibility |
|---|---|
| `Transaction` | Stores transaction state and undo information |
| `LockManager` | Coordinates resource ownership |
| `InventoryService` | Implements inventory reservations |
| `LockMode` | Represents lock compatibility |
| `TransactionState` | Represents transaction lifecycle |

### Synchronization mechanisms

The implementation uses:

- `std::mutex` for protecting shared lock-manager structures.
- `std::condition_variable` for waiting on lock availability.
- `std::unique_lock` for controlled mutex ownership.
- `std::chrono` for timeout management.
- STL containers for resource and transaction tracking.

The condition variable allows a waiting thread to release the manager mutex while sleeping.

When another transaction releases its locks, the manager notifies waiting threads.

### Complexity

| Operation | Expected complexity |
|---|---|
| Transaction registration | O(1) average |
| Lock-table lookup | O(log R) |
| Lock ownership update | O(log R) |
| Wait-for graph traversal | O(V + E) |
| Resource release | O(L log R) |

Where:

- R represents tracked resources.
- V represents transactions.
- E represents wait-for graph edges.
- L represents locks held by a transaction.

**Implementation limitation:** The C++ example provides a compact lock manager for a controlled demonstration. A production system would require more comprehensive waiter scheduling, lock upgrades, cancellation, transaction isolation, and durable recovery.

## 9. Java 17 Implementation: Enterprise Banking Service

The Java implementation models an enterprise transaction service.

It uses explicit domain types and separates business operations from lock management.

### Main components

| Component | Responsibility |
|---|---|
| `Account` | Immutable account representation |
| `Transaction` | Transaction identity and lifecycle |
| `LockPolicy` | Lock acquisition contract |
| `LockRegistry` | Resource-level synchronization |
| `AccountRepository` | Account data operations |
| `TransactionManager` | Commit and rollback |
| `BankingService` | Transfer business rules |

### ReentrantReadWriteLock

Java's `ReentrantReadWriteLock` supports concurrent readers and exclusive writers.

Its read lock permits multiple simultaneous readers.

Its write lock requires exclusive ownership.

Fair mode is enabled in the implementation to provide queue-oriented scheduling behavior, although fairness can reduce throughput.

### Deterministic lock ordering

The service sorts account identifiers before acquiring locks.

This reduces circular-wait risk when concurrent transfers use the same locking protocol.

### Business validation

The service verifies:

- Valid source and destination accounts.
- Distinct account identifiers.
- Positive transfer amounts.
- Sufficient funds.
- Destination balance overflow.
- Transaction lifecycle state.

The account repository records original values for rollback.

**Implementation limitation:** The example is an in-memory enterprise service, not a durable transaction coordinator. Its lock registry is designed for exclusive account-lock usage and is not a complete general-purpose shared-to-exclusive lock conversion implementation.

## 10. PostgreSQL Implementation: Database-Level Pessimistic Locking

The SQL implementation demonstrates how PostgreSQL manages concurrent access through database transactions and row-level locks.

### 10.1 SELECT FOR UPDATE

`SELECT ... FOR UPDATE` acquires row-level locks on selected records.

Other transactions attempting conflicting updates or locking reads must wait until the transaction releases the locks.

Example use case:

- A banking application identifies two accounts.
- It locks both rows.
- It validates their balances.
- It performs the debit and credit.
- It commits the transaction.

The operation ensures that concurrent transfers cannot independently modify the same protected account rows.

### 10.2 SELECT FOR SHARE

`SELECT ... FOR SHARE` obtains shared row locks.

It prevents conflicting updates and deletion while allowing compatible shared locks.

It is useful when a transaction must protect records against modification while performing a dependent operation.

### 10.3 SELECT FOR NO KEY UPDATE

`SELECT ... FOR NO KEY UPDATE` obtains a row lock weaker than `FOR UPDATE`.

It conflicts with other updates and competing `NO KEY UPDATE` locks but permits `KEY SHARE` locks.

The distinction is useful when an operation modifies non-key attributes and does not require the strongest row-lock mode.

### 10.4 NOWAIT

`NOWAIT` causes a locking statement to fail immediately if a conflicting lock cannot be obtained.

It is useful when waiting is unacceptable.

PostgreSQL reports a lock-not-available error rather than allowing the transaction to wait indefinitely.

### 10.5 SKIP LOCKED

`SKIP LOCKED` skips rows that cannot immediately be locked.

It is particularly useful for concurrent queue workers.

For example, two workers can claim different pending jobs without both attempting to process the same locked record.

It is important to understand that `SKIP LOCKED` deliberately provides an inconsistent view of the selected rows. It is appropriate for queue processing, not general-purpose consistent reporting.

### 10.6 Transaction boundaries

PostgreSQL releases transaction-scoped locks when the transaction commits or rolls back.

The SQL implementation uses explicit transactions to demonstrate atomic operations.

The transfer function:

1. Validates the transfer request.
2. Locks the source and destination accounts.
3. Validates account status and currency.
4. Checks sufficient funds.
5. Records the transfer.
6. Updates both balances.
7. Marks the transfer completed.

If any operation fails, the transaction must be rolled back.

### 10.7 Deadlock handling

PostgreSQL automatically detects deadlocks.

When a deadlock occurs, PostgreSQL aborts one transaction to allow another to proceed.

Important SQLSTATE values include:

| SQLSTATE | Meaning |
|---|---|
| `40P01` | Deadlock detected |
| `55P03` | Lock not available |
| `40001` | Serialization failure |
| `57014` | Query canceled |

Applications should retry the complete transaction when the failure is retryable.

A retry policy should use bounded attempts and randomized backoff.

### 10.8 Operational monitoring

The SQL implementation uses:

- `pg_locks` to inspect lock ownership.
- `pg_stat_activity` to inspect database sessions.
- `pg_blocking_pids()` to identify blocking relationships.

Indexes are provided for transaction retrieval, audit history, and pending job selection.

The effectiveness of indexes should be verified using execution plans and realistic workloads.

## 11. Important Distinctions

### Pessimistic versus optimistic concurrency

| Dimension | Pessimistic | Optimistic |
|---|---|---|
| Conflict assumption | Conflicts are anticipated | Conflicts are relatively uncommon |
| Main mechanism | Locks | Validation and conflict detection |
| Contention | Transactions may wait | Transactions may restart |
| Rollback behavior | Used for transaction failures | Also used after validation conflicts |
| Suitable workload | High contention or costly conflicts | Low contention with independent operations |

Optimistic concurrency commonly uses version numbers, timestamps, or conditional updates.

Pessimistic concurrency acquires locks before performing conflicting operations.

Neither approach is universally superior.

### Locking versus isolation levels

Locking is a concurrency-control mechanism.

Isolation levels define guarantees about what concurrent transactions can observe.

These concepts are related but are not interchangeable.

| Isolation level | Important characteristic |
|---|---|
| Read Uncommitted | PostgreSQL treats this as Read Committed |
| Read Committed | Each statement obtains a new committed-data snapshot |
| Repeatable Read | Transaction-level snapshot with additional anomaly prevention |
| Serializable | Transactions behave as though executed serially, with possible serialization failures |

Explicit row locks can be used at different isolation levels.

They do not automatically prevent every possible phantom or predicate-level anomaly.

Serializable isolation provides stronger guarantees where required by business invariants.

## 12. Performance and Security Considerations

### Performance

Long-running transactions retain locks longer and increase contention.

Important operational measures include:

- Keeping transactions short.
- Acquiring resources in a consistent order.
- Avoiding unnecessary exclusive locks.
- Using suitable indexes.
- Limiting transaction scope.
- Monitoring lock waits.
- Applying reasonable timeouts.
- Avoiding excessive lock upgrades.
- Designing bounded retry policies.

A high number of blocked transactions can reduce throughput even when CPU and storage resources are available.

### Security

Locking protects transaction consistency, not application authorization.

An application must separately enforce:

- Authentication.
- Account ownership.
- Transaction authorization.
- Input validation.
- Least-privilege database permissions.
- Audit-log access restrictions.
- Protection against unauthorized direct database modifications.

Audit records should not be treated as tamper-proof merely because they are stored in a database table.

Production financial systems should use controlled database roles, durable audit infrastructure, and appropriate operational access controls.

### Failure handling

A production implementation should explicitly handle:

- Lock acquisition timeout.
- Deadlock victim selection.
- Interrupted operations.
- Transaction rollback.
- Connection loss.
- Database restart.
- Duplicate requests.
- Retry exhaustion.
- Partial external side effects.

External operations such as payment notifications must not be assumed to roll back automatically with a database transaction.

A transactional outbox or another durable messaging mechanism can coordinate database changes with external delivery.

## 13. Cross-Language Implementation Comparison

| Dimension | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Synchronization | Condition variable | Promise queue | Mutex and condition variable | Read/write locks | Database lock manager |
| Lock ownership | Transaction map | Resource map | Lock table | Lock registry | Database engine |
| Shared locks | Yes | Yes | Yes | Read lock | Yes |
| Exclusive locks | Yes | Yes | Yes | Write lock | Yes |
| Timeout | Monotonic deadline | Timer | `wait_until` | `tryLock` | `lock_timeout` |
| Deadlock handling | Wait-for graph | Wait-for graph | Wait-for graph | Ordered acquisition | Database detection |
| Rollback | Undo log | Undo log | Undo log | Undo log | Transaction rollback |
| Durability | No | No | No | No | Yes, subject to database configuration |

The implementations demonstrate different engineering approaches rather than identical production transaction managers.

## 14. Practical Applications

Pessimistic locking is particularly useful where concurrent modifications must preserve strict resource-level invariants.

Representative applications include:

- Bank account transfers.
- Inventory reservation.
- Warehouse stock allocation.
- Seat reservation.
- Financial ledger updates.
- Concurrent job claiming.
- Shared resource scheduling.
- Critical configuration updates.
- Enterprise record processing.

The decision to use pessimistic locking should consider contention frequency, transaction duration, rollback cost, and the consequences of conflicting updates.

## 15. Execution and Validation

### Python

Run the script with Python 3.10 or later.

It uses standard-library modules and requires no external dependencies.

The demonstrations verify lock compatibility, rollback, concurrent account transfers, and balance conservation.

### JavaScript

Run the program with Node.js 18 or later.

It uses built-in modules and requires no npm dependencies.

The demonstration processes concurrent inventory reservations and verifies that unsuccessful reservations do not change stock.

### C++17

Compile with a C++17-compatible compiler and thread support.

The implementation uses the standard library and launches concurrent inventory-reservation workers.

### Java 17

Compile the single source file using Java 17.

The program executes concurrent banking transactions and checks the financial conservation invariant.

### PostgreSQL

Execute the SQL script using a PostgreSQL 15 or later database.

The script creates the schema, tables, constraints, indexes, functions, procedure, trigger, sample records, and reporting queries.

The locking demonstrations involving `NOWAIT`, competing transactions, and `SKIP LOCKED` are best tested using multiple independent database sessions.

## 16. Important Engineering Limitations

The application-level examples are simulations and do not replace a production database transaction manager.

In particular:

- In-memory undo logs are not crash-recovery mechanisms.
- Application locks do not coordinate across independent processes unless a shared coordination system is used.
- Lock fairness does not guarantee starvation-free execution under every scheduling policy.
- Timeout handling does not prove that a deadlock exists.
- Lock acquisition order must be consistent across all relevant code paths.
- A transaction may require predicate or range protection beyond individual row locks.
- Retrying transactions requires idempotency and careful treatment of external side effects.
- High-contention workloads can make pessimistic locking expensive.

Correct pessimistic concurrency design therefore requires coordinated resource ownership, appropriate isolation guarantees, transaction boundaries, reliable rollback, and operational monitoring.
