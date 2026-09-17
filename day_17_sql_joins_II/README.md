# SQL Joins II: FULL JOIN, CROSS JOIN, SELF JOIN

## Topic

This study covers three important SQL join patterns:

- `FULL OUTER JOIN`
- `CROSS JOIN`
- `SELF JOIN`

The implementations also use `INNER JOIN` and `LEFT JOIN` as reference points because the behavior of the three main join types is easier to understand when compared with ordinary matching and outer-join operations.

The accompanying Python program uses SQLite to demonstrate executable SQL. The JavaScript program models relational join behavior with native JavaScript data structures. The C++ program develops the same concepts into an industry-style organizational data case study using standard-library containers.

---

## Introduction to SQL joins

A SQL join combines rows from two relations according to a relationship expressed by a join condition.

A typical equality join has the structure:

`FROM table_a AS a JOIN table_b AS b ON a.key = b.key`

The join condition determines which rows are considered related.

A critical concept is that a join does not necessarily preserve the number of rows in either input. If one row on the left matches several rows on the right, the left row appears several times in the result. This is normal relational behavior and is particularly important for one-to-many and many-to-many relationships.

The three joins studied here have different purposes:

| Join | Main behavior | Typical use |
|---|---|---|
| `INNER JOIN` | Matching rows only | Ordinary relationships |
| `LEFT JOIN` | All left rows plus matches | Optional relationships |
| `FULL OUTER JOIN` | All rows from both sides | Reconciliation |
| `CROSS JOIN` | Every possible pair | Cartesian combinations |
| `SELF JOIN` | A table joined to itself | Hierarchies and intra-table relationships |

---

## Fundamental terminology

### Left relation

The table or result appearing on the left side of a join.

For example:

`FROM departments AS d`

makes `departments` the left relation.

### Right relation

The table or result appearing on the right side.

For example:

`JOIN employees AS e`

makes `employees` the right relation.

### Join predicate

The condition that determines whether two rows match.

A common equality predicate is:

`d.department_id = e.department_id`

### Matching row

A pair of rows for which the join predicate evaluates to `TRUE`.

### Unmatched row

A row for which no row on the other side satisfies the join predicate.

Outer joins preserve some or all unmatched rows.

### NULL-extended row

When an outer join preserves a row that has no match, columns belonging to the missing side are represented by `NULL`.

### Cardinality

Cardinality describes the number of rows in a relation or result.

Join cardinality is especially important because one input row can produce multiple result rows.

---

## INNER JOIN as the reference model

An `INNER JOIN` returns only rows that satisfy the join condition.

The Python implementation demonstrates employees joined to departments:

`e.department_id = d.department_id`

Employees whose department exists appear in the result.

An employee without a department does not appear.

Departments without employees also do not appear.

Conceptually:

`INNER JOIN = matching rows only`

This behavior is useful as a baseline for understanding `FULL OUTER JOIN`.

---

## FULL OUTER JOIN

A `FULL OUTER JOIN` preserves rows from both input relations.

For matching rows, values from both sides are combined.

For a left-only row, the right-side columns become `NULL`.

For a right-only row, the left-side columns become `NULL`.

Conceptually:

`FULL OUTER JOIN = matches + left-only rows + right-only rows`

A typical query is structurally:

`SELECT ... FROM departments AS d FULL OUTER JOIN employees AS e ON d.department_id = e.department_id`

The Python and JavaScript implementations classify the resulting rows as:

- `matched`
- `department_without_employee`
- `employee_without_department`

This classification is useful because it makes the purpose of a full join explicit.

---

## Why FULL OUTER JOIN is useful

Full joins are particularly useful when two datasets must be reconciled.

Examples include:

- comparing two customer lists
- reconciling accounting records
- comparing current and historical inventories
- identifying missing master data
- comparing two system exports
- detecting orphan records
- validating migration completeness

Suppose one system contains customers and another contains orders.

A full join can expose three categories:

`matched`

The customer and order relationship exists.

`customer_without_order`

A customer exists but no matching order exists.

`orphan_order`

An order exists but no matching customer exists.

This makes a full join useful for data-quality analysis.

---

## FULL OUTER JOIN and NULL

NULL values in an outer join do not necessarily mean that the original database column was NULL.

An outer join can create a NULL because no matching row existed.

For example, if the `Research` department has no employee, the result can contain:

`Research | NULL`

The `NULL` represents the missing employee side of the relationship.

This distinction is important during analysis.

---

## Portable FULL JOIN construction

Database engines differ in their support for join syntax.

Where native `FULL OUTER JOIN` is unavailable, a common conceptual construction uses two outer-join result sets.

The first part preserves the left relation:

`LEFT JOIN`

The second part finds right-side rows that have no left-side match.

The two sets can then be combined with `UNION`.

The Python implementation contains this portable approach as well as a native `FULL OUTER JOIN` attempt when supported by the installed SQLite version.

`UNION` removes duplicate complete rows.

`UNION ALL` retains duplicates.

The choice must therefore be based on the intended semantics.

---

## CROSS JOIN

A `CROSS JOIN` produces a Cartesian product.

If relation A contains `m` rows and relation B contains `n` rows, the Cartesian product contains:

`m × n`

row combinations.

For example:

`2 employees × 4 projects = 8 combinations`

The Python, JavaScript, and C++ implementations demonstrate this behavior.

A cross join does not require a matching predicate.

Its defining property is that every left row is paired with every right row.

---

## Legitimate CROSS JOIN applications

A Cartesian product is not inherently incorrect.

It can be useful for:

- scenario generation
- product combinations
- test matrices
- scheduling combinations
- generating date and time grids
- permission combinations
- parameter sweeps
- simulation inputs

For example, a planning system might intentionally generate every combination of:

`employee × shift`

before applying availability rules.

A cross join is appropriate when the Cartesian product itself is the desired intermediate relation.

---

## Accidental CROSS JOINs

A Cartesian product can also be an expensive mistake.

A missing or incorrect join condition can cause two large tables to be combined without the intended relationship.

If one table has 100,000 rows and another has 200,000 rows, a Cartesian product has a theoretical size of:

`100,000 × 200,000 = 20,000,000,000`

rows.

This illustrates why join predicates must be reviewed carefully.

---

## SELF JOIN

A `SELF JOIN` joins a table to another logical reference of the same table.

The table is not physically duplicated.

SQL simply gives the same table different aliases.

The employee hierarchy is a classic example.

The `employees` table contains:

`employee_id`

and:

`manager_id`

The `manager_id` refers back to another row in the same `employees` table.

A query can conceptually use:

`employees AS employee`

and:

`employees AS manager`

with the relationship:

`employee.manager_id = manager.employee_id`

This transforms a flat employee table into an employee-manager relationship.

---

## Why aliases matter in a SELF JOIN

Without aliases, it becomes difficult to distinguish the two logical roles.

Consider:

`employee.employee_name`

versus:

`manager.employee_name`

Both values originate from the same physical table, but they represent different roles.

Aliases therefore provide semantic clarity.

---

## SELF JOIN for peer relationships

A self join can compare rows within the same table.

For example, employees belonging to the same department can be paired.

A naive self join can generate:

`A,B`

and:

`B,A`

as separate rows.

It can also generate:

`A,A`

if self-pairs are not excluded.

The Python, JavaScript, and C++ implementations use a condition equivalent to:

`a.employee_id < b.employee_id`

This ensures that:

- an employee is not paired with itself
- each unordered pair appears only once

This pattern is useful when comparing records inside one relation.

---

## SELF JOIN applications

Common applications include:

- employee-manager hierarchies
- organizational reporting structures
- category-parent relationships
- bill-of-materials structures
- social relationships
- graph-like relationships stored in relational tables
- comparing records within the same table
- finding peer groups
- identifying duplicate or similar records

For deeper hierarchical traversal, recursive common table expressions may be more appropriate than repeatedly writing self joins.

---

## Join cardinality

Join cardinality is one of the most important practical concepts in SQL.

Suppose one department has five employees.

A join between that department and its employees produces five rows for that department.

If the same result is later joined to another one-to-many relation containing four projects, the intermediate relationship can multiply again.

This is why a query can unexpectedly produce far more rows than either source table.

Before using `SUM`, `AVG`, `COUNT`, or another aggregate, the expected relationship cardinality should be understood.

---

## One-to-one relationships

In a one-to-one relationship, one row generally matches at most one row on the other side.

A join normally preserves a relatively small number of combinations.

Uniqueness constraints often help enforce such relationships.

---

## One-to-many relationships

In a one-to-many relationship, one row on one side can match many rows on the other side.

The department-to-employee relationship is an example:

`department -> employees`

One department can have many employees.

A join therefore naturally produces multiple result rows for a single department.

---

## Many-to-many relationships

Many-to-many relationships require an intermediate relationship table.

The example uses:

`employee_projects`

It contains:

- `employee_id`
- `project_id`
- `allocation_percent`

This allows:

`employee -> many projects`

and:

`project -> many employees`

The join therefore proceeds through the junction table.

This is generally preferable to storing a list of project identifiers directly inside an employee row.

---

## LEFT JOIN and aggregation

The Python, JavaScript, and C++ implementations demonstrate departments with employee counts and average salaries.

A `LEFT JOIN` is important when departments with zero employees must remain visible.

An inner join would remove departments without employees.

With an outer join, the missing employee side becomes `NULL`.

A key SQL distinction is:

`COUNT(e.employee_id)`

versus:

`COUNT(*)`

For a department with no employee:

`COUNT(e.employee_id)` returns `0`

while `COUNT(*)` can count the NULL-extended row produced by the outer join.

This difference is a frequent source of aggregation errors.

---

## ON versus WHERE

The placement of conditions can change the meaning of an outer join.

Consider a left join between departments and employees.

A condition inside `ON` controls which employees qualify as matches.

A condition in `WHERE` filters the already-produced join result.

For example:

`LEFT JOIN employees e ON d.department_id = e.department_id AND e.salary >= 100000`

can preserve departments even if they have no employee earning at least 100,000.

By contrast:

`LEFT JOIN employees e ON d.department_id = e.department_id WHERE e.salary >= 100000`

can remove rows whose employee side is `NULL`.

This is why `ON` and `WHERE` should not be treated as interchangeable in outer joins.

---

## SQL NULL and three-valued logic

SQL uses three logical states:

- `TRUE`
- `FALSE`
- `UNKNOWN`

A comparison involving `NULL` generally produces `UNKNOWN`.

Therefore:

`department_id = NULL`

is not the correct way to test for NULL.

Use:

`department_id IS NULL`

or:

`department_id IS NOT NULL`

This behavior differs from ordinary Boolean reasoning and must be considered when working with outer joins.

---

## Semi-joins

A semi-join returns rows from one relation when at least one matching row exists in another relation.

The Python implementation uses:

`EXISTS`

to find departments having employees.

The important property is that a department appears once even if it has many employees.

A semi-join expresses existence rather than returning the complete matching relationship.

---

## Anti-joins

An anti-join returns rows for which no matching row exists.

The Python implementation uses:

`NOT EXISTS`

to identify departments without employees.

This is useful for data-quality queries such as:

- customers without orders
- products without inventory
- employees without assignments
- departments without managers
- accounts without transactions

---

## Python implementation

The Python implementation uses SQLite through the standard-library `sqlite3` module.

The database is created in memory, so no external database server or file is required.

The schema contains:

- `departments`
- `employees`
- `projects`
- `employee_projects`
- `customers`
- `orders`

This structure provides enough relationships to demonstrate the main join types and their practical consequences.

### Python fundamentals

The program introduces:

- database connections
- table creation
- primary keys
- foreign keys
- nullable relationships
- inserts
- `SELECT`
- `INNER JOIN`
- `LEFT JOIN`
- `FULL OUTER JOIN`
- `CROSS JOIN`
- `SELF JOIN`
- aggregation
- `EXISTS`
- `NOT EXISTS`
- `CASE`
- `COALESCE`
- query plans
- parameterized queries
- assertions

### Python FULL JOIN

The program first demonstrates a portable `UNION` construction and then attempts native `FULL OUTER JOIN` support.

The result is classified into relationship states.

This makes the example useful for reconciliation rather than merely demonstrating syntax.

### Python CROSS JOIN

The Python example intentionally restricts the employee set to two rows before producing the Cartesian product.

This keeps the output manageable while preserving the mathematical behavior of the operation.

### Python SELF JOIN

The employee table is joined to itself.

One alias represents the employee.

Another represents the manager.

A second self-join example produces peer pairs and prevents symmetric duplicates using an ID comparison.

### Python security

The program demonstrates parameterized SQL using a salary threshold.

The value is passed separately from the SQL statement.

This is safer than constructing SQL by concatenating untrusted input.

---

## JavaScript implementation

The JavaScript file models relational operations with native arrays, loops, `Map`, and `Set`.

It does not require an external npm package.

This implementation is deliberately different from the Python implementation because it exposes the mechanics of a join algorithm rather than relying on a database engine to execute the join.

### JavaScript INNER JOIN

The generic `innerJoin` function compares every left row against every right row.

Its structure makes the basic relational operation visible:

- iterate through left rows
- iterate through right rows
- evaluate the predicate
- emit a projected result when the predicate is true

This is an educational nested-loop implementation.

### JavaScript LEFT JOIN

The `leftJoin` function tracks whether a left row matched.

If no match exists, it calls the projection with a `null` right-side value.

This explicitly models SQL's NULL-extension behavior.

### JavaScript FULL OUTER JOIN

The `fullOuterJoin` implementation works in two logical phases.

The first phase processes left rows and records which right rows matched.

The second phase emits right rows that were never matched.

A `Set` tracks matched right-side indexes.

This mirrors the conceptual structure of a full outer join.

### JavaScript CROSS JOIN

The `crossJoin` function deliberately emits every pair.

Its result size follows:

`m × n`

This makes the relationship between algorithmic behavior and Cartesian-product cardinality explicit.

### JavaScript SELF JOIN

The same `employees` array is supplied as both logical sides of a join.

The hierarchy example resolves managers.

The peer example uses an ID ordering condition to prevent duplicate unordered pairs.

### JavaScript indexed lookup

The program also constructs a `Map` keyed by department ID.

Instead of scanning every department for every employee, an employee can perform a direct map lookup.

This demonstrates the conceptual benefit of an index for equality joins.

---

## C++ case study

The C++ implementation develops the join concepts into an organizational data system.

The modeled domain includes:

- departments
- employees
- projects
- employee-project assignments
- customers
- orders

The case study is implemented with standard C++17 facilities.

### Problem being modeled

An organization needs to analyze employee assignments, organizational hierarchy, project relationships, and customer-order data.

The system must identify:

- employees associated with departments
- departments without employees
- employees without departments
- employee-manager relationships
- employee peer pairs
- employee-project assignments
- department statistics
- customer/order mismatches

These requirements naturally map to different join patterns.

---

## C++ design

The implementation defines separate structures for domain entities.

Examples include:

`Department`

`Employee`

`Project`

`EmployeeProject`

`Customer`

`Order`

Nullable relationships use:

`std::optional<int>`

This provides a type-safe representation of values that may be absent.

For example, an employee may have no manager.

---

## C++ FULL JOIN case study

The full join between departments and employees is implemented in two phases.

The first phase iterates over departments and searches for matching employees.

If employees are found, matched rows are emitted.

If none are found, a department-only row is emitted.

The second phase examines employees and emits those that were never matched.

An `unordered_set` stores matched employee IDs.

The result therefore contains:

- matched department/employee relationships
- departments without employees
- employees without departments

This is equivalent to the conceptual result of a full outer join.

---

## C++ CROSS JOIN case study

The program generates employee/project combinations.

If two employees and four projects are selected:

`2 × 4 = 8`

combinations are produced.

The implementation explicitly documents the `O(m × n)` nature of the operation.

This is important for production systems because Cartesian products can grow very rapidly.

---

## C++ SELF JOIN case study

The employee table contains `managerId`.

The same employee collection is therefore used in two logical roles:

`employee`

and:

`manager`

For every employee with a manager ID, the program searches for the employee whose ID equals that manager ID.

This demonstrates a self-referential relationship.

The program also generates employee peer pairs within the same department.

The condition:

`first.id < second.id`

prevents both symmetric combinations and self-pairs.

---

## C++ many-to-many case study

The `employeeProjects` structure acts as a junction relation.

Each row represents one employee-project relationship.

The program resolves:

`employeeId -> Employee`

and:

`projectId -> Project`

and produces a readable assignment result.

The relationship also stores allocation percentage, demonstrating that attributes can belong to the relationship itself rather than to either entity.

---

## C++ aggregation

The department statistics operation calculates:

- employee count
- average salary

Departments with no employees remain in the result.

The implementation explicitly checks the employee count before calculating an average, preventing division by zero.

This models the semantics required when an outer join is followed by aggregation.

---

## Query complexity

A straightforward nested-loop equality join compares every left row with every right row.

For relations containing `m` and `n` rows, the worst-case number of comparisons is:

`O(m × n)`

A cross join has the same fundamental Cartesian growth because its output itself can contain `m × n` rows.

A self join over `n` rows can require:

`O(n²)`

comparisons when implemented as a naive pairwise scan.

---

## Indexed equality lookup

The C++ implementation builds an:

`unordered_map<int, const Department*>`

using department ID as the key.

The expected behavior becomes:

- index construction: `O(n)`
- employee lookups: expected `O(m)`
- combined expected cost: `O(m + n)`

This is conceptually similar to an equality lookup supported by an index in a database system.

Actual database performance depends on the optimizer, index structure, statistics, storage engine, data distribution, and query workload.

---

## Query-planning considerations

A database engine does not necessarily execute a SQL join as a literal nested loop.

Depending on the engine and workload, possible strategies include:

- nested-loop joins
- index-assisted nested loops
- hash joins
- merge joins

The optimizer chooses a strategy based on available information.

Indexes can improve lookup performance, but they are not free.

They consume storage and can increase the cost of inserts, updates, and deletes.

An index should therefore be evaluated against actual workload requirements.

---

## Duplicate rows and join multiplication

A common mistake is to assume that a join preserves one row per entity.

Consider:

- one department
- five employees
- four projects associated through another relationship

Joining both one-to-many relationships can produce several rows representing combinations of the related records.

If aggregation occurs afterward, a value may be counted multiple times.

This is particularly dangerous with:

`SUM`

because duplicated relationship rows can inflate totals.

Correct SQL design requires understanding the grain of the intermediate result.

---

## Join grain

The grain of a result means what one row represents.

For example:

`one row per employee`

is a different grain from:

`one row per employee-project assignment`

and:

`one row per employee-project-department combination`

Before adding aggregation, determine what one result row represents.

Many join-related errors are actually grain errors.

---

## Composite join keys

Some relationships require multiple columns.

A conceptual join can use:

`a.company_id = b.company_id`

and:

`a.account_id = b.account_id`

together.

Joining only on `company_id` could match unrelated accounts belonging to the same company.

The join predicate must therefore represent the complete relationship key.

---

## Edge cases

Important join edge cases include:

### Empty left table

An inner join produces no rows.

A right-oriented outer join can still preserve rows from the other side.

### Empty right table

An inner join produces no rows.

A left join preserves left rows with NULL right-side values.

### NULL join key

A NULL foreign key normally does not match an ordinary equality predicate.

This can produce an unmatched row in an outer join.

### Duplicate join keys

Duplicate keys can multiply output rows.

### No matches

A full join preserves unmatched rows from both sides.

### Symmetric self-join pairs

A peer comparison can produce both:

`A,B`

and:

`B,A`

unless the predicate prevents it.

### Self-pairs

A self join can produce:

`A,A`

unless an explicit condition excludes it.

### Large Cartesian products

A cross join can become computationally and operationally expensive very quickly.

---

## Common mistakes

### Treating FULL JOIN as an expanded INNER JOIN

A full join does not simply return more matching rows.

It also preserves unmatched rows from both sides.

### Filtering NULL with equality

Incorrect:

`column = NULL`

Correct:

`column IS NULL`

### Putting an outer-join filter in the wrong clause

Moving a condition from `ON` to `WHERE` can change which outer rows survive.

### Forgetting join cardinality

One-to-many and many-to-many relationships naturally multiply rows.

### Using CROSS JOIN accidentally

A missing predicate can generate a Cartesian product.

### Confusing SELF JOIN with a special SQL join keyword

`SELF JOIN` describes the relationship pattern.

The SQL syntax normally uses an ordinary join with the same table referenced twice under different aliases.

### Counting NULL-extended rows incorrectly

`COUNT(*)` and `COUNT(column)` can produce different results after an outer join.

### Aggregating before understanding duplication

Aggregates can become incorrect when a preceding join multiplies rows.

---

## Limitations of the educational implementations

The Python program uses SQLite and an in-memory database.

It is intended for controlled demonstrations rather than large-scale production workloads.

The JavaScript implementation models relational behavior using arrays. It does not provide a full SQL parser or query optimizer.

The C++ implementation models joins directly with standard-library structures rather than communicating with a database server.

A production database engine provides additional capabilities such as:

- query optimization
- statistics
- indexes
- transaction management
- concurrency control
- persistence
- recovery
- locking
- execution-plan selection

The implementations are therefore algorithmic and educational representations of relational join behavior.

---

## Security considerations

SQL joins themselves are not an injection vulnerability, but applications that construct SQL dynamically can become vulnerable.

Values supplied by users should be bound through parameterized queries.

For example, the Python implementation demonstrates a parameterized salary filter.

Applications should avoid directly concatenating untrusted input into SQL statements.

Identifiers such as table names and column names require different handling because ordinary value parameters do not generally represent arbitrary SQL identifiers.

Trusted allowlists are appropriate when applications must choose among permitted identifiers.

Production systems should also apply:

- least-privilege database accounts
- appropriate access controls
- transaction boundaries
- validation
- logging
- controlled error reporting

---

## Performance considerations

### Reduce unnecessary rows

Filter data at an appropriate stage, while preserving the intended semantics of outer joins.

### Index join keys

Frequently used equality join columns may benefit from indexes.

Foreign-key columns are common candidates, although the correct index depends on workload and database engine behavior.

### Avoid accidental Cartesian products

Review every cross join and every join predicate.

### Check execution plans

Database systems provide explain or query-plan facilities.

The Python implementation demonstrates `EXPLAIN QUERY PLAN` with SQLite.

### Consider data volume

A query that performs well on hundreds of rows may behave very differently on millions of rows.

### Avoid unnecessary application-side joins

If large datasets already reside in a relational database, transferring them into application memory just to join them can be inefficient.

The database engine is generally designed to perform relational operations close to the stored data.

---

## Implementation comparison

| Concern | Python | JavaScript | C++ |
|---|---|---|---|
| Main purpose | Executable SQL study | Join algorithm modeling | Technical case study |
| Data engine | SQLite | Native arrays | Standard-library containers |
| FULL JOIN | Native/portable SQL | Explicit algorithm | Explicit algorithm |
| CROSS JOIN | SQL | Nested loops | Nested loops |
| SELF JOIN | SQL aliases | Same array twice | Same vector twice |
| NULL modeling | SQL `NULL` | `null` | `std::optional` |
| Index concept | SQLite query plan | `Map` | `unordered_map` |
| Validation | Assertions and SQL constraints | JavaScript validation | Exceptions and validation |
| Security | Parameterized SQL | Application-side concerns | SQL integration guidance |
| Complexity visibility | Database-oriented | Algorithm-oriented | Algorithm and data-structure oriented |

---

## Important distinctions

### FULL OUTER JOIN versus LEFT JOIN

A left join preserves unmatched rows from the left side only.

A full outer join preserves unmatched rows from both sides.

### FULL OUTER JOIN versus INNER JOIN

An inner join removes unmatched rows.

A full outer join retains them.

### CROSS JOIN versus INNER JOIN

A cross join does not require a matching relationship.

An inner join normally requires a predicate that determines matching rows.

### SELF JOIN versus CROSS JOIN

A self join describes joining a table to itself.

A cross join describes Cartesian pairing.

They can technically be combined, but they express different concepts.

### SELF JOIN versus recursive query

A self join can connect one level of a hierarchy.

A recursive common table expression can traverse an arbitrary-depth hierarchy when supported by the database engine.

---

## Real-world relevance

These join patterns appear in many systems.

### Financial systems

Full joins can reconcile ledger exports with transaction records.

### Enterprise applications

Self joins can represent employee-manager structures.

### Security systems

Self joins can compare entities or relationships stored in a common table.

### E-commerce

Cross joins can generate controlled product, region, or pricing scenarios.

### Data engineering

Full joins can identify discrepancies between source and target datasets during migration.

### Business analytics

Left joins allow reports to include entities with zero related activity.

### Data quality

Anti-join patterns can detect orphan records and missing relationships.

---

## Practical reasoning process for joins

A reliable way to design a join is to determine:

1. What does one row in each source represent?
2. Which columns identify the relationship?
3. Is the relationship one-to-one, one-to-many, or many-to-many?
4. Which unmatched rows must remain visible?
5. Can either join key contain NULL?
6. Can duplicate keys multiply the result?
7. What should one row in the final result represent?
8. Is the operation intentionally Cartesian?
9. Does filtering belong in `ON` or `WHERE`?
10. Does aggregation occur at the correct grain?
11. Does the database have suitable indexes?
12. What does the execution plan show?

These questions prevent many practical join errors before the query is executed.

---

## Files in this study

The Python implementation demonstrates actual SQL behavior using SQLite.

The JavaScript implementation exposes join mechanics directly through arrays, loops, `Map`, and `Set`.

The C++ implementation develops the same relational concepts into a structured organizational data case study using typed data structures, optional relationships, validation, indexed lookups, reconciliation, and complexity analysis.

Together, the implementations distinguish SQL semantics from language-specific implementation techniques while preserving the same underlying relational principles.
```
