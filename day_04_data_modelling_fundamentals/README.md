# Data Modeling Fundamentals

## Introduction

Data modeling is the disciplined process of representing business information, the relationships among pieces of information, and the rules that determine which states of that information are valid.

A data model connects business requirements to an implementable data structure. A typical modeling progression is:

1. Understand the business domain.
2. Identify entities and their meaning.
3. Identify attributes.
4. Identify identifiers and keys.
5. Identify relationships.
6. Define cardinality and optionality.
7. Capture business rules.
8. Build a conceptual model.
9. Transform the conceptual model into a logical relational model.
10. Normalize the design where appropriate.
11. Add integrity constraints.
12. Design indexes and physical structures according to workload.
13. Test valid and invalid states.
14. Address security, lifecycle, historical, and production requirements.

The accompanying Python script demonstrates these concepts progressively and then implements a university data model using SQLite.

---

## 1. Entity

An **entity** is a distinguishable object, concept, or event about which an organization needs to retain information.

Examples include:

- CUSTOMER
- STUDENT
- EMPLOYEE
- PRODUCT
- COURSE
- ORDER
- INVOICE
- DEPARTMENT

An entity should represent a meaningful business concept rather than merely a convenient programming structure.

### Entity type and entity instance

An **entity type** describes a category of similar objects.

For example:

- Entity type: `STUDENT`
- Entity instance: student with `student_id = 101`

The entity type defines the structure and meaning. An instance represents one occurrence of that type.

The Python script represents entity definitions through `EntityDefinition` and represents individual domain objects through classes such as `Customer`, `Employee`, and `Product`.

---

## 2. Attributes

An **attribute** describes a property of an entity or relationship.

For a STUDENT entity, possible attributes include:

- student_id
- name
- email
- date_of_birth

For a PRODUCT entity:

- product_id
- name
- price
- active

Attributes should represent facts that belong to the concept being modeled.

### Simple attributes

A simple attribute cannot meaningfully be decomposed for the model's intended purpose.

Examples:

- price
- gender code
- employee_id

### Composite attributes

A composite attribute consists of meaningful components.

A person's name might conceptually be represented as:

- first_name
- middle_name
- last_name

The Python script demonstrates this through the `PersonName` class.

Whether an attribute should remain conceptually composite depends on business requirements. In a normalized relational implementation, the useful atomic components are normally stored separately.

### Single-valued attributes

A single-valued attribute has one value for a particular entity occurrence.

For example, a student might have one date of birth.

### Multivalued attributes

A multivalued attribute can contain multiple values for one entity.

For example, a customer may have several telephone numbers.

In a relational database, a multivalued attribute is commonly transformed into a separate relation:

`CUSTOMER_PHONE(customer_id, phone_number)`

This avoids storing comma-separated values in one column.

### Stored attributes

A stored attribute is persisted directly.

Example:

`date_of_birth`

### Derived attributes

A derived attribute is calculated from other information.

For example, age can be derived from date of birth and the current date.

The Python script demonstrates this through the `Customer.age` property.

A derived value should not automatically be stored. Storing it may be appropriate when:

- calculation is expensive,
- historical snapshots are required,
- the value is intentionally materialized,
- reporting performance requires it.

The cost is consistency management.

---

## 3. Domains

A **domain** defines the valid set of values for an attribute.

A database column being declared as `TEXT` does not fully describe its business meaning. An email address, country code, course code, and free-form description may all technically be text while having completely different semantic rules.

The script defines domains such as:

- `EmailAddress`
- `PositiveMoney`
- `Age`

For example, an age domain can restrict values to a reasonable range.

Domains are important because they make data validation explicit.

A useful distinction is:

- **Data type:** how a system represents a value.
- **Domain:** which values are meaningful for a particular business attribute.
- **Business rule:** how values relate to other values or business states.
- **Database constraint:** a mechanism used to enforce a rule in persistent data.

---

## 4. Keys

Keys are central to data modeling because relationships require reliable identity.

### Candidate key

A **candidate key** is a minimal set of attributes that uniquely identifies an entity occurrence.

An entity can have more than one candidate key.

For EMPLOYEE, possible candidate keys could be:

- employee_id
- national_id
- email

provided each is genuinely unique and stable enough for the intended purpose.

### Primary key

A **primary key** is the candidate key selected as the principal identifier.

For example:

`EMPLOYEE(employee_id, ...)`

The primary key should uniquely identify every row and normally should not be nullable.

### Alternate candidate keys

Candidate keys not selected as the primary key are still important.

If `employee_id` is the primary key but email must also be unique, the model should preserve that uniqueness through a `UNIQUE` constraint.

A surrogate primary key does not eliminate the need to enforce business uniqueness.

### Composite key

A **composite key** contains multiple attributes.

The script uses:

`ENROLLMENT(student_id, course_id)`

This means that the combination of student and course identifies one enrollment.

Neither component alone is sufficient if a student can enroll in multiple courses and a course can have multiple students.

---

## 5. Natural Keys and Surrogate Keys

A **natural key** has business meaning.

Examples:

- course_code
- ISO country code
- a legally defined identifier

A **surrogate key** is a system-generated identifier with little or no business meaning.

Examples:

- student_id
- product_id
- course_id

### Natural-key advantages

Natural keys can:

- carry useful business meaning,
- already be unique,
- eliminate unnecessary technical identifiers in simple cases.

### Natural-key risks

Business identifiers may:

- change,
- be long,
- contain multiple attributes,
- have awkward formatting,
- become invalid after a business-policy change.

### Surrogate-key advantages

Surrogate keys generally:

- remain compact,
- simplify references,
- separate technical identity from business attributes,
- work well as foreign keys.

### Surrogate-key risks

A surrogate key does not automatically protect business uniqueness.

For example, using:

`customer_id`

does not prevent two rows from having the same business email address.

A separate `UNIQUE(email)` constraint may still be required.

---

## 6. Relationships

A **relationship** describes a meaningful association between entity types.

Examples:

- CUSTOMER places ORDER
- STUDENT enrolls in COURSE
- EMPLOYEE manages EMPLOYEE
- DEPARTMENT offers COURSE
- INSTRUCTOR teaches COURSE

Relationships should be expressed using business meaning rather than merely physical foreign-key terminology.

---

## 7. Cardinality

**Cardinality** describes how many occurrences of one entity can be associated with occurrences of another.

The primary relationship classifications are:

- one-to-one
- one-to-many
- many-to-many

### One-to-one

Example:

`PERSON 1:1 PASSPORT`

A business rule might state that each passport belongs to exactly one person and a person can have at most one passport.

### One-to-many

Example:

`CUSTOMER 1:N ORDER`

One customer may place many orders.

Each order belongs to one customer.

In a relational implementation, the foreign key normally appears on the many side:

`ORDER(customer_id)`

### Many-to-many

Example:

`STUDENT M:N COURSE`

A student can enroll in many courses, and a course can have many students.

A relational database does not normally represent this directly as one foreign-key column on either entity. It is transformed into an associative relation.

---

## 8. Optionality and Participation

Cardinality alone is not enough. The model must also express whether participation is optional or mandatory.

Common notation is:

- `0..1` = zero or one
- `1..1` = exactly one
- `0..N` = zero or many
- `1..N` = one or many

For example:

`CUSTOMER 0..N ORDER`

means a customer may have zero orders or many orders.

An order might have:

`ORDER 1..1 CUSTOMER`

meaning every order must belong to exactly one customer.

The Python script represents this through `RelationshipEnd`, including minimum and maximum cardinalities.

---

## 9. Business Rules

A **business rule** describes a condition that must hold because of business policy or operational reality.

Examples:

- Every order belongs to exactly one customer.
- An order must contain at least one line.
- Product quantity must be positive.
- Product price cannot be negative.
- A shipped order must have a shipment date.
- A course must belong to one department.
- An employee may have at most one direct manager.

Business rules are more expressive than simple entity definitions.

The script represents business rules with the `BusinessRule` class and executable validation functions.

---

## 10. Constraints

A **constraint** is a formal mechanism restricting valid database states.

Common relational constraints include:

- PRIMARY KEY
- FOREIGN KEY
- UNIQUE
- NOT NULL
- CHECK

### PRIMARY KEY

Guarantees row identity and uniqueness.

### FOREIGN KEY

Maintains referential integrity between related tables.

### UNIQUE

Prevents duplicate values or duplicate combinations of values.

### NOT NULL

Requires a value to be present.

### CHECK

Restricts values according to a Boolean condition.

For example:

`credits BETWEEN 1 AND 6`

The university model uses all of these mechanisms.

---

## 11. Referential Integrity

**Referential integrity** means that a foreign-key reference must correspond to a valid referenced key, unless the relationship is explicitly optional and represented by NULL.

For example:

`ENROLLMENT.student_id`

references:

`STUDENT.student_id`

An enrollment referring to a nonexistent student would violate referential integrity.

The Python script enables SQLite foreign-key enforcement and intentionally attempts invalid inserts to demonstrate the resulting integrity errors.

---

## 12. Foreign Keys

A **foreign key** represents a relationship between relations.

For example:

`INSTRUCTOR.department_id`

references:

`DEPARTMENT.department_id`

Foreign keys can be:

- single-column,
- composite,
- nullable for optional relationships,
- configured with delete/update actions.

Foreign keys are not merely technical connections. They encode business relationships.

---

## 13. Foreign-Key Delete Actions

Common actions include:

### RESTRICT

Prevents deletion when dependent rows exist.

This is useful when the dependent records must not outlive their parent.

### CASCADE

Deletes dependent records automatically.

This is useful for strongly owned dependent data such as some order-line or associative records.

It should be used cautiously because one delete can remove many rows.

### SET NULL

Removes the association by setting the foreign key to NULL.

This requires the foreign-key column to permit NULL.

The appropriate action should be determined by lifecycle semantics, not convenience.

---

## 14. Associative Entities

A many-to-many relationship often becomes an **associative entity**.

For:

`STUDENT M:N COURSE`

create:

`ENROLLMENT(student_id, course_id, enrolled_on, status, grade)`

The associative entity has an important property: it can contain attributes belonging to the relationship itself.

For example:

- enrolled_on
- grade
- enrollment status

A student's grade is not a permanent attribute of the student. It belongs to the student's participation in a particular course.

This is a major modeling distinction.

---

## 15. Relationship Attributes

A relationship attribute describes the association between entities.

For:

`STUDENT -- ENROLLS -- COURSE`

these attributes belong naturally to the enrollment:

- enrolled_on
- grade
- status

These do not belong directly to STUDENT or COURSE.

Correct ownership of attributes reduces redundancy and improves semantic clarity.

---

## 16. Recursive Relationships

A **recursive relationship** occurs when an entity relates to itself.

A common example is:

`EMPLOYEE manages EMPLOYEE`

An employee may have a manager who is another employee.

A relational implementation can use:

`EMPLOYEE(manager_id)`

where `manager_id` references `EMPLOYEE(employee_id)`.

Recursive relationships require additional validation because cycles may be invalid.

The script detects:

- nonexistent managers,
- self-management,
- management cycles.

---

## 17. Weak Entities

A **weak entity** has an identity that depends partly or completely on another entity.

An order line is a common example.

Suppose:

`ORDER_LINE(order_id, line_number, product_id, quantity)`

A line number such as `1` is not globally unique.

The identity is:

`(order_id, line_number)`

The order line therefore depends on the order for its full identity.

Weak-entity concepts are especially useful when a dependent object has no meaningful independent identifier within the business domain.

---

## 18. NULL and Optional Relationships

NULL requires careful interpretation.

NULL does not universally mean:

- zero,
- empty string,
- false,
- unknown,
- not applicable.

Its exact business meaning should be documented.

SQL also uses three-valued logic:

- TRUE
- FALSE
- UNKNOWN

For example, comparisons involving NULL do not behave like ordinary value comparisons.

Use:

`IS NULL`

and:

`IS NOT NULL`

rather than:

`= NULL`

or:

`<> NULL`

An optional foreign key is often represented by a nullable column.

For example:

`COURSE.instructor_id`

can be NULL if a course may exist before an instructor is assigned.

---

## 19. Entity Versus Attribute

One of the most important modeling decisions is determining whether a concept deserves to be an entity or should remain an attribute.

A concept is more likely to deserve entity status when it has:

- independent identity,
- its own lifecycle,
- multiple attributes,
- relationships with other concepts,
- repeated occurrences,
- independent business significance.

### Example: date of birth

`date_of_birth` normally works well as an attribute.

### Example: phone number

If a customer has multiple numbers and each number has metadata such as type, verification status, and validity period, a separate entity may be appropriate.

### Example: address

Address modeling depends strongly on the business.

If it is merely a simple value, an attribute may be sufficient.

If addresses are shared, independently maintained, historically tracked, or classified, an ADDRESS entity may be more appropriate.

---

## 20. Data Modeling Workflow

A disciplined workflow is:

### Step 1: Define scope

Determine the business process and organizational area being modeled.

### Step 2: Collect business rules

Interview stakeholders, inspect processes, and define the rules that must hold.

### Step 3: Identify entities

Find the important business concepts.

### Step 4: Identify attributes

Determine the facts needed about each entity.

### Step 5: Identify candidate keys

Determine which attributes can uniquely identify entity instances.

### Step 6: Select primary keys

Choose the principal identifier.

### Step 7: Identify relationships

Determine how entities interact.

### Step 8: Define cardinality and optionality

Determine minimum and maximum participation.

### Step 9: Resolve many-to-many relationships

Create associative entities when required.

### Step 10: Identify relationship attributes

Place facts on the relationship when they describe the association itself.

### Step 11: Analyze dependencies

Determine what facts depend on which identifiers.

### Step 12: Normalize

Remove inappropriate redundancy and dependency anomalies.

### Step 13: Map to relational tables

Define tables, columns, keys, and relationships.

### Step 14: Add integrity constraints

Use primary keys, foreign keys, UNIQUE, NOT NULL, and CHECK constraints.

### Step 15: Design indexes

Base indexes on actual workload and access patterns.

### Step 16: Test

Test both valid and invalid states.

---

## 21. Functional Dependencies

A **functional dependency** expresses a determination relationship.

If:

`student_id -> student_name, student_email`

then a given student ID determines the corresponding student name and email.

For an enrollment relation:

`(student_id, course_id) -> enrolled_on, grade`

The pair of identifiers determines the attributes specific to that enrollment.

Functional dependencies are central to normalization because they reveal which facts belong together.

The dependency must represent a genuine business rule rather than an accidental property of a small sample dataset.

---

## 22. Normalization

Normalization organizes relational data to reduce unnecessary redundancy and dependency anomalies.

### First Normal Form

A relation in 1NF should contain atomic values appropriate to the model and should not use repeating groups as a substitute for relational structure.

For example, storing:

`"9876, 1234, 5555"`

inside a phone-number column is generally poor relational design when the numbers must be queried individually.

### Second Normal Form

2NF concerns dependencies on parts of a composite key.

If a table has:

`PRIMARY KEY(student_id, course_id)`

a non-key attribute should depend on the complete key rather than only part of it.

For example, `student_name` depends on `student_id`, not on the complete enrollment key. Therefore it belongs in STUDENT rather than ENROLLMENT.

### Third Normal Form

3NF removes inappropriate transitive dependencies among non-key attributes.

For example, if:

`employee_id -> department_id`

and:

`department_id -> department_name`

then storing `department_name` directly in EMPLOYEE can create redundancy.

A separate DEPARTMENT relation is generally more appropriate.

---

## 23. Update, Insert, and Delete Anomalies

Poorly normalized models can produce anomalies.

### Update anomaly

If the same fact appears in many rows, updating only some occurrences creates inconsistent data.

### Insert anomaly

A fact may be impossible to insert without an unrelated fact.

For example, a course may be impossible to store until at least one student enrolls.

### Delete anomaly

Deleting one fact may accidentally delete another fact that was stored in the same row.

For example, deleting the final enrollment for a course could accidentally eliminate the only stored information about the course.

Normalization addresses these problems by separating facts according to their dependencies.

---

## 24. Normalization Versus Denormalization

Normalization is not a rule that every production system must maximize at all costs.

### Normalization benefits

- Reduced redundancy
- Clearer dependencies
- Easier consistency management
- Better representation of independent facts
- Reduced update anomalies

### Normalization costs

- More relations
- More joins
- Potentially more complicated read queries

### Denormalization

Denormalization intentionally introduces redundancy or precomputed data for a specific reason.

Possible motivations include:

- read-heavy workloads,
- reporting,
- analytics,
- latency requirements,
- materialized summaries.

The major risk is consistency.

A duplicated value creates an obligation to keep multiple copies synchronized.

The correct sequence is to establish a correct model first and then introduce measured, intentional denormalization when necessary.

---

## 25. Surrogate Keys Do Not Replace Business Constraints

Consider:

`CUSTOMER(customer_id, email)`

If `customer_id` is a surrogate primary key, the following can still be invalid:

| customer_id | email |
|---:|---|
| 1 | user@example.com |
| 2 | user@example.com |

If email must be unique, the model needs:

`UNIQUE(email)`

A surrogate identifier establishes technical identity. It does not automatically establish every business uniqueness rule.

---

## 26. Temporal Data

Many business systems must preserve historical states.

Examples:

- employee salary history,
- product price history,
- customer addresses,
- account status changes,
- contract versions.

A simple temporal design may use:

- valid_from
- valid_to

The script demonstrates salary history using this approach.

A critical requirement is preventing overlapping validity periods when the business expects exactly one valid version at a given time.

Temporal modeling becomes more complex when distinguishing:

- when a fact is true in the business world,
- when the system learned or recorded the fact.

These are different temporal dimensions.

---

## 27. Historical Snapshots

A current PRODUCT table may contain the current product price.

An invoice often cannot simply reference the current price because historical invoices must remain correct after the product price changes.

For example:

`INVOICE_LINE(product_id, product_name_at_sale, quantity, unit_price_at_sale)`

The snapshot values represent the transaction as it occurred.

This is deliberate denormalization with a strong historical purpose.

---

## 28. Derived Values

Consider an invoice line:

`quantity * unit_price`

The line total is derived.

The script implements this with the `InvoiceLine.line_total` property.

A derived value can remain calculated when:

- the calculation is cheap,
- source values are always available,
- consistency is more important than read latency.

It can be materialized when:

- calculation is expensive,
- read performance is critical,
- historical snapshots are required,
- the database or application has a reliable consistency mechanism.

---

## 29. Business Rules Beyond Basic Constraints

Some rules cannot be expressed easily with a simple primary key or foreign key.

Examples include:

- An employee and manager must belong to the same department.
- A customer can have no more than three active addresses.
- Two bookings cannot overlap in time.
- A shipped order must satisfy a payment condition.
- A resource cannot be double-booked.

Depending on the database and architecture, these rules may require:

- composite constraints,
- triggers,
- application/domain logic,
- transactions,
- specialized database features,
- carefully designed relational structures.

The important principle is that the rule should be identified first and the enforcement mechanism selected afterward.

---

## 30. Validation Layers

A robust data system can enforce rules at multiple layers.

### User-interface validation

Useful for immediate feedback.

It is not sufficient as the only integrity mechanism because users and applications can bypass interfaces.

### Application or domain validation

Useful for expressing business behavior and producing meaningful error messages.

### Database validation

Important because multiple applications, scripts, services, integrations, and administrative processes may write directly to the database.

Database constraints create a persistent integrity boundary.

---

## 31. Query and Relational Implementation

The university model in the script contains:

### STUDENT

- student_id
- name
- email
- date_of_birth

### COURSE

- course_id
- course_code
- title
- credits
- department_id
- instructor_id

### INSTRUCTOR

- instructor_id
- name
- email
- department_id

### DEPARTMENT

- department_id
- name

### ENROLLMENT

- student_id
- course_id
- enrolled_on
- grade

The model demonstrates the transformation:

`STUDENT M:N COURSE`

into:

`STUDENT 1:N ENROLLMENT N:1 COURSE`

This is one of the most important practical transformations in relational data modeling.

---

## 32. SQL Joins and Relationships

The script queries students and their courses using joins.

Conceptually:

`STUDENT -> ENROLLMENT -> COURSE`

The join conditions are:

`student.student_id = enrollment.student_id`

and:

`enrollment.course_id = course.course_id`

This demonstrates how logical relationships become SQL operations.

A LEFT JOIN is also demonstrated for optional relationships, such as a course that has no assigned instructor.

---

## 33. Data Dictionary

A **data dictionary** documents attributes and their meaning.

Useful metadata includes:

- table name,
- column name,
- data type,
- nullability,
- description,
- business meaning,
- key status,
- relationship information,
- allowed values.

The script provides a small programmatic data dictionary through `ColumnDefinition`.

Documentation is important because data models are semantic systems, not merely collections of columns.

---

## 34. Indexing and Performance

Indexes are physical optimization structures.

Common candidates include:

- primary keys,
- frequently searched unique identifiers,
- foreign keys used in joins,
- selective filtering columns,
- common ordering columns,
- composite query patterns.

Indexes have costs:

- storage consumption,
- additional write work,
- maintenance overhead,
- memory consumption.

Too many indexes can reduce write performance.

A foreign key relationship does not necessarily mean that every database automatically creates the most useful index for the foreign-key column.

Index design should be based on actual workload.

---

## 35. Composite Indexes

Suppose an application frequently performs:

`WHERE department_id = ? AND status = ?`

An index such as:

`(department_id, status)`

may support this access pattern effectively.

The order of columns in a composite index matters.

The best index depends on:

- query predicates,
- selectivity,
- sorting requirements,
- join patterns,
- workload,
- database optimizer behavior.

Index design should therefore be tested using actual query plans rather than assumptions.

The script uses SQLite's `EXPLAIN QUERY PLAN` to demonstrate how query access strategies can be inspected.

---

## 36. Security Considerations

Data modeling has security implications.

Important principles include:

- minimize unnecessary sensitive data,
- enforce least privilege,
- protect credentials,
- restrict access to sensitive tables,
- maintain appropriate auditing,
- use parameterized SQL,
- validate inputs,
- define retention requirements,
- consider encryption where appropriate.

The script demonstrates parameterized SQL rather than constructing SQL by concatenating external values.

For example, a value such as:

`CS101' OR 1=1 --`

must be treated as data, not interpreted as SQL syntax.

Parameterized queries are a fundamental defense against SQL injection.

---

## 37. Transactions

A transaction groups related database changes into a controlled unit.

For example, creating a student and enrolling that student in a course may represent one logical operation.

If one operation succeeds and the other fails, the database should not be left in an inconsistent intermediate state.

The script demonstrates a transaction containing:

1. student insertion,
2. enrollment insertion.

Transactions are essential when multiple changes must satisfy business rules collectively.

---

## 38. Production Considerations

A production data model should consider more than tables and relationships.

Important concerns include:

### Naming

Use consistent naming conventions.

### Data types

Select types that accurately represent the business semantics.

### Identity

Choose stable identifiers appropriate to the domain.

### Uniqueness

Explicitly enforce important business uniqueness.

### Referential integrity

Use foreign keys where relationships require database-enforced consistency.

### Nullability

Define exactly what NULL means.

### Delete behavior

Choose RESTRICT, CASCADE, SET NULL, or other mechanisms based on business lifecycle.

### Transactions

Protect multi-step state transitions.

### Indexes

Design around real workloads.

### Migrations

Schema changes should be managed systematically and safely.

### Retention

Determine how long different categories of data must remain available.

### Archival

Large historical datasets may require separate lifecycle strategies.

### Auditability

Some domains require historical records of changes.

### Security

Protect sensitive data and restrict access according to role and need.

---

## 39. Common Modeling Mistakes

### Treating every concept as an attribute

This can hide entities that have their own identity and lifecycle.

### Treating every concept as an entity

This can create unnecessary tables and complexity.

### Omitting identifiers

Every persistent entity needs a reliable way to be identified.

### Storing comma-separated lists

This makes individual values difficult to query, validate, constrain, and relate.

### Missing UNIQUE constraints

A surrogate primary key does not automatically prevent duplicate business facts.

### Ignoring optionality

A relationship must specify whether participation is required.

### Ignoring relationship attributes

Facts such as grade, enrollment date, and quantity may belong to relationships.

### Excessive NULL usage

NULL should have a clearly understood meaning.

### Relying exclusively on application validation

Other database writers may bypass the application.

### Using CASCADE without lifecycle analysis

A cascade can remove many dependent records unexpectedly.

### Premature denormalization

Duplicating data before identifying a real performance requirement creates unnecessary consistency problems.

---

## 40. ER Model to Relational Mapping

Common transformation rules are:

| Conceptual construct | Relational representation |
|---|---|
| Strong entity | Relation with its attributes and primary key |
| 1:N relationship | Foreign key on the N-side |
| M:N relationship | Associative relation |
| 1:1 relationship | Foreign key on an appropriate side, often UNIQUE |
| Multivalued attribute | Separate relation |
| Composite attribute | Atomic component columns |
| Weak entity | Owner key included in dependent identity |
| Recursive relationship | Self-referencing foreign key or associative relation |

These transformations convert semantic relationships into relational structures.

---

## 41. E-Commerce Example

A simplified e-commerce conceptual model can contain:

### CUSTOMER

Represents buyers.

### PRODUCT

Represents products offered by the business.

### ORDER

Represents a customer's transaction.

### ORDER_LINE

Represents an individual product occurrence within an order.

### PAYMENT

Represents payment transactions.

### ADDRESS

Represents customer addresses when addresses require independent management.

Typical relationships include:

`CUSTOMER 1:N ORDER`

`ORDER 1:N ORDER_LINE`

`PRODUCT 1:N ORDER_LINE`

`ORDER 1:N PAYMENT`

`CUSTOMER 1:N ADDRESS`

Potential rules include:

- every order belongs to one customer,
- every order has at least one order line,
- every order line references one product,
- quantity must be positive,
- payment amount cannot be negative,
- shipment status must obey payment and fulfillment rules.

The example illustrates how business requirements drive model structure.

---

## 42. Hospital Modeling Example

A simplified healthcare-oriented model might contain:

- PATIENT
- DOCTOR
- APPOINTMENT
- DEPARTMENT
- PRESCRIPTION
- MEDICATION

Possible relationships include:

`PATIENT books APPOINTMENT`

`DOCTOR belongs to DEPARTMENT`

`PATIENT receives PRESCRIPTION`

`PRESCRIPTION contains MEDICATION`

Sensitive domains require particularly careful consideration of:

- identity,
- access control,
- auditability,
- retention,
- historical correctness,
- data minimization.

The conceptual model should reflect the actual business process without storing unnecessary personal information.

---

## 43. Model Quality

A model should be reviewed for:

### Completeness

Are all relevant entities and relationships represented?

### Correctness

Do the entities and attributes reflect the actual business meaning?

### Consistency

Are names, definitions, and relationship interpretations consistent?

### Uniqueness

Are identifiers and business uniqueness rules correctly represented?

### Referential integrity

Can invalid references enter the database?

### Cardinality

Are minimum and maximum relationship counts correct?

### Optionality

Are mandatory relationships enforced?

### Dependency correctness

Do attributes belong to the correct determinant?

### Normalization

Is redundancy justified?

### Performance

Does the physical design support actual access patterns?

### Security

Does the model avoid unnecessary exposure and support appropriate access controls?

The script implements a basic automated model-quality report.

---

## 44. Model Testing

A data model should be tested with both valid and invalid states.

Useful tests include:

- valid primary keys,
- duplicate primary keys,
- duplicate business identifiers,
- valid foreign keys,
- missing foreign keys,
- NULL values where allowed,
- NULL values where forbidden,
- valid cardinality,
- invalid cardinality,
- invalid domain values,
- invalid business states,
- recursive relationship cycles,
- duplicate composite keys,
- historical interval overlaps.

The Python script uses `unittest` to test several of these cases.

Testing constraints is especially important because the absence of an error can be evidence that a required rule is not actually enforced.

---

## 45. Conceptual, Logical, and Physical Modeling

### Conceptual model

Focuses on business meaning.

It answers:

- What entities exist?
- What relationships exist?
- What are the major business rules?

Implementation details are minimized.

### Logical model

Transforms concepts into a formal data structure.

For a relational database, it defines:

- relations,
- attributes,
- keys,
- foreign keys,
- dependencies,
- normalization.

### Physical model

Deals with implementation details such as:

- specific data types,
- indexes,
- partitions,
- storage,
- database-specific constraints,
- performance structures.

A strong design preserves semantic correctness while moving through these levels.

---

## 46. Core Distinctions

| Concept | Meaning |
|---|---|
| Entity | Business object or concept |
| Attribute | Property of an entity or relationship |
| Relationship | Association between entities |
| Domain | Valid value set for an attribute |
| Candidate key | Minimal unique identifier |
| Primary key | Selected candidate key |
| Foreign key | Reference to another relation |
| Natural key | Business-meaningful identifier |
| Surrogate key | System-generated identifier |
| Cardinality | Number of related instances |
| Optionality | Whether participation is required |
| Business rule | Required business condition |
| Constraint | Formal enforcement mechanism |
| Normalization | Reduction of inappropriate redundancy |
| Denormalization | Deliberate redundancy for a justified purpose |
| Associative entity | Entity resolving an M:N relationship |
| Weak entity | Entity whose identity depends on another entity |
| Derived attribute | Value calculated from other information |

---

## 47. Implementation Structure in the Python Script

The script progresses from conceptual theory into executable implementation.

Its major components include:

- domain definitions,
- entity definitions,
- key definitions,
- relationship definitions,
- cardinality modeling,
- business-rule objects,
- an associative enrollment entity,
- recursive employee relationships,
- weak order-line identity,
- temporal salary history,
- normalization examples,
- relational table definitions,
- SQL DDL generation,
- SQLite database creation,
- sample data,
- SQL queries,
- referential-integrity demonstrations,
- transaction handling,
- schema introspection,
- query-plan inspection,
- validation functions,
- unit tests.

The implementation uses only the Python standard library, with SQLite provided by `sqlite3`.

---

## 48. Practical Modeling Principles

A technically strong data model should:

1. Represent business concepts rather than arbitrary application objects.
2. Give persistent entities clear identities.
3. Distinguish candidate keys from the selected primary key.
4. Preserve business uniqueness independently of surrogate identifiers.
5. Place attributes with the concepts they actually describe.
6. Model relationships explicitly.
7. Specify both cardinality and optionality.
8. Convert many-to-many relationships into appropriate associative structures.
9. Capture relationship-specific attributes on the relationship.
10. Use domains and constraints to protect valid values.
11. Analyze functional dependencies before deciding table structure.
12. Normalize to reduce inappropriate redundancy.
13. Denormalize only for a justified and measured reason.
14. Treat NULL semantics deliberately.
15. Preserve historical facts when current values are insufficient.
16. Use transactions for multi-step state changes.
17. Use foreign keys to protect referential integrity.
18. Design indexes according to actual workload.
19. Test invalid states as aggressively as valid states.
20. Treat security, retention, and lifecycle requirements as modeling concerns rather than afterthoughts.

---

## 49. Real-World Relevance

Data modeling is foundational to systems such as:

- banking platforms,
- e-commerce systems,
- education management systems,
- healthcare applications,
- inventory systems,
- human-resource systems,
- supply-chain platforms,
- customer relationship management systems,
- financial reporting systems,
- government information systems,
- analytics platforms.

A poor model can create duplicated facts, inconsistent records, difficult queries, weak integrity, security problems, and expensive migrations.

A well-designed model gives applications a stable representation of business reality and provides a foundation for reliable data operations.

