import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public class RepositoryGovernance {

    enum PullRequestState {
        DRAFT, OPEN, CLOSED, MERGED
    }

    enum ReviewState {
        COMMENTED, APPROVED, CHANGES_REQUESTED, DISMISSED
    }

    enum MergeStrategy {
        MERGE_COMMIT, SQUASH, REBASE
    }

    record Commit(String sha, String message) {
        Commit {
            if (sha == null || sha.isBlank()) {
                throw new IllegalArgumentException("Commit SHA is required");
            }
            if (message == null || message.isBlank()) {
                throw new IllegalArgumentException("Commit message is required");
            }
        }
    }

    record Review(
        String reviewer,
        ReviewState state,
        String commitSha
    ) {
        Review {
            if (reviewer == null || reviewer.isBlank()) {
                throw new IllegalArgumentException("Reviewer is required");
            }
            Objects.requireNonNull(state, "Review state is required");
            if (commitSha == null || commitSha.isBlank()) {
                throw new IllegalArgumentException("Review commit is required");
            }
        }
    }

    record StatusCheck(String name, boolean passed) {
        StatusCheck {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("Status check name is required");
            }
        }
    }

    record BranchProtection(
        String branch,
        int requiredReviews,
        Set<String> requiredChecks,
        boolean requireResolvedConversations,
        boolean allowDirectPush,
        boolean allowForcePush,
        boolean requireLinearHistory
    ) {
        BranchProtection {
            if (branch == null || branch.isBlank()) {
                throw new IllegalArgumentException("Protected branch is required");
            }
            if (requiredReviews < 0) {
                throw new IllegalArgumentException(
                    "Required reviews cannot be negative"
                );
            }
            requiredChecks = Set.copyOf(requiredChecks);
        }
    }

    static final class PullRequest {
        private final int number;
        private final String sourceBranch;
        private final String targetBranch;
        private PullRequestState state;
        private final List<Commit> commits = new ArrayList<>();
        private final List<Review> reviews = new ArrayList<>();
        private final Map<String, StatusCheck> checks = new HashMap<>();
        private int unresolvedConversations;
        private int baseRevision;
        private MergeStrategy mergeStrategy;

        PullRequest(
            int number,
            String sourceBranch,
            String targetBranch,
            List<Commit> commits,
            int baseRevision
        ) {
            if (number <= 0) {
                throw new IllegalArgumentException("PR number must be positive");
            }
            if (sourceBranch.equals(targetBranch)) {
                throw new IllegalArgumentException(
                    "Source and target branches must differ"
                );
            }
            if (commits.isEmpty()) {
                throw new IllegalArgumentException(
                    "A PR must contain at least one commit"
                );
            }

            this.number = number;
            this.sourceBranch = sourceBranch;
            this.targetBranch = targetBranch;
            this.commits.addAll(commits);
            this.baseRevision = baseRevision;
            this.state = PullRequestState.OPEN;
        }

        int number() {
            return number;
        }

        String targetBranch() {
            return targetBranch;
        }

        PullRequestState state() {
            return state;
        }

        List<Commit> commits() {
            return Collections.unmodifiableList(commits);
        }

        List<Review> reviews() {
            return Collections.unmodifiableList(reviews);
        }

        Map<String, StatusCheck> checks() {
            return Collections.unmodifiableMap(checks);
        }

        int unresolvedConversations() {
            return unresolvedConversations;
        }

        int baseRevision() {
            return baseRevision;
        }

        void addCommit(Commit commit) {
            requireOpen();
            commits.add(commit);
        }

        void addReview(Review review) {
            requireOpen();

            boolean commitExists = commits.stream()
                .anyMatch(c -> c.sha().equals(review.commitSha()));

            if (!commitExists) {
                throw new IllegalArgumentException(
                    "Review must reference a PR commit"
                );
            }

            reviews.add(review);
        }

        void setCheck(StatusCheck check) {
            checks.put(check.name(), check);
        }

        void openConversation() {
            unresolvedConversations++;
        }

        void resolveConversation() {
            if (unresolvedConversations > 0) {
                unresolvedConversations--;
            }
        }

        void synchronize(int targetRevision) {
            if (targetRevision < baseRevision) {
                throw new IllegalArgumentException(
                    "Target revision cannot move backwards"
                );
            }
            baseRevision = targetRevision;
        }

        void merge(MergeStrategy strategy) {
            requireOpen();
            mergeStrategy = strategy;
            state = PullRequestState.MERGED;
        }

        private void requireOpen() {
            if (state != PullRequestState.OPEN) {
                throw new IllegalStateException(
                    "Operation requires an open Pull Request"
                );
            }
        }
    }

    record MergeDecision(boolean eligible, List<String> reasons) {
        MergeDecision {
            reasons = List.copyOf(reasons);
        }
    }

    static final class MergeEligibilityService {
        private final Map<String, BranchProtection> policies =
            new HashMap<>();

        void registerPolicy(BranchProtection policy) {
            policies.put(policy.branch(), policy);
        }

        MergeDecision evaluate(
            PullRequest pr,
            Set<String> eligibleReviewers,
            int currentTargetRevision
        ) {
            List<String> failures = new ArrayList<>();

            BranchProtection policy = policies.get(pr.targetBranch());

            if (policy == null) {
                failures.add("Target branch has no protection policy");
                return new MergeDecision(false, failures);
            }

            if (pr.state() != PullRequestState.OPEN) {
                failures.add("Pull Request is not open");
            }

            if (pr.baseRevision() != currentTargetRevision) {
                failures.add("Pull Request is behind the target branch");
            }

            if (
                policy.requireResolvedConversations() &&
                pr.unresolvedConversations() > 0
            ) {
                failures.add("Unresolved conversations remain");
            }

            for (String required : policy.requiredChecks()) {
                StatusCheck check = pr.checks().get(required);
                if (check == null || !check.passed()) {
                    failures.add(
                        "Required check has not passed: " + required
                    );
                }
            }

            if (!pr.commits().isEmpty()) {
                String currentCommit =
                    pr.commits().get(pr.commits().size() - 1).sha();

                Map<String, Review> latest = new HashMap<>();

                for (Review review : pr.reviews()) {
                    if (eligibleReviewers.contains(review.reviewer())) {
                        latest.put(review.reviewer(), review);
                    }
                }

                long approvals = latest.values().stream()
                    .filter(r -> r.state() == ReviewState.APPROVED)
                    .filter(r -> r.commitSha().equals(currentCommit))
                    .count();

                if (approvals < policy.requiredReviews()) {
                    failures.add(
                        "Current approvals: " + approvals +
                        ", required: " + policy.requiredReviews()
                    );
                }
            }

            return new MergeDecision(failures.isEmpty(), failures);
        }

        void merge(
            PullRequest pr,
            Set<String> eligibleReviewers,
            int currentTargetRevision,
            MergeStrategy strategy
        ) {
            MergeDecision decision = evaluate(
                pr,
                eligibleReviewers,
                currentTargetRevision
            );

            if (!decision.eligible()) {
                throw new IllegalStateException(
                    "Merge blocked: " +
                    String.join("; ", decision.reasons())
                );
            }

            BranchProtection policy = policies.get(pr.targetBranch());

            if (
                policy.requireLinearHistory() &&
                strategy == MergeStrategy.MERGE_COMMIT
            ) {
                throw new IllegalStateException(
                    "Merge commits violate linear-history policy"
                );
            }

            pr.merge(strategy);
        }
    }

    public static void main(String[] args) {
        MergeEligibilityService service =
            new MergeEligibilityService();

        service.registerPolicy(
            new BranchProtection(
                "main",
                2,
                Set.of("tests", "security"),
                true,
                false,
                false,
                true
            )
        );

        PullRequest pr = new PullRequest(
            210,
            "feature/invoice-validation",
            "main",
            List.of(
                new Commit("a01", "Validate invoice ownership"),
                new Commit("a02", "Reject invalid invoice state")
            ),
            30
        );

        pr.setCheck(new StatusCheck("tests", true));
        pr.setCheck(new StatusCheck("security", true));
        pr.openConversation();

        pr.addReview(
            new Review(
                "alice",
                ReviewState.APPROVED,
                "a02"
            )
        );

        pr.addReview(
            new Review(
                "bob",
                ReviewState.APPROVED,
                "a02"
            )
        );

        Set<String> eligibleReviewers =
            new HashSet<>(Set.of("alice", "bob"));

        MergeDecision beforeResolution = service.evaluate(
            pr,
            eligibleReviewers,
            30
        );

        System.out.println(
            "Eligible before resolution: " +
            beforeResolution.eligible()
        );
        beforeResolution.reasons()
            .forEach(reason -> System.out.println("Reason: " + reason));

        pr.resolveConversation();

        // A new commit invalidates approvals tied to the previous changeset.
        pr.addCommit(
            new Commit("a03", "Harden invoice authorization")
        );

        MergeDecision afterCommit = service.evaluate(
            pr,
            eligibleReviewers,
            30
        );

        System.out.println(
            "Eligible after new commit: " +
            afterCommit.eligible()
        );
        afterCommit.reasons()
            .forEach(reason -> System.out.println("Reason: " + reason));

        pr.addReview(
            new Review(
                "alice",
                ReviewState.APPROVED,
                "a03"
            )
        );

        pr.addReview(
            new Review(
                "bob",
                ReviewState.APPROVED,
                "a03"
            )
        );

        service.merge(
            pr,
            eligibleReviewers,
            30,
            MergeStrategy.REBASE
        );

        System.out.println(
            "Final Pull Request state: " + pr.state()
        );
    }
}
