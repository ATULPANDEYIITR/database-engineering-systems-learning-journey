# Database Transaction Isolation Levels

## Technical Scope

Database transaction isolation determines how concurrently executing transactions observe database changes and how the database handles conflicting operations.

Isolation is one of the four properties of ACID transactions:

| Property | Meaning |
|---|---|
| Atomicity | A transaction completes entirely or is rolled back |
| Consistency | Transactions preserve database integrity rules |
| Isolation | Concurrent transactions observe data according to defined visibility rules |
| Durability | Committed changes survive failures according to database guarantees |

The four standard isolation levels are:

1. Read Uncommitted
2. Read Committed
3. Repeatable Read
4. Serializable

Each level places different restrictions on concurrent data access. Stronger isolation generally reduces concurrency anomalies but can increase transaction conflicts, blocking, retries, and processing costs.

The implementations cover transaction execution, snapshot management, version tracking, concurrent updates, conflict detection, and database-level integrity.

## 1. Transaction Fundamentals

A transaction is a logical unit of database work.

Consider a bank transfer:

- Account A contains 5,000.
- Account B contains 3,000.
- The transfer amount is 1,000.

The transaction must debit Account A and credit Account B.

The required operations are:

1. Read the source balance.
2. Read the destination balance.
3. Validate available funds.
4. Debit the source.
5. Credit the destination.
6. Commit both changes.

The intended result is:

| Account | Initial balance | Transfer | Final balance |
|---|---:|---:|---:|
| Account A | 5,000 | -1,000 | 4,000 |
| Account B | 3,000 | +1,000 | 4,000 |
| Total | 8,000 | 0 | 8,000 |

Both account modifications must belong to the same transaction.

If the second operation fails, the first modification must not remain committed independently.

### Transaction lifecycle

    BEGIN
      |
      v
    READ
      |
      v
    VALIDATE
      |
      v
    WRITE
      |
      v
    COMMIT
      |
      v
    DURABLE RESULT

    Any failure before commit
      |
      v
    ROLLBACK

A transaction normally moves through active, committed, or aborted states.

A committed transaction cannot simply be rolled back through an ordinary transaction rollback command.

## 2. Concurrency and Transaction Anomalies

Concurrency allows multiple database transactions to execute during overlapping periods.

It improves resource utilization and application throughput, but unrestricted concurrent access can produce inconsistent observations.

### 2.1 Dirty Read

A dirty read occurs when one transaction reads a value written by another transaction that has not committed.

Example:

| Step | Transaction A | Transaction B |
|---|---|---|
| 1 | Begin | |
| 2 | Update balance to 500 | |
| 3 | | Read balance as 500 |
| 4 | Rollback | |
| 5 | | Previously read value was never committed |

Transaction B has observed a value that does not become part of the committed database state.

This can cause incorrect calculations, decisions, and reports.

Dirty reads are possible under implementations that genuinely support Read Uncommitted.

**PostgreSQL distinction:** PostgreSQL does not permit dirty reads. A transaction requesting Read Uncommitted receives Read Committed behavior.

### 2.2 Non-Repeatable Read

A non-repeatable read occurs when a transaction reads the same row twice and obtains different committed values.

Example:

| Step | Transaction A | Transaction B |
|---|---|---|
| 1 | Begin | |
| 2 | Read balance: 1,000 | |
| 3 | | Update balance to 800 |
| 4 | | Commit |
| 5 | Read balance: 800 | |

The first and second reads differ because another transaction committed an update between the two statements.

This behavior is permitted under Read Committed.

### 2.3 Phantom Read

A phantom read occurs when a repeated query using the same search condition returns a different set of rows.

Example:

Transaction A:

- Counts accounts with balances above 5,000.
- Another transaction inserts an account satisfying that condition.
- Transaction A repeats the query.
- The result contains an additional row.

Unlike a non-repeatable read, which concerns an existing row's changing values, a phantom read concerns the result set of a predicate-based query.

The distinction is important when applications calculate totals, determine eligibility, or enforce business limits.

PostgreSQL Repeatable Read prevents phantom reads through its transaction-level snapshot.

### 2.4 Lost Update

A lost update occurs when concurrent transactions calculate changes using the same earlier value and one update overwrites the other.

Example:

Initial balance: 1,000.

- Transaction A reads 1,000.
- Transaction B reads 1,000.
- Transaction A calculates 900.
- Transaction B calculates 800.
- Both attempt to update the balance.

An implementation without suitable concurrency control may lose one transaction's modification.

Databases use row locks, version checks, conflict detection, or other mechanisms to prevent unsafe updates.

### 2.5 Serialization Anomaly

A serialization anomaly occurs when concurrent transactions produce a result that cannot be explained by any valid serial ordering of those transactions.

A serial execution completes one transaction before executing the next.

Serializable isolation attempts to preserve the correctness of this ordering even when transactions execute concurrently.

## 3. Read Uncommitted

Read Uncommitted is the weakest standard isolation level.

It places relatively few restrictions on concurrent reads.

### Characteristics

- Dirty reads may occur in database systems that support them.
- Non-repeatable reads may occur.
- Phantom reads may occur.
- Concurrent modifications require separate write-concurrency controls.
- Applications must tolerate potentially inconsistent observations.

### Suitable situations

Read Uncommitted may be considered for workloads where approximate intermediate information is acceptable and the database genuinely implements this isolation level.

It is generally inappropriate for financial transactions, inventory reservations, payment processing, or other workflows requiring committed data.

### PostgreSQL implementation

PostgreSQL maps Read Uncommitted to Read Committed.

Therefore, the following request:

`SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;`

does not permit reading another transaction's uncommitted changes.

The effective behavior is Read Committed.

This implementation-specific distinction is important when comparing PostgreSQL with other database systems.

## 4. Read Committed

Read Committed ensures that each statement sees committed data.

It is the default isolation level in PostgreSQL.

### Characteristics

- Dirty reads are prevented.
- Non-repeatable reads are possible.
- Phantom reads are possible.
- Each statement receives a new committed snapshot.
- Uncommitted changes from other transactions remain invisible.

### Statement-level snapshots

The central mechanism is statement-level visibility.

Consider:

    Transaction A:
        BEGIN ISOLATION LEVEL READ COMMITTED;

        SELECT balance FROM accounts
        WHERE account_number = 'ACC-1001';

        SELECT balance FROM accounts
        WHERE account_number = 'ACC-1001';

    Transaction B:
        UPDATE accounts
        SET balance = 800
        WHERE account_number = 'ACC-1001';

        COMMIT;

The second statement in Transaction A may observe the new committed balance.

### Practical applications

Read Committed is useful for:

- Standard web applications.
- Individual record retrieval.
- Frequently updated operational data.
- Independent database operations.
- Workloads where each statement should observe recent committed changes.

### Limitation

Multiple statements within a transaction do not necessarily operate on the same database snapshot.

Applications must account for this when business rules depend on consistent observations across several queries.

## 5. Repeatable Read

Repeatable Read provides a stable transaction-level view of committed data.

In PostgreSQL, the snapshot is established when the transaction performs its first snapshot-taking statement.

Subsequent statements retain that snapshot.

### Characteristics

- Dirty reads are prevented.
- Non-repeatable reads are prevented.
- Phantom reads are prevented in PostgreSQL.
- The transaction retains a consistent snapshot.
- Conflicting concurrent updates can cause transaction failure.

### Snapshot mechanism

Suppose Transaction A starts and reads an account balance of 1,000.

Transaction B updates the balance to 700 and commits.

Transaction A continues to observe 1,000 through its existing snapshot.

The current committed database value is 700, but Transaction A retains its earlier view.

This is an important distinction:

**A transaction snapshot does not mean the entire database stops changing.**

Other transactions can commit changes while the current transaction continues reading its existing snapshot.

### Concurrent update behavior

PostgreSQL Repeatable Read prevents certain unsafe concurrent updates.

If a transaction attempts to update a row that another transaction has modified since its snapshot was established, PostgreSQL can raise a serialization failure.

The application must handle that failure.

### Practical applications

- Consistent reporting.
- Multi-query data analysis.
- Account reconciliation.
- Operations requiring stable row visibility.
- Workflows where repeated reads must produce consistent results.

### Limitation

Long-running transactions retain older snapshots.

This can prevent PostgreSQL from removing obsolete row versions during vacuum processing.

Consequently, long transactions can increase storage pressure and reduce database maintenance efficiency.

## 6. Serializable

Serializable is the strongest standard isolation level.

It aims to make concurrent execution equivalent to some valid serial execution order.

### Characteristics

- Dirty reads are prevented.
- Non-repeatable reads are prevented.
- Phantom reads are prevented.
- Serialization anomalies are prevented.
- Concurrent transactions may be aborted.
- Applications must implement transaction retry handling.

### Serializable execution

Consider two transactions that independently inspect a business condition and update different records.

Both transactions may initially observe a valid condition.

Their combined changes could violate a business rule even though each transaction appears correct when considered independently.

Serializable isolation detects unsafe dependency patterns and rejects an execution that cannot be serialized.

### PostgreSQL implementation

PostgreSQL implements Serializable using Serializable Snapshot Isolation (SSI).

SSI uses snapshot-based execution and tracks read/write dependencies to identify dangerous concurrent structures.

It does not simply lock every row read by every serializable transaction.

A serialization failure commonly uses SQLSTATE:

`40001`

Applications should:

1. Detect the serialization error.
2. Roll back the failed transaction.
3. Begin a new transaction.
4. Repeat the complete business operation.
5. Apply a bounded retry policy.

Retrying only the final failed SQL statement is insufficient when earlier decisions were based on a snapshot that is no longer valid.

### Practical applications

- Financial settlement.
- Inventory allocation.
- Reservation systems.
- Concurrent quota enforcement.
- Complex business rules.
- Operations where serial execution equivalence is essential.

### Performance tradeoff

Serializable transactions can experience more retries under high contention.

Transaction duration, predicate complexity, and concurrent write activity affect conflict rates.

## 7. Comparison of Isolation Levels

| Characteristic | Read Uncommitted | Read Committed | Repeatable Read | Serializable |
|---|---|---|---|---|
| Dirty reads | Possible in supporting systems | Prevented | Prevented | Prevented |
| Non-repeatable reads | Possible | Possible | Prevented | Prevented |
| Phantom reads | Possible | Possible | Possible under some implementations | Prevented |
| PostgreSQL dirty reads | Prevented | Prevented | Prevented | Prevented |
| PostgreSQL non-repeatable reads | Prevented | Possible | Prevented | Prevented |
| PostgreSQL phantom reads | Prevented | Possible | Prevented | Prevented |
| Stable transaction snapshot | No | No | Yes | Yes |
| Serialization failures | Implementation-dependent | Not normally for ordinary snapshot conflicts | Possible | Possible |
| Concurrency flexibility | High | High | Moderate | More restrictive |

The table describes the general SQL isolation concepts and PostgreSQL-specific behavior. Actual locking and conflict behavior depends on the database implementation and statement type.

## 8. MVCC and Version Management

Multi-Version Concurrency Control (MVCC) is a database technique that maintains multiple versions of rows.

Instead of requiring every reader to block every writer, the database can provide readers with an appropriate committed row version.

### Main mechanisms

- A transaction reads a version visible to its snapshot.
- An update creates a new row version.
- Readers can continue accessing an older visible version.
- Transaction visibility determines which versions are accessible.
- Obsolete versions are eventually eligible for cleanup.

### Conceptual example

    Initial version:
        Account balance = 1,000

    Transaction A:
        Reads version 1,000

    Transaction B:
        Creates version 800
        Commits

    Transaction A:
        Continues reading version 1,000

    New Transaction C:
        Reads version 800

The different transactions can observe different versions without requiring every reader to block the writer.

PostgreSQL uses tuple visibility information and transaction identifiers to implement MVCC. The in-memory examples in the source files use explicit version counters to demonstrate the underlying concept.

## 9. Python Implementation

**File:** Python transaction-isolation implementation.

The Python implementation provides a versioned in-memory database model.

### Main components

| Component | Responsibility |
|---|---|
| `IsolationLevel` | Defines the four isolation levels |
| `TransactionState` | Tracks transaction lifecycle |
| `Version` | Stores a value and version number |
| `Transaction` | Maintains snapshot and transaction-local state |
| `Database` | Coordinates reads, writes, commits, and rollback |
| `WriteConflictError` | Reports concurrent write conflicts |
| `SerializationError` | Reports failed serializable validation |

### Read behavior

The implementation distinguishes:

- Transaction-local writes.
- Current committed data.
- Transaction-level snapshots.
- Simulated uncommitted writes.

Read Committed obtains the current committed view for each read.

Repeatable Read and Serializable retain their original snapshots.

The Read Uncommitted implementation deliberately demonstrates dirty-read visibility as a generic isolation concept. It does not represent PostgreSQL behavior.

### Commit validation

The commit operation checks whether a row has changed since the transaction originally accessed it.

Serializable transactions receive additional read-dependency validation.

The database then publishes the transaction's writes and changes its state to committed.

### Testing

The script demonstrates:

- Dirty-read behavior in the abstract simulator.
- Non-repeatable reads.
- Repeatable snapshots.
- Concurrent write conflicts.
- Serializable validation.
- Atomic account transfers.
- Rollback behavior.
- Rejection of operations on inactive transactions.

Assertions verify important expected outcomes.

### Implementation limitation

The Python implementation is a teaching simulator, not a complete database engine.

Its simplified Serializable validation does not track all predicate dependencies or provide full Serializable Snapshot Isolation.

Its commit process is also not designed for real multi-threaded database execution.

## 10. JavaScript Implementation

**File:** JavaScript transaction-isolation implementation.

The JavaScript implementation emphasizes asynchronous transaction workflows and event-driven processing.

### Main components

| Component | Responsibility |
|---|---|
| `TransactionalDatabase` | Manages versioned records |
| `Transaction` | Maintains transaction-specific state |
| `TransferService` | Implements atomic account transfers |
| `IsolationLevel` | Defines isolation policies |
| `TransactionState` | Controls valid transaction operations |
| `EventEmitter` | Publishes transaction lifecycle events |
| `SerializationError` | Reports dependency conflicts |

### Event-driven processing

The database publishes events for:

- Transaction creation.
- Record writes.
- Successful commits.
- Rollbacks.

This allows audit or monitoring components to observe transaction activity without being embedded in every business operation.

### Asynchronous commits

The commit method uses asynchronous function semantics.

It performs validation and publication without an intervening asynchronous operation.

This is important because an `await` inserted between validation and publication could allow another operation to interleave.

### Security and validation

The implementation validates:

- Isolation-level values.
- Record existence.
- Numeric values.
- Positive transfer amounts.
- Available balances.
- Transaction state.

Transaction identifiers are generated using Node.js cryptographic UUID functionality.

### Implementation limitation

JavaScript event-loop execution does not provide a database transaction manager.

The example's in-memory validation and publication are atomic only within its simplified execution model.

A real database must provide cross-process concurrency control, durable storage, locking or equivalent conflict management, and recovery.

The Serializable implementation is illustrative and does not implement full predicate dependency tracking.

## 11. C++17 Implementation

**File:** C++ transaction-isolation engine.

The C++ implementation emphasizes explicit domain structures and conflict analysis.

### Main components

| Component | Responsibility |
|---|---|
| `Database` | Stores versioned records |
| `Transaction` | Stores snapshots and pending changes |
| `Operation` | Represents a scheduled transaction operation |
| `SerializationGraph` | Analyzes transaction conflicts |
| `Conflict` | Represents a directed dependency |
| `WriteConflict` | Represents a concurrent write failure |
| `SerializationFailure` | Represents failed validation |

### Conflict serializability

The precedence graph represents transaction dependencies.

A directed edge:

`T1 -> T2`

means that an operation in T1 precedes and conflicts with an operation in T2.

Two operations conflict when:

- They belong to different transactions.
- They access the same data item.
- At least one operation is a write.
- Their order can affect the result.

Read-read pairs do not create conflicts.

### Graph analysis

The implementation uses Kahn's topological sorting algorithm.

Its main complexity is:

- Graph construction: proportional to the number of examined operation pairs.
- Topological sorting: O(V + E).
- V: number of transactions.
- E: number of unique dependency edges.

If the graph contains a cycle, the schedule is not conflict-serializable.

An acyclic graph has at least one valid topological transaction order.

### Important distinction

Conflict serializability is a schedule-analysis technique.

It is not a complete implementation of database Serializable isolation.

The example's optimistic validation does not implement full predicate locking, MVCC visibility rules, or PostgreSQL SSI.

## 12. Java 17 Enterprise Implementation

**File:** Java enterprise transaction-isolation implementation.

The Java implementation emphasizes enterprise domain modeling, explicit policies, transaction services, and audit records.

### Main components

| Component | Responsibility |
|---|---|
| `Account` | Immutable account representation |
| `Transaction` | Holds transaction state and snapshots |
| `AccountRepository` | Provides account persistence behavior |
| `IsolationPolicy` | Defines read-view behavior |
| `IsolationPolicyRegistry` | Selects the appropriate isolation policy |
| `TransactionManager` | Coordinates transaction operations |
| `TransferService` | Enforces account-transfer business rules |
| `AuditService` | Records transaction events |

### Java 17 features

The implementation uses:

- Records for immutable domain data.
- Enums for controlled state values.
- Interfaces for policy abstraction.
- Collections for transaction snapshots.
- Generics for type-safe data structures.
- Streams for audit reporting.
- `BigDecimal` for financial arithmetic.
- Custom exceptions for domain failures.
- Synchronized methods for simplified in-memory concurrency control.

### Policy separation

Isolation behavior is separated from transaction management.

This allows the transaction manager to obtain a read view without embedding all isolation rules in the business service.

The account transfer service focuses on business validation and transaction orchestration.

### Enterprise audit

Audit events record transaction lifecycle changes.

A typical sequence is:

    BEGIN
      |
      v
    WRITE:ACCOUNT_A
      |
      v
    WRITE:ACCOUNT_B
      |
      v
    COMMIT

A failed transaction produces an abort event.

### Implementation limitation

The Java implementation is an in-memory domain model.

Its synchronized repository operations are not equivalent to a database MVCC engine.

Its Serializable validation is simplified and does not provide complete predicate dependency detection.

A production implementation should delegate actual isolation enforcement to the database and use bounded retries for retryable transaction failures.

## 13. PostgreSQL Implementation

**File:** PostgreSQL transaction-isolation laboratory.

The SQL implementation uses PostgreSQL-specific features to demonstrate real database behavior.

### Relational model

The database contains four primary tables.

| Table | Purpose |
|---|---|
| `accounts` | Account balances and record versions |
| `transactions` | Transfer transaction records |
| `transaction_audit` | Transaction lifecycle events |
| `isolation_observations` | Isolation behavior observations |

### Relationships

    accounts
       |
       | account_id
       |
       v
    transactions
       |
       | transaction_id
       |
       v
    transaction_audit

    isolation_observations
       |
       v
    Isolation behavior reports

### Integrity constraints

The schema enforces:

- Unique account numbers.
- Unique transaction references.
- Positive transaction amounts.
- Nonnegative account balances.
- Valid account statuses.
- Valid isolation-level values.
- Valid transaction states.
- Foreign-key relationships.
- Different source and destination accounts.

### Version trigger

The account version trigger increments the version whenever an account row changes.

This supports optimistic concurrency demonstrations and record-change auditing.

It does not replace PostgreSQL's native MVCC version information.

### Audit trigger

The transaction audit trigger records changes to transaction status.

This separates transaction-state reporting from the business operation that changes the state.

### Transfer procedure

`transfer_funds` implements a database-side account transfer.

Its operations include:

1. Validate the amount.
2. Validate source and destination accounts.
3. Acquire row locks in a deterministic order.
4. Check available funds.
5. Create a pending transaction record.
6. Debit the source.
7. Credit the destination.
8. Mark the transaction committed.
9. Record an audit event.

The procedure participates in the caller's transaction.

It does not independently commit the surrounding transaction.

### Concurrent transaction demonstrations

The SQL file contains separate-session examples for the isolation levels.

This distinction is necessary because transaction concurrency cannot be demonstrated faithfully through sequential statements in one database session.

The examples show how two independent PostgreSQL sessions can interact.

### Serializable retry handling

A PostgreSQL serialization failure can return SQLSTATE `40001`.

Applications must retry the complete transaction, including the original reads and business-rule decisions.

Retries should be bounded and supported by appropriate error handling.

### Indexing

Indexes support:

- Account status retrieval.
- Source-account transaction history.
- Destination-account transaction history.
- Transaction-status reporting.
- Audit history.
- Isolation observation filtering.

The JSONB audit-details index supports searches involving structured event metadata.

## 14. Isolation-Level Selection

Isolation should be selected according to the consistency requirements of the business operation.

| Workload | Consideration |
|---|---|
| Standard account lookup | Read Committed |
| Independent operational updates | Read Committed |
| Consistent multi-query reporting | Repeatable Read |
| Account reconciliation | Repeatable Read or Serializable |
| Financial settlement | Serializable where required by business invariants |
| Inventory allocation | Serializable or carefully designed locking |
| High-contention updates | Explicit locking and conflict management |
| Approximate analytical processing | Read Committed or snapshot-based reporting, depending on requirements |

The isolation level alone does not guarantee business correctness.

Applications must also enforce constraints, validate input, manage concurrent writes, and handle transaction failures.

## 15. Performance and Resource Considerations

### Transaction duration

Long-running transactions increase the time during which locks or snapshots remain relevant.

They can also delay cleanup of obsolete MVCC row versions.

Transactions should contain only the database operations required for the business unit of work.

### Lock contention

Concurrent writes to the same records can cause blocking.

A deterministic locking order reduces the risk of deadlocks when multiple transactions need the same resources.

### Serialization retries

Serializable transactions can fail when their concurrent dependency patterns cannot be safely serialized.

Retrying a complete transaction introduces additional database work.

High retry rates can indicate excessive contention or an unsuitable transaction design.

### Index maintenance

Indexes improve retrieval performance but introduce additional write overhead.

Indexes should support actual query patterns rather than being created indiscriminately.

### Connection management

Database connections should not remain occupied by idle transactions.

Connection pools must account for transaction duration, application concurrency, and database capacity.

## 16. Security and Reliability

Transaction isolation does not replace database security.

A production system should implement:

- Least-privilege database roles.
- Parameterized SQL statements.
- Input validation.
- Appropriate transaction timeouts.
- Controlled access to sensitive records.
- Audit logging.
- Backup and recovery procedures.
- Safe retry handling.
- Connection encryption where required.
- Monitoring for deadlocks and serialization failures.

### Retry safety

Retries create an important reliability concern.

An application may not know whether an operation committed if a network failure occurs during the response.

For operations such as payments, an idempotency key or unique business transaction reference can prevent duplicate processing.

A retry should not blindly execute an external payment or notification operation again.

### Error handling

Important PostgreSQL errors include:

| SQLSTATE | Meaning |
|---|---|
| `40001` | Serialization failure |
| `40P01` | Deadlock detected |
| `23505` | Unique constraint violation |
| `23503` | Foreign-key violation |
| `23514` | Check constraint violation |

These errors require different handling strategies.

A serialization failure can normally be retried as a complete transaction.

A unique constraint violation may indicate duplicate business processing and should be evaluated according to the operation's semantics.

## 17. Important Technical Distinctions

The following concepts must not be treated as interchangeable:

| Concept | Meaning |
|---|---|
| Isolation level | Rules governing concurrent transaction visibility and anomalies |
| Transaction snapshot | The database state visible to a transaction |
| MVCC | Mechanism for managing multiple row versions |
| Row locking | Mechanism for coordinating conflicting row operations |
| Optimistic concurrency control | Validation of changes against previously observed versions |
| Conflict serializability | Determination of whether a schedule is equivalent to a serial schedule under conflict analysis |
| Serializable isolation | Database guarantee of serializable transaction execution |
| Deadlock | Circular dependency involving transactions waiting for resources |
| Serialization failure | Rejection of an execution that cannot satisfy Serializable guarantees |

A transaction can use MVCC while also acquiring row locks.

Likewise, Serializable isolation does not mean every transaction executes physically one after another.

It means the resulting committed behavior must satisfy the required serial equivalence.

## 18. Execution and Verification

### Python

Run the script with Python 3.10 or later.

Expected demonstrations include dirty-read simulation, non-repeatable reads, stable snapshots, write conflicts, serializable validation, and atomic transfers.

The script ends by executing assertions.

### JavaScript

Run with Node.js 18 or later.

The implementation uses only built-in Node.js modules.

The output includes transaction events, asynchronous commits, conflict handling, and transfer verification.

### C++17

Compile using a C++17-compatible compiler.

The program uses the standard library and requires no third-party dependencies.

It demonstrates version management, transaction scheduling, and precedence graph analysis.

### Java 17

Compile the source using Java 17.

The main class is `TransactionIsolationEnterprise`.

The program demonstrates enterprise transaction management, policy selection, auditing, and account transfers.

### PostgreSQL

Execute the SQL file using PostgreSQL 15 or later.

The script recreates the `isolation_lab` schema.

It creates tables, constraints, indexes, functions, procedures, triggers, and views before inserting sample data and executing reporting queries.

The `pgcrypto` extension is not required because `gen_random_uuid()` is available in the specified PostgreSQL versions.

The concurrent demonstrations must be run in separate database sessions to observe real transaction interaction.

## 19. Limitations and Interpretation

The five implementations serve different technical purposes.

| Implementation | Primary perspective | Main limitation |
|---|---|---|
| Python | Versioned transaction simulation | Simplified concurrency and validation |
| JavaScript | Asynchronous event-driven workflow | No actual multi-process transaction manager |
| C++17 | Schedule and precedence graph analysis | No complete database execution engine |
| Java 17 | Enterprise transaction and policy modeling | In-memory persistence |
| PostgreSQL | Actual relational database transactions | Concurrent demonstrations require separate sessions |

The source implementations should not be interpreted as interchangeable database engines.

In particular:

- The Python dirty-read simulation demonstrates a general isolation concept, not PostgreSQL behavior.
- The JavaScript commit mechanism is limited to its single-process execution model.
- The C++ precedence graph evaluates conflict serializability rather than implementing full database serializability.
- The Java policy registry illustrates isolation selection, not a replacement for database transaction management.
- PostgreSQL provides the actual MVCC and concurrency-control mechanisms.

The central engineering decision is to select an isolation strategy based on the business invariants, concurrency patterns, and failure-handling requirements of the application.
