# PostgreSQL Indexes: B-tree, Hash, GIN, GiST, and BRIN

## Scope

This project examines five PostgreSQL index access methods:

- **B-tree** for general-purpose ordered access, equality, ranges, and sorting.
- **Hash** for equality-oriented lookup.
- **GIN** for inverted indexing of multi-valued and document-like data such as arrays and JSONB.
- **GiST** for extensible operator classes, with range overlap and containment as the primary example.
- **BRIN** for compact block-range summaries on very large tables where column values are correlated with physical row order.

The central design principle is that an index should be selected according to the operators used by a workload, the structure of the indexed data, selectivity, table size, physical ordering, and write-maintenance cost. An index is not simply a faster copy of a table.

The implementations use repository and pull-request analytics as the domain because the same workload naturally contains equality predicates, ordered timestamps, multi-valued labels, lifecycle ranges, and large chronological event histories.

## Why PostgreSQL Has Multiple Index Access Methods

A single index structure cannot efficiently represent every kind of search.

A B-tree maintains ordered keys. This makes it useful when a query asks for an exact value, a range, or rows in sorted order. A timestamp column is a natural B-tree candidate when the workload contains expressions such as `created_at >= ...` and `ORDER BY created_at`.

A Hash index maps keys according to hash values. Its useful semantic boundary is equality. It is therefore narrower than B-tree. A query asking whether `repository_id = 102` fits the equality model, while a query asking for `repository_id > 100` requires ordering semantics that Hash does not provide.

GIN has a different purpose. A row containing an array such as `['security', 'postgresql']` represents multiple searchable keys. A conventional scalar ordered index does not naturally model membership of each individual array element. GIN uses an inverted representation in which indexed keys point toward the rows containing those keys. This is well suited to PostgreSQL operators such as array containment and JSONB containment.

GiST is a generalized search framework whose behavior depends on an operator class. PostgreSQL range types provide a useful example. A lifecycle represented by `tstzrange(created_at, merged_at)` can be queried for overlap with another range. This is fundamentally different from asking for one scalar timestamp.

BRIN takes yet another approach. Instead of maintaining an index entry comparable to a normal row-level index entry for every tuple, it records summaries for ranges of physical table pages. A timestamp column inserted in chronological order can therefore allow PostgreSQL to eliminate large physical regions without storing a large B-tree-like structure. BRIN effectiveness depends strongly on correlation between the indexed value and physical storage order.

## B-tree

The Python implementation models a B-tree as sorted `(key, row_id)` entries. This is not PostgreSQL's internal implementation, but it exposes the important property: keys are ordered.

The model supports:

- Exact equality lookup through binary-search boundaries.
- Range lookup through lower and upper boundaries.
- Ordered retrieval for newest or oldest records.

The Python example indexes pull-request `state` and `created_at`. The timestamp index demonstrates why B-tree is more than an equality structure. The same ordered structure can serve equality, ranges, and ordering requirements.

The SQL implementation creates:

`idx_pr_state_btree`

for state equality and

`idx_pr_created_btree`

for timestamp filtering and ordering.

A composite B-tree,

`idx_pr_repository_created_btree`

demonstrates how a workload can combine repository filtering with chronological retrieval.

The important production distinction is that a B-tree index does not guarantee an index scan. PostgreSQL's planner estimates the cost of available plans. A sequential scan can be cheaper when a predicate matches a large proportion of a small table.

## Hash

The Python Hash model stores a dictionary of keys mapped to row identifiers. Its intended operation is direct equality lookup.

The JavaScript and C++ implementations treat Hash as an equality-specialized alternative to B-tree. This distinction matters because it prevents the common mistake of assuming that all index types are interchangeable.

The SQL implementation creates:

`idx_pr_repository_hash`

on `repository_id`.

The query

`WHERE repository_id = 2`

has the required equality semantics. A Hash index does not provide the ordering behavior of B-tree, so it is not a substitute when the workload also requires range conditions or ordered retrieval.

The planner is still free to select a sequential scan or another available index. Index presence is an available access path, not an execution command.

## GIN

GIN stands for Generalized Inverted Index.

Its natural use case is a row containing multiple searchable values. The SQL example stores pull-request labels in a PostgreSQL `text[]` column:

`ARRAY['security', 'postgresql']`

The GIN index:

`idx_pr_labels_gin`

supports array-oriented predicates such as:

`labels @> ARRAY['security', 'postgresql']`

and:

`labels && ARRAY['security', 'performance']`

The first asks whether the row contains all requested values. The second asks whether the row contains at least one value from the requested set.

The same access-method family is also demonstrated with JSONB. The metadata column contains structured attributes such as:

`{"risk":"critical","component":"database"}`

The GIN index on `metadata` supports JSONB containment queries.

This differs materially from B-tree. The important question is not simply whether a value is equal to another value. The indexed row contains a collection of keys, and the query asks about the relationship between the collection and a requested set of keys.

GIN can have meaningful write and storage overhead because one row may contribute many indexed keys. This trade-off matters for frequently updated tables.

## GiST

GiST means Generalized Search Tree.

The project uses PostgreSQL's built-in `tstzrange` type so that a pull request can have a lifecycle interval:

`[created_at, merged_at)`

An unmerged pull request uses an open-ended upper boundary represented by PostgreSQL's range semantics.

The GiST index:

`idx_pr_lifecycle_gist`

supports range-oriented predicates.

The overlap query uses:

`lifecycle && tstzrange(...)`

This asks whether two intervals intersect.

A containment query uses:

`lifecycle <@ tstzrange(...)`

which asks whether one range is contained within another.

This is not merely a different spelling of a B-tree range condition. A B-tree works naturally with ordered scalar keys. GiST provides an operator-class-driven search framework that can represent relationships such as overlap between ranges.

The Java implementation makes this distinction explicit through the `RANGE_OVERLAP` predicate type, while the C++ case study treats overlap as a separate workload category from scalar equality and range filtering.

## BRIN

BRIN means Block Range Index.

The key distinction is physical granularity.

A conventional row-oriented index can maintain search information for individual indexed values. BRIN instead summarizes groups of table pages. For a timestamp column, a summary can represent the minimum and maximum timestamp associated with a physical page range.

If a query requests a date interval that cannot intersect a summary range, PostgreSQL can skip the corresponding table pages.

The SQL script creates:

`idx_pr_created_brin`

on `created_at`.

The pull requests are deliberately inserted in chronological order. This creates physical correlation between `created_at` and heap position, which is the condition that makes BRIN particularly useful.

The Python implementation includes a separate physical-correlation experiment. It constructs BRIN-like summaries once with chronological insertion order and again after randomizing the rows. The conceptual result demonstrates why a BRIN index can lose effectiveness when the indexed column is poorly correlated with physical storage.

BRIN is particularly attractive for very large append-oriented tables such as historical events, telemetry, logs, or time-series-like operational records. Its compactness does not mean it can answer every predicate without visiting heap pages. It identifies candidate page ranges, after which PostgreSQL may still inspect rows in those ranges.

## How the Access Methods Relate

| Access method | Natural predicate | Data characteristic | Main strength | Important limitation |
| --- | --- | --- | --- | --- |
| B-tree | `=`, `<`, `>`, ranges, ordering | Ordered scalar values | Broad general-purpose access | Can be unnecessary for low-selectivity scans |
| Hash | Equality | Scalar equality keys | Equality lookup | No ordering or range semantics |
| GIN | Collection/document containment | Arrays, JSONB, multiple keys | Inverted membership search | Can require substantial index storage and write work |
| GiST | Operator-class-defined relationships | Ranges and other specialized structures | Extensible relationship-oriented search | Effectiveness depends on operator class and data |
| BRIN | Physical-range filtering | Large correlated tables | Very small index footprint | Requires useful physical correlation |

These categories should not be treated as interchangeable labels.

A query such as `repository_id = 102` belongs to the scalar equality category.

A query such as `created_at BETWEEN ... AND ...` belongs to ordered range access.

A query such as `labels @> ARRAY[...]` belongs to collection containment.

A query such as `lifecycle && tstzrange(...)` belongs to range relationship evaluation.

A chronological event table where values follow physical insertion order is a candidate for BRIN because the access method exploits storage correlation rather than merely scalar ordering.

## Python Implementation

The Python program provides executable models for all five access methods.

`BTreeIndex` maintains sorted key-row pairs and uses `bisect_left` and `bisect_right` for equality and range boundaries. It also demonstrates ordered retrieval.

`HashIndex` stores hash buckets in a dictionary and exposes equality lookup only.

`GINIndex` builds posting lists from pull-request labels. `contains_all()` intersects posting sets, while `contains_any()` performs a union-like membership operation.

`GiSTRangeIndex` represents pull-request lifecycles as intervals and evaluates overlap between two ranges. The implementation is intentionally a conceptual model rather than a claim that PostgreSQL's internal GiST algorithm is implemented with the same Python loop.

`BRINIndex` groups rows into physical blocks and stores minimum and maximum values for each block. A range query eliminates blocks whose summary cannot intersect the requested interval.

The program also performs invariant checks so that the modeled indexes can be compared against direct row filtering.

## JavaScript Implementation

The JavaScript implementation uses an event-driven query workload rather than translating the Python index classes.

`QueryEventBus` emits `query:planned` events after a query has been classified.

`IndexCatalog` represents the available PostgreSQL access methods and the operators they support.

`QueryPlanner` chooses an access method based on predicate semantics. Equality receives special handling because both B-tree and Hash can support it, while B-tree has broader ordered capabilities.

`QueryExecutor` evaluates the same predicates against an in-memory workload containing repository IDs, labels, timestamps, and lifecycle intervals.

This separation mirrors an important database-engineering distinction: predicate classification, access-path selection, and row evaluation are related but separate responsibilities.

The program also demonstrates validation failure for an unsupported predicate rather than silently pretending that every operator has an appropriate index.

## C++ Case Study

The C++ program models a database platform team's index-advisor workload.

`IndexDefinition` describes an index's access method, indexed column, supported predicate classes, and operational rationale.

`IndexAdvisor` evaluates workload predicates and chooses a structurally appropriate access method. Equality receives special treatment so that B-tree is preferred when both B-tree and Hash are possible.

`RepositoryWorkload` represents repository activity containing scalar repository identifiers, labels, creation positions, and lifecycle durations.

The workload distinguishes equality, collection containment, scalar ranges, and interval overlap. This keeps the technical categories separate instead of treating every query as a generic lookup.

The final distribution report shows which access methods the workload would require and explains why the methods have different operational roles.

The case study also emphasizes an important production property: an advisor can identify a structurally appropriate index, but PostgreSQL's cost-based planner ultimately determines whether using that index is cheaper than another execution plan.

## Java Implementation

The Java program presents the topic as an enterprise repository-governance service.

`IndexPolicy` explicitly describes an access method, indexed column, supported predicate types, and operational purpose.

`QueryRequest` represents a typed query requirement rather than a raw SQL string. `PredicateType` separates equality, range, ordering, array containment, and range overlap.

`IndexSelectionService` applies the index policies and resolves the special case where equality is supported by both B-tree and Hash.

`RepositoryEvent` is an immutable Java record. It validates lifecycle ordering when an event is constructed, preventing an invalid interval from entering the domain model.

`RepositoryQueryService` executes domain-specific predicates over immutable event data. The implementation therefore separates domain validation, access-method policy, and query behavior.

This structure is useful for enterprise systems because index selection policies can be represented explicitly rather than being hidden inside unrelated conditional statements.

## SQL Data Model

The PostgreSQL schema contains:

- `repositories`, which owns repository identities and teams.
- `pull_requests`, which contains scalar state, timestamps, labels, and JSONB metadata.
- `repository_events`, which represents operational events with JSONB payloads.

The pull-request table contains a generated `tstzrange` lifecycle column. This makes the temporal relationship explicit and allows the GiST example to use PostgreSQL's native range operators.

The temporal check constraint prevents `merged_at` from occurring before `created_at`.

Foreign keys enforce repository ownership.

The `state` check constraint limits pull-request state to valid domain values.

The label array and JSONB metadata provide data structures that genuinely benefit from GIN.

The chronological `created_at` column provides the workload for B-tree and BRIN comparison.

## SQL Indexes and Constraints

The SQL script creates multiple B-tree indexes because B-tree supports several important access patterns:

- State equality.
- Timestamp ranges.
- Timestamp ordering.
- Repository plus timestamp access through a composite key.

The Hash index targets repository equality.

The GIN label index supports array containment and overlap.

The GIN metadata index supports JSONB containment.

The GiST lifecycle index supports range overlap and range containment.

The BRIN timestamp index summarizes physical page ranges and uses a small `pages_per_range` value so its behavior is easier to observe in a demonstration dataset.

The script calls `ANALYZE` because PostgreSQL's planner relies on statistics when estimating query costs.

## Planner Behavior

An important distinction is the difference between **index applicability** and **index selection**.

An index may support the operators in a query without being used by the planner.

For example, a B-tree may support a predicate, but PostgreSQL may choose a sequential scan if the table is small or if the predicate is expected to return a large proportion of rows.

The same principle applies to Hash, GIN, GiST, and BRIN.

`EXPLAIN (ANALYZE, BUFFERS)` is therefore more meaningful than merely inspecting whether an index exists. It reveals the actual execution plan, execution timing, buffer activity, and whether the selected access path matched expectations.

The SQL script deliberately uses `EXPLAIN` rather than asserting that a particular access method must always appear in the plan.

## Selectivity and Table Size

Index usefulness depends heavily on selectivity.

A highly selective predicate may identify a small number of rows, making index navigation valuable.

A predicate that matches most rows may require so much heap access that a sequential scan becomes cheaper.

Table size also changes the cost balance. A sequential scan over a tiny table can be extremely cheap even when a theoretically applicable index exists.

BRIN changes this calculation because its index itself can remain very small. It is particularly attractive when a huge table has natural physical ordering, such as events appended by timestamp.

GIN has a different trade-off. One row can produce many indexed keys, so a GIN index can be substantially larger and more expensive to maintain than a simple scalar B-tree.

## Composite B-tree Considerations

The SQL script includes:

`(repository_id, created_at)`

as a composite B-tree.

Column order matters. A composite index is not equivalent to maintaining two unrelated indexes.

The leading column, `repository_id`, defines the first major ordering dimension. A workload filtering by repository and then ordering or filtering by creation time can make good use of this arrangement.

The design should therefore reflect actual query predicates rather than mechanically indexing every frequently queried column.

## Common Design Errors

### Treating Hash as a universal replacement for B-tree

Hash is designed around equality. It does not provide the ordering semantics that make B-tree useful for range predicates and `ORDER BY`.

### Using GIN for ordinary scalar ordering

GIN is valuable for multi-key membership and containment. A scalar timestamp ordering problem is not naturally a GIN workload.

### Using GiST without understanding the operator class

GiST is a generalized framework. Its usefulness depends on the indexed data type and operator class. Creating a GiST index without identifying the operators it needs to accelerate does not establish that it is a useful index.

### Choosing BRIN solely because the index is small

BRIN's compactness is not enough. Its value depends on correlation between the indexed value and physical table layout.

### Assuming an index forces PostgreSQL to use it

The optimizer chooses execution plans based on estimates and costs. `CREATE INDEX` does not mean `Index Scan` is guaranteed.

### Ignoring write cost

Every additional index creates maintenance work during `INSERT`, `UPDATE`, and `DELETE` operations. An index that improves one rare query while substantially increasing write overhead may be a poor production decision.

## Debugging and Verification

Index design should be evaluated through actual workload evidence.

Useful PostgreSQL inspection includes:

`EXPLAIN (ANALYZE, BUFFERS)`

for execution behavior and:

`pg_index`

and:

`pg_am`

for inspecting index definitions and access methods.

The SQL script queries these catalog structures to expose the actual access method associated with each created index.

For BRIN, physical correlation should be considered explicitly. A timestamp column whose values are inserted in chronological order is a stronger BRIN candidate than the same column after extensive random physical placement.

For GIN, the number and distribution of indexed keys matter because collection-heavy rows can increase index size and maintenance cost.

For GiST, the relevant operator class and the selectivity of spatial or range relationships determine practical usefulness.

## Production Considerations

Index design is a workload decision rather than a datatype-only decision.

A production review should consider:

- Query predicates and operators rather than column names alone.
- Selectivity and expected result size.
- Table growth and expected data volume.
- Insert, update, and delete frequency.
- Physical correlation for BRIN candidates.
- Collection cardinality for GIN candidates.
- Operator-class requirements for GiST.
- Composite-column order for B-tree indexes.
- Planner statistics and maintenance.
- Actual execution plans rather than assumptions about index usage.
- Storage consumption and operational maintenance.

The five access methods solve different search problems. B-tree provides broad ordered access, Hash specializes in equality, GIN indexes multiple contained keys, GiST represents generalized operator relationships such as range overlap, and BRIN summarizes physically grouped data. Good PostgreSQL index design comes from matching those properties to the workload rather than selecting an index type by habit.
