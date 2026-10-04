/*
 * Normalization I: Functional Dependencies and Anomalies
 *
 * C++17 technical case study:
 * A university registrar stores student, course, section, instructor, and
 * enrollment facts. The initial relation combines facts with different
 * determinants, creating redundancy and anomalies. The program builds an
 * FD-aware governance engine that computes closures, candidate keys,
 * identifies dependency violations, and produces normalized projections.
 *
 * Compile:
 *     g++ -std=c++17 -O2 normalization_functional_dependencies.cpp -o normalization
 */

#include <algorithm>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using Attribute = std::string;
using AttributeSet = std::set<Attribute>;
using Row = std::map<Attribute, std::string>;

struct FunctionalDependency {
    AttributeSet determinant;
    AttributeSet dependent;
};

std::string formatSet(const AttributeSet& values) {
    std::string result = "{";
    bool first = true;

    for (const auto& value : values) {
        if (!first) {
            result += ", ";
        }
        result += value;
        first = false;
    }

    result += "}";
    return result;
}

std::string formatFD(const FunctionalDependency& dependency) {
    return formatSet(dependency.determinant) + " -> " +
           formatSet(dependency.dependent);
}

bool containsAll(const AttributeSet& container,
                 const AttributeSet& required) {
    return std::includes(
        container.begin(),
        container.end(),
        required.begin(),
        required.end()
    );
}

bool isProperSubset(const AttributeSet& left,
                    const AttributeSet& right) {
    return left.size() < right.size() && containsAll(right, left);
}

// ---------------------------------------------------------------------------
// Relation model
// ---------------------------------------------------------------------------

class Relation {
public:
    Relation(
        std::string name,
        std::vector<Attribute> columns,
        std::vector<Row> rows
    )
        : name_(std::move(name)),
          columns_(std::move(columns)),
          rows_(std::move(rows)) {
        validate();
    }

    const std::vector<Attribute>& columns() const {
        return columns_;
    }

    const std::vector<Row>& rows() const {
        return rows_;
    }

    void insert(const Row& row) {
        for (const auto& column : columns_) {
            if (!row.contains(column)) {
                throw std::invalid_argument(
                    "Tuple is missing column: " + column
                );
            }
        }

        if (row.size() != columns_.size()) {
            throw std::invalid_argument(
                "Tuple contains an attribute not present in the relation."
            );
        }

        rows_.push_back(row);
    }

    void display(const std::string& title) const {
        std::cout << "\n" << title << "\n";

        if (rows_.empty()) {
            std::cout << "(empty)\n";
            return;
        }

        std::map<Attribute, std::size_t> widths;

        for (const auto& column : columns_) {
            widths[column] = column.size();
            for (const auto& row : rows_) {
                widths[column] =
                    std::max(widths[column], row.at(column).size());
            }
        }

        for (const auto& column : columns_) {
            std::cout << std::left
                      << std::setw(static_cast<int>(widths[column]))
                      << column << " | ";
        }
        std::cout << "\n";

        for (std::size_t i = 0; i < columns_.size(); ++i) {
            const auto& column = columns_[i];
            std::cout << std::string(widths[column], '-')
                      << (i + 1 == columns_.size() ? '\n' : "-+-");
        }

        for (const auto& row : rows_) {
            for (const auto& column : columns_) {
                std::cout << std::left
                          << std::setw(static_cast<int>(widths[column]))
                          << row.at(column) << " | ";
            }
            std::cout << "\n";
        }
    }

private:
    void validate() const {
        std::set<Attribute> known(columns_.begin(), columns_.end());

        if (known.size() != columns_.size()) {
            throw std::invalid_argument("Duplicate relation attribute.");
        }

        for (const auto& row : rows_) {
            for (const auto& column : columns_) {
                if (!row.contains(column)) {
                    throw std::invalid_argument(
                        "Initial row is missing column: " + column
                    );
                }
            }

            if (row.size() != columns_.size()) {
                throw std::invalid_argument(
                    "Initial row contains an unknown attribute."
                );
            }
        }
    }

    std::string name_;
    std::vector<Attribute> columns_;
    std::vector<Row> rows_;
};

// ---------------------------------------------------------------------------
// Functional dependency engine
// ---------------------------------------------------------------------------

class DependencyEngine {
public:
    explicit DependencyEngine(std::vector<FunctionalDependency> dependencies)
        : dependencies_(std::move(dependencies)) {}

    AttributeSet closure(AttributeSet attributes) const {
        /*
         * The closure algorithm repeatedly applies FDs whose left-hand side
         * is already known. The fixed point is X+.
         */
        bool changed = true;

        while (changed) {
            changed = false;

            for (const auto& dependency : dependencies_) {
                if (!containsAll(attributes, dependency.determinant)) {
                    continue;
                }

                for (const auto& attribute : dependency.dependent) {
                    if (!attributes.contains(attribute)) {
                        attributes.insert(attribute);
                        changed = true;
                    }
                }
            }
        }

        return attributes;
    }

    bool implies(
        const AttributeSet& determinant,
        const AttributeSet& dependent
    ) const {
        return containsAll(closure(determinant), dependent);
    }

    bool isSuperkey(
        const AttributeSet& candidate,
        const AttributeSet& relationAttributes
    ) const {
        return containsAll(closure(candidate), relationAttributes);
    }

    std::vector<AttributeSet> candidateKeys(
        const AttributeSet& relationAttributes
    ) const {
        /*
         * Candidate-key enumeration uses combinations. It is intentionally
         * explicit for the case study so that minimality is visible.
         *
         * Complexity is exponential in the number of relation attributes.
         * A production schema-analysis tool needs stronger pruning for
         * large relations.
         */
        std::vector<Attribute> attributes(
            relationAttributes.begin(),
            relationAttributes.end()
        );

        std::vector<AttributeSet> keys;

        for (std::size_t size = 1; size <= attributes.size(); ++size) {
            std::vector<bool> selection(attributes.size(), false);
            std::fill(
                selection.begin(),
                selection.begin() + static_cast<long>(size),
                true
            );

            do {
                AttributeSet candidate;

                for (std::size_t i = 0; i < attributes.size(); ++i) {
                    if (selection[i]) {
                        candidate.insert(attributes[i]);
                    }
                }

                if (!isSuperkey(candidate, relationAttributes)) {
                    continue;
                }

                bool containsExistingKey = false;

                for (const auto& key : keys) {
                    if (containsAll(candidate, key)) {
                        containsExistingKey = true;
                        break;
                    }
                }

                if (!containsExistingKey) {
                    keys.push_back(candidate);
                }

            } while (
                std::prev_permutation(selection.begin(), selection.end())
            );
        }

        return keys;
    }

    const std::vector<FunctionalDependency>& dependencies() const {
        return dependencies_;
    }

private:
    std::vector<FunctionalDependency> dependencies_;
};

// ---------------------------------------------------------------------------
// FD violation analysis
// ---------------------------------------------------------------------------

std::vector<std::pair<Row, Row>> findViolations(
    const Relation& relation,
    const FunctionalDependency& dependency
) {
    std::vector<std::pair<Row, Row>> violations;

    const auto& rows = relation.rows();

    for (std::size_t i = 0; i < rows.size(); ++i) {
        for (std::size_t j = i + 1; j < rows.size(); ++j) {
            bool sameDeterminant = true;

            for (const auto& attribute : dependency.determinant) {
                if (rows[i].at(attribute) != rows[j].at(attribute)) {
                    sameDeterminant = false;
                    break;
                }
            }

            if (!sameDeterminant) {
                continue;
            }

            bool differentDependent = false;

            for (const auto& attribute : dependency.dependent) {
                if (rows[i].at(attribute) != rows[j].at(attribute)) {
                    differentDependent = true;
                    break;
                }
            }

            if (differentDependent) {
                violations.emplace_back(rows[i], rows[j]);
            }
        }
    }

    return violations;
}

// ---------------------------------------------------------------------------
// Projection used by the normalization case study
// ---------------------------------------------------------------------------

Relation project(
    const Relation& source,
    const std::string& name,
    const std::vector<Attribute>& columns
) {
    std::set<std::vector<std::string>> seen;
    std::vector<Row> rows;

    for (const auto& sourceRow : source.rows()) {
        std::vector<std::string> values;
        Row projected;

        for (const auto& column : columns) {
            const std::string& value = sourceRow.at(column);
            values.push_back(value);
            projected[column] = value;
        }

        if (seen.insert(values).second) {
            rows.push_back(projected);
        }
    }

    return Relation(name, columns, rows);
}

// ---------------------------------------------------------------------------
// Case study
// ---------------------------------------------------------------------------

void demonstrateRegistrarCaseStudy() {
    /*
     * Business semantics:
     *
     * student_id -> student_name, student_program
     * course_id -> course_name, department
     * instructor_id -> instructor_name
     * course_id, section_no, term -> instructor_id
     * student_id, course_id, section_no, term -> grade
     *
     * The composite enrollment identifier determines the grade, while other
     * attributes are determined by smaller identifiers. Those different
     * determinants are the source of redundancy in the original relation.
     */
    const std::vector<Attribute> attributes = {
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
        "grade"
    };

    const std::vector<FunctionalDependency> dependencies = {
        {
            {"student_id"},
            {"student_name", "student_program"}
        },
        {
            {"course_id"},
            {"course_name", "department"}
        },
        {
            {"instructor_id"},
            {"instructor_name"}
        },
        {
            {"course_id", "section_no", "term"},
            {"instructor_id"}
        },
        {
            {"student_id", "course_id", "section_no", "term"},
            {"grade"}
        }
    };

    DependencyEngine engine(dependencies);

    std::cout << "\nFunctional dependency set\n";
    for (const auto& dependency : dependencies) {
        std::cout << "  " << formatFD(dependency) << "\n";
    }

    AttributeSet allAttributes(
        attributes.begin(),
        attributes.end()
    );

    std::cout << "\nAttribute closures\n";

    const std::vector<AttributeSet> closureInputs = {
        {"student_id"},
        {"course_id"},
        {"course_id", "section_no", "term"},
        {"student_id", "course_id", "section_no", "term"}
    };

    for (const auto& input : closureInputs) {
        std::cout << "  " << formatSet(input)
                  << "+ = "
                  << formatSet(engine.closure(input))
                  << "\n";
    }

    std::cout << "\nCandidate keys\n";

    const auto keys = engine.candidateKeys(allAttributes);

    for (const auto& key : keys) {
        std::cout << "  " << formatSet(key) << "\n";
    }

    std::cout << "\nDependency implication checks\n";

    const AttributeSet studentId = {"student_id"};
    const AttributeSet studentName = {"student_name"};
    const AttributeSet courseId = {"course_id"};
    const AttributeSet instructorId = {"instructor_id"};
    const AttributeSet enrollmentKey = {
        "student_id",
        "course_id",
        "section_no",
        "term"
    };
    const AttributeSet instructorName = {"instructor_name"};

    std::cout
        << "  student_id -> student_name: "
        << (engine.implies(studentId, studentName) ? "true" : "false")
        << "\n";

    std::cout
        << "  course_id -> instructor_id: "
        << (engine.implies(courseId, instructorId) ? "true" : "false")
        << "\n";

    std::cout
        << "  enrollment key -> instructor_name: "
        << (engine.implies(enrollmentKey, instructorName) ? "true" : "false")
        << "\n";

    const Relation original(
        "EnrollmentRecord",
        attributes,
        {
            {
                {"student_id", "S1"},
                {"student_name", "Asha"},
                {"student_program", "MCA"},
                {"course_id", "DB101"},
                {"course_name", "Database Systems"},
                {"department", "Computer Science"},
                {"section_no", "A"},
                {"term", "2026-Fall"},
                {"instructor_id", "I7"},
                {"instructor_name", "Dr. Rao"},
                {"grade", "A"}
            },
            {
                {"student_id", "S2"},
                {"student_name", "Kabir"},
                {"student_program", "MBA"},
                {"course_id", "DB101"},
                {"course_name", "Database Systems"},
                {"department", "Computer Science"},
                {"section_no", "A"},
                {"term", "2026-Fall"},
                {"instructor_id", "I7"},
                {"instructor_name", "Dr. Rao"},
                {"grade", "B+"}
            },
            {
                {"student_id", "S1"},
                {"student_name", "Asha"},
                {"student_program", "MCA"},
                {"course_id", "AI201"},
                {"course_name", "Machine Learning"},
                {"department", "Computer Science"},
                {"section_no", "B"},
                {"term", "2026-Fall"},
                {"instructor_id", "I9"},
                {"instructor_name", "Dr. Sen"},
                {"grade", "A-"}
            }
        }
    );

    original.display("Original denormalized registrar relation");

    /*
     * These projections isolate facts with distinct determinants. The
     * projection step also removes duplicate student/course/instructor facts,
     * directly reducing update redundancy.
     */
    const Relation student = project(
        original,
        "Student",
        {"student_id", "student_name", "student_program"}
    );

    const Relation course = project(
        original,
        "Course",
        {"course_id", "course_name", "department"}
    );

    const Relation instructor = project(
        original,
        "Instructor",
        {"instructor_id", "instructor_name"}
    );

    const Relation section = project(
        original,
        "Section",
        {"course_id", "section_no", "term", "instructor_id"}
    );

    const Relation enrollment = project(
        original,
        "Enrollment",
        {
            "student_id",
            "course_id",
            "section_no",
            "term",
            "grade"
        }
    );

    student.display("Normalized relation: Student");
    course.display("Normalized relation: Course");
    instructor.display("Normalized relation: Instructor");
    section.display("Normalized relation: Section");
    enrollment.display("Normalized relation: Enrollment");
}

// ---------------------------------------------------------------------------
// Concrete anomaly demonstrations
// ---------------------------------------------------------------------------

void demonstrateAnomalies() {
    Relation employeeDepartment(
        "EmployeeDepartment",
        {
            "employee_id",
            "employee_name",
            "department",
            "department_location"
        },
        {
            {
                {"employee_id", "E101"},
                {"employee_name", "Anita"},
                {"department", "Finance"},
                {"department_location", "Mumbai"}
            },
            {
                {"employee_id", "E102"},
                {"employee_name", "Rahul"},
                {"department", "Finance"},
                {"department_location", "Mumbai"}
            }
        }
    );

    employeeDepartment.display("Update anomaly before a location change");

    /*
     * The business rule department -> department_location means every
     * Finance tuple must agree on the location. Updating only one duplicate
     * creates an inconsistent database state.
     */
    Relation inconsistent(
        "EmployeeDepartment",
        employeeDepartment.columns(),
        {
            {
                {"employee_id", "E101"},
                {"employee_name", "Anita"},
                {"department", "Finance"},
                {"department_location", "Pune"}
            },
            {
                {"employee_id", "E102"},
                {"employee_name", "Rahul"},
                {"department", "Finance"},
                {"department_location", "Mumbai"}
            }
        }
    );

    inconsistent.display("Update anomaly after only one duplicate was changed");

    const DependencyEngine locationRules({
        {
            {"department"},
            {"department_location"}
        }
    });

    const auto violations = findViolations(
        inconsistent,
        {
            {"department"},
            {"department_location"}
        }
    );

    std::cout
        << "\nDepartment-location FD violations: "
        << violations.size()
        << "\n";

    std::cout
        << "\nInsertion anomaly: a course that has been approved but has "
        << "no enrollment cannot naturally appear in StudentCourse without "
        << "inventing a student tuple.\n";

    std::cout
        << "Deletion anomaly: deleting the final enrollment tuple can "
        << "remove the only stored copy of the course and instructor facts.\n";

    /*
     * locationRules is retained as an actual policy object rather than
     * merely describing the dependency in prose.
     */
    const AttributeSet department = {"department"};
    const AttributeSet location = {"department_location"};

    std::cout
        << "Policy check department -> department_location: "
        << (locationRules.implies(department, location) ? "enforced" : "not enforced")
        << "\n";
}

// ---------------------------------------------------------------------------
// Edge conditions
// ---------------------------------------------------------------------------

void demonstrateEdgeConditions() {
    std::cout << "\nEdge conditions\n";

    Relation employee(
        "Employee",
        {"employee_id", "name"},
        {
            {
                {"employee_id", "E1"},
                {"name", "Asha"}
            },
            {
                {"employee_id", "E2"},
                {"name", "Kabir"}
            }
        }
    );

    const FunctionalDependency validFD{
        {"employee_id"},
        {"name"}
    };

    const auto validViolations = findViolations(employee, validFD);

    std::cout
        << "  employee_id -> name violations: "
        << validViolations.size()
        << "\n";

    Relation badEmployee(
        "Employee",
        {"employee_id", "name"},
        {
            {
                {"employee_id", "E1"},
                {"name", "Asha"}
            },
            {
                {"employee_id", "E1"},
                {"name", "Kabir"}
            }
        }
    );

    const auto badViolations = findViolations(badEmployee, validFD);

    std::cout
        << "  Same employee_id with two names: "
        << badViolations.size()
        << " violation\n";

    std::cout
        << "  A clean sample does not prove an FD. FD validity comes from "
        << "the meaning of the data, not only from current observations.\n";

    std::cout
        << "  Candidate-key enumeration is exact for this small case study "
        << "but grows exponentially as the attribute count increases.\n";
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

int main() {
    try {
        std::cout << std::string(78, '=') << "\n";
        std::cout << "NORMALIZATION I: FUNCTIONAL DEPENDENCIES AND ANOMALIES\n";
        std::cout << std::string(78, '=') << "\n";

        demonstrateAnomalies();
        demonstrateRegistrarCaseStudy();
        demonstrateEdgeConditions();

        std::cout << "\nCase-study interpretation\n";
        std::cout
            << "Functional dependencies expose which attributes determine "
            << "other attributes. The original registrar relation combines "
            << "facts with different determinants, producing redundancy. "
            << "The decomposition separates those facts so that a change to "
            << "a student, course, instructor, section, or enrollment is "
            << "stored at the appropriate level.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << "\n";
        return 1;
    }
}
