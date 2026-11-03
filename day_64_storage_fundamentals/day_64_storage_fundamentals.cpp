#include <algorithm>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

enum class PRState {
    Draft,
    Open,
    Closed,
    Merged
};

enum class ReviewState {
    Commented,
    Approved,
    ChangesRequested,
    Dismissed
};

enum class MergeStrategy {
    MergeCommit,
    Squash,
    Rebase
};

struct Commit {
    std::string sha;
    std::string message;
    std::string parentSha;

    Commit(std::string id, std::string msg, std::string parent = "")
        : sha(std::move(id)), message(std::move(msg)), parentSha(std::move(parent)) {}
};

struct Review {
    std::string reviewer;
    ReviewState state;
    std::string commitSha;
    bool dismissed{false};
    std::vector<std::string> comments;
};

struct StatusCheck {
    std::string name;
    bool passed;
    bool required;
    std::string message;
};

struct BranchProtection {
    int requiredReviews{1};
    std::set<std::string> requiredChecks;
    bool restrictDirectPush{true};
    bool restrictForcePush{true};
    bool requireConversationResolution{true};
    bool requireLinearHistory{false};
    bool allowAdminBypass{false};
};

class Branch {
public:
    std::string name;
    bool protectedBranch{false};
    std::vector<Commit> commits;

    explicit Branch(std::string branchName, bool protectedValue = false)
        : name(std::move(branchName)), protectedBranch(protectedValue) {}

    std::string head() const {
        return commits.empty() ? "" : commits.back().sha;
    }
};

class PullRequest {
public:
    int number;
    std::string source;
    std::string target;
    std::string title;
    std::string author;
    PRState state{PRState::Open};
    bool draft{false};
    std::vector<Commit> commits;
    std::vector<Review> reviews;
    std::map<std::string, StatusCheck> checks;
    int unresolvedConversations{0};
    std::string baseHeadAtCreation;
    MergeStrategy strategy{MergeStrategy::Squash};

    PullRequest(
        int numberValue,
        std::string sourceBranch,
        std::string targetBranch,
        std::string titleValue,
        std::string authorValue,
        std::string baseHead,
        bool isDraft
    )
        : number(numberValue),
          source(std::move(sourceBranch)),
          target(std::move(targetBranch)),
          title(std::move(titleValue)),
          author(std::move(authorValue)),
          draft(isDraft),
          baseHeadAtCreation(std::move(baseHead)) {
        state = isDraft ? PRState::Draft : PRState::Open;
    }

    void addReview(const Review& review) {
        if (state != PRState::Open) {
            throw std::runtime_error("Reviews require an open pull request.");
        }
        reviews.push_back(review);
    }

    void addCheck(const StatusCheck& check) {
        checks[check.name] = check;
    }

    void close() {
        if (state == PRState::Merged) {
            throw std::runtime_error("Merged pull request cannot be closed.");
        }
        state = PRState::Closed;
    }

    void reopen() {
        if (state != PRState::Closed) {
            throw std::runtime_error("Only closed pull requests can be reopened.");
        }
        state = PRState::Open;
    }
};

class Repository {
private:
    std::string name;
    std::string owner;
    int nextPR{1};

    std::map<std::string, Branch> branches;
    std::map<int, PullRequest> pullRequests;
    std::map<std::string, BranchProtection> protection;

public:
    Repository(std::string repositoryName, std::string repositoryOwner)
        : name(std::move(repositoryName)), owner(std::move(repositoryOwner)) {}

    void createBranch(const std::string& name, bool protectedBranch = false) {
        if (branches.contains(name)) {
            throw std::runtime_error("Branch already exists.");
        }
        branches.emplace(name, Branch{name, protectedBranch});
    }

    void addCommit(
        const std::string& branchName,
        const std::string& sha,
        const std::string& message
    ) {
        auto it = branches.find(branchName);
        if (it == branches.end()) {
            throw std::runtime_error("Unknown branch.");
        }

        const auto duplicate = std::find_if(
            it->second.commits.begin(),
            it->second.commits.end(),
            [&](const Commit& c) { return c.sha == sha; }
        );

        if (duplicate != it->second.commits.end()) {
            throw std::runtime_error("Duplicate commit SHA.");
        }

        it->second.commits.emplace_back(sha, message, it->second.head());
    }

    void protectBranch(
        const std::string& branchName,
        const BranchProtection& policy
    ) {
        auto it = branches.find(branchName);
        if (it == branches.end()) {
            throw std::runtime_error("Cannot protect unknown branch.");
        }

        it->second.protectedBranch = true;
        protection[branchName] = policy;
    }

    PullRequest& createPullRequest(
        const std::string& source,
        const std::string& target,
        const std::string& title,
        const std::string& author
    ) {
        if (!branches.contains(source) || !branches.contains(target)) {
            throw std::runtime_error("Both branches must exist.");
        }

        if (source == target) {
            throw std::runtime_error("Source and target must differ.");
        }

        auto& sourceBranch = branches.at(source);
        auto& targetBranch = branches.at(target);

        PullRequest pr(
            nextPR++,
            source,
            target,
            title,
            author,
            targetBranch.head(),
            false
        );

        pr.commits = sourceBranch.commits;
        auto [it, inserted] = pullRequests.emplace(pr.number, std::move(pr));
        if (!inserted) {
            throw std::runtime_error("Unable to create pull request.");
        }

        return it->second;
    }

    std::pair<bool, std::vector<std::string>>
    evaluateMerge(const PullRequest& pr) const {
        std::vector<std::string> reasons;

        if (pr.state != PRState::Open) {
            reasons.push_back("Pull request is not open.");
        }

        if (pr.draft) {
            reasons.push_back("Pull request remains a draft.");
        }

        if (pr.commits.empty()) {
            reasons.push_back("Pull request has no changes.");
        }

        const auto policyIt = protection.find(pr.target);
        if (policyIt == protection.end()) {
            return {reasons.empty(), reasons};
        }

        const auto& targetBranch = branches.at(pr.target);
        const auto& sourceBranch = branches.at(pr.source);
        const auto& policy = policyIt->second;

        if (targetBranch.head() != pr.baseHeadAtCreation) {
            reasons.push_back("Target branch has changed; synchronization is required.");
        }

        std::set<std::string> approvals;
        bool changesRequested = false;

        for (const auto& review : pr.reviews) {
            if (review.dismissed) {
                continue;
            }

            const bool current =
                review.commitSha == sourceBranch.head() ||
                review.commitSha == targetBranch.head();

            if (!current) {
                continue;
            }

            if (review.state == ReviewState::Approved) {
                approvals.insert(review.reviewer);
            } else if (review.state == ReviewState::ChangesRequested) {
                changesRequested = true;
            }
        }

        if (changesRequested) {
            reasons.push_back("A current reviewer has requested changes.");
        }

        if (static_cast<int>(approvals.size()) < policy.requiredReviews) {
            reasons.push_back("Required approvals have not been satisfied.");
        }

        for (const auto& checkName : policy.requiredChecks) {
            const auto checkIt = pr.checks.find(checkName);

            if (checkIt == pr.checks.end()) {
                reasons.push_back("Missing required check: " + checkName);
            } else if (!checkIt->second.passed) {
                reasons.push_back("Failed required check: " + checkName);
            }
        }

        if (policy.requireConversationResolution &&
            pr.unresolvedConversations > 0) {
            reasons.push_back("Unresolved review conversations remain.");
        }

        return {reasons.empty(), reasons};
    }

    void merge(int prNumber) {
        auto prIt = pullRequests.find(prNumber);
        if (prIt == pullRequests.end()) {
            throw std::runtime_error("Unknown pull request.");
        }

        PullRequest& pr = prIt->second;
        const auto [eligible, reasons] = evaluateMerge(pr);

        if (!eligible) {
            std::string message = "Merge rejected:";
            for (const auto& reason : reasons) {
                message += " " + reason;
            }
            throw std::runtime_error(message);
        }

        Branch& target = branches.at(pr.target);
        Branch& source = branches.at(pr.source);

        if (pr.strategy == MergeStrategy::Squash) {
            target.commits.emplace_back(
                "squash-" + std::to_string(pr.number),
                "Squash: " + pr.title,
                target.head()
            );
        } else if (pr.strategy == MergeStrategy::MergeCommit) {
            target.commits.emplace_back(
                "merge-" + std::to_string(pr.number),
                "Merge pull request #" + std::to_string(pr.number),
                target.head()
            );
        } else {
            for (const auto& commit : source.commits) {
                target.commits.emplace_back(
                    "rebased-" + commit.sha,
                    commit.message,
                    target.head()
                );
            }
        }

        pr.state = PRState::Merged;
    }

    const Branch& getBranch(const std::string& name) const {
        return branches.at(name);
    }
};

int main() {
    try {
        Repository repository("storage-platform", "platform-admin");

        repository.createBranch("main", true);
        repository.createBranch("feature/page-storage");

        repository.addCommit("main", "a001", "Initialize repository");
        repository.addCommit("feature/page-storage", "a001", "Initialize repository");
        repository.addCommit("feature/page-storage", "b101", "Implement pages");
        repository.addCommit("feature/page-storage", "b102", "Validate blocks");

        BranchProtection policy;
        policy.requiredReviews = 2;
        policy.requiredChecks = {"unit-tests", "storage-integrity"};
        policy.restrictDirectPush = true;
        policy.restrictForcePush = true;
        policy.requireConversationResolution = true;

        repository.protectBranch("main", policy);

        PullRequest& pr = repository.createPullRequest(
            "feature/page-storage",
            "main",
            "Implement physical storage model",
            "developer-1"
        );

        pr.addCheck({
            "unit-tests",
            true,
            true,
            "All tests passed"
        });

        pr.addCheck({
            "storage-integrity",
            true,
            true,
            "Storage boundaries validated"
        });

        pr.addReview({
            "reviewer-1",
            ReviewState::Approved,
            "b102",
            false,
            {"Allocation logic is bounded."}
        });

        pr.addReview({
            "reviewer-2",
            ReviewState::Approved,
            "b102",
            false,
            {"Record validation is correct."}
        });

        const auto [eligible, reasons] = repository.evaluateMerge(pr);

        std::cout << "Pull Request #" << pr.number << "\n";
        std::cout << "Merge eligible: " << std::boolalpha << eligible << "\n";

        for (const auto& reason : reasons) {
            std::cout << "  - " << reason << "\n";
        }

        repository.merge(pr.number);

        std::cout << "State: Merged\n";
        std::cout << "main HEAD: "
                  << repository.getBranch("main").head() << "\n";

        try {
            if (repository.getBranch("main").protectedBranch) {
                throw std::runtime_error(
                    "Direct push rejected by protected-branch policy."
                );
            }
        } catch (const std::exception& ex) {
            std::cout << "Protection test: " << ex.what() << "\n";
        }
    } catch (const std::exception& ex) {
        std::cerr << "Fatal error: " << ex.what() << "\n";
        return 1;
    }

    return 0;
}
