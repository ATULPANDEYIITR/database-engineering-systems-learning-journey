#include <algorithm>
#include <cmath>
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

/*
 * LSM Tree implementation in C++17.
 *
 * Scenario: High-volume IoT telemetry ingestion.
 *
 * Components:
 * - Memtable
 * - Sequence-numbered mutations
 * - Immutable SSTable runs
 * - Bloom filter
 * - Sparse index
 * - Tombstones
 * - Multi-level compaction
 * - Point and range queries
 * - Storage statistics
 */

enum class Operation {
    PUT,
    DELETE
};

struct Entry {
    std::string key;
    std::string value;
    std::uint64_t sequence;
    Operation operation;

    Entry(
        std::string k,
        std::string v,
        std::uint64_t s,
        Operation op
    ) : key(std::move(k)),
        value(std::move(v)),
        sequence(s),
        operation(op) {
        if (key.empty()) {
            throw std::invalid_argument("Empty key");
        }

        if (sequence == 0) {
            throw std::invalid_argument("Invalid sequence");
        }

        if (operation == Operation::DELETE && !value.empty()) {
            throw std::invalid_argument(
                "Tombstone cannot contain a value"
            );
        }
    }
};

class BloomFilter {
private:
    std::vector<bool> bits;
    std::size_t bitCount;
    std::size_t hashCount;

    static std::uint64_t hash(
        const std::string& value,
        std::uint64_t seed
    ) {
        std::uint64_t result = seed;

        for (unsigned char character : value) {
            result ^= character;
            result *= 1099511628211ULL;
        }

        return result;
    }

public:
    explicit BloomFilter(
        std::size_t capacity,
        double falsePositiveRate = 0.01
    ) {
        if (capacity == 0 ||
            falsePositiveRate <= 0 ||
            falsePositiveRate >= 1) {
            throw std::invalid_argument(
                "Invalid Bloom filter configuration"
            );
        }

        bitCount = std::max<std::size_t>(
            8,
            static_cast<std::size_t>(
                std::ceil(
                    -static_cast<double>(capacity) *
                    std::log(falsePositiveRate) /
                    (std::log(2.0) * std::log(2.0))
                )
            )
        );

        hashCount = std::max<std::size_t>(
            1,
            static_cast<std::size_t>(
                std::round(
                    static_cast<double>(bitCount) /
                    capacity * std::log(2.0)
                )
            )
        );

        bits.resize(bitCount, false);
    }

    void add(const std::string& key) {
        const auto first = hash(key, 1469598103934665603ULL);
        const auto second = hash(key, 1099511628211ULL) | 1ULL;

        for (std::size_t i = 0; i < hashCount; ++i) {
            const auto position =
                (first + i * second) % bitCount;

            bits[position] = true;
        }
    }

    bool mightContain(const std::string& key) const {
        const auto first = hash(key, 1469598103934665603ULL);
        const auto second = hash(key, 1099511628211ULL) | 1ULL;

        for (std::size_t i = 0; i < hashCount; ++i) {
            const auto position =
                (first + i * second) % bitCount;

            if (!bits[position]) {
                return false;
            }
        }

        return true;
    }
};

class SSTable {
private:
    std::uint64_t id;
    std::size_t level;
    std::vector<Entry> entries;
    BloomFilter bloom;
    std::vector<std::pair<std::string, std::size_t>> sparseIndex;
    std::size_t interval;

public:
    SSTable(
        std::uint64_t tableId,
        std::size_t tableLevel,
        std::vector<Entry> data,
        std::size_t indexInterval = 4
    ) :
        id(tableId),
        level(tableLevel),
        entries(std::move(data)),
        bloom(std::max<std::size_t>(entries.size(), 1)),
        interval(indexInterval) {

        if (entries.empty() || interval == 0) {
            throw std::invalid_argument(
                "Invalid SSTable construction"
            );
        }

        std::sort(
            entries.begin(),
            entries.end(),
            [](const Entry& a, const Entry& b) {
                return a.key < b.key;
            }
        );

        for (std::size_t i = 0; i < entries.size(); ++i) {
            if (i > 0 &&
                entries[i - 1].key == entries[i].key) {
                throw std::invalid_argument(
                    "Duplicate SSTable key"
                );
            }

            bloom.add(entries[i].key);

            if (i % interval == 0) {
                sparseIndex.emplace_back(
                    entries[i].key,
                    i
                );
            }
        }
    }

    std::uint64_t getId() const {
        return id;
    }

    std::size_t getLevel() const {
        return level;
    }

    const std::vector<Entry>& getEntries() const {
        return entries;
    }

    std::optional<Entry> get(
        const std::string& key
    ) const {
        if (
            key < entries.front().key ||
            key > entries.back().key ||
            !bloom.mightContain(key)
        ) {
            return std::nullopt;
        }

        auto it = std::upper_bound(
            sparseIndex.begin(),
            sparseIndex.end(),
            key,
            [](const std::string& value,
               const auto& index) {
                return value < index.first;
            }
        );

        std::size_t start = 0;

        if (it != sparseIndex.begin()) {
            --it;
            start = it->second;
        }

        const std::size_t end = std::min(
            start + interval,
            entries.size()
        );

        auto position = std::lower_bound(
            entries.begin() + start,
            entries.begin() + end,
            key,
            [](const Entry& entry, const std::string& value) {
                return entry.key < value;
            }
        );

        if (
            position != entries.begin() + end &&
            position->key == key
        ) {
            return *position;
        }

        return std::nullopt;
    }

    std::vector<Entry> rangeScan(
        const std::string& start,
        const std::string& end
    ) const {
        if (start > end) {
            throw std::invalid_argument("Invalid scan range");
        }

        std::vector<Entry> result;

        for (const auto& entry : entries) {
            if (entry.key >= start && entry.key <= end) {
                result.push_back(entry);
            }
        }

        return result;
    }
};

class LSMTree {
private:
    std::map<std::string, Entry> memtable;
    std::map<std::size_t, std::vector<SSTable>> levels;

    std::uint64_t sequence = 0;
    std::uint64_t tableSequence = 0;

    std::size_t memtableLimit;
    std::size_t levelCapacity;
    std::size_t indexInterval;

    std::uint64_t nextSequence() {
        if (sequence == UINT64_MAX) {
            throw std::overflow_error(
                "Sequence number exhausted"
            );
        }

        return ++sequence;
    }

    void checkCompaction(std::size_t level) {
        if (levels[level].size() >= levelCapacity) {
            compact(level);
        }
    }

public:
    explicit LSMTree(
        std::size_t memoryLimit = 4,
        std::size_t capacity = 3,
        std::size_t sparseInterval = 4
    ) :
        memtableLimit(memoryLimit),
        levelCapacity(capacity),
        indexInterval(sparseInterval) {

        if (
            memoryLimit == 0 ||
            capacity < 2 ||
            sparseInterval == 0
        ) {
            throw std::invalid_argument(
                "Invalid LSM configuration"
            );
        }

        levels[0] = {};
    }

    void put(
        const std::string& key,
        const std::string& value
    ) {
        if (key.empty()) {
            throw std::invalid_argument("Empty key");
        }

        Entry entry(
            key,
            value,
            nextSequence(),
            Operation::PUT
        );

        memtable[key] = std::move(entry);

        if (memtable.size() >= memtableLimit) {
            flush();
        }
    }

    void remove(const std::string& key) {
        if (key.empty()) {
            throw std::invalid_argument("Empty key");
        }

        Entry entry(
            key,
            "",
            nextSequence(),
            Operation::DELETE
        );

        memtable[key] = std::move(entry);

        if (memtable.size() >= memtableLimit) {
            flush();
        }
    }

    std::optional<std::string> get(
        const std::string& key
    ) const {
        std::optional<Entry> latest;

        auto memoryEntry = memtable.find(key);

        if (memoryEntry != memtable.end()) {
            latest = memoryEntry->second;
        }

        for (const auto& [level, tables] : levels) {
            for (const auto& table : tables) {
                auto candidate = table.get(key);

                if (
                    candidate &&
                    (!latest ||
                     candidate->sequence > latest->sequence)
                ) {
                    latest = candidate;
                }
            }
        }

        if (
            !latest ||
            latest->operation == Operation::DELETE
        ) {
            return std::nullopt;
        }

        return latest->value;
    }

    void flush() {
        if (memtable.empty()) {
            return;
        }

        std::vector<Entry> entries;

        for (const auto& [key, entry] : memtable) {
            entries.push_back(entry);
        }

        SSTable output(
            ++tableSequence,
            0,
            std::move(entries),
            indexInterval
        );

        // The immutable run is created before clearing memory.
        levels[0].push_back(std::move(output));
        memtable.clear();

        checkCompaction(0);
    }

    void compact(std::size_t level) {
        auto& inputs = levels[level];

        if (inputs.size() < 2) {
            return;
        }

        std::map<std::string, Entry> merged;

        for (const auto& table : inputs) {
            for (const auto& entry : table.getEntries()) {
                auto it = merged.find(entry.key);

                if (
                    it == merged.end() ||
                    entry.sequence > it->second.sequence
                ) {
                    merged[entry.key] = entry;
                }
            }
        }

        std::vector<Entry> outputEntries;

        for (const auto& [key, entry] : merged) {
            outputEntries.push_back(entry);
        }

        const std::size_t nextLevel = level + 1;

        SSTable output(
            ++tableSequence,
            nextLevel,
            std::move(outputEntries),
            indexInterval
        );

        // Tombstones are preserved because lower-level overlap
        // and snapshot visibility are not tracked by this model.
        inputs.clear();

        levels[nextLevel].push_back(std::move(output));

        checkCompaction(nextLevel);
    }

    std::map<std::string, std::string> rangeScan(
        const std::string& start,
        const std::string& end
    ) const {
        if (start > end) {
            throw std::invalid_argument("Invalid scan range");
        }

        std::map<std::string, Entry> latest;

        auto process = [&](const Entry& entry) {
            if (entry.key < start || entry.key > end) {
                return;
            }

            auto it = latest.find(entry.key);

            if (
                it == latest.end() ||
                entry.sequence > it->second.sequence
            ) {
                latest[entry.key] = entry;
            }
        };

        for (const auto& [key, entry] : memtable) {
            process(entry);
        }

        for (const auto& [level, tables] : levels) {
            for (const auto& table : tables) {
                for (const auto& entry : table.getEntries()) {
                    process(entry);
                }
            }
        }

        std::map<std::string, std::string> result;

        for (const auto& [key, entry] : latest) {
            if (entry.operation == Operation::PUT) {
                result[key] = entry.value;
            }
        }

        return result;
    }

    void printStatistics() const {
        std::cout << "\nLSM STORAGE STATISTICS\n";
        std::cout << "Sequence: " << sequence << '\n';
        std::cout << "Memtable keys: " << memtable.size() << '\n';

        std::size_t totalRuns = 0;
        std::size_t totalEntries = 0;

        for (const auto& [level, tables] : levels) {
            std::size_t entries = 0;

            for (const auto& table : tables) {
                entries += table.getEntries().size();
            }

            totalRuns += tables.size();
            totalEntries += entries;

            std::cout
                << "Level " << level
                << " | Runs: " << tables.size()
                << " | Entries: " << entries
                << '\n';
        }

        std::cout << "Total runs: " << totalRuns << '\n';
        std::cout << "Physical entries: "
                  << totalEntries << '\n';
    }

    bool validate() const {
        std::set<std::uint64_t> identifiers;

        for (const auto& [level, tables] : levels) {
            for (const auto& table : tables) {
                if (table.getLevel() != level) {
                    return false;
                }

                if (!identifiers.insert(table.getId()).second) {
                    return false;
                }

                const auto& entries = table.getEntries();

                for (std::size_t i = 1; i < entries.size(); ++i) {
                    if (entries[i - 1].key >= entries[i].key) {
                        return false;
                    }
                }
            }
        }

        for (const auto& [key, entry] : memtable) {
            if (entry.sequence > sequence) {
                return false;
            }
        }

        return true;
    }
};

int main() {
    try {
        LSMTree storage(3, 2, 2);

        std::cout << "IOT TELEMETRY LSM ENGINE\n";

        storage.put("sensor:001", "temperature=25.4");
        storage.put("sensor:002", "temperature=26.1");
        storage.put("sensor:003", "temperature=24.8");

        storage.put("sensor:002", "temperature=27.2");
        storage.remove("sensor:003");
        storage.put("sensor:004", "temperature=23.9");

        std::cout << "\nPOINT LOOKUPS\n";

        for (const auto& key : {
            "sensor:001",
            "sensor:002",
            "sensor:003",
            "sensor:004"
        }) {
            auto value = storage.get(key);

            std::cout << key << ": ";

            if (value) {
                std::cout << *value;
            } else {
                std::cout << "NOT FOUND";
            }

            std::cout << '\n';
        }

        std::cout << "\nRANGE SCAN\n";

        auto records = storage.rangeScan(
            "sensor:001",
            "sensor:004"
        );

        for (const auto& [key, value] : records) {
            std::cout << key << " -> " << value << '\n';
        }

        storage.flush();
        storage.printStatistics();

        std::cout << "\nINVARIANT VALIDATION\n";

        if (!storage.validate()) {
            throw std::runtime_error("LSM invariant violation");
        }

        if (storage.get("sensor:002") !=
            std::optional<std::string>("temperature=27.2")) {
            throw std::runtime_error("Version resolution failed");
        }

        if (storage.get("sensor:003").has_value()) {
            throw std::runtime_error("Tombstone resolution failed");
        }

        std::cout << "All validations passed.\n";

        std::cout << "\nCOMPACTION\n";
        storage.compact(0);
        storage.printStatistics();

        if (!storage.validate()) {
            throw std::runtime_error(
                "Post-compaction validation failed"
            );
        }

        std::cout << "Post-compaction checks passed.\n";

    } catch (const std::exception& error) {
        std::cerr << "Storage error: "
                  << error.what() << '\n';

        return 1;
    }

    return 0;
}
