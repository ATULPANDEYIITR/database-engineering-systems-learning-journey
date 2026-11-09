# Write-Ahead Logging: Durability and Crash Recovery

## 1. Technical Scope

Write-Ahead Logging (WAL) is a database reliability mechanism that records changes in a sequential log before the corresponding modified data pages are written to persistent storage.

The central principle is:

**The log record describing a change must become durable before the modified database page is allowed to become durable.**

WAL separates transaction durability from data-page persistence. A database can acknowledge a committed transaction even when its modified data pages remain in memory, provided the required log records have been safely persisted.

The implementations demonstrate transaction logging, log sequence numbers, commit records, checkpoints, integrity verification, recovery analysis, REDO, and UNDO.

## 2. Fundamental Concepts

### 2.1 Write-Ahead Logging

A database maintains two important categories of information:

| Component | Responsibility |
|---|---|
| Write-Ahead Log | Records transaction operations and their ordering |
| Data pages | Store the actual database records |
| Transaction metadata | Tracks transaction lifecycle and outcomes |
| Checkpoint metadata | Identifies recovery progress and relevant state |

Consider a banking transaction that transfers 200 units from account A to account B.

Initial state:

| Account | Balance |
|---|---:|
| A | 1000 |
| B | 500 |

Proposed changes:

| Account | Old value | New value |
|---|---:|---:|
| A | 1000 | 800 |
| B | 500 | 700 |

The database records the changes in the WAL before modifying the corresponding persistent pages.

A simplified sequence is:

1. Begin the transaction.
2. Append the first update record.
3. Ensure the update record is durable before flushing its modified page.
4. Append the second update record.
5. Append the commit record.
6. Ensure the commit record is durable.
7. Acknowledge successful transaction completion.

The modified data pages do not need to reach persistent storage before the commit acknowledgment.

### 2.2 Log Sequence Number

A Log Sequence Number (LSN) identifies a position in the WAL.

LSNs establish the ordering of log records.

Example:

| LSN | Transaction | Operation |
|---:|---|---|
| 1 | T1 | BEGIN |
| 2 | T1 | UPDATE A |
| 3 | T1 | UPDATE B |
| 4 | T1 | COMMIT |
| 5 | T2 | BEGIN |
| 6 | T2 | UPDATE A |
| 7 | T2 | UPDATE B |

An LSN is not necessarily a transaction identifier or a timestamp. It identifies a position in the log sequence.

In production database engines, LSNs can be represented as byte positions rather than simple sequential integers.

### 2.3 Transaction Records

The implementations use five record categories.

| Record | Meaning |
|---|---|
| BEGIN | Transaction has started |
| UPDATE | A database value is being modified |
| COMMIT | Transaction has successfully committed |
| ABORT | Transaction has been rolled back |
| CHECKPOINT | Recovery-related state has been recorded |

An UPDATE record stores:

- Transaction identifier
- LSN
- Affected key or page
- Previous value
- New value
- Integrity checksum

Recording the previous value supports UNDO. Recording the new value supports REDO.

## 3. Durability and the Write-Ahead Rule

Durability is the property that committed transactions survive failures covered by the database's durability guarantees.

WAL supports durability by separating log persistence from data-page flushing.

### 3.1 Log Persistence

A log write can pass through several stages:

| Stage | Description |
|---|---|
| Application buffer | The database constructs a log record |
| Operating-system buffer | The record is transferred to operating-system-managed storage buffers |
| Storage device | Data is transferred to persistent storage |
| Durable acknowledgment | The database receives confirmation from its persistence mechanism |

A normal file write or application-level flush does not necessarily guarantee physical persistence.

The implementations use different mechanisms:

- Python uses `flush()` and `os.fsync()`.
- Java uses `FileChannel.force(true)`.
- JavaScript uses Node.js `FileHandle.sync()`.
- C++17 demonstrates stream flushing and explicitly identifies the need for platform-specific synchronization.
- PostgreSQL models WAL concepts through relational records while relying on PostgreSQL's actual storage engine for physical durability.

### 3.2 Commit Durability

A transaction is not considered durably committed merely because its updated values exist in memory.

The commit record must be persisted according to the database's durability policy before success is acknowledged.

The essential ordering is:

Log update records → durable log records → durable commit record → commit acknowledgment.

Data pages may be written later.

### 3.3 Group Commit

Group commit allows multiple transactions to share a log synchronization operation.

Instead of forcing storage synchronization independently for every transaction, a database can collect several commit records and persist them together.

Benefits include:

- Reduced synchronization overhead.
- Improved transaction throughput.
- Better utilization of storage devices.

The trade-off is that transactions waiting in the same group experience synchronization latency.

The supplied implementations prioritize clarity and individually synchronized writes rather than implementing concurrent group commit.

## 4. Crash Recovery

Crash recovery restores database consistency after an unexpected interruption.

A database may contain:

- Committed transactions whose data pages were not flushed.
- Incomplete transactions whose changes reached some data pages.
- Log records that were written but whose associated transaction never committed.
- Partially written final log records.

Recovery must distinguish these situations.

### 4.1 Recovery Phases

The implementations demonstrate three principal phases.

| Phase | Purpose |
|---|---|
| Analysis | Identify transaction outcomes |
| REDO | Reapply operations that might not have reached data pages |
| UNDO | Reverse operations belonging to incomplete transactions |

The overall workflow is:

    Durable WAL
        |
        v
    Analysis
        |
        +---- Identify committed transactions
        |
        +---- Identify incomplete transactions
        |
        v
    REDO
        |
        +---- Replay committed operations
        |
        +---- Replay operations requiring recovery
        |
        v
    UNDO
        |
        +---- Reverse incomplete transactions
        |
        v
    Recovery completion

### 4.2 Analysis

Analysis examines the log and determines the transaction outcome.

For example:

| Transaction | BEGIN | UPDATE | COMMIT | Classification |
|---|---|---|---|---|
| T1 | Yes | Yes | Yes | Committed |
| T2 | Yes | Yes | No | Incomplete |
| T3 | Yes | No | Yes | Committed |
| T4 | Yes | No | No | Incomplete |

A transaction with a durable commit record is classified as committed.

A transaction with no terminal record is treated as incomplete.

An explicitly aborted transaction is not treated as a successful transaction.

### 4.3 REDO

REDO replays logged changes that might not have reached their corresponding data pages before a crash.

For the banking example:

- T1 changes account A from 1000 to 800.
- T1 changes account B from 500 to 700.
- T1 commits.

If the database crashes before flushing either modified page, recovery must reproduce both changes.

The committed transaction's new values are applied again.

REDO must be safe when an operation has already reached storage.

A production database commonly uses pageLSN information to determine whether a particular operation has already been applied to a page.

### 4.4 UNDO

UNDO reverses changes made by transactions that did not successfully commit.

Suppose T2 modifies:

| Account | Original value | Uncommitted value |
|---|---:|---:|
| A | 800 | 600 |
| B | 700 | 900 |

The transaction crashes before committing.

Recovery reverses the changes:

| Account | Restored value |
|---|---:|
| A | 800 |
| B | 700 |

UNDO generally processes log records in reverse order because later modifications must be reversed before earlier modifications.

### 4.5 Combined REDO and UNDO Example

The Python, JavaScript, C++17 and Java 17 demonstrations execute this scenario:

| Transaction | Operation | Result |
|---|---|---|
| T1 | Set A to 1000 | Logged |
| T1 | Set B to 500 | Logged |
| T1 | Commit | Durable |
| T2 | Set A to 800 | Logged |
| T2 | Set B to 700 | Logged |
| T2 | Crash before commit | Incomplete |

Recovery performs REDO for T1 and T2, followed by UNDO for T2.

Expected recovered state:

| Account | Recovered value |
|---|---:|
| A | 1000 |
| B | 500 |

This example demonstrates why committed and incomplete transactions must be treated differently.

## 5. Checkpoints

A checkpoint records recovery-related information so that a database does not always need to examine its entire historical log.

A checkpoint can contain:

- Checkpoint LSN.
- Active transaction identifiers.
- Dirty-page information.
- Relevant recovery metadata.

### 5.1 Dirty Pages

A dirty page is a database page modified in memory but not yet written to its persistent storage location.

A dirty-page table helps identify which pages may require REDO.

Example:

| Page | Last modification LSN | Dirty |
|---|---:|---|
| Account A | 18 | Yes |
| Account B | 21 | Yes |
| Inventory 101 | 14 | No |

The checkpoint identifies recovery information relevant to outstanding page writes.

### 5.2 Checkpoint Types

**Sharp checkpoint**

A sharp checkpoint attempts to flush relevant dirty pages before establishing the checkpoint boundary.

**Fuzzy checkpoint**

A fuzzy checkpoint allows normal database activity to continue while checkpoint information is collected.

Fuzzy checkpoints generally reduce operational interruption.

They require additional metadata to identify active transactions and pages that may still need recovery.

### 5.3 Checkpoint Limitations

A checkpoint does not automatically mean that all earlier WAL records can be deleted.

A database must retain every log record still required for:

- Crash recovery.
- Active transactions.
- Replication.
- Archiving.
- Backup recovery.
- Other configured durability mechanisms.

The SQL and programming examples use simplified checkpoint representations rather than implementing a production fuzzy checkpoint protocol.

## 6. Torn Writes and WAL Integrity

A torn write occurs when a storage operation does not complete as intended, potentially leaving only part of a page or record updated.

WAL helps databases recover from interrupted operations, but the database must also detect incomplete or damaged log records.

### 6.1 Checksums

The examples use CRC32 in the Python, JavaScript, C++17 and Java implementations.

A checksum detects accidental corruption of a record.

For example:

| Field | Original | Corrupted |
|---|---|---|
| LSN | 10 | 10 |
| Account | A | A |
| Old value | 1000 | 1000 |
| New value | 800 | 900 |
| Checksum | Original checksum | Invalid checksum |

The modified record fails integrity validation.

CRC32 is suitable for demonstrating accidental corruption detection. It is not a cryptographic authentication mechanism.

### 6.2 Incomplete Final Records

A process may terminate during the final WAL append.

The resulting file can contain complete records followed by an incomplete final line.

The Python, JavaScript and Java implementations discard an incomplete final record and truncate the file to its last validated record boundary.

A malformed complete record is treated as corruption rather than silently ignored.

The C++ implementation uses a simpler text-file format and rejects malformed records. It does not implement the same torn-tail repair procedure.

### 6.3 Idempotent Recovery

Recovery should not repeatedly damage data when recovery itself is interrupted or restarted.

An operation is idempotent when repeating it produces the same final state.

The demonstrations use:

- Deterministic replay order.
- Previous and new values.
- Explicit abort records.
- LSN-based ordering.

The implementations verify that a second recovery produces the same database values.

Production engines require more extensive recovery bookkeeping, including pageLSN checks and compensation log records.

## 7. Pulling the Concepts Together: Recovery Architecture

The major components have distinct responsibilities.

| Component | Responsibility |
|---|---|
| Transaction manager | Controls transaction lifecycle |
| WAL manager | Appends and persists log records |
| Buffer manager | Maintains modified pages |
| Checkpoint manager | Captures recovery progress |
| Recovery manager | Performs analysis, REDO and UNDO |
| Storage manager | Persists database pages |

A simplified interaction is:

    Transaction Manager
            |
            v
       WAL Manager
            |
            v
      Durable Log
            |
            +------------------+
            |                  |
            v                  v
      Buffer Manager     Recovery Manager
            |                  |
            v                  |
       Data Pages <-------------+
            |
            v
      Persistent Storage

The WAL manager must coordinate with the buffer manager to preserve write-ahead ordering.

The recovery manager uses the persisted log to reconstruct the required database state.

## 8. Python Implementation

The Python file provides a self-contained storage simulation.

### Implemented mechanisms

| Component | Implementation |
|---|---|
| WAL record | Frozen dataclass |
| Record categories | Enum |
| Integrity | CRC32 |
| Persistence | File append, flush and fsync |
| Transaction state | Dictionary-backed transaction registry |
| Modified pages | Dictionary |
| Dirty-page tracking | Set |
| Recovery | Analysis, REDO and UNDO |
| Validation | Assertions and exceptions |
| Temporary storage | TemporaryDirectory |

### Important design decisions

`WALRecord` is immutable, preventing accidental modification of previously constructed log records.

`DurableWAL` separates log persistence from transaction processing.

`WALDatabase` implements the transaction and recovery logic.

The `update()` operation appends the WAL record before changing the in-memory database.

The `commit()` operation records COMMIT before changing the transaction state to COMMITTED.

`recover()` reconstructs transaction outcomes and restores the database.

The implementation detects invalid checksums and incomplete final records.

The example deliberately uses a logical key-value database rather than actual disk pages.

## 9. JavaScript Implementation

The JavaScript implementation focuses on asynchronous persistence and event-driven transaction monitoring.

### Implemented mechanisms

| Component | Implementation |
|---|---|
| Persistence | Node.js file handles |
| Synchronization | `FileHandle.sync()` |
| Concurrent append ordering | Promise queue |
| Transaction state | Objects and Map |
| Dirty-page tracking | Set |
| Event monitoring | EventEmitter |
| Integrity | CRC32 |
| Recovery | Analysis, REDO and UNDO |

### Important design decisions

The WAL manager serializes concurrent append operations through a promise chain.

This prevents multiple asynchronous callers from allocating and writing the same LSN.

The transaction manager emits events for:

- Transaction creation.
- Updates.
- Commit.
- Abort.
- Checkpoint completion.
- Recovery analysis.
- Recovery completion.

Event-driven monitoring separates storage operations from operational visibility.

The implementation uses Node.js standard-library features and does not require external npm packages.

The promise queue provides ordering within one process. It is not a distributed locking mechanism and does not provide multi-process coordination.

## 10. C++17 Implementation

The C++ implementation emphasizes explicit domain modeling and low-level storage-engine structure.

### Implemented mechanisms

| Component | Implementation |
|---|---|
| WAL records | Struct |
| Record categories | Enum class |
| Record storage | Vector |
| Database pages | Map |
| Active transaction tracking | Map |
| Dirty-page tracking | Set |
| Integrity | CRC32 |
| Persistence | Binary file stream |
| Recovery | Ordered log traversal |

### Important design decisions

The `WALRecord` structure contains the complete logical record.

`DurableWAL` manages sequential LSN allocation and append operations.

`StorageEngine` manages database pages and transaction transitions.

The `std::map` container provides deterministic key ordering and logarithmic lookup.

The reverse iterator is used for UNDO processing.

The implementation uses standard C++17 facilities without external dependencies.

The file stream's `flush()` operation does not guarantee physical durability. A production implementation must use an appropriate platform-specific persistence operation, such as `fsync()` or an equivalent storage synchronization interface.

## 11. Java 17 Implementation

The Java implementation presents an enterprise-oriented storage architecture with explicit service boundaries.

### Implemented mechanisms

| Component | Implementation |
|---|---|
| WAL record | Immutable record |
| Transaction states | Enum |
| Record categories | Enum |
| Persistence | FileChannel |
| Durability request | `force(true)` |
| Integrity | CRC32 |
| Transaction processing | TransactionService |
| Storage | HashMap |
| Dirty-page tracking | HashSet |
| Recovery | Dedicated recovery method |

### Important design decisions

The immutable `WALRecord` prevents mutation of established log entries.

`DurableWAL` handles record construction, persistence and validation.

`TransactionService` manages transaction state and logical page changes.

Custom exceptions distinguish storage and integrity failures from ordinary validation errors.

The use of `Map.copyOf()` provides immutable database snapshots for inspection.

The implementation uses Java 17 standard-library functionality without third-party dependencies.

## 12. PostgreSQL Implementation

The SQL file models a relational WAL laboratory using a dedicated `wal_lab` schema.

It is an educational implementation of WAL concepts. It does not replace or modify PostgreSQL's internal WAL machinery.

### Relational structure

| Table | Responsibility |
|---|---|
| `wal_transactions` | Transaction lifecycle |
| `database_pages` | Logical database page values |
| `wal_records` | Append-only transaction records |
| `wal_checkpoints` | Checkpoint metadata |
| `recovery_runs` | Recovery execution |
| `recovery_events` | Individual recovery operations |

### Relationships

    wal_transactions
          |
          v
      wal_records
          |
          +------------------+
          |                  |
          v                  v
      database_pages    recovery_events
          |
          v
      wal_checkpoints

### Database integrity

The implementation uses:

- Primary keys.
- Foreign keys.
- Unique constraints.
- Check constraints.
- Enum types.
- Identity-generated LSNs.
- Indexes for transaction and page retrieval.
- Triggers for record validation.
- Functions for checksums.
- Procedures for transaction operations.
- Views for reporting.

### Transaction processing

`begin_transaction()` creates a transaction and records BEGIN.

`update_page()` appends UPDATE before modifying the logical page.

`commit_transaction()` appends COMMIT and updates the transaction status.

`abort_transaction()` restores previous values in reverse LSN order.

`create_checkpoint()` records active transaction and dirty-page metadata.

`recover_database()` performs the recovery phases.

### Reporting

The script includes queries for:

- WAL sequence inspection.
- Transaction lifecycle reporting.
- Checksum validation.
- Record aggregation.
- Recovery phase statistics.
- Unresolved transaction detection.
- Page-state inspection.
- Transaction completion eligibility.
- Recovery history.

The SQL workload is enclosed in a transaction so that the demonstration can be validated as a consistent unit.

## 13. Important Distinctions

### 13.1 WAL Versus Data Files

| WAL | Data files |
|---|---|
| Records changes | Store current database values |
| Usually sequentially appended | Modified through page writes |
| Supports recovery | Provides the database's persisted state |
| Contains transaction history required for recovery | Contains the current page representation |

### 13.2 REDO Versus UNDO

| REDO | UNDO |
|---|---|
| Reapplies changes | Reverses changes |
| Uses new values | Uses previous values |
| Handles operations that may not have reached pages | Handles incomplete transactions |
| Typically processes records forward | Typically processes records backward |

### 13.3 Checkpoint Versus Commit

A commit records the successful completion of a transaction.

A checkpoint records recovery-related progress.

A checkpoint does not commit transactions, and a commit does not necessarily flush every modified data page.

### 13.4 Logical WAL Versus Physical WAL

Logical logging records operations in terms of logical changes, such as modifying an account balance.

Physical logging records changes at the storage-page or byte level.

Real database engines may combine logical, physical and physiological logging approaches.

The examples use logical key-value updates to keep recovery behavior understandable.

## 14. ARIES and Production Recovery

The examples demonstrate the fundamental recovery concepts, but they are not complete implementations of ARIES.

ARIES stands for Algorithms for Recovery and Isolation Exploiting Semantics.

It is a recovery methodology associated with transaction logging and database systems.

Important ARIES concepts include:

| Concept | Function |
|---|---|
| Analysis | Reconstruct transaction and dirty-page information |
| REDO | Repeat history where necessary |
| UNDO | Reverse incomplete transaction operations |
| pageLSN | Identifies the latest log record applied to a page |
| Compensation Log Record | Records an undo operation |
| UndoNextLSN | Identifies the next log position for rollback |
| Fuzzy checkpoint | Records checkpoint information without requiring a complete system-wide stop |

An important distinction is that ARIES repeats history during REDO, including changes belonging to transactions that were incomplete at the time of the crash. UNDO subsequently reverses those incomplete transactions.

The simplified implementations replay incomplete transaction updates during REDO and reverse them during UNDO, illustrating the same broad recovery outcome without implementing the complete ARIES protocol.

### Compensation Log Records

A Compensation Log Record (CLR) records the effect of an undo operation.

CLRs allow recovery to resume safely if another crash occurs during rollback.

A production implementation must also manage undo progress, log retention and transaction recovery state.

### PageLSN

A pageLSN identifies the latest log record reflected in a page.

Before applying an update during REDO, the recovery manager can compare the record's LSN with the pageLSN.

This avoids applying an already reflected change unnecessarily.

None of the five implementations constitutes a complete pageLSN-based ARIES engine.

## 15. Performance Considerations

### Sequential Logging

Sequential log appends generally provide better storage efficiency than random writes.

The WAL is commonly designed to exploit sequential storage behavior.

### Synchronization Cost

Durability synchronization can dominate transaction latency.

Group commit reduces the number of synchronization operations by allowing multiple transactions to share persistence work.

### Checkpoint Frequency

Frequent checkpoints can reduce recovery work but increase background storage activity.

Infrequent checkpoints reduce checkpoint overhead but may increase recovery time.

### Recovery Complexity

For a WAL containing N records:

- Analysis requires O(N) time.
- REDO requires O(N) time in the simplified model.
- UNDO requires O(N) time.
- Reverse traversal requires access to the log in reverse order.

The in-memory examples retain records in collections. Production databases typically use segmented WAL files, bounded memory structures and optimized recovery metadata.

## 16. Security and Failure Considerations

WAL files can contain sensitive information.

Security controls should address:

- Restricted file permissions.
- Encryption at rest where required.
- Secure backup storage.
- Access control.
- Integrity validation.
- Monitoring of failed persistence operations.
- Storage-capacity monitoring.
- Safe log retention.
- Replication and archival integrity.

A checksum detects accidental corruption but does not prevent intentional modification.

A production system should also consider:

- Disk exhaustion.
- Storage-device failures.
- Partial writes.
- Concurrent transactions.
- Process termination during commit.
- Recovery interruption.
- Replication lag.
- Backup restoration.
- Log archival failures.

The educational implementations do not provide distributed consensus, replication, encrypted log storage or full physical-page recovery.

## 17. Execution and Validation

| File | Runtime | Execution |
|---|---|---|
| Python | Python 3.10+ | `python wal_recovery.py` |
| JavaScript | Node.js | `node wal_recovery.js` |
| C++17 | C++17 compiler | `g++ -std=c++17 -O2 -Wall -Wextra -pedantic wal.cpp -o wal` followed by `./wal` |
| Java | Java 17 | `javac WALRecovery.java` followed by `java WALRecovery` |
| PostgreSQL | PostgreSQL 14+ | `psql -d database_name -f wal_recovery.sql` |

The examples create demonstration WAL files in the current working directory, except the Python and JavaScript demonstrations, which use temporary directories.

The PostgreSQL script creates and populates the `wal_lab` schema. It drops an existing schema with that name before recreating it.

Expected recovery values:

| Key | Expected value |
|---|---:|
| account_A | 1000 |
| account_B | 500 |

Validation checks include:

- Correct LSN progression.
- Record checksum verification.
- Rejection of malformed records.
- Prevention of invalid transaction transitions.
- Persistence before page modification.
- REDO of committed transactions.
- UNDO of incomplete transactions.
- Recovery completion.
- Repeated recovery consistency.

## 18. Implementation Limitations

These programs are educational storage-engine models rather than production database implementations.

| Capability | Demonstrated | Production completeness |
|---|---|---|
| Sequential WAL records | Yes | Simplified |
| Transaction lifecycle | Yes | Simplified |
| Commit logging | Yes | Simplified |
| Write-ahead ordering | Yes | Simplified |
| Checksums | Yes | Limited |
| Torn-tail detection | Yes, in selected implementations | Limited |
| Checkpoints | Yes | Simplified |
| REDO | Yes | Simplified |
| UNDO | Yes | Simplified |
| PageLSN | No | Not implemented |
| Compensation log records | No | Not implemented |
| Concurrent recovery workers | No | Not implemented |
| Group commit | No | Not implemented |
| Replication | No | Not implemented |
| Physical page recovery | No | Not implemented |
| Distributed durability | No | Not implemented |

The SQL implementation uses ordinary PostgreSQL transactions to persist its educational records. Its recovery procedure demonstrates logical transaction recovery, not PostgreSQL server crash recovery.

The file-backed implementations also have limitations involving multi-process coordination, storage-device behavior and platform-specific synchronization.

These distinctions are important when translating WAL concepts into an actual database storage architecture.
