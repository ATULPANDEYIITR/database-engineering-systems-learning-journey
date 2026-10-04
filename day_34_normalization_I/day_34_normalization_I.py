"""
Normalization I: Functional Dependencies and Anomalies

A self-contained executable teaching model for relational normalization.
The program progresses from functional dependencies to anomaly detection,
candidate keys, closure computation, and a lossless decomposition example.

Run:
    python normalization_functional_dependencies.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import FrozenSet, Iterable, Mapping, Sequence


# ---------------------------------------------------------------------------
# Relational data model
# ---------------------------------------------------------------------------

Row = dict[str, object]
AttributeSet = FrozenSet[str]


@dataclass
class Relation:
    """A small in-memory relational table used to demonstrate anomalies."""

    name: str
    columns: tuple[str, ...]
    rows: list[Row] = field(default_factory=list)

    def validate(self) -> None:
        """Reject rows containing missing or unknown attributes."""
        expected = set(self.columns)

        for index, row in enumerate(self.rows, start=1):
            actual = set(row)
            if actual != expected:
                missing = expected - actual
                extra = actual - expected
                raise ValueError(
                    f"{self.name} row {index} has invalid columns. "
                    f"Missing={sorted(missing)}, Extra={sorted(extra)}"
                )

    def insert(self, **values: object) -> None:
        """Insert one complete tuple after schema validation."""
        if set(values) != set(self.columns):
            raise ValueError(
                f"Insert into {self.name} requires exactly "
                f"{self.columns}, received {tuple(values)}"
            )
        self.rows.append(dict(values))

    def delete_where(self, predicate) -> list[Row]:
        """Delete matching tuples and return the deleted rows."""
        removed = [row for row in self.rows if predicate(row)]
        self.rows[:] = [row for row in self.rows if not predicate(row)]
        return removed

    def update_where(self, predicate, **changes: object) -> int:
        """Update matching tuples and return the number changed."""
        unknown = set(changes) - set(self.columns)
        if unknown:
            raise ValueError(f"Unknown columns in update: {sorted(unknown)}")

        count = 0
        for row in self.rows:
            if predicate(row):
                row.update(changes)
                count += 1
        return count

    def display(self, title: str | None = None) -> None:
        if title:
            print(f"\n{title}")
        widths = {
            column: max(
                len(column),
                *(len(str(row[column])) for row in self.rows),
            )
            for column in self.columns
        }
        header = " | ".join(column.ljust(widths[column]) for column in self.columns)
        print(header)
        print("-+-".join("-" * widths[column] for column in self.columns))
        for row in self.rows:
            print(
                " | ".join(
                    str(row[column]).ljust(widths[column])
                    for column in self.columns
                )
            )


# ---------------------------------------------------------------------------
# Functional dependency model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FunctionalDependency:
    """
    X -> Y means that whenever two tuples agree on every attribute in X,
    they must also agree on every attribute in Y.
    """

    determinant: AttributeSet
    dependent: AttributeSet

    def __post_init__(self) -> None:
        if not self.determinant:
            raise ValueError("A determinant must contain at least one attribute.")
        if not self.dependent:
            raise ValueError("A dependent set must contain at least one attribute.")

    def __str__(self) -> str:
        left = ", ".join(sorted(self.determinant))
        right = ", ".join(sorted(self.dependent))
        return f"{{{left}}} -> {{{right}}}"


def fd(
    determinant: Iterable[str],
    dependent: Iterable[str],
) -> FunctionalDependency:
    return FunctionalDependency(frozenset(determinant), frozenset(dependent))


def attribute_closure(
    attributes: Iterable[str],
    dependencies: Sequence[FunctionalDependency],
) -> AttributeSet:
    """
    Compute X+ under a set of functional dependencies.

    Start with X. Whenever the current closure contains a dependency's
    determinant, add its dependent attributes. Repeat until no new
    attributes can be derived.
    """
    closure = set(attributes)

    changed = True
    while changed:
        changed = False
        for dependency in dependencies:
            if dependency.determinant <= closure:
                before = len(closure)
                closure.update(dependency.dependent)
                changed |= len(closure) > before

    return frozenset(closure)


def implies(
    determinant: Iterable[str],
    dependent: Iterable[str],
    dependencies: Sequence[FunctionalDependency],
) -> bool:
    """Test whether X -> Y follows from the supplied dependencies."""
    return set(dependent) <= attribute_closure(determinant, dependencies)


def is_superkey(
    attributes: Iterable[str],
    relation_attributes: Iterable[str],
    dependencies: Sequence[FunctionalDependency],
) -> bool:
    """A superkey determines every attribute in the relation."""
    return attribute_closure(attributes, dependencies) >= set(relation_attributes)


def candidate_keys(
    relation_attributes: Iterable[str],
    dependencies: Sequence[FunctionalDependency],
) -> list[AttributeSet]:
    """
    Find minimal superkeys by exhaustive search.

    This is deliberately educational. Exhaustive key enumeration is
    exponential in the number of attributes and should not be used as the
    production algorithm for very wide schemas.
    """
    attributes = tuple(sorted(set(relation_attributes)))
    keys: list[AttributeSet] = []

    for size in range(1, len(attributes) + 1):
        for combination in combinations(attributes, size):
            candidate = frozenset(combination)

            if not is_superkey(candidate, attributes, dependencies):
                continue

            # Minimality: no already-known candidate key may be contained in it.
            if any(key <= candidate for key in keys):
                continue

            keys.append(candidate)

    return keys


def prime_attributes(candidate_keys_list: Sequence[AttributeSet]) -> set[str]:
    return set().union(*(set(key) for key in candidate_keys_list))


def violates_fd(
    relation: Relation,
    dependency: FunctionalDependency,
) -> list[tuple[Row, Row]]:
    """
    Find concrete tuple pairs that violate X -> Y.

    For each determinant value, all dependent values must be identical.
    """
    violations = []

    for first_index, first in enumerate(relation.rows):
        for second in relation.rows[first_index + 1 :]:
            same_determinant = all(
                first[column] == second[column]
                for column in dependency.determinant
            )
            different_dependent = any(
                first[column] != second[column]
                for column in dependency.dependent
            )

            if same_determinant and different_dependent:
                violations.append((first, second))

    return violations


# ---------------------------------------------------------------------------
# Anomaly demonstrations
# ---------------------------------------------------------------------------

def demonstrate_update_anomaly() -> None:
    """
    A department location is duplicated for every employee.

    Changing the department location requires multiple row updates.
    Missing one creates inconsistent copies of the same fact.
    """
    table = Relation(
        "EmployeeDepartment",
        ("employee_id", "employee_name", "department", "department_location"),
        [
            {
                "employee_id": "E101",
                "employee_name": "Anita",
                "department": "Finance",
                "department_location": "Mumbai",
            },
            {
                "employee_id": "E102",
                "employee_name": "Rahul",
                "department": "Finance",
                "department_location": "Mumbai",
            },
            {
                "employee_id": "E103",
                "employee_name": "Meera",
                "department": "HR",
                "department_location": "Delhi",
            },
        ],
    )

    table.display("Before the department location changes")

    table.update_where(
        lambda row: row["employee_id"] == "E101",
        department_location="Pune",
    )

    table.display(
        "After updating only E101: the FD department -> department_location "
        "is now violated"
    )

    dependency = fd({"department"}, {"department_location"})
    violations = violate_fd(table, dependency)

    print(f"\nUpdate anomaly detected for {dependency}: {len(violations)} violation(s)")


def demonstrate_insertion_anomaly() -> None:
    """
    Course information cannot be stored unless a student is also enrolled.

    A normalized design would store course facts independently.
    """
    enrollment = Relation(
        "StudentCourse",
        ("student_id", "student_name", "course_id", "course_name", "instructor"),
        [
            {
                "student_id": "S1",
                "student_name": "Asha",
                "course_id": "DB101",
                "course_name": "Database Systems",
                "instructor": "Dr. Rao",
            }
        ],
    )

    print("\nInsertion anomaly")
    enrollment.display("Current enrollment relation")
    print(
        "\nSuppose DB202 = 'Distributed Databases' is approved but has no "
        "students yet. This relation has no natural row in which to store "
        "the course fact without inventing a student or using NULL values."
    )


def demonstrate_deletion_anomaly() -> None:
    """
    Deleting the final enrollment for a course also deletes course metadata.
    """
    enrollment = Relation(
        "StudentCourse",
        ("student_id", "student_name", "course_id", "course_name", "instructor"),
        [
            {
                "student_id": "S1",
                "student_name": "Asha",
                "course_id": "DB101",
                "course_name": "Database Systems",
                "instructor": "Dr. Rao",
            },
            {
                "student_id": "S2",
                "student_name": "Kabir",
                "course_id": "DB101",
                "course_name": "Database Systems",
                "instructor": "Dr. Rao",
            },
        ],
    )

    enrollment.display("Before deleting the last student")
    enrollment.delete_where(lambda row: row["student_id"] == "S1")
    enrollment.display("After deleting S1")

    enrollment.delete_where(lambda row: row["student_id"] == "S2")
    enrollment.display(
        "After deleting S2: the database has lost the DB101 course fact"
    )


# ---------------------------------------------------------------------------
# A realistic normalization analysis
# ---------------------------------------------------------------------------

def demonstrate_functional_dependencies() -> None:
    """
    Analyze a university enrollment relation.

    Attributes:
        student_id -> student_name, student_program
        course_id -> course_name, department
        instructor_id -> instructor_name
        course_id, section_no, term -> instructor_id
        student_id, course_id, section_no, term -> grade

    The last determinant is an enrollment identifier and should be a key.
    """
    attributes = {
        "student_id",
        "student_name",
        "student_program",
        "course_id",
        "course_name",
        "department",
        "instructor_id",
        "instructor_name",
        "section_no",
        "term",
        "grade",
    }

    dependencies = [
        fd({"student_id"}, {"student_name", "student_program"}),
        fd({"course_id"}, {"course_name", "department"}),
        fd({"instructor_id"}, {"instructor_name"}),
        fd(
            {"course_id", "section_no", "term"},
            {"instructor_id"},
        ),
        fd(
            {"student_id", "course_id", "section_no", "term"},
            {"grade"},
        ),
    ]

    print("\nFunctional dependencies")
    for dependency in dependencies:
        print(f"  {dependency}")

    print("\nClosure calculations")
    examples = [
        {"student_id"},
        {"course_id"},
        {"course_id", "section_no", "term"},
        {"student_id", "course_id", "section_no", "term"},
    ]

    for attributes_to_close in examples:
        closure = attribute_closure(attributes_to_close, dependencies)
        print(
            f"  {sorted(attributes_to_close)}+ = "
            f"{sorted(closure)}"
        )

    keys = candidate_keys(attributes, dependencies)

    print("\nCandidate keys")
    for key in keys:
        print(f"  {sorted(key)}")

    primes = prime_attributes(keys)
    print(f"\nPrime attributes: {sorted(primes)}")

    print("\nFD implication checks")
    checks = [
        (
            {"student_id"},
            {"student_name"},
        ),
        (
            {"student_id", "course_id", "section_no", "term"},
            {"instructor_name"},
        ),
        (
            {"course_id"},
            {"instructor_id"},
        ),
    ]

    for determinant, dependent in checks:
        result = implies(determinant, dependent, dependencies)
        print(
            f"  {sorted(determinant)} -> {sorted(dependent)}: "
            f"{'implied' if result else 'not implied'}"
        )


# ---------------------------------------------------------------------------
# Detecting partial and transitive dependencies
# ---------------------------------------------------------------------------

def demonstrate_dependency_types() -> None:
    """
    Show why dependency type matters when evaluating a schema.

    In EnrollmentRecord, the composite key is:
        (student_id, course_id, section_no, term)

    student_id -> student_name is a partial dependency because student_id
    is only part of the composite key.

    course_id -> course_name is also partial.

    instructor_id -> instructor_name is a non-key dependency. If
    (course_id, section_no, term) -> instructor_id, then instructor_name is
    transitively dependent on the enrollment key through instructor_id.
    """
    print("\nPartial and transitive dependency analysis")

    key = {
        "student_id",
        "course_id",
        "section_no",
        "term",
    }

    dependencies = [
        fd({"student_id"}, {"student_name"}),
        fd({"course_id"}, {"course_name"}),
        fd(
            {"course_id", "section_no", "term"},
            {"instructor_id"},
        ),
        fd({"instructor_id"}, {"instructor_name"}),
    ]

    for dependency in dependencies:
        determinant = set(dependency.determinant)

        if determinant < key:
            classification = "partial dependency on the composite key"
        elif determinant <= key:
            classification = "dependency whose determinant contains the full key"
        else:
            classification = (
                "non-key dependency; inspect it for a transitive dependency path"
            )

        print(f"  {dependency}")
        print(f"    {classification}")

    print(
        "\nThe chain course_id, section_no, term -> instructor_id -> "
        "instructor_name is the important transitive pattern. The enrollment "
        "key determines instructor_name, but instructor_id provides an "
        "intermediate determinant."
    )


# ---------------------------------------------------------------------------
# Decomposition demonstration
# ---------------------------------------------------------------------------

def project_relation(
    relation: Relation,
    columns: Sequence[str],
) -> Relation:
    """
    Project a relation onto a subset of attributes and remove duplicate tuples.

    Projection is useful when constructing normalized relations from a
    denormalized relation.
    """
    selected = tuple(columns)
    unique_rows: list[Row] = []
    seen: set[tuple[object, ...]] = set()

    for row in relation.rows:
        values = tuple(row[column] for column in selected)
        if values not in seen:
            seen.add(values)
            unique_rows.append(dict(zip(selected, values)))

    return Relation(relation.name + "_projection", selected, unique_rows)


def demonstrate_decomposition() -> None:
    """
    Decompose an enrollment relation into relations whose dependencies are
    easier to enforce.

    Student(student_id, student_name, student_program)
    Course(course_id, course_name, department)
    Instructor(instructor_id, instructor_name)
    Section(course_id, section_no, term, instructor_id)
    Enrollment(student_id, course_id, section_no, term, grade)

    The decomposition separates facts about students, courses, instructors,
    sections, and individual enrollment outcomes.
    """
    source = Relation(
        "EnrollmentRecord",
        (
            "student_id",
            "student_name",
            "student_program",
            "course_id",
            "course_name",
            "department",
            "section_no",
            "term",
            "instructor_id",
            "instructor_name",
            "grade",
        ),
        [
            {
                "student_id": "S1",
                "student_name": "Asha",
                "student_program": "MCA",
                "course_id": "DB101",
                "course_name": "Database Systems",
                "department": "Computer Science",
                "section_no": "A",
                "term": "2026-Fall",
                "instructor_id": "I7",
                "instructor_name": "Dr. Rao",
                "grade": "A",
            },
            {
                "student_id": "S2",
                "student_name": "Kabir",
                "student_program": "MBA",
                "course_id": "DB101",
                "course_name": "Database Systems",
                "department": "Computer Science",
                "section_no": "A",
                "term": "2026-Fall",
                "instructor_id": "I7",
                "instructor_name": "Dr. Rao",
                "grade": "B+",
            },
            {
                "student_id": "S1",
                "student_name": "Asha",
                "student_program": "MCA",
                "course_id": "AI201",
                "course_name": "Machine Learning",
                "department": "Computer Science",
                "section_no": "B",
                "term": "2026-Fall",
                "instructor_id": "I9",
                "instructor_name": "Dr. Sen",
                "grade": "A-",
            },
        ],
    )

    student = project_relation(
        source,
        ("student_id", "student_name", "student_program"),
    )
    course = project_relation(
        source,
        ("course_id", "course_name", "department"),
    )
    instructor = project_relation(
        source,
        ("instructor_id", "instructor_name"),
    )
    section = project_relation(
        source,
        ("course_id", "section_no", "term", "instructor_id"),
    )
    enrollment = project_relation(
        source,
        ("student_id", "course_id", "section_no", "term", "grade"),
    )

    for table in [student, course, instructor, section, enrollment]:
        table.display(f"Normalized relation: {table.name}")


# ---------------------------------------------------------------------------
# Validation and edge cases
# ---------------------------------------------------------------------------

def demonstrate_edge_cases() -> None:
    print("\nValidation and edge cases")

    try:
        FunctionalDependency(frozenset(), frozenset({"name"}))
    except ValueError as error:
        print(f"  Empty determinant rejected: {error}")

    try:
        FunctionalDependency(frozenset({"id"}), frozenset())
    except ValueError as error:
        print(f"  Empty dependent set rejected: {error}")

    relation = Relation("Employee", ("employee_id", "name"), [])
    try:
        relation.insert(employee_id="E1")
    except ValueError as error:
        print(f"  Incomplete tuple rejected: {error}")

    dependency = fd({"employee_id"}, {"name"})
    relation.insert(employee_id="E1", name="Asha")
    relation.insert(employee_id="E2", name="Kabir")

    violations = violate_fd(relation, dependency)
    print(
        f"  FD {dependency} has "
        f"{len(violations)} violation(s) in the current relation."
    )

    print(
        "\n  Important edge case: an FD is a constraint about all valid "
        "tuples, not merely a pattern observed in a small sample. A sample "
        "with no violation does not prove that an FD is semantically true."
    )


# ---------------------------------------------------------------------------
# Main educational workflow
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 78)
    print("NORMALIZATION I: FUNCTIONAL DEPENDENCIES AND ANOMALIES")
    print("=" * 78)

    print(
        "\nCore idea: normalization reduces problematic redundancy by organizing "
        "attributes according to the facts and dependencies they represent."
    )

    demonstrate_update_anomaly()
    demonstrate_insertion_anomaly()
    demonstrate_deletion_anomaly()

    demonstrate_functional_dependencies()
    demonstrate_dependency_types()
    demonstrate_decomposition()
    demonstrate_edge_cases()

    print("\n" + "=" * 78)
    print("Key operational rule")
    print("=" * 78)
    print(
        "For an FD X -> Y, the database must ensure that two tuples with "
        "the same X values cannot disagree on Y. Candidate keys are minimal "
        "attribute sets whose closure contains every attribute of the "
        "relation. Anomalies arise when unrelated facts are stored together "
        "and redundancy makes insertion, update, or deletion unsafe."
    )


if __name__ == "__main__":
    main()
