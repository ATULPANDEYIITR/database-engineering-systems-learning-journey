"""
Cardinality: One-to-One, One-to-Many, Many-to-Many

A self-contained progression from basic relationship modeling to a small
in-memory relational data model with validation, querying, mutation, and
integrity checks.

The examples use a university registration domain because the relationship
types are naturally distinct:

- One-to-one: Student <-> StudentProfile
- One-to-many: Department -> Course
- Many-to-many: Student <-> Course through Enrollment
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# One-to-one relationship
# ---------------------------------------------------------------------------

@dataclass
class StudentProfile:
    """The profile belongs to exactly one student in this model."""
    profile_id: str
    student_id: str
    phone: str
    city: str


@dataclass
class Student:
    """A student has at most one profile and can enroll in many courses."""
    student_id: str
    name: str
    email: str
    profile_id: Optional[str] = None
    course_ids: Set[str] = field(default_factory=set)


def demonstrate_one_to_one() -> None:
    print("\n=== ONE-TO-ONE ===")

    student = Student(
        student_id="S100",
        name="Atul Pandey",
        email="atul@example.edu",
    )

    profile = StudentProfile(
        profile_id="P100",
        student_id="S100",
        phone="+91-9876543210",
        city="Lucknow",
    )

    # The foreign-key-like reference lives on the student side.
    student.profile_id = profile.profile_id

    print(f"Student: {student.name}")
    print(f"Profile: {profile.profile_id}")
    print(f"Student -> Profile: {student.profile_id}")
    print(f"Profile -> Student: {profile.student_id}")

    # A one-to-one constraint means another profile cannot legitimately
    # claim the same student if profile ownership is unique.
    second_profile = StudentProfile(
        profile_id="P101",
        student_id="S100",
        phone="+91-9000000000",
        city="Delhi",
    )

    if second_profile.student_id == student.student_id:
        print("Rejected: a second profile would violate one-to-one cardinality.")


# ---------------------------------------------------------------------------
# One-to-many relationship
# ---------------------------------------------------------------------------

@dataclass
class Department:
    department_id: str
    name: str
    course_ids: Set[str] = field(default_factory=set)


@dataclass
class Course:
    course_id: str
    title: str
    department_id: str


def demonstrate_one_to_many() -> None:
    print("\n=== ONE-TO-MANY ===")

    department = Department("D10", "Computer Science")

    courses = [
        Course("C101", "Database Systems", department.department_id),
        Course("C102", "Distributed Systems", department.department_id),
        Course("C103", "Software Engineering", department.department_id),
    ]

    for course in courses:
        department.course_ids.add(course.course_id)

    print(f"Department: {department.name}")
    print("Courses owned by the department:")

    for course in courses:
        print(f"  {course.course_id}: {course.title}")

    # Many Course records may reference one Department.
    print(
        f"One department -> {len(department.course_ids)} courses "
        "(one-to-many)."
    )


# ---------------------------------------------------------------------------
# Many-to-many relationship
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Enrollment:
    """
    Associative entity for the many-to-many Student <-> Course relationship.

    A student may have many enrollments, and a course may have many students.
    The pair (student_id, course_id) is unique.
    """
    student_id: str
    course_id: str
    enrolled_on: date
    grade: Optional[str] = None


def demonstrate_many_to_many() -> None:
    print("\n=== MANY-TO-MANY ===")

    students = {
        "S100": Student("S100", "Atul Pandey", "atul@example.edu"),
        "S101": Student("S101", "Priya Sharma", "priya@example.edu"),
        "S102": Student("S102", "Rahul Singh", "rahul@example.edu"),
    }

    courses = {
        "C101": Course("C101", "Database Systems", "D10"),
        "C102": Course("C102", "Distributed Systems", "D10"),
        "C103": Course("C103", "Software Engineering", "D10"),
    }

    enrollments: Set[Enrollment] = {
        Enrollment("S100", "C101", date(2026, 9, 1)),
        Enrollment("S100", "C102", date(2026, 9, 1)),
        Enrollment("S101", "C101", date(2026, 9, 2)),
        Enrollment("S101", "C103", date(2026, 9, 2)),
        Enrollment("S102", "C101", date(2026, 9, 3)),
    }

    for enrollment in enrollments:
        students[enrollment.student_id].course_ids.add(enrollment.course_id)

    for student in students.values():
        course_names = [
            courses[course_id].title
            for course_id in sorted(student.course_ids)
        ]
        print(f"{student.name}: {', '.join(course_names)}")

    print("The Enrollment entity resolves the many-to-many relationship.")


# ---------------------------------------------------------------------------
# Generic cardinality-aware repository
# ---------------------------------------------------------------------------

class CardinalityError(ValueError):
    """Raised when an operation would violate relationship cardinality."""


class NotFoundError(KeyError):
    """Raised when a referenced entity does not exist."""


class UniversityRepository:
    """
    In-memory model of three relationship types.

    Integrity rules:
      * Every profile references one existing student.
      * A student has at most one profile.
      * Every course references one existing department.
      * A department can own many courses.
      * Every enrollment references one existing student and course.
      * A student-course enrollment pair is unique.
    """

    def __init__(self) -> None:
        self.students: Dict[str, Student] = {}
        self.profiles: Dict[str, StudentProfile] = {}
        self.departments: Dict[str, Department] = {}
        self.courses: Dict[str, Course] = {}
        self.enrollments: Set[Enrollment] = set()

    # ----- entity creation -------------------------------------------------

    def add_student(self, student: Student) -> None:
        self._require_new_id(self.students, student.student_id, "student")
        self.students[student.student_id] = student

    def add_department(self, department: Department) -> None:
        self._require_new_id(
            self.departments,
            department.department_id,
            "department",
        )
        self.departments[department.department_id] = department

    def add_profile(self, profile: StudentProfile) -> None:
        self._require_reference(
            self.students,
            profile.student_id,
            "student",
        )
        self._require_new_id(self.profiles, profile.profile_id, "profile")

        # This set of checks represents the unique constraint required for
        # the one-to-one side of the relationship.
        existing_profile = next(
            (
                item
                for item in self.profiles.values()
                if item.student_id == profile.student_id
            ),
            None,
        )

        if existing_profile is not None:
            raise CardinalityError(
                f"Student {profile.student_id} already has profile "
                f"{existing_profile.profile_id}."
            )

        self.profiles[profile.profile_id] = profile
        self.students[profile.student_id].profile_id = profile.profile_id

    def add_course(self, course: Course) -> None:
        self._require_reference(
            self.departments,
            course.department_id,
            "department",
        )
        self._require_new_id(self.courses, course.course_id, "course")

        self.courses[course.course_id] = course
        self.departments[course.department_id].course_ids.add(
            course.course_id
        )

    def enroll(
        self,
        student_id: str,
        course_id: str,
        enrolled_on: date,
        grade: Optional[str] = None,
    ) -> Enrollment:
        self._require_reference(self.students, student_id, "student")
        self._require_reference(self.courses, course_id, "course")

        # The pair is the logical key of the associative relationship.
        if any(
            item.student_id == student_id and item.course_id == course_id
            for item in self.enrollments
        ):
            raise CardinalityError(
                f"{student_id} is already enrolled in {course_id}."
            )

        enrollment = Enrollment(
            student_id=student_id,
            course_id=course_id,
            enrolled_on=enrolled_on,
            grade=grade,
        )

        self.enrollments.add(enrollment)
        self.students[student_id].course_ids.add(course_id)
        return enrollment

    # ----- relationship queries ------------------------------------------

    def get_student_profile(self, student_id: str) -> Optional[StudentProfile]:
        self._require_reference(self.students, student_id, "student")

        profile_id = self.students[student_id].profile_id
        if profile_id is None:
            return None

        return self.profiles[profile_id]

    def get_department_courses(self, department_id: str) -> List[Course]:
        self._require_reference(
            self.departments,
            department_id,
            "department",
        )

        return [
            self.courses[course_id]
            for course_id in sorted(
                self.departments[department_id].course_ids
            )
        ]

    def get_student_courses(self, student_id: str) -> List[Course]:
        self._require_reference(self.students, student_id, "student")

        return [
            self.courses[course_id]
            for course_id in sorted(self.students[student_id].course_ids)
        ]

    def get_course_students(self, course_id: str) -> List[Student]:
        self._require_reference(self.courses, course_id, "course")

        student_ids = {
            enrollment.student_id
            for enrollment in self.enrollments
            if enrollment.course_id == course_id
        }

        return [
            self.students[student_id]
            for student_id in sorted(student_ids)
        ]

    def find_common_courses(
        self,
        first_student_id: str,
        second_student_id: str,
    ) -> Set[str]:
        """
        A many-to-many query can be expressed as set intersection.

        This avoids scanning every course after the relationship has already
        been represented as student -> course IDs.
        """
        self._require_reference(
            self.students,
            first_student_id,
            "student",
        )
        self._require_reference(
            self.students,
            second_student_id,
            "student",
        )

        first = self.students[first_student_id].course_ids
        second = self.students[second_student_id].course_ids

        return first & second

    # ----- mutation -------------------------------------------------------

    def remove_enrollment(self, student_id: str, course_id: str) -> None:
        matching = next(
            (
                item
                for item in self.enrollments
                if item.student_id == student_id
                and item.course_id == course_id
            ),
            None,
        )

        if matching is None:
            raise NotFoundError(
                f"No enrollment exists for {student_id} and {course_id}."
            )

        self.enrollments.remove(matching)
        self.students[student_id].course_ids.discard(course_id)

    # ----- integrity checking --------------------------------------------

    def validate_integrity(self) -> List[str]:
        """
        Performs explicit relationship consistency checks.

        Real relational databases normally enforce these constraints through
        foreign keys, UNIQUE constraints, and transaction semantics.
        """
        errors: List[str] = []

        # One-to-one consistency.
        profile_owners: Dict[str, int] = {}

        for profile in self.profiles.values():
            if profile.student_id not in self.students:
                errors.append(
                    f"Profile {profile.profile_id} references missing "
                    f"student {profile.student_id}."
                )

            profile_owners[profile.student_id] = (
                profile_owners.get(profile.student_id, 0) + 1
            )

        for student_id, count in profile_owners.items():
            if count > 1:
                errors.append(
                    f"Student {student_id} has {count} profiles; "
                    "one-to-one cardinality requires at most one."
                )

        # One-to-many consistency.
        for course in self.courses.values():
            if course.department_id not in self.departments:
                errors.append(
                    f"Course {course.course_id} references missing "
                    f"department {course.department_id}."
                )
            else:
                department = self.departments[course.department_id]
                if course.course_id not in department.course_ids:
                    errors.append(
                        f"Department {department.department_id} is missing "
                        f"course {course.course_id} from its reverse index."
                    )

        # Many-to-many consistency.
        seen_pairs: Set[Tuple[str, str]] = set()

        for enrollment in self.enrollments:
            pair = (enrollment.student_id, enrollment.course_id)

            if pair in seen_pairs:
                errors.append(
                    f"Duplicate enrollment pair: "
                    f"{enrollment.student_id}/{enrollment.course_id}."
                )

            seen_pairs.add(pair)

            if enrollment.student_id not in self.students:
                errors.append(
                    f"Enrollment references missing student "
                    f"{enrollment.student_id}."
                )

            if enrollment.course_id not in self.courses:
                errors.append(
                    f"Enrollment references missing course "
                    f"{enrollment.course_id}."
                )

        return errors

    # ----- helpers --------------------------------------------------------

    @staticmethod
    def _require_new_id(
        collection: Dict[str, object],
        identifier: str,
        entity_name: str,
    ) -> None:
        if identifier in collection:
            raise CardinalityError(
                f"{entity_name.title()} ID {identifier} already exists."
            )

    @staticmethod
    def _require_reference(
        collection: Dict[str, object],
        identifier: str,
        entity_name: str,
    ) -> None:
        if identifier not in collection:
            raise NotFoundError(
                f"{entity_name.title()} {identifier} does not exist."
            )


# ---------------------------------------------------------------------------
# Relational-style table representation
# ---------------------------------------------------------------------------

def display_relationship_tables(repository: UniversityRepository) -> None:
    print("\n=== RELATIONAL REPRESENTATION ===")

    print("\nStudents")
    for student in repository.students.values():
        print(
            f"  {student.student_id} | "
            f"{student.name} | "
            f"profile={student.profile_id}"
        )

    print("\nStudent Profiles")
    for profile in repository.profiles.values():
        print(
            f"  {profile.profile_id} | "
            f"student={profile.student_id} | "
            f"{profile.city}"
        )

    print("\nDepartments")
    for department in repository.departments.values():
        print(
            f"  {department.department_id} | "
            f"{department.name}"
        )

    print("\nCourses")
    for course in repository.courses.values():
        print(
            f"  {course.course_id} | "
            f"{course.title} | "
            f"department={course.department_id}"
        )

    print("\nEnrollments")
    for enrollment in sorted(
        repository.enrollments,
        key=lambda item: (item.student_id, item.course_id),
    ):
        print(
            f"  {enrollment.student_id} | "
            f"{enrollment.course_id} | "
            f"{enrollment.enrolled_on} | "
            f"grade={enrollment.grade or '-'}"
        )


# ---------------------------------------------------------------------------
# Failure demonstrations
# ---------------------------------------------------------------------------

def demonstrate_failures(repository: UniversityRepository) -> None:
    print("\n=== CARDINALITY VIOLATIONS AND FAILURE HANDLING ===")

    try:
        repository.add_profile(
            StudentProfile(
                profile_id="P999",
                student_id="S100",
                phone="+91-1111111111",
                city="Mumbai",
            )
        )
    except CardinalityError as exc:
        print(f"One-to-one violation caught: {exc}")

    try:
        repository.add_course(
            Course(
                course_id="C999",
                title="Invalid Course",
                department_id="D404",
            )
        )
    except NotFoundError as exc:
        print(f"One-to-many reference violation caught: {exc}")

    try:
        repository.enroll(
            student_id="S100",
            course_id="C101",
            enrolled_on=date.today(),
        )
    except CardinalityError as exc:
        print(f"Many-to-many duplicate relationship caught: {exc}")

    try:
        repository.enroll(
            student_id="S404",
            course_id="C101",
            enrolled_on=date.today(),
        )
    except NotFoundError as exc:
        print(f"Foreign-reference violation caught: {exc}")


# ---------------------------------------------------------------------------
# Small executable test suite
# ---------------------------------------------------------------------------

def run_assertions(repository: UniversityRepository) -> None:
    assert repository.get_student_profile("S100") is not None

    course_ids = {
        course.course_id
        for course in repository.get_department_courses("D10")
    }
    assert course_ids == {"C101", "C102", "C103"}

    student_course_ids = {
        course.course_id
        for course in repository.get_student_courses("S100")
    }
    assert student_course_ids == {"C101", "C102"}

    course_student_ids = {
        student.student_id
        for student in repository.get_course_students("C101")
    }
    assert course_student_ids == {"S100", "S101", "S102"}

    assert repository.find_common_courses("S100", "S101") == {"C101"}

    before = len(repository.enrollments)
    repository.remove_enrollment("S100", "C102")
    assert len(repository.enrollments) == before - 1

    assert not repository.validate_integrity()

    # Restore the relationship so the final state remains representative.
    repository.enroll(
        "S100",
        "C102",
        date(2026, 9, 1),
    )

    assert not repository.validate_integrity()


# ---------------------------------------------------------------------------
# Advanced discussion through executable measurements
# ---------------------------------------------------------------------------

def demonstrate_lookup_performance(repository: UniversityRepository) -> None:
    print("\n=== REPRESENTATION AND PERFORMANCE ===")

    enrollment_count = len(repository.enrollments)
    print(f"Enrollment rows: {enrollment_count}")

    # The direct student.course_ids index provides approximately O(k) access
    # for a student's courses, where k is that student's relationship count.
    student = repository.students["S100"]
    print(
        f"Student S100 stores {len(student.course_ids)} course references "
        "directly."
    )

    # The set representation also makes membership checks average O(1).
    print(
        "Set membership provides average O(1) membership testing, while "
        "a list would require a linear scan."
    )

    # The Enrollment set prevents duplicate identical records at the Python
    # object level, while the repository's pair check enforces the business
    # key explicitly.
    print(
        "The enrollment pair (student_id, course_id) acts as a logical "
        "composite key."
    )


# ---------------------------------------------------------------------------
# Main demonstration
# ---------------------------------------------------------------------------

def build_sample_repository() -> UniversityRepository:
    repository = UniversityRepository()

    repository.add_student(
        Student("S100", "Atul Pandey", "atul@example.edu")
    )
    repository.add_student(
        Student("S101", "Priya Sharma", "priya@example.edu")
    )
    repository.add_student(
        Student("S102", "Rahul Singh", "rahul@example.edu")
    )

    repository.add_department(
        Department("D10", "Computer Science")
    )
    repository.add_department(
        Department("D20", "Management")
    )

    repository.add_profile(
        StudentProfile(
            "P100",
            "S100",
            "+91-9876543210",
            "Lucknow",
        )
    )
    repository.add_profile(
        StudentProfile(
            "P101",
            "S101",
            "+91-9123456780",
            "Delhi",
        )
    )

    repository.add_course(
        Course("C101", "Database Systems", "D10")
    )
    repository.add_course(
        Course("C102", "Distributed Systems", "D10")
    )
    repository.add_course(
        Course("C103", "Software Engineering", "D10")
    )
    repository.add_course(
        Course("C201", "Product Management", "D20")
    )

    repository.enroll("S100", "C101", date(2026, 9, 1))
    repository.enroll("S100", "C102", date(2026, 9, 1))
    repository.enroll("S101", "C101", date(2026, 9, 2))
    repository.enroll("S101", "C103", date(2026, 9, 2))
    repository.enroll("S102", "C101", date(2026, 9, 3))
    repository.enroll("S102", "C201", date(2026, 9, 3))

    return repository


def main() -> None:
    print("CARDINALITY: RELATIONSHIP MODELING")

    demonstrate_one_to_one()
    demonstrate_one_to_many()
    demonstrate_many_to_many()

    repository = build_sample_repository()

    display_relationship_tables(repository)

    print("\n=== RELATIONSHIP QUERIES ===")

    profile = repository.get_student_profile("S100")
    print(
        f"S100 profile: {profile.city}, {profile.phone}"
        if profile
        else "S100 has no profile."
    )

    print("D10 courses:")
    for course in repository.get_department_courses("D10"):
        print(f"  {course.course_id}: {course.title}")

    print("Students in C101:")
    for student in repository.get_course_students("C101"):
        print(f"  {student.student_id}: {student.name}")

    print(
        "Courses shared by S100 and S101:",
        sorted(repository.find_common_courses("S100", "S101")),
    )

    demonstrate_failures(repository)
    run_assertions(repository)
    demonstrate_lookup_performance(repository)

    print("\n=== INTEGRITY RESULT ===")
    errors = repository.validate_integrity()

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("All one-to-one, one-to-many, and many-to-many constraints are valid.")

    print("\nExecutable demonstration completed successfully.")


if __name__ == "__main__":
    main()
