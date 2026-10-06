/*
 * Advanced Database Normalization: BCNF, 4NF, and 5NF
 *
 * C++17+
 *
 * Case study:
 * A university data platform stores teaching assignments, instructor
 * offices, independent employee capabilities, and supplier-part-project
 * relationships. The program implements a normalization analysis engine
 * capable of evaluating:
 *
 *   - attribute closures
 *   - candidate keys
 *   - BCNF violations
 *   - BCNF decomposition
 *   - multivalued dependencies
 *   - 4NF violations and decomposition
 *   - join dependencies relevant to 5NF
 *   - lossless reconstruction using concrete relation instances
 *   - dependency-preservation trade-offs
 *
 * The program intentionally uses standard-library data structures so the
 * normalization algorithms remain visible rather than being hidden behind
 * external database libraries.
 */

#include <algorithm>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

using Attribute = std::string;
using AttributeSet = std::set<Attribute>;

struct FunctionalDependency {
    AttributeSet determinant;
    AttributeSet dependent;
};

struct MultivaluedDependency {
    AttributeSet determinant;
    AttributeSet dependent;
    AttributeSet relation;
};

struct JoinDependency {
    AttributeSet relation;
    std::vector<AttributeSet> components;
};

struct RelationSchema {
    std::string name;
    AttributeSet attributes;
    std::vector<FunctionalDependency> functionalDependencies;
    std::vector<MultivaluedDependency> multivaluedDependencies;
    std::vector<JoinDependency> joinDependencies;
};

using Row = std::map<Attribute, std::string>;

std::string formatSet(const AttributeSet& attributes) {
    std::ostringstream output;
    output << "{";

    bool first = true;
    for (const auto& attribute : attributes) {
        if (!first) {
            output << ", ";
        }
        output << attribute;
        first = false;
    }

    output << "}";
    return output.str();
}

std::string formatFD(const FunctionalDependency& fd) {
    return formatSet(fd.determinant) + " -> " + formatSet(fd.dependent);
}

std::string formatMVD(const MultivaluedDependency& mvd) {
    return formatSet(mvd.determinant) + " ->> "
        + formatSet(mvd.dependent)
        + " in "
        + formatSet(mvd.relation);
}

AttributeSet setUnion(
    const AttributeSet& left,
    const AttributeSet& right
) {
    AttributeSet result = left;
    result.insert(right.begin(), right.end());
    return result;
}

AttributeSet setDifference(
    const AttributeSet& left,
    const AttributeSet& right
) {
    AttributeSet result;

    for (const auto& attribute : left) {
        if (!right.contains(attribute)) {
            result.insert(attribute);
        }
    }

    return result;
}

bool isSubset(
    const AttributeSet& subset,
    const AttributeSet& superset
) {
    for (const auto& attribute : subset) {
        if (!superset.contains(attribute)) {
            return false;
        }
    }

    return true;
}

bool isEqual(
    const AttributeSet& left,
    const AttributeSet& right
) {
    return left == right;
}

AttributeSet attributeClosure(
    const AttributeSet& attributes,
    const std::vector<FunctionalDependency>& dependencies
) {
    AttributeSet closure = attributes;

    bool changed = true;

    while (changed) {
        changed = false;

        for (const auto& dependency : dependencies) {
            if (!isSubset(dependency.determinant, closure)) {
                continue;
            }

            const std::size_t before = closure.size();

            closure.insert(
                dependency.dependent.begin(),
                dependency.dependent.end()
            );

            if (closure.size() != before) {
                changed = true;
            }
        }
    }

    return closure;
}

bool isSuperkey(
    const AttributeSet& candidate,
    const AttributeSet& relation,
    const std::vector<FunctionalDependency>& dependencies
) {
    return isEqual(
        attributeClosure(candidate, dependencies),
        relation
    );
}

std::vector<AttributeSet> allSubsets(
    const AttributeSet& attributes
) {
    std::vector<Attribute> ordered(
        attributes.begin(),
        attributes.end()
    );

    std::vector<AttributeSet> result;

    const std::size_t count = ordered.size();

    if (count >= sizeof(std::size_t) * 8) {
        throw std::runtime_error(
            "Exhaustive subset enumeration is unsuitable for this schema size."
        );
    }

    const std::size_t total = static_cast<std::size_t>(1) << count;

    for (std::size_t mask = 0; mask < total; ++mask) {
        AttributeSet subset;

        for (std::size_t bit = 0; bit < count; ++bit) {
            if ((mask & (static_cast<std::size_t>(1) << bit)) != 0) {
                subset.insert(ordered[bit]);
            }
        }

        result.push_back(subset);
    }

    std::sort(
        result.begin(),
        result.end(),
        [](const AttributeSet& left, const AttributeSet& right) {
            if (left.size() != right.size()) {
                return left.size() < right.size();
            }
            return left < right;
        }
    );

    return result;
}

std::vector<AttributeSet> candidateKeys(
    const AttributeSet& relation,
    const std::vector<FunctionalDependency>& dependencies
) {
    std::vector<AttributeSet> keys;

    for (const auto& subset : allSubsets(relation)) {
        if (subset.empty()) {
            continue;
        }

        if (!isSuperkey(subset, relation, dependencies)) {
            continue;
        }

        bool containsExistingKey = false;

        for (const auto& key : keys) {
            if (isSubset(key, subset)) {
                containsExistingKey = true;
                break;
            }
        }

        if (!containsExistingKey) {
            keys.push_back(subset);
        }
    }

    return keys;
}

bool isTrivial(
    const FunctionalDependency& dependency
) {
    return isSubset(
        dependency.dependent,
        dependency.determinant
    );
}

std::vector<FunctionalDependency> bcnfViolations(
    const RelationSchema& relation
) {
    std::vector<FunctionalDependency> violations;

    for (const auto& dependency : relation.functionalDependencies) {
        if (isTrivial(dependency)) {
            continue;
        }

        if (!isSuperkey(
                dependency.determinant,
                relation.attributes,
                relation.functionalDependencies
            )) {
            violations.push_back(dependency);
        }
    }

    return violations;
}

std::vector<FunctionalDependency> projectFDs(
    const RelationSchema& source,
    const AttributeSet& attributes
) {
    std::vector<FunctionalDependency> result;

    for (const auto& dependency : source.functionalDependencies) {
        AttributeSet involved = setUnion(
            dependency.determinant,
            dependency.dependent
        );

        if (isSubset(involved, attributes)) {
            result.push_back(dependency);
        }
    }

    return result;
}

std::vector<RelationSchema> bcnfDecompose(
    const RelationSchema& relation
) {
    const auto violations = bcnfViolations(relation);

    if (violations.empty()) {
        return {relation};
    }

    const FunctionalDependency violation = violations.front();

    const AttributeSet firstAttributes = setUnion(
        violation.determinant,
        violation.dependent
    );

    const AttributeSet secondAttributes = setUnion(
        violation.determinant,
        setDifference(
            relation.attributes,
            violation.dependent
        )
    );

    RelationSchema first{
        relation.name + "_BCNF_A",
        firstAttributes,
        projectFDs(relation, firstAttributes),
        {},
        {}
    };

    RelationSchema second{
        relation.name + "_BCNF_B",
        secondAttributes,
        projectFDs(relation, secondAttributes),
        {},
        {}
    };

    std::vector<RelationSchema> result;

    const auto firstResult = bcnfDecompose(first);
    const auto secondResult = bcnfDecompose(second);

    result.insert(
        result.end(),
        firstResult.begin(),
        firstResult.end()
    );

    result.insert(
        result.end(),
        secondResult.begin(),
        secondResult.end()
    );

    return result;
}

bool nonTrivialMVD(
    const MultivaluedDependency& mvd
) {
    const AttributeSet xAndY = setUnion(
        mvd.determinant,
        mvd.dependent
    );

    return !mvd.dependent.empty()
        && !isSubset(mvd.dependent, mvd.determinant)
        && xAndY != mvd.relation;
}

std::vector<MultivaluedDependency> fourNFViolations(
    const RelationSchema& relation
) {
    std::vector<MultivaluedDependency> violations;

    for (const auto& fd : relation.functionalDependencies) {
        MultivaluedDependency mvd{
            fd.determinant,
            fd.dependent,
            relation.attributes
        };

        if (
            nonTrivialMVD(mvd)
            && !isSuperkey(
                mvd.determinant,
                relation.attributes,
                relation.functionalDependencies
            )
        ) {
            violations.push_back(mvd);
        }
    }

    for (const auto& mvd : relation.multivaluedDependencies) {
        if (
            nonTrivialMVD(mvd)
            && !isSuperkey(
                mvd.determinant,
                relation.attributes,
                relation.functionalDependencies
            )
        ) {
            violations.push_back(mvd);
        }
    }

    return violations;
}

std::pair<RelationSchema, RelationSchema> fourNFDecompose(
    const RelationSchema& relation,
    const MultivaluedDependency& violation
) {
    const AttributeSet firstAttributes = setUnion(
        violation.determinant,
        violation.dependent
    );

    const AttributeSet secondAttributes = setUnion(
        violation.determinant,
        setDifference(
            relation.attributes,
            violation.dependent
        )
    );

    return {
        RelationSchema{
            relation.name + "_4NF_A",
            firstAttributes,
            {},
            {},
            {}
        },
        RelationSchema{
            relation.name + "_4NF_B",
            secondAttributes,
            {},
            {},
            {}
        }
    };
}

bool rowsSatisfyFD(
    const std::vector<Row>& rows,
    const FunctionalDependency& dependency
) {
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

            for (const auto& attribute : dependency.dependent) {
                if (rows[i].at(attribute) != rows[j].at(attribute)) {
                    return false;
                }
            }
        }
    }

    return true;
}

std::string rowKey(const Row& row) {
    std::ostringstream output;

    for (const auto& [attribute, value] : row) {
        output << attribute << "=" << value << "|";
    }

    return output.str();
}

std::vector<Row> naturalJoin(
    const std::vector<Row>& left,
    const std::vector<Row>& right
) {
    std::vector<Row> result;
    std::set<std::string> seen;

    for (const auto& leftRow : left) {
        for (const auto& rightRow : right) {
            bool compatible = true;

            for (const auto& [attribute, value] : leftRow) {
                auto rightValue = rightRow.find(attribute);

                if (
                    rightValue != rightRow.end()
                    && rightValue->second != value
                ) {
                    compatible = false;
                    break;
                }
            }

            if (!compatible) {
                continue;
            }

            Row merged = leftRow;
            merged.insert(rightRow.begin(), rightRow.end());

            if (seen.insert(rowKey(merged)).second) {
                result.push_back(merged);
            }
        }
    }

    return result;
}

std::vector<Row> projectRows(
    const std::vector<Row>& rows,
    const AttributeSet& attributes
) {
    std::vector<Row> result;
    std::set<std::string> seen;

    for (const auto& row : rows) {
        Row projected;

        for (const auto& attribute : attributes) {
            projected[attribute] = row.at(attribute);
        }

        if (seen.insert(rowKey(projected)).second) {
            result.push_back(projected);
        }
    }

    return result;
}

void printRows(const std::vector<Row>& rows) {
    for (const auto& row : rows) {
        std::cout << "  {";

        bool first = true;
        for (const auto& [attribute, value] : row) {
            if (!first) {
                std::cout << ", ";
            }

            std::cout << attribute << "=" << value;
            first = false;
        }

        std::cout << "}\n";
    }
}

void printSchema(const RelationSchema& relation) {
    std::cout << "\nRelation: " << relation.name << "\n";
    std::cout << "Attributes: "
              << formatSet(relation.attributes)
              << "\n";

    if (!relation.functionalDependencies.empty()) {
        std::cout << "Functional dependencies:\n";

        for (const auto& dependency : relation.functionalDependencies) {
            std::cout << "  "
                      << formatFD(dependency)
                      << "\n";
        }
    }

    if (!relation.multivaluedDependencies.empty()) {
        std::cout << "Multivalued dependencies:\n";

        for (const auto& dependency : relation.multivaluedDependencies) {
            std::cout << "  "
                      << formatMVD(dependency)
                      << "\n";
        }
    }
}

void demonstrateBCNFCaseStudy() {
    std::cout << "\n=== BCNF CASE STUDY ===\n";

    /*
     * A student can take many courses, and an instructor has one office.
     * The instructor-office dependency has a determinant that is not a
     * candidate key of the original relation.
     */
    RelationSchema teaching{
        "TeachingAssignment",
        {
            "Student",
            "Course",
            "Instructor",
            "InstructorOffice"
        },
        {
            {
                {"Student", "Course"},
                {"Instructor"}
            },
            {
                {"Instructor"},
                {"InstructorOffice"}
            }
        },
        {},
        {}
    };

    printSchema(teaching);

    const auto keys = candidateKeys(
        teaching.attributes,
        teaching.functionalDependencies
    );

    std::cout << "Candidate keys:\n";
    for (const auto& key : keys) {
        std::cout << "  " << formatSet(key) << "\n";
    }

    const auto violations = bcnfViolations(teaching);

    std::cout << "BCNF violations:\n";
    for (const auto& violation : violations) {
        std::cout << "  "
                  << formatFD(violation)
                  << "\n";
    }

    const auto decomposition = bcnfDecompose(teaching);

    std::cout << "BCNF decomposition:\n";
    for (const auto& relation : decomposition) {
        printSchema(relation);
    }
}

void demonstrate4NFCaseStudy() {
    std::cout << "\n=== 4NF CASE STUDY ===\n";

    /*
     * Skills and spoken languages are independent multivalued facts about an
     * employee. Storing both in one relation forces the Cartesian combination
     * of skills and languages for each employee.
     */
    RelationSchema employee{
        "EmployeeCapability",
        {
            "Employee",
            "Skill",
            "Language"
        },
        {},
        {
            {
                {"Employee"},
                {"Skill"},
                {"Employee", "Skill", "Language"}
            }
        },
        {}
    };

    printSchema(employee);

    const auto violations = fourNFViolations(employee);

    for (const auto& violation : violations) {
        std::cout << "4NF violation: "
                  << formatMVD(violation)
                  << "\n";

        const auto decomposition = fourNFDecompose(
            employee,
            violation
        );

        std::cout << "4NF relations:\n";
        printSchema(decomposition.first);
        printSchema(decomposition.second);
    }

    std::vector<Row> original{
        {
            {"Employee", "E1"},
            {"Skill", "C++"},
            {"Language", "English"}
        },
        {
            {"Employee", "E1"},
            {"Skill", "C++"},
            {"Language", "French"}
        },
        {
            {"Employee", "E1"},
            {"Skill", "SQL"},
            {"Language", "English"}
        },
        {
            {"Employee", "E1"},
            {"Skill", "SQL"},
            {"Language", "French"}
        }
    };

    const std::vector<Row> employeeSkills =
        projectRows(
            original,
            {"Employee", "Skill"}
        );

    const std::vector<Row> employeeLanguages =
        projectRows(
            original,
            {"Employee", "Language"}
        );

    const auto reconstructed = naturalJoin(
        employeeSkills,
        employeeLanguages
    );

    std::cout << "Employee-Skill:\n";
    printRows(employeeSkills);

    std::cout << "Employee-Language:\n";
    printRows(employeeLanguages);

    std::cout << "Reconstructed relation:\n";
    printRows(reconstructed);
}

void demonstrate5NFCaseStudy() {
    std::cout << "\n=== 5NF CASE STUDY ===\n";

    /*
     * The ternary Supplier-Part-Project association is decomposed into three
     * pairwise relations only under a business rule that says the ternary
     * association is completely determined by those pairwise facts.
     *
     * Without that semantic rule, a pairwise decomposition can create
     * combinations that were never actually authorized.
     */
    RelationSchema supply{
        "SupplierPartProject",
        {
            "Supplier",
            "Part",
            "Project"
        },
        {},
        {},
        {
            {
                {
                    "Supplier",
                    "Part",
                    "Project"
                },
                {
                    {"Supplier", "Part"},
                    {"Supplier", "Project"},
                    {"Part", "Project"}
                }
            }
        }
    };

    printSchema(supply);

    std::vector<Row> supplierPart{
        {
            {"Supplier", "S1"},
            {"Part", "P1"}
        },
        {
            {"Supplier", "S1"},
            {"Part", "P2"}
        }
    };

    std::vector<Row> supplierProject{
        {
            {"Supplier", "S1"},
            {"Project", "J1"}
        }
    };

    std::vector<Row> partProject{
        {
            {"Part", "P1"},
            {"Project", "J1"}
        },
        {
            {"Part", "P2"},
            {"Project", "J1"}
        }
    };

    const auto intermediate = naturalJoin(
        supplierPart,
        supplierProject
    );

    const auto reconstructed = naturalJoin(
        intermediate,
        partProject
    );

    std::cout << "Supplier-Part:\n";
    printRows(supplierPart);

    std::cout << "Supplier-Project:\n";
    printRows(supplierProject);

    std::cout << "Part-Project:\n";
    printRows(partProject);

    std::cout << "Three-way reconstruction:\n";
    printRows(reconstructed);
}

void demonstrateLosslessBCNFReconstruction() {
    std::cout << "\n=== LOSSLESS RECONSTRUCTION ===\n";

    /*
     * The original teaching data contains an instructor office determined
     * solely by instructor. The decomposition separates that dependency
     * into InstructorOffice and TeachingAssignment.
     */
    std::vector<Row> original{
        {
            {"Student", "S1"},
            {"Course", "DB101"},
            {"Instructor", "I1"},
            {"InstructorOffice", "B201"}
        },
        {
            {"Student", "S2"},
            {"Course", "DB101"},
            {"Instructor", "I1"},
            {"InstructorOffice", "B201"}
        },
        {
            {"Student", "S1"},
            {"Course", "OS201"},
            {"Instructor", "I2"},
            {"InstructorOffice", "C102"}
        }
    };

    const auto teaching =
        projectRows(
            original,
            {"Student", "Course", "Instructor"}
        );

    const auto offices =
        projectRows(
            original,
            {"Instructor", "InstructorOffice"}
        );

    const auto reconstructed =
        naturalJoin(teaching, offices);

    std::cout << "Original relation:\n";
    printRows(original);

    std::cout << "Teaching relation:\n";
    printRows(teaching);

    std::cout << "Instructor office relation:\n";
    printRows(offices);

    std::cout << "Natural join reconstruction:\n";
    printRows(reconstructed);

    std::cout
        << "The reconstruction succeeds because the common determinant "
        << "Instructor functionally determines InstructorOffice.\n";
}

void discussTradeoffs() {
    std::cout << "\n=== DESIGN TRADE-OFFS ===\n";

    std::cout
        << "BCNF provides stronger redundancy control than 3NF, but a BCNF "
        << "decomposition may fail to preserve every original dependency.\n";

    std::cout
        << "4NF addresses independent multivalued facts that functional "
        << "dependencies alone do not adequately model.\n";

    std::cout
        << "5NF is stricter still. A decomposition based on a join dependency "
        << "must be justified by actual relationship semantics, not merely by "
        << "the presence of three attributes.\n";

    std::cout
        << "Candidate-key enumeration is exponential in the number of "
        << "attributes, so the exhaustive implementation is appropriate for "
        << "learning and small schemas rather than large production catalogs.\n";
}

int main() {
    std::cout
        << "============================================================\n"
        << "ADVANCED NORMALIZATION: BCNF, 4NF, AND 5NF\n"
        << "============================================================\n";

    demonstrateBCNFCaseStudy();
    demonstrate4NFCaseStudy();
    demonstrate5NFCaseStudy();
    demonstrateLosslessBCNFReconstruction();
    discussTradeoffs();

    std::cout << "\n=== END OF CASE STUDY ===\n";

    return 0;
}
