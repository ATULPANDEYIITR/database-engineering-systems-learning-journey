#include <algorithm>
#include <functional>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

/*
 * Deadlock Detection, Prevention and Recovery Engine.
 *
 * C++17 implementation of a repository-independent resource
 * allocation and transaction governance model.
 *
 * Capabilities:
 * - Resource allocation
 * - Wait-for graph generation
 * - DFS-based cycle detection
 * - Global resource ordering
 * - Victim selection
 * - Transaction rollback
 * - FIFO waiter scheduling
 */

enum class TransactionState {
    ACTIVE,
    WAITING,
    COMMITTED,
    ABORTED
};

string stateName(TransactionState state) {
    switch (state) {
        case TransactionState::ACTIVE:
            return "ACTIVE";
        case TransactionState::WAITING:
            return "WAITING";
        case TransactionState::COMMITTED:
            return "COMMITTED";
        case TransactionState::ABORTED:
            return "ABORTED";
    }

    return "UNKNOWN";
}

struct Transaction {
    string id;
    int startOrder;
    TransactionState state = TransactionState::ACTIVE;
    set<string> heldResources;
    string waitingFor;
    int rollbackCount = 0;
};

struct Resource {
    string name;
    int order;
    string owner;
    vector<string> waitQueue;
};

struct DeadlockReport {
    vector<string> cycle;
    string victim;
};

class ResourceManager {
private:
    map<string, Transaction> transactions;
    map<string, Resource> resources;

    bool preventionEnabled;
    int clock = 0;

    void validateTransaction(const string& id) const {
        auto it = transactions.find(id);

        if (it == transactions.end()) {
            throw runtime_error("Unknown transaction: " + id);
        }

        if (it->second.state != TransactionState::ACTIVE &&
            it->second.state != TransactionState::WAITING) {
            throw runtime_error("Transaction is not active: " + id);
        }
    }

    void validateOrder(
        const Transaction& transaction,
        const Resource& requested
    ) const {
        if (!preventionEnabled ||
            transaction.heldResources.empty()) {
            return;
        }

        int highest = -1;

        for (const string& name : transaction.heldResources) {
            highest = max(highest, resources.at(name).order);
        }

        if (requested.order < highest) {
            throw runtime_error(
                "Resource ordering violation for transaction " +
                transaction.id
            );
        }
    }

    void removeFromQueues(const string& transactionId) {
        for (auto& entry : resources) {
            auto& queue = entry.second.waitQueue;

            queue.erase(
                remove(queue.begin(), queue.end(), transactionId),
                queue.end()
            );
        }
    }

    void wakeWaiter(Resource& resource) {
        while (resource.owner.empty() &&
               !resource.waitQueue.empty()) {

            string id = resource.waitQueue.front();

            resource.waitQueue.erase(
                resource.waitQueue.begin()
            );

            auto it = transactions.find(id);

            if (it == transactions.end()) {
                continue;
            }

            Transaction& transaction = it->second;

            if (transaction.state != TransactionState::WAITING) {
                continue;
            }

            resource.owner = id;

            transaction.heldResources.insert(resource.name);
            transaction.waitingFor.clear();
            transaction.state = TransactionState::ACTIVE;

            cout << "[GRANTED] " << id
                 << " acquired " << resource.name << '\n';
        }
    }

public:
    explicit ResourceManager(bool prevention = false)
        : preventionEnabled(prevention) {}

    void addResource(const string& name, int order) {
        if (name.empty() || resources.count(name)) {
            throw invalid_argument(
                "Resource name must be unique."
            );
        }

        if (order < 0) {
            throw invalid_argument(
                "Resource order cannot be negative."
            );
        }

        for (const auto& entry : resources) {
            if (entry.second.order == order) {
                throw invalid_argument(
                    "Resource order must be unique."
                );
            }
        }

        resources.emplace(
            name,
            Resource{name, order, "", {}}
        );

        cout << "[RESOURCE] Registered " << name << '\n';
    }

    void beginTransaction(const string& id) {
        if (id.empty() || transactions.count(id)) {
            throw invalid_argument(
                "Transaction ID must be unique."
            );
        }

        transactions.emplace(
            id,
            Transaction{id, ++clock}
        );

        cout << "[START] " << id << '\n';
    }

    bool acquire(
        const string& transactionId,
        const string& resourceName
    ) {
        validateTransaction(transactionId);

        auto resourceIt = resources.find(resourceName);

        if (resourceIt == resources.end()) {
            throw invalid_argument("Unknown resource.");
        }

        Transaction& transaction =
            transactions.at(transactionId);

        Resource& resource = resourceIt->second;

        if (transaction.heldResources.count(resourceName)) {
            return true;
        }

        if (!transaction.waitingFor.empty()) {
            throw runtime_error(
                "Transaction already has an outstanding request."
            );
        }

        validateOrder(transaction, resource);

        if (resource.owner.empty()) {
            resource.owner = transactionId;

            transaction.heldResources.insert(resourceName);

            cout << "[ACQUIRED] " << transactionId
                 << " -> " << resourceName << '\n';

            return true;
        }

        if (resource.owner == transactionId) {
            return true;
        }

        if (find(
                resource.waitQueue.begin(),
                resource.waitQueue.end(),
                transactionId
            ) == resource.waitQueue.end()) {
            resource.waitQueue.push_back(transactionId);
        }

        transaction.state = TransactionState::WAITING;
        transaction.waitingFor = resourceName;

        cout << "[WAITING] " << transactionId
             << " -> " << resource.owner
             << " for " << resourceName << '\n';

        return false;
    }

    map<string, set<string>> buildWaitForGraph() const {
        map<string, set<string>> graph;

        for (const auto& entry : transactions) {
            const Transaction& transaction = entry.second;

            if (transaction.state != TransactionState::WAITING) {
                continue;
            }

            const Resource& resource =
                resources.at(transaction.waitingFor);

            if (!resource.owner.empty()) {
                graph[transaction.id].insert(resource.owner);
            }
        }

        return graph;
    }

    vector<vector<string>> detectDeadlocks() const {
        auto graph = buildWaitForGraph();

        map<string, int> color;

        for (const auto& entry : transactions) {
            color[entry.first] = 0;
        }

        vector<string> stack;
        vector<vector<string>> cycles;
        set<vector<string>> signatures;

        auto canonicalize = [](vector<string> cycle) {
            vector<string> best = cycle;

            for (size_t i = 1; i < cycle.size(); ++i) {
                vector<string> rotated;

                rotated.insert(
                    rotated.end(),
                    cycle.begin() + i,
                    cycle.end()
                );

                rotated.insert(
                    rotated.end(),
                    cycle.begin(),
                    cycle.begin() + i
                );

                best = min(best, rotated);
            }

            return best;
        };

        function<void(const string&)> dfs =
            [&](const string& node) {

                color[node] = 1;
                stack.push_back(node);

                auto it = graph.find(node);

                if (it != graph.end()) {
                    for (const string& next : it->second) {
                        if (color[next] == 0) {
                            dfs(next);
                        }
                        else if (color[next] == 1) {
                            auto position = find(
                                stack.begin(),
                                stack.end(),
                                next
                            );

                            vector<string> cycle(
                                position,
                                stack.end()
                            );

                            auto key = canonicalize(cycle);

                            if (signatures.insert(key).second) {
                                cycles.push_back(cycle);
                            }
                        }
                    }
                }

                stack.pop_back();
                color[node] = 2;
            };

        for (const auto& entry : graph) {
            if (color[entry.first] == 0) {
                dfs(entry.first);
            }
        }

        return cycles;
    }

    string selectVictim(const vector<string>& cycle) const {
        if (cycle.empty()) {
            throw invalid_argument("Empty deadlock cycle.");
        }

        return *max_element(
            cycle.begin(),
            cycle.end(),
            [&](const string& a, const string& b) {
                return transactions.at(a).startOrder <
                       transactions.at(b).startOrder;
            }
        );
    }

    void releaseAll(const string& transactionId) {
        Transaction& transaction =
            transactions.at(transactionId);

        vector<string> held(
            transaction.heldResources.begin(),
            transaction.heldResources.end()
        );

        transaction.heldResources.clear();

        // Clear ownership before waking any waiting transaction.
        for (const string& name : held) {
            Resource& resource = resources.at(name);

            if (resource.owner == transactionId) {
                resource.owner.clear();
            }
        }

        for (const string& name : held) {
            wakeWaiter(resources.at(name));
        }
    }

    DeadlockReport recover(const vector<string>& cycle) {
        string victim = selectVictim(cycle);

        Transaction& transaction = transactions.at(victim);

        removeFromQueues(victim);

        transaction.waitingFor.clear();
        transaction.state = TransactionState::ABORTED;
        transaction.rollbackCount++;

        cout << "[RECOVERY] Victim selected: "
             << victim << '\n';

        releaseAll(victim);

        cout << "[ABORTED] " << victim
             << " rolled back.\n";

        return {cycle, victim};
    }

    void release(
        const string& transactionId,
        const string& resourceName
    ) {
        validateTransaction(transactionId);

        auto it = resources.find(resourceName);

        if (it == resources.end() ||
            it->second.owner != transactionId) {
            throw runtime_error("Resource ownership violation.");
        }

        Resource& resource = it->second;

        resource.owner.clear();

        transactions.at(transactionId)
            .heldResources.erase(resourceName);

        cout << "[RELEASED] " << transactionId
             << " -> " << resourceName << '\n';

        wakeWaiter(resource);
    }

    void commit(const string& transactionId) {
        validateTransaction(transactionId);

        Transaction& transaction =
            transactions.at(transactionId);

        if (transaction.state != TransactionState::ACTIVE) {
            throw runtime_error(
                "Waiting transaction cannot commit."
            );
        }

        transaction.state = TransactionState::COMMITTED;

        releaseAll(transactionId);

        cout << "[COMMITTED] " << transactionId << '\n';
    }

    vector<DeadlockReport> detectAndRecover() {
        vector<DeadlockReport> reports;

        while (true) {
            auto cycles = detectDeadlocks();

            if (cycles.empty()) {
                break;
            }

            reports.push_back(recover(cycles.front()));
        }

        return reports;
    }

    void displayState() const {
        cout << "\nTRANSACTION STATUS\n";

        for (const auto& entry : transactions) {
            const Transaction& tx = entry.second;

            cout << tx.id << " | "
                 << stateName(tx.state)
                 << " | held: ";

            for (const auto& name : tx.heldResources) {
                cout << name << " ";
            }

            cout << "| waiting: " << tx.waitingFor << '\n';
        }

        cout << "\nRESOURCE STATUS\n";

        for (const auto& entry : resources) {
            const Resource& resource = entry.second;

            cout << resource.name
                 << " | owner: "
                 << (resource.owner.empty()
                         ? "NONE"
                         : resource.owner)
                 << " | queue: ";

            for (const string& id : resource.waitQueue) {
                cout << id << " ";
            }

            cout << '\n';
        }

        cout << "\nWAIT-FOR GRAPH\n";

        auto graph = buildWaitForGraph();

        for (const auto& entry : graph) {
            cout << entry.first << " -> ";

            for (const string& owner : entry.second) {
                cout << owner << " ";
            }

            cout << '\n';
        }
    }
};

void detectionScenario() {
    cout << "\n====================================\n";
    cout << "DEADLOCK DETECTION AND RECOVERY\n";
    cout << "====================================\n";

    ResourceManager manager;

    manager.addResource("DATABASE", 1);
    manager.addResource("FILE", 2);

    manager.beginTransaction("T1");
    manager.beginTransaction("T2");

    manager.acquire("T1", "DATABASE");
    manager.acquire("T2", "FILE");

    manager.acquire("T1", "FILE");
    manager.acquire("T2", "DATABASE");

    manager.displayState();

    auto cycles = manager.detectDeadlocks();

    cout << "\nDETECTED CYCLES\n";

    for (const auto& cycle : cycles) {
        for (const auto& id : cycle) {
            cout << id << " -> ";
        }

        cout << cycle.front() << '\n';
    }

    auto reports = manager.detectAndRecover();

    cout << "\nRECOVERY REPORTS: "
         << reports.size() << '\n';

    manager.displayState();

    for (const string& id : {"T1", "T2"}) {
        // Only active transactions can commit.
        try {
            manager.commit(id);
        } catch (const runtime_error&) {
            // Aborted transactions require no further action.
        }
    }

    manager.displayState();
}

void preventionScenario() {
    cout << "\n====================================\n";
    cout << "DEADLOCK PREVENTION\n";
    cout << "====================================\n";

    ResourceManager manager(true);

    manager.addResource("ACCOUNT", 1);
    manager.addResource("LEDGER", 2);
    manager.addResource("AUDIT", 3);

    manager.beginTransaction("PAYMENT");

    manager.acquire("PAYMENT", "ACCOUNT");
    manager.acquire("PAYMENT", "LEDGER");

    try {
        manager.acquire("PAYMENT", "ACCOUNT");
        manager.acquire("PAYMENT", "AUDIT");
    } catch (const runtime_error& error) {
        cout << "[PREVENTION] "
             << error.what() << '\n';
    }

    manager.commit("PAYMENT");
}

void validationScenario() {
    cout << "\n====================================\n";
    cout << "VALIDATION AND ERROR HANDLING\n";
    cout << "====================================\n";

    ResourceManager manager;

    manager.addResource("CACHE", 1);
    manager.beginTransaction("T3");

    try {
        manager.acquire("T3", "UNKNOWN");
    } catch (const exception& error) {
        cout << "[VALIDATION] "
             << error.what() << '\n';
    }

    try {
        manager.release("T3", "CACHE");
    } catch (const exception& error) {
        cout << "[VALIDATION] "
             << error.what() << '\n';
    }

    manager.commit("T3");
}

int main() {
    try {
        detectionScenario();
        preventionScenario();
        validationScenario();

        cout << "\nAll C++17 scenarios completed.\n";
    } catch (const exception& error) {
        cerr << "[FATAL] " << error.what() << '\n';
        return 1;
    }

    return 0;
}
