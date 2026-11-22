# Shared Locks, Exclusive Locks, and Lock Compatibility

## 1. Domain and Technical Scope

Locking is a concurrency-control mechanism used by database systems and transactional applications to regulate simultaneous access to shared resources.

A transaction may read or modify a resource while other transactions are accessing the same resource. Without appropriate coordination, concurrent operations can produce inconsistent results, lost updates, non-repeatable reads, and other concurrency anomalies.

Locks establish temporary access restrictions that determine which transactions can operate on a resource concurrently.

This implementation examines three fundamental concepts:

- Shared locks (S): permit concurrent compatible readers.
- Exclusive locks (X): provide exclusive access to a resource.
- Lock compatibility: determines whether a requested lock can coexist with locks already granted to other transactions.

The five implementations approach the same domain from different engineering perspectives:

| Implementation | Primary engineering perspective |
|---|---|
| Python | Thread-safe locking, transaction simulation, and resource lifecycle |
| JavaScript | Asynchronous scheduling and event-driven lock management |
| C++17 | Deterministic lock scheduling and transaction state management |
| Java 17 | Enterprise domain modeling, policies, and synchronized services |
| PostgreSQL | Relational lock management, integrity enforcement, and reporting |

## 2. Fundamental Lock Concepts

### 2.1 Shared Locks

A shared lock permits a transaction to read a resource while preventing incompatible exclusive access.

Multiple transactions can hold shared locks on the same resource simultaneously.

Example:

- Transaction T1 reads account 1001.
- Transaction T2 reads account 1001.
- Both transactions acquire shared locks.
- Neither transaction can obtain an exclusive lock while the other transaction retains its shared lock.

Shared locks are particularly useful when concurrent read operations should be permitted without allowing simultaneous modifications.

Typical characteristics:

- Multiple readers can coexist.
- Shared locks conflict with exclusive locks.
- Shared access does not authorize modification.
- Shared locks are normally released according to transaction or locking-protocol rules.

### 2.2 Exclusive Locks

An exclusive lock provides one transaction with exclusive access to a resource.

When a transaction holds an exclusive lock:

- Another transaction cannot acquire a shared lock on that resource.
- Another transaction cannot acquire an exclusive lock on that resource.
- The owning transaction can perform permitted modifications.

Example:

A payment transaction modifies account 1001.

1. T3 requests an exclusive lock.
2. Existing shared locks must be released.
3. T3 obtains exclusive access.
4. The account modification is performed.
5. The transaction completes.
6. The exclusive lock is released.

Exclusive locking protects modifications from incompatible concurrent operations.

### 2.3 Lock Compatibility Matrix

Compatibility is evaluated between the requested lock and the lock already held by another transaction.

| Requested lock | Existing shared | Existing exclusive |
|---|---|---|
| Shared (S) | Compatible | Incompatible |
| Exclusive (X) | Incompatible | Incompatible |

The matrix can be represented as:

| Requested / Held | S | X |
|---|---:|---:|
| S | 1 | 0 |
| X | 0 | 0 |

Where:

- 1 means compatible.
- 0 means incompatible.

The compatibility rule is asymmetric in its evaluation perspective, but the resulting compatibility relationship is symmetric for this lock model.

A shared request can coexist with existing shared holders. Every other combination involving another transaction is incompatible.

## 3. Lock Acquisition and Transaction Behavior

A lock acquisition request does not necessarily result in immediate ownership.

The lock manager evaluates the requested mode against the current holders and any applicable scheduling rules.

The general workflow is:

Transaction
    |
    v
Request lock
    |
    v
Validate transaction and resource
    |
    v
Evaluate compatibility
    |
    +---- Compatible ----> Grant lock
    |
    +---- Incompatible ---> Queue request
                                |
                                v
                         Existing holder releases
                                |
                                v
                         Reevaluate request
                                |
                                v
                         Grant or reject

A waiting transaction must not be treated as a lock holder.

This distinction is important because requesting an exclusive lock does not provide exclusive access until the lock has actually been granted.

### 3.1 Lock Ownership

A lock manager maintains ownership information for each resource.

A typical resource state contains:

- Resource identifier.
- Current transaction holders.
- Lock modes.
- Acquisition counts.
- Waiting requests.
- Request ordering.

For example:

| Resource | Transaction | Mode | State |
|---|---|---|---|
| account:1001 | T1 | S | Granted |
| account:1001 | T2 | S | Granted |
| account:1001 | T3 | X | Waiting |
| inventory:500 | T4 | X | Granted |

T1 and T2 can read account 1001 concurrently.

T3 cannot modify that account until both shared locks are released.

T4 can independently hold an exclusive lock on inventory 500 because it is a different resource.

### 3.2 Reentrant Lock Acquisition

Reentrant acquisition occurs when a transaction requests a lock on a resource it already owns.

The implementations maintain acquisition counts.

For example:

1. T1 acquires a shared lock on resource R.
2. T1 requests another shared lock on R.
3. The acquisition count increases.
4. The first release decreases the count.
5. Ownership remains until the final acquisition is released.

An existing exclusive holder can satisfy either shared or exclusive requests from the same transaction without surrendering exclusive ownership.

Reentrancy must be implemented carefully because incorrect acquisition counting can cause premature release or permanently retained locks.

## 4. Lock Upgrades and Downgrades

### 4.1 Shared-to-Exclusive Upgrade

A lock upgrade converts an existing shared lock into an exclusive lock.

Example:

- T1 holds S on account 1001.
- T1 decides to update the account.
- T1 requests X.
- T2 also holds S on account 1001.

T1 cannot safely receive exclusive ownership while T2 retains shared ownership.

A particularly dangerous situation occurs when T1 and T2 both hold shared locks and both attempt to upgrade.

Neither can proceed while the other retains its shared lock.

This can produce a conversion deadlock.

The implementations therefore reject unsafe upgrades when competing holders exist.

Alternative production approaches include:

- Acquiring an exclusive lock before reading.
- Using a database-specific update-lock mechanism.
- Applying a transaction-level deadlock prevention policy.
- Releasing the shared lock and requesting an exclusive lock, while accepting that the resource may change between operations.

### 4.2 Exclusive-to-Shared Downgrade

Downgrading converts exclusive ownership into shared ownership.

After a downgrade, other transactions may acquire compatible shared locks.

The supplied implementations focus on acquisition and upgrade behavior. A production system can implement explicit downgrade operations when its transaction semantics require them.

## 5. Lock Scheduling and Fairness

Compatibility alone does not determine the order in which waiting transactions receive locks.

A scheduler determines how requests are processed.

The Python, JavaScript, C++, and Java implementations use FIFO-oriented queue handling.

Consider:

| Order | Transaction | Requested mode |
|---|---|---|
| 1 | T1 | S |
| 2 | T2 | X |
| 3 | T3 | S |

Suppose another transaction currently holds X.

After that exclusive holder releases the resource, T1 and T2 may be eligible for processing according to their position and current holders.

T3 should not repeatedly bypass an earlier incompatible exclusive request.

This is important because unrestricted reader preference can cause writer starvation.

FIFO scheduling reduces this risk, although strict fairness guarantees depend on the complete scheduling implementation.

The SQL implementation records request order using generated request identifiers and maintains waiting-request metadata.

It does not implement an autonomous background lock scheduler. Waiting requests require an application-level scheduler or database-specific coordination to be granted after resources become available.

## 6. Python Implementation

### 6.1 Architecture

The Python implementation uses four primary structures:

| Component | Responsibility |
|---|---|
| `LockMode` | Defines shared and exclusive modes |
| `LockRequest` | Represents a pending acquisition |
| `LockState` | Maintains holders and waiting requests |
| `LockManager` | Coordinates acquisition and release |

`Transaction` provides a higher-level transaction interface.

### 6.2 Thread Safety

The implementation uses `threading.Condition` with an underlying reentrant lock.

The condition variable protects:

- Resource ownership.
- Acquisition counts.
- Waiting queues.
- Lock conversion.
- Release operations.

A waiting thread sleeps until the condition changes rather than repeatedly checking the resource.

When a holder releases a lock, the manager notifies waiting threads.

Each awakened thread reevaluates compatibility and queue position.

This is important because a notification does not guarantee that a particular transaction can immediately acquire the lock.

### 6.3 Timeout Management

Lock requests support configurable timeouts.

A transaction that cannot acquire a lock within the specified duration receives a `LockTimeout`.

The request is removed from the waiting queue, and other waiting transactions are notified.

Timeouts help prevent indefinite application-level waiting.

### 6.4 Exception Handling

The implementation distinguishes:

- Invalid resource or transaction identifiers.
- Lock acquisition timeouts.
- Unsafe upgrade attempts.
- Attempts to release unowned locks.

Transaction context management provides automatic cleanup.

### 6.5 Performance Characteristics

For a resource with H holders and Q waiting requests:

- Holder compatibility evaluation: O(H).
- Queue fairness evaluation: O(Q).
- Lock release: O(1) for direct holder lookup.
- Full transaction cleanup: O(R + H), where R is the number of tracked resources and H represents relevant ownership entries.

The in-memory implementation is suitable for simulation and single-process coordination.

It does not coordinate independent application processes or provide durable database locking.

## 7. JavaScript Implementation

### 7.1 Asynchronous Lock Management

JavaScript uses an event-driven architecture.

The implementation uses:

- `Map` for resource and transaction ownership.
- `Promise` for asynchronous acquisition.
- `EventEmitter` for lock lifecycle notifications.
- `setTimeout` for request expiration.
- Classes for lock manager and transaction responsibilities.

The acquisition operation returns a Promise.

A Promise resolves when the requested lock is granted and rejects when acquisition fails.

This allows application code to wait without blocking the JavaScript event loop.

### 7.2 Event-Driven Lifecycle

The lock manager emits two important events:

| Event | Meaning |
|---|---|
| `granted` | A transaction acquired a lock |
| `released` | A transaction released a lock |

These events can support monitoring and application-level observability.

The events are separate from the transaction's business operations.

### 7.3 Timeout and Queue Processing

Each waiting request receives a timer.

If the request exceeds its permitted waiting duration:

1. The request is removed from the queue.
2. Its Promise is rejected.
3. The queue is reevaluated.
4. Other eligible transactions can proceed.

The manager clears timers when requests are granted or removed.

This prevents unnecessary timer execution after completion.

### 7.4 Transaction Lifecycle

Transactions support:

- Shared acquisition.
- Exclusive acquisition.
- Explicit release.
- Commit.
- Rollback.

Both commit and rollback release owned locks and transition the transaction into an inactive state.

Subsequent lock requests against an inactive transaction are rejected.

### 7.5 Engineering Considerations

The implementation is appropriate for coordinating asynchronous operations within one Node.js process.

It is not a distributed lock service.

A production deployment requiring multiple application instances needs shared coordination through a database, distributed lock service, or another mechanism with appropriate failure and lease semantics.

The implementation also does not claim that FIFO scheduling eliminates every possible deadlock. Multi-resource transactions require additional deadlock detection or prevention.

## 8. C++17 Implementation

### 8.1 Domain Modeling

The C++ implementation models the lock system through:

| Structure | Purpose |
|---|---|
| `LockMode` | Lock type |
| `RequestStatus` | Acquisition outcome |
| `LockRequest` | Waiting acquisition |
| `LockHolder` | Current ownership |
| `LockState` | Resource-level state |
| `LockManager` | Central scheduling engine |
| `Transaction` | Transaction lifecycle |

STL containers provide resource indexing and ownership management.

### 8.2 Deterministic Scheduling

The program models lock acquisition through deterministic state transitions.

A request receives one of three outcomes:

- Granted.
- Waiting.
- Rejected.

The distinction between waiting and rejected is important.

A waiting request remains eligible for future processing.

A rejected request has failed validation or violates the defined locking policy.

### 8.3 Independent Resource Concurrency

Locks are maintained separately for each resource.

Therefore, an exclusive lock on `orders:10` does not prevent another transaction from acquiring an exclusive lock on `orders:20`.

This is an important property of resource-level locking.

A global lock would unnecessarily restrict independent operations.

### 8.4 Memory and Performance

The implementation uses:

- `unordered_map` for average O(1) resource and holder lookup.
- `queue` for FIFO waiting requests.
- Structured records for explicit state representation.

Compatibility checks require O(H) time for H existing holders.

The simplified queue implementation prioritizes clarity of state transitions over a highly optimized production scheduler.

The program is single-threaded and deterministic. It is not a concurrent operating-system mutex implementation.

## 9. Java 17 Enterprise Implementation

### 9.1 Enterprise Domain Types

The Java implementation separates domain concepts from transaction services.

Its major components include:

- `LockMode`
- `TransactionStatus`
- `RequestStatus`
- `LockFailure`
- `LockPolicy`
- `LockRequest`
- `HolderSnapshot`
- `ResourceSnapshot`
- `LockManager`
- `Transaction`
- `LockEligibilityService`

Java records represent immutable request and reporting data.

The internal holder and resource state remain mutable because lock ownership changes during transaction execution.

### 9.2 Resource-Specific Policies

Not every enterprise resource needs identical locking rules.

For example, an audit-log resource may permit shared access but prohibit exclusive access through the application-level policy.

The `LockPolicy` record expresses these restrictions.

The manager checks policy eligibility before processing the request.

This separates technical lock compatibility from authorization and resource-specific operational policy.

A compatible request can still be prohibited by policy.

### 9.3 State Transitions

Transactions support three states:

| State | Meaning |
|---|---|
| ACTIVE | Transaction can request locks |
| COMMITTED | Transaction completed successfully |
| ROLLED_BACK | Transaction was cancelled |

Only active transactions may request new locks.

Commit and rollback release all owned resources.

The implementation rejects attempts to complete an already completed transaction.

### 9.4 Synchronization

The lock manager uses synchronized methods to protect shared state.

This provides mutual exclusion around state modifications within one Java process.

It does not provide distributed coordination between application servers.

The eligibility service provides a snapshot-based assessment. Actual acquisition must still be performed through the lock manager because resource state can change after a snapshot is obtained.

### 9.5 Enterprise Application Implications

This architecture separates:

- Resource policy.
- Compatibility rules.
- Transaction lifecycle.
- Lock ownership.
- Acquisition eligibility.
- State reporting.

Such separation makes it easier to introduce additional policies, audit events, metrics, and external coordination services.

## 10. PostgreSQL Implementation

### 10.1 Relational Architecture

The SQL implementation uses the `lock_lab` schema.

Its primary relationships are:

    Repositories
        |
        v
    Resources
        |
        +------------------+
        |                  |
        v                  v
    Lock Holders      Lock Requests
        |                  |
        v                  v
    Transactions      Lock Events
        |
        v
    Transaction Status

The principal tables are:

| Table | Responsibility |
|---|---|
| `repositories` | Groups logical resources |
| `resources` | Stores lockable objects and policies |
| `transactions` | Stores transaction identities and states |
| `lock_compatibility` | Defines valid lock combinations |
| `lock_holders` | Stores granted ownership |
| `lock_requests` | Stores acquisition requests |
| `lock_events` | Preserves operational history |

Foreign keys maintain referential integrity.

Unique constraints prevent duplicate transaction ownership records for the same resource.

Check constraints restrict resource types, acquisition counts, and valid transaction states.

### 10.2 Compatibility as Relational Data

The compatibility matrix is stored in a relational table rather than being hardcoded exclusively into application logic.

This makes compatibility evaluation queryable.

A join between `lock_holders` and `lock_compatibility` determines whether an existing lock conflicts with a requested mode.

This is useful for reporting, auditing, and policy evaluation.

### 10.3 Trigger-Based Integrity

The `validate_lock_holder` trigger checks:

- Transaction activity.
- Resource-specific mode permissions.
- Existing incompatible holders.

The trigger provides a database-level integrity check for inserts and relevant updates.

The acquisition function and trigger serve different purposes.

The function coordinates the acquisition workflow.

The trigger protects the holder table from invalid ownership changes.

### 10.4 Transaction Serialization

The `request_lock` function locks the resource row using `FOR UPDATE`.

This serializes acquisition decisions made through that function for the same logical resource.

It prevents two concurrent calls from independently observing an empty holder set and granting conflicting locks.

Different resource rows can be processed independently.

The transaction row is also locked to validate transaction state.

Production applications must maintain a consistent ordering when acquiring multiple resource rows to reduce database deadlocks.

### 10.5 Waiting Requests

The `lock_requests` table distinguishes between:

- Waiting.
- Granted.
- Rejected.
- Cancelled.

A waiting request does not create a row in `lock_holders`.

This prevents the database from incorrectly treating pending requests as active lock ownership.

The implementation stores request ordering through generated request identifiers.

It does not automatically promote queued requests after release. An external scheduler must reevaluate pending requests, check compatibility, and atomically grant eligible requests.

### 10.6 Transaction Completion

The `finish_transaction` function completes an active transaction and releases its holdings.

It also cancels the transaction's remaining waiting requests for resources it owns.

The function distinguishes successful completion from rollback through the transaction-state enum.

### 10.7 Reporting

The SQL implementation provides views for:

- Current lock ownership.
- Waiting acquisition requests.
- Compatibility combinations.
- Resource contention.

Additional queries evaluate:

- Active shared holders.
- Active exclusive holders.
- Waiting requests.
- Current exclusive-lock eligibility.
- Historical lock events.
- Invalid ownership states.
- Incompatible ownership combinations.

Indexes support common access patterns involving resource identifiers, transaction identifiers, and waiting-request status.

## 11. Logical Locks and Native PostgreSQL Locks

The SQL model represents application-level logical locks.

It should not be confused with PostgreSQL's native locking mechanisms.

PostgreSQL provides several built-in lock facilities.

| Mechanism | Purpose |
|---|---|
| `FOR SHARE` | Acquires a shared row-level lock |
| `FOR UPDATE` | Acquires an exclusive-style row-level lock |
| `FOR NO KEY UPDATE` | Acquires a weaker row-level modification lock |
| `FOR KEY SHARE` | Protects referenced key values |
| Table locks | Coordinate operations at table level |
| Advisory locks | Coordinate application-defined resources |

PostgreSQL row-level lock modes have more detailed compatibility rules than the simplified S/X model implemented here.

In particular, `FOR UPDATE` and `FOR SHARE` should not be assumed to represent every database locking mode or isolation-level behavior.

The application-level model provides an educational representation of shared/exclusive compatibility.

The native database engine remains responsible for actual database concurrency control.

## 12. Locking Protocols and Concurrency Control

### 12.1 Two-Phase Locking

Two-Phase Locking (2PL) is a concurrency-control protocol with two phases.

**Growing phase**

- Transactions acquire locks.
- Existing locks can be retained.
- New locks may be acquired.

**Shrinking phase**

- Transactions release locks.
- New locks cannot be acquired under basic 2PL.

Strict Two-Phase Locking retains exclusive locks until transaction completion.

Rigorous Two-Phase Locking retains both shared and exclusive locks until transaction completion.

These protocols help guarantee conflict serializability under their respective assumptions.

The supplied implementations demonstrate acquisition, compatibility, and release. They do not enforce a complete 2PL protocol in every implementation.

### 12.2 Deadlocks

A deadlock occurs when transactions form a circular waiting dependency.

Example:

| Transaction | Holds | Waiting for |
|---|---|---|
| T1 | Resource A | Resource B |
| T2 | Resource B | Resource A |

Neither transaction can proceed.

Common approaches include:

- Wait-for graph analysis.
- Deadlock detection.
- Transaction timeouts.
- Wait-die prevention.
- Wound-wait prevention.
- Consistent resource acquisition ordering.

The implementations reject a specific unsafe shared-to-exclusive upgrade scenario, but that does not constitute complete deadlock detection.

### 12.3 Starvation

Starvation occurs when a transaction waits indefinitely because other transactions repeatedly receive access first.

A writer may experience starvation if new shared requests continually bypass its exclusive request.

Queue ordering and fairness policies help reduce this problem.

A production lock manager must define whether it prioritizes readers, writers, transaction age, or another scheduling criterion.

### 12.4 Lock Granularity

Lock granularity determines the size of the resource being protected.

| Granularity | Example | Main tradeoff |
|---|---|---|
| Database | Entire database | Simple coordination, low concurrency |
| Table | Entire customer table | Broad contention |
| Page | Database storage page | Intermediate coordination |
| Row | Individual account | Higher concurrency |
| Application object | Specific business resource | Flexible application-level coordination |

Fine-grained locking increases concurrency but introduces additional management overhead.

Coarse-grained locking reduces management complexity but can create unnecessary contention.

## 13. Practical Enterprise Scenario

Consider a banking application processing account statements and payments.

Three transactions access account 1001:

| Transaction | Operation | Required mode |
|---|---|---|
| T1 | Generate statement | S |
| T2 | Verify account balance | S |
| T3 | Execute payment | X |

T1 and T2 can execute concurrently because their shared locks are compatible.

T3 must wait because its exclusive lock conflicts with both shared locks.

After T1 and T2 complete, T3 can obtain exclusive access and perform the payment operation.

The same model applies to:

- Inventory reservation.
- Order processing.
- Configuration updates.
- Document editing.
- Financial ledger modifications.
- Concurrent enterprise data processing.

The critical design requirement is that lock ownership, transaction state, and resource identity must be coordinated consistently.

## 14. Security and Production Considerations

Locking is a concurrency-control mechanism, not an authorization mechanism.

A transaction holding an exclusive lock does not automatically have permission to modify the underlying business resource.

Production systems should separately implement:

- Authentication.
- Authorization.
- Resource ownership validation.
- Transaction identity validation.
- Input validation.
- Audit logging.
- Timeout management.
- Deadlock handling.
- Connection and session cleanup.

Application-level lock identifiers should be validated and consistently scoped.

Untrusted clients should not be allowed to release locks belonging to other transactions.

Lock managers should also account for transaction crashes, abandoned sessions, process termination, and distributed-system failures.

In PostgreSQL, native transactional locks are generally preferable when the resource is a database row or table because their lifecycle is managed by the database engine.

Logical application locks are useful when coordination must cover resources that do not map directly to database rows.

## 15. Implementation Limitations

| Implementation | Important limitation |
|---|---|
| Python | In-memory and process-local; upgrade conflicts are rejected rather than resolved |
| JavaScript | Single-process asynchronous coordination; no distributed lock guarantees |
| C++17 | Deterministic simulation rather than a multithreaded production lock manager |
| Java 17 | Synchronized in-process state; no cross-server coordination |
| PostgreSQL | Application-level model; pending requests require an external scheduling mechanism |

The implementations use a simplified shared/exclusive compatibility model.

They do not implement intention locks, predicate locks, range locks, multigranularity locking, or the complete compatibility matrices used by advanced database engines.

A production database also needs carefully defined isolation semantics, transaction recovery, deadlock handling, and atomic resource updates.

## 16. Technical Comparison

| Capability | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Shared locks | Yes | Yes | Yes | Yes | Yes |
| Exclusive locks | Yes | Yes | Yes | Yes | Yes |
| Compatibility evaluation | Yes | Yes | Yes | Yes | Yes |
| Waiting requests | Yes | Yes | Yes | Yes | Yes |
| FIFO-oriented scheduling | Yes | Yes | Yes | Yes | Recorded; external processing |
| Reentrant acquisition | Yes | Yes | Yes | Yes | Yes |
| Upgrade handling | Conflict rejection | Conflict rejection | Conflict rejection | Policy-based rejection | Policy-based rejection |
| Timeout support | Yes | Yes | No | No | Requires additional processing |
| Transaction cleanup | Yes | Yes | Yes | Yes | Yes |
| Resource-specific policies | Limited | Limited | Limited | Yes | Yes |
| Persistent ownership | No | No | No | No | Yes |

## 17. Key Technical Distinctions

The following distinctions are fundamental to understanding lock management:

1. A shared lock permits compatible concurrent reads; it does not provide exclusive modification rights.
2. An exclusive lock prevents other transactions from acquiring incompatible locks on the same resource.
3. Compatibility determines whether a request can coexist with existing ownership.
4. A waiting request is not a granted lock.
5. Lock ownership belongs to a transaction or an explicitly defined coordination identity.
6. Reentrant acquisition requires correct ownership counting.
7. Lock upgrades can introduce conversion deadlocks.
8. Queue scheduling influences fairness and starvation.
9. Deadlock prevention and detection are separate from basic compatibility evaluation.
10. Logical application locks and native database locks have different operational guarantees.

The central relationship is:

**Lock Mode + Existing Holders + Compatibility Policy + Scheduling Rules = Lock Acquisition Decision**

The correctness of a concurrent application depends not only on selecting shared or exclusive locks, but also on managing ownership, transaction lifecycle, waiting requests, and resource state consistently.
