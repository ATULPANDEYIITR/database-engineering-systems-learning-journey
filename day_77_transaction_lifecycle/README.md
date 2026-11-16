# Transaction Lifecycle: Transaction States, Commit and Rollback

## 1. Introduction

A database transaction is a logical unit of work containing one or more operations that must be processed according to defined consistency and reliability rules.

The transaction lifecycle describes how a transaction begins, executes operations, reaches a decision, and either commits its changes or rolls them back.

A banking transfer provides a practical example. Transferring ₹1,500 from Alice's account to Bob's account requires two related operations:

- Deduct ₹1,500 from Alice's account.
- Add ₹1,500 to Bob's account.

Both operations must succeed together. If the deduction succeeds but the deposit fails, the database must not retain an incomplete transfer.

The transaction lifecycle provides the mechanisms needed to control such operations.

## 2. Transaction Fundamentals

A transaction is a controlled sequence of database operations.

Its primary characteristics are represented by ACID:

| Property | Meaning | Practical implication |
|---|---|---|
| Atomicity | All operations succeed or none do | Both sides of a transfer are processed together |
| Consistency | Database constraints remain valid | An account cannot acquire a negative balance |
| Isolation | Concurrent transactions do not produce unacceptable interference | Simultaneous transfers must not cause lost updates |
| Durability | Committed changes survive failures | A successful transfer remains recorded after a restart |

ACID describes transaction guarantees. Transaction states describe the transaction's progress through its lifecycle.

These are related concepts, but they are not interchangeable.

## 3. Transaction Lifecycle and States

The implementations use an explicit state machine.

### State definitions

| State | Description | Permitted behavior |
|---|---|---|
| NEW | Transaction has been created | Initialization |
| ACTIVE | Transaction is executing operations | Read, write, savepoint, commit or rollback |
| COMMITTING | Commit validation is in progress | Validate and publish changes |
| COMMITTED | Transaction completed successfully | Read results; no further modifications |
| ROLLING_BACK | Uncommitted changes are being discarded | Restore or discard staged changes |
| ROLLED_BACK | Transaction has been cancelled | No further modifications |
| FAILED | Transaction encountered a failure | Recovery or rollback |

The lifecycle can be represented as:

NEW → ACTIVE → COMMITTING → COMMITTED

An alternative path is:

NEW → ACTIVE → ROLLING_BACK → ROLLED_BACK

A transaction can also fail during execution or commit:

ACTIVE → FAILED

COMMITTING → FAILED

A failed transaction must be recovered or rolled back. It must not be treated as successfully committed.

### Valid state transitions

| Current state | Allowed next state |
|---|---|
| NEW | ACTIVE |
| ACTIVE | COMMITTING, ROLLING_BACK, FAILED |
| COMMITTING | COMMITTED, FAILED |
| ROLLING_BACK | ROLLED_BACK, FAILED |
| FAILED | ROLLING_BACK |
| COMMITTED | None |
| ROLLED_BACK | None |

The state machine prevents operations such as committing an already committed transaction or modifying a rolled-back transaction.

The Python, JavaScript, C++17, and Java 17 implementations enforce these transitions through explicit validation.

PostgreSQL enforces business transaction state changes using a trigger.

## 4. Beginning a Transaction

A transaction begins when the system establishes a boundary around a group of operations.

In SQL:

`BEGIN;`

For example:

`BEGIN;`

`UPDATE accounts SET balance = balance - 1500 WHERE account_number = 'ACC-1001';`

`UPDATE accounts SET balance = balance + 1500 WHERE account_number = 'ACC-1002';`

`COMMIT;`

The database executes the operations within one transaction boundary.

If an operation fails, the application can issue `ROLLBACK`.

A transaction may also be started with a selected isolation level:

- READ COMMITTED
- REPEATABLE READ
- SERIALIZABLE

Isolation level selection determines how concurrent transactions interact with database reads and writes.

## 5. Transaction Execution and Staged Changes

During the ACTIVE state, the transaction executes its operations.

The implementations distinguish between staged changes and committed database state.

For example, consider the initial account balances:

| Account | Owner | Initial balance |
|---|---|---:|
| ACC-001 | Alice | ₹10,000 |
| ACC-002 | Bob | ₹5,000 |
| ACC-003 | Charlie | ₹2,500 |

Alice transfers ₹1,500 to Bob.

The proposed transaction contains:

| Operation | Account | Amount |
|---|---|---:|
| Debit | Alice | -₹1,500 |
| Credit | Bob | +₹1,500 |

Before commit, these operations are staged in the transaction's working state.

The committed database remains unchanged until the transaction successfully completes.

This distinction is important:

- Proposed changes describe what the transaction intends to perform.
- Staged changes represent operations prepared within the transaction.
- Committed state represents durable database changes.
- Rolled-back changes are discarded and do not become durable.

The in-memory implementations use private snapshots to model staged changes. PostgreSQL uses actual database transaction boundaries.

## 6. Commit Operation

Commit finalizes a transaction.

In SQL:

`COMMIT;`

A successful commit establishes that the database has accepted the transaction's modifications.

The commit process involves:

1. Confirming that the transaction is active.
2. Validating the operations.
3. Checking database constraints.
4. Resolving concurrency conflicts.
5. Publishing the changes.
6. Marking the transaction as committed.

After a successful commit, the transaction enters the COMMITTED state.

### Example

Initial balances:

| Account | Balance |
|---|---:|
| Alice | ₹10,000 |
| Bob | ₹5,000 |

Transfer amount: ₹1,500.

After commit:

| Account | Balance |
|---|---:|
| Alice | ₹8,500 |
| Bob | ₹6,500 |

The total balance remains ₹15,000.

A committed transaction cannot be reversed by issuing ROLLBACK afterward. Correcting a committed business transaction requires a separate compensating transaction.

## 7. Rollback Operation

Rollback cancels uncommitted changes.

In SQL:

`ROLLBACK;`

Consider a withdrawal transaction:

- Initial balance: ₹5,000.
- Requested withdrawal: ₹1,000.
- Staged balance: ₹4,000.
- Business validation fails.

The transaction is rolled back.

The resulting committed balance remains ₹5,000.

Rollback is useful when:

- A business rule is violated.
- An account has insufficient funds.
- An operation references an invalid account.
- A database constraint rejects an update.
- A concurrency conflict prevents safe publication.
- An application encounters an unexpected exception.

### Full rollback versus partial rollback

| Mechanism | Effect |
|---|---|
| ROLLBACK | Discards all changes made within the current transaction |
| ROLLBACK TO SAVEPOINT | Discards changes made after the specified savepoint |
| Compensating transaction | Creates a new transaction to counteract a previously committed business operation |

These mechanisms solve different problems.

A savepoint does not commit the transaction. A compensating transaction does not erase the historical record of an earlier commit.

## 8. Savepoints and Partial Rollback

A savepoint creates an intermediate recovery point inside an active database transaction.

SQL example:

`BEGIN;`

`UPDATE accounts SET balance = balance + 250 WHERE account_number = 'ACC-001';`

`SAVEPOINT before_second_operation;`

`UPDATE accounts SET balance = balance - 500 WHERE account_number = 'ACC-002';`

`ROLLBACK TO SAVEPOINT before_second_operation;`

`COMMIT;`

The first update remains part of the transaction. The second update is discarded.

Savepoints are useful in workflows containing multiple optional operations.

### Savepoint rules

- A savepoint exists only within its transaction.
- A transaction can create multiple savepoints.
- Rolling back to a savepoint preserves operations performed before it.
- Operations after the savepoint are undone.
- Releasing a savepoint removes its recovery marker.
- Committing or fully rolling back the transaction ends the savepoint lifecycle.

The Python, JavaScript, C++17, and Java 17 programs implement snapshot-based savepoints.

The PostgreSQL implementation combines native SQL savepoints with staged operation records.

## 9. Transaction Isolation

Isolation controls how concurrent transactions observe and modify data.

Consider two transactions attempting to withdraw money from the same account.

Initial balance: ₹5,000.

Transaction A requests ₹4,000.

Transaction B requests ₹3,000.

Both transactions must not independently assume that the original balance is still available and collectively withdraw ₹7,000.

### Isolation levels

| Isolation level | Main behavior | Important limitation |
|---|---|---|
| READ UNCOMMITTED | Allows the weakest isolation semantics | PostgreSQL treats it as READ COMMITTED |
| READ COMMITTED | Each statement sees committed data as of its snapshot | Repeated reads may return different values |
| REPEATABLE READ | Maintains a consistent transaction snapshot | Serialization anomalies may still be possible |
| SERIALIZABLE | Enforces serializable transaction outcomes | Transactions may be aborted and require retries |

Important concurrency anomalies include:

**Dirty read:** A transaction reads changes that another transaction has not committed.

**Non-repeatable read:** A transaction reads the same record twice and observes different committed values.

**Phantom read:** Repeating a query returns a different set of matching records because another transaction changed qualifying rows.

**Lost update:** One transaction overwrites another transaction's update without correctly incorporating it.

**Write skew:** Concurrent transactions make individually valid updates that collectively violate a business invariant.

PostgreSQL's MVCC architecture provides snapshot-based concurrency control.

The SQL implementation demonstrates three commonly used isolation levels.

## 10. Optimistic Concurrency Control

Optimistic concurrency control allows transactions to work using snapshots and checks whether relevant records changed before commit.

Each account has a version number.

Example:

| Transaction | Account version observed | Intended action |
|---|---:|---|
| TX-001 | 0 | Deposit ₹100 |
| TX-002 | 0 | Deposit ₹200 |

TX-001 commits first.

The account version becomes 1.

TX-002 attempts to commit using its original version of 0.

The version comparison detects a conflict.

TX-002 must not overwrite TX-001's update.

The in-memory implementations use version checking to detect stale snapshots.

PostgreSQL uses row-level locking and transaction isolation to protect its actual database updates.

Optimistic concurrency is particularly useful when conflicts are relatively uncommon.

It reduces the need to hold long-running locks while application operations are being prepared.

## 11. Python Implementation

The Python program models a transactional banking system.

### Main components

| Component | Responsibility |
|---|---|
| Account | Stores account identity, owner, balance and version |
| Transaction | Maintains state, operations, history and savepoints |
| BankDatabase | Maintains committed account records |
| TransactionManager | Coordinates transaction operations |
| TransactionEvent | Records state transitions |
| TransactionState | Defines permitted transaction states |

### Important mechanisms

**Dataclasses:** Represent account and transaction event records.

**Enums:** Define transaction states.

**Dictionaries:** Store account snapshots and savepoints.

**Lists:** Maintain operation sequences and state history.

**Deep copying:** Separates staged data from committed database data.

**RLock:** Protects shared in-memory database operations.

**Version checking:** Detects concurrent modifications.

**Exceptions:** Represent validation failures, insufficient funds and concurrency conflicts.

### Executed scenarios

- Successful transfer and deposit.
- Full rollback.
- Savepoint creation and restoration.
- Insufficient-funds rejection.
- Concurrent modification detection.

The implementation is educational. It simulates transactional behavior using in-memory data rather than providing the crash recovery, persistent storage, and isolation guarantees of a real database.

## 12. JavaScript Implementation

The JavaScript program uses an event-driven transaction architecture.

### Main components

| Component | Responsibility |
|---|---|
| Transaction | Manages staged operations and transaction state |
| AccountStore | Stores committed account records |
| TransactionService | Coordinates transaction execution |
| EventEmitter | Publishes state-change events |
| State | Defines transaction lifecycle states |

### Event-driven behavior

The transaction emits state-change events whenever it moves between states.

Listeners receive information about:

- Previous state.
- Current state.
- Transaction identifier.
- Description.
- Timestamp.

This supports monitoring and audit integrations.

### Asynchronous processing

The AccountStore uses Promises to serialize commit operations.

This prevents simultaneous commit publication from modifying the same in-memory state without coordination.

The implementation also uses:

- Maps for account storage.
- Sets or map-based structures for managing unique transaction identifiers and savepoint-related state.
- Immutable event objects.
- Integer cents for monetary calculations.
- Node.js filesystem APIs for audit export.
- Explicit error handling.

The use of integer cents avoids common floating-point representation problems in monetary calculations.

The commit queue is an in-process coordination mechanism, not a distributed transaction coordinator.

## 13. C++17 Implementation

The C++17 program emphasizes explicit state management and controlled resource access.

### Main components

| Component | Responsibility |
|---|---|
| Account | Represents an account |
| Transaction | Holds staged changes and transaction history |
| Database | Coordinates committed state |
| Savepoint | Stores a recovery snapshot |
| Operation | Represents an individual transaction operation |
| TransactionState | Defines lifecycle states |

### Engineering decisions

**STL map:** Provides ordered account storage and predictable lookup behavior.

**Vectors:** Maintain operation and event sequences.

**Mutex:** Protects shared database state.

**RAII:** Uses `std::lock_guard` to release locks automatically when scopes end.

**Exceptions:** Propagate validation and concurrency failures.

**Copy-and-swap:** Prepares a replacement account map and publishes it after validation.

**Integer monetary values:** Store currency in cents rather than binary floating-point values.

The program demonstrates how transactional state can be managed without external libraries.

The implementation uses an in-memory database. Its mutex provides process-level synchronization, not multi-process database isolation or crash durability.

## 14. Java 17 Implementation

The Java implementation uses an enterprise-oriented domain model.

### Main components

| Component | Responsibility |
|---|---|
| Account | Account domain entity |
| Transaction | Transaction execution context |
| AccountRepository | Committed account storage |
| TransactionService | Application-level transaction orchestration |
| TransactionEvent | Immutable lifecycle event |
| TransactionResult | Execution result |
| TransactionListener | Event notification interface |
| Savepoint | Intermediate recovery snapshot |

### Java 17 features

**Records:** Represent immutable events, operations, savepoints and transaction results.

**Enums:** Define transaction states and operation types.

**Interfaces:** Separate event notification behavior from transaction execution.

**Streams:** Support account reporting and collection processing.

**Collections:** Maintain transaction snapshots and operation histories.

**BigDecimal:** Provides precise decimal monetary calculations.

**ReentrantLock:** Coordinates access to shared account state.

**Custom exceptions:** Distinguish validation, insufficient funds, concurrency and state-transition errors.

### Enterprise workflow

The TransactionService coordinates business operations.

The AccountRepository controls committed state.

The Transaction entity maintains the transaction lifecycle.

This separation prevents business orchestration from being mixed with repository-level persistence responsibilities.

The implementation also provides immutable event records, explicit state transitions and a concurrency-conflict scenario.

## 15. PostgreSQL Implementation

The PostgreSQL script models the transaction lifecycle using relational database structures.

### Database entities

| Table | Purpose |
|---|---|
| accounts | Stores account details and committed balances |
| transactions | Stores transaction metadata and lifecycle state |
| transaction_operations | Stores individual staged operations |
| transaction_audit | Records lifecycle events |
| transaction_savepoints | Stores savepoint metadata |

### Database mechanisms

**Schemas:** Isolate transaction-related database objects.

**Primary keys:** Provide unique record identification.

**Foreign keys:** Maintain relationships between accounts, transactions and operations.

**Unique constraints:** Prevent duplicate account numbers, transaction references and operation sequences.

**Check constraints:** Reject invalid monetary amounts and invalid operation configurations.

**Indexes:** Support account lookups, transaction retrieval and audit-history queries.

**Triggers:** Validate state transitions, maintain account versions and record audit events.

**Functions:** Create business transactions and stage operations.

**Procedures:** Coordinate business transaction commits and rollbacks within caller-managed SQL transactions.

**Views:** Present transaction, account and audit reports.

**CTEs:** Calculate account activity using operation records.

### Transaction boundaries

The SQL implementation distinguishes between two concepts:

1. The PostgreSQL database transaction.
2. The business transaction record stored in the transactions table.

A business transaction record tracks workflow progress.

A PostgreSQL transaction provides actual database atomicity and durability.

For example, updating a business transaction record to COMMITTED is not independently equivalent to issuing SQL COMMIT.

The caller must commit the surrounding PostgreSQL transaction after the business commit procedure completes successfully.

This distinction is essential when implementing database-backed transaction processing.

## 16. Transaction Failure and Recovery

Transaction failures can occur at different lifecycle stages.

| Failure | Example | Appropriate response |
|---|---|---|
| Initialization failure | Missing account details | Reject transaction creation |
| Validation failure | Negative transfer amount | Reject the operation |
| Business failure | Insufficient balance | Roll back the transaction |
| Constraint failure | Invalid database record | Roll back the database transaction |
| Concurrency conflict | Stale account version | Retry or reject according to policy |
| Commit failure | Database rejects publication | Roll back the transaction |
| Application failure | Unexpected exception | Discard uncommitted work |
| Connection failure | Client loses database connection | Determine commit outcome before retrying |

A particularly important production issue is an uncertain commit outcome.

A client may lose its connection after the database commits but before the client receives confirmation.

Blindly retrying a payment could result in duplicate processing.

Production payment systems should therefore use:

- Unique idempotency keys.
- Durable transaction references.
- Duplicate-request detection.
- Transaction-status reconciliation.
- Controlled retry policies.
- Audit records.

## 17. Transaction Logging and Auditing

Transaction auditing records the sequence of important lifecycle events.

A useful audit record includes:

| Field | Purpose |
|---|---|
| Transaction ID | Identifies the transaction |
| Previous state | Records the state before a transition |
| Current state | Records the resulting state |
| Event type | Identifies the action |
| Timestamp | Establishes event chronology |
| Actor | Identifies the initiating principal |
| Description | Explains the event |

An audit history helps investigate failed operations, identify concurrency problems and reconstruct transaction processing decisions.

A production audit design should restrict modification and deletion privileges and should distinguish technical logs from legally or operationally required financial records.

Sensitive authentication data should never be written to transaction logs.

## 18. Transaction Processing and Security

Transaction processing requires controls at both application and database levels.

Important controls include:

- Validate account ownership before processing.
- Enforce authorization independently of transaction state.
- Reject negative and zero-value operations.
- Prevent unauthorized account modifications.
- Use parameterized SQL queries.
- Restrict direct table modification privileges.
- Protect transaction identifiers and account information.
- Enforce database constraints.
- Use appropriate isolation levels.
- Monitor long-running transactions.
- Maintain auditable state transitions.
- Apply idempotency controls to external payment requests.

Database constraints provide a final integrity boundary, but they do not replace application authorization.

Similarly, a successful transaction-state transition does not prove that the initiating user was authorized to perform the operation.

## 19. Performance Considerations

Transaction design affects throughput, latency and resource utilization.

| Mechanism | Performance consideration |
|---|---|
| Long-running transactions | Retain locks or snapshots for longer |
| Frequent commits | Increase transaction-management overhead |
| Excessive savepoints | Increase transaction bookkeeping |
| Broad row locking | Increase contention |
| SERIALIZABLE isolation | May require transaction retries |
| Large audit tables | Increase storage and index-maintenance costs |
| Full snapshot copying | Increases memory consumption |
| Indexes | Improve retrieval but add write overhead |

The Python, JavaScript, C++17 and Java 17 examples copy account snapshots to make staged changes easy to understand.

For large production workloads, copying an entire database snapshot per transaction is inefficient.

A real transactional storage engine uses more sophisticated mechanisms such as MVCC, write sets, lock management, write-ahead logging and recovery procedures.

## 20. Important Distinctions

| Concept | Responsibility |
|---|---|
| Transaction | Defines a logical unit of work |
| Transaction state | Describes execution progress |
| ACID | Defines transaction reliability properties |
| BEGIN | Starts a database transaction |
| COMMIT | Makes transaction changes durable |
| ROLLBACK | Discards uncommitted changes |
| SAVEPOINT | Creates an intermediate recovery point |
| Isolation | Controls concurrent transaction interactions |
| Locking | Coordinates access to shared records |
| MVCC | Maintains multiple versions of records |
| Optimistic concurrency | Detects conflicts during validation |
| Audit log | Records transaction events |
| Compensating transaction | Corrects the business effect of a previously committed operation |

These mechanisms work together but solve different problems.

## 21. Implementation Limitations

The five implementations are designed to demonstrate the same transaction lifecycle from different engineering perspectives.

Their guarantees are not identical.

| Implementation | Persistence | Concurrency mechanism | Main limitation |
|---|---|---|---|
| Python | In-memory | RLock and version checking | No crash durability |
| JavaScript | In-memory | Promise commit queue and version checking | Coordination is process-local |
| C++17 | In-memory | Mutex and version checking | No persistent storage |
| Java 17 | In-memory | ReentrantLock and version checking | No database recovery |
| PostgreSQL | Persistent database | MVCC, row locking and isolation | Requires correct caller transaction management |

The PostgreSQL implementation provides real database transaction semantics.

The in-memory implementations simulate those semantics to make state transitions, staged changes, commit behavior and rollback decisions observable.

The examples do not implement distributed atomic commits across independent databases or external services.

For external integrations, an outbox pattern or an appropriately designed saga workflow is required.

## 22. Practical Transaction Workflow

A typical database-backed transaction follows this sequence:

1. Authenticate the initiating user.
2. Authorize the requested operation.
3. Begin a database transaction.
4. Read the relevant records.
5. Validate business conditions.
6. Stage the required changes.
7. Check integrity and concurrency conditions.
8. Commit if every required operation succeeds.
9. Roll back if an operation fails.
10. Record and monitor the final transaction outcome.

The central design requirement is that the database must not expose a partially completed operation as a successful transaction.
