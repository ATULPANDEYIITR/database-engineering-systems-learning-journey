#include <algorithm>
#include <cmath>
#include <cstdint>
#include <functional>
#include <iomanip>
#include <iostream>
#include <list>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

// ============================================================
// 1. DOMAIN TYPES
// ============================================================

enum class TransactionState {
    Active,
    Committed,
    Aborted
};

enum class PageType {
    Heap,
    Index
};

enum class ReviewDecision {
    Pending,
    Approved,
    ChangesRequested,
    Commented
};

enum class CheckStatus {
    Pending,
    Running,
    Passed,
    Failed
};

enum class MergeStrategy {
    MergeCommit,
    Squash,
    Rebase
};

struct Employee {
    int id;
    string name;
    string department;
    double salary;
};

struct Page {
    int id;
    PageType type;
    vector<Employee> records;
    bool dirty = false;
    uint64_t pageLSN = 0;
};

struct LogRecord {
    uint64_t lsn;
    int transactionId;
    string operation;
    int pageId;
    optional<Employee> before;
    optional<Employee> after;
};

// ============================================================
// 2. EXCEPTIONS
// ============================================================

class DatabaseException : public runtime_error {
public:
    explicit DatabaseException(const string& message)
        : runtime_error(message) {}
};

class ConstraintException : public DatabaseException {
public:
    explicit ConstraintException(const string& message)
        : DatabaseException(message) {}
};

class TransactionException : public DatabaseException {
public:
    explicit TransactionException(const string& message)
        : DatabaseException(message) {}
};

// ============================================================
// 3. WRITE-AHEAD LOG
// ============================================================

class WriteAheadLog {
private:
    vector<LogRecord> records;
    uint64_t nextLSN = 1;
    uint64_t durableLSN = 0;

public:
    uint64_t append(
        int transactionId,
        const string& operation,
        int pageId,
        optional<Employee> before = nullopt,
        optional<Employee> after = nullopt
    ) {
        LogRecord record{
            nextLSN++,
            transactionId,
            operation,
            pageId,
            before,
            after
        };

        records.push_back(record);
        return record.lsn;
    }

    void flush() {
        if (!records.empty()) {
            durableLSN = records.back().lsn;
        }
    }

    uint64_t getDurableLSN() const {
        return durableLSN;
    }

    const vector<LogRecord>& getRecords() const {
        return records;
    }

    vector<LogRecord> transactionRecords(int transactionId) const {
        vector<LogRecord> result;

        copy_if(
            records.begin(),
            records.end(),
            back_inserter(result),
            [transactionId](const LogRecord& record) {
                return record.transactionId == transactionId;
            }
        );

        return result;
    }
};

// ============================================================
// 4. DISK MANAGER
// ============================================================

class DiskManager {
private:
    unordered_map<int, Page> storage;
    int nextPageId = 1;

public:
    Page allocate(PageType type) {
        Page page;
        page.id = nextPageId++;
        page.type = type;

        storage.emplace(page.id, page);
        return page;
    }

    Page read(int pageId) const {
        auto it = storage.find(pageId);

        if (it == storage.end()) {
            throw DatabaseException("Page does not exist.");
        }

        return it->second;
    }

    void write(const Page& page, uint64_t durableLSN) {
        if (page.pageLSN > durableLSN) {
            throw DatabaseException(
                "WAL durability rule violated."
            );
        }

        storage[page.id] = page;
    }

    bool exists(int pageId) const {
        return storage.find(pageId) != storage.end();
    }

    size_t pageCount() const {
        return storage.size();
    }
};

// ============================================================
// 5. LRU BUFFER POOL
// ============================================================

class BufferPool {
private:
    struct Frame {
        Page page;
        list<int>::iterator position;
    };

    size_t capacity;
    DiskManager& disk;
    WriteAheadLog& wal;

    unordered_map<int, Frame> frames;
    list<int> lru;

    size_t hits = 0;
    size_t misses = 0;
    size_t evictions = 0;

    void evict() {
        if (frames.empty()) return;

        int victimId = lru.back();
        Frame& frame = frames.at(victimId);

        if (frame.page.dirty) {
            wal.flush();
            disk.write(frame.page, wal.getDurableLSN());
        }

        frames.erase(victimId);
        lru.pop_back();
        ++evictions;
    }

public:
    BufferPool(
        size_t capacity,
        DiskManager& disk,
        WriteAheadLog& wal
    ) : capacity(capacity), disk(disk), wal(wal) {
        if (capacity == 0) {
            throw invalid_argument(
                "Buffer pool capacity must be positive."
            );
        }
    }

    Page& fetch(int pageId) {
        auto it = frames.find(pageId);

        if (it != frames.end()) {
            ++hits;
            lru.erase(it->second.position);
            lru.push_front(pageId);
            it->second.position = lru.begin();

            return it->second.page;
        }

        ++misses;

        if (frames.size() >= capacity) {
            evict();
        }

        Page page = disk.read(pageId);

        lru.push_front(pageId);

        Frame frame{
            page,
            lru.begin()
        };

        auto inserted = frames.emplace(pageId, frame);

        return inserted.first->second.page;
    }

    void insertNew(const Page& page) {
        if (frames.size() >= capacity) {
            evict();
        }

        lru.push_front(page.id);

        frames.emplace(
            page.id,
            Frame{page, lru.begin()}
        );
    }

    void flushAll() {
        wal.flush();

        for (auto& entry : frames) {
            Page& page = entry.second.page;

            if (page.dirty) {
                disk.write(page, wal.getDurableLSN());
                page.dirty = false;
            }
        }
    }

    double hitRatio() const {
        size_t total = hits + misses;

        return total == 0
            ? 0.0
            : static_cast<double>(hits) / total;
    }

    void printStatistics() const {
        cout << "Buffer pool hits: " << hits << '\n';
        cout << "Buffer pool misses: " << misses << '\n';
        cout << "Buffer pool evictions: " << evictions << '\n';
        cout << fixed << setprecision(2);
        cout << "Hit ratio: " << hitRatio() * 100 << "%\n";
    }
};

// ============================================================
// 6. DATABASE TRANSACTION
// ============================================================

class Database;

class Transaction {
private:
    int id;
    Database& database;
    TransactionState state = TransactionState::Active;

    struct UndoEntry {
        int pageId;
        int slot;
        Employee employee;
    };

    vector<UndoEntry> undoLog;

    friend class Database;

public:
    Transaction(int id, Database& database)
        : id(id), database(database) {}

    int getId() const {
        return id;
    }

    TransactionState getState() const {
        return state;
    }

    void commit();
    void rollback();
};

// ============================================================
// 7. DATABASE ENGINE AND HASH INDEX
// ============================================================

class Database {
private:
    DiskManager disk;
    WriteAheadLog wal;
    BufferPool buffer;

    unordered_map<string, vector<int>> tables;
    unordered_map<int, pair<int, int>> employeeIndex;

    int nextTransactionId = 1;
    int nextEmployeeId = 1;

    friend class Transaction;

public:
    explicit Database(size_t bufferCapacity)
        : buffer(bufferCapacity, disk, wal) {}

    Transaction begin() {
        return Transaction(nextTransactionId++, *this);
    }

    void insert(
        Transaction& transaction,
        const string& table,
        Employee employee
    ) {
        if (transaction.state != TransactionState::Active) {
            throw TransactionException(
                "Cannot modify an inactive transaction."
            );
        }

        if (table.empty()) {
            throw invalid_argument("Table name is required.");
        }

        if (employee.id <= 0 ||
            employee.name.empty() ||
            employee.department.empty() ||
            !isfinite(employee.salary) ||
            employee.salary < 0) {
            throw ConstraintException(
                "Invalid employee record."
            );
        }

        if (employeeIndex.count(employee.id)) {
            throw ConstraintException(
                "Duplicate employee identifier."
            );
        }

        if (employee.id >= nextEmployeeId) {
            nextEmployeeId = employee.id + 1;
        }

        Page* target = nullptr;

        for (int pageId : tables[table]) {
            Page& page = buffer.fetch(pageId);

            if (page.records.size() < 3) {
                target = &page;
                break;
            }
        }

        if (target == nullptr) {
            Page page = disk.allocate(PageType::Heap);
            int pageId = page.id;

            tables[table].push_back(pageId);
            buffer.insertNew(page);

            target = &buffer.fetch(pageId);
        }

        int slot = static_cast<int>(target->records.size());

        uint64_t lsn = wal.append(
            transaction.id,
            "INSERT",
            target->id,
            nullopt,
            employee
        );

        target->records.push_back(employee);
        target->pageLSN = lsn;
        target->dirty = true;

        employeeIndex[employee.id] = {
            target->id,
            slot
        };

        transaction.undoLog.push_back({
            target->id,
            slot,
            employee
        });
    }

    optional<Employee> findById(int employeeId) {
        auto it = employeeIndex.find(employeeId);

        if (it == employeeIndex.end()) {
            return nullopt;
        }

        auto [pageId, slot] = it->second;

        Page& page = buffer.fetch(pageId);

        if (slot < 0 ||
            static_cast<size_t>(slot) >= page.records.size()) {
            throw DatabaseException("Stale index entry.");
        }

        return page.records[slot];
    }

    vector<Employee> scan(const string& table) {
        vector<Employee> result;

        auto it = tables.find(table);

        if (it == tables.end()) return result;

        for (int pageId : it->second) {
            Page& page = buffer.fetch(pageId);

            result.insert(
                result.end(),
                page.records.begin(),
                page.records.end()
            );
        }

        return result;
    }

    void rollbackInsert(
        int pageId,
        int slot,
        int employeeId
    ) {
        Page& page = buffer.fetch(pageId);

        if (slot < 0 ||
            static_cast<size_t>(slot) >= page.records.size()) {
            throw DatabaseException(
                "Undo location is invalid."
            );
        }

        page.records.erase(page.records.begin() + slot);
        page.dirty = true;

        employeeIndex.erase(employeeId);

        // Slots following the deleted position shift by one.
        for (size_t i = static_cast<size_t>(slot);
             i < page.records.size();
             ++i) {
            employeeIndex[page.records[i].id] = {
                pageId,
                static_cast<int>(i)
            };
        }
    }

    void commit(Transaction& transaction) {
        if (transaction.state != TransactionState::Active) {
            throw TransactionException(
                "Transaction cannot be committed."
            );
        }

        wal.append(
            transaction.id,
            "COMMIT",
            0
        );

        wal.flush();
        buffer.flushAll();

        transaction.undoLog.clear();
        transaction.state = TransactionState::Committed;
    }

    void rollback(Transaction& transaction) {
        if (transaction.state != TransactionState::Active) {
            throw TransactionException(
                "Transaction cannot be rolled back."
            );
        }

        for (auto it = transaction.undoLog.rbegin();
             it != transaction.undoLog.rend();
             ++it) {
            rollbackInsert(
                it->pageId,
                it->slot,
                it->employee.id
            );
        }

        wal.append(
            transaction.id,
            "ABORT",
            0
        );

        wal.flush();
        buffer.flushAll();

        transaction.undoLog.clear();
        transaction.state = TransactionState::Aborted;
    }

    void flush() {
        buffer.flushAll();
    }

    void printStatistics() const {
        cout << "Allocated pages: " << disk.pageCount() << '\n';
        cout << "WAL records: " << wal.getRecords().size() << '\n';
        buffer.printStatistics();
    }
};

void Transaction::commit() {
    database.commit(*this);
}

void Transaction::rollback() {
    database.rollback(*this);
}

// ============================================================
// 8. RELATIONAL QUERY OPERATORS
// ============================================================

class QueryOperator {
public:
    virtual ~QueryOperator() = default;

    virtual vector<Employee> execute() = 0;
};

class TableScanOperator : public QueryOperator {
private:
    Database& database;
    string table;

public:
    TableScanOperator(Database& database, string table)
        : database(database), table(move(table)) {}

    vector<Employee> execute() override {
        return database.scan(table);
    }
};

class FilterOperator : public QueryOperator {
private:
    unique_ptr<QueryOperator> child;
    function<bool(const Employee&)> predicate;

public:
    FilterOperator(
        unique_ptr<QueryOperator> child,
        function<bool(const Employee&)> predicate
    ) : child(move(child)), predicate(move(predicate)) {}

    vector<Employee> execute() override {
        vector<Employee> input = child->execute();
        vector<Employee> output;

        copy_if(
            input.begin(),
            input.end(),
            back_inserter(output),
            predicate
        );

        return output;
    }
};

class SortOperator : public QueryOperator {
private:
    unique_ptr<QueryOperator> child;

public:
    explicit SortOperator(unique_ptr<QueryOperator> child)
        : child(move(child)) {}

    vector<Employee> execute() override {
        vector<Employee> rows = child->execute();

        sort(
            rows.begin(),
            rows.end(),
            [](const Employee& a, const Employee& b) {
                return a.salary > b.salary;
            }
        );

        return rows;
    }
};

class HashAggregate {
public:
    struct Result {
        string department;
        size_t count;
        double sum;
        double average;
        double minimum;
        double maximum;
    };

    static vector<Result> execute(
        const vector<Employee>& rows
    ) {
        struct Accumulator {
            size_t count = 0;
            double sum = 0;
            double minimum = numeric_limits<double>::max();
            double maximum = numeric_limits<double>::lowest();
        };

        unordered_map<string, Accumulator> groups;

        for (const Employee& employee : rows) {
            auto& group = groups[employee.department];

            ++group.count;
            group.sum += employee.salary;
            group.minimum = min(
                group.minimum,
                employee.salary
            );
            group.maximum = max(
                group.maximum,
                employee.salary
            );
        }

        vector<Result> results;

        for (const auto& [department, group] : groups) {
            results.push_back({
                department,
                group.count,
                group.sum,
                group.sum / group.count,
                group.minimum,
                group.maximum
            });
        }

        return results;
    }
};

// ============================================================
// 9. COST-BASED ACCESS PATH SELECTION
// ============================================================

class QueryPlanner {
public:
    struct Plan {
        string accessPath;
        double scanCost;
        double indexCost;
    };

    Plan choose(
        size_t rows,
        size_t distinctValues,
        size_t recordsPerPage
    ) const {
        if (recordsPerPage == 0) {
            throw invalid_argument(
                "Page capacity cannot be zero."
            );
        }

        double scanCost = ceil(
            static_cast<double>(rows) / recordsPerPage
        );

        double indexCost;

        if (rows == 0 || distinctValues == 0) {
            indexCost = numeric_limits<double>::infinity();
        } else {
            indexCost = log2(max<size_t>(2, rows))
                + static_cast<double>(rows) / distinctValues;
        }

        return {
            indexCost < scanCost ? "INDEX_SCAN" : "TABLE_SCAN",
            scanCost,
            indexCost
        };
    }
};

// ============================================================
// 10. APPLICATION
// ============================================================

int main() {
    try {
        Database database(2);

        auto transaction = database.begin();

        transaction.commit();

        auto insertTransaction = database.begin();

        database.insert(
            insertTransaction,
            "employees",
            {101, "Asha", "Engineering", 90000}
        );

        database.insert(
            insertTransaction,
            "employees",
            {102, "Ravi", "Engineering", 85000}
        );

        database.insert(
            insertTransaction,
            "employees",
            {103, "Meera", "Research", 110000}
        );

        database.insert(
            insertTransaction,
            "employees",
            {104, "Kabir", "Research", 95000}
        );

        insertTransaction.commit();

        cout << "\nINDEX LOOKUP\n";

        auto employee = database.findById(103);

        if (employee) {
            cout << employee->name
                 << " | "
                 << employee->department
                 << " | "
                 << employee->salary
                 << '\n';
        }

        cout << "\nQUERY PIPELINE\n";

        unique_ptr<QueryOperator> query =
            make_unique<SortOperator>(
                make_unique<FilterOperator>(
                    make_unique<TableScanOperator>(
                        database,
                        "employees"
                    ),
                    [](const Employee& employee) {
                        return employee.salary >= 90000;
                    }
                )
            );

        vector<Employee> results = query->execute();

        for (const Employee& employee : results) {
            cout << employee.id
                 << " | "
                 << employee.name
                 << " | "
                 << employee.department
                 << " | "
                 << employee.salary
                 << '\n';
        }

        cout << "\nHASH AGGREGATION\n";

        auto aggregates = HashAggregate::execute(
            database.scan("employees")
        );

        for (const auto& group : aggregates) {
            cout << group.department
                 << " | count=" << group.count
                 << " | average=" << group.average
                 << " | min=" << group.minimum
                 << " | max=" << group.maximum
                 << '\n';
        }

        cout << "\nQUERY PLANNER\n";

        QueryPlanner planner;

        auto plan = planner.choose(
            100000,
            100000,
            64
        );

        cout << "Selected: " << plan.accessPath << '\n';
        cout << "Scan cost: " << plan.scanCost << '\n';
        cout << "Index cost: " << plan.indexCost << '\n';

        cout << "\nTRANSACTION ROLLBACK TEST\n";

        auto rollbackTransaction = database.begin();

        database.insert(
            rollbackTransaction,
            "employees",
            {105, "Temporary", "Testing", 50000}
        );

        rollbackTransaction.rollback();

        if (!database.findById(105)) {
            cout << "Rollback verification: PASSED\n";
        } else {
            throw DatabaseException(
                "Rollback failed."
            );
        }

        cout << "\nDATABASE STATISTICS\n";
        database.printStatistics();

        cout << "\nALL TESTS PASSED\n";

    } catch (const exception& error) {
        cerr << "Database failure: "
             << error.what()
             << '\n';

        return 1;
    }

    return 0;
}
