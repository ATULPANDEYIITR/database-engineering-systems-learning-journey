# SQL aggregations: COUNT, SUM, AVG, MIN, MAX, GROUP BY

## Introduction

SQL aggregation is the process of calculating summary information from multiple rows in a relational dataset. Aggregations are fundamental to reporting, business intelligence, data analysis, financial analysis, operational dashboards, and database applications.

The Python script accompanying this README uses SQLite through Python's built-in `sqlite3` module. It creates a complete sample sales database and progressively demonstrates aggregation concepts using executable SQL.

The central aggregate functions are:

- `COUNT()` for counting rows or non-NULL values
- `SUM()` for calculating totals
- `AVG()` for calculating arithmetic means
- `MIN()` for finding the smallest value
- `MAX()` for finding the largest value

`GROUP BY` changes an aggregation from a single overall result into separate results for defined groups.

The script also demonstrates related concepts such as `WHERE`, `HAVING`, `DISTINCT`, `CASE`, `JOIN`, `LEFT JOIN`, `COALESCE`, subqueries, Common Table Expressions, conditional aggregation, weighted averages, window functions, query plans, indexing, data-quality checks, and SQL security.

## Database structure

The example database contains three tables.

### Customers

The `customers` table represents customer information.

Important columns include:

- `customer_id`
- `customer_name`
- `city`
- `segment`
- `signup_date`

Each customer has one row identified by `customer_id`.

### Products

The `products` table represents products.

Important columns include:

- `product_id`
- `product_name`
- `category`
- `unit_price`
- `cost_price`

Each product has one row identified by `product_id`.

### Orders

The `orders` table represents transaction-level sales data.

Important columns include:

- `order_id`
- `customer_id`
- `product_id`
- `order_date`
- `quantity`
- `unit_price`
- `discount_percent`
- `sales_channel`
- `status`

The order table is the main transactional table used for aggregation.

## Understanding aggregation

Without aggregation, a query can return one row for every matching record.

For example, selecting rows from the `orders` table can return many individual transactions.

An aggregate query instead transforms many rows into one or more summary results.

A query containing an aggregate function without `GROUP BY` generally produces one summary row for the entire matching input.

For example:

    SELECT COUNT(*)
    FROM orders;

The result represents the number of rows in `orders`.

When `GROUP BY` is introduced, the input is partitioned into groups and the aggregate calculation is performed independently for each group.

For example:

    SELECT customer_id, COUNT(*)
    FROM orders
    GROUP BY customer_id;

The result contains one row for each customer represented in the orders table.

## COUNT

`COUNT()` measures the number of rows or values.

There are three important forms.

### COUNT(*)

`COUNT(*)` counts rows.

    SELECT COUNT(*)
    FROM orders;

This is the appropriate form when the question is simply how many rows exist.

It counts rows even when individual columns contain `NULL`.

### COUNT(column)

`COUNT(column)` counts non-NULL values in the specified column.

    SELECT COUNT(status)
    FROM orders;

If every order has a status, this may produce the same result as `COUNT(*)`. The two expressions are nevertheless conceptually different.

If a column contains four rows with values:

    10
    20
    NULL
    30

then `COUNT(*)` returns 4 while `COUNT(amount)` returns 3.

### COUNT(DISTINCT column)

`COUNT(DISTINCT column)` counts unique non-NULL values.

    SELECT COUNT(DISTINCT customer_id)
    FROM orders;

This is useful when the question concerns unique entities rather than rows.

For example:

- number of order lines: `COUNT(*)`
- number of customers: `COUNT(DISTINCT customer_id)`
- number of products: `COUNT(DISTINCT product_id)`

These measurements must not be confused.

## SUM

`SUM()` adds numeric values.

    SELECT SUM(quantity)
    FROM orders;

This can calculate total units sold.

Aggregates can also operate on expressions.

For example, the script calculates gross line sales using:

    quantity * unit_price

The total gross sales calculation is therefore:

    SUM(quantity * unit_price)

Discounted revenue can be calculated as:

    SUM(
        quantity * unit_price
        * (1 - discount_percent / 100.0)
    )

This demonstrates an important property of SQL aggregation: the expression being aggregated does not have to be a physical column.

## AVG

`AVG()` calculates the arithmetic mean.

Conceptually:

    AVG(x) = SUM(x) / COUNT(x)

For example:

    SELECT AVG(quantity)
    FROM orders;

`AVG(column)` ignores NULL values.

The meaning of an average depends on what is being averaged.

These are different metrics:

    AVG(quantity)

    AVG(unit_price)

    AVG(quantity * unit_price)

The first measures average quantity per order line. The second measures average unit price per order line. The third measures average gross line value.

A technically correct average can still be inappropriate if it does not represent the intended business metric.

## MIN

`MIN()` returns the smallest non-NULL value.

Examples include:

    SELECT MIN(unit_price)
    FROM orders;

    SELECT MIN(quantity)
    FROM orders;

For date values represented consistently in ISO format, `MIN()` can identify the earliest date.

The script uses:

    MIN(order_date)

to find the first order date.

## MAX

`MAX()` returns the largest non-NULL value.

Examples include:

    SELECT MAX(unit_price)
    FROM orders;

    SELECT MAX(quantity)
    FROM orders;

For ISO-formatted dates, `MAX(order_date)` can identify the latest date.

`MIN()` and `MAX()` are useful for identifying ranges, boundaries, extreme values, and data-quality conditions.

## Multiple aggregates

Several aggregate functions can be used in the same query.

A dashboard query might calculate:

- number of order lines
- number of unique customers
- total units
- total revenue
- average quantity
- minimum quantity
- maximum quantity

For example:

    SELECT
        COUNT(*) AS order_count,
        COUNT(DISTINCT customer_id) AS customer_count,
        SUM(quantity) AS units,
        AVG(quantity) AS average_quantity,
        MIN(quantity) AS minimum_quantity,
        MAX(quantity) AS maximum_quantity
    FROM orders;

This produces a compact summary of the entire matching dataset.

## GROUP BY

`GROUP BY` partitions rows into groups.

For example:

    SELECT
        sales_channel,
        COUNT(*) AS order_count
    FROM orders
    GROUP BY sales_channel;

If the data contains `Online` and `Sales`, SQL creates one group for each channel.

The aggregate function is then evaluated independently inside each group.

Conceptually:

    all rows
        |
        +-- Online rows -> COUNT
        |
        +-- Sales rows  -> COUNT

The result contains one row per sales channel.

## GROUP BY multiple columns

More than one grouping column can be specified.

    GROUP BY sales_channel, status

This creates groups based on combinations of the two columns.

Possible groups include:

    Online + Completed
    Online + Cancelled
    Sales + Completed

The combination of grouping columns defines the result grain.

Similarly:

    GROUP BY customer_id, product_id

produces one result per customer-product combination.

## Result grain

Grain describes what one result row represents.

Examples:

- `orders` table: one row represents one order line
- `GROUP BY customer_id`: one row represents one customer
- `GROUP BY category`: one row represents one product category
- `GROUP BY customer_id, product_id`: one row represents one customer-product combination
- `GROUP BY order_month, sales_channel`: one row represents one month-channel combination

Understanding grain before writing an aggregation query is one of the most important analytical skills in SQL.

Many incorrect reports are caused not by invalid SQL syntax but by aggregating at the wrong grain.

## WHERE and aggregation

`WHERE` filters individual rows before grouping.

For example:

    SELECT
        customer_id,
        COUNT(*) AS completed_orders
    FROM orders
    WHERE status = 'Completed'
    GROUP BY customer_id;

Cancelled rows are removed before the customer groups are formed.

This distinction matters because filtering before aggregation changes which rows contribute to the calculation.

## HAVING

`HAVING` filters groups after aggregation.

For example:

    SELECT
        customer_id,
        COUNT(*) AS order_count
    FROM orders
    GROUP BY customer_id
    HAVING COUNT(*) >= 2;

`COUNT(*)` is an aggregate expression, so it belongs in `HAVING` rather than `WHERE`.

A useful conceptual distinction is:

- `WHERE` asks which rows should participate
- `HAVING` asks which resulting groups should remain

A common logical processing order is:

    FROM
    WHERE
    GROUP BY
    HAVING
    SELECT
    ORDER BY

The exact implementation is database-engine dependent, but this model is useful for understanding query behavior.

## DISTINCT

`DISTINCT` removes duplicate result combinations.

For example:

    SELECT DISTINCT city, segment
    FROM customers;

This returns unique combinations of city and segment.

`GROUP BY` can sometimes produce a similar result:

    SELECT city, segment
    FROM customers
    GROUP BY city, segment;

When no aggregation is required, `DISTINCT` is usually clearer because its purpose is explicitly to remove duplicate combinations.

`GROUP BY` is more appropriate when aggregate calculations are required.

## JOIN and aggregation

Analytical queries frequently combine transaction data with descriptive information.

The script joins:

    orders
    customers
    products

This allows the data to be grouped by attributes such as:

- customer segment
- customer city
- product category
- product name

For example, revenue by product category can be calculated by joining orders to products and grouping by category.

The basic pattern is:

    SELECT
        p.category,
        SUM(o.quantity * o.unit_price) AS revenue
    FROM orders AS o
    JOIN products AS p
        ON o.product_id = p.product_id
    GROUP BY p.category;

The join makes the product category available to the aggregation.

## LEFT JOIN and zero-count groups

An important reporting requirement is often to include categories that have no transactions.

An `INNER JOIN` removes unmatched records.

A `LEFT JOIN` preserves rows from the left table even when no matching record exists on the right.

The script demonstrates products with zero completed orders.

A key detail is:

    COUNT(o.order_id)

rather than:

    COUNT(*)

When a product has no matching order, the joined order columns are NULL.

`COUNT(o.order_id)` therefore returns zero.

`COUNT(*)` counts the preserved LEFT JOIN row and can produce a misleading count of one.

This is an important practical distinction in reporting queries.

## COALESCE

Aggregate results can be NULL when no applicable value exists.

For example, `SUM()` over an empty input can return NULL.

`COALESCE()` can replace NULL with a specified value:

    COALESCE(SUM(quantity), 0)

This is useful when a report requires a numeric zero.

NULL and zero are not equivalent concepts.

NULL may mean:

- unknown
- missing
- unavailable
- not applicable
- no matching records

Zero means that the known numeric value is exactly zero.

The appropriate treatment depends on the meaning of the data.

## NULL behavior

Aggregate functions have specific NULL behavior.

For a column containing:

    10
    20
    NULL
    30

the results are conceptually:

    COUNT(*)      = 4
    COUNT(amount) = 3
    SUM(amount)   = 60
    AVG(amount)   = 20
    MIN(amount)   = 10
    MAX(amount)   = 30

The NULL value is not treated as zero by `SUM()` or `AVG()`.

When all values are NULL, aggregate results such as `SUM`, `AVG`, `MIN`, and `MAX` can be NULL.

This behavior must be considered when designing reports and application logic.

## Empty input

Aggregate queries behave differently when no rows match.

For a query that matches no rows:

    COUNT(*) = 0

while:

    SUM(...)
    AVG(...)
    MIN(...)
    MAX(...)

can return NULL.

This distinction is important for applications that consume SQL results.

An application should not assume that every aggregate result is numeric.

## Conditional aggregation

Conditional aggregation calculates multiple filtered metrics in a single query.

A common pattern is:

    SUM(
        CASE
            WHEN condition THEN 1
            ELSE 0
        END
    )

This can count rows satisfying a condition.

For example:

    SUM(
        CASE
            WHEN status = 'Completed' THEN 1
            ELSE 0
        END
    )

counts completed rows.

Another form calculates conditional totals:

    SUM(
        CASE
            WHEN status = 'Completed'
            THEN quantity * unit_price
            ELSE 0
        END
    )

Conditional aggregation is particularly useful for dashboards because several related metrics can be calculated together.

Modern SQL dialects may also support:

    COUNT(*) FILTER (WHERE condition)

The script demonstrates both the `CASE` approach and the `FILTER` approach. The `CASE` pattern is broadly portable across SQL systems.

## CASE and grouping

`CASE` can transform continuous or detailed values into analytical categories.

The script groups order quantities into bands such as:

- Single item
- 2-4 items
- 5-9 items
- 10+ items

The general structure is:

    CASE
        WHEN condition THEN category
        WHEN condition THEN category
        ELSE category
    END

The resulting expression can be grouped and aggregated.

This technique is useful for:

- customer segmentation
- price bands
- age groups
- transaction-size bands
- risk categories
- profitability classifications

## Aggregating calculated expressions

It is often unnecessary to store every business metric as a separate physical column.

For example, line revenue can be calculated from:

    quantity * unit_price

Discount amount can be calculated from:

    quantity * unit_price * discount_percent / 100.0

Net revenue can then be calculated as:

    quantity * unit_price
    * (1 - discount_percent / 100.0)

The script aggregates these expressions directly.

This keeps derived values close to their underlying data but requires the business definitions to be consistently implemented.

## Revenue and gross profit

The sample product table includes `cost_price`.

The script calculates estimated gross profit using:

    quantity * (
        discounted_unit_price - cost_price
    )

where discounted unit price is:

    unit_price * (1 - discount_percent / 100.0)

The result can then be aggregated by product category.

This demonstrates how aggregation can support practical financial and commercial reporting.

## Weighted averages

A simple average treats every row equally.

That can be inappropriate when rows represent different quantities.

Suppose one order line contains one unit and another contains ten units. Averaging their unit prices gives both rows equal weight.

A weighted average instead uses quantity as the weight:

    SUM(quantity * unit_price) / SUM(quantity)

This measures the average price actually represented by each unit.

Weighted averages are important for:

- average selling price
- portfolio calculations
- inventory analysis
- financial metrics
- survey analysis
- performance measurements

The correct average depends on the analytical question.

## Date aggregation

The script stores dates in ISO format:

    YYYY-MM-DD

It demonstrates grouping by month using the first seven characters of the date.

Conceptually:

    2025-01-20 -> 2025-01

This allows calculations such as monthly:

- order count
- units sold
- revenue

Date aggregation is widely used for:

- monthly revenue
- daily transactions
- quarterly performance
- annual sales
- customer activity
- operational reporting

Date functions are database-specific, so production queries should use the appropriate functions for the target SQL engine.

## Ordering aggregated results

Grouped results can be sorted using `ORDER BY`.

For example:

    ORDER BY total_sales DESC

can place the highest-selling customers first.

Aggregate aliases can often be referenced in `ORDER BY`.

`LIMIT` can then be used to retrieve a top-N result.

For example:

    ORDER BY total_sales DESC
    LIMIT 5

produces the five highest aggregated results.

Always specify `ORDER BY` when result ordering matters. SQL does not guarantee an order simply because the data appears sorted during testing.

## HAVING with multiple conditions

A group can be filtered using several aggregate conditions.

For example:

    HAVING
        COUNT(*) >= 2
        AND SUM(...) > 50000

This can identify customers who have both sufficient transaction volume and sufficient sales.

`HAVING` is therefore useful for segmentation based on aggregate behavior.

## Aggregate subqueries

Sometimes one aggregate result must be compared with another aggregate result.

For example, the script first calculates total sales per customer and then calculates the average of those customer-level totals.

The important conceptual sequence is:

    order-level data
        |
        v
    customer-level sales
        |
        v
    average customer sales
        |
        v
    compare individual customers with the benchmark

This is different from simply calculating the average order value.

The level at which the first aggregation occurs changes the meaning of the second aggregation.

## Common Table Expressions

A Common Table Expression, or CTE, begins with `WITH`.

For example:

    WITH customer_sales AS (
        ...
    )
    SELECT ...
    FROM customer_sales;

CTEs are particularly useful for multi-stage analytical calculations.

The script uses a CTE to:

1. calculate sales per customer,
2. calculate the average customer sales,
3. compare each customer with that average.

CTEs can improve readability and make complex queries easier to reason about.

They do not automatically guarantee better performance. Query optimization depends on the database engine and query structure.

## Percentages and ratios

Aggregated percentages require careful arithmetic.

The script calculates each sales channel's percentage of total sales.

Conceptually:

    channel_sales / total_sales * 100

Decimal arithmetic is deliberately used:

    sales * 100.0 / total

Using a decimal literal can avoid unintended integer division in systems where integer arithmetic would otherwise truncate the result.

Ratios also require protection against division by zero.

A common SQL technique is:

    NULLIF(denominator, 0)

For example:

    numerator / NULLIF(denominator, 0)

If the denominator is zero, `NULLIF` returns NULL rather than zero, preventing a division-by-zero error in systems that raise such errors.

## Window functions versus GROUP BY

`GROUP BY` reduces rows.

For example:

    SELECT
        customer_id,
        SUM(...)
    FROM orders
    GROUP BY customer_id;

This returns one row per customer.

A window function can calculate a customer total while retaining every order row.

Conceptually:

    SUM(...) OVER (
        PARTITION BY customer_id
    )

produces the customer-level aggregate alongside individual order records.

This distinction is essential:

- `GROUP BY` changes the number of rows
- window aggregation generally preserves the original row detail

The script also demonstrates ranking aggregated customer results using `RANK()`.

## Ranking aggregated results

Ranking is often applied after aggregation.

The script first calculates total sales per customer and then uses:

    RANK() OVER (ORDER BY total_sales DESC)

to assign sales rankings.

This creates a two-stage analytical process:

    transactions
        |
        v
    customer totals
        |
        v
    customer ranking

Window functions are especially useful for this type of analysis.

## ROLLUP, CUBE, and GROUPING SETS

Advanced SQL systems may support grouping extensions such as:

- `ROLLUP`
- `CUBE`
- `GROUPING SETS`

These features can produce multiple aggregation levels in one query.

For example, a report might require:

- category and channel detail
- category subtotals
- channel subtotals
- grand total

The exact syntax differs by database system.

SQLite does not support the standard `ROLLUP` syntax used by several other SQL systems, so the script demonstrates the concept using `UNION ALL`.

The underlying analytical idea is more important than the dialect-specific syntax.

## Join duplication risk

One of the most serious aggregation errors occurs when a join unexpectedly multiplies rows.

Suppose an order line matches three rows in another table. After the join, the original order line can appear three times.

If the query then executes:

    SUM(order_value)

the value may be counted three times.

Similarly:

    COUNT(*)

may no longer represent the number of original transactions.

This is why the intended grain must be established before aggregation.

The sample database uses one customer row per customer ID and one product row per product ID, so the primary joins preserve the order-line grain.

In production systems, many-to-many relationships require particular care.

## Data-quality validation with aggregates

Aggregate functions are also useful for data-quality testing.

Examples include:

    COUNT(*) WHERE quantity <= 0

    MIN(unit_price)

    MAX(discount_percent)

    COUNT(DISTINCT customer_id)

These checks can identify:

- invalid quantities
- negative prices
- discounts outside expected ranges
- unexpected duplicate identifiers
- missing values
- unusual extremes

Aggregation therefore supports both reporting and validation.

## Reconciliation

A useful production technique is reconciliation.

For an additive metric, the overall total should normally match the sum of correctly calculated grouped subtotals.

For example:

    overall sales

should match:

    SUM(customer-level sales)

when both calculations use the same business rules and complete dataset.

A difference can indicate:

- duplicate joins
- missing rows
- inconsistent filters
- incorrect grouping
- different business definitions
- NULL handling problems

The script explicitly compares an overall sales result with the sum of customer-level sales.

## Financial precision

The educational database uses SQLite `REAL` values for simplicity.

Floating-point representation is not ideal for exact financial accounting because some decimal values cannot be represented exactly in binary floating-point form.

Production financial systems should normally use an appropriate fixed-precision decimal or numeric type supported by the database.

Python's `Decimal` type is also useful for exact decimal arithmetic in application code.

The correct precision and scale should be defined according to the financial requirements of the system.

## Performance considerations

Aggregation performance depends on several factors:

- number of input rows
- number of groups
- filtering selectivity
- join complexity
- indexes
- sorting requirements
- database memory
- storage layout
- query optimizer
- database engine
- data distribution

The script demonstrates `EXPLAIN QUERY PLAN` in SQLite.

Query plans help determine whether indexes are being used and how the database intends to execute the query.

An index can improve filtering and joining, but indexes also introduce:

- storage overhead
- additional write cost
- maintenance cost
- possible optimizer trade-offs

Indexes should therefore be designed based on actual workload requirements rather than added indiscriminately.

## Indexing for aggregation

An index such as:

    (status, customer_id)

may be useful for a query that filters by `status` and groups by `customer_id`.

The usefulness of such an index depends on:

- data volume
- cardinality
- filter selectivity
- database engine
- query plan
- competing indexes

A small demonstration database cannot reliably predict production performance.

Performance testing should use representative data volumes and realistic queries.

## SQL security

Aggregation itself is not a security vulnerability, but applications frequently construct aggregation queries using user-provided filters.

SQL should never be built by directly concatenating untrusted input into the query string.

The script demonstrates parameterized SQL using:

    WHERE c.city = ?

The value is supplied separately.

This approach allows the database driver to distinguish SQL syntax from data values.

Parameterized queries are a fundamental defense against SQL injection.

Dynamic SQL involving table names, column names, or SQL keywords requires different handling because many database drivers do not allow those identifiers to be supplied as ordinary parameters.

## Common mistakes

### Using WHERE for aggregate conditions

Incorrect conceptual structure:

    WHERE COUNT(*) > 2

Aggregate conditions belong in `HAVING`.

Correct structure:

    GROUP BY customer_id
    HAVING COUNT(*) > 2

### Confusing COUNT(*) with COUNT(column)

`COUNT(*)` counts rows.

`COUNT(column)` counts non-NULL values.

### Forgetting NULL behavior

`NULL` is not automatically equivalent to zero.

`SUM`, `AVG`, `MIN`, and `MAX` ignore NULL values.

### Using the wrong average

A simple average may not represent a weighted business metric.

### Aggregating after an accidental row multiplication

A many-to-many join can inflate totals and counts.

### Using the wrong grouping grain

A query can be valid SQL and still produce an analytically incorrect result.

### Ignoring transaction status

Cancelled, returned, refunded, pending, and completed transactions may need different business treatment.

### Forgetting decimal arithmetic

Ratios and percentages require appropriate numeric types and division behavior.

### Assuming output order

Without `ORDER BY`, row order is not guaranteed.

### Replacing all NULL values with zero

This can hide meaningful missing or unavailable information.

### Using SELECT *

Explicit columns make analytical queries easier to understand and maintain.

## Business interpretation matters

SQL syntax alone does not determine whether an aggregate metric is meaningful.

Consider the phrase "average sales."

It could mean:

- average order value
- average order-line value
- average customer sales
- average daily sales
- average monthly sales
- average unit selling price

These calculations can produce very different results.

The first step in designing an analytical query is therefore to define:

1. what one source row represents,
2. what one output row should represent,
3. which records are included,
4. which metric is being calculated,
5. which dimensions define the groups.

Only then should the SQL aggregation be written.

## Practical aggregation patterns

### Total sales

    SELECT SUM(quantity * unit_price)
    FROM orders;

### Number of orders

    SELECT COUNT(*)
    FROM orders;

### Unique customers

    SELECT COUNT(DISTINCT customer_id)
    FROM orders;

### Average quantity

    SELECT AVG(quantity)
    FROM orders;

### Minimum and maximum price

    SELECT
        MIN(unit_price),
        MAX(unit_price)
    FROM orders;

### Sales by customer

    SELECT
        customer_id,
        SUM(quantity * unit_price) AS sales
    FROM orders
    GROUP BY customer_id;

### Sales by category

    SELECT
        category,
        SUM(revenue) AS sales
    FROM ...
    GROUP BY category;

### Groups above a threshold

    SELECT
        customer_id,
        SUM(quantity * unit_price) AS sales
    FROM orders
    GROUP BY customer_id
    HAVING SUM(quantity * unit_price) > 100000;

### Conditional count

    SELECT
        SUM(
            CASE
                WHEN status = 'Completed' THEN 1
                ELSE 0
            END
        ) AS completed_orders
    FROM orders;

## Production considerations

A production aggregation query should be evaluated from several perspectives.

### Correctness

Verify:

- filters
- joins
- grouping columns
- NULL behavior
- transaction statuses
- business definitions
- rounding rules
- date boundaries

### Performance

Review:

- execution plan
- indexes
- table size
- join cardinality
- grouping cardinality
- repeated calculations
- unnecessary columns

### Maintainability

Prefer:

- explicit columns
- meaningful aliases
- readable CTEs where appropriate
- consistent business definitions
- clear naming
- documented assumptions

### Security

Use:

- parameterized SQL
- least-privilege database accounts
- controlled access to sensitive data
- appropriate auditing
- careful handling of dynamic SQL

### Data quality

Monitor:

- NULL rates
- duplicate identifiers
- invalid numeric ranges
- unexpected categories
- missing dimensions
- reconciliation differences

## SQL dialect differences

The script uses SQLite because it is available through Python's standard library and requires no external database server.

The fundamental concepts are widely applicable to:

- PostgreSQL
- MySQL
- Microsoft SQL Server
- Oracle Database
- Snowflake
- BigQuery
- Databricks SQL
- other relational and analytical SQL systems

Syntax can differ for:

- date manipulation
- decimal types
- `FILTER`
- `ROLLUP`
- `CUBE`
- `GROUPING SETS`
- identifier handling
- type conversion
- optimizer behavior

A query should therefore be tested against the actual database engine used in production.

## Execution

The script requires Python and uses only the standard library.

The main database functionality comes from:

    import sqlite3

The script creates an in-memory database, creates the tables, inserts sample records, executes the aggregation examples, displays results, performs performance inspection, and runs assertions that validate important behaviors.

No external database server or third-party Python package is required.

## Scope of the script

The script progresses from basic aggregation to advanced analytical SQL.

It demonstrates:

- aggregate fundamentals
- `COUNT`
- `SUM`
- `AVG`
- `MIN`
- `MAX`
- multiple aggregates
- `GROUP BY`
- multiple grouping columns
- `WHERE`
- `HAVING`
- `DISTINCT`
- joins
- left joins
- conditional aggregation
- `CASE`
- calculated expressions
- revenue and profit calculations
- subqueries
- CTEs
- ratios and percentages
- weighted averages
- NULL behavior
- `COALESCE`
- date aggregation
- top-N analysis
- calculated grouping
- aggregation grain
- join duplication risks
- window functions
- ranking
- subtotal concepts
- parameterized SQL
- query plans
- indexing
- data-quality checks
- reconciliation
- automated tests
- numeric precision
- production considerations

The examples are intentionally connected to one sales dataset so that the relationship between raw transactional rows, grouped data, and analytical metrics remains visible throughout the script.
