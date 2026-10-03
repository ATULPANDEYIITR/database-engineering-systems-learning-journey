# Cardinality: One-to-One, One-to-Many, and Many-to-Many

## Purpose

Cardinality describes how many instances of one entity can be associated with instances of another entity.

This repository models three distinct relationship patterns inside a university registration domain:

- **One-to-one:** a `Student` can have at most one `StudentProfile`, and each profile belongs to one student.
- **One-to-many:** a `Department` can contain many `Course` records, while each course belongs to one department.
- **Many-to-many:** a `Student` can take many courses and a `Course` can contain many students. The relationship is represented by an `Enrollment` association.

The implementations deliberately use different techniques in each language. Python emphasizes an explicit in-memory relational model and integrity validation. JavaScript emphasizes an event-driven relationship service using `Map`, `Set`, classes, and asynchronous validation. C++ presents the same domain as a strongly typed repository and focuses on composite keys, hash-based structures, validation, and algorithmic behavior.

## Cardinality as a Data-Modeling Constraint

Cardinality is not merely a description of how data happens to look at one point in time. It is a constraint on the valid state of the system.

For a one-to-one relationship, the important rule is uniqueness on the owning side. If a student already has profile `P100`, inserting another profile for that same student must fail.

For a one-to-many relationship, many child records can point to the same parent. A department can therefore be referenced by many courses. The restriction is on the child side: each course in this model has one `department_id`.

For a many-to-many relationship, neither endpoint is unique. A student can occur in many enrollment records and a course can occur in many enrollment records. The combination of the two endpoint identifiers is unique for one logical enrollment relationship.

These distinctions determine where keys, uniqueness rules, foreign-key references, and association records belong.

## One-to-One

The Python implementation represents a student with an optional `profile_id` and stores profiles separately. The repository rejects a second profile when `student.profile_id` is already populated.

The JavaScript implementation uses the same ownership idea through `Student.profileId`. `addProfile()` checks that the referenced student exists and that the student does not already have a profile.

The C++ implementation represents the optional relationship with `std::optional<std::string>`. This is useful because the absence of a profile is different from a profile identifier containing an empty string.

A one-to-one relationship can be represented in a relational database by placing a foreign key on one table and enforcing uniqueness on that foreign key. Without the uniqueness constraint, the structure becomes one-to-many instead.

The distinction is therefore structural:

| Relationship | Parent-side multiplicity | Child-side multiplicity | Typical enforcement |
| --- | --- | --- | --- |
| One-to-one | At most one related record | At most one owner | Foreign key plus unique constraint |
| One-to-many | Many related records | One parent | Foreign key on child |
| Many-to-many | Many related records | Many related records | Association table with composite or unique key |

## One-to-Many

The department-course relationship demonstrates a parent with multiple children.

`Department D10` owns courses such as `C101`, `C102`, and `C103`. Each course stores one `department_id`, so a course does not simultaneously belong to multiple departments in this model.

The Python `Department.course_ids` set provides a reverse index, while `Course.department_id` represents the direct relationship. The repository's integrity validator checks that these two representations agree.

The JavaScript implementation uses `Department.courseIds` as a `Set`. Adding a course updates both the course record and the department's collection of course identifiers.

The C++ implementation stores the same relationship with `Department::courseIds` and `Course::departmentId`. This makes the direction of the relationship explicit and allows efficient membership tests through `std::unordered_set`.

A common modeling mistake is to interpret "one department has many courses" as requiring a list of complete course objects inside the department record. In a relational design, the normal representation is a foreign key on the course rows. A reverse collection may be maintained by application code or obtained through a query.

## Many-to-Many

Many-to-many relationships require a different structure because neither endpoint can hold a single foreign-key value that fully represents the relationship.

A student may take `C101`, `C102`, and `C103`. At the same time, `C101` may contain `S100`, `S101`, and `S102`.

The relationship is therefore represented by `Enrollment`.

Conceptually, the data is:

`Student -> Enrollment <- Course`

An enrollment contains the two endpoint identifiers and can also contain attributes belonging to the relationship itself, such as:

- enrollment date
- semester
- status
- grade

This is one reason an association entity is more useful than trying to store a single list directly on either endpoint.

### Composite relationship identity

The logical identity of an enrollment in the implementations is the pair:

`(student_id, course_id)`

The Python repository explicitly searches for an existing pair before inserting an enrollment.

The JavaScript service converts the pair into a stable key such as `S100::C101` and stores enrollments in a `Map`.

The C++ implementation uses a dedicated `EnrollmentKey` structure containing `studentId` and `courseId`. `EnrollmentKeyHash` makes the composite key usable in an `unordered_map`.

The result is a direct representation of the rule that the same student-course pair cannot be inserted twice.

## The Relationship Between the Three Patterns

The three cardinalities should not be treated as interchangeable.

A one-to-one relationship answers:

> Can this entity have more than one related entity?

A one-to-many relationship answers:

> Can one parent be associated with multiple child records while each child has one parent?

A many-to-many relationship answers:

> Can both sides participate in multiple relationships with the other side?

The university example makes the differences concrete:

`Student S100 -> Profile P100`

is one-to-one.

`Department D10 -> Course C101, C102, C103`

is one-to-many.

`Student S100 -> C101, C102` and `Student S101 -> C101, C103`

is many-to-many through `Enrollment`.

## Python Implementation

The Python program builds a complete in-memory relationship repository.

`Student`, `StudentProfile`, `Department`, `Course`, and `Enrollment` are represented with dataclasses. The repository maintains separate dictionaries for entity lookup and a set of enrollment records for the many-to-many relationship.

The one-to-one implementation is enforced by checking whether a student already owns a profile.

The one-to-many implementation validates that a course's `department_id` references an existing department and maintains the department's course index.

The many-to-many implementation validates both endpoints, prevents duplicate student-course pairs, and provides queries in both directions.

The `validate_integrity()` method is particularly important because it demonstrates that relationship correctness involves more than checking individual objects. It verifies forward references, reverse indexes, endpoint existence, and duplicate relationship pairs.

The program also exercises failure conditions rather than merely constructing valid data. It attempts to create a second profile, reference a nonexistent department, duplicate an enrollment, and enroll a nonexistent student.

The `find_common_courses()` method demonstrates a useful many-to-many query by taking the set intersection of two students' course sets.

## JavaScript Implementation

The JavaScript implementation treats cardinality as part of an event-driven domain service.

`Map` is used for primary entity lookup because identifiers are the natural keys of the records. `Set` is used for collections of related identifiers because duplicate relationship identifiers should not be stored.

The `CardinalityService` extends Node.js's `EventEmitter`. Successful mutations emit events such as `student.created`, `profile.attached`, `course.created`, and `enrollment.created`.

This is useful in a larger system because relationship mutations can become observable domain events. An audit component, cache updater, notification service, or persistence layer could react to these events without changing the relationship-validation logic itself.

The many-to-many relationship uses a composite string key in the form `studentId::courseId`. The key is checked before an enrollment is inserted.

The service also exposes asynchronous integrity validation. The current implementation validates in memory, but the asynchronous interface demonstrates how the operation could later await database or transactional work without changing the caller's high-level workflow.

The `withdraw()` operation shows that relationship cardinality also matters during mutation. Removing an enrollment must update both the association store and the student's course index.

## C++ Case Study

The C++ program models the university registration domain as a typed repository.

The one-to-one relationship uses `std::optional<std::string>` for the student's profile reference. This explicitly models the possibility that a student has no profile while preventing multiple profile identifiers from occupying that field.

The one-to-many relationship stores course identifiers in `Department::courseIds` and the owning department identifier in `Course::departmentId`.

The many-to-many relationship is represented by `Enrollment`. A custom `EnrollmentKey` contains the two endpoint identifiers, and `EnrollmentKeyHash` permits the relationship to be stored in an `std::unordered_map`.

This representation makes the logical composite key visible in the type system.

The repository validates references before mutations. A course cannot be created for a missing department, and an enrollment cannot be created for a missing student or course.

Duplicate enrollment detection operates on the composite key. This is more precise than treating the student or course identifier independently because neither identifier is unique within the many-to-many relationship.

The `validateIntegrity()` method checks both directions of important relationships. It detects missing endpoints, inconsistent reverse references, and disagreements between association records and their keys.

The case study also tests withdrawal and re-enrollment, showing that cardinality constraints apply to updates as well as inserts.

## Keys and Cardinality

Cardinality and key design are closely related.

A primary key identifies one entity record. A foreign key identifies a related record. A unique constraint prevents multiple records from claiming a value that must be unique.

For one-to-one relationships, the foreign key on the dependent side commonly needs a uniqueness constraint.

For one-to-many relationships, the foreign key normally does not need to be unique because multiple child records must be allowed to reference the same parent.

For many-to-many relationships, the association table commonly has either a composite primary key such as `(student_id, course_id)` or a surrogate identifier combined with a unique constraint on the two foreign keys.

The implementations use these ideas directly rather than treating cardinality as only a documentation concept.

## Referential Integrity

Cardinality describes how many relationships are allowed, while referential integrity verifies that relationship endpoints actually exist.

For example, this relationship is invalid:

`Course C999 -> Department D404`

if `D404` does not exist.

Likewise, this enrollment is invalid:

`Student S404 -> Course C101`

if `S404` does not exist.

The implementations reject such operations before modifying their relationship structures.

A production relational database normally enforces these conditions through foreign keys and transactions. Application-level validation remains useful because it can provide earlier, clearer domain errors, but it should not be treated as a replacement for database constraints when persistent relational storage is used.

## Reverse References

The examples intentionally maintain some relationships in both directions.

A student has a `profileId`, while a profile contains `studentId`.

A course has a `departmentId`, while a department contains its course identifiers.

This makes queries convenient, but it introduces a consistency responsibility: both representations must be updated together.

The integrity validators demonstrate why duplicated relationship state is potentially dangerous. If the course says it belongs to `D10` but `D10` does not contain that course in its reverse index, the model is inconsistent.

A production system may avoid storing redundant reverse state and derive it through queries, or it may maintain denormalized indexes with transactional guarantees.

## Query Direction

Cardinality influences query patterns.

For one-to-one data, finding the related record is a direct lookup because at most one result is expected.

For one-to-many data, querying a department's courses naturally returns multiple records.

For many-to-many data, either endpoint can be the starting point. The system may need:

`Student -> Enrollment -> Course`

or:

`Course -> Enrollment -> Student`

The Python and JavaScript programs expose both directions for the many-to-many relationship. The C++ case study also provides student-to-course and course-to-student queries.

This bidirectional behavior is one of the main practical differences between a many-to-many association and a simple foreign-key relationship.

## Performance Considerations

The examples use hash-based structures for identifier membership because relationship collections frequently need existence checks.

A hash-set membership operation is average O(1), although worst-case behavior depends on hashing and implementation details.

The Python and JavaScript implementations use sets for related identifiers. The C++ implementation uses `std::unordered_set` and `std::unordered_map`.

The course-to-student query in the examples scans enrollment records. If there are `E` enrollment records, a direct scan is O(E).

A production database would normally create an index on the relevant association-table foreign key, such as `course_id`, so that reverse many-to-many queries do not require a complete table scan.

Finding shared courses can be performed efficiently by intersecting relationship sets. The C++ implementation deliberately iterates through the smaller set and checks membership in the larger set, reducing unnecessary work.

## Edge Cases

A robust cardinality implementation must define what happens when an entity has no related records.

A student without a profile is valid under the "at most one" interpretation of one-to-one. The Python and C++ models represent this absence explicitly.

A department without courses is also valid. One-to-many does not imply that the parent must have at least one child.

A student with no enrollments is valid in the many-to-many model.

Duplicate association records are different. Two identical student-course enrollments represent the same relationship and are rejected.

Missing references are also different from empty relationships. A missing department identifier is an invalid reference, not an empty department relationship.

## Common Modeling Errors

### Treating one-to-many as many-to-many

If every course belongs to exactly one department, adding a separate association record for every department-course relationship unnecessarily changes the model. A foreign key on `Course` is sufficient.

### Forgetting uniqueness in one-to-one

A foreign key by itself does not necessarily prevent multiple profiles from pointing to the same student. The one-to-one requirement needs uniqueness on the dependent reference.

### Storing a many-to-many relationship in one endpoint

Putting a single course identifier on `Student` cannot represent multiple enrollments. A list can represent several courses, but it moves the association into an embedded structure and makes relationship attributes and relational integrity more difficult to manage.

### Omitting the association entity

A many-to-many relationship often needs its own data because the relationship itself has attributes. `Enrollment` can carry semester, status, grade, dates, or other information that belongs to the relationship rather than to either endpoint.

### Updating only one side of a relationship

If an application maintains both forward and reverse indexes, updating only one side produces an inconsistent graph. The integrity checks in all three implementations are designed to expose this failure.

## Validation and Failure Handling

The implementations distinguish between two important classes of errors.

A reference error occurs when an operation points to an entity that does not exist.

A cardinality error occurs when the referenced entities exist but the proposed relationship violates the allowed multiplicity.

For example:

`D404` not existing is a reference problem.

Adding a second profile to `S100` is a cardinality problem.

Creating a second `S100`-`C101` enrollment is a duplicate relationship problem.

Keeping these cases distinct improves diagnostics and makes application behavior easier to test.

## Security and Data Integrity

Cardinality rules contribute to data integrity and can prevent malformed relationship state, but cardinality itself is not an authorization mechanism.

A system must still separately control who is allowed to create, modify, or remove relationships.

For persistent applications, relationship mutations should normally occur inside transactions when several tables or association records must change together. A successful enrollment, for example, should not leave an enrollment record inserted while the corresponding relationship index remains stale because a later operation failed.

User-supplied identifiers should also be validated according to the application's identifier rules. In a database-backed implementation, parameterized queries should be used rather than constructing SQL from identifiers or other external input.

## Production Database Mapping

The in-memory structures map naturally to relational tables.

A one-to-one design can resemble:

`students(id, ...)`

`student_profiles(id, student_id UNIQUE, ...)`

A one-to-many design can resemble:

`departments(id, ...)`

`courses(id, department_id, ...)`

A many-to-many design can resemble:

`students(id, ...)`

`courses(id, ...)`

`enrollments(student_id, course_id, semester, grade, PRIMARY KEY(student_id, course_id))`

The exact schema depends on whether the same student can enroll in the same course more than once across different semesters. If historical enrollment is required, the logical key might instead include semester or another course-offering identifier.

That design decision illustrates an important principle: cardinality must be defined against the business identity of the relationship. If `S100` taking `C101` in Fall 2026 and `S100` taking `C101` in Fall 2027 are distinct valid relationships, then `(student_id, course_id)` alone is not the complete key.

## Practical Interpretation

The three relationship types represent different constraints rather than different ways of naming the same structure.

One-to-one establishes uniqueness between two entity instances.

One-to-many establishes a parent-child relationship where many children may share one parent.

Many-to-many establishes an association in which both sides can participate repeatedly, normally requiring an association entity or table.

The implementations make these distinctions executable. They validate references, prevent invalid multiplicities, represent many-to-many relationships through an explicit association, query relationships in both directions, and check whether the resulting relationship graph remains internally consistent.
