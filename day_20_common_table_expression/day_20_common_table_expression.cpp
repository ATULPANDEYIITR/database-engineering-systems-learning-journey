/*
 * Common Table Expressions: C++ Industry Case Study
 *
 * Scenario:
 *     Organizational analytics for a large enterprise.
 *
 * The system stores employees as parent-child relationships:
 *
 *     CEO
 *       -> Director
 *          -> Manager
 *             -> Employee
 *
 * The C++ program demonstrates how a production application can model the
 * same logical problem that a recursive SQL CTE solves.
 *
 * The program:
 *     - models relational employee records
 *     - validates input data
 *     - builds a management hierarchy
 *     - performs recursive traversal
 *     - detects cycles
 *     - calculates hierarchy depth
 *     - calculates management paths
 *     - aggregates department metrics
 *     - ranks departments
 *     - generates the equivalent recursive CTE SQL
 *     - demonstrates query parameter handling conceptually
 *
 * The program intentionally uses only the C++17 standard library.
 * A real application would execute the generated SQL through a database
 * driver such as a PostgreSQL, SQLite, MySQL, or SQL Server client library.
 */

#include <algorithm>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using namespace std;

/* ------------------------------------------------------------------------- */
/* Employee model                                                            */
/* ------------------------------------------------------------------------- */

struct Employee {
    int id;
    string name;
    optional<int> managerId;
    string department;
    string title;
    double salary;
};

/*
 * Department metrics represent the output of a grouped SQL CTE.
 */
struct DepartmentMetrics {
    string department;
    size_t employeeCount = 0;
    double payroll = 0.0;
    double averageSalary = 0.0;
    int payrollRank = 0;
};

/*
 * HierarchyNode represents the information a recursive CTE would carry
 * from one level to the next.
 */
struct HierarchyNode {
    int employeeId;
    int level;
    string path;
};

/* ------------------------------------------------------------------------- */
/* EmployeeRepository                                                        */
/* ------------------------------------------------------------------------- */

class EmployeeRepository {
private:
    vector<Employee> employees;

public:
    void addEmployee(const Employee& employee) {
        if (employee.id <= 0) {
            throw invalid_argument("Employee ID must be positive.");
        }

        if (employee.name.empty()) {
            throw invalid_argument("Employee name cannot be empty.");
        }

        if (employee.department.empty()) {
            throw invalid_argument("Department cannot be empty.");
        }

        if (employee.salary <= 0) {
            throw invalid_argument("Salary must be positive.");
        }

        employees.push_back(employee);
    }

    const vector<Employee>& all() const {
        return employees;
    }

    const Employee* findById(int id) const {
        for (const auto& employee : employees) {
            if (employee.id == id) {
                return &employee;
            }
        }

        return nullptr;
    }

    vector<const Employee*> directReports(int managerId) const {
        vector<const Employee*> reports;

        for (const auto& employee : employees) {
            if (employee.managerId.has_value() &&
                employee.managerId.value() == managerId) {
                reports.push_back(&employee);
            }
        }

        sort(
            reports.begin(),
            reports.end(),
            [](const Employee* left, const Employee* right) {
                return left->id < right->id;
            }
        );

        return reports;
    }

    vector<const Employee*> topLevelEmployees() const {
        vector<const Employee*> roots;

        for (const auto& employee : employees) {
            if (!employee.managerId.has_value()) {
                roots.push_back(&employee);
            }
        }

        sort(
            roots.begin(),
            roots.end(),
            [](const Employee* left, const Employee* right) {
                return left->id < right->id;
            }
        );

        return roots;
    }
};

/* ------------------------------------------------------------------------- */
/* OrganizationAnalyzer                                                      */
/* ------------------------------------------------------------------------- */

class OrganizationAnalyzer {
private:
    const EmployeeRepository& repository;

    /*
     * Recursive traversal.
     *
     * SQL equivalent:
     *
     *     WITH RECURSIVE hierarchy AS (
     *         anchor
     *         UNION ALL
     *         recursive member
     *     )
     *
     * The visited set provides explicit cycle protection.
     */
    void traverse(
        int employeeId,
        int level,
        const string& path,
        unordered_set<int>& visited,
        vector<HierarchyNode>& result
    ) const {
        if (visited.find(employeeId) != visited.end()) {
            throw runtime_error(
                "Cycle detected while traversing employee hierarchy at ID " +
                to_string(employeeId)
            );
        }

        const Employee* employee = repository.findById(employeeId);

        if (employee == nullptr) {
            throw runtime_error(
                "Hierarchy references an employee that does not exist: " +
                to_string(employeeId)
            );
        }

        visited.insert(employeeId);

        string currentPath = path.empty()
            ? employee->name
            : path + " > " + employee->name;

        result.push_back({
            employeeId,
            level,
            currentPath
        });

        const auto reports = repository.directReports(employeeId);

        for (const Employee* report : reports) {
            traverse(
                report->id,
                level + 1,
                currentPath,
                visited,
                result
            );
        }

        visited.erase(employeeId);
    }

public:
    explicit OrganizationAnalyzer(
        const EmployeeRepository& repositoryReference
    )
        : repository(repositoryReference) {}

    vector<HierarchyNode> buildHierarchy() const {
        vector<HierarchyNode> result;

        /*
         * Each top-level employee acts as an anchor row.
         * Recursion then expands direct reports.
         */
        for (const Employee* root : repository.topLevelEmployees()) {
            unordered_set<int> visited;

            traverse(
                root->id,
                0,
                "",
                visited,
                result
            );
        }

        return result;
    }

    vector<HierarchyNode> buildSubtree(int rootId) const {
        vector<HierarchyNode> result;
        unordered_set<int> visited;

        traverse(
            rootId,
            0,
            "",
            visited,
            result
        );

        return result;
    }

    map<string, DepartmentMetrics> calculateDepartmentMetrics() const {
        map<string, DepartmentMetrics> metrics;

        for (const Employee& employee : repository.all()) {
            auto& metric = metrics[employee.department];

            metric.department = employee.department;
            metric.employeeCount++;
            metric.payroll += employee.salary;
        }

        for (auto& [department, metric] : metrics) {
            metric.averageSalary =
                metric.employeeCount == 0
                    ? 0.0
                    : metric.payroll /
                      static_cast<double>(metric.employeeCount);
        }

        return metrics;
    }

    vector<DepartmentMetrics> rankedDepartments() const {
        auto metricMap = calculateDepartmentMetrics();

        vector<DepartmentMetrics> result;

        for (const auto& [department, metric] : metricMap) {
            result.push_back(metric);
        }

        sort(
            result.begin(),
            result.end(),
            [](const DepartmentMetrics& left,
               const DepartmentMetrics& right) {
                if (left.payroll != right.payroll) {
                    return left.payroll > right.payroll;
                }

                return left.department < right.department;
            }
        );

        int rank = 0;
        double previousPayroll = -1.0;
        int position = 0;

        for (auto& metric : result) {
            ++position;

            /*
             * This implements dense-rank-like behavior:
             * equal payroll values receive the same rank.
             */
            if (metric.payroll != previousPayroll) {
                rank = position;
                previousPayroll = metric.payroll;
            }

            metric.payrollRank = rank;
        }

        return result;
    }
};

/* ------------------------------------------------------------------------- */
/* Data validation                                                            */
/* ------------------------------------------------------------------------- */

class OrganizationValidator {
public:
    static vector<string> validate(const EmployeeRepository& repository) {
        vector<string> errors;
        unordered_set<int> ids;

        for (const Employee& employee : repository.all()) {
            if (!ids.insert(employee.id).second) {
                errors.push_back(
                    "Duplicate employee ID: " +
                    to_string(employee.id)
                );
            }

            if (employee.managerId.has_value()) {
                if (repository.findById(employee.managerId.value()) == nullptr) {
                    errors.push_back(
                        "Employee " +
                        to_string(employee.id) +
                        " references missing manager " +
                        to_string(employee.managerId.value())
                    );
                }

                if (employee.managerId.value() == employee.id) {
                    errors.push_back(
                        "Employee " +
                        to_string(employee.id) +
                        " directly manages itself."
                    );
                }
            }
        }

        return errors;
    }
};

/* ------------------------------------------------------------------------- */
/* SQL generator                                                              */
/* ------------------------------------------------------------------------- */

class SqlGenerator {
public:
    static string recursiveHierarchyQuery() {
        /*
         * This is the SQL form that the C++ application's logical hierarchy
         * operation corresponds to.
         */
        return R"SQL(
WITH RECURSIVE employee_tree AS (
    SELECT
        employee_id,
        employee_name,
        manager_id,
        department,
        job_title,
        salary,
        0 AS level,
        employee_name AS path
    FROM employees
    WHERE manager_id IS NULL

    UNION ALL

    SELECT
        e.employee_id,
        e.employee_name,
        e.manager_id,
        e.department,
        e.job_title,
        e.salary,
        tree.level + 1,
        tree.path || ' > ' || e.employee_name
    FROM employees AS e
    JOIN employee_tree AS tree
        ON e.manager_id = tree.employee_id
)
SELECT
    employee_id,
    employee_name,
    department,
    job_title,
    salary,
    level,
    path
FROM employee_tree
ORDER BY path;
)SQL";
    }

    static string analyticsQuery() {
        return R"SQL(
WITH RECURSIVE organization AS (
    SELECT
        employee_id,
        employee_name,
        manager_id,
        department,
        salary,
        0 AS level
    FROM employees
    WHERE manager_id IS NULL

    UNION ALL

    SELECT
        e.employee_id,
        e.employee_name,
        e.manager_id,
        e.department,
        e.salary,
        organization.level + 1
    FROM employees AS e
    JOIN organization
        ON e.manager_id = organization.employee_id
),
department_metrics AS (
    SELECT
        department,
        COUNT(*) AS employee_count,
        SUM(salary) AS payroll,
        AVG(salary) AS average_salary
    FROM organization
    GROUP BY department
),
ranked_departments AS (
    SELECT
        department,
        employee_count,
        payroll,
        average_salary,
        RANK() OVER (
            ORDER BY payroll DESC
        ) AS payroll_rank
    FROM department_metrics
)
SELECT *
FROM ranked_departments
ORDER BY payroll_rank;
)SQL";
    }
};

/* ------------------------------------------------------------------------- */
/* Report printer                                                             */
/* ------------------------------------------------------------------------- */

class ReportPrinter {
public:
    static void printHierarchy(
        const vector<HierarchyNode>& hierarchy,
        const EmployeeRepository& repository
    ) {
        cout << "\nORGANIZATION HIERARCHY\n";
        cout << string(90, '-') << '\n';

        for (const auto& node : hierarchy) {
            const Employee* employee =
                repository.findById(node.employeeId);

            if (employee == nullptr) {
                continue;
            }

            cout << "Level " << node.level
                 << " | "
                 << left << setw(20) << employee->name
                 << " | "
                 << setw(28) << employee->title
                 << " | "
                 << setw(15) << employee->department
                 << " | Path: "
                 << node.path
                 << '\n';
        }
    }

    static void printDepartments(
        const vector<DepartmentMetrics>& metrics
    ) {
        cout << "\nDEPARTMENT ANALYTICS\n";
        cout << string(85, '-') << '\n';

        cout << left
             << setw(18) << "Department"
             << setw(12) << "Employees"
             << setw(18) << "Payroll"
             << setw(18) << "Avg Salary"
             << setw(10) << "Rank"
             << '\n';

        cout << string(85, '-') << '\n';

        cout << fixed << setprecision(2);

        for (const auto& metric : metrics) {
            cout << left
                 << setw(18) << metric.department
                 << setw(12) << metric.employeeCount
                 << setw(18) << metric.payroll
                 << setw(18) << metric.averageSalary
                 << setw(10) << metric.payrollRank
                 << '\n';
        }
    }

    static void printSubtree(
        const vector<HierarchyNode>& subtree,
        const EmployeeRepository& repository,
        int rootId
    ) {
        const Employee* root = repository.findById(rootId);

        cout << "\nMANAGEMENT SUBTREE\n";

        if (root == nullptr) {
            cout << "Root employee does not exist.\n";
            return;
        }

        cout << "Root: " << root->name << '\n';
        cout << string(70, '-') << '\n';

        for (const auto& node : subtree) {
            const Employee* employee =
                repository.findById(node.employeeId);

            if (employee != nullptr) {
                cout << string(
                    static_cast<size_t>(node.level * 4),
                    ' '
                )
                << "- "
                << employee->name
                << " [" << employee->title << "]\n";
            }
        }
    }
};

/* ------------------------------------------------------------------------- */
/* Repository factory                                                         */
/* ------------------------------------------------------------------------- */

EmployeeRepository createEnterpriseOrganization() {
    EmployeeRepository repository;

    repository.addEmployee({
        1,
        "Anita Rao",
        nullopt,
        "Executive",
        "Chief Executive Officer",
        240000
    });

    repository.addEmployee({
        2,
        "Vikram Shah",
        1,
        "Engineering",
        "Engineering Director",
        190000
    });

    repository.addEmployee({
        3,
        "Meera Iyer",
        2,
        "Engineering",
        "Engineering Manager",
        145000
    });

    repository.addEmployee({
        4,
        "Arjun Singh",
        3,
        "Engineering",
        "Senior Software Engineer",
        125000
    });

    repository.addEmployee({
        5,
        "Neha Kapoor",
        3,
        "Engineering",
        "Software Engineer",
        105000
    });

    repository.addEmployee({
        6,
        "Rahul Verma",
        3,
        "Engineering",
        "Software Engineer",
        98000
    });

    repository.addEmployee({
        7,
        "Karan Malhotra",
        2,
        "Engineering",
        "Platform Manager",
        140000
    });

    repository.addEmployee({
        8,
        "Isha Gupta",
        7,
        "Engineering",
        "Cloud Engineer",
        115000
    });

    repository.addEmployee({
        9,
        "Rohan Das",
        7,
        "Engineering",
        "DevOps Engineer",
        118000
    });

    repository.addEmployee({
        10,
        "Priya Nair",
        1,
        "Product",
        "Product Director",
        185000
    });

    repository.addEmployee({
        11,
        "Sahil Mehta",
        10,
        "Product",
        "Product Manager",
        135000
    });

    repository.addEmployee({
        12,
        "Tanya Bose",
        11,
        "Product",
        "Product Analyst",
        90000
    });

    repository.addEmployee({
        13,
        "Aman Jain",
        11,
        "Product",
        "Product Analyst",
        92000
    });

    repository.addEmployee({
        14,
        "Divya Menon",
        1,
        "Finance",
        "Finance Manager",
        130000
    });

    return repository;
}

/* ------------------------------------------------------------------------- */
/* Cycle demonstration                                                        */
/* ------------------------------------------------------------------------- */

void demonstrateCycleDetection() {
    cout << "\nCYCLE DETECTION TEST\n";
    cout << string(70, '-') << '\n';

    EmployeeRepository cyclicRepository;

    cyclicRepository.addEmployee({
        1,
        "Employee A",
        3,
        "Test",
        "Role A",
        100000
    });

    cyclicRepository.addEmployee({
        2,
        "Employee B",
        1,
        "Test",
        "Role B",
        90000
    });

    cyclicRepository.addEmployee({
        3,
        "Employee C",
        2,
        "Test",
        "Role C",
        80000
    });

    OrganizationAnalyzer analyzer(cyclicRepository);

    try {
        /*
         * There is no root in this particular cycle, so we explicitly start
         * at employee 1 to demonstrate recursive cycle protection.
         */
        const auto subtree = analyzer.buildSubtree(1);

        (void)subtree;

        cout << "Unexpected result: cycle was not detected.\n";
    } catch (const exception& error) {
        cout << "Expected failure: "
             << error.what()
             << '\n';
    }
}

/* ------------------------------------------------------------------------- */
/* Complexity discussion                                                       */
/* ------------------------------------------------------------------------- */

void printComplexityAnalysis() {
    cout << R"TEXT(

COMPLEXITY AND PERFORMANCE

Hierarchy traversal:
    The analyzer visits each reachable employee once for a normal tree.
    With an indexed database relationship on manager_id, a recursive SQL
    CTE can efficiently locate child rows.

    The C++ demonstration uses a vector and scans employees when finding
    direct reports. That makes each child lookup O(N), so the simple
    implementation can approach O(N^2) for a large hierarchy.

    A production C++ implementation could maintain:
        unordered_map<int, vector<int>>

    mapping each manager to direct-report IDs. That makes child discovery
    approximately O(1) average lookup plus the number of returned children.

SQL-side performance:
    The equivalent database implementation should index manager_id.

Recursive growth:
    Tree traversal is normally proportional to the number of reachable
    nodes and edges, but graph traversal can grow rapidly when many paths
    exist.

Aggregation:
    Department aggregation is O(N) before sorting.

Ranking:
    Sorting M department rows is O(M log M), where M is the number of
    departments.

The key distinction is that SQL CTE syntax describes a relational operation,
while the database optimizer determines how that operation is physically
executed.
)TEXT";
}

/* ------------------------------------------------------------------------- */
/* Main                                                                       */
/* ------------------------------------------------------------------------- */

int main() {
    try {
        cout << string(90, '=') << '\n';
        cout << "COMMON TABLE EXPRESSIONS: C++ INDUSTRY CASE STUDY\n";
        cout << string(90, '=') << '\n';

        /*
         * Step 1:
         * Build the enterprise data model.
         */
        EmployeeRepository repository =
            createEnterpriseOrganization();

        /*
         * Step 2:
         * Validate relational integrity.
         */
        cout << "\nDATA VALIDATION\n";
        cout << string(70, '-') << '\n';

        const auto errors =
            OrganizationValidator::validate(repository);

        if (errors.empty()) {
            cout << "Validation passed. No structural errors found.\n";
        } else {
            for (const string& error : errors) {
                cout << "ERROR: " << error << '\n';
            }
            return 1;
        }

        /*
         * Step 3:
         * Build the complete hierarchy.
         *
         * This is the in-memory equivalent of a recursive CTE.
         */
        OrganizationAnalyzer analyzer(repository);

        const auto hierarchy =
            analyzer.buildHierarchy();

        ReportPrinter::printHierarchy(
            hierarchy,
            repository
        );

        /*
         * Step 4:
         * Retrieve a selected manager's subtree.
         */
        const int selectedManagerId = 2;

        const auto subtree =
            analyzer.buildSubtree(selectedManagerId);

        ReportPrinter::printSubtree(
            subtree,
            repository,
            selectedManagerId
        );

        /*
         * Step 5:
         * Aggregate departments.
         *
         * This corresponds to a later non-recursive CTE operating on the
         * logical result of the hierarchy stage.
         */
        const auto departmentMetrics =
            analyzer.rankedDepartments();

        ReportPrinter::printDepartments(
            departmentMetrics
        );

        /*
         * Step 6:
         * Display the SQL representation.
         */
        cout << "\nEQUIVALENT RECURSIVE SQL\n";
        cout << string(90, '-') << '\n';
        cout << SqlGenerator::recursiveHierarchyQuery();

        cout << "\nEQUIVALENT MULTI-STAGE ANALYTICS SQL\n";
        cout << string(90, '-') << '\n';
        cout << SqlGenerator::analyticsQuery();

        /*
         * Step 7:
         * Explain performance characteristics.
         */
        printComplexityAnalysis();

        /*
         * Step 8:
         * Demonstrate an important recursive edge case.
         */
        demonstrateCycleDetection();

        /*
         * Step 9:
         * Demonstrate the parameter-binding concept.
         */
        cout << R"TEXT(

PARAMETERIZATION CONCEPT

A real database call should keep SQL structure separate from user values.

Example conceptual statement:

    WITH qualifying_orders AS (
        SELECT order_id, customer_id, amount
        FROM orders
        WHERE amount >= ?
    )
    SELECT *
    FROM qualifying_orders;

The value belongs in a bound parameter rather than being concatenated into
the SQL string. This reduces SQL injection risk and lets the database driver
handle the value according to its type.
)TEXT";

        cout << "\nCASE STUDY COMPLETED\n";

        return 0;
    } catch (const exception& error) {
        cerr << "Fatal error: "
             << error.what()
             << '\n';

        return 1;
    }
}
