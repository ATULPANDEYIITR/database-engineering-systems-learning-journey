import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * Enterprise-oriented model of PostgreSQL view semantics.
 *
 * The domain separates:
 * - repository source records,
 * - dynamically evaluated reporting projections,
 * - explicitly refreshed materialized reporting snapshots.
 *
 * Java records provide immutable domain values, while the repository service
 * controls mutation and validation.
 */
public class ViewReportingEnterpriseDemo {

    enum PullRequestState {
        OPEN,
        MERGED,
        CLOSED
    }

    enum ReviewState {
        APPROVED,
        CHANGES_REQUESTED,
        COMMENTED
    }

    record Repository(String name, String ownerTeam, boolean active) {
        Repository {
            requireText(name, "Repository name");
            requireText(ownerTeam, "Owner team");
        }
    }

    record PullRequest(
        int number,
        String repository,
        String author,
        PullRequestState state,
        int additions,
        int deletions,
        Instant mergedAt
    ) {
        PullRequest {
            if (number <= 0) {
                throw new IllegalArgumentException(
                    "Pull request number must be positive"
                );
            }

            requireText(repository, "Repository");
            requireText(author, "Author");
            Objects.requireNonNull(state, "State");

            if (additions < 0 || deletions < 0) {
                throw new IllegalArgumentException(
                    "Change counts cannot be negative"
                );
            }

            if (state == PullRequestState.MERGED && mergedAt == null) {
                throw new IllegalArgumentException(
                    "Merged pull requests require mergedAt"
                );
            }
        }
    }

    record Review(
        int pullRequest,
        String reviewer,
        ReviewState state
    ) {
        Review {
            if (pullRequest <= 0) {
                throw new IllegalArgumentException(
                    "Pull request number must be positive"
                );
            }

            requireText(reviewer, "Reviewer");
            Objects.requireNonNull(state, "Review state");
        }
    }

    record RepositoryReport(
        String repository,
        String ownerTeam,
        long pullRequests,
        long mergedPullRequests,
        long totalChanges,
        double averageChangeSize
    ) {}

    static final class RepositoryService {
        private final Map<String, Repository> repositories = new HashMap<>();
        private final List<PullRequest> pullRequests = new ArrayList<>();
        private final List<Review> reviews = new ArrayList<>();

        void addRepository(Repository repository) {
            Objects.requireNonNull(repository);

            if (repositories.putIfAbsent(
                repository.name(),
                repository
            ) != null) {
                throw new IllegalArgumentException(
                    "Repository already exists: " + repository.name()
                );
            }
        }

        void addPullRequest(PullRequest pullRequest) {
            Objects.requireNonNull(pullRequest);

            if (!repositories.containsKey(pullRequest.repository())) {
                throw new IllegalArgumentException(
                    "Unknown repository: " + pullRequest.repository()
                );
            }

            if (pullRequests.stream()
                .anyMatch(pr -> pr.number() == pullRequest.number())) {
                throw new IllegalArgumentException(
                    "Duplicate pull request number"
                );
            }

            pullRequests.add(pullRequest);
        }

        void addReview(Review review) {
            Objects.requireNonNull(review);

            if (pullRequests.stream()
                .noneMatch(pr -> pr.number() == review.pullRequest())) {
                throw new IllegalArgumentException(
                    "Review references unknown pull request"
                );
            }

            reviews.add(review);
        }

        /*
         * Dynamic view equivalent.
         *
         * The result is reconstructed from current source state. No cached
         * result is retained by this method.
         */
        List<RepositoryReport> repositoryActivityView() {
            List<RepositoryReport> result = new ArrayList<>();

            for (Repository repository : repositories.values()) {
                List<PullRequest> repositoryPRs = pullRequests.stream()
                    .filter(pr ->
                        pr.repository().equals(repository.name()))
                    .toList();

                long merged = repositoryPRs.stream()
                    .filter(pr -> pr.state() == PullRequestState.MERGED)
                    .count();

                long totalChanges = repositoryPRs.stream()
                    .mapToLong(pr -> pr.additions() + pr.deletions())
                    .sum();

                double average = repositoryPRs.isEmpty()
                    ? 0.0
                    : (double) totalChanges / repositoryPRs.size();

                result.add(new RepositoryReport(
                    repository.name(),
                    repository.ownerTeam(),
                    repositoryPRs.size(),
                    merged,
                    totalChanges,
                    average
                ));
            }

            return Collections.unmodifiableList(result);
        }

        /*
         * A separate review projection prevents review decisions from being
         * confused with repository activity metrics.
         */
        Map<Integer, Map<ReviewState, Long>> reviewView() {
            Map<Integer, Map<ReviewState, Long>> result = new HashMap<>();

            for (Review review : reviews) {
                result.computeIfAbsent(
                    review.pullRequest(),
                    ignored -> new HashMap<>()
                ).merge(
                    review.state(),
                    1L,
                    Long::sum
                );
            }

            return result;
        }
    }

    static final class MaterializedReportService {
        private final RepositoryService source;
        private List<RepositoryReport> snapshot = List.of();
        private Instant refreshedAt;

        MaterializedReportService(RepositoryService source) {
            this.source = Objects.requireNonNull(source);
        }

        synchronized void refresh() {
            /*
             * Replacing the immutable snapshot gives readers a stable result
             * while refresh work is performed. A database implementation can
             * use PostgreSQL's materialized-view refresh semantics.
             */
            List<RepositoryReport> newSnapshot =
                source.repositoryActivityView();

            snapshot = List.copyOf(newSnapshot);
            refreshedAt = Instant.now();
        }

        synchronized List<RepositoryReport> read() {
            return snapshot;
        }

        synchronized Instant refreshedAt() {
            return refreshedAt;
        }
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(
                field + " must not be blank"
            );
        }
    }

    private static void printReports(
        String title,
        List<RepositoryReport> reports
    ) {
        System.out.println("\n" + title);
        System.out.println(
            "Repository | Team | PRs | Merged | Changes | Average"
        );

        for (RepositoryReport report : reports) {
            System.out.printf(
                "%s | %s | %d | %d | %d | %.2f%n",
                report.repository(),
                report.ownerTeam(),
                report.pullRequests(),
                report.mergedPullRequests(),
                report.totalChanges(),
                report.averageChangeSize()
            );
        }
    }

    public static void main(String[] args) {
        RepositoryService service = new RepositoryService();

        service.addRepository(
            new Repository("payments-api", "platform", true)
        );
        service.addRepository(
            new Repository("customer-portal", "web", true)
        );

        Instant now = Instant.now();

        service.addPullRequest(new PullRequest(
            101,
            "payments-api",
            "alice",
            PullRequestState.MERGED,
            180,
            42,
            now
        ));

        service.addPullRequest(new PullRequest(
            102,
            "payments-api",
            "bob",
            PullRequestState.OPEN,
            80,
            15,
            null
        ));

        service.addPullRequest(new PullRequest(
            201,
            "customer-portal",
            "carol",
            PullRequestState.MERGED,
            300,
            90,
            now
        ));

        service.addReview(
            new Review(101, "reviewer-a", ReviewState.APPROVED)
        );
        service.addReview(
            new Review(102, "reviewer-b", ReviewState.CHANGES_REQUESTED)
        );
        service.addReview(
            new Review(201, "reviewer-c", ReviewState.APPROVED)
        );

        printReports(
            "Dynamic repository view",
            service.repositoryActivityView()
        );

        MaterializedReportService report =
            new MaterializedReportService(service);

        report.refresh();

        printReports(
            "Materialized report",
            report.read()
        );

        System.out.println(
            "Materialized at: " + report.refreshedAt()
        );

        /*
         * The new row immediately affects a dynamic view but not the stored
         * materialized snapshot.
         */
        service.addPullRequest(new PullRequest(
            103,
            "payments-api",
            "diana",
            PullRequestState.MERGED,
            45,
            10,
            Instant.now()
        ));

        printReports(
            "Dynamic view after source change",
            service.repositoryActivityView()
        );

        printReports(
            "Materialized report before refresh",
            report.read()
        );

        report.refresh();

        printReports(
            "Materialized report after refresh",
            report.read()
        );

        System.out.println("\nReview projection:");
        service.reviewView().forEach(
            (pullRequest, states) ->
                System.out.println(
                    "PR #" + pullRequest + " -> " + states
                )
        );

        System.out.println(
            "\nDesign trade-off: dynamic views prioritize freshness; "
            + "materialized views prioritize repeated read performance "
            + "when controlled staleness is acceptable."
        );
    }
}
