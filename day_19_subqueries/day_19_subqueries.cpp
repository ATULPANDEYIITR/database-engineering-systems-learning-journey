/*
 * SQL Subqueries: Industry-Style C++ Case Study
 *
 * Case study:
 * Employee intelligence and departmental performance analysis.
 *
 * The program models the relational data used by SQL subquery examples and
 * implements the equivalent relational operations in modern C++.
 *
 * It demonstrates the reasoning behind:
 * - scalar subqueries
 * - IN subqueries
 * - EXISTS
 * - NOT EXISTS
 * - correlated subqueries
 * - nested subqueries
 * - multi-level subqueries
 * - aggregate subqueries
 * - derived-table processing
 * - JOIN alternatives
 * - NULL-like optional values
 * - validation
 * - exception handling
 * - indexing with unordered_map
 * - complexity trade-offs
 *
 * Compile:
 *   g++ -std=c++17 -O2 subqueries.cpp -o subqueries
 */

#include <algorithm>
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

using namespace std;

// -----------------------------------------------------------------------------
// Domain models
// -----------------------------------------------------------------------------

struct Department {
    int id;
    string name;
    string location;
    double budget;
};

struct Employee {
    int id;
    string name;
    int departmentId;
    optional<int> managerId;
    double salary;
    bool active;
};

struct Project {
    int id;
    string name;
    int departmentId;
    double budget;
    string status;
};

struct Sale {
    int id;
    int employeeId;
    double amount;
};

struct Review {
    int id;
    int employeeId;
    double score;
};

struct DepartmentMetrics {
    int departmentId;
    string departmentName;
    size_t employeeCount;
    double averageSalary;
    double activeProjectBudget;
    double totalSales;
};


// -----------------------------------------------------------------------------
// Formatting
// -----------------------------------------------------------------------------

void printTitle(const string& title) {
    cout << "\n" << string(88, '=') << "\n";
    cout << title << "\n";
    cout << string(88, '=') << "\n";
}

void printSubtitle(const string& title) {
    cout << "\n" << string(70, '-') << "\n";
    cout << title << "\n";
    cout << string(70, '-') << "\n";
}

void printMoney(double value) {
    cout << fixed << setprecision(2) << value;
}


// -----------------------------------------------------------------------------
// Dataset
// -----------------------------------------------------------------------------

vector<Department> createDepartments() {
    return {
        {1, "Engineering", "Bengaluru", 1800000},
        {2, "Finance", "Mumbai", 900000},
        {3, "Operations", "Delhi", 1200000},
        {4, "Research", "Hyderabad", 1500000},
        {5, "Security", "Pune", 1300000}
    };
}

vector<Employee> createEmployees() {
    return {
        {1, "Aarav", 1, nullopt, 150000, true},
        {2, "Meera", 1, 1, 125000, true},
        {3, "Kabir", 1, 1, 110000, true},
        {4, "Ishita", 1, 2, 90000, true},
        {5, "Rohan", 2, nullopt, 140000, true},
        {6, "Anaya", 2, 5, 100000, true},
        {7, "Vivaan", 2, 5, 85000, true},
        {8, "Diya", 3, nullopt, 115000, true},
        {9, "Arjun", 3, 8, 78000, true},
        {10, "Sara", 3, 8, 72000, true},
        {11, "Advik", 4, nullopt, 155000, true},
        {12, "Tara", 4, 11, 130000, true},
        {13, "Neil", 4, 11, 95000, true},
        {14, "Kavya", 5, nullopt, 145000, true},
        {15, "Yash", 5, 14, 105000, true},
        {16, "Naina", 5, 14, 88000, true}
    };
}

vector<Project> createProjects() {
    return {
        {1, "Cloud Migration", 1, 600000, "ACTIVE"},
        {2, "Developer Platform", 1, 450000, "ACTIVE"},
        {3, "Fraud Analytics", 2, 300000, "ACTIVE"},
        {4, "Cost Optimization", 2, 180000, "CLOSED"},
        {5, "Supply Forecasting", 3, 350000, "ACTIVE"},
        {6, "AI Research", 4, 700000, "ACTIVE"},
        {7, "Threat Intelligence", 5, 500000, "ACTIVE"},
        {8, "Security Automation", 5, 250000, "PLANNED"}
    };
}

vector<Sale> createSales() {
    return {
        {1, 2, 90000},
        {2, 3, 120000},
        {3, 4, 75000},
        {4, 5, 140000},
        {5, 6, 95000},
        {6, 7, 50000},
        {7, 8, 110000},
        {8, 9, 70000},
        {9, 10, 65000},
        {10, 11, 180000},
        {11, 12, 130000},
        {12, 13, 90000},
        {13, 14, 160000},
        {14, 15, 105000},
        {15, 16, 72000}
    };
}

vector<Review> createReviews() {
    return {
        {1, 2, 91},
        {2, 3, 84},
        {3, 4, 78},
        {4, 6, 88},
        {5, 7, 74},
        {6, 9, 81},
        {7, 10, 79},
        {8, 12, 95},
        {9, 13, 87},
        {10, 15, 90},
        {11, 16, 76}
    };
}


// -----------------------------------------------------------------------------
// Generic relational helpers
// -----------------------------------------------------------------------------

double average(const vector<double>& values) {
    if (values.empty()) {
        throw invalid_argument("Cannot calculate average of an empty set");
    }

    double total = 0.0;

    for (double value : values) {
        total += value;
    }

    return total / static_cast<double>(values.size());
}

double sum(const vector<double>& values) {
    double total = 0.0;

    for (double value : values) {
        total += value;
    }

    return total;
}

optional<double> optionalAverage(const vector<double>& values) {
    if (values.empty()) {
        return nullopt;
    }

    return average(values);
}

double maximum(const vector<double>& values) {
    if (values.empty()) {
        throw invalid_argument("Cannot calculate maximum of an empty set");
    }

    return *max_element(values.begin(), values.end());
}

void validateData(
    const vector<Department>& departments,
    const vector<Employee>& employees,
    const vector<Project>& projects,
    const vector<Sale>& sales,
    const vector<Review>& reviews
) {
    unordered_set<int> departmentIds;

    for (const auto& department : departments) {
        if (department.budget < 0) {
            throw invalid_argument("Department budget cannot be negative");
        }

        if (!departmentIds.insert(department.id).second) {
            throw invalid_argument("Duplicate department ID");
        }
    }

    unordered_set<int> employeeIds;

    for (const auto& employee : employees) {
        if (!employeeIds.insert(employee.id).second) {
            throw invalid_argument("Duplicate employee ID");
        }

        if (!departmentIds.contains(employee.departmentId)) {
            throw invalid_argument(
                "Employee references an unknown department"
            );
        }

        if (employee.salary <= 0) {
            throw invalid_argument("Employee salary must be positive");
        }
    }

    for (const auto& project : projects) {
        if (!departmentIds.contains(project.departmentId)) {
            throw invalid_argument(
                "Project references an unknown department"
            );
        }

        if (project.budget < 0) {
            throw invalid_argument("Project budget cannot be negative");
        }
    }

    for (const auto& sale : sales) {
        if (!employeeIds.contains(sale.employeeId)) {
            throw invalid_argument(
                "Sale references an unknown employee"
            );
        }

        if (sale.amount < 0) {
            throw invalid_argument("Sale amount cannot be negative");
        }
    }

    for (const auto& review : reviews) {
        if (!employeeIds.contains(review.employeeId)) {
            throw invalid_argument(
                "Review references an unknown employee"
            );
        }

        if (review.score < 0 || review.score > 100) {
            throw invalid_argument("Review score must be between 0 and 100");
        }
    }
}


// -----------------------------------------------------------------------------
// Scalar subquery equivalent
// -----------------------------------------------------------------------------

double companyAverageSalary(const vector<Employee>& employees) {
    vector<double> salaries;

    for (const auto& employee : employees) {
        if (employee.active) {
            salaries.push_back(employee.salary);
        }
    }

    return average(salaries);
}

void demonstrateScalarSubquery(const vector<Employee>& employees) {
    printTitle("1. Scalar subquery");

    /*
     * SQL equivalent:
     *
     * SELECT employee_name, salary
     * FROM employees
     * WHERE salary > (
     *     SELECT AVG(salary)
     *     FROM employees
     * );
     *
     * The subquery produces exactly one scalar value.
     */

    const double companyAverage = companyAverageSalary(employees);

    cout << "Company average salary: ";
    printMoney(companyAverage);
    cout << "\n\nEmployees above company average:\n";

    for (const auto& employee : employees) {
        if (employee.active && employee.salary > companyAverage) {
            cout << employee.name << " | ";
            printMoney(employee.salary);
            cout << "\n";
        }
    }
}


// -----------------------------------------------------------------------------
// Correlated subquery
// -----------------------------------------------------------------------------

double departmentAverageSalary(
    int departmentId,
    const vector<Employee>& employees
) {
    vector<double> salaries;

    for (const auto& employee : employees) {
        if (
            employee.active &&
            employee.departmentId == departmentId
        ) {
            salaries.push_back(employee.salary);
        }
    }

    return average(salaries);
}

void demonstrateCorrelatedSubquery(
    const vector<Employee>& employees
) {
    printTitle("2. Correlated scalar subquery");

    /*
     * SQL equivalent:
     *
     * SELECT e.employee_name, e.salary
     * FROM employees AS e
     * WHERE e.salary > (
     *     SELECT AVG(e2.salary)
     *     FROM employees AS e2
     *     WHERE e2.department_id = e.department_id
     * );
     *
     * The inner calculation depends on e.department_id.
     */

    for (const auto& employee : employees) {
        const double departmentAverage =
            departmentAverageSalary(
                employee.departmentId,
                employees
            );

        if (
            employee.active &&
            employee.salary > departmentAverage
        ) {
            cout << employee.name
                 << " | salary=";
            printMoney(employee.salary);
            cout << " | department average=";
            printMoney(departmentAverage);
            cout << "\n";
        }
    }
}


// -----------------------------------------------------------------------------
// IN subquery
// -----------------------------------------------------------------------------

unordered_set<int> departmentsAboveBudget(
    const vector<Department>& departments,
    double threshold
) {
    unordered_set<int> result;

    for (const auto& department : departments) {
        if (department.budget > threshold) {
            result.insert(department.id);
        }
    }

    return result;
}

void demonstrateInSubquery(
    const vector<Department>& departments,
    const vector<Employee>& employees
) {
    printTitle("3. IN subquery");

    /*
     * SQL equivalent:
     *
     * WHERE department_id IN (
     *     SELECT department_id
     *     FROM departments
     *     WHERE budget > 1300000
     * )
     */

    const auto departmentIds =
        departmentsAboveBudget(departments, 1300000);

    for (const auto& employee : employees) {
        if (departmentIds.contains(employee.departmentId)) {
            cout << employee.name << "\n";
        }
    }
}


// -----------------------------------------------------------------------------
// EXISTS
// -----------------------------------------------------------------------------

bool hasActiveProject(
    int departmentId,
    const vector<Project>& projects
) {
    for (const auto& project : projects) {
        if (
            project.departmentId == departmentId &&
            project.status == "ACTIVE"
        ) {
            return true;
        }
    }

    return false;
}

bool hasSale(
    int employeeId,
    const vector<Sale>& sales
) {
    for (const auto& sale : sales) {
        if (sale.employeeId == employeeId) {
            return true;
        }
    }

    return false;
}

void demonstrateExists(
    const vector<Department>& departments,
    const vector<Project>& projects,
    const vector<Employee>& employees,
    const vector<Sale>& sales
) {
    printTitle("4. EXISTS and NOT EXISTS");

    /*
     * EXISTS does not care about the actual selected value.
     * The conceptual SQL is:
     *
     * WHERE EXISTS (
     *     SELECT 1
     *     FROM projects
     *     WHERE projects.department_id = departments.department_id
     *       AND projects.status = 'ACTIVE'
     * )
     */

    cout << "Departments with active projects:\n";

    for (const auto& department : departments) {
        if (hasActiveProject(department.id, projects)) {
            cout << department.name << "\n";
        }
    }

    cout << "\nEmployees without sales (NOT EXISTS):\n";

    for (const auto& employee : employees) {
        if (!hasSale(employee.id, sales)) {
            cout << employee.name << "\n";
        }
    }
}


// -----------------------------------------------------------------------------
// Correlated NOT EXISTS
// -----------------------------------------------------------------------------

bool hasHigherPaidEmployeeInSameDepartment(
    const Employee& employee,
    const vector<Employee>& employees
) {
    for (const auto& candidate : employees) {
        if (
            candidate.departmentId == employee.departmentId &&
            candidate.salary > employee.salary
        ) {
            return true;
        }
    }

    return false;
}

void demonstrateTopPerGroup(
    const vector<Employee>& employees
) {
    printTitle("5. Correlated NOT EXISTS for top-per-group");

    /*
     * SQL equivalent:
     *
     * WHERE NOT EXISTS (
     *     SELECT 1
     *     FROM employees AS higher
     *     WHERE higher.department_id = e.department_id
     *       AND higher.salary > e.salary
     * )
     *
     * Ties are preserved because only strictly greater salaries disqualify
     * the current row.
     */

    for (const auto& employee : employees) {
        if (
            !hasHigherPaidEmployeeInSameDepartment(
                employee,
                employees
            )
        ) {
            cout << employee.name
                 << " | department="
                 << employee.departmentId
                 << " | salary=";
            printMoney(employee.salary);
            cout << "\n";
        }
    }
}


// -----------------------------------------------------------------------------
// Nested and multi-level calculations
// -----------------------------------------------------------------------------

unordered_map<int, double> activeProjectBudgetByDepartment(
    const vector<Department>& departments,
    const vector<Project>& projects
) {
    unordered_map<int, double> result;

    for (const auto& department : departments) {
        double total = 0.0;

        for (const auto& project : projects) {
            if (
                project.departmentId == department.id &&
                project.status == "ACTIVE"
            ) {
                total += project.budget;
            }
        }

        result[department.id] = total;
    }

    return result;
}

void demonstrateMultiLevelSubquery(
    const vector<Department>& departments,
    const vector<Project>& projects,
    const vector<Employee>& employees
) {
    printTitle("6. Multi-level subquery");

    /*
     * Logical SQL levels:
     *
     * Level 1:
     *   SUM(active project budgets) per department.
     *
     * Level 2:
     *   AVG(those departmental totals).
     *
     * Level 3:
     *   Select departments above the average.
     *
     * Level 4:
     *   Select employees belonging to those departments.
     */

    const auto budgetMap =
        activeProjectBudgetByDepartment(
            departments,
            projects
        );

    vector<double> departmentBudgets;

    for (const auto& department : departments) {
        departmentBudgets.push_back(
            budgetMap.at(department.id)
        );
    }

    const double averageActiveProjectBudget =
        average(departmentBudgets);

    unordered_set<int> qualifyingDepartments;

    for (const auto& department : departments) {
        if (
            budgetMap.at(department.id) >
            averageActiveProjectBudget
        ) {
            qualifyingDepartments.insert(department.id);
        }
    }

    cout << "Average active-project budget: ";
    printMoney(averageActiveProjectBudget);
    cout << "\n\nEmployees in qualifying departments:\n";

    for (const auto& employee : employees) {
        if (
            qualifyingDepartments.contains(
                employee.departmentId
            )
        ) {
            cout << employee.name
                 << " | department="
                 << employee.departmentId
                 << "\n";
        }
    }
}


// -----------------------------------------------------------------------------
// Aggregate subquery for review performance
// -----------------------------------------------------------------------------

optional<double> bestReviewScore(
    int employeeId,
    const vector<Review>& reviews
) {
    vector<double> scores;

    for (const auto& review : reviews) {
        if (review.employeeId == employeeId) {
            scores.push_back(review.score);
        }
    }

    if (scores.empty()) {
        return nullopt;
    }

    return maximum(scores);
}

void demonstrateAggregateSubquery(
    const vector<Employee>& employees,
    const vector<Review>& reviews
) {
    printTitle("7. Aggregate subquery with optional result");

    vector<double> allScores;

    for (const auto& review : reviews) {
        allScores.push_back(review.score);
    }

    const double companyAverageReview =
        average(allScores);

    /*
     * SQL equivalent:
     *
     * SELECT e.employee_name
     * FROM employees AS e
     * WHERE (
     *     SELECT MAX(score)
     *     FROM performance_reviews AS r
     *     WHERE r.employee_id = e.employee_id
     * ) > (
     *     SELECT AVG(score)
     *     FROM performance_reviews
     * );
     */

    for (const auto& employee : employees) {
        const auto bestScore =
            bestReviewScore(employee.id, reviews);

        if (
            bestScore.has_value() &&
            *bestScore > companyAverageReview
        ) {
            cout << employee.name
                 << " | best score=";
            printMoney(*bestScore);
            cout << " | company average=";
            printMoney(companyAverageReview);
            cout << "\n";
        }
    }
}


// -----------------------------------------------------------------------------
// Derived-table case study
// -----------------------------------------------------------------------------

DepartmentMetrics calculateDepartmentMetrics(
    const Department& department,
    const vector<Employee>& employees,
    const vector<Project>& projects,
    const vector<Sale>& sales
) {
    vector<double> salaries;
    double projectBudget = 0.0;
    double totalSales = 0.0;

    for (const auto& employee : employees) {
        if (
            employee.departmentId == department.id &&
            employee.active
        ) {
            salaries.push_back(employee.salary);

            for (const auto& sale : sales) {
                if (sale.employeeId == employee.id) {
                    totalSales += sale.amount;
                }
            }
        }
    }

    for (const auto& project : projects) {
        if (
            project.departmentId == department.id &&
            project.status == "ACTIVE"
        ) {
            projectBudget += project.budget;
        }
    }

    return {
        department.id,
        department.name,
        salaries.size(),
        salaries.empty() ? 0.0 : average(salaries),
        projectBudget,
        totalSales
    };
}

vector<DepartmentMetrics> buildDepartmentMetrics(
    const vector<Department>& departments,
    const vector<Employee>& employees,
    const vector<Project>& projects,
    const vector<Sale>& sales
) {
    vector<DepartmentMetrics> metrics;

    for (const auto& department : departments) {
        metrics.push_back(
            calculateDepartmentMetrics(
                department,
                employees,
                projects,
                sales
            )
        );
    }

    return metrics;
}

void demonstrateDerivedTable(
    const vector<Department>& departments,
    const vector<Employee>& employees,
    const vector<Project>& projects,
    const vector<Sale>& sales
) {
    printTitle("8. Derived-table style processing");

    /*
     * SQL concept:
     *
     * FROM (
     *     SELECT ...
     *     FROM departments
     * ) AS department_metrics
     *
     * The C++ vector below plays the role of the intermediate relational
     * result.
     */

    const auto metrics =
        buildDepartmentMetrics(
            departments,
            employees,
            projects,
            sales
        );

    for (const auto& metric : metrics) {
        cout << metric.departmentName
             << " | employees="
             << metric.employeeCount
             << " | avg salary=";

        printMoney(metric.averageSalary);

        cout << " | active project budget=";
        printMoney(metric.activeProjectBudget);

        cout << " | sales=";
        printMoney(metric.totalSales);

        cout << "\n";
    }
}


// -----------------------------------------------------------------------------
// Advanced industry-style query
// -----------------------------------------------------------------------------

bool qualifiesForPerformanceProgram(
    const Employee& employee,
    const vector<Employee>& employees,
    const vector<Project>& projects,
    const vector<Sale>& sales,
    const vector<Review>& reviews,
    double companyAverageReview
) {
    /*
     * This function corresponds to a multi-condition SQL query containing
     * several subqueries.
     */

    if (!employee.active) {
        return false;
    }

    // Correlated scalar subquery:
    // employee salary > average salary in employee's department.
    const double departmentAverage =
        departmentAverageSalary(
            employee.departmentId,
            employees
        );

    if (employee.salary <= departmentAverage) {
        return false;
    }

    // Correlated EXISTS:
    // employee must have at least one sale.
    if (!hasSale(employee.id, sales)) {
        return false;
    }

    // Aggregate scalar subquery:
    // best review score must exceed company average.
    const auto bestScore =
        bestReviewScore(employee.id, reviews);

    if (
        !bestScore.has_value() ||
        *bestScore <= companyAverageReview
    ) {
        return false;
    }

    // Correlated EXISTS against departments/projects.
    if (!hasActiveProject(employee.departmentId, projects)) {
        return false;
    }

    return true;
}

void demonstrateAdvancedCaseStudy(
    const vector<Employee>& employees,
    const vector<Project>& projects,
    const vector<Sale>& sales,
    const vector<Review>& reviews
) {
    printTitle("9. Industry-style employee intelligence query");

    vector<double> reviewScores;

    for (const auto& review : reviews) {
        reviewScores.push_back(review.score);
    }

    const double companyAverageReview =
        average(reviewScores);

    cout << "Company average review score: ";
    printMoney(companyAverageReview);
    cout << "\n\nQualified employees:\n";

    for (const auto& employee : employees) {
        if (
            qualifiesForPerformanceProgram(
                employee,
                employees,
                projects,
                sales,
                reviews,
                companyAverageReview
            )
        ) {
            cout << employee.name
                 << " | salary=";
            printMoney(employee.salary);

            const auto score =
                bestReviewScore(employee.id, reviews);

            cout << " | best review=";
            printMoney(*score);

            cout << "\n";
        }
    }
}


// -----------------------------------------------------------------------------
// JOIN alternative
// -----------------------------------------------------------------------------

void demonstrateJoinAlternative(
    const vector<Department>& departments,
    const vector<Employee>& employees
) {
    printTitle("10. Subquery versus JOIN-style implementation");

    /*
     * Subquery:
     *
     * WHERE department_id IN (
     *     SELECT department_id
     *     FROM departments
     *     WHERE budget > 1300000
     * )
     */

    cout << "Subquery-style membership processing:\n";

    unordered_set<int> qualifyingDepartmentIds;

    for (const auto& department : departments) {
        if (department.budget > 1300000) {
            qualifyingDepartmentIds.insert(department.id);
        }
    }

    for (const auto& employee : employees) {
        if (qualifyingDepartmentIds.contains(employee.departmentId)) {
            cout << employee.name << "\n";
        }
    }

    /*
     * JOIN-style:
     * Resolve the related department and apply its predicate directly.
     */

    cout << "\nJOIN-style processing:\n";

    for (const auto& employee : employees) {
        for (const auto& department : departments) {
            if (
                department.id == employee.departmentId &&
                department.budget > 1300000
            ) {
                cout << employee.name
                     << " | "
                     << department.name
                     << "\n";
            }
        }
    }
}


// -----------------------------------------------------------------------------
// Indexing and optimized correlated lookup
// -----------------------------------------------------------------------------

unordered_map<int, vector<const Employee*>>
buildEmployeesByDepartment(
    const vector<Employee>& employees
) {
    unordered_map<int, vector<const Employee*>> index;

    for (const auto& employee : employees) {
        index[employee.departmentId].push_back(&employee);
    }

    return index;
}

void demonstrateIndexedOptimization(
    const vector<Employee>& employees
) {
    printTitle("11. Optimizing correlated access with an index");

    /*
     * A naive correlated implementation may repeatedly scan every employee.
     *
     * If there are N employees and each outer employee triggers an O(N)
     * inner scan, the simple algorithm can approach O(N²).
     *
     * A relational database can use an index on department_id. We emulate
     * that idea with unordered_map.
     */

    const auto index =
        buildEmployeesByDepartment(employees);

    size_t comparisons = 0;

    for (const auto& employee : employees) {
        const auto iterator =
            index.find(employee.departmentId);

        if (iterator == index.end()) {
            continue;
        }

        vector<double> salaries;

        for (const Employee* candidate : iterator->second) {
            ++comparisons;

            if (candidate->active) {
                salaries.push_back(candidate->salary);
            }
        }

        if (!salaries.empty()) {
            const double averageSalary =
                average(salaries);

            if (employee.salary > averageSalary) {
                cout << employee.name
                     << " is above the indexed department average.\n";
            }
        }
    }

    cout << "\nIndexed candidate comparisons: "
         << comparisons
         << "\n";
}


// -----------------------------------------------------------------------------
// NULL and three-valued logic
// -----------------------------------------------------------------------------

void demonstrateNullLikeSemantics(
    const vector<Employee>& employees
) {
    printTitle("12. NULL-like optional values");

    /*
     * SQL NULL represents an unknown or missing value.
     *
     * C++ std::optional is useful for modeling the presence/absence of a
     * value, but it is not a complete implementation of SQL's three-valued
     * logic.
     *
     * In SQL:
     *
     *     salary = NULL
     *
     * is UNKNOWN.
     *
     * Correct SQL tests use:
     *
     *     salary IS NULL
     *     salary IS NOT NULL
     *
     * C++ optional makes absence explicit through has_value().
     */

    for (const auto& employee : employees) {
        if (!employee.managerId.has_value()) {
            cout << employee.name
                 << " has no recorded manager.\n";
        }
    }
}


// -----------------------------------------------------------------------------
// Automated tests
// -----------------------------------------------------------------------------

void assertCondition(bool condition, const string& message) {
    if (!condition) {
        throw runtime_error("Test failure: " + message);
    }
}

void runTests(
    const vector<Department>& departments,
    const vector<Employee>& employees,
    const vector<Project>& projects,
    const vector<Sale>& sales,
    const vector<Review>& reviews
) {
    printTitle("13. Automated validation tests");

    const double companyAverage =
        companyAverageSalary(employees);

    size_t aboveAverageCount = 0;

    for (const auto& employee : employees) {
        if (
            employee.salary > companyAverage
        ) {
            ++aboveAverageCount;
        }
    }

    assertCondition(
        aboveAverageCount > 0,
        "At least one employee must exceed company average"
    );

    size_t activeProjectDepartments = 0;

    for (const auto& department : departments) {
        if (hasActiveProject(department.id, projects)) {
            ++activeProjectDepartments;
        }
    }

    assertCondition(
        activeProjectDepartments > 0,
        "At least one department must have an active project"
    );

    for (const auto& employee : employees) {
        const double departmentAverage =
            departmentAverageSalary(
                employee.departmentId,
                employees
            );

        assertCondition(
            departmentAverage > 0,
            "Department average salary must be positive"
        );
    }

    vector<double> scores;

    for (const auto& review : reviews) {
        scores.push_back(review.score);
    }

    assertCondition(
        !scores.empty(),
        "Review data must not be empty"
    );

    cout << "All C++ case-study tests passed.\n";

    (void)sales;
}


// -----------------------------------------------------------------------------
// Main application
// -----------------------------------------------------------------------------

int main() {
    try {
        printTitle(
            "SQL SUBQUERIES: C++ RELATIONAL CASE STUDY"
        );

        const auto departments = createDepartments();
        const auto employees = createEmployees();
        const auto projects = createProjects();
        const auto sales = createSales();
        const auto reviews = createReviews();

        validateData(
            departments,
            employees,
            projects,
            sales,
            reviews
        );

        demonstrateScalarSubquery(employees);

        demonstrateCorrelatedSubquery(
            employees
        );

        demonstrateInSubquery(
            departments,
            employees
        );

        demonstrateExists(
            departments,
            projects,
            employees,
            sales
        );

        demonstrateTopPerGroup(
            employees
        );

        demonstrateMultiLevelSubquery(
            departments,
            projects,
            employees
        );

        demonstrateAggregateSubquery(
            employees,
            reviews
        );

        demonstrateDerivedTable(
            departments,
            employees,
            projects,
            sales
        );

        demonstrateAdvancedCaseStudy(
            employees,
            projects,
            sales,
            reviews
        );

        demonstrateJoinAlternative(
            departments,
            employees
        );

        demonstrateIndexedOptimization(
            employees
        );

        demonstrateNullLikeSemantics(
            employees
        );

        runTests(
            departments,
            employees,
            projects,
            sales,
            reviews
        );

        printTitle("14. Architectural observations");

        cout << R"(
Scalar subqueries return a single value and are useful for reference
calculations such as averages, maximums, counts, and thresholds.

IN subqueries return a set of values used for membership testing.

EXISTS and NOT EXISTS answer existence questions and are particularly useful
for correlated relationships.

Correlated subqueries depend on values from the outer row. The logical
execution model can resemble repeated inner evaluation, although a database
optimizer may transform the query.

Nested and multi-level subqueries allow one calculation to become the input
to another calculation. They can express complex business rules but may
become difficult to maintain when deeply nested.

JOINs, CTEs, derived tables, and window functions can often express the same
business logic more directly. The best form depends on semantics, clarity,
database optimizer behavior, data volume, indexes, and measured performance.

In production systems, parameterized SQL, explicit NULL handling, indexes,
query-plan inspection, realistic test data, and database-specific testing
are essential.
)";

        return 0;
    }
    catch (const exception& error) {
        cerr << "\nApplication error: "
             << error.what()
             << "\n";

        return 1;
    }
}
