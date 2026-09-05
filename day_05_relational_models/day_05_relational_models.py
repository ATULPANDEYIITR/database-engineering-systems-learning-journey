"""
RELATIONAL MODEL
================

A comprehensive, executable study guide for the Relational Model in database
systems, progressing from absolute beginner concepts to advanced relational
reasoning.

The program uses only Python's standard library. It implements a small
in-memory relational engine so that relations, tuples, attributes, keys,
constraints, relational algebra, joins, normalization ideas, integrity
rules, query processing concepts, and practical database design can be
demonstrated directly through executable code.

Run:
    python relational_model.py
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


# ============================================================================
# 1. FUNDAMENTAL TERMINOLOGY
# ============================================================================

"""
A relational database is based on the mathematical concept of a relation.

Important terminology:

    Relation      -> conceptually represented as a table
    Tuple         -> a row
    Attribute     -> a column
    Domain        -> set of permitted values for an attribute
    Degree        -> number of attributes
    Cardinality   -> number of tuples
    Schema        -> structural definition of a relation
    Instance      -> tuples currently stored in the relation

A relational schema is commonly written as:

    STUDENT(StudentID, Name, Department, Age)

The values of attributes must come from appropriate domains.

A relational table is not merely an arbitrary spreadsheet. Relational
databases impose structural and integrity rules that make data suitable for
formal operations and reliable querying.
"""


@dataclass(frozen=True)
class Column:
    """Describes one attribute of a relation."""

    name: str
    domain: type
    nullable: bool = False


class RelationError(Exception):
    """Base exception for relational-model violations."""


class SchemaError(RelationError):
    """Raised when relation structure is invalid."""


class ConstraintError(RelationError):
    """Raised when an integrity constraint is violated."""


class Relation:
    """
    A small immutable-schema relation.

    This implementation stores tuples internally as dictionaries for
    readability, while enforcing a fixed ordered schema.

    Important relational properties demonstrated here:
        - Every tuple has the same attributes.
        - Attribute names are unique.
        - Attribute values must satisfy their domains.
        - NULL-like values are represented with None.
        - Duplicate tuples are rejected because a mathematical relation is a
          set of tuples.
    """

    def __init__(
        self,
        name: str,
        columns: Sequence[Column],
        rows: Iterable[Dict[str, Any]] = (),
        primary_key: Optional[Sequence[str]] = None,
        candidate_keys: Optional[Sequence[Sequence[str]]] = None,
        foreign_keys: Optional[
            Sequence[Tuple[Sequence[str], "Relation", Sequence[str]]]
        ] = None,
        checks: Optional[
            Sequence[Tuple[str, Callable[[Dict[str, Any]], bool]]]
        ] = None,
    ) -> None:
        self.name = name
        self.columns = tuple(columns)
        self._validate_schema()

        self.primary_key = tuple(primary_key or ())
        self.candidate_keys = tuple(
            tuple(key) for key in (candidate_keys or ())
        )
        self.foreign_keys = list(foreign_keys or [])
        self.checks = list(checks or [])

        self._validate_key_definitions()

        self._rows: List[Tuple[Any, ...]] = []
        self._row_set = set()

        for row in rows:
            self.insert(row)

    # ----------------------------------------------------------------------
    # Schema and validation
    # ----------------------------------------------------------------------

    def _validate_schema(self) -> None:
        if not self.name:
            raise SchemaError("Relation name cannot be empty.")

        names = [column.name for column in self.columns]

        if len(names) != len(set(names)):
            raise SchemaError("Attribute names must be unique.")

        if not names:
            raise SchemaError("A relation must have at least one attribute.")

    def _attribute_names(self) -> Tuple[str, ...]:
        return tuple(column.name for column in self.columns)

    def _validate_key_definitions(self) -> None:
        attributes = set(self._attribute_names())

        for key_name in self.primary_key:
            if key_name not in attributes:
                raise SchemaError(
                    f"Primary-key attribute {key_name!r} does not exist."
                )

        if self.primary_key and any(
            column.nullable
            for column in self.columns
            if column.name in self.primary_key
        ):
            raise SchemaError("Primary-key attributes cannot be nullable.")

        for candidate_key in self.candidate_keys:
            if not candidate_key:
                raise SchemaError("Candidate keys cannot be empty.")

            if not set(candidate_key).issubset(attributes):
                raise SchemaError(
                    f"Candidate key {candidate_key!r} contains an unknown "
                    "attribute."
                )

    def _validate_row_shape(self, row: Dict[str, Any]) -> None:
        expected = set(self._attribute_names())
        actual = set(row)

        missing = expected - actual
        extra = actual - expected

        if missing:
            raise SchemaError(f"Missing attributes: {sorted(missing)}.")

        if extra:
            raise SchemaError(f"Unknown attributes: {sorted(extra)}.")

    def _validate_row_domains(self, row: Dict[str, Any]) -> None:
        for column in self.columns:
            value = row[column.name]

            if value is None:
                if not column.nullable:
                    raise ConstraintError(
                        f"{column.name} cannot be NULL."
                    )
                continue

            # bool is a subclass of int in Python. Treating it as an integer
            # domain would be surprising for database-style validation, so
            # require exact type compatibility for this teaching engine.
            if type(value) is not column.domain:
                raise ConstraintError(
                    f"{column.name} expects {column.domain.__name__}, "
                    f"received {type(value).__name__}."
                )

    def _validate_checks(self, row: Dict[str, Any]) -> None:
        for description, check in self.checks:
            if not check(row):
                raise ConstraintError(
                    f"CHECK constraint failed: {description}"
                )

    def _tuple_from_row(self, row: Dict[str, Any]) -> Tuple[Any, ...]:
        return tuple(row[column.name] for column in self.columns)

    def _row_from_tuple(self, values: Tuple[Any, ...]) -> Dict[str, Any]:
        return {
            column.name: value
            for column, value in zip(self.columns, values)
        }

    def _key_value(
        self,
        row: Dict[str, Any],
        key: Sequence[str],
    ) -> Tuple[Any, ...]:
        return tuple(row[column] for column in key)

    # ----------------------------------------------------------------------
    # Data modification
    # ----------------------------------------------------------------------

    def insert(self, row: Dict[str, Any]) -> None:
        """Insert one tuple after enforcing relation-level constraints."""

        self._validate_row_shape(row)
        self._validate_row_domains(row)
        self._validate_checks(row)

        values = self._tuple_from_row(row)

        if values in self._row_set:
            raise ConstraintError(
                "Duplicate tuple rejected. Relations are sets of tuples."
            )

        # Primary-key uniqueness.
        if self.primary_key:
            new_key = self._key_value(row, self.primary_key)

            for existing in self.rows():
                if self._key_value(existing, self.primary_key) == new_key:
                    raise ConstraintError(
                        f"Duplicate primary key: {new_key}"
                    )

        # Candidate-key uniqueness.
        for candidate_key in self.candidate_keys:
            new_key = self._key_value(row, candidate_key)

            for existing in self.rows():
                if self._key_value(existing, candidate_key) == new_key:
                    raise ConstraintError(
                        f"Duplicate candidate key {candidate_key}: {new_key}"
                    )

        # Foreign-key referential integrity.
        for local_columns, referenced_relation, referenced_columns in (
            self.foreign_keys
        ):
            local_values = self._key_value(row, local_columns)

            # SQL permits a nullable foreign key to contain NULL. A composite
            # key containing NULL is therefore ignored by this simplified
            # enforcement logic.
            if any(value is None for value in local_values):
                continue

            found = False

            for referenced_row in referenced_relation.rows():
                referenced_values = self._key_value(
                    referenced_row,
                    referenced_columns,
                )

                if local_values == referenced_values:
                    found = True
                    break

            if not found:
                raise ConstraintError(
                    f"Foreign key {local_columns}={local_values} does not "
                    f"reference an existing tuple in "
                    f"{referenced_relation.name}."
                )

        self._rows.append(values)
        self._row_set.add(values)

    def delete_where(self, predicate: Callable[[Dict[str, Any]], bool]) -> int:
        """Delete tuples satisfying a predicate and return the count."""

        old_rows = self.rows()
        retained = [
            row for row in old_rows
            if not predicate(row)
        ]

        removed = len(old_rows) - len(retained)

        self._rows = []
        self._row_set = set()

        for row in retained:
            values = self._tuple_from_row(row)
            self._rows.append(values)
            self._row_set.add(values)

        return removed

    # ----------------------------------------------------------------------
    # Relational information
    # ----------------------------------------------------------------------

    @property
    def degree(self) -> int:
        """Number of attributes in the relation."""

        return len(self.columns)

    @property
    def cardinality(self) -> int:
        """Number of tuples in the current relation instance."""

        return len(self._rows)

    def rows(self) -> List[Dict[str, Any]]:
        """Return tuples as dictionaries."""

        return [
            self._row_from_tuple(values)
            for values in self._rows
        ]

    def copy(self, name: Optional[str] = None) -> "Relation":
        """Create a relation with the same schema and tuples."""

        return Relation(
            name=name or self.name,
            columns=self.columns,
            rows=self.rows(),
            primary_key=self.primary_key,
            candidate_keys=self.candidate_keys,
        )

    def __repr__(self) -> str:
        return (
            f"Relation(name={self.name!r}, degree={self.degree}, "
            f"cardinality={self.cardinality})"
        )

    def print_table(self, title: Optional[str] = None) -> None:
        """Display a relation in a readable tabular form."""

        if title:
            print(f"\n{title}")

        names = list(self._attribute_names())
        rows = self.rows()

        widths = {
            name: max(
                len(name),
                *(len(str(row[name])) for row in rows)
            )
            for name in names
        }

        separator = "+".join(
            "-" * (widths[name] + 2)
            for name in names
        )

        print("+" + separator + "+")
        print(
            "| "
            + " | ".join(
                f"{name:<{widths[name]}}"
                for name in names
            )
            + " |"
        )
        print("+" + separator + "+")

        for row in rows:
            print(
                "| "
                + " | ".join(
                    f"{str(row[name]):<{widths[name]}}"
                    for name in names
                )
                + " |"
            )

        print("+" + separator + "+")
        print(
            f"Degree = {self.degree}, Cardinality = {self.cardinality}"
        )


# ============================================================================
# 2. RELATION SCHEMA, INSTANCE, DEGREE, AND CARDINALITY
# ============================================================================

def section_01_fundamentals() -> None:
    print("\n" + "=" * 78)
    print("1. RELATIONAL FUNDAMENTALS")
    print("=" * 78)

    student_columns = [
        Column("StudentID", int),
        Column("Name", str),
        Column("Age", int),
        Column("Department", str),
    ]

    students = Relation(
        "STUDENT",
        student_columns,
        primary_key=("StudentID",),
        rows=[
            {
                "StudentID": 1,
                "Name": "Asha",
                "Age": 21,
                "Department": "CSE",
            },
            {
                "StudentID": 2,
                "Name": "Ravi",
                "Age": 22,
                "Department": "ECE",
            },
            {
                "StudentID": 3,
                "Name": "Meera",
                "Age": 20,
                "Department": "CSE",
            },
        ],
    )

    students.print_table("STUDENT relation")

    print("\nSchema:")
    print("STUDENT(StudentID, Name, Age, Department)")
    print("Degree:", students.degree)
    print("Cardinality:", students.cardinality)

    print(
        "\nTerminology: STUDENT is the relation, each dictionary is a tuple, "
        "and StudentID/Name/Age/Department are attributes."
    )


# ============================================================================
# 3. DOMAINS AND ATOMIC VALUES
# ============================================================================

def section_02_domains() -> None:
    print("\n" + "=" * 78)
    print("2. DOMAINS AND DOMAIN INTEGRITY")
    print("=" * 78)

    accounts = Relation(
        "ACCOUNT",
        [
            Column("AccountID", int),
            Column("Owner", str),
            Column("Balance", float),
        ],
        primary_key=("AccountID",),
        checks=[
            (
                "Balance must be non-negative",
                lambda row: row["Balance"] >= 0,
            )
        ],
        rows=[
            {
                "AccountID": 1001,
                "Owner": "Neha",
                "Balance": 5000.0,
            }
        ],
    )

    accounts.print_table("Valid ACCOUNT relation")

    print("\nAttempting invalid domain value:")
    try:
        accounts.insert(
            {
                "AccountID": 1002,
                "Owner": "Arun",
                "Balance": "not a number",
            }
        )
    except ConstraintError as error:
        print("Rejected:", error)

    print("\nAttempting invalid CHECK constraint:")
    try:
        accounts.insert(
            {
                "AccountID": 1002,
                "Owner": "Arun",
                "Balance": -10.0,
            }
        )
    except ConstraintError as error:
        print("Rejected:", error)


# ============================================================================
# 4. KEYS
# ============================================================================

def section_03_keys() -> None:
    print("\n" + "=" * 78)
    print("3. KEYS: SUPERKEY, CANDIDATE KEY, PRIMARY KEY, ALTERNATE KEY")
    print("=" * 78)

    employees = Relation(
        "EMPLOYEE",
        [
            Column("EmployeeID", int),
            Column("Email", str),
            Column("Name", str),
        ],
        primary_key=("EmployeeID",),
        candidate_keys=[
            ("Email",),
        ],
        rows=[
            {
                "EmployeeID": 101,
                "Email": "a@example.com",
                "Name": "Anita",
            },
            {
                "EmployeeID": 102,
                "Email": "b@example.com",
                "Name": "Bharat",
            },
        ],
    )

    employees.print_table("EMPLOYEE")

    print(
        "\nEmployeeID is the primary key. "
        "Email is an alternate candidate key."
    )

    print(
        "\nKey concepts:"
        "\n  Superkey: any attribute set that uniquely identifies tuples."
        "\n  Candidate key: a minimal superkey."
        "\n  Primary key: candidate key selected as the main identifier."
        "\n  Alternate key: candidate key not selected as primary key."
        "\n  Composite key: key containing multiple attributes."
        "\n  Surrogate key: artificial identifier such as an integer ID."
        "\n  Natural key: identifier with meaning in the business domain."
    )

    print("\nDuplicate primary key test:")
    try:
        employees.insert(
            {
                "EmployeeID": 101,
                "Email": "different@example.com",
                "Name": "Duplicate",
            }
        )
    except ConstraintError as error:
        print("Rejected:", error)

    print("\nDuplicate candidate key test:")
    try:
        employees.insert(
            {
                "EmployeeID": 103,
                "Email": "a@example.com",
                "Name": "Another Employee",
            }
        )
    except ConstraintError as error:
        print("Rejected:", error)


# ============================================================================
# 5. PRIMARY AND FOREIGN KEYS
# ============================================================================

def section_04_referential_integrity() -> None:
    print("\n" + "=" * 78)
    print("4. REFERENTIAL INTEGRITY AND FOREIGN KEYS")
    print("=" * 78)

    departments = Relation(
        "DEPARTMENT",
        [
            Column("DepartmentID", int),
            Column("DepartmentName", str),
        ],
        primary_key=("DepartmentID",),
        rows=[
            {
                "DepartmentID": 10,
                "DepartmentName": "Computer Science",
            },
            {
                "DepartmentID": 20,
                "DepartmentName": "Electronics",
            },
        ],
    )

    students = Relation(
        "STUDENT",
        [
            Column("StudentID", int),
            Column("Name", str),
            Column("DepartmentID", int),
        ],
        primary_key=("StudentID",),
        foreign_keys=[
            (
                ("DepartmentID",),
                departments,
                ("DepartmentID",),
            )
        ],
        rows=[
            {
                "StudentID": 1,
                "Name": "Asha",
                "DepartmentID": 10,
            },
            {
                "StudentID": 2,
                "Name": "Ravi",
                "DepartmentID": 20,
            },
        ],
    )

    departments.print_table("DEPARTMENT")
    students.print_table("STUDENT")

    print("\nValid foreign-key insertion:")
    students.insert(
        {
            "StudentID": 3,
            "Name": "Meera",
            "DepartmentID": 10,
        }
    )
    print("Accepted.")

    print("\nInvalid foreign-key insertion:")
    try:
        students.insert(
            {
                "StudentID": 4,
                "Name": "Kabir",
                "DepartmentID": 999,
            }
        )
    except ConstraintError as error:
        print("Rejected:", error)

    print(
        "\nReferential integrity requires every non-NULL foreign-key value "
        "to refer to a corresponding referenced key value."
    )


# ============================================================================
# 6. RELATIONAL ALGEBRA: SELECTION
# ============================================================================

def selection(
    relation: Relation,
    predicate: Callable[[Dict[str, Any]], bool],
    name: Optional[str] = None,
) -> Relation:
    """
    Relational algebra selection: sigma.

    SELECT-like interpretation:
        Keep rows satisfying a predicate.

    Mathematical intuition:
        σ_condition(R)
    """

    return Relation(
        name=name or f"SELECT_{relation.name}",
        columns=relation.columns,
        rows=[
            row
            for row in relation.rows()
            if predicate(row)
        ],
    )


def section_05_selection() -> None:
    print("\n" + "=" * 78)
    print("5. RELATIONAL ALGEBRA: SELECTION")
    print("=" * 78)

    employees = Relation(
        "EMPLOYEE",
        [
            Column("EmployeeID", int),
            Column("Name", str),
            Column("Department", str),
            Column("Salary", float),
        ],
        primary_key=("EmployeeID",),
        rows=[
            {
                "EmployeeID": 1,
                "Name": "Asha",
                "Department": "IT",
                "Salary": 80000.0,
            },
            {
                "EmployeeID": 2,
                "Name": "Ravi",
                "Department": "HR",
                "Salary": 65000.0,
            },
            {
                "EmployeeID": 3,
                "Name": "Meera",
                "Department": "IT",
                "Salary": 95000.0,
            },
            {
                "EmployeeID": 4,
                "Name": "Kabir",
                "Department": "Finance",
                "Salary": 70000.0,
            },
        ],
    )

    employees.print_table("Original EMPLOYEE")

    high_paid = selection(
        employees,
        lambda row: row["Salary"] >= 80000.0,
        "HIGH_PAID_EMPLOYEES",
    )

    high_paid.print_table(
        "Selection: employees with Salary >= 80000"
    )

    print("\nRelational algebra notation:")
    print("σ Salary >= 80000 (EMPLOYEE)")


# ============================================================================
# 7. RELATIONAL ALGEBRA: PROJECTION
# ============================================================================

def projection(
    relation: Relation,
    attributes: Sequence[str],
    name: Optional[str] = None,
) -> Relation:
    """
    Relational algebra projection: pi.

    Keep selected attributes and eliminate duplicate resulting tuples.
    """

    existing = set(relation._attribute_names())

    if not set(attributes).issubset(existing):
        missing = set(attributes) - existing
        raise SchemaError(f"Unknown projection attributes: {missing}")

    columns_by_name = {
        column.name: column
        for column in relation.columns
    }

    projected_columns = [
        columns_by_name[attribute]
        for attribute in attributes
    ]

    seen = set()
    projected_rows = []

    for row in relation.rows():
        projected = {
            attribute: row[attribute]
            for attribute in attributes
        }

        values = tuple(projected[attribute] for attribute in attributes)

        if values not in seen:
            seen.add(values)
            projected_rows.append(projected)

    return Relation(
        name=name or f"PROJECT_{relation.name}",
        columns=projected_columns,
        rows=projected_rows,
    )


def section_06_projection() -> None:
    print("\n" + "=" * 78)
    print("6. RELATIONAL ALGEBRA: PROJECTION")
    print("=" * 78)

    employees = Relation(
        "EMPLOYEE",
        [
            Column("EmployeeID", int),
            Column("Name", str),
            Column("Department", str),
            Column("Salary", float),
        ],
        rows=[
            {
                "EmployeeID": 1,
                "Name": "Asha",
                "Department": "IT",
                "Salary": 80000.0,
            },
            {
                "EmployeeID": 2,
                "Name": "Ravi",
                "Department": "HR",
                "Salary": 65000.0,
            },
            {
                "EmployeeID": 3,
                "Name": "Meera",
                "Department": "IT",
                "Salary": 95000.0,
            },
        ],
    )

    departments = projection(
        employees,
        ["Department"],
        "EMPLOYEE_DEPARTMENTS",
    )

    employees.print_table("EMPLOYEE")
    departments.print_table(
        "Projection: π Department (EMPLOYEE)"
    )

    print(
        "\nProjection differs from selection:"
        "\n  Selection removes tuples."
        "\n  Projection removes attributes and duplicate resulting tuples."
    )


# ============================================================================
# 8. SET OPERATIONS
# ============================================================================

def _compatible_for_set_operation(
    left: Relation,
    right: Relation,
) -> None:
    if left.degree != right.degree:
        raise SchemaError(
            "Set operations require union-compatible degree."
        )

    left_types = tuple(column.domain for column in left.columns)
    right_types = tuple(column.domain for column in right.columns)

    if left_types != right_types:
        raise SchemaError(
            "Set operations require corresponding attribute domains "
            "to be compatible."
        )


def union(left: Relation, right: Relation, name: str = "UNION") -> Relation:
    """Relational union."""

    _compatible_for_set_operation(left, right)

    return Relation(
        name,
        left.columns,
        rows=left.rows() + right.rows(),
    )


def intersection(
    left: Relation,
    right: Relation,
    name: str = "INTERSECTION",
) -> Relation:
    """Relational intersection."""

    _compatible_for_set_operation(left, right)

    right_tuples = {
        tuple(row[column.name] for column in right.columns)
        for row in right.rows()
    }

    rows = []

    for row in left.rows():
        values = tuple(row[column.name] for column in left.columns)
        if values in right_tuples:
            rows.append(row)

    return Relation(name, left.columns, rows)


def difference(
    left: Relation,
    right: Relation,
    name: str = "DIFFERENCE",
) -> Relation:
    """Relational difference: left minus right."""

    _compatible_for_set_operation(left, right)

    right_tuples = {
        tuple(row[column.name] for column in right.columns)
        for row in right.rows()
    }

    rows = []

    for row in left.rows():
        values = tuple(row[column.name] for column in left.columns)

        if values not in right_tuples:
            rows.append(row)

    return Relation(name, left.columns, rows)


def section_07_set_operations() -> None:
    print("\n" + "=" * 78)
    print("7. RELATIONAL ALGEBRA: UNION, INTERSECTION, DIFFERENCE")
    print("=" * 78)

    columns = [
        Column("StudentID", int),
        Column("Name", str),
    ]

    morning = Relation(
        "MORNING",
        columns,
        rows=[
            {"StudentID": 1, "Name": "Asha"},
            {"StudentID": 2, "Name": "Ravi"},
            {"StudentID": 3, "Name": "Meera"},
        ],
    )

    evening = Relation(
        "EVENING",
        columns,
        rows=[
            {"StudentID": 3, "Name": "Meera"},
            {"StudentID": 4, "Name": "Kabir"},
        ],
    )

    union(morning, evening).print_table(
        "Union: MORNING ∪ EVENING"
    )

    intersection(morning, evening).print_table(
        "Intersection: MORNING ∩ EVENING"
    )

    difference(morning, evening).print_table(
        "Difference: MORNING − EVENING"
    )


# ============================================================================
# 9. CARTESIAN PRODUCT
# ============================================================================

def cartesian_product(
    left: Relation,
    right: Relation,
    name: str = "CARTESIAN_PRODUCT",
) -> Relation:
    """
    Cartesian product.

    Every tuple from left is paired with every tuple from right.

    Attribute names must be unique in this educational implementation.
    Real database systems often qualify attributes using relation names.
    """

    left_names = set(left._attribute_names())
    right_names = set(right._attribute_names())

    if left_names & right_names:
        raise SchemaError(
            "Cartesian product requires distinct attribute names in this "
            "implementation."
        )

    columns = list(left.columns) + list(right.columns)
    rows = []

    for left_row, right_row in product(
        left.rows(),
        right.rows(),
    ):
        rows.append({**left_row, **right_row})

    return Relation(name, columns, rows)


def section_08_cartesian_product() -> None:
    print("\n" + "=" * 78)
    print("8. CARTESIAN PRODUCT")
    print("=" * 78)

    students = Relation(
        "STUDENT",
        [
            Column("StudentID", int),
            Column("StudentName", str),
        ],
        rows=[
            {"StudentID": 1, "StudentName": "Asha"},
            {"StudentID": 2, "StudentName": "Ravi"},
        ],
    )

    courses = Relation(
        "COURSE",
        [
            Column("CourseID", int),
            Column("CourseName", str),
        ],
        rows=[
            {"CourseID": 10, "CourseName": "DBMS"},
            {"CourseID": 20, "CourseName": "Networks"},
        ],
    )

    result = cartesian_product(students, courses)

    students.print_table("STUDENT")
    courses.print_table("COURSE")
    result.print_table("STUDENT × COURSE")

    print(
        "\nIf R has m tuples and S has n tuples, "
        "R × S has m × n tuples."
    )


# ============================================================================
# 10. RENAMING
# ============================================================================

def rename(
    relation: Relation,
    attribute_mapping: Dict[str, str],
    name: Optional[str] = None,
) -> Relation:
    """Relational algebra rename operation."""

    old_names = set(relation._attribute_names())

    if not set(attribute_mapping).issubset(old_names):
        raise SchemaError("Rename references an unknown attribute.")

    new_names = [
        attribute_mapping.get(column.name, column.name)
        for column in relation.columns
    ]

    if len(new_names) != len(set(new_names)):
        raise SchemaError("Renaming created duplicate attribute names.")

    new_columns = [
        Column(
            new_name,
            column.domain,
            column.nullable,
        )
        for column, new_name in zip(relation.columns, new_names)
    ]

    rows = []

    for row in relation.rows():
        rows.append(
            {
                attribute_mapping.get(key, key): value
                for key, value in row.items()
            }
        )

    return Relation(
        name or f"RENAME_{relation.name}",
        new_columns,
        rows,
    )


def section_09_rename() -> None:
    print("\n" + "=" * 78)
    print("9. RELATIONAL ALGEBRA: RENAME")
    print("=" * 78)

    people = Relation(
        "PEOPLE",
        [
            Column("ID", int),
            Column("Name", str),
        ],
        rows=[
            {"ID": 1, "Name": "Asha"},
            {"ID": 2, "Name": "Ravi"},
        ],
    )

    renamed = rename(
        people,
        {"ID": "PersonID"},
        "RENAMED_PEOPLE",
    )

    people.print_table("Original")
    renamed.print_table("After renaming ID → PersonID")


# ============================================================================
# 11. JOINS
# ============================================================================

def inner_join(
    left: Relation,
    right: Relation,
    left_on: Sequence[str],
    right_on: Sequence[str],
    name: str = "INNER_JOIN",
) -> Relation:
    """
    Equijoin implementation.

    Matching rows are combined when the corresponding join attributes are
    equal.

    This uses a hash-based implementation rather than comparing every pair,
    demonstrating an important query-processing optimization.
    """

    if len(left_on) != len(right_on):
        raise SchemaError("Join key lengths must match.")

    left_names = set(left._attribute_names())
    right_names = set(right._attribute_names())

    if not set(left_on).issubset(left_names):
        raise SchemaError("Unknown left join attribute.")

    if not set(right_on).issubset(right_names):
        raise SchemaError("Unknown right join attribute.")

    # Prefix overlapping names to prevent ambiguous attributes.
    output_columns: List[Column] = []

    for column in left.columns:
        output_columns.append(
            Column(
                column.name,
                column.domain,
                column.nullable,
            )
        )

    for column in right.columns:
        output_name = (
            column.name
            if column.name not in left_names
            else f"{right.name}.{column.name}"
        )

        output_columns.append(
            Column(
                output_name,
                column.domain,
                column.nullable,
            )
        )

    hash_table: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}

    for row in right.rows():
        key = tuple(row[column] for column in right_on)
        hash_table.setdefault(key, []).append(row)

    result_rows = []

    for left_row in left.rows():
        key = tuple(left_row[column] for column in left_on)

        for right_row in hash_table.get(key, []):
            combined = dict(left_row)

            for column_name, value in right_row.items():
                output_name = (
                    column_name
                    if column_name not in left_names
                    else f"{right.name}.{column_name}"
                )
                combined[output_name] = value

            result_rows.append(combined)

    return Relation(name, output_columns, result_rows)


def left_outer_join(
    left: Relation,
    right: Relation,
    left_on: Sequence[str],
    right_on: Sequence[str],
    name: str = "LEFT_OUTER_JOIN",
) -> Relation:
    """Left outer join using the same hash-based matching principle."""

    if len(left_on) != len(right_on):
        raise SchemaError("Join key lengths must match.")

    left_names = set(left._attribute_names())
    right_names = set(right._attribute_names())

    output_columns = list(left.columns)

    for column in right.columns:
        output_name = (
            column.name
            if column.name not in left_names
            else f"{right.name}.{column.name}"
        )

        output_columns.append(
            Column(output_name, column.domain, True)
        )

    hash_table: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}

    for row in right.rows():
        key = tuple(row[column] for column in right_on)
        hash_table.setdefault(key, []).append(row)

    rows = []

    for left_row in left.rows():
        key = tuple(left_row[column] for column in left_on)
        matches = hash_table.get(key, [])

        if matches:
            for right_row in matches:
                combined = dict(left_row)

                for column_name, value in right_row.items():
                    output_name = (
                        column_name
                        if column_name not in left_names
                        else f"{right.name}.{column_name}"
                    )
                    combined[output_name] = value

                rows.append(combined)
        else:
            combined = dict(left_row)

            for column in right.columns:
                output_name = (
                    column.name
                    if column.name not in left_names
                    else f"{right.name}.{column.name}"
                )
                combined[output_name] = None

            rows.append(combined)

    return Relation(name, output_columns, rows)


def section_10_joins() -> None:
    print("\n" + "=" * 78)
    print("10. RELATIONAL JOINS")
    print("=" * 78)

    departments = Relation(
        "DEPARTMENT",
        [
            Column("DepartmentID", int),
            Column("DepartmentName", str),
        ],
        rows=[
            {"DepartmentID": 10, "DepartmentName": "CSE"},
            {"DepartmentID": 20, "DepartmentName": "ECE"},
            {"DepartmentID": 30, "DepartmentName": "MBA"},
        ],
    )

    employees = Relation(
        "EMPLOYEE",
        [
            Column("EmployeeID", int),
            Column("Name", str),
            Column("DepartmentID", int),
        ],
        rows=[
            {"EmployeeID": 1, "Name": "Asha", "DepartmentID": 10},
            {"EmployeeID": 2, "Name": "Ravi", "DepartmentID": 20},
            {"EmployeeID": 3, "Name": "Meera", "DepartmentID": 10},
        ],
    )

    inner = inner_join(
        employees,
        departments,
        ["DepartmentID"],
        ["DepartmentID"],
        "EMPLOYEE_DEPARTMENT",
    )

    inner.print_table("Inner join")

    outer = left_outer_join(
        employees,
        departments,
        ["DepartmentID"],
        ["DepartmentID"],
        "LEFT_EMPLOYEE_DEPARTMENT",
    )

    outer.print_table("Left outer join")

    print(
        "\nJoin concepts:"
        "\n  Inner join -> only matching tuples."
        "\n  Left outer join -> all left tuples plus matching right tuples."
        "\n  Right outer join -> symmetric concept preserving the right side."
        "\n  Full outer join -> preserves unmatched tuples from both sides."
        "\n  Equijoin -> join condition uses equality."
        "\n  Natural join -> conceptually joins same-named compatible "
        "attributes and avoids duplicate join columns."
        "\n  Theta join -> join condition may use =, <, >, <=, >=, or !=."
    )


# ============================================================================
# 12. THETA JOIN
# ============================================================================

def theta_join(
    left: Relation,
    right: Relation,
    predicate: Callable[
        [Dict[str, Any], Dict[str, Any]], bool
    ],
    name: str = "THETA_JOIN",
) -> Relation:
    """
    General theta join.

    This implementation uses nested loops because arbitrary predicates cannot
    generally be converted into a simple hash lookup.
    """

    left_names = set(left._attribute_names())

    columns = list(left.columns)

    for column in right.columns:
        output_name = (
            column.name
            if column.name not in left_names
            else f"{right.name}.{column.name}"
        )

        columns.append(
            Column(
                output_name,
                column.domain,
                column.nullable,
            )
        )

    rows = []

    for left_row in left.rows():
        for right_row in right.rows():
            if predicate(left_row, right_row):
                combined = dict(left_row)

                for key, value in right_row.items():
                    output_name = (
                        key
                        if key not in left_names
                        else f"{right.name}.{key}"
                    )
                    combined[output_name] = value

                rows.append(combined)

    return Relation(name, columns, rows)


def section_11_theta_join() -> None:
    print("\n" + "=" * 78)
    print("11. THETA JOIN")
    print("=" * 78)

    employees = Relation(
        "EMPLOYEE",
        [
            Column("EmployeeID", int),
            Column("Name", str),
            Column("Salary", float),
        ],
        rows=[
            {"EmployeeID": 1, "Name": "Asha", "Salary": 80000.0},
            {"EmployeeID": 2, "Name": "Ravi", "Salary": 60000.0},
        ],
    )

    bands = Relation(
        "BAND",
        [
            Column("BandID", int),
            Column("MinimumSalary", float),
        ],
        rows=[
            {"BandID": 1, "MinimumSalary": 50000.0},
            {"BandID": 2, "MinimumSalary": 70000.0},
        ],
    )

    result = theta_join(
        employees,
        bands,
        lambda employee, band:
            employee["Salary"] >= band["MinimumSalary"],
    )

    result.print_table(
        "Theta join: Employee.Salary >= Band.MinimumSalary"
    )


# ============================================================================
# 13. DIVISION
# ============================================================================

def division(
    dividend: Relation,
    divisor: Relation,
    name: str = "DIVISION",
) -> Relation:
    """
    Relational division.

    Conceptual use:

        Find X values related to every Y value.

    Example:
        ENROLLMENT(Student, Course)
        REQUIRED(Course)

    Division can answer:
        "Which students completed every required course?"

    The divisor attributes must be contained in the dividend attributes.
    """

    dividend_names = dividend._attribute_names()
    divisor_names = divisor._attribute_names()

    if not set(divisor_names).issubset(dividend_names):
        raise SchemaError(
            "Divisor attributes must be contained in dividend attributes."
        )

    quotient_names = [
        attribute
        for attribute in dividend_names
        if attribute not in divisor_names
    ]

    quotient_columns = [
        column
        for column in dividend.columns
        if column.name in quotient_names
    ]

    quotient_candidates = projection(
        dividend,
        quotient_names,
        "DIVISION_CANDIDATES",
    )

    result_rows = []

    for candidate in quotient_candidates.rows():
        qualifies = True

        for divisor_row in divisor.rows():
            matching = False

            for dividend_row in dividend.rows():
                candidate_matches = all(
                    dividend_row[attribute] == candidate[attribute]
                    for attribute in quotient_names
                )

                divisor_matches = all(
                    dividend_row[attribute] == divisor_row[attribute]
                    for attribute in divisor_names
                )

                if candidate_matches and divisor_matches:
                    matching = True
                    break

            if not matching:
                qualifies = False
                break

        if qualifies:
            result_rows.append(candidate)

    return Relation(name, quotient_columns, result_rows)


def section_12_division() -> None:
    print("\n" + "=" * 78)
    print("12. RELATIONAL DIVISION")
    print("=" * 78)

    enrollment = Relation(
        "ENROLLMENT",
        [
            Column("StudentID", int),
            Column("CourseID", int),
        ],
        rows=[
            {"StudentID": 1, "CourseID": 101},
            {"StudentID": 1, "CourseID": 102},
            {"StudentID": 1, "CourseID": 103},
            {"StudentID": 2, "CourseID": 101},
            {"StudentID": 2, "CourseID": 102},
            {"StudentID": 3, "CourseID": 101},
        ],
    )

    required = Relation(
        "REQUIRED",
        [
            Column("CourseID", int),
        ],
        rows=[
            {"CourseID": 101},
            {"CourseID": 102},
        ],
    )

    enrollment.print_table("ENROLLMENT")
    required.print_table("REQUIRED")

    result = division(enrollment, required)

    result.print_table(
        "Students enrolled in every required course"
    )


# ============================================================================
# 14. SQL CONCEPTS VERSUS RELATIONAL ALGEBRA
# ============================================================================

def section_13_sql_mapping() -> None:
    print("\n" + "=" * 78)
    print("13. RELATIONAL ALGEBRA AND SQL CONCEPTUAL MAPPING")
    print("=" * 78)

    print(
        """
Relational algebra                 Typical SQL expression
---------------------------------------------------------------------------
Selection σ                         WHERE
Projection π                       SELECT column_list
Union ∪                             UNION
Intersection ∩                     INTERSECT
Difference −                       EXCEPT
Cartesian product ×               CROSS JOIN
Join                                JOIN ... ON ...
Rename ρ                            AS
Grouping/aggregation               GROUP BY / aggregate functions

Example:

Relational algebra:
    π Name ( σ Department = 'IT' (EMPLOYEE) )

Conceptual SQL:
    SELECT Name
    FROM EMPLOYEE
    WHERE Department = 'IT';

Relational algebra describes operations formally.
SQL is a practical declarative language that includes relational operations
plus features such as ordering, grouping, aggregation, NULL semantics,
transactions, recursive queries, window functions, and implementation
specific extensions.
"""
    )


# ============================================================================
# 15. NULL AND THREE-VALUED LOGIC
# ============================================================================

def sql_equals(left: Any, right: Any) -> Optional[bool]:
    """
    Simplified SQL-style equality.

    In SQL:
        NULL = value      -> UNKNOWN
        NULL = NULL       -> UNKNOWN

    Python's None == None is True, so ordinary Python equality is not
    equivalent to SQL NULL semantics.
    """

    if left is None or right is None:
        return None

    return left == right


def sql_and(
    left: Optional[bool],
    right: Optional[bool],
) -> Optional[bool]:
    """Three-valued SQL AND."""

    if left is False or right is False:
        return False

    if left is None or right is None:
        return None

    return True


def sql_or(
    left: Optional[bool],
    right: Optional[bool],
) -> Optional[bool]:
    """Three-valued SQL OR."""

    if left is True or right is True:
        return True

    if left is None or right is None:
        return None

    return False


def sql_not(value: Optional[bool]) -> Optional[bool]:
    """Three-valued SQL NOT."""

    if value is None:
        return None

    return not value


def section_14_null_logic() -> None:
    print("\n" + "=" * 78)
    print("14. NULL AND THREE-VALUED LOGIC")
    print("=" * 78)

    print("SQL-style NULL comparison:")
    print("NULL = 10 ->", sql_equals(None, 10))
    print("NULL = NULL ->", sql_equals(None, None))
    print("10 = 10 ->", sql_equals(10, 10))

    print("\nThree-valued AND:")
    print("TRUE AND UNKNOWN ->", sql_and(True, None))
    print("FALSE AND UNKNOWN ->", sql_and(False, None))

    print("\nThree-valued OR:")
    print("TRUE OR UNKNOWN ->", sql_or(True, None))
    print("FALSE OR UNKNOWN ->", sql_or(False, None))

    print("\nThree-valued NOT:")
    print("NOT UNKNOWN ->", sql_not(None))

    print(
        """
Important distinction:

NULL does not mean zero.
NULL does not mean an empty string.
NULL does not mean false.
NULL represents missing, unknown, or inapplicable information depending
on context.

In SQL filtering, a WHERE condition generally retains rows only when the
condition evaluates to TRUE. FALSE and UNKNOWN are not retained.
"""
    )


# ============================================================================
# 16. INTEGRITY CONSTRAINTS
# ============================================================================

def section_15_integrity_constraints() -> None:
    print("\n" + "=" * 78)
    print("15. INTEGRITY CONSTRAINTS")
    print("=" * 78)

    print(
        """
Major relational integrity concepts:

1. Domain integrity
   Values must belong to permitted domains.

2. Entity integrity
   A primary-key value must identify a tuple and cannot be NULL.

3. Referential integrity
   A foreign-key value must correspond to a referenced key, subject to
   the DBMS's NULL and constraint semantics.

4. Key constraints
   Candidate-key values must be unique.

5. General assertions/check constraints
   Business predicates can restrict legal states.

Example business rule:
    Salary >= 0

The important design principle is to enforce invariants as close to the
data boundary as practical. Application-only validation can be bypassed
when multiple applications, scripts, integrations, or administrative tools
write to the same database.
"""
    )


# ============================================================================
# 17. ENTITY-RELATIONSHIP TO RELATIONAL MODEL
# ============================================================================

def section_16_er_mapping() -> None:
    print("\n" + "=" * 78)
    print("16. MAPPING CONCEPTUAL ENTITIES TO RELATIONS")
    print("=" * 78)

    print(
        """
A conceptual design may contain:

    STUDENT
    COURSE
    STUDENT enrolls in COURSE

A many-to-many relationship normally becomes an associative relation:

    STUDENT(StudentID, Name)
    COURSE(CourseID, Title)
    ENROLLMENT(StudentID, CourseID, EnrollmentDate)

ENROLLMENT has foreign keys:

    ENROLLMENT.StudentID -> STUDENT.StudentID
    ENROLLMENT.CourseID  -> COURSE.CourseID

A common primary key is:

    (StudentID, CourseID)

This is a composite key because one student's enrollment in one course is
identified by the combination of the two attributes.
"""
    )

    student = Relation(
        "STUDENT",
        [
            Column("StudentID", int),
            Column("Name", str),
        ],
        primary_key=("StudentID",),
        rows=[
            {"StudentID": 1, "Name": "Asha"},
            {"StudentID": 2, "Name": "Ravi"},
        ],
    )

    course = Relation(
        "COURSE",
        [
            Column("CourseID", int),
            Column("Title", str),
        ],
        primary_key=("CourseID",),
        rows=[
            {"CourseID": 101, "Title": "DBMS"},
            {"CourseID": 102, "Title": "Networks"},
        ],
    )

    enrollment = Relation(
        "ENROLLMENT",
        [
            Column("StudentID", int),
            Column("CourseID", int),
            Column("EnrollmentDate", str),
        ],
        primary_key=("StudentID", "CourseID"),
        foreign_keys=[
            (
                ("StudentID",),
                student,
                ("StudentID",),
            ),
            (
                ("CourseID",),
                course,
                ("CourseID",),
            ),
        ],
        rows=[
            {
                "StudentID": 1,
                "CourseID": 101,
                "EnrollmentDate": "2026-08-01",
            },
            {
                "StudentID": 1,
                "CourseID": 102,
                "EnrollmentDate": "2026-08-02",
            },
        ],
    )

    student.print_table("STUDENT")
    course.print_table("COURSE")
    enrollment.print_table("ENROLLMENT")


# ============================================================================
# 18. FUNCTIONAL DEPENDENCIES
# ============================================================================

def section_17_functional_dependencies() -> None:
    print("\n" + "=" * 78)
    print("17. FUNCTIONAL DEPENDENCIES")
    print("=" * 78)

    print(
        """
A functional dependency is written:

    X -> Y

It means that for any two tuples in a relation, if their X values are the
same, their Y values must also be the same.

Example:

    StudentID -> StudentName, Department

This means StudentID determines StudentName and Department.

A functional dependency is a statement about the semantics of the data,
not simply an accidental pattern observed in a current dataset.

Important terms:

    Determinant
        The left side X.

    Dependent
        The right side Y.

    Trivial dependency
        Y is a subset of X.

    Non-trivial dependency
        Y is not a subset of X.

    Full functional dependency
        Y depends on the whole determinant, not merely a proper subset.

    Partial dependency
        A non-key attribute depends on only part of a composite key.

    Transitive dependency
        X -> Y and Y -> Z can produce an indirect dependency X -> Z.
"""
    )


# ============================================================================
# 19. NORMALIZATION
# ============================================================================

def section_18_normalization() -> None:
    print("\n" + "=" * 78)
    print("18. NORMALIZATION: 1NF, 2NF, 3NF, BCNF")
    print("=" * 78)

    print(
        """
Normalization organizes relations to reduce undesirable redundancy and
update anomalies.

UNNORMALIZED example:

    ORDER(
        OrderID,
        CustomerName,
        Product1,
        Product2,
        Product3
    )

Repeating groups violate the usual first-normal-form design principle.

FIRST NORMAL FORM (1NF)
-----------------------
Attributes contain atomic values according to the chosen relational model.
Repeating groups are represented as separate tuples rather than repeated
columns such as Product1, Product2, Product3.

SECOND NORMAL FORM (2NF)
------------------------
A relation is in 2NF when it is in 1NF and every non-prime attribute is fully
functionally dependent on every candidate key.

2NF is mainly relevant when candidate keys are composite.

Example:

    ENROLLMENT(StudentID, CourseID, StudentName, CourseName, Grade)

Candidate key:
    (StudentID, CourseID)

Dependencies:
    StudentID -> StudentName
    CourseID  -> CourseName
    (StudentID, CourseID) -> Grade

StudentName and CourseName depend on only part of the composite key, producing
partial dependencies.

A decomposition can be:

    STUDENT(StudentID, StudentName)
    COURSE(CourseID, CourseName)
    ENROLLMENT(StudentID, CourseID, Grade)

THIRD NORMAL FORM (3NF)
-----------------------
A common formal characterization is:

For every non-trivial FD X -> A, either:
    X is a superkey
or:
    A is a prime attribute.

The intuitive goal is to eliminate problematic transitive dependencies among
non-key attributes.

BOYCE-CODD NORMAL FORM (BCNF)
-----------------------------
For every non-trivial functional dependency X -> Y, X must be a superkey.

BCNF is stricter than 3NF.

Normalization is not a purely mechanical process. It depends on functional
dependencies, candidate keys, lossless decomposition, dependency preservation,
and business semantics.
"""
    )


# ============================================================================
# 20. LOSSLESS AND DEPENDENCY-PRESERVING DECOMPOSITION
# ============================================================================

def section_19_decomposition() -> None:
    print("\n" + "=" * 78)
    print("19. LOSSLESS JOIN AND DEPENDENCY PRESERVATION")
    print("=" * 78)

    print(
        """
A decomposition of relation R into R1, R2, ... is lossless if joining the
decomposed relations reconstructs exactly the information represented by R,
without generating spurious tuples.

A decomposition is dependency-preserving if the relevant functional
dependencies can be enforced using the decomposed relations without requiring
a join merely to check them.

These properties are separate:

    Lossless
        Prevents information loss or spurious reconstruction.

    Dependency preserving
        Makes integrity rules easier to enforce locally.

A decomposition can be lossless without preserving every dependency.

In database design, a sound normalization process must consider both rather
than simply splitting tables until they look small.
"""
    )


# ============================================================================
# 21. DENORMALIZATION
# ============================================================================

def section_20_denormalization() -> None:
    print("\n" + "=" * 78)
    print("20. DENORMALIZATION AND TRADE-OFFS")
    print("=" * 78)

    print(
        """
Normalization benefits:

    - Reduces unnecessary duplication.
    - Reduces insertion anomalies.
    - Reduces update anomalies.
    - Reduces deletion anomalies.
    - Clarifies dependencies and integrity rules.

Denormalization may intentionally duplicate derived or frequently accessed
data to improve read performance or simplify certain workloads.

Costs of denormalization:

    - More storage.
    - More complicated writes.
    - Risk of inconsistent copies.
    - More complicated synchronization.
    - Harder integrity enforcement.

A useful design principle is:

    Normalize for correctness and clear dependencies first.
    Denormalize deliberately when workload evidence justifies it.

Denormalization is an implementation choice, not a replacement for
understanding the relational design.
"""
    )


# ============================================================================
# 22. RELATIONAL COMPLETENESS
# ============================================================================

def section_21_relational_completeness() -> None:
    print("\n" + "=" * 78)
    print("21. RELATIONAL ALGEBRA AND EXPRESSIVE POWER")
    print("=" * 78)

    print(
        """
The classical relational algebra contains operators such as:

    Selection
    Projection
    Union
    Difference
    Cartesian product
    Rename

Joins can be expressed using combinations of Cartesian product and selection,
although direct join operators are much more convenient.

Relationally complete query languages can express the queries expressible by
the core relational algebra, subject to the precise formal definition being
used.

Modern SQL is not identical to pure relational algebra because SQL includes:

    - Duplicate-preserving behavior in many operations.
    - NULL and three-valued logic.
    - Aggregation.
    - Ordering.
    - Recursive queries.
    - Window functions.
    - Data-definition features.
    - Transaction and procedural features.

The relational model is therefore best viewed as the conceptual and formal
foundation rather than as a complete description of every feature of modern
SQL systems.
"""
    )


# ============================================================================
# 23. RELATIONAL MODEL VERSUS SQL TABLES
# ============================================================================

def section_22_relational_vs_sql() -> None:
    print("\n" + "=" * 78)
    print("22. RELATIONAL MODEL VERSUS SQL TABLE SEMANTICS")
    print("=" * 78)

    print(
        """
Relational theory:

    - A relation is a set of tuples.
    - Duplicate tuples do not exist.
    - Tuple ordering is irrelevant.
    - Attribute ordering is conceptually less important than attribute names.
    - NULL is not fundamental to classical relational algebra.

SQL in practice:

    - SELECT results can contain duplicates unless DISTINCT is used.
    - ORDER BY explicitly requests presentation order.
    - NULL introduces UNKNOWN.
    - Bag/multiset semantics appear in many operations.
    - SQL adds aggregation, windows, recursion, and procedural capabilities.

Example:

    SELECT Department
    FROM Employee;

may return:

    IT
    IT
    HR

while:

    SELECT DISTINCT Department
    FROM Employee;

returns each distinct department once.

This distinction is important when translating between mathematical relational
reasoning and actual SQL behavior.
"""
    )


# ============================================================================
# 24. QUERY PROCESSING
# ============================================================================

def section_23_query_processing() -> None:
    print("\n" + "=" * 78)
    print("23. QUERY PROCESSING AND OPTIMIZATION")
    print("=" * 78)

    print(
        """
A DBMS does not normally execute a declarative query by blindly performing
operations in the textual order written by the user.

A simplified pipeline is:

    SQL text
        ↓
    Parsing
        ↓
    Validation / semantic analysis
        ↓
    Logical query representation
        ↓
    Query rewriting
        ↓
    Cost-based optimization
        ↓
    Physical execution plan
        ↓
    Storage and operator execution

Important optimization ideas:

1. Selection pushdown
   Apply filters as early as possible to reduce intermediate relation size.

2. Projection pushdown
   Carry only required attributes when safe.

3. Join ordering
   Choose an efficient sequence of joins.

4. Index usage
   Use suitable indexes to reduce data access.

5. Hash join
   Efficient for many equality joins.

6. Sort-merge join
   Useful when inputs are sorted or sorting is otherwise beneficial.

7. Nested-loop join
   Flexible and sometimes efficient when one input is small or indexed.

8. Cardinality estimation
   Estimate intermediate result sizes.

9. Cost estimation
   Compare possible execution plans.

The logical relational expression describes what is required.
The physical plan describes how the DBMS will produce it.
"""
    )


# ============================================================================
# 25. HASH JOIN VERSUS NESTED LOOP JOIN
# ============================================================================

def section_24_join_performance() -> None:
    print("\n" + "=" * 78)
    print("24. JOIN PERFORMANCE COMPARISON")
    print("=" * 78)

    print(
        """
Nested-loop join:

    For each left tuple:
        compare against right tuples

Approximate simple comparison work:
    O(|R| × |S|)

Hash join for equality predicates:

    Build hash table for one input:
        O(|S|)

    Probe for each tuple of the other input:
        O(|R|) expected

Expected work:
    O(|R| + |S|)

The real cost depends on:

    - Available memory.
    - Data distribution.
    - Hash collisions.
    - Disk I/O.
    - Indexes.
    - Sorting requirements.
    - Parallelism.
    - Cardinality estimates.
    - Join selectivity.

A hash join cannot directly replace every theta join because arbitrary
predicates may not have a hashable equality structure.
"""
    )


# ============================================================================
# 26. INDEXES AND THE RELATIONAL MODEL
# ============================================================================

def section_25_indexes() -> None:
    print("\n" + "=" * 78)
    print("25. INDEXES: LOGICAL MODEL VERSUS PHYSICAL IMPLEMENTATION")
    print("=" * 78)

    print(
        """
Indexes are physical access structures rather than relational-model
attributes in the mathematical sense.

Common index structures include:

    B-tree / B+ tree
        Good general-purpose structure supporting equality and range access.

    Hash index
        Strong for equality lookups, generally unsuitable for ordered range
        traversal.

Indexes can accelerate:

    WHERE predicates
    JOIN conditions
    ORDER BY
    GROUP BY
    uniqueness enforcement

Indexes also have costs:

    - Additional storage.
    - Insert overhead.
    - Update overhead.
    - Delete overhead.
    - Maintenance work.
    - Potentially poor usefulness when selectivity is low.

A relational schema should not be confused with its indexes. Two physical
implementations can provide the same logical relation while using different
access structures.
"""
    )


# ============================================================================
# 27. TRANSACTIONS AND RELATIONAL STATE
# ============================================================================

def section_26_transactions() -> None:
    print("\n" + "=" * 78)
    print("26. TRANSACTIONS AND CONSISTENT RELATIONAL STATE")
    print("=" * 78)

    print(
        """
A transaction groups database operations into a logical unit.

ACID properties:

    Atomicity
        A transaction's operations are treated as one unit.

    Consistency
        A successful transaction preserves defined integrity constraints.

    Isolation
        Concurrent transactions should not interfere in ways prohibited by
        the chosen isolation semantics.

    Durability
        Committed changes survive failures according to the DBMS guarantees.

Typical state transition:

    Valid state
        ↓
    Transaction executes
        ↓
    Intermediate state
        ↓
    Commit
        ↓
    Valid persistent state

If a transaction fails, rollback attempts to restore the previous consistent
state.

The relational model specifies logical data structures and integrity.
Transaction systems provide the mechanisms needed to safely transition
between database states.
"""
    )


# ============================================================================
# 28. CONCURRENCY ANOMALIES
# ============================================================================

def section_27_concurrency() -> None:
    print("\n" + "=" * 78)
    print("27. CONCURRENCY ANOMALIES")
    print("=" * 78)

    print(
        """
When transactions execute concurrently, insufficient isolation can produce
anomalies.

Dirty read:
    Transaction A reads uncommitted data written by transaction B.

Non-repeatable read:
    Transaction A reads a row, transaction B changes it and commits, and
    transaction A reads it again and gets a different value.

Phantom:
    Transaction A repeats a predicate query and observes additional or
    missing qualifying rows because transaction B inserted or removed rows.

Lost update:
    Concurrent writes overwrite one another without proper coordination.

Isolation levels provide different guarantees and performance characteristics.
Exact behavior is DBMS-specific and should be understood before relying on
a particular concurrency assumption.
"""
    )


# ============================================================================
# 29. SECURITY
# ============================================================================

def section_28_security() -> None:
    print("\n" + "=" * 78)
    print("28. SECURITY CONSIDERATIONS")
    print("=" * 78)

    print(
        """
Relational-model security in production includes:

1. Authentication
   Establish who is connecting.

2. Authorization
   Control which users or roles may SELECT, INSERT, UPDATE, DELETE, or
   administer objects.

3. Least privilege
   Give each account only the permissions it actually requires.

4. Parameterized queries
   Prevent user input from becoming executable SQL syntax.

5. Encryption
   Protect data in transit and, where appropriate, at rest.

6. Auditing
   Record important access and modification events.

7. Row-level or column-level controls
   Restrict visibility where supported and appropriate.

8. Constraint enforcement
   Prevent invalid states from being introduced through alternate access
   paths.

A secure relational application cannot depend exclusively on client-side
validation. The database and application layers should enforce appropriate
security boundaries independently.
"""
    )


# ============================================================================
# 30. SQL INJECTION DEMONSTRATION
# ============================================================================

def demonstrate_sql_injection_concept() -> None:
    print("\n" + "=" * 78)
    print("29. SQL INJECTION: UNSAFE VERSUS PARAMETERIZED THINKING")
    print("=" * 78)

    username = "alice"

    unsafe_query = (
        "SELECT * FROM users WHERE username = '"
        + username
        + "';"
    )

    print("Unsafe string construction:")
    print(unsafe_query)

    malicious_input = "' OR '1'='1"

    unsafe_malicious_query = (
        "SELECT * FROM users WHERE username = '"
        + malicious_input
        + "';"
    )

    print("\nMalicious input changes SQL structure:")
    print(unsafe_malicious_query)

    print(
        """
The secure principle is to keep SQL code separate from data.

Conceptually:

    cursor.execute(
        "SELECT * FROM users WHERE username = %s",
        (username,)
    )

The exact placeholder syntax varies by database driver.

Parameterization causes the database driver to treat the supplied value as
data rather than as part of the SQL program.
"""
    )


# ============================================================================
# 31. DATA ANOMALIES
# ============================================================================

def section_30_anomalies() -> None:
    print("\n" + "=" * 78)
    print("30. INSERTION, UPDATE, AND DELETION ANOMALIES")
    print("=" * 78)

    print(
        """
Consider:

    COURSE_OFFERING(
        CourseID,
        CourseName,
        InstructorID,
        InstructorName
    )

If InstructorName is repeated across many rows:

UPDATE ANOMALY
    An instructor's name must be changed in multiple tuples.

INSERTION ANOMALY
    It may be impossible to store a new instructor cleanly until an
    associated course offering exists.

DELETION ANOMALY
    Deleting the final course offering taught by an instructor might
    accidentally remove the only stored record of that instructor.

Normalization separates independently determined facts into relations that
reflect their dependencies.

For example:

    INSTRUCTOR(InstructorID, InstructorName)
    COURSE(CourseID, CourseName, InstructorID)

This reduces redundancy and makes integrity relationships explicit.
"""
    )


# ============================================================================
# 32. CANDIDATE KEY DISCOVERY EXAMPLE
# ============================================================================

def is_superkey(
    rows: Sequence[Dict[str, Any]],
    attributes: Sequence[str],
) -> bool:
    """Check whether attributes uniquely identify all tuples."""

    seen = set()

    for row in rows:
        key = tuple(row[attribute] for attribute in attributes)

        if key in seen:
            return False

        seen.add(key)

    return True


def minimal_superkey(
    rows: Sequence[Dict[str, Any]],
    attributes: Sequence[str],
) -> bool:
    """Check whether a superkey is minimal."""

    if not is_superkey(rows, attributes):
        return False

    if len(attributes) == 1:
        return True

    for index in range(len(attributes)):
        reduced = (
            list(attributes[:index])
            + list(attributes[index + 1:])
        )

        if is_superkey(rows, reduced):
            return False

    return True


def discover_candidate_keys(
    rows: Sequence[Dict[str, Any]],
    attributes: Sequence[str],
) -> List[Tuple[str, ...]]:
    """
    Brute-force candidate-key discovery.

    This is educational rather than production-grade. Candidate-key discovery
    can become combinatorially expensive as the number of attributes grows.
    """

    candidates: List[Tuple[str, ...]] = []

    for size in range(1, len(attributes) + 1):
        for combination in _combinations(attributes, size):
            if minimal_superkey(rows, combination):
                candidates.append(combination)

    return candidates


def _combinations(
    values: Sequence[str],
    size: int,
) -> Iterable[Tuple[str, ...]]:
    """Small standard-library-free combination generator."""

    if size == 0:
        yield ()
        return

    if size > len(values):
        return

    def recurse(
        start: int,
        chosen: List[str],
    ) -> Iterable[Tuple[str, ...]]:
        if len(chosen) == size:
            yield tuple(chosen)
            return

        remaining = size - len(chosen)

        for index in range(
            start,
            len(values) - remaining + 1,
        ):
            chosen.append(values[index])
            yield from recurse(index + 1, chosen)
            chosen.pop()

    yield from recurse(0, [])


def section_31_candidate_key_discovery() -> None:
    print("\n" + "=" * 78)
    print("31. CANDIDATE KEY DISCOVERY")
    print("=" * 78)

    rows = [
        {
            "EmployeeID": 1,
            "Email": "a@example.com",
            "Name": "Asha",
        },
        {
            "EmployeeID": 2,
            "Email": "b@example.com",
            "Name": "Ravi",
        },
        {
            "EmployeeID": 3,
            "Email": "c@example.com",
            "Name": "Meera",
        },
    ]

    attributes = ["EmployeeID", "Email", "Name"]

    print(
        "Candidate keys discovered by brute-force uniqueness testing:"
    )

    for candidate in discover_candidate_keys(rows, attributes):
        print(" ", candidate)

    print(
        """
This technique demonstrates the definition of a candidate key, but it does
not discover business semantics. A dataset can accidentally contain unique
values that are not guaranteed to remain unique.

For example, names might currently be unique but should not automatically be
treated as candidate keys.
"""
    )


# ============================================================================
# 33. COMPOSITE KEYS
# ============================================================================

def section_32_composite_keys() -> None:
    print("\n" + "=" * 78)
    print("32. COMPOSITE KEYS")
    print("=" * 78)

    registrations = Relation(
        "REGISTRATION",
        [
            Column("StudentID", int),
            Column("CourseID", int),
            Column("Semester", str),
        ],
        primary_key=("StudentID", "CourseID", "Semester"),
        rows=[
            {
                "StudentID": 1,
                "CourseID": 101,
                "Semester": "2026-FALL",
            },
            {
                "StudentID": 1,
                "CourseID": 102,
                "Semester": "2026-FALL",
            },
            {
                "StudentID": 1,
                "CourseID": 101,
                "Semester": "2027-SPRING",
            },
        ],
    )

    registrations.print_table("REGISTRATION")

    print(
        """
A composite key is appropriate when uniqueness is inherently determined by
multiple attributes.

(StudentID, CourseID, Semester)

means that the same student may take the same course again in a different
semester while the complete three-attribute combination remains unique.
"""
    )


# ============================================================================
# 34. RELATIONAL ALGEBRA PIPELINE
# ============================================================================

def section_33_algebra_pipeline() -> None:
    print("\n" + "=" * 78)
    print("33. COMBINING RELATIONAL ALGEBRA OPERATIONS")
    print("=" * 78)

    employees = Relation(
        "EMPLOYEE",
        [
            Column("EmployeeID", int),
            Column("Name", str),
            Column("DepartmentID", int),
            Column("Salary", float),
        ],
        rows=[
            {
                "EmployeeID": 1,
                "Name": "Asha",
                "DepartmentID": 10,
                "Salary": 80000.0,
            },
            {
                "EmployeeID": 2,
                "Name": "Ravi",
                "DepartmentID": 20,
                "Salary": 60000.0,
            },
            {
                "EmployeeID": 3,
                "Name": "Meera",
                "DepartmentID": 10,
                "Salary": 95000.0,
            },
        ],
    )

    departments = Relation(
        "DEPARTMENT",
        [
            Column("DepartmentID", int),
            Column("DepartmentName", str),
        ],
        rows=[
            {"DepartmentID": 10, "DepartmentName": "IT"},
            {"DepartmentID": 20, "DepartmentName": "HR"},
        ],
    )

    joined = inner_join(
        employees,
        departments,
        ["DepartmentID"],
        ["DepartmentID"],
    )

    filtered = selection(
        joined,
        lambda row: row["Salary"] >= 90000.0,
        "FILTERED",
    )

    final = projection(
        filtered,
        ["Name", "DepartmentName"],
        "FINAL",
    )

    joined.print_table("1. Join")
    filtered.print_table("2. Selection")
    final.print_table("3. Projection")

    print(
        """
This mirrors:

    π Name, DepartmentName
      (
        σ Salary >= 90000
          (
            EMPLOYEE ⋈ DEPARTMENT
          )
      )

The same logical query can often be reordered by an optimizer into a more
efficient physical plan, provided the transformation preserves semantics.
"""
    )


# ============================================================================
# 35. EDGE CASES
# ============================================================================

def section_34_edge_cases() -> None:
    print("\n" + "=" * 78)
    print("34. IMPORTANT EDGE CASES")
    print("=" * 78)

    print(
        """
1. Empty relation
   A relation may contain zero tuples while still having a valid schema.

2. Duplicate insertion
   Mathematical relations do not contain duplicate tuples.

3. Duplicate projected values
   Projection eliminates duplicates in classical relational algebra.

4. NULL
   SQL's NULL behavior differs from ordinary Python None equality.

5. Composite keys
   Uniqueness depends on the entire combination.

6. Empty result
   A valid query may produce a relation with zero tuples.

7. Empty divisor in relational division
   Formal relational division has subtle mathematical behavior for an empty
   divisor. Implementations and SQL formulations should be analyzed carefully
   rather than assumed equivalent.

8. Attribute-name collisions
   Joins can produce ambiguous names. SQL resolves this through qualification
   and aliases.

9. Foreign-key NULLs
   SQL allows NULL foreign keys unless prohibited by NOT NULL or other
   constraints.

10. Domain assumptions
    A type such as integer does not necessarily capture all business rules.
    CHECK constraints may still be required.
"""
    )

    empty = Relation(
        "EMPTY",
        [
            Column("ID", int),
            Column("Name", str),
        ],
    )

    empty.print_table("Valid empty relation")

    try:
        empty.insert({"ID": 1, "Name": "A"})
        empty.insert({"ID": 1, "Name": "A"})
    except ConstraintError as error:
        print("\nDuplicate tuple edge case:", error)


# ============================================================================
# 36. COMMON DESIGN MISTAKES
# ============================================================================

def section_35_common_mistakes() -> None:
    print("\n" + "=" * 78)
    print("35. COMMON RELATIONAL-DESIGN MISTAKES")
    print("=" * 78)

    print(
        """
Mistake 1: Treating a table as merely a spreadsheet
    Relational design includes domains, keys, dependencies, and constraints.

Mistake 2: Using a non-unique business attribute as a primary key
    Names, phone numbers, or addresses may change or fail uniqueness.

Mistake 3: Storing comma-separated lists
    Example:
        Skills = "Python,SQL,Java"
    This complicates querying and violates atomicity assumptions.

Mistake 4: Repeating columns
    Example:
        Phone1, Phone2, Phone3
    A separate relation may be more appropriate when the number of values is
    variable.

Mistake 5: Ignoring foreign keys
    This permits orphaned references and weakens referential integrity.

Mistake 6: Excessive normalization without workload awareness
    Correctness matters, but highly fragmented schemas can require many joins.

Mistake 7: Premature denormalization
    Duplication introduced before a measured performance need can create
    unnecessary synchronization problems.

Mistake 8: Assuming current uniqueness means guaranteed uniqueness
    A candidate key must be justified by domain semantics and constraints.

Mistake 9: Confusing NULL with zero or empty string
    They represent different concepts.

Mistake 10: Relying only on application validation
    Multiple clients can bypass application rules. Database constraints are
    important for shared persistent state.

Mistake 11: Assuming SQL is identical to classical relational algebra
    SQL has duplicate and NULL semantics that require separate consideration.

Mistake 12: Ignoring transaction boundaries
    Multiple related updates should be protected by appropriate transaction
    semantics.
"""
    )


# ============================================================================
# 37. RELATIONAL MODEL LIMITATIONS
# ============================================================================

def section_36_limitations() -> None:
    print("\n" + "=" * 78)
    print("36. LIMITATIONS AND TRADE-OFFS")
    print("=" * 78)

    print(
        """
Strengths:

    - Simple tabular abstraction.
    - Strong mathematical foundation.
    - Declarative query capabilities.
    - Mature integrity mechanisms.
    - Powerful join and set operations.
    - Well-understood normalization principles.
    - Mature transaction and concurrency technology.

Trade-offs:

    - Complex relationships can require many joins.
    - Object-oriented structures may require mapping layers.
    - Hierarchical or graph-shaped queries may be less direct than in
      specialized models.
    - Schema changes can be operationally expensive in some systems.
    - Strong consistency and relational constraints can increase write cost.
    - Distributed relational systems introduce additional consistency,
      latency, and coordination considerations.

The relational model remains especially effective where structured entities,
integrity constraints, transactional correctness, and ad hoc querying are
central requirements.
"""
    )


# ============================================================================
# 38. PRACTICAL DATABASE DESIGN WORKFLOW
# ============================================================================

def section_37_design_workflow() -> None:
    print("\n" + "=" * 78)
    print("37. PRACTICAL RELATIONAL DATABASE DESIGN WORKFLOW")
    print("=" * 78)

    print(
        """
A disciplined design process can be organized as follows:

1. Identify business entities and concepts.
2. Identify attributes.
3. Identify domains and legal values.
4. Identify candidate keys.
5. Select appropriate primary keys.
6. Identify relationships between entities.
7. Map relationships to relations.
8. Define foreign keys.
9. Document functional dependencies.
10. Normalize where appropriate.
11. Verify lossless decomposition.
12. Evaluate dependency preservation.
13. Define integrity constraints.
14. Consider transaction boundaries.
15. Identify important query patterns.
16. Add indexes based on actual access patterns.
17. Evaluate execution plans and cardinality.
18. Test concurrency behavior.
19. Apply authorization and security controls.
20. Monitor production workload and revise physical design when justified.

Logical design and physical optimization should be treated as related but
distinct concerns.
"""
    )


# ============================================================================
# 39. PRACTICAL E-COMMERCE MODEL
# ============================================================================

def section_38_real_world_model() -> None:
    print("\n" + "=" * 78)
    print("38. REAL-WORLD E-COMMERCE RELATIONAL MODEL")
    print("=" * 78)

    customer = Relation(
        "CUSTOMER",
        [
            Column("CustomerID", int),
            Column("Name", str),
        ],
        primary_key=("CustomerID",),
        rows=[
            {"CustomerID": 1, "Name": "Asha"},
            {"CustomerID": 2, "Name": "Ravi"},
        ],
    )

    product = Relation(
        "PRODUCT",
        [
            Column("ProductID", int),
            Column("ProductName", str),
            Column("Price", float),
        ],
        primary_key=("ProductID",),
        checks=[
            (
                "Price must be non-negative",
                lambda row: row["Price"] >= 0,
            )
        ],
        rows=[
            {"ProductID": 100, "ProductName": "Keyboard", "Price": 1500.0},
            {"ProductID": 200, "ProductName": "Mouse", "Price": 700.0},
        ],
    )

    order = Relation(
        "ORDERS",
        [
            Column("OrderID", int),
            Column("CustomerID", int),
        ],
        primary_key=("OrderID",),
        foreign_keys=[
            (
                ("CustomerID",),
                customer,
                ("CustomerID",),
            )
        ],
        rows=[
            {"OrderID": 5001, "CustomerID": 1},
            {"OrderID": 5002, "CustomerID": 2},
        ],
    )

    order_item = Relation(
        "ORDER_ITEM",
        [
            Column("OrderID", int),
            Column("ProductID", int),
            Column("Quantity", int),
        ],
        primary_key=("OrderID", "ProductID"),
        foreign_keys=[
            (
                ("OrderID",),
                order,
                ("OrderID",),
            ),
            (
                ("ProductID",),
                product,
                ("ProductID",),
            ),
        ],
        checks=[
            (
                "Quantity must be positive",
                lambda row: row["Quantity"] > 0,
            )
        ],
        rows=[
            {"OrderID": 5001, "ProductID": 100, "Quantity": 2},
            {"OrderID": 5001, "ProductID": 200, "Quantity": 1},
            {"OrderID": 5002, "ProductID": 200, "Quantity": 3},
        ],
    )

    customer.print_table("CUSTOMER")
    product.print_table("PRODUCT")
    order.print_table("ORDERS")
    order_item.print_table("ORDER_ITEM")

    print(
        """
Design observations:

CUSTOMER
    One tuple per customer.

PRODUCT
    One tuple per product.

ORDERS
    One tuple per order, referencing its customer.

ORDER_ITEM
    Associative relation between orders and products.

The composite primary key (OrderID, ProductID) prevents the same product
from appearing more than once within the same order while permitting the
same product to occur in many different orders.
"""
    )

    order_customer = inner_join(
        order,
        customer,
        ["CustomerID"],
        ["CustomerID"],
        "ORDER_CUSTOMER",
    )

    order_customer.print_table(
        "Orders associated with customers"
    )


# ============================================================================
# 40. PROPERTY-BASED STYLE INVARIANTS
# ============================================================================

def section_39_invariants() -> None:
    print("\n" + "=" * 78)
    print("39. RELATIONAL INVARIANTS AND TESTING")
    print("=" * 78)

    relation = Relation(
        "TEST",
        [
            Column("ID", int),
            Column("Value", str),
        ],
        primary_key=("ID",),
        rows=[
            {"ID": 1, "Value": "A"},
            {"ID": 2, "Value": "B"},
        ],
    )

    assert relation.degree == 2
    assert relation.cardinality == 2

    ids = [row["ID"] for row in relation.rows()]
    assert len(ids) == len(set(ids))

    projected = projection(
        relation,
        ["Value"],
    )

    assert projected.cardinality == 2

    selected = selection(
        relation,
        lambda row: row["ID"] > 100,
    )

    assert selected.cardinality == 0

    print("Basic relational invariants passed.")

    print(
        """
Useful database tests include:

    - Key uniqueness.
    - Foreign-key validity.
    - Domain validity.
    - CHECK constraints.
    - Expected cardinality bounds.
    - Join correctness.
    - Duplicate elimination where appropriate.
    - NULL behavior.
    - Transaction rollback behavior.
    - Migration compatibility.
    - Query-result regression tests.

Tests should cover both normal and adversarial states.
"""
    )


# ============================================================================
# 41. MINI QUERY ENGINE
# ============================================================================

class Query:
    """
    Fluent educational query object.

    It illustrates the idea that a declarative query can be represented as
    a sequence of logical relational operations.
    """

    def __init__(self, relation: Relation):
        self.relation = relation

    def where(
        self,
        predicate: Callable[[Dict[str, Any]], bool],
    ) -> "Query":
        return Query(
            selection(
                self.relation,
                predicate,
                self.relation.name,
            )
        )

    def select(
        self,
        *attributes: str,
    ) -> "Query":
        return Query(
            projection(
                self.relation,
                attributes,
                self.relation.name,
            )
        )

    def result(self) -> Relation:
        return self.relation


def section_40_mini_query_engine() -> None:
    print("\n" + "=" * 78)
    print("40. MINI DECLARATIVE QUERY PIPELINE")
    print("=" * 78)

    products = Relation(
        "PRODUCT",
        [
            Column("ProductID", int),
            Column("Name", str),
            Column("Category", str),
            Column("Price", float),
        ],
        rows=[
            {
                "ProductID": 1,
                "Name": "Keyboard",
                "Category": "Computer",
                "Price": 1500.0,
            },
            {
                "ProductID": 2,
                "Name": "Mouse",
                "Category": "Computer",
                "Price": 700.0,
            },
            {
                "ProductID": 3,
                "Name": "Chair",
                "Category": "Furniture",
                "Price": 5000.0,
            },
        ],
    )

    result = (
        Query(products)
        .where(lambda row: row["Price"] >= 1000.0)
        .select("Name", "Price")
        .result()
    )

    result.print_table(
        "Products with Price >= 1000, projected to Name and Price"
    )

    print(
        """
The chain:

    where(...)
    select(...)

corresponds conceptually to relational operations:

    σ Price >= 1000
    π Name, Price

The physical execution order could be optimized by a real DBMS.
"""
    )


# ============================================================================
# 42. RELATIONAL MODEL CHECKLIST
# ============================================================================

def section_41_checklist() -> None:
    print("\n" + "=" * 78)
    print("41. TECHNICAL CHECKLIST")
    print("=" * 78)

    checklist = [
        "Relation has a defined schema.",
        "Attributes have meaningful domains.",
        "Tuples conform to the schema.",
        "Primary key identifies tuples.",
        "Candidate keys are understood.",
        "Foreign keys represent valid references.",
        "Entity integrity is enforced.",
        "Referential integrity is enforced.",
        "Functional dependencies are documented.",
        "Normalization decisions are deliberate.",
        "Lossless decomposition is considered.",
        "Dependency preservation is considered.",
        "NULL semantics are understood.",
        "Relational algebra operations are understood.",
        "Join behavior is understood.",
        "SQL bag semantics are distinguished from set semantics.",
        "Indexes are treated as physical structures.",
        "Transactions protect multi-step state changes.",
        "Concurrency anomalies are understood.",
        "Least privilege is applied.",
        "Queries use parameterization.",
        "Production performance is measured rather than guessed.",
    ]

    for number, item in enumerate(checklist, start=1):
        print(f"{number:2}. [ ] {item}")


# ============================================================================
# 43. COMPREHENSIVE EXAM-STYLE DEMONSTRATION
# ============================================================================

def section_42_exam_example() -> None:
    print("\n" + "=" * 78)
    print("42. COMPREHENSIVE RELATIONAL-MODEL EXAMPLE")
    print("=" * 78)

    department = Relation(
        "DEPARTMENT",
        [
            Column("DepartmentID", int),
            Column("DepartmentName", str),
        ],
        primary_key=("DepartmentID",),
        candidate_keys=[("DepartmentName",)],
        rows=[
            {
                "DepartmentID": 1,
                "DepartmentName": "CSE",
            },
            {
                "DepartmentID": 2,
                "DepartmentName": "MBA",
            },
        ],
    )

    student = Relation(
        "STUDENT",
        [
            Column("StudentID", int),
            Column("Name", str),
            Column("DepartmentID", int),
        ],
        primary_key=("StudentID",),
        foreign_keys=[
            (
                ("DepartmentID",),
                department,
                ("DepartmentID",),
            )
        ],
        rows=[
            {"StudentID": 101, "Name": "Asha", "DepartmentID": 1},
            {"StudentID": 102, "Name": "Ravi", "DepartmentID": 1},
            {"StudentID": 103, "Name": "Meera", "DepartmentID": 2},
        ],
    )

    course = Relation(
        "COURSE",
        [
            Column("CourseID", int),
            Column("CourseName", str),
        ],
        primary_key=("CourseID",),
        rows=[
            {"CourseID": 10, "CourseName": "DBMS"},
            {"CourseID": 20, "CourseName": "Statistics"},
        ],
    )

    enrollment = Relation(
        "ENROLLMENT",
        [
            Column("StudentID", int),
            Column("CourseID", int),
            Column("Grade", str),
        ],
        primary_key=("StudentID", "CourseID"),
        foreign_keys=[
            (
                ("StudentID",),
                student,
                ("StudentID",),
            ),
            (
                ("CourseID",),
                course,
                ("CourseID",),
            ),
        ],
        rows=[
            {"StudentID": 101, "CourseID": 10, "Grade": "A"},
            {"StudentID": 101, "CourseID": 20, "Grade": "A"},
            {"StudentID": 102, "CourseID": 10, "Grade": "B"},
            {"StudentID": 103, "CourseID": 10, "Grade": "A"},
        ],
    )

    department.print_table("DEPARTMENT")
    student.print_table("STUDENT")
    course.print_table("COURSE")
    enrollment.print_table("ENROLLMENT")

    student_department = inner_join(
        student,
        department,
        ["DepartmentID"],
        ["DepartmentID"],
    )

    student_department.print_table(
        "Students with their departments"
    )

    excellent = selection(
        enrollment,
        lambda row: row["Grade"] == "A",
    )

    excellent.print_table(
        "Enrollment tuples with Grade = A"
    )

    all_required = division(
        enrollment,
        Relation(
            "REQUIRED_COURSES",
            [Column("CourseID", int)],
            rows=[
                {"CourseID": 10},
                {"CourseID": 20},
            ],
        ),
    )

    all_required.print_table(
        "Students taking every required course"
    )


# ============================================================================
# 44. MAIN PROGRAM
# ============================================================================

def main() -> None:
    """
    Run the complete educational demonstration.

    Each section is independent enough to illustrate a particular concept,
    while later sections combine concepts introduced earlier.
    """

    print("=" * 78)
    print("RELATIONAL MODEL: COMPLETE PYTHON STUDY GUIDE")
    print("=" * 78)

    section_01_fundamentals()
    section_02_domains()
    section_03_keys()
    section_04_referential_integrity()
    section_05_selection()
    section_06_projection()
    section_07_set_operations()
    section_08_cartesian_product()
    section_09_rename()
    section_10_joins()
    section_11_theta_join()
    section_12_division()
    section_13_sql_mapping()
    section_14_null_logic()
    section_15_integrity_constraints()
    section_16_er_mapping()
    section_17_functional_dependencies()
    section_18_normalization()
    section_19_decomposition()
    section_20_denormalization()
    section_21_relational_completeness()
    section_22_relational_vs_sql()
    section_23_query_processing()
    section_24_join_performance()
    section_25_indexes()
    section_26_transactions()
    section_27_concurrency()
    section_28_security()
    demonstrate_sql_injection_concept()
    section_30_anomalies()
    section_31_candidate_key_discovery()
    section_32_composite_keys()
    section_33_algebra_pipeline()
    section_34_edge_cases()
    section_35_common_mistakes()
    section_36_limitations()
    section_37_design_workflow()
    section_38_real_world_model()
    section_39_invariants()
    section_40_mini_query_engine()
    section_41_checklist()
    section_42_exam_example()

    print("\n" + "=" * 78)
    print("END OF RELATIONAL MODEL STUDY GUIDE")
    print("=" * 78)


if __name__ == "__main__":
    main()
