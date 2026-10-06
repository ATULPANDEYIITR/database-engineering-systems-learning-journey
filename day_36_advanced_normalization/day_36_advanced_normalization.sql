/*
Advanced Database Normalization: BCNF, 4NF, and 5NF
PostgreSQL-compatible SQL

The schema models:
- functional dependencies relevant to BCNF
- independent multivalued facts relevant to 4NF
- a ternary association relevant to 5NF
- candidate-key and uniqueness constraints
- referential integrity
- database-level validation
- views that expose decomposed relational structures
- examples of lossless reconstruction through joins

The SQL deliberately uses different relations for the three normal-form
problems instead of treating BCNF, 4NF, and 5NF as interchangeable concepts.
*/

DROP SCHEMA IF EXISTS advanced_normalization CASCADE;
CREATE SCHEMA advanced_normalization;

SET search_path TO advanced_normalization;

-- ============================================================
-- BCNF: TEACHING ASSIGNMENT
-- ============================================================

/*
Business rules:

A student-course pair identifies the instructor teaching that course to the
student.

An instructor determines the instructor office.

The dependency Instructor -> InstructorOffice is problematic in the original
four-attribute relation because Instructor is not a superkey of that relation.
The normalized design separates instructor facts from student-course facts.
*/

CREATE TABLE instructor (
    instructor_id     TEXT PRIMARY KEY,
    instructor_name   TEXT NOT NULL,
    office_code       TEXT NOT NULL,
    CONSTRAINT uq_instructor_office
        UNIQUE (instructor_id, office_code)
);

CREATE TABLE course (
    course_id         TEXT PRIMARY KEY,
    course_name       TEXT NOT NULL
);

CREATE TABLE student (
    student_id        TEXT PRIMARY KEY,
    student_name      TEXT NOT NULL
);

CREATE TABLE teaching_assignment (
    student_id        TEXT NOT NULL,
    course_id         TEXT NOT NULL,
    instructor_id     TEXT NOT NULL,

    PRIMARY KEY (student_id, course_id),

    CONSTRAINT fk_assignment_student
        FOREIGN KEY (student_id)
        REFERENCES student(student_id),

    CONSTRAINT fk_assignment_course
        FOREIGN KEY (course_id)
        REFERENCES course(course_id),

    CONSTRAINT fk_assignment_instructor
        FOREIGN KEY (instructor_id)
        REFERENCES instructor(instructor_id)
);

INSERT INTO student (student_id, student_name)
VALUES
    ('S001', 'Anita Rao'),
    ('S002', 'Rahul Mehta'),
    ('S003', 'Kiran Shah');

INSERT INTO course (course_id, course_name)
VALUES
    ('DB101', 'Database Systems'),
    ('OS201', 'Operating Systems'),
    ('SE301', 'Software Engineering');

INSERT INTO instructor (
    instructor_id,
    instructor_name,
    office_code
)
VALUES
    ('I001', 'Dr. Meera Singh', 'B201'),
    ('I002', 'Dr. Arjun Verma', 'C102');

INSERT INTO teaching_assignment (
    student_id,
    course_id,
    instructor_id
)
VALUES
    ('S001', 'DB101', 'I001'),
    ('S002', 'DB101', 'I001'),
    ('S003', 'OS201', 'I002'),
    ('S001', 'SE301', 'I002');

-- The original conceptual dependency can now be expressed through joins:
-- (Student, Course) -> Instructor
-- Instructor -> InstructorOffice

SELECT
    ta.student_id,
    ta.course_id,
    ta.instructor_id,
    i.instructor_name,
    i.office_code
FROM teaching_assignment AS ta
JOIN instructor AS i
    ON i.instructor_id = ta.instructor_id
ORDER BY ta.student_id, ta.course_id;

-- A uniqueness violation demonstrates database-level key enforcement.
-- The following statement is intentionally commented out because the SQL
-- script must execute successfully.
--
-- INSERT INTO teaching_assignment
-- VALUES ('S001', 'DB101', 'I002');

-- ============================================================
-- BCNF ANALYSIS SUPPORT
-- ============================================================

CREATE TABLE normalization_fd_catalog (
    relation_name     TEXT NOT NULL,
    determinant       TEXT NOT NULL,
    dependent         TEXT NOT NULL,
    is_non_trivial    BOOLEAN NOT NULL,
    determinant_is_superkey BOOLEAN NOT NULL,
    normal_form_issue TEXT,
    PRIMARY KEY (relation_name, determinant, dependent)
);

INSERT INTO normalization_fd_catalog
VALUES
    (
        'TeachingAssignmentOriginal',
        '{StudentID, CourseID}',
        '{InstructorID}',
        TRUE,
        TRUE,
        NULL
    ),
    (
        'TeachingAssignmentOriginal',
        '{InstructorID}',
        '{InstructorOffice}',
        TRUE,
        FALSE,
        'BCNF violation'
    );

SELECT *
FROM normalization_fd_catalog
WHERE normal_form_issue IS NOT NULL;

-- ============================================================
-- 4NF: INDEPENDENT MULTIVALUED FACTS
-- ============================================================

/*
An employee can possess several skills and speak several languages.

The skill set and language set are independent. A single relation:

    EmployeeSkillLanguage(Employee, Skill, Language)

would need to contain every skill-language combination for an employee.

The normalized design stores each independent multivalued fact separately.
*/

CREATE TABLE employee (
    employee_id      TEXT PRIMARY KEY,
    employee_name    TEXT NOT NULL
);

CREATE TABLE skill (
    skill_code       TEXT PRIMARY KEY,
    skill_name       TEXT NOT NULL UNIQUE
);

CREATE TABLE language (
    language_code    TEXT PRIMARY KEY,
    language_name    TEXT NOT NULL UNIQUE
);

CREATE TABLE employee_skill (
    employee_id      TEXT NOT NULL,
    skill_code       TEXT NOT NULL,

    PRIMARY KEY (employee_id, skill_code),

    FOREIGN KEY (employee_id)
        REFERENCES employee(employee_id),

    FOREIGN KEY (skill_code)
        REFERENCES skill(skill_code)
);

CREATE TABLE employee_language (
    employee_id      TEXT NOT NULL,
    language_code    TEXT NOT NULL,

    PRIMARY KEY (employee_id, language_code),

    FOREIGN KEY (employee_id)
        REFERENCES employee(employee_id),

    FOREIGN KEY (language_code)
        REFERENCES language(language_code)
);

INSERT INTO employee (
    employee_id,
    employee_name
)
VALUES
    ('E001', 'Priya Nair'),
    ('E002', 'Vikram Das');

INSERT INTO skill (
    skill_code,
    skill_name
)
VALUES
    ('PY', 'Python'),
    ('SQL', 'SQL'),
    ('CPP', 'C++');

INSERT INTO language (
    language_code,
    language_name
)
VALUES
    ('EN', 'English'),
    ('FR', 'French'),
    ('HI', 'Hindi');

INSERT INTO employee_skill
VALUES
    ('E001', 'PY'),
    ('E001', 'SQL'),
    ('E002', 'CPP');

INSERT INTO employee_language
VALUES
    ('E001', 'EN'),
    ('E001', 'FR'),
    ('E002', 'EN'),
    ('E002', 'HI');

-- The independent facts can be queried without storing a Cartesian product.

SELECT
    e.employee_name,
    s.skill_name
FROM employee_skill AS es
JOIN employee AS e
    ON e.employee_id = es.employee_id
JOIN skill AS s
    ON s.skill_code = es.skill_code
ORDER BY e.employee_name, s.skill_name;

SELECT
    e.employee_name,
    l.language_name
FROM employee_language AS el
JOIN employee AS e
    ON e.employee_id = el.employee_id
JOIN language AS l
    ON l.language_code = el.language_code
ORDER BY e.employee_name, l.language_name;

-- ============================================================
-- 4NF CROSS-PRODUCT RECONSTRUCTION
-- ============================================================

/*
For an employee whose skill set and language set are independent, the
conceptual four-row Cartesian combination can be reconstructed.

This is a semantic demonstration of the MVD:

    Employee ->> Skill

in the relation EmployeeSkillLanguage.
*/

CREATE VIEW employee_skill_language_reconstruction AS
SELECT
    es.employee_id,
    es.skill_code,
    el.language_code
FROM employee_skill AS es
JOIN employee_language AS el
    ON el.employee_id = es.employee_id;

SELECT *
FROM employee_skill_language_reconstruction
ORDER BY employee_id, skill_code, language_code;

-- ============================================================
-- 4NF VALIDATION QUERY
-- ============================================================

/*
For E001 there are two skills and two languages, so an independent MVD
requires four combinations in the reconstructed relation.
*/

SELECT
    employee_id,
    COUNT(DISTINCT skill_code) AS skill_count,
    COUNT(DISTINCT language_code) AS language_count,
    COUNT(*) AS reconstructed_combinations,
    COUNT(DISTINCT skill_code)
        * COUNT(DISTINCT language_code)
        AS expected_combinations
FROM employee_skill_language_reconstruction
GROUP BY employee_id
ORDER BY employee_id;

-- ============================================================
-- 5NF: SUPPLIER-PART-PROJECT
-- ============================================================

/*
The ternary relation SupplierPartProject can sometimes contain a join
dependency:

    *(SupplierPart, SupplierProject, PartProject)

A pairwise decomposition is valid only when the domain semantics state that
the ternary association is exactly implied by those three pairwise relations.

The following tables model the decomposed relations.
*/

CREATE TABLE supplier (
    supplier_id       TEXT PRIMARY KEY,
    supplier_name     TEXT NOT NULL
);

CREATE TABLE part (
    part_id           TEXT PRIMARY KEY,
    part_name         TEXT NOT NULL
);

CREATE TABLE project (
    project_id        TEXT PRIMARY KEY,
    project_name      TEXT NOT NULL
);

CREATE TABLE supplier_part (
    supplier_id       TEXT NOT NULL,
    part_id           TEXT NOT NULL,

    PRIMARY KEY (supplier_id, part_id),

    FOREIGN KEY (supplier_id)
        REFERENCES supplier(supplier_id),

    FOREIGN KEY (part_id)
        REFERENCES part(part_id)
);

CREATE TABLE supplier_project (
    supplier_id       TEXT NOT NULL,
    project_id        TEXT NOT NULL,

    PRIMARY KEY (supplier_id, project_id),

    FOREIGN KEY (supplier_id)
        REFERENCES supplier(supplier_id),

    FOREIGN KEY (project_id)
        REFERENCES project(project_id)
);

CREATE TABLE part_project (
    part_id           TEXT NOT NULL,
    project_id        TEXT NOT NULL,

    PRIMARY KEY (part_id, project_id),

    FOREIGN KEY (part_id)
        REFERENCES part(part_id),

    FOREIGN KEY (project_id)
        REFERENCES project(project_id)
);

INSERT INTO supplier
VALUES
    ('SUP1', 'Precision Components Ltd'),
    ('SUP2', 'Industrial Parts Co');

INSERT INTO part
VALUES
    ('P1', 'Controller'),
    ('P2', 'Sensor');

INSERT INTO project
VALUES
    ('PR1', 'Autonomous Platform'),
    ('PR2', 'Factory Upgrade');

INSERT INTO supplier_part
VALUES
    ('SUP1', 'P1'),
    ('SUP1', 'P2'),
    ('SUP2', 'P2');

INSERT INTO supplier_project
VALUES
    ('SUP1', 'PR1'),
    ('SUP2', 'PR2');

INSERT INTO part_project
VALUES
    ('P1', 'PR1'),
    ('P2', 'PR1'),
    ('P2', 'PR2');

-- ============================================================
-- 5NF JOIN RECONSTRUCTION
-- ============================================================

/*
The natural join is the database-level representation of the join dependency.
If the business rule is correct, the reconstruction equals the intended
ternary relation. If the business rule is not correct, the join can generate
spurious tuples.
*/

CREATE VIEW supplier_part_project_reconstructed AS
SELECT
    sp.supplier_id,
    sp.part_id,
    sj.project_id
FROM supplier_part AS sp
JOIN supplier_project AS sj
    ON sj.supplier_id = sp.supplier_id
JOIN part_project AS pp
    ON pp.part_id = sp.part_id
   AND pp.project_id = sj.project_id;

SELECT *
FROM supplier_part_project_reconstructed
ORDER BY supplier_id, part_id, project_id;

-- ============================================================
-- INDEXES
-- ============================================================

/*
Primary keys already create indexes for the pairwise relationship tables.
These additional indexes target the common reverse traversal direction:
finding all suppliers for a part or all employees associated with a skill
or language.
*/

CREATE INDEX idx_supplier_part_part
    ON supplier_part(part_id);

CREATE INDEX idx_supplier_project_project
    ON supplier_project(project_id);

CREATE INDEX idx_part_project_project
    ON part_project(project_id);

CREATE INDEX idx_employee_skill_skill
    ON employee_skill(skill_code);

CREATE INDEX idx_employee_language_language
    ON employee_language(language_code);

-- ============================================================
-- TRANSACTIONAL INTEGRITY EXAMPLE
-- ============================================================

/*
A new employee capability should be inserted atomically when the application
creates the employee and associated facts together.

PostgreSQL's foreign keys prevent child rows from referring to nonexistent
parent entities.
*/

BEGIN;

INSERT INTO employee (
    employee_id,
    employee_name
)
VALUES
    ('E003', 'Neha Kapoor');

INSERT INTO employee_skill
VALUES
    ('E003', 'PY');

INSERT INTO employee_language
VALUES
    ('E003', 'EN');

COMMIT;

SELECT
    e.employee_name,
    s.skill_name,
    l.language_name
FROM employee AS e
JOIN employee_skill AS es
    ON es.employee_id = e.employee_id
JOIN skill AS s
    ON s.skill_code = es.skill_code
JOIN employee_language AS el
    ON el.employee_id = e.employee_id
JOIN language AS l
    ON l.language_code = el.language_code
WHERE e.employee_id = 'E003';

-- ============================================================
-- INVALID STATE DEMONSTRATIONS
-- ============================================================

/*
The following statements are intentionally commented out.

They demonstrate integrity failures without causing the complete script to
terminate.

A nonexistent employee cannot receive a skill because of the foreign key.
A duplicate employee-skill relationship cannot be inserted because the
composite primary key represents the relationship as a set.
*/

/*
INSERT INTO employee_skill
VALUES ('E999', 'PY');
*/

/*
INSERT INTO employee_skill
VALUES ('E001', 'PY');
*/

-- ============================================================
-- NORMALIZATION METADATA
-- ============================================================

CREATE TABLE normal_form_reference (
    normal_form       TEXT PRIMARY KEY,
    dependency_type   TEXT NOT NULL,
    determinant_rule  TEXT NOT NULL,
    primary_purpose   TEXT NOT NULL
);

INSERT INTO normal_form_reference
VALUES
(
    'BCNF',
    'Functional dependency',
    'Every non-trivial determinant must be a superkey',
    'Eliminate redundancy caused by non-key determinants'
),
(
    '4NF',
    'Multivalued dependency',
    'Every non-trivial MVD determinant must be a superkey',
    'Separate independent multivalued facts'
),
(
    '5NF',
    'Join dependency',
    'Every non-trivial JD must be implied by candidate-key and dependency semantics',
    'Eliminate redundancy caused by irreducible join dependencies'
);

SELECT *
FROM normal_form_reference
ORDER BY normal_form;

-- ============================================================
-- COMPARATIVE DIAGNOSTIC QUERY
-- ============================================================

SELECT
    normal_form,
    dependency_type,
    determinant_rule,
    primary_purpose
FROM normal_form_reference
WHERE normal_form IN ('BCNF', '4NF', '5NF')
ORDER BY
    CASE normal_form
        WHEN 'BCNF' THEN 1
        WHEN '4NF' THEN 2
        WHEN '5NF' THEN 3
    END;
