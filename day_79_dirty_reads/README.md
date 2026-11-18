# Dirty Reads: Causes, Examples and Prevention

## 1. Introduction

A dirty read occurs when one database transaction reads data written by another transaction before that transaction has committed.

The problem is that the reading transaction uses data that is not yet permanent. The writing transaction might subsequently commit, or it might roll back.

If it rolls back, the reading transaction has already used a value that never became part of the committed database state.

Dirty reads are a transaction-isolation problem in relational database systems.

They are particularly important in financial applications, inventory management, payment processing, order management, banking systems, and other applications where incorrect intermediate values can influence business decisions.

## 2. Fundamental Transaction Concepts

A database transaction is a group of operations treated as one logical unit of work.

The main transaction operations are:

| Operation | Meaning |
|---|---|
| BEGIN | Starts a transaction |
| READ | Retrieves database information |
| INSERT | Adds a record |
| UPDATE | Changes an existing record |
| DELETE | Removes a record |
| COMMIT | Permanently publishes transaction changes |
| ROLLBACK | Cancels uncommitted transaction changes |

A transaction generally follows this lifecycle:

Transaction begins

→ Reads existing data

→ Performs operations

→ Stages changes

→ Validates changes

→ COMMIT or ROLLBACK

The important distinction is between a staged change and a committed change.

A staged change belongs to an active transaction. A committed change becomes part of the database's committed state.

Other transactions must follow the database engine's isolation rules when accessing these changes.

## 3. What Is a Dirty Read?

A dirty read happens when Transaction B reads an uncommitted change made by Transaction A.

Consider a bank account with an original balance of ₹10,000.

Transaction A changes the balance to ₹4,000 but has not committed.

Transaction B reads the balance and receives ₹4,000.

Transaction A then rolls back.

The actual committed balance remains ₹10,000.

Transaction B has therefore used an invalid intermediate value.

### Transaction sequence

| Step | Transaction A | Transaction B | Database state |
|---|---|---|---|
| 1 | Begins | | ₹10,000 committed |
| 2 | | Begins | ₹10,000 committed |
| 3 | Changes balance to ₹4,000 | | ₹10,000 committed, ₹4,000 uncommitted |
| 4 | | Reads balance | May observe ₹4,000 |
| 5 | Rolls back | | ₹10,000 committed |
| 6 | | Continues processing | Previously observed ₹4,000 was invalid |

The dirty read occurs at step 4.

The rollback at step 5 demonstrates why the value was unsafe.

### Important distinction

A dirty read is not simply reading recently modified data.

A transaction can safely read a recently modified value if the modifying transaction has committed and the database's isolation rules permit that read.

The defining characteristic is that the value came from another transaction that had not committed.

## 4. Causes of Dirty Reads

Dirty reads generally arise from a combination of transaction concurrency and insufficient isolation.

### 4.1 Concurrent transactions

Multiple transactions execute during overlapping periods.

For example:

- Transaction A updates a customer account.
- Transaction B reads that account.
- Transaction A has not committed.
- Transaction B receives the intermediate value if the database permits it.

Concurrency itself is not a problem. The problem is allowing one transaction to observe another transaction's uncommitted changes.

### 4.2 READ UNCOMMITTED isolation

READ UNCOMMITTED is the weakest standard SQL transaction-isolation level.

In database systems that support dirty-read visibility, transactions using this isolation level may read changes that other transactions have not committed.

This can improve concurrency in some workloads, but it sacrifices the guarantee that every observed value is committed.

### 4.3 Long-running transactions

Long-running transactions increase the time during which intermediate changes may remain available for observation.

For example, a transaction might update inventory and then perform several additional operations before committing.

Other transactions may interact with the same records during this period.

Shorter transaction boundaries reduce the exposure window, although they do not replace appropriate isolation controls.

### 4.4 Incorrect transaction design

Applications may read values before the transaction that produces those values has completed.

This is especially dangerous when the application uses intermediate values to:

- Approve payments.
- Calculate account balances.
- Confirm inventory availability.
- Generate invoices.
- Authorize withdrawals.
- Make financial decisions.

## 5. Practical Dirty Read Examples

### 5.1 Banking application

Initial balance: ₹50,000.

Transaction A:

- Starts a transaction.
- Changes the balance to ₹20,000.
- Has not committed.

Transaction B:

- Reads the balance.
- Receives ₹20,000.
- Calculates that the customer has insufficient funds.

Transaction A:

- Encounters an error.
- Rolls back.

The actual balance remains ₹50,000.

Transaction B made a decision using a value that was never committed.

### 5.2 Inventory management

Initial inventory: 500 units.

Transaction A temporarily reduces inventory to 100 units while processing a bulk order.

Transaction B reads 100 units and rejects another order.

Transaction A subsequently rolls back because the order fails validation.

Actual inventory remains 500 units.

Transaction B incorrectly rejected a valid order.

### 5.3 Payment processing

Transaction A updates a payment status from PENDING to COMPLETED but has not committed.

Transaction B reads COMPLETED and initiates another business operation.

Transaction A rolls back because the payment gateway rejects the transaction.

Transaction B has acted on an uncommitted payment status.

This can cause incorrect order processing and reconciliation problems.

## 6. Dirty Read Versus Other Concurrency Problems

Dirty reads are different from other transaction anomalies.

| Anomaly | Meaning | Example |
|---|---|---|
| Dirty read | Reading another transaction's uncommitted changes | Reading a balance that is later rolled back |
| Non-repeatable read | Reading the same row twice and obtaining different committed values | A customer's address changes between two reads |
| Phantom read | Repeating a query and finding additional or missing qualifying rows | A new order appears between two queries |
| Lost update | One transaction overwrites another transaction's update | Two users modify the same account using an old value |
| Write skew | Concurrent transactions make individually valid changes that violate a shared rule | Two doctors independently mark themselves unavailable, leaving no doctor on duty |

These problems require different controls.

Preventing dirty reads does not automatically prevent every other concurrency anomaly.

## 7. Transaction Isolation Levels

SQL defines four principal transaction-isolation levels.

| Isolation level | Dirty reads | Non-repeatable reads | Phantom reads |
|---|---|---|---|
| READ UNCOMMITTED | Possible where supported | Possible | Possible |
| READ COMMITTED | Prevented | Possible | Possible |
| REPEATABLE READ | Prevented | Prevented | Depends on implementation and database guarantees |
| SERIALIZABLE | Prevented | Prevented | Prevented |

The table describes the standard isolation guarantees. Actual implementation details can differ between database products.

### 7.1 READ UNCOMMITTED

This is the weakest isolation level.

In systems supporting it, a transaction may read another transaction's uncommitted changes.

Example:

- Transaction A updates an account.
- Transaction B reads the updated balance.
- Transaction A rolls back.

Transaction B has performed a dirty read.

This level should not be used when business decisions require committed data.

### 7.2 READ COMMITTED

READ COMMITTED prevents dirty reads.

A transaction can read only committed data from other transactions.

Example:

- Transaction A changes a balance.
- Transaction B reads the account before A commits.
- Transaction B sees the previous committed balance.
- Transaction A commits.
- A subsequent read by B can see the newly committed balance.

READ COMMITTED generally provides a new committed snapshot for each statement.

Therefore, two SELECT statements within one transaction can return different committed values.

### 7.3 REPEATABLE READ

REPEATABLE READ provides a stable view of data for the transaction, according to the database's implementation.

A transaction that reads a particular row again generally sees the same version rather than a newly committed version from another transaction.

This prevents dirty reads and non-repeatable reads.

The exact treatment of concurrent updates and phantom rows depends on the database implementation.

PostgreSQL implements REPEATABLE READ using snapshot isolation and can raise serialization-related errors for conflicting updates.

### 7.4 SERIALIZABLE

SERIALIZABLE provides the strongest standard isolation guarantee.

Concurrent transactions must produce results equivalent to some valid serial execution.

This helps prevent anomalies that may remain possible at lower isolation levels.

It can introduce additional transaction failures, including serialization errors.

Applications must be prepared to retry transactions that fail for serialization reasons.

## 8. Prevention Mechanisms

### 8.1 Select an appropriate isolation level

The primary prevention mechanism is to avoid allowing transactions to read uncommitted data.

READ COMMITTED is sufficient to prevent dirty reads in systems that implement its standard guarantees.

REPEATABLE READ and SERIALIZABLE provide stronger guarantees when the business operation requires them.

### 8.2 Use COMMIT and ROLLBACK correctly

COMMIT publishes changes.

ROLLBACK discards uncommitted changes.

Applications should avoid exposing intermediate business results before the transaction has completed.

A successful database UPDATE does not necessarily mean that the transaction has committed.

### 8.3 Keep transactions short

A transaction should contain only the operations required for its logical business task.

Avoid:

- Unnecessary user interaction inside a transaction.
- Long external API calls while holding database locks.
- Unnecessary delays before committing.
- Unrelated processing inside transaction boundaries.

### 8.4 Use appropriate locking

Row-level locking can protect critical read-modify-write operations.

For example, PostgreSQL supports SELECT FOR UPDATE.

This allows a transaction to lock selected rows before performing a dependent update.

Locking and isolation are related but distinct mechanisms.

A lock controls concurrent access to particular database resources. Isolation defines the visibility and consistency guarantees of transactions.

### 8.5 Use database constraints

Constraints protect data integrity even when multiple application processes operate concurrently.

Useful constraints include:

- PRIMARY KEY.
- FOREIGN KEY.
- UNIQUE.
- CHECK.
- NOT NULL.

For example, a CHECK constraint can prevent negative account balances.

Constraints do not independently prevent dirty reads, but they reduce the possibility of invalid committed data.

### 8.6 Handle transaction failures

Production applications must handle:

- Deadlocks.
- Serialization failures.
- Lock timeouts.
- Connection interruptions.
- Constraint violations.
- Transaction rollbacks.

A retry should restart the complete logical transaction rather than blindly repeating an individual statement.

Retries should be bounded and should account for external side effects.

## 9. PostgreSQL-Specific Behavior

PostgreSQL has an important implementation difference.

Although PostgreSQL accepts:

- READ UNCOMMITTED.
- READ COMMITTED.
- REPEATABLE READ.
- SERIALIZABLE.

It treats READ UNCOMMITTED as READ COMMITTED.

Therefore, PostgreSQL does not permit dirty reads.

This means the following two settings provide the same effective dirty-read protection in PostgreSQL:

- SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
- SET TRANSACTION ISOLATION LEVEL READ COMMITTED;

This behavior should not be assumed for every database engine.

### PostgreSQL isolation behavior

| Requested level | Effective PostgreSQL behavior |
|---|---|
| READ UNCOMMITTED | READ COMMITTED |
| READ COMMITTED | READ COMMITTED |
| REPEATABLE READ | Snapshot isolation |
| SERIALIZABLE | Serializable execution with conflict detection |

PostgreSQL uses multiversion concurrency control, commonly called MVCC.

MVCC maintains multiple row versions so transactions can access an appropriate committed version without every reader needing to block every writer.

It is one of the main mechanisms used by PostgreSQL to provide transaction isolation.

## 10. Understanding MVCC

MVCC stands for Multiversion Concurrency Control.

Instead of treating every row as having only one immediately visible version, an MVCC database maintains row versions and uses transaction visibility rules to determine which version a transaction can read.

Consider an account with a balance of ₹10,000.

Transaction A updates the balance to ₹7,000.

While A remains uncommitted, another transaction operating under READ COMMITTED can continue reading the previously committed version.

After A commits, subsequent statements can see ₹7,000.

If A rolls back, the uncommitted version does not become visible as committed data.

### Conceptual visibility

Before update:

Committed version: ₹10,000

During uncommitted update:

Committed version: ₹10,000

Uncommitted version: ₹7,000

After commit:

Committed version: ₹7,000

After rollback:

Committed version: ₹10,000

MVCC allows database systems to manage concurrent reads and writes while maintaining visibility rules.

## 11. Implementation Architecture

The five source files implement different views of transaction isolation.

| File | Engineering perspective | Main implementation |
|---|---|---|
| Python | Transaction simulation | Write buffers, isolation policies, anomaly detection, unit tests |
| JavaScript | Event-driven transaction processing | Promise scheduling, event history, policy-based reads |
| C++17 | Transaction engine | STL-based transaction management and governance |
| Java 17 | Enterprise domain architecture | Records, interfaces, isolation policies, services and exceptions |
| PostgreSQL | Relational database implementation | Tables, constraints, functions, procedures, triggers and isolation queries |

### 11.1 Python implementation

The Python script uses an in-memory database.

The `Account` dataclass represents an account.

The `Transaction` dataclass maintains:

- Transaction identifier.
- Isolation level.
- Transaction state.
- Pending writes.
- Snapshot data.
- Read observations.

The `Database` class implements the main transaction operations.

The `read()` method determines which version of a record is visible.

The `write()` method stages a value without immediately modifying committed data.

The `commit()` method validates and publishes changes.

The `rollback()` method discards pending writes.

The `detect_dirty_reads()` method identifies observations that originated from transactions that subsequently rolled back.

The unit tests validate dirty-read behavior, prevention, snapshot consistency and invalid transaction states.

### 11.2 JavaScript implementation

The JavaScript implementation uses Maps for transaction and record storage.

Its event history records transaction operations in execution order.

The event model distinguishes:

- BEGIN.
- READ.
- WRITE.
- COMMIT.
- ROLLBACK.

Asynchronous functions and Promises demonstrate how transaction operations can be scheduled without relying on arbitrary delays.

The implementation also uses explicit validation and transaction-state checks.

This design is useful for understanding how application services coordinate concurrent database operations.

The in-memory simulator does not provide actual database-level concurrency or locking.

### 11.3 C++17 implementation

The C++ implementation uses:

- Structs for domain records.
- Enums for isolation and transaction states.
- Maps for committed records and pending writes.
- Vectors for transaction observations.
- Exceptions for invalid operations.

The transaction engine validates all pending changes before applying them.

This avoids publishing a partially validated write set.

The dirty-read detection function examines observations and determines whether their originating transactions subsequently rolled back.

The implementation also includes snapshot-version conflict checks.

### 11.4 Java 17 implementation

The Java implementation uses an enterprise-oriented design.

Its major domain components are:

| Component | Responsibility |
|---|---|
| Account | Immutable account data |
| Transaction | Transaction state and pending changes |
| Observation | Records a transaction's read result |
| IsolationPolicy | Defines the visibility decision |
| Database | Coordinates transaction operations |
| DirtyReadFinding | Represents a detected anomaly |

The `IsolationPolicy` interface separates visibility rules from transaction management.

The database registers an implementation for each isolation level.

This makes the design easier to extend with additional transaction policies.

Custom exceptions distinguish invalid input from transaction-state failures.

### 11.5 PostgreSQL implementation

The SQL file creates a dedicated `dirty_read_lab` schema.

It includes:

- Account records.
- Transaction audit records.
- Isolation test results.
- Integrity constraints.
- Performance-oriented indexes.
- Audit triggers.
- Balance-update functions.
- A transactional transfer procedure.
- Isolation capability reporting.
- Validation and aggregation queries.

The `transfer_funds` procedure locks account rows in a consistent order.

This helps reduce deadlock risk when multiple transfers involve the same accounts.

The script also demonstrates savepoints and rollback.

Its two-session experiment explains how PostgreSQL prevents dirty reads in practice.

## 12. Detailed Database Workflow

The relational design follows this structure:

Repository-independent database workflow:

Account

→ Transaction begins

→ Transaction reads account

→ Transaction stages an update

→ Isolation rules determine visibility

→ Another transaction attempts to read

→ Database applies visibility and locking rules

→ Original transaction commits or rolls back

→ Database exposes the appropriate committed version

→ Audit and reporting operations examine the result

The distinction between staged data and committed data remains central throughout this workflow.

## 13. Important SQL Mechanisms

| Mechanism | Purpose |
|---|---|
| Schema | Organizes related database objects |
| Primary key | Uniquely identifies records |
| Foreign key | Maintains relationships |
| CHECK | Enforces valid values |
| Index | Improves selected retrieval operations |
| View | Provides reusable reporting queries |
| Function | Performs reusable database logic |
| Procedure | Executes transactional business operations |
| Trigger | Records changes automatically |
| Savepoint | Creates a point to which a transaction can roll back |
| FOR UPDATE | Locks selected rows |
| CTE | Structures a query using named intermediate results |

The audit trigger records committed balance changes as part of the same database transaction.

If the transaction rolls back, the corresponding trigger-generated audit insertion also rolls back.

This is important because an audit record should not incorrectly indicate that an uncommitted change became permanent.

## 14. Security and Data Integrity Considerations

Dirty reads can become a security and operational concern when uncommitted information influences sensitive decisions.

Important controls include:

- Restrict access using database roles.
- Prevent unauthorized modifications.
- Use parameterized SQL statements.
- Validate all input values.
- Apply database constraints.
- Use appropriate transaction isolation.
- Protect critical read-modify-write operations.
- Monitor long-running transactions.
- Record important committed operations.
- Handle transaction failures safely.

A database should not rely exclusively on application-level validation.

Critical integrity rules should also be enforced by the database wherever possible.

## 15. Performance Considerations

Stronger isolation can introduce additional costs.

| Mechanism | Performance consideration |
|---|---|
| READ COMMITTED | Usually provides a practical balance between concurrency and consistency |
| REPEATABLE READ | Maintains a stable transaction snapshot |
| SERIALIZABLE | Can introduce serialization failures and retries |
| Row-level locking | Can cause waiting and deadlocks |
| Long transactions | Can retain old row versions and increase resource usage |
| Indexes | Improve selected queries but add write and storage overhead |
| Audit triggers | Add work to modifying transactions |

The appropriate isolation level should be selected according to business correctness requirements.

Choosing the weakest possible isolation level solely to improve performance can produce incorrect business outcomes.

## 16. Edge Cases and Failure Conditions

The implementations address several important failure conditions.

| Condition | Expected behavior |
|---|---|
| Reading a missing account | Reject the operation |
| Writing a negative balance | Reject the operation |
| Committing an inactive transaction | Raise an error |
| Rolling back an inactive transaction | Raise an error |
| Reading another transaction's pending write | Depends on isolation policy |
| Writer rolls back after an uncommitted read | Dirty-read anomaly |
| Writer commits before a later READ COMMITTED statement | New committed value becomes visible |
| Concurrent update under snapshot isolation | May require conflict handling |
| Invalid transfer amount | Reject the transfer |
| Suspended account | Reject the protected balance operation |

The in-memory implementations are educational transaction models rather than replacements for a database engine.

They do not reproduce all database features, including complete lock scheduling, deadlock detection, process-level concurrency, transaction recovery, or every MVCC rule.

## 17. Practical Application Guidelines

Different applications have different consistency requirements.

| Application | Important consideration |
|---|---|
| Banking | Committed balances and safe read-modify-write operations |
| Payment systems | Payment status must not be treated as final before commit |
| Inventory management | Avoid making stock decisions using uncommitted updates |
| E-commerce | Maintain consistent order and inventory processing |
| Healthcare systems | Avoid decisions based on uncommitted clinical records |
| Financial reporting | Use an appropriate consistent reporting snapshot |
| Enterprise resource planning | Coordinate concurrent updates to shared business records |

For financial operations, READ COMMITTED is generally a safer starting point than READ UNCOMMITTED, but the complete transaction design must still address lost updates, concurrent modifications and business constraints.

For operations requiring stronger consistency, REPEATABLE READ or SERIALIZABLE may be appropriate.

The final choice depends on the database engine, application workflow and correctness requirements.

## 18. Key Technical Distinctions

The following concepts should remain separate:

| Concept | Responsibility |
|---|---|
| Transaction | Groups database operations into a logical unit |
| Isolation level | Controls transaction visibility and consistency guarantees |
| COMMIT | Makes transaction changes permanent |
| ROLLBACK | Cancels uncommitted changes |
| MVCC | Maintains and manages multiple row versions |
| Locking | Coordinates access to shared database resources |
| Constraint | Enforces database integrity rules |
| Audit logging | Records relevant database operations |
| Dirty-read detection | Identifies reads originating from uncommitted changes |

A transaction can be correctly structured while still using an unsuitable isolation level.

Similarly, selecting an appropriate isolation level does not eliminate the need for constraints, locking, error handling and correct transaction boundaries.
