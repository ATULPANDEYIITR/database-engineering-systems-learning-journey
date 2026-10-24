import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class PostgresTransactionModel {

    enum TransactionState {
        ACTIVE,
        COMMITTED,
        ROLLED_BACK
    }

    static class TransactionException extends RuntimeException {
        TransactionException(String message) {
            super(message);
        }
    }

    static class ConstraintViolation extends TransactionException {
        ConstraintViolation(String message) {
            super(message);
        }
    }

    static class TransactionStateException extends TransactionException {
        TransactionStateException(String message) {
            super(message);
        }
    }

    static class SerializationConflict extends TransactionException {
        SerializationConflict(String message) {
            super(message);
        }
    }

    record AuditEvent(
        int transactionId,
        String action,
        String details
    ) {}

    static final class Account {
        private final int id;
        private final String owner;
        private BigDecimal balance;
        private int version;

        Account(
            int id,
            String owner,
            BigDecimal balance,
            int version
        ) {
            if (id <= 0) {
                throw new ConstraintViolation(
                    "account id must be positive"
                );
            }

            if (owner == null || owner.isBlank()) {
                throw new ConstraintViolation(
                    "owner is required"
                );
            }

            if (balance == null ||
                balance.compareTo(BigDecimal.ZERO) < 0) {
                throw new ConstraintViolation(
                    "balance cannot be negative"
                );
            }

            this.id = id;
            this.owner = owner;
            this.balance = normalize(balance);
            this.version = version;
        }

        Account copy() {
            return new Account(
                id,
                owner,
                balance,
                version
            );
        }

        int id() {
            return id;
        }

        String owner() {
            return owner;
        }

        BigDecimal balance() {
            return balance;
        }

        void setBalance(BigDecimal balance) {
            this.balance = normalize(balance);
        }

        int version() {
            return version;
        }

        void setVersion(int version) {
            this.version = version;
        }

        private static BigDecimal normalize(
            BigDecimal value
        ) {
            return value.setScale(
                2,
                RoundingMode.HALF_EVEN
            );
        }
    }

    static final class Repository {
        private Map<Integer, Account> accounts =
            new LinkedHashMap<>();

        private List<AuditEvent> auditLog =
            new ArrayList<>();

        private long version = 0;

        void addAccount(
            int id,
            String owner,
            BigDecimal balance
        ) {
            if (accounts.containsKey(id)) {
                throw new ConstraintViolation(
                    "duplicate account id"
                );
            }

            accounts.put(
                id,
                new Account(id, owner, balance, 0)
            );

            version++;
        }
    }

    static final class Savepoint {
        private final String name;
        private final Map<Integer, Account> accounts;
        private final List<AuditEvent> auditLog;

        Savepoint(
            String name,
            Map<Integer, Account> accounts,
            List<AuditEvent> auditLog
        ) {
            this.name = name;
            this.accounts = copyAccounts(accounts);
            this.auditLog = new ArrayList<>(auditLog);
        }
    }

    static final class Transaction {
        private final Repository repository;
        private final int transactionId;
        private final long initialVersion;

        private TransactionState state =
            TransactionState.ACTIVE;

        private Map<Integer, Account> workingAccounts;
        private List<AuditEvent> workingAudit;
        private final Map<String, Savepoint> savepoints =
            new LinkedHashMap<>();

        Transaction(
            Repository repository,
            int transactionId
        ) {
            this.repository = Objects.requireNonNull(
                repository
            );
            this.transactionId = transactionId;
            this.initialVersion = repository.version;
            this.workingAccounts =
                copyAccounts(repository.accounts);
            this.workingAudit =
                new ArrayList<>(repository.auditLog);
        }

        private void requireActive() {
            if (state != TransactionState.ACTIVE) {
                throw new TransactionStateException(
                    "transaction is " + state
                );
            }
        }

        private Account account(int id) {
            requireActive();

            Account account = workingAccounts.get(id);

            if (account == null) {
                throw new ConstraintViolation(
                    "account " + id + " does not exist"
                );
            }

            return account;
        }

        private void audit(
            String action,
            String details
        ) {
            workingAudit.add(
                new AuditEvent(
                    transactionId,
                    action,
                    details
                )
            );
        }

        void beginSavepoint(String name) {
            requireActive();

            if (name == null || name.isBlank()) {
                throw new ConstraintViolation(
                    "savepoint name is required"
                );
            }

            savepoints.put(
                name,
                new Savepoint(
                    name,
                    workingAccounts,
                    workingAudit
                )
            );
        }

        void rollbackToSavepoint(String name) {
            requireActive();

            Savepoint point = savepoints.get(name);

            if (point == null) {
                throw new TransactionStateException(
                    "savepoint does not exist"
                );
            }

            workingAccounts =
                copyAccounts(point.accounts);

            workingAudit =
                new ArrayList<>(point.auditLog);

            boolean found = false;

            for (String key :
                new ArrayList<>(savepoints.keySet())) {

                if (key.equals(name)) {
                    found = true;
                } else if (found) {
                    savepoints.remove(key);
                }
            }
        }

        void releaseSavepoint(String name) {
            requireActive();

            if (savepoints.remove(name) == null) {
                throw new TransactionStateException(
                    "savepoint does not exist"
                );
            }
        }

        void deposit(
            int id,
            BigDecimal amount
        ) {
            Account account = account(id);

            if (amount == null ||
                amount.compareTo(BigDecimal.ZERO) <= 0) {
                throw new ConstraintViolation(
                    "deposit must be positive"
                );
            }

            account.setBalance(
                account.balance().add(amount)
            );

            audit(
                "DEPOSIT",
                "account=" + id +
                ", amount=" + amount
            );
        }

        void withdraw(
            int id,
            BigDecimal amount
        ) {
            Account account = account(id);

            if (amount == null ||
                amount.compareTo(BigDecimal.ZERO) <= 0) {
                throw new ConstraintViolation(
                    "withdrawal must be positive"
                );
            }

            if (account.balance().compareTo(amount) < 0) {
                throw new ConstraintViolation(
                    "insufficient funds"
                );
            }

            account.setBalance(
                account.balance().subtract(amount)
            );

            audit(
                "WITHDRAW",
                "account=" + id +
                ", amount=" + amount
            );
        }

        void transfer(
            int sourceId,
            int targetId,
            BigDecimal amount
        ) {
            requireActive();

            if (sourceId == targetId) {
                throw new ConstraintViolation(
                    "source and target must differ"
                );
            }

            withdraw(sourceId, amount);
            deposit(targetId, amount);

            audit(
                "TRANSFER",
                "source=" + sourceId +
                ", target=" + targetId +
                ", amount=" + amount
            );
        }

        void commit() {
            requireActive();

            if (repository.version != initialVersion) {
                state = TransactionState.ROLLED_BACK;

                throw new SerializationConflict(
                    "repository changed during transaction"
                );
            }

            for (Map.Entry<Integer, Account> entry :
                workingAccounts.entrySet()) {

                Account current =
                    repository.accounts.get(entry.getKey());

                Account candidate = entry.getValue();

                if (current != null &&
                    current.balance()
                        .compareTo(candidate.balance()) != 0) {

                    candidate.setVersion(
                        current.version() + 1
                    );
                }
            }

            repository.accounts =
                copyAccounts(workingAccounts);

            repository.auditLog =
                new ArrayList<>(workingAudit);

            repository.version++;

            state = TransactionState.COMMITTED;
        }

        void rollback() {
            requireActive();

            workingAccounts =
                copyAccounts(repository.accounts);

            workingAudit =
                new ArrayList<>(repository.auditLog);

            savepoints.clear();

            state = TransactionState.ROLLED_BACK;
        }
    }

    static final class TransactionService {
        private final Repository repository;
        private int nextTransactionId = 1;

        TransactionService(Repository repository) {
            this.repository = repository;
        }

        Transaction begin() {
            return new Transaction(
                repository,
                nextTransactionId++
            );
        }
    }

    private static Map<Integer, Account> copyAccounts(
        Map<Integer, Account> source
    ) {
        Map<Integer, Account> result =
            new LinkedHashMap<>();

        for (Map.Entry<Integer, Account> entry :
            source.entrySet()) {

            result.put(
                entry.getKey(),
                entry.getValue().copy()
            );
        }

        return result;
    }

    private static void printAccounts(
        Repository repository,
        String title
    ) {
        System.out.println("\n" + title);
        System.out.println("-".repeat(title.length()));

        for (Account account :
            repository.accounts.values()) {

            System.out.printf(
                "%d: %-10s balance=%8s version=%d%n",
                account.id(),
                account.owner(),
                account.balance(),
                account.version()
            );
        }
    }

    public static void main(String[] args) {
        Repository repository = new Repository();

        repository.addAccount(
            1,
            "Alice",
            new BigDecimal("1500.00")
        );

        repository.addAccount(
            2,
            "Bob",
            new BigDecimal("900.00")
        );

        repository.addAccount(
            3,
            "Carol",
            new BigDecimal("300.00")
        );

        TransactionService service =
            new TransactionService(repository);

        printAccounts(
            repository,
            "Initial state"
        );

        Transaction transaction =
            service.begin();

        transaction.deposit(
            1,
            new BigDecimal("200.00")
        );

        transaction.commit();

        printAccounts(
            repository,
            "After COMMIT"
        );

        Transaction failed =
            service.begin();

        try {
            failed.withdraw(
                2,
                new BigDecimal("10000.00")
            );

            failed.commit();
        } catch (ConstraintViolation error) {
            System.out.println(
                "\nExpected failure: " +
                error.getMessage()
            );

            failed.rollback();
        }

        printAccounts(
            repository,
            "After ROLLBACK"
        );

        Transaction savepointTransaction =
            service.begin();

        savepointTransaction.deposit(
            1,
            new BigDecimal("50.00")
        );

        savepointTransaction.beginSavepoint(
            "before_risky_operation"
        );

        try {
            savepointTransaction.withdraw(
                2,
                new BigDecimal("5000.00")
            );
        } catch (ConstraintViolation error) {
            System.out.println(
                "\nSavepoint recovery: " +
                error.getMessage()
            );

            savepointTransaction.rollbackToSavepoint(
                "before_risky_operation"
            );
        }

        savepointTransaction.deposit(
            2,
            new BigDecimal("25.00")
        );

        savepointTransaction.releaseSavepoint(
            "before_risky_operation"
        );

        savepointTransaction.commit();

        printAccounts(
            repository,
            "After SAVEPOINT recovery"
        );

        Transaction transfer =
            service.begin();

        transfer.transfer(
            1,
            3,
            new BigDecimal("125.00")
        );

        transfer.commit();

        printAccounts(
            repository,
            "After atomic transfer"
        );

        Transaction first = service.begin();
        Transaction second = service.begin();

        first.deposit(
            1,
            new BigDecimal("10.00")
        );

        first.commit();

        try {
            second.deposit(
                2,
                new BigDecimal("10.00")
            );

            second.commit();
        } catch (SerializationConflict error) {
            System.out.println(
                "\nConcurrency conflict: " +
                error.getMessage()
            );
        }

        printAccounts(
            repository,
            "After conflict detection"
        );

        if (repository.accounts.get(1)
            .balance()
            .compareTo(new BigDecimal("1760.00")) != 0) {

            throw new AssertionError(
                "unexpected account 1 balance"
            );
        }

        if (repository.accounts.get(2)
            .balance()
            .compareTo(new BigDecimal("925.00")) != 0) {

            throw new AssertionError(
                "unexpected account 2 balance"
            );
        }

        if (repository.accounts.get(3)
            .balance()
            .compareTo(new BigDecimal("425.00")) != 0) {

            throw new AssertionError(
                "unexpected account 3 balance"
            );
        }

        System.out.println("\nAudit log");

        for (AuditEvent event : repository.auditLog) {
            System.out.printf(
                "tx=%d %-10s %s%n",
                event.transactionId(),
                event.action(),
                event.details()
            );
        }
    }
}
