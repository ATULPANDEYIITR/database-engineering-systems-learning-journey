#include <algorithm>
#include <cassert>
#include <iomanip>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

enum class TransactionState {
    Active,
    Committed,
    RolledBack
};

class TransactionError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class ConstraintViolation : public TransactionError {
public:
    using TransactionError::TransactionError;
};

class TransactionStateError : public TransactionError {
public:
    using TransactionError::TransactionError;
};

class SerializationConflict : public TransactionError {
public:
    using TransactionError::TransactionError;
};

struct Account {
    int id;
    std::string owner;
    long long balanceCents;
    int version;
};

struct AuditEvent {
    int transactionId;
    std::string action;
    std::string details;
};

class Database {
public:
    std::map<int, Account> accounts;
    std::vector<AuditEvent> auditLog;
    long long version = 0;

    void addAccount(
        int id,
        const std::string& owner,
        long long balanceCents
    ) {
        if (accounts.contains(id)) {
            throw ConstraintViolation(
                "account id must be unique"
            );
        }

        if (balanceCents < 0) {
            throw ConstraintViolation(
                "account balance cannot be negative"
            );
        }

        accounts.emplace(
            id,
            Account{id, owner, balanceCents, 0}
        );

        ++version;
    }
};

struct Savepoint {
    std::string name;
    std::map<int, Account> accounts;
    std::vector<AuditEvent> auditLog;
};

class Transaction {
private:
    Database& database;
    int transactionId;
    TransactionState state = TransactionState::Active;
    long long initialVersion;

    std::map<int, Account> workingAccounts;
    std::vector<AuditEvent> workingAudit;
    std::map<std::string, Savepoint> savepoints;

    void requireActive() const {
        if (state != TransactionState::Active) {
            throw TransactionStateError(
                "transaction is not active"
            );
        }
    }

    Account& account(int id) {
        requireActive();

        auto iterator = workingAccounts.find(id);

        if (iterator == workingAccounts.end()) {
            throw ConstraintViolation(
                "account does not exist"
            );
        }

        return iterator->second;
    }

    void audit(
        const std::string& action,
        const std::string& details
    ) {
        workingAudit.push_back(
            AuditEvent{
                transactionId,
                action,
                details
            }
        );
    }

public:
    Transaction(
        Database& database,
        int transactionId
    )
        : database(database),
          transactionId(transactionId),
          initialVersion(database.version),
          workingAccounts(database.accounts),
          workingAudit(database.auditLog) {}

    void beginSavepoint(const std::string& name) {
        requireActive();

        if (name.empty()) {
            throw ConstraintViolation(
                "savepoint name cannot be empty"
            );
        }

        savepoints[name] = Savepoint{
            name,
            workingAccounts,
            workingAudit
        };
    }

    void rollbackToSavepoint(const std::string& name) {
        requireActive();

        auto iterator = savepoints.find(name);

        if (iterator == savepoints.end()) {
            throw TransactionStateError(
                "savepoint does not exist"
            );
        }

        workingAccounts = iterator->second.accounts;
        workingAudit = iterator->second.auditLog;

        // Savepoints created after the target are no longer valid.
        auto target = iterator;
        ++target;

        while (target != savepoints.end()) {
            target = savepoints.erase(target);
        }
    }

    void releaseSavepoint(const std::string& name) {
        requireActive();

        if (!savepoints.erase(name)) {
            throw TransactionStateError(
                "savepoint does not exist"
            );
        }
    }

    void deposit(int id, long long amountCents) {
        Account& target = account(id);

        if (amountCents <= 0) {
            throw ConstraintViolation(
                "deposit must be positive"
            );
        }

        target.balanceCents += amountCents;

        audit(
            "DEPOSIT",
            "account=" + std::to_string(id) +
            ", cents=" + std::to_string(amountCents)
        );
    }

    void withdraw(int id, long long amountCents) {
        Account& source = account(id);

        if (amountCents <= 0) {
            throw ConstraintViolation(
                "withdrawal must be positive"
            );
        }

        if (source.balanceCents < amountCents) {
            throw ConstraintViolation(
                "insufficient funds"
            );
        }

        source.balanceCents -= amountCents;

        audit(
            "WITHDRAW",
            "account=" + std::to_string(id) +
            ", cents=" + std::to_string(amountCents)
        );
    }

    void transfer(
        int sourceId,
        int targetId,
        long long amountCents
    ) {
        requireActive();

        if (sourceId == targetId) {
            throw ConstraintViolation(
                "source and target must differ"
            );
        }

        withdraw(sourceId, amountCents);
        deposit(targetId, amountCents);

        audit(
            "TRANSFER",
            "source=" + std::to_string(sourceId) +
            ", target=" + std::to_string(targetId) +
            ", cents=" + std::to_string(amountCents)
        );
    }

    void commit() {
        requireActive();

        /*
         * This is an optimistic concurrency check. PostgreSQL normally
         * provides stronger transactional guarantees through MVCC and
         * isolation levels. The simulation explicitly detects a changed
         * database version before publishing its working state.
         */
        if (database.version != initialVersion) {
            state = TransactionState::RolledBack;

            throw SerializationConflict(
                "database changed during transaction"
            );
        }

        for (auto& [id, account] : workingAccounts) {
            auto original = database.accounts.find(id);

            if (
                original != database.accounts.end() &&
                account.balanceCents !=
                    original->second.balanceCents
            ) {
                account.version =
                    original->second.version + 1;
            }
        }

        database.accounts = workingAccounts;
        database.auditLog = workingAudit;
        ++database.version;

        state = TransactionState::Committed;
    }

    void rollback() {
        requireActive();

        workingAccounts = database.accounts;
        workingAudit = database.auditLog;
        savepoints.clear();

        state = TransactionState::RolledBack;
    }

    TransactionState getState() const {
        return state;
    }
};

class TransactionManager {
private:
    Database& database;
    int nextTransactionId = 1;

public:
    explicit TransactionManager(Database& database)
        : database(database) {}

    Transaction begin() {
        return Transaction(
            database,
            nextTransactionId++
        );
    }
};

void printAccounts(
    const Database& database,
    const std::string& title
) {
    std::cout << "\n" << title << "\n";
    std::cout << std::string(title.size(), '-') << "\n";

    for (const auto& [id, account] : database.accounts) {
        std::cout
            << std::setw(2) << id << " "
            << std::left << std::setw(10)
            << account.owner
            << " balance="
            << std::right << std::setw(8)
            << std::fixed << std::setprecision(2)
            << account.balanceCents / 100.0
            << " version="
            << account.version
            << "\n";
    }
}

int main() {
    try {
        Database database;

        database.addAccount(1, "Alice", 150000);
        database.addAccount(2, "Bob", 90000);
        database.addAccount(3, "Carol", 30000);

        TransactionManager manager(database);

        printAccounts(database, "Initial state");

        {
            auto transaction = manager.begin();

            transaction.deposit(1, 20000);
            transaction.commit();
        }

        printAccounts(database, "After COMMIT");

        {
            auto transaction = manager.begin();

            try {
                transaction.withdraw(2, 1000000);
                transaction.commit();
            } catch (const ConstraintViolation& error) {
                std::cout
                    << "\nExpected failure: "
                    << error.what()
                    << "\n";

                transaction.rollback();
            }
        }

        printAccounts(database, "After ROLLBACK");

        {
            auto transaction = manager.begin();

            transaction.deposit(1, 5000);
            transaction.beginSavepoint(
                "before_risky_operation"
            );

            try {
                transaction.withdraw(2, 500000);
            } catch (const ConstraintViolation& error) {
                std::cout
                    << "\nSavepoint recovery: "
                    << error.what()
                    << "\n";

                transaction.rollbackToSavepoint(
                    "before_risky_operation"
                );
            }

            transaction.deposit(2, 2500);
            transaction.releaseSavepoint(
                "before_risky_operation"
            );

            transaction.commit();
        }

        printAccounts(
            database,
            "After SAVEPOINT recovery"
        );

        {
            auto transaction = manager.begin();

            transaction.transfer(
                1,
                3,
                12500
            );

            transaction.commit();
        }

        printAccounts(
            database,
            "After atomic transfer"
        );

        {
            auto first = manager.begin();
            auto second = manager.begin();

            first.deposit(1, 1000);
            first.commit();

            try {
                second.deposit(2, 1000);
                second.commit();
            } catch (const SerializationConflict& error) {
                std::cout
                    << "\nConcurrency conflict: "
                    << error.what()
                    << "\n";
            }
        }

        printAccounts(
            database,
            "After optimistic conflict detection"
        );

        assert(
            database.accounts.at(1).balanceCents == 176500
        );
        assert(
            database.accounts.at(2).balanceCents == 92500
        );
        assert(
            database.accounts.at(3).balanceCents == 42500
        );

        std::cout << "\nAudit log\n";
        std::cout << "---------\n";

        for (const auto& event : database.auditLog) {
            std::cout
                << "tx=" << event.transactionId
                << " "
                << std::setw(10)
                << std::left
                << event.action
                << " "
                << event.details
                << "\n";
        }

    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << "\n";

        return 1;
    }

    return 0;
}
