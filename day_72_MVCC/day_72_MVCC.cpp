/*
 * MVCC: Multi-Version Concurrency Control
 *
 * C++17 repository-independent database governance engine.
 *
 * Implements:
 * - Version chains
 * - Snapshot visibility
 * - Transaction lifecycle
 * - Read/write sets
 * - Snapshot isolation
 * - Serializable validation
 * - Write-write conflict detection
 * - Atomic commit validation
 * - Row deletion
 * - Garbage collection
 * - Transaction statistics
 *
 * Compile:
 * g++ -std=c++17 -O2 -Wall -Wextra -pedantic mvcc.cpp -o mvcc
 */

#include <algorithm>
#include <cstdint>
#include <exception>
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
    READ_COMMITTED,
    SNAPSHOT,
    SERIALIZABLE
};

enum class TransactionState {
    ACTIVE,
    COMMITTED,
    ABORTED
};

class MVCCException : public runtime_error {
public:
    explicit MVCCException(const string& message)
        : runtime_error(message) {}
};

class WriteConflict : public MVCCException {
public:
    explicit WriteConflict(const string& message)
        : MVCCException(message) {}
};

class SerializationFailure : public MVCCException {
public:
    explicit SerializationFailure(const string& message)
        : MVCCException(message) {}
};

struct Version {
    string value;
    uint64_t xmin;
    optional<uint64_t> xmax;
    bool deleted;
    uint64_t timestamp;
};

struct Transaction {
    uint64_t id;
    IsolationLevel isolation;
    TransactionState state;

    set<uint64_t> snapshot;

    map<string, optional<string>> writes;
    map<string, optional<uint64_t>> reads;

    uint64_t startTimestamp;
};

class MVCCDatabase {
private:
    map<string, vector<Version>> rows_;

    map<uint64_t, Transaction> transactions_;

    set<uint64_t> active_;
    set<uint64_t> committed_;
    set<uint64_t> aborted_;

    uint64_t nextId_ = 1;
    uint64_t clock_ = 0;

    uint64_t tick() {
        return ++clock_;
    }

    Transaction& validate(Transaction& tx) {
        if (tx.state != TransactionState::ACTIVE) {
            throw MVCCException("Transaction is not active");
        }

        auto it = transactions_.find(tx.id);

        if (it == transactions_.end()) {
            throw MVCCException("Unknown transaction");
        }

        if (&it->second != &tx) {
            throw MVCCException("Invalid transaction reference");
        }

        return tx;
    }

    bool visible(
        const Version& version,
        const Transaction& tx
    ) const {
        bool creatorVisible =
            version.xmin == tx.id ||
            (
                tx.snapshot.count(version.xmin) == 0 &&
                committed_.count(version.xmin) > 0
            );

        if (!creatorVisible) {
            return false;
        }

        if (!version.xmax.has_value()) {
            return true;
        }

        const uint64_t deleter = version.xmax.value();

        if (deleter == tx.id) {
            return false;
        }

        if (tx.snapshot.count(deleter) > 0) {
            return true;
        }

        return committed_.count(deleter) == 0;
    }

    const Version* visibleVersion(
        const string& key,
        const Transaction& tx
    ) const {
        auto it = rows_.find(key);

        if (it == rows_.end()) {
            return nullptr;
        }

        const auto& chain = it->second;

        for (auto rit = chain.rbegin(); rit != chain.rend(); ++rit) {
            if (visible(*rit, tx)) {
                return rit->deleted ? nullptr : &(*rit);
            }
        }

        return nullptr;
    }

    void refreshSnapshot(Transaction& tx) {
        if (tx.isolation == IsolationLevel::READ_COMMITTED) {
            tx.snapshot = active_;
        }
    }

    void validateWrites(const Transaction& tx) const {
        for (const auto& [key, value] : tx.writes) {
            (void)value;

            auto it = rows_.find(key);

            const Version* latest = nullptr;

            if (it != rows_.end()) {
                const auto& chain = it->second;

                for (auto rit = chain.rbegin(); rit != chain.rend(); ++rit) {
                    if (committed_.count(rit->xmin)) {
                        latest = &(*rit);
                        break;
                    }
                }
            }

            optional<uint64_t> observed;

            auto readIt = tx.reads.find(key);

            if (readIt != tx.reads.end()) {
                observed = readIt->second;
            }

            optional<uint64_t> current;

            if (latest != nullptr) {
                current = latest->xmin;
            }

            if (current != observed) {
                throw WriteConflict(
                    "Concurrent modification detected for key: " + key
                );
            }
        }
    }

    void validateSerializable(const Transaction& tx) const {
        for (const auto& [key, observed] : tx.reads) {
            if (tx.writes.count(key)) {
                continue;
            }

            auto it = rows_.find(key);

            optional<uint64_t> latestId;

            if (it != rows_.end()) {
                for (
                    auto rit = it->second.rbegin();
                    rit != it->second.rend();
                    ++rit
                ) {
                    if (committed_.count(rit->xmin)) {
                        latestId = rit->xmin;
                        break;
                    }
                }
            }

            if (latestId != observed) {
                throw SerializationFailure(
                    "Serializable read validation failed: " + key
                );
            }
        }
    }

public:
    Transaction& begin(
        IsolationLevel isolation = IsolationLevel::SNAPSHOT
    ) {
        const uint64_t id = nextId_++;

        Transaction tx{
            id,
            isolation,
            TransactionState::ACTIVE,
            active_,
            {},
            {},
            tick()
        };

        auto [it, inserted] = transactions_.emplace(id, move(tx));

        if (!inserted) {
            throw MVCCException("Transaction allocation failed");
        }

        active_.insert(id);

        cout << "BEGIN transaction=" << id << '\n';

        return it->second;
    }

    optional<string> read(
        Transaction& tx,
        const string& key
    ) {
        validate(tx);
        refreshSnapshot(tx);

        const Version* version = visibleVersion(key, tx);

        if (tx.reads.count(key) == 0) {
            tx.reads[key] = version
                ? optional<uint64_t>(version->xmin)
                : nullopt;
        }

        if (version == nullptr) {
            cout << "READ " << key << " = NULL\n";
            return nullopt;
        }

        cout << "READ " << key
             << " = " << version->value
             << " version=" << version->xmin << '\n';

        return version->value;
    }

    void write(
        Transaction& tx,
        const string& key,
        const string& value
    ) {
        validate(tx);

        if (key.empty()) {
            throw invalid_argument("Key cannot be empty");
        }

        refreshSnapshot(tx);

        const Version* current = visibleVersion(key, tx);

        if (tx.reads.count(key) == 0) {
            tx.reads[key] = current
                ? optional<uint64_t>(current->xmin)
                : nullopt;
        }

        tx.writes[key] = value;

        cout << "BUFFER WRITE transaction="
             << tx.id << " key=" << key << '\n';
    }

    void erase(Transaction& tx, const string& key) {
        validate(tx);
        refreshSnapshot(tx);

        const Version* current = visibleVersion(key, tx);

        if (current == nullptr) {
            return;
        }

        if (tx.reads.count(key) == 0) {
            tx.reads[key] = current->xmin;
        }

        tx.writes[key] = nullopt;

        cout << "BUFFER DELETE key=" << key << '\n';
    }

    void commit(Transaction& tx) {
        validate(tx);

        try {
            validateWrites(tx);

            if (tx.isolation == IsolationLevel::SERIALIZABLE) {
                validateSerializable(tx);
            }

            // The database applies all writes only after validation.
            // In a production engine, WAL and crash recovery are
            // required for durable atomicity.

            for (const auto& [key, value] : tx.writes) {
                auto it = rows_.find(key);

                if (it != rows_.end()) {
                    for (
                        auto rit = it->second.rbegin();
                        rit != it->second.rend();
                        ++rit
                    ) {
                        if (
                            committed_.count(rit->xmin) &&
                            !rit->xmax.has_value()
                        ) {
                            rit->xmax = tx.id;
                            break;
                        }
                    }
                }
            }

            const uint64_t commitTimestamp = tick();

            for (const auto& [key, value] : tx.writes) {
                Version version{
                    value.value_or(""),
                    tx.id,
                    nullopt,
                    !value.has_value(),
                    commitTimestamp
                };

                rows_[key].push_back(move(version));
            }

            tx.state = TransactionState::COMMITTED;
            committed_.insert(tx.id);
            active_.erase(tx.id);

            cout << "COMMIT transaction=" << tx.id
                 << " writes=" << tx.writes.size() << '\n';

        } catch (...) {
            rollback(tx);
            throw;
        }
    }

    void rollback(Transaction& tx) {
        if (tx.state != TransactionState::ACTIVE) {
            return;
        }

        tx.writes.clear();

        tx.state = TransactionState::ABORTED;
        active_.erase(tx.id);
        aborted_.insert(tx.id);

        tick();

        cout << "ROLLBACK transaction=" << tx.id << '\n';
    }

    size_t vacuum() {
        const uint64_t horizon = active_.empty()
            ? nextId_
            : *active_.begin();

        size_t removed = 0;

        for (auto it = rows_.begin(); it != rows_.end();) {
            auto& chain = it->second;

            auto newEnd = remove_if(
                chain.begin(),
                chain.end(),
                [&](const Version& version) {
                    bool abortedCreator =
                        aborted_.count(version.xmin) > 0;

                    bool obsolete =
                        version.xmax.has_value() &&
                        committed_.count(version.xmax.value()) > 0 &&
                        version.xmax.value() < horizon;

                    if (abortedCreator || obsolete) {
                        ++removed;
                        return true;
                    }

                    return false;
                }
            );

            chain.erase(newEnd, chain.end());

            if (chain.empty()) {
                it = rows_.erase(it);
            } else {
                ++it;
            }
        }

        cout << "VACUUM removed=" << removed << '\n';

        return removed;
    }

    void inspect(const string& key) const {
        auto it = rows_.find(key);

        if (it == rows_.end()) {
            cout << "No versions for " << key << '\n';
            return;
        }

        cout << "\nVersion chain: " << key << '\n';

        for (const auto& version : it->second) {
            cout << "  value=" << version.value
                 << " xmin=" << version.xmin
                 << " xmax=";

            if (version.xmax.has_value()) {
                cout << version.xmax.value();
            } else {
                cout << "NULL";
            }

            cout << " deleted=" << boolalpha
                 << version.deleted << '\n';
        }
    }

    void statistics() const {
        size_t versions = 0;

        for (const auto& [key, chain] : rows_) {
            (void)key;
            versions += chain.size();
        }

        cout << "\nDatabase statistics\n"
             << "Keys: " << rows_.size() << '\n'
             << "Versions: " << versions << '\n'
             << "Active: " << active_.size() << '\n'
             << "Committed: " << committed_.size() << '\n'
             << "Aborted: " << aborted_.size() << '\n';
    }
};

int main() {
    try {
        MVCCDatabase database;

        cout << "\n=== INITIALIZATION ===\n";

        auto& setup = database.begin();

        database.write(setup, "account-101", "1000");
        database.write(setup, "account-102", "500");

        database.commit(setup);

        cout << "\n=== SNAPSHOT VISIBILITY ===\n";

        auto& reader = database.begin(
            IsolationLevel::SNAPSHOT
        );

        database.read(reader, "account-101");

        auto& writer = database.begin();

        database.write(writer, "account-101", "1200");
        database.commit(writer);

        cout << "Reader retains old snapshot:\n";

        database.read(reader, "account-101");

        database.commit(reader);

        cout << "\n=== NEW SNAPSHOT ===\n";

        auto& newReader = database.begin();

        database.read(newReader, "account-101");
        database.commit(newReader);

        cout << "\n=== WRITE CONFLICT ===\n";

        auto& first = database.begin();
        auto& second = database.begin();

        database.write(first, "account-102", "600");
        database.write(second, "account-102", "700");

        database.commit(first);

        try {
            database.commit(second);
        } catch (const WriteConflict& error) {
            cout << "Expected conflict: "
                 << error.what() << '\n';
        }

        cout << "\n=== READ COMMITTED ===\n";

        auto& rc = database.begin(
            IsolationLevel::READ_COMMITTED
        );

        database.read(rc, "account-101");

        auto& updater = database.begin();

        database.write(updater, "account-101", "1500");
        database.commit(updater);

        database.read(rc, "account-101");
        database.commit(rc);

        cout << "\n=== DELETE AND ROLLBACK ===\n";

        auto& deletion = database.begin();

        database.erase(deletion, "account-102");
        database.rollback(deletion);

        auto& verify = database.begin();

        database.read(verify, "account-102");
        database.commit(verify);

        cout << "\n=== VERSION INSPECTION ===\n";

        database.inspect("account-101");
        database.inspect("account-102");

        cout << "\n=== VACUUM ===\n";

        database.vacuum();

        database.statistics();

    } catch (const exception& error) {
        cerr << "Fatal database error: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}
