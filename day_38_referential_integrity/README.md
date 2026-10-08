# Referential Integrity: Foreign-Key Relationships and Cascading Actions

## Scope

Referential integrity is the relational-database property that keeps relationships between parent and child rows valid. A foreign key expresses the dependency, while a referential action defines what happens when the referenced parent key is updated or deleted.

This implementation set models a customer-to-order-to-order-item hierarchy:

`Customer -> Order -> OrderItem`

It also includes two additional relationship patterns:

`Customer -> CustomerContact` using `SET NULL`

`Employee -> Employee` using a self-referencing foreign key

The six deliverables deliberately approach the subject from different technical perspectives. Python provides an executable in-memory integrity model and a real SQLite enforcement example. JavaScript models relationship changes through an event-driven service. C++ presents a repository-style integrity engine with explicit policy handling. Java models the domain with records, policies, interfaces, streams, and service-level rules. PostgreSQL provides authoritative relational constraints, indexes, transactions, cascading behavior, and metadata queries.

## Core Referential-Integrity Model

A foreign key connects a child column to a candidate key, normally a primary key or unique key, in a parent table.

For the order model:

`customer.customer_id` is the referenced parent key.

`customer_order.customer_id` is the foreign key.

A valid order therefore requires its `customer_id` to identify an existing customer.

The same rule applies to the second relationship:

`customer_order.order_id` is the parent key.

`order_item.order_id` is the foreign key.

This creates a dependency chain. An order cannot be created with a nonexistent customer, and an order item cannot be created with a nonexistent order.

Referential integrity is different from ordinary domain validation. A rule such as `quantity > 0` is a domain constraint. A rule such as `order.customer_id` must identify an existing customer is a relationship constraint.

## Foreign Keys as Database Invariants

Application code can check whether a parent exists before inserting a child, but that check alone does not establish a durable database invariant.

Two application processes can attempt changes concurrently. A database administrator can execute SQL directly. A migration can manipulate data. Another service may write to the same database.

The foreign-key constraint therefore belongs at the database boundary when the relationship is part of the relational model.

The PostgreSQL implementation contains:

`FOREIGN KEY (customer_id) REFERENCES customer(customer_id)`

and:

`FOREIGN KEY (order_id) REFERENCES customer_order(order_id)`

These constraints make invalid references database errors rather than merely application-level warnings.

The Python, JavaScript, C++, and Java implementations still validate relationships before mutation. Their validation represents useful domain behavior and produces clearer application errors, while the database remains the authoritative integrity boundary in a multi-client system.

## Parent and Child Semantics

A parent row is referenced by one or more child rows.

For example, a customer can have many orders:

`customer.customer_id = 42`

can be referenced by:

`customer_order.customer_id = 42`

The child foreign key does not normally have to be unique. Multiple orders can therefore reference the same customer.

A foreign key can also be nullable. When a nullable foreign key contains `NULL`, it does not identify a parent row. This is important for `SET NULL` relationships.

The customer-contact model demonstrates this distinction. A contact can remain meaningful without an associated customer, so `customer_contact.customer_id` is nullable and uses `ON DELETE SET NULL`.

By contrast, `customer_order.customer_id` is declared `NOT NULL`. An order must always have an owning customer in this model.

## Referential Actions

### RESTRICT

`RESTRICT` prevents deletion of a parent when dependent rows exist.

The customer-to-order relationship uses this behavior.

If customer `CUST-001` has orders, deleting that customer is rejected. The database preserves the relationship rather than silently deleting business data.

This is appropriate when child records have business significance independent of the physical lifetime of the parent.

The Python model's `delete_customer_restrict()` method explicitly searches for dependent orders and rejects the deletion.

The JavaScript and Java services use the same relationship policy concept.

The PostgreSQL constraint is authoritative:

`ON DELETE RESTRICT`

The practical consequence is that the application must first remove or reassign dependent orders before the customer can be deleted.

### CASCADE

`CASCADE` propagates a parent deletion to dependent rows.

The order-to-order-item relationship uses:

`ON DELETE CASCADE`

An order item has no independent meaning in this domain after its containing order is removed. Therefore, deleting an order automatically deletes its items.

A second cascade can create a transitive operation.

If customer-to-order is also configured as `CASCADE`, then:

`Customer deletion -> Order deletion -> OrderItem deletion`

The C++ and Java programs explicitly model this transitive relationship. The Python implementation has `delete_customer_with_cascade()` for the same reason.

Cascade behavior should be chosen because the child is logically dependent on the parent, not merely because cascading is convenient.

### SET NULL

`SET NULL` removes the parent reference while preserving the child.

The foreign-key column must therefore permit `NULL`.

The contact relationship uses this design:

`customer_contact.customer_id`

references:

`customer.customer_id`

with:

`ON DELETE SET NULL`

When the customer disappears, the contact survives and its `customer_id` becomes `NULL`.

The Python, JavaScript, C++, and Java implementations explicitly distinguish this policy from mandatory relationships. The C++ and Java models reject `SET NULL` for mandatory child fields rather than pretending that a non-nullable field can represent a null relationship.

### ON UPDATE CASCADE

`ON UPDATE CASCADE` propagates a referenced-key change into dependent foreign keys.

The PostgreSQL script includes it on the customer-to-order and order-to-item relationships.

Primary-key updates are uncommon in many production systems because stable surrogate keys are normally preferred. The action is still important for understanding the full referential-action model.

The Python and JavaScript examples demonstrate the corresponding conceptual operation by changing the parent identifier and synchronizing dependent references.

## Relationship Graph

The principal relational structure is:

`Customer`

`  |`

`  +---- CustomerContact`

`  |`

`  +---- CustomerOrder`

`           |`

`           +---- OrderItem`

`CustomerContact` uses `SET NULL`.

`CustomerOrder` uses `RESTRICT` for customer deletion.

`OrderItem` uses `CASCADE` for order deletion.

This means the relationships have deliberately different semantics. They are not interchangeable.

A contact can survive without a customer.

An order cannot exist without a customer.

An order item cannot exist without an order.

## Python Implementation

The Python program begins with an in-memory representation of the relationship graph using dictionaries keyed by primary identifiers.

`ReferentialIntegrityStore` maintains separate collections for customers, orders, and items.

The insertion methods demonstrate the most important foreign-key rule directly. `add_order()` rejects a customer identifier that is not present in the customer collection. `add_item()` similarly rejects a nonexistent order identifier.

The implementation also separates relationship failures from ordinary domain validation. `ReferentialIntegrityError` represents broken relationships, while `ValueError` handles conditions such as negative order amounts or invalid quantities.

The `validate()` method scans the entire relationship graph and reports references that do not resolve to an existing parent.

The program demonstrates three deletion policies:

`delete_customer_restrict()` blocks deletion when orders exist.

`delete_order_cascade()` removes dependent items before deleting the order.

`delete_customer_with_cascade()` demonstrates a transitive cascade across two relationships.

The final Python example creates actual SQLite tables with foreign keys enabled through `PRAGMA foreign_keys = ON`. This is important because SQLite's foreign-key enforcement must be explicitly enabled for the connection.

That section moves from simulated application behavior to database-level enforcement.

## JavaScript Implementation

The JavaScript implementation uses `Map` objects to represent indexed entity collections.

This is appropriate for the demonstration because relationship lookup by identifier is a primary operation. It also avoids treating arrays as if they were relational tables with database constraints.

`Repository` owns the parent and child collections and stores relationship policies explicitly.

`EventBus` adds an event-driven dimension. Deletion of a child through a cascade emits an `item.deleted` event, while deletion of an order emits an `order.deleted` event.

This distinction is useful in application architectures where a database operation may need to trigger application-level cache invalidation, audit logging, or other observers.

The JavaScript implementation also demonstrates an important boundary: an in-memory snapshot can illustrate rollback behavior, but it is not equivalent to a real database transaction. A production application should use the database transaction mechanism when atomicity across multiple persistent changes is required.

## C++ Case Study

The C++ program models a repository-style integrity engine.

`RepositoryGovernanceEngine` owns customers, orders, and order items in `std::unordered_map` containers. The maps provide direct identifier-based access while the relationship scans locate dependent children.

The case study separates:

- parent existence checks
- child insertion
- dependent discovery
- deletion policy evaluation
- cascading deletion
- relationship reassignment
- integrity validation

`DeleteAction` represents `RESTRICT`, `CASCADE`, and `SET NULL` explicitly.

The implementation intentionally rejects `SET NULL` when the domain model defines `OrderItem::orderId` as mandatory. This demonstrates an important schema-design rule: a referential action cannot contradict the nullability and business invariant of the child attribute.

The program also discusses complexity. Its dependent-discovery functions scan the relevant unordered map, giving linear behavior relative to the collection being scanned.

A relational database can improve the corresponding operations through indexes on foreign-key columns. This is why the PostgreSQL implementation creates indexes on `customer_order.customer_id` and `order_item.order_id`.

## Java Enterprise Domain Model

The Java implementation represents relationship rules through domain types and services.

`Customer`, `Order`, and `OrderItem` are immutable records. Their compact constructors enforce local invariants such as positive identifiers, nonempty names, nonnegative amounts, and positive quantities.

`RelationshipPolicy` makes the referential action explicit rather than burying it in scattered conditional statements.

`IntegrityRule` defines a reusable validation abstraction. `OrderCustomerRule` validates customer references, while `ItemOrderRule` validates order references.

`RepositoryService` coordinates entity creation, deletion, reassignment, and complete integrity validation.

The service uses Java streams to locate dependent identifiers. This provides a clear distinction between the domain relationships and the storage implementation.

The Java example also models an important policy conflict. A mandatory `orderId` cannot support `SET NULL` without changing the domain representation. The service therefore rejects that combination.

## SQL Data Model

The PostgreSQL script creates the `referential_integrity_demo` schema and defines five tables:

`customer`

Stores parent customer records and exposes `customer_id` as the primary key.

`customer_order`

References `customer(customer_id)` and uses `ON DELETE RESTRICT`.

`order_item`

References `customer_order(order_id)` and uses `ON DELETE CASCADE`.

`customer_contact`

References `customer(customer_id)` and uses `ON DELETE SET NULL`.

`employee`

References itself through `manager_id`, demonstrating a self-referencing foreign key.

The database constraints enforce both structural and domain rules.

Examples include:

`PRIMARY KEY` for entity identity.

`UNIQUE` for business identifiers such as customer codes and order references.

`NOT NULL` for mandatory relationships.

`CHECK` constraints for amounts, quantities, statuses, and nonblank names.

`FOREIGN KEY` constraints for relationship validity.

## SQL Transactional Demonstrations

The PostgreSQL script uses transactions around destructive demonstrations.

The `RESTRICT` example attempts to delete a customer that still owns orders and captures the expected foreign-key violation.

The `CASCADE` example deletes an order and inspects the dependent order items. The transaction is rolled back so the demonstration does not permanently modify the initial dataset.

The `SET NULL` example demonstrates that the contact survives while its parent reference becomes null.

The `ON UPDATE CASCADE` demonstration changes a referenced customer identifier temporarily and shows that dependent order references follow the change.

Rolling back these demonstrations is important because an educational SQL script should be repeatable without requiring the sample data to be manually reconstructed after every execution.

## Self-Referencing Foreign Keys

The employee table demonstrates a relationship in which the parent and child entity type are the same.

`employee.manager_id` references `employee.employee_id`.

A root employee has a null manager reference.

A subordinate employee stores another employee's identifier as its manager.

The foreign key prevents an employee from referencing a nonexistent manager.

`ON DELETE SET NULL` means that deleting a manager does not delete subordinate employees. Their manager relationship is simply removed.

The recursive common table expression in the SQL script traverses this hierarchy.

This is a different relationship pattern from the customer-order hierarchy even though the same foreign-key mechanism enforces it.

## Integrity Validation Versus Referential Constraints

Application validation and database constraints have different responsibilities.

Application validation can provide immediate, domain-friendly feedback before attempting a write.

Database constraints protect the stored state against every writer that reaches the database.

A robust system can use both.

For example, an application can first check that customer `42` exists and return a clear validation message. The database should still enforce the foreign key because another process could delete customer `42` or modify related data between application-level checks and the final write.

A foreign key therefore establishes an invariant at the persistence boundary.

## Indexing Foreign Keys

A primary key automatically receives an index in PostgreSQL, but PostgreSQL does not automatically create an index on every referencing foreign-key column.

The child-side columns are therefore indexed explicitly:

`customer_order.customer_id`

`order_item.order_id`

`customer_contact.customer_id`

`employee.manager_id`

These indexes support common operations such as:

- finding all orders belonging to a customer
- checking for dependent orders before a parent deletion
- joining orders to customers
- finding items belonging to an order
- traversing employee hierarchies

Indexing strategy should follow actual access patterns. An index is not automatically beneficial merely because a column participates in a foreign key, but high-volume parent-child operations usually justify careful indexing.

## Cascading and Transaction Boundaries

A cascade is part of the database operation that triggers it.

When an order is deleted, its cascading order-item deletions occur as part of the same database statement and transaction.

This is materially different from an application manually issuing several independent delete statements.

For example, an application that first deletes order items and then deletes the order can leave an inconsistent intermediate state if the second operation fails outside a transaction.

A properly designed transaction provides atomicity around related changes.

Database-level cascading also reduces the risk that an application forgets one dependent table when the relationship is intentionally defined as cascading.

## Transitive Cascades

A cascade can propagate through multiple foreign-key relationships.

In this model:

`Customer -> Order` can be configured as `CASCADE`.

`Order -> OrderItem` is configured as `CASCADE`.

Deleting a customer can therefore remove its orders and those orders' items.

This behavior must be treated carefully because one parent deletion can affect many rows across multiple tables.

The appropriate question is not whether cascade deletion is technically possible. The important question is whether the child data has the same lifecycle as its parent.

If order items must be retained for legal, accounting, or audit reasons, `CASCADE` would be inappropriate even if it is convenient.

## Common Integrity Failures

An orphan child occurs when a child row contains a foreign-key value that does not identify an existing parent.

The examples deliberately attempt such operations:

An order references nonexistent customer `999`.

An order item references nonexistent order `999999999`.

Both are rejected.

Another failure is attempting to delete a parent while a `RESTRICT` relationship still has children.

A different failure occurs when a developer chooses `SET NULL` but defines the foreign-key column as mandatory. The referential action and column definition then express incompatible requirements.

Duplicate parent keys are also rejected by the primary-key constraint before relationship processing can succeed.

## Practical Design Decisions

Use `RESTRICT` when the child must prevent deletion of its parent.

Use `CASCADE` when the child is genuinely dependent on the parent and should disappear with it.

Use `SET NULL` when the child remains meaningful without the parent and the relationship is optional.

Use `NOT NULL` on a foreign key when every child must have a parent.

Allow `NULL` when the relationship is intentionally optional.

Keep foreign-key enforcement in the database even when application code performs pre-validation.

Index high-volume foreign-key columns when joins, dependent discovery, or parent deletion checks require efficient access.

Use transactions when several relationship changes must succeed or fail together.

## Referential Integrity and Data Lifecycle

Foreign keys describe more than how tables join. They encode lifecycle decisions.

The customer-order relationship says that an order is structurally dependent on a customer.

The order-item relationship says that an item is structurally dependent on an order.

The customer-contact relationship says that a contact can survive independently of its previous customer.

The employee hierarchy says that an employee can survive without a manager.

These are different business lifecycle decisions represented through the same relational mechanism.

The quality of a referential-integrity design therefore depends on choosing the action that matches the intended lifecycle of each relationship.

## Production Considerations

Foreign-key constraints should normally be created deliberately as part of the database schema rather than treated as optional application conventions.

Parent and child identifiers should use compatible data types.

Referenced keys should be stable and appropriately indexed.

Foreign-key columns should be nullable only when an absent relationship is semantically valid.

Cascading rules should be reviewed carefully because one deletion can affect large dependency graphs.

Large tables should have appropriate indexes on frequently used foreign-key columns.

Schema migrations should account for existing orphaned data before adding a new foreign-key constraint.

Data cleanup should occur before enabling a constraint when legacy data contains invalid references.

Transactions should be used for multi-step relationship changes.

Deletion policies should reflect business lifecycle semantics rather than simply reducing application code.

## Implementation Comparison

| Deliverable | Referential-integrity focus | Distinct technical contribution |
| --- | --- | --- |
| Python | Parent-child validation, RESTRICT, CASCADE, SET NULL, SQLite enforcement | Executable in-memory model plus real SQLite foreign-key behavior |
| JavaScript | Relationship policies, deletion events, cascading state changes | Event-driven application representation |
| C++ | Integrity engine and explicit deletion-policy model | System-oriented case study with explicit complexity discussion |
| Java | Domain types, policy abstractions, validation rules | Enterprise-style service and immutable record model |
| PostgreSQL SQL | Foreign keys, constraints, indexes, transactions, actions | Authoritative relational enforcement and metadata inspection |
| README | Conceptual relationships and implementation decisions | Cross-implementation technical interpretation |

## Limitations

The in-memory Python, JavaScript, C++, and Java models do not provide the concurrency guarantees of a relational database.

Their relationship checks operate within the process that owns the data structures. They therefore demonstrate the semantics of referential integrity rather than replacing database constraints in a multi-client system.

The PostgreSQL script is the authoritative example for database-level enforcement. It demonstrates how the same conceptual relationship is represented using actual relational constraints, indexes, transactions, and referential actions.

The examples also use a relatively small dependency graph. Production schemas can contain many levels of dependencies, cycles, archival requirements, soft-delete policies, partitioning, and high-volume data movement. Those concerns require relationship-specific design rather than blindly applying `CASCADE` to every foreign key.
