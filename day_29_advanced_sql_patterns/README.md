# Advanced SQL Patterns: Top-N, Gaps-and-Islands, Deduplication, and Pivot-Style Analysis

## Topic Scope

Advanced SQL becomes particularly powerful when a problem cannot be solved cleanly with a simple `SELECT`, `WHERE`, `GROUP BY`, or `ORDER BY`.

This study focuses on four important analytical patterns:

1. **Top-N analysis**
   - Global Top-N
   - Top-N per group
   - Top-N with ties
   - `ROW_NUMBER()`
   - `RANK()`
   - `DENSE_RANK()`

2. **Gaps-and-islands analysis**
   - Consecutive records
   - Missing periods
   - Activity streaks
   - Sessionization
   - `LAG()`
   - Cumulative boundary flags

3. **Deduplication**
   - Identifying duplicate business records
   - Selecting the canonical record
   - Keeping the newest record
   - Deterministic tie-breaking
   - Safe deletion strategies

4. **Pivot-style analysis**
   - Conditional aggregation
   - `CASE`
   - Converting row-oriented categories into analytical columns
   - Dynamic pivot SQL
   - Identifier safety

The Python implementation executes real SQL using SQLite. The JavaScript implementation models the same analytical logic using arrays and functions. The C++ implementation develops the patterns into an industry-style retail analytics case study using standard-library data structures.

---

## 1. Why These Patterns Matter

Relational data is normally stored in rows:

| Region | Product | Amount |
|---|---|---:|
| North | Laptop | 1200 |
| North | Phone | 800 |
| South | Laptop | 2200 |

Business questions frequently require a different view:

- Which are the two largest transactions in every region?
- Which customers had activity on consecutive days?
- Which records represent the same employee and which copy should survive?
- How much did each region sell for each product?
- What was the cumulative sales value?
- Where did a customer's activity break into separate sessions?
- Which transactions belong to the top two ranks rather than merely the first two rows?

These questions require SQL techniques that preserve row-level detail while calculating information across related rows.

Window functions are especially important because they allow calculations across a set of related rows without collapsing those rows into a single `GROUP BY` result.

---

# 2. Fundamental Concepts

## 2.1 `GROUP BY` versus Window Functions

A normal aggregation collapses rows.

For example:

`GROUP BY region`

can produce one result per region.

A window function does not normally collapse the underlying rows.

For example:

`ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC)`

can assign a position to every transaction while preserving every transaction.

This distinction is fundamental.

### Aggregation

A grouped query answers:

> What is the total sales amount for each region?

### Window calculation

A window query answers:

> What position does each sale have inside its region?

Both are analytical operations, but they operate at different levels.

---

# 3. Window Function Structure

A typical window expression has this structure:

`FUNCTION(...) OVER (PARTITION BY ... ORDER BY ...)`

The three important components are:

- **Function**: the calculation, such as `ROW_NUMBER()` or `SUM()`
- **PARTITION BY**: defines independent groups
- **ORDER BY**: defines the sequence inside each group

For example:

`ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC)`

means:

1. Split rows by `region`.
2. Sort each region by `amount` descending.
3. Number the rows independently inside every region.

---

# 4. `ROW_NUMBER()`

`ROW_NUMBER()` assigns a unique sequential number to each row in a window.

Suppose a region contains:

| Amount |
|---:|
| 2100 |
| 1500 |
| 1200 |
| 900 |

The result is:

| Amount | Row Number |
|---:|---:|
| 2100 | 1 |
| 1500 | 2 |
| 1200 | 3 |
| 900 | 4 |

A typical expression is:

`ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC)`

## Why a Tie-Breaker Matters

Suppose two transactions both have an amount of `1300`.

If the query only says:

`ORDER BY amount DESC`

the database is not necessarily required to choose a stable order between those tied rows.

When exactly N rows must be returned, use a deterministic secondary key:

`ORDER BY amount DESC, sale_id`

This creates a stable ordering.

---

# 5. `RANK()`

`RANK()` gives tied rows the same rank.

For values:

| Value |
|---:|
| 100 |
| 100 |
| 90 |
| 80 |

the ranks are:

| Value | Rank |
|---:|---:|
| 100 | 1 |
| 100 | 1 |
| 90 | 3 |
| 80 | 4 |

The rank jumps from `1` to `3` because two rows occupied first place.

This is useful when business terminology is explicitly rank-based.

---

# 6. `DENSE_RANK()`

`DENSE_RANK()` also gives tied rows the same rank, but does not leave gaps.

For:

| Value |
|---:|
| 100 |
| 100 |
| 90 |
| 80 |

the dense ranks are:

| Value | Dense Rank |
|---:|---:|
| 100 | 1 |
| 100 | 1 |
| 90 | 2 |
| 80 | 3 |

The distinction is:

| Function | 100 | 100 | 90 | 80 |
|---|---:|---:|---:|---:|
| `ROW_NUMBER()` | 1 | 2 | 3 | 4 |
| `RANK()` | 1 | 1 | 3 | 4 |
| `DENSE_RANK()` | 1 | 1 | 2 | 3 |

---

# 7. Top-N Analysis

A global Top-N query is straightforward:

`ORDER BY amount DESC LIMIT 5`

This returns the five largest rows in the entire result.

The problem becomes more interesting when the requirement is:

> Return the top two sales in every region.

A global `LIMIT 2` is not correct because it limits the entire result set rather than each group.

The standard pattern is:

1. Rank rows inside each group.
2. Put the ranking into a CTE or derived table.
3. Filter the ranking.

Conceptually:

`ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC, sale_id)`

followed by:

`WHERE rn <= 2`

This pattern is one of the most reusable advanced SQL techniques.

---

# 8. Top-N Per Group: Exact Number of Rows

`ROW_NUMBER()` is appropriate when the requirement is:

> Return exactly N rows per group, assuming the group contains at least N rows.

For example:

`ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC, sale_id)`

followed by:

`WHERE row_number <= 2`

returns exactly two rows per region when each region has two or more rows.

The Python implementation demonstrates this against the sales table.

---

# 9. Top-N With Ties

Sometimes the requirement is:

> Return everyone whose rank is within the top two positions.

That is different.

If two employees tie for first place, both should be included.

`RANK()` is appropriate when rank-based ties must be preserved.

The distinction is important:

- `ROW_NUMBER()` answers a row-count question.
- `RANK()` answers a rank question.
- `DENSE_RANK()` answers a dense-rank question.

Do not choose between them merely because they appear similar.

Choose according to the business definition.

---

# 10. `LAG()` and `LEAD()`

`LAG()` accesses a previous row.

`LEAD()` accesses a following row.

For example:

`LAG(amount) OVER (PARTITION BY salesperson ORDER BY sale_date)`

allows a query to compare the current sale with the previous sale.

Similarly:

`LEAD(amount) OVER (PARTITION BY salesperson ORDER BY sale_date)`

looks forward.

These functions are useful for:

- Change detection
- Period-over-period analysis
- Time-series comparisons
- Identifying gaps
- Detecting state transitions
- Calculating previous and next values
- Sessionization

The Python and JavaScript implementations both demonstrate adjacent-row analysis.

---

# 11. Running Totals

A running total can be calculated using a windowed aggregate:

`SUM(amount) OVER (ORDER BY sale_date, sale_id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`

The important distinction is that this is not the same as a normal `GROUP BY`.

A grouped sum produces one row per group.

A running total preserves each transaction while adding cumulative information.

For example:

| Date | Amount | Running Total |
|---|---:|---:|
| Jan 1 | 100 | 100 |
| Jan 2 | 200 | 300 |
| Jan 3 | 150 | 450 |

---

# 12. Window Frames

A window has two related ideas:

- Which rows belong to the partition?
- Which rows within that partition belong to the calculation frame?

A common frame is:

`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`

This explicitly means:

> Start at the first row of the ordered partition and continue through the current row.

Explicit frames are valuable when precise behavior matters.

`ROWS` and `RANGE` are not always interchangeable. `RANGE` can group peer values according to the ordering expression, while `ROWS` operates on physical rows.

When deterministic row-by-row accumulation is required, `ROWS` is often the clearer choice.

---

# 13. Gaps-and-Islands

The gaps-and-islands problem is a general pattern for identifying consecutive groups.

An **island** is a consecutive run.

A **gap** separates one run from another.

Examples include:

- Consecutive login days
- Consecutive dates with sales
- Continuous machine operation
- Consecutive employee attendance
- Streaks of customer activity
- Continuous stock availability
- Consecutive status values

The problem usually has two stages:

1. Detect where a new island starts.
2. Assign an island identifier and aggregate each island.

---

# 14. Detecting Gaps With `LAG()`

Suppose a customer has activity on:

- January 1
- January 2
- January 3
- January 10
- January 11

`LAG(event_date)` produces the previous activity date.

The date differences become approximately:

- First row: no previous date
- January 2: 1 day
- January 3: 1 day
- January 10: 7 days
- January 11: 1 day

The jump from January 3 to January 10 identifies a boundary.

A boundary flag can be created with a `CASE` expression.

Conceptually:

`CASE WHEN previous_date IS NULL OR days_since_previous > 1 THEN 1 ELSE 0 END`

This turns a date sequence into a sequence of island-boundary markers.

---

# 15. Cumulative Island Identifiers

Once a new-island flag exists, a cumulative sum can create an island number.

Conceptually:

`SUM(new_island) OVER (PARTITION BY customer_id ORDER BY event_date ROWS UNBOUNDED PRECEDING)`

If the flags are:

`1, 0, 0, 1, 0`

the cumulative island numbers become:

`1, 1, 1, 2, 2`

The rows can then be grouped by:

`customer_id, island_number`

This produces one result per consecutive island.

---

# 16. The Date Minus Row-Number Technique

Another classic gaps-and-islands method uses:

`date - ROW_NUMBER()`

For consecutive dates, subtracting the row number produces the same derived value.

For example, conceptually:

| Date | Row Number | Derived Key |
|---|---:|---|
| Jan 1 | 1 | Dec 31 |
| Jan 2 | 2 | Dec 31 |
| Jan 3 | 3 | Dec 31 |
| Jan 7 | 4 | Jan 3 |

The first three rows therefore share an island key.

The key requirement is that the date sequence and row numbering use compatible ordering.

---

# 17. Duplicate Dates and Duplicate Events

Gaps-and-islands logic can become incorrect if multiple events occur on the same date and the intended unit is a calendar day.

If the business question is:

> Was the customer active on consecutive calendar days?

then multiple events on the same day may need to be reduced to one day before calculating islands.

If the business question is:

> Were individual events consecutive according to their timestamps?

then each event may need to remain separate.

This distinction should be resolved before choosing the query pattern.

---

# 18. Sessionization

Sessionization is a practical form of gaps-and-islands analysis.

A session starts when the time gap from the previous event exceeds a defined threshold.

For example, a website might define:

- Events within 30 minutes as part of one session.
- More than 30 minutes of inactivity as a new session.

The general algorithm is:

1. Partition events by user.
2. Order events chronologically.
3. Use `LAG()` to obtain the previous event.
4. Calculate the time difference.
5. Mark a new session when the threshold is exceeded.
6. Cumulatively sum the boundary flag.
7. Group by user and session number.

The Python implementation demonstrates this logic with calendar-day gaps. A production system using timestamps would normally calculate differences in minutes or seconds.

---

# 19. Deduplication

Deduplication means identifying records that represent the same logical entity or event and selecting the canonical record.

The first question is not:

> Which SQL statement deletes duplicates?

The first question is:

> What defines a duplicate?

Examples of possible business keys:

- Email address
- Customer ID plus date
- External transaction ID
- Employee ID
- Product SKU
- Source-system record ID

A duplicate rule must be based on business meaning rather than simply identical physical rows.

---

# 20. Finding Duplicate Groups

A basic duplicate search uses:

`GROUP BY business_key HAVING COUNT(*) > 1`

For example:

`GROUP BY email`

with:

`HAVING COUNT(*) > 1`

identifies email values appearing more than once.

This is a discovery query.

It does not yet determine which row should survive.

---

# 21. Deterministic Deduplication

A robust approach is:

1. Partition by the business key.
2. Sort records according to the retention policy.
3. Assign `ROW_NUMBER()`.
4. Keep row number 1.
5. Remove rows with row numbers greater than 1.

For example:

`ROW_NUMBER() OVER (PARTITION BY email ORDER BY updated_at DESC, record_id DESC)`

means:

- Group records by email.
- Prefer the newest record.
- If timestamps tie, prefer the larger record ID.

The second ordering criterion makes the result deterministic.

---

# 22. Why Deterministic Ordering Matters

Consider two duplicate records:

| Email | Updated At | Record ID |
|---|---|---:|
| a@example.com | 2026-03-01 09:00 | 10 |
| a@example.com | 2026-03-01 09:00 | 11 |

If the query orders only by `updated_at`, the two rows are peers.

A deterministic retention policy can instead specify:

`ORDER BY updated_at DESC, record_id DESC`

Record `11` is then clearly preferred.

This is important for:

- Repeatable ETL pipelines
- Data cleanup jobs
- Auditable transformations
- Production migrations
- Testing
- Reproducibility

---

# 23. Safe Deduplication Deletion

Deletion should not begin with a destructive statement.

A safer workflow is:

1. Identify duplicate groups.
2. Display candidate rows.
3. Add `ROW_NUMBER()`.
4. Verify the rows where `rn > 1`.
5. Run the delete inside a transaction.
6. Validate the resulting row count.
7. Commit only after validation.

The Python implementation follows this pattern.

For production data, additional safeguards may include:

- Backup or point-in-time recovery
- Audit logging
- Change approval
- Dry-run mode
- Foreign-key analysis
- Referential-integrity validation
- Application downtime or synchronization controls where necessary

---

# 24. Deduplication Is Not Always Deletion

A duplicate record may contain useful information.

Two records might contain:

- Different addresses
- Different phone numbers
- Different source-system metadata
- Different timestamps
- Different consent states

In such cases, simply deleting all but one record may destroy information.

Possible alternatives include:

- Merge records
- Preserve a history table
- Create a canonical master record
- Maintain source provenance
- Mark obsolete records rather than deleting them

The correct strategy depends on the data model.

---

# 25. Pivot-Style Analysis

A pivot transforms category values into columns.

For example, source data:

| Region | Product | Sales |
|---|---|---:|
| North | Laptop | 3600 |
| North | Phone | 1700 |
| North | Tablet | 600 |

can become:

| Region | Laptop | Phone | Tablet |
|---|---:|---:|---:|
| North | 3600 | 1700 | 600 |

A portable SQL technique is conditional aggregation.

The pattern is:

`SUM(CASE WHEN product = 'Laptop' THEN amount ELSE 0 END)`

The Python implementation executes this pattern directly.

---

# 26. Conditional Aggregation

Conditional aggregation combines:

- `SUM`
- `COUNT`
- `AVG`
- `MIN`
- `MAX`
- `CASE`

For example:

`SUM(CASE WHEN product = 'Laptop' THEN amount ELSE 0 END)`

calculates the sum only for Laptop rows.

A count can use:

`SUM(CASE WHEN product = 'Laptop' THEN 1 ELSE 0 END)`

This is useful even when a database supports a native pivot operation because conditional aggregation is widely portable.

---

# 27. Pivot Versus Normalized Data

A pivot is usually useful for reporting.

It is generally not the ideal storage format for transactional data.

Normalized transactional data is naturally represented as:

`region, product, amount`

A report may present:

`region, laptop_sales, phone_sales, tablet_sales`

The report format should not automatically dictate the underlying storage model.

---

# 28. Dynamic Pivot SQL

Static pivot-style SQL is easy when categories are known:

- Laptop
- Phone
- Tablet

Dynamic categories require generated SQL.

This introduces an important security issue.

SQL values can normally be passed through parameters:

`WHERE region = ?`

SQL identifiers generally cannot be parameterized in the same way.

For example, a generated column name is part of SQL structure rather than a normal data value.

Therefore, dynamic identifiers should come from a strict allow-list or pass identifier validation.

The Python, JavaScript, and C++ implementations demonstrate identifier validation before SQL generation.

---

# 29. SQL Injection Considerations

Do not build value filters by concatenating arbitrary user input.

Unsafe conceptual pattern:

`"SELECT ... WHERE region = '" + userInput + "'"`

The safer approach is parameter binding.

For example:

`WHERE region = ?`

with the region supplied separately as a bound parameter.

Dynamic identifiers are different. They generally require validation or an application-level allow-list.

Security controls therefore need to distinguish:

- SQL values
- SQL identifiers
- SQL keywords
- Generated expressions

---

# 30. Combined Analytical Queries

Real reporting queries often combine multiple advanced techniques.

The Python implementation includes a combined report that calculates:

- Regional totals
- Ranking within regions
- Percentage of regional sales
- Running regional totals

The logical sequence is:

1. Calculate regional totals.
2. Join totals back to transaction rows.
3. Calculate rankings.
4. Calculate running totals.
5. Calculate percentages.
6. Sort the final report.

Common table expressions make this sequence easier to reason about.

---

# 31. Common Table Expressions

A CTE uses:

`WITH name AS (...)`

It creates a named intermediate query result.

CTEs are useful for analytical SQL because complex problems can be broken into logical stages.

For example:

`WITH region_totals AS (...)`

followed by:

`WITH ranked AS (...)`

allows each stage to have a clear purpose.

A CTE does not automatically mean the database materializes the result. Optimization behavior depends on the database engine and query plan.

---

# 32. Python Implementation

The Python script uses the standard-library `sqlite3` module.

This provides a real relational database environment without requiring an external database server.

The script creates:

- `sales`
- `customer_events`
- `employee_records`

The data is deliberately small enough to inspect while still demonstrating realistic analytical requirements.

## Python Demonstrates

The Python implementation includes:

- Basic aggregation
- Global Top-N
- `ROW_NUMBER()`
- `RANK()`
- `DENSE_RANK()`
- `LAG()`
- `LEAD()`
- Running totals
- Top-N per group
- Top-N with ties
- Gaps-and-islands
- Sessionization
- Duplicate detection
- Transaction-safe deduplication
- Pivot-style conditional aggregation
- Dynamic pivot SQL generation
- Parameterized queries
- Query plans
- Indexes
- Validation tests

Because the SQL is executed against SQLite, these examples demonstrate actual SQL behavior rather than merely presenting query strings.

---

# 33. Python Database Design

The `sales` table contains:

- `sale_id`
- `customer_id`
- `salesperson`
- `region`
- `product`
- `sale_date`
- `amount`

The `customer_events` table contains:

- `event_id`
- `customer_id`
- `event_date`
- `event_type`
- `session_gap_min`
- `event_value`

The `employee_records` table contains duplicate logical employee records so that the deduplication algorithm has meaningful input.

---

# 34. Python Deduplication Transaction

The deduplication implementation explicitly starts a transaction.

The intended sequence is:

1. Record the initial row count.
2. Begin the transaction.
3. Delete records ranked after the canonical row.
4. Validate the row count.
5. Commit.
6. Roll back if an exception occurs.

This illustrates an important production principle:

> A data-cleaning operation should have explicit validation and failure handling.

A production system may require additional controls, but the transactional structure is an important foundation.

---

# 35. JavaScript Implementation

The JavaScript implementation intentionally does not simply repeat the Python program.

It models the relational operations with arrays and JavaScript functions.

This demonstrates the underlying algorithms independently of a database engine.

Important functions include:

- `groupBy`
- `rankWithinGroups`
- `addRankAndDenseRank`
- `topNPerGroup`
- `topNWithTies`
- `addLagAndLead`
- `addRunningTotal`
- `consecutiveDateIslands`
- `sessionize`
- `findDuplicates`
- `deduplicateKeepNewest`
- `pivotSales`
- `buildDynamicPivotSQL`

This separation makes it easier to understand what a database window function is doing conceptually.

---

# 36. JavaScript Ranking

The JavaScript ranking implementation first partitions rows by a grouping key.

For each group it:

1. Sorts by descending measure.
2. Applies a deterministic ID tie-breaker.
3. Assigns sequential row numbers.

A second implementation calculates both rank and dense rank.

This demonstrates that SQL window functions are declarative expressions of common data-processing algorithms.

The database engine can execute these operations using optimized query-processing mechanisms, while the JavaScript implementation exposes the algorithm directly.

---

# 37. JavaScript Gaps-and-Islands

The JavaScript implementation uses a state-machine style approach.

For every customer's sorted events:

1. Inspect the previous event.
2. Calculate the date gap.
3. Decide whether a new island starts.
4. Extend the current island or create a new one.

This is conceptually equivalent to a SQL implementation based on `LAG()` plus a cumulative boundary calculation.

The distinction between the JavaScript algorithm and SQL syntax is useful:

- JavaScript expresses the state transition procedurally.
- SQL expresses the relationship declaratively.

---

# 38. JavaScript Dynamic Pivot

The JavaScript file generates pivot-style SQL.

It separately handles:

- SQL literals
- SQL identifiers

This distinction matters because a product value such as `Laptop` is data, while a generated alias such as `laptop_sales` becomes part of SQL syntax.

The implementation rejects unsafe identifiers that contain unexpected characters.

This is an example of defensive SQL generation.

---

# 39. C++ Case Study

The C++ program models a retail analytics service.

The system receives:

- Sales transactions
- Customer activity events
- Employee records

It must produce:

- Regional Top-N results
- Tie-aware rankings
- Activity islands
- Customer sessions
- A canonical employee master
- Product-by-region pivot analysis
- A combined management report

The implementation uses only the C++17 standard library.

---

# 40. C++ Data Structures

The case study defines:

- `Sale`
- `Event`
- `EmployeeRecord`
- `RankedSale`
- `Session`
- `Island`
- `PivotRow`
- `RegionalReportRow`

These structures represent domain entities rather than generic arrays.

This makes the analytical transformations explicit.

---

# 41. C++ Top-N Architecture

The ranking process is:

1. Partition sales by region using `std::map`.
2. Sort each partition.
3. Calculate row number.
4. Calculate rank.
5. Calculate dense rank.
6. Filter according to the requested Top-N rule.

This corresponds closely to:

`PARTITION BY region ORDER BY amount DESC, sale_id`

The secondary ordering by `sale_id` guarantees deterministic row numbering.

---

# 42. C++ Gaps-and-Islands Architecture

The C++ island algorithm:

1. Partitions events by customer.
2. Sorts events chronologically.
3. Calculates the date gap.
4. Starts a new island when the gap exceeds one day.
5. Aggregates island start date, end date, and event count.

The implementation includes date conversion functions rather than relying on an external date library.

This keeps the program self-contained.

---

# 43. C++ Sessionization

Sessionization uses the same boundary principle as gaps-and-islands.

A new session is created when:

`daysBetween(previousEvent, currentEvent) > maximumGapDays`

A production event-processing system would generally use timestamp-level resolution such as seconds or minutes.

The case study intentionally keeps the model readable while demonstrating the essential boundary logic.

---

# 44. C++ Deduplication

The C++ implementation groups employee records by email.

Each group is sorted by:

1. `updatedAt` descending
2. `recordId` descending

The first row becomes the canonical row.

This corresponds to a SQL query using:

`ROW_NUMBER() OVER (PARTITION BY email ORDER BY updated_at DESC, record_id DESC)`

followed by a filter for `rn = 1`.

---

# 45. C++ Pivot-Style Analysis

The C++ pivot implementation creates one `PivotRow` per region.

Each sale updates one of:

- `laptop`
- `phone`
- `tablet`
- `total`

This models SQL conditional aggregation.

The implementation also generates SQL dynamically to show how an application might construct a pivot query when categories are configured at runtime.

---

# 46. C++ Combined Report

The final management report combines:

- Ranking
- Regional totals
- Percentage of regional sales
- Running totals

The algorithm first calculates totals, then sorts rows for ranking, and separately orders them chronologically for cumulative calculations.

This demonstrates an important analytical concept:

> Different calculations may require different orderings over the same data.

Ranking might require:

`amount DESC`

while a running total might require:

`date ASC`

These should not be conflated.

---

# 47. Edge Cases

Advanced analytical SQL should explicitly consider edge cases.

Important examples include:

## Empty Groups

A group may contain zero rows after filtering.

Queries should not assume that every category has data.

## Fewer Than N Rows

Top-N per group should naturally return fewer than N rows when a group contains fewer than N records.

## Ties

Ties determine whether `ROW_NUMBER()`, `RANK()`, or `DENSE_RANK()` is appropriate.

## NULL Values

Ordering behavior for `NULL` differs between database systems.

If NULL placement matters, specify it explicitly where the SQL dialect supports it, or use an expression such as:

`ORDER BY amount IS NULL, amount DESC`

## Duplicate Dates

Multiple events on the same date may or may not represent multiple activity days depending on the business definition.

## Equal Timestamps

A deterministic secondary ordering column may be necessary.

## Empty Pivot Categories

A pivot report may need to display a zero for categories with no transactions.

## New Categories

A static pivot must be updated when new categories appear.

Dynamic pivoting can address this but introduces SQL-generation complexity.

---

# 48. Common Mistakes

## Mistake 1: Using Global `LIMIT` for Top-N Per Group

`LIMIT 5` limits the entire result.

It does not mean five rows per region.

Use a window function and filter its result instead.

## Mistake 2: Using `ROW_NUMBER()` When Ties Must Be Preserved

`ROW_NUMBER()` always creates unique positions.

Use `RANK()` when tied rows should share a rank.

## Mistake 3: Omitting a Deterministic Tie-Breaker

Ordering only by a non-unique value can make row selection ambiguous.

Add a stable unique key when exact row selection matters.

## Mistake 4: Deleting Duplicates Before Inspecting Them

First identify the canonical and non-canonical rows.

Then validate the deletion set.

## Mistake 5: Defining Duplicates Only by Physical Equality

Two records can differ physically while representing the same logical entity.

Define the business key.

## Mistake 6: Ignoring Time Granularity

A session threshold measured in minutes cannot be modeled accurately by whole-day comparisons.

Use the appropriate timestamp precision.

## Mistake 7: Generating Dynamic SQL Without Identifier Validation

Dynamic identifiers are part of SQL structure.

They require allow-list validation or strict syntax validation.

## Mistake 8: Confusing Report Format With Storage Format

A pivoted report is not necessarily an appropriate transactional schema.

---

# 49. Limitations

The examples are deliberately self-contained and educational.

The Python implementation uses SQLite, which means some syntax and optimizer behavior differs from systems such as:

- PostgreSQL
- MySQL
- SQL Server
- Oracle
- Snowflake
- BigQuery

Window-function concepts are broadly transferable, but exact syntax can differ.

The JavaScript implementation models database behavior with in-memory arrays. It therefore does not reproduce a database optimizer, disk-backed storage, indexing internals, transaction isolation, or distributed query execution.

The C++ implementation models the algorithms directly rather than connecting to a production database.

---

# 50. Performance Considerations

Advanced analytical queries can be expensive because ranking and ordered window calculations often require sorting.

For a dataset of `n` rows, a straightforward sorting-based implementation commonly has approximately:

`O(n log n)`

time complexity.

The exact cost depends on:

- Database engine
- Existing indexes
- Cardinality
- Partition size
- Query plan
- Memory available for sorting
- Data distribution
- Predicate selectivity
- Parallel execution

---

# 51. Indexing

Indexes can improve filtering and ordering.

For Top-N analysis, useful indexes may align with:

- Partition columns
- Ordering columns
- Deterministic tie-breakers

For example, a conceptual index might align with:

`(region, amount DESC, sale_id)`

For gaps-and-islands queries, an index aligned with:

`(customer_id, event_date, event_id)`

can help retrieve customer events in chronological order.

Indexes have costs:

- Additional disk space
- More expensive inserts
- More expensive updates
- More expensive deletes
- Maintenance overhead

Indexes should therefore be chosen according to actual workload and query plans.

---

# 52. Query Plans

The Python implementation uses `EXPLAIN QUERY PLAN`.

Query plans help answer questions such as:

- Is an index being used?
- Is a table being scanned?
- Is sorting required?
- Which access path did the optimizer select?

An index existing in the schema does not guarantee that it will be used.

The optimizer chooses an execution strategy based on statistics, selectivity, available indexes, query structure, and database-specific rules.

---

# 53. Security Considerations

The most important security rule for application-generated SQL is to separate SQL structure from user-controlled values.

For normal values:

- Use parameterized queries.
- Do not concatenate arbitrary user input into SQL.

For dynamic identifiers:

- Use a strict allow-list.
- Validate identifier syntax.
- Avoid allowing arbitrary table or column names.

For destructive deduplication:

- Use transactions.
- Validate the target rows.
- Maintain appropriate backup and recovery controls.
- Preserve auditability where required.

For sensitive datasets, access controls and data governance are as important as query correctness.

---

# 54. Implementation Considerations

A production implementation should define the business semantics before writing the analytical query.

For Top-N:

- Is N based on rows or ranks?
- Should ties be included?
- Is the result deterministic?

For gaps-and-islands:

- What constitutes consecutive?
- Is the unit a date, hour, minute, or second?
- Are duplicate timestamps separate events?

For deduplication:

- What defines a duplicate?
- Which record wins?
- Should records be deleted, merged, or marked inactive?

For pivot analysis:

- Are categories fixed?
- Can categories change?
- Is a wide report actually required?

These decisions determine the correct SQL pattern.

---

# 55. Practical Applications

## Sales Analytics

Top-N per region can identify the highest-value transactions or products.

## Customer Analytics

Gaps-and-islands can identify:

- Activity streaks
- Retention periods
- Dormant periods
- Sessions
- Re-engagement events

## Data Engineering

Deduplication is common during:

- ETL
- Data migration
- Master-data processing
- Source-system reconciliation
- Batch ingestion

## Financial Reporting

Pivot-style aggregation can present:

- Revenue by product
- Expenses by department
- Monthly totals
- Regional performance

## Operations

Gaps-and-islands can detect:

- Machine uptime
- Service outages
- Inventory availability
- Employee attendance

## Monitoring

Sessionization and gap detection can identify:

- User sessions
- Incident periods
- Continuous service failures
- Bursts of activity

---

# 56. Important Distinctions

| Requirement | Appropriate Pattern |
|---|---|
| Exactly N rows per group | `ROW_NUMBER()` |
| Top N ranks including ties | `RANK()` |
| Dense ranking without gaps | `DENSE_RANK()` |
| Previous row | `LAG()` |
| Next row | `LEAD()` |
| Running total | Windowed `SUM()` |
| Consecutive sequences | Gaps-and-islands |
| Time-based sessions | Sessionization |
| Find duplicate groups | `GROUP BY ... HAVING COUNT(*) > 1` |
| Keep one duplicate record | `ROW_NUMBER()` with retention ordering |
| Report categories as columns | Conditional aggregation |
| Runtime-defined pivot columns | Dynamic SQL with identifier validation |

---

# 57. Relationship Between the Three Implementations

## Python

Python demonstrates the actual execution of SQL.

Its primary purpose is to show how a relational database expresses these patterns using:

- SQL window functions
- CTEs
- Aggregation
- Transactions
- Indexes
- Query plans

## JavaScript

JavaScript demonstrates the algorithmic meaning of the SQL.

Its array-based implementation exposes:

- Partitioning
- Sorting
- Ranking
- State transitions
- Duplicate grouping
- Conditional aggregation

This is useful when building application-side data processing or when trying to understand what a declarative SQL expression represents operationally.

## C++

C++ develops the ideas into a larger technical case study.

Its focus is:

- Explicit domain modeling
- Data structures
- Algorithms
- Deterministic ordering
- Error handling
- Complexity
- Modular architecture
- Production-oriented design decisions

---

# 58. Conceptual Model

The four main patterns can be viewed as transformations.

### Top-N

`Rows -> Partition -> Order -> Rank -> Filter`

### Gaps-and-Islands

`Rows -> Partition -> Order -> Compare Adjacent Rows -> Mark Boundaries -> Group Islands`

### Deduplication

`Rows -> Define Business Key -> Partition -> Order by Retention Rule -> Keep Canonical Row`

### Pivot-Style Analysis

`Rows -> Group -> Evaluate Category Conditions -> Aggregate -> Produce Wide Report`

Recognizing these transformations makes it easier to design advanced queries rather than memorizing individual SQL statements.

---

# 59. Recommended Query Design Sequence

For a complex analytical problem, a reliable design process is:

1. Define the business question.
2. Identify the required grain of the result.
3. Define the grouping or partitioning key.
4. Define the ordering rule.
5. Determine whether ties matter.
6. Identify required adjacent-row relationships.
7. Define boundary conditions if sequences are involved.
8. Define the canonical record if deduplication is involved.
9. Define output categories if pivoting is involved.
10. Build intermediate CTEs.
11. Validate intermediate results.
12. Check edge cases.
13. Inspect the query plan.
14. Add or adjust indexes based on evidence.
15. Validate production-scale performance.

This approach is generally safer than trying to write the entire analytical query in one expression.

---

# 60. Files in This Study

The four deliverables represent the same subject at different levels:

- The Python script provides executable SQL demonstrations.
- The JavaScript file provides application-side algorithmic equivalents.
- The C++ program provides a detailed technical case study.
- This README provides the conceptual and implementation context connecting the three.

The implementations deliberately use deterministic ordering, explicit validation, edge-case handling, and production-oriented safeguards because these details often determine whether an analytical query is merely syntactically valid or actually reliable in practice.
