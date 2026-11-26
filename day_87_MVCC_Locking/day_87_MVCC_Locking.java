import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.HashSet;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.ReentrantLock;

/*
 * MVCC vs Locking: Enterprise Transaction Governance.
 *
 * Java 17 implementation.
 *
 * Models:
 * - Snapshot isolation.
 * - Versioned records.
 * - Optimistic conflict validation.
 * - Pessimistic exclusive locking.
 * - Transaction state transitions.
 * - Commit and rollback.
 * - Workload policy evaluation.
 * - Enterprise transaction metrics.
 *
 * No third-party dependencies.
 */

public class Main {

    enum TransactionState {
        ACTIVE,
        COMMITTED,
        ABORTED
    }

    enum ConcurrencyModel {
        MVCC,
        PESSIMISTIC_LOCKING
    }

    static class TransactionException extends RuntimeException {
        TransactionException(String message) {
            super(message);
        }
    }

    static class WriteConflictException extends TransactionException {
        WriteConflictException(String message) {
            super(message);
        }
    }

    static class LockConflictException extends TransactionException {
        LockConflictException(String message) {
            super(message);
        }
    }

    record Version<T>(long timestamp, T value) {}

    record MetricsSnapshot(
        long started,
        long committed,
        long aborted,
        long conflicts,
        long lockFailures,
        long reads,
        long writes
    ) {
        double commitRate() {
            return started == 0
                ? 0.0
                : committed * 100.0 / started;
        }
    }

    static class Metrics {
        private long started;
        private long committed;
        private long aborted;
        private long conflicts;
        private long lockFailures;
        private long reads;
        private long writes;

        MetricsSnapshot snapshot() {
            return new MetricsSnapshot(
                started,
                committed,
                aborted,
                conflicts,
                lockFailures,
                reads,
                writes
            );
        }
    }

    static class Transaction {
        private final long id;
        private final long snapshot;

        private TransactionState state = TransactionState.ACTIVE;

        private final Map<String, Object> writes =
            new LinkedHashMap<>();

        private final Set<String> reads =
            new HashSet<>();

        private final Set<String> locks =
            new HashSet<>();

        Transaction(long id, long snapshot) {
            this.id = id;
            this.snapshot = snapshot;
        }

        long id() {
            return id;
        }

        long snapshot() {
            return snapshot;
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
    }


    interface TransactionEngine {
        Transaction begin();

        Object read(Transaction transaction, String key);

        void write(
            Transaction transaction,
            String key,
            Object value
        );

        void commit(Transaction transaction);

        void rollback(Transaction transaction);

        MetricsSnapshot metrics();
    }


    static final class MvccEngine implements TransactionEngine {

        private final Map<String, List<Version<Object>>> storage =
            new HashMap<>();

        private final AtomicLong transactionIds =
            new AtomicLong();

        private final Metrics metrics = new Metrics();

        private long clock = 0;

        MvccEngine(Map<String, Object> initialData) {
            initialData.forEach((key, value) -> {
                validateKey(key);

                storage.put(
                    key,
                    new ArrayList<>(
                        List.of(new Version<>(0, value))
                    )
                );
            });
        }

        private void validateKey(String key) {
            if (key == null || key.isBlank()) {
                throw new IllegalArgumentException(
                    "Record key cannot be empty"
                );
            }
        }

        @Override
        public synchronized Transaction begin() {
            metrics.started++;

            return new Transaction(
                transactionIds.incrementAndGet(),
                clock
            );
        }

        private Optional<Version<Object>> visibleVersion(
            String key,
            long snapshot
        ) {
            List<Version<Object>> versions =
                storage.getOrDefault(key, List.of());

            for (int i = versions.size() - 1; i >= 0; i--) {
                Version<Object> version = versions.get(i);

                if (version.timestamp() <= snapshot) {
                    return Optional.of(version);
                }
            }

            return Optional.empty();
        }

        @Override
        public synchronized Object read(
            Transaction transaction,
            String key
        ) {
            transaction.ensureActive();
            validateKey(key);

            metrics.reads++;

            if (transaction.writes.containsKey(key)) {
                return transaction.writes.get(key);
            }

            transaction.reads.add(key);

            return visibleVersion(
                key,
                transaction.snapshot
            ).map(Version::value).orElse(null);
        }

        @Override
        public synchronized void write(
            Transaction transaction,
            String key,
            Object value
        ) {
            transaction.ensureActive();
            validateKey(key);

            transaction.writes.put(key, value);
        }

        @Override
        public synchronized void commit(
            Transaction transaction
        ) {
            transaction.ensureActive();

            // Validate the entire write set before publication.
            for (String key : transaction.writes.keySet()) {
                List<Version<Object>> versions =
                    storage.getOrDefault(key, List.of());

                if (
                    !versions.isEmpty() &&
                    versions.get(versions.size() - 1).timestamp()
                        > transaction.snapshot
                ) {
                    transaction.state = TransactionState.ABORTED;

                    metrics.aborted++;
                    metrics.conflicts++;

                    throw new WriteConflictException(
                        "Concurrent modification of " + key
                    );
                }
            }

            long commitTimestamp = ++clock;

            for (var entry : transaction.writes.entrySet()) {
                storage.computeIfAbsent(
                    entry.getKey(),
                    ignored -> new ArrayList<>()
                ).add(
                    new Version<>(
                        commitTimestamp,
                        entry.getValue()
                    )
                );

                metrics.writes++;
            }

            transaction.state = TransactionState.COMMITTED;
            metrics.committed++;
        }

        @Override
        public synchronized void rollback(
            Transaction transaction
        ) {
            transaction.ensureActive();

            transaction.writes.clear();
            transaction.state = TransactionState.ABORTED;

            metrics.aborted++;
        }

        List<Version<Object>> history(String key) {
            synchronized (this) {
                return Collections.unmodifiableList(
                    new ArrayList<>(
                        storage.getOrDefault(key, List.of())
                    )
                );
            }
        }

        @Override
        public MetricsSnapshot metrics() {
            return metrics.snapshot();
        }
    }


    static final class LockingEngine implements TransactionEngine {

        private final Map<String, Object> storage =
            new HashMap<>();

        private final Map<String, Long> owners =
            new HashMap<>();

        private final Map<String, ReentrantLock> mutexes =
            new HashMap<>();

        private final AtomicLong transactionIds =
            new AtomicLong();

        private final Metrics metrics = new Metrics();

        LockingEngine(Map<String, Object> initialData) {
            storage.putAll(initialData);
        }

        private synchronized void acquire(
            Transaction transaction,
            String key
        ) {
            transaction.ensureActive();

            if (transaction.locks.contains(key)) {
                return;
            }

            Long owner = owners.get(key);

            if (owner != null && owner != transaction.id) {
                metrics.lockFailures++;

                throw new LockConflictException(
                    "Record " + key + " is locked by " + owner
                );
            }

            owners.put(key, transaction.id);
            transaction.locks.add(key);
        }

        @Override
        public synchronized Transaction begin() {
            metrics.started++;

            return new Transaction(
                transactionIds.incrementAndGet(),
                0
            );
        }

        @Override
        public synchronized Object read(
            Transaction transaction,
            String key
        ) {
            transaction.ensureActive();

            acquire(transaction, key);
            metrics.reads++;

            if (transaction.writes.containsKey(key)) {
                return transaction.writes.get(key);
            }

            return storage.get(key);
        }

        @Override
        public synchronized void write(
            Transaction transaction,
            String key,
            Object value
        ) {
            transaction.ensureActive();

            acquire(transaction, key);

            transaction.writes.put(key, value);
        }

        private synchronized void releaseAll(
            Transaction transaction
        ) {
            for (String key : transaction.locks) {
                if (
                    Objects.equals(
                        owners.get(key),
                        transaction.id
                    )
                ) {
                    owners.remove(key);
                }
            }

            transaction.locks.clear();
        }

        @Override
        public synchronized void commit(
            Transaction transaction
        ) {
            transaction.ensureActive();

            storage.putAll(transaction.writes);

            metrics.writes += transaction.writes.size();
            metrics.committed++;

            transaction.state = TransactionState.COMMITTED;

            releaseAll(transaction);
        }

        @Override
        public synchronized void rollback(
            Transaction transaction
        ) {
            transaction.ensureActive();

            transaction.writes.clear();
            metrics.aborted++;

            transaction.state = TransactionState.ABORTED;

            releaseAll(transaction);
        }

        @Override
        public MetricsSnapshot metrics() {
            return metrics.snapshot();
        }

        synchronized Object currentValue(String key) {
            return storage.get(key);
        }
    }


    record Workload(
        String name,
        double readRatio,
        double contention,
        double writeHotspot,
        double durationMillis
    ) {
        Workload {
            Objects.requireNonNull(name);

            if (
                readRatio < 0 || readRatio > 1 ||
                contention < 0 || contention > 1 ||
                writeHotspot < 0 || writeHotspot > 1 ||
                durationMillis < 0
            ) {
                throw new IllegalArgumentException(
                    "Invalid workload parameters"
                );
            }
        }
    }


    record ArchitectureDecision(
        String model,
        double mvccScore,
        double lockingScore,
        String rationale
    ) {}


    static final class ArchitecturePolicy {

        ArchitectureDecision evaluate(Workload workload) {
            double mvccScore =
                60 * workload.readRatio()
                + 25 * (1 - workload.contention())
                + 15 * (1 - workload.writeHotspot())
                - Math.min(
                    workload.durationMillis() / 1000,
                    20
                );

            double lockingScore =
                50 * workload.contention()
                + 30 * workload.writeHotspot()
                + 20 * Math.min(
                    workload.durationMillis() / 1000,
                    1
                );

            String preferred =
                mvccScore >= lockingScore
                    ? "MVCC"
                    : "PESSIMISTIC_LOCKING";

            String rationale =
                preferred.equals("MVCC")
                    ? "Read concurrency and low contention favor versioned reads."
                    : "Write contention makes explicit serialization worth evaluating.";

            return new ArchitectureDecision(
                preferred,
                mvccScore,
                lockingScore,
                rationale
            );
        }
    }


    private static void demonstrateMvcc() {
        System.out.println("\n=== ENTERPRISE MVCC ===");

        MvccEngine engine = new MvccEngine(
            Map.of(
                "account", 1000,
                "inventory", 200
            )
        );

        Transaction first = engine.begin();
        Transaction second = engine.begin();

        System.out.println(
            "First snapshot: " +
            engine.read(first, "account")
        );

        System.out.println(
            "Second snapshot: " +
            engine.read(second, "account")
        );

        engine.write(first, "account", 900);
        engine.write(second, "account", 800);

        engine.commit(first);

        try {
            engine.commit(second);
        } catch (WriteConflictException error) {
            System.out.println(
                "Expected conflict: " + error.getMessage()
            );
        }

        System.out.println(
            "Version history: " + engine.history("account")
        );

        System.out.println(
            "Metrics: " + engine.metrics()
        );
    }


    private static void demonstrateLocking() {
        System.out.println("\n=== ENTERPRISE LOCKING ===");

        LockingEngine engine = new LockingEngine(
            Map.of("inventory", 100)
        );

        Transaction first = engine.begin();
        Transaction second = engine.begin();

        System.out.println(
            "First reads: " +
            engine.read(first, "inventory")
        );

        try {
            engine.read(second, "inventory");
        } catch (LockConflictException error) {
            System.out.println(
                "Lock contention: " + error.getMessage()
            );
        }

        engine.write(first, "inventory", 90);
        engine.commit(first);

        System.out.println(
            "Second reads after release: " +
            engine.read(second, "inventory")
        );

        engine.write(second, "inventory", 80);
        engine.commit(second);

        System.out.println(
            "Final inventory: " +
            engine.currentValue("inventory")
        );

        System.out.println(
            "Metrics: " + engine.metrics()
        );
    }


    private static void evaluateWorkloads() {
        System.out.println("\n=== ENTERPRISE POLICY EVALUATION ===");

        ArchitecturePolicy policy = new ArchitecturePolicy();

        List<Workload> workloads = List.of(
            new Workload(
                "Reporting platform",
                0.95,
                0.10,
                0.05,
                100
            ),
            new Workload(
                "Inventory management",
                0.30,
                0.90,
                0.90,
                500
            ),
            new Workload(
                "Long-running transactions",
                0.60,
                0.70,
                0.50,
                5000
            )
        );

        workloads.stream()
            .map(policy::evaluate)
            .forEach(System.out::println);
    }


    public static void main(String[] args) {
        try {
            demonstrateMvcc();
            demonstrateLocking();
            evaluateWorkloads();

            // Validate that a completed transaction cannot be reused.
            MvccEngine test = new MvccEngine(
                Map.of("x", 10)
            );

            Transaction transaction = test.begin();
            test.commit(transaction);

            try {
                test.read(transaction, "x");
                throw new AssertionError(
                    "Expected closed transaction rejection"
                );
            } catch (TransactionException expected) {
                System.out.println(
                    "\nTransaction-state validation passed."
                );
            }

            System.out.println("All checks passed.");

        } catch (Exception error) {
            System.err.println(
                "Application failure: " + error.getMessage()
            );

            System.exit(1);
        }
    }
}
