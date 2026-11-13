# Query Optimizer: Cost Estimation, Statistics and Plan Selection

## 1. Technical Scope

A query optimizer determines an efficient execution strategy for a database query.

A relational query describes the required result rather than prescribing the exact sequence of physical operations. The optimizer evaluates alternative execution strategies and selects a plan according to estimated execution cost.

The central optimization problem involves three connected activities:

1. Estimating how many rows each operation will process.
2. Estimating the resource consumption of alternative physical operations.
3. Selecting an execution plan with a comparatively low estimated cost.

This project implements an educational cost-based relational query optimizer across Python, JavaScript, C++17, Java 17 and PostgreSQL.

The implementations use a common business scenario involving customers, orders and payments.

The example workload retrieves completed orders, successful payments and customers belonging to a particular geographical region.

## 2. Query Optimization Architecture

The optimizer follows this logical processing architecture:

SQL Query
    |
    v
Query Validation
    |
    v
Statistics Catalog
    |
    v
Predicate Analysis
    |
    v
Selectivity Estimation
    |
    v
Cardinality Estimation
    |
    v
Access Path Evaluation
    |
    v
Join Order Enumeration
    |
    v
Physical Operator Costing
    |
    v
Execution Plan Selection
    |
    v
Estimated Execution Plan

# Cost-Based Query Optimization in Relational Database Management Systems

The architecture separates logical query requirements from physical execution decisions.

For example, retrieving customers and their orders expresses a logical relationship. The optimizer must still determine whether sequential scanning, index scanning, hash joining or nested-loop joining is preferable.

An execution plan represents the selected arrangement of physical operations.

## 3. Fundamental Terminology

| Term | Meaning |
|---|---|
| Query optimizer | Component responsible for selecting an execution strategy |
| Query plan | Structured representation of query execution operations |
| Logical plan | Representation of relational operations independent of physical implementation |
| Physical plan | Representation of concrete execution algorithms |
| Cardinality | Number of rows produced or processed by an operation |
| Selectivity | Fraction of rows expected to satisfy a predicate |
| Statistics | Metadata describing relations and their columns |
| NDV | Number of distinct values in a column |
| MCV | Most common values and their observed frequencies |
| Histogram | Distribution representation used for estimating value ranges |
| Access path | Method used to retrieve rows from a relation |
| Cost model | Formula for estimating resource consumption |
| Join order | Sequence in which relations are combined |
| Join algorithm | Physical method used to execute a join |
| EXPLAIN | Representation of an estimated execution plan |
| EXPLAIN ANALYZE | Execution-plan inspection that also executes the query and reports actual measurements |

Cost is an estimate, not a direct measurement of elapsed execution time.

A lower estimated cost does not guarantee lower wall-clock execution time under every workload.

## 4. Statistics and Cardinality Estimation

### 4.1 Relation Statistics

Relation-level statistics describe the physical and logical characteristics of a table.

The implementations maintain:

- Estimated row count.
- Estimated page count.
- Column statistics.
- Available index statistics.
- Statistics collection timestamp.

Consider the example relations:

| Relation | Estimated Rows | Estimated Pages |
|---|---:|---:|
| customers | 100,000 | 1,000 |
| orders | 1,000,000 | 12,000 |
| payments | 850,000 | 9,000 |

The optimizer uses these values to estimate scanning and joining costs.

The statistics are estimates rather than guarantees about the current contents of a database.

### 4.2 Distinct Value Count

Distinct value count indicates how many different values are estimated to exist in a column.

For example:

- `customers.customer_id`: 100,000 distinct values.
- `orders.customer_id`: 100,000 distinct values.
- `orders.status`: 4 distinct values.

A column with a high number of distinct values may support relatively selective equality predicates.

A column with a small number of distinct values may contain many repeated values.

### 4.3 Null Fraction

Null fraction represents the proportion of rows containing NULL values.

For a column with 100,000 rows and a null fraction of 0.10:

\[
N_{\text{null}}=100000 \times 0.10=10000
\]

The remaining 90,000 rows contain non-NULL values.

The implementations distinguish NULL-related equality estimation from ordinary equality estimation.

In SQL, NULL comparison semantics require particular care. `IS NULL` is not equivalent to ordinary equality with NULL.

### 4.4 Most Common Values

A most-common-value distribution records frequent values and their estimated frequencies.

Example:

| Region | Frequency |
|---|---:|
| North | 0.35 |
| South | 0.25 |
| East | 0.20 |
| West | 0.15 |

For a predicate:

region = 'North'
The estimated selectivity is:

\[
S=0.35
\]

Estimated matching rows:

\[
N=100000 \times 0.35=35000
\]

This is more informative than assuming uniform distribution across all distinct values.

### **4.5 Histograms**

Histograms describe value distributions through ordered boundaries.

The example amount histogram contains:

\[
[0,100,250,500,1000,5000,10000]
\]

A range predicate can use histogram boundaries to approximate the proportion of values falling within the requested interval.

For a simplified uniform distribution between histogram endpoints:

\[
S(a,b)= \frac{ \max(0,\min(b,H_{\max})-\max(a,H_{\min})) }{ H_{\max}-H_{\min} }
\]

This is an educational approximation.

A production database may use more sophisticated histogram representations, including bucket frequencies and nonuniform distributions.

## **5. Predicate Selectivity**

Selectivity estimates the proportion of relation rows satisfying a predicate.

For an equality predicate on a column without MCV information, a uniform-distribution estimate is:

\[
S=\frac{1-f_{\text{null}}}{NDV}
\]

Where:

- \(S\) is estimated selectivity.
- \(f_{\text{null}}\) is the null fraction.
- \(NDV\) is the number of distinct values.

For a non-NULL equality predicate with 100,000 distinct values and no NULLs:

\[
S=\frac{1}{100000}=0.00001
\]

The estimated cardinality becomes:

\[
N_{\text{filtered}}=N_{\text{base}}\times S
\]

For multiple predicates, the implementations initially assume statistical independence:

\[
S_{\text{combined}}=\prod_{i=1}^{n}S_i
\]

For example:

- Region selectivity: 0.35.
- Completed-order selectivity: 0.65.
- Payment-success selectivity: 0.80.

The independence assumption may be inaccurate when columns are correlated.

A production optimizer benefits from multicolumn statistics, dependency information and more sophisticated distribution models.

## **6. Cardinality Estimation**

Cardinality estimation predicts the number of rows returned by an operation.

It is one of the most influential components of cost-based optimization.

An incorrect estimate can affect:

- Access path selection.
- Join ordering.
- Join algorithm selection.
- Memory allocation.
- Sorting strategy.
- Intermediate result size.

For a filtered relation:

\[
N_{\text{filtered}}=N_{\text{base}}\times S
\]

For an equality join, a simplified estimate is:

\[
N_{\text{join}}= \frac{N_L\times N_R}{\max(NDV_L,NDV_R)}
\]

Where:

- \(N_L\) is the estimated left input cardinality.
- \(N_R\) is the estimated right input cardinality.
- \(NDV_L\) is the left join column's distinct value count.
- \(NDV_R\) is the right join column's distinct value count.

This formula assumes compatible join distributions and does not model every case involving NULLs, foreign-key constraints, uniqueness or skew.

## **7. Physical Access Paths**

An access path determines how the database retrieves records from a relation.

The implementations compare sequential scans and index scans.

### **7.1 Sequential Scan**

A sequential scan reads relation pages and evaluates applicable predicates against the rows.

The educational model uses:

\[
C_{\text{seq}}= P\times C_{\text{seq-page}} + N\times C_{\text{tuple}} + N\times K\times C_{\text{operator}}
\]

Where:

- \(P\) is the relation page count.
- \(N\) is the estimated row count.
- \(K\) is the number of predicates.
- \(C_{\text{seq-page}}\) is the sequential page cost.
- \(C_{\text{tuple}}\) is the per-row processing cost.
- \(C_{\text{operator}}\) is the predicate evaluation cost.

Sequential scans can be efficient when:

- A large fraction of a relation is required.
- The relation is relatively small.
- An applicable index is unavailable.
- Index traversal and random page access would be more expensive.

### **7.2 Index Scan**

An index scan uses an index to locate qualifying records.

The educational model considers:

- Index height.
- Index page count.
- Estimated qualifying rows.
- Heap page accesses.
- Cache assumptions.
- Index-only access.

Its simplified cost model is:

\[
C_{\text{index}}= H\times C_{\text{random-page}} + P_{\text{heap}}\times C_{\text{random-page}}\times D + N_{\text{result}}\times C_{\text{tuple}}
\]

Where:

- \(H\) is estimated index traversal height.
- \(P_{\text{heap}}\) is estimated heap page access.
- \(D\) is the cache discount factor.
- \(N_{\text{result}}\) is estimated matching rows.

An index scan is not automatically faster than a sequential scan.

A poorly selective index predicate may require extensive heap access.

### **7.3 Index-Only Scans**

An index-only scan can avoid some heap access when the required data is available from the index and visibility conditions permit it.

The implementations represent this through an index-only property and a reduced heap-access estimate.

Actual index-only behavior depends on database implementation and visibility-map state.

## **8. Join Algorithms**

The project implements two physical join algorithms.

### **8.1 Hash Join**

A hash join builds a hash table from one input and probes it using rows from the other input.

The simplified cost model is:

\[
C_{\text{hash}}= C_L+C_R+ N_{\text{build}}\times C_{\text{hash-build}} + N_{\text{probe}}\times C_{\text{operator}} + (N_L+N_R)\times C_{\text{tuple}}
\]

The smaller input is treated as the hash-build input for cost estimation.

Hash joins are generally suitable for equality joins involving substantial inputs.

Important practical constraints include:

- Available memory.
- Hash table size.
- Data distribution.
- Hash collisions.
- Disk spilling.
- Parallel execution.

The sample implementation does not simulate disk spilling or parallel hash execution.

### **8.2 Nested-Loop Join**

A nested-loop join evaluates matching conditions by combining an outer input with an inner input.

The simplified cost model is:

\[
C_{\text{nested}}= C_L+C_R+ N_L\times N_R\times C_{\text{loop}} + N_{\text{output}}\times C_{\text{tuple}}
\]

Nested-loop joins can be effective when:

- The outer input is small.
- The inner input has an efficient index.
- The estimated number of matching rows is small.

The supplied implementation uses a simplified inner-input cost model. A production implementation should account explicitly for indexed inner lookups and repeated page access.

### **8.3 Join Algorithm Comparison**

| Characteristic | Hash Join | Nested Loop |
|---|---|---|
| Main mechanism | Hash table and probing | Repeated inner evaluation |
| Typical join condition | Equality | Equality and other supported conditions |
| Small outer input | Can work well | Often beneficial |
| Large inputs | Often suitable | May become expensive |
| Memory dependency | Significant | Generally lower |
| Index dependency | Not required | Can benefit substantially |
| Main risk | Hash memory pressure | Repeated inner work |

The best choice depends on estimated cardinalities, access paths, memory and the physical cost model.

## **9. Join Order Optimization**

A query involving multiple relations can have several possible join orders.

For three relations, possible left-deep arrangements include:

- Customers joined with orders, followed by payments.
- Orders joined with payments, followed by customers.
- Customers joined with payments, followed by orders, if a connecting condition exists.

The order affects intermediate cardinalities and total estimated cost.

### **9.1 Dynamic Programming**

The Python, C++17 and Java implementations use dynamic-programming-style enumeration of connected left-deep plans.

The JavaScript implementation uses a greedy connected join-selection strategy.

Dynamic programming stores the cheapest known plan for each relation subset.

For a subset \(S\), the optimizer evaluates possible partitions:

\[
S=A\cup B
\]

Where:

\[
A\cap B=\varnothing
\]

The selected plan minimizes:

\[
C(S)= \min_{A,B} \left[ C(A)+C(B)+C_{\text{join}}(A,B) \right]
\]

The supplied dynamic-programming implementations restrict enumeration to connected left-deep plans rather than exhaustive enumeration of every bushy join tree.

This reduces the search space but may exclude a globally preferable bushy plan.

### **9.2 Complexity**

For \(n\) relations, subset enumeration has exponential complexity.

A typical dynamic-programming join optimizer has complexity around:

\[
O(3^n)
\]

for broad subset-partition enumeration, with additional factors depending on join alternatives and implementation.

The implementations use practical relation-count limits to control memory and processing requirements.

Greedy optimization reduces search work but can make locally attractive choices that produce a globally inferior plan.

## **10. Cost Model and Plan Selection**

The cost model assigns numerical estimates to physical operations.

The sample configuration uses:

| Parameter | Value |
|---|---:|
| Sequential page cost | 1.0 |
| Random page cost | 4.0 |
| Tuple processing cost | 0.01 |
| Operator processing cost | 0.0025 |
| Hash build cost | 0.015 |
| Nested-loop processing cost | 0.005 |
| Cache discount | 0.75 |

These values are illustrative.

They do not represent universal hardware-independent performance measurements.

The optimizer calculates candidate costs and chooses the least expensive available candidate.

Conceptually:

\[
P_{\text{selected}}= \arg\min_{P\in\mathcal{P}} C(P)
\]

Where:

- \(\mathcal{P}\) represents the candidate plan set.
- \(C(P)\) represents the estimated cost of plan \(P\).

The selected plan is an estimate-based decision rather than a guarantee of actual runtime performance.

## **11. Implementation Architecture by Language**

### **11.1 Python**

The Python implementation provides a domain-oriented optimization simulator.

| Component | Responsibility |
|---|---|
| `Histogram` | Range distribution estimation |
| `ColumnStatistics` | NDV, null fraction and MCV information |
| `RelationStatistics` | Relation-level statistics |
| `StatisticsCatalog` | Statistics registration and retrieval |
| `CardinalityEstimator` | Predicate and row estimation |
| `CostEstimator` | Physical scan costing |
| `JoinEstimator` | Join cardinality and algorithm costing |
| `QueryOptimizer` | Dynamic-programming join ordering |
| `Plan` | Execution-plan representation |

Important Python features include dataclasses, enums, dictionaries, lists, sets, immutable query descriptions and custom exceptions.

The test routines validate MCV estimates, histogram ranges, unknown relations and invalid histogram definitions.

The script uses standard-library functionality only.

### **11.2 JavaScript**

The JavaScript implementation provides an event-driven catalog and asynchronous statistics registration.

Its architecture includes:

- `EventEmitter` for statistics lifecycle notifications.
- `Map` for catalog and index lookups.
- `Set` for connected relations.
- Immutable query and plan representations.
- Promise-based catalog operations.
- Greedy join-order selection.
- Explicit input validation.

The catalog emits registration and update events.

This approach is useful in systems where statistics collection and optimization are integrated into asynchronous application services.

The optimizer does not execute SQL or accept arbitrary SQL fragments. It evaluates structured query descriptions.

### **11.3 C++17**

The C++17 implementation focuses on explicit domain modeling and algorithmic control.

| Component | Responsibility |
|---|---|
| `Histogram` | Numeric distribution estimation |
| `StatisticsCatalog` | Relation statistics storage |
| `CardinalityEstimator` | Selectivity and cardinality |
| `AccessPathEvaluator` | Scan alternatives |
| `JoinEstimator` | Join cost comparison |
| `QueryOptimizer` | Bitmask-based dynamic programming |
| `Plan` | Recursive execution-plan tree |

The optimizer uses a 64-bit subset representation for relation combinations.

Its configured maximum of twelve relations limits the dynamic-programming state space.

The implementation uses STL containers, optional values, structured bindings and exception handling.

No third-party dependencies are required.

### **11.4 Java 17**

The Java implementation models optimization as a collection of enterprise-oriented services.

Its major components include:

- Immutable records for domain data.
- `StatisticsRepository` for catalog access.
- `CardinalityService` for row estimation.
- `AccessPathService` for scan selection.
- `JoinPlanningService` for physical join alternatives.
- `OptimizationService` for plan enumeration.
- `CostPolicy` for centralized cost parameters.

The repository interface separates statistics access from optimization logic.

This makes the design suitable for later integration with persistent statistics repositories or application-level services.

The current implementation uses an in-memory repository and does not connect to a production database.

### **11.5 PostgreSQL**

The PostgreSQL implementation provides a relational model for optimizer metadata and workload analysis.

The `query_lab` schema contains:

| Table | Purpose |
|---|---|
| `cost_configuration` | Cost parameters |
| `relation_statistics` | Relation-level statistics |
| `column_statistics` | Column distributions |
| `index_statistics` | Index metadata |
| `query_workload` | Registered optimization workloads |
| `query_relations` | Relations participating in queries |
| `query_predicates` | Predicate definitions |
| `query_joins` | Join conditions |
| `execution_plan_candidates` | Physical plan alternatives |
| `optimization_results` | Selected optimization results |

The SQL implementation includes:

- Primary and foreign keys.
- Unique and check constraints.
- JSONB-based MCV storage.
- Numeric histogram arrays.
- Statistics validation triggers.
- Timestamp maintenance triggers.
- Selectivity estimation functions.
- Filtered cardinality estimation.
- Access path cost evaluation.
- Join cardinality estimation.
- Join algorithm comparison.
- Statistics refresh procedures.
- Ranking and freshness views.
- Transactional statistics updates.

The schema is an educational optimizer metadata model. It is not an extension of PostgreSQL's internal planner.

## **12. Complete Optimization Workflow**

The example workload uses three relations:

YAML representation:

    customers
        |
        | customer_id
        |
      orders
        |
        | order_id
        |
      payments

The logical conditions are:

- Customers belong to the North region.
- Orders have COMPLETED status.
- Order amounts fall between 100 and 1,000.
- Payments have SUCCESS status.
- Customer identifiers connect customers to orders.
- Order identifiers connect orders to payments.

The optimizer performs the following operations:

| Stage | Operation | Result |
|---:|---|---|
| 1 | Query validation | Checks relation and predicate definitions |
| 2 | Statistics lookup | Retrieves relation and column metadata |
| 3 | Selectivity estimation | Estimates predicate matching fractions |
| 4 | Cardinality estimation | Estimates filtered relation sizes |
| 5 | Access path evaluation | Compares sequential and index scans |
| 6 | Join estimation | Predicts intermediate result cardinalities |
| 7 | Join costing | Compares hash and nested-loop alternatives |
| 8 | Join ordering | Evaluates connected relation combinations |
| 9 | Plan selection | Chooses the lowest estimated-cost candidate |
| 10 | Plan reporting | Displays estimated operations, rows and costs |

The implementations expose intermediate estimates to make optimization decisions inspectable.

## **13. Statistics Quality and Estimation Errors**

Statistics are only useful when they reasonably represent the underlying data.

Several conditions can produce inaccurate estimates.

### **Stale Statistics**

Data distributions change following inserts, updates and deletes.

Statistics collected before a substantial data change may no longer represent current table contents.

The implementations track the statistics collection timestamp and identify potentially stale information.

### **Data Skew**

Uniform-distribution assumptions can produce substantial errors when a few values account for most rows.

MCV statistics improve estimates for frequently occurring values.

### **Correlated Columns**

The independence assumption can underestimate or overestimate the combined selectivity of predicates.

For example, customer region and shipping region may be strongly correlated.

Multiplying their independent selectivities may produce an inaccurate result.

### **Insufficient Histogram Resolution**

A histogram with too few boundaries cannot represent detailed distribution patterns.

Increasing statistics collection detail may improve estimation accuracy, although it also increases metadata collection and storage costs.

### **Parameter Sensitivity**

A parameterized query may behave differently depending on its actual parameter value.

A predicate that is highly selective for one value may return a substantial fraction of the table for another.

A single cached plan may therefore be unsuitable for every parameter value.

## **14. EXPLAIN and Actual Execution**

An estimated plan and an executed plan provide different kinds of information.

| Feature | EXPLAIN | EXPLAIN ANALYZE |
|---|---|---|
| Displays estimated operations | Yes | Yes |
| Displays estimated rows | Yes | Yes |
| Displays estimated cost | Yes | Yes |
| Executes the statement | No | Yes |
| Reports actual rows | No | Yes |
| Reports execution time | No | Yes |
| Useful for identifying estimate errors | Limited | Yes |

A practical diagnostic process compares estimated and actual cardinalities.

For example:

| Metric | Estimated | Actual |
|---|---:|---:|
| Filtered orders | 65,000 | 240,000 |
| Joined payments | 52,000 | 190,000 |

A substantial difference indicates that the optimizer's assumptions may not adequately describe the data distribution.

This can motivate statistics refreshes, improved column statistics or a different estimation strategy.

For statements that modify data, execution-plan analysis should account for the fact that `EXPLAIN ANALYZE` executes the statement. A transaction that is subsequently rolled back can be appropriate for controlled testing, subject to external side-effect considerations.

## **15. Performance Considerations**

### **Search Space**

Join ordering is an expensive combinatorial problem.

Dynamic programming provides systematic exploration but consumes increasing memory and computation as relation count grows.

Practical database optimizers use search-space restrictions, heuristics and alternative optimization techniques for larger queries.

### **Statistics Collection**

Statistics collection has a cost.

Frequent analysis can improve estimate freshness but consumes database resources.

Collection frequency should reflect data-change rates and query sensitivity.

### **Index Maintenance**

Indexes improve some read operations but impose storage and write-maintenance costs.

An index should not be considered beneficial solely because it exists.

Its selectivity, physical size, access pattern and cache behavior matter.

### **Memory**

Hash joins, sorts and other operations depend on available memory.

The sample cost models do not fully represent memory pressure, temporary disk usage or spilling.

### **Parallel Execution**

Parallel scans and joins can change the cost relationship between physical operators.

The supplied models use single-operation cost estimates and do not calculate parallel worker allocation.

## **16. Security and Reliability**

The implementations include validation for malformed statistics, unknown relations, unknown columns, invalid histograms and unsupported query structures.

Additional production controls should include:

- Restricting statistics catalog access.
- Using parameterized database statements.
- Applying least-privilege database roles.
- Validating externally supplied relation and column identifiers.
- Limiting query complexity and optimizer search time.
- Avoiding untrusted SQL execution.
- Monitoring statistics collection failures.
- Auditing cost configuration changes.
- Separating estimated plans from actual query execution.
- Protecting sensitive distribution information in statistics exports.

The optimizer should not execute arbitrary SQL simply because a plan has been generated.

## **17. Limitations of the Educational Model**

The five implementations intentionally focus on the core cost-based optimization mechanisms.

They do not reproduce the complete internal behavior of a production relational database.

| Area | Current Implementation | Production Considerations |
|---|---|---|
| Cardinality | Basic NDV, MCV and histogram estimation | Multivariate statistics and advanced estimators |
| Predicates | Equality and numeric ranges | Complex expressions and predicate transformations |
| Access paths | Sequential and index scans | Bitmap scans, index-only details and partition pruning |
| Joins | Hash and nested-loop joins | Merge joins and specialized join operators |
| Join ordering | Left-deep dynamic programming or greedy selection | Bushy trees and advanced search strategies |
| Cost model | Simplified CPU and page costs | Hardware, cache, memory and concurrency effects |
| Statistics | In-memory or educational catalog | Database-managed statistics collection |
| Execution | Plan estimation | Actual operator execution and runtime feedback |
| Parallelism | Not modeled | Parallel scans and joins |
| Distributed queries | Not modeled | Network transfer and distributed join costs |

These limitations distinguish the project from a production database query planner.

## **18. Practical Evaluation Criteria**

The optimizer implementations can be evaluated through the following criteria:

| Evaluation Area | Expected Behavior |
|---|---|
| Statistics validation | Invalid distributions are rejected |
| MCV estimation | Frequent values use recorded frequencies |
| Equality estimation | NDV-based fallback is applied |
| Range estimation | Histogram boundaries influence selectivity |
| Cardinality | Filtered row counts are calculated |
| Scan selection | Available access paths are compared |
| Join estimation | Join output cardinality is calculated |
| Join costing | Hash and nested-loop alternatives are compared |
| Join ordering | Connected relation combinations are evaluated |
| Statistics freshness | Old statistics are identified |
| Failure handling | Missing or invalid metadata raises errors |
| Plan reporting | Selected operations and estimated costs are displayed |

A meaningful evaluation should also compare estimated cardinalities with actual database measurements.

The difference between estimated and actual row counts is an important indicator of optimizer estimation quality.

## **19. Running the Implementations**

| Implementation | Runtime | Dependencies |
|---|---|---|
| Python | Python 3.10+ | Standard library |
| JavaScript | Node.js 18+ | Node.js standard library |
| C++17 | C++17 compiler | Standard library |
| Java | Java 17 | Java standard library |
| PostgreSQL | PostgreSQL 15+ | PostgreSQL database |

The four application implementations are independently executable.

The PostgreSQL script creates the `query_lab` schema, inserts example statistics and workload records, defines optimization functions, and executes reporting queries.

The PostgreSQL script should be run against a database in which the executing role has permission to create schemas, tables, functions, procedures, triggers and indexes.

## **20. Technical Relationships**

The central relationship between the project's components is:

    Statistics
        |
        v
    Selectivity
        |
        v
    Cardinality
        |
        v
    Access Path Costs
        |
        v
    Join Cardinality
        |
        v
    Join Algorithm Costs
        |
        v
    Join Order
        |
        v
    Plan Cost
        |
        v
    Selected Execution Plan

Statistics influence cardinality estimates.

Cardinality estimates influence the estimated cost of physical operations.

Physical operation costs influence join ordering and plan selection.

Consequently, statistics quality and cost-model accuracy directly affect the quality of the selected execution plan.
