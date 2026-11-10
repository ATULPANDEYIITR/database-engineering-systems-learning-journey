# Database Checkpoints, Dirty Pages and Recovery

## 1. Technical Scope

This project models database checkpointing and crash recovery through five independent implementations:

| File | Engineering perspective | Main responsibility |
|---|---|---|
| Python | Storage-engine simulation | Transaction execution and recovery |
| JavaScript | Event-driven storage model | Asynchronous WAL and recovery coordination |
| C++17 | Recovery engine | LSN-based analysis, redo and undo |
| Java 17 | Enterprise architecture | Domain types and recovery services |
| PostgreSQL | Relational workflow | WAL, page, transaction and checkpoint metadata |

The central problem is maintaining database consistency when a system crashes after modifying cached pages but before every modified page reaches persistent storage.

A database must distinguish between:

- Changes recorded in the write-ahead log.
- Changes applied to pages in memory.
- Changes written to persistent data pages.
- Transactions that successfully committed.
- Transactions that were incomplete when the crash occurred.

Checkpointing reduces the amount of log processing required during recovery. It does not eliminate the need for recovery.

## 2. Fundamental Storage Concepts

### 2.1 Database pages

Database storage engines organize records into pages or blocks.

A page typically contains:

- A page identifier.
- Stored records.
- Page metadata.
- A page-level log sequence number.
- Buffer-management information.

A database buffer pool maintains frequently accessed pages in memory.

When a transaction modifies a page, the buffer manager usually modifies its in-memory representation. The corresponding persistent data page might remain unchanged until a later write operation.

This difference creates the dirty-page problem.

### 2.2 Dirty pages

A dirty page is a cached page containing modifications that have not yet been written to persistent data storage.

For example:

| Page | Persistent value | Cached value | State |
|---|---:|---:|---|
| ACCOUNT_101 | 1,000 | 1,100 | Clean after flush |
| ACCOUNT_202 | 2,000 | 1,800 | Dirty |
| ACCOUNT_303 | 3,000 | 3,500 | Dirty |

Dirty pages are not necessarily unsafe. Their modifications can be reconstructed from durable WAL records after a crash.

The critical requirement is that the corresponding log records must be durable before the modified data pages are written.

### 2.3 Page LSN

A page LSN identifies the latest log record whose modification is reflected in that page.

If a page contains a modification corresponding to LSN 25, its page LSN must represent at least that operation.

During recovery, the page LSN helps determine whether a log record needs to be replayed.

A record with an LSN not greater than the page LSN has already been reflected in the page and can be skipped.

### 2.4 Recovery LSN and recLSN

The recovery LSN, commonly represented as `recLSN`, identifies the earliest WAL record that might need to be reapplied to a dirty page.

Consider the following sequence:

| LSN | Operation |
|---:|---|
| 10 | Transaction A modifies Page 1 |
| 15 | Transaction B modifies Page 2 |
| 20 | Transaction A modifies Page 1 |
| 25 | Transaction C commits |

Page 1 has:

- `recLSN = 10`
- `pageLSN = 20`

Its recovery interval begins at LSN 10.

The recovery manager uses this information to identify a conservative point from which log processing should begin.

## 3. Write-Ahead Logging

Write-Ahead Logging (WAL) separates the recording of database modifications from the physical writing of modified data pages.

A WAL record describes an operation before the corresponding data page is considered safely persisted.

### 3.1 WAL record structure

The implementations model the following attributes:

| Attribute | Purpose |
|---|---|
| LSN | Unique sequential log position |
| Transaction ID | Identifies the modifying transaction |
| Record type | Identifies the operation |
| Page ID | Identifies the affected page |
| Old value | Supports undo |
| New value | Supports redo |
| Undo-next LSN | Supports compensation-record traversal |

The LSN provides an ordering mechanism for log records.

It is not necessarily a byte offset or timestamp.

### 3.2 Important record types

| Record | Meaning |
|---|---|
| BEGIN | Transaction begins |
| UPDATE | Transaction modifies a page |
| COMMIT | Transaction successfully commits |
| ABORT | Transaction aborts |
| END | Transaction processing finishes |
| CHECKPOINT_BEGIN | Checkpoint starts |
| CHECKPOINT_END | Checkpoint metadata is recorded |
| CLR | Compensation Log Record |

### 3.3 WAL durability rule

The essential write-ahead rule is:

**The WAL record describing a page modification must become durable before the modified page is written to persistent storage.**

For a page with page LSN 50, the durable WAL boundary must be at least 50 before that page can be safely flushed.

The Python, JavaScript, C++17 and Java implementations enforce this rule in their page-flush operations.

The PostgreSQL implementation represents the rule through its WAL durability boundary and page-flush procedure.

### 3.4 Commit durability

A successful transaction commit requires its commit record to reach durable storage before the database acknowledges successful completion.

This is different from requiring every modified data page to be written immediately.

A committed transaction can therefore have dirty pages.

After a crash, redo processing reconstructs committed modifications that were not reflected in persistent pages.

## 4. Database Checkpoints

### 4.1 Definition

A checkpoint is a recovery coordination mechanism that establishes a known point in the database's WAL and records information needed to resume recovery efficiently.

A checkpoint can record:

- Its starting and ending LSN.
- The dirty-page table.
- Active transactions.
- Transaction progress.
- Associated recovery metadata.

A checkpoint is not equivalent to a complete database backup.

It does not necessarily mean every dirty page has been flushed.

### 4.2 Checkpoint lifecycle

The educational implementations use the following lifecycle:

1. Append a checkpoint-begin record.
2. Capture the current dirty-page table.
3. Capture active transaction information.
4. Append a checkpoint-end record.
5. Make the checkpoint metadata durable.
6. Retain the checkpoint as a recovery reference.

Plain-text representation:

    Database Activity
           |
           v
    CHECKPOINT_BEGIN
           |
           v
    Capture Dirty Page Table
           |
           v
    Capture Transaction Table
           |
           v
    CHECKPOINT_END
           |
           v
    Flush Checkpoint WAL
           |
           v
    Checkpoint Completed

### 4.3 Fuzzy checkpoints

A fuzzy checkpoint allows normal database activity to continue while checkpoint metadata is collected.

It does not require stopping all transactions or flushing every dirty page before checkpoint completion.

Consider:

| Event | LSN | Page State |
|---|---:|---|
| Transaction A updates Page 1 | 10 | Dirty |
| Transaction B updates Page 2 | 15 | Dirty |
| Checkpoint begins | 20 | Both dirty |
| Checkpoint metadata recorded | 23 | Both tracked |
| Transaction A commits | 25 | Page 1 may remain dirty |
| Transaction C updates Page 3 | 28 | Dirty |
| Crash | 30 | Recovery required |

The checkpoint records the information needed to identify relevant dirty pages and active transactions.

Subsequent operations are recovered using the WAL.

The implementations use this model rather than requiring a complete database-wide flush.

### 4.4 Checkpoint metadata

The checkpoint dirty-page table maps each dirty page to its earliest recovery LSN.

Example:

| Page | recLSN |
|---|---:|
| Page 1 | 10 |
| Page 2 | 15 |
| Page 3 | 28 |

The earliest recovery LSN is 10.

The transaction table records transactions that were active when checkpoint information was captured.

These two structures serve different purposes:

- The dirty-page table determines the potential redo starting point.
- The transaction table contributes to identifying incomplete transactions.

### 4.5 Checkpoint frequency and performance

Frequent checkpoints can reduce recovery work, but they can increase storage I/O and checkpoint-related overhead.

Infrequent checkpoints can reduce checkpoint activity while increasing the amount of WAL that might need to be examined after a crash.

The appropriate balance depends on:

- Database write volume.
- Buffer-pool size.
- Storage throughput.
- WAL generation rate.
- Recovery-time objectives.
- Checkpoint configuration.

## 5. Dirty-Page Management

### 5.1 Dirty-page lifecycle

    Persistent Page
          |
          v
    Load Into Buffer Pool
          |
          v
    Transaction Updates Page
          |
          v
    Append WAL Record
          |
          v
    Update Cached Page
          |
          v
    Mark Page Dirty
          |
          v
    WAL Becomes Durable
          |
          v
    Write Data Page
          |
          v
    Mark Page Clean

The dirty flag represents whether the cached page differs from its persistent representation.

The `recLSN` must be retained from the first modification that made the page dirty. Later modifications should not replace it while the page remains dirty.

When a page is successfully flushed, its dirty flag is cleared and its recovery LSN is reset.

### 5.2 Page flushing

A page flush has two important effects:

- The modified page becomes persistent.
- The page no longer requires redo for modifications already represented by its persistent image.

The WAL durability check prevents the database from writing a page whose corresponding log records have not yet become durable.

### 5.3 Dirty-page table versus buffer pool

These structures have different responsibilities.

| Structure | Responsibility |
|---|---|
| Buffer pool | Holds cached page contents |
| Dirty-page table | Identifies pages requiring potential recovery |
| WAL | Records modification history |
| Persistent storage | Holds durable page images |

A dirty-page table is recovery metadata, not a replacement for the actual cached pages.

## 6. Crash Recovery

### 6.1 Recovery objectives

Recovery must establish a consistent database state after an unexpected interruption.

The primary requirements are:

- Preserve committed transactions.
- Remove the effects of incomplete transactions.
- Avoid applying an operation twice.
- Maintain WAL-before-data ordering.
- Produce durable recovered pages.

### 6.2 Analysis phase

The analysis phase examines checkpoint metadata and subsequent WAL records.

It identifies:

- Active transactions.
- Committed transactions.
- Aborted transactions.
- Transaction progress.
- Dirty pages.
- The earliest required redo LSN.

Example:

| Transaction | Last operation | State at crash |
|---|---|---|
| T1 | COMMIT | Committed |
| T2 | UPDATE | Active |
| T3 | COMMIT | Committed |

T1 and T3 must retain their committed modifications.

T2 requires undo processing.

### 6.3 Redo phase

Redo repeats durable modifications when the persistent page does not already contain them.

The operation is based on the WAL record and page LSN.

Conceptually:

    For each eligible WAL record:
        Read its page.
        Compare page LSN with record LSN.
        If page LSN is older:
            Reapply the recorded modification.
            Update page LSN.
        Otherwise:
            Skip the modification.

Redo is idempotent when page-state checks are correctly implemented.

The operation can safely be reconsidered without blindly applying every modification again.

### 6.4 Undo phase

Undo reverses modifications belonging to transactions that did not successfully commit.

Suppose:

| LSN | Transaction | Operation |
|---:|---|---|
| 10 | T1 | BEGIN |
| 11 | T1 | UPDATE Account A: 1,000 to 1,100 |
| 12 | T1 | COMMIT |
| 13 | T2 | BEGIN |
| 14 | T2 | UPDATE Account B: 2,000 to 1,800 |
| 15 | T2 | Crash |

Recovery must preserve Account A at 1,100 and restore Account B to 2,000.

The implementations store old and new values in their update records to demonstrate redo and undo.

### 6.5 Compensation Log Records

A Compensation Log Record (CLR) records an action performed during undo.

Its purpose is to make recovery progress itself recoverable.

A production recovery algorithm must also maintain transaction log chains and appropriate undo-next pointers.

The implementations model CLR records and the relationship between original updates and compensation operations.

Their recovery engines are educational approximations rather than complete ARIES implementations.

### 6.6 Recovery lifecycle

    Database Crash
          |
          v
    Load Durable Storage
          |
          v
    Locate Latest Durable Checkpoint
          |
          v
    ANALYSIS
          |
          v
    Reconstruct Transaction and Dirty-Page State
          |
          v
    REDO
          |
          v
    Restore Durable Page Modifications
          |
          v
    UNDO
          |
          v
    Reverse Incomplete Transactions
          |
          v
    Persist Compensation Records
          |
          v
    Flush Recovered Pages
          |
          v
    Database Recovered

## 7. Important Recovery Distinctions

| Concept | Responsibility |
|---|---|
| Checkpoint | Establishes a recovery reference point |
| Dirty-page tracking | Identifies potentially unpersisted modifications |
| WAL | Preserves modification history |
| Page LSN | Identifies modifications reflected in a page |
| recLSN | Identifies the earliest relevant recovery record |
| Analysis | Reconstructs recovery state |
| Redo | Reapplies necessary durable operations |
| Undo | Reverses incomplete transaction operations |
| CLR | Records compensation performed during undo |

These mechanisms are related but not interchangeable.

A checkpoint does not replace WAL.

A dirty-page table does not replace the buffer pool.

Redo does not replace undo.

A commit record does not imply that every modified data page has already been flushed.

## 8. Python Implementation

**File:** `database_checkpoints.py`

The Python implementation models a complete storage-engine workflow using standard-library data structures.

### Main components

| Component | Responsibility |
|---|---|
| `WriteAheadLog` | LSN allocation and durability |
| `BufferPool` | Page caching and dirty tracking |
| `DatabaseEngine` | Transaction and checkpoint coordination |
| `LogRecord` | Immutable-style WAL record representation |
| `Transaction` | Transaction lifecycle |
| `Checkpoint` | Recovery metadata |
| `RecoveryState` | Database recovery lifecycle |

### Implementation decisions

Dataclasses represent pages, transactions, log records and checkpoints.

Enums prevent inconsistent representations of transaction and log states.

Dictionaries provide direct lookup of pages and transactions.

The WAL stores ordered records in a list, making LSN-to-record lookup straightforward.

The checkpoint manager captures dirty-page and transaction metadata without requiring a complete page flush.

The recovery manager reconstructs transaction state, replays eligible operations and reverses incomplete transactions.

The reporting mechanism writes JSON through a temporary file followed by an atomic rename.

### Demonstration scenario

The Python program creates three account pages.

- Transaction 1 modifies Account 101 and commits.
- Account 101 is flushed.
- Transaction 2 modifies Account 202 and remains active.
- A fuzzy checkpoint is created.
- Transaction 3 modifies Account 303 and commits.
- Transaction 2 performs another update.
- The database crashes.

Expected persistent values after recovery:

| Page | Expected value |
|---|---:|
| ACCOUNT-101 | 1,100 |
| ACCOUNT-202 | 2,000 |
| ACCOUNT-303 | 3,500 |

The assertions verify that committed changes survive and the incomplete transaction is reversed.

## 9. JavaScript Implementation

**File:** `database-checkpoints.js`

The JavaScript implementation emphasizes asynchronous execution and event-driven storage behavior.

### Main components

| Component | Responsibility |
|---|---|
| `WriteAheadLog` | Log sequencing and durability |
| `BufferPool` | Page state and dirty-page events |
| `TransactionManager` | Transaction operations |
| `CheckpointManager` | Fuzzy checkpoint creation |
| `RecoveryManager` | Recovery coordination |
| `DatabaseEngine` | Overall engine state |

### JavaScript-specific decisions

`Map` stores page and transaction state.

`EventEmitter` publishes page and transaction lifecycle events.

`async` and `await` represent asynchronous commit coordination.

`Promise.resolve()` demonstrates an asynchronous scheduling boundary. It does not represent an actual physical disk flush.

`structuredClone()` isolates metadata objects from subsequent mutation.

`crypto.randomUUID()` creates unique temporary report filenames.

The implementation also validates page identifiers and integer values.

The recovery manager uses transaction histories to determine which operations require undo.

## 10. C++17 Implementation

**File:** `database_recovery.cpp`

The C++ implementation concentrates on a strongly typed recovery engine.

### Main components

| Component | Responsibility |
|---|---|
| `WriteAheadLog` | Ordered log and durable boundary |
| `BufferPool` | Cached page management |
| `DatabaseEngine` | Storage-engine coordination |
| `Transaction` | Transaction state |
| `Checkpoint` | Checkpoint metadata |
| `RecoveryService` logic | Analysis, redo and undo |

### Engineering decisions

`std::map` provides deterministic ordering for pages and transaction metadata.

`std::vector` stores ordered WAL records.

`std::optional` represents missing transaction, page and LSN information.

Enums distinguish transaction and engine states.

References avoid unnecessary copying of mutable page objects.

Exceptions report invalid operations, unknown pages and WAL durability violations.

The recovery engine demonstrates why the persistent page LSN must be compared with the WAL record LSN before replay.

## 11. Java 17 Implementation

**File:** `DatabaseRecovery.java`

The Java implementation models checkpoint and recovery responsibilities through explicit service boundaries.

### Main components

| Component | Responsibility |
|---|---|
| `WriteAheadLog` | Log sequencing and durable boundaries |
| `BufferPool` | Cached page management |
| `TransactionService` | Transaction operations |
| `CheckpointService` | Checkpoint metadata |
| `RecoveryService` | Recovery execution |
| `DatabaseEngine` | Engine coordination |

### Enterprise design decisions

Java records represent immutable WAL records, transaction snapshots and recovery reports.

Enums represent transaction and engine states.

The service classes separate transaction execution from checkpointing and recovery.

Collections maintain transaction and page state.

The recovery report provides structured results instead of relying exclusively on console output.

The design also demonstrates validation at service boundaries and explicit exceptions for invalid transaction operations.

## 12. PostgreSQL Implementation

**File:** `database_checkpoints.sql`

The SQL implementation models the relationships among database engines, transactions, pages, WAL records, checkpoints and recovery operations.

### Relational architecture

    Storage Engines
          |
          +---- Database Transactions
          |           |
          |           +---- WAL Records
          |
          +---- Database Pages
          |           |
          |           +---- Dirty Page Metadata
          |
          +---- Checkpoints
          |           |
          |           +---- Checkpoint Dirty Pages
          |           |
          |           +---- Checkpoint Transactions
          |
          +---- Recovery Runs
                      |
                      +---- Recovery Actions

### Main tables

| Table | Purpose |
|---|---|
| `storage_engines` | Engine identity and LSN boundaries |
| `database_transactions` | Transaction state and progress |
| `database_pages` | Page contents and dirty status |
| `wal_records` | Ordered modification records |
| `checkpoints` | Checkpoint lifecycle |
| `checkpoint_dirty_pages` | Captured dirty-page information |
| `checkpoint_transactions` | Active transaction snapshots |
| `recovery_runs` | Recovery execution metadata |
| `recovery_actions` | Individual recovery decisions |

### Database constraints

The schema uses primary keys, foreign keys, unique identifiers, check constraints and indexes.

Important integrity rules include:

- Durable LSN cannot exceed the generated LSN.
- A dirty page must have a recovery LSN.
- A clean page cannot retain a dirty-page recovery LSN.
- A checkpoint marked completed must have an ending LSN.
- WAL update records must contain page and value information.
- Compensation pointers must refer to earlier log positions.

### Database functions and procedures

| Routine | Purpose |
|---|---|
| `append_wal_record` | Generates an LSN and inserts a log record |
| `flush_wal` | Advances the durable WAL boundary |
| `begin_transaction` | Starts a transaction |
| `update_database_page` | Applies a logged page modification |
| `commit_transaction` | Persists the commit record |
| `flush_database_page` | Validates WAL ordering before page flushing |
| `create_checkpoint` | Captures checkpoint metadata |
| `calculate_recovery_plan` | Calculates a conservative redo starting point |

The reporting views provide transaction analysis, dirty-page information, checkpoint history, WAL statistics and recovery eligibility.

The sample data represents committed and incomplete transactions.

## 13. Edge Cases and Failure Conditions

A reliable checkpoint and recovery design must account for more than a normal successful execution.

| Failure condition | Required handling |
|---|---|
| Crash before commit record becomes durable | Treat transaction as incomplete |
| Crash after durable commit | Preserve committed changes |
| Dirty page without durable WAL | Do not flush that page |
| Page already contains an operation | Avoid unnecessary redo |
| Multiple updates to one page | Preserve earliest recLSN |
| Multiple active transactions | Recover each transaction independently |
| No valid checkpoint | Begin recovery from an earlier WAL position |
| Invalid page identifier | Reject the operation |
| Unknown transaction | Reject the operation |
| Repeated page flush | Treat an already clean page as a no-op |
| Invalid durable LSN | Reject the flush request |
| Recovery-generated modifications | Record compensation information |

A production recovery implementation must also handle interrupted recovery, log truncation, partial page writes, corrupted WAL, concurrent transactions, transaction dependencies and storage-device failures.

## 14. Performance Considerations

### 14.1 Checkpoint frequency

Checkpoint frequency influences recovery duration and storage I/O.

A checkpoint that is too frequent can increase write pressure.

A checkpoint that is too infrequent can increase recovery work.

### 14.2 WAL indexing

The implementations use ordered log structures and transaction-specific lookup mechanisms.

The SQL schema indexes:

- Engine and transaction identifiers.
- Engine and page identifiers.
- WAL record types.
- Checkpoint completion positions.

These indexes support transaction reconstruction and page-oriented recovery queries.

### 14.3 Dirty-page management

Tracking only dirty pages avoids repeatedly processing every database page during checkpoint analysis.

The earliest dirty-page recLSN gives a conservative starting point for redo.

### 14.4 Buffer-pool sizing

A larger buffer pool can reduce physical reads but may allow more dirty pages to accumulate.

The relationship between buffer-pool capacity, dirty-page thresholds, writeback frequency and checkpoint activity influences recovery performance.

### 14.5 Recovery complexity

Let:

- N represent the number of durable WAL records examined.
- P represent the number of pages.
- T represent the number of transactions.
- U represent the number of operations requiring undo.

The educational implementations use:

| Operation | Approximate complexity |
|---|---|
| WAL append | O(1) amortized |
| WAL LSN lookup | O(1) with indexed storage |
| Page lookup | O(1) average with hash maps |
| Ordered page lookup | O(log P) with ordered maps |
| Dirty-page capture | O(P) |
| Transaction analysis | O(N) |
| Redo scan | O(N) |
| Transaction-history grouping | O(N) |
| Undo processing | O(U) |
| Final page flush | O(P) |

Actual database recovery performance depends on WAL volume, storage latency, page organization, indexing, concurrency and checkpoint metadata.

## 15. Security and Reliability Considerations

Database recovery is also a durability and integrity problem.

Important controls include:

- Restricting access to WAL and data files.
- Protecting checkpoint metadata from unauthorized modification.
- Validating WAL record ordering.
- Preserving durable transaction boundaries.
- Avoiding premature WAL recycling.
- Protecting recovery logs and diagnostic reports.
- Verifying storage integrity.
- Maintaining backups independently of checkpoints.
- Testing recovery using realistic failure scenarios.

WAL records can contain sensitive information. Their access, retention and archival policies should therefore be consistent with database security requirements.

Recovery metadata should not be treated as trusted merely because it was generated by an earlier database process.

## 16. Important Limitations

These implementations are educational storage-engine models, not production database engines.

| Capability | Implemented model | Production requirement |
|---|---|---|
| WAL | In-memory ordered records | Durable, crash-safe WAL storage |
| LSN | Sequential integer | Engine-specific log sequence management |
| Dirty pages | In-memory page objects | Concurrent buffer manager |
| Checkpoints | Dirty-page and transaction snapshots | Atomic and recoverable checkpoint metadata |
| Redo | Page-LSN comparison | Complete physiological or logical redo |
| Undo | Old-value restoration | Transaction chains and recovery-safe undo |
| CLR | Compensation records | Complete undo-next processing |
| Durability | Simulated flush boundary | Verified stable-storage persistence |
| Concurrency | Simplified sequential execution | Locks, latches and isolation management |
| Storage | Simulated disk map | Real page files and I/O management |

The Java implementation intentionally concentrates on service boundaries and domain modeling. Its sample execution demonstrates the normal transaction and checkpoint workflow, not a complete recovery invocation.

The JavaScript implementation models asynchronous coordination but does not perform physical disk I/O.

The SQL implementation stores recovery metadata relationally. PostgreSQL itself does not use these educational tables to perform native database crash recovery.

The Python and C++ recovery models illustrate the major recovery phases but do not implement the full ARIES protocol, including complete transaction log-chain traversal, restartable undo and all compensation-record semantics.

## 17. Verification Scenarios

The following scenarios are represented across the implementations:

| Scenario | Expected behavior |
|---|---|
| Committed transaction with unflushed page | Redo preserves the modification |
| Active transaction at checkpoint | Transaction remains eligible for undo |
| Update after checkpoint | WAL is considered during recovery |
| Multiple updates to one page | Earliest recovery LSN is preserved |
| Page already flushed | Its persistent value survives a crash |
| Recovery with no incomplete transactions | Committed state remains unchanged |
| Invalid WAL flush boundary | Operation is rejected |
| Data-page flush before WAL durability | Durability violation is reported |
| Unknown page | Validation error |
| Unknown or inactive transaction | Transaction operation is rejected |

The expected account values in the principal demonstration are:

| Account | Initial value | Final recovered value |
|---|---:|---:|
| ACCOUNT_101 | 1,000 | 1,100 |
| ACCOUNT_202 | 2,000 | 2,000 |
| ACCOUNT_303 | 3,000 | 3,500 |

The result demonstrates the distinction between durable committed changes, dirty cached pages and incomplete transactions.
