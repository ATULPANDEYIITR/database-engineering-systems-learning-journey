# Advanced Normalization: BCNF, 4NF, and 5NF

## Scope

Advanced normalization addresses dependencies that remain important after the basic normalization process has separated obvious repeating groups and partial or transitive dependencies.

This implementation set focuses on three distinct normal forms:

- **BCNF** strengthens the treatment of functional dependencies by requiring every non-trivial determinant to be a superkey.
- **4NF** extends dependency analysis to multivalued dependencies, which arise when two independent sets of values are associated with the same determinant.
- **5NF** addresses join dependencies and decompositions that cannot be justified solely through functional or multivalued dependencies.

These normal forms are related, but they solve different sources of redundancy. Treating them as interchangeable obscures the reason a schema requires a particular decomposition.

---

## Functional Dependencies as the Foundation

A functional dependency has the form `X -> Y`.

It means that whenever two tuples agree on all attributes in `X`, they must also agree on every attribute in `Y`.

For example:

`InstructorID -> InstructorOffice`

means that an instructor has one determined office in the modeled domain.

The determinant is the left-hand side, `InstructorID`, while the dependent is the right-hand side, `InstructorOffice`.

The important question for BCNF is not simply whether an FD exists. The important question is whether the determinant is a superkey of the relation.

### Attribute closure

The Python, JavaScript, C++, and Java implementations compute attribute closure.

For a set of attributes `X`, its closure `X+` contains the attributes that can be derived from `X` using the known functional dependencies.

If:

`X+ = R`

then `X` is a superkey for relation `R`.

Closure is therefore central to candidate-key discovery and BCNF testing.

The implementations repeatedly apply dependencies whose determinants are already contained in the current closure. The process stops when no new attribute can be derived.

### Candidate keys

A candidate key is a minimal superkey.

The implementations enumerate attribute subsets for small educational schemas, compute their closures, and retain only minimal superkeys.

This exhaustive approach is useful for demonstrating the mechanics because every candidate is visible. It is not an appropriate strategy for very large schemas because the number of subsets grows exponentially with the number of attributes.

---

## BCNF

Boyce-Codd Normal Form requires:

> For every non-trivial functional dependency `X -> Y` that holds in relation `R`, `X` must be a superkey of `R`.

A dependency is trivial when its dependent attributes are already contained in its determinant.

For example:

`{StudentID, CourseID} -> {StudentID}`

is trivial because `StudentID` is already part of the determinant.

A dependency such as:

`InstructorID -> InstructorOffice`

is non-trivial when `InstructorOffice` is not part of `InstructorID`.

The BCNF question is then whether `InstructorID` determines the complete relation.

If it does not, the dependency is a BCNF violation.

### BCNF case study

The implementations model a relation containing:

- `Student`
- `Course`
- `Instructor`
- `InstructorOffice`

with dependencies:

`{Student, Course} -> Instructor`

and:

`Instructor -> InstructorOffice`

The first determinant can identify the instructor associated with a student-course assignment.

The second determinant identifies the instructor's office, but `Instructor` does not identify an entire student-course assignment. Therefore the second dependency violates BCNF in the original combined relation.

The BCNF decomposition separates instructor facts from teaching assignments.

The conceptual result is:

`Instructor(InstructorID, InstructorOffice)`

and:

`TeachingAssignment(StudentID, CourseID, InstructorID)`

The decomposition removes the repeated instructor-office fact from every teaching assignment.

---

## BCNF Decomposition Rule

For a violating dependency:

`X -> Y`

in relation `R`, a standard BCNF decomposition produces:

`R1 = X ∪ Y`

and:

`R2 = R - (Y - X)`

The Python, JavaScript, C++, and Java implementations apply this transformation recursively.

The recursion matters because decomposing one violating relation can produce another relation that still contains a BCNF violation.

The algorithm therefore continues until each resulting relation has no detected non-trivial FD whose determinant is not a superkey.

---

## Lossless Decomposition

Normalization is not useful if decomposition loses valid information.

A lossless decomposition allows the original relation to be reconstructed through joins without introducing incorrect combinations or losing tuples.

The Python and C++ implementations use concrete rows to demonstrate reconstruction. The JavaScript implementation performs natural joins over projected row sets, while the SQL implementation reconstructs decomposed relations with actual PostgreSQL joins.

For the instructor example, the decomposition is based on:

`Instructor -> InstructorOffice`

The common attribute `Instructor` identifies the office row associated with each teaching assignment, allowing the original information to be reconstructed.

Losslessness is therefore a structural property of the decomposition, not simply a visual impression that the tables "look normalized."

---

## Dependency Preservation

A second issue is dependency preservation.

A decomposition is dependency-preserving when the constraints from the original schema can be enforced by checking the decomposed relations without reconstructing the entire original relation.

BCNF does not guarantee dependency preservation.

This is an important distinction from losslessness:

- **Lossless decomposition** asks whether the original information can be reconstructed.
- **Dependency preservation** asks whether the original dependencies can still be enforced locally in the decomposed schema.

A design can be lossless while making some original dependency checks more difficult.

The Python implementation explicitly analyzes this trade-off rather than assuming that every BCNF decomposition automatically preserves every dependency.

---

## 4NF

Fourth Normal Form addresses **multivalued dependencies**.

An MVD is written:

`X ->> Y`

and describes a situation in which, for a given value of `X`, the set of `Y` values is independent of another set of attributes.

This is fundamentally different from an FD.

An FD says that one value determines another value.

An MVD says that one determinant is associated with a set of values independently of another set of values.

### Employee capability example

The implementations use:

`Employee(Employee, Skill, Language)`

where an employee can have multiple skills and multiple spoken languages.

Suppose employee `E1` has:

- skills: Python, SQL
- languages: English, French

If skills and languages are independent facts, the combined relation must contain:

- Python / English
- Python / French
- SQL / English
- SQL / French

The four rows are not four independent business facts. They are the combinations created by two independent sets.

The relevant dependency can be expressed as:

`Employee ->> Skill`

with the complementary independent information represented by `Language`.

Storing the cross-product directly creates unnecessary repetition.

---

## 4NF Rule

A relation is in 4NF when, for every non-trivial multivalued dependency:

`X ->> Y`

the determinant `X` is a superkey.

This is deliberately analogous to the BCNF rule, but the dependency being tested is different.

BCNF tests functional dependencies.

4NF tests multivalued dependencies.

### 4NF decomposition

For a non-trivial MVD:

`X ->> Y`

in relation `R`, the standard decomposition is based on:

`R1 = X ∪ Y`

and:

`R2 = X ∪ (R - Y)`

For the employee example, the resulting relations are conceptually:

`EmployeeSkill(Employee, Skill)`

and:

`EmployeeLanguage(Employee, Language)`

The Cartesian combinations no longer need to be stored explicitly.

The SQL implementation represents these relations as `employee_skill` and `employee_language`.

---

## Why 4NF Is Not Just "More BCNF"

BCNF cannot express every redundancy caused by independent multivalued facts.

Consider:

`Employee ->> Skill`

and:

`Employee ->> Language`

The issue is not that a skill functionally determines a language or that a language functionally determines a skill.

Neither set determines the other.

The redundancy comes from their independent combination under the same determinant.

That is why a separate MVD analysis is required.

---

## Concrete 4NF Reconstruction

The SQL implementation reconstructs the conceptual employee-skill-language combinations through:

`employee_skill JOIN employee_language`

using `employee_id` as the common determinant.

The reconstructed relation for an employee with two skills and two languages contains four combinations.

The database therefore stores the independent facts once while deriving the combinations when they are needed.

This design reduces update anomalies.

If an employee learns a new language, the language relationship is inserted once. The system does not need to update every skill-language combination for that employee.

---

## 5NF

Fifth Normal Form is concerned with **join dependencies**.

A join dependency states that a relation can be reconstructed exactly by joining several projections.

The notation can be expressed conceptually as:

`*{R1, R2, ..., Rn}`

A non-trivial join dependency can justify a decomposition even when ordinary functional and multivalued dependency analysis does not identify the redundancy.

5NF is therefore sometimes described as **Project-Join Normal Form**.

---

## Supplier-Part-Project Case Study

The C++, Java, and SQL implementations use a ternary relationship involving:

- Supplier
- Part
- Project

The potential decomposition is:

`SupplierPart(Supplier, Part)`

`SupplierProject(Supplier, Project)`

`PartProject(Part, Project)`

The critical point is that this decomposition is not automatically correct merely because the relation contains three attributes.

The decomposition is valid only if the business semantics establish that the original ternary relationship is exactly implied by those pairwise relationships.

If the three pairwise facts are independent but jointly sufficient to determine the valid supplier-part-project combinations, the join dependency supports the decomposition.

If the original ternary association contains information that cannot be derived from the pairwise relations, decomposition can produce spurious tuples.

---

## Spurious Tuples in 5NF

Suppose a supplier supplies a part and participates in a project, while the part is used in that project.

A naive join of pairwise relations may infer that the supplier supplies that part specifically for that project even if the original business rule never authorized that combination.

Therefore, 5NF requires semantic justification.

This is an important distinction from 4NF.

4NF asks whether independent multivalued facts create unnecessary combinations.

5NF asks whether a multi-way relationship can be decomposed into smaller relationships without losing the exact meaning of the original relationship.

---

## 5NF SQL Reconstruction

The PostgreSQL implementation creates:

`SupplierPart`

`SupplierProject`

`PartProject`

and reconstructs the ternary association through joins on the shared attributes.

The query:

`SupplierPart JOIN SupplierProject JOIN PartProject`

is meaningful only under the assumed join dependency.

The schema therefore treats the join dependency as a domain rule rather than as an automatic consequence of normalization.

---

## SQL Data Model

The SQL script uses PostgreSQL-compatible DDL and DML.

The BCNF portion includes:

- `student`
- `course`
- `instructor`
- `teaching_assignment`

The instructor identifier is a key in `instructor`, while the student-course pair is the key of `teaching_assignment`.

Foreign keys ensure that assignments cannot refer to nonexistent students, courses, or instructors.

The 4NF portion contains:

- `employee`
- `skill`
- `language`
- `employee_skill`
- `employee_language`

The composite primary keys model each employee-to-skill and employee-to-language relationship as a set.

The 5NF portion contains:

- `supplier`
- `part`
- `project`
- `supplier_part`
- `supplier_project`
- `part_project`

Each pairwise relation uses a composite primary key.

---

## Database-Level Integrity

Normalization does not eliminate the need for database constraints.

The SQL implementation uses primary keys to prevent duplicate relationship tuples.

Foreign keys prevent references to nonexistent parent entities.

Unique constraints are used where the domain requires uniqueness beyond the primary key.

For example, `skill_name` and `language_name` are unique because the sample domain treats those names as unique identifiers for their respective catalogs.

This illustrates an important distinction:

Normalization describes dependency structure, while database constraints enforce concrete instances of those rules.

---

## Indexing Considerations

Primary keys create useful indexes automatically in PostgreSQL.

The SQL script adds indexes on reverse relationship columns such as:

`employee_skill(skill_code)`

`employee_language(language_code)`

`supplier_part(part_id)`

`supplier_project(project_id)`

These indexes support queries that begin from the dependent side of a relationship.

Normalization can increase the number of relations and therefore increase the number of joins required by some queries. Index design becomes important after decomposition.

A normalized schema is not automatically a performant schema. Query workload, cardinality, join selectivity, and indexing strategy still matter.

---

## Python Implementation

The Python program provides the most algorithmically complete normalization engine.

It implements:

- `attribute_closure()` for functional-dependency inference
- `candidate_keys()` for candidate-key discovery
- canonical-cover processing
- BCNF violation detection
- recursive BCNF decomposition
- dependency-preservation analysis
- MVD representation
- 4NF violation detection
- 4NF decomposition
- concrete FD instance validation
- concrete MVD instance validation
- natural-join reconstruction
- concrete 5NF join reconstruction

The Python implementation uses immutable sets for dependency attributes so that determinant and dependent collections can be safely reasoned about as mathematical sets.

Its candidate-key enumeration is intentionally exhaustive. That makes the mechanism transparent for small examples but exposes an important complexity limitation: the number of possible attribute subsets grows exponentially.

---

## JavaScript Implementation

The JavaScript implementation emphasizes a complementary event-oriented and data-processing representation.

It models functional dependencies, multivalued dependencies, join dependencies, and relation schemas as JavaScript classes.

The program also demonstrates:

- set-based dependency inference
- candidate-key enumeration
- BCNF decomposition
- 4NF decomposition
- concrete natural joins
- FD instance validation
- MVD instance validation
- normalization-policy reporting

The natural-join implementation uses object rows and JSON-derived row signatures to remove duplicate tuples.

This representation is useful for understanding why a normalized relational design can reconstruct derived combinations dynamically rather than persisting every combination.

---

## C++ Case Study

The C++ implementation presents normalization as a schema-analysis engine.

`RelationSchema` represents a relation and its dependency metadata.

`FunctionalDependency`, `MultivaluedDependency`, and `JoinDependency` represent the three dependency types separately.

The program uses:

- `std::set` for mathematical attribute sets
- `std::map` for concrete relational tuples
- recursive BCNF decomposition
- exhaustive candidate-key enumeration
- concrete FD checking
- projection of rows
- natural joins
- explicit reconstruction tests

The use of ordered sets makes equality and subset testing deterministic.

The program also includes a practical warning for exhaustive candidate-key analysis: it should not be used blindly on very large attribute sets because subset enumeration has exponential growth.

---

## Java Enterprise Model

The Java implementation models normalization using immutable records and an explicit analysis report.

`FunctionalDependency`, `MultivaluedDependency`, and `JoinDependency` are records representing distinct dependency types.

`RelationSchema` represents a normalized-domain object containing attributes and dependency metadata.

`NormalizationReport` collects:

- candidate keys
- BCNF violations
- 4NF violations
- join dependencies

The Java implementation uses immutable sets to reduce accidental mutation of dependency definitions.

This is particularly useful for a rule-analysis service because dependency definitions should behave as stable domain metadata rather than mutable application state.

---

## Relationship Between the Three Normal Forms

The distinctions can be expressed compactly:

| Normal Form | Dependency Being Evaluated | Central Question |
|---|---|---|
| BCNF | Functional dependency | Is every non-trivial determinant a superkey? |
| 4NF | Multivalued dependency | Is every non-trivial MVD determinant a superkey? |
| 5NF | Join dependency | Can a valid multi-way relationship be reconstructed exactly from smaller projections? |

The progression is not simply a ranking of "more normalized" tables.

Each normal form captures a different mathematical source of redundancy.

A relation can therefore require a 4NF analysis even when its functional dependencies appear satisfactory.

Likewise, a 5NF analysis requires consideration of join dependencies that are not adequately represented by ordinary FD analysis.

---

## Common Design Mistakes

### Treating every determinant as a key

A determinant in an FD is not automatically a candidate key.

The closure of the determinant must contain the entire relation before it qualifies as a superkey.

BCNF specifically fails when a non-trivial determinant is not a superkey.

### Assuming 3NF and BCNF are identical

BCNF is stricter than 3NF.

A relation can satisfy 3NF while still containing a dependency whose determinant is not a superkey.

This is one reason BCNF decomposition can sometimes require additional analysis beyond a conventional 3NF design.

### Treating MVDs as ordinary FDs

`Employee -> Skill` means one employee has one determined skill value.

`Employee ->> Skill` means an employee has an independent set of skills relative to the other attributes.

These statements have different meanings and produce different normalization behavior.

### Splitting every multivalued attribute without checking semantics

A decomposition should represent a genuine independent multivalued fact.

If the relationship between two attributes is actually constrained by another attribute, treating them as independent can change the meaning of the data.

### Assuming every ternary relationship belongs in 5NF pairwise tables

A ternary relation does not automatically have the join dependency required for a pairwise decomposition.

The business rule must justify the reconstruction.

### Confusing losslessness with dependency preservation

A decomposition can reconstruct the original relation but still make some dependencies difficult to enforce locally.

Conversely, dependency preservation does not by itself prove that a decomposition is lossless.

Both properties must be considered independently.

---

## Performance Implications

Higher normalization can reduce redundancy, but it can also increase the number of relations involved in common queries.

BCNF decomposition may require joins between key-dependent relations.

4NF decomposition can replace one wide relation with multiple relationship tables, after which applications may need joins to reconstruct combined information.

5NF can produce several pairwise relations whose joins are more expensive than reading a single denormalized relation.

The appropriate design therefore depends on both dependency correctness and workload characteristics.

Indexes should support the join paths introduced by decomposition.

The SQL example indexes relationship columns used to traverse the normalized structures in reverse directions.

---

## Transactional Implications

Decomposition can cause one business operation to touch several relations.

For example, creating a new employee with a skill and language can require inserts into:

`employee`

`employee_skill`

`employee_language`

The SQL implementation groups those operations in a transaction.

Transactions preserve atomicity when a business operation spans multiple normalized relations.

Foreign-key enforcement also ensures that relationship rows cannot be committed with nonexistent parent entities.

---

## Security and Data Integrity

Normalization itself is not a security mechanism.

Its primary purpose is dependency correctness and reduction of redundancy.

Security still requires appropriate authorization, least-privilege database roles, transaction controls, auditing, and input validation at the application boundary.

Normalization can indirectly improve integrity by reducing the number of places where the same fact is stored.

For example, storing an instructor's office once means an office change does not require synchronized updates across every teaching assignment.

That reduces the number of opportunities for inconsistent copies of the same fact.

---

## Debugging Normalization Problems

When a schema appears to contain redundancy, identify the actual dependency rather than immediately adding or removing tables.

For BCNF, write the suspected FD and compute its determinant closure.

For 4NF, determine whether the supposed independent value sets really vary independently for the same determinant.

For 5NF, identify the proposed projections and verify whether their join is guaranteed to reproduce exactly the intended tuples.

Concrete test data is particularly valuable.

The Python, JavaScript, C++, and SQL examples all demonstrate this principle by constructing relation instances and performing joins rather than relying solely on textual descriptions of normal forms.

---

## Practical Normalization Workflow

A technically sound workflow begins with the business semantics.

Identify the attributes that belong to the relation and document the dependencies that actually hold.

Determine candidate keys using closure rather than assuming that an obvious identifier is the only key.

Evaluate non-trivial functional dependencies for BCNF.

If independent multivalued facts exist, evaluate the corresponding MVDs for 4NF.

If a multi-way relationship appears decomposable into several projections, determine whether a genuine join dependency exists before applying a 5NF decomposition.

After every decomposition, verify losslessness.

Check dependency preservation where local enforcement is important.

Finally, evaluate the resulting schema against realistic queries, indexes, transaction boundaries, and integrity constraints.

---

## Production Considerations

Normalization should be driven by actual dependencies rather than by a desire to maximize the number of tables.

A highly decomposed schema can become difficult to query if joins become excessive or if the dependency assumptions are poorly documented.

The opposite problem also occurs: keeping independent facts together can create update anomalies, duplicated values, and large numbers of unnecessary combinations.

BCNF, 4NF, and 5NF provide mathematical tools for identifying these structures.

The final database design still requires domain validation, integrity constraints, workload analysis, indexing, transaction design, and careful treatment of business rules.
