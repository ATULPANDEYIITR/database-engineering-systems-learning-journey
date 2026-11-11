/*
 * MVCC: Multi-Version Concurrency Control
 *
 * Enterprise-oriented transactional storage model.
 *
 * Java 17 features:
 * - Records
 * - Sealed domain-independent service design
 * - Enums and immutable snapshots
 * - Collections and streams
 * - Generic transaction operations
 * - Optimistic concurrency validation
 * - Isolation policies
 * - State transition enforcement
 * - Transaction monitoring
 * - Version garbage collection
 *
 * Compile:
 * javac MVCCEnterprise.java
 *
 * Run:
 * java MVCCEnterprise
 */

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Function;
import java.util.stream.Collectors;

public class MVCCEnterprise {

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

    enum Operation {
        READ,
        WRITE,
        DELETE,
        COMMIT,
        ROLLBACK
    }

    static class DatabaseException extends RuntimeException {
        DatabaseException(String message) {
            super(message);
        }
    }

    static class WriteConflictException extends DatabaseException {
        WriteConflictException(String message) {
            super(message);
        }
    }

    static class SerializationException extends DatabaseException {
        SerializationException(String message) {
            super(message);
        }
    }

    static class InvalidStateException extends DatabaseException {
        InvalidStateException(String message) {
            super(message);
        }
    }

    record Version<T>(
        T value,
        long xmin,
        Long xmax,
        boolean deleted,
        long timestamp
    ) {}

    record TransactionEvent(
        long transactionId,
        Operation operation,
        String key,
        Instant occurredAt,
        String detail
    ) {}

    record DatabaseStatistics(
        int keys,
        int versions,
        int activeTransactions,
        int committedTransactions,
        int abortedTransactions
    ) {}

    static final class Transaction {
        private final long id;
        private final IsolationLevel isolation;
        private final long startTimestamp;

        private Set<Long> snapshot;

        private TransactionState state = TransactionState.ACTIVE;

        private final Map<String, Object> writes = new HashMap<>();

        private final Map<String, Long> reads = new HashMap<>();

        private Transaction(
            long id,
            IsolationLevel isolation,
            long startTimestamp,
            Set<Long> snapshot
        ) {
            this.id = id;
            this.isolation = isolation;
            this.startTimestamp = startTimestamp;
            this.snapshot = new HashSet<>(snapshot);
        }

        public long id() {
            return id;
        }

        public TransactionState state() {
            return state;
        }

        public IsolationLevel isolation() {
            return isolation;
        }

        public long startTimestamp() {
            return startTimestamp;
        }
    }

    interface TransactionListener {
        void onEvent(TransactionEvent event);
    }

    static final class MVCCStore {

        private final Map<String, List<Version<Object>>> rows =
            new HashMap<>();

        private final Map<Long, Transaction> transactions =
            new HashMap<>();

        private final Set<Long> active = new HashSet<>();
        private final Set<Long> committed = new HashSet<>();
        private final Set<Long> aborted = new HashSet<>();

        private final List<TransactionListener> listeners =
            new ArrayList<>();

        private final AtomicLong nextId = new AtomicLong(1);

        private long clock = 0;

        private synchronized long tick() {
            return ++clock;
        }

        public void addListener(TransactionListener listener) {
            listeners.add(Objects.requireNonNull(listener));
        }

        private void publish(
            Transaction transaction,
            Operation operation,
            String key,
            String detail
        ) {
            TransactionEvent event = new TransactionEvent(
                transaction.id,
                operation,
                key,
                Instant.now(),
                detail
            );

            // Listener failures must not corrupt transaction state.
            for (TransactionListener listener : listeners) {
                try {
                    listener.onEvent(event);
                } catch (RuntimeException exception) {
                    System.err.println(
                        "Monitoring listener failure: "
                        + exception.getMessage()
                    );
                }
            }
        }

        private void requireActive(Transaction transaction) {
            if (
                transaction == null ||
                transaction.state != TransactionState.ACTIVE ||
                transactions.get(transaction.id) != transaction
            ) {
                throw new InvalidStateException(
                    "Transaction is not active or is not registered"
                );
            }
        }

        public synchronized Transaction begin(
            IsolationLevel isolation
        ) {
            Objects.requireNonNull(isolation);

            long id = nextId.getAndIncrement();
            long timestamp = tick();

            Transaction transaction = new Transaction(
                id,
                isolation,
                timestamp,
                active
            );

            transactions.put(id, transaction);
            active.add(id);

            publish(
                transaction,
                Operation.READ,
                null,
                "Transaction started with " + isolation
            );

            return transaction;
        }

        private boolean visible(
            Version<Object> version,
            Transaction transaction
        ) {
            boolean creatorVisible =
                version.xmin() == transaction.id ||
                (
                    !transaction.snapshot.contains(version.xmin()) &&
                    committed.contains(version.xmin())
                );

            if (!creatorVisible) {
                return false;
            }

            if (version.xmax() == null) {
                return true;
            }

            long deleter = version.xmax();

            if (deleter == transaction.id) {
                return false;
            }

            if (transaction.snapshot.contains(deleter)) {
                return true;
            }

            return !committed.contains(deleter);
        }

        private Version<Object> findVisible(
            String key,
            Transaction transaction
        ) {
            List<Version<Object>> chain = rows.getOrDefault(
                key,
                Collections.emptyList()
            );

            for (int i = chain.size() - 1; i >= 0; i--) {
                Version<Object> version = chain.get(i);

                if (visible(version, transaction)) {
                    return version.deleted() ? null : version;
                }
            }

            return null;
        }

        private void refreshSnapshot(Transaction transaction) {
            if (transaction.isolation == IsolationLevel.READ_COMMITTED) {
                transaction.snapshot = new HashSet<>(active);
            }
        }

        public synchronized <T> Optional<T> read(
            Transaction transaction,
            String key,
            Class<T> type
        ) {
            requireActive(transaction);
            validateKey(key);
            refreshSnapshot(transaction);

            Version<Object> version = findVisible(key, transaction);

            transaction.reads.putIfAbsent(
                key,
                version == null ? -1L : version.xmin()
            );

            publish(
                transaction,
                Operation.READ,
                key,
                version == null ? "Not found" :
                    "Visible version " + version.xmin()
            );

            if (version == null) {
                return Optional.empty();
            }

            if (!type.isInstance(version.value())) {
                throw new DatabaseException(
                    "Stored value has an incompatible type"
                );
            }

            return Optional.of(type.cast(version.value()));
        }

        public synchronized void write(
            Transaction transaction,
            String key,
            Object value
        ) {
            requireActive(transaction);
            validateKey(key);
            Objects.requireNonNull(value, "Null values are not supported");

            refreshSnapshot(transaction);

            Version<Object> current = findVisible(key, transaction);

            transaction.reads.putIfAbsent(
                key,
                current == null ? -1L : current.xmin()
            );

            transaction.writes.put(key, value);

            publish(
                transaction,
                Operation.WRITE,
                key,
                "Write buffered"
            );
        }

        public synchronized boolean delete(
            Transaction transaction,
            String key
        ) {
            requireActive(transaction);
            validateKey(key);
            refreshSnapshot(transaction);

            Version<Object> current = findVisible(key, transaction);

            if (current == null) {
                return false;
            }

            transaction.reads.putIfAbsent(key, current.xmin());

            transaction.writes.put(key, DeletedValue.INSTANCE);

            publish(
                transaction,
                Operation.DELETE,
                key,
                "Delete buffered"
            );

            return true;
        }

        private void validateKey(String key) {
            if (key == null || key.isBlank()) {
                throw new IllegalArgumentException(
                    "Key cannot be empty"
                );
            }
        }

        private void validateWrites(Transaction transaction) {
            for (String key : transaction.writes.keySet()) {
                List<Version<Object>> chain = rows.getOrDefault(
                    key,
                    Collections.emptyList()
                );

                Version<Object> latest = chain.stream()
                    .filter(version -> committed.contains(version.xmin()))
                    .max(Comparator.comparingLong(Version::timestamp))
                    .orElse(null);

                long current = latest == null ? -1L : latest.xmin();

                long observed = transaction.reads.getOrDefault(key, -1L);

                if (current != observed) {
                    throw new WriteConflictException(
                        "Concurrent update on key: " + key
                    );
                }
            }
        }

        private void validateSerializable(Transaction transaction) {
            for (Map.Entry<String, Long> entry :
                transaction.reads.entrySet()) {

                String key = entry.getKey();

                if (transaction.writes.containsKey(key)) {
                    continue;
                }

                Version<Object> latest = rows.getOrDefault(
                    key,
                    Collections.emptyList()
                ).stream()
                    .filter(version -> committed.contains(version.xmin()))
                    .max(Comparator.comparingLong(Version::timestamp))
                    .orElse(null);

                long current = latest == null ? -1L : latest.xmin();

                if (current != entry.getValue()) {
                    throw new SerializationException(
                        "Read dependency changed: " + key
                    );
                }
            }
        }

        public synchronized void commit(Transaction transaction) {
            requireActive(transaction);

            try {
                validateWrites(transaction);

                if (
                    transaction.isolation ==
                    IsolationLevel.SERIALIZABLE
                ) {
                    validateSerializable(transaction);
                }

                // Validation is completed before modifying version chains.
                for (String key : transaction.writes.keySet()) {
                    List<Version<Object>> chain = rows.get(key);

                    if (chain == null) {
                        continue;
                    }

                    for (int i = chain.size() - 1; i >= 0; i--) {
                        Version<Object> previous = chain.get(i);

                        if (
                            committed.contains(previous.xmin()) &&
                            previous.xmax() == null
                        ) {
                            chain.set(
                                i,
                                new Version<>(
                                    previous.value(),
                                    previous.xmin(),
                                    transaction.id,
                                    previous.deleted(),
                                    previous.timestamp()
                                )
                            );

                            break;
                        }
                    }
                }

                long commitTimestamp = tick();

                for (Map.Entry<String, Object> entry :
                    transaction.writes.entrySet()) {

                    boolean deleted =
                        entry.getValue() == DeletedValue.INSTANCE;

                    Object value = deleted ? null : entry.getValue();

                    rows.computeIfAbsent(
                        entry.getKey(),
                        ignored -> new ArrayList<>()
                    ).add(
                        new Version<>(
                            value,
                            transaction.id,
                            null,
                            deleted,
                            commitTimestamp
                        )
                    );
                }

                transaction.state = TransactionState.COMMITTED;
                committed.add(transaction.id);
                active.remove(transaction.id);

                publish(
                    transaction,
                    Operation.COMMIT,
                    null,
                    "Committed " + transaction.writes.size() + " writes"
                );

            } catch (RuntimeException exception) {
                rollback(transaction);
                throw exception;
            }
        }

        public synchronized void rollback(Transaction transaction) {
            if (
                transaction == null ||
                transaction.state != TransactionState.ACTIVE
            ) {
                return;
            }

            requireActive(transaction);

            transaction.writes.clear();

            transaction.state = TransactionState.ABORTED;
            active.remove(transaction.id);
            aborted.add(transaction.id);

            tick();

            publish(
                transaction,
                Operation.ROLLBACK,
                null,
                "Transaction aborted"
            );
        }

        public synchronized int vacuum() {
            long horizon = active.isEmpty()
                ? nextId.get()
                : active.stream().min(Long::compareTo).orElse(nextId.get());

            int removed = 0;

            var iterator = rows.entrySet().iterator();

            while (iterator.hasNext()) {
                var entry = iterator.next();

                List<Version<Object>> chain = entry.getValue();

                int previousSize = chain.size();

                chain.removeIf(version -> {
                    boolean abortedCreator =
                        aborted.contains(version.xmin());

                    boolean obsolete =
                        version.xmax() != null &&
                        committed.contains(version.xmax()) &&
                        version.xmax() < horizon;

                    return abortedCreator || obsolete;
                });

                removed += previousSize - chain.size();

                if (chain.isEmpty()) {
                    iterator.remove();
                }
            }

            return removed;
        }

        public synchronized List<Version<Object>> inspect(
            String key
        ) {
            return List.copyOf(
                rows.getOrDefault(key, Collections.emptyList())
            );
        }

        public synchronized DatabaseStatistics statistics() {
            int versionCount = rows.values().stream()
                .mapToInt(List::size)
                .sum();

            return new DatabaseStatistics(
                rows.size(),
                versionCount,
                active.size(),
                committed.size(),
                aborted.size()
            );
        }
    }

    private enum DeletedValue {
        INSTANCE
    }

    static final class TransactionService {

        private final MVCCStore store;

        TransactionService(MVCCStore store) {
            this.store = store;
        }

        public void transfer(
            String source,
            String destination,
            long amount
        ) {
            if (amount <= 0) {
                throw new IllegalArgumentException(
                    "Transfer amount must be positive"
                );
            }

            Transaction transaction = store.begin(
                IsolationLevel.SERIALIZABLE
            );

            try {
                long sourceBalance = store.read(
                    transaction,
                    source,
                    Long.class
                ).orElseThrow(
                    () -> new DatabaseException("Source account missing")
                );

                long destinationBalance = store.read(
                    transaction,
                    destination,
                    Long.class
                ).orElseThrow(
                    () -> new DatabaseException("Destination account missing")
                );

                if (sourceBalance < amount) {
                    throw new DatabaseException(
                        "Insufficient account balance"
                    );
                }

                store.write(
                    transaction,
                    source,
                    sourceBalance - amount
                );

                store.write(
                    transaction,
                    destination,
                    Math.addExact(destinationBalance, amount)
                );

                store.commit(transaction);

            } catch (RuntimeException exception) {
                store.rollback(transaction);
                throw exception;
            }
        }
    }

    public static void main(String[] args) {
        MVCCStore store = new MVCCStore();

        store.addListener(event ->
            System.out.println(
                "[EVENT] transaction=" + event.transactionId() +
                " operation=" + event.operation() +
                " key=" + event.key() +
                " detail=" + event.detail()
            )
        );

        try {
            System.out.println("\n1. Initialize enterprise accounts");

            Transaction setup = store.begin(
                IsolationLevel.SNAPSHOT
            );

            store.write(setup, "account-001", 1000L);
            store.write(setup, "account-002", 500L);

            store.commit(setup);

            System.out.println("\n2. Snapshot isolation");

            Transaction reader = store.begin(
                IsolationLevel.REPEATABLE_READ
            );

            System.out.println(
                "Initial balance: " +
                store.read(reader, "account-001", Long.class)
            );

            Transaction updater = store.begin(
                IsolationLevel.SNAPSHOT
            );

            store.write(updater, "account-001", 1200L);
            store.commit(updater);

            System.out.println(
                "Reader snapshot: " +
                store.read(reader, "account-001", Long.class)
            );

            store.commit(reader);

            System.out.println("\n3. New transaction");

            Transaction latest = store.begin(
                IsolationLevel.READ_COMMITTED
            );

            System.out.println(
                "Latest balance: " +
                store.read(latest, "account-001", Long.class)
            );

            store.commit(latest);

            System.out.println("\n4. Write-write conflict");

            Transaction first = store.begin(
                IsolationLevel.SNAPSHOT
            );

            Transaction second = store.begin(
                IsolationLevel.SNAPSHOT
            );

            store.write(first, "account-002", 600L);
            store.write(second, "account-002", 700L);

            store.commit(first);

            try {
                store.commit(second);
            } catch (WriteConflictException exception) {
                System.out.println(
                    "Expected conflict: " + exception.getMessage()
                );
            }

            System.out.println("\n5. Serializable transfer");

            TransactionService service = new TransactionService(store);

            service.transfer(
                "account-001",
                "account-002",
                100L
            );

            Transaction verification = store.begin(
                IsolationLevel.SNAPSHOT
            );

            System.out.println(
                "Source: " +
                store.read(verification, "account-001", Long.class)
            );

            System.out.println(
                "Destination: " +
                store.read(verification, "account-002", Long.class)
            );

            store.commit(verification);

            System.out.println("\n6. Delete and rollback");

            Transaction deletion = store.begin(
                IsolationLevel.SNAPSHOT
            );

            store.delete(deletion, "account-002");
            store.rollback(deletion);

            System.out.println("\n7. Version history");

            store.inspect("account-001").forEach(
                System.out::println
            );

            System.out.println("\n8. Vacuum");

            System.out.println(
                "Removed versions: " + store.vacuum()
            );

            System.out.println("\n9. Statistics");

            System.out.println(store.statistics());

        } catch (DatabaseException exception) {
            System.err.println(
                "Database operation failed: " + exception.getMessage()
            );

            System.exitCode = 1;
        }
    }
}
