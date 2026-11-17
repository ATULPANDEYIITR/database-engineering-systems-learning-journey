#include <algorithm>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * Database Transaction Isolation Engine
 *
 * C++17 implementation of:
 * - Transaction modeling
 * - Isolation-level semantics
 * - Versioned database records
 * - Concurrent transaction schedules
 * - Conflict detection
 * - Lost-update detection
 * - Non-repeatable read detection
 * - Conflict serializability analysis
 *
 * The schedule analyzer operates on explicit transaction operations.
 */

enum class IsolationLevel {
    ReadUncommitted,
    ReadCommitted,
    RepeatableRead,
    Serializable
};

enum class OperationType {
    Read,
    Write,
    Commit,
    Rollback
};

enum class TransactionState {
    Active,
    Committed,
    Aborted
};

struct Operation {
    int transactionId;
    OperationType type;
    std::string key;
    int value = 0;
};

struct VersionedValue {
    int value;
    int version;
};

struct Transaction {
    int id;
    IsolationLevel isolation;
    TransactionState state = TransactionState::Active;

    std::map<std::string, int> writes;
    std::map<std::string, int> readVersions;
    std::map<std::string, int> writeVersions;
    std::map<std::string, VersionedValue> snapshot;
};

class TransactionException : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class WriteConflict : public TransactionException {
public:
    using TransactionException::TransactionException;
};

class SerializationFailure : public TransactionException {
public:
    using TransactionException::TransactionException;
};

std::string toString(IsolationLevel level) {
    switch (level) {
        case IsolationLevel::ReadUncommitted:
            return "READ UNCOMMITTED";
        case IsolationLevel::ReadCommitted:
            return "READ COMMITTED";
        case IsolationLevel::RepeatableRead:
            return "REPEATABLE READ";
        case IsolationLevel::Serializable:
            return "SERIALIZABLE";
    }

    return "UNKNOWN";
}

class Database {
private:
    std::map<std::string, VersionedValue> records;
    std::unordered_map<int, Transaction> transactions;
    int nextTransactionId = 1;
    int nextVersion = 1;

public:
    explicit Database(
        const std::map<std::string, int>& initialData
    ) {
        for (const auto& [key, value] : initialData) {
            records[key] = {value, nextVersion++};
        }
    }

    int begin(IsolationLevel isolation) {
        Transaction transaction;

        transaction.id = nextTransactionId++;
        transaction.isolation = isolation;

        if (
            isolation == IsolationLevel::RepeatableRead ||
            isolation == IsolationLevel::Serializable
        ) {
            transaction.snapshot = records;
        }

        const int id = transaction.id;

        transactions.emplace(id, std::move(transaction));

        return id;
    }

    Transaction& getTransaction(int id) {
        auto iterator = transactions.find(id);

        if (iterator == transactions.end()) {
            throw TransactionException("Unknown transaction");
        }

        Transaction& transaction = iterator->second;

        if (transaction.state != TransactionState::Active) {
            throw TransactionException("Transaction is not active");
        }

        return transaction;
    }

    int read(int transactionId, const std::string& key) {
        Transaction& transaction = getTransaction(transactionId);

        auto localWrite = transaction.writes.find(key);

        if (localWrite != transaction.writes.end()) {
            return localWrite->second;
        }

        const auto& view =
            (
                transaction.isolation == IsolationLevel::RepeatableRead ||
                transaction.isolation == IsolationLevel::Serializable
            )
            ? transaction.snapshot
            : records;

        auto iterator = view.find(key);

        if (iterator == view.end()) {
            throw TransactionException("Record does not exist: " + key);
        }

        transaction.readVersions.emplace(
            key,
            iterator->second.version
        );

        return iterator->second.value;
    }

    void write(
        int transactionId,
        const std::string& key,
        int value
    ) {
        Transaction& transaction = getTransaction(transactionId);

        auto iterator = records.find(key);

        if (iterator == records.end()) {
            throw TransactionException("Unknown record: " + key);
        }

        transaction.writes[key] = value;

        transaction.writeVersions.emplace(
            key,
            iterator->second.version
        );
    }

    void commit(int transactionId) {
        Transaction& transaction = getTransaction(transactionId);

        for (const auto& [key, originalVersion] :
             transaction.writeVersions) {

            auto iterator = records.find(key);

            if (
                iterator == records.end() ||
                iterator->second.version != originalVersion
            ) {
                rollback(transactionId);
                throw WriteConflict(
                    "Concurrent write conflict on " + key
                );
            }
        }

        if (transaction.isolation == IsolationLevel::Serializable) {
            for (const auto& [key, originalVersion] :
                 transaction.readVersions) {

                if (transaction.writes.count(key)) {
                    continue;
                }

                auto iterator = records.find(key);

                if (
                    iterator == records.end() ||
                    iterator->second.version != originalVersion
                ) {
                    rollback(transactionId);

                    throw SerializationFailure(
                        "Read dependency changed: " + key
                    );
                }
            }
        }

        // Apply all writes after validation.
        for (const auto& [key, value] : transaction.writes) {
            records[key] = {value, nextVersion++};
        }

        transaction.state = TransactionState::Committed;
    }

    void rollback(int transactionId) {
        Transaction& transaction = getTransaction(transactionId);

        transaction.writes.clear();
        transaction.state = TransactionState::Aborted;
    }

    void print() const {
        for (const auto& [key, record] : records) {
            std::cout << key
                      << " = " << record.value
                      << " (version " << record.version << ")\n";
        }
    }

    int value(const std::string& key) const {
        auto iterator = records.find(key);

        if (iterator == records.end()) {
            throw TransactionException("Unknown record");
        }

        return iterator->second.value;
    }
};

struct Conflict {
    int from;
    int to;
    std::string key;
};

class SerializationGraph {
private:
    std::set<int> transactions;
    std::vector<Conflict> conflicts;

public:
    void addTransaction(int id) {
        transactions.insert(id);
    }

    void addOperation(const Operation& first,
                      const Operation& second) {
        if (first.transactionId == second.transactionId) {
            return;
        }

        if (first.type == OperationType::Commit ||
            first.type == OperationType::Rollback ||
            second.type == OperationType::Commit ||
            second.type == OperationType::Rollback) {
            return;
        }

        if (first.key != second.key) {
            return;
        }

        // Two reads do not create a conflict.
        if (
            first.type == OperationType::Read &&
            second.type == OperationType::Read
        ) {
            return;
        }

        conflicts.push_back({
            first.transactionId,
            second.transactionId,
            first.key
        });
    }

    bool isConflictSerializable() const {
        std::map<int, int> indegree;
        std::map<int, std::vector<int>> graph;

        for (int id : transactions) {
            indegree[id] = 0;
        }

        std::set<std::pair<int, int>> uniqueEdges;

        for (const auto& conflict : conflicts) {
            auto edge = std::make_pair(
                conflict.from,
                conflict.to
            );

            if (uniqueEdges.insert(edge).second) {
                graph[conflict.from].push_back(conflict.to);
                indegree[conflict.to]++;
            }
        }

        // Kahn's topological sorting algorithm.
        std::vector<int> queue;

        for (const auto& [id, degree] : indegree) {
            if (degree == 0) {
                queue.push_back(id);
            }
        }

        std::size_t processed = 0;

        while (!queue.empty()) {
            int current = queue.back();
            queue.pop_back();
            processed++;

            for (int next : graph[current]) {
                if (--indegree[next] == 0) {
                    queue.push_back(next);
                }
            }
        }

        return processed == transactions.size();
    }

    void printConflicts() const {
        std::cout << "\nPrecedence graph edges:\n";

        for (const auto& conflict : conflicts) {
            std::cout << "T" << conflict.from
                      << " -> T" << conflict.to
                      << " on " << conflict.key << '\n';
        }

        if (conflicts.empty()) {
            std::cout << "No conflicting operations.\n";
        }
    }
};

void demonstrateReadCommitted() {
    std::cout << "\n1. READ COMMITTED\n";

    Database db({{"balance", 1000}});

    int reader = db.begin(IsolationLevel::ReadCommitted);
    int writer = db.begin(IsolationLevel::ReadCommitted);

    int first = db.read(reader, "balance");

    db.write(writer, "balance", 800);
    db.commit(writer);

    int second = db.read(reader, "balance");

    std::cout << "First read: " << first << '\n';
    std::cout << "Second read: " << second << '\n';

    if (first == second) {
        throw std::runtime_error("Expected non-repeatable read");
    }

    db.rollback(reader);
}

void demonstrateRepeatableRead() {
    std::cout << "\n2. REPEATABLE READ\n";

    Database db({{"inventory", 100}});

    int reader = db.begin(IsolationLevel::RepeatableRead);
    int writer = db.begin(IsolationLevel::ReadCommitted);

    int first = db.read(reader, "inventory");

    db.write(writer, "inventory", 75);
    db.commit(writer);

    int second = db.read(reader, "inventory");

    std::cout << "First read: " << first << '\n';
    std::cout << "Second read: " << second << '\n';

    if (first != second) {
        throw std::runtime_error("Snapshot consistency failure");
    }

    db.commit(reader);
}

void demonstrateWriteConflict() {
    std::cout << "\n3. WRITE CONFLICT\n";

    Database db({{"stock", 50}});

    int first = db.begin(IsolationLevel::RepeatableRead);
    int second = db.begin(IsolationLevel::RepeatableRead);

    db.write(first, "stock", 40);
    db.write(second, "stock", 30);

    db.commit(first);

    try {
        db.commit(second);
        throw std::runtime_error("Expected write conflict");
    } catch (const WriteConflict& error) {
        std::cout << "Detected: " << error.what() << '\n';
    }

    std::cout << "Committed stock: "
              << db.value("stock") << '\n';
}

void demonstrateSerializable() {
    std::cout << "\n4. SERIALIZABLE VALIDATION\n";

    Database db({{"account", 1000}});

    int reader = db.begin(IsolationLevel::Serializable);
    int writer = db.begin(IsolationLevel::ReadCommitted);

    int observed = db.read(reader, "account");

    db.write(writer, "account", 700);
    db.commit(writer);

    std::cout << "Snapshot balance: " << observed << '\n';
    std::cout << "Current balance: "
              << db.value("account") << '\n';

    try {
        db.commit(reader);
        throw std::runtime_error("Expected serialization failure");
    } catch (const SerializationFailure& error) {
        std::cout << "Detected: " << error.what() << '\n';
    }
}

void demonstratePrecedenceGraph() {
    std::cout << "\n5. CONFLICT SERIALIZABILITY\n";

    SerializationGraph graph;

    graph.addTransaction(1);
    graph.addTransaction(2);
    graph.addTransaction(3);

    std::vector<Operation> schedule = {
        {1, OperationType::Read, "A"},
        {2, OperationType::Write, "A"},
        {1, OperationType::Write, "B"},
        {2, OperationType::Read, "B"},
        {3, OperationType::Read, "C"}
    };

    for (std::size_t i = 0; i < schedule.size(); ++i) {
        for (std::size_t j = i + 1; j < schedule.size(); ++j) {
            graph.addOperation(schedule[i], schedule[j]);
        }
    }

    graph.printConflicts();

    std::cout << "Conflict serializable: "
              << std::boolalpha
              << graph.isConflictSerializable()
              << '\n';
}

void demonstrateAtomicTransfer() {
    std::cout << "\n6. ATOMIC ACCOUNT TRANSFER\n";

    Database db({
        {"alice", 5000},
        {"bob", 3000}
    });

    int transaction = db.begin(IsolationLevel::Serializable);

    const int amount = 1000;

    int alice = db.read(transaction, "alice");
    int bob = db.read(transaction, "bob");

    if (amount <= 0 || alice < amount) {
        db.rollback(transaction);
        throw TransactionException("Invalid transfer");
    }

    db.write(transaction, "alice", alice - amount);
    db.write(transaction, "bob", bob + amount);

    db.commit(transaction);

    db.print();

    if (
        db.value("alice") + db.value("bob") != 8000
    ) {
        throw std::runtime_error("Account conservation failure");
    }
}

void printIsolationCharacteristics() {
    std::cout << "\n7. ISOLATION LEVELS\n";

    const std::vector<IsolationLevel> levels = {
        IsolationLevel::ReadUncommitted,
        IsolationLevel::ReadCommitted,
        IsolationLevel::RepeatableRead,
        IsolationLevel::Serializable
    };

    for (auto level : levels) {
        std::cout << std::left
                  << std::setw(22)
                  << toString(level)
                  << '\n';
    }

    std::cout
        << "\nPostgreSQL maps READ UNCOMMITTED to READ COMMITTED.\n";
}

int main() {
    try {
        std::cout
            << "DATABASE TRANSACTION ISOLATION ENGINE\n"
            << "======================================\n";

        demonstrateReadCommitted();
        demonstrateRepeatableRead();
        demonstrateWriteConflict();
        demonstrateSerializable();
        demonstratePrecedenceGraph();
        demonstrateAtomicTransfer();
        printIsolationCharacteristics();

        std::cout << "\nAll demonstrations completed.\n";
    } catch (const std::exception& error) {
        std::cerr << "Execution error: "
                  << error.what() << '\n';

        return 1;
    }

    return 0;
}
