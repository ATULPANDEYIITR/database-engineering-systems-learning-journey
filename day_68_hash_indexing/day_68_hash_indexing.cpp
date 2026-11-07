#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <list>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

class HashIndexError : public runtime_error {
public:
    explicit HashIndexError(const string& message)
        : runtime_error(message) {}
};

struct Transaction {
    string transactionId;
    string accountId;
    double amount;
    string status;
};

struct IndexStatistics {
    size_t capacity;
    size_t size;
    double loadFactor;
    size_t occupiedBuckets;
    size_t maximumChainLength;
    size_t collisions;
};

/*
 * Separate-chaining hash index for transaction records.
 *
 * Each bucket stores a linked list of key-value pairs.
 * Rehashing recalculates bucket positions after resizing.
 */
template <typename Key, typename Value,
          typename Hash = hash<Key>>
class ChainedHashIndex {
private:
    vector<list<pair<Key, Value>>> buckets;
    size_t currentSize = 0;
    double maxLoadFactor;
    size_t collisionCount = 0;
    Hash hasher;

    size_t bucketIndex(const Key& key) const {
        return hasher(key) % buckets.size();
    }

    void validateCapacity(size_t capacity) const {
        if (capacity < 2) {
            throw invalid_argument(
                "Capacity must be at least 2."
            );
        }
    }

public:
    explicit ChainedHashIndex(
        size_t capacity = 8,
        double loadFactor = 0.75
    ) : buckets(capacity), maxLoadFactor(loadFactor) {

        validateCapacity(capacity);

        if (loadFactor < 0.25 || loadFactor > 2.0) {
            throw invalid_argument(
                "Invalid maximum load factor."
            );
        }
    }

    size_t size() const {
        return currentSize;
    }

    size_t capacity() const {
        return buckets.size();
    }

    double loadFactor() const {
        return static_cast<double>(currentSize) /
               buckets.size();
    }

    void insert(const Key& key, const Value& value) {
        size_t index = bucketIndex(key);

        for (auto& entry : buckets[index]) {
            if (entry.first == key) {
                entry.second = value;
                return;
            }
        }

        if (
            static_cast<double>(currentSize + 1) /
            buckets.size() > maxLoadFactor
        ) {
            rehash(buckets.size() * 2);
            index = bucketIndex(key);
        }

        if (!buckets[index].empty()) {
            collisionCount++;
        }

        buckets[index].emplace_back(key, value);
        currentSize++;
    }

    optional<Value> find(const Key& key) const {
        const size_t index = bucketIndex(key);

        for (const auto& entry : buckets[index]) {
            if (entry.first == key) {
                return entry.second;
            }
        }

        return nullopt;
    }

    Value get(const Key& key) const {
        auto result = find(key);

        if (!result.has_value()) {
            throw HashIndexError("Key not found.");
        }

        return result.value();
    }

    bool contains(const Key& key) const {
        return find(key).has_value();
    }

    bool erase(const Key& key) {
        const size_t index = bucketIndex(key);
        auto& bucket = buckets[index];

        auto position = find_if(
            bucket.begin(),
            bucket.end(),
            [&key](const auto& entry) {
                return entry.first == key;
            }
        );

        if (position == bucket.end()) {
            return false;
        }

        bucket.erase(position);
        currentSize--;

        return true;
    }

    void rehash(size_t newCapacity) {
        validateCapacity(newCapacity);

        auto oldBuckets = move(buckets);

        buckets.clear();
        buckets.resize(newCapacity);
        currentSize = 0;

        for (const auto& bucket : oldBuckets) {
            for (const auto& entry : bucket) {
                const size_t index = bucketIndex(entry.first);

                buckets[index].push_back(entry);
                currentSize++;
            }
        }
    }

    IndexStatistics statistics() const {
        size_t occupied = 0;
        size_t maximumChain = 0;

        for (const auto& bucket : buckets) {
            if (!bucket.empty()) {
                occupied++;
            }

            maximumChain = max(
                maximumChain,
                bucket.size()
            );
        }

        return {
            buckets.size(),
            currentSize,
            loadFactor(),
            occupied,
            maximumChain,
            collisionCount
        };
    }

    void display() const {
        for (size_t i = 0; i < buckets.size(); i++) {
            cout << "Bucket " << i << ": ";

            for (const auto& entry : buckets[i]) {
                cout << "[" << entry.first << "] ";
            }

            cout << '\n';
        }
    }
};


/*
 * Open addressing using linear probing.
 *
 * Deleted slots are represented separately from empty slots.
 * This preserves the search path for keys inserted after collisions.
 */
template <typename Key, typename Value,
          typename Hash = hash<Key>>
class LinearProbingIndex {
private:
    struct Slot {
        enum class State {
            EMPTY,
            OCCUPIED,
            DELETED
        };

        State state = State::EMPTY;
        Key key{};
        Value value{};
    };

    vector<Slot> slots;
    size_t currentSize = 0;
    size_t deletedCount = 0;
    Hash hasher;

    size_t indexFor(const Key& key) const {
        return hasher(key) % slots.size();
    }

public:
    explicit LinearProbingIndex(size_t capacity = 8)
        : slots(capacity) {

        if (capacity < 2) {
            throw invalid_argument(
                "Capacity must be at least 2."
            );
        }
    }

    size_t size() const {
        return currentSize;
    }

    void insert(const Key& key, const Value& value) {
        if (
            static_cast<double>(
                currentSize + deletedCount + 1
            ) / slots.size() > 0.65
        ) {
            resize(slots.size() * 2);
        }

        size_t start = indexFor(key);
        optional<size_t> firstDeleted;

        for (size_t offset = 0; offset < slots.size(); offset++) {
            size_t index = (start + offset) % slots.size();
            Slot& slot = slots[index];

            if (slot.state == Slot::State::OCCUPIED) {
                if (slot.key == key) {
                    slot.value = value;
                    return;
                }
                continue;
            }

            if (slot.state == Slot::State::DELETED) {
                if (!firstDeleted.has_value()) {
                    firstDeleted = index;
                }
                continue;
            }

            const size_t target = firstDeleted.value_or(index);

            if (firstDeleted.has_value()) {
                deletedCount--;
            }

            slots[target].key = key;
            slots[target].value = value;
            slots[target].state = Slot::State::OCCUPIED;

            currentSize++;
            return;
        }

        if (firstDeleted.has_value()) {
            Slot& slot = slots[firstDeleted.value()];

            slot.key = key;
            slot.value = value;
            slot.state = Slot::State::OCCUPIED;

            deletedCount--;
            currentSize++;
            return;
        }

        resize(slots.size() * 2);
        insert(key, value);
    }

    optional<Value> find(const Key& key) const {
        const size_t start = indexFor(key);

        for (size_t offset = 0; offset < slots.size(); offset++) {
            const size_t index = (start + offset) % slots.size();
            const Slot& slot = slots[index];

            if (slot.state == Slot::State::EMPTY) {
                return nullopt;
            }

            if (
                slot.state == Slot::State::OCCUPIED &&
                slot.key == key
            ) {
                return slot.value;
            }
        }

        return nullopt;
    }

    bool erase(const Key& key) {
        const size_t start = indexFor(key);

        for (size_t offset = 0; offset < slots.size(); offset++) {
            const size_t index = (start + offset) % slots.size();
            Slot& slot = slots[index];

            if (slot.state == Slot::State::EMPTY) {
                return false;
            }

            if (
                slot.state == Slot::State::OCCUPIED &&
                slot.key == key
            ) {
                slot.state = Slot::State::DELETED;
                currentSize--;
                deletedCount++;
                return true;
            }
        }

        return false;
    }

    void resize(size_t newCapacity) {
        vector<pair<Key, Value>> entries;

        for (const Slot& slot : slots) {
            if (slot.state == Slot::State::OCCUPIED) {
                entries.emplace_back(slot.key, slot.value);
            }
        }

        slots.clear();
        slots.resize(newCapacity);

        currentSize = 0;
        deletedCount = 0;

        for (const auto& entry : entries) {
            insert(entry.first, entry.second);
        }
    }
};


/*
 * Enterprise transaction directory.
 * The unique transaction ID is the hash-index key.
 */
class TransactionDirectory {
private:
    ChainedHashIndex<string, Transaction> index;

public:
    TransactionDirectory()
        : index(4, 0.75) {}

    void registerTransaction(const Transaction& transaction) {
        if (
            transaction.transactionId.empty() ||
            transaction.accountId.empty()
        ) {
            throw invalid_argument(
                "Transaction and account IDs are required."
            );
        }

        if (
            !isfinite(transaction.amount) ||
            transaction.amount < 0
        ) {
            throw invalid_argument(
                "Transaction amount must be finite and non-negative."
            );
        }

        static const vector<string> allowedStatuses = {
            "PENDING",
            "APPROVED",
            "REJECTED",
            "SETTLED"
        };

        if (
            find(
                allowedStatuses.begin(),
                allowedStatuses.end(),
                transaction.status
            ) == allowedStatuses.end()
        ) {
            throw invalid_argument("Invalid transaction status.");
        }

        index.insert(
            transaction.transactionId,
            transaction
        );
    }

    optional<Transaction> findTransaction(
        const string& transactionId
    ) const {
        return index.find(transactionId);
    }

    bool removeTransaction(const string& transactionId) {
        return index.erase(transactionId);
    }

    void printStatistics() const {
        const auto stats = index.statistics();

        cout << "\nTRANSACTION INDEX STATISTICS\n";
        cout << "Capacity: " << stats.capacity << '\n';
        cout << "Records: " << stats.size << '\n';
        cout << "Load factor: " << fixed
             << setprecision(2) << stats.loadFactor << '\n';
        cout << "Occupied buckets: "
             << stats.occupiedBuckets << '\n';
        cout << "Maximum chain length: "
             << stats.maximumChainLength << '\n';
        cout << "Collisions: " << stats.collisions << '\n';
    }
};


void demonstrateStandardHashMap() {
    cout << "\nSTANDARD STL HASH MAP\n";

    unordered_map<string, string> employeeDepartments;

    employeeDepartments.emplace("EMP-101", "Engineering");
    employeeDepartments.emplace("EMP-102", "Security");
    employeeDepartments.emplace("EMP-103", "Research");

    auto result = employeeDepartments.find("EMP-102");

    if (result != employeeDepartments.end()) {
        cout << "Employee department: "
             << result->second << '\n';
    }

    cout << "Bucket count: "
         << employeeDepartments.bucket_count() << '\n';

    cout << "Load factor: "
         << employeeDepartments.load_factor() << '\n';
}


void runTests() {
    ChainedHashIndex<string, int> index(2);

    index.insert("A", 10);
    index.insert("B", 20);
    index.insert("A", 15);

    assert(index.size() == 2);
    assert(index.get("A") == 15);
    assert(index.get("B") == 20);

    assert(index.erase("A"));
    assert(!index.contains("A"));

    LinearProbingIndex<string, int> probing(4);

    probing.insert("A", 1);
    probing.insert("B", 2);

    assert(probing.erase("A"));

    probing.insert("C", 3);

    assert(probing.find("B").value() == 2);
    assert(probing.find("C").value() == 3);

    cout << "\nAll tests passed.\n";
}


int main() {
    try {
        cout << "HASH INDEXING: TRANSACTION MANAGEMENT\n";

        demonstrateStandardHashMap();

        cout << "\nSEPARATE CHAINING\n";

        TransactionDirectory directory;

        vector<Transaction> transactions = {
            {"TX-1001", "ACC-101", 12500.50, "APPROVED"},
            {"TX-1002", "ACC-102", 8500.00, "PENDING"},
            {"TX-1003", "ACC-103", 24000.75, "SETTLED"},
            {"TX-1004", "ACC-104", 5200.00, "REJECTED"},
            {"TX-1005", "ACC-105", 17200.00, "APPROVED"}
        };

        for (const auto& transaction : transactions) {
            directory.registerTransaction(transaction);
        }

        auto transaction = directory.findTransaction("TX-1003");

        if (transaction.has_value()) {
            cout << "Found transaction: "
                 << transaction->transactionId << '\n';

            cout << "Account: "
                 << transaction->accountId << '\n';

            cout << "Amount: "
                 << transaction->amount << '\n';
        }

        directory.removeTransaction("TX-1002");

        directory.printStatistics();

        cout << "\nOPEN ADDRESSING\n";

        LinearProbingIndex<string, string> openIndex(8);

        openIndex.insert("ACC-101", "ACTIVE");
        openIndex.insert("ACC-102", "SUSPENDED");
        openIndex.insert("ACC-103", "ACTIVE");

        openIndex.erase("ACC-102");
        openIndex.insert("ACC-104", "ACTIVE");

        cout << "ACC-104: "
             << openIndex.find("ACC-104").value() << '\n';

        runTests();

        cout << "\nCOMPLEXITY\n";
        cout << "Average lookup: O(1)\n";
        cout << "Average insertion: O(1)\n";
        cout << "Average deletion: O(1)\n";
        cout << "Worst-case lookup: O(n)\n";
        cout << "Rehashing: O(n)\n";

    } catch (const exception& error) {
        cerr << "ERROR: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
