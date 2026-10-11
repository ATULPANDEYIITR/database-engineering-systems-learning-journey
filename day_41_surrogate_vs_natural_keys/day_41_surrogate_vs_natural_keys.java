import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

/*
 * Enterprise repository-independent customer identity governance model.
 *
 * Compile and run:
 *   javac KeysDesignLab.java
 *   java KeysDesignLab
 *
 * The example distinguishes stable internal identity from mutable business
 * identifiers and uses explicit domain rules to prevent conflicting mappings.
 */

public class KeysDesignLab {

    enum IdentifierType {
        SURROGATE,
        NATURAL,
        EXTERNAL
    }

    record NaturalCustomerKey(String countryCode, String taxIdentifier) {
        NaturalCustomerKey {
            countryCode = Objects.requireNonNull(countryCode)
                    .trim().toUpperCase();
            taxIdentifier = Objects.requireNonNull(taxIdentifier).trim();

            if (!countryCode.matches("[A-Z]{2}")) {
                throw new IllegalArgumentException(
                        "Country code must contain two ASCII letters.");
            }
            if (taxIdentifier.isEmpty()) {
                throw new IllegalArgumentException(
                        "Tax identifier cannot be empty.");
            }
        }
    }

    record SourceKey(String system, String recordId) {
        SourceKey {
            system = Objects.requireNonNull(system).trim().toLowerCase();
            recordId = Objects.requireNonNull(recordId).trim();

            if (system.isEmpty() || recordId.isEmpty()) {
                throw new IllegalArgumentException(
                        "Source system and record ID are required.");
            }
        }
    }

    record Customer(long id, String legalName, NaturalCustomerKey naturalKey) {
        Customer {
            if (id <= 0) {
                throw new IllegalArgumentException(
                        "Surrogate customer ID must be positive.");
            }
            legalName = Objects.requireNonNull(legalName).trim();
            Objects.requireNonNull(naturalKey);

            if (legalName.isEmpty()) {
                throw new IllegalArgumentException(
                        "Legal name cannot be empty.");
            }
        }
    }

    record Order(
            UUID id,
            long customerId,
            SourceKey sourceKey,
            long amountMinorUnits
    ) {
        Order {
            Objects.requireNonNull(id);
            Objects.requireNonNull(sourceKey);

            if (customerId <= 0) {
                throw new IllegalArgumentException(
                        "Customer ID must be positive.");
            }
            if (amountMinorUnits < 0) {
                throw new IllegalArgumentException(
                        "Amount cannot be negative.");
            }
        }
    }

    static final class IdentityConflictException extends RuntimeException {
        IdentityConflictException(String message) {
            super(message);
        }
    }

    static final class CustomerIdentityService {
        private long nextId = 1;

        private final Map<Long, Customer> customersById = new HashMap<>();
        private final Map<NaturalCustomerKey, Long> idByNaturalKey =
                new HashMap<>();
        private final Map<SourceKey, Long> idBySourceKey = new HashMap<>();

        Customer register(
                String legalName,
                NaturalCustomerKey naturalKey,
                SourceKey sourceKey
        ) {
            Objects.requireNonNull(naturalKey);
            Objects.requireNonNull(sourceKey);

            if (idByNaturalKey.containsKey(naturalKey)) {
                throw new IdentityConflictException(
                        "Natural customer key is already registered.");
            }
            if (idBySourceKey.containsKey(sourceKey)) {
                throw new IdentityConflictException(
                        "External source key is already mapped.");
            }

            // A database-generated identity should replace this local
            // allocator in a multi-process deployment.
            long id = nextId++;
            Customer customer = new Customer(id, legalName, naturalKey);

            customersById.put(id, customer);
            idByNaturalKey.put(naturalKey, id);
            idBySourceKey.put(sourceKey, id);
            return customer;
        }

        Customer findById(long id) {
            Customer customer = customersById.get(id);
            if (customer == null) {
                throw new IdentityConflictException(
                        "Customer surrogate ID does not exist.");
            }
            return customer;
        }

        Customer findByNaturalKey(NaturalCustomerKey naturalKey) {
            Long id = idByNaturalKey.get(naturalKey);
            if (id == null) {
                throw new IdentityConflictException(
                        "Natural key is not registered.");
            }
            return findById(id);
        }

        Customer correctNaturalKey(long customerId, NaturalCustomerKey newKey) {
            Customer existing = findById(customerId);
            Objects.requireNonNull(newKey);

            Long owner = idByNaturalKey.get(newKey);
            if (owner != null && owner != customerId) {
                throw new IdentityConflictException(
                        "Replacement natural key belongs to another customer.");
            }

            // Build the replacement before changing the indexes. The surrogate
            // ID stays constant, so orders and other relationships remain valid.
            Customer updated = new Customer(
                    existing.id(),
                    existing.legalName(),
                    newKey
            );

            idByNaturalKey.remove(existing.naturalKey());
            idByNaturalKey.put(newKey, customerId);
            customersById.put(customerId, updated);
            return updated;
        }

        long resolveOrRegisterExternalMapping(
                SourceKey sourceKey,
                long customerId
        ) {
            findById(customerId);
            Long current = idBySourceKey.get(sourceKey);

            if (current != null && current != customerId) {
                throw new IdentityConflictException(
                        "Source identity is already assigned to another customer.");
            }

            idBySourceKey.putIfAbsent(sourceKey, customerId);
            return customerId;
        }

        int size() {
            return customersById.size();
        }
    }

    static final class OrderService {
        private final CustomerIdentityService customerService;
        private final Map<UUID, Order> ordersById = new HashMap<>();
        private final Map<SourceKey, UUID> orderIdBySourceKey = new HashMap<>();
        private final Map<Long, Set<UUID>> orderIdsByCustomer = new HashMap<>();

        OrderService(CustomerIdentityService customerService) {
            this.customerService = Objects.requireNonNull(customerService);
        }

        Order ingest(
                long customerId,
                SourceKey sourceKey,
                long amountMinorUnits
        ) {
            customerService.findById(customerId);

            if (amountMinorUnits < 0) {
                throw new IllegalArgumentException(
                        "Order amount cannot be negative.");
            }

            UUID existingId = orderIdBySourceKey.get(sourceKey);
            if (existingId != null) {
                Order existing = ordersById.get(existingId);

                if (existing.customerId() != customerId
                        || existing.amountMinorUnits() != amountMinorUnits) {
                    throw new IdentityConflictException(
                            "Duplicate source event contains conflicting values.");
                }
                return existing;
            }

            Order order = new Order(
                    UUID.randomUUID(),
                    customerId,
                    sourceKey,
                    amountMinorUnits
            );

            ordersById.put(order.id(), order);
            orderIdBySourceKey.put(sourceKey, order.id());
            orderIdsByCustomer
                    .computeIfAbsent(customerId, ignored -> new HashSet<>())
                    .add(order.id());

            return order;
        }

        List<Order> findForCustomer(long customerId) {
            Set<UUID> ids = orderIdsByCustomer.getOrDefault(
                    customerId, Set.of());

            List<Order> result = new ArrayList<>();
            for (UUID id : ids) {
                result.add(ordersById.get(id));
            }
            return List.copyOf(result);
        }
    }

    public static void main(String[] args) {
        CustomerIdentityService identities = new CustomerIdentityService();
        OrderService orders = new OrderService(identities);

        NaturalCustomerKey originalTaxKey =
                new NaturalCustomerKey("in", "GST-29-ACME-001");
        SourceKey sourceKey = new SourceKey("erp-east", "CUST-0044");

        Customer customer = identities.register(
                "Northern Industrial Supplies",
                originalTaxKey,
                sourceKey
        );

        Order firstOrder = orders.ingest(
                customer.id(),
                new SourceKey("erp-east", "ORDER-8801"),
                720050
        );

        Order retry = orders.ingest(
                customer.id(),
                new SourceKey("erp-east", "ORDER-8801"),
                720050
        );

        System.out.println("Customer ID: " + customer.id());
        System.out.println("Order ID: " + firstOrder.id());
        System.out.println("Idempotent retry: "
                + firstOrder.id().equals(retry.id()));

        Customer corrected = identities.correctNaturalKey(
                customer.id(),
                new NaturalCustomerKey("IN", "GST-29-ACME-009")
        );

        System.out.println("Corrected natural key: " + corrected.naturalKey());
        System.out.println("Surrogate identity unchanged: "
                + (customer.id() == corrected.id()));
        System.out.println("Existing orders preserved: "
                + orders.findForCustomer(customer.id()).size());

        try {
            identities.register(
                    "Duplicate Entity",
                    corrected.naturalKey(),
                    new SourceKey("erp-west", "CUST-9120")
            );
        } catch (IdentityConflictException error) {
            System.out.println("Duplicate registration rejected: "
                    + error.getMessage());
        }

        try {
            orders.ingest(
                    customer.id(),
                    new SourceKey("erp-east", "ORDER-8801"),
                    1
            );
        } catch (IdentityConflictException error) {
            System.out.println("Conflicting retry rejected: "
                    + error.getMessage());
        }

        try {
            identities.findById(9999);
        } catch (IdentityConflictException error) {
            System.out.println("Invalid surrogate reference rejected: "
                    + error.getMessage());
        }

        System.out.println("Registered customers: " + identities.size());
        System.out.println("Identifier categories: "
                + List.of(IdentifierType.SURROGATE,
                          IdentifierType.NATURAL,
                          IdentifierType.EXTERNAL));
    }
}
