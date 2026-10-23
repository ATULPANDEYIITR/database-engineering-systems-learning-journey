# PostgreSQL Stored Procedures and Triggers

## Scope

Stored procedures and triggers are database-side mechanisms for encapsulating operations and automatically enforcing or reacting to data changes.

They solve different problems:

| Mechanism | Primary purpose | Invocation |
|---|---|---|
| Function | Encapsulate reusable logic and optionally return a value | `SELECT`, expressions, or other database code |
| Procedure | Encapsulate an explicit database operation | `CALL` |
| Trigger | Automatically execute database logic when a table event occurs | Implicitly through `INSERT`, `UPDATE`, or `DELETE` |
| Trigger function | Function invoked by a trigger | Automatically by PostgreSQL |
| Constraint | Declaratively enforce a data rule | Automatically by PostgreSQL |

The five implementations use the same core domain while emphasizing different programming models.

The central relationship is:

**Procedure → explicitly requested operation**

**Trigger → automatically executed reaction**

**Constraint → declaratively enforced invariant**

A procedure can coordinate several writes. A trigger can enforce or maintain behavior whenever a relevant table event occurs, regardless of which application issued the statement.

## Domain Model

The examples use a financial-account domain because it creates meaningful database automation requirements.

The relational model contains:

- `customers`
- `accounts`
- `account_transactions`
- `account_audit`

The principal relationship is:

Customer → Accounts → Transactions

Account changes generate audit records.

Transaction insertion automatically changes an account balance.

A transfer coordinates two transaction insertions inside one database operation.

The resulting flow is:

`Client operation`

→ `Procedure`

→ `INSERT`

→ `Transaction trigger`

→ `Account UPDATE`

→ `Account validation trigger`

→ `Audit trigger`

This illustrates why procedure and trigger responsibilities must be separated carefully.

## Stored Procedures

A procedure provides an explicit operational boundary.

The PostgreSQL implementation defines `transfer_funds`, which accepts:

- source account
- destination account
- transfer amount

The procedure validates that the accounts differ, the amount is positive, both accounts exist, both accounts are active, and the source account contains enough funds.

It then inserts a debit and a credit.

The balance itself is not manually maintained by the procedure. The transaction trigger owns that responsibility.

This division avoids having multiple pieces of code implement the same balance-maintenance rule.

The Python, JavaScript, C++, and Java implementations model this concept with explicit procedure-like service methods.

## Functions Versus Procedures

PostgreSQL functions and procedures are related but not interchangeable.

The SQL implementation uses `create_customer_account` as a function because the caller needs the generated account identifier.

The operation is invoked as an expression:

`SELECT create_customer_account(...)`

The transfer operation is a procedure:

`CALL transfer_funds(...)`

The procedure represents an operation whose primary purpose is controlled database behavior rather than producing a scalar query result.

Trigger functions are a third category. PostgreSQL requires trigger actions to execute through functions returning `TRIGGER`.

The trigger functions inspect `TG_OP`, `NEW`, and `OLD` to determine the operation and row values.

## Trigger Timing

The SQL implementation uses both `BEFORE` and `AFTER` triggers.

### BEFORE triggers

The account validation trigger executes before an account row is written.

It checks:

- account number validity
- non-negative balances
- excessive balance changes

It also updates `updated_at`.

A `BEFORE` trigger can modify `NEW` before the row is stored or reject the operation with an exception.

This is useful when the trigger needs to validate or normalize the incoming row.

### AFTER triggers

The audit trigger runs after an account change has succeeded.

It records:

- affected account
- previous balance
- new balance
- operation type
- timestamp
- database user

The transaction trigger is also an `AFTER INSERT` trigger. It interprets a newly inserted financial transaction and changes the corresponding account balance.

The distinction matters:

`BEFORE` is appropriate for validation and transformation.

`AFTER` is appropriate when the original row change must succeed before derived work is performed.

## Row-Level Automation

The triggers are declared `FOR EACH ROW`.

Therefore, each affected row produces an independent trigger invocation.

For example, inserting two transaction rows causes the transaction trigger to run twice.

This is different from a statement-level trigger, which executes once for the SQL statement regardless of the number of rows affected.

Row-level triggers are useful when the logic needs access to individual `OLD` and `NEW` row values.

They can become expensive for large bulk operations when every row causes substantial additional work.

## Automatic Balance Maintenance

The `account_transactions` table stores the business event.

The account balance is derived from that event stream.

For a credit:

`new_balance = old_balance + amount`

For a debit:

`new_balance = old_balance - amount`

The trigger executes this rule automatically.

This prevents callers from having to remember to update both tables.

The design also provides a single database-level location for the balance-maintenance rule.

A major limitation is that triggers can make data changes less obvious to developers who inspect only the original SQL statement. Documentation, naming, tests, and controlled trigger scope are therefore important.

## Validation and Constraints

The SQL design does not use triggers for every possible rule.

Declarative constraints handle simple invariants:

- primary keys prevent duplicate identifiers
- foreign keys prevent orphaned relationships
- unique constraints prevent duplicate emails and account numbers
- `CHECK` constraints prevent invalid amounts
- enum types restrict transaction and account status values

Triggers are reserved for rules requiring procedural behavior.

This distinction is important because a simple invariant is usually clearer and easier for PostgreSQL to enforce through a constraint.

For example:

`amount > 0`

is naturally a `CHECK` constraint.

The rule:

`insert transaction → modify account balance → create audit record`

requires procedural behavior and is suitable for triggers.

## Trigger Failure and Atomicity

The debit trigger refuses to perform a debit when the account does not have enough funds.

The failure raises an exception.

In PostgreSQL, an unhandled exception causes the current transaction to fail. Changes performed within that transaction can then be rolled back.

The SQL script demonstrates this through explicit transaction blocks.

This provides a stronger correctness model than application code that performs independent writes without transaction boundaries.

The in-memory Python, JavaScript, C++, and Java implementations explicitly restore state to approximate this behavior.

They cannot reproduce the full concurrency and recovery guarantees of PostgreSQL.

## Transactional Procedure Behavior

The transfer procedure locks the two account rows using `FOR UPDATE`.

This matters when concurrent transactions can attempt to modify the same accounts.

The implementation obtains locks in account-ID order. Consistent lock ordering reduces the risk of deadlocks when two concurrent transfers operate in opposite directions.

The procedure then creates:

- one debit transaction
- one credit transaction

Both operations occur in the same transaction context when the caller invokes the procedure normally.

If either operation fails, PostgreSQL can roll back the complete transaction.

This creates an important boundary:

**The procedure defines the business operation.**

**The transaction defines atomicity.**

**The trigger defines automatic row-level behavior.**

These responsibilities should not be conflated.

## Audit Automation

The `account_audit` table records balance changes automatically.

The audit trigger stores both the old and new values.

This creates an immutable-style history of important account changes without requiring every caller to manually write audit rows.

The JavaScript, Java, C++, and Python implementations maintain equivalent audit collections.

The SQL version also records `CURRENT_USER`, which provides database-level attribution.

For production systems, audit requirements may require additional controls such as retention rules, append-only permissions, partitioning, and carefully restricted access.

## Python Implementation

The Python program models a database using dictionaries and domain classes.

`Database` owns:

- accounts
- transactions
- audit records
- trigger registries

Trigger registration is explicit.

`before_insert_account` validates account creation.

`before_update_account` rejects excessive balance changes.

`after_update_account` records audit history.

`after_insert_transaction` applies transaction effects to the account balance.

The procedure-like `create_account_procedure` validates input before delegating the actual insert.

`transfer_procedure` coordinates two transaction operations and retains snapshots so failures can restore affected state.

The implementation intentionally separates:

- data storage
- trigger dispatch
- validation
- audit behavior
- business operations

This makes trigger execution visible while preserving the conceptual distinction between explicit and automatic database logic.

The rollback code is deliberately described as an approximation. PostgreSQL's transaction manager provides stronger atomicity and concurrency guarantees than an in-memory Python dictionary.

## JavaScript Implementation

The JavaScript implementation uses Node.js `EventEmitter` to model event-driven trigger behavior.

Database events include:

- `beforeInsertAccount`
- `beforeUpdateAccount`
- `afterUpdateAccount`
- `afterInsertTransaction`

This creates a useful analogy to database triggers without treating an application event emitter as a replacement for a database trigger.

The JavaScript implementation emphasizes event dispatch, immutable-style object copies, and explicit rollback snapshots.

The `transferProcedure` function coordinates two transaction events and restores state when an operation fails.

Validation is performed before database mutation, while event listeners represent automatic behavior.

The implementation uses only Node.js standard-library functionality.

## C++ Implementation

The C++ implementation treats database automation as a strongly structured domain engine.

`Database` owns relational-style collections and private trigger functions.

Money is represented as integer minor units rather than floating-point values. This avoids common binary floating-point problems in financial calculations.

For example, `1000000` represents a monetary value of `10000.00`.

The trigger sequence is explicit:

`beforeInsertAccount`

→ account insertion

`beforeUpdateAccount`

→ balance validation

`afterUpdateAccount`

→ audit creation

`afterInsertTransaction`

→ balance maintenance

The transfer operation snapshots affected state and restores it if a later operation fails.

The design uses standard C++17 containers and exceptions and requires no external libraries.

## Java Implementation

The Java implementation uses explicit domain types and service classes.

The domain model contains:

- `Account`
- `Transaction`
- `AuditRecord`
- `TransactionType`
- `AccountStatus`

`BigDecimal` is used for monetary values rather than floating-point primitives.

Trigger behavior is represented through interfaces:

- `AccountInsertTrigger`
- `AccountUpdateTrigger`
- `TransactionInsertTrigger`

This makes trigger responsibilities explicit and allows the database model to register different handlers.

`AccountProcedureService` represents controlled account creation.

`TransferProcedure` represents a multi-step business operation.

The implementation uses immutable Java records for domain values and `List.copyOf` and `Map.copyOf` when exposing collections.

This provides a stronger separation between internal mutable state and externally visible domain data.

## PostgreSQL Implementation

The PostgreSQL script is the authoritative database-oriented implementation.

It creates a dedicated schema named `procedure_trigger_lab`, making the script isolated from unrelated database objects.

The database contains:

- typed enums
- primary keys
- foreign keys
- unique constraints
- check constraints
- indexes
- functions
- procedures
- trigger functions
- triggers
- a reporting view
- sample data
- transactional demonstrations

The `accounts` table is protected by a `BEFORE INSERT OR UPDATE` trigger.

The `account_audit` table receives changes through an `AFTER` trigger.

The `account_transactions` table drives balance changes through another `AFTER INSERT` trigger.

The `transfer_funds` procedure coordinates multiple related operations and locks rows using `FOR UPDATE`.

The `account_activity_summary` view provides reporting without repeating the aggregation logic in every query.

## Transaction and Trigger Interaction

A simplified execution path for a successful transfer is:

`CALL transfer_funds(...)`

→ validate parameters

→ lock source and destination rows

→ insert debit transaction

→ transaction trigger fires

→ account balance is updated

→ account update trigger validates the new balance

→ account audit trigger records the change

→ insert credit transaction

→ transaction trigger fires

→ destination balance is updated

→ account update trigger validates the new balance

→ account audit trigger records the change

The procedure does not need to duplicate the balance-maintenance logic because the trigger owns it.

This separation is one of the most important design principles demonstrated by the implementation.

## Trigger Recursion and Side Effects

Triggers can cause additional table operations.

The transaction trigger performs an `UPDATE` on `accounts`.

That update invokes the account triggers.

Therefore, one `INSERT` into `account_transactions` causes a chain of database events.

This is useful when the dependency is intentional, but it can become difficult to reason about if triggers modify tables that activate other triggers recursively.

Production designs should therefore document trigger chains and avoid unnecessary cross-table side effects.

A trigger should have a narrow, predictable responsibility.

## Failure Modes

The implementations cover several failure conditions.

### Invalid account data

An empty account number or negative opening balance is rejected.

### Duplicate identifiers

Primary-key and unique constraints prevent duplicate records.

### Invalid transactions

A transaction with a zero or negative amount violates the database rule.

### Insufficient funds

The transaction trigger rejects a debit when the account does not contain enough money.

### Excessive balance changes

The account validation trigger rejects unusually large direct balance changes.

### Missing relationships

Foreign keys prevent transactions from referencing nonexistent accounts.

### Invalid transfers

The procedure rejects self-transfers, non-positive amounts, missing accounts, inactive accounts, and insufficient funds.

## Performance Considerations

Triggers execute as part of data modification, so their cost contributes directly to the latency of the originating statement.

The transaction-to-account lookup is supported by the primary key on `accounts.account_id`.

The transaction reporting path is supported by:

`idx_transactions_account_created`

This index helps queries filtering by account and ordering by transaction time.

The audit history uses:

`idx_audit_account_changed`

This supports account-specific audit-history retrieval ordered by change time.

Indexes should be created for actual access patterns rather than added indiscriminately. Every additional index increases storage requirements and write overhead.

For very large transaction or audit tables, partitioning and retention strategies may become necessary.

## Security Considerations

Database automation executes with database privileges and can therefore affect data independently of application-layer assumptions.

Important controls include:

- restrict direct writes to sensitive tables
- grant execution rights only to appropriate procedure callers
- use parameterized procedure interfaces
- validate authorization separately from validation of data correctness
- protect audit records from unauthorized modification
- avoid dynamic SQL unless necessary
- use `SECURITY DEFINER` only when its privilege boundary is deliberately designed
- control ownership of functions and procedures
- review trigger behavior when privileges change

Validation is not the same as authorization.

A trigger can determine that a value is invalid, but it should not automatically be treated as a complete authorization system.

## Maintainability and Debugging

Stored procedures centralize explicit business operations.

Triggers centralize automatic reactions.

The combination is powerful but can hide execution paths from application developers.

Debugging should therefore inspect:

- the original SQL statement
- invoked procedures
- trigger definitions
- trigger timing
- affected rows
- transaction boundaries
- exceptions
- audit records
- lock behavior

The PostgreSQL implementation uses clear function and trigger names so the execution path can be traced from the database catalog and source.

A practical design rule is to keep triggers small and deterministic while placing larger multi-step business workflows in procedures.

## Design Boundaries

The four major responsibilities in this implementation are deliberately distinct:

| Responsibility | Preferred mechanism |
|---|---|
| Simple data invariant | Constraint |
| Explicit multi-step business operation | Procedure |
| Automatic reaction to row changes | Trigger |
| Reusable query or calculation | Function |

A common design mistake is placing every business rule inside triggers.

That can produce unexpected side effects and make application behavior difficult to predict.

Another mistake is placing every automatic invariant in application code.

That allows other clients, scripts, administrative sessions, or future services to bypass the rule.

The database should own rules that must remain true regardless of which client modifies the data.

## Educational Workflow

The implementations progress from explicit procedural behavior to automatic database reactions.

The Python model makes the mechanics easy to inspect.

The JavaScript model emphasizes event-driven execution.

The C++ model emphasizes strongly typed domain state and deterministic resource ownership.

The Java model emphasizes domain interfaces, immutable records, and service boundaries.

The PostgreSQL script demonstrates the actual database mechanisms: `CREATE PROCEDURE`, `CREATE FUNCTION`, trigger functions, `BEFORE` triggers, `AFTER` triggers, constraints, row locking, transactions, views, indexes, and relational integrity.

Together, the implementations demonstrate why stored procedures and triggers are complementary rather than interchangeable mechanisms.
