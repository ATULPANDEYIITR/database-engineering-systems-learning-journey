# Serializable Systems: Serializable Execution and Practical Costs

## 1. Introduction

Database transactions frequently execute concurrently to improve throughput, resource utilization, and response time. Concurrent execution creates opportunities for interference between transactions that access shared data.

A database system must preserve the correctness guarantees of transaction processing while allowing independent operations to execute simultaneously.

**Serializability** is a correctness criterion for concurrent transaction execution. A concurrent schedule is serializable when its effect is equivalent to the effect of some serial execution of the same transactions.

A serial execution completes one transaction before beginning another. A serializable execution can interleave operations while preserving an equivalent logical outcome.

The central engineering problem is balancing correctness, concurrency, transaction throughput, and the practical cost of controlling interference.

## 2. Transaction Fundamentals

A transaction is a logical unit of database work containing one or more operations.

The conventional ACID properties describe transaction guarantees.

| Property | Meaning |
|---|---|
| Atomicity | All transaction operations succeed or the transaction is rolled back. |
| Consistency | Transactions preserve defined database integrity constraints. |
| Isolation | Concurrent transactions behave according to the selected isolation guarantees. |
| Durability | Committed changes survive failures according to the database's durability configuration. |

Consider a transfer of 200 units between two accounts.

The transaction contains:

1. Read the source balance.
2. Read the destination balance.
3. Subtract 200 from the source.
4. Add 200 to the destination.
5. Commit both changes.

The required invariant is:

`Initial total balance = Final total balance`

If the debit succeeds but the credit does not, the database has an inconsistent financial result. Atomicity prevents this partial publication.

## 3. Serial and Concurrent Execution

### Serial execution

A serial schedule executes transactions sequentially.

Example:

| Order | Operation |
|---|---|
| 1 | T1 reads Account A |
| 2 | T1 writes Account A |
| 3 | T1 commits |
| 4 | T2 reads Account A |
| 5 | T2 writes Account A |
| 6 | T2 commits |

There is no transaction overlap.

The advantage is straightforward reasoning about transaction outcomes. The disadvantage is reduced concurrency when transactions could safely operate independently.

### Concurrent execution

Concurrent execution interleaves operations from multiple transactions.

Example:

| Order | Transaction | Operation |
|---|---|---|
| 1 | T1 | Read A |
| 2 | T2 | Read B |
| 3 | T1 | Write A |
| 4 | T2 | Write B |
| 5 | T1 | Commit |
| 6 | T2 | Commit |

If the transactions operate on independent resources, this schedule can execute concurrently without introducing a conflict.

The objective is not to eliminate concurrency. It is to control harmful interference.

## 4. Serializability

Serializability establishes whether a concurrent schedule is equivalent to a serial transaction ordering.

Two important concepts are conflict serializability and view serializability.

### 4.1 Conflict serializability

Two operations conflict when all the following conditions hold:

- They belong to different transactions.
- They access the same data item.
- At least one operation is a write.

The conflicting operation pairs are:

| First operation | Second operation | Conflict |
|---|---|---|
| Read A | Read A | No |
| Read A | Write A | Yes |
| Write A | Read A | Yes |
| Write A | Write A | Yes |
| Read A | Write B | No |

The resource must be identical for the operations to conflict.

### 4.2 Precedence graph

A precedence graph determines conflict serializability.

- Each transaction represents a vertex.
- Each conflicting operation pair creates a directed edge.
- The edge points from the transaction performing the earlier conflicting operation to the transaction performing the later operation.

For example:

`T1 → T2`

means that the conflicting operations require T1 to precede T2 in an equivalent serial execution.

A schedule is conflict-serializable if and only if its precedence graph is acyclic.

A directed cycle indicates that the required transaction ordering is contradictory.

For example:

`T1 → T2 → T3 → T1`

No serial ordering can satisfy all three dependencies.

### 4.3 Topological sorting

A directed acyclic graph can be topologically sorted.

The resulting ordering provides an equivalent serial transaction sequence.

The Python, C++17, and Java implementations use Kahn's topological sorting algorithm:

1. Calculate the incoming edge count for each transaction.
2. Insert transactions with zero incoming edges into a queue.
3. Remove a transaction and append it to the result.
4. Reduce the incoming edge count of its neighboring transactions.
5. Add newly eligible transactions to the queue.
6. Compare the number of processed transactions with the total number of vertices.

If all vertices are processed, the graph is acyclic.

**Complexity**

For a graph with V transactions and E dependencies:

- Graph construction: O(n²) in the implemented pairwise schedule analysis, where n is the number of operations.
- Topological sorting: O(V + E).
- Graph storage: O(V + E).

The pairwise implementation is suitable for educational schedules and moderate-sized inputs. Production analyzers can improve graph construction by grouping operations by resource and examining only relevant conflicting pairs.

### 4.4 View serializability

View serializability is a broader correctness criterion than conflict serializability.

It considers:

- Initial reads.
- Read-from relationships.
- Final writes.

A schedule may be view-serializable without being conflict-serializable, particularly in schedules involving blind writes.

Conflict serializability is generally easier to analyze and is the more common practical foundation for scheduling algorithms.

## 5. Transaction Anomalies

Concurrent execution can produce results that violate expected transaction behavior.

### 5.1 Lost update

Two transactions read the same initial value and independently calculate updates.

Suppose Account A contains 1,000.

| Operation | T1 | T2 |
|---|---|---|
| 1 | Read 1,000 | |
| 2 | | Read 1,000 |
| 3 | Write 900 | |
| 4 | | Write 800 |

If the final value is 800, T1's update has been overwritten.

The correct outcome depends on the business operation and the intended serialization order.

### 5.2 Dirty read

A transaction reads data written by another transaction that has not committed.

If the writer subsequently aborts, the reader has used data that never became committed database state.

### 5.3 Non-repeatable read

A transaction reads the same row twice and obtains different committed values because another transaction modified it between the reads.

### 5.4 Phantom read

A transaction repeats a predicate-based query and obtains a different set of rows because another transaction inserted, deleted, or modified rows satisfying the predicate.

### 5.5 Write skew

Two transactions read overlapping data and modify different rows.

Each transaction may independently satisfy an invariant based on its snapshot, while their combined committed result violates that invariant.

Write skew is an important reason why preventing direct row-level write conflicts is not sufficient to guarantee serializability.

## 6. Concurrency Control Mechanisms

Serializable execution can be implemented through different concurrency control approaches.

### 6.1 Two-Phase Locking

Two-Phase Locking (2PL) divides transaction locking behavior into two phases.

| Phase | Behavior |
|---|---|
| Growing phase | Transactions acquire locks but do not release locks. |
| Shrinking phase | Transactions release locks and cannot acquire new locks. |

The protocol prevents schedules that violate conflict serializability.

Two common lock modes are:

**Shared lock (S)**

Allows multiple transactions to read the same resource.

**Exclusive lock (X)**

Allows one transaction to modify a resource while excluding incompatible access.

Lock compatibility:

| Existing lock | Requested shared | Requested exclusive |
|---|---|---|
| Shared | Compatible | Incompatible |
| Exclusive | Incompatible | Incompatible |

### 6.2 Strict Two-Phase Locking

Strict 2PL retains exclusive locks until commit or rollback.

This simplifies recovery because other transactions cannot observe uncommitted writes.

Its practical costs include:

- Lock acquisition overhead.
- Waiting time.
- Reduced concurrency under contention.
- Deadlock detection.
- Transaction rollback.
- Potential starvation.

The JavaScript and C++ implementations model lock ownership, compatibility, waiting, and transaction completion.

The JavaScript implementation also constructs a wait-for graph to identify deadlock cycles.

### 6.3 Deadlocks

A deadlock occurs when transactions wait for resources held by one another.

Example:

- T1 owns an exclusive lock on A.
- T2 owns an exclusive lock on B.
- T1 requests B.
- T2 requests A.

The wait-for graph becomes:

`T1 → T2 → T1`

A cycle indicates deadlock.

Typical resolution strategies include:

- Detecting cycles.
- Selecting a victim transaction.
- Rolling back the victim.
- Releasing its locks.
- Allowing blocked transactions to continue.

Deterministic resource acquisition order can reduce the probability of deadlocks.

### 6.4 Optimistic Concurrency Control

Optimistic Concurrency Control (OCC) assumes conflicts are sufficiently uncommon that transactions can execute without acquiring exclusive locks for every operation.

A conventional OCC transaction has three phases:

| Phase | Purpose |
|---|---|
| Read | Read data and calculate tentative changes. |
| Validation | Determine whether concurrent execution invalidated the transaction's assumptions. |
| Write | Publish validated changes. |

A transaction aborts when validation fails.

The Python implementation uses read sets, write sets, commit timestamps, and a private workspace.

The Java implementation extends the model with version tracking and explicit enterprise transaction states.

**Advantages**

- Reduced lock-management overhead during transaction execution.
- Good performance for workloads with relatively few conflicts.
- Independent transactions can progress concurrently.

**Disadvantages**

- Validation overhead.
- Aborted work must be repeated.
- High-contention workloads can produce excessive retries.
- Long-running transactions may repeatedly fail validation.

OCC is not automatically equivalent to a production serializable database implementation. Its correctness depends on the validation protocol and the assumptions made about transaction reads, writes, and publication.

## 7. Database Isolation Levels

Isolation levels describe the concurrency guarantees provided by a database.

| Isolation level | General behavior |
|---|---|
| Read Uncommitted | Allows the weakest isolation; PostgreSQL treats this as Read Committed. |
| Read Committed | Each statement obtains a fresh committed-data snapshot. |
| Repeatable Read | Maintains a transaction-level snapshot in PostgreSQL and prevents non-repeatable reads. |
| Serializable | Provides the strongest standard SQL isolation guarantee. |

PostgreSQL uses Multiversion Concurrency Control (MVCC) to maintain multiple row versions.

### 7.1 MVCC

MVCC allows readers and writers to operate with reduced direct blocking.

A transaction reads an appropriate database snapshot rather than necessarily waiting for every concurrent writer.

Important mechanisms include:

- Transaction visibility.
- Row-version management.
- Snapshot acquisition.
- Write conflict detection.
- Vacuum and dead-tuple maintenance.

MVCC improves concurrency but does not automatically make every concurrent schedule serializable.

### 7.2 PostgreSQL Serializable Snapshot Isolation

PostgreSQL implements Serializable isolation using Serializable Snapshot Isolation (SSI).

SSI builds on snapshot-based execution and monitors dangerous read/write dependency patterns.

Rather than requiring every reader to hold conventional shared locks for the entire transaction, SSI detects concurrency patterns that could lead to non-serializable execution.

A transaction may be aborted even when it does not encounter a direct row-level write conflict.

Applications must therefore handle serialization failures.

The important SQLSTATE is:

`40001`

A serialization failure requires retrying the complete transaction.

Retrying only the final failed statement is unsafe because earlier reads and business decisions may have become invalid.

## 8. Practical Costs of Serializable Execution

Serializable execution provides strong correctness guarantees, but these guarantees have operational costs.

### 8.1 Locking overhead

Lock-based mechanisms require:

- Lock tables.
- Lock acquisition.
- Lock compatibility checks.
- Lock release.
- Waiting queues.
- Deadlock detection.

The cost increases when transactions frequently access the same resources.

### 8.2 Validation overhead

Optimistic approaches must determine whether transaction assumptions remain valid.

Validation may involve:

- Read-set comparisons.
- Write-set comparisons.
- Version checks.
- Commit-history examination.
- Dependency tracking.

Large transaction sets increase validation work.

### 8.3 Transaction aborts

A transaction may perform substantial work before an isolation conflict is discovered.

When it aborts, its uncommitted changes must be discarded and the transaction may need to execute again.

This creates wasted CPU, memory, database I/O, and network activity.

### 8.4 Reduced throughput under contention

Serializable execution does not guarantee maximum throughput.

If many transactions compete for a small number of frequently modified resources, serialization constraints may significantly reduce parallel progress.

A high abort rate can also reduce effective throughput.

### 8.5 Latency

Transaction latency includes more than SQL execution time.

It can include:

- Lock waiting.
- Validation.
- Deadlock resolution.
- Rollback.
- Retry.
- Network communication.
- Commit durability operations.

For this reason, average latency alone is insufficient. Production measurements should also examine p95 and p99 latency.

## 9. Cost Comparison

| Dimension | Strict 2PL | Optimistic concurrency | PostgreSQL SSI |
|---|---|---|---|
| Main mechanism | Locks | Validation | Snapshot and dependency monitoring |
| Reader blocking | Possible | Usually avoided during reading | Usually reduced through MVCC |
| Writer conflicts | Lock waiting | Validation failure | Serialization conflict detection |
| Deadlocks | Possible | Not inherent to validation | Deadlocks remain possible through locking |
| Retry requirement | Deadlock or other transaction failure | Validation failure | Serialization failure |
| Contention behavior | Increased waiting | Increased aborts | Increased serialization failures |
| Main overhead | Lock management | Validation and retries | Dependency tracking and retries |
| Typical consideration | Predictable resource coordination | Low-conflict workloads | Strong database isolation |

These mechanisms are not interchangeable implementations with identical operational behavior. Their guarantees and costs depend on the complete execution protocol.

## 10. Implementation Architecture

The five source files approach serializable execution from complementary engineering perspectives.

| File | Implementation focus |
|---|---|
| Python | Schedule analysis, precedence graphs, OCC simulation, transaction validation, and performance estimation |
| JavaScript | Event-driven lock management, lock compatibility, wait queues, deadlock detection, and rollback |
| C++17 | Repository-independent transaction governance, lock ownership, wait-for graphs, and serializability analysis |
| Java 17 | Enterprise transaction domain model, immutable records, state transitions, version validation, and transaction services |
| PostgreSQL | Relational transaction processing, account transfers, isolation configuration, integrity constraints, auditing, and reporting |

### 10.1 Python implementation

The Python program defines an explicit transaction domain.

`Operation` represents an individual read or write.

`ConflictSerializabilityAnalyzer` constructs the precedence graph and performs topological sorting.

`Transaction` stores the transaction's identity, timestamps, state, and read/write sets.

`OptimisticTransactionManager` maintains:

- Shared database state.
- Resource versions.
- Transaction workspaces.
- Commit history.
- Validation results.

A transaction's private workspace prevents uncommitted writes from becoming visible through the manager's public snapshot.

The demonstration deliberately creates two transactions that read the same account balance. The first commits. The second fails validation because its read has become stale.

### 10.2 JavaScript implementation

The JavaScript implementation focuses on lock coordination.

`LockManager` tracks:

- Lock holders.
- Shared and exclusive ownership.
- Waiting transactions.
- Lock acquisition requests.
- Wait-for dependencies.
- Deadlock cycles.

`SerializableDatabase` separates committed database state from transaction-local workspace state.

The event-oriented model illustrates why waiting transactions must not commit while their lock requests remain unresolved.

The implementation is a synchronous lock-manager simulation. Its asynchronous entry point demonstrates application-level execution structure, not a complete production scheduler with independently executing worker transactions.

### 10.3 C++17 implementation

The C++ implementation uses STL containers to represent transaction state and lock ownership.

Its principal components are:

- `ScheduleAnalyzer`
- `GovernanceEngine`
- `Transaction`
- `Operation`
- `AnalysisResult`

The engine evaluates lock compatibility, records read/write sets, manages private writes, detects wait-for graph cycles, and publishes validated changes at commit.

Its use of `unordered_map` and `unordered_set` provides average constant-time lookup for many resource and transaction operations.

The implementation emphasizes explicit ownership, controlled state transitions, and predictable resource management.

### 10.4 Java 17 implementation

The Java program uses enterprise-oriented domain modeling.

Its principal types include:

- `Operation`
- `CommitRecord`
- `AnalysisResult`
- `Transaction`
- `EnterpriseTransactionService`
- `TransferService`

Java records represent immutable operation and commit-history data.

The transaction service uses synchronized methods to serialize access to its in-memory shared state.

The implementation maintains resource versions and validates transactions before publishing writes.

The `TransferService` separates business rules from transaction-management responsibilities.

The implementation is an in-memory educational model. Its synchronization is not a replacement for database-level distributed transaction isolation.

### 10.5 PostgreSQL implementation

The SQL script models a transactional account-processing system.

Its schema contains:

| Table | Responsibility |
|---|---|
| `repositories` | Organizes account-processing domains |
| `accounts` | Maintains account balances and states |
| `transaction_records` | Stores transaction lifecycle information |
| `transaction_entries` | Records debit and credit entries |
| `transaction_events` | Maintains transaction audit events |
| `serialization_metrics` | Records isolation-level performance observations |

The schema uses primary keys, foreign keys, unique constraints, check constraints, and indexes.

A trigger automatically increments the account version when relevant account data changes.

Another trigger records transaction status changes.

The `transfer_funds` procedure performs a controlled transfer using deterministic account locking.

The procedure executes within the transaction established by its caller.

The sample transaction uses PostgreSQL Serializable isolation.

The reporting views provide account-level summaries and isolation-level performance comparisons.

## 11. PostgreSQL Transaction Workflow

The database transaction workflow follows this sequence:

`BEGIN`

↓

`SET TRANSACTION ISOLATION LEVEL SERIALIZABLE`

↓

`Validate transaction inputs`

↓

`Acquire required locks`

↓

`Read account balances`

↓

`Check business constraints`

↓

`Update source and destination`

↓

`Insert debit and credit entries`

↓

`Record transaction events`

↓

`COMMIT`

If any operation fails, the application must roll back the transaction.

A successful commit makes the complete transaction visible.

### 11.1 Transaction retry design

Applications using Serializable isolation should implement bounded retries.

A robust retry process consists of:

1. Begin a new transaction.
2. Re-read all relevant database state.
3. Re-evaluate all business conditions.
4. Repeat the complete write operation.
5. Commit if validation succeeds.
6. Retry only recognized transient failures.
7. Stop after a configured retry limit.

A practical backoff strategy uses exponential delays with random jitter.

For example, a system can begin with a short delay and progressively increase the delay for subsequent attempts.

The retry mechanism must distinguish serialization failures from permanent business errors.

Insufficient funds should not trigger repeated execution.

Deadlock failures, generally identified by SQLSTATE `40P01`, require separate handling.

External side effects must also be controlled. Sending payment notifications or initiating external transfers before database commit can create duplicate or inconsistent effects.

An idempotency key and transactional outbox pattern can help coordinate these operations.

## 12. Performance Measurement

A meaningful serializability evaluation should measure more than execution time.

| Metric | Purpose |
|---|---|
| Transaction throughput | Measures completed transactions per time unit |
| Commit latency | Measures time required to complete a transaction |
| p95 latency | Identifies slower transactions |
| p99 latency | Identifies extreme latency |
| Abort rate | Measures unsuccessful transaction attempts |
| Retry count | Measures additional execution caused by conflicts |
| Lock wait time | Quantifies waiting for incompatible locks |
| Deadlock count | Measures cyclic lock dependencies |
| Validation time | Measures OCC or serialization validation overhead |
| CPU utilization | Identifies processing costs |
| Memory utilization | Identifies transaction and version-management costs |
| I/O operations | Measures storage-related workload |

The SQL implementation includes `serialization_metrics` and a reporting view for comparing isolation-level observations.

The inserted sample measurements are illustrative, not benchmark results from an actual concurrent workload.

### 12.1 A practical cost model

A simplified transaction-processing cost model is:

\[
C_{\text{total}} =
C_{\text{execution}} +
C_{\text{coordination}} +
C_{\text{validation}} +
C_{\text{retry}} +
C_{\text{recovery}}
\]

For an optimistic system, a simplified expected-cost model can be expressed as:

\[
E[C] =
C_{\text{normal}} +
P_{\text{abort}} \times C_{\text{retry}}
\]

Where:

- \(C_{\text{normal}}\) represents ordinary transaction processing cost.
- \(P_{\text{abort}}\) represents the probability of transaction abort.
- \(C_{\text{retry}}\) represents the additional cost of repeating the transaction.

The simplified model does not capture all dependencies between retries, contention, and transaction duration. It is useful for understanding why an apparently inexpensive validation mechanism may become expensive under heavy contention.

## 13. Engineering and Security Considerations

### 13.1 Data integrity

Business invariants should be enforced as close to the data as practical.

Useful controls include:

- Nonnegative balance constraints.
- Unique transaction references.
- Foreign-key relationships.
- Atomic debit and credit operations.
- Consistent account-state validation.
- Transactional audit records.

Application validation alone cannot prevent all concurrent integrity violations.

### 13.2 Lock ordering

Transactions that require multiple resources should acquire locks in a consistent order whenever practical.

For example, account identifiers can determine acquisition order.

This reduces circular waiting but does not eliminate every possible deadlock.

### 13.3 Retry safety

A retry can execute an operation more than once from the application's perspective.

Systems processing financial or externally visible operations should use:

- Unique idempotency identifiers.
- Duplicate request detection.
- Transactional audit records.
- Controlled external message delivery.
- Bounded retries.

### 13.4 Access control

Database users should receive only the privileges required for their responsibilities.

Sensitive operations should be protected through appropriate database roles and application authorization.

Audit records should not expose credentials, authentication tokens, or unnecessary personal information.

### 13.5 Resource management

Long-running transactions can retain old MVCC snapshots, increase resource consumption, and delay cleanup.

Applications should keep transactions short and avoid unnecessary network calls while a transaction is open.

Database monitoring should include active transactions, lock waits, deadlocks, serialization failures, and storage maintenance.

## 14. Important Implementation Limitations

The implementations are complementary educational models, not interchangeable production database engines.

| Implementation | Limitation |
|---|---|
| Python OCC | Uses conservative in-memory commit-history validation and does not implement a complete production OCC certification protocol. |
| JavaScript lock manager | Demonstrates locking and deadlock detection but does not provide a complete independently scheduled asynchronous transaction runtime. |
| C++17 engine | Uses an in-memory lock model and does not implement persistent recovery or complete lock-queue scheduling. |
| Java 17 service | Uses process-local synchronization and does not coordinate transactions across multiple application instances. |
| PostgreSQL SQL | Demonstrates database-level transaction handling, but production retry logic must be implemented by the calling application. |

The distinction between simulation and database execution is important.

A correct in-memory simulation does not automatically provide durability, crash recovery, distributed consistency, or production-grade isolation.

## 15. Complexity Reference

| Mechanism | Typical computational consideration |
|---|---|
| Precedence graph construction | O(n²) for pairwise operation comparison |
| Topological sorting | O(V + E) |
| Hash-based resource lookup | O(1) average |
| Transaction read/write-set storage | O(R + W) |
| Lock compatibility checks | Depends on the number of current lock holders |
| Wait-for graph cycle detection | O(V + E) |
| OCC validation | Depends on read-set size and relevant commit history |
| Indexed account lookup | Typically O(log N) for B-tree indexes |
| Transaction retry | Repeats the complete transaction workload |

Here, n represents schedule operations, V represents transactions, E represents graph dependencies, R represents read-set entries, W represents write-set entries, and N represents database rows.

## 16. Technical Distinctions

The following concepts should remain separate when analyzing serializable systems.

| Concept | Responsibility |
|---|---|
| Serial execution | Executes transactions sequentially. |
| Concurrent execution | Allows overlapping transaction operations. |
| Serializability | Defines whether concurrent execution is equivalent to a serial execution. |
| Conflict serializability | Uses conflicting operations and precedence graphs to establish equivalence. |
| Two-Phase Locking | Controls access through growing and shrinking lock phases. |
| Strict Two-Phase Locking | Retains exclusive locks until transaction completion. |
| Optimistic Concurrency Control | Executes provisionally and validates before publication. |
| MVCC | Maintains multiple row versions for concurrent access. |
| Serializable Snapshot Isolation | Detects dangerous concurrent dependencies to enforce serializable outcomes. |
| Transaction rollback | Discards uncommitted transaction changes. |
| Transaction retry | Re-executes the complete transaction after a retryable failure. |

Serializable execution is a correctness requirement, not a guarantee that every workload will execute quickly.

The practical engineering objective is to preserve valid transaction outcomes while controlling contention, validation overhead, retries, lock waiting, resource consumption, and application latency. 
