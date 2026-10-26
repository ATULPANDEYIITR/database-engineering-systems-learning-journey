#include <algorithm>
#include <exception>
#include <iostream>
#include <numeric>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

enum class CheckStatus {
    PASS,
    FAIL,
    PENDING
};

struct StatusCheck {
    std::string name;
    CheckStatus status;
};

struct PullRequestRecord {
    int id;
    std::string title;
    std::vector<std::string> labels;
    std::vector<std::string> changedFiles;
    std::vector<StatusCheck> checks;
};

class ArrayEngine {
public:
    static void validate(const std::vector<std::string>& values) {
        for (const auto& value : values) {
            if (value.empty()) {
                throw std::invalid_argument(
                    "array cannot contain an empty string"
                );
            }
        }
    }

    static std::vector<std::string> unique(
        const std::vector<std::string>& values
    ) {
        validate(values);

        std::unordered_set<std::string> seen;
        std::vector<std::string> result;

        result.reserve(values.size());

        for (const auto& value : values) {
            if (seen.insert(value).second) {
                result.push_back(value);
            }
        }

        return result;
    }

    static std::vector<std::string> difference(
        const std::vector<std::string>& left,
        const std::vector<std::string>& right
    ) {
        std::unordered_set<std::string> rightSet(right.begin(), right.end());
        std::vector<std::string> result;

        for (const auto& value : left) {
            if (!rightSet.contains(value)) {
                result.push_back(value);
            }
        }

        return result;
    }

    static std::vector<std::string> intersection(
        const std::vector<std::string>& left,
        const std::vector<std::string>& right
    ) {
        std::unordered_set<std::string> rightSet(right.begin(), right.end());
        std::unordered_set<std::string> emitted;
        std::vector<std::string> result;

        for (const auto& value : left) {
            if (rightSet.contains(value) && emitted.insert(value).second) {
                result.push_back(value);
            }
        }

        return result;
    }

    static bool containsAll(
        const std::vector<std::string>& values,
        const std::vector<std::string>& required
    ) {
        std::unordered_set<std::string> available(values.begin(), values.end());

        return std::all_of(
            required.begin(),
            required.end(),
            [&](const std::string& value) {
                return available.contains(value);
            }
        );
    }

    static std::vector<std::pair<std::size_t, std::string>> unnest(
        const std::vector<std::string>& values
    ) {
        std::vector<std::pair<std::size_t, std::string>> result;

        for (std::size_t i = 0; i < values.size(); ++i) {
            // PostgreSQL arrays are commonly addressed using 1-based indexes.
            result.emplace_back(i + 1, values[i]);
        }

        return result;
    }

    static std::vector<std::string> slice(
        const std::vector<std::string>& values,
        std::size_t start,
        std::size_t end
    ) {
        if (start == 0 || end < start || end > values.size()) {
            throw std::out_of_range("invalid 1-based array slice");
        }

        return {
            values.begin() + static_cast<std::ptrdiff_t>(start - 1),
            values.begin() + static_cast<std::ptrdiff_t>(end)
        };
    }
};

class MergeEligibilityEngine {
public:
    static bool requiredChecksPass(
        const std::vector<StatusCheck>& checks
    ) {
        return std::all_of(
            checks.begin(),
            checks.end(),
            [](const StatusCheck& check) {
                return check.status == CheckStatus::PASS;
            }
        );
    }

    static bool evaluate(const PullRequestRecord& pullRequest) {
        if (pullRequest.id <= 0 || pullRequest.title.empty()) {
            return false;
        }

        if (!requiredChecksPass(pullRequest.checks)) {
            return false;
        }

        const auto labels = ArrayEngine::unique(pullRequest.labels);

        // Governance rule represented as an array membership decision.
        return ArrayEngine::containsAll(labels, {"reviewed", "approved"});
    }
};

void printArray(
    const std::string& name,
    const std::vector<std::string>& values
) {
    std::cout << name << ": [";

    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i > 0) {
            std::cout << ", ";
        }
        std::cout << values[i];
    }

    std::cout << "]\n";
}

int main() {
    try {
        std::vector<std::string> labels{
            "database",
            "postgresql",
            "reviewed",
            "database",
            "approved"
        };

        std::vector<std::string> protectedLabels{
            "reviewed",
            "approved",
            "security"
        };

        auto uniqueLabels = ArrayEngine::unique(labels);
        auto commonLabels = ArrayEngine::intersection(
            labels,
            protectedLabels
        );
        auto missingLabels = ArrayEngine::difference(
            protectedLabels,
            labels
        );

        printArray("Unique labels", uniqueLabels);
        printArray("Intersection", commonLabels);
        printArray("Missing labels", missingLabels);

        std::cout
            << "Contains review requirements: "
            << std::boolalpha
            << ArrayEngine::containsAll(
                labels,
                {"reviewed", "approved"}
            )
            << '\n';

        std::cout << "Unnested positions:\n";
        for (const auto& [position, value] :
             ArrayEngine::unnest(labels)) {
            std::cout << "  " << position << " -> " << value << '\n';
        }

        auto selected = ArrayEngine::slice(labels, 2, 4);
        printArray("Slice 2..4", selected);

        PullRequestRecord pullRequest{
            1001,
            "Add array-based deployment metadata",
            labels,
            {
                "src/deployment.cpp",
                "tests/deployment_test.cpp"
            },
            {
                {"compile", CheckStatus::PASS},
                {"unit-tests", CheckStatus::PASS},
                {"security-scan", CheckStatus::PASS}
            }
        };

        std::cout
            << "Merge eligible: "
            << std::boolalpha
            << MergeEligibilityEngine::evaluate(pullRequest)
            << '\n';

        pullRequest.checks[1].status = CheckStatus::FAIL;

        std::cout
            << "Merge eligible after failed check: "
            << std::boolalpha
            << MergeEligibilityEngine::evaluate(pullRequest)
            << '\n';

        std::vector<std::vector<int>> matrix{
            {1, 2},
            {3, 4},
            {5, 6}
        };

        std::vector<int> flattened;
        for (const auto& row : matrix) {
            flattened.insert(flattened.end(), row.begin(), row.end());
        }

        std::cout << "Flattened numeric array: ";
        for (const auto value : flattened) {
            std::cout << value << ' ';
        }
        std::cout << '\n';

        // Most set-based membership checks are O(n) to construct the set,
        // followed by average O(1) lookups. Copies and slices are O(n).
    }
    catch (const std::exception& error) {
        std::cerr << "Operation failed: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
