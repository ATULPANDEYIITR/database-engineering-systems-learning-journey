#include <algorithm>
#include <cstdint>
#include <exception>
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

enum class IsolationLevel {
    ReadUncommitted,
    ReadCommitted,
    RepeatableRead,
    Serializable
};

enum class TransactionState {
    Active,
    Committed,
    RolledBack,
    Failed
};

string isolationName(IsolationLevel level) {
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

struct Record {
    int id;
    double balance;
    uint64_t version;
};

struct Transaction {
    string id;
    IsolationLevel isolation;
    TransactionState state = TransactionState::Active;

    map<int, Record> snapshot;
    map<int, Record> writes;
    map<int, uint64_t> readVersions;
};

class DatabaseException : public runtime_error {
public:
    using runtime_error::runtime_error;
};

class WriteConflict : public DatabaseException {
public:
    using DatabaseException::DatabaseException;
};

class SerializationConflict : public DatabaseException {
public:
    using DatabaseException::DatabaseException;
};

class Database {
private:
    map<int, Record> records;

    void ensureActive(const Transaction& tx) const {
        if (tx.state != TransactionState::Active) {
            throw DatabaseException(
                "Transaction is not active: " + tx.id
            );
        }
    }

public:
    Database() {
        records.emplace(1, Record{1, 1000.0, 1});
        records.emplace(2, Record{2, 2000.0, 1});
    }

    Transaction begin(
        const string& id,
        IsolationLevel isolation
    ) const {
        Transaction tx;
        tx.id = id;
        tx.isolation = isolation;
        tx.snapshot = records;

        cout << "\n[BEGIN] " << id
             << " | " << isolationName(isolation) << '\n';

        return tx;
    }

    Record read(Transaction& tx, int recordId) const {
        ensureActive(tx);

        auto current = records.find(recordId);

        if (current == records.end()) {
            throw DatabaseException("Record does not exist.");
        }

        Record result;

        if (tx.writes.count(recordId)) {
            result = tx.writes.at(recordId);
        } else if (
            tx.isolation == IsolationLevel::ReadCommitted ||
            tx.isolation == IsolationLevel::ReadUncommitted
        ) {
            result = current->second;
        } else {
            result = tx.snapshot.at(recordId);
        }

        tx.readVersions.emplace(recordId, result.version);

        cout << "[READ] " << tx.id
             << " | Account " << recordId
             << " | Balance " << result.balance
             << " | Version " << result.version << '\n';

        return result;
    }

    void write(
        Transaction& tx,
        int recordId,
        double balance
    ) {
        ensureActive(tx);

        if (balance < 0) {
            throw DatabaseException("Negative balance rejected.");
        }

        auto it = tx.snapshot.find(recordId);

        if (it == tx.snapshot.end()) {
            throw DatabaseException("Unknown account.");
        }

        Record base = tx.writes.count(recordId)
            ? tx.writes.at(recordId)
            : it->second;

        tx.writes[recordId] = {
            recordId,
            balance,
            base.version
        };

        cout << "[WRITE] " << tx.id
             << " | Account " << recordId
             << " | New balance " << balance << '\n';
    }

    void commit(Transaction& tx) {
        ensureActive(tx);

        // Validate every pending write before changing any record.
        for (const auto& [id, pending] : tx.writes) {
            const Record& current = records.at(id);

            if (current.version != pending.version) {
                tx.state = TransactionState::Failed;
                throw WriteConflict(
                    "Concurrent modification of account " +
                    to_string(id)
                );
            }
        }

        if (tx.isolation == IsolationLevel::Serializable) {
            for (const auto& [id, expected] : tx.readVersions) {
                if (records.at(id).version != expected) {
                    tx.state = TransactionState::Failed;
                    throw SerializationConflict(
                        "Serializable validation failed for account " +
                        to_string(id)
                    );
                }
            }
        }

        for (const auto& [id, pending] : tx.writes) {
            Record& current = records.at(id);

            current.balance = pending.balance;
            ++current.version;
        }

        tx.state = TransactionState::Committed;
        cout << "[COMMIT] " << tx.id << '\n';
    }

    void rollback(Transaction& tx) const {
        ensureActive(tx);

        tx.writes.clear();
        tx.state = TransactionState::RolledBack;

        cout << "[ROLLBACK] " << tx.id << '\n';
    }

    void display() const {
        cout << "\nDATABASE STATE\n";

        for (const auto& [id, record] : records) {
            cout << "Account " << id
                 << " | Balance " << fixed << setprecision(2)
                 << record.balance
                 << " | Version " << record.version << '\n';
        }
    }
};

void experimentNonRepeatableRead() {
    cout << "\n=== NON-REPEATABLE READ ===\n";

    Database db;

    auto reader = db.begin(
        "T1",
        IsolationLevel::ReadCommitted
    );

    auto writer = db.begin(
        "T2",
        IsolationLevel::ReadCommitted
    );

    Record first = db.read(reader, 1);

    db.write(writer, 1, 1500.0);
    db.commit(writer);

    Record second = db.read(reader, 1);

    cout << "First read:  " << first.balance << '\n';
    cout << "Second read: " << second.balance << '\n';

    cout << "Non-repeatable read: "
         << boolalpha
         << (first.balance != second.balance) << '\n';

    db.commit(reader);
    db.display();
}

void experimentRepeatableRead() {
    cout << "\n=== REPEATABLE READ ===\n";

    Database db;

    auto reader = db.begin(
        "T3",
        IsolationLevel::RepeatableRead
    );

    auto writer = db.begin(
        "T4",
        IsolationLevel::ReadCommitted
    );

    Record first = db.read(reader, 1);

    db.write(writer, 1, 1800.0);
    db.commit(writer);

    Record second = db.read(reader, 1);

    cout << "First read:  " << first.balance << '\n';
    cout << "Second read: " << second.balance << '\n';

    cout << "Stable snapshot: "
         << boolalpha
         << (first.balance == second.balance) << '\n';

    db.commit(reader);
    db.display();
}

void experimentConcurrentWriters() {
    cout << "\n=== CONCURRENT WRITE CONFLICT ===\n";

    Database db;

    auto first = db.begin(
        "T5",
        IsolationLevel::RepeatableRead
    );

    auto second = db.begin(
        "T6",
        IsolationLevel::RepeatableRead
    );

    db.read(first, 1);
    db.read(second, 1);

    db.write(first, 1, 1200.0);
    db.write(second, 1, 1300.0);

    db.commit(first);

    try {
        db.commit(second);
    } catch (const WriteConflict& error) {
        cout << "[REJECTED] " << error.what() << '\n';
    }

    db.display();
}

void experimentSerializable() {
    cout << "\n=== SERIALIZABLE VALIDATION ===\n";

    Database db;

    auto reader = db.begin(
        "T7",
        IsolationLevel::Serializable
    );

    auto writer = db.begin(
        "T8",
        IsolationLevel::ReadCommitted
    );

    db.read(reader, 1);
    db.read(writer, 1);

    db.write(writer, 1, 2200.0);
    db.commit(writer);

    try {
        db.commit(reader);
    } catch (const SerializationConflict& error) {
        cout << "[SERIALIZATION FAILURE] "
             << error.what() << '\n';
    }

    db.display();
}

void experimentRollback() {
    cout << "\n=== ROLLBACK ===\n";

    Database db;

    auto tx = db.begin(
        "T9",
        IsolationLevel::ReadCommitted
    );

    db.write(tx, 1, 500.0);
    db.rollback(tx);

    db.display();
}

int main() {
    try {
        experimentNonRepeatableRead();
        experimentRepeatableRead();
        experimentConcurrentWriters();
        experimentSerializable();
        experimentRollback();

        cout << "\nALL EXPERIMENTS COMPLETED.\n";
    } catch (const exception& error) {
        cerr << "FATAL ERROR: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
