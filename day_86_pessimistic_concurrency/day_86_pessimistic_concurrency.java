import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/*
 * Pessimistic Concurrency: Enterprise Lock-Based Transaction Service
 *
 * Enterprise scenario:
 * Concurrent bank transfers with account-level pessimistic locks.
 *
 * Features:
 * - Shared and exclusive locking
 * - ReentrantReadWriteLock
 * - Deterministic lock ordering
 * - Timed lock acquisition
 * - Strict two-phase locking
 * - Transaction lifecycle management
 * - Rollback support
 * - Audit events
 * - Business validation
 * - Concurrent execution
 */

public class Main {

    enum LockMode {
        SHARED,
        EXCLUSIVE
    }

    enum TransactionState {
        ACTIVE,
        COMMITTED,
        ABORTED
    }

    record Account(String id, long balance) {
        Account {
            if (id == null || id.isBlank()) {
                throw new IllegalArgumentException("Invalid account ID");
            }

            if (balance < 0) {
                throw new IllegalArgumentException("Negative balance");
            }
        }
    }

    record AuditEvent(
        long transactionId,
        String operation,
        String resource,
        long timestamp
    ) {}

    static class TransactionException extends RuntimeException {
        TransactionException(String message) {
            super(message);
        }
    }

    static class LockTimeoutException extends TransactionException {
        LockTimeoutException(String message) {
            super(message);
        }
    }

    static class Transaction {

        private final long id;
        private final Map<String, Long> undoLog = new HashMap<>();
        private final Set<String> lockedResources = new HashSet<>();

        private TransactionState state = TransactionState.ACTIVE;
        private boolean growing = true;

        Transaction(long id) {
            this.id = id;
        }

        long id() {
            return id;
        }

        TransactionState state() {
            return state;
        }
    }

    interface LockPolicy {
        void acquire(
            Transaction transaction,
            String resource,
            LockMode mode,
            Duration timeout
        );
    }

    static class LockRegistry implements LockPolicy {

        private final Map<String, ReentrantReadWriteLock> locks =
            new ConcurrentHashMap<>();

        private final List<AuditEvent> auditEvents =
            java.util.Collections.synchronizedList(new ArrayList<>());

        private final AtomicLong sequence = new AtomicLong();

        private ReentrantReadWriteLock getLock(String resource) {
            return locks.computeIfAbsent(
                resource,
                ignored -> new ReentrantReadWriteLock(true)
            );
        }

        @Override
        public void acquire(
            Transaction transaction,
            String resource,
            LockMode mode,
            Duration timeout
        ) {
            if (transaction.state != TransactionState.ACTIVE) {
                throw new TransactionException("Inactive transaction");
            }

            if (resource == null || resource.isBlank()) {
                throw new IllegalArgumentException("Invalid resource");
            }

            if (timeout == null || timeout.isNegative()) {
                throw new IllegalArgumentException("Invalid timeout");
            }

            if (transaction.lockedResources.contains(resource)) {
                return;
            }

            if (!transaction.growing) {
                throw new TransactionException(
                    "Strict 2PL violation"
                );
            }

            ReentrantReadWriteLock lock = getLock(resource);

            boolean acquired;

            try {
                if (mode == LockMode.SHARED) {
                    acquired = lock.readLock().tryLock(
                        timeout.toNanos(),
                        TimeUnit.NANOSECONDS
                    );
                } else {
                    acquired = lock.writeLock().tryLock(
                        timeout.toNanos(),
                        TimeUnit.NANOSECONDS
                    );
                }

            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();

                throw new TransactionException(
                    "Lock acquisition interrupted"
                );
            }

            if (!acquired) {
                throw new LockTimeoutException(
                    "Timeout acquiring " + resource
                );
            }

            transaction.lockedResources.add(resource);

            auditEvents.add(new AuditEvent(
                transaction.id,
                "LOCK_" + mode,
                resource,
                System.currentTimeMillis()
            ));
        }

        void releaseAll(Transaction transaction) {
            List<String> resources = new ArrayList<>(
                transaction.lockedResources
            );

            resources.sort(Comparator.reverseOrder());

            for (String resource : resources) {
                ReentrantReadWriteLock lock = getLock(resource);

                // This service uses exclusive account locks.
                lock.writeLock().unlock();
            }

            transaction.lockedResources.clear();
        }

        List<AuditEvent> auditTrail() {
            synchronized (auditEvents) {
                return List.copyOf(auditEvents);
            }
        }
    }

    static class AccountRepository {

        private final Map<String, Long> balances =
            new ConcurrentHashMap<>();

        AccountRepository(List<Account> accounts) {
            for (Account account : accounts) {
                if (
                    balances.putIfAbsent(
                        account.id(),
                        account.balance()
                    ) != null
                ) {
                    throw new IllegalArgumentException(
                        "Duplicate account"
                    );
                }
            }
        }

        long balance(String id) {
            Long value = balances.get(id);

            if (value == null) {
                throw new TransactionException(
                    "Account not found: " + id
                );
            }

            return value;
        }

        void update(
            Transaction transaction,
            String id,
            long newBalance
        ) {
            if (newBalance < 0) {
                throw new TransactionException(
                    "Balance cannot become negative"
                );
            }

            if (!transaction.lockedResources.contains(id)) {
                throw new TransactionException(
                    "Exclusive account lock required"
                );
            }

            if (!transaction.undoLog.containsKey(id)) {
                transaction.undoLog.put(id, balance(id));
            }

            balances.put(id, newBalance);
        }

        void rollback(Transaction transaction) {
            List<Map.Entry<String, Long>> entries =
                new ArrayList<>(transaction.undoLog.entrySet());

            for (int i = entries.size() - 1; i >= 0; i--) {
                Map.Entry<String, Long> entry = entries.get(i);

                balances.put(entry.getKey(), entry.getValue());
            }

            transaction.undoLog.clear();
        }

        Map<String, Long> snapshot() {
            return Map.copyOf(balances);
        }

        long total() {
            return balances.values()
                .stream()
                .mapToLong(Long::longValue)
                .sum();
        }
    }

    static class TransactionManager {

        private final LockRegistry registry;
        private final AccountRepository repository;

        private final AtomicLong ids = new AtomicLong(1);

        TransactionManager(
            LockRegistry registry,
            AccountRepository repository
        ) {
            this.registry = registry;
            this.repository = repository;
        }

        Transaction begin() {
            return new Transaction(ids.getAndIncrement());
        }

        void acquire(
            Transaction transaction,
            String resource,
            LockMode mode,
            Duration timeout
        ) {
            registry.acquire(transaction, resource, mode, timeout);
        }

        void commit(Transaction transaction) {
            if (transaction.state != TransactionState.ACTIVE) {
                throw new TransactionException(
                    "Transaction is not active"
                );
            }

            transaction.growing = false;
            transaction.state = TransactionState.COMMITTED;

            // Strict 2PL releases locks only after commit.
            registry.releaseAll(transaction);
        }

        void rollback(Transaction transaction) {
            if (transaction.state != TransactionState.ACTIVE) {
                return;
            }

            repository.rollback(transaction);

            transaction.growing = false;
            transaction.state = TransactionState.ABORTED;

            registry.releaseAll(transaction);
        }
    }

    static class BankingService {

        private final AccountRepository repository;
        private final TransactionManager transactionManager;

        private final Duration lockTimeout =
            Duration.ofSeconds(3);

        BankingService(
            AccountRepository repository,
            TransactionManager transactionManager
        ) {
            this.repository = repository;
            this.transactionManager = transactionManager;
        }

        void transfer(
            String source,
            String destination,
            long amount
        ) {
            if (source == null || destination == null) {
                throw new IllegalArgumentException(
                    "Account IDs are required"
                );
            }

            if (source.equals(destination)) {
                throw new IllegalArgumentException(
                    "Accounts must differ"
                );
            }

            if (amount <= 0) {
                throw new IllegalArgumentException(
                    "Amount must be positive"
                );
            }

            Transaction transaction =
                transactionManager.begin();

            try {
                // Acquire locks in a deterministic global order.
                // This prevents circular wait for these transfers.
                Set<String> ordered = new TreeSet<>(
                    List.of(source, destination)
                );

                for (String account : ordered) {
                    transactionManager.acquire(
                        transaction,
                        account,
                        LockMode.EXCLUSIVE,
                        lockTimeout
                    );
                }

                long sourceBalance = repository.balance(source);
                long destinationBalance = repository.balance(destination);

                if (sourceBalance < amount) {
                    throw new TransactionException(
                        "Insufficient funds"
                    );
                }

                long newDestinationBalance =
                    Math.addExact(destinationBalance, amount);

                repository.update(
                    transaction,
                    source,
                    sourceBalance - amount
                );

                repository.update(
                    transaction,
                    destination,
                    newDestinationBalance
                );

                transactionManager.commit(transaction);

            } catch (RuntimeException exception) {
                transactionManager.rollback(transaction);
                throw exception;
            }
        }

        Map<String, Long> balances() {
            return repository.snapshot();
        }
    }

    public static void main(String[] args) throws Exception {

        System.out.println(
            "PESSIMISTIC CONCURRENCY: ENTERPRISE BANKING"
        );

        LockRegistry registry = new LockRegistry();

        AccountRepository repository = new AccountRepository(
            List.of(
                new Account("ACC-1001", 100_000),
                new Account("ACC-1002", 80_000),
                new Account("ACC-1003", 60_000)
            )
        );

        TransactionManager manager =
            new TransactionManager(registry, repository);

        BankingService banking =
            new BankingService(repository, manager);

        long initialTotal = repository.total();

        List<Thread> workers = new ArrayList<>();

        for (int i = 0; i < 12; i++) {
            final int index = i;

            Thread worker = new Thread(() -> {
                try {
                    String source;
                    String destination;

                    if (index % 2 == 0) {
                        source = "ACC-1001";
                        destination = "ACC-1002";
                    } else {
                        source = "ACC-1002";
                        destination = "ACC-1003";
                    }

                    banking.transfer(
                        source,
                        destination,
                        500
                    );

                } catch (TransactionException exception) {
                    System.err.println(
                        "Transaction rejected: " +
                        exception.getMessage()
                    );
                }
            });

            workers.add(worker);
            worker.start();
        }

        for (Thread worker : workers) {
            worker.join();
        }

        System.out.println("\nFinal balances:");

        banking.balances().forEach(
            (account, balance) ->
                System.out.println(account + ": " + balance)
        );

        if (repository.total() != initialTotal) {
            throw new IllegalStateException(
                "Financial conservation invariant violated"
            );
        }

        System.out.println(
            "\nInitial total: " + initialTotal
        );

        System.out.println(
            "Final total: " + repository.total()
        );

        System.out.println(
            "Audit events: " + registry.auditTrail().size()
        );

        System.out.println(
            "Financial invariants verified."
        );
    }
}
