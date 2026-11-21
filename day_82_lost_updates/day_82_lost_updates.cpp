#include <algorithm>
#include <atomic>
#include <cstdint>
#include <exception>
#include <iostream>
#include <limits>
#include <mutex>
#include <optional>
#include <shared_mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>

enum class Operation {
    Deposit,
    Withdraw
};

enum class WritePolicy {
    Unsafe,
    Optimistic,
    Pessimistic
};

enum class TransactionStatus {
    Committed,
    Conflict,
    Rejected
};

struct AccountSnapshot {
    int accountId;
    std::string owner;
    std::int64_t balance;
    std::uint64_t version;
};

struct TransactionResult {
    TransactionStatus status;
    std::string message;
    std::optional<AccountSnapshot> account;
};

struct AuditEntry {
    std::uint64_t transactionId;
    int accountId;
    std::int64_t oldBalance;
    std::int64_t newBalance;
    std::uint64_t oldVersion;
    std::uint64_t newVersion;
    WritePolicy policy;
    Operation operation;
};

class ValidationError : public std::runtime_error {
public:
    explicit ValidationError(const std::string& message)
        : std::runtime_error(message) {}
};

class Account {
private:
    int id_;
    std::string owner_;
    std::int64_t balance_;
    std::uint64_t version_;

public:
    Account(int id, std::string owner, std::int64_t balance)
        : id_(id),
          owner_(std::move(owner)),
          balance_(balance),
          version_(0) {

        if (id <= 0) {
            throw ValidationError("Account ID must be positive.");
        }

        if (owner_.empty()) {
            throw ValidationError("Owner cannot be empty.");
        }

        if (balance < 0) {
            throw ValidationError("Balance cannot be negative.");
        }
    }

    AccountSnapshot snapshot() const {
        return {id_, owner_, balance_, version_};
    }

    friend class Repository;
};

class Repository {
private:
    std::unordered_map<int, Account> accounts_;
    std::unordered_map<int, std::shared_ptr<std::mutex>> locks_;

    mutable std::shared_mutex stateMutex_;
    mutable std::mutex auditMutex_;

    std::vector<AuditEntry> audit_;
    std::atomic<std::uint64_t> nextTransactionId_{1};

    static void validateAmount(std::int64_t amount) {
        if (amount <= 0) {
            throw ValidationError("Amount must be positive.");
        }
    }

    static std::int64_t calculate(
        std::int64_t balance,
        std::int64_t amount,
        Operation operation
    ) {
        if (operation == Operation::Deposit) {
            if (balance > std::numeric_limits<std::int64_t>::max()
                              - amount) {
                throw ValidationError("Balance overflow.");
            }
            return balance + amount;
        }

        if (balance < amount) {
            throw ValidationError("Insufficient funds.");
        }

        return balance - amount;
    }

    void record(
        const AccountSnapshot& previous,
        const AccountSnapshot& current,
        WritePolicy policy,
        Operation operation
    ) {
        AuditEntry event{
            nextTransactionId_.fetch_add(1),
            current.accountId,
            previous.balance,
            current.balance,
            previous.version,
            current.version,
            policy,
            operation
        };

        std::lock_guard<std::mutex> guard(auditMutex_);
        audit_.push_back(event);
    }

public:
    void createAccount(Account account) {
        const auto snapshot = account.snapshot();

        std::unique_lock<std::shared_mutex> guard(stateMutex_);

        if (accounts_.find(snapshot.accountId) != accounts_.end()) {
            throw ValidationError("Duplicate account.");
        }

        accounts_.emplace(snapshot.accountId, std::move(account));
        locks_[snapshot.accountId] =
            std::make_shared<std::mutex>();
    }

    AccountSnapshot read(int id) const {
        std::shared_lock<std::shared_mutex> guard(stateMutex_);

        auto iterator = accounts_.find(id);

        if (iterator == accounts_.end()) {
            throw ValidationError("Account not found.");
        }

        return iterator->second.snapshot();
    }

    /*
     * Deliberately unsafe implementation.
     * The transaction uses a previously captured balance and
     * overwrites a potentially newer balance.
     */
    TransactionResult unsafeWrite(
        const AccountSnapshot& staleSnapshot,
        std::int64_t amount,
        Operation operation
    ) {
        try {
            validateAmount(amount);

            std::unique_lock<std::shared_mutex> guard(stateMutex_);

            auto iterator = accounts_.find(staleSnapshot.accountId);

            if (iterator == accounts_.end()) {
                throw ValidationError("Account not found.");
            }

            Account& account = iterator->second;
            const auto previous = account.snapshot();

            const auto newBalance = calculate(
                staleSnapshot.balance,
                amount,
                operation
            );

            account.balance_ = newBalance;
            account.version_++;

            const auto current = account.snapshot();

            guard.unlock();

            record(
                previous, current,
                WritePolicy::Unsafe, operation
            );

            return {
                TransactionStatus::Committed,
                "Unsafe write committed.",
                current
            };
        } catch (const std::exception& error) {
            return {
                TransactionStatus::Rejected,
                error.what(),
                std::nullopt
            };
        }
    }

    /*
     * Optimistic concurrency:
     * version validation and modification occur in one
     * exclusive critical section.
     */
    TransactionResult optimisticWrite(
        int id,
        std::uint64_t expectedVersion,
        std::int64_t amount,
        Operation operation
    ) {
        try {
            validateAmount(amount);

            std::unique_lock<std::shared_mutex> guard(stateMutex_);

            auto iterator = accounts_.find(id);

            if (iterator == accounts_.end()) {
                throw ValidationError("Account not found.");
            }

            Account& account = iterator->second;

            if (account.version_ != expectedVersion) {
                return {
                    TransactionStatus::Conflict,
                    "Version conflict: transaction snapshot is stale.",
                    account.snapshot()
                };
            }

            const auto previous = account.snapshot();

            account.balance_ = calculate(
                account.balance_,
                amount,
                operation
            );

            account.version_++;

            const auto current = account.snapshot();

            guard.unlock();

            record(
                previous, current,
                WritePolicy::Optimistic, operation
            );

            return {
                TransactionStatus::Committed,
                "Optimistic write committed.",
                current
            };
        } catch (const std::exception& error) {
            return {
                TransactionStatus::Rejected,
                error.what(),
                std::nullopt
            };
        }
    }

    /*
     * Pessimistic locking:
     * acquire an account-specific mutex before accessing state.
     */
    TransactionResult pessimisticWrite(
        int id,
        std::int64_t amount,
        Operation operation
    ) {
        try {
            validateAmount(amount);

            std::shared_ptr<std::mutex> accountLock;

            {
                std::shared_lock<std::shared_mutex> guard(stateMutex_);

                auto iterator = locks_.find(id);

                if (iterator == locks_.end()) {
                    throw ValidationError("Account not found.");
                }

                accountLock = iterator->second;
            }

            std::lock_guard<std::mutex> accountGuard(*accountLock);

            std::unique_lock<std::shared_mutex> guard(stateMutex_);

            auto iterator = accounts_.find(id);

            if (iterator == accounts_.end()) {
                throw ValidationError("Account not found.");
            }

            Account& account = iterator->second;
            const auto previous = account.snapshot();

            account.balance_ = calculate(
                account.balance_,
                amount,
                operation
            );

            account.version_++;

            const auto current = account.snapshot();

            guard.unlock();

            record(
                previous, current,
                WritePolicy::Pessimistic, operation
            );

            return {
                TransactionStatus::Committed,
                "Pessimistic write committed.",
                current
            };
        } catch (const std::exception& error) {
            return {
                TransactionStatus::Rejected,
                error.what(),
                std::nullopt
            };
        }
    }

    TransactionResult retryOptimistic(
        int id,
        std::int64_t amount,
        Operation operation,
        int maxAttempts = 5
    ) {
        if (maxAttempts < 1) {
            return {
                TransactionStatus::Rejected,
                "Invalid retry count.",
                std::nullopt
            };
        }

        for (int attempt = 0; attempt < maxAttempts; ++attempt) {
            const auto current = read(id);

            auto result = optimisticWrite(
                id,
                current.version,
                amount,
                operation
            );

            if (result.status != TransactionStatus::Conflict) {
                return result;
            }

            std::this_thread::yield();
        }

        return {
            TransactionStatus::Conflict,
            "Optimistic retry limit exceeded.",
            read(id)
        };
    }

    std::vector<AuditEntry> audit() const {
        std::lock_guard<std::mutex> guard(auditMutex_);
        return audit_;
    }
};

void demonstrateLostUpdate() {
    std::cout << "\n1. Lost update demonstration\n";

    Repository repository;
    repository.createAccount(Account(1, "Customer A", 1000));

    const auto transactionA = repository.read(1);
    const auto transactionB = repository.read(1);

    repository.unsafeWrite(
        transactionA, 200, Operation::Deposit
    );

    repository.unsafeWrite(
        transactionB, 100, Operation::Withdraw
    );

    const auto result = repository.read(1);

    std::cout << "Expected balance: 1100\n";
    std::cout << "Actual balance: " << result.balance << '\n';

    if (result.balance != 900) {
        throw std::runtime_error(
            "Lost-update demonstration failed."
        );
    }
}

void demonstrateOptimisticControl() {
    std::cout << "\n2. Optimistic concurrency\n";

    Repository repository;
    repository.createAccount(Account(2, "Customer B", 1000));

    const auto first = repository.read(2);
    const auto second = repository.read(2);

    auto firstResult = repository.optimisticWrite(
        2, first.version, 200, Operation::Deposit
    );

    auto secondResult = repository.optimisticWrite(
        2, second.version, 100, Operation::Withdraw
    );

    std::cout << firstResult.message << '\n';
    std::cout << secondResult.message << '\n';

    auto retry = repository.retryOptimistic(
        2, 100, Operation::Withdraw
    );

    std::cout << "Retry result: " << retry.message << '\n';
    std::cout << "Final balance: "
              << repository.read(2).balance << '\n';
}

void demonstratePessimisticControl() {
    std::cout << "\n3. Pessimistic concurrency\n";

    Repository repository;
    repository.createAccount(Account(3, "Customer C", 1000));

    constexpr int THREADS = 8;
    constexpr int OPERATIONS_PER_THREAD = 100;

    std::vector<std::thread> workers;

    for (int i = 0; i < THREADS; ++i) {
        workers.emplace_back([&repository]() {
            for (int j = 0; j < OPERATIONS_PER_THREAD; ++j) {
                auto result = repository.pessimisticWrite(
                    3, 10, Operation::Deposit
                );

                if (result.status != TransactionStatus::Committed) {
                    throw std::runtime_error(result.message);
                }
            }
        });
    }

    for (auto& worker : workers) {
        worker.join();
    }

    const auto result = repository.read(3);

    std::cout << "Expected balance: 9000\n";
    std::cout << "Actual balance: " << result.balance << '\n';

    if (result.balance != 9000) {
        throw std::runtime_error(
            "Pessimistic locking test failed."
        );
    }
}

void demonstrateFailureHandling() {
    std::cout << "\n4. Validation and failure handling\n";

    Repository repository;
    repository.createAccount(Account(4, "Customer D", 100));

    auto insufficient = repository.pessimisticWrite(
        4, 200, Operation::Withdraw
    );

    auto invalid = repository.pessimisticWrite(
        4, -10, Operation::Deposit
    );

    std::cout << insufficient.message << '\n';
    std::cout << invalid.message << '\n';

    std::cout << "Unchanged balance: "
              << repository.read(4).balance << '\n';
}

void demonstrateAudit() {
    std::cout << "\n5. Audit history\n";

    Repository repository;
    repository.createAccount(Account(5, "Customer E", 500));

    repository.pessimisticWrite(
        5, 100, Operation::Deposit
    );

    repository.pessimisticWrite(
        5, 50, Operation::Withdraw
    );

    for (const auto& event : repository.audit()) {
        std::cout
            << "Transaction " << event.transactionId
            << ": " << event.oldBalance
            << " -> " << event.newBalance
            << ", version " << event.oldVersion
            << " -> " << event.newVersion << '\n';
    }
}

int main() {
    try {
        demonstrateLostUpdate();
        demonstrateOptimisticControl();
        demonstratePessimisticControl();
        demonstrateFailureHandling();
        demonstrateAudit();

        std::cout << "\nAll demonstrations completed.\n";
    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
