```javascript
/*
 * SQL Joins II: FULL JOIN, CROSS JOIN, and SELF JOIN
 *
 * This file is executable with Node.js and demonstrates SQL join concepts
 * through an in-memory relational model implemented with plain JavaScript.
 *
 * No external npm package is required.
 *
 * The examples intentionally model SQL semantics so that the JavaScript
 * implementation can complement the database-oriented Python implementation.
 */

"use strict";

// ---------------------------------------------------------------------------
// General-purpose helpers
// ---------------------------------------------------------------------------

function printTitle(title) {
    console.log("\n" + "=".repeat(78));
    console.log(title);
    console.log("=".repeat(78));
}

function printRows(rows, columns) {
    if (rows.length === 0) {
        console.log("(no rows)");
        return;
    }

    console.log(columns.join(" | "));
    console.log("-".repeat(78));

    for (const row of rows) {
        console.log(
            columns
                .map((column) => row[column] === null || row[column] === undefined
                    ? "NULL"
                    : String(row[column]))
                .join(" | ")
        );
    }
}

function assert(condition, message) {
    if (!condition) {
        throw new Error("Assertion failed: " + message);
    }
}


// ---------------------------------------------------------------------------
// Dataset
// ---------------------------------------------------------------------------

const departments = [
    { departmentId: 10, departmentName: "Engineering" },
    { departmentId: 20, departmentName: "Finance" },
    { departmentId: 30, departmentName: "Security" },
    { departmentId: 40, departmentName: "Research" },
    { departmentId: 50, departmentName: "Legal" }
];

const employees = [
    { employeeId: 1, employeeName: "Asha", managerId: null, departmentId: 10, salary: 125000 },
    { employeeId: 2, employeeName: "Bharat", managerId: 1, departmentId: 10, salary: 95000 },
    { employeeId: 3, employeeName: "Chen", managerId: 1, departmentId: 10, salary: 98000 },
    { employeeId: 4, employeeName: "Divya", managerId: null, departmentId: 20, salary: 110000 },
    { employeeId: 5, employeeName: "Ethan", managerId: 4, departmentId: 20, salary: 88000 },
    { employeeId: 6, employeeName: "Fatima", managerId: null, departmentId: 30, salary: 118000 },
    { employeeId: 7, employeeName: "Gopal", managerId: 6, departmentId: 30, salary: 90000 },
    { employeeId: 8, employeeName: "Hina", managerId: null, departmentId: null, salary: 76000 }
];

const projects = [
    { projectId: 100, projectName: "Payment Platform", departmentId: 10 },
    { projectId: 200, projectName: "Audit Automation", departmentId: 20 },
    { projectId: 300, projectName: "Threat Detection", departmentId: 30 },
    { projectId: 400, projectName: "Independent Research", departmentId: 40 }
];

const employeeProjects = [
    { employeeId: 1, projectId: 100, allocationPercent: 50 },
    { employeeId: 2, projectId: 100, allocationPercent: 100 },
    { employeeId: 4, projectId: 200, allocationPercent: 60 },
    { employeeId: 6, projectId: 300, allocationPercent: 70 },
    { employeeId: 7, projectId: 300, allocationPercent: 30 }
];


// ---------------------------------------------------------------------------
// INNER JOIN
// ---------------------------------------------------------------------------

function innerJoin(leftRows, rightRows, predicate, projector) {
    const result = [];

    for (const left of leftRows) {
        for (const right of rightRows) {
            if (predicate(left, right)) {
                result.push(projector(left, right));
            }
        }
    }

    return result;
}

function demonstrateInnerJoin() {
    const result = innerJoin(
        employees,
        departments,
        (employee, department) =>
            employee.departmentId === department.departmentId,
        (employee, department) => ({
            employee: employee.employeeName,
            department: department.departmentName
        })
    );

    printTitle("INNER JOIN");
    printRows(result, ["employee", "department"]);

    console.log(
        "\nOnly employee/department pairs satisfying the equality predicate " +
        "are returned."
    );
}


// ---------------------------------------------------------------------------
// LEFT JOIN
// ---------------------------------------------------------------------------

function leftJoin(leftRows, rightRows, predicate, projector) {
    const result = [];

    for (const left of leftRows) {
        let matched = false;

        for (const right of rightRows) {
            if (predicate(left, right)) {
                matched = true;
                result.push(projector(left, right));
            }
        }

        // SQL LEFT JOIN creates a NULL-extended row when no right row matches.
        if (!matched) {
            result.push(projector(left, null));
        }
    }

    return result;
}

function demonstrateLeftJoin() {
    const result = leftJoin(
        departments,
        employees,
        (department, employee) =>
            employee !== null &&
            department.departmentId === employee.departmentId,
        (department, employee) => ({
            department: department.departmentName,
            employee: employee ? employee.employeeName : null
        })
    );

    printTitle("LEFT JOIN");
    printRows(result, ["department", "employee"]);

    console.log(
        "\nResearch and Legal remain visible because the left side is preserved."
    );
}


// ---------------------------------------------------------------------------
// FULL OUTER JOIN
// ---------------------------------------------------------------------------

function fullOuterJoin(leftRows, rightRows, predicate, projector) {
    const result = [];
    const matchedRightIndexes = new Set();

    for (const left of leftRows) {
        let matched = false;

        for (let index = 0; index < rightRows.length; index += 1) {
            const right = rightRows[index];

            if (predicate(left, right)) {
                matched = true;
                matchedRightIndexes.add(index);
                result.push(projector(left, right));
            }
        }

        if (!matched) {
            result.push(projector(left, null));
        }
    }

    // Any right row not matched by a left row is right-only.
    for (let index = 0; index < rightRows.length; index += 1) {
        if (!matchedRightIndexes.has(index)) {
            result.push(projector(null, rightRows[index]));
        }
    }

    return result;
}

function demonstrateFullOuterJoin() {
    const result = fullOuterJoin(
        departments,
        employees,
        (department, employee) =>
            department !== null &&
            employee !== null &&
            department.departmentId === employee.departmentId,
        (department, employee) => ({
            department: department ? department.departmentName : null,
            employee: employee ? employee.employeeName : null,
            status:
                department === null
                    ? "employee_without_department"
                    : employee === null
                        ? "department_without_employee"
                        : "matched"
        })
    );

    printTitle("FULL OUTER JOIN");
    printRows(result, ["department", "employee", "status"]);

    console.log(
        "\nA FULL OUTER JOIN preserves unmatched rows from both inputs."
    );
}


// ---------------------------------------------------------------------------
// CROSS JOIN
// ---------------------------------------------------------------------------

function crossJoin(leftRows, rightRows, projector) {
    const result = [];

    // Every left row is intentionally paired with every right row.
    for (const left of leftRows) {
        for (const right of rightRows) {
            result.push(projector(left, right));
        }
    }

    return result;
}

function demonstrateCrossJoin() {
    const selectedEmployees = employees.slice(0, 2);

    const result = crossJoin(
        selectedEmployees,
        projects,
        (employee, project) => ({
            employee: employee.employeeName,
            project: project.projectName
        })
    );

    printTitle("CROSS JOIN");
    printRows(result, ["employee", "project"]);

    assert(
        result.length === selectedEmployees.length * projects.length,
        "Cartesian product cardinality should be m × n."
    );

    console.log(
        `\n${selectedEmployees.length} employees × ` +
        `${projects.length} projects = ${result.length} combinations.`
    );
}


// ---------------------------------------------------------------------------
// SELF JOIN
// ---------------------------------------------------------------------------

function demonstrateSelfJoinHierarchy() {
    // The same employees array is used twice.
    // One logical role represents the employee and the other represents
    // that employee's manager.
    const result = leftJoin(
        employees,
        employees,
        (employee, manager) =>
            manager !== null &&
            employee.managerId === manager.employeeId,
        (employee, manager) => ({
            employee: employee.employeeName,
            manager: manager ? manager.employeeName : null
        })
    );

    printTitle("SELF JOIN: EMPLOYEE -> MANAGER");
    printRows(result, ["employee", "manager"]);
}

function demonstrateSelfJoinPeers() {
    const result = [];

    for (const employeeA of employees) {
        for (const employeeB of employees) {
            // The inequality prevents A-B and B-A duplicates and also
            // prevents A-A self-pairs.
            if (
                employeeA.employeeId < employeeB.employeeId &&
                employeeA.departmentId !== null &&
                employeeA.departmentId === employeeB.departmentId
            ) {
                result.push({
                    employeeA: employeeA.employeeName,
                    employeeB: employeeB.employeeName,
                    departmentId: employeeA.departmentId
                });
            }
        }
    }

    printTitle("SELF JOIN: EMPLOYEE PEER PAIRS");
    printRows(result, ["employeeA", "employeeB", "departmentId"]);
}


// ---------------------------------------------------------------------------
// FULL JOIN reconciliation
// ---------------------------------------------------------------------------

const customers = [
    { customerId: 1, customerName: "Alpha" },
    { customerId: 2, customerName: "Beta" },
    { customerId: 3, customerName: "Gamma" },
    { customerId: 4, customerName: "Delta" }
];

const orders = [
    { orderId: 101, customerId: 1, amount: 500 },
    { orderId: 102, customerId: 1, amount: 250 },
    { orderId: 103, customerId: 2, amount: 900 },
    { orderId: 104, customerId: null, amount: 120 }
];

function demonstrateReconciliation() {
    const result = fullOuterJoin(
        customers,
        orders,
        (customer, order) =>
            customer !== null &&
            order !== null &&
            customer.customerId === order.customerId,
        (customer, order) => ({
            customer: customer ? customer.customerName : null,
            orderId: order ? order.orderId : null,
            amount: order ? order.amount : null,
            status:
                customer === null
                    ? "orphan_order"
                    : order === null
                        ? "customer_without_order"
                        : "matched"
        })
    );

    printTitle("FULL JOIN RECONCILIATION");
    printRows(result, ["customer", "orderId", "amount", "status"]);
}


// ---------------------------------------------------------------------------
// Many-to-many relationship
// ---------------------------------------------------------------------------

function demonstrateManyToMany() {
    const employeeProjectRows = innerJoin(
        employeeProjects,
        employees,
        (assignment, employee) =>
            assignment.employeeId === employee.employeeId,
        (assignment, employee) => ({
            employeeId: employee.employeeId,
            employeeName: employee.employeeName,
            projectId: assignment.projectId,
            allocationPercent: assignment.allocationPercent
        })
    );

    const result = innerJoin(
        employeeProjectRows,
        projects,
        (assignment, project) =>
            assignment.projectId === project.projectId,
        (assignment, project) => ({
            employee: assignment.employeeName,
            project: project.projectName,
            allocationPercent: assignment.allocationPercent
        })
    );

    printTitle("MANY-TO-MANY JOIN THROUGH A JUNCTION TABLE");
    printRows(result, ["employee", "project", "allocationPercent"]);
}


// ---------------------------------------------------------------------------
// Aggregation after a LEFT JOIN
// ---------------------------------------------------------------------------

function demonstrateAggregation() {
    const joined = leftJoin(
        departments,
        employees,
        (department, employee) =>
            employee !== null &&
            department.departmentId === employee.departmentId,
        (department, employee) => ({
            departmentId: department.departmentId,
            departmentName: department.departmentName,
            employee: employee
        })
    );

    const grouped = new Map();

    for (const row of joined) {
        if (!grouped.has(row.departmentId)) {
            grouped.set(row.departmentId, {
                department: row.departmentName,
                salaries: [],
                employeeCount: 0
            });
        }

        const group = grouped.get(row.departmentId);

        if (row.employee !== null) {
            group.salaries.push(row.employee.salary);
            group.employeeCount += 1;
        }
    }

    const result = [...grouped.values()].map((group) => ({
        department: group.department,
        employeeCount: group.employeeCount,
        averageSalary:
            group.salaries.length === 0
                ? 0
                : group.salaries.reduce((sum, salary) => sum + salary, 0) /
                  group.salaries.length
    }));

    printTitle("LEFT JOIN + GROUPING");
    printRows(result, ["department", "employeeCount", "averageSalary"]);

    console.log(
        "\nThe JavaScript model explicitly ignores NULL-extended employee " +
        "objects when calculating the average."
    );
}


// ---------------------------------------------------------------------------
// EXISTS / NOT EXISTS conceptual equivalents
// ---------------------------------------------------------------------------

function demonstrateSemiAndAntiJoin() {
    const departmentsWithEmployees = departments.filter((department) =>
        employees.some(
            (employee) => employee.departmentId === department.departmentId
        )
    );

    const departmentsWithoutEmployees = departments.filter((department) =>
        !employees.some(
            (employee) => employee.departmentId === department.departmentId
        )
    );

    printTitle("SEMI-JOIN AND ANTI-JOIN PATTERNS");

    console.log(
        "Departments with employees:",
        departmentsWithEmployees.map((department) => department.departmentName)
    );

    console.log(
        "Departments without employees:",
        departmentsWithoutEmployees.map((department) => department.departmentName)
    );

    console.log(
        "\nArray.some() corresponds conceptually to SQL EXISTS."
    );
}


// ---------------------------------------------------------------------------
// NULL semantics
// ---------------------------------------------------------------------------

function demonstrateNullSemantics() {
    printTitle("NULL SEMANTICS");

    console.log("null === null in JavaScript:", null === null);
    console.log(
        "SQL comparison differs: NULL = NULL is UNKNOWN, not TRUE."
    );

    console.log(
        "SQL requires IS NULL for testing whether a value is NULL."
    );
}


// ---------------------------------------------------------------------------
// Join cardinality and accidental Cartesian products
// ---------------------------------------------------------------------------

function demonstrateCardinality() {
    const m = employees.length;
    const n = projects.length;

    console.log(
        `\nCartesian product upper bound: ${m} × ${n} = ${m * n} rows`
    );

    console.log(
        "A missing join predicate can therefore produce unexpectedly large output."
    );
}


// ---------------------------------------------------------------------------
// Complexity demonstration
// ---------------------------------------------------------------------------

function compareNaiveAndIndexedJoin() {
    /*
     * The simple nested-loop join is easy to understand but can require
     * O(m × n) predicate checks.
     *
     * Building a Map on the join key allows indexed lookup and commonly
     * reduces the matching phase toward O(m + n) for equality joins.
     */

    const departmentById = new Map(
        departments.map((department) => [
            department.departmentId,
            department
        ])
    );

    const result = employees.map((employee) => {
        const department = departmentById.get(employee.departmentId);

        return {
            employee: employee.employeeName,
            department: department ? department.departmentName : null
        };
    });

    printTitle("INDEXED EQUALITY JOIN CONCEPT");
    printRows(result, ["employee", "department"]);

    console.log(
        "\nMap-based lookup is conceptually similar to having an index " +
        "supporting an equality lookup."
    );
}


// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function validateData() {
    const departmentIds = new Set();

    for (const department of departments) {
        if (departmentIds.has(department.departmentId)) {
            throw new Error("Duplicate department ID.");
        }

        departmentIds.add(department.departmentId);

        if (!department.departmentName.trim()) {
            throw new Error("Department name cannot be empty.");
        }
    }

    for (const employee of employees) {
        if (employee.salary < 0) {
            throw new Error("Salary cannot be negative.");
        }

        if (
            employee.departmentId !== null &&
            !departmentIds.has(employee.departmentId)
        ) {
            throw new Error(
                `Employee ${employee.employeeId} references an unknown department.`
            );
        }
    }
}


// ---------------------------------------------------------------------------
// Production-oriented considerations
// ---------------------------------------------------------------------------

function printProductionConsiderations() {
    printTitle("PRODUCTION CONSIDERATIONS");

    console.log(`
1. Define the relationship and expected cardinality before joining.
2. Use explicit JOIN predicates.
3. Treat CROSS JOIN as an intentional Cartesian operation.
4. Use aliases in SELF JOINs so each logical role is unambiguous.
5. Expect NULL-extended rows from outer joins.
6. Distinguish filtering in ON from filtering in WHERE.
7. Check whether duplicate keys can multiply rows.
8. Use aggregation only after verifying join cardinality.
9. Index frequently joined columns when supported by the database workload.
10. Inspect query plans for expensive production queries.
11. Parameterize values rather than constructing SQL from untrusted strings.
12. Test empty tables, duplicate keys, NULL keys, and unmatched records.
13. Avoid loading entire large datasets into application memory when the
    database can perform the join more efficiently.
`);
}


// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
    validateData();

    demonstrateInnerJoin();
    demonstrateLeftJoin();
    demonstrateFullOuterJoin();
    demonstrateCrossJoin();
    demonstrateSelfJoinHierarchy();
    demonstrateSelfJoinPeers();
    demonstrateReconciliation();
    demonstrateManyToMany();
    demonstrateAggregation();
    demonstrateSemiAndAntiJoin();
    demonstrateNullSemantics();
    demonstrateCardinality();
    compareNaiveAndIndexedJoin();
    printProductionConsiderations();

    assert(
        departments.length === 5,
        "Expected five departments."
    );

    assert(
        employees.filter((employee) => employee.departmentId === null).length === 1,
        "Expected one employee without a department."
    );

    console.log("\nAll JavaScript assertions passed.");
}

main();
```
