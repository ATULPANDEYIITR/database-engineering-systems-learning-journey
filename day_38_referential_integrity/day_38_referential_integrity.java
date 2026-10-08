import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class ReferentialIntegrityDemo {

    enum DeleteAction {
        RESTRICT,
        CASCADE,
        SET_NULL
    }

    static class ReferentialIntegrityException extends Exception {
        public ReferentialIntegrityException(String message) {
            super(message);
        }
    }

    record Customer(long id, String name) {
        Customer {
            if (id <= 0) {
                throw new IllegalArgumentException("Customer ID must be positive.");
            }
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("Customer name is required.");
            }
            name = name.trim();
        }
    }

    record Order(long id, long customerId, BigDecimal amount) {
        Order {
            if (id <= 0) {
                throw new IllegalArgumentException("Order ID must be positive.");
            }
            if (customerId <= 0) {
                throw new IllegalArgumentException(
                    "Customer reference must be positive."
                );
            }
            if (amount == null || amount.signum() < 0) {
                throw new IllegalArgumentException(
                    "Order amount must be non-negative."
                );
            }
        }

        Order withCustomer(long newCustomerId) {
            return new Order(id, newCustomerId, amount);
        }
    }

    record OrderItem(
        long id,
        long orderId,
        String product,
        int quantity
    ) {
        OrderItem {
            if (id <= 0) {
                throw new IllegalArgumentException("Item ID must be positive.");
            }
            if (orderId <= 0) {
                throw new IllegalArgumentException(
                    "Order reference must be positive."
                );
            }
            if (product == null || product.isBlank()) {
                throw new IllegalArgumentException("Product is required.");
            }
            if (quantity <= 0) {
                throw new IllegalArgumentException(
                    "Quantity must be positive."
                );
            }
            product = product.trim();
        }
    }

    record RelationshipPolicy(
        String parentType,
        String childType,
        String foreignKey,
        DeleteAction onDelete
    ) {}

    interface IntegrityRule {
        void validate(
            Map<Long, Customer> customers,
            Map<Long, Order> orders,
            Map<Long, OrderItem> items
        ) throws ReferentialIntegrityException;
    }

    static class OrderCustomerRule implements IntegrityRule {
        @Override
        public void validate(
            Map<Long, Customer> customers,
            Map<Long, Order> orders,
            Map<Long, OrderItem> items
        ) throws ReferentialIntegrityException {
            for (Order order : orders.values()) {
                if (!customers.containsKey(order.customerId())) {
                    throw new ReferentialIntegrityException(
                        "Order " + order.id()
                        + " references missing customer "
                        + order.customerId()
                    );
                }
            }
        }
    }

    static class ItemOrderRule implements IntegrityRule {
        @Override
        public void validate(
            Map<Long, Customer> customers,
            Map<Long, Order> orders,
            Map<Long, OrderItem> items
        ) throws ReferentialIntegrityException {
            for (OrderItem item : items.values()) {
                if (!orders.containsKey(item.orderId())) {
                    throw new ReferentialIntegrityException(
                        "Item " + item.id()
                        + " references missing order "
                        + item.orderId()
                    );
                }
            }
        }
    }

    static class RepositoryService {
        private final Map<Long, Customer> customers = new HashMap<>();
        private final Map<Long, Order> orders = new HashMap<>();
        private final Map<Long, OrderItem> items = new HashMap<>();

        private final Map<String, RelationshipPolicy> policies =
            new HashMap<>();

        private final List<IntegrityRule> integrityRules = List.of(
            new OrderCustomerRule(),
            new ItemOrderRule()
        );

        RepositoryService() {
            policies.put(
                "customer-order",
                new RelationshipPolicy(
                    "Customer",
                    "Order",
                    "customer_id",
                    DeleteAction.RESTRICT
                )
            );

            policies.put(
                "order-item",
                new RelationshipPolicy(
                    "Order",
                    "OrderItem",
                    "order_id",
                    DeleteAction.CASCADE
                )
            );
        }

        void addCustomer(Customer customer)
            throws ReferentialIntegrityException {

            if (customers.containsKey(customer.id())) {
                throw new ReferentialIntegrityException(
                    "Duplicate customer key: " + customer.id()
                );
            }

            customers.put(customer.id(), customer);
        }

        void addOrder(Order order)
            throws ReferentialIntegrityException {

            if (orders.containsKey(order.id())) {
                throw new ReferentialIntegrityException(
                    "Duplicate order key: " + order.id()
                );
            }

            if (!customers.containsKey(order.customerId())) {
                throw new ReferentialIntegrityException(
                    "Cannot create order " + order.id()
                    + ": customer " + order.customerId()
                    + " does not exist."
                );
            }

            orders.put(order.id(), order);
        }

        void addOrderItem(OrderItem item)
            throws ReferentialIntegrityException {

            if (items.containsKey(item.id())) {
                throw new ReferentialIntegrityException(
                    "Duplicate item key: " + item.id()
                );
            }

            if (!orders.containsKey(item.orderId())) {
                throw new ReferentialIntegrityException(
                    "Cannot create item " + item.id()
                    + ": order " + item.orderId()
                    + " does not exist."
                );
            }

            items.put(item.id(), item);
        }

        private List<Long> orderIdsForCustomer(long customerId) {
            return orders.values()
                .stream()
                .filter(order -> order.customerId() == customerId)
                .map(Order::id)
                .toList();
        }

        private List<Long> itemIdsForOrder(long orderId) {
            return items.values()
                .stream()
                .filter(item -> item.orderId() == orderId)
                .map(OrderItem::id)
                .toList();
        }

        void deleteOrder(long orderId)
            throws ReferentialIntegrityException {

            if (!orders.containsKey(orderId)) {
                throw new ReferentialIntegrityException(
                    "Order " + orderId + " does not exist."
                );
            }

            RelationshipPolicy policy = policies.get("order-item");
            List<Long> childIds = itemIdsForOrder(orderId);

            if (policy.onDelete() == DeleteAction.RESTRICT &&
                !childIds.isEmpty()) {
                throw new ReferentialIntegrityException(
                    "Order deletion blocked because dependent items exist."
                );
            }

            if (policy.onDelete() == DeleteAction.CASCADE) {
                childIds.forEach(items::remove);
            }

            if (policy.onDelete() == DeleteAction.SET_NULL) {
                /*
                 * The OrderItem record intentionally uses a mandatory orderId.
                 * SET NULL would require Optional<Long> or a nullable database
                 * column, so the current domain rejects this policy.
                 */
                throw new ReferentialIntegrityException(
                    "SET NULL conflicts with the mandatory orderId invariant."
                );
            }

            orders.remove(orderId);
        }

        void deleteCustomer(long customerId)
            throws ReferentialIntegrityException {

            if (!customers.containsKey(customerId)) {
                throw new ReferentialIntegrityException(
                    "Customer " + customerId + " does not exist."
                );
            }

            RelationshipPolicy policy = policies.get("customer-order");
            List<Long> childOrders = orderIdsForCustomer(customerId);

            if (policy.onDelete() == DeleteAction.RESTRICT &&
                !childOrders.isEmpty()) {
                throw new ReferentialIntegrityException(
                    "Customer deletion blocked by dependent orders: "
                    + childOrders
                );
            }

            if (policy.onDelete() == DeleteAction.CASCADE) {
                for (long orderId : childOrders) {
                    deleteOrder(orderId);
                }
            }

            if (policy.onDelete() == DeleteAction.SET_NULL) {
                throw new ReferentialIntegrityException(
                    "SET NULL requires Order.customerId to be nullable."
                );
            }

            customers.remove(customerId);
        }

        void reassignOrder(long orderId, long newCustomerId)
            throws ReferentialIntegrityException {

            Order current = orders.get(orderId);

            if (current == null) {
                throw new ReferentialIntegrityException(
                    "Order " + orderId + " does not exist."
                );
            }

            if (!customers.containsKey(newCustomerId)) {
                throw new ReferentialIntegrityException(
                    "Customer " + newCustomerId + " does not exist."
                );
            }

            orders.put(orderId, current.withCustomer(newCustomerId));
        }

        void validateAll()
            throws ReferentialIntegrityException {

            for (IntegrityRule rule : integrityRules) {
                rule.validate(customers, orders, items);
            }
        }

        void printPolicy(String relationshipName) {
            RelationshipPolicy policy = policies.get(relationshipName);

            System.out.println(
                relationshipName
                + ": "
                + policy.parentType()
                + " -> "
                + policy.childType()
                + ", foreign key="
                + policy.foreignKey()
                + ", ON DELETE="
                + policy.onDelete()
            );
        }

        void printState(String label) {
            System.out.println(
                label
                + " | customers=" + customers.size()
                + ", orders=" + orders.size()
                + ", items=" + items.size()
            );
        }
    }

    private static void demonstrateMandatoryRelationships()
        throws Exception {

        System.out.println("\n=== Mandatory foreign-key relationships ===");

        RepositoryService service = new RepositoryService();

        service.addCustomer(new Customer(1, "Enterprise Customer"));
        service.addOrder(
            new Order(
                100,
                1,
                new BigDecimal("15000.00")
            )
        );
        service.addOrderItem(
            new OrderItem(
                1000,
                100,
                "Industrial Controller",
                2
            )
        );

        service.validateAll();
        service.printState("Valid state");

        try {
            service.addOrder(
                new Order(
                    101,
                    999,
                    new BigDecimal("2000.00")
                )
            );
        } catch (ReferentialIntegrityException exception) {
            System.out.println(
                "Invalid order rejected: " + exception.getMessage()
            );
        }
    }

    private static void demonstrateRestrict()
        throws Exception {

        System.out.println("\n=== RESTRICT policy ===");

        RepositoryService service = new RepositoryService();

        service.addCustomer(new Customer(2, "Restricted Customer"));
        service.addOrder(
            new Order(
                200,
                2,
                new BigDecimal("3000.00")
            )
        );

        service.printPolicy("customer-order");

        try {
            service.deleteCustomer(2);
        } catch (ReferentialIntegrityException exception) {
            System.out.println(
                "Deletion blocked: " + exception.getMessage()
            );
        }

        service.deleteOrder(200);
        service.deleteCustomer(2);
        service.printState("After dependents are removed");
    }

    private static void demonstrateCascade()
        throws Exception {

        System.out.println("\n=== CASCADE policy ===");

        RepositoryService service = new RepositoryService();

        service.policies.put(
            "customer-order",
            new RelationshipPolicy(
                "Customer",
                "Order",
                "customer_id",
                DeleteAction.CASCADE
            )
        );

        service.addCustomer(new Customer(3, "Cascade Customer"));
        service.addOrder(
            new Order(300, 3, new BigDecimal("1000.00"))
        );
        service.addOrder(
            new Order(301, 3, new BigDecimal("2000.00"))
        );

        service.addOrderItem(
            new OrderItem(3000, 300, "Part A", 4)
        );
        service.addOrderItem(
            new OrderItem(3001, 301, "Part B", 6)
        );

        service.printState("Before transitive cascade");
        service.deleteCustomer(3);
        service.printState("After customer deletion");
        service.validateAll();
    }

    private static void demonstrateReassignment()
        throws Exception {

        System.out.println("\n=== Foreign-key reassignment ===");

        RepositoryService service = new RepositoryService();

        service.addCustomer(new Customer(10, "Customer A"));
        service.addCustomer(new Customer(11, "Customer B"));

        service.addOrder(
            new Order(1000, 10, new BigDecimal("7000.00"))
        );

        service.reassignOrder(1000, 11);
        service.validateAll();

        System.out.println(
            "Order 1000 now references customer 11."
        );
    }

    private static void demonstratePolicyConflict()
        throws Exception {

        System.out.println("\n=== SET NULL policy conflict ===");

        RepositoryService service = new RepositoryService();

        service.addCustomer(new Customer(20, "Nullable Test"));
        service.addOrder(
            new Order(2000, 20, new BigDecimal("900.00"))
        );
        service.addOrderItem(
            new OrderItem(20000, 2000, "Device", 1)
        );

        service.policies.put(
            "order-item",
            new RelationshipPolicy(
                "Order",
                "OrderItem",
                "order_id",
                DeleteAction.SET_NULL
            )
        );

        try {
            service.deleteOrder(2000);
        } catch (ReferentialIntegrityException exception) {
            System.out.println(
                "Policy rejected: " + exception.getMessage()
            );
        }
    }

    private static void demonstrateIntegrityBoundary() {
        System.out.println("\n=== Database integrity boundary ===");

        System.out.println(
            "Application validation can reject an orphan before a write, "
            + "but a relational database foreign key remains the authoritative "
            + "constraint when multiple applications or concurrent sessions "
            + "can modify the same data."
        );

        System.out.println(
            "Foreign-key columns should normally be indexed when parent "
            + "deletion checks, joins, and child lookups occur frequently."
        );
    }

    public static void main(String[] args) throws Exception {
        System.out.println(
            "REFERENTIAL INTEGRITY: FOREIGN KEYS AND CASCADING ACTIONS"
        );

        demonstrateMandatoryRelationships();
        demonstrateRestrict();
        demonstrateCascade();
        demonstrateReassignment();
        demonstratePolicyConflict();
        demonstrateIntegrityBoundary();

        System.out.println("\n=== Domain policies ===");

        RepositoryService service = new RepositoryService();
        service.printPolicy("customer-order");
        service.printPolicy("order-item");

        System.out.println(
            "\nThe model distinguishes the existence constraint imposed by "
            + "a foreign key from the action selected when its parent changes."
        );
    }
}
