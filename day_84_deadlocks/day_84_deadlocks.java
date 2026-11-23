import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Deque;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/**
 * Enterprise Deadlock Governance System.
 *
 * Java 17 implementation featuring:
 * - Immutable resource and transaction identifiers
 * - Explicit transaction lifecycle
 * - Resource allocation services
 * - Wait-for graph analysis
 * - Deadlock detection
 * - Prevention policies
 * - Recovery strategies
 * - Audit events
 * - Merge-like atomic resource release
 *
 * Dependencies: Java 17 standard library.
 */

public class DeadlockGovernance {

    enum TransactionState {
        ACTIVE,
        WAITING,
        COMMITTED,
        ABORTED
    }

    enum PreventionPolicy {
        NONE,
        RESOURCE_ORDERING,
        WAIT_DIE,
        WOUND_WAIT
    }

    enum RecoveryPolicy {
        YOUNGEST_TRANSACTION,
        FEWEST_LOCKS
    }

    record ResourceId(String value) {
        ResourceId {
            Objects.requireNonNull(value);

            if (value.isBlank()) {
                throw new IllegalArgumentException(
                    "Resource ID cannot be blank."
                );
            }
        }
    }

    record TransactionId(String value) {
        TransactionId {
            Objects.requireNonNull(value);

            if (value.isBlank()) {
                throw new IllegalArgumentException(
                    "Transaction ID cannot be blank."
                );
            }
        }
    }

    record AuditEvent(
        Instant timestamp,
        String eventType,
        String transactionId,
        String details
    ) {}

    record DeadlockReport(
        List<TransactionId> cycle,
        TransactionId victim,
        String recoveryReason
    ) {}

    static final class Transaction {

        private final TransactionId id;
        private final long timestamp;

        private TransactionState state;
        private final Set<ResourceId> held;
        private ResourceId waitingFor;
        private int rollbackCount;

        Transaction(TransactionId id, long timestamp) {
            this.id = id;
            this.timestamp = timestamp;
            this.state = TransactionState.ACTIVE;
            this.held = new LinkedHashSet<>();
            this.rollbackCount = 0;
        }

        TransactionId id() {
            return id;
        }

        long timestamp() {
            return timestamp;
        }

        TransactionState state() {
            return state;
        }

        Set<ResourceId> held() {
            return Collections.unmodifiableSet(held);
        }

        Optional<ResourceId> waitingFor() {
            return Optional.ofNullable(waitingFor);
        }

        int rollbackCount() {
            return rollbackCount;
        }
    }

    static final class Resource {

        private final ResourceId id;
        private final int order;
        private TransactionId owner;
        private final Deque<TransactionId> queue;

        Resource(ResourceId id, int order) {
            this.id = id;
            this.order = order;
            this.queue = new ArrayDeque<>();
        }
    }

    interface VictimSelector {
        Transaction select(List<Transaction> candidates);
    }

    static final class YoungestTransactionSelector
            implements VictimSelector {

        @Override
        public Transaction select(List<Transaction> candidates) {
            return candidates.stream()
                .max(Comparator.comparingLong(Transaction::timestamp))
                .orElseThrow(
                    () -> new IllegalArgumentException(
                        "No recovery candidates."
                    )
                );
        }
    }

    static final class FewestLocksSelector
            implements VictimSelector {

        @Override
        public Transaction select(List<Transaction> candidates) {
            return candidates.stream()
                .min(
                    Comparator.comparingInt(
                        tx -> tx.held.size()
                    ).thenComparingLong(Transaction::timestamp)
                )
                .orElseThrow(
                    () -> new IllegalArgumentException(
                        "No recovery candidates."
                    )
                );
        }
    }

    static final class ResourceManager {

        private final Map<ResourceId, Resource> resources =
            new LinkedHashMap<>();

        private final Map<TransactionId, Transaction> transactions =
            new LinkedHashMap<>();

        private final List<AuditEvent> auditLog =
            new ArrayList<>();

        private final PreventionPolicy preventionPolicy;
        private final VictimSelector victimSelector;

        private long clock;

        ResourceManager(
            PreventionPolicy preventionPolicy,
            RecoveryPolicy recoveryPolicy
        ) {
            this.preventionPolicy =
                Objects.requireNonNull(preventionPolicy);

            this.victimSelector = switch (recoveryPolicy) {
                case YOUNGEST_TRANSACTION ->
                    new YoungestTransactionSelector();

                case FEWEST_LOCKS ->
                    new FewestLocksSelector();
            };
        }

        private void audit(
            String type,
            TransactionId transactionId,
            String details
        ) {
            auditLog.add(
                new AuditEvent(
                    Instant.now(),
                    type,
                    transactionId == null
                        ? "SYSTEM"
                        : transactionId.value(),
                    details
                )
            );
        }

        public void addResource(ResourceId id, int order) {
            Objects.requireNonNull(id);

            if (order < 0) {
                throw new IllegalArgumentException(
                    "Resource order must be non-negative."
                );
            }

            if (resources.containsKey(id)) {
                throw new IllegalArgumentException(
                    "Duplicate resource."
                );
            }

            boolean duplicateOrder = resources.values()
                .stream()
                .anyMatch(resource -> resource.order == order);

            if (duplicateOrder) {
                throw new IllegalArgumentException(
                    "Resource order must be unique."
                );
            }

            resources.put(id, new Resource(id, order));

            audit("RESOURCE_REGISTERED", null, id.value());
        }

        public void begin(TransactionId id) {
            Objects.requireNonNull(id);

            if (transactions.containsKey(id)) {
                throw new IllegalArgumentException(
                    "Transaction already exists."
                );
            }

            Transaction transaction =
                new Transaction(id, ++clock);

            transactions.put(id, transaction);

            audit("TRANSACTION_STARTED", id, "");
        }

        private Transaction requireActive(TransactionId id) {
            Transaction transaction = transactions.get(id);

            if (transaction == null) {
                throw new IllegalArgumentException(
                    "Unknown transaction."
                );
            }

            if (transaction.state != TransactionState.ACTIVE &&
                transaction.state != TransactionState.WAITING) {

                throw new IllegalStateException(
                    "Transaction state is " + transaction.state
                );
            }

            return transaction;
        }

        private Resource requireResource(ResourceId id) {
            Resource resource = resources.get(id);

            if (resource == null) {
                throw new IllegalArgumentException(
                    "Unknown resource: " + id.value()
                );
            }

            return resource;
        }

        private void enforcePrevention(
            Transaction transaction,
            Resource requested
        ) {
            if (preventionPolicy !=
                    PreventionPolicy.RESOURCE_ORDERING ||
                transaction.held.isEmpty()) {
                return;
            }

            int maximum = transaction.held.stream()
                .map(resources::get)
                .mapToInt(resource -> resource.order)
                .max()
                .orElse(-1);

            if (requested.order < maximum) {
                throw new IllegalStateException(
                    "Global resource ordering violation."
                );
            }
        }

        public boolean acquire(
            TransactionId transactionId,
            ResourceId resourceId
        ) {
            Transaction transaction = requireActive(transactionId);
            Resource resource = requireResource(resourceId);

            if (transaction.held.contains(resourceId)) {
                return true;
            }

            if (transaction.waitingFor != null) {
                throw new IllegalStateException(
                    "Transaction already has a pending request."
                );
            }

            enforcePrevention(transaction, resource);

            if (resource.owner == null) {
                resource.owner = transactionId;
                transaction.held.add(resourceId);

                audit(
                    "RESOURCE_ACQUIRED",
                    transactionId,
                    resourceId.value()
                );

                return true;
            }

            if (resource.owner.equals(transactionId)) {
                return true;
            }

            Transaction owner =
                transactions.get(resource.owner);

            switch (preventionPolicy) {

                case WAIT_DIE -> {
                    if (transaction.timestamp < owner.timestamp) {
                        // Older transaction is allowed to wait.
                    } else {
                        abort(transactionId);
                        throw new IllegalStateException(
                            "Wait-die rejected younger transaction."
                        );
                    }
                }

                case WOUND_WAIT -> {
                    if (transaction.timestamp < owner.timestamp) {
                        // Older requester wounds younger holder.
                        abort(owner.id);
                    } else {
                        throw new IllegalStateException(
                            "Wound-wait rejected younger requester."
                        );
                    }
                }

                default -> {
                    // Detection and recovery remain enabled.
                }
            }

            if (resource.owner == null) {
                resource.owner = transactionId;
                transaction.held.add(resourceId);

                audit(
                    "RESOURCE_ACQUIRED",
                    transactionId,
                    resourceId.value()
                );

                return true;
            }

            if (!resource.queue.contains(transactionId)) {
                resource.queue.addLast(transactionId);
            }

            transaction.state = TransactionState.WAITING;
            transaction.waitingFor = resourceId;

            audit(
                "RESOURCE_WAITING",
                transactionId,
                "Owner: " + resource.owner.value()
            );

            return false;
        }

        public Map<TransactionId, Set<TransactionId>>
                buildWaitForGraph() {

            Map<TransactionId, Set<TransactionId>> graph =
                new LinkedHashMap<>();

            for (Transaction transaction : transactions.values()) {
                if (transaction.state != TransactionState.WAITING) {
                    continue;
                }

                Resource resource =
                    resources.get(transaction.waitingFor);

                if (resource != null && resource.owner != null) {
                    graph.computeIfAbsent(
                        transaction.id,
                        ignored -> new LinkedHashSet<>()
                    ).add(resource.owner);
                }
            }

            return graph;
        }

        public List<List<TransactionId>> detectDeadlocks() {
            Map<TransactionId, Set<TransactionId>> graph =
                buildWaitForGraph();

            Map<TransactionId, Integer> colors =
                new HashMap<>();

            List<TransactionId> stack = new ArrayList<>();

            List<List<TransactionId>> cycles =
                new ArrayList<>();

            Set<String> signatures = new HashSet<>();

            for (TransactionId id : transactions.keySet()) {
                colors.put(id, 0);
            }

            class DFS {

                void visit(TransactionId id) {
                    colors.put(id, 1);
                    stack.add(id);

                    for (TransactionId next :
                            graph.getOrDefault(id, Set.of())) {

                        int color = colors.getOrDefault(next, 0);

                        if (color == 0) {
                            visit(next);
                        } else if (color == 1) {
                            int index = stack.indexOf(next);

                            List<TransactionId> cycle =
                                new ArrayList<>(
                                    stack.subList(index, stack.size())
                                );

                            String signature = canonical(cycle);

                            if (signatures.add(signature)) {
                                cycles.add(cycle);
                            }
                        }
                    }

                    stack.remove(stack.size() - 1);
                    colors.put(id, 2);
                }

                private String canonical(
                    List<TransactionId> cycle
                ) {
                    List<String> rotations = new ArrayList<>();

                    for (int i = 0; i < cycle.size(); i++) {
                        List<String> rotation = new ArrayList<>();

                        for (int j = 0; j < cycle.size(); j++) {
                            rotation.add(
                                cycle.get((i + j) % cycle.size()).value()
                            );
                        }

                        rotations.add(String.join("|", rotation));
                    }

                    return rotations.stream()
                        .sorted()
                        .findFirst()
                        .orElse("");
                }
            }

            DFS dfs = new DFS();

            for (TransactionId id : graph.keySet()) {
                if (colors.get(id) == 0) {
                    dfs.visit(id);
                }
            }

            return cycles;
        }

        private Transaction chooseVictim(
            List<TransactionId> cycle
        ) {
            List<Transaction> candidates = cycle.stream()
                .map(transactions::get)
                .filter(Objects::nonNull)
                .toList();

            return victimSelector.select(candidates);
        }

        private void removeFromQueues(TransactionId id) {
            for (Resource resource : resources.values()) {
                resource.queue.removeIf(id::equals);
            }
        }

        private void wakeWaiter(Resource resource) {
            while (resource.owner == null &&
                    !resource.queue.isEmpty()) {

                TransactionId nextId = resource.queue.removeFirst();

                Transaction next = transactions.get(nextId);

                if (next == null ||
                    next.state != TransactionState.WAITING) {
                    continue;
                }

                resource.owner = nextId;

                next.held.add(resource.id);
                next.waitingFor = null;
                next.state = TransactionState.ACTIVE;

                audit(
                    "RESOURCE_GRANTED",
                    nextId,
                    resource.id.value()
                );
            }
        }

        private void releaseAll(Transaction transaction) {
            List<ResourceId> held =
                new ArrayList<>(transaction.held);

            transaction.held.clear();

            for (ResourceId id : held) {
                Resource resource = resources.get(id);

                if (transaction.id.equals(resource.owner)) {
                    resource.owner = null;
                }
            }

            for (ResourceId id : held) {
                wakeWaiter(resources.get(id));
            }
        }

        public DeadlockReport recover(
            List<TransactionId> cycle
        ) {
            if (cycle == null || cycle.isEmpty()) {
                throw new IllegalArgumentException(
                    "Deadlock cycle is required."
                );
            }

            Transaction victim = chooseVictim(cycle);

            abort(victim.id);

            DeadlockReport report = new DeadlockReport(
                List.copyOf(cycle),
                victim.id,
                "Victim aborted to break circular wait."
            );

            audit(
                "DEADLOCK_RECOVERED",
                victim.id,
                report.recoveryReason()
            );

            return report;
        }

        public void abort(TransactionId id) {
            Transaction transaction = requireActive(id);

            removeFromQueues(id);

            transaction.waitingFor = null;
            transaction.state = TransactionState.ABORTED;
            transaction.rollbackCount++;

            releaseAll(transaction);

            audit("TRANSACTION_ABORTED", id, "Rollback completed.");
        }

        public void commit(TransactionId id) {
            Transaction transaction = requireActive(id);

            if (transaction.state != TransactionState.ACTIVE) {
                throw new IllegalStateException(
                    "Waiting transaction cannot commit."
                );
            }

            transaction.state = TransactionState.COMMITTED;

            releaseAll(transaction);

            audit("TRANSACTION_COMMITTED", id, "");
        }

        public List<DeadlockReport> detectAndRecover() {
            List<DeadlockReport> reports = new ArrayList<>();

            while (true) {
                List<List<TransactionId>> cycles =
                    detectDeadlocks();

                if (cycles.isEmpty()) {
                    break;
                }

                reports.add(recover(cycles.get(0)));
            }

            return List.copyOf(reports);
        }

        public void printStatus() {
            System.out.println("\nTRANSACTION STATUS");

            for (Transaction tx : transactions.values()) {
                System.out.printf(
                    "%s | %s | held=%s | waiting=%s%n",
                    tx.id.value(),
                    tx.state,
                    tx.held,
                    tx.waitingFor
                );
            }

            System.out.println("\nRESOURCE STATUS");

            for (Resource resource : resources.values()) {
                System.out.printf(
                    "%s | owner=%s | queue=%s%n",
                    resource.id.value(),
                    resource.owner,
                    resource.queue
                );
            }

            System.out.println("\nWAIT-FOR GRAPH");

            buildWaitForGraph().forEach(
                (id, owners) ->
                    System.out.println(id + " -> " + owners)
            );
        }

        public List<AuditEvent> auditLog() {
            return List.copyOf(auditLog);
        }
    }

    private static void detectionScenario() {
        System.out.println(
            "\nSCENARIO 1: DEADLOCK DETECTION AND RECOVERY"
        );

        ResourceManager manager = new ResourceManager(
            PreventionPolicy.NONE,
            RecoveryPolicy.YOUNGEST_TRANSACTION
        );

        ResourceId database = new ResourceId("DATABASE");
        ResourceId file = new ResourceId("FILE");

        TransactionId t1 = new TransactionId("T1");
        TransactionId t2 = new TransactionId("T2");

        manager.addResource(database, 1);
        manager.addResource(file, 2);

        manager.begin(t1);
        manager.begin(t2);

        manager.acquire(t1, database);
        manager.acquire(t2, file);

        manager.acquire(t1, file);
        manager.acquire(t2, database);

        manager.printStatus();

        List<List<TransactionId>> cycles =
            manager.detectDeadlocks();

        System.out.println("\nDETECTED CYCLES");

        cycles.forEach(System.out::println);

        List<DeadlockReport> reports =
            manager.detectAndRecover();

        System.out.println("\nRECOVERY REPORT");

        reports.forEach(System.out::println);

        manager.printStatus();

        if (manager.transactions.get(t1).state ==
                TransactionState.ACTIVE) {
            manager.commit(t1);
        }

        manager.printStatus();
    }

    private static void preventionScenario() {
        System.out.println(
            "\nSCENARIO 2: RESOURCE ORDERING PREVENTION"
        );

        ResourceManager manager = new ResourceManager(
            PreventionPolicy.RESOURCE_ORDERING,
            RecoveryPolicy.FEWEST_LOCKS
        );

        ResourceId account = new ResourceId("ACCOUNT");
        ResourceId ledger = new ResourceId("LEDGER");

        TransactionId payment = new TransactionId("PAYMENT");

        manager.addResource(account, 1);
        manager.addResource(ledger, 2);

        manager.begin(payment);

        manager.acquire(payment, account);
        manager.acquire(payment, ledger);

        try {
            manager.acquire(payment, account);
        } catch (IllegalStateException error) {
            System.out.println(
                "[PREVENTION] " + error.getMessage()
            );
        }

        manager.commit(payment);
    }

    private static void waitDieScenario() {
        System.out.println(
            "\nSCENARIO 3: WAIT-DIE PREVENTION"
        );

        ResourceManager manager = new ResourceManager(
            PreventionPolicy.WAIT_DIE,
            RecoveryPolicy.YOUNGEST_TRANSACTION
        );

        ResourceId account = new ResourceId("ACCOUNT");

        TransactionId older = new TransactionId("OLDER");
        TransactionId younger = new TransactionId("YOUNGER");

        manager.addResource(account, 1);

        manager.begin(older);
        manager.begin(younger);

        manager.acquire(older, account);

        try {
            manager.acquire(younger, account);
        } catch (IllegalStateException error) {
            System.out.println("[WAIT-DIE] " + error.getMessage());
        }

        manager.commit(older);
    }

    public static void main(String[] args) {
        detectionScenario();
        preventionScenario();
        waitDieScenario();

        System.out.println(
            "\nEnterprise deadlock governance demonstrations completed."
        );
    }
}
