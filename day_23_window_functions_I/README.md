# Window Functions I | OVER, PARTITION BY, ORDER BY

## Topic introduction

SQL window functions perform calculations across a related set of rows while preserving the individual rows in the result.

They are particularly useful when a query needs both:

- the original row;
- information about other rows related to that row.

For example, an employee report may need to display each employee's salary together with:

- the average salary of the employee's department;
- the employee's position within that department;
- the highest salary in the department;
- the difference from the previous employee's salary;
- a cumulative departmental value.

A conventional `GROUP BY` query is often not sufficient because `GROUP BY` normally reduces multiple input rows into fewer output rows.

A window function provides a different model:

`function(...) OVER (...)`

The function calculates a value over a window of related rows, while the current row remains in the result.

The central syntax studied in this module is:

`function(...) OVER (PARTITION BY ... ORDER BY ...)`

The three components have different responsibilities:

- `function(...)` specifies what is calculated.
- `PARTITION BY` defines which rows belong to the same logical group.
- `ORDER BY` inside `OVER()` defines the sequence used by order-sensitive window calculations.

The Python implementation uses SQLite so that the SQL queries are executable without an external database server. The JavaScript implementation models the same mechanics explicitly with arrays and functions. The C++ implementation develops an industry-style regional sales analytics engine using standard-library data structures and algorithms.

---

## Fundamental distinction: GROUP BY versus window functions

Consider a table containing employees:

| employee | department | salary |
| --- | --- | ---: |
| Diya | Engineering | 110000 |
| Kabir | Engineering | 110000 |
| Meera | Engineering | 82000 |
| Anaya | Sales | 105000 |

A grouped query such as:

`SELECT department, AVG(salary) FROM employees GROUP BY department`

returns one row per department.

The employee rows themselves are no longer individually represented.

A window expression such as:

`AVG(salary) OVER (PARTITION BY department)`

calculates the department average while preserving every employee row.

The distinction is fundamental:

| Feature | `GROUP BY` | Window function |
| --- | --- | --- |
| Reduces rows | Yes | No |
| Keeps individual rows | Usually no | Yes |
| Calculates group-level statistics | Yes | Yes |
| Supports row-relative calculations | No | Yes |
| Supports `LAG` and `LEAD` | No | Yes |
| Supports ranking | No | Yes |
| Supports running calculations | Not directly | Yes |
| Uses `OVER()` | No | Yes |

A useful mental model is:

`GROUP BY` answers questions about groups.

Window functions answer questions about a row in relation to a group or ordered sequence.

---

## The `OVER()` clause

The `OVER()` clause tells SQL that an expression is a window function.

The simplest form is:

`COUNT(*) OVER ()`

With no `PARTITION BY` and no window `ORDER BY`, the window normally covers the complete result set.

The Python implementation demonstrates:

`COUNT(*) OVER ()`

and:

`AVG(salary) OVER ()`

Each employee receives the same company-wide count and average because every employee belongs to the same unpartitioned window.

This differs from:

`SELECT COUNT(*) FROM employees`

because the latter returns a single result row, while `COUNT(*) OVER ()` attaches the count to every employee row.

---

## `PARTITION BY`

`PARTITION BY` divides the rows into independent logical windows.

For example:

`AVG(salary) OVER (PARTITION BY department_id)`

means:

1. group the rows conceptually by department;
2. calculate the average separately inside each department;
3. attach that department average to every employee in that department.

A partition is not the same thing as a physical database table or a permanent group.

It is a logical calculation boundary created for the window expression.

If a table contains four departments, the expression can create four independent logical windows.

For example:

`COUNT(*) OVER (PARTITION BY department_id)`

can produce:

| Employee | Department | Department employee count |
| --- | --- | ---: |
| Diya | Engineering | 4 |
| Kabir | Engineering | 4 |
| Anaya | Sales | 4 |
| Vihaan | Sales | 4 |
| Arjun | Finance | 3 |
| Sara | Finance | 3 |

The rows remain individual rows.

---

## Multiple partitioning columns

`PARTITION BY` can contain more than one column.

For example:

`PARTITION BY region, product`

creates a separate logical partition for every unique combination of region and product.

Suppose the data contains:

| Region | Product |
| --- | --- |
| North | Laptop |
| North | Phone |
| North | Laptop |
| West | Laptop |
| West | Phone |

The partitions are conceptually:

- North + Laptop
- North + Phone
- West + Laptop
- West + Phone

The Python program demonstrates this with regional product revenue.

The same technique is useful for:

- customer and month;
- country and product;
- department and job title;
- account and transaction type;
- region and sales channel.

---

## `ORDER BY` inside `OVER()`

`ORDER BY` inside a window defines the logical sequence used by the window calculation.

For example:

`ROW_NUMBER() OVER (ORDER BY salary DESC)`

assigns positions according to descending salary.

With partitioning:

`ROW_NUMBER() OVER (PARTITION BY department_id ORDER BY salary DESC)`

assigns a separate salary sequence inside each department.

The `ORDER BY` inside `OVER()` is different from the final query `ORDER BY`.

For example:

`ROW_NUMBER() OVER (ORDER BY salary DESC)`

can calculate a salary ranking while the final query uses:

`ORDER BY employee_name`

to display employees alphabetically.

The analytical order and presentation order are therefore independent.

This distinction is one of the most important concepts in window-function SQL.

---

## Deterministic ordering

A window ordering should be carefully designed when the order matters.

Suppose two employees both have a salary of `110000`.

This expression:

`ROW_NUMBER() OVER (ORDER BY salary DESC)`

does not establish which tied employee should receive row number 1 and which should receive row number 2.

A deterministic version can use a unique tiebreaker:

`ROW_NUMBER() OVER (ORDER BY salary DESC, employee_id)`

The salary is the business ordering criterion.

The employee ID is a deterministic secondary ordering criterion.

This is particularly important for:

- pagination;
- de-duplication;
- top-N selection;
- audit reports;
- reproducible data processing;
- incremental pipelines.

The Python, JavaScript, and C++ implementations deliberately use unique IDs as tiebreakers where a unique sequence is required.

---

## Ranking functions

Three important ranking functions are:

- `ROW_NUMBER()`
- `RANK()`
- `DENSE_RANK()`

They are similar but have different behavior when ties exist.

Suppose salaries are:

`110000, 110000, 95000, 82000`

### `ROW_NUMBER()`

The result is:

`1, 2, 3, 4`

Every row receives a unique number.

Tied values do not share a number.

### `RANK()`

The result is:

`1, 1, 3, 4`

The two employees tied at the highest salary both receive rank 1.

The next employee receives rank 3 because two rows occupy the first rank.

### `DENSE_RANK()`

The result is:

`1, 1, 2, 3`

The two tied employees receive rank 1.

The next distinct salary receives rank 2.

No rank is skipped.

The distinction can be represented as:

| Salary | `ROW_NUMBER` | `RANK` | `DENSE_RANK` |
| ---: | ---: | ---: | ---: |
| 110000 | 1 | 1 | 1 |
| 110000 | 2 | 1 | 1 |
| 95000 | 3 | 3 | 2 |
| 82000 | 4 | 4 | 3 |

The correct function depends on the business meaning of "position."

---

## Choosing a ranking function

Use `ROW_NUMBER()` when every row needs a unique sequence.

Typical applications include:

- selecting exactly one row from each duplicate group;
- pagination;
- deterministic ordering;
- selecting exactly N rows from each group.

Use `RANK()` when tied values should share a position and gaps after ties are meaningful.

Use `DENSE_RANK()` when tied values should share a position but the ranking sequence should not contain gaps.

The choice should be based on the required semantics rather than convenience.

---

## Aggregate window functions

Many aggregate functions can operate as window functions.

Common examples include:

- `SUM()`
- `AVG()`
- `COUNT()`
- `MIN()`
- `MAX()`

For example:

`SUM(revenue) OVER (PARTITION BY region)`

calculates total regional revenue while retaining every sale.

Similarly:

`AVG(salary) OVER (PARTITION BY department_id)`

calculates the average salary of the employee's department while preserving each employee row.

This makes window aggregates useful for comparative analysis.

A row can contain both:

`salary`

and:

`AVG(salary) OVER (PARTITION BY department_id)`

allowing the query to calculate:

`salary - department_average`

without first collapsing the department.

The Python implementation demonstrates this comparison directly.

---

## Percentage of a partition

A common analytical pattern is calculating the percentage contribution of a row to its partition.

For example:

`revenue / SUM(revenue) OVER (PARTITION BY region) * 100`

produces the percentage of regional revenue represented by the current sale.

The Python and JavaScript implementations demonstrate this pattern.

Conceptually:

| Sale | Region revenue | Regional total | Contribution |
| --- | ---: | ---: | ---: |
| Sale A | 2500 | 11000 | 22.73% |
| Sale B | 1800 | 11000 | 16.36% |

The important feature is that the total remains available on every row.

---

## `LAG()`

`LAG()` accesses an earlier row in the ordered window.

Basic syntax:

`LAG(expression) OVER (ORDER BY ...)`

For partitioned data:

`LAG(revenue) OVER (PARTITION BY region ORDER BY sale_date, sale_id)`

The current sale can therefore be compared with the previous sale in the same region.

Typical applications include:

- previous-period revenue;
- previous transaction value;
- change from the previous event;
- trend detection;
- detecting changes in status;
- identifying gaps.

The first row in each partition has no previous row, so `LAG()` normally returns `NULL` unless a default value is supplied.

---

## `LEAD()`

`LEAD()` is the opposite conceptual direction.

It accesses a later row in the ordered window.

For example:

`LEAD(revenue) OVER (PARTITION BY region ORDER BY sale_date, sale_id)`

can show the revenue of the next sale.

The last row in a partition normally has no next row, so its `LEAD()` result is `NULL`.

`LAG()` and `LEAD()` are particularly useful for sequential data.

---

## Running totals

A running total is a cumulative calculation.

A common pattern is:

`SUM(revenue) OVER (PARTITION BY region ORDER BY sale_date, sale_id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`

The calculation starts at the first row of the partition and ends at the current row.

For example:

| Revenue | Running total |
| ---: | ---: |
| 1000 | 1000 |
| 1500 | 2500 |
| 700 | 3200 |
| 2000 | 5200 |

The C++ case study explicitly implements this sequence.

Running totals are common in:

- financial reporting;
- cumulative sales;
- inventory movement;
- account balances;
- cumulative production;
- operational dashboards.

---

## Window frames

A window frame specifies the subset of the ordered partition used for a particular row.

A common frame is:

`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`

This means:

- begin at the first row of the partition;
- end at the current row.

Another example is:

`ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`

This represents the current row and the two preceding physical rows.

The Python and JavaScript implementations use this idea for a three-row moving average.

A critical distinction is that `ROWS` refers to physical rows in the window ordering.

A three-row frame is not automatically the same as a three-day frame.

If the data has missing dates, multiple rows per date, or irregular timestamps, the two concepts can produce different results.

---

## `FIRST_VALUE()`

`FIRST_VALUE()` returns the value from the first row of the window frame.

For example:

`FIRST_VALUE(employee_name) OVER (PARTITION BY department_id ORDER BY salary DESC)`

can identify the first employee in salary order within each department.

This is useful for identifying:

- highest-ranked records;
- earliest events;
- first transaction;
- initial state;
- first observed value.

The meaning depends on the window ordering and frame.

---

## `LAST_VALUE()` and the frame problem

`LAST_VALUE()` is a frequent source of mistakes.

Consider:

`LAST_VALUE(employee_name) OVER (PARTITION BY department_id ORDER BY salary DESC)`

The result depends on the window frame.

If the frame ends at the current row, the current row may itself be the frame's last row.

That can make `LAST_VALUE()` appear to return the current employee rather than the last employee of the complete partition.

When the intention is to examine the final row of the complete ordered partition, an explicit frame can be used:

`ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`

The Python implementation deliberately compares the default behavior with an explicit complete-partition frame.

This is an important example of why understanding window frames matters.

---

## `NTILE()`

`NTILE(n)` distributes ordered rows into approximately equal buckets.

For example:

`NTILE(4) OVER (ORDER BY salary DESC)`

creates four ordered groups.

These are often called quartiles when there are four buckets.

Similarly:

`NTILE(10)`

can divide data into ten buckets often described as deciles.

`NTILE()` does not necessarily produce exactly equal row counts when the total number of rows cannot be evenly divided.

It is useful for:

- segmentation;
- salary bands;
- customer groups;
- analytical cohorts;
- approximate percentile-style grouping.

The Python and JavaScript implementations demonstrate four-bucket segmentation.

---

## `PERCENT_RANK()`

`PERCENT_RANK()` expresses a row's relative ranking between 0 and 1.

Its general behavior is based on rank rather than simply assigning an integer position.

The Python implementation demonstrates:

`PERCENT_RANK() OVER (ORDER BY salary)`

The value is useful when an integer rank is not enough and a relative position is more meaningful.

Interpretation should account for ties because ranking functions and distribution functions have specific tie semantics.

---

## `CUME_DIST()`

`CUME_DIST()` represents the cumulative distribution position.

It answers a question similar to:

"At what cumulative point does this row occur in the ordered population?"

It is different from `PERCENT_RANK()`.

The Python implementation calculates both functions side by side so their behavior can be compared.

---

## Conditional window logic

Window expressions can be combined with conditional expressions.

For example:

`SUM(CASE WHEN salary >= 100000 THEN salary ELSE 0 END) OVER (PARTITION BY department_id)`

calculates the total salary contributed by employees meeting the condition.

Conditional window calculations are useful for:

- category-specific totals;
- conditional counts;
- threshold analysis;
- compliance reporting;
- segmentation;
- business-rule calculations.

Where supported by the database engine, `FILTER` can provide another way to express conditional aggregation.

The Python implementation demonstrates both `CASE` and `FILTER`.

---

## The `FILTER` clause

A database engine that supports aggregate `FILTER` can use expressions such as:

`COUNT(*) FILTER (WHERE salary >= 100000) OVER (PARTITION BY department_id)`

This counts only rows meeting the condition while preserving all result rows.

The distinction is useful when the query needs several conditional measures at once.

For example, an employee report could show:

- total employees;
- high earners;
- low earners;
- average salary;

while still returning one row per employee.

Database support for specific window-function syntax can differ, so SQL should always be checked against the target database engine.

---

## Named window definitions

When multiple window functions use exactly the same partitioning and ordering, a named window can reduce repetition.

For example:

`WINDOW department_window AS (PARTITION BY department_id ORDER BY salary DESC, employee_id)`

can then be referenced by:

`ROW_NUMBER() OVER department_window`

and:

`RANK() OVER department_window`

and:

`DENSE_RANK() OVER department_window`

The Python implementation demonstrates this form.

Named windows improve readability when a query contains many related calculations.

---

## Window functions and `WHERE`

A common mistake is attempting to write:

`WHERE ROW_NUMBER() OVER (...) <= 2`

at the same query level.

Window calculations are not normally available to `WHERE` at that level.

The standard pattern is to calculate the window value in an inner query, common table expression, or derived table and filter it outside.

For example, the Python implementation uses a structure equivalent to:

`SELECT ... FROM (SELECT ..., ROW_NUMBER() OVER (...) AS salary_rank FROM employees) WHERE salary_rank <= 2`

This is the standard top-N-per-group pattern.

---

## Top-N per group

A common analytical requirement is:

"Return the top two employees from every department."

A window function solves this cleanly:

1. partition by department;
2. order by salary;
3. assign a row number;
4. filter the resulting row number.

Conceptually:

`ROW_NUMBER() OVER (PARTITION BY department_id ORDER BY salary DESC, employee_id)`

creates a sequence inside each department.

An outer query then selects rows where the sequence is less than or equal to 2.

The Python implementation executes this against the employee dataset.

The JavaScript implementation provides the same analytical operation through the `topNPerGroup()` function.

The C++ case study applies the pattern to regional sales.

---

## De-duplication with `ROW_NUMBER()`

A common data-processing pattern is:

`ROW_NUMBER() OVER (PARTITION BY business_key ORDER BY preferred_record DESC)`

The resulting row number can identify which record should be retained.

For example, if multiple records represent the same logical customer and one record has the most recent timestamp, the latest record can receive row number 1.

The outer query can then keep only row number 1.

The ordering must reflect the actual business rule.

Using an arbitrary ordering can produce an incorrect record-selection result.

The Python implementation demonstrates the structure using employee department and salary as an intentionally simple analytical key.

---

## `CASE` expressions and windows

A window expression can be combined with `CASE` to classify results.

For example:

`CASE WHEN salary > department_average THEN 'Above average' WHEN salary < department_average THEN 'Below average' ELSE 'At average' END`

can be applied after calculating the department average.

The production-style Python report demonstrates this pattern.

This is useful because analytical queries often have two stages:

1. calculate a metric;
2. classify the current row based on that metric.

Common classifications include:

- above or below benchmark;
- positive or negative change;
- first or later occurrence;
- high, medium, or low segment.

---

## Common edge cases

### Empty partitions

If a query produces no rows for a partition, no window result exists for that partition.

An application should not assume that every possible partition key has data.

### Single-row partitions

A single-row partition has no previous or next row.

Therefore:

- `LAG()` returns `NULL`;
- `LEAD()` returns `NULL`;
- a running total equals the current value;
- the row normally receives rank 1.

### Ties

Ties must be handled deliberately.

Choose among:

- `ROW_NUMBER()`;
- `RANK()`;
- `DENSE_RANK()`.

Do not assume that all three functions have equivalent semantics.

### Duplicate ordering values

If an order is not unique, functions such as `ROW_NUMBER()` may not produce a business-deterministic sequence unless a unique tiebreaker is added.

### NULL values

NULL ordering and NULL treatment should be understood for the specific database engine.

When a business requirement depends on NULL placement, make the rule explicit rather than relying on default behavior.

The Python implementation demonstrates explicit NULL placement using a `CASE` expression.

---

## The two `ORDER BY` concepts

SQL queries can contain both:

`ORDER BY` inside `OVER()`

and:

`ORDER BY` at the end of the query.

They have different jobs.

The window ordering determines the sequence used for the analytical calculation.

The final query ordering determines how the resulting rows are presented.

For example:

`ROW_NUMBER() OVER (PARTITION BY department_id ORDER BY salary DESC)`

can calculate salary position.

The final:

`ORDER BY employee_name`

can then display the results alphabetically.

Changing the final display order does not necessarily change the already-defined analytical sequence.

---

## Python implementation

The Python script uses the standard-library `sqlite3` module.

This provides a useful teaching environment because the program can:

- create an in-memory database;
- create tables;
- insert data;
- create indexes;
- execute real SQL;
- print query results;
- inspect query plans;
- execute assertions.

No external Python package is required.

The database schema contains:

- `departments`;
- `employees`;
- `sales`.

The employee data is intentionally designed with salary ties.

For example, Engineering contains two employees with a salary of `110000`, while Sales also contains a pair of employees with the same salary.

This makes the differences between `ROW_NUMBER`, `RANK`, and `DENSE_RANK` visible.

The sales data contains:

- dates;
- regions;
- products;
- quantities;
- prices;
- calculated revenue.

The Python program demonstrates:

- ordinary `GROUP BY`;
- `OVER()`;
- `PARTITION BY`;
- `ORDER BY`;
- ranking functions;
- `FIRST_VALUE`;
- `LAST_VALUE`;
- `LAG`;
- `LEAD`;
- running totals;
- moving windows;
- `NTILE`;
- `PERCENT_RANK`;
- `CUME_DIST`;
- multiple partition columns;
- conditional window expressions;
- `FILTER`;
- named windows;
- top-N per group;
- de-duplication patterns;
- common table expressions;
- NULL ordering;
- deterministic ordering;
- query-plan inspection;
- validation;
- assertions.

The Python implementation therefore demonstrates actual SQL semantics rather than merely reproducing SQL terminology in ordinary Python.

---

## JavaScript implementation

JavaScript does not provide SQL's `OVER`, `PARTITION BY`, and `ORDER BY` syntax for ordinary arrays.

The JavaScript file therefore implements the underlying mechanics directly.

The central helper is `applyWindow()`.

It models the conceptual stages of a window calculation:

1. partition rows;
2. sort each partition;
3. process each row in its ordered position;
4. calculate an analytical value;
5. preserve the original row.

This makes the mechanics visible without hiding them behind a database engine.

The implementation demonstrates:

- partitioning with `Map`;
- ordered partitions;
- `ROW_NUMBER`;
- `RANK`;
- `DENSE_RANK`;
- `LAG`;
- `LEAD`;
- running totals;
- moving averages;
- first and last values;
- `NTILE`;
- percentage of partition total;
- conditional calculations;
- NULL handling;
- deterministic tiebreaking;
- top-N per group;
- validation;
- testing;
- a sales analytics case study;
- a basic performance benchmark.

The JavaScript implementation is particularly useful for understanding the algorithmic structure behind a window operation.

For example, `PARTITION BY region` becomes a map from region to arrays of rows.

`ORDER BY date, id` becomes an explicit sorting comparator.

`LAG()` becomes access to the previous element in the ordered partition.

This does not replace a database implementation, but it clarifies what the database is conceptually doing.

---

## C++ case study

The C++ program models an industry-style regional sales analytics system.

The problem is to generate an analytical report where every sale retains its identity while receiving contextual metrics.

Each sale contains:

- sale ID;
- employee ID;
- date;
- region;
- product;
- revenue.

The system calculates:

- regional total revenue;
- running regional revenue;
- previous sale revenue;
- next sale revenue;
- revenue change;
- moving average;
- percentage contribution;
- revenue rank;
- dense rank;
- row number.

This is equivalent to combining several SQL window calculations.

The program first validates the input data.

It then partitions sales by region.

Each partition is ordered chronologically using:

`date`

followed by:

`sale id`

The sale ID is a deterministic tiebreaker for duplicate dates.

A running total is calculated while traversing each ordered partition.

The previous value is obtained from the preceding array element, representing the conceptual behavior of `LAG()`.

The next value is obtained from the following element, representing `LEAD()`.

The moving average uses the current row and the previous two rows, corresponding conceptually to:

`ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`

Revenue ranking uses a revenue-descending order and a sale-ID tiebreaker.

The C++ program also includes a top-N-per-region report.

---

## C++ data structures

The case study uses standard C++ structures:

- `vector` for ordered collections of rows;
- `map` for partitions grouped by region;
- `unordered_map` for efficient region totals;
- `optional` for values that may not exist, such as the previous revenue of the first row;
- `set` and standard algorithms where appropriate.

`std::optional<double>` is particularly useful for modeling SQL `NULL` in a strongly typed application.

For example, the first row in a region has no previous revenue.

Instead of inventing a numeric value such as zero, the program represents the absence explicitly.

This distinction is important.

Zero means that a value exists and is zero.

NULL means that the value is unavailable or does not exist for the current relationship.

---

## C++ architectural stages

The case study follows several stages.

### Data creation

`createEmployees()` and `createSales()` provide deterministic test data.

### Validation

`validateEmployee()` and `validateSale()` enforce basic constraints before analytical processing.

### Partitioning

`partitionByRegion()` groups sales by region.

This corresponds conceptually to:

`PARTITION BY region`

### Ordering

`sortPartitionChronologically()` orders each partition by date and sale ID.

This corresponds conceptually to:

`ORDER BY sale_date, sale_id`

### Window calculation

`calculateSalesAnalytics()` calculates:

- partition totals;
- running totals;
- previous values;
- next values;
- moving averages;
- percentage contribution.

### Ranking

`assignRevenueRanks()` adds:

- row number;
- rank;
- dense rank.

### Top-N selection

`topNPerRegion()` implements a top-N-per-group pattern.

### Reporting

`printSalesAnalytics()` displays the analytical result.

### Testing

`runTests()` verifies important invariants and tie behavior.

This staged design mirrors how an analytical processing pipeline can be organized in production software.

---

## Algorithmic complexity

Window operations frequently require ordering.

If a partition contains `n` rows, sorting it generally costs approximately:

`O(n log n)`

When multiple partitions contain a total of `n` rows, the combined sorting cost depends on the distribution of rows among partitions.

Running totals can be calculated in linear time after the ordering has been established:

`O(n)`

The C++ program deliberately includes a straightforward ranking implementation that repeatedly counts higher values.

That implementation can approach:

`O(n²)`

within a partition.

A production implementation can optimize rank assignment by traversing an already sorted partition and tracking changes in the ordered value.

The conceptual lesson is important:

the mathematical definition of a window calculation does not dictate the most efficient implementation.

Database engines use execution planners and specialized operators to implement these operations efficiently.

---

## Database performance considerations

Window queries often require ordering.

The database may need to:

- scan rows;
- partition rows logically;
- sort rows;
- maintain temporary structures;
- calculate the window expression;
- return the final result.

Indexes can help with filtering and ordering, but an index does not automatically eliminate every sort or make every window query faster.

The Python schema creates indexes such as:

`idx_employees_department_salary`

and:

`idx_sales_region_date`

These indexes reflect common access patterns in the examples.

The Python script also uses:

`EXPLAIN QUERY PLAN`

to demonstrate how query plans can be inspected.

For production workloads, performance should be measured using realistic:

- row counts;
- partition sizes;
- data distributions;
- filters;
- indexes;
- concurrency levels.

An analytical query that is fast on a few thousand rows can behave very differently on millions or billions of rows.

---

## Window frames and performance

A frame can restrict the number of rows considered for a particular calculation.

For example:

`ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`

uses only three physical rows at most.

A complete-partition frame such as:

`ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`

can expose the entire partition to the calculation.

The correct frame should be selected based on the required semantics.

A frame is not merely a performance setting.

It changes the meaning of the result.

This is especially important for:

- `LAST_VALUE`;
- moving averages;
- cumulative calculations;
- ordered aggregates.

---

## Security considerations

Window functions themselves are not a security mechanism.

They calculate data that the query is already authorized to access.

Security should therefore be addressed at the surrounding application and database layers.

Important considerations include:

- use parameterized SQL for user-supplied values;
- do not construct SQL through unsafe string concatenation;
- enforce database permissions;
- restrict sensitive columns;
- apply row-level security where supported and required;
- avoid exposing confidential analytical results through unauthorized reports;
- validate input values in application code where appropriate.

A window function does not bypass database authorization by itself.

The Python examples use fixed SQL and parameterized execution infrastructure where parameters are needed, rather than constructing SQL from untrusted input.

---

## Common mistakes

### Treating `PARTITION BY` as `GROUP BY`

`GROUP BY` changes the number of rows.

`PARTITION BY` defines logical calculation groups while preserving rows.

### Forgetting the window `ORDER BY`

Functions such as `ROW_NUMBER`, `LAG`, and `LEAD` depend on a meaningful order.

The order should reflect the business meaning of the analysis.

### Using the wrong ranking function

`ROW_NUMBER`, `RANK`, and `DENSE_RANK` have different tie behavior.

### Assuming ties have a deterministic sequence

If two rows have the same ordering values, a unique tiebreaker may be required.

### Confusing window ordering with final output ordering

`ORDER BY` inside `OVER()` controls the analytical sequence.

The final query `ORDER BY` controls result presentation.

### Filtering a window result directly in `WHERE`

Use a derived table or common table expression when the window result needs to be filtered.

### Misunderstanding `LAST_VALUE`

The frame determines which rows are visible to `LAST_VALUE`.

Use an explicit frame when the intended result requires the final row of the entire partition.

### Treating `ROWS` as a date interval

`ROWS BETWEEN 2 PRECEDING AND CURRENT ROW` means two preceding physical rows.

It does not mean two preceding calendar days.

### Replacing NULL with zero without considering semantics

Zero and NULL represent different concepts.

Replacing one with the other can change business results.

---

## Important distinctions

| Concept | Meaning |
| --- | --- |
| `OVER()` | Turns an aggregate or analytical expression into a window calculation |
| `PARTITION BY` | Divides rows into independent logical windows |
| Window `ORDER BY` | Defines analytical sequence |
| Final `ORDER BY` | Controls output presentation |
| `ROW_NUMBER()` | Unique sequential position |
| `RANK()` | Ties share rank; gaps occur |
| `DENSE_RANK()` | Ties share rank; no gaps |
| `LAG()` | Access an earlier row |
| `LEAD()` | Access a later row |
| `FIRST_VALUE()` | Value from the first row of the frame |
| `LAST_VALUE()` | Value from the last row of the frame |
| `NTILE()` | Divides ordered rows into buckets |
| `SUM() OVER()` | Aggregate while retaining rows |
| `AVG() OVER()` | Average while retaining rows |
| Window frame | Restricts rows considered by an ordered window calculation |

---

## Practical applications

Window functions are widely useful for analytical workloads.

Typical applications include:

### Finance

- cumulative portfolio values;
- period-over-period changes;
- transaction rankings;
- account-level running balances;
- benchmark comparisons.

### Sales

- top sales representatives;
- top products by region;
- cumulative revenue;
- percentage contribution;
- previous-period comparisons.

### Human resources

- salary rankings;
- department benchmarks;
- compensation percentiles;
- tenure ordering;
- duplicate-record selection.

### Operations

- running production totals;
- previous machine readings;
- event sequence analysis;
- moving averages;
- anomaly investigation.

### E-commerce

- customer purchase sequence;
- previous order value;
- product ranking;
- customer segmentation;
- revenue contribution.

### Data engineering

- de-duplication;
- latest-record selection;
- event ordering;
- change detection;
- slowly changing analytical datasets.

---

## Implementation considerations

A reliable window query should begin with a precise business question.

For example:

"Find the top two employees in every department."

This is incomplete until "top" is defined.

Possible meanings include:

- highest salary;
- highest performance score;
- earliest hire;
- highest sales;
- most recent record.

The ordering expression must represent the intended business definition.

Similarly, "previous transaction" is meaningless until the sequence is defined.

The query should specify an appropriate ordering such as:

`ORDER BY transaction_timestamp, transaction_id`

rather than assuming that physical storage order represents chronological order.

---

## Production considerations

Production window queries should be evaluated for:

- correctness;
- deterministic ordering;
- NULL behavior;
- tie handling;
- frame semantics;
- index availability;
- partition size;
- memory usage;
- execution time;
- concurrency;
- database-specific behavior.

SQL dialects differ.

A query that works in one database may require syntax changes in another.

Examples of database systems with window-function support include modern versions of PostgreSQL, SQL Server, Oracle, MySQL, MariaDB, SQLite, and others, but individual functions and syntax details can differ.

Always validate the exact query against the target database engine.

---

## Relationship between the three implementations

The three implementations intentionally have different roles.

### Python

Python provides actual SQL execution through SQLite.

It is the most direct implementation for learning the SQL syntax because the queries use real:

- `OVER`;
- `PARTITION BY`;
- `ORDER BY`;
- window aggregates;
- ranking functions;
- frame specifications.

### JavaScript

JavaScript exposes the mechanics behind a window calculation.

Its `applyWindow()` function shows how a program can:

1. partition data;
2. order each partition;
3. traverse the ordered rows;
4. calculate contextual values;
5. preserve every row.

This is useful for understanding what a database engine conceptually needs to accomplish.

### C++

C++ turns the concepts into a structured analytical processing case study.

The program uses:

- typed data structures;
- partition maps;
- ordered vectors;
- optional values;
- validation;
- ranking;
- running calculations;
- top-N selection;
- testing;
- complexity analysis.

The three implementations therefore demonstrate the same analytical concepts at different abstraction levels.

---

## Testing considerations

Window-function queries should be tested with data that exposes their important semantics.

A useful test dataset should include:

- multiple partitions;
- single-row partitions;
- tied ordering values;
- duplicate dates;
- first rows;
- last rows;
- NULL values where relevant;
- empty result sets;
- multiple rows with the same business key.

The provided implementations deliberately include ties.

The Python program verifies ranking behavior with assertions.

The JavaScript program validates row numbering and top-N behavior.

The C++ program verifies employee ranking, tie semantics, partition totals, and percentage ranges.

This is more useful than testing only ordinary unique-value cases because many window-function bugs appear specifically at boundaries and ties.

---

## Conceptual model

A useful way to reason about:

`SUM(value) OVER (PARTITION BY group ORDER BY timestamp)`

is:

"Take each group separately, arrange its rows in timestamp order, and calculate the requested value using the relevant window around each current row."

For a running total, the window grows from the first row to the current row.

For a moving average, the window moves with the current row.

For `LAG`, the calculation looks backward.

For `LEAD`, it looks forward.

For ranking functions, the ordered partition determines the position.

This model makes many advanced window queries easier to understand because they become combinations of three questions:

1. Which rows belong together?
2. In what order should they be considered?
3. Which rows around the current row should participate in the calculation?

Those questions correspond closely to:

- `PARTITION BY`;
- `ORDER BY`;
- the window frame or function-specific behavior.

---

## Reference patterns demonstrated by the implementations

### Company-wide average

`AVG(salary) OVER ()`

### Department average

`AVG(salary) OVER (PARTITION BY department_id)`

### Department ranking

`RANK() OVER (PARTITION BY department_id ORDER BY salary DESC)`

### Deterministic row number

`ROW_NUMBER() OVER (PARTITION BY department_id ORDER BY salary DESC, employee_id)`

### Previous value

`LAG(revenue) OVER (PARTITION BY region ORDER BY sale_date, sale_id)`

### Next value

`LEAD(revenue) OVER (PARTITION BY region ORDER BY sale_date, sale_id)`

### Running total

`SUM(revenue) OVER (PARTITION BY region ORDER BY sale_date, sale_id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`

### Moving three-row average

`AVG(revenue) OVER (PARTITION BY region ORDER BY sale_date, sale_id ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)`

### Percentage of partition

`revenue / SUM(revenue) OVER (PARTITION BY region) * 100`

### Top two rows per group

Calculate `ROW_NUMBER()` in an inner query and filter the result in an outer query.

These patterns form the practical foundation for more advanced window-function work.
