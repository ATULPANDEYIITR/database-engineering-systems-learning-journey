# PostgreSQL Table Engineering

## Scope

This project examines the design and evolution of PostgreSQL relational tables through `CREATE TABLE`, `ALTER TABLE`, and integrity constraints. The examples model an inventory and order-management system in which products belong to categories, customers place orders, and order items retain purchase-time prices.

The central engineering objective is to make the database enforce structural and relational rules instead of relying exclusively on application code.

## Table definition and data modeling

A table definition establishes the permitted structure of stored data. Its columns define attributes, data types define the kinds of values those attributes can store, defaults supply omitted values, and constraints restrict invalid states.

The inventory schema separates products, categories, customers, orders, and order items because each represents a distinct entity or relationship.

| Table | Responsibility | Important relationship |
|---|---|---|
| `categories` | Defines product classifications | One category can classify many products |
| `products` | Stores SKU, description, price, and available stock | References a category |
| `customers` | Stores customer identity and contact information | One customer can place many orders |
| `orders` | Records an order and its lifecycle status | References a customer |
| `order_items` | Records products, quantities, and captured prices within an order | References both an order and a product |

Identity columns provide generated numeric keys. These keys remain independent of changeable business attributes such as product names or customer email addresses.

The `order_items` table uses a composite primary key consisting of `order_id` and `product_id`. This design permits a product to appear in different orders while preventing duplicate entries for the same product within one order. A system that permits separate lines for the same product would instead use a generated order-item identifier.

## Data types and defaults

PostgreSQL data types should reflect the intended meaning and range of an attribute.

- `BIGINT` provides a large integer range for generated identifiers.
- `INTEGER` represents inventory quantities in the example.
- `TEXT` stores names, SKUs, descriptions, and email addresses.
- `NUMERIC(12,2)` represents prices with fixed decimal precision, avoiding the binary rounding behavior associated with floating-point monetary calculations.
- `BOOLEAN` records whether a product is active.
- `TIMESTAMPTZ` stores timestamps with time-zone-aware semantics.

A declaration such as `stock_quantity INTEGER NOT NULL DEFAULT 0` establishes three distinct rules. The column stores integer values, cannot contain SQL `NULL`, and receives zero when an insert omits the column.

A default does not replace a constraint. Explicitly inserting a negative quantity still requires rejection through a suitable `CHECK` constraint.

## Constraints and integrity enforcement

### Primary keys

A primary key uniquely identifies each row and prohibits null key values. PostgreSQL creates a unique index to enforce the primary-key constraint.

A generated identifier is useful when a business value may change. The product name, for example, should not ordinarily be the primary key because names can be corrected or reused.

### Unique constraints

`UNIQUE (sku)` prevents two products from having the same SKU. `UNIQUE (email)` provides a corresponding rule for customer email addresses.

A unique constraint can span multiple columns. This is useful when uniqueness belongs to a combination of attributes rather than to any one attribute independently.

PostgreSQL normally treats null values as distinct under a unique constraint. Consequently, a unique nullable column can contain multiple null values. A required business identifier should generally use both `UNIQUE` and `NOT NULL`.

### NOT NULL

`NOT NULL` requires an actual value for a column. It is distinct from a `CHECK` constraint.

PostgreSQL considers a check satisfied when its expression evaluates to either true or unknown. As a result, `CHECK (unit_price >= 0)` alone does not prohibit a null price. Combining it with `NOT NULL` enforces both requirements.

### CHECK constraints

The product schema uses checks to reject negative prices, negative stock quantities, empty trimmed SKUs, and empty product names.

A check is most suitable for a rule that can be evaluated against the row being inserted or updated. It should not be used as a substitute for a foreign key or for rules requiring dependable comparisons with other rows.

### Foreign keys

`products.category_id` references `categories.category_id`. The database therefore rejects a non-null category identifier that has no matching parent row.

The example uses `ON DELETE SET NULL`, allowing a category to be removed without deleting its products. This action requires the referencing column to permit null values.

Orders use `ON DELETE RESTRICT` for customers because deleting a customer with dependent orders should not silently erase the business record. Order items use `ON DELETE CASCADE` for their parent order, while product references use `ON DELETE RESTRICT`.

Referential actions are business decisions. `CASCADE`, `SET NULL`, and `RESTRICT` have different consequences and should be selected according to data-retention requirements.

### Defaults

Defaults such as `CURRENT_TIMESTAMP`, `TRUE`, and `0.00` supply values when an insert omits the associated columns.

A default is not an automatic update rule. For example, a default timestamp does not refresh `updated_at` every time a product changes. A production application must explicitly update it or use an appropriately designed trigger.

## CREATE TABLE and schema evolution

`CREATE TABLE` defines a new relation. Defining keys and constraints during creation makes the intended structure explicit from the beginning.

`ALTER TABLE` changes an existing relation while preserving its table identity. The examples add `description` and `updated_at` to the products table, then set a default for `description`.

The important distinction is between setting a default and changing existing values. `ALTER COLUMN description SET DEFAULT ''` controls future inserts that omit the column. It does not independently rewrite old rows.

The examples use `IF NOT EXISTS` for selected operations so that the demonstration can be rerun. This is a limited form of idempotency, not a full schema verification mechanism. An existing column may have the wrong type or constraint definition even though an `ADD COLUMN IF NOT EXISTS` statement completes without creating it.

A reliable migration process therefore needs version tracking, controlled deployment, and verification of the resulting catalog state.

## Python implementation

The Python script uses a `ColumnDefinition` data class to represent column metadata. It validates identifiers and restricts the demonstration to a known set of PostgreSQL types.

Its constraint examples distinguish application-level validation from database enforcement. The local checks produce understandable errors, while the optional PostgreSQL execution path applies DDL and queries `information_schema.columns` and `pg_constraint`.

The optional connection uses `psycopg`. When `DATABASE_URL` is absent, the script still runs its offline demonstrations. When configured, it executes the schema statements and inspects the resulting tables and constraints.

The schema statements use fixed identifiers rather than interpolating user-provided SQL. Parameterized queries are used for catalog filters. SQL parameters safely represent values but do not substitute table or column identifiers.

## JavaScript implementation

The JavaScript program focuses on migration planning and deployment rather than reproducing the Python schema model.

Each migration has a version, a descriptive name, and a list of SQL statements. A SHA-256 checksum is computed from the migration's statements and recorded in `inventory.schema_migrations`.

On a subsequent run, an already-applied version is skipped only when its stored name and checksum match. Editing an applied migration therefore produces an error instead of silently treating changed SQL as previously deployed SQL.

The migration runner uses a PostgreSQL advisory lock to serialize cooperating migration processes. Each migration is executed in a transaction, and a failure rolls back its DDL and version record together.

The example requires the Node.js `pg` package for database execution. The offline validation path can run without it.

Advisory locks protect only deployments that cooperate with the same locking convention. They do not replace database permissions, migration review, backups, or an operational rollback strategy.

## C++ case study

The C++ program represents a warehouse schema as an offline design registry.

A `Table` contains column definitions, primary-key metadata, unique keys, and check expressions. The `Schema` class rejects duplicate tables, invalid identifiers, duplicate columns, unsupported types, and keys that reference missing columns.

Foreign-key validation verifies that source and target tables exist, that the columns exist, that their types are compatible, and that the referenced single column is a primary or unique key. It also checks whether `ON DELETE SET NULL` is compatible with source-column nullability.

The program generates foreign-key DDL after the schema passes its modeled checks. It deliberately labels this output as a planning report rather than claiming that a database has been changed.

The registry is an educational subset of PostgreSQL's schema rules, not a complete PostgreSQL parser. Type compatibility, operator classes, composite references, collations, identifier quoting, and many other database details require more comprehensive validation in a production migration system.

## Java implementation

The Java program uses records for immutable column and foreign-key definitions, enums for data types and constraint categories, and dedicated classes for table metadata, migration state, and schema registration.

`TableDefinition` validates primary keys, unique keys, and column references. `SchemaRegistry` checks foreign-key targets and source-column compatibility before registering relationships.

The `Migration` class represents deployment state with `PLANNED`, `VALIDATED`, `APPLIED`, and `FAILED` values. Its state transition method prevents a migration from being marked applied before validation.

The implementation demonstrates how explicit domain types can make invalid operations harder to express. Its migration state is still an in-memory model: successful local validation is not proof that PostgreSQL accepted or committed the corresponding DDL.

## SQL implementation

The PostgreSQL script is the authoritative executable relational example. It creates the inventory schema, declares its tables and constraints, adds indexes, evolves the product table, inserts sample records, and inspects the resulting catalog.

The information schema provides portable metadata views for tables, columns, and constraints. PostgreSQL's `pg_constraint` catalog provides database-specific constraint metadata.

The order-total query joins orders to customers and order items. It uses `COALESCE` to return zero for an order without item rows. Item prices are captured separately from the current product price so historical order totals do not change merely because a product's price changes later.

The script includes controlled tests for duplicate SKUs, negative prices, invalid category references, and null product names. Each expected violation is caught inside a PL/pgSQL exception block.

## Indexes and query performance

Primary keys and unique constraints create indexes automatically. Foreign keys do not automatically create indexes on the referencing columns.

The example adds indexes for specific access patterns:

- `products(category_id, active)` supports filtering products by category and active status.
- `orders(customer_id, ordered_at DESC)` supports retrieving a customer's most recent orders.
- `order_items(product_id)` supports product-centric queries and helps with operations that need to find referencing order items.

Index order matters. A multicolumn B-tree index is generally most useful when a query constrains its leading columns. Indexes also consume storage and add work to inserts, updates, and deletes. Actual index choices should be tested against representative queries and data distributions.

## Safe schema migrations

Schema changes can affect table locks, application compatibility, deployment duration, and existing data.

A production migration should account for the following concerns:

- **Existing data:** A new `NOT NULL` or `CHECK` rule may fail if stored rows violate the intended rule. Clean or backfill the data before enforcing the constraint.
- **Lock acquisition:** Many `ALTER TABLE` operations require locks that can block concurrent work. A short statement can still wait a long time for a conflicting lock.
- **Large tables:** Adding columns with defaults is often efficient on modern PostgreSQL, but behavior depends on the operation and version. Large backfills and index builds still require careful planning.
- **Concurrent index creation:** `CREATE INDEX CONCURRENTLY` can reduce write blocking for suitable indexes, but it cannot run inside a transaction block.
- **Migration history:** Applied migrations should be immutable. Follow-up changes belong in new versions rather than edits to previously applied migration files.
- **Application compatibility:** When an application version expects a new column, deployment order must ensure the schema and application remain compatible during rollout.

A migration framework should distinguish planned changes, validated changes, successfully committed changes, and failed deployments.

## Common mistakes and limitations

- Assuming a default makes a column mandatory. A column can still be explicitly inserted as null unless `NOT NULL` or another appropriate rule prevents it.
- Using a `CHECK` constraint for a relationship that should be enforced by a foreign key.
- Assuming `UNIQUE` rejects every repeated null value. PostgreSQL's default behavior allows multiple nulls.
- Assuming `ALTER COLUMN SET DEFAULT` modifies existing records.
- Assuming `IF NOT EXISTS` confirms the full definition of an existing object.
- Assuming a successful application-side validation eliminates race conditions. Concurrent transactions can still conflict, so uniqueness and referential integrity must be enforced by the database.
- Treating a generated DDL report as proof that a database migration executed successfully.
- Building indexes without considering their write cost, storage cost, and actual query plans.

The strongest table design combines precise types, explicit constraints, suitable indexes, deliberate referential actions, and versioned migrations. Each mechanism has a distinct responsibility, and their interaction determines whether the database can maintain valid data as the application evolves.
