import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/*
 * Normalization II: 1NF, 2NF, and 3NF
 *
 * Enterprise-oriented case study:
 * An order-management service stores customers, orders, products, and
 * order-line quantities. The program models the progression from an
 * unnormalized structure through 1NF, 2NF, and finally 3NF.
 *
 * Compile and run:
 *   javac NormalizationII.java
 *   java NormalizationII
 */

public class NormalizationII {

    record Customer(
        String customerId,
        String customerName,
        String customerCity
    ) {}

    record Product(
        String productId,
        String productName
    ) {}

    record Order(
        int orderId,
        String orderDate,
        String customerId
    ) {}

    record OrderItem(
        int orderId,
        String productId,
        int quantity
    ) {}

    record RawProduct(
        String productId,
        String productName,
        int quantity
    ) {}

    record RawOrder(
        int orderId,
        String orderDate,
        String customerId,
        String customerName,
        String customerCity,
        List<RawProduct> products
    ) {}

    enum NormalForm {
        UNNORMALIZED,
        FIRST_NORMAL_FORM,
        SECOND_NORMAL_FORM,
        THIRD_NORMAL_FORM
    }

    static final class ValidationException extends Exception {
        ValidationException(String message) {
            super(message);
        }
    }

    interface RelationValidator<T> {
        void validate(T value) throws ValidationException;
    }

    static final class CustomerValidator
            implements RelationValidator<Customer> {

        @Override
        public void validate(Customer customer)
                throws ValidationException {

            if (customer.customerId() == null ||
                customer.customerId().isBlank()) {
                throw new ValidationException(
                    "Customer ID must not be blank."
                );
            }

            if (customer.customerName() == null ||
                customer.customerName().isBlank()) {
                throw new ValidationException(
                    "Customer name must not be blank."
                );
            }

            if (customer.customerCity() == null ||
                customer.customerCity().isBlank()) {
                throw new ValidationException(
                    "Customer city must not be blank."
                );
            }
        }
    }

    static final class ProductValidator
            implements RelationValidator<Product> {

        @Override
        public void validate(Product product)
                throws ValidationException {

            if (product.productId() == null ||
                product.productId().isBlank()) {
                throw new ValidationException(
                    "Product ID must not be blank."
                );
            }

            if (product.productName() == null ||
                product.productName().isBlank()) {
                throw new ValidationException(
                    "Product name must not be blank."
                );
            }
        }
    }

    static final class OrderItemValidator
            implements RelationValidator<OrderItem> {

        @Override
        public void validate(OrderItem item)
                throws ValidationException {

            if (item.quantity() <= 0) {
                throw new ValidationException(
                    "Order-item quantity must be greater than zero."
                );
            }
        }
    }

    static final class Repository {

        private final Map<String, Customer> customers = new HashMap<>();
        private final Map<String, Product> products = new HashMap<>();
        private final Map<Integer, Order> orders = new HashMap<>();
        private final Map<String, OrderItem> orderItems = new HashMap<>();

        private final CustomerValidator customerValidator =
            new CustomerValidator();

        private final ProductValidator productValidator =
            new ProductValidator();

        private final OrderItemValidator orderItemValidator =
            new OrderItemValidator();

        void addCustomer(Customer customer)
                throws ValidationException {

            customerValidator.validate(customer);

            if (customers.containsKey(customer.customerId())) {
                throw new ValidationException(
                    "Duplicate customer primary key: "
                    + customer.customerId()
                );
            }

            customers.put(customer.customerId(), customer);
        }

        void addProduct(Product product)
                throws ValidationException {

            productValidator.validate(product);

            if (products.containsKey(product.productId())) {
                throw new ValidationException(
                    "Duplicate product primary key: "
                    + product.productId()
                );
            }

            products.put(product.productId(), product);
        }

        void addOrder(Order order)
                throws ValidationException {

            if (orders.containsKey(order.orderId())) {
                throw new ValidationException(
                    "Duplicate order primary key: "
                    + order.orderId()
                );
            }

            if (!customers.containsKey(order.customerId())) {
                throw new ValidationException(
                    "Customer foreign key does not exist: "
                    + order.customerId()
                );
            }

            orders.put(order.orderId(), order);
        }

        void addOrderItem(OrderItem item)
                throws ValidationException {

            orderItemValidator.validate(item);

            String key = orderItemKey(item.orderId(), item.productId());

            if (orderItems.containsKey(key)) {
                throw new ValidationException(
                    "Duplicate OrderItems composite key: " + key
                );
            }

            if (!orders.containsKey(item.orderId())) {
                throw new ValidationException(
                    "Order foreign key does not exist: "
                    + item.orderId()
                );
            }

            if (!products.containsKey(item.productId())) {
                throw new ValidationException(
                    "Product foreign key does not exist: "
                    + item.productId()
                );
            }

            orderItems.put(key, item);
        }

        void updateCustomerCity(
                String customerId,
                String newCity
        ) throws ValidationException {

            Customer existing = customers.get(customerId);

            if (existing == null) {
                throw new ValidationException(
                    "Cannot update an unknown customer."
                );
            }

            if (newCity == null || newCity.isBlank()) {
                throw new ValidationException(
                    "Customer city must not be blank."
                );
            }

            /*
             * Because customer facts have their own determinant and relation,
             * one immutable record can be replaced instead of rewriting
             * customer attributes duplicated across Orders.
             */
            customers.put(
                customerId,
                new Customer(
                    existing.customerId(),
                    existing.customerName(),
                    newCity
                )
            );
        }

        List<String> businessView() {
            List<OrderItem> sortedItems = new ArrayList<>(orderItems.values());

            sortedItems.sort(
                (left, right) -> {
                    int orderComparison =
                        Integer.compare(left.orderId(), right.orderId());

                    if (orderComparison != 0) {
                        return orderComparison;
                    }

                    return left.productId().compareTo(right.productId());
                }
            );

            List<String> output = new ArrayList<>();

            for (OrderItem item : sortedItems) {
                Order order = orders.get(item.orderId());
                Customer customer = customers.get(order.customerId());
                Product product = products.get(item.productId());

                output.add(
                    "%d | %s | %s | %s | %d".formatted(
                        order.orderId(),
                        customer.customerName(),
                        customer.customerCity(),
                        product.productName(),
                        item.quantity()
                    )
                );
            }

            return output;
        }

        private static String orderItemKey(
                int orderId,
                String productId
        ) {
            return orderId + "::" + productId;
        }

        void printCardinality() {
            System.out.println(
                "Customers: " + customers.size()
                + ", Orders: " + orders.size()
                + ", Products: " + products.size()
                + ", OrderItems: " + orderItems.size()
            );
        }
    }

    static List<RawOrder> rawOrders() {
        return List.of(
            new RawOrder(
                1001,
                "2026-10-01",
                "C001",
                "Asha Rao",
                "Lucknow",
                List.of(
                    new RawProduct("P101", "Keyboard", 2),
                    new RawProduct("P102", "Mouse", 1)
                )
            ),
            new RawOrder(
                1002,
                "2026-10-02",
                "C002",
                "Rohan Mehta",
                "Delhi",
                List.of(
                    new RawProduct("P101", "Keyboard", 1)
                )
            )
        );
    }

    static List<Map<String, Object>> flattenTo1NF(
            List<RawOrder> source
    ) {
        List<Map<String, Object>> rows = new ArrayList<>();

        for (RawOrder order : source) {
            for (RawProduct product : order.products()) {
                if (product.quantity() <= 0) {
                    throw new IllegalArgumentException(
                        "Quantity must be positive."
                    );
                }

                Map<String, Object> row = new HashMap<>();

                row.put("orderId", order.orderId());
                row.put("orderDate", order.orderDate());
                row.put("customerId", order.customerId());
                row.put("customerName", order.customerName());
                row.put("customerCity", order.customerCity());
                row.put("productId", product.productId());
                row.put("productName", product.productName());
                row.put("quantity", product.quantity());

                rows.add(row);
            }
        }

        return rows;
    }

    static List<Order> decomposeOrders(
            List<Map<String, Object>> rows
    ) throws ValidationException {

        Map<Integer, Order> result = new HashMap<>();

        for (Map<String, Object> row : rows) {
            int orderId = (Integer) row.get("orderId");

            Order candidate = new Order(
                orderId,
                (String) row.get("orderDate"),
                (String) row.get("customerId")
            );

            if (result.containsKey(orderId) &&
                !result.get(orderId).equals(candidate)) {
                throw new ValidationException(
                    "orderId does not determine one consistent order."
                );
            }

            result.put(orderId, candidate);
        }

        return new ArrayList<>(result.values());
    }

    static List<Product> decomposeProducts(
            List<Map<String, Object>> rows
    ) throws ValidationException {

        Map<String, Product> result = new HashMap<>();

        for (Map<String, Object> row : rows) {
            String productId = (String) row.get("productId");
            Product candidate = new Product(
                productId,
                (String) row.get("productName")
            );

            if (result.containsKey(productId) &&
                !result.get(productId).equals(candidate)) {
                throw new ValidationException(
                    "productId does not determine one product name."
                );
            }

            result.put(productId, candidate);
        }

        return new ArrayList<>(result.values());
    }

    static List<OrderItem> decomposeOrderItems(
            List<Map<String, Object>> rows
    ) {
        List<OrderItem> result = new ArrayList<>();

        for (Map<String, Object> row : rows) {
            result.add(
                new OrderItem(
                    (Integer) row.get("orderId"),
                    (String) row.get("productId"),
                    (Integer) row.get("quantity")
                )
            );
        }

        return result;
    }

    static List<Customer> decomposeCustomers(
            List<RawOrder> source
    ) throws ValidationException {

        Map<String, Customer> result = new HashMap<>();

        for (RawOrder order : source) {
            Customer candidate = new Customer(
                order.customerId(),
                order.customerName(),
                order.customerCity()
            );

            Customer previous = result.putIfAbsent(
                candidate.customerId(),
                candidate
            );

            if (previous != null && !previous.equals(candidate)) {
                throw new ValidationException(
                    "customerId does not determine one customer."
                );
            }
        }

        return new ArrayList<>(result.values());
    }

    static void explainNormalForms() {
        System.out.println(
            "1NF: repeating groups are removed and values are atomic."
        );
        System.out.println(
            "2NF: non-key attributes depend on the whole candidate key, "
            + "not only part of a composite key."
        );
        System.out.println(
            "3NF: non-key attributes do not depend transitively on a "
            + "candidate key through another non-key determinant."
        );
    }

    static void demonstrateAnomalies() {
        System.out.println("\nAnomaly analysis:");
        System.out.println(
            "Update: customer facts have one authoritative row."
        );
        System.out.println(
            "Insertion: products can exist before an order references them."
        );
        System.out.println(
            "Deletion: removing an order item does not remove product master data."
        );
    }

    static void demonstrateFailureStates(Repository repository) {
        System.out.println("\nFailure-state demonstrations:");

        try {
            repository.addOrderItem(
                new OrderItem(1001, "P101", 4)
            );
        } catch (ValidationException ex) {
            System.out.println("Duplicate key rejected: " + ex.getMessage());
        }

        try {
            repository.addOrderItem(
                new OrderItem(1001, "P999", 1)
            );
        } catch (ValidationException ex) {
            System.out.println("Foreign-key failure rejected: "
                + ex.getMessage());
        }

        try {
            repository.addOrderItem(
                new OrderItem(1001, "P101", -1)
            );
        } catch (ValidationException ex) {
            System.out.println("Domain constraint rejected: "
                + ex.getMessage());
        }
    }

    public static void main(String[] args) {
        try {
            System.out.println(
                "NORMALIZATION II: 1NF -> 2NF -> 3NF"
            );
            explainNormalForms();

            List<RawOrder> source = rawOrders();

            System.out.println(
                "\nThe unnormalized representation stores a List<RawProduct> "
                + "inside each RawOrder."
            );

            List<Map<String, Object>> firstNF =
                flattenTo1NF(source);

            System.out.println(
                "\n1NF rows: " + firstNF.size()
            );
            System.out.println(
                "Composite key: (orderId, productId)"
            );

            List<Order> secondNFOrders =
                decomposeOrders(firstNF);

            List<Product> products =
                decomposeProducts(firstNF);

            List<OrderItem> orderItems =
                decomposeOrderItems(firstNF);

            System.out.println(
                "\n2NF decomposition separates order-level and "
                + "product-level dependencies."
            );
            System.out.println(
                "Orders: " + secondNFOrders.size()
                + ", Products: " + products.size()
                + ", OrderItems: " + orderItems.size()
            );

            /*
             * The source data is used here to extract customer facts because
             * those facts are identified by customerId, not orderId.
             */
            List<Customer> customers =
                decomposeCustomers(source);

            System.out.println(
                "\n3NF decomposition separates customer facts from Orders."
            );
            System.out.println(
                "Customers: " + customers.size()
            );

            Repository repository = new Repository();

            for (Customer customer : customers) {
                repository.addCustomer(customer);
            }

            for (Product product : products) {
                repository.addProduct(product);
            }

            for (Order order : secondNFOrders) {
                repository.addOrder(order);
            }

            for (OrderItem item : orderItems) {
                repository.addOrderItem(item);
            }

            System.out.println("\nNormalized repository:");
            repository.printCardinality();

            System.out.println(
                "\nReconstructed business view:"
            );

            for (String line : repository.businessView()) {
                System.out.println(line);
            }

            System.out.println(
                "\nUpdating C001's city from the Customer relation..."
            );

            repository.updateCustomerCity("C001", "Kanpur");

            for (String line : repository.businessView()) {
                System.out.println(line);
            }

            demonstrateAnomalies();
            demonstrateFailureStates(repository);

            System.out.println(
                "\nFinal relations:"
                + "\nCustomers(customerId, customerName, customerCity)"
                + "\nOrders(orderId, orderDate, customerId)"
                + "\nProducts(productId, productName)"
                + "\nOrderItems(orderId, productId, quantity)"
            );

        } catch (ValidationException | IllegalArgumentException ex) {
            System.err.println("Validation failure: " + ex.getMessage());
        }
    }
}
