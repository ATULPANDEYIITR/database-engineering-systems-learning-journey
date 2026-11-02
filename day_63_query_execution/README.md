# Query Execution: Operators, Execution Plans and Result Generation

## Scope

This project models how a relational query moves from a logical request to a physical execution process and finally to a result set.

The five implementations use the same domain but deliberately emphasize different engineering mechanisms:

| Implementation | Primary perspective |
|---|---|
| Python | Iterator-based relational execution model |
| JavaScript | Asynchronous operator pipeline |
| C++17 | Explicit physical execution engine |
| Java 17 | Enterprise domain model and typed execution services |
| PostgreSQL | Native relational planning, execution, constraints, and reporting |

The central distinction is between the requested result and the work required to produce it.

A query describes what data is required. An execution plan describes how that data will be obtained and transformed. Operators perform individual physical operations such as scanning, filtering, joining, sorting, aggregating, and limiting. Result generation materializes the final rows in the requested structure.

## Execution Model

The implementations use the following conceptual pipeline:

    Query
      |
      v
    Validation
      |
      v
    Logical operations
      |
      v
    Physical execution plan
      |
      +--> Scan
      |
      +--> Filter
      |
      +--> Join
      |
      +--> Aggregate / Sort
      |
      +--> Limit
      |
      v
    Result generation
      |
      v
    Result set

A useful distinction is:

- **Scan** obtains candidate rows.
- **Filter** removes rows that do not satisfy predicates.
- **Join** combines rows from different relations.
- **Aggregate** reduces rows into grouped results.
- **Sort** establishes result ordering.
- **Limit** bounds the final result.
- **Projection** chooses or computes output fields.
- **Result generation** exposes the completed rows to the caller.

The order of these operations affects cost even when the logical result remains unchanged.

## Operators

### Sequential Scan

A sequential scan examines rows from a table in storage order.

The Python, JavaScript, C++17, and Java implementations provide explicit sequential-scan operators. PostgreSQL can select a sequential scan when the planner estimates that reading a large portion of a relation is cheaper than using an index.

For a relation containing `N` rows, a basic sequential scan has approximately `O(N)` row-processing complexity.

Sequential scans are not inherently inefficient. When a predicate matches a large fraction of a table, scanning the relation can be cheaper than performing many index lookups followed by heap access.

### Index Scan

The examples use an index on customer status to reduce the number of candidate customer rows before the join.

Conceptually:

    customers
        |
        | status = active
        v
    Index Scan
        |
        v
    matching customers

The Python implementation stores index positions in dictionaries. JavaScript uses `Map`, while C++ uses `unordered_map`. Java builds an explicit status index.

The PostgreSQL implementation creates B-tree indexes and exposes the optimizer's selected physical strategy through `EXPLAIN`.

Index usefulness depends on selectivity, table size, data distribution, and the cost of accessing the underlying rows.

### Filter

A filter evaluates a predicate for each candidate row.

The execution model is:

    input row
        |
        v
    predicate
      /   \
   true   false
    |       |
  output   discard

Applying selective predicates early can reduce the number of rows processed by downstream operators.

The implementations validate predicate inputs and raise execution errors when referenced fields are unavailable.

### Projection

Projection transforms an internal row into the output schema.

The Python implementation uses named expressions. JavaScript uses object expressions. Java uses a typed `ResultRow` record.

Projection is important because internal execution rows can contain fields required for joins or predicates that should not appear in the final result.

### Hash Join

The implementations use a hash join for equality joins.

The general process is:

    right relation
          |
          v
    build hash table
          |
          v
    probe with left relation
          |
          v
    matching pairs

If the build-side relation has `M` rows and the probe-side relation has `N` rows, the expected processing cost is approximately `O(M + N)` under reasonable hash distribution.

The main memory trade-off is that the hash table must hold the build side or its relevant keys.

A hash join is appropriate for equality predicates such as:

`customers.customer_id = orders.customer_id`

It is not a general replacement for every join strategy.

### Sort

Sorting establishes deterministic ordering for the requested result.

The implementations sort qualifying order rows by descending order value before applying the result limit.

A comparison-based sort has approximately `O(N log N)` time complexity.

Sorting can be avoided or reduced when an appropriate ordered index already supplies rows in the requested order.

### Limit

`LIMIT` restricts the number of returned rows.

The logical position of `LIMIT` matters. A query requiring the three largest values cannot safely limit before sorting unless another operation already guarantees the required ordering.

The physical optimizer may use specialized strategies such as top-N processing rather than fully sorting every qualifying row.

## Execution Plans

An execution plan is a tree of physical operators.

The sample plan is structurally similar to:

    Limit
      |
    Sort
      |
    Project
      |
    Filter
      |
    Hash Join
      |          |
      |          +-- Sequential Scan orders
      |
      +-- Index Scan customers(status)

The exact physical order selected by a database optimizer can differ from this simplified model.

The Python, JavaScript, C++17, and Java programs expose their own operator trees through `explain`.

PostgreSQL provides native plan inspection with `EXPLAIN`.

### Estimated Versus Actual Execution

`EXPLAIN` describes the optimizer's selected plan and estimated costs.

`EXPLAIN ANALYZE` executes the statement and reports actual execution information such as observed rows and execution timing.

The PostgreSQL script uses both forms.

This distinction is important because an optimizer works with estimates. If statistics do not accurately represent current data distribution, the selected plan can be inappropriate.

## Result Generation

Result generation is the final stage in which the internal representation becomes the requested result schema.

The examples return:

| Field | Meaning |
|---|---|
| `customer_id` | Customer associated with the order |
| `customer_name` | Human-readable customer name |
| `order_id` | Order identifier |
| `order_total` | Monetary order value |

The internal join requires both customer and order keys. The final result exposes only the fields required by the query.

This separation prevents internal execution state from becoming an accidental public result schema.

## Python Implementation

The Python program uses an iterator-oriented operator hierarchy.

Important mechanisms include:

- `Table` stores validated rows and optional indexes.
- `SeqScan` reads every row.
- `IndexScan` uses a dictionary-backed equality index.
- `Filter` evaluates predicates.
- `Project` computes output fields.
- `HashJoin` builds a hash table for equality matching.
- `HashAggregate` demonstrates grouped counting.
- `Sort` orders rows.
- `Limit` bounds the result.
- `explain()` produces a readable physical plan.
- Assertions verify result invariants.
- Exceptions distinguish validation and execution failures.
- SHA-256 creates a deterministic query identifier for the example.

The design uses Python dictionaries heavily because they provide natural representations for relational rows and hash indexes.

The index is deliberately built before query execution. This makes the distinction between an indexed lookup and a sequential scan explicit rather than hiding it behind a database driver.

## JavaScript Implementation

The JavaScript implementation treats operators as asynchronous generators.

This gives the execution model a streaming-oriented interface:

    source
      |
      v
    async generator
      |
      v
    transformation
      |
      v
    async generator

`SeqScan`, `IndexScan`, `Filter`, `Project`, `HashJoin`, `Sort`, and `Limit` all expose asynchronous execution.

The design can therefore accommodate asynchronous data sources without changing the operator abstraction.

`Map` provides hash-index behavior, `Set` supports validation, and Node.js `crypto` creates a stable query identifier.

The program also separates validation errors from execution errors and terminates with a non-zero process status when an unexpected execution failure occurs.

## C++17 Implementation

The C++ implementation emphasizes explicit ownership and physical execution.

`Operator` is an abstract base class. Concrete operators are stored through `std::unique_ptr`, making ownership of the execution tree explicit.

The engine uses:

- `std::vector` for ordered row collections.
- `std::unordered_map` for hash indexes.
- `std::function` for predicates.
- `std::unique_ptr` for operator ownership.
- exceptions for invalid plans and execution failures.
- `std::chrono` for execution timing.

The hash join materializes the build side and probes it using the left-side keys.

The implementation also checks for ambiguous output columns during joins. This prevents silent overwriting of values when two input operators expose the same field name.

The C++ program intentionally uses a compact value representation for the demonstration while preserving the physical operator structure.

## Java 17 Implementation

The Java implementation focuses on typed domain modeling and service boundaries.

Records represent immutable domain values:

- `Query`
- `Customer`
- `Order`
- `ResultRow`

The `Query` record validates its own invariants before execution.

The `Operator<T>` interface provides a generic execution contract. Concrete operators implement typed scans, filters, joins, sorting, and limiting.

`HashJoin` uses Java collections to construct a hash table. `Sort` uses stream processing and typed comparators.

`QueryExecutionService` tracks explicit execution states:

    CREATED
       |
       v
    PLANNED
       |
       v
    EXECUTING
       |
       v
    COMPLETED

An execution failure moves the service into `FAILED`.

This state model makes query execution behavior explicit and provides a useful boundary for an enterprise service where planning, execution, telemetry, authorization, and error handling may be separate concerns.

## PostgreSQL Implementation

The PostgreSQL implementation moves from a simulated execution engine to an actual relational database.

The schema contains:

- `customers`
- `orders`
- indexes
- a result view
- validation functions
- a validation trigger

Foreign keys guarantee that an order cannot reference a nonexistent customer.

Check constraints enforce valid customer states and non-negative monetary values.

The indexes target common access paths:

- customer status
- order customer identifier
- order total

The script includes retrieval, aggregation, CTE-based processing, window functions, validation, reporting, and plan inspection.

`EXPLAIN` exposes optimizer-selected operators and estimated costs.

`EXPLAIN ANALYZE` adds actual execution information by executing the statement.

## Logical Versus Physical Processing

The logical request can be expressed as:

    SELECT active customers
    JOIN their orders
    WHERE order_total >= 800
    ORDER BY order_total DESC
    LIMIT 3

A physical engine must decide how to implement this request.

Possible physical choices include:

| Logical operation | Possible physical operator |
|---|---|
| Read relation | Sequential scan |
| Equality lookup | Index scan |
| Equality join | Hash join |
| Ordered output | Sort |
| Grouping | Hash aggregate |
| Ordered index access | Index scan |
| Result restriction | Limit |

The logical query does not dictate one physical implementation.

An optimizer can select another strategy when statistics, indexes, available memory, or estimated cardinalities make it cheaper.

## Cardinality and Cost

Cardinality is the number of rows expected at an operator.

A simplified plan can be understood through cardinality flow:

    customers: 4
         |
    active filter
         |
       3 rows
         |
       join
         |
       4 rows
         |
    total >= 800
         |
       3 rows
         |
       sort
         |
       limit 3
         |
       3 rows

Accurate cardinality estimates matter because downstream operator costs depend heavily on the number of rows they receive.

For example, a filter that removes 99% of rows can dramatically reduce the cost of a later sort or join.

## Failure Conditions

The implementations explicitly handle several invalid conditions:

- unknown columns
- missing indexes
- invalid query limits
- negative monetary values
- invalid status values
- malformed rows
- ambiguous join output columns
- invalid aggregation keys
- invalid sort keys
- failed result invariants

The PostgreSQL schema adds database-level enforcement so that invalid data cannot depend solely on application behavior.

## Transactions and Integrity

The PostgreSQL script demonstrates transaction boundaries and savepoints.

A transaction groups related changes into one atomic unit.

A savepoint provides a rollback point inside a transaction when a particular operation fails.

This matters because query execution and data modification are different concerns. A read-only query may inspect a consistent transaction snapshot, while write workflows require explicit durability and rollback semantics.

The example also uses `ROLLBACK` around diagnostic `EXPLAIN ANALYZE` execution so that plan inspection does not accidentally persist unrelated writes.

## Security Considerations

Query execution systems should not treat SQL text, predicates, or identifiers as trusted input.

Important controls include:

- parameterized statements for external values
- strict schema validation
- least-privilege database roles
- controlled access to execution-plan information
- resource limits for expensive queries
- statement timeouts
- row-level authorization where required
- protection against unbounded result generation
- audit logging for privileged query execution

The in-memory implementations avoid SQL injection by not constructing SQL strings at all.

The PostgreSQL example uses fixed SQL definitions and typed database objects. Application code using this schema should still bind user-provided values rather than concatenating SQL strings.

## Performance Considerations

The principal trade-offs represented in the project are:

| Operation | Typical consideration |
|---|---|
| Sequential scan | Good for broad table access |
| Index scan | Useful for selective predicates |
| Hash join | Efficient equality joins with memory available |
| Sort | `O(N log N)` comparison-based ordering |
| Hash aggregate | Fast grouping with memory consumption |
| Projection | Reduces result width |
| Limit | Reduces returned result size |
| CTE | Separates logical processing; optimizer behavior depends on PostgreSQL version and query shape |

Indexes improve some access paths but impose storage and write-maintenance costs.

Hash-based operators trade memory for faster expected lookup.

Sorting can become expensive as intermediate cardinality grows.

Reducing rows before expensive operators is often an important optimization.

## Edge Cases

The examples account for:

- empty index matches
- inactive customers
- orders below the threshold
- zero qualifying rows
- invalid limits
- invalid indexes
- missing fields
- duplicate output fields
- negative monetary values
- invalid foreign-key relationships
- execution failures
- transaction rollback

An empty result is a valid result and should not be treated as an execution error.

## Relationship Between the Five Implementations

The implementations share the same conceptual execution pipeline but do not mechanically reproduce one another.

Python emphasizes composable iterator-style operators.

JavaScript emphasizes asynchronous execution and event-compatible pipelines.

C++17 emphasizes explicit physical execution, ownership, and low-level data structures.

Java 17 emphasizes typed domain modeling, immutable records, generic operators, and explicit service state.

PostgreSQL demonstrates the complete database environment in which a mature optimizer, storage engine, statistics system, indexes, constraints, transactions, and execution engine cooperate.

The common abstraction is:

    Logical request
        |
        v
    Plan
        |
        v
    Operators
        |
        v
    Intermediate rows
        |
        v
    Result generation

The physical implementation can differ substantially while preserving the same logical result.
