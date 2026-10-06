/**
 * Advanced Database Normalization: BCNF, 4NF, and 5NF
 *
 * Node.js 18+ / modern JavaScript.
 *
 * This program focuses on database-theory behavior rather than generic
 * JavaScript syntax. It models:
 *   - functional dependencies and candidate keys
 *   - BCNF violations and decomposition
 *   - multivalued dependencies and 4NF
 *   - join dependencies and 5NF
 *   - lossless reconstruction using concrete relation instances
 *   - normalization policy evaluation
 *
 * No external packages are required.
 */

"use strict";

class FunctionalDependency {
    constructor(determinant, dependent) {
        this.determinant = new Set(determinant);
        this.dependent = new Set(dependent);
    }

    toString() {
        return `${formatSet(this.determinant)} -> ${formatSet(this.dependent)}`;
    }
}

class MultivaluedDependency {
    constructor(determinant, dependent, relation) {
        this.determinant = new Set(determinant);
        this.dependent = new Set(dependent);
        this.relation = new Set(relation);
    }

    toString() {
        return `${formatSet(this.determinant)} ->> ${formatSet(this.dependent)} ` +
            `in ${formatSet(this.relation)}`;
    }
}

class JoinDependency {
    constructor(relation, components) {
        this.relation = new Set(relation);
        this.components = components.map(component => new Set(component));
    }

    toString() {
        const components = this.components
            .map(component => formatSet(component))
            .join(", ");
        return `*{${components}} on ${formatSet(this.relation)}`;
    }
}

class RelationSchema {
    constructor({
        name,
        attributes,
        functionalDependencies = [],
        multivaluedDependencies = [],
        joinDependencies = []
    }) {
        this.name = name;
        this.attributes = new Set(attributes);
        this.functionalDependencies = functionalDependencies;
        this.multivaluedDependencies = multivaluedDependencies;
        this.joinDependencies = joinDependencies;
    }
}

function formatSet(values) {
    return `{${[...values].sort().join(", ")}}`;
}

function cloneSet(values) {
    return new Set(values);
}

function setEquals(left, right) {
    if (left.size !== right.size) {
        return false;
    }

    for (const value of left) {
        if (!right.has(value)) {
            return false;
        }
    }

    return true;
}

function isSubset(subset, superset) {
    for (const value of subset) {
        if (!superset.has(value)) {
            return false;
        }
    }
    return true;
}

function union(...sets) {
    const result = new Set();

    for (const current of sets) {
        for (const value of current) {
            result.add(value);
        }
    }

    return result;
}

function difference(left, right) {
    const result = new Set();

    for (const value of left) {
        if (!right.has(value)) {
            result.add(value);
        }
    }

    return result;
}

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

function allSubsets(values) {
    const sorted = [...values].sort();
    const result = [];

    for (let size = 0; size <= sorted.length; size += 1) {
        result.push(...combinations(sorted, size).map(item => new Set(item)));
    }

    return result;
}

function attributeClosure(attributes, dependencies) {
    const closure = cloneSet(attributes);

    let changed = true;

    while (changed) {
        changed = false;

        for (const dependency of dependencies) {
            if (isSubset(dependency.determinant, closure)) {
                const before = closure.size;

                for (const attribute of dependency.dependent) {
                    closure.add(attribute);
                }

                if (closure.size !== before) {
                    changed = true;
                }
            }
        }
    }

    return closure;
}

function isSuperkey(attributes, relation, dependencies) {
    return setEquals(
        attributeClosure(attributes, dependencies),
        relation
    );
}

function candidateKeys(relation, dependencies) {
    const keys = [];

    for (const subset of allSubsets(relation)) {
        if (subset.size === 0) {
            continue;
        }

        if (!isSuperkey(subset, relation, dependencies)) {
            continue;
        }

        const containsExistingKey = keys.some(key =>
            isSubset(key, subset)
        );

        if (!containsExistingKey) {
            keys.push(subset);
        }
    }

    return keys;
}

function isTrivialDependency(dependency) {
    return isSubset(dependency.dependent, dependency.determinant);
}

function bcnfViolations(schema) {
    return schema.functionalDependencies.filter(dependency => {
        if (isTrivialDependency(dependency)) {
            return false;
        }

        return !isSuperkey(
            dependency.determinant,
            schema.attributes,
            schema.functionalDependencies
        );
    });
}

function projectDependencies(schema, attributes) {
    return schema.functionalDependencies.filter(dependency =>
        isSubset(
            union(dependency.determinant, dependency.dependent),
            attributes
        )
    );
}

function bcnfDecompose(schema) {
    const violations = bcnfViolations(schema);

    if (violations.length === 0) {
        return [schema];
    }

    const violation = violations[0];
    const x = violation.determinant;
    const y = violation.dependent;

    const firstAttributes = union(x, y);
    const secondAttributes = union(
        x,
        difference(schema.attributes, y)
    );

    const first = new RelationSchema({
        name: `${schema.name}_BCNF_A`,
        attributes: firstAttributes,
        functionalDependencies: projectDependencies(
            schema,
            firstAttributes
        )
    });

    const second = new RelationSchema({
        name: `${schema.name}_BCNF_B`,
        attributes: secondAttributes,
        functionalDependencies: projectDependencies(
            schema,
            secondAttributes
        )
    });

    return [
        ...bcnfDecompose(first),
        ...bcnfDecompose(second)
    ];
}

function isNonTrivialMVD(mvd) {
    const xUnionY = union(mvd.determinant, mvd.dependent);

    return (
        mvd.dependent.size > 0 &&
        !isSubset(mvd.dependent, mvd.determinant) &&
        !setEquals(xUnionY, mvd.relation)
    );
}

function fourNfViolations(schema) {
    const violations = [];

    for (const dependency of schema.functionalDependencies) {
        const mvd = new MultivaluedDependency(
            dependency.determinant,
            dependency.dependent,
            schema.attributes
        );

        if (
            isNonTrivialMVD(mvd) &&
            !isSuperkey(
                mvd.determinant,
                schema.attributes,
                schema.functionalDependencies
            )
        ) {
            violations.push(mvd);
        }
    }

    for (const mvd of schema.multivaluedDependencies) {
        if (
            isNonTrivialMVD(mvd) &&
            !isSuperkey(
                mvd.determinant,
                schema.attributes,
                schema.functionalDependencies
            )
        ) {
            violations.push(mvd);
        }
    }

    return violations;
}

function fourNfDecompose(schema, mvd) {
    const firstAttributes = union(
        mvd.determinant,
        mvd.dependent
    );

    const secondAttributes = union(
        mvd.determinant,
        difference(schema.attributes, mvd.dependent)
    );

    return [
        new RelationSchema({
            name: `${schema.name}_4NF_A`,
            attributes: firstAttributes
        }),
        new RelationSchema({
            name: `${schema.name}_4NF_B`,
            attributes: secondAttributes
        })
    ];
}

function rowKey(row) {
    return JSON.stringify(
        Object.entries(row).sort(([a], [b]) => a.localeCompare(b))
    );
}

function projectRows(rows, attributes) {
    const seen = new Map();

    for (const row of rows) {
        const projected = {};

        for (const attribute of attributes) {
            projected[attribute] = row[attribute];
        }

        seen.set(rowKey(projected), projected);
    }

    return [...seen.values()];
}

function naturalJoin(leftRows, rightRows) {
    const result = [];

    for (const left of leftRows) {
        for (const right of rightRows) {
            const commonAttributes = Object.keys(left)
                .filter(attribute =>
                    Object.prototype.hasOwnProperty.call(right, attribute)
                );

            const compatible = commonAttributes.every(attribute =>
                left[attribute] === right[attribute]
            );

            if (!compatible) {
                continue;
            }

            result.push({
                ...left,
                ...right
            });
        }
    }

    const unique = new Map();

    for (const row of result) {
        unique.set(rowKey(row), row);
    }

    return [...unique.values()];
}

function satisfiesFD(rows, dependency) {
    const determinant = [...dependency.determinant];
    const dependent = [...dependency.dependent];

    for (let leftIndex = 0; leftIndex < rows.length; leftIndex += 1) {
        for (
            let rightIndex = leftIndex + 1;
            rightIndex < rows.length;
            rightIndex += 1
        ) {
            const left = rows[leftIndex];
            const right = rows[rightIndex];

            const determinantMatches = determinant.every(
                attribute => left[attribute] === right[attribute]
            );

            if (!determinantMatches) {
                continue;
            }

            const dependentMatches = dependent.every(
                attribute => left[attribute] === right[attribute]
            );

            if (!dependentMatches) {
                return false;
            }
        }
    }

    return true;
}

function satisfiesMVD(rows, mvd) {
    const determinant = [...mvd.determinant];
    const dependent = [...mvd.dependent];
    const relation = [...mvd.relation];

    const other = relation.filter(
        attribute =>
            !mvd.determinant.has(attribute) &&
            !mvd.dependent.has(attribute)
    );

    const rowSet = new Set(rows.map(rowKey));

    for (let i = 0; i < rows.length; i += 1) {
        for (let j = i + 1; j < rows.length; j += 1) {
            const first = rows[i];
            const second = rows[j];

            const sameDeterminant = determinant.every(
                attribute => first[attribute] === second[attribute]
            );

            if (!sameDeterminant) {
                continue;
            }

            const firstCross = {};
            const secondCross = {};

            for (const attribute of relation) {
                if (mvd.determinant.has(attribute)) {
                    firstCross[attribute] = first[attribute];
                    secondCross[attribute] = first[attribute];
                } else if (mvd.dependent.has(attribute)) {
                    firstCross[attribute] = first[attribute];
                    secondCross[attribute] = second[attribute];
                } else if (other.includes(attribute)) {
                    firstCross[attribute] = second[attribute];
                    secondCross[attribute] = first[attribute];
                }
            }

            if (
                !rowSet.has(rowKey(firstCross)) ||
                !rowSet.has(rowKey(secondCross))
            ) {
                return false;
            }
        }
    }

    return true;
}

function describeSchema(schema) {
    console.log(`\nRelation: ${schema.name}`);
    console.log(`Attributes: ${formatSet(schema.attributes)}`);

    if (schema.functionalDependencies.length > 0) {
        console.log("Functional dependencies:");

        for (const dependency of schema.functionalDependencies) {
            console.log(`  ${dependency}`);
        }
    }

    if (schema.multivaluedDependencies.length > 0) {
        console.log("Multivalued dependencies:");

        for (const dependency of schema.multivaluedDependencies) {
            console.log(`  ${dependency}`);
        }
    }

    if (schema.joinDependencies.length > 0) {
        console.log("Join dependencies:");

        for (const dependency of schema.joinDependencies) {
            console.log(`  ${dependency}`);
        }
    }
}

function demonstrateBCNF() {
    console.log("\n=== BCNF Decomposition ===");

    const schema = new RelationSchema({
        name: "Teaching",
        attributes: [
            "Student",
            "Course",
            "Instructor",
            "InstructorOffice"
        ],
        functionalDependencies: [
            new FunctionalDependency(
                ["Student", "Course"],
                ["Instructor"]
            ),
            new FunctionalDependency(
                ["Instructor"],
                ["InstructorOffice"]
            )
        ]
    });

    describeSchema(schema);

    const keys = candidateKeys(
        schema.attributes,
        schema.functionalDependencies
    );

    console.log("Candidate keys:");

    for (const key of keys) {
        console.log(`  ${formatSet(key)}`);
    }

    console.log("BCNF violations:");

    for (const violation of bcnfViolations(schema)) {
        console.log(`  ${violation}`);
    }

    console.log("BCNF decomposition:");

    for (const relation of bcnfDecompose(schema)) {
        describeSchema(relation);
    }
}

function demonstrate4NF() {
    console.log("\n=== 4NF and Independent Multivalued Facts ===");

    const schema = new RelationSchema({
        name: "EmployeeProfile",
        attributes: [
            "Employee",
            "Skill",
            "Language"
        ],
        multivaluedDependencies: [
            new MultivaluedDependency(
                ["Employee"],
                ["Skill"],
                ["Employee", "Skill", "Language"]
            )
        ]
    });

    describeSchema(schema);

    const violations = fourNfViolations(schema);

    for (const violation of violations) {
        console.log(`4NF violation: ${violation}`);

        const decomposition = fourNfDecompose(
            schema,
            violation
        );

        console.log("4NF decomposition:");

        for (const relation of decomposition) {
            describeSchema(relation);
        }
    }

    const rows = [
        { Employee: "E1", Skill: "Python", Language: "English" },
        { Employee: "E1", Skill: "Python", Language: "French" },
        { Employee: "E1", Skill: "SQL", Language: "English" },
        { Employee: "E1", Skill: "SQL", Language: "French" }
    ];

    const skillRows = projectRows(
        rows,
        ["Employee", "Skill"]
    );

    const languageRows = projectRows(
        rows,
        ["Employee", "Language"]
    );

    const reconstructed = naturalJoin(
        skillRows,
        languageRows
    );

    console.log("Employee-Skill relation:");
    console.table(skillRows);

    console.log("Employee-Language relation:");
    console.table(languageRows);

    console.log("Natural join:");
    console.table(reconstructed);

    console.log(
        "The decomposed design stores the independent skill and language "
        + "sets without repeating every skill-language combination."
    );
}

function demonstrate5NF() {
    console.log("\n=== 5NF and Join Dependencies ===");

    const schema = new RelationSchema({
        name: "SupplierPartProject",
        attributes: [
            "Supplier",
            "Part",
            "Project"
        ],
        joinDependencies: [
            new JoinDependency(
                ["Supplier", "Part", "Project"],
                [
                    ["Supplier", "Part"],
                    ["Supplier", "Project"],
                    ["Part", "Project"]
                ]
            )
        ]
    });

    describeSchema(schema);

    const supplierPart = [
        { Supplier: "S1", Part: "P1" },
        { Supplier: "S1", Part: "P2" }
    ];

    const supplierProject = [
        { Supplier: "S1", Project: "J1" }
    ];

    const partProject = [
        { Part: "P1", Project: "J1" },
        { Part: "P2", Project: "J1" }
    ];

    const reconstructed = naturalJoin(
        naturalJoin(supplierPart, supplierProject),
        partProject
    );

    console.log("Supplier-Part:");
    console.table(supplierPart);

    console.log("Supplier-Project:");
    console.table(supplierProject);

    console.log("Part-Project:");
    console.table(partProject);

    console.log("Three-way join reconstruction:");
    console.table(reconstructed);

    console.log(
        "5NF decomposition is justified only when the business semantics "
        + "actually imply the relevant join dependency. Splitting every "
        + "ternary relation into pairwise relations can introduce spurious "
        + "combinations when that semantic condition is absent."
    );
}

function demonstrateFDInstance() {
    console.log("\n=== Functional Dependency Instance Check ===");

    const dependency = new FunctionalDependency(
        ["Student", "Course"],
        ["Grade"]
    );

    const valid = [
        { Student: "S1", Course: "DB", Grade: "A" },
        { Student: "S1", Course: "OS", Grade: "B" },
        { Student: "S2", Course: "DB", Grade: "A" }
    ];

    const invalid = [
        { Student: "S1", Course: "DB", Grade: "A" },
        { Student: "S1", Course: "DB", Grade: "C" }
    ];

    console.log(
        "Valid relation satisfies FD:",
        satisfiesFD(valid, dependency)
    );

    console.log(
        "Invalid relation satisfies FD:",
        satisfiesFD(invalid, dependency)
    );
}

function demonstrateMVDInstance() {
    console.log("\n=== Multivalued Dependency Instance Check ===");

    const mvd = new MultivaluedDependency(
        ["Employee"],
        ["Skill"],
        ["Employee", "Skill", "Language"]
    );

    const complete = [
        { Employee: "E1", Skill: "Python", Language: "English" },
        { Employee: "E1", Skill: "Python", Language: "French" },
        { Employee: "E1", Skill: "SQL", Language: "English" },
        { Employee: "E1", Skill: "SQL", Language: "French" }
    ];

    const incomplete = [
        { Employee: "E1", Skill: "Python", Language: "English" },
        { Employee: "E1", Skill: "SQL", Language: "French" }
    ];

    console.log(
        "Complete cross-product satisfies MVD:",
        satisfiesMVD(complete, mvd)
    );

    console.log(
        "Incomplete cross-product satisfies MVD:",
        satisfiesMVD(incomplete, mvd)
    );
}

function normalizationAdvisor(schema) {
    const keys = candidateKeys(
        schema.attributes,
        schema.functionalDependencies
    );

    const bcnf = bcnfViolations(schema);
    const fourNf = fourNfViolations(schema);

    return {
        relation: schema.name,
        candidateKeys: keys.map(formatSet),
        bcnfCompliant: bcnf.length === 0,
        bcnfViolations: bcnf.map(String),
        fourNfCompliant: fourNf.length === 0,
        fourNfViolations: fourNf.map(String),
        joinDependencies: schema.joinDependencies.map(String)
    };
}

function main() {
    console.log("=".repeat(72));
    console.log("ADVANCED NORMALIZATION: BCNF, 4NF, AND 5NF");
    console.log("=".repeat(72));

    demonstrateBCNF();
    demonstrate4NF();
    demonstrate5NF();
    demonstrateFDInstance();
    demonstrateMVDInstance();

    console.log("\n=== Normalization Policy Evaluation ===");

    const schema = new RelationSchema({
        name: "EmployeeSkillLanguage",
        attributes: [
            "Employee",
            "Skill",
            "Language"
        ],
        multivaluedDependencies: [
            new MultivaluedDependency(
                ["Employee"],
                ["Skill"],
                ["Employee", "Skill", "Language"]
            )
        ]
    });

    console.dir(
        normalizationAdvisor(schema),
        { depth: null }
    );

    console.log("\n=== Practical Distinction ===");
    console.log(
        "BCNF controls non-trivial functional dependencies whose determinants "
        + "are not superkeys."
    );
    console.log(
        "4NF controls non-trivial multivalued dependencies whose determinants "
        + "are not superkeys."
    );
    console.log(
        "5NF controls non-trivial join dependencies that remain after the "
        + "constraints addressed by lower normal forms."
    );
}

main();
