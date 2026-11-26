#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

enum class TransactionState {
    ACTIVE,
    COMMITTED,
    ABORTED
};

enum class ConcurrencyModel {
    MVCC,
    PESSIMISTIC_LOCKING
};

struct Version {
    uint64_t timestamp;
    int64_t value;
};

struct Transaction {
    uint64_t id;
    uint64_t snapshot;
    TransactionState state = TransactionState::ACTIVE;

    unordered_map<string, int64_t> writes;
    set<string> reads;
    set<string> locks;
};

struct Metrics {
    uint64_t started = 0;
    uint64_t committed = 0;
    uint64_t aborted = 0;
    uint64_t conflicts = 0;
    uint64_t lockFailures = 0;
    uint64_t reads = 0;
    uint64_t writes = 0;
};

class ConcurrencyException : public runtime_error {
public:
    explicit ConcurrencyException(const string& message)
        : runtime_error(message) {}
};

class MVCCEngine {
private:
    uint64_t clock = 0;
    uint64_t nextId = 1;

    unordered_map<string, vector<Version>> storage;

    Metrics metrics;

    void ensureActive(const Transaction& tx) const {
        if (tx.state != TransactionState::ACTIVE) {
            throw ConcurrencyException(
                "Transaction is not active"
            );
        }
    }

    optional<Version> visibleVersion(
        const string& key,
        uint64_t snapshot
    ) const {
        auto it = storage.find(key);

        if (it == storage.end()) {
            return nullopt;
        }

        const auto& versions = it->second;

        auto position = upper_bound(
            versions.begin(),
            versions.end(),
            snapshot,
            [](uint64_t timestamp, const Version& version) {
                return timestamp < version.timestamp;
            }
        );

        if (position == versions.begin()) {
            return nullopt;
        }

        return *prev(position);
    }

public:
    explicit MVCCEngine(
        const unordered_map<string, int64_t>& initial
    ) {
        for (const auto& [key, value] : initial) {
            storage[key].push_back({0, value});
        }
    }

    Transaction begin() {
        metrics.started++;

        return Transaction{
            nextId++,
            clock
        };
    }

    optional<int64_t> read(
        Transaction& tx,
        const string& key
    ) {
        ensureActive(tx);
        metrics.reads++;

        auto pending = tx.writes.find(key);

        if (pending != tx.writes.end()) {
            return pending->second;
        }

        tx.reads.insert(key);

        auto version = visibleVersion(key, tx.snapshot);

        if (!version.has_value()) {
            return nullopt;
        }

        return version->value;
    }

    void write(
        Transaction& tx,
        const string& key,
        int64_t value
    ) {
        ensureActive(tx);

        if (key.empty()) {
            throw invalid_argument("Key cannot be empty");
        }

        tx.writes[key] = value;
    }

    bool commit(Transaction& tx) {
        ensureActive(tx);

        // First-committer-wins conflict validation.
        for (const auto& [key, value] : tx.writes) {
            auto it = storage.find(key);

            if (
                it != storage.end() &&
                !it->second.empty() &&
                it->second.back().timestamp > tx.snapshot
            ) {
                tx.state = TransactionState::ABORTED;

                metrics.aborted++;
                metrics.conflicts++;

                return false;
            }
        }

        // Publish the complete write set at one logical timestamp.
        ++clock;

        for (const auto& [key, value] : tx.writes) {
            storage[key].push_back({clock, value});
            metrics.writes++;
        }

        tx.state = TransactionState::COMMITTED;
        metrics.committed++;

        return true;
    }

    void rollback(Transaction& tx) {
        ensureActive(tx);

        tx.writes.clear();
        tx.state = TransactionState::ABORTED;

        metrics.aborted++;
    }

    void printHistory(const string& key) const {
        cout << "History for " << key << ":\n";

        auto it = storage.find(key);

        if (it == storage.end()) {
            cout << "No versions\n";
            return;
        }

        for (const auto& version : it->second) {
            cout << "Timestamp: " << version.timestamp
                 << ", Value: " << version.value << '\n';
        }
    }

    const Metrics& getMetrics() const {
        return metrics;
    }
};


class PessimisticLockingEngine {
private:
    unordered_map<string, int64_t> storage;
    unordered_map<string, uint64_t> owners;

    uint64_t nextId = 1;
    Metrics metrics;

    void ensureActive(const Transaction& tx) const {
        if (tx.state != TransactionState::ACTIVE) {
            throw ConcurrencyException(
                "Transaction is not active"
            );
        }
    }

    void acquire(Transaction& tx, const string& key) {
        auto owner = owners.find(key);

        if (
            owner != owners.end() &&
            owner->second != tx.id
        ) {
            metrics.lockFailures++;

            throw ConcurrencyException(
                "Exclusive lock unavailable for " + key
            );
        }

        owners[key] = tx.id;
        tx.locks.insert(key);
    }

    void releaseAll(Transaction& tx) {
        for (const auto& key : tx.locks) {
            auto owner = owners.find(key);

            if (
                owner != owners.end() &&
                owner->second == tx.id
            ) {
                owners.erase(owner);
            }
        }

        tx.locks.clear();
    }

public:
    explicit PessimisticLockingEngine(
        unordered_map<string, int64_t> initial
    ) : storage(std::move(initial)) {}

    Transaction begin() {
        metrics.started++;

        return Transaction{
            nextId++,
            0
        };
    }

    optional<int64_t> read(
        Transaction& tx,
        const string& key
    ) {
        ensureActive(tx);
        acquire(tx, key);

        metrics.reads++;

        auto pending = tx.writes.find(key);

        if (pending != tx.writes.end()) {
            return pending->second;
        }

        auto it = storage.find(key);

        if (it == storage.end()) {
            return nullopt;
        }

        return it->second;
    }

    void write(
        Transaction& tx,
        const string& key,
        int64_t value
    ) {
        ensureActive(tx);
        acquire(tx, key);

        tx.writes[key] = value;
    }

    void commit(Transaction& tx) {
        ensureActive(tx);

        // Locks guarantee exclusive access until publication.
        for (const auto& [key, value] : tx.writes) {
            storage[key] = value;
            metrics.writes++;
        }

        tx.state = TransactionState::COMMITTED;
        metrics.committed++;

        releaseAll(tx);
    }

    void rollback(Transaction& tx) {
        ensureActive(tx);

        tx.writes.clear();
        tx.state = TransactionState::ABORTED;

        metrics.aborted++;

        releaseAll(tx);
    }

    int64_t currentValue(const string& key) const {
        auto it = storage.find(key);

        if (it == storage.end()) {
            throw out_of_range("Unknown record: " + key);
        }

        return it->second;
    }

    const Metrics& getMetrics() const {
        return metrics;
    }
};


struct Workload {
    string name;
    double readRatio;
    double contention;
    double transactionDuration;
    double writeHotspot;
};

struct ArchitectureResult {
    double mvccScore;
    double lockingScore;
    string preferred;
};

class ArchitectureEvaluator {
public:
    static ArchitectureResult evaluate(
        const Workload& workload
    ) {
        if (
            workload.readRatio < 0 ||
            workload.readRatio > 1 ||
            workload.contention < 0 ||
            workload.contention > 1 ||
            workload.writeHotspot < 0 ||
            workload.writeHotspot > 1 ||
            workload.transactionDuration < 0
        ) {
            throw invalid_argument(
                "Invalid workload parameters"
            );
        }

        double mvcc =
            60 * workload.readRatio +
            25 * (1 - workload.contention) +
            15 * (1 - workload.writeHotspot) -
            min(workload.transactionDuration / 1000.0, 20.0);

        double locking =
            50 * workload.contention +
            30 * workload.writeHotspot +
            20 * min(
                workload.transactionDuration / 1000.0,
                1.0
            );

        return {
            mvcc,
            locking,
            mvcc >= locking
                ? "MVCC"
                : "PESSIMISTIC_LOCKING"
        };
    }
};


void demonstrateMVCC() {
    cout << "\n=== MVCC ENGINE ===\n";

    MVCCEngine engine({
        {"account_A", 1000},
        {"account_B", 500}
    });

    Transaction first = engine.begin();
    Transaction second = engine.begin();

    cout << "First reads: "
         << *engine.read(first, "account_A") << '\n';

    cout << "Second reads: "
         << *engine.read(second, "account_A") << '\n';

    engine.write(first, "account_A", 900);
    engine.write(second, "account_A", 800);

    cout << "First commit: "
         << boolalpha << engine.commit(first) << '\n';

    cout << "Second commit: "
         << engine.commit(second) << '\n';

    engine.printHistory("account_A");

    const Metrics& m = engine.getMetrics();

    cout << "Conflicts: " << m.conflicts << '\n';
}


void demonstrateLocking() {
    cout << "\n=== PESSIMISTIC LOCKING ENGINE ===\n";

    PessimisticLockingEngine engine({
        {"inventory", 100}
    });

    Transaction first = engine.begin();
    Transaction second = engine.begin();

    cout << "First reads: "
         << *engine.read(first, "inventory") << '\n';

    try {
        engine.read(second, "inventory");
    } catch (const ConcurrencyException& error) {
        cout << "Expected contention: "
             << error.what() << '\n';
    }

    engine.write(first, "inventory", 90);
    engine.commit(first);

    cout << "Second reads after release: "
         << *engine.read(second, "inventory") << '\n';

    engine.write(second, "inventory", 80);
    engine.commit(second);

    cout << "Final inventory: "
         << engine.currentValue("inventory") << '\n';

    cout << "Lock failures: "
         << engine.getMetrics().lockFailures << '\n';
}


void demonstrateArchitectureEvaluation() {
    cout << "\n=== ARCHITECTURAL EVALUATION ===\n";

    vector<Workload> workloads = {
        {
            "Read-heavy reporting",
            0.95,
            0.10,
            100,
            0.05
        },
        {
            "High-contention inventory",
            0.30,
            0.90,
            500,
            0.90
        },
        {
            "Long-running transactions",
            0.60,
            0.70,
            5000,
            0.50
        }
    };

    for (const auto& workload : workloads) {
        auto result = ArchitectureEvaluator::evaluate(
            workload
        );

        cout << "\n" << workload.name << '\n';

        cout << "MVCC score: "
             << fixed << setprecision(2)
             << result.mvccScore << '\n';

        cout << "Locking score: "
             << result.lockingScore << '\n';

        cout << "Preferred model: "
             << result.preferred << '\n';
    }
}


int main() {
    try {
        demonstrateMVCC();
        demonstrateLocking();
        demonstrateArchitectureEvaluation();

        // Verify first-committer-wins behavior.
        MVCCEngine test({{"x", 10}});

        auto first = test.begin();
        auto second = test.begin();

        test.write(first, "x", 20);
        test.write(second, "x", 30);

        if (!test.commit(first)) {
            throw runtime_error("Unexpected first commit failure");
        }

        if (test.commit(second)) {
            throw runtime_error("Expected a write conflict");
        }

        cout << "\nAll correctness checks passed.\n";

    } catch (const exception& error) {
        cerr << "Execution error: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}
