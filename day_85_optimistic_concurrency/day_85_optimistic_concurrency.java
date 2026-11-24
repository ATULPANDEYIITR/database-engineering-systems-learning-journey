import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.UnaryOperator;

// ---------------------------------------------------------
// Optimistic Concurrency Control
// Java 17 Enterprise Implementation
// ---------------------------------------------------------

public class OptimisticConcurrency {

    // -----------------------------------------------------
    // Domain exceptions
    // -----------------------------------------------------

    static class ConcurrencyException extends RuntimeException {
        ConcurrencyException(String message) {
            super(message);
        }
    }

    static class VersionConflictException extends ConcurrencyException {

        final String recordId;
        final long expectedVersion;
        final long actualVersion;

        VersionConflictException(
            String recordId,
            long expectedVersion,
            long actualVersion
        ) {
            super(
                "Version conflict for " + recordId +
                ": expected " + expectedVersion +
                ", actual " + actualVersion
            );

            this.recordId = recordId;
            this.expectedVersion = expectedVersion;
            this.actualVersion = actualVersion;
        }
    }

    static class ValidationException extends RuntimeException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class RecordNotFoundException extends RuntimeException {
        RecordNotFoundException(String id) {
            super("Record not found: " + id);
        }
    }

    // -----------------------------------------------------
    // Domain types
    // -----------------------------------------------------

    enum TransactionStatus {
        PENDING,
        COMMITTED,
        CONFLICTED,
        ABORTED
    }

    enum ReviewOperation {
        UPDATE,
        TRANSFER_DEBIT,
        TRANSFER_CREDIT
    }

    record Account(
        String id,
        double balance
    ) {

        Account {
            if (id == null || id.isBlank()) {
                throw new ValidationException("Account ID is required.");
            }

            if (!Double.isFinite(balance) || balance < 0) {
                throw new ValidationException("Invalid account balance.");
            }
        }
    }

    record Snapshot(
        String id,
        Account account,
        long version,
        Instant updatedAt
    ) {}

    record AuditEntry(
        String transactionId,
        String recordId,
        long oldVersion,
        long newVersion,
        ReviewOperation operation,
        Instant timestamp
    ) {}

    record TransactionResult(
        String transactionId,
        TransactionStatus status,
        int attempts,
        Snapshot snapshot
    ) {}

    record RetryPolicy(
        int maxAttempts,
        long initialDelayMillis,
        long maxDelayMillis
    ) {

        RetryPolicy {
            if (
                maxAttempts < 1 ||
                initialDelayMillis < 0 ||
                maxDelayMillis < initialDelayMillis
            ) {
                throw new ValidationException("Invalid retry policy.");
            }
        }

        long delay(int attempt) {

            double exponential = initialDelayMillis *
                Math.pow(2, attempt);

            return Math.min(
                (long) exponential,
                maxDelayMillis
            );
        }
    }

    // -----------------------------------------------------
    // Versioned aggregate
    // -----------------------------------------------------

    static final class VersionedAccount {

        private Account account;
        private long version;
        private Instant updatedAt;

        VersionedAccount(Account account) {
            this.account = account;
            this.version = 1;
            this.updatedAt = Instant.now();
        }

        Snapshot snapshot() {
            return new Snapshot(
                account.id(),
                account,
                version,
                updatedAt
            );
        }
    }

    // -----------------------------------------------------
    // Repository interface
    // -----------------------------------------------------

    interface AccountRepository {

        Snapshot create(Account account);

        Snapshot read(String id);

        Snapshot compareAndSet(
            String id,
            long expectedVersion,
            Account replacement,
            String transactionId
        );

        List<AuditEntry> audit();
    }

    // -----------------------------------------------------
    // Repository implementation
    // -----------------------------------------------------

    static final class InMemoryAccountRepository
        implements AccountRepository {

        private final Map<String, VersionedAccount> accounts =
            new ConcurrentHashMap<>();

        private final List<AuditEntry> audit =
            Collections.synchronizedList(new ArrayList<>());

        @Override
        public Snapshot create(Account account) {

            Objects.requireNonNull(account);

            VersionedAccount stored =
                new VersionedAccount(account);

            VersionedAccount previous = accounts.putIfAbsent(
                account.id(),
                stored
            );

            if (previous != null) {
                throw new ValidationException("Duplicate account.");
            }

            return stored.snapshot();
        }

        @Override
        public Snapshot read(String id) {

            VersionedAccount stored = accounts.get(id);

            if (stored == null) {
                throw new RecordNotFoundException(id);
            }

            synchronized (stored) {
                return stored.snapshot();
            }
        }

        @Override
        public Snapshot compareAndSet(
            String id,
            long expectedVersion,
            Account replacement,
            String transactionId
        ) {

            VersionedAccount stored = accounts.get(id);

            if (stored == null) {
                throw new RecordNotFoundException(id);
            }

            if (!id.equals(replacement.id())) {
                throw new ValidationException(
                    "Replacement account ID cannot change."
                );
            }

            synchronized (stored) {

                if (stored.version != expectedVersion) {
                    throw new VersionConflictException(
                        id,
                        expectedVersion,
                        stored.version
                    );
                }

                long oldVersion = stored.version;

                stored.account = replacement;
                stored.version++;
                stored.updatedAt = Instant.now();

                audit.add(
                    new AuditEntry(
                        transactionId,
                        id,
                        oldVersion,
                        stored.version,
                        ReviewOperation.UPDATE,
                        stored.updatedAt
                    )
                );

                return stored.snapshot();
            }
        }

        /*
         * Multi-account transaction lock ordering prevents
         * deadlocks when several transfers execute concurrently.
         */
        public void transfer(
            String sourceId,
            String destinationId,
            double amount
        ) {

            if (
                sourceId.equals(destinationId) ||
                !Double.isFinite(amount) ||
                amount <= 0
            ) {
                throw new ValidationException("Invalid transfer.");
            }

            VersionedAccount source = accounts.get(sourceId);
            VersionedAccount destination = accounts.get(destinationId);

            if (source == null) {
                throw new RecordNotFoundException(sourceId);
            }

            if (destination == null) {
                throw new RecordNotFoundException(destinationId);
            }

            VersionedAccount first =
                sourceId.compareTo(destinationId) < 0
                    ? source : destination;

            VersionedAccount second =
                first == source ? destination : source;

            String transactionId = UUID.randomUUID().toString();

            synchronized (first) {
                synchronized (second) {

                    if (source.account.balance() < amount) {
                        throw new ValidationException("Insufficient funds.");
                    }

                    Account newSource = new Account(
                        sourceId,
                        source.account.balance() - amount
                    );

                    Account newDestination = new Account(
                        destinationId,
                        destination.account.balance() + amount
                    );

                    long sourceOldVersion = source.version;
                    long destinationOldVersion = destination.version;

                    // Both calculations finish before either mutation.
                    source.account = newSource;
                    destination.account = newDestination;

                    source.version++;
                    destination.version++;

                    Instant now = Instant.now();

                    source.updatedAt = now;
                    destination.updatedAt = now;

                    audit.add(
                        new AuditEntry(
                            transactionId,
                            sourceId,
                            sourceOldVersion,
                            source.version,
                            ReviewOperation.TRANSFER_DEBIT,
                            now
                        )
                    );

                    audit.add(
                        new AuditEntry(
                            transactionId,
                            destinationId,
                            destinationOldVersion,
                            destination.version,
                            ReviewOperation.TRANSFER_CREDIT,
                            now
                        )
                    );
                }
            }
        }

        @Override
        public List<AuditEntry> audit() {
            synchronized (audit) {
                return List.copyOf(audit);
            }
        }
    }

    // -----------------------------------------------------
    // Transaction service
    // -----------------------------------------------------

    static final class TransactionService {

        private final AccountRepository repository;

        TransactionService(AccountRepository repository) {
            this.repository = repository;
        }

        TransactionResult execute(
            String accountId,
            UnaryOperator<Account> businessOperation,
            RetryPolicy policy
        ) {

            String transactionId = UUID.randomUUID().toString();

            for (int attempt = 1; attempt <= policy.maxAttempts(); attempt++) {

                Snapshot snapshot = repository.read(accountId);

                // Business processing happens outside the update lock.
                Account proposed = businessOperation.apply(
                    snapshot.account()
                );

                try {

                    Snapshot committed = repository.compareAndSet(
                        accountId,
                        snapshot.version(),
                        proposed,
                        transactionId
                    );

                    return new TransactionResult(
                        transactionId,
                        TransactionStatus.COMMITTED,
                        attempt,
                        committed
                    );

                } catch (VersionConflictException exception) {

                    if (attempt == policy.maxAttempts()) {
                        return new TransactionResult(
                            transactionId,
                            TransactionStatus.ABORTED,
                            attempt,
                            repository.read(accountId)
                        );
                    }

                    try {
                        Thread.sleep(policy.delay(attempt - 1));
                    } catch (InterruptedException interrupted) {
                        Thread.currentThread().interrupt();

                        throw new ConcurrencyException(
                            "Transaction interrupted."
                        );
                    }
                }
            }

            throw new ConcurrencyException("Unexpected transaction failure.");
        }
    }

    // -----------------------------------------------------
    // Inventory service
    // -----------------------------------------------------

    static final class InventoryService {

        private final TransactionService transactions;

        InventoryService(TransactionService transactions) {
            this.transactions = transactions;
        }

        TransactionResult reserve(
            String productId,
            double quantity
        ) {

            if (!Double.isFinite(quantity) || quantity <= 0) {
                throw new ValidationException("Invalid reservation quantity.");
            }

            return transactions.execute(
                productId,
                account -> {

                    if (account.balance() < quantity) {
                        throw new ValidationException(
                            "Insufficient inventory."
                        );
                    }

                    return new Account(
                        account.id(),
                        account.balance() - quantity
                    );
                },
                new RetryPolicy(20, 1, 100)
            );
        }
    }

    // -----------------------------------------------------
    // Enterprise demonstration
    // -----------------------------------------------------

    private static void demonstrateConflict(
        AccountRepository repository
    ) {

        System.out.println("\n1. Version conflict");

        Snapshot readerA = repository.read("ACC-100");
        Snapshot readerB = repository.read("ACC-100");

        repository.compareAndSet(
            "ACC-100",
            readerA.version(),
            new Account("ACC-100", 4500),
            "TX-A"
        );

        try {

            repository.compareAndSet(
                "ACC-100",
                readerB.version(),
                new Account("ACC-100", 3000),
                "TX-B"
            );

        } catch (VersionConflictException error) {
            System.out.println(error.getMessage());
        }
    }

    private static void demonstrateParallelUpdates(
        TransactionService transactions,
        AccountRepository repository
    ) {

        System.out.println("\n2. Parallel transactions");

        repository.create(new Account("COUNTER", 0));

        List<CompletableFuture<TransactionResult>> tasks =
            new ArrayList<>();

        for (int i = 0; i < 20; i++) {

            tasks.add(
                CompletableFuture.supplyAsync(() ->
                    transactions.execute(
                        "COUNTER",
                        account -> new Account(
                            account.id(),
                            account.balance() + 1
                        ),
                        new RetryPolicy(100, 1, 50)
                    )
                )
            );
        }

        CompletableFuture.allOf(
            tasks.toArray(CompletableFuture[]::new)
        ).join();

        Snapshot result = repository.read("COUNTER");

        System.out.println("Counter: " + result.account().balance());
        System.out.println("Version: " + result.version());

        if (result.account().balance() != 20) {
            throw new IllegalStateException("Lost update detected.");
        }
    }

    private static void demonstrateTransfer(
        InMemoryAccountRepository repository
    ) {

        System.out.println("\n3. Atomic account transfer");

        repository.create(new Account("ACC-200", 1000));

        repository.transfer("ACC-100", "ACC-200", 500);

        System.out.println(repository.read("ACC-100"));
        System.out.println(repository.read("ACC-200"));
    }

    private static void demonstrateInventory(
        TransactionService transactions,
        AccountRepository repository
    ) {

        System.out.println("\n4. Inventory reservation");

        repository.create(new Account("PRODUCT-1", 1000));

        InventoryService inventory = new InventoryService(transactions);

        List<CompletableFuture<TransactionResult>> tasks =
            new ArrayList<>();

        for (int i = 0; i < 5; i++) {
            tasks.add(
                CompletableFuture.supplyAsync(
                    () -> inventory.reserve("PRODUCT-1", 10)
                )
            );
        }

        CompletableFuture.allOf(
            tasks.toArray(CompletableFuture[]::new)
        ).join();

        System.out.println(repository.read("PRODUCT-1"));
    }

    private static void demonstrateAudit(
        AccountRepository repository
    ) {

        System.out.println("\n5. Audit history");

        for (AuditEntry entry : repository.audit()) {
            System.out.println(entry);
        }
    }

    public static void main(String[] args) {

        InMemoryAccountRepository repository =
            new InMemoryAccountRepository();

        repository.create(new Account("ACC-100", 5000));

        TransactionService transactions =
            new TransactionService(repository);

        try {

            demonstrateConflict(repository);

            demonstrateParallelUpdates(
                transactions,
                repository
            );

            demonstrateTransfer(repository);

            demonstrateInventory(
                transactions,
                repository
            );

            demonstrateAudit(repository);

            System.out.println("\nAll enterprise checks completed.");

        } catch (RuntimeException error) {

            System.err.println(
                "Execution failed: " + error.getMessage()
            );

            System.exit(1);
        }
    }
}
