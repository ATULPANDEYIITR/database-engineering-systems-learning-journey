/*
 * Set Operations in C++
 * =====================
 *
 * Detailed industry-style case study:
 * Secure Access and Resource Reconciliation System
 *
 * The program demonstrates:
 * - std::set
 * - std::unordered_set
 * - uniqueness
 * - insertion and deletion
 * - union
 * - intersection
 * - difference
 * - symmetric difference
 * - subset and superset checks
 * - disjointness
 * - permission validation
 * - role-based access control
 * - resource reconciliation
 * - graph-style relationships
 * - validation and error handling
 * - complexity considerations
 * - deterministic ordered output
 *
 * Compile:
 *   g++ -std=c++17 -Wall -Wextra -pedantic set_operations.cpp -o set_operations
 */

#include <algorithm>
#include <chrono>
#include <iostream>
#include <iterator>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

using StringSet = std::set<std::string>;

void section(const std::string& title) {
    std::cout << "\n" << std::string(78, '=') << "\n";
    std::cout << title << "\n";
    std::cout << std::string(78, '=') << "\n";
}

template <typename Container>
void printContainer(
    const std::string& label,
    const Container& values
) {
    std::cout << label << ": {";

    bool first = true;
    for (const auto& value : values) {
        if (!first) {
            std::cout << ", ";
        }

        std::cout << value;
        first = false;
    }

    std::cout << "}\n";
}

template <typename Set>
Set setUnion(const Set& first, const Set& second) {
    Set result;

    std::set_union(
        first.begin(),
        first.end(),
        second.begin(),
        second.end(),
        std::inserter(result, result.begin())
    );

    return result;
}

template <typename Set>
Set setIntersection(const Set& first, const Set& second) {
    Set result;

    std::set_intersection(
        first.begin(),
        first.end(),
        second.begin(),
        second.end(),
        std::inserter(result, result.begin())
    );

    return result;
}

template <typename Set>
Set setDifference(const Set& first, const Set& second) {
    Set result;

    std::set_difference(
        first.begin(),
        first.end(),
        second.begin(),
        second.end(),
        std::inserter(result, result.begin())
    );

    return result;
}

template <typename Set>
Set symmetricDifference(const Set& first, const Set& second) {
    Set result;

    std::set_symmetric_difference(
        first.begin(),
        first.end(),
        second.begin(),
        second.end(),
        std::inserter(result, result.begin())
    );

    return result;
}

template <typename Set>
bool isSubset(const Set& subset, const Set& superset) {
    return std::includes(
        superset.begin(),
        superset.end(),
        subset.begin(),
        subset.end()
    );
}

template <typename Set>
bool isDisjoint(const Set& first, const Set& second) {
    auto firstIterator = first.begin();
    auto secondIterator = second.begin();

    while (
        firstIterator != first.end() &&
        secondIterator != second.end()
    ) {
        if (*firstIterator == *secondIterator) {
            return false;
        }

        if (*firstIterator < *secondIterator) {
            ++firstIterator;
        } else {
            ++secondIterator;
        }
    }

    return true;
}

void demonstrateFundamentals() {
    section("1. SET FUNDAMENTALS");

    StringSet permissions = {
        "read",
        "write",
        "execute"
    };

    printContainer("permissions", permissions);

    // std::set stores unique values in sorted order.
    permissions.insert("read");
    permissions.insert("delete");

    printContainer("after insertions", permissions);

    std::cout
        << "contains read: "
        << (permissions.contains("read") ? "yes" : "no")
        << "\n";

    std::cout
        << "contains admin: "
        << (permissions.contains("admin") ? "yes" : "no")
        << "\n";

    permissions.erase("delete");

    printContainer("after deleting delete", permissions);
}

void demonstrateCoreOperations() {
    section("2. CORE SET OPERATIONS");

    StringSet developers = {
        "Asha",
        "Ravi",
        "Neha",
        "Kabir"
    };

    StringSet securityTeam = {
        "Neha",
        "Kabir",
        "Meera",
        "Arjun"
    };

    printContainer("developers", developers);
    printContainer("security team", securityTeam);

    printContainer(
        "union",
        setUnion(developers, securityTeam)
    );

    printContainer(
        "intersection",
        setIntersection(developers, securityTeam)
    );

    printContainer(
        "developers only",
        setDifference(developers, securityTeam)
    );

    printContainer(
        "security only",
        setDifference(securityTeam, developers)
    );

    printContainer(
        "symmetric difference",
        symmetricDifference(developers, securityTeam)
    );
}

void demonstrateRelationships() {
    section("3. SUBSETS, SUPERSETS, AND DISJOINTNESS");

    StringSet permissions = {
        "read",
        "write",
        "execute"
    };

    StringSet required = {
        "read",
        "write"
    };

    StringSet unrelated = {
        "database",
        "network"
    };

    std::cout
        << "required is subset: "
        << (isSubset(required, permissions) ? "yes" : "no")
        << "\n";

    std::cout
        << "permissions is superset: "
        << (isSubset(required, permissions) ? "yes" : "no")
        << "\n";

    std::cout
        << "permissions are disjoint from unrelated: "
        << (isDisjoint(permissions, unrelated) ? "yes" : "no")
        << "\n";
}

void demonstrateAlgebra() {
    section("4. SET ALGEBRA");

    StringSet a = {"A", "B", "C"};
    StringSet b = {"C", "D", "E"};
    StringSet c = {"E", "F"};

    const bool unionCommutative =
        setUnion(a, b) == setUnion(b, a);

    const bool intersectionCommutative =
        setIntersection(a, b) == setIntersection(b, a);

    const bool unionAssociative =
        setUnion(setUnion(a, b), c) ==
        setUnion(a, setUnion(b, c));

    const bool intersectionAssociative =
        setIntersection(setIntersection(a, b), c) ==
        setIntersection(a, setIntersection(b, c));

    std::cout
        << "union commutative: "
        << (unionCommutative ? "yes" : "no")
        << "\n";

    std::cout
        << "intersection commutative: "
        << (intersectionCommutative ? "yes" : "no")
        << "\n";

    std::cout
        << "union associative: "
        << (unionAssociative ? "yes" : "no")
        << "\n";

    std::cout
        << "intersection associative: "
        << (intersectionAssociative ? "yes" : "no")
        << "\n";
}

void demonstrateDeMorganLaw() {
    section("5. DE MORGAN'S LAW");

    StringSet universal = {
        "A", "B", "C", "D", "E", "F"
    };

    StringSet a = {"A", "B", "C"};
    StringSet b = {"C", "D"};

    StringSet left =
        setDifference(
            universal,
            setUnion(a, b)
        );

    StringSet right =
        setIntersection(
            setDifference(universal, a),
            setDifference(universal, b)
        );

    printContainer(
        "U - (A union B)",
        left
    );

    printContainer(
        "(U - A) intersection (U - B)",
        right
    );

    std::cout
        << "identity holds: "
        << (left == right ? "yes" : "no")
        << "\n";
}

class AccessController {
private:
    StringSet userPermissions;

public:
    explicit AccessController(StringSet permissions)
        : userPermissions(std::move(permissions)) {}

    bool hasPermission(const std::string& permission) const {
        return userPermissions.contains(permission);
    }

    StringSet missingPermissions(
        const StringSet& required
    ) const {
        return setDifference(required, userPermissions);
    }

    StringSet forbiddenPermissions(
        const StringSet& forbidden
    ) const {
        return setIntersection(userPermissions, forbidden);
    }

    bool canPerform(
        const StringSet& required,
        const StringSet& forbidden
    ) const {
        return missingPermissions(required).empty() &&
               forbiddenPermissions(forbidden).empty();
    }

    const StringSet& permissions() const {
        return userPermissions;
    }
};

void demonstrateAccessControl() {
    section("6. INDUSTRY CASE STUDY: ACCESS CONTROL");

    StringSet required = {
        "read",
        "write"
    };

    StringSet forbidden = {
        "admin",
        "manage_users",
        "delete"
    };

    AccessController user({
        "read",
        "write",
        "download"
    });

    printContainer(
        "user permissions",
        user.permissions()
    );

    printContainer(
        "missing permissions",
        user.missingPermissions(required)
    );

    printContainer(
        "forbidden permissions",
        user.forbiddenPermissions(forbidden)
    );

    std::cout
        << "access policy satisfied: "
        << (
            user.canPerform(required, forbidden)
                ? "yes"
                : "no"
        )
        << "\n";
}

struct Role {
    std::string name;
    StringSet permissions;
};

class RoleRepository {
private:
    std::vector<Role> roles;

public:
    void addRole(const Role& role) {
        if (role.name.empty()) {
            throw std::invalid_argument(
                "Role name cannot be empty"
            );
        }

        roles.push_back(role);
    }

    const Role* findRole(
        const std::string& roleName
    ) const {
        for (const auto& role : roles) {
            if (role.name == roleName) {
                return &role;
            }
        }

        return nullptr;
    }
};

void demonstrateRoleBasedAccessControl() {
    section("7. ROLE-BASED ACCESS CONTROL");

    RoleRepository repository;

    repository.addRole({
        "developer",
        {"read", "write", "deploy"}
    });

    repository.addRole({
        "auditor",
        {"read", "audit"}
    });

    repository.addRole({
        "administrator",
        {
            "read",
            "write",
            "delete",
            "manage_users"
        }
    });

    const Role* developer =
        repository.findRole("developer");

    if (developer == nullptr) {
        throw std::runtime_error(
            "Developer role was not found"
        );
    }

    StringSet requested = {
        "read",
        "write"
    };

    StringSet missing =
        setDifference(
            requested,
            developer->permissions
        );

    printContainer(
        "developer permissions",
        developer->permissions
    );

    printContainer(
        "requested permissions",
        requested
    );

    printContainer(
        "missing requested permissions",
        missing
    );

    std::cout
        << "developer satisfies request: "
        << (missing.empty() ? "yes" : "no")
        << "\n";
}

void demonstrateInventoryReconciliation() {
    section("8. INVENTORY RECONCILIATION");

    StringSet expected = {
        "laptop",
        "monitor",
        "keyboard",
        "mouse",
        "dock"
    };

    StringSet scanned = {
        "laptop",
        "monitor",
        "keyboard",
        "dock",
        "headset"
    };

    StringSet confirmed =
        setIntersection(expected, scanned);

    StringSet missing =
        setDifference(expected, scanned);

    StringSet unexpected =
        setDifference(scanned, expected);

    printContainer("confirmed", confirmed);
    printContainer("missing", missing);
    printContainer("unexpected", unexpected);
}

void demonstrateGraphOperations() {
    section("9. GRAPH-STYLE SET OPERATIONS");

    std::set<std::string> aNeighbors = {
        "B",
        "C"
    };

    std::set<std::string> bNeighbors = {
        "A",
        "C",
        "D"
    };

    printContainer(
        "A neighbors",
        aNeighbors
    );

    printContainer(
        "B neighbors",
        bNeighbors
    );

    printContainer(
        "shared neighbors",
        setIntersection(
            aNeighbors,
            bNeighbors
        )
    );

    printContainer(
        "only A",
        setDifference(
            aNeighbors,
            bNeighbors
        )
    );

    printContainer(
        "only B",
        setDifference(
            bNeighbors,
            aNeighbors
        )
    );
}

void demonstrateTagFiltering() {
    section("10. TAG-BASED FILTERING");

    StringSet articleTags = {
        "cpp",
        "algorithms",
        "security",
        "data-structures"
    };

    StringSet requiredTags = {
        "cpp",
        "security"
    };

    StringSet excludedTags = {
        "advertising",
        "politics"
    };

    const bool hasRequired =
        isSubset(requiredTags, articleTags);

    const bool hasExcluded =
        !isDisjoint(articleTags, excludedTags);

    printContainer("article tags", articleTags);

    std::cout
        << "has required tags: "
        << (hasRequired ? "yes" : "no")
        << "\n";

    std::cout
        << "has excluded tags: "
        << (hasExcluded ? "yes" : "no")
        << "\n";

    std::cout
        << "accepted: "
        << (
            hasRequired && !hasExcluded
                ? "yes"
                : "no"
        )
        << "\n";
}

void demonstrateUnorderedSet() {
    section("11. ORDERED SET VERSUS UNORDERED SET");

    std::set<int> ordered = {
        5,
        1,
        4,
        2,
        3
    };

    std::unordered_set<int> unordered = {
        5,
        1,
        4,
        2,
        3
    };

    printContainer("std::set", ordered);
    printContainer("std::unordered_set", unordered);

    /*
     * std::set:
     * - ordered
     * - logarithmic lookup, insertion, and deletion
     * - tree-based implementation
     *
     * std::unordered_set:
     * - no sorted iteration guarantee
     * - average constant-time lookup, insertion, and deletion
     * - hash-table-based implementation
     */
}

void demonstratePerformance() {
    section("12. PERFORMANCE CASE STUDY");

    constexpr int size = 100000;

    std::set<int> first;
    std::set<int> second;

    for (int i = 0; i < size; ++i) {
        first.insert(i);
        second.insert(i + size / 2);
    }

    const auto start =
        std::chrono::high_resolution_clock::now();

    std::set<int> result =
        setIntersection(first, second);

    const auto finish =
        std::chrono::high_resolution_clock::now();

    const std::chrono::duration<double, std::milli> elapsed =
        finish - start;

    std::cout
        << "intersection size: "
        << result.size()
        << "\n";

    std::cout
        << "intersection time: "
        << elapsed.count()
        << " ms\n";

    /*
     * For std::set, individual lookup/insertion/deletion is O(log n).
     * Standard set algorithms process sorted ranges efficiently.
     * Memory consumption is O(n) for storing n distinct elements.
     */
}

void demonstrateEdgeCases() {
    section("13. EDGE CASES");

    StringSet empty;
    StringSet values = {
        "A",
        "B",
        "C"
    };

    printContainer(
        "empty union values",
        setUnion(empty, values)
    );

    printContainer(
        "empty intersection values",
        setIntersection(empty, values)
    );

    printContainer(
        "values minus empty",
        setDifference(values, empty)
    );

    std::cout
        << "empty subset of values: "
        << (isSubset(empty, values) ? "yes" : "no")
        << "\n";

    std::cout
        << "empty disjoint from values: "
        << (isDisjoint(empty, values) ? "yes" : "no")
        << "\n";
}

void demonstrateValidation() {
    section("14. INPUT AND BUSINESS VALIDATION");

    auto validateRequiredPermissions =
        [](
            const StringSet& supplied,
            const StringSet& required
        ) -> bool {
            return isSubset(required, supplied);
        };

    StringSet supplied = {
        "read",
        "write"
    };

    StringSet required = {
        "read",
        "write",
        "download"
    };

    const bool valid =
        validateRequiredPermissions(
            supplied,
            required
        );

    printContainer("supplied", supplied);
    printContainer("required", required);

    std::cout
        << "validation result: "
        << (valid ? "valid" : "invalid")
        << "\n";
}

void runAssertions() {
    section("15. PROGRAMMATIC TESTS");

    StringSet a = {
        "A",
        "B",
        "C"
    };

    StringSet b = {
        "C",
        "D"
    };

    if (
        setUnion(a, b) !=
        StringSet({"A", "B", "C", "D"})
    ) {
        throw std::runtime_error(
            "Union test failed"
        );
    }

    if (
        setIntersection(a, b) !=
        StringSet({"C"})
    ) {
        throw std::runtime_error(
            "Intersection test failed"
        );
    }

    if (
        setDifference(a, b) !=
        StringSet({"A", "B"})
    ) {
        throw std::runtime_error(
            "Difference test failed"
        );
    }

    if (
        symmetricDifference(a, b) !=
        StringSet({"A", "B", "D"})
    ) {
        throw std::runtime_error(
            "Symmetric difference test failed"
        );
    }

    if (!isSubset(
            StringSet({"A", "B"}),
            a
        )) {
        throw std::runtime_error(
            "Subset test failed"
        );
    }

    std::cout << "All set-operation tests passed.\n";
}

int main() {
    try {
        demonstrateFundamentals();
        demonstrateCoreOperations();
        demonstrateRelationships();
        demonstrateAlgebra();
        demonstrateDeMorganLaw();
        demonstrateAccessControl();
        demonstrateRoleBasedAccessControl();
        demonstrateInventoryReconciliation();
        demonstrateGraphOperations();
        demonstrateTagFiltering();
        demonstrateUnorderedSet();
        demonstratePerformance();
        demonstrateEdgeCases();
        demonstrateValidation();
        runAssertions();

        section("16. COMPLETION");
        std::cout
            << "Set operations case study completed successfully.\n";

        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << "\n";

        return 1;
    }
}
