/*
 * Denormalization case study for an enterprise order analytics platform.
 *
 * Java 17+.
 *
 * The program deliberately separates:
 *   - authoritative normalized entities
 *   - derived denormalized projections
 *   - projection refresh
 *   - reconciliation
 *   - consistency policy
 *   - historical snapshot semantics
 */

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

public class DenormalizationCaseStudy {

    enum OrderStatus {
        PROCESSING,
        SHIPPED,
        DELIVERED,
        CANCELLED
    }

    enum ConsistencyMode {
        STRICT,
        EVENTUAL,
        HISTORICAL
    }

    record Customer(
        long id,
        String name,
        String region
    ) {
        Customer {
            if (id <= 0) {
                throw new IllegalArgumentException("Customer ID must be positive.");
            }
            requireText(name, "Customer name");
            requireText(region, "Customer region");
        }
    }

    record Product(
        long id,
        String name,
        String category,
        BigDecimal unitPrice
    ) {
        Product {
            if (id <= 0) {
                throw new IllegalArgumentException("Product ID must be positive.");
            }
            requireText(name, "Product name");
            requireText(category, "Product category");

            if (unitPrice == null || unitPrice.signum() < 0) {
                throw new IllegalArgumentException("Product price cannot be negative.");
            }

            unitPrice = unitPrice.setScale(2, RoundingMode.HALF_UP);
        }
    }

    record Order(
        long id,
        long customerId,
        LocalDate orderDate,
        OrderStatus status
    ) {
        Order {
            if (id <= 0 || customerId <= 0) {
                throw new IllegalArgumentException("IDs must be positive.");
            }
            Objects.requireNonNull(orderDate, "Order date is required.");
            Objects.requireNonNull(status, "Order status is required.");
        }
    }

    record OrderLine(
        long orderId,
        long productId,
        int quantity
    ) {
        OrderLine {
            if (orderId <= 0 || productId <= 0 || quantity <= 0) {
                throw new IllegalArgumentException(
                    "Order-line identifiers and quantity must be positive."
                );
            }
        }
    }

    record OrderReadModel(
        long orderId,
        long customerId,
        String customerName,
        String region,
        LocalDate orderDate,
        OrderStatus status,
        int itemCount,
        BigDecimal totalAmount,
        long sourceVersion,
        Instant materializedAt
    ) {
        OrderReadModel {
            requireText(customerName, "Read-model customer name");
            requireText(region, "Read-model region");

            if (itemCount < 0) {
                throw new IllegalArgumentException("Item count cannot be negative.");
            }

            Objects.requireNonNull(totalAmount, "Total amount is required.");
            Objects.requireNonNull(orderDate, "Order date is required.");
            Objects.requireNonNull(status, "Order status is required.");
            Objects.requireNonNull(materializedAt, "Materialization timestamp is required.");
        }
    }

    record DenormalizationPolicy(
        ConsistencyMode consistencyMode,
        double readToWriteRatio,
        int joinCostScore,
        boolean historicalSnapshot,
        boolean acceptsProjectionLag
    ) {
        DenormalizationPolicy {
            Objects.requireNonNull(consistencyMode);

            if (readToWriteRatio < 0 || joinCostScore < 0 || joinCostScore > 10) {
                throw new IllegalArgumentException("Invalid workload score.");
            }
        }

        boolean isCandidate() {
            if (historicalSnapshot) {
                return true;
            }

            if (consistencyMode == ConsistencyMode.STRICT && !acceptsProjectionLag) {
                return false;
            }

            return readToWriteRatio >= 5.0 && joinCostScore >= 3;
        }
    }

    static final class NormalizedStore {

        private final Map<Long, Customer> customers = new HashMap<>();
        private final Map<Long, Product> products = new HashMap<>();
        private final Map<Long, Order> orders = new HashMap<>();
        private final List<OrderLine> orderLines = new ArrayList<>();
        private long version = 1;

        void addCustomer(Customer customer) {
            requireUnique(customers, customer.id(), "customer");
            customers.put(customer.id(), customer);
            version++;
        }

        void addProduct(Product product) {
            requireUnique(products, product.id(), "product");
            products.put(product.id(), product);
            version++;
        }

        void addOrder(Order order) {
            if (!customers.containsKey(order.customerId())) {
                throw new IllegalStateException(
                    "An order cannot reference a missing customer."
                );
            }

            requireUnique(orders, order.id(), "order");
            orders.put(order.id(), order);
            version++;
        }

        void addOrderLine(OrderLine line) {
            if (!orders.containsKey(line.orderId())) {
                throw new IllegalStateException(
                    "An order line cannot reference a missing order."
                );
            }

            if (!products.containsKey(line.productId())) {
                throw new IllegalStateException(
                    "An order line cannot reference a missing product."
                );
            }

            orderLines.add(line);
            version++;
        }

        void updateCustomerName(long customerId, String newName) {
            Customer current = requireCustomer(customerId);
            customers.put(
                customerId,
                new Customer(current.id(), newName, current.region())
            );
            version++;
        }

        void updateOrderStatus(long orderId, OrderStatus status) {
            Order current = requireOrder(orderId);
            orders.put(
                orderId,
                new Order(
                    current.id(),
                    current.customerId(),
                    current.orderDate(),
                    status
                )
            );
            version++;
        }

        Optional<OrderReadModel> buildReadModel(long orderId) {
            Order order = orders.get(orderId);

            if (order == null) {
                return Optional.empty();
            }

            Customer customer = requireCustomer(order.customerId());

            int itemCount = 0;
            BigDecimal total = BigDecimal.ZERO;

            for (OrderLine line : orderLines) {
                if (line.orderId() != orderId) {
                    continue;
                }

                Product product = products.get(line.productId());

                if (product == null) {
                    throw new IllegalStateException(
                        "Order line references missing product."
                    );
                }

                itemCount += line.quantity();

                total = total.add(
                    product.unitPrice()
                        .multiply(BigDecimal.valueOf(line.quantity()))
                );
            }

            return Optional.of(
                new OrderReadModel(
                    order.id(),
                    customer.id(),
                    customer.name(),
                    customer.region(),
                    order.orderDate(),
                    order.status(),
                    itemCount,
                    total.setScale(2, RoundingMode.HALF_UP),
                    version,
                    Instant.now()
                )
            );
        }

        Customer requireCustomer(long id) {
            Customer customer = customers.get(id);

            if (customer == null) {
                throw new IllegalStateException("Customer does not exist: " + id);
            }

            return customer;
        }

        Order requireOrder(long id) {
            Order order = orders.get(id);

            if (order == null) {
                throw new IllegalStateException("Order does not exist: " + id);
            }

            return order;
        }

        List<Order> orders() {
            return List.copyOf(orders.values());
        }

        long version() {
            return version;
        }
    }

    static final class ProjectionService {

        private final NormalizedStore source;
        private final Map<Long, OrderReadModel> projections = new HashMap<>();

        ProjectionService(NormalizedStore source) {
            this.source = Objects.requireNonNull(source);
        }

        void rebuild() {
            projections.clear();

            for (Order order : source.orders()) {
                source.buildReadModel(order.id())
                    .ifPresent(model -> projections.put(order.id(), model));
            }
        }

        void refresh(long orderId) {
            source.buildReadModel(orderId)
                .ifPresentOrElse(
                    model -> projections.put(orderId, model),
                    () -> projections.remove(orderId)
                );
        }

        OrderReadModel get(long orderId) {
            OrderReadModel model = projections.get(orderId);

            if (model == null) {
                throw new IllegalStateException(
                    "Order is not materialized in the read model."
                );
            }

            return model;
        }

        boolean isFresh(long orderId) {
            return get(orderId).sourceVersion() == source.version();
        }
    }

    static final class ReconciliationService {

        private final NormalizedStore source;

        ReconciliationService(NormalizedStore source) {
            this.source = source;
        }

        boolean matchesSource(OrderReadModel model) {
            Optional<OrderReadModel> expected =
                source.buildReadModel(model.orderId());

            return expected.map(current ->
                current.customerId() == model.customerId()
                    && current.customerName().equals(model.customerName())
                    && current.region().equals(model.region())
                    && current.status() == model.status()
                    && current.itemCount() == model.itemCount()
                    && current.totalAmount().compareTo(model.totalAmount()) == 0
            ).orElse(false);
        }
    }

    private static void requireUnique(
        Map<Long, ?> map,
        long id,
        String entity
    ) {
        if (map.containsKey(id)) {
            throw new IllegalArgumentException(
                "Duplicate " + entity + " ID: " + id
            );
        }
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " cannot be blank.");
        }
    }

    private static void printModel(OrderReadModel model) {
        System.out.printf(
            "Order %d | %s | %s | %s | units=%d | total=%s | sourceVersion=%d%n",
            model.orderId(),
            model.customerName(),
            model.region(),
            model.status(),
            model.itemCount(),
            model.totalAmount(),
            model.sourceVersion()
        );
    }

    private static NormalizedStore createStore() {
        NormalizedStore store = new NormalizedStore();

        store.addCustomer(new Customer(1, "Aarav Mehta", "North"));
        store.addCustomer(new Customer(2, "Priya Nair", "South"));
        store.addCustomer(new Customer(3, "Kabir Singh", "North"));
        store.addCustomer(new Customer(4, "Meera Shah", "West"));

        store.addProduct(
            new Product(
                101,
                "Mechanical Keyboard",
                "Peripherals",
                new BigDecimal("89.99")
            )
        );

        store.addProduct(
            new Product(
                102,
                "USB-C Dock",
                "Peripherals",
                new BigDecimal("129.50")
            )
        );

        store.addProduct(
            new Product(
                103,
                "27-inch Monitor",
                "Displays",
                new BigDecimal("279.00")
            )
        );

        store.addProduct(
            new Product(
                104,
                "Laptop Stand",
                "Accessories",
                new BigDecimal("45.00")
            )
        );

        store.addProduct(
            new Product(
                105,
                "Noise-Cancelling Headset",
                "Audio",
                new BigDecimal("159.95")
            )
        );

        store.addOrder(
            new Order(
                5001,
                1,
                LocalDate.of(2026, 9, 1),
                OrderStatus.SHIPPED
            )
        );

        store.addOrder(
            new Order(
                5002,
                2,
                LocalDate.of(2026, 9, 2),
                OrderStatus.PROCESSING
            )
        );

        store.addOrder(
            new Order(
                5003,
                1,
                LocalDate.of(2026, 9, 3),
                OrderStatus.DELIVERED
            )
        );

        store.addOrderLine(new OrderLine(5001, 101, 1));
        store.addOrderLine(new OrderLine(5001, 103, 2));
        store.addOrderLine(new OrderLine(5002, 102, 1));
        store.addOrderLine(new OrderLine(5002, 104, 2));
        store.addOrderLine(new OrderLine(5003, 105, 1));
        store.addOrderLine(new OrderLine(5003, 101, 2));

        return store;
    }

    private static void demonstrateProjectionLifecycle(
        NormalizedStore source
    ) {
        System.out.println("=== MATERIALIZED READ MODEL ===");

        ProjectionService projection = new ProjectionService(source);
        projection.rebuild();

        printModel(projection.get(5001));

        System.out.println(
            "Fresh before source update: "
                + projection.isFresh(5001)
        );

        source.updateCustomerName(1, "Aarav Mehta Kumar");

        System.out.println(
            "Fresh after source update: "
                + projection.isFresh(5001)
        );

        projection.refresh(5001);

        System.out.println(
            "Fresh after projection refresh: "
                + projection.isFresh(5001)
        );

        printModel(projection.get(5001));
    }

    private static void demonstrateReconciliation(
        NormalizedStore source
    ) {
        System.out.println("\n=== RECONCILIATION ===");

        ProjectionService projection = new ProjectionService(source);
        projection.rebuild();

        ReconciliationService reconciliation =
            new ReconciliationService(source);

        OrderReadModel valid = projection.get(5002);

        System.out.println(
            "Valid projection: "
                + reconciliation.matchesSource(valid)
        );

        OrderReadModel corrupted =
            new OrderReadModel(
                valid.orderId(),
                valid.customerId(),
                valid.customerName(),
                valid.region(),
                valid.orderDate(),
                valid.status(),
                valid.itemCount(),
                valid.totalAmount().add(new BigDecimal("25.00")),
                valid.sourceVersion(),
                valid.materializedAt()
            );

        System.out.println(
            "Corrupted projection: "
                + reconciliation.matchesSource(corrupted)
        );
    }

    private static void demonstratePolicies() {
        System.out.println("\n=== POLICY EVALUATION ===");

        List<DenormalizationPolicy> policies = List.of(
            new DenormalizationPolicy(
                ConsistencyMode.EVENTUAL,
                12.0,
                7,
                false,
                true
            ),
            new DenormalizationPolicy(
                ConsistencyMode.STRICT,
                2.0,
                4,
                false,
                false
            ),
            new DenormalizationPolicy(
                ConsistencyMode.HISTORICAL,
                1.0,
                1,
                true,
                false
            )
        );

        for (DenormalizationPolicy policy : policies) {
            System.out.println(
                "Mode=" + policy.consistencyMode()
                    + ", candidate=" + policy.isCandidate()
            );
        }
    }

    private static void demonstrateFailureState(
        NormalizedStore source
    ) {
        System.out.println("\n=== FAILURE HANDLING ===");

        try {
            source.addOrderLine(new OrderLine(9999, 101, 1));
        } catch (IllegalStateException error) {
            System.out.println(
                "Rejected invalid order-line relationship: "
                    + error.getMessage()
            );
        }

        try {
            source.addCustomer(new Customer(1, "Duplicate", "North"));
        } catch (IllegalArgumentException error) {
            System.out.println(
                "Rejected duplicate customer: "
                    + error.getMessage()
            );
        }
    }

    public static void main(String[] args) {
        NormalizedStore source = createStore();

        System.out.println("=== NORMALIZED SOURCE VERSION ===");
        System.out.println(source.version());

        source.buildReadModel(5001).ifPresent(
            DenormalizationCaseStudy::printModel
        );

        demonstrateProjectionLifecycle(source);
        demonstrateReconciliation(source);
        demonstratePolicies();
        demonstrateFailureState(source);

        System.out.println("\n=== DOMAIN PRINCIPLE ===");
        System.out.println(
            "The normalized model owns transactional facts. "
                + "The denormalized model owns derived read performance. "
                + "A projection version, refresh mechanism, and reconciliation "
                + "service make the consistency boundary explicit."
        );
    }
}
