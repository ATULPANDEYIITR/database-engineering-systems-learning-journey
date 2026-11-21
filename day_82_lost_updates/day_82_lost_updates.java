import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.ReentrantLock;

/*
 * Lost Updates: Enterprise account transaction management.
 *
 * Java 17 implementation featuring:
 * - Domain records and immutable snapshots.
 * - Repository abstraction.
 * - Optimistic version validation.
 * - Pessimistic account-level locking.
 * - Transaction policies.
 * - Retry management.
 * - Audit events.
 * - Idempotent request processing.
 */

public class LostUpdateEnterprise {

    enum Operation {
        DEPOSIT,
        WITHDRAW
    }

    enum ConcurrencyStrategy {
        UNSAFE,
        OPTIMISTIC,
        PESSIMISTIC
    }

    enum TransactionStatus {
        COMMITTED,
        CONFLICT,
        REJECTED
    }

    record AccountSnapshot(
        long accountId,
        String owner,
        long balance,
        long version
    ) {}

    record TransactionRequest(
        String requestId,
        long accountId,
        long amount,
        Operation operation
    ) {
        TransactionRequest {
            if (requestId == null || requestId.isBlank()) {
                throw new ValidationException(
                    "Request identifier is required."
                );
            }

            if (accountId <= 0 || amount <= 0) {
                throw new ValidationException(
                    "Account ID and amount must be positive."
                );
            }

            if (operation == null) {
                throw new ValidationException(
                    "Operation is required."
                );
            }
        }
    }

    record TransactionResult(
        TransactionStatus status,
        String message,
        Optional<AccountSnapshot> account,
        String transactionId
    ) {}

    record AuditEvent(
        String transactionId,
        long accountId,
        long previousBalance,
        long currentBalance,
        long previousVersion,
        long currentVersion,
        Operation operation,
        ConcurrencyStrategy strategy,
        Instant timestamp
    ) {}

    static class ValidationException extends RuntimeException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class ConcurrencyException extends RuntimeException {
        ConcurrencyException(String message) {
            super(message);
        }
    }

    static class Account {
        private final long id;
        private final String owner;
        private long balance;
        private long version;

        Account(long id, String owner, long balance) {
            if (id <= 0) {
                throw new ValidationException(
                    "Account ID must be positive."
                );
            }

            if (owner == null || owner.isBlank()) {
                throw new ValidationException(
                    "Account owner is required."
                );
            }

            if (balance < 0) {
                throw new ValidationException(
                    "Initial balance cannot be negative."
                );
            }

            this.id = id;
            this.owner = owner;
            this.balance = balance;
            this.version = 0;
        }

        AccountSnapshot snapshot() {
            return new AccountSnapshot(
                id, owner, balance, version
            );
        }
    }

    interface TransactionPolicy {
        TransactionResult execute(
            TransactionRequest request,
            AccountSnapshot snapshot
        );
    }

    static class OptimisticPolicy implements TransactionPolicy {

        private final AccountRepository repository;

        OptimisticPolicy(AccountRepository repository) {
            this.repository = repository;
        }

        @Override
        public TransactionResult execute(
            TransactionRequest request,
            AccountSnapshot snapshot
        ) {
            return repository.optimisticWrite(request, snapshot);
        }
    }

    static class PessimisticPolicy implements TransactionPolicy {

        private final AccountRepository repository;

        PessimisticPolicy(AccountRepository repository) {
            this.repository = repository;
        }

        @Override
        public TransactionResult execute(
            TransactionRequest request,
            AccountSnapshot snapshot
        ) {
            return repository.pessimisticWrite(request);
        }
    }

    static class AccountRepository {

        private final Map<Long, Account> accounts =
            new ConcurrentHashMap<>();

        private final Map<Long, ReentrantLock> locks =
            new ConcurrentHashMap<>();

        private final List<AuditEvent> audit =
            Collections.synchronizedList(new ArrayList<>());

        private final Map<String, TransactionResult> idempotency =
            new ConcurrentHashMap<>();

        private final AtomicLong transactionSequence =
            new AtomicLong(1);

        void create(Account account) {
            AccountSnapshot snapshot = account.snapshot();

            Account previous = accounts.putIfAbsent(
                snapshot.accountId(), account
            );

            if (previous != null) {
                throw new ValidationException(
                    "Duplicate account."
                );
            }

            locks.put(
                snapshot.accountId(),
                new ReentrantLock(true)
            );
        }

        AccountSnapshot read(long id) {
            Account account = accounts.get(id);

            if (account == null) {
                throw new ValidationException(
                    "Account not found."
                );
            }

            synchronized (account) {
                return account.snapshot();
            }
        }

        private long calculate(
            long current,
            long amount,
            Operation operation
        ) {
            try {
                if (operation == Operation.DEPOSIT) {
                    return Math.addExact(current, amount);
                }

                if (current < amount) {
                    throw new ValidationException(
                        "Insufficient funds."
                    );
                }

                return Math.subtractExact(current, amount);

            } catch (ArithmeticException error) {
                throw new ValidationException(
                    "Balance overflow."
                );
            }
        }

        private TransactionResult commit(
            Account account,
            TransactionRequest request,
            Long expectedVersion,
            ConcurrencyStrategy strategy
        ) {
            synchronized (account) {
                AccountSnapshot previous = account.snapshot();

                if (expectedVersion != null &&
                    account.version != expectedVersion) {

                    return new TransactionResult(
                        TransactionStatus.CONFLICT,
                        "Stale account version.",
                        Optional.of(previous),
                        null
                    );
                }

                long newBalance = calculate(
                    account.balance,
                    request.amount(),
                    request.operation()
                );

                account.balance = newBalance;
                account.version++;

                AccountSnapshot current = account.snapshot();

                String transactionId = "TX-" +
                    transactionSequence.getAndIncrement();

                audit.add(new AuditEvent(
                    transactionId,
                    account.id,
                    previous.balance(),
                    current.balance(),
                    previous.version(),
                    current.version(),
                    request.operation(),
                    strategy,
                    Instant.now()
                ));

                return new TransactionResult(
                    TransactionStatus.COMMITTED,
                    "Transaction committed.",
                    Optional.of(current),
                    transactionId
                );
            }
        }

        /*
         * Demonstrates the unsafe stale-snapshot behavior.
         */
        TransactionResult unsafeWrite(
            TransactionRequest request,
            AccountSnapshot staleSnapshot
        ) {
            Account account = accounts.get(request.accountId());

            if (account == null) {
                throw new ValidationException("Account not found.");
            }

            synchronized (account) {
                AccountSnapshot previous = account.snapshot();

                long newBalance = calculate(
                    staleSnapshot.balance(),
                    request.amount(),
                    request.operation()
                );

                account.balance = newBalance;
                account.version++;

                AccountSnapshot current = account.snapshot();

                String transactionId = "TX-" +
                    transactionSequence.getAndIncrement();

                audit.add(new AuditEvent(
                    transactionId,
                    account.id,
                    previous.balance(),
                    current.balance(),
                    previous.version(),
                    current.version(),
                    request.operation(),
                    ConcurrencyStrategy.UNSAFE,
                    Instant.now()
                ));

                return new TransactionResult(
                    TransactionStatus.COMMITTED,
                    "Unsafe write committed.",
                    Optional.of(current),
                    transactionId
                );
            }
        }

        TransactionResult optimisticWrite(
            TransactionRequest request,
            AccountSnapshot snapshot
        ) {
            Account account = accounts.get(request.accountId());

            if (account == null) {
                throw new ValidationException("Account not found.");
            }

            return commit(
                account,
                request,
                snapshot.version(),
                ConcurrencyStrategy.OPTIMISTIC
            );
        }

        TransactionResult pessimisticWrite(
            TransactionRequest request
        ) {
            ReentrantLock lock = locks.get(request.accountId());

            Account account = accounts.get(request.accountId());

            if (lock == null || account == null) {
                throw new ValidationException("Account not found.");
            }

            lock.lock();

            try {
                return commit(
                    account,
                    request,
                    null,
                    ConcurrencyStrategy.PESSIMISTIC
                );
            } finally {
                lock.unlock();
            }
        }

        TransactionResult executeIdempotent(
            TransactionRequest request,
            TransactionPolicy policy
        ) {
            TransactionResult existing =
                idempotency.get(request.requestId());

            if (existing != null) {
                return existing;
            }

            TransactionResult result;

            try {
                result = policy.execute(
                    request,
                    read(request.accountId())
                );
            } catch (RuntimeException error) {
                throw error;
            }

            if (result.status() != TransactionStatus.COMMITTED) {
                return result;
            }

            TransactionResult previous = idempotency.putIfAbsent(
                request.requestId(),
                result
            );

            return previous == null ? result : previous;
        }

        List<AuditEvent> auditReport() {
            synchronized (audit) {
                return List.copyOf(audit);
            }
        }
    }

    static class TransactionService {

        private final AccountRepository repository;
        private final TransactionPolicy optimisticPolicy;
        private final TransactionPolicy pessimisticPolicy;

        TransactionService(AccountRepository repository) {
            this.repository = repository;
            this.optimisticPolicy =
                new OptimisticPolicy(repository);
            this.pessimisticPolicy =
                new PessimisticPolicy(repository);
        }

        TransactionResult optimistic(
            TransactionRequest request,
            int maxAttempts
        ) {
            if (maxAttempts < 1) {
                throw new ValidationException(
                    "Retry count must be positive."
                );
            }

            for (int attempt = 0; attempt < maxAttempts; attempt++) {
                AccountSnapshot snapshot =
                    repository.read(request.accountId());

                TransactionResult result =
                    optimisticPolicy.execute(request, snapshot);

                if (result.status() != TransactionStatus.CONFLICT) {
                    return result;
                }

                try {
                    Thread.sleep(Math.min(10L * (attempt + 1), 100L));
                } catch (InterruptedException error) {
                    Thread.currentThread().interrupt();

                    throw new ConcurrencyException(
                        "Transaction retry interrupted."
                    );
                }
            }

            throw new ConcurrencyException(
                "Maximum concurrency retries exceeded."
            );
        }

        TransactionResult pessimistic(
            TransactionRequest request
        ) {
            return pessimisticPolicy.execute(
                request,
                repository.read(request.accountId())
            );
        }
    }

    private static TransactionRequest request(
        String id,
        long accountId,
        long amount,
        Operation operation
    ) {
        return new TransactionRequest(
            id, accountId, amount, operation
        );
    }

    static void demonstrateLostUpdate() {
        System.out.println("\n1. Lost update");

        AccountRepository repository = new AccountRepository();
        repository.create(new Account(1, "Customer A", 1000));

        AccountSnapshot first = repository.read(1);
        AccountSnapshot second = repository.read(1);

        repository.unsafeWrite(
            request("unsafe-1", 1, 200, Operation.DEPOSIT),
            first
        );

        repository.unsafeWrite(
            request("unsafe-2", 1, 100, Operation.WITHDRAW),
            second
        );

        System.out.println("Expected balance: 1100");
        System.out.println("Actual balance: " +
            repository.read(1).balance());
    }

    static void demonstrateOptimisticLocking() {
        System.out.println("\n2. Optimistic locking");

        AccountRepository repository = new AccountRepository();
        repository.create(new Account(2, "Customer B", 1000));

        AccountSnapshot first = repository.read(2);
        AccountSnapshot second = repository.read(2);

        TransactionRequest deposit =
            request("opt-1", 2, 200, Operation.DEPOSIT);

        TransactionRequest withdrawal =
            request("opt-2", 2, 100, Operation.WITHDRAW);

        System.out.println(
            repository.optimisticWrite(deposit, first).message()
        );

        TransactionResult stale =
            repository.optimisticWrite(withdrawal, second);

        System.out.println("Second transaction: " + stale.message());

        TransactionService service = new TransactionService(repository);

        service.optimistic(
            request("opt-3", 2, 100, Operation.WITHDRAW),
            4
        );

        System.out.println(
            "Final balance: " + repository.read(2).balance()
        );
    }

    static void demonstratePessimisticLocking()
        throws Exception {

        System.out.println("\n3. Pessimistic locking");

        AccountRepository repository = new AccountRepository();
        repository.create(new Account(3, "Customer C", 1000));

        TransactionService service = new TransactionService(repository);

        int workers = 6;
        int operations = 100;

        ExecutorService executor =
            Executors.newFixedThreadPool(workers);

        try {
            List<Future<?>> futures = new ArrayList<>();

            for (int i = 0; i < workers; i++) {
                futures.add(executor.submit(() -> {
                    for (int j = 0; j < operations; j++) {
                        service.pessimistic(
                            request(
                                UUID.randomUUID().toString(),
                                3,
                                10,
                                Operation.DEPOSIT
                            )
                        );
                    }
                }));
            }

            for (Future<?> future : futures) {
                future.get();
            }
        } finally {
            executor.shutdown();
        }

        System.out.println("Expected balance: 7000");
        System.out.println(
            "Actual balance: " + repository.read(3).balance()
        );
    }

    static void demonstrateIdempotency() {
        System.out.println("\n4. Idempotent processing");

        AccountRepository repository = new AccountRepository();
        repository.create(new Account(4, "Customer D", 500));

        TransactionRequest payment =
            request("PAYMENT-100", 4, 100, Operation.DEPOSIT);

        TransactionPolicy policy =
            new OptimisticPolicy(repository);

        TransactionResult first =
            repository.executeIdempotent(payment, policy);

        TransactionResult second =
            repository.executeIdempotent(payment, policy);

        System.out.println("First: " + first.message());
        System.out.println("Duplicate: " + second.message());
        System.out.println(
            "Final balance: " + repository.read(4).balance()
        );
    }

    static void demonstrateAuditAndValidation() {
        System.out.println("\n5. Audit and validation");

        AccountRepository repository = new AccountRepository();
        repository.create(new Account(5, "Customer E", 100));

        TransactionService service = new TransactionService(repository);

        try {
            service.pessimistic(
                request("invalid-1", 5, 200, Operation.WITHDRAW)
            );
        } catch (ValidationException error) {
            System.out.println("Rejected: " + error.getMessage());
        }

        service.pessimistic(
            request("valid-1", 5, 50, Operation.DEPOSIT)
        );

        for (AuditEvent event : repository.auditReport()) {
            System.out.println(
                event.transactionId() + ": " +
                event.previousBalance() + " -> " +
                event.currentBalance() +
                ", version " + event.previousVersion() +
                " -> " + event.currentVersion()
            );
        }
    }

    public static void main(String[] args) {
        try {
            demonstrateLostUpdate();
            demonstrateOptimisticLocking();
            demonstratePessimisticLocking();
            demonstrateIdempotency();
            demonstrateAuditAndValidation();

            System.out.println("\nEnterprise concurrency tests completed.");

        } catch (Exception error) {
            System.err.println("Execution failed: " + error.getMessage());
            System.exit(1);
        }
    }
}
