# Disk and SSD Behavior

## 1. Storage Performance Fundamentals

Disk and SSD performance depends on how data is accessed, how much data is transferred, how requests are queued, and how quickly the storage device completes each operation.

Two distinct performance characteristics are important:

- **Latency:** The time required to complete an I/O request.
- **Throughput:** The amount of data transferred per unit of time.

A storage device can have high sequential throughput but relatively poor random I/O performance. This distinction is particularly important for database systems, virtual machines, transactional applications, and large-file processing.

The five source files implement storage-performance models, workload simulation, enterprise monitoring, benchmark analysis, and relational reporting.

## 2. HDD, SATA SSD, and NVMe SSD

### 2.1 Hard Disk Drive

An HDD stores information magnetically on rotating platters.

Its mechanical components include:

- Magnetic platters.
- Spindle motor.
- Read/write heads.
- Actuator assembly.
- Controller electronics.

An HDD experiences mechanical positioning delays.

Two important components of random-access latency are:

1. **Seek time:** Time required to position the read/write head over the required track.
2. **Rotational latency:** Time spent waiting for the required sector to rotate beneath the head.

Average rotational latency can be estimated using:

\[
L_{\text{rotation}}=\frac{30000}{RPM}
\]

For a 7200 RPM HDD:

\[
L_{\text{rotation}}=\frac{30000}{7200}
\]

\[
L_{\text{rotation}}\approx 4.17\text{ ms}
\]

This value represents average rotational latency, not complete I/O latency. Seek time, controller processing, transfer time, and queueing also contribute.

Sequential access is efficient because the read/write head can transfer neighboring data without repeatedly repositioning.

Random access requires more frequent positioning operations, making it comparatively expensive.

### 2.2 SATA SSD

A SATA SSD uses NAND flash memory rather than rotating magnetic platters.

Its major components include:

- NAND flash memory.
- Flash controller.
- Firmware.
- Flash Translation Layer (FTL).
- DRAM or other mapping structures, depending on the design.
- Error correction mechanisms.

The absence of mechanical positioning reduces access latency.

SATA SSDs are constrained by the SATA interface and its associated protocol overhead.

A SATA SSD may provide substantially better random I/O performance than an HDD, even when its sequential throughput is limited by the interface.

### 2.3 NVMe SSD

NVMe is a storage protocol designed for nonvolatile memory devices, commonly connected through PCI Express.

NVMe provides:

- Multiple submission and completion queues.
- High queue concurrency.
- Reduced protocol overhead compared with legacy storage interfaces.
- Efficient command processing.
- Support for high-performance PCIe storage.

An NVMe SSD can deliver much higher sequential bandwidth and random IOPS than a typical SATA SSD.

Its actual performance depends on:

- PCIe generation and lane configuration.
- Controller architecture.
- NAND type.
- Firmware.
- Thermal conditions.
- Queue depth.
- Workload characteristics.

NVMe is a protocol, while SSD describes a storage-device technology. The terms are related but are not interchangeable.

## 3. Sequential I/O and Random I/O

### 3.1 Sequential I/O

Sequential I/O processes data in adjacent or logically continuous storage locations.

Examples include:

- Reading large video files.
- Writing backup archives.
- Streaming datasets.
- Copying large files.
- Sequential database scans.

The principal performance measurement is usually throughput.

For a transfer of size \(S\) and bandwidth \(B\):

\[
T_{\text{transfer}}=\frac{S}{B}
\]

When latency is included:

\[
T_{\text{I/O}}=T_{\text{access}}+T_{\text{transfer}}
\]

For example, transferring 1,024 MB at 512 MB/s requires approximately:

\[
T=\frac{1024}{512}=2\text{ seconds}
\]

This estimate assumes a sustained transfer rate and excludes additional operating-system and application overhead.

### 3.2 Random I/O

Random I/O accesses storage locations that are not necessarily adjacent.

Examples include:

- Database index lookups.
- Transaction processing.
- Metadata retrieval.
- Virtual machine disk operations.
- Small-file access.
- Randomized data retrieval.

Random I/O is commonly evaluated through IOPS.

IOPS means Input/Output Operations Per Second.

\[
IOPS=\frac{\text{Completed I/O Operations}}{\text{Elapsed Time}}
\]

For a device completing 50,000 operations in one second:

\[
IOPS=50,000
\]

Random I/O performance is strongly influenced by block size, queue depth, request distribution, and read/write characteristics.

### 3.3 Comparison

| Characteristic | Sequential I/O | Random I/O |
|---|---|---|
| Access pattern | Adjacent locations | Distributed locations |
| Primary measurement | MB/s or GB/s | IOPS |
| Typical operation | Large transfers | Small independent requests |
| HDD behavior | Efficient | Mechanical positioning is expensive |
| SSD behavior | High transfer rates | Low access latency |
| Common application | Backup and streaming | Databases and transactional systems |

## 4. I/O Latency

I/O latency measures the time between issuing an I/O request and completing it.

A simplified latency model is:

\[
L_{\text{total}} =
L_{\text{queue}}+
L_{\text{device}}+
L_{\text{transfer}}
\]

Where:

- \(L_{\text{queue}}\): Time waiting for service.
- \(L_{\text{device}}\): Device processing and access time.
- \(L_{\text{transfer}}\): Time needed to transfer data.

Real systems can contain additional overhead from application processing, operating-system scheduling, filesystem operations, controller processing, and interface communication.

### 4.1 Average Latency

\[
L_{\text{avg}}=
\frac{\sum_{i=1}^{n}L_i}{n}
\]

Average latency provides a general measure of request completion time.

It can conceal occasional slow requests.

### 4.2 Percentile Latency

Percentiles help identify latency variation.

| Metric | Interpretation |
|---|---|
| P50 | Median request latency |
| P95 | 95% of requests complete at or below this latency |
| P99 | 99% of requests complete at or below this latency |
| P99.9 | 99.9% of requests complete at or below this latency |

A database may have acceptable average latency but poor P99 latency.

This can affect transaction response times and application reliability.

The Python, JavaScript, C++, and Java implementations calculate average, P95, and P99 latency.

## 5. IOPS and Throughput Relationship

IOPS and throughput are related through block size.

\[
Throughput=IOPS\times BlockSize
\]

When block size is measured in bytes:

\[
Throughput_{MB/s}=
\frac{IOPS\times BlockSize}{1024^2}
\]

Consider a storage device performing 100,000 IOPS with 4 KB blocks.

\[
Throughput=
\frac{100000\times4096}{1048576}
\]

\[
Throughput\approx390.63\text{ MB/s}
\]

This calculation assumes that the device sustains the specified IOPS and block size.

High IOPS does not automatically mean high throughput. Small blocks can generate high operation counts while transferring comparatively little data.

Large sequential requests can produce high throughput with fewer individual I/O operations.

## 6. Queue Depth and Concurrency

Queue depth represents the number of outstanding storage requests.

A queue allows the device to process multiple requests without requiring the application to wait for each request individually.

Queue depth affects:

- Request scheduling.
- Device utilization.
- IOPS.
- Throughput.
- Request waiting time.
- Tail latency.

HDDs and SSDs have different scheduling characteristics.

HDD performance can benefit from request reordering because the controller can reduce mechanical movement.

SSDs can process requests concurrently without mechanical positioning. NVMe supports multiple queues and high concurrency.

Increasing queue depth does not guarantee improved performance.

Excessive queue depth can increase waiting time and tail latency.

### 6.1 Little's Law

A useful relationship between concurrency, throughput, and latency is Little's Law:

\[
N=\lambda W
\]

Where:

- \(N\): Average number of outstanding requests.
- \(\lambda\): Average completion rate.
- \(W\): Average time spent in the system.

For storage systems:

\[
IOPS\approx\frac{QueueDepth}{AverageLatencySeconds}
\]

This relationship is useful when analyzing sustained workloads under appropriate steady-state assumptions.

## 7. SSD Internal Behavior

### 7.1 NAND Flash

NAND flash stores information in memory cells.

Common NAND categories include:

| Type | Bits per Cell |
|---|---:|
| SLC | 1 |
| MLC | 2 |
| TLC | 3 |
| QLC | 4 |

Higher bits per cell can increase storage density, but generally introduce more complex programming and endurance tradeoffs.

Actual performance and endurance depend on NAND generation, controller design, firmware, and workload.

### 7.2 Flash Translation Layer

The Flash Translation Layer maps logical block addresses to physical flash locations.

Applications access logical block addresses, while the SSD controller manages the underlying NAND organization.

The FTL handles:

- Logical-to-physical mapping.
- Garbage collection.
- Wear leveling.
- Bad-block management.
- Data relocation.
- Write management.

This abstraction allows the SSD to manage NAND flash without exposing its physical layout to applications.

### 7.3 Write Amplification

NAND flash generally cannot overwrite an existing programmed page directly.

The controller may need to relocate valid data and erase blocks before reusing flash space.

Write amplification is:

\[
WAF=
\frac{\text{Physical NAND Bytes Written}}
{\text{Host Bytes Written}}
\]

A WAF greater than one indicates that the SSD writes more physical data than the host requested.

Higher write amplification can affect endurance and write performance.

### 7.4 Garbage Collection

Garbage collection reclaims flash blocks by moving valid pages and erasing blocks containing invalid pages.

This process can temporarily compete with host I/O.

Consequences may include:

- Increased write latency.
- Variable throughput.
- Higher internal write activity.
- Changes in sustained performance.

### 7.5 TRIM

TRIM allows an operating system or filesystem to inform an SSD that certain logical blocks no longer contain useful data.

The SSD can use this information to manage invalid pages and garbage collection.

TRIM does not directly erase every physical NAND cell immediately.

## 8. Performance Measurement

A meaningful storage benchmark should define:

1. Device and interface.
2. Read or write operation.
3. Sequential or random access.
4. Block size.
5. Queue depth.
6. Number of requests.
7. Test duration.
8. Data-set size.
9. Cache conditions.
10. Measurement methodology.

### 8.1 Block Size

Different block sizes produce different performance characteristics.

| Block Size | Typical Workload |
|---|---|
| 4 KB | Database and small random requests |
| 8 KB | Database pages and application data |
| 64 KB | Mixed application workloads |
| 128 KB | Large data transfers |
| 1 MB | Sequential file operations |

The appropriate block size depends on the application's actual I/O pattern.

### 8.2 Cache Effects

Measured performance can be influenced by:

- Operating-system page cache.
- Filesystem cache.
- SSD controller cache.
- DRAM write buffering.
- SLC write cache.
- Application-level caching.

A benchmark that repeatedly reads the same file may measure memory-cache performance rather than physical storage performance.

Similarly, a successful write operation does not necessarily mean that data has reached nonvolatile media.

Durability-sensitive measurements must account for synchronization and flush behavior.

### 8.3 Sustained and Burst Performance

SSDs can deliver high initial write throughput because of caching mechanisms.

Sustained write performance may decline after cache exhaustion.

Performance can also change due to:

- Thermal throttling.
- Background garbage collection.
- Drive fullness.
- Firmware behavior.
- Concurrent workloads.
- NAND temperature and operating conditions.

A short benchmark may not represent long-running production performance.

## 9. Python Implementation

File: `disk_ssd_behavior.py`

The Python program provides an analytical storage simulator.

### Main components

| Component | Responsibility |
|---|---|
| `StorageType` | Defines HDD, SATA SSD, and NVMe SSD |
| `IOType` | Defines four read/write workload categories |
| `StorageProfile` | Stores device performance characteristics |
| `StorageSimulator` | Calculates estimated service latency |
| `BenchmarkReport` | Stores performance measurements |
| `analyze_workload()` | Evaluates configured performance thresholds |

### Implemented mechanisms

The simulator calculates sequential latency using bandwidth and transfer size.

Random I/O latency uses configured IOPS and access latency.

Queue depth introduces a simplified contention penalty.

The benchmark engine collects latency samples and calculates:

- Average latency.
- Median latency.
- P95 latency.
- P99 latency.
- Throughput.
- IOPS.

The real-file microbenchmark separately measures buffered sequential reads and synchronized writes using temporary files.

It demonstrates the difference between analytical estimates and actual file-system measurements.

### Important limitation

The analytical simulator is not a physical storage controller emulator.

Its queue penalty and latency variation are simplified models. It does not reproduce real scheduling, caching, garbage collection, firmware, or device-level concurrency.

## 10. JavaScript Implementation

File: `disk_ssd_behavior.js`

The JavaScript program emphasizes asynchronous request processing.

### Main components

| Component | Responsibility |
|---|---|
| `StorageDevice` | Represents storage hardware characteristics |
| `LatencyTracker` | Collects latency observations |
| `StorageController` | Manages outstanding I/O requests |
| `StorageError` | Represents validation and execution failures |
| `compareDevices()` | Runs workload comparisons |

### Event-driven workflow

The request lifecycle is:

Storage Request  
→ Validation  
→ Queue Insertion  
→ Queue Scheduling  
→ Device Service Simulation  
→ Completion  
→ Latency Recording  
→ Reporting

The controller uses Promises and asynchronous execution.

Application-side concurrency is controlled independently from device queue depth.

`Promise.allSettled()` allows a batch to report individual failures without discarding successful operations.

The real-file benchmark uses Node.js filesystem APIs and requests synchronization through `FileHandle.sync()`.

### Important limitation

JavaScript timers have scheduling granularity and operating-system overhead.

The asynchronous simulator demonstrates queue management and concurrency. Its measured execution time is not equivalent to hardware I/O latency.

## 11. C++17 Implementation

File: `disk_ssd_behavior.cpp`

The C++ implementation focuses on a modular storage-performance engine.

### Main components

| Component | Responsibility |
|---|---|
| `StorageDevice` | Storage specification |
| `IORequest` | Request representation |
| `IOResult` | Request completion data |
| `StorageEngine` | Service-time calculation and benchmark execution |
| `StorageFleet` | Multi-device management |
| `PerformancePolicy` | Performance classification |

### Design decisions

The implementation uses:

- Enumerations for storage types and I/O operations.
- Structures for requests and benchmark results.
- Classes for storage behavior.
- STL vectors for measurements.
- STL algorithms for percentile calculations.
- Exceptions for invalid inputs.

The engine separates device service-time estimation from benchmark aggregation.

This makes it possible to extend the system with different device profiles or workload models without changing the reporting logic.

### Performance considerations

Latency samples are sorted to calculate percentiles.

For \(n\) observations:

- Collecting observations requires \(O(n)\) storage.
- Average calculation requires \(O(n)\) time.
- Sorting requires \(O(n\log n)\) time.
- Percentile retrieval after sorting requires \(O(1)\) time.

The implementation uses a simplified deterministic model and does not claim to reproduce physical queue scheduling.

## 12. Java 17 Implementation

File: `DiskSSDBehavior.java`

The Java implementation represents an enterprise storage-monitoring service.

### Domain architecture

Storage Registry  
→ Storage Assets  
→ Storage Service  
→ Workload Service  
→ Telemetry Repository  
→ Analytics Service  
→ Policy Engine

### Main domain types

| Type | Responsibility |
|---|---|
| `StorageSpecification` | Immutable device configuration |
| `IORequest` | Validated I/O request |
| `IOObservation` | Recorded request result |
| `StorageAsset` | Device identity and lifecycle |
| `StorageRegistry` | Device inventory |
| `TelemetryRepository` | Observation storage |
| `AnalyticsService` | Performance calculations |
| `PerformancePolicy` | SLA configuration |
| `PolicyEngine` | Performance evaluation |

Java records provide immutable data structures for specifications, requests, observations, and policy results.

The storage asset maintains its lifecycle status.

A failed device cannot directly return to active status. Recovery must be represented by a separate operational process.

### Policy evaluation

The policy engine checks:

- Average latency.
- P95 latency.
- P99 latency.
- Minimum IOPS.

It produces one of three evaluation outcomes:

- `PASS`
- `WARNING`
- `CRITICAL`

The application keeps storage execution, telemetry persistence, analytics, and policy decisions in separate service classes.

The example uses an in-memory repository. Production systems would require durable persistence, transactional updates, access controls, and concurrent workload handling.

## 13. PostgreSQL Implementation

File: `disk_ssd_behavior.sql`

The PostgreSQL script models a relational storage-monitoring system.

### Database relationship

Storage Devices  
→ Benchmark Runs  
→ I/O Observations  
→ Benchmark Results  
→ Policy Evaluations

Applications and performance policies provide additional context for each benchmark.

### Database objects

| Object | Purpose |
|---|---|
| `storage_devices` | Storage hardware inventory |
| `applications` | Workload ownership and criticality |
| `performance_policies` | Performance thresholds |
| `benchmark_runs` | Benchmark execution state |
| `io_observations` | Individual I/O measurements |
| `benchmark_results` | Aggregated benchmark metrics |
| `policy_evaluations` | SLA evaluation decisions |
| `device_status_history` | Device lifecycle history |

### Integrity mechanisms

The database uses primary keys, foreign keys, unique constraints, and check constraints.

These mechanisms prevent invalid values and maintain relationships between benchmark records and their associated devices.

The benchmark-state trigger enforces the following lifecycle:

CREATED  
→ RUNNING  
→ COMPLETED

A running benchmark can also transition to `FAILED`.

Completed and failed benchmarks are terminal states in this model.

### Benchmark calculations

The `calculate_benchmark()` function calculates:

- Total bytes transferred.
- Average latency.
- P95 latency.
- P99 latency.
- Throughput.
- Achieved IOPS.

The calculation uses PostgreSQL's ordered-set percentile aggregate functions.

The `complete_benchmark` procedure validates observation counts, calculates the final metrics, stores benchmark results, and changes the benchmark state.

### Performance policies

The `evaluate_benchmark_policy()` function compares benchmark results against configured performance limits.

It records violations and produces a policy decision.

This separates measurement from policy evaluation.

A benchmark can contain valid measurements while still failing a performance policy.

### Indexing

Indexes support:

- Device-specific benchmark history.
- Benchmark status retrieval.
- Operation filtering.
- Observation retrieval.
- Latency analysis.
- Policy decision reporting.

For large telemetry systems, partitioning by time and defining data-retention policies may be necessary.

## 14. Comparative Performance Interpretation

The following values are illustrative device profiles used by the source files, not guaranteed manufacturer specifications.

| Characteristic | Enterprise HDD | SATA SSD | NVMe SSD |
|---|---:|---:|---:|
| Sequential read | 180 MB/s | 550 MB/s | 3500 MB/s |
| Sequential write | 160 MB/s | 500 MB/s | 3000 MB/s |
| Random read | 120 IOPS | 90,000 IOPS | 600,000 IOPS |
| Random write | 110 IOPS | 80,000 IOPS | 500,000 IOPS |
| Access latency | 8 ms | 0.08 ms | 0.02 ms |
| Maximum modeled queue depth | 4 | 32 | 64 |

These profiles demonstrate why device selection should consider the workload rather than sequential throughput alone.

### Application suitability

| Workload | Important Characteristic |
|---|---|
| Database OLTP | Random IOPS and tail latency |
| Large backups | Sequential write throughput |
| Video streaming | Sustained sequential read throughput |
| Virtual machines | Mixed I/O and queue management |
| Analytics | Sequential scans and concurrent reads |
| Metadata-heavy applications | Small random I/O latency |

## 15. Benchmarking Limitations and Production Considerations

### 15.1 Synthetic Workloads

Synthetic benchmarks are useful for controlled comparisons.

Their results may not represent production performance because real applications generate mixed workloads with varying request sizes and concurrency.

A realistic evaluation should reproduce application-specific access patterns.

### 15.2 Queueing and Latency

Queue depth must be interpreted together with latency.

A higher IOPS result accompanied by significantly higher P99 latency may be unsuitable for latency-sensitive applications.

### 15.3 Data Integrity

Performance testing must not overwrite production data or run uncontrolled destructive workloads.

Use dedicated test files, isolated test volumes, and appropriate permissions.

Temporary-file tests should clean up their test artifacts even when execution fails.

### 15.4 Endurance

SSD write endurance is influenced by NAND technology, write amplification, workload distribution, temperature, and total writes.

Useful device health indicators include:

- Percentage of rated endurance consumed.
- Host bytes written.
- NAND bytes written, when available.
- Media errors.
- Temperature.
- Available spare capacity.

### 15.5 Monitoring

Production storage monitoring should collect:

- Average latency.
- P95 and P99 latency.
- Read and write IOPS.
- Sequential throughput.
- Queue depth.
- Queue wait time.
- Device utilization.
- Temperature.
- Error counts.
- Device health.

Measurements should be collected over appropriate time windows to distinguish short-lived bursts from sustained performance problems.

## 16. Technical Distinctions

| Concept | Meaning |
|---|---|
| HDD | Magnetic storage using mechanical components |
| SSD | Solid-state storage using nonvolatile memory |
| SATA | Storage interface and protocol family |
| NVMe | Protocol designed for nonvolatile memory over PCIe |
| Latency | Time required to complete an operation |
| Throughput | Data transferred per unit of time |
| IOPS | Number of completed I/O operations per second |
| Block size | Amount of data transferred in an I/O operation |
| Queue depth | Number of outstanding requests |
| Seek time | Mechanical positioning time on an HDD |
| Rotational latency | Waiting time for a sector to rotate into position |
| FTL | Flash Translation Layer |
| TRIM | Notification that logical storage blocks are no longer needed |
| WAF | Ratio of physical NAND writes to host writes |
| P99 | Latency threshold covering 99% of observed operations |

## 17. Cross-Language Implementation Comparison

| Language | Engineering Perspective | Main Mechanisms |
|---|---|---|
| Python | Analytical simulation | Dataclasses, enums, statistics, file I/O |
| JavaScript | Asynchronous request processing | Promises, event-driven queues, filesystem APIs |
| C++17 | Modular performance engine | STL, domain structures, exceptions, algorithms |
| Java 17 | Enterprise monitoring architecture | Records, services, repositories, policy evaluation |
| PostgreSQL | Persistent telemetry and reporting | Relational constraints, triggers, procedures, aggregation |

The implementations use different abstractions but share the same storage-performance concepts.

Their calculations are simplified models intended for technical analysis and learning. Actual device measurements must be obtained from controlled workloads and hardware-level telemetry.
