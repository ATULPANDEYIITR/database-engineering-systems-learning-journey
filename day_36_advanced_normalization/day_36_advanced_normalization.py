"""
Advanced Database Normalization: BCNF, 4NF, and 5NF
====================================================

A self-contained executable learning and demonstration program covering:

- Functional dependencies and candidate keys
- Attribute closure
- Minimal/canonical covers
- BCNF decomposition
- Lossless decomposition checks
- Dependency preservation analysis
- 4NF and multivalued dependencies
- 4NF decomposition
- 5NF, join dependencies, and projection-based reasoning
- A practical normalization workflow
- Relational-schema validation
- Example schemas involving independent multivalued facts
- Reconstruction of decomposed relations through joins

The implementation uses only the Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import FrozenSet, Iterable, Sequence


Attribute = str
AttributeSet = FrozenSet[Attribute]


def fs(values: Iterable[Attribute]) -> AttributeSet:
    return frozenset(values)


def format_set(values: Iterable[Attribute]) -> str:
    return "{" + ", ".join(sorted(values)) + "}"


@dataclass(frozen=True)
class FunctionalDependency:
    determinant: AttributeSet
    dependent: AttributeSet

    def __str__(self) -> str:
        return f"{format_set(self.determinant)} -> {format_set(self.dependent)}"


@dataclass(frozen=True)
class MultivaluedDependency:
    determinant: AttributeSet
    dependent: AttributeSet
    relation: AttributeSet

    def __str__(self) -> str:
        return (
            f"{format_set(self.determinant)} ->> "
            f"{format_set(self.dependent)} "
            f"in {format_set(self.relation)}"
        )


@dataclass(frozen=True)
class JoinDependency:
    relation: AttributeSet
    components: tuple[AttributeSet, ...]

    def __str__(self) -> str:
        parts = ", ".join(format_set(component) for component in self.components)
        return f"*{{{parts}}} on {format_set(self.relation)}"


@dataclass
class RelationSchema:
    name: str
    attributes: AttributeSet
    functional_dependencies: list[FunctionalDependency] = field(default_factory=list)
    multivalued_dependencies: list[MultivaluedDependency] = field(default_factory=list)
    join_dependencies: list[JoinDependency] = field(default_factory=list)


def powerset(values: Sequence[Attribute]) -> Iterable[AttributeSet]:
    for size in range(len(values) + 1):
        for combination in combinations(values, size):
            yield fs(combination)


def attribute_closure(
    attributes: AttributeSet,
    dependencies: Sequence[FunctionalDependency],
) -> AttributeSet:
    """
    Compute X+ under a set of functional dependencies.

    The closure starts with X and repeatedly applies any dependency whose
    determinant is already contained in the closure.
    """
    closure = set(attributes)
    changed = True

    while changed:
        changed = False
        for dependency in dependencies:
            if dependency.determinant.issubset(closure):
                before = len(closure)
                closure.update(dependency.dependent)
                if len(closure) != before:
                    changed = True

    return frozenset(closure)


def is_superkey(
    attributes: AttributeSet,
    relation_attributes: AttributeSet,
    dependencies: Sequence[FunctionalDependency],
) -> bool:
    return attribute_closure(attributes, dependencies) == relation_attributes


def candidate_keys(
    relation_attributes: AttributeSet,
    dependencies: Sequence[FunctionalDependency],
) -> list[AttributeSet]:
    """
    Enumerate candidate keys.

    This exhaustive implementation is deliberately used for educational
    clarity. Real systems with very large schemas need more efficient
    dependency-analysis algorithms.
    """
    keys: list[AttributeSet] = []
    ordered = sorted(relation_attributes)

    for candidate in powerset(ordered):
        if not candidate:
            continue

        if not is_superkey(candidate, relation_attributes, dependencies):
            continue

        if all(not existing.issubset(candidate) for existing in keys):
            keys.append(candidate)

    return keys


def prime_attributes(keys: Sequence[AttributeSet]) -> AttributeSet:
    result: set[Attribute] = set()
    for key in keys:
        result.update(key)
    return frozenset(result)


def violates_bcnf(
    relation: RelationSchema,
) -> list[FunctionalDependency]:
    """
    BCNF requires every non-trivial FD X -> Y to have X as a superkey.
    """
    violations = []

    for dependency in relation.functional_dependencies:
        if dependency.dependent.issubset(dependency.determinant):
            continue

        if not is_superkey(
            dependency.determinant,
            relation.attributes,
            relation.functional_dependencies,
        ):
            violations.append(dependency)

    return violations


def is_trivial_fd(
    dependency: FunctionalDependency,
) -> bool:
    return dependency.dependent.issubset(dependency.determinant)


def split_fd_rhs(
    dependencies: Sequence[FunctionalDependency],
) -> list[FunctionalDependency]:
    result = []

    for dependency in dependencies:
        for attribute in dependency.dependent:
            result.append(
                FunctionalDependency(
                    dependency.determinant,
                    fs([attribute]),
                )
            )

    return result


def remove_extraneous_lhs_attributes(
    dependencies: Sequence[FunctionalDependency],
) -> list[FunctionalDependency]:
    """
    Remove attributes from determinants when they are logically redundant.
    """
    current = split_fd_rhs(dependencies)
    changed = True

    while changed:
        changed = False

        for index, dependency in enumerate(list(current)):
            determinant = set(dependency.determinant)

            for attribute in list(determinant):
                reduced_determinant = fs(determinant - {attribute})

                remaining = current.copy()
                remaining[index] = FunctionalDependency(
                    reduced_determinant,
                    dependency.dependent,
                )

                closure = attribute_closure(
                    reduced_determinant,
                    remaining,
                )

                if dependency.dependent.issubset(closure):
                    current[index] = FunctionalDependency(
                        reduced_determinant,
                        dependency.dependent,
                    )
                    changed = True
                    determinant.remove(attribute)

    return current


def remove_redundant_dependencies(
    dependencies: Sequence[FunctionalDependency],
) -> list[FunctionalDependency]:
    current = split_fd_rhs(dependencies)

    changed = True
    while changed:
        changed = False

        for index, dependency in enumerate(list(current)):
            remaining = current[:index] + current[index + 1 :]
            closure = attribute_closure(
                dependency.determinant,
                remaining,
            )

            if dependency.dependent.issubset(closure):
                current.pop(index)
                changed = True
                break

    return current


def canonical_cover(
    dependencies: Sequence[FunctionalDependency],
) -> list[FunctionalDependency]:
    """
    Compute a canonical/minimal cover:
    - singleton RHS
    - no extraneous LHS attributes
    - no redundant dependencies
    """
    step_one = split_fd_rhs(dependencies)
    step_two = remove_extraneous_lhs_attributes(step_one)
    step_three = remove_redundant_dependencies(step_two)

    unique = {
        (dependency.determinant, dependency.dependent): dependency
        for dependency in step_three
    }

    return list(unique.values())


def fd_implies(
    dependencies: Sequence[FunctionalDependency],
    target: FunctionalDependency,
) -> bool:
    closure = attribute_closure(target.determinant, dependencies)
    return target.dependent.issubset(closure)


def dependency_preserved(
    decomposed_relations: Sequence[RelationSchema],
    original_dependencies: Sequence[FunctionalDependency],
) -> bool:
    """
    Check dependency preservation by computing the union of FDs projected onto
    each decomposed relation.

    This is a practical finite test for the provided FD set.
    """
    projected: list[FunctionalDependency] = []

    for relation in decomposed_relations:
        for dependency in original_dependencies:
            if dependency.determinant.union(dependency.dependent).issubset(
                relation.attributes
            ):
                projected.append(dependency)

    for dependency in original_dependencies:
        if not fd_implies(projected, dependency):
            return False

    return True


def bcnf_decompose(
    relation: RelationSchema,
) -> list[RelationSchema]:
    """
    Recursive BCNF decomposition.

    For a violating FD X -> Y in R:
      R1 = X union Y
      R2 = R - (Y - X)

    The decomposition is lossless for the selected BCNF violation.
    """
    violations = violates_bcnf(relation)

    if not violations:
        return [relation]

    violating_fd = violations[0]
    x = violating_fd.determinant
    y = violating_fd.dependent

    r1_attributes = x.union(y)
    r2_attributes = relation.attributes.difference(y.difference(x))

    def project_dependencies(attributes: AttributeSet) -> list[FunctionalDependency]:
        projected = []

        for dependency in relation.functional_dependencies:
            if dependency.determinant.union(dependency.dependent).issubset(attributes):
                projected.append(dependency)

        return projected

    r1 = RelationSchema(
        name=f"{relation.name}_BCNF_A",
        attributes=r1_attributes,
        functional_dependencies=project_dependencies(r1_attributes),
    )

    r2 = RelationSchema(
        name=f"{relation.name}_BCNF_B",
        attributes=r2_attributes,
        functional_dependencies=project_dependencies(r2_attributes),
    )

    result: list[RelationSchema] = []
    result.extend(bcnf_decompose(r1))
    result.extend(bcnf_decompose(r2))
    return result


def nontrivial_mvd(
    mvd: MultivaluedDependency,
) -> bool:
    x = mvd.determinant
    y = mvd.dependent
    r = mvd.relation

    return bool(y) and not y.issubset(x) and not x.union(y) == r


def violates_4nf(
    relation: RelationSchema,
) -> list[MultivaluedDependency]:
    """
    4NF requires every non-trivial MVD X ->> Y to have X as a superkey.

    A relation's FDs also induce MVDs. Every FD X -> Y is an MVD X ->> Y.
    """
    violations = []

    for fd in relation.functional_dependencies:
        mvd = MultivaluedDependency(
            determinant=fd.determinant,
            dependent=fd.dependent,
            relation=relation.attributes,
        )

        if nontrivial_mvd(mvd) and not is_superkey(
            fd.determinant,
            relation.attributes,
            relation.functional_dependencies,
        ):
            violations.append(mvd)

    for mvd in relation.multivalued_dependencies:
        if nontrivial_mvd(mvd) and not is_superkey(
            mvd.determinant,
            relation.attributes,
            relation.functional_dependencies,
        ):
            violations.append(mvd)

    return violations


def mvd_4nf_decompose(
    relation: RelationSchema,
    violation: MultivaluedDependency,
) -> tuple[RelationSchema, RelationSchema]:
    """
    For a 4NF violation X ->> Y in R:
      R1 = X union Y
      R2 = R - Y + X
    """
    x = violation.determinant
    y = violation.dependent

    r1_attributes = x.union(y)
    r2_attributes = x.union(relation.attributes.difference(y))

    r1 = RelationSchema(
        name=f"{relation.name}_4NF_A",
        attributes=r1_attributes,
    )

    r2 = RelationSchema(
        name=f"{relation.name}_4NF_B",
        attributes=r2_attributes,
    )

    return r1, r2


def relation_contains(
    relation: RelationSchema,
    attributes: Iterable[Attribute],
) -> bool:
    return fs(attributes).issubset(relation.attributes)


def demonstrate_lossless_join(
    original_rows: list[dict[str, str]],
    left_attributes: Sequence[str],
    right_attributes: Sequence[str],
) -> list[dict[str, str]]:
    """
    Materialize a natural join between two projected relations.

    This function is used only as a concrete demonstration of how a
    decomposition can reconstruct the original information.
    """
    left_keys = [
        {key: row[key] for key in left_attributes}
        for row in original_rows
    ]
    right_keys = [
        {key: row[key] for key in right_attributes}
        for row in original_rows
    ]

    result: list[dict[str, str]] = []

    for left in left_keys:
        for right in right_keys:
            common = set(left).intersection(right)

            if all(left[column] == right[column] for column in common):
                merged = dict(left)
                merged.update(right)
                if merged not in result:
                    result.append(merged)

    return result


def demonstrate_4nf_join(
    rows: list[dict[str, str]],
    first_attributes: Sequence[str],
    second_attributes: Sequence[str],
) -> list[dict[str, str]]:
    return demonstrate_lossless_join(
        rows,
        first_attributes,
        second_attributes,
    )


def validate_relation_rows(
    relation: RelationSchema,
    rows: list[dict[str, str]],
) -> list[str]:
    errors = []

    for index, row in enumerate(rows):
        missing = relation.attributes.difference(row)

        if missing:
            errors.append(
                f"Row {index} is missing attributes {format_set(missing)}."
            )

        unexpected = set(row).difference(relation.attributes)

        if unexpected:
            errors.append(
                f"Row {index} contains unexpected attributes "
                f"{format_set(unexpected)}."
            )

    return errors


def check_fd_instance(
    rows: list[dict[str, str]],
    dependency: FunctionalDependency,
) -> bool:
    """
    Test whether a concrete relation instance satisfies an FD.

    Two rows that agree on X must agree on Y.
    """
    determinant = sorted(dependency.determinant)
    dependent = sorted(dependency.dependent)

    for left, right in combinations(rows, 2):
        if all(left[a] == right[a] for a in determinant):
            if any(left[a] != right[a] for a in dependent):
                return False

    return True


def check_mvd_instance(
    rows: list[dict[str, str]],
    mvd: MultivaluedDependency,
) -> bool:
    """
    Concrete MVD test.

    For every pair of tuples agreeing on X, the cross-combination of their
    Y values with their remaining values must also exist.
    """
    x = sorted(mvd.determinant)
    y = sorted(mvd.dependent)
    z = sorted(mvd.relation.difference(mvd.determinant.union(mvd.dependent)))

    row_signatures = {
        tuple(sorted(row.items()))
        for row in rows
    }

    for first, second in combinations(rows, 2):
        if not all(first[column] == second[column] for column in x):
            continue

        candidate_one = dict(first)
        candidate_two = dict(second)

        for column in y:
            candidate_one[column] = first[column]
            candidate_one[column] = second[column]
            candidate_two[column] = second[column]
            candidate_two[column] = first[column]

        # Construct the two required cross tuples explicitly.
        required_one = {}
        required_two = {}

        for column in mvd.relation:
            if column in x:
                required_one[column] = first[column]
                required_two[column] = first[column]
            elif column in y:
                required_one[column] = first[column]
                required_two[column] = second[column]
            else:
                required_one[column] = second[column]
                required_two[column] = first[column]

        if (
            tuple(sorted(required_one.items())) not in row_signatures
            or tuple(sorted(required_two.items())) not in row_signatures
        ):
            return False

    return True


def print_relation(relation: RelationSchema) -> None:
    print(f"\nRelation: {relation.name}")
    print(f"Attributes: {format_set(relation.attributes)}")

    if relation.functional_dependencies:
        print("Functional dependencies:")
        for dependency in relation.functional_dependencies:
            print(f"  {dependency}")

    if relation.multivalued_dependencies:
        print("Multivalued dependencies:")
        for dependency in relation.multivalued_dependencies:
            print(f"  {dependency}")

    if relation.join_dependencies:
        print("Join dependencies:")
        for dependency in relation.join_dependencies:
            print(f"  {dependency}")


def demonstrate_candidate_keys() -> None:
    print("\n=== Candidate Keys and Attribute Closure ===")

    relation_attributes = fs(
        ["StudentID", "CourseID", "InstructorID", "Grade"]
    )

    dependencies = [
        FunctionalDependency(fs(["StudentID", "CourseID"]), fs(["Grade"])),
        FunctionalDependency(fs(["CourseID"]), fs(["InstructorID"])),
    ]

    print(f"Relation attributes: {format_set(relation_attributes)}")

    closure = attribute_closure(
        fs(["StudentID", "CourseID"]),
        dependencies,
    )

    print(
        f"Closure of {{StudentID, CourseID}}: "
        f"{format_set(closure)}"
    )

    keys = candidate_keys(relation_attributes, dependencies)

    print("Candidate keys:")
    for key in keys:
        print(f"  {format_set(key)}")


def demonstrate_canonical_cover() -> None:
    print("\n=== Canonical Cover ===")

    dependencies = [
        FunctionalDependency(
            fs(["EmployeeID", "ProjectID"]),
            fs(["EmployeeName", "ProjectName"]),
        ),
        FunctionalDependency(
            fs(["ProjectID"]),
            fs(["ProjectName"]),
        ),
        FunctionalDependency(
            fs(["EmployeeID"]),
            fs(["EmployeeName"]),
        ),
    ]

    print("Original dependencies:")
    for dependency in dependencies:
        print(f"  {dependency}")

    cover = canonical_cover(dependencies)

    print("Canonical cover:")
    for dependency in cover:
        print(f"  {dependency}")


def demonstrate_bcnf() -> None:
    print("\n=== BCNF: Boyce-Codd Normal Form ===")

    relation = RelationSchema(
        name="CourseInstructorStudent",
        attributes=fs(
            [
                "StudentID",
                "CourseID",
                "InstructorID",
                "InstructorOffice",
            ]
        ),
        functional_dependencies=[
            FunctionalDependency(
                fs(["StudentID", "CourseID"]),
                fs(["InstructorID"]),
            ),
            FunctionalDependency(
                fs(["InstructorID"]),
                fs(["InstructorOffice"]),
            ),
        ],
    )

    print_relation(relation)

    keys = candidate_keys(
        relation.attributes,
        relation.functional_dependencies,
    )

    print("Candidate keys:")
    for key in keys:
        print(f"  {format_set(key)}")

    violations = violates_bcnf(relation)

    print("BCNF violations:")
    for violation in violations:
        print(f"  {violation}")

    decomposed = bcnf_decompose(relation)

    print("BCNF decomposition:")
    for child in decomposed:
        print_relation(child)


def demonstrate_bcnf_tradeoff() -> None:
    print("\n=== BCNF and Dependency Preservation ===")

    attributes = fs(["Student", "Course", "Instructor"])

    dependencies = [
        FunctionalDependency(
            fs(["Student", "Course"]),
            fs(["Instructor"]),
        ),
        FunctionalDependency(
            fs(["Instructor"]),
            fs(["Course"]),
        ),
    ]

    relation = RelationSchema(
        name="TeachingAssignment",
        attributes=attributes,
        functional_dependencies=dependencies,
    )

    print_relation(relation)

    keys = candidate_keys(attributes, dependencies)
    print("Candidate keys:")
    for key in keys:
        print(f"  {format_set(key)}")

    decomposition = bcnf_decompose(relation)

    print("BCNF relations:")
    for child in decomposition:
        print_relation(child)

    print(
        "Dependency preservation after the demonstrated decomposition:",
        dependency_preserved(decomposition, dependencies),
    )

    print(
        "BCNF can therefore improve redundancy/anomaly control while "
        "sometimes sacrificing direct dependency preservation."
    )


def demonstrate_4nf() -> None:
    print("\n=== 4NF: Multivalued Dependencies ===")

    relation = RelationSchema(
        name="EmployeeSkillLanguage",
        attributes=fs(
            ["Employee", "Skill", "Language"]
        ),
        multivalued_dependencies=[
            MultivaluedDependency(
                determinant=fs(["Employee"]),
                dependent=fs(["Skill"]),
                relation=fs(["Employee", "Skill", "Language"]),
            )
        ],
    )

    print_relation(relation)

    violation = relation.multivalued_dependencies[0]
    first, second = mvd_4nf_decompose(relation, violation)

    print("4NF violation:")
    print(f"  {violation}")

    print("4NF decomposition:")
    print_relation(first)
    print_relation(second)

    original_rows = [
        {
            "Employee": "E01",
            "Skill": "Python",
            "Language": "English",
        },
        {
            "Employee": "E01",
            "Skill": "Python",
            "Language": "French",
        },
        {
            "Employee": "E01",
            "Skill": "SQL",
            "Language": "English",
        },
        {
            "Employee": "E01",
            "Skill": "SQL",
            "Language": "French",
        },
    ]

    print("Original relation rows:")
    for row in original_rows:
        print(f"  {row}")

    skills = [
        {"Employee": row["Employee"], "Skill": row["Skill"]}
        for row in original_rows
    ]

    languages = [
        {"Employee": row["Employee"], "Language": row["Language"]}
        for row in original_rows
    ]

    skills = [dict(row) for row in {tuple(sorted(x.items())) for x in skills}]
    languages = [
        dict(row)
        for row in {tuple(sorted(x.items())) for x in languages}
    ]

    reconstructed = []

    for skill in skills:
        for language in languages:
            if skill["Employee"] == language["Employee"]:
                reconstructed.append(
                    {
                        "Employee": skill["Employee"],
                        "Skill": skill["Skill"],
                        "Language": language["Language"],
                    }
                )

    print("4NF decomposed relations:")
    print(f"  EmployeeSkill: {skills}")
    print(f"  EmployeeLanguage: {languages}")

    print("Natural join reconstruction:")
    for row in reconstructed:
        print(f"  {row}")


def demonstrate_5nf() -> None:
    print("\n=== 5NF: Join Dependencies ===")

    relation = RelationSchema(
        name="SupplierPartProject",
        attributes=fs(
            ["Supplier", "Part", "Project"]
        ),
        join_dependencies=[
            JoinDependency(
                relation=fs(["Supplier", "Part", "Project"]),
                components=(
                    fs(["Supplier", "Part"]),
                    fs(["Supplier", "Project"]),
                    fs(["Part", "Project"]),
                ),
            )
        ],
    )

    print_relation(relation)

    print(
        "\nThe relation represents a ternary association. "
        "A 5NF decomposition is justified when the business semantics "
        "guarantee that the ternary relationship is exactly reconstructible "
        "from the relevant pairwise relationships."
    )

    sp = [
        {"Supplier": "S1", "Part": "P1"},
        {"Supplier": "S1", "Part": "P2"},
    ]

    sj = [
        {"Supplier": "S1", "Project": "J1"},
    ]

    pj = [
        {"Part": "P1", "Project": "J1"},
        {"Part": "P2", "Project": "J1"},
    ]

    reconstructed = []

    for supplier_part in sp:
        for supplier_project in sj:
            for part_project in pj:
                if (
                    supplier_part["Supplier"]
                    == supplier_project["Supplier"]
                    and supplier_part["Part"]
                    == part_project["Part"]
                    and supplier_project["Project"]
                    == part_project["Project"]
                ):
                    reconstructed.append(
                        {
                            "Supplier": supplier_part["Supplier"],
                            "Part": supplier_part["Part"],
                            "Project": supplier_project["Project"],
                        }
                    )

    print("Supplier-Part:")
    for row in sp:
        print(f"  {row}")

    print("Supplier-Project:")
    for row in sj:
        print(f"  {row}")

    print("Part-Project:")
    for row in pj:
        print(f"  {row}")

    print("Join reconstruction:")
    for row in reconstructed:
        print(f"  {row}")


def demonstrate_instance_validation() -> None:
    print("\n=== Concrete Instance Validation ===")

    relation = RelationSchema(
        name="Enrollment",
        attributes=fs(["Student", "Course", "Grade"]),
        functional_dependencies=[
            FunctionalDependency(
                fs(["Student", "Course"]),
                fs(["Grade"]),
            )
        ],
    )

    valid_rows = [
        {"Student": "A01", "Course": "DB101", "Grade": "A"},
        {"Student": "A01", "Course": "OS201", "Grade": "B"},
        {"Student": "A02", "Course": "DB101", "Grade": "A"},
    ]

    invalid_rows = [
        {"Student": "A01", "Course": "DB101", "Grade": "A"},
        {"Student": "A01", "Course": "DB101", "Grade": "B"},
    ]

    dependency = relation.functional_dependencies[0]

    print("Valid FD instance:", check_fd_instance(valid_rows, dependency))
    print("Invalid FD instance:", check_fd_instance(invalid_rows, dependency))


def demonstrate_mvd_instance() -> None:
    print("\n=== Concrete MVD Instance Validation ===")

    relation = fs(["Employee", "Skill", "Language"])

    valid_rows = [
        {"Employee": "E1", "Skill": "Python", "Language": "English"},
        {"Employee": "E1", "Skill": "Python", "Language": "French"},
        {"Employee": "E1", "Skill": "SQL", "Language": "English"},
        {"Employee": "E1", "Skill": "SQL", "Language": "French"},
    ]

    invalid_rows = [
        {"Employee": "E1", "Skill": "Python", "Language": "English"},
        {"Employee": "E1", "Skill": "SQL", "Language": "French"},
    ]

    mvd = MultivaluedDependency(
        determinant=fs(["Employee"]),
        dependent=fs(["Skill"]),
        relation=relation,
    )

    print("MVD:", mvd)
    print(
        "Complete cross-product instance satisfies MVD:",
        check_mvd_instance(valid_rows, mvd),
    )
    print(
        "Incomplete cross-product instance satisfies MVD:",
        check_mvd_instance(invalid_rows, mvd),
    )


def practical_normalization_workflow() -> None:
    print("\n=== Practical Normalization Workflow ===")

    print(
        """
Start with the business relation and its real semantic rules.
Identify candidate keys rather than assuming that a convenient identifier
is automatically the only key.

Use functional dependencies to test BCNF. A dependency violates BCNF when
its determinant is not a superkey and the dependency is non-trivial.

After BCNF analysis, identify genuine multivalued dependencies. 4NF addresses
independent sets of facts that cannot be adequately described by ordinary
functional dependencies alone.

Finally, inspect join dependencies. 5NF is concerned with irreducible
decompositions caused by join dependencies, especially in relations that
represent complex multi-way associations.

Every decomposition must be evaluated for lossless reconstruction and, where
required by the application, dependency preservation.

Normalization is a semantic design activity. A decomposition is not justified
merely because its tables look smaller.
""".strip()
    )


def demonstrate_edge_cases() -> None:
    print("\n=== Edge Cases and Design Considerations ===")

    empty_key = fs([])
    relation_attributes = fs(["A", "B"])

    print(
        "Empty attribute closure:",
        format_set(attribute_closure(empty_key, [])),
    )

    print(
        "Single-attribute relation:",
        candidate_keys(
            fs(["A"]),
            [
                FunctionalDependency(
                    fs(["A"]),
                    fs(["A"]),
                )
            ],
        ),
    )

    print(
        "Trivial dependency A -> A:",
        is_trivial_fd(
            FunctionalDependency(fs(["A"]), fs(["A"]))
        ),
    )

    print(
        "A relation with no non-trivial dependencies has no BCNF violation."
    )

    print(
        "Important limitation: exhaustive candidate-key enumeration has "
        "exponential worst-case growth as the number of attributes increases."
    )


def main() -> None:
    print("=" * 72)
    print("ADVANCED NORMALIZATION: BCNF, 4NF, AND 5NF")
    print("=" * 72)

    demonstrate_candidate_keys()
    demonstrate_canonical_cover()
    demonstrate_bcnf()
    demonstrate_bcnf_tradeoff()
    demonstrate_4nf()
    demonstrate_5nf()
    demonstrate_instance_validation()
    demonstrate_mvd_instance()
    practical_normalization_workflow()
    demonstrate_edge_cases()

    print("\n=== Demonstration Complete ===")
    print(
        "The examples distinguish functional dependencies and BCNF, "
        "multivalued dependencies and 4NF, and join dependencies and 5NF."
    )


if __name__ == "__main__":
    main()
