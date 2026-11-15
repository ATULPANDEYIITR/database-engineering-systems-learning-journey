#include <algorithm>
#include <cstdint>
#include <exception>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

/*
 * ACID Fundamentals: C++17 Transaction and Governance Engine
 *
 * Models an account-management database with:
 * - Atomic multi-account transfers.
 * - Consistency invariants.
 * - Optimistic concurrency validation.
 * - Serializable commit coordination.
 * - Durable write-ahead transaction records.
 * - Recovery of committed operations.
 * - Idempotency and transaction state management.
 *
 * Uses only the C++17 standard library.
 */

using AccountId = std::uint64_t;
using TransactionId = std::uint64_t;
using Money = std::int64_t; // Integer cents.

enum class TransactionState {
    Active,
    Committed,
    RolledBack,
    Conflict
};

enum class LogType {
    Begin,
    Commit,
    Rollback
};

struct Account {
    AccountId id;
    std::string owner;
    Money balance;
    std::uint64_t version;
};

struct AccountSnapshot {
    AccountId id;
    Money balance;
    std::uint64_t version;
};

struct TransferOperation {
    AccountId source;
    AccountId destination;
    Money amount;
};

struct LogRecord {
    LogType type;
    TransactionId transactionId;
    std::vector<TransferOperation> operations;
};

class TransactionError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class InsufficientFunds : public TransactionError {
public:
    using TransactionError::TransactionError;
};

class SerializationConflict : public TransactionError {
public:
    using TransactionError::TransactionError;
};

class ConstraintViolation : public TransactionError {
public:
    using TransactionError::TransactionError;
};

class Transaction {
private:
    TransactionId id_;
    TransactionState state_;
    std::map<AccountId, AccountSnapshot> snapshot_;
    std::map<AccountId, Account> staged_;
    std::vector<TransferOperation> operations_;

public:
    Transaction(
        TransactionId id,
        const std::map<AccountId, Account>& accounts
    ) : id_(id), state_(TransactionState::Active) {
        for (const auto& [accountId, account] : accounts) {
            snapshot_.emplace(
                accountId,
                AccountSnapshot{
                    accountId,
                    account.balance,
                    account.version
                }
            );
        }
    }

    TransactionId id() const {
        return id_;
    }

    TransactionState state() const {
        return state_;
    }

    void setState(TransactionState state) {
        state_ = state;
    }

    const auto& snapshot() const {
        return snapshot_;
    }

    const auto& staged() const {
        return staged_;
    }

    const auto& operations() const {
        return operations_;
    }

    void ensureActive() const {
        if (state_ != TransactionState::Active) {
            throw TransactionError(
                "Transaction is not active."
            );
        }
    }

    Account read(AccountId id) const {
        ensureActive();

        auto staged = staged_.find(id);

        if (staged != staged_.end()) {
            return staged->second;
        }

        auto snapshot = snapshot_.find(id);

        if (snapshot == snapshot_.end()) {
            throw ConstraintViolation("Account does not exist.");
        }

        return Account{
            id,
            "",
            snapshot->second.balance,
            snapshot->second.version
        };
    }

    void transfer(
        AccountId source,
        AccountId destination,
        Money amount
    ) {
        ensureActive();

        if (source == destination) {
            throw ConstraintViolation(
                "Source and destination must differ."
            );
        }

        if (amount <= 0) {
            throw ConstraintViolation(
                "Transfer amount must be positive."
            );
        }

        Account sourceAccount = read(source);
        Account destinationAccount = read(destination);

        if (sourceAccount.balance < amount) {
            throw InsufficientFunds(
                "Insufficient source balance."
            );
        }

        if (destinationAccount.balance >
            INT64_MAX - amount) {
            throw ConstraintViolation(
                "Destination balance overflow."
            );
        }

        sourceAccount.balance -= amount;
        destinationAccount.balance += amount;

        staged_[source] = sourceAccount;
        staged_[destination] = destinationAccount;

        operations_.push_back({
            source,
            destination,
            amount
        });
    }

    void rollback() {
        ensureActive();
        staged_.clear();
        operations_.clear();
        state_ = TransactionState::RolledBack;
    }
};

class WriteAheadLog {
private:
    std::string filename_;

public:
    explicit WriteAheadLog(std::string filename)
        : filename_(std::move(filename)) {}

    void append(const LogRecord& record) {
        std::ofstream output(
            filename_,
            std::ios::app
        );

        if (!output) {
            throw TransactionError(
                "Cannot open transaction log."
            );
        }

        output << static_cast<int>(record.type)
               << ' ' << record.transactionId
               << ' ' << record.operations.size();

        for (const auto& operation : record.operations) {
            output << ' '
                   << operation.source << ' '
                   << operation.destination << ' '
                   << operation.amount;
        }

        output << '\n';
        output.flush();

        if (!output) {
            throw TransactionError(
                "Failed to write transaction log."
            );
        }
    }

    std::vector<LogRecord> readAll() const {
        std::vector<LogRecord> records;
        std::ifstream input(filename_);

        if (!input) {
            return records;
        }

        int type;
        TransactionId id;
        std::size_t count;

        while (input >> type >> id >> count) {
            if (type < 0 || type > 2 || count > 100000) {
                throw TransactionError(
                    "Invalid transaction log record."
                );
            }

            LogRecord record{
                static_cast<LogType>(type),
                id,
                {}
            };

            for (std::size_t i = 0; i < count; ++i) {
                TransferOperation operation{};

                if (!(input
                    >> operation.source
                    >> operation.destination
                    >> operation.amount)) {
                    throw TransactionError(
                        "Corrupt transaction log."
                    );
                }

                record.operations.push_back(operation);
            }

            records.push_back(std::move(record));
        }

        if (!input.eof()) {
            throw TransactionError(
                "Malformed transaction log."
            );
        }

        return records;
    }
};

class Database {
private:
    std::map<AccountId, Account> accounts_;
    std::map<TransactionId, TransactionState> states_;
    std::set<TransactionId> committed_;
    std::set<std::string> idempotencyKeys_;

    TransactionId nextTransactionId_ = 1;
    AccountId nextAccountId_ = 1;

    WriteAheadLog log_;

    static void validateAccount(const Account& account) {
        if (account.balance < 0) {
            throw ConstraintViolation(
                "Account balance cannot be negative."
            );
        }

        if (account.owner.empty()) {
            throw ConstraintViolation(
                "Account owner is required."
            );
        }
    }

    void applyOperations(
        std::map<AccountId, Account>& target,
        const std::vector<TransferOperation>& operations
    ) {
        for (const auto& operation : operations) {
            auto source = target.find(operation.source);
            auto destination = target.find(operation.destination);

            if (source == target.end() ||
                destination == target.end()) {
                throw ConstraintViolation(
                    "Transfer references an unknown account."
                );
            }

            if (operation.amount <= 0 ||
                operation.source == operation.destination) {
                throw ConstraintViolation(
                    "Invalid transfer operation."
                );
            }

            if (source->second.balance < operation.amount) {
                throw InsufficientFunds(
                    "Recovery encountered insufficient funds."
                );
            }

            if (destination->second.balance >
                INT64_MAX - operation.amount) {
                throw ConstraintViolation(
                    "Balance overflow."
                );
            }

            source->second.balance -= operation.amount;
            destination->second.balance += operation.amount;
        }
    }

public:
    explicit Database(std::string logFile)
        : log_(std::move(logFile)) {}

    AccountId createAccount(
        const std::string& owner,
        Money initialBalance
    ) {
        Account account{
            nextAccountId_++,
            owner,
            initialBalance,
            0
        };

        validateAccount(account);
        accounts_.emplace(account.id, account);

        return account.id;
    }

    Transaction begin() {
        Transaction transaction(
            nextTransactionId_++,
            accounts_
        );

        states_[transaction.id()] = TransactionState::Active;

        log_.append({
            LogType::Begin,
            transaction.id(),
            {}
        });

        return transaction;
    }

    void commit(
        Transaction& transaction,
        const std::string& idempotencyKey = ""
    ) {
        transaction.ensureActive();

        if (!idempotencyKey.empty() &&
            idempotencyKeys_.count(idempotencyKey)) {
            throw TransactionError(
                "Duplicate idempotency key."
            );
        }

        // Validate every account read by the transaction.
        for (const auto& [id, snapshot] :
            transaction.snapshot()) {

            auto current = accounts_.find(id);

            if (current == accounts_.end() ||
                current->second.version != snapshot.version) {
                transaction.setState(TransactionState::Conflict);
                states_[transaction.id()] = TransactionState::Conflict;

                throw SerializationConflict(
                    "Concurrent transaction changed an account."
                );
            }
        }

        // Work on a private copy so failed operations cannot partially
        // modify the committed database state.
        auto candidate = accounts_;

        for (const auto& [id, staged] : transaction.staged()) {
            auto found = candidate.find(id);

            if (found == candidate.end()) {
                throw ConstraintViolation("Unknown account.");
            }

            found->second.balance = staged.balance;
            found->second.version += 1;
            validateAccount(found->second);
        }

        // Persist the complete commit record before publishing state.
        // A production WAL must also use fsync and a recovery protocol.
        log_.append({
            LogType::Commit,
            transaction.id(),
            transaction.operations()
        });

        accounts_.swap(candidate);

        committed_.insert(transaction.id());

        if (!idempotencyKey.empty()) {
            idempotencyKeys_.insert(idempotencyKey);
        }

        transaction.setState(TransactionState::Committed);
        states_[transaction.id()] = TransactionState::Committed;
    }

    void rollback(Transaction& transaction) {
        transaction.rollback();

        states_[transaction.id()] =
            TransactionState::RolledBack;

        log_.append({
            LogType::Rollback,
            transaction.id(),
            {}
        });
    }

    Account getAccount(AccountId id) const {
        auto found = accounts_.find(id);

        if (found == accounts_.end()) {
            throw ConstraintViolation(
                "Account does not exist."
            );
        }

        return found->second;
    }

    Money totalBalance() const {
        Money total = 0;

        for (const auto& [id, account] : accounts_) {
            if (account.balance > INT64_MAX - total) {
                throw ConstraintViolation(
                    "Total balance overflow."
                );
            }

            total += account.balance;
        }

        return total;
    }

    void recover() {
        auto records = log_.readAll();

        std::map<TransactionId, std::vector<TransferOperation>>
            committedOperations;

        std::set<TransactionId> committedIds;

        for (const auto& record : records) {
            if (record.type == LogType::Commit) {
                committedIds.insert(record.transactionId);
                committedOperations[record.transactionId] =
                    record.operations;
            }
        }

        for (const auto& [id, operations] :
            committedOperations) {

            if (!committedIds.count(id)) {
                continue;
            }

            // In a fresh database, replay committed records in order.
            applyOperations(accounts_, operations);

            for (const auto& operation : operations) {
                accounts_.at(operation.source).version++;
                accounts_.at(operation.destination).version++;
            }

            committed_.insert(id);
        }
    }

    void printAccounts() const {
        std::cout << "\nACCOUNT STATE\n";

        for (const auto& [id, account] : accounts_) {
            std::cout
                << "ID: " << id
                << " | Owner: " << account.owner
                << " | Balance: ";

            std::cout << std::fixed << std::setprecision(2)
                      << static_cast<double>(account.balance) / 100.0;

            std::cout
                << " | Version: " << account.version
                << '\n';
        }
    }
};

int main() {
    try {
        Database database("acid_transactions.log");

        const AccountId treasury =
            database.createAccount("Treasury", 100000);

        const AccountId research =
            database.createAccount("Research", 25000);

        const Money initialTotal = database.totalBalance();

        database.printAccounts();

        std::cout << "\nATOMICITY TEST\n";

        Transaction failed = database.begin();

        try {
            failed.transfer(treasury, research, 10000);
            database.rollback(failed);
        } catch (const std::exception& error) {
            std::cout << "Failure: " << error.what() << '\n';
        }

        if (database.totalBalance() != initialTotal) {
            throw TransactionError(
                "Atomicity invariant failed."
            );
        }

        std::cout << "\nCONSISTENCY TEST\n";

        Transaction invalid = database.begin();

        try {
            invalid.transfer(treasury, research, 99999999);
        } catch (const InsufficientFunds& error) {
            std::cout << "Rejected: " << error.what() << '\n';
            database.rollback(invalid);
        }

        std::cout << "\nISOLATION TEST\n";

        Transaction first = database.begin();
        Transaction second = database.begin();

        first.transfer(treasury, research, 5000);
        second.transfer(treasury, research, 7000);

        database.commit(first, "PAYMENT-001");

        try {
            database.commit(second, "PAYMENT-002");
        } catch (const SerializationConflict& error) {
            std::cout << "Conflict detected: "
                      << error.what() << '\n';
        }

        std::cout << "\nDURABILITY TEST\n";

        Database recovered("acid_transactions.log");

        recovered.createAccount("Treasury", 100000);
        recovered.createAccount("Research", 25000);

        recovered.recover();
        recovered.printAccounts();

        std::cout << "\nFINAL BALANCE: "
                  << static_cast<double>(
                        recovered.totalBalance()
                     ) / 100.0
                  << '\n';

        std::cout << "\nACID execution completed.\n";

        return 0;

    } catch (const std::exception& error) {
        std::cerr << "FATAL: " << error.what() << '\n';
        return 1;
    }
}
