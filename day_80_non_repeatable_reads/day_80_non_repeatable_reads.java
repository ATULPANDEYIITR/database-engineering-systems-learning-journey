import java.util.*;
import java.util.concurrent.atomic.AtomicLong;

/**
 * NON-REPEATABLE READS
 *
 * Enterprise transaction and concurrency management simulator.
 *
 * Java 17
 *
 * Demonstrates:
 * - Transaction snapshots.
 * - READ COMMITTED behavior.
 * - REPEATABLE READ behavior.
 * - SERIALIZABLE validation.
 * - Optimistic concurrency control.
 * - Transaction lifecycle.
 * - Approval-independent transaction validation.
 * - Atomic commit and rollback.
 */
public class NonRepeatableReads {

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
        FAILED
    }

    record Account(
        int id,
        String owner,
        long balanceInCents,
        long version
    ) {
        Account {
            if (id <= 0) {
                throw new IllegalArgumentException("Invalid account ID.");
            }

            if (owner == null || owner.isBlank()) {
                throw new IllegalArgumentException("Owner is required.");
            }

            if (balanceInCents < 0) {
                throw new IllegalArgumentException("Negative balance.");
            }

            if (version < 1) {
                throw new IllegalArgumentException("Invalid version.");
            }
        }

        Account withBalance(long amount) {
            return new Account(
                id,
                owner,
                amount,
                version
            );
        }

        Account withVersion(long newVersion) {
            return new Account(
                id,
                owner,
                balanceInCents,
                newVersion
            );
        }
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

    static class SerializationException extends TransactionException {
        SerializationException(String message) {
            super(message);
        }
    }

    static class Transaction {
        private final String id;
        private final IsolationLevel isolation;

        private final Map<Integer, Account> snapshot;
        private final Map<Integer, Account> writes = new HashMap<>();
        private final Map<Integer, Long> readVersions = new HashMap<>();

        private TransactionStatus status = TransactionStatus.ACTIVE;

        Transaction(
            String id,
            IsolationLevel isolation,
            Map<Integer, Account> databaseSnapshot
        ) {
            this.id = id;
            this.isolation = isolation;
            this.snapshot = Map.copyOf(databaseSnapshot);
        }

        String id() {
            return id;
        }

        IsolationLevel isolation() {
            return isolation;
        }

        TransactionStatus status() {
            return status;
        }

        void ensureActive() {
            if (status != TransactionStatus.ACTIVE) {
                throw new TransactionException(
                    "Transaction is not active: " + status
                );
            }
        }
    }

    static class Database {
        private final Map<Integer, Account> accounts = new HashMap<>();
        private final AtomicLong transactionSequence = new AtomicLong();

        public Database() {
            insert(new Account(1, "Operations", 100_000, 1));
            insert(new Account(2, "Engineering", 200_000, 1));
        }

        private synchronized void insert(Account account) {
            if (accounts.putIfAbsent(account.id(), account) != null) {
                throw new IllegalArgumentException("Duplicate account.");
            }
        }

        public synchronized Transaction begin(
            IsolationLevel isolation
        ) {
            String id = "TX-" + transactionSequence.incrementAndGet();

            Transaction tx = new Transaction(
                id,
                Objects.requireNonNull(isolation),
                accounts
            );

            System.out.printf(
                "[BEGIN] %s | %s%n",
                id,
                isolation
            );

            return tx;
        }

        public synchronized Account read(
            Transaction tx,
            int accountId
        ) {
            tx.ensureActive();

            Account account;

            if (tx.writes.containsKey(accountId)) {
                account = tx.writes.get(accountId);
            } else if (
                tx.isolation == IsolationLevel.READ_COMMITTED ||
                tx.isolation == IsolationLevel.READ_UNCOMMITTED
            ) {
                account = accounts.get(accountId);
            } else {
                account = tx.snapshot.get(accountId);
            }

            if (account == null) {
                throw new TransactionException("Account not found.");
            }

            tx.readVersions.putIfAbsent(
                accountId,
                account.version()
            );

            System.out.printf(
                "[READ] %s | Account %d | Balance %d | Version %d%n",
                tx.id,
                accountId,
                account.balanceInCents(),
                account.version()
            );

            return account;
        }

        public synchronized void update(
            Transaction tx,
            int accountId,
            long newBalance
        ) {
            tx.ensureActive();

            if (newBalance < 0) {
                throw new TransactionException(
                    "Balance cannot be negative."
                );
            }

            Account current = tx.writes.getOrDefault(
                accountId,
                tx.snapshot.get(accountId)
            );

            if (current == null) {
                throw new TransactionException("Unknown account.");
            }

            tx.writes.put(
                accountId,
                current.withBalance(newBalance)
            );

            System.out.printf(
                "[WRITE] %s | Account %d | New balance %d%n",
                tx.id,
                accountId,
                newBalance
            );
        }

        public synchronized void transfer(
            Transaction tx,
            int sourceId,
            int targetId,
            long amount
        ) {
            tx.ensureActive();

            if (amount <= 0 || sourceId == targetId) {
                throw new TransactionException(
                    "Invalid transfer parameters."
                );
            }

            Account source = read(tx, sourceId);
            Account target = read(tx, targetId);

            if (source.balanceInCents() < amount) {
                throw new TransactionException("Insufficient funds.");
            }

            if (Long.MAX_VALUE - target.balanceInCents() < amount) {
                throw new TransactionException("Balance overflow.");
            }

            update(
                tx,
                sourceId,
                source.balanceInCents() - amount
            );

            update(
                tx,
                targetId,
                target.balanceInCents() + amount
            );
        }

        public synchronized void commit(Transaction tx) {
            tx.ensureActive();

            // Validate the entire write set before applying changes.
            for (Map.Entry<Integer, Account> entry : tx.writes.entrySet()) {
                Account current = accounts.get(entry.getKey());

                if (
                    current == null ||
                    current.version() != entry.getValue().version()
                ) {
                    tx.status = TransactionStatus.FAILED;

                    throw new WriteConflictException(
                        "Concurrent modification: account " +
                        entry.getKey()
                    );
                }
            }

            // Serializable transactions validate all previously read rows.
            if (tx.isolation == IsolationLevel.SERIALIZABLE) {
                for (Map.Entry<Integer, Long> entry :
                    tx.readVersions.entrySet()) {

                    Account current = accounts.get(entry.getKey());

                    if (
                        current == null ||
                        current.version() != entry.getValue()
                    ) {
                        tx.status = TransactionStatus.FAILED;

                        throw new SerializationException(
                            "Serializable conflict on account " +
                            entry.getKey()
                        );
                    }
                }
            }

            for (Map.Entry<Integer, Account> entry : tx.writes.entrySet()) {
                int id = entry.getKey();
                Account pending = entry.getValue();
                Account current = accounts.get(id);

                accounts.put(
                    id,
                    pending.withVersion(current.version() + 1)
                );
            }

            tx.status = TransactionStatus.COMMITTED;

            System.out.println("[COMMIT] " + tx.id);
        }

        public synchronized void rollback(Transaction tx) {
            tx.ensureActive();

            tx.writes.clear();
            tx.status = TransactionStatus.ROLLED_BACK;

            System.out.println("[ROLLBACK] " + tx.id);
        }

        public synchronized void report() {
            System.out.println("\nACCOUNT REPORT");

            accounts.values()
                .stream()
                .sorted(Comparator.comparingInt(Account::id))
                .forEach(account ->
                    System.out.printf(
                        "Account=%d Owner=%s Balance=%d Version=%d%n",
                        account.id(),
                        account.owner(),
                        account.balanceInCents(),
                        account.version()
                    )
                );
        }
    }

    interface Experiment {
        void execute();
    }

    static class ExperimentRunner {
        private final List<Experiment> experiments = new ArrayList<>();

        void register(Experiment experiment) {
            experiments.add(Objects.requireNonNull(experiment));
        }

        void executeAll() {
            for (Experiment experiment : experiments) {
                try {
                    experiment.execute();
                } catch (TransactionException exception) {
                    System.out.println(
                        "[EXPECTED TRANSACTION FAILURE] " +
                        exception.getMessage()
                    );
                }
            }
        }
    }

    static void nonRepeatableReadExperiment() {
        System.out.println("\n=== READ COMMITTED ===");

        Database db = new Database();

        Transaction reader = db.begin(IsolationLevel.READ_COMMITTED);
        Transaction writer = db.begin(IsolationLevel.READ_COMMITTED);

        Account first = db.read(reader, 1);

        db.update(writer, 1, 150_000);
        db.commit(writer);

        Account second = db.read(reader, 1);

        System.out.println(
            "Non-repeatable read: " +
            (first.balanceInCents() != second.balanceInCents())
        );

        db.commit(reader);
        db.report();
    }

    static void repeatableReadExperiment() {
        System.out.println("\n=== REPEATABLE READ ===");

        Database db = new Database();

        Transaction reader = db.begin(IsolationLevel.REPEATABLE_READ);
        Transaction writer = db.begin(IsolationLevel.READ_COMMITTED);

        Account first = db.read(reader, 1);

        db.update(writer, 1, 180_000);
        db.commit(writer);

        Account second = db.read(reader, 1);

        System.out.println(
            "Stable snapshot: " +
            (first.balanceInCents() == second.balanceInCents())
        );

        db.commit(reader);
        db.report();
    }

    static void concurrentWriteExperiment() {
        System.out.println("\n=== CONCURRENT WRITERS ===");

        Database db = new Database();

        Transaction first = db.begin(IsolationLevel.REPEATABLE_READ);
        Transaction second = db.begin(IsolationLevel.REPEATABLE_READ);

        db.read(first, 1);
        db.read(second, 1);

        db.update(first, 1, 120_000);
        db.update(second, 1, 130_000);

        db.commit(first);

        try {
            db.commit(second);
        } catch (WriteConflictException exception) {
            System.out.println("[CONFLICT] " + exception.getMessage());
        }

        db.report();
    }

    static void serializableExperiment() {
        System.out.println("\n=== SERIALIZABLE ===");

        Database db = new Database();

        Transaction reader = db.begin(IsolationLevel.SERIALIZABLE);
        Transaction writer = db.begin(IsolationLevel.READ_COMMITTED);

        db.read(reader, 1);

        db.update(writer, 1, 220_000);
        db.commit(writer);

        try {
            db.commit(reader);
        } catch (SerializationException exception) {
            System.out.println("[REJECTED] " + exception.getMessage());
        }

        db.report();
    }

    static void transferExperiment() {
        System.out.println("\n=== ATOMIC ACCOUNT TRANSFER ===");

        Database db = new Database();

        Transaction tx = db.begin(IsolationLevel.SERIALIZABLE);

        db.transfer(tx, 1, 2, 25_000);
        db.commit(tx);

        db.report();
    }

    static void rollbackExperiment() {
        System.out.println("\n=== ROLLBACK ===");

        Database db = new Database();

        Transaction tx = db.begin(IsolationLevel.READ_COMMITTED);

        db.update(tx, 1, 500);
        db.rollback(tx);

        db.report();
    }

    public static void main(String[] args) {
        ExperimentRunner runner = new ExperimentRunner();

        runner.register(NonRepeatableReads::nonRepeatableReadExperiment);
        runner.register(NonRepeatableReads::repeatableReadExperiment);
        runner.register(NonRepeatableReads::concurrentWriteExperiment);
        runner.register(NonRepeatableReads::serializableExperiment);
        runner.register(NonRepeatableReads::transferExperiment);
        runner.register(NonRepeatableReads::rollbackExperiment);

        runner.executeAll();

        System.out.println("\nALL ENTERPRISE TRANSACTION EXPERIMENTS COMPLETED.");
    }
}
