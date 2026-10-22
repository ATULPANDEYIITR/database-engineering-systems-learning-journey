#include <algorithm>
#include <cmath>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

enum class PullRequestState {
    Open,
    Merged,
    Closed
};

enum class ReviewState {
    Commented,
    ChangesRequested,
    Approved,
    Dismissed
};

struct Review {
    std::string reviewer;
    ReviewState state;
    std::string comment;
};

struct StatusCheck {
    std::string name;
    bool passed;
};

struct BranchProtection {
    std::string branchName;
    int requiredApprovals;
    bool requireSuccessfulChecks;
    bool requireResolvedConversations;
    bool allowDirectPush;
    bool allowForcePush;
    bool allowDeletion;
    bool requireLinearHistory;
};

struct PullRequest {
    int number;
    std::string title;
    std::string sourceBranch;
    std::string targetBranch;
    PullRequestState state{PullRequestState::Open};
    int changedFiles{0};
    int additions{0};
    int deletions{0};
    int unresolvedConversations{0};
    std::vector<Review> reviews;
    std::vector<StatusCheck> statusChecks;
};

struct EligibilityResult {
    bool eligible;
    std::vector<std::string> reasons;
};

class GovernanceError : public std::runtime_error {
public:
    explicit GovernanceError(const std::string& message)
        : std::runtime_error(message) {}
};

class RepositoryGovernance {
private:
    std::map<std::string, BranchProtection> protectedBranches_;

    static std::string stateName(PullRequestState state) {
        switch (state) {
            case PullRequestState::Open:
                return "OPEN";
            case PullRequestState::Merged:
                return "MERGED";
            case PullRequestState::Closed:
                return "CLOSED";
        }
        return "UNKNOWN";
    }

    static int approvalCount(const PullRequest& pr) {
        int approvals = 0;

        for (const auto& review : pr.reviews) {
            if (review.state == ReviewState::Approved) {
                ++approvals;
            }
        }

        return approvals;
    }

    static bool allChecksPassed(const PullRequest& pr) {
        if (pr.statusChecks.empty()) {
            return false;
        }

        for (const auto& check : pr.statusChecks) {
            if (!check.passed) {
                return false;
            }
        }

        return true;
    }

public:
    void protectBranch(const BranchProtection& policy) {
        if (policy.branchName.empty()) {
            throw GovernanceError("Protected branch name cannot be empty");
        }

        if (policy.requiredApprovals < 0) {
            throw GovernanceError("Required approvals cannot be negative");
        }

        protectedBranches_[policy.branchName] = policy;
    }

    EligibilityResult evaluate(const PullRequest& pr) const {
        EligibilityResult result{true, {}};

        auto policyIt = protectedBranches_.find(pr.targetBranch);

        if (policyIt == protectedBranches_.end()) {
            result.reasons.push_back(
                "target branch has no protection policy"
            );
            result.eligible = false;
            return result;
        }

        const BranchProtection& policy = policyIt->second;

        if (pr.state != PullRequestState::Open) {
            result.reasons.push_back("Pull Request is not open");
        }

        if (pr.sourceBranch.empty() || pr.targetBranch.empty()) {
            result.reasons.push_back("branch names cannot be empty");
        }

        if (pr.sourceBranch == pr.targetBranch) {
            result.reasons.push_back(
                "source and target branches must differ"
            );
        }

        if (pr.changedFiles <= 0) {
            result.reasons.push_back("Pull Request contains no changes");
        }

        const int approvals = approvalCount(pr);

        if (approvals < policy.requiredApprovals) {
            std::ostringstream message;
            message << "requires " << policy.requiredApprovals
                    << " approvals but has " << approvals;
            result.reasons.push_back(message.str());
        }

        if (policy.requireSuccessfulChecks && !allChecksPassed(pr)) {
            result.reasons.push_back(
                "one or more required status checks have failed"
            );
        }

        if (policy.requireResolvedConversations &&
            pr.unresolvedConversations > 0) {
            std::ostringstream message;
            message << pr.unresolvedConversations
                    << " review conversations remain unresolved";
            result.reasons.push_back(message.str());
        }

        result.eligible = result.reasons.empty();
        return result;
    }

    void merge(PullRequest& pr) const {
        const EligibilityResult result = evaluate(pr);

        if (!result.eligible) {
            std::ostringstream message;
            message << "PR #" << pr.number << " cannot be merged:";

            for (const auto& reason : result.reasons) {
                message << "\n - " << reason;
            }

            throw GovernanceError(message.str());
        }

        pr.state = PullRequestState::Merged;
    }
};

static std::string riskLevel(const PullRequest& pr) {
    int score = 0;

    if (pr.changedFiles > 20) {
        score += 2;
    } else if (pr.changedFiles > 10) {
        score += 1;
    }

    const int lineDelta = std::abs(pr.additions - pr.deletions);

    if (lineDelta > 500) {
        score += 2;
    } else if (lineDelta > 200) {
        score += 1;
    }

    if (pr.reviews.empty()) {
        score += 2;
    }

    if (score >= 4) {
        return "HIGH";
    }

    if (score >= 2) {
        return "MEDIUM";
    }

    return "LOW";
}

static PullRequest makePullRequest(
    int number,
    const std::string& title,
    const std::string& source,
    int changedFiles,
    int additions,
    int deletions,
    std::vector<Review> reviews,
    std::vector<StatusCheck> checks,
    int unresolvedConversations
) {
    PullRequest pr;
    pr.number = number;
    pr.title = title;
    pr.sourceBranch = source;
    pr.targetBranch = "main";
    pr.changedFiles = changedFiles;
    pr.additions = additions;
    pr.deletions = deletions;
    pr.reviews = std::move(reviews);
    pr.statusChecks = std::move(checks);
    pr.unresolvedConversations = unresolvedConversations;
    return pr;
}

int main() {
    try {
        RepositoryGovernance governance;

        governance.protectBranch({
            "main",
            2,
            true,
            true,
            false,
            false,
            false,
            true
        });

        std::vector<PullRequest> pullRequests;

        pullRequests.push_back(makePullRequest(
            301,
            "Introduce repository governance rules",
            "feature/governance",
            6,
            170,
            30,
            {
                {"alice", ReviewState::Approved,
                 "Policy implementation is clear"},
                {"bob", ReviewState::Approved,
                 "Constraints are appropriate"},
                {"carol", ReviewState::Commented,
                 "Minor documentation suggestion"}
            },
            {
                {"unit-tests", true},
                {"lint", true},
                {"security-scan", true}
            },
            0
        ));

        pullRequests.push_back(makePullRequest(
            302,
            "Refactor merge workflow",
            "feature/merge-workflow",
            18,
            430,
            70,
            {
                {"alice", ReviewState::Approved,
                 "Architecture is acceptable"}
            },
            {
                {"unit-tests", true},
                {"lint", false},
                {"security-scan", true}
            },
            1
        ));

        for (auto& pr : pullRequests) {
            std::cout << "\nPR #" << pr.number << ": "
                      << pr.title << "\n";
            std::cout << "State: "
                      << (pr.state == PullRequestState::Open
                              ? "OPEN"
                              : pr.state == PullRequestState::Merged
                                    ? "MERGED"
                                    : "CLOSED")
                      << "\n";
            std::cout << "Risk: " << riskLevel(pr) << "\n";

            const EligibilityResult result = governance.evaluate(pr);

            std::cout << "Merge eligible: "
                      << (result.eligible ? "YES" : "NO") << "\n";

            if (!result.eligible) {
                std::cout << "Blocking conditions:\n";

                for (const auto& reason : result.reasons) {
                    std::cout << "  - " << reason << "\n";
                }
            }

            try {
                governance.merge(pr);
                std::cout << "Merge operation: SUCCESS\n";
            } catch (const GovernanceError& error) {
                std::cout << "Merge operation: REJECTED\n";
                std::cout << error.what() << "\n";
            }
        }

        std::cout << "\nGovernance engine completed.\n";
    } catch (const std::exception& error) {
        std::cerr << "Fatal governance error: "
                  << error.what() << '\n';
        return 1;
    }

    return 0;
}
