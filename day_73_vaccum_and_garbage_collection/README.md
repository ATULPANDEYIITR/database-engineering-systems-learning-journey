# Vacuum and Garbage Collection in PostgreSQL

## 1. Technical Scope

PostgreSQL uses Multi-Version Concurrency Control (MVCC) to support concurrent transactions without requiring every reader to block writers.

MVCC maintains multiple physical versions of a logical row. When a transaction updates or deletes a row, PostgreSQL does not immediately overwrite or physically remove the previous tuple version.

These obsolete versions are called **dead tuples** when they are no longer visible to any transaction that might still require them.

Vacuuming is the database maintenance process responsible for identifying and reclaiming eligible dead-tuple storage.

The implementations cover:

- MVCC tuple-version creation.
- Dead tuple accumulation.
- Transaction visibility horizons.
- Standard VACUUM.
- VACUUM FULL.
- ANALYZE.
- Transaction ID freezing.
- Autovacuum thresholds and scheduling.
- Heap storage and page management.
- Storage monitoring and maintenance reporting.

## 2. PostgreSQL MVCC and Dead Tuples

### 2.1 Multi-Version Concurrency Control

Each PostgreSQL heap tuple contains transaction metadata that determines its visibility.

Two important transaction identifiers are:

| Attribute | Meaning |
|---|---|
| `xmin` | Transaction ID associated with tuple creation |
| `xmax` | Transaction ID associated with tuple deletion or replacement |

An inserted tuple receives an insertion transaction identifier.

When another transaction updates or deletes that tuple, PostgreSQL records the deleting transaction identifier in its tuple metadata.

An UPDATE normally creates a new tuple version. The previous version remains physically present until it becomes safe to remove.

### 2.2 Tuple Lifecycle

The implementations use the following conceptual states:

| State | Meaning |
|---|---|
| LIVE | Current logical row version |
| DEAD | Obsolete version awaiting safe cleanup |
| FROZEN | Tuple whose transaction visibility metadata has been frozen |
| REMOVED | Tuple removed from the simulation's active storage |

Conceptual lifecycle:

    INSERT
      |
      v
    LIVE
      |
      | UPDATE or DELETE
      v
    DEAD
      |
      | No relevant active snapshot requires it
      v
    REMOVED

A PostgreSQL tuple does not necessarily follow this exact application-level state machine. PostgreSQL manages visibility through transaction metadata, snapshots, tuple headers, and vacuum processing.

### 2.3 Why Dead Tuples Accumulate

Dead tuples arise from:

- UPDATE operations.
- DELETE operations.
- Repeated changes to frequently modified records.
- Bulk data replacement.
- High-write workloads.
- Transactions that delay cleanup eligibility.

Consider an order record:

| Operation | Amount | Tuple condition |
|---|---:|---|
| Initial insertion | 500 | Original version |
| First update | 650 | Original version becomes obsolete |
| Second update | 800 | Previous version becomes obsolete |
| Third update | 900 | Another obsolete version is created |

The logical database contains one current order, but its physical heap may temporarily contain several tuple versions.

Dead tuples consume storage and can increase the amount of work required for scans and maintenance.

## 3. Transaction Visibility and Vacuum Safety

### 3.1 Visibility Horizon

A dead tuple cannot be removed merely because a DELETE statement has completed.

An older transaction might still hold a snapshot that requires access to an earlier row version.

Vacuum must respect the oldest relevant transaction visibility horizon.

The Python, JavaScript, C++17, and Java 17 implementations include transaction registries that track active transactions.

Example:

    Transaction A begins
          |
          v
    Transaction B deletes a row
          |
          v
    Transaction B commits
          |
          v
    VACUUM executes
          |
          v
    Older snapshot still active
          |
          v
    Dead tuple remains
          |
          v
    Transaction A completes
          |
          v
    VACUUM can remove eligible tuple

This illustrates why long-running transactions can interfere with cleanup.

### 3.2 Transaction Identifiers

PostgreSQL transaction IDs have finite-width storage.

Transaction ID wraparound is a critical database safety concern. PostgreSQL freezes sufficiently old tuples to prevent historical transaction identifiers from being interpreted incorrectly after wraparound.

Important concepts include:

- `xmin`
- `xmax`
- `relfrozenxid`
- Transaction ID age
- Freeze thresholds
- Aggressive vacuuming
- Wraparound protection

The implementations model freezing through a separate `FROZEN` state. This is an educational abstraction rather than an implementation of PostgreSQL's internal tuple-header representation.

## 4. Standard VACUUM

Standard `VACUUM` identifies dead tuples that are safe to remove and makes their storage available for reuse.

Example:

    VACUUM orders;

A more informative operation is:

    VACUUM (VERBOSE, ANALYZE) orders;

### 4.1 What Standard VACUUM Does

- Identifies obsolete tuple versions.
- Checks whether tuples are removable.
- Reclaims eligible dead-tuple space.
- Makes available space reusable by future operations.
- Performs relevant index cleanup.
- Maintains visibility information.
- Supports transaction ID freezing.
- Can update planner statistics when ANALYZE is specified.

Standard VACUUM generally does not shrink the relation's physical file to return all reclaimed space to the operating system.

For example:

| Measurement | Before | After |
|---|---:|---:|
| Physical heap allocation | 100 MB | 100 MB |
| Live data | 65 MB | 65 MB |
| Reusable space | 10 MB | 35 MB |
| Dead tuple storage | 25 MB | Reduced |

These values are illustrative. Actual storage behavior depends on page layout, tuple visibility, free space, indexes, and concurrent workloads.

### 4.2 Visibility Map

PostgreSQL maintains a visibility map for heap relations.

It tracks page-level information, including:

- All-visible pages.
- All-frozen pages.

This information supports index-only scans and helps vacuum avoid unnecessary work on pages that do not require processing.

The five programs model tuple visibility and freezing but do not reproduce the internal visibility-map implementation.

### 4.3 Free Space Map

The Free Space Map (FSM) records information about available space in relation pages.

It helps PostgreSQL locate pages with sufficient free space for new tuple versions.

The educational programs use explicit page-capacity tracking to demonstrate storage reuse.

PostgreSQL's actual FSM uses a separate internal structure and is not equivalent to the simplified page allocation logic in these programs.

## 5. VACUUM FULL

`VACUUM FULL` performs a table rewrite.

Example:

    VACUUM (FULL, VERBOSE, ANALYZE) orders;

Its primary purpose is to compact the relation and release unused filesystem space.

### 5.1 Standard VACUUM Versus VACUUM FULL

| Characteristic | Standard VACUUM | VACUUM FULL |
|---|---|---|
| Dead tuple cleanup | Yes | Yes |
| Relation rewrite | No | Yes |
| Compacts physical storage | Limited | Yes |
| Can shrink relation file | Generally no | Yes |
| ACCESS EXCLUSIVE lock | No | Yes |
| Additional temporary disk space | Usually limited | Potentially substantial |
| Suitable for routine maintenance | Yes | Not normally |

`VACUUM FULL` requires an `ACCESS EXCLUSIVE` lock on the target relation.

This can block concurrent readers and writers.

It also needs additional disk capacity while constructing the rewritten relation.

It should not be treated as the default response to ordinary dead tuple accumulation.

## 6. ANALYZE and Query Planner Statistics

`ANALYZE` collects statistical information about table contents.

The PostgreSQL query planner uses these statistics to estimate:

- Row counts.
- Value distributions.
- Column selectivity.
- Data correlations.
- Expected query costs.

Example:

    ANALYZE orders;

A combined operation is:

    VACUUM (ANALYZE) orders;

VACUUM and ANALYZE perform different responsibilities.

| Operation | Responsibility |
|---|---|
| VACUUM | Dead tuple cleanup and storage maintenance |
| ANALYZE | Query planner statistics collection |

Removing dead tuples does not automatically mean that the query planner has sufficiently current statistics.

The Python implementation exposes an explicit `analyze()` method. The PostgreSQL implementation also includes ANALYZE eligibility and storage-reporting mechanisms.

## 7. Autovacuum

Autovacuum is PostgreSQL's background maintenance mechanism.

It automatically schedules vacuuming and statistics collection based on configurable thresholds.

It is not simply a timer that runs VACUUM at fixed intervals.

### 7.1 Vacuum Threshold

A simplified traditional vacuum threshold is:

\[
T_v = T_b + S_v \times N
\]

Where:

- \(T_v\) = vacuum threshold.
- \(T_b\) = base vacuum threshold.
- \(S_v\) = vacuum scale factor.
- \(N\) = estimated number of live tuples.

For example:

| Parameter | Value |
|---|---:|
| Base threshold | 50 |
| Scale factor | 0.20 |
| Estimated live tuples | 10,000 |
| Calculated threshold | 2,050 |

The simplified rule is:

\[
D > T_v
\]

Where \(D\) represents the estimated number of dead tuples.

Actual PostgreSQL autovacuum behavior also incorporates additional considerations, including insert-triggered vacuuming, worker availability, cost throttling, transaction ID age, and database configuration.

### 7.2 Analyze Threshold

A simplified analyze threshold is:

\[
T_a = A_b + S_a \times N
\]

Where:

- \(A_b\) = base analyze threshold.
- \(S_a\) = analyze scale factor.
- \(N\) = estimated live tuples.

The implementations evaluate vacuum and analyze thresholds independently.

### 7.3 Autovacuum Configuration

The PostgreSQL implementation demonstrates relation-specific configuration:

| Parameter | Purpose |
|---|---|
| `autovacuum_enabled` | Enables or disables automatic maintenance for a relation |
| `autovacuum_vacuum_threshold` | Base vacuum threshold |
| `autovacuum_vacuum_scale_factor` | Relative vacuum threshold |
| `autovacuum_analyze_threshold` | Base analyze threshold |
| `autovacuum_analyze_scale_factor` | Relative analyze threshold |
| `autovacuum_vacuum_cost_limit` | Maintenance cost budget |

These settings should be selected according to workload characteristics.

High-write tables may require more aggressive maintenance settings than relatively static tables.

### 7.4 Autovacuum Failure Conditions

Important operational conditions include:

- Long-running transactions.
- Idle transactions left open.
- Insufficient autovacuum workers.
- Cost-based maintenance delays.
- High write rates.
- Large indexes.
- Disk-space limitations.
- Lock contention.
- Excessive transaction ID age.

A configured autovacuum policy does not guarantee that a maintenance worker will immediately execute.

## 8. VACUUM FREEZE and Transaction ID Wraparound

PostgreSQL uses freezing to protect transaction visibility from transaction ID wraparound.

Old transaction identifiers cannot safely be interpreted indefinitely.

Freezing marks eligible old tuple transaction metadata so that old transaction IDs do not cause incorrect visibility decisions.

Example:

    VACUUM (FREEZE, VERBOSE) orders;

Important monitoring attributes include:

| Attribute | Purpose |
|---|---|
| `relfrozenxid` | Relation's frozen transaction ID horizon |
| `age(relfrozenxid)` | Approximate transaction ID age |
| `autovacuum_freeze_max_age` | Configuration controlling aggressive wraparound protection |

Wraparound protection is a database correctness requirement, not merely a performance optimization.

A database experiencing severe wraparound risk can enter protective behavior that restricts normal operations.

## 9. Heap Pages and Storage Reclamation

PostgreSQL stores ordinary table data in heap pages.

A page contains tuple versions and associated page-management information.

The educational implementations model pages using fixed tuple capacities.

For example:

    Relation: orders

    Page 0: [LIVE] [DEAD] [LIVE] [LIVE]
    Page 1: [LIVE] [DEAD] [DEAD] [LIVE]
    Page 2: [LIVE] [LIVE] [LIVE] [DEAD]

After eligible cleanup:

    Page 0: [LIVE] [FREE] [LIVE] [LIVE]
    Page 1: [LIVE] [FREE] [FREE] [LIVE]
    Page 2: [LIVE] [LIVE] [LIVE] [FREE]

Free space becomes available for reuse.

The simulation simplifies page allocation and does not reproduce PostgreSQL's actual heap-page layout, line pointers, page headers, FSM, or visibility map.

### 9.1 Storage Measurements

The PostgreSQL implementation uses:

| Function | Measurement |
|---|---|
| `pg_relation_size()` | Main relation storage |
| `pg_indexes_size()` | Index storage |
| `pg_total_relation_size()` | Relation plus associated storage |
| `pg_size_pretty()` | Human-readable storage representation |

The monitoring views combine these measurements with statistics from `pg_stat_user_tables`.

### 9.2 Important Statistics

| Attribute | Interpretation |
|---|---|
| `n_live_tup` | Estimated live tuples |
| `n_dead_tup` | Estimated dead tuples |
| `n_tup_ins` | Inserted tuples |
| `n_tup_upd` | Updated tuples |
| `n_tup_del` | Deleted tuples |
| `last_vacuum` | Last manual vacuum |
| `last_autovacuum` | Last automatic vacuum |
| `last_analyze` | Last manual analyze |
| `last_autoanalyze` | Last automatic analyze |

These are monitoring estimates and counters, not exact physical tuple inventories.

## 10. Python Implementation

The Python program models vacuuming as a repository of tuple records with explicit state transitions.

### Architecture

| Component | Responsibility |
|---|---|
| `TupleRecord` | Represents an individual tuple version |
| `Table` | Maintains tuple storage and page allocation |
| `TransactionManager` | Tracks active transactions |
| `AutovacuumConfig` | Validates maintenance thresholds |
| `AutovacuumWorker` | Evaluates maintenance eligibility |
| `VacuumReport` | Captures maintenance results |
| `VacuumMode` | Separates standard, full, and freeze operations |

### Important Mechanisms

**Insertion**

Creates a tuple with an insertion transaction identifier.

**Update**

Marks the old version dead and inserts a new version.

**Deletion**

Marks the current tuple version as dead.

**Standard vacuum**

Removes eligible dead versions after checking the transaction visibility horizon.

**Full vacuum**

Reconstructs the simulated page allocation using surviving tuples.

**Freeze**

Marks sufficiently old live tuples as frozen.

**Autovacuum**

Calculates maintenance eligibility using configurable thresholds.

### Validation

The script checks:

- Invalid transaction identifiers.
- Missing tuple identifiers.
- Invalid page capacity.
- Invalid scale factors.
- Duplicate transaction completion.
- Updates against nonexistent tuples.
- Dead tuple accounting.

The simulation uses in-memory collections, so it demonstrates behavior rather than durable PostgreSQL storage.

## 11. JavaScript Implementation

The JavaScript implementation uses an event-driven maintenance architecture.

It emphasizes asynchronous scheduling, encapsulated storage structures, and explicit error handling.

### Architecture

| Component | Responsibility |
|---|---|
| `TransactionRegistry` | Tracks active transaction identifiers |
| `MVCCPage` | Models page capacity |
| `MVCCRelation` | Maintains tuple versions and relation statistics |
| `AutovacuumPolicy` | Evaluates maintenance thresholds |
| `MaintenanceScheduler` | Executes asynchronous maintenance |
| `ValidationError` | Represents invalid operations |
| `MaintenanceError` | Represents maintenance failures |

### Event-Driven Maintenance

The scheduler evaluates current storage statistics before starting maintenance.

Its execution sequence is:

    Request
       |
       v
    Read relation statistics
       |
       v
    Evaluate vacuum policy
       |
       +---- Threshold not reached
       |          |
       |          v
       |        Skip
       |
       +---- Threshold reached
                  |
                  v
              Schedule work
                  |
                  v
              Execute vacuum
                  |
                  v
              Record event
                  |
                  v
              Release worker

The `setImmediate()` operation yields execution to the Node.js event loop before maintenance continues.

The worker prevents overlapping execution through an explicit running-state check.

The model uses an in-memory event history rather than a durable maintenance queue.

## 12. C++17 Implementation

The C++17 program emphasizes explicit domain modeling and storage allocation.

### Architecture

| Component | Responsibility |
|---|---|
| `Tuple` | Stores tuple metadata |
| `Page` | Maintains tuple identifiers and capacity |
| `Relation` | Implements storage operations |
| `TransactionRegistry` | Maintains transaction visibility |
| `AutovacuumPolicy` | Evaluates maintenance requirements |
| `GovernanceEngine` | Coordinates maintenance decisions |
| `VacuumReport` | Captures operation results |

### Design Decisions

- `std::map` maintains tuple records indexed by identifiers.
- `std::set` tracks active transactions in sorted order.
- `std::vector` manages physical page representations.
- `std::optional` represents deletion transaction metadata.
- Enumerations distinguish tuple and vacuum states.
- Exceptions handle invalid storage operations.

The transaction registry provides an efficient lookup of the oldest active transaction using the first element of its ordered set.

The implementation favors explicit ownership and deterministic data structures over additional dependencies.

### Complexity

Let:

- \(N\) = number of tuple records.
- \(P\) = number of pages.
- \(A\) = number of active transactions.

| Operation | Approximate complexity |
|---|---|
| Tuple lookup | \(O(\log N)\) |
| Tuple insertion | \(O(\log N)\) |
| Active transaction insertion | \(O(\log A)\) |
| Oldest transaction lookup | \(O(1)\) |
| Full relation scan | \(O(N)\) |
| Page compaction | \(O(N)\), excluding map-operation overhead |

The simplified page allocator may inspect multiple pages when searching for reusable capacity.

## 13. Java 17 Implementation

The Java program models storage maintenance as an enterprise service architecture.

It uses records for immutable data objects, enumerations for domain states, interfaces for maintenance behavior, and separate services for transaction and maintenance operations.

### Architecture

| Component | Responsibility |
|---|---|
| `Tuple` | Immutable tuple representation |
| `Page` | Page-capacity management |
| `Relation` | Storage and tuple lifecycle |
| `TransactionService` | Transaction management |
| `AutovacuumPolicy` | Immutable maintenance policy |
| `AutovacuumService` | Maintenance eligibility and execution |
| `MaintenanceService` | Vacuum service contract |
| `VacuumReport` | Immutable execution result |

### Enterprise-Oriented Design

**Immutable records**

Tuple updates create replacement records rather than modifying individual record fields.

**Explicit state transitions**

Tuple state changes are validated before replacement.

**Policy separation**

Autovacuum thresholds are represented independently from relation storage.

**Service separation**

Transaction tracking and maintenance execution have distinct responsibilities.

**Optional results**

`Optional<VacuumReport>` distinguishes an executed maintenance operation from a skipped operation.

**Failure handling**

Custom exceptions identify transaction and storage failures.

This architecture demonstrates how database maintenance behavior can be represented through explicit application-level domain services.

It is not a substitute for PostgreSQL's internal maintenance workers.

## 14. PostgreSQL SQL Implementation

The SQL script provides a relational representation of a business workload and its maintenance operations.

### Database Objects

| Object | Purpose |
|---|---|
| `app_users` | Customer records |
| `orders` | Transactional workload |
| `maintenance_log` | Maintenance execution history |
| `autovacuum_policies` | Maintenance threshold configuration |
| `transaction_snapshots` | Application-level transaction audit |
| `table_storage_statistics` | Tuple and maintenance statistics |
| `relation_storage` | Physical relation-size reporting |
| `maintenance_summary` | Aggregated maintenance results |

### Data Integrity

The implementation uses:

- Primary keys.
- Foreign keys.
- Unique constraints.
- Check constraints.
- Identity columns.
- Timestamp defaults.
- Update triggers.
- Performance-oriented indexes.

The `set_order_updated_at()` trigger updates timestamps and increments the order version whenever an order changes.

### Maintenance Functions

| Function | Responsibility |
|---|---|
| `evaluate_vacuum()` | Determines whether configured vacuum thresholds are exceeded |
| `evaluate_analyze()` | Evaluates statistics refresh requirements |
| `record_maintenance()` | Records maintenance results |

The CTE-based query independently evaluates estimated dead tuples against configured thresholds.

### Transaction Handling

The script demonstrates transaction boundaries with `BEGIN` and `COMMIT`.

It also includes an application-level transaction audit table.

This audit table is not PostgreSQL's internal transaction snapshot mechanism.

### Actual Maintenance Commands

The SQL script executes:

- `VACUUM (VERBOSE, ANALYZE)`
- `VACUUM (FULL, VERBOSE, ANALYZE)`
- `VACUUM (FREEZE, VERBOSE, ANALYZE)`
- `ANALYZE` through combined maintenance commands.

VACUUM commands are deliberately placed outside explicit transaction blocks because PostgreSQL does not permit ordinary VACUUM execution inside a transaction block.

## 15. Four Important Maintenance Distinctions

| Mechanism | Primary responsibility | Filesystem space reclamation |
|---|---|---|
| VACUUM | Clean up eligible dead tuples | Usually does not shrink the relation file |
| VACUUM FULL | Rewrite and compact the relation | Can return unused relation space |
| ANALYZE | Refresh query planner statistics | No direct reclamation |
| FREEZE | Protect transaction ID visibility | No direct reclamation |

Autovacuum is the background scheduling and execution mechanism that coordinates routine vacuum and analyze operations.

These mechanisms are related but are not interchangeable.

## 16. Operational Failure Modes

### Long-Running Transactions

A transaction that retains an old snapshot can prevent cleanup of tuples still potentially visible to that snapshot.

Operational controls include:

- Monitoring transaction age.
- Investigating idle transactions.
- Reviewing long-running reporting queries.
- Monitoring replication-related retention horizons.

### Excessive Dead Tuples

A high dead-tuple count can increase maintenance requirements and degrade storage efficiency.

Possible causes include:

- Frequent updates.
- Large delete operations.
- Poorly configured autovacuum thresholds.
- Insufficient maintenance capacity.

### Index Bloat

Dead heap tuples and index bloat are related but distinct storage concerns.

Removing heap dead tuples does not necessarily mean every index has been physically compacted to its minimum possible size.

Index cleanup behavior depends on index type, PostgreSQL version, and vacuum processing.

### Disk-Space Exhaustion

VACUUM FULL may need substantial temporary disk space while rewriting a relation.

Insufficient capacity can cause maintenance failure.

Capacity planning must account for the existing relation, indexes, temporary rewrite requirements, and concurrent workload.

### Autovacuum Contention

Autovacuum workers consume CPU, memory, and storage I/O.

Too little maintenance can allow dead tuples to accumulate. Excessively aggressive maintenance can interfere with application workload performance.

The maintenance configuration must balance both concerns.

### Transaction ID Wraparound

Transaction ID wraparound is a database correctness risk.

Monitoring `age(relfrozenxid)` and the database's configured freeze thresholds is essential.

Wraparound protection must not be disabled as a routine performance optimization.

## 17. Performance and Security Considerations

### Performance

- Prefer routine standard VACUUM over unnecessary full-table rewrites.
- Configure table-specific autovacuum thresholds for high-churn relations.
- Monitor dead tuples and transaction age.
- Review maintenance worker availability.
- Monitor heap and index storage independently.
- Avoid unnecessary long-running transactions.
- Refresh planner statistics after significant data changes.
- Schedule disruptive operations according to workload requirements.

### Security

Database maintenance requires appropriate privileges.

Production maintenance automation should follow these principles:

- Grant only the required database privileges.
- Restrict access to maintenance configuration.
- Avoid constructing SQL commands from untrusted relation names.
- Audit administrative maintenance operations.
- Monitor failed maintenance attempts.
- Protect transaction and operational metadata.
- Use controlled execution identities for scheduled maintenance.

The PostgreSQL script uses fixed relation names in its maintenance commands rather than accepting arbitrary SQL identifiers from external input.

## 18. Limitations of the Implementations

The four programming-language implementations are educational MVCC simulations.

They do not reproduce every internal PostgreSQL storage mechanism.

| PostgreSQL feature | Implementation coverage |
|---|---|
| Tuple versions | Simulated |
| Transaction visibility | Simplified |
| Dead tuple cleanup | Simulated |
| Heap pages | Simplified |
| Standard vacuum | Simulated |
| VACUUM FULL | Simulated compaction |
| Transaction freezing | Simplified |
| Autovacuum thresholds | Modeled |
| Asynchronous maintenance | JavaScript scheduler |
| Visibility map | Not implemented |
| Free Space Map | Simplified page allocation |
| HOT updates | Not implemented |
| Index vacuum internals | Not implemented |
| WAL and crash recovery | Not implemented |
| Parallel vacuum internals | Not implemented |
| Replication feedback | Not implemented |

The PostgreSQL SQL implementation executes actual PostgreSQL maintenance commands and retrieves database statistics.

Its statistics are estimates and should be interpreted accordingly.

## 19. Practical Storage Maintenance Workflow

A production maintenance investigation can follow this sequence:

    Application workload
           |
           v
    Monitor UPDATE and DELETE activity
           |
           v
    Inspect n_dead_tup and relation size
           |
           v
    Inspect active transactions
           |
           v
    Evaluate vacuum thresholds
           |
           v
    Check autovacuum activity
           |
           v
    Execute or allow standard VACUUM
           |
           v
    Refresh planner statistics
           |
           v
    Inspect heap and index sizes
           |
           v
    Monitor transaction ID age
           |
           v
    Consider VACUUM FULL only when justified

This workflow separates tuple cleanup, planner statistics, transaction ID safety, and physical storage reclamation into distinct operational responsibilities.

## 20. Execution Requirements

| Deliverable | Runtime or database | Dependencies |
|---|---|---|
| Python | Python 3.10+ | Standard library |
| JavaScript | Node.js 18+ | Node.js standard library |
| C++17 | C++17 compiler | Standard Template Library |
| Java | Java 17 | Java standard library |
| PostgreSQL | PostgreSQL 15+ | PostgreSQL server and appropriate privileges |

The Python program, JavaScript program, C++17 program, and Java 17 program each execute independently.

The PostgreSQL script creates its own schema and database objects and executes actual maintenance statements against its demonstration tables.
