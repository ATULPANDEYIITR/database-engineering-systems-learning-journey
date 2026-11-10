#include <algorithm>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * C++17 database checkpoint and recovery engine.
 *
 * Implements:
 * - WAL and durable LSN management
 * - Transaction lifecycle
 * - Buffer-pool page management
 * - Dirty-page tables
 * - Fuzzy checkpoints
 * - Analysis, redo and undo
 * - Commit durability
 * - Branch-independent recovery state
 */

using LSN = std::uint64_t;
using TransactionId = std::uint64_t;
using PageId = std::string;
using Value = std::int64_t;

enum class LogType {
    Begin,
    Update,
    Commit,
    Abort,
    End,
    CheckpointBegin,
    CheckpointEnd,
    Compensation
};

enum class TransactionState {
    Active,
    Committed,
    Aborted,
    Ended
};

enum class EngineState {
    Running,
    Crashed,
    Recovering,
    Recovered
};

std::string toString(LogType type) {
    switch (type) {
        case LogType::Begin: return "BEGIN";
        case LogType::Update: return "UPDATE";
        case LogType::Commit: return "COMMIT";
        case LogType::Abort: return "ABORT";
        case LogType::End: return "END";
        case LogType::CheckpointBegin: return "CHECKPOINT_BEGIN";
        case LogType::CheckpointEnd: return "CHECKPOINT_END";
        case LogType::Compensation: return "CLR";
    }

    throw std::logic_error("Unknown log type");
}

std::string toString(TransactionState state) {
    switch (state) {
        case TransactionState::Active: return "ACTIVE";
        case TransactionState::Committed: return "COMMITTED";
        case TransactionState::Aborted: return "ABORTED";
        case TransactionState::Ended: return "ENDED";
    }

    throw std::logic_error("Unknown transaction state");
}

struct LogRecord {
    LSN lsn;
    LogType type;
    std::optional<TransactionId> transactionId;
    std::optional<PageId> pageId;
    std::optional<Value> oldValue;
    std::optional<Value> newValue;
};

struct Page {
    PageId id;
    Value value = 0;
    LSN pageLSN = 0;
    std::optional<LSN> recLSN;
    bool dirty = false;
};

struct Transaction {
    TransactionId id;
    TransactionState state = TransactionState::Active;
    LSN lastLSN = 0;
};

struct Checkpoint {
    LSN beginLSN = 0;
    LSN endLSN = 0;
    std::map<PageId, LSN> dirtyPageTable;
    std::map<TransactionId, Transaction> transactionTable;
};

class WriteAheadLog {
private:
    std::vector<LogRecord> records_;
    LSN nextLSN_ = 1;
    LSN durableLSN_ = 0;

public:
    LSN append(
        LogType type,
        std::optional<TransactionId> transactionId = std::nullopt,
        std::optional<PageId> pageId = std::nullopt,
        std::optional<Value> oldValue = std::nullopt,
        std::optional<Value> newValue = std::nullopt
    ) {
        records_.push_back({
            nextLSN_,
            type,
            transactionId,
            pageId,
            oldValue,
            newValue
        });

        return nextLSN_++;
    }

    void flush(LSN target) {
        if (target < durableLSN_ || target >= nextLSN_) {
            throw std::invalid_argument("Invalid WAL flush target");
        }

        durableLSN_ = target;
    }

    LSN durableLSN() const {
        return durableLSN_;
    }

    LSN lastLSN() const {
        return nextLSN_ - 1;
    }

    const std::vector<LogRecord>& records() const {
        return records_;
    }

    std::vector<LogRecord> durableRecords() const {
        std::vector<LogRecord> result;

        for (const auto& record : records_) {
            if (record.lsn <= durableLSN_) {
                result.push_back(record);
            }
        }

        return result;
    }
};

class BufferPool {
private:
    std::map<PageId, Page> pages_;

public:
    void createPage(const PageId& id, Value value) {
        if (id.empty()) {
            throw std::invalid_argument("Empty page identifier");
        }

        if (pages_.count(id)) {
            throw std::invalid_argument("Duplicate page identifier");
        }

        pages_.emplace(id, Page{id, value});
    }

    Page& getPage(const PageId& id) {
        auto iterator = pages_.find(id);

        if (iterator == pages_.end()) {
            throw std::out_of_range("Page not found: " + id);
        }

        return iterator->second;
    }

    const Page& getPage(const PageId& id) const {
        auto iterator = pages_.find(id);

        if (iterator == pages_.end()) {
            throw std::out_of_range("Page not found: " + id);
        }

        return iterator->second;
    }

    void update(const PageId& id, Value value, LSN lsn) {
        Page& page = getPage(id);

        if (!page.dirty) {
            page.recLSN = lsn;
        }

        page.value = value;
        page.pageLSN = lsn;
        page.dirty = true;
    }

    std::map<PageId, LSN> dirtyPageTable() const {
        std::map<PageId, LSN> result;

        for (const auto& [id, page] : pages_) {
            if (page.dirty && page.recLSN.has_value()) {
                result[id] = *page.recLSN;
            }
        }

        return result;
    }

    void flush(
        const PageId& id,
        const WriteAheadLog& wal,
        std::map<PageId, Value>& disk
    ) {
        Page& page = getPage(id);

        if (!page.dirty) {
            return;
        }

        if (wal.durableLSN() < page.pageLSN) {
            throw std::runtime_error(
                "WAL durability violation for page " + id
            );
        }

        disk[id] = page.value;
        page.dirty = false;
        page.recLSN.reset();
    }

    const std::map<PageId, Page>& pages() const {
        return pages_;
    }
};

class DatabaseEngine {
private:
    WriteAheadLog wal_;
    BufferPool bufferPool_;

    std::map<TransactionId, Transaction> transactions_;
    std::vector<Checkpoint> checkpoints_;

    std::map<PageId, Value> disk_;

    TransactionId nextTransactionId_ = 1;
    EngineState state_ = EngineState::Running;

    void ensureRunning() const {
        if (state_ != EngineState::Running) {
            throw std::runtime_error("Database is not running");
        }
    }

    Transaction& activeTransaction(TransactionId id) {
        auto iterator = transactions_.find(id);

        if (
            iterator == transactions_.end() ||
            iterator->second.state != TransactionState::Active
        ) {
            throw std::runtime_error("Transaction is not active");
        }

        return iterator->second;
    }

    void rebuildBufferPoolFromDisk() {
        bufferPool_ = BufferPool();

        for (const auto& [id, value] : disk_) {
            bufferPool_.createPage(id, value);
        }
    }

public:
    void createPage(const PageId& id, Value value) {
        ensureRunning();

        bufferPool_.createPage(id, value);
        disk_[id] = value;
    }

    TransactionId begin() {
        ensureRunning();

        const TransactionId id = nextTransactionId_++;
        const LSN lsn = wal_.append(LogType::Begin, id);

        transactions_[id] = Transaction{
            id,
            TransactionState::Active,
            lsn
        };

        return id;
    }

    void update(
        TransactionId transactionId,
        const PageId& pageId,
        Value newValue
    ) {
        ensureRunning();

        Transaction& transaction = activeTransaction(transactionId);
        const Page& page = bufferPool_.getPage(pageId);

        const LSN lsn = wal_.append(
            LogType::Update,
            transactionId,
            pageId,
            page.value,
            newValue
        );

        bufferPool_.update(pageId, newValue, lsn);
        transaction.lastLSN = lsn;
    }

    void commit(TransactionId id) {
        ensureRunning();

        Transaction& transaction = activeTransaction(id);

        const LSN commitLSN = wal_.append(LogType::Commit, id);

        transaction.lastLSN = commitLSN;

        // Commit acknowledgement requires durable commit logging.
        wal_.flush(commitLSN);

        transaction.state = TransactionState::Committed;

        transaction.lastLSN = wal_.append(LogType::End, id);
    }

    void abort(TransactionId id) {
        ensureRunning();

        Transaction& transaction = activeTransaction(id);

        const LSN lsn = wal_.append(LogType::Abort, id);

        wal_.flush(lsn);
        transaction.state = TransactionState::Aborted;
        transaction.lastLSN = lsn;
    }

    void flushPage(const PageId& id) {
        ensureRunning();

        bufferPool_.flush(id, wal_, disk_);
    }

    void checkpoint() {
        ensureRunning();

        Checkpoint checkpoint;

        checkpoint.beginLSN = wal_.append(
            LogType::CheckpointBegin
        );

        checkpoint.dirtyPageTable = bufferPool_.dirtyPageTable();

        for (const auto& [id, transaction] : transactions_) {
            if (transaction.state == TransactionState::Active) {
                checkpoint.transactionTable[id] = transaction;
            }
        }

        checkpoint.endLSN = wal_.append(
            LogType::CheckpointEnd
        );

        wal_.flush(checkpoint.endLSN);
        checkpoints_.push_back(checkpoint);

        std::cout
            << "Checkpoint completed: "
            << checkpoint.beginLSN << " -> "
            << checkpoint.endLSN << '\n';
    }

    void crash() {
        ensureRunning();

        state_ = EngineState::Crashed;
        rebuildBufferPoolFromDisk();

        std::cout << "Database crash simulated.\n";
    }

    void recover() {
        if (state_ != EngineState::Crashed) {
            throw std::runtime_error("Database must be crashed");
        }

        state_ = EngineState::Recovering;

        const auto records = wal_.durableRecords();

        const Checkpoint* checkpoint = nullptr;

        for (auto iterator = checkpoints_.rbegin();
             iterator != checkpoints_.rend();
             ++iterator) {
            if (iterator->endLSN <= wal_.durableLSN()) {
                checkpoint = &(*iterator);
                break;
            }
        }

        LSN redoStart = 1;

        std::map<PageId, LSN> dirtyTable;

        if (checkpoint != nullptr) {
            dirtyTable = checkpoint->dirtyPageTable;

            if (!dirtyTable.empty()) {
                redoStart = std::min_element(
                    dirtyTable.begin(),
                    dirtyTable.end(),
                    [](const auto& a, const auto& b) {
                        return a.second < b.second;
                    }
                )->second;
            } else {
                redoStart = checkpoint->endLSN + 1;
            }
        }

        std::map<TransactionId, TransactionState> states;

        if (checkpoint != nullptr) {
            for (const auto& [id, transaction] :
                 checkpoint->transactionTable) {
                states[id] = transaction.state;
            }
        }

        // Analysis phase.
        for (const auto& record : records) {
            if (
                record.lsn < redoStart ||
                !record.transactionId.has_value()
            ) {
                continue;
            }

            const auto id = *record.transactionId;

            if (record.type == LogType::Begin) {
                states[id] = TransactionState::Active;
            } else if (record.type == LogType::Commit) {
                states[id] = TransactionState::Committed;
            } else if (record.type == LogType::Abort) {
                states[id] = TransactionState::Aborted;
            } else if (record.type == LogType::End) {
                states[id] = TransactionState::Ended;
            }
        }

        std::size_t redoCount = 0;
        std::size_t undoCount = 0;

        // Redo phase.
        for (const auto& record : records) {
            if (
                record.lsn < redoStart ||
                (record.type != LogType::Update &&
                 record.type != LogType::Compensation)
            ) {
                continue;
            }

            if (!record.pageId.has_value()) {
                continue;
            }

            Page& page = bufferPool_.getPage(*record.pageId);

            if (page.pageLSN >= record.lsn) {
                continue;
            }

            page.value = *record.newValue;
            page.pageLSN = record.lsn;
            page.dirty = true;

            if (!page.recLSN.has_value()) {
                page.recLSN = record.lsn;
            }

            ++redoCount;
        }

        // Build per-transaction log histories.
        std::map<TransactionId, std::vector<LogRecord>> histories;

        for (const auto& record : records) {
            if (record.transactionId.has_value()) {
                histories[*record.transactionId].push_back(record);
            }
        }

        // Undo phase: reverse uncommitted durable updates.
        for (auto& [id, history] : histories) {
            const bool committed =
                states[id] == TransactionState::Committed ||
                states[id] == TransactionState::Ended;

            if (committed) {
                continue;
            }

            std::reverse(history.begin(), history.end());

            for (const auto& record : history) {
                if (
                    record.type != LogType::Update &&
                    record.type != LogType::Compensation
                ) {
                    continue;
                }

                if (!record.pageId.has_value()) {
                    continue;
                }

                Page& page = bufferPool_.getPage(*record.pageId);

                if (page.pageLSN < record.lsn) {
                    continue;
                }

                const LSN clrLSN = wal_.append(
                    LogType::Compensation,
                    id,
                    record.pageId,
                    record.newValue,
                    record.oldValue
                );

                page.value = *record.oldValue;
                page.pageLSN = clrLSN;
                page.dirty = true;

                if (!page.recLSN.has_value()) {
                    page.recLSN = clrLSN;
                }

                ++undoCount;
            }

            if (transactions_.count(id)) {
                transactions_[id].state = TransactionState::Aborted;
            }
        }

        // Persist compensation records before writing recovered pages.
        if (wal_.lastLSN() > 0) {
            wal_.flush(wal_.lastLSN());
        }

        for (const auto& [id, page] : bufferPool_.pages()) {
            if (page.dirty) {
                bufferPool_.flush(id, wal_, disk_);
            }
        }

        state_ = EngineState::Recovered;

        std::cout << "\nRecovery report\n";
        std::cout << "Redo operations: " << redoCount << '\n';
        std::cout << "Undo operations: " << undoCount << '\n';

        for (const auto& [id, value] : disk_) {
            std::cout << id << " = " << value << '\n';
        }
    }

    void printState() const {
        std::cout << "\nEngine state\n";
        std::cout << "Durable LSN: " << wal_.durableLSN() << '\n';
        std::cout << "Latest LSN: " << wal_.lastLSN() << '\n';

        std::cout << "\nDisk pages\n";

        for (const auto& [id, value] : disk_) {
            std::cout << id << " = " << value << '\n';
        }

        std::cout << "\nTransactions\n";

        for (const auto& [id, transaction] : transactions_) {
            std::cout
                << id << " : "
                << toString(transaction.state) << '\n';
        }
    }
};

int main() {
    try {
        DatabaseEngine database;

        database.createPage("ACCOUNT_101", 1000);
        database.createPage("ACCOUNT_202", 2000);
        database.createPage("ACCOUNT_303", 3000);

        const auto tx1 = database.begin();

        database.update(tx1, "ACCOUNT_101", 1100);
        database.commit(tx1);

        database.flushPage("ACCOUNT_101");

        const auto tx2 = database.begin();

        database.update(tx2, "ACCOUNT_202", 1800);

        database.checkpoint();

        const auto tx3 = database.begin();

        database.update(tx3, "ACCOUNT_303", 3500);
        database.commit(tx3);

        database.update(tx2, "ACCOUNT_202", 1700);

        database.printState();

        database.crash();
        database.recover();

        database.printState();

        std::cout << "\nValidation completed.\n";

    } catch (const std::exception& error) {
        std::cerr << "Database error: "
                  << error.what() << '\n';
        return 1;
    }

    return 0;
}
