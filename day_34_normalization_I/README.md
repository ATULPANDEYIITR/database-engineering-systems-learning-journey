# Normalization I: Functional Dependencies and Anomalies

## Scope

This project introduces relational normalization through two closely connected ideas:

- **Functional dependencies**, which express deterministic relationships among attributes.
- **Anomalies**, which expose the practical problems created when facts with different determinants are stored redundantly in the same relation.

The three implementations use the same database-design principles from different technical perspectives:

- The Python program provides an executable analytical model with relation operations, FD validation, closure computation, candidate-key discovery, anomaly demonstrations, and decomposition.
- The JavaScript program models the same domain through objects, `Set`, class-based relations, projection, validation, and dependency analysis. Its implementation emphasizes JavaScript's collection and object-processing mechanisms.
- The C++ program presents a university registrar case study with an explicit dependency engine, relation abstraction, candidate-key enumeration, FD violation detection, and normalized projections.

The focus is deliberately narrower than the complete normalization theory. The material establishes the dependency and anomaly reasoning needed before moving to more advanced normal forms.

## Why Normalization Begins with Dependencies

A relational table may contain values that describe several different kinds of facts.

Consider an enrollment relation containing:

- student identity and student attributes,
- course identity and course attributes,
- section information,
- instructor identity and instructor attributes,
- an individual student's grade.

These facts do not necessarily have the same determinant.

For example:

`student_id -> student_name, student_program`

means that a student's identifier determines the student's name and program.

Similarly:

`course_id -> course_name, department`

means that the course identifier determines course-level facts.

A section may instead be identified by:

`course_id, section_no, term -> instructor_id`

The grade belongs to an enrollment:

`student_id, course_id, section_no, term -> grade`

Putting all of these facts into one relation causes the same student, course, and instructor information to appear repeatedly. The repeated data is not merely a storage issue. It creates opportunities for inconsistent database states.

Normalization uses dependency information to place facts at an appropriate relational level.

## Functional Dependencies

A functional dependency has the form:

`X -> Y`

where `X` is the determinant and `Y` is the dependent attribute set.

The statement means:

> If two valid tuples agree on every attribute in X, they must also agree on every attribute in Y.

For a relation containing employee data, the dependency:

`employee_id -> employee_name`

states that two tuples with the same employee identifier cannot legally contain different employee names.

The dependency is a semantic constraint. It is not simply a pattern discovered from the rows currently stored.

A table containing:

| employee_id | employee_name |
| --- | --- |
| E1 | Asha |
| E2 | Kabir |

does not prove that `employee_id -> employee_name` is true. The rule must come from the meaning of employee identifiers. A small sample can fail to expose a dependency violation even when the proposed dependency is false.

### Determinants and dependents

In:

`course_id -> course_name, department`

`course_id` is the determinant.

`course_name` and `department` are dependent attributes.

The determinant does not have to be a single attribute. A composite determinant is possible:

`course_id, section_no, term -> instructor_id`

The entire combination determines the instructor for that particular course section and academic term.

This distinction is important because a composite determinant can behave differently from each individual attribute.

## Attribute Closure

The Python, JavaScript, and C++ implementations calculate **attribute closure**.

For an attribute set `X`, its closure under a dependency set `F` is written as:

`X+`

The closure contains all attributes that can be derived from `X` using the functional dependencies.

Suppose the dependency set contains:

`course_id -> course_name, department`

and:

`course_id, section_no, term -> instructor_id`

and:

`instructor_id -> instructor_name`

Then:

`{course_id, section_no, term}+`

contains:

- `course_id`
- `section_no`
- `term`
- `course_name`
- `department`
- `instructor_id`
- `instructor_name`

because the initial attributes activate the section dependency, which produces `instructor_id`, which then activates the instructor dependency.

Closure computation therefore exposes dependency chains that are not immediately visible from the original FD list.

The implementations use a fixed-point algorithm:

1. Start with the requested attributes.
2. Find dependencies whose determinants are already contained in the closure.
3. Add their dependent attributes.
4. Repeat until no new attributes can be added.

The stopping condition is important. Reapplying already-satisfied dependencies must not cause an infinite loop.

## Superkeys and Candidate Keys

A **superkey** is an attribute set whose closure contains every attribute of the relation.

If the complete relation has attributes:

`student_id, student_name, student_program, course_id, course_name, department, section_no, term, instructor_id, instructor_name, grade`

then an attribute set is a superkey when its closure contains all of them.

A **candidate key** is a minimal superkey.

Minimality means that no proper subset of the candidate key is itself a superkey.

The registrar case study identifies:

`student_id, course_id, section_no, term`

as the enrollment identifier for the particular data model.

Its closure includes the grade directly. It also determines the course, section, instructor, and student information through the dependency paths.

The distinction between superkey and candidate key matters because adding unnecessary attributes can preserve uniqueness while destroying minimality.

The programs use exhaustive candidate-key enumeration because the schemas are intentionally small enough to make the mechanism transparent. Exhaustive enumeration has exponential worst-case behavior and is therefore unsuitable as a general strategy for very wide database schemas.

## Anomalies

Anomalies are practical symptoms of inappropriate redundancy.

They are especially useful when learning normalization because they connect abstract dependencies to concrete database behavior.

### Update anomaly

Consider:

| employee_id | employee_name | department | department_location |
| --- | --- | --- | --- |
| E101 | Anita | Finance | Mumbai |
| E102 | Rahul | Finance | Mumbai |

If:

`department -> department_location`

is true, the location of Finance is stored twice.

Suppose Finance moves from Mumbai to Pune. Updating only the first tuple produces:

| employee_id | employee_name | department | department_location |
| --- | --- | --- | --- |
| E101 | Anita | Finance | Pune |
| E102 | Rahul | Finance | Mumbai |

The relation now violates the functional dependency.

The Python, JavaScript, and C++ implementations deliberately create this state and detect the FD violation.

The normalized design separates department facts from employee facts. A department location then has one appropriate storage location rather than being copied into every employee tuple.

### Insertion anomaly

Suppose a relation stores:

`student_id, student_name, course_id, course_name, instructor`

and every row represents an enrollment.

A university approves a new course but no student has enrolled yet.

There is no natural tuple in which to store only the course information. Inserting a fabricated student would corrupt the meaning of the relation. Using arbitrary NULL values introduces a different representation problem.

The anomaly exists because course existence and student enrollment have been forced into the same relation.

A separate `Course` relation permits the course to exist independently of enrollment.

### Deletion anomaly

Consider a course with only one enrolled student.

If the final enrollment tuple is deleted, the course name and instructor information may disappear with it.

The deletion was intended to remove an enrollment, but it also removed an unrelated course fact.

The normalized decomposition separates these facts so that deleting an enrollment does not delete the course definition.

## Partial Dependencies

A partial dependency is especially relevant when the candidate key is composite.

The registrar enrollment key is:

`student_id, course_id, section_no, term`

But:

`student_id -> student_name, student_program`

does not require the entire enrollment key.

Likewise:

`course_id -> course_name, department`

uses only part of the composite enrollment key.

These are partial dependencies because non-key attributes depend on only a proper subset of the composite key.

This matters because repeating student and course facts across enrollment records creates unnecessary redundancy.

The first major normalization consequence is to separate facts that depend on the student identifier from facts that depend on the course identifier and from facts that depend on the complete enrollment identifier.

## Transitive Dependency Patterns

A dependency chain can also create redundancy through an intermediate determinant.

The registrar model contains:

`course_id, section_no, term -> instructor_id`

and:

`instructor_id -> instructor_name`

Therefore the section identifier indirectly determines `instructor_name`.

The important relationship is:

`course_id, section_no, term -> instructor_id -> instructor_name`

The instructor's name is a property of the instructor identified by `instructor_id`, not an independent property of every enrollment.

If the instructor name changes, storing it in every enrollment tuple creates many rows that must be updated.

The normalized model stores:

`Instructor(instructor_id, instructor_name)`

and references that instructor from:

`Section(course_id, section_no, term, instructor_id)`

This makes the dependency structure explicit.

## Python Implementation

The Python program defines a `Relation` class for basic relational operations.

It supports:

- tuple insertion with schema validation,
- conditional updates,
- conditional deletion,
- tabular output,
- dependency violation detection.

The `FunctionalDependency` class stores determinant and dependent attribute sets.

`attribute_closure()` implements the fixed-point closure algorithm. `implies()` uses closure to determine whether a proposed dependency follows from the supplied dependency set.

`is_superkey()` tests whether a set determines every relation attribute. `candidate_keys()` performs exhaustive minimal-superkey discovery.

The program also contains separate executable demonstrations for:

- update anomalies,
- insertion anomalies,
- deletion anomalies,
- functional dependency analysis,
- attribute closure,
- candidate keys,
- prime attributes,
- partial dependency patterns,
- transitive dependency patterns,
- projection into normalized relations,
- invalid FD definitions,
- incomplete tuples,
- concrete FD violations.

The decomposition creates relations corresponding to distinct fact types:

`Student(student_id, student_name, student_program)`

`Course(course_id, course_name, department)`

`Instructor(instructor_id, instructor_name)`

`Section(course_id, section_no, term, instructor_id)`

`Enrollment(student_id, course_id, section_no, term, grade)`

The code uses standard-library Python only.

## JavaScript Implementation

The JavaScript implementation uses a different representation from the Python program.

Functional dependencies are represented using JavaScript objects containing `Set` instances. This makes determinant and dependent membership operations explicit.

`attributeClosure()` demonstrates fixed-point processing using JavaScript's `Set` operations.

The `Relation` class models table structure and supports:

- schema validation,
- tuple insertion,
- updates,
- deletion,
- tabular rendering.

`findFDViolations()` compares tuple pairs and directly evaluates the definition of a functional dependency:

- compare determinant attributes,
- require equal determinant values,
- check whether dependent attributes disagree.

Candidate-key enumeration uses JavaScript arrays and recursive combination generation. The implementation intentionally exposes the combinatorial nature of key discovery rather than hiding it behind a database package.

The decomposition uses a `project()` function that constructs projected relations while removing duplicate tuples through serialized value combinations.

This implementation is executable with Node.js and does not require npm dependencies.

## C++ Case Study

The C++ implementation models a university registrar as a small dependency-aware system.

The central relation is:

`EnrollmentRecord`

with attributes for students, courses, sections, instructors, and grades.

The `FunctionalDependency` structure represents a dependency as two ordered sets of attributes.

`Relation` provides:

- schema validation,
- tuple insertion,
- row storage,
- tabular output.

`DependencyEngine` provides:

- attribute closure,
- FD implication,
- superkey testing,
- candidate-key enumeration.

The candidate-key implementation generates combinations of relation attributes and checks whether each combination is a superkey. Previously discovered smaller keys prevent larger supersets from being classified as candidate keys.

The program explicitly detects a department-location inconsistency using:

`department -> department_location`

The case study then projects the denormalized registrar relation into `Student`, `Course`, `Instructor`, `Section`, and `Enrollment`.

This is a useful systems-level perspective because the decomposition is not presented merely as a collection of syntax examples. Each resulting relation corresponds to a distinct business fact and determinant.

The program compiles with C++17 and uses only the standard library.

## Dependency Preservation and Decomposition

A decomposition is useful only when its resulting relations preserve the intended meaning and constraints.

For the registrar case:

`Student` owns student-level dependencies.

`Course` owns course-level dependencies.

`Instructor` owns instructor-level dependencies.

`Section` owns the relationship between a course section and its instructor.

`Enrollment` owns the grade associated with a student taking a particular section.

The decomposition reduces repeated facts.

For example, the original relation may store `Database Systems` and `Computer Science` in every enrollment for `DB101`. After decomposition, the course fact exists once in `Course`.

Likewise, `Dr. Rao` is stored once in `Instructor` rather than once for every enrollment involving that instructor.

This arrangement also makes updates local. Changing an instructor's name updates the instructor relation rather than every enrollment record.

## Anomaly Detection as a Dependency Check

The code demonstrates an important relationship between anomalies and functional dependencies.

For an FD:

`X -> Y`

a violation exists when two tuples satisfy:

`tuple1[X] = tuple2[X]`

but:

`tuple1[Y] != tuple2[Y]`

The programs search for such tuple pairs explicitly.

This is useful for debugging a populated relation, but it must not be confused with proving that an FD is valid.

A database may contain no violation today because the problematic combination has not yet occurred. The correctness of the dependency must come from domain semantics and database design.

## Edge Cases

### Composite determinants

The determinant can contain several attributes. The closure algorithm must require every determinant attribute before applying the dependency.

For:

`course_id, section_no, term -> instructor_id`

having only `course_id` is insufficient.

### Multiple dependent attributes

An FD such as:

`student_id -> student_name, student_program`

is equivalent to the collection:

`student_id -> student_name`

and:

`student_id -> student_program`

for closure purposes.

The implementations retain the dependent attributes together for convenient representation.

### Duplicate tuples

Duplicate tuples do not automatically constitute an FD violation. An FD concerns disagreement in dependent attributes among tuples that agree on the determinant.

Duplicate rows may still indicate poor relational design or missing key constraints, but they are a separate issue from the logical definition of an FD.

### Empty determinants

The implementations reject an empty determinant for educational clarity.

An empty determinant can be discussed formally in relational theory, but allowing it here would introduce a special constant-value dependency that is outside the intended scope of this first normalization module.

### Incomplete rows

The relation models reject incomplete tuples. This prevents missing attributes from silently being interpreted as dependency satisfaction or violation.

Real database systems have explicit NULL semantics, which complicate equality and dependency reasoning. The examples intentionally use complete values so that the FD mechanism remains mathematically clear.

## Common Design Mistakes

A common mistake is assuming that a unique-looking attribute is automatically a key. Uniqueness must come from the data model and integrity rules, not from visual inspection of a sample.

Another mistake is treating every attribute in a composite identifier as equally responsible for every non-key fact. Closure and dependency analysis reveal whether an attribute subset is actually sufficient to determine another attribute.

It is also incorrect to infer an FD merely because a current dataset happens to satisfy it. If two current rows happen to have the same course ID and course name, that is evidence about the current instance, not proof that the business rule guarantees the relationship.

Another frequent error is fixing redundancy by manually synchronizing duplicate values. That treats the symptom rather than the dependency structure. The stronger solution is to store each fact at the level determined by its natural determinant.

## Practical Normalization Workflow

A dependency-driven design process begins with the meaning of the attributes rather than with arbitrary table splitting.

Identify the facts represented by the relation and determine which attributes uniquely determine other attributes.

Write the meaningful functional dependencies explicitly.

Compute closures when determining whether a proposed identifier determines the complete relation.

Find minimal superkeys to identify candidate keys.

Inspect non-key attributes for dependencies on subsets of composite keys and for dependency chains through non-key determinants.

Then examine the relation for update, insertion, and deletion anomalies.

The resulting decomposition should place attributes with their appropriate determinants while maintaining meaningful relationships between the resulting relations.

## Performance Considerations

Attribute closure is generally inexpensive for small educational dependency sets. The implementation repeatedly scans the FD collection until reaching a fixed point.

Candidate-key discovery is the expensive operation in these examples. With `n` attributes, exhaustive enumeration may examine combinations across the entire power set, giving exponential growth.

FD violation detection in the supplied programs compares pairs of rows, giving quadratic behavior in the number of tuples for the straightforward implementation.

These algorithms are intentionally transparent. Production database systems rely on indexes, constraints, query planning, schema metadata, and specialized dependency-analysis techniques rather than repeatedly scanning all row pairs in application code.

## Security and Data Integrity

Normalization is primarily a data-integrity technique, but integrity failures can become operational and security problems.

Contradictory employee, customer, account, or authorization-related facts can cause incorrect decisions when applications trust duplicated attributes.

A dependency-aware schema reduces the number of places in which a fact can become inconsistent.

Normalization does not itself provide authentication, authorization, encryption, auditing, or protection from SQL injection. Those concerns remain separate database and application security responsibilities.

The relevant integrity principle here is that a fact should have a clear determinant and should not be unnecessarily duplicated across unrelated tuples.

## Limitations of This Module

The examples use complete in-memory tuples and do not attempt to reproduce every SQL feature.

They do not implement NULL-aware dependency semantics, transaction isolation, concurrency control, SQL query planning, foreign-key enforcement, or physical indexing.

The decomposition demonstrations are designed to make dependency structure visible. They should not be interpreted as a universal decomposition algorithm for arbitrary schemas.

Higher normal forms require additional reasoning beyond the material demonstrated here, particularly when multivalued dependencies, join dependencies, or dependency-preservation trade-offs become relevant.
