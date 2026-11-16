import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.locks.ReentrantLock;
import java.util.stream.Collectors;

/*
 * Transaction Lifecycle Enterprise Management System
 *
 * Java 17
 *
 * Features:
 * - Transaction state machine
 * - Immutable transaction events
 * - Account domain model
 * - Commit and rollback
 * - Savepoints
 * - Approval-independent transaction execution
 * - Optimistic concurrency control
 * - Atomic commit publication
 * - Validation and exception handling
 *
 * Compile:
 *   javac TransactionLifecycle.java
 *
 * Run:
 *   java TransactionLifecycle
 */

public class TransactionLifecycle {

    enum TransactionState {
        NEW,
        ACTIVE,
        COMMITTING,
        COMMITTED,
        ROLLING_BACK,
        ROLLED_BACK,
        FAILED
    }

    enum OperationType {
        DEPOSIT,
        WITHDRAW,
        TRANSFER
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

    static class InsufficientFundsException extends TransactionException {
        InsufficientFundsException(String message) {
            super(message);
        }
    }

    static class ConcurrencyException extends TransactionException {
        ConcurrencyException(String message) {
            super(message);
        }
    }

    static class InvalidStateException extends TransactionException {
        InvalidStateException(String message) {
            super(message);
        }
    }

    record TransactionEvent(
        Instant timestamp,
        TransactionState previousState,
        TransactionState currentState,
        String description
    ) {}

    record Operation(
        OperationType type,
        String sourceAccount,
        String destinationAccount,
        BigDecimal amount
    ) {}

    record TransactionResult(
        UUID transactionId,
        TransactionState finalState,
        int operationCount,
        String message
    ) {}

    interface TransactionListener {
        void onStateChanged(TransactionEvent event);
    }

    static final class Account {
        private final String id;
        private final String owner;
        private BigDecimal balance;
        private long version;

        Account(String id, String owner, BigDecimal balance) {
            if (
                id == null || id.isBlank() ||
                owner == null || owner.isBlank()
            ) {
                throw new ValidationException("Account details are required.");
            }

            this.id = id;
            this.owner = owner;
            this.balance = validateInitialBalance(balance);
            this.version = 0;
        }

        private static BigDecimal validateInitialBalance(
            BigDecimal balance
        ) {
            Objects.requireNonNull(balance, "Balance is required.");

            BigDecimal normalized = balance.setScale(
                2,
                RoundingMode.UNNECESSARY
            );

            if (normalized.signum() < 0) {
                throw new ValidationException(
                    "Initial balance cannot be negative."
                );
            }

            return normalized;
        }

        Account copy() {
            Account copy = new Account(id, owner, balance);
            copy.version = version;
            return copy;
        }

        String id() {
            return id;
        }

        String owner() {
            return owner;
        }

        BigDecimal balance() {
            return balance;
        }

        long version() {
            return version;
        }
    }

    static final class Transaction {
        private final UUID id = UUID.randomUUID();

        private TransactionState state = TransactionState.NEW;

        private final Map<String, Account> workingAccounts;
        private final Map<String, Long> originalVersions;

        private final List<Operation> operations = new ArrayList<>();
        private final List<TransactionEvent> history = new ArrayList<>();

        private final Map<String, Savepoint> savepoints =
            new LinkedHashMap<>();

        private String error;

        private Transaction(
            Map<String, Account> snapshot,
            TransactionListener listener
        ) {
            this.workingAccounts = copyAccounts(snapshot);

            this.originalVersions = snapshot.entrySet()
                .stream()
                .collect(Collectors.toMap(
                    Map.Entry::getKey,
                    entry -> entry.getValue().version()
                ));

            transition(
                TransactionState.ACTIVE,
                "Transaction started.",
                listener
            );
        }

        private void transition(
            TransactionState next,
            String description,
            TransactionListener listener
        ) {
            Map<TransactionState, List<TransactionState>> allowed =
                Map.of(
                    TransactionState.NEW,
                    List.of(TransactionState.ACTIVE),

                    TransactionState.ACTIVE,
                    List.of(
                        TransactionState.COMMITTING,
                        TransactionState.ROLLING_BACK,
                        TransactionState.FAILED
                    ),

                    TransactionState.COMMITTING,
                    List.of(
                        TransactionState.COMMITTED,
                        TransactionState.FAILED
                    ),

                    TransactionState.ROLLING_BACK,
                    List.of(TransactionState.ROLLED_BACK),

                    TransactionState.FAILED,
                    List.of(TransactionState.ROLLING_BACK),

                    TransactionState.COMMITTED,
                    List.of(),

                    TransactionState.ROLLED_BACK,
                    List.of()
                );

            if (!allowed.get(state).contains(next)) {
                throw new InvalidStateException(
                    "Invalid transition: " + state + " -> " + next
                );
            }

            TransactionEvent event = new TransactionEvent(
                Instant.now(),
                state,
                next,
                description
            );

            state = next;
            history.add(event);

            if (listener != null) {
                listener.onStateChanged(event);
            }
        }

        private void requireActive() {
            if (state != TransactionState.ACTIVE) {
                throw new InvalidStateException(
                    "Transaction is not active."
                );
            }
        }

        private Account account(String id) {
            Account account = workingAccounts.get(id);

            if (account == null) {
                throw new ValidationException(
                    "Account does not exist: " + id
                );
            }

            return account;
        }

        void deposit(String accountId, BigDecimal amount) {
            requireActive();

            BigDecimal value = validateAmount(amount);
            Account account = account(accountId);

            account.balance = account.balance.add(value);

            operations.add(new Operation(
                OperationType.DEPOSIT,
                accountId,
                null,
                value
            ));
        }

        void withdraw(String accountId, BigDecimal amount) {
            requireActive();

            BigDecimal value = validateAmount(amount);
            Account account = account(accountId);

            if (account.balance.compareTo(value) < 0) {
                throw new InsufficientFundsException(
                    "Insufficient funds in " + accountId
                );
            }

            account.balance = account.balance.subtract(value);

            operations.add(new Operation(
                OperationType.WITHDRAW,
                accountId,
                null,
                value
            ));
        }

        void transfer(
            String sourceId,
            String destinationId,
            BigDecimal amount
        ) {
            requireActive();

            if (sourceId.equals(destinationId)) {
                throw new ValidationException(
                    "Source and destination must differ."
                );
            }

            BigDecimal value = validateAmount(amount);

            Account source = account(sourceId);
            Account destination = account(destinationId);

            if (source.balance.compareTo(value) < 0) {
                throw new InsufficientFundsException(
                    "Insufficient funds."
                );
            }

            // Both modifications remain private until commit.
            source.balance = source.balance.subtract(value);
            destination.balance = destination.balance.add(value);

            operations.add(new Operation(
                OperationType.TRANSFER,
                sourceId,
                destinationId,
                value
            ));
        }

        void createSavepoint(String name) {
            requireActive();

            if (
                name == null ||
                name.isBlank() ||
                savepoints.containsKey(name)
            ) {
                throw new ValidationException(
                    "Invalid or duplicate savepoint."
                );
            }

            savepoints.put(
                name,
                new Savepoint(
                    copyAccounts(workingAccounts),
                    operations.size()
                )
            );
        }

        void rollbackToSavepoint(String name) {
            requireActive();

            Savepoint savepoint = savepoints.get(name);

            if (savepoint == null) {
                throw new ValidationException(
                    "Savepoint does not exist."
                );
            }

            workingAccounts.clear();
            workingAccounts.putAll(
                copyAccounts(savepoint.accounts())
            );

            while (operations.size() > savepoint.operationCount()) {
                operations.remove(operations.size() - 1);
            }

            List<String> names = new ArrayList<>(savepoints.keySet());
            int index = names.indexOf(name);

            for (int i = names.size() - 1; i > index; i--) {
                savepoints.remove(names.get(i));
            }
        }

        UUID id() {
            return id;
        }

        TransactionState state() {
            return state;
        }

        String error() {
            return error;
        }

        int operationCount() {
            return operations.size();
        }

        List<TransactionEvent> history() {
            return Collections.unmodifiableList(history);
        }
    }

    record Savepoint(
        Map<String, Account> accounts,
        int operationCount
    ) {
        Savepoint {
            accounts = Collections.unmodifiableMap(
                copyAccounts(accounts)
            );
        }
    }

    static BigDecimal validateAmount(BigDecimal amount) {
        Objects.requireNonNull(amount, "Amount is required.");

        BigDecimal normalized = amount.setScale(
            2,
            RoundingMode.UNNECESSARY
        );

        if (normalized.signum() <= 0) {
            throw new ValidationException(
                "Amount must be positive."
            );
        }

        return normalized;
    }

    static Map<String, Account> copyAccounts(
        Map<String, Account> source
    ) {
        Map<String, Account> copy = new HashMap<>();

        source.forEach(
            (id, account) -> copy.put(id, account.copy())
        );

        return copy;
    }

    static final class AccountRepository {
        private final Map<String, Account> accounts =
            new HashMap<>();

        private final ReentrantLock commitLock =
            new ReentrantLock(true);

        private final TransactionListener listener;

        AccountRepository(TransactionListener listener) {
            this.listener = listener;
        }

        void addAccount(Account account) {
            commitLock.lock();

            try {
                if (accounts.containsKey(account.id())) {
                    throw new ValidationException(
                        "Duplicate account."
                    );
                }

                accounts.put(account.id(), account.copy());
            } finally {
                commitLock.unlock();
            }
        }

        Transaction begin() {
            commitLock.lock();

            try {
                return new Transaction(
                    copyAccounts(accounts),
                    listener
                );
            } finally {
                commitLock.unlock();
            }
        }

        void commit(Transaction transaction) {
            transaction.requireActive();

            transaction.transition(
                TransactionState.COMMITTING,
                "Validating commit.",
                listener
            );

            try {
                commitLock.lock();

                try {
                    for (
                        Map.Entry<String, Account> entry :
                        transaction.workingAccounts.entrySet()
                    ) {
                        String id = entry.getKey();
                        Account staged = entry.getValue();
                        Account current = accounts.get(id);

                        if (current == null) {
                            throw new ConcurrencyException(
                                "Account disappeared: " + id
                            );
                        }

                        if (
                            current.version() !=
                            transaction.originalVersions.get(id)
                        ) {
                            throw new ConcurrencyException(
                                "Concurrent modification: " + id
                            );
                        }

                        if (staged.balance().signum() < 0) {
                            throw new ValidationException(
                                "Negative balance detected."
                            );
                        }
                    }

                    // Prepare a complete replacement before publication.
                    Map<String, Account> replacement =
                        copyAccounts(accounts);

                    transaction.workingAccounts.forEach((id, staged) -> {
                        Account current = replacement.get(id);

                        if (
                            current.balance().compareTo(
                                staged.balance()
                            ) != 0
                        ) {
                            current.balance = staged.balance();
                            current.version++;
                        }
                    });

                    accounts.clear();
                    accounts.putAll(replacement);

                } finally {
                    commitLock.unlock();
                }

                transaction.transition(
                    TransactionState.COMMITTED,
                    "Commit completed successfully.",
                    listener
                );

            } catch (RuntimeException exception) {
                transaction.error = exception.getMessage();

                transaction.transition(
                    TransactionState.FAILED,
                    "Commit failed: " + exception.getMessage(),
                    listener
                );

                throw exception;
            }
        }

        void rollback(Transaction transaction) {
            if (
                transaction.state != TransactionState.ACTIVE &&
                transaction.state != TransactionState.FAILED
            ) {
                throw new InvalidStateException(
                    "Transaction cannot be rolled back."
                );
            }

            transaction.transition(
                TransactionState.ROLLING_BACK,
                "Discarding uncommitted changes.",
                listener
            );

            transaction.workingAccounts.clear();
            transaction.operations.clear();
            transaction.savepoints.clear();

            transaction.transition(
                TransactionState.ROLLED_BACK,
                "Rollback completed.",
                listener
            );
        }

        List<Account> findAll() {
            commitLock.lock();

            try {
                return accounts.values()
                    .stream()
                    .map(Account::copy)
                    .toList();
            } finally {
                commitLock.unlock();
            }
        }
    }

    static final class TransactionService {
        private final AccountRepository repository;

        TransactionService(AccountRepository repository) {
            this.repository = repository;
        }

        TransactionResult execute(
            java.util.function.Consumer<Transaction> work
        ) {
            Transaction transaction = repository.begin();

            try {
                work.accept(transaction);
                repository.commit(transaction);

                return new TransactionResult(
                    transaction.id(),
                    transaction.state(),
                    transaction.operationCount(),
                    "Transaction committed."
                );

            } catch (RuntimeException exception) {
                if (
                    transaction.state() == TransactionState.ACTIVE ||
                    transaction.state() == TransactionState.FAILED
                ) {
                    repository.rollback(transaction);
                }

                return new TransactionResult(
                    transaction.id(),
                    transaction.state(),
                    transaction.operationCount(),
                    exception.getMessage()
                );
            }
        }
    }

    static void printAccounts(AccountRepository repository) {
        System.out.println("\nACCOUNT REPORT");

        repository.findAll().stream()
            .sorted(java.util.Comparator.comparing(Account::id))
            .forEach(account ->
                System.out.printf(
                    "%-12s %-12s %12s Version=%d%n",
                    account.id(),
                    account.owner(),
                    account.balance().toPlainString(),
                    account.version()
                )
            );
    }

    public static void main(String[] args) {
        TransactionListener listener = event ->
            System.out.printf(
                "[%s] %s -> %s | %s%n",
                event.timestamp(),
                event.previousState(),
                event.currentState(),
                event.description()
            );

        AccountRepository repository =
            new AccountRepository(listener);

        repository.addAccount(
            new Account(
                "ACC-001",
                "Alice",
                new BigDecimal("10000.00")
            )
        );

        repository.addAccount(
            new Account(
                "ACC-002",
                "Bob",
                new BigDecimal("5000.00")
            )
        );

        repository.addAccount(
            new Account(
                "ACC-003",
                "Charlie",
                new BigDecimal("2500.00")
            )
        );

        TransactionService service =
            new TransactionService(repository);

        System.out.println("\nSCENARIO 1: SUCCESSFUL COMMIT");

        System.out.println(service.execute(transaction -> {
            transaction.transfer(
                "ACC-001",
                "ACC-002",
                new BigDecimal("1500.00")
            );

            transaction.deposit(
                "ACC-003",
                new BigDecimal("250.00")
            );
        }));

        printAccounts(repository);

        System.out.println("\nSCENARIO 2: SAVEPOINT");

        System.out.println(service.execute(transaction -> {
            transaction.deposit(
                "ACC-001",
                new BigDecimal("200.00")
            );

            transaction.createSavepoint("BEFORE_WITHDRAWAL");

            transaction.withdraw(
                "ACC-002",
                new BigDecimal("300.00")
            );

            transaction.rollbackToSavepoint(
                "BEFORE_WITHDRAWAL"
            );
        }));

        printAccounts(repository);

        System.out.println("\nSCENARIO 3: FULL ROLLBACK");

        System.out.println(service.execute(transaction -> {
            transaction.withdraw(
                "ACC-002",
                new BigDecimal("100.00")
            );

            throw new ValidationException(
                "Business validation rejected the transaction."
            );
        }));

        printAccounts(repository);

        System.out.println("\nSCENARIO 4: CONCURRENT MODIFICATION");

        Transaction first = repository.begin();
        Transaction second = repository.begin();

        first.deposit("ACC-001", new BigDecimal("100.00"));
        second.deposit("ACC-001", new BigDecimal("200.00"));

        repository.commit(first);

        try {
            repository.commit(second);
        } catch (ConcurrencyException exception) {
            System.out.println(
                "Expected conflict: " + exception.getMessage()
            );

            repository.rollback(second);
        }

        printAccounts(repository);

        System.out.println("\nALL SCENARIOS COMPLETED");
    }
}
