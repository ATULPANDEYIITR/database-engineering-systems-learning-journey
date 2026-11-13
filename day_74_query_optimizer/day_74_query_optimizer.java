/*
 * Query Optimizer: Cost Estimation, Statistics and Plan Selection
 *
 * Java 17
 *
 * Enterprise-oriented implementation:
 * - Immutable domain records
 * - Statistics repository interface
 * - Column and index statistics
 * - Cardinality estimation service
 * - Predicate validation
 * - Access-path selection
 * - Join algorithm policies
 * - Dynamic-programming join enumeration
 * - Statistics freshness monitoring
 * - Explicit optimization exceptions
 *
 * Compile:
 * javac QueryOptimizer.java
 *
 * Run:
 * java QueryOptimizer
 */

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.TreeMap;

// ============================================================
// 1. APPLICATION ENTRY POINT
// ============================================================

public class QueryOptimizer {

    public static void main(String[] args) {

        try {

            StatisticsRepository repository =
                SampleStatistics.create();

            CostPolicy costPolicy = new CostPolicy(
                1.0,
                4.0,
                0.01,
                0.0025,
                0.015,
                0.005,
                0.75
            );

            CardinalityService cardinality =
                new CardinalityService(repository);

            AccessPathService accessPaths =
                new AccessPathService(
                    repository,
                    cardinality,
                    costPolicy
                );

            JoinPlanningService joinPlanning =
                new JoinPlanningService(
                    repository,
                    costPolicy
                );

            OptimizationService optimization =
                new OptimizationService(
                    repository,
                    accessPaths,
                    joinPlanning
                );

            runTests(repository, cardinality, accessPaths);

            Query query = new Query(
                List.of(
                    "customers",
                    "orders",
                    "payments"
                ),
                Map.of(
                    "customers",
                    List.of(
                        new Predicate(
                            "region",
                            Operator.EQUAL,
                            "North",
                            null
                        )
                    ),
                    "orders",
                    List.of(
                        new Predicate(
                            "status",
                            Operator.EQUAL,
                            "COMPLETED",
                            null
                        ),
                        new Predicate(
                            "amount",
                            Operator.BETWEEN,
                            "100",
                            1000.0
                        )
                    ),
                    "payments",
                    List.of(
                        new Predicate(
                            "payment_status",
                            Operator.EQUAL,
                            "SUCCESS",
                            null
                        )
                    )
                ),
                List.of(
                    new JoinCondition(
                        "customers",
                        "customer_id",
                        "orders",
                        "customer_id"
                    ),
                    new JoinCondition(
                        "orders",
                        "order_id",
                        "payments",
                        "order_id"
                    )
                )
            );

            System.out.println("\nQUERY OPTIMIZATION REPORT");
            System.out.println("=========================");

            for (String relationName : query.relations()) {

                RelationStats stats =
                    repository.get(relationName);

                List<Predicate> predicates =
                    query.predicates().getOrDefault(
                        relationName,
                        List.of()
                    );

                List<Plan> candidates =
                    accessPaths.evaluate(
                        relationName,
                        predicates
                    );

                System.out.println("\nRelation: " + relationName);
                System.out.println("Base rows: " + stats.rows());
                System.out.printf(
                    "Estimated rows: %.2f%n",
                    candidates.get(0).rows()
                );

                for (Plan plan : candidates) {
                    System.out.printf(
                        "  %s: cost=%.3f%n",
                        plan.operation(),
                        plan.cost()
                    );
                }

                if (!repository.isFresh(
                    relationName,
                    Duration.ofHours(24)
                )) {
                    System.out.println(
                        "[WARNING] Statistics may be stale."
                    );
                }
            }

            Plan selected = optimization.optimize(query);

            System.out.println("\nSELECTED EXECUTION PLAN");
            System.out.println("=======================");
            System.out.println(selected.explain());

            System.out.printf(
                "%nTotal estimated cost: %.3f%n",
                selected.cost()
            );

            System.out.printf(
                "Estimated output rows: %.2f%n",
                selected.rows()
            );

        } catch (OptimizationException exception) {
            System.err.println(
                "[OPTIMIZATION ERROR] " + exception.getMessage()
            );
            System.exit(1);
        }
    }

    private static void runTests(
        StatisticsRepository repository,
        CardinalityService cardinality,
        AccessPathService accessPaths
    ) {

        double north = cardinality.selectivity(
            "customers",
            new Predicate(
                "region",
                Operator.EQUAL,
                "North",
                null
            )
        );

        if (Math.abs(north - 0.35) > 1e-9) {
            throw new OptimizationException(
                "MCV estimation test failed."
            );
        }

        double rows = cardinality.filteredRows(
            "customers",
            List.of(
                new Predicate(
                    "region",
                    Operator.EQUAL,
                    "North",
                    null
                )
            )
        );

        if (Math.abs(rows - 35000) > 1e-9) {
            throw new OptimizationException(
                "Filtered cardinality test failed."
            );
        }

        List<Plan> plans = accessPaths.evaluate(
            "orders",
            List.of(
                new Predicate(
                    "status",
                    Operator.EQUAL,
                    "COMPLETED",
                    null
                )
            )
        );

        if (plans.size() < 2) {
            throw new OptimizationException(
                "Expected sequential and index scan alternatives."
            );
        }

        if (repository.get("orders").rows() <= 0) {
            throw new OptimizationException(
                "Invalid relation row count."
            );
        }

        System.out.println("[TEST] All tests passed.");
    }
}

// ============================================================
// 2. EXCEPTIONS
// ============================================================

class OptimizationException extends RuntimeException {

    public OptimizationException(String message) {
        super(message);
    }

    public OptimizationException(
        String message,
        Throwable cause
    ) {
        super(message, cause);
    }
}

// ============================================================
// 3. ENUMS
// ============================================================

enum Operator {
    EQUAL,
    LESS_THAN,
    GREATER_THAN,
    BETWEEN
}

enum ScanAlgorithm {
    SEQUENTIAL,
    INDEX
}

enum JoinAlgorithm {
    HASH,
    NESTED_LOOP
}

// ============================================================
// 4. IMMUTABLE DOMAIN RECORDS
// ============================================================

record CostPolicy(
    double sequentialPage,
    double randomPage,
    double tuple,
    double operation,
    double hashBuild,
    double nestedLoop,
    double cacheDiscount
) {

    CostPolicy {
        double[] values = {
            sequentialPage,
            randomPage,
            tuple,
            operation,
            hashBuild,
            nestedLoop,
            cacheDiscount
        };

        for (double value : values) {
            if (!Double.isFinite(value) || value <= 0) {
                throw new OptimizationException(
                    "Invalid cost configuration."
                );
            }
        }

        if (cacheDiscount > 1) {
            throw new OptimizationException(
                "Cache discount cannot exceed one."
            );
        }
    }
}

record Histogram(List<Double> boundaries) {

    Histogram {
        boundaries = List.copyOf(boundaries);

        if (boundaries.size() < 2) {
            throw new OptimizationException(
                "Histogram requires at least two boundaries."
            );
        }

        for (int i = 0; i < boundaries.size(); i++) {

            double value = boundaries.get(i);

            if (!Double.isFinite(value)) {
                throw new OptimizationException(
                    "Invalid histogram boundary."
                );
            }

            if (
                i > 0 &&
                value <= boundaries.get(i - 1)
            ) {
                throw new OptimizationException(
                    "Histogram boundaries must increase."
                );
            }
        }
    }

    double estimate(double low, double high) {

        if (low > high) {
            throw new OptimizationException(
                "Invalid histogram range."
            );
        }

        double minimum = boundaries.get(0);
        double maximum = boundaries.get(
            boundaries.size() - 1
        );

        if (high <= minimum || low >= maximum) {
            return 0.0;
        }

        double overlap = Math.max(
            0.0,
            Math.min(high, maximum) - Math.max(low, minimum)
        );

        return overlap / (maximum - minimum);
    }
}

record ColumnStats(
    String name,
    long distinctValues,
    double nullFraction,
    Map<String, Double> mostCommonValues,
    Optional<Histogram> histogram
) {

    ColumnStats {

        Objects.requireNonNull(name);
        Objects.requireNonNull(mostCommonValues);
        Objects.requireNonNull(histogram);

        if (name.isBlank() || distinctValues < 1) {
            throw new OptimizationException(
                "Invalid column statistics."
            );
        }

        if (
            !Double.isFinite(nullFraction) ||
            nullFraction < 0 ||
            nullFraction > 1
        ) {
            throw new OptimizationException(
                "Invalid null fraction."
            );
        }

        Map<String, Double> copied = Map.copyOf(
            mostCommonValues
        );

        double total = copied.values()
            .stream()
            .mapToDouble(Double::doubleValue)
            .sum();

        if (total > 1.0 + 1e-9) {
            throw new OptimizationException(
                "MCV frequencies exceed one."
            );
        }

        for (double frequency : copied.values()) {
            if (
                !Double.isFinite(frequency) ||
                frequency < 0 ||
                frequency > 1
            ) {
                throw new OptimizationException(
                    "Invalid MCV frequency."
                );
            }
        }

        mostCommonValues = copied;
    }
}

record IndexStats(
    String column,
    long pages,
    boolean unique,
    boolean indexOnly
) {

    IndexStats {
        if (
            column == null ||
            column.isBlank() ||
            pages < 1
        ) {
            throw new OptimizationException(
                "Invalid index statistics."
            );
        }
    }
}

record RelationStats(
    String name,
    double rows,
    long pages,
    Map<String, ColumnStats> columns,
    Map<String, IndexStats> indexes,
    Instant analyzedAt
) {

    RelationStats {

        Objects.requireNonNull(name);
        Objects.requireNonNull(columns);
        Objects.requireNonNull(indexes);
        Objects.requireNonNull(analyzedAt);

        if (
            name.isBlank() ||
            !Double.isFinite(rows) ||
            rows < 0 ||
            pages < 0
        ) {
            throw new OptimizationException(
                "Invalid relation statistics."
            );
        }

        if (rows > 0 && pages == 0) {
            throw new OptimizationException(
                "Nonempty relation requires pages."
            );
        }

        columns = Map.copyOf(columns);
        indexes = Map.copyOf(indexes);

        for (var entry : columns.entrySet()) {
            if (!entry.getKey().equals(entry.getValue().name())) {
                throw new OptimizationException(
                    "Column mapping mismatch."
                );
            }
        }

        for (var entry : indexes.entrySet()) {
            if (
                !entry.getKey().equals(entry.getValue().column()) ||
                !columns.containsKey(entry.getKey())
            ) {
                throw new OptimizationException(
                    "Invalid index mapping."
                );
            }
        }
    }
}

record Predicate(
    String column,
    Operator operator,
    String value,
    Double upper
) {
    Predicate {
        Objects.requireNonNull(column);
        Objects.requireNonNull(operator);

        if (column.isBlank()) {
            throw new OptimizationException(
                "Predicate column is empty."
            );
        }

        if (
            operator == Operator.BETWEEN &&
            upper == null
        ) {
            throw new OptimizationException(
                "Range predicate requires upper boundary."
            );
        }
    }
}

record JoinCondition(
    String leftRelation,
    String leftColumn,
    String rightRelation,
    String rightColumn
) {
    JoinCondition {
        Objects.requireNonNull(leftRelation);
        Objects.requireNonNull(leftColumn);
        Objects.requireNonNull(rightRelation);
        Objects.requireNonNull(rightColumn);

        if (
            leftRelation.equals(rightRelation) ||
            leftColumn.isBlank() ||
            rightColumn.isBlank()
        ) {
            throw new OptimizationException(
                "Invalid join definition."
            );
        }
    }
}

record Query(
    List<String> relations,
    Map<String, List<Predicate>> predicates,
    List<JoinCondition> joins
) {
    Query {
        relations = List.copyOf(relations);

        Map<String, List<Predicate>> copied =
            new HashMap<>();

        predicates.forEach(
            (relation, values) ->
                copied.put(relation, List.copyOf(values))
        );

        predicates = Map.copyOf(copied);
        joins = List.copyOf(joins);
    }
}

// ============================================================
// 5. EXECUTION PLAN
// ============================================================

record Plan(
    String operation,
    double cost,
    double rows,
    String details,
    List<Plan> children
) {

    Plan {
        if (
            operation == null ||
            !Double.isFinite(cost) ||
            cost < 0 ||
            !Double.isFinite(rows) ||
            rows < 0
        ) {
            throw new OptimizationException(
                "Invalid execution plan."
            );
        }

        details = details == null ? "" : details;
        children = List.copyOf(children);
    }

    String explain() {
        return explain(0);
    }

    private String explain(int depth) {

        String indentation = "  ".repeat(depth);

        StringBuilder output = new StringBuilder();

        output.append(indentation)
            .append(operation)
            .append(" (cost=")
            .append(String.format("%.3f", cost))
            .append(", rows=")
            .append(String.format("%.2f", rows))
            .append(")");

        if (!details.isBlank()) {
            output.append("\n")
                .append(indentation)
                .append("  ")
                .append(details);
        }

        for (Plan child : children) {
            output.append("\n")
                .append(child.explain(depth + 1));
        }

        return output.toString();
    }
}

// ============================================================
// 6. STATISTICS REPOSITORY
// ============================================================

interface StatisticsRepository {

    RelationStats get(String relation);

    boolean isFresh(String relation, Duration maximumAge);
}

class InMemoryStatisticsRepository
    implements StatisticsRepository {

    private final Map<String, RelationStats> relations =
        new HashMap<>();

    public void register(RelationStats statistics) {

        if (relations.containsKey(statistics.name())) {
            throw new OptimizationException(
                "Duplicate relation: " + statistics.name()
            );
        }

        relations.put(statistics.name(), statistics);
    }

    @Override
    public RelationStats get(String relation) {

        RelationStats statistics = relations.get(relation);

        if (statistics == null) {
            throw new OptimizationException(
                "Statistics not found: " + relation
            );
        }

        return statistics;
    }

    @Override
    public boolean isFresh(
        String relation,
        Duration maximumAge
    ) {
        return Duration.between(
            get(relation).analyzedAt(),
            Instant.now()
        ).compareTo(maximumAge) <= 0;
    }
}

// ============================================================
// 7. CARDINALITY ESTIMATION SERVICE
// ============================================================

class CardinalityService {

    private final StatisticsRepository repository;

    CardinalityService(StatisticsRepository repository) {
        this.repository = repository;
    }

    double selectivity(
        String relationName,
        Predicate predicate
    ) {

        RelationStats relation = repository.get(
            relationName
        );

        ColumnStats column = relation.columns().get(
            predicate.column()
        );

        if (column == null) {
            throw new OptimizationException(
                "Unknown column: " + predicate.column()
            );
        }

        if (predicate.operator() == Operator.EQUAL) {

            if (predicate.value().equals("NULL")) {
                return column.nullFraction();
            }

            Double frequency =
                column.mostCommonValues().get(
                    predicate.value()
                );

            if (frequency != null) {
                return frequency;
            }

            return (
                1.0 - column.nullFraction()
            ) / column.distinctValues();
        }

        Optional<Histogram> histogram = column.histogram();

        if (histogram.isEmpty()) {
            return predicate.operator() == Operator.BETWEEN
                ? 0.25
                : 0.33;
        }

        try {

            double value = Double.parseDouble(
                predicate.value()
            );

            return switch (predicate.operator()) {

                case LESS_THAN ->
                    histogram.get().estimate(
                        histogram.get().boundaries().get(0),
                        value
                    );

                case GREATER_THAN ->
                    histogram.get().estimate(
                        value,
                        histogram.get().boundaries().get(
                            histogram.get().boundaries().size() - 1
                        )
                    );

                case BETWEEN ->
                    histogram.get().estimate(
                        value,
                        predicate.upper()
                    );

                default -> throw new OptimizationException(
                    "Unsupported predicate."
                );
            };

        } catch (NumberFormatException exception) {
            throw new OptimizationException(
                "Range predicate must be numeric.",
                exception
            );
        }
    }

    double filteredRows(
        String relation,
        List<Predicate> predicates
    ) {

        double selectivity = 1.0;

        for (Predicate predicate : predicates) {
            selectivity *= selectivity(relation, predicate);
        }

        return repository.get(relation).rows()
            * selectivity;
    }
}

// ============================================================
// 8. ACCESS PATH SERVICE
// ============================================================

class AccessPathService {

    private final StatisticsRepository repository;
    private final CardinalityService cardinality;
    private final CostPolicy costs;

    AccessPathService(
        StatisticsRepository repository,
        CardinalityService cardinality,
        CostPolicy costs
    ) {
        this.repository = repository;
        this.cardinality = cardinality;
        this.costs = costs;
    }

    List<Plan> evaluate(
        String relationName,
        List<Predicate> predicates
    ) {

        RelationStats relation = repository.get(
            relationName
        );

        double rows = cardinality.filteredRows(
            relationName,
            predicates
        );

        double sequentialCost =
            relation.pages() * costs.sequentialPage()
            + relation.rows() * costs.tuple()
            + relation.rows()
            * predicates.size()
            * costs.operation();

        List<Plan> candidates = new ArrayList<>();

        candidates.add(
            new Plan(
                "Sequential Scan",
                sequentialCost,
                rows,
                "relation=" + relationName,
                List.of()
            )
        );

        for (Predicate predicate : predicates) {

            if (predicate.operator() != Operator.EQUAL) {
                continue;
            }

            IndexStats index = relation.indexes().get(
                predicate.column()
            );

            if (index == null) {
                continue;
            }

            double height = Math.max(
                1,
                Math.ceil(Math.log(index.pages() + 1) / Math.log(2))
            );

            double heapPages = relation.rows() == 0
                ? 0
                : rows * relation.pages() / relation.rows();

            if (index.indexOnly()) {
                heapPages *= 0.1;
            }

            double indexCost =
                height * costs.randomPage()
                + heapPages * costs.randomPage()
                * costs.cacheDiscount()
                + rows * costs.tuple();

            candidates.add(
                new Plan(
                    "Index Scan",
                    indexCost,
                    rows,
                    "relation=" + relationName
                        + ", index=" + predicate.column(),
                    List.of()
                )
            );
        }

        candidates.sort(
            Comparator.comparingDouble(Plan::cost)
        );

        return List.copyOf(candidates);
    }
}

// ============================================================
// 9. JOIN PLANNING SERVICE
// ============================================================

class JoinPlanningService {

    private final StatisticsRepository repository;
    private final CostPolicy costs;

    JoinPlanningService(
        StatisticsRepository repository,
        CostPolicy costs
    ) {
        this.repository = repository;
        this.costs = costs;
    }

    double estimateRows(
        double leftRows,
        double rightRows,
        JoinCondition join
    ) {

        RelationStats left = repository.get(
            join.leftRelation()
        );

        RelationStats right = repository.get(
            join.rightRelation()
        );

        ColumnStats leftColumn = left.columns().get(
            join.leftColumn()
        );

        ColumnStats rightColumn = right.columns().get(
            join.rightColumn()
        );

        if (leftColumn == null || rightColumn == null) {
            throw new OptimizationException(
                "Invalid join column."
            );
        }

        return leftRows * rightRows /
            Math.max(
                leftColumn.distinctValues(),
                rightColumn.distinctValues()
            );
    }

    List<Plan> candidates(
        Plan left,
        Plan right,
        JoinCondition join
    ) {

        double rows = estimateRows(
            left.rows(),
            right.rows(),
            join
        );

        double buildRows = Math.min(
            left.rows(),
            right.rows()
        );

        double probeRows = Math.max(
            left.rows(),
            right.rows()
        );

        double hashCost =
            left.cost() + right.cost()
            + buildRows * costs.hashBuild()
            + probeRows * costs.operation()
            + (left.rows() + right.rows()) * costs.tuple();

        double nestedCost =
            left.cost() + right.cost()
            + left.rows() * right.rows() * costs.nestedLoop()
            + rows * costs.tuple();

        return List.of(
            new Plan(
                "Hash Join",
                hashCost,
                rows,
                "build rows=" + buildRows,
                List.of(left, right)
            ),
            new Plan(
                "Nested Loop",
                nestedCost,
                rows,
                "outer rows=" + left.rows(),
                List.of(left, right)
            )
        );
    }
}

// ============================================================
// 10. OPTIMIZATION SERVICE
// ============================================================

class OptimizationService {

    private final StatisticsRepository repository;
    private final AccessPathService accessPaths;
    private final JoinPlanningService joins;

    OptimizationService(
        StatisticsRepository repository,
        AccessPathService accessPaths,
        JoinPlanningService joins
    ) {
        this.repository = repository;
        this.accessPaths = accessPaths;
        this.joins = joins;
    }

    Plan optimize(Query query) {

        validate(query);

        int count = query.relations().size();

        if (count > 12) {
            throw new OptimizationException(
                "Maximum supported relation count is 12."
            );
        }

        Map<Long, Plan> dp = new HashMap<>();

        for (int i = 0; i < count; i++) {

            String relation = query.relations().get(i);

            List<Predicate> predicates =
                query.predicates().getOrDefault(
                    relation,
                    List.of()
                );

            dp.put(
                1L << i,
                accessPaths.evaluate(
                    relation,
                    predicates
                ).get(0)
            );
        }

        long fullMask = (1L << count) - 1;

        for (int size = 2; size <= count; size++) {

            for (long mask = 1; mask <= fullMask; mask++) {

                if (Long.bitCount(mask) != size) {
                    continue;
                }

                Plan best = null;

                for (int i = 0; i < count; i++) {

                    long currentBit = 1L << i;

                    if ((mask & currentBit) == 0) {
                        continue;
                    }

                    long leftMask = mask ^ currentBit;

                    Plan left = dp.get(leftMask);
                    Plan right = dp.get(currentBit);

                    if (left == null || right == null) {
                        continue;
                    }

                    String relation =
                        query.relations().get(i);

                    for (JoinCondition join : query.joins()) {

                        boolean connected =
                            join.leftRelation().equals(relation)
                            && containsRelation(
                                leftMask,
                                query,
                                join.rightRelation()
                            )
                            ||
                            join.rightRelation().equals(relation)
                            && containsRelation(
                                leftMask,
                                query,
                                join.leftRelation()
                            );

                        if (!connected) {
                            continue;
                        }

                        for (Plan candidate :
                            joins.candidates(left, right, join)) {

                            if (
                                best == null ||
                                candidate.cost() < best.cost()
                            ) {
                                best = candidate;
                            }
                        }
                    }
                }

                if (best != null) {
                    dp.put(mask, best);
                }
            }
        }

        Plan result = dp.get(fullMask);

        if (result == null) {
            throw new OptimizationException(
                "No connected execution plan found."
            );
        }

        return result;
    }

    private boolean containsRelation(
        long mask,
        Query query,
        String relation
    ) {
        for (int i = 0; i < query.relations().size(); i++) {
            if (
                (mask & (1L << i)) != 0 &&
                query.relations().get(i).equals(relation)
            ) {
                return true;
            }
        }

        return false;
    }

    private void validate(Query query) {

        if (
            query.relations().isEmpty() ||
            query.relations().size() > 12
        ) {
            throw new OptimizationException(
                "Invalid query relation count."
            );
        }

        if (
            new HashSet<>(query.relations()).size()
            != query.relations().size()
        ) {
            throw new OptimizationException(
                "Duplicate relations are not supported."
            );
        }

        Set<String> relationSet = new HashSet<>(
            query.relations()
        );

        for (String relation : query.relations()) {
            repository.get(relation);
        }

        if (!relationSet.containsAll(query.predicates().keySet())) {
            throw new OptimizationException(
                "Predicate references an unknown relation."
            );
        }

        for (JoinCondition join : query.joins()) {

            if (
                !relationSet.contains(join.leftRelation()) ||
                !relationSet.contains(join.rightRelation())
            ) {
                throw new OptimizationException(
                    "Join references an unknown relation."
                );
            }
        }
    }
}

// ============================================================
// 11. SAMPLE STATISTICS
// ============================================================

class SampleStatistics {

    static InMemoryStatisticsRepository create() {

        InMemoryStatisticsRepository repository =
            new InMemoryStatisticsRepository();

        Map<String, ColumnStats> customerColumns =
            new TreeMap<>();

        customerColumns.put(
            "customer_id",
            new ColumnStats(
                "customer_id",
                100000,
                0.0,
                Map.of(),
                Optional.empty()
            )
        );

        customerColumns.put(
            "region",
            new ColumnStats(
                "region",
                10,
                0.0,
                Map.of(
                    "North", 0.35,
                    "South", 0.25,
                    "East", 0.20,
                    "West", 0.15
                ),
                Optional.empty()
            )
        );

        repository.register(
            new RelationStats(
                "customers",
                100000,
                1000,
                customerColumns,
                Map.of(
                    "customer_id",
                    new IndexStats(
                        "customer_id", 250, true, false
                    ),
                    "region",
                    new IndexStats(
                        "region", 80, false, false
                    )
                ),
                Instant.now()
            )
        );

        Map<String, ColumnStats> orderColumns =
            new TreeMap<>();

        orderColumns.put(
            "order_id",
            new ColumnStats(
                "order_id",
                1000000,
                0.0,
                Map.of(),
                Optional.empty()
            )
        );

        orderColumns.put(
            "customer_id",
            new ColumnStats(
                "customer_id",
                100000,
                0.0,
                Map.of(),
                Optional.empty()
            )
        );

        orderColumns.put(
            "status",
            new ColumnStats(
                "status",
                4,
                0.0,
                Map.of(
                    "COMPLETED", 0.65,
                    "PENDING", 0.20,
                    "CANCELLED", 0.10,
                    "FAILED", 0.05
                ),
                Optional.empty()
            )
        );

        orderColumns.put(
            "amount",
            new ColumnStats(
                "amount",
                50000,
                0.0,
                Map.of(),
                Optional.of(
                    new Histogram(
                        List.of(
                            0.0, 100.0, 250.0,
                            500.0, 1000.0,
                            5000.0, 10000.0
                        )
                    )
                )
            )
        );

        repository.register(
            new RelationStats(
                "orders",
                1000000,
                12000,
                orderColumns,
                Map.of(
                    "customer_id",
                    new IndexStats(
                        "customer_id", 2000, false, false
                    ),
                    "status",
                    new IndexStats(
                        "status", 500, false, false
                    ),
                    "order_id",
                    new IndexStats(
                        "order_id", 2500, true, false
                    )
                ),
                Instant.now()
            )
        );

        Map<String, ColumnStats> paymentColumns =
            new TreeMap<>();

        paymentColumns.put(
            "payment_id",
            new ColumnStats(
                "payment_id",
                850000,
                0.0,
                Map.of(),
                Optional.empty()
            )
        );

        paymentColumns.put(
            "order_id",
            new ColumnStats(
                "order_id",
                800000,
                0.0,
                Map.of(),
                Optional.empty()
            )
        );

        paymentColumns.put(
            "payment_status",
            new ColumnStats(
                "payment_status",
                3,
                0.0,
                Map.of(
                    "SUCCESS", 0.80,
                    "PENDING", 0.15,
                    "FAILED", 0.05
                ),
                Optional.empty()
            )
        );

        repository.register(
            new RelationStats(
                "payments",
                850000,
                9000,
                paymentColumns,
                Map.of(
                    "order_id",
                    new IndexStats(
                        "order_id", 1800, false, false
                    ),
                    "payment_id",
                    new IndexStats(
                        "payment_id", 2000, true, false
                    )
                ),
                Instant.now()
            )
        );

        return repository;
    }
}
