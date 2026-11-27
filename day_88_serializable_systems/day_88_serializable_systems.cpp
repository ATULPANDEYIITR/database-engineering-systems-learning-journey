#include <algorithm>
#include <chrono>
#include <functional>
#include <iostream>
#include <map>
#include <queue>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using namespace std;

enum class OperationType {
    READ,
    WRITE
};

enum class IsolationLevel {
    READ_COMMITTED,
    REPEATABLE_READ,
    SERIALIZABLE
};

enum class TransactionState {
    ACTIVE,
    COMMITTED,
    ABORTED
};

struct Operation {
    string transaction;
    string resource;
    OperationType type;
};

struct Transaction {
    string id;
    TransactionState state = TransactionState::ACTIVE;
    unordered_set<string> readSet;
    unordered_set<string> writeSet;
    unordered_map<string, long long> workspace;
};

struct AnalysisResult {
    bool serializable = false;
    vector<string> order;
    vector<string> cycle;
    unordered_map<string, unordered_set<string>> graph;
};

class ScheduleAnalyzer {

public:

    AnalysisResult analyze(
        const vector<Operation>& operations
    ) const {

        AnalysisResult result;

        vector<string> transactions;

        for (const auto& operation : operations) {

            if (
                find(
                    transactions.begin(),
                    transactions.end(),
                    operation.transaction
                ) == transactions.end()
            ) {
                transactions.push_back(operation.transaction);
            }

            result.graph[operation.transaction];
        }

        // Construct precedence edges from conflicting operations.
        for (size_t i = 0; i < operations.size(); ++i) {

            for (size_t j = i + 1; j < operations.size(); ++j) {

                const auto& first = operations[i];
                const auto& second = operations[j];

                if (first.transaction == second.transaction) {
                    continue;
                }

                if (first.resource != second.resource) {
                    continue;
                }

                const bool conflict =
                    first.type == OperationType::WRITE ||
                    second.type == OperationType::WRITE;

                if (conflict) {
                    result.graph[first.transaction].insert(
                        second.transaction
                    );
                }
            }
        }

        unordered_map<string, int> indegree;

        for (const auto& transaction : transactions) {
            indegree[transaction] = 0;
        }

        for (const auto& [source, neighbors] : result.graph) {

            for (const auto& destination : neighbors) {
                indegree[destination]++;
            }
        }

        queue<string> ready;

        for (const auto& [transaction, degree] : indegree) {

            if (degree == 0) {
                ready.push(transaction);
            }
        }

        while (!ready.empty()) {

            string current = ready.front();
            ready.pop();

            result.order.push_back(current);

            for (const auto& neighbor : result.graph[current]) {

                indegree[neighbor]--;

                if (indegree[neighbor] == 0) {
                    ready.push(neighbor);
                }
            }
        }

        result.serializable =
            result.order.size() == transactions.size();

        if (!result.serializable) {

            for (const auto& [transaction, degree] : indegree) {

                if (degree > 0) {
                    result.cycle.push_back(transaction);
                }
            }
        }

        return result;
    }
};


class GovernanceEngine {

private:

    unordered_map<string, long long> database;

    unordered_map<string, Transaction> transactions;

    unordered_map<string, unordered_set<string>> sharedLocks;

    unordered_map<string, string> exclusiveLocks;

    unordered_map<string, unordered_set<string>> waitForGraph;

    size_t lockWaits = 0;
    size_t lockGrants = 0;
    size_t aborts = 0;

    void ensureActive(const string& id) const {

        auto it = transactions.find(id);

        if (it == transactions.end()) {
            throw runtime_error("Transaction not found: " + id);
        }

        if (it->second.state != TransactionState::ACTIVE) {
            throw runtime_error("Transaction is not active: " + id);
        }
    }

    bool canAcquire(
        const string& id,
        const string& resource,
        OperationType type
    ) const {

        auto exclusive = exclusiveLocks.find(resource);

        if (
            exclusive != exclusiveLocks.end() &&
            exclusive->second != id
        ) {
            return false;
        }

        if (type == OperationType::WRITE) {

            auto shared = sharedLocks.find(resource);

            if (shared != sharedLocks.end()) {

                for (const auto& holder : shared->second) {

                    if (holder != id) {
                        return false;
                    }
                }
            }
        }

        return true;
    }

    void grant(
        const string& id,
        const string& resource,
        OperationType type
    ) {

        if (type == OperationType::READ) {
            sharedLocks[resource].insert(id);
        } else {
            exclusiveLocks[resource] = id;
        }

        lockGrants++;
    }

    void releaseLocks(const string& id) {

        for (auto it = sharedLocks.begin(); it != sharedLocks.end();) {

            it->second.erase(id);

            if (it->second.empty()) {
                it = sharedLocks.erase(it);
            } else {
                ++it;
            }
        }

        for (
            auto it = exclusiveLocks.begin();
            it != exclusiveLocks.end();
        ) {

            if (it->second == id) {
                it = exclusiveLocks.erase(it);
            } else {
                ++it;
            }
        }

        waitForGraph.erase(id);

        for (auto& [transaction, neighbors] : waitForGraph) {
            neighbors.erase(id);
        }
    }

public:

    explicit GovernanceEngine(
        unordered_map<string, long long> initialData
    ) : database(move(initialData)) {

        for (const auto& [resource, value] : database) {

            if (value < 0) {
                throw invalid_argument("Negative initial balance");
            }
        }
    }

    void begin(const string& id) {

        if (transactions.count(id)) {
            throw runtime_error("Duplicate transaction ID");
        }

        Transaction transaction;
        transaction.id = id;

        transactions.emplace(id, move(transaction));
    }

    bool acquire(
        const string& id,
        const string& resource,
        OperationType type
    ) {

        ensureActive(id);

        if (!database.count(resource)) {
            throw runtime_error("Unknown resource: " + resource);
        }

        if (!canAcquire(id, resource, type)) {

            lockWaits++;

            if (!waitForGraph.count(id)) {
                waitForGraph[id];
            }

            auto exclusive = exclusiveLocks.find(resource);

            if (
                exclusive != exclusiveLocks.end() &&
                exclusive->second != id
            ) {
                waitForGraph[id].insert(exclusive->second);
            }

            auto shared = sharedLocks.find(resource);

            if (type == OperationType::WRITE &&
                shared != sharedLocks.end()) {

                for (const auto& holder : shared->second) {

                    if (holder != id) {
                        waitForGraph[id].insert(holder);
                    }
                }
            }

            return false;
        }

        grant(id, resource, type);
        return true;
    }

    long long read(
        const string& id,
        const string& resource
    ) {

        ensureActive(id);

        if (!acquire(id, resource, OperationType::READ)) {
            throw runtime_error("Read blocked by lock conflict");
        }

        auto& transaction = transactions.at(id);

        transaction.readSet.insert(resource);

        auto written = transaction.workspace.find(resource);

        if (written != transaction.workspace.end()) {
            return written->second;
        }

        return database.at(resource);
    }

    bool write(
        const string& id,
        const string& resource,
        long long value
    ) {

        ensureActive(id);

        if (value < 0) {
            throw invalid_argument("Balance cannot be negative");
        }

        if (!acquire(id, resource, OperationType::WRITE)) {
            return false;
        }

        auto& transaction = transactions.at(id);

        transaction.writeSet.insert(resource);
        transaction.workspace[resource] = value;

        return true;
    }

    bool detectDeadlock() const {

        unordered_set<string> visited;
        unordered_set<string> active;

        function<bool(const string&)> dfs =
            [&](const string& node) -> bool {

                if (active.count(node)) {
                    return true;
                }

                if (visited.count(node)) {
                    return false;
                }

                visited.insert(node);
                active.insert(node);

                auto it = waitForGraph.find(node);

                if (it != waitForGraph.end()) {

                    for (const auto& neighbor : it->second) {

                        if (dfs(neighbor)) {
                            return true;
                        }
                    }
                }

                active.erase(node);

                return false;
            };

        for (const auto& [transaction, neighbors] : waitForGraph) {

            if (dfs(transaction)) {
                return true;
            }
        }

        return false;
    }

    bool commit(const string& id) {

        ensureActive(id);

        Transaction& transaction = transactions.at(id);

        // Check all constraints before publishing changes.
        for (const auto& [resource, value] : transaction.workspace) {

            if (value < 0) {
                abort(id);
                return false;
            }
        }

        for (const auto& [resource, value] : transaction.workspace) {
            database[resource] = value;
        }

        transaction.state = TransactionState::COMMITTED;

        // Strict 2PL retains locks until commit.
        releaseLocks(id);

        return true;
    }

    void abort(const string& id) {

        ensureActive(id);

        Transaction& transaction = transactions.at(id);

        transaction.workspace.clear();
        transaction.state = TransactionState::ABORTED;

        releaseLocks(id);
        aborts++;
    }

    const unordered_map<string, long long>& snapshot() const {
        return database;
    }

    void printMetrics() const {

        cout << "\nLock grants: " << lockGrants << '\n';
        cout << "Lock waits: " << lockWaits << '\n';
        cout << "Aborts: " << aborts << '\n';
    }
};


void demonstrateScheduleAnalysis() {

    cout << "\n=== Conflict Serializability ===\n";

    vector<Operation> schedule = {
        {"T1", "A", OperationType::READ},
        {"T2", "B", OperationType::READ},
        {"T1", "B", OperationType::WRITE},
        {"T2", "A", OperationType::WRITE}
    };

    ScheduleAnalyzer analyzer;

    AnalysisResult result = analyzer.analyze(schedule);

    cout << "Serializable: "
         << (result.serializable ? "YES" : "NO")
         << '\n';

    cout << "Precedence graph:\n";

    for (const auto& [transaction, neighbors] : result.graph) {

        cout << transaction << " -> ";

        for (const auto& neighbor : neighbors) {
            cout << neighbor << " ";
        }

        cout << '\n';
    }

    if (result.serializable) {

        cout << "Equivalent order: ";

        for (const auto& transaction : result.order) {
            cout << transaction << " ";
        }

        cout << '\n';

    } else {

        cout << "Cycle members: ";

        for (const auto& transaction : result.cycle) {
            cout << transaction << " ";
        }

        cout << '\n';
    }
}


void demonstrateSerializableTransfers() {

    cout << "\n=== Strict Two-Phase Locking ===\n";

    GovernanceEngine engine({
        {"ACCOUNT_A", 1000},
        {"ACCOUNT_B", 500}
    });

    engine.begin("TRANSFER_1");

    long long source = engine.read(
        "TRANSFER_1",
        "ACCOUNT_A"
    );

    long long destination = engine.read(
        "TRANSFER_1",
        "ACCOUNT_B"
    );

    const long long amount = 200;

    if (source < amount) {
        engine.abort("TRANSFER_1");
        throw runtime_error("Insufficient funds");
    }

    if (!engine.write(
        "TRANSFER_1",
        "ACCOUNT_A",
        source - amount
    )) {
        engine.abort("TRANSFER_1");
        throw runtime_error("Source lock unavailable");
    }

    if (!engine.write(
        "TRANSFER_1",
        "ACCOUNT_B",
        destination + amount
    )) {
        engine.abort("TRANSFER_1");
        throw runtime_error("Destination lock unavailable");
    }

    engine.commit("TRANSFER_1");

    for (const auto& [account, balance] : engine.snapshot()) {
        cout << account << ": " << balance << '\n';
    }

    engine.printMetrics();
}


void demonstrateRollback() {

    cout << "\n=== Atomic Rollback ===\n";

    GovernanceEngine engine({
        {"ACCOUNT_A", 1000},
        {"ACCOUNT_B", 500}
    });

    engine.begin("T1");

    engine.write("T1", "ACCOUNT_A", 100);

    engine.abort("T1");

    cout << "ACCOUNT_A after abort: "
         << engine.snapshot().at("ACCOUNT_A")
         << '\n';
}


void demonstratePerformance() {

    cout << "\n=== Concurrency Cost Analysis ===\n";

    const size_t transactions = 10000;
    const size_t conflicts = 850;
    const double validationCost = 0.05;
    const double retryCost = 1.4;

    const double estimatedCost =
        transactions * validationCost +
        conflicts * retryCost;

    cout << "Transactions: " << transactions << '\n';
    cout << "Conflicts: " << conflicts << '\n';
    cout << "Estimated cost units: "
         << estimatedCost << '\n';

    cout << "Conflict ratio: "
         << static_cast<double>(conflicts) / transactions
         << '\n';
}


int main() {

    try {

        const auto started = chrono::steady_clock::now();

        demonstrateScheduleAnalysis();
        demonstrateSerializableTransfers();
        demonstrateRollback();
        demonstratePerformance();

        const auto finished = chrono::steady_clock::now();

        const auto elapsed =
            chrono::duration_cast<chrono::microseconds>(
                finished - started
            ).count();

        cout << "\nExecution time: "
             << elapsed << " microseconds\n";

    } catch (const exception& error) {

        cerr << "Execution error: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}
