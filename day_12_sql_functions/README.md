# SQL functions: string, numeric, date, conditional and NULL-handling functions

## Topic introduction

SQL functions are operations that accept values or expressions and return a result. They are fundamental to querying, transforming, validating, cleaning, reporting on, and analyzing relational data.

This study script uses Python's built-in `sqlite3` module to create an in-memory SQLite database. No external Python package is required.

The script progresses from basic SQL function concepts to practical reporting, NULL handling, safe calculations, data cleaning, indexing, security, Common Table Expressions, views, window functions, testing, and production considerations.

The examples are deliberately implemented as executable SQL rather than being presented only as theoretical descriptions.

SQLite is used as the execution environment because it is available through Python's standard library. SQL concepts are broadly transferable to PostgreSQL, MySQL, SQL Server, Oracle, and other relational database systems, although function names and syntax can differ.

## What is a SQL function?

A SQL function accepts one or more arguments and returns a value.

The general conceptual structure is:

    FUNCTION(argument1, argument2, ...)

Examples include:

    UPPER(first_name)
    LOWER(email)
    LENGTH(first_name)
    ROUND(salary, 2)
    COALESCE(commission, 0)

Functions can appear in many parts of a SQL statement:

- SELECT
- WHERE
- ORDER BY
- GROUP BY
- HAVING
- JOIN expressions
- CASE expressions
- Common Table Expressions
- subqueries
- views
- aggregate expressions
- window-function expressions

A function may operate on an individual value, an expression, or a collection of rows depending on the type of function.

## Scalar and aggregate functions

### Scalar functions

A scalar function normally processes one row at a time and returns one value for that row.

Examples:

    UPPER(first_name)
    LENGTH(email)
    ROUND(salary, 2)
    COALESCE(commission, 0)

If a table contains ten rows, a scalar expression in a SELECT statement can produce up to ten corresponding results.

### Aggregate functions

Aggregate functions process multiple rows.

Common aggregate functions include:

    COUNT()
    SUM()
    AVG()
    MIN()
    MAX()

For example:

    AVG(salary)

produces a single average for the selected group.

Scalar and aggregate functions can be combined:

    ROUND(AVG(salary), 2)

The aggregate operation calculates the average and the scalar function rounds the result.

## String functions

String functions manipulate character data.

The script demonstrates:

- `UPPER`
- `LOWER`
- `LENGTH`
- `TRIM`
- `SUBSTR`
- `REPLACE`
- `INSTR`
- string concatenation

### UPPER

`UPPER` converts alphabetic characters to uppercase.

    UPPER(first_name)

If the value is `Aarav`, the result is `AARAV`.

A common use is standardizing text for reporting or comparison.

### LOWER

`LOWER` converts alphabetic characters to lowercase.

    LOWER(email)

This is frequently useful when normalizing email addresses or performing case-insensitive comparisons.

### LENGTH

`LENGTH` returns the length of a string.

    LENGTH(first_name)

The exact treatment of characters can depend on the database and data type, especially for multilingual data.

### TRIM

`TRIM` removes whitespace from the beginning and end of a string.

    TRIM(email)

It is useful when imported data contains accidental spaces.

A critical limitation is that `TRIM` does not automatically solve every kind of whitespace or formatting problem. Data imported from external systems can contain different whitespace characters that require more specialized processing.

### SUBSTR

`SUBSTR` extracts a portion of a string.

    SUBSTR(last_name, 1, 1)

The exact indexing and argument behavior should be checked for the database being used.

In the script it is used to construct display names.

### REPLACE

`REPLACE` replaces matching text.

    REPLACE(email, 'example.com', 'company.com')

This is useful for controlled text transformations, although indiscriminate replacement can corrupt data when the replacement rule is broader than intended.

### INSTR

`INSTR` searches for a substring and returns its position in SQLite.

It can be useful for detecting the presence or location of text within another value.

### Concatenation

SQLite uses the `||` operator for string concatenation.

    first_name || ' ' || last_name

This creates a full name.

String concatenation syntax differs between database systems. PostgreSQL also supports `||`, while MySQL commonly uses `CONCAT()`. SQL Server commonly uses `+` or `CONCAT()`, and Oracle supports `||`.

## NULL behavior in string functions

Most SQL functions propagate NULL when the required input is NULL.

For example:

    LENGTH(NULL)

produces `NULL`.

This is different from producing zero.

A missing string and an empty string are different concepts.

An empty string represents a string containing no characters. NULL represents missing, unknown, or unavailable information.

## Numeric functions

Numeric functions perform mathematical or numerical transformations.

The script demonstrates:

- `ABS`
- `ROUND`
- modulo operations
- numeric expressions
- NULL-safe calculations
- division-by-zero protection

### ABS

`ABS` returns the absolute value.

    ABS(value)

For example, the absolute value of `-25` is `25`.

### ROUND

`ROUND` rounds a number to a specified number of decimal places.

    ROUND(amount, 2)

Rounding is particularly important in financial reporting, but rounding should be applied according to the business requirement.

Rounding intermediate values and rounding only the final result can produce different outcomes.

### Modulo

Modulo returns a remainder.

SQLite supports the `%` operator.

    quantity % 2

This can be used for parity checks and other remainder-based logic.

### Numeric NULL propagation

If an expression contains NULL, its result may also become NULL.

For example:

    salary + commission

produces NULL if either value is NULL.

A NULL-safe alternative can be:

    COALESCE(salary, 0) + COALESCE(commission, 0)

Whether replacing NULL with zero is correct depends on the meaning of the data.

## Financial calculations and precision

The script calculates gross and net sales using expressions such as:

    quantity * unit_price

and:

    quantity * unit_price * (1 - COALESCE(discount, 0))

The second expression treats a missing discount as zero.

That is appropriate only when a missing discount is known to mean that no discount applies.

Financial systems require particular care with precision and rounding. Floating-point arithmetic can introduce representation issues. Production financial systems commonly use appropriate exact numeric or decimal data types and explicit rounding rules.

## Date and time functions

Date functions allow SQL queries to manipulate and analyze temporal data.

SQLite has a different date architecture from systems such as PostgreSQL and SQL Server. SQLite commonly stores date and time information as:

- TEXT
- REAL
- INTEGER

The script uses ISO-style date strings such as:

    2026-04-01

This format is particularly useful because its lexical order corresponds to chronological order when consistently stored as `YYYY-MM-DD`.

## SQLite date functions

The script demonstrates:

- `date()`
- `strftime()`
- `julianday()`
- date modifiers

### Extracting date components

SQLite's `strftime()` can extract formatted components.

For example:

    strftime('%Y', hire_date)

extracts the year.

Similarly:

    strftime('%m', hire_date)

extracts the month.

A reporting month can be represented as:

    strftime('%Y-%m', sale_date)

This is useful for monthly reporting.

### Date arithmetic

SQLite supports date modifiers.

For example:

    date(hire_date, '+1 year')

calculates a date one year after the stored date.

### Elapsed time

`julianday()` can be used to calculate the difference between dates.

Conceptually:

    julianday(end_date) - julianday(start_date)

produces the difference in days.

Date arithmetic becomes more complicated when business days, time zones, daylight-saving transitions, holidays, or timestamp precision are involved.

## Date and time portability

Date syntax varies substantially across database systems.

SQLite commonly uses:

    date('now')
    datetime('now')
    strftime(...)

PostgreSQL provides concepts such as:

    CURRENT_DATE
    CURRENT_TIMESTAMP
    EXTRACT()

MySQL commonly provides:

    CURDATE()
    NOW()
    DATE_FORMAT()

SQL Server commonly provides:

    GETDATE()
    DATEPART()
    DATEADD()

Oracle provides functions such as:

    SYSDATE
    ADD_MONTHS()
    TO_CHAR()

The conceptual operation may be portable even when the exact syntax is not.

## Conditional logic with CASE

`CASE` is SQL's primary general-purpose conditional expression.

The searched form is:

    CASE
        WHEN condition1 THEN result1
        WHEN condition2 THEN result2
        ELSE default_result
    END

The script uses CASE for:

- salary bands
- employment status descriptions
- transaction-size classification
- performance classification
- data-quality classification
- handling multiple edge cases

### Searched CASE

A searched CASE evaluates conditions.

Example:

    CASE
        WHEN salary IS NULL THEN 'Missing'
        WHEN salary >= 100000 THEN 'High'
        WHEN salary >= 80000 THEN 'Medium'
        ELSE 'Low'
    END

The order of conditions matters.

If several conditions could be true, the first matching condition determines the result.

### Simple CASE

Simple CASE compares one expression against multiple values.

Example:

    CASE status
        WHEN 'ACTIVE' THEN 'Currently employed'
        WHEN 'ON_LEAVE' THEN 'Temporarily unavailable'
        ELSE 'Unknown status'
    END

Simple CASE is useful when the classification is based on exact values.

### CASE is an expression

CASE is not merely procedural control flow.

It produces a value, which means it can be used in:

- SELECT
- ORDER BY
- GROUP BY
- aggregate expressions
- nested expressions
- CTEs
- views

## NULL fundamentals

NULL is one of the most important concepts in SQL.

NULL generally indicates missing, unknown, or unavailable information.

It is not equivalent to:

- zero
- false
- an empty string
- a blank value
- an ordinary text value

## Three-valued logic

SQL uses three logical states:

- TRUE
- FALSE
- UNKNOWN

This explains why ordinary equality does not work with NULL.

This expression is incorrect for testing NULL:

    salary = NULL

The correct test is:

    salary IS NULL

For non-NULL values:

    salary IS NOT NULL

A comparison involving NULL generally evaluates to UNKNOWN rather than TRUE or FALSE.

This behavior affects WHERE clauses, joins, CASE expressions, arithmetic, aggregates, and data-quality logic.

## COALESCE

`COALESCE` returns the first non-NULL expression.

General form:

    COALESCE(value1, value2, value3, ...)

Examples:

    COALESCE(commission, 0)

    COALESCE(email, 'Email unavailable')

    COALESCE(email, phone, 'No contact available')

COALESCE is particularly useful for:

- default values
- presentation output
- calculations
- multiple fallback values
- reporting

### COALESCE with numbers

The script uses:

    COALESCE(commission, 0)

to allow calculations to proceed when commission is missing.

This does not mean that the underlying commission has been changed to zero. It only changes the value returned by that particular expression.

### COALESCE with strings

The script uses:

    COALESCE(phone, 'Not provided')

to create presentation-friendly output.

Again, this does not repair the underlying data.

## COALESCE and business meaning

Replacing NULL with a value can change the meaning of a calculation.

Consider:

    AVG(salary)

and:

    AVG(COALESCE(salary, 0))

These are not equivalent.

The first calculates the average of known salary values.

The second treats every missing salary as zero.

If NULL means "salary has not been recorded," treating it as zero may produce a misleading business metric.

NULL handling therefore requires domain understanding, not just SQL syntax.

## NULLIF

`NULLIF` compares two expressions.

General form:

    NULLIF(a, b)

If `a` equals `b`, NULLIF returns NULL.

Otherwise it returns `a`.

A common use is protecting against division by zero:

    numerator / NULLIF(denominator, 0)

If the denominator is zero, `NULLIF` turns it into NULL instead of zero.

The result is then NULL rather than an invalid division.

This is particularly useful for percentages, ratios, margins, utilization rates, conversion rates, and other metrics involving denominators.

## IFNULL

SQLite provides:

    IFNULL(value, fallback)

It is similar to the two-argument form of COALESCE.

For example:

    IFNULL(commission, 0)

For portable SQL, `COALESCE` is generally preferable because it is standard SQL and supports multiple fallback expressions.

Different database systems use different names.

Examples include:

- SQLite: `IFNULL`
- MySQL: `IFNULL`
- SQL Server: `ISNULL`
- Oracle: `NVL`
- Standard SQL: `COALESCE`

## String cleaning with NULL handling

Real datasets frequently contain both NULL and empty or whitespace-only strings.

A useful pattern is:

    NULLIF(TRIM(email), '')

This converts an empty string after trimming into NULL.

The result can then be passed to COALESCE:

    COALESCE(NULLIF(TRIM(email), ''), 'No usable email')

This creates a two-stage normalization process:

1. Remove surrounding whitespace.
2. Convert an empty result to NULL.
3. Replace NULL with a presentation fallback.

The script applies this pattern to customer and contact data.

## Functions in WHERE

Functions can be used in filtering conditions.

Example:

    WHERE LOWER(email) = LOWER(?)

This can provide case-insensitive matching.

The major performance consideration is that transforming a column inside a predicate can affect index usage.

For example:

    WHERE LOWER(email) = ?

may require the database to calculate `LOWER(email)` for many rows unless a suitable expression index, generated column, collation, or other database-specific optimization is available.

The script demonstrates an SQLite expression index for this use case.

## Functions in ORDER BY

Functions can be used to sort by calculated values.

Example:

    ORDER BY LENGTH(first_name), LOWER(first_name)

This allows sorting according to derived characteristics rather than the raw stored value.

NULL handling can also influence ordering:

    ORDER BY COALESCE(commission, 0) DESC

This treats missing commission as zero for the purpose of sorting.

That interpretation should be used only when it makes sense for the report.

## Functions in GROUP BY

Functions can create grouping dimensions.

For example:

    GROUP BY strftime('%Y-%m', sale_date)

groups sales into reporting months.

CASE can also create categories that become grouping dimensions.

For example, transactions can be classified into:

- Large
- Medium
- Small

and then aggregated by those categories.

## WHERE versus HAVING

WHERE and HAVING operate at different stages.

`WHERE` filters individual rows before grouping.

Example:

    WHERE salary > 80000

`HAVING` filters groups after aggregation.

Example:

    HAVING AVG(salary) > 80000

This distinction is fundamental when writing analytical SQL.

## Aggregate functions and NULL

Aggregate functions have specific NULL behavior.

`COUNT(*)` counts rows.

`COUNT(column)` counts non-NULL values in that column.

`SUM(column)` normally ignores NULL values.

`AVG(column)` normally ignores NULL values.

`MIN(column)` and `MAX(column)` generally ignore NULL values when non-NULL values are available.

This means:

    COUNT(*)

and:

    COUNT(commission)

can return different values.

The difference is important when measuring data completeness.

## Nested functions

SQL functions can be nested.

Example:

    COALESCE(LOWER(TRIM(email)), 'missing')

The operations conceptually occur from the inside outward:

- `TRIM(email)`
- `LOWER(...)`
- `COALESCE(...)`

Nested expressions can be powerful but can become difficult to maintain when they become excessively deep.

CTEs, subqueries, views, generated columns, or carefully designed schema structures can improve readability when expressions become complex.

## Business metrics using functions

The script calculates real analytical metrics such as:

- gross revenue
- net revenue
- discount-adjusted revenue
- transaction counts
- department revenue
- average salary
- salary classifications
- sales performance
- achievement percentages

For a sale:

    gross_amount = quantity * unit_price

For a discount-adjusted sale:

    net_amount =
        quantity * unit_price * (1 - COALESCE(discount, 0))

The expression demonstrates how numeric and NULL-handling functions combine with ordinary arithmetic.

## Safe ratio calculations

Ratios often contain a denominator that can be zero or NULL.

Unsafe conceptual logic:

    numerator / denominator

A safer pattern is:

    numerator / NULLIF(denominator, 0)

This turns zero into NULL.

The result can then be classified with CASE if the business report needs to distinguish:

- missing denominator
- zero denominator
- successful ratio
- target achieved
- target not achieved

The script demonstrates these conditions explicitly.

## Functions and data quality

SQL functions are useful for identifying and transforming inconsistent data.

Examples include:

    TRIM(name)

    LOWER(email)

    REPLACE(phone, ' ', '')

    NULLIF(TRIM(email), '')

These operations can be used during:

- data migration
- reporting
- ETL pipelines
- data quality checks
- staging-table processing
- customer-data normalization

A transformation query does not automatically modify the stored data. A SELECT expression only changes the value returned by that query.

Permanent correction requires an appropriate data-modification operation and should be handled carefully in production systems.

## CTEs and function-heavy queries

A Common Table Expression can divide a complex query into logical stages.

The script first calculates gross and net sales in a CTE and then classifies transactions in the outer query.

This is useful because it separates:

- raw calculations
- business classification
- final presentation

CTEs can improve readability and debugging.

They do not automatically guarantee better performance. The database optimizer decides how the query is executed, and behavior differs by database engine and query structure.

## Views containing functions

The script creates an employee-directory view that includes:

- uppercase employee names
- normalized email
- NULL-safe phone display
- employment-status classification

A view can provide a reusable logical interface over underlying tables.

Views are useful when the same transformation logic is needed by multiple queries or reporting consumers.

A view should still be designed carefully because complex views can become difficult to maintain and may introduce performance considerations.

## Window functions with scalar functions

Window functions differ from ordinary scalar and aggregate functions.

An aggregate such as:

    AVG(salary)

can reduce multiple rows into one result per group.

A window expression such as:

    AVG(salary) OVER (PARTITION BY department)

can calculate a department average while retaining each employee row.

The script combines window functions with:

- `ROUND`
- `CASE`

This enables analytical comparisons such as identifying employees whose salaries are above or below a department or company average.

## SQL dialect differences

The conceptual categories of SQL functions are broadly portable, but exact syntax varies.

| Operation | SQLite | PostgreSQL | MySQL | SQL Server | Oracle |
|---|---|---|---|---|---|
| Uppercase | `UPPER()` | `UPPER()` | `UPPER()` | `UPPER()` | `UPPER()` |
| Lowercase | `LOWER()` | `LOWER()` | `LOWER()` | `LOWER()` | `LOWER()` |
| Length | `LENGTH()` | `LENGTH()` | `LENGTH()` | `LEN()` | `LENGTH()` |
| Substring | `SUBSTR()` | `SUBSTRING()` | `SUBSTRING()` | `SUBSTRING()` | `SUBSTR()` |
| Rounding | `ROUND()` | `ROUND()` | `ROUND()` | `ROUND()` | `ROUND()` |
| Absolute value | `ABS()` | `ABS()` | `ABS()` | `ABS()` | `ABS()` |
| NULL fallback | `COALESCE()` | `COALESCE()` | `COALESCE()` | `COALESCE()` | `COALESCE()` |
| Two-value fallback | `IFNULL()` | `COALESCE()` | `IFNULL()` | `ISNULL()` | `NVL()` |
| Current date | `date('now')` | `CURRENT_DATE` | `CURDATE()` | `CAST(GETDATE() AS DATE)` | `SYSDATE` |
| Current timestamp | `datetime('now')` | `CURRENT_TIMESTAMP` | `NOW()` | `GETDATE()` | `SYSTIMESTAMP` |

This table illustrates why SQL knowledge has two layers:

1. Understanding the relational and functional concept.
2. Understanding the syntax and behavior of the target database engine.

## Performance considerations

Functions consume CPU and can affect query optimization.

Important considerations include:

### Functions on indexed columns

A condition such as:

    WHERE LOWER(email) = ?

may prevent a normal index on `email` from being used efficiently.

Possible solutions include:

- expression indexes
- functional indexes
- generated columns
- normalized stored values
- appropriate collations
- database-specific case-insensitive data types

The correct solution depends on the database engine and application requirements.

### Repeated calculations

If an expensive expression is repeated many times, consider whether it can be calculated once through a CTE, subquery, generated column, view, or other appropriate design.

### Filtering

Filtering unnecessary rows early can reduce the amount of data that later expressions need to process.

### Query plans

Important production queries should be evaluated using the database's execution-plan tools.

SQLite provides:

    EXPLAIN QUERY PLAN

Other systems provide more sophisticated execution-plan facilities.

Performance should be measured rather than assumed.

## Security considerations

SQL functions themselves are not a replacement for secure SQL construction.

The script demonstrates parameterized SQL through Python's `sqlite3` API.

The unsafe conceptual approach is to concatenate external values into SQL text.

The preferred approach is:

    WHERE email = ?

with the value supplied separately as a bound parameter.

Parameterized queries help prevent SQL injection because data is treated separately from SQL syntax.

Security also requires:

- appropriate database permissions
- least-privilege access
- validation of application inputs
- secure credentials
- controlled schema modification privileges
- appropriate logging
- protection of sensitive information

## Debugging SQL function expressions

Complex function expressions should be debugged incrementally.

Instead of immediately writing a large expression, inspect individual stages.

For example, a normalization expression can be conceptually separated into:

    TRIM(email)

then:

    LOWER(TRIM(email))

then:

    NULLIF(LOWER(TRIM(email)), '')

then:

    COALESCE(NULLIF(LOWER(TRIM(email)), ''), 'missing')

This makes it easier to identify which operation is producing an unexpected result.

CTEs are particularly useful for debugging multi-stage calculations.

## Common mistakes

### Comparing NULL with equals

Incorrect:

    column = NULL

Correct:

    column IS NULL

### Confusing NULL with zero

These represent different meanings.

Zero is known numeric data.

NULL indicates missing, unknown, or unavailable data.

### Confusing NULL with an empty string

An empty string is a value containing no characters.

NULL represents absence of a known value.

### Blindly replacing NULL with zero

COALESCE is powerful, but:

    COALESCE(value, 0)

should be used only when zero is the correct interpretation.

### Ignoring database dialects

A query written for SQLite may not execute unchanged on PostgreSQL, MySQL, SQL Server, or Oracle.

### Rounding too early

Rounding intermediate calculations can change the final result.

### Applying functions without considering indexes

A function in a WHERE clause can affect index usage.

### Ignoring date representation

Date calculations require consistent data types and formats.

### Using functions to hide data-quality problems

A presentation fallback such as:

    COALESCE(email, 'Unknown')

does not repair the missing email in the database.

## Edge cases

The script deliberately includes several edge cases.

### NULL salary

One employee has no salary value.

This demonstrates:

- `IS NULL`
- `COALESCE`
- NULL propagation
- conditional classification
- aggregate NULL behavior

### NULL commission

Some employees have no commission.

This demonstrates the difference between missing commission and zero commission.

### NULL email

Missing email values are used to demonstrate safe presentation and normalization.

### Zero denominator

The ratio table includes a denominator of zero.

`NULLIF` converts the zero into NULL to prevent an unsafe division.

### NULL denominator

A NULL denominator is handled separately from zero.

### Empty or whitespace-only email

The contact data demonstrates the combination:

    TRIM
    NULLIF
    COALESCE

This is a practical data-cleaning pattern.

### Boundary classifications

Salary and transaction classifications use ordered CASE conditions.

This demonstrates why condition ordering matters.

## Testing SQL functions

The script contains executable tests for core behavior.

The tests verify operations such as:

- uppercase conversion
- lowercase conversion
- string length
- COALESCE fallback
- multiple COALESCE values
- NULLIF behavior
- rounding

SQL tests are important because small differences in NULL behavior, data types, date calculations, and rounding can affect production results.

## Production implementation considerations

A production implementation should consider:

### Correctness

The function expression must implement the intended business rule.

### Data types

Numeric calculations should use suitable numeric types.

Date and timestamp columns should have an appropriate representation for the database.

### NULL semantics

Every important NULL should have a defined interpretation.

### Portability

If an application supports multiple database systems, database-specific functions should be isolated or abstracted where appropriate.

### Performance

Function-heavy queries should be evaluated using actual query plans and production-like data volumes.

### Maintainability

Readable SQL is preferable to unnecessarily compact SQL.

Complex expressions should be decomposed when doing so improves understanding and debugging.

### Security

External values should be parameterized.

### Testing

Boundary conditions should be tested, including:

- NULL
- zero
- empty strings
- negative numbers
- very large values
- dates at month and year boundaries
- invalid or unexpected text
- duplicate data
- missing relationships

## Practical applications

SQL functions are used extensively in:

- data analytics
- business intelligence
- financial reporting
- sales reporting
- customer analytics
- HR systems
- accounting systems
- ETL and data pipelines
- data quality processes
- operational dashboards
- application backends
- audit reports
- performance measurement
- database views
- ad-hoc analysis

String functions are especially important for data normalization.

Numeric functions are central to financial and operational calculations.

Date functions support time-based reporting.

CASE expressions implement business classifications.

NULL-handling functions make incomplete datasets safer to process.

## Function selection guide

| Requirement | Common SQL technique |
|---|---|
| Convert text to uppercase | `UPPER()` |
| Convert text to lowercase | `LOWER()` |
| Remove surrounding spaces | `TRIM()` |
| Extract part of a string | `SUBSTR()` or database-specific equivalent |
| Replace text | `REPLACE()` |
| Search inside text | `INSTR()` or database-specific equivalent |
| Combine strings | `||` or `CONCAT()` depending on database |
| Round a number | `ROUND()` |
| Absolute value | `ABS()` |
| Calculate remainder | `%` or `MOD()` |
| Extract date parts | `strftime()` or database-specific date functions |
| Add date intervals | Database-specific date arithmetic |
| Conditional classification | `CASE` |
| Find a missing value | `IS NULL` |
| Find a non-missing value | `IS NOT NULL` |
| Use first non-NULL value | `COALESCE()` |
| Replace one NULL value | `IFNULL()`, `ISNULL()`, `NVL()`, or `COALESCE()` |
| Convert a special value to NULL | `NULLIF()` |
| Protect a division denominator | `NULLIF(denominator, 0)` |
| Aggregate rows | `COUNT()`, `SUM()`, `AVG()`, `MIN()`, `MAX()` |
| Calculate across related rows | Window functions |
| Improve complex query readability | CTEs |
| Encapsulate reusable query logic | Views |

## Relationship between the major function categories

The five main categories in this study are closely related.

String functions transform textual data.

Numeric functions transform and calculate numerical data.

Date functions transform and analyze temporal data.

Conditional expressions apply business rules.

NULL-handling functions control how missing information participates in expressions.

Real analytical queries commonly combine all of them.

A sales report might:

1. normalize a salesperson's name with string functions
2. calculate revenue with numeric expressions
3. group sales by month with date functions
4. replace missing discounts with COALESCE
5. classify transactions with CASE
6. aggregate the resulting values with SUM
7. sort the final output using calculated values

The Python script demonstrates this progression through executable queries rather than isolated syntax examples.
