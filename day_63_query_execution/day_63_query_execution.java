import java.util.*;
import java.util.function.Function;
import java.util.function.Predicate;

/**
 * Query Execution: operators, execution plans, and result generation.
 *
 * The model uses immutable records for query input, explicit state
 * transitions in the execution service, and composable operators.
 */
public class QueryExecutionDemo {

    enum ExecutionState {
        CREATED,
        PLANNED,
        EXECUTING,
        COMPLETED,
        FAILED
    }

    static class QueryException extends RuntimeException {
        QueryException(String message) {
            super(message);
        }
    }

    static final class ValidationException extends QueryException {
        ValidationException(String message) {
            super(message);
        }
    }

    static final class ExecutionException extends QueryException {
        ExecutionException(String message) {
            super(message);
        }
    }

    record Query(String status, double minimumTotal, int limit) {
        Query {
            if (!Set.of("active", "inactive").contains(status)) {
                throw new ValidationException("Unsupported customer status.");
            }
            if (minimumTotal < 0 || Double.isNaN(minimumTotal)) {
                throw new ValidationException("Invalid minimum total.");
            }
            if (limit <= 0) {
                throw new ValidationException("LIMIT must be positive.");
            }
        }
    }

    record Customer(int id, String name, String status) {}

    record Order(int id, int customerId, double total) {}

    record ResultRow(
        int customerId,
        String customerName,
        int orderId,
        double total
    ) {}

    interface Operator<T> {
        List<T> execute();
        String explain(int indent);
    }

    static final class Table<T> {
        private final String name;
        private final List<T> rows;

        Table(String name, List<T> rows) {
            if (name == null || name.isBlank()) {
                throw new ValidationException("Table name is required.");
            }
            this.name = name;
            this.rows = List.copyOf(rows);
        }

        String name() {
            return name;
        }

        List<T> rows() {
            return rows;
        }
    }

    static final class IndexScan<T, K> implements Operator<T> {
        private final Table<T> table;
        private final Map<K, List<T>> index;
        private final K key;
        private final String description;

        IndexScan(
            Table<T> table,
            Map<K, List<T>> index,
            K key,
            String description
        ) {
            this.table = table;
            this.index = index;
            this.key = key;
            this.description = description;
        }

        @Override
        public List<T> execute() {
            return List.copyOf(index.getOrDefault(key, List.of()));
        }

        @Override
        public String explain(int indent) {
            return " ".repeat(indent) +
                "Index Scan on " + table.name() +
                " (" + description + ")";
        }
    }

    static final class SeqScan<T> implements Operator<T> {
        private final Table<T> table;

        SeqScan(Table<T> table) {
            this.table = table;
        }

        @Override
        public List<T> execute() {
            return table.rows();
        }

        @Override
        public String explain(int indent) {
            return " ".repeat(indent) +
                "Seq Scan on " + table.name();
        }
    }

    static final class Filter<T> implements Operator<T> {
        private final Operator<T> child;
        private final Predicate<T> predicate;
        private final String description;

        Filter(
            Operator<T> child,
            Predicate<T> predicate,
            String description
        ) {
            this.child = child;
            this.predicate = predicate;
            this.description = description;
        }

        @Override
        public List<T> execute() {
            return child.execute()
                .stream()
                .filter(predicate)
                .toList();
        }

        @Override
        public String explain(int indent) {
            return " ".repeat(indent) +
                "Filter: " + description + "\n" +
                child.explain(indent + 2);
        }
    }

    static final class HashJoin<L, R, K, O> implements Operator<O> {
        private final Operator<L> left;
        private final Operator<R> right;
        private final Function<L, K> leftKey;
        private final Function<R, K> rightKey;
        private final java.util.function.BiFunction<L, R, O> merger;
        private final String description;

        HashJoin(
            Operator<L> left,
            Operator<R> right,
            Function<L, K> leftKey,
            Function<R, K> rightKey,
            java.util.function.BiFunction<L, R, O> merger,
            String description
        ) {
            this.left = left;
            this.right = right;
            this.leftKey = leftKey;
            this.rightKey = rightKey;
            this.merger = merger;
            this.description = description;
        }

        @Override
        public List<O> execute() {
            Map<K, List<R>> hashTable = new HashMap<>();

            for (R row : right.execute()) {
                hashTable
                    .computeIfAbsent(rightKey.apply(row), ignored ->
                        new ArrayList<>())
                    .add(row);
            }

            List<O> result = new ArrayList<>();

            for (L leftRow : left.execute()) {
                List<R> matches =
                    hashTable.getOrDefault(leftKey.apply(leftRow), List.of());

                for (R rightRow : matches) {
                    result.add(merger.apply(leftRow, rightRow));
                }
            }

            return List.copyOf(result);
        }

        @Override
        public String explain(int indent) {
            return " ".repeat(indent) +
                "Hash Join: " + description + "\n" +
                left.explain(indent + 2) + "\n" +
                right.explain(indent + 2);
        }
    }

    static final class Sort<T> implements Operator<T> {
        private final Operator<T> child;
        private final Comparator<T> comparator;
        private final String description;

        Sort(
            Operator<T> child,
            Comparator<T> comparator,
            String description
        ) {
            this.child = child;
            this.comparator = comparator;
            this.description = description;
        }

        @Override
        public List<T> execute() {
            return child.execute()
                .stream()
                .sorted(comparator)
                .toList();
        }

        @Override
        public String explain(int indent) {
            return " ".repeat(indent) +
                "Sort: " + description + "\n" +
                child.explain(indent + 2);
        }
    }

    static final class Limit<T> implements Operator<T> {
        private final Operator<T> child;
        private final int limit;

        Limit(Operator<T> child, int limit) {
            if (limit < 0) {
                throw new ValidationException("Negative LIMIT.");
            }
            this.child = child;
            this.limit = limit;
        }

        @Override
        public List<T> execute() {
            return child.execute()
                .stream()
                .limit(limit)
                .toList();
        }

        @Override
        public String explain(int indent) {
            return " ".repeat(indent) +
                "Limit: " + limit + "\n" +
                child.explain(indent + 2);
        }
    }

    static final class QueryExecutionService {
        private ExecutionState state = ExecutionState.CREATED;

        List<ResultRow> execute(Query query) {
            try {
                Operator<ResultRow> plan = buildPlan(query);
                state = ExecutionState.PLANNED;

                state = ExecutionState.EXECUTING;
                List<ResultRow> result = plan.execute();

                state = ExecutionState.COMPLETED;
                return result;
            } catch (RuntimeException error) {
                state = ExecutionState.FAILED;
                throw error;
            }
        }

        ExecutionState state() {
            return state;
        }

        Operator<ResultRow> buildPlan(Query query) {
            Table<Customer> customers = new Table<>(
                "customers",
                List.of(
                    new Customer(1, "Asha", "active"),
                    new Customer(2, "Bharat", "active"),
                    new Customer(3, "Chen", "inactive"),
                    new Customer(4, "Divya", "active")
                )
            );

            Table<Order> orders = new Table<>(
                "orders",
                List.of(
                    new Order(101, 1, 450),
                    new Order(102, 1, 1200),
                    new Order(103, 2, 900),
                    new Order(104, 3, 2500),
                    new Order(105, 4, 1750)
                )
            );

            Map<String, List<Customer>> statusIndex = new HashMap<>();
            for (Customer customer : customers.rows()) {
                statusIndex
                    .computeIfAbsent(customer.status(), ignored ->
                        new ArrayList<>())
                    .add(customer);
            }

            Operator<Customer> customerScan = new IndexScan<>(
                customers,
                statusIndex,
                query.status(),
                "status = " + query.status()
            );

            Operator<Order> orderScan = new SeqScan<>(orders);

            Operator<ResultRow> join = new HashJoin<>(
                customerScan,
                orderScan,
                Customer::id,
                Order::customerId,
                (customer, order) -> new ResultRow(
                    customer.id(),
                    customer.name(),
                    order.id(),
                    order.total()
                ),
                "customers.id = orders.customer_id"
            );

            Operator<ResultRow> filtered = new Filter<>(
                join,
                row -> row.total() >= query.minimumTotal(),
                "order.total >= " + query.minimumTotal()
            );

            Operator<ResultRow> sorted = new Sort<>(
                filtered,
                Comparator.comparingDouble(ResultRow::total).reversed(),
                "total DESC"
            );

            return new Limit<>(sorted, query.limit());
        }
    }

    public static void main(String[] args) {
        Query query = new Query("active", 800.0, 3);
        QueryExecutionService service = new QueryExecutionService();

        Operator<ResultRow> plan = service.buildPlan(query);

        System.out.println("EXECUTION PLAN");
        System.out.println(plan.explain(0));

        long started = System.nanoTime();
        List<ResultRow> results = service.execute(query);
        long elapsed = System.nanoTime() - started;

        System.out.println("\nRESULT SET");
        System.out.println("customer_id | customer_name | order_id | total");

        for (ResultRow row : results) {
            System.out.printf(
                "%d | %s | %d | %.2f%n",
                row.customerId(),
                row.customerName(),
                row.orderId(),
                row.total()
            );
        }

        System.out.printf(
            "%nRows returned: %d%nExecution time: %.3f ms%n",
            results.size(),
            elapsed / 1_000_000.0
        );

        if (results.size() > query.limit()) {
            throw new ExecutionException("LIMIT invariant failed.");
        }

        if (results.stream().anyMatch(
            row -> row.total() < query.minimumTotal()
        )) {
            throw new ExecutionException("Filter invariant failed.");
        }

        try {
            new Query("unknown", 0, 3);
        } catch (ValidationException error) {
            System.out.println(
                "\nValidation failure handled: " + error.getMessage()
            );
        }

        System.out.println("Execution state: " + service.state());
    }
}
