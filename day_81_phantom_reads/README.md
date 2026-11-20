# Phantom Reads: Range Queries and Transaction Isolation

## 1. Technical Overview

A phantom read occurs when a transaction executes the same range-based query more than once and obtains a different set of qualifying rows because another transaction has inserted, deleted, or modified records that satisfy the query predicate.

The defining characteristic is a change in the result set, not necessarily a modification of an existing record.

Consider an inventory database containing:

| Product ID | Product | Price |
|---:|---|---:|
| 1 | Keyboard | 1200 |
| 2 | Mouse | 800 |
| 3 | Monitor | 8500 |
| 4 | Desk | 6000 |
| 5 | Notebook | 150 |

Transaction A executes:

`SELECT * FROM products WHERE price >= 500 AND price < 5000;`

It initially receives two products: Keyboard and Mouse.

Transaction B inserts a Webcam priced at 2500 and commits.

Transaction A repeats the same query.

Under PostgreSQL READ COMMITTED, the second execution can return three products. The Webcam is a newly visible qualifying row.

The new result is a phantom relative to Transaction A's earlier range query.

## 2. Fundamental Terminology

| Term | Meaning |
|---|---|
| Transaction | A logical unit of database operations |
| Range query | A query selecting rows satisfying a range predicate |
| Predicate | A condition determining which records qualify |
| Phantom row | A newly visible or no longer qualifying row that changes a repeated query's result |
| Snapshot | A consistent view of database visibility at a particular transaction point |
| MVCC | Multi-Version Concurrency Control |
| Isolation level | A transaction-level guarantee governing concurrent visibility |
| Serialization | An execution equivalent to some valid sequential transaction order |
| Predicate conflict | A dependency involving records satisfying a previously evaluated condition |
| Serialization failure | An aborted transaction that cannot safely complete under serializable execution |

A phantom read must be distinguished from a non-repeatable read.

A non-repeatable read involves an existing row whose values change between reads.

A phantom read involves a change in the collection of rows satisfying a predicate.

For example:

- Non-repeatable read: Product 1 changes from 1200 to 1500.
- Phantom read: Product 6 is inserted with a price of 2500 and begins satisfying the range query.

A range query does not need to use a literal SQL `BETWEEN` expression to produce a phantom. Conditions involving comparisons, category membership, date intervals, or other predicates can also produce this behavior.

## 3. Range Query Mechanics

A range query selects records using lower and upper boundaries.

The implementations use half-open intervals:

`minimum <= price < maximum`

For a range of `[500, 5000)`, the following rules apply:

| Price | Included |
|---:|---|
| 499 | No |
| 500 | Yes |
| 1200 | Yes |
| 4999.99 | Yes |
| 5000 | No |

Half-open intervals avoid overlapping adjacent ranges.

For example:

- `[0, 1000)`
- `[1000, 2000)`
- `[2000, 3000)`

Every boundary value belongs to exactly one interval.

Range queries are particularly important in:

- Inventory and pricing systems
- Financial reporting
- Reservation and scheduling systems
- Employee salary analysis
- Banking transaction processing
- Time-series aggregation
- Order management

### How phantoms arise

The following schedule demonstrates the problem.

| Step | Transaction A | Transaction B |
|---|---|---|
| 1 | Begin transaction | |
| 2 | Read products priced 500–4999 | |
| 3 | | Begin transaction |
| 4 | | Insert product priced 2500 |
| 5 | | Commit |
| 6 | Repeat range query | |
| 7 | Observe additional row | |

The important distinction is that Transaction B does not need to modify any record previously returned to Transaction A.

It changes the membership of the queried range.

## 4. Transaction Isolation Levels

Different isolation levels provide different guarantees concerning concurrent changes.

### READ COMMITTED

READ COMMITTED provides statement-level snapshots in PostgreSQL.

Each statement obtains a new snapshot of committed data.

Consequently, two identical SELECT statements within one transaction can observe different committed database states.

This behavior permits phantom reads.

The Python, JavaScript, C++ and Java implementations reproduce this behavior by reading the latest committed database state for each query.

The PostgreSQL demonstration uses:

`BEGIN ISOLATION LEVEL READ COMMITTED;`

A concurrent committed insertion can appear in a subsequent range query.

### REPEATABLE READ

REPEATABLE READ provides a transaction-level snapshot in PostgreSQL.

The transaction continues to observe the database snapshot established by its first relevant statement.

Concurrent transactions may commit new matching records, but those records remain invisible to the existing snapshot.

The same transaction therefore receives a stable range-query result.

PostgreSQL implements REPEATABLE READ using MVCC snapshot visibility. Its behavior is stronger than the minimum SQL standard guarantee because it prevents phantom reads.

A new transaction receives a newer snapshot and can observe the previously committed insertion.

An important distinction is that PostgreSQL REPEATABLE READ does not provide complete serializability. Write-skew anomalies can still occur when concurrent transactions read overlapping information and update different records.

### SERIALIZABLE

SERIALIZABLE provides the strongest standard isolation level.

The database must ensure that successfully committed concurrent transactions behave as though they executed in a valid sequential order.

PostgreSQL implements this guarantee using Serializable Snapshot Isolation (SSI).

SSI tracks read-write dependencies and identifies dangerous structures that could produce a non-serializable execution.

A transaction can therefore fail at commit even when its individual SQL statements executed successfully.

The application must handle SQLSTATE `40001`, roll back the complete transaction, and retry the complete unit of work when appropriate.

## 5. Comparison of Isolation Levels

| Property | Read Committed | Repeatable Read | Serializable |
|---|---|---|---|
| Statement snapshot | New snapshot per statement | Transaction snapshot | Transaction snapshot |
| Dirty reads | Prevented | Prevented | Prevented |
| Non-repeatable reads | Possible | Prevented | Prevented |
| Phantom reads | Possible | Prevented in PostgreSQL | Prevented |
| Write conflicts | Possible | Detected in conflicting updates | Detected where necessary |
| Serialization failures | Not typical for ordinary reads | Possible for conflicting writes | Possible |
| Retry requirements | Application-dependent | Application-dependent | Important |
| Concurrency | Generally high | Generally high | May require retries |

The precise guarantees depend on the database implementation. Isolation levels should not be assumed to have identical internal mechanisms across database products.

## 6. Multi-Version Concurrency Control

MVCC allows database transactions to access appropriate row versions without requiring every reader to block every writer.

A simplified conceptual representation is:

| Product | Version | Price | Visibility |
|---|---:|---:|---|
| Keyboard | 1 | 1200 | Committed |
| Mouse | 2 | 800 | Committed |
| Webcam | 3 | 2500 | Committed after insertion |

Under a transaction-level snapshot, a transaction can continue reading the versions visible to its snapshot even after another transaction commits a new version.

MVCC therefore provides a foundation for consistent reads and concurrent execution.

MVCC alone should not be interpreted as a universal guarantee against phantom reads. The actual behavior depends on snapshot boundaries, isolation level, and database implementation.

PostgreSQL uses transaction IDs and tuple visibility information to determine which row versions are visible.

Old row versions may remain physically present until vacuum processing makes their storage reusable.

## 7. Four Important Mechanisms

These mechanisms should not be treated as interchangeable.

| Mechanism | Responsibility |
|---|---|
| Range query | Defines which rows qualify |
| MVCC | Controls visibility of row versions |
| Repeatable Read | Maintains a stable transaction snapshot |
| Serializable | Enforces serializable transaction behavior |

A range query does not automatically lock all possible future rows.

MVCC does not automatically make every transaction serializable.

Repeatable Read and Serializable provide different guarantees and may have different concurrency costs.

## 8. Python Implementation

The Python implementation provides an in-memory transactional database simulator.

### Domain model

The implementation uses:

- `Product` for inventory records.
- `VersionedProduct` for committed record versions.
- `RangePredicate` for range conditions.
- `Transaction` for transaction state and pending writes.
- `Database` for shared committed state.

The isolation level and transaction state are represented using enumerations.

### Transaction workflow

The workflow is:

`BEGIN → READ → STAGE WRITES → VALIDATE → COMMIT`

A transaction maintains:

- A starting snapshot.
- A starting database version.
- A pending write set.
- Previously evaluated range predicates.
- An explicit transaction state.

READ COMMITTED reads current committed rows.

REPEATABLE READ reads the transaction's original snapshot.

SERIALIZABLE additionally records range predicates and checks subsequent committed changes against them.

### Predicate validation

The simulator records price ranges accessed by serializable transactions.

At commit, it checks whether another transaction committed a product change within a previously read range.

A conflict causes a serialization failure and transaction abortion.

### Important limitation

The Python simulator is an educational optimistic-concurrency model, not a complete implementation of PostgreSQL SSI.

Its range validation is conservative and simplified. It does not implement the complete PostgreSQL dependency graph, transaction identifier management, lock manager, tuple visibility rules, or concurrent execution engine.

Its purpose is to make the relationship between snapshots, predicates, concurrent writes, and commit validation executable.

## 9. JavaScript Implementation

The JavaScript implementation models transactions through an event-driven architecture.

### Main components

| Component | Responsibility |
|---|---|
| `TransactionalStore` | Manages shared committed data |
| `Transaction` | Stores transaction-local state |
| `RangePredicate` | Defines query boundaries |
| `validateProduct()` | Validates inventory records |
| `queryRange()` | Evaluates a range query |
| `commit()` | Validates and applies pending writes |
| `rollback()` | Discards uncommitted writes |

Node.js `EventEmitter` provides transaction lifecycle notifications.

Events include:

- `transaction:begin`
- `query:executed`
- `write:staged`
- `transaction:commit`
- `transaction:abort`
- `transaction:rollback`

The asynchronous commit method provides an interface suitable for asynchronous transaction orchestration.

Its shared-state application phase executes synchronously within the JavaScript event loop.

This simulator does not implement a database lock manager or provide genuine parallel transaction execution. An asynchronous JavaScript method alone does not establish database-level concurrency guarantees.

## 10. C++17 Implementation

The C++ implementation emphasizes explicit domain modeling and controlled state transitions.

### Data structures

| Structure | Purpose |
|---|---|
| `Product` | Represents an inventory record |
| `VersionedProduct` | Associates a record with a version |
| `RangePredicate` | Evaluates interval membership |
| `Change` | Records committed modifications |
| `Transaction` | Stores transaction-local information |
| `Database` | Manages shared database state |

The implementation uses `std::map` for deterministic record lookup and ordered iteration.

Pending insertions and updates are stored in a write set.

A deletion is represented through `std::optional<Product>`.

### Commit behavior

Before applying a write set, the database validates:

1. Transaction state.
2. Concurrent write conflicts.
3. Serializable predicate conflicts.
4. Product constraints.

The write set is applied only after validation succeeds.

This demonstrates the principle of validating a transaction before publishing its changes.

The in-memory implementation assumes a single-threaded execution schedule. It does not claim thread safety or replace the synchronization mechanisms of a production storage engine.

## 11. Java 17 Implementation

The Java implementation introduces an enterprise-oriented service architecture.

### Domain and service components

| Component | Responsibility |
|---|---|
| `Product` record | Immutable inventory entity |
| `RangePredicate` record | Immutable range condition |
| `Transaction` | Transaction lifecycle and write set |
| `ProductDatabase` | Transaction repository implementation |
| `TransactionRepository` | Storage abstraction |
| `TransactionPolicy` | Isolation and retry configuration |
| `InventoryService` | Application-facing range-query service |

Records provide immutable product and range values.

The repository interface separates transaction operations from the service layer.

Custom exceptions distinguish serialization failures, write conflicts, and general transaction errors.

### Enterprise workflow

The inventory service:

1. Constructs a validated range predicate.
2. Begins a transaction according to its configured isolation policy.
3. Executes the range query.
4. Commits the transaction.
5. Handles failures without leaving an active transaction.

The retry limit is represented in the policy model.

A complete production retry mechanism would also need to create a fresh transaction for every attempt, repeat all reads and writes, use bounded backoff, and distinguish retryable from non-retryable errors.

## 12. PostgreSQL Implementation

The PostgreSQL script models the actual relational workflow.

### Relational structure

| Database object | Responsibility |
|---|---|
| `products` | Inventory records |
| `transaction_audit` | Records committed inventory changes |
| `audit_product_change()` | Implements audit behavior |
| `trg_product_audit` | Activates audit processing |
| `get_products_in_range()` | Performs validated range retrieval |
| `is_price_range_eligible()` | Evaluates product eligibility |
| `update_product_price()` | Updates inventory prices |
| `price_range_report` | Aggregates inventory by category |

### Constraints

The product table enforces:

- Primary-key uniqueness.
- Non-empty product names.
- Non-empty categories.
- Non-negative prices.

These constraints prevent invalid records from entering the database through ordinary SQL operations.

### Indexing

The partial index on `(price, product_id)` supports active-product range queries.

The category-price index supports queries combining category filtering with price ranges.

The indexes consume additional storage and increase write maintenance costs. Their usefulness should be verified against actual query plans and workload characteristics.

### Audit behavior

The audit trigger records insertion, modification, and deletion events.

The audit rows participate in the same transaction as the original operation.

Consequently, rolling back the product modification also rolls back its corresponding audit record.

The audit table is an operational change log, not a tamper-proof compliance archive.

### Concurrent transaction experiments

The SQL script contains three separate two-session experiments.

| Experiment | Session A | Session B | Expected behavior |
|---|---|---|---|
| READ COMMITTED | Repeats range query | Inserts matching row | A can observe a phantom |
| REPEATABLE READ | Repeats range query | Inserts matching row | A retains its original snapshot |
| SERIALIZABLE | Reads a range and performs a dependent write | Inserts a matching row | PostgreSQL may abort a transaction to preserve serializability |

These experiments must be executed using two independent database sessions.

Running both transactions sequentially in one SQL session does not demonstrate concurrent visibility.

The Serializable experiment uses a dependent write to make a serialization conflict possible. Its exact outcome depends on transaction timing and dependency structure.

## 13. PostgreSQL Serializable Snapshot Isolation

PostgreSQL SSI differs from conventional strict two-phase locking.

Serializable transactions use MVCC snapshots while the database tracks relevant read-write dependencies.

Predicate-level conflicts are represented internally through predicate locks, commonly exposed through the `SIReadLock` lock mode.

These locks primarily support conflict detection rather than blocking every concurrent writer.

A dangerous dependency structure can cause PostgreSQL to abort a transaction.

The resulting error uses SQLSTATE `40001`.

An application should:

- Roll back the entire failed transaction.
- Start a new transaction.
- Re-execute the complete business operation.
- Use bounded retry attempts.
- Apply appropriate backoff.
- Avoid repeating non-idempotent external side effects.

A successful individual query does not guarantee that its containing serializable transaction will commit.

## 14. Practical Performance Considerations

### Range-query indexes

B-tree indexes are useful for ordered comparisons and many range predicates.

An index on `price` can reduce the number of records examined when the range is selective.

The query planner may still prefer a sequential scan when most rows qualify or the table is small.

### Snapshot retention

Long-running transactions can retain old row versions and interfere with cleanup.

In PostgreSQL, long-running snapshots can contribute to table and index bloat by delaying removal of obsolete tuple versions.

### Serializable retries

Serializable execution can increase transaction aborts under high contention.

Applications must balance stronger correctness guarantees against retry costs.

### Predicate scope

Broad range predicates can interact with more concurrent changes than narrow predicates.

Queries should select the records required by the business operation rather than unnecessarily broad ranges.

### Transaction duration

Short transactions reduce the period during which conflicting operations can develop.

Network calls and unrelated processing should generally remain outside database transactions.

## 15. Security and Data Integrity

Isolation and access control solve different problems.

Transaction isolation governs concurrent visibility and consistency.

Database permissions govern who can read or modify records.

The implementation uses input validation and database constraints to protect record integrity.

Production systems should also consider:

- Least-privilege database roles.
- Parameterized SQL statements.
- Restricted execution privileges on procedures.
- Secure connection configuration.
- Audit-log access restrictions.
- Transaction timeouts.
- Controlled retry policies.
- Protection against unauthorized administrative changes.

A high isolation level does not prevent unauthorized data access.

## 16. Edge Cases and Failure Conditions

| Condition | Expected handling |
|---|---|
| Minimum exceeds maximum | Reject the range |
| Null range boundary | Reject invalid input |
| Negative product price | Reject insertion or update |
| Duplicate product ID | Reject conflicting insertion |
| Concurrent insertion | Validate against transaction visibility and isolation rules |
| Concurrent update | Detect applicable write conflict |
| Concurrent deletion | Prevent stale writes where required |
| Empty range result | Return an empty result set |
| Transaction already committed | Reject further transaction operations |
| Serialization failure | Abort and retry the complete transaction when appropriate |
| Rollback | Discard pending writes |
| Long-running transaction | Monitor snapshot retention and resource usage |

## 17. Educational Comparison of the Five Implementations

| Deliverable | Main engineering perspective | Core mechanism |
|---|---|---|
| Python | Transaction simulation | Versioned records and predicate validation |
| JavaScript | Event-driven transaction management | Lifecycle events and asynchronous orchestration |
| C++17 | Explicit storage and state modeling | Ordered containers and validated write sets |
| Java 17 | Enterprise service architecture | Repository abstraction and transaction policies |
| PostgreSQL | Relational transaction execution | MVCC and Serializable Snapshot Isolation |

The four application-language implementations use deliberately simplified optimistic-concurrency models.

Their serializable predicate validation is not equivalent to a complete production database serialization algorithm.

PostgreSQL provides the actual database-level isolation guarantees.

## 18. Key Conceptual Distinctions

The central relationships are:

- A range query defines the set of records being examined.
- A concurrent insertion or modification can change that set.
- MVCC determines which record versions are visible.
- READ COMMITTED permits a new statement snapshot.
- REPEATABLE READ preserves a transaction snapshot.
- SERIALIZABLE ensures successful transactions are equivalent to a valid serial execution.
- Serialization failures require transaction-level error handling.

A phantom read is therefore a concurrency-control problem involving the membership of a query result, rather than simply a problem involving the repeated reading of one database row.
