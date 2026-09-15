# SQL foundations project: build and query a complete small relational database

## Topic introduction

SQL, or Structured Query Language, is the standard language used to define, manipulate, and query relational data. A relational database represents information as tables containing rows and columns and connects related tables through keys.

This project models a small educational commerce system containing customers, employees, product categories, products, orders, order items, and payments.

The same conceptual problem is approached from three programming languages:

- Python uses SQLite through the standard `sqlite3` library and demonstrates actual SQL execution.
- JavaScript implements relational concepts at the application level using arrays, objects, Maps, validation, joins, grouping, indexes, transactions, and asynchronous behavior.
- C++ develops a more systems-oriented in-memory relational database model with explicit classes, indexes, constraints, transactions, validation, reporting, and performance measurements.

The Python implementation is the primary SQL implementation because SQLite is a real relational database engine. The JavaScript and C++ implementations make the underlying mechanisms easier to understand by showing how relational concepts can be represented through ordinary programming constructs.

## Fundamental relational concepts

### Database

A database is an organized collection of persistent or temporary data. A relational database stores data using relations, normally represented as tables.

The project contains these logical entities:

| Table | Purpose |
|---|---|
| `customers` | Stores customer information |
| `employees` | Stores employees responsible for orders |
| `categories` | Groups products into business categories |
| `products` | Stores products, prices, stock, and categories |
| `orders` | Records customer orders |
| `order_items` | Records the products and quantities belonging to each order |
| `payments` | Records payment information for orders |

The separation of these entities avoids storing the same customer and product information repeatedly in every order.

### Table

A table represents a relation. It consists of rows and columns.

For example, the `customers` table contains one row for each customer and columns such as `customer_id`, `full_name`, `email`, `city`, `signup_date`, and `status`.

### Row

A row represents one record or tuple.

One customer row represents one customer. One order row represents one order.

### Column

A column represents an attribute of an entity.

Examples include:

- `customer_id`
- `full_name`
- `price`
- `stock_quantity`
- `order_date`
- `payment_method`

### Primary key

A primary key uniquely identifies each row.

The project uses:

- `customers.customer_id`
- `employees.employee_id`
- `categories.category_id`
- `products.product_id`
- `orders.order_id`
- `payments.payment_id`

The `order_items` table uses a separate identifier in the JavaScript and C++ implementations. The Python SQLite design demonstrates a composite primary key consisting of `order_id` and `product_id`.

A primary key should be stable, unique, and non-null.

### Foreign key

A foreign key creates a relationship between tables.

Examples:

- `products.category_id` references `categories.category_id`.
- `orders.customer_id` references `customers.customer_id`.
- `orders.employee_id` references `employees.employee_id`.
- `order_items.order_id` references `orders.order_id`.
- `order_items.product_id` references `products.product_id`.
- `payments.order_id` references `orders.order_id`.

Foreign keys protect referential integrity by preventing references to records that do not exist.

## Core principles of relational design

A relational database should represent facts in a structured way rather than duplicating information unnecessarily.

The order-management model follows these principles:

- Each major business entity has its own table.
- Relationships are represented using keys.
- Constraints protect important business invariants.
- Repeating product information is represented through `order_items`.
- Orders and payments are separate because they have different responsibilities.
- Queries combine related tables when information from multiple entities is required.

This approach reduces update anomalies and makes reporting possible through joins and aggregation.

## SQL categories

SQL is commonly divided into several categories.

### DDL

Data Definition Language defines database structures.

Typical statements include:

- `CREATE TABLE`
- `CREATE INDEX`
- `CREATE VIEW`
- `ALTER TABLE`
- `DROP TABLE`

The Python script uses `CREATE TABLE`, `CREATE INDEX`, and `CREATE VIEW`.

### DML

Data Manipulation Language changes data.

Examples include:

- `INSERT`
- `UPDATE`
- `DELETE`

The Python implementation uses all three concepts.

### DQL

Data Query Language is commonly associated with `SELECT`.

The project uses `SELECT` extensively for filtering, joining, aggregation, subqueries, reporting, and window functions.

### TCL

Transaction Control Language includes operations such as:

- `BEGIN`
- `COMMIT`
- `ROLLBACK`

The Python implementation explicitly demonstrates transaction behavior.

### DCL

Data Control Language includes commands such as `GRANT` and `REVOKE`. These are more relevant to server database administration than the embedded SQLite demonstration.

## Basic SQL structure

A typical query has the conceptual structure:

`SELECT columns FROM table WHERE condition GROUP BY columns HAVING group_condition ORDER BY columns LIMIT count`

Not every clause is required.

For example, a simple query can select customer information from the `customers` table and sort it by customer ID.

SQL keywords are generally case-insensitive, although uppercase keywords are commonly used for readability.

## Filtering

The `WHERE` clause filters individual rows.

Important operators include:

- `=`
- `<>`
- `>`
- `<`
- `>=`
- `<=`
- `AND`
- `OR`
- `NOT`
- `IN`
- `BETWEEN`
- `LIKE`
- `IS NULL`
- `IS NOT NULL`

The Python implementation demonstrates these operators against customers, products, and orders.

### IN

`IN` is useful when a value can belong to a known set.

The project uses it to select customers from multiple cities.

### BETWEEN

`BETWEEN` is useful for ranges. For date strings in the project's SQLite model, ISO-style dates allow lexicographic comparisons to work predictably.

### LIKE

`LIKE` performs pattern matching. The Python implementation uses it to find products containing the word `Python`.

### NULL

`NULL` represents an absent or unknown value. It is not equivalent to zero, an empty string, or false.

The correct tests are:

`column IS NULL`

and

`column IS NOT NULL`

Writing `column = NULL` does not correctly test for NULL.

SQL's treatment of NULL introduces three-valued logic: a condition can evaluate to TRUE, FALSE, or UNKNOWN.

## Sorting and limiting

`ORDER BY` controls result ordering.

`ASC` represents ascending order and `DESC` represents descending order.

`LIMIT` restricts the number of returned rows in SQLite.

Sorting should not be assumed unless an explicit ordering is requested.

## Expressions and aliases

SQL can calculate values during a query.

The Python implementation calculates tax and tax-inclusive prices using arithmetic expressions.

Aliases make query output easier to understand. For example, `price * 1.18 AS price_with_tax` gives a calculated result a meaningful name.

## CASE expressions

`CASE` provides conditional logic inside SQL.

The project uses it to classify products into price bands such as:

- entry
- standard
- premium

It also classifies customers according to revenue.

This is similar conceptually to `if` and `else if` logic in Python, JavaScript, and C++.

## Joins

A join combines rows from multiple tables according to a relationship.

### INNER JOIN

An `INNER JOIN` returns rows for which the join condition matches on both sides.

The project joins:

`orders.customer_id = customers.customer_id`

to display customer information with order information.

### LEFT JOIN

A `LEFT JOIN` retains every row from the left table even when there is no matching row on the right.

The Python implementation uses this to count orders for every customer, including customers who have no orders.

This is important for reports such as customer lists where missing activity must remain visible.

### Multiple joins

The detailed order report joins:

`orders`

with:

`customers`

and:

`order_items`

and:

`products`

This produces a business-level result containing customer, order, product, quantity, unit price, and line total.

### Cartesian products

If a join condition is missing or incorrect, the database can produce a Cartesian product in which many rows are combined with many unrelated rows.

This can dramatically increase result size and produce incorrect reports.

## Aggregation

Aggregate functions calculate values across multiple rows.

The project demonstrates:

- `COUNT`
- `SUM`
- `AVG`
- `MIN`
- `MAX`

Examples include customer counts, order counts, product revenue, and total units sold.

### GROUP BY

`GROUP BY` forms groups before aggregate functions are evaluated.

For example, orders can be grouped by customer to calculate revenue per customer.

### HAVING

`HAVING` filters groups after aggregation.

The distinction is important:

- `WHERE` filters individual rows.
- `HAVING` filters groups.

Using `WHERE` for an aggregate condition such as a total revenue threshold is incorrect because the aggregate has not yet been computed at the row-filtering stage.

## Subqueries

A subquery is a query nested inside another query.

The Python implementation demonstrates a scalar subquery that compares product prices with the average product price.

It also demonstrates a correlated subquery that calculates the number of orders for each customer.

Correlated subqueries can be useful but may be expensive when evaluated repeatedly. A join and grouped query may provide a better execution plan for the same logical requirement.

## Common table expressions

A Common Table Expression, or CTE, is introduced using `WITH`.

The project uses CTEs to create intermediate result sets such as valid order lines and customer revenue.

CTEs improve readability by separating a complicated analytical problem into named logical stages.

They do not automatically mean that the intermediate result is physically materialized. Exact optimizer behavior depends on the database engine.

## Window functions

Window functions perform calculations across related rows without collapsing those rows into one row per group.

The Python implementation demonstrates:

- `ROW_NUMBER`
- `RANK`
- `DENSE_RANK`
- running totals
- partitioned ranking

A normal `GROUP BY` might turn many product rows into one category row. A window function can calculate a ranking while keeping every product row visible.

This makes window functions useful for:

- rankings
- running totals
- moving calculations
- comparisons with previous or next rows
- top-N analysis
- analytical reporting

## Views

A view is a named query definition.

The Python project creates `customer_order_summary` as a reusable reporting interface.

Views can simplify complex queries and provide controlled access to selected data.

A conventional view does not necessarily store a physical copy of its result. It generally represents a query that is evaluated when used, although database engines can provide materialized-view mechanisms separately.

## Constraints

Constraints enforce data integrity.

The Python implementation uses:

### NOT NULL

A required value cannot be missing.

### UNIQUE

A value cannot be duplicated within the constrained uniqueness definition.

Customer email is unique in the project.

### PRIMARY KEY

A row identifier must be unique and non-null.

### CHECK

A condition must be satisfied.

Examples include:

- product price must not be negative
- stock must not be negative
- order status must belong to an allowed set
- payment status must belong to an allowed set

### FOREIGN KEY

A referenced record must exist according to the configured relationship rules.

Constraints are important because application code is not the only possible writer to a database. The database itself should protect fundamental invariants.

## Cascading and referential actions

The Python schema demonstrates several referential actions.

`ON DELETE CASCADE` is used for order items and payments where deleting an order should remove dependent records.

`ON DELETE SET NULL` is used for the optional employee relationship on orders.

`ON DELETE RESTRICT` prevents deletion of referenced customers, categories, or products when dependent records still exist.

The correct action depends on the business meaning of the relationship. Cascading deletes should be used deliberately because one deletion can affect many records.

## Normalization

Normalization reduces unnecessary duplication.

An unnormalized order might contain:

`order_id, customer_name, customer_email, product1, product2, product3`

This creates several problems.

The number of products is artificially limited. Customer information is repeated. Changing a customer's email may require changing many rows. Searching and aggregating products becomes difficult.

A normalized model separates:

- `customers`
- `products`
- `orders`
- `order_items`

### First normal form

First Normal Form requires atomic values and avoids repeating groups.

Instead of product columns such as `product1`, `product2`, and `product3`, each order item is represented by a separate row.

### Second normal form

Second Normal Form concerns dependencies on the whole key, particularly for composite keys.

The project demonstrates the idea through order items, where the relationship between an order and product is represented explicitly.

### Third normal form

Third Normal Form addresses transitive dependencies between non-key attributes.

For example, category information belongs in a category table rather than being repeatedly stored with every product.

Normalization reduces update, insertion, and deletion anomalies.

## Denormalization

Normalization is not an absolute rule for every workload.

Analytical systems may intentionally duplicate or precompute information to improve read performance.

Possible reasons include:

- faster reporting
- reduced join cost
- simplified analytical queries
- compatibility with data warehouses

The trade-off is increased storage and greater risk of inconsistent duplicated information.

## Transactions

A transaction groups related operations into one logical unit.

The project demonstrates a realistic order operation involving:

- stock validation
- stock deduction
- order creation
- order-item creation
- payment creation

If one operation fails, the transaction should not leave the database partially modified.

### ACID

Atomicity means all operations in a transaction succeed or the transaction is rolled back.

Consistency means database rules remain satisfied.

Isolation describes how concurrent transactions are separated from one another.

Durability means committed data survives normal system failures according to the database's durability guarantees.

Exact transaction and isolation behavior differs between SQLite, PostgreSQL, MySQL, and other database systems.

## UPDATE, DELETE, and UPSERT

`UPDATE` modifies existing rows.

A missing `WHERE` clause can modify every row.

`DELETE` removes rows and should be treated as a destructive operation.

An UPSERT combines insertion with conflict handling. SQLite supports syntax such as `ON CONFLICT ... DO UPDATE`.

Before executing a destructive operation, it is often useful to run a corresponding `SELECT` using the same condition to verify which rows will be affected.

## Parameterized SQL

Parameterized SQL separates SQL structure from user-provided values.

The Python implementation uses `?` placeholders.

This is safer than constructing SQL with string concatenation.

An unsafe pattern conceptually looks like:

`SELECT ... WHERE email = '` followed by untrusted input.

A safe pattern uses:

`SELECT ... WHERE email = ?`

with the user value supplied separately.

Parameterized queries are one of the primary defenses against SQL injection.

They do not replace authentication, authorization, database permissions, secure configuration, or other security controls.

## Python implementation

The Python implementation uses only the standard-library `sqlite3` module.

SQLite is an actual relational database engine, so the SQL statements in the Python file are executed by a real SQL engine rather than merely being simulated.

### Schema creation

`create_schema()` creates all project tables and indexes.

It enables foreign-key enforcement with:

`PRAGMA foreign_keys = ON`

This is important because SQLite requires foreign-key enforcement to be enabled explicitly for the connection.

### Data loading

`seed_data()` inserts customers, employees, categories, products, orders, order items, and payments.

The dataset is deliberately small enough to inspect manually while containing enough relationships for meaningful joins and reports.

### Query demonstrations

The Python file demonstrates:

- basic `SELECT`
- aliases
- arithmetic expressions
- `WHERE`
- `IN`
- `BETWEEN`
- `LIKE`
- `IS NULL`
- `CASE`
- `INNER JOIN`
- `LEFT JOIN`
- multiple joins
- `GROUP BY`
- `HAVING`
- aggregate functions
- scalar subqueries
- correlated subqueries
- CTEs
- window functions
- views
- updates
- upserts
- transactions
- parameterized queries
- query plans
- metadata inspection

### Validation and testing

The Python implementation intentionally executes invalid operations and catches `sqlite3.IntegrityError`.

It also contains a small test suite checking:

- customer existence
- email uniqueness
- product value validity
- foreign-key relationships

This demonstrates the difference between deliberately testing failure conditions and allowing invalid state into the database.

## JavaScript implementation

The JavaScript file does not require an external database package.

Instead, it implements relational concepts using JavaScript data structures.

### Table abstraction

The `Table` class stores rows and maintains a primary-key `Map`.

This demonstrates why a database needs structures capable of locating records efficiently.

### Database abstraction

The `RelationalDatabase` class contains tables and indexes and provides transaction operations.

The transaction implementation takes a snapshot of the database state. A successful operation commits the new state. A failed operation restores the snapshot.

This is an educational approximation rather than a replacement for a production database transaction manager.

Real database engines must handle concurrency, locking, logging, crash recovery, isolation, durability, and many other concerns.

### Joins

`innerJoin()` and `leftJoin()` demonstrate the logical behavior of SQL joins using JavaScript `Map` objects.

The implementation creates lookup structures rather than repeatedly searching every row of the right-side collection.

This illustrates an important database-engineering concept: efficient joins often depend on data structures and access paths.

### Grouping

`groupBy()` maps rows into groups.

The aggregation functions calculate totals and averages over those groups.

This mirrors the conceptual behavior of SQL `GROUP BY` and aggregate functions.

### Indexing

The JavaScript implementation creates indexes using `Map`.

For a city index, a structure similar to:

`city -> list of customer rows`

allows direct lookup by city instead of scanning every customer.

### Asynchronous behavior

The asynchronous example uses a Promise and `async`/`await`.

This is relevant to application-level database access because JavaScript web applications commonly communicate with databases asynchronously.

The example simulates that boundary without introducing an external database driver.

## C++ case study

The C++ implementation develops an in-memory order-management database from lower-level building blocks.

It uses:

- structs for rows
- vectors for table storage
- `unordered_map` for indexes
- exceptions for failures
- optional values for nullable relationships
- sorting algorithms for ranking
- transaction snapshots for rollback
- explicit validation
- performance measurement

### Problem being modeled

The system represents an educational commerce platform selling courses and learning products.

A customer can create multiple orders.

An order can contain multiple products.

A product belongs to one category.

An order can have an employee associated with it.

An order can have payment information.

This produces realistic one-to-many and many-to-many relationships.

### Data structures

`vector` represents table storage.

`unordered_map<int, size_t>` represents primary-key indexes.

`unordered_map<string, vector<int>>` represents the city index.

The use of separate indexes demonstrates the distinction between table storage and access paths.

### Foreign-key validation

Before inserting a product, the implementation checks that its category exists.

Before inserting an order, it checks that the customer exists and that an optional employee exists when specified.

Before inserting an order item, it checks that both the order and product exist.

This reproduces the conceptual role of relational foreign keys.

### Aggregation

The customer revenue report groups orders by customer ID and calculates revenue.

The product report aggregates units and revenue by product.

C++ does not automatically provide SQL's `GROUP BY`, so the program explicitly creates aggregation maps and then sorts the resulting records.

This makes the underlying computational work visible.

### Transactions

The `Database` class stores a snapshot before beginning a transaction.

A successful operation calls `commit()`.

An exception triggers `rollback()`.

This is a simplified educational model of atomicity.

It does not implement database write-ahead logging, concurrent transactions, crash recovery, locking, or durable storage.

### Performance case study

The program compares a linear scan with an indexed lookup over a synthetic dataset.

A linear scan has O(n) lookup complexity.

A hash-based index has expected O(1) lookup complexity for suitable keys, although real performance depends on hashing, collisions, memory locality, distribution, and implementation details.

Building the index requires O(n) work and O(n) additional storage.

This illustrates why indexes are not free optimizations.

## Important distinctions

### SQL versus a programming language

SQL describes data operations declaratively.

A procedural programming language such as Python, JavaScript, or C++ generally specifies control flow explicitly.

For example, a SQL query can request revenue grouped by customer without explicitly describing how the database should iterate through every row.

The database optimizer decides an execution strategy.

The C++ and JavaScript implementations make much of this execution process explicit.

### Database versus application data structures

An array or vector is not equivalent to a relational database.

A production database provides capabilities such as:

- persistent storage
- transactions
- constraints
- query optimization
- indexes
- concurrency control
- crash recovery
- access control
- backup mechanisms

The JavaScript and C++ implementations intentionally model selected concepts rather than reproducing a complete database engine.

### Primary key versus foreign key

A primary key identifies a record within its table.

A foreign key references a key in another table.

The two serve different purposes.

### WHERE versus HAVING

`WHERE` filters rows before grouping.

`HAVING` filters groups after aggregation.

### INNER JOIN versus LEFT JOIN

`INNER JOIN` keeps matching rows.

`LEFT JOIN` keeps all rows from the left side and adds matching rows from the right side when available.

### DELETE versus DROP

`DELETE` removes rows from a table.

`DROP TABLE` removes the table structure itself.

They are fundamentally different operations.

### WHERE versus ON in outer joins

With a `LEFT JOIN`, placing a right-side condition in `WHERE` can eliminate NULL-extended rows and effectively change the result into inner-join behavior.

A condition that is intended to control which right-side rows participate in the join can often belong in the `ON` clause.

## Edge cases

### Empty result sets

A query may legitimately return no rows. Applications should handle an empty result rather than assuming at least one record exists.

### NULL values

Aggregates and comparisons treat NULL specially. `COUNT(column)` ignores NULL values while `COUNT(*)` counts rows.

### Duplicate values

Non-key attributes can often legitimately repeat. Only attributes constrained by `UNIQUE` must be unique.

### Duplicate join matches

A one-to-many join intentionally produces multiple result rows.

For example, joining one order with three order items produces three joined rows.

This is expected behavior rather than a database error.

### Zero quantities

The project prohibits zero and negative order-item quantities because an order item represents a purchased quantity.

### Negative financial values

Product prices, salaries, payments, and unit prices are constrained to non-negative values.

The exact financial model of a real application may require stronger monetary handling, including fixed-precision decimal types rather than binary floating-point arithmetic.

### Empty tables

Aggregate queries over empty tables can produce NULL for some aggregate functions. Application code should handle those cases appropriately.

## Exceptions and failure conditions

The Python implementation catches SQLite integrity errors.

The JavaScript implementation defines `ConstraintError` and `ForeignKeyError`.

The C++ implementation defines corresponding exception classes.

These failures include:

- duplicate primary keys
- duplicate email addresses
- invalid foreign keys
- invalid product prices
- invalid stock values
- invalid order statuses
- missing required fields
- insufficient stock
- duplicate payments

The database should reject invalid states rather than relying exclusively on application-level assumptions.

## Common mistakes

### Forgetting WHERE

This is one of the most dangerous SQL mistakes.

An `UPDATE` without a `WHERE` can modify every row.

A `DELETE` without a `WHERE` can delete every row.

### Treating NULL as a normal value

Use `IS NULL` instead of `= NULL`.

### Using SELECT *

`SELECT *` can return unnecessary columns and make application interfaces more fragile when schemas change.

Explicit columns make queries clearer.

### Building SQL through string concatenation

String concatenation with untrusted input can introduce SQL injection.

Parameterized statements should be used.

### Missing join conditions

An incorrect join condition can multiply rows and corrupt aggregate calculations.

### Ignoring transactions

A business operation involving several dependent writes can leave partial state when a failure occurs unless it is handled atomically.

### Creating too many indexes

Every index has storage and write-maintenance costs.

### Assuming all SQL databases behave identically

SQL dialects, data types, functions, transaction behavior, isolation levels, optimizers, and indexing features differ between database systems.

## Performance considerations

Database performance depends on more than raw query complexity.

Important factors include:

- number of rows
- indexes
- selectivity
- join order
- query plan
- memory
- disk I/O
- concurrency
- network latency
- transaction duration
- result-set size

### Indexes

Indexes can make repeated searches much faster.

The project includes indexes for:

- customer city
- order customer and date
- order status
- product category
- order-item product

A composite index such as `(customer_id, order_date)` can support queries that first identify a customer and then work with dates for that customer.

Index column order matters.

### Query plans

The Python script uses `EXPLAIN QUERY PLAN`.

A query plan provides information about how SQLite intends to access data.

Query plans should be examined when performance problems are real rather than creating indexes blindly.

### Result size

Returning thousands or millions of unnecessary rows can be expensive even when the database query itself is efficient.

Applications should select only required columns and use pagination for large result sets.

### Transactions

Long-running transactions can increase contention.

Transactions should generally contain the operations required for atomicity without holding resources unnecessarily.

## Security considerations

SQL security begins with treating database input as untrusted.

### SQL injection

Use parameterized queries.

The Python implementation demonstrates this with `?` parameters.

### Least privilege

Production applications should use database accounts with only the permissions required for their responsibilities.

An application that only needs to read reporting data should not automatically receive permission to drop tables.

### Credentials

Database credentials should not be committed to source control.

Production secrets should be managed through an appropriate secret-management mechanism or protected environment configuration.

### Personal data

Customer names and email addresses represent personal information.

Applications should collect, store, process, and expose personal information according to applicable organizational and legal requirements.

### Backups

Backups containing customer or payment data require appropriate protection.

Access controls and encryption should be considered for both live databases and backups.

## Implementation considerations

### SQLite

SQLite is embedded and file-oriented rather than a traditional client-server database.

It is useful for:

- learning
- local applications
- prototypes
- testing
- small embedded workloads

It has a different concurrency and operational model from server databases.

### PostgreSQL and MySQL

Server database systems provide features for multi-user workloads, networking, administration, authentication, replication, operational monitoring, and more sophisticated concurrency requirements.

SQL syntax is similar across systems but not identical.

A query written for SQLite may require changes when moved to PostgreSQL or MySQL.

## Data types and monetary values

The Python SQLite implementation uses SQLite's dynamic typing model and stores monetary examples as numeric values.

For production financial systems, monetary representation deserves careful design.

Binary floating-point values can introduce representation errors.

Depending on the database and application requirements, fixed-precision decimal types or integer minor units such as paise or cents may be preferable.

## Date and time considerations

The Python SQLite implementation uses ISO-style timestamp text values.

SQLite does not have a dedicated strict timestamp storage class comparable to some server databases.

Production systems should explicitly define:

- timezone policy
- storage representation
- date versus timestamp semantics
- daylight-saving behavior where relevant
- serialization format

UTC-based storage is common for timestamps in distributed systems, with local timezone conversion performed at presentation boundaries when appropriate.

## Production database design

A production relational system normally requires:

- carefully designed schemas
- constraints
- migrations
- backups
- restore testing
- access control
- monitoring
- logging
- query performance analysis
- transaction management
- concurrency planning
- disaster-recovery procedures

Schema changes should normally be handled through versioned migrations rather than manually editing production tables.

Testing should include both successful operations and expected failure conditions.

## Relationship between the three implementations

| Concern | Python | JavaScript | C++ |
|---|---|---|---|
| Real SQL engine | Yes, SQLite | No | No |
| Tables | SQLite tables | `Table` class | vectors and structs |
| Primary-key lookup | SQLite indexes | `Map` | `unordered_map` |
| Foreign-key validation | SQLite constraints | application validation | explicit validation |
| Joins | SQL joins | join functions | explicit lookup/join logic |
| Aggregation | SQL aggregate functions | grouping functions | aggregation maps |
| Transactions | SQLite transactions | snapshot transactions | snapshot transactions |
| Query optimizer | SQLite | None | None |
| Async application behavior | not central | Promise and `async`/`await` | not central |
| Performance model | query plans | data-structure comparison | measured scan/index comparison |
| Systems-level visibility | moderate | application-level | high |

The Python implementation demonstrates what SQL actually looks like when executed by a relational database engine.

The JavaScript implementation explains how relational concepts can appear inside application code.

The C++ implementation makes storage, indexes, validation, transactions, and algorithmic complexity explicit.

## Real-world relevance

The project models patterns found in many production systems.

An e-commerce system can use the same concepts for:

- customers
- products
- inventory
- orders
- order lines
- payments

A banking system uses related concepts for:

- customers
- accounts
- transactions
- branches
- permissions

A learning platform can model:

- students
- courses
- enrollments
- instructors
- payments
- assessments

A business analytics platform can query operational tables using:

- joins
- aggregates
- CTEs
- window functions
- ranking
- date-based analysis

The relational model is therefore not limited to the example domain. The same principles apply to many structured business applications.

## Files and execution

The Python file can be executed with a standard Python installation because it uses only the standard library.

The JavaScript file can be executed with a modern Node.js runtime and has no external npm dependency.

The C++ case study is designed for C++17 or later and uses only the C++ standard library.

The Python implementation is the authoritative SQL demonstration in this project because it executes statements against an actual SQLite database.

## Concepts demonstrated by the complete project

The implementations collectively cover:

- relational databases
- tables
- rows
- columns
- schemas
- primary keys
- foreign keys
- candidate uniqueness
- constraints
- normalization
- one-to-many relationships
- many-to-many relationships
- DDL
- DML
- SELECT queries
- filtering
- sorting
- aliases
- expressions
- NULL
- joins
- aggregation
- GROUP BY
- HAVING
- subqueries
- correlated subqueries
- CTEs
- CASE expressions
- window functions
- views
- indexes
- query plans
- transactions
- ACID principles
- rollback
- parameterized SQL
- SQL injection prevention
- data validation
- error handling
- application-level relational modeling
- asynchronous database-access patterns
- algorithmic complexity
- performance trade-offs
- production database design considerations
