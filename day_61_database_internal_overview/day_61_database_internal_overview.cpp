#include <algorithm>
#include <cassert>
#include <cstddef>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <list>
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
 * Database Internals Overview
 * Query Engine, Storage Engine, and Buffer Manager
 *
 * C++17 case study:
 * A page-oriented storage engine is combined with an LRU buffer manager,
 * a secondary index, a query executor, and a merge-safe transaction model.
 *
 * The program uses only the C++17 standard library.
 */

constexpr std::size_t PAGE_CAPACITY = 6;
constexpr std::size_t BUFFER_POOL_CAPACITY = 3;

enum class PageType {
    Heap,
    Index
};

struct Record {
    int rowId{};
    int customerId{};
    std::string name;
    double balance{};

    void validate() const {
        if (rowId <= 0) {
            throw std::invalid_argument("rowId must be positive");
        }

        if (customerId <= 0) {
            throw std::invalid_argument("customerId must be positive");
        }

        if (name.empty() || name.size() > 80) {
            throw std::invalid_argument("name must contain 1-80 characters");
        }

        if (balance < -10000000.0 || balance > 10000000.0) {
            throw std::invalid_argument("balance outside supported range");
        }
    }
};

class Page {
public:
    Page(int id, PageType type)
        : id_(id), type_(type) {}

    int id() const {
        return id_;
    }

    PageType type() const {
        return type_;
    }

    bool dirty() const {
        return dirty_;
    }

    void markDirty(bool value) {
        dirty_ = value;
    }

    long long lsn() const {
        return lsn_;
    }

    void setLsn(long long value) {
        lsn_ = value;
    }

    const std::vector<Record>& records() const {
        return records_;
    }

    std::vector<Record>& records() {
        return records_;
    }

    void insert(Record record) {
        record.validate();

        if (records_.size() >= PAGE_CAPACITY) {
            throw std::runtime_error("page is full");
        }

        records_.push_back(std::move(record));
        dirty_ = true;
    }

    Record* find(int rowId) {
        for (auto& record : records_) {
            if (record.rowId == rowId) {
                return &record;
            }
        }
        return nullptr;
    }

private:
    int id_;
    PageType type_;
    std::vector<Record> records_;
    bool dirty_{false};
    long long lsn_{0};
};

class DiskManager {
public:
    explicit DiskManager(std::string file)
        : file_(std::move(file)) {}

    std::shared_ptr<Page> allocate(PageType type) {
        auto page = std::make_shared<Page>(nextPageId_++, type);
        pages_[page->id()] = page;
        return page;
    }

    std::shared_ptr<Page> read(int pageId) const {
        auto it = pages_.find(pageId);

        if (it == pages_.end()) {
            throw std::out_of_range("page does not exist");
        }

        return clone(*it->second);
    }

    void write(const std::shared_ptr<Page>& page) {
        if (!pages_.contains(page->id())) {
            throw std::out_of_range("cannot write unknown page");
        }

        pages_[page->id()] = clone(*page);
        pages_[page->id()]->markDirty(false);
    }

    const std::map<int, std::shared_ptr<Page>>& pages() const {
        return pages_;
    }

    void persist() const {
        std::ofstream output(file_);

        if (!output) {
            throw std::runtime_error("cannot open database file");
        }

        output << "NEXT " << nextPageId_ << '\n';

        for (const auto& [id, page] : pages_) {
            output << "PAGE "
                   << id << ' '
                   << (page->type() == PageType::Heap ? "HEAP" : "INDEX")
                   << '\n';

            for (const auto& record : page->records()) {
                output << "ROW "
                       << record.rowId << ' '
                       << record.customerId << ' '
                       << std::quoted(record.name) << ' '
                       << std::setprecision(17)
                       << record.balance
                       << '\n';
            }
        }
    }

private:
    static std::shared_ptr<Page> clone(const Page& source) {
        auto result = std::make_shared<Page>(
            source.id(),
            source.type()
        );

        result->records() = source.records();
        result->markDirty(source.dirty());
        result->setLsn(source.lsn());

        return result;
    }

    std::string file_;
    int nextPageId_{1};
    std::map<int, std::shared_ptr<Page>> pages_;
};

class BufferManager {
public:
    BufferManager(DiskManager& disk, std::size_t capacity)
        : disk_(disk), capacity_(capacity) {
        if (capacity == 0) {
            throw std::invalid_argument(
                "buffer pool capacity must be positive"
            );
        }
    }

    std::shared_ptr<Page> fetch(int pageId) {
        auto found = frames_.find(pageId);

        if (found != frames_.end()) {
            ++hits_;
            touch(pageId);
            return found->second;
        }

        ++misses_;

        if (frames_.size() >= capacity_) {
            evict();
        }

        auto page = disk_.read(pageId);
        frames_[pageId] = page;
        order_.push_back(pageId);

        return page;
    }

    void markDirty(int pageId, long long lsn) {
        auto page = fetch(pageId);
        page->markDirty(true);
        page->setLsn(lsn);
    }

    void flushAll() {
        for (auto& [id, page] : frames_) {
            if (page->dirty()) {
                disk_.write(page);
                page->markDirty(false);
                ++diskWrites_;
            }
        }
    }

    void printStatistics() const {
        const std::size_t accesses = hits_ + misses_;
        const double hitRate =
            accesses == 0
                ? 0.0
                : static_cast<double>(hits_) / accesses;

        std::cout
            << "Buffer hits: " << hits_ << '\n'
            << "Buffer misses: " << misses_ << '\n'
            << "Evictions: " << evictions_ << '\n'
            << "Disk writes: " << diskWrites_ << '\n'
            << "Hit rate: "
            << std::fixed << std::setprecision(3)
            << hitRate << '\n';
    }

private:
    void touch(int pageId) {
        order_.remove(pageId);
        order_.push_back(pageId);
    }

    void evict() {
        if (order_.empty()) {
            throw std::runtime_error("buffer pool has no eviction candidate");
        }

        const int pageId = order_.front();
        order_.pop_front();

        auto it = frames_.find(pageId);

        if (it == frames_.end()) {
            throw std::runtime_error("LRU metadata is inconsistent");
        }

        if (it->second->dirty()) {
            disk_.write(it->second);
            ++diskWrites_;
        }

        frames_.erase(it);
        ++evictions_;
    }

    DiskManager& disk_;
    std::size_t capacity_;
    std::unordered_map<int, std::shared_ptr<Page>> frames_;
    std::list<int> order_;

    std::size_t hits_{0};
    std::size_t misses_{0};
    std::size_t evictions_{0};
    std::size_t diskWrites_{0};
};

class HeapTable {
public:
    HeapTable(DiskManager& disk, BufferManager& buffer)
        : disk_(disk), buffer_(buffer) {}

    int insert(const Record& record) {
        record.validate();

        if (locator_.contains(record.rowId)) {
            throw std::invalid_argument("duplicate rowId");
        }

        std::shared_ptr<Page> target;

        for (auto it = pageIds_.rbegin(); it != pageIds_.rend(); ++it) {
            auto page = buffer_.fetch(*it);

            if (page->records().size() < PAGE_CAPACITY) {
                target = page;
                break;
            }
        }

        if (!target) {
            target = disk_.allocate(PageType::Heap);
            pageIds_.push_back(target->id());

            // Newly allocated pages do not exist in the buffer until fetched.
            target = buffer_.fetch(target->id());
        }

        target->insert(record);
        locator_[record.rowId] = target->id();

        return target->id();
    }

    std::optional<Record> get(int rowId) {
        auto it = locator_.find(rowId);

        if (it == locator_.end()) {
            return std::nullopt;
        }

        auto page = buffer_.fetch(it->second);
        auto record = page->find(rowId);

        if (!record) {
            throw std::runtime_error("locator points to missing record");
        }

        return *record;
    }

    std::pair<int, double> updateBalance(
        int rowId,
        double newBalance
    ) {
        auto it = locator_.find(rowId);

        if (it == locator_.end()) {
            throw std::out_of_range("row does not exist");
        }

        auto page = buffer_.fetch(it->second);
        auto record = page->find(rowId);

        if (!record) {
            throw std::runtime_error("row locator corruption");
        }

        if (newBalance < -10000000.0 ||
            newBalance > 10000000.0) {
            throw std::invalid_argument("invalid balance");
        }

        const double oldBalance = record->balance;
        record->balance = newBalance;
        page->markDirty(true);

        return {page->id(), oldBalance};
    }

    std::vector<Record> scan() {
        std::vector<Record> result;

        for (int pageId : pageIds_) {
            auto page = buffer_.fetch(pageId);

            result.insert(
                result.end(),
                page->records().begin(),
                page->records().end()
            );
        }

        return result;
    }

    const std::unordered_map<int, int>& locator() const {
        return locator_;
    }

private:
    DiskManager& disk_;
    BufferManager& buffer_;

    std::vector<int> pageIds_;
    std::unordered_map<int, int> locator_;
};

class SecondaryIndex {
public:
    void build(HeapTable& table) {
        entries_.clear();

        for (const auto& record : table.scan()) {
            entries_.emplace(
                record.customerId,
                table.locator().at(record.rowId)
            );
        }
    }

    std::vector<int> lookup(int customerId) const {
        std::vector<int> result;

        auto range = entries_.equal_range(customerId);

        for (auto it = range.first; it != range.second; ++it) {
            result.push_back(it->second);
        }

        return result;
    }

private:
    std::multimap<int, int> entries_;
};

class QueryEngine {
public:
    QueryEngine(
        HeapTable& table,
        SecondaryIndex& index,
        BufferManager& buffer
    )
        : table_(table),
          index_(index),
          buffer_(buffer) {}

    std::vector<Record> sequential(int customerId) {
        auto rows = table_.scan();

        std::vector<Record> result;

        std::copy_if(
            rows.begin(),
            rows.end(),
            std::back_inserter(result),
            [customerId](const Record& record) {
                return record.customerId == customerId;
            }
        );

        return result;
    }

    std::vector<Record> indexed(int customerId) {
        std::set<int> uniquePages;
        std::vector<Record> result;

        for (int pageId : index_.lookup(customerId)) {
            uniquePages.insert(pageId);
        }

        for (int pageId : uniquePages) {
            auto page = buffer_.fetch(pageId);

            for (const auto& record : page->records()) {
                if (record.customerId == customerId) {
                    result.push_back(record);
                }
            }
        }

        return result;
    }

private:
    HeapTable& table_;
    SecondaryIndex& index_;
    BufferManager& buffer_;
};

struct LogEntry {
    long long lsn;
    int transactionId;
    int pageId;
    int rowId;
    double oldBalance;
    double newBalance;
};

class Transaction {
public:
    Transaction(
        int id,
        HeapTable& table,
        BufferManager& buffer
    )
        : id_(id), table_(table), buffer_(buffer) {}

    void update(int rowId, double newBalance) {
        if (!active_) {
            throw std::logic_error("transaction is inactive");
        }

        auto [pageId, oldBalance] =
            table_.updateBalance(rowId, newBalance);

        logs_.push_back({
            nextLsn_++,
            id_,
            pageId,
            rowId,
            oldBalance,
            newBalance
        });

        buffer_.markDirty(pageId, logs_.back().lsn);
    }

    void commit() {
        if (!active_) {
            throw std::logic_error("transaction is inactive");
        }

        // WAL records would be forced before dirty data pages in a
        // production engine. Here the in-memory log already exists.
        buffer_.flushAll();
        active_ = false;
    }

    void rollback() {
        if (!active_) {
            throw std::logic_error("transaction is inactive");
        }

        for (auto it = logs_.rbegin(); it != logs_.rend(); ++it) {
            auto page = buffer_.fetch(it->pageId);
            auto record = page->find(it->rowId);

            if (!record) {
                throw std::runtime_error(
                    "rollback encountered missing record"
                );
            }

            record->balance = it->oldBalance;
            page->markDirty(true);
        }

        buffer_.flushAll();
        active_ = false;
    }

    std::size_t logCount() const {
        return logs_.size();
    }

private:
    int id_;
    HeapTable& table_;
    BufferManager& buffer_;
    bool active_{true};
    long long nextLsn_{1};
    std::vector<LogEntry> logs_;
};

int main() {
    try {
        DiskManager disk("database_internal_demo.db");
        BufferManager buffer(disk, BUFFER_POOL_CAPACITY);
        HeapTable table(disk, buffer);

        const std::vector<Record> rows = {
            {1, 101, "Asha", 1250.0},
            {2, 102, "Ravi", 840.0},
            {3, 101, "Meera", 2190.0},
            {4, 103, "Kabir", 450.0},
            {5, 104, "Nisha", 3300.0},
            {6, 102, "Arjun", 910.0},
            {7, 105, "Isha", 720.0},
            {8, 101, "Dev", 1500.0}
        };

        for (const auto& row : rows) {
            table.insert(row);
        }

        SecondaryIndex index;
        index.build(table);

        QueryEngine engine(table, index, buffer);

        const auto sequential = engine.sequential(101);
        const auto indexed = engine.indexed(101);

        std::set<int> sequentialIds;
        std::set<int> indexedIds;

        for (const auto& row : sequential) {
            sequentialIds.insert(row.rowId);
        }

        for (const auto& row : indexed) {
            indexedIds.insert(row.rowId);
        }

        assert(sequentialIds == indexedIds);

        Transaction transaction(7001, table, buffer);
        transaction.update(1, 1750.0);
        transaction.update(3, 2490.0);
        transaction.commit();

        assert(table.get(1)->balance == 1750.0);
        assert(table.get(3)->balance == 2490.0);

        Transaction rollbackTransaction(7002, table, buffer);
        rollbackTransaction.update(1, 9999.0);
        rollbackTransaction.rollback();

        assert(table.get(1)->balance == 1750.0);

        disk.persist();

        std::cout << "Database Internals Demonstration\n";
        std::cout << "--------------------------------\n";
        std::cout << "Heap pages: " << disk.pages().size() << '\n';
        std::cout << "Customer 101 rows: "
                  << indexed.size() << '\n';
        std::cout << "Transaction log entries: "
                  << transaction.logCount() << '\n';

        buffer.printStatistics();

        try {
            table.insert({1, 999, "Duplicate", 1.0});
        } catch (const std::exception& error) {
            std::cout
                << "Validation failure handled: "
                << error.what() << '\n';
        }

        try {
            disk.read(999999);
        } catch (const std::exception& error) {
            std::cout
                << "Storage failure handled: "
                << error.what() << '\n';
        }

        std::cout << "Database state persisted to "
                  << "database_internal_demo.db\n";
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal database-engine error: "
            << error.what() << '\n';
        return 1;
    }

    return 0;
}
