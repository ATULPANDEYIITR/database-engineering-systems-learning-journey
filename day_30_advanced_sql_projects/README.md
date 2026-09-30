# Advanced SQL Project: Analytical SQL System Using Complex Queries

## Project Scope

This project models an analytical reporting system built around transactional business data. The central problem is not storing orders. It is transforming normalized transactional records into reliable analytical metrics without double-counting revenue, mixing cancelled transactions with completed sales, losing zero-activity periods, or confusing historical measurements with predictions.

The project uses three implementations with deliberately different roles:

- The Python implementation executes actual SQL against an in-memory SQLite database.
- The JavaScript implementation models an event-driven analytical reporting service using immutable data transformations and asynchronous report orchestration.
- The C++ implementation presents a strongly typed analytical engine that represents SQL-style aggregation, ranking, cohort analysis, and anomaly detection as a reusable processing pipeline.

The underlying scenario is a technology-commerce business selling software, security, analytics, infrastructure, and support products to customers across multiple regions and customer segments.

## Analytical Data Model

The transactional model contains five principal entities.

`customers` stores the customer dimension. Each customer has a region, segment, and signup date.

`products` stores product attributes such as category, unit cost, and list price.

`orders` represents the transaction header. An order belongs to exactly one customer and has a status of `completed`, `cancelled`, or `refunded`.

`order_items` represents the individual products within an order. Revenue is calculated at this level because quantity, transaction-specific price, and discount are attributes of the item.

`payments` represents payment activity in the Python database. It is deliberately separate from revenue calculation because payment state and commercial order state are not necessarily identical concepts.

`customer_events` represents behavioral activity such as signup, activation, product views, and support contacts.

This separation creates a normalized transactional structure from which analytical views can be constructed.

## Revenue Grain and Double-Counting

The most important analytical design decision is the grain of the revenue calculation.

Revenue is calculated from an order item:

`quantity × unit_price × (1 - discount_rate)`

An order can contain several order items, so joining `orders` to `order_items` produces multiple rows per order. Counting orders after that join without using `COUNT(DISTINCT order_id)` can inflate order counts.

The Python implementation handles this distinction explicitly. Revenue is aggregated over order-item rows, while completed order counts use distinct order identifiers.

The order status is also applied before revenue aggregation. Cancelled orders therefore do not contribute to completed-sales revenue.

Refunds are retained as transaction states rather than silently deleted. This preserves the distinction between the existence of a transaction and its analytical treatment.

## Foundational Analytical SQL

The Python implementation starts with direct SQL aggregations.

Monthly revenue groups completed order items by `substr(order_date, 1, 7)`. Category profitability joins orders, order items, and products so that revenue and product cost can be compared at the same item grain.

Gross margin is calculated as:

`quantity × ((unit_price × (1 - discount_rate)) - unit_cost)`

The category query then calculates margin percentage using `NULLIF` to prevent division by zero.

The customer summary demonstrates a different join requirement. Customers are left-joined to orders and order items so that customers without completed revenue can still appear in the analytical population.

This distinction between inner and outer joins matters in analytical systems. An inner join answers a question about entities that have matching activity. A left join can preserve the complete dimension population.

## Common Table Expressions

Common table expressions, or CTEs, are used in the Python implementation to divide complex analytical logic into named stages.

The customer-segment analysis first creates `customer_revenue`. This produces one row per customer containing observed revenue.

A second CTE, `segment_stats`, aggregates those customer-level rows into segment-level metrics.

The final query then calculates each segment's share of total revenue using a window expression.

This structure is preferable to forcing all calculations into one large aggregation because each CTE establishes a clear analytical grain.

A CTE does not automatically mean that the database materializes the intermediate result. Query optimizers may inline or transform CTEs depending on the database engine and query. CTEs should therefore be treated primarily as a query-organization mechanism unless the specific database documents materialization behavior.

## Window Functions

Window functions calculate values across related rows without collapsing those rows into a single aggregate row.

The project uses several important window patterns.

`RANK() OVER (ORDER BY revenue DESC)` produces global customer rankings while retaining each customer's row.

`DENSE_RANK()` is used for regional ranking.

`LAG()` retrieves the previous month's revenue and enables month-over-month growth calculations.

A windowed `AVG()` creates a three-period rolling average.

A windowed `SUM()` creates cumulative revenue.

The distinction between `GROUP BY` and a window function is fundamental. `GROUP BY` reduces multiple rows into groups. A window function calculates across a related set while preserving the current row.

## Rolling Metrics

The monthly report calculates three related measures:

- Previous-month revenue comes from `LAG(revenue)`.
- Month-over-month growth compares the current revenue with the previous value.
- The three-month rolling average uses a window frame covering the current row and two preceding rows.
- Cumulative revenue uses a frame beginning at the first available row.

The first month has no previous month, so its growth value is naturally `NULL` in the SQL expression rather than being treated as a genuine zero-growth observation.

This is an important analytical distinction. Missing comparison data is not necessarily equivalent to a measured value of zero.

## RFM Segmentation

The Python implementation creates an RFM-style customer analysis.

Recency represents how recently a customer completed an order.

Frequency represents the number of completed orders.

Monetary value represents observed completed-order revenue.

The query uses `NTILE(4)` to divide customers into four approximate ordered groups for each metric. The resulting scores are combined into an RFM score.

The segmentation rules are then expressed as SQL `CASE` conditions:

- customers strong on recency, frequency, and monetary value become `high-value-active`;
- recently active customers with meaningful frequency become `active-growth`;
- customers with lower recency but high monetary value become `valuable-at-risk`;
- remaining customers are classified as `standard`.

These are descriptive business rules, not machine-learning predictions.

## Cohort Analysis and Retention

Cohort analysis answers a different question from ordinary monthly revenue reporting.

The first completed purchase month becomes the customer's cohort month. Subsequent completed purchase months represent activity.

The Python query constructs:

`first_purchase`

This identifies the first completed-order month for each customer.

`activity`

This creates distinct customer-month activity records so multiple orders in the same month do not inflate retention.

`cohort_activity`

This counts active customers for each cohort and activity-month combination.

`cohort_size`

This establishes the original size of each cohort.

Retention is then:

`active customers in activity month / original cohort customers × 100`

Because activity is deduplicated at the customer-month level, a customer placing three orders during a month still counts as one retained active customer.

## Recursive CTE Calendar Generation

The Python implementation also demonstrates a recursive CTE.

The `months` CTE generates a sequence from January through June 2024. Revenue is then left-joined onto that generated calendar.

This solves a common reporting problem: aggregation queries naturally omit periods for which no fact rows exist.

A calendar series provides the missing analytical dimension, allowing a report to show zero rather than silently removing the month.

The same pattern can be extended to days, weeks, fiscal periods, subscription ages, organizational hierarchies, or other sequential dimensions.

Recursive CTEs should be bounded carefully. An unrestricted recursive query can produce excessive rows or fail because of database recursion limits.

## Pareto Analysis

The product analysis ranks products by revenue and calculates cumulative revenue contribution.

The window expression:

`SUM(revenue) OVER (ORDER BY revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`

creates the cumulative revenue sequence.

Dividing cumulative revenue by total revenue produces cumulative contribution percentage.

This allows the report to distinguish products that collectively account for the first approximately 80 percent of revenue from products forming the longer tail.

The 80 percent threshold is an analytical classification rule rather than a universal law. The important SQL mechanism is the ordered cumulative window calculation.

## Anomaly Detection

The Python implementation calculates an order-value distribution and identifies unusually large orders.

SQLite does not provide the same standard deviation aggregate available in some analytical database systems, so the program derives population variance from:

`AVG(x²) - AVG(x)²`

The standard deviation is the square root of that variance.

An order is classified as a potential anomaly when its value exceeds the mean by more than two population standard deviations.

This is a deliberately simple statistical screening rule. It should not be interpreted as proof that an order is fraudulent or erroneous.

Real production anomaly systems often account for seasonality, customer-specific baselines, product mix, currency, geography, and transaction volume before flagging an event.

## Observed Customer Lifetime Value

The project calculates historical customer financial value from completed transactions.

Revenue and gross margin are aggregated by customer. Margin per order is then derived from those observed values.

The Python implementation deliberately calls this `Observed Customer Lifetime Value`. It does not attempt to forecast future purchases.

A predictive lifetime-value model would require assumptions about future retention, expected purchase frequency, expected margin, discounting, and potentially customer-level covariates. Mixing those assumptions into a historical SQL metric would make the metric harder to interpret.

## JavaScript Analytical Service

The JavaScript implementation uses a different architecture.

Instead of executing SQL directly, it models an analytical service whose normalized records are transformed through reusable functions.

`groupBy()` provides reusable grouping behavior.

`revenueForItem()` centralizes the revenue formula.

`marginForItem()` joins item data with the product index.

`customerRevenue()` produces a customer-level analytical projection.

`rankCustomers()` adds ranking and revenue contribution.

`calculateMonthlyWindows()` models the semantics of `LAG`, rolling averages, and cumulative sums.

`productPareto()` creates an ordered cumulative contribution analysis.

`cohortRetention()` constructs first-purchase cohorts and distinct monthly activity.

`rfmSegmentation()` models multi-dimensional customer scoring.

The code uses `Map` for indexed access. This avoids repeatedly scanning the entire customer or product array when an order item needs its related entity.

## Event-Driven Report Execution

`AnalyticalReportService` extends Node.js `EventEmitter`.

A report emits `reportStarted` before execution and `reportCompleted` after successful execution. Failures emit `reportFailed`.

This represents an important application-layer distinction from SQL itself. SQL calculates the analytical result, while an application service can manage orchestration, observability, scheduling, logging, and error propagation around those queries.

The service also uses `Promise.all()` to execute independent reports concurrently from the application's perspective.

A production database connection pool would determine whether such concurrency is actually beneficial. Unlimited parallel reporting against the same database can increase contention rather than improve performance.

## C++ Analytical Case Study

The C++ implementation models the same business scenario as a strongly typed analytical engine.

The central class is `AnalyticsEngine`.

It stores normalized vectors for customers, products, orders, and order items. It then creates hash indexes using `std::unordered_map`.

These indexes represent the practical purpose of indexed joins: an order can locate its customer without scanning the entire customer collection, and an order item can locate its product without scanning all products.

The constructor establishes the pipeline:

- seed data;
- build lookup indexes;
- validate relationships and values.

This mirrors an analytical system in which data-quality validation occurs before derived metrics are published.

## C++ Customer Aggregation

`customerMetrics()` constructs one analytical row per customer.

It processes completed order items, joins each item to its order and customer, accumulates revenue and margin, and separately counts unique customer-order pairs.

The separate order-count set is important because an order can contain multiple items. Counting items would not be equivalent to counting orders.

The final result is sorted by revenue.

The algorithm is approximately linear in the number of order items for the main aggregation, plus the cost of maintaining the unique customer-order set.

## C++ Ranking

`rankCustomers()` applies SQL-like ranking semantics after customer aggregation.

Customers are sorted by descending revenue. The implementation assigns the same rank to equal revenue values, matching the conceptual behavior of SQL `RANK()`.

Revenue contribution is calculated against total customer revenue.

This demonstrates an important architecture principle: ranking should normally operate on an already established analytical grain. Ranking raw order-item rows would answer a different question.

## C++ Pareto Calculation

`productPareto()` aggregates completed order-item revenue by product, sorts products in descending revenue order, then maintains a cumulative revenue value.

The cumulative percentage is calculated against total product revenue.

The primary cost is the sort:

`O(P log P)`

where `P` is the number of products with observed revenue.

The aggregation itself is approximately `O(I)`, where `I` is the number of order items.

For very large datasets, a database engine may perform this work more efficiently by combining indexes, sorting, parallel execution, columnar storage, and query planning.

## C++ Cohort Retention

The C++ cohort implementation first records each customer's earliest completed order.

It then stores distinct activity months in a `std::set` per customer.

The distinct-month representation prevents multiple orders from inflating the number of retained customers.

Cohort customers are grouped by first-purchase month. Activity counts are then calculated against each cohort.

This is the same analytical concept as the SQL cohort query, but the implementation exposes the underlying data structures that a query engine conceptually has to manage.

## C++ Anomaly Detection

The C++ implementation aggregates completed revenue at order level and calculates the population mean and standard deviation.

For each order, the z-score is:

`(order_value - mean) / standard_deviation`

Orders above a z-score of 2 are marked as potential anomalies.

The implementation explicitly handles the zero-standard-deviation case to avoid division by zero.

This demonstrates a broader analytical engineering principle: statistical calculations require explicit handling of degenerate datasets.

## Data Quality Rules

Analytical correctness depends on data quality before query complexity becomes relevant.

The Python database uses foreign-key constraints for entity relationships.

The C++ engine validates duplicate identifiers, missing references, invalid statuses, negative quantities, invalid discounts, and invalid pricing.

Important production checks include:

- orphan fact records;
- duplicate business keys;
- missing dimension records;
- invalid dates;
- impossible monetary values;
- duplicated order-item combinations;
- unexpected status values;
- incomplete transactional records.

A technically sophisticated query over invalid source data still produces an unreliable result.

## NULL and Missing-Data Semantics

Analytical SQL must distinguish among zero, missing, and undefined values.

`COALESCE` converts a missing aggregate result into a defined fallback value when that behavior is intended.

`NULLIF` protects division operations from zero denominators.

`LAG` naturally returns `NULL` when there is no previous row.

A left join preserves dimension records even when matching fact rows are absent.

These behaviors should be chosen deliberately. Replacing every `NULL` with zero can destroy information about whether a value was actually measured.

## Query Grain

A reliable analytical query should establish its grain before aggregation.

Examples in this project include:

- order-item grain for revenue;
- order grain for order-value anomaly detection;
- customer grain for customer revenue;
- customer-month grain for retention activity;
- cohort-month/activity-month grain for retention percentages;
- product grain for Pareto analysis.

Many SQL errors occur because a query combines multiple grains without accounting for their multiplicative effect.

For example, joining orders to both order items and payment records can multiply rows when an order has multiple items and multiple payments. The correct solution is often to aggregate each fact source separately before joining the resulting one-row-per-order datasets.

## Performance Considerations

Complex analytical SQL can become expensive because joins, grouping, sorting, and window functions can require substantial memory and CPU.

The Python schema creates indexes on:

`orders(customer_id, order_date)`

`orders(order_date, status)`

`order_items(product_id)`

`customer_events(customer_id, event_date)`

Indexes should match real access patterns rather than being added indiscriminately. Indexes improve some reads but add storage and write-maintenance cost.

Window functions that require ordering may introduce sorting work. Large `ORDER BY` operations should be examined with the database's execution-plan tooling.

The Python program uses `EXPLAIN QUERY PLAN` to inspect how SQLite approaches an indexed customer/date lookup.

For production analytical systems, query plans should be evaluated using representative data volumes rather than a small development dataset.

## Security Considerations

Analytical queries can be exposed to the same injection risks as transactional queries.

The Python implementation demonstrates parameter binding for the regional filter rather than concatenating user input into SQL text.

The dangerous pattern is conceptually:

`WHERE region = '` + userInput + `'`

The safe pattern is a parameterized predicate such as `WHERE region = ?` with the value supplied separately.

Production analytical systems should also enforce database permissions. Reporting identities generally should not receive unnecessary write, schema-management, or administrative privileges.

Sensitive customer attributes should be minimized in analytical outputs, and access to exported reports should follow the organization's authorization requirements.

## Transaction and Derived-Data Safety

The Python implementation creates a temporary analytical staging table inside a transaction.

The staging process validates that rows were actually produced before the transaction completes.

The underlying principle is useful when analytical pipelines persist derived tables or summary snapshots: partial transformations should not become visible as if they were complete datasets.

For large production pipelines, this idea can be extended through staging schemas, atomic table replacement, partition-level processing, or database-specific transactional strategies.

## Common Analytical Failure Modes

### Double-counting after joins

Joining two one-to-many relationships at once can multiply fact rows. Aggregating each source to a compatible grain before joining prevents this.

### Counting rows instead of business entities

`COUNT(*)` over order-item rows does not equal the number of orders. Distinct entity identifiers or pre-aggregation are required when the analytical question is about orders or customers.

### Treating cancelled transactions as sales

Transaction status must be incorporated into the metric definition rather than filtered only in a final presentation layer.

### Losing zero-activity periods

A direct aggregation only returns periods represented in the fact table. Calendar CTEs or date dimensions preserve periods with no activity.

### Incorrect retention counts

Retention should normally count distinct active customers per cohort-period, not raw order volume.

### Dividing by zero

Ratios should protect denominators with appropriate conditional logic or `NULLIF`.

### Confusing missing with zero

No prior month is different from a month whose measured revenue is zero.

### Ranking before aggregation

Ranking order items does not rank customers. The analytical grain must be established before ranking.

### Assuming a CTE is always materialized

CTEs improve query structure but do not universally imply physical materialization.

### Treating anomaly flags as proof

A statistical threshold identifies observations worth inspecting. It does not establish why the observation occurred.

## Practical SQL Architecture

A mature analytical query often follows a layered structure:

`raw transactional tables`

→ `validated fact rows`

→ `grain-specific CTE`

→ `aggregated metrics`

→ `window calculations`

→ `business classifications`

→ `final analytical output`

The Python implementation directly demonstrates this style with CTE chains.

The JavaScript implementation exposes the same conceptual layers as application functions.

The C++ implementation expresses them as typed processing stages.

The three approaches therefore show the same analytical principles from database, application, and systems-programming perspectives without requiring the implementations to be identical.

## Execution

The Python program requires only Python 3 and the standard-library `sqlite3` module.

Run it with:

`python advanced_sql_project.py`

The JavaScript program requires a Node.js runtime.

Run it with:

`node advanced_sql_project.js`

The C++ program requires a C++17-compatible compiler.

A typical compilation command is:

`g++ -std=c++17 -O2 advanced_sql_project.cpp -o advanced_sql_project`

Then run:

`./advanced_sql_project`

On Windows with a compatible compiler, the generated executable can be run as:

`advanced_sql_project.exe`

No external database server is required for the Python implementation because SQLite is created in memory. The JavaScript and C++ implementations intentionally keep their analytical datasets in process memory to demonstrate their respective programming models.

## Technical Relationships

The project separates several concepts that are often incorrectly treated as one operation.

A transaction is stored at an operational grain.

An analytical query establishes the grain relevant to a business question.

Aggregation converts detailed records into that grain.

CTEs provide named intermediate query stages.

Window functions calculate contextual values without collapsing the result set.

Ranking orders already-established analytical entities.

Cohort analysis introduces a temporal grouping based on an entity's first observed event.

Retention measures subsequent activity relative to the cohort population.

Pareto analysis orders contributions and accumulates them.

Anomaly detection applies a statistical rule to an established metric.

The resulting analytical system is therefore not simply a collection of complex SQL expressions. It is a sequence of deliberate transformations in which data grain, filtering, joins, aggregation, temporal logic, and statistical interpretation each have a specific role.
