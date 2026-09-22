/*
 * Set Operations in JavaScript
 * =============================
 *
 * A practical study of JavaScript's Set collection and mathematical
 * set operations, progressing from fundamentals to advanced applications.
 *
 * Topics:
 * - Set creation and uniqueness
 * - Membership
 * - Adding and deleting values
 * - Union
 * - Intersection
 * - Difference
 * - Symmetric difference
 * - Subsets and supersets
 * - Disjoint sets
 * - Set conversion
 * - Set algebra
 * - Object identity
 * - Set-based filtering
 * - Permission analysis
 * - Graph relationships
 * - Performance considerations
 * - Edge cases
 * - Validation and testing
 */

"use strict";

function section(title) {
    console.log("\n" + "=".repeat(78));
    console.log(title);
    console.log("=".repeat(78));
}

function printSet(label, values) {
    console.log(`${label}:`, [...values]);
}

function union(...sets) {
    const result = new Set();

    for (const currentSet of sets) {
        for (const value of currentSet) {
            result.add(value);
        }
    }

    return result;
}

function intersection(first, ...others) {
    const result = new Set();

    for (const value of first) {
        if (others.every((currentSet) => currentSet.has(value))) {
            result.add(value);
        }
    }

    return result;
}

function difference(first, ...others) {
    const result = new Set();

    for (const value of first) {
        if (!others.some((currentSet) => currentSet.has(value))) {
            result.add(value);
        }
    }

    return result;
}

function symmetricDifference(first, second) {
    const result = new Set();

    for (const value of first) {
        if (!second.has(value)) {
            result.add(value);
        }
    }

    for (const value of second) {
        if (!first.has(value)) {
            result.add(value);
        }
    }

    return result;
}

function isSubset(subset, superset) {
    for (const value of subset) {
        if (!superset.has(value)) {
            return false;
        }
    }

    return true;
}

function isDisjoint(first, second) {
    const smaller = first.size <= second.size ? first : second;
    const larger = smaller === first ? second : first;

    for (const value of smaller) {
        if (larger.has(value)) {
            return false;
        }
    }

    return true;
}

function demonstrateFundamentals() {
    section("1. SET FUNDAMENTALS");

    const numbers = new Set([1, 2, 3, 4, 5]);
    printSet("numbers", numbers);

    // Set automatically removes duplicate primitive values.
    const duplicates = new Set([1, 2, 2, 3, 3, 4]);
    printSet("duplicates removed", duplicates);

    console.log("numbers.has(3):", numbers.has(3));
    console.log("numbers.has(10):", numbers.has(10));
    console.log("numbers.size:", numbers.size);

    // Sets preserve insertion order during iteration.
    // This is different from treating a set as an indexed array.
    console.log("iteration order:");
    for (const value of numbers) {
        console.log(value);
    }
}

function demonstrateMutation() {
    section("2. ADDING AND REMOVING ELEMENTS");

    const values = new Set([1, 2, 3]);

    values.add(4);
    values.add(4);
    printSet("after adding 4 twice", values);

    values.add(5).add(6);
    printSet("after chained add operations", values);

    console.log("delete(6):", values.delete(6));
    console.log("delete(100):", values.delete(100));

    values.clear();
    printSet("after clear", values);
}

function demonstrateCoreOperations() {
    section("3. CORE SET OPERATIONS");

    const pythonStudents = new Set(["Asha", "Ravi", "Neha", "Kabir"]);
    const sqlStudents = new Set(["Neha", "Kabir", "Meera", "Arjun"]);

    printSet("Python students", pythonStudents);
    printSet("SQL students", sqlStudents);

    printSet("union", union(pythonStudents, sqlStudents));
    printSet("intersection", intersection(pythonStudents, sqlStudents));
    printSet("Python only", difference(pythonStudents, sqlStudents));
    printSet("SQL only", difference(sqlStudents, pythonStudents));
    printSet(
        "symmetric difference",
        symmetricDifference(pythonStudents, sqlStudents)
    );
}

function demonstrateRelationships() {
    section("4. SET RELATIONSHIPS");

    const permissions = new Set(["read", "write", "execute"]);
    const required = new Set(["read", "write"]);
    const unrelated = new Set(["network", "database"]);

    console.log("required is subset:", isSubset(required, permissions));
    console.log("permissions is superset:", isSubset(required, permissions));
    console.log(
        "permissions and unrelated are disjoint:",
        isDisjoint(permissions, unrelated)
    );

    console.log(
        "equal sets:",
        isSubset(permissions, new Set(permissions)) &&
        isSubset(new Set(permissions), permissions)
    );
}

function demonstrateMultipleSets() {
    section("5. MULTIPLE SET OPERATIONS");

    const a = new Set([1, 2, 3, 4]);
    const b = new Set([3, 4, 5, 6]);
    const c = new Set([4, 6, 7, 8]);

    printSet("A union B union C", union(a, b, c));
    printSet("A intersection B intersection C", intersection(a, b, c));
    printSet("A minus B and C", difference(a, b, c));
}

function demonstrateSetAlgebra() {
    section("6. SET ALGEBRA");

    const a = new Set([1, 2, 3]);
    const b = new Set([3, 4, 5]);
    const c = new Set([5, 6, 7]);

    const unionAB = union(a, b);
    const unionBA = union(b, a);
    const intersectionAB = intersection(a, b);
    const intersectionBA = intersection(b, a);

    console.log(
        "union is commutative:",
        isEqual(unionAB, unionBA)
    );

    console.log(
        "intersection is commutative:",
        isEqual(intersectionAB, intersectionBA)
    );

    console.log(
        "union is associative:",
        isEqual(
            union(union(a, b), c),
            union(a, union(b, c))
        )
    );

    console.log(
        "intersection is associative:",
        isEqual(
            intersection(intersection(a, b), c),
            intersection(a, intersection(b, c))
        )
    );
}

function isEqual(first, second) {
    return first.size === second.size && isSubset(first, second);
}

function demonstrateSetConversion() {
    section("7. ARRAY AND SET CONVERSION");

    const values = [5, 1, 5, 2, 3, 2, 4, 4];
    const uniqueValues = new Set(values);

    console.log("original array:", values);
    printSet("unique set", uniqueValues);

    const uniqueArray = [...uniqueValues];
    console.log("unique array:", uniqueArray);
}

function demonstrateObjectIdentity() {
    section("8. OBJECT IDENTITY AND SETS");

    const firstObject = { id: 1, name: "Atul" };
    const equivalentObject = { id: 1, name: "Atul" };

    const objects = new Set([firstObject, equivalentObject]);

    // JavaScript objects are compared by reference, not structural content.
    console.log("object set size:", objects.size);
    console.log("firstObject exists:", objects.has(firstObject));
    console.log("equivalentObject exists:", objects.has(equivalentObject));

    const sameReference = firstObject;
    console.log("same reference exists:", objects.has(sameReference));
}

function demonstrateNaNAndZero() {
    section("9. SPECIAL VALUE BEHAVIOR");

    const values = new Set([NaN, NaN, 0, -0]);

    // Set uses SameValueZero semantics for membership.
    console.log("Set size for [NaN, NaN, 0, -0]:", values.size);
    console.log("has(NaN):", values.has(NaN));
    console.log("has(-0):", values.has(-0));
}

function demonstratePracticalFiltering() {
    section("10. PRACTICAL DATA FILTERING");

    const users = [
        {
            name: "Asha",
            skills: new Set(["python", "sql", "linux"])
        },
        {
            name: "Ravi",
            skills: new Set(["python", "cpp"])
        },
        {
            name: "Neha",
            skills: new Set(["sql", "security", "linux"])
        },
        {
            name: "Kabir",
            skills: new Set(["python", "security", "docker"])
        }
    ];

    const requiredSkills = new Set(["python", "security"]);

    const matchingUsers = users
        .filter((user) => isSubset(requiredSkills, user.skills))
        .map((user) => user.name);

    console.log("users with all required skills:", matchingUsers);
}

function demonstratePermissions() {
    section("11. PERMISSION ANALYSIS");

    const userPermissions = new Set(["read", "write", "download"]);
    const requiredPermissions = new Set(["read", "write"]);
    const sensitivePermissions = new Set([
        "delete",
        "admin",
        "manage_users"
    ]);

    const missing = difference(requiredPermissions, userPermissions);
    const extra = difference(userPermissions, requiredPermissions);
    const dangerous = intersection(
        userPermissions,
        sensitivePermissions
    );

    printSet("missing permissions", missing);
    printSet("extra permissions", extra);
    printSet("sensitive permissions", dangerous);

    const valid =
        missing.size === 0 &&
        dangerous.size === 0;

    console.log("least-privilege validation:", valid);
}

function demonstrateGraphRelationships() {
    section("12. GRAPH-STYLE NEIGHBOR OPERATIONS");

    const graph = new Map([
        ["A", new Set(["B", "C"])],
        ["B", new Set(["A", "C", "D"])],
        ["C", new Set(["A", "B", "D"])],
        ["D", new Set(["B", "C"])]
    ]);

    const aNeighbors = graph.get("A");
    const bNeighbors = graph.get("B");

    printSet("A neighbors", aNeighbors);
    printSet("B neighbors", bNeighbors);
    printSet("shared neighbors", intersection(aNeighbors, bNeighbors));
    printSet("only A", difference(aNeighbors, bNeighbors));
    printSet("only B", difference(bNeighbors, aNeighbors));
}

function demonstrateTagMatching() {
    section("13. TAG MATCHING");

    const articleTags = new Set([
        "python",
        "algorithms",
        "security",
        "data-structures"
    ]);

    const requiredTags = new Set(["python", "security"]);
    const excludedTags = new Set(["advertising", "politics"]);

    const hasRequiredTags = isSubset(requiredTags, articleTags);
    const hasExcludedTags =
        intersection(articleTags, excludedTags).size > 0;

    console.log("has required tags:", hasRequiredTags);
    console.log("has excluded tags:", hasExcludedTags);
    console.log(
        "article accepted:",
        hasRequiredTags && !hasExcludedTags
    );
}

function demonstrateComplement() {
    section("14. COMPLEMENT RELATIVE TO A UNIVERSAL SET");

    const universal = new Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    const a = new Set([1, 2, 3, 4]);

    const complement = difference(universal, a);

    printSet("universal", universal);
    printSet("A", a);
    printSet("complement of A", complement);
}

function demonstrateDeMorganLaw() {
    section("15. DE MORGAN'S LAW");

    const universal = new Set([1, 2, 3, 4, 5, 6]);
    const a = new Set([1, 2, 3]);
    const b = new Set([3, 4]);

    const left = difference(universal, union(a, b));
    const right = intersection(
        difference(universal, a),
        difference(universal, b)
    );

    printSet("U - (A union B)", left);
    printSet("(U - A) intersection (U - B)", right);

    console.log("De Morgan identity holds:", isEqual(left, right));
}

function demonstrateValidation() {
    section("16. BUSINESS-RULE VALIDATION");

    function validateAccess(
        userPermissions,
        requiredPermissions,
        forbiddenPermissions
    ) {
        const missing = difference(
            requiredPermissions,
            userPermissions
        );

        const forbidden = intersection(
            userPermissions,
            forbiddenPermissions
        );

        return {
            valid: missing.size === 0 && forbidden.size === 0,
            missing,
            forbidden
        };
    }

    const result = validateAccess(
        new Set(["read", "write", "delete"]),
        new Set(["read", "write"]),
        new Set(["admin", "delete"])
    );

    console.log("valid:", result.valid);
    printSet("missing", result.missing);
    printSet("forbidden", result.forbidden);
}

function demonstrateInventory() {
    section("17. INVENTORY RECONCILIATION");

    const expected = new Set([
        "laptop",
        "monitor",
        "keyboard",
        "mouse",
        "dock"
    ]);

    const scanned = new Set([
        "laptop",
        "monitor",
        "keyboard",
        "dock",
        "headset"
    ]);

    printSet("confirmed", intersection(expected, scanned));
    printSet("missing", difference(expected, scanned));
    printSet("unexpected", difference(scanned, expected));
}

function demonstratePerformance() {
    section("18. PERFORMANCE CONSIDERATIONS");

    const size = 100000;
    const first = new Set();
    const second = new Set();

    for (let i = 0; i < size; i++) {
        first.add(i);
        second.add(i + size / 2);
    }

    const start = performance.now();
    const result = intersection(first, second);
    const elapsed = performance.now() - start;

    console.log("intersection size:", result.size);
    console.log(`intersection time: ${elapsed.toFixed(4)} ms`);

    /*
     * Set.has() is designed for efficient membership testing.
     * The exact performance depends on the JavaScript engine.
     * Whole-set operations require iteration over their operands.
     */
}

function demonstrateEdgeCases() {
    section("19. EDGE CASES");

    const empty = new Set();
    const values = new Set([1, 2, 3]);

    printSet("empty union values", union(empty, values));
    printSet("empty intersection values", intersection(empty, values));
    printSet("values minus empty", difference(values, empty));

    console.log("empty subset of values:", isSubset(empty, values));
    console.log("empty disjoint from values:", isDisjoint(empty, values));

    const strings = new Set(["a", "a", "b"]);
    printSet("duplicate strings removed", strings);
}

function demonstrateTesting() {
    section("20. TESTING");

    console.assert(
        isEqual(
            union(new Set([1, 2]), new Set([2, 3])),
            new Set([1, 2, 3])
        ),
        "Union test failed"
    );

    console.assert(
        isEqual(
            intersection(new Set([1, 2]), new Set([2, 3])),
            new Set([2])
        ),
        "Intersection test failed"
    );

    console.assert(
        isEqual(
            difference(new Set([1, 2]), new Set([2])),
            new Set([1])
        ),
        "Difference test failed"
    );

    console.assert(
        isEqual(
            symmetricDifference(
                new Set([1, 2]),
                new Set([2, 3])
            ),
            new Set([1, 3])
        ),
        "Symmetric difference test failed"
    );

    console.log("All assertions completed.");
}

function demonstrateAdvancedComposition() {
    section("21. ADVANCED SET COMPOSITION");

    const development = new Set([
        "python",
        "git",
        "linux",
        "docker",
        "sql"
    ]);

    const security = new Set([
        "linux",
        "python",
        "cryptography",
        "networking"
    ]);

    const cloud = new Set([
        "linux",
        "docker",
        "networking",
        "terraform"
    ]);

    printSet("all skills", union(development, security, cloud));
    printSet(
        "development/security overlap",
        intersection(development, security)
    );

    printSet(
        "development only",
        difference(development, security, cloud)
    );
}

function main() {
    demonstrateFundamentals();
    demonstrateMutation();
    demonstrateCoreOperations();
    demonstrateRelationships();
    demonstrateMultipleSets();
    demonstrateSetAlgebra();
    demonstrateSetConversion();
    demonstrateObjectIdentity();
    demonstrateNaNAndZero();
    demonstratePracticalFiltering();
    demonstratePermissions();
    demonstrateGraphRelationships();
    demonstrateTagMatching();
    demonstrateComplement();
    demonstrateDeMorganLaw();
    demonstrateValidation();
    demonstrateInventory();
    demonstratePerformance();
    demonstrateEdgeCases();
    demonstrateTesting();
    demonstrateAdvancedComposition();

    section("22. COMPLETION");
    console.log("Set operations study completed successfully.");
}

main();
