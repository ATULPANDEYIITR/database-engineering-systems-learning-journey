# Query Processing: Parsing, Analysis, Rewriting and Planning

## Scope

This learning artifact models a compact relational query-processing pipeline:

`SQL text → lexical tokens → parsed query → semantic analysis → rewritten query → logical/physical plan → execution`

The implementation treats parsing, analysis, rewriting, and planning as distinct stages. Parsing determines syntactic structure. Analysis verifies that the requested objects and expressions are meaningful against a catalog. Rewriting changes a valid query representation without changing its intended result. Planning chooses an execution sequence. Execution is the final stage used by the executable examples to demonstrate that the planned representation can produce rows.

The examples use deliberately constrained SQL rather than attempting to implement the full SQL standard. The supported language includes `SELECT`, `FROM`, `WHERE`, `AND`, `ORDER BY`, `ASC`, `DESC`, `LIMIT`, aliases with `AS`, comparison operators, identifiers, numeric literals, string literals, and projection with `*`.

## Processing Model

The five implementation perspectives represent the same core concepts through different engineering models.

| Stage | Responsibility | Main artifact |
|---|---|---|
| Lexing | Convert characters into tokens | Token stream |
| Parsing | Establish grammatical structure | Query object |
| Analysis | Validate names and query semantics | Validated query |
| Rewriting | Apply safe representation changes | Rewritten query |
| Planning | Select executable operations | Physical plan |
| Execution | Apply the selected operations | Result rows |

The important distinction is that a parser does not need to know whether a table actually exists. That responsibility belongs to semantic analysis. A planner should not compensate for malformed SQL because malformed syntax should have failed before planning begins.

## Lexical Analysis

The Python, JavaScript, C++17, and Java 17 implementations contain explicit lexers.

The lexer scans the input from left to right and recognizes:

- keywords such as `SELECT`, `FROM`, `WHERE`, and `ORDER`
- identifiers such as table and column names
- integer literals
- quoted string literals
- comparison operators
- punctuation such as commas, semicolons, parentheses, and `*`

Whitespace is discarded.

Quoted strings are handled separately from identifiers so that values such as `'Security'` are not interpreted as column names. The implementations also recognize doubled single quotes inside string literals.

Unsupported characters generate lexical failures rather than being silently discarded. Unterminated strings are also rejected.

The resulting token stream provides a stable interface between character processing and grammar processing.

## Parsing

The parser consumes tokens according to a restricted SQL grammar.

A representative structure is:

`SELECT select_list FROM table [WHERE predicate [AND predicate...]] [ORDER BY column [ASC|DESC]] [LIMIT number]`

The parser constructs a structured query representation containing:

- selected expressions
- optional aliases
- source table
- predicates
- ordering column
- ordering direction
- optional row limit

This separates syntax from execution. A parsed query can therefore be analyzed or rewritten without repeatedly examining the original SQL characters.

A malformed query fails before semantic processing. Examples include a missing table name, an incomplete comparison, an invalid `LIMIT`, or unexpected trailing tokens.

## Semantic Analysis

Parsing can establish that `SELECT missing FROM employees` is syntactically valid while still being unable to determine whether `missing` is a real column.

Semantic analysis uses a catalog containing tables and their columns.

The validation rules include:

- referenced tables must exist
- projected columns must exist
- predicate columns must exist
- ordering columns must exist
- limits must not be negative

The catalog abstraction is intentionally separate from the parser. This reflects the database architecture in which parsing operates on language structure while semantic analysis resolves names against database metadata.

A semantic error therefore has a different meaning from a parse error.

## Query Rewriting

Rewriting operates after successful analysis.

The examples implement a deliberately conservative rewrite stage. A redundant predicate pattern is removed when it is known to have no useful filtering effect in the restricted model.

The important architectural property is the separation of representation transformation from parsing. A rewrite receives a structured query rather than raw SQL.

A production query processor can use this stage for transformations such as:

- predicate simplification
- constant folding
- predicate normalization
- projection pruning
- subquery transformations
- join reordering
- redundant expression elimination

Such transformations must preserve query semantics. The examples therefore keep the rewrite rules small enough to reason about directly.

## Planning

The planner converts a validated and rewritten query into an ordered sequence of operations.

The common plan shape is:

`TableScan → PredicateFilter → Sort → Limit → Projection`

Not every query requires every operation. A query without a predicate does not require filtering. A query without ordering does not require sorting. A query without a limit does not require a limit operation.

The C++ implementation represents this as a repository-independent execution plan with explicit node names. The Java implementation exposes a service-oriented planner. Python keeps the plan close to the query objects. JavaScript emits plan events through an event-driven engine.

The plan is deliberately simple, but it represents an important database principle: the execution strategy should be derived from query structure rather than hard-coded for each SQL string.

## Catalog and Metadata

The Python catalog stores table definitions and rows.

The JavaScript catalog uses a `Map` so table lookup is explicit and efficient.

The C++ catalog uses an `unordered_map`, giving average constant-time table-name lookup.

The Java implementation uses a `HashMap` for the same metadata responsibility.

The PostgreSQL implementation provides a relational metadata model containing:

- repositories
- tables
- columns
- indexes
- queries
- query-table relationships
- predicates
- plan nodes
- query lifecycle events

This makes the PostgreSQL implementation closer to a persistent query-processing control plane than an in-memory interpreter.

## Python Implementation

The Python implementation models the complete pipeline in one executable script.

Its primary components are:

| Component | Responsibility |
|---|---|
| `Lexer` | Converts SQL characters into typed tokens |
| `Parser` | Builds a `Query` object |
| `Catalog` | Resolves tables |
| `QueryPlanner` | Performs semantic validation, rewriting, and plan construction |
| `QueryExecutor` | Applies predicates, ordering, limits, and projection |
| `run_query` | Connects all processing stages |

Python `dataclass` types provide compact representations for tokens, conditions, selected expressions, queries, and tables.

The execution path is:

`SQL → Lexer → Parser → QueryPlanner.analyze → QueryPlanner.rewrite → QueryPlanner.plan → QueryExecutor`

The script also exercises failures for an unknown column and an unknown table.

A small benchmark repeats parsing, analysis, rewriting, and execution to expose the cost of repeatedly processing query text.

## JavaScript Implementation

The JavaScript implementation emphasizes event-driven processing.

`QueryEngine` extends `EventEmitter` and emits lifecycle events including:

- `queryReceived`
- `parsed`
- `rewritten`
- `planned`
- `executionStarted`
- `executionCompleted`

This design separates query processing from observers. Logging, metrics, tracing, or a user interface can subscribe to lifecycle events without modifying the parser or executor.

JavaScript `Map` and `Set` structures support catalog and column validation. The executor is asynchronous at its public boundary through `async` methods, allowing the same architecture to accommodate asynchronous storage or remote execution later without changing the query representation.

The implementation remains dependency-free and uses Node.js standard-library functionality.

## C++17 Implementation

The C++17 implementation treats query processing as a typed execution engine.

Its domain representation uses:

- `enum class TokenType`
- `std::variant` for numeric and string values
- structures for tokens, conditions, select items, queries, rows, and tables
- `std::unordered_map` for row and catalog lookup
- STL algorithms for filtering and sorting

The planner explicitly produces physical operations such as:

`TableScan`
`PredicateFilter`
`Sort`
`Limit`
`Projection`

The executor applies those operations against an in-memory catalog.

The use of `std::variant` prevents all literal values from being represented as untyped strings. Numeric comparisons therefore use numeric ordering rather than lexical ordering.

The implementation also separates lexical, parsing, semantic, planning, and execution exceptions.

## Java 17 Implementation

The Java implementation uses explicit enterprise-style domain boundaries.

Records represent immutable value objects such as:

- `Token`
- `SelectItem`
- `Condition`
- `Query`
- `Row`
- `Table`

The `QueryPolicy` interface separates semantic rules from the planner. `StrictQueryPolicy` implements validation for columns, predicates, ordering, and limits.

`Planner` is responsible for rewriting and physical-plan construction.

`ExecutionService` is responsible for applying the plan's relational behavior.

This produces a service relationship:

`Lexer → Parser → QueryPolicy → Planner → ExecutionService`

The design demonstrates why explicit domain types matter in larger systems. A policy can be replaced without rewriting parsing logic, and execution can evolve without changing the syntax model.

Java collections and streams are used selectively. Immutable records reduce accidental mutation of the query representation after parsing.

## PostgreSQL Implementation

The PostgreSQL script models persistent metadata and processing state.

The `query_processing` schema contains the central entities:

`repositories`
→ `tables_catalog`
→ `columns_catalog`

and query execution entities:

`queries`
→ `query_tables`
→ `query_predicates`
→ `plan_nodes`
→ `query_events`

The model distinguishes metadata from runtime query state.

`tables_catalog` represents relations known to the processing environment. `columns_catalog` represents their attributes. `indexes_catalog` stores simplified index metadata that can be consulted by a planner.

`queries` stores submitted SQL and its lifecycle state.

`query_predicates` represents analyzed predicates independently of the original SQL text.

`plan_nodes` records the selected execution sequence and allows estimated and actual execution metrics to be compared.

`query_events` records state transitions for observability.

## Query State Management

The PostgreSQL `query_status` enum represents:

`RECEIVED → PARSED → ANALYZED → REWRITTEN → PLANNED → EXECUTED`

A failed query enters `FAILED`.

A trigger prevents invalid forward transitions such as moving directly from `RECEIVED` to `EXECUTED`. This provides database-level enforcement rather than relying exclusively on application code.

The state model distinguishes processing lifecycle from query semantics. A query may be syntactically valid but fail semantic analysis. A valid analyzed query may still produce an unsuitable or failed execution plan in a more complete system.

## Execution Semantics

The implementations execute a limited relational model.

For a query such as:

`SELECT name, salary FROM employees WHERE salary >= 90000 ORDER BY salary DESC LIMIT 3`

the conceptual operations are:

`SCAN employees`
`FILTER salary >= 90000`
`SORT salary DESC`
`LIMIT 3`
`PROJECT name, salary`

Filtering reduces the candidate rows before sorting. The simplified engine performs filtering before sorting because sorting the entire relation would generally perform unnecessary work.

The actual cost behavior depends on available indexes, statistics, cardinality, and storage characteristics. The examples use a sequential scan because their data is held in memory and the datasets are intentionally small.

## Complexity Considerations

For an in-memory table containing `n` rows:

| Operation | Typical simplified cost |
|---|---:|
| Table lookup in catalog | O(1) average |
| Full scan | O(n) |
| Predicate filtering | O(n) per predicate |
| Sorting | O(n log n) |
| Limit after sorting | O(1) after sorted result is available |
| Projection | O(n × selected_columns) |

Multiple independent predicates can increase the filtering cost in the simplified executors because each predicate scans the intermediate row set.

A database optimizer can use indexes, predicate selectivity, statistics, join algorithms, and cost estimates to avoid unnecessary full scans or sorts.

## Failure Handling

The implementations distinguish several failure categories.

### Lexical failures

These occur when the input cannot be converted into valid tokens.

Examples include:

- unsupported characters
- unterminated strings

### Parse failures

These occur when tokens do not satisfy the supported grammar.

Examples include:

- missing `FROM`
- missing identifier
- missing comparison operator
- malformed `LIMIT`
- unexpected trailing tokens

### Semantic failures

These occur after successful parsing.

Examples include:

- unknown table
- unknown column
- unknown ordering column
- invalid limit

This separation makes error reporting more precise and prevents downstream stages from receiving malformed input.

## Security Considerations

The examples parse SQL text directly because their purpose is to demonstrate query-processing mechanisms. A production database application should not construct SQL by concatenating untrusted values.

The implementations provide no authentication, authorization, transaction isolation, network protocol, or storage-engine security layer.

The PostgreSQL schema uses primary keys, foreign keys, check constraints, and controlled status transitions to preserve metadata integrity.

The query processors also reject unsupported syntax instead of silently interpreting unknown constructs. Restricting the grammar is an important defensive property for a small embedded query engine.

For production SQL execution, parameterized statements should be used for external values rather than interpolating untrusted strings into SQL text.

## PostgreSQL Constraints and Transactions

The PostgreSQL model uses:

- primary keys for entity identity
- foreign keys for relationships
- unique constraints for catalog consistency
- check constraints for valid numerical and state values
- enum types for controlled lifecycle states
- indexes for repeated lookup patterns
- triggers for state-transition enforcement
- transactions for atomic query registration and failure recording

The sample transaction registers a query before subsequent processing states are recorded.

The failed-query example records an explicit error state rather than allowing a malformed workflow to appear successfully executed.

## Query Observability

The PostgreSQL event table creates a persistent processing history.

Each query can be examined through:

- current state
- timestamps
- referenced tables
- predicate count
- plan-node count
- event sequence
- estimated plan metrics
- actual execution metrics

This allows an operational system to compare estimated and actual behavior.

For example, if a filter is estimated to produce 9,000 rows but repeatedly produces 45,000, statistics or cardinality assumptions may be inaccurate. That discrepancy can influence future planning decisions.

## Relationship Between the Five Implementations

The implementations are intentionally complementary.

| Language | Primary perspective |
|---|---|
| Python | Complete educational query-processing simulator |
| JavaScript | Event-driven processing and observability |
| C++17 | Typed execution and physical-plan engine |
| Java 17 | Enterprise domain modeling and policy separation |
| PostgreSQL | Persistent metadata, lifecycle state, and plan reporting |

They do not represent five independent database products. They represent different ways to model the same processing concepts.

## Edge Cases

The examples explicitly handle:

- empty or malformed query structures
- unknown tables
- unknown columns
- invalid ordering columns
- negative limits
- unsupported characters
- unterminated string literals
- unexpected trailing tokens
- unsupported operators
- empty query predicates
- empty execution results

A production implementation would need many more cases, including joins, grouping, aggregation, null semantics, three-valued logic, subqueries, functions, type coercion, transactions, locking, permissions, and cost-based optimization.

## Limitations

This is a deliberately constrained query processor rather than a complete SQL implementation.

It does not implement:

- joins
- `GROUP BY`
- aggregate functions
- window functions
- subqueries
- common table expressions
- `NULL` and three-valued SQL logic
- type coercion
- date and timestamp literals
- expression trees
- arithmetic expressions
- indexes during actual in-memory execution
- cost-based join optimization
- statistics collection
- concurrent execution
- transaction isolation
- distributed planning

The PostgreSQL component models query-processing metadata and workflow rather than replacing PostgreSQL's native parser and optimizer.

## Practical Architecture

A larger query-processing system can extend the same separation:

`Client`
→ `SQL Parser`
→ `AST`
→ `Semantic Analyzer`
→ `Logical Rewrite`
→ `Optimizer`
→ `Physical Plan`
→ `Executor`
→ `Storage`

The key architectural boundary is the representation passed between stages. Once SQL text has become a structured representation, later phases should operate on that representation rather than repeatedly reparsing the original text.

The five implementations preserve this principle at different levels of detail.
