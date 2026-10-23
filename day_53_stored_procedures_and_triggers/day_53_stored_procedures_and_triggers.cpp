#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

using Money = long long; // Store currency as the smallest unit to avoid floating-point errors.

class DatabaseError : public std::runtime_error {
public:
    explicit DatabaseError(const std::string& message)
        : std::runtime_error(message) {}
};

class ConstraintViolation : public DatabaseError {
public:
    explicit ConstraintViolation(const std::string& message)
        : DatabaseError(message) {}
};

class NotFoundError : public DatabaseError {
public:
    explicit NotFoundError(const std::string& message)
        : DatabaseError(message) {}
};

enum class TransactionType {
    Credit,
    Debit
};

struct Account {
    int id;
    std::string customerName;
    Money balance;
    bool active{true};
};

struct Transaction {
    int id;
    int accountId;
    Money amount;
    TransactionType type;
};

struct AuditRecord {
    long long id;
    int accountId;
    Money oldBalance;
    Money newBalance;
    std::string action;
};

class Database {
private:
    std::map<int, Account> accounts;
    std::map<int, Transaction> transactions;
    std::vector<AuditRecord> auditLog;

    int nextTransactionId{1};
    long long nextAuditId{1};

    /*
     * These methods represent database triggers.
     * BEFORE triggers can reject a change before the row is stored.
     * AFTER triggers perform derived work after the row operation succeeds.
     */
    void beforeInsertAccount(const Account& account) const {
        if (account.id <= 0) {
            throw ConstraintViolation("Account ID must be positive");
        }

        if (account.customerName.empty()) {
            throw ConstraintViolation("Customer name cannot be empty");
        }

        if (account.balance < 0) {
            throw ConstraintViolation("Opening balance cannot be negative");
        }
    }

    void beforeUpdateAccount(
        const Account& oldAccount,
        const Account& newAccount
    ) const {
        if (newAccount.balance < 0) {
            throw ConstraintViolation("Balance cannot become negative");
        }

        if (std::llabs(newAccount.balance - oldAccount.balance) > 1000000) {
            throw ConstraintViolation(
                "Balance change exceeds the configured threshold"
            );
        }
    }

    void afterUpdateAccount(
        const Account& oldAccount,
        const Account& newAccount
    ) {
        auditLog.push_back({
            nextAuditId++,
            newAccount.id,
            oldAccount.balance,
            newAccount.balance,
            "ACCOUNT_BALANCE_UPDATE"
        });
    }

    void afterInsertTransaction(const Transaction& transaction) {
        auto iterator = accounts.find(transaction.accountId);

        if (iterator == accounts.end()) {
            throw NotFoundError("Transaction account does not exist");
        }

        Account oldAccount = iterator->second;
        Account updated = oldAccount;

        if (transaction.type == TransactionType::Credit) {
            updated.balance += transaction.amount;
        } else {
            updated.balance -= transaction.amount;
        }

        beforeUpdateAccount(oldAccount, updated);
        iterator->second = updated;
        afterUpdateAccount(oldAccount, updated);
    }

public:
    Account createAccount(
        int id,
        const std::string& customerName,
        Money openingBalance
    ) {
        if (accounts.contains(id)) {
            throw ConstraintViolation("Duplicate account ID");
        }

        Account account{id, customerName, openingBalance};
        beforeInsertAccount(account);
        accounts.emplace(id, account);

        return account;
    }

    Transaction insertTransaction(
        int accountId,
        Money amount,
        TransactionType type
    ) {
        if (!accounts.contains(accountId)) {
            throw NotFoundError("Account does not exist");
        }

        if (amount <= 0) {
            throw ConstraintViolation("Transaction amount must be positive");
        }

        Transaction transaction{
            nextTransactionId++,
            accountId,
            amount,
            type
        };

        /*
         * If the AFTER trigger fails, the transaction row is removed.
         * This approximates statement-level atomicity in the in-memory model.
         */
        transactions.emplace(transaction.id, transaction);

        try {
            afterInsertTransaction(transaction);
        } catch (...) {
            transactions.erase(transaction.id);
            throw;
        }

        return transaction;
    }

    /*
     * Procedure-style operation.
     *
     * The operation coordinates two writes and rolls back both account
     * states and transaction rows when either operation fails.
     */
    void transfer(
        int sourceId,
        int destinationId,
        Money amount
    ) {
        if (sourceId == destinationId) {
            throw ConstraintViolation(
                "Source and destination accounts must differ"
            );
        }

        if (amount <= 0) {
            throw ConstraintViolation("Transfer amount must be positive");
        }

        auto sourceIterator = accounts.find(sourceId);
        auto destinationIterator = accounts.find(destinationId);

        if (sourceIterator == accounts.end() ||
            destinationIterator == accounts.end()) {
            throw NotFoundError("Both accounts must exist");
        }

        const Account sourceSnapshot = sourceIterator->second;
        const Account destinationSnapshot = destinationIterator->second;

        const std::size_t auditSnapshot = auditLog.size();
        const int transactionSnapshot = nextTransactionId;

        try {
            if (sourceSnapshot.balance < amount) {
                throw ConstraintViolation("Insufficient funds");
            }

            insertTransaction(sourceId, amount, TransactionType::Debit);
            insertTransaction(destinationId, amount, TransactionType::Credit);
        } catch (...) {
            accounts[sourceId] = sourceSnapshot;
            accounts[destinationId] = destinationSnapshot;

            while (nextTransactionId > transactionSnapshot) {
                transactions.erase(nextTransactionId - 1);
                --nextTransactionId;
            }

            auditLog.resize(auditSnapshot);
            throw;
        }
    }

    void printAccounts() const {
        std::cout << "\nAccounts\n";

        for (const auto& [id, account] : accounts) {
            std::cout << "  " << id
                      << " | " << account.customerName
                      << " | balance=" << std::fixed
                      << std::setprecision(2)
                      << account.balance / 100.0
                      << '\n';
        }
    }

    void printAuditLog() const {
        std::cout << "\nAudit records\n";

        for (const auto& record : auditLog) {
            std::cout << "  audit=" << record.id
                      << " account=" << record.accountId
                      << " old=" << record.oldBalance / 100.0
                      << " new=" << record.newBalance / 100.0
                      << " action=" << record.action
                      << '\n';
        }
    }
};

int main() {
    try {
        Database database;

        database.createAccount(101, "Aarav Mehta", 1000000);
        database.createAccount(102, "Meera Sharma", 500000);

        database.printAccounts();

        database.insertTransaction(101, 75000, TransactionType::Credit);
        database.insertTransaction(102, 50000, TransactionType::Debit);

        database.printAccounts();

        std::cout << "\nExecuting transfer procedure\n";
        database.transfer(101, 102, 100000);

        database.printAccounts();
        database.printAuditLog();

        std::cout << "\nTesting trigger validation\n";

        try {
            database.insertTransaction(102, 100000000, TransactionType::Debit);
        } catch (const DatabaseError& error) {
            std::cout << "Expected failure: "
                      << error.what() << '\n';
        }

        std::cout << "\nTesting procedure rollback\n";

        try {
            database.transfer(102, 101, 100000000);
        } catch (const DatabaseError& error) {
            std::cout << "Expected failure: "
                      << error.what() << '\n';
        }

        database.printAccounts();
    } catch (const std::exception& error) {
        std::cerr << "Fatal database error: "
                  << error.what() << '\n';
        return 1;
    }

    return 0;
}
