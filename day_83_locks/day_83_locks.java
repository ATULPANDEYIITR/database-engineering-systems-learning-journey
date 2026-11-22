// Locks.java
// Shared Locks, Exclusive Locks, and Lock Compatibility
// Java 17
//
// Enterprise-oriented transaction locking model.
// Includes domain records, explicit policies, immutable snapshots,
// synchronized state management, compatibility validation,
// queued requests, transaction lifecycle, and merge-free lock evaluation.

import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

public class Locks {

    enum LockMode {
        SHARED,
        EXCLUSIVE
    }

    enum TransactionStatus {
        ACTIVE,
        COMMITTED,
        ROLLED_BACK
    }

    enum RequestStatus {
        GRANTED,
        WAITING,
        REJECTED
    }

    enum LockFailure {
        INVALID_REQUEST,
        INCOMPATIBLE_HOLDER,
        UPGRADE_CONFLICT,
        TRANSACTION_INACTIVE,
        LOCK_NOT_HELD
    }

    record LockPolicy(
        boolean allowShared,
        boolean allowExclusive,
        boolean allowUpgrade
    ) {
        LockPolicy {
            if (!allowShared && !allowExclusive) {
                throw new IllegalArgumentException(
                    "At least one lock mode must be permitted."
                );
            }
        }

        boolean permits(LockMode mode) {
            return mode == LockMode.SHARED
                ? allowShared
                : allowExclusive;
        }
    }

    record LockRequest(
        String transactionId,
        String resource,
        LockMode mode,
        Instant requestedAt,
        long sequence
    ) {}

    record HolderSnapshot(
        String transactionId,
        LockMode mode,
        int acquisitionCount
    ) {}

    record ResourceSnapshot(
        String resource,
        List<HolderSnapshot> holders,
        List<LockRequest> waiting
    ) {}

    static class LockException extends RuntimeException {
        private final LockFailure failure;

        LockException(
            LockFailure failure,
            String message
        ) {
            super(message);
            this.failure = failure;
        }

        LockFailure failure() {
            return failure;
        }
    }

    static final class Holder {
        LockMode mode;
        int count;

        Holder(LockMode mode) {
            this.mode = mode;
            this.count = 1;
        }
    }

    static final class ResourceState {
        final Map<String, Holder> holders = new HashMap<>();
        final Deque<LockRequest> waiting = new ArrayDeque<>();
    }

    static final class LockManager {

        private final Map<String, ResourceState> resources =
            new HashMap<>();

        private final Map<String, LockPolicy> policies =
            new HashMap<>();

        private long sequence = 0;

        LockManager() {
            LockPolicy standardPolicy =
                new LockPolicy(true, true, true);

            policies.put("DEFAULT", standardPolicy);
        }

        synchronized void configurePolicy(
            String resource,
            LockPolicy policy
        ) {
            validateResource(resource);

            ResourceState state = resources.get(resource);

            if (
                state != null &&
                (!state.holders.isEmpty() || !state.waiting.isEmpty())
            ) {
                throw new IllegalStateException(
                    "Cannot change policy while resource is in use."
                );
            }

            policies.put(resource, Objects.requireNonNull(policy));
        }

        synchronized RequestStatus acquire(
            String transactionId,
            String resource,
            LockMode mode
        ) {
            validateRequest(transactionId, resource, mode);

            ResourceState state = resources.computeIfAbsent(
                resource,
                ignored -> new ResourceState()
            );

            LockPolicy policy = policies.getOrDefault(
                resource,
                policies.get("DEFAULT")
            );

            if (!policy.permits(mode)) {
                throw new LockException(
                    LockFailure.INVALID_REQUEST,
                    "Lock mode is prohibited by resource policy."
                );
            }

            Holder existing = state.holders.get(transactionId);

            if (existing != null) {
                if (
                    existing.mode == LockMode.EXCLUSIVE ||
                    mode == LockMode.SHARED
                ) {
                    existing.count++;
                    return RequestStatus.GRANTED;
                }

                if (!policy.allowUpgrade()) {
                    throw new LockException(
                        LockFailure.UPGRADE_CONFLICT,
                        "Lock upgrades are prohibited."
                    );
                }

                if (state.holders.size() > 1) {
                    throw new LockException(
                        LockFailure.UPGRADE_CONFLICT,
                        "Upgrade rejected because other readers exist."
                    );
                }
            }

            LockRequest request = new LockRequest(
                transactionId,
                resource,
                mode,
                Instant.now(),
                ++sequence
            );

            if (canGrant(state, request)) {
                grant(state, request);
                return RequestStatus.GRANTED;
            }

            state.waiting.addLast(request);
            return RequestStatus.WAITING;
        }

        private boolean canGrant(
            ResourceState state,
            LockRequest request
        ) {
            for (Map.Entry<String, Holder> entry :
                state.holders.entrySet()) {

                if (entry.getKey().equals(request.transactionId())) {
                    continue;
                }

                if (
                    request.mode() == LockMode.EXCLUSIVE ||
                    entry.getValue().mode == LockMode.EXCLUSIVE
                ) {
                    return false;
                }
            }

            // Preserve FIFO fairness for incompatible requests.
            for (LockRequest earlier : state.waiting) {
                if (earlier == request) {
                    break;
                }

                if (
                    earlier.mode() == LockMode.EXCLUSIVE ||
                    request.mode() == LockMode.EXCLUSIVE
                ) {
                    return false;
                }
            }

            return true;
        }

        private void grant(
            ResourceState state,
            LockRequest request
        ) {
            Holder holder = state.holders.get(
                request.transactionId()
            );

            if (holder == null) {
                state.holders.put(
                    request.transactionId(),
                    new Holder(request.mode())
                );
            } else {
                holder.mode = request.mode();
                holder.count = 1;
            }
        }

        synchronized void release(
            String transactionId,
            String resource
        ) {
            ResourceState state = resources.get(resource);

            if (
                state == null ||
                !state.holders.containsKey(transactionId)
            ) {
                throw new LockException(
                    LockFailure.LOCK_NOT_HELD,
                    "Transaction does not own the requested lock."
                );
            }

            Holder holder = state.holders.get(transactionId);

            holder.count--;

            if (holder.count == 0) {
                state.holders.remove(transactionId);
            }

            drain(resource);
        }

        synchronized void releaseAll(String transactionId) {
            for (String resource : resources.keySet()) {
                ResourceState state = resources.get(resource);

                state.holders.remove(transactionId);

                state.waiting.removeIf(
                    request ->
                        request.transactionId().equals(transactionId)
                );
            }

            for (String resource : resources.keySet()) {
                drain(resource);
            }
        }

        private void drain(String resource) {
            ResourceState state = resources.get(resource);

            if (state == null) {
                return;
            }

            while (!state.waiting.isEmpty()) {
                LockRequest request = state.waiting.peekFirst();

                if (!canGrant(state, request)) {
                    break;
                }

                state.waiting.removeFirst();
                grant(state, request);
            }
        }

        synchronized ResourceSnapshot snapshot(String resource) {
            ResourceState state = resources.get(resource);

            if (state == null) {
                return new ResourceSnapshot(
                    resource,
                    List.of(),
                    List.of()
                );
            }

            List<HolderSnapshot> holders = new ArrayList<>();

            state.holders.forEach((id, holder) ->
                holders.add(
                    new HolderSnapshot(
                        id,
                        holder.mode,
                        holder.count
                    )
                )
            );

            return new ResourceSnapshot(
                resource,
                List.copyOf(holders),
                List.copyOf(state.waiting)
            );
        }

        private void validateRequest(
            String transactionId,
            String resource,
            LockMode mode
        ) {
            if (
                transactionId == null ||
                transactionId.isBlank() ||
                resource == null ||
                resource.isBlank() ||
                mode == null
            ) {
                throw new LockException(
                    LockFailure.INVALID_REQUEST,
                    "Invalid transaction, resource, or lock mode."
                );
            }
        }

        private void validateResource(String resource) {
            if (resource == null || resource.isBlank()) {
                throw new IllegalArgumentException(
                    "Resource is required."
                );
            }
        }
    }

    static final class Transaction {

        private final String id;
        private final LockManager manager;

        private TransactionStatus status =
            TransactionStatus.ACTIVE;

        Transaction(String id, LockManager manager) {
            this.id = Objects.requireNonNull(id);
            this.manager = Objects.requireNonNull(manager);
        }

        RequestStatus shared(String resource) {
            checkActive();

            return manager.acquire(
                id,
                resource,
                LockMode.SHARED
            );
        }

        RequestStatus exclusive(String resource) {
            checkActive();

            return manager.acquire(
                id,
                resource,
                LockMode.EXCLUSIVE
            );
        }

        void commit() {
            complete(TransactionStatus.COMMITTED);
        }

        void rollback() {
            complete(TransactionStatus.ROLLED_BACK);
        }

        private void complete(TransactionStatus finalStatus) {
            checkActive();

            manager.releaseAll(id);
            status = finalStatus;
        }

        private void checkActive() {
            if (status != TransactionStatus.ACTIVE) {
                throw new LockException(
                    LockFailure.TRANSACTION_INACTIVE,
                    "Transaction is not active."
                );
            }
        }

        TransactionStatus status() {
            return status;
        }

        String id() {
            return id;
        }
    }

    static final class LockEligibilityService {

        private final LockManager manager;

        LockEligibilityService(LockManager manager) {
            this.manager = manager;
        }

        boolean canAcquireImmediately(
            String transactionId,
            String resource,
            LockMode requestedMode
        ) {
            ResourceSnapshot snapshot = manager.snapshot(resource);

            for (HolderSnapshot holder : snapshot.holders()) {
                if (holder.transactionId().equals(transactionId)) {
                    continue;
                }

                if (
                    requestedMode == LockMode.EXCLUSIVE ||
                    holder.mode() == LockMode.EXCLUSIVE
                ) {
                    return false;
                }
            }

            return snapshot.waiting().isEmpty() ||
                (
                    requestedMode == LockMode.SHARED &&
                    snapshot.waiting().stream()
                        .noneMatch(r -> r.mode() == LockMode.EXCLUSIVE)
                );
        }
    }

    private static void compatibilityScenario() {
        System.out.println("\n1. Shared lock compatibility");

        LockManager manager = new LockManager();

        Transaction t1 = new Transaction("T1", manager);
        Transaction t2 = new Transaction("T2", manager);
        Transaction t3 = new Transaction("T3", manager);

        t1.shared("account:100");
        t2.shared("account:100");

        System.out.println(manager.snapshot("account:100"));

        RequestStatus result = t3.exclusive("account:100");

        System.out.println("T3 exclusive request: " + result);

        t1.commit();

        System.out.println(manager.snapshot("account:100"));

        t2.commit();

        System.out.println(manager.snapshot("account:100"));

        t3.commit();
    }

    private static void upgradeScenario() {
        System.out.println("\n2. Shared-to-exclusive upgrade");

        LockManager manager = new LockManager();

        Transaction t1 = new Transaction("T10", manager);
        Transaction t2 = new Transaction("T20", manager);

        t1.shared("inventory:10");
        t2.shared("inventory:10");

        try {
            t1.exclusive("inventory:10");
        } catch (LockException error) {
            System.out.println(
                error.failure() + ": " + error.getMessage()
            );
        }

        t1.rollback();
        t2.rollback();
    }

    private static void policyScenario() {
        System.out.println("\n3. Resource-specific lock policy");

        LockManager manager = new LockManager();

        manager.configurePolicy(
            "audit:logs",
            new LockPolicy(true, false, false)
        );

        Transaction t1 = new Transaction("AUDIT-1", manager);

        t1.shared("audit:logs");

        try {
            t1.exclusive("audit:logs");
        } catch (LockException error) {
            System.out.println(
                "Policy rejection: " + error.getMessage()
            );
        }

        t1.commit();
    }

    private static void independentResourcesScenario() {
        System.out.println("\n4. Independent resource access");

        LockManager manager = new LockManager();

        Transaction t1 = new Transaction(
            UUID.randomUUID().toString(),
            manager
        );

        Transaction t2 = new Transaction(
            UUID.randomUUID().toString(),
            manager
        );

        t1.exclusive("orders:100");
        t2.exclusive("orders:200");

        System.out.println(manager.snapshot("orders:100"));
        System.out.println(manager.snapshot("orders:200"));

        LockEligibilityService eligibility =
            new LockEligibilityService(manager);

        System.out.println(
            "Independent resource available: " +
            eligibility.canAcquireImmediately(
                t1.id(),
                "orders:200",
                LockMode.SHARED
            )
        );

        t1.commit();
        t2.commit();
    }

    public static void main(String[] args) {
        compatibilityScenario();
        upgradeScenario();
        policyScenario();
        independentResourcesScenario();

        System.out.println("\nAll Java demonstrations completed.");
    }
}
