# Non-Repeatable Reads: Concurrency Behavior and Transaction Isolation

## 1. Introduction

A non-repeatable read is a transaction concurrency anomaly in which the same transaction retrieves different committed values for the same database row when it executes an identical query more than once.

The anomaly occurs when another transaction modifies and commits the relevant data between the two read operations.

Transaction isolation determines which changes a transaction can observe while other transactions execute concurrently.

This project implements transaction simulations in Python, JavaScript, C++17, and Java 17, together with a PostgreSQL relational model and executable SQL experiments.

The central scenario is a banking database containing multiple accounts. One transaction reads an account balance, another transaction modifies and commits that balance, and the original transaction reads the account again.

## 2. Fundamental Concepts

### 2.1 Transactions

A transaction is a logical unit of database work. It groups operations that must satisfy defined consistency and atomicity requirements.

A transaction commonly follows this lifecycle:

`BEGIN → READ → WRITE → VALIDATE → COMMIT`

If an operation fails, the transaction can be rolled back.

The four ACID properties are:

| Property | Meaning |
|---|---|
| Atomicity | All transaction changes succeed or none are committed. |
| Consistency | Database constraints remain satisfied. |
| Isolation | Concurrent transactions follow defined visibility and conflict rules. |
| Durability | Committed changes survive failures according to database durability guarantees. |

### 2.2 Concurrent Execution

Concurrent execution occurs when multiple transactions operate on a database during overlapping periods.

Consider two transactions:

- T1 reads the balance of account 1.
- T2 updates account 1 and commits.
- T1 reads account 1 again.

The outcome depends on the isolation level.

| Time | Transaction T1 | Transaction T2 |
|---|---|---|
| 1 | BEGIN | |
| 2 | Read balance = 1,000 | |
| 3 | | BEGIN |
| 4 | | Update balance = 1,500 |
| 5 | | COMMIT |
| 6 | Read balance = 1,500 | |
| 7 | COMMIT | |

T1 observes two different committed values.

This is a non-repeatable read.

### 2.3 Non-Repeatable Read

A non-repeatable read occurs when a previously retrieved row changes from the perspective of a transaction because another transaction commits an update between successive reads.

The important characteristics are:

- The original transaction remains active.
- Both reads access the same logical row.
- Another transaction modifies the row.
- The modification is committed.
- The original transaction observes the new value during a subsequent read.

A change made by an uncommitted transaction is not sufficient to establish a non-repeatable read. That situation relates to a dirty read.

### 2.4 Distinction Between Related Anomalies

| Anomaly | Meaning |
|---|---|
| Dirty read | A transaction reads changes that another transaction has not committed. |
| Non-repeatable read | A transaction reads a row, another transaction changes and commits it, and the first transaction reads a different value. |
| Phantom read | Repeating a predicate-based query produces a different set of qualifying rows. |
| Lost update | One transaction overwrites another transaction's update without properly accounting for it. |
| Write skew | Concurrent transactions modify different rows based on overlapping observations, potentially violating a business invariant. |

These anomalies are related to concurrency but represent different failure conditions.

## 3. Transaction Isolation Levels

Isolation levels define the visibility and concurrency guarantees provided to transactions.

### 3.1 READ UNCOMMITTED

READ UNCOMMITTED permits dirty reads in database systems that implement them.

PostgreSQL does not implement dirty reads. It treats READ UNCOMMITTED as READ COMMITTED.

Consequently, PostgreSQL READ UNCOMMITTED does not expose uncommitted changes.

### 3.2 READ COMMITTED

READ COMMITTED provides a new committed snapshot for each SQL statement.

A transaction can therefore observe different committed values when it repeats a query.

Example:

1. T1 begins.
2. T1 reads an account balance of 1,000.
3. T2 changes the balance to 1,500.
4. T2 commits.
5. T1 executes the same SELECT statement.
6. T1 reads 1,500.

The second read is not repeatable.

This isolation level is useful for general-purpose transactional applications where statement-level visibility is acceptable.

### 3.3 REPEATABLE READ

REPEATABLE READ provides a stable transaction-level snapshot in PostgreSQL.

A transaction continues to observe the database state represented by its snapshot, even when other transactions commit changes after that snapshot was established.

Example:

1. T1 begins.
2. T1 reads a balance of 1,000.
3. T2 updates the balance to 1,500.
4. T2 commits.
5. T1 reads the same account again.
6. T1 still sees 1,000.

PostgreSQL implements REPEATABLE READ using multiversion concurrency control.

A transaction can also encounter a serialization failure when it attempts to modify a row changed by another transaction after its snapshot was established.

REPEATABLE READ in PostgreSQL prevents non-repeatable reads and phantom reads, although it does not prevent every possible serialization anomaly.

### 3.4 SERIALIZABLE

SERIALIZABLE provides the strongest standard transaction isolation level.

The database guarantees that successfully committed concurrent transactions produce results equivalent to some serial execution order.

PostgreSQL uses Serializable Snapshot Isolation (SSI).

SSI tracks read-write dependencies and detects dangerous dependency structures. It can abort transactions when concurrent execution cannot safely be considered serializable.

A transaction can fail with SQLSTATE `40001`, indicating a serialization failure.

Applications must be prepared to retry the entire transaction.

### 3.5 Isolation Comparison

| Isolation level | Dirty reads | Non-repeatable reads | Phantom reads |
|---|---|---|---|
| READ UNCOMMITTED | Possible in some systems | Possible | Possible |
| READ COMMITTED | Prevented | Possible | Possible |
| REPEATABLE READ | Prevented | Prevented | Prevented in PostgreSQL |
| SERIALIZABLE | Prevented | Prevented | Prevented |

The table describes standard isolation guarantees and PostgreSQL behavior. Implementations can provide stronger guarantees than the minimum requirements of an isolation level.

## 4. Mechanisms Behind Non-Repeatable Reads

### 4.1 Statement-Level Snapshots

Under READ COMMITTED, PostgreSQL establishes a snapshot for each statement.

A statement sees data committed before its snapshot was established, subject to PostgreSQL's concurrency and visibility rules.

The next statement can obtain a newer snapshot.

This explains why two SELECT statements inside one transaction can return different committed values.

### 4.2 Transaction-Level Snapshots

Under REPEATABLE READ, PostgreSQL uses a transaction-level snapshot.

The transaction continues to read the row versions visible to that snapshot.

PostgreSQL uses MVCC rather than requiring every reader to block every writer.

### 4.3 Multiversion Concurrency Control

Multiversion Concurrency Control, or MVCC, maintains multiple row versions.

A database transaction determines which versions are visible according to its snapshot and transaction visibility rules.

A simplified representation is:

`Account 1: Version 1 → Version 2 → Version 3`

A transaction using an earlier snapshot can continue to observe an older visible version while a newer committed version exists.

PostgreSQL manages tuple visibility using transaction identifiers and MVCC metadata. The version counters used in this project's application-level simulations are simplified educational representations, not PostgreSQL's internal tuple-version mechanism.

### 4.4 Locks

Locks coordinate access to database resources.

Important lock categories include:

- Row-level locks.
- Table-level locks.
- Transaction-level coordination.
- Advisory locks.

A normal PostgreSQL SELECT does not acquire a row-level lock that blocks ordinary updates.

Commands such as `SELECT ... FOR UPDATE` explicitly acquire row locks and can block conflicting updates.

Locks and snapshots serve different purposes. A stable snapshot does not mean that every row is exclusively locked.

## 5. Python Implementation

File: `non_repeatable_reads.py`

The Python program models transaction behavior using standard-library data structures.

### 5.1 Domain Model

The implementation defines:

- `IsolationLevel`: Supported isolation configurations.
- `TransactionState`: Transaction lifecycle states.
- `Record`: Account data and version.
- `Transaction`: Snapshot, pending writes, and read versions.
- `Database`: Centralized storage and transaction operations.

Dataclasses represent records and transactions.

Dictionaries provide efficient record lookup and transaction write-set storage.

### 5.2 Transaction Lifecycle

The database exposes the following operations:

| Operation | Responsibility |
|---|---|
| `begin()` | Creates a transaction and captures a snapshot. |
| `read()` | Retrieves a visible record version. |
| `write()` | Stores a pending transaction change. |
| `commit()` | Validates and applies pending changes. |
| `rollback()` | Discards uncommitted writes. |
| `show()` | Displays the committed database state. |

### 5.3 Experiments

The program implements six experiments:

1. READ COMMITTED non-repeatable reads.
2. REPEATABLE READ snapshot stability.
3. Serialization and concurrent modification conflicts.
4. Optimistic version validation.
5. Transaction rollback.
6. Thread-safe database modifications.

The first two experiments demonstrate the central difference between statement-level and transaction-level snapshots.

### 5.4 Optimistic Concurrency Control

Each record contains a version number.

A transaction remembers the version associated with its original record.

At commit time, the database compares the expected version with the current committed version.

If the versions differ, the write is rejected.

This prevents a stale transaction from silently overwriting a more recent committed update.

### 5.5 Thread Safety

The threaded experiment uses a reentrant lock around shared database state.

Four threads perform repeated deposits.

The lock ensures that each simulated read-modify-write operation executes atomically within the process.

This is an application-level synchronization mechanism. It is not a replacement for database transaction isolation across multiple application processes or database connections.

### 5.6 Limitations

The Python implementation is a deterministic educational simulator.

Its snapshot and version validation mechanisms are simplified. In particular, it does not implement PostgreSQL's complete SSI dependency tracking or general predicate-locking behavior.

The `READ_UNCOMMITTED` option also models PostgreSQL's effective READ COMMITTED behavior rather than dirty reads.

## 6. JavaScript Implementation

File: `non_repeatable_reads.js`

The JavaScript implementation emphasizes asynchronous execution, event-driven monitoring, and transaction coordination.

### 6.1 Architecture

The main components are:

- `Database`: Shared record storage and transaction creation.
- `Transaction`: Snapshot, write set, and transaction state.
- `Mutex`: Asynchronous mutual exclusion.
- `EventEmitter`: Transaction event reporting.

JavaScript Maps represent records and pending writes.

### 6.2 Asynchronous Coordination

The `Mutex` class implements an asynchronous queue.

Its `acquire()` method either obtains the lock immediately or waits for the previous holder to release it.

The `runExclusive()` method ensures that the lock is released even when an operation throws an exception.

This prevents concurrent asynchronous operations from applying partially coordinated changes to shared in-memory state.

### 6.3 Event-Driven Monitoring

The database publishes the following events:

| Event | Meaning |
|---|---|
| `begin` | A transaction starts. |
| `read` | A transaction reads a record. |
| `write` | A transaction schedules a modification. |
| `commit` | A transaction commits. |
| `rollback` | A transaction rolls back. |

Event listeners produce structured transaction logs.

These events make transaction interleaving easier to observe.

### 6.4 Asynchronous Interleaving

The asynchronous experiment starts a reader transaction and allows it to pause between two reads.

A writer updates and commits the account during that interval.

The reader's second statement obtains a newer committed value under READ COMMITTED.

The experiment illustrates how JavaScript's asynchronous scheduling can expose transaction anomalies when database operations are not isolated appropriately.

### 6.5 Failure Handling

The implementation distinguishes:

- `DatabaseError`
- `SerializationError`
- `WriteConflictError`

The commit operation validates all pending writes before applying them.

This prevents a transaction from partially committing its write set.

### 6.6 Practical Considerations

An in-memory mutex coordinates only operations within the same JavaScript process.

A production application must use database transactions and database-level isolation across multiple processes, servers, and connections.

A mutex in an application does not provide distributed transaction isolation.

## 7. C++17 Implementation

File: `non_repeatable_reads.cpp`

The C++17 program focuses on explicit domain modeling, deterministic execution, and transaction validation.

### 7.1 Data Structures

The implementation uses:

| Structure | Purpose |
|---|---|
| `Record` | Account identity, balance, and version. |
| `Transaction` | Snapshot and pending modifications. |
| `map` | Ordered record storage. |
| `enum class` | Isolation levels and transaction states. |
| `exception` | Structured failure handling. |

The ordered map provides predictable record traversal and lookup.

### 7.2 Governance of Transaction Changes

The commit process follows these steps:

1. Confirm that the transaction is active.
2. Validate the versions of all modified records.
3. Validate the read set for SERIALIZABLE transactions.
4. Apply all pending writes.
5. Increment record versions.
6. Mark the transaction as committed.

If validation fails, the transaction enters the FAILED state.

### 7.3 Experiments

The C++ implementation includes:

- Non-repeatable reads.
- Stable repeatable reads.
- Concurrent writer conflicts.
- Serializable validation.
- Rollback.

The experiments use explicit transaction interleaving instead of relying on operating-system thread scheduling.

This produces deterministic and reproducible results.

### 7.4 Complexity

Let:

- N represent the number of stored records.
- R represent the number of records in a transaction's read set.
- W represent the number of records in its write set.

For the ordered-map implementation:

| Operation | Approximate complexity |
|---|---|
| Record lookup | O(log N) |
| Snapshot copying | O(N) |
| Write-set insertion | O(log N) |
| Read-set validation | O(R log N) |
| Write-set validation | O(W log N) |
| Commit application | O(W log N) |

The full snapshot-copying approach is intentionally simple. Production transaction managers use more efficient MVCC structures.

### 7.5 Engineering Tradeoffs

The implementation uses deterministic transaction interleaving to make isolation behavior easy to inspect.

Its version-based validation is suitable for demonstrating conflicting row updates but is not a complete serializable database implementation.

A production database must also address predicate dependencies, transaction scheduling, deadlocks, recovery, and durable commit processing.

## 8. Java 17 Implementation

File: `NonRepeatableReads.java`

The Java implementation represents an enterprise-oriented transaction service.

### 8.1 Domain Types

The application uses Java 17 records and enums.

`Account` is an immutable record containing:

- Account identifier.
- Account owner.
- Balance in cents.
- Version number.

Using integer cents avoids floating-point rounding problems in monetary calculations.

`Transaction` contains:

- Transaction identifier.
- Isolation level.
- Snapshot.
- Pending writes.
- Read-version information.
- Transaction status.

### 8.2 Service Architecture

The `Database` class manages account operations and transaction execution.

The `ExperimentRunner` interface separates individual experiments from their execution mechanism.

This makes the experiments independently registerable and testable.

### 8.3 Atomic Transfer

The transfer operation validates:

- Positive transfer amount.
- Different source and destination accounts.
- Source account existence.
- Destination account existence.
- Sufficient funds.
- Destination balance overflow.

Both account changes are committed together.

If a transaction fails before commit, the application must roll it back or discard the failed transaction.

### 8.4 State Transitions

The permitted transaction lifecycle is:

`ACTIVE → COMMITTED`

or:

`ACTIVE → ROLLED_BACK`

A validation failure can produce:

`ACTIVE → FAILED`

A completed, rolled-back, or failed transaction cannot perform additional database operations.

### 8.5 Monetary Precision

The implementation stores monetary values as `long` integers representing cents.

For example:

| Monetary value | Stored value |
|---|---:|
| 100.00 | 10,000 |
| 250.50 | 25,050 |
| 1,000.00 | 100,000 |

This avoids the precision problems associated with binary floating-point arithmetic.

### 8.6 Concurrency and Synchronization

The simulator uses synchronized database methods to serialize access to its in-memory state.

This is a simplified process-level concurrency mechanism.

A real enterprise application should delegate isolation, locking, and commit coordination to its transactional database.

## 9. PostgreSQL Implementation

File: `non_repeatable_reads.sql`

The PostgreSQL implementation provides a relational account management model.

### 9.1 Database Schema

The script creates the `concurrency_lab` schema.

Its main tables are:

| Table | Responsibility |
|---|---|
| `accounts` | Stores account identity, balance, and version. |
| `account_transactions` | Stores transfer requests and their outcomes. |
| `transaction_audit` | Records account balance modifications. |

The relationships are:

`Accounts → Account Transactions → Transaction Audit`

Account transaction records reference their source and destination accounts.

Audit records reference the modified account and optionally the associated transfer.

### 9.2 Constraints

The schema enforces:

- Unique account names.
- Non-negative account balances.
- Positive version numbers.
- Positive transfer amounts.
- Different source and target accounts.
- Valid transaction status values.
- Referential integrity.

These constraints provide database-level protection independently of application validation.

### 9.3 Indexing

The script creates indexes for:

- Source-account transaction retrieval.
- Target-account transaction retrieval.
- Transaction-status filtering.
- Account audit history.

These indexes support common operational queries.

Indexes consume storage and increase write costs. Additional indexes should be justified by actual query patterns and execution plans.

### 9.4 Audit Trigger

The `audit_account_change()` trigger function records account balance changes.

When a balance changes, the trigger:

1. Increments the account version.
2. Updates the modification timestamp.
3. Inserts the old balance and new balance into the audit table.
4. Records the old and new version values.

The trigger operates within the transaction that modifies the account.

An audit entry is therefore rolled back if the associated transaction rolls back.

### 9.5 Atomic Transfer Procedure

The `transfer_funds()` procedure performs a transfer between two accounts.

It validates the transfer parameters and locks the account rows in ascending account identifier order.

Consistent lock ordering reduces the possibility of deadlocks when multiple transfers operate on overlapping accounts.

The procedure then:

1. Checks account existence.
2. Checks available funds.
3. Debits the source account.
4. Credits the destination account.
5. Marks the transaction as completed.

The procedure does not issue an independent COMMIT. Its operations participate in the caller's transaction.

A failed transfer raises an exception, which causes the surrounding transaction to fail unless the caller handles the error through an appropriate savepoint or transaction boundary.

### 9.6 Reporting

The script includes:

- Account balance reporting.
- Transaction summary reporting.
- Audit history retrieval.
- Account activity aggregation.
- Common table expressions.
- Database integrity validation.

These queries demonstrate how transaction data can support operational monitoring and reconciliation.

### 9.7 Concurrent Session Experiments

The SQL script contains separate-session instructions for reproducing real PostgreSQL concurrency behavior.

Two independent PostgreSQL connections are necessary.

The READ COMMITTED experiment demonstrates non-repeatable reads.

The REPEATABLE READ experiment demonstrates transaction-level snapshot visibility.

The SERIALIZABLE experiment demonstrates serialization conflict detection.

These experiments should be executed with separate connections rather than sequential statements in one session.

### 9.8 Savepoints

The script also demonstrates savepoints.

A savepoint allows a transaction to undo operations performed after a specific point without necessarily rolling back all earlier transaction work.

`ROLLBACK TO SAVEPOINT` does not terminate the transaction.

## 10. Distinguishing Application Simulations from PostgreSQL

The five implementations use related concepts but do not implement identical database internals.

| Feature | Application simulators | PostgreSQL |
|---|---|---|
| Snapshots | Copied in-memory records | MVCC snapshots |
| Record versions | Explicit counters | Internal tuple and transaction metadata |
| READ COMMITTED | Latest committed record per read | Statement-level snapshots |
| REPEATABLE READ | Stored transaction snapshot | Transaction-level snapshot |
| Write conflicts | Version comparisons | Database concurrency control |
| SERIALIZABLE | Simplified read-set validation | Serializable Snapshot Isolation |
| Locks | In-process synchronization where implemented | Database-managed locks |
| Durability | Not provided | WAL and configured durability mechanisms |

A version counter in an application is not equivalent to PostgreSQL's internal MVCC implementation.

Likewise, checking that previously read records remain unchanged is not a complete implementation of serializable isolation.

## 11. Practical Applications

Non-repeatable reads are important in systems where repeated observations of the same data influence business decisions.

### 11.1 Banking

An account balance is read before a withdrawal.

Another transaction modifies the balance before the first transaction completes.

A transaction that relies on an earlier balance without appropriate validation may make an incorrect decision.

### 11.2 Inventory Management

An order-processing transaction reads available stock.

Another transaction reserves inventory.

The first transaction subsequently observes a different stock quantity.

Inventory reservations require appropriate concurrency control to prevent overselling.

### 11.3 Financial Reporting

A report reads several account balances during concurrent updates.

Under READ COMMITTED, separate statements can observe different committed states.

A consistent transaction snapshot may be preferable when a report requires a stable database view.

### 11.4 Online Payments

Payment processing often requires atomic updates across multiple records.

A transfer must not debit one account without crediting the other.

Database transactions, appropriate isolation, constraints, and retry handling work together to maintain integrity.

### 11.5 Enterprise Applications

Business workflows frequently read data, evaluate conditions, and subsequently update records.

When another transaction changes the relevant data during that workflow, the application must determine whether its earlier decision remains valid.

Isolation and concurrency control provide the foundation for making that decision safely.

## 12. Performance and Security Considerations

### 12.1 Performance

Higher isolation guarantees can increase transaction conflicts and retries.

Long-running transactions can retain old snapshots, delay cleanup of obsolete row versions, and increase database resource consumption.

Useful practices include:

- Keep transactions short.
- Avoid unnecessary database operations inside transactions.
- Use indexes for frequently accessed records.
- Lock records in a consistent order.
- Retry serialization failures when the operation is safe to repeat.
- Monitor transaction duration and lock waits.
- Avoid excessive concurrent updates to heavily contended records.

### 12.2 Security

Concurrency controls are not substitutes for access control.

Production systems should also implement:

- Database authentication.
- Least-privilege permissions.
- Parameterized SQL.
- Restricted administrative access.
- Audit retention policies.
- Protected database connections.
- Appropriate application authorization.

Sensitive account information should not be exposed through diagnostic logs.

### 12.3 Retry Handling

A transaction rejected because of a serialization failure should normally be restarted from its beginning.

Retrying only the final failed SQL statement can be incorrect because earlier reads and business decisions may no longer be valid.

Retry policies should include:

- A bounded retry count.
- Appropriate backoff.
- Transaction-level rollback.
- Idempotency controls for external side effects.
- Logging of repeated failures.

External payment requests, emails, and other non-database operations should not be repeated blindly when a transaction is retried.

## 13. Edge Cases and Limitations

The implementations deliberately address several important failure conditions.

| Condition | Expected handling |
|---|---|
| Unknown account | Reject the operation. |
| Negative balance | Reject the update. |
| Invalid transfer amount | Reject the transfer. |
| Duplicate identifier | Enforce uniqueness. |
| Concurrent modification | Reject a stale write. |
| Serialization conflict | Abort and potentially retry the transaction. |
| Insufficient funds | Reject the transfer. |
| Transaction already completed | Reject further operations. |
| Partial transfer failure | Roll back the entire transfer. |
| Long-running transaction | Monitor resource usage and snapshot retention. |

The educational simulators do not implement complete database recovery, distributed transactions, deadlock detection, predicate locking, or durable storage.

The PostgreSQL implementation provides actual relational constraints, transaction management, row locking, triggers, and MVCC-based isolation through the database engine.

## 14. Repository File Structure

| File | Implementation focus |
|---|---|
| `non_repeatable_reads.py` | Transaction simulation, snapshots, version validation, and thread safety. |
| `non_repeatable_reads.js` | Asynchronous execution, event-driven monitoring, and mutex coordination. |
| `non_repeatable_reads.cpp` | Explicit transaction state, ordered storage, and conflict validation. |
| `NonRepeatableReads.java` | Enterprise domain modeling, monetary precision, and transaction services. |
| `non_repeatable_reads.sql` | PostgreSQL schema, constraints, triggers, procedures, reporting, and concurrent-session experiments. |
| `README.md` | Technical concepts, implementation distinctions, and operational behavior. |

## 15. Execution and Validation

### Python

Requires Python 3.10 or later.

Run the file using `python non_repeatable_reads.py`.

### JavaScript

Requires Node.js 18 or later.

Run the file using `node non_repeatable_reads.js`.

### C++17

Compile using a C++17-compatible compiler.

The program uses only the C++ standard library.

### Java 17

Compile and run the single-file program using Java 17.

The program does not require third-party dependencies.

### PostgreSQL

Execute `non_repeatable_reads.sql` using a PostgreSQL client with permission to create the schema, tables, procedures, and triggers.

The initial setup and demonstration operations are executable SQL.

For the genuine concurrent-session experiments, open two independent PostgreSQL connections and follow the corresponding session instructions in the SQL file.

The SQL setup is designed for a dedicated learning schema. It drops and recreates its experiment tables, so it should not be executed against production data.

## 16. Key Technical Distinctions

The central distinction in this project is the difference between a transaction's view of data and the latest committed state of the database.

The following concepts must remain separate:

- **Non-repeatable read:** An observable change in a previously read row during a transaction.
- **READ COMMITTED:** A new committed snapshot for each statement.
- **REPEATABLE READ:** A stable transaction snapshot.
- **SERIALIZABLE:** A guarantee that successful concurrent execution is equivalent to serial execution.
- **MVCC:** A database mechanism that maintains and exposes multiple row versions.
- **Optimistic concurrency control:** A strategy that validates whether data changed before accepting a write.
- **Pessimistic locking:** A strategy that coordinates conflicting operations through locks.
- **Serialization failure:** An aborted transaction that cannot safely participate in the required serial execution order.

These mechanisms solve related but different problems.

A stable snapshot prevents non-repeatable reads, but it does not automatically make every business operation correct. Applications must still enforce business invariants, validate writes, handle transaction failures, and use appropriate isolation guarantees.
