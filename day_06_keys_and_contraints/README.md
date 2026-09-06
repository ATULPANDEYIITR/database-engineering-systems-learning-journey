# Keys and Constraints in Relational Databases

## Topic

This study document accompanies the Python script on relational database keys and constraints. It progresses from the basic relational model to advanced schema-design considerations using executable SQLite examples through Python's standard-library `sqlite3` module.

The central distinction is:

- **Keys** describe how rows are identified and how relationships can be represented.
- **Constraints** define rules that restrict the states the database is allowed to contain.

A well-designed relational schema uses both to make important data-integrity rules explicit and enforceable.

---

## 1. Relational Database Foundations

A relational database organizes data into relations, commonly represented as tables.

A table consists conceptually of:

- **Rows**, also called tuples or records, representing individual instances.
- **Columns**, also called attributes, representing properties.
- **Schema**, describing the table structure, relationships, data types, and integrity rules.

For example, a `Student` relation might contain:

- `student_id`
- `email`
- `full_name`

Without constraints, the database may accept duplicate identifiers, missing values, or invalid relationships. Keys and constraints provide the formal mechanisms for preventing such invalid states.

---

# 2. Keys

A **key** is a set of one or more attributes used to identify rows or establish relationships.

Important key classifications include:

1. Super key
2. Candidate key
3. Primary key
4. Alternate key
5. Composite key
6. Natural key
7. Surrogate key
8. Foreign key

These terms are related but are not interchangeable.

---

## 3. Super Key

A **super key** is any set of attributes that uniquely identifies a row.

Suppose `employee_id` uniquely identifies every employee.

Then all of the following can theoretically identify a row:

- `{employee_id}`
- `{employee_id, email}`
- `{employee_id, employee_name}`
- `{employee_id, email, employee_name}`

All are super keys because each contains an attribute that guarantees uniqueness.

The extra attributes are unnecessary for identification.

---

## 4. Candidate Key

A **candidate key** is a minimal super key.

Minimality means that no attribute can be removed while retaining uniqueness.

If `employee_id` alone is unique, then:

- `{employee_id}` is a candidate key.
- `{employee_id, email}` is only a super key.
- `{employee_id, email, employee_name}` is only a super key.

This distinction is important in relational theory.

A relation can have multiple candidate keys.

For example:

    Employee(employee_id, email, government_id, employee_name)

If all three of the following are guaranteed to be unique:

- `employee_id`
- `email`
- `government_id`

then each can be a candidate key.

---

# 5. Primary Key

A **primary key** is the candidate key selected as the principal identifier for rows in a table.

For example:

    employee_id INTEGER PRIMARY KEY

The primary key provides an identity mechanism for the entity represented by the table.

A primary key has these important characteristics:

- It uniquely identifies rows.
- It cannot contain NULL.
- There is one primary-key definition per table.
- It can consist of multiple columns.
- It is commonly referenced by foreign keys.

The statement that a table has "one primary key" does not mean that the primary key must contain one column.

A table may have:

    PRIMARY KEY (student_id, course_id)

This is a **composite primary key**.

---

# 6. Primary Key Versus Candidate Key

Candidate keys represent all minimal possible identifiers.

The primary key is the candidate key selected for principal use.

For example:

    Employee
    -----------------------------
    employee_id
    email
    government_id
    employee_name

If all of these are unique identifiers:

- `employee_id` can be a candidate key.
- `email` can be a candidate key.
- `government_id` can be a candidate key.

If `employee_id` is selected as the primary key:

- `employee_id` becomes the primary key.
- `email` becomes an alternate key.
- `government_id` becomes an alternate key.

The database schema commonly expresses the primary key with `PRIMARY KEY` and alternate uniqueness with `UNIQUE`.

---

# 7. Alternate Key

An **alternate key** is a candidate key that was not selected as the primary key.

For example:

    employee_id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    government_id TEXT NOT NULL UNIQUE

Here:

- `employee_id` is the primary key.
- `email` can represent an alternate candidate key.
- `government_id` can represent another alternate candidate key.

The relational concept of candidate keys should not be confused with the SQL syntax used to enforce them.

---

# 8. UNIQUE Constraints

A `UNIQUE` constraint prevents duplicate values according to the database's uniqueness rules.

Example:

    email TEXT UNIQUE

This ensures that non-NULL email values cannot be duplicated.

Multiple UNIQUE constraints can exist in the same table.

For example:

    CREATE TABLE employees (
        employee_id INTEGER PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        employee_code TEXT NOT NULL UNIQUE
    );

Here:

- `employee_id` identifies the row.
- `email` is unique.
- `employee_code` is unique.

The schema therefore protects several distinct identity-related properties.

---

# 9. PRIMARY KEY Versus UNIQUE

| Property | PRIMARY KEY | UNIQUE |
|---|---|---|
| Main row identifier | Yes | Not necessarily |
| Multiple definitions allowed | No | Yes |
| NULL allowed | No | DBMS-dependent; SQLite permits multiple NULLs |
| Can be composite | Yes | Yes |
| Can enforce alternate candidate key | Yes | Yes |
| Common foreign-key target | Yes | Yes, when valid under DBMS rules |

A common design is:

    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE

This separates internal row identity from business-level uniqueness.

---

# 10. NULL and UNIQUE

One of the most important edge cases is the interaction between `NULL` and `UNIQUE`.

In SQLite:

    email TEXT UNIQUE

can contain multiple NULL values.

For example:

    NULL
    NULL
    person@example.com

The two NULL values do not violate the UNIQUE constraint.

This happens because SQL's treatment of NULL differs from ordinary equality.

If the business rule is:

> Every row must have an email and no two rows may have the same email.

the schema should be:

    email TEXT NOT NULL UNIQUE

`UNIQUE` alone does not express the requirement that the value must exist.

---

# 11. NULL Is Not an Empty String

These values are different:

    NULL
    ''

`NULL` represents the absence or unknown nature of a value.

An empty string is an actual string value containing zero characters.

Therefore:

    name TEXT NOT NULL

rejects:

    NULL

but does not necessarily reject:

    ''

If empty strings are also forbidden, a separate rule may be needed, such as a suitable `CHECK` condition.

---

# 12. Composite Keys

A **composite key** contains multiple attributes.

Consider student enrollment:

    Enrollment(student_id, course_id)

A student can take multiple courses.

A course can contain multiple students.

But the same student should generally not be enrolled in the same course more than once.

Therefore:

    PRIMARY KEY (student_id, course_id)

is appropriate.

The combination is unique even though:

- `student_id` repeats across courses.
- `course_id` repeats across students.

---

# 13. Composite UNIQUE Constraints

A composite UNIQUE constraint applies to a combination of columns.

Example:

    UNIQUE (building_id, room_number)

This allows:

    building 1, room 101
    building 1, room 102
    building 2, room 101

but rejects another:

    building 1, room 101

The constraint does not make `building_id` globally unique.

It does not make `room_number` globally unique.

It makes the **combination** unique.

---

# 14. Composite Primary Key Versus Composite UNIQUE

A composite primary key:

    PRIMARY KEY (student_id, course_id)

makes the combination the table's principal identifier.

A composite UNIQUE constraint:

    UNIQUE (department_id, project_code)

requires the combination to be unique but does not make it the table's primary identity.

A table may contain one primary-key definition and several UNIQUE constraints.

---

# 15. Natural Keys

A **natural key** is based on meaningful real-world or business data.

Examples can include:

- ISO country codes
- ISBN values
- formally defined business codes
- certain government or organizational identifiers

Natural keys can be useful because they already exist in the domain.

They can also create difficulties when:

- the value changes,
- the value is long,
- the value exposes business information,
- the value is not actually guaranteed to remain unique,
- the key is composite.

Natural-key suitability depends on the stability and semantics of the domain.

---

# 16. Surrogate Keys

A **surrogate key** is an artificial identifier introduced primarily to identify a database row.

Examples include:

- generated integers,
- identity values,
- UUIDs.

A common design is:

    customer_id INTEGER PRIMARY KEY,
    customer_code TEXT NOT NULL UNIQUE

The surrogate key provides stable internal identity.

The UNIQUE constraint separately protects the business identifier.

A surrogate key does **not** automatically make business attributes unique.

---

# 17. Natural Keys Versus Surrogate Keys

| Characteristic | Natural Key | Surrogate Key |
|---|---|---|
| Derived from business data | Yes | No |
| Artificial identifier | No | Yes |
| Can change with business rules | Potentially | Usually designed to remain stable |
| May expose business meaning | Yes | Usually less meaningful |
| Often compact | Not necessarily | Often |
| Requires separate business uniqueness | Depends | Usually yes |
| Suitable for relationships | Sometimes | Often convenient |

Neither strategy is universally correct.

The appropriate choice depends on stability, semantics, size, generation requirements, and application architecture.

---

# 18. Foreign Keys

A **foreign key** represents a relationship between rows in different tables, or sometimes within the same table.

Example:

    departments
        department_id PRIMARY KEY

    employees
        department_id
        REFERENCES departments(department_id)

The parent table contains the referenced key.

The child table contains the foreign key.

Terminology:

- **Parent table**: referenced table.
- **Child table**: table containing the reference.
- **Referenced key**: parent-side key.
- **Referencing key**: child-side foreign key.

---

# 19. Referential Integrity

A foreign key protects **referential integrity**.

Suppose:

    department_id = 10

appears in `employees`.

The database should ensure that department 10 exists in the parent table, unless the foreign key is NULL and the relationship is optional.

A value such as:

    department_id = 999

should be rejected if department 999 does not exist.

This prevents orphaned references.

---

# 20. Foreign Key and NOT NULL

A foreign key can be nullable.

Example:

    department_id INTEGER
        REFERENCES departments(department_id)

This allows:

    department_id = NULL

If the relationship is mandatory, use:

    department_id INTEGER NOT NULL
        REFERENCES departments(department_id)

The distinction is:

- `NULL`: no department reference is currently represented.
- `999`: an explicit reference to department 999, which must exist.

A foreign key does not inherently imply `NOT NULL`.

---

# 21. Foreign Key Referencing a UNIQUE Key

Foreign keys commonly reference primary keys, but they may also reference appropriate unique candidate or alternate keys.

For example:

    department_code TEXT NOT NULL UNIQUE

can be referenced by:

    FOREIGN KEY (department_code)
        REFERENCES departments(department_code)

This is useful when a stable business identifier is intentionally part of the relationship.

The exact requirements for referenced keys vary among DBMS implementations.

---

# 22. Foreign Key Actions

When a referenced parent row is updated or deleted, the database needs a policy for dependent child rows.

Common referential actions include:

- `CASCADE`
- `RESTRICT`
- `NO ACTION`
- `SET NULL`
- `SET DEFAULT`

These actions are part of referential-integrity design.

---

# 23. ON DELETE CASCADE

Example:

    FOREIGN KEY (order_id)
        REFERENCES orders(order_id)
        ON DELETE CASCADE

If an order is deleted, its dependent order items are deleted automatically.

This is appropriate when the child has no independent lifecycle.

Typical examples include:

- order and order items,
- project and project membership records,
- post and comments.

Cascade deletion should be used deliberately because one deletion can remove a large amount of dependent data.

---

# 24. ON DELETE SET NULL

Example:

    manager_id INTEGER
        REFERENCES employees(employee_id)
        ON DELETE SET NULL

If the referenced employee is removed, dependent `manager_id` values become NULL.

This is appropriate when the child row should remain but its relationship should be removed.

The child column must permit NULL.

---

# 25. RESTRICT and NO ACTION

Restrictive behavior prevents a parent modification when dependent rows would be left invalid.

This is useful when deleting the parent would violate a business rule.

For example:

    customer -> invoices

A system may want to prevent deletion of a customer while invoices remain.

The exact timing and semantics of `RESTRICT` and `NO ACTION` can differ between database engines.

---

# 26. ON UPDATE CASCADE

`ON UPDATE CASCADE` propagates a changed referenced key to child rows.

Example:

    countries.country_code
    offices.country_code

If the country code changes and the relationship uses:

    ON UPDATE CASCADE

the child references can be updated automatically.

This is more useful when referenced business keys are mutable.

With stable surrogate primary keys, primary-key updates are usually avoided.

---

# 27. Self-Referencing Foreign Keys

A foreign key can reference the same table.

Example:

    CREATE TABLE employees (
        employee_id INTEGER PRIMARY KEY,
        manager_id INTEGER,
        FOREIGN KEY (manager_id)
            REFERENCES employees(employee_id)
    );

This represents an organizational hierarchy.

The root employee may have:

    manager_id = NULL

while subordinate employees reference another employee.

Self-referencing relationships are useful for:

- organizational structures,
- category hierarchies,
- threaded comments,
- folder trees,
- bill-of-material structures.

---

# 28. Many-to-Many Relationships

Relational databases commonly model many-to-many relationships with a junction table.

Instead of directly representing:

    students <-> courses

use:

    students
    courses
    enrollments

The enrollment table can contain:

    student_id
    course_id

and:

    PRIMARY KEY (student_id, course_id)

with two foreign keys.

This provides:

- uniqueness of each relationship,
- referential integrity,
- a natural place for relationship attributes such as enrollment date or grade.

---

# 29. NOT NULL

`NOT NULL` requires a value to be present.

Example:

    name TEXT NOT NULL

A NULL insertion is rejected.

`NOT NULL` is useful for mandatory attributes such as:

- employee name,
- email,
- product price,
- status,
- foreign keys representing mandatory relationships.

It does not mean that every possible form of "empty" data is rejected.

For example, an empty string is not NULL.

---

# 30. CHECK Constraints

A `CHECK` constraint limits values according to a Boolean condition.

Examples:

    age INTEGER CHECK (age >= 0)

    price NUMERIC CHECK (price >= 0)

    status TEXT CHECK (
        status IN ('ACTIVE', 'BLOCKED')
    )

`CHECK` is particularly useful for row-level domain rules.

It can express:

- ranges,
- allowed states,
- simple relationships between columns,
- non-negative values,
- valid combinations of local attributes.

---

# 31. CHECK Is Not a Replacement for Foreign Keys

Suppose an employee must belong to an existing department.

A CHECK expression should not be used as the normal mechanism for checking whether another table contains a matching row.

That is a relational relationship and should be modeled with:

    FOREIGN KEY (department_id)
        REFERENCES departments(department_id)

The mechanisms have different purposes:

- `CHECK`: local value/domain validation.
- `FOREIGN KEY`: cross-table referential integrity.

---

# 32. DEFAULT

A `DEFAULT` value is supplied when an INSERT omits a column.

Example:

    status TEXT NOT NULL DEFAULT 'ACTIVE'

If status is omitted, the database can insert `ACTIVE`.

A DEFAULT is not the same as NOT NULL.

If a caller explicitly supplies NULL to a NOT NULL column, the NOT NULL constraint still applies.

DEFAULT also does not normally prevent explicitly supplied alternative values.

Therefore:

    DEFAULT

answers:

> What value should be supplied when the column is omitted?

while:

    NOT NULL

answers:

> Is NULL permitted?

---

# 33. Combining Constraints

Real schemas commonly combine several constraints.

For example:

    user_id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    age INTEGER NOT NULL CHECK (age >= 18),
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'BLOCKED')),
    department_id INTEGER
        REFERENCES departments(department_id)

Each rule has a distinct purpose:

| Constraint | Purpose |
|---|---|
| PRIMARY KEY | Identity |
| UNIQUE | Prevent duplicate values |
| NOT NULL | Require a value |
| CHECK | Restrict the domain |
| DEFAULT | Supply omitted values |
| FOREIGN KEY | Protect relationships |

Strong schema design usually combines constraints rather than trying to make one rule perform unrelated functions.

---

# 34. Entity Integrity

**Entity integrity** concerns the reliable identification of rows.

The primary key is the classic SQL mechanism for entity integrity.

A table representing employees should not contain two indistinguishable rows with the same primary identity.

The primary key therefore provides the foundation for identifying individual entities.

---

# 35. Referential Integrity

**Referential integrity** ensures that relationships between tables remain valid.

Example:

    employee.department_id
        ->
    department.department_id

A foreign-key constraint prevents an employee from referring to a nonexistent department.

Referential integrity is essential for relational consistency.

---

# 36. Domain Integrity

**Domain integrity** concerns the values that attributes are allowed to contain.

Typical mechanisms include:

- data types,
- NOT NULL,
- CHECK,
- DEFAULT,
- UNIQUE in appropriate cases.

For example:

    salary NUMERIC NOT NULL CHECK (salary >= 0)

captures multiple domain requirements:

1. Salary must exist.
2. Salary cannot be negative.

---

# 37. Business Integrity

Business integrity refers to organization-specific rules.

Examples:

- Every employee must have an organization.
- A room number must be unique within a building.
- A product price cannot be negative.
- An account can have only defined statuses.
- A project code must be unique within an organization.

Some business rules map directly to SQL constraints.

Other rules may require:

- transactions,
- triggers,
- application-level logic,
- locking,
- specialized database features.

The more critical the invariant, the stronger the case for enforcing it at the database layer when practical.

---

# 38. Constraints Apply to UPDATE

Constraints do not apply only to INSERT.

An UPDATE can violate:

- primary keys,
- UNIQUE constraints,
- NOT NULL,
- CHECK,
- foreign keys.

For example:

    UPDATE products
    SET price = -50;

can violate:

    CHECK (price >= 0)

Similarly:

    UPDATE employees
    SET department_id = 999;

can violate a foreign key.

Schema testing must therefore cover INSERT, UPDATE, and DELETE.

---

# 39. Constraints and DELETE

Deleting parent records can affect referential integrity.

Suppose:

    departments
        department_id = 10

and:

    employees
        department_id = 10

Deleting department 10 may:

- fail,
- delete employees,
- set employee department references to NULL,
- use another configured referential action.

The correct choice depends on business meaning.

---

# 40. Transactions and Constraints

Constraints are particularly powerful when combined with transactions.

A transaction groups multiple database operations into one logical unit.

For example:

1. Begin transaction.
2. Update account A.
3. Update account B.
4. Perform validation.
5. Commit if everything is valid.
6. Roll back if an integrity rule fails.

If one operation violates a constraint and the transaction is rolled back, earlier operations can be undone as part of restoring the previous consistent state.

Transactions are therefore an important part of maintaining multi-step integrity.

---

# 41. Constraint Timing

Some database systems support **deferrable constraints**.

A deferrable constraint can sometimes be checked at transaction commit instead of immediately after a statement.

Concepts include:

- `DEFERRABLE`
- `INITIALLY DEFERRED`
- `INITIALLY IMMEDIATE`

This can be useful when a sequence of changes temporarily creates an intermediate state that would violate a constraint even though the final transaction state is valid.

Support and semantics differ significantly among database engines.

---

# 42. Conditional Uniqueness

Some business rules require uniqueness only for certain rows.

For example:

> Active usernames must be unique, but inactive accounts may reuse an old username.

A normal UNIQUE constraint would not directly express this rule.

SQLite supports partial indexes, allowing a design such as:

    CREATE UNIQUE INDEX uq_active_username
    ON accounts(username)
    WHERE active = 1;

This is an advanced schema-design pattern.

Other database systems may call equivalent features filtered indexes or partial indexes.

---

# 43. Keys and Normalization

Keys are fundamental to relational normalization.

Functional dependency is often written:

    X -> Y

This means that the value of X determines the value of Y.

For example:

    employee_id -> employee_name, email, department_id

if `employee_id` is a candidate key.

Candidate keys are important when analyzing:

- functional dependencies,
- partial dependencies,
- transitive dependencies,
- normal forms.

Normalization uses these concepts to reduce redundancy and update anomalies.

Constraints then make parts of the intended logical model enforceable in the actual database.

---

# 44. Key Selection Criteria

When selecting a primary key, consider:

### Stability

Will the identifier change?

Stable identifiers reduce the need to update references.

### Uniqueness

Is uniqueness guaranteed by the domain?

### Nullability

Can the value ever be absent?

A primary key cannot depend on an optional attribute.

### Width

Large keys can increase index and foreign-key storage requirements.

### Meaning

Does the identifier expose business information?

### Generation

Can it be generated reliably?

### Distribution

In distributed systems, identifier generation may require additional considerations such as coordination, collision avoidance, or ordering.

There is no universal rule that every schema should use either natural keys or surrogate keys.

---

# 45. Foreign Keys and Indexing

Foreign-key columns often participate in:

- joins,
- filtering,
- parent-row deletion,
- parent-row updates.

An index on a foreign-key column can therefore be valuable in production workloads.

For example:

    CREATE INDEX idx_orders_customer_id
    ON orders(customer_id);

The exact indexing strategy should be based on query workload and database behavior.

Indexes provide benefits but also have costs:

- storage,
- INSERT overhead,
- UPDATE overhead,
- DELETE overhead,
- maintenance complexity.

A schema should not automatically index every column.

---

# 46. Primary Keys, UNIQUE Constraints, and Indexes

Primary keys and UNIQUE constraints commonly require internal index structures or equivalent mechanisms to efficiently enforce uniqueness.

Indexes can make uniqueness checking efficient, but their existence should not be confused with the logical constraint itself.

For example:

    UNIQUE (email)

expresses a logical integrity rule.

The database may implement the rule using an index.

The logical schema and physical implementation are related but conceptually distinct.

---

# 47. Foreign-Key Indexing

A foreign-key constraint and an index on the foreign-key column are different things.

For example:

    FOREIGN KEY (department_id)
        REFERENCES departments(department_id)

protects referential integrity.

An index:

    CREATE INDEX idx_employee_department
    ON employees(department_id);

supports efficient access.

A foreign key does not universally guarantee that an index will be created on the child column automatically.

DBMS behavior varies, so production schema designers should inspect the actual indexes.

---

# 48. SQLite Foreign-Key Enforcement

The Python script uses:

    PRAGMA foreign_keys = ON

SQLite requires foreign-key enforcement to be enabled for the connection.

This is an important DBMS-specific detail.

A schema may contain a foreign-key declaration without behaving as expected if enforcement is not enabled.

Production code using SQLite should deliberately configure foreign-key enforcement rather than assuming it is automatically active.

---

# 49. Schema Introspection

SQLite provides metadata commands such as:

    PRAGMA table_info(table_name)

    PRAGMA foreign_key_list(table_name)

    PRAGMA index_list(table_name)

    PRAGMA index_info(index_name)

These can help investigate:

- columns,
- primary-key metadata,
- foreign keys,
- indexes,
- schema implementation.

Schema introspection is useful when debugging migrations and verifying that the deployed schema matches the intended design.

---

# 50. Named Constraints

Many SQL systems allow constraints to be named.

For example:

    CONSTRAINT uq_customer_email
        UNIQUE (email)

and:

    CONSTRAINT fk_employee_department
        FOREIGN KEY (department_id)
        REFERENCES departments(department_id)

Meaningful names can improve:

- schema readability,
- migration management,
- diagnostics,
- database administration,
- documentation.

The exact ability to alter, drop, or rename constraints differs between DBMS implementations.

---

# 51. Constraint Interactions

A single column may participate in several rules.

Example:

    email TEXT NOT NULL UNIQUE

This combines:

- `NOT NULL`: email must exist.
- `UNIQUE`: duplicate non-NULL emails are prohibited.

Another example:

    department_id INTEGER NOT NULL
        REFERENCES departments(department_id)

combines:

- mandatory relationship,
- referential integrity.

A more complete design might include:

    salary NUMERIC NOT NULL CHECK (salary >= 0)

which combines:

- required value,
- valid numeric domain.

Constraints are therefore compositional.

---

# 52. Edge Cases

Important edge cases include:

### NULL

Especially relevant to:

- UNIQUE,
- foreign keys,
- CHECK expressions.

### Empty strings

An empty string is not NULL.

### Composite keys

The uniqueness rule applies to the combination.

### Parent deletion

The result depends on the foreign-key action.

### Parent-key updates

The result depends on update behavior.

### Self-referencing relationships

They can create hierarchical dependencies.

### Soft deletion

Conditional uniqueness may be needed.

### Mutable natural keys

Changing a natural key can affect many references.

### Multiple constraint violations

A single statement can potentially conflict with several rules. The exact error reported depends on the database engine and evaluation behavior.

### Boundary values

Test both allowed and forbidden boundaries.

For example:

    age = 18

and:

    age = 17

should be tested when the rule is:

    CHECK (age >= 18)

---

# 53. Common Mistakes

## Mistake 1: Assuming UNIQUE Means NOT NULL

Incorrect assumption:

    email TEXT UNIQUE

means every row must have an email.

Correct approach when required:

    email TEXT NOT NULL UNIQUE

---

## Mistake 2: Forgetting Foreign-Key Enforcement

With SQLite, explicitly enable:

    PRAGMA foreign_keys = ON

for the relevant connection.

---

## Mistake 3: Relying Entirely on Application Validation

Application validation is useful, but concurrent applications, scripts, migrations, and other clients can bypass it.

Important integrity rules should be enforced at the database level where practical.

---

## Mistake 4: Treating a Surrogate Key as Business Uniqueness

This:

    customer_id INTEGER PRIMARY KEY

does not mean:

    email

or:

    customer_code

is unique.

Business identifiers need their own constraints.

---

## Mistake 5: Making a Mandatory Foreign Key Nullable

If every employee must belong to a department, this is incomplete:

    department_id INTEGER
        REFERENCES departments(department_id)

Use:

    department_id INTEGER NOT NULL
        REFERENCES departments(department_id)

---

## Mistake 6: Using an Oversized Composite Primary Key Without Evaluation

Composite keys are appropriate when the combination naturally represents identity.

In other cases, a surrogate primary key plus carefully selected UNIQUE constraints may provide simpler relationships.

---

## Mistake 7: Using CASCADE Without Understanding Its Consequences

A cascading delete can remove many dependent rows.

It should reflect the actual lifecycle of the data.

---

## Mistake 8: Ignoring UPDATE Operations

Constraints can fail during updates even when all existing rows were originally valid.

---

# 54. Security Considerations

Keys and constraints contribute to secure and reliable data handling, but they are not an authorization system.

For example:

    FOREIGN KEY

ensures that a referenced object exists.

It does not mean that the current user is authorized to access that object.

Authorization belongs to access-control mechanisms.

Constraints can still contribute to security by preventing invalid states such as:

- duplicate security identifiers,
- invalid account states,
- missing required attributes,
- invalid relationships.

The Python examples also use parameterized SQL rather than constructing SQL commands through string concatenation.

Parameterized statements treat input as data and are an important defense against SQL injection.

---

# 55. Production Design Considerations

A production schema should consider more than merely whether a constraint can be written.

Important questions include:

- Is the identifier stable?
- Is business uniqueness explicitly enforced?
- Are required values marked NOT NULL?
- Are domain rules represented by CHECK constraints?
- Are relationships protected by foreign keys?
- Are nullable relationships intentional?
- Are cascade actions safe?
- Are important foreign-key columns indexed?
- Are transactions used correctly?
- Are schema migrations tested?
- Are database-specific behaviors documented?
- Are constraints covered by automated tests?
- Are identifiers exposing sensitive business information unnecessarily?

Database integrity is part of the application's architecture, not merely a collection of SQL syntax features.

---

# 56. Practical Business Rules and Their SQL Mechanisms

| Business Requirement | Typical Mechanism |
|---|---|
| Every row needs an identifier | PRIMARY KEY |
| Email must be unique | UNIQUE |
| Email is mandatory | NOT NULL |
| Price cannot be negative | CHECK |
| Status has a defined set of values | CHECK |
| Status defaults to ACTIVE | DEFAULT |
| Employee must reference an existing department | FOREIGN KEY |
| Child rows should disappear with parent | ON DELETE CASCADE |
| Child rows should remain but lose parent relationship | ON DELETE SET NULL |
| Parent deletion should be prohibited | RESTRICT / NO ACTION |
| Parent identifier changes should propagate | ON UPDATE CASCADE |
| Student-course relationship must be unique | Composite PRIMARY KEY |
| Project code unique within organization | Composite UNIQUE |
| Active usernames only must be unique | Partial/filtered unique index |

---

# 57. Production-Style Combined Schema

The script demonstrates a schema containing:

- organizations,
- users,
- projects,
- project memberships.

The design uses:

    PRIMARY KEY

for row identity.

It uses:

    UNIQUE

for organization codes and user emails.

It uses:

    NOT NULL

for mandatory attributes.

It uses:

    CHECK

for allowed statuses.

It uses:

    DEFAULT

for automatically assigned states.

It uses:

    FOREIGN KEY

for relationships.

It uses:

    ON DELETE CASCADE

where dependent project data follows the project lifecycle.

It uses:

    ON DELETE SET NULL

where employees can remain after their department relationship is removed.

It uses:

    PRIMARY KEY (project_id, user_id)

for unique project-membership combinations.

This demonstrates how multiple integrity mechanisms cooperate in a realistic relational design.

---

# 58. Constraint Testing

Database constraints should be tested systematically.

Important tests include:

### Primary key

Attempt duplicate identifiers.

### UNIQUE

Attempt duplicate business identifiers.

### NOT NULL

Attempt missing required values.

### CHECK

Test values immediately below, at, and above boundaries.

### Foreign key

Attempt references to nonexistent parent rows.

### DELETE

Test each configured referential action.

### UPDATE

Attempt changes that would violate uniqueness or relationships.

### Composite constraints

Test duplicate combinations while allowing valid combinations.

### NULL behavior

Explicitly test NULL values where they are allowed.

A database schema is part of the executable correctness boundary, so constraints deserve automated tests.

---

# 59. Constraint Decision Framework

When designing a schema, ask the following questions.

### Question 1

How is the row uniquely identified?

Use a primary key.

### Question 2

Are there additional candidate or business identifiers?

Use UNIQUE constraints.

### Question 3

Must the value always exist?

Use NOT NULL.

### Question 4

Are there allowed ranges or states?

Use CHECK.

### Question 5

Should an omitted value receive a standard value?

Use DEFAULT.

### Question 6

Does one table refer to another?

Use FOREIGN KEY.

### Question 7

What happens when the parent is deleted?

Choose deliberately among:

- CASCADE,
- SET NULL,
- RESTRICT,
- NO ACTION,
- another appropriate lifecycle strategy.

### Question 8

Can the referenced identifier change?

If yes, consider the implications of ON UPDATE behavior.

---

# 60. Key Classification Reference

| Key Type | Definition |
|---|---|
| Super key | Any attribute set that uniquely identifies a row |
| Candidate key | Minimal super key |
| Primary key | Selected candidate key used as the principal identifier |
| Alternate key | Candidate key not selected as primary |
| Composite key | Key containing multiple attributes |
| Natural key | Meaningful business/domain identifier |
| Surrogate key | Artificial identifier |
| Foreign key | Attribute set referencing a key in another or the same table |

A useful logical relationship is:

    Candidate key ⊆ Super keys

More precisely, every candidate key is a minimal super key, while a super key can contain unnecessary attributes.

---

# 61. Primary Key Design Example

Consider an employee table.

One possible design is:

    employee_id INTEGER PRIMARY KEY,
    employee_code TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE

This provides three distinct concepts:

- `employee_id`: internal row identity.
- `employee_code`: business identifier.
- `email`: unique business/contact attribute.

The primary key does not eliminate the need for additional constraints.

---

# 62. Composite Key Design Example

For:

    Enrollment(student_id, course_id)

the combination:

    (student_id, course_id)

identifies one enrollment relationship.

This is an excellent case for a composite key because neither column alone identifies an enrollment.

`student_id` identifies a student.

`course_id` identifies a course.

Together they identify the relationship.

---

# 63. Composite Unique Design Example

Suppose project codes only need to be unique within an organization.

The correct rule is:

    UNIQUE (organization_id, project_code)

not:

    UNIQUE (project_code)

The first permits:

    Organization A -> P-001
    Organization B -> P-001

while preventing:

    Organization A -> P-001
    Organization A -> P-001

This illustrates why constraints must match the scope of the business rule.

---

# 64. Data Integrity Layers

A relational schema can be viewed as several layers of integrity:

    Identity
        PRIMARY KEY

    Uniqueness
        UNIQUE

    Presence
        NOT NULL

    Domain validity
        CHECK

    Automatic values
        DEFAULT

    Relationships
        FOREIGN KEY

    Relationship lifecycle
        CASCADE / SET NULL / RESTRICT / NO ACTION

A strong design assigns each rule to the mechanism that expresses it most precisely.

---

# 65. SQLite-Specific Implementation Notes

The Python script uses only the standard-library `sqlite3` package.

This keeps the examples:

- self-contained,
- executable,
- independent of external packages,
- independent of a database server.

SQLite-specific behavior demonstrated in the script includes:

- `INTEGER PRIMARY KEY`,
- automatic integer identifier behavior,
- `PRAGMA foreign_keys`,
- partial indexes,
- schema introspection through PRAGMA statements,
- SQLite's handling of NULL values under UNIQUE.

These behaviors should not automatically be assumed to be identical in PostgreSQL, MySQL, SQL Server, Oracle, or other database systems.

---

# 66. Performance Considerations

Constraints have computational and storage consequences.

### Primary keys

Usually require efficient identity lookup structures.

### UNIQUE constraints

Require the database to detect duplicate values.

### Foreign keys

Require referential checks.

### Indexes

Can make constraint enforcement and queries faster but require maintenance.

### Composite indexes

The order of columns can affect query usability and performance.

### Wide keys

Large primary keys can increase the size of indexes and foreign-key references.

### Cascades

Large cascading operations can affect transaction size, locking, logging, and execution time.

Performance decisions should be based on realistic workload characteristics rather than on constraint avoidance.

Integrity should not normally be removed merely to avoid the cost of enforcing correctness.

---

# 67. Security and Data Exposure

A natural key may contain meaningful or sensitive information.

For example, a business identifier may reveal organizational structure or external identifiers.

A surrogate key can sometimes reduce the amount of business meaning exposed in internal relationships.

This does not automatically make surrogate keys more secure.

Security still requires appropriate:

- authentication,
- authorization,
- encryption,
- access controls,
- auditing,
- parameterized queries.

Keys and constraints are primarily mechanisms for identity and integrity.

---

# 68. Advanced Design Pattern: Soft Deletes

A soft-delete system may keep rows physically present while marking them inactive.

For example:

    active = 0

This creates a possible uniqueness problem.

A username might need to be unique among active users while historical inactive rows may contain the same username.

A partial unique index can express:

    unique username WHERE active = 1

This is a practical example of matching the exact scope of a business rule rather than applying an unnecessarily global UNIQUE constraint.

---

# 69. Advanced Design Pattern: Self-Referencing Hierarchies

A self-referencing foreign key:

    manager_id
        REFERENCES employees(employee_id)

can represent an organizational tree.

Important design questions include:

- Can the manager be NULL?
- Can an employee manage themselves?
- Can cycles occur?
- What happens when a manager is deleted?
- Should subordinate records remain?
- Should the relationship be reassigned?

A simple foreign key protects existence of the referenced employee, but more complex hierarchy rules may require additional mechanisms.

---

# 70. Advanced Design Pattern: Many-to-Many Associations

A junction table typically contains:

    PRIMARY KEY (left_id, right_id)

and:

    FOREIGN KEY (left_id)
    FOREIGN KEY (right_id)

This creates a relational representation of a many-to-many association.

Additional relationship attributes can be added:

    enrolled_on
    role
    quantity
    ranking
    membership_status

The junction table therefore represents more than merely a technical workaround; it is itself a meaningful relation.

---

# 71. Constraints and Application Logic

Application validation and database constraints serve complementary roles.

Application validation can provide:

- user-friendly messages,
- early feedback,
- form validation,
- business workflow handling.

Database constraints provide:

- centralized integrity enforcement,
- protection against alternate clients,
- consistency across applications,
- protection against accidental invalid writes.

A robust architecture commonly uses application validation for usability and database constraints for core data integrity.

---

# 72. Important Distinctions

## PRIMARY KEY vs UNIQUE

Primary key is the selected principal identifier.

UNIQUE enforces additional uniqueness.

## UNIQUE vs NOT NULL

UNIQUE prevents duplicate values.

NOT NULL prevents missing values.

They solve different problems.

## CHECK vs FOREIGN KEY

CHECK generally validates local row/domain conditions.

FOREIGN KEY validates references between relations.

## DEFAULT vs NOT NULL

DEFAULT supplies a value when a column is omitted.

NOT NULL prohibits NULL.

## Natural vs Surrogate Key

Natural keys come from the business domain.

Surrogate keys are artificial identifiers.

## Composite vs Single-Column Key

Composite keys use multiple attributes.

Single-column keys use one attribute.

---

# 73. Practical Schema Review Checklist

Before deploying a relational schema, verify:

- Every important entity has an appropriate primary key.
- Primary keys are stable enough for their intended role.
- Alternate business identifiers have appropriate UNIQUE constraints.
- Required attributes are NOT NULL.
- Domain restrictions are represented with CHECK where appropriate.
- Foreign-key relationships are explicitly declared.
- Nullable relationships are intentional.
- Composite constraints match the actual business scope.
- Referential actions are deliberate.
- Cascade behavior has been reviewed for destructive consequences.
- Foreign-key columns are indexed when workload requires it.
- NULL behavior is understood.
- Surrogate keys are not being mistaken for business uniqueness.
- Natural identifiers are used only when their properties justify them.
- INSERT, UPDATE, and DELETE behavior is tested.
- Transactions protect multi-step integrity requirements.
- DBMS-specific behavior is documented.
- Security responsibilities are separated from integrity responsibilities.

---

# 74. Conceptual Model

The complete relationship among the major concepts can be represented as:

    RELATIONAL MODEL
    |
    +-- Rows
    |
    +-- Attributes
    |
    +-- Keys
    |   |
    |   +-- Super Key
    |   |
    |   +-- Candidate Key
    |       |
    |       +-- Primary Key
    |       |
    |       +-- Alternate Key
    |
    +-- Composite Keys
    |
    +-- Natural Keys
    |
    +-- Surrogate Keys
    |
    +-- Foreign Keys
    |
    +-- Constraints
        |
        +-- PRIMARY KEY
        +-- UNIQUE
        +-- NOT NULL
        +-- CHECK
        +-- DEFAULT
        +-- FOREIGN KEY
            |
            +-- CASCADE
            +-- SET NULL
            +-- RESTRICT
            +-- NO ACTION
            +-- SET DEFAULT

This structure provides a useful mental model for separating identity,
uniqueness, mandatory values, domain rules, automatic values, and
relationships.

---

# 75. Python Script Coverage

The accompanying Python script demonstrates these concepts through executable SQLite examples:

1. Relational-table fundamentals
2. Candidate keys
3. Primary keys
4. SQLite integer primary keys
5. UNIQUE constraints
6. NULL and UNIQUE behavior
7. Foreign keys
8. Nullable foreign keys
9. Composite primary keys
10. Composite UNIQUE constraints
11. Natural versus surrogate keys
12. NOT NULL
13. CHECK
14. DEFAULT
15. Entity, referential, and domain integrity
16. Foreign-key actions
17. ON UPDATE CASCADE
18. Multiple foreign keys
19. Foreign keys referencing UNIQUE keys
20. Constraint interactions
21. UPDATE violations
22. DELETE violations
23. Transactions
24. Constraint introspection
25. Named constraints
26. PRIMARY KEY versus UNIQUE
27. Key classification
28. Super-key minimality
29. Business-rule translation
30. Self-referencing foreign keys
31. Many-to-many design
32. Deferrable constraints as an advanced concept
33. Conditional uniqueness
34. Composite UNIQUE and NULL
35. Data types versus constraints
36. Automated constraint testing
37. Performance considerations
38. Security considerations
39. Common mistakes
40. Edge cases
41. Normalization connections
42. Primary-key design
43. Production-style schema
44. Cascade trade-offs
45. Schema review
46. Constraint decision mapping
47. Integrated schema examples
48. Conceptual learning map

The examples are intentionally implemented rather than presented only as abstract definitions, allowing the behavior of keys and constraints to be observed through successful and intentionally rejected database operations.
