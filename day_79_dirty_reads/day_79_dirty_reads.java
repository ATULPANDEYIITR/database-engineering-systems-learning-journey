import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicInteger;

/*
 * Dirty Reads: Enterprise Transaction Isolation Governance
 *
 * Java 17 implementation.
 *
 * Features:
 * - Explicit transaction domain types.
 * - Isolation policy evaluation.
 * - Write-set management.
 * - Snapshot visibility.
 * - Dirty-read detection.
 * - Transaction lifecycle enforcement.
 * - Commit conflict detection.
 * - Immutable observation records.
 * - Enterprise reporting.
 */

public class DirtyReadEnterprise {

    enum IsolationLevel {
        READ_UNCOMMITTED,
        READ_COMMITTED,
        REPEATABLE_READ
    }

    enum TransactionState {
        ACTIVE,
        COMMITTED,
        ROLLED_BACK
    }

    enum ObservationType {
        OWN_WRITE,
        COMMITTED,
        UNCOMMITTED,
        SNAPSHOT
    }

    static class TransactionException extends RuntimeException {
        TransactionException(String message) {
            super(message);
        }
    }

    static class ValidationException extends TransactionException {
        ValidationException(String message) {
            super(message);
        }
    }

    record Account(int id, String owner, double balance, long version) {
        Account {
            if (id <= 0) {
                throw new ValidationException("Account ID must be positive.");
            }

            if (owner == null || owner.isBlank()) {
                throw new ValidationException("Owner is required.");
            }

            if (!Double.isFinite(balance) || balance < 0) {
                throw new ValidationException("Invalid account balance.");
            }
        }

        Account withBalance(double newBalance, long newVersion) {
            return new Account(id, owner, newBalance, newVersion);
        }
    }

    record Observation(
        int accountId,
        double value,
        ObservationType type,
        Integer writerId
    ) {}

    record DirtyReadFinding(
        int readerId,
        int writerId,
        int accountId,
        double observedValue
    ) {}

    interface IsolationPolicy {
        double resolve(
            Transaction reader,
            int accountId,
            Database database
        );
    }

    static final class Transaction {

        private final int id;
        private final IsolationLevel isolation;
        private final long snapshotVersion;

        private TransactionState state = TransactionState.ACTIVE;

        private final Map<Integer, Double> writes = new HashMap<>();
        private final Map<Integer, Double> snapshot = new HashMap<>();
        private final List<Observation> observations = new ArrayList<>();

        Transaction(
            int id,
            IsolationLevel isolation,
            long snapshotVersion
        ) {
            this.id = id;
            this.isolation = isolation;
            this.snapshotVersion = snapshotVersion;
        }

        int id() {
            return id;
        }

        IsolationLevel isolation() {
            return isolation;
        }

        TransactionState state() {
            return state;
        }

        Map<Integer, Double> writes() {
            return Collections.unmodifiableMap(writes);
        }

        void requireActive() {
            if (state != TransactionState.ACTIVE) {
                throw new TransactionException(
                    "Transaction " + id + " is " + state
                );
            }
        }
    }

    static final class Database {

        private final Map<Integer, Account> accounts = new HashMap<>();
        private final Map<Integer, Transaction> transactions = new HashMap<>();

        private final AtomicInteger transactionSequence =
            new AtomicInteger(1);

        private final Map<IsolationLevel, IsolationPolicy> policies =
            new EnumMap<>(IsolationLevel.class);

        private long version;

        Database() {
            policies.put(
                IsolationLevel.READ_UNCOMMITTED,
                this::readUncommitted
            );

            policies.put(
                IsolationLevel.READ_COMMITTED,
                this::readCommitted
            );

            policies.put(
                IsolationLevel.REPEATABLE_READ,
                this::readSnapshot
            );
        }

        void addAccount(int id, String owner, double balance) {
            if (accounts.containsKey(id)) {
                throw new ValidationException("Duplicate account.");
            }

            accounts.put(
                id,
                new Account(id, owner, balance, ++version)
            );
        }

        Transaction begin(IsolationLevel isolation) {
            Objects.requireNonNull(isolation);

            Transaction transaction = new Transaction(
                transactionSequence.getAndIncrement(),
                isolation,
                version
            );

            if (isolation == IsolationLevel.REPEATABLE_READ) {
                accounts.forEach(
                    (id, account) ->
                        transaction.snapshot.put(id, account.balance())
                );
            }

            transactions.put(transaction.id(), transaction);

            System.out.printf(
                "BEGIN T%d [%s]%n",
                transaction.id(),
                isolation
            );

            return transaction;
        }

        private void requireAccount(int id) {
            if (!accounts.containsKey(id)) {
                throw new ValidationException(
                    "Account " + id + " does not exist."
                );
            }
        }

        void write(
            Transaction transaction,
            int accountId,
            double balance
        ) {
            transaction.requireActive();
            requireAccount(accountId);

            if (!Double.isFinite(balance) || balance < 0) {
                throw new ValidationException("Invalid balance.");
            }

            transaction.writes.put(accountId, balance);

            System.out.printf(
                "T%d staged account %d = %.2f%n",
                transaction.id(),
                accountId,
                balance
            );
        }

        double read(Transaction transaction, int accountId) {
            transaction.requireActive();
            requireAccount(accountId);

            IsolationPolicy policy = policies.get(
                transaction.isolation()
            );

            return policy.resolve(
                transaction,
                accountId,
                this
            );
        }

        private double readUncommitted(
            Transaction reader,
            int accountId,
            Database database
        ) {
            if (reader.writes.containsKey(accountId)) {
                return recordObservation(
                    reader,
                    accountId,
                    reader.writes.get(accountId),
                    ObservationType.OWN_WRITE,
                    null
                );
            }

            for (Transaction writer : transactions.values()) {
                if (
                    writer.id() != reader.id() &&
                    writer.state() == TransactionState.ACTIVE &&
                    writer.writes.containsKey(accountId)
                ) {
                    return recordObservation(
                        reader,
                        accountId,
                        writer.writes.get(accountId),
                        ObservationType.UNCOMMITTED,
                        writer.id()
                    );
                }
            }

            return recordObservation(
                reader,
                accountId,
                accounts.get(accountId).balance(),
                ObservationType.COMMITTED,
                null
            );
        }

        private double readCommitted(
            Transaction reader,
            int accountId,
            Database database
        ) {
            if (reader.writes.containsKey(accountId)) {
                return recordObservation(
                    reader,
                    accountId,
                    reader.writes.get(accountId),
                    ObservationType.OWN_WRITE,
                    null
                );
            }

            return recordObservation(
                reader,
                accountId,
                accounts.get(accountId).balance(),
                ObservationType.COMMITTED,
                null
            );
        }

        private double readSnapshot(
            Transaction reader,
            int accountId,
            Database database
        ) {
            if (reader.writes.containsKey(accountId)) {
                return recordObservation(
                    reader,
                    accountId,
                    reader.writes.get(accountId),
                    ObservationType.OWN_WRITE,
                    null
                );
            }

            return recordObservation(
                reader,
                accountId,
                reader.snapshot.get(accountId),
                ObservationType.SNAPSHOT,
                null
            );
        }

        private double recordObservation(
            Transaction transaction,
            int accountId,
            double value,
            ObservationType type,
            Integer writerId
        ) {
            Observation observation = new Observation(
                accountId,
                value,
                type,
                writerId
            );

            transaction.observations.add(observation);

            System.out.printf(
                "T%d READ account %d = %.2f [%s]%n",
                transaction.id(),
                accountId,
                value,
                type
            );

            return value;
        }

        void commit(Transaction transaction) {
            transaction.requireActive();

            // Validate the entire write set before publishing changes.
            for (Map.Entry<Integer, Double> entry :
                    transaction.writes.entrySet()) {

                requireAccount(entry.getKey());

                if (
                    !Double.isFinite(entry.getValue()) ||
                    entry.getValue() < 0
                ) {
                    throw new ValidationException(
                        "Commit contains an invalid balance."
                    );
                }

                if (
                    transaction.isolation() ==
                        IsolationLevel.REPEATABLE_READ &&
                    accounts.get(entry.getKey()).version() >
                        transaction.snapshotVersion
                ) {
                    throw new TransactionException(
                        "Concurrent update conflict on account " +
                        entry.getKey()
                    );
                }
            }

            transaction.writes.forEach((id, balance) -> {
                Account previous = accounts.get(id);

                accounts.put(
                    id,
                    previous.withBalance(balance, ++version)
                );
            });

            transaction.state = TransactionState.COMMITTED;

            System.out.printf("COMMIT T%d%n", transaction.id());
        }

        void rollback(Transaction transaction) {
            transaction.requireActive();

            transaction.writes.clear();
            transaction.state = TransactionState.ROLLED_BACK;

            System.out.printf("ROLLBACK T%d%n", transaction.id());
        }

        double committedBalance(int accountId) {
            requireAccount(accountId);
            return accounts.get(accountId).balance();
        }

        List<DirtyReadFinding> detectDirtyReads() {
            List<DirtyReadFinding> findings = new ArrayList<>();

            for (Transaction reader : transactions.values()) {
                for (Observation observation : reader.observations) {
                    if (
                        observation.type() !=
                            ObservationType.UNCOMMITTED
                    ) {
                        continue;
                    }

                    Transaction writer = transactions.get(
                        observation.writerId()
                    );

                    if (
                        writer != null &&
                        writer.state() == TransactionState.ROLLED_BACK
                    ) {
                        findings.add(new DirtyReadFinding(
                            reader.id(),
                            writer.id(),
                            observation.accountId(),
                            observation.value()
                        ));
                    }
                }
            }

            return List.copyOf(findings);
        }

        void report() {
            System.out.println("\nTRANSACTION GOVERNANCE REPORT");

            for (Transaction transaction : transactions.values()) {
                System.out.printf(
                    "T%d | %s | %s | pending writes: %d%n",
                    transaction.id(),
                    transaction.isolation(),
                    transaction.state(),
                    transaction.writes.size()
                );
            }

            System.out.println("\nDIRTY READ FINDINGS");

            List<DirtyReadFinding> findings = detectDirtyReads();

            if (findings.isEmpty()) {
                System.out.println("No confirmed dirty reads.");
            }

            findings.forEach(finding ->
                System.out.printf(
                    "Reader T%d observed %.2f from rolled-back writer T%d%n",
                    finding.readerId(),
                    finding.observedValue(),
                    finding.writerId()
                )
            );
        }
    }

    static void dirtyReadScenario() {
        System.out.println("\n=== DIRTY READ SCENARIO ===");

        Database database = new Database();
        database.addAccount(101, "Alice", 1000);

        Transaction writer = database.begin(
            IsolationLevel.READ_UNCOMMITTED
        );

        Transaction reader = database.begin(
            IsolationLevel.READ_UNCOMMITTED
        );

        database.write(writer, 101, 400);
        double observed = database.read(reader, 101);

        database.rollback(writer);

        System.out.println("Reader observed: " + observed);
        System.out.println(
            "Actual committed value: " +
            database.committedBalance(101)
        );

        database.report();
    }

    static void readCommittedScenario() {
        System.out.println("\n=== READ COMMITTED SCENARIO ===");

        Database database = new Database();
        database.addAccount(102, "Bob", 2000);

        Transaction writer = database.begin(
            IsolationLevel.READ_UNCOMMITTED
        );

        Transaction reader = database.begin(
            IsolationLevel.READ_COMMITTED
        );

        database.write(writer, 102, 700);

        double observed = database.read(reader, 102);

        if (observed != 2000) {
            throw new AssertionError("Dirty read was not prevented.");
        }

        database.rollback(writer);

        System.out.println("Protected read: " + observed);
    }

    static void repeatableReadScenario() {
        System.out.println("\n=== REPEATABLE READ SCENARIO ===");

        Database database = new Database();
        database.addAccount(103, "Carol", 3000);

        Transaction reader = database.begin(
            IsolationLevel.REPEATABLE_READ
        );

        Transaction writer = database.begin(
            IsolationLevel.READ_COMMITTED
        );

        double first = database.read(reader, 103);

        database.write(writer, 103, 2500);
        database.commit(writer);

        double second = database.read(reader, 103);

        System.out.println("First observation: " + first);
        System.out.println("Second observation: " + second);
        System.out.println(
            "Current value: " + database.committedBalance(103)
        );

        if (first != second) {
            throw new AssertionError("Snapshot changed unexpectedly.");
        }
    }

    static void validationScenario() {
        System.out.println("\n=== VALIDATION SCENARIO ===");

        Database database = new Database();
        database.addAccount(104, "David", 500);

        Transaction transaction = database.begin(
            IsolationLevel.READ_COMMITTED
        );

        try {
            database.write(transaction, 104, -100);
            throw new AssertionError("Negative balance accepted.");
        } catch (ValidationException expected) {
            System.out.println(
                "Invalid write rejected: " + expected.getMessage()
            );
        }

        database.rollback(transaction);

        try {
            database.commit(transaction);
            throw new AssertionError("Inactive transaction accepted.");
        } catch (TransactionException expected) {
            System.out.println(
                "Invalid state rejected: " + expected.getMessage()
            );
        }
    }

    public static void main(String[] args) {
        try {
            dirtyReadScenario();
            readCommittedScenario();
            repeatableReadScenario();
            validationScenario();

            System.out.println(
                "\nEnterprise transaction scenarios completed."
            );

        } catch (Exception exception) {
            System.err.println(
                "Execution failure: " + exception.getMessage()
            );

            System.exit(1);
        }
    }
}
