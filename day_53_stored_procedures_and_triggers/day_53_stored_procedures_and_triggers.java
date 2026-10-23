import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class StoredProceduresAndTriggers {

    enum TransactionType {
        CREDIT,
        DEBIT
    }

    enum AccountStatus {
        ACTIVE,
        SUSPENDED,
        CLOSED
    }

    record Account(
        int id,
        String customerName,
        BigDecimal balance,
        AccountStatus status
    ) {}

    record Transaction(
        long id,
        int accountId,
        BigDecimal amount,
        TransactionType type,
        Instant createdAt
    ) {}

    record AuditRecord(
        long id,
        int accountId,
        BigDecimal oldBalance,
        BigDecimal newBalance,
        Instant changedAt
    ) {}

    static class DatabaseException extends RuntimeException {
        DatabaseException(String message) {
            super(message);
        }
    }

    static class ConstraintViolation extends DatabaseException {
        ConstraintViolation(String message) {
            super(message);
        }
    }

    static class NotFoundException extends DatabaseException {
        NotFoundException(String message) {
            super(message);
        }
    }

    /*
     * The trigger interface makes database events explicit.
     * BEFORE handlers may reject a mutation.
     * AFTER handlers react to a successful mutation.
     */
    interface AccountInsertTrigger {
        void beforeInsert(Account account);
    }

    interface AccountUpdateTrigger {
        void beforeUpdate(Account oldAccount, Account newAccount);

        void afterUpdate(Account oldAccount, Account newAccount);
    }

    interface TransactionInsertTrigger {
        void afterInsert(Transaction transaction);
    }

    static final class RepositoryDatabase {
        private final Map<Integer, Account> accounts = new HashMap<>();
        private final Map<Long, Transaction> transactions = new HashMap<>();
        private final List<AuditRecord> auditLog = new ArrayList<>();

        private final List<AccountInsertTrigger> accountInsertTriggers =
            new ArrayList<>();

        private final List<AccountUpdateTrigger> accountUpdateTriggers =
            new ArrayList<>();

        private final List<TransactionInsertTrigger> transactionTriggers =
            new ArrayList<>();

        private long nextTransactionId = 1;
        private long nextAuditId = 1;

        void registerAccountInsertTrigger(AccountInsertTrigger trigger) {
            accountInsertTriggers.add(Objects.requireNonNull(trigger));
        }

        void registerAccountUpdateTrigger(AccountUpdateTrigger trigger) {
            accountUpdateTriggers.add(Objects.requireNonNull(trigger));
        }

        void registerTransactionTrigger(TransactionInsertTrigger trigger) {
            transactionTriggers.add(Objects.requireNonNull(trigger));
        }

        Account insertAccount(Account account) {
            if (accounts.containsKey(account.id())) {
                throw new ConstraintViolation("Account ID already exists");
            }

            for (AccountInsertTrigger trigger : accountInsertTriggers) {
                trigger.beforeInsert(account);
            }

            accounts.put(account.id(), account);
            return account;
        }

        Account updateBalance(int accountId, BigDecimal newBalance) {
            Account oldAccount = findAccount(accountId);

            Account newAccount = new Account(
                oldAccount.id(),
                oldAccount.customerName(),
                newBalance,
                oldAccount.status()
            );

            for (AccountUpdateTrigger trigger : accountUpdateTriggers) {
                trigger.beforeUpdate(oldAccount, newAccount);
            }

            accounts.put(accountId, newAccount);

            for (AccountUpdateTrigger trigger : accountUpdateTriggers) {
                trigger.afterUpdate(oldAccount, newAccount);
            }

            return newAccount;
        }

        Transaction insertTransaction(
            int accountId,
            BigDecimal amount,
            TransactionType type
        ) {
            findAccount(accountId);

            if (amount.compareTo(BigDecimal.ZERO) <= 0) {
                throw new ConstraintViolation(
                    "Transaction amount must be positive"
                );
            }

            Transaction transaction = new Transaction(
                nextTransactionId++,
                accountId,
                amount,
                type,
                Instant.now()
            );

            transactions.put(transaction.id(), transaction);

            try {
                for (TransactionInsertTrigger trigger : transactionTriggers) {
                    trigger.afterInsert(transaction);
                }
            } catch (RuntimeException error) {
                transactions.remove(transaction.id());
                throw error;
            }

            return transaction;
        }

        Account findAccount(int accountId) {
            Account account = accounts.get(accountId);

            if (account == null) {
                throw new NotFoundException(
                    "Account " + accountId + " does not exist"
                );
            }

            return account;
        }

        List<AuditRecord> auditLog() {
            return List.copyOf(auditLog);
        }

        Map<Integer, Account> accountSnapshot() {
            return Map.copyOf(accounts);
        }

        long auditSize() {
            return auditLog.size();
        }

        void truncateAudit(long size) {
            while (auditLog.size() > size) {
                auditLog.remove(auditLog.size() - 1);
            }
        }

        void appendAudit(
            int accountId,
            BigDecimal oldBalance,
            BigDecimal newBalance
        ) {
            auditLog.add(
                new AuditRecord(
                    nextAuditId++,
                    accountId,
                    oldBalance,
                    newBalance,
                    Instant.now()
                )
            );
        }
    }

    /*
     * Explicit procedure service.
     *
     * A procedure is treated as an application-facing database operation
     * with controlled parameters and a defined business result.
     */
    static final class AccountProcedureService {
        private final RepositoryDatabase database;

        AccountProcedureService(RepositoryDatabase database) {
            this.database = database;
        }

        Account createAccount(
            int id,
            String customerName,
            BigDecimal openingBalance
        ) {
            if (id <= 0) {
                throw new ConstraintViolation("Account ID must be positive");
            }

            String normalizedName = customerName == null
                ? ""
                : customerName.trim();

            if (normalizedName.isEmpty()) {
                throw new ConstraintViolation(
                    "Customer name cannot be empty"
                );
            }

            if (openingBalance == null ||
                openingBalance.compareTo(BigDecimal.ZERO) < 0) {
                throw new ConstraintViolation(
                    "Opening balance cannot be negative"
                );
            }

            return database.insertAccount(
                new Account(
                    id,
                    normalizedName,
                    openingBalance,
                    AccountStatus.ACTIVE
                )
            );
        }
    }

    static final class TransferProcedure {
        private final RepositoryDatabase database;

        TransferProcedure(RepositoryDatabase database) {
            this.database = database;
        }

        void execute(
            int sourceId,
            int destinationId,
            BigDecimal amount
        ) {
            if (sourceId == destinationId) {
                throw new ConstraintViolation(
                    "Source and destination must differ"
                );
            }

            if (amount == null ||
                amount.compareTo(BigDecimal.ZERO) <= 0) {
                throw new ConstraintViolation(
                    "Transfer amount must be positive"
                );
            }

            Account sourceBefore = database.findAccount(sourceId);
            Account destinationBefore = database.findAccount(destinationId);

            long auditSize = database.auditSize();

            try {
                if (sourceBefore.balance().compareTo(amount) < 0) {
                    throw new ConstraintViolation("Insufficient funds");
                }

                database.insertTransaction(
                    sourceId,
                    amount,
                    TransactionType.DEBIT
                );

                database.insertTransaction(
                    destinationId,
                    amount,
                    TransactionType.CREDIT
                );
            } catch (RuntimeException error) {
                /*
                 * A real PostgreSQL transaction provides rollback semantics
                 * at the database engine level. This in-memory example
                 * restores affected state explicitly.
                 */
                database.updateBalance(
                    sourceId,
                    sourceBefore.balance()
                );

                database.updateBalance(
                    destinationId,
                    destinationBefore.balance()
                );

                database.truncateAudit(auditSize);
                throw error;
            }
        }
    }

    private static void registerTriggers(RepositoryDatabase database) {
        database.registerAccountInsertTrigger(account -> {
            if (account.balance().compareTo(BigDecimal.ZERO) < 0) {
                throw new ConstraintViolation(
                    "Balance cannot be negative"
                );
            }
        });

        database.registerAccountUpdateTrigger(
            new AccountUpdateTrigger() {
                @Override
                public void beforeUpdate(
                    Account oldAccount,
                    Account newAccount
                ) {
                    if (newAccount.balance().compareTo(BigDecimal.ZERO) < 0) {
                        throw new ConstraintViolation(
                            "Balance cannot become negative"
                        );
                    }

                    BigDecimal change = newAccount.balance()
                        .subtract(oldAccount.balance())
                        .abs();

                    if (change.compareTo(new BigDecimal("10000")) > 0) {
                        throw new ConstraintViolation(
                            "Balance change exceeds the trigger threshold"
                        );
                    }
                }

                @Override
                public void afterUpdate(
                    Account oldAccount,
                    Account newAccount
                ) {
                    database.appendAudit(
                        newAccount.id(),
                        oldAccount.balance(),
                        newAccount.balance()
                    );
                }
            }
        );

        database.registerTransactionTrigger(transaction -> {
            Account account = database.findAccount(transaction.accountId());

            BigDecimal newBalance;

            if (transaction.type() == TransactionType.CREDIT) {
                newBalance = account.balance().add(transaction.amount());
            } else {
                newBalance = account.balance().subtract(transaction.amount());
            }

            database.updateBalance(account.id(), newBalance);
        });
    }

    private static void printAccounts(RepositoryDatabase database) {
        System.out.println("\nAccounts");

        database.accountSnapshot()
            .values()
            .stream()
            .sorted((a, b) -> Integer.compare(a.id(), b.id()))
            .forEach(account ->
                System.out.printf(
                    "%d | %s | %s | %s%n",
                    account.id(),
                    account.customerName(),
                    account.balance(),
                    account.status()
                )
            );
    }

    private static void printAuditLog(RepositoryDatabase database) {
        System.out.println("\nAudit records");

        database.auditLog().forEach(System.out::println);
    }

    public static void main(String[] args) {
        RepositoryDatabase database = new RepositoryDatabase();
        registerTriggers(database);

        AccountProcedureService accountProcedures =
            new AccountProcedureService(database);

        TransferProcedure transferProcedure =
            new TransferProcedure(database);

        accountProcedures.createAccount(
            101,
            "Aarav Mehta",
            new BigDecimal("10000.00")
        );

        accountProcedures.createAccount(
            102,
            "Meera Sharma",
            new BigDecimal("5000.00")
        );

        printAccounts(database);

        database.insertTransaction(
            101,
            new BigDecimal("750.00"),
            TransactionType.CREDIT
        );

        database.insertTransaction(
            102,
            new BigDecimal("500.00"),
            TransactionType.DEBIT
        );

        printAccounts(database);

        System.out.println("\nExecuting transfer procedure");

        transferProcedure.execute(
            101,
            102,
            new BigDecimal("1000.00")
        );

        printAccounts(database);
        printAuditLog(database);

        System.out.println("\nTesting trigger failure");

        try {
            database.updateBalance(
                101,
                new BigDecimal("50000.00")
            );
        } catch (DatabaseException error) {
            System.out.println(
                "Expected failure: " + error.getMessage()
            );
        }

        System.out.println("\nTesting procedure validation");

        try {
            accountProcedures.createAccount(
                103,
                "",
                new BigDecimal("100.00")
            );
        } catch (DatabaseException error) {
            System.out.println(
                "Expected failure: " + error.getMessage()
            );
        }
    }
}
