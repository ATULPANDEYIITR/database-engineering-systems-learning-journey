# SQL subqueries: scalar, correlated, nested and multi-level subqueries

## Topic introduction

A subquery is a SQL query embedded inside another SQL statement. The inner query produces a value, a set of values, a row, or a result set that the outer query uses to make a decision or construct its result.

Subqueries are useful when a query needs information that must first be calculated from another relation. Typical examples include finding employees whose salary exceeds the company average, identifying departments with active projects, comparing an employee with the average salary of that employee's department, and filtering rows according to the existence or absence of related records.

The central distinction is the relationship between the outer query and the inner query.

A non-correlated subquery can normally be evaluated independently of the current outer row. A correlated subquery refers to a column from the outer query and therefore depends on the current outer-row context.

This distinction is fundamental to understanding scalar, correlated, nested, and multi-level subqueries.

---

## Relational model used in the implementations

The examples use a small organizational database containing:

- `departments`
- `employees`
- `projects`
- `assignments`
- `sales`
- `performance_reviews`

The principal relationships are:

- Each employee belongs to a department.
- An employee can have a manager.
- A department can have multiple projects.
- Employees can generate sales.
- Employees can have performance reviews.

These relationships allow the implementations to demonstrate subqueries against individual rows, groups, related rows, and multiple levels of derived information.

---

## Fundamental terminology

### Outer query

The outer query is the SQL statement that contains the subquery.

For example, in a query that selects employees and uses another query to calculate the average salary, the employee query is the outer query.

### Subquery

A subquery is the embedded `SELECT` statement.

A simple conceptual structure is:

`SELECT ... FROM ... WHERE value > (SELECT ...);`

### Inner query

The inner query is another term for the subquery.

### Scalar subquery

A scalar subquery returns one value.

Typical examples include:

- `AVG(salary)`
- `MAX(salary)`
- `MIN(salary)`
- `SUM(amount)`
- `COUNT(*)`

A scalar subquery is normally used where the outer expression expects a single value.

### Correlated subquery

A correlated subquery refers to a column from the outer query.

Conceptually:

`WHERE e.salary > (SELECT AVG(e2.salary) FROM employees AS e2 WHERE e2.department_id = e.department_id)`

The inner query depends on `e.department_id`, which belongs to the current outer row.

### Nested subquery

A nested subquery contains another subquery within it.

For example:

`WHERE department_id IN (SELECT department_id FROM departments WHERE budget > (SELECT AVG(budget) FROM departments))`

The budget comparison itself contains another query.

### Multi-level subquery

A multi-level subquery contains several logical layers of calculation.

A possible chain is:

1. Calculate project budget by department.
2. Calculate the average of those departmental budgets.
3. Select departments above that average.
4. Select employees belonging to those departments.

### Derived table

A subquery in the `FROM` clause can produce a temporary relational result that the outer query treats as a table.

For example:

`FROM (SELECT department_id, COUNT(*) AS employee_count FROM employees GROUP BY department_id) AS metrics`

A derived table is especially useful when an intermediate aggregation needs to be filtered or joined.

---

## Why subqueries are needed

A normal filter can compare a column with a constant:

`WHERE salary > 100000`

A subquery allows the comparison value itself to come from the database:

`WHERE salary > (SELECT AVG(salary) FROM employees)`

This changes the query from a fixed rule to a data-dependent rule.

The database calculates the reference value and then uses it in the outer operation.

---

## Scalar subqueries

A scalar subquery produces one value.

The Python implementation demonstrates this using SQLite:

`SELECT employee_name, salary FROM employees WHERE salary > (SELECT AVG(salary) FROM employees)`

The inner query calculates the company-wide average salary. The outer query returns employees whose salaries are greater than that value.

The important conceptual structure is:

`outer expression > (single value)`

### Scalar subquery in the SELECT list

A scalar subquery can also calculate a value displayed for every outer row.

The Python implementation uses:

`salary / (SELECT AVG(salary) FROM employees)`

This allows each employee's salary to be compared with the company average.

A scalar subquery in a `SELECT` list can be useful for calculated reporting columns, although repeated correlated calculations may require careful performance analysis.

---

## Single-row versus scalar subqueries

A scalar subquery is concerned with returning one value.

A single-row subquery can technically return one row containing one or more columns, but the surrounding expression determines what shape is valid.

For example, a scalar comparison such as:

`salary = (SELECT salary FROM employees WHERE employee_id = 2)`

requires the subquery to provide one compatible value.

A production query should make its expected cardinality clear. If a query assumes a single row but the database can contain multiple matching rows, the query may fail or behave differently depending on the database engine.

A uniqueness constraint is often useful when the data model guarantees that a lookup should identify only one row.

---

## IN subqueries

`IN` is used when the subquery produces a set of values.

Example:

`WHERE department_id IN (SELECT department_id FROM departments WHERE budget > 1300000)`

The inner query returns department IDs.

The outer query then asks whether each employee's `department_id` belongs to that set.

The conceptual question is:

"Is this value a member of the result produced by the subquery?"

This differs from a scalar comparison.

Scalar comparison:

`salary > (SELECT AVG(salary) FROM employees)`

Set membership:

`department_id IN (SELECT department_id FROM departments WHERE budget > 1300000)`

---

## NOT IN

`NOT IN` expresses non-membership.

For example:

`WHERE department_id NOT IN (SELECT department_id FROM departments WHERE location = 'Mumbai')`

A significant issue arises when the subquery can return `NULL`.

SQL uses three-valued logic:

- `TRUE`
- `FALSE`
- `UNKNOWN`

A comparison involving `NULL` generally produces `UNKNOWN`, not `TRUE` or `FALSE`.

Consequently, `NOT IN` can produce surprising results if the subquery contains `NULL`.

When the intended business question is "return rows for which no related row exists", `NOT EXISTS` is often a clearer and safer expression.

---

## EXISTS

`EXISTS` asks whether the subquery returns at least one row.

The actual selected value inside the `EXISTS` subquery is normally irrelevant.

A common form is:

`WHERE EXISTS (SELECT 1 FROM projects WHERE projects.department_id = departments.department_id)`

The database only needs to establish whether a matching row exists.

This makes `EXISTS` naturally suitable for questions such as:

- Does this department have an active project?
- Does this employee have a sale?
- Does this customer have an order?
- Does this account have a transaction?
- Does this product have inventory?

The Python and C++ implementations use existence checks to model these relationships.

---

## NOT EXISTS

`NOT EXISTS` asks whether the subquery produces no rows.

A typical example is:

`WHERE NOT EXISTS (SELECT 1 FROM sales WHERE sales.employee_id = employees.employee_id)`

This identifies employees for whom no matching sale exists.

`NOT EXISTS` is particularly important for anti-join logic.

Typical uses include:

- customers without orders,
- employees without reviews,
- products without sales,
- departments without active projects,
- accounts without transactions.

---

## EXISTS versus IN

`IN` and `EXISTS` can sometimes produce equivalent results, but their semantics are different.

`IN` asks whether a value belongs to a set.

`EXISTS` asks whether at least one matching row exists.

For example:

`WHERE department_id IN (SELECT department_id FROM departments WHERE location = 'Bengaluru')`

can be conceptually expressed using:

`WHERE EXISTS (SELECT 1 FROM departments WHERE departments.department_id = employees.department_id AND departments.location = 'Bengaluru')`

The second form makes the row relationship explicit.

The choice should be based on meaning, NULL behavior, readability, and measured execution characteristics.

---

## Correlated subqueries

A correlated subquery refers to a value from the outer query.

Consider:

`SELECT e.employee_name, e.salary FROM employees AS e WHERE e.salary > (SELECT AVG(e2.salary) FROM employees AS e2 WHERE e2.department_id = e.department_id)`

The inner query contains:

`e2.department_id = e.department_id`

The first `e2` belongs to the inner query.

The second `e` belongs to the outer query.

Therefore, the inner query depends on the current outer employee.

The business question is:

"Is this employee's salary greater than the average salary of this employee's department?"

That is fundamentally different from:

"Is this employee's salary greater than the average salary of the entire company?"

The first question requires correlation.

---

## Logical execution model for a correlated subquery

A useful conceptual model is:

1. Select an outer row.
2. Read the correlated values from that row.
3. Evaluate the inner query using those values.
4. Produce the inner result.
5. Apply the outer condition.
6. Continue with the next outer row.

For teaching purposes, this explains why correlated queries can appear to perform repeated work.

It should not be interpreted as a guaranteed physical execution strategy.

A database optimizer can transform a correlated subquery into another execution strategy. It may use indexes, joins, hashing, sorting, materialization, or other techniques.

The actual execution plan depends on the database engine, schema, indexes, statistics, data distribution, and query structure.

---

## Correlated EXISTS

`EXISTS` becomes especially expressive when the relationship between the outer and inner rows matters.

Example:

`WHERE EXISTS (SELECT 1 FROM projects AS p WHERE p.department_id = d.department_id AND p.status = 'ACTIVE')`

For each department, the inner query checks for a matching active project.

The condition is correlated because `p.department_id` is compared with `d.department_id` from the outer query.

---

## Correlated NOT EXISTS and top-per-group queries

A classic pattern identifies the highest-paid employee in each department:

`WHERE NOT EXISTS (SELECT 1 FROM employees AS higher WHERE higher.department_id = e.department_id AND higher.salary > e.salary)`

The logic is:

- Consider the current employee.
- Search for another employee in the same department.
- If a strictly higher salary exists, reject the current employee.
- If no strictly higher salary exists, keep the employee.

This also handles ties naturally.

If two employees have the same highest salary, neither has a strictly higher employee, so both are returned.

This demonstrates an important property of relational queries: business rules must be expressed precisely.

"Highest salary" can mean:

- one arbitrary employee,
- every employee tied for highest salary,
- exactly one employee after applying a secondary ordering rule.

The SQL must match the intended definition.

---

## Nested subqueries

Nested subqueries contain one subquery inside another.

Example:

`WHERE department_id IN (SELECT department_id FROM departments WHERE budget > (SELECT AVG(budget) FROM departments))`

The innermost query calculates the average department budget.

The middle query selects departments whose budget exceeds that value.

The outer query selects employees belonging to those departments.

The logical sequence is:

`employees -> qualifying departments -> average budget`

Nested queries are useful because each level can represent a distinct relational question.

Deep nesting can become difficult to maintain, so production SQL should be structured according to clarity rather than nesting depth alone.

---

## Multi-level subqueries

Multi-level subqueries extend the nesting idea into several logical stages.

The Python, JavaScript, and C++ implementations model a departmental project-budget analysis.

The calculation consists of:

- active project budgets per department,
- the average of those departmental totals,
- departments whose total exceeds that average,
- employees belonging to those departments.

The dependency chain can be represented conceptually as:

`projects -> department totals -> average departmental total -> qualifying departments -> employees`

This is a genuine multi-level relational problem because each stage depends on the result of another stage.

---

## Subqueries in different SQL clauses

Subqueries can appear in several places.

### WHERE

The most common form:

`WHERE salary > (SELECT AVG(salary) FROM employees)`

### SELECT

A scalar subquery can produce a calculated output column:

`SELECT employee_name, (SELECT AVG(salary) FROM employees) AS company_average FROM employees`

### FROM

A subquery can create a derived table:

`FROM (SELECT department_id, COUNT(*) AS employee_count FROM employees GROUP BY department_id) AS metrics`

### HAVING

A grouped result can be compared with a scalar subquery:

`HAVING AVG(salary) > (SELECT AVG(salary) FROM employees)`

The appropriate placement depends on whether the subquery is being used as a value, filter, grouped condition, or relational input.

---

## Aggregate subqueries

Aggregate functions are particularly useful in subqueries.

Important functions include:

- `COUNT`
- `SUM`
- `AVG`
- `MIN`
- `MAX`

A global aggregate can create a reference value:

`SELECT AVG(salary) FROM employees`

A correlated aggregate can create a group-specific reference:

`SELECT AVG(e2.salary) FROM employees AS e2 WHERE e2.department_id = e.department_id`

The first is non-correlated.

The second is correlated.

---

## Aggregate subqueries and NULL

Aggregate functions require careful interpretation.

`AVG`, `SUM`, `MIN`, and `MAX` generally ignore `NULL` values.

If there are no applicable rows, aggregate behavior can produce `NULL`, depending on the function.

For example, `SUM` over no matching rows can return `NULL`.

Applications may use `COALESCE` when a business rule requires a concrete fallback:

`COALESCE((SELECT SUM(amount) ...), 0)`

The Python implementation demonstrates this concept with review and sales calculations.

---

## Derived tables

A derived table is a subquery in the `FROM` clause.

Example:

`SELECT department_name, employee_count FROM (SELECT department_id, COUNT(*) AS employee_count FROM employees GROUP BY department_id) AS metrics`

The inner query produces an intermediate relational result.

The outer query can then:

- filter it,
- sort it,
- join it,
- aggregate it again,
- calculate additional expressions.

Derived tables are particularly useful when an intermediate calculation must be treated as a relational object.

---

## Nested subqueries versus derived tables

A nested subquery emphasizes dependency between expressions.

A derived table emphasizes an intermediate relation.

For example, a complex departmental calculation may be easier to understand as:

`departments -> derived department metrics -> final filter`

rather than as many levels of scalar expressions.

The correct choice depends on readability, database support, optimizer behavior, and the shape of the required result.

---

## Subqueries versus JOINs

Many subqueries can be rewritten as joins.

Subquery form:

`SELECT e.employee_name FROM employees AS e WHERE e.department_id IN (SELECT d.department_id FROM departments AS d WHERE d.budget > 1300000)`

Equivalent join-oriented form:

`SELECT e.employee_name FROM employees AS e JOIN departments AS d ON d.department_id = e.department_id WHERE d.budget > 1300000`

A join explicitly describes the relationship between rows.

An `IN` subquery emphasizes set membership.

Neither construct is automatically superior in every situation.

The database optimizer may transform one representation into an execution plan similar to the other.

The implementations deliberately show both approaches.

---

## Subqueries versus CTEs

A Common Table Expression uses `WITH` to name an intermediate query.

A deeply nested expression can sometimes be rewritten as a sequence of named relational stages.

For example, a multi-level analysis can conceptually become:

`WITH department_totals AS (...)`

followed by:

`average_totals AS (...)`

followed by:

`qualifying_departments AS (...)`

followed by the final query.

CTEs can improve readability when a complex subquery is reused or when several logical stages need descriptive names.

The topic of subqueries does not require CTEs, but understanding the relationship helps when designing maintainable SQL.

---

## Subqueries versus window functions

Window functions calculate values across related rows while preserving individual rows.

For example:

`AVG(salary) OVER (PARTITION BY department_id)`

calculates a department average while retaining each employee row.

A correlated subquery can express the same business idea:

`(SELECT AVG(e2.salary) FROM employees AS e2 WHERE e2.department_id = e.department_id)`

A window function may be more direct when the required result is a row-level value compared with a group statistic.

The Python implementation uses a correlated subquery.

The Python SQLite implementation also demonstrates a window-function alternative.

The C++ implementation explains how indexing and precomputed group information can reduce repeated relational work in an application-level model.

---

## C++ case study

The C++ program models an industry-style employee intelligence system.

The system contains:

- departments,
- employees,
- projects,
- sales,
- performance reviews.

The case study is deliberately more structured than isolated syntax examples.

### Domain structures

The C++ program defines:

- `Department`
- `Employee`
- `Project`
- `Sale`
- `Review`
- `DepartmentMetrics`

These structures represent rows from relational tables.

`std::optional<int>` is used for manager IDs to model the possibility that an employee does not have a recorded manager.

### Validation

The program validates:

- unique department IDs,
- unique employee IDs,
- valid foreign-key-like references,
- positive employee salaries,
- non-negative project budgets,
- non-negative sales,
- review scores between 0 and 100.

This corresponds to database integrity constraints.

### Scalar subquery implementation

`companyAverageSalary` calculates a single company-wide average.

The outer employee loop then compares each employee against that scalar result.

This models:

`salary > (SELECT AVG(salary) FROM employees)`

### Correlated subquery implementation

`departmentAverageSalary` calculates the average salary for a specified department.

The employee processing function supplies the current employee's department ID.

This models the dependency of an inner SQL query on the current outer row.

### IN implementation

`departmentsAboveBudget` constructs a set of qualifying department IDs.

Employees are then tested for membership in that set.

This models:

`department_id IN (subquery)`

The use of `unordered_set` represents an application-level optimization for membership tests.

### EXISTS implementation

`hasActiveProject` checks whether a department has at least one active project.

It stops once a matching project is found.

This mirrors the semantic purpose of `EXISTS`.

### NOT EXISTS implementation

`hasSale` is used with negation to identify employees without sales.

This models:

`NOT EXISTS (SELECT 1 FROM sales ...)`

### Correlated NOT EXISTS

The C++ function `hasHigherPaidEmployeeInSameDepartment` implements the logic behind a top-per-group query.

An employee qualifies as a department salary leader if no employee in the same department has a greater salary.

### Multi-level query

The C++ program calculates:

1. active project budget by department,
2. average of those departmental budgets,
3. qualifying departments,
4. employees in those departments.

This corresponds directly to a multi-level subquery design.

### Derived-table processing

`DepartmentMetrics` represents an intermediate relational result.

The program calculates employee count, average salary, active project budget, and total sales for each department.

The resulting vector behaves conceptually like a derived table.

### Advanced employee intelligence rule

The program identifies employees who satisfy all of the following conditions:

- active employee,
- salary above department average,
- at least one sale,
- best review score above the company review average,
- department has an active project.

This combines scalar calculations, correlated calculations, `EXISTS` logic, and aggregate logic.

---

## JavaScript implementation

The JavaScript file provides a language-level relational model using arrays, maps, sets, and functions.

It does not require an external database package.

This makes the relational reasoning visible without hiding the behavior behind a database driver.

### Scalar calculations

Functions such as `average`, `sum`, `max`, and `min` provide the aggregation behavior required by the examples.

### IN

A JavaScript `Set` is used to represent a set returned by a subquery.

The resulting membership test corresponds to SQL `IN`.

### EXISTS

JavaScript `Array.prototype.some()` is useful for demonstrating existence semantics.

For example:

`projects.some(...)`

answers whether at least one matching project exists.

### Correlated logic

A loop over employees combined with a filtered group of employees demonstrates the same dependency as a correlated SQL subquery.

### Multi-level processing

JavaScript arrays are used to represent intermediate relational results.

This is useful for understanding how one query result can become the input to another query layer.

### Derived-table model

`departmentMetrics` represents a derived result set.

The outer filtering step then operates on the intermediate result.

### Performance comparison

The JavaScript implementation also contrasts repeated scanning with precomputed maps.

This illustrates why repeated correlated operations can become expensive when implemented naively.

A relational database may solve the same problem using indexes, joins, hashing, materialization, or optimizer transformations.

---

## Python implementation

Python uses the standard-library `sqlite3` module to execute real SQL.

This makes the Python implementation the most direct demonstration of actual database subquery syntax among the three implementations.

### Database creation

The script creates an in-memory SQLite database.

This avoids external files and makes the study file self-contained.

### Schema

The database defines relational tables with:

- primary keys,
- foreign keys,
- unique constraints,
- `CHECK` constraints,
- indexes.

### Scalar subqueries

The script demonstrates:

- company average salary,
- maximum salary,
- department averages,
- calculated reference metrics.

### IN and NOT IN

The script demonstrates set membership and explicitly discusses the NULL-related risks of `NOT IN`.

### EXISTS and NOT EXISTS

The script uses real SQLite queries to identify departments with active projects and employees without sales.

### Correlated subqueries

The script compares employee salary with the average salary of the employee's own department.

### Nested and multi-level subqueries

The script builds several layers of relational calculation, including active project budgets and departmental comparisons.

### Subqueries in multiple clauses

The Python implementation demonstrates subqueries in:

- `SELECT`,
- `WHERE`,
- `FROM`,
- `HAVING`.

### Query plans

The script uses SQLite's `EXPLAIN QUERY PLAN` to inspect how the database approaches a correlated query.

This is important because SQL performance cannot reliably be inferred from syntax alone.

---

## Cardinality

Cardinality describes how many rows a query returns.

Subqueries can have different expected cardinalities.

### Scalar

Expected:

- one row,
- one column,
- one value.

Example:

`SELECT AVG(salary) FROM employees`

### Set

Expected:

- zero or more rows,
- one column.

Example:

`SELECT department_id FROM departments WHERE budget > 1300000`

### EXISTS

Expected:

- zero or more rows,
- but only existence matters.

### Derived table

Can contain:

- zero or more rows,
- multiple columns.

Understanding cardinality prevents many SQL errors.

---

## Common mistakes

### Treating every subquery as scalar

This is incorrect:

`WHERE salary > (SELECT salary FROM employees)`

if the inner query can return many employees.

The operator expects a scalar result, while the query may produce many rows.

### Using `=` when the subquery returns multiple values

If multiple values are expected, `IN` may be appropriate.

### Ignoring NULL with NOT IN

A nullable subquery column can produce unexpected three-valued-logic behavior.

`NOT EXISTS` is often a better expression for "no matching row exists".

### Forgetting correlation

A company average and a department average are different calculations.

This:

`SELECT AVG(salary) FROM employees`

does not depend on the outer employee.

This:

`SELECT AVG(e2.salary) FROM employees AS e2 WHERE e2.department_id = e.department_id`

does.

### Correlating on the wrong column

A correlated query must use the correct relationship.

If the outer and inner rows are joined using an incorrect key, the result can be logically wrong even if the SQL is syntactically valid.

### Repeating complex subqueries unnecessarily

Repeated logic makes SQL difficult to maintain.

A CTE, derived table, window function, or pre-aggregation may improve the structure.

### Assuming a correlated query always executes once per outer row

That is a useful conceptual model, but not a guarantee about the physical execution plan.

The optimizer may transform the query.

### Ignoring indexes

A correlated relationship such as:

`inner.department_id = outer.department_id`

can benefit from an index on the inner table's correlation column.

### Optimizing before measuring

A theoretically expensive query may perform adequately on a small dataset.

A seemingly simple query may perform poorly at production scale.

Execution plans and representative benchmarks are more reliable than assumptions.

---

## NULL and three-valued logic

SQL does not use only two logical states.

The logical states are:

- `TRUE`
- `FALSE`
- `UNKNOWN`

An expression involving an unknown value can produce `UNKNOWN`.

For example:

`salary = NULL`

is not a correct test for missing data.

Use:

`salary IS NULL`

or:

`salary IS NOT NULL`

This distinction becomes particularly important with:

- `NOT IN`,
- comparisons,
- joins,
- aggregate results,
- optional relationships.

---

## Security considerations

Subqueries themselves are not inherently a security vulnerability.

The primary application-level concern is unsafe construction of SQL.

Avoid:

`"SELECT ... WHERE name = '" + userInput + "'"`

Use parameterized queries instead.

Python's `sqlite3` implementation demonstrates parameter binding using `?`.

The principle is:

- SQL structure is supplied as SQL.
- User data is supplied as parameters.

This prevents data from being interpreted as SQL syntax in the normal parameter-binding model.

Database permissions should also follow least privilege.

An application account should receive only the permissions required by its workload.

---

## Performance considerations

Subquery performance depends on:

- database engine,
- table size,
- indexes,
- data distribution,
- statistics,
- selectivity,
- join relationships,
- aggregation strategy,
- optimizer behavior,
- memory,
- disk access,
- concurrency.

### Correlated subqueries

A correlated query can conceptually involve repeated inner lookups.

If an outer query contains `N` rows and an unoptimized inner search scans `N` rows for each outer row, a naive implementation can approach `O(N²)` work.

A database optimizer may transform this into a much better execution plan.

### Indexes

Useful indexes may include:

`employees(department_id)`

`sales(employee_id)`

`performance_reviews(employee_id)`

`projects(department_id)`

Indexes can make correlated lookups and existence tests substantially more efficient.

Indexes also have costs:

- storage,
- insertion overhead,
- update overhead,
- deletion overhead,
- maintenance,
- additional optimizer decisions.

### Query plans

Important queries should be inspected with the database's query-plan facilities.

The Python implementation uses:

`EXPLAIN QUERY PLAN`

for SQLite.

Other database engines provide their own execution-plan mechanisms.

---

## Advanced design considerations

### Choose the expression that matches the question

Use `IN` when the question is membership.

Use `EXISTS` when the question is existence.

Use a scalar subquery when one value is required.

Use correlation when the inner calculation depends on the current outer row.

Use a derived table when an intermediate result needs to behave like a table.

Use a window function when the problem involves row-level calculations against groups.

### Keep business semantics explicit

A query should make clear:

- what population is being measured,
- which rows are included,
- how NULL is treated,
- whether ties are allowed,
- whether inactive records count,
- whether empty sets are valid,
- whether duplicate relationships are possible.

### Separate calculation stages

Complex analytical queries become easier to reason about when each logical stage has a clear purpose.

For example:

`projects -> departmental totals -> average total -> qualifying departments -> employees`

This decomposition also helps with testing.

---

## Edge cases

### Empty subquery result

A subquery may return no rows.

The outer operator must have appropriate semantics for an empty result.

### NULL result

An aggregate or nullable expression can return `NULL`.

The outer query must handle this deliberately.

### Duplicate values

An `IN` subquery may contain duplicate values. Membership semantics generally do not require duplicates to be meaningful.

### Ties

A top-per-group query can return multiple rows when multiple rows share the same maximum.

### Missing relationships

An employee may have no sales or no reviews.

`EXISTS` and `NOT EXISTS` can express these cases naturally.

### Multiple matching rows

A scalar lookup that unexpectedly produces multiple rows indicates a mismatch between the query's assumptions and the data model.

### Large datasets

A query that works well with a few thousand rows may require a different structure at millions or billions of rows.

---

## Portability considerations

SQL syntax differs between database systems.

The implementations use SQLite for executable SQL examples because SQLite is available through Python's standard library.

Some SQL features differ across systems.

For example, quantified comparison syntax involving `ANY` and `ALL` is not uniformly available in SQLite.

The Python implementation therefore demonstrates aggregate equivalents such as:

`value > (SELECT MAX(value) ...)`

where that is semantically appropriate.

Production applications should validate the exact syntax and optimizer behavior against the target database engine.

---

## ANY and ALL

Some SQL database systems support:

`value > ALL (subquery)`

and:

`value > ANY (subquery)`

These expressions compare one value against multiple values produced by a subquery.

Conceptually:

`> ALL`

means the value must satisfy the comparison against every relevant value.

`> ANY`

means the value must satisfy the comparison against at least one relevant value.

Equivalent aggregate formulations can sometimes be used.

For example, a condition similar to:

`value > ALL (subquery)`

can often be represented as:

`value > (SELECT MAX(value) FROM ...)`

when empty-set and NULL semantics are compatible.

Such rewrites must be validated rather than applied mechanically.

---

## Testing strategy

The Python, JavaScript, and C++ implementations contain validation or test logic.

Important subquery tests should include:

- normal matching rows,
- no matching rows,
- multiple matching rows,
- duplicate values,
- NULL values,
- ties,
- empty groups,
- inactive records,
- invalid foreign-key-like relationships,
- unexpected cardinality.

A production test suite should verify both correctness and performance characteristics where the query is business-critical.

---

## Implementation comparison

| Aspect | Python | JavaScript | C++ |
|---|---|---|---|
| Database execution | Real SQLite | In-memory relational model | In-memory relational model |
| Scalar subqueries | Direct SQL | Function-based model | Function-based model |
| Correlation | Real SQL correlation | Array filtering | Explicit relational functions |
| EXISTS | Real SQL | `some()` | Explicit search |
| IN | Real SQL | `Set` membership | `unordered_set` |
| Multi-level logic | Nested SQL | Intermediate arrays | Intermediate structures |
| Derived results | SQL derived tables | Arrays | `DepartmentMetrics` |
| NULL modeling | SQLite NULL | JavaScript `null` | `std::optional` |
| Performance study | SQLite query plan | Algorithmic comparison | Indexed lookup model |
| Security | Parameterized SQLite queries | Parameterized SQL pattern | Application architecture discussion |
| Main educational value | Actual SQL syntax | Relational logic in application code | Systems-oriented implementation |

---

## Why the three languages are useful together

Python provides the most direct executable SQL environment because `sqlite3` is part of the standard library.

JavaScript demonstrates how applications can represent relational operations using arrays, maps, sets, and functions. This is useful for understanding how database results are consumed and transformed at the application layer.

C++ emphasizes explicit data structures, validation, memory-oriented design, algorithmic complexity, and indexed lookup strategies.

The three implementations therefore demonstrate different layers of the same conceptual problem.

---

## Practical applications

Subqueries are common in:

- business intelligence,
- financial reporting,
- customer analytics,
- fraud detection,
- inventory systems,
- human-resource systems,
- sales analytics,
- banking systems,
- project management,
- compliance reporting,
- security analytics,
- operational dashboards,
- recommendation systems,
- enterprise resource planning.

Typical questions include:

"Which customers have spent more than the average customer?"

"Which employees earn more than their department average?"

"Which departments have no active projects?"

"Which products have never been sold?"

"Which accounts have transactions above the account-level average?"

"Which regions have revenue above the company average?"

"Which employees have a review score above the organizational average?"

These are naturally expressed using scalar, correlated, nested, and existence-based subqueries.

---

## Production considerations

Production SQL should be designed with the following concerns in mind:

- Correct relational semantics.
- Explicit NULL handling.
- Appropriate indexes.
- Parameterized input.
- Database-specific syntax validation.
- Execution-plan inspection.
- Representative performance testing.
- Appropriate transaction boundaries.
- Referential integrity.
- Appropriate constraints.
- Clear naming.
- Maintainable query structure.
- Controlled database permissions.
- Monitoring of expensive queries.

Subqueries are not inherently an optimization problem or an anti-pattern. They are a relational language construct. Their suitability depends on the business question, data model, query shape, database optimizer, and operational requirements.

---

## Core distinctions

| Concept | Main question |
|---|---|
| Scalar subquery | What single value should be used? |
| `IN` subquery | Is this value in the returned set? |
| `NOT IN` subquery | Is this value absent from the returned set? |
| `EXISTS` | Does at least one matching row exist? |
| `NOT EXISTS` | Does no matching row exist? |
| Correlated subquery | What result applies to this outer row? |
| Nested subquery | What result should another subquery consume? |
| Multi-level subquery | What happens when several relational calculations depend on each other? |
| Derived table | What intermediate result should behave like a table? |
| JOIN alternative | Can the relationship be expressed directly between relations? |
| Window-function alternative | Can a group calculation be retained alongside each row? |

---

## Important rules

A scalar subquery should produce a compatible single value.

An `IN` subquery should normally produce one column.

`EXISTS` is concerned with whether rows exist, not with the value selected by the inner query.

A correlated subquery references the outer query.

Nested subqueries can contain further subqueries.

Multi-level subqueries represent several dependent relational calculations.

`NOT EXISTS` is often preferable to `NOT IN` for anti-existence logic when nullable values are possible.

NULL is not equivalent to zero, an empty string, or a normal value.

The database optimizer determines physical execution, so logical SQL structure should not be confused with guaranteed execution order.

Query plans and representative benchmarks should be used for performance analysis.

Parameterized SQL should be used when external input is incorporated into a query.

The actual Python, JavaScript, and C++ implementations demonstrate these principles through executable relational examples and a complete employee intelligence case study.
