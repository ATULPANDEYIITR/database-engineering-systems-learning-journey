# CASE Expressions in SQL

## Topic

**CASE Expressions | Conditional transformations and business logic in SQL**

CASE is an SQL expression used to transform conditions into values. It allows a query to classify records, calculate conditional values, create business categories, perform conditional aggregation, control custom sorting, validate data, and express decision rules directly inside SQL.

The fundamental structure is:

`CASE ... WHEN ... THEN ... ELSE ... END`

A CASE expression is not a separate procedural program. It is an expression that produces a value. That distinction is important because the resulting value can be used in many SQL clauses and expressions.

The three implementations in this repository approach the topic from different perspectives:

- The Python implementation uses SQLite to execute real SQL CASE expressions.
- The JavaScript implementation demonstrates equivalent application-layer logic and shows the corresponding SQL statements.
- The C++ implementation develops an industry-style transaction and customer classification system using CASE-style rule functions, aggregation, validation, ordering, and testing.

---

## Fundamental concept

A CASE expression answers a question of the form:

> Given the current row and a set of conditions, which value should this row produce?

For example:

`CASE WHEN amount >= 10000 THEN 'Large' ELSE 'Regular' END`

For each row, SQL evaluates the condition and returns one of the specified results.

CASE is particularly useful because SQL normally processes sets of rows, while business requirements frequently describe categories and decisions:

- small, medium, or large order
- low, medium, or high risk
- paid, pending, refunded, or cancelled
- active, inactive, or prospective customer
- express, standard, or delayed shipment
- eligible or ineligible
- domestic or international
- profitable or unprofitable
- missing, valid, or invalid data

CASE provides a direct mechanism for translating these rules into query results.

---

## CASE terminology

### CASE expression

The complete conditional expression.

`CASE WHEN amount >= 5000 THEN 'Large' ELSE 'Regular' END`

### WHEN

Defines a condition or comparison that SQL evaluates.

### THEN

Defines the value returned when its associated WHEN condition matches.

### ELSE

Defines the fallback value when no WHEN condition matches.

### END

Terminates the CASE expression.

### Simple CASE

Compares one expression against several possible values.

`CASE payment_status WHEN 'paid' THEN 'Complete' WHEN 'pending' THEN 'Waiting' ELSE 'Other' END`

### Searched CASE

Tests independent Boolean conditions.

`CASE WHEN amount < 1000 THEN 'Small' WHEN amount < 5000 THEN 'Medium' ELSE 'Large' END`

### Condition

A logical expression evaluated as true, false, or, in SQL's three-valued logic, unknown.

### Result expression

The value returned by THEN or ELSE.

---

## Simple CASE

Simple CASE has this general structure:

`CASE expression WHEN value1 THEN result1 WHEN value2 THEN result2 ELSE result END`

The expression following CASE is compared with each WHEN value.

The Python implementation demonstrates this with payment status:

`CASE payment_status WHEN 'paid' THEN 'Payment complete' WHEN 'pending' THEN 'Awaiting payment' WHEN 'cancelled' THEN 'Order cancelled' WHEN 'refunded' THEN 'Money returned' ELSE 'Unknown status' END`

If `payment_status` is `paid`, the result is `Payment complete`.

If it is `pending`, the result is `Awaiting payment`.

If none of the listed values match, the ELSE result is returned.

Simple CASE is particularly suitable for discrete categories such as:

- status codes
- country codes
- product types
- transaction states
- department codes
- membership levels

---

## Searched CASE

Searched CASE has this structure:

`CASE WHEN condition1 THEN result1 WHEN condition2 THEN result2 ELSE result END`

Unlike simple CASE, each WHEN contains a condition.

For order classification:

`CASE WHEN amount < 1000 THEN 'Small' WHEN amount < 5000 THEN 'Medium' WHEN amount < 20000 THEN 'Large' ELSE 'Enterprise' END`

This form is more flexible because conditions can include:

- comparisons
- ranges
- AND
- OR
- IS NULL
- IS NOT NULL
- IN
- calculations
- combinations of multiple columns

Searched CASE is usually the appropriate form for numerical ranges and multi-column business rules.

---

## Rule ordering

CASE rules are ordered.

Consider:

`CASE WHEN amount >= 1000 THEN 'At least 1,000' WHEN amount >= 5000 THEN 'At least 5,000' ELSE 'Below 1,000' END`

An amount of 8000 satisfies `amount >= 1000`. The first rule therefore determines the result, so the 5000 condition does not provide the intended classification.

A more appropriate ordering is:

`CASE WHEN amount >= 5000 THEN 'At least 5,000' WHEN amount >= 1000 THEN 'At least 1,000' ELSE 'Below 1,000' END`

This is one of the most important CASE design principles.

When conditions overlap, the rule order is part of the business logic.

---

## ELSE and unmatched rows

If no WHEN condition matches and ELSE exists, SQL returns the ELSE result.

If ELSE is omitted, the result is normally NULL when no condition matches.

For example:

`CASE WHEN payment_status = 'paid' THEN 'Recognized' END`

A pending order does not satisfy the condition, so the result becomes NULL.

An explicit ELSE is often preferable when every row should have a known classification.

For example:

`CASE WHEN payment_status = 'paid' THEN 'Recognized' ELSE 'Unrecognized' END`

The appropriate choice depends on whether an unmatched record should represent a genuine missing value or a defined fallback category.

---

## NULL handling

NULL represents missing or unknown information in SQL. It is not equivalent to zero, an empty string, or the text `NULL`.

The incorrect pattern is:

`annual_income = NULL`

The appropriate test is:

`annual_income IS NULL`

Similarly:

`annual_income IS NOT NULL`

should be used to identify values that are present.

SQL uses three-valued logic:

- TRUE
- FALSE
- UNKNOWN

Comparisons involving NULL commonly produce UNKNOWN rather than TRUE.

The Python implementation contains examples involving missing annual income, missing credit scores, and missing country information.

The C++ implementation models similar situations with `std::optional`, which allows a field to contain either a value or no value.

---

## CASE with numerical ranges

A frequent reporting requirement is converting continuous numerical values into categories.

Example:

`CASE WHEN amount < 1000 THEN 'Small' WHEN amount < 5000 THEN 'Medium' WHEN amount < 20000 THEN 'Large' ELSE 'Enterprise' END`

This creates four ranges:

| Amount | Category |
|---:|---|
| Less than 1,000 | Small |
| 1,000 to less than 5,000 | Medium |
| 5,000 to less than 20,000 | Large |
| 20,000 or more | Enterprise |

The exact boundary rules matter.

For example, 5,000 belongs to Large because the first condition that applies is `amount < 20000` after the earlier `amount < 5000` condition has failed.

Boundary values should therefore be explicitly tested.

---

## CASE in SELECT

One of the most common uses of CASE is creating a derived column.

Example:

`SELECT order_id, amount, CASE WHEN amount < 1000 THEN 'Small' WHEN amount < 5000 THEN 'Medium' ELSE 'Large' END AS order_size FROM orders;`

The original database column is not modified.

Instead, the query creates a calculated result named `order_size`.

This is useful for:

- reports
- dashboards
- analytics
- exports
- data classification
- business intelligence
- customer segmentation

The Python implementation executes these queries against SQLite and prints their actual results.

---

## CASE in calculations

CASE can return numbers.

Example:

`CASE WHEN amount >= 50000 THEN amount * 0.005 WHEN amount >= 10000 THEN amount * 0.01 ELSE amount * 0.02 END`

The expression calculates a service fee based on transaction size.

CASE can therefore implement pricing and financial rules such as:

- discounts
- fees
- commissions
- taxes
- rebates
- penalties
- interest adjustments
- shipping charges

For financial applications, floating-point arithmetic may not provide the required decimal precision. The Python and C++ examples use ordinary numeric types for educational purposes, while production financial systems should select numeric types and database data types appropriate for their precision requirements.

---

## CASE in WHERE

CASE can technically be used in a WHERE condition.

For example:

`WHERE CASE WHEN payment_status = 'paid' AND amount >= 5000 THEN 1 ELSE 0 END = 1`

This works, but a direct predicate is often clearer:

`WHERE payment_status = 'paid' AND amount >= 5000`

The second form expresses the filtering requirement directly.

This distinction is important for both readability and query optimization.

CASE is especially natural when the query needs to produce a derived value. A direct predicate is often preferable when the sole objective is filtering rows.

---

## CASE in ORDER BY

CASE is extremely useful for custom business ordering.

Alphabetical sorting does not always represent business priority.

For example:

`ORDER BY CASE payment_status WHEN 'pending' THEN 1 WHEN 'paid' THEN 2 WHEN 'refunded' THEN 3 WHEN 'cancelled' THEN 4 ELSE 5 END`

This creates a custom order:

1. Pending
2. Paid
3. Refunded
4. Cancelled
5. Other

The numeric values do not have to be displayed. They are simply used to control sorting.

The Python, JavaScript, and C++ implementations all demonstrate this concept.

---

## CASE in GROUP BY

CASE can convert raw numerical data into groups.

Example:

`SELECT CASE WHEN amount < 1000 THEN 'Small' WHEN amount < 5000 THEN 'Medium' ELSE 'Large' END AS category, COUNT(*) AS order_count FROM orders GROUP BY CASE WHEN amount < 1000 THEN 'Small' WHEN amount < 5000 THEN 'Medium' ELSE 'Large' END;`

This transforms individual transaction values into analytical categories.

Common applications include:

- revenue bands
- age groups
- salary ranges
- customer tenure
- credit score bands
- order-size buckets
- latency categories
- inventory levels

The resulting groups can then be counted, summed, averaged, or otherwise analyzed.

---

## Conditional aggregation

Conditional aggregation is one of the most important advanced uses of CASE.

A conditional count can be written as:

`SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END)`

This counts rows satisfying the condition.

A conditional total can be written as:

`SUM(CASE WHEN payment_status = 'paid' THEN amount ELSE 0 END)`

This adds only amounts from paid transactions.

A report can therefore calculate multiple business metrics in a single query:

`SELECT COUNT(*) AS total_orders, SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END) AS paid_orders, SUM(CASE WHEN payment_status = 'pending' THEN 1 ELSE 0 END) AS pending_orders, SUM(CASE WHEN payment_status = 'paid' THEN amount ELSE 0 END) AS paid_revenue FROM orders;`

This pattern is widely applicable to reporting systems.

---

## Conditional counting

There are several ways to count conditional records.

One common pattern is:

`SUM(CASE WHEN condition THEN 1 ELSE 0 END)`

Another pattern is:

`COUNT(CASE WHEN condition THEN 1 END)`

The first pattern explicitly supplies zero for nonmatching rows.

The second pattern relies on COUNT ignoring NULL values.

Both patterns can be valid, but the explicit `SUM` form is often easy to understand when teaching conditional aggregation.

---

## Conditional pivoting

Some database systems provide dedicated pivot functionality, while others do not.

CASE plus aggregation can reproduce many pivot-style reports.

Example:

`SUM(CASE WHEN payment_status = 'paid' THEN amount ELSE 0 END) AS paid_amount`

`SUM(CASE WHEN payment_status = 'pending' THEN amount ELSE 0 END) AS pending_amount`

`SUM(CASE WHEN payment_status = 'refunded' THEN amount ELSE 0 END) AS refunded_amount`

This can transform status values from rows into separate calculated columns.

The Python implementation demonstrates this pattern against the orders table.

The C++ implementation constructs a similar payment pivot with standard-library data structures.

---

## CASE in UPDATE

CASE can also be used when modifying stored data.

Example:

`UPDATE customers SET customer_status = CASE WHEN customer_status = 'prospect' AND signup_days_ago <= 30 THEN 'new_prospect' WHEN customer_status = 'inactive' AND signup_days_ago > 365 THEN 'dormant' ELSE customer_status END;`

This allows different rows to receive different update values.

CASE in UPDATE should be used carefully because it changes persistent data.

Important production practices include:

- test the SELECT version first
- verify the WHERE clause
- use a transaction when appropriate
- validate the affected row count
- preserve auditability for important changes
- test boundary conditions

The Python implementation creates a demonstration copy before applying an UPDATE.

---

## CASE and common SQL functions

CASE is frequently combined with other SQL functions.

One example is `COALESCE`.

`COALESCE` returns the first non-NULL expression.

Example:

`COALESCE(annual_income, 0)`

can convert a missing income into zero for a specific calculation.

CASE can then classify the resulting value:

`CASE WHEN COALESCE(annual_income, 0) = 0 THEN 'Income unavailable' WHEN annual_income < 50000 THEN 'Low' ELSE 'High' END`

The two constructs solve different problems:

- COALESCE handles fallback values for NULL expressions.
- CASE applies explicit conditional business rules.

---

## Nested CASE

CASE expressions can contain other CASE expressions.

Example:

`CASE WHEN credit_score >= 700 THEN CASE WHEN annual_income >= 100000 THEN 'High-score/high-income' ELSE 'High-score/lower-income' END ELSE 'Lower-score' END`

Nested CASE can represent multi-stage classification.

It should not be used indiscriminately.

Deep nesting can create:

- difficult-to-read SQL
- duplicated rules
- difficult testing
- difficult auditing
- maintenance problems

When a rule becomes large, a CTE, view, generated column, rule table, or application-layer design may be easier to maintain.

The appropriate solution depends on the ownership and lifecycle of the business rule.

---

## CASE with CTEs

A common advanced design is to calculate one classification in a Common Table Expression and use that result later.

Conceptually:

`WITH customer_rules AS (...) SELECT ... FROM customer_rules`

This can make a large query easier to understand.

For example, the first CTE can calculate:

`risk_level`

The outer query can then calculate:

`recommended_process`

based on that risk level and other aggregated information.

The Python implementation demonstrates this approach with a customer risk report.

This creates a logical sequence:

1. classify customer
2. aggregate paid orders
3. combine the results
4. classify the required operational action
5. sort the final report

---

## CASE with window functions

CASE can be combined with window functions.

A window function provides context across related rows while CASE transforms the resulting information.

For example, a query can calculate total customer revenue with:

`SUM(amount) OVER (PARTITION BY customer_id)`

and then classify an order according to its contribution to that total.

This allows SQL to answer questions such as:

- Is this transaction a major contribution from the customer?
- Does this employee represent a high share of departmental revenue?
- Is this event unusually large compared with the customer's normal activity?

The Python implementation contains an example combining CASE with a window function.

---

## Business-rule example

The project models a customer and transaction system.

Customers have:

- customer ID
- name
- country
- annual income
- credit score
- account status

Orders have:

- order ID
- customer ID
- order date
- amount
- payment status
- shipping days
- discount rate

The system can classify customers by risk:

`CASE WHEN credit_score IS NULL OR annual_income IS NULL THEN 'UNKNOWN' WHEN credit_score < 600 THEN 'HIGH' WHEN credit_score < 700 THEN 'MEDIUM' ELSE 'LOW' END`

Transactions can be classified by size:

`CASE WHEN amount < 1000 THEN 'Small' WHEN amount < 5000 THEN 'Medium' WHEN amount < 20000 THEN 'Large' ELSE 'Enterprise' END`

The same transaction can be classified by shipping performance:

`CASE WHEN shipping_days = 0 THEN 'Not shipped' WHEN shipping_days <= 3 THEN 'Express' WHEN shipping_days <= 7 THEN 'Standard' ELSE 'Delayed' END`

These are separate dimensions. A transaction can simultaneously be:

- Large
- Delayed
- Paid
- Medium risk

This illustrates why CASE is useful for multidimensional reporting.

---

## Python implementation

The Python script uses SQLite through Python's built-in `sqlite3` module.

No external package is required.

The database contains three tables:

- `customers`
- `orders`
- `employees`

The Python implementation executes actual SQL rather than merely printing SQL syntax.

### Schema

The `customers` table contains customer information such as income, credit score, country, and status.

The `orders` table contains financial and operational transaction information.

The `employees` table provides a second business context for performance and compensation classification.

### Beginner examples

The script first demonstrates simple CASE using payment status.

It then demonstrates searched CASE using numerical order amounts.

This establishes the distinction between comparing one expression against several values and evaluating independent conditions.

### NULL examples

The script explicitly handles missing income, missing credit score, and missing country.

This is important because a CASE rule that ignores NULL values can produce classifications that are different from the intended business meaning.

### Business segmentation

The customer segmentation rules combine annual income and credit score.

This demonstrates that CASE conditions can reference multiple columns and use Boolean operators.

### Conditional calculations

The script calculates:

- discount amount
- net amount
- shipping category
- service fee

This demonstrates that THEN and ELSE can return calculated numeric expressions.

### Filtering and sorting

The script shows CASE in WHERE and explains why a direct predicate can sometimes be preferable.

It also demonstrates CASE in ORDER BY for business-priority sorting.

### Conditional aggregation

The script calculates:

- total orders
- paid orders
- pending orders
- cancelled orders
- refunded orders
- paid revenue
- pending revenue

This demonstrates the important pattern:

`SUM(CASE WHEN condition THEN value ELSE 0 END)`

### Grouping and pivoting

The script creates revenue buckets and a CASE-based pivot-style report.

These techniques are particularly useful for analytical SQL.

### Data modification

The UPDATE example uses a copied table so that the educational demonstration does not modify the original customer dataset.

### Advanced query

The CTE-based report demonstrates how CASE-derived categories can become inputs to subsequent business rules.

### Testing

The Python program contains explicit boundary tests for:

- 0
- 999.99
- 1000
- 4999.99
- 5000
- 19999.99
- 20000

Boundary testing is essential for range-based CASE expressions.

---

## JavaScript implementation

The JavaScript implementation approaches the subject from the application layer.

It does not require an external npm database package. Instead, it demonstrates the business rules in JavaScript while showing the corresponding SQL CASE expressions.

This makes the distinction between database-side and application-side transformations clear.

### Simple CASE comparison

JavaScript uses conditional logic to reproduce the mapping from payment status to a human-readable description.

The SQL equivalent is a simple CASE expression.

### Searched CASE comparison

JavaScript `if` conditions reproduce the numerical range classification used by SQL searched CASE.

This illustrates the conceptual similarity between the two forms.

### NULL handling

JavaScript explicitly checks for `null` and `undefined`.

This is not identical to SQL's three-valued logic, but it provides a useful application-layer comparison.

The important lesson is that missing data must be handled intentionally in both environments.

### Conditional calculations

The JavaScript implementation calculates service fees using ordered conditions.

This corresponds directly to a numeric CASE expression in SQL.

### Custom ordering

JavaScript uses an object as a status-to-priority mapping and then uses `sort`.

The SQL equivalent uses CASE in ORDER BY.

This demonstrates the same business requirement implemented in two different environments.

### Conditional aggregation

JavaScript's `reduce` method performs calculations equivalent to SQL conditional aggregation.

For example, paid revenue is accumulated only when `paymentStatus === "paid"`.

SQL performs the equivalent operation with conditional SUM.

### Rule tables

The JavaScript implementation also demonstrates a rule-table approach.

Instead of hard-coding every threshold directly into a conditional chain, the thresholds can be represented as data.

This approach becomes relevant when business rules change frequently.

A database implementation can use the same idea through a dedicated rules table.

---

## C++ case study

The C++ implementation models a more complete transaction-processing system.

The scenario involves:

- customers
- transactions
- transaction classifications
- customer risk
- payment aggregation
- operational actions

The system separates raw domain data from business-rule functions.

### Domain structures

The `Customer` structure contains customer attributes.

The `Transaction` structure contains transaction attributes.

The `ClassifiedTransaction` structure contains the derived results.

The `CustomerReport` structure contains aggregated reporting information.

This separation prevents raw data and derived reporting values from being mixed together.

### Optional values

C++ `std::optional` represents values that may be unavailable.

This provides a useful conceptual parallel to SQL NULL.

A customer can therefore have:

- a known income
- an unknown income
- a known credit score
- an unknown credit score

The risk classifier explicitly handles missing values.

### Rule engine

`TransactionRuleEngine` centralizes transaction-related business transformations.

It calculates:

- transaction size
- shipping category
- customer risk
- service fee
- operational action

This demonstrates a maintainable alternative to scattering business rules throughout application code.

### Customer indexing

Customers are indexed by ID using `std::unordered_map`.

This avoids repeatedly scanning the complete customer collection when transactions need to find their corresponding customer.

Expected lookup is approximately O(1).

### Conditional aggregation

The customer report performs conditional aggregation.

Paid transactions contribute to paid revenue and paid order count.

Pending transactions contribute to pending order count.

This is conceptually equivalent to SQL expressions such as:

`SUM(CASE WHEN payment_status = 'paid' THEN amount ELSE 0 END)`

and:

`SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END)`

### Custom ordering

The C++ implementation assigns priorities to risk categories and sorts the resulting reports.

This models:

`ORDER BY CASE risk WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'UNKNOWN' THEN 3 ELSE 4 END`

The important idea is that CASE can create a hidden ordering value.

### Pivot report

The payment pivot separates transaction amounts into:

- paid
- pending
- cancelled
- refunded

This is equivalent to conditional aggregation in SQL.

### Validation

Customer data is validated through CASE-style rules.

Possible classifications include:

- missing income and credit score
- missing income
- missing credit score
- invalid negative income
- invalid credit score
- valid

This demonstrates that CASE is useful not only for presentation but also for data-quality reporting.

---

## SQL versus application logic

The same business rule can often be implemented both in SQL and in application code.

The decision about where the rule belongs should consider several factors.

### SQL is often appropriate when

- the rule is directly related to stored data
- the result is needed for filtering
- the result is needed for grouping
- the result is needed for sorting
- the result is needed for aggregation
- transferring raw data to the application would be unnecessarily expensive
- the database is the authoritative owner of the classification

### Application code may be appropriate when

- the rule depends on application state
- the rule requires external services
- the rule depends on user-interface state
- the transformation is not useful to other database consumers
- application ownership is intentional
- the business logic is substantially easier to test and maintain outside SQL

The main architectural risk is duplication.

If a risk classification exists independently in SQL, JavaScript, Python, and another service, the implementations can eventually disagree.

A clear ownership decision and shared boundary tests reduce this risk.

---

## Rule tables versus hard-coded CASE

A short, stable business rule is often clear as CASE.

For example:

`CASE WHEN amount < 1000 THEN 'Small' WHEN amount < 5000 THEN 'Medium' WHEN amount < 20000 THEN 'Large' ELSE 'Enterprise' END`

A rule table may be preferable when thresholds change frequently.

A rule table could contain:

| Minimum | Maximum | Category |
|---:|---:|---|
| 0 | 999.99 | Small |
| 1000 | 4999.99 | Medium |
| 5000 | 19999.99 | Large |
| 20000 | Open-ended | Enterprise |

The advantage is that rule values become data rather than SQL source code.

This can make changes easier to audit and administer.

The trade-off is increased schema and query complexity.

---

## CASE and data quality

CASE is useful for exposing data-quality problems.

For example:

`CASE WHEN annual_income IS NULL AND credit_score IS NULL THEN 'Missing both' WHEN annual_income IS NULL THEN 'Missing income' WHEN credit_score IS NULL THEN 'Missing credit score' WHEN annual_income < 0 THEN 'Invalid income' ELSE 'Valid' END`

This approach is useful because it preserves the original data while producing a diagnostic classification.

Instead of silently replacing bad data, a reporting query can expose the exact condition that requires attention.

This is particularly useful for:

- ETL validation
- data migration
- analytics quality checks
- customer onboarding
- financial data validation
- operational monitoring

---

## Important distinction: CASE versus WHERE

CASE produces a value.

WHERE determines whether a row participates in the result.

For example:

`CASE WHEN amount >= 5000 THEN 'Large' ELSE 'Small' END`

produces a classification.

`WHERE amount >= 5000`

filters rows.

These mechanisms may sometimes express similar logic, but they have different purposes.

Using the appropriate construct makes SQL easier to understand.

---

## Important distinction: CASE versus COALESCE

CASE evaluates explicit conditions.

COALESCE chooses the first non-NULL value.

Example:

`COALESCE(country, 'Unknown')`

means use country when it exists and `Unknown` otherwise.

CASE can express a broader rule:

`CASE WHEN country IS NULL THEN 'Unknown' WHEN country = 'India' THEN 'Domestic' ELSE 'International' END`

COALESCE handles missing values.

CASE handles business decisions.

They are frequently combined.

---

## Important distinction: simple CASE versus searched CASE

Simple CASE:

`CASE status WHEN 'paid' THEN 'Complete' WHEN 'pending' THEN 'Waiting' ELSE 'Other' END`

Searched CASE:

`CASE WHEN amount >= 5000 THEN 'Large' WHEN payment_status = 'pending' THEN 'Waiting' ELSE 'Other' END`

Use simple CASE when comparing one expression against discrete values.

Use searched CASE when the rules involve conditions, ranges, multiple columns, or Boolean expressions.

---

## Common mistakes

### Incorrect NULL comparison

Incorrect:

`WHERE credit_score = NULL`

Correct:

`WHERE credit_score IS NULL`

### Incorrect rule order

Incorrect:

`CASE WHEN amount >= 1000 THEN 'Medium' WHEN amount >= 5000 THEN 'Large' END`

The second condition cannot classify values of 5000 or greater because the first condition already matches them.

### Missing ELSE

A missing ELSE can produce NULL values unexpectedly.

### Overly broad conditions

A broad condition placed before a specific condition can make the specific condition unreachable.

### Inconsistent result types

CASE branches should have compatible result types.

Mixing unrelated types can produce implicit conversions or database-specific behavior.

### Excessive nesting

Deeply nested CASE expressions can become difficult to read, test, and maintain.

### Duplicated rules

Copying the same large CASE expression into many queries increases the chance of inconsistent future changes.

### Using CASE for authorization

A CASE expression that produces `Allowed` or `Denied` should not be treated as a security boundary.

Actual authorization must be enforced through appropriate security mechanisms.

### Unparameterized input

User-provided values should not be inserted directly into SQL text.

Use parameterized queries.

---

## Edge cases

### Boundary values

Always test exact boundaries.

For:

`WHEN amount < 1000`

the values 999.99 and 1000 behave differently.

### Negative values

A numerical classification may not automatically reject negative values.

If negative values are invalid, validation should explicitly detect them.

### NULL values

A NULL value can behave differently from every ordinary value.

Explicitly define the desired treatment.

### Unexpected categories

An unexpected status should normally have a defined ELSE behavior.

### Overlapping ranges

Review every pair of numerical conditions for overlap.

### Empty datasets

Conditional aggregation and reporting queries should be checked against the case where no rows match.

### Mixed data quality

Production data may not satisfy assumptions made by the original business rule.

Validation should therefore be considered part of the design.

---

## Performance considerations

CASE itself is usually not the primary performance problem in a complex SQL workload.

The larger costs commonly come from:

- scanning large tables
- joins
- sorting
- grouping
- window functions
- data transfer
- disk access
- memory pressure

Still, CASE placement matters.

### CASE in SELECT

Usually performs an expression calculation for each returned row.

### CASE in ORDER BY

May contribute to sorting work.

### CASE in WHERE

Can make the filtering expression less directly usable by an index, depending on the database and query structure.

When a direct predicate is available, it can often be clearer.

### Repeated CASE expressions

Repeating a large CASE expression many times increases maintenance cost and can increase computation.

A CTE, view, generated column, or centralized rule design may be appropriate.

### Generated or computed columns

Some database systems support generated or computed columns.

A frequently used classification may sometimes be materialized or indexed through such a mechanism.

The exact approach depends on the database engine.

### Execution plans

Production performance should be measured using the database's execution-plan facilities and representative data.

The Python implementation includes an SQLite `EXPLAIN QUERY PLAN` example to introduce this concept.

---

## Security considerations

CASE is not an authorization mechanism.

A query such as:

`CASE WHEN condition THEN 'Allowed' ELSE 'Denied' END`

does not automatically prevent unauthorized access to the underlying row.

Security must be implemented through appropriate mechanisms such as:

- database permissions
- row-level security where supported
- application authorization
- authentication
- access-control policies
- controlled views
- auditing

SQL values supplied by users should be parameterized.

The Python implementation demonstrates a parameterized threshold:

`CASE WHEN amount >= ? THEN 'Above threshold' ELSE 'Below threshold' END`

The value is supplied separately from the SQL statement.

This prevents the value itself from becoming part of the SQL syntax and is an important defense against SQL injection.

Dynamic table names, column names, and SQL keywords are different from ordinary values and require validated design when they must be dynamic.

---

## Testing CASE expressions

CASE expressions should be tested like business rules.

Range classifications should include:

- below the first boundary
- exactly at the first boundary
- just above the first boundary
- just below the next boundary
- exactly at the next boundary
- above the final boundary
- NULL
- invalid values where applicable

For the order-size rule, the Python implementation tests:

- 0
- 999.99
- 1000
- 4999.99
- 5000
- 19999.99
- 20000

The JavaScript implementation tests the same important boundaries.

The C++ implementation uses assertions to verify the expected classification.

This cross-language testing approach is useful when the same business rule is implemented in multiple systems.

---

## Performance model for rule evaluation

A CASE expression containing `k` WHEN conditions can require up to `k` condition checks for one row in the worst case.

For `n` rows, the simple expression-evaluation component can therefore be thought of as having a worst-case relationship of O(n × k).

This does not represent the full cost of a SQL query.

A query can spend substantially more time on:

- joining
- sorting
- aggregation
- disk I/O
- network transfer
- scanning
- window processing

The C++ case study also demonstrates algorithmic design.

Customer IDs are indexed using `unordered_map`, giving expected constant-time lookup.

The customer report requires a transaction pass and customer pass, approximately O(n + m), where:

- n is the number of transactions
- m is the number of customers

Sorting the final report costs approximately O(m log m).

---

## Production design considerations

A CASE expression is often appropriate when a rule is:

- stable
- relatively small
- directly tied to the query
- naturally expressed as conditions
- useful for reporting or aggregation

A more centralized design may be appropriate when rules are:

- frequently changed
- administered by non-developers
- large in number
- subject to effective dates
- subject to extensive audit requirements
- shared by many systems

Potential alternatives include:

- rules tables
- views
- CTEs
- generated columns
- stored procedures where appropriate
- application-layer services
- dedicated rule engines in specialized systems

The correct design depends on the business ownership of the rule and the architecture of the system.

---

## Implementation comparison

| Aspect | Python | JavaScript | C++ |
|---|---|---|---|
| Primary role | Execute real SQL | Compare SQL and application logic | Model a technical case study |
| Database execution | SQLite | Not required | Not required |
| CASE execution | Actual SQL | SQL shown alongside equivalent logic | CASE-style C++ rule functions |
| NULL representation | SQLite NULL | `null` and `undefined` | `std::optional` |
| Aggregation | SQL SUM and COUNT | `reduce` and maps | Explicit aggregation structures |
| Sorting | SQL ORDER BY CASE | JavaScript `sort` | `std::sort` |
| Testing | Python assertions | JavaScript exceptions | C++ assertions |
| Rule organization | SQL queries and CTEs | Functions and rule data | Rule-engine class |
| Performance focus | Query design | Data-transfer and application processing | Algorithmic complexity |
| Best demonstration | Actual SQL behavior | Cross-layer comparison | System architecture |

---

## Real-world applications

CASE expressions appear in many production SQL workloads.

### Financial systems

CASE can classify:

- transaction risk
- payment state
- revenue band
- customer segment
- fee category
- loan status

### E-commerce

CASE can classify:

- order size
- shipping speed
- inventory state
- customer value
- discount tier

### Banking

CASE can support:

- customer segmentation
- risk reporting
- account status
- transaction monitoring
- delinquency categories

### Human resources

CASE can classify:

- salary bands
- performance bands
- employee tenure
- departmental categories

### Data engineering

CASE can support:

- data-quality labels
- transformation rules
- ETL normalization
- anomaly categories
- migration validation

### Analytics

CASE is frequently used to turn numerical or categorical raw data into dimensions suitable for reports and dashboards.

---

## Practical CASE patterns

### Classification

`CASE WHEN amount < 1000 THEN 'Small' ELSE 'Large' END`

### Status translation

`CASE status WHEN 'P' THEN 'Pending' WHEN 'C' THEN 'Complete' ELSE 'Unknown' END`

### Conditional numeric calculation

`CASE WHEN amount >= 10000 THEN amount * 0.01 ELSE amount * 0.02 END`

### Conditional count

`SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END)`

### Conditional total

`SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END)`

### Custom sorting

`ORDER BY CASE status WHEN 'urgent' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END`

### Missing-value classification

`CASE WHEN value IS NULL THEN 'Missing' ELSE 'Present' END`

### Data-quality validation

`CASE WHEN amount < 0 THEN 'Invalid' ELSE 'Valid' END`

### Multi-column rule

`CASE WHEN credit_score >= 750 AND annual_income >= 100000 THEN 'Premium' ELSE 'Standard' END`

---

## Files in this implementation

The Python implementation is a standalone educational SQL program. It creates an in-memory SQLite database, inserts representative records, executes actual SQL CASE queries, performs conditional aggregation, demonstrates CTEs and window functions, inspects a query plan, and runs boundary tests.

The JavaScript implementation provides an application-layer perspective. It demonstrates how SQL CASE rules correspond to JavaScript functions, object-based mappings, array sorting, reduction-based aggregation, rule tables, validation, and test cases.

The C++ implementation is an industry-style technical case study. It separates domain data from business rules, indexes customers for efficient lookup, handles missing values through `std::optional`, aggregates transactions, creates pivot-style output, sorts by business priority, validates records, and tests rule boundaries.

Together, the three implementations show that CASE is fundamentally a mechanism for converting conditions into values, while the appropriate implementation layer depends on where the business rule belongs.

## Key principles

1. CASE produces a value.
2. Simple CASE compares one expression with possible values.
3. Searched CASE evaluates independent conditions.
4. WHEN conditions are ordered.
5. The first applicable rule determines the result.
6. ELSE defines the fallback result.
7. Omitting ELSE can produce NULL.
8. NULL should be tested with IS NULL or IS NOT NULL.
9. CASE can return text, numbers, dates, or other compatible result types.
10. CASE can be used in SELECT, ORDER BY, GROUP BY, UPDATE, and other expressions.
11. Conditional aggregation is one of the most powerful practical CASE patterns.
12. CASE should not be confused with WHERE filtering.
13. CASE is not an authorization mechanism.
14. Complex and frequently changing rule systems may benefit from centralized rule data.
15. Boundary conditions should be tested explicitly.
16. Query performance should be measured using realistic workloads and execution plans.
17. Parameterized queries should be used for user-supplied SQL values.
18. Business-rule ownership should be clear when the same logic exists in multiple application layers.
