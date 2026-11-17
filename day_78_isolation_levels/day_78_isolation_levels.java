import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;

/*
 * Enterprise Database Transaction Isolation Model
 *
 * Java 17 implementation featuring:
 * - Explicit transaction domain types
 * - Isolation policies
 * - Versioned account records
 * - Transaction snapshots
 * - Optimistic concurrency control
 * - Serializable validation
 * - Atomic transfer services
 * - Audit events
 * - Custom exceptions
 */

public class TransactionIsolationEnterprise {

    enum IsolationLevel {
        READ_UNCOMMITTED,
        READ_COMMITTED,
        REPEATABLE_READ,
        SERIALIZABLE
    }

    enum TransactionStatus {
        ACTIVE,
        COMMITTED,
        ROLLED_BACK,
        ABORTED
    }

    record Account(
        String accountId,
        BigDecimal balance,
        long version
    ) {
        Account {
            Objects.requireNonNull(accountId);
            Objects.requireNonNull(balance);

            if (accountId.isBlank()) {
                throw new IllegalArgumentException(
                    "Account ID cannot be blank"
                );
            }

            if (balance.signum() < 0) {
                throw new IllegalArgumentException(
                    "Account balance cannot be negative"
                );
            }

            if (version < 0) {
                throw new IllegalArgumentException(
                    "Version cannot be negative"
                );
            }
        }

        Account withBalance(BigDecimal newBalance, long newVersion) {
            return new Account(
                accountId,
                newBalance,
                newVersion
            );
        }
    }

    record AuditEvent(
        String transactionId,
        String event,
        Instant timestamp,
        IsolationLevel isolationLevel
    ) {}

    record TransactionResult(
        String transactionId,
        TransactionStatus status,
        Map<String, BigDecimal> resultingBalances
    ) {}

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

    static class SerializationException extends TransactionException {
        SerializationException(String message) {
            super(message);
        }
    }

    static class InsufficientFundsException extends TransactionException {
        InsufficientFundsException(String message) {
            super(message);
        }
    }

    static final class Transaction {

        private final String id;
        private final IsolationLevel isolationLevel;
        private final Instant startedAt;

        private final Map<String, Account> snapshot;
        private final Map<String, BigDecimal> writes =
            new LinkedHashMap<>();

        private final Map<String, Long> readVersions =
            new HashMap<>();

        private final Map<String, Long> writeVersions =
            new HashMap<>();

        private TransactionStatus status = TransactionStatus.ACTIVE;

        Transaction(
            IsolationLevel isolationLevel,
            Map<String, Account> snapshot
        ) {
            this.id = UUID.randomUUID().toString();
            this.isolationLevel = isolationLevel;
            this.snapshot = Map.copyOf(snapshot);
            this.startedAt = Instant.now();
        }

        void ensureActive() {
            if (status != TransactionStatus.ACTIVE) {
                throw new TransactionException(
                    "Transaction is not active: " + status
                );
            }
        }

        String id() {
            return id;
        }

        IsolationLevel isolationLevel() {
            return isolationLevel;
        }

        TransactionStatus status() {
            return status;
        }

        Instant startedAt() {
            return startedAt;
        }
    }

    static final class AccountRepository {

        private final Map<String, Account> accounts =
            new LinkedHashMap<>();

        private final AtomicLong versionSequence =
            new AtomicLong(1);

        synchronized void addAccount(
            String accountId,
            BigDecimal openingBalance
        ) {
            if (accounts.containsKey(accountId)) {
                throw new TransactionException(
                    "Duplicate account: " + accountId
                );
            }

            accounts.put(
                accountId,
                new Account(
                    accountId,
                    openingBalance,
                    versionSequence.getAndIncrement()
                )
            );
        }

        synchronized Map<String, Account> snapshot() {
            return Collections.unmodifiableMap(
                new LinkedHashMap<>(accounts)
            );
        }

        synchronized Account find(String accountId) {
            Account account = accounts.get(accountId);

            if (account == null) {
                throw new TransactionException(
                    "Account not found: " + accountId
                );
            }

            return account;
        }

        synchronized void apply(
            Map<String, BigDecimal> writes
        ) {
            for (Map.Entry<String, BigDecimal> entry :
                 writes.entrySet()) {

                Account current = find(entry.getKey());

                accounts.put(
                    entry.getKey(),
                    current.withBalance(
                        entry.getValue(),
                        versionSequence.getAndIncrement()
                    )
                );
            }
        }

        synchronized Map<String, BigDecimal> balances() {
            Map<String, BigDecimal> result =
                new LinkedHashMap<>();

            accounts.forEach(
                (id, account) ->
                    result.put(id, account.balance())
            );

            return Map.copyOf(result);
        }
    }

    interface IsolationPolicy {
        Map<String, Account> readView(
            Transaction transaction,
            AccountRepository repository
        );
    }

    static final class IsolationPolicyRegistry {

        private final Map<IsolationLevel, IsolationPolicy> policies =
            new EnumMap<>(IsolationLevel.class);

        IsolationPolicyRegistry() {

            // PostgreSQL maps READ UNCOMMITTED to READ COMMITTED.
            policies.put(
                IsolationLevel.READ_UNCOMMITTED,
                (transaction, repository) -> repository.snapshot()
            );

            policies.put(
                IsolationLevel.READ_COMMITTED,
                (transaction, repository) -> repository.snapshot()
            );

            policies.put(
                IsolationLevel.REPEATABLE_READ,
                (transaction, repository) -> transaction.snapshot
            );

            policies.put(
                IsolationLevel.SERIALIZABLE,
                (transaction, repository) -> transaction.snapshot
            );
        }

        Map<String, Account> readView(
            Transaction transaction,
            AccountRepository repository
        ) {
            return policies.get(transaction.isolationLevel())
                .readView(transaction, repository);
        }
    }

    static final class AuditService {

        private final List<AuditEvent> events =
            Collections.synchronizedList(new ArrayList<>());

        void record(Transaction transaction, String event) {
            events.add(
                new AuditEvent(
                    transaction.id(),
                    event,
                    Instant.now(),
                    transaction.isolationLevel()
                )
            );
        }

        List<AuditEvent> getEvents() {
            synchronized (events) {
                return List.copyOf(events);
            }
        }
    }

    static final class TransactionManager {

        private final AccountRepository repository;
        private final IsolationPolicyRegistry policyRegistry;
        private final AuditService auditService;

        TransactionManager(
            AccountRepository repository,
            IsolationPolicyRegistry policyRegistry,
            AuditService auditService
        ) {
            this.repository = repository;
            this.policyRegistry = policyRegistry;
            this.auditService = auditService;
        }

        Transaction begin(IsolationLevel isolationLevel) {
            Transaction transaction = new Transaction(
                isolationLevel,
                repository.snapshot()
            );

            auditService.record(transaction, "BEGIN");

            return transaction;
        }

        BigDecimal read(
            Transaction transaction,
            String accountId
        ) {
            transaction.ensureActive();

            if (transaction.writes.containsKey(accountId)) {
                return transaction.writes.get(accountId);
            }

            Map<String, Account> view =
                policyRegistry.readView(transaction, repository);

            Account account = view.get(accountId);

            if (account == null) {
                throw new TransactionException(
                    "Account does not exist: " + accountId
                );
            }

            transaction.readVersions.putIfAbsent(
                accountId,
                account.version()
            );

            return account.balance();
        }

        void write(
            Transaction transaction,
            String accountId,
            BigDecimal newBalance
        ) {
            transaction.ensureActive();

            Objects.requireNonNull(newBalance);

            if (newBalance.signum() < 0) {
                throw new IllegalArgumentException(
                    "Negative balances are prohibited"
                );
            }

            Account current = repository.find(accountId);

            transaction.writeVersions.putIfAbsent(
                accountId,
                current.version()
            );

            transaction.writes.put(accountId, newBalance);

            auditService.record(
                transaction,
                "WRITE:" + accountId
            );
        }

        private void validate(Transaction transaction) {

            Map<String, Account> currentSnapshot =
                repository.snapshot();

            for (Map.Entry<String, Long> entry :
                 transaction.writeVersions.entrySet()) {

                Account current = currentSnapshot.get(entry.getKey());

                if (
                    current == null ||
                    current.version() != entry.getValue()
                ) {
                    throw new WriteConflictException(
                        "Concurrent write conflict: " + entry.getKey()
                    );
                }
            }

            if (
                transaction.isolationLevel() ==
                IsolationLevel.SERIALIZABLE
            ) {
                for (Map.Entry<String, Long> entry :
                     transaction.readVersions.entrySet()) {

                    if (transaction.writes.containsKey(entry.getKey())) {
                        continue;
                    }

                    Account current = currentSnapshot.get(entry.getKey());

                    if (
                        current == null ||
                        current.version() != entry.getValue()
                    ) {
                        throw new SerializationException(
                            "Read dependency changed: " + entry.getKey()
                        );
                    }
                }
            }
        }

        synchronized TransactionResult commit(
            Transaction transaction
        ) {
            transaction.ensureActive();

            try {
                validate(transaction);

                // The repository update is synchronized, making
                // validation and publication atomic in this model.
                repository.apply(transaction.writes);

                transaction.status = TransactionStatus.COMMITTED;

                auditService.record(transaction, "COMMIT");

                return new TransactionResult(
                    transaction.id(),
                    transaction.status(),
                    repository.balances()
                );

            } catch (TransactionException exception) {
                transaction.writes.clear();
                transaction.status = TransactionStatus.ABORTED;

                auditService.record(transaction, "ABORT");

                throw exception;
            }
        }

        void rollback(Transaction transaction) {
            transaction.ensureActive();

            transaction.writes.clear();
            transaction.status = TransactionStatus.ROLLED_BACK;

            auditService.record(transaction, "ROLLBACK");
        }
    }

    static final class TransferService {

        private final TransactionManager transactionManager;

        TransferService(TransactionManager transactionManager) {
            this.transactionManager = transactionManager;
        }

        TransactionResult transfer(
            String source,
            String destination,
            BigDecimal amount
        ) {
            Objects.requireNonNull(amount);

            if (amount.signum() <= 0) {
                throw new IllegalArgumentException(
                    "Transfer amount must be positive"
                );
            }

            Transaction transaction =
                transactionManager.begin(IsolationLevel.SERIALIZABLE);

            try {
                BigDecimal sourceBalance =
                    transactionManager.read(transaction, source);

                BigDecimal destinationBalance =
                    transactionManager.read(transaction, destination);

                if (sourceBalance.compareTo(amount) < 0) {
                    throw new InsufficientFundsException(
                        "Insufficient source account balance"
                    );
                }

                transactionManager.write(
                    transaction,
                    source,
                    sourceBalance.subtract(amount)
                );

                transactionManager.write(
                    transaction,
                    destination,
                    destinationBalance.add(amount)
                );

                return transactionManager.commit(transaction);

            } catch (RuntimeException exception) {
                if (transaction.status() == TransactionStatus.ACTIVE) {
                    transactionManager.rollback(transaction);
                }

                throw exception;
            }
        }
    }

    static void demonstrateReadCommitted(
        TransactionManager manager
    ) {
        System.out.println("\n1. READ COMMITTED");

        Transaction reader =
            manager.begin(IsolationLevel.READ_COMMITTED);

        Transaction writer =
            manager.begin(IsolationLevel.READ_COMMITTED);

        BigDecimal first = manager.read(reader, "inventory");

        manager.write(
            writer,
            "inventory",
            new BigDecimal("75")
        );

        manager.commit(writer);

        BigDecimal second = manager.read(reader, "inventory");

        System.out.println("First read: " + first);
        System.out.println("Second read: " + second);

        if (first.compareTo(second) == 0) {
            throw new IllegalStateException(
                "Expected non-repeatable read"
            );
        }

        manager.rollback(reader);
    }

    static void demonstrateRepeatableRead(
        TransactionManager manager
    ) {
        System.out.println("\n2. REPEATABLE READ");

        Transaction reader =
            manager.begin(IsolationLevel.REPEATABLE_READ);

        Transaction writer =
            manager.begin(IsolationLevel.READ_COMMITTED);

        BigDecimal first = manager.read(reader, "inventory");

        manager.write(
            writer,
            "inventory",
            new BigDecimal("50")
        );

        manager.commit(writer);

        BigDecimal second = manager.read(reader, "inventory");

        System.out.println("First read: " + first);
        System.out.println("Second read: " + second);

        if (first.compareTo(second) != 0) {
            throw new IllegalStateException(
                "Snapshot consistency violated"
            );
        }

        manager.commit(reader);
    }

    static void demonstrateWriteConflict(
        TransactionManager manager
    ) {
        System.out.println("\n3. CONCURRENT WRITE CONFLICT");

        Transaction first =
            manager.begin(IsolationLevel.REPEATABLE_READ);

        Transaction second =
            manager.begin(IsolationLevel.REPEATABLE_READ);

        manager.write(first, "inventory", new BigDecimal("40"));
        manager.write(second, "inventory", new BigDecimal("30"));

        manager.commit(first);

        try {
            manager.commit(second);
            throw new IllegalStateException(
                "Expected write conflict"
            );
        } catch (WriteConflictException exception) {
            System.out.println(exception.getMessage());
        }
    }

    static void demonstrateSerializableFailure(
        TransactionManager manager
    ) {
        System.out.println("\n4. SERIALIZABLE VALIDATION");

        Transaction reader =
            manager.begin(IsolationLevel.SERIALIZABLE);

        Transaction writer =
            manager.begin(IsolationLevel.READ_COMMITTED);

        BigDecimal observed =
            manager.read(reader, "inventory");

        manager.write(
            writer,
            "inventory",
            new BigDecimal("20")
        );

        manager.commit(writer);

        System.out.println("Snapshot value: " + observed);

        try {
            manager.commit(reader);
            throw new IllegalStateException(
                "Expected serialization failure"
            );
        } catch (SerializationException exception) {
            System.out.println(exception.getMessage());
        }
    }

    public static void main(String[] args) {

        AccountRepository repository = new AccountRepository();

        repository.addAccount(
            "alice",
            new BigDecimal("5000")
        );

        repository.addAccount(
            "bob",
            new BigDecimal("3000")
        );

        repository.addAccount(
            "inventory",
            new BigDecimal("100")
        );

        IsolationPolicyRegistry registry =
            new IsolationPolicyRegistry();

        AuditService audit = new AuditService();

        TransactionManager manager = new TransactionManager(
            repository,
            registry,
            audit
        );

        demonstrateReadCommitted(manager);
        demonstrateRepeatableRead(manager);
        demonstrateWriteConflict(manager);
        demonstrateSerializableFailure(manager);

        System.out.println("\n5. ENTERPRISE TRANSFER");

        TransferService transferService =
            new TransferService(manager);

        TransactionResult result = transferService.transfer(
            "alice",
            "bob",
            new BigDecimal("1000")
        );

        System.out.println("Transaction: " + result.transactionId());
        System.out.println("Status: " + result.status());
        System.out.println("Balances: " + result.resultingBalances());

        if (
            result.resultingBalances().get("alice")
                .add(result.resultingBalances().get("bob"))
                .compareTo(new BigDecimal("8000")) != 0
        ) {
            throw new IllegalStateException(
                "Account conservation violated"
            );
        }

        System.out.println("\n6. TRANSACTION AUDIT");

        audit.getEvents().stream()
            .limit(15)
            .forEach(System.out::println);

        System.out.println("\nAll enterprise demonstrations completed.");
    }
}
