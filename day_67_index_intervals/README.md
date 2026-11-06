# Index Internals: B-Trees, Tree Traversal, and Index Pages

## 1. Technical Scope

A database index is an auxiliary data structure that reduces the amount of table data examined during query execution. An index stores searchable key information and references that allow the database engine to locate corresponding table records.

This project examines three connected aspects of database indexing:

1. **B-trees and B+ trees:** Hierarchical structures that maintain sorted keys and support efficient search, insertion, and deletion.
2. **Tree traversal:** Navigation through internal pages and leaf pages to locate individual keys or retrieve ordered ranges.
3. **Index pages:** Fixed-size or managed storage units containing index keys, record references, and child-page references.

The implementations use a B+ tree as the principal educational data structure. PostgreSQL demonstrations examine the actual database index implementation through system catalogs, execution plans, and optional physical-page inspection.

## 2. B-Tree and B+ Tree Structures

### B-tree

A B-tree is a balanced multiway search tree. Unlike a binary search tree, a B-tree node can contain multiple keys and multiple child pointers.

Its principal characteristics are:

- Keys are maintained in sorted order.
- Internal nodes direct searches toward the appropriate subtree.
- Leaf-level records or references are maintained at the bottom of the tree.
- Nodes have minimum and maximum occupancy requirements.
- Splitting and merging preserve balance.
- All leaves remain at the same depth.

A B-tree reduces tree height by storing multiple keys per node. This is useful when accessing persistent storage because each page access can retrieve multiple search keys.

### B+ tree

A B+ tree separates navigation information from the indexed data entries.

Its internal pages contain separator keys and child-page references. Leaf pages contain sorted keys and their associated values or record references.

Leaf pages are linked sequentially.

This design supports both point lookups and range queries.

The distinction is important:

| Property | B-tree | B+ tree |
|---|---|---|
| Internal pages | Search keys and data references may coexist | Separator keys and child pointers |
| Leaf pages | Data entries | Data entries or record references |
| Sequential leaf links | Implementation-dependent | Commonly maintained |
| Range retrieval | Supported | Particularly efficient |
| Internal fan-out | Depends on page representation | Often higher because internal pages store navigation information |

The Python, JavaScript, C++17, and Java 17 programs implement B+ tree structures rather than claiming to reproduce every feature of a production database's B-tree implementation.

## 3. B+ Tree Page Organization

The tree contains two primary page types.

### Internal pages

An internal page contains:

- Sorted separator keys.
- Child-page references.
- A parent relationship in the educational implementations.

For a page containing `n` separator keys, there are normally `n + 1` child pointers.

Consider the following conceptual structure:

        Internal Page
          [30 | 60]
          /    |    \
         /     |     \
        /      |      \
     Leaf    Leaf     Leaf
    [10,20] [30,40] [60,70,80]

A search for key `45` follows the middle child because it belongs to the range beginning at separator `30` and ending before separator `60`.

A search for key `60` follows the right child because separator equality is routed to the right subtree.

### Leaf pages

Leaf pages contain:

- Sorted indexed keys.
- Associated values or record references.
- A pointer to the next leaf page.

For example:

    Leaf 1: [10, 20] -> Leaf 2
    Leaf 2: [30, 40] -> Leaf 3
    Leaf 3: [60, 70, 80] -> NULL

A range query from `20` through `70` locates the first matching leaf and follows the leaf chain until it encounters a key greater than the upper boundary.

This avoids repeatedly traversing the internal tree for each matching record.

### Page occupancy

The implementations define the maximum number of leaf keys as:

`order - 1`

The maximum number of internal children is:

`order`

For an order of five:

| Property | Capacity |
|---|---:|
| Maximum internal children | 5 |
| Maximum internal separator keys | 4 |
| Maximum leaf keys | 4 |

Minimum occupancy depends on the page type and tree-order convention.

The implementations enforce minimum occupancy after deletion through borrowing and merging.

## 4. Search and Tree Traversal

### Point search

Point search starts at the root.

The algorithm:

1. Reads the current internal page.
2. Compares the requested key with separator keys.
3. Selects the appropriate child.
4. Repeats until reaching a leaf.
5. Performs a binary search inside the leaf.
6. Returns the associated value when the key exists.

For a balanced tree with fan-out `m`, the tree height is approximately:

\[
O(\log_m n)
\]

Searching within a page requires approximately:

\[
O(\log m)
\]

comparisons when binary search is used.

The Python and Java implementations use binary search to locate keys and child positions. JavaScript and C++ also use binary-search-based navigation.

### Breadth-first traversal

Breadth-first traversal visits pages level by level.

The JavaScript and C++ implementations expose page-oriented traversal reports.

This is useful for examining:

- Tree height.
- Page distribution.
- Internal versus leaf page counts.
- Child relationships.
- Separator-key placement.

### Depth-first traversal

Depth-first traversal explores a child subtree before moving to the next sibling.

The JavaScript implementation exposes this traversal through `depthFirst()`.

This provides a structural view of the hierarchy rather than only the sorted record sequence.

### Leaf traversal

Leaf traversal begins at the leftmost leaf and follows sequential leaf pointers.

The result is a sorted sequence of all indexed keys.

Its complexity is:

\[
O(n)
\]

This traversal is particularly useful for ordered scans and integrity verification.

## 5. Insertions and Page Splitting

When a new key is inserted:

1. The tree locates the destination leaf.
2. The key is inserted in sorted order.
3. Duplicate keys are rejected.
4. The leaf occupancy is checked.
5. An overflowing leaf is split.
6. A new right sibling is created.
7. A separator key is incorporated into the parent.
8. Parent pages are split recursively when necessary.

A leaf split redistributes existing entries between two pages.

For example:

    Before:
    [10, 20, 30, 40, 50]

    After:
    [10, 20] -> [30, 40, 50]

The first key of the right page becomes the parent separator.

If the original leaf was the root, a new internal root is created.

Internal page splitting follows the same structural principle, but distributes child pointers rather than leaf values.

Splitting preserves the balance of the tree and prevents individual pages from exceeding their capacity.

## 6. Deletions, Borrowing, and Merging

Deleting an indexed key can cause a page to fall below its minimum occupancy.

Three maintenance operations are relevant.

### Borrowing from a sibling

When a neighboring page has more than its minimum occupancy, an entry or child pointer can be transferred.

The parent separator keys are then recalculated.

### Merging pages

When neither sibling can lend an entry, adjacent pages are merged.

For leaf pages, their entries are combined and the leaf-chain pointer is updated.

For internal pages, their child pointers are combined and parent relationships are repaired.

### Root contraction

When an internal root is left with one child, the child becomes the new root.

The tree height decreases by one.

These operations preserve:

- Sorted key order.
- Parent-child relationships.
- Separator-key correctness.
- Minimum page occupancy.
- Sequential leaf traversal.

The four in-memory implementations include deletion and rebalancing operations.

## 7. Index Pages and Physical Storage

A database index is not simply a collection of objects in application memory.

Production database engines store index structures in managed storage pages.

A physical index page may contain:

- Page headers.
- Index tuples.
- Item identifiers.
- Free-space information.
- Special-purpose metadata.
- Links or structural information required by the access method.

The actual layout depends on the database engine and its storage implementation.

### PostgreSQL B-tree pages

PostgreSQL uses a B-tree access method for its standard B-tree indexes.

Relevant PostgreSQL structures include:

| Structure | Purpose |
|---|---|
| `pg_class` | Relation metadata |
| `pg_index` | Index definitions and validity information |
| `pg_am` | Index access methods |
| `pg_indexes` | Human-readable index definitions |
| `pg_stat_user_indexes` | Index usage statistics |
| `pg_class.relpages` | Estimated relation page count |
| `pg_relation_size()` | Physical relation size |

The SQL implementation uses these catalogs to inspect index metadata and physical relation sizes.

The optional `pageinspect` extension exposes lower-level page information.

Its functions include:

- `bt_metap()` for B-tree metadata.
- `bt_page_stats()` for page-level statistics.
- `bt_page_items()` for inspecting individual index-page items.

Physical-page interpretation is implementation-specific. Page numbers and internal structures must be interpreted using the relevant PostgreSQL version and index metadata.

## 8. Buffer Pool and Page Caching

Database systems use shared memory and caching mechanisms to avoid unnecessary physical disk reads.

A buffer pool stores database pages in memory.

When a query requests a page:

1. The buffer manager checks whether the page is already cached.
2. A cache hit allows the page to be reused.
3. A cache miss requires the page to be loaded.
4. If the buffer pool has no free slot, a replacement policy identifies a page for eviction.

The Python, JavaScript, C++17, and Java implementations include simplified LRU buffer-pool simulations.

LRU means Least Recently Used.

The least recently accessed page is removed when the cache reaches its capacity.

The following measurements are recorded:

- Hits.
- Misses.
- Evictions.
- Hit ratio.

The hit ratio is:

\[
\text{Hit Ratio}
=
\frac{\text{Cache Hits}}
{\text{Cache Hits}+\text{Cache Misses}}
\]

These simulations illustrate replacement behavior. They do not implement PostgreSQL's actual buffer manager, dirty-page handling, WAL coordination, concurrency control, or background writing.

## 9. Index Selection and Query Execution

An index does not guarantee that every query uses it.

The database query planner evaluates available access paths and estimates their costs.

Relevant considerations include:

- Table size.
- Estimated matching rows.
- Selectivity.
- Index height.
- Page access cost.
- Sequential scan cost.
- Data distribution.
- Cache conditions.
- Sort requirements.
- Visibility information.

### Composite indexes

The PostgreSQL implementation defines:

`(customer_id, order_date DESC)`

This index supports queries that filter by customer and retrieve that customer's orders in descending date order.

Column order matters.

A composite B-tree index is generally most directly useful when a query constrains its leading indexed columns.

### Partial indexes

The SQL implementation creates an index restricted to completed orders.

This reduces the indexed population when the query workload frequently targets that subset.

The planner must be able to establish that the query predicate implies the partial-index predicate.

### Covering indexes

The SQL implementation uses an `INCLUDE` clause to store additional non-key columns in an index.

These included columns can support index-only scan candidates without changing the search ordering.

An index-only scan also depends on visibility-map information. PostgreSQL may still need heap access when visibility information is insufficient.

### Execution-plan inspection

The SQL script uses:

`EXPLAIN (ANALYZE, BUFFERS)`

This provides information about:

- Selected execution operations.
- Estimated and actual row counts.
- Execution time.
- Buffer hits.
- Buffer reads.
- Index and table access.

`ANALYZE` executes the query, so it should be used with awareness of query cost and side effects.

## 10. Python Implementation

The Python script provides a complete educational B+ tree with explicit page relationships.

| Component | Responsibility |
|---|---|
| `IndexEntry` | Represents a key-value entry |
| `BPlusNode` | Represents an internal or leaf page |
| `BPlusTree` | Maintains the index hierarchy |
| `BufferPool` | Simulates LRU page caching |
| `DuplicateKeyError` | Rejects duplicate keys |
| `KeyNotFoundError` | Handles missing deletion targets |
| `IndexInvariantError` | Reports structural corruption |

The tree implements:

- Point search.
- Insertion.
- Leaf and internal splitting.
- Deletion.
- Sibling borrowing.
- Page merging.
- Root contraction.
- Range scans.
- Sorted leaf traversal.
- Breadth-first page reporting.
- Tree-height calculation.
- Structural validation.

The randomized integrity test inserts 500 keys, deletes 250, and verifies the remaining ordered key sequence.

The implementation uses Python lists for page entries and `bisect` for efficient position lookup.

Insertion into a Python list requires element shifting, so page-local insertion remains linear in the number of keys despite binary-search position lookup.

The page read and write counters are educational logical-operation counters, not actual disk I/O measurements.

## 11. JavaScript Implementation

The JavaScript implementation uses an event-oriented engineering perspective.

Its principal components are:

| Component | Responsibility |
|---|---|
| `IndexPage` | Maintains page state and version |
| `BPlusIndex` | Handles tree navigation and page maintenance |
| `LRUBufferPool` | Tracks page-cache behavior |
| `IndexQueryService` | Exposes asynchronous query execution |

The implementation uses:

- `Map` for page management.
- `Set` for cycle detection.
- `Promise.all()` for concurrent query requests.
- `setImmediate()` to yield query-service execution to the event loop.
- Explicit page versions.
- Binary search for page navigation.

The asynchronous service demonstrates request coordination. The underlying in-memory index is not a transactional, multi-writer database engine.

The implementation validates integer keys using `Number.isSafeInteger()`. This avoids silently accepting integers outside JavaScript's exact integer range.

The page version counter illustrates how page modifications can be tracked for diagnostics. It is not a replacement for database transaction identifiers or concurrency-control mechanisms.

## 12. C++17 Implementation

The C++17 implementation models page relationships using smart pointers.

Its primary design elements are:

- `IndexPage` for individual pages.
- `PageType` for page classification.
- `BPlusTree` for tree operations.
- `BufferPool` for cache simulation.
- `shared_ptr` for page ownership.
- `weak_ptr` for parent references.

Using weak parent references avoids creating ownership cycles between parent and child pages.

The implementation uses STL algorithms such as:

- `lower_bound()`
- `upper_bound()`
- `find()`
- `is_sorted()`
- `adjacent_find()`
- `shuffle()`

The tree performs insertion, search, range retrieval, deletion, structural validation, and page reporting.

Exceptions distinguish duplicate-key insertion from missing-key deletion.

The randomized test verifies structural integrity after large insertion and deletion workloads.

The implementation is designed for educational single-threaded operation. It does not provide database-grade synchronization, persistent page serialization, crash recovery, or transactional rollback.

## 13. Java 17 Implementation

The Java implementation presents index management through enterprise-oriented domain types.

Its design includes:

| Type | Responsibility |
|---|---|
| `IndexMetadata` | Describes the logical index |
| `IndexRecord` | Represents an indexed key and value |
| `IndexPage` | Maintains page contents and relationships |
| `PageSnapshot` | Provides immutable page inspection data |
| `IndexStatistics` | Represents index metrics |
| `IndexState` | Controls index availability |
| `BPlusIndex` | Provides index operations |
| `BufferPool` | Simulates LRU caching |
| `IndexQueryService` | Coordinates asynchronous queries |

The index state model distinguishes building, active, degraded, and disabled states.

Writes are permitted during building and active states. Searches require the active state.

The implementation uses synchronized index operations to prevent concurrent modifications from corrupting the in-memory tree.

The query service uses a fixed thread pool and `CompletableFuture` for asynchronous execution.

Immutable records provide structured representations of metadata and diagnostic results.

The validation mechanism checks:

- Page occupancy.
- Separator keys.
- Parent pointers.
- Leaf-chain relationships.
- Record counts.
- Reachability of pages.

This enterprise-oriented model illustrates explicit state management and service boundaries without claiming to reproduce the full operational lifecycle of a production database index.

## 14. PostgreSQL Implementation

The SQL script creates an independent `index_lab` schema.

### Relational model

The schema contains:

| Table | Purpose |
|---|---|
| `customers` | Stores customer records |
| `orders` | Stores customer order records |
| `index_config` | Documents index definitions and intended usage |
| `index_audit` | Records order modification events |

The customer and order relationship uses a foreign key.

The schema also applies:

- Primary-key constraints.
- Unique constraints.
- Check constraints.
- Foreign-key restrictions.
- Identity-generated identifiers.
- Default values.
- Transactional data modifications.

### Index definitions

The script demonstrates:

- Primary-key indexes.
- Unique indexes.
- Composite B-tree indexes.
- Descending index columns.
- Partial indexes.
- Covering indexes.

The database creates indexes automatically for primary-key and unique constraints.

Additional indexes are created for query patterns that filter or order customer and order records.

### Database diagnostics

The SQL script queries PostgreSQL catalogs to inspect:

- Index definitions.
- Index access methods.
- Index validity.
- Index readiness.
- Index sizes.
- Index usage counters.
- Relation page estimates.

It also uses `EXPLAIN (ANALYZE, BUFFERS)` to compare query execution behavior.

### Audit workflow

An `AFTER` trigger records insert, update, and delete operations on the orders table.

The trigger writes an audit record containing:

- Operation type.
- Table name.
- Affected record identifier.
- Event timestamp.
- Transaction identifier.

The transactional example demonstrates savepoints, constraint failures, exception handling, and rollback.

### Physical page inspection

The optional `pageinspect` section illustrates physical B-tree inspection.

The extension is not required for the core schema, sample data, or query demonstrations.

Installation and inspection permissions depend on database administration settings.

## 15. Complexity Analysis

Let:

- `n` represent the number of indexed records.
- `m` represent the maximum page fan-out.
- `h` represent the tree height.

| Operation | Typical complexity |
|---|---|
| Point search | `O(log_m n)` page traversal |
| Search within a page | `O(log m)` |
| Range scan returning `k` entries | `O(log_m n + k)` |
| Full leaf traversal | `O(n)` |
| Insertion | `O(log_m n)` page traversal plus page-local movement |
| Deletion | `O(log_m n)` page traversal plus rebalancing |
| Breadth-first traversal | `O(p)` for `p` pages |
| Structural validation | `O(p + n)` |

A B+ tree's principal storage advantage is its high fan-out.

When each page stores many keys, the number of levels required to index a large dataset remains relatively small.

In real databases, physical I/O cost is influenced by page size, cache residency, tuple representation, storage devices, and concurrency.

The complexity figures describe the logical data structure and do not represent exact query execution times.

## 16. Validation and Failure Conditions

The implementations explicitly handle several failure conditions.

| Condition | Expected behavior |
|---|---|
| Duplicate key | Reject insertion |
| Missing deletion key | Raise an exception |
| Invalid tree order | Reject initialization |
| Invalid key type | Reject the operation |
| Leaf overflow | Split the leaf |
| Internal overflow | Split the internal page |
| Leaf underflow | Borrow or merge |
| Internal underflow | Borrow or merge |
| Invalid separator key | Fail structural validation |
| Incorrect parent pointer | Fail structural validation |
| Broken leaf chain | Fail structural validation |
| Incorrect record count | Fail structural validation |
| Invalid buffer capacity | Reject initialization |

Structural validation is particularly important because an index can contain individually sorted pages while still having incorrect separator keys or broken child relationships.

## 17. Performance and Operational Considerations

### Index size

Indexes consume storage in addition to the underlying table.

Large indexes can increase:

- Storage consumption.
- Write amplification.
- Cache pressure.
- Maintenance costs.
- Backup size.

### Write performance

Every insertion or deletion may require index-page modifications.

Page splitting can cause additional page writes and parent modifications.

Indexes should therefore reflect actual query requirements rather than being created for every table column.

### Fillfactor

PostgreSQL supports index fillfactor settings that influence initial page occupancy.

Lower fillfactor can leave more room for future insertions in certain workloads.

The tradeoff is between free space and storage efficiency.

### Index maintenance

`ANALYZE` updates planner statistics.

`REINDEX` rebuilds an index.

`VACUUM` supports tuple cleanup and visibility-map maintenance.

These operations have different purposes and should not be treated as interchangeable.

### Security

Index keys can expose sensitive information about the underlying dataset.

Database access permissions, schema permissions, query authorization, and administrative access should be controlled independently of index performance.

Physical inspection extensions may expose low-level storage information and should be restricted to appropriately authorized roles.

### Concurrency and durability

The in-memory implementations are educational models.

Production database engines must also address:

- Transaction isolation.
- Concurrent page modification.
- Latching and locking.
- Write-ahead logging.
- Crash recovery.
- Page consistency.
- Dead tuples.
- Transaction visibility.
- Structural modification safety.

These requirements are essential when translating a conceptual tree implementation into a persistent database storage engine.
