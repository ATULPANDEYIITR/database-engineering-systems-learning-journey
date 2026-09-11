# Sorting and limiting in SQL

## Topic introduction

Sorting and limiting are fundamental SQL operations used to control the order and size of query results.

The main SQL clauses covered in this tutorial are:

- `ORDER BY`
- `ASC`
- `DESC`
- `LIMIT`
- `OFFSET`

The Python script uses SQLite through Python's built-in `sqlite3` module. It creates an in-memory database containing employees, products, and sales, then executes progressively more advanced SQL queries against that data.

The examples move from basic sorting to multi-column ordering, pagination, deterministic results, ranking, indexes, query plans, security considerations, and keyset pagination.

## Basic SQL query structure

A common SQL query has the following structure:

    SELECT columns
    FROM table
    WHERE conditions
    GROUP BY grouping_columns
    HAVING group_conditions
    ORDER BY sorting_expression
    LIMIT row_count
    OFFSET rows_to_skip;

Not every query needs every clause.

For sorting and limiting, the most important relationship is:

    SELECT ...
    FROM ...
    WHERE ...
    ORDER BY ...
    LIMIT ...
    OFFSET ...;

`ORDER BY` determines the ordering of the result set.

`LIMIT` restricts how many rows are returned.

`OFFSET` skips a number of rows before returning the requested result.

## ORDER BY

`ORDER BY` sorts the rows returned by a query.

Basic syntax:

    SELECT column1, column2
    FROM table_name
    ORDER BY column_name;

For example:

    SELECT name, salary
    FROM employees
    ORDER BY salary;

When no direction is specified, ascending order is normally used.

The explicit form is:

    SELECT name, salary
    FROM employees
    ORDER BY salary ASC;

The important principle is that `ORDER BY` defines the presentation order of the result.

Without `ORDER BY`, SQL does not guarantee a particular row order. A query may appear to return rows in insertion order during testing, but application code should never depend on that accidental behavior.

## ASC

`ASC` means ascending order.

For numeric values:

    10
    20
    30
    40

For text, ascending order generally follows the database's collation rules.

For dates represented in a suitable sortable format:

    2024-01-01
    2024-06-01
    2025-01-01

Ascending order is useful when looking for:

- lowest prices
- lowest salaries
- oldest records
- earliest dates
- alphabetical names
- smallest quantities

Example:

    SELECT name, salary
    FROM employees
    ORDER BY salary ASC;

## DESC

`DESC` means descending order.

For numbers:

    40
    30
    20
    10

For dates:

    2025-01-01
    2024-06-01
    2024-01-01

Example:

    SELECT name, salary
    FROM employees
    ORDER BY salary DESC;

Descending order is commonly used for:

- highest salaries
- highest prices
- highest scores
- newest records
- largest sales amounts
- most recent transactions

A common business query is:

    SELECT name, salary
    FROM employees
    ORDER BY salary DESC
    LIMIT 5;

This means "return the five highest-ranked employees according to salary."

## ORDER BY with multiple columns

SQL can sort by several columns.

Example:

    ORDER BY department ASC, salary DESC;

The first column has the highest sorting priority.

The database first sorts by `department`.

Within each department, it then sorts by `salary` in descending order.

A more detailed ordering might be:

    ORDER BY department ASC,
             salary DESC,
             name ASC;

The sorting priority is therefore:

1. Department ascending
2. Salary descending within each department
3. Name ascending when both department and salary are equal

This is called hierarchical or lexicographic ordering.

## Tie-breaking

A critical issue occurs when multiple rows have the same value.

Suppose several employees have a salary of `85000`.

This query:

    ORDER BY salary DESC
    LIMIT 5;

defines the salary ordering but does not fully define the order of employees who have equal salaries.

For deterministic results, a unique or sufficiently unique tie-breaker can be added:

    ORDER BY salary DESC, employee_id ASC
    LIMIT 5;

Here:

- `salary` is the primary ordering key.
- `employee_id` is the secondary ordering key.

This is particularly important for pagination.

## Sorting by expressions

`ORDER BY` can use expressions rather than only stored columns.

The Python script calculates total compensation using:

    salary + bonus

The query can sort by:

    ORDER BY salary + bonus DESC;

An expression can also be given an alias:

    SELECT
        name,
        salary,
        bonus,
        salary + bonus AS total_compensation
    FROM employees
    ORDER BY total_compensation DESC;

Aliases can make analytical queries easier to read.

## LIMIT

`LIMIT` restricts the number of rows returned.

Example:

    SELECT name, salary
    FROM employees
    ORDER BY salary DESC
    LIMIT 5;

This returns at most five rows.

`LIMIT` is commonly used for:

- top-N queries
- dashboards
- search result previews
- product listings
- leaderboards
- recent transactions
- API responses
- recommendation lists

The key distinction is that `LIMIT` does not define which rows are important.

`ORDER BY` defines the ranking.

`LIMIT` then restricts the number of ranked rows returned.

Therefore:

    ORDER BY salary DESC
    LIMIT 5

means the top five by salary.

By contrast:

    LIMIT 5

only means that five rows should be returned. It does not define which five rows represent the "top" five.

## OFFSET

`OFFSET` skips rows before returning results.

Example:

    SELECT name, salary
    FROM employees
    ORDER BY salary DESC
    LIMIT 5 OFFSET 5;

The database first considers the sorted result.

The first five rows are skipped.

The next five rows are returned.

Conceptually:

    sorted rows
    ├── rows 1-5   -> skipped
    └── rows 6-10  -> returned

`OFFSET 0` means that no rows are skipped.

## LIMIT and OFFSET together

The standard conceptual pattern is:

    LIMIT page_size OFFSET rows_to_skip

For a page-based interface:

    OFFSET = (page_number - 1) * page_size

For example, with five records per page:

Page 1:

    OFFSET = (1 - 1) * 5
           = 0

Page 2:

    OFFSET = (2 - 1) * 5
           = 5

Page 3:

    OFFSET = (3 - 1) * 5
           = 10

Page 4:

    OFFSET = (4 - 1) * 5
           = 15

This is the basis of traditional page-number pagination.

## Pagination

Pagination divides a large result set into smaller sections.

A typical API may request:

    page = 3
    page_size = 10

The application calculates:

    offset = (3 - 1) * 10
           = 20

The resulting SQL is conceptually:

    SELECT ...
    FROM employees
    ORDER BY employee_id ASC
    LIMIT 10 OFFSET 20;

This returns rows 21 through 30 of the sorted result, assuming enough records exist.

Pagination is common in:

- websites
- REST APIs
- administrative dashboards
- e-commerce systems
- reporting applications
- employee directories
- financial transaction systems

## Why ORDER BY matters for pagination

Pagination without deterministic ordering is unsafe.

For example:

    SELECT name
    FROM employees
    LIMIT 10 OFFSET 10;

does not specify which ten rows constitute the second page.

A better query is:

    SELECT employee_id, name
    FROM employees
    ORDER BY employee_id ASC
    LIMIT 10 OFFSET 10;

For more complex sorting:

    ORDER BY salary DESC, employee_id ASC

The secondary key makes ties deterministic.

## WHERE with ORDER BY and LIMIT

Filtering and sorting are commonly combined.

Example:

    SELECT name, salary
    FROM employees
    WHERE department = 'Engineering'
    ORDER BY salary DESC
    LIMIT 5;

The intended logical operation is:

1. Consider employees.
2. Keep Engineering employees.
3. Sort them by salary.
4. Return the first five.

This is a standard pattern for filtered top-N queries.

## GROUP BY with ORDER BY and LIMIT

`LIMIT` can also operate on aggregated results.

Example:

    SELECT
        department,
        AVG(salary) AS average_salary
    FROM employees
    GROUP BY department
    ORDER BY average_salary DESC
    LIMIT 3;

This does not return three employees.

It returns three departments ranked by average salary.

The distinction between row-level ranking and group-level ranking is important.

## DISTINCT with ORDER BY and LIMIT

`DISTINCT` removes duplicate result values.

For example:

    SELECT DISTINCT salary
    FROM employees
    ORDER BY salary DESC
    LIMIT 3;

This returns the three highest unique salary levels.

This differs from:

    SELECT name, salary
    FROM employees
    ORDER BY salary DESC
    LIMIT 3;

The second query returns three employees, while the first returns three distinct salary values.

## Finding the nth row

`LIMIT` and `OFFSET` can be used to select a particular position.

For example:

    ORDER BY salary DESC
    LIMIT 1 OFFSET 1;

returns the second row in the sorted result.

The general pattern is:

    LIMIT 1 OFFSET n - 1

for the nth row.

This does not necessarily mean the nth distinct value.

If duplicate salary values exist, the second row and second-highest unique salary are different concepts.

For the second distinct salary level:

    SELECT DISTINCT salary
    FROM employees
    ORDER BY salary DESC
    LIMIT 1 OFFSET 1;

## LIMIT 1

`LIMIT 1` is useful when only the first sorted row is required.

For example, the highest-paid employee:

    SELECT employee_id, name, salary
    FROM employees
    ORDER BY salary DESC, employee_id ASC
    LIMIT 1;

This is different from simply calculating:

    MAX(salary)

`MAX(salary)` returns the highest value.

`ORDER BY ... LIMIT 1` can return the complete row associated with that value.

If several rows tie, the secondary ordering determines which row is returned.

## NULL values and sorting

`NULL` represents a missing or unknown value.

It is not equivalent to:

- zero
- an empty string
- false
- a missing database row

The position of `NULL` values in sorted results can depend on the database system.

SQLite normally places `NULL` before non-NULL values for ascending order and after non-NULL values for descending order.

Applications should explicitly define the desired behavior when NULL placement affects business logic.

One SQLite technique is:

    ORDER BY performance_score IS NULL ASC,
             performance_score DESC;

The first expression separates non-NULL and NULL values.

The second expression sorts the known scores.

A more explicit approach using `CASE` is:

    ORDER BY
        CASE
            WHEN performance_score IS NULL THEN 1
            ELSE 0
        END,
        performance_score DESC;

This places non-NULL scores before NULL scores.

## Sorting text

Text sorting follows the database's collation rules.

A basic query is:

    SELECT name
    FROM employees
    ORDER BY name ASC;

For case-insensitive ordering in SQLite, the script demonstrates:

    ORDER BY name COLLATE NOCASE ASC;

Real applications may require more sophisticated locale-aware sorting rules.

Alphabetical ordering is therefore not always identical across different database systems or locales.

## Sorting dates

Date sorting requires a consistent representation.

The script stores dates in ISO-style format:

    YYYY-MM-DD

For this representation, lexicographic order matches chronological order.

For example:

    2024-01-10
    2024-03-20
    2024-12-31

can be sorted correctly as text.

For production systems, database-native date/time types or a clearly defined canonical representation should be used where available.

The query for newest records is:

    ORDER BY hire_date DESC;

The query for oldest records is:

    ORDER BY hire_date ASC;

## JOIN with ORDER BY and LIMIT

Sorting can be applied after combining multiple tables.

For example, sales can be joined with products and employees:

    SELECT
        s.sale_id,
        p.product_name,
        e.name AS salesperson,
        s.sale_amount
    FROM sales AS s
    JOIN products AS p
        ON p.product_id = s.product_id
    JOIN employees AS e
        ON e.employee_id = s.employee_id
    ORDER BY s.sale_amount DESC
    LIMIT 5;

This produces the largest sales transactions across the joined dataset.

## Top sales by employee

A more advanced query combines:

- `JOIN`
- `GROUP BY`
- `COUNT`
- `SUM`
- `ORDER BY`
- `LIMIT`

For example:

    SELECT
        e.name,
        COUNT(s.sale_id) AS transactions,
        SUM(s.sale_amount) AS total_revenue
    FROM employees AS e
    JOIN sales AS s
        ON s.employee_id = e.employee_id
    GROUP BY e.employee_id, e.name
    ORDER BY total_revenue DESC
    LIMIT 5;

The query ranks employees based on aggregated revenue rather than individual transactions.

## Conditional sorting with CASE

Sometimes alphabetical or numerical sorting is not the desired business order.

Suppose departments should appear in this priority:

1. Engineering
2. Finance
3. Sales
4. Marketing

A `CASE` expression can define that custom order:

    ORDER BY
        CASE department
            WHEN 'Engineering' THEN 1
            WHEN 'Finance' THEN 2
            WHEN 'Sales' THEN 3
            WHEN 'Marketing' THEN 4
            ELSE 5
        END;

This technique is useful when the required order comes from business rules rather than natural alphabetical or numerical ordering.

## Top-N per group

A global `LIMIT` does not solve a top-N-per-group problem.

For example:

    ORDER BY salary DESC
    LIMIT 2

returns only two employees across the entire company.

It does not return the top two employees from every department.

For top-N per group, window functions are useful.

The script uses:

    ROW_NUMBER() OVER (
        PARTITION BY department
        ORDER BY salary DESC, employee_id ASC
    )

This assigns a position separately within each department.

The outer query can then select:

    WHERE position <= 2

This produces the top two employees in every department.

## ROW_NUMBER, RANK, and DENSE_RANK

These window functions solve different ranking problems.

### ROW_NUMBER

Every row gets a unique position.

Example conceptually:

    Salary    ROW_NUMBER
    110000    1
    105000    2
    105000    3
    98000     4

Even tied values receive different row numbers.

### RANK

Tied values receive the same rank, and gaps appear.

Example:

    Salary    RANK
    110000    1
    105000    2
    105000    2
    98000     4

### DENSE_RANK

Tied values receive the same rank without gaps.

Example:

    Salary    DENSE_RANK
    110000    1
    105000    2
    105000    2
    98000     3

The choice depends on the business meaning of ranking.

## Top salary levels versus top employees

Consider:

    ORDER BY salary DESC
    LIMIT 3;

This means three rows.

If the third position contains tied employees, some equally qualified employees may be excluded.

If the requirement is:

"Return everyone belonging to the top three salary levels."

then `DENSE_RANK()` is more appropriate:

    DENSE_RANK() OVER (ORDER BY salary DESC)

followed by:

    WHERE salary_level <= 3

This distinction is important in analytics and reporting.

## OFFSET pagination limitations

`LIMIT/OFFSET` is easy to understand, but it has limitations.

Suppose a query requests:

    LIMIT 50 OFFSET 1000000;

The database may need to process or walk through a large number of preceding rows before returning the requested page.

This can make deep pagination expensive.

There is another problem with changing data.

Suppose page 1 contains records:

    1, 2, 3, 4, 5

Before page 2 is requested, a new record is inserted near the beginning.

The result positions shift.

Page 2 may then contain a duplicate from page 1 or skip a record that should have appeared.

Deterministic ordering helps define the sequence, but it does not make offset pagination immune to concurrent inserts and deletes.

## Keyset pagination

Keyset pagination is also called cursor pagination.

Instead of saying:

    OFFSET 1000000

the application remembers the last record from the previous page.

For an increasing unique identifier:

    WHERE employee_id > ?
    ORDER BY employee_id ASC
    LIMIT ?

If the last record on the previous page has:

    employee_id = 100

the next query can use:

    WHERE employee_id > 100

This allows the database to continue from a known position.

Keyset pagination is often preferable for:

- large datasets
- infinite scrolling
- transaction feeds
- social feeds
- continuously changing data
- APIs where sequential navigation is more important than direct page jumping

## Composite keyset pagination

A more complicated example occurs when sorting by:

    ORDER BY salary DESC, employee_id ASC

The next page condition needs to preserve that exact ordering.

If the previous page ended with:

    salary = 85000
    employee_id = 10

the next page can use:

    WHERE
        salary < 85000
        OR (salary = 85000 AND employee_id > 10)

This means:

- move to a lower salary, or
- remain at the same salary and move to a larger employee ID

This preserves the ordering across pages.

## LIMIT/OFFSET versus keyset pagination

### LIMIT/OFFSET

Advantages:

- Simple syntax
- Easy to understand
- Easy to implement
- Supports direct page numbers
- Convenient for small datasets

Limitations:

- Large offsets can be expensive
- Results can shift when the underlying dataset changes
- Deep pagination can become inefficient

### Keyset pagination

Advantages:

- Efficient for sequential navigation
- Avoids large offsets
- Works well with large datasets
- Well suited to changing feeds

Limitations:

- More complex query conditions
- Direct navigation to an arbitrary page is difficult
- Requires an appropriate stable ordering key
- Cursor state must be managed by the application

The appropriate approach depends on the application's requirements.

## Performance considerations

Sorting can be computationally expensive.

A conventional comparison-based sort has approximately `O(n log n)` comparison complexity, although an actual database query can use very different strategies depending on:

- indexes
- query optimizer decisions
- data distribution
- storage engine
- available memory
- statistics
- filtering conditions
- database implementation

An important distinction is that `LIMIT` does not automatically mean the database processes only the limited number of rows.

For example:

    ORDER BY salary DESC
    LIMIT 10;

The database still needs an efficient way to determine the ten highest salaries.

An appropriate index may allow the database to retrieve rows in the required order without performing a full explicit sort.

## Indexes and ORDER BY

An index can sometimes improve sorting performance.

The script creates:

    CREATE INDEX idx_employees_salary
    ON employees(salary);

This can help queries involving salary ordering.

A composite index can be more useful for queries combining filtering and sorting.

For:

    WHERE department = 'Engineering'
    ORDER BY salary DESC, employee_id ASC
    LIMIT 5;

a possible index structure is:

    CREATE INDEX idx_department_salary_id
    ON employees(department, salary DESC, employee_id ASC);

The best index depends on the complete workload.

Indexes have costs:

- additional storage
- additional maintenance during inserts
- additional maintenance during updates
- additional maintenance during deletes
- potential optimizer complexity

An index should therefore be justified by real query requirements and measurements.

## EXPLAIN QUERY PLAN

The Python script demonstrates SQLite's `EXPLAIN QUERY PLAN`.

This is useful for understanding how the database intends to execute a query.

For example:

    EXPLAIN QUERY PLAN
    SELECT name, salary
    FROM employees
    ORDER BY salary DESC
    LIMIT 5;

The query plan can indicate whether the database is using an index or needs a temporary sorting operation.

Production performance analysis should use actual query plans and representative workloads rather than assumptions.

## Filtering and sorting together

Indexes are especially important when a query repeatedly combines filtering and sorting.

Consider:

    WHERE department = ?
    ORDER BY salary DESC, employee_id ASC
    LIMIT 20;

An index beginning with the filtering column can sometimes support both operations.

The conceptual index is:

    (department, salary DESC, employee_id ASC)

The exact usefulness depends on the database optimizer and the distribution of values.

## Security considerations

Sorting itself is not normally a security risk, but dynamic SQL can introduce SQL injection vulnerabilities.

A common application requirement is:

"Allow the user to choose whether employees are sorted by salary, name, or hire date."

It is unsafe to directly concatenate unrestricted user input into SQL.

For values, parameterized queries should be used:

    WHERE department = ?

Identifiers such as column names generally cannot be supplied through the same parameter mechanism.

A safer design is an allowlist:

    allowed_sort_columns = {
        "name": "name",
        "salary": "salary",
        "hire_date": "hire_date",
        "performance": "performance_score",
    }

The application accepts only a predefined key and maps it to a trusted SQL identifier.

The same principle applies to `ASC` and `DESC`.

Allowed application choices can be mapped to trusted SQL syntax:

    {
        "ascending": "ASC",
        "descending": "DESC"
    }

Unrestricted user input should never be inserted directly into SQL syntax.

## Pagination input validation

Applications should validate pagination parameters before executing a query.

Useful rules include:

- page must be an integer
- page must be at least 1
- page size must be an integer
- page size must be at least 1
- page size should have a reasonable maximum

For example, an API might reject:

    page = 0

or:

    page_size = 1000000

A maximum page size prevents clients from requesting unnecessarily large result sets and protects database and application resources.

The script uses a maximum page size of 100.

This value is an application policy, not a universal SQL requirement.

## Parameterized LIMIT and OFFSET

The Python `sqlite3` interface supports parameter binding for values.

The script demonstrates:

    LIMIT ?
    OFFSET ?

with parameters supplied separately.

This is preferable to constructing SQL using raw user-provided values.

Parameterization improves safety and prevents many SQL injection and quoting problems.

## Dynamic ORDER BY considerations

There is an important distinction between SQL values and SQL identifiers.

This is appropriate for a value:

    WHERE department = ?

A column name is different.

The application cannot generally write:

    ORDER BY ?

and expect the placeholder to represent an arbitrary column identifier.

For dynamic sorting, the safer pattern is:

1. Accept a controlled application-level sort key.
2. Check it against an allowlist.
3. Map it to a trusted SQL column name.
4. Construct the SQL using only that trusted mapping.
5. Parameterize ordinary values.

This provides both flexibility and security.

## Edge cases

### LIMIT 0

    LIMIT 0

returns no rows.

This can be useful when an application needs metadata or query validation without requesting actual records, depending on the database system.

### OFFSET larger than the result set

If the query has fewer rows than the requested offset, the result is empty.

For example:

    LIMIT 5 OFFSET 1000

returns no rows when the result contains fewer than 1001 rows.

### LIMIT larger than the available rows

If `LIMIT` is greater than the number of available rows, the database simply returns all remaining rows.

### OFFSET 0

`OFFSET 0` means no rows are skipped.

### Negative LIMIT or OFFSET

Behavior for negative values can vary between database systems.

Applications should validate these values rather than relying on database-specific behavior.

## Common mistakes

### Mistake: LIMIT without meaningful ORDER BY

Incorrect for a top-N requirement:

    SELECT name, salary
    FROM employees
    LIMIT 5;

This does not mean "five highest-paid employees."

Correct:

    SELECT name, salary
    FROM employees
    ORDER BY salary DESC
    LIMIT 5;

### Mistake: Forgetting tie-breakers

Potentially nondeterministic:

    ORDER BY salary DESC
    LIMIT 10;

More deterministic:

    ORDER BY salary DESC, employee_id ASC
    LIMIT 10;

### Mistake: Treating OFFSET as a ranking mechanism

`OFFSET` does not rank records.

It only skips rows in the established result ordering.

### Mistake: Confusing nth row with nth distinct value

This:

    ORDER BY salary DESC
    LIMIT 1 OFFSET 1;

finds the second row.

This:

    SELECT DISTINCT salary
    ORDER BY salary DESC
    LIMIT 1 OFFSET 1;

finds the second distinct salary level.

### Mistake: Assuming insertion order

A table is not inherently an ordered list.

If order matters, specify it with `ORDER BY`.

### Mistake: Using arbitrary dynamic SQL

Unvalidated dynamic sort columns or directions can create security vulnerabilities.

Use an allowlist for SQL identifiers and parameter binding for values.

## Real-world applications

Sorting and limiting appear in many systems.

### E-commerce

Examples include:

- cheapest products
- most expensive products
- highest-rated products
- newest products
- lowest-stock products
- paginated product listings

Example:

    SELECT product_name, price
    FROM products
    ORDER BY price ASC
    LIMIT 20;

### Employee systems

Examples include:

- highest-paid employees
- newest employees
- department rankings
- employee directory pagination
- highest performance scores

### Financial systems

Examples include:

- latest transactions
- largest transactions
- highest-value accounts
- recent payments
- ranked financial metrics

### Analytics

Examples include:

- top departments by revenue
- top products by sales
- highest-performing salespeople
- highest average salary departments
- top-N groups

### APIs

Sorting and limiting are frequently exposed through query parameters such as:

    page
    page_size
    sort
    direction

These inputs should be validated and mapped to controlled SQL behavior.

## Implementation considerations

The Python script uses `sqlite3` because it is part of Python's standard library.

The database is created in memory:

    sqlite3.connect(":memory:")

This makes the tutorial self-contained.

Three tables are created:

- `employees`
- `products`
- `sales`

The data is inserted programmatically, so the script does not require external CSV files, databases, or packages.

The script also contains reusable helper functions for:

- executing queries
- displaying rows
- validating pagination
- retrieving paginated employee records
- testing sorting behavior

## Testing considerations

The script includes automated tests for:

- descending salary ordering
- `LIMIT`
- `OFFSET`
- multiple-column ordering
- pagination input validation
- keyset pagination

Testing sorting is especially important because a query may return correct-looking data while failing to guarantee deterministic ordering.

A useful test should verify the actual sequence of returned values rather than merely checking that rows exist.

## Production considerations

For production applications, sorting and limiting should be designed together with:

- deterministic ordering
- appropriate indexes
- validated pagination inputs
- parameterized values
- controlled dynamic sort fields
- realistic query-plan analysis
- suitable page sizes
- concurrency behavior
- database-specific syntax
- appropriate pagination strategy

Small datasets may work perfectly with `LIMIT/OFFSET`, while very large datasets and continuously changing feeds may benefit from keyset pagination.

## Important distinctions

| Concept | Purpose |
|---|---|
| `ORDER BY` | Defines result ordering |
| `ASC` | Sorts in ascending order |
| `DESC` | Sorts in descending order |
| `LIMIT` | Restricts the number of returned rows |
| `OFFSET` | Skips rows before returning results |
| `DISTINCT` | Removes duplicate result values |
| `GROUP BY` | Creates groups for aggregation |
| `ROW_NUMBER()` | Assigns a unique row position |
| `RANK()` | Assigns rankings with gaps after ties |
| `DENSE_RANK()` | Assigns rankings without gaps after ties |
| Keyset pagination | Uses a cursor condition instead of a large offset |
| Index | Can accelerate filtering and/or ordering |

## Query patterns covered by the script

The script demonstrates the following important patterns:

    SELECT ...
    FROM employees
    ORDER BY salary ASC;

    SELECT ...
    FROM employees
    ORDER BY salary DESC;

    SELECT ...
    FROM employees
    ORDER BY salary DESC
    LIMIT 5;

    SELECT ...
    FROM employees
    ORDER BY salary DESC
    LIMIT 5 OFFSET 5;

    SELECT ...
    FROM employees
    WHERE department = ?
    ORDER BY salary DESC, employee_id ASC
    LIMIT ? OFFSET ?;

    SELECT DISTINCT salary
    FROM employees
    ORDER BY salary DESC
    LIMIT 3;

    SELECT ...
    FROM employees
    ORDER BY salary + bonus DESC
    LIMIT 5;

    SELECT ...
    FROM employees
    ORDER BY performance_score IS NULL,
             performance_score DESC;

    SELECT ...
    FROM employees
    ORDER BY
        CASE department
            WHEN 'Engineering' THEN 1
            WHEN 'Finance' THEN 2
            WHEN 'Sales' THEN 3
            WHEN 'Marketing' THEN 4
            ELSE 5
        END;

    SELECT ...
    FROM employees
    WHERE employee_id > ?
    ORDER BY employee_id ASC
    LIMIT ?;

## Conceptual execution model

For a query such as:

    SELECT name, salary
    FROM employees
    WHERE department = 'Engineering'
    ORDER BY salary DESC
    LIMIT 5 OFFSET 10;

the important conceptual stages are:

1. Start with the employee rows.
2. Apply the department filter.
3. Establish the requested salary ordering.
4. Skip the first ten rows of that ordered result.
5. Return the next five rows.

Understanding this relationship prevents many common mistakes.

## Practical interpretation of common requirements

"Give me the five highest salaries."

Use:

    ORDER BY salary DESC
    LIMIT 5

"Give me the five lowest prices."

Use:

    ORDER BY price ASC
    LIMIT 5

"Give me the next ten employees after the first twenty."

Use:

    ORDER BY employee_id ASC
    LIMIT 10 OFFSET 20

"Give me the highest-paid Engineering employees."

Use:

    WHERE department = 'Engineering'
    ORDER BY salary DESC

"Give me page three with ten records per page."

Use:

    LIMIT 10 OFFSET 20

"Give me the top two employees from every department."

Use a window function such as `ROW_NUMBER()` rather than a global `LIMIT`.

"Give me everyone tied within the top three salary levels."

Use `DENSE_RANK()` rather than a simple `LIMIT 3`.

"Give me the next page efficiently from a very large ordered dataset."

Consider keyset pagination instead of a large `OFFSET`.

## Scope of the Python implementation

The Python script provides executable examples for:

- basic `SELECT`
- ascending sorting
- descending sorting
- multi-column sorting
- expression-based sorting
- aliases
- `LIMIT`
- `OFFSET`
- page-based pagination
- filtered pagination
- top-N queries
- bottom-N queries
- `DISTINCT`
- aggregation
- joins
- date sorting
- text sorting
- NULL handling
- deterministic ordering
- dynamic sorting with allowlists
- parameterized pagination
- keyset pagination
- composite keyset pagination
- query plans
- indexes
- composite indexes
- top-N per group
- ranking functions
- conditional sorting
- application-level validation
- automated tests

The examples are implemented against a complete in-memory SQLite dataset, allowing the entire script to run independently.
