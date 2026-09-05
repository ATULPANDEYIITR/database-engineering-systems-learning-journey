# Relational Model

## 1. Introduction

The relational model is a formal approach to organizing, storing, and manipulating data using relations. In practical database systems, a relation is commonly represented as a table consisting of rows and columns.

The model was introduced by Edgar F. Codd in 1970 and became the foundation for relational database management systems such as PostgreSQL, MySQL, Oracle Database, Microsoft SQL Server, and SQLite.

The relational model provides a mathematical basis for representing data and defining operations on that data. Its central ideas include:

- Relations
- Tuples
- Attributes
- Domains
- Keys
- Integrity constraints
- Relational algebra
- Relationships between relations

A relational database separates the logical organization of data from the physical details of how that data is stored.

---

## 2. Why the Relational Model Is Important

Before relational databases became dominant, database systems commonly used hierarchical and network-oriented structures. These approaches could represent complex relationships but often required applications to understand the underlying structure of the data.

The relational model introduced a simpler logical representation.

Instead of representing information through pointers between records, data can be represented as tables.

For example:

    STUDENT
    --------------------------------
    StudentID | Name | Department
    --------------------------------
    101       | Ravi | CSE
    102       | Neha | ECE
    103       | Amit | CSE

The logical structure is easy to understand:

- Each table represents a relation.
- Each row represents a tuple.
- Each column represents an attribute.
- Each attribute has a domain.
- Keys identify tuples.
- Constraints maintain correctness.

This structure also allows users to query data without needing to know exactly where or how the database stores the records physically.

---

## 3. Mathematical Foundation

The relational model is based on concepts from set theory and predicate logic.

Suppose there are two domains:

    StudentID = {101, 102, 103}
    Name = {Ravi, Neha, Amit}

A relation can be viewed as a subset of the Cartesian product of its attribute domains.

For two domains A and B:

    A × B

represents every possible ordered pair where the first element comes from A and the second element comes from B.

If:

    A = {1, 2}
    B = {X, Y}

then:

    A × B =
    {(1, X), (1, Y), (2, X), (2, Y)}

A relation contains only selected tuples from such a Cartesian product.

This mathematical foundation is what makes relational algebra possible.

---

## 4. Relation

A relation is the fundamental structure of the relational model.

In practical database terminology, a relation is usually represented as a table.

For example:

    STUDENT
    --------------------------------
    StudentID | Name | Age
    --------------------------------
    1         | Ravi | 22
    2         | Neha | 21
    3         | Amit | 23

The relation has:

    Relation name: STUDENT

    Attributes:
    StudentID
    Name
    Age

    Tuples:
    (1, Ravi, 22)
    (2, Neha, 21)
    (3, Amit, 23)

A relation has a defined schema and a current collection of tuples.

---

## 5. Relation Schema

A relation schema defines the structure of a relation.

It specifies:

- Relation name
- Attribute names
- Domains or data types
- Structural constraints

For example:

    STUDENT(StudentID, Name, Age, Department)

This represents the schema of the STUDENT relation.

A more formal notation is:

    R(A1, A2, A3, ..., An)

where:

- R is the relation name.
- A1, A2, A3, ..., An are attributes.

For example:

    STUDENT(StudentID, Name, Age, Department)

is a relation schema with four attributes.

---

## 6. Relation Instance

A relation instance is the actual collection of tuples stored in a relation at a particular point in time.

Schema:

    STUDENT(StudentID, Name, Age)

Instance:

    StudentID | Name | Age
    -----------------------
    101       | Ravi | 22
    102       | Neha | 21

The schema usually changes less frequently.

The instance changes whenever rows are inserted, updated, or deleted.

Therefore:

    Schema = Structure

    Instance = Current data

---

## 7. Attribute

An attribute is a named property or characteristic of an entity represented in a relation.

For:

    STUDENT(StudentID, Name, Age, Department)

the attributes are:

    StudentID
    Name
    Age
    Department

In a table, attributes are represented by columns.

Each attribute has a domain that defines the set of permissible values.

---

## 8. Domain

A domain is the set of allowable values for an attribute.

For example:

    Age domain = positive integers within a reasonable range

    Gender domain = {Male, Female, Other}

    Department domain = {CSE, ECE, ME, CE}

    StudentID domain = positive integers

A domain provides semantic meaning to an attribute.

For example, if:

    Age ∈ Integer

then values such as:

    25
    30
    40

may be valid.

Values such as:

    "Delhi"
    "Computer Science"

would not belong to that domain.

Modern SQL systems implement domain restrictions primarily through data types and constraints.

---

## 9. Tuple

A tuple is an ordered collection of attribute values.

In a table, a tuple corresponds approximately to a row.

Consider:

    STUDENT
    --------------------------------
    StudentID | Name | Age
    --------------------------------
    101       | Ravi | 22
    102       | Neha | 21

The tuples are:

    (101, Ravi, 22)

    (102, Neha, 21)

The number of attributes in a tuple is called the degree of the relation.

---

## 10. Degree

The degree of a relation is the number of attributes in the relation schema.

For:

    STUDENT(StudentID, Name, Age, Department)

the degree is:

    4

because there are four attributes.

Another example:

    EMPLOYEE(EmployeeID, Name, Salary)

Degree:

    3

Degree describes the structure of a relation, not the number of rows.

---

## 11. Cardinality

The cardinality of a relation is the number of tuples in the relation.

For:

    STUDENT
    --------------------------------
    StudentID | Name | Age
    --------------------------------
    101       | Ravi | 22
    102       | Neha | 21
    103       | Amit | 23

the cardinality is:

    3

Therefore:

    Degree = Number of columns

    Cardinality = Number of rows

This distinction is important in database examinations.

---

## 12. Relation Properties

A classical relation has several important properties.

### 12.1 Atomic Values

Each attribute value should be atomic in the classical relational model.

For example:

    StudentID | Name
    ----------------
    101       | Ravi

is valid.

A value such as:

    Ravi, Neha, Amit

stored as one attribute value would violate first normal form when those values represent multiple independent values.

---

### 12.2 No Duplicate Tuples

A mathematical relation is a set of tuples.

Sets do not contain duplicate elements.

Therefore, in the classical relational model, duplicate tuples are not allowed.

SQL is slightly different because ordinary SQL query results may contain duplicate rows unless `DISTINCT` is specified.

Example:

    SELECT Department
    FROM STUDENT;

may produce:

    CSE
    CSE
    ECE

Using:

    SELECT DISTINCT Department
    FROM STUDENT;

produces unique department values.

---

### 12.3 Attribute Values Come From Domains

Each attribute value must belong to its associated domain.

For example:

    Age = 25

may be valid.

    Age = "Computer Science"

would generally be invalid.

---

### 12.4 Attribute Names Are Unique Within a Relation

A relation schema should identify its attributes unambiguously.

For example:

    STUDENT(StudentID, Name, Age)

contains uniquely named attributes.

When multiple relations are joined, qualified names or aliases may be needed to distinguish attributes with the same name.

---

### 12.5 Ordering of Tuples Is Not Significant

In the mathematical relational model, the order of tuples does not matter.

These represent the same relation:

    (1, Ravi)
    (2, Neha)

and:

    (2, Neha)
    (1, Ravi)

Physical databases may return rows in different orders unless an explicit `ORDER BY` is used.

---

### 12.6 Ordering of Attributes Is Conceptually Defined by the Schema

The schema associates each attribute with its domain.

Although SQL displays columns in a defined order, the logical identity of an attribute comes from its name and meaning rather than its physical position.

---

## 13. Relational Schema vs Relation Instance

These two concepts must not be confused.

Schema:

    STUDENT(StudentID, Name, Age)

Instance:

    StudentID | Name | Age
    -----------------------
    101       | Ravi | 22
    102       | Neha | 21

The schema defines what the relation looks like.

The instance represents the actual tuples currently stored.

If another student is inserted, the schema remains unchanged while the instance changes.

---

## 14. Database Schema

A database schema is the logical structure of an entire database.

Suppose a university database contains:

    STUDENT(StudentID, Name, Department)

    COURSE(CourseID, CourseName, Credits)

    ENROLLMENT(StudentID, CourseID, Semester, Grade)

Together these relation schemas form part of the database schema.

The database schema can include:

- Relations
- Attributes
- Data types
- Keys
- Foreign keys
- Constraints
- Views
- Indexes
- Other database objects

---

## 15. Database Instance

A database instance is the actual state of all data in a database at a particular moment.

If a database contains 5,000 students today and 5,100 students next month, the database schema may remain the same while the database instance changes.

This distinction is fundamental:

    Database Schema = Definition

    Database Instance = Current state

---

## 16. Keys

Keys are used to identify tuples and establish relationships between relations.

Important types of keys include:

- Super key
- Candidate key
- Primary key
- Alternate key
- Foreign key
- Composite key

Understanding the differences between these concepts is essential.

---

## 17. Super Key

A super key is a set of one or more attributes that can uniquely identify a tuple.

Consider:

    STUDENT(StudentID, Name, Email, Department)

Suppose StudentID and Email are both unique.

Possible super keys include:

    {StudentID}

    {Email}

    {StudentID, Name}

    {StudentID, Department}

    {StudentID, Email}

All of these can uniquely identify a student if StudentID is already unique.

A super key does not have to be minimal.

---

## 18. Candidate Key

A candidate key is a minimal super key.

Minimal means that no attribute can be removed while preserving uniqueness.

If:

    StudentID

uniquely identifies every student, then:

    {StudentID}

is a candidate key.

If:

    Email

also uniquely identifies every student, then:

    {Email}

is another candidate key.

But:

    {StudentID, Name}

is not a candidate key because StudentID alone is sufficient.

---

## 19. Primary Key

A primary key is the candidate key selected to uniquely identify tuples in a relation.

Example:

    STUDENT(
        StudentID PRIMARY KEY,
        Name,
        Department
    )

The primary key should provide unique identification of each row.

A primary key normally cannot contain NULL values.

---

## 20. Alternate Key

Candidate keys that are not selected as the primary key are called alternate keys.

Suppose:

    StudentID
    Email

are both candidate keys.

If StudentID is selected as the primary key, Email becomes an alternate key.

In SQL, an alternate key is commonly enforced with a `UNIQUE` constraint.

---

## 21. Composite Key

A composite key consists of more than one attribute.

Consider:

    ENROLLMENT(StudentID, CourseID, Semester, Grade)

A student can enroll in multiple courses.

A course can contain multiple students.

Suppose the combination:

    StudentID + CourseID

uniquely identifies an enrollment.

Then:

    (StudentID, CourseID)

is a composite candidate key.

Example:

    StudentID | CourseID | Grade
    ----------------------------
    101       | CS101    | A
    101       | CS102    | B
    102       | CS101    | A

StudentID alone is not unique.

CourseID alone is not unique.

Together they may uniquely identify the relationship.

---

## 22. Foreign Key

A foreign key is an attribute or set of attributes in one relation that references a candidate key, typically the primary key, of another relation.

Example:

    DEPARTMENT(DepartmentID, DepartmentName)

    STUDENT(StudentID, Name, DepartmentID)

Here:

    DEPARTMENT.DepartmentID

is the referenced key.

    STUDENT.DepartmentID

is the foreign key.

The foreign key represents a relationship between students and departments.

---

## 23. Referential Integrity

Referential integrity ensures that a foreign-key value corresponds to an existing referenced key value, subject to the behavior defined by the database system and constraint actions.

Suppose:

    DEPARTMENT
    ------------
    D1
    D2

and:

    STUDENT
    ----------------
    StudentID | DepartmentID
    -------------------------
    101       | D1
    102       | D2

A student should not normally reference:

    D9

if D9 does not exist in DEPARTMENT.

This prevents orphan references.

---

## 24. Integrity Constraints

Integrity constraints maintain correctness and consistency of database data.

Major categories include:

- Domain constraints
- Key constraints
- Entity integrity
- Referential integrity
- General semantic constraints

---

## 25. Domain Constraint

A domain constraint ensures that attribute values come from valid domains.

For example:

    Age INTEGER

restricts the type of value that can be stored.

A more restrictive SQL definition could be:

    Age INTEGER CHECK (Age >= 0)

This prevents negative ages.

---

## 26. Entity Integrity

Entity integrity states that the primary key of a relation cannot contain NULL values.

The reason is straightforward.

A primary key must uniquely identify a tuple.

A NULL value represents an unknown or missing value and cannot serve as a reliable identifier.

Example:

    StudentID PRIMARY KEY

must have a value for every row.

---

## 27. Referential Integrity Constraint

Referential integrity applies to foreign keys.

Example:

    STUDENT.DepartmentID

references:

    DEPARTMENT.DepartmentID

The database should prevent a student from referencing a department that does not exist unless the operation is handled through an explicitly defined referential action.

---

## 28. General Constraints

Databases can also enforce business rules.

Examples:

    Salary > 0

    Credits BETWEEN 1 AND 10

    Age >= 18

    StartDate <= EndDate

SQL can implement many such restrictions using `CHECK`, `UNIQUE`, `NOT NULL`, foreign keys, and other mechanisms.

---

## 29. NULL

NULL represents the absence of a known value.

It does not necessarily mean:

- Zero
- Empty string
- False
- Unknown in every possible semantic situation

NULL introduces three-valued logic in SQL:

    TRUE
    FALSE
    UNKNOWN

For example:

    WHERE Salary = NULL

does not correctly test for NULL.

Instead:

    WHERE Salary IS NULL

should be used.

---

## 30. SQL and the Classical Relational Model

SQL is based on the relational model but is not identical to the classical mathematical model.

Important differences include:

- SQL permits duplicate rows in ordinary query results.
- SQL supports NULL.
- SQL has three-valued logic.
- SQL supports ordering through `ORDER BY`.
- SQL provides additional features beyond pure relational algebra.
- SQL tables can have implementation-specific physical behavior.

Therefore:

    Relational Model ≠ SQL

but SQL is strongly influenced by relational concepts.

---

## 31. Relational Algebra

Relational algebra is a formal query language for relational databases.

It defines operations that take relations as input and produce relations as output.

Important operations include:

- Selection
- Projection
- Union
- Set difference
- Cartesian product
- Rename
- Join

Relational algebra provides the theoretical foundation for many database query-processing concepts.

---

## 32. Selection

Selection chooses tuples satisfying a condition.

Symbol:

    σ

Suppose:

    STUDENT(StudentID, Name, Age, Department)

To select students older than 21:

    σ Age > 21 (STUDENT)

If the table contains:

    101 | Ravi | 22 | CSE
    102 | Neha | 20 | ECE
    103 | Amit | 23 | CSE

the result is:

    101 | Ravi | 22 | CSE
    103 | Amit | 23 | CSE

Selection filters rows.

SQL equivalent:

    SELECT *
    FROM STUDENT
    WHERE Age > 21;

---

## 33. Projection

Projection selects specific attributes.

Symbol:

    π

Example:

    π Name, Department (STUDENT)

returns only:

    Name
    Department

SQL equivalent:

    SELECT Name, Department
    FROM STUDENT;

Projection primarily reduces the number of columns.

---

## 34. Selection vs Projection

This distinction is frequently tested.

Selection:

    Filters rows.

Projection:

    Selects columns.

Example:

    σ Age > 21 (STUDENT)

means:

    Keep rows where Age > 21.

Example:

    π Name, Age (STUDENT)

means:

    Keep only Name and Age columns.

Memory aid:

    Selection = Rows

    Projection = Columns

---

## 35. Union

Union combines tuples from two union-compatible relations.

Symbol:

    ∪

For:

    R ∪ S

R and S must have compatible schemas.

Union compatibility generally requires:

- Same number of attributes
- Corresponding attributes with compatible domains

Example:

    CSE_STUDENTS
    ------------
    101
    102

    ECE_STUDENTS
    ------------
    103
    104

Then:

    CSE_STUDENTS ∪ ECE_STUDENTS

produces:

    101
    102
    103
    104

Duplicate tuples are eliminated in classical set-based relational algebra.

---

## 36. Set Difference

Set difference returns tuples present in one relation but not another.

Symbol:

    −

Example:

    R − S

means:

    Tuples in R that are not in S.

If:

    R = {1, 2, 3}

    S = {2, 3, 4}

then:

    R − S = {1}

---

## 37. Intersection

Intersection returns tuples common to both relations.

Symbol:

    ∩

If:

    R = {1, 2, 3}

    S = {2, 3, 4}

then:

    R ∩ S = {2, 3}

Intersection can also be expressed using other relational operations in classical relational algebra.

---

## 38. Cartesian Product

Cartesian product combines every tuple of one relation with every tuple of another.

Symbol:

    ×

If R contains 2 tuples and S contains 3 tuples:

    |R × S| = 2 × 3 = 6

Example:

    STUDENT
    -------
    101
    102

    COURSE
    ------
    C1
    C2
    C3

Then:

    STUDENT × COURSE

produces six combinations.

Cartesian products can become extremely large, which is one reason joins are usually preferred when a meaningful relationship exists.

---

## 39. Rename

Rename changes the name of a relation or its attributes in relational algebra.

Symbol:

    ρ

Example:

    ρ S(STUDENT)

renames STUDENT as S.

Rename is particularly useful when a relation is referenced multiple times, such as in a self-join.

---

## 40. Join

A join combines related tuples from two relations.

Joins are among the most important operations in relational databases.

Common types include:

- Theta join
- Equi-join
- Natural join
- Inner join
- Outer joins
- Self join

---

## 41. Theta Join

A theta join combines tuples according to a specified comparison condition.

Conditions can include:

    =
    <
    >
    <=
    >=
    !=

Example:

    R ⋈ condition S

A theta join can be viewed conceptually as a selection over a Cartesian product:

    R ⋈condition S
    =
    σcondition(R × S)

---

## 42. Equi-Join

An equi-join is a theta join using equality.

Example:

    STUDENT.DepartmentID = DEPARTMENT.DepartmentID

The matching rows are combined.

SQL example:

    SELECT *
    FROM STUDENT S
    JOIN DEPARTMENT D
      ON S.DepartmentID = D.DepartmentID;

---

## 43. Natural Join

A natural join automatically joins relations using attributes with the same name and compatible domains.

Suppose:

    STUDENT(StudentID, Name, DepartmentID)

    DEPARTMENT(DepartmentID, DepartmentName)

A natural join can match:

    DepartmentID

and produce a combined relation.

Natural joins are convenient but can be risky in practical systems because adding a same-named column can unintentionally change the join behavior.

Explicit join conditions are often clearer.

---

## 44. Inner Join

An inner join returns only matching tuples.

Example:

    STUDENT
    -----------------------
    StudentID | DepartmentID
    -----------------------
    101       | D1
    102       | D2

    DEPARTMENT
    -----------------------
    DepartmentID | Name
    -----------------------
    D1           | CSE

An inner join produces only the student associated with D1.

SQL:

    SELECT S.StudentID, S.DepartmentID, D.Name
    FROM STUDENT S
    INNER JOIN DEPARTMENT D
        ON S.DepartmentID = D.DepartmentID;

---

## 45. Left Outer Join

A left outer join returns all rows from the left relation and matching rows from the right relation.

If no matching right-side row exists, right-side columns may contain NULL.

SQL:

    SELECT *
    FROM STUDENT S
    LEFT JOIN DEPARTMENT D
        ON S.DepartmentID = D.DepartmentID;

This is useful when the requirement is:

    Return every student, even if department information is missing.

---

## 46. Right Outer Join

A right outer join returns all rows from the right relation and matching rows from the left relation.

Example:

    SELECT *
    FROM STUDENT S
    RIGHT JOIN DEPARTMENT D
        ON S.DepartmentID = D.DepartmentID;

This can show every department, including departments with no students.

---

## 47. Full Outer Join

A full outer join returns:

- Matching rows
- Unmatched rows from the left relation
- Unmatched rows from the right relation

Missing values on either side are represented by NULL.

Conceptually:

    FULL OUTER JOIN
    =
    Left outer join + right outer join behavior

subject to SQL implementation details.

---

## 48. Self Join

A self join joins a relation with itself.

Consider:

    EMPLOYEE(EmployeeID, Name, ManagerID)

ManagerID references another employee.

A self join can connect employees with their managers.

SQL:

    SELECT E.Name AS Employee,
           M.Name AS Manager
    FROM EMPLOYEE E
    LEFT JOIN EMPLOYEE M
      ON E.ManagerID = M.EmployeeID;

The same table is used twice with different aliases.

---

## 49. Relational Division

Relational division is a relational algebra operation useful for queries involving "for all" conditions.

Suppose:

    ENROLLMENT(StudentID, CourseID)

and:

    REQUIRED(CourseID)

A division operation can identify students who have enrolled in every required course.

This type of operation is more difficult to express directly in SQL but can often be implemented using combinations of:

- `GROUP BY`
- `HAVING`
- `NOT EXISTS`
- Nested queries

Relational division is important conceptually because it demonstrates how relational algebra can express universal conditions.

---

## 50. Functional Dependency

A functional dependency describes a relationship between attributes.

It is written as:

    X → Y

and means:

    If two tuples agree on X, they must also agree on Y.

For example:

    StudentID → StudentName

means a given StudentID determines exactly one StudentName.

If:

    101 → Ravi

then another tuple with StudentID 101 should not have a different student name.

Functional dependencies are central to:

- Key identification
- Normalization
- Schema design
- Anomaly prevention

---

## 51. Trivial Functional Dependency

A functional dependency:

    X → Y

is trivial if:

    Y ⊆ X

Example:

    {StudentID, Name} → StudentID

is trivial because StudentID is already part of the left-hand side.

---

## 52. Non-Trivial Functional Dependency

A functional dependency is non-trivial if:

    Y is not a subset of X

Example:

    StudentID → Name

assuming StudentID determines Name.

This is non-trivial because Name is not part of StudentID.

---

## 53. Full Functional Dependency

An attribute is fully functionally dependent on a composite key if it depends on the entire key and not on a proper subset of the key.

Suppose:

    ENROLLMENT(StudentID, CourseID, Grade)

and:

    (StudentID, CourseID) → Grade

If neither:

    StudentID → Grade

nor:

    CourseID → Grade

is true, Grade is fully functionally dependent on the composite key.

This concept is important in second normal form.

---

## 54. Partial Dependency

A partial dependency occurs when a non-key attribute depends on only part of a composite candidate key.

Example:

    ENROLLMENT(StudentID, CourseID, StudentName)

Suppose:

    (StudentID, CourseID) → StudentName

but:

    StudentID → StudentName

also holds.

Then StudentName depends only on part of the composite key.

This creates a partial dependency.

---

## 55. Transitive Dependency

A transitive dependency occurs when a non-key attribute depends on another non-key attribute through a key.

Example:

    StudentID → DepartmentID

    DepartmentID → DepartmentName

Therefore:

    StudentID → DepartmentName

DepartmentName is transitively dependent on StudentID through DepartmentID.

Transitive dependencies are important when analyzing third normal form.

---

## 56. Normalization

Normalization is a systematic process of organizing relations to reduce redundancy and prevent anomalies.

Common normal forms include:

- First Normal Form
- Second Normal Form
- Third Normal Form
- Boyce-Codd Normal Form
- Fourth Normal Form
- Fifth Normal Form

Normalization primarily uses functional dependencies and keys.

---

## 57. First Normal Form

A relation is in first normal form when attribute values are atomic and repeating groups are eliminated.

Poor design:

    STUDENT
    --------------------------------
    StudentID | Name | PhoneNumbers
    --------------------------------
    101       | Ravi | 9999, 8888

A normalized design might be:

    STUDENT
    ----------------
    StudentID | Name

    STUDENT_PHONE
    ----------------------
    StudentID | Phone

This represents multiple phone numbers as separate tuples.

---

## 58. Second Normal Form

A relation is in second normal form if:

1. It is in first normal form.
2. Every non-prime attribute is fully functionally dependent on every candidate key.

Second normal form primarily addresses partial dependency.

Example:

    ENROLLMENT(
        StudentID,
        CourseID,
        StudentName,
        CourseName,
        Grade
    )

Suppose:

    StudentID → StudentName

    CourseID → CourseName

    (StudentID, CourseID) → Grade

Then StudentName and CourseName depend only on parts of the composite key.

The relation violates 2NF.

It can be decomposed into:

    STUDENT(StudentID, StudentName)

    COURSE(CourseID, CourseName)

    ENROLLMENT(StudentID, CourseID, Grade)

---

## 59. Third Normal Form

A relation is in third normal form if it is in 2NF and has no problematic transitive dependency of non-prime attributes on candidate keys.

Consider:

    STUDENT(StudentID, StudentName, DepartmentID, DepartmentName)

Suppose:

    StudentID → DepartmentID

    DepartmentID → DepartmentName

Then:

    StudentID → DepartmentName

through DepartmentID.

A decomposition can be:

    STUDENT(StudentID, StudentName, DepartmentID)

    DEPARTMENT(DepartmentID, DepartmentName)

---

## 60. Boyce-Codd Normal Form

A relation is in BCNF if, for every non-trivial functional dependency:

    X → Y

X is a super key.

BCNF is stricter than 3NF.

A relation can satisfy 3NF but fail BCNF in certain dependency structures.

BCNF is important when more aggressive removal of redundancy is required.

---

## 61. Lossless Decomposition

When a relation is decomposed into multiple relations, a lossless decomposition allows the original relation to be reconstructed without introducing incorrect tuples or losing valid information.

For example:

    R(A, B, C)

may be decomposed into:

    R1(A, B)

    R2(A, C)

The decomposition must be analyzed using the functional dependencies to determine whether it is lossless.

Lossless decomposition is a major requirement in normalization.

---

## 62. Dependency Preservation

A decomposition is dependency preserving if all relevant functional dependencies can be enforced by checking the decomposed relations without requiring expensive joins.

A decomposition may be lossless but not dependency preserving.

Database design often attempts to achieve:

- Lossless decomposition
- Dependency preservation
- Appropriate normal form

These objectives can sometimes conflict.

---

## 63. Update Anomalies

Poorly designed relations can create anomalies.

The major types are:

- Insertion anomaly
- Update anomaly
- Deletion anomaly

---

## 64. Insertion Anomaly

An insertion anomaly occurs when a new fact cannot be inserted without introducing unrelated information.

Example:

    COURSE_ENROLLMENT
    --------------------------------
    StudentID | StudentName | Course
    --------------------------------

If a course exists but no student has enrolled yet, it may be difficult to represent the course without creating an artificial student record.

Separating COURSE and STUDENT-related information can solve this problem.

---

## 65. Update Anomaly

An update anomaly occurs when the same fact is stored multiple times and all copies must be updated consistently.

Example:

    StudentID | DepartmentID | DepartmentName

If CSE appears in 1,000 rows and its name changes, every relevant row may need updating.

A separate DEPARTMENT relation avoids unnecessary duplication.

---

## 66. Deletion Anomaly

A deletion anomaly occurs when deleting one fact unintentionally removes another important fact.

Example:

If the only student enrolled in a course is deleted, a poorly designed table might also lose the only stored information about that course.

Normalization separates independent facts into appropriate relations.

---

## 67. Denormalization

Denormalization intentionally introduces redundancy to improve performance or simplify access patterns.

It can be useful when:

- Read performance is critical.
- Joins are expensive.
- Data is mostly read rather than modified.
- Reporting workloads dominate.
- Aggregated values are frequently requested.

Trade-offs include:

- More storage
- More complicated updates
- Potential inconsistency
- Greater maintenance requirements

Denormalization should be deliberate rather than accidental.

---

## 68. Relational Database Management System

A relational database management system implements relational database concepts and provides mechanisms for:

- Data definition
- Data manipulation
- Query processing
- Transaction management
- Concurrency control
- Security
- Recovery
- Integrity enforcement

Examples include:

- PostgreSQL
- MySQL
- Oracle Database
- Microsoft SQL Server
- SQLite

Although these systems are relational, their features and implementation details differ.

---

## 69. SQL

SQL is the dominant language used to interact with relational databases.

Major SQL categories include:

### DDL

Data Definition Language.

Examples:

    CREATE
    ALTER
    DROP
    TRUNCATE

### DML

Data Manipulation Language.

Examples:

    INSERT
    UPDATE
    DELETE

### DQL

Data Query Language is commonly used as a practical classification for:

    SELECT

### DCL

Data Control Language.

Examples:

    GRANT
    REVOKE

### TCL

Transaction Control Language.

Examples:

    COMMIT
    ROLLBACK
    SAVEPOINT

These classifications are commonly used for learning SQL, although terminology can vary between educational sources.

---

## 70. Creating a Relation in SQL

Example:

    CREATE TABLE STUDENT (
        StudentID INTEGER PRIMARY KEY,
        Name VARCHAR(100) NOT NULL,
        Age INTEGER CHECK (Age >= 0),
        DepartmentID INTEGER
    );

This defines a relational table.

The database system also creates internal metadata describing the table.

---

## 71. Inserting Tuples

Example:

    INSERT INTO STUDENT
        (StudentID, Name, Age, DepartmentID)
    VALUES
        (101, 'Ravi', 22, 10);

Multiple tuples can be inserted:

    INSERT INTO STUDENT
        (StudentID, Name, Age, DepartmentID)
    VALUES
        (102, 'Neha', 21, 20),
        (103, 'Amit', 23, 10);

---

## 72. Selecting Data

Basic query:

    SELECT *
    FROM STUDENT;

Selecting particular attributes:

    SELECT Name, Age
    FROM STUDENT;

Filtering:

    SELECT Name
    FROM STUDENT
    WHERE Age > 21;

---

## 73. Updating Data

Example:

    UPDATE STUDENT
    SET Age = 23
    WHERE StudentID = 101;

The WHERE clause is important.

Without a WHERE clause:

    UPDATE STUDENT
    SET Age = 23;

all rows may be modified.

This is a common operational mistake.

---

## 74. Deleting Data

Example:

    DELETE FROM STUDENT
    WHERE StudentID = 101;

Without a WHERE clause:

    DELETE FROM STUDENT;

may delete every row from the table.

Production systems should use particular care with destructive statements.

---

## 75. Transactions

A transaction is a logical unit of database work.

Typical transaction operations include:

    BEGIN;

    UPDATE ...

    INSERT ...

    COMMIT;

If something goes wrong:

    ROLLBACK;

Transactions are important when multiple operations must succeed or fail together.

---

## 76. ACID Properties

Relational database transactions are commonly described using ACID.

### Atomicity

A transaction is treated as a unit.

Either all required operations occur or the transaction is rolled back.

### Consistency

A transaction should preserve defined integrity constraints.

### Isolation

Concurrent transactions should behave according to the database's isolation guarantees.

### Durability

Committed changes should survive failures according to the database's durability mechanisms.

---

## 77. Concurrency Control

Multiple users or applications can access a relational database simultaneously.

Concurrency control helps maintain correctness when transactions overlap.

Common concepts include:

- Locks
- Shared locks
- Exclusive locks
- Isolation levels
- Deadlocks
- MVCC
- Serializable execution

Different database systems implement these mechanisms differently.

---

## 78. Isolation Levels

Common SQL transaction isolation levels include:

- Read Uncommitted
- Read Committed
- Repeatable Read
- Serializable

Some systems also implement additional behavior or terminology.

Higher isolation can reduce certain concurrency anomalies but may reduce concurrency or increase contention.

---

## 79. Indexes

An index is a data structure that helps the database locate rows efficiently.

Example:

    CREATE INDEX idx_student_name
    ON STUDENT(Name);

Indexes can improve queries such as:

    SELECT *
    FROM STUDENT
    WHERE Name = 'Ravi';

Indexes are not free.

They require:

- Additional storage
- Maintenance during inserts
- Maintenance during updates
- Maintenance during deletes
- Query-planning considerations

Too many indexes can hurt write performance.

---

## 80. Query Optimization

A database optimizer determines an execution strategy for a query.

For example, for:

    SELECT *
    FROM STUDENT
    WHERE StudentID = 101;

the optimizer may choose an index lookup if an appropriate index exists.

For a join:

    STUDENT JOIN DEPARTMENT

the optimizer may consider different join algorithms and access paths.

Common join algorithms include:

- Nested-loop join
- Hash join
- Merge join

The optimal strategy depends on data size, statistics, indexes, predicates, available memory, and database implementation.

---

## 81. Physical Data Independence

Physical data independence means changes to physical storage should not require changes to the logical schema or application programs.

Examples include:

- Changing indexes
- Changing storage layout
- Changing file organization
- Changing certain partitioning strategies

Applications should ideally continue to work without modification.

---

## 82. Logical Data Independence

Logical data independence means certain changes to the logical schema should not require changes to external views or application programs.

Examples can include adding attributes or restructuring relations in ways that preserve required external interfaces.

Logical data independence is generally harder to achieve than physical data independence.

---

## 83. Views

A view is a virtual relation defined by a query.

Example:

    CREATE VIEW CSE_STUDENTS AS
    SELECT StudentID, Name
    FROM STUDENT
    WHERE DepartmentID = 10;

The view provides a logical interface over the underlying tables.

Views can help with:

- Security
- Abstraction
- Reusability
- Simplifying complex queries

---

## 84. Security in the Relational Model

Database security controls who can access which data and what operations they can perform.

Common mechanisms include:

- Authentication
- Authorization
- Roles
- Privileges
- Views
- Row-level security
- Encryption
- Auditing

A principle of least privilege should be applied.

Applications should receive only the permissions they actually require.

---

## 85. SQL Injection

Applications should not construct SQL by directly concatenating untrusted input.

Unsafe pattern:

    query = "SELECT * FROM users WHERE name = '" + user_input + "'"

This can allow malicious input to alter the intended SQL statement.

Parameterized queries should be used instead.

For example, application frameworks typically provide parameter binding such as:

    SELECT *
    FROM users
    WHERE name = ?

The exact syntax depends on the database driver.

---

## 86. Referential Actions

Foreign keys can specify actions when referenced rows are updated or deleted.

Common actions include:

    CASCADE
    SET NULL
    SET DEFAULT
    RESTRICT
    NO ACTION

For example:

    FOREIGN KEY (DepartmentID)
    REFERENCES DEPARTMENT(DepartmentID)
    ON DELETE CASCADE

means deleting a department may cause related rows to be deleted, depending on the database implementation and constraint behavior.

Cascade actions should be used carefully because a single deletion can affect many rows.

---

## 87. Relational Model and Entity-Relationship Model

The Entity-Relationship model is often used during conceptual database design.

The relational model represents the resulting logical structure using relations.

A common design process is:

    Requirements
         ↓
    Entity-Relationship Model
         ↓
    Relational Schema
         ↓
    Normalization
         ↓
    Physical Database Design
         ↓
    Implementation

An ER model focuses on entities, attributes, and relationships.

The relational model focuses on relations, attributes, tuples, keys, and constraints.

---

## 88. Mapping ER Concepts to Relations

An entity set commonly becomes a relation.

Example:

    ENTITY: STUDENT

becomes:

    STUDENT(StudentID, Name, Age)

A 1:N relationship can commonly be represented using a foreign key on the N-side.

For example:

    DEPARTMENT(DepartmentID, Name)

    STUDENT(StudentID, Name, DepartmentID)

A many-to-many relationship commonly requires an associative relation.

Example:

    STUDENT(StudentID, Name)

    COURSE(CourseID, Name)

    ENROLLMENT(StudentID, CourseID)

---

## 89. One-to-One Relationship

Suppose:

    PERSON(PersonID, Name)

    PASSPORT(PassportID, PersonID)

If each person has at most one passport and each passport belongs to at most one person, a unique constraint on the foreign key can enforce the one-to-one relationship.

Example concept:

    PassportID PRIMARY KEY
    PersonID UNIQUE
    PersonID REFERENCES PERSON(PersonID)

---

## 90. One-to-Many Relationship

Example:

    DEPARTMENT(DepartmentID, DepartmentName)

    EMPLOYEE(EmployeeID, Name, DepartmentID)

One department can have many employees.

The foreign key is stored in EMPLOYEE:

    Employee.DepartmentID
        →
    Department.DepartmentID

---

## 91. Many-to-Many Relationship

Suppose:

- Students can take many courses.
- Courses can have many students.

A direct foreign key in either STUDENT or COURSE is insufficient.

An associative relation is needed:

    ENROLLMENT(
        StudentID,
        CourseID,
        Semester,
        Grade
    )

The combination:

    StudentID + CourseID + Semester

may serve as a candidate key if the business rules allow a student to take the same course only once per semester.

---

## 92. Relational Algebra and SQL Comparison

Selection:

    σ Age > 21 (STUDENT)

SQL:

    SELECT *
    FROM STUDENT
    WHERE Age > 21;

Projection:

    π Name, Age (STUDENT)

SQL:

    SELECT Name, Age
    FROM STUDENT;

Join:

    STUDENT ⋈ STUDENT.DepartmentID = DEPARTMENT.DepartmentID DEPARTMENT

SQL:

    SELECT *
    FROM STUDENT
    JOIN DEPARTMENT
      ON STUDENT.DepartmentID = DEPARTMENT.DepartmentID;

The correspondence is conceptual because SQL contains features beyond classical relational algebra.

---

## 93. Set Operations in SQL

SQL provides:

    UNION
    UNION ALL
    INTERSECT
    EXCEPT

Example:

    SELECT StudentID
    FROM CSE_STUDENTS

    UNION

    SELECT StudentID
    FROM ECE_STUDENTS;

`UNION` generally removes duplicate results.

`UNION ALL` preserves duplicates and can therefore be faster because duplicate elimination is not required.

---

## 94. Aggregation

Relational systems support aggregation functions such as:

    COUNT
    SUM
    AVG
    MIN
    MAX

Example:

    SELECT DepartmentID, COUNT(*)
    FROM STUDENT
    GROUP BY DepartmentID;

This produces the number of students per department.

Aggregation extends beyond the basic classical relational algebra operations commonly taught in introductory database theory.

---

## 95. GROUP BY and HAVING

`GROUP BY` creates groups.

Example:

    SELECT DepartmentID, COUNT(*)
    FROM STUDENT
    GROUP BY DepartmentID;

`HAVING` filters groups.

Example:

    SELECT DepartmentID, COUNT(*)
    FROM STUDENT
    GROUP BY DepartmentID
    HAVING COUNT(*) > 10;

A useful distinction is:

    WHERE → filters rows before grouping

    HAVING → filters groups after grouping

---

## 96. Common Mistakes

### Mistake 1: Confusing Degree and Cardinality

Incorrect:

    Degree = Number of rows

Correct:

    Degree = Number of attributes

    Cardinality = Number of tuples

---

### Mistake 2: Confusing Selection and Projection

Incorrect:

    Selection selects columns.

Correct:

    Selection filters tuples.

    Projection selects attributes.

---

### Mistake 3: Assuming Every Super Key Is a Candidate Key

A candidate key must be minimal.

If:

    {StudentID}

is already unique, then:

    {StudentID, Name}

is a super key but not a candidate key.

---

### Mistake 4: Treating a Foreign Key as Necessarily Unique

A foreign key generally does not have to be unique.

For example:

    DepartmentID

can occur in many STUDENT rows.

---

### Mistake 5: Assuming NULL Equals Zero

NULL is not zero.

It represents the absence of a value and participates in SQL's three-valued logic.

---

### Mistake 6: Using Equality to Test NULL

Incorrect:

    WHERE Age = NULL

Correct:

    WHERE Age IS NULL

---

### Mistake 7: Forgetting Composite Keys

A relationship table may require multiple attributes to uniquely identify a tuple.

---

### Mistake 8: Assuming SQL Tables Always Behave Like Mathematical Sets

Ordinary SQL query results may contain duplicates.

Use:

    DISTINCT

when duplicate elimination is required.

---

### Mistake 9: Using Natural Joins Without Understanding Column Names

A natural join can join on every same-named compatible attribute.

Explicit join predicates are often safer and clearer.

---

### Mistake 10: Ignoring Functional Dependencies During Normalization

Normalization should be based on dependencies and keys, not merely on visual inspection of tables.

---

## 97. Advantages of the Relational Model

Major advantages include:

- Simple tabular representation
- Strong mathematical foundation
- Powerful query capabilities
- Data independence
- Integrity constraints
- Standardized SQL interfaces
- Mature transaction support
- Mature security mechanisms
- Broad tooling ecosystem
- Flexible data retrieval

The relational model is particularly effective for structured data with well-defined relationships and consistency requirements.

---

## 98. Limitations of the Relational Model

Potential limitations include:

- Complex joins can become expensive.
- Highly normalized schemas can require many joins.
- Object-oriented structures may require additional mapping.
- Unstructured or rapidly changing data may be awkward to model.
- Large-scale distributed workloads can require specialized architectural techniques.
- Schema changes may require careful migration planning.

These limitations do not make relational databases unsuitable. They indicate that database technology should be selected according to workload requirements.

---

## 99. Relational Model vs NoSQL

Relational databases generally emphasize:

- Structured schemas
- Relationships
- SQL
- Transactions
- Strong integrity constraints
- Consistency guarantees

NoSQL systems may emphasize:

- Flexible schemas
- Horizontal scalability
- Specialized access patterns
- Document, key-value, column-family, or graph models

The choice should depend on:

- Data structure
- Query patterns
- Consistency requirements
- Scale
- Operational requirements
- Transaction requirements
- Team expertise

The relational model remains appropriate for a very large range of production systems.

---

## 100. Practical Example

Consider a university database.

### STUDENT

    StudentID | Name  | DepartmentID
    --------------------------------
    101       | Ravi  | D1
    102       | Neha  | D2
    103       | Amit  | D1

### DEPARTMENT

    DepartmentID | DepartmentName
    -----------------------------
    D1           | Computer Science
    D2           | Electronics

### COURSE

    CourseID | CourseName
    ---------------------
    C101     | Database Systems
    C102     | Operating Systems

### ENROLLMENT

    StudentID | CourseID | Grade
    ----------------------------
    101       | C101     | A
    101       | C102     | B
    102       | C101     | A
    103       | C101     | B

Relationships:

    STUDENT.DepartmentID
        →
    DEPARTMENT.DepartmentID

and:

    ENROLLMENT.StudentID
        →
    STUDENT.StudentID

    ENROLLMENT.CourseID
        →
    COURSE.CourseID

This design separates independent facts and represents relationships explicitly.

---

## 101. Example SQL Schema

    CREATE TABLE DEPARTMENT (
        DepartmentID VARCHAR(10) PRIMARY KEY,
        DepartmentName VARCHAR(100) NOT NULL UNIQUE
    );

    CREATE TABLE STUDENT (
        StudentID INTEGER PRIMARY KEY,
        Name VARCHAR(100) NOT NULL,
        DepartmentID VARCHAR(10),
        FOREIGN KEY (DepartmentID)
            REFERENCES DEPARTMENT(DepartmentID)
    );

    CREATE TABLE COURSE (
        CourseID VARCHAR(10) PRIMARY KEY,
        CourseName VARCHAR(100) NOT NULL
    );

    CREATE TABLE ENROLLMENT (
        StudentID INTEGER,
        CourseID VARCHAR(10),
        Grade VARCHAR(2),
        PRIMARY KEY (StudentID, CourseID),
        FOREIGN KEY (StudentID)
            REFERENCES STUDENT(StudentID),
        FOREIGN KEY (CourseID)
            REFERENCES COURSE(CourseID)
    );

This example demonstrates:

- Primary keys
- Foreign keys
- Composite keys
- Entity relationships
- Referential integrity
- Unique constraints
- Not-null constraints

---

## 102. Example Queries

Find all CSE students:

    SELECT S.StudentID, S.Name
    FROM STUDENT S
    JOIN DEPARTMENT D
      ON S.DepartmentID = D.DepartmentID
    WHERE D.DepartmentName = 'Computer Science';

Find courses taken by Ravi:

    SELECT C.CourseID, C.CourseName, E.Grade
    FROM STUDENT S
    JOIN ENROLLMENT E
      ON S.StudentID = E.StudentID
    JOIN COURSE C
      ON E.CourseID = C.CourseID
    WHERE S.Name = 'Ravi';

Count students per department:

    SELECT DepartmentID, COUNT(*) AS StudentCount
    FROM STUDENT
    GROUP BY DepartmentID;

Find students who are not enrolled in any course:

    SELECT S.StudentID, S.Name
    FROM STUDENT S
    LEFT JOIN ENROLLMENT E
      ON S.StudentID = E.StudentID
    WHERE E.StudentID IS NULL;

---

## 103. Relational Model Terminology

The following terminology is important.

| Relational Concept | Common Table Terminology |
|---|---|
| Relation | Table |
| Tuple | Row |
| Attribute | Column |
| Domain | Allowed value set / data type |
| Relation schema | Table definition |
| Relation instance | Current table contents |
| Degree | Number of columns |
| Cardinality | Number of rows |
| Primary key | Selected unique identifier |
| Foreign key | Referencing attribute(s) |
| Constraint | Rule enforcing valid data |

The terms are closely related but should not be treated as perfectly interchangeable in formal database theory.

---

## 104. Important Formulae and Facts

### Cartesian Product Cardinality

If:

    |R| = m

and:

    |S| = n

then:

    |R × S| = m × n

---

### Projection

Projection can reduce the number of attributes.

In classical relational algebra, duplicate tuples resulting from projection are eliminated because relations are sets.

---

### Selection

Selection does not change the degree of the relation.

It can reduce cardinality.

Therefore:

    Degree(σcondition(R)) = Degree(R)

while:

    Cardinality(σcondition(R)) <= Cardinality(R)

---

### Cartesian Product Degree

If:

    degree(R) = m

    degree(S) = n

then:

    degree(R × S) = m + n

---

### Cartesian Product Cardinality

If:

    cardinality(R) = m

    cardinality(S) = n

then:

    cardinality(R × S) = m × n

---

## 105. Exam-Oriented Concepts

For database examinations, especially GATE-style questions, pay particular attention to:

- Relation
- Tuple
- Attribute
- Domain
- Degree
- Cardinality
- Super key
- Candidate key
- Primary key
- Foreign key
- Functional dependency
- Closure
- Minimal cover
- Normalization
- 1NF
- 2NF
- 3NF
- BCNF
- Lossless decomposition
- Dependency preservation
- Selection
- Projection
- Union
- Difference
- Cartesian product
- Join
- Division
- SQL semantics
- NULL
- Three-valued logic

---

## 106. Functional Dependency Closure

Given a set of functional dependencies F and an attribute set X, the closure of X under F is written:

    X+

It contains all attributes that can be functionally determined by X using F.

Example:

    F = {
        A → B,
        B → C
    }

Start with:

    A+ = {A}

Using:

    A → B

we obtain:

    A+ = {A, B}

Using:

    B → C

we obtain:

    A+ = {A, B, C}

Therefore:

    A+ = {A, B, C}

Attribute closure is used to determine whether an attribute set is a super key.

---

## 107. Candidate Key Using Attribute Closure

Suppose:

    R(A, B, C, D)

and:

    F = {
        A → B,
        B → C,
        AC → D
    }

Compute:

    A+

Initially:

    A+ = {A}

Using A → B:

    A+ = {A, B}

Using B → C:

    A+ = {A, B, C}

Now AC → D applies because A and C are available:

    A+ = {A, B, C, D}

Therefore A determines every attribute of R.

So A is a super key.

If no subset of A exists other than the empty set, A is also a candidate key.

---

## 108. Minimal Cover

A minimal cover is an equivalent set of functional dependencies satisfying commonly used minimality conditions.

A typical procedure is:

1. Ensure each dependency has a single attribute on the right side.
2. Remove extraneous attributes from left sides where possible.
3. Remove redundant dependencies.

Example:

    A → BC

can be decomposed into:

    A → B
    A → C

This makes dependency analysis easier.

---

## 109. Armstrong's Axioms

Armstrong's axioms provide inference rules for functional dependencies.

The three basic axioms are:

### Reflexivity

If:

    Y ⊆ X

then:

    X → Y

### Augmentation

If:

    X → Y

then:

    XZ → YZ

### Transitivity

If:

    X → Y

and:

    Y → Z

then:

    X → Z

Additional inference rules can be derived from these axioms.

---

## 110. Lossless Join Test

For a decomposition of relation R into R1 and R2, a commonly used lossless-join condition is based on whether the common attributes functionally determine one of the decomposed relations.

If:

    R1 ∩ R2 → R1

or:

    R1 ∩ R2 → R2

under the relevant functional dependencies, the binary decomposition is lossless.

For larger decompositions, the chase algorithm can be used.

---

## 111. Dependency Preservation

Suppose a relation R is decomposed into R1, R2, ..., Rn.

Let:

    Fi

represent dependencies projected onto Ri.

The decomposition is dependency preserving if the union of the projected dependencies logically implies the original dependency set.

Conceptually:

    F+ = (F1 ∪ F2 ∪ ... ∪ Fn)+

for the relevant dependencies.

Dependency preservation allows constraints to be checked without reconstructing the original relation through joins.

---

## 112. Relational Algebra Expression Examples

Find students from CSE:

    σ Department = 'CSE' (STUDENT)

Find only names:

    π Name (STUDENT)

Find names of CSE students:

    π Name (σ Department = 'CSE' (STUDENT))

Find students and departments:

    STUDENT ⋈ STUDENT.DepartmentID = DEPARTMENT.DepartmentID DEPARTMENT

Find students enrolled in Database Systems:

    π StudentID (
        σ CourseName = 'Database Systems'
        (
            ENROLLMENT ⋈ COURSE
        )
    )

These expressions can be nested because relational algebra operations produce relations.

---

## 113. Relational Algebra Properties

Relational algebra operations can often be rearranged to improve query execution.

For example, applying a restrictive selection before a large join may reduce the number of tuples participating in the join.

Conceptually:

    σcondition(R ⋈ S)

may sometimes be transformed into an equivalent expression that pushes the selection closer to R or S.

This idea is called selection pushdown and is used by query optimizers.

---

## 114. Query Optimization Trade-Offs

A database optimizer balances:

- CPU cost
- Disk I/O
- Memory consumption
- Network transfer
- Cardinality estimates
- Available indexes
- Join order
- Predicate selectivity

A theoretically equivalent SQL query can have different execution costs depending on its structure and the database system's optimizer.

Good SQL is therefore not only about correctness. For production workloads, execution plans and workload characteristics also matter.

---

## 115. Referential Integrity Design Choices

Suppose a department is deleted.

Possible policies include:

### RESTRICT

Prevent deletion when dependent rows exist.

### CASCADE

Delete dependent rows.

### SET NULL

Set foreign keys in dependent rows to NULL if allowed.

### SET DEFAULT

Set dependent foreign keys to a predefined default where supported and appropriate.

The correct policy depends on the business meaning of the relationship.

---

## 116. Primary Key Design

A good primary key should generally be:

- Stable
- Unique
- Non-null
- Predictable in terms of uniqueness
- Appropriate for the workload

Natural keys can represent meaningful business identifiers.

Surrogate keys can provide stable database identifiers independent of business meaning.

Neither approach is universally superior.

The choice depends on:

- Business requirements
- Uniqueness guarantees
- Key length
- Change frequency
- Integration requirements
- Database workload

---

## 117. Surrogate Key

A surrogate key is an artificial identifier introduced for database purposes.

Example:

    StudentID INTEGER GENERATED BY DEFAULT AS IDENTITY

The value itself may have no business meaning.

Advantages can include:

- Simple references
- Small keys
- Stable identifiers
- Convenient joins

Potential disadvantages include:

- Additional generated identifier
- Need for separate uniqueness constraints for business keys
- Potentially less meaningful data representation

---

## 118. Natural Key

A natural key is an attribute or combination of attributes that has real-world meaning and uniquely identifies an entity.

Examples might include:

    PassportNumber

    Nationally assigned identifier

    Official registration number

Natural keys can change or have privacy and integration implications, so careful design is required.

---

## 119. Constraints and Data Quality

Relational databases can enforce many data-quality rules close to the data.

Examples:

    NOT NULL

    UNIQUE

    PRIMARY KEY

    FOREIGN KEY

    CHECK

This is preferable to relying exclusively on application code.

Application-level validation remains useful, but database constraints provide an additional integrity boundary.

---

## 120. Practical Design Principles

When designing a relational schema:

1. Identify independent entities.
2. Identify attributes.
3. Determine candidate keys.
4. Select appropriate primary keys.
5. Identify relationships.
6. Define foreign keys.
7. Identify functional dependencies.
8. Normalize where appropriate.
9. Check lossless decomposition.
10. Check dependency preservation.
11. Add integrity constraints.
12. Design indexes based on actual access patterns.
13. Consider transaction requirements.
14. Apply least-privilege security.
15. Test realistic workloads.
16. Monitor query performance.
17. Plan schema migrations carefully.

---

## 121. Production Considerations

A relational schema that is theoretically correct can still perform poorly in production.

Production database design should consider:

- Data volume
- Query frequency
- Concurrent users
- Transaction size
- Index selectivity
- Lock contention
- Connection management
- Backup strategy
- Recovery requirements
- Replication
- Monitoring
- Migration strategy
- Security
- Data retention
- Compliance requirements

Logical modeling and physical optimization are related but distinct activities.

---

## 122. Relational Model Checklist

Before considering a relational schema complete, verify:

- Are relations clearly defined?
- Are attributes appropriately named?
- Are domains appropriate?
- Are candidate keys identified?
- Is a suitable primary key selected?
- Are foreign keys correctly defined?
- Are integrity constraints enforced?
- Are NULL values intentional?
- Are functional dependencies understood?
- Is normalization appropriate?
- Is the decomposition lossless?
- Is dependency preservation required?
- Are indexes justified by actual queries?
- Are destructive operations protected?
- Are transactions correctly designed?
- Are security permissions appropriate?
- Is the design tested against realistic workloads?

---

## 123. Key Distinctions to Memorize

### Relation vs Relation Schema

    Relation schema = structure

    Relation = current set of tuples

### Degree vs Cardinality

    Degree = columns

    Cardinality = rows

### Super Key vs Candidate Key

    Super key = unique identifier, not necessarily minimal

    Candidate key = minimal super key

### Candidate Key vs Primary Key

    Candidate key = possible minimal identifier

    Primary key = selected candidate key

### Primary Key vs Foreign Key

    Primary key = identifies tuples in its own relation

    Foreign key = references a key in another relation

### Selection vs Projection

    Selection = rows

    Projection = columns

### WHERE vs HAVING

    WHERE = filters rows

    HAVING = filters groups

### DELETE vs DROP

    DELETE = removes tuples

    DROP = removes a database object such as a table

---

## 124. Conceptual Mental Model

A useful way to understand the relational model is:

    Domain
       ↓
    Attribute
       ↓
    Tuple
       ↓
    Relation
       ↓
    Database Schema
       ↓
    Database Instance

Keys identify tuples.

Foreign keys connect relations.

Constraints protect correctness.

Relational algebra defines formal operations.

SQL provides a practical language for interacting with relational databases.

Normalization helps reduce redundancy and anomalies.

Indexes and query optimization improve physical execution.

Transactions protect changes during concurrent operations and failures.

---

## 125. Final Reference Table

| Concept | Meaning |
|---|---|
| Relation | Set of tuples with a defined schema |
| Relation schema | Structure of a relation |
| Relation instance | Current set of tuples |
| Attribute | Named property/column |
| Domain | Permitted set of values |
| Tuple | Ordered collection of attribute values |
| Degree | Number of attributes |
| Cardinality | Number of tuples |
| Super key | Attribute set that uniquely identifies tuples |
| Candidate key | Minimal super key |
| Primary key | Selected candidate key |
| Alternate key | Candidate key not selected as primary |
| Foreign key | Attribute set referencing another relation's key |
| Entity integrity | Primary key cannot be NULL |
| Referential integrity | Foreign-key references must satisfy defined constraints |
| Selection | Filters tuples |
| Projection | Selects attributes |
| Union | Combines compatible relations |
| Difference | Tuples in one relation but not another |
| Cartesian product | Combines every tuple from two relations |
| Join | Combines related tuples |
| Functional dependency | Attribute determination relationship |
| Normalization | Reduces redundancy and anomalies |
| 1NF | Atomic attribute values |
| 2NF | No partial dependency of non-prime attributes |
| 3NF | No problematic transitive dependency |
| BCNF | Every determinant is a super key |
| Lossless decomposition | Original information can be reconstructed without spurious information |
| Dependency preservation | Dependencies remain enforceable on decomposed relations |
| SQL | Practical language for relational databases |
| Transaction | Logical unit of database work |
| ACID | Atomicity, Consistency, Isolation, Durability |
| Index | Structure used to accelerate data access |
| View | Virtual relation defined by a query |

---

## 126. Essential Takeaways

The relational model represents structured information through relations.

A relation consists conceptually of tuples, and tuples contain values for attributes.

Domains define permissible values.

Degree counts attributes.

Cardinality counts tuples.

Keys provide identification.

Foreign keys represent relationships between relations.

Integrity constraints maintain valid data.

Relational algebra provides a formal framework for querying relations.

Selection filters tuples.

Projection selects attributes.

Joins combine related relations.

Functional dependencies describe attribute determination.

Normalization reduces redundancy and data anomalies.

SQL provides the practical interface used by relational database systems.

The relational model separates logical data organization from physical storage and provides a strong foundation for reliable, consistent, and queryable data management.
