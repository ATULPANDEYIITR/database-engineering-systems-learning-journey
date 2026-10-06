/*
 * Advanced Database Normalization: BCNF, 4NF, and 5NF
 *
 * Java 17+
 *
 * Enterprise-oriented case study:
 * A university information platform maintains teaching assignments,
 * instructor offices, employee capabilities, and supplier-part-project
 * relationships. The model uses explicit domain types and services to
 * evaluate normalization rules rather than representing them as loose
 * conditional statements.
 */

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;

public class AdvancedNormalization {

    enum NormalForm {
        BCNF,
        FOUR_NF,
        FIVE_NF
    }

    record FunctionalDependency(
        Set<String> determinant,
        Set<String> dependent
    ) {
        public FunctionalDependency {
            determinant = immutableSet(determinant);
            dependent = immutableSet(dependent);
        }

        @Override
        public String toString() {
            return formatSet(determinant)
                + " -> "
                + formatSet(dependent);
        }
    }

    record MultivaluedDependency(
        Set<String> determinant,
        Set<String> dependent,
        Set<String> relation
    ) {
        public MultivaluedDependency {
            determinant = immutableSet(determinant);
            dependent = immutableSet(dependent);
            relation = immutableSet(relation);
        }

        @Override
        public String toString() {
            return formatSet(determinant)
                + " ->> "
                + formatSet(dependent)
                + " in "
                + formatSet(relation);
        }
    }

    record JoinDependency(
        Set<String> relation,
        List<Set<String>> components
    ) {
        public JoinDependency {
            relation = immutableSet(relation);
            components = components.stream()
                .map(AdvancedNormalization::immutableSet)
                .toList();
        }

        @Override
        public String toString() {
            return "*{"
                + components.stream()
                    .map(AdvancedNormalization::formatSet)
                    .collect(Collectors.joining(", "))
                + "} on "
                + formatSet(relation);
        }
    }

    record RelationSchema(
        String name,
        Set<String> attributes,
        List<FunctionalDependency> functionalDependencies,
        List<MultivaluedDependency> multivaluedDependencies,
        List<JoinDependency> joinDependencies
    ) {
        public RelationSchema {
            Objects.requireNonNull(name);
            attributes = immutableSet(attributes);
            functionalDependencies = List.copyOf(functionalDependencies);
            multivaluedDependencies = List.copyOf(multivaluedDependencies);
            joinDependencies = List.copyOf(joinDependencies);
        }
    }

    record NormalizationReport(
        String relation,
        List<Set<String>> candidateKeys,
        List<FunctionalDependency> bcnfViolations,
        List<MultivaluedDependency> fourNfViolations,
        List<JoinDependency> joinDependencies
    ) {
        boolean bcnfCompliant() {
            return bcnfViolations.isEmpty();
        }

        boolean fourNfCompliant() {
            return fourNfViolations.isEmpty();
        }
    }

    static Set<String> immutableSet(Collection<String> values) {
        return Collections.unmodifiableSet(
            new TreeSet<>(values)
        );
    }

    static Set<String> union(
        Set<String> left,
        Set<String> right
    ) {
        Set<String> result = new TreeSet<>(left);
        result.addAll(right);
        return result;
    }

    static Set<String> difference(
        Set<String> left,
        Set<String> right
    ) {
        Set<String> result = new TreeSet<>(left);

        for (String value : right) {
            result.remove(value);
        }

        return result;
    }

    static boolean subset(
        Set<String> subset,
        Set<String> superset
    ) {
        return superset.containsAll(subset);
    }

    static boolean equal(
        Set<String> left,
        Set<String> right
    ) {
        return left.equals(right);
    }

    static String formatSet(Set<String> attributes) {
        return "{"
            + attributes.stream()
                .sorted()
                .collect(Collectors.joining(", "))
            + "}";
    }

    static Set<String> closure(
        Set<String> attributes,
        List<FunctionalDependency> dependencies
    ) {
        Set<String> result = new TreeSet<>(attributes);

        boolean changed = true;

        while (changed) {
            changed = false;

            for (FunctionalDependency dependency : dependencies) {
                if (!subset(dependency.determinant(), result)) {
                    continue;
                }

                int before = result.size();

                result.addAll(dependency.dependent());

                if (result.size() != before) {
                    changed = true;
                }
            }
        }

        return result;
    }

    static boolean isSuperkey(
        Set<String> attributes,
        RelationSchema relation
    ) {
        return equal(
            closure(
                attributes,
                relation.functionalDependencies()
            ),
            relation.attributes()
        );
    }

    static List<Set<String>> allSubsets(
        Set<String> attributes
    ) {
        List<String> values = new ArrayList<>(attributes);
        List<Set<String>> result = new ArrayList<>();

        long count = 1L << values.size();

        for (long mask = 0; mask < count; mask++) {
            Set<String> subset = new TreeSet<>();

            for (int bit = 0; bit < values.size(); bit++) {
                if ((mask & (1L << bit)) != 0) {
                    subset.add(values.get(bit));
                }
            }

            result.add(subset);
        }

        result.sort(
            Comparator
                .comparingInt(Set::size)
                .thenComparing(Object::toString)
        );

        return result;
    }

    static List<Set<String>> candidateKeys(
        RelationSchema relation
    ) {
        List<Set<String>> keys = new ArrayList<>();

        for (Set<String> subset : allSubsets(relation.attributes())) {
            if (subset.isEmpty()) {
                continue;
            }

            if (!isSuperkey(subset, relation)) {
                continue;
            }

            boolean hasSmallerKey = keys.stream()
                .anyMatch(existing -> subset(subset, existing));

            if (!hasSmallerKey) {
                keys.add(subset);
            }
        }

        return keys;
    }

    static boolean trivial(
        FunctionalDependency dependency
    ) {
        return subset(
            dependency.dependent(),
            dependency.determinant()
        );
    }

    static List<FunctionalDependency> bcnfViolations(
        RelationSchema relation
    ) {
        return relation.functionalDependencies().stream()
            .filter(dependency -> !trivial(dependency))
            .filter(dependency ->
                !isSuperkey(dependency.determinant(), relation)
            )
            .toList();
    }

    static List<FunctionalDependency> projectFDs(
        RelationSchema source,
        Set<String> attributes
    ) {
        return source.functionalDependencies().stream()
            .filter(dependency ->
                subset(
                    union(
                        dependency.determinant(),
                        dependency.dependent()
                    ),
                    attributes
                )
            )
            .toList();
    }

    static List<RelationSchema> bcnfDecompose(
        RelationSchema relation
    ) {
        List<FunctionalDependency> violations =
            bcnfViolations(relation);

        if (violations.isEmpty()) {
            return List.of(relation);
        }

        FunctionalDependency violation =
            violations.getFirst();

        Set<String> firstAttributes = union(
            violation.determinant(),
            violation.dependent()
        );

        Set<String> secondAttributes = union(
            violation.determinant(),
            difference(
                relation.attributes(),
                violation.dependent()
            )
        );

        RelationSchema first = new RelationSchema(
            relation.name() + "_BCNF_A",
            firstAttributes,
            projectFDs(relation, firstAttributes),
            List.of(),
            List.of()
        );

        RelationSchema second = new RelationSchema(
            relation.name() + "_BCNF_B",
            secondAttributes,
            projectFDs(relation, secondAttributes),
            List.of(),
            List.of()
        );

        List<RelationSchema> result = new ArrayList<>();
        result.addAll(bcnfDecompose(first));
        result.addAll(bcnfDecompose(second));

        return result;
    }

    static boolean nonTrivial(
        MultivaluedDependency dependency
    ) {
        Set<String> xAndY = union(
            dependency.determinant(),
            dependency.dependent()
        );

        return !dependency.dependent().isEmpty()
            && !subset(
                dependency.dependent(),
                dependency.determinant()
            )
            && !xAndY.equals(dependency.relation());
    }

    static List<MultivaluedDependency> fourNfViolations(
        RelationSchema relation
    ) {
        List<MultivaluedDependency> result =
            new ArrayList<>();

        for (FunctionalDependency dependency :
            relation.functionalDependencies()) {

            MultivaluedDependency mvd =
                new MultivaluedDependency(
                    dependency.determinant(),
                    dependency.dependent(),
                    relation.attributes()
                );

            if (
                nonTrivial(mvd)
                && !isSuperkey(
                    mvd.determinant(),
                    relation
                )
            ) {
                result.add(mvd);
            }
        }

        for (MultivaluedDependency dependency :
            relation.multivaluedDependencies()) {

            if (
                nonTrivial(dependency)
                && !isSuperkey(
                    dependency.determinant(),
                    relation
                )
            ) {
                result.add(dependency);
            }
        }

        return result;
    }

    static List<RelationSchema> fourNfDecompose(
        RelationSchema relation,
        MultivaluedDependency violation
    ) {
        Set<String> firstAttributes = union(
            violation.determinant(),
            violation.dependent()
        );

        Set<String> secondAttributes = union(
            violation.determinant(),
            difference(
                relation.attributes(),
                violation.dependent()
            )
        );

        return List.of(
            new RelationSchema(
                relation.name() + "_4NF_A",
                firstAttributes,
                List.of(),
                List.of(),
                List.of()
            ),
            new RelationSchema(
                relation.name() + "_4NF_B",
                secondAttributes,
                List.of(),
                List.of(),
                List.of()
            )
        );
    }

    static NormalizationReport analyze(
        RelationSchema relation
    ) {
        return new NormalizationReport(
            relation.name(),
            candidateKeys(relation),
            bcnfViolations(relation),
            fourNfViolations(relation),
            relation.joinDependencies()
        );
    }

    static void printSchema(RelationSchema relation) {
        System.out.println();
        System.out.println("Relation: " + relation.name());
        System.out.println(
            "Attributes: " + formatSet(relation.attributes())
        );

        if (!relation.functionalDependencies().isEmpty()) {
            System.out.println("Functional dependencies:");

            relation.functionalDependencies().forEach(
                dependency ->
                    System.out.println("  " + dependency)
            );
        }

        if (!relation.multivaluedDependencies().isEmpty()) {
            System.out.println("Multivalued dependencies:");

            relation.multivaluedDependencies().forEach(
                dependency ->
                    System.out.println("  " + dependency)
            );
        }

        if (!relation.joinDependencies().isEmpty()) {
            System.out.println("Join dependencies:");

            relation.joinDependencies().forEach(
                dependency ->
                    System.out.println("  " + dependency)
            );
        }
    }

    static void demonstrateBCNF() {
        System.out.println("\n=== BCNF ENTERPRISE MODEL ===");

        RelationSchema teaching = new RelationSchema(
            "TeachingAssignment",
            Set.of(
                "Student",
                "Course",
                "Instructor",
                "InstructorOffice"
            ),
            List.of(
                new FunctionalDependency(
                    Set.of("Student", "Course"),
                    Set.of("Instructor")
                ),
                new FunctionalDependency(
                    Set.of("Instructor"),
                    Set.of("InstructorOffice")
                )
            ),
            List.of(),
            List.of()
        );

        printSchema(teaching);

        NormalizationReport report =
            analyze(teaching);

        System.out.println("Candidate keys:");
        report.candidateKeys().forEach(
            key -> System.out.println("  " + formatSet(key))
        );

        System.out.println("BCNF violations:");
        report.bcnfViolations().forEach(
            violation -> System.out.println("  " + violation)
        );

        System.out.println("BCNF decomposition:");

        bcnfDecompose(teaching).forEach(
            AdvancedNormalization::printSchema
        );
    }

    static void demonstrate4NF() {
        System.out.println(
            "\n=== 4NF EMPLOYEE CAPABILITY MODEL ==="
        );

        RelationSchema employee = new RelationSchema(
            "EmployeeCapability",
            Set.of(
                "Employee",
                "Skill",
                "Language"
            ),
            List.of(),
            List.of(
                new MultivaluedDependency(
                    Set.of("Employee"),
                    Set.of("Skill"),
                    Set.of(
                        "Employee",
                        "Skill",
                        "Language"
                    )
                )
            ),
            List.of()
        );

        printSchema(employee);

        NormalizationReport report =
            analyze(employee);

        report.fourNfViolations().forEach(
            violation -> {
                System.out.println(
                    "4NF violation: " + violation
                );

                System.out.println(
                    "Decomposition:"
                );

                fourNfDecompose(
                    employee,
                    violation
                ).forEach(
                    AdvancedNormalization::printSchema
                );
            }
        );

        System.out.println(
            "The separate relations represent independent "
            + "employee-to-skill and employee-to-language facts."
        );
    }

    static void demonstrate5NF() {
        System.out.println(
            "\n=== 5NF SUPPLIER-PART-PROJECT MODEL ==="
        );

        JoinDependency dependency =
            new JoinDependency(
                Set.of(
                    "Supplier",
                    "Part",
                    "Project"
                ),
                List.of(
                    Set.of("Supplier", "Part"),
                    Set.of("Supplier", "Project"),
                    Set.of("Part", "Project")
                )
            );

        RelationSchema supply =
            new RelationSchema(
                "SupplierPartProject",
                Set.of(
                    "Supplier",
                    "Part",
                    "Project"
                ),
                List.of(),
                List.of(),
                List.of(dependency)
            );

        printSchema(supply);

        System.out.println(
            "5NF requires the join dependency to be semantically valid. "
            + "The existence of three attributes alone does not justify "
            + "pairwise decomposition."
        );
    }

    static void demonstratePolicyBoundaries() {
        System.out.println(
            "\n=== NORMAL FORM POLICY BOUNDARIES ==="
        );

        System.out.println(
            "BCNF: every non-trivial functional dependency must have "
            + "a superkey determinant."
        );

        System.out.println(
            "4NF: every non-trivial multivalued dependency must have "
            + "a superkey determinant."
        );

        System.out.println(
            "5NF: every non-trivial join dependency must be implied by "
            + "the candidate-key structure and applicable constraints."
        );

        System.out.println(
            "A production schema should retain only decompositions whose "
            + "business semantics justify the resulting joins."
        );
    }

    public static void main(String[] args) {
        System.out.println(
            "============================================================"
        );
        System.out.println(
            "ADVANCED NORMALIZATION: BCNF, 4NF, AND 5NF"
        );
        System.out.println(
            "============================================================"
        );

        demonstrateBCNF();
        demonstrate4NF();
        demonstrate5NF();
        demonstratePolicyBoundaries();

        System.out.println(
            "\n=== NORMALIZATION ANALYSIS COMPLETE ==="
        );
    }
}
