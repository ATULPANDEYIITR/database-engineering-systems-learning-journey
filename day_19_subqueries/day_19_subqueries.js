/*
 * SQL Subqueries: Scalar, Correlated, Nested, and Multi-Level Subqueries
 *
 * This self-contained JavaScript study file complements a relational SQL
 * implementation by modeling the same subquery concepts with JavaScript
 * arrays and functions.
 *
 * It demonstrates:
 * - scalar subquery thinking
 * - set-producing subqueries
 * - IN and NOT IN semantics
 * - EXISTS and NOT EXISTS
 * - correlated subqueries
 * - nested subqueries
 * - multi-level subqueries
 * - aggregate calculations
 * - derived-table thinking
 * - NULL behavior
 * - comparison with JOIN-like processing
 * - validation
 * - parameterized SQL construction
 * - complexity and performance observations
 *
 * Runtime:
 *   Node.js 18+ recommended.
 *
 * No external npm package is required.
 */

"use strict";

// -----------------------------------------------------------------------------
// Generic utility functions
// -----------------------------------------------------------------------------

function printTitle(title) {
    console.log("\n" + "=".repeat(88));
    console.log(title);
    console.log("=".repeat(88));
}

function printSubtitle(title) {
    console.log("\n" + "-".repeat(72));
    console.log(title);
    console.log("-".repeat(72));
}

function printRows(rows) {
    if (rows.length === 0) {
        console.log("(no rows)");
        return;
    }

    console.table(rows);
}

function average(values) {
    if (values.length === 0) {
        return null;
    }

    return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function sum(values) {
    return values.reduce((total, value) => total + value, 0);
}

function max(values) {
    if (values.length === 0) {
        return null;
    }

    return Math.max(...values);
}

function min(values) {
    if (values.length === 0) {
        return null;
    }

    return Math.min(...values);
}

function round(value, digits = 2) {
    if (value === null || value === undefined) {
        return null;
    }

    const factor = 10 ** digits;
    return Math.round((value + Number.EPSILON) * factor) / factor;
}


// -----------------------------------------------------------------------------
// Dataset
// -----------------------------------------------------------------------------

const departments = [
    { departmentId: 1, departmentName: "Engineering", location: "Bengaluru", budget: 1800000 },
    { departmentId: 2, departmentName: "Finance", location: "Mumbai", budget: 900000 },
    { departmentId: 3, departmentName: "Operations", location: "Delhi", budget: 1200000 },
    { departmentId: 4, departmentName: "Research", location: "Hyderabad", budget: 1500000 },
    { departmentId: 5, departmentName: "Security", location: "Pune", budget: 1300000 }
];

const employees = [
    { employeeId: 1, employeeName: "Aarav", departmentId: 1, managerId: null, salary: 150000, status: "ACTIVE" },
    { employeeId: 2, employeeName: "Meera", departmentId: 1, managerId: 1, salary: 125000, status: "ACTIVE" },
    { employeeId: 3, employeeName: "Kabir", departmentId: 1, managerId: 1, salary: 110000, status: "ACTIVE" },
    { employeeId: 4, employeeName: "Ishita", departmentId: 1, managerId: 2, salary: 90000, status: "ACTIVE" },
    { employeeId: 5, employeeName: "Rohan", departmentId: 2, managerId: null, salary: 140000, status: "ACTIVE" },
    { employeeId: 6, employeeName: "Anaya", departmentId: 2, managerId: 5, salary: 100000, status: "ACTIVE" },
    { employeeId: 7, employeeName: "Vivaan", departmentId: 2, managerId: 5, salary: 85000, status: "ACTIVE" },
    { employeeId: 8, employeeName: "Diya", departmentId: 3, managerId: null, salary: 115000, status: "ACTIVE" },
    { employeeId: 9, employeeName: "Arjun", departmentId: 3, managerId: 8, salary: 78000, status: "ACTIVE" },
    { employeeId: 10, employeeName: "Sara", departmentId: 3, managerId: 8, salary: 72000, status: "ACTIVE" },
    { employeeId: 11, employeeName: "Advik", departmentId: 4, managerId: null, salary: 155000, status: "ACTIVE" },
    { employeeId: 12, employeeName: "Tara", departmentId: 4, managerId: 11, salary: 130000, status: "ACTIVE" },
    { employeeId: 13, employeeName: "Neil", departmentId: 4, managerId: 11, salary: 95000, status: "ACTIVE" },
    { employeeId: 14, employeeName: "Kavya", departmentId: 5, managerId: null, salary: 145000, status: "ACTIVE" },
    { employeeId: 15, employeeName: "Yash", departmentId: 5, managerId: 14, salary: 105000, status: "ACTIVE" },
    { employeeId: 16, employeeName: "Naina", departmentId: 5, managerId: 14, salary: 88000, status: "ACTIVE" }
];

const projects = [
    { projectId: 1, projectName: "Cloud Migration", departmentId: 1, budget: 600000, status: "ACTIVE" },
    { projectId: 2, projectName: "Developer Platform", departmentId: 1, budget: 450000, status: "ACTIVE" },
    { projectId: 3, projectName: "Fraud Analytics", departmentId: 2, budget: 300000, status: "ACTIVE" },
    { projectId: 4, projectName: "Cost Optimization", departmentId: 2, budget: 180000, status: "CLOSED" },
    { projectId: 5, projectName: "Supply Forecasting", departmentId: 3, budget: 350000, status: "ACTIVE" },
    { projectId: 6, projectName: "AI Research", departmentId: 4, budget: 700000, status: "ACTIVE" },
    { projectId: 7, projectName: "Threat Intelligence", departmentId: 5, budget: 500000, status: "ACTIVE" },
    { projectId: 8, projectName: "Security Automation", departmentId: 5, budget: 250000, status: "PLANNED" }
];

const sales = [
    { saleId: 1, employeeId: 2, amount: 90000 },
    { saleId: 2, employeeId: 3, amount: 120000 },
    { saleId: 3, employeeId: 4, amount: 75000 },
    { saleId: 4, employeeId: 5, amount: 140000 },
    { saleId: 5, employeeId: 6, amount: 95000 },
    { saleId: 6, employeeId: 7, amount: 50000 },
    { saleId: 7, employeeId: 8, amount: 110000 },
    { saleId: 8, employeeId: 9, amount: 70000 },
    { saleId: 9, employeeId: 10, amount: 65000 },
    { saleId: 10, employeeId: 11, amount: 180000 },
    { saleId: 11, employeeId: 12, amount: 130000 },
    { saleId: 12, employeeId: 13, amount: 90000 },
    { saleId: 13, employeeId: 14, amount: 160000 },
    { saleId: 14, employeeId: 15, amount: 105000 },
    { saleId: 15, employeeId: 16, amount: 72000 }
];

const reviews = [
    { reviewId: 1, employeeId: 2, score: 91 },
    { reviewId: 2, employeeId: 3, score: 84 },
    { reviewId: 3, employeeId: 4, score: 78 },
    { reviewId: 4, employeeId: 6, score: 88 },
    { reviewId: 5, employeeId: 7, score: 74 },
    { reviewId: 6, employeeId: 9, score: 81 },
    { reviewId: 7, employeeId: 10, score: 79 },
    { reviewId: 8, employeeId: 12, score: 95 },
    { reviewId: 9, employeeId: 13, score: 87 },
    { reviewId: 10, employeeId: 15, score: 90 },
    { reviewId: 11, employeeId: 16, score: 76 }
];


// -----------------------------------------------------------------------------
// Validation
// -----------------------------------------------------------------------------

function validateDataset() {
    printTitle("1. Relational data validation");

    const departmentIds = new Set(departments.map(d => d.departmentId));

    for (const employee of employees) {
        if (!departmentIds.has(employee.departmentId)) {
            throw new Error(
                `Employee ${employee.employeeName} references an unknown department`
            );
        }

        if (employee.salary <= 0) {
            throw new Error(
                `Employee ${employee.employeeName} has an invalid salary`
            );
        }
    }

    for (const project of projects) {
        if (!departmentIds.has(project.departmentId)) {
            throw new Error(
                `Project ${project.projectName} references an unknown department`
            );
        }
    }

    console.log("Dataset validation passed.");
}


// -----------------------------------------------------------------------------
// Scalar subquery equivalents
// -----------------------------------------------------------------------------

function demonstrateScalarSubquery() {
    printTitle("2. Scalar subquery equivalents");

    /*
     * SQL concept:
     *
     * SELECT employee_name
     * FROM employees
     * WHERE salary > (
     *     SELECT AVG(salary)
     *     FROM employees
     * );
     *
     * The inner SELECT produces one value.
     */
    const companyAverageSalary = average(
        employees.map(employee => employee.salary)
    );

    const aboveAverage = employees
        .filter(employee => employee.salary > companyAverageSalary)
        .map(employee => ({
            employeeName: employee.employeeName,
            salary: employee.salary,
            companyAverage: round(companyAverageSalary)
        }));

    printRows(aboveAverage);

    printSubtitle("Scalar subquery in a calculated expression");

    const maximumSalary = max(employees.map(employee => employee.salary));

    printRows(
        employees.map(employee => ({
            employeeName: employee.employeeName,
            salary: employee.salary,
            percentageOfMaximum: round(
                employee.salary / maximumSalary * 100
            )
        }))
    );
}


// -----------------------------------------------------------------------------
// Set-producing subqueries
// -----------------------------------------------------------------------------

function demonstrateInSubquery() {
    printTitle("3. IN as a set-producing subquery");

    /*
     * SQL concept:
     *
     * WHERE department_id IN (
     *     SELECT department_id
     *     FROM departments
     *     WHERE budget > 1300000
     * )
     */

    const qualifyingDepartmentIds = departments
        .filter(department => department.budget > 1300000)
        .map(department => department.departmentId);

    const result = employees
        .filter(employee =>
            qualifyingDepartmentIds.includes(employee.departmentId)
        )
        .map(employee => ({
            employeeName: employee.employeeName,
            departmentId: employee.departmentId,
            salary: employee.salary
        }));

    printRows(result);
}


// -----------------------------------------------------------------------------
// EXISTS and NOT EXISTS
// -----------------------------------------------------------------------------

function demonstrateExists() {
    printTitle("4. EXISTS and NOT EXISTS");

    /*
     * EXISTS is about row existence rather than the value returned.
     *
     * SQL concept:
     *
     * WHERE EXISTS (
     *     SELECT 1
     *     FROM projects
     *     WHERE projects.department_id = departments.department_id
     *       AND projects.status = 'ACTIVE'
     * )
     */

    const departmentsWithActiveProjects = departments
        .filter(department =>
            projects.some(
                project =>
                    project.departmentId === department.departmentId &&
                    project.status === "ACTIVE"
            )
        )
        .map(department => department.departmentName);

    console.log("Departments with active projects:");
    console.log(departmentsWithActiveProjects);

    /*
     * NOT EXISTS:
     * The employee is selected only if no matching sales row exists.
     */
    const employeesWithoutSales = employees
        .filter(employee =>
            !sales.some(sale => sale.employeeId === employee.employeeId)
        )
        .map(employee => employee.employeeName);

    console.log("Employees without sales:");
    console.log(employeesWithoutSales);
}


// -----------------------------------------------------------------------------
// Correlated subqueries
// -----------------------------------------------------------------------------

function demonstrateCorrelatedSubquery() {
    printTitle("5. Correlated subquery");

    /*
     * SQL concept:
     *
     * SELECT employee_name, salary
     * FROM employees AS e
     * WHERE salary > (
     *     SELECT AVG(e2.salary)
     *     FROM employees AS e2
     *     WHERE e2.department_id = e.department_id
     * );
     *
     * The inner calculation depends on the current outer employee.
     */

    const result = [];

    for (const employee of employees) {
        const departmentEmployees = employees.filter(
            candidate =>
                candidate.departmentId === employee.departmentId
        );

        const departmentAverage = average(
            departmentEmployees.map(candidate => candidate.salary)
        );

        if (employee.salary > departmentAverage) {
            result.push({
                employeeName: employee.employeeName,
                departmentId: employee.departmentId,
                salary: employee.salary,
                departmentAverage: round(departmentAverage)
            });
        }
    }

    printRows(result);
}


// -----------------------------------------------------------------------------
// Correlated NOT EXISTS for top-per-group
// -----------------------------------------------------------------------------

function demonstrateCorrelatedTopPerGroup() {
    printTitle("6. Correlated NOT EXISTS for top-per-group");

    /*
     * SQL concept:
     *
     * WHERE NOT EXISTS (
     *     SELECT 1
     *     FROM employees AS higher
     *     WHERE higher.department_id = e.department_id
     *       AND higher.salary > e.salary
     * )
     *
     * If no employee in the same department has a strictly greater salary,
     * the current employee is a department salary leader.
     */

    const leaders = employees.filter(employee => {
        const higherPaidEmployeeExists = employees.some(
            candidate =>
                candidate.departmentId === employee.departmentId &&
                candidate.salary > employee.salary
        );

        return !higherPaidEmployeeExists;
    });

    printRows(
        leaders.map(employee => ({
            employeeName: employee.employeeName,
            departmentId: employee.departmentId,
            salary: employee.salary
        }))
    );
}


// -----------------------------------------------------------------------------
// Nested subqueries
// -----------------------------------------------------------------------------

function demonstrateNestedSubqueries() {
    printTitle("7. Nested subqueries");

    /*
     * Logical levels:
     *
     * Level 1:
     *   Calculate average department budget.
     *
     * Level 2:
     *   Select departments above that average.
     *
     * Level 3:
     *   Select employees belonging to those departments.
     */

    const averageDepartmentBudget = average(
        departments.map(department => department.budget)
    );

    const aboveAverageBudgetDepartmentIds = departments
        .filter(department => department.budget > averageDepartmentBudget)
        .map(department => department.departmentId);

    const employeesInThoseDepartments = employees
        .filter(employee =>
            aboveAverageBudgetDepartmentIds.includes(employee.departmentId)
        )
        .map(employee => ({
            employeeName: employee.employeeName,
            departmentId: employee.departmentId,
            salary: employee.salary
        }));

    printRows(employeesInThoseDepartments);
}


// -----------------------------------------------------------------------------
// Multi-level subqueries
// -----------------------------------------------------------------------------

function demonstrateMultiLevelSubquery() {
    printTitle("8. Multi-level subquery case study");

    /*
     * Goal:
     *
     * Find employees belonging to departments whose ACTIVE project budget
     * exceeds the average ACTIVE project budget across departments.
     *
     * Layer 1:
     *   Calculate active project budget per department.
     *
     * Layer 2:
     *   Calculate the average of those departmental totals.
     *
     * Layer 3:
     *   Select departments above that average.
     *
     * Layer 4:
     *   Select employees belonging to those departments.
     */

    const activeProjectBudgetByDepartment = departments.map(department => {
        const departmentProjects = projects.filter(
            project =>
                project.departmentId === department.departmentId &&
                project.status === "ACTIVE"
        );

        return {
            departmentId: department.departmentId,
            activeProjectBudget: sum(
                departmentProjects.map(project => project.budget)
            )
        };
    });

    const averageActiveProjectBudget = average(
        activeProjectBudgetByDepartment.map(
            item => item.activeProjectBudget
        )
    );

    const qualifyingDepartmentIds = activeProjectBudgetByDepartment
        .filter(
            item =>
                item.activeProjectBudget > averageActiveProjectBudget
        )
        .map(item => item.departmentId);

    const result = employees
        .filter(employee =>
            qualifyingDepartmentIds.includes(employee.departmentId)
        )
        .map(employee => ({
            employeeName: employee.employeeName,
            departmentId: employee.departmentId,
            salary: employee.salary
        }));

    printRows(result);
}


// -----------------------------------------------------------------------------
// Correlated aggregate plus EXISTS
// -----------------------------------------------------------------------------

function demonstrateAdvancedCombinedQuery() {
    printTitle("9. Advanced combined subquery logic");

    /*
     * Business requirement:
     *
     * An employee qualifies when:
     * 1. salary is above department average,
     * 2. employee has at least one sale,
     * 3. employee's best review score exceeds company review average,
     * 4. employee's department has an active project.
     *
     * This mirrors a realistic analytical SQL query containing several
     * correlated and non-correlated subqueries.
     */

    const companyReviewAverage = average(
        reviews.map(review => review.score)
    );

    const result = [];

    for (const employee of employees) {
        const departmentEmployees = employees.filter(
            candidate =>
                candidate.departmentId === employee.departmentId &&
                candidate.status === "ACTIVE"
        );

        const departmentAverageSalary = average(
            departmentEmployees.map(candidate => candidate.salary)
        );

        const employeeSales = sales.filter(
            sale => sale.employeeId === employee.employeeId
        );

        const employeeReviews = reviews.filter(
            review => review.employeeId === employee.employeeId
        );

        const departmentHasActiveProject = projects.some(
            project =>
                project.departmentId === employee.departmentId &&
                project.status === "ACTIVE"
        );

        const bestReviewScore = employeeReviews.length > 0
            ? max(employeeReviews.map(review => review.score))
            : null;

        if (
            employee.status === "ACTIVE" &&
            employee.salary > departmentAverageSalary &&
            employeeSales.length > 0 &&
            bestReviewScore !== null &&
            bestReviewScore > companyReviewAverage &&
            departmentHasActiveProject
        ) {
            result.push({
                employeeName: employee.employeeName,
                salary: employee.salary,
                departmentAverage: round(departmentAverageSalary),
                bestReviewScore,
                companyReviewAverage: round(companyReviewAverage),
                salesCount: employeeSales.length
            });
        }
    }

    printRows(result);
}


// -----------------------------------------------------------------------------
// Derived-table thinking
// -----------------------------------------------------------------------------

function demonstrateDerivedTable() {
    printTitle("10. Derived-table equivalent");

    /*
     * SQL derived-table concept:
     *
     * FROM (
     *     SELECT department_id, COUNT(*) AS employee_count
     *     FROM employees
     *     GROUP BY department_id
     * ) AS department_metrics
     *
     * The inner result behaves like a temporary relational table.
     */

    const departmentMetrics = departments.map(department => {
        const activeEmployees = employees.filter(
            employee =>
                employee.departmentId === department.departmentId &&
                employee.status === "ACTIVE"
        );

        return {
            departmentId: department.departmentId,
            departmentName: department.departmentName,
            employeeCount: activeEmployees.length,
            averageSalary: round(
                average(activeEmployees.map(employee => employee.salary))
            )
        };
    });

    printRows(
        departmentMetrics
            .filter(metric => metric.employeeCount >= 2)
            .sort((a, b) => b.averageSalary - a.averageSalary)
    );
}


// -----------------------------------------------------------------------------
// NULL semantics
// -----------------------------------------------------------------------------

function demonstrateNullSemantics() {
    printTitle("11. NULL and three-valued logic");

    /*
     * JavaScript and SQL have different NULL semantics.
     *
     * JavaScript's null is a language value.
     * SQL NULL means "missing or unknown".
     *
     * SQL uses:
     *   TRUE
     *   FALSE
     *   UNKNOWN
     *
     * This is why:
     *
     *   column = NULL
     *
     * is not the correct SQL test.
     *
     * SQL uses:
     *
     *   column IS NULL
     *
     * or:
     *
     *   column IS NOT NULL
     */

    const values = [1, 2, null];

    console.log("JavaScript values:", values);

    console.log(
        "JavaScript strict comparison null === null:",
        null === null
    );

    console.log(
        "SQL-style existence should be modeled explicitly rather than "
        + "assuming JavaScript equality has identical semantics."
    );

    /*
     * A safe conceptual anti-existence implementation:
     */
    const employeesWithoutReviews = employees.filter(
        employee =>
            !reviews.some(
                review => review.employeeId === employee.employeeId
            )
    );

    printRows(
        employeesWithoutReviews.map(employee => ({
            employeeName: employee.employeeName,
            reviewScore: null
        }))
    );
}


// -----------------------------------------------------------------------------
// IN versus EXISTS
// -----------------------------------------------------------------------------

function demonstrateInVsExists() {
    printTitle("12. IN versus EXISTS");

    const locations = new Set(
        departments
            .filter(
                department =>
                    department.location === "Bengaluru" ||
                    department.location === "Hyderabad"
            )
            .map(department => department.departmentId)
    );

    const usingInStyle = employees.filter(
        employee => locations.has(employee.departmentId)
    );

    const usingExistsStyle = employees.filter(
        employee =>
            departments.some(
                department =>
                    department.departmentId === employee.departmentId &&
                    (
                        department.location === "Bengaluru" ||
                        department.location === "Hyderabad"
                    )
            )
    );

    console.log("IN-style result:");
    printRows(usingInStyle.map(employee => ({
        employeeName: employee.employeeName
    })));

    console.log("EXISTS-style result:");
    printRows(usingExistsStyle.map(employee => ({
        employeeName: employee.employeeName
    })));

    console.log(
        "For this non-NULL relationship, both formulations represent "
        + "the same membership question."
    );
}


// -----------------------------------------------------------------------------
// JOIN-style comparison
// -----------------------------------------------------------------------------

function demonstrateJoinAlternative() {
    printTitle("13. Subquery versus JOIN-style processing");

    /*
     * Subquery formulation:
     *
     * WHERE department_id IN (
     *     SELECT department_id
     *     FROM departments
     *     WHERE budget > 1300000
     * )
     */

    const subqueryDepartmentIds = new Set(
        departments
            .filter(department => department.budget > 1300000)
            .map(department => department.departmentId)
    );

    const subqueryStyle = employees.filter(
        employee => subqueryDepartmentIds.has(employee.departmentId)
    );

    /*
     * JOIN-style formulation:
     *
     * JOIN departments
     * ON departments.department_id = employees.department_id
     * WHERE departments.budget > 1300000
     */

    const joinStyle = [];

    for (const employee of employees) {
        const department = departments.find(
            item => item.departmentId === employee.departmentId
        );

        if (department && department.budget > 1300000) {
            joinStyle.push({
                employeeName: employee.employeeName,
                departmentName: department.departmentName
            });
        }
    }

    console.log("Subquery-style:");
    printRows(
        subqueryStyle.map(employee => ({
            employeeName: employee.employeeName
        }))
    );

    console.log("JOIN-style:");
    printRows(joinStyle);
}


// -----------------------------------------------------------------------------
// Parameterized SQL construction
// -----------------------------------------------------------------------------

function demonstrateParameterizedSQL() {
    printTitle("14. Security: parameterized SQL");

    /*
     * JavaScript application code often sends SQL to a database driver.
     *
     * Unsafe:
     *
     *   const sql = "SELECT ... WHERE name = '" + userInput + "'";
     *
     * A malicious value can alter SQL syntax.
     *
     * Safe:
     *
     *   const sql = "SELECT ... WHERE name = ?";
     *   connection.execute(sql, [userInput]);
     *
     * This example demonstrates the query shape without requiring an external
     * database driver.
     */

    const userInput = "Engineering";

    const sql = `
        SELECT employee_name
        FROM employees
        WHERE department_id IN (
            SELECT department_id
            FROM departments
            WHERE department_name = ?
        )
    `;

    const parameters = [userInput];

    console.log("Parameterized SQL:");
    console.log(sql.trim());
    console.log("Parameters:", parameters);
}


// -----------------------------------------------------------------------------
// Complexity comparison
// -----------------------------------------------------------------------------

function demonstrateComplexity() {
    printTitle("15. Performance model");

    /*
     * A direct array-based correlated implementation may repeatedly scan
     * employees.
     *
     * If there are N outer employees and each correlated lookup scans N
     * employees, the straightforward implementation can approach O(N²).
     *
     * SQL database optimizers can transform such queries, use indexes,
     * materialize intermediate results, or choose joins and other plans.
     */

    const n = employees.length;

    console.log(`Employee count N = ${n}`);
    console.log(
        "Naive correlated-array mental model: approximately O(N²)"
    );

    /*
     * Precomputing department averages turns repeated searches into indexed
     * map lookups, producing a substantially better application-level design.
     */
    const salaryGroups = new Map();

    for (const employee of employees) {
        if (!salaryGroups.has(employee.departmentId)) {
            salaryGroups.set(employee.departmentId, []);
        }

        salaryGroups.get(employee.departmentId).push(employee.salary);
    }

    const departmentAverages = new Map();

    for (const [departmentId, salaries] of salaryGroups.entries()) {
        departmentAverages.set(departmentId, average(salaries));
    }

    const optimizedResult = employees.filter(
        employee =>
            employee.salary >
            departmentAverages.get(employee.departmentId)
    );

    console.log(
        "Precomputed-group result count:",
        optimizedResult.length
    );

    console.log(
        "This illustrates why relational databases can benefit from "
        + "indexes, grouping, joins, materialization, and optimizer rewrites."
    );
}


// -----------------------------------------------------------------------------
// Window-function conceptual alternative
// -----------------------------------------------------------------------------

function demonstrateWindowFunctionConcept() {
    printTitle("16. Window-function alternative");

    /*
     * SQL can express:
     *
     * AVG(salary) OVER (PARTITION BY department_id)
     *
     * without collapsing employees into groups.
     *
     * JavaScript does not have SQL window functions built into Array methods,
     * so we emulate the same partition-and-annotate operation.
     */

    const departmentGroups = new Map();

    for (const employee of employees) {
        if (!departmentGroups.has(employee.departmentId)) {
            departmentGroups.set(employee.departmentId, []);
        }

        departmentGroups.get(employee.departmentId).push(employee);
    }

    const result = employees.map(employee => {
        const group = departmentGroups.get(employee.departmentId);
        const departmentAverage = average(
            group.map(item => item.salary)
        );

        return {
            employeeName: employee.employeeName,
            departmentId: employee.departmentId,
            salary: employee.salary,
            departmentAverage: round(departmentAverage)
        };
    });

    printRows(result);
}


// -----------------------------------------------------------------------------
// Validation and tests
// -----------------------------------------------------------------------------

function assert(condition, message) {
    if (!condition) {
        throw new Error(`Assertion failed: ${message}`);
    }
}

function runTests() {
    printTitle("17. Automated tests");

    const companyAverage = average(
        employees.map(employee => employee.salary)
    );

    const aboveCompanyAverage = employees.filter(
        employee => employee.salary > companyAverage
    );

    assert(
        aboveCompanyAverage.length > 0,
        "At least one employee should be above company average"
    );

    const activeProjectDepartments = departments.filter(
        department =>
            projects.some(
                project =>
                    project.departmentId === department.departmentId &&
                    project.status === "ACTIVE"
            )
    );

    assert(
        activeProjectDepartments.length > 0,
        "At least one department should have an active project"
    );

    const departmentLeaders = employees.filter(employee => {
        return !employees.some(
            candidate =>
                candidate.departmentId === employee.departmentId &&
                candidate.salary > employee.salary
        );
    });

    assert(
        departmentLeaders.length === departments.length,
        "Each department should have at least one salary leader"
    );

    console.log("All JavaScript assertions passed.");
}


// -----------------------------------------------------------------------------
// Main
// -----------------------------------------------------------------------------

function main() {
    printTitle("SQL SUBQUERIES THROUGH A JAVASCRIPT RELATIONAL MODEL");

    try {
        validateDataset();
        demonstrateScalarSubquery();
        demonstrateInSubquery();
        demonstrateExists();
        demonstrateCorrelatedSubquery();
        demonstrateCorrelatedTopPerGroup();
        demonstrateNestedSubqueries();
        demonstrateMultiLevelSubquery();
        demonstrateAdvancedCombinedQuery();
        demonstrateDerivedTable();
        demonstrateNullSemantics();
        demonstrateInVsExists();
        demonstrateJoinAlternative();
        demonstrateParameterizedSQL();
        demonstrateComplexity();
        demonstrateWindowFunctionConcept();
        runTests();

        printTitle("18. Core distinctions");

        console.log(`
Scalar subquery:
  Produces one value.

IN subquery:
  Produces a set of values used for membership testing.

EXISTS subquery:
  Tests whether at least one matching row exists.

Correlated subquery:
  Refers to the current row of the outer query.

Nested subquery:
  Contains another subquery inside it.

Multi-level subquery:
  Uses several layers of nested relational calculations.

Derived-table subquery:
  Produces a result set that behaves like a table in the outer query.

Production consideration:
  Choose among subqueries, joins, CTEs, and window functions according to
  clarity, semantics, optimizer behavior, and measured performance.
`);
    } catch (error) {
        console.error("Execution failed:", error.message);
        process.exitCode = 1;
    }
}

main();
