"""
Data Modeling Fundamentals
==========================

A self-contained study and executable demonstration of:

    - Entities
    - Attributes
    - Relationships
    - Cardinality and participation
    - Primary keys and candidate keys
    - Foreign keys
    - Composite keys
    - Domains and constraints
    - Business rules
    - ER-style conceptual modeling
    - Logical relational modeling
    - Normalization
    - Functional dependencies
    - Associative entities
    - Recursive relationships
    - Weak entities
    - Derived and multivalued attributes
    - Optionality
    - Referential integrity
    - Denormalization trade-offs
    - Temporal and historical data considerations
    - Validation and model testing
    - Schema generation
    - Query examples
    - Performance and production considerations

The examples use only Python's standard library.

Run:
    python data_modeling_fundamentals.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Iterable, Optional
import re
import sqlite3
import unittest


# =============================================================================
# 1. FUNDAMENTAL VOCABULARY
# =============================================================================

def print_section(title: str) -> None:
    """Print a readable section heading."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def explain_fundamentals() -> None:
    """
    Data modeling describes the data an organization needs, how pieces of
    data relate to one another, and which rules make the data valid.

    A useful progression is:

        Business reality
            -> conceptual model
            -> logical model
            -> physical implementation

    Example:
        A university has students.
        A student has a student number and name.
        Students enroll in courses.
        An enrollment belongs to one student and one course.

    The concepts in this function are represented explicitly so that the
    terminology can be studied alongside executable Python structures.
    """
    print_section("1. FUNDAMENTAL CONCEPTS")

    terms = {
        "Entity": (
            "A distinguishable real-world or business object about which "
            "the organization stores information."
        ),
        "Entity type": (
            "A definition or class of similar entities, such as CUSTOMER."
        ),
        "Entity instance": (
            "One occurrence of an entity type, such as customer 101."
        ),
        "Attribute": (
            "A property that describes an entity or relationship."
        ),
        "Domain": (
            "The set of valid values for an attribute."
        ),
        "Relationship": (
            "A meaningful association between entity types."
        ),
        "Cardinality": (
            "How many instances of one entity can or must relate to another."
        ),
        "Participation": (
            "Whether participation in a relationship is mandatory or optional."
        ),
        "Business rule": (
            "A rule derived from business policy or operational reality."
        ),
        "Key": (
            "An attribute or set of attributes used to uniquely identify "
            "an entity or relationship occurrence."
        ),
        "Primary key": (
            "The selected candidate key used as the principal identifier."
        ),
        "Foreign key": (
            "An attribute or set of attributes referencing a key in another "
            "relation."
        ),
        "Constraint": (
            "A formal condition that restricts allowed database states."
        ),
    }

    for term, definition in terms.items():
        print(f"{term:18} : {definition}")


# =============================================================================
# 2. DOMAINS AND ATTRIBUTE TYPES
# =============================================================================

class AttributeKind(Enum):
    """Common conceptual attribute classifications."""
    SIMPLE = "simple"
    COMPOSITE = "composite"
    SINGLE_VALUED = "single-valued"
    MULTIVALUED = "multivalued"
    DERIVED = "derived"
    STORED = "stored"


@dataclass(frozen=True)
class Domain:
    """
    A domain defines valid values for an attribute.

    A domain is stronger than merely saying "this is a string". It captures
    semantic restrictions such as length, format, range, or allowed values.
    """
    name: str
    python_type: type
    validator: Optional[Callable[[Any], bool]] = None
    description: str = ""

    def validate(self, value: Any) -> bool:
        if value is None:
            return False

        if not isinstance(value, self.python_type):
            return False

        if self.validator is not None:
            return bool(self.validator(value))

        return True


EMAIL_DOMAIN = Domain(
    name="EmailAddress",
    python_type=str,
    validator=lambda value: bool(
        re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value)
    ),
    description="A basic syntactic email address domain.",
)

POSITIVE_MONEY_DOMAIN = Domain(
    name="PositiveMoney",
    python_type=Decimal,
    validator=lambda value: value >= Decimal("0"),
    description="Non-negative monetary values.",
)

AGE_DOMAIN = Domain(
    name="Age",
    python_type=int,
    validator=lambda value: 0 <= value <= 150,
    description="A simplified human age domain.",
)


def demonstrate_domains() -> None:
    print_section("2. DOMAINS AND ATTRIBUTE VALIDATION")

    samples = [
        (EMAIL_DOMAIN, "alice@example.com"),
        (EMAIL_DOMAIN, "not-an-email"),
        (POSITIVE_MONEY_DOMAIN, Decimal("125.50")),
        (POSITIVE_MONEY_DOMAIN, Decimal("-2.00")),
        (AGE_DOMAIN, 33),
        (AGE_DOMAIN, 200),
    ]

    for domain, value in samples:
        print(
            f"{domain.name:18} "
            f"value={value!r:25} "
            f"valid={domain.validate(value)}"
        )

    print("\nImportant distinction:")
    print("- A domain describes what values are acceptable.")
    print("- A business rule describes what relationships or states are acceptable.")
    print("- A database constraint is an implementation mechanism for enforcing rules.")


# =============================================================================
# 3. ATTRIBUTES: SIMPLE, COMPOSITE, DERIVED, MULTIVALUED
# =============================================================================

@dataclass
class PersonName:
    """
    A composite conceptual attribute.

    Conceptually, a person's name may be represented as one logical attribute
    while being decomposed into first, middle, and last components.
    """
    first_name: str
    middle_name: Optional[str]
    last_name: str


@dataclass
class Customer:
    """
    Example entity with stored and derived attributes.

    customer_id is the identifier.
    date_of_birth is stored.
    age is derived from date_of_birth and today's date.
    """
    customer_id: int
    name: PersonName
    email: str
    date_of_birth: date
    phone_numbers: list[str] = field(default_factory=list)

    @property
    def age(self) -> int:
        today = date.today()
        years = today.year - self.date_of_birth.year

        if (today.month, today.day) < (
            self.date_of_birth.month,
            self.date_of_birth.day,
        ):
            years -= 1

        return years


def demonstrate_attribute_classifications() -> None:
    print_section("3. ATTRIBUTE CLASSIFICATIONS")

    customer = Customer(
        customer_id=1,
        name=PersonName(
            first_name="Asha",
            middle_name=None,
            last_name="Sharma",
        ),
        email="asha@example.com",
        date_of_birth=date(1995, 5, 10),
        phone_numbers=["+91-9000000000", "+91-9111111111"],
    )

    print("Composite attribute:", customer.name)
    print("Stored attribute:", customer.date_of_birth)
    print("Derived attribute:", customer.age)
    print("Multivalued attribute:", customer.phone_numbers)

    print("\nModeling caution:")
    print(
        "A multivalued attribute often becomes a separate relation in a "
        "relational model, such as CUSTOMER_PHONE(customer_id, phone_number)."
    )


# =============================================================================
# 4. ENTITY TYPES, IDENTIFIERS, AND KEYS
# =============================================================================

@dataclass(frozen=True)
class KeyDefinition:
    """Describes a candidate or primary key."""
    name: str
    columns: tuple[str, ...]
    is_primary: bool = False

    @property
    def is_composite(self) -> bool:
        return len(self.columns) > 1


@dataclass
class EntityDefinition:
    """Conceptual description of an entity type."""
    name: str
    attributes: list[str]
    candidate_keys: list[KeyDefinition]
    primary_key: KeyDefinition

    def validate_primary_key(self) -> None:
        if self.primary_key not in self.candidate_keys:
            raise ValueError(
                f"Primary key {self.primary_key.name} must be a candidate key."
            )

        if not self.primary_key.is_primary:
            raise ValueError(
                "The selected primary key must be marked as primary."
            )


def demonstrate_keys() -> None:
    print_section("4. KEYS")

    employee = EntityDefinition(
        name="EMPLOYEE",
        attributes=["employee_id", "national_id", "email", "name"],
        candidate_keys=[
            KeyDefinition(
                name="PK_EMPLOYEE",
                columns=("employee_id",),
                is_primary=True,
            ),
            KeyDefinition(
                name="UQ_EMPLOYEE_NATIONAL_ID",
                columns=("national_id",),
            ),
            KeyDefinition(
                name="UQ_EMPLOYEE_EMAIL",
                columns=("email",),
            ),
        ],
        primary_key=KeyDefinition(
            name="PK_EMPLOYEE",
            columns=("employee_id",),
            is_primary=True,
        ),
    )

    employee.validate_primary_key()

    print("Entity:", employee.name)
    print("Candidate keys:")
    for key in employee.candidate_keys:
        print(
            f"  {key.name}: {key.columns} "
            f"{'(primary)' if key.is_primary else ''}"
        )

    composite = KeyDefinition(
        name="PK_ENROLLMENT",
        columns=("student_id", "course_id"),
        is_primary=True,
    )

    print("\nComposite key:")
    print(composite.columns)
    print(
        "A composite key identifies an occurrence using multiple attributes "
        "together."
    )


# =============================================================================
# 5. RELATIONSHIPS, CARDINALITY, AND OPTIONALITY
# =============================================================================

class Cardinality(Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_MANY = "M:N"


class Participation(Enum):
    OPTIONAL = "optional"
    MANDATORY = "mandatory"


@dataclass(frozen=True)
class RelationshipEnd:
    entity: str
    minimum: int
    maximum: Optional[int]

    def __post_init__(self) -> None:
        if self.minimum < 0:
            raise ValueError("Minimum cardinality cannot be negative.")

        if self.maximum is not None and self.maximum < self.minimum:
            raise ValueError("Maximum cardinality cannot be less than minimum.")

    @property
    def participation(self) -> Participation:
        return (
            Participation.MANDATORY
            if self.minimum >= 1
            else Participation.OPTIONAL
        )


@dataclass(frozen=True)
class RelationshipDefinition:
    name: str
    left: RelationshipEnd
    right: RelationshipEnd

    @property
    def cardinality(self) -> Cardinality:
        left_max = self.left.maximum
        right_max = self.right.maximum

        if left_max == 1 and right_max == 1:
            return Cardinality.ONE_TO_ONE

        if left_max == 1 or right_max == 1:
            return Cardinality.ONE_TO_MANY

        return Cardinality.MANY_TO_MANY


def demonstrate_relationships() -> None:
    print_section("5. RELATIONSHIPS AND CARDINALITY")

    relationships = [
        RelationshipDefinition(
            name="CUSTOMER_PLACES_ORDER",
            left=RelationshipEnd("CUSTOMER", 0, None),
            right=RelationshipEnd("ORDER", 1, 1),
        ),
        RelationshipDefinition(
            name="EMPLOYEE_MANAGES_EMPLOYEE",
            left=RelationshipEnd("MANAGER", 0, None),
            right=RelationshipEnd("EMPLOYEE", 0, 1),
        ),
        RelationshipDefinition(
            name="STUDENT_ENROLLS_COURSE",
            left=RelationshipEnd("STUDENT", 0, None),
            right=RelationshipEnd("COURSE", 0, None),
        ),
        RelationshipDefinition(
            name="PERSON_HAS_PASSPORT",
            left=RelationshipEnd("PERSON", 0, 1),
            right=RelationshipEnd("PASSPORT", 1, 1),
        ),
    ]

    for relationship in relationships:
        print(f"\n{relationship.name}")
        print(f"  Cardinality: {relationship.cardinality.value}")
        print(
            f"  {relationship.left.entity}: "
            f"{relationship.left.minimum}.."
            f"{relationship.left.maximum if relationship.left.maximum is not None else 'N'} "
            f"({relationship.left.participation.value})"
        )
        print(
            f"  {relationship.right.entity}: "
            f"{relationship.right.minimum}.."
            f"{relationship.right.maximum if relationship.right.maximum is not None else 'N'} "
            f"({relationship.right.participation.value})"
        )

    print("\nNotation interpretation:")
    print("0..1  = optional, at most one")
    print("1..1  = mandatory, exactly one")
    print("0..N  = optional, zero or many")
    print("1..N  = mandatory, one or many")


# =============================================================================
# 6. BUSINESS RULES
# =============================================================================

@dataclass(frozen=True)
class BusinessRule:
    """A formalized statement describing an allowed or required condition."""
    identifier: str
    description: str
    validator: Callable[[dict[str, Any]], bool]

    def evaluate(self, context: dict[str, Any]) -> bool:
        return bool(self.validator(context))


def build_business_rules() -> list[BusinessRule]:
    return [
        BusinessRule(
            identifier="BR-001",
            description="Every order must belong to exactly one customer.",
            validator=lambda context: (
                context.get("customer_id") is not None
            ),
        ),
        BusinessRule(
            identifier="BR-002",
            description="Order quantity must be positive.",
            validator=lambda context: context.get("quantity", 0) > 0,
        ),
        BusinessRule(
            identifier="BR-003",
            description="Product price cannot be negative.",
            validator=lambda context: context.get("unit_price", Decimal("-1"))
            >= Decimal("0"),
        ),
        BusinessRule(
            identifier="BR-004",
            description="A shipped order must have a shipment date.",
            validator=lambda context: (
                context.get("status") != "SHIPPED"
                or context.get("shipped_at") is not None
            ),
        ),
    ]


def demonstrate_business_rules() -> None:
    print_section("6. BUSINESS RULES")

    rules = build_business_rules()

    contexts = [
        {
            "customer_id": 10,
            "quantity": 2,
            "unit_price": Decimal("50.00"),
            "status": "NEW",
        },
        {
            "customer_id": None,
            "quantity": 2,
            "unit_price": Decimal("50.00"),
            "status": "NEW",
        },
        {
            "customer_id": 10,
            "quantity": 0,
            "unit_price": Decimal("50.00"),
            "status": "NEW",
        },
        {
            "customer_id": 10,
            "quantity": 1,
            "unit_price": Decimal("20.00"),
            "status": "SHIPPED",
            "shipped_at": None,
        },
    ]

    for index, context in enumerate(contexts, start=1):
        print(f"\nContext {index}: {context}")
        for rule in rules:
            print(
                f"  {rule.identifier}: "
                f"{'PASS' if rule.evaluate(context) else 'FAIL'}"
            )

    print(
        "\nA conceptual business rule should be expressed precisely enough "
        "to determine what database state is valid."
    )


# =============================================================================
# 7. A COMPLETE CONCEPTUAL MODEL
# =============================================================================

def build_university_conceptual_model() -> dict[str, EntityDefinition | RelationshipDefinition]:
    """
    Build a compact university model.

    Entities:
        STUDENT
        COURSE
        INSTRUCTOR
        DEPARTMENT
        ENROLLMENT

    Relationships:
        STUDENT enrolls in COURSE through ENROLLMENT.
        INSTRUCTOR teaches COURSE.
        DEPARTMENT offers COURSE.
        INSTRUCTOR works for DEPARTMENT.

    ENROLLMENT is an associative entity because STUDENT and COURSE have
    many-to-many cardinality and the relationship itself has attributes.
    """
    student = EntityDefinition(
        name="STUDENT",
        attributes=["student_id", "name", "email", "date_of_birth"],
        candidate_keys=[
            KeyDefinition("PK_STUDENT", ("student_id",), True),
            KeyDefinition("UQ_STUDENT_EMAIL", ("email",)),
        ],
        primary_key=KeyDefinition("PK_STUDENT", ("student_id",), True),
    )

    course = EntityDefinition(
        name="COURSE",
        attributes=["course_id", "course_code", "title", "credits"],
        candidate_keys=[
            KeyDefinition("PK_COURSE", ("course_id",), True),
            KeyDefinition("UQ_COURSE_CODE", ("course_code",)),
        ],
        primary_key=KeyDefinition("PK_COURSE", ("course_id",), True),
    )

    instructor = EntityDefinition(
        name="INSTRUCTOR",
        attributes=["instructor_id", "name", "email"],
        candidate_keys=[
            KeyDefinition("PK_INSTRUCTOR", ("instructor_id",), True),
            KeyDefinition("UQ_INSTRUCTOR_EMAIL", ("email",)),
        ],
        primary_key=KeyDefinition(
            "PK_INSTRUCTOR",
            ("instructor_id",),
            True,
        ),
    )

    department = EntityDefinition(
        name="DEPARTMENT",
        attributes=["department_id", "name"],
        candidate_keys=[
            KeyDefinition("PK_DEPARTMENT", ("department_id",), True),
            KeyDefinition("UQ_DEPARTMENT_NAME", ("name",)),
        ],
        primary_key=KeyDefinition(
            "PK_DEPARTMENT",
            ("department_id",),
            True,
        ),
    )

    enrollment = EntityDefinition(
        name="ENROLLMENT",
        attributes=[
            "student_id",
            "course_id",
            "enrolled_on",
            "grade",
        ],
        candidate_keys=[
            KeyDefinition(
                "PK_ENROLLMENT",
                ("student_id", "course_id"),
                True,
            )
        ],
        primary_key=KeyDefinition(
            "PK_ENROLLMENT",
            ("student_id", "course_id"),
            True,
        ),
    )

    relationships = {
        "STUDENT_ENROLLS_COURSE": RelationshipDefinition(
            name="STUDENT_ENROLLS_COURSE",
            left=RelationshipEnd("STUDENT", 0, None),
            right=RelationshipEnd("COURSE", 0, None),
        ),
        "INSTRUCTOR_TEACHES_COURSE": RelationshipDefinition(
            name="INSTRUCTOR_TEACHES_COURSE",
            left=RelationshipEnd("INSTRUCTOR", 0, None),
            right=RelationshipEnd("COURSE", 0, 1),
        ),
        "DEPARTMENT_OFFERS_COURSE": RelationshipDefinition(
            name="DEPARTMENT_OFFERS_COURSE",
            left=RelationshipEnd("DEPARTMENT", 0, None),
            right=RelationshipEnd("COURSE", 1, 1),
        ),
        "DEPARTMENT_EMPLOYS_INSTRUCTOR": RelationshipDefinition(
            name="DEPARTMENT_EMPLOYS_INSTRUCTOR",
            left=RelationshipEnd("DEPARTMENT", 0, None),
            right=RelationshipEnd("INSTRUCTOR", 1, 1),
        ),
    }

    model: dict[str, EntityDefinition | RelationshipDefinition] = {
        "STUDENT": student,
        "COURSE": course,
        "INSTRUCTOR": instructor,
        "DEPARTMENT": department,
        "ENROLLMENT": enrollment,
    }

    model.update(relationships)
    return model


def demonstrate_conceptual_model() -> None:
    print_section("7. CONCEPTUAL UNIVERSITY MODEL")

    model = build_university_conceptual_model()

    print("Entities:")
    for name, definition in model.items():
        if isinstance(definition, EntityDefinition):
            print(f"  {name}: {definition.attributes}")

    print("\nRelationships:")
    for name, relationship in model.items():
        if isinstance(relationship, RelationshipDefinition):
            print(
                f"  {name}: "
                f"{relationship.left.entity} "
                f"{relationship.cardinality.value} "
                f"{relationship.right.entity}"
            )


# =============================================================================
# 8. MAPPING CONCEPTUAL MODELS TO RELATIONAL TABLES
# =============================================================================

@dataclass(frozen=True)
class ForeignKeyDefinition:
    """
    Describes a foreign-key relationship in a logical relational model.
    """
    columns: tuple[str, ...]
    referenced_table: str
    referenced_columns: tuple[str, ...]
    on_delete: str = "NO ACTION"
    on_update: str = "NO ACTION"

    def validate(self) -> None:
        if len(self.columns) != len(self.referenced_columns):
            raise ValueError(
                "Foreign key and referenced key must have the same number "
                "of columns."
            )


@dataclass
class TableDefinition:
    """Logical relational table definition."""
    name: str
    columns: dict[str, str]
    primary_key: tuple[str, ...]
    unique_constraints: list[tuple[str, ...]] = field(default_factory=list)
    foreign_keys: list[ForeignKeyDefinition] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.primary_key:
            raise ValueError(f"{self.name} must have a primary key.")

        for column in self.primary_key:
            if column not in self.columns:
                raise ValueError(
                    f"Primary key column {column} does not exist in {self.name}."
                )

        for foreign_key in self.foreign_keys:
            foreign_key.validate()

            for column in foreign_key.columns:
                if column not in self.columns:
                    raise ValueError(
                        f"Foreign key column {column} does not exist."
                    )


def build_university_relational_model() -> list[TableDefinition]:
    """Map the university conceptual model into relational structures."""
    tables = [
        TableDefinition(
            name="department",
            columns={
                "department_id": "INTEGER",
                "name": "TEXT NOT NULL",
            },
            primary_key=("department_id",),
            unique_constraints=[("name",)],
        ),
        TableDefinition(
            name="student",
            columns={
                "student_id": "INTEGER",
                "name": "TEXT NOT NULL",
                "email": "TEXT NOT NULL",
                "date_of_birth": "TEXT NOT NULL",
            },
            primary_key=("student_id",),
            unique_constraints=[("email",)],
        ),
        TableDefinition(
            name="instructor",
            columns={
                "instructor_id": "INTEGER",
                "name": "TEXT NOT NULL",
                "email": "TEXT NOT NULL",
                "department_id": "INTEGER NOT NULL",
            },
            primary_key=("instructor_id",),
            unique_constraints=[("email",)],
            foreign_keys=[
                ForeignKeyDefinition(
                    columns=("department_id",),
                    referenced_table="department",
                    referenced_columns=("department_id",),
                    on_delete="RESTRICT",
                )
            ],
        ),
        TableDefinition(
            name="course",
            columns={
                "course_id": "INTEGER",
                "course_code": "TEXT NOT NULL",
                "title": "TEXT NOT NULL",
                "credits": "INTEGER NOT NULL",
                "department_id": "INTEGER NOT NULL",
                "instructor_id": "INTEGER",
            },
            primary_key=("course_id",),
            unique_constraints=[("course_code",)],
            foreign_keys=[
                ForeignKeyDefinition(
                    columns=("department_id",),
                    referenced_table="department",
                    referenced_columns=("department_id",),
                    on_delete="RESTRICT",
                ),
                ForeignKeyDefinition(
                    columns=("instructor_id",),
                    referenced_table="instructor",
                    referenced_columns=("instructor_id",),
                    on_delete="SET NULL",
                ),
            ],
            checks=["credits BETWEEN 1 AND 6"],
        ),
        TableDefinition(
            name="enrollment",
            columns={
                "student_id": "INTEGER NOT NULL",
                "course_id": "INTEGER NOT NULL",
                "enrolled_on": "TEXT NOT NULL",
                "grade": "TEXT",
            },
            primary_key=("student_id", "course_id"),
            foreign_keys=[
                ForeignKeyDefinition(
                    columns=("student_id",),
                    referenced_table="student",
                    referenced_columns=("student_id",),
                    on_delete="CASCADE",
                ),
                ForeignKeyDefinition(
                    columns=("course_id",),
                    referenced_table="course",
                    referenced_columns=("course_id",),
                    on_delete="CASCADE",
                ),
            ],
            checks=[
                "grade IS NULL OR grade IN ('A', 'B', 'C', 'D', 'F')"
            ],
        ),
    ]

    for table in tables:
        table.validate()

    return tables


def quote_sql_identifier(identifier: str) -> str:
    """
    Quote an SQLite identifier safely.

    Identifiers should ideally come from trusted schema metadata rather than
    user input. Double quotes are used for SQL identifiers.
    """
    return '"' + identifier.replace('"', '""') + '"'


def generate_create_table_sql(table: TableDefinition) -> str:
    """Generate CREATE TABLE SQL from a logical table definition."""
    parts: list[str] = []

    for column_name, column_type in table.columns.items():
        parts.append(
            f"{quote_sql_identifier(column_name)} {column_type}"
        )

    pk = ", ".join(quote_sql_identifier(c) for c in table.primary_key)
    parts.append(f"PRIMARY KEY ({pk})")

    for unique_columns in table.unique_constraints:
        columns = ", ".join(
            quote_sql_identifier(c) for c in unique_columns
        )
        parts.append(f"UNIQUE ({columns})")

    for foreign_key in table.foreign_keys:
        local_columns = ", ".join(
            quote_sql_identifier(c) for c in foreign_key.columns
        )
        referenced_columns = ", ".join(
            quote_sql_identifier(c)
            for c in foreign_key.referenced_columns
        )

        parts.append(
            f"FOREIGN KEY ({local_columns}) "
            f"REFERENCES {quote_sql_identifier(foreign_key.referenced_table)} "
            f"({referenced_columns}) "
            f"ON DELETE {foreign_key.on_delete} "
            f"ON UPDATE {foreign_key.on_update}"
        )

    for check in table.checks:
        parts.append(f"CHECK ({check})")

    return (
        f"CREATE TABLE {quote_sql_identifier(table.name)} (\n"
        + ",\n".join(f"    {part}" for part in parts)
        + "\n);"
    )


def demonstrate_relational_mapping() -> None:
    print_section("8. RELATIONAL MAPPING")

    tables = build_university_relational_model()

    for table in tables:
        print(generate_create_table_sql(table))
        print()


# =============================================================================
# 9. NORMALIZATION AND FUNCTIONAL DEPENDENCIES
# =============================================================================

@dataclass(frozen=True)
class FunctionalDependency:
    """
    X -> Y means that a value of X determines a value of Y.

    Example:
        student_id -> student_name

    This is a statement about the data model, not merely an observed
    coincidence in a particular dataset.
    """
    determinant: frozenset[str]
    dependent: frozenset[str]

    def __str__(self) -> str:
        left = ", ".join(sorted(self.determinant))
        right = ", ".join(sorted(self.dependent))
        return f"{left} -> {right}"


def explain_functional_dependencies() -> None:
    print_section("9. FUNCTIONAL DEPENDENCIES")

    dependencies = [
        FunctionalDependency(
            frozenset({"student_id"}),
            frozenset({"student_name", "student_email"}),
        ),
        FunctionalDependency(
            frozenset({"course_id"}),
            frozenset({"course_code", "course_title"}),
        ),
        FunctionalDependency(
            frozenset({"student_id", "course_id"}),
            frozenset({"enrolled_on", "grade"}),
        ),
    ]

    for dependency in dependencies:
        print(dependency)

    print("\nInterpretation:")
    print(
        "If student_id identifies one student, the student's name and email "
        "are determined by student_id."
    )
    print(
        "For ENROLLMENT, the combination (student_id, course_id) identifies "
        "the enrollment-specific attributes."
    )


@dataclass(frozen=True)
class NormalizationAssessment:
    first_normal_form: bool
    second_normal_form: bool
    third_normal_form: bool
    explanation: str


def assess_enrollment_table() -> NormalizationAssessment:
    """
    ENROLLMENT(student_id, course_id, enrolled_on, grade)

    Assume:
        (student_id, course_id) -> enrolled_on, grade

    There are no repeating groups.
    Non-key attributes depend on the complete composite key.
    There are no transitive dependencies among the listed attributes.

    Therefore the simplified table satisfies 1NF, 2NF, and 3NF under these
    assumptions.
    """
    return NormalizationAssessment(
        first_normal_form=True,
        second_normal_form=True,
        third_normal_form=True,
        explanation=(
            "The relation contains atomic values and its non-key attributes "
            "depend on the complete composite key without a transitive "
            "dependency among non-key attributes."
        ),
    )


def demonstrate_normalization() -> None:
    print_section("10. NORMALIZATION")

    assessment = assess_enrollment_table()

    print("ENROLLMENT(student_id, course_id, enrolled_on, grade)")
    print("1NF:", assessment.first_normal_form)
    print("2NF:", assessment.second_normal_form)
    print("3NF:", assessment.third_normal_form)
    print("Reason:", assessment.explanation)

    print("\nA denormalized example:")
    print(
        "ENROLLMENT(student_id, student_name, course_id, course_title, grade)"
    )
    print(
        "This duplicates student and course facts and can create update, "
        "insert, and delete anomalies."
    )

    print("\nNormalized decomposition:")
    print("STUDENT(student_id, student_name)")
    print("COURSE(course_id, course_title)")
    print("ENROLLMENT(student_id, course_id, grade)")


# =============================================================================
# 11. UPDATE, INSERT, AND DELETE ANOMALIES
# =============================================================================

def demonstrate_anomalies() -> None:
    print_section("11. DATA ANOMALIES")

    rows = [
        {
            "student_id": 1,
            "student_name": "Asha",
            "course_id": 10,
            "course_title": "Databases",
        },
        {
            "student_id": 1,
            "student_name": "Asha",
            "course_id": 11,
            "course_title": "Networks",
        },
        {
            "student_id": 2,
            "student_name": "Ravi",
            "course_id": 10,
            "course_title": "Databases",
        },
    ]

    print("Denormalized rows:")
    for row in rows:
        print(row)

    print(
        "\nUpdate anomaly: changing 'Databases' requires changing every "
        "duplicate occurrence."
    )

    print(
        "Insert anomaly: if courses can only be stored through enrollments, "
        "a course with no enrolled students may be impossible to insert."
    )

    print(
        "Delete anomaly: deleting the final enrollment for a course can "
        "accidentally delete the only stored information about that course."
    )


# =============================================================================
# 12. ASSOCIATIVE ENTITIES AND MANY-TO-MANY RELATIONSHIPS
# =============================================================================

@dataclass
class Enrollment:
    """
    Associative entity resolving STUDENT M:N COURSE.

    It can carry attributes that belong to the association itself, such as:
        enrolled_on
        grade
        status
    """
    student_id: int
    course_id: int
    enrolled_on: date
    status: str = "ACTIVE"
    grade: Optional[str] = None

    VALID_STATUSES = {"ACTIVE", "DROPPED", "COMPLETED"}

    def validate(self) -> None:
        if self.status not in self.VALID_STATUSES:
            raise ValueError("Invalid enrollment status.")

        if self.grade is not None and self.grade not in {
            "A", "B", "C", "D", "F"
        }:
            raise ValueError("Invalid grade.")


def demonstrate_associative_entity() -> None:
    print_section("12. ASSOCIATIVE ENTITIES")

    enrollment = Enrollment(
        student_id=101,
        course_id=501,
        enrolled_on=date(2026, 8, 1),
        status="ACTIVE",
    )

    enrollment.validate()
    print(enrollment)

    print(
        "\nA many-to-many relationship is usually transformed into an "
        "associative entity in a relational model."
    )
    print("STUDENT 1 --- N ENROLLMENT N --- 1 COURSE")


# =============================================================================
# 13. RECURSIVE RELATIONSHIPS
# =============================================================================

@dataclass(frozen=True)
class Employee:
    employee_id: int
    name: str
    manager_id: Optional[int] = None


def validate_employee_hierarchy(employees: Iterable[Employee]) -> None:
    """
    Validate a simple recursive employee-manager relationship.

    Rules:
        - An employee may have no manager.
        - A manager must refer to an existing employee.
        - An employee cannot directly manage themselves.
        - The hierarchy cannot contain a cycle.
    """
    employee_list = list(employees)
    by_id = {employee.employee_id: employee for employee in employee_list}

    if len(by_id) != len(employee_list):
        raise ValueError("Employee IDs must be unique.")

    for employee in employee_list:
        if employee.manager_id is None:
            continue

        if employee.manager_id not in by_id:
            raise ValueError(
                f"Manager {employee.manager_id} does not exist."
            )

        if employee.manager_id == employee.employee_id:
            raise ValueError("An employee cannot directly manage themselves.")

    for employee in employee_list:
        visited: set[int] = set()
        current_id: Optional[int] = employee.employee_id

        while current_id is not None:
            if current_id in visited:
                raise ValueError(
                    f"Management cycle detected starting from employee "
                    f"{employee.employee_id}."
                )

            visited.add(current_id)
            current = by_id[current_id]
            current_id = current.manager_id


def demonstrate_recursive_relationship() -> None:
    print_section("13. RECURSIVE RELATIONSHIPS")

    employees = [
        Employee(1, "CEO"),
        Employee(2, "Manager A", 1),
        Employee(3, "Manager B", 1),
        Employee(4, "Developer A", 2),
        Employee(5, "Developer B", 2),
    ]

    validate_employee_hierarchy(employees)

    print("Valid employee hierarchy.")

    invalid = [
        Employee(1, "A", 2),
        Employee(2, "B", 1),
    ]

    try:
        validate_employee_hierarchy(invalid)
    except ValueError as error:
        print("Expected validation error:", error)


# =============================================================================
# 14. WEAK ENTITIES
# =============================================================================

@dataclass(frozen=True)
class Order:
    order_id: int
    customer_id: int


@dataclass(frozen=True)
class OrderLine:
    """
    An order line may be identified by (order_id, line_number).

    line_number alone is not globally unique, so it is a partial identifier
    whose identity depends on its owning ORDER.
    """
    order_id: int
    line_number: int
    product_id: int
    quantity: int

    @property
    def identity(self) -> tuple[int, int]:
        return self.order_id, self.line_number


def demonstrate_weak_entity() -> None:
    print_section("14. WEAK ENTITIES")

    line = OrderLine(
        order_id=5001,
        line_number=1,
        product_id=300,
        quantity=2,
    )

    print("Order-line identity:", line.identity)
    print(
        "The line number is unique only within its order. "
        "The composite identity depends on the owner order."
    )


# =============================================================================
# 15. ONE-TO-ONE RELATIONSHIP MODELING
# =============================================================================

def demonstrate_one_to_one() -> None:
    print_section("15. ONE-TO-ONE RELATIONSHIPS")

    print(
        "Example: PERSON 0..1 --- 1 PASSPORT"
    )
    print(
        "A passport belongs to exactly one person, while a person may have "
        "zero or one passport under this business rule."
    )

    print(
        "\nIn a relational model, PASSPORT.person_id can be both:"
        "\n  - a foreign key referencing PERSON(person_id)"
        "\n  - UNIQUE to prevent multiple passports per person."
    )


# =============================================================================
# 16. NULL, OPTIONALITY, AND THREE-VALUED LOGIC
# =============================================================================

def demonstrate_null_behavior() -> None:
    print_section("16. NULL AND OPTIONALITY")

    values = [None, 10, 0]

    for value in values:
        print(f"value={value!r:5} | Python value is None: {value is None}")

    print(
        "\nDatabase NULL does not mean zero, empty string, false, or "
        "not applicable in every context."
    )

    print(
        "SQL comparisons involving NULL use three-valued logic: TRUE, "
        "FALSE, and UNKNOWN."
    )

    print(
        "Use IS NULL and IS NOT NULL rather than '= NULL' and '<> NULL'."
    )


# =============================================================================
# 17. TEMPORAL DATA AND HISTORICAL MODELING
# =============================================================================

@dataclass(frozen=True)
class EmployeeSalaryHistory:
    employee_id: int
    salary: Decimal
    valid_from: date
    valid_to: Optional[date] = None

    def validate(self) -> None:
        if self.salary < Decimal("0"):
            raise ValueError("Salary cannot be negative.")

        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from.")


def find_salary_on_date(
    history: Iterable[EmployeeSalaryHistory],
    employee_id: int,
    target_date: date,
) -> Optional[EmployeeSalaryHistory]:
    """
    Return the salary version valid on target_date.

    This is a simple application-time validity model.
    """
    matching = [
        record
        for record in history
        if record.employee_id == employee_id
        and record.valid_from <= target_date
        and (
            record.valid_to is None
            or target_date < record.valid_to
        )
    ]

    if len(matching) > 1:
        raise ValueError("Overlapping salary history intervals detected.")

    return matching[0] if matching else None


def demonstrate_temporal_modeling() -> None:
    print_section("17. TEMPORAL DATA")

    history = [
        EmployeeSalaryHistory(
            employee_id=1,
            salary=Decimal("50000"),
            valid_from=date(2025, 1, 1),
            valid_to=date(2026, 1, 1),
        ),
        EmployeeSalaryHistory(
            employee_id=1,
            salary=Decimal("60000"),
            valid_from=date(2026, 1, 1),
        ),
    ]

    for record in history:
        record.validate()

    for target in [date(2025, 6, 1), date(2026, 6, 1)]:
        result = find_salary_on_date(history, 1, target)
        print(target, "->", result)


# =============================================================================
# 18. BUSINESS RULE VALIDATION WITH AN IN-MEMORY DOMAIN MODEL
# =============================================================================

@dataclass
class Product:
    product_id: int
    name: str
    price: Decimal
    active: bool = True

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Product name cannot be empty.")

        if self.price < Decimal("0"):
            raise ValueError("Product price cannot be negative.")


@dataclass
class OrderRecord:
    order_id: int
    customer_id: int
    status: str = "NEW"
    lines: list[OrderLine] = field(default_factory=list)

    VALID_STATUSES = {"NEW", "PAID", "SHIPPED", "CANCELLED"}

    def add_line(
        self,
        product_id: int,
        quantity: int,
    ) -> None:
        if quantity <= 0:
            raise ValueError("Order quantity must be greater than zero.")

        next_line_number = len(self.lines) + 1

        self.lines.append(
            OrderLine(
                order_id=self.order_id,
                line_number=next_line_number,
                product_id=product_id,
                quantity=quantity,
            )
        )

    def validate(self) -> None:
        if self.status not in self.VALID_STATUSES:
            raise ValueError("Invalid order status.")

        if not self.lines:
            raise ValueError("An order must contain at least one line.")

        line_numbers = [line.line_number for line in self.lines]

        if len(line_numbers) != len(set(line_numbers)):
            raise ValueError("Order line numbers must be unique.")


def calculate_order_total(
    order: OrderRecord,
    products: dict[int, Product],
) -> Decimal:
    """Calculate an order total from current product prices."""
    total = Decimal("0")

    for line in order.lines:
        if line.product_id not in products:
            raise KeyError(f"Unknown product: {line.product_id}")

        product = products[line.product_id]

        if not product.active:
            raise ValueError(
                f"Product {product.product_id} is inactive."
            )

        total += product.price * line.quantity

    return total


def demonstrate_domain_model() -> None:
    print_section("18. DOMAIN MODEL VALIDATION")

    products = {
        100: Product(100, "Keyboard", Decimal("2500.00")),
        101: Product(101, "Mouse", Decimal("1200.00")),
    }

    for product in products.values():
        product.validate()

    order = OrderRecord(order_id=9001, customer_id=1)
    order.add_line(product_id=100, quantity=1)
    order.add_line(product_id=101, quantity=2)
    order.validate()

    total = calculate_order_total(order, products)

    print("Order:", order)
    print("Total:", total)


# =============================================================================
# 19. REAL DATABASE IMPLEMENTATION WITH SQLITE
# =============================================================================

def create_database() -> sqlite3.Connection:
    """
    Create a relational database from the logical model.

    SQLite is part of Python's standard library, so no external package is
    required.
    """
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    tables = build_university_relational_model()

    # Tables must be created in dependency order.
    for table in tables:
        connection.execute(generate_create_table_sql(table))

    return connection


def populate_database(connection: sqlite3.Connection) -> None:
    """Insert a small consistent dataset."""
    connection.executemany(
        "INSERT INTO department (department_id, name) VALUES (?, ?)",
        [
            (1, "Computer Science"),
            (2, "Mathematics"),
        ],
    )

    connection.executemany(
        """
        INSERT INTO student
            (student_id, name, email, date_of_birth)
        VALUES (?, ?, ?, ?)
        """,
        [
            (101, "Asha Sharma", "asha@example.com", "1995-05-10"),
            (102, "Ravi Kumar", "ravi@example.com", "1998-02-15"),
        ],
    )

    connection.executemany(
        """
        INSERT INTO instructor
            (instructor_id, name, email, department_id)
        VALUES (?, ?, ?, ?)
        """,
        [
            (201, "Dr. Mehta", "mehta@example.com", 1),
            (202, "Dr. Rao", "rao@example.com", 2),
        ],
    )

    connection.executemany(
        """
        INSERT INTO course
            (course_id, course_code, title, credits,
             department_id, instructor_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (301, "CS101", "Database Systems", 4, 1, 201),
            (302, "CS102", "Computer Networks", 4, 1, 201),
            (303, "MA101", "Discrete Mathematics", 3, 2, 202),
        ],
    )

    connection.executemany(
        """
        INSERT INTO enrollment
            (student_id, course_id, enrolled_on, grade)
        VALUES (?, ?, ?, ?)
        """,
        [
            (101, 301, "2026-08-01", "A"),
            (101, 302, "2026-08-02", None),
            (102, 301, "2026-08-03", "B"),
            (102, 303, "2026-08-03", "A"),
        ],
    )

    connection.commit()


def demonstrate_sql_queries(connection: sqlite3.Connection) -> None:
    print_section("19. RELATIONAL DATABASE QUERIES")

    print("Students and their courses:")

    query = """
        SELECT
            s.student_id,
            s.name AS student_name,
            c.course_code,
            c.title,
            e.grade
        FROM student AS s
        JOIN enrollment AS e
            ON e.student_id = s.student_id
        JOIN course AS c
            ON c.course_id = e.course_id
        ORDER BY s.student_id, c.course_code
    """

    for row in connection.execute(query):
        print(row)

    print("\nCourses with optional instructor:")
    query = """
        SELECT
            c.course_code,
            c.title,
            i.name AS instructor_name
        FROM course AS c
        LEFT JOIN instructor AS i
            ON i.instructor_id = c.instructor_id
        ORDER BY c.course_code
    """

    for row in connection.execute(query):
        print(row)

    print("\nStudents with number of enrollments:")
    query = """
        SELECT
            s.student_id,
            s.name,
            COUNT(e.course_id) AS enrollment_count
        FROM student AS s
        LEFT JOIN enrollment AS e
            ON e.student_id = s.student_id
        GROUP BY s.student_id, s.name
        ORDER BY s.student_id
    """

    for row in connection.execute(query):
        print(row)


# =============================================================================
# 20. CONSTRAINTS AND REFERENTIAL INTEGRITY
# =============================================================================

def demonstrate_constraints(connection: sqlite3.Connection) -> None:
    print_section("20. CONSTRAINTS AND REFERENTIAL INTEGRITY")

    print("Attempting a duplicate student email:")

    try:
        connection.execute(
            """
            INSERT INTO student
                (student_id, name, email, date_of_birth)
            VALUES (?, ?, ?, ?)
            """,
            (999, "Duplicate", "asha@example.com", "2000-01-01"),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        connection.rollback()
        print("Expected integrity error:", error)

    print("\nAttempting an enrollment for a nonexistent student:")

    try:
        connection.execute(
            """
            INSERT INTO enrollment
                (student_id, course_id, enrolled_on, grade)
            VALUES (?, ?, ?, ?)
            """,
            (9999, 301, "2026-08-10", None),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        connection.rollback()
        print("Expected foreign-key error:", error)

    print("\nAttempting an invalid course credit value:")

    try:
        connection.execute(
            """
            INSERT INTO course
                (course_id, course_code, title, credits,
                 department_id, instructor_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (999, "BAD", "Invalid Course", 0, 1, 201),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        connection.rollback()
        print("Expected CHECK constraint error:", error)


# =============================================================================
# 21. DELETE ACTIONS: CASCADE, RESTRICT, SET NULL
# =============================================================================

def demonstrate_delete_actions() -> None:
    print_section("21. FOREIGN-KEY DELETE ACTIONS")

    print("RESTRICT:")
    print(
        "Prevents deletion of a parent row when dependent rows exist."
    )

    print("\nCASCADE:")
    print(
        "Deletes dependent rows automatically when the parent is deleted."
    )

    print("\nSET NULL:")
    print(
        "Removes the association by setting the foreign key to NULL, "
        "provided the column permits NULL."
    )

    print(
        "\nThe correct action depends on the business meaning of the "
        "relationship. CASCADE should not be selected merely for convenience."
    )


# =============================================================================
# 22. EDGE CASES
# =============================================================================

def demonstrate_edge_cases() -> None:
    print_section("22. EDGE CASES")

    print("Case 1: duplicate identifiers")

    try:
        employees = [
            Employee(1, "A"),
            Employee(1, "B"),
        ]
        validate_employee_hierarchy(employees)
    except ValueError as error:
        print("Handled:", error)

    print("\nCase 2: missing manager")

    try:
        employees = [
            Employee(1, "A", 999),
        ]
        validate_employee_hierarchy(employees)
    except ValueError as error:
        print("Handled:", error)

    print("\nCase 3: invalid enrollment status")

    try:
        Enrollment(
            student_id=1,
            course_id=1,
            enrolled_on=date.today(),
            status="UNKNOWN",
        ).validate()
    except ValueError as error:
        print("Handled:", error)

    print("\nCase 4: negative product price")

    try:
        Product(
            product_id=1,
            name="Invalid",
            price=Decimal("-10"),
        ).validate()
    except ValueError as error:
        print("Handled:", error)

    print("\nCase 5: empty order")

    try:
        OrderRecord(order_id=1, customer_id=1).validate()
    except ValueError as error:
        print("Handled:", error)


# =============================================================================
# 23. MODEL QUALITY CHECKS
# =============================================================================

@dataclass
class ModelQualityReport:
    entity_names_unique: bool
    primary_keys_present: bool
    foreign_keys_valid: bool
    relationship_names_unique: bool
    business_rules_present: bool
    issues: list[str]

    @property
    def valid(self) -> bool:
        return not self.issues


def inspect_model_quality() -> ModelQualityReport:
    model = build_university_conceptual_model()
    entities = [
        value for value in model.values()
        if isinstance(value, EntityDefinition)
    ]
    relationships = [
        value for value in model.values()
        if isinstance(value, RelationshipDefinition)
    ]

    issues: list[str] = []

    entity_names = [entity.name for entity in entities]
    entity_names_unique = len(entity_names) == len(set(entity_names))

    if not entity_names_unique:
        issues.append("Entity names are not unique.")

    primary_keys_present = all(
        bool(entity.primary_key.columns)
        for entity in entities
    )

    if not primary_keys_present:
        issues.append("Every entity must have an identifier.")

    tables = build_university_relational_model()
    try:
        for table in tables:
            table.validate()
        foreign_keys_valid = True
    except ValueError as error:
        foreign_keys_valid = False
        issues.append(str(error))

    relationship_names = [relationship.name for relationship in relationships]
    relationship_names_unique = (
        len(relationship_names) == len(set(relationship_names))
    )

    if not relationship_names_unique:
        issues.append("Relationship names are not unique.")

    business_rules_present = bool(build_business_rules())

    if not business_rules_present:
        issues.append("The model contains no documented business rules.")

    return ModelQualityReport(
        entity_names_unique=entity_names_unique,
        primary_keys_present=primary_keys_present,
        foreign_keys_valid=foreign_keys_valid,
        relationship_names_unique=relationship_names_unique,
        business_rules_present=business_rules_present,
        issues=issues,
    )


def demonstrate_model_quality() -> None:
    print_section("23. MODEL QUALITY CHECKS")

    report = inspect_model_quality()

    print("Entity names unique:", report.entity_names_unique)
    print("Primary keys present:", report.primary_keys_present)
    print("Foreign keys valid:", report.foreign_keys_valid)
    print("Relationship names unique:", report.relationship_names_unique)
    print("Business rules documented:", report.business_rules_present)
    print("Model valid:", report.valid)

    if report.issues:
        print("Issues:")
        for issue in report.issues:
            print(" -", issue)


# =============================================================================
# 24. NORMALIZATION VERSUS DENORMALIZATION
# =============================================================================

@dataclass
class DenormalizationDecision:
    requirement: str
    benefit: str
    risk: str


def compare_normalization_and_denormalization() -> None:
    print_section("24. NORMALIZATION VS DENORMALIZATION")

    decisions = [
        DenormalizationDecision(
            requirement="Reduce duplicated facts",
            benefit="Normalization reduces redundancy.",
            risk="More joins may be required for some queries.",
        ),
        DenormalizationDecision(
            requirement="Optimize read-heavy reporting",
            benefit="Precomputed or duplicated values may reduce joins.",
            risk="Writes become more complex and consistency must be maintained.",
        ),
        DenormalizationDecision(
            requirement="Maintain one authoritative business fact",
            benefit="Normalization provides a clearer source of truth.",
            risk="Complex reporting queries can require multiple joins.",
        ),
    ]

    for decision in decisions:
        print(f"\nRequirement: {decision.requirement}")
        print(f"Benefit: {decision.benefit}")
        print(f"Risk: {decision.risk}")

    print(
        "\nA sound model starts with correct semantics. "
        "Performance-driven denormalization should be deliberate and measured."
    )


# =============================================================================
# 25. SURROGATE KEYS VERSUS NATURAL KEYS
# =============================================================================

def compare_surrogate_and_natural_keys() -> None:
    print_section("25. SURROGATE KEYS VS NATURAL KEYS")

    print(
        "Natural key example: ISO country code such as 'IN'."
    )
    print(
        "Surrogate key example: integer country_id generated by the system."
    )

    print("\nNatural-key advantages:")
    print("- Carries business meaning.")
    print("- May already be unique and stable.")
    print("- Can avoid an extra identifier in simple domains.")

    print("\nNatural-key risks:")
    print("- Business identifiers can change.")
    print("- They may be long or composite.")
    print("- Business meaning can be inappropriate for technical identity.")

    print("\nSurrogate-key advantages:")
    print("- Usually compact and stable.")
    print("- Simplifies foreign-key references.")
    print("- Separates technical identity from business attributes.")

    print("\nSurrogate-key risks:")
    print("- Does not itself prevent duplicate business facts.")
    print("- Requires separate UNIQUE constraints for natural identifiers.")
    print("- Can hide important business semantics if poorly documented.")


# =============================================================================
# 26. INDEXING CONSIDERATIONS
# =============================================================================

def demonstrate_indexing_principles() -> None:
    print_section("26. INDEXING AND PERFORMANCE")

    print("Common indexing candidates:")
    print("- Primary keys")
    print("- Frequently searched unique business identifiers")
    print("- Foreign keys used heavily in joins")
    print("- Columns used in selective filtering")
    print("- Columns supporting common ORDER BY or GROUP BY operations")

    print("\nImportant trade-offs:")
    print("- Indexes accelerate suitable reads.")
    print("- Indexes consume storage.")
    print("- Indexes increase INSERT, UPDATE, and DELETE work.")
    print("- Too many indexes can harm write-heavy workloads.")
    print("- Composite index column order matters.")

    print(
        "\nA foreign key does not automatically guarantee an index in every "
        "database system. Index strategy should be designed for the workload."
    )


# =============================================================================
# 27. COMPOSITE INDEX ORDER
# =============================================================================

def explain_composite_index() -> None:
    print_section("27. COMPOSITE INDEX ORDER")

    print(
        "Suppose an application frequently queries:"
        "\nWHERE department_id = ? AND status = ?"
    )

    print(
        "\nAn index such as (department_id, status) can support that access "
        "pattern efficiently."
    )

    print(
        "\nThe order is not arbitrary. The useful access paths depend on the "
        "database optimizer, predicate structure, selectivity, and workload."
    )

    print(
        "\nDo not create indexes solely from column popularity. "
        "Design them around actual query patterns."
    )


# =============================================================================
# 28. SECURITY CONSIDERATIONS
# =============================================================================

def demonstrate_security_principles(connection: sqlite3.Connection) -> None:
    print_section("28. SECURITY CONSIDERATIONS")

    print("Use parameterized SQL rather than concatenating user input.")

    malicious_or_external_value = "CS101' OR 1=1 --"

    # Safe parameterization: the value remains data, not executable SQL.
    row = connection.execute(
        """
        SELECT course_id, course_code, title
        FROM course
        WHERE course_code = ?
        """,
        (malicious_or_external_value,),
    ).fetchone()

    print("Parameterized lookup result:", row)

    print("\nOther production principles:")
    print("- Apply least-privilege database permissions.")
    print("- Avoid storing unnecessary sensitive data.")
    print("- Protect secrets outside source code.")
    print("- Use encryption appropriate to the threat model.")
    print("- Audit access to sensitive business data.")
    print("- Validate at application and database boundaries.")
    print("- Treat authorization rules as separate from data validation.")


# =============================================================================
# 29. TRANSACTIONS AND CONSISTENCY
# =============================================================================

def demonstrate_transaction(connection: sqlite3.Connection) -> None:
    print_section("29. TRANSACTIONS")

    try:
        with connection:
            connection.execute(
                """
                INSERT INTO student
                    (student_id, name, email, date_of_birth)
                VALUES (?, ?, ?, ?)
                """,
                (103, "Neha", "neha@example.com", "1997-07-01"),
            )

            connection.execute(
                """
                INSERT INTO enrollment
                    (student_id, course_id, enrolled_on, grade)
                VALUES (?, ?, ?, ?)
                """,
                (103, 301, "2026-08-05", None),
            )

        print("Transaction committed successfully.")

    except sqlite3.IntegrityError as error:
        print("Transaction rolled back:", error)

    student = connection.execute(
        "SELECT student_id, name FROM student WHERE student_id = 103"
    ).fetchone()

    print("Student after transaction:", student)


# =============================================================================
# 30. NULLABLE FOREIGN KEYS AND OPTIONAL RELATIONSHIPS
# =============================================================================

def demonstrate_optional_foreign_key(connection: sqlite3.Connection) -> None:
    print_section("30. OPTIONAL FOREIGN KEYS")

    connection.execute(
        """
        INSERT INTO course
            (course_id, course_code, title, credits,
             department_id, instructor_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (304, "CS103", "Independent Study", 2, 1, None),
    )

    connection.commit()

    result = connection.execute(
        """
        SELECT course_code, instructor_id
        FROM course
        WHERE course_id = ?
        """,
        (304,),
    ).fetchone()

    print("Course with optional instructor:", result)

    print(
        "The NULL instructor_id represents the absence of an assigned "
        "instructor under this model."
    )


# =============================================================================
# 31. DERIVED VALUES AND SNAPSHOT VALUES
# =============================================================================

@dataclass
class InvoiceLine:
    quantity: int
    unit_price: Decimal

    @property
    def line_total(self) -> Decimal:
        return self.quantity * self.unit_price


def demonstrate_derived_values() -> None:
    print_section("31. DERIVED VALUES")

    line = InvoiceLine(
        quantity=3,
        unit_price=Decimal("199.99"),
    )

    print("Quantity:", line.quantity)
    print("Unit price:", line.unit_price)
    print("Derived line total:", line.line_total)

    print(
        "\nNot every derived value should be stored. "
        "Storing a derived value can improve read performance or preserve a "
        "historical snapshot, but creates a consistency responsibility."
    )


# =============================================================================
# 32. HISTORICAL SNAPSHOT EXAMPLE
# =============================================================================

@dataclass(frozen=True)
class InvoiceLineSnapshot:
    product_id: int
    product_name_at_sale: str
    quantity: int
    unit_price_at_sale: Decimal

    @property
    def total(self) -> Decimal:
        return self.quantity * self.unit_price_at_sale


def demonstrate_snapshot_modeling() -> None:
    print_section("32. HISTORICAL SNAPSHOTS")

    snapshot = InvoiceLineSnapshot(
        product_id=10,
        product_name_at_sale="Keyboard",
        quantity=2,
        unit_price_at_sale=Decimal("2500.00"),
    )

    print(snapshot)
    print("Historical total:", snapshot.total)

    print(
        "\nA sales invoice often needs historical values rather than a "
        "live lookup of today's product price."
    )


# =============================================================================
# 33. ENTITY VERSUS ATTRIBUTE DECISIONS
# =============================================================================

def entity_or_attribute_decision_guide() -> None:
    print_section("33. ENTITY VS ATTRIBUTE")

    print(
        "Ask whether the concept has an independent identity, relationships, "
        "lifecycle, or attributes of its own."
    )

    print("\nExample: CUSTOMER phone number")
    print(
        "If one customer has many phone numbers and each number has its own "
        "metadata, a separate CUSTOMER_PHONE entity may be appropriate."
    )

    print("\nExample: CUSTOMER date_of_birth")
    print(
        "A date of birth normally does not require an independent identity, "
        "so it is naturally modeled as an attribute."
    )

    print("\nExample: ADDRESS")
    print(
        "If addresses are shared, independently managed, classified, or "
        "historically tracked, treating ADDRESS as an entity may be useful."
    )


# =============================================================================
# 34. RELATIONSHIP ATTRIBUTE DECISIONS
# =============================================================================

def relationship_attribute_guide() -> None:
    print_section("34. ATTRIBUTES OF RELATIONSHIPS")

    print(
        "A relationship attribute describes the association rather than "
        "either participating entity."
    )

    print("\nSTUDENT -- ENROLLS -- COURSE")
    print("grade belongs to the enrollment, not permanently to the student.")
    print("enrolled_on belongs to the enrollment.")
    print("course title belongs to COURSE.")
    print("student email belongs to STUDENT.")


# =============================================================================
# 35. BUSINESS RULES THAT KEYS CANNOT EXPRESS ALONE
# =============================================================================

def demonstrate_complex_business_rules() -> None:
    print_section("35. BUSINESS RULES BEYOND BASIC KEYS")

    print("Rule: An employee may have one manager.")
    print("A simple foreign key can represent this.")

    print("\nRule: A manager must belong to the same department as the employee.")
    print(
        "This requires additional enforcement, such as a composite foreign "
        "key, trigger, application logic, or another carefully designed model."
    )

    print("\nRule: A customer may have at most three active addresses.")
    print(
        "A basic UNIQUE constraint cannot express this cardinality directly "
        "in a portable relational design."
    )

    print("\nRule: A course cannot have overlapping scheduled sessions.")
    print(
        "This is a temporal business rule that may require specialized "
        "constraints, exclusion mechanisms, triggers, or transactional logic "
        "depending on the database."
    )


# =============================================================================
# 36. VALIDATION LAYERS
# =============================================================================

def explain_validation_layers() -> None:
    print_section("36. VALIDATION LAYERS")

    print("Layer 1: User-interface validation")
    print("Provides immediate feedback but cannot be trusted as the only control.")

    print("\nLayer 2: Application/domain validation")
    print("Expresses business behavior and reusable domain rules.")

    print("\nLayer 3: Database constraints")
    print(
        "Protects persistent data against invalid states even when multiple "
        "applications or processes write to the database."
    )

    print(
        "\nStrong systems use the database as an important integrity boundary "
        "rather than relying exclusively on application code."
    )


# =============================================================================
# 37. MODELING WORKFLOW
# =============================================================================

def explain_modeling_workflow() -> None:
    print_section("37. DATA MODELING WORKFLOW")

    steps = [
        "1. Identify business scope and stakeholders.",
        "2. Collect business rules and definitions.",
        "3. Identify candidate entities.",
        "4. Identify attributes for each entity.",
        "5. Determine candidate identifiers.",
        "6. Identify relationships.",
        "7. Specify cardinality and optionality.",
        "8. Resolve many-to-many relationships.",
        "9. Identify relationship attributes.",
        "10. Validate functional dependencies.",
        "11. Normalize where appropriate.",
        "12. Map the conceptual model to relations.",
        "13. Add primary keys, foreign keys, UNIQUE and CHECK constraints.",
        "14. Define indexes based on workload.",
        "15. Test valid and invalid states.",
        "16. Review security, lifecycle, retention, and operational requirements.",
    ]

    for step in steps:
        print(step)


# =============================================================================
# 38. COMMON MODELING MISTAKES
# =============================================================================

def demonstrate_common_mistakes() -> None:
    print_section("38. COMMON MODELING MISTAKES")

    mistakes = {
        "No stable identifier": (
            "Without a reliable key, entities can be difficult to reference."
        ),
        "Everything as one table": (
            "Creates redundancy and update anomalies."
        ),
        "Everything as separate tables": (
            "Can introduce unnecessary complexity and excessive joins."
        ),
        "Ignoring optionality": (
            "Allows invalid or ambiguous relationship states."
        ),
        "Missing UNIQUE constraints": (
            "A surrogate key alone does not prevent duplicate business facts."
        ),
        "Storing comma-separated lists": (
            "Violates relational atomicity and makes querying and validation difficult."
        ),
        "Overusing NULL": (
            "Can hide different meanings such as unknown, not applicable, "
            "not yet determined, or missing."
        ),
        "Encoding business rules only in code": (
            "Other writers can bypass application-level validation."
        ),
        "Choosing cascade deletes casually": (
            "A delete can unintentionally remove large amounts of related data."
        ),
        "Premature denormalization": (
            "Introduces synchronization problems before a performance need is proven."
        ),
    }

    for mistake, consequence in mistakes.items():
        print(f"\n{mistake}")
        print(f"  {consequence}")


# =============================================================================
# 39. ER MODEL TO RELATIONAL MODEL RULES
# =============================================================================

def explain_er_to_relational_mapping() -> None:
    print_section("39. ER TO RELATIONAL MAPPING")

    rules = [
        (
            "Strong entity",
            "Create a relation containing its attributes and primary key."
        ),
        (
            "1:N relationship",
            "Place the primary key of the 1-side as a foreign key on the N-side."
        ),
        (
            "M:N relationship",
            "Create an associative relation containing foreign keys to both entities."
        ),
        (
            "1:1 relationship",
            "Place a foreign key on one side, often the side with mandatory participation."
        ),
        (
            "Multivalued attribute",
            "Create a separate relation containing the owner's key and the value."
        ),
        (
            "Composite attribute",
            "Store its atomic components when using a normalized relational design."
        ),
        (
            "Weak entity",
            "Include the owner's key as part of the dependent entity's identifying key."
        ),
        (
            "Recursive relationship",
            "Use a self-referencing foreign key or associative relation depending on cardinality."
        ),
    ]

    for concept, rule in rules:
        print(f"\n{concept}:")
        print(f"  {rule}")


# =============================================================================
# 40. DATA DICTIONARY
# =============================================================================

@dataclass(frozen=True)
class ColumnDefinition:
    table: str
    name: str
    data_type: str
    nullable: bool
    description: str


def build_data_dictionary() -> list[ColumnDefinition]:
    return [
        ColumnDefinition(
            "student",
            "student_id",
            "INTEGER",
            False,
            "Stable identifier for a student.",
        ),
        ColumnDefinition(
            "student",
            "name",
            "TEXT",
            False,
            "Student's display name.",
        ),
        ColumnDefinition(
            "student",
            "email",
            "TEXT",
            False,
            "Unique student email address.",
        ),
        ColumnDefinition(
            "course",
            "course_id",
            "INTEGER",
            False,
            "Stable identifier for a course.",
        ),
        ColumnDefinition(
            "course",
            "course_code",
            "TEXT",
            False,
            "Business identifier such as CS101.",
        ),
        ColumnDefinition(
            "enrollment",
            "student_id",
            "INTEGER",
            False,
            "Student participating in the enrollment.",
        ),
        ColumnDefinition(
            "enrollment",
            "course_id",
            "INTEGER",
            False,
            "Course participating in the enrollment.",
        ),
        ColumnDefinition(
            "enrollment",
            "grade",
            "TEXT",
            True,
            "Optional grade assigned to the enrollment.",
        ),
    ]


def demonstrate_data_dictionary() -> None:
    print_section("40. DATA DICTIONARY")

    for column in build_data_dictionary():
        print(
            f"{column.table}.{column.name:15} "
            f"type={column.data_type:8} "
            f"nullable={str(column.nullable):5} "
            f"| {column.description}"
        )


# =============================================================================
# 41. SCHEMA INTROSPECTION
# =============================================================================

def demonstrate_schema_introspection(connection: sqlite3.Connection) -> None:
    print_section("41. SCHEMA INTROSPECTION")

    tables = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
        """
    ).fetchall()

    print("Tables:")
    for table_name, in tables:
        print(" -", table_name)

    print("\nColumns in enrollment:")
    columns = connection.execute(
        "PRAGMA table_info(enrollment)"
    ).fetchall()

    for column in columns:
        cid, name, data_type, not_null, default_value, primary_key = column
        print(
            f"  {name:15} type={data_type:8} "
            f"not_null={not_null} pk_position={primary_key}"
        )

    print("\nForeign keys in enrollment:")
    foreign_keys = connection.execute(
        "PRAGMA foreign_key_list(enrollment)"
    ).fetchall()

    for foreign_key in foreign_keys:
        print(f"  {foreign_key}")


# =============================================================================
# 42. EXPLAIN QUERY PLAN
# =============================================================================

def demonstrate_query_plan(connection: sqlite3.Connection) -> None:
    print_section("42. QUERY PLAN")

    plan = connection.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT
            s.name,
            c.title
        FROM student AS s
        JOIN enrollment AS e
            ON e.student_id = s.student_id
        JOIN course AS c
            ON c.course_id = e.course_id
        WHERE s.student_id = ?
        """,
        (101,),
    ).fetchall()

    for row in plan:
        print(row)

    print(
        "\nQuery plans reveal how a database intends to access the data. "
        "They are useful when validating performance assumptions."
    )


# =============================================================================
# 43. TESTABLE BUSINESS RULE FUNCTIONS
# =============================================================================

def validate_email(email: str) -> None:
    if not EMAIL_DOMAIN.validate(email):
        raise ValueError("Invalid email address.")


def validate_course_credits(credits: int) -> None:
    if not 1 <= credits <= 6:
        raise ValueError("Course credits must be between 1 and 6.")


def validate_enrollment(
    student_id: int,
    course_id: int,
    grade: Optional[str],
) -> None:
    if student_id <= 0:
        raise ValueError("Student ID must be positive.")

    if course_id <= 0:
        raise ValueError("Course ID must be positive.")

    if grade is not None and grade not in {"A", "B", "C", "D", "F"}:
        raise ValueError("Grade must be A, B, C, D, F, or NULL.")


# =============================================================================
# 44. UNIT TESTS
# =============================================================================

class DataModelingTests(unittest.TestCase):
    """Executable tests for selected model rules."""

    def test_email_domain(self) -> None:
        self.assertTrue(EMAIL_DOMAIN.validate("test@example.com"))
        self.assertFalse(EMAIL_DOMAIN.validate("invalid"))

    def test_employee_cycle_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_employee_hierarchy(
                [
                    Employee(1, "A", 2),
                    Employee(2, "B", 1),
                ]
            )

    def test_employee_self_management_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_employee_hierarchy(
                [Employee(1, "A", 1)]
            )

    def test_order_requires_lines(self) -> None:
        with self.assertRaises(ValueError):
            OrderRecord(
                order_id=1,
                customer_id=1,
            ).validate()

    def test_positive_order_quantity(self) -> None:
        order = OrderRecord(order_id=1, customer_id=1)

        with self.assertRaises(ValueError):
            order.add_line(product_id=10, quantity=0)

    def test_enrollment_grade(self) -> None:
        validate_enrollment(1, 2, "A")

        with self.assertRaises(ValueError):
            validate_enrollment(1, 2, "Z")

    def test_database_foreign_key(self) -> None:
        connection = create_database()

        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO enrollment
                    (student_id, course_id, enrolled_on, grade)
                VALUES (?, ?, ?, ?)
                """,
                (999, 999, "2026-01-01", None),
            )

        connection.close()

    def test_composite_enrollment_key(self) -> None:
        connection = create_database()
        populate_database(connection)

        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO enrollment
                    (student_id, course_id, enrolled_on, grade)
                VALUES (?, ?, ?, ?)
                """,
                (101, 301, "2026-08-10", "B"),
            )

        connection.close()


def run_tests() -> None:
    print_section("44. EXECUTABLE TESTS")

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        DataModelingTests
    )

    result = unittest.TextTestRunner(
        verbosity=2
    ).run(suite)

    if not result.wasSuccessful():
        raise SystemExit(1)


# =============================================================================
# 45. MODELING COMPARISONS
# =============================================================================

def print_comparison_table() -> None:
    print_section("45. IMPORTANT MODELING COMPARISONS")

    comparisons = [
        (
            "Entity",
            "Independent concept with identity or lifecycle",
            "CUSTOMER, PRODUCT, STUDENT",
        ),
        (
            "Attribute",
            "Property describing a concept",
            "customer.email, product.price",
        ),
        (
            "Relationship",
            "Association between concepts",
            "CUSTOMER places ORDER",
        ),
        (
            "Primary key",
            "Selected identifier for relation rows",
            "student_id",
        ),
        (
            "Candidate key",
            "Any minimal unique identifier",
            "email, student_id",
        ),
        (
            "Foreign key",
            "Reference to a key in another relation",
            "enrollment.student_id",
        ),
        (
            "Natural key",
            "Business-meaningful identifier",
            "course_code",
        ),
        (
            "Surrogate key",
            "System-generated identifier",
            "course_id",
        ),
        (
            "Stored attribute",
            "Persisted value",
            "date_of_birth",
        ),
        (
            "Derived attribute",
            "Calculated from other information",
            "age",
        ),
        (
            "Normalization",
            "Reduce redundancy and dependency anomalies",
            "Separate STUDENT and COURSE facts",
        ),
        (
            "Denormalization",
            "Deliberate duplication for a specific workload",
            "Reporting snapshot",
        ),
    ]

    headers = ("Concept", "Meaning", "Example")
    widths = (20, 44, 36)

    print(
        f"{headers[0]:<{widths[0]}} | "
        f"{headers[1]:<{widths[1]}} | "
        f"{headers[2]:<{widths[2]}}"
    )
    print("-" * sum(widths) + "-+-")

    for row in comparisons:
        print(
            f"{row[0]:<{widths[0]}} | "
            f"{row[1]:<{widths[1]}} | "
            f"{row[2]:<{widths[2]}}"
        )


# =============================================================================
# 46. PRODUCTION DESIGN CONSIDERATIONS
# =============================================================================

def explain_production_considerations() -> None:
    print_section("46. PRODUCTION CONSIDERATIONS")

    considerations = [
        "Naming conventions must be consistent and documented.",
        "Data types should represent business semantics accurately.",
        "Primary keys should be stable enough for their intended role.",
        "Business uniqueness should be enforced explicitly.",
        "Foreign keys should preserve referential integrity.",
        "Nullable columns should have a clearly defined meaning.",
        "Delete behavior should reflect lifecycle semantics.",
        "Transactions should protect multi-step state changes.",
        "Indexes should be based on measured workload.",
        "Schema migrations should be versioned and reversible where practical.",
        "Sensitive data should be minimized and appropriately protected.",
        "Retention and archival rules should be reflected in lifecycle design.",
        "Audit requirements may require dedicated history structures.",
        "Large tables may eventually require partitioning or archival strategies.",
        "Model documentation should remain synchronized with the implemented schema.",
    ]

    for consideration in considerations:
        print("-", consideration)


# =============================================================================
# 47. COMPLETE EXAMPLE: E-COMMERCE CONCEPTUAL MODEL
# =============================================================================

def explain_ecommerce_model() -> None:
    print_section("47. COMPLETE E-COMMERCE EXAMPLE")

    print("Entities:")
    print("- CUSTOMER")
    print("- PRODUCT")
    print("- ORDER")
    print("- ORDER_LINE")
    print("- PAYMENT")
    print("- ADDRESS")

    print("\nRelationships:")
    print("- CUSTOMER 1:N ORDER")
    print("- ORDER 1:N ORDER_LINE")
    print("- PRODUCT 1:N ORDER_LINE")
    print("- ORDER 1:N PAYMENT")
    print("- CUSTOMER 1:N ADDRESS")

    print("\nPotential business rules:")
    print("- Every order belongs to exactly one customer.")
    print("- Every order has at least one order line.")
    print("- Every order line references one product.")
    print("- Quantity must be positive.")
    print("- A payment amount cannot be negative.")
    print("- An order cannot be marked SHIPPED before required payment conditions.")
    print("- An address may be designated as a default address under a uniqueness rule.")

    print("\nKey insight:")
    print(
        "The entity names are not enough. A useful model specifies identity, "
        "attributes, relationships, cardinality, optionality, and business rules."
    )


# =============================================================================
# 48. COMPLETE EXAMPLE: HOSPITAL MODELING CONSIDERATIONS
# =============================================================================

def explain_hospital_model() -> None:
    print_section("48. HOSPITAL DATA MODELING EXAMPLE")

    print("Possible entities:")
    print("- PATIENT")
    print("- DOCTOR")
    print("- APPOINTMENT")
    print("- DEPARTMENT")
    print("- PRESCRIPTION")
    print("- MEDICATION")

    print("\nPotential relationships:")
    print("- PATIENT books APPOINTMENT with DOCTOR.")
    print("- DOCTOR belongs to DEPARTMENT.")
    print("- PATIENT may receive PRESCRIPTION.")
    print("- PRESCRIPTION may contain multiple MEDICATION items.")

    print("\nModeling caution:")
    print(
        "Sensitive domains require particularly careful definition of access, "
        "retention, audit, identity, and historical correctness. "
        "The conceptual model should not expose more personal information "
        "than the business process actually requires."
    )


# =============================================================================
# 49. DATA MODEL TEST MATRIX
# =============================================================================

@dataclass(frozen=True)
class ModelTestCase:
    name: str
    description: str
    should_pass: bool
    test: Callable[[], None]


def build_model_test_matrix() -> list[ModelTestCase]:
    def valid_email() -> None:
        validate_email("user@example.com")

    def invalid_email() -> None:
        validate_email("not-valid")

    def valid_credits() -> None:
        validate_course_credits(4)

    def invalid_credits() -> None:
        validate_course_credits(10)

    return [
        ModelTestCase(
            "Valid email",
            "A syntactically valid email should be accepted.",
            True,
            valid_email,
        ),
        ModelTestCase(
            "Invalid email",
            "An invalid email should be rejected.",
            False,
            invalid_email,
        ),
        ModelTestCase(
            "Valid credits",
            "A course credit value within the domain should be accepted.",
            True,
            valid_credits,
        ),
        ModelTestCase(
            "Invalid credits",
            "A course credit value outside the domain should be rejected.",
            False,
            invalid_credits,
        ),
    ]


def demonstrate_model_test_matrix() -> None:
    print_section("49. MODEL TEST MATRIX")

    for case in build_model_test_matrix():
        try:
            case.test()
            actual_pass = True
        except (ValueError, TypeError):
            actual_pass = False

        expected = "PASS" if case.should_pass else "REJECT"
        actual = "PASS" if actual_pass else "REJECT"

        print(
            f"{case.name:20} expected={expected:6} actual={actual:6} "
            f"| {case.description}"
        )


# =============================================================================
# 50. FINAL INTEGRATED DEMONSTRATION
# =============================================================================

def run_integrated_example() -> None:
    """
    Build and query the complete relational model.

    This integrates:
        entities
        keys
        foreign keys
        constraints
        relationships
        associative entities
        SQL queries
        referential integrity
    """
    print_section("50. INTEGRATED RELATIONAL MODEL")

    connection = create_database()
    populate_database(connection)

    demonstrate_sql_queries(connection)

    print("\nAdding a valid student and enrollment atomically:")
    demonstrate_transaction(connection)

    print("\nTesting optional instructor relationship:")
    demonstrate_optional_foreign_key(connection)

    print("\nSchema:")
    demonstrate_schema_introspection(connection)

    print("\nQuery execution plan:")
    demonstrate_query_plan(connection)

    connection.close()


# =============================================================================
# 51. MAIN PROGRAM
# =============================================================================

def main() -> None:
    """
    Execute the complete learning sequence.

    Each section is intentionally independent enough to be studied separately,
    while the final database examples integrate the concepts into one model.
    """
    explain_fundamentals()
    demonstrate_domains()
    demonstrate_attribute_classifications()
    demonstrate_keys()
    demonstrate_relationships()
    demonstrate_business_rules()
    demonstrate_conceptual_model()
    demonstrate_relational_mapping()
    explain_functional_dependencies()
    demonstrate_normalization()
    demonstrate_anomalies()
    demonstrate_associative_entity()
    demonstrate_recursive_relationship()
    demonstrate_weak_entity()
    demonstrate_one_to_one()
    demonstrate_null_behavior()
    demonstrate_temporal_modeling()
    demonstrate_domain_model()
    compare_normalization_and_denormalization()
    compare_surrogate_and_natural_keys()
    demonstrate_indexing_principles()
    explain_composite_index()
    entity_or_attribute_decision_guide()
    relationship_attribute_guide()
    demonstrate_complex_business_rules()
    explain_validation_layers()
    explain_modeling_workflow()
    demonstrate_common_mistakes()
    explain_er_to_relational_mapping()
    demonstrate_data_dictionary()
    explain_production_considerations()
    explain_ecommerce_model()
    explain_hospital_model()
    demonstrate_model_test_matrix()
    print_comparison_table()

    connection = create_database()
    populate_database(connection)

    demonstrate_constraints(connection)
    demonstrate_delete_actions()
    demonstrate_security_principles(connection)
    demonstrate_query_plan(connection)

    connection.close()

    demonstrate_derived_values()
    demonstrate_snapshot_modeling()
    demonstrate_model_quality()
    run_integrated_example()

    # Unit tests are run last so the educational output appears before the
    # test runner output.
    run_tests()


if __name__ == "__main__":
    main()
