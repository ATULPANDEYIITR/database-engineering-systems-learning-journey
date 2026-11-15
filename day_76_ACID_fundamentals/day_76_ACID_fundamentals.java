import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.locks.ReentrantLock;

/*
 * ACID Fundamentals: Enterprise Transaction Management
 *
 * Java 17 implementation covering:
 * - Atomicity through staged state and commit.
 * - Consistency through domain invariants.
 * - Isolation through optimistic version validation.
 * - Durability through atomic persistent snapshots.
 * - Explicit transaction lifecycle.
 * - Idempotency and audit records.
 * - Business policy enforcement.
 *
 * No third-party dependencies.
 */

public class AcidFundamentals {

    enum TransactionState {
        ACTIVE,
        COMMITTED,
        ROLLED_BACK,
        CONFLICT
    }

    enum IsolationLevel {
        READ_COMMITTED,
        REPEATABLE_READ,
        SERIALIZABLE
    }

    record Account(
        long id,
        String owner,
        long balanceCents,
        long version
    ) {
        Account {
            if (id <= 0) {
                throw new IllegalArgumentException(
                    "Account ID must be positive."
                );
            }

            if (owner == null || owner.isBlank()) {
                throw new IllegalArgumentException(
                    "Account owner is required."
                );
            }

            if (balanceCents < 0 || version < 0) {
                throw new IllegalArgumentException(
                    "Balance and version cannot be negative."
                );
            }
        }

        Account debit(long amount) {
            if (amount <= 0 || amount > balanceCents) {
                throw new InsufficientFundsException(
                    "Invalid debit or insufficient funds."
                );
            }

            return new Account(
                id,
                owner,
                balanceCents - amount,
                version
            );
        }

        Account credit(long amount) {
            if (amount <= 0 ||
                balanceCents > Long.MAX_VALUE - amount) {
                throw new IllegalArgumentException(
                    "Invalid credit amount."
                );
            }

            return new Account(
                id,
                owner,
                balanceCents + amount,
                version
            );
        }

        Account withVersion(long newVersion) {
            return new Account(
                id,
                owner,
                balanceCents,
                newVersion
            );
        }
    }

    record Transfer(
        long sourceId,
        long destinationId,
        long amountCents
    ) {
        Transfer {
            if (sourceId == destinationId) {
                throw new IllegalArgumentException(
                    "Accounts must differ."
                );
            }

            if (amountCents <= 0) {
                throw new IllegalArgumentException(
                    "Transfer amount must be positive."
                );
            }
        }
    }

    record AuditEntry(
        String transactionId,
        String operation,
        Instant timestamp,
        String description
    ) {}

    record CommitResult(
        String transactionId,
        long commitVersion,
        int operationCount
    ) {}

    static class TransactionException extends RuntimeException {
        TransactionException(String message) {
            super(message);
        }
    }

    static class InsufficientFundsException
        extends TransactionException {

        InsufficientFundsException(String message) {
            super(message);
        }
    }

    static class SerializationConflictException
        extends TransactionException {

        SerializationConflictException(String message) {
            super(message);
        }
    }

    static class DuplicateTransactionException
        extends TransactionException {

        DuplicateTransactionException(String message) {
            super(message);
        }
    }

    interface DurabilityProvider {
        void persist(
            Map<Long, Account> accounts,
            List<AuditEntry> audit,
            long commitVersion
        ) throws IOException;
    }

    static class FileDurabilityProvider
        implements DurabilityProvider {

        private final Path destination;

        FileDurabilityProvider(Path destination) {
            this.destination = destination.toAbsolutePath();
        }

        @Override
        public void persist(
            Map<Long, Account> accounts,
            List<AuditEntry> audit,
            long commitVersion
        ) throws IOException {

            Path directory = destination.getParent();

            if (directory != null) {
                Files.createDirectories(directory);
            }

            Path temporary = Files.createTempFile(
                directory,
                "acid-",
                ".tmp"
            );

            try {
                try (BufferedWriter writer = Files.newBufferedWriter(
                    temporary,
                    StandardCharsets.UTF_8,
                    StandardOpenOption.TRUNCATE_EXISTING
                )) {
                    writer.write("COMMIT_VERSION|" + commitVersion);
                    writer.newLine();

                    for (Account account : accounts.values()) {
                        writer.write(
                            "ACCOUNT|" +
                            account.id() + "|" +
                            account.owner().replace("|", "") + "|" +
                            account.balanceCents() + "|" +
                            account.version()
                        );
                        writer.newLine();
                    }

                    for (AuditEntry entry : audit) {
                        writer.write(
                            "AUDIT|" +
                            entry.transactionId() + "|" +
                            entry.operation() + "|" +
                            entry.timestamp() + "|" +
                            entry.description().replace("|", "")
                        );
                        writer.newLine();
                    }
                }

                try {
                    Files.move(
                        temporary,
                        destination,
                        StandardCopyOption.ATOMIC_MOVE,
                        StandardCopyOption.REPLACE_EXISTING
                    );
                } catch (java.nio.file.AtomicMoveNotSupportedException e) {
                    Files.move(
                        temporary,
                        destination,
                        StandardCopyOption.REPLACE_EXISTING
                    );
                }

            } finally {
                Files.deleteIfExists(temporary);
            }
        }
    }

    static class Transaction {

        private final String id;
        private final TransactionManager manager;
        private final IsolationLevel isolationLevel;

        private final Map<Long, Account> snapshot;
        private final Map<Long, Long> originalVersions =
            new HashMap<>();

        private final Map<Long, Account> staged =
            new HashMap<>();

        private final List<Transfer> operations =
            new ArrayList<>();

        private TransactionState state =
            TransactionState.ACTIVE;

        Transaction(
            String id,
            TransactionManager manager,
            IsolationLevel isolationLevel,
            Map<Long, Account> snapshot
        ) {
            this.id = id;
            this.manager = manager;
            this.isolationLevel = isolationLevel;
            this.snapshot = Map.copyOf(snapshot);
        }

        String id() {
            return id;
        }

        TransactionState state() {
            return state;
        }

        IsolationLevel isolationLevel() {
            return isolationLevel;
        }

        void ensureActive() {
            if (state != TransactionState.ACTIVE) {
                throw new TransactionException(
                    "Transaction is " + state
                );
            }
        }

        Account read(long accountId) {
            ensureActive();

            if (staged.containsKey(accountId)) {
                return staged.get(accountId);
            }

            Account account = snapshot.get(accountId);

            if (account == null) {
                throw new TransactionException(
                    "Account does not exist: " + accountId
                );
            }

            return account;
        }

        void write(Account account) {
            ensureActive();

            Account original = snapshot.get(account.id());

            if (original == null) {
                throw new TransactionException(
                    "Cannot modify unknown account."
                );
            }

            originalVersions.putIfAbsent(
                account.id(),
                original.version()
            );

            staged.put(account.id(), account);
        }

        void transfer(
            long sourceId,
            long destinationId,
            long amount
        ) {
            ensureActive();

            Transfer transfer = new Transfer(
                sourceId,
                destinationId,
                amount
            );

            Account source = read(sourceId);
            Account destination = read(destinationId);

            write(source.debit(amount));
            write(destination.credit(amount));

            operations.add(transfer);
        }

        void rollback() {
            ensureActive();
            staged.clear();
            operations.clear();
            state = TransactionState.ROLLED_BACK;
        }
    }

    static class TransactionManager {

        private final Map<Long, Account> accounts =
            new HashMap<>();

        private final List<AuditEntry> audit =
            new ArrayList<>();

        private final Set<String> idempotencyKeys =
            new HashSet<>();

        private final ReentrantLock commitLock =
            new ReentrantLock(true);

        private final DurabilityProvider durabilityProvider;

        private long accountSequence = 0;
        private long commitVersion = 0;

        TransactionManager(DurabilityProvider provider) {
            this.durabilityProvider =
                Objects.requireNonNull(provider);
        }

        synchronized long createAccount(
            String owner,
            long initialBalance
        ) {
            Account account = new Account(
                ++accountSequence,
                owner,
                initialBalance,
                0
            );

            accounts.put(account.id(), account);
            return account.id();
        }

        synchronized Transaction begin(
            IsolationLevel isolationLevel
        ) {
            return new Transaction(
                UUID.randomUUID().toString(),
                this,
                isolationLevel,
                new HashMap<>(accounts)
            );
        }

        CommitResult commit(
            Transaction transaction,
            String idempotencyKey
        ) {
            transaction.ensureActive();

            commitLock.lock();

            try {
                if (idempotencyKey != null &&
                    !idempotencyKey.isBlank() &&
                    idempotencyKeys.contains(idempotencyKey)) {

                    throw new DuplicateTransactionException(
                        "Idempotency key already used."
                    );
                }

                // Optimistic validation: reject stale write sets.
                for (Map.Entry<Long, Long> entry :
                    transaction.originalVersions.entrySet()) {

                    Account current = accounts.get(entry.getKey());

                    if (current == null ||
                        current.version() != entry.getValue()) {

                        transaction.state =
                            TransactionState.CONFLICT;

                        throw new SerializationConflictException(
                            "Concurrent modification detected."
                        );
                    }
                }

                Map<Long, Account> candidate =
                    new HashMap<>(accounts);

                for (Map.Entry<Long, Account> entry :
                    transaction.staged.entrySet()) {

                    Account previous = candidate.get(entry.getKey());

                    Account updated = entry.getValue()
                        .withVersion(previous.version() + 1);

                    candidate.put(entry.getKey(), updated);
                }

                validateGlobalInvariants(candidate);

                List<AuditEntry> candidateAudit =
                    new ArrayList<>(audit);

                candidateAudit.add(new AuditEntry(
                    transaction.id,
                    "COMMIT",
                    Instant.now(),
                    "Operations: " + transaction.operations.size()
                ));

                long nextCommitVersion = commitVersion + 1;

                // Durable persistence must succeed before publishing
                // the candidate committed state.
                durabilityProvider.persist(
                    candidate,
                    candidateAudit,
                    nextCommitVersion
                );

                accounts.clear();
                accounts.putAll(candidate);

                audit.clear();
                audit.addAll(candidateAudit);

                if (idempotencyKey != null &&
                    !idempotencyKey.isBlank()) {
                    idempotencyKeys.add(idempotencyKey);
                }

                commitVersion = nextCommitVersion;
                transaction.state = TransactionState.COMMITTED;

                return new CommitResult(
                    transaction.id,
                    commitVersion,
                    transaction.operations.size()
                );

            } catch (IOException error) {
                throw new TransactionException(
                    "Durability failure: " + error.getMessage()
                );

            } finally {
                commitLock.unlock();
            }
        }

        private void validateGlobalInvariants(
            Map<Long, Account> candidate
        ) {
            for (Account account : candidate.values()) {
                if (account.balanceCents() < 0) {
                    throw new TransactionException(
                        "Negative account balance detected."
                    );
                }
            }
        }

        synchronized Account getAccount(long id) {
            Account account = accounts.get(id);

            if (account == null) {
                throw new TransactionException(
                    "Account does not exist."
                );
            }

            return account;
        }

        synchronized long totalBalance() {
            long total = 0;

            for (Account account : accounts.values()) {
                total = Math.addExact(
                    total,
                    account.balanceCents()
                );
            }

            return total;
        }

        synchronized void printAccounts() {
            accounts.values().stream()
                .sorted((a, b) -> Long.compare(a.id(), b.id()))
                .forEach(System.out::println);
        }

        synchronized long getCommitVersion() {
            return commitVersion;
        }
    }

    public static void main(String[] args) throws Exception {

        Path databaseFile = Path.of("acid_enterprise.dat");

        Files.deleteIfExists(databaseFile);

        DurabilityProvider provider =
            new FileDurabilityProvider(databaseFile);

        TransactionManager manager =
            new TransactionManager(provider);

        long treasury = manager.createAccount(
            "Corporate Treasury",
            1_000_000
        );

        long research = manager.createAccount(
            "Research Department",
            250_000
        );

        long initialTotal = manager.totalBalance();

        System.out.println("INITIAL ACCOUNTS");
        manager.printAccounts();

        System.out.println("\nATOMICITY");

        Transaction failed = manager.begin(
            IsolationLevel.SERIALIZABLE
        );

        failed.transfer(treasury, research, 100_000);
        failed.rollback();

        if (manager.totalBalance() != initialTotal) {
            throw new IllegalStateException(
                "Atomicity invariant failed."
            );
        }

        System.out.println("Rollback preserved account balances.");

        System.out.println("\nCONSISTENCY");

        Transaction invalid = manager.begin(
            IsolationLevel.SERIALIZABLE
        );

        try {
            invalid.transfer(
                treasury,
                research,
                99_999_999
            );
        } catch (InsufficientFundsException error) {
            System.out.println("Rejected: " + error.getMessage());
            invalid.rollback();
        }

        System.out.println("\nISOLATION");

        Transaction first = manager.begin(
            IsolationLevel.SERIALIZABLE
        );

        Transaction second = manager.begin(
            IsolationLevel.SERIALIZABLE
        );

        first.transfer(treasury, research, 50_000);
        second.transfer(treasury, research, 70_000);

        System.out.println(
            manager.commit(first, "CORP-TRANSFER-001")
        );

        try {
            manager.commit(second, "CORP-TRANSFER-002");
        } catch (SerializationConflictException error) {
            System.out.println(
                "Serialization conflict: " + error.getMessage()
            );
        }

        System.out.println("\nDURABILITY");

        System.out.println(
            "Persistent database: " +
            databaseFile.toAbsolutePath()
        );

        System.out.println(
            "Commit version: " + manager.getCommitVersion()
        );

        System.out.println("\nFINAL ACCOUNTS");
        manager.printAccounts();

        if (manager.totalBalance() != initialTotal) {
            throw new IllegalStateException(
                "Consistency invariant failed."
            );
        }

        System.out.println(
            "\nTotal preserved: " + manager.totalBalance()
        );

        System.out.println("\nACID execution completed.");
    }
}
