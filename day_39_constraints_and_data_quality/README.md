# Constraints and Data Quality: CHECK, NOT NULL, UNIQUE, and Business Rules

## Technical scope

Reliable relational data depends on more than whether an application accepts an input. A value can have the correct data type but still be incomplete, duplicated, outside an allowed range, or inconsistent with another record.

This project examines four complementary mechanisms:

- `NOT NULL` requires a value to be present.
- `UNIQUE` prevents duplicate values within a defined key.
- `CHECK` evaluates a Boolean condition for each inserted or updated row.
- Business rules define acceptable states and relationships according to the organization's operational requirements.

These mechanisms solve different problems. A non-null salary may still be negative. A unique email column may still accept multiple null values under common SQL uniqueness semantics. A valid department name in an application does not establish that the department exists in the database.

The implementations use employee onboarding as a realistic domain. Employee codes and email addresses act as identifiers, salaries are nonnegative monetary values, ages are restricted to an allowed range, and each employee must reference an existing department.

## Terminology and enforcement boundaries

### Completeness with NOT NULL

A mandatory attribute must not be absent. The SQL schema applies `NOT NULL` to employee codes, email addresses, names, ages, salaries, department references, and creation timestamps.

`NOT NULL` is not equivalent to a non-empty-string rule. In PostgreSQL, an empty string is a value rather than `NULL`. A mandatory textual field often needs both `NOT NULL` and a `CHECK` expression such as `length(btrim(full_name)) > 0`.

A default value also does not make a column mandatory. A default supplies a value when an insert omits the column, but a caller may still explicitly supply `NULL` unless the column is declared `NOT NULL`.

### Uniqueness with UNIQUE

`UNIQUE` establishes that two rows cannot share the same key value under the constraint's comparison semantics. It is appropriate for employee codes, department codes, and other identifiers that must identify a single record.

Normalization matters. If `ALICE@example.com` and `alice@example.com` represent the same logical address, a case-sensitive uniqueness check may not implement the intended business rule. The Python, JavaScript, C++, and Java implementations normalize email addresses before checking them. The PostgreSQL implementation also creates a unique expression index on `lower(btrim(email))`, making case and surrounding whitespace differences subject to database-level enforcement.

A unique constraint is not a substitute for `NOT NULL`. PostgreSQL's ordinary unique constraints allow multiple null values by default. A mandatory unique identifier therefore normally requires both declarations.

### Validity with CHECK

A `CHECK` constraint restricts the values a row can contain. The employee schema uses it to enforce age ranges, nonnegative salaries, valid Boolean states, and nonblank identifiers.

A check expression generally passes when it evaluates to `TRUE` or `UNKNOWN`; only `FALSE` rejects the row. Because comparisons with `NULL` usually evaluate to `UNKNOWN`, a condition such as `salary >= 0` does not replace `salary NOT NULL`.

Checks are strongest for row-local conditions. Rules involving other rows, such as uniqueness across records, belong in unique constraints or unique indexes. Rules involving referenced entities are usually represented by foreign keys.

### Business rules and relational integrity

Business rules specify which states are meaningful for a particular organization. Examples include a permitted age range, a salary precision policy, and the requirement that an employee belong to a registered department.

The implementations distinguish between format validation and authoritative persistence. Application validation can return a useful message before a database request. Database constraints remain necessary because records may also arrive through imports, administrative scripts, background jobs, or concurrent application requests.

A foreign key ensures that a referenced department exists. It does not automatically ensure that the department is active. If active-department membership must remain valid throughout an employee's lifetime, that additional policy needs an explicit design, such as a controlled department-status transition, a trigger, or a transactional service operation.

## Data-quality lifecycle

The examples use a validation pipeline that separates raw input from accepted records.

Raw employee records are normalized and checked for required values, format, numeric precision, and permitted ranges. Identifiers are converted to canonical forms before uniqueness checks. Department references are then verified against the known department set. Only after these checks succeed is the record added to the in-memory registry or written to the database.

For imports, rejected records are retained in a staging workflow with a reason describing the failed rule. This allows operators to distinguish malformed input from duplicate identifiers and missing department references. A quality report aggregates accepted records and validation failures.

Application checks and database constraints have different roles. Application checks provide early feedback and improve usability. Database constraints protect stored data regardless of which client submits the write. Both are needed for a dependable system.

## Python implementation

The Python script uses the standard-library `sqlite3` module to create a relational model with departments, employees, and a quality audit table.

The `Employee` dataclass defines the incoming domain record. `validate_employee` normalizes identifiers and applies business rules before persistence. `parse_salary` uses `Decimal` so monetary values are not initially represented as binary floating-point values.

The database schema separately enforces `NOT NULL`, `UNIQUE`, `CHECK`, and foreign-key requirements. This separation is important because an application-level validator can be bypassed by direct SQL.

`try_insert_invalid` records rejected attempts in an audit table without leaving an invalid employee record behind. The transaction demonstration inserts a record and then deliberately attempts a duplicate identifier. The resulting integrity error causes the transaction to roll back, illustrating the atomicity of a grouped database operation.

The script also demonstrates that SQLite permits multiple null values in a unique column. The temporary table isolates this behavior so it can be observed without changing the employee schema.

The query-plan demonstration shows how a composite index on department and active status can support a common filtering pattern. Actual index usage depends on table size, data distribution, and the database query planner.

SQLite-specific considerations include enabling foreign-key enforcement on each connection and recognizing that its type affinity rules differ from PostgreSQL's stricter typing. The schema is designed for demonstration rather than as a complete enterprise identity or payroll system.

## JavaScript implementation

The JavaScript file models a data-quality service in Node.js using private class fields, immutable employee records, maps, sets, and an event emitter.

`validateEmployee` normalizes employee codes and emails, checks the age range, and converts salary into integer cents. Integer minor currency units avoid many floating-point accumulation errors when the system needs exact cent-level amounts.

`EmployeeRegistry` maintains separate maps for employee IDs, employee codes, and normalized email addresses. These indexes make identifier lookups and uniqueness checks efficient on average. The implementation completes validation before mutating the maps, avoiding a partially inserted record when a rule fails.

`QualityEventBus` emits structured failure events with a rule identifier, timestamp, and relevant context. Event-driven reporting separates the detection of a quality failure from its presentation. The sample keeps these events in memory; a production service would need durable logging and appropriate controls over sensitive employee information.

`ImportService` accepts or rejects each record independently. This is a deliberate partial-import policy, not an all-or-nothing transaction. A persistent implementation that requires batch atomicity should use a database transaction or a staging-table workflow.

The email expression checks a basic business format rather than implementing every permitted email-address syntax. Production systems should distinguish syntax validation from proof that an address belongs to a person.

## C++ case study

The C++ program models an employee onboarding engine using a validation result, explicit issue records, ordered employee storage, and hash-based identifier indexes.

`validateInput` returns a `ValidationResult` containing either a valid employee or a collection of rule violations. Collecting several independent errors at once gives import operators more useful feedback than stopping at the first malformed field.

The engine canonicalizes employee codes and emails before testing uniqueness. Department membership is checked against a known set. The accepted employee is inserted only after all these checks succeed.

Salary is stored in integer cents. The parser rejects negative values, excess fractional precision, malformed input, and values that exceed the supported integer range. The program therefore avoids using a binary floating-point value as the authoritative salary representation.

The ordered map stores employees by numeric identifier, while unordered maps index employee codes and email addresses. These structures support direct identifier lookup with average constant-time hash-map access and deterministic iteration through the employee collection.

The program includes duplicate codes, duplicate email addresses, an invalid age, an unknown department, a negative salary, and excessive decimal precision. These examples exercise different rules rather than treating every rejection as the same error.

The engine is intentionally single-threaded. Its check-then-insert sequence is not safe against concurrent writers without synchronization. A multi-process deployment would also require a shared persistence layer with database-enforced uniqueness. The implementation demonstrates domain validation, not a replacement for transactional database integrity.

## Java implementation

The Java program represents the same general domain through records, enums, immutable employee values, and a repository-oriented service design.

`EmployeeCommand` represents incoming data, while `Employee` represents a validated record with an assigned identifier and creation timestamp. Keeping command and stored-record types separate prevents incoming data from directly controlling persistence metadata.

`QualityRule` enumerates recognized validation failures. `QualityViolation` records the rule, severity, field, timestamp, and relevant employee code. `DataQualityException` carries a rule identifier and field so a caller can respond to a failure without parsing a free-form message.

`EmployeeRepository` maintains indexes for employee codes and normalized email addresses. It also verifies that a department has been registered before accepting a new employee. `OnboardingService` processes a batch and records rejected attempts through the repository's violation collection.

The salary update creates a replacement immutable employee record rather than exposing a mutable object that other code can modify without validation. `BigDecimal` with explicit scale rules provides predictable monetary precision.

The example repository is in memory, so it does not provide database transaction isolation or cross-process consistency. In a production enterprise application, the same domain rules would be complemented by database constraints and transactional repository methods. In particular, uniqueness must not depend only on checking a map before insertion when concurrent requests are possible.

## PostgreSQL relational model

The SQL script defines an isolated `data_quality_demo` schema containing departments, employees, quality rules, audit records, and import staging rows.

The `department` table gives each department a primary key and unique business identifiers. Its budget is mandatory and nonnegative.

The `employee` table uses a generated primary key, mandatory identifiers, a unique employee code, a unique email address, and a foreign key to the department table. Its age, salary, textual fields, and other row-local properties are protected by check constraints.

A case-insensitive expression index on `lower(btrim(email))` closes a gap that a conventional case-sensitive unique constraint would leave open. The application should normalize values consistently as well, but the index is the final authority for this particular uniqueness rule.

The staging table accepts raw textual values for fields that may be malformed in an import. The `employee_staging_quality` view classifies records before they are promoted to the production table. Numeric casts are guarded by format checks so ordinary malformed text does not cause the diagnostic query to fail prematurely.

The import transaction inserts valid staged records, updates staging outcomes, and writes rejected records to the quality audit table. `ON CONFLICT DO NOTHING` is a final safeguard against conflicts that may arise between an earlier validation query and the actual insert. Production workflows should still report skipped conflicts explicitly rather than silently treating them as accepted records.

The script uses foreign keys, check constraints, unique constraints, expression indexes, an operational quality view, aggregate queries, and an `EXPLAIN` query. It also includes exception-handled demonstrations of `NOT NULL`, `CHECK`, and case-insensitive uniqueness failures.

The audit table references a catalog of quality rules. This relationship prevents audit records from referring to unknown rule identifiers, making quality failures easier to classify and aggregate.

## Distinguishing the four mechanisms

| Mechanism | Primary responsibility | Example | What it does not guarantee |
|---|---|---|---|
| `NOT NULL` | Completeness | An employee must have a name. | A nonblank or meaningful name. |
| `UNIQUE` | Key uniqueness | No two employees share an employee code. | Valid syntax or ownership of the identifier. |
| `CHECK` | Row-local validity | Age must be between 18 and 100. | Uniqueness across rows or existence of a referenced department. |
| Business rule | Domain correctness | Employees must belong to an eligible department. | Automatic database enforcement unless implemented through suitable constraints or controlled operations. |

A reliable design combines these mechanisms rather than expecting one to replace another. For example, a mandatory employee email needs `NOT NULL`, a uniqueness rule, an accepted format, and a consistent normalization policy.

## Edge cases and common failures

**NULL and empty strings:** A null value is different from an empty string or a string containing only whitespace. Mandatory textual attributes often require both a presence constraint and a nonblank check.

**Case and whitespace differences:** Unique values should be compared according to the intended business meaning. Email addresses may need case normalization and surrounding-whitespace removal before uniqueness is evaluated.

**Precision and rounding:** Money should use a decimal representation or integer minor units. A policy must state whether excess fractional digits are rejected or rounded. The examples reject excess precision rather than silently changing the supplied value.

**Concurrent inserts:** Two application requests can both observe that an identifier is unused and then attempt to insert it. A database unique constraint prevents both from successfully claiming the same key. Application-level uniqueness checks improve error messages but cannot replace this guarantee.

**Cross-row business rules:** A `CHECK` constraint is not a general substitute for foreign keys, unique indexes, triggers, or transactional service logic. Rules that depend on other rows need an enforcement mechanism appropriate to their scope.

**Failed batch imports:** Partial acceptance and all-or-nothing acceptance are different policies. Partial imports preserve valid records while rejecting individual failures. Atomic imports require staging and transaction boundaries that prevent incomplete batches from becoming visible as successful operations.

**Audit-data sensitivity:** Quality logs should capture enough context to diagnose a failure without unnecessarily retaining personal or confidential information. Access control and retention requirements apply to audit records as well as production data.

## Performance and operational considerations

Unique constraints and indexes add write overhead because inserts and updates must maintain index entries. Their value is strongest when they protect important invariants or support frequent query patterns.

The employee department index supports queries that filter by department and active status. The audit index supports investigations that filter by rule and sort by detection time. Indexes should be selected according to actual access patterns rather than added to every column.

Quality reports should track both rule-level failures and business-level outcomes. A rising duplicate-email rejection rate may indicate a source-system integration problem. An increase in missing department references may indicate stale reference data. These trends can help distinguish isolated bad records from recurring process failures.

Database constraints protect persisted invariants, application validation provides useful feedback, staging workflows make imports inspectable, and quality metrics reveal recurring defects. Together, these mechanisms establish a practical data-quality architecture in which invalid records are rejected, failures are explainable, and accepted data remains consistent across multiple entry points.
