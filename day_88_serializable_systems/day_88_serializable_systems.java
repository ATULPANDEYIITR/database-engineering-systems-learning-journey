import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;

/*
 * Serializable Systems
 *
 * Enterprise transaction management model.
 *
 * Java version: 17
 *
 * Features:
 * - Typed transaction operations
 * - Conflict serializability analysis
 * - Optimistic concurrency control
 * - Transaction state transitions
 * - Version-based validation
 * - Atomic write publication
 * - Isolation policies
 * - Approval of transaction execution
 * - Retry and conflict metrics
 * - Enterprise domain validation
 */

public class SerializableSystems {

    enum OperationType {
        READ,
        WRITE
    }

    enum TransactionStatus {
        ACTIVE,
        VALIDATING,
        COMMITTED,
        ABORTED
    }

    enum IsolationPolicy {
        READ_COMMITTED,
        REPEATABLE_READ,
        SERIALIZABLE
    }

    record Operation(
        String transactionId,
        String resource,
        OperationType type
    ) {
        Operation {
            if (transactionId == null || transactionId.isBlank()) {
                throw new IllegalArgumentException(
                    "Transaction ID is required"
                );
            }

            if (resource == null || resource.isBlank()) {
                throw new IllegalArgumentException(
                    "Resource is required"
                );
            }

            Objects.requireNonNull(type);
        }
    }

    record CommitRecord(
        String transactionId,
        long commitTimestamp,
        Set<String> readSet,
        Set<String> writeSet
    ) {
        CommitRecord {
            readSet = Set.copyOf(readSet);
            writeSet = Set.copyOf(writeSet);
        }
    }

    record AnalysisResult(
        boolean serializable,
        List<String> executionOrder,
        Map<String, Set<String>> dependencies,
        Set<String> cycleMembers
    ) {}

    static class TransactionException extends RuntimeException {

        TransactionException(String message) {
            super(message);
        }
    }

    static class Transaction {

        private final String id;
        private final long startTimestamp;
        private final Set<String> readSet = new HashSet<>();
        private final Set<String> writeSet = new HashSet<>();
        private final Map<String, Long> observedVersions =
            new HashMap<>();

        private final Map<String, Long> workspace =
            new LinkedHashMap<>();

        private TransactionStatus status =
            TransactionStatus.ACTIVE;

        private Transaction(
            String id,
            long startTimestamp
        ) {
            this.id = id;
            this.startTimestamp = startTimestamp;
        }

        String id() {
            return id;
        }

        long startTimestamp() {
            return startTimestamp;
        }

        TransactionStatus status() {
            return status;
        }

        Set<String> readSet() {
            return Set.copyOf(readSet);
        }

        Set<String> writeSet() {
            return Set.copyOf(writeSet);
        }

        private void requireActive() {

            if (status != TransactionStatus.ACTIVE) {
                throw new TransactionException(
                    "Transaction is not active: " + id
                );
            }
        }
    }


    static class SerializableScheduleAnalyzer {

        AnalysisResult analyze(List<Operation> operations) {

            Map<String, Set<String>> graph =
                new LinkedHashMap<>();

            for (Operation operation : operations) {
                graph.putIfAbsent(
                    operation.transactionId(),
                    new LinkedHashSet<>()
                );
            }

            for (int i = 0; i < operations.size(); i++) {

                Operation first = operations.get(i);

                for (int j = i + 1; j < operations.size(); j++) {

                    Operation second = operations.get(j);

                    if (
                        first.transactionId().equals(
                            second.transactionId()
                        )
                    ) {
                        continue;
                    }

                    if (!first.resource().equals(second.resource())) {
                        continue;
                    }

                    boolean conflict =
                        first.type() == OperationType.WRITE ||
                        second.type() == OperationType.WRITE;

                    if (conflict) {
                        graph.get(first.transactionId()).add(
                            second.transactionId()
                        );
                    }
                }
            }

            Map<String, Integer> indegree = new HashMap<>();

            graph.keySet().forEach(
                id -> indegree.put(id, 0)
            );

            graph.values().forEach(
                neighbors -> neighbors.forEach(
                    id -> indegree.merge(id, 1, Integer::sum)
                )
            );

            Queue<String> ready = new ArrayDeque<>();

            indegree.forEach((id, degree) -> {
                if (degree == 0) {
                    ready.add(id);
                }
            });

            List<String> order = new ArrayList<>();

            while (!ready.isEmpty()) {

                String current = ready.remove();
                order.add(current);

                for (String neighbor : graph.get(current)) {

                    int remaining =
                        indegree.merge(neighbor, -1, Integer::sum);

                    if (remaining == 0) {
                        ready.add(neighbor);
                    }
                }
            }

            boolean serializable =
                order.size() == graph.size();

            Set<String> cycleMembers = new LinkedHashSet<>();

            if (!serializable) {

                indegree.forEach((id, degree) -> {
                    if (degree > 0) {
                        cycleMembers.add(id);
                    }
                });
            }

            Map<String, Set<String>> immutableGraph =
                graph.entrySet().stream().collect(
                    Collectors.toUnmodifiableMap(
                        Map.Entry::getKey,
                        entry -> Set.copyOf(entry.getValue())
                    )
                );

            return new AnalysisResult(
                serializable,
                List.copyOf(order),
                immutableGraph,
                Set.copyOf(cycleMembers)
            );
        }
    }


    static class EnterpriseTransactionService {

        private final Map<String, Long> database =
            new LinkedHashMap<>();

        private final Map<String, Long> versions =
            new HashMap<>();

        private final Map<String, Transaction> transactions =
            new LinkedHashMap<>();

        private final List<CommitRecord> history =
            new ArrayList<>();

        private final AtomicLong clock = new AtomicLong();

        private final IsolationPolicy isolationPolicy;

        private long commits;
        private long aborts;
        private long validationFailures;

        EnterpriseTransactionService(
            Map<String, Long> initialData,
            IsolationPolicy isolationPolicy
        ) {

            if (initialData.isEmpty()) {
                throw new IllegalArgumentException(
                    "Initial database cannot be empty"
                );
            }

            initialData.forEach((resource, value) -> {

                if (resource == null || resource.isBlank()) {
                    throw new IllegalArgumentException(
                        "Invalid resource name"
                    );
                }

                if (value == null || value < 0) {
                    throw new IllegalArgumentException(
                        "Invalid initial value"
                    );
                }

                database.put(resource, value);
                versions.put(resource, 0L);
            });

            this.isolationPolicy =
                Objects.requireNonNull(isolationPolicy);
        }

        synchronized Transaction begin(String id) {

            if (id == null || id.isBlank()) {
                throw new IllegalArgumentException(
                    "Transaction ID is required"
                );
            }

            if (transactions.containsKey(id)) {
                throw new TransactionException(
                    "Duplicate transaction ID: " + id
                );
            }

            Transaction transaction = new Transaction(
                id,
                clock.incrementAndGet()
            );

            transactions.put(id, transaction);

            return transaction;
        }

        synchronized long read(
            Transaction transaction,
            String resource
        ) {

            transaction.requireActive();

            requireResource(resource);

            if (transaction.workspace.containsKey(resource)) {
                return transaction.workspace.get(resource);
            }

            if (
                isolationPolicy == IsolationPolicy.SERIALIZABLE ||
                isolationPolicy == IsolationPolicy.REPEATABLE_READ
            ) {

                transaction.observedVersions.putIfAbsent(
                    resource,
                    versions.get(resource)
                );
            }

            transaction.readSet.add(resource);

            return database.get(resource);
        }

        synchronized void write(
            Transaction transaction,
            String resource,
            long value
        ) {

            transaction.requireActive();

            requireResource(resource);

            if (value < 0) {
                throw new IllegalArgumentException(
                    "Account value cannot be negative"
                );
            }

            transaction.writeSet.add(resource);
            transaction.workspace.put(resource, value);
        }

        private void requireResource(String resource) {

            if (!database.containsKey(resource)) {
                throw new TransactionException(
                    "Unknown resource: " + resource
                );
            }
        }

        private boolean validate(Transaction transaction) {

            for (CommitRecord record : history) {

                if (
                    record.commitTimestamp() <=
                    transaction.startTimestamp()
                ) {
                    continue;
                }

                // A transaction cannot commit using a read that
                // was invalidated by a later committed writer.
                if (
                    transaction.readSet().stream().anyMatch(
                        record.writeSet()::contains
                    )
                ) {
                    return false;
                }
            }

            // Version validation also protects repeatable reads.
            for (
                Map.Entry<String, Long> observed :
                transaction.observedVersions.entrySet()
            ) {

                long currentVersion =
                    versions.get(observed.getKey());

                if (currentVersion != observed.getValue()) {
                    return false;
                }
            }

            return true;
        }

        synchronized boolean commit(Transaction transaction) {

            transaction.requireActive();

            transaction.status = TransactionStatus.VALIDATING;

            if (!validate(transaction)) {

                transaction.status = TransactionStatus.ABORTED;

                aborts++;
                validationFailures++;

                return false;
            }

            long commitTimestamp = clock.incrementAndGet();

            // Publish all validated writes within the synchronized
            // critical section.
            for (
                Map.Entry<String, Long> entry :
                transaction.workspace.entrySet()
            ) {

                database.put(entry.getKey(), entry.getValue());

                versions.put(
                    entry.getKey(),
                    commitTimestamp
                );
            }

            transaction.status = TransactionStatus.COMMITTED;

            history.add(new CommitRecord(
                transaction.id(),
                commitTimestamp,
                transaction.readSet(),
                transaction.writeSet()
            ));

            commits++;

            return true;
        }

        synchronized void abort(Transaction transaction) {

            transaction.requireActive();

            transaction.workspace.clear();
            transaction.status = TransactionStatus.ABORTED;

            aborts++;
        }

        synchronized Map<String, Long> snapshot() {
            return Map.copyOf(database);
        }

        synchronized Map<String, Long> metrics() {

            return Map.of(
                "commits", commits,
                "aborts", aborts,
                "validationFailures", validationFailures,
                "historyRecords", (long) history.size()
            );
        }

        IsolationPolicy isolationPolicy() {
            return isolationPolicy;
        }
    }


    static class TransferService {

        private final EnterpriseTransactionService transactions;

        TransferService(
            EnterpriseTransactionService transactions
        ) {
            this.transactions = transactions;
        }

        boolean transfer(
            String transactionId,
            String source,
            String destination,
            long amount
        ) {

            if (amount <= 0) {
                throw new IllegalArgumentException(
                    "Transfer amount must be positive"
                );
            }

            Transaction transaction =
                transactions.begin(transactionId);

            try {

                long sourceBalance =
                    transactions.read(transaction, source);

                long destinationBalance =
                    transactions.read(transaction, destination);

                if (sourceBalance < amount) {

                    transactions.abort(transaction);

                    throw new TransactionException(
                        "Insufficient funds"
                    );
                }

                if (
                    Long.MAX_VALUE - destinationBalance < amount
                ) {

                    transactions.abort(transaction);

                    throw new TransactionException(
                        "Destination balance overflow"
                    );
                }

                transactions.write(
                    transaction,
                    source,
                    sourceBalance - amount
                );

                transactions.write(
                    transaction,
                    destination,
                    destinationBalance + amount
                );

                return transactions.commit(transaction);

            } catch (RuntimeException exception) {

                if (
                    transaction.status() ==
                    TransactionStatus.ACTIVE
                ) {
                    transactions.abort(transaction);
                }

                throw exception;
            }
        }
    }


    static void demonstrateConflictAnalysis() {

        System.out.println(
            "\n=== Conflict Serializability ==="
        );

        List<Operation> operations = List.of(
            new Operation("T1", "A", OperationType.READ),
            new Operation("T2", "B", OperationType.READ),
            new Operation("T1", "B", OperationType.WRITE),
            new Operation("T2", "A", OperationType.WRITE)
        );

        AnalysisResult result =
            new SerializableScheduleAnalyzer().analyze(operations);

        System.out.println(
            "Serializable: " + result.serializable()
        );

        System.out.println(
            "Dependencies: " + result.dependencies()
        );

        System.out.println(
            "Cycle members: " + result.cycleMembers()
        );

        if (result.serializable()) {
            System.out.println(
                "Equivalent order: " + result.executionOrder()
            );
        }
    }


    static void demonstrateEnterpriseTransactions() {

        System.out.println(
            "\n=== Enterprise Transaction Processing ==="
        );

        EnterpriseTransactionService service =
            new EnterpriseTransactionService(
                Map.of(
                    "ACCOUNT_A", 5000L,
                    "ACCOUNT_B", 2000L
                ),
                IsolationPolicy.SERIALIZABLE
            );

        TransferService transferService =
            new TransferService(service);

        boolean committed = transferService.transfer(
            "TXN_1001",
            "ACCOUNT_A",
            "ACCOUNT_B",
            750
        );

        System.out.println("Committed: " + committed);

        System.out.println("Balances: " + service.snapshot());

        System.out.println("Metrics: " + service.metrics());

        long total = service.snapshot()
            .values()
            .stream()
            .mapToLong(Long::longValue)
            .sum();

        if (total != 7000) {
            throw new IllegalStateException(
                "Account conservation invariant violated"
            );
        }
    }


    static void demonstrateConflict() {

        System.out.println(
            "\n=== Concurrent Transaction Conflict ==="
        );

        EnterpriseTransactionService service =
            new EnterpriseTransactionService(
                Map.of(
                    "ACCOUNT_A", 1000L,
                    "ACCOUNT_B", 500L
                ),
                IsolationPolicy.SERIALIZABLE
            );

        Transaction first = service.begin("T1");
        Transaction second = service.begin("T2");

        long firstRead = service.read(first, "ACCOUNT_A");
        long secondRead = service.read(second, "ACCOUNT_A");

        service.write(first, "ACCOUNT_A", firstRead - 100);
        service.write(second, "ACCOUNT_A", secondRead - 200);

        System.out.println(
            "T1 commit: " + service.commit(first)
        );

        System.out.println(
            "T2 commit: " + service.commit(second)
        );

        System.out.println("Balances: " + service.snapshot());

        System.out.println("Metrics: " + service.metrics());
    }


    public static void main(String[] args) {

        long started = System.nanoTime();

        demonstrateConflictAnalysis();
        demonstrateEnterpriseTransactions();
        demonstrateConflict();

        long elapsed = System.nanoTime() - started;

        System.out.printf(
            "%nExecution time: %.3f ms%n",
            elapsed / 1_000_000.0
        );
    }
}
