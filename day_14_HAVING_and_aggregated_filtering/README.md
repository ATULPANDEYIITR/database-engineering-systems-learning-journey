# HAVING and aggregated filtering

## Topic introduction

`HAVING` is the SQL clause used to filter groups after `GROUP BY` and aggregate calculations have been performed. It is most useful when a requirement depends on a value such as `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, or another aggregate expression.

A basic grouped-filtering query has this structure:

    SELECT group_column, AGGREGATE(expression)
    FROM table_name
    WHERE row_condition
    GROUP BY group_column
    HAVING aggregate_condition
    ORDER BY aggregate_result;

The central distinction is:

- `WHERE` filters individual source rows.
- `GROUP BY` combines rows into groups.
- Aggregate functions calculate metrics for those groups.
- `HAVING` filters the resulting groups.
- `ORDER BY` sorts the surviving result.
- `LIMIT` restricts how many rows are returned.

The accompanying Python script uses SQLite through Python's built-in `sqlite3` module. It creates a complete sales-oriented dataset containing customers, products, orders, and order items, then demonstrates grouped filtering from introductory examples through advanced analytical patterns.

## Database model used in the script

The script creates four related tables.

### Customers

The `customers` table represents customers.

Important columns include:

- `customer_id`: unique customer identifier
- `customer_name`: customer name
- `city`: customer location
- `customer_segment`: Consumer, Business, or Enterprise

### Products

The `products` table represents products.

Important columns include:

- `product_id`: unique product identifier
- `product_name`: product name
- `category`: product category
- `unit_price`: standard product price

### Orders

The `orders` table represents customer orders.

Important columns include:

- `order_id`: unique order identifier
- `customer_id`: customer associated with the order
- `order_date`: order date
- `status`: Completed, Pending, Cancelled, or Returned

### Order items

The `order_items` table represents individual products within an order.

Important columns include:

- `order_item_id`: unique line identifier
- `order_id`: associated order
- `product_id`: associated product
- `quantity`: number of units
- `unit_price`: transaction price
- `discount_percent`: discount applied to the line

The relationships are:

    customer
        |
        | one-to-many
        v
    orders
        |
        | one-to-many
        v
    order_items
        |
        | many-to-one
        v
    products

This structure makes it possible to demonstrate an important aggregation issue: joining a parent table to a child table can multiply rows.

## Aggregate functions

Aggregation converts multiple rows into a group-level value.

### COUNT

`COUNT(*)` counts rows.

Example:

    SELECT COUNT(*)
    FROM orders;

`COUNT(column)` counts non-NULL values in the specified column.

Example:

    SELECT COUNT(status)
    FROM orders;

`COUNT(DISTINCT column)` counts unique non-NULL values.

Example:

    SELECT COUNT(DISTINCT customer_id)
    FROM orders;

These three forms answer different questions and should not be treated as interchangeable.

### SUM

`SUM` calculates the total of numeric values.

Example:

    SELECT SUM(quantity)
    FROM order_items;

A grouped version can calculate units sold per product:

    SELECT product_id, SUM(quantity)
    FROM order_items
    GROUP BY product_id;

### AVG

`AVG` calculates an arithmetic mean.

Example:

    SELECT AVG(unit_price)
    FROM order_items;

The meaning of an average depends on the rows being averaged. An average across order-item rows is not necessarily the same as an average across orders or customers.

### MIN and MAX

`MIN` returns the smallest value and `MAX` returns the largest value.

Example:

    SELECT
        MIN(unit_price),
        MAX(unit_price)
    FROM order_items;

These functions are also valid within grouped queries.

## What GROUP BY does

`GROUP BY` defines the population over which aggregate functions operate.

For example:

    SELECT
        customer_id,
        COUNT(*) AS order_count
    FROM orders
    GROUP BY customer_id;

The result contains one row per customer.

For a customer with five orders, `COUNT(*)` evaluates to five for that customer's group.

If the query instead uses:

    GROUP BY customer_id, status

then the group represents a combination of customer and status.

The same customer can therefore produce multiple groups:

    customer 1 + Completed
    customer 1 + Pending
    customer 1 + Cancelled

The grouping columns define the grain of the result.

## The fundamental role of HAVING

Suppose the requirement is:

> Find customers who have at least two orders.

The aggregate condition is:

    COUNT(*) >= 2

The correct query is:

    SELECT
        customer_id,
        COUNT(*) AS order_count
    FROM orders
    GROUP BY customer_id
    HAVING COUNT(*) >= 2;

`COUNT(*)` is calculated separately for every customer group. `HAVING` then removes groups whose count is less than two.

This is the defining use of `HAVING`.

## WHERE versus HAVING

The most important distinction in this topic is the difference between row-level and group-level filtering.

### WHERE

`WHERE` operates before grouping.

Example:

    SELECT
        customer_id,
        COUNT(*) AS completed_orders
    FROM orders
    WHERE status = 'Completed'
    GROUP BY customer_id;

Only completed orders participate in the grouping.

### HAVING

`HAVING` operates on grouped results.

Example:

    SELECT
        customer_id,
        COUNT(*) AS completed_orders
    FROM orders
    WHERE status = 'Completed'
    GROUP BY customer_id
    HAVING COUNT(*) >= 2;

The query performs two different types of filtering:

    WHERE status = 'Completed'

defines which rows are eligible for aggregation.

    HAVING COUNT(*) >= 2

defines which groups are eligible for the final result.

A useful mental model is:

    WHERE -> Which rows should participate?
    GROUP BY -> How should those rows be grouped?
    HAVING -> Which groups should survive?

## Logical query processing order

A simplified logical processing model is:

    FROM
    WHERE
    GROUP BY
    HAVING
    SELECT
    ORDER BY
    LIMIT

This is a conceptual processing order, not necessarily the physical execution plan used by the database engine.

For example:

    SELECT
        customer_id,
        COUNT(*) AS order_count
    FROM orders
    WHERE status = 'Completed'
    GROUP BY customer_id
    HAVING COUNT(*) >= 2
    ORDER BY order_count DESC;

Conceptually:

1. Read rows from `orders`.
2. Remove rows whose status is not `Completed`.
3. Group the remaining rows by customer.
4. Count rows within each customer group.
5. Remove groups with fewer than two rows.
6. Sort the surviving groups.
7. Return them.

Understanding this sequence prevents many SQL mistakes.

## Why aggregate expressions do not normally belong in WHERE

The following pattern is invalid:

    SELECT
        customer_id,
        COUNT(*)
    FROM orders
    WHERE COUNT(*) >= 2
    GROUP BY customer_id;

The problem is that `WHERE` is logically evaluated before the grouping and aggregate calculation.

At the `WHERE` stage, the database is evaluating individual source rows. `COUNT(*)` is a group-level calculation.

The correct form is:

    SELECT
        customer_id,
        COUNT(*) AS order_count
    FROM orders
    GROUP BY customer_id
    HAVING COUNT(*) >= 2;

## Filtering aggregated revenue

The script calculates transaction-line revenue using:

    quantity * unit_price * (1 - discount_percent / 100.0)

Customer-level revenue is then calculated using:

    SUM(
        quantity * unit_price *
        (1 - discount_percent / 100.0)
    )

A requirement such as:

> Find customers with at least 100,000 in completed revenue.

can be expressed as:

    SELECT
        customer_id,
        SUM(
            quantity * unit_price *
            (1 - discount_percent / 100.0)
        ) AS revenue
    FROM orders
    JOIN order_items
        ON order_items.order_id = orders.order_id
    WHERE orders.status = 'Completed'
    GROUP BY customer_id
    HAVING SUM(
        quantity * unit_price *
        (1 - discount_percent / 100.0)
    ) >= 100000;

The revenue threshold is a group-level condition, so it belongs in `HAVING`.

## Multiple conditions in HAVING

`HAVING` supports Boolean expressions.

Example:

    HAVING COUNT(*) >= 2
       AND SUM(amount) >= 100000

Both conditions must be true.

`OR` can be used when either condition is sufficient:

    HAVING COUNT(*) >= 5
        OR SUM(amount) >= 200000

Parentheses should be used when combining `AND` and `OR` in complex expressions.

Example:

    HAVING
        (COUNT(*) >= 2 AND SUM(amount) >= 100000)
        OR MAX(amount) >= 75000

This makes the intended Boolean logic explicit.

## HAVING without GROUP BY

An aggregate query can sometimes use `HAVING` without an explicit `GROUP BY`.

Example:

    SELECT
        COUNT(*) AS completed_orders
    FROM orders
    WHERE status = 'Completed'
    HAVING COUNT(*) >= 10;

The filtered dataset can be treated as one aggregate group.

If the count is at least ten, the query returns the aggregate row. If the condition is false, no result row is returned.

This can be useful for threshold checks.

It is important to distinguish the absence of `GROUP BY` from the absence of aggregation. The query still contains an aggregate function, so the entire qualifying dataset is treated as one group.

## COUNT variants

The script demonstrates three important forms.

    COUNT(*)

Counts rows, including rows where individual columns contain `NULL`.

    COUNT(column)

Counts only rows where that column is non-NULL.

    COUNT(DISTINCT column)

Counts unique non-NULL values.

For example:

    SELECT
        customer_id,
        COUNT(*) AS order_rows,
        COUNT(DISTINCT order_date) AS active_days
    FROM orders
    GROUP BY customer_id
    HAVING COUNT(DISTINCT order_date) >= 2;

This asks whether the customer had orders on at least two distinct dates.

## NULL and aggregation

`NULL` does not represent an ordinary numeric value.

Most standard numeric aggregate functions ignore NULL inputs.

For example:

    SUM(amount)
    AVG(amount)

do not treat NULL as zero.

The script creates groups containing NULL values to demonstrate this behavior.

A group containing only NULL values can produce:

    SUM(amount) -> NULL
    AVG(amount) -> NULL

rather than zero.

This matters when a `HAVING` expression compares an aggregate result.

For example:

    HAVING SUM(amount) > 15

does not return a group where `SUM(amount)` is NULL.

SQL uses three-valued logic:

    TRUE
    FALSE
    UNKNOWN

A `HAVING` condition must evaluate to TRUE for the group to remain.

## COALESCE and aggregate results

`COALESCE` can replace NULL with a chosen value.

Example:

    HAVING COALESCE(SUM(amount), 0) > 10

This treats a NULL total as zero.

The decision should be based on the meaning of the data.

There is a semantic difference between:

    no known value

and:

    actual value of zero

Replacing every NULL with zero can hide this distinction.

## Conditional aggregation

A powerful pattern combines `CASE` with an aggregate function.

Example:

    SUM(
        CASE
            WHEN status = 'Completed' THEN 1
            ELSE 0
        END
    )

This produces a conditional count.

A grouped query can calculate several metrics simultaneously:

    SELECT
        customer_id,
        COUNT(*) AS total_orders,
        SUM(
            CASE
                WHEN status = 'Completed' THEN 1
                ELSE 0
            END
        ) AS completed_orders,
        SUM(
            CASE
                WHEN status = 'Cancelled' THEN 1
                ELSE 0
            END
        ) AS cancelled_orders
    FROM orders
    GROUP BY customer_id;

The conditional aggregate can then be used in `HAVING`.

Example:

    HAVING SUM(
        CASE
            WHEN status = 'Completed' THEN 1
            ELSE 0
        END
    ) >= 2

This pattern is particularly useful for status-based reporting.

Some database systems support aggregate `FILTER` syntax, but SQL dialect support varies. `CASE`-based conditional aggregation is broadly useful when portability is important.

## Grouping by multiple columns

A query such as:

    GROUP BY city, customer_segment

creates one group for each distinct combination of city and segment.

Therefore, a group is not simply a city and not simply a segment.

For example, these can be separate groups:

    Delhi + Consumer
    Delhi + Business
    Delhi + Enterprise

A `HAVING` condition is evaluated independently for each combination.

## Join multiplication

Join multiplication is one of the most important practical aggregation problems.

Suppose one order contains five order-item rows.

After joining:

    orders
    JOIN order_items

that order appears five times in the joined result.

Therefore:

    COUNT(*)

counts order-item rows, not necessarily orders.

If the business question is:

> How many unique orders did the customer place?

the safer expression is:

    COUNT(DISTINCT order_id)

This distinction is critical when using `HAVING`.

Incorrect logic can qualify a customer because the customer has many order-item rows rather than because the customer has many actual orders.

Before writing an aggregate query, identify the grain:

    What does one row represent at this stage?

It might represent:

- one customer
- one order
- one order item
- one product
- one customer-month
- one product-month

The aggregate function must match the intended grain.

## Derived tables and aggregate filtering

Instead of `HAVING`, an aggregate result can be exposed through a derived table.

Example:

    SELECT
        customer_id,
        order_count
    FROM (
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY customer_id
    ) AS customer_counts
    WHERE order_count >= 2;

This creates a relation containing the grouped result and then applies an ordinary `WHERE` condition to the outer query.

The two approaches express related logic:

    GROUP BY ... HAVING ...

and:

    aggregate query
        -> derived table
        -> outer WHERE

`HAVING` is often clearer when the condition belongs directly to grouping. A derived table can be useful when the aggregate result becomes an explicit intermediate dataset.

## Common table expressions

A common table expression, or CTE, can separate aggregation from subsequent analysis.

Example structure:

    WITH customer_metrics AS (
        SELECT
            customer_id,
            COUNT(*) AS completed_orders,
            SUM(amount) AS revenue
        FROM orders
        WHERE status = 'Completed'
        GROUP BY customer_id
    )
    SELECT
        customer_id,
        completed_orders,
        revenue
    FROM customer_metrics
    WHERE completed_orders >= 2
      AND revenue >= 100000;

The script uses this approach for more advanced customer qualification.

CTEs are useful when:

- the grouped result has several metrics
- the result needs to be reused
- the query contains multiple analytical stages
- separating logical stages improves readability

## HAVING and window functions

`GROUP BY` and window functions solve different problems.

A grouped query:

    SELECT
        customer_id,
        COUNT(*) AS order_count
    FROM orders
    GROUP BY customer_id;

collapses multiple rows into one row per customer.

A window expression preserves result rows while calculating across them.

For example:

    SUM(order_count) OVER ()

can calculate the total across the grouped customer results.

A useful analytical pipeline is:

    transaction rows
        -> GROUP BY
        -> HAVING
        -> window calculations
        -> final ordering

The script demonstrates a customer-level revenue percentage using this pattern.

## Top groups

`HAVING`, `ORDER BY`, and `LIMIT` have different responsibilities.

For example:

    HAVING revenue >= 50000

determines which groups are eligible.

    ORDER BY revenue DESC

ranks the eligible groups.

    LIMIT 3

selects the first three groups from that ranking.

They should not be treated as interchangeable.

The query therefore has a conceptual flow:

    calculate groups
        -> remove groups below threshold
        -> rank surviving groups
        -> select top N

## Time-based grouped filtering

Reporting frequently requires grouping by a time period.

The SQLite script uses:

    substr(order_date, 1, 7)

to obtain a year-month representation such as:

    2026-01
    2026-02
    2026-03

A query can then group by month and apply a revenue threshold:

    GROUP BY substr(order_date, 1, 7)
    HAVING SUM(revenue_expression) >= 100000

Date and time syntax varies considerably across SQL engines, so production implementations should use the appropriate functions for the target database.

## Ratios and percentages

`HAVING` can filter ratios, not only simple counts and sums.

For example, a completion rate can be calculated as:

    completed_orders / total_orders

A query can then retain customers whose completion rate is at least 75 percent.

The script uses multiplication by `1.0` in SQLite to ensure decimal division:

    1.0 * completed_orders / total_orders

When calculating ratios, check:

- whether the denominator can be zero
- whether integer division is possible
- whether NULL values are present
- whether the numerator and denominator represent the intended populations
- whether rounding should occur before or after filtering

Rounding can itself affect threshold decisions. In financial reporting, it is usually important to distinguish between filtering on an unrounded value and filtering on a displayed rounded value.

## HAVING with DISTINCT

`DISTINCT` changes the population being aggregated.

Example:

    COUNT(DISTINCT status)

answers:

> How many different statuses does this group have?

It does not answer:

> How many order rows does this group have?

Similarly:

    COUNT(DISTINCT order_id)

is appropriate when the business concept is a unique order rather than a physical row in a joined dataset.

## LEFT JOIN and zero-count groups

Outer joins introduce an important grouped-filtering pattern.

Suppose the requirement is:

> Find customers with no completed orders.

The script uses a `LEFT JOIN` and puts the status condition in the join condition:

    LEFT JOIN orders AS o
        ON o.customer_id = c.customer_id
        AND o.status = 'Completed'

Then:

    COUNT(o.order_id)

returns zero for customers without a matching completed order.

The condition:

    HAVING COUNT(o.order_id) = 0

selects those customers.

This is different from placing the condition in `WHERE`.

A `WHERE` condition that requires `o.status = 'Completed'` would remove the unmatched rows and can effectively destroy the zero-count behavior expected from the `LEFT JOIN`.

## Predicate placement

A useful optimization and correctness question is:

> Can this condition be evaluated before grouping?

If the answer is yes, it is often a `WHERE` predicate.

For example:

    WHERE status = 'Completed'

reduces the number of rows that need to be grouped.

An aggregate condition such as:

    HAVING SUM(amount) >= 100000

cannot generally be evaluated until the group-level sum has been computed.

Correct predicate placement can improve both readability and performance.

## SQL aliases in HAVING

The script demonstrates SQLite's support for referring to a select alias in `HAVING`.

Example:

    SELECT
        customer_id,
        COUNT(*) AS order_count
    FROM orders
    GROUP BY customer_id
    HAVING order_count >= 2;

SQL dialects differ in their handling of aliases in different clauses. For portable SQL, explicitly repeating the aggregate expression can be safer:

    HAVING COUNT(*) >= 2

The actual target database should determine which syntax is appropriate.

## Three-valued logic

SQL conditions can evaluate to:

    TRUE
    FALSE
    UNKNOWN

`NULL` commonly produces `UNKNOWN` in comparisons.

For example:

    SUM(amount) > 100

does not become TRUE when `SUM(amount)` is NULL.

This is especially important in `HAVING`, because only groups for which the predicate evaluates to TRUE survive.

The difference between FALSE and UNKNOWN is important in more complex expressions involving `AND`, `OR`, and `NOT`.

## Common mistakes

### Using WHERE for aggregate filtering

Incorrect:

    WHERE COUNT(*) >= 2

Correct:

    HAVING COUNT(*) >= 2

The aggregate condition belongs to the group-filtering stage.

### Filtering source rows in HAVING

If the requirement is:

> Count only completed orders.

the status restriction generally belongs in:

    WHERE status = 'Completed'

Then `HAVING` should handle the group-level threshold.

Using the wrong clause can change the meaning of the query.

### Counting joined rows instead of entities

A parent-child join can multiply rows.

If an order has several order items:

    COUNT(*)

may count order-item rows.

Use:

    COUNT(DISTINCT order_id)

when the metric represents unique orders.

### Ignoring NULL behavior

`COUNT(column)`, `SUM(column)`, and `AVG(column)` have NULL-related behavior that differs from ordinary arithmetic.

A query should explicitly define what NULL means for the business metric.

### Grouping at the wrong level

These queries answer different questions:

    GROUP BY customer_id

    GROUP BY customer_id, month

The first produces customer-level metrics. The second produces customer-month metrics.

### Mixing AND and OR without parentheses

Complex conditions should be written explicitly.

Prefer:

    HAVING
        (COUNT(*) >= 2 AND SUM(amount) >= 100000)
        OR MAX(amount) >= 75000

rather than depending on implicit operator precedence.

### Applying LIMIT before validating the logic

`LIMIT` can hide groups that should be present.

Validate:

    grouping
    aggregates
    HAVING
    ordering

before relying on a limited result.

## Boundary conditions

Aggregate filtering should be tested around thresholds.

If the requirement is:

    HAVING COUNT(*) >= 5

then these cases are materially different:

    COUNT(*) = 4
    COUNT(*) = 5
    COUNT(*) = 6

The same applies to:

    >
    >=
    <
    <=
    =
    BETWEEN

A one-character change can alter the population selected by an analytical query.

## Performance considerations

`HAVING` is applied to grouped results, so performance depends on the entire query rather than on `HAVING` in isolation.

The database may need to perform:

    source access
        -> joins
        -> WHERE filtering
        -> grouping
        -> aggregation
        -> HAVING
        -> sorting
        -> limiting

Reducing unnecessary rows before grouping can therefore be valuable.

For example:

    WHERE status = 'Completed'

can prevent non-completed orders from entering the aggregation process.

Indexes can support the earlier stages. The script creates indexes on order status/customer and order-item order identifiers and demonstrates SQLite's `EXPLAIN QUERY PLAN`.

Indexes have trade-offs. They require storage and can increase the cost of writes because the indexes must also be maintained.

Performance should be measured with realistic data and the actual production database engine.

## Query-plan analysis

`EXPLAIN QUERY PLAN` is useful for understanding how a database approaches a query.

It can help identify:

- table scans
- index usage
- join strategies
- temporary structures
- sorting behavior

The exact output is database-specific.

A query that performs well on a small development dataset may behave differently at production scale. Execution plans should therefore be examined with representative data volumes.

## Production reporting considerations

For small datasets, direct `GROUP BY` and `HAVING` queries are usually straightforward.

For large analytical workloads, repeated aggregation may become expensive.

Production architectures may use:

- summary tables
- materialized views
- partitioning
- incremental aggregation
- analytical databases
- reporting datasets
- carefully designed indexes

These approaches trade query speed against complexity, storage, freshness, and maintenance.

A precomputed summary can make reporting fast, but the system must keep the derived information synchronized with source data.

The logical concept of aggregated filtering remains the same even when the physical reporting architecture becomes more sophisticated.

## Security considerations

`HAVING` is not a security mechanism.

When values are supplied by users or external systems, parameterized queries should be used.

Safe structure:

    SELECT
        customer_id,
        COUNT(*) AS order_count
    FROM orders
    WHERE customer_id = ?
    GROUP BY customer_id
    HAVING COUNT(*) >= ?;

Unsafe query construction can occur when untrusted values are concatenated directly into SQL.

SQL injection prevention depends on proper parameter binding and safe query construction.

Authorization is a separate concern. A correctly written aggregate query can still expose data that the current user is not permitted to see if application-level access control is missing.

## Testing aggregated filtering

Grouped SQL should be tested with boundary and exceptional data.

Important test cases include:

- no matching rows
- exactly the threshold
- one row below the threshold
- one row above the threshold
- NULL aggregate inputs
- groups containing only NULL values
- duplicate business entities
- multiple child rows per parent
- customers with no matching orders
- zero-count outer-join groups
- multiple statuses
- multiple dates
- decimal values
- large aggregates

The script contains executable assertions for customer-count thresholds and demonstrations of boundary values.

## Debugging strategy

When a `HAVING` query produces unexpected results, build the query incrementally.

### Inspect source rows

First verify the data being considered.

    SELECT ...
    FROM ...
    WHERE ...;

### Inspect grouping

Then remove `HAVING` and inspect group sizes.

    SELECT
        group_column,
        COUNT(*) AS row_count
    FROM ...
    WHERE ...
    GROUP BY group_column;

### Inspect aggregate values

Add the metrics used by the business rule.

    SELECT
        group_column,
        COUNT(*) AS row_count,
        SUM(amount) AS total_amount,
        AVG(amount) AS average_amount
    FROM ...
    GROUP BY group_column;

### Add HAVING

Only after the aggregate values are understood should the group filter be applied.

This makes it easier to identify whether the problem originates in:

- source filtering
- joins
- grouping
- aggregation
- NULL handling
- threshold logic

## Business-question translation

A useful method for converting a business requirement into SQL is:

1. Identify the entity being measured.
2. Identify the grouping key.
3. Identify the metric.
4. Decide whether the metric is aggregate.
5. Put row-level restrictions in `WHERE`.
6. Put group-level restrictions in `HAVING`.
7. Validate the grain.
8. Add ordering or ranking only after the metric is correct.

Examples:

### Customers with at least three orders

    SELECT customer_id
    FROM orders
    GROUP BY customer_id
    HAVING COUNT(*) >= 3;

### Cities with at least two customers

    SELECT city
    FROM customers
    GROUP BY city
    HAVING COUNT(*) >= 2;

### Products sold in at least two orders

    SELECT product_id
    FROM order_items
    GROUP BY product_id
    HAVING COUNT(DISTINCT order_id) >= 2;

The critical step is defining what one group represents.

## Reusable HAVING patterns

### Minimum group size

    SELECT group_column, COUNT(*) AS row_count
    FROM table_name
    GROUP BY group_column
    HAVING COUNT(*) >= 10;

### Minimum total

    SELECT group_column, SUM(amount) AS total_amount
    FROM table_name
    GROUP BY group_column
    HAVING SUM(amount) >= 100000;

### Range of totals

    SELECT group_column, SUM(amount) AS total_amount
    FROM table_name
    GROUP BY group_column
    HAVING SUM(amount) BETWEEN 50000 AND 100000;

### Multiple aggregate requirements

    SELECT group_column
    FROM table_name
    GROUP BY group_column
    HAVING COUNT(*) >= 5
       AND AVG(amount) > 1000;

### Minimum number of unique values

    SELECT group_column
    FROM table_name
    GROUP BY group_column
    HAVING COUNT(DISTINCT category) >= 3;

### Conditional threshold

    SELECT group_column
    FROM table_name
    GROUP BY group_column
    HAVING SUM(
        CASE
            WHEN status = 'Completed' THEN 1
            ELSE 0
        END
    ) >= 5;

These patterns cover many practical grouped-filtering requirements.

## Important distinctions

| Concept | Purpose |
|---|---|
| `WHERE` | Filters source rows |
| `GROUP BY` | Defines groups |
| `COUNT` | Counts rows or values |
| `COUNT(DISTINCT ...)` | Counts unique values |
| `SUM` | Calculates totals |
| `AVG` | Calculates averages |
| `MIN` | Finds minimum values |
| `MAX` | Finds maximum values |
| `HAVING` | Filters groups |
| `ORDER BY` | Sorts the result |
| `LIMIT` | Restricts the number of returned rows |
| CTE | Names an intermediate query result |
| Derived table | Uses a query as a table-like input |
| Window function | Calculates across related rows without collapsing them |

## HAVING versus derived-table WHERE

These approaches can express similar logic:

    SELECT
        customer_id,
        COUNT(*) AS order_count
    FROM orders
    GROUP BY customer_id
    HAVING COUNT(*) >= 2;

and:

    SELECT
        customer_id,
        order_count
    FROM (
        SELECT
            customer_id,
            COUNT(*) AS order_count
        FROM orders
        GROUP BY customer_id
    ) AS customer_counts
    WHERE order_count >= 2;

`HAVING` communicates that the condition is directly associated with grouping.

The derived-table version is useful when the grouped result becomes an intermediate dataset that will undergo additional transformations.

## HAVING versus window functions

`GROUP BY` reduces multiple rows into groups.

Window functions preserve rows while calculating across a related set.

For example:

    GROUP BY customer_id

produces one result row per customer.

A window expression such as:

    SUM(order_count) OVER ()

can calculate a total across those customer-level results without collapsing them further.

They are complementary techniques rather than replacements for one another.

## HAVING and outer joins

A particularly useful pattern is finding entities with zero related records.

Example:

    SELECT
        c.customer_id,
        COUNT(o.order_id) AS completed_orders
    FROM customers AS c
    LEFT JOIN orders AS o
        ON o.customer_id = c.customer_id
        AND o.status = 'Completed'
    GROUP BY c.customer_id
    HAVING COUNT(o.order_id) = 0;

This can identify:

- customers with no orders
- products with no sales
- employees with no assignments
- accounts with no transactions

The placement of the condition in the `ON` clause is important because it preserves unmatched rows.

## Dialect considerations

`HAVING` is a standard SQL concept, but individual database engines differ in syntax and behavior.

Potential differences include:

- aggregate functions
- date functions
- alias visibility
- `FILTER` support
- grouping rules
- NULL-related behavior of specialized functions
- optimizer behavior
- execution-plan syntax

The script uses SQLite because it is available through Python's standard library and is sufficient for demonstrating the core concepts.

Production SQL should be tested against the actual database engine being used.

## Practical applications

Aggregated filtering is common in:

- sales reporting
- customer segmentation
- financial reporting
- inventory analysis
- marketing analytics
- fraud detection
- transaction monitoring
- operational dashboards
- employee workload analysis
- product performance analysis
- cohort analysis
- revenue qualification
- customer retention analysis
- quality-control reporting

Typical business requirements include:

> Customers with more than five purchases.

    HAVING COUNT(*) > 5

> Products generating at least 100,000 in revenue.

    HAVING SUM(revenue) >= 100000

> Cities with at least 20 customers.

    HAVING COUNT(*) >= 20

> Customers active in at least three months.

    HAVING COUNT(DISTINCT month) >= 3

> Products appearing in at least ten distinct orders.

    HAVING COUNT(DISTINCT order_id) >= 10

> Customer segments with sufficient transaction volume.

    HAVING COUNT(DISTINCT transaction_id) >= threshold

The common pattern is always the same: calculate a group-level metric and then decide which groups satisfy the requirement.

## Complete query reasoning model

A reliable way to reason about a grouped query is:

    1. What is the source?
    2. What does one source row represent?
    3. Which rows should be excluded before aggregation?
    4. What defines a group?
    5. What aggregate metrics are required?
    6. Which conditions depend on those aggregates?
    7. Are NULL values possible?
    8. Can joins multiply rows?
    9. Should the metric count rows or unique entities?
    10. Should groups be ranked?
    11. Is a top-N limit required?
    12. Does the SQL dialect support the syntax being used?
    13. Does the query perform adequately at realistic scale?
    14. Are parameterization and authorization handled correctly?

This reasoning process is more important than memorizing the `HAVING` keyword because it determines whether the resulting query represents the intended business logic.

## Script coverage

The Python study file demonstrates:

- aggregate-function fundamentals
- `WHERE` versus `HAVING`
- basic `HAVING`
- revenue aggregation
- multiple aggregate conditions
- `HAVING` without `GROUP BY`
- `COUNT` variants
- NULL behavior
- `CASE`-based conditional aggregation
- aggregate aliases
- multiple grouping columns
- join multiplication
- aggregate subqueries
- common table expressions
- derived tables
- window functions
- top-group selection
- time-based aggregation
- product performance analysis
- customer-segment analysis
- common SQL anti-patterns
- three-valued logic
- `DISTINCT` aggregation
- percentage calculations
- reusable grouped-filtering patterns
- query-plan inspection
- predicate placement
- data-quality checks
- parameterized queries
- aggregate testing
- zero-count `LEFT JOIN` patterns
- business-requirement translation
- advanced customer qualification
- production reporting considerations
- SQL dialect differences
- debugging methodology
- threshold and boundary testing
- an integrated multi-stage analytical query

The central principle demonstrated throughout the script is that `HAVING` is fundamentally about **filtering groups based on aggregated or group-level conditions**, while `WHERE` is fundamentally about **filtering rows before grouping**.
