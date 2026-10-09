#include <algorithm>
#include <cctype>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * Repository-independent enterprise data-quality case study:
 * employee onboarding for a multi-department organization.
 *
 * The core engine uses explicit validation results, normalized unique keys,
 * integer minor currency units, and staged commits.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic data_quality.cpp -o data_quality
 */

struct ValidationIssue {
    std::string rule;
    std::string field;
    std::string message;
};

struct EmployeeInput {
    std::string employeeCode;
    std::string email;
    std::string fullName;
    int age{};
    std::string salary;
    std::string department;
    bool active{true};
};

struct Employee {
    int id{};
    std::string employeeCode;
    std::string email;
    std::string fullName;
    int age{};
    long long salaryCents{};
    std::string department;
    bool active{};
};

struct ValidationResult {
    std::optional<Employee> employee;
    std::vector<ValidationIssue> issues;

    bool valid() const {
        return employee.has_value() && issues.empty();
    }
};

std::string trim(const std::string& value) {
    const auto first = std::find_if_not(
        value.begin(), value.end(),
        [](unsigned char ch) { return std::isspace(ch); }
    );

    const auto last = std::find_if_not(
        value.rbegin(), value.rend(),
        [](unsigned char ch) { return std::isspace(ch); }
    ).base();

    if (first >= last) {
        return "";
    }

    return std::string(first, last);
}

std::string uppercase(std::string value) {
    std::transform(
        value.begin(), value.end(), value.begin(),
        [](unsigned char ch) {
            return static_cast<char>(std::toupper(ch));
        }
    );
    return value;
}

std::string lowercase(std::string value) {
    std::transform(
        value.begin(), value.end(), value.begin(),
        [](unsigned char ch) {
            return static_cast<char>(std::tolower(ch));
        }
    );
    return value;
}

bool validEmailShape(const std::string& email) {
    if (email.empty() || email.size() > 254) {
        return false;
    }

    const auto at = email.find('@');

    if (at == std::string::npos ||
        at == 0 ||
        at != email.rfind('@') ||
        at + 1 >= email.size()) {
        return false;
    }

    const auto dot = email.find('.', at + 1);

    if (dot == std::string::npos ||
        dot == at + 1 ||
        dot + 1 >= email.size()) {
        return false;
    }

    return std::none_of(
        email.begin(), email.end(),
        [](unsigned char ch) { return std::isspace(ch); }
    );
}

std::optional<long long> parseMoneyCents(const std::string& input) {
    const std::string value = trim(input);

    if (value.empty() || value.front() == '-') {
        return std::nullopt;
    }

    std::size_t position = 0;
    long long whole = 0;

    while (position < value.size() &&
           std::isdigit(static_cast<unsigned char>(value[position]))) {
        const int digit = value[position] - '0';

        if (whole > (9223372036854775807LL / 100 - digit) / 10) {
            return std::nullopt;
        }

        whole = whole * 10 + digit;
        ++position;
    }

    if (position == 0) {
        return std::nullopt;
    }

    int cents = 0;

    if (position < value.size() && value[position] == '.') {
        ++position;

        if (position >= value.size() ||
            !std::isdigit(static_cast<unsigned char>(value[position]))) {
            return std::nullopt;
        }

        cents = (value[position] - '0') * 10;
        ++position;

        if (position < value.size() &&
            std::isdigit(static_cast<unsigned char>(value[position]))) {
            cents += value[position] - '0';
            ++position;
        }
    }

    if (position != value.size()) {
        return std::nullopt;
    }

    if (whole > (9223372036854775807LL - cents) / 100) {
        return std::nullopt;
    }

    return whole * 100 + cents;
}

ValidationResult validateInput(const EmployeeInput& input) {
    ValidationResult result;

    Employee employee;
    employee.employeeCode = uppercase(trim(input.employeeCode));
    employee.email = lowercase(trim(input.email));
    employee.fullName = trim(input.fullName);
    employee.age = input.age;
    employee.department = trim(input.department);
    employee.active = input.active;

    if (employee.employeeCode.empty() ||
        employee.employeeCode.size() > 20) {
        result.issues.push_back({
            "EMPLOYEE_CODE_LENGTH", "employeeCode",
            "Employee code must contain 1 to 20 characters."
        });
    }

    if (!validEmailShape(employee.email)) {
        result.issues.push_back({
            "EMAIL_FORMAT", "email",
            "Email has an invalid basic structure."
        });
    }

    if (employee.fullName.empty() || employee.fullName.size() > 100) {
        result.issues.push_back({
            "FULL_NAME_LENGTH", "fullName",
            "Full name must contain 1 to 100 characters."
        });
    }

    if (employee.age < 18 || employee.age > 100) {
        result.issues.push_back({
            "AGE_RANGE", "age",
            "Age must be between 18 and 100."
        });
    }

    if (employee.department.empty() || employee.department.size() > 50) {
        result.issues.push_back({
            "DEPARTMENT_LENGTH", "department",
            "Department must contain 1 to 50 characters."
        });
    }

    const auto salary = parseMoneyCents(input.salary);

    if (!salary) {
        result.issues.push_back({
            "SALARY_FORMAT", "salary",
            "Salary must be a nonnegative decimal with at most two fractional digits."
        });
    } else {
        employee.salaryCents = *salary;
    }

    if (result.issues.empty()) {
        result.employee = employee;
    }

    return result;
}

class EmployeeQualityEngine {
private:
    std::set<std::string> departments_;
    std::unordered_map<std::string, int> codeIndex_;
    std::unordered_map<std::string, int> emailIndex_;
    std::map<int, Employee> employees_;
    std::vector<ValidationIssue> audit_;
    int nextId_{1};

    void auditIssues(const std::vector<ValidationIssue>& issues) {
        audit_.insert(audit_.end(), issues.begin(), issues.end());
    }

public:
    EmployeeQualityEngine()
        : departments_{"Engineering", "Finance", "Operations"} {}

    bool add(const EmployeeInput& input) {
        ValidationResult validation = validateInput(input);

        if (!validation.valid()) {
            auditIssues(validation.issues);

            for (const auto& issue : validation.issues) {
                std::cout << "Rejected [" << issue.rule << "] "
                          << issue.field << ": "
                          << issue.message << '\n';
            }

            return false;
        }

        Employee candidate = *validation.employee;

        // Unique checks use canonicalized values. Raw input must not be used
        // as the index key because casing and whitespace can differ.
        if (codeIndex_.count(candidate.employeeCode) != 0) {
            audit_.push_back({
                "UNIQUE_EMPLOYEE_CODE", "employeeCode",
                "Employee code already exists."
            });
            std::cout << "Rejected [UNIQUE_EMPLOYEE_CODE]: "
                      << candidate.employeeCode << '\n';
            return false;
        }

        if (emailIndex_.count(candidate.email) != 0) {
            audit_.push_back({
                "UNIQUE_EMAIL", "email",
                "Email already exists."
            });
            std::cout << "Rejected [UNIQUE_EMAIL]: "
                      << candidate.email << '\n';
            return false;
        }

        if (departments_.count(candidate.department) == 0) {
            audit_.push_back({
                "FOREIGN_KEY_DEPARTMENT", "department",
                "Department does not exist."
            });
            std::cout << "Rejected [FOREIGN_KEY_DEPARTMENT]: "
                      << candidate.department << '\n';
            return false;
        }

        candidate.id = nextId_;

        // All domain checks are completed before mutation. A production
        // multi-threaded implementation would also require synchronization.
        employees_.emplace(candidate.id, candidate);
        codeIndex_.emplace(candidate.employeeCode, candidate.id);
        emailIndex_.emplace(candidate.email, candidate.id);
        ++nextId_;

        std::cout << "Accepted " << candidate.employeeCode
                  << " as employee ID " << candidate.id << '\n';

        return true;
    }

    bool updateSalary(const std::string& code, const std::string& amount) {
        const std::string normalizedCode = uppercase(trim(code));
        const auto found = codeIndex_.find(normalizedCode);

        if (found == codeIndex_.end()) {
            std::cout << "Salary update rejected: employee not found.\n";
            return false;
        }

        const auto cents = parseMoneyCents(amount);

        if (!cents) {
            audit_.push_back({
                "SALARY_FORMAT", "salary",
                "Salary update must be nonnegative with at most two decimals."
            });
            std::cout << "Salary update rejected: invalid monetary value.\n";
            return false;
        }

        employees_.at(found->second).salaryCents = *cents;
        return true;
    }

    std::vector<Employee> findDepartment(
        const std::string& department,
        bool activeOnly
    ) const {
        std::vector<Employee> matches;

        for (const auto& entry : employees_) {
            const Employee& employee = entry.second;

            if (employee.department == department &&
                (!activeOnly || employee.active)) {
                matches.push_back(employee);
            }
        }

        return matches;
    }

    void printQualityMetrics() const {
        std::map<std::string, int> counts;
        std::map<std::string, long long> salaryTotals;

        for (const auto& entry : employees_) {
            const Employee& employee = entry.second;
            ++counts[employee.department];
            salaryTotals[employee.department] += employee.salaryCents;
        }

        std::cout << "\nDepartment quality metrics\n";

        for (const auto& entry : counts) {
            const auto total = salaryTotals.at(entry.first);

            std::cout << entry.first
                      << ": employee_count=" << entry.second
                      << ", average_salary="
                      << std::fixed << std::setprecision(2)
                      << static_cast<double>(total) /
                             static_cast<double>(entry.second) / 100.0
                      << '\n';
        }

        std::cout << "Rejected rule evaluations: "
                  << audit_.size() << '\n';
    }

    void printEmployees(const std::vector<Employee>& employees) const {
        for (const auto& employee : employees) {
            std::cout << employee.employeeCode << " | "
                      << employee.fullName << " | "
                      << employee.department << " | "
                      << std::fixed << std::setprecision(2)
                      << static_cast<double>(employee.salaryCents) / 100.0
                      << " | active="
                      << (employee.active ? "true" : "false")
                      << '\n';
        }
    }

    std::size_t size() const {
        return employees_.size();
    }
};

int main() {
    EmployeeQualityEngine engine;

    const std::vector<EmployeeInput> onboardingBatch = {
        {"E-301", "ALICE@example.com", "Alice Sharma", 32,
         "65000.00", "Engineering", true},
        {"E-302", "rahul@example.com", "Rahul Verma", 41,
         "82000.00", "Finance", true},
        {"E-303", "meera@example.com", "Meera Singh", 27,
         "54000.00", "Operations", false},
        {"E-301", "duplicate@example.com", "Duplicate Code", 30,
         "40000.00", "Finance", true},
        {"E-304", "alice@EXAMPLE.com", "Duplicate Email", 30,
         "40000.00", "Engineering", true},
        {"E-305", "underage@example.com", "Underage Applicant", 17,
         "35000.00", "Finance", true},
        {"E-306", "unknown@example.com", "Unknown Department", 29,
         "45000.00", "Legal", true},
        {"E-307", "negative@example.com", "Negative Salary", 35,
         "-200.00", "Operations", true},
        {"E-308", "precision@example.com", "Excess Precision", 35,
         "500.999", "Operations", true}
    };

    std::cout << "Employee onboarding quality engine\n";

    for (const auto& input : onboardingBatch) {
        engine.add(input);
    }

    std::cout << "\nActive Engineering employees\n";
    engine.printEmployees(engine.findDepartment("Engineering", true));

    std::cout << "\nSalary correction\n";

    if (engine.updateSalary("E-301", "68000.00")) {
        std::cout << "Salary updated successfully.\n";
    }

    engine.updateSalary("E-301", "-1.00");
    engine.updateSalary("E-999", "50000.00");

    engine.printQualityMetrics();

    std::cout << "\nFinal employee count: " << engine.size() << '\n';

    return 0;
}
