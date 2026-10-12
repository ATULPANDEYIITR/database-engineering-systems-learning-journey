import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;

/**
 * Enterprise repository governance with explicit temporal and review policies.
 * Compile: javac TemporalRepositoryGovernance.java
 * Run: java TemporalRepositoryGovernance
 */
public class TemporalRepositoryGovernance {

    enum PullRequestState {
        DRAFT, OPEN, CLOSED, MERGED
    }

    enum ReviewState {
        PENDING, COMMENTED, CHANGES_REQUESTED, APPROVED, DISMISSED
    }

    enum CheckConclusion {
        PENDING, SUCCESS, FAILURE, CANCELLED
    }

    enum MergeStrategy {
        SQUASH, REBASE, MERGE_COMMIT
    }

    record Commit(String id, Instant createdAt, String message) {
        Commit {
            if (id == null || id.isBlank()) throw new IllegalArgumentException("Commit ID is required.");
            Objects.requireNonNull(createdAt, "Commit time is required.");
            if (message == null || message.isBlank()) throw new IllegalArgumentException("Commit message is required.");
        }
    }

    record FileChange(String path, int additions, int deletions) {
        FileChange {
            if (path == null || path.isBlank()) throw new IllegalArgumentException("File path is required.");
            if (additions < 0 || deletions < 0) throw new IllegalArgumentException("Change counts cannot be negative.");
        }
    }

    record ReviewComment(
        String id,
        String reviewer,
        String filePath,
        int line,
        String body,
        boolean resolved,
        Instant createdAt
    ) {
        ReviewComment {
            if (id == null || id.isBlank() || reviewer == null || reviewer.isBlank()) {
                throw new IllegalArgumentException("Comment ID and reviewer are required.");
            }
            if (filePath == null || filePath.isBlank() || line < 1) {
                throw new IllegalArgumentException("Inline comments require a file and positive line.");
            }
            if (body == null || body.isBlank()) throw new IllegalArgumentException("Comment body is required.");
            Objects.requireNonNull(createdAt, "Comment timestamp is required.");
        }

        ReviewComment resolve() {
            return new ReviewComment(id, reviewer, filePath, line, body, true, createdAt);
        }
    }

    record Review(
        String reviewer,
        ReviewState state,
        String commitId,
        Instant submittedAt,
        boolean dismissed
    ) {
        Review {
            if (reviewer == null || reviewer.isBlank()) throw new IllegalArgumentException("Reviewer is required.");
            Objects.requireNonNull(state, "Review state is required.");
            if (commitId == null || commitId.isBlank()) throw new IllegalArgumentException("Reviewed commit is required.");
            Objects.requireNonNull(submittedAt, "Review timestamp is required.");
        }
    }

    record StatusCheck(
        String name,
        String commitId,
        CheckConclusion conclusion,
        Instant completedAt
    ) {
        StatusCheck {
            if (name == null || name.isBlank()) throw new IllegalArgumentException("Check name is required.");
            if (commitId == null || commitId.isBlank()) throw new IllegalArgumentException("Check commit is required.");
            Objects.requireNonNull(conclusion, "Check conclusion is required.");
            Objects.requireNonNull(completedAt, "Check timestamp is required.");
        }
    }

    static final class BranchProtectionPolicy {
        final String branch;
        final int requiredApprovals;
        final Set<String> eligibleReviewers;
        final Set<String> codeOwnerPaths;
        final Set<String> requiredChecks;
        final Set<MergeStrategy> permittedStrategies;
        final boolean dismissStaleApprovals;
        final boolean requireCodeOwnerApproval;
        final boolean requireResolvedComments;
        final boolean requireSynchronizedBase;
        final boolean requireLinearHistory;
        final boolean allowDirectPush;
        final boolean allowForcePush;
        final boolean allowDeletion;
        final Set<String> bypassActors;

        BranchProtectionPolicy(
            String branch,
            int requiredApprovals,
            Set<String> eligibleReviewers,
            Set<String> codeOwnerPaths,
            Set<String> requiredChecks,
            Set<MergeStrategy> permittedStrategies,
            boolean dismissStaleApprovals,
            boolean requireCodeOwnerApproval,
            boolean requireResolvedComments,
            boolean requireSynchronizedBase,
            boolean requireLinearHistory,
            boolean allowDirectPush,
            boolean allowForcePush,
            boolean allowDeletion,
            Set<String> bypassActors
        ) {
            if (branch == null || branch.isBlank()) throw new IllegalArgumentException("Protected branch is required.");
            if (requiredApprovals < 0) throw new IllegalArgumentException("Approval threshold cannot be negative.");
            this.branch = branch;
            this.requiredApprovals = requiredApprovals;
            this.eligibleReviewers = Set.copyOf(eligibleReviewers);
            this.codeOwnerPaths = Set.copyOf(codeOwnerPaths);
            this.requiredChecks = Set.copyOf(requiredChecks);
            this.permittedStrategies = Set.copyOf(permittedStrategies);
            this.dismissStaleApprovals = dismissStaleApprovals;
            this.requireCodeOwnerApproval = requireCodeOwnerApproval;
            this.requireResolvedComments = requireResolvedComments;
            this.requireSynchronizedBase = requireSynchronizedBase;
            this.requireLinearHistory = requireLinearHistory;
            this.allowDirectPush = allowDirectPush;
            this.allowForcePush = allowForcePush;
            this.allowDeletion = allowDeletion;
            this.bypassActors = Set.copyOf(bypassActors);
        }
    }

    static final class PullRequest {
        final String id;
        final String author;
        final String sourceBranch;
        final String targetBranch;
        final Instant openedAt;
        final List<FileChange> changes = new ArrayList<>();
        final List<Review> reviews = new ArrayList<>();
        final List<ReviewComment> comments = new ArrayList<>();
        final List<StatusCheck> checks = new ArrayList<>();
        final List<Commit> commits = new ArrayList<>();

        PullRequestState state;
        String headCommit;
        String baseCommit;
        boolean baseSynchronized;
        boolean mergeConflict;
        boolean codeOwnerApproved;
        Instant mergedAt;
        String mergeCommit;
        long revision;

        PullRequest(
            String id,
            String author,
            String sourceBranch,
            String targetBranch,
            Commit base,
            Commit head,
            boolean draft
        ) {
            if (id == null || id.isBlank() || author == null || author.isBlank()) {
                throw new IllegalArgumentException("Pull Request ID and author are required.");
            }
            if (sourceBranch == null || sourceBranch.isBlank()
                || targetBranch == null || targetBranch.isBlank()
                || sourceBranch.equals(targetBranch)) {
                throw new IllegalArgumentException("Distinct source and target branches are required.");
            }
            this.id = id;
            this.author = author;
            this.sourceBranch = sourceBranch;
            this.targetBranch = targetBranch;
            this.openedAt = Instant.now();
            this.baseCommit = Objects.requireNonNull(base).id();
            this.headCommit = Objects.requireNonNull(head).id();
            this.commits.add(head);
            this.state = draft ? PullRequestState.DRAFT : PullRequestState.OPEN;
            this.baseSynchronized = true;
        }

        void markReady() {
            if (state != PullRequestState.DRAFT) {
                throw new IllegalStateException("Only a draft can be marked ready.");
            }
            state = PullRequestState.OPEN;
        }

        void addChange(FileChange change) {
            ensureMutable();
            changes.add(Objects.requireNonNull(change));
        }

        void addComment(ReviewComment comment) {
            ensureMutable();
            if (comments.stream().anyMatch(existing -> existing.id().equals(comment.id()))) {
                throw new IllegalArgumentException("Duplicate review comment ID.");
            }
            comments.add(comment);
        }

        void resolveComment(String commentId) {
            ensureMutable();
            for (int i = 0; i < comments.size(); i++) {
                if (comments.get(i).id().equals(commentId)) {
                    comments.set(i, comments.get(i).resolve());
                    return;
                }
            }
            throw new IllegalArgumentException("Review comment does not exist.");
        }

        void push(Commit commit, boolean conflicts) {
            ensureMutable();
            Objects.requireNonNull(commit);
            if (commits.stream().anyMatch(existing -> existing.id().equals(commit.id()))) {
                throw new IllegalArgumentException("Duplicate commit in Pull Request history.");
            }
            commits.add(commit);
            headCommit = commit.id();
            mergeConflict = conflicts;
            revision++;
        }

        void synchronizeBase(Commit newBase, boolean conflicts) {
            ensureMutable();
            baseCommit = Objects.requireNonNull(newBase).id();
            baseSynchronized = true;
            mergeConflict = conflicts;
        }

        void addReview(Review review, BranchProtectionPolicy policy) {
            ensureMutable();
            Objects.requireNonNull(review);
            if (review.reviewer().equals(author)) {
                throw new IllegalArgumentException("Authors cannot approve their own Pull Request.");
            }
            if (!policy.eligibleReviewers.contains(review.reviewer())) {
                throw new IllegalArgumentException("Reviewer is not eligible under policy.");
            }
            if (!review.commitId().equals(headCommit)) {
                throw new IllegalArgumentException("Review must reference the current head commit.");
            }
            reviews.add(review);
        }

        void addStatusCheck(StatusCheck check) {
            ensureMutable();
            checks.add(Objects.requireNonNull(check));
        }

        void ensureMutable() {
            if (state != PullRequestState.OPEN && state != PullRequestState.DRAFT) {
                throw new IllegalStateException("Completed Pull Requests cannot be modified.");
            }
        }

        void close() {
            if (state == PullRequestState.MERGED) throw new IllegalStateException("Merged request cannot be closed.");
            if (state != PullRequestState.OPEN && state != PullRequestState.DRAFT) {
                throw new IllegalStateException("Pull Request is already closed.");
            }
            state = PullRequestState.CLOSED;
        }

        void reopen() {
            if (state != PullRequestState.CLOSED) {
                throw new IllegalStateException("Only a closed, unmerged request can be reopened.");
            }
            state = PullRequestState.OPEN;
        }
    }

    record Eligibility(boolean eligible, List<String> blockers) {
        Eligibility {
            blockers = List.copyOf(blockers);
        }
    }

    static final class GovernanceService {
        private final BranchProtectionPolicy policy;
        private final Map<String, PullRequest> pullRequests = new LinkedHashMap<>();
        private final Map<String, Commit> commits = new HashMap<>();

        GovernanceService(BranchProtectionPolicy policy) {
            this.policy = Objects.requireNonNull(policy);
        }

        void registerCommit(Commit commit) {
            Commit existing = commits.putIfAbsent(commit.id(), commit);
            if (existing != null && !existing.equals(commit)) {
                throw new IllegalArgumentException("Commit ID cannot be reused with different content.");
            }
        }

        void registerPullRequest(PullRequest pr) {
            if (!pr.targetBranch.equals(policy.branch)) {
                throw new IllegalArgumentException("Pull Request target is not the protected branch.");
            }
            if (!commits.containsKey(pr.baseCommit) || !commits.containsKey(pr.headCommit)) {
                throw new IllegalArgumentException("Pull Request references unregistered commits.");
            }
            if (pullRequests.putIfAbsent(pr.id, pr) != null) {
                throw new IllegalArgumentException("Pull Request ID already exists.");
            }
        }

        Eligibility evaluate(String id, String actor, MergeStrategy strategy) {
            PullRequest pr = requireRequest(id);
            List<String> blockers = new ArrayList<>();

            // A bypass is an explicit governance exception, not an ordinary approval.
            if (policy.bypassActors.contains(actor)) {
                return new Eligibility(true, List.of("Explicit policy bypass by " + actor));
            }

            if (pr.state != PullRequestState.OPEN) blockers.add("Pull Request must be open.");
            if (!pr.targetBranch.equals(policy.branch)) blockers.add("Target branch is not protected by this policy.");
            if (policy.requireSynchronizedBase && !pr.baseSynchronized) {
                blockers.add("Base branch synchronization is required.");
            }
            if (pr.mergeConflict) blockers.add("Merge conflict must be resolved.");
            if (policy.requireResolvedComments
                && pr.comments.stream().anyMatch(comment -> !comment.resolved())) {
                blockers.add("Unresolved review comments remain.");
            }
            if (!policy.permittedStrategies.contains(strategy)) {
                blockers.add("Merge strategy is not permitted.");
            }
            if (policy.requireLinearHistory && strategy == MergeStrategy.MERGE_COMMIT) {
                blockers.add("Linear history prohibits merge commits.");
            }

            Set<String> validApprovers = pr.reviews.stream()
                .filter(review -> review.state() == ReviewState.APPROVED)
                .filter(review -> !review.dismissed())
                .filter(review -> review.commitId().equals(pr.headCommit))
                .filter(review -> !review.reviewer().equals(pr.author))
                .filter(review -> policy.eligibleReviewers.contains(review.reviewer()))
                .map(Review::reviewer)
                .collect(Collectors.toCollection(TreeSet::new));

            if (validApprovers.size() < policy.requiredApprovals) {
                blockers.add("Required number of current approvals has not been met.");
            }

            if (policy.requireCodeOwnerApproval
                && pr.changes.stream().anyMatch(change -> policy.codeOwnerPaths.contains(change.path()))
                && !pr.codeOwnerApproved) {
                blockers.add("Code-owner approval is required for a protected file.");
            }

            for (String required : policy.requiredChecks) {
                boolean passed = pr.checks.stream().anyMatch(check ->
                    check.name().equals(required)
                    && check.commitId().equals(pr.headCommit)
                    && check.conclusion() == CheckConclusion.SUCCESS
                );
                if (!passed) blockers.add("Required check missing or stale: " + required);
            }

            return new Eligibility(blockers.isEmpty(), blockers);
        }

        void merge(String id, String actor, MergeStrategy strategy) {
            PullRequest pr = requireRequest(id);
            Eligibility eligibility = evaluate(id, actor, strategy);
            if (!eligibility.eligible()) {
                throw new IllegalStateException(
                    "Merge blocked for " + id + ": " + String.join("; ", eligibility.blockers())
                );
            }
            // The merge state transition is applied only after every policy condition passes.
            pr.state = PullRequestState.MERGED;
            pr.mergedAt = Instant.now();
            pr.mergeCommit = "merge-result-" + id;
        }

        boolean authorizeDirectPush(String actor) {
            return policy.allowDirectPush && policy.bypassActors.contains(actor);
        }

        boolean authorizeForcePush(String actor) {
            return policy.allowForcePush && policy.bypassActors.contains(actor);
        }

        boolean authorizeBranchDeletion(String actor) {
            return policy.allowDeletion && policy.bypassActors.contains(actor);
        }

        PullRequest requireRequest(String id) {
            PullRequest pr = pullRequests.get(id);
            if (pr == null) throw new IllegalArgumentException("Unknown Pull Request: " + id);
            return pr;
        }
    }

    public static void main(String[] args) {
        BranchProtectionPolicy policy = new BranchProtectionPolicy(
            "main",
            2,
            Set.of("asha", "kabir", "meera"),
            Set.of("src/security/TokenService.java"),
            Set.of("unit-tests", "dependency-audit"),
            Set.of(MergeStrategy.SQUASH, MergeStrategy.REBASE),
            true,
            true,
            true,
            true,
            true,
            false,
            false,
            false,
            Set.of("emergency-release-manager")
        );

        GovernanceService service = new GovernanceService(policy);
        Commit base = new Commit("base-100", Instant.parse("2026-10-10T09:00:00Z"), "Current main");
        Commit head = new Commit("head-200", Instant.parse("2026-10-12T08:00:00Z"), "Rotate refresh tokens");
        service.registerCommit(base);
        service.registerCommit(head);

        PullRequest pr = new PullRequest(
            "PR-482", "ravi", "feature/token-rotation", "main", base, head, true
        );
        pr.addChange(new FileChange("src/security/TokenService.java", 94, 21));
        pr.addChange(new FileChange("src/security/TokenServiceTest.java", 61, 5));
        service.registerPullRequest(pr);

        pr.markReady();
        Instant reviewTime = Instant.parse("2026-10-12T09:00:00Z");
        pr.addReview(new Review("asha", ReviewState.APPROVED, "head-200", reviewTime, false), policy);
        pr.addReview(new Review("kabir", ReviewState.APPROVED, "head-200", reviewTime, false), policy);
        pr.addStatusCheck(new StatusCheck(
            "unit-tests", "head-200", CheckConclusion.SUCCESS, Instant.now()
        ));
        pr.addStatusCheck(new StatusCheck(
            "dependency-audit", "head-200", CheckConclusion.SUCCESS, Instant.now()
        ));

        System.out.println("Initial merge eligibility:");
        System.out.println(service.evaluate("PR-482", "release-bot", MergeStrategy.SQUASH));

        pr.addComment(new ReviewComment(
            "COMMENT-9", "asha", "src/security/TokenService.java",
            47, "Reject expired refresh tokens before rotation.", false, reviewTime
        ));
        System.out.println("Eligibility with unresolved discussion:");
        System.out.println(service.evaluate("PR-482", "release-bot", MergeStrategy.SQUASH));

        pr.resolveComment("COMMENT-9");
        pr.codeOwnerApproved = true;
        Commit newHead = new Commit(
            "head-201", Instant.parse("2026-10-12T10:00:00Z"), "Handle token expiry"
        );
        service.registerCommit(newHead);
        pr.push(newHead, false);

        // Existing reviews and status checks refer to head-200, so they no longer
        // satisfy a policy that evaluates the current head-201.
        System.out.println("Eligibility after new commit:");
        System.out.println(service.evaluate("PR-482", "release-bot", MergeStrategy.SQUASH));

        Instant newReviewTime = Instant.parse("2026-10-12T10:30:00Z");
        pr.addReview(new Review("asha", ReviewState.APPROVED, "head-201", newReviewTime, false), policy);
        pr.addReview(new Review("meera", ReviewState.APPROVED, "head-201", newReviewTime, false), policy);
        pr.addStatusCheck(new StatusCheck(
            "unit-tests", "head-201", CheckConclusion.SUCCESS, Instant.now()
        ));
        pr.addStatusCheck(new StatusCheck(
            "dependency-audit", "head-201", CheckConclusion.SUCCESS, Instant.now()
        ));

        Eligibility finalDecision = service.evaluate("PR-482", "release-bot", MergeStrategy.SQUASH);
        System.out.println("Final eligibility: " + finalDecision);
        service.merge("PR-482", "release-bot", MergeStrategy.SQUASH);
        System.out.println("Merged state: " + pr.state + " at " + pr.mergedAt);

        try {
            pr.push(new Commit(
                "head-202", Instant.now(), "Attempted post-merge edit"
            ), false);
        } catch (IllegalStateException exception) {
            System.out.println("Post-merge modification rejected: " + exception.getMessage());
        }

        System.out.println("Direct push permitted: " + service.authorizeDirectPush("developer-ravi"));
        System.out.println("Force push permitted: " + service.authorizeForcePush("developer-ravi"));
        System.out.println("Branch deletion permitted: " + service.authorizeBranchDeletion("developer-ravi"));
    }
}
