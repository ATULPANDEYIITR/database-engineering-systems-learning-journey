# Buffer Management

## 1. Introduction

Buffer management is a database storage mechanism that controls the movement of data pages between persistent storage and main memory.

Database operations frequently access the same pages. Reading every page directly from storage creates unnecessary I/O operations and increases query execution time.

A buffer manager maintains a collection of memory frames called a **buffer pool**. Each frame can hold one database page.

The main objectives are:

- Reduce expensive storage reads.
- Reuse frequently accessed pages.
- Manage limited memory capacity.
- Track modified pages.
- Prevent eviction of pages currently in use.
- Control when modified pages are written to persistent storage.

The five implementations demonstrate buffer management through different engineering approaches: object-oriented simulation, asynchronous event-driven processing, low-level memory management, enterprise domain modeling, and relational database operations.

## 2. Core Terminology

| Term | Meaning |
|---|---|
| Buffer | Temporary memory used to hold database data. |
| Buffer pool | Collection of memory frames maintained by the database system. |
| Buffer frame | A memory slot capable of holding one database page. |
| Database page | Fixed-size unit of data transferred between storage and memory. |
| Page ID | Identifier used to locate a database page. |
| Cache hit | Requested page is already available in the buffer pool. |
| Cache miss | Requested page is not available and must be loaded. |
| Pin count | Number of active users or operations holding a page. |
| Dirty page | Modified page whose latest contents have not been persisted. |
| Clean page | Page that does not have outstanding modifications. |
| Eviction | Removal of a page from the buffer pool. |
| Flush | Writing a modified page to persistent storage. |
| Replacement policy | Rule used to select a page for eviction. |
| Storage manager | Component responsible for persistent page reads and writes. |

## 3. Buffer Pool Architecture

A buffer pool is a fixed-capacity memory structure.

For example, a database configured with 100 frames and an 8 KB page size has a nominal page-storage capacity of:

`100 × 8 KB = 800 KB`

The buffer pool maintains a mapping between database page identifiers and memory frames.

### Logical architecture

    Database Query
          |
          v
    Buffer Manager
          |
          v
    Page Lookup
          |
          +---------------------+
          |                     |
          v                     v
       Cache Hit             Cache Miss
          |                     |
          v                     v
      Existing Frame        Storage Manager
          |                     |
          |                     v
          |                 Read Page
          |                     |
          |                     v
          |                Available Frame
          |                     |
          +----------+----------+
                     |
                     v
               Database Operation
                     |
              +------+------+
              |             |
              v             v
           Clean          Modified
                           |
                           v
                       Dirty Page
                           |
                           v
                       Page Flush
                           |
                           v
                    Persistent Storage

### Buffer pool responsibilities

1. Locate a requested page.
2. Determine whether the page is cached.
3. Load missing pages.
4. Select frames for replacement.
5. Track page access and pinning.
6. Identify modified pages.
7. Persist dirty pages.
8. Maintain cache statistics.

A buffer pool is not the same as a database connection pool. A connection pool manages database connections, while a buffer pool manages database pages in memory.

## 4. Cache Hits

A cache hit occurs when a requested page already exists in the buffer pool.

Example:

- A transaction requests page 101.
- The buffer manager finds page 101 in frame 2.
- The existing frame is returned.
- No additional storage read is necessary.

A hit generally requires less time than a storage read.

Repeated access to frequently used pages can produce a high cache hit ratio.

### Hit ratio

The cache hit ratio measures the proportion of requests satisfied from memory.

\[
Hit\ Ratio = \frac{Cache\ Hits}{Total\ Requests}
\]

For example:

- Requests: 1,000
- Hits: 850
- Misses: 150

\[
Hit\ Ratio = \frac{850}{1000}=0.85
\]

The hit ratio is 85%.

A high hit ratio can indicate effective cache reuse, although it does not independently establish good query performance.

## 5. Cache Misses

A cache miss occurs when the requested page is not available in the buffer pool.

The buffer manager must retrieve the page from persistent storage.

### Miss-processing workflow

1. Receive the page request.
2. Search the buffer pool.
3. Confirm that the page is absent.
4. Locate a free frame.
5. If necessary, select an eviction candidate.
6. Flush the candidate if it is dirty.
7. Load the requested page.
8. Update frame metadata.
9. Return the page to the requesting operation.

If every frame is pinned, the buffer manager cannot safely replace any page. The request must wait or fail according to the database's resource-management policy.

### Miss ratio

\[
Miss\ Ratio = \frac{Cache\ Misses}{Total\ Requests}
\]

For a system that classifies every request as either a hit or miss:

\[
Hit\ Ratio + Miss\ Ratio = 1
\]

A cache miss does not necessarily indicate poor database design. First-time access to a page naturally produces a miss.

## 6. Page Replacement Policies

A buffer pool has limited memory. When all frames are occupied, a replacement policy determines which page can be removed.

### 6.1 Least Recently Used (LRU)

LRU selects the page that has not been accessed for the longest period.

Example:

| Page | Last access |
|---|---|
| 101 | 10:05 |
| 102 | 10:12 |
| 103 | 10:09 |

If all pages are eligible for eviction, page 101 is selected.

The assumption is that recently accessed pages are more likely to be accessed again.

The Python implementation uses `OrderedDict` to maintain the LRU ordering.

The C++ implementation uses a doubly linked list and hash map.

The Java implementation uses an access-order `LinkedHashMap`.

The JavaScript implementation uses timestamps and candidate selection.

### 6.2 Least Frequently Used (LFU)

LFU selects the eligible page with the lowest access frequency.

Example:

| Page | Access count |
|---|---:|
| 101 | 12 |
| 102 | 3 |
| 103 | 8 |

Page 102 is the LFU candidate.

LFU can preserve frequently accessed pages even when they have not been used recently.

Its limitation is that historical access counts can become less representative of current workloads. Production implementations may use aging or frequency decay.

### Policy comparison

| Characteristic | LRU | LFU |
|---|---|---|
| Selection basis | Recent access | Access frequency |
| Main assumption | Recent pages will be reused | Frequently used pages will be reused |
| Main metadata | Access ordering or timestamps | Frequency counters |
| Common limitation | Sequential scans can displace useful pages | Old access history can dominate |
| Suitable workload | Temporal locality | Repeated frequency-based access |

The Python, JavaScript, and C++ examples use LRU. The Java implementation supports both LRU and LFU policies.

## 7. Pinning and Unpinning

Pinning protects a page from eviction while an operation is using it.

The pin count records the number of active references.

For example:

| Page | Pin count | Eviction eligibility |
|---|---:|---|
| 101 | 0 | Eligible |
| 102 | 1 | Not eligible |
| 103 | 3 | Not eligible |

When an operation finishes using a page, it must unpin the page.

The buffer manager should reject:

- Unpinning a page that is not cached.
- Unpinning a page whose pin count is already zero.
- Evicting a page with a positive pin count.
- Invalidating a pinned page.

Incorrect pin management can exhaust buffer capacity even when some pages are no longer actively needed.

The implementations use explicit pin and unpin operations and validate pin counts before eviction.

## 8. Dirty and Clean Pages

### Clean pages

A clean page contains data that has no outstanding modifications requiring persistence.

It can generally be evicted without a write operation.

### Dirty pages

A dirty page has been modified in memory but its latest contents have not yet been written to persistent storage.

A dirty page must be persisted before an ordinary eviction.

Example:

1. Page 101 is loaded.
2. An update modifies a customer record.
3. The page becomes dirty.
4. The buffer manager retains the modified page.
5. A flush operation writes the page to storage.
6. The page becomes clean.

### Write-back strategy

Write-back delays storage writes until a flush or eviction occurs.

Advantages:

- Multiple modifications can be combined into fewer writes.
- Storage operations can be scheduled more efficiently.
- Repeated modifications can remain in memory.

Risks:

- Dirty pages require careful recovery management.
- Unexpected failures can threaten unpersisted modifications.
- Dirty-page accumulation can create write pressure.

### Write-through strategy

Write-through sends modifications to storage immediately.

Advantages:

- Storage is updated more frequently.
- The amount of outstanding dirty data is reduced.

Limitations:

- More frequent writes can increase I/O overhead.
- Repeated modifications may generate unnecessary storage activity.

The Python, JavaScript, and C++ implementations demonstrate write-back. Java supports both write-back and a write-through option.

## 9. Buffer Management Workflows

### 9.1 Page retrieval

    fetch(page_id)
        |
        v
    Search buffer pool
        |
        +---- Found ----> Update access metadata
        |                         |
        |                         v
        |                    Return frame
        |
        +---- Not found --> Read storage
                                  |
                                  v
                           Free frame available?
                                  |
                            +-----+-----+
                            |           |
                           Yes          No
                            |           |
                            |      Select victim
                            |           |
                            |      Check pin count
                            |           |
                            |      Flush if dirty
                            |           |
                            +-----+-----+
                                  |
                                  v
                              Load page
                                  |
                                  v
                              Return frame

### 9.2 Dirty-page flushing

    Identify dirty frame
           |
           v
    Check pin count
           |
           v
    Confirm unpinned
           |
           v
    Write page to storage
           |
           v
    Mark page clean
           |
           v
    Update write statistics

A failed storage write must not cause the dirty state to be cleared.

### 9.3 Buffer pressure

Buffer pressure occurs when the number of occupied frames approaches the configured capacity.

Possible responses include:

- Evict eligible clean pages.
- Flush and evict eligible dirty pages.
- Improve replacement policy.
- Increase buffer capacity when memory permits.
- Investigate excessive pin durations.
- Reduce unnecessary page access.

Increasing capacity is not always the correct solution. The workload, query patterns, memory availability, and operating-system behavior must also be considered.

## 10. Python Implementation

The Python file implements a reusable buffer-pool simulator.

### Main components

| Component | Responsibility |
|---|---|
| `BufferFrame` | Represents one cached page. |
| `BufferStatistics` | Tracks hits, misses, writes, and evictions. |
| `BufferPool` | Manages frames and page operations. |
| `FrameState` | Identifies clean, dirty, and free states. |
| `StorageManager` callbacks | Simulate page retrieval and persistence. |

### Important implementation decisions

**OrderedDict-based LRU**

The first entry represents the least recently used page, while the final entry represents the most recently used page.

A cache hit moves the accessed page to the end.

**Storage callbacks**

The loader and writer are injected into the buffer pool. This separates memory management from storage implementation.

**Locking**

An `RLock` protects shared buffer-pool operations against concurrent access within the process.

**Page validation**

The implementation validates:

- Page identifiers.
- Page sizes.
- Write offsets.
- Payload types.
- Pin counts.
- Frame availability.

**Persistence**

Dirty pages are written before eviction. If the writer raises an exception, the frame remains available.

### Complexity

| Operation | Expected complexity |
|---|---|
| Cache lookup | O(1) |
| Cache hit | O(1) |
| LRU update | O(1) |
| LRU victim search | O(n) |
| Page modification | O(page size) |
| Statistics retrieval | O(n) |

The example uses a scan for an unpinned eviction candidate. A production implementation can maintain a separate eligible-frame structure.

## 11. JavaScript Implementation

The JavaScript file models an asynchronous buffer manager using Node.js.

### Main components

| Component | Responsibility |
|---|---|
| `BufferFrame` | Stores page data and metadata. |
| `BufferPool` | Coordinates page retrieval and replacement. |
| `EventEmitter` | Publishes cache and storage events. |
| `Map` | Stores page-to-frame mappings. |
| `inFlight` | Coordinates concurrent page loads. |
| `BufferManagementError` | Represents buffer-operation failures. |

### Asynchronous page loading

A database storage operation may take longer than a memory lookup.

The implementation uses asynchronous loader and writer functions.

A significant optimization is request coalescing.

If three concurrent requests request the same missing page, the `inFlight` map allows them to share one storage read rather than issuing three independent reads.

This behavior reduces redundant I/O.

### Event-driven monitoring

The buffer manager emits events for:

- `hit`
- `miss`
- `eviction`
- `write`
- `closed`

These events can be connected to monitoring systems, logging services, or operational dashboards.

### Data protection

The implementation copies page buffers when returning data to the storage writer and when returning read results.

This reduces accidental mutation of internal buffer frames by external consumers.

### Concurrency limitation

The example coordinates concurrent reads of the same page, but it is not a fully transactional multi-threaded database buffer manager.

Concurrent modifications and replacement operations require stronger synchronization in a production implementation. A database engine would also integrate page latches, transaction locks, recovery protocols, and write ordering.

## 12. C++17 Implementation

The C++17 implementation uses explicit memory-oriented structures.

### Main components

| Component | Responsibility |
|---|---|
| `Page` | Models database page contents and metadata. |
| `Frame` | Associates a page with its LRU position. |
| `StorageManager` | Simulates persistent storage. |
| `BufferPool` | Manages frame allocation and replacement. |
| `Statistics` | Tracks operational metrics. |
| `PageState` | Distinguishes clean and dirty pages. |

### STL data structures

**unordered_map**

Provides expected constant-time page lookup.

**list**

Maintains the order of recently accessed pages.

**Iterator storage**

Each frame stores its position in the linked list. This allows constant-time removal and reinsertion during LRU updates.

### Engineering considerations

C++ gives direct control over object lifetime and data movement.

The implementation uses:

- References to the storage manager.
- Value-based page structures.
- `std::move` for page loading.
- Exceptions for invalid operations.
- Explicit pin-count management.
- Standard containers without external dependencies.

The page-size check ensures that storage returns exactly the expected number of bytes.

The implementation is single-threaded. A concurrent version would need synchronization around both the hash map and LRU list.

## 13. Java 17 Implementation

The Java 17 file models an enterprise-oriented buffer-management service.

### Main components

| Component | Responsibility |
|---|---|
| `BufferConfiguration` | Defines capacity, page size, and policies. |
| `PageFrame` | Represents a managed memory frame. |
| `PageStorage` | Defines the storage contract. |
| `InMemoryStorage` | Implements simulated persistent storage. |
| `BufferStatistics` | Tracks operational measurements. |
| `BufferPool` | Provides the buffer-management service. |
| `EvictionPolicy` | Selects LRU or LFU behavior. |

### Domain modeling

The implementation uses a record for immutable buffer configuration.

The storage interface separates page management from the underlying storage mechanism.

This allows another storage implementation to replace the in-memory demonstration without changing the buffer-pool interface.

### LRU and LFU policy selection

The enterprise implementation supports two replacement strategies.

LRU uses the access-order `LinkedHashMap`.

LFU selects the eligible frame with the lowest access count, using page ID as a deterministic tie-breaker.

### Write-through configuration

The configuration supports a write-through option.

When enabled, modified pages are persisted immediately.

When disabled, modifications remain dirty until an explicit flush or eviction.

### Failure handling

The implementation handles:

- Invalid page identifiers.
- Invalid configuration.
- Storage read failures.
- Storage write failures.
- Invalid write boundaries.
- Pinned-frame eviction attempts.
- Invalid unpin operations.
- Buffer-pool closure.

The synchronized buffer-pool methods serialize access to shared frame state within one Java object.

A production database would require more advanced concurrency controls to permit safe parallel page access.

## 14. PostgreSQL Implementation

The SQL file models buffer management as a relational workflow.

It uses the `buffer_management` schema.

### Database entities

| Table | Purpose |
|---|---|
| `buffer_pools` | Stores pool configuration. |
| `database_pages` | Stores persistent page records. |
| `buffer_frames` | Represents memory-frame allocation. |
| `buffer_statistics` | Maintains hit, miss, and I/O counters. |
| `buffer_io_log` | Records page-management operations. |

### Relational structure

    buffer_pools
         |
         +---------------- buffer_frames
         |
         +---------------- buffer_statistics
         |
         +---------------- buffer_io_log

    database_pages
         |
         +---------------- buffer_frames

### Integrity constraints

The schema enforces:

- Positive buffer capacities.
- Positive page sizes.
- Unique frame numbers within each pool.
- One cached copy of a page per pool.
- Nonnegative pin counts.
- Nonnegative access counts.
- Valid frame-state combinations.
- Consistent hit and miss totals.
- Valid frame allocation within pool capacity.

### Indexing strategy

The LRU index supports finding the oldest eligible frames.

The dirty-page index supports dirty-frame identification.

The pinned-frame index supports operational inspection.

The audit indexes support time-based log retrieval and failed-operation analysis.

Partial indexes reduce the number of irrelevant records included in the indexed structures.

### Database functions

| Function | Responsibility |
|---|---|
| `fetch_page` | Retrieves or loads a page. |
| `pin_page` | Protects a frame from eviction. |
| `unpin_page` | Releases a frame and optionally marks it dirty. |
| `modify_page` | Simulates page modification. |
| `flush_page` | Clears the dirty state after simulated persistence. |

### Views

`buffer_pool_report` provides capacity, utilization, and cache statistics.

`buffer_eviction_candidates` identifies the least recently accessed unpinned frame.

`cache_efficiency` classifies buffer-pool performance based on hit ratio.

### SQL implementation limitation

The relational implementation is a logical simulation of buffer management.

It stores page contents in `BYTEA` records and models frames as relational rows. It does not access PostgreSQL's internal shared-buffer frames or replace PostgreSQL's native buffer manager.

The demonstration also simplifies page synchronization and recovery. The page catalog is not a substitute for physical page storage, WAL, checkpoints, or crash recovery.

## 15. Performance Metrics

Buffer-pool performance should be evaluated using multiple metrics.

| Metric | Calculation or interpretation |
|---|---|
| Hit ratio | Hits divided by requests. |
| Miss ratio | Misses divided by requests. |
| Eviction count | Number of removed frames. |
| Dirty-page count | Number of modified pages awaiting persistence. |
| Write count | Number of simulated storage writes. |
| Failed evictions | Number of replacement attempts without an eligible frame. |
| Pin count | Number of active references to a page. |
| Buffer utilization | Occupied frames divided by total frames. |

### Buffer utilization

\[
Utilization =
\frac{Occupied\ Frames}{Total\ Frames}
\]

A buffer pool with 80 occupied frames out of 100 has 80% utilization.

High utilization alone does not indicate a performance problem. A well-utilized pool can deliver excellent cache performance.

### Average access time

An approximate model is:

\[
T_{avg} =
(H \times T_{memory}) +
(M \times T_{storage})
\]

Where:

- \(H\) is the hit ratio.
- \(M\) is the miss ratio.
- \(T_{memory}\) is average memory access time.
- \(T_{storage}\) is average storage-read time.

The model assumes hit and miss probabilities account for all requests. Actual database latency also depends on concurrency, storage queues, CPU processing, synchronization, and operating-system caching.

## 16. Edge Cases and Failure Conditions

| Condition | Expected behavior |
|---|---|
| Zero buffer capacity | Reject configuration. |
| Negative page identifier | Reject request. |
| Missing page | Report storage lookup failure. |
| Invalid page size | Reject loaded page. |
| All frames pinned | Prevent eviction. |
| Dirty victim | Persist before replacement. |
| Storage write failure | Retain dirty state. |
| Unpin without pin | Reject operation. |
| Invalidate pinned page | Reject operation. |
| Write beyond page boundary | Reject modification. |
| Flush pinned page | Reject operation. |
| Empty buffer pool statistics | Return zero ratios. |
| Concurrent requests for one missing page | Coordinate storage reads where implemented. |

## 17. Security and Reliability Considerations

Buffer management affects database correctness and data confidentiality.

Important controls include:

- Restricting buffer-management operations to authorized database components.
- Preventing unauthorized modification of page contents.
- Validating page identifiers and offsets.
- Preventing memory-boundary violations.
- Protecting sensitive pages from unintended exposure.
- Avoiding unbounded memory allocation.
- Ensuring dirty pages are not silently discarded.
- Recording failed storage operations.
- Maintaining appropriate synchronization.
- Integrating with transaction recovery and write-ahead logging.

A dirty-page flush is not, by itself, a complete transaction durability guarantee.

Production database systems coordinate buffer management with transaction processing, logging, checkpoints, concurrency control, and crash recovery.

## 18. Practical Comparison of the Five Implementations

| Implementation | Main engineering perspective | Important mechanism |
|---|---|---|
| Python | Algorithm simulation | OrderedDict-based LRU and explicit state management |
| JavaScript | Asynchronous application architecture | Promise-based loading, request coalescing, and events |
| C++17 | Memory-oriented implementation | Hash map and linked-list LRU |
| Java 17 | Enterprise service design | Configuration records, storage interfaces, and eviction policies |
| PostgreSQL | Relational workflow modeling | Constraints, functions, triggers, indexes, and reporting views |

## 19. Learning Outcomes

The implementations establish the relationships between buffer capacity, page access, cache hits, cache misses, replacement policies, pinning, dirty-page tracking, and storage writes.

The central operational distinction is:

- A cache hit reuses an existing memory frame.
- A cache miss requires a storage read.
- Pinning prevents a frame from being evicted while in use.
- A dirty page requires persistence before ordinary eviction.
- A replacement policy determines which eligible page leaves the buffer pool.

Together, these mechanisms allow database systems to manage limited memory while reducing unnecessary persistent-storage operations.
