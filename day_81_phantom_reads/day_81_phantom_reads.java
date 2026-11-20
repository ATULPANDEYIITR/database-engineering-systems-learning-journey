import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.function.Predicate;

/**
 * Phantom Reads: Range Queries and Transaction Isolation
 *
 * Enterprise-oriented transaction management model.
 *
 * Java 17 features:
 * - Records and enums
 * - Immutable domain values
 * - Service interfaces
 * - Policy objects
 * - Snapshot isolation
 * - Predicate validation
 * - Transaction state transitions
 * - Custom exceptions
 * - Stream-based range processing
 */

public class PhantomReadsDemo {

    enum IsolationLevel {
        READ_COMMITTED,
        REPEATABLE_READ,
        SERIALIZABLE
    }

    enum TransactionState {
        ACTIVE,
        COMMITTED,
        ABORTED
    }

    record Product(
        int id,
        String name,
        double price,
        String category
    ) {
        Product {
            if (id <= 0) {
                throw new IllegalArgumentException(
                    "Product ID must be positive"
                );
            }

            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Product name is required"
                );
            }

            if (!Double.isFinite(price) || price < 0) {
                throw new IllegalArgumentException(
                    "Invalid product price"
                );
            }

            if (category == null || category.isBlank()) {
                throw new IllegalArgumentException(
                    "Category is required"
                );
            }
        }
    }

    record VersionedProduct(Product product, long version) {}

    record Change(long version, double price, int productId) {}

    record RangePredicate(
        double minimum,
        double maximum,
        boolean includeMinimum,
        boolean includeMaximum
    ) {
        RangePredicate {
            if (
                !Double.isFinite(minimum) ||
                !Double.isFinite(maximum) ||
                minimum > maximum
            ) {
                throw new IllegalArgumentException("Invalid range");
            }
        }

        boolean contains(double value) {
            boolean lower = includeMinimum
                ? value >= minimum
                : value > minimum;

            boolean upper = includeMaximum
                ? value <= maximum
                : value < maximum;

            return lower && upper;
        }

        static RangePredicate halfOpen(
            double minimum,
            double maximum
        ) {
            return new RangePredicate(
                minimum,
                maximum,
                true,
                false
            );
        }
    }

    static class TransactionException extends RuntimeException {
        TransactionException(String message) {
            super(message);
        }
    }

    static class SerializationFailure extends TransactionException {
        SerializationFailure(String message) {
            super(message);
        }
    }

    static class WriteConflict extends TransactionException {
        WriteConflict(String message) {
            super(message);
        }
    }

    static class Transaction {
        private final long id;
        private final IsolationLevel isolation;
        private final long startVersion;

        private final Map<Integer, VersionedProduct> snapshot;
        private final Map<Integer, Optional<Product>> writes =
            new HashMap<>();

        private final List<RangePredicate> readRanges =
            new ArrayList<>();

        private TransactionState state = TransactionState.ACTIVE;

        Transaction(
            long id,
            IsolationLevel isolation,
            long startVersion,
            Map<Integer, VersionedProduct> snapshot
        ) {
            this.id = id;
            this.isolation = isolation;
            this.startVersion = startVersion;
            this.snapshot = Map.copyOf(snapshot);
        }

        long id() {
            return id;
        }

        IsolationLevel isolation() {
            return isolation;
        }

        TransactionState state() {
            return state;
        }

        void ensureActive() {
            if (state != TransactionState.ACTIVE) {
                throw new TransactionException(
                    "Transaction " + id + " is " + state
                );
            }
        }

        void commitState() {
            ensureActive();
            state = TransactionState.COMMITTED;
        }

        void abortState() {
            state = TransactionState.ABORTED;
        }
    }

    interface TransactionRepository {
        Transaction begin(IsolationLevel isolation);

        List<Product> queryRange(
            Transaction transaction,
            RangePredicate predicate
        );

        void insert(Transaction transaction, Product product);

        void commit(Transaction transaction);

        void rollback(Transaction transaction);
    }

    static class ProductDatabase implements TransactionRepository {

        private final Map<Integer, VersionedProduct> rows =
            new HashMap<>();

        private final List<Change> history = new ArrayList<>();

        private long version = 0;
        private long transactionSequence = 0;

        void seed(List<Product> products) {
            for (Product product : products) {
                if (rows.containsKey(product.id())) {
                    throw new WriteConflict("Duplicate product ID");
                }

                rows.put(
                    product.id(),
                    new VersionedProduct(product, ++version)
                );
            }
        }

        @Override
        public Transaction begin(IsolationLevel isolation) {
            Objects.requireNonNull(isolation);

            return new Transaction(
                ++transactionSequence,
                isolation,
                version,
                rows
            );
        }

        private Map<Integer, Product> visibleRows(
            Transaction transaction
        ) {
            transaction.ensureActive();

            Map<Integer, VersionedProduct> source =
                transaction.isolation() == IsolationLevel.READ_COMMITTED
                    ? rows
                    : transaction.snapshot;

            Map<Integer, Product> visible = new HashMap<>();

            source.forEach(
                (id, entry) -> visible.put(id, entry.product())
            );

            transaction.writes.forEach((id, product) -> {
                if (product.isPresent()) {
                    visible.put(id, product.get());
                } else {
                    visible.remove(id);
                }
            });

            return visible;
        }

        @Override
        public List<Product> queryRange(
            Transaction transaction,
            RangePredicate predicate
        ) {
            transaction.ensureActive();

            if (transaction.isolation() == IsolationLevel.SERIALIZABLE) {
                transaction.readRanges.add(predicate);
            }

            return visibleRows(transaction)
                .values()
                .stream()
                .filter(product -> predicate.contains(product.price()))
                .sorted(Comparator.comparingInt(Product::id))
                .toList();
        }

        @Override
        public void insert(
            Transaction transaction,
            Product product
        ) {
            transaction.ensureActive();

            if (visibleRows(transaction).containsKey(product.id())) {
                throw new WriteConflict(
                    "Product already exists: " + product.id()
                );
            }

            transaction.writes.put(
                product.id(),
                Optional.of(product)
            );
        }

        void update(Transaction transaction, Product product) {
            transaction.ensureActive();

            if (!visibleRows(transaction).containsKey(product.id())) {
                throw new TransactionException("Product does not exist");
            }

            transaction.writes.put(
                product.id(),
                Optional.of(product)
            );
        }

        void delete(Transaction transaction, int productId) {
            transaction.ensureActive();

            if (!visibleRows(transaction).containsKey(productId)) {
                throw new TransactionException("Product does not exist");
            }

            transaction.writes.put(
                productId,
                Optional.empty()
            );
        }

        private void validateWriteConflicts(Transaction transaction) {
            for (int id : transaction.writes.keySet()) {
                VersionedProduct current = rows.get(id);
                VersionedProduct original = transaction.snapshot.get(id);

                if (transaction.isolation() != IsolationLevel.READ_COMMITTED) {
                    if ((current == null) != (original == null)) {
                        throw new WriteConflict(
                            "Concurrent insertion or deletion: " + id
                        );
                    }

                    if (
                        current != null &&
                        current.version() != original.version()
                    ) {
                        throw new WriteConflict(
                            "Concurrent modification: " + id
                        );
                    }
                } else if (original == null && current != null) {
                    throw new WriteConflict(
                        "Concurrent insertion: " + id
                    );
                }
            }
        }

        private void validateSerializable(Transaction transaction) {
            for (Change change : history) {
                if (change.version() <= transaction.startVersion) {
                    continue;
                }

                boolean conflict = transaction.readRanges
                    .stream()
                    .anyMatch(range -> range.contains(change.price()));

                if (conflict) {
                    throw new SerializationFailure(
                        "Concurrent transaction changed a read range"
                    );
                }
            }
        }

        @Override
        public void commit(Transaction transaction) {
            transaction.ensureActive();

            try {
                validateWriteConflicts(transaction);

                if (transaction.isolation() == IsolationLevel.SERIALIZABLE) {
                    validateSerializable(transaction);
                }

                // All validations finish before the write set is applied.
                for (Map.Entry<Integer, Optional<Product>> entry :
                    transaction.writes.entrySet()) {

                    int id = entry.getKey();
                    Optional<Product> product = entry.getValue();

                    long newVersion = ++version;

                    if (product.isPresent()) {
                        Product saved = product.get();

                        rows.put(
                            id,
                            new VersionedProduct(saved, newVersion)
                        );

                        history.add(
                            new Change(
                                newVersion,
                                saved.price(),
                                saved.id()
                            )
                        );
                    } else {
                        rows.remove(id);
                    }
                }

                transaction.commitState();

                System.out.println(
                    "Transaction " + transaction.id() + " committed."
                );

            } catch (TransactionException exception) {
                transaction.abortState();

                System.out.println(
                    "Transaction " + transaction.id() +
                    " aborted: " + exception.getMessage()
                );

                throw exception;
            }
        }

        @Override
        public void rollback(Transaction transaction) {
            transaction.ensureActive();
            transaction.writes.clear();
            transaction.abortState();
        }

        List<Product> allProducts() {
            return rows.values()
                .stream()
                .map(VersionedProduct::product)
                .sorted(Comparator.comparingInt(Product::id))
                .toList();
        }
    }

    static class TransactionPolicy {

        private final IsolationLevel isolation;
        private final int retryLimit;

        TransactionPolicy(
            IsolationLevel isolation,
            int retryLimit
        ) {
            if (retryLimit < 0 || retryLimit > 10) {
                throw new IllegalArgumentException(
                    "Retry limit must be between 0 and 10"
                );
            }

            this.isolation = isolation;
            this.retryLimit = retryLimit;
        }

        IsolationLevel isolation() {
            return isolation;
        }

        int retryLimit() {
            return retryLimit;
        }
    }

    static class InventoryService {

        private final ProductDatabase database;
        private final TransactionPolicy policy;

        InventoryService(
            ProductDatabase database,
            TransactionPolicy policy
        ) {
            this.database = database;
            this.policy = policy;
        }

        List<Product> findProductsInPriceRange(
            double minimum,
            double maximum
        ) {
            RangePredicate predicate =
                RangePredicate.halfOpen(minimum, maximum);

            Transaction transaction =
                database.begin(policy.isolation());

            try {
                List<Product> products =
                    database.queryRange(transaction, predicate);

                database.commit(transaction);

                return products;

            } catch (RuntimeException exception) {
                if (transaction.state() == TransactionState.ACTIVE) {
                    database.rollback(transaction);
                }

                throw exception;
            }
        }
    }

    private static ProductDatabase createDatabase() {
        ProductDatabase database = new ProductDatabase();

        database.seed(List.of(
            new Product(1, "Keyboard", 1200, "Electronics"),
            new Product(2, "Mouse", 800, "Electronics"),
            new Product(3, "Monitor", 8500, "Electronics"),
            new Product(4, "Desk", 6000, "Furniture"),
            new Product(5, "Notebook", 150, "Stationery")
        ));

        return database;
    }

    private static void display(
        String title,
        List<Product> products
    ) {
        System.out.println("\n" + title);

        products.forEach(product ->
            System.out.printf(
                "%d | %-15s | %.2f%n",
                product.id(),
                product.name(),
                product.price()
            )
        );

        System.out.println("Rows: " + products.size());
    }

    private static void demonstrateReadCommitted() {
        System.out.println("\n=== READ COMMITTED ===");

        ProductDatabase database = createDatabase();

        Transaction reader =
            database.begin(IsolationLevel.READ_COMMITTED);

        RangePredicate range =
            RangePredicate.halfOpen(500, 5000);

        List<Product> first = database.queryRange(reader, range);

        Transaction writer =
            database.begin(IsolationLevel.READ_COMMITTED);

        database.insert(
            writer,
            new Product(6, "Webcam", 2500, "Electronics")
        );

        database.commit(writer);

        List<Product> second = database.queryRange(reader, range);

        display("First query", first);
        display("Second query", second);

        assert first.size() == 3;
        assert second.size() == 4;

        database.commit(reader);
    }

    private static void demonstrateRepeatableRead() {
        System.out.println("\n=== REPEATABLE READ ===");

        ProductDatabase database = createDatabase();

        Transaction reader =
            database.begin(IsolationLevel.REPEATABLE_READ);

        RangePredicate range =
            RangePredicate.halfOpen(500, 5000);

        List<Product> first = database.queryRange(reader, range);

        Transaction writer =
            database.begin(IsolationLevel.READ_COMMITTED);

        database.insert(
            writer,
            new Product(6, "Webcam", 2500, "Electronics")
        );

        database.commit(writer);

        List<Product> second = database.queryRange(reader, range);

        display("First query", first);
        display("Second query", second);

        assert first.size() == second.size();

        database.commit(reader);

        Transaction later =
            database.begin(IsolationLevel.REPEATABLE_READ);

        List<Product> current =
            database.queryRange(later, range);

        assert current.size() == 4;

        display("New transaction", current);

        database.commit(later);
    }

    private static void demonstrateSerializable() {
        System.out.println("\n=== SERIALIZABLE ===");

        ProductDatabase database = createDatabase();

        Transaction reader =
            database.begin(IsolationLevel.SERIALIZABLE);

        RangePredicate range =
            RangePredicate.halfOpen(500, 5000);

        List<Product> first = database.queryRange(reader, range);

        Transaction writer =
            database.begin(IsolationLevel.READ_COMMITTED);

        database.insert(
            writer,
            new Product(6, "Webcam", 2500, "Electronics")
        );

        database.commit(writer);

        display("Initial range", first);

        try {
            database.commit(reader);
            throw new AssertionError("Expected serialization failure");
        } catch (SerializationFailure exception) {
            System.out.println(
                "Expected conflict: " + exception.getMessage()
            );
        }

        assert reader.state() == TransactionState.ABORTED;
    }

    private static void demonstrateRollback() {
        System.out.println("\n=== ROLLBACK ===");

        ProductDatabase database = createDatabase();

        Transaction transaction =
            database.begin(IsolationLevel.READ_COMMITTED);

        database.insert(
            transaction,
            new Product(99, "Temporary", 900, "Testing")
        );

        database.rollback(transaction);

        assert database.allProducts()
            .stream()
            .noneMatch(product -> product.id() == 99);

        System.out.println("Uncommitted insertion discarded.");
    }

    private static void demonstrateService() {
        System.out.println("\n=== SERVICE LAYER ===");

        ProductDatabase database = createDatabase();

        TransactionPolicy policy = new TransactionPolicy(
            IsolationLevel.REPEATABLE_READ,
            3
        );

        InventoryService service =
            new InventoryService(database, policy);

        List<Product> results =
            service.findProductsInPriceRange(500, 5000);

        display("Inventory service results", results);
    }

    public static void main(String[] args) {
        try {
            demonstrateReadCommitted();
            demonstrateRepeatableRead();
            demonstrateSerializable();
            demonstrateRollback();
            demonstrateService();

            System.out.println("\nAll Java transaction tests passed.");

        } catch (RuntimeException exception) {
            System.err.println(
                "Application failure: " + exception.getMessage()
            );

            System.exit(1);
        }
    }
}
