# Database Internals Overview

## Scope

This project models three tightly connected parts of a relational database engine:

1. Query engine
2. Storage engine
3. Buffer manager

The implementations use the same conceptual database workload while taking different engineering approaches in Python, JavaScript, C++17, Java 17, and PostgreSQL.

The central relationship is:

    SQL request
        |
        v
    Query Engine
        |
        +----------------------+
        |                      |
        v                      v
    Index Access          Sequential Scan
        |                      |
        +----------+-----------+
                   |
                   v
              Buffer Manager
                   |
                   v
              Storage Engine
                   |
                   v
              Database Pages
                   |
                   v
               Persistent Storage

The query engine decides how data should be located. The buffer manager controls which pages are resident in memory. The storage engine owns the representation and persistence of those pages.

## Technical Model

A database does not normally treat every row as an independent operating-system file operation. Data is organized into pages or blocks. A query causes the engine to locate relevant pages, obtain them through the buffer manager, and inspect records or index structures.

The project models the following flow:

    Record
      |
      v
    Heap Page
      |
      v
    Disk Manager
      |
      +----> Buffer Pool
                 |
                 +----> Cache hit
                 |
                 +----> Cache miss
                          |
                          v
                       Disk Read

A modified resident page becomes dirty. Before that page can safely be discarded, its contents must be written back to durable storage.

## Storage Engine

The storage engine is responsible for the physical organization of database data.

The Python, JavaScript, C++17, and Java implementations use heap-style pages. Records are inserted into available pages until the configured page capacity is reached. A new page is then allocated.

A simplified physical structure is:

    Heap File
    |
    +-- Page 1
    |    +-- Row 1
    |    +-- Row 2
    |    +-- Row 3
    |
    +-- Page 2
         +-- Row 4
         +-- Row 5
         +-- Row 6

Each implementation also maintains a row locator. The locator maps a logical row identifier to the page containing that row.

This avoids scanning every page when the system already knows the physical location of a specific row.

### Python storage implementation

The Python implementation uses `DiskManager`, `Page`, and `HeapTable`.

`DiskManager` stores pages in a JSON-backed representation and provides page allocation, reading, writing, and persistence.

`Page` contains records, a page type, a dirty flag, and a log sequence number.

`HeapTable` maintains `page_ids` and a `row_locator`. Inserts search existing pages for free capacity before allocating another page.

The implementation uses deep copies when pages cross the storage boundary. This models the distinction between a persistent page representation and a mutable in-memory buffer frame.

### JavaScript storage implementation

The JavaScript implementation uses asynchronous filesystem APIs. `DiskManager.readPage()` returns a promise and introduces a small asynchronous delay to make the disk boundary explicit.

`Page` is a mutable object. `HeapTable` maintains a `Map` for row-to-page location.

The storage representation is serialized as JSON. Temporary-file replacement is used during persistence so that a write does not directly overwrite the main database file before the new representation has been prepared.

### C++17 storage implementation

The C++ implementation separates `Page`, `DiskManager`, and `HeapTable`.

`Page` owns a vector of records. `DiskManager` owns persistent page objects and returns copies when pages are read.

The explicit ownership model illustrates an important storage-engine boundary: a buffer frame can be changed without directly modifying the persistent representation until a flush occurs.

### Java 17 storage implementation

The Java implementation uses the `PageStore` interface to separate storage behavior from higher-level database logic.

`InMemoryDisk` implements the interface, while `RepositoryTable` depends on the abstraction rather than a concrete storage class.

This design allows the storage mechanism to be replaced without changing the query or transaction services.

## Page Organization

A page has a finite capacity. The examples intentionally use a small capacity so that page allocation and buffer replacement occur frequently.

A page contains:

| Attribute | Purpose |
|---|---|
| Page identifier | Uniquely identifies the physical page |
| Page type | Distinguishes heap and index pages |
| Records | Stored logical rows |
| Dirty state | Indicates that memory contains modifications |
| LSN | Identifies the latest associated log record |

A dirty page is different from a modified logical row.

The row change happens at the logical data level. The dirty flag records the physical consequence that the in-memory page no longer exactly matches its durable representation.

## Buffer Manager

The buffer manager sits between query execution and storage.

Its main responsibility is to reduce expensive storage reads by keeping recently used pages in memory.

The project models an LRU policy:

    Most recently used
             |
             v
    [Page C] [Page A] [Page B]
                         ^
                         |
                  Least recently used

When a new page is needed and the buffer pool is full, the least recently used page becomes the eviction candidate.

If the candidate is clean, it can be discarded.

If it is dirty, it must first be written to storage.

## Buffer Pool Mechanics

The implementations track:

- buffer hits
- buffer misses
- evictions
- dirty-page writes
- hit rate

The hit rate is calculated as:

    hits / (hits + misses)

A high hit rate means the working set is fitting effectively within the available buffer pool.

A low hit rate can indicate that:

- the working set is larger than memory capacity
- the access pattern has poor locality
- the replacement policy is unsuitable
- queries repeatedly revisit pages after eviction

The metric is useful only in relation to a specific workload. A high hit rate does not automatically mean that the query plan is optimal.

## Python Buffer Manager

Python uses `OrderedDict` to implement LRU behavior.

The first entry represents the least recently used frame and the last entry represents the most recently used frame.

Fetching an existing page moves it to the end of the structure. Fetching a missing page may cause eviction.

Dirty pages are written through `DiskManager.write_page()` before eviction.

## JavaScript Buffer Manager

JavaScript uses `Map` insertion order to implement the LRU queue.

A cache hit removes and reinserts the page, moving it to the most-recent position.

The buffer manager also extends `EventEmitter`. Buffer misses and page flushes emit events that provide operational visibility without coupling logging directly into the storage algorithm.

This is useful for an event-driven runtime because instrumentation can observe the engine without changing the query interface.

## C++17 Buffer Manager

C++17 uses:

- `unordered_map` for page lookup
- `list` for LRU ordering

The hash map provides fast page lookup, while the linked list allows an entry to be removed and repositioned without shifting an array.

The implementation explicitly checks for inconsistent LRU metadata and throws an exception rather than silently continuing with corrupted cache state.

## Java 17 Buffer Manager

Java uses an access-ordered `LinkedHashMap`.

This gives the implementation a compact representation of LRU state. Every successful lookup changes the access order automatically.

The buffer manager also tracks write operations and exposes a formatted statistics report.

## Query Engine

The query engine determines how a logical request is executed.

Two access paths are implemented:

- sequential heap scan
- indexed lookup

The distinction is important because both can return identical logical results while having very different physical costs.

### Sequential Scan

A sequential scan reads pages in storage order and evaluates each row against the predicate.

For a predicate such as:

    customer_id = 101

the engine performs:

    Page 1 -> inspect rows
    Page 2 -> inspect rows
    Page 3 -> inspect rows
    ...

This is appropriate when:

- a large fraction of rows qualifies
- no useful index exists
- the table is small
- sequential locality is favorable

The cost is related to the number of pages that must be examined.

### Indexed Lookup

The indexed path first resolves the search key through an index.

The conceptual flow is:

    customer_id = 101
            |
            v
       Index lookup
            |
            v
       Page identifiers
            |
            v
       Buffer manager
            |
            v
       Matching records

The project uses a compact ordered index representation rather than implementing a production B-tree with page splits and multi-level node management.

The index maps customer identifiers to pages containing matching records.

The important database concept is the change in access path, not the simulation of every physical B-tree operation.

## Index Versus Heap Scan

The two approaches are deliberately verified against each other.

The implementations compare row identifiers returned by the indexed and sequential paths.

If the sets differ, the engine raises an error.

This is important because an index is an acceleration structure. It must not change query semantics.

A useful invariant is:

    Result(indexed predicate)
        =
    Result(sequential predicate)

for the same committed database state.

## Query Cost

For a sequential scan, the approximate page-level cost is:

    O(number of pages scanned)

For a simple ordered index lookup, the conceptual lookup cost is approximately:

    O(log N + matching entries)

where `N` represents indexed entries.

The actual cost depends on:

- index height
- page density
- selectivity
- clustering
- buffer residency
- random versus sequential I/O
- number of matching rows

An index can be slower than a sequential scan when the predicate matches a large proportion of the table.

## Query Planning

A production query optimizer has many responsibilities that are outside the scope of these compact implementations.

A full optimizer may consider:

- relation cardinality
- predicate selectivity
- available indexes
- join algorithms
- sort costs
- aggregation costs
- memory limits
- disk I/O
- statistics
- parallel execution

The examples isolate the physical distinction between sequential and indexed access so that storage and buffer effects remain visible.

## Transaction State

The Python, JavaScript, C++17, and Java implementations include transaction-style update behavior.

The explicit transaction states are:

    ACTIVE
       |
       +----> COMMITTED
       |
       +----> ROLLED_BACK

An active transaction can perform updates.

A committed transaction makes its modifications durable through buffer flushing.

A rolled-back transaction restores earlier values recorded before the transaction changes.

The model is intentionally smaller than a full MVCC database. It demonstrates the relationship between logical updates, dirty pages, write logging, and persistence.

## Write-Ahead Logging

The implementations include a simplified WAL model.

A log entry records information such as:

| Field | Purpose |
|---|---|
| LSN | Ordering identifier |
| Transaction ID | Identifies the modifying transaction |
| Page ID | Identifies affected storage |
| Row ID | Identifies the logical row |
| Old value | Supports rollback |
| New value | Describes the update |

The fundamental WAL principle is that recovery information must be recorded before the corresponding dirty data page is considered safely durable.

The implementations do not attempt to reproduce PostgreSQL's complete WAL and crash-recovery subsystem. They expose the dependency between log ordering and dirty-page flushing.

## Dirty Pages

A page becomes dirty when its in-memory representation differs from durable storage.

Example:

    Disk:
    balance = 1250

    Buffer:
    balance = 1750
    dirty = true

The buffer manager cannot simply discard the buffer copy because doing so would lose the update.

The correct sequence is:

    Update
      |
      v
    Dirty page
      |
      v
    WAL record
      |
      v
    Flush
      |
      v
    Durable page
      |
      v
    Dirty state cleared

## PostgreSQL Storage Model

The PostgreSQL script represents database internals relationally rather than attempting to reproduce PostgreSQL's own internal storage engine.

The schema contains:

- `repositories`
- `branches`
- `commits`
- `database_pages`
- `repository_rows`
- `engine_transactions`
- `write_ahead_log`
- `buffer_frames`
- `index_entries`
- `pull_requests`
- `status_checks`

The repository and pull-request tables provide a realistic application context while the page, transaction, WAL, and buffer tables model the database-engine concepts.

## PostgreSQL Constraints

The database uses:

- primary keys
- foreign keys
- unique constraints
- check constraints
- enumerated types
- indexes
- triggers
- views
- functions
- procedures

Examples include:

`customer_id > 0`

ensures that customer identifiers are valid.

`balance BETWEEN -10000000 AND 10000000`

prevents unrealistic values from entering the storage model.

Foreign keys ensure that page references and transaction references cannot silently point to nonexistent objects.

## PostgreSQL Page Model

`database_pages` records the physical page abstraction used by the learning model.

Important fields include:

| Field | Meaning |
|---|---|
| `page_id` | Physical page identifier |
| `repository_id` | Owning database context |
| `page_type` | Heap or index |
| `page_number` | Logical position |
| `page_lsn` | Latest associated log sequence number |
| `is_dirty` | Indicates modified in-memory state |

`repository_rows.page_id` links logical records to their storage page.

This makes the physical relationship queryable through SQL.

## PostgreSQL Buffer Frames

`buffer_frames` represents pages currently resident in the buffer pool.

It records:

- page identity
- pin count
- dirty state
- last access time

The `last_accessed_at` column supports an LRU-style reporting model.

A real database buffer manager has considerably more state, including concurrency controls, pinning rules, replacement decisions, and synchronization mechanisms.

The relational model intentionally focuses on the core relationship between residency, modification, and access recency.

## PostgreSQL WAL Model

`write_ahead_log` records modifications before the corresponding page is considered clean.

The `update_customer_balance()` function:

1. validates the requested balance
2. verifies that the transaction is active
3. locks the target row
4. reads the old balance
5. creates a WAL record
6. updates the row
7. marks the associated page dirty
8. records the WAL sequence number on the page

This demonstrates the dependency between logical modification and physical persistence state.

## PostgreSQL Transaction Workflow

The transaction lifecycle is represented by `engine_transactions`.

An active transaction can update data.

The `finish_engine_transaction()` procedure changes an active transaction to a terminal state and records its completion timestamp.

The schema prevents an active transaction from having a completion timestamp and requires completed transactions to have one.

This constraint turns a workflow rule into a database-level invariant.

## Failure Handling

The implementations deliberately exercise failure conditions.

Examples include:

- duplicate row identifiers
- missing pages
- invalid customer identifiers
- invalid balances
- full pages
- inactive transactions
- inconsistent row locators
- rollback of missing records
- buffer metadata inconsistencies

These cases matter because database engines must preserve invariants when operations fail.

A storage engine that works only on successful execution is not sufficient. The failure path is part of the design.

## Data Integrity Invariants

The implementations enforce several important invariants.

### Row identity

A row identifier must be unique.

### Page location

Every known row must map to a valid page.

### Page capacity

A page cannot exceed its configured record capacity.

### Dirty state

A modified page must remain marked dirty until its contents are flushed.

### Transaction state

A completed transaction cannot accept further changes.

### Query consistency

Sequential and indexed access must return equivalent logical rows for the same committed state.

### Persistent state

A flushed page must represent the durable version of the in-memory page.

## Security Considerations

Database internals have security implications even when the examples are local simulations.

Important controls include:

- validate numeric ranges before persistence
- reject malformed identifiers
- enforce referential integrity
- avoid trusting page identifiers supplied by clients
- separate logical row identifiers from physical storage locations
- restrict transaction state transitions
- protect WAL data from unauthorized modification
- prevent path manipulation when using file-backed storage
- use parameterized SQL for application-generated PostgreSQL statements
- avoid exposing internal page metadata to untrusted clients

The PostgreSQL model uses constraints and server-side functions to move important validation into the database boundary.

## Performance Considerations

The main performance mechanisms represented in the project are page locality, indexing, and buffering.

A sequential scan benefits from contiguous access and can be efficient for large result sets.

An index can reduce the number of pages inspected for selective predicates.

The buffer pool reduces repeated storage reads when the working set fits within memory.

Performance therefore depends on the combined system:

    Query Plan
        +
    Index Selectivity
        +
    Page Layout
        +
    Buffer Residency
        +
    Storage Latency

Changing only one layer may not improve the complete workload.

## Complexity

| Operation | Conceptual cost |
|---|---|
| Row locator lookup | O(1) average |
| Sequential table scan | O(P) pages |
| Ordered index lookup | O(log N + K) |
| LRU buffer lookup | O(1) average |
| LRU eviction | O(1) with explicit ordering structure |
| Heap insertion | O(P) in the simple demonstration |
| Transaction rollback | O(C), where C is number of changes |

`P` represents pages examined, `N` represents indexed entries, and `K` represents matching index entries.

The simple heap insertion algorithm searches for a page with capacity. A production engine would maintain free-space information to avoid repeatedly examining pages.

## Python, JavaScript, C++17, Java 17, and PostgreSQL Comparison

| Implementation | Main perspective | Important mechanism |
|---|---|---|
| Python | Database simulation | Dataclasses, ordered buffer pool, heap storage, WAL model |
| JavaScript | Event-driven engine | Promises, `Map` LRU behavior, events, asynchronous storage |
| C++17 | Systems-oriented engine | Explicit ownership, STL containers, LRU list, exception handling |
| Java 17 | Enterprise domain model | Records, interfaces, services, explicit transaction states |
| PostgreSQL | Relational engine model | Constraints, triggers, functions, procedures, indexes, CTEs |

The implementations are deliberately not line-for-line translations.

Python emphasizes compact modeling and executable experimentation.

JavaScript exposes asynchronous and event-driven behavior.

C++17 emphasizes explicit systems-level structures and ownership.

Java 17 separates domain abstractions through interfaces, records, and service classes.

PostgreSQL moves validation and workflow rules into relational constraints and server-side execution.

## Storage Engine, Buffer Manager, and Query Engine Relationship

These components solve different problems.

### Storage Engine

Answers:

> Where and how is data physically represented?

It manages pages, records, allocation, reads, writes, and durable representation.

### Buffer Manager

Answers:

> Which storage pages should currently reside in memory?

It manages page residency, replacement, dirty state, and flushing.

### Query Engine

Answers:

> Which data should be accessed, and through which access path?

It performs scans, index lookups, filtering, and execution planning.

They interact but should not be treated as interchangeable.

    Query Engine
        |
        | requests page
        v
    Buffer Manager
        |
        | cache miss
        v
    Storage Engine
        |
        v
    Persistent Storage

A query engine should not need to know the details of disk-file layout. The buffer manager should not decide the logical meaning of a SQL predicate. The storage engine should not decide whether a query should use an index.

## Practical Failure Scenarios

### Buffer pool too small

If the working set exceeds buffer capacity, pages can repeatedly enter and leave the pool.

This increases storage traffic and lowers the hit rate.

### Dirty page eviction

Evicting a dirty page without flushing it loses committed or otherwise durable work.

The implementations therefore write dirty pages before eviction.

### Stale index

If an index is not updated when underlying data changes, an indexed query can return incorrect results.

The examples rebuild the compact index after loading data rather than implementing a full incremental index-maintenance subsystem.

### Invalid locator

If a row locator points to a page that no longer contains the row, the engine treats the condition as corruption instead of silently returning incorrect data.

### Rollback failure

Rollback must process changes in reverse order so that multiple modifications to the same row can restore the earliest state correctly.

## Scope and Limitations

The implementations are technical learning models rather than production database engines.

They do not attempt to implement:

- full SQL parsing
- a complete cost-based optimizer
- physical B-tree node splitting
- MVCC snapshots
- lock managers
- deadlock detection
- crash recovery
- replication
- parallel query execution
- compression
- sophisticated free-space management
- checkpoint processing
- distributed transactions

The PostgreSQL script also does not replace PostgreSQL's internal buffer manager or storage engine. Its tables provide a relational model for reasoning about those mechanisms.

## Concrete Execution Workflow

The five implementations follow a common conceptual workload:

    1. Create repository/database context
            |
            v
    2. Allocate heap pages
            |
            v
    3. Insert records
            |
            v
    4. Build customer index
            |
            v
    5. Execute sequential lookup
            |
            v
    6. Execute indexed lookup
            |
            v
    7. Compare logical results
            |
            v
    8. Update records
            |
            v
    9. Mark pages dirty
            |
            v
   10. Record WAL-style information
            |
            v
   11. Commit or roll back
            |
            v
   12. Flush persistent state
            |
            v
   13. Inspect buffer and storage metrics

This workflow connects logical query processing with the physical page and memory-management mechanisms that support it.

## Repository and Commit Context

The relational schema includes repositories, branches, commits, pull requests, and status checks because database internals are commonly encountered inside repository-backed software systems.

These entities are separate from the storage-engine model.

The database-engine entities explain how data is stored and accessed.

The repository entities provide an application context in which those mechanisms can operate.

The distinction prevents application-level objects from being confused with physical database pages.

## Important Distinctions

| Concept | Meaning |
|---|---|
| Row | Logical application data |
| Page | Physical unit of storage management |
| Buffer frame | In-memory residency of a page |
| Heap scan | Sequential physical access path |
| Index lookup | Indirect access path through an index |
| Dirty page | Modified in-memory page not yet flushed |
| WAL record | Recovery-oriented record of a modification |
| Transaction | Unit of logical state change |
| Query plan | Strategy used to obtain query results |
| Storage engine | Component managing physical persistence |
| Buffer manager | Component managing memory residency |
| Query engine | Component executing logical requests |

These distinctions are central to understanding why database internals are layered rather than implemented as one monolithic operation.

## File Roles

| File | Role |
|---|---|
| Python source | Page-oriented database simulation with JSON persistence and LRU buffering |
| JavaScript source | Asynchronous, event-driven storage and buffer model |
| C++17 source | Systems-oriented repository database engine with explicit LRU structures |
| Java 17 source | Enterprise-style domain and service model |
| PostgreSQL script | Relational representation with database-enforced integrity and workflow rules |
| README.md | Technical description of the shared database-internals model |

The implementations share the same conceptual workload but use language-specific mechanisms to expose different aspects of query execution, storage, buffering, indexing, transactions, and persistence.
