#!/usr/bin/env python3
"""
Entity Relationship Modeling
============================

A self-contained executable study of ER modeling through a university
course-registration domain.

The script progresses from:
    entities -> attributes -> keys -> relationships -> cardinality
    -> participation -> associative entities -> constraints
    -> normalization-aware design -> schema generation -> validation
    -> diagram export -> relationship queries

No external packages are required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable
import csv
import json
import re


# ---------------------------------------------------------------------------
# Core ER vocabulary
# ---------------------------------------------------------------------------

class Cardinality(Enum):
    ONE = "1"
    MANY = "N"


class Participation(Enum):
    OPTIONAL = "optional"
    MANDATORY = "mandatory"


class AttributeKind(Enum):
    SIMPLE = "simple"
    COMPOSITE = "composite"
    MULTIVALUED = "multivalued"
    DERIVED = "derived"


@dataclass(frozen=True)
class Attribute:
    """
    Describes an ER attribute independently from a physical database column.

    A composite attribute such as name can contain child attributes.
    A derived attribute is normally calculated rather than stored directly.
    A multivalued attribute usually becomes a separate relation when mapped
    to a relational schema.
    """
    name: str
    data_type: str
    kind: AttributeKind = AttributeKind.SIMPLE
    required: bool = False
    children: tuple["Attribute", ...] = ()
    description: str = ""

    def validate_definition(self) -> None:
        if not self.name.strip():
            raise ValueError("Attribute name cannot be empty.")
        if self.kind is AttributeKind.COMPOSITE and not self.children:
            raise ValueError(
                f"Composite attribute '{self.name}' must define child attributes."
            )
        if self.kind is not AttributeKind.COMPOSITE and self.children:
            raise ValueError(
                f"Only composite attributes may contain children: {self.name}"
            )

    def flatten(self) -> list["Attribute"]:
        """Return leaf attributes for relational mapping."""
        self.validate_definition()
        if self.kind is not AttributeKind.COMPOSITE:
            return [self]
        flattened: list[Attribute] = []
        for child in self.children:
            flattened.extend(child.flatten())
        return flattened


@dataclass
class Entity:
    """
    Represents an ER entity type.

    Attributes are kept as a dictionary so definitions can be validated for
    duplicate names and later mapped to SQL columns.
    """
    name: str
    description: str = ""
    attributes: dict[str, Attribute] = field(default_factory=dict)
    primary_key: tuple[str, ...] = ()

    def add_attribute(self, attribute: Attribute) -> None:
        attribute.validate_definition()
        key = attribute.name.lower()
        if key in {existing.lower() for existing in self.attributes}:
            raise ValueError(
                f"Entity '{self.name}' already contains attribute '{attribute.name}'."
            )
        self.attributes[attribute.name] = attribute

    def set_primary_key(self, *attribute_names: str) -> None:
        if not attribute_names:
            raise ValueError("An entity must have at least one primary-key attribute.")

        missing = [
            name for name in attribute_names if name not in self.attributes
        ]
        if missing:
            raise ValueError(
                f"Cannot define primary key for '{self.name}'; "
                f"missing attributes: {missing}"
            )

        derived = [
            name for name in attribute_names
            if self.attributes[name].kind is AttributeKind.DERIVED
        ]
        if derived:
            raise ValueError(
                f"Derived attributes cannot form a primary key: {derived}"
            )

        self.primary_key = tuple(attribute_names)

    def get_leaf_attributes(self) -> list[Attribute]:
        result: list[Attribute] = []
        for attribute in self.attributes.values():
            result.extend(attribute.flatten())
        return result

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.name.strip():
            errors.append("Entity has an empty name.")

        if not self.attributes:
            errors.append(f"Entity '{self.name}' has no attributes.")

        if not self.primary_key:
            errors.append(f"Entity '{self.name}' has no primary key.")
        else:
            for key in self.primary_key:
                if key not in self.attributes:
                    errors.append(
                        f"Primary-key attribute '{key}' does not exist in "
                        f"entity '{self.name}'."
                    )

        for attribute in self.attributes.values():
            try:
                attribute.validate_definition()
            except ValueError as exc:
                errors.append(str(exc))

        return errors


@dataclass(frozen=True)
class Endpoint:
    """
    One side of an ER relationship.

    minimum=0 means optional participation.
    minimum=1 means mandatory participation.
    maximum=1 means one related instance.
    maximum=None means many related instances.
    """
    entity: str
    minimum: int
    maximum: int | None

    def validate(self) -> None:
        if self.minimum not in (0, 1):
            raise ValueError("ER minimum cardinality must be 0 or 1.")
        if self.maximum is not None and self.maximum < 1:
            raise ValueError("ER maximum cardinality must be positive.")
        if self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Minimum cardinality cannot exceed maximum cardinality.")

    @property
    def participation(self) -> Participation:
        return (
            Participation.MANDATORY
            if self.minimum == 1
            else Participation.OPTIONAL
        )

    @property
    def cardinality(self) -> Cardinality:
        return Cardinality.ONE if self.maximum == 1 else Cardinality.MANY

    def min_max_label(self) -> str:
        maximum = "N" if self.maximum is None else str(self.maximum)
        return f"({self.minimum},{maximum})"


@dataclass
class Relationship:
    """
    Models a named relationship between entity types.

    A relationship may carry attributes itself. Such attributes are especially
    important for many-to-many relationships because they belong to the
    association, not to either participating entity.
    """
    name: str
    left: Endpoint
    right: Endpoint
    description: str = ""
    attributes: dict[str, Attribute] = field(default_factory=dict)

    def validate(self, known_entities: set[str]) -> list[str]:
        errors: list[str] = []

        if not self.name.strip():
            errors.append("Relationship has an empty name.")

        try:
            self.left.validate()
            self.right.validate()
        except ValueError as exc:
            errors.append(str(exc))

        if self.left.entity not in known_entities:
            errors.append(
                f"Relationship '{self.name}' references unknown entity "
                f"'{self.left.entity}'."
            )
        if self.right.entity not in known_entities:
            errors.append(
                f"Relationship '{self.name}' references unknown entity "
                f"'{self.right.entity}'."
            )

        for attribute in self.attributes.values():
            try:
                attribute.validate_definition()
            except ValueError as exc:
                errors.append(str(exc))

        return errors

    @property
    def is_many_to_many(self) -> bool:
        return (
            self.left.maximum is None
            and self.right.maximum is None
        )

    @property
    def is_one_to_many(self) -> bool:
        return (
            self.left.maximum == 1 and self.right.maximum is None
        ) or (
            self.left.maximum is None and self.right.maximum == 1
        )

    @property
    def is_one_to_one(self) -> bool:
        return self.left.maximum == 1 and self.right.maximum == 1


@dataclass
class ERModel:
    """Container for entities and relationships in an ER model."""

    name: str
    entities: dict[str, Entity] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)

    def add_entity(self, entity: Entity) -> None:
        if entity.name in self.entities:
            raise ValueError(f"Duplicate entity: {entity.name}")
        self.entities[entity.name] = entity

    def add_relationship(self, relationship: Relationship) -> None:
        errors = relationship.validate(set(self.entities))
        if errors:
            raise ValueError("; ".join(errors))
        self.relationships.append(relationship)

    def validate(self) -> list[str]:
        errors: list[str] = []

        for entity in self.entities.values():
            errors.extend(entity.validate())

        entity_names = set(self.entities)
        for relationship in self.relationships:
            errors.extend(relationship.validate(entity_names))

        return errors

    def find_relationships_for(self, entity_name: str) -> list[Relationship]:
        return [
            relationship
            for relationship in self.relationships
            if relationship.left.entity == entity_name
            or relationship.right.entity == entity_name
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "entities": [
                {
                    "name": entity.name,
                    "description": entity.description,
                    "primary_key": list(entity.primary_key),
                    "attributes": [
                        {
                            "name": attribute.name,
                            "data_type": attribute.data_type,
                            "kind": attribute.kind.value,
                            "required": attribute.required,
                            "description": attribute.description,
                            "children": [
                                {
                                    "name": child.name,
                                    "data_type": child.data_type,
                                    "kind": child.kind.value,
                                    "required": child.required,
                                    "description": child.description,
                                }
                                for child in attribute.children
                            ],
                        }
                        for attribute in entity.attributes.values()
                    ],
                }
                for entity in self.entities.values()
            ],
            "relationships": [
                {
                    "name": relationship.name,
                    "description": relationship.description,
                    "left": {
                        "entity": relationship.left.entity,
                        "min": relationship.left.minimum,
                        "max": relationship.left.maximum,
                    },
                    "right": {
                        "entity": relationship.right.entity,
                        "min": relationship.right.minimum,
                        "max": relationship.right.maximum,
                    },
                    "attributes": [
                        {
                            "name": attribute.name,
                            "data_type": attribute.data_type,
                            "kind": attribute.kind.value,
                            "required": attribute.required,
                            "description": attribute.description,
                        }
                        for attribute in relationship.attributes.values()
                    ],
                }
                for relationship in self.relationships
            ],
        }

    def to_mermaid(self) -> str:
        """
        Produce an ER diagram representation.

        Mermaid's ER syntax expresses cardinality at relationship endpoints.
        The textual relationship names and attributes remain tied to the
        conceptual model rather than to a particular SQL implementation.
        """
        lines = ["erDiagram"]

        def endpoint_marker(endpoint: Endpoint) -> str:
            if endpoint.minimum == 0 and endpoint.maximum == 1:
                return "o|"
            if endpoint.minimum == 1 and endpoint.maximum == 1:
                return "||"
            if endpoint.minimum == 0 and endpoint.maximum is None:
                return "o{"
            return "|{"

        for entity in self.entities.values():
            lines.append(f"    {entity.name} {{")
            for attribute in entity.get_leaf_attributes():
                marker = "PK " if attribute.name in entity.primary_key else ""
                if attribute.kind is AttributeKind.DERIVED:
                    marker = "DERIVED "
                lines.append(
                    f"        {attribute.data_type} {attribute.name} "
                    f'"{marker}{attribute.description}"'
                )
            lines.append("    }")

        for relationship in self.relationships:
            left_marker = endpoint_marker(self._orient_endpoint(relationship, True))
            right_marker = endpoint_marker(self._orient_endpoint(relationship, False))
            lines.append(
                f"    {relationship.left.entity} {left_marker}--{right_marker} "
                f"{relationship.right.entity} : {relationship.name}"
            )

        return "\n".join(lines)

    @staticmethod
    def _orient_endpoint(
        relationship: Relationship, left: bool
    ) -> Endpoint:
        return relationship.left if left else relationship.right


# ---------------------------------------------------------------------------
# Relational mapping
# ---------------------------------------------------------------------------

@dataclass
class SQLTable:
    name: str
    columns: list[tuple[str, str, bool]] = field(default_factory=list)
    primary_key: tuple[str, ...] = ()
    foreign_keys: list[tuple[str, str, str]] = field(default_factory=list)

    def add_column(self, name: str, sql_type: str, nullable: bool) -> None:
        self.columns.append((name, sql_type, nullable))


PYTHON_TO_SQL = {
    "integer": "INTEGER",
    "string": "VARCHAR(255)",
    "text": "TEXT",
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "boolean": "BOOLEAN",
    "decimal": "DECIMAL(12,2)",
}


def map_er_model_to_sql(model: ERModel) -> list[SQLTable]:
    """
    Convert the conceptual ER model into a practical relational design.

    The important mapping decisions are:
    - entity -> table
    - simple attribute -> column
    - composite attribute -> leaf columns
    - one-to-many -> foreign key on the many side
    - many-to-many -> associative table
    - relationship attributes -> associative table columns
    """
    tables: dict[str, SQLTable] = {}

    for entity in model.entities.values():
        table = SQLTable(entity.name)
        for attribute in entity.get_leaf_attributes():
            if attribute.kind is AttributeKind.MULTIVALUED:
                continue
            sql_type = PYTHON_TO_SQL.get(attribute.data_type, "TEXT")
            table.add_column(
                attribute.name,
                sql_type,
                not attribute.required and attribute.name not in entity.primary_key,
            )
        table.primary_key = entity.primary_key
        tables[entity.name] = table

        # A multivalued attribute cannot safely be represented by putting
        # several values into one scalar column. Create a separate relation.
        for attribute in entity.attributes.values():
            if attribute.kind is AttributeKind.MULTIVALUED:
                value_table = SQLTable(f"{entity.name}_{attribute.name}")
                for key in entity.primary_key:
                    key_type = next(
                        a.data_type
                        for a in entity.get_leaf_attributes()
                        if a.name == key
                    )
                    value_table.add_column(
                        f"{entity.name}_{key}",
                        PYTHON_TO_SQL.get(key_type, "TEXT"),
                        False,
                    )
                    value_table.foreign_keys.append(
                        (
                            f"{entity.name}_{key}",
                            entity.name,
                            key,
                        )
                    )

                value_table.add_column(
                    "value",
                    PYTHON_TO_SQL.get(attribute.data_type, "TEXT"),
                    False,
                )
                value_table.primary_key = tuple(
                    [f"{entity.name}_{key}" for key in entity.primary_key]
                    + ["value"]
                )
                tables[value_table.name] = value_table

    for relationship in model.relationships:
        left_entity = model.entities[relationship.left.entity]
        right_entity = model.entities[relationship.right.entity]

        if relationship.is_many_to_many:
            table_name = relationship.name
            if table_name in tables:
                raise ValueError(f"Generated table already exists: {table_name}")

            association = SQLTable(table_name)

            for entity in (left_entity, right_entity):
                for key in entity.primary_key:
                    attribute = entity.attributes[key]
                    column_name = f"{entity.name}_{key}"
                    association.add_column(
                        column_name,
                        PYTHON_TO_SQL.get(attribute.data_type, "TEXT"),
                        False,
                    )
                    association.foreign_keys.append(
                        (column_name, entity.name, key)
                    )

            for attribute in relationship.attributes.values():
                association.add_column(
                    attribute.name,
                    PYTHON_TO_SQL.get(attribute.data_type, "TEXT"),
                    not attribute.required,
                )

            association.primary_key = tuple(
                f"{left_entity.name}_{key}" for key in left_entity.primary_key
            ) + tuple(
                f"{right_entity.name}_{key}" for key in right_entity.primary_key
            )
            tables[table_name] = association

        elif relationship.is_one_to_many:
            one = (
                relationship.left
                if relationship.left.maximum == 1
                else relationship.right
            )
            many = (
                relationship.right
                if relationship.left.maximum == 1
                else relationship.left
            )

            one_entity = model.entities[one.entity]
            many_table = tables[many.entity]

            # The foreign key belongs on the many side because each many-side
            # instance references at most one parent in this relationship.
            for key in one_entity.primary_key:
                source_attribute = one_entity.attributes[key]
                foreign_key_column = f"{one_entity.name}_{key}"
                if not any(
                    column[0] == foreign_key_column
                    for column in many_table.columns
                ):
                    nullable = many.minimum == 0
                    many_table.add_column(
                        foreign_key_column,
                        PYTHON_TO_SQL.get(
                            source_attribute.data_type, "TEXT"
                        ),
                        nullable,
                    )
                    many_table.foreign_keys.append(
                        (foreign_key_column, one.entity, key)
                    )

        elif relationship.is_one_to_one:
            # For a 1:1 relationship, the foreign key can be placed on the
            # mandatory side or selected according to ownership semantics.
            # Here the right entity receives it unless the right side is
            # mandatory and the left side is optional, in which case the
            # right-side row must reference the left row.
            target = model.entities[relationship.right.entity]
            source = model.entities[relationship.left.entity]
            target_table = tables[target.name]

            for key in source.primary_key:
                source_attribute = source.attributes[key]
                foreign_key_column = f"{source.name}_{key}"
                target_table.add_column(
                    foreign_key_column,
                    PYTHON_TO_SQL.get(source_attribute.data_type, "TEXT"),
                    relationship.right.minimum == 0,
                )
                target_table.foreign_keys.append(
                    (foreign_key_column, source.name, key)
                )

    return list(tables.values())


def generate_sql(tables: Iterable[SQLTable]) -> str:
    """Generate readable PostgreSQL-compatible DDL from mapped tables."""
    statements: list[str] = []

    for table in tables:
        column_lines = []
        for name, sql_type, nullable in table.columns:
            nullability = "" if nullable else " NOT NULL"
            column_lines.append(f"    {name} {sql_type}{nullability}")

        if table.primary_key:
            column_lines.append(
                "    PRIMARY KEY (" + ", ".join(table.primary_key) + ")"
            )

        for column, referenced_table, referenced_column in table.foreign_keys:
            column_lines.append(
                f"    FOREIGN KEY ({column}) REFERENCES "
                f"{referenced_table}({referenced_column})"
            )

        statements.append(
            f"CREATE TABLE {table.name} (\n"
            + ",\n".join(column_lines)
            + "\n);"
        )

    return "\n\n".join(statements)


# ---------------------------------------------------------------------------
# Example domain model
# ---------------------------------------------------------------------------

def build_university_model() -> ERModel:
    model = ERModel(
        name="University Course Registration",
    )

    student = Entity(
        "Student",
        "A learner who can register for university course offerings.",
    )
    student.add_attribute(
        Attribute(
            "student_id",
            "string",
            required=True,
            description="Stable institutional identifier",
        )
    )
    student.add_attribute(
        Attribute(
            "name",
            "string",
            kind=AttributeKind.COMPOSITE,
            children=(
                Attribute("first_name", "string", required=True),
                Attribute("last_name", "string", required=True),
            ),
            description="Student's decomposable name",
        )
    )
    student.add_attribute(
        Attribute(
            "email",
            "string",
            required=True,
            description="Institutional email address",
        )
    )
    student.add_attribute(
        Attribute(
            "phone_numbers",
            "string",
            kind=AttributeKind.MULTIVALUED,
            description="Zero or more contact numbers",
        )
    )
    student.add_attribute(
        Attribute(
            "registration_count",
            "integer",
            kind=AttributeKind.DERIVED,
            description="Calculated from enrollment records",
        )
    )
    student.set_primary_key("student_id")
    model.add_entity(student)

    instructor = Entity(
        "Instructor",
        "Faculty member responsible for teaching course offerings.",
    )
    instructor.add_attribute(
        Attribute(
            "instructor_id",
            "string",
            required=True,
            description="Faculty identifier",
        )
    )
    instructor.add_attribute(
        Attribute("name", "string", required=True, description="Faculty name")
    )
    instructor.add_attribute(
        Attribute("email", "string", required=True, description="Faculty email")
    )
    instructor.set_primary_key("instructor_id")
    model.add_entity(instructor)

    department = Entity(
        "Department",
        "Academic department that owns courses.",
    )
    department.add_attribute(
        Attribute(
            "department_id",
            "string",
            required=True,
            description="Department identifier",
        )
    )
    department.add_attribute(
        Attribute(
            "name",
            "string",
            required=True,
            description="Department name",
        )
    )
    department.set_primary_key("department_id")
    model.add_entity(department)

    course = Entity(
        "Course",
        "Reusable academic course definition, independent of a semester.",
    )
    course.add_attribute(
        Attribute(
            "course_id",
            "string",
            required=True,
            description="Course identifier",
        )
    )
    course.add_attribute(
        Attribute(
            "title",
            "string",
            required=True,
            description="Official course title",
        )
    )
    course.add_attribute(
        Attribute(
            "credits",
            "integer",
            required=True,
            description="Academic credit value",
        )
    )
    course.set_primary_key("course_id")
    model.add_entity(course)

    offering = Entity(
        "CourseOffering",
        "A particular scheduled instance of a course in a term.",
    )
    offering.add_attribute(
        Attribute(
            "offering_id",
            "string",
            required=True,
            description="Offering identifier",
        )
    )
    offering.add_attribute(
        Attribute(
            "term",
            "string",
            required=True,
            description="Academic term such as 2026-FALL",
        )
    )
    offering.add_attribute(
        Attribute(
            "capacity",
            "integer",
            required=True,
            description="Maximum number of enrolled students",
        )
    )
    offering.add_attribute(
        Attribute(
            "room",
            "string",
            required=False,
            description="Scheduled classroom",
        )
    )
    offering.set_primary_key("offering_id")
    model.add_entity(offering)

    enrollment = Entity(
        "Enrollment",
        "Associative entity representing a student's registration in an offering.",
    )
    enrollment.add_attribute(
        Attribute(
            "enrollment_id",
            "string",
            required=True,
            description="Enrollment record identifier",
        )
    )
    enrollment.add_attribute(
        Attribute(
            "enrolled_on",
            "date",
            required=True,
            description="Registration date",
        )
    )
    enrollment.add_attribute(
        Attribute(
            "status",
            "string",
            required=True,
            description="ACTIVE, DROPPED, or COMPLETED",
        )
    )
    enrollment.add_attribute(
        Attribute(
            "grade",
            "string",
            required=False,
            description="Final grade when available",
        )
    )
    enrollment.set_primary_key("enrollment_id")
    model.add_entity(enrollment)

    # Department owns zero or many courses; every course belongs to one
    # department. This is a classic 1:N relationship.
    model.add_relationship(
        Relationship(
            "OFFERS",
            Endpoint("Department", 0, None),
            Endpoint("Course", 1, 1),
            "A department may own many courses; each course has one owner.",
        )
    )

    # A course can have many offerings over time, while each offering is
    # generated from exactly one course definition.
    model.add_relationship(
        Relationship(
            "HAS_OFFERING",
            Endpoint("Course", 0, None),
            Endpoint("CourseOffering", 1, 1),
            "Course definition to scheduled offering.",
        )
    )

    # An instructor may teach multiple offerings. An offering requires at
    # least one instructor in this simplified model.
    model.add_relationship(
        Relationship(
            "TEACHES",
            Endpoint("Instructor", 0, None),
            Endpoint("CourseOffering", 1, None),
            "Teaching assignment.",
        )
    )

    # Enrollment is the associative entity resolving the conceptual
    # Student <-> CourseOffering many-to-many relationship.
    model.add_relationship(
        Relationship(
            "STUDENT_ENROLLMENT",
            Endpoint("Student", 0, None),
            Endpoint("Enrollment", 1, 1),
            "Student can have many enrollment records.",
        )
    )

    model.add_relationship(
        Relationship(
            "OFFERING_ENROLLMENT",
            Endpoint("CourseOffering", 0, None),
            Endpoint("Enrollment", 1, 1),
            "Offering can contain many enrollment records.",
        )
    )

    return model


# ---------------------------------------------------------------------------
# Sample operational data and relationship-aware validation
# ---------------------------------------------------------------------------

@dataclass
class EnrollmentRecord:
    enrollment_id: str
    student_id: str
    offering_id: str
    enrolled_on: str
    status: str
    grade: str | None = None


@dataclass
class OfferingRecord:
    offering_id: str
    course_id: str
    term: str
    capacity: int


class RegistrationService:
    """
    A small domain service showing how an ER model becomes application rules.

    The ER diagram defines structural relationships. The service adds
    business constraints such as capacity and duplicate registration.
    """

    VALID_STATUSES = {"ACTIVE", "DROPPED", "COMPLETED"}

    def __init__(self) -> None:
        self.students: set[str] = set()
        self.offerings: dict[str, OfferingRecord] = {}
        self.enrollments: dict[str, EnrollmentRecord] = {}

    def add_student(self, student_id: str) -> None:
        if not re.fullmatch(r"STU-\d{4}", student_id):
            raise ValueError("Student ID must look like STU-0001.")
        if student_id in self.students:
            raise ValueError(f"Student already exists: {student_id}")
        self.students.add(student_id)

    def add_offering(self, offering: OfferingRecord) -> None:
        if offering.capacity <= 0:
            raise ValueError("Offering capacity must be positive.")
        if offering.offering_id in self.offerings:
            raise ValueError(
                f"Offering already exists: {offering.offering_id}"
            )
        self.offerings[offering.offering_id] = offering

    def enroll(
        self,
        enrollment_id: str,
        student_id: str,
        offering_id: str,
        enrolled_on: str,
    ) -> EnrollmentRecord:
        if student_id not in self.students:
            raise KeyError(f"Unknown student: {student_id}")
        if offering_id not in self.offerings:
            raise KeyError(f"Unknown offering: {offering_id}")
        if enrollment_id in self.enrollments:
            raise ValueError(
                f"Enrollment identifier already exists: {enrollment_id}"
            )

        active_for_student = {
            record.offering_id
            for record in self.enrollments.values()
            if record.student_id == student_id
            and record.status == "ACTIVE"
        }
        if offering_id in active_for_student:
            raise ValueError(
                "The student already has an active enrollment for this offering."
            )

        offering = self.offerings[offering_id]
        active_count = sum(
            record.status == "ACTIVE"
            and record.offering_id == offering_id
            for record in self.enrollments.values()
        )

        if active_count >= offering.capacity:
            raise RuntimeError(
                f"Offering {offering_id} has reached its capacity."
            )

        record = EnrollmentRecord(
            enrollment_id=enrollment_id,
            student_id=student_id,
            offering_id=offering_id,
            enrolled_on=enrolled_on,
            status="ACTIVE",
        )
        self.enrollments[enrollment_id] = record
        return record

    def drop(self, enrollment_id: str) -> None:
        record = self.enrollments.get(enrollment_id)
        if record is None:
            raise KeyError(f"Unknown enrollment: {enrollment_id}")
        if record.status != "ACTIVE":
            raise ValueError(
                f"Only ACTIVE enrollments can be dropped; "
                f"current state is {record.status}."
            )
        record.status = "DROPPED"

    def set_grade(self, enrollment_id: str, grade: str) -> None:
        record = self.enrollments.get(enrollment_id)
        if record is None:
            raise KeyError(f"Unknown enrollment: {enrollment_id}")
        if record.status not in {"ACTIVE", "COMPLETED"}:
            raise ValueError(
                "A grade cannot be assigned to a dropped enrollment."
            )
        if grade not in {"A", "B", "C", "D", "F"}:
            raise ValueError("Grade must be A, B, C, D, or F.")
        record.grade = grade
        record.status = "COMPLETED"

    def student_enrollments(self, student_id: str) -> list[EnrollmentRecord]:
        if student_id not in self.students:
            raise KeyError(f"Unknown student: {student_id}")
        return [
            record
            for record in self.enrollments.values()
            if record.student_id == student_id
        ]

    def offering_roster(self, offering_id: str) -> list[str]:
        if offering_id not in self.offerings:
            raise KeyError(f"Unknown offering: {offering_id}")
        return [
            record.student_id
            for record in self.enrollments.values()
            if record.offering_id == offering_id
            and record.status == "ACTIVE"
        ]

    def to_csv(self, path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "enrollment_id",
                    "student_id",
                    "offering_id",
                    "enrolled_on",
                    "status",
                    "grade",
                ],
            )
            writer.writeheader()
            for record in self.enrollments.values():
                writer.writerow(record.__dict__)


# ---------------------------------------------------------------------------
# Relationship-analysis utilities
# ---------------------------------------------------------------------------

def describe_relationship(relationship: Relationship) -> str:
    left = relationship.left
    right = relationship.right

    if relationship.is_many_to_many:
        pattern = "many-to-many"
    elif relationship.is_one_to_many:
        pattern = "one-to-many"
    elif relationship.is_one_to_one:
        pattern = "one-to-one"
    else:
        pattern = "non-standard bounded cardinality"

    return (
        f"{relationship.name}: {left.entity} {left.min_max_label()} "
        f"<-> {right.entity} {right.min_max_label()} "
        f"({pattern}); "
        f"{left.entity} participation is {left.participation.value}, "
        f"{right.entity} participation is {right.participation.value}."
    )


def demonstrate_identifying_vs_non_identifying() -> None:
    """
    Explain a key distinction through data structures.

    An identifying relationship means the child's identity depends on the
    parent's key. A non-identifying relationship keeps a separate child key
    and merely stores the parent key as a foreign key.
    """
    print("\nIDENTIFYING VS NON-IDENTIFYING RELATIONSHIPS")
    print(
        "Enrollment uses its own enrollment_id, so its identity does not "
        "depend on Student or CourseOffering."
    )
    print(
        "A dependent entity such as OrderLine could instead use "
        "(order_id, line_number) as its primary key, making the parent key "
        "part of the child's identity."
    )


# ---------------------------------------------------------------------------
# Deliberately invalid models for error detection
# ---------------------------------------------------------------------------

def demonstrate_validation_failures() -> None:
    print("\nMODEL VALIDATION FAILURES")

    broken = Entity("BrokenEntity")
    broken.add_attribute(
        Attribute("calculated_total", "decimal", kind=AttributeKind.DERIVED)
    )

    try:
        broken.set_primary_key("calculated_total")
    except ValueError as exc:
        print(f"Rejected invalid key: {exc}")

    model = ERModel("Broken Model")
    model.add_entity(broken)

    relationship = Relationship(
        "UNKNOWN_RELATION",
        Endpoint("BrokenEntity", 1, 1),
        Endpoint("MissingEntity", 0, None),
    )

    try:
        model.add_relationship(relationship)
    except ValueError as exc:
        print(f"Rejected invalid relationship: {exc}")


# ---------------------------------------------------------------------------
# Executable demonstration
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 78)
    print("ENTITY RELATIONSHIP MODELING: UNIVERSITY REGISTRATION")
    print("=" * 78)

    model = build_university_model()

    errors = model.validate()
    if errors:
        raise RuntimeError("Model should be valid:\n" + "\n".join(errors))

    print("\nENTITIES AND KEYS")
    for entity in model.entities.values():
        print(
            f"{entity.name}: PK={entity.primary_key}; "
            f"attributes={list(entity.attributes)}"
        )

    print("\nRELATIONSHIPS AND CARDINALITY")
    for relationship in model.relationships:
        print(describe_relationship(relationship))

    print("\nCOMPOSITE ATTRIBUTE MAPPING")
    student = model.entities["Student"]
    print(
        "Student.name expands to:",
        [attribute.name for attribute in student.get_leaf_attributes()],
    )

    print("\nMULTIVALUED ATTRIBUTE MAPPING")
    print(
        "Student.phone_numbers becomes a separate relation instead of "
        "storing comma-separated phone numbers in Student."
    )

    tables = map_er_model_to_sql(model)

    print("\nRELATIONAL MAPPING")
    for table in tables:
        print(
            f"{table.name}: columns={[column[0] for column in table.columns]}, "
            f"PK={table.primary_key}, FKs={table.foreign_keys}"
        )

    print("\nGENERATED SQL")
    print(generate_sql(tables))

    print("\nMERMAID ER DIAGRAM")
    print(model.to_mermaid())

    demonstrate_identifying_vs_non_identifying()
    demonstrate_validation_failures()

    print("\nAPPLICATION-LEVEL RELATIONSHIP RULES")
    service = RegistrationService()

    service.add_student("STU-0001")
    service.add_student("STU-0002")

    service.add_offering(
        OfferingRecord(
            offering_id="OFF-1001",
            course_id="CS-501",
            term="2026-FALL",
            capacity=2,
        )
    )

    service.add_offering(
        OfferingRecord(
            offering_id="OFF-1002",
            course_id="CS-601",
            term="2026-FALL",
            capacity=1,
        )
    )

    service.enroll(
        "ENR-0001",
        "STU-0001",
        "OFF-1001",
        "2026-08-01",
    )
    service.enroll(
        "ENR-0002",
        "STU-0002",
        "OFF-1001",
        "2026-08-02",
    )

    try:
        service.enroll(
            "ENR-0003",
            "STU-0001",
            "OFF-1001",
            "2026-08-03",
        )
    except ValueError as exc:
        print(f"Duplicate relationship rejected: {exc}")

    service.drop("ENR-0002")

    service.enroll(
        "ENR-0003",
        "STU-0001",
        "OFF-1002",
        "2026-08-03",
    )
    service.set_grade("ENR-0001", "A")

    print(
        "STU-0001 enrollments:",
        [record.__dict__ for record in service.student_enrollments("STU-0001")],
    )
    print(
        "OFF-1001 active roster:",
        service.offering_roster("OFF-1001"),
    )

    output_dir = Path("er_model_output")
    output_dir.mkdir(exist_ok=True)

    model_path = output_dir / "university_er_model.json"
    model_path.write_text(
        json.dumps(model.to_dict(), indent=2),
        encoding="utf-8",
    )

    sql_path = output_dir / "university_schema.sql"
    sql_path.write_text(
        generate_sql(tables),
        encoding="utf-8",
    )

    diagram_path = output_dir / "university_er_diagram.mmd"
    diagram_path.write_text(
        model.to_mermaid(),
        encoding="utf-8",
    )

    enrollment_path = output_dir / "enrollments.csv"
    service.to_csv(enrollment_path)

    print("\nFILES WRITTEN")
    for path in (
        model_path,
        sql_path,
        diagram_path,
        enrollment_path,
    ):
        print(path)

    print("\nDESIGN CHECK")
    print(
        "The conceptual model separates entity identity, descriptive "
        "attributes, relationship cardinality, participation constraints, "
        "and relationship resolution."
    )
    print(
        "The relational mapping then turns those conceptual decisions into "
        "tables, keys, foreign keys, and associative structures."
    )


if __name__ == "__main__":
    main()
