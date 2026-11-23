# Deadlocks: Detection, Prevention and Recovery

## 1. Deadlock Fundamentals

A deadlock is a condition in which two or more transactions remain blocked indefinitely because each transaction is waiting for a resource held by another transaction in the same group.

A transaction may acquire resources successfully, execute some operations, and subsequently become unable to proceed because another transaction controls a required resource.

Deadlocks are particularly relevant to:

- Database transaction processing
- Operating system resource management
- Multithreaded applications
- Distributed services
- File systems
- Concurrent financial operations
- Shared-memory applications
- Enterprise resource scheduling

Consider two transactions and two resources:

| Transaction | First resource | Second request |
|---|---|---|
| T1 | DATABASE | FILE_SYSTEM |
| T2 | FILE_SYSTEM | DATABASE |

The execution sequence is:

1. T1 acquires DATABASE.
2. T2 acquires FILE_SYSTEM.
3. T1 requests FILE_SYSTEM and waits.
4. T2 requests DATABASE and waits.
5. Neither transaction can continue independently.

The resulting dependency graph is:

    T1 ----waits for----> T2
     ^                    |
     |                    |
     +------waits for-----+

The circular dependency prevents either transaction from progressing.

## 2. Necessary Conditions for Deadlock

A deadlock requires four conditions, commonly known as the Coffman conditions.

| Condition | Meaning | Example |
|---|---|---|
| Mutual exclusion | A resource cannot be simultaneously controlled by multiple transactions | Exclusive database lock |
| Hold and wait | A transaction retains resources while requesting additional resources | T1 holds DATABASE while requesting FILE_SYSTEM |
| No preemption | Resources cannot normally be forcibly taken away | Lock remains with its owner |
| Circular wait | Transactions form a circular resource dependency | T1 waits for T2 and T2 waits for T1 |

All four conditions must exist for this classical deadlock model.

Removing at least one condition prevents this category of deadlock.

This provides the theoretical foundation for deadlock prevention.

## 3. Resource Allocation Graph

A Resource Allocation Graph represents the relationship between transactions and resources.

It contains two types of vertices:

- Transaction vertices represent executing transactions.
- Resource vertices represent available or allocated resources.

Two important edge types are:

| Edge | Meaning |
|---|---|
| Request edge | Transaction requests a resource |
| Assignment edge | Resource is assigned to a transaction |

Example:

    T1 ----request----> R2
    T2 ----request----> R1

    R1 ----assigned---> T1
    R2 ----assigned---> T2

The resulting cycle indicates a deadlock when every resource involved has exactly one instance.

For resources with multiple instances, a cycle alone is not sufficient to establish that a deadlock exists.

## 4. Wait-for Graph

A Wait-for Graph simplifies resource dependency analysis.

Resource vertices are removed, leaving direct transaction-to-transaction dependencies.

An edge:

    T1 -> T2

means T1 is waiting for a resource currently held by T2.

For single-instance resources:

- No directed cycle means no deadlock.
- A directed cycle means a deadlock exists.

The graph is the primary structure used by the detection implementations in this project.

### Graph construction

For each waiting transaction:

1. Identify its requested resource.
2. Identify the resource's current owner.
3. Create a directed edge from the waiting transaction to its owner.
4. Repeat for all outstanding requests.

The resulting graph represents the current blocking relationships rather than historical resource requests.

## 5. Deadlock Detection

Detection allows transactions to acquire resources normally and checks whether their current dependencies form a deadlock.

This approach does not necessarily prevent deadlocks. It identifies them after they have occurred.

### 5.1 Depth-first search

The Python, JavaScript, C++17 and Java 17 implementations use depth-first search to identify cycles.

The algorithm maintains three node states:

| State | Meaning |
|---|---|
| WHITE | Not visited |
| GRAY | Currently being explored |
| BLACK | Completely processed |

A directed edge to a GRAY vertex identifies a back edge.

The back edge identifies a cycle in the active DFS path.

The cycle represents a deadlock in the single-instance resource model.

### 5.2 Detection algorithm

The process is:

1. Construct the wait-for graph.
2. Initialize all transaction vertices as unvisited.
3. Start DFS from each unvisited vertex.
4. Mark the current vertex as GRAY.
5. Explore its outgoing dependencies.
6. Identify back edges to GRAY vertices.
7. Extract the corresponding cycle.
8. Mark the completed vertex as BLACK.

### 5.3 Complexity

Let:

- V represent the number of transactions.
- E represent the number of wait-for dependencies.

Using adjacency lists:

| Operation | Time complexity |
|---|---|
| Graph construction | O(V + E) |
| DFS cycle detection | O(V + E) |
| Graph storage | O(V + E) |

The implementations use adjacency structures appropriate to each language.

Cycle enumeration can require additional processing when a graph contains many overlapping cycles. The implementations primarily focus on identifying cycles needed for recovery.

### 5.4 Single-instance and multiple-instance resources

An important distinction exists between resource types.

**Single-instance resources**

Each resource has exactly one available instance.

A cycle in the wait-for graph establishes deadlock.

**Multiple-instance resources**

A resource type may have several interchangeable instances.

A cycle may exist without a deadlock because another instance could become available and allow a transaction to proceed.

Multiple-instance detection requires allocation, outstanding-request and available-instance information.

The classical detection algorithm maintains:

- Available: currently available resource instances.
- Allocation: resources allocated to each transaction.
- Request: outstanding resource requirements.

It repeatedly identifies transactions whose requests can be satisfied using the currently available resources.

Their allocated resources are then considered available to other transactions.

Transactions that cannot be eliminated from this process may be deadlocked.

The implementations in this project deliberately use single-instance resources for the wait-for graph model.

## 6. Deadlock Prevention

Deadlock prevention ensures that at least one necessary deadlock condition cannot occur.

Unlike detection, prevention applies restrictions before or during resource acquisition.

### 6.1 Resource ordering

Resource ordering assigns every resource a unique numerical rank.

Transactions must acquire resources in increasing order.

Example:

| Resource | Order |
|---|---:|
| ACCOUNT | 1 |
| DATABASE | 2 |
| LEDGER | 3 |
| AUDIT_LOG | 4 |

A transaction may acquire:

    ACCOUNT -> DATABASE -> LEDGER

It cannot subsequently request ACCOUNT after acquiring LEDGER.

This eliminates circular wait because every dependency must follow the same increasing order.

The Python, JavaScript, C++17 and Java 17 programs implement this policy.

The PostgreSQL implementation enforces it through `request_resource_ordered()`.

**Trade-off:** Resource ordering requires advance knowledge of resource dependencies. It may restrict execution flexibility and requires consistent ordering across application components.

### 6.2 Wait-die scheme

Wait-die is a timestamp-based prevention algorithm.

Every transaction receives a timestamp when it starts.

Older transactions have smaller timestamps.

When a transaction requests a resource held by another transaction:

| Requester | Resource owner | Decision |
|---|---|---|
| Older | Younger | Wait |
| Younger | Older | Abort requester |

A younger transaction cannot wait for an older transaction.

The scheme prevents circular waiting because waiting dependencies follow a consistent age direction.

An aborted transaction may restart with its original timestamp to reduce starvation.

### 6.3 Wound-wait scheme

Wound-wait uses the opposite decision rules.

| Requester | Resource owner | Decision |
|---|---|---|
| Older | Younger | Abort resource owner |
| Younger | Older | Wait |

An older transaction can preempt a younger transaction.

A younger transaction must wait for an older transaction.

This creates an ordered dependency structure and prevents circular wait.

The Java implementation includes both wait-die and wound-wait policy evaluation. Wait-die is demonstrated directly.

### 6.4 Prevention trade-offs

| Policy | Main mechanism | Operational consideration |
|---|---|---|
| Resource ordering | Fixed resource acquisition order | Requires consistent ordering |
| Wait-die | Older transactions may wait | Younger transactions may restart frequently |
| Wound-wait | Older transactions abort younger holders | Can increase rollback activity |

Prevention reduces deadlock occurrence but can reduce concurrency or introduce additional transaction restarts.

## 7. Deadlock Avoidance

Deadlock avoidance differs from prevention and detection.

Avoidance evaluates whether granting a resource request would leave the system in a safe state.

A safe state is one in which at least one ordering of transaction completion exists.

### Banker's algorithm

The Banker's algorithm is a classical multiple-instance resource avoidance algorithm.

It uses:

| Structure | Purpose |
|---|---|
| Available | Available resource instances |
| Max | Maximum resource demand of each transaction |
| Allocation | Currently allocated instances |
| Need | Remaining resource requirements |

The relationship is:

    Need = Max - Allocation

The algorithm searches for a sequence in which every transaction can finish using the resources currently available and those released by previously completed transactions.

If such a sequence exists, the state is safe.

If no sequence exists, granting the request could result in an unsafe state.

An unsafe state is not necessarily a deadlock. It means that safe completion cannot currently be guaranteed using the declared maximum requirements.

The five implementations focus on resource ordering, detection and recovery rather than implementing the Banker's algorithm.

## 8. Deadlock Recovery

Deadlock recovery begins after a deadlock has been detected.

Its objective is to break the circular dependency and restore transaction progress.

Two important recovery approaches are:

- Transaction termination
- Resource preemption

### 8.1 Transaction termination

A recovery manager selects one or more transactions for termination.

The terminated transaction releases its allocated resources.

Waiting transactions may then acquire the released resources.

Termination can involve:

- Full transaction rollback
- Partial rollback
- Restart from a safe checkpoint

The implementations use full transaction abort and resource release.

### 8.2 Victim selection

Selecting a victim is an important recovery decision.

Possible criteria include:

- Transaction age
- Number of held resources
- Amount of completed work
- Rollback cost
- Business priority
- Number of affected transactions
- Restart cost

The Python, JavaScript and C++17 implementations select the youngest transaction.

The Java implementation supports two victim-selection strategies:

- Youngest transaction
- Fewest held resources

The PostgreSQL procedure supports corresponding recovery policies.

The youngest transaction strategy is simple and deterministic within the simulation. It is not necessarily optimal for production systems because transaction age alone does not measure rollback cost.

### 8.3 Resource release

After victim selection:

1. Remove the victim's pending requests.
2. Mark the transaction ABORTED.
3. Increment its rollback counter.
4. Release all resources held by the victim.
5. Process waiting queues.
6. Grant available resources to eligible waiting transactions.
7. Rebuild the dependency graph.
8. Repeat detection if necessary.

This ordering is important.

Ownership records must be cleared before waiters are granted resources. Otherwise, the manager could temporarily create inconsistent ownership information.

### 8.4 Starvation

Repeatedly selecting the same transaction class as a victim can cause starvation.

A transaction may repeatedly restart without completing.

Possible controls include:

- Preserving transaction timestamps across restarts.
- Increasing victim-selection cost for previously aborted transactions.
- Tracking rollback frequency.
- Giving priority to transactions close to completion.
- Limiting repeated aborts.

The sample implementations track rollback counts to support this type of extension.

## 9. Distinguishing the Four Management Approaches

| Approach | Timing | Main objective |
|---|---|---|
| Prevention | Before deadlock formation | Eliminate a necessary deadlock condition |
| Avoidance | Before granting a request | Preserve a safe system state |
| Detection | During execution | Identify existing deadlocks |
| Recovery | After detection | Break deadlocks and restore progress |

These approaches are related but are not interchangeable.

A production resource manager may combine prevention, detection and recovery depending on the resource type and workload.

---

# 10. Python Implementation

**File:** `deadlock_management.py`

The Python implementation provides a complete single-instance resource management simulator.

### Main components

| Component | Responsibility |
|---|---|
| `Transaction` | Maintains transaction state and allocated resources |
| `Resource` | Maintains ownership and waiting queue |
| `DeadlockManager` | Coordinates acquisition, detection and recovery |
| `DeadlockReport` | Records detected cycles and selected victims |
| `TransactionState` | Defines lifecycle states |
| `ResourceOrderViolation` | Reports prevention violations |

### Transaction lifecycle

    ACTIVE
      |
      +---- resource unavailable ----> WAITING
      |                                  |
      |                                  +---- resource granted ----> ACTIVE
      |
      +---- successful completion ----> COMMITTED
      |
      +---- deadlock recovery ---------> ABORTED

The implementation uses dictionaries for transaction and resource lookup, sets for resource ownership, and deques for FIFO waiting queues.

### Important mechanisms

**Wait-for graph**

`build_wait_for_graph()` derives dependencies from waiting transactions and current resource owners.

**Detection**

`detect_deadlocks()` performs DFS with WHITE, GRAY and BLACK states.

**Victim selection**

`select_victim()` chooses the transaction with the greatest start sequence.

**Recovery**

`recover()` removes the victim's requests, releases its resources and wakes waiting transactions.

**Prevention**

`prevention_enabled` activates global resource ordering.

### Validation

The program checks:

- Duplicate transaction identifiers
- Duplicate resource identifiers
- Unknown resources
- Invalid resource orders
- Resource ownership violations
- Invalid transaction states
- Out-of-order acquisition
- Attempts to commit waiting transactions

The `run_assertions()` function validates cycle detection, victim termination, successful recovery and resource-order enforcement.

### Execution

Requirements:

- Python 3.10 or later
- Standard library only

Run:

    python deadlock_management.py

---

# 11. JavaScript Implementation

**File:** `deadlock_management.js`

The JavaScript implementation uses an event-driven resource manager.

Unlike the synchronous Python simulator, it represents pending resource requests through Promises.

### Main components

| Component | Responsibility |
|---|---|
| `DeadlockManager` | Central resource coordination |
| `Transaction` | Transaction lifecycle and ownership |
| `Resource` | Current owner and pending requests |
| `DeadlockError` | Reports detected deadlocks |
| `ResourceOrderError` | Reports prevention violations |
| `EventEmitter` | Publishes operational events |

### Asynchronous resource acquisition

`acquire()` returns a Promise.

When a resource is available, the Promise resolves immediately.

When unavailable, the request is placed in a FIFO queue.

The transaction becomes WAITING.

When the resource is released, the manager grants it to the next eligible waiter and resolves the corresponding Promise.

### Event-driven monitoring

The implementation emits events such as:

| Event | Meaning |
|---|---|
| `RESOURCE_REGISTERED` | Resource created |
| `TRANSACTION_STARTED` | Transaction initialized |
| `RESOURCE_ACQUIRED` | Immediate resource grant |
| `RESOURCE_WAITING` | Request placed in queue |
| `DEADLOCK_DETECTED` | Circular dependency identified |
| `TRANSACTION_ABORTED` | Victim terminated |
| `RESOURCE_GRANTED` | Waiting transaction resumed |
| `DEADLOCK_RECOVERED` | Recovery completed |

The event listener provides structured information suitable for monitoring and debugging.

### Failure handling

The implementation uses `Promise.allSettled()` to handle both successful resource acquisition and rejected requests.

This is important because a deadlock victim may have an outstanding Promise that must be rejected when its transaction is aborted.

The manager also prevents a transaction from issuing a second outstanding resource request while already waiting.

### Execution

Requirements:

- Node.js 18 or later
- No npm dependencies

Run:

    node deadlock_management.js

---

# 12. C++17 Implementation

**File:** `deadlock_management.cpp`

The C++ implementation emphasizes deterministic resource governance and efficient state management.

### Main components

| Component | Responsibility |
|---|---|
| `Transaction` | Stores transaction state |
| `Resource` | Stores ownership and queue |
| `ResourceManager` | Implements allocation and recovery |
| `DeadlockReport` | Stores recovery results |
| `TransactionState` | Defines transaction states |

### Data structures

| Structure | Purpose |
|---|---|
| `std::map` | Ordered transaction and resource lookup |
| `std::set` | Prevents duplicate held resources |
| `std::vector` | Stores waiting queues and detected cycles |
| `std::function` | Supports recursive DFS |
| `std::algorithm` | Provides sorting, searching and selection |

The program uses STL containers without third-party libraries.

### Resource governance

`acquire()` validates transaction status, checks resource ordering, grants available resources or places requests in the waiting queue.

`buildWaitForGraph()` creates the current dependency graph.

`detectDeadlocks()` identifies cycles through recursive DFS.

`selectVictim()` selects the youngest transaction.

`releaseAll()` clears ownership and wakes eligible waiting transactions.

### Engineering considerations

The implementation uses ordered maps and sets.

Lookup operations therefore generally require logarithmic time rather than constant-time average lookup.

This is a deliberate trade-off favoring deterministic iteration and straightforward debugging.

The DFS implementation uses recursive traversal. Very deep dependency graphs may require an iterative DFS implementation to avoid stack exhaustion.

### Execution

Compile:

    g++ -std=c++17 -O2 -Wall -Wextra -pedantic deadlock_management.cpp -o deadlock_management

Run:

    ./deadlock_management

On Windows:

    .\deadlock_management.exe

---

# 13. Java 17 Implementation

**File:** `DeadlockGovernance.java`

The Java implementation models an enterprise transaction governance service.

It emphasizes explicit domain types, policy objects, immutable reporting structures and separation of responsibilities.

### Domain model

| Type | Responsibility |
|---|---|
| `TransactionId` | Strongly typed transaction identifier |
| `ResourceId` | Strongly typed resource identifier |
| `Transaction` | Transaction lifecycle and state |
| `Resource` | Resource ownership |
| `AuditEvent` | Operational event record |
| `DeadlockReport` | Immutable recovery result |
| `VictimSelector` | Recovery policy interface |

### Prevention policies

The `PreventionPolicy` enum defines:

- NONE
- RESOURCE_ORDERING
- WAIT_DIE
- WOUND_WAIT

The implementation evaluates these policies during resource acquisition.

### Recovery policies

The `RecoveryPolicy` enum defines:

- YOUNGEST_TRANSACTION
- FEWEST_LOCKS

The `VictimSelector` interface separates victim selection from recovery execution.

This allows the recovery strategy to change without rewriting graph construction or transaction management.

### Enterprise-oriented features

The program uses:

- Java records for immutable identifiers and reports.
- Interfaces for recovery policy selection.
- Enums for controlled state transitions.
- Collections for resource and transaction management.
- Streams for candidate selection.
- Audit events for operational traceability.
- Custom validation through exceptions.

### Wait-die behavior

An older transaction can wait for a younger transaction.

A younger transaction requesting a resource held by an older transaction is aborted.

### Wound-wait behavior

An older transaction requesting a resource held by a younger transaction aborts the younger transaction.

A younger requester must wait for an older holder.

The implementation demonstrates wait-die and provides policy evaluation for wound-wait.

### Execution

Requirements:

- Java Development Kit 17

Compile:

    javac --release 17 DeadlockGovernance.java

Run:

    java DeadlockGovernance

---

# 14. PostgreSQL Implementation

**File:** `deadlock_management.sql`

The PostgreSQL implementation models deadlock management as a relational workflow.

It stores transactions, resources, locks, waiting requests, deadlock events and audit information.

### Database architecture

    deadlock_lab
       |
       +-- transactions
       |
       +-- resources
       |
       +-- held_locks
       |
       +-- lock_waits
       |
       +-- wait_for_edges (VIEW)
       |
       +-- deadlock_events
       |
       +-- transaction_audit
       |
       +-- reporting views
       |
       +-- management functions and procedures

### Table relationships

| Table | Purpose |
|---|---|
| `transactions` | Transaction identity and lifecycle |
| `resources` | Resource definitions and ordering |
| `held_locks` | Current resource ownership |
| `lock_waits` | Outstanding resource requests |
| `deadlock_events` | Detected cycles and recovery decisions |
| `transaction_audit` | Operational event history |

### Integrity constraints

The database uses primary keys, foreign keys, unique constraints and check constraints.

The primary key on `held_locks.resource_id` ensures that one resource has at most one current owner.

The unique constraint on transaction and resource combinations prevents duplicate waiting requests.

The transaction status enum restricts lifecycle values to valid states.

A trigger validates the transaction state before inserting a waiting request.

### Wait-for graph representation

The `wait_for_edges` view joins `lock_waits` and `held_locks`.

The resulting records represent:

- Waiting transaction
- Blocking transaction
- Requested resource
- Request timestamp

The view is the relational representation of the wait-for graph.

### Deadlock detection

`detect_deadlocks()` uses a recursive common table expression.

The recursive query:

1. Starts from existing wait-for edges.
2. Builds transaction paths.
3. Follows subsequent dependencies.
4. Identifies paths returning to their starting transaction.
5. Returns detected cycles.
6. Selects a youngest transaction as the default victim.

The implementation targets single-instance resources.

### Resource-ordering prevention

`request_resource_ordered()` compares the requested resource order with the maximum order of resources already held by the transaction.

A lower-order request is rejected.

This enforces the global resource acquisition rule.

### Recovery procedure

`recover_deadlocks()` performs the following operations:

1. Executes deadlock detection.
2. Selects a victim.
3. Deletes the victim's outstanding requests.
4. Marks the victim ABORTED.
5. Increments the rollback count.
6. Releases its held resources.
7. Grants available resources to eligible waiting transactions.
8. Records the recovery event.
9. Repeats until no deadlock remains.

### Transaction management

The database provides:

- `request_resource()`
- `request_resource_ordered()`
- `detect_deadlocks()`
- `release_transaction_resources()`
- `commit_transaction()`
- `abort_transaction()`
- `recover_deadlocks()`

Functions return values or calculate information.

Procedures execute transaction-management workflows.

### Reporting

The reporting views provide:

- Transaction resource summaries
- Resource contention information
- Commit eligibility

The audit table records resource acquisition, waiting, grant, commit, abort and recovery events.

### Transactional consistency

Resource ownership and transaction state changes must be performed atomically.

The SQL workflow uses database transactions, row locking and `SKIP LOCKED` for waiter selection.

The sample script also demonstrates an explicit transaction boundary.

For production deployment, concurrent recovery workers should follow a consistent locking order and use an appropriate isolation strategy to avoid introducing new contention or recovery races.

### Execution

Requirements:

- PostgreSQL 15 or later
- Permission to create a schema, functions, procedures, tables and triggers

Execute:

    psql -U postgres -d your_database -f deadlock_management.sql

The script creates the `deadlock_lab` schema, builds the database objects, inserts demonstration records, creates a circular wait and executes recovery.

The sample is intended for an isolated learning database. It should not be executed against an existing production schema without reviewing its object definitions and deployment requirements.

---

# 15. Realistic Enterprise Scenario

Consider a financial application processing account transfers and ledger updates.

Two services operate concurrently.

**Transaction T1: Payment Processing**

1. Acquires ACCOUNT.
2. Updates the account balance.
3. Requests LEDGER.

**Transaction T2: Reporting**

1. Acquires LEDGER.
2. Reads ledger entries.
3. Requests ACCOUNT.

The resulting dependencies are:

    T1 holds ACCOUNT
    T2 holds LEDGER

    T1 waits for LEDGER
    T2 waits for ACCOUNT

    T1 -> T2 -> T1

### Detection response

The monitoring service constructs a wait-for graph and identifies the cycle.

### Prevention response

A common acquisition order is established:

    ACCOUNT -> LEDGER -> AUDIT_LOG

Both services must follow this order.

### Recovery response

If the deadlock occurs under detection-based management:

1. The recovery manager selects a victim.
2. The victim is aborted.
3. Its locks are released.
4. The surviving transaction obtains the required resource.
5. The surviving transaction completes.
6. The aborted transaction may restart.

### Business considerations

A financial system must ensure that rollback reverses all uncommitted effects.

Database rollback alone may not reverse external actions such as payment gateway requests, email delivery or external service calls.

Those operations require separate consistency mechanisms, such as idempotency keys, transactional outbox processing and compensating actions.

---

# 16. Failure Modes and Operational Controls

| Failure mode | Consequence | Control |
|---|---|---|
| Incorrect resource ordering | Circular wait remains possible | Centralized acquisition policy |
| Delayed detection | Longer transaction blocking | Detection intervals and lock monitoring |
| Incorrect victim selection | Excessive rollback cost | Cost-aware recovery |
| Repeated victim selection | Starvation | Rollback tracking and priority adjustment |
| Incomplete rollback | Inconsistent business state | Atomic transaction boundaries |
| Stale wait records | Incorrect dependency graph | Lifecycle validation and cleanup |
| Duplicate ownership | Resource integrity violation | Unique resource ownership constraint |
| Recovery race | Conflicting lock transitions | Consistent row-locking order |
| Unhandled asynchronous rejection | Unhandled Promise failures | Explicit Promise rejection handling |
| Excessively deep graph | Recursive stack exhaustion | Iterative graph traversal |
| Resource leakage | Reduced concurrency | Guaranteed cleanup and ownership auditing |

## 17. Security Considerations

Deadlock management is also a resource-governance concern.

Important controls include:

- Restricting who can acquire and release privileged resources.
- Validating transaction identity.
- Preventing unauthorized resource release.
- Limiting lock acquisition duration.
- Monitoring repeated transaction aborts.
- Protecting audit records against unauthorized modification.
- Restricting database procedure execution privileges.
- Applying transaction timeouts.
- Preventing resource-exhaustion attacks.
- Monitoring unusually large waiting queues.

Database users should receive only the privileges necessary to execute their assigned transaction operations.

Application-level transaction identifiers must not be treated as authentication credentials.

Audit information should avoid storing passwords, access tokens, confidential payment details or other unnecessary sensitive information.

## 18. Performance and Scalability

Deadlock management introduces additional processing overhead.

Its impact depends on graph size, resource contention, detection frequency and recovery cost.

| Component | Main performance consideration |
|---|---|
| Resource lookup | Efficient indexing |
| Wait queue | FIFO scheduling |
| Graph construction | Number of active waiting transactions |
| Cycle detection | O(V + E) for DFS |
| Victim selection | Candidate evaluation cost |
| Rollback | Amount of work requiring reversal |
| Audit | Storage and indexing overhead |
| Database recovery | Lock contention and transaction isolation |

### Monitoring metrics

An operational deadlock management service should track:

- Deadlocks detected per minute.
- Average deadlock resolution time.
- Number of transactions aborted.
- Average rollback duration.
- Resource utilization.
- Average waiting time.
- Maximum waiting queue length.
- Repeated transaction aborts.
- Resource acquisition failures.
- Percentage of transactions completing successfully.

These measurements help distinguish genuine deadlocks from ordinary lock contention and excessive transaction duration.

## 19. Implementation Comparison

| Capability | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Resource ownership | Yes | Yes | Yes | Yes | Yes |
| Waiting queues | Deque | Promise queue | Vector queue | Deque | Relational table |
| Wait-for graph | Yes | Yes | Yes | Yes | View |
| DFS detection | Yes | Yes | Yes | Yes | Recursive CTE |
| Resource ordering | Yes | Yes | Yes | Yes | Yes |
| Wait-die | No | No | No | Yes | Defined policy type |
| Wound-wait | No | No | No | Defined policy type | Defined policy type |
| Victim selection | Youngest | Youngest | Youngest | Configurable | Configurable |
| Recovery | Yes | Yes | Yes | Yes | Yes |
| Audit | Event list | EventEmitter | Console events | Audit records | Audit table |
| Automated checks | Assertions | Demonstrations | Scenario validation | Scenario validation | SQL validation queries |

## 20. Technical Limitations

The implementations intentionally use a simplified resource allocation model.

The following limitations should be considered before adapting the code to production systems:

1. Resources have one instance each.
2. The wait-for graph represents direct blocking dependencies.
3. The examples do not implement distributed deadlock detection.
4. The simulations do not model network partitions or failed machines.
5. Full transaction abort is used rather than checkpoint-based partial rollback.
6. Resource ordering assumes that all participating components follow the same ordering policy.
7. The JavaScript implementation demonstrates asynchronous request coordination within one process.
8. The PostgreSQL recovery workflow is an educational implementation, not a replacement for PostgreSQL's native lock manager.
9. The database procedures do not implement a complete multi-worker recovery protocol.
10. The implementations do not guarantee fairness under every possible scheduling pattern.

For distributed deadlocks, local wait-for graphs may be insufficient. A transaction may wait for a resource managed by another service or database instance. Distributed detection requires information exchange and coordination across resource managers.

Production recovery must also account for idempotency, retries, transaction boundaries, external side effects and consistency guarantees.

---

# 21. Core Terminology

| Term | Definition |
|---|---|
| Deadlock | Circular resource dependency preventing progress |
| Transaction | A logical unit of work |
| Resource | An object required for execution |
| Mutual exclusion | Exclusive access to a resource |
| Hold and wait | Retaining resources while requesting others |
| Circular wait | Closed chain of transaction dependencies |
| Resource allocation graph | Graph of transaction-resource relationships |
| Wait-for graph | Graph of transaction blocking dependencies |
| Safe state | State with a possible transaction completion sequence |
| Unsafe state | State in which safe completion is not guaranteed |
| Deadlock prevention | Removing at least one necessary deadlock condition |
| Deadlock avoidance | Rejecting requests that could produce an unsafe state |
| Deadlock detection | Identifying an existing deadlock |
| Deadlock recovery | Breaking a detected deadlock |
| Victim | Transaction selected for termination |
| Rollback | Reversal of uncommitted transaction operations |
| Wait-die | Older transactions wait; younger requesters abort |
| Wound-wait | Older requesters abort younger holders |
| Resource ordering | Acquiring resources according to a consistent global order |
| Starvation | Repeated inability of a transaction to complete |

## 22. Learning Outcomes

The five implementations demonstrate how the same deadlock-management problem can be addressed through different engineering models:

- Python emphasizes simulation, graph analysis and validation.
- JavaScript emphasizes asynchronous resource coordination and event-driven monitoring.
- C++17 emphasizes deterministic resource management and STL-based graph processing.
- Java 17 emphasizes enterprise domain modeling, policy objects and explicit transaction states.
- PostgreSQL emphasizes relational integrity, recursive graph analysis, transaction procedures and audit reporting.

The central distinction remains:

**Prevention controls how resources are requested. Detection identifies circular dependencies. Recovery breaks those dependencies and restores transaction progress.**
