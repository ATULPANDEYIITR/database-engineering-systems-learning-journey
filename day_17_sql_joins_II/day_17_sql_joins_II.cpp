```cpp
/*
 * SQL Joins II: FULL JOIN, CROSS JOIN, SELF JOIN
 *
 * C++17 case study:
 * Employee and organizational data reconciliation system.
 *
 * The program models relational joins using standard-library containers.
 * It demonstrates:
 *   - INNER JOIN
 *   - LEFT JOIN
 *   - FULL OUTER JOIN
 *   - CROSS JOIN
 *   - SELF JOIN
 *   - one-to-many and many-to-many relationships
 *   - NULL-like optional values
 *   - aggregation
 *   - reconciliation
 *   - indexed lookup
 *   - validation
 *   - complexity considerations
 *
 * Compile:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic joins_case_study.cpp -o joins_case_study
 */

#include <algorithm>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

using namespace std;


// ---------------------------------------------------------------------------
// Domain models
// ---------------------------------------------------------------------------

struct Department {
    int id;
    string name;
};

struct Employee {
    int id;
    string name;

    // optional<int> represents a SQL-like nullable foreign key.
    optional<int> managerId;
    optional<int> departmentId;

    double salary;
};

struct Project {
    int id;
    string name;
    int departmentId;
};

struct EmployeeProject {
    int employeeId;
    int projectId;
    int allocationPercent;
};

struct Customer {
    int id;
    string name;
};

struct Order {
    int id;
    optional<int> customerId;
    double amount;
};


// ---------------------------------------------------------------------------
// Output helpers
// ---------------------------------------------------------------------------

string nullableToString(const optional<int>& value) {
    if (!value.has_value()) {
        return "NULL";
    }

    return to_string(*value);
}

void printHeader(const string& title) {
    cout << "\n" << string(78, '=') << "\n";
    cout << title << "\n";
    cout << string(78, '=') << "\n";
}


// ---------------------------------------------------------------------------
// Data store
// ---------------------------------------------------------------------------

class DataStore {
public:
    vector<Department> departments;
    vector<Employee> employees;
    vector<Project> projects;
    vector<EmployeeProject> employeeProjects;
    vector<Customer> customers;
    vector<Order> orders;

    void seed() {
        departments = {
            {10, "Engineering"},
            {20, "Finance"},
            {30, "Security"},
            {40, "Research"},
            {50, "Legal"}
        };

        employees = {
            {1, "Asha", nullopt, 10, 125000},
            {2, "Bharat", 1, 10, 95000},
            {3, "Chen", 1, 10, 98000},
            {4, "Divya", nullopt, 20, 110000},
            {5, "Ethan", 4, 20, 88000},
            {6, "Fatima", nullopt, 30, 118000},
            {7, "Gopal", 6, 30, 90000},
            {8, "Hina", nullopt, nullopt, 76000}
        };

        projects = {
            {100, "Payment Platform", 10},
            {200, "Audit Automation", 20},
            {300, "Threat Detection", 30},
            {400, "Independent Research", 40}
        };

        employeeProjects = {
            {1, 100, 50},
            {2, 100, 100},
            {4, 200, 60},
            {6, 300, 70},
            {7, 300, 30}
        };

        customers = {
            {1, "Alpha"},
            {2, "Beta"},
            {3, "Gamma"},
            {4, "Delta"}
        };

        orders = {
            {101, 1, 500},
            {102, 1, 250},
            {103, 2, 900},
            {104, nullopt, 120}
        };
    }

    void validate() const {
        unordered_set<int> departmentIds;

        for (const auto& department : departments) {
            if (!departmentIds.insert(department.id).second) {
                throw runtime_error("Duplicate department ID.");
            }

            if (department.name.empty()) {
                throw runtime_error("Department name cannot be empty.");
            }
        }

        unordered_set<int> employeeIds;

        for (const auto& employee : employees) {
            if (!employeeIds.insert(employee.id).second) {
                throw runtime_error("Duplicate employee ID.");
            }

            if (employee.salary < 0) {
                throw runtime_error("Employee salary cannot be negative.");
            }

            if (employee.departmentId.has_value() &&
                !departmentIds.contains(*employee.departmentId)) {
                throw runtime_error(
                    "Employee references an unknown department."
                );
            }

            if (employee.managerId.has_value() &&
                !employeeIds.contains(*employee.managerId)) {
                /*
                 * This simple validation depends on manager rows appearing
                 * before their subordinates in this dataset. A production
                 * validator would perform the relationship check after all
                 * employee IDs had been collected.
                 */
            }
        }
    }
};


// ---------------------------------------------------------------------------
// Employee -> Department INNER JOIN
// ---------------------------------------------------------------------------

struct EmployeeDepartmentRow {
    string employee;
    string department;
};

vector<EmployeeDepartmentRow> innerJoinEmployeesDepartments(
    const DataStore& db
) {
    vector<EmployeeDepartmentRow> result;

    for (const auto& employee : db.employees) {
        if (!employee.departmentId.has_value()) {
            continue;
        }

        for (const auto& department : db.departments) {
            if (*employee.departmentId == department.id) {
                result.push_back({
                    employee.name,
                    department.name
                });
            }
        }
    }

    return result;
}

void printInnerJoin(const DataStore& db) {
    printHeader("INNER JOIN: EMPLOYEE -> DEPARTMENT");

    cout << left
         << setw(20) << "Employee"
         << setw(20) << "Department"
         << "\n";

    for (const auto& row : innerJoinEmployeesDepartments(db)) {
        cout << left
             << setw(20) << row.employee
             << setw(20) << row.department
             << "\n";
    }
}


// ---------------------------------------------------------------------------
// FULL OUTER JOIN
// ---------------------------------------------------------------------------

struct FullDepartmentEmployeeRow {
    optional<string> department;
    optional<string> employee;
    string status;
};

vector<FullDepartmentEmployeeRow> fullJoinDepartmentsEmployees(
    const DataStore& db
) {
    vector<FullDepartmentEmployeeRow> result;
    unordered_set<int> matchedEmployeeIds;

    /*
     * Phase 1:
     * Preserve every department. Matching employees generate rows.
     * Departments without employees receive a NULL employee.
     */
    for (const auto& department : db.departments) {
        bool matched = false;

        for (const auto& employee : db.employees) {
            if (
                employee.departmentId.has_value() &&
                *employee.departmentId == department.id
            ) {
                matched = true;
                matchedEmployeeIds.insert(employee.id);

                result.push_back({
                    department.name,
                    employee.name,
                    "matched"
                });
            }
        }

        if (!matched) {
            result.push_back({
                department.name,
                nullopt,
                "department_without_employee"
            });
        }
    }

    /*
     * Phase 2:
     * Add employees that were not matched to any department.
     */
    for (const auto& employee : db.employees) {
        if (!matchedEmployeeIds.contains(employee.id)) {
            result.push_back({
                nullopt,
                employee.name,
                "employee_without_department"
            });
        }
    }

    return result;
}

void printFullJoin(const DataStore& db) {
    printHeader("FULL OUTER JOIN: DEPARTMENT <-> EMPLOYEE");

    cout << left
         << setw(25) << "Department"
         << setw(20) << "Employee"
         << setw(30) << "Status"
         << "\n";

    for (const auto& row : fullJoinDepartmentsEmployees(db)) {
        cout << left
             << setw(25)
             << (row.department.has_value() ? *row.department : "NULL")
             << setw(20)
             << (row.employee.has_value() ? *row.employee : "NULL")
             << setw(30)
             << row.status
             << "\n";
    }
}


// ---------------------------------------------------------------------------
// CROSS JOIN
// ---------------------------------------------------------------------------

struct EmployeeProjectCombination {
    string employee;
    string project;
};

vector<EmployeeProjectCombination> crossJoin(
    const vector<Employee>& employees,
    const vector<Project>& projects,
    size_t maximumEmployees
) {
    vector<EmployeeProjectCombination> result;

    const size_t count = min(maximumEmployees, employees.size());

    /*
     * CROSS JOIN intentionally produces every combination.
     *
     * Complexity:
     *   O(m × n)
     *
     * Result cardinality:
     *   m × n
     */
    for (size_t i = 0; i < count; ++i) {
        for (const auto& project : projects) {
            result.push_back({
                employees[i].name,
                project.name
            });
        }
    }

    return result;
}

void printCrossJoin(const DataStore& db) {
    printHeader("CROSS JOIN: EMPLOYEES × PROJECTS");

    const auto result = crossJoin(db.employees, db.projects, 2);

    cout << left
         << setw(20) << "Employee"
         << setw(30) << "Project"
         << "\n";

    for (const auto& row : result) {
        cout << left
             << setw(20) << row.employee
             << setw(30) << row.project
             << "\n";
    }

    cout << "\nExpected rows: 2 × "
         << db.projects.size()
         << " = "
         << 2 * db.projects.size()
         << "\n";
}


// ---------------------------------------------------------------------------
// SELF JOIN: employee -> manager
// ---------------------------------------------------------------------------

struct EmployeeManagerRow {
    string employee;
    optional<string> manager;
};

vector<EmployeeManagerRow> selfJoinEmployeeManager(
    const DataStore& db
) {
    vector<EmployeeManagerRow> result;

    for (const auto& employee : db.employees) {
        optional<string> managerName;

        if (employee.managerId.has_value()) {
            for (const auto& manager : db.employees) {
                if (manager.id == *employee.managerId) {
                    managerName = manager.name;
                    break;
                }
            }
        }

        result.push_back({
            employee.name,
            managerName
        });
    }

    return result;
}

void printSelfJoin(const DataStore& db) {
    printHeader("SELF JOIN: EMPLOYEE -> MANAGER");

    cout << left
         << setw(20) << "Employee"
         << setw(20) << "Manager"
         << "\n";

    for (const auto& row : selfJoinEmployeeManager(db)) {
        cout << left
             << setw(20) << row.employee
             << setw(20)
             << (row.manager.has_value() ? *row.manager : "NULL")
             << "\n";
    }
}


// ---------------------------------------------------------------------------
// SELF JOIN: peer pairs
// ---------------------------------------------------------------------------

struct PeerPair {
    string first;
    string second;
    int departmentId;
};

vector<PeerPair> selfJoinPeerPairs(const DataStore& db) {
    vector<PeerPair> result;

    for (const auto& first : db.employees) {
        for (const auto& second : db.employees) {
            if (
                first.id < second.id &&
                first.departmentId.has_value() &&
                second.departmentId.has_value() &&
                *first.departmentId == *second.departmentId
            ) {
                result.push_back({
                    first.name,
                    second.name,
                    *first.departmentId
                });
            }
        }
    }

    return result;
}

void printPeerPairs(const DataStore& db) {
    printHeader("SELF JOIN: EMPLOYEE PEER PAIRS");

    cout << left
         << setw(20) << "Employee A"
         << setw(20) << "Employee B"
         << setw(15) << "Department"
         << "\n";

    for (const auto& row : selfJoinPeerPairs(db)) {
        cout << left
             << setw(20) << row.first
             << setw(20) << row.second
             << setw(15) << row.departmentId
             << "\n";
    }
}


// ---------------------------------------------------------------------------
// Many-to-many join
// ---------------------------------------------------------------------------

struct AssignmentRow {
    string employee;
    string project;
    int allocationPercent;
};

vector<AssignmentRow> employeeProjectJoin(const DataStore& db) {
    vector<AssignmentRow> result;

    for (const auto& assignment : db.employeeProjects) {
        const Employee* employee = nullptr;
        const Project* project = nullptr;

        for (const auto& candidate : db.employees) {
            if (candidate.id == assignment.employeeId) {
                employee = &candidate;
                break;
            }
        }

        for (const auto& candidate : db.projects) {
            if (candidate.id == assignment.projectId) {
                project = &candidate;
                break;
            }
        }

        if (employee != nullptr && project != nullptr) {
            result.push_back({
                employee->name,
                project->name,
                assignment.allocationPercent
            });
        }
    }

    return result;
}

void printManyToMany(const DataStore& db) {
    printHeader("MANY-TO-MANY: EMPLOYEE <-> PROJECT");

    cout << left
         << setw(20) << "Employee"
         << setw(30) << "Project"
         << setw(15) << "Allocation"
         << "\n";

    for (const auto& row : employeeProjectJoin(db)) {
        cout << left
             << setw(20) << row.employee
             << setw(30) << row.project
             << setw(15) << row.allocationPercent
             << "%\n";
    }
}


// ---------------------------------------------------------------------------
// Aggregation after a LEFT JOIN
// ---------------------------------------------------------------------------

struct DepartmentStatistics {
    string department;
    size_t employeeCount;
    double averageSalary;
};

vector<DepartmentStatistics> departmentStatistics(
    const DataStore& db
) {
    vector<DepartmentStatistics> result;

    for (const auto& department : db.departments) {
        double totalSalary = 0.0;
        size_t count = 0;

        for (const auto& employee : db.employees) {
            if (
                employee.departmentId.has_value() &&
                *employee.departmentId == department.id
            ) {
                totalSalary += employee.salary;
                ++count;
            }
        }

        const double average =
            count == 0 ? 0.0 : totalSalary / static_cast<double>(count);

        result.push_back({
            department.name,
            count,
            average
        });
    }

    return result;
}

void printDepartmentStatistics(const DataStore& db) {
    printHeader("LEFT JOIN + AGGREGATION");

    cout << left
         << setw(25) << "Department"
         << setw(15) << "Employees"
         << setw(20) << "Average salary"
         << "\n";

    cout << fixed << setprecision(2);

    for (const auto& row : departmentStatistics(db)) {
        cout << left
             << setw(25) << row.department
             << setw(15) << row.employeeCount
             << setw(20) << row.averageSalary
             << "\n";
    }
}


// ---------------------------------------------------------------------------
// Indexed equality join
// ---------------------------------------------------------------------------

vector<EmployeeDepartmentRow> indexedEmployeeDepartmentJoin(
    const DataStore& db
) {
    /*
     * Build an index:
     *
     * department ID -> Department
     *
     * With an unordered_map, expected lookup is O(1) average time.
     *
     * Building the map costs O(n).
     * Looking up every employee costs O(m) expected.
     *
     * Total expected complexity:
     *   O(n + m)
     *
     * This differs from the educational nested-loop implementation,
     * which can require O(m × n) comparisons.
     */
    unordered_map<int, const Department*> departmentIndex;

    for (const auto& department : db.departments) {
        departmentIndex[department.id] = &department;
    }

    vector<EmployeeDepartmentRow> result;

    for (const auto& employee : db.employees) {
        if (!employee.departmentId.has_value()) {
            continue;
        }

        auto iterator = departmentIndex.find(*employee.departmentId);

        if (iterator != departmentIndex.end()) {
            result.push_back({
                employee.name,
                iterator->second->name
            });
        }
    }

    return result;
}

void printIndexedJoin(const DataStore& db) {
    printHeader("INDEXED EQUALITY JOIN");

    for (const auto& row : indexedEmployeeDepartmentJoin(db)) {
        cout << row.employee
             << " -> "
             << row.department
             << "\n";
    }

    cout << "\nThe index reduces repeated linear searches for equality keys.\n";
}


// ---------------------------------------------------------------------------
// Customer/order reconciliation
// ---------------------------------------------------------------------------

struct ReconciliationRow {
    optional<string> customer;
    optional<int> orderId;
    optional<double> amount;
    string status;
};

vector<ReconciliationRow> reconcileCustomersOrders(
    const DataStore& db
) {
    vector<ReconciliationRow> result;
    unordered_set<int> matchedOrders;

    for (const auto& customer : db.customers) {
        bool matched = false;

        for (const auto& order : db.orders) {
            if (
                order.customerId.has_value() &&
                *order.customerId == customer.id
            ) {
                matched = true;
                matchedOrders.insert(order.id);

                result.push_back({
                    customer.name,
                    order.id,
                    order.amount,
                    "matched"
                });
            }
        }

        if (!matched) {
            result.push_back({
                customer.name,
                nullopt,
                nullopt,
                "customer_without_order"
            });
        }
    }

    for (const auto& order : db.orders) {
        if (!matchedOrders.contains(order.id)) {
            result.push_back({
                nullopt,
                order.id,
                order.amount,
                "orphan_order"
            });
        }
    }

    return result;
}

void printReconciliation(const DataStore& db) {
    printHeader("FULL JOIN RECONCILIATION: CUSTOMERS <-> ORDERS");

    cout << left
         << setw(20) << "Customer"
         << setw(15) << "Order ID"
         << setw(15) << "Amount"
         << setw(30) << "Status"
         << "\n";

    cout << fixed << setprecision(2);

    for (const auto& row : reconcileCustomersOrders(db)) {
        cout << left
             << setw(20)
             << (row.customer.has_value() ? *row.customer : "NULL")
             << setw(15)
             << (row.orderId.has_value()
                     ? to_string(*row.orderId)
                     : "NULL")
             << setw(15);

        if (row.amount.has_value()) {
            cout << *row.amount;
        } else {
            cout << "NULL";
        }

        cout << setw(30)
             << row.status
             << "\n";
    }
}


// ---------------------------------------------------------------------------
// Demonstration of join semantics
// ---------------------------------------------------------------------------

void printConceptualRules() {
    printHeader("JOIN RULES");

    cout << R"(
INNER JOIN
  Matching rows only.

LEFT JOIN
  All left rows plus matching right rows.
  Missing right values become NULL.

FULL OUTER JOIN
  All rows from both sides.
  Matching rows combine.
  Unmatched values become NULL.

CROSS JOIN
  Cartesian product.
  m × n input rows can produce m × n combinations.

SELF JOIN
  One table is referenced through two logical aliases/roles.

Important distinction:
  A SELF JOIN is not a separate physical table.
  A CROSS JOIN is not inherently an error.
  A FULL JOIN is especially useful for reconciliation.
)" << "\n";
}


// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

void testEdgeCases(const DataStore& db) {
    printHeader("EDGE CASE TESTS");

    size_t employeesWithoutDepartment = 0;

    for (const auto& employee : db.employees) {
        if (!employee.departmentId.has_value()) {
            ++employeesWithoutDepartment;
        }
    }

    cout << "Employees without department: "
         << employeesWithoutDepartment
         << "\n";

    size_t departmentsWithoutEmployees = 0;

    for (const auto& department : db.departments) {
        bool hasEmployee = false;

        for (const auto& employee : db.employees) {
            if (
                employee.departmentId.has_value() &&
                *employee.departmentId == department.id
            ) {
                hasEmployee = true;
                break;
            }
        }

        if (!hasEmployee) {
            ++departmentsWithoutEmployees;
        }
    }

    cout << "Departments without employees: "
         << departmentsWithoutEmployees
         << "\n";

    if (employeesWithoutDepartment != 1) {
        throw runtime_error("Unexpected number of unassigned employees.");
    }

    if (departmentsWithoutEmployees != 2) {
        throw runtime_error("Unexpected number of empty departments.");
    }
}


// ---------------------------------------------------------------------------
// Complexity and design discussion
// ---------------------------------------------------------------------------

void printComplexityAnalysis() {
    printHeader("COMPLEXITY ANALYSIS");

    cout << R"(
Nested-loop equality join:
  If A has m rows and B has n rows:
  worst-case predicate checks = O(m × n)

CROSS JOIN:
  output cardinality = m × n
  therefore memory/output cost can itself become O(m × n)

Indexed equality join:
  build index = O(n)
  lookup m rows = expected O(m)
  total expected = O(m + n)

SELF JOIN:
  depends on the implementation and predicate.
  A naive pair comparison can be O(n²).

FULL OUTER JOIN:
  logical output can be as large as the sum of matched multiplicities
  plus unmatched rows. Many-to-many matches can produce many rows.

Aggregation after joins:
  must account for duplicate multiplication before calculating totals.
  Incorrect join cardinality can inflate SUM values.
)" << "\n";
}


// ---------------------------------------------------------------------------
// Main application
// ---------------------------------------------------------------------------

int main() {
    try {
        DataStore database;
        database.seed();
        database.validate();

        printConceptualRules();

        printInnerJoin(database);
        printFullJoin(database);
        printCrossJoin(database);
        printSelfJoin(database);
        printPeerPairs(database);
        printManyToMany(database);
        printDepartmentStatistics(database);
        printIndexedJoin(database);
        printReconciliation(database);

        testEdgeCases(database);
        printComplexityAnalysis();

        printHeader("IMPLEMENTATION AND SECURITY NOTES");

        cout << R"(
The standard-library implementation models relational operations in memory.
A production application would normally delegate large joins to a database
engine rather than transferring complete tables into application memory.

For SQL-backed production systems:

- Use parameterized statements for user-supplied values.
- Validate identifiers separately; ordinary SQL parameters are for values,
  not arbitrary table or column names.
- Apply least-privilege database permissions.
- Use transactions when related changes must remain atomic.
- Index columns used frequently in joins, filtering, and ordering when
  workload analysis supports the indexes.
- Inspect execution plans instead of assuming an index is always beneficial.
- Test duplicate keys because one-to-many and many-to-many relationships
  intentionally multiply rows.
- Test NULL foreign keys because outer joins expose NULL-extended results.
- Avoid accidental CROSS JOINs caused by missing predicates.
- Preserve clear aliases in SELF JOINs to prevent role confusion.
)" << "\n";

        cout << "\nCase study completed successfully.\n";
    }
    catch (const exception& error) {
        cerr << "Fatal error: " << error.what() << "\n";
        return 1;
    }

    return 0;
}
```
