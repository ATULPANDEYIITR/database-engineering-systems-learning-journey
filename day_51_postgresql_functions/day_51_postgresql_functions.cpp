#include <algorithm>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

enum class PullRequestState {
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
};

struct Review {
    std::string reviewer;
    ReviewState state;
    std::string commitSha;
};

struct StatusCheck {
    std::string name;
    bool passed;
};

struct BranchProtection {
    std::string branch;
    int requiredReviews{};
    std::set<std::string> requiredChecks;
    bool requireResolvedConversations{true};
    bool allowDirectPush{false};
    bool allowForcePush{false};
    bool requireLinearHistory{false};
};

struct PullRequest {
    int number{};
    std::string sourceBranch;
    std::string targetBranch;
    PullRequestState state{PullRequestState::Open};
    std::vector<Commit> commits;
    std::vector<Review> reviews;
    std::vector<StatusCheck> checks;
    int unresolvedConversations{};
    int baseRevision{};
    std::optional<MergeStrategy> strategy;
};

struct Eligibility {
    bool allowed{};
    std::vector<std::string> reasons;
};

class GovernanceEngine {
private:
    std::map<std::string, BranchProtection> protections_;

    static bool hasCommit(const PullRequest& pr, const std::string& sha) {
        return std::any_of(
            pr.commits.begin(),
            pr.commits.end(),
            [&](const Commit& c) { return c.sha == sha; }
        );
    }

    static bool checkPassed(
        const PullRequest& pr,
        const std::string& checkName
    ) {
        for (const auto& check : pr.checks) {
            if (check.name == checkName) {
                return check.passed;
            }
        }
        return false;
    }

    static std::map<std::string, Review> latestReviews(
        const PullRequest& pr
    ) {
        std::map<std::string, Review> latest;

        for (const auto& review : pr.reviews) {
            latest[review.reviewer] = review;
        }

        return latest;
    }

public:
    void protectBranch(const BranchProtection& protection) {
        if (protection.branch.empty()) {
            throw std::invalid_argument("Protected branch requires a name");
        }

        if (protection.requiredReviews < 0) {
            throw std::invalid_argument("Required review count cannot be negative");
        }

        protections_[protection.branch] = protection;
    }

    Eligibility evaluate(
        const PullRequest& pr,
        const std::set<std::string>& eligibleReviewers
    ) const {
        Eligibility result{true, {}};

        auto protectionIt = protections_.find(pr.targetBranch);

        if (protectionIt == protections_.end()) {
            result.allowed = false;
            result.reasons.push_back("Target branch is not protected");
            return result;
        }

        const auto& protection = protectionIt->second;

        if (pr.state != PullRequestState::Open) {
            result.allowed = false;
            result.reasons.push_back("Pull Request is not open");
        }

        if (pr.commits.empty()) {
            result.allowed = false;
            result.reasons.push_back("Pull Request has no commits");
        }

        if (pr.baseRevision < 0) {
            result.allowed = false;
            result.reasons.push_back("Invalid base revision");
        }

        if (pr.unresolvedConversations > 0 &&
            protection.requireResolvedConversations) {
            result.allowed = false;
            result.reasons.push_back("Unresolved conversations remain");
        }

        for (const auto& requiredCheck : protection.requiredChecks) {
            if (!checkPassed(pr, requiredCheck)) {
                result.allowed = false;
                result.reasons.push_back(
                    "Required status check failed or is missing: " +
                    requiredCheck
                );
            }
        }

        if (pr.commits.empty()) {
            return result;
        }

        const std::string currentCommit = pr.commits.back().sha;
        const auto latest = latestReviews(pr);

        int validApprovals = 0;

        for (const auto& [reviewer, review] : latest) {
            if (
                eligibleReviewers.contains(reviewer) &&
                review.state == ReviewState::Approved &&
                review.commitSha == currentCommit
            ) {
                ++validApprovals;
            }
        }

        if (validApprovals < protection.requiredReviews) {
            result.allowed = false;
            result.reasons.push_back(
                "Current eligible approvals: " +
                std::to_string(validApprovals) +
                ", required: " +
                std::to_string(protection.requiredReviews)
            );
        }

        return result;
    }

    void submitReview(
        PullRequest& pr,
        const std::string& reviewer,
        ReviewState state,
        const std::string& commitSha
    ) const {
        if (pr.state != PullRequestState::Open) {
            throw std::runtime_error("Cannot review a non-open Pull Request");
        }

        if (!hasCommit(pr, commitSha)) {
            throw std::runtime_error(
                "Review must reference a commit in the Pull Request"
            );
        }

        if (reviewer.empty()) {
            throw std::runtime_error("Reviewer cannot be empty");
        }

        pr.reviews.push_back({reviewer, state, commitSha});
    }

    void merge(
        PullRequest& pr,
        const std::set<std::string>& eligibleReviewers,
        MergeStrategy strategy
    ) const {
        const auto result = evaluate(pr, eligibleReviewers);

        if (!result.allowed) {
            std::string message = "Merge blocked:";
            for (const auto& reason : result.reasons) {
                message += "\n - " + reason;
            }
            throw std::runtime_error(message);
        }

        const auto& protection = protections_.at(pr.targetBranch);

        if (
            protection.requireLinearHistory &&
            strategy == MergeStrategy::MergeCommit
        ) {
            throw std::runtime_error(
                "Merge-commit strategy violates linear-history protection"
            );
        }

        pr.state = PullRequestState::Merged;
        pr.strategy = strategy;
    }
};

static const char* stateName(PullRequestState state) {
    switch (state) {
        case PullRequestState::Draft: return "draft";
        case PullRequestState::Open: return "open";
        case PullRequestState::Closed: return "closed";
        case PullRequestState::Merged: return "merged";
    }
    return "unknown";
}

int main() {
    try {
        GovernanceEngine engine;

        engine.protectBranch({
            "main",
            2,
            {"build", "security"},
            true,
            false,
            false,
            true
        });

        PullRequest pr{
            81,
            "feature/payment-audit",
            "main",
            PullRequestState::Open,
            {
                {"001abc", "Record payment authorization"},
                {"002def", "Reject invalid merchant state"}
            },
            {},
            {
                {"build", true},
                {"security", true}
            },
            0,
            12,
            std::nullopt
        };

        engine.submitReview(
            pr,
            "reviewer-alice",
            ReviewState::Approved,
            "002def"
        );

        engine.submitReview(
            pr,
            "reviewer-bob",
            ReviewState::Approved,
            "002def"
        );

        const std::set<std::string> eligible{
            "reviewer-alice",
            "reviewer-bob"
        };

        auto eligibility = engine.evaluate(pr, eligible);

        std::cout << "Eligible before update: "
                  << std::boolalpha
                  << eligibility.allowed
                  << '\n';

        // A new commit makes approvals against the old changeset stale.
        pr.commits.push_back({
            "003ghi",
            "Improve audit event validation"
        });

        eligibility = engine.evaluate(pr, eligible);

        std::cout << "Eligible after new commit: "
                  << eligibility.allowed
                  << '\n';

        for (const auto& reason : eligibility.reasons) {
            std::cout << "Reason: " << reason << '\n';
        }

        engine.submitReview(
            pr,
            "reviewer-alice",
            ReviewState::Approved,
            "003ghi"
        );

        engine.submitReview(
            pr,
            "reviewer-bob",
            ReviewState::Approved,
            "003ghi"
        );

        engine.merge(pr, eligible, MergeStrategy::Rebase);

        std::cout << "Final PR state: "
                  << stateName(pr.state)
                  << '\n';

    } catch (const std::exception& ex) {
        std::cerr << "Governance failure: " << ex.what() << '\n';
        return 1;
    }

    return 0;
}
