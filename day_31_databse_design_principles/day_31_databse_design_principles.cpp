#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * Database Design Principles
 *
 * C++ case study:
 * A university operates a high-volume enrollment system. The design engine
 * below evaluates a proposed logical schema and then maps its workload to
 * physical access paths.
 *
 * The program deliberately separates:
 *
 *   Logical design
 *     entities, attributes, keys, relationships, dependencies
 *
 *   Physical design
 *     indexes, partitioning decisions, storage estimates, access paths
 *
 *   Design objectives
 *     integrity, performance, maintainability, scalability, and security
 *
 * This is an executable design-analysis model, not a replacement for a
 * database optimizer or storage engine.
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic database_design.cpp -o database_design
 */

namespace dbdesign {

// ---------------------------------------------------------------------------
// Logical design structures
// ---------------------------------------------------------------------------

struct Attribute {
    std::string name;
    std::string type;
    bool nullable;
};

struct ForeignKey {
    std::vector<std::string> columns;
    std::string referenced_table;
    std::vector<std::string> referenced_columns;
};

struct TableDefinition {
    std::string name;
    std::vector<Attribute> attributes;
    std::vector<std::string> primary_key;
    std::vector<std::vector<std::string>> candidate_keys;
    std::vector<ForeignKey> foreign_keys;

    bool has_attribute(const std::string& name) const {
        return std::any_of(
            attributes.begin(),
            attributes.end(),
            [&](const Attribute& attribute) {
                return attribute.name == name;
            }
        );
    }

    bool primary_key_matches(
        const std::vector<std::string>& columns
    ) const {
        return primary_key == columns;
    }
};


class LogicalSchema {
private:
    std::map<std::string, TableDefinition> tables_;

public:
    void add_table(TableDefinition table) {
        if (tables_.contains(table.name)) {
            throw std::invalid_argument(
                "duplicate logical table: " + table.name
            );
        }

        tables_.emplace(table.name, std::move(table));
    }

    const TableDefinition& table(const std::string& name) const {
        auto iterator = tables_.find(name);

        if (iterator == tables_.end()) {
            throw std::out_of_range(
                "logical table does not exist: " + name
            );
        }

        return iterator->second;
    }

    const std::map<std::string, TableDefinition>& tables() const {
        return tables_;
    }

    std::vector<std::string> validate() const {
        std::vector<std::string> errors;

        for (const auto& [name, table] : tables_) {
            std::set<std::string> names;

            for (const auto& attribute : table.attributes) {
                if (!names.insert(attribute.name).second) {
                    errors.push_back(
                        name + ": duplicate attribute " + attribute.name
                    );
                }
            }

            if (table.primary_key.empty()) {
                errors.push_back(name + ": missing primary key");
            }

            for (const auto& column : table.primary_key) {
                if (!table.has_attribute(column)) {
                    errors.push_back(
                        name + ": primary-key attribute " + column
                        + " does not exist"
                    );
                }
            }

            for (const auto& key : table.candidate_keys) {
                for (const auto& column : key) {
                    if (!table.has_attribute(column)) {
                        errors.push_back(
                            name + ": candidate-key attribute "
                            + column + " does not exist"
                        );
                    }
                }
            }

            for (const auto& foreign_key : table.foreign_keys) {
                if (foreign_key.columns.size() !=
                    foreign_key.referenced_columns.size()) {
                    errors.push_back(
                        name + ": foreign-key column count mismatch"
                    );
                    continue;
                }

                for (const auto& column : foreign_key.columns) {
                    if (!table.has_attribute(column)) {
                        errors.push_back(
                            name + ": foreign-key column "
                            + column + " does not exist"
                        );
                    }
                }

                auto referenced = tables_.find(
                    foreign_key.referenced_table
                );

                if (referenced == tables_.end()) {
                    errors.push_back(
                        name + ": referenced table "
                        + foreign_key.referenced_table
                        + " does not exist"
                    );
                    continue;
                }

                if (!referenced->second.primary_key_matches(
                        foreign_key.referenced_columns)) {
                    errors.push_back(
                        name + ": foreign key does not reference the "
                        "declared primary key of "
                        + foreign_key.referenced_table
                    );
                }
            }
        }

        return errors;
    }
};


// ---------------------------------------------------------------------------
// Functional dependencies
// ---------------------------------------------------------------------------

struct FunctionalDependency {
    std::vector<std::string> determinant;
    std::vector<std::string> dependent;

    std::string describe() const {
        auto join = [](const std::vector<std::string>& values) {
            std::ostringstream output;

            for (std::size_t i = 0; i < values.size(); ++i) {
                if (i != 0) {
                    output << ", ";
                }
                output << values[i];
            }

            return output.str();
        };

        return join(determinant) + " -> " + join(dependent);
    }
};


// ---------------------------------------------------------------------------
// Physical design
// ---------------------------------------------------------------------------

struct IndexDefinition {
    std::string name;
    std::string table;
    std::vector<std::string> columns;
    bool unique;

    /*
     * The simplified access-path test models the most important B-tree
     * principle for this case study: a useful predicate should generally
     * constrain the leftmost indexed column.
     */
    bool supports(const std::set<std::string>& predicates) const {
        return !columns.empty() &&
               predicates.contains(columns.front());
    }
};


struct PhysicalDesign {
    std::vector<IndexDefinition> indexes;
    std::map<std::string, std::string> partitioning;

    std::vector<const IndexDefinition*> indexes_for(
        const std::string& table
    ) const {
        std::vector<const IndexDefinition*> result;

        for (const auto& index : indexes) {
            if (index.table == table) {
                result.push_back(&index);
            }
        }

        return result;
    }

    std::vector<const IndexDefinition*> candidate_indexes(
        const std::string& table,
        const std::set<std::string>& predicates
    ) const {
        std::vector<const IndexDefinition*> result;

        for (const auto* index : indexes_for(table)) {
            if (index->supports(predicates)) {
                result.push_back(index);
            }
        }

        return result;
    }
};


// ---------------------------------------------------------------------------
// Workload model
// ---------------------------------------------------------------------------

struct QueryWorkload {
    std::string name;
    std::string table;
    std::set<std::string> predicates;
    std::size_t executions_per_day;
    std::size_t rows_examined;
    std::size_t rows_returned;
    double average_latency_ms;

    double selectivity() const {
        if (rows_examined == 0) {
            return 0.0;
        }

        return static_cast<double>(rows_returned) /
               static_cast<double>(rows_examined);
    }
};


struct WorkloadFinding {
    std::string query;
    std::string reason;
};


std::vector<WorkloadFinding> evaluate_workload(
    const PhysicalDesign& physical,
    const std::vector<QueryWorkload>& workload
) {
    std::vector<WorkloadFinding> findings;

    for (const auto& query : workload) {
        if (query.executions_per_day < 1000) {
            continue;
        }

        auto indexes = physical.candidate_indexes(
            query.table,
            query.predicates
        );

        if (indexes.empty() &&
            query.rows_returned <= query.rows_examined / 100) {
            findings.push_back({
                query.name,
                "high-frequency selective query has no modeled access path"
            });
        }
    }

    return findings;
}


// ---------------------------------------------------------------------------
// Storage estimation
// ---------------------------------------------------------------------------

struct StorageEstimate {
    std::size_t row_count;
    std::size_t key_bytes;
    std::size_t pointer_bytes;
    double overhead_fraction;

    double bytes() const {
        const double base =
            static_cast<double>(row_count) *
            static_cast<double>(key_bytes + pointer_bytes);

        return base * (1.0 + overhead_fraction);
    }
};


double mib(double bytes) {
    return bytes / (1024.0 * 1024.0);
}


// ---------------------------------------------------------------------------
// In-memory operational representation
// ---------------------------------------------------------------------------

struct Student {
    int student_id;
    std::string student_number;
    std::string name;
    std::string email;
};


struct Section {
    int section_id;
    int course_id;
    int instructor_id;
    int term_id;
    std::string room;
    int capacity;
};


struct Enrollment {
    int student_id;
    int section_id;
    std::string enrolled_on;
    std::optional<std::string> grade;
};


struct EnrollmentKey {
    int student_id;
    int section_id;

    bool operator<(const EnrollmentKey& other) const {
        return std::tie(student_id, section_id) <
               std::tie(other.student_id, other.section_id);
    }
};


class EnrollmentDatabase {
private:
    std::map<int, Student> students_;
    std::map<int, Section> sections_;
    std::map<EnrollmentKey, Enrollment> enrollments_;

public:
    void add_student(Student student) {
        if (student.student_id <= 0) {
            throw std::invalid_argument(
                "student_id must be positive"
            );
        }

        if (student.email.find('@') == std::string::npos) {
            throw std::invalid_argument(
                "student email is invalid"
            );
        }

        if (students_.contains(student.student_id)) {
            throw std::runtime_error(
                "student primary key already exists"
            );
        }

        for (const auto& [id, existing] : students_) {
            if (existing.student_number == student.student_number) {
                throw std::runtime_error(
                    "student_number violates candidate-key uniqueness"
                );
            }

            if (existing.email == student.email) {
                throw std::runtime_error(
                    "email violates candidate-key uniqueness"
                );
            }
        }

        students_.emplace(student.student_id, std::move(student));
    }

    void add_section(Section section) {
        if (section.capacity <= 0) {
            throw std::invalid_argument(
                "section capacity must be positive"
            );
        }

        if (sections_.contains(section.section_id)) {
            throw std::runtime_error(
                "section primary key already exists"
            );
        }

        sections_.emplace(section.section_id, std::move(section));
    }

    void enroll(
        int student_id,
        int section_id,
        const std::string& enrolled_on
    ) {
        if (!students_.contains(student_id)) {
            throw std::runtime_error(
                "student foreign-key constraint failed"
            );
        }

        auto section = sections_.find(section_id);

        if (section == sections_.end()) {
            throw std::runtime_error(
                "section foreign-key constraint failed"
            );
        }

        EnrollmentKey key{student_id, section_id};

        if (enrollments_.contains(key)) {
            throw std::runtime_error(
                "composite enrollment primary key already exists"
            );
        }

        int section_count = 0;

        for (const auto& [stored_key, enrollment] : enrollments_) {
            if (enrollment.section_id == section_id) {
                ++section_count;
            }
        }

        if (section_count >= section->second.capacity) {
            throw std::runtime_error(
                "section capacity constraint failed"
            );
        }

        enrollments_.emplace(
            key,
            Enrollment{
                student_id,
                section_id,
                enrolled_on,
                std::nullopt
            }
        );
    }

    void assign_grade(
        int student_id,
        int section_id,
        const std::string& grade
    ) {
        static const std::set<std::string> allowed{
            "A+", "A", "B+", "B", "C+", "C", "D", "F", "I"
        };

        if (!allowed.contains(grade)) {
            throw std::invalid_argument(
                "unsupported grade"
            );
        }

        EnrollmentKey key{student_id, section_id};
        auto iterator = enrollments_.find(key);

        if (iterator == enrollments_.end()) {
            throw std::runtime_error(
                "cannot assign grade to missing enrollment"
            );
        }

        iterator->second.grade = grade;
    }

    std::size_t enrollment_count() const {
        return enrollments_.size();
    }

    std::vector<Enrollment> enrollments_for_student(
        int student_id
    ) const {
        std::vector<Enrollment> result;

        for (const auto& [key, enrollment] : enrollments_) {
            if (key.student_id == student_id) {
                result.push_back(enrollment);
            }
        }

        return result;
    }
};


// ---------------------------------------------------------------------------
// Transactional batch simulation
// ---------------------------------------------------------------------------

class EnrollmentTransaction {
private:
    EnrollmentDatabase& database_;
    std::vector<Enrollment> original_state_;
    bool active_ = true;

    /*
     * This compact transaction model only snapshots enrollment records.
     * A real database transaction would use transaction isolation, logging,
     * locking or MVCC, recovery, and durable commit semantics.
     */

public:
    explicit EnrollmentTransaction(
        EnrollmentDatabase& database
    )
        : database_(database) {
        // The example transaction is intentionally narrow because only
        // enrollment rows are modified by this workflow.
        original_state_ =
            database_.enrollments_for_student(1);
    }

    void execute(
        const std::vector<std::tuple<int, int, std::string>>& requests
    ) {
        if (!active_) {
            throw std::runtime_error(
                "transaction is no longer active"
            );
        }

        try {
            for (const auto& [student, section, enrolled_on] : requests) {
                database_.enroll(student, section, enrolled_on);
            }
        } catch (...) {
            /*
             * The database object deliberately exposes no arbitrary rollback
             * API. The catch demonstrates the important design requirement:
             * production code should delegate atomic rollback to the database
             * transaction rather than trying to reconstruct state in memory.
             */
            active_ = false;
            throw;
        }
    }

    void commit() {
        if (!active_) {
            throw std::runtime_error(
                "cannot commit failed transaction"
            );
        }

        active_ = false;
    }

    const std::vector<Enrollment>& captured_state() const {
        return original_state_;
    }
};


// ---------------------------------------------------------------------------
// Schema construction
// ---------------------------------------------------------------------------

LogicalSchema build_schema() {
    LogicalSchema schema;

    schema.add_table({
        "student",
        {
            {"student_id", "INTEGER", false},
            {"student_number", "VARCHAR(20)", false},
            {"full_name", "VARCHAR(120)", false},
            {"email", "VARCHAR(254)", false},
            {"birth_date", "DATE", true}
        },
        {"student_id"},
        {
            {"student_number"},
            {"email"}
        },
        {}
    });

    schema.add_table({
        "course",
        {
            {"course_id", "INTEGER", false},
            {"course_code", "VARCHAR(20)", false},
            {"course_name", "VARCHAR(160)", false},
            {"credit_hours", "SMALLINT", false}
        },
        {"course_id"},
        {
            {"course_code"}
        },
        {}
    });

    schema.add_table({
        "instructor",
        {
            {"instructor_id", "INTEGER", false},
            {"employee_number", "VARCHAR(20)", false},
            {"full_name", "VARCHAR(120)", false},
            {"email", "VARCHAR(254)", false}
        },
        {"instructor_id"},
        {
            {"employee_number"},
            {"email"}
        },
        {}
    });

    schema.add_table({
        "academic_term",
        {
            {"term_id", "INTEGER", false},
            {"term_code", "VARCHAR(20)", false},
            {"start_date", "DATE", false},
            {"end_date", "DATE", false}
        },
        {"term_id"},
        {
            {"term_code"}
        },
        {}
    });

    schema.add_table({
        "course_section",
        {
            {"section_id", "INTEGER", false},
            {"course_id", "INTEGER", false},
            {"instructor_id", "INTEGER", false},
            {"term_id", "INTEGER", false},
            {"room_code", "VARCHAR(30)", false},
            {"capacity", "INTEGER", false}
        },
        {"section_id"},
        {
            {
                "course_id",
                "term_id",
                "instructor_id",
                "room_code"
            }
        },
        {
            {
                {"course_id"},
                "course",
                {"course_id"}
            },
            {
                {"instructor_id"},
                "instructor",
                {"instructor_id"}
            },
            {
                {"term_id"},
                "academic_term",
                {"term_id"}
            }
        }
    });

    schema.add_table({
        "enrollment",
        {
            {"student_id", "INTEGER", false},
            {"section_id", "INTEGER", false},
            {"enrolled_on", "DATE", false},
            {"grade", "VARCHAR(2)", true}
        },
        {"student_id", "section_id"},
        {},
        {
            {
                {"student_id"},
                "student",
                {"student_id"}
            },
            {
                {"section_id"},
                "course_section",
                {"section_id"}
            }
        }
    });

    return schema;
}


// ---------------------------------------------------------------------------
// Physical design construction
// ---------------------------------------------------------------------------

PhysicalDesign build_physical_design() {
    PhysicalDesign design;

    design.indexes = {
        {
            "ux_student_email",
            "student",
            {"email"},
            true
        },
        {
            "ux_student_number",
            "student",
            {"student_number"},
            true
        },
        {
            "ix_section_term_course",
            "course_section",
            {"term_id", "course_id"},
            false
        },
        {
            "ix_section_instructor_term",
            "course_section",
            {"instructor_id", "term_id"},
            false
        },
        {
            "ix_enrollment_student_section",
            "enrollment",
            {"student_id", "section_id"},
            false
        },
        {
            "ix_enrollment_section_student",
            "enrollment",
            {"section_id", "student_id"},
            false
        }
    };

    design.partitioning = {
        {
            "enrollment",
            "range partitioning by academic term when volume and lifecycle justify it"
        },
        {
            "course_section",
            "term-oriented partitioning only after operational evidence"
        }
    };

    return design;
}


// ---------------------------------------------------------------------------
// Output helpers
// ---------------------------------------------------------------------------

void print_schema(const LogicalSchema& schema) {
    std::cout << "\nLOGICAL SCHEMA\n"
              << std::string(72, '=') << "\n";

    for (const auto& [name, table] : schema.tables()) {
        std::cout << "\n" << name << "\n";

        for (const auto& attribute : table.attributes) {
            std::cout
                << "  "
                << std::left
                << std::setw(18)
                << attribute.name
                << std::setw(15)
                << attribute.type
                << (attribute.nullable ? "NULL" : "NOT NULL")
                << "\n";
        }

        std::cout << "  PK: ";

        for (std::size_t i = 0; i < table.primary_key.size(); ++i) {
            if (i != 0) {
                std::cout << ", ";
            }
            std::cout << table.primary_key[i];
        }

        std::cout << "\n";

        for (const auto& key : table.candidate_keys) {
            std::cout << "  AK: ";

            for (std::size_t i = 0; i < key.size(); ++i) {
                if (i != 0) {
                    std::cout << ", ";
                }
                std::cout << key[i];
            }

            std::cout << "\n";
        }
    }
}


void print_dependencies() {
    std::cout << "\nFUNCTIONAL DEPENDENCIES\n"
              << std::string(72, '=') << "\n";

    const std::vector<FunctionalDependency> dependencies{
        {
            {"student_id"},
            {"student_number", "email"}
        },
        {
            {"course_id"},
            {"course_code", "course_name"}
        },
        {
            {"section_id"},
            {"course_id", "instructor_id", "term_id", "capacity"}
        },
        {
            {"student_id", "section_id"},
            {"enrolled_on", "grade"}
        }
    };

    for (const auto& dependency : dependencies) {
        std::cout << "  "
                  << dependency.describe()
                  << "\n";
    }

    std::cout
        << "\nThe composite enrollment key expresses the relationship fact: "
        << "one student can appear once per section.\n";
}


void print_physical_design(const PhysicalDesign& design) {
    std::cout << "\nPHYSICAL DESIGN\n"
              << std::string(72, '=') << "\n";

    for (const auto& index : design.indexes) {
        std::cout
            << "  "
            << index.name
            << ": "
            << index.table
            << "(";

        for (std::size_t i = 0; i < index.columns.size(); ++i) {
            if (i != 0) {
                std::cout << ", ";
            }
            std::cout << index.columns[i];
        }

        std::cout << ")";

        if (index.unique) {
            std::cout << " UNIQUE";
        }

        std::cout << "\n";
    }

    std::cout << "\nPartitioning:\n";

    for (const auto& [table, strategy] : design.partitioning) {
        std::cout
            << "  "
            << table
            << ": "
            << strategy
            << "\n";
    }
}


// ---------------------------------------------------------------------------
// Main technical case study
// ---------------------------------------------------------------------------

} // namespace dbdesign


int main() {
    using namespace dbdesign;

    try {
        std::cout
            << "DATABASE DESIGN PRINCIPLES\n"
            << std::string(72, '=')
            << "\n"
            << "Case study: university enrollment database\n";

        LogicalSchema schema = build_schema();

        const auto validation_errors = schema.validate();

        std::cout << "\nLOGICAL DESIGN VALIDATION\n"
                  << std::string(72, '=')
                  << "\n";

        if (!validation_errors.empty()) {
            for (const auto& error : validation_errors) {
                std::cerr << "ERROR: " << error << "\n";
            }

            return 1;
        }

        std::cout
            << "Logical schema passed key, attribute, and foreign-key validation.\n";

        print_schema(schema);
        print_dependencies();

        std::cout << "\nRELATIONSHIP MODEL\n"
                  << std::string(72, '=')
                  << "\n"
                  << "Student and Section form a many-to-many relationship.\n"
                  << "Enrollment is the associative entity that resolves that "
                     "relationship.\n"
                  << "Its composite key prevents duplicate student-section pairs.\n";

        PhysicalDesign physical = build_physical_design();
        print_physical_design(physical);

        std::vector<QueryWorkload> workload{
            {
                "Student transcript lookup",
                "enrollment",
                {"student_id"},
                25000,
                2000000,
                42,
                6.2
            },
            {
                "Section roster lookup",
                "enrollment",
                {"section_id"},
                18000,
                2000000,
                80,
                7.1
            },
            {
                "Course sections in a term",
                "course_section",
                {"term_id", "course_id"},
                7500,
                50000,
                12,
                4.8
            },
            {
                "Student lookup by email",
                "student",
                {"email"},
                40000,
                1500000,
                1,
                2.1
            },
            {
                "Administrative room search",
                "course_section",
                {"room_code"},
                100,
                50000,
                8000,
                29.4
            }
        };

        std::cout << "\nWORKLOAD ANALYSIS\n"
                  << std::string(72, '=')
                  << "\n";

        for (const auto& query : workload) {
            const auto indexes = physical.candidate_indexes(
                query.table,
                query.predicates
            );

            std::cout
                << "\n"
                << query.name
                << "\n"
                << "  executions/day: "
                << query.executions_per_day
                << "\n"
                << "  rows examined: "
                << query.rows_examined
                << "\n"
                << "  rows returned: "
                << query.rows_returned
                << "\n"
                << "  selectivity: "
                << std::fixed
                << std::setprecision(4)
                << query.selectivity() * 100.0
                << "%\n"
                << "  average latency: "
                << query.average_latency_ms
                << " ms\n"
                << "  modeled access paths: ";

            if (indexes.empty()) {
                std::cout << "none";
            } else {
                for (std::size_t i = 0; i < indexes.size(); ++i) {
                    if (i != 0) {
                        std::cout << ", ";
                    }

                    std::cout << indexes[i]->name;
                }
            }

            std::cout << "\n";
        }

        const auto findings = evaluate_workload(
            physical,
            workload
        );

        std::cout << "\nDESIGN FINDINGS\n"
                  << std::string(72, '=')
                  << "\n";

        if (findings.empty()) {
            std::cout << "No high-frequency selective query lacks a modeled index.\n";
        } else {
            for (const auto& finding : findings) {
                std::cout
                    << "  "
                    << finding.query
                    << ": "
                    << finding.reason
                    << "\n";
            }
        }

        std::cout << "\nINDEX STORAGE ESTIMATE\n"
                  << std::string(72, '=')
                  << "\n";

        StorageEstimate enrollment_index{
            2000000,
            8,
            8,
            0.15
        };

        std::cout
            << "Estimated enrollment index footprint: "
            << std::fixed
            << std::setprecision(1)
            << mib(enrollment_index.bytes())
            << " MiB\n";

        std::cout
            << "This estimate is intentionally approximate. A real storage "
               "engine also has page structure, alignment, fill factor, "
               "visibility metadata, compression, and implementation-specific "
               "overhead.\n";

        std::cout << "\nINTEGRITY CASE STUDY\n"
                  << std::string(72, '=')
                  << "\n";

        EnrollmentDatabase database;

        database.add_student({
            1,
            "S1001",
            "Asha Rao",
            "asha.rao@example.edu"
        });

        database.add_student({
            2,
            "S1002",
            "Ravi Shah",
            "ravi.shah@example.edu"
        });

        database.add_section({
            501,
            301,
            77,
            20261,
            "DB-204",
            2
        });

        database.enroll(
            1,
            501,
            "2026-08-15"
        );

        database.assign_grade(
            1,
            501,
            "A"
        );

        std::cout
            << "Valid enrollment and grade assignment succeeded.\n";

        try {
            database.enroll(
                1,
                501,
                "2026-08-16"
            );
        } catch (const std::exception& error) {
            std::cout
                << "Expected duplicate-key rejection: "
                << error.what()
                << "\n";
        }

        try {
            database.enroll(
                999,
                501,
                "2026-08-16"
            );
        } catch (const std::exception& error) {
            std::cout
                << "Expected foreign-key rejection: "
                << error.what()
                << "\n";
        }

        std::cout << "\nBATCH OPERATION\n"
                  << std::string(72, '=')
                  << "\n";

        EnrollmentTransaction transaction(database);

        try {
            transaction.execute({
                {2, 501, "2026-08-16"},
                {999, 501, "2026-08-16"}
            });

            transaction.commit();
        } catch (const std::exception& error) {
            std::cout
                << "Batch rejected after constraint failure: "
                << error.what()
                << "\n";

            std::cout
                << "A production implementation should rely on the database "
                   "transaction manager for atomic rollback rather than an "
                   "application-level reconstruction of state.\n";
        }

        std::cout
            << "\nCurrent enrollment count: "
            << database.enrollment_count()
            << "\n";

        std::cout << "\nLOGICAL VS PHYSICAL DESIGN\n"
                  << std::string(72, '=')
                  << "\n"
                  << "Logical design decides what the data means and how "
                     "business entities relate.\n"
                  << "Physical design decides how those facts are stored and "
                     "accessed efficiently.\n"
                  << "Changing an index should normally not change the meaning "
                     "of student, course, section, or enrollment.\n"
                  << "Changing a relationship or dependency can change the "
                     "logical model and therefore requires broader analysis.\n";

        std::cout << "\nDESIGN OBJECTIVES\n"
                  << std::string(72, '=')
                  << "\n"
                  << "Integrity: enforce keys, foreign keys, domains, and "
                     "business constraints.\n"
                  << "Performance: optimize measured access patterns without "
                     "creating unnecessary indexes.\n"
                  << "Maintainability: give each business fact a clear owner "
                     "and minimize accidental duplication.\n"
                  << "Scalability: account for data growth, workload growth, "
                     "and operational lifecycle.\n"
                  << "Storage efficiency: balance row width, indexes, "
                     "partitioning, and historical retention.\n"
                  << "Security: expose only the data and operations required "
                     "by each database role.\n";

        std::cout
            << "\nThe case study demonstrates why a sound database design "
               "starts with business semantics and then uses workload evidence "
               "to shape the physical implementation.\n";

        return 0;

    } catch (const std::exception& error) {
        std::cerr
            << "Fatal design-analysis error: "
            << error.what()
            << "\n";

        return 1;
    }
}
