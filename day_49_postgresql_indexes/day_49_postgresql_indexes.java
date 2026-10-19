import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.function.Predicate;
import java.util.stream.Collectors;

/*
 * PostgreSQL Index Governance Service
 *
 * Enterprise scenario:
 * A database platform team maintains an indexing policy for a repository
 * analytics service. Queries are classified by operator semantics, then an
 * index policy determines which PostgreSQL access method is suitable.
 *
 * Java 17 standard library only.
 */

public class PostgreSQLIndexGovernance {

    enum IndexMethod {
        BTREE,
        HASH,
        GIN,
        GIST,
        BRIN,
        SEQUENTIAL_SCAN
    }

    enum PredicateType {
        EQUALITY,
        RANGE,
        ORDERING,
        ARRAY_CONTAINMENT,
        RANGE_OVERLAP
    }

    record QueryRequest(
            String column,
            PredicateType predicateType,
            String description
    ) {
        QueryRequest {
            Objects.requireNonNull(column);
            Objects.requireNonNull(predicateType);
            Objects.requireNonNull(description);
        }
    }

    record IndexPolicy(
            String name,
            IndexMethod method,
            String column,
            Set<PredicateType> supportedPredicates,
            String operationalPurpose
    ) {
        IndexPolicy {
            supportedPredicates = Set.copyOf(supportedPredicates);
        }

        boolean supports(QueryRequest request) {
            return column.equals(request.column())
                    && supportedPredicates.contains(request.predicateType());
        }
    }

    record RepositoryEvent(
            long id,
            long repositoryId,
            Set<String> labels,
            Instant createdAt,
            Instant lifecycleEnd
    ) {
        RepositoryEvent {
            labels = Set.copyOf(labels);

            if (lifecycleEnd.isBefore(createdAt)) {
                throw new IllegalArgumentException(
                        "Lifecycle end cannot precede event creation."
                );
            }
        }
    }

    static final class InvalidQueryException extends RuntimeException {
        InvalidQueryException(String message) {
            super(message);
        }
    }

    static final class IndexSelectionService {
        private final List<IndexPolicy> policies;

        IndexSelectionService(List<IndexPolicy> policies) {
            this.policies = List.copyOf(policies);
        }

        IndexPolicy select(QueryRequest request) {
            List<IndexPolicy> candidates = policies.stream()
                    .filter(policy -> policy.supports(request))
                    .toList();

            if (candidates.isEmpty()) {
                return new IndexPolicy(
                        "none",
                        IndexMethod.SEQUENTIAL_SCAN,
                        request.column(),
                        Set.of(),
                        "No configured access method supports this predicate."
                );
            }

            /*
             * Equality can be handled by both B-tree and Hash. The service
             * prefers B-tree because it also supports ordering and ranges,
             * reducing the need for a narrow index when both workloads exist.
             */
            if (request.predicateType() == PredicateType.EQUALITY) {
                return candidates.stream()
                        .filter(policy -> policy.method() == IndexMethod.BTREE)
                        .findFirst()
                        .orElse(candidates.getFirst());
            }

            return candidates.getFirst();
        }
    }

    static final class RepositoryQueryService {
        private final List<RepositoryEvent> events;

        RepositoryQueryService(List<RepositoryEvent> events) {
            this.events = List.copyOf(events);
        }

        List<RepositoryEvent> execute(QueryRequest request) {
            return switch (request.predicateType()) {
                case EQUALITY -> equality(request);
                case ARRAY_CONTAINMENT -> labelContainment(request);
                case RANGE -> creationRange(request);
                case RANGE_OVERLAP -> lifecycleOverlap(request);
                case ORDERING -> orderedByCreation();
            };
        }

        private List<RepositoryEvent> equality(QueryRequest request) {
            if (!request.column().equals("repository_id")) {
                throw new InvalidQueryException(
                        "Equality implementation expects repository_id."
                );
            }

            return events.stream()
                    .filter(event -> event.repositoryId() == 102)
                    .toList();
        }

        private List<RepositoryEvent> labelContainment(QueryRequest request) {
            if (!request.column().equals("labels")) {
                throw new InvalidQueryException(
                        "Containment implementation expects labels."
                );
            }

            return events.stream()
                    .filter(event ->
                            event.labels().contains("postgresql")
                                    && event.labels().contains("security"))
                    .toList();
        }

        private List<RepositoryEvent> creationRange(QueryRequest request) {
            if (!request.column().equals("created_at")) {
                throw new InvalidQueryException(
                        "Range implementation expects created_at."
                );
            }

            Instant lower = Instant.parse("2026-02-01T00:00:00Z");
            Instant upper = Instant.parse("2026-03-01T00:00:00Z");

            return events.stream()
                    .filter(event ->
                            !event.createdAt().isBefore(lower)
                                    && !event.createdAt().isAfter(upper))
                    .toList();
        }

        private List<RepositoryEvent> lifecycleOverlap(QueryRequest request) {
            if (!request.column().equals("lifecycle")) {
                throw new InvalidQueryException(
                        "Overlap implementation expects lifecycle."
                );
            }

            Instant lower = Instant.parse("2026-02-10T00:00:00Z");
            Instant upper = Instant.parse("2026-02-18T00:00:00Z");

            return events.stream()
                    .filter(event ->
                            !event.createdAt().isAfter(upper)
                                    && !event.lifecycleEnd().isBefore(lower))
                    .toList();
        }

        private List<RepositoryEvent> orderedByCreation() {
            return events.stream()
                    .sorted(java.util.Comparator.comparing(RepositoryEvent::createdAt))
                    .toList();
        }
    }

    private static List<IndexPolicy> policies() {
        return List.of(
                new IndexPolicy(
                        "idx_repository_btree",
                        IndexMethod.BTREE,
                        "repository_id",
                        EnumSet.of(
                                PredicateType.EQUALITY,
                                PredicateType.RANGE,
                                PredicateType.ORDERING
                        ),
                        "General-purpose equality, ordering, and range access."
                ),
                new IndexPolicy(
                        "idx_repository_hash",
                        IndexMethod.HASH,
                        "repository_id",
                        EnumSet.of(PredicateType.EQUALITY),
                        "Equality-oriented access without ordering semantics."
                ),
                new IndexPolicy(
                        "idx_labels_gin",
                        IndexMethod.GIN,
                        "labels",
                        EnumSet.of(PredicateType.ARRAY_CONTAINMENT),
                        "Inverted membership lookup for collection values."
                ),
                new IndexPolicy(
                        "idx_lifecycle_gist",
                        IndexMethod.GIST,
                        "lifecycle",
                        EnumSet.of(PredicateType.RANGE_OVERLAP),
                        "Range overlap and other operator-class-defined searches."
                ),
                new IndexPolicy(
                        "idx_created_brin",
                        IndexMethod.BRIN,
                        "created_at",
                        EnumSet.of(PredicateType.RANGE),
                        "Compact block summaries for physically correlated timestamps."
                )
        );
    }

    private static List<RepositoryEvent> sampleEvents() {
        Instant base = Instant.parse("2026-01-05T10:00:00Z");

        return List.of(
                new RepositoryEvent(
                        1,
                        101,
                        Set.of("database", "postgresql"),
                        base,
                        base.plus(2, ChronoUnit.DAYS)
                ),
                new RepositoryEvent(
                        2,
                        102,
                        Set.of("security", "postgresql"),
                        base.plus(20, ChronoUnit.DAYS),
                        base.plus(28, ChronoUnit.DAYS)
                ),
                new RepositoryEvent(
                        3,
                        102,
                        Set.of("performance", "gin"),
                        base.plus(35, ChronoUnit.DAYS),
                        base.plus(40, ChronoUnit.DAYS)
                ),
                new RepositoryEvent(
                        4,
                        103,
                        Set.of("release", "performance"),
                        base.plus(48, ChronoUnit.DAYS),
                        base.plus(50, ChronoUnit.DAYS)
                ),
                new RepositoryEvent(
                        5,
                        101,
                        Set.of("audit", "security"),
                        base.plus(60, ChronoUnit.DAYS),
                        base.plus(66, ChronoUnit.DAYS)
                )
        );
    }

    private static void printPolicy(IndexPolicy policy) {
        System.out.printf(
                "  %-24s %-18s %s%n",
                policy.name(),
                policy.method(),
                policy.operationalPurpose()
        );
    }

    public static void main(String[] args) {
        System.out.println("PostgreSQL Index Governance Service");

        List<IndexPolicy> policies = policies();
        IndexSelectionService selector = new IndexSelectionService(policies);
        RepositoryQueryService queryService =
                new RepositoryQueryService(sampleEvents());

        System.out.println("\nConfigured index policies");
        policies.forEach(PostgreSQLIndexGovernance::printPolicy);

        List<QueryRequest> requests = List.of(
                new QueryRequest(
                        "repository_id",
                        PredicateType.EQUALITY,
                        "Locate events for one repository"
                ),
                new QueryRequest(
                        "labels",
                        PredicateType.ARRAY_CONTAINMENT,
                        "Find events tagged with PostgreSQL and security"
                ),
                new QueryRequest(
                        "lifecycle",
                        PredicateType.RANGE_OVERLAP,
                        "Find events overlapping a maintenance interval"
                ),
                new QueryRequest(
                        "created_at",
                        PredicateType.RANGE,
                        "Find events in a creation-time interval"
                ),
                new QueryRequest(
                        "created_at",
                        PredicateType.ORDERING,
                        "Read events in creation order"
                )
        );

        System.out.println("\nPolicy evaluation");

        for (QueryRequest request : requests) {
            IndexPolicy selected = selector.select(request);
            List<RepositoryEvent> result = queryService.execute(request);

            System.out.println("\n" + request.description());
            System.out.println("Column: " + request.column());
            System.out.println("Predicate: " + request.predicateType());
            System.out.println("Selected access method: " + selected.method());
            System.out.println("Rows matched: " + result.size());

            String ids = result.stream()
                    .map(event -> Long.toString(event.id()))
                    .collect(Collectors.joining(", "));

            System.out.println("Event IDs: " + (ids.isBlank() ? "(none)" : ids));
        }

        System.out.println("\nEnterprise design observations");
        System.out.println(
                "B-tree is treated as the broad default when equality and ordered access coexist."
        );
        System.out.println(
                "Hash remains a specialized equality structure rather than a replacement for B-tree."
        );
        System.out.println(
                "GIN handles membership/containment semantics for multi-valued attributes."
        );
        System.out.println(
                "GiST handles range relationships through PostgreSQL operator classes."
        );
        System.out.println(
                "BRIN is selected for large, physically correlated time-series style data."
        );
        System.out.println(
                "The PostgreSQL planner can still reject an applicable index when a sequential scan has lower estimated cost."
        );

        try {
            QueryRequest invalid = new QueryRequest(
                    "labels",
                    PredicateType.EQUALITY,
                    "Unsupported equality semantics for labels"
            );

            IndexPolicy policy = selector.select(invalid);

            if (policy.method() == IndexMethod.SEQUENTIAL_SCAN) {
                throw new InvalidQueryException(
                        "No configured equality index policy exists for labels."
                );
            }
        } catch (InvalidQueryException exception) {
            System.out.println(
                    "\nValidation failure handled explicitly: "
                            + exception.getMessage()
            );
        }
    }
}
