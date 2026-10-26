import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.function.Predicate;
import java.util.stream.Collectors;

public class PostgresArrayGovernance {

    enum ReviewState {
        PENDING,
        APPROVED,
        CHANGES_REQUESTED,
        DISMISSED
    }

    enum CheckState {
        PASS,
        FAIL,
        PENDING
    }

    record StatusCheck(String name, CheckState state) {
        StatusCheck {
            Objects.requireNonNull(name);
            Objects.requireNonNull(state);

            if (name.isBlank()) {
                throw new IllegalArgumentException("check name cannot be blank");
            }
        }
    }

    record Review(
            String reviewer,
            ReviewState state,
            List<String> comments
    ) {
        Review {
            Objects.requireNonNull(reviewer);
            Objects.requireNonNull(state);
            Objects.requireNonNull(comments);

            if (reviewer.isBlank()) {
                throw new IllegalArgumentException("reviewer cannot be blank");
            }

            comments = List.copyOf(comments);
        }
    }

    record PullRequest(
            long id,
            String sourceBranch,
            String targetBranch,
            List<String> commits,
            List<String> labels,
            List<Review> reviews,
            List<StatusCheck> checks
    ) {
        PullRequest {
            if (id <= 0) {
                throw new IllegalArgumentException("id must be positive");
            }

            if (sourceBranch.isBlank() || targetBranch.isBlank()) {
                throw new IllegalArgumentException("branches are required");
            }

            commits = List.copyOf(commits);
            labels = normalize(labels);
            reviews = List.copyOf(reviews);
            checks = List.copyOf(checks);
        }
    }

    static final class ArrayOperations {

        private ArrayOperations() {
        }

        static List<String> normalize(List<String> values) {
            Objects.requireNonNull(values);

            return values.stream()
                    .filter(Objects::nonNull)
                    .map(String::trim)
                    .filter(value -> !value.isEmpty())
                    .map(String::toLowerCase)
                    .distinct()
                    .toList();
        }

        static List<String> appendUnique(
                List<String> values,
                String value
        ) {
            if (value == null || value.isBlank()) {
                throw new IllegalArgumentException(
                        "array element cannot be blank"
                );
            }

            List<String> result = new ArrayList<>(values);

            if (!result.contains(value)) {
                result.add(value);
            }

            return List.copyOf(result);
        }

        static List<String> difference(
                List<String> left,
                List<String> right
        ) {
            Set<String> rightSet = new LinkedHashSet<>(right);

            return left.stream()
                    .filter(value -> !rightSet.contains(value))
                    .toList();
        }

        static List<String> intersection(
                List<String> left,
                List<String> right
        ) {
            Set<String> rightSet = new LinkedHashSet<>(right);

            return left.stream()
                    .filter(rightSet::contains)
                    .distinct()
                    .toList();
        }

        static boolean containsAll(
                List<String> values,
                List<String> required
        ) {
            Set<String> available = new LinkedHashSet<>(values);
            return available.containsAll(required);
        }

        static List<Map.Entry<Integer, String>> unnest(
                List<String> values
        ) {
            List<Map.Entry<Integer, String>> result = new ArrayList<>();

            for (int i = 0; i < values.size(); i++) {
                // PostgreSQL-style presentation uses a 1-based position.
                result.add(Map.entry(i + 1, values.get(i)));
            }

            return List.copyOf(result);
        }

        static List<String> filter(
                List<String> values,
                Predicate<String> predicate
        ) {
            return values.stream()
                    .filter(predicate)
                    .toList();
        }
    }

    static final class MergeEligibilityService {

        boolean isEligible(PullRequest pullRequest) {
            boolean requiredChecksPassed = pullRequest.checks().stream()
                    .allMatch(check -> check.state() == CheckState.PASS);

            if (!requiredChecksPassed) {
                return false;
            }

            boolean hasApproval = pullRequest.reviews().stream()
                    .anyMatch(review -> review.state() == ReviewState.APPROVED);

            boolean hasBlockingReview = pullRequest.reviews().stream()
                    .anyMatch(review ->
                            review.state() == ReviewState.CHANGES_REQUESTED
                    );

            boolean hasGovernanceLabels = ArrayOperations.containsAll(
                    pullRequest.labels(),
                    List.of("reviewed", "security")
            );

            return hasApproval && !hasBlockingReview && hasGovernanceLabels;
        }
    }

    static void print(String label, List<?> values) {
        System.out.println(label + ": " + values);
    }

    public static void main(String[] args) {
        List<String> labels = List.of(
                "Database",
                "PostgreSQL",
                "Reviewed",
                "Security",
                "Database"
        );

        List<String> normalized = ArrayOperations.normalize(labels);

        print("Normalized", normalized);
        print(
                "Difference",
                ArrayOperations.difference(
                        normalized,
                        List.of("postgresql")
                )
        );
        print(
                "Intersection",
                ArrayOperations.intersection(
                        normalized,
                        List.of("database", "security", "cloud")
                )
        );
        print(
                "Append unique",
                ArrayOperations.appendUnique(normalized, "arrays")
        );
        print(
                "Unnested",
                ArrayOperations.unnest(normalized)
        );

        Review approvedReview = new Review(
                "reviewer-1",
                ReviewState.APPROVED,
                List.of("Array constraints verified")
        );

        PullRequest pullRequest = new PullRequest(
                9001,
                "feature/array-support",
                "main",
                List.of("c101", "c102", "c103"),
                normalized,
                List.of(approvedReview),
                List.of(
                        new StatusCheck("compile", CheckState.PASS),
                        new StatusCheck("tests", CheckState.PASS),
                        new StatusCheck("security", CheckState.PASS)
                )
        );

        MergeEligibilityService service =
                new MergeEligibilityService();

        System.out.println(
                "Merge eligible: " + service.isEligible(pullRequest)
        );

        PullRequest failedPullRequest = new PullRequest(
                pullRequest.id(),
                pullRequest.sourceBranch(),
                pullRequest.targetBranch(),
                pullRequest.commits(),
                pullRequest.labels(),
                List.of(
                        new Review(
                                "reviewer-1",
                                ReviewState.CHANGES_REQUESTED,
                                List.of("Missing array validation")
                        )
                ),
                pullRequest.checks()
        );

        System.out.println(
                "Merge eligible after requested changes: "
                        + service.isEligible(failedPullRequest)
        );

        List<String> productionTags = ArrayOperations.filter(
                normalized,
                value -> value.equals("security")
                        || value.equals("postgresql")
        );

        print("Policy-selected tags", productionTags);

        /*
         * Immutable List.copyOf prevents callers from silently changing
         * domain state after validation. This is useful when an array-like
         * collection represents a business decision rather than temporary data.
         */
    }
}
