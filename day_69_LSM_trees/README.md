# Log-Structured Merge Trees (LSM Trees)

## 1. Project Overview

This project implements the fundamental mechanisms of Log-Structured Merge Trees (LSM Trees) across Python, JavaScript, C++17, Java 17, and PostgreSQL.

An LSM Tree is a storage architecture designed to optimize write-heavy workloads. Instead of immediately modifying data in its final sorted disk location, the architecture collects writes in memory and periodically writes sorted batches to persistent storage.

The design reduces random disk writes by converting them into sequential writes and background merge operations.

The implementations demonstrate:

- Buffered writes and write optimization.
- Write-ahead logging.
- In-memory memtables.
- Immutable sorted string tables.
- Bloom filters.
- Sparse indexes.
- Sequence-based version management.
- Tombstones and logical deletion.
- Multi-level storage.
- Flush operations.
- Size-tiered compaction.
- Point lookups and range scans.
- Storage metrics and validation.

## 2. LSM Tree Architecture

An LSM Tree separates incoming writes from persistent sorted storage.

The principal components are:

| Component | Responsibility |
|---|---|
| Write-Ahead Log (WAL) | Records mutations before acknowledgment |
| Memtable | Maintains recent writes in memory |
| Immutable Memtable | Preserves a stable snapshot during flushing |
| SSTable | Stores sorted, immutable key-value records |
| Bloom Filter | Reduces unnecessary SSTable lookups |
| Sparse Index | Locates approximate positions within sorted runs |
| Level 0 | Receives newly flushed SSTables |
| Higher Levels | Store progressively compacted data |
| Compaction | Merges sorted runs and resolves duplicate versions |
| Tombstone | Represents a logical deletion |

### Architecture diagram

    Client Write
         |
         v
    Write-Ahead Log
         |
         v
      Memtable
         |
         | Capacity threshold
         v
       Flush
         |
         v
      Level 0
         |
         | Size-tiered compaction
         v
      Level 1
         |
         v
      Level 2
         |
         v
      Persistent Storage

Point reads search the memtable and relevant SSTables. Sequence numbers determine which version is authoritative.

## 3. Write-Ahead Logging

The WAL provides a recovery mechanism for acknowledged mutations.

Each record contains:

- Key.
- Value.
- Sequence number.
- Operation type.
- Timestamp.

Two operations are supported:

| Operation | Meaning |
|---|---|
| PUT | Insert or update a key |
| DELETE | Create a tombstone for a key |

The write sequence is:

1. Validate the incoming mutation.
2. Assign a monotonically increasing sequence number.
3. Append the mutation to the WAL.
4. Persist the WAL record.
5. Update the memtable.
6. Check whether the memtable has reached its configured capacity.
7. Trigger a flush when necessary.

The WAL must be durable before a successful write acknowledgment.

A production implementation must also manage WAL rotation, checksums, partial-record recovery, checkpointing, and synchronization between durable flushes and log reclamation.

## 4. Memtables

A memtable is an in-memory structure that buffers incoming writes.

The implementations use:

| Language | Data structure |
|---|---|
| Python | Dictionary |
| JavaScript | Map |
| C++17 | std::map |
| Java 17 | HashMap |
| PostgreSQL | Relational table with uniqueness constraints |

A repeated write to the same key replaces its previous memtable entry.

For example:

| Sequence | Key | Value |
|---:|---|---|
| 1 | account:101 | ACTIVE |
| 2 | account:102 | PENDING |
| 3 | account:101 | VERIFIED |

The memtable contains only the latest in-memory version of each key.

This reduces the number of records that need to be written when the memtable is flushed.

A production memtable generally uses a concurrent ordered structure, such as a skip list or balanced tree, when ordered iteration and concurrent writes are required.

## 5. Memtable Flushing

Flushing converts the current memtable into an immutable sorted run.

The process involves:

1. Taking a consistent snapshot of the memtable.
2. Sorting its records by key.
3. Constructing an SSTable.
4. Building the Bloom filter.
5. Building the sparse index.
6. Publishing the completed run.
7. Releasing the flushed memtable.

The output is immutable.

This property simplifies concurrent reads because existing SSTables do not need to be modified when new records arrive.

The implementations use a configurable memtable capacity to demonstrate automatic flushing.

A production engine normally separates the active memtable from immutable memtables awaiting background flush workers.

## 6. Sorted String Tables (SSTables)

An SSTable is an immutable, sorted representation of key-value records.

Example:

| Key | Value | Sequence |
|---|---|---:|
| account:101 | VERIFIED | 5 |
| account:102 | ACTIVE | 2 |
| account:103 | PENDING | 4 |
| account:104 | CLOSED | 7 |

SSTables are sorted by key.

This supports efficient sequential access and range queries.

An SSTable typically contains:

- Data blocks.
- Index blocks.
- Bloom filter metadata.
- Key-range metadata.
- Checksums.
- Compression information.
- Version information.

The educational implementations represent these components in memory or relational metadata rather than implementing a production binary SSTable file format.

## 7. Bloom Filters

A Bloom filter is a probabilistic data structure used to test whether a key might exist in an SSTable.

It provides two possible results:

| Result | Interpretation |
|---|---|
| Definitely absent | The key is not in the SSTable |
| Possibly present | The key may exist and requires verification |

Bloom filters can produce false positives but must not produce false negatives when correctly maintained.

A false positive causes an unnecessary lookup. It does not produce an incorrect value.

### False-positive probability

The approximate optimal bit count is:

\[
m = -\frac{n\ln(p)}{(\ln 2)^2}
\]

Where:

- \(m\) is the number of bits.
- \(n\) is the expected number of inserted keys.
- \(p\) is the target false-positive probability.

The optimal number of hash functions is:

\[
k = \frac{m}{n}\ln 2
\]

The implementations use a target false-positive rate of approximately 1%.

The Python, JavaScript, and C++ versions implement membership structures directly. The Java implementation provides a corresponding in-memory filter. PostgreSQL stores Bloom filter configuration metadata rather than implementing a physical Bloom bit array.

## 8. Sparse Indexes

A sparse index stores selected keys and their positions instead of maintaining an index entry for every record.

For example, with an index interval of four:

| Position | Key | Indexed |
|---:|---|---|
| 0 | account:001 | Yes |
| 1 | account:002 | No |
| 2 | account:003 | No |
| 3 | account:004 | No |
| 4 | account:005 | Yes |
| 5 | account:006 | No |
| 6 | account:007 | No |
| 7 | account:008 | No |

A lookup first finds the nearest indexed key and then searches a small section of the sorted data.

This reduces index memory requirements.

The trade-off is that more records may need to be inspected after locating the appropriate index entry.

## 9. Point Lookups

A point lookup searches for one key.

The logical read sequence is:

1. Search the active memtable.
2. Check relevant SSTable key ranges.
3. Consult Bloom filters.
4. Locate candidate records through sparse indexes.
5. Retrieve matching versions.
6. Select the highest sequence number.
7. Interpret the winning operation.

The newest version is determined by sequence number, not merely by SSTable level or physical file order.

This distinction is important because multiple SSTables may contain different versions of the same key.

### Example

| Storage location | Key | Value | Sequence |
|---|---|---|---:|
| Memtable | account:101 | CLOSED | 15 |
| Level 0 | account:101 | ACTIVE | 10 |
| Level 1 | account:101 | VERIFIED | 7 |

The correct result is `CLOSED`, because sequence 15 is the newest mutation.

## 10. Tombstones and Logical Deletion

An LSM Tree generally does not immediately remove an old record when a delete operation occurs.

Instead, it writes a tombstone.

Example:

| Sequence | Key | Operation | Value |
|---:|---|---|---|
| 1 | account:101 | PUT | ACTIVE |
| 2 | account:101 | DELETE | NULL |

The tombstone has a higher sequence number and therefore hides the earlier value.

This prevents older SSTables from making a deleted record visible again.

Tombstones cannot be discarded merely because they have been encountered during compaction.

They may be removed only when the engine can establish that no older version can reappear through lower-level data, snapshots, replicas, or other supported recovery mechanisms.

The educational implementations retain tombstones during compaction.

## 11. Compaction

Compaction merges multiple SSTables into a smaller number of sorted runs.

Its main responsibilities include:

- Combining sorted records.
- Resolving duplicate keys.
- Retaining the newest sequence.
- Preserving deletion information.
- Rebuilding indexes.
- Rebuilding Bloom filters.
- Updating storage-level metadata.

### Example

Input run A:

| Key | Value | Sequence |
|---|---|---:|
| account:101 | ACTIVE | 1 |
| account:102 | PENDING | 2 |

Input run B:

| Key | Value | Sequence |
|---|---|---:|
| account:101 | VERIFIED | 5 |
| account:103 | CLOSED | 6 |

Output:

| Key | Value | Sequence |
|---|---|---:|
| account:101 | VERIFIED | 5 |
| account:102 | PENDING | 2 |
| account:103 | CLOSED | 6 |

The newer version of account:101 replaces the older version in the compacted output.

### Size-tiered compaction

The implementations demonstrate a simplified size-tiered strategy.

When the number of runs reaches a configured threshold, the runs are merged into the next level.

| Level | Purpose |
|---|---|
| Level 0 | Newly flushed runs |
| Level 1 | First compacted runs |
| Level 2 | Larger merged runs |
| Level 3 | Deeper storage |
| Higher levels | Progressively consolidated data |

This model is useful for learning compaction mechanics.

Real storage engines may use size-tiered, leveled, universal, or time-window-based compaction strategies.

## 12. Read Amplification, Write Amplification, and Space Amplification

Three performance concepts are central to LSM Tree design.

### Read amplification

Read amplification describes the amount of storage work required to retrieve a record.

A key may exist in several SSTables, requiring multiple candidate checks.

Bloom filters and indexing reduce unnecessary reads.

### Write amplification

Write amplification describes how many physical bytes are written relative to the amount of logical data written by the application.

A record may be rewritten several times during successive compactions.

This means LSM Trees optimize the initial write path but still perform additional background write operations.

### Space amplification

Space amplification describes additional storage consumed by obsolete versions, overlapping runs, and tombstones.

Compaction reduces redundant versions and reclaims space when deletion is safe.

The three amplification measures are related.

Reducing one can increase another, depending on the compaction strategy and workload.

## 13. Range Scans

Range scans retrieve records between two keys.

The implementations:

1. Validate the requested boundaries.
2. Read the memtable.
3. Inspect relevant SSTable records.
4. Group versions by key.
5. Select the highest sequence number.
6. Remove logically deleted records.
7. Return sorted results.

For example, a request for `account:100` through `account:200` returns the currently visible records in that key range.

Production systems generally merge sorted iterators instead of collecting all records into memory.

This reduces memory consumption and allows streaming results.

## 14. Python Implementation

The Python implementation uses classes and dataclasses to represent storage components.

| Component | Implementation |
|---|---|
| Entry | Immutable dataclass |
| Bloom filter | Bytearray-backed bit structure |
| WAL | JSON Lines file |
| Memtable | Dictionary |
| SSTable | Sorted list |
| Sparse index | Key and position lists |
| Levels | Dictionary of run lists |
| Compaction | Sequence-based version merging |

The script demonstrates:

- WAL persistence.
- Write and delete operations.
- Automatic flushing.
- Point lookups.
- Range scans.
- Compaction.
- Storage statistics.
- WAL recovery.
- Structural assertions.

The recovery demonstration rebuilds the latest visible state from the retained WAL.

It does not implement a production checkpoint protocol or durable SSTable recovery.

## 15. JavaScript Implementation

The JavaScript implementation adopts an event-driven storage design.

Its architecture uses:

- `Map` for memtable storage.
- `Uint8Array` for Bloom filter bits.
- Node.js filesystem APIs for WAL persistence.
- Promises for asynchronous writes.
- An `EventEmitter` for storage lifecycle events.
- A serialized mutation queue for write ordering.
- `queueMicrotask` for scheduled compaction.

Important events include:

| Event | Meaning |
|---|---|
| write | Mutation persisted |
| delete | Tombstone recorded |
| flush | New sorted run created |
| compaction | Runs merged |
| error | Background operation failed |
| close | Storage engine closed |

The write queue ensures that concurrent mutations do not reorder sequence assignment and WAL persistence.

The implementation uses asynchronous WAL writes and exposes storage metrics.

Its recovery method reconstructs the memtable from the WAL. It is an educational recovery path rather than a complete production recovery protocol.

## 16. C++17 Implementation

The C++ implementation uses STL structures and explicit domain modeling.

| Component | Implementation |
|---|---|
| Entry | Struct |
| Memtable | `std::map` |
| Levels | `std::map` |
| Bloom filter | `std::vector<bool>` |
| SSTables | `std::vector<Entry>` |
| Version resolution | Sequence comparison |
| Range scans | Ordered map |
| Error handling | Exceptions |

The implementation demonstrates a telemetry workload involving sensor measurements.

It emphasizes:

- Explicit storage state.
- Ordered key management.
- Input validation.
- Sequence overflow protection.
- Immutable SSTable construction.
- Compaction behavior.
- Tombstone handling.
- Post-operation invariant checks.

The ordered memtable provides logarithmic lookup and insertion in exchange for higher per-entry overhead than a hash-based structure.

The implementation is an in-memory simulation and does not provide disk persistence or concurrent access synchronization.

## 17. Java 17 Implementation

The Java implementation models an enterprise financial-event storage service.

It uses:

- Records for immutable data structures.
- Enums for operation and storage states.
- Policy objects for configuration and validation.
- `HashMap` for memtable management.
- `TreeMap` for ordered levels and range results.
- `AtomicLong` for sequence assignment.
- Synchronized service methods for serialized access.
- Custom exceptions for storage failures.
- Streams for result processing.

The `StoragePolicy` class controls:

- Memtable capacity.
- Compaction run capacity.
- Sparse index interval.
- Maximum key length.

The `LSMStorageService` class manages storage operations and enforces state transitions.

Flush and compaction operations restore the active state when an exception occurs.

The Java implementation is an in-memory domain model. Its synchronization does not replace the durability guarantees of a production WAL or transactional filesystem implementation.

## 18. PostgreSQL Implementation

The PostgreSQL script models the LSM storage workflow through relational tables.

It separates operational metadata from the actual key-value records.

### Relational model

| Table | Purpose |
|---|---|
| storage_engine | Engine configuration |
| storage_level | Storage-level definitions |
| wal_record | Ordered mutation history |
| memtable_entry | Current in-memory entries |
| sstable | Sorted-run metadata |
| sstable_entry | SSTable records |
| bloom_filter_metadata | Bloom filter configuration |
| sparse_index_entry | Sparse index records |
| storage_operation | Flush and compaction history |

### Database integrity

The SQL implementation uses:

- Primary keys.
- Foreign keys.
- Unique constraints.
- Check constraints.
- Lookup indexes.
- Sequence-number indexes.
- Stored functions.
- Views.
- Transactions.
- Common table expressions.
- Window functions.

The `write_record` function inserts the WAL record and then updates the memtable within the same database transaction.

The `flush_memtable` function creates an SSTable and associated metadata before removing the memtable entries.

The `compact_level` function merges active runs, selects the newest version for each key, creates a new run, and retires the input runs.

The `get_record` function resolves the newest visible version across the memtable and active SSTables.

The `scan_range` function implements ordered range retrieval with tombstone filtering.

The reporting views expose storage-level and engine-level metrics.

### Important distinction

PostgreSQL is being used here as a relational simulation of LSM concepts.

Its ordinary tables and indexes are not themselves a custom LSM storage engine implementation. The relational model illustrates storage metadata, operations, version resolution, and transactional processing.

The Bloom filter table stores configuration and insertion metadata rather than actual filter bits.

## 19. Complexity Analysis

Let:

- \(N\) represent the number of records in an SSTable.
- \(M\) represent the number of entries in a memtable.
- \(L\) represent the number of levels.
- \(R\) represent the number of candidate SSTables.

Approximate complexity for the demonstrated data structures:

| Operation | Expected or approximate complexity |
|---|---|
| Hash-based memtable insertion | \(O(1)\) average |
| Ordered memtable insertion | \(O(\log M)\) |
| Memtable lookup | \(O(1)\) average with hashing |
| Memtable lookup using an ordered tree | \(O(\log M)\) |
| Sorting during flush | \(O(M\log M)\) |
| Bloom filter membership | \(O(k)\) |
| Sparse index search | \(O(\log(N/I))\) |
| Local indexed search | \(O(I)\) |
| Full merge of sorted runs | \(O(N\log R)\) |
| Full in-memory version resolution | \(O(N\log N)\) in the demonstrated map-based approaches |

Here, \(I\) represents the sparse-index interval.

Actual production costs depend on block sizes, caching, compression, filesystem behavior, concurrency, and the number of overlapping runs.

## 20. Design Trade-offs

| Design decision | Benefit | Cost |
|---|---|---|
| Buffered writes | Reduces random write operations | Requires memory |
| WAL | Supports recovery | Additional sequential writes |
| Immutable SSTables | Simplifies concurrent reads | Requires compaction |
| Bloom filters | Avoids unnecessary reads | Consumes memory |
| Sparse indexes | Reduces index size | Requires local scanning |
| Tombstones | Preserves deletion correctness | Temporarily consumes space |
| Compaction | Removes obsolete versions | Causes write amplification |
| Multiple levels | Organizes persistent storage | Increases operational complexity |

## 21. Edge Cases and Failure Handling

The implementations consider the following cases:

- Empty keys.
- Invalid values.
- Duplicate keys.
- Repeated updates.
- Deleting a nonexistent key.
- Looking up a deleted key.
- Stale values in older SSTables.
- Empty memtables.
- Invalid range boundaries.
- Invalid storage capacities.
- Duplicate SSTable identifiers.
- Sequence number validation.
- WAL record corruption.
- Failed asynchronous writes.
- Compaction failures.
- Invalid engine states.

Several production requirements remain outside the educational implementations.

These include:

- Crash-safe atomic file publication.
- SSTable checksums and corruption detection.
- WAL segmentation and checkpointing.
- Concurrent read snapshots.
- Multi-threaded compaction scheduling.
- Level-overlap tracking.
- Safe tombstone garbage collection.
- Replication consistency.
- Durable manifest management.
- Backpressure and resource limits.

## 22. Running the Implementations

| Language | Execution |
|---|---|
| Python | `python lsm_tree.py` |
| JavaScript | `node lsm_tree.js` |
| C++17 | `g++ -std=c++17 -O2 -Wall -Wextra lsm_tree.cpp -o lsm_tree` |
| Java 17 | `javac LSMTreeDemo.java` followed by `java LSMTreeDemo` |
| PostgreSQL | Execute the SQL script using `psql` |

The Python and JavaScript implementations create local WAL files. Their demonstration data directories can be removed after execution.

The PostgreSQL script creates and populates the `lsm_lab` schema. It drops an existing schema with that name before rebuilding it.

## 23. Educational Outcomes

The five implementations provide complementary perspectives on LSM storage design.

The Python implementation emphasizes data structures, WAL recovery, and operational validation.

The JavaScript implementation emphasizes asynchronous persistence, serialized writes, and event-driven storage behavior.

The C++17 implementation emphasizes ordered structures, domain modeling, and explicit resource-oriented engineering decisions.

The Java 17 implementation emphasizes enterprise storage policies, service boundaries, immutable records, and controlled state transitions.

The PostgreSQL implementation emphasizes relational integrity, transactional operations, version resolution, and operational reporting.

Together, they demonstrate how write buffering, immutable sorted storage, indexing, version resolution, and compaction form the foundation of write-optimized storage systems.
