/**
 * Normalization I: Functional Dependencies and Anomalies
 *
 * This Node.js program models functional dependencies, attribute closure,
 * candidate keys, anomaly detection, dependency classification, and a
 * normalization-oriented decomposition.
 *
 * Run with:
 *     node normalization_functional_dependencies.js
 */

"use strict";

// ---------------------------------------------------------------------------
// Functional dependency primitives
// ---------------------------------------------------------------------------

function makeFD(determinant, dependent) {
    if (!determinant.length) {
        throw new Error("A functional dependency needs a determinant.");
    }
    if (!dependent.length) {
        throw new Error("A functional dependency needs dependent attributes.");
    }

    return {
        determinant: new Set(determinant),
        dependent: new Set(dependent),
    };
}

function formatSet(values) {
    return `{${[...values].sort().join(", ")}}`;
}

function formatFD(dependency) {
    return `${formatSet(dependency.determinant)} -> ${formatSet(
        dependency.dependent
    )}`;
}

// ---------------------------------------------------------------------------
// Attribute closure
// ---------------------------------------------------------------------------

function attributeClosure(attributes, dependencies) {
    /*
     * X+ begins with X. Every dependency whose determinant is already
     * contained in the closure contributes its dependent attributes.
     * The process stops at a fixed point.
     */
    const closure = new Set(attributes);

    let changed = true;
    while (changed) {
        changed = false;

        for (const dependency of dependencies) {
            const determinantSatisfied = [...dependency.determinant].every(
                (attribute) => closure.has(attribute)
            );

            if (!determinantSatisfied) {
                continue;
            }

            for (const attribute of dependency.dependent) {
                if (!closure.has(attribute)) {
                    closure.add(attribute);
                    changed = true;
                }
            }
        }
    }

    return closure;
}

function implies(determinant, dependent, dependencies) {
    const closure = attributeClosure(determinant, dependencies);
    return dependent.every((attribute) => closure.has(attribute));
}

function isSuperkey(attributes, relationAttributes, dependencies) {
    const closure = attributeClosure(attributes, dependencies);
    return relationAttributes.every((attribute) => closure.has(attribute));
}

// ---------------------------------------------------------------------------
// Candidate-key enumeration
// ---------------------------------------------------------------------------

function combinations(values, size) {
    const result = [];

    function build(start, current) {
        if (current.length === size) {
            result.push([...current]);
            return;
        }

        for (let index = start; index < values.length; index += 1) {
            current.push(values[index]);
            build(index + 1, current);
            current.pop();
        }
    }

    build(0, []);
    return result;
}

function isSubset(left, right) {
    return [...left].every((value) => right.has(value));
}

function candidateKeys(relationAttributes, dependencies) {
    /*
     * Exhaustive enumeration is useful for a compact educational model.
     * It has exponential worst-case behavior, so real database tooling uses
     * more specialized algorithms for large schemas.
     */
    const attributes = [...new Set(relationAttributes)].sort();
    const keys = [];

    for (let size = 1; size <= attributes.length; size += 1) {
        for (const combination of combinations(attributes, size)) {
            const candidate = new Set(combination);

            if (!isSuperkey(combination, attributes, dependencies)) {
                continue;
            }

            if (keys.some((key) => isSubset(key, candidate))) {
                continue;
            }

            keys.push(candidate);
        }
    }

    return keys;
}

// ---------------------------------------------------------------------------
// Relation and anomaly model
// ---------------------------------------------------------------------------

class Relation {
    constructor(name, columns, rows = []) {
        this.name = name;
        this.columns = [...columns];
        this.rows = rows.map((row) => ({ ...row }));
        this.validate();
    }

    validate() {
        const expected = new Set(this.columns);

        this.rows.forEach((row, rowIndex) => {
            const actual = new Set(Object.keys(row));

            const missing = this.columns.filter((column) => !actual.has(column));
            const extra = [...actual].filter((column) => !expected.has(column));

            if (missing.length || extra.length) {
                throw new Error(
                    `${this.name} row ${rowIndex + 1} has invalid columns. ` +
                    `Missing=${missing.join(",")}; Extra=${extra.join(",")}`
                );
            }
        });
    }

    insert(row) {
        const expected = new Set(this.columns);
        const actual = new Set(Object.keys(row));

        if (
            actual.size !== expected.size ||
            [...expected].some((column) => !actual.has(column))
        ) {
            throw new Error(`Incomplete tuple supplied to ${this.name}.`);
        }

        this.rows.push({ ...row });
    }

    update(predicate, changes) {
        for (const column of Object.keys(changes)) {
            if (!this.columns.includes(column)) {
                throw new Error(`Unknown column: ${column}`);
            }
        }

        let count = 0;

        for (const row of this.rows) {
            if (predicate(row)) {
                Object.assign(row, changes);
                count += 1;
            }
        }

        return count;
    }

    deleteWhere(predicate) {
        const removed = [];
        const retained = [];

        for (const row of this.rows) {
            if (predicate(row)) {
                removed.push(row);
            } else {
                retained.push(row);
            }
        }

        this.rows = retained;
        return removed;
    }

    display(title = this.name) {
        console.log(`\n${title}`);

        if (!this.rows.length) {
            console.log("(empty)");
            return;
        }

        const widths = Object.fromEntries(
            this.columns.map((column) => [
                column,
                Math.max(
                    column.length,
                    ...this.rows.map((row) => String(row[column]).length)
                ),
            ])
        );

        const line = this.columns
            .map((column) => "-".repeat(widths[column]))
            .join("-+-");

        console.log(
            this.columns
                .map((column) => column.padEnd(widths[column]))
                .join(" | ")
        );
        console.log(line);

        for (const row of this.rows) {
            console.log(
                this.columns
                    .map((column) => String(row[column]).padEnd(widths[column]))
                    .join(" | ")
            );
        }
    }
}

function findFDViolations(relation, dependency) {
    const violations = [];

    for (let first = 0; first < relation.rows.length; first += 1) {
        for (let second = first + 1; second < relation.rows.length; second += 1) {
            const left = relation.rows[first];
            const right = relation.rows[second];

            const sameDeterminant = [...dependency.determinant].every(
                (attribute) => left[attribute] === right[attribute]
            );

            const differentDependent = [...dependency.dependent].some(
                (attribute) => left[attribute] !== right[attribute]
            );

            if (sameDeterminant && differentDependent) {
                violations.push([left, right]);
            }
        }
    }

    return violations;
}

// ---------------------------------------------------------------------------
// Event-driven Pull-Request-style state changes are intentionally not used.
// This file focuses specifically on relational normalization.
// ---------------------------------------------------------------------------

function demonstrateUpdateAnomaly() {
    const employeeDepartment = new Relation(
        "EmployeeDepartment",
        ["employee_id", "employee_name", "department", "department_location"],
        [
            {
                employee_id: "E101",
                employee_name: "Anita",
                department: "Finance",
                department_location: "Mumbai",
            },
            {
                employee_id: "E102",
                employee_name: "Rahul",
                department: "Finance",
                department_location: "Mumbai",
            },
            {
                employee_id: "E103",
                employee_name: "Meera",
                department: "HR",
                department_location: "Delhi",
            },
        ]
    );

    employeeDepartment.display("Update anomaly: initial state");

    employeeDepartment.update(
        (row) => row.employee_id === "E101",
        { department_location: "Pune" }
    );

    employeeDepartment.display(
        "Update anomaly: one duplicate fact changed but another did not"
    );

    const dependency = makeFD(
        ["department"],
        ["department_location"]
    );

    console.log(
        `\n${formatFD(dependency)} violations:`,
        findFDViolations(employeeDepartment, dependency).length
    );
}

function demonstrateInsertionAnomaly() {
    const enrollment = new Relation(
        "StudentCourse",
        ["student_id", "student_name", "course_id", "course_name", "instructor"],
        [
            {
                student_id: "S1",
                student_name: "Asha",
                course_id: "DB101",
                course_name: "Database Systems",
                instructor: "Dr. Rao",
            },
        ]
    );

    enrollment.display("Insertion anomaly");

    console.log(
        "\nA new course with no enrolled students has no natural tuple in " +
        "this relation. Storing it would require inventing an enrollment " +
        "or allowing an artificial NULL-based row."
    );
}

function demonstrateDeletionAnomaly() {
    const enrollment = new Relation(
        "StudentCourse",
        ["student_id", "student_name", "course_id", "course_name", "instructor"],
        [
            {
                student_id: "S1",
                student_name: "Asha",
                course_id: "DB101",
                course_name: "Database Systems",
                instructor: "Dr. Rao",
            },
            {
                student_id: "S2",
                student_name: "Kabir",
                course_id: "DB101",
                course_name: "Database Systems",
                instructor: "Dr. Rao",
            },
        ]
    );

    enrollment.deleteWhere((row) => row.student_id === "S1");
    enrollment.deleteWhere((row) => row.student_id === "S2");

    enrollment.display(
        "Deletion anomaly: deleting the final enrollment removed the course fact"
    );
}

// ---------------------------------------------------------------------------
// Dependency analysis
// ---------------------------------------------------------------------------

function demonstrateDependencyAnalysis() {
    const attributes = [
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
    ];

    const dependencies = [
        makeFD(["student_id"], ["student_name", "student_program"]),
        makeFD(["course_id"], ["course_name", "department"]),
        makeFD(["instructor_id"], ["instructor_name"]),
        makeFD(
            ["course_id", "section_no", "term"],
            ["instructor_id"]
        ),
        makeFD(
            ["student_id", "course_id", "section_no", "term"],
            ["grade"]
        ),
    ];

    console.log("\nFunctional dependencies");

    for (const dependency of dependencies) {
        console.log(`  ${formatFD(dependency)}`);
    }

    console.log("\nClosures");

    const closureInputs = [
        ["student_id"],
        ["course_id"],
        ["course_id", "section_no", "term"],
        ["student_id", "course_id", "section_no", "term"],
    ];

    for (const input of closureInputs) {
        const closure = attributeClosure(input, dependencies);
        console.log(`  ${formatSet(input)}+ = ${formatSet(closure)}`);
    }

    const keys = candidateKeys(attributes, dependencies);

    console.log("\nCandidate keys");

    for (const key of keys) {
        console.log(`  ${formatSet(key)}`);
    }

    const primeAttributes = new Set(keys.flatMap((key) => [...key]));

    console.log(
        `\nPrime attributes: ${formatSet(primeAttributes)}`
    );

    console.log("\nDependency implication");

    const checks = [
        [["student_id"], ["student_name"]],
        [
            ["student_id", "course_id", "section_no", "term"],
            ["instructor_name"],
        ],
        [["course_id"], ["instructor_id"]],
    ];

    for (const [left, right] of checks) {
        console.log(
            `  ${formatSet(left)} -> ${formatSet(right)}: ` +
            `${implies(left, right, dependencies) ? "implied" : "not implied"}`
        );
    }
}

// ---------------------------------------------------------------------------
// Decomposition
// ---------------------------------------------------------------------------

function project(relation, columns, name) {
    const seen = new Set();
    const rows = [];

    for (const row of relation.rows) {
        const values = columns.map((column) => row[column]);
        const identity = JSON.stringify(values);

        if (!seen.has(identity)) {
            seen.add(identity);
            rows.push(
                Object.fromEntries(
                    columns.map((column, index) => [column, values[index]])
                )
            );
        }
    }

    return new Relation(name, columns, rows);
}

function demonstrateDecomposition() {
    const source = new Relation(
        "EnrollmentRecord",
        [
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
        ],
        [
            {
                student_id: "S1",
                student_name: "Asha",
                student_program: "MCA",
                course_id: "DB101",
                course_name: "Database Systems",
                department: "Computer Science",
                section_no: "A",
                term: "2026-Fall",
                instructor_id: "I7",
                instructor_name: "Dr. Rao",
                grade: "A",
            },
            {
                student_id: "S2",
                student_name: "Kabir",
                student_program: "MBA",
                course_id: "DB101",
                course_name: "Database Systems",
                department: "Computer Science",
                section_no: "A",
                term: "2026-Fall",
                instructor_id: "I7",
                instructor_name: "Dr. Rao",
                grade: "B+",
            },
            {
                student_id: "S1",
                student_name: "Asha",
                student_program: "MCA",
                course_id: "AI201",
                course_name: "Machine Learning",
                department: "Computer Science",
                section_no: "B",
                term: "2026-Fall",
                instructor_id: "I9",
                instructor_name: "Dr. Sen",
                grade: "A-",
            },
        ]
    );

    const normalizedRelations = [
        project(
            source,
            ["student_id", "student_name", "student_program"],
            "Student"
        ),
        project(
            source,
            ["course_id", "course_name", "department"],
            "Course"
        ),
        project(
            source,
            ["instructor_id", "instructor_name"],
            "Instructor"
        ),
        project(
            source,
            ["course_id", "section_no", "term", "instructor_id"],
            "Section"
        ),
        project(
            source,
            ["student_id", "course_id", "section_no", "term", "grade"],
            "Enrollment"
        ),
    ];

    for (const relation of normalizedRelations) {
        relation.display(`Normalized relation: ${relation.name}`);
    }
}

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

function demonstrateEdgeCases() {
    console.log("\nEdge cases");

    try {
        makeFD([], ["name"]);
    } catch (error) {
        console.log(`  Empty determinant rejected: ${error.message}`);
    }

    try {
        makeFD(["id"], []);
    } catch (error) {
        console.log(`  Empty dependent set rejected: ${error.message}`);
    }

    const employee = new Relation(
        "Employee",
        ["employee_id", "name"],
        [
            { employee_id: "E1", name: "Asha" },
            { employee_id: "E2", name: "Kabir" },
        ]
    );

    const dependency = makeFD(["employee_id"], ["name"]);

    console.log(
        `  ${formatFD(dependency)} violations: ` +
        findFDViolations(employee, dependency).length
    );

    console.log(
        "  Absence of a violation in a sample does not establish that an " +
        "FD is semantically valid. Functional dependencies are business or " +
        "domain rules about all legal database states."
    );
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
    console.log("=".repeat(78));
    console.log("NORMALIZATION I: FUNCTIONAL DEPENDENCIES AND ANOMALIES");
    console.log("=".repeat(78));

    demonstrateUpdateAnomaly();
    demonstrateInsertionAnomaly();
    demonstrateDeletionAnomaly();
    demonstrateDependencyAnalysis();
    demonstrateDecomposition();
    demonstrateEdgeCases();

    console.log("\nThe central relationship is:");
    console.log(
        "functional dependencies describe which facts determine other facts; " +
        "normalization uses those dependencies to reduce redundancy and " +
        "prevent insertion, update, and deletion anomalies."
    );
}

main();
