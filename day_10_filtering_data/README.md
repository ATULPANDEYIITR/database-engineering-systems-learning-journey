# Filtering Data in SQL

## Topic

Filtering Data with SQL using comparison operators, logical operators, `NULL`, `BETWEEN`, `IN`, and `LIKE`.

The accompanying Python script provides a complete executable tutorial using Python's built-in `sqlite3` module. It creates an in-memory relational database, inserts sample data, and demonstrates filtering from basic `WHERE` conditions through advanced multi-condition queries, subqueries, joins, aggregation, parameterized SQL, and performance considerations.

No external Python package or database server is required.

## SQL filtering fundamentals

Filtering means selecting only the rows that satisfy a specified condition.

The primary SQL clause for row-level filtering is `WHERE`.

A basic structure is:

    SELECT column1, column2
    FROM table_name
    WHERE condition;

For example, a query can select products whose price is greater than a particular amount:

    SELECT product_name, price
    FROM products
    WHERE price > 20000;

The database evaluates the condition for each applicable row. Rows for which the condition evaluates to `TRUE` are retained by the `WHERE` clause.

Rows for which the condition evaluates to `FALSE` or `UNKNOWN` are not returned.

## Comparison operators

Comparison operators compare values.

The principal operators demonstrated in the script are:

| Operator | Meaning |
|---|---|
| `=` | Equal to |
| `<>` | Not equal to |
| `>` | Greater than |
| `>=` | Greater than or equal to |
| `<` | Less than |
| `<=` | Less than or equal to |

SQL equality uses `=` rather than the programming-language-style `==`.

For example:

    SELECT product_name
    FROM products
    WHERE category = 'Electronics';

A numeric comparison can be written as:

    SELECT product_name, price
    FROM products
    WHERE price >= 10000;

The comparison must make sense for the underlying data type. Numeric comparisons and text comparisons follow different rules, and implicit type conversion behavior varies between database systems.

## Equality and inequality

Equality tests whether two values match:

    WHERE membership = 'Gold'

Inequality excludes a value:

    WHERE category <> 'Electronics'

For a simple inequality condition, `<>` is widely recognized as the standard SQL operator. Some database systems also support `!=`, but `<>` is the more traditional portable SQL form.

## Logical operators

Logical operators combine conditions.

The main operators are:

| Operator | Meaning |
|---|---|
| `AND` | Every combined condition must be true |
| `OR` | At least one combined condition must be true |
| `NOT` | Reverses a logical condition |

### AND

`AND` requires both conditions to be true.

    WHERE age >= 30
      AND membership = 'Gold'

This is useful when multiple requirements must be satisfied simultaneously.

### OR

`OR` requires at least one condition to be true.

    WHERE city = 'Delhi'
       OR city = 'Lucknow'

### NOT

`NOT` reverses a condition.

    WHERE NOT category = 'Electronics'

For simple inequality, the equivalent expression is often clearer:

    WHERE category <> 'Electronics'

## Operator precedence

Mixed `AND` and `OR` expressions require careful attention.

A simplified precedence order is:

1. `NOT`
2. `AND`
3. `OR`

Therefore:

    WHERE A OR B AND C

is interpreted as:

    WHERE A OR (B AND C)

It is not normally interpreted as:

    WHERE (A OR B) AND C

Parentheses make the intended logic explicit:

    WHERE (city = 'Delhi' OR city = 'Lucknow')
      AND membership = 'Gold'

Parentheses are especially important in business rules because a query can be syntactically valid while producing logically incorrect results.

## SQL three-valued logic

SQL does not operate only with `TRUE` and `FALSE`.

SQL uses three logical states:

- `TRUE`
- `FALSE`
- `UNKNOWN`

The third state is especially important when `NULL` is involved.

A condition involving an unknown value can evaluate to `UNKNOWN`.

For example:

    NULL = 5

does not evaluate to `TRUE`.

Similarly:

    NULL = NULL

does not evaluate to `TRUE`.

This behavior is fundamental to understanding SQL filtering.

A `WHERE` clause returns rows only when its condition evaluates to `TRUE`.

Conditions evaluating to `FALSE` or `UNKNOWN` are excluded.

## NULL

`NULL` represents a missing, unknown, or unavailable value.

It should not automatically be interpreted as:

- zero
- an empty string
- false
- a literal word such as `"NULL"`

The correct syntax for testing a NULL value is:

    WHERE column_name IS NULL

The correct syntax for testing a non-NULL value is:

    WHERE column_name IS NOT NULL

For example:

    SELECT customer_name, email
    FROM customers
    WHERE email IS NULL;

A common mistake is:

    WHERE email = NULL;

This does not correctly identify NULL values because normal comparison operators produce `UNKNOWN` when the relevant value is NULL.

## NULL and logical operators

NULL becomes particularly important when combined with `AND`, `OR`, and `NOT`.

Important logical relationships include:

| Expression | Result |
|---|---|
| `TRUE AND UNKNOWN` | `UNKNOWN` |
| `FALSE AND UNKNOWN` | `FALSE` |
| `TRUE OR UNKNOWN` | `TRUE` |
| `FALSE OR UNKNOWN` | `UNKNOWN` |
| `NOT UNKNOWN` | `UNKNOWN` |

This explains why apparently intuitive filters can behave unexpectedly when columns contain NULL values.

## NULL and arithmetic

Arithmetic involving NULL commonly produces NULL.

For example, if `discount` is NULL:

    price * (1 - discount)

can produce NULL.

The correct treatment depends on the business meaning of the missing value.

If a missing discount explicitly means zero discount, `COALESCE` can express that rule:

    COALESCE(discount, 0)

This produces zero when `discount` is NULL.

The distinction is important because replacing NULL with zero is a business decision, not merely a technical operation.

## COALESCE

`COALESCE` returns the first non-NULL expression.

For example:

    COALESCE(membership, 'No Membership')

converts a missing membership value into a display label.

With several expressions:

    COALESCE(value1, value2, value3)

the first non-NULL value is returned.

`COALESCE` is useful for:

- default display values
- calculations where a specific missing-value policy is appropriate
- reporting
- conditional expressions

It should not be used automatically. Replacing unknown information with a default can change the meaning of the analysis.

## BETWEEN

`BETWEEN` tests whether a value falls within an inclusive range.

The following:

    WHERE price BETWEEN 1000 AND 5000

is equivalent to:

    WHERE price >= 1000
      AND price <= 5000

The endpoints are included.

Therefore, if the value is exactly `1000` or exactly `5000`, it satisfies the condition.

`NOT BETWEEN` selects values outside the inclusive range.

    WHERE price NOT BETWEEN 1000 AND 5000

### BETWEEN and NULL

If the tested value is NULL, the result is not `TRUE`.

For example:

    NULL BETWEEN 10 AND 20

produces `UNKNOWN`.

Consequently, a row with a NULL value will not pass an ordinary `WHERE ... BETWEEN ...` filter.

### BETWEEN and dates

For simple date values, `BETWEEN` can be convenient.

The script uses ISO-formatted dates such as:

    2025-02-01

ISO `YYYY-MM-DD` formatting has useful chronological ordering when dates are stored as text.

For timestamps, half-open ranges are often safer:

    timestamp >= start
    AND timestamp < next_period_start

This avoids problems involving the exact time represented by the end boundary.

## IN

`IN` checks whether a value belongs to a specified set.

For example:

    WHERE city IN ('Delhi', 'Lucknow', 'Pune')

is conceptually similar to:

    WHERE city = 'Delhi'
       OR city = 'Lucknow'
       OR city = 'Pune'

`IN` is usually clearer when multiple discrete values must be matched.

## NOT IN

`NOT IN` excludes values appearing in a specified set.

For example:

    WHERE category NOT IN ('Electronics', 'Stationery')

A major edge case occurs when the comparison set contains NULL.

For example:

    WHERE customer_id NOT IN (1, 2, NULL)

can produce unexpected results because SQL's three-valued logic makes the condition `UNKNOWN` for values that cannot establish a definite non-match.

When a subquery can contain NULL values, `NOT EXISTS` is often a safer alternative.

## IN versus EXISTS

`IN` and `EXISTS` can both be used for relationship-based filtering, but they express different concepts.

`IN` asks whether a value belongs to a result set:

    WHERE customer_id IN (
        SELECT customer_id
        FROM orders
        WHERE status = 'Pending'
    )

`EXISTS` asks whether at least one matching row exists:

    WHERE EXISTS (
        SELECT 1
        FROM orders
        WHERE orders.customer_id = customers.customer_id
          AND status = 'Pending'
    )

`EXISTS` is especially useful for correlated relationship checks.

The performance characteristics of `IN` and `EXISTS` depend on the database optimizer, indexes, data distribution, query structure, and database engine. The choice should be based on semantic clarity first and measured performance when necessary.

## NOT EXISTS

`NOT EXISTS` is useful when the requirement is to find rows for which no matching related row exists.

For example:

    WHERE NOT EXISTS (
        SELECT 1
        FROM orders
        WHERE orders.customer_id = customers.customer_id
          AND status = 'Cancelled'
    )

This asks whether there is no cancelled order associated with the customer.

It avoids the specific NULL-related problem associated with `NOT IN`.

## LIKE

`LIKE` performs pattern matching on text.

Two primary wildcards are important:

| Wildcard | Meaning |
|---|---|
| `%` | Zero or more characters |
| `_` | Exactly one character |

Examples:

    WHERE customer_name LIKE 'A%'

matches names beginning with `A`.

    WHERE customer_name LIKE '%ar%'

matches names containing `ar`.

    WHERE customer_name LIKE '%a'

matches values ending with `a`.

The underscore matches exactly one character:

    WHERE customer_name LIKE 'A_a%'

## NOT LIKE

`NOT LIKE` excludes values matching a pattern.

For example:

    WHERE product_name NOT LIKE '%Desk%'

selects product names that do not contain the specified pattern.

## Escaping LIKE wildcards

Sometimes `%` or `_` is actual data rather than a wildcard.

SQL can use an escape character to search for a literal wildcard.

For example, using backslash as the escape character:

    LIKE '%\%%' ESCAPE '\'

can search for a literal percent sign.

Similarly:

    LIKE '%\_%' ESCAPE '\'

can search for a literal underscore.

Exact escape syntax and behavior can vary between database systems, so production queries should follow the target database's documented rules.

## LIKE case sensitivity

Case sensitivity is database-specific.

SQLite's default behavior for ASCII text differs from some other SQL database systems.

Applications should not assume that:

    LIKE 'a%'

has identical case behavior in every database engine.

If a specific case-insensitive search policy is required, an explicit normalization strategy can be used, such as:

    LOWER(customer_name) LIKE LOWER(?)

The performance impact should be considered because applying a function to a column can affect normal index usage.

Some database systems provide dedicated operators, collations, functional indexes, or other mechanisms for efficient case-insensitive search.

## Combining filtering conditions

Real queries frequently combine several filtering techniques.

For example:

    WHERE country = 'India'
      AND age BETWEEN 25 AND 45
      AND city IN ('Delhi', 'Lucknow', 'Mumbai')
      AND membership IS NOT NULL

This expresses four independent business requirements.

Complex filters should be formatted so that each business rule is visible.

For mixed conditions, parentheses should explicitly communicate the intended logic:

    WHERE country = 'India'
      AND (
            membership = 'Gold'
            OR membership = 'Silver'
          )

This is easier to review than a densely packed Boolean expression.

## Filtering calculated values

A filter does not have to compare only stored columns.

SQL can filter expressions.

For example:

    WHERE quantity * price > 20000

can identify order lines whose gross value exceeds a threshold.

Expressions can combine arithmetic, functions, and conditional logic.

When NULL is involved, the expression's NULL behavior must be considered.

For example:

    quantity * price * (1 - discount)

can become NULL if `discount` is NULL.

If the business rule says NULL means no discount:

    quantity * price * (1 - COALESCE(discount, 0))

makes that rule explicit.

## CASE expressions

`CASE` implements conditional logic in SQL.

A common form is:

    CASE
        WHEN condition1 THEN result1
        WHEN condition2 THEN result2
        ELSE result3
    END

It can be used to create classifications such as:

- Budget
- Mid-range
- Premium

or:

- Out of Stock
- Low Stock
- Available

`CASE` is particularly useful when a filter should be represented as an analytical flag instead of removing rows.

For example, a product can remain in the result while being classified according to its stock level.

## WHERE versus HAVING

`WHERE` and `HAVING` perform different roles.

`WHERE` filters rows before grouping.

`HAVING` filters groups after aggregation.

For example:

    SELECT status, COUNT(*)
    FROM orders
    WHERE status <> 'Cancelled'
    GROUP BY status;

Here `WHERE` removes cancelled rows before counting.

A group-level condition requires `HAVING`:

    SELECT customer_id, COUNT(*)
    FROM orders
    GROUP BY customer_id
    HAVING COUNT(*) >= 2;

`COUNT(*) >= 2` cannot normally be placed in `WHERE` because the aggregate result is produced at the grouping stage.

## Filtering joined data

Filtering can reference columns from multiple tables.

For example, an order query can simultaneously filter:

- customer country
- product category
- product price
- order status

A simplified structure is:

    FROM orders
    JOIN customers
        ON customers.customer_id = orders.customer_id
    JOIN products
        ON products.product_id = orders.product_id
    WHERE customers.country = 'India'
      AND products.category = 'Electronics'
      AND orders.status = 'Delivered'

The location of a filter matters with outer joins.

For a `LEFT JOIN`, placing a right-table condition in the `WHERE` clause can remove rows where the right side is NULL. This can make the result behave like an inner join for that condition.

If unmatched left-side rows must be preserved, the condition may belong in the `ON` clause instead.

This is an important semantic distinction.

## Subquery filtering

A subquery can provide values for filtering.

A scalar subquery can produce one value:

    WHERE price > (
        SELECT AVG(price)
        FROM products
    )

This selects products priced above the overall average.

An `IN` subquery can produce a set:

    WHERE customer_id IN (
        SELECT customer_id
        FROM orders
        WHERE status = 'Pending'
    )

Subqueries are useful when the filtering condition depends on derived information rather than a fixed literal.

## Correlated subqueries

A correlated subquery references a value from the outer query.

The script uses this technique to find products whose price is above the average price of their own category.

Conceptually:

    WHERE p.price > (
        SELECT AVG(p2.price)
        FROM products AS p2
        WHERE p2.category = p.category
    )

The inner query changes according to the current outer row.

Correlated subqueries can be expressive, but they should be evaluated carefully for performance on large datasets. A join, window function, or pre-aggregated relation may sometimes provide a more efficient implementation.

## Conditional aggregation

Filtering does not always mean deleting rows from the result.

Conditional aggregation can calculate statistics for different subsets within the same group.

For example:

    SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END)

counts delivered orders within each customer group.

This is useful for reporting metrics such as:

- total orders
- delivered orders
- cancelled orders
- pending orders

The script also demonstrates SQLite's aggregate `FILTER` syntax where supported.

## Dynamic filtering

Applications frequently allow users to specify optional filters.

For example, a reporting interface may allow:

- country
- minimum age
- maximum age
- city
- membership
- name pattern
- email availability

The script demonstrates building the conditional structure dynamically while keeping actual values parameterized.

The important distinction is:

- SQL structure can be constructed by application logic.
- User values should be passed as parameters.

This protects the application from SQL injection and prevents data values from accidentally becoming SQL syntax.

## Parameterized queries

Parameterized queries separate SQL instructions from values.

Instead of constructing:

    WHERE customer_name = 'user supplied value'

by string concatenation, the SQL contains a placeholder:

    WHERE customer_name = ?

and the value is supplied separately.

Python's SQLite interface supports this directly.

Parameterized queries are essential when filtering based on user input.

## SQL injection

SQL injection occurs when untrusted input is incorrectly incorporated into SQL syntax.

A dangerous approach is to construct a query by concatenating user input into the SQL string.

The script intentionally demonstrates a malicious-looking input and then safely passes it as a parameter.

With parameterization, the database treats the supplied value as data rather than executable SQL syntax.

This principle applies to:

- search forms
- login systems
- reporting interfaces
- APIs
- administrative dashboards
- filtering endpoints
- database-backed applications

Parameterization is a fundamental database security practice.

## Dynamic IN lists

A common application requirement is:

    city IN (...)

where the number of cities is determined at runtime.

The script generates one parameter placeholder for each value.

For example, conceptually:

    city IN (?, ?, ?)

with the three city names supplied separately.

The values are never concatenated directly into the SQL statement.

An empty list requires explicit application handling because there are no values to compare against. Applications should define the intended meaning of an empty selection instead of generating invalid or ambiguous SQL.

## Date filtering

The script stores example dates as ISO-formatted strings:

    YYYY-MM-DD

For example:

    2025-02-01

For simple date-only values, ISO formatting provides natural lexical ordering.

A date filter can use:

    WHERE order_date >= '2025-02-01'
      AND order_date < '2025-03-01'

This represents February as a half-open interval.

Half-open intervals are particularly useful for timestamps because the end boundary is excluded.

For example:

    timestamp >= '2025-02-01 00:00:00'
    AND timestamp < '2025-03-01 00:00:00'

includes the complete month without having to guess the final representable time of the last day.

Database systems differ in their date and timestamp data types, so production applications should use the native date/time facilities of the selected database.

## Logical query processing order

A simplified logical processing sequence is:

1. `FROM` and `JOIN`
2. `WHERE`
3. `GROUP BY`
4. `HAVING`
5. `SELECT`
6. `ORDER BY`
7. `LIMIT`

This explains several SQL behaviors.

For example, `WHERE` filters rows before grouping.

`HAVING` filters groups after aggregation.

`ORDER BY` can often use a selected alias because it is logically processed later than `SELECT`.

The database's physical execution plan does not necessarily follow this exact sequence internally. Query optimizers can reorder operations when the result remains semantically equivalent.

## Performance considerations

Filtering performance depends on:

- table size
- number of rows
- selectivity
- indexes
- data distribution
- query structure
- joins
- functions used in predicates
- database engine
- optimizer behavior
- storage architecture

Indexes can make filtering substantially faster when they match common access patterns.

The script creates indexes for selected columns and uses SQLite's `EXPLAIN QUERY PLAN` to inspect query strategies.

## Indexes

An index is a data structure that can help the database locate matching rows without scanning every row of a table.

Indexes can be useful for conditions such as:

    WHERE country = 'India'

or:

    WHERE price BETWEEN 10000 AND 30000

An index is not free.

Indexes consume storage and can increase the cost of `INSERT`, `UPDATE`, and `DELETE` operations because the index must also be maintained.

Indexes should therefore be designed according to actual workload patterns.

## LIKE and performance

A pattern such as:

    LIKE 'Desk%'

provides a known beginning to the search pattern and can be more index-friendly in appropriate database configurations.

A pattern such as:

    LIKE '%Desk%'

starts with a wildcard. A conventional B-tree index often cannot efficiently locate the beginning of such a pattern because the beginning is unknown.

For large-scale substring search, database-specific search technologies or specialized indexing strategies may be more appropriate.

## Functions in filtering conditions

A condition such as:

    WHERE LOWER(customer_name) = 'aarav sharma'

can be semantically useful, but applying a function to a column can prevent a conventional index from being used efficiently in some database systems.

Possible strategies include:

- normalized search columns
- functional indexes
- generated columns
- appropriate collations
- database-specific search features

The correct strategy depends on the database engine and workload.

## Security considerations

Filtering code should follow several security principles.

### Use parameterized queries

Do not concatenate untrusted values into SQL.

### Validate application-level input

Parameters prevent SQL injection, but validation is still useful for enforcing business rules such as:

- numeric ranges
- allowed categories
- maximum search length
- acceptable date ranges

### Restrict dynamic SQL structure

Values can normally be parameterized. SQL identifiers such as table names, column names, and sort directions usually cannot be passed as ordinary parameters.

If an application allows users to select a sort column, use an explicit allowlist mapping approved user choices to fixed SQL identifiers.

### Avoid unnecessary data exposure

A filter should return only the columns required by the application.

Filtering rows correctly does not compensate for exposing sensitive columns unnecessarily.

## Edge cases

Important filtering edge cases include:

### NULL

Use `IS NULL` and `IS NOT NULL`.

### Empty string

An empty string is not necessarily the same as NULL.

### Zero

Zero is a numeric value, not NULL.

### BETWEEN boundaries

`BETWEEN` includes both endpoints.

### NULL in NOT IN

A NULL in a comparison set can make `NOT IN` behave unexpectedly.

### Empty IN lists

Applications should explicitly define what an empty selection means.

### LIKE wildcards

`%` and `_` have special meanings and must be escaped when they are intended as literal characters.

### Case sensitivity

LIKE behavior varies between database systems.

### Outer joins

The location of a filtering condition can change whether unmatched rows are preserved.

### Timestamp boundaries

Half-open intervals are often safer than inclusive end timestamps.

## Common mistakes

### Using `==`

Incorrect in standard SQL:

    WHERE price == 1000

Preferred SQL form:

    WHERE price = 1000

Some database engines accept `==`, but relying on non-standard syntax reduces portability.

### Comparing with NULL using `=`

Incorrect:

    WHERE email = NULL

Correct:

    WHERE email IS NULL

### Forgetting BETWEEN is inclusive

This:

    BETWEEN 10 AND 20

includes both 10 and 20.

### Ignoring operator precedence

This:

    A OR B AND C

does not mean:

    (A OR B) AND C

Use parentheses when the intended logic requires them.

### Using NOT IN against nullable data

If the comparison set contains NULL, the result can become UNKNOWN.

Consider `NOT EXISTS` when appropriate.

### Treating NULL as zero automatically

Only use:

    COALESCE(value, 0)

when the business meaning of NULL really is zero for that calculation.

### Concatenating user input

Do not create SQL by inserting raw user values into SQL strings.

Use parameters.

### Filtering an outer join incorrectly

A right-table condition in `WHERE` can eliminate the unmatched rows that a `LEFT JOIN` was intended to preserve.

### Assuming all SQL databases behave identically

SQL is standardized, but database products have differences in:

- syntax
- functions
- NULL-related behavior in specialized features
- text comparison
- collations
- indexing
- date/time handling
- optimizer behavior
- pattern matching

## Comparison of filtering techniques

| Technique | Primary purpose |
|---|---|
| `=` | Match one exact value |
| `<>` | Exclude one exact value |
| `>` / `<` | Compare magnitude |
| `>=` / `<=` | Compare magnitude including boundary |
| `AND` | Require multiple conditions |
| `OR` | Accept alternative conditions |
| `NOT` | Negate a condition |
| `IS NULL` | Find missing values |
| `IS NOT NULL` | Find known values |
| `BETWEEN` | Inclusive range filtering |
| `IN` | Membership in a set |
| `NOT IN` | Exclusion from a set, with NULL caveats |
| `LIKE` | Pattern matching |
| `NOT LIKE` | Pattern exclusion |
| `EXISTS` | Test whether related rows exist |
| `NOT EXISTS` | Test whether related rows do not exist |
| `HAVING` | Filter aggregated groups |

## Practical filter design

A reliable filtering process starts with the business requirement.

For example:

"Find Indian customers aged 25 through 45 in Delhi or Lucknow who have Gold or Silver membership and a known email address."

This can be decomposed into:

    country = 'India'

    age BETWEEN 25 AND 45

    city IN ('Delhi', 'Lucknow')

    membership IN ('Gold', 'Silver')

    email IS NOT NULL

The final SQL becomes easier to understand because each condition directly corresponds to one business rule.

## Testing filtering logic

Filtering logic should be tested at boundaries and exceptional values.

Important test categories include:

- exact lower boundary
- exact upper boundary
- just below the lower boundary
- just above the upper boundary
- NULL values
- empty strings
- zero values
- unexpected categories
- duplicate values
- empty filter lists
- different text casing
- missing related rows

The script includes assertion-based checks for important filtering results.

Assertions can help catch changes that accidentally alter query behavior.

## Production implementation considerations

Production filtering should consider more than syntactic correctness.

Important concerns include:

- parameterization
- query plan inspection
- index design
- data volume
- pagination
- connection management
- transaction boundaries
- timeout behavior
- logging
- monitoring
- database-specific syntax
- access control
- input validation
- NULL semantics
- date and timestamp boundaries

For large datasets, filtering and pagination should be designed together.

Returning a small filtered result is generally preferable to retrieving millions of rows and filtering them in application code when the database can perform the filtering efficiently.

## Filtering in the database versus Python

For database-backed applications, filtering is usually best performed in SQL when the condition can be expressed efficiently by the database.

For example:

    SELECT *
    FROM products
    WHERE price >= 10000;

is generally preferable to retrieving every product into Python and then filtering the list.

Database-side filtering reduces unnecessary data transfer and allows the database optimizer to use indexes and other execution strategies.

Python-side processing remains appropriate when the transformation cannot reasonably be expressed in SQL or when the data has already been retrieved for a legitimate reason.

## Real-world applications

SQL filtering is fundamental to:

- customer analytics
- sales reporting
- financial systems
- inventory management
- banking applications
- e-commerce platforms
- healthcare databases
- HR systems
- CRM systems
- dashboards
- business intelligence
- fraud detection
- transaction monitoring
- logistics
- operational reporting
- data analysis pipelines

Typical requirements include finding:

- customers meeting demographic criteria
- products within a price range
- transactions above a threshold
- records belonging to selected categories
- incomplete records
- records matching a search pattern
- orders within a date range
- entities with or without related activity
- groups exceeding an aggregate threshold

## Script structure

The Python script is organized progressively.

It begins with database creation and sample data, then moves through:

- `SELECT` and `WHERE`
- comparison operators
- logical operators
- operator precedence
- NULL and three-valued logic
- `COALESCE`
- `BETWEEN`
- `IN`
- parameterized `IN`
- `LIKE`
- wildcard escaping
- case considerations
- complex predicates
- calculated filters
- `CASE`
- `WHERE` versus `HAVING`
- subqueries
- `EXISTS`
- correlated subqueries
- date filtering
- edge cases
- dynamic filters
- SQL injection protection
- indexes
- query plans
- joins
- conditional aggregation
- testing
- assertions
- practical business rules
- integrated advanced filtering

The examples execute against the same in-memory SQLite database, allowing the filtering concepts to be observed directly rather than presented only as theoretical syntax.

## Database portability

The tutorial uses SQLite for execution convenience, but the concepts are broadly applicable to SQL.

Differences should be expected when moving to systems such as PostgreSQL, MySQL, SQL Server, Oracle, or other relational database engines.

Particular areas requiring database-specific verification include:

- case sensitivity
- date and timestamp types
- pattern matching
- collations
- regular expressions
- functional indexes
- query optimizer behavior
- execution-plan syntax
- specialized NULL-handling functions
- parameter placeholder syntax

The underlying principles of row filtering, Boolean logic, NULL semantics, ranges, set membership, and pattern matching remain central to relational querying.
