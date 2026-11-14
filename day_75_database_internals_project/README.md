# Database Internals Project

## Project Overview

This project examines how a relational database processes information from physical storage to query execution. It implements and models the principal mechanisms responsible for storing records, managing memory, maintaining indexes, preserving transaction changes, and executing relational operations.

The five implementations provide complementary perspectives:

| Implementation | Primary engineering perspective |
|---|---|
| Python | Simulated database engine with storage, transactions, and query operators |
| JavaScript | Asynchronous, event-driven database execution |
| C++17 | Memory-oriented storage and execution architecture |
| Java 17 | Enterprise-oriented database services and domain modeling |
| PostgreSQL | Relational observability, catalog metadata, and operational analysis |

The project distinguishes actual database mechanisms from educational simulations. PostgreSQL provides its own production storage engine, transaction manager, buffer manager, and query executor. The SQL implementation records observations and models selected internal concepts rather than replacing these mechanisms.

---

## 1. Database Architecture

A relational database processes information through several cooperating subsystems.

The principal execution path is:

    SQL Statement
         |
         v
    SQL Parsing
         |
         v
    Semantic Analysis
         |
         v
    Query Optimization
         |
         v
    Physical Query Plan
         |
         v
    Query Execution Engine
         |
         v
    Buffer Manager
         |
         v
    Storage Manager
         |
         v
    Database Files

Transaction management and write-ahead logging support the execution path by controlling consistency and durability.

### Principal subsystems

| Subsystem | Responsibility |
|---|---|
| Catalog | Stores metadata about database objects |
| Storage manager | Manages physical data pages |
| Buffer manager | Maintains frequently accessed pages in memory |
| Transaction manager | Controls transaction state and isolation |
| WAL manager | Records changes for recovery |
| Index manager | Supports efficient record retrieval |
| Query optimizer | Selects an execution strategy |
| Query executor | Executes physical relational operators |
| Statistics manager | Supplies information for cost estimation |

These components are related but have distinct responsibilities. An index does not replace a buffer manager, and a query optimizer does not execute the selected plan.

---

## 2. Relational Storage and Physical Pages

### 2.1 Tables and tuples

A relational table represents a logical collection of records.

A tuple contains attribute values associated with a row. For example, an employee record can contain:

| Attribute | Type | Example |
|---|---|---|
| employee_id | INTEGER | 101 |
| employee_name | TEXT | Asha |
| department_id | INTEGER | 1 |
| salary | NUMERIC | 90000.00 |

The logical table is not necessarily stored as one continuous collection of records. Database engines organize physical storage into pages or blocks.

### 2.2 Pages

A page is a fixed-size unit of database storage and memory management.

A typical page contains:

- Page header.
- Tuple or index information.
- Record-location information.
- Free-space information.
- Additional structural metadata.

The PostgreSQL default database block size is commonly 8192 bytes, although this is determined by the build configuration.

The implementations use simplified page structures containing:

| Field | Purpose |
|---|---|
| Page identifier | Identifies a physical page |
| Page type | Identifies heap or index storage |
| Records | Stores page contents |
| Dirty state | Indicates whether memory differs from disk |
| Page LSN | Identifies the latest associated WAL position |
| Checksum | Supports integrity verification in the educational model |

### 2.3 Heap storage

Heap storage organizes tuples without requiring the physical order of rows to match a particular indexed attribute.

The Python, C++, and Java implementations use collections of heap pages.

When inserting a record, the engine:

1. Identifies the destination table.
2. Searches its available pages.
3. Checks available record capacity.
4. Allocates a page when necessary.
5. Appends the record.
6. Updates the page's dirty state.
7. Associates the operation with a WAL sequence number.

A heap scan reads the table's pages and returns their records.

The primary advantage is straightforward insertion and general-purpose record storage. A heap scan may become expensive when a query needs only a small subset of a large table.

### 2.4 Page utilization

Page utilization measures how much physical page capacity is occupied.

\[
\text{Utilization} =
\frac{\text{Used Bytes}}{\text{Page Size}}
\times 100
\]

The PostgreSQL implementation records:

- Page capacity.
- Occupied bytes.
- Free bytes.
- Tuple count.
- Dirty-page status.

Page-accounting constraints prevent recorded occupied and free space from exceeding the configured page size.

---

## 3. Buffer Management

### 3.1 Purpose of the buffer pool

Disk access is generally more expensive than accessing memory.

The buffer manager retains database pages in memory to avoid repeatedly retrieving the same pages from persistent storage.

A buffer pool consists of a limited number of frames. Each frame holds a database page.

When a requested page is already resident, the operation is a buffer hit.

When the page must be loaded from storage, the operation is a buffer miss.

\[
\text{Hit Ratio} =
\frac{\text{Buffer Hits}}
{\text{Buffer Hits}+\text{Buffer Misses}}
\]

A higher hit ratio can indicate effective memory reuse, although it does not independently establish good query performance.

### 3.2 LRU replacement

The Python implementation uses `OrderedDict`.

The JavaScript implementation uses `Map`.

The C++ implementation combines `unordered_map` and `list`.

The Java implementation uses an access-ordered `LinkedHashMap`.

All four implementations model Least Recently Used replacement.

The replacement procedure is:

1. Access a resident page.
2. Move it to the most-recently-used position.
3. Load missing pages into available frames.
4. When the pool is full, select the least recently used page.
5. Flush the victim if it is dirty.
6. Reuse its frame.

| Operation | Expected complexity |
|---|---|
| Lookup | O(1) average |
| LRU promotion | O(1) |
| Victim identification | O(1) |
| Eviction | O(1), excluding dirty-page I/O |

LRU is a useful baseline. Production systems may use more sophisticated replacement mechanisms to account for sequential scans, workload patterns, and access frequency.

### 3.3 Dirty pages

A dirty page has been modified in memory but has not yet been written to persistent storage.

Writing every modification directly to disk can generate excessive I/O.

The implementations therefore allow modifications to remain in the buffer pool until a flush or eviction operation.

Before writing a dirty page, the WAL durability requirement must be satisfied.

The Python, JavaScript, C++, and Java examples implement this ordering rule.

### 3.4 Buffer pool limitations

The educational implementations use simplified in-memory page collections and counters.

They do not provide:

- Concurrent buffer-frame pinning.
- Production-grade page latches.
- Background writer processes.
- Full checkpoint management.
- Parallel buffer access.
- Production replacement policies.
- Operating-system direct-I/O integration.

These mechanisms require more complex coordination than a basic LRU cache.

---

## 4. Write-Ahead Logging

### 4.1 Purpose

Write-Ahead Logging preserves a sequence of database changes so that committed work can be recovered after a failure.

The fundamental rule is:

**The corresponding log record must become durable before the modified data page is written to persistent storage.**

This rule prevents a dirty data page from reaching disk without the recovery information needed to interpret its changes.

### 4.2 Log Sequence Numbers

A Log Sequence Number identifies a position in the transaction log.

Each recorded operation receives a monotonically increasing LSN.

The educational implementations associate each modified page with its latest relevant LSN.

The WAL manager also tracks a durable LSN representing the highest log position confirmed as durable in the simplified model.

A page is eligible for flushing only when:

\[
\text{Page LSN} \leq \text{Durable LSN}
\]

### 4.3 WAL operations

The Python and JavaScript implementations record structured log entries.

The C++ and Java implementations maintain typed log records.

The PostgreSQL schema records WAL observations with:

- Database identifier.
- Transaction identifier.
- LSN.
- Operation type.
- Relation name.
- Record size.
- Durability observation.

The model distinguishes:

| Operation | Meaning |
|---|---|
| INSERT | New record |
| UPDATE | Existing record modification |
| DELETE | Record deletion |
| COMMIT | Successful transaction completion |
| ABORT | Transaction cancellation |
| CHECKPOINT | Recovery-related checkpoint event |
| FULL_PAGE_IMAGE | Full-page image observation |

The SQL schema records observations rather than constructing PostgreSQL's actual WAL stream.

### 4.4 Recovery distinction

WAL-based recovery generally involves two major activities:

- Redo: Reapply necessary logged changes.
- Undo: Reverse incomplete transactional changes where required by the recovery design.

The Python implementation demonstrates basic undo actions.

The other implementations model transaction changes and rollback.

None of the educational engines implements complete crash recovery, ARIES recovery, fuzzy checkpoints, or production-grade concurrent recovery.

---

## 5. Transactions and ACID Properties

A transaction groups database operations into a logical unit of work.

The four ACID properties are:

| Property | Meaning |
|---|---|
| Atomicity | A transaction succeeds completely or is rolled back |
| Consistency | Database constraints remain satisfied |
| Isolation | Concurrent transactions observe behavior governed by the isolation model |
| Durability | Committed changes survive the failures covered by the durability mechanism |

### 5.1 Transaction lifecycle

The implementations use three principal transaction states:

    ACTIVE
       |
       +-----------> COMMITTED
       |
       +-----------> ABORTED

A transaction cannot be committed or rolled back again after reaching a terminal state.

### 5.2 Commit processing

The educational transaction workflow:

1. Validates that the transaction is active.
2. Appends a commit record.
3. Flushes the WAL.
4. Flushes dirty database pages.
5. Marks the transaction committed.
6. Releases its undo information.

A production database can acknowledge a committed transaction after the commit record is durable without requiring every modified data page to be immediately flushed.

The educational implementations use simplified page-flush behavior.

### 5.3 Rollback processing

Rollback executes registered undo operations in reverse order.

Reverse execution matters when multiple changes depend on earlier modifications.

For example:

    Insert A
       |
       v
    Insert B
       |
       v
    Insert C
       |
       v
    Rollback C
       |
       v
    Rollback B
       |
       v
    Rollback A

The implementations demonstrate basic insertion rollback and index maintenance.

### 5.4 Important concurrency limitation

The educational transaction engines do not provide full multi-version concurrency control or serializable concurrent execution.

They do not implement:

- Transaction lock managers.
- Deadlock detection.
- Predicate locking.
- Snapshot isolation.
- Serializable conflict detection.
- Complete transaction isolation.

The Java and C++ examples use synchronization or single-threaded execution for selected state operations, not a complete concurrent transaction architecture.

---

## 6. Indexing and Record Retrieval

### 6.1 Why indexes exist

An index provides an alternative access path to table records.

Without an index, finding a specific record may require scanning every page.

With an appropriate index, the database can locate a smaller candidate set.

The Python implementation uses a dictionary-based hash index.

The JavaScript implementation uses `Map`.

The C++ implementation uses `unordered_map`.

The Java implementation uses `HashMap`.

These structures demonstrate direct key lookup rather than implementing a complete disk-resident database B-tree.

### 6.2 Index lookup

The modeled lookup workflow is:

    Search Key
        |
        v
    Index Lookup
        |
        v
    Page Identifier
        |
        v
    Slot Identifier
        |
        v
    Buffer Pool
        |
        v
    Record Retrieval

An index entry identifies the page and record position.

The engine then retrieves the appropriate page through its buffer pool.

### 6.3 Hash indexes and B-tree indexes

These structures have different purposes.

| Property | Hash index | B-tree index |
|---|---|---|
| Equality search | Suitable | Suitable |
| Range search | Not naturally supported | Suitable |
| Ordered traversal | Not naturally supported | Supported |
| Key organization | Hash-based | Ordered |
| Typical use | Equality lookup | Equality and range lookup |

The educational implementations use hash-based indexes because they provide a concise way to demonstrate index-to-page navigation.

PostgreSQL supports several index types, including B-tree, Hash, GIN, GiST, and BRIN.

### 6.4 Index maintenance

An index must remain consistent with its underlying table.

When inserting a record, the engine must register the corresponding index entry.

When rolling back an insertion, the index entry must also be removed.

The implementations include this relationship in their simplified primary-index and hash-index models.

Production index management also requires handling page splits, deletion, concurrent modifications, visibility rules, and index-specific maintenance.

---

## 7. MVCC and Tuple Visibility

Multi-Version Concurrency Control allows database transactions to work with different versions of records.

Instead of immediately replacing every old tuple, an MVCC system can retain multiple tuple versions.

Conceptually:

    Logical Row 101

       Version 1
          |
          v
       Version 2
          |
          v
       Version 3

Transaction metadata determines which version is visible to a particular transaction.

### 7.1 Transaction identifiers

PostgreSQL uses transaction identifiers and tuple metadata to support visibility decisions.

Important tuple concepts include:

- `xmin`: Transaction associated with tuple creation.
- `xmax`: Transaction associated with tuple deletion or replacement.
- Tuple visibility: Whether a particular transaction can observe the version.
- Vacuum: Cleanup of obsolete tuple versions when they are no longer required.

The PostgreSQL implementation includes a `tuple_versions` table for recording simplified MVCC observations.

It also provides a query that identifies possible obsolete versions.

This is an analytical model, not a replacement for PostgreSQL's snapshot visibility rules or vacuum implementation.

### 7.2 MVCC and isolation

Different isolation levels determine how concurrent transactions observe database changes.

| Isolation level | Principal behavior |
|---|---|
| Read Uncommitted | PostgreSQL treats this as Read Committed |
| Read Committed | Each statement obtains an appropriate snapshot |
| Repeatable Read | Maintains a transaction-level snapshot |
| Serializable | Adds serialization conflict detection |

MVCC and locking are complementary mechanisms. MVCC does not eliminate the need for synchronization and locking.

---

## 8. Query Processing and Execution

### 8.1 Query processing stages

A database does not execute SQL simply by reading a table and returning records.

A typical processing pipeline is:

1. Parse the SQL statement.
2. Resolve tables, columns, and functions.
3. Validate types and permissions.
4. Generate candidate execution plans.
5. Estimate execution costs.
6. Select a physical plan.
7. Execute relational operators.
8. Return results.

### 8.2 Logical and physical plans

A logical plan describes the required relational operations.

A physical plan determines how those operations are implemented.

For example, a query requesting employees with salaries above a threshold may have a logical structure:

    Employees
        |
        v
    Filter salary >= 90000
        |
        v
    Project name, department, salary

A physical implementation may use:

- Sequential scan.
- Index scan.
- Bitmap scan.
- Filter.
- Projection.
- Sort.

The same logical query can have different physical plans depending on available indexes, statistics, memory, and estimated data distribution.

### 8.3 Implemented operators

| Operator | Function | Expected complexity |
|---|---|---|
| Table Scan | Reads table records | O(n) |
| Filter | Selects qualifying records | O(n) |
| Projection | Selects requested attributes | O(n × k) |
| Sort | Orders records | O(n log n) |
| Hash Join | Matches records using a hash table | O(n + m) average |
| Hash Aggregate | Groups and aggregates records | O(n) average |

Here, `n` and `m` represent input record counts, while `k` represents the number of projected attributes.

### 8.4 Table scans

A sequential scan visits table pages and examines their records.

It is often efficient when a large proportion of the table must be read.

The Python, JavaScript, C++, and Java implementations expose table-scan operators.

### 8.5 Filtering

Filtering evaluates a predicate against each input record.

For example:

    salary >= 90000

The result contains only records satisfying the condition.

Predicate evaluation is generally linear in the number of records processed.

### 8.6 Projection

Projection reduces the attributes returned by a query.

For example:

    employee_name, department_id, salary

It can reduce intermediate data size and avoid carrying unnecessary attributes through later operations.

The Python and JavaScript implementations validate requested columns before returning projected records.

### 8.7 Hash joins

A hash join combines two relations using equality between join keys.

The algorithm has two phases:

**Build phase**

- Read the build-side relation.
- Calculate hash values.
- Store rows in hash buckets.

**Probe phase**

- Read the other relation.
- Calculate its join-key hash.
- Find matching build-side records.
- Produce joined tuples.

Expected time complexity is O(n + m), assuming suitable hash distribution.

Memory consumption depends on the size of the build-side relation.

The Python and JavaScript implementations provide executable hash-join operators. Their memory requirements make them unsuitable for unbounded inputs without additional partitioning or spill-to-disk mechanisms.

### 8.8 Hash aggregation

Hash aggregation groups rows using a grouping attribute.

For each group, the engine maintains:

- Count.
- Sum.
- Minimum.
- Maximum.
- Average.

Average is derived from sum divided by count.

The implementations demonstrate aggregation by employee department.

---

## 9. Query Optimization and Cost Estimation

Query optimization attempts to identify an efficient physical execution plan.

It uses database statistics and estimated operator costs.

### 9.1 Table scan cost

A simplified table-scan estimate is:

\[
C_{\text{scan}} =
\left\lceil
\frac{N}{R}
\right\rceil
\]

Where:

- \(N\) is the estimated number of rows.
- \(R\) is the number of rows per page.

This approximates the number of pages required for a complete scan.

### 9.2 Index scan cost

The educational models use a simplified estimate:

\[
C_{\text{index}} =
\log_2(\max(2,N))
+
\frac{N}{D}
\]

Where:

- \(N\) is the estimated row count.
- \(D\) is the number of distinct indexed values.

The first term approximates index traversal depth.

The second term estimates matching records under a simplified uniform-distribution assumption.

### 9.3 Access-path selection

The optimizer compares estimated costs.

    Calculate Table Scan Cost
              |
              v
    Calculate Index Scan Cost
              |
              v
       Compare Estimates
              |
       +------+------+
       |             |
    Index Cheaper   Scan Cheaper
       |             |
       v             v
    Index Scan    Table Scan

An index is not automatically faster than a sequential scan.

For a query returning a large proportion of a table, a sequential scan can be more efficient.

### 9.4 Statistics and estimation errors

Database statistics describe the distribution of stored data.

Important measurements include:

- Estimated row count.
- Number of distinct values.
- Null fraction.
- Attribute correlation.
- Value distribution.
- Table size.

Incorrect statistics can cause inaccurate cardinality estimates and poor execution plans.

The PostgreSQL schema records table statistics and plan estimates.

Its cardinality comparison query calculates the ratio between estimated and actual rows.

---

## 10. PostgreSQL Implementation

The PostgreSQL script provides a relational model for observing database behavior.

It uses the `dbinternals` schema to organize monitoring and catalog-related information.

### 10.1 Main entities

| Table | Responsibility |
|---|---|
| database_instances | Database configuration |
| database_tables | Logical table metadata |
| database_columns | Column metadata |
| storage_pages | Physical page observations |
| buffer_pool_observations | Buffer activity |
| database_transactions | Transaction lifecycle |
| wal_observations | WAL event observations |
| tuple_versions | MVCC version observations |
| database_indexes | Index metadata |
| index_observations | Index usage statistics |
| query_executions | Query execution history |
| query_plan_nodes | Physical plan operators |
| table_statistics | Cardinality statistics |
| query_cost_estimates | Access-path cost comparisons |

### 10.2 Integrity mechanisms

The SQL implementation uses:

- Primary keys.
- Foreign keys.
- Unique constraints.
- Check constraints.
- Partial indexes.
- Composite indexes.
- Triggers.
- Stored functions.
- Stored procedures.
- Transactions.
- Views.

These mechanisms enforce data integrity within the observation schema.

### 10.3 Transaction procedures

The `complete_database_transaction` procedure supports terminal transaction-state transitions.

It locks the selected transaction row using `FOR UPDATE`.

It rejects nonexistent transactions and transactions that have already reached a terminal state.

The procedure records a simplified commit or abort observation.

The simulated LSN values are identifiers for demonstration and must not be interpreted as actual PostgreSQL WAL positions.

### 10.4 Query execution analysis

The script includes:

- Buffer hit-ratio calculation.
- Page utilization analysis.
- Dirty-page identification.
- Transaction lifecycle reporting.
- Index usage reporting.
- Query-plan analysis.
- Cardinality-estimation comparison.
- Query workload aggregation.
- MVCC version investigation.
- Execution failure reporting.

It also uses PostgreSQL's `EXPLAIN (ANALYZE, BUFFERS)` to inspect an actual query execution.

This is distinct from the simulated cost functions in the other implementations.

---

## 11. Implementation-Specific Engineering Decisions

### Python

The Python implementation concentrates on database simulation and storage behavior.

| Component | Design |
|---|---|
| Page representation | Dataclass |
| Disk storage | JSON-lines persistence |
| WAL | Append-only records |
| Buffer pool | OrderedDict |
| Replacement | LRU |
| Index | Dictionary |
| Transactions | Undo-action collection |
| Query operators | Iterator-based |
| Aggregation | Hash grouping |
| Cost model | Simplified numerical estimates |

The iterator-based query operators allow intermediate processing without requiring every operator to materialize its complete result.

The hash join and aggregation operators still maintain in-memory structures proportional to their input data.

### JavaScript

The JavaScript implementation emphasizes asynchronous storage operations and event-driven behavior.

| Component | Design |
|---|---|
| Page representation | Class |
| Buffer pool | Map |
| Storage operations | Async methods |
| WAL | Append-only file |
| Transaction state | Explicit state machine |
| Events | EventEmitter |
| Query operators | Operator tree |
| Hash joins | Map-based |
| Aggregation | Map-based |
| Cost model | QueryOptimizer |

Events report important database operations:

- `database:ready`
- `row:inserted`
- `index:created`
- `transaction:committed`
- `transaction:aborted`

This approach separates operational notifications from the code that performs database changes.

The demonstration uses asynchronous file operations but does not implement concurrent transaction isolation.

### C++17

The C++ implementation emphasizes explicit memory structures and predictable storage access.

| Component | Design |
|---|---|
| Page model | Struct |
| Buffer frames | Struct |
| Buffer lookup | unordered_map |
| LRU ordering | list |
| Transaction undo | Vector |
| Index | unordered_map |
| Query operators | Polymorphic classes |
| Aggregation | Hash-based |
| Cost estimation | Numeric model |

The buffer pool separates page lookup from recency ordering.

This allows efficient lookup and replacement without scanning the complete buffer collection.

`unique_ptr` manages query-operator ownership and avoids manual memory management for the query tree.

### Java 17

The Java implementation emphasizes enterprise domain modeling.

| Component | Design |
|---|---|
| Employee | Immutable record |
| Transaction state | Enum |
| Page | Encapsulated class |
| WAL | Typed log records |
| Buffer pool | LinkedHashMap |
| Storage | DiskManager abstraction |
| Transactions | Dedicated service objects |
| Query operators | Interface-based |
| Aggregation | Streams and collectors |
| Validation | Constructors and exceptions |

Immutable employee records reduce accidental modification of stored domain values.

The `QueryOperator` interface separates execution behavior from individual operator implementations.

The model uses synchronized operations for selected shared structures, but does not implement a complete concurrent transaction manager.

---

## 12. Failure Handling and Data Integrity

Database systems must handle invalid input, missing pages, transaction failures, and inconsistent storage state.

The implementations include several failure scenarios.

| Failure | Expected handling |
|---|---|
| Invalid table identifier | Reject operation |
| Invalid employee record | Validation exception |
| Duplicate indexed value | Constraint violation |
| Missing page | Storage exception |
| Stale index entry | Reject retrieval |
| Inactive transaction | Transaction exception |
| Buffer eviction of dirty page | Flush WAL before page write |
| Transaction rollback | Reverse registered changes |
| Invalid projection column | Query execution error |
| Invalid aggregate input | Reject nonnumeric values |
| Page checksum mismatch | Storage failure |

### Important integrity distinction

A successful transaction operation does not automatically establish complete database durability.

Production durability requires a correct interaction among:

- WAL persistence.
- Commit processing.
- Data-page flushing.
- Checkpointing.
- Crash recovery.
- Storage-device guarantees.

The educational implementations demonstrate the ordering principle but do not provide a production recovery system.

---

## 13. Performance Considerations

Database performance depends on the complete execution path rather than a single component.

### 13.1 Memory and disk behavior

A workload with repeated access to the same pages may benefit from a larger buffer pool.

A sequential workload may produce many page reads even when the buffer pool is functioning correctly.

A high cache hit ratio does not necessarily mean that a query is efficient. A query may still perform excessive CPU work or return too many records.

### 13.2 Index selection

Indexes reduce the work required for selective lookups but require additional storage and maintenance.

An index can increase the cost of:

- Inserts.
- Updates.
- Deletes.
- Vacuum operations.
- Storage management.

Index selection must consider query patterns and data distribution.

### 13.3 Sorting and aggregation

Sorting requires O(n log n) comparison work in the usual comparison-based model.

Hash aggregation generally requires O(n) expected processing time but uses memory proportional to the number of groups.

Large operations may exceed available memory.

Production systems therefore implement temporary-file spilling and memory-aware execution strategies.

### 13.4 Query planning

Accurate cardinality estimates are important because they influence:

- Join order.
- Join algorithm.
- Index selection.
- Aggregation strategy.
- Sorting decisions.
- Parallel execution choices.

The simple cost formulas in this project illustrate access-path comparison. They are not substitutes for a production optimizer's cost model.

---

## 14. Security and Operational Considerations

Database internals are directly relevant to security and operational reliability.

Important considerations include:

- Validate identifiers separately from SQL values.
- Use parameterized queries for application-supplied values.
- Apply least-privilege database permissions.
- Protect database files and WAL files.
- Restrict access to transaction and execution metadata.
- Avoid logging passwords, tokens, and sensitive record contents.
- Validate checksums and detect storage corruption.
- Protect backup and recovery procedures.
- Monitor long-running transactions.
- Monitor abnormal temporary-file growth.
- Review index and query execution behavior.
- Control access to administrative functions.

The Python and JavaScript examples use local files with basic access restrictions where applicable. The C++ and Java examples use in-memory storage.

None of these educational applications provides production-grade authentication, authorization, encryption at rest, network security, or backup management.

---

## 15. Execution

### Python

Requirements:

- Python 3.10 or later.
- Standard library only.

Run the script directly with Python.

The program creates a temporary database directory, performs inserts, creates an index, executes queries, verifies rollback, and checks persistence.

### JavaScript

Requirements:

- Node.js 18 or later.
- Standard library only.

Run the JavaScript file with Node.js.

The demonstration creates a local database directory named `database_internals_demo`.

It maintains a page file and an append-only WAL file.

### C++17

Requirements:

- A C++17-compatible compiler.

Compile using the C++17 language standard.

The program runs its storage, transaction, query, and cost-estimation demonstrations without external libraries.

### Java 17

Requirements:

- JDK 17.

Compile the standalone Java source file and run the `DatabaseInternals` class.

The program uses only Java standard-library facilities.

### PostgreSQL

Requirements:

- PostgreSQL 15 or later.
- Permission to create schemas, tables, functions, triggers, and procedures.

Execute the complete SQL script against a database where the executing role has the required permissions.

The script creates its own `dbinternals` schema and demonstrates operational queries against PostgreSQL.

---

## 16. Verification Scenarios

The following scenarios are covered by the implementations.

| Scenario | Expected result |
|---|---|
| Insert valid employee records | Records become available for retrieval |
| Retrieve an existing employee | Correct indexed record is returned |
| Retrieve a missing employee | No matching record |
| Insert duplicate indexed key | Constraint failure |
| Commit transaction | Transaction enters COMMITTED state |
| Roll back insertion | Inserted record is removed |
| Scan employee table | All committed demonstration records are returned |
| Filter salaries | Only qualifying records remain |
| Sort employees | Records appear in descending salary order |
| Group by department | Department-level statistics are calculated |
| Compare scan and index cost | Lower estimated cost is selected |
| Evict a dirty page | WAL is flushed before the page |
| Corrupt persisted page | Checksum validation rejects the page |
| Record failed query | Failure appears in execution reporting |

The PostgreSQL implementation also demonstrates relational joins, CTEs, window functions, aggregation, execution-plan inspection, and integrity constraints.

---

## 17. Limitations and Technical Scope

This project is a collection of educational database models rather than a replacement relational database.

Several production mechanisms are intentionally outside its scope.

| Mechanism | Project coverage |
|---|---|
| Heap pages | Simplified implementation |
| Buffer pool | LRU simulation |
| Dirty-page management | Simplified |
| WAL | Append-only educational log |
| Crash recovery | Not fully implemented |
| Transactions | Basic commit and undo |
| MVCC | Observational SQL model |
| Isolation | Not fully implemented |
| Hash indexing | Implemented |
| B-tree indexing | Discussed and represented in PostgreSQL metadata |
| Query planning | Simplified cost model |
| Sequential scan | Implemented |
| Filtering | Implemented |
| Projection | Implemented |
| Sorting | Implemented |
| Hash join | Implemented in Python and JavaScript |
| Hash aggregation | Implemented |
| Concurrent execution | Limited |
| Parallel query processing | Not implemented |
| Production security | Not implemented |

The most important architectural distinction is between a conceptual simulation and a production database implementation.

A real database must coordinate storage, memory, transaction visibility, recovery, concurrency, and query execution under concurrent workloads and failures.

The project models selected mechanisms independently so that their responsibilities, interactions, costs, and failure conditions can be examined.

## 18. Core Technical Relationships

The following relationships summarize the architecture:

| Mechanism | Depends on | Main purpose |
|---|---|---|
| Heap storage | Page management | Organizes tuples |
| Buffer pool | Storage manager | Reduces repeated disk reads |
| Dirty-page flushing | Buffer manager and WAL | Preserves write ordering |
| WAL | Transaction manager and storage | Supports recovery |
| Transaction rollback | Undo information | Reverses uncommitted changes |
| MVCC | Transaction metadata | Determines tuple visibility |
| Indexing | Table and page organization | Reduces retrieval work |
| Query optimization | Statistics and cost estimates | Selects execution plans |
| Query execution | Physical operators | Produces relational results |
| Monitoring | Execution and storage metadata | Identifies performance behavior |

Understanding these dependencies is essential when examining a database from its physical storage structures through its final query results.
