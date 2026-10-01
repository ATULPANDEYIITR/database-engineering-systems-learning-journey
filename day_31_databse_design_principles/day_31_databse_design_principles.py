#!/usr/bin/env python3
"""
Database Design Principles
Logical vs. physical design, design objectives

A self-contained case study for designing a university course-enrollment
database. The program separates logical modeling decisions from physical
implementation decisions and evaluates practical design objectives such as:

- correctness and integrity
- normalization and controlled redundancy
- query performance
- storage efficiency
- maintainability
- scalability
- security and operational safety

No external packages are required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import math
import re


# ---------------------------------------------------------------------------
# Logical design: entities, attributes, relationships, keys, and constraints
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Attribute:
    name: str
    data_type: str
    nullable: bool = False
    description: str = ""


@dataclass(frozen=True)
class ForeignKey:
    columns: Tuple[str, ...]
    referenced_table: str
    referenced_columns: Tuple[str, ...]
    on_delete: str = "RESTRICT"


@dataclass
class LogicalTable:
    name: str
    attributes: List[Attribute]
    primary_key: Tuple[str, ...]
    candidate_keys: List[Tuple[str, ...]] = field(default_factory=list)
    foreign_keys: List[ForeignKey] = field(default_factory=list)

    def attribute_names(self) -> set[str]:
        return {attribute.name for attribute in self.attributes}

    def validate_definition(self) -> List[str]:
        errors: List[str] = []
        names = [attribute.name for attribute in self.attributes]

        if len(names) != len(set(names)):
            errors.append(f"{self.name}: duplicate attribute names")

        if not self.primary_key:
            errors.append(f"{self.name}: primary key is missing")

        missing_pk = set(self.primary_key) - set(names)
        if missing_pk:
            errors.append(
                f"{self.name}: primary-key attributes do not exist: "
                f"{sorted(missing_pk)}"
            )

        for key in self.candidate_keys:
            missing = set(key) - set(names)
            if missing:
                errors.append(
                    f"{self.name}: candidate-key attributes do not exist: "
                    f"{sorted(missing)}"
                )

        for foreign_key in self.foreign_keys:
            if not foreign_key.columns:
                errors.append(f"{self.name}: empty foreign key")
            if len(foreign_key.columns) != len(foreign_key.referenced_columns):
                errors.append(
                    f"{self.name}: foreign-key column counts do not match"
                )
            missing = set(foreign_key.columns) - set(names)
            if missing:
                errors.append(
                    f"{self.name}: foreign-key columns do not exist: "
                    f"{sorted(missing)}"
                )

        return errors


@dataclass
class LogicalSchema:
    tables: Dict[str, LogicalTable]

    def validate(self) -> List[str]:
        errors: List[str] = []

        for table in self.tables.values():
            errors.extend(table.validate_definition())

            for foreign_key in table.foreign_keys:
                if foreign_key.referenced_table not in self.tables:
                    errors.append(
                        f"{table.name}: references unknown table "
                        f"{foreign_key.referenced_table}"
                    )
                    continue

                referenced = self.tables[foreign_key.referenced_table]
                missing = (
                    set(foreign_key.referenced_columns)
                    - referenced.attribute_names()
                )
                if missing:
                    errors.append(
                        f"{table.name}: references unknown columns "
                        f"in {referenced.name}: {sorted(missing)}"
                    )

                if tuple(foreign_key.referenced_columns) != referenced.primary_key:
                    errors.append(
                        f"{table.name}: foreign key references "
                        f"{foreign_key.referenced_table} columns "
                        f"{foreign_key.referenced_columns}, but this model "
                        f"expects its primary key {referenced.primary_key}"
                    )

        return errors

    def print_schema(self) -> None:
        print("\nLOGICAL SCHEMA")
        print("=" * 72)

        for table in self.tables.values():
            print(f"\n{table.name}")
            for attribute in table.attributes:
                nullability = "NULL" if attribute.nullable else "NOT NULL"
                print(
                    f"  {attribute.name:<18} "
                    f"{attribute.data_type:<12} {nullability}"
                )

            print(f"  PK  {', '.join(table.primary_key)}")

            for key in table.candidate_keys:
                print(f"  AK  {', '.join(key)}")

            for foreign_key in table.foreign_keys:
                print(
                    f"  FK  ({', '.join(foreign_key.columns)}) -> "
                    f"{foreign_key.referenced_table}"
                    f"({', '.join(foreign_key.referenced_columns)})"
                )


def build_logical_schema() -> LogicalSchema:
    """
    This model captures business facts without committing to indexes,
    partitioning, page layout, clustering, or a specific storage engine.
    """

    students = LogicalTable(
        name="student",
        attributes=[
            Attribute("student_id", "INTEGER"),
            Attribute("student_number", "VARCHAR(20)"),
            Attribute("full_name", "VARCHAR(120)"),
            Attribute("email", "VARCHAR(254)"),
            Attribute("birth_date", "DATE", nullable=True),
        ],
        primary_key=("student_id",),
        candidate_keys=[("student_number",), ("email",)],
    )

    instructors = LogicalTable(
        name="instructor",
        attributes=[
            Attribute("instructor_id", "INTEGER"),
            Attribute("employee_number", "VARCHAR(20)"),
            Attribute("full_name", "VARCHAR(120)"),
            Attribute("email", "VARCHAR(254)"),
        ],
        primary_key=("instructor_id",),
        candidate_keys=[("employee_number",), ("email",)],
    )

    courses = LogicalTable(
        name="course",
        attributes=[
            Attribute("course_id", "INTEGER"),
            Attribute("course_code", "VARCHAR(20)"),
            Attribute("course_name", "VARCHAR(160)"),
            Attribute("credit_hours", "INTEGER"),
        ],
        primary_key=("course_id",),
        candidate_keys=[("course_code",)],
    )

    terms = LogicalTable(
        name="academic_term",
        attributes=[
            Attribute("term_id", "INTEGER"),
            Attribute("term_code", "VARCHAR(20)"),
            Attribute("start_date", "DATE"),
            Attribute("end_date", "DATE"),
        ],
        primary_key=("term_id",),
        candidate_keys=[("term_code",)],
    )

    sections = LogicalTable(
        name="course_section",
        attributes=[
            Attribute("section_id", "INTEGER"),
            Attribute("course_id", "INTEGER"),
            Attribute("instructor_id", "INTEGER"),
            Attribute("term_id", "INTEGER"),
            Attribute("room_code", "VARCHAR(30)"),
            Attribute("capacity", "INTEGER"),
        ],
        primary_key=("section_id",),
        candidate_keys=[
            ("course_id", "term_id", "instructor_id", "room_code")
        ],
        foreign_keys=[
            ForeignKey(("course_id",), "course", ("course_id",)),
            ForeignKey(("instructor_id",), "instructor", ("instructor_id",)),
            ForeignKey(("term_id",), "academic_term", ("term_id",)),
        ],
    )

    enrollments = LogicalTable(
        name="enrollment",
        attributes=[
            Attribute("student_id", "INTEGER"),
            Attribute("section_id", "INTEGER"),
            Attribute("enrolled_on", "DATE"),
            Attribute("grade", "VARCHAR(2)", nullable=True),
        ],
        primary_key=("student_id", "section_id"),
        foreign_keys=[
            ForeignKey(("student_id",), "student", ("student_id",)),
            ForeignKey(("section_id",), "course_section", ("section_id",)),
        ],
    )

    return LogicalSchema(
        {
            table.name: table
            for table in (
                students,
                instructors,
                courses,
                terms,
                sections,
                enrollments,
            )
        }
    )


# ---------------------------------------------------------------------------
# Functional dependencies and normalization reasoning
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FunctionalDependency:
    determinant: Tuple[str, ...]
    dependent: Tuple[str, ...]

    def __str__(self) -> str:
        return f"{', '.join(self.determinant)} -> {', '.join(self.dependent)}"


def demonstrate_normalization() -> None:
    print("\nNORMALIZATION CASE STUDY")
    print("=" * 72)

    print(
        "\nAn unnormalized reporting row might contain student, course, "
        "instructor, term, and enrollment facts together."
    )

    print(
        "\nFunctional dependencies for the normalized enrollment design:"
    )

    dependencies = [
        FunctionalDependency(("student_id",), ("student_number", "email")),
        FunctionalDependency(("course_id",), ("course_code", "course_name")),
        FunctionalDependency(
            ("section_id",),
            ("course_id", "instructor_id", "term_id", "capacity"),
        ),
        FunctionalDependency(
            ("student_id", "section_id"),
            ("enrolled_on", "grade"),
        ),
    ]

    for dependency in dependencies:
        print(f"  {dependency}")

    print(
        "\nThe enrollment primary key is composite because an enrollment "
        "belongs to the combination of one student and one section."
    )

    print(
        "\nSeparating student, course, instructor, section, term, and "
        "enrollment facts prevents update anomalies."
    )

    print(
        "\nControlled denormalization can still be appropriate for a "
        "read-heavy reporting workload, but it should be an intentional "
        "physical or derived representation rather than accidental duplication."
    )


# ---------------------------------------------------------------------------
# Physical design: indexes, partitioning, storage, and access paths
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IndexDefinition:
    name: str
    table: str
    columns: Tuple[str, ...]
    unique: bool = False
    partial_predicate: Optional[str] = None

    def estimated_key_width(self, column_widths: Dict[str, int]) -> int:
        return sum(column_widths.get(column, 8) for column in self.columns)


@dataclass
class PhysicalDesign:
    indexes: List[IndexDefinition]
    partitioning: Dict[str, str]
    storage_notes: Dict[str, str]

    def indexes_for_table(self, table: str) -> List[IndexDefinition]:
        return [index for index in self.indexes if index.table == table]


def build_physical_design() -> PhysicalDesign:
    """
    Physical design answers questions that do not change the business model:
    which access paths exist, how data is distributed, and what storage
    characteristics are appropriate for the workload.
    """

    return PhysicalDesign(
        indexes=[
            IndexDefinition(
                "ux_student_student_number",
                "student",
                ("student_number",),
                unique=True,
            ),
            IndexDefinition(
                "ux_student_email",
                "student",
                ("email",),
                unique=True,
            ),
            IndexDefinition(
                "ix_section_term_course",
                "course_section",
                ("term_id", "course_id"),
            ),
            IndexDefinition(
                "ix_section_instructor_term",
                "course_section",
                ("instructor_id", "term_id"),
            ),
            IndexDefinition(
                "ix_enrollment_section_student",
                "enrollment",
                ("section_id", "student_id"),
            ),
            IndexDefinition(
                "ix_enrollment_student_section",
                "enrollment",
                ("student_id", "section_id"),
            ),
        ],
        partitioning={
            "enrollment": "RANGE by academic term through a derived term key",
            "course_section": "RANGE by academic term when section volume warrants it",
        },
        storage_notes={
            "student": "OLTP row storage; frequent point lookups and updates",
            "course_section": "OLTP row storage; indexed term-based access",
            "enrollment": "High-volume relationship table; consider partitioning only after workload evidence",
        },
    )


def print_physical_design(design: PhysicalDesign) -> None:
    print("\nPHYSICAL DESIGN")
    print("=" * 72)

    print("\nIndexes:")
    for index in design.indexes:
        uniqueness = "UNIQUE " if index.unique else ""
        predicate = (
            f" WHERE {index.partial_predicate}"
            if index.partial_predicate
            else ""
        )
        print(
            f"  {index.name}: {uniqueness}{index.table}"
            f"({', '.join(index.columns)}){predicate}"
        )

    print("\nPartitioning decisions:")
    for table, strategy in design.partitioning.items():
        print(f"  {table}: {strategy}")

    print("\nStorage notes:")
    for table, note in design.storage_notes.items():
        print(f"  {table}: {note}")


# ---------------------------------------------------------------------------
# Query workload analysis
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class QueryPattern:
    name: str
    table: str
    predicates: Tuple[str, ...]
    expected_frequency_per_day: int
    priority: str


def recommend_access_paths(
    queries: Sequence[QueryPattern],
    design: PhysicalDesign,
) -> None:
    print("\nWORKLOAD-DRIVEN DESIGN")
    print("=" * 72)

    for query in queries:
        matching = [
            index
            for index in design.indexes_for_table(query.table)
            if all(predicate in index.columns for predicate in query.predicates)
        ]

        print(f"\n{query.name}")
        print(f"  Table: {query.table}")
        print(f"  Predicates: {', '.join(query.predicates)}")
        print(f"  Frequency/day: {query.expected_frequency_per_day}")
        print(f"  Priority: {query.priority}")

        if matching:
            print("  Candidate access paths:")
            for index in matching:
                print(f"    {index.name}")
        else:
            print("  Candidate access paths: none in current physical design")
            print(
                "  Decision: investigate workload and query plans before "
                "creating another index."
            )


# ---------------------------------------------------------------------------
# Integrity and validation
# ---------------------------------------------------------------------------

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class IntegrityError(ValueError):
    """Raised when a simulated database operation violates a business rule."""


@dataclass
class EnrollmentStore:
    students: Dict[int, Dict[str, object]]
    sections: Dict[int, Dict[str, object]]
    enrollments: Dict[Tuple[int, int], Dict[str, object]]

    def add_student(
        self,
        student_id: int,
        student_number: str,
        full_name: str,
        email: str,
        birth_date: Optional[date] = None,
    ) -> None:
        if student_id <= 0:
            raise IntegrityError("student_id must be positive")

        if not student_number.strip():
            raise IntegrityError("student_number cannot be empty")

        if not EMAIL_PATTERN.match(email):
            raise IntegrityError("email format is invalid")

        if student_id in self.students:
            raise IntegrityError("student primary key already exists")

        if any(
            row["student_number"] == student_number
            for row in self.students.values()
        ):
            raise IntegrityError("student_number must be unique")

        if any(row["email"] == email for row in self.students.values()):
            raise IntegrityError("email must be unique")

        self.students[student_id] = {
            "student_number": student_number,
            "full_name": full_name.strip(),
            "email": email,
            "birth_date": birth_date,
        }

    def add_section(
        self,
        section_id: int,
        course_id: int,
        instructor_id: int,
        term_id: int,
        room_code: str,
        capacity: int,
    ) -> None:
        if section_id <= 0:
            raise IntegrityError("section_id must be positive")

        if capacity <= 0:
            raise IntegrityError("capacity must be greater than zero")

        if section_id in self.sections:
            raise IntegrityError("section primary key already exists")

        self.sections[section_id] = {
            "course_id": course_id,
            "instructor_id": instructor_id,
            "term_id": term_id,
            "room_code": room_code,
            "capacity": capacity,
        }

    def enroll(
        self,
        student_id: int,
        section_id: int,
        enrolled_on: date,
    ) -> None:
        if student_id not in self.students:
            raise IntegrityError("foreign-key violation: student does not exist")

        if section_id not in self.sections:
            raise IntegrityError("foreign-key violation: section does not exist")

        key = (student_id, section_id)

        if key in self.enrollments:
            raise IntegrityError(
                "duplicate enrollment violates the composite primary key"
            )

        section = self.sections[section_id]
        current_count = sum(
            1
            for enrollment in self.enrollments.values()
            if enrollment["section_id"] == section_id
        )

        if current_count >= int(section["capacity"]):
            raise IntegrityError("section capacity has been reached")

        self.enrollments[key] = {
            "enrolled_on": enrolled_on,
            "grade": None,
        }

    def assign_grade(
        self,
        student_id: int,
        section_id: int,
        grade: str,
    ) -> None:
        allowed = {"A+", "A", "B+", "B", "C+", "C", "D", "F", "I"}

        if grade not in allowed:
            raise IntegrityError(f"unsupported grade: {grade}")

        key = (student_id, section_id)

        if key not in self.enrollments:
            raise IntegrityError("cannot grade a missing enrollment")

        self.enrollments[key]["grade"] = grade

    def enrollments_for_student(self, student_id: int) -> List[Dict[str, object]]:
        return [
            {
                "student_id": student_id,
                "section_id": section_id,
                **record,
            }
            for (stored_student_id, section_id), record in self.enrollments.items()
            if stored_student_id == student_id
        ]


# ---------------------------------------------------------------------------
# Cardinality and relationship reasoning
# ---------------------------------------------------------------------------

def demonstrate_relationships() -> None:
    print("\nRELATIONSHIP DESIGN")
    print("=" * 72)

    print(
        "\nStudent -> Enrollment is one-to-many: one student can have "
        "many enrollment records."
    )

    print(
        "Section -> Enrollment is one-to-many: one section can contain "
        "many students."
    )

    print(
        "Student <-> Section is therefore many-to-many, represented by "
        "the enrollment associative entity."
    )

    print(
        "\nThe enrollment composite key (student_id, section_id) prevents "
        "the same student from being enrolled in the same section twice."
    )


# ---------------------------------------------------------------------------
# Capacity and performance calculations
# ---------------------------------------------------------------------------

def estimate_index_storage(
    row_count: int,
    key_width_bytes: int,
    pointer_bytes: int = 8,
    overhead_fraction: float = 0.15,
) -> float:
    """
    This is a planning estimate, not a storage-engine measurement.
    Real indexes include page headers, alignment, tree structure,
    fill factor, visibility metadata, and implementation-specific overhead.
    """
    if row_count < 0:
        raise ValueError("row_count cannot be negative")
    if key_width_bytes <= 0:
        raise ValueError("key_width_bytes must be positive")
    if pointer_bytes <= 0:
        raise ValueError("pointer_bytes must be positive")
    if not 0 <= overhead_fraction <= 1:
        raise ValueError("overhead_fraction must be between zero and one")

    base = row_count * (key_width_bytes + pointer_bytes)
    return base * (1 + overhead_fraction)


def compare_selectivity(
    total_rows: int,
    matching_rows: int,
) -> float:
    if total_rows <= 0:
        raise ValueError("total_rows must be positive")
    if not 0 <= matching_rows <= total_rows:
        raise ValueError("matching_rows must be within the table cardinality")

    return matching_rows / total_rows


def demonstrate_performance() -> None:
    print("\nPHYSICAL PERFORMANCE TRADE-OFFS")
    print("=" * 72)

    total_enrollments = 2_000_000
    matching_rows = 4_000

    selectivity = compare_selectivity(
        total_enrollments,
        matching_rows,
    )

    estimated_index_bytes = estimate_index_storage(
        row_count=total_enrollments,
        key_width_bytes=8,
    )

    print(f"\nEnrollment rows: {total_enrollments:,}")
    print(f"Rows matching a student lookup: {matching_rows:,}")
    print(f"Estimated selectivity: {selectivity:.4%}")
    print(
        "A selective index can substantially reduce rows examined for "
        "point or narrow-range lookups."
    )
    print(
        "Estimated index storage: "
        f"{estimated_index_bytes / (1024 ** 2):,.1f} MiB"
    )

    print(
        "\nThe estimate illustrates an important physical-design trade-off: "
        "indexes improve read access but consume storage and impose write "
        "maintenance whenever indexed rows change."
    )


# ---------------------------------------------------------------------------
# Bad design demonstration
# ---------------------------------------------------------------------------

def demonstrate_design_anomaly() -> None:
    print("\nBAD DESIGN AND UPDATE ANOMALY")
    print("=" * 72)

    denormalized_rows = [
        {
            "student_number": "S1001",
            "student_name": "Asha Rao",
            "course_code": "CS301",
            "course_name": "Database Systems",
            "instructor": "Dr. Mehta",
        },
        {
            "student_number": "S1002",
            "student_name": "Ravi Shah",
            "course_code": "CS301",
            "course_name": "Database Systems",
            "instructor": "Dr. Mehta",
        },
        {
            "student_number": "S1003",
            "student_name": "Neha Singh",
            "course_code": "CS301",
            "course_name": "Database Systems",
            "instructor": "Dr. Mehta",
        },
    ]

    print("\nRepeated course facts:")
    for row in denormalized_rows:
        print(
            f"  {row['student_number']}: "
            f"{row['course_code']} = {row['course_name']}"
        )

    print(
        "\nIf the course name changes, every duplicated row must be updated. "
        "Missing one row creates contradictory facts."
    )

    print(
        "Separating course facts into a course relation makes course_name "
        "dependent on course_id rather than on each enrollment occurrence."
    )


# ---------------------------------------------------------------------------
# Design objective evaluation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DesignObjective:
    name: str
    measurement: str
    target: str


def print_design_objectives() -> None:
    objectives = [
        DesignObjective(
            "Integrity",
            "constraint violations and invalid references",
            "zero accepted invalid foreign keys or duplicate keys",
        ),
        DesignObjective(
            "Performance",
            "latency for representative query patterns",
            "measure with realistic query plans and production-like data",
        ),
        DesignObjective(
            "Maintainability",
            "complexity of schema changes and duplicated business facts",
            "business facts have clear ownership",
        ),
        DesignObjective(
            "Scalability",
            "growth in rows, concurrent access, and operational workload",
            "growth remains predictable under measured workloads",
        ),
        DesignObjective(
            "Storage efficiency",
            "table, index, and historical-data footprint",
            "avoid indexes and duplicated attributes without workload justification",
        ),
        DesignObjective(
            "Security",
            "least-privilege access and exposure of sensitive attributes",
            "users receive only the data operations they require",
        ),
    ]

    print("\nDATABASE DESIGN OBJECTIVES")
    print("=" * 72)

    for objective in objectives:
        print(f"\n{objective.name}")
        print(f"  Measurement: {objective.measurement}")
        print(f"  Target: {objective.target}")


# ---------------------------------------------------------------------------
# Security-specific physical considerations
# ---------------------------------------------------------------------------

def demonstrate_security_boundaries() -> None:
    print("\nSECURITY DESIGN CONSIDERATIONS")
    print("=" * 72)

    print(
        "\nLogical design identifies sensitive attributes such as email and "
        "birth_date. Physical implementation must then determine who can "
        "read or modify them."
    )

    print(
        "\nA reporting role might receive access to course and enrollment "
        "facts without receiving direct access to personal student attributes."
    )

    print(
        "\nSecurity is not solved by hiding a column from application code. "
        "Database privileges, views, row-level policies where supported, "
        "parameterized statements, encryption controls, and auditing form "
        "the operational boundary."
    )

    print(
        "\nLeast privilege also affects schema design: separating data by "
        "responsibility can make access policies easier to express and audit."
    )


# ---------------------------------------------------------------------------
# Schema evolution
# ---------------------------------------------------------------------------

def demonstrate_schema_evolution() -> None:
    print("\nSCHEMA EVOLUTION")
    print("=" * 72)

    print(
        "\nSuppose the university introduces a section status such as "
        "'planned', 'open', 'closed', or 'cancelled'."
    )

    print(
        "The logical change adds a business attribute to course_section. "
        "The physical migration must then consider existing rows, a default "
        "value, deployment order, index impact, and application compatibility."
    )

    print(
        "\nA safe migration commonly separates compatibility concerns from "
        "the final constraint state. Existing data must satisfy the new "
        "constraint before the database can reliably enforce it."
    )


# ---------------------------------------------------------------------------
# Transaction-like behavior for a batch enrollment operation
# ---------------------------------------------------------------------------

class EnrollmentBatch:
    """
    A small in-memory transaction simulation.

    Real database transactions provide atomicity, isolation, durability,
    and recovery semantics that this Python object does not reproduce.
    This class demonstrates the design principle that a multi-row business
    operation should not leave half-applied state when validation fails.
    """

    def __init__(self, store: EnrollmentStore):
        self.store = store
        self._enrollments_before = dict(store.enrollments)
        self._active = True

    def enroll_many(
        self,
        requests: Iterable[Tuple[int, int, date]],
    ) -> None:
        if not self._active:
            raise RuntimeError("batch is no longer active")

        try:
            for student_id, section_id, enrolled_on in requests:
                self.store.enroll(
                    student_id,
                    section_id,
                    enrolled_on,
                )
        except Exception:
            self.store.enrollments = self._enrollments_before
            self._active = False
            raise

    def commit(self) -> None:
        if not self._active:
            raise RuntimeError("cannot commit inactive batch")
        self._active = False


# ---------------------------------------------------------------------------
# Main case study
# ---------------------------------------------------------------------------

def run_case_study() -> None:
    print("DATABASE DESIGN PRINCIPLES")
    print("=" * 72)
    print(
        "Case study: an academic enrollment system designed from business "
        "requirements through logical modeling and physical optimization."
    )

    logical_schema = build_logical_schema()
    errors = logical_schema.validate()

    print("\nLOGICAL SCHEMA VALIDATION")
    print("=" * 72)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise RuntimeError("logical schema validation failed")

    print("Logical schema is internally consistent.")
    logical_schema.print_schema()

    demonstrate_relationships()
    demonstrate_normalization()
    demonstrate_design_anomaly()

    physical_design = build_physical_design()
    print_physical_design(physical_design)

    workload = [
        QueryPattern(
            name="Find all courses taken by a student",
            table="enrollment",
            predicates=("student_id",),
            expected_frequency_per_day=25_000,
            priority="high",
        ),
        QueryPattern(
            name="Find students enrolled in a section",
            table="enrollment",
            predicates=("section_id",),
            expected_frequency_per_day=18_000,
            priority="high",
        ),
        QueryPattern(
            name="Find sections for a course in a term",
            table="course_section",
            predicates=("term_id", "course_id"),
            expected_frequency_per_day=7_500,
            priority="high",
        ),
        QueryPattern(
            name="Find a student by email",
            table="student",
            predicates=("email",),
            expected_frequency_per_day=40_000,
            priority="critical",
        ),
        QueryPattern(
            name="Find sections by room only",
            table="course_section",
            predicates=("room_code",),
            expected_frequency_per_day=100,
            priority="low",
        ),
    ]

    recommend_access_paths(workload, physical_design)
    demonstrate_performance()

    print("\nINTEGRITY ENFORCEMENT SIMULATION")
    print("=" * 72)

    store = EnrollmentStore(
        students={},
        sections={},
        enrollments={},
    )

    store.add_student(
        student_id=1,
        student_number="S1001",
        full_name="Asha Rao",
        email="asha.rao@example.edu",
    )
    store.add_student(
        student_id=2,
        student_number="S1002",
        full_name="Ravi Shah",
        email="ravi.shah@example.edu",
    )

    store.add_section(
        section_id=501,
        course_id=301,
        instructor_id=77,
        term_id=20261,
        room_code="DB-204",
        capacity=2,
    )

    store.enroll(1, 501, date(2026, 8, 15))
    store.assign_grade(1, 501, "A")

    print("Valid enrollment and grade assignment succeeded.")

    try:
        store.enroll(1, 501, date(2026, 8, 16))
    except IntegrityError as exc:
        print(f"Expected constraint failure: {exc}")

    try:
        store.add_student(
            student_id=3,
            student_number="S1003",
            full_name="Invalid Student",
            email="not-an-email",
        )
    except IntegrityError as exc:
        print(f"Expected validation failure: {exc}")

    print("\nEnrollment rows for S1001:")
    for row in store.enrollments_for_student(1):
        print(f"  {row}")

    print("\nBATCH ATOMICITY SIMULATION")
    print("=" * 72)

    batch = EnrollmentBatch(store)

    try:
        batch.enroll_many(
            [
                (2, 501, date(2026, 8, 16)),
                (1, 999, date(2026, 8, 16)),
            ]
        )
        batch.commit()
    except IntegrityError as exc:
        print(f"Batch rejected: {exc}")
        print(
            "The successful first operation was rolled back in the "
            "simulation because the second operation failed."
        )

    print(
        f"Enrollment count after rollback: {len(store.enrollments)}"
    )

    demonstrate_security_boundaries()
    demonstrate_schema_evolution()
    print_design_objectives()

    print("\nDESIGN DECISION")
    print("=" * 72)
    print(
        "The logical model keeps business facts separated according to "
        "entities, relationships, keys, and dependencies. The physical "
        "model adds access paths and storage decisions based on measured "
        "workload rather than changing the meaning of those facts."
    )

    print(
        "\nA database design is successful when its constraints preserve "
        "correctness while its physical implementation meets measurable "
        "performance, storage, security, operational, and scalability goals."
    )


if __name__ == "__main__":
    run_case_study()
