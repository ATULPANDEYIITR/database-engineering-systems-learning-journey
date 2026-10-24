
# PostgreSQL Transactions: BEGIN, COMMIT, ROLLBACK, and SAVEPOINT

## Scope

This project models PostgreSQL transaction processing through five independent implementations:

| File | Primary perspective | Main mechanism |
|---|---|---|
| Python | Application transaction simulation | Transaction object with isolated working state |
| JavaScript | Event-driven application model | Events, asynchronous workflow, and savepoints |
| C++17 | Transaction engine | STL-based transactional state and conflict detection |
| Java 17 | Enterprise domain model | Explicit services, domain types, validation, and state transitions |
| PostgreSQL | Relational implementation | Real transactions, constraints, triggers, locks, functions, and savepoints |

The central concept is that a transaction groups related database operations into one unit of work. A successful transaction makes its changes durable through `COMMIT`. A transaction that cannot safely complete can discard its changes through `ROLLBACK`. A `SAVEPOINT` creates an intermediate recovery point inside an active transaction.

The implementations intentionally distinguish actual PostgreSQL behavior from application-level simulations. The Python, JavaScript, C++17, and Java 17 programs model transaction semantics without connecting to PostgreSQL. The SQL file uses PostgreSQL transaction commands directly.

## Transaction Lifecycle

A transaction normally follows this lifecycle:

```text
BEGIN
  |
  v
ACTIVE
  |
  +---- successful operations ----> COMMIT ----> DURABLE STATE
  |
  +---- failure ------------------> ROLLBACK --> ORIGINAL STATE
  |
  +---- partial recovery ---------> SAVEPOINT
                                      |
                                      v
                              ROLLBACK TO SAVEPOINT
                                      |
                                      v
                              continue transaction
                                      |
                                      v
                                    COMMIT
```

`BEGIN` establishes a transaction boundary. Statements executed after `BEGIN` participate in that transaction until `COMMIT` or `ROLLBACK`.

`COMMIT` makes the transaction's changes durable and releases transactional resources.

`ROLLBACK` discards changes made by the current transaction.

`SAVEPOINT` does not start an independent transaction. It establishes a point inside the existing transaction to which execution can return.

`ROLLBACK TO SAVEPOINT` discards changes made after the named savepoint while retaining earlier work.

`RELEASE SAVEPOINT` removes the named recovery point while leaving the transaction active.

## Atomicity

Atomicity means that a transaction is treated as one unit of work.

Consider a transfer:

```text
Account A
   |
   | subtract 125
   v
Account A - 125

Account B
   |
   | add 125
   v
Account B + 125
```

The two balance changes must not produce a committed state in which only one side changed.

The PostgreSQL implementation uses `transfer_funds()` to perform both updates inside the caller's transaction. The function locks the relevant account rows, validates the source balance, subtracts from the source, and adds to the target.

If an exception occurs before the transaction commits, the transaction can be rolled back.

## BEGIN

`BEGIN` starts an explicit transaction block.

The PostgreSQL implementation uses explicit boundaries such as:

```sql
BEGIN;
-- Operation 1
-- Operation 2
COMMIT;
```

This is different from treating every individual SQL statement as an independent unit of application work.

Explicit transaction boundaries are important when several statements must succeed or fail together.

For example, creating a transfer request and marking that transfer as completed should not leave an inconsistent workflow state.

## COMMIT

`COMMIT` completes the transaction successfully.

Before the commit, modifications belong to the transaction and are subject to the transaction's visibility and locking rules.

After the commit, the changes become part of the durable database state.

The SQL implementation uses successful transfers followed by `COMMIT`. The application simulations implement the same conceptual boundary by replacing repository state only during their `commit()` methods.

The simulations also perform version checks before publishing their working state. This is an application-level concurrency model rather than a replacement for PostgreSQL's MVCC and isolation mechanisms.

## ROLLBACK

`ROLLBACK` abandons the current transaction.

A useful failure pattern is:

```text
BEGIN
  |
  +--> valid operation
  |
  +--> failing operation
  |
  +--> ROLLBACK
```

The SQL implementation deliberately performs a valid balance change followed by an exception and then rolls the complete transaction back.

The important distinction is that a statement failure and transaction recovery are related but not identical concepts. Depending on the error and execution context, PostgreSQL can place the transaction into an aborted state. The application must then roll back the transaction or roll back to a suitable savepoint before continuing with additional SQL statements.

The Python, JavaScript, C++17, and Java 17 models make this recovery behavior explicit through transaction state objects and exceptions.

## SAVEPOINT

A savepoint creates a partial recovery boundary.

Example:

```text
BEGIN
  |
  +--> operation A
  |
  +--> SAVEPOINT s1
  |
  +--> operation B fails
  |
  +--> ROLLBACK TO SAVEPOINT s1
  |
  +--> operation C
  |
  +--> COMMIT
```

Operation A remains part of the transaction.

Operation B is discarded.

Operation C is retained when the transaction commits.

This differs from a complete `ROLLBACK`, which discards all transaction changes.

The PostgreSQL script uses `SAVEPOINT before_risky_operation` before operations that may violate balance constraints.

## RELEASE SAVEPOINT

`RELEASE SAVEPOINT` removes a savepoint that is no longer needed.

It does not commit the surrounding transaction.

The transaction remains active and can continue executing statements.

This distinction is important:

| Command | Effect on transaction |
|---|---|
| `COMMIT` | Ends transaction successfully |
| `ROLLBACK` | Ends transaction and discards transaction changes |
| `SAVEPOINT` | Creates an internal recovery point |
| `ROLLBACK TO SAVEPOINT` | Reverts changes after the savepoint |
| `RELEASE SAVEPOINT` | Removes the savepoint without ending the transaction |

## Statement Failure Versus Transaction Failure

A transaction contains multiple statements, but PostgreSQL does not treat every failed statement as an opportunity to continue normally.

For example:

```sql
BEGIN;
UPDATE accounts SET balance = balance - 10 WHERE account_id = 1;
-- An invalid statement causes an error.
UPDATE accounts SET balance = balance + 10 WHERE account_id = 2;
COMMIT;
```

If the invalid statement causes the transaction to enter the aborted state, subsequent statements cannot simply proceed as though nothing happened.

A savepoint changes the recovery strategy:

```sql
BEGIN;
UPDATE accounts SET balance = balance - 10 WHERE account_id = 1;

SAVEPOINT s1;

-- An operation that may fail.

ROLLBACK TO SAVEPOINT s1;

UPDATE accounts SET balance = balance + 10 WHERE account_id = 2;
COMMIT;
```

This allows the application to recover from a localized failure while retaining valid earlier work.

## Constraints and Transactions

The PostgreSQL implementation uses database constraints to prevent invalid state.

The `accounts` table contains:

- A primary key.
- A non-null owner.
- A non-negative balance check.
- A non-negative version check.

The `transfer_requests` table contains:

- A primary key.
- Foreign keys.
- A positive amount constraint.
- A source/target distinction constraint.
- A controlled workflow status.

Database constraints are important because application validation alone cannot guarantee integrity when multiple clients can write to the same database.

The Python, JavaScript, C++17, and Java implementations reproduce these constraints through explicit validation exceptions.

## Triggers

The SQL implementation uses triggers for three separate responsibilities:

1. Preventing an account from being persisted with a negative balance.
2. Incrementing `account_version` when the balance changes.
3. Recording balance changes in `transaction_audit`.

Triggers execute as part of the database operation and therefore participate in the surrounding transaction.

If the surrounding transaction rolls back, trigger-generated changes are rolled back as well.

This is a major reason transactional boundaries are useful for audit and integrity mechanisms.

## Functions and Transaction Boundaries

`transfer_funds()` is a PostgreSQL function that performs the domain-specific transfer operation.

The function:

1. Validates that source and target accounts differ.
2. Validates that the amount is positive.
3. Locks the relevant account rows.
4. Verifies that the source exists.
5. Verifies that the target exists.
6. Checks available funds.
7. Decreases the source balance.
8. Increases the target balance.
9. Records an audit event.

The function does not independently create the caller's outer transaction. The caller controls the transaction boundary.

This separation allows the same function to participate in a larger transactional workflow.

## Row Locking

The transfer implementation uses `SELECT ... FOR UPDATE`.

The lock protects rows from concurrent modifications that could invalidate the balance decision made by the current transaction.

The conceptual sequence is:

```text
Transaction A
    |
    +-- lock Account 1
    |
    +-- check balance
    |
    +-- subtract amount
    |
    +-- commit
    |
    v
Transaction B can continue
```

The SQL implementation orders account IDs before acquiring locks. Consistent lock ordering reduces the possibility of deadlocks when multiple transactions transfer funds between overlapping account pairs.

Locks are released according to PostgreSQL transaction semantics when the transaction completes.

## MVCC

PostgreSQL uses Multiversion Concurrency Control, commonly called MVCC.

MVCC allows transactions to work with transaction-consistent views of data while concurrent transactions are executing.

The application implementations use simpler copies of repository state. These copies are educational models, not replacements for PostgreSQL MVCC.

The SQL implementation therefore provides the more accurate database perspective:

- Transactions establish visibility rules.
- Row locks protect selected rows.
- Concurrent transactions can observe different transaction snapshots depending on isolation.
- Committed changes become visible according to PostgreSQL's concurrency rules.

## Isolation

Transaction isolation determines how concurrent transactions can observe and interact with one another.

PostgreSQL provides these isolation levels:

| Isolation level | Main property |
|---|---|
| Read Uncommitted | PostgreSQL treats this effectively as Read Committed |
| Read Committed | Each statement normally sees a snapshot of committed data at statement start |
| Repeatable Read | The transaction maintains a stable snapshot for reads |
| Serializable | PostgreSQL enforces serializable behavior and may require transaction retry after serialization failure |

`Read Committed` is PostgreSQL's default isolation level.

The SQL artifact does not artificially change the default isolation level because its core purpose is explicit transaction control rather than a single isolation-level demonstration.

Applications using `SERIALIZABLE` must be prepared to retry transactions that fail with serialization-related errors.

## Savepoints and Nested Work

A savepoint resembles a nested recovery boundary but is not a fully independent nested transaction.

For example:

```text
Transaction
|
+-- Work A
|
+-- Savepoint S1
|   |
|   +-- Work B
|   |
|   +-- Roll back B
|
+-- Work C
|
+-- Commit
```

Work A survives.

Work B is reverted.

Work C can proceed.

The Python, JavaScript, C++17, and Java implementations represent savepoints as snapshots of transaction-local state.

The PostgreSQL implementation uses the actual `SAVEPOINT`, `ROLLBACK TO SAVEPOINT`, and `RELEASE SAVEPOINT` commands.

## Python Implementation

The Python program defines:

- `Database`
- `Transaction`
- `Savepoint`
- `Account`
- `AuditEvent`
- Transaction-specific exceptions.
- A transaction manager.

The `Transaction` object maintains a working copy of accounts. `commit()` publishes the working state only when the database version is unchanged.

The program demonstrates:

- Successful commit.
- Complete rollback after insufficient funds.
- Savepoint recovery.
- Atomic transfer.
- Optimistic conflict detection.
- Audit logging.
- Executable assertions.

`Decimal` is used instead of binary floating-point arithmetic for account balances.

The version check is deliberately simple. A production PostgreSQL application should rely on PostgreSQL transaction isolation and explicit concurrency controls appropriate to the workload.

## JavaScript Implementation

The JavaScript implementation uses Node.js standard-library functionality and `EventEmitter`.

The transaction object emits events for:

- Data changes.
- Savepoint creation.
- Savepoint rollback.
- Savepoint release.
- Commit.
- Rollback.

The asynchronous `transfer()` method demonstrates how an application workflow can include asynchronous processing while retaining an explicit transaction object.

The implementation uses `Map` for account storage and clones transaction state when creating recovery points.

JavaScript numbers are not ideal for financial amounts at arbitrary precision. The example uses ordinary numbers for clarity and controlled demonstration values. A production financial application should use an exact decimal representation or integer minor units appropriate to the domain.

## C++17 Implementation

The C++ program models transaction state with:

- `enum class`
- `struct`
- `std::map`
- `std::vector`
- Exception types.
- A transaction manager.
- Explicit savepoint objects.

Account balances are represented as integer cents rather than floating-point values.

For example:

```text
150000 cents = 1500.00
```

This avoids floating-point rounding problems for the modeled monetary values.

The C++ transaction engine performs a complete state replacement during commit and rejects a commit if the repository version has changed since the transaction began.

The conflict mechanism provides a clear model of optimistic concurrency control while remaining distinct from PostgreSQL's actual MVCC implementation.

## Java 17 Implementation

The Java implementation uses an enterprise-oriented domain structure.

Important types include:

- `Repository`
- `Transaction`
- `TransactionService`
- `Account`
- `Savepoint`
- `AuditEvent`
- Transaction-specific exception types.

`AuditEvent` is represented as a Java record because it is immutable data.

`Account` validates its domain invariants and normalizes monetary values to two decimal places.

`TransactionService` owns transaction identifiers and creates explicit transaction objects.

The transaction object exposes domain operations rather than exposing its internal collections directly.

The model also makes transaction state explicit through the `TransactionState` enum.

## PostgreSQL Implementation

The SQL file creates a dedicated `transaction_lab` schema.

Its relational model includes:

| Object | Purpose |
|---|---|
| `accounts` | Durable account balances |
| `repositories` | Versioned repository-style metadata |
| `transaction_audit` | Transactional audit information |
| `transfer_requests` | Transfer workflow state |
| `account_transaction_summary` | Reporting view |

The SQL also includes:

- Primary keys.
- Foreign keys.
- Unique constraints.
- Check constraints.
- Indexes.
- Triggers.
- PL/pgSQL functions.
- Explicit transactions.
- Savepoints.
- Row locks.
- CTEs.
- Reporting queries.

The script starts by dropping and recreating the dedicated schema so it can be executed repeatedly in a clean PostgreSQL database.

**Warning:** Dropping and recreating the schema deletes existing objects and data in `transaction_lab`. Run the script only in an appropriate test database or after backing up any required data.

## Transactional Audit

Audit records are generated by database triggers and explicit transfer processing.

The important property is that audit records participate in the same transaction as the operation that caused them.

For example:

```text
BEGIN
  |
  +-- update account
  |
  +-- trigger creates audit row
  |
  +-- later operation fails
  |
  +-- ROLLBACK
```

The account update and its audit record are both rolled back.

This prevents an audit trail from claiming that a transaction occurred when the corresponding database change was not committed.

## Optimistic Concurrency

The SQL schema contains `account_version`.

The value is increased when the account balance changes.

Application code can use the version as an optimistic concurrency token:

```text
read row
  |
  +-- remember version = 7
  |
modify row only when version = 7
  |
  +-- success -> new version = 8
  |
  +-- zero rows affected -> concurrent modification detected
```

The SQL file includes a CTE-based update demonstrating this pattern.

The version mechanism complements PostgreSQL's transactional concurrency controls. It should not be confused with PostgreSQL's internal transaction IDs or MVCC implementation.

## Transactional Integrity

The database design places important invariants at the database layer.

Examples include:

- Balances cannot be negative.
- Transfer amounts must be positive.
- Source and target accounts must differ.
- Account identifiers must be unique.
- Transfer statuses are restricted to known values.
- Referenced accounts must exist.

The combination of constraints, triggers, transactions, and row locks creates multiple layers of protection.

A robust application should not depend exclusively on a client-side check such as:

```python
if balance >= amount:
    ...
```

The value can change between a client-side check and a database update when multiple transactions are active.

Database-side locking and conditional updates provide stronger protection.

## Failure Handling

The implementations distinguish several failure classes.

| Failure | Appropriate response |
|---|---|
| Invalid amount | Reject operation |
| Missing account | Reject operation |
| Insufficient funds | Reject or recover to savepoint |
| Constraint violation | Roll back affected transaction work |
| Transaction state misuse | Reject operation |
| Concurrent state change | Retry or abort according to policy |
| Serialization failure | Retry complete transaction when appropriate |

A retry after a serialization failure must generally restart the transaction rather than simply repeat the failed statement.

This matters because a serialization failure means the transaction's previous assumptions may no longer be valid.

## Performance Considerations

Transactions have operational costs.

Long-running transactions can:

- Retain old row versions.
- Delay cleanup.
- Hold locks.
- Increase contention.
- Increase the impact of failures.

A practical transaction should normally contain only the operations that must be atomic.

The SQL implementation uses indexes where they support recurring access patterns:

- Audit records by account and time.
- Transfer requests by status and time.

Indexes are not added to every column because unnecessary indexes increase storage and write overhead.

Row locking is scoped to the accounts required by the transfer rather than locking the entire table.

## Security Considerations

Transaction control contributes to integrity but is not an authorization system.

A production application should separately control:

- Database credentials.
- Role privileges.
- Ownership.
- Access to sensitive tables.
- Application authorization.
- Connection security.
- Audit access.

The SQL design demonstrates data integrity constraints, not a complete identity and access-management architecture.

Application code should use parameterized SQL rather than constructing SQL statements through string concatenation.

Transaction boundaries should also prevent partially completed security-sensitive workflows from becoming durable.

## Common Failure Modes

### Forgetting to Commit

A transaction that remains open can hold resources and locks longer than expected.

Applications should ensure that successful work reaches `COMMIT` and failed work reaches `ROLLBACK`.

### Continuing After a Transaction Error

An aborted PostgreSQL transaction cannot simply continue with arbitrary statements.

The application should roll back the transaction or use an appropriate savepoint recovery strategy.

### Using Savepoints as Independent Transactions

A savepoint does not make its changes independently durable.

The outer transaction must still commit.

### Long Transactions

Keeping a transaction open while waiting for external services is risky.

External calls should normally be separated from database transactions unless the architecture explicitly requires the database transaction to remain open.

### Incorrect Lock Ordering

Concurrent transactions that acquire overlapping locks in inconsistent orders can create deadlocks.

Consistent lock ordering reduces this risk.

### Application-Only Validation

A balance check performed only in application code can become stale under concurrency.

Important invariants should be enforced by the database as well.

## Practical Workflow

A robust transactional workflow can be represented as:

```text
Validate request
      |
      v
BEGIN
      |
      v
Lock or otherwise protect required rows
      |
      v
Perform database changes
      |
      +------ failure ------> ROLLBACK
      |
      v
Validate final state
      |
      v
COMMIT
      |
      v
Durable state
```

For workflows containing recoverable optional operations:

```text
BEGIN
  |
  +-- required work
  |
  +-- SAVEPOINT
  |
  +-- optional work
  |       |
  |       +-- failure
  |              |
  |              v
  |       ROLLBACK TO SAVEPOINT
  |
  +-- required final work
  |
  +-- COMMIT
```

The correct choice between complete rollback and savepoint recovery depends on whether the earlier work remains valid after the failure.

## Implementation Distinctions

The five source files intentionally use different implementation approaches.

| Implementation | Main design decision |
|---|---|
| Python | Decimal money, object-based transaction state, assertions |
| JavaScript | Event-driven transaction events and asynchronous transfer |
| C++17 | Integer cents, STL state containers, exception-based engine |
| Java 17 | Explicit enterprise domain types and immutable audit records |
| PostgreSQL | Actual transaction commands, MVCC-compatible locking, constraints, triggers, and functions |

The simulations are useful for understanding transaction state and recovery logic, while the PostgreSQL implementation demonstrates the actual database mechanisms that enforce transactional behavior.

## Boundaries of the Model

The application-language implementations do not reproduce PostgreSQL internals.

They do not implement:

- PostgreSQL MVCC tuple versions.
- PostgreSQL WAL.
- PostgreSQL lock manager internals.
- PostgreSQL isolation snapshots.
- Crash recovery.
- Two-phase commit.
- Distributed transactions.
- Replication.

Their purpose is to make transaction boundaries, failure handling, savepoints, and concurrency decisions explicit.

The PostgreSQL script provides the database-level implementation for these concepts.

## Key Distinctions

The central distinctions are:

| Mechanism | Primary responsibility |
|---|---|
| `BEGIN` | Establish transaction boundary |
| `COMMIT` | Make successful transaction changes durable |
| `ROLLBACK` | Discard the transaction |
| `SAVEPOINT` | Establish partial recovery point |
| `ROLLBACK TO SAVEPOINT` | Discard changes after a savepoint |
| `RELEASE SAVEPOINT` | Remove a savepoint |
| Constraint | Reject invalid database state |
| Trigger | Enforce or react to database changes |
| Row lock | Coordinate concurrent modifications |
| Isolation level | Define visibility and concurrency guarantees |
| Version token | Support explicit optimistic concurrency checks |

These mechanisms solve different problems. A savepoint is not a replacement for a transaction, a constraint is not a replacement for authorization, and an application version column is not a replacement for PostgreSQL's concurrency-control system.
