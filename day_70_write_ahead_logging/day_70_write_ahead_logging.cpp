#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * Write-Ahead Logging: Repository-independent storage engine model.
 *
 * Features:
 * - Typed WAL records
 * - Monotonic LSN allocation
 * - CRC32 integrity checks
 * - Write-ahead ordering
 * - Transaction state management
 * - REDO and UNDO recovery
 * - Commit durability
 * - Checkpoint records
 * - Protected transaction transitions
 *
 * Compile:
 * g++ -std=c++17 -O2 -Wall -Wextra -pedantic wal.cpp -o wal
 */

enum class RecordType {
    BEGIN,
    UPDATE,
    COMMIT,
    ABORT,
    CHECKPOINT
};

std::string toString(RecordType type) {
    switch (type) {
        case RecordType::BEGIN: return "BEGIN";
        case RecordType::UPDATE: return "UPDATE";
        case RecordType::COMMIT: return "COMMIT";
        case RecordType::ABORT: return "ABORT";
        case RecordType::CHECKPOINT: return "CHECKPOINT";
    }
    throw std::invalid_argument("Unknown record type");
}

uint32_t crc32(const std::string& input) {
    uint32_t crc = 0xFFFFFFFF;

    for (unsigned char byte : input) {
        crc ^= byte;

        for (int i = 0; i < 8; ++i) {
            crc = (crc >> 1) ^
                ((crc & 1) ? 0xEDB88320 : 0);
        }
    }

    return crc ^ 0xFFFFFFFF;
}

struct WALRecord {
    uint64_t lsn;
    int transactionId;
    RecordType type;
    std::string key;
    std::optional<int64_t> oldValue;
    std::optional<int64_t> newValue;
    uint32_t checksum = 0;

    std::string payload() const {
        std::ostringstream out;

        out << lsn << '|'
            << transactionId << '|'
            << toString(type) << '|'
            << key << '|';

        if (oldValue) out << *oldValue;
        else out << "NULL";

        out << '|';

        if (newValue) out << *newValue;
        else out << "NULL";

        return out.str();
    }

    void calculateChecksum() {
        checksum = crc32(payload());
    }

    bool valid() const {
        return checksum == crc32(payload());
    }
};

class DurableWAL {
private:
    std::string filePath;
    uint64_t nextLSN = 1;
    std::vector<WALRecord> records;

public:
    explicit DurableWAL(std::string path)
        : filePath(std::move(path)) {
        load();
    }

    void load() {
        records.clear();
        nextLSN = 1;

        std::ifstream input(filePath, std::ios::binary);

        if (!input) {
            std::ofstream create(filePath, std::ios::binary);
            if (!create) {
                throw std::runtime_error("Cannot create WAL file");
            }
            return;
        }

        std::string line;

        while (std::getline(input, line)) {
            if (line.empty()) continue;

            std::istringstream stream(line);

            uint64_t lsn;
            int transactionId;
            std::string typeText;
            std::string key;
            std::string oldText;
            std::string newText;
            uint32_t checksum;

            if (!(stream >> lsn >> transactionId >> typeText
                  >> std::quoted(key) >> oldText >> newText
                  >> checksum)) {
                throw std::runtime_error("Malformed WAL record");
            }

            RecordType type;

            if (typeText == "BEGIN") type = RecordType::BEGIN;
            else if (typeText == "UPDATE") type = RecordType::UPDATE;
            else if (typeText == "COMMIT") type = RecordType::COMMIT;
            else if (typeText == "ABORT") type = RecordType::ABORT;
            else if (typeText == "CHECKPOINT") type = RecordType::CHECKPOINT;
            else throw std::runtime_error("Unknown WAL record");

            WALRecord record{
                lsn, transactionId, type, key, std::nullopt,
                std::nullopt, checksum
            };

            if (oldText != "NULL") {
                record.oldValue = std::stoll(oldText);
            }

            if (newText != "NULL") {
                record.newValue = std::stoll(newText);
            }

            if (record.lsn != nextLSN || !record.valid()) {
                throw std::runtime_error(
                    "WAL sequence or checksum validation failed"
                );
            }

            records.push_back(record);
            ++nextLSN;
        }
    }

    WALRecord append(
        int transactionId,
        RecordType type,
        const std::string& key = "",
        std::optional<int64_t> oldValue = std::nullopt,
        std::optional<int64_t> newValue = std::nullopt
    ) {
        WALRecord record{
            nextLSN,
            transactionId,
            type,
            key,
            oldValue,
            newValue
        };

        record.calculateChecksum();

        std::ofstream output(
            filePath,
            std::ios::binary | std::ios::app
        );

        if (!output) {
            throw std::runtime_error("Cannot open WAL for append");
        }

        output << record.lsn << ' '
               << record.transactionId << ' '
               << toString(record.type) << ' '
               << std::quoted(record.key) << ' ';

        if (record.oldValue) output << *record.oldValue;
        else output << "NULL";

        output << ' ';

        if (record.newValue) output << *record.newValue;
        else output << "NULL";

        output << ' ' << record.checksum << '\n';
        output.flush();

        if (!output) {
            throw std::runtime_error("WAL write failed");
        }

        // C++ stream flushing is not equivalent to fsync.
        // A production engine must use platform-specific durable I/O.

        records.push_back(record);
        ++nextLSN;

        return record;
    }

    const std::vector<WALRecord>& getRecords() const {
        return records;
    }

    uint64_t lastLSN() const {
        return nextLSN - 1;
    }
};

enum class TransactionState {
    ACTIVE,
    COMMITTED,
    ABORTED
};

struct Transaction {
    int id;
    TransactionState state = TransactionState::ACTIVE;
};

class StorageEngine {
private:
    DurableWAL wal;
    std::map<std::string, int64_t> pages;
    std::map<int, Transaction> transactions;
    std::set<std::string> dirtyPages;
    int nextTransactionId = 1;

    void requireActive(const Transaction& tx) const {
        auto found = transactions.find(tx.id);

        if (found == transactions.end() ||
            found->second.state != TransactionState::ACTIVE ||
            tx.state != TransactionState::ACTIVE) {
            throw std::logic_error("Transaction is not active");
        }
    }

public:
    explicit StorageEngine(const std::string& file)
        : wal(file) {}

    Transaction begin() {
        int id = nextTransactionId++;

        wal.append(id, RecordType::BEGIN);

        Transaction tx{id, TransactionState::ACTIVE};
        transactions.emplace(id, tx);

        std::cout << "BEGIN T" << id << '\n';
        return tx;
    }

    void update(
        Transaction& tx,
        const std::string& key,
        int64_t newValue
    ) {
        requireActive(tx);

        if (key.empty() || key.size() > 128) {
            throw std::invalid_argument("Invalid page key");
        }

        std::optional<int64_t> oldValue;

        auto found = pages.find(key);

        if (found != pages.end()) {
            oldValue = found->second;
        }

        // Log persistence precedes the in-memory page update.
        wal.append(
            tx.id,
            RecordType::UPDATE,
            key,
            oldValue,
            newValue
        );

        pages[key] = newValue;
        dirtyPages.insert(key);

        std::cout << "UPDATE " << key << " = "
                  << newValue << '\n';
    }

    void commit(Transaction& tx) {
        requireActive(tx);

        wal.append(tx.id, RecordType::COMMIT);

        tx.state = TransactionState::COMMITTED;
        transactions.at(tx.id).state = TransactionState::COMMITTED;

        std::cout << "COMMIT T" << tx.id << '\n';
    }

    void abort(Transaction& tx) {
        requireActive(tx);

        const auto& records = wal.getRecords();

        for (auto it = records.rbegin(); it != records.rend(); ++it) {
            if (it->transactionId != tx.id ||
                it->type != RecordType::UPDATE) {
                continue;
            }

            if (it->oldValue) {
                pages[it->key] = *it->oldValue;
            } else {
                pages.erase(it->key);
            }
        }

        wal.append(tx.id, RecordType::ABORT);

        tx.state = TransactionState::ABORTED;
        transactions.at(tx.id).state = TransactionState::ABORTED;
    }

    void checkpoint() {
        auto record = wal.append(0, RecordType::CHECKPOINT);
        dirtyPages.clear();

        std::cout << "CHECKPOINT LSN "
                  << record.lsn << '\n';
    }

    void simulateCrash() {
        pages.clear();
        transactions.clear();
        dirtyPages.clear();
        std::cout << "\n*** CRASH ***\n";
    }

    std::map<std::string, int64_t> recover() {
        const auto& records = wal.getRecords();

        std::set<int> active;
        std::set<int> committed;

        std::cout << "\n--- ANALYSIS ---\n";

        for (const auto& record : records) {
            switch (record.type) {
                case RecordType::BEGIN:
                    active.insert(record.transactionId);
                    break;

                case RecordType::COMMIT:
                    active.erase(record.transactionId);
                    committed.insert(record.transactionId);
                    break;

                case RecordType::ABORT:
                    active.erase(record.transactionId);
                    break;

                default:
                    break;
            }
        }

        std::cout << "Committed: " << committed.size()
                  << ", Incomplete: " << active.size() << '\n';

        std::cout << "\n--- REDO ---\n";

        for (const auto& record : records) {
            if (record.type != RecordType::UPDATE) continue;

            if (committed.count(record.transactionId) ||
                active.count(record.transactionId)) {
                pages[record.key] = *record.newValue;

                std::cout << "REDO LSN "
                          << record.lsn << '\n';
            }
        }

        std::cout << "\n--- UNDO ---\n";

        for (auto it = records.rbegin(); it != records.rend(); ++it) {
            if (it->type != RecordType::UPDATE ||
                !active.count(it->transactionId)) {
                continue;
            }

            if (it->oldValue) {
                pages[it->key] = *it->oldValue;
            } else {
                pages.erase(it->key);
            }

            std::cout << "UNDO LSN "
                      << it->lsn << '\n';
        }

        // Persist recovery outcomes to prevent repeated undo.
        for (int id : active) {
            wal.append(id, RecordType::ABORT);
        }

        return pages;
    }

    void printPages() const {
        std::cout << "\nDATABASE PAGES\n";

        for (const auto& [key, value] : pages) {
            std::cout << key << " = " << value << '\n';
        }
    }
};

int main() {
    try {
        const std::string walFile = "wal_storage.log";

        // Start with a clean demonstration log.
        {
            std::ofstream reset(walFile, std::ios::trunc);
            if (!reset) {
                throw std::runtime_error("Cannot initialize WAL");
            }
        }

        StorageEngine engine(walFile);

        std::cout << "--- NORMAL PROCESSING ---\n";

        auto first = engine.begin();
        engine.update(first, "account_A", 1000);
        engine.update(first, "account_B", 500);
        engine.commit(first);

        auto second = engine.begin();
        engine.update(second, "account_A", 800);
        engine.update(second, "account_B", 700);

        engine.printPages();

        engine.simulateCrash();

        std::cout << "\n--- RECOVERY ---\n";

        StorageEngine recovered(walFile);
        auto result = recovered.recover();

        recovered.printPages();

        if (result.at("account_A") != 1000 ||
            result.at("account_B") != 500) {
            throw std::runtime_error("Recovery assertion failed");
        }

        // A second recovery must not undo already resolved transactions.
        StorageEngine repeated(walFile);
        auto secondResult = repeated.recover();

        if (secondResult != result) {
            throw std::runtime_error("Idempotency assertion failed");
        }

        std::cout << "\nAll validations passed.\n";
    }
    catch (const std::exception& error) {
        std::cerr << "Storage engine failure: "
                  << error.what() << '\n';
        return 1;
    }

    return 0;
}
