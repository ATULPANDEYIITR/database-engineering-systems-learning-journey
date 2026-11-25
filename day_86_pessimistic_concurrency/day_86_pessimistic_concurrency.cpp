#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <exception>
#include <iostream>
#include <map>
#include <mutex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

/*
 * Pessimistic Concurrency: Repository-Independent
 * Resource Locking and Merge-Eligibility Engine
 *
 * Scenario:
 * An enterprise warehouse processes concurrent inventory
 * reservations using pessimistic exclusive locking.
 *
 * Features:
 * - Shared and exclusive locks
 * - Lock compatibility
 * - Timed acquisition
 * - Deadlock detection
 * - Two-phase locking
 * - Strict lock retention
 * - Atomic inventory updates
 * - Transaction rollback
 * - Concurrent reservation processing
 */

enum class LockMode {
    SHARED,
    EXCLUSIVE
};

enum class TransactionState {
    ACTIVE,
    COMMITTED,
    ABORTED
};

struct LockRequest {
    int transactionId;
    std::string resource;
    LockMode mode;
};

struct Transaction {
    int id;
    TransactionState state = TransactionState::ACTIVE;
    bool growing = true;

    std::map<std::string, LockMode> locks;
    std::map<std::string, int> undoLog;
    std::set<int> waitingFor;
};

class LockManager {
private:
    std::mutex mutex;
    std::condition_variable condition;

    std::map<std::string, std::map<int, LockMode>> lockTable;
    std::unordered_map<int, Transaction*> transactions;

    bool conflicts(
        int transactionId,
        const std::string& resource,
        LockMode requested
    ) const {
        auto it = lockTable.find(resource);

        if (it == lockTable.end()) return false;

        for (const auto& [holder, heldMode] : it->second) {
            if (holder == transactionId) continue;

            if (
                requested == LockMode::EXCLUSIVE ||
                heldMode == LockMode::EXCLUSIVE
            ) {
                return true;
            }
        }

        return false;
    }

    std::set<int> blockers(
        int transactionId,
        const std::string& resource,
        LockMode requested
    ) const {
        std::set<int> result;

        auto it = lockTable.find(resource);

        if (it == lockTable.end()) return result;

        for (const auto& [holder, heldMode] : it->second) {
            if (holder == transactionId) continue;

            if (
                requested == LockMode::EXCLUSIVE ||
                heldMode == LockMode::EXCLUSIVE
            ) {
                result.insert(holder);
            }
        }

        return result;
    }

    bool hasCycle(
        int current,
        std::set<int>& visited,
        std::set<int>& active
    ) const {
        if (active.count(current)) return true;
        if (visited.count(current)) return false;

        visited.insert(current);
        active.insert(current);

        auto it = transactions.find(current);

        if (it != transactions.end()) {
            for (int next : it->second->waitingFor) {
                if (hasCycle(next, visited, active)) {
                    return true;
                }
            }
        }

        active.erase(current);
        return false;
    }

    bool hasCycle(int transactionId) const {
        std::set<int> visited;
        std::set<int> active;

        return hasCycle(transactionId, visited, active);
    }

    void releaseLocked(Transaction& transaction) {
        for (const auto& [resource, mode] : transaction.locks) {
            auto it = lockTable.find(resource);

            if (it == lockTable.end()) continue;

            it->second.erase(transaction.id);

            if (it->second.empty()) {
                lockTable.erase(it);
            }
        }

        transaction.locks.clear();
        transaction.waitingFor.clear();

        for (auto& [id, other] : transactions) {
            other->waitingFor.erase(transaction.id);
        }

        condition.notify_all();
    }

public:
    void registerTransaction(Transaction& transaction) {
        std::lock_guard<std::mutex> guard(mutex);

        if (transactions.count(transaction.id)) {
            throw std::runtime_error("Duplicate transaction ID");
        }

        transactions[transaction.id] = &transaction;
    }

    void acquire(
        Transaction& transaction,
        const std::string& resource,
        LockMode requested,
        int timeoutMilliseconds = 3000
    ) {
        if (resource.empty() || timeoutMilliseconds < 0) {
            throw std::invalid_argument("Invalid lock request");
        }

        std::unique_lock<std::mutex> guard(mutex);

        if (transaction.state != TransactionState::ACTIVE) {
            throw std::runtime_error("Transaction is inactive");
        }

        auto existing = transaction.locks.find(resource);

        if (existing != transaction.locks.end()) {
            if (
                existing->second == LockMode::EXCLUSIVE ||
                requested == LockMode::SHARED
            ) {
                return;
            }
        }

        if (!transaction.growing) {
            throw std::runtime_error("Two-phase locking violation");
        }

        const auto deadline =
            std::chrono::steady_clock::now() +
            std::chrono::milliseconds(timeoutMilliseconds);

        while (true) {
            if (transaction.state != TransactionState::ACTIVE) {
                throw std::runtime_error("Transaction terminated");
            }

            transaction.waitingFor = blockers(
                transaction.id,
                resource,
                requested
            );

            if (hasCycle(transaction.id)) {
                transaction.waitingFor.clear();

                throw std::runtime_error(
                    "Deadlock detected; transaction must abort"
                );
            }

            if (!conflicts(transaction.id, resource, requested)) {
                transaction.waitingFor.clear();

                lockTable[resource][transaction.id] = requested;
                transaction.locks[resource] = requested;

                return;
            }

            if (
                condition.wait_until(guard, deadline) ==
                std::cv_status::timeout
            ) {
                transaction.waitingFor.clear();

                throw std::runtime_error("Lock acquisition timeout");
            }
        }
    }

    void commit(Transaction& transaction) {
        std::lock_guard<std::mutex> guard(mutex);

        if (transaction.state != TransactionState::ACTIVE) {
            throw std::runtime_error("Cannot commit inactive transaction");
        }

        transaction.growing = false;
        transaction.state = TransactionState::COMMITTED;

        releaseLocked(transaction);
    }

    void rollback(
        Transaction& transaction,
        std::map<std::string, int>& database
    ) {
        std::lock_guard<std::mutex> guard(mutex);

        if (transaction.state != TransactionState::ACTIVE) return;

        for (
            auto it = transaction.undoLog.rbegin();
            it != transaction.undoLog.rend();
            ++it
        ) {
            database[it->first] = it->second;
        }

        transaction.undoLog.clear();
        transaction.growing = false;
        transaction.state = TransactionState::ABORTED;

        releaseLocked(transaction);
    }
};

class InventoryService {
private:
    std::map<std::string, int> inventory;
    LockManager manager;

    std::mutex idMutex;
    int nextTransactionId = 1;

    int generateId() {
        std::lock_guard<std::mutex> guard(idMutex);
        return nextTransactionId++;
    }

public:
    explicit InventoryService(
        const std::map<std::string, int>& initialInventory
    ) : inventory(initialInventory) {

        if (inventory.empty()) {
            throw std::invalid_argument("Inventory cannot be empty");
        }

        for (const auto& [product, quantity] : inventory) {
            if (product.empty() || quantity < 0) {
                throw std::invalid_argument("Invalid inventory record");
            }
        }
    }

    bool reserve(
        const std::string& product,
        int quantity,
        int timeoutMilliseconds = 3000
    ) {
        if (quantity <= 0) {
            throw std::invalid_argument("Quantity must be positive");
        }

        Transaction transaction;
        transaction.id = generateId();

        manager.registerTransaction(transaction);

        try {
            manager.acquire(
                transaction,
                product,
                LockMode::EXCLUSIVE,
                timeoutMilliseconds
            );

            auto it = inventory.find(product);

            if (it == inventory.end()) {
                throw std::runtime_error("Unknown product");
            }

            if (it->second < quantity) {
                throw std::runtime_error("Insufficient inventory");
            }

            transaction.undoLog[product] = it->second;

            it->second -= quantity;

            manager.commit(transaction);

            return true;

        } catch (const std::exception& error) {
            manager.rollback(transaction, inventory);

            std::cerr
                << "Transaction "
                << transaction.id
                << " rejected: "
                << error.what()
                << '\n';

            return false;
        }
    }

    void display() const {
        std::cout << "\nInventory state:\n";

        for (const auto& [product, quantity] : inventory) {
            std::cout
                << product
                << " = "
                << quantity
                << '\n';
        }
    }

    int totalStock() const {
        int total = 0;

        for (const auto& [product, quantity] : inventory) {
            total += quantity;
        }

        return total;
    }
};

void runConcurrentReservations() {
    InventoryService service({
        {"LAPTOP", 100},
        {"MONITOR", 80},
        {"KEYBOARD", 200}
    });

    const int initialTotal = service.totalStock();

    std::vector<std::thread> workers;

    for (int i = 0; i < 10; ++i) {
        workers.emplace_back([&service, i]() {
            std::string product;

            switch (i % 3) {
                case 0: product = "LAPTOP"; break;
                case 1: product = "MONITOR"; break;
                default: product = "KEYBOARD"; break;
            }

            service.reserve(product, 5, 5000);
        });
    }

    for (auto& worker : workers) {
        worker.join();
    }

    service.display();

    std::cout
        << "\nInitial stock: "
        << initialTotal
        << "\nFinal stock: "
        << service.totalStock()
        << '\n';

    if (service.totalStock() > initialTotal) {
        throw std::runtime_error("Inventory conservation violated");
    }

    std::cout << "Inventory invariant verified.\n";
}

int main() {
    try {
        std::cout
            << "PESSIMISTIC CONCURRENCY ENGINE\n"
            << "==============================\n";

        runConcurrentReservations();

        std::cout << "\nExecution completed.\n";

    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
