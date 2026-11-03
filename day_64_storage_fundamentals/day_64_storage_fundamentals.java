import java.util.*;

public class RepositoryGovernanceDemo {

    enum PullRequestState {
        DRAFT, OPEN, CLOSED, MERGED
    }

    enum ReviewState {
        COMMENTED, APPROVED, CHANGES_REQUESTED, DISMISSED
    }

    enum MergeStrategy {
        MERGE_COMMIT, SQUASH, REBASE
    }

    record Commit(String sha, String message, String parentSha) {
        Commit {
            if (sha == null || sha.isBlank() || message == null || message.isBlank()) {
                throw new IllegalArgumentException("Commit identity and message are required.");
            }
        }
    }

    record StatusCheck(String name, boolean passed, boolean required, String message) {}

    record ReviewComment(String reviewer, String text) {}

    static final class Review {
        private final String reviewer;
        private final ReviewState state;
        private final String commitSha;
        private final List<ReviewComment> comments;
        private boolean dismissed;

        Review(
            String reviewer,
            ReviewState state,
            String commitSha,
            List<ReviewComment> comments
        ) {
            if (reviewer == null || reviewer.isBlank()) {
                throw new IllegalArgumentException("Reviewer is required.");
            }
            this.reviewer = reviewer;
            this.state = Objects.requireNonNull(state);
            this.commitSha = Objects.requireNonNull(commitSha);
            this.comments = List.copyOf(comments);
        }

        String reviewer() {
            return reviewer;
        }

        ReviewState state() {
            return state;
        }

        String commitSha() {
            return commitSha;
        }

        boolean dismissed() {
            return dismissed;
        }

        void dismiss() {
            dismissed = true;
        }
    }

    static final class Branch {
        private final String name;
        private boolean protectedBranch;
        private final List<Commit> commits = new ArrayList<>();

        Branch(String name, boolean protectedBranch) {
            this.name = name;
            this.protectedBranch = protectedBranch;
        }

        String head() {
            return commits.isEmpty() ? null : commits.getLast().sha();
        }
    }

    record BranchProtectionPolicy(
        int requiredReviews,
        Set<String> requiredChecks,
        boolean restrictDirectPush,
        boolean restrictForcePush,
        boolean requireConversationResolution,
        boolean requireLinearHistory,
        boolean allowAdministratorBypass
    ) {
        BranchProtectionPolicy {
            if (requiredReviews < 0) {
                throw new IllegalArgumentException("Required reviews cannot be negative.");
            }
            requiredChecks = Set.copyOf(requiredChecks);
        }
    }

    static final class PullRequest {
        private final int number;
        private final String sourceBranch;
        private final String targetBranch;
        private final String title;
        private final String author;
        private final List<Commit> commits;
        private final List<Review> reviews = new ArrayList<>();
        private final Map<String, StatusCheck> checks = new HashMap<>();

        private PullRequestState state;
        private boolean draft;
        private int unresolvedConversations;
        private String baseHeadAtCreation;
        private MergeStrategy mergeStrategy = MergeStrategy.SQUASH;

        PullRequest(
            int number,
            String sourceBranch,
            String targetBranch,
            String title,
            String author,
            String baseHeadAtCreation,
            boolean draft,
            List<Commit> commits
        ) {
            this.number = number;
            this.sourceBranch = sourceBranch;
            this.targetBranch = targetBranch;
            this.title = title;
            this.author = author;
            this.baseHeadAtCreation = baseHeadAtCreation;
            this.draft = draft;
            this.state = draft ? PullRequestState.DRAFT : PullRequestState.OPEN;
            this.commits = new ArrayList<>(commits);
        }

        void addReview(Review review) {
            if (state != PullRequestState.OPEN) {
                throw new IllegalStateException("Only open pull requests accept reviews.");
            }
            reviews.add(review);
        }

        void addStatusCheck(StatusCheck check) {
            checks.put(check.name(), check);
        }

        void close() {
            if (state == PullRequestState.MERGED) {
                throw new IllegalStateException("Merged pull requests cannot be closed.");
            }
            state = PullRequestState.CLOSED;
        }

        void reopen() {
            if (state != PullRequestState.CLOSED) {
                throw new IllegalStateException("Only closed pull requests can be reopened.");
            }
            state = PullRequestState.OPEN;
        }

        void markReady() {
            if (!draft) {
                throw new IllegalStateException("Pull request is already ready.");
            }
            draft = false;
            state = PullRequestState.OPEN;
        }
    }

    record MergeEvaluation(boolean eligible, List<String> reasons) {}

    static final class Repository {
        private final String name;
        private final String owner;
        private final Map<String, Branch> branches = new HashMap<>();
        private final Map<Integer, PullRequest> pullRequests = new HashMap<>();
        private final Map<String, BranchProtectionPolicy> policies = new HashMap<>();
        private int nextPullRequestNumber = 1;

        Repository(String name, String owner) {
            this.name = name;
            this.owner = owner;
        }

        void createBranch(String name, boolean protectedBranch) {
            if (branches.containsKey(name)) {
                throw new IllegalArgumentException("Branch already exists.");
            }
            branches.put(name, new Branch(name, protectedBranch));
        }

        void addCommit(String branchName, String sha, String message) {
            Branch branch = requireBranch(branchName);
            String parent = branch.head();

            if (branch.commits.stream().anyMatch(c -> c.sha().equals(sha))) {
                throw new IllegalArgumentException("Duplicate commit SHA.");
            }

            branch.commits.add(new Commit(sha, message, parent));
        }

        void configureProtection(
            String branchName,
            BranchProtectionPolicy policy
        ) {
            Branch branch = requireBranch(branchName);
            branch.protectedBranch = true;
            policies.put(branchName, policy);
        }

        PullRequest createPullRequest(
            String source,
            String target,
            String title,
            String author,
            boolean draft
        ) {
            Branch sourceBranch = requireBranch(source);
            Branch targetBranch = requireBranch(target);

            if (source.equals(target)) {
                throw new IllegalArgumentException("Source and target must differ.");
            }

            PullRequest pr = new PullRequest(
                nextPullRequestNumber++,
                source,
                target,
                title,
                author,
                targetBranch.head(),
                draft,
                sourceBranch.commits
            );

            pullRequests.put(pr.number, pr);
            return pr;
        }

        MergeEvaluation evaluate(PullRequest pr) {
            List<String> reasons = new ArrayList<>();
            Branch source = requireBranch(pr.sourceBranch);
            Branch target = requireBranch(pr.targetBranch);
            BranchProtectionPolicy policy = policies.get(pr.targetBranch);

            if (pr.state != PullRequestState.OPEN) {
                reasons.add("Pull request is not open.");
            }

            if (pr.draft) {
                reasons.add("Pull request is still a draft.");
            }

            if (pr.commits.isEmpty()) {
                reasons.add("Pull request contains no commits.");
            }

            if (policy == null) {
                return new MergeEvaluation(reasons.isEmpty(), List.copyOf(reasons));
            }

            if (!Objects.equals(target.head(), pr.baseHeadAtCreation)) {
                reasons.add("Target branch changed after PR creation.");
            }

            Set<String> approvals = new HashSet<>();
            boolean changesRequested = false;

            for (Review review : pr.reviews) {
                if (review.dismissed()) {
                    continue;
                }

                boolean current =
                    review.commitSha().equals(source.head()) ||
                    review.commitSha().equals(target.head());

                if (!current) {
                    continue;
                }

                if (review.state() == ReviewState.APPROVED) {
                    approvals.add(review.reviewer());
                }

                if (review.state() == ReviewState.CHANGES_REQUESTED) {
                    changesRequested = true;
                }
            }

            if (changesRequested) {
                reasons.add("A current reviewer requested changes.");
            }

            if (approvals.size() < policy.requiredReviews()) {
                reasons.add(
                    "Required approvals: " + policy.requiredReviews() +
                    ", current approvals: " + approvals.size() + "."
                );
            }

            for (String checkName : policy.requiredChecks()) {
                StatusCheck check = pr.checks.get(checkName);

                if (check == null) {
                    reasons.add("Missing status check: " + checkName);
                } else if (!check.passed()) {
                    reasons.add("Failed status check: " + checkName);
                }
            }

            if (policy.requireConversationResolution() &&
                pr.unresolvedConversations > 0) {
                reasons.add("Unresolved review conversations remain.");
            }

            return new MergeEvaluation(reasons.isEmpty(), List.copyOf(reasons));
        }

        void merge(PullRequest pr) {
            MergeEvaluation evaluation = evaluate(pr);

            if (!evaluation.eligible()) {
                throw new IllegalStateException(
                    "Merge rejected: " + String.join(" ", evaluation.reasons())
                );
            }

            Branch target = requireBranch(pr.targetBranch);
            Branch source = requireBranch(pr.sourceBranch);

            if (pr.mergeStrategy == MergeStrategy.SQUASH) {
                target.commits.add(
                    new Commit(
                        "squash-" + pr.number,
                        "Squash: " + pr.title,
                        target.head()
                    )
                );
            } else if (pr.mergeStrategy == MergeStrategy.MERGE_COMMIT) {
                target.commits.add(
                    new Commit(
                        "merge-" + pr.number,
                        "Merge pull request #" + pr.number,
                        target.head()
                    )
                );
            } else {
                for (Commit commit : source.commits) {
                    target.commits.add(
                        new Commit(
                            "rebased-" + commit.sha(),
                            commit.message(),
                            target.head()
                        )
                    );
                }
            }

            pr.state = PullRequestState.MERGED;
        }

        private Branch requireBranch(String name) {
            Branch branch = branches.get(name);
            if (branch == null) {
                throw new IllegalArgumentException("Unknown branch: " + name);
            }
            return branch;
        }
    }

    public static void main(String[] args) {
        Repository repository =
            new Repository("storage-platform", "platform-admin");

        repository.createBranch("main", true);
        repository.createBranch("feature/storage-pages", false);

        repository.addCommit("main", "a001", "Initialize repository");
        repository.addCommit(
            "feature/storage-pages",
            "a001",
            "Initialize repository"
        );
        repository.addCommit(
            "feature/storage-pages",
            "b101",
            "Implement page allocation"
        );
        repository.addCommit(
            "feature/storage-pages",
            "b102",
            "Validate physical storage boundaries"
        );

        repository.configureProtection(
            "main",
            new BranchProtectionPolicy(
                2,
                Set.of("unit-tests", "storage-integrity"),
                true,
                true,
                true,
                false,
                false
            )
        );

        PullRequest pr = repository.createPullRequest(
            "feature/storage-pages",
            "main",
            "Implement physical storage model",
            "developer-1",
            false
        );

        pr.addStatusCheck(
            new StatusCheck(
                "unit-tests",
                true,
                true,
                "All tests passed"
            )
        );

        pr.addStatusCheck(
            new StatusCheck(
                "storage-integrity",
                true,
                true,
                "Storage boundaries validated"
            )
        );

        pr.addReview(
            new Review(
                "reviewer-1",
                ReviewState.APPROVED,
                "b102",
                List.of(
                    new ReviewComment(
                        "reviewer-1",
                        "Allocation logic is bounded."
                    )
                )
            )
        );

        pr.addReview(
            new Review(
                "reviewer-2",
                ReviewState.APPROVED,
                "b102",
                List.of(
                    new ReviewComment(
                        "reviewer-2",
                        "Record validation is explicit."
                    )
                )
            )
        );

        MergeEvaluation evaluation = repository.evaluate(pr);

        System.out.println("Pull Request #" + pr.number);
        System.out.println("Merge eligible: " + evaluation.eligible());

        for (String reason : evaluation.reasons()) {
            System.out.println(" - " + reason);
        }

        if (evaluation.eligible()) {
            repository.merge(pr);
            System.out.println("State: MERGED");
        }
    }
}
