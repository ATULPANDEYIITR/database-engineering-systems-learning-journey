#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * PostgreSQL Index Governance Case Study
 *
 * Scenario:
 * A large engineering organization stores repository activity in PostgreSQL.
 * Its database team must choose index access methods for operational queries.
 *
 * The program implements an index-advisor engine rather than reproducing
 * database internals. It evaluates predicates against a workload and explains
 * why B-tree, Hash, GIN, GiST, or BRIN is structurally appropriate.
 *
 * C++17 standard library only.
 */

enum class IndexMethod {
    BTree,
    Hash,
    GIN,
    GiST,
    BRIN,
    SequentialScan
};

std::string toString(IndexMethod method) {
    switch (method) {
        case IndexMethod::BTree: return "B-tree";
        case IndexMethod::Hash: return "Hash";
        case IndexMethod::GIN: return "GIN";
        case IndexMethod::GiST: return "GiST";
        case IndexMethod::BRIN: return "BRIN";
        case IndexMethod::SequentialScan: return "Sequential Scan";
    }
    return "Unknown";
}

enum class PredicateKind {
    Equality,
    Range,
    CollectionContains,
    RangeOverlap,
    OrderedLookup
};

struct QueryPredicate {
    std::string column;
    PredicateKind kind;
    std::string description;
};

struct IndexDefinition {
    std::string name;
    IndexMethod method;
    std::string column;
    std::set<PredicateKind> supported;
    std::string rationale;
};

struct WorkloadObservation {
    QueryPredicate predicate;
    IndexMethod selected;
    std::string explanation;
};

class IndexAdvisor {
private:
    std::vector<IndexDefinition> definitions;

public:
    IndexAdvisor() {
        definitions.push_back({
            "idx_activity_repository_btree",
            IndexMethod::BTree,
            "repository_id",
            {PredicateKind::Equality, PredicateKind::Range, PredicateKind::OrderedLookup},
            "B-tree supports equality, ordering, and range navigation."
        });

        definitions.push_back({
            "idx_activity_repository_hash",
            IndexMethod::Hash,
            "repository_id",
            {PredicateKind::Equality},
            "Hash is specialized for equality lookup."
        });

        definitions.push_back({
            "idx_activity_labels_gin",
            IndexMethod::GIN,
            "labels",
            {PredicateKind::CollectionContains},
            "GIN stores inverted membership information for collection values."
        });

        definitions.push_back({
            "idx_activity_lifecycle_gist",
            IndexMethod::GiST,
            "lifecycle",
            {PredicateKind::RangeOverlap},
            "GiST supports range-oriented operator classes and overlap searches."
        });

        definitions.push_back({
            "idx_activity_created_brin",
            IndexMethod::BRIN,
            "created_at",
            {PredicateKind::Range},
            "BRIN summarizes physical block ranges and is compact for correlated data."
        });
    }

    WorkloadObservation advise(const QueryPredicate& predicate) const {
        std::vector<const IndexDefinition*> candidates;

        for (const auto& definition : definitions) {
            if (definition.column == predicate.column &&
                definition.supported.contains(predicate.kind)) {
                candidates.push_back(&definition);
            }
        }

        if (candidates.empty()) {
            return {
                predicate,
                IndexMethod::SequentialScan,
                "No modeled index access method directly supports this predicate."
            };
        }

        // B-tree has broader semantics than Hash for equality workloads.
        if (predicate.kind == PredicateKind::Equality) {
            for (const auto* candidate : candidates) {
                if (candidate->method == IndexMethod::BTree) {
                    return {
                        predicate,
                        IndexMethod::BTree,
                        "B-tree is preferred because the same index can also serve "
                        "ordering and range workloads."
                    };
                }
            }
        }

        return {
            predicate,
            candidates.front()->method,
            candidates.front()->rationale
        };
    }

    void printCatalog() const {
        std::cout << "\nIndex catalog\n";

        for (const auto& definition : definitions) {
            std::cout
                << "  " << definition.name
                << " | " << toString(definition.method)
                << " | column=" << definition.column
                << "\n    " << definition.rationale << '\n';
        }
    }
};

struct RepositoryActivity {
    int id;
    int repositoryId;
    std::string eventType;
    std::set<std::string> labels;
    int createdDay;
    int durationDays;
};

class RepositoryWorkload {
private:
    std::vector<RepositoryActivity> rows;

public:
    RepositoryWorkload() {
        rows = {
            {1, 101, "pull_request", {"postgresql", "database"}, 10, 2},
            {2, 101, "deployment", {"release"}, 20, 1},
            {3, 102, "pull_request", {"security", "postgresql"}, 35, 7},
            {4, 102, "incident", {"security"}, 44, 3},
            {5, 103, "pull_request", {"performance", "gin"}, 60, 5},
            {6, 103, "deployment", {"release", "performance"}, 72, 2},
            {7, 101, "pull_request", {"postgresql", "range"}, 80, 8},
            {8, 102, "pull_request", {"security", "audit"}, 91, 4}
        };
    }

    std::vector<int> execute(const QueryPredicate& predicate) const {
        std::vector<int> result;

        for (const auto& row : rows) {
            bool match = false;

            if (predicate.column == "repository_id" &&
                predicate.kind == PredicateKind::Equality) {
                match = row.repositoryId == 102;
            }

            if (predicate.column == "labels" &&
                predicate.kind == PredicateKind::CollectionContains) {
                match =
                    row.labels.contains("postgresql") &&
                    row.labels.contains("security");
            }

            if (predicate.column == "created_at" &&
                predicate.kind == PredicateKind::Range) {
                match = row.createdDay >= 50 && row.createdDay <= 80;
            }

            if (predicate.column == "lifecycle" &&
                predicate.kind == PredicateKind::RangeOverlap) {
                const int requestedStart = 42;
                const int requestedEnd = 50;
                const int rowStart = row.createdDay;
                const int rowEnd = row.createdDay + row.durationDays;

                match = rowStart <= requestedEnd && rowEnd >= requestedStart;
            }

            if (match) {
                result.push_back(row.id);
            }
        }

        return result;
    }
};

class MergeEligibilityLikeReport {
public:
    static void analyze(const std::vector<WorkloadObservation>& observations) {
        std::map<IndexMethod, int> usage;

        for (const auto& observation : observations) {
            usage[observation.selected]++;
        }

        std::cout << "\nWorkload access-method distribution\n";

        for (const auto& [method, count] : usage) {
            std::cout
                << "  " << std::left << std::setw(18)
                << toString(method)
                << " queries=" << count << '\n';
        }

        std::cout << "\nEngineering interpretation\n";
        std::cout
            << "  A B-tree is the default general-purpose choice when "
               "equality, ordering, or ranges matter.\n"
            << "  A Hash index is narrow: it is useful when equality is the "
               "dominant requirement and ordering is irrelevant.\n"
            << "  GIN is appropriate when one row contains multiple searchable "
               "keys such as array or JSONB elements.\n"
            << "  GiST is valuable when the predicate is defined by an "
               "operator class such as range overlap.\n"
            << "  BRIN is most attractive for very large, physically ordered "
               "tables where block summaries eliminate large regions of I/O.\n";
    }
};

int main() {
    std::cout << "PostgreSQL Index Access-Method Case Study\n";
    std::cout << "B-tree | Hash | GIN | GiST | BRIN\n";

    IndexAdvisor advisor;
    RepositoryWorkload workload;

    advisor.printCatalog();

    const std::vector<QueryPredicate> queries = {
        {
            "repository_id",
            PredicateKind::Equality,
            "Find activity belonging to repository 102"
        },
        {
            "labels",
            PredicateKind::CollectionContains,
            "Find rows containing both postgresql and security labels"
        },
        {
            "lifecycle",
            PredicateKind::RangeOverlap,
            "Find lifecycle ranges overlapping a maintenance window"
        },
        {
            "created_at",
            PredicateKind::Range,
            "Find activity created between physical-time boundaries"
        }
    };

    std::vector<WorkloadObservation> observations;

    std::cout << "\nQuery workload analysis\n";

    for (const auto& query : queries) {
        auto observation = advisor.advise(query);
        observations.push_back(observation);

        const auto result = workload.execute(query);

        std::cout
            << "\nPredicate: " << query.description
            << "\nAccess method: " << toString(observation.selected)
            << "\nReason: " << observation.explanation
            << "\nCandidate row IDs: ";

        if (result.empty()) {
            std::cout << "(none)";
        } else {
            for (std::size_t i = 0; i < result.size(); ++i) {
                if (i > 0) std::cout << ", ";
                std::cout << result[i];
            }
        }

        std::cout << '\n';
    }

    MergeEligibilityLikeReport::analyze(observations);

    std::cout << "\nIndex design constraints\n";
    std::cout
        << "  Index maintenance consumes write I/O and storage.\n"
        << "  Selectivity affects whether an index scan is cheaper than a sequential scan.\n"
        << "  PostgreSQL statistics influence the planner's estimated costs.\n"
        << "  A BRIN index can remain tiny because it summarizes page ranges rather "
           "than storing one search entry per tuple.\n"
        << "  GIN can be substantially larger and more write-intensive because "
           "one row may contribute many indexed keys.\n"
        << "  GiST behavior depends on the operator class and predicate geometry.\n";

    std::cout << "\nCase-study result: access method selection must follow the "
                 "operator semantics and physical data characteristics, not "
                 "the popularity of a particular index type.\n";

    return 0;
}
