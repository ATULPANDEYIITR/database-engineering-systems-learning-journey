# Database Design Principles

## Logical vs. Physical Design and Design Objectives

Database design is the process of converting business information requirements into a structure that preserves correctness, supports required operations, and can operate efficiently as data and workload grow.

A useful design separates two related but different concerns:

- **Logical design** defines what information exists, how facts are related, which attributes identify entities, and which integrity rules must hold.
- **Physical design** determines how the logical model is implemented for a particular database engine and workload, including indexes, partitioning, storage choices, and access paths.
- **Design objectives** provide measurable criteria for deciding whether the resulting database is appropriate. Typical objectives include integrity, performance, maintainability, scalability, storage efficiency, security, and operational reliability.

The three implementations in this repository use an academic enrollment system as a common domain while approaching the subject differently.

---

## The Academic Enrollment Scenario

The case study models a university where students register for course sections during academic terms.

The central business facts are separated into:

`student` stores student identity and contact information.

`course` stores reusable information about an academic course.

`instructor` stores instructor identity.

`academic_term` identifies periods such as a semester.

`course_section` represents a particular offering of a course during a term, including its instructor, room, and capacity.

`enrollment` represents the relationship between a student and a section and stores facts specific to that relationship, such as enrollment date and grade.

This separation is important because these entities have different lifecycles and different ownership of facts. A course name belongs to the course rather than to every enrollment involving that course.

---

## Logical Design

Logical design describes the database independently of storage-engine details.

The major questions are:

- What are the entities?
- What attributes describe each entity?
- Which attributes form primary keys?
- Which alternate identifiers must remain unique?
- What relationships exist between entities?
- What are the cardinalities of those relationships?
- Which attributes depend on which keys?
- Which values are optional?
- Which references must point to existing entities?
- Which business rules must be enforced as constraints?

A logical design should not depend on whether a database engine stores rows in particular pages, uses a B-tree index, compresses data, or partitions a table.

### Keys

The `student` relation uses `student_id` as its primary key.

`student_number` and `email` are modeled as candidate keys because they are alternate identifiers that are required to be unique in the case study.

The `course` relation uses `course_id` as its primary key and `course_code` as an alternate unique identifier.

The `enrollment` relation uses the composite primary key `(student_id, section_id)`.

The composite key expresses an important business fact: a student can be associated with a section once. A second row containing the same student and section would represent a duplicate relationship rather than a new enrollment.

### Foreign keys

`course_section.course_id` references `course.course_id`.

`course_section.instructor_id` references `instructor.instructor_id`.

`course_section.term_id` references `academic_term.term_id`.

`enrollment.student_id` references `student.student_id`.

`enrollment.section_id` references `course_section.section_id`.

These references preserve relationship integrity. An enrollment cannot legitimately refer to a student or section that does not exist.

### Cardinality

The relationship between students and course sections is many-to-many.

A student can enroll in many sections, while a section can contain many students.

Relational modeling represents this relationship with the associative entity `enrollment`:

`student -> enrollment -> course_section`

This avoids storing a variable-length collection of section identifiers inside a student row and allows relationship-specific attributes such as `enrolled_on` and `grade`.

---

## Functional Dependencies and Normalization

A functional dependency describes a relationship in which one set of attributes determines another set of attributes.

Examples from the model include:

`student_id -> student_number, email`

`course_id -> course_code, course_name`

`section_id -> course_id, instructor_id, term_id, capacity`

`student_id, section_id -> enrolled_on, grade`

These dependencies provide a foundation for deciding where attributes belong.

If `course_name` is determined by `course_id`, placing the course name in every enrollment record introduces unnecessary repetition. A course rename would then require multiple updates.

The normalized design instead stores the course fact once in `course`.

### Update anomaly

Consider three enrollment records containing:

`CS301 | Database Systems`

If the university changes the course title, every duplicated occurrence must be changed. Updating only some rows creates contradictory representations of the same business fact.

The normalized structure avoids this particular anomaly because `course_name` is stored with the course entity.

### Insert anomaly

A design that stores course information only together with enrollment information can make it difficult to represent a newly created course before any student enrolls in it.

Separating `course` from `enrollment` allows the course to exist independently.

### Delete anomaly

If the only record containing course information is an enrollment row, deleting the last enrollment could accidentally remove the only representation of the course.

Separate entity storage prevents the enrollment lifecycle from controlling the existence of the course itself.

Normalization is not simply a rule to maximize the number of tables. It is a method for placing facts according to their dependencies and minimizing unintended redundancy.

---

## Physical Design

Physical design starts after the logical facts and relationships are understood.

The physical layer considers questions such as:

- Which queries execute frequently?
- Which predicates are selective?
- Which columns should be indexed?
- Should an index be unique?
- What should the leading column of a composite index be?
- How much storage will indexes consume?
- Is partitioning justified?
- How will data growth affect maintenance?
- Which access paths should be supported?
- How will inserts and updates interact with indexes?
- Which physical decisions depend on a particular database engine?

The physical design in the implementations includes indexes such as:

`ux_student_email`

`ux_student_number`

`ix_section_term_course`

`ix_enrollment_student_section`

`ix_enrollment_section_student`

These indexes are not part of the business meaning of the entities. They are access structures intended to make particular operations efficient.

---

## Why Index Column Order Matters

A composite index on:

`(student_id, section_id)`

is naturally suited to queries beginning with `student_id`.

A second index on:

`(section_id, student_id)`

supports the opposite traversal direction.

This distinction matters because the same two columns can represent different physical access patterns depending on their order.

For example, the enrollment table must support both:

- finding the sections belonging to a student
- finding the students belonging to a section

A single index may not provide equally efficient access for both workloads.

The JavaScript implementation models this using a simplified leftmost-column test. Real database optimizers use substantially more information, including statistics, selectivity, available operators, ordering requirements, estimated row counts, and alternative execution plans.

---

## Workload-Driven Physical Design

Physical design should be based on workload rather than on a rule such as "index every column."

The case study includes high-frequency operations such as:

- student transcript lookup
- section roster lookup
- course sections within an academic term
- student lookup by email

A selective query that examines millions of rows but returns only a small number of rows is a strong candidate for an appropriate access path.

By contrast, an infrequent query that returns a large fraction of a table may gain little from an additional index.

Every index also has a cost. Indexes consume storage and require maintenance when indexed rows are inserted, updated, or deleted.

A physical design therefore balances read performance against write overhead, storage, and operational complexity.

---

## Partitioning

Partitioning divides a logical table into physical pieces according to a partitioning key or rule.

The case study identifies `enrollment` as a possible candidate for range partitioning by academic term because enrollment data naturally has a time-oriented lifecycle.

Partitioning is not automatically beneficial.

It can introduce:

- additional operational configuration
- more complicated maintenance
- partition-management requirements
- constraints on partition-key design
- query-planning considerations
- migration and archival complexity

Partitioning becomes a physical design decision only after data volume, access patterns, retention policies, and database-engine behavior justify it.

The logical meaning of `enrollment` does not change simply because its physical rows are distributed among partitions.

---

## Design Objectives

A database design should be evaluated against explicit objectives rather than judged only by whether the schema "looks normalized."

### Integrity

Integrity means that stored facts obey defined rules.

The case study enforces or models:

- primary-key uniqueness
- candidate-key uniqueness
- foreign-key existence
- valid grade values
- positive section capacity
- duplicate-enrollment prevention
- required versus nullable attributes

Integrity rules are part of the logical contract of the data.

### Performance

Performance should be evaluated using representative workload measurements.

Relevant measurements include:

- query latency
- rows examined
- rows returned
- throughput
- execution frequency
- CPU consumption
- I/O activity
- memory consumption

The programs calculate selectivity for workload examples. Selectivity is useful because an access path becomes particularly valuable when a predicate narrows a large relation to a relatively small result.

A production decision should use the database engine's actual execution plans and statistics rather than the simplified estimates used by these programs.

### Maintainability

A maintainable schema gives each business fact a clear owner.

For example, course information should not be copied into every enrollment record simply because a particular report needs it.

Clear logical ownership makes changes easier to reason about and reduces the number of places where a business fact must be updated.

### Scalability

Scalability concerns more than the number of rows.

The design must account for:

- increasing enrollment volume
- increasing concurrent users
- increasing query frequency
- larger indexes
- longer maintenance operations
- historical data growth
- backup and recovery requirements

A design that works for ten thousand enrollment rows may require different physical strategies when the table contains hundreds of millions of rows.

### Storage efficiency

Storage efficiency includes:

- row width
- index footprint
- duplicate data
- historical retention
- partition overhead
- compression where supported
- temporary and operational storage

The C++ implementation includes an approximate index-footprint calculation to demonstrate why every physical access path has a storage cost.

The estimate is deliberately not presented as a database-engine measurement.

### Security

Security influences both logical and physical design.

The logical model identifies potentially sensitive attributes such as student email and birth date.

The physical implementation must then determine which database roles can access those attributes.

Possible mechanisms include:

- database privileges
- views
- row-level security where supported
- restricted service accounts
- auditing
- encryption
- parameterized database operations

Security should not depend solely on an application deciding not to display a field.

---

## Python Implementation

The Python program provides a complete model of the design process.

`Attribute`, `ForeignKey`, and `LogicalTable` represent the logical schema.

`LogicalSchema.validate()` checks relationships between tables and verifies that declared keys and foreign-key targets are structurally consistent.

The normalization portion explicitly represents functional dependencies so that the relationship between identifiers and dependent facts can be examined directly.

The physical layer uses `IndexDefinition` and `PhysicalDesign` to represent access paths separately from logical tables.

`QueryPattern` models a workload, allowing access paths to be compared with real query requirements.

`EnrollmentStore` then moves from schema reasoning into operational behavior. It checks:

- positive identifiers
- email format
- candidate-key uniqueness
- duplicate primary keys
- foreign-key existence
- section capacity
- composite enrollment uniqueness
- valid grade values

The Python program also demonstrates a transaction-like batch operation. It is intentionally described as a simulation because an in-memory snapshot does not provide the durability, isolation, concurrency control, logging, or recovery guarantees of a real database transaction.

---

## JavaScript Implementation

The JavaScript implementation uses a different emphasis.

The logical schema is represented by classes such as `Attribute`, `ForeignKey`, `LogicalTable`, and `LogicalSchema`.

The physical model uses `IndexDefinition` and evaluates indexes against query predicates.

A simplified leftmost-column rule is implemented by `IndexDefinition.canSupport()`. This demonstrates why composite-index column order matters without pretending to reproduce a production optimizer.

The program also introduces an event-driven model through `SchemaEventBus`.

Schema changes can emit events such as:

`column-added`

`index-added`

This illustrates a physical implementation concern that does not exist at the same level in the logical model. Adding an attribute can require compatibility checks and migration planning, while adding an index is primarily a physical access-path operation.

`WorkloadMonitor` records observed query characteristics including rows examined, rows returned, and latency.

The asynchronous transaction example reflects the way Node.js applications commonly interact with database clients. The code uses an in-memory snapshot for educational atomicity modeling; a real application should use the database driver's transaction mechanism.

---

## C++ Case Study

The C++ program acts as a repository governance and design-analysis engine for the academic enrollment system.

Its logical model contains:

- `Attribute`
- `ForeignKey`
- `TableDefinition`
- `LogicalSchema`

`LogicalSchema::validate()` checks primary keys, candidate keys, attributes, referenced tables, and foreign-key references.

The physical layer contains:

- `IndexDefinition`
- `PhysicalDesign`
- `QueryWorkload`

The workload evaluator compares frequent selective queries with modeled access paths.

The C++ program also calculates an approximate index storage footprint. This demonstrates a physical-design trade-off: a useful index can improve access speed but increases storage and write-maintenance requirements.

The operational portion uses `EnrollmentDatabase` with `std::map` structures to model students, sections, and composite enrollment keys.

`EnrollmentKey` is deliberately represented as a pair of identifiers rather than as a single generated number. This mirrors the logical meaning of the enrollment relationship.

Constraint failures are demonstrated through exceptions:

- duplicate student identifiers
- duplicate candidate keys
- missing student foreign keys
- missing section foreign keys
- duplicate student-section enrollment
- section capacity violations
- invalid grades

The C++ transaction class also emphasizes an important production distinction: application-level state reconstruction should not be confused with real database transaction semantics.

---

## Logical Design vs. Physical Design

| Concern | Logical design | Physical design |
|---|---|---|
| Main question | What does the data mean? | How should the database store and access it? |
| Entities | Defines entities and relationships | Implements their storage |
| Attributes | Determines business facts | Considers storage representation |
| Primary keys | Defines identity | May influence clustering or index structures |
| Foreign keys | Defines referential relationships | May affect indexing and modification costs |
| Normalization | Controls dependency-driven redundancy | May be balanced against workload-specific denormalization |
| Indexes | Usually not part of the conceptual model | Core physical access structures |
| Partitioning | Not normally part of the logical meaning | Physical distribution mechanism |
| Query workload | Provides requirements | Drives access-path selection |
| Storage footprint | Indirect concern | Direct design concern |
| Database engine | Should remain relatively independent | Strongly influences implementation |

The distinction is not absolute in every modeling methodology. Some design processes combine logical and physical decisions progressively. The key principle is to understand whether a decision changes the meaning of the data or only changes how efficiently that meaning is implemented.

---

## Normalization vs. Denormalization

Normalization is useful when duplicated facts would create inconsistency or modification anomalies.

Denormalization can be useful when a measured workload requires faster read access and the additional redundancy is intentionally controlled.

For example, a reporting system might maintain a precomputed representation of frequently requested enrollment information.

That representation should be treated as a deliberate derived structure with a defined refresh strategy. It should not become an accidental second source of truth.

A useful distinction is:

**Normalized source data** preserves authoritative business facts.

**Derived or denormalized data** optimizes particular workloads while accepting additional synchronization or storage requirements.

The decision should be based on workload evidence and correctness requirements.

---

## Common Design Mistakes

### Mixing logical and physical concerns too early

Choosing indexes before understanding the entities and dependencies can result in optimized access to an incorrect model.

The logical structure should establish what the facts mean before physical optimization is finalized.

### Storing many-to-many relationships inside a single attribute

Putting all section identifiers into a text field inside `student` prevents the database from treating each student-section relationship as an independently addressable row.

The `enrollment` associative entity provides a relational structure for the relationship.

### Repeating dependent facts

Copying `course_name` into every enrollment row increases storage and creates update anomalies.

The course entity should own course facts.

### Indexing every column

An index is not free.

Additional indexes consume storage and increase maintenance work during writes. They can also complicate physical design and backup or migration operations.

### Ignoring composite-index order

An index on `(student_id, section_id)` and an index on `(section_id, student_id)` are not interchangeable for all query patterns.

The leading column determines which predicate patterns can efficiently exploit the index.

### Assuming normalization automatically guarantees performance

Normalization primarily addresses logical redundancy and dependency structure.

Performance depends on workload, cardinality, indexes, query formulation, statistics, execution plans, hardware, concurrency, and database-engine behavior.

### Treating estimates as measurements

The programs use simplified selectivity and storage calculations.

Production decisions require measurements from representative datasets and realistic workload tests.

---

## Edge Cases

The implementations explicitly address several important edge conditions.

A student cannot be inserted with a duplicate primary key.

A student cannot reuse another student's email or student number.

An enrollment cannot reference a missing student.

An enrollment cannot reference a missing section.

A student cannot be enrolled twice in the same section.

A section cannot accept enrollment beyond its modeled capacity.

A grade must belong to the allowed grade domain.

A schema definition cannot reference an unknown table.

A foreign key must reference the declared primary key in the case-study model.

A composite key must be treated as a relationship identity rather than as two unrelated attributes.

---

## Schema Evolution

Logical and physical changes have different consequences.

Adding `status` to `course_section` is a logical schema change because it introduces a new business fact.

Adding an index on `course_section(status, term_id)` is primarily a physical change because it creates a new access path without changing the meaning of existing facts.

A production migration must consider:

- existing rows
- nullable versus non-nullable semantics
- default values
- validation of historical data
- application compatibility
- deployment order
- index-build duration
- locking behavior
- rollback strategy
- backup and recovery

A new non-nullable attribute cannot simply be assumed to work against an existing populated table. The migration must establish a valid value for existing records before the final constraint can safely be enforced.

---

## Performance Considerations

The most important physical-design decisions should be tied to workload measurements.

For the enrollment workload, useful measurements include:

`rows_examined / rows_returned`

query latency under realistic concurrency

execution frequency

index usage

write volume

table growth rate

index growth rate

maintenance cost

A highly selective lookup on a large table can justify an index even when the index adds significant storage.

A query returning most of a table may be better served by a sequential access strategy, depending on the database engine and workload.

Indexes also have write costs because an inserted or updated row may require changes to multiple access structures.

Partitioning can reduce the amount of data involved in some operations, but it can also introduce additional planning and administration complexity.

---

## Security and Operational Considerations

Logical design should identify data that requires restricted access.

In this case, student contact information and birth dates have different access requirements from course metadata.

A production system should define roles around required operations rather than giving every application identity unrestricted access to every table.

Physical security considerations can include:

- least-privilege database roles
- restricted views
- row-level policies where appropriate
- encrypted connections
- encrypted storage where required
- auditing
- parameterized queries
- controlled administrative access
- backup protection
- retention and deletion policies

Security requirements can influence physical architecture without changing the underlying logical relationships.

---

## Debugging and Validation Strategy

A database design should be validated at multiple levels.

### Structural validation

Check that:

- every table has an appropriate primary key
- key attributes actually exist
- foreign keys point to valid relations
- foreign-key columns have compatible semantics
- candidate keys represent genuinely unique business identifiers

### Dependency validation

Ask whether each non-key attribute depends on the correct determinant.

For example, `course_name` should depend on the course identity rather than on the enrollment identity.

### Workload validation

Measure representative queries using realistic cardinalities.

An index that appears useful on a small development dataset may become less useful at production scale, and an index that seems unnecessary on a small dataset may become essential when selectivity and concurrency change.

### Operational validation

Test:

- inserts
- updates
- deletes
- constraint failures
- migration behavior
- backup and restore procedures
- index maintenance
- high-concurrency access
- recovery scenarios

A logically correct schema can still have operational problems if migrations, backups, access control, or physical maintenance are not designed carefully.

---

## Design Principle

A robust database design begins with the facts the organization needs to preserve.

The logical model establishes entities, relationships, keys, dependencies, and integrity rules.

The physical model then uses workload and operational evidence to determine how those facts should be stored and accessed.

The separation does not mean the two designs are unrelated. Physical decisions depend on the logical structure, while workload evidence can reveal that the logical model needs refinement.

The important distinction is that an index, partition, or storage optimization should not silently change the meaning of the underlying business data.

A sound design therefore treats correctness as the foundation, workload evidence as the basis for physical optimization, and measurable design objectives as the criteria for evaluating the resulting system.
