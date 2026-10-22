import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public class PlpgsqlConceptsEnterprise {

    enum PullRequestState {
        OPEN,
        MERGED,
        CLOSED
    }

    enum ReviewState {
        COMMENTED,
        CHANGES_REQUESTED,
        APPROVED,
        DISMISSED
    }

    enum MergeStrategy {
        MERGE_COMMIT,
        SQUASH,
        REBASE
    }

    record Review(
            String reviewer,
            ReviewState state,
            String comment
    ) {
        Review {
            Objects.requireNonNull(reviewer, "reviewer");
            Objects.requireNonNull(state, "state");

            if (reviewer.isBlank()) {
                throw new IllegalArgumentException(
                        "Reviewer cannot be blank"
                );
            }
        }
    }

    record StatusCheck(String name, boolean passed) {
        StatusCheck {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                        "Status-check name cannot be blank"
                );
            }
        }
    }

    record BranchPolicy(
            String branch,
            int requiredApprovals,
            Set<String> requiredChecks,
            boolean requireResolvedConversations,
            boolean allowDirectPush,
            boolean allowForcePush,
            boolean allowDeletion,
            boolean requireLinearHistory
    ) {
        BranchPolicy {
            Objects.requireNonNull(branch, "branch");
            Objects.requireNonNull(requiredChecks, "requiredChecks");

            if (branch.isBlank()) {
                throw new IllegalArgumentException(
                        "Protected branch cannot be blank"
                );
            }

            if (requiredApprovals < 0) {
                throw new IllegalArgumentException(
                        "Required approvals cannot be negative"
                );
            }

            requiredChecks = Set.copyOf(requiredChecks);
        }
    }

    static final class PullRequest {
        private final int number;
        private final String title;
        private final String sourceBranch;
        private final String targetBranch;
        private final int changedFiles;
        private final List<Review> reviews;
        private final List<StatusCheck> statusChecks;

        private PullRequestState state;
        private int unresolvedConversations;

        PullRequest(
                int number,
                String title,
                String sourceBranch,
                String targetBranch,
                int changedFiles,
                List<Review> reviews,
                List<StatusCheck> statusChecks
        ) {
            if (number <= 0) {
                throw new IllegalArgumentException(
                        "Pull Request number must be positive"
                );
            }

            if (title == null || title.isBlank()) {
                throw new IllegalArgumentException(
                        "Pull Request title cannot be blank"
                );
            }

            if (sourceBranch == null || sourceBranch.isBlank()) {
                throw new IllegalArgumentException(
                        "Source branch cannot be blank"
                );
            }

            if (targetBranch == null || targetBranch.isBlank()) {
                throw new IllegalArgumentException(
                        "Target branch cannot be blank"
                );
            }

            if (changedFiles < 0) {
                throw new IllegalArgumentException(
                        "Changed-file count cannot be negative"
                );
            }

            this.number = number;
            this.title = title;
            this.sourceBranch = sourceBranch;
            this.targetBranch = targetBranch;
            this.changedFiles = changedFiles;
            this.reviews = new ArrayList<>(reviews);
            this.statusChecks = new ArrayList<>(statusChecks);
            this.state = PullRequestState.OPEN;
        }

        int number() {
            return number;
        }

        String title() {
            return title;
        }

        String sourceBranch() {
            return sourceBranch;
        }

        String targetBranch() {
            return targetBranch;
        }

        int changedFiles() {
            return changedFiles;
        }

        PullRequestState state() {
            return state;
        }

        List<Review> reviews() {
            return List.copyOf(reviews);
        }

        List<StatusCheck> statusChecks() {
            return List.copyOf(statusChecks);
        }

        int unresolvedConversations() {
            return unresolvedConversations;
        }

        void setUnresolvedConversations(int count) {
            if (count < 0) {
                throw new IllegalArgumentException(
                        "Conversation count cannot be negative"
                );
            }

            unresolvedConversations = count;
        }

        void merge() {
            state = PullRequestState.MERGED;
        }

        void close() {
            if (state == PullRequestState.MERGED) {
                throw new IllegalStateException(
                        "A merged Pull Request cannot be closed"
                );
            }

            state = PullRequestState.CLOSED;
        }
    }

    record EligibilityResult(
            boolean eligible,
            List<String> reasons
    ) {
        EligibilityResult {
            reasons = List.copyOf(reasons);
        }
    }

    static final class MergeEligibilityService {
        private final Map<String, BranchPolicy> policies = new HashMap<>();

        void registerPolicy(BranchPolicy policy) {
            policies.put(policy.branch(), policy);
        }

        EligibilityResult evaluate(
                PullRequest pullRequest,
                MergeStrategy strategy
        ) {
            List<String> reasons = new ArrayList<>();

            BranchPolicy policy =
                    policies.get(pullRequest.targetBranch());

            if (policy == null) {
                reasons.add("target branch has no governance policy");
                return new EligibilityResult(false, reasons);
            }

            if (pullRequest.state() != PullRequestState.OPEN) {
                reasons.add("Pull Request is not open");
            }

            if (pullRequest.sourceBranch()
                    .equals(pullRequest.targetBranch())) {
                reasons.add("source and target branches must differ");
            }

            if (pullRequest.changedFiles() == 0) {
                reasons.add("Pull Request contains no changes");
            }

            long approvals = pullRequest.reviews()
                    .stream()
                    .filter(review ->
                            review.state() == ReviewState.APPROVED)
                    .count();

            if (approvals < policy.requiredApprovals()) {
                reasons.add(
                        "required approvals: "
                                + policy.requiredApprovals()
                                + ", actual approvals: "
                                + approvals
                );
            }

            Map<String, Boolean> checks = new HashMap<>();

            for (StatusCheck check : pullRequest.statusChecks()) {
                checks.put(
                        check.name().toLowerCase(),
                        check.passed()
                );
            }

            for (String required : policy.requiredChecks()) {
                Boolean passed = checks.get(required.toLowerCase());

                if (!Boolean.TRUE.equals(passed)) {
                    reasons.add(
                            "required status check failed or missing: "
                                    + required
                    );
                }
            }

            if (policy.requireResolvedConversations()
                    && pullRequest.unresolvedConversations() > 0) {
                reasons.add(
                        pullRequest.unresolvedConversations()
                                + " unresolved review conversations"
                );
            }

            if (strategy == MergeStrategy.REBASE
                    && !policy.requireLinearHistory()) {
                reasons.add(
                        "rebase strategy is not required by this policy"
                );
            }

            return new EligibilityResult(
                    reasons.isEmpty(),
                    reasons
            );
        }

        void merge(
                PullRequest pullRequest,
                MergeStrategy strategy
        ) {
            EligibilityResult result =
                    evaluate(pullRequest, strategy);

            if (!result.eligible()) {
                throw new IllegalStateException(
                        "Merge rejected: "
                                + String.join(
                                        "; ",
                                        result.reasons()
                                )
                );
            }

            pullRequest.merge();
        }
    }

    static String risk(PullRequest pullRequest) {
        int score = 0;

        if (pullRequest.changedFiles() > 20) {
            score += 2;
        } else if (pullRequest.changedFiles() > 10) {
            score++;
        }

        if (pullRequest.reviews().isEmpty()) {
            score += 2;
        }

        if (pullRequest.unresolvedConversations() > 0) {
            score++;
        }

        if (score >= 4) {
            return "HIGH";
        }

        if (score >= 2) {
            return "MEDIUM";
        }

        return "LOW";
    }

    static PullRequest createPullRequest(
            int number,
            String title,
            String source,
            int changedFiles,
            List<Review> reviews,
            List<StatusCheck> checks
    ) {
        return new PullRequest(
                number,
                title,
                source,
                "main",
                changedFiles,
                reviews,
                checks
        );
    }

    public static void main(String[] args) {
        MergeEligibilityService service =
                new MergeEligibilityService();

        service.registerPolicy(
                new BranchPolicy(
                        "main",
                        2,
                        Set.of(
                                "unit-tests",
                                "lint",
                                "security-scan"
                        ),
                        true,
                        false,
                        false,
                        false,
                        true
                )
        );

        PullRequest approved = createPullRequest(
                401,
                "Introduce repository governance service",
                "feature/governance-service",
                8,
                List.of(
                        new Review(
                                "alice",
                                ReviewState.APPROVED,
                                "Policy is sound"
                        ),
                        new Review(
                                "bob",
                                ReviewState.APPROVED,
                                "Validation is sufficient"
                        )
                ),
                List.of(
                        new StatusCheck("unit-tests", true),
                        new StatusCheck("lint", true),
                        new StatusCheck("security-scan", true)
                )
        );

        PullRequest blocked = createPullRequest(
                402,
                "Modify enterprise review rules",
                "feature/review-rules",
                16,
                List.of(
                        new Review(
                                "alice",
                                ReviewState.APPROVED,
                                "Needs another reviewer"
                        )
                ),
                List.of(
                        new StatusCheck("unit-tests", true),
                        new StatusCheck("lint", false),
                        new StatusCheck("security-scan", true)
                )
        );

        blocked.setUnresolvedConversations(1);

        List<PullRequest> requests =
                List.of(approved, blocked);

        for (PullRequest pullRequest : requests) {
            System.out.println(
                    "\nPR #" + pullRequest.number()
                            + ": " + pullRequest.title()
            );
            System.out.println(
                    "Risk: " + risk(pullRequest)
            );

            EligibilityResult result =
                    service.evaluate(
                            pullRequest,
                            MergeStrategy.MERGE_COMMIT
                    );

            System.out.println(
                    "Eligible: " + result.eligible()
            );

            if (!result.eligible()) {
                for (String reason : result.reasons()) {
                    System.out.println("  - " + reason);
                }
            }

            try {
                service.merge(
                        pullRequest,
                        MergeStrategy.MERGE_COMMIT
                );

                System.out.println(
                        "State: " + pullRequest.state()
                );
            } catch (IllegalStateException error) {
                System.out.println(
                        "Merge rejected: " + error.getMessage()
                );
            }
        }

        System.out.println(
                "\nProtected operations available: "
                        + EnumSet.of(
                                MergeStrategy.MERGE_COMMIT,
                                MergeStrategy.SQUASH,
                                MergeStrategy.REBASE
                        )
        );
    }
}
