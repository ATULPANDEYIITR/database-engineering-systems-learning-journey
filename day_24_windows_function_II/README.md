# Window Functions II: ROW_NUMBER, RANK, DENSE_RANK, NTILE

## Topic introduction

Window functions calculate values across a related set of rows while preserving the individual rows in the result. Ranking window functions are especially useful when data must be ordered, compared, grouped into positions, or divided into segments.

This study focuses on four SQL window functions:

- `ROW_NUMBER()`
- `RANK()`
- `DENSE_RANK()`
- `NTILE(n)`

The central distinction is how these functions treat rows that have equal values in their window ordering.

For ordered values such as `100, 100, 90, 80`:

| Function | Result |
|---|---|
| `ROW_NUMBER()` | `1, 2, 3, 4` |
| `RANK()` | `1, 1, 3, 4` |
| `DENSE_RANK()` | `1, 1, 2, 3` |
| `NTILE(2)` | `1, 1, 2, 2` |

`ROW_NUMBER()` assigns a distinct position to every row. `RANK()` gives equal values the same rank and leaves gaps after ties. `DENSE_RANK()` gives equal values the same rank without gaps. `NTILE()` assigns rows to approximately equal-sized buckets.

The three implementations in this study demonstrate these mechanics from different programming perspectives.

## Fundamental window-function concepts

A ranking expression commonly follows this structure:

`FUNCTION() OVER (PARTITION BY ... ORDER BY ...)`

The important components are:

### Window function

The function determines what value is calculated for each row.

Examples include:

- `ROW_NUMBER()`
- `RANK()`
- `DENSE_RANK()`
- `NTILE(4)`

### `OVER`

The `OVER` clause defines the window over which the function operates.

A window does not normally collapse rows into one row per group. Each source row can remain visible while receiving a calculated value.

### `PARTITION BY`

`PARTITION BY` divides the input into independent groups.

For example:

`PARTITION BY department`

means that employees in Engineering are ranked independently from employees in Sales and HR.

Without `PARTITION BY`, the ranking is calculated across the entire input set.

This distinction is important:

`RANK() OVER (ORDER BY salary DESC)`

produces one global ranking.

`RANK() OVER (PARTITION BY department ORDER BY salary DESC)`

produces one ranking sequence per department.

### `ORDER BY`

The window's `ORDER BY` determines the ordering used to calculate the ranking.

For example:

`ORDER BY salary DESC`

places the highest salary first.

`ORDER BY salary ASC`

places the lowest salary first.

The direction is therefore part of the meaning of the ranking.

## `ROW_NUMBER()`

`ROW_NUMBER()` assigns a unique sequential number to every row within each partition.

Conceptually:

`ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC)`

If salaries are:

`100000, 100000, 90000, 80000`

the row numbers are:

`1, 2, 3, 4`

The two employees earning `100000` do not receive the same row number.

### Main characteristics

`ROW_NUMBER()`:

- always assigns one number to every row;
- starts at `1` within each partition;
- does not assign the same number to two rows in the same ordered partition;
- is useful when physical rows must be selected;
- is particularly useful for top-N-per-group queries;
- is frequently used for deduplication.

### Deterministic ordering

If the ordering expression does not uniquely distinguish rows, tied rows may have an unspecified relative order.

For example:

`ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC)`

does not specify which employee receives row number `1` when two employees have the same salary.

A deterministic secondary key can be used:

`ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC, employee_id ASC)`

If `employee_id` is unique, every row has a deterministic position.

This distinction is important because adding a unique tie-breaker to `ROW_NUMBER()` determines which row gets which number.

## `RANK()`

`RANK()` assigns the same rank to rows that have equal values in the window ordering.

For:

`100, 100, 90, 80`

the result is:

`1, 1, 3, 4`

The gap between `1` and `3` exists because two rows occupy rank `1`.

This is the same general concept used by competition-style ranking.

### Main characteristics

`RANK()`:

- gives equal ordering values the same rank;
- starts at `1`;
- leaves gaps after ties;
- is appropriate when tied positions should be preserved;
- can return more than N rows when filtering for the top N ranks.

For example, if three employees share first place, the next employee receives rank `4`.

## `DENSE_RANK()`

`DENSE_RANK()` also gives equal values the same rank, but it does not leave gaps.

For:

`100, 100, 90, 80`

the result is:

`1, 1, 2, 3`

The two `100` values form one rank, `90` becomes the second distinct value, and `80` becomes the third.

### Main characteristics

`DENSE_RANK()`:

- gives equal ordering values the same rank;
- starts at `1`;
- does not create gaps after ties;
- is useful for ranking distinct value levels;
- is useful when the second-highest or third-highest distinct value is required.

For example, if a department has salaries:

`120000, 110000, 110000, 95000`

the dense ranks are:

`1, 2, 2, 3`

The second-highest distinct salary is therefore `110000`.

## `NTILE(n)`

`NTILE(n)` divides the ordered rows in each partition into approximately equal-sized buckets.

For example:

`NTILE(4)`

attempts to create four groups.

It is commonly used for:

- quartiles;
- deciles;
- customer segmentation;
- risk bands;
- performance cohorts;
- approximate percentile-style grouping.

`NTILE()` is fundamentally different from the three ranking functions because it is primarily a bucket-assignment function.

### NTILE distribution

Suppose there are `10` rows and `4` buckets.

The rows cannot be divided into four equal groups because:

`10 / 4 = 2 remainder 2`

The first two buckets receive three rows each and the remaining two buckets receive two rows each.

The conceptual distribution is:

`3, 3, 2, 2`

If there are `11` rows:

`3, 3, 3, 2`

If there are `12` rows:

`3, 3, 3, 3`

When the number of buckets exceeds the number of rows, some bucket numbers have no rows.

## Ranking comparison

Consider these ordered values:

| Value | `ROW_NUMBER()` | `RANK()` | `DENSE_RANK()` |
|---:|---:|---:|---:|
| 100 | 1 | 1 | 1 |
| 100 | 2 | 1 | 1 |
| 90 | 3 | 3 | 2 |
| 90 | 4 | 3 | 2 |
| 80 | 5 | 5 | 3 |

The differences become clear when ties occur.

### `ROW_NUMBER()` versus `RANK()`

`ROW_NUMBER()` distinguishes physical rows even when their ordering values are equal.

`RANK()` treats equal ordering values as tied.

### `RANK()` versus `DENSE_RANK()`

Both functions preserve ties.

The difference is what happens after a tie.

For:

`100, 100, 90`

`RANK()` gives:

`1, 1, 3`

`DENSE_RANK()` gives:

`1, 1, 2`

### `DENSE_RANK()` versus `NTILE()`

`DENSE_RANK()` is determined by distinct ordering values.

`NTILE()` is determined by row positions and the requested number of buckets.

Therefore, `NTILE()` does not behave like a ranking function that simply removes or preserves rank gaps.

## Tie handling and `ORDER BY`

The definition of a tie depends on the expressions used by the ranking function's `ORDER BY`.

Consider:

`RANK() OVER (PARTITION BY department ORDER BY salary DESC)`

Two employees with the same salary tie.

Now consider:

`RANK() OVER (PARTITION BY department ORDER BY salary DESC, employee_id ASC)`

If `employee_id` is unique, the complete ordering key is unique. Equal salaries no longer produce the same complete ordering key.

This is a subtle but important distinction.

A unique secondary ordering column is often appropriate for `ROW_NUMBER()` because it provides deterministic physical ordering.

It can change the semantic meaning of `RANK()` or `DENSE_RANK()` if the intention was to rank only by salary.

## Top N per group

A common analytical problem is selecting the highest-paid employees in every department.

`ROW_NUMBER()` is appropriate when exactly N physical rows are required.

The conceptual SQL pattern is:

`ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC, employee_id ASC)`

followed by filtering for row number less than or equal to N in an outer query or common table expression.

For N equal to `2`, every department contributes at most two physical rows.

This is different from using `RANK()`.

## Top N with ties

Suppose a department has salaries:

`120000, 110000, 110000, 90000`

Filtering:

`RANK() <= 2`

returns three rows:

- `120000`
- `110000`
- `110000`

This happens because both employees earning `110000` share rank `2`.

Therefore:

- `ROW_NUMBER() <= N` limits physical rows;
- `RANK() <= N` limits ranking positions and can preserve ties.

The choice depends on the intended business rule.

## Second-highest distinct value

`DENSE_RANK()` is particularly useful when the requirement refers to a distinct value.

For:

`120000, 110000, 110000, 90000`

the dense ranks are:

`1, 2, 2, 3`

Filtering for `DENSE_RANK() = 2` returns both employees earning `110000`.

The same approach works for:

- second-highest price;
- third-highest transaction amount;
- second-highest performance score;
- third-highest distinct compensation level.

## Deduplication with `ROW_NUMBER()`

A frequent data-processing pattern is retaining the latest record for each entity.

Suppose a customer has multiple records with different update timestamps.

A window expression can conceptually use:

`ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY updated_at DESC, record_id DESC)`

The latest record receives `1`.

Filtering for `1` retains the preferred record.

This is one of the most practical uses of `ROW_NUMBER()`.

The secondary identifier is useful when two records have the same timestamp and a deterministic choice is required.

## Python implementation

The Python implementation builds a small in-memory model of SQL window processing.

### Partitioning

`partition_rows()` groups dictionaries according to selected partition columns.

A department becomes the partition key in the employee examples.

The implementation uses a dictionary whose keys represent combinations of partition values.

### Ordering

`sort_partition()` creates an ordered copy of each partition.

The implementation supports multiple ordering columns and both ascending and descending directions.

This makes it possible to represent an expression such as:

`ORDER BY salary DESC, employee_id ASC`

### `ROW_NUMBER`

The Python `row_number()` function:

1. creates partitions;
2. sorts each partition;
3. enumerates the ordered rows from `1`;
4. attaches the resulting number to each row.

The implementation demonstrates the fundamental algorithm directly.

### `RANK`

The Python `rank_rows()` implementation compares each row's ordering key with the previous row.

When the ordering key changes, the current physical position becomes the new rank.

This creates gaps after ties.

### `DENSE_RANK`

The Python `dense_rank_rows()` implementation increments the rank only when the ordering key changes.

The physical position is not used as the new rank.

This removes gaps after ties.

### `NTILE`

The Python `ntile_rows()` implementation uses integer division and the remainder to calculate bucket sizes.

For `q` rows and `n` buckets:

`q = n × base_size + remainder`

The first `remainder` buckets receive one extra row.

This reproduces the essential distribution behavior of `NTILE()`.

### Reusable ranking engine

The `RankingSpecification` dataclass separates a window definition from the ranking operation.

`WindowRankingEngine` then applies the same specification to:

- `ROW_NUMBER`;
- `RANK`;
- `DENSE_RANK`;
- `NTILE`.

This reflects an important software-design principle: the window specification and the operation can be represented separately.

## JavaScript implementation

The JavaScript implementation focuses on practical application-level data processing.

It uses:

- arrays;
- objects;
- `Map`;
- array copying;
- sorting;
- classes;
- validation;
- asynchronous functions;
- assertions;
- performance measurement.

### JavaScript partitioning

`partitionRows()` uses `Map` to construct independent partitions.

A composite key is serialized so multiple partition columns can be represented.

### JavaScript ordering

`compareRows()` supports multiple ordering expressions.

Each expression specifies:

- a column;
- ascending or descending direction.

The implementation copies arrays before sorting so the source data is not unintentionally mutated.

### JavaScript ranking engine

`WindowRankingEngine` stores:

- partition columns;
- ordering columns.

The same configuration can then be used with all four ranking operations.

This demonstrates how a JavaScript application could encapsulate a reusable analytical transformation.

### Asynchronous example

The sales-analysis example uses an `async` function and a Promise-based data loader.

The Promise represents the kind of asynchronous data access commonly found in applications.

The ranking logic itself remains independent of the asynchronous transport mechanism.

## C++ case study

The C++ implementation models a regional sales analytics system.

Each record contains:

- `saleId`;
- `region`;
- `salesperson`;
- `revenue`.

The application partitions sales by region and calculates the four ranking values.

### Problem being solved

A business analytics system needs to answer several questions:

- Who is the highest-revenue salesperson in each region?
- What is each salesperson's competition-style rank?
- What is the salesperson's distinct revenue level?
- Which approximate performance bucket does each salesperson occupy?
- Who belongs to the top two physical rows?
- Who belongs to the top two ranking positions including ties?
- What is the second-highest distinct revenue level?

These questions map naturally to the four window functions.

### Architecture

The C++ case study separates responsibilities into several components.

`SalesRecord`

Represents source business data.

`RankedSalesRecord`

Stores a source record together with calculated ranking values.

`WindowSpecification`

Represents the conceptual window configuration.

`RegionalSalesAnalytics`

Provides higher-level business operations such as:

- complete ranking analysis;
- top N per region;
- top N positions with ties;
- second-highest distinct revenue.

Utility functions handle formatting and output.

Validation functions check input constraints before analytical processing.

### Partitioning

`partitionByRegion()` stores sales records in a map keyed by region.

This represents:

`PARTITION BY region`

Each region is processed independently.

### Sorting

`sortByRevenueDescending()` orders each partition by:

1. revenue descending;
2. sale ID ascending.

Revenue defines the business ranking.

Sale ID provides deterministic ordering for physical row positions.

### `ROW_NUMBER` in C++

`calculateRowNumber()` assigns a sequential position to each sorted row.

For a region containing four rows, the values are:

`1, 2, 3, 4`

The function does not treat equal revenue as a tie for purposes of the physical row number.

### `RANK` in C++

`calculateRank()` compares revenue values.

If two consecutive rows have equal revenue, they receive the same rank.

When a new revenue value appears, the rank becomes the physical position.

This creates gaps after ties.

### `DENSE_RANK` in C++

`calculateDenseRank()` increments the rank only when the revenue changes.

Consequently, equal revenue values share one rank and no gap is introduced.

### `NTILE` in C++

`calculateNTile()` implements the bucket distribution mathematically.

The number of rows is divided by the requested bucket count.

The quotient determines the base bucket size and the remainder determines how many buckets receive one additional row.

### Business-level methods

The C++ class demonstrates how low-level ranking operations can support higher-level analytics.

`topNPerRegion()` uses `ROW_NUMBER()` semantics.

`topNWithTies()` uses `RANK()` semantics.

`secondHighestDistinctRevenue()` uses `DENSE_RANK()` semantics.

This separation makes the difference between SQL mechanics and business requirements explicit.

## Important distinctions

| Requirement | Appropriate function |
|---|---|
| Unique position for every row | `ROW_NUMBER()` |
| Competition rank with gaps | `RANK()` |
| Competition rank without gaps | `DENSE_RANK()` |
| Approximately equal-sized buckets | `NTILE(n)` |
| Exactly N physical rows per group | Usually `ROW_NUMBER()` |
| Top N positions including ties | Usually `RANK()` |
| Nth distinct ordered value | Usually `DENSE_RANK()` |
| Quartile or decile segmentation | `NTILE()` |

These descriptions concern the ranking behavior itself. The complete SQL query must still account for filtering, null behavior, ordering requirements, and database-specific execution characteristics.

## Window ordering versus final result ordering

A window function's `ORDER BY` and the final query's `ORDER BY` serve different purposes.

A query can conceptually calculate:

`ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC)`

while the final result is ordered by:

`ORDER BY employee_id`

The window ordering determines the row number.

The final `ORDER BY` determines how the result set is displayed or returned.

Confusing these two ordering operations is a common source of SQL debugging errors.

## Filtering window-function results

Window functions are generally calculated after the `WHERE` filtering phase.

A direct predicate such as a same-level `WHERE row_number <= 2` is therefore not normally valid when `row_number` is an alias produced by the same `SELECT`.

A common structure is:

1. calculate the window function in a subquery or CTE;
2. filter the generated ranking column in an outer query.

This is the standard pattern for top-N-per-group analysis.

## Edge cases

### Empty input

An empty input produces no ranking rows.

There are no rows to rank or place into buckets.

### Single-row partition

A partition containing one row gives that row:

- `ROW_NUMBER = 1`;
- `RANK = 1`;
- `DENSE_RANK = 1`.

For `NTILE(5)`, the existing row occupies bucket `1`; there are not enough rows to populate every bucket.

### More buckets than rows

If `NTILE(n)` requests more buckets than there are rows, some bucket numbers receive no rows.

This does not mean rows are duplicated to populate all buckets.

### Invalid bucket count

`NTILE()` requires a positive bucket count.

The Python, JavaScript, and C++ implementations explicitly reject zero or negative bucket counts.

### Ties

Ties are meaningful only according to the expressions defining the window ordering.

Adding more ordering expressions can change which rows are considered equal.

### Null values

The exact ordering of null values can vary by SQL database system and query syntax.

Production SQL should explicitly account for the target database's null-ordering behavior where nulls are possible.

The educational implementations avoid relying on database-specific null-ranking semantics.

## Common mistakes

### Mistaking `RANK()` for `ROW_NUMBER()`

`RANK()` allows equal rows to share a position.

`ROW_NUMBER()` does not.

### Mistaking `RANK()` for `DENSE_RANK()`

`RANK()` creates gaps after ties.

`DENSE_RANK()` does not.

### Assuming `NTILE()` creates perfectly equal groups

Perfect equality is possible only when the number of rows divides evenly by the number of buckets.

Otherwise, some buckets receive one more row than others.

### Forgetting `PARTITION BY`

Without `PARTITION BY`, the ranking is global.

If the requirement is one ranking per department, region, customer, or other entity, the appropriate partition must be defined.

### Adding an unintended unique tie-breaker

A unique secondary ordering column is useful for deterministic `ROW_NUMBER()` results.

For `RANK()` and `DENSE_RANK()`, a unique secondary column can remove intended ties and therefore change the ranking semantics.

### Filtering too early

Filtering source rows before the window function changes the population being ranked.

Filtering after ranking can produce a fundamentally different result.

This is important when deciding whether a condition belongs before or after the window calculation.

### Ignoring final ordering

The order used to calculate a ranking is not necessarily the order in which the final result is returned.

An explicit final `ORDER BY` should be used when result ordering matters.

## Performance considerations

Ranking functions commonly require the database engine to organize rows according to partitioning and ordering requirements.

For a partition of `k` rows, a conceptual in-memory implementation can have:

- partition construction: approximately `O(k)`;
- sorting: approximately `O(k log k)`;
- `ROW_NUMBER()` assignment after sorting: `O(k)`;
- `RANK()` assignment after sorting: `O(k)`;
- `DENSE_RANK()` assignment after sorting: `O(k)`;
- `NTILE()` assignment after sorting: `O(k)`.

For `n` total rows, sorting is frequently the dominant operation.

The exact database cost depends on:

- indexes;
- table size;
- data distribution;
- statistics;
- available memory;
- parallel execution;
- sorting strategy;
- partition structure;
- query predicates;
- database optimizer behavior;
- physical execution plan.

The Python, JavaScript, and C++ implementations explicitly materialize and sort partitions. A production database engine may use substantially different execution strategies.

## Performance practices

For large analytical queries:

- filter unnecessary source rows before ranking when the business logic permits it;
- select only required columns;
- use deterministic ordering where reproducibility is required;
- inspect execution plans;
- understand the database's indexing capabilities;
- avoid unnecessary window functions;
- avoid ranking data that can be reduced before the window operation;
- evaluate memory and sorting behavior for large partitions.

A particularly large single partition can require substantial sorting and memory resources even if the overall table is not exceptionally large.

## Security considerations

Ranking functions themselves are not normally a security boundary.

The security risks usually come from how the SQL query is constructed and what data the query exposes.

Important production practices include:

- parameterize user-supplied filter values;
- do not concatenate untrusted input into SQL identifiers or expressions;
- restrict database permissions;
- expose only required columns;
- apply row-level security where appropriate;
- avoid revealing sensitive ranking information without authorization;
- validate application-level inputs such as requested bucket counts and limits.

A ranking query can unintentionally reveal sensitive business information if the underlying data contains compensation, customer value, credit, performance, or other restricted attributes.

## Implementation considerations

### SQL

SQL is the natural environment for these functions because modern relational database systems can execute ranking operations close to the data.

The database optimizer can decide how to partition, sort, and process rows.

### Python

Python is useful for making the underlying algorithm explicit.

The implementation demonstrates:

- dictionaries;
- lists;
- sorting;
- grouping;
- dataclasses;
- reusable classes;
- assertions;
- validation.

It is especially useful for understanding what a window operation conceptually does.

### JavaScript

JavaScript is useful when ranked data becomes part of an application or web interface.

The implementation demonstrates:

- array transformations;
- `Map`;
- object spread;
- reusable classes;
- asynchronous processing;
- application-style data handling;
- validation and runtime assertions.

### C++

C++ makes the algorithmic and systems aspects explicit.

The case study demonstrates:

- structs;
- classes;
- maps;
- vectors;
- sorting;
- validation;
- exception handling;
- deterministic ordering;
- synthetic performance testing;
- explicit complexity considerations.

## Production considerations

The in-memory implementations are educational models of SQL window behavior.

They should not be interpreted as replacements for a database query engine.

A production SQL system can optimize these operations using physical execution strategies that are not represented by the Python, JavaScript, or C++ examples.

Production query design should consider:

- the size of the source table;
- the size of individual partitions;
- required ordering;
- deterministic tie-breaking;
- filtering order;
- indexes;
- execution plans;
- memory requirements;
- concurrency;
- transaction semantics;
- data freshness;
- access control.

The business definition of a tie should also be established before selecting the function.

## Practical applications

### Employee compensation

`DENSE_RANK()` can identify distinct compensation levels within departments.

`ROW_NUMBER()` can select a fixed number of employees.

### Sales analytics

`RANK()` can create competition-style regional leaderboards.

`NTILE(4)` can divide representatives into approximate performance quartiles.

### Customer analytics

`NTILE(10)` can divide customers into deciles according to revenue, spending, or another ordered measure.

### Financial analysis

`DENSE_RANK()` can identify the second-highest distinct transaction amount or valuation.

`RANK()` can preserve ties in ordered financial metrics.

### Data quality and deduplication

`ROW_NUMBER()` can identify the preferred record among multiple records representing the same business entity.

### Sports analytics

`RANK()` naturally represents competition ranking where tied scores share a position.

`ROW_NUMBER()` can provide a deterministic sequence when every record must have a unique position.

## Conceptual checklist

When choosing a ranking window function, ask:

1. Should every row have a unique position?
2. Should equal values share a position?
3. Should gaps appear after ties?
4. Should rank numbers remain consecutive?
5. Is the goal ranking or bucket segmentation?
6. Should ranking restart for each group?
7. What columns define a tie?
8. Is deterministic ordering required?
9. Are exactly N physical rows required?
10. Should ties at the boundary be retained?
11. Is the requirement based on distinct values?
12. Can the operation be performed efficiently on the target dataset?

The answers determine whether `ROW_NUMBER()`, `RANK()`, `DENSE_RANK()`, or `NTILE()` best expresses the intended operation.

## Core syntax reference

`ROW_NUMBER() OVER (ORDER BY expression)`

`ROW_NUMBER() OVER (PARTITION BY group_column ORDER BY expression)`

`RANK() OVER (ORDER BY expression)`

`RANK() OVER (PARTITION BY group_column ORDER BY expression)`

`DENSE_RANK() OVER (ORDER BY expression)`

`DENSE_RANK() OVER (PARTITION BY group_column ORDER BY expression)`

`NTILE(4) OVER (ORDER BY expression)`

`NTILE(4) OVER (PARTITION BY group_column ORDER BY expression)`

These expressions can be assigned aliases such as `row_number`, `rank`, `dense_rank`, or `quartile` and then used by an outer query for filtering or further processing.

## Relationship between the four functions

The four functions can be viewed according to the information they preserve.

`ROW_NUMBER()` preserves physical row identity in the sequence.

`RANK()` preserves competition positions and tie gaps.

`DENSE_RANK()` preserves distinct ordered-value positions without gaps.

`NTILE()` preserves approximate population segmentation rather than competition positions.

That distinction explains why similar-looking analytical requirements can produce substantially different results depending on the selected function.
