#include <algorithm>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

/*
 * C++17 repository governance case study.
 *
 * Scenario: a payments service uses a governance engine to determine whether
 * a proposed change may enter its production branch. The engine separates
 * repository data, branch policy, review history, CI evidence, and the
 * decision to merge.
 *
 * This is a policy simulation, not a Git object implementation. Commit IDs
 * are illustrative identifiers. A production host must obtain trustworthy
 * commit ancestry, signature verification, permissions, and check provenance
 * from its Git and CI infrastructure.
 */

enum class PullRequestState { Draft, Open, Closed, Merged };
enum class ReviewDecision { Comment, Approved, ChangesRequested, Dismissed };
enum class CheckState { Pending, Success, Failure, Error };
enum class MergeStrategy { MergeCommit, Squash, Rebase };

std::string toString(PullRequestState state) {
    switch (state) {
        case PullRequestState::Draft: return "draft";
        case PullRequestState::Open: return "open";
        case PullRequestState::Closed: return "closed";
        case PullRequestState::Merged: return "merged";
    }
    throw std::logic_error("Unknown pull request state.");
}

std::string toString(ReviewDecision decision) {
    switch (decision) {
        case ReviewDecision::Comment: return "comment";
        case ReviewDecision::Approved: return "approved";
        case ReviewDecision::ChangesRequested: return "changes requested";
        case ReviewDecision::Dismissed: return "dismissed";
    }
    throw std::logic_error("Unknown review decision.");
}

std::string toString(CheckState state) {
    switch (state) {
        case CheckState::Pending: return "pending";
        case CheckState::Success: return "success";
        case CheckState::Failure: return "failure";
        case CheckState::Error: return "error";
    }
    throw std::logic_error("Unknown check state.");
}

std::string toString(MergeStrategy strategy) {
    switch (strategy) {
        case MergeStrategy::MergeCommit: return "merge commit";
        case MergeStrategy::Squash: return "squash";
        case MergeStrategy::Rebase: return "rebase";
    }
    throw std::logic_error("Unknown merge strategy.");
}

struct Commit {
    std::string sha;
    std::string author;
    std::string message;
    std::vector<std::string> parents;
};

struct Branch {
    std::string name;
    std::string headSha;
    bool deleted = false;
};

struct Reviewer {
    std::string id;
    std::string team;
    bool active = true;
};

struct Review {
    std::string reviewerId;
    std::string commitSha;
    ReviewDecision decision;
    std::time_t submittedAt;
};

struct StatusCheck {
    std::string context;
    std::string commitSha;
    CheckState state;
    std::time_t completedAt;
};

struct ReviewComment {
    std::string id;
    std::string authorId;
    std::string body;
    std::optional<std::string> filePath;
    std::optional<int> line;
    bool resolved = false;
};

struct BranchProtection {
    std::size_t requiredApprovals = 1;
    std::set<std::string> requiredChecks;
    std::set<std::string> eligibleTeams;
    std::set<MergeStrategy> allowedStrategies{MergeStrategy::Squash};
    bool requireResolvedConversations = true;
    bool requireUpToDateBase = true;
    bool requireLinearHistory = false;
    bool dismissStaleApprovals = true;
    bool prohibitDirectPushes = true;
    bool prohibitForcePushes = true;
    bool prohibitDeletion = true;
    bool requireSignedCommits = false;
};

struct PullRequest {
    int number;
    std::string authorId;
    std::string sourceBranch;
    std::string targetBranch;
    std::string title;
    std::string baseSha;
    std::string headSha;
    PullRequestState state;
    bool draft = false;
    std::vector<Review> reviews;
    std::vector<StatusCheck> checks;
    std::vector<ReviewComment> comments;
    std::optional<std::string> mergedSha;
};

class Repository {
public:
    explicit Repository(std::string name, std::string defaultBranch)
        : name_(std::move(name)), defaultBranch_(std::move(defaultBranch)) {
        if (name_.empty() || defaultBranch_.empty()) {
            throw std::invalid_argument("Repository name and default branch are required.");
        }
    }

    void addCommit(Commit commit) {
        if (commit.sha.empty() || commit.author.empty() || commit.message.empty()) {
            throw std::invalid_argument("Commit SHA, author, and message are required.");
        }
        if (commits_.count(commit.sha)) {
            throw std::invalid_argument("Duplicate commit SHA.");
        }
        for (const auto& parent : commit.parents) {
            if (!commits_.count(parent)) {
                throw std::invalid_argument("Commit parent must already exist.");
            }
        }
        commits_.emplace(commit.sha, std::move(commit));
    }

    void addBranch(const std::string& name, const std::string& headSha) {
        if (!commits_.count(headSha)) {
            throw std::invalid_argument("Branch head must reference a known commit.");
        }
        if (!branches_.emplace(name, Branch{name, headSha, false}).second) {
            throw std::invalid_argument("Branch names must be unique.");
        }
    }

    void setProtection(const std::string& branchName, BranchProtection policy) {
        if (!branches_.count(branchName)) {
            throw std::invalid_argument("Cannot protect a nonexistent branch.");
        }
        protections_[branchName] = std::move(policy);
    }

    void addReviewer(Reviewer reviewer) {
        if (reviewer.id.empty() || reviewer.team.empty()) {
            throw std::invalid_argument("Reviewer ID and team are required.");
        }
        if (!reviewers_.emplace(reviewer.id, std::move(reviewer)).second) {
            throw std::invalid_argument("Duplicate reviewer identifier.");
        }
    }

    PullRequest& openPullRequest(
        int number,
        const std::string& authorId,
        const std::string& source,
        const std::string& target,
        const std::string& title,
        bool draft = false
    ) {
        const auto sourceIt = branches_.find(source);
        const auto targetIt = branches_.find(target);
        if (source == target || sourceIt == branches_.end() || targetIt == branches_.end()) {
            throw std::invalid_argument("Pull request requires distinct existing branches.");
        }
        if (sourceIt->second.deleted || targetIt->second.deleted) {
            throw std::invalid_argument("Deleted branches cannot be used.");
        }
        if (number <= 0 || authorId.empty() || title.empty()) {
            throw std::invalid_argument("Invalid pull request identity or title.");
        }
        if (pullRequests_.count(number)) {
            throw std::invalid_argument("Pull request number already exists.");
        }

        PullRequest pr{
            number,
            authorId,
            source,
            target,
            title,
            targetIt->second.headSha,
            sourceIt->second.headSha,
            draft ? PullRequestState::Draft : PullRequestState::Open,
            draft
        };
        return pullRequests_.emplace(number, std::move(pr)).first->second;
    }

    void publish(int number) {
        PullRequest& pr = getPullRequest(number);
        if (pr.state != PullRequestState::Draft) {
            throw std::logic_error("Only draft pull requests can be published.");
        }
        pr.state = PullRequestState::Open;
        pr.draft = false;
    }

    void submitReview(
        int number,
        const std::string& reviewerId,
        const std::string& commitSha,
        ReviewDecision decision
    ) {
        PullRequest& pr = getPullRequest(number);
        if (pr.state != PullRequestState::Open) {
            throw std::logic_error("Reviews require an open pull request.");
        }
        const auto reviewerIt = reviewers_.find(reviewerId);
        if (reviewerIt == reviewers_.end() || !reviewerIt->second.active) {
            throw std::invalid_argument("Reviewer is missing or inactive.");
        }
        if (reviewerId == pr.authorId && decision == ReviewDecision::Approved) {
            throw std::runtime_error("Authors cannot approve their own changes.");
        }
        if (!commits_.count(commitSha)) {
            throw std::invalid_argument("Review commit does not exist.");
        }
        pr.reviews.push_back(
            Review{reviewerId, commitSha, decision, std::time(nullptr)}
        );
    }

    void recordCheck(
        int number,
        std::string context,
        std::string commitSha,
        CheckState state
    ) {
        PullRequest& pr = getPullRequest(number);
        if (context.empty() || !commits_.count(commitSha)) {
            throw std::invalid_argument("Check context and commit are required.");
        }
        pr.checks.push_back(StatusCheck{
            std::move(context), std::move(commitSha), state, std::time(nullptr)
        });
    }

    void addComment(
        int number,
        ReviewComment comment
    ) {
        PullRequest& pr = getPullRequest(number);
        if (pr.state != PullRequestState::Open) {
            throw std::logic_error("Comments require an open pull request.");
        }
        if (comment.body.empty()) {
            throw std::invalid_argument("Review comment cannot be empty.");
        }
        if (comment.filePath.has_value() != comment.line.has_value()) {
            throw std::invalid_argument("Inline comment requires a path and line.");
        }
        if (comment.line && *comment.line < 1) {
            throw std::invalid_argument("Inline comment line must be positive.");
        }
        pr.comments.push_back(std::move(comment));
    }

    void resolveComment(int number, const std::string& commentId) {
        PullRequest& pr = getPullRequest(number);
        const auto it = std::find_if(
            pr.comments.begin(), pr.comments.end(),
            [&](const ReviewComment& comment) { return comment.id == commentId; }
        );
        if (it == pr.comments.end()) {
            throw std::invalid_argument("Review comment not found.");
        }
        it->resolved = true;
    }

    void synchronizeBase(int number) {
        PullRequest& pr = getPullRequest(number);
        if (pr.state != PullRequestState::Open && pr.state != PullRequestState::Draft) {
            throw std::logic_error("Only active pull requests can synchronize.");
        }
        pr.baseSha = branches_.at(pr.targetBranch).headSha;
    }

    std::vector<std::string> evaluateMerge(int number, MergeStrategy strategy) const {
        const PullRequest& pr = getPullRequestConst(number);
        std::vector<std::string> blockers;

        if (pr.state != PullRequestState::Open || pr.draft) {
            blockers.push_back("Pull request must be published and open.");
            return blockers;
        }

        const auto sourceIt = branches_.find(pr.sourceBranch);
        const auto targetIt = branches_.find(pr.targetBranch);
        if (sourceIt == branches_.end() || targetIt == branches_.end() ||
            sourceIt->second.deleted || targetIt->second.deleted) {
            blockers.push_back("Source or target branch is missing or deleted.");
            return blockers;
        }
        if (sourceIt->second.headSha != pr.headSha) {
            blockers.push_back("Source branch head differs from pull request head.");
        }

        const auto protectionIt = protections_.find(pr.targetBranch);
        if (protectionIt == protections_.end()) {
            return blockers;
        }
        const BranchProtection& policy = protectionIt->second;

        if (!policy.allowedStrategies.count(strategy)) {
            blockers.push_back("Requested merge strategy is prohibited.");
        }
        if (policy.requireUpToDateBase && pr.baseSha != targetIt->second.headSha) {
            blockers.push_back("Target branch advanced; base synchronization is required.");
        }
        if (policy.requireLinearHistory && strategy == MergeStrategy::MergeCommit) {
            blockers.push_back("Merge commits violate the linear-history policy.");
        }

        std::map<std::string, Review> latestReviews;
        for (const Review& review : pr.reviews) {
            const auto current = latestReviews.find(review.reviewerId);
            if (current == latestReviews.end() ||
                review.submittedAt >= current->second.submittedAt) {
                latestReviews[review.reviewerId] = review;
            }
        }

        std::set<std::string> eligibleApprovals;
        for (const auto& entry : latestReviews) {
            const Review& review = entry.second;
            if (review.decision != ReviewDecision::Approved) continue;
            if (policy.dismissStaleApprovals && review.commitSha != pr.headSha) continue;

            const auto reviewerIt = reviewers_.find(review.reviewerId);
            if (reviewerIt == reviewers_.end() || !reviewerIt->second.active) continue;
            if (!policy.eligibleTeams.empty() &&
                !policy.eligibleTeams.count(reviewerIt->second.team)) continue;

            eligibleApprovals.insert(review.reviewerId);
        }

        if (eligibleApprovals.size() < policy.requiredApprovals) {
            std::ostringstream message;
            message << "Required approvals: " << policy.requiredApprovals
                    << ", eligible approvals: " << eligibleApprovals.size() << ".";
            blockers.push_back(message.str());
        }

        // A check is valid only for the exact head commit. A passing check
        // attached to an older revision is not evidence for the proposed tree.
        std::map<std::string, StatusCheck> latestChecks;
        for (const StatusCheck& check : pr.checks) {
            if (check.commitSha != pr.headSha) continue;
            const auto current = latestChecks.find(check.context);
            if (current == latestChecks.end() ||
                check.completedAt >= current->second.completedAt) {
                latestChecks[check.context] = check;
            }
        }

        for (const auto& context : policy.requiredChecks) {
            const auto check = latestChecks.find(context);
            if (check == latestChecks.end()) {
                blockers.push_back("Required check is missing: " + context);
            } else if (check->second.state != CheckState::Success) {
                blockers.push_back(
                    "Required check is " + toString(check->second.state) + ": " + context
                );
            }
        }

        if (policy.requireResolvedConversations) {
            const auto unresolved = std::count_if(
                pr.comments.begin(), pr.comments.end(),
                [](const ReviewComment& comment) { return !comment.resolved; }
            );
            if (unresolved > 0) {
                blockers.push_back("Unresolved review conversations remain.");
            }
        }

        if (policy.requireSignedCommits) {
            // Signature state is intentionally absent from this case-study model.
            blockers.push_back("Signed-commit verification evidence is unavailable.");
        }

        return blockers;
    }

    std::string merge(int number, MergeStrategy strategy, const std::string& actor) {
        PullRequest& pr = getPullRequest(number);
        const auto blockers = evaluateMerge(number, strategy);
        if (!blockers.empty()) {
            std::ostringstream error;
            error << "Merge rejected";
            for (const auto& blocker : blockers) error << "\n- " << blocker;
            throw std::runtime_error(error.str());
        }

        const std::string mergeSha =
            "sim-merge-" + std::to_string(number) + "-" + pr.headSha;
        const std::string targetSha = branches_.at(pr.targetBranch).headSha;

        if (!commits_.count(mergeSha)) {
            addCommit(Commit{
                mergeSha,
                actor,
                "Merge pull request #" + std::to_string(number) + ": " + pr.title,
                {targetSha, pr.headSha}
            });
        }

        branches_.at(pr.targetBranch).headSha = mergeSha;
        pr.state = PullRequestState::Merged;
        pr.mergedSha = mergeSha;
        auditLog_.push_back("merged #" + std::to_string(number) + " by " + actor);
        return mergeSha;
    }

    void directPush(const std::string& branchName, const std::string& sha) {
        Branch& branch = branches_.at(branchName);
        const auto policy = protections_.find(branchName);
        if (policy != protections_.end() && policy->second.prohibitDirectPushes) {
            throw std::runtime_error("Direct push blocked by branch protection.");
        }
        if (!commits_.count(sha)) {
            throw std::invalid_argument("Unknown target commit.");
        }
        branch.headSha = sha;
    }

    void deleteBranch(const std::string& branchName) {
        Branch& branch = branches_.at(branchName);
        if (branchName == defaultBranch_) {
            throw std::runtime_error("Default branch cannot be deleted.");
        }
        const auto policy = protections_.find(branchName);
        if (policy != protections_.end() && policy->second.prohibitDeletion) {
            throw std::runtime_error("Protected branch deletion is prohibited.");
        }
        branch.deleted = true;
    }

    const std::string& branchHead(const std::string& branchName) const {
        return branches_.at(branchName).headSha;
    }

    const std::vector<std::string>& auditLog() const {
        return auditLog_;
    }

private:
    std::string name_;
    std::string defaultBranch_;
    std::map<std::string, Commit> commits_;
    std::map<std::string, Branch> branches_;
    std::map<std::string, Reviewer> reviewers_;
    std::map<std::string, BranchProtection> protections_;
    std::map<int, PullRequest> pullRequests_;
    std::vector<std::string> auditLog_;

    PullRequest& getPullRequest(int number) {
        const auto it = pullRequests_.find(number);
        if (it == pullRequests_.end()) {
            throw std::invalid_argument("Pull request does not exist.");
        }
        return it->second;
    }

    const PullRequest& getPullRequestConst(int number) const {
        const auto it = pullRequests_.find(number);
        if (it == pullRequests_.end()) {
            throw std::invalid_argument("Pull request does not exist.");
        }
        return it->second;
    }
};

int main() {
    try {
        Repository repository("payments-api", "main");

        repository.addCommit({"p100", "developer", "Initial service", {}});
        repository.addCommit({"p110", "developer", "Add idempotency keys", {"p100"}});
        repository.addBranch("main", "p100");
        repository.addBranch("feature/idempotency", "p110");

        repository.addReviewer({"security-reviewer", "security", true});
        repository.addReviewer({"platform-reviewer", "platform", true});

        BranchProtection policy;
        policy.requiredApprovals = 2;
        policy.requiredChecks = {"unit-tests", "dependency-audit"};
        policy.eligibleTeams = {"security", "platform"};
        policy.allowedStrategies = {MergeStrategy::Squash};
        policy.requireResolvedConversations = true;
        policy.requireUpToDateBase = true;
        policy.dismissStaleApprovals = true;
        policy.prohibitDirectPushes = true;
        repository.setProtection("main", policy);

        PullRequest& pr = repository.openPullRequest(
            41,
            "developer",
            "feature/idempotency",
            "main",
            "Enforce payment idempotency"
        );

        repository.submitReview(
            41, "security-reviewer", "p110", ReviewDecision::Approved
        );
        repository.submitReview(
            41, "platform-reviewer", "p110", ReviewDecision::Approved
        );
        repository.recordCheck(41, "unit-tests", "p110", CheckState::Success);
        repository.recordCheck(41, "dependency-audit", "p110", CheckState::Success);

        repository.addComment(
            41,
            ReviewComment{
                "comment-1",
                "security-reviewer",
                "Retry behavior needs a concurrency test.",
                std::string("src/idempotency.cpp"),
                88,
                false
            }
        );

        std::cout << "Repository governance: " << pr.title << "\n";
        auto blockers = repository.evaluateMerge(41, MergeStrategy::Squash);
        for (const auto& blocker : blockers) {
            std::cout << "BLOCKED: " << blocker << "\n";
        }

        repository.resolveComment(41, "comment-1");
        blockers = repository.evaluateMerge(41, MergeStrategy::Squash);

        if (blockers.empty()) {
            const std::string mergeSha = repository.merge(
                41, MergeStrategy::Squash, "release-bot"
            );
            std::cout << "Merged as " << mergeSha << "\n";
            std::cout << "Target branch head: " << repository.branchHead("main") << "\n";
        }

        try {
            repository.directPush("main", "p110");
        } catch (const std::exception& error) {
            std::cout << "Expected governance rejection: " << error.what() << "\n";
        }

        std::cout << "Audit entries: " << repository.auditLog().size() << "\n";
    } catch (const std::exception& error) {
        std::cerr << "Fatal domain error: " << error.what() << "\n";
        return 1;
    }
    return 0;
}
