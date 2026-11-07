import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/*
 * Hash Indexing: Enterprise Customer and Transaction Access
 *
 * Java 17 implementation covering:
 * - HashMap and ConcurrentHashMap
 * - Generic separate chaining
 * - Collision handling
 * - Open addressing
 * - Dynamic resizing
 * - Transaction lookup
 * - Data validation
 * - Index policies
 * - Hash distribution statistics
 * - Immutable domain records
 * - Automated tests
 */

public class HashIndexingDemo {

    enum TransactionStatus {
        PENDING,
        APPROVED,
        REJECTED,
        SETTLED
    }

    enum IndexStatus {
        ACTIVE,
        REBUILDING,
        DISABLED
    }

    record Customer(
        String customerId,
        String name,
        String department
    ) {
        Customer {
            if (customerId == null ||
                !customerId.matches("CUST-\\d{4,}")) {
                throw new IllegalArgumentException(
                    "Invalid customer ID."
                );
            }

            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Customer name is required."
                );
            }

            if (department == null || department.isBlank()) {
                throw new IllegalArgumentException(
                    "Department is required."
                );
            }
        }
    }

    record Transaction(
        String transactionId,
        String accountId,
        double amount,
        TransactionStatus status
    ) {
        Transaction {
            if (transactionId == null ||
                !transactionId.matches("TX-\\d{4,}")) {
                throw new IllegalArgumentException(
                    "Invalid transaction ID."
                );
            }

            if (accountId == null || accountId.isBlank()) {
                throw new IllegalArgumentException(
                    "Account ID is required."
                );
            }

            if (!Double.isFinite(amount) || amount < 0) {
                throw new IllegalArgumentException(
                    "Invalid transaction amount."
                );
            }

            Objects.requireNonNull(
                status,
                "Transaction status is required."
            );
        }
    }

    record IndexPolicy(
        double maximumLoadFactor,
        int initialCapacity,
        boolean allowUpdates
    ) {
        IndexPolicy {
            if (maximumLoadFactor < 0.25 ||
                maximumLoadFactor > 2.0) {
                throw new IllegalArgumentException(
                    "Invalid load factor."
                );
            }

            if (initialCapacity < 2) {
                throw new IllegalArgumentException(
                    "Capacity must be at least 2."
                );
            }
        }
    }

    record IndexStatistics(
        int capacity,
        int size,
        double loadFactor,
        int occupiedBuckets,
        int maximumChainLength,
        long collisions
    ) {}


    static class IndexException extends RuntimeException {
        IndexException(String message) {
            super(message);
        }
    }


    interface KeyValueIndex<K, V> {
        void put(K key, V value);

        Optional<V> find(K key);

        boolean delete(K key);

        int size();

        IndexStatistics statistics();
    }


    /*
     * Separate chaining with dynamic resizing.
     */
    static class ChainedHashIndex<K, V>
            implements KeyValueIndex<K, V> {

        private List<List<Map.Entry<K, V>>> buckets;
        private int size;
        private final IndexPolicy policy;
        private long collisions;

        ChainedHashIndex(IndexPolicy policy) {
            this.policy = Objects.requireNonNull(policy);

            buckets = new ArrayList<>();

            for (int i = 0; i < policy.initialCapacity(); i++) {
                buckets.add(new ArrayList<>());
            }
        }

        private void validateKey(K key) {
            if (key == null) {
                throw new IllegalArgumentException(
                    "Null keys are not permitted."
                );
            }
        }

        private int index(K key) {
            return Math.floorMod(
                key.hashCode(),
                buckets.size()
            );
        }

        private int findPosition(List<Map.Entry<K, V>> bucket, K key) {
            for (int i = 0; i < bucket.size(); i++) {
                if (bucket.get(i).getKey().equals(key)) {
                    return i;
                }
            }

            return -1;
        }

        @Override
        public void put(K key, V value) {
            validateKey(key);
            Objects.requireNonNull(value, "Null values are not permitted.");

            int index = index(key);
            List<Map.Entry<K, V>> bucket = buckets.get(index);

            int position = findPosition(bucket, key);

            if (position >= 0) {
                if (!policy.allowUpdates()) {
                    throw new IndexException(
                        "Updating existing keys is disabled."
                    );
                }

                bucket.set(
                    position,
                    Map.entry(key, value)
                );

                return;
            }

            if (
                (double) (size + 1) / buckets.size()
                    > policy.maximumLoadFactor()
            ) {
                resize(buckets.size() * 2);
                index = index(key);
                bucket = buckets.get(index);
            }

            if (!bucket.isEmpty()) {
                collisions++;
            }

            bucket.add(Map.entry(key, value));
            size++;
        }

        @Override
        public Optional<V> find(K key) {
            validateKey(key);

            List<Map.Entry<K, V>> bucket =
                buckets.get(index(key));

            int position = findPosition(bucket, key);

            return position < 0
                ? Optional.empty()
                : Optional.of(bucket.get(position).getValue());
        }

        @Override
        public boolean delete(K key) {
            validateKey(key);

            List<Map.Entry<K, V>> bucket =
                buckets.get(index(key));

            int position = findPosition(bucket, key);

            if (position < 0) {
                return false;
            }

            bucket.remove(position);
            size--;

            return true;
        }

        private void resize(int newCapacity) {
            List<List<Map.Entry<K, V>>> oldBuckets = buckets;

            buckets = new ArrayList<>();

            for (int i = 0; i < newCapacity; i++) {
                buckets.add(new ArrayList<>());
            }

            size = 0;

            for (List<Map.Entry<K, V>> bucket : oldBuckets) {
                for (Map.Entry<K, V> entry : bucket) {
                    int newIndex = index(entry.getKey());

                    buckets.get(newIndex).add(entry);
                    size++;
                }
            }
        }

        @Override
        public int size() {
            return size;
        }

        @Override
        public IndexStatistics statistics() {
            int occupied = 0;
            int maximumChain = 0;

            for (List<Map.Entry<K, V>> bucket : buckets) {
                if (!bucket.isEmpty()) {
                    occupied++;
                }

                maximumChain = Math.max(
                    maximumChain,
                    bucket.size()
                );
            }

            return new IndexStatistics(
                buckets.size(),
                size,
                (double) size / buckets.size(),
                occupied,
                maximumChain,
                collisions
            );
        }
    }


    /*
     * Open addressing with linear probing.
     * Tombstones preserve search paths after deletion.
     */
    static class LinearProbingIndex<K, V> {

        private enum State {
            EMPTY,
            OCCUPIED,
            DELETED
        }

        private static class Slot<K, V> {
            State state = State.EMPTY;
            K key;
            V value;
        }

        private Slot<K, V>[] slots;
        private int size;
        private int deleted;

        @SuppressWarnings("unchecked")
        LinearProbingIndex(int capacity) {
            if (capacity < 2) {
                throw new IllegalArgumentException(
                    "Capacity must be at least 2."
                );
            }

            slots = (Slot<K, V>[]) new Slot[capacity];

            for (int i = 0; i < capacity; i++) {
                slots[i] = new Slot<>();
            }
        }

        private int index(K key) {
            Objects.requireNonNull(key, "Null keys are prohibited.");

            return Math.floorMod(
                key.hashCode(),
                slots.length
            );
        }

        void put(K key, V value) {
            Objects.requireNonNull(value, "Null values are prohibited.");

            if (
                (double) (size + deleted + 1) / slots.length > 0.65
            ) {
                resize(slots.length * 2);
            }

            int start = index(key);
            int firstDeleted = -1;

            for (int offset = 0; offset < slots.length; offset++) {
                int position = (start + offset) % slots.length;
                Slot<K, V> slot = slots[position];

                if (slot.state == State.OCCUPIED) {
                    if (slot.key.equals(key)) {
                        slot.value = value;
                        return;
                    }

                    continue;
                }

                if (slot.state == State.DELETED) {
                    if (firstDeleted == -1) {
                        firstDeleted = position;
                    }

                    continue;
                }

                int target = firstDeleted >= 0
                    ? firstDeleted
                    : position;

                if (firstDeleted >= 0) {
                    deleted--;
                }

                slots[target].key = key;
                slots[target].value = value;
                slots[target].state = State.OCCUPIED;

                size++;
                return;
            }

            if (firstDeleted >= 0) {
                Slot<K, V> slot = slots[firstDeleted];

                slot.key = key;
                slot.value = value;
                slot.state = State.OCCUPIED;

                deleted--;
                size++;
                return;
            }

            resize(slots.length * 2);
            put(key, value);
        }

        Optional<V> find(K key) {
            int start = index(key);

            for (int offset = 0; offset < slots.length; offset++) {
                int position = (start + offset) % slots.length;
                Slot<K, V> slot = slots[position];

                if (slot.state == State.EMPTY) {
                    return Optional.empty();
                }

                if (
                    slot.state == State.OCCUPIED &&
                    slot.key.equals(key)
                ) {
                    return Optional.of(slot.value);
                }
            }

            return Optional.empty();
        }

        boolean delete(K key) {
            int start = index(key);

            for (int offset = 0; offset < slots.length; offset++) {
                int position = (start + offset) % slots.length;
                Slot<K, V> slot = slots[position];

                if (slot.state == State.EMPTY) {
                    return false;
                }

                if (
                    slot.state == State.OCCUPIED &&
                    slot.key.equals(key)
                ) {
                    slot.state = State.DELETED;
                    slot.key = null;
                    slot.value = null;

                    size--;
                    deleted++;

                    return true;
                }
            }

            return false;
        }

        @SuppressWarnings("unchecked")
        private void resize(int capacity) {
            Slot<K, V>[] oldSlots = slots;

            slots = (Slot<K, V>[]) new Slot[capacity];

            for (int i = 0; i < capacity; i++) {
                slots[i] = new Slot<>();
            }

            size = 0;
            deleted = 0;

            for (Slot<K, V> slot : oldSlots) {
                if (slot.state == State.OCCUPIED) {
                    put(slot.key, slot.value);
                }
            }
        }

        int size() {
            return size;
        }

        double loadFactor() {
            return (double) size / slots.length;
        }
    }


    /*
     * Concurrent directory using Java's concurrent hash map.
     * Compound business operations must still be coordinated
     * separately when they involve multiple records.
     */
    static class EnterpriseCustomerService {

        private final ConcurrentHashMap<String, Customer> customers =
            new ConcurrentHashMap<>();

        void register(Customer customer) {
            Objects.requireNonNull(customer);

            Customer previous = customers.putIfAbsent(
                customer.customerId(),
                customer
            );

            if (previous != null) {
                throw new IndexException(
                    "Customer ID already exists."
                );
            }
        }

        Optional<Customer> find(String customerId) {
            return Optional.ofNullable(
                customers.get(customerId)
            );
        }

        boolean remove(String customerId) {
            return customers.remove(customerId) != null;
        }

        List<Customer> findByDepartment(String department) {
            return customers.values()
                .stream()
                .filter(
                    customer -> customer.department()
                        .equalsIgnoreCase(department)
                )
                .toList();
        }

        int size() {
            return customers.size();
        }
    }


    static String sha256(String value) {
        try {
            MessageDigest digest =
                MessageDigest.getInstance("SHA-256");

            byte[] bytes = digest.digest(
                value.getBytes(StandardCharsets.UTF_8)
            );

            StringBuilder result = new StringBuilder();

            for (byte item : bytes) {
                result.append(
                    String.format("%02x", item & 0xff)
                );
            }

            return result.toString();

        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException(
                "SHA-256 is unavailable.",
                exception
            );
        }
    }


    static void demonstrateStandardHashMap() {
        System.out.println("\nSTANDARD HASH MAP");

        Map<String, String> departments = new HashMap<>();

        departments.put("EMP-101", "Engineering");
        departments.put("EMP-102", "Security");
        departments.put("EMP-103", "Research");

        System.out.println(
            "EMP-102: " + departments.get("EMP-102")
        );

        System.out.println(
            "Missing key: " + departments.get("EMP-999")
        );

        System.out.println(
            "Contains employee: " + departments.containsKey("EMP-101")
        );
    }


    static void demonstrateChaining() {
        System.out.println("\nSEPARATE CHAINING");

        IndexPolicy policy = new IndexPolicy(
            0.75,
            4,
            true
        );

        ChainedHashIndex<String, Transaction> index =
            new ChainedHashIndex<>(policy);

        List<Transaction> transactions = List.of(
            new Transaction(
                "TX-1001", "ACC-101",
                12500.0, TransactionStatus.APPROVED
            ),
            new Transaction(
                "TX-1002", "ACC-102",
                8500.0, TransactionStatus.PENDING
            ),
            new Transaction(
                "TX-1003", "ACC-103",
                24000.0, TransactionStatus.SETTLED
            ),
            new Transaction(
                "TX-1004", "ACC-104",
                5200.0, TransactionStatus.REJECTED
            ),
            new Transaction(
                "TX-1005", "ACC-105",
                17500.0, TransactionStatus.APPROVED
            )
        );

        for (Transaction transaction : transactions) {
            index.put(
                transaction.transactionId(),
                transaction
            );
        }

        index.find("TX-1003").ifPresent(
            transaction -> System.out.println(
                "Retrieved transaction: " + transaction
            )
        );

        System.out.println(
            "Index statistics: " + index.statistics()
        );

        index.delete("TX-1002");

        System.out.println(
            "After deletion: " + index.size()
        );
    }


    static void demonstrateOpenAddressing() {
        System.out.println("\nOPEN ADDRESSING");

        LinearProbingIndex<String, String> index =
            new LinearProbingIndex<>(8);

        index.put("ACC-101", "ACTIVE");
        index.put("ACC-102", "SUSPENDED");
        index.put("ACC-103", "ACTIVE");

        index.delete("ACC-102");

        index.put("ACC-104", "ACTIVE");

        System.out.println(
            "ACC-103: " + index.find("ACC-103")
        );

        System.out.println(
            "ACC-104: " + index.find("ACC-104")
        );

        System.out.println(
            "Load factor: " + index.loadFactor()
        );
    }


    static void demonstrateConcurrentAccess() {
        System.out.println("\nCONCURRENT HASH INDEX");

        EnterpriseCustomerService service =
            new EnterpriseCustomerService();

        service.register(
            new Customer(
                "CUST-1001",
                "Aarav Sharma",
                "Engineering"
            )
        );

        service.register(
            new Customer(
                "CUST-1002",
                "Diya Verma",
                "Security"
            )
        );

        service.register(
            new Customer(
                "CUST-1003",
                "Kabir Singh",
                "Engineering"
            )
        );

        System.out.println(
            "Engineering customers: " +
            service.findByDepartment("Engineering")
        );

        System.out.println(
            "Customer count: " + service.size()
        );
    }


    static void runTests() {
        ChainedHashIndex<String, Integer> index =
            new ChainedHashIndex<>(
                new IndexPolicy(0.75, 2, true)
            );

        index.put("A", 10);
        index.put("B", 20);
        index.put("A", 15);

        assert index.size() == 2;
        assert index.find("A").orElseThrow() == 15;
        assert index.find("B").orElseThrow() == 20;

        assert index.delete("A");
        assert index.find("A").isEmpty();

        LinearProbingIndex<String, Integer> open =
            new LinearProbingIndex<>(4);

        open.put("A", 1);
        open.put("B", 2);

        assert open.delete("A");

        open.put("C", 3);

        assert open.find("B").orElseThrow() == 2;
        assert open.find("C").orElseThrow() == 3;

        assert sha256("test").equals(sha256("test"));
        assert sha256("test").length() == 64;

        System.out.println("\nAll assertions passed.");
    }


    public static void main(String[] args) {
        System.out.println("HASH INDEXING: ENTERPRISE ACCESS");

        demonstrateStandardHashMap();
        demonstrateChaining();
        demonstrateOpenAddressing();
        demonstrateConcurrentAccess();

        System.out.println("\nSTABLE CRYPTOGRAPHIC HASH");
        System.out.println(sha256("customer-1001"));

        runTests();

        System.out.println("\nPERFORMANCE CHARACTERISTICS");
        System.out.println("Average lookup: O(1)");
        System.out.println("Average insertion: O(1)");
        System.out.println("Average deletion: O(1)");
        System.out.println("Worst-case lookup: O(n)");
        System.out.println("Resizing: O(n)");
    }
}
