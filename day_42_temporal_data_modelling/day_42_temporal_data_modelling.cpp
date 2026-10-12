#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

using namespace std;
using namespace std::chrono;

using Instant = system_clock::time_point;
using Seconds = chrono::seconds;

Instant utc(int year, unsigned month, unsigned day, int hour = 0, int minute = 0) {
    using namespace chrono;
    const year_month_day date{chrono::year{year}, chrono::month{month}, chrono::day{day}};
    if (!date.ok() || hour < 0 || hour > 23 || minute < 0 || minute > 59) {
        throw invalid_argument("Invalid calendar date or time.");
    }
    return sys_days{date} + hours{hour} + minutes{minute};
}

string formatInstant(Instant value) {
    const time_t raw = system_clock::to_time_t(value);
    tm utcTime{};
#ifdef _WIN32
    gmtime_s(&utcTime, &raw);
#else
    gmtime_r(&raw, &utcTime);
#endif
    ostringstream output;
    output << put_time(&utcTime, "%Y-%m-%dT%H:%M:%SZ");
    return output.str();
}

struct Change {
    string file;
    string summary;
    int additions;
    int deletions;
};

struct Review {
    string reviewer;
    string state;
    bool dismissed = false;
    Instant submittedAt{};
    string commitId;
};

struct StatusCheck {
    string name;
    string commitId;
    bool required;
    string conclusion;
};

enum class PullRequestState {
    Draft,
    Open,
    Merged,
    Closed
};

string stateName(PullRequestState state) {
    switch (state) {
        case PullRequestState::Draft: return "draft";
        case PullRequestState::Open: return "open";
        case PullRequestState::Merged: return "merged";
        case PullRequestState::Closed: return "closed";
    }
    throw logic_error("Unknown Pull Request state.");
}

struct ProtectionPolicy {
    string targetBranch;
    int requiredApprovals = 1;
    bool requireAllConversationsResolved = true;
    bool requireLinearHistory = true;
    bool allowForcePush = false;
    bool allowDeletion = false;
    bool allowDirectPush = false;
    bool dismissStaleApprovals = true;
    bool requireCodeOwnerReview = false;
    set<string> requiredChecks;
    set<string> restrictedMergeStrategies{"merge-commit"};
    set<string> bypassActors;
};

struct PullRequest {
    string id;
    string author;
    string sourceBranch;
    string targetBranch;
    string baseCommit;
    string headCommit;
    PullRequestState state = PullRequestState::Open;
    bool baseSynchronized = true;
    bool hasMergeConflict = false;
    bool conversationsResolved = true;
    bool codeOwnerApproved = false;
    vector<Change> changes;
    vector<Review> reviews;
    vector<StatusCheck> checks;
};

struct Eligibility {
    bool allowed = false;
    vector<string> blockers;
};

class RepositoryGovernance {
    ProtectionPolicy policy_;
    set<string> eligibleReviewers_;
    set<string> codeOwners_;
    map<string, PullRequest> requests_;
    set<string> knownCommits_;

    int validApprovalCount(const PullRequest& pr) const {
        set<string> reviewers;
        for (const Review& review : pr.reviews) {
            if (eligibleReviewers_.contains(review.reviewer)
                && review.reviewer != pr.author
                && review.state == "approved"
                && !review.dismissed
                && review.commitId == pr.headCommit) {
                reviewers.insert(review.reviewer);
            }
        }
        return static_cast<int>(reviewers.size());
    }

    bool changedCodeOwnedFile(const PullRequest& pr) const {
        return any_of(pr.changes.begin(), pr.changes.end(), [&](const Change& change) {
            return codeOwners_.contains(change.file);
        });
    }

public:
    RepositoryGovernance(
        ProtectionPolicy policy,
        set<string> eligibleReviewers,
        set<string> codeOwners
    ) : policy_(move(policy)),
        eligibleReviewers_(move(eligibleReviewers)),
        codeOwners_(move(codeOwners)) {}

    void registerCommit(const string& commit) {
        if (commit.empty()) throw invalid_argument("Commit identifier cannot be empty.");
        knownCommits_.insert(commit);
    }

    void addPullRequest(PullRequest pr) {
        if (pr.id.empty() || pr.author.empty() || pr.sourceBranch.empty()
            || pr.targetBranch.empty() || pr.headCommit.empty()
            || pr.baseCommit.empty()) {
            throw invalid_argument("Pull Request metadata is incomplete.");
        }
        if (pr.sourceBranch == pr.targetBranch) {
            throw invalid_argument("Source and target branches must differ.");
        }
        if (!knownCommits_.contains(pr.headCommit)
            || !knownCommits_.contains(pr.baseCommit)) {
            throw invalid_argument("Pull Request references an unknown commit.");
        }
        if (pr.targetBranch != policy_.targetBranch) {
            throw invalid_argument("Target branch does not match the governance policy.");
        }
        if (!requests_.emplace(pr.id, move(pr)).second) {
            throw invalid_argument("Duplicate Pull Request identifier.");
        }
    }

    PullRequest& request(const string& id) {
        auto found = requests_.find(id);
        if (found == requests_.end()) throw out_of_range("Pull Request not found.");
        return found->second;
    }

    void requestReview(const string& id, const string& reviewer) {
        PullRequest& pr = request(id);
        if (pr.state != PullRequestState::Open) {
            throw logic_error("Reviews can only be requested on an open Pull Request.");
        }
        if (!eligibleReviewers_.contains(reviewer) || reviewer == pr.author) {
            throw invalid_argument("Reviewer is not eligible or is the author.");
        }
        const bool alreadyRequested = any_of(
            pr.reviews.begin(), pr.reviews.end(),
            [&](const Review& review) { return review.reviewer == reviewer; }
        );
        if (!alreadyRequested) {
            pr.reviews.push_back(Review{
                reviewer, "pending", false, system_clock::now(), pr.headCommit
            });
        }
    }

    void submitReview(
        const string& id,
        const string& reviewer,
        const string& state,
        const string& commitId
    ) {
        PullRequest& pr = request(id);
        if (pr.state != PullRequestState::Open) {
            throw logic_error("A review cannot be submitted to a non-open request.");
        }
        if (!eligibleReviewers_.contains(reviewer) || reviewer == pr.author) {
            throw invalid_argument("Reviewer is not eligible or is the author.");
        }
        if (state != "approved" && state != "changes_requested" && state != "commented") {
            throw invalid_argument("Unsupported review state.");
        }
        if (commitId != pr.headCommit) {
            throw invalid_argument("Review must reference the current head commit.");
        }
        pr.reviews.push_back(Review{
            reviewer, state, false, system_clock::now(), commitId
        });
    }

    void resolveConversations(const string& id) {
        request(id).conversationsResolved = true;
    }

    void synchronizeBase(const string& id, const string& newBaseCommit, bool conflict) {
        PullRequest& pr = request(id);
        if (pr.state != PullRequestState::Open && pr.state != PullRequestState::Draft) {
            throw logic_error("Only an unmerged Pull Request can be synchronized.");
        }
        if (!knownCommits_.contains(newBaseCommit)) {
            throw invalid_argument("New base commit is unknown.");
        }
        pr.baseCommit = newBaseCommit;
        pr.baseSynchronized = true;
        pr.hasMergeConflict = conflict;
    }

    void pushCommit(const string& id, const string& newHead, bool hasConflict) {
        PullRequest& pr = request(id);
        if (pr.state != PullRequestState::Open && pr.state != PullRequestState::Draft) {
            throw logic_error("Cannot push changes to a completed Pull Request.");
        }
        if (!knownCommits_.contains(newHead)) {
            throw invalid_argument("New head commit is unknown.");
        }
        pr.headCommit = newHead;
        pr.hasMergeConflict = hasConflict;
        // Stale reviews remain in the audit history. Policy evaluation excludes
        // approvals tied to an earlier head commit.
    }

    void setStatusCheck(
        const string& id,
        const string& name,
        const string& commitId,
        const string& conclusion,
        bool required
    ) {
        PullRequest& pr = request(id);
        if (conclusion != "success" && conclusion != "failure"
            && conclusion != "pending" && conclusion != "cancelled") {
            throw invalid_argument("Invalid status-check conclusion.");
        }
        if (!knownCommits_.contains(commitId)) {
            throw invalid_argument("Status check references an unknown commit.");
        }
        pr.checks.push_back(StatusCheck{name, commitId, required, conclusion});
    }

    Eligibility evaluate(const string& id, const string& actor,
                        const string& strategy = "squash") const {
        auto found = requests_.find(id);
        if (found == requests_.end()) throw out_of_range("Pull Request not found.");
        const PullRequest& pr = found->second;
        Eligibility result;

        if (policy_.bypassActors.contains(actor)) {
            result.allowed = true;
            result.blockers.push_back("Governance bypass explicitly used by " + actor);
            return result;
        }

        if (pr.state != PullRequestState::Open) {
            result.blockers.push_back("Pull Request is not open.");
        }
        if (pr.targetBranch != policy_.targetBranch) {
            result.blockers.push_back("Target branch is not governed by this policy.");
        }
        if (pr.sourceBranch == pr.targetBranch) {
            result.blockers.push_back("Source and target branches are identical.");
        }
        if (!pr.baseSynchronized) {
            result.blockers.push_back("Source branch has not been synchronized with base.");
        }
        if (pr.hasMergeConflict) {
            result.blockers.push_back("Merge conflicts remain.");
        }
        if (policy_.requireAllConversationsResolved && !pr.conversationsResolved) {
            result.blockers.push_back("Review conversations remain unresolved.");
        }
        if (policy_.requireCodeOwnerReview && changedCodeOwnedFile(pr)
            && !pr.codeOwnerApproved) {
            result.blockers.push_back("Code-owner review is missing.");
        }
        if (validApprovalCount(pr) < policy_.requiredApprovals) {
            result.blockers.push_back("Insufficient current, eligible approvals.");
        }

        for (const string& required : policy_.requiredChecks) {
            bool succeeded = any_of(pr.checks.begin(), pr.checks.end(),
                [&](const StatusCheck& check) {
                    return check.name == required
                        && check.commitId == pr.headCommit
                        && check.conclusion == "success";
                });
            if (!succeeded) {
                result.blockers.push_back("Required check has not succeeded on head: " + required);
            }
        }

        if (policy_.restrictedMergeStrategies.contains(strategy)) {
            result.blockers.push_back("Merge strategy is prohibited: " + strategy);
        }
        if (policy_.requireLinearHistory && strategy == "merge-commit") {
            result.blockers.push_back("Linear history policy rejects merge commits.");
        }

        result.allowed = result.blockers.empty();
        return result;
    }

    void merge(const string& id, const string& actor, const string& strategy) {
        PullRequest& pr = request(id);
        const Eligibility eligibility = evaluate(id, actor, strategy);
        if (!eligibility.allowed) {
            ostringstream message;
            message << "Merge rejected:";
            for (const string& blocker : eligibility.blockers) message << "\n - " << blocker;
            throw logic_error(message.str());
        }
        pr.state = PullRequestState::Merged;
    }

    void close(const string& id) {
        PullRequest& pr = request(id);
        if (pr.state == PullRequestState::Merged) {
            throw logic_error("A merged Pull Request cannot be closed as unmerged.");
        }
        pr.state = PullRequestState::Closed;
    }

    void reopen(const string& id) {
        PullRequest& pr = request(id);
        if (pr.state != PullRequestState::Closed) {
            throw logic_error("Only a closed, unmerged Pull Request can be reopened.");
        }
        pr.state = PullRequestState::Open;
    }
};

int main() {
    try {
        ProtectionPolicy policy;
        policy.targetBranch = "main";
        policy.requiredApprovals = 2;
        policy.requireAllConversationsResolved = true;
        policy.requireLinearHistory = true;
        policy.dismissStaleApprovals = true;
        policy.requireCodeOwnerReview = true;
        policy.requiredChecks = {"unit-tests", "security-scan"};
        policy.restrictedMergeStrategies = {"merge-commit"};
        policy.bypassActors = {"emergency-release-manager"};

        RepositoryGovernance governance(
            policy,
            {"reviewer-asha", "reviewer-kabir", "reviewer-meera"},
            {"src/authentication.cpp"}
        );

        for (const string& commit : {"base-100", "feature-200", "feature-201"}) {
            governance.registerCommit(commit);
        }

        PullRequest pr;
        pr.id = "PR-482";
        pr.author = "developer-ravi";
        pr.sourceBranch = "feature/secure-token-refresh";
        pr.targetBranch = "main";
        pr.baseCommit = "base-100";
        pr.headCommit = "feature-200";
        pr.baseSynchronized = true;
        pr.hasMergeConflict = false;
        pr.conversationsResolved = false;
        pr.changes = {
            {"src/authentication.cpp", "Refresh token validation", 84, 19},
            {"tests/authentication_test.cpp", "Cover token expiry cases", 55, 4}
        };

        governance.addPullRequest(pr);
        governance.requestReview("PR-482", "reviewer-asha");
        governance.requestReview("PR-482", "reviewer-kabir");
        governance.submitReview("PR-482", "reviewer-asha", "approved", "feature-200");
        governance.submitReview("PR-482", "reviewer-kabir", "approved", "feature-200");

        governance.setStatusCheck(
            "PR-482", "unit-tests", "feature-200", "success", true
        );
        governance.setStatusCheck(
            "PR-482", "security-scan", "feature-200", "success", true
        );

        auto printEligibility = [&](const string& stage) {
            Eligibility result = governance.evaluate("PR-482", "release-bot", "squash");
            cout << "\n" << stage << "\n";
            cout << "Merge eligible: " << boolalpha << result.allowed << "\n";
            for (const string& blocker : result.blockers) cout << " - " << blocker << "\n";
        };

        printEligibility("Initial policy evaluation");

        governance.resolveConversations("PR-482");
        governance.request("PR-482").codeOwnerApproved = true;
        printEligibility("After resolving discussions and recording code-owner approval");

        governance.registerCommit("feature-202");
        governance.pushCommit("PR-482", "feature-202", false);
        printEligibility("After a new commit makes prior approvals and checks stale");

        governance.submitReview(
            "PR-482", "reviewer-meera", "approved", "feature-202"
        );
        governance.submitReview(
            "PR-482", "reviewer-asha", "approved", "feature-202"
        );
        governance.setStatusCheck(
            "PR-482", "unit-tests", "feature-202", "success", true
        );
        governance.setStatusCheck(
            "PR-482", "security-scan", "feature-202", "success", true
        );

        printEligibility("After current-head approvals and checks are recorded");
        governance.merge("PR-482", "release-bot", "squash");
        cout << "Final Pull Request state: "
             << stateName(governance.request("PR-482").state) << "\n";

        // The bypass is explicit and audited by the eligibility result.
        auto bypass = governance.evaluate(
            "PR-482", "emergency-release-manager", "merge-commit"
        );
        cout << "Explicit bypass accepted: " << bypass.allowed << "\n";

    } catch (const exception& error) {
        cerr << "Governance engine error: " << error.what() << "\n";
        return 1;
    }
    return 0;
}
