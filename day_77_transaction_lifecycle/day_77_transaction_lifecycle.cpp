#include <algorithm>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

/*
 * Transaction Lifecycle and Repository-Independent Governance Engine
 *
 * Financial transaction model:
 * - Explicit transaction state machine
 * - Atomic commit
 * - Full rollback
 * - Savepoints
 * - Account version checking
 * - Concurrent modification detection
 * - Transaction history
 *
 * Compile:
 *   g++ -std=c++17 -O2 -Wall -Wextra -pedantic transaction.cpp -o transaction
 *
 * Run:
 *   ./transaction
 */

enum class TransactionState {
    NEW,
    ACTIVE,
    COMMITTING,
    COMMITTED,
    ROLLING_BACK,
    ROLLED_BACK,
    FAILED
};

std::string stateName(TransactionState state) {
    switch (state) {
        case TransactionState::NEW: return "NEW";
        case TransactionState::ACTIVE: return "ACTIVE";
        case TransactionState::COMMITTING: return "COMMITTING";
        case TransactionState::COMMITTED: return "COMMITTED";
        case TransactionState::ROLLING_BACK: return "ROLLING_BACK";
        case TransactionState::ROLLED_BACK: return "ROLLED_BACK";
        case TransactionState::FAILED: return "FAILED";
    }

    throw std::logic_error("Unknown transaction state.");
}

class TransactionError : public std::runtime_error {
public:
    explicit TransactionError(const std::string& message)
        : std::runtime_error(message) {}
};

class ValidationError : public TransactionError {
public:
    using TransactionError::TransactionError;
};

class InsufficientFundsError : public TransactionError {
public:
    using TransactionError::TransactionError;
};

class ConcurrencyError : public TransactionError {
public:
    using TransactionError::TransactionError;
};

class InvalidStateError : public TransactionError {
public:
    using TransactionError::TransactionError;
};

struct Account {
    std::string id;
    std::string owner;
    std::int64_t balanceCents;
    std::uint64_t version = 0;
};

struct TransactionEvent {
    TransactionState previous;
    TransactionState current;
    std::string description;
};

struct Operation {
    std::string type;
    std::string source;
    std::string destination;
    std::int64_t amountCents;
};

struct Savepoint {
    std::map<std::string, Account> accounts;
    std::size_t operationCount;
};

class Transaction {
private:
    static bool isAllowed(
        TransactionState current,
        TransactionState next
    ) {
        switch (current) {
            case TransactionState::NEW:
                return next == TransactionState::ACTIVE;

            case TransactionState::ACTIVE:
                return next == TransactionState::COMMITTING ||
                       next == TransactionState::ROLLING_BACK ||
                       next == TransactionState::FAILED;

            case TransactionState::COMMITTING:
                return next == TransactionState::COMMITTED ||
                       next == TransactionState::FAILED;

            case TransactionState::ROLLING_BACK:
                return next == TransactionState::ROLLED_BACK ||
                       next == TransactionState::FAILED;

            case TransactionState::FAILED:
                return next == TransactionState::ROLLING_BACK;

            case TransactionState::COMMITTED:
            case TransactionState::ROLLED_BACK:
                return false;
        }

        return false;
    }

public:
    std::string id;
    TransactionState state = TransactionState::NEW;

    std::map<std::string, Account> workingAccounts;
    std::map<std::string, std::uint64_t> originalVersions;

    std::vector<Operation> operations;
    std::vector<TransactionEvent> history;

    std::map<std::string, Savepoint> savepoints;

    explicit Transaction(
        const std::map<std::string, Account>& snapshot,
        const std::string& transactionId
    ) : id(transactionId), workingAccounts(snapshot) {

        for (const auto& [accountId, account] : snapshot) {
            originalVersions[accountId] = account.version;
        }

        transition(
            TransactionState::ACTIVE,
            "Transaction started."
        );
    }

    void transition(
        TransactionState next,
        const std::string& description
    ) {
        if (!isAllowed(state, next)) {
            throw InvalidStateError(
                "Invalid transition: " +
                stateName(state) + " -> " + stateName(next)
            );
        }

        history.push_back({state, next, description});

        std::cout
            << "[" << id << "] "
            << stateName(state) << " -> "
            << stateName(next) << ": "
            << description << "\n";

        state = next;
    }

    void requireActive() const {
        if (state != TransactionState::ACTIVE) {
            throw InvalidStateError("Transaction is not active.");
        }
    }

    Account& getAccount(const std::string& id) {
        auto iterator = workingAccounts.find(id);

        if (iterator == workingAccounts.end()) {
            throw ValidationError("Account does not exist: " + id);
        }

        return iterator->second;
    }

    void transfer(
        const std::string& sourceId,
        const std::string& destinationId,
        std::int64_t amountCents
    ) {
        requireActive();

        if (sourceId == destinationId) {
            throw ValidationError("Accounts must be different.");
        }

        if (amountCents <= 0) {
            throw ValidationError("Transfer must be positive.");
        }

        Account& source = getAccount(sourceId);
        Account& destination = getAccount(destinationId);

        if (source.balanceCents < amountCents) {
            throw InsufficientFundsError("Insufficient funds.");
        }

        if (
            destination.balanceCents >
            INT64_MAX - amountCents
        ) {
            throw ValidationError("Destination balance overflow.");
        }

        source.balanceCents -= amountCents;
        destination.balanceCents += amountCents;

        operations.push_back({
            "TRANSFER",
            sourceId,
            destinationId,
            amountCents
        });
    }

    void deposit(
        const std::string& accountId,
        std::int64_t amountCents
    ) {
        requireActive();

        if (amountCents <= 0) {
            throw ValidationError("Deposit must be positive.");
        }

        Account& account = getAccount(accountId);

        if (account.balanceCents > INT64_MAX - amountCents) {
            throw ValidationError("Balance overflow.");
        }

        account.balanceCents += amountCents;

        operations.push_back({
            "DEPOSIT",
            accountId,
            "",
            amountCents
        });
    }

    void withdraw(
        const std::string& accountId,
        std::int64_t amountCents
    ) {
        requireActive();

        if (amountCents <= 0) {
            throw ValidationError("Withdrawal must be positive.");
        }

        Account& account = getAccount(accountId);

        if (account.balanceCents < amountCents) {
            throw InsufficientFundsError("Insufficient funds.");
        }

        account.balanceCents -= amountCents;

        operations.push_back({
            "WITHDRAW",
            accountId,
            "",
            amountCents
        });
    }

    void createSavepoint(const std::string& name) {
        requireActive();

        if (name.empty() || savepoints.count(name)) {
            throw ValidationError("Invalid or duplicate savepoint.");
        }

        savepoints.emplace(
            name,
            Savepoint{workingAccounts, operations.size()}
        );

        std::cout << "Savepoint created: " << name << "\n";
    }

    void rollbackToSavepoint(const std::string& name) {
        requireActive();

        auto iterator = savepoints.find(name);

        if (iterator == savepoints.end()) {
            throw ValidationError("Savepoint does not exist.");
        }

        workingAccounts = iterator->second.accounts;
        operations.resize(iterator->second.operationCount);

        auto later = std::next(iterator);
        savepoints.erase(later, savepoints.end());

        std::cout << "Restored savepoint: " << name << "\n";
    }
};

class Database {
private:
    std::map<std::string, Account> accounts;
    mutable std::mutex mutex;
    std::uint64_t nextTransactionId = 1;

public:
    void addAccount(const Account& account) {
        std::lock_guard<std::mutex> guard(mutex);

        if (
            account.id.empty() ||
            account.owner.empty() ||
            account.balanceCents < 0
        ) {
            throw ValidationError("Invalid account.");
        }

        if (accounts.count(account.id)) {
            throw ValidationError("Duplicate account.");
        }

        accounts.emplace(account.id, account);
    }

    Transaction begin() {
        std::lock_guard<std::mutex> guard(mutex);

        std::ostringstream id;
        id << "TX-" << std::setw(6)
           << std::setfill('0')
           << nextTransactionId++;

        return Transaction(accounts, id.str());
    }

    void commit(Transaction& transaction) {
        transaction.requireActive();

        transaction.transition(
            TransactionState::COMMITTING,
            "Commit validation started."
        );

        try {
            std::lock_guard<std::mutex> guard(mutex);

            // Validate every account before modifying the database.
            for (const auto& [id, staged] : transaction.workingAccounts) {
                auto current = accounts.find(id);

                if (current == accounts.end()) {
                    throw ConcurrencyError("Account was removed: " + id);
                }

                if (
                    current->second.version !=
                    transaction.originalVersions.at(id)
                ) {
                    throw ConcurrencyError(
                        "Concurrent update detected: " + id
                    );
                }

                if (staged.balanceCents < 0) {
                    throw ValidationError("Negative balance detected.");
                }
            }

            // Build a complete replacement before publishing it.
            auto replacement = accounts;

            for (const auto& [id, staged] : transaction.workingAccounts) {
                auto& current = replacement.at(id);

                if (current.balanceCents != staged.balanceCents) {
                    current.balanceCents = staged.balanceCents;
                    ++current.version;
                }
            }

            // A map swap publishes the fully validated database state.
            accounts.swap(replacement);

            transaction.transition(
                TransactionState::COMMITTED,
                "All staged changes published."
            );

        } catch (...) {
            transaction.transition(
                TransactionState::FAILED,
                "Commit validation or publication failed."
            );

            throw;
        }
    }

    void rollback(Transaction& transaction) {
        if (
            transaction.state != TransactionState::ACTIVE &&
            transaction.state != TransactionState::FAILED
        ) {
            throw InvalidStateError("Transaction cannot be rolled back.");
        }

        transaction.transition(
            TransactionState::ROLLING_BACK,
            "Discarding transaction snapshot."
        );

        transaction.operations.clear();
        transaction.savepoints.clear();

        transaction.workingAccounts.clear();

        transaction.transition(
            TransactionState::ROLLED_BACK,
            "Rollback completed."
        );
    }

    void printAccounts() const {
        std::lock_guard<std::mutex> guard(mutex);

        std::cout << "\nACCOUNT REPORT\n";
        std::cout
            << std::left
            << std::setw(15) << "ACCOUNT"
            << std::setw(15) << "OWNER"
            << std::setw(15) << "BALANCE"
            << "VERSION\n";

        for (const auto& [id, account] : accounts) {
            const double balance =
                static_cast<double>(account.balanceCents) / 100.0;

            std::cout
                << std::left
                << std::setw(15) << id
                << std::setw(15) << account.owner
                << std::fixed
                << std::setprecision(2)
                << std::setw(15) << balance
                << account.version << "\n";
        }
    }
};

void runDemonstration() {
    Database database;

    database.addAccount({
        "ACC-001", "Alice", 1000000, 0
    });

    database.addAccount({
        "ACC-002", "Bob", 500000, 0
    });

    database.addAccount({
        "ACC-003", "Charlie", 250000, 0
    });

    std::cout << "\nSCENARIO 1: COMMIT\n";

    Transaction first = database.begin();

    first.transfer("ACC-001", "ACC-002", 150000);
    first.deposit("ACC-003", 25000);

    database.commit(first);

    database.printAccounts();

    std::cout << "\nSCENARIO 2: ROLLBACK\n";

    Transaction second = database.begin();

    second.withdraw("ACC-002", 50000);

    database.rollback(second);

    database.printAccounts();

    std::cout << "\nSCENARIO 3: SAVEPOINT\n";

    Transaction third = database.begin();

    third.deposit("ACC-001", 10000);
    third.createSavepoint("BEFORE_WITHDRAWAL");

    third.withdraw("ACC-002", 25000);

    third.rollbackToSavepoint("BEFORE_WITHDRAWAL");

    database.commit(third);

    database.printAccounts();

    std::cout << "\nSCENARIO 4: INSUFFICIENT FUNDS\n";

    Transaction fourth = database.begin();

    try {
        fourth.withdraw("ACC-002", 999999999);
        database.commit(fourth);
    } catch (const TransactionError& error) {
        std::cout << "Expected error: " << error.what() << "\n";

        if (
            fourth.state == TransactionState::ACTIVE ||
            fourth.state == TransactionState::FAILED
        ) {
            database.rollback(fourth);
        }
    }

    std::cout << "\nSCENARIO 5: CONCURRENT MODIFICATION\n";

    Transaction fifth = database.begin();
    Transaction sixth = database.begin();

    fifth.deposit("ACC-001", 10000);
    sixth.deposit("ACC-001", 20000);

    database.commit(fifth);

    try {
        database.commit(sixth);
    } catch (const ConcurrencyError& error) {
        std::cout << "Expected conflict: " << error.what() << "\n";
        database.rollback(sixth);
    }

    database.printAccounts();

    std::cout << "\nALL SCENARIOS COMPLETED\n";
}

int main() {
    try {
        runDemonstration();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << "\n";
        return 1;
    }
}
