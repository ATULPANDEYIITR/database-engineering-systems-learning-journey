#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * Dirty Reads: Repository-independent transaction governance engine.
 *
 * Implements:
 * - Transaction write buffers.
 * - Isolation-level evaluation.
 * - Dirty-read detection.
 * - Commit and rollback.
 * - Snapshot visibility.
 * - Atomic validation before commit.
 * - Transaction lifecycle enforcement.
 *
 * C++17, standard library only.
 */

enum class IsolationLevel {
    ReadUncommitted,
    ReadCommitted,
    RepeatableRead
};

enum class TransactionState {
    Active,
    Committed,
    RolledBack
};

std::string toString(IsolationLevel level) {
    switch (level) {
        case IsolationLevel::ReadUncommitted:
            return "READ UNCOMMITTED";
        case IsolationLevel::ReadCommitted:
            return "READ COMMITTED";
        case IsolationLevel::RepeatableRead:
            return "REPEATABLE READ";
    }

    throw std::logic_error("Unknown isolation level.");
}

std::string toString(TransactionState state) {
    switch (state) {
        case TransactionState::Active:
            return "ACTIVE";
        case TransactionState::Committed:
            return "COMMITTED";
        case TransactionState::RolledBack:
            return "ROLLED BACK";
    }

    throw std::logic_error("Unknown transaction state.");
}

struct Account {
    int id;
    std::string owner;
    double balance;
    std::uint64_t version;
};

struct ReadObservation {
    int accountId;
    double value;
    int writerId;
    bool uncommitted;
};

struct Transaction {
    int id;
    IsolationLevel isolation;
    TransactionState state = TransactionState::Active;

    std::map<int, double> writes;
    std::map<int, double> snapshot;
    std::vector<ReadObservation> reads;

    std::uint64_t snapshotVersion = 0;
};

struct DirtyReadFinding {
    int readerId;
    int writerId;
    int accountId;
    double observedValue;
};

class TransactionEngine {
private:
    std::map<int, Account> accounts;
    std::map<int, Transaction> transactions;

    int nextTransactionId = 1;
    std::uint64_t globalVersion = 0;

    void requireActive(const Transaction& transaction) const {
        if (transaction.state != TransactionState::Active) {
            throw std::logic_error(
                "Transaction is not active."
            );
        }
    }

    void requireAccount(int accountId) const {
        if (accounts.find(accountId) == accounts.end()) {
            throw std::out_of_range("Account does not exist.");
        }
    }

    Transaction& getTransaction(int id) {
        auto it = transactions.find(id);

        if (it == transactions.end()) {
            throw std::out_of_range("Transaction does not exist.");
        }

        return it->second;
    }

public:
    void addAccount(
        int id,
        const std::string& owner,
        double balance
    ) {
        if (id <= 0 || owner.empty()) {
            throw std::invalid_argument("Invalid account details.");
        }

        if (!std::isfinite(balance) || balance < 0) {
            throw std::invalid_argument("Invalid initial balance.");
        }

        if (accounts.find(id) != accounts.end()) {
            throw std::invalid_argument("Duplicate account.");
        }

        accounts.emplace(
            id,
            Account{id, owner, balance, ++globalVersion}
        );
    }

    Transaction& begin(IsolationLevel isolation) {
        Transaction transaction;
        transaction.id = nextTransactionId++;
        transaction.isolation = isolation;
        transaction.snapshotVersion = globalVersion;

        if (isolation == IsolationLevel::RepeatableRead) {
            for (const auto& [id, account] : accounts) {
                transaction.snapshot[id] = account.balance;
            }
        }

        auto [it, inserted] = transactions.emplace(
            transaction.id,
            std::move(transaction)
        );

        if (!inserted) {
            throw std::logic_error("Transaction ID collision.");
        }

        std::cout << "BEGIN T" << it->first
                  << " [" << toString(isolation) << "]\n";

        return it->second;
    }

    void write(int transactionId, int accountId, double balance) {
        Transaction& transaction = getTransaction(transactionId);

        requireActive(transaction);
        requireAccount(accountId);

        if (!std::isfinite(balance) || balance < 0) {
            throw std::invalid_argument("Invalid account balance.");
        }

        transaction.writes[accountId] = balance;

        std::cout << "T" << transactionId
                  << " staged " << balance
                  << " for account " << accountId << '\n';
    }

    double read(int transactionId, int accountId) {
        Transaction& reader = getTransaction(transactionId);

        requireActive(reader);
        requireAccount(accountId);

        double value = 0.0;
        int writerId = -1;
        bool uncommitted = false;

        auto ownWrite = reader.writes.find(accountId);

        if (ownWrite != reader.writes.end()) {
            value = ownWrite->second;

        } else if (
            reader.isolation == IsolationLevel::ReadUncommitted
        ) {
            value = accounts.at(accountId).balance;

            // Search active transactions for an uncommitted write.
            for (const auto& [id, transaction] : transactions) {
                if (
                    id != transactionId &&
                    transaction.state == TransactionState::Active
                ) {
                    auto pending = transaction.writes.find(accountId);

                    if (pending != transaction.writes.end()) {
                        value = pending->second;
                        writerId = id;
                        uncommitted = true;
                        break;
                    }
                }
            }

        } else if (
            reader.isolation == IsolationLevel::RepeatableRead
        ) {
            value = reader.snapshot.at(accountId);

        } else {
            value = accounts.at(accountId).balance;
        }

        reader.reads.push_back({
            accountId,
            value,
            writerId,
            uncommitted
        });

        std::cout << "T" << transactionId
                  << " READ account " << accountId
                  << " = " << value;

        if (uncommitted) {
            std::cout << " [UNCOMMITTED FROM T" << writerId << "]";
        } else {
            std::cout << " [COMMITTED OR OWN WRITE]";
        }

        std::cout << '\n';

        return value;
    }

    void commit(int transactionId) {
        Transaction& transaction = getTransaction(transactionId);

        requireActive(transaction);

        // Validate the complete write set before changing committed data.
        for (const auto& [accountId, balance] : transaction.writes) {
            requireAccount(accountId);

            if (!std::isfinite(balance) || balance < 0) {
                throw std::invalid_argument(
                    "Commit contains invalid balance."
                );
            }

            if (
                transaction.isolation == IsolationLevel::RepeatableRead &&
                accounts.at(accountId).version >
                    transaction.snapshotVersion
            ) {
                throw std::runtime_error(
                    "Concurrent update conflict."
                );
            }
        }

        for (const auto& [accountId, balance] : transaction.writes) {
            Account& account = accounts.at(accountId);
            account.balance = balance;
            account.version = ++globalVersion;
        }

        transaction.state = TransactionState::Committed;

        std::cout << "COMMIT T" << transactionId << '\n';
    }

    void rollback(int transactionId) {
        Transaction& transaction = getTransaction(transactionId);

        requireActive(transaction);

        transaction.writes.clear();
        transaction.state = TransactionState::RolledBack;

        std::cout << "ROLLBACK T" << transactionId << '\n';
    }

    double committedBalance(int accountId) const {
        auto it = accounts.find(accountId);

        if (it == accounts.end()) {
            throw std::out_of_range("Account does not exist.");
        }

        return it->second.balance;
    }

    std::vector<DirtyReadFinding> detectDirtyReads() const {
        std::vector<DirtyReadFinding> findings;

        for (const auto& [readerId, reader] : transactions) {
            for (const auto& observation : reader.reads) {
                if (!observation.uncommitted) {
                    continue;
                }

                auto writer = transactions.find(
                    observation.writerId
                );

                if (
                    writer != transactions.end() &&
                    writer->second.state == TransactionState::RolledBack
                ) {
                    findings.push_back({
                        readerId,
                        observation.writerId,
                        observation.accountId,
                        observation.value
                    });
                }
            }
        }

        return findings;
    }

    void report() const {
        std::cout << "\nTRANSACTION REPORT\n";

        for (const auto& [id, transaction] : transactions) {
            std::cout << "T" << id << ": "
                      << toString(transaction.state)
                      << ", isolation="
                      << toString(transaction.isolation)
                      << ", pending_writes="
                      << transaction.writes.size()
                      << '\n';
        }

        std::cout << "\nDIRTY READ FINDINGS\n";

        auto findings = detectDirtyReads();

        if (findings.empty()) {
            std::cout << "No confirmed dirty reads.\n";
        }

        for (const auto& finding : findings) {
            std::cout
                << "Reader T" << finding.readerId
                << " observed account " << finding.accountId
                << " value " << finding.observedValue
                << " from writer T" << finding.writerId
                << ", which rolled back.\n";
        }
    }
};

void demonstrateDirtyRead() {
    std::cout << "\n=== DIRTY READ ===\n";

    TransactionEngine engine;

    engine.addAccount(101, "Alice", 1000.0);

    Transaction& writer = engine.begin(
        IsolationLevel::ReadUncommitted
    );

    Transaction& reader = engine.begin(
        IsolationLevel::ReadUncommitted
    );

    engine.write(writer.id, 101, 400.0);

    engine.read(reader.id, 101);

    engine.rollback(writer.id);

    std::cout << "Committed balance after rollback: "
              << engine.committedBalance(101)
              << '\n';

    engine.report();
}

void demonstrateReadCommitted() {
    std::cout << "\n=== READ COMMITTED ===\n";

    TransactionEngine engine;
    engine.addAccount(102, "Bob", 2000.0);

    Transaction& writer = engine.begin(
        IsolationLevel::ReadUncommitted
    );

    Transaction& reader = engine.begin(
        IsolationLevel::ReadCommitted
    );

    engine.write(writer.id, 102, 700.0);

    double observed = engine.read(reader.id, 102);

    if (observed != 2000.0) {
        throw std::runtime_error("Dirty read prevention failed.");
    }

    engine.rollback(writer.id);

    std::cout << "Reader observed committed value: "
              << observed << '\n';
}

void demonstrateRepeatableRead() {
    std::cout << "\n=== REPEATABLE READ ===\n";

    TransactionEngine engine;
    engine.addAccount(103, "Carol", 3000.0);

    Transaction& reader = engine.begin(
        IsolationLevel::RepeatableRead
    );

    Transaction& writer = engine.begin(
        IsolationLevel::ReadCommitted
    );

    double first = engine.read(reader.id, 103);

    engine.write(writer.id, 103, 2500.0);
    engine.commit(writer.id);

    double second = engine.read(reader.id, 103);

    std::cout << "First read: " << first << '\n';
    std::cout << "Second read: " << second << '\n';
    std::cout << "Current committed value: "
              << engine.committedBalance(103) << '\n';

    if (first != second) {
        throw std::runtime_error("Snapshot consistency failed.");
    }
}

void demonstrateCommitVisibility() {
    std::cout << "\n=== COMMIT VISIBILITY ===\n";

    TransactionEngine engine;
    engine.addAccount(104, "David", 5000.0);

    Transaction& writer = engine.begin(
        IsolationLevel::ReadCommitted
    );

    Transaction& reader = engine.begin(
        IsolationLevel::ReadCommitted
    );

    engine.write(writer.id, 104, 4500.0);

    double before = engine.read(reader.id, 104);

    engine.commit(writer.id);

    double after = engine.read(reader.id, 104);

    std::cout << "Before commit: " << before << '\n';
    std::cout << "After commit: " << after << '\n';

    if (before != 5000.0 || after != 4500.0) {
        throw std::runtime_error("Commit visibility failed.");
    }
}

void demonstrateValidation() {
    std::cout << "\n=== VALIDATION ===\n";

    TransactionEngine engine;
    engine.addAccount(105, "Eve", 100.0);

    Transaction& transaction = engine.begin(
        IsolationLevel::ReadCommitted
    );

    try {
        engine.write(transaction.id, 105, -10.0);
        throw std::runtime_error("Negative balance was accepted.");
    } catch (const std::invalid_argument& error) {
        std::cout << "Correctly rejected invalid write: "
                  << error.what() << '\n';
    }

    engine.rollback(transaction.id);

    try {
        engine.commit(transaction.id);
        throw std::runtime_error("Inactive transaction was accepted.");
    } catch (const std::logic_error& error) {
        std::cout << "Correctly rejected inactive transaction: "
                  << error.what() << '\n';
    }
}

int main() {
    try {
        std::cout << std::fixed << std::setprecision(2);

        demonstrateDirtyRead();
        demonstrateReadCommitted();
        demonstrateRepeatableRead();
        demonstrateCommitVisibility();
        demonstrateValidation();

        std::cout << "\nAll scenarios completed successfully.\n";

    } catch (const std::exception& error) {
        std::cerr << "Execution error: "
                  << error.what() << '\n';

        return 1;
    }

    return 0;
}
