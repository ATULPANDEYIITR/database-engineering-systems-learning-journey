# SELECT Fundamentals: SELECT, FROM, WHERE, Aliases, and Expressions

## Topic Introduction

The `SELECT` statement is the primary SQL mechanism for retrieving data from a relational database. It can be used for simple data inspection, precise filtering, calculated values, reporting, analytical queries, and complex multi-stage data transformations.

The fundamental structure is:

    SELECT column_list
    FROM table_name
    WHERE condition;

The Python script accompanying this README uses SQLite through Python's standard-library `sqlite3` module. It creates a complete in-memory relational database and executes progressively more sophisticated SQL statements against it.

The tutorial begins with the basic relationship between tables, rows, columns, and queries, then develops the concepts of projection, filtering, aliases, expressions, `NULL`, conditional logic, aggregation, joins, subqueries, CTEs, window functions, parameterized queries, performance, security, and production considerations.

---

## 1. Relational Database Fundamentals

A relational database stores information in tables.

A table contains:

- **Rows**: individual records.
- **Columns**: attributes describing those records.
- **Schema**: the structural definition of tables, columns, data types, relationships, and constraints.
- **Primary key**: a column or set of columns that uniquely identifies a row.
- **Foreign key**: a reference from one table to a key in another table.

The script creates the following tables:

- `departments`
- `employees`
- `customers`
- `orders`
- `products`

For example, `employees` contains employee-specific information such as:

- employee ID
- first name
- last name
- email
- department
- job title
- salary
- commission
- hire date
- manager
- active status

The relational design separates different business concepts into different tables and connects them through keys.

---

## 2. What SELECT Does

`SELECT` retrieves a result set from one or more sources.

The simplest form is:

    SELECT first_name
    FROM employees;

This requests the `first_name` column from the `employees` table.

Selecting multiple columns is equally straightforward:

    SELECT first_name, last_name, job_title
    FROM employees;

The order of columns in the `SELECT` list determines the order of columns in the result.

### SELECT Does Not Normally Modify Data

A basic `SELECT` is a read operation. It does not modify the underlying table.

Statements such as `INSERT`, `UPDATE`, and `DELETE` are responsible for data modification.

---

## 3. SELECT *

The asterisk means all columns:

    SELECT *
    FROM employees;

This is useful while exploring an unfamiliar table, but explicit column selection is usually preferable in production queries.

Instead of:

    SELECT *
    FROM employees;

a stable application interface might use:

    SELECT employee_id, first_name, last_name, email
    FROM employees;

Explicit selection has several advantages:

- It documents the required fields.
- It avoids unnecessary data transfer.
- It reduces accidental dependence on future schema changes.
- It makes application result sets more predictable.
- It makes queries easier to review.

`SELECT *` is not inherently incorrect. Its suitability depends on the purpose of the query.

---

## 4. FROM

`FROM` identifies the source from which rows are retrieved.

For a basic table query:

    SELECT first_name, salary
    FROM employees;

`employees` is the source table.

`FROM` can also operate on more complex sources such as:

- joined tables
- subqueries
- CTEs
- views
- derived tables
- database-specific table-valued constructs

As SQL becomes more advanced, the source represented by `FROM` does not necessarily have to be a physical table.

---

## 5. Projection

The operation of choosing specific columns from a relation is commonly called **projection**.

For example:

    SELECT first_name, salary
    FROM employees;

The original table may contain many columns, but the query exposes only two.

Projection can involve either existing columns or calculated expressions.

For example:

    SELECT
        first_name,
        salary * 12 AS annual_salary
    FROM employees;

Here, `annual_salary` is not stored directly in the table. It is calculated during query execution.

---

## 6. Column Aliases

A column alias gives a result column a temporary output name.

Example:

    SELECT
        first_name AS first,
        last_name AS last
    FROM employees;

The alias affects the result-set name. It does not rename the underlying database column.

Aliases are particularly useful for calculated expressions:

    SELECT
        salary * 12 AS annual_salary
    FROM employees;

A readable alias is preferable to exposing a complicated expression as a generated column name.

### AS Is Often Optional

Many SQL dialects allow:

    SELECT salary * 12 annual_salary
    FROM employees;

instead of:

    SELECT salary * 12 AS annual_salary
    FROM employees;

Using `AS` is generally clearer, particularly when a query contains many expressions.

---

## 7. Table Aliases

A table alias provides a shorter temporary name for a table reference.

Example:

    SELECT
        e.first_name,
        e.salary
    FROM employees AS e;

The table can then be referenced as `e`.

This becomes particularly important when multiple tables contain columns with the same name.

For example:

    SELECT
        e.first_name,
        d.department_name
    FROM employees AS e
    JOIN departments AS d
        ON e.department_id = d.department_id;

Qualified names such as `e.first_name` and `d.department_name` clearly identify the source of each column.

---

## 8. Self-Referencing Tables

A table can sometimes need to be referenced more than once.

The employee table contains a `manager_id` that refers back to another employee.

That makes it possible to use the same table twice:

    FROM employees AS employee
    LEFT JOIN employees AS manager
        ON employee.manager_id = manager.employee_id

The two aliases represent different roles:

- `employee` represents the employee.
- `manager` represents that employee's manager.

This is a common relational pattern for hierarchical data.

---

## 9. Expressions

An **expression** is a SQL construct that evaluates to a value.

Examples include:

    salary

    salary * 12

    first_name || ' ' || last_name

    salary >= 100000

    commission IS NULL

    CASE
        WHEN salary >= 100000 THEN 'High'
        ELSE 'Standard'
    END

Expressions are central to SQL because queries frequently need to calculate or transform values rather than simply return stored columns.

---

## 10. Arithmetic Expressions

SQL supports arithmetic operations such as:

- addition: `+`
- subtraction: `-`
- multiplication: `*`
- division: `/`

For example:

    SELECT
        first_name,
        salary,
        salary * 12 AS annual_salary
    FROM employees;

Another example:

    SELECT
        salary,
        salary / 12.0 AS monthly_salary
    FROM employees;

Using `12.0` instead of `12` can be useful when the database's numeric division rules make integer division possible.

Exact arithmetic behavior can vary between SQL implementations and data types.

---

## 11. String Expressions

SQLite supports the `||` operator for string concatenation.

Example:

    SELECT
        first_name || ' ' || last_name AS full_name
    FROM employees;

The script also demonstrates functions such as:

- `UPPER`
- `LOWER`
- `LENGTH`
- `SUBSTR`

These functions transform or inspect text.

String-function syntax is one area where SQL dialects can differ. A query written for SQLite should not automatically be assumed to be identical in PostgreSQL, MySQL, SQL Server, or Oracle.

---

## 12. WHERE

`WHERE` filters rows.

Example:

    SELECT employee_id, first_name, salary
    FROM employees
    WHERE salary > 100000;

The condition is called a **predicate**.

Only rows for which the predicate evaluates to `TRUE` qualify for the result.

Common comparison operators include:

- `=`
- `<>`
- `!=`
- `>`
- `<`
- `>=`
- `<=`

Exact support for some operators can vary by database system.

---

## 13. AND

`AND` requires both conditions to be true.

Example:

    SELECT first_name, salary
    FROM employees
    WHERE salary >= 80000
      AND salary <= 120000;

Both salary conditions must hold.

Parentheses are useful when the logic becomes complex.

---

## 14. OR

`OR` allows either condition to qualify.

Example:

    SELECT first_name, department_id
    FROM employees
    WHERE department_id = 1
       OR department_id = 5;

A row qualifies if either condition evaluates to `TRUE`.

---

## 15. NOT

`NOT` reverses a predicate.

Example:

    WHERE job_title NOT LIKE '%Manager%'

The condition selects rows that do not match the pattern.

`NOT` can also be applied to other logical conditions.

---

## 16. Logical Operator Precedence

A typical precedence relationship is:

1. `NOT`
2. `AND`
3. `OR`

Therefore:

    A OR B AND C

is interpreted conceptually as:

    A OR (B AND C)

It is not interpreted as:

    (A OR B) AND C

For business rules, explicit parentheses are strongly recommended:

    WHERE (department_id = 1 OR department_id = 5)
      AND salary > 100000

This makes the intended logic unambiguous.

---

## 17. BETWEEN

`BETWEEN` checks whether a value falls within an inclusive range.

Example:

    WHERE salary BETWEEN 80000 AND 120000

The endpoints are included.

Therefore, a salary of exactly `80000` or exactly `120000` qualifies.

This differs from the common half-open interval pattern:

    WHERE hire_date >= '2022-01-01'
      AND hire_date < '2025-01-01'

The latter includes the starting boundary and excludes the ending boundary.

Half-open intervals are particularly useful for date and timestamp ranges.

---

## 18. IN

`IN` checks whether a value belongs to a specified set.

Example:

    WHERE department_id IN (1, 4, 5)

This is often clearer than a long chain of equality comparisons.

Conceptually:

    department_id = 1
    OR department_id = 4
    OR department_id = 5

The behavior of `NOT IN` becomes more subtle when `NULL` is involved, so NULL-aware alternatives such as `NOT EXISTS` can be safer in appropriate relational queries.

---

## 19. LIKE

`LIKE` performs pattern matching.

Example:

    WHERE job_title LIKE '%Engineer%'

The percent sign `%` represents a sequence of zero or more characters in standard SQL pattern matching.

Another commonly used wildcard is `_`, which represents a single character in many SQL implementations.

Pattern matching rules and case sensitivity can vary by database and configuration.

---

## 20. NULL

`NULL` represents missing, unknown, or inapplicable information.

It is not equivalent to:

- zero
- an empty string
- `FALSE`

The following is incorrect as a NULL test:

    WHERE commission = NULL

The correct forms are:

    WHERE commission IS NULL

and:

    WHERE commission IS NOT NULL

---

## 21. Three-Valued Logic

SQL uses three logical states:

- `TRUE`
- `FALSE`
- `UNKNOWN`

Operations involving `NULL` can produce `UNKNOWN`.

For example:

    commission > 10000

cannot be determined as true or false if `commission` is `NULL`.

Because `WHERE` retains rows only when the predicate evaluates to `TRUE`, rows producing `UNKNOWN` are not returned.

This is one of the most important differences between SQL predicates and ordinary two-valued Boolean logic.

---

## 22. NULL Propagation

Arithmetic involving `NULL` generally produces `NULL`.

For example:

    commission * 2

produces `NULL` when `commission` is `NULL`.

The script demonstrates this behavior and then uses `COALESCE`:

    COALESCE(commission, 0)

This substitutes zero when the commission is NULL.

The correct fallback depends on business semantics. Replacing missing data with zero is appropriate only when "missing commission" genuinely means "no commission."

---

## 23. COALESCE

`COALESCE` returns the first non-NULL expression.

Example:

    COALESCE(commission, 0)

With multiple alternatives:

    COALESCE(value1, value2, value3)

the database evaluates the expressions in order and uses the first non-NULL result.

It is useful for:

- display defaults
- arithmetic
- optional relationships
- fallback values

It should not be used blindly to conceal data-quality problems.

---

## 24. CASE Expressions

`CASE` provides conditional logic.

The searched form is:

    CASE
        WHEN condition1 THEN result1
        WHEN condition2 THEN result2
        ELSE default_result
    END

The first matching condition is selected.

The script uses salary ranges to create compensation categories.

For example:

    CASE
        WHEN salary >= 120000 THEN 'Executive'
        WHEN salary >= 100000 THEN 'Senior'
        WHEN salary >= 80000 THEN 'Mid-level'
        ELSE 'Entry-level'
    END

The order matters. If a salary satisfies multiple conditions, the first matching branch wins.

---

## 25. Simple CASE

A simple CASE compares one expression against multiple values.

Example:

    CASE active
        WHEN 1 THEN 'Active'
        WHEN 0 THEN 'Inactive'
        ELSE 'Unknown'
    END

This differs from searched CASE, where each `WHEN` contains an independent condition.

---

## 26. DISTINCT

`DISTINCT` removes duplicate result rows.

Example:

    SELECT DISTINCT department_id
    FROM employees;

For multiple columns, distinctness applies to the complete combination:

    SELECT DISTINCT department_id, active
    FROM employees;

Two rows are considered duplicates for the purpose of this query only when all selected values are equivalent under the database's comparison semantics.

### DISTINCT Is Not a Duplicate-Join Fix

Suppose an incorrect join produces five copies of the same employee.

Adding `DISTINCT` may hide the visible duplication, but it does not correct the underlying relational logic.

The correct approach is to understand why the join produced multiple rows.

---

## 27. ORDER BY

`ORDER BY` determines result ordering.

Example:

    SELECT first_name, salary
    FROM employees
    ORDER BY salary DESC;

`ASC` specifies ascending order.

`DESC` specifies descending order.

Multiple ordering keys are possible:

    ORDER BY salary DESC, first_name ASC

The second expression is used when the first sort key is tied.

Without `ORDER BY`, applications should not assume that rows will appear in a particular business order.

---

## 28. LIMIT and OFFSET

SQLite supports `LIMIT` and `OFFSET`.

Example:

    SELECT first_name, salary
    FROM employees
    ORDER BY salary DESC
    LIMIT 5;

This returns five rows.

Pagination can be expressed as:

    LIMIT 3 OFFSET 2

Large offset-based pagination can become inefficient in some systems. Production applications may use keyset or cursor-based pagination when appropriate.

---

## 29. Aggregate Functions

Aggregate functions operate over multiple rows.

Common aggregates include:

- `COUNT`
- `SUM`
- `AVG`
- `MIN`
- `MAX`

Example:

    SELECT
        AVG(salary),
        MIN(salary),
        MAX(salary)
    FROM employees;

This produces summary values rather than one output row for every employee.

---

## 30. COUNT(*) Versus COUNT(column)

This distinction is important.

    COUNT(*)

counts rows.

    COUNT(commission)

counts non-NULL values in `commission`.

If ten rows exist and three commission values are NULL:

- `COUNT(*)` returns 10.
- `COUNT(commission)` returns 7.

The script demonstrates this difference explicitly.

---

## 31. GROUP BY

`GROUP BY` divides rows into groups before aggregate calculations.

Example:

    SELECT
        department_id,
        COUNT(*) AS employee_count,
        AVG(salary) AS average_salary
    FROM employees
    GROUP BY department_id;

The result contains one row per department represented in the grouping.

When writing grouped queries, every selected non-aggregated expression generally needs to be compatible with the grouping rules of the target database.

---

## 32. HAVING

`HAVING` filters groups after aggregation.

Example:

    SELECT
        department_id,
        COUNT(*) AS employee_count
    FROM employees
    GROUP BY department_id
    HAVING COUNT(*) >= 2;

A useful conceptual distinction is:

- `WHERE` filters individual input rows.
- `HAVING` filters grouped results.

---

## 33. Conceptual Query Processing Order

Although SQL is written using `SELECT` first, a useful conceptual processing model is:

1. `FROM`
2. `JOIN`
3. `WHERE`
4. `GROUP BY`
5. `HAVING`
6. `SELECT`
7. `DISTINCT`
8. `ORDER BY`
9. `LIMIT` / `OFFSET`

This model explains why a SELECT alias generally cannot be used directly in `WHERE`.

For example:

    SELECT salary * 12 AS annual_salary
    FROM employees
    WHERE annual_salary > 1000000;

The alias belongs to the SELECT result, while the WHERE condition is conceptually evaluated earlier.

A subquery or CTE can create another query level:

    SELECT employee_name, annual_salary
    FROM (
        SELECT
            first_name || ' ' || last_name AS employee_name,
            salary * 12 AS annual_salary
        FROM employees
    )
    WHERE annual_salary > 1200000;

At the outer query level, `annual_salary` is now a column of the intermediate result.

---

## 34. Joins

Real databases usually distribute related information across multiple tables.

An employee has a `department_id`, while the department table has the corresponding `department_id`.

An inner join can combine them:

    SELECT
        e.first_name,
        d.department_name
    FROM employees AS e
    INNER JOIN departments AS d
        ON e.department_id = d.department_id;

### INNER JOIN

An `INNER JOIN` returns rows with matching records on both sides.

An employee without a matching department is excluded.

### LEFT JOIN

A `LEFT JOIN` preserves rows from the left table:

    SELECT
        e.first_name,
        d.department_name
    FROM employees AS e
    LEFT JOIN departments AS d
        ON e.department_id = d.department_id;

An employee without a department remains in the result, with NULL values for department columns.

This distinction is essential when missing relationships should remain visible.

---

## 35. Qualified Column References

When multiple tables are present, qualification improves clarity:

    e.salary
    d.department_name

Instead of:

    salary
    department_name

Qualified references also prevent ambiguity when different tables contain columns with identical names.

---

## 36. Scalar Subqueries

A scalar subquery returns one value.

Example:

    SELECT
        first_name,
        salary,
        (
            SELECT AVG(salary)
            FROM employees
        ) AS company_average_salary
    FROM employees;

Each employee row can then be compared with the company-wide average.

Scalar subqueries are useful when a query requires a single derived value calculated independently from the current row.

The subquery must satisfy the scalar requirement. A subquery returning multiple rows where a single value is required can produce an error or database-specific behavior.

---

## 37. Correlated Subqueries

A correlated subquery references a value from the outer query.

Example concept:

    SELECT c.customer_name
    FROM customers AS c
    WHERE EXISTS (
        SELECT 1
        FROM orders AS o
        WHERE o.customer_id = c.customer_id
    );

The inner query refers to `c.customer_id`.

The result is evaluated in relation to the current customer.

Correlated subqueries can be powerful, but their performance depends on the database optimizer, indexes, data volume, and query structure.

---

## 38. EXISTS

`EXISTS` checks whether a subquery returns at least one row.

It is useful for questions such as:

- Which customers have orders?
- Which employees have a manager?
- Which products have related transactions?
- Which records satisfy a related-table condition?

Example:

    WHERE EXISTS (
        SELECT 1
        FROM orders AS o
        WHERE o.customer_id = c.customer_id
    )

The actual selected value inside an `EXISTS` subquery is normally irrelevant. The existence of at least one qualifying row is what matters.

---

## 39. NOT EXISTS

`NOT EXISTS` is useful for finding records without related rows.

Example:

    SELECT c.customer_name
    FROM customers AS c
    WHERE NOT EXISTS (
        SELECT 1
        FROM orders AS o
        WHERE o.customer_id = c.customer_id
    );

This can be preferable to certain `NOT IN` formulations when NULL behavior could otherwise make the result surprising.

---

## 40. Common Table Expressions

A CTE is defined using `WITH`.

Example:

    WITH employee_compensation AS (
        SELECT
            employee_id,
            salary + COALESCE(commission, 0) AS total_compensation
        FROM employees
    )
    SELECT *
    FROM employee_compensation
    WHERE total_compensation >= 110000;

CTEs provide named intermediate query stages.

They are particularly useful for:

- complex transformations
- improving readability
- separating business logic into stages
- analytical queries
- recursive queries

A CTE does not necessarily represent a permanent stored table.

---

## 41. Window Functions

Window functions perform calculations across related rows while retaining the individual rows.

This is a key distinction from `GROUP BY`.

With `GROUP BY`:

    many rows -> fewer rows

With a window function:

    many rows -> same rows plus calculated values

The script demonstrates:

- `ROW_NUMBER`
- `RANK`
- `AVG(...) OVER (...)`
- `SUM(...) OVER (...)`

Example:

    ROW_NUMBER() OVER (
        PARTITION BY department_id
        ORDER BY salary DESC
    )

This ranks employees within each department.

---

## 42. PARTITION BY

`PARTITION BY` divides rows into independent groups for a window function.

For example:

    PARTITION BY department_id

means each department receives its own window calculation.

Without a partition, the window may operate over the entire result set.

---

## 43. Window ORDER BY

A window function can have its own ordering:

    ORDER BY salary DESC

This determines the logical sequence used by functions such as ranking and running totals.

Window ordering is conceptually distinct from the final query's `ORDER BY`.

A query may calculate rankings according to one order while displaying the final rows according to another.

---

## 44. Running Totals

The script calculates customer running order totals with:

    SUM(amount) OVER (
        PARTITION BY customer_id
        ORDER BY order_date, order_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )

The expression keeps each order row while adding the cumulative value for that customer.

Including `order_id` as a tie-breaker makes the ordering deterministic when two orders have the same date.

---

## 45. Date and Time Expressions

SQLite handles date and time differently from systems with dedicated date and timestamp data types.

SQLite can represent temporal information using:

- text
- real numbers
- integers

The script uses ISO-style date strings such as:

    2025-01-15

Because ISO dates use year-month-day ordering, lexical ordering works naturally for consistently formatted date strings.

For example:

    WHERE hire_date >= '2022-01-01'
      AND hire_date < '2025-01-01'

creates a half-open interval.

Date and time functions are highly dialect-specific, so SQL written for SQLite should be tested before being migrated to another database.

---

## 46. Boolean Expressions

A comparison itself can be an expression.

Example:

    SELECT
        first_name,
        salary,
        salary >= 100000 AS is_high_earner
    FROM employees;

The result contains a calculated indicator.

For portability, applications should not assume that every database represents Boolean results identically.

Some systems have a native Boolean type, while others represent logical values differently.

---

## 47. Parameterized Queries

Parameterized SQL is essential for security when user-controlled values are involved.

The script uses SQLite placeholders:

    SELECT employee_id, first_name
    FROM employees
    WHERE salary >= ?;

The value is supplied separately:

    connection.execute(sql, (100000,))

The database driver handles the parameter as data rather than treating it as part of the SQL syntax.

---

## 48. SQL Injection

An unsafe application might construct SQL by directly concatenating user input.

Conceptually:

    "SELECT ... WHERE email = '" + user_input + "'"

If the input contains SQL syntax, the resulting statement may change meaning.

Parameterized queries prevent this class of injection for values.

This is both a security requirement and a maintainability best practice.

---

## 49. Dynamic Identifiers

Parameters normally represent values, not SQL identifiers.

For example, a placeholder cannot generally be used to safely substitute an arbitrary table or column name.

For dynamic sorting, filtering columns, or table selection, application code should use a strict allowlist.

The script demonstrates:

    allowed_sort_columns = {
        "name": "last_name",
        "salary": "salary",
        "hire_date": "hire_date",
    }

The external request is mapped to a known-safe SQL identifier.

This is substantially safer than inserting arbitrary user input into the SQL statement.

---

## 50. Performance Considerations

A syntactically correct SELECT can still perform poorly.

Important factors include:

- table size
- index design
- selectivity of predicates
- join cardinality
- sorting
- grouping
- aggregation
- subqueries
- window calculations
- data distribution
- database statistics
- optimizer behavior

### Selecting Only Required Columns

Prefer:

    SELECT employee_id, first_name, salary
    FROM employees;

when those are the only required fields.

This can reduce I/O, memory consumption, network transfer, and application processing.

---

## 51. Indexes

The script creates indexes on frequently queried columns such as:

- `department_id`
- `salary`
- `hire_date`
- `customer_id`
- `order_date`

Indexes can make selective lookups much faster.

They are not free.

Indexes consume:

- storage
- memory/cache capacity
- write/update resources

An index that is never useful for important queries can become unnecessary overhead.

Index design should be based on actual access patterns and execution plans.

---

## 52. EXPLAIN QUERY PLAN

The script uses SQLite's:

    EXPLAIN QUERY PLAN

to inspect how SQLite intends to execute queries.

This can reveal whether a query uses an index or performs a broader scan.

Execution plans are essential for diagnosing performance problems.

They should be evaluated using realistic data sizes because a query that performs well against ten rows may behave very differently against ten million rows.

---

## 53. Sargability and Functions on Columns

A predicate such as:

    WHERE email = ?

can often use an ordinary index on `email`.

A predicate such as:

    WHERE LOWER(email) = ?

may prevent a normal index from being used depending on the database and index definition.

Possible solutions include:

- normalizing data during ingestion
- using a suitable functional/expression index when supported
- using database-specific case-insensitive indexing features

The correct choice depends on the database and application requirements.

---

## 54. Edge Cases

The script demonstrates several important edge cases.

### Empty Results

A valid query can return zero rows.

Applications must distinguish between:

- query execution failure
- successful execution with zero rows

### NULL Arithmetic

Arithmetic involving NULL generally results in NULL.

### Division by Zero

Division-by-zero behavior is database-specific. SQLite can produce NULL for numeric division by zero, while other database systems may raise an error.

Production SQL should never assume that all database engines behave identically.

### NULL Ordering

The default position of NULL values in sorting can differ between database systems.

When NULL ordering is important, use a database-supported explicit technique rather than relying on a default.

---

## 55. Common Mistakes

### Mistake 1: Testing NULL with `=`

Incorrect:

    WHERE commission = NULL

Correct:

    WHERE commission IS NULL

### Mistake 2: Assuming row order

Incorrect assumption:

    SELECT *
    FROM employees;

will always return rows in the same order.

Correct approach:

    SELECT *
    FROM employees
    ORDER BY employee_id;

### Mistake 3: Misunderstanding AND and OR

Ambiguous:

    WHERE department_id = 1
       OR department_id = 5
      AND salary > 100000

Prefer explicit parentheses:

    WHERE (department_id = 1 OR department_id = 5)
      AND salary > 100000

### Mistake 4: Using DISTINCT to hide join problems

If a join creates unwanted duplicates, determine why.

Do not automatically use `DISTINCT` to conceal the issue.

### Mistake 5: Treating NULL as zero

NULL means missing or unknown, not necessarily zero.

Only use:

    COALESCE(value, 0)

when zero is semantically correct.

### Mistake 6: Concatenating untrusted values into SQL

Use parameterized queries for values.

### Mistake 7: Assuming one SQL dialect is universal

Functions, data types, date handling, NULL ordering, and pagination syntax differ between database systems.

---

## 56. SQL Dialect Differences

The core concepts of `SELECT`, `FROM`, `WHERE`, aliases, expressions, joins, and filtering are broadly applicable across relational databases.

Exact syntax can differ.

Important areas of variation include:

- string concatenation
- date and time functions
- Boolean data types
- identifier quoting
- pagination syntax
- NULL ordering
- regular expressions
- JSON operations
- generated columns
- functional indexes
- optimizer behavior

The Python script deliberately uses SQLite syntax so that the complete tutorial can run without a separate database server.

---

## 57. Testing SELECT Queries

SELECT statements should be validated using known expectations.

Useful tests include:

- expected row count
- expected values
- NULL behavior
- boundary conditions
- empty results
- join behavior
- duplicate behavior
- ordering
- aggregate results

The script includes executable assertions for:

- active employee count
- known employee lookup
- NULL department count
- minimum salary
- inclusive `BETWEEN` behavior
- empty result sets

Testing SQL is especially important when queries implement business rules.

---

## 58. Production Design Considerations

A production SELECT should be evaluated across several dimensions.

### Correctness

Does the query return precisely the required records?

### Security

Are user-supplied values parameterized?

Are dynamic SQL identifiers restricted through allowlists?

### Performance

Does the query scale with realistic data volumes?

Are appropriate indexes available?

Has the execution plan been inspected where necessary?

### Maintainability

Are table and column aliases meaningful?

Are complicated expressions formatted clearly?

Are business rules expressed explicitly?

### NULL Semantics

Are missing values intentionally handled?

Could a NULL unexpectedly remove a row from a filter?

### Data Quality

Are dates consistently represented?

Can duplicate records occur?

Can relationships be missing?

### Portability

Is the SQL intentionally dependent on SQLite or another specific database?

### Observability

Can slow or frequently executed queries be identified and investigated?

---

## 59. Practical Reporting Query

The script includes a compensation report that combines many fundamental SELECT concepts.

It calculates:

- employee name
- department
- job title
- salary
- commission
- total compensation
- compensation category

It uses:

- `SELECT`
- `FROM`
- `LEFT JOIN`
- table aliases
- column aliases
- arithmetic expressions
- `COALESCE`
- `CASE`
- `WHERE`
- `ORDER BY`

This demonstrates an important SQL principle: simple constructs become powerful when composed carefully.

---

## 60. Advanced Customer Analysis

The script also builds customer-level reports from `customers` and `orders`.

The query demonstrates:

- `LEFT JOIN`
- `COUNT`
- `SUM`
- `AVG`
- `MAX`
- `COALESCE`
- `GROUP BY`
- CTEs
- `CASE`

The `LEFT JOIN` is important because customers with no orders can still be included in the report.

Without the left join, customers lacking matching order rows could disappear from the result.

---

## 61. SELECT Expressions Versus WHERE Conditions

A useful mental model is:

- `WHERE` determines which rows qualify.
- `SELECT` determines what values are projected for those rows.

Example:

    SELECT
        first_name,
        salary,
        salary * 12 AS annual_salary
    FROM employees
    WHERE salary >= 100000;

The `WHERE` clause selects employees whose salary meets the threshold.

The `SELECT` list then calculates annual salary for the qualifying employees.

Keeping these responsibilities conceptually separate makes complex queries easier to reason about.

---

## 62. Query Readability

SQL style affects correctness because difficult-to-read SQL is harder to validate.

Useful practices include:

- Put major clauses on separate lines.
- Indent expressions consistently.
- Use descriptive aliases.
- Qualify columns in multi-table queries.
- Use parentheses for complicated logical expressions.
- Give calculated columns meaningful names.
- Keep related conditions together.
- Prefer explicit columns over unnecessary `SELECT *`.

A readable query is easier to debug, review, test, and maintain.

---

## 63. Core Syntax Reference

### Basic SELECT

    SELECT column1, column2
    FROM table_name;

### SELECT with WHERE

    SELECT column1, column2
    FROM table_name
    WHERE condition;

### Alias

    SELECT column1 AS readable_name
    FROM table_name;

### Table Alias

    SELECT t.column1
    FROM table_name AS t;

### Expression

    SELECT salary * 12 AS annual_salary
    FROM employees;

### Multiple Conditions

    SELECT *
    FROM employees
    WHERE salary >= 100000
      AND active = 1;

### IN

    SELECT *
    FROM employees
    WHERE department_id IN (1, 4, 5);

### BETWEEN

    SELECT *
    FROM employees
    WHERE salary BETWEEN 80000 AND 120000;

### LIKE

    SELECT *
    FROM employees
    WHERE job_title LIKE '%Engineer%';

### NULL

    SELECT *
    FROM employees
    WHERE commission IS NULL;

### CASE

    SELECT
        first_name,
        CASE
            WHEN salary >= 100000 THEN 'High'
            ELSE 'Standard'
        END AS salary_class
    FROM employees;

### DISTINCT

    SELECT DISTINCT department_id
    FROM employees;

### ORDER BY

    SELECT first_name, salary
    FROM employees
    ORDER BY salary DESC;

### Aggregate

    SELECT AVG(salary)
    FROM employees;

### GROUP BY

    SELECT department_id, AVG(salary)
    FROM employees
    GROUP BY department_id;

### HAVING

    SELECT department_id, COUNT(*)
    FROM employees
    GROUP BY department_id
    HAVING COUNT(*) >= 2;

### JOIN

    SELECT e.first_name, d.department_name
    FROM employees AS e
    JOIN departments AS d
        ON e.department_id = d.department_id;

### CTE

    WITH employee_data AS (
        SELECT employee_id, salary
        FROM employees
    )
    SELECT *
    FROM employee_data;

### Window Function

    SELECT
        first_name,
        salary,
        RANK() OVER (ORDER BY salary DESC) AS salary_rank
    FROM employees;

---

## 64. Conceptual Distinctions

| Concept | Purpose |
|---|---|
| `SELECT` | Defines values and columns returned |
| `FROM` | Defines the source of rows |
| `WHERE` | Filters individual rows |
| Column alias | Names a result expression |
| Table alias | Names a table reference within the query |
| Expression | Calculates or evaluates a value |
| `DISTINCT` | Removes duplicate result combinations |
| `ORDER BY` | Controls result ordering |
| `LIMIT` | Restricts the number of returned rows |
| `GROUP BY` | Creates groups for aggregation |
| `HAVING` | Filters groups |
| `JOIN` | Combines related row sources |
| `CASE` | Performs conditional value selection |
| `COALESCE` | Selects the first non-NULL value |
| Scalar subquery | Produces a single derived value |
| `EXISTS` | Tests whether related rows exist |
| CTE | Names an intermediate query |
| Window function | Calculates across related rows without collapsing them |

---

## 65. Fundamental Rules to Retain

1. `SELECT` determines the result projection.
2. `FROM` determines the source.
3. `WHERE` filters rows.
4. Use `IS NULL` and `IS NOT NULL` for NULL testing.
5. Use parentheses when Boolean logic could be ambiguous.
6. `BETWEEN` includes both boundaries.
7. `COUNT(*)` counts rows, while `COUNT(column)` ignores NULL values.
8. `GROUP BY` reduces rows into groups for aggregation.
9. `HAVING` filters aggregate groups.
10. `ORDER BY` is required when deterministic result ordering matters.
11. Column aliases improve result readability.
12. Table aliases improve clarity and are essential for self-joins and multi-table queries.
13. `CASE` implements conditional expressions.
14. `COALESCE` handles NULL fallback values.
15. `DISTINCT` should not be used to conceal incorrect relational logic.
16. Parameterized queries should be used for user-supplied values.
17. Dynamic SQL identifiers require strict validation or allowlisting.
18. Indexes should be evaluated according to actual workload and query plans.
19. SQL syntax and semantics vary between database systems.
20. Production SQL should be tested against realistic data and edge cases.
