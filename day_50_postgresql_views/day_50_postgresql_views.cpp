#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using TimePoint = std::chrono::system_clock::time_point;

struct Repository {
    std::string name;
    std::string team;
    bool active;
};

struct PullRequest {
    int number;
    std::string repository;
    std::string author;
    std::string state;
    int additions;
    int deletions;
    std::optional<TimePoint> mergedAt;
};

struct Review {
    int pullRequest;
    std::string reviewer;
    std::string state;
};

struct RepositoryMetrics {
    std::string repository;
    std::string team;
    std::size_t pullRequests{};
    std::size_t mergedPullRequests{};
    long totalChanges{};
    double averageChangeSize{};
};

class GovernanceEngine {
private:
    std::vector<Repository> repositories_;
    std::vector<PullRequest> pullRequests_;
    std::vector<Review> reviews_;

    static void validatePullRequest(const PullRequest& pr) {
        if (pr.number <= 0) {
            throw std::invalid_argument("Pull request number must be positive");
        }

        if (pr.repository.empty() || pr.author.empty()) {
            throw std::invalid_argument(
                "Repository and author are required"
            );
        }

        if (pr.additions < 0 || pr.deletions < 0) {
            throw std::invalid_argument(
                "Change counts cannot be negative"
            );
        }
    }

public:
    void addRepository(Repository repository) {
        if (repository.name.empty()) {
            throw std::invalid_argument("Repository name cannot be empty");
        }

        const auto duplicate = std::find_if(
            repositories_.begin(),
            repositories_.end(),
            [&](const Repository& existing) {
                return existing.name == repository.name;
            }
        );

        if (duplicate != repositories_.end()) {
            throw std::invalid_argument("Duplicate repository");
        }

        repositories_.push_back(std::move(repository));
    }

    void addPullRequest(PullRequest pr) {
        validatePullRequest(pr);

        const bool knownRepository = std::any_of(
            repositories_.begin(),
            repositories_.end(),
            [&](const Repository& repository) {
                return repository.name == pr.repository;
            }
        );

        if (!knownRepository) {
            throw std::invalid_argument("Unknown repository");
        }

        const bool duplicate = std::any_of(
            pullRequests_.begin(),
            pullRequests_.end(),
            [&](const PullRequest& existing) {
                return existing.number == pr.number;
            }
        );

        if (duplicate) {
            throw std::invalid_argument("Duplicate pull request number");
        }

        pullRequests_.push_back(std::move(pr));
    }

    void addReview(Review review) {
        const bool knownPR = std::any_of(
            pullRequests_.begin(),
            pullRequests_.end(),
            [&](const PullRequest& pr) {
                return pr.number == review.pullRequest;
            }
        );

        if (!knownPR) {
            throw std::invalid_argument("Review references unknown pull request");
        }

        if (review.reviewer.empty()) {
            throw std::invalid_argument("Reviewer is required");
        }

        if (review.state != "APPROVED" &&
            review.state != "CHANGES_REQUESTED" &&
            review.state != "COMMENTED") {
            throw std::invalid_argument("Invalid review state");
        }

        reviews_.push_back(std::move(review));
    }

    /*
     * A normal view is represented by a function that scans current base
     * records. No computed result is retained between calls.
     */
    std::vector<RepositoryMetrics> repositoryActivityView() const {
        std::vector<RepositoryMetrics> result;

        for (const auto& repository : repositories_) {
            RepositoryMetrics metrics;
            metrics.repository = repository.name;
            metrics.team = repository.team;

            long total = 0;

            for (const auto& pr : pullRequests_) {
                if (pr.repository != repository.name) {
                    continue;
                }

                ++metrics.pullRequests;
                total += static_cast<long>(pr.additions) + pr.deletions;

                if (pr.mergedAt.has_value()) {
                    ++metrics.mergedPullRequests;
                }
            }

            metrics.totalChanges = total;
            metrics.averageChangeSize =
                metrics.pullRequests == 0
                    ? 0.0
                    : static_cast<double>(total) / metrics.pullRequests;

            result.push_back(metrics);
        }

        return result;
    }

    /*
     * Evaluates review state independently from repository activity. This
     * separation mirrors distinct reporting views in a relational schema.
     */
    std::map<int, std::pair<int, int>> reviewView() const {
        std::map<int, std::pair<int, int>> result;

        for (const auto& review : reviews_) {
            auto& counters = result[review.pullRequest];

            if (review.state == "APPROVED") {
                ++counters.first;
            } else if (review.state == "CHANGES_REQUESTED") {
                ++counters.second;
            }
        }

        return result;
    }
};

class MaterializedRepositoryReport {
private:
    std::vector<RepositoryMetrics> snapshot_;
    TimePoint refreshedAt_{};

public:
    void refresh(const GovernanceEngine& engine) {
        /*
         * Refresh replaces the stored analytical snapshot. This is the key
         * behavioral difference from a normal view.
         */
        snapshot_ = engine.repositoryActivityView();
        refreshedAt_ = std::chrono::system_clock::now();
    }

    const std::vector<RepositoryMetrics>& read() const {
        return snapshot_;
    }

    bool hasBeenRefreshed() const {
        return !snapshot_.empty() ||
               refreshedAt_ != TimePoint{};
    }
};

void printMetrics(
    const std::string& title,
    const std::vector<RepositoryMetrics>& rows
) {
    std::cout << "\n" << title << "\n";
    std::cout << std::string(78, '-') << "\n";

    std::cout
        << std::left
        << std::setw(22) << "Repository"
        << std::setw(15) << "Team"
        << std::setw(10) << "PRs"
        << std::setw(12) << "Merged"
        << std::setw(12) << "Changes"
        << std::setw(10) << "Avg"
        << "\n";

    for (const auto& row : rows) {
        std::cout
            << std::left
            << std::setw(22) << row.repository
            << std::setw(15) << row.team
            << std::setw(10) << row.pullRequests
            << std::setw(12) << row.mergedPullRequests
            << std::setw(12) << row.totalChanges
            << std::fixed << std::setprecision(2)
            << std::setw(10) << row.averageChangeSize
            << "\n";
    }
}

int main() {
    try {
        GovernanceEngine engine;

        engine.addRepository({"payments-api", "platform", true});
        engine.addRepository({"customer-portal", "web", true});
        engine.addRepository({"legacy-reporting", "data", false});

        const auto now = std::chrono::system_clock::now();

        engine.addPullRequest({
            101,
            "payments-api",
            "alice",
            "MERGED",
            180,
            42,
            now
        });

        engine.addPullRequest({
            102,
            "payments-api",
            "bob",
            "OPEN",
            80,
            15,
            std::nullopt
        });

        engine.addPullRequest({
            201,
            "customer-portal",
            "carol",
            "MERGED",
            300,
            90,
            now
        });

        engine.addReview({101, "reviewer-a", "APPROVED"});
        engine.addReview({101, "reviewer-b", "APPROVED"});
        engine.addReview({102, "reviewer-a", "CHANGES_REQUESTED"});
        engine.addReview({201, "reviewer-c", "APPROVED"});

        printMetrics(
            "Dynamic repository activity view",
            engine.repositoryActivityView()
        );

        MaterializedRepositoryReport report;
        report.refresh(engine);

        printMetrics(
            "Materialized repository report",
            report.read()
        );

        /*
         * Source data changes after materialization. The dynamic calculation
         * immediately sees it, while the stored snapshot does not.
         */
        engine.addPullRequest({
            103,
            "payments-api",
            "diana",
            "MERGED",
            45,
            10,
            now
        });

        printMetrics(
            "Dynamic view after source modification",
            engine.repositoryActivityView()
        );

        printMetrics(
            "Materialized report before refresh",
            report.read()
        );

        report.refresh(engine);

        printMetrics(
            "Materialized report after refresh",
            report.read()
        );

        const auto reviewData = engine.reviewView();

        std::cout << "\nReview decision view\n";
        for (const auto& [pr, counts] : reviewData) {
            std::cout
                << "PR #" << pr
                << ": approvals=" << counts.first
                << ", change_requests=" << counts.second
                << "\n";
        }

        std::cout
            << "\nPerformance trade-off: dynamic views avoid refresh work but "
            << "recompute their query; materialized reports trade freshness "
            << "for faster reads of expensive derived data.\n";

        std::cout
            << "Security consideration: expose only columns appropriate for "
            << "the reporting audience and enforce sensitive access at the "
            << "database layer rather than relying on application filtering.\n";

    } catch (const std::exception& error) {
        std::cerr << "Execution failure: " << error.what() << "\n";
        return 1;
    }

    return 0;
}
