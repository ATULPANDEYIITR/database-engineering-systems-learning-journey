# SQL Joins I: INNER JOIN, LEFT JOIN, RIGHT JOIN

## Introduction

SQL JOINs combine rows from two or more relational tables according to a relationship condition. They are fundamental to relational database work because useful business information is commonly distributed across multiple tables rather than stored in one large table.

This implementation set studies three core JOIN types:

- `INNER JOIN`
- `LEFT JOIN`
- `RIGHT JOIN`

The Python implementation uses SQLite through Python's standard `sqlite3` module. It provides executable SQL statements, aggregation examples, NULL handling, query-plan inspection, relationship validation, and parameterized queries.

The JavaScript implementation builds SQL-style joins directly over arrays of JavaScript objects. This makes the mechanics of row matching, row preservation, NULL-like values, one-to-many relationships, and hash-based equality joins explicit.

The C++ implementation develops a small order-management reporting system. It models customers and orders as separate relations and implements nested-loop and indexed JOIN algorithms, reporting, validation, NULL-like unmatched rows, and performance comparisons.

## Relational foundations

A relational database represents information using relations, commonly exposed as tables.

A table contains:

- rows, representing records;
- columns, representing attributes;
- keys, identifying relationships between records;
- constraints, protecting data integrity.

The example database contains a `customers` table:

| customer_id | customer_name | city |
|---:|---|---|
| 1 | Asha | Lucknow |
| 2 | Bharat | Delhi |
| 3 | Chitra | Mumbai |
| 4 | Dev | Pune |
| 5 | Esha | Jaipur |

The `orders` table contains:

| order_id | customer_id | product | amount |
|---:|---:|---|---:|
| 101 | 1 | Laptop | 75000 |
| 102 | 1 | Mouse | 1500 |
| 103 | 2 | Monitor | 18000 |
| 104 | 3 | Keyboard | 3500 |
| 105 | NULL | Unassigned Device | 9000 |

`customers.customer_id` is a primary key. `orders.customer_id` is a foreign-key-style relationship to that key.

The relationship can be expressed as:

`customers.customer_id = orders.customer_id`

This relationship is the basis for the examples.

## Terminology

### Relation

A relation is the mathematical foundation of a relational table. In practical SQL work, the term table is more common.

### Row

A row represents one record in a table.

For example, the customer identified by `customer_id = 1` is one row.

### Column

A column represents an attribute.

`customer_name`, `city`, and `amount` are examples.

### Primary key

A primary key uniquely identifies a row within a table.

For the customer table:

`customer_id`

is the primary key.

### Foreign key

A foreign key stores a value that refers to a key in another table.

The order table uses `customer_id` to associate an order with a customer.

### Join key

A join key is the column or expression used to establish a relationship between rows.

The common equality condition is:

`customers.customer_id = orders.customer_id`

### Join predicate

A predicate is a condition that determines whether two rows qualify for a relationship.

A basic equality predicate is:

`c.customer_id = o.customer_id`

A more restrictive condition can contain additional predicates.

### Cardinality

Cardinality describes the number of rows or the multiplicity of relationships.

A customer can have zero, one, or many orders. This is a one-to-many relationship.

This matters because a JOIN does not necessarily produce one output row per input row.

If one customer has five matching orders, that customer can appear in five joined rows.

### NULL

`NULL` represents an unknown, unavailable, or absent value in SQL.

It is not equivalent to:

- zero;
- an empty string;
- `FALSE`;
- a normal missing-object value.

SQL uses three-valued logic involving `TRUE`, `FALSE`, and `UNKNOWN`.

## The basic JOIN structure

A common SQL structure is:

`SELECT columns FROM table_a AS a INNER JOIN table_b AS b ON a.key = b.key;`

The important components are:

- `FROM` identifies the initial relation.
- `JOIN` introduces another relation.
- `ON` defines the matching condition.
- `SELECT` identifies the columns returned.

Aliases such as `c` and `o` make multi-table queries easier to read:

`customers AS c`

and

`orders AS o`

allow expressions such as:

`c.customer_id = o.customer_id`

## INNER JOIN

An `INNER JOIN` returns only rows for which the join condition is satisfied.

The central behavior can be described as:

> Return matching pairs and discard unmatched rows.

For the customer and order example, the matching relationships are:

| Customer | Order |
|---|---:|
| Asha | 101 |
| Asha | 102 |
| Bharat | 103 |
| Chitra | 104 |

Dev and Esha have no orders, so they do not appear.

The order with a `NULL` customer ID also does not match a normal equality predicate.

### Python demonstration

The Python implementation executes:

`SELECT c.customer_name, o.product, o.amount FROM customers AS c INNER JOIN orders AS o ON c.customer_id = o.customer_id;`

The result demonstrates the actual SQL behavior through SQLite.

The script also combines `INNER JOIN` with:

- aliases;
- `WHERE`;
- `GROUP BY`;
- aggregate functions;
- `HAVING`;
- parameterized conditions.

### When INNER JOIN is appropriate

`INNER JOIN` is appropriate when the result should contain only entities having a valid relationship.

Examples include:

- customers with orders;
- employees with departments;
- products with valid categories;
- transactions with valid accounts;
- students with enrolled courses.

If unmatched records must remain visible, an outer JOIN is generally more appropriate.

## LEFT JOIN

A `LEFT JOIN` is an outer join that preserves every row from the left relation.

The basic structure is:

`SELECT ... FROM customers AS c LEFT JOIN orders AS o ON c.customer_id = o.customer_id;`

The result contains:

- all customers;
- matching orders where available;
- `NULL` values for order columns where no match exists.

For the example:

| Customer | Order |
|---|---:|
| Asha | 101 |
| Asha | 102 |
| Bharat | 103 |
| Chitra | 104 |
| Dev | NULL |
| Esha | NULL |

Dev and Esha remain visible even though they have no orders.

### Finding entities without matches

A common pattern is:

`LEFT JOIN ... WHERE right_table.key IS NULL`

For customers without orders:

`SELECT c.customer_name FROM customers AS c LEFT JOIN orders AS o ON c.customer_id = o.customer_id WHERE o.order_id IS NULL;`

This identifies unmatched left-side rows.

The Python program executes this pattern directly.

### LEFT JOIN with aggregation

A reporting requirement often asks for every customer and their total spending.

An `INNER JOIN` would remove customers with no orders.

A `LEFT JOIN` preserves them:

`SELECT c.customer_name, COUNT(o.order_id), COALESCE(SUM(o.amount), 0) FROM customers AS c LEFT JOIN orders AS o ON c.customer_id = o.customer_id GROUP BY c.customer_id, c.customer_name;`

`COALESCE` converts a NULL aggregate result into a useful numeric value.

The distinction between `COUNT(*)` and `COUNT(o.order_id)` is important.

For an unmatched customer:

- `COUNT(*)` can count the preserved JOIN row;
- `COUNT(o.order_id)` counts only actual order IDs and therefore produces zero.

## RIGHT JOIN

A `RIGHT JOIN` preserves every row from the right relation.

Conceptually:

`A RIGHT JOIN B`

is equivalent in preservation semantics to:

`B LEFT JOIN A`

For example:

`SELECT o.order_id, c.customer_name FROM customers AS c RIGHT JOIN orders AS o ON c.customer_id = o.customer_id;`

Every order remains in the result.

The order with `customer_id = NULL` is preserved, while the customer columns are NULL.

### RIGHT JOIN and LEFT JOIN equivalence

A RIGHT JOIN:

`customers RIGHT JOIN orders`

can be rewritten as:

`orders LEFT JOIN customers`

with the corresponding relationship condition.

This is why many SQL codebases prefer LEFT JOIN consistently. The preserved table is visually positioned on the left.

The important principle is not the keyword itself. The important principle is which relation must be preserved.

### SQLite compatibility

The Python program checks the SQLite version before executing a native `RIGHT JOIN`.

For environments without native RIGHT JOIN support, it demonstrates the equivalent reversed `LEFT JOIN`.

This distinction is useful when SQL is transferred between database systems with different feature histories or compatibility requirements.

## INNER JOIN versus LEFT JOIN versus RIGHT JOIN

| Join type | Matching rows | Unmatched left rows | Unmatched right rows |
|---|---|---|---|
| `INNER JOIN` | Yes | Removed | Removed |
| `LEFT JOIN` | Yes | Preserved | Removed |
| `RIGHT JOIN` | Yes | Removed | Preserved |

A useful mental model is:

`INNER JOIN`  
Keep matching relationships only.

`LEFT JOIN`  
Keep everything on the left and attach matching rows from the right.

`RIGHT JOIN`  
Keep everything on the right and attach matching rows from the left.

## ON versus WHERE

One of the most important JOIN concepts is the difference between conditions placed in `ON` and conditions placed in `WHERE`.

Consider:

`FROM customers AS c LEFT JOIN orders AS o ON c.customer_id = o.customer_id AND o.amount >= 5000`

The amount condition restricts which orders are eligible to match, while customers remain preserved.

Compare this with:

`FROM customers AS c LEFT JOIN orders AS o ON c.customer_id = o.customer_id WHERE o.amount >= 5000`

The JOIN first creates unmatched rows containing NULL order values. The `WHERE` condition then removes those rows because `NULL >= 5000` is not TRUE.

The second query therefore loses customers with no qualifying order.

### Practical rule

`ON` controls relationship matching.

`WHERE` filters the resulting rows.

This distinction is particularly important for `LEFT JOIN` and `RIGHT JOIN`.

## NULL and JOIN behavior

Consider the order:

`order_id = 105`

with:

`customer_id = NULL`

The predicate:

`c.customer_id = o.customer_id`

does not produce a TRUE result when the order's key is NULL.

SQL NULL semantics are different from ordinary programming-language equality.

A condition such as:

`customer_id = NULL`

is not the correct way to test for NULL.

Use:

`customer_id IS NULL`

or:

`customer_id IS NOT NULL`

The Python implementation explicitly demonstrates this behavior.

## One-to-many relationships

A JOIN does not automatically collapse related records.

Asha has two orders:

- order 101;
- order 102.

Therefore an INNER JOIN produces two rows involving Asha.

This is expected relational behavior.

Suppose a customer has 100 orders. A JOIN between customers and orders can produce 100 output rows for that customer.

This becomes particularly important when several one-to-many relationships are joined simultaneously.

If one customer has:

- 3 orders;
- 4 support tickets;

a naïve join of both one-to-many tables can potentially produce up to 12 combinations for that customer.

This phenomenon is often called row multiplication or join multiplication.

## Aggregation after JOIN

When the desired result is one row per customer, aggregation is needed.

Typical functions include:

- `COUNT`;
- `SUM`;
- `AVG`;
- `MIN`;
- `MAX`.

For example:

`SUM(o.amount)`

calculates total spending.

`COUNT(o.order_id)`

counts actual matching orders.

`GROUP BY c.customer_id, c.customer_name`

changes the result from transaction-level rows to customer-level groups.

`HAVING` filters groups after aggregation.

For example:

`HAVING SUM(o.amount) > 10000`

keeps customers whose aggregate spending exceeds the threshold.

## Joining multiple tables

JOINs can be chained.

The employee model contains:

- departments;
- employees.

An employee can be associated with a department.

A department can have multiple employees.

A LEFT JOIN from departments to employees preserves departments even if no employee is assigned.

This produces a report suitable for detecting empty organizational units.

When multiple JOINs are chained, the logical structure should be kept explicit:

1. identify the entities;
2. identify their relationship keys;
3. determine which side must be preserved;
4. write the join predicate;
5. apply filters deliberately;
6. aggregate when required.

## Self JOIN

A self JOIN joins a table with itself.

The Python implementation uses an employee hierarchy containing:

- an employee;
- a manager ID.

The table is referenced twice through aliases.

Conceptually:

`employees AS employee`

and:

`employees AS manager`

The relationship is:

`employee.manager_id = manager.employee_id`

A self JOIN is useful for hierarchical relationships such as:

- employees and managers;
- categories and parent categories;
- accounts and parent accounts;
- locations and parent regions.

Aliases are essential because the same physical table represents two logical roles.

## Cartesian products

A Cartesian product pairs every row in one relation with every row in another relation.

If table A has 5 rows and table B has 5 rows:

`5 × 5 = 25`

row combinations are possible.

SQL can explicitly request this with:

`CROSS JOIN`

An unintended Cartesian product can produce a massive result.

The Python program demonstrates the count of combinations using:

`SELECT COUNT(*) FROM customers CROSS JOIN orders;`

A sudden and unexpected explosion in row count is an important JOIN debugging signal.

## Common JOIN mistakes

### Joining on the wrong columns

A query can be syntactically valid while being logically wrong.

The selected columns must represent the intended relationship.

Joining unrelated columns can create plausible-looking but incorrect results.

### Forgetting the relationship condition

An incomplete JOIN can produce a Cartesian product or an unintended relationship.

Always inspect the `ON` predicate.

### Accidentally converting a LEFT JOIN into INNER-like behavior

This commonly occurs when a nullable right-side column is filtered in `WHERE`.

The correct placement depends on whether unmatched left-side rows should remain.

### Using `SELECT *`

`SELECT *` can:

- return unnecessary data;
- produce duplicate column names;
- make application code fragile;
- expose fields that were not intended for a consumer;
- become unstable when schemas change.

Explicit column selection is generally clearer.

### Ignoring duplicate keys

A column assumed to be unique may not actually be unique.

Joining against non-unique keys can multiply rows.

Key constraints and data-quality checks help protect relationship assumptions.

### Assuming NULL matches NULL

Ordinary equality does not make NULL values match.

Use explicit NULL predicates when appropriate.

### Ignoring result cardinality

A JOIN can legitimately increase the number of rows.

Unexpected cardinality should trigger investigation of:

- relationship multiplicity;
- duplicate keys;
- missing predicates;
- incorrect keys;
- unintended many-to-many combinations.

## Python implementation

The Python program uses only the standard library:

`sqlite3`

This allows the examples to execute against a real SQL engine without an external package.

The database is created in memory:

`sqlite3.connect(":memory:")`

The program creates:

- `customers`;
- `orders`;
- `departments`;
- `employees`;
- `employees_hierarchy`.

### Python JOIN coverage

The Python implementation demonstrates:

- basic table creation;
- primary keys;
- foreign keys;
- INNER JOIN;
- LEFT JOIN;
- RIGHT JOIN when supported;
- RIGHT JOIN rewritten as reversed LEFT JOIN;
- aliases;
- WHERE conditions;
- ON conditions;
- NULL handling;
- GROUP BY;
- HAVING;
- COUNT;
- SUM;
- AVG;
- COALESCE;
- CASE;
- self JOIN;
- three-table relationships;
- Cartesian products;
- relationship validation;
- parameterized queries;
- query plans;
- indexes;
- semantic assertions.

### Parameterized SQL

The Python implementation uses parameter binding:

`WHERE c.city = ?`

and passes the value separately.

This is preferable to constructing SQL by concatenating user-controlled values.

Parameterized queries help prevent SQL injection because data values are handled separately from SQL syntax.

## Python query-plan analysis

The Python program creates an index:

`CREATE INDEX idx_orders_customer_id ON orders(customer_id)`

It then executes `EXPLAIN QUERY PLAN`.

A database optimizer can use indexes to locate matching records efficiently.

An important distinction is that a foreign-key relationship and an index are separate concepts.

A foreign key expresses referential integrity.

An index is an access structure that can accelerate lookups and other operations.

Whether an index is beneficial depends on workload, data distribution, selectivity, storage cost, and the database optimizer.

## JavaScript implementation

The JavaScript file deliberately does not depend on an npm database package.

Instead, it represents relational rows as JavaScript objects:

`{ customer_id: 1, customer_name: "Asha", city: "Lucknow" }`

and orders as objects containing the related key.

This makes the mechanics of a JOIN visible.

### JavaScript INNER JOIN

The `innerJoin` function uses nested loops.

For every left row, it examines every right row and emits a pair when the keys match.

Its basic complexity is:

`O(L × R)`

where:

- `L` is the number of left rows;
- `R` is the number of right rows.

### JavaScript LEFT JOIN

The `leftJoin` function maintains a `foundMatch` flag.

If no right-side row matches a left row, it emits a result containing:

`right_data: null`

This models the preservation rule of SQL LEFT JOIN.

### JavaScript RIGHT JOIN

The `rightJoin` implementation reverses the inputs and uses the LEFT JOIN mechanism.

This demonstrates the conceptual equivalence:

`A RIGHT JOIN B`

and:

`B LEFT JOIN A`

when the corresponding columns and output projection are reversed appropriately.

### JavaScript hash JOIN

The `hashInnerJoin` function builds a `Map`.

The map associates a join key with all right-side rows having that key.

The algorithm then probes the map for each left row.

For equality joins, average-case complexity becomes approximately:

`O(L + R + output)`

instead of:

`O(L × R)`

The trade-off is additional memory for the hash index.

## C++ case study

The C++ program models an order-management reporting system.

The primary entities are:

- `Customer`;
- `Order`;
- `Department`;
- `Employee`.

The customer model contains:

`customer_id`

`customer_name`

`city`

The order model contains:

`order_id`

`customer_id`

`product`

`amount`

The `std::optional<int>` type is used for `Order::customer_id` because an order may contain no customer ID.

This gives C++ a clear representation of a nullable relationship.

## C++ INNER JOIN

The `innerJoin` function implements a nested-loop equality join.

For every customer, it examines every order.

A pair is emitted when:

`order.customer_id == customer.customer_id`

and the order contains a customer ID.

This is conceptually equivalent to:

`INNER JOIN orders ON customers.customer_id = orders.customer_id`

The function returns only matching pairs.

## C++ LEFT JOIN

The `leftJoin` function preserves every customer.

For each customer:

1. search all orders;
2. emit matching pairs;
3. if no match is found, emit `{customer, nullptr}`.

The `nullptr` represents the absence of a matching right-side row in this in-memory model.

This corresponds conceptually to SQL NULL values appearing in columns from the unmatched side.

## C++ RIGHT JOIN

The `rightJoin` function reverses the preservation rule.

Every order is retained.

If an order has no matching customer, its customer pointer is `nullptr`.

This models:

`customers RIGHT JOIN orders`

and is conceptually equivalent to reversing the tables and using a LEFT JOIN.

## C++ reporting system

The `buildCustomerReport` function answers a practical business question:

> What is the number of orders and total spending for every customer?

The requirement is that customers with zero orders must still appear.

That makes LEFT JOIN the appropriate relational pattern.

The report contains:

- customer name;
- order count;
- total spending.

Orders are accumulated after the JOIN.

This is analogous to SQL aggregation with `GROUP BY`.

## C++ relationship validation

The program builds a lookup of known customer IDs and checks every order.

This detects an order containing a non-NULL customer ID that does not correspond to an existing customer.

A real relational database can enforce such relationships using foreign-key constraints.

Application-level validation remains useful when processing external files, legacy data, imports, or systems where database constraints are unavailable.

## C++ indexed JOIN

The `indexedInnerJoin` function creates:

`std::unordered_multimap<int, const Order*>`

The multimap is appropriate because several orders can belong to one customer.

The index transforms repeated searching into key lookup.

The general structure is:

1. build an index from order customer IDs;
2. iterate through customers;
3. look up matching orders;
4. emit matching pairs.

This changes the average algorithmic behavior from a nested comparison approach toward:

`O(customers + orders + output)`

for an equality join, subject to hash-table behavior and output size.

## Complexity considerations

### Nested-loop JOIN

For `L` left rows and `R` right rows:

`O(L × R)`

comparisons may be required.

The method is simple and can still be useful for small inputs.

### Hash JOIN

Building an index requires approximately:

`O(R)`

work and memory.

Probing the index requires approximately:

`O(L)`

lookups, excluding the cost of emitting matching results.

The overall average-case behavior is approximately:

`O(L + R + output)`

for an equality join.

### Database execution plans

A real database is not required to use either of these exact implementations.

Common physical strategies include:

- nested-loop join;
- hash join;
- merge join.

The optimizer chooses an execution strategy based on factors such as:

- table sizes;
- indexes;
- statistics;
- data distribution;
- join predicates;
- filtering conditions;
- available memory;
- expected result cardinality.

SQL describes the requested result. The database engine decides how to produce it.

## Indexing considerations

An index on a frequently joined foreign-key column can be useful.

For example:

`orders(customer_id)`

can support efficient lookup of orders for a given customer.

Indexes have costs:

- additional storage;
- additional write overhead;
- maintenance work;
- possible cache pressure.

An index should therefore be justified by actual query and workload requirements.

`EXPLAIN` or the database engine's equivalent execution-plan facilities are important for diagnosing query performance.

## Security considerations

JOIN syntax itself is not an SQL injection vulnerability. The security problem arises when untrusted data is inserted into SQL syntax incorrectly.

Avoid constructing SQL through string concatenation with user input.

Unsafe conceptual pattern:

`"SELECT ... WHERE city = '" + userInput + "'"`

Use parameterized queries instead.

The Python program demonstrates:

`WHERE c.city = ?`

with the city supplied as a separate parameter.

For real applications, parameterization should be applied consistently to user-controlled values.

Least-privilege database accounts, appropriate authorization, validation, and careful exposure of query results are also important in production systems.

## Implementation considerations

A JOIN should be designed around the relationship being modeled, not simply around the desire to combine tables.

Questions to answer before writing the query include:

- What are the entities?
- What is the relationship key?
- Is the key unique?
- Can either key be NULL?
- Is the relationship one-to-one, one-to-many, or many-to-many?
- Which table must always appear?
- What should happen when no related record exists?
- Should filtering happen during matching or after the JOIN?
- What should the expected result cardinality be?
- Is aggregation required?
- Is an index available?
- What does the execution plan show?

These questions prevent many logical JOIN errors.

## Edge cases

### No matching rows

For INNER JOIN, no matches means no result rows.

For LEFT JOIN, the left-side rows remain.

For RIGHT JOIN, the right-side rows remain.

### NULL join key

A NULL key normally does not satisfy an equality JOIN predicate.

The Python, JavaScript, and C++ implementations explicitly model this case.

### Multiple matches

One left row can match multiple right rows.

Every valid pair can become an output row.

### Duplicate keys

If a supposedly unique relationship column contains duplicates, the JOIN may multiply results.

Database constraints should reflect actual data-model assumptions.

### Empty tables

If the right table is empty:

- INNER JOIN produces no rows;
- LEFT JOIN still produces every left row;
- RIGHT JOIN produces no rows if the right side is empty.

### Cartesian product

A CROSS JOIN deliberately produces all combinations.

An accidental Cartesian product can create very large result sets.

### Filtering unmatched rows

A WHERE predicate referencing a nullable outer-joined side can remove unmatched records.

This is a frequent source of unexpected results.

## Important distinctions

### JOIN versus WHERE

A JOIN establishes relationships between rows.

A WHERE clause filters rows after the relevant relational operations.

### ON versus WHERE

For an INNER JOIN, many straightforward predicates can produce equivalent results when moved between ON and WHERE.

For an OUTER JOIN, the placement can change which unmatched rows survive.

### Primary key versus foreign key

A primary key identifies a record in its own table.

A foreign key represents a relationship to another table.

They serve different roles even when they contain related values.

### JOIN versus aggregation

JOIN combines related rows.

Aggregation transforms groups of rows into summary values.

They are often used together but solve different problems.

### Logical JOIN versus physical join algorithm

`INNER JOIN` is SQL-level relational semantics.

Nested-loop, hash, and merge joins are physical execution strategies.

A SQL query does not normally dictate which physical algorithm the database must use.

## Practical applications

JOINs appear throughout real database systems.

Examples include:

### Customer systems

Customers can be joined with:

- orders;
- addresses;
- payments;
- support tickets;
- subscriptions.

### Financial systems

Accounts can be joined with:

- transactions;
- customers;
- branches;
- instruments;
- settlement records.

### Human resources

Employees can be joined with:

- departments;
- managers;
- compensation records;
- attendance;
- projects.

### Education

Students can be joined with:

- courses;
- enrollments;
- grades;
- departments;
- examinations.

### Security and operations

Events can be joined with:

- users;
- devices;
- locations;
- incidents;
- access records.

The specific JOIN type depends on whether unmatched records must remain visible.

## Production considerations

A production JOIN should be evaluated from both correctness and performance perspectives.

Correctness considerations include:

- relationship integrity;
- NULL semantics;
- key uniqueness;
- cardinality;
- duplicate records;
- preservation requirements;
- aggregation behavior.

Performance considerations include:

- indexes;
- table size;
- selectivity;
- join order;
- execution plans;
- memory;
- result-set size;
- network transfer.

A technically valid JOIN can still be unsuitable for production if it creates an unexpectedly large result set.

## Testing JOIN behavior

The Python, JavaScript, and C++ programs include assertions around important semantic cases.

The expected values are:

- `INNER JOIN`: 4 matching rows;
- `LEFT JOIN`: 6 output rows;
- `RIGHT JOIN`: 5 preserved order rows;
- unmatched customers: 2;
- orders with NULL customer IDs: 1.

These numbers are not arbitrary. They follow directly from the input data:

Asha has two orders.

Bharat has one order.

Chitra has one order.

Dev has no orders.

Esha has no orders.

There is one order without a customer ID.

The resulting cardinalities are therefore predictable.

## Three-language comparison

| Language | Main purpose in this implementation |
|---|---|
| Python | Execute actual SQL against SQLite |
| JavaScript | Expose JOIN mechanics using arrays and custom algorithms |
| C++ | Build a realistic in-memory reporting system and compare algorithms |

Python is useful because the examples execute real SQL syntax through SQLite.

JavaScript is useful for demonstrating the mechanics behind JOINs without requiring a database server.

C++ is useful for exploring data structures, memory representation, algorithmic complexity, pointers, `std::optional`, hash indexing, and application-level system design.

The three implementations therefore approach the same relational concepts at different layers.

## Relationship between SQL and in-memory JOINs

The JavaScript and C++ implementations are educational models of JOIN behavior.

A real SQL engine has substantially more functionality, including:

- query parsing;
- query optimization;
- execution planning;
- indexes;
- statistics;
- transaction management;
- concurrency control;
- buffer management;
- storage engines;
- locking or multiversion mechanisms;
- constraint enforcement.

An application-level nested-loop function should not be assumed to behave like a production database engine.

The in-memory implementations are useful for understanding the relational result that the database is required to produce.

## Key conceptual model

The three JOINs can be remembered by their preservation rules.

`INNER JOIN`

Only matched relationships survive.

`LEFT JOIN`

Everything from the left side survives.

`RIGHT JOIN`

Everything from the right side survives.

The most important question when choosing among them is:

> Which records must remain in the result even when no related record exists?

If the answer is "only records having a match", use an INNER JOIN.

If the answer is "every record from the first table", use a LEFT JOIN.

If the answer is "every record from the second table", use a RIGHT JOIN.

In many codebases, RIGHT JOIN can be rewritten as a reversed LEFT JOIN, making LEFT JOIN the primary outer-join form used for readability and consistency.
