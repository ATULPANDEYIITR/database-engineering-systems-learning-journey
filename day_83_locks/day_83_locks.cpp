// locks.cpp
// Shared Locks, Exclusive Locks, and Lock Compatibility
// C++17
//
// Repository-independent database lock simulation.
// Implements a deterministic transaction scheduler, lock compatibility,
// FIFO waiting queues, lock upgrades, and transaction cleanup.

#include <algorithm>
#include <chrono>
#include <iostream>
#include <map>
#include <optional>
#include <queue>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

enum class LockMode {
    Shared,
    Exclusive
};

enum class RequestStatus {
    Granted,
    Waiting,
    Rejected
};

std::string modeName(LockMode mode) {
    return mode == LockMode::Shared ? "SHARED" : "EXCLUSIVE";
}

bool compatible(LockMode requested, LockMode held) {
    return requested == LockMode::Shared &&
           held == LockMode::Shared;
}

struct LockRequest {
    std::string transactionId;
    std::string resource;
    LockMode mode;
    std::size_t sequence;
};

struct LockHolder {
    LockMode mode;
    int count;
};

struct LockState {
    std::unordered_map<std::string, LockHolder> holders;
    std::queue<LockRequest> waiting;
};

class LockManager {
private:
    std::unordered_map<std::string, LockState> resources;
    std::size_t nextSequence = 1;

    bool compatibleWithHolders(
        const LockState& state,
        const std::string& transaction,
        LockMode mode
    ) const {
        for (const auto& entry : state.holders) {
            if (entry.first == transaction) {
                continue;
            }

            if (!compatible(mode, entry.second.mode)) {
                return false;
            }
        }

        return true;
    }

    bool canGrant(
        const LockState& state,
        const LockRequest& request
    ) const {
        if (!compatibleWithHolders(
                state,
                request.transactionId,
                request.mode
            )) {
            return false;
        }

        // The first incompatible waiting request cannot be bypassed.
        if (!state.waiting.empty()) {
            const auto& first = state.waiting.front();

            if (
                first.transactionId != request.transactionId &&
                (
                    first.mode != LockMode::Shared ||
                    request.mode != LockMode::Shared
                )
            ) {
                return false;
            }
        }

        return true;
    }

    void grant(
        LockState& state,
        const LockRequest& request
    ) {
        auto it = state.holders.find(request.transactionId);

        if (it == state.holders.end()) {
            state.holders.emplace(
                request.transactionId,
                LockHolder{request.mode, 1}
            );
        } else {
            it->second.mode = request.mode;
            it->second.count = 1;
        }

        std::cout
            << "GRANTED: " << request.transactionId
            << " -> " << request.resource
            << " [" << modeName(request.mode) << "]\n";
    }

    void drain(const std::string& resource) {
        auto& state = resources.at(resource);

        while (!state.waiting.empty()) {
            const auto request = state.waiting.front();

            if (!canGrant(state, request)) {
                break;
            }

            state.waiting.pop();
            grant(state, request);
        }
    }

public:
    RequestStatus acquire(
        const std::string& transaction,
        const std::string& resource,
        LockMode mode
    ) {
        if (transaction.empty() || resource.empty()) {
            throw std::invalid_argument(
                "Transaction and resource are required."
            );
        }

        auto& state = resources[resource];

        auto existing = state.holders.find(transaction);

        if (existing != state.holders.end()) {
            if (
                existing->second.mode == LockMode::Exclusive ||
                mode == LockMode::Shared
            ) {
                ++existing->second.count;
                return RequestStatus::Granted;
            }

            // Do not allow unsafe upgrades when other readers exist.
            if (state.holders.size() > 1) {
                std::cout
                    << "UPGRADE REJECTED: " << transaction
                    << " has competing readers on " << resource << "\n";

                return RequestStatus::Rejected;
            }
        }

        LockRequest request{
            transaction,
            resource,
            mode,
            nextSequence++
        };

        if (canGrant(state, request)) {
            grant(state, request);
            return RequestStatus::Granted;
        }

        state.waiting.push(request);

        std::cout
            << "WAITING: " << transaction
            << " -> " << resource
            << " [" << modeName(mode) << "]\n";

        return RequestStatus::Waiting;
    }

    void release(
        const std::string& transaction,
        const std::string& resource
    ) {
        auto resourceIt = resources.find(resource);

        if (resourceIt == resources.end()) {
            throw std::runtime_error("Unknown resource.");
        }

        auto& state = resourceIt->second;
        auto holder = state.holders.find(transaction);

        if (holder == state.holders.end()) {
            throw std::runtime_error(
                "Transaction does not hold this resource."
            );
        }

        --holder->second.count;

        if (holder->second.count == 0) {
            state.holders.erase(holder);
            std::cout
                << "RELEASED: " << transaction
                << " -> " << resource << "\n";
        }

        drain(resource);
    }

    void releaseAll(const std::string& transaction) {
        for (auto& entry : resources) {
            auto& state = entry.second;

            state.holders.erase(transaction);

            // Remove outstanding requests belonging to the transaction.
            std::queue<LockRequest> remaining;

            while (!state.waiting.empty()) {
                auto request = state.waiting.front();
                state.waiting.pop();

                if (request.transactionId != transaction) {
                    remaining.push(request);
                }
            }

            state.waiting.swap(remaining);
        }

        for (const auto& entry : resources) {
            drain(entry.first);
        }
    }

    void printState() const {
        std::cout << "\nLOCK TABLE\n";

        for (const auto& entry : resources) {
            std::cout << "Resource: " << entry.first << "\n";

            for (const auto& holder : entry.second.holders) {
                std::cout
                    << "  " << holder.first
                    << " [" << modeName(holder.second.mode)
                    << "] count=" << holder.second.count << "\n";
            }

            auto waiting = entry.second.waiting;

            while (!waiting.empty()) {
                const auto request = waiting.front();
                waiting.pop();

                std::cout
                    << "  WAITING: " << request.transactionId
                    << " [" << modeName(request.mode) << "]\n";
            }
        }
    }
};

class Transaction {
private:
    std::string id;
    LockManager& manager;
    bool active = true;

public:
    Transaction(std::string transactionId, LockManager& lockManager)
        : id(std::move(transactionId)), manager(lockManager) {}

    RequestStatus shared(const std::string& resource) {
        if (!active) {
            throw std::runtime_error("Transaction is inactive.");
        }

        return manager.acquire(id, resource, LockMode::Shared);
    }

    RequestStatus exclusive(const std::string& resource) {
        if (!active) {
            throw std::runtime_error("Transaction is inactive.");
        }

        return manager.acquire(id, resource, LockMode::Exclusive);
    }

    void commit() {
        if (!active) {
            throw std::runtime_error("Transaction already completed.");
        }

        manager.releaseAll(id);
        active = false;

        std::cout << "COMMITTED: " << id << "\n";
    }

    void rollback() {
        if (!active) {
            throw std::runtime_error("Transaction already completed.");
        }

        manager.releaseAll(id);
        active = false;

        std::cout << "ROLLED BACK: " << id << "\n";
    }

    ~Transaction() {
        if (active) {
            manager.releaseAll(id);
        }
    }
};

void demonstrateCompatibility() {
    std::cout << "\n1. SHARED LOCK COMPATIBILITY\n";

    LockManager manager;

    Transaction t1("T1", manager);
    Transaction t2("T2", manager);
    Transaction t3("T3", manager);

    t1.shared("accounts:100");
    t2.shared("accounts:100");

    t3.exclusive("accounts:100");

    manager.printState();

    t1.commit();

    manager.printState();

    t2.commit();

    manager.printState();

    t3.commit();
}

void demonstrateUpgradeConflict() {
    std::cout << "\n2. LOCK UPGRADE CONFLICT\n";

    LockManager manager;

    Transaction t1("T10", manager);
    Transaction t2("T20", manager);

    t1.shared("inventory:50");
    t2.shared("inventory:50");

    const auto result = t1.exclusive("inventory:50");

    if (result == RequestStatus::Rejected) {
        std::cout << "Upgrade safely rejected.\n";
    }

    t1.commit();
    t2.commit();
}

void demonstrateIndependentResources() {
    std::cout << "\n3. INDEPENDENT RESOURCE CONCURRENCY\n";

    LockManager manager;

    Transaction t1("T100", manager);
    Transaction t2("T200", manager);

    t1.exclusive("orders:10");
    t2.exclusive("orders:20");

    manager.printState();

    t1.commit();
    t2.commit();
}

void demonstrateReentrancy() {
    std::cout << "\n4. REENTRANT ACQUISITION\n";

    LockManager manager;

    Transaction t1("T300", manager);

    t1.shared("products:10");
    t1.shared("products:10");

    manager.printState();

    manager.releaseAll("T300");

    t1.commit();
}

int main() {
    try {
        demonstrateCompatibility();
        demonstrateUpgradeConflict();
        demonstrateIndependentResources();
        demonstrateReentrancy();

        std::cout << "\nAll C++ demonstrations completed.\n";
    } catch (const std::exception& error) {
        std::cerr << "LOCK MANAGER ERROR: "
                  << error.what() << "\n";

        return 1;
    }

    return 0;
}
